from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["data_generated_at"]


def test_meta_lists_forecast_years_and_disables_markets_by_default(client):
    meta = client.get("/api/meta").json()
    assert meta["features"] == {"market_prices": False, "live_weather": True}
    assert meta["leads"] == ["Jul", "Aug", "Sep", "Oct", "Nov"]
    assert meta["forecast_years"], "pipeline should produce at least one forward-looking season"
    for leads in meta["forecast_years"].values():
        assert set(leads) <= set(meta["leads"])


def test_districts_and_geojson(client):
    districts = client.get("/api/districts").json()
    assert len(districts) == 30
    assert len({d["slug"] for d in districts}) == 30
    r = client.get("/api/districts/geojson")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    assert len(r.json()["features"]) == 30
    cached = client.get("/api/districts/geojson", headers={"If-None-Match": r.headers["etag"]})
    assert cached.status_code == 304


def test_district_detail(client):
    d = client.get("/api/districts/cuttack").json()
    assert d["name"] == "Cuttack"
    years = [row["year"] for row in d["kharif_rice"]]
    assert years == sorted(years) and min(years) <= 2000
    assert "Rice" in d["crops"]


def test_unknown_and_malformed_district(client):
    assert client.get("/api/districts/atlantis").status_code == 404
    assert client.get("/api/districts/CUT1").status_code == 422
    assert client.get("/api/districts/a" * 30).status_code in (404, 422)


def test_yields_explorer(client):
    r = client.get("/api/districts/cuttack/yields", params={"crop": "Rice", "season": "Winter"})
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and all(row["season"] == "Winter" for row in rows)
    assert client.get("/api/districts/cuttack/yields", params={"crop": "Unobtainium"}).status_code == 404


def test_forecast_map_and_intervals(client):
    meta = client.get("/api/meta").json()
    year, leads = next(iter(meta["forecast_years"].items()))
    r = client.get("/api/forecasts", params={"year": year, "lead": leads[-1]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["districts"]) >= 25
    for row in body["districts"]:
        assert row["lo90"] <= row["lo80"] <= row["forecast_t_ha"] <= row["hi80"] <= row["hi90"]
        assert "drivers" not in row
    assert body["state"]["lo90"] <= body["state"]["forecast_t_ha"] <= body["state"]["hi90"]


def test_forecast_validation(client):
    assert client.get("/api/forecasts", params={"year": 2026, "lead": "Dec"}).status_code == 422
    assert client.get("/api/forecasts", params={"year": 1800, "lead": "Oct"}).status_code == 422
    assert client.get("/api/forecasts", params={"year": 2090, "lead": "Oct"}).status_code == 404


def test_district_forecasts_include_drivers(client):
    body = client.get("/api/forecasts/cuttack").json()
    assert body["forecasts"]
    first = body["forecasts"][0]
    assert {"forecast_t_ha", "trend_t_ha", "drivers", "cyclones", "issued_after"} <= set(first)


def test_backtest_is_out_of_sample_series(client):
    rows = client.get("/api/backtest/cuttack", params={"lead": "Oct"}).json()["rows"]
    assert rows
    assert min(r["year"] for r in rows) >= 2003
    assert all(r["actual"] is not None and r["forecast"] is not None for r in rows)


def test_model_card(client):
    card = client.get("/api/model-card").json()
    assert card["chosen"]["key"] == "online-selection"
    pool = set(card["chosen"]["pool"])
    assert pool and pool == {c["key"] for c in card["candidates"] if c["in_selection_pool"]}
    assert card["protocol"]["evaluation"].startswith("rolling-origin")
    assert "disclosure" in card["protocol"]
    assert set(card["chosen"]["coverage"]) == {"Jul", "Aug", "Sep", "Oct", "Nov"}
    assert set(card["chosen"]["current_choice"].values()) <= pool


def test_season_weather(client):
    body = client.get("/api/districts/puri/weather", params={"year": 2019}).json()
    assert [m["month"] for m in body["months"]] == [6, 7, 8, 9, 10, 11]
    assert all(m["prcp"] is not None and m["prcp_normal"] for m in body["months"])


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "Not found"}
    assert client.post("/api/health").status_code in (404, 405)
