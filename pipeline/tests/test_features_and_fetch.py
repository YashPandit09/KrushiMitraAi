from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipeline import features, fetch
from pipeline.geo import centroid, haversine_km


def test_longest_dry_run():
    assert features._longest_run(np.array([True, True, False, True, True, True, False])) == 3
    assert features._longest_run(np.array([], dtype=bool)) == 0


def test_monthly_table_marks_incomplete_months():
    idx = pd.date_range("2026-09-01", "2026-10-21", freq="D")
    df = pd.DataFrame({c: 1.0 for c in ["prcp", "tmax", "tmin", "srad", "gwet", "rh"]}, index=idx)
    df.loc["2026-09-10", "prcp"] = 70.0
    m = features.monthly_table(df)
    assert bool(m.loc[(2026, 9), "complete"]) is True
    assert bool(m.loc[(2026, 10), "complete"]) is False
    assert m.loc[(2026, 9), "heavy_days"] == 1


def test_cyclone_features_respect_distance_and_time(monkeypatch):
    tracks = pd.DataFrame(
        {
            "SID": ["X", "X", "Y"],
            "NAME": ["PHAILIN", "PHAILIN", "FAR"],
            "time": pd.to_datetime(["2013-10-12 12:00", "2013-10-13 00:00", "2013-10-12 12:00"]),
            "LAT": [19.3, 20.0, 15.0],
            "LON": [84.9, 84.5, 90.0],
            "wind_kt": [115.0, 60.0, 140.0],
        }
    )
    monkeypatch.setattr(features, "cyclone_tracks", lambda: tracks)
    near = features.cyclone_features(84.7, 19.6, pd.Timestamp("2013-05-01"), pd.Timestamp("2013-10-31"))
    assert near["cyclone_wind_kt"] == 115.0
    assert 0 < near["cyclone_exposure"] <= 115.0
    before = features.cyclone_features(84.7, 19.6, pd.Timestamp("2013-05-01"), pd.Timestamp("2013-09-30"))
    assert before == {"cyclone_wind_kt": 0.0, "cyclone_exposure": 0.0}
    events = features.cyclone_events(84.7, 19.6, pd.Timestamp("2013-05-01"), pd.Timestamp("2013-10-31"))
    assert [e["name"] for e in events] == ["Phailin"]


def test_feature_descriptions_are_human_readable():
    assert features.describe("prcp_anom_Sep")["label"] == "September rainfall vs normal"
    assert features.describe("cyclone_wind_kt")["unit"] == "kt"
    assert features.describe("unknown_thing")["label"] == "unknown_thing"


def test_centroid_and_distance():
    square = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}
    assert centroid(square) == pytest.approx((1.0, 1.0))
    assert haversine_km(85.0, 20.0, 85.0, 21.0) == pytest.approx(111.2, abs=0.5)


def _series(days, value):
    return {d.strftime("%Y%m%d"): value for d in days}


def test_precipitation_scale_detects_the_24x_bug():
    days = pd.date_range("2025-06-01", "2025-12-31", freq="D")
    history = _series(days, 5.0)
    assert fetch.precipitation_scale(history, _series(days, 120.0), days[0].date(), days[-1].date()) == 24.0
    assert fetch.precipitation_scale(history, _series(days, 5.0), days[0].date(), days[-1].date()) == 1.0
    with pytest.raises(RuntimeError):
        fetch.precipitation_scale(history, _series(days, 50.0), days[0].date(), days[-1].date())


def test_validate_power_rejects_implausible_rainfall():
    year = pd.date_range("2020-01-01", "2020-12-31", freq="D")
    ok = {"PRECTOTCORR": _series(year, 4.0)}  # ~1460 mm/yr
    fetch.validate_power("x", ok)
    with pytest.raises(RuntimeError):
        fetch.validate_power("x", {"PRECTOTCORR": _series(year, 96.0)})  # 24x too large
