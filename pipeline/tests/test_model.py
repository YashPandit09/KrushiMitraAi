from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipeline import model


def test_trend_recovers_slope_and_resists_outliers():
    years = np.arange(2000, 2020)
    values = 1.0 + 0.05 * (years - 2000)
    values[5] = 0.1  # a disaster year must not drag the trend down much
    t = model.fit_trend(years, values)
    assert t.slope == pytest.approx(0.05, abs=0.005)
    assert t.at(2020) == pytest.approx(2.0, abs=0.05)


def test_trend_window_and_short_history():
    years = np.arange(2000, 2020)
    values = np.where(years < 2010, 1.0, 1.0 + 0.1 * (years - 2010))
    assert model.fit_trend(years, values, window=10).slope == pytest.approx(0.1, abs=0.01)
    short = model.fit_trend(np.array([2000, 2001]), np.array([1.0, 3.0]))
    assert short.slope == 0.0


def test_conformal_quantile_finite_sample_correction():
    scores = np.arange(1, 11) / 10  # 0.1 .. 1.0
    # ceil((10 + 1) * 0.8) = 9 -> 9th smallest
    assert model.conformal_quantile(scores, 0.8) == pytest.approx(0.9)
    assert model.conformal_quantile(scores, 0.95) == pytest.approx(1.0)  # capped at the max
    assert np.isnan(model.conformal_quantile(np.array([]), 0.9))


def _synthetic(n_years=14, districts=("a", "b", "c")):
    rng = np.random.default_rng(0)
    rows, feats = [], []
    for d in districts:
        for y in range(1998, 1998 + n_years):
            x = rng.normal()
            trend = 1 + 0.03 * (y - 1998)
            rows.append({"district_slug": d, "year": y, "yield_t_ha": trend * (1 + 0.2 * x), "qc_flag": ""})
            feats.append({"district_slug": d, "year": y, "prcp_anom_season": x})
    target = pd.DataFrame(rows)
    X = pd.DataFrame(feats).set_index(["district_slug", "year"])
    return target, X


def test_backtest_never_trains_on_the_season_it_forecasts(monkeypatch):
    target, X = _synthetic()
    seen: list[tuple[int, int]] = []
    original = model.training_frame

    def spy(target_, features_, trends_, before_year):
        frame = original(target_, features_, trends_, before_year)
        seen.append((before_year, int(frame["year"].max())))
        return frame

    monkeypatch.setattr(model, "training_frame", spy)
    monkeypatch.setattr(model.config, "FIRST_BACKTEST_YEAR", 2005)
    bt = model.backtest(target, {"Oct": X}, model.ModelConfig("ridge", "compact", None))
    assert seen and all(max_train < test_year for test_year, max_train in seen)
    assert sorted(bt["year"].unique()) == list(range(2005, 2012))


def test_weather_signal_is_learned_out_of_sample(monkeypatch):
    target, X = _synthetic(n_years=20)
    monkeypatch.setattr(model.config, "FIRST_BACKTEST_YEAR", 2008)
    trend_bt = model.backtest(target, {"Oct": X}, model.ModelConfig("trend", "none", None))
    ridge_bt = model.backtest(target, {"Oct": X}, model.ModelConfig("ridge", "compact", None))
    rmse = lambda bt: float(np.sqrt(np.mean((bt["forecast"] - bt["actual"]) ** 2)))  # noqa: E731
    assert rmse(ridge_bt) < 0.75 * rmse(trend_bt)


def test_intervals_use_only_past_seasons():
    rows = []
    for year in range(2000, 2016):
        err = 0.1 if year < 2015 else 5.0  # a huge miss in 2015 must not widen 2015's own interval
        rows.append({"lead": "Oct", "year": year, "actual": 1.0 + err, "forecast": 1.0, "district_slug": "a"})
    bt = model.add_intervals(pd.DataFrame(rows), levels=(0.8,), window=10)
    last = bt[bt["year"] == 2015].iloc[0]
    assert last["hi80"] == pytest.approx(1.1)
    assert np.isnan(bt[bt["year"] == 2001].iloc[0]["hi80"])  # not enough history yet


def test_score_reports_skill_against_reference():
    s = model.score(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), reference=np.array([2.0, 2.0, 2.0]))
    assert s["rmse"] == 0 and s["skill_vs_trend"] == 1.0
