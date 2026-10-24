"""Live data proxies: Open-Meteo weather forecast and data.gov.in (Agmarknet) mandi prices.

Both are reached only with allow-listed parameters (a known district centroid, a known
commodity), and responses are cached, so the number of upstream calls is bounded no matter how
much traffic the app receives. API keys never leave the server.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

log = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
USER_AGENT = "KrushiMitraAI/1.0 (+https://github.com/YashPandit09/KrushiMitraAi)"

# Agmarknet commodity names (as published) offered in the app.
COMMODITIES = {
    "paddy": "Paddy(Dhan)(Common)",
    "rice": "Rice",
    "maize": "Maize",
    "green-gram": "Green Gram (Moong)(Whole)",
    "black-gram": "Black Gram (Urd Beans)(Whole)",
    "groundnut": "Groundnut",
    "mustard": "Mustard",
    "potato": "Potato",
    "onion": "Onion",
    "tomato": "Tomato",
    "brinjal": "Brinjal",
}


class UpstreamError(Exception):
    """An upstream service failed or returned something unusable."""


class TTLCache:
    """Async-safe TTL cache with one in-flight fetch per key (no thundering herd)."""

    def __init__(self, max_entries: int = 1024) -> None:
        self._data: dict[tuple, tuple[float, Any]] = {}
        self._locks: dict[tuple, asyncio.Lock] = {}
        self.max_entries = max_entries

    async def get_or_fetch(self, key: tuple, ttl: float, fetch: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._data.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self._data.get(key)
            if hit and hit[0] > time.monotonic():
                return hit[1]
            value = await fetch()
            if len(self._data) >= self.max_entries:
                self._data.clear()
            self._data[key] = (time.monotonic() + ttl, value)
            return value


class LiveServices:
    def __init__(self, client: httpx.AsyncClient, api_key: str | None, weather_ttl: int, market_ttl: int) -> None:
        self.client = client
        self.api_key = api_key
        self.weather_ttl = weather_ttl
        self.market_ttl = market_ttl
        self.cache = TTLCache()

    async def weather(self, lat: float, lon: float) -> dict:
        async def fetch() -> dict:
            params = {
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "daily": ",".join(
                    [
                        "precipitation_sum",
                        "precipitation_probability_max",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "wind_speed_10m_max",
                    ]
                ),
                "timezone": "Asia/Kolkata",
                "forecast_days": "7",
            }
            data = await self._get_json(OPEN_METEO_URL, params)
            daily = data.get("daily")
            if not isinstance(daily, dict) or "time" not in daily:
                raise UpstreamError("unexpected weather response")
            days = []
            for i, day in enumerate(daily["time"]):
                days.append(
                    {
                        "date": day,
                        "rain_mm": _pick(daily, "precipitation_sum", i),
                        "rain_probability_pct": _pick(daily, "precipitation_probability_max", i),
                        "tmax_c": _pick(daily, "temperature_2m_max", i),
                        "tmin_c": _pick(daily, "temperature_2m_min", i),
                        "wind_max_kmh": _pick(daily, "wind_speed_10m_max", i),
                    }
                )
            return {
                "days": days,
                "source": "Open-Meteo.com (CC BY 4.0)",
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        return await self.cache.get_or_fetch(("weather", round(lat, 3), round(lon, 3)), self.weather_ttl, fetch)

    async def market_prices(self, district_name: str, commodity_key: str) -> dict:
        if not self.api_key:
            raise UpstreamError("market prices not configured")
        commodity = COMMODITIES[commodity_key]

        async def fetch() -> dict:
            params = {
                "api-key": self.api_key,
                "format": "json",
                "limit": "100",
                "filters[state]": "Odisha",
                "filters[commodity]": commodity,
            }
            data = await self._get_json(AGMARKNET_URL, params)
            records = data.get("records")
            if not isinstance(records, list):
                raise UpstreamError("unexpected market response")
            rows = [_market_row(r) for r in records if isinstance(r, dict)]
            rows = [r for r in rows if r is not None]
            local = [r for r in rows if r["district"].lower() == district_name.lower()]
            return {
                "commodity": commodity,
                "district_markets": local,
                "state_markets": rows[:25],
                "source": "Agmarknet via data.gov.in (Government Open Data License - India)",
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

        return await self.cache.get_or_fetch(("market", commodity_key), self.market_ttl, fetch)

    async def _get_json(self, url: str, params: dict[str, str]) -> dict:
        try:
            resp = await self.client.get(url, params=params)
        except httpx.HTTPError as exc:
            log.warning("upstream request failed: %s", type(exc).__name__)
            raise UpstreamError("upstream unavailable") from exc
        if resp.status_code != 200:
            log.warning("upstream %s returned HTTP %s", url.split("/")[2], resp.status_code)
            raise UpstreamError("upstream error")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("invalid upstream JSON") from exc
        if not isinstance(data, dict):
            raise UpstreamError("invalid upstream payload")
        return data


def _pick(daily: dict, key: str, i: int):
    values = daily.get(key) or []
    return values[i] if i < len(values) else None


def _market_row(r: dict) -> dict | None:
    try:
        return {
            "market": str(r.get("market", "")).strip(),
            "district": str(r.get("district", "")).strip(),
            "variety": str(r.get("variety", "")).strip(),
            "arrival_date": str(r.get("arrival_date", "")).strip(),
            "min_price": float(r["min_price"]),
            "max_price": float(r["max_price"]),
            "modal_price": float(r["modal_price"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def make_client(timeout: float, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=False,
        transport=transport,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
