"""KrushiMitra AI - FastAPI application.

Serves the processed forecast data (read-only), two cached live proxies (weather, mandi prices)
and, in production, the built React frontend from the same origin.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import Settings, get_settings
from .security import RateLimiter, SecurityHeadersMiddleware, client_ip
from .services import COMMODITIES, LiveServices, UpstreamError, make_client
from .store import DataStore

log = logging.getLogger("krushimitra")

Slug = Annotated[str, Path(pattern=r"^[a-z]{3,20}$", description="District slug, e.g. 'cuttack'")]
Lead = Literal["Jul", "Aug", "Sep", "Oct", "Nov"]


def create_app(settings: Settings | None = None, store: DataStore | None = None, transport=None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = store or DataStore.load(settings.data_dir)
    limiter = RateLimiter(settings.live_rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = make_client(settings.upstream_timeout_seconds, transport)
        api_key = settings.data_gov_in_api_key.get_secret_value() if settings.data_gov_in_api_key else None
        app.state.live = LiveServices(client, api_key, settings.weather_cache_seconds, settings.market_cache_seconds)
        yield
        await client.aclose()

    app = FastAPI(
        title="KrushiMitra AI",
        version=__version__,
        description="Kharif rice yield forecasts for Odisha's 30 districts, with honest uncertainty.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.store = store
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"], allow_credentials=False
        )
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):  # never leak internals to clients
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    def district_or_404(slug: str) -> dict:
        district = store.by_slug.get(slug)
        if district is None:
            raise HTTPException(status_code=404, detail="Unknown district")
        return district

    # ------------------------------------------------------------------ metadata
    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "version": __version__, "data_generated_at": store.forecasts["generated_at"]}

    @app.get("/api/meta", tags=["meta"])
    def meta() -> dict:
        ev = store.evaluation
        return {
            "version": __version__,
            "generated_at": store.forecasts["generated_at"],
            "weather_through": store.forecasts["weather_through"],
            "last_season_with_official_yield": store.forecasts["last_season_with_official_yield"],
            "model": store.forecasts["model"],
            "model_by_lead": store.forecasts.get("model_by_lead", {}),
            "target": ev["target"],
            "leads": store.leads,
            "forecast_years": {str(y): store.leads_for_year(y) for y in store.forecast_years()},
            "features": {"market_prices": settings.market_prices_enabled, "live_weather": True},
            "commodities": {k: v for k, v in COMMODITIES.items()},
        }

    @app.get("/api/model-card", tags=["meta"])
    def model_card() -> dict:
        ev = store.evaluation
        compact = [
            {
                "key": c["key"],
                "model": c["model"],
                "features": c["features"],
                "trend_window": c["trend_window"],
                "in_selection_pool": c.get("in_selection_pool", False),
                "validation_rmse_mean": c["validation_rmse_mean"],
                "test_rmse_mean": c["test_rmse_mean"],
                "by_lead": c["by_lead"],
            }
            for c in ev["candidates"]
        ]
        return {
            "generated_at": ev["generated_at"],
            "target": ev["target"],
            "data": {k: v for k, v in ev["data"].items() if k != "flagged_rows"},
            "flagged_rows": ev["data"]["flagged_rows"],
            "protocol": ev["protocol"],
            "candidates": compact,
            "baselines": ev["baselines"],
            "chosen": ev["chosen"],
        }

    # ------------------------------------------------------------------ districts & history
    @app.get("/api/districts", tags=["districts"])
    def districts() -> list[dict]:
        return store.districts

    @app.get("/api/districts/geojson", tags=["districts"])
    def districts_geojson(request: Request) -> Response:
        headers = {"ETag": store.geojson_etag, "Cache-Control": "public, max-age=86400"}
        if request.headers.get("if-none-match") == store.geojson_etag:
            return Response(status_code=304, headers=headers)
        return Response(content=store.geojson, media_type="application/geo+json", headers=headers)

    @app.get("/api/districts/{slug}", tags=["districts"])
    def district(slug: Slug) -> dict:
        d = district_or_404(slug)
        return {**d, "kharif_rice": store.kharif.get(slug, []), "crops": store.crops.get(slug, {})}

    @app.get("/api/districts/{slug}/yields", tags=["districts"])
    def district_yields(
        slug: Slug,
        crop: Annotated[str, Query(min_length=2, max_length=60)] = "Rice",
        season: Annotated[str | None, Query(max_length=30)] = None,
    ) -> dict:
        district_or_404(slug)
        seasons = store.crops.get(slug, {}).get(crop)
        if seasons is None:
            raise HTTPException(status_code=404, detail="Unknown crop for this district")
        rows = [
            r for r in store.yields.get(slug, []) if r["crop"] == crop and (season is None or r["season"] == season)
        ]
        return {"district": slug, "crop": crop, "season": season, "seasons": seasons, "rows": rows}

    @app.get("/api/districts/{slug}/weather", tags=["districts"])
    def district_weather(slug: Slug, year: Annotated[int, Query(ge=1991, le=2100)]) -> dict:
        district_or_404(slug)
        months = [r for r in store.weather.get(slug, []) if r["year"] == year and 6 <= r["month"] <= 11]
        return {"district": slug, "year": year, "months": months}

    # ------------------------------------------------------------------ forecasts
    @app.get("/api/forecasts", tags=["forecasts"])
    def forecasts(year: Annotated[int, Query(ge=1998, le=2100)], lead: Lead) -> dict:
        rows = store.forecasts_for(year, lead)
        if not rows:
            raise HTTPException(status_code=404, detail="No forecast for this season and lead time")
        # The state interval is calibrated on state-level errors in the pipeline (averaging
        # district bounds would overstate the uncertainty of the aggregate).
        state = next(
            (
                {k: v for k, v in s.items() if k not in ("year", "lead")}
                for s in store.forecasts.get("state", [])
                if s["year"] == year and s["lead"] == lead
            ),
            None,
        )
        slim = [{k: v for k, v in r.items() if k not in ("drivers", "cyclones")} for r in rows]
        return {"year": year, "lead": lead, "state": state, "districts": slim}

    @app.get("/api/forecasts/{slug}", tags=["forecasts"])
    def district_forecasts(slug: Slug) -> dict:
        district_or_404(slug)
        return {"district": slug, "forecasts": store.forecasts_for_district(slug)}

    @app.get("/api/backtest/{slug}", tags=["forecasts"])
    def district_backtest(slug: Slug, lead: Lead = "Oct") -> dict:
        district_or_404(slug)
        return {"district": slug, "lead": lead, "rows": store.backtest.get((slug, lead), [])}

    # ------------------------------------------------------------------ live proxies
    def live(request: Request) -> LiveServices:
        limiter.check(client_ip(request))
        return request.app.state.live

    @app.get("/api/live/weather/{slug}", tags=["live"])
    async def live_weather(slug: Slug, request: Request) -> dict:
        d = district_or_404(slug)
        try:
            return await live(request).weather(d["lat"], d["lon"])
        except UpstreamError:
            raise HTTPException(status_code=502, detail="Weather service unavailable, try again later") from None

    @app.get("/api/live/market-prices/{slug}", tags=["live"])
    async def live_market(
        slug: Slug, request: Request, commodity: Annotated[str, Query(pattern=r"^[a-z-]{3,20}$")] = "paddy"
    ) -> dict:
        d = district_or_404(slug)
        if not settings.market_prices_enabled:
            raise HTTPException(status_code=503, detail="Market prices are not enabled on this server")
        if commodity not in COMMODITIES:
            raise HTTPException(status_code=404, detail="Unknown commodity")
        try:
            return await live(request).market_prices(d["name"], commodity)
        except UpstreamError:
            raise HTTPException(status_code=502, detail="Market price service unavailable, try again later") from None

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str) -> None:
        raise HTTPException(status_code=404, detail="Not found")

    # ------------------------------------------------------------------ frontend (production build)
    dist = settings.frontend_dist
    if (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        index = dist / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
