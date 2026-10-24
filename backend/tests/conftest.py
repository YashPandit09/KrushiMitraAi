from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app

WEATHER_JSON = {
    "daily": {
        "time": ["2026-10-24", "2026-10-25"],
        "precipitation_sum": [1.2, 0.0],
        "precipitation_probability_max": [40, 10],
        "temperature_2m_max": [31.0, 30.5],
        "temperature_2m_min": [22.0, 21.8],
        "wind_speed_10m_max": [12.0, 10.0],
    }
}
MARKET_JSON = {
    "records": [
        {
            "state": "Odisha",
            "district": "Cuttack",
            "market": "Cuttack",
            "commodity": "Paddy(Dhan)(Common)",
            "variety": "Common",
            "arrival_date": "24/10/2026",
            "min_price": "2100",
            "max_price": "2300",
            "modal_price": "2200",
        },
        {"state": "Odisha", "district": "Puri", "market": "Nimapara", "modal_price": "not-a-number"},
    ]
}


class Upstream:
    """Records outbound calls and returns canned responses."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.fail = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.fail:
            return httpx.Response(503, json={"error": "down"})
        if request.url.host == "api.open-meteo.com":
            return httpx.Response(200, json=WEATHER_JSON)
        if request.url.host == "api.data.gov.in":
            return httpx.Response(200, json=MARKET_JSON)
        return httpx.Response(404)


@pytest.fixture
def upstream() -> Upstream:
    return Upstream()


@pytest.fixture
def client_factory(upstream: Upstream, tmp_path) -> Callable:
    @contextmanager
    def make(**overrides) -> Iterator[TestClient]:
        overrides.setdefault("frontend_dist", tmp_path / "no-frontend")
        settings = Settings(_env_file=None, **overrides)
        app = create_app(settings, transport=httpx.MockTransport(upstream))
        with TestClient(app) as client:
            yield client

    return make


@pytest.fixture
def client(client_factory) -> Iterator[TestClient]:
    with client_factory() as c:
        yield c
