"""Backtest every candidate, run online model selection, report honestly, forecast the current season.

See PROTOCOL_HISTORY below for why the deployed system uses online selection (disclosed in the model card).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from . import config, features, geo, harmonize, report
from .model import (
    CANDIDATES,
    ENSEMBLE,
    ENSEMBLE_MEMBERS,
    REFERENCE,
    SELECTION_POOL,
    SELECTION_WINDOW,
    ModelConfig,
    add_intervals,
    backtest,
    baselines,
    choose,
    combine,
    conformal_quantile,
    fit_season,
    interval_for,
    online_selection,
    predict_season,
    score,
    season_errors,
)

log = logging.getLogger(__name__)
PROTOCOL_HISTORY = (
    "The first protocol picked a single model on a fixed validation period (2006-2014). On the test period "
    "(2015-2024) that choice lost to the plain trend. The deployed system therefore uses online selection: for "
    "each lead time and season it uses whichever pool member had the lowest error over the previous eight seasons "
    "- something a forecaster could have done in real time. Because this change was made after seeing the first "
    "test results, the test-period numbers of the online system are not fully independent; both protocols are "
    "reported side by side."
)
KEYS = ["district_slug", "year", "lead"]
ALL_CONFIGS = {c.key: c for c in (*CANDIDATES, ENSEMBLE)}


# --------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------
def build_inputs(today: date | None = None):
    today = today or date.today()
    geo.write_district_files()
    des = harmonize.load_des(config.RAW / "apy" / "apy_des.csv")
    upag = harmonize.load_upag(config.RAW / "apy" / "apy_upag.csv")
    explorer = harmonize.build_explorer_table(des, upag)
    target = harmonize.build_kharif_rice(des, upag, geo.nearest_neighbours(5))
    years = range(int(target["year"].min()), today.year + 1)
    feats = {lead: features.feature_table(lead, years) for lead in config.LEAD_MONTHS}
    return explorer, target, feats


# --------------------------------------------------------------------------------------
# Evaluation helpers
# --------------------------------------------------------------------------------------
def _scores(bt: pd.DataFrame, years, pred_col: str = "forecast") -> dict[str, float]:
    sub = bt[bt["year"].isin(years)]
    return score(sub["actual"], sub[pred_col], reference=sub["trend_ref"])


def state_level(bt: pd.DataFrame, target: pd.DataFrame, pred_col: str = "forecast") -> pd.DataFrame:
    """Area-weighted Odisha-wide yield per season and lead.

    Actual = total production / total area of the season. Forecasts are weighted by the previous
    season's district areas - the latest areas known when the forecast is made.
    """
    area = target.pivot(index="year", columns="district_slug", values="area_ha").sort_index().ffill()
    prev_area = area.shift(1)
    actual = target.groupby("year").apply(lambda g: g["production_t"].sum() / g["area_ha"].sum(), include_groups=False)
    rows = []
    for (year, lead), g in bt.groupby(["year", "lead"]):
        if year not in prev_area.index:
            continue
        w = prev_area.loc[year, g["district_slug"]].to_numpy()
        ok = ~np.isnan(w) & g[pred_col].notna().to_numpy()
        if ok.sum() < 25:  # a state figure needs (almost) every district
            continue
        rows.append(
            {
                "year": year,
                "lead": lead,
                "actual": float(actual.loc[year]),
                "forecast": float(np.average(g[pred_col].to_numpy()[ok], weights=w[ok])),
                "trend_ref": float(np.average(g["trend_ref"].to_numpy()[ok], weights=w[ok])),
            }
        )
    return pd.DataFrame(rows)


def summarize(key: str, bt: pd.DataFrame, target: pd.DataFrame) -> dict:
    state = state_level(bt, target)
    by_lead = {}
    for lead, g in bt.groupby("lead", sort=False):
        s = state[state["lead"] == lead]
        by_lead[lead] = {
            "validation": _scores(g, config.VALIDATION_YEARS),
            "test": _scores(g, config.TEST_YEARS),
            "state_validation": _scores(s, config.VALIDATION_YEARS),
            "state_test": _scores(s, config.TEST_YEARS),
        }
    cfg = ALL_CONFIGS.get(key)
    return {
        "key": key,
        "model": cfg.model if cfg else key,
        "features": cfg.features if cfg else "mixed",
        "trend_window": cfg.trend_window if cfg else None,
        "in_selection_pool": key in {c.key for c in SELECTION_POOL},
        "by_lead": by_lead,
        "validation_rmse_mean": float(np.mean([v["validation"]["rmse"] for v in by_lead.values()])),
        "test_rmse_mean": float(np.mean([v["test"]["rmse"] for v in by_lead.values()])),
    }


def coverage_report(bt: pd.DataFrame) -> dict:
    out = {}
    test = bt[bt["year"].isin(config.TEST_YEARS)]
    for lead, g in test.groupby("lead", sort=False):
        out[lead] = {}
        for level in config.INTERVAL_LEVELS:
            tag = int(round(level * 100))
            ok = g[[f"lo{tag}", f"hi{tag}"]].notna().all(axis=1)
            inside = (g.loc[ok, "actual"] >= g.loc[ok, f"lo{tag}"]) & (g.loc[ok, "actual"] <= g.loc[ok, f"hi{tag}"])
            width = ((g.loc[ok, f"hi{tag}"] - g.loc[ok, f"lo{tag}"]) / g.loc[ok, "forecast"]).mean()
            out[lead][str(tag)] = {"coverage": float(inside.mean()), "mean_width_pct": float(width * 100)}
    return out


# --------------------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------------------
def evaluate(target: pd.DataFrame, feats: dict[str, pd.DataFrame]):
    backtests: dict[str, pd.DataFrame] = {}
    for cfg in CANDIDATES:
        log.info("backtest %s", cfg.key)
        backtests[cfg.key] = backtest(target, feats, cfg)
    backtests[ENSEMBLE.key] = combine([backtests[m.key] for m in ENSEMBLE_MEMBERS], ENSEMBLE.key)

    ref = backtests[REFERENCE.key][[*KEYS, "forecast"]].rename(columns={"forecast": "trend_ref"})
    backtests = {k: bt.merge(ref, on=KEYS) for k, bt in backtests.items()}
    results = [summarize(k, bt, target) for k, bt in backtests.items()]

    pool = [c.key for c in SELECTION_POOL]
    meta = online_selection(backtests, pool).merge(ref, on=KEYS)

    base = baselines(target).merge(
        backtests[REFERENCE.key].query("lead == 'Oct'")[["district_slug", "year", "trend_ref", "actual"]],
        on=["district_slug", "year"],
    )
    baseline_scores = {
        name: {
            "validation": _scores(base, config.VALIDATION_YEARS, name),
            "test": _scores(base, config.TEST_YEARS, name),
        }
        for name in ("persistence", "mean5")
    }
    return results, backtests, meta, baseline_scores, base


def fixed_split_choice(results: list[dict]) -> str:
    """What the original protocol would deploy: lowest mean validation RMSE (pool members excluded)."""
    single = [r for r in results if r["key"] in {c.key for c in CANDIDATES}]
    return min(single, key=lambda r: r["validation_rmse_mean"])["key"]


# --------------------------------------------------------------------------------------
# Current-season forecasts
# --------------------------------------------------------------------------------------
class Fitted:
    """A pool member - or the equal-weight ensemble - fitted on every season before ``before_year``."""

    def __init__(self, target: pd.DataFrame, X: pd.DataFrame, cfg: ModelConfig, before_year: int) -> None:
        members = ENSEMBLE_MEMBERS if cfg == ENSEMBLE else (cfg,)
        self.parts = [fit_season(target, X, m, before_year) for m in members]
        self.trends, _, self.cols = self.parts[0]

    def predict(self, X: pd.DataFrame, year: int) -> pd.DataFrame:
        preds = [predict_season(t, m, c, X, year) for t, m, c in self.parts]
        out = preds[0].copy()
        out["anomaly_pred"] = np.mean([p["anomaly_pred"].to_numpy() for p in preds], axis=0)
        out["forecast"] = out["trend"] * (1.0 + out["anomaly_pred"])
        return out

    def contributions(self, rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        parts = [m.contributions(rows[c]) for _, m, c in self.parts]
        contrib = np.mean([p[0] for p in parts], axis=0)
        bias = np.mean([p[1] for p in parts], axis=0)
        return contrib, bias


def current_forecasts(target, feats, backtests, meta_bt) -> tuple[list[dict], dict, dict]:
    last_yield_year = int(target["year"].max())
    pool = [c.key for c in SELECTION_POOL]
    errors = season_errors(backtests, pool)
    forecasts, importance, choice = [], {}, {}
    for lead, X in feats.items():
        key = choose(errors, pool, lead, last_yield_year + 1, SELECTION_WINDOW)
        choice[lead] = key
        fitted = Fitted(target, X, ALL_CONFIGS[key], last_yield_year + 1)
        all_contrib, _ = fitted.contributions(X)
        ranked = sorted(zip(fitted.cols, np.abs(all_contrib).mean(axis=0), strict=True), key=lambda kv: -kv[1])
        importance[lead] = [
            {"feature": f, **features.describe(f), "mean_abs_anomaly_pct": round(float(v) * 100, 2)}
            for f, v in ranked
            if v > 0
        ][:12]
        q = {int(round(lv * 100)): interval_for(meta_bt, lead, lv) for lv in config.INTERVAL_LEVELS}
        future_years = sorted(y for y in X.index.get_level_values("year").unique() if y > last_yield_year)
        for year in future_years:
            pred = fitted.predict(X, year)
            contrib, bias = fitted.contributions(pred)
            end = pd.Timestamp(year, config.LEAD_MONTHS[lead], 1) + pd.offsets.MonthEnd(0)
            for i, row in enumerate(pred.itertuples(index=False)):
                drivers = []
                for j in np.argsort(-np.abs(contrib[i]))[:6]:
                    effect = float(contrib[i, j]) * row.trend
                    if abs(effect) >= 0.005:
                        f = fitted.cols[j]
                        value = round(float(getattr(row, f)), 3)
                        drivers.append(
                            {"feature": f, **features.describe(f), "value": value, "effect_t_ha": round(effect, 3)}
                        )
                lon, lat = geo.district_centroids()[row.district_slug]
                cyc_start = pd.Timestamp(year, config.CYCLONE_WINDOW_START_MONTH, 1)
                forecasts.append(
                    {
                        "district_slug": row.district_slug,
                        "year": int(year),
                        "lead": lead,
                        "model": key,
                        "issued_after": end.strftime("%Y-%m-%d"),
                        "forecast_t_ha": round(float(row.forecast), 3),
                        "trend_t_ha": round(float(row.trend), 3),
                        "anomaly_pct": round(float(row.anomaly_pred) * 100, 1),
                        "baseline_anomaly_pct": round(float(bias[i]) * 100, 1),
                        **{f"lo{t}": round(max(0.0, float(row.forecast) * (1 - qq)), 3) for t, qq in q.items()},
                        **{f"hi{t}": round(float(row.forecast) * (1 + qq), 3) for t, qq in q.items()},
                        "season_rain_anomaly_pct": round(float(row.prcp_anom_season) * 100, 1),
                        "cyclones": features.cyclone_events(lon, lat, cyc_start, end + pd.Timedelta(hours=23)),
                        "drivers": drivers,
                    }
                )
    return forecasts, importance, choice


def state_forecasts(forecasts: list[dict], target: pd.DataFrame, bt: pd.DataFrame) -> list[dict]:
    """Odisha-wide forecast per (season, lead) with its *own* conformal interval.

    District errors partly cancel in the aggregate, so the state interval is calibrated on the
    state-level backtest errors (previous 10 seasons, same lead) instead of averaging district
    bounds - averaging would overstate the state's uncertainty.
    """
    latest_area = target.sort_values("year").groupby("district_slug")["area_ha"].last()
    state_bt = state_level(bt, target)
    out = []
    fc = pd.DataFrame(forecasts)
    if fc.empty:
        return out
    for (year, lead), g in fc.groupby(["year", "lead"]):
        w = latest_area.reindex(g["district_slug"]).to_numpy()
        hist = state_bt[state_bt["lead"] == lead].sort_values("year").tail(config.CALIBRATION_YEARS)
        rel = (hist["actual"] / hist["forecast"] - 1.0).abs().to_numpy()
        point = float(np.average(g["forecast_t_ha"], weights=w))
        row = {
            "year": int(year),
            "lead": lead,
            "forecast_t_ha": round(point, 3),
            "trend_t_ha": round(float(np.average(g["trend_t_ha"], weights=w)), 3),
        }
        for level in config.INTERVAL_LEVELS:
            tag = int(round(level * 100))
            q = conformal_quantile(rel, level)
            row[f"lo{tag}"] = round(max(0.0, point * (1 - q)), 3)
            row[f"hi{tag}"] = round(point * (1 + q), 3)
        out.append(row)
    return out


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def run(today: date | None = None) -> dict:
    today = today or date.today()
    explorer, target, feats = build_inputs(today)
    results, backtests, meta, baseline_scores, base = evaluate(target, feats)

    bt = add_intervals(meta)
    bt = bt.merge(base[["district_slug", "year", "persistence", "mean5"]], on=["district_slug", "year"], how="left")
    forecasts, importance, choice = current_forecasts(target, feats, backtests, bt)
    state_fc = state_forecasts(forecasts, target, bt)
    log.info("current-season model per lead: %s", choice)

    test = bt[bt["year"].isin(config.TEST_YEARS)]
    clean = test[test["qc_flag"] == ""]
    state_bt = state_level(bt, target)
    fixed_key = fixed_split_choice(results)
    fixed = next(r for r in results if r["key"] == fixed_key)
    history = {
        lead: {str(int(y)): k for y, k in g.groupby("year")["config"].first().items()}
        for lead, g in bt.groupby("lead", sort=False)
    }
    chosen_report = {
        "key": "online-selection",
        "description": (
            f"For each lead time and season, the pool member with the lowest mean squared error over the "
            f"previous {SELECTION_WINDOW} seasons is used."
        ),
        "pool": [c.key for c in SELECTION_POOL],
        "window_seasons": SELECTION_WINDOW,
        "current_choice": choice,
        "selection_history": history,
        "coverage": coverage_report(bt),
        "test_by_lead": {
            lead: score(g["actual"], g["forecast"], g["trend_ref"]) for lead, g in test.groupby("lead", sort=False)
        },
        "state_test_by_lead": {lead: _scores(g, config.TEST_YEARS) for lead, g in state_bt.groupby("lead", sort=False)},
        "sensitivity_excluding_flagged_rows": {
            lead: score(g["actual"], g["forecast"], g["trend_ref"]) for lead, g in clean.groupby("lead", sort=False)
        },
        "test_rmse_by_district": {
            slug: round(score(g["actual"], g["forecast"])["rmse"], 4)
            for slug, g in test[test["lead"] == "Oct"].groupby("district_slug")
        },
        "feature_importance": importance,
        "fixed_split_protocol": {
            "would_have_chosen": fixed_key,
            "validation_rmse_mean": fixed["validation_rmse_mean"],
            "test_rmse_mean": fixed["test_rmse_mean"],
            "note": "Original protocol (single model chosen on 2006-2014). It lost to the trend baseline on "
            "2015-2024, which motivated the switch to online selection.",
        },
    }

    weather_last = min(features.last_complete_day(features.daily(d.slug)) for d in config.DISTRICTS)
    evaluation = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target": "Kharif (autumn + winter) rice yield, tonnes per hectare (milled-rice basis, as published by DES)",
        "data": {
            "districts": len(config.DISTRICTS),
            "first_season": int(target["year"].min()),
            "last_season_with_official_yield": int(target["year"].max()),
            "district_seasons": int(len(target)),
            "weather_through": weather_last.isoformat(),
            "flagged_rows": target[target["qc_flag"] != ""][["district_slug", "year", "yield_t_ha", "qc_flag"]].to_dict(
                orient="records"
            ),
        },
        "protocol": {
            "evaluation": "rolling-origin: the forecast for season t is trained only on seasons before t",
            "first_backtest_season": config.FIRST_BACKTEST_YEAR,
            "validation_seasons": list(config.VALIDATION_YEARS),
            "test_seasons": list(config.TEST_YEARS),
            "selection": chosen_report["description"],
            "intervals": "split conformal on the previous 10 seasons' relative errors of the deployed system, "
            "same lead time",
            "leads": {k: f"issued after the end of month {v}" for k, v in config.LEAD_MONTHS.items()},
            "disclosure": PROTOCOL_HISTORY,
        },
        "candidates": results,
        "baselines": baseline_scores,
        "chosen": chosen_report,
    }
    _write(explorer, target, bt, forecasts, state_fc, evaluation)
    return evaluation


def _write(explorer, target, bt, forecasts, state, evaluation) -> None:
    out = config.PROCESSED
    out.mkdir(parents=True, exist_ok=True)
    explorer.to_csv(out / "yields_odisha.csv", index=False)
    target.to_csv(out / "kharif_rice.csv", index=False)
    features.weather_monthly_export().to_csv(out / "weather_monthly.csv", index=False)
    cols = [
        "district_slug",
        "year",
        "lead",
        "config",
        "actual",
        "forecast",
        "trend",
        "lo80",
        "hi80",
        "lo90",
        "hi90",
        "persistence",
        "mean5",
        "qc_flag",
    ]
    bt[cols].round(4).sort_values(["district_slug", "lead", "year"]).to_csv(out / "backtest.csv", index=False)
    payload = {
        "generated_at": evaluation["generated_at"],
        "weather_through": evaluation["data"]["weather_through"],
        "last_season_with_official_yield": evaluation["data"]["last_season_with_official_yield"],
        "model": evaluation["chosen"]["key"],
        "model_by_lead": evaluation["chosen"]["current_choice"],
        "state": state,
        "forecasts": forecasts,
    }
    (out / "forecasts.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    (out / "evaluation.json").write_text(json.dumps(evaluation, indent=1, default=_json_default), encoding="utf-8")
    report.write(json.loads(json.dumps(evaluation, default=_json_default)))
    log.info("wrote processed artifacts to %s and docs/MODEL_CARD.md", out.relative_to(config.ROOT))


def _json_default(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    raise TypeError(type(obj))
