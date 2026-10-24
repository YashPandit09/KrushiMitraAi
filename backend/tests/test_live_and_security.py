from __future__ import annotations

SECRET = "fake-test-value-not-a-real-key"  # noqa: S105  gitleaks:allow


def test_security_headers_on_api(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "cdn.jsdelivr.net" not in csp
    assert "strict-transport-security" not in r.headers  # only sent over HTTPS


def test_docs_get_their_own_csp(client):
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert "cdn.jsdelivr.net" in r.headers["content-security-policy"]


def test_hsts_over_https(client):
    r = client.get("https://testserver/api/health")
    assert r.headers["strict-transport-security"].startswith("max-age=")


def test_live_weather_is_cached(client, upstream):
    first = client.get("/api/live/weather/cuttack")
    assert first.status_code == 200
    assert first.json()["days"][0] == {
        "date": "2026-10-24",
        "rain_mm": 1.2,
        "rain_probability_pct": 40,
        "tmax_c": 31.0,
        "tmin_c": 22.0,
        "wind_max_kmh": 12.0,
    }
    client.get("/api/live/weather/cuttack")
    assert len(upstream.calls) == 1, "second request must be served from cache"
    assert upstream.calls[0].url.params["latitude"] and upstream.calls[0].url.params["timezone"] == "Asia/Kolkata"


def test_live_weather_upstream_failure_is_502(client, upstream):
    upstream.fail = True
    r = client.get("/api/live/weather/puri")
    assert r.status_code == 502
    assert "unavailable" in r.json()["detail"]


def test_live_rate_limit(client_factory):
    with client_factory(live_rate_limit_per_minute=2) as c:
        assert c.get("/api/live/weather/cuttack").status_code == 200
        assert c.get("/api/live/weather/cuttack").status_code == 200
        r = c.get("/api/live/weather/cuttack")
        assert r.status_code == 429
        assert int(r.headers["retry-after"]) >= 1


def test_market_prices_disabled_without_key(client, upstream):
    assert client.get("/api/live/market-prices/cuttack").status_code == 503
    assert not upstream.calls


def test_market_prices_with_key_never_leaks_it(client_factory, upstream):
    with client_factory(data_gov_in_api_key=SECRET) as c:
        assert c.get("/api/meta").json()["features"]["market_prices"] is True
        r = c.get("/api/live/market-prices/cuttack", params={"commodity": "paddy"})
        assert r.status_code == 200
        body = r.json()
        assert body["district_markets"][0]["modal_price"] == 2200.0
        assert len(body["state_markets"]) == 1  # the malformed record is dropped
        assert SECRET not in r.text
        assert upstream.calls[0].url.params["api-key"] == SECRET  # sent upstream only
        assert c.get("/api/live/market-prices/cuttack", params={"commodity": "uranium"}).status_code == 404
        assert c.get("/api/live/market-prices/cuttack", params={"commodity": "Paddy!"}).status_code == 422


def test_cors_is_off_by_default_and_configurable(client_factory):
    with client_factory() as c:
        r = c.get("/api/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers
    with client_factory(cors_origins="https://ok.example, https://also.example") as c:
        r = c.get("/api/health", headers={"Origin": "https://ok.example"})
        assert r.headers["access-control-allow-origin"] == "https://ok.example"


def test_spa_serving_and_path_traversal(client_factory, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>KrushiMitra</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    with client_factory(frontend_dist=dist) as c:
        assert "KrushiMitra" in c.get("/").text
        assert "KrushiMitra" in c.get("/district/cuttack").text  # client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/robots.txt").text == "User-agent: *"
        assert "top secret" not in c.get("/..%2Fsecret.txt").text
        assert c.get("/api/nope").status_code == 404  # API 404s are not swallowed by the SPA
