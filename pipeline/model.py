"""Yield = district trend x (1 + weather-driven anomaly).

* The trend captures technology and management gains (Odisha's Kharif rice yields roughly
  doubled between 1998 and 2024). It is fitted per district with a robust (Huber) regression.
* The anomaly model explains the year-to-year deviation from trend using weather and cyclone
  features. It is pooled across districts so that it learns from all 30 at once.
* Every evaluated forecast is made "rolling-origin": the model for season t is trained only on
  seasons before t, exactly as it would have been run in real time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .features import feature_columns

MIN_TREND_YEARS = 5
ANOMALY_CLIP = 0.6  # training anomalies are winsorised to +/- 60 % to limit leverage of errors


# --------------------------------------------------------------------------------------
# Trend
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Trend:
    intercept: float
    slope: float
    center: float

    def at(self, year: float) -> float:
        return self.intercept + self.slope * (year - self.center)


def fit_trend(years: np.ndarray, values: np.ndarray, window: int | None = None) -> Trend:
    order = np.argsort(years)
    years, values = np.asarray(years, float)[order], np.asarray(values, float)[order]
    if window is not None:
        years, values = years[-window:], values[-window:]
    center = float(years.mean())
    if len(years) < MIN_TREND_YEARS:
        return Trend(float(np.median(values)), 0.0, center)
    model = HuberRegressor(epsilon=1.35, alpha=0.0, max_iter=500).fit((years - center).reshape(-1, 1), values)
    return Trend(float(model.intercept_), float(model.coef_[0]), center)


# --------------------------------------------------------------------------------------
# Anomaly models
# --------------------------------------------------------------------------------------
class NoAnomaly:
    """Trend only."""

    name = "trend"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> NoAnomaly:
        self.columns_ = list(X.columns)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X))

    def contributions(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return np.zeros((len(X), X.shape[1])), np.zeros(len(X))


class RidgeAnomaly:
    name = "ridge"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> RidgeAnomaly:
        self.columns_ = list(X.columns)
        self.pipe_ = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3.5, 30))
        )
        self.pipe_.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.pipe_.predict(X[self.columns_])

    def contributions(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        imputer, scaler, ridge = self.pipe_.steps[0][1], self.pipe_.steps[1][1], self.pipe_.steps[2][1]
        z = scaler.transform(imputer.transform(X[self.columns_]))
        contrib = z * ridge.coef_
        return contrib, np.full(len(X), ridge.intercept_)


class LGBMAnomaly:
    name = "lgbm"

    PARAMS = dict(
        objective="huber",
        alpha=0.2,
        n_estimators=300,
        learning_rate=0.03,
        num_leaves=8,
        min_child_samples=25,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.7,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=1,
        deterministic=True,
        force_col_wise=True,
        verbose=-1,
    )

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> LGBMAnomaly:
        self.columns_ = list(X.columns)
        self.model_ = lgb.LGBMRegressor(**self.PARAMS).fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model_.predict(X[self.columns_])

    def contributions(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        out = self.model_.predict(X[self.columns_], pred_contrib=True)  # TreeSHAP values + bias column
        return out[:, :-1], out[:, -1]


MODELS = {"trend": NoAnomaly, "ridge": RidgeAnomaly, "lgbm": LGBMAnomaly}


@dataclass(frozen=True)
class ModelConfig:
    model: str  # key of MODELS
    features: str  # "compact" | "monthly" | "none" (trend only)
    trend_window: int | None  # None = all available years

    @property
    def key(self) -> str:
        return f"{self.model}|{self.features}|w={self.trend_window or 'all'}"


TREND_ONLY = "trend"
CANDIDATES = tuple(
    [ModelConfig(TREND_ONLY, "none", w) for w in (None, 15)]
    + [ModelConfig(m, f, w) for m in ("ridge", "lgbm") for f in ("compact", "monthly") for w in (None, 15)]
)
REFERENCE = ModelConfig(TREND_ONLY, "none", None)  # skill is always measured against this

# The deployed system picks, separately for each lead time and each season, the member of a small
# pool with the lowest error over the previous SELECTION_WINDOW seasons - exactly what a forecaster
# could have done in real time. The pool uses all available years for the trend.
ENSEMBLE = ModelConfig("ensemble", "compact", None)
ENSEMBLE_MEMBERS = (REFERENCE, ModelConfig("ridge", "compact", None), ModelConfig("lgbm", "compact", None))
SELECTION_POOL = (*ENSEMBLE_MEMBERS, ENSEMBLE)
SELECTION_WINDOW = 8


# --------------------------------------------------------------------------------------
# Fitting one season
# --------------------------------------------------------------------------------------
def fit_trends(target: pd.DataFrame, before_year: int, window: int | None) -> dict[str, Trend]:
    hist = target[target["year"] < before_year]
    return {
        slug: fit_trend(g["year"].to_numpy(), g["yield_t_ha"].to_numpy(), window)
        for slug, g in hist.groupby("district_slug")
    }


def training_frame(target: pd.DataFrame, features: pd.DataFrame, trends: dict[str, Trend], before_year: int):
    hist = target[target["year"] < before_year].copy()
    hist["trend"] = [trends[s].at(y) for s, y in zip(hist["district_slug"], hist["year"], strict=True)]
    hist["anomaly"] = (hist["yield_t_ha"] / hist["trend"] - 1.0).clip(-ANOMALY_CLIP, ANOMALY_CLIP)
    return hist.join(features, on=["district_slug", "year"], how="inner")


def fit_season(target: pd.DataFrame, features: pd.DataFrame, cfg: ModelConfig, before_year: int):
    """Fit trends + anomaly model on all seasons strictly before ``before_year``."""
    trends = fit_trends(target, before_year, cfg.trend_window)
    train = training_frame(target, features, trends, before_year)
    cols = feature_columns(list(features.columns), "compact" if cfg.features == "none" else cfg.features)
    model = MODELS[cfg.model]().fit(train[cols], train["anomaly"].to_numpy())
    return trends, model, cols


def predict_season(trends, model, cols, features: pd.DataFrame, year: int) -> pd.DataFrame:
    rows = features.xs(year, level="year", drop_level=False).reset_index()
    rows = rows[rows["district_slug"].isin(trends)]
    rows["trend"] = [trends[s].at(year) for s in rows["district_slug"]]
    rows["anomaly_pred"] = model.predict(rows[cols])
    rows["forecast"] = rows["trend"] * (1.0 + rows["anomaly_pred"])
    return rows


# --------------------------------------------------------------------------------------
# Rolling-origin backtest + baselines
# --------------------------------------------------------------------------------------
def backtest(target: pd.DataFrame, features_by_lead: dict[str, pd.DataFrame], cfg: ModelConfig) -> pd.DataFrame:
    last_year = int(target["year"].max())
    out = []
    for lead, feats in features_by_lead.items():
        for year in range(config.FIRST_BACKTEST_YEAR, last_year + 1):
            trends, model, cols = fit_season(target, feats, cfg, year)
            pred = predict_season(trends, model, cols, feats, year)
            pred["lead"] = lead
            out.append(pred[["district_slug", "year", "lead", "trend", "anomaly_pred", "forecast"]])
    bt = pd.concat(out, ignore_index=True)
    actual = target[["district_slug", "year", "yield_t_ha", "qc_flag"]].rename(columns={"yield_t_ha": "actual"})
    bt = bt.merge(actual, on=["district_slug", "year"], how="inner")
    bt["config"] = cfg.key
    return bt


def combine(backtests: list[pd.DataFrame], key: str) -> pd.DataFrame:
    """Equal-weight average of member backtests (they share the same trend fit)."""
    keys = ["district_slug", "year", "lead"]
    base = backtests[0][[*keys, "trend", "actual", "qc_flag"]].copy()
    stacked = pd.concat([b[[*keys, "anomaly_pred", "forecast"]] for b in backtests])
    mean = stacked.groupby(keys, as_index=False)[["anomaly_pred", "forecast"]].mean()
    out = base.merge(mean, on=keys, how="inner")
    out["config"] = key
    return out


def season_errors(backtests: dict[str, pd.DataFrame], pool: list[str]) -> dict[str, pd.Series]:
    """Mean squared out-of-sample error per (lead, season) for each pool member."""
    return {
        k: backtests[k]
        .assign(se=(backtests[k]["forecast"] - backtests[k]["actual"]) ** 2)
        .groupby(["lead", "year"])["se"]
        .mean()
        for k in pool
    }


def online_selection(backtests: dict[str, pd.DataFrame], pool: list[str], window: int = SELECTION_WINDOW):
    """For every lead and season, use the pool member with the lowest mean squared error over the
    previous ``window`` seasons (out-of-sample errors only). Returns the selected forecasts."""
    keys = ["district_slug", "year", "lead"]
    errors = season_errors(backtests, pool)
    rows = []
    first = config.FIRST_BACKTEST_YEAR + window
    for lead in backtests[pool[0]]["lead"].unique():
        years = sorted(backtests[pool[0]].loc[backtests[pool[0]]["lead"] == lead, "year"].unique())
        for year in (y for y in years if y >= first):
            chosen = choose(errors, pool, lead, year, window)
            sel = backtests[chosen]
            rows.append(sel[(sel["lead"] == lead) & (sel["year"] == year)].assign(config=chosen))
    out = pd.concat(rows, ignore_index=True)
    return out[[*keys, "trend", "anomaly_pred", "forecast", "actual", "qc_flag", "config"]]


def choose(errors: dict[str, pd.Series], pool: list[str], lead: str, year: int, window: int) -> str:
    """Pool member with the lowest mean error over seasons [year - window, year - 1]."""

    def trailing(k: str) -> float:
        s = errors[k].loc[lead]
        return float(s[(s.index < year) & (s.index >= year - window)].mean())

    return min(pool, key=trailing)


def baselines(target: pd.DataFrame) -> pd.DataFrame:
    """Persistence (last season) and 5-season mean, for every district-year."""
    rows = []
    for slug, g in target.groupby("district_slug"):
        s = g.set_index("year")["yield_t_ha"].sort_index()
        for year in s.index:
            prev = s[s.index < year]
            rows.append(
                {
                    "district_slug": slug,
                    "year": year,
                    "persistence": prev.iloc[-1] if len(prev) else np.nan,
                    "mean5": prev.iloc[-5:].mean() if len(prev) >= 3 else np.nan,
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Conformal prediction intervals
# --------------------------------------------------------------------------------------
def conformal_quantile(scores: np.ndarray, level: float) -> float:
    """Split-conformal quantile with the finite-sample correction ceil((n+1) * level) / n."""
    scores = np.sort(np.asarray(scores, float))
    n = len(scores)
    if n == 0:
        return math.nan
    k = min(n, math.ceil((n + 1) * level))
    return float(scores[k - 1])


def add_intervals(bt: pd.DataFrame, levels=config.INTERVAL_LEVELS, window: int = config.CALIBRATION_YEARS):
    """Relative intervals forecast x (1 +/- q), calibrated on the previous ``window`` seasons'
    out-of-sample errors for the same lead time. No information from the target season is used."""
    bt = bt.sort_values(["lead", "year"]).copy()
    bt["rel_error"] = (bt["actual"] / bt["forecast"] - 1.0).abs()
    for level in levels:
        tag = int(round(level * 100))
        bt[f"lo{tag}"] = np.nan
        bt[f"hi{tag}"] = np.nan
    for _lead, g in bt.groupby("lead"):
        for year in g["year"].unique():
            cal = g[(g["year"] < year) & (g["year"] >= year - window)]
            if cal["year"].nunique() < 3:
                continue
            idx = g.index[g["year"] == year]
            for level in levels:
                tag = int(round(level * 100))
                q = conformal_quantile(cal["rel_error"].dropna().to_numpy(), level)
                bt.loc[idx, f"lo{tag}"] = (bt.loc[idx, "forecast"] * (1 - q)).clip(lower=0)
                bt.loc[idx, f"hi{tag}"] = bt.loc[idx, "forecast"] * (1 + q)
    return bt.drop(columns="rel_error")


def interval_for(bt: pd.DataFrame, lead: str, level: float, window: int = config.CALIBRATION_YEARS) -> float:
    """Relative half-width for a *new* season, from the latest ``window`` backtest seasons."""
    g = bt[bt["lead"] == lead]
    last = int(g["year"].max())
    cal = g[g["year"] > last - window]
    return conformal_quantile((cal["actual"] / cal["forecast"] - 1.0).abs().dropna().to_numpy(), level)


# --------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------
def score(actual: np.ndarray, pred: np.ndarray, reference: np.ndarray | None = None) -> dict[str, float]:
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    ok = ~(np.isnan(a) | np.isnan(p))
    a, p = a[ok], p[ok]
    err = p - a
    out = {
        "n": int(ok.sum()),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae": float(np.mean(np.abs(err))),
        "mape": float(np.mean(np.abs(err) / a) * 100),
        "bias": float(np.mean(err)),
        "r2": float(1 - np.sum(err**2) / np.sum((a - a.mean()) ** 2)),
    }
    if reference is not None:
        r = np.asarray(reference, float)[ok]
        out["skill_vs_trend"] = float(1 - np.sum(err**2) / np.sum((r - a) ** 2))
    return out
