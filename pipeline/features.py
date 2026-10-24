"""Weather and cyclone features per district, Kharif season and forecast lead time.

A forecast "issued at the end of month L" may only use information available by then, so
every feature for lead L is computed from data up to the last day of month L.
"""

from __future__ import annotations

import calendar
import json
import logging
from datetime import date
from functools import cache, lru_cache

import numpy as np
import pandas as pd

from . import config
from .geo import district_centroids

log = logging.getLogger(__name__)

MONTH_ABBR = {m: calendar.month_abbr[m] for m in range(1, 13)}
MONTH_NAME = {m: calendar.month_name[m] for m in range(1, 13)}


# --------------------------------------------------------------------------------------
# Weather (NASA POWER, daily)
# --------------------------------------------------------------------------------------
def load_power(slug: str) -> pd.DataFrame:
    path = config.RAW / "power" / f"{slug}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    params = payload["properties"]["parameter"]
    df = pd.DataFrame({config.POWER_PARAMETERS[k]: pd.Series(v, dtype=float) for k, v in params.items()})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(-999.0, np.nan).sort_index()


@cache
def daily(slug: str) -> pd.DataFrame:
    return load_power(slug)


def last_complete_day(df: pd.DataFrame) -> date:
    """Last day on which the core variables (rain, temperature, soil wetness) are all present."""
    core = df[["prcp", "tmax", "tmin", "gwet"]].dropna()
    return core.index.max().date()


def monthly_table(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly aggregates; ``complete`` marks months with a full set of daily rain observations."""
    g = df.groupby([df.index.year, df.index.month])
    out = pd.DataFrame(
        {
            "prcp": g["prcp"].sum(min_count=1),
            "tmax": g["tmax"].mean(),
            "tmin": g["tmin"].mean(),
            "srad": g["srad"].mean(),
            "gwet": g["gwet"].mean(),
            "rh": g["rh"].mean(),
            "heavy_days": g["prcp"].apply(lambda s: int((s >= config.HEAVY_RAIN_MM).sum())),
            "wet_days": g["prcp"].apply(lambda s: int((s >= config.WET_DAY_MM).sum())),
            "n_days": g["prcp"].count(),
        }
    )
    out.index.names = ["year", "month"]
    days_in_month = [calendar.monthrange(y, m)[1] for y, m in out.index]
    out["complete"] = out["n_days"].to_numpy() == np.asarray(days_in_month)
    return out


def climatology(monthly: pd.DataFrame) -> pd.DataFrame:
    """1991-2020 monthly normals (WMO standard period)."""
    y0, y1 = config.CLIMATOLOGY_YEARS
    base = monthly[(monthly.index.get_level_values("year") >= y0) & (monthly.index.get_level_values("year") <= y1)]
    return base.groupby(level="month")[["prcp", "tmax", "tmin", "srad", "gwet", "rh", "heavy_days"]].mean()


def _longest_run(mask: np.ndarray) -> int:
    best = run = 0
    for flag in mask:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


# --------------------------------------------------------------------------------------
# Cyclones (IBTrACS, North Indian Ocean)
# --------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def cyclone_tracks() -> pd.DataFrame:
    path = config.RAW / "ibtracs" / "ibtracs.NI.list.v04r01.csv"
    cols = ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "WMO_WIND", "USA_WIND"]
    df = pd.read_csv(path, skiprows=[1], usecols=cols, keep_default_na=False, na_values=["", " "], low_memory=False)
    df["time"] = pd.to_datetime(df["ISO_TIME"])
    for c in ("LAT", "LON", "WMO_WIND", "USA_WIND"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # IMD (WMO agency for this basin) reports 3-minute sustained winds; JTWC's 1-minute winds are
    # scaled by 0.88 when IMD has no value, a standard approximate conversion.
    df["wind_kt"] = df["WMO_WIND"].fillna(df["USA_WIND"] * 0.88)
    df = df[(df["SEASON"] >= 1991) & df["LON"].between(76, 94) & df["LAT"].between(12, 27)]
    return df.dropna(subset=["wind_kt"])[["SID", "NAME", "time", "LAT", "LON", "wind_kt"]].reset_index(drop=True)


def _distance_km(lon: float, lat: float, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    lon, lat, lons, lats = np.radians(lon), np.radians(lat), np.radians(lons), np.radians(lats)
    a = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def cyclone_features(lon: float, lat: float, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    tracks = cyclone_tracks()
    pts = tracks[(tracks["time"] >= start) & (tracks["time"] <= end)]
    if pts.empty:
        return {"cyclone_wind_kt": 0.0, "cyclone_exposure": 0.0}
    d = _distance_km(lon, lat, pts["LON"].to_numpy(), pts["LAT"].to_numpy())
    wind = pts["wind_kt"].to_numpy()
    core = wind[d <= config.CYCLONE_CORE_KM]
    exposure = wind * np.clip(1 - d / config.CYCLONE_EXPOSURE_KM, 0, 1)
    return {
        "cyclone_wind_kt": float(core.max()) if core.size else 0.0,
        "cyclone_exposure": float(exposure.max()),
    }


def cyclone_events(lon: float, lat: float, start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    """Named storms that came within the exposure radius - shown to users as context."""
    tracks = cyclone_tracks()
    pts = tracks[(tracks["time"] >= start) & (tracks["time"] <= end)].copy()
    if pts.empty:
        return []
    pts["dist_km"] = _distance_km(lon, lat, pts["LON"].to_numpy(), pts["LAT"].to_numpy())
    near = pts[pts["dist_km"] <= config.CYCLONE_EXPOSURE_KM]
    events = []
    for sid, g in near.groupby("SID"):
        closest = g.loc[g["dist_km"].idxmin()]
        name = str(closest["NAME"]).title()
        events.append(
            {
                "name": "Unnamed depression" if name in ("Unnamed", "Not_Named") else name.split(":")[0],
                "date": closest["time"].strftime("%Y-%m-%d"),
                "closest_km": round(float(closest["dist_km"])),
                "max_wind_kt": round(float(g["wind_kt"].max())),
                "sid": sid,
            }
        )
    return sorted(events, key=lambda e: e["date"])


# --------------------------------------------------------------------------------------
# Season features
# --------------------------------------------------------------------------------------
def season_features(slug: str, year: int, lead_month: int) -> dict[str, float] | None:
    """Features for one district-season, using data up to the end of ``lead_month``.

    Returns None when any required month is not yet complete in the weather record.
    """
    df = daily(slug)
    mon = monthly_for(slug)
    clim = climatology_for(slug)
    months = [m for m in config.SEASON_MONTHS if m <= lead_month]
    for m in months:
        if (year, m) not in mon.index or not bool(mon.loc[(year, m), "complete"]):
            return None

    feats: dict[str, float] = {}
    for m in months:
        row, c = mon.loc[(year, m)], clim.loc[m]
        tag = MONTH_ABBR[m]
        feats[f"prcp_anom_{tag}"] = float(np.clip(row["prcp"] / c["prcp"] - 1.0, -1.0, 4.0))
        feats[f"tmax_anom_{tag}"] = float(row["tmax"] - c["tmax"])
        feats[f"tmin_anom_{tag}"] = float(row["tmin"] - c["tmin"])
        feats[f"srad_anom_{tag}"] = float(row["srad"] - c["srad"])
        feats[f"gwet_anom_{tag}"] = float(row["gwet"] - c["gwet"])
        feats[f"heavy_days_{tag}"] = float(row["heavy_days"])

    start = pd.Timestamp(year, 6, 1)
    end = pd.Timestamp(year, lead_month, calendar.monthrange(year, lead_month)[1])
    season = df.loc[start:end]
    total, normal = float(season["prcp"].sum()), float(clim.loc[months, "prcp"].sum())
    feats["prcp_anom_season"] = float(np.clip(total / normal - 1.0, -1.0, 4.0))
    feats["prcp_3day_max"] = float(season["prcp"].rolling(3).sum().max())
    core = season.loc[pd.Timestamp(year, 7, 1) :]
    feats["dry_spell_days"] = float(_longest_run((core["prcp"] < config.WET_DAY_MM).to_numpy())) if len(core) else 0.0
    late = season.loc[pd.Timestamp(year, 8, 1) :]
    feats["hot_days"] = float((late["tmax"] >= config.HOT_DAY_C).sum()) if len(late) else 0.0

    # Compact summaries (fewer, physically motivated predictors - less prone to overfitting)
    recent = [m for m in months if m >= lead_month - 1]
    feats["prcp_anom_recent"] = float(
        np.clip(mon.loc[[(year, m) for m in recent], "prcp"].sum() / clim.loc[recent, "prcp"].sum() - 1.0, -1.0, 4.0)
    )
    wet_months = [m for m in months if m >= 7] or months
    feats["gwet_anom_mean"] = float(np.mean([feats[f"gwet_anom_{MONTH_ABBR[m]}"] for m in wet_months]))
    heat_months = [m for m in months if m >= 8] or months
    feats["tmax_anom_mean"] = float(np.mean([feats[f"tmax_anom_{MONTH_ABBR[m]}"] for m in heat_months]))
    feats["heavy_days_season"] = float(sum(feats[f"heavy_days_{MONTH_ABBR[m]}"] for m in months))

    lon, lat = district_centroids()[slug]
    cyc_start = pd.Timestamp(year, config.CYCLONE_WINDOW_START_MONTH, 1)
    cyc_end = end + pd.Timedelta(hours=23, minutes=59)
    feats.update(cyclone_features(lon, lat, cyc_start, cyc_end))
    feats["coastal"] = float(config.BY_SLUG[slug].coastal)
    feats["kbk"] = float(config.BY_SLUG[slug].kbk)
    return feats


COMPACT_FEATURES = (
    "prcp_anom_season",
    "prcp_anom_recent",
    "gwet_anom_mean",
    "tmax_anom_mean",
    "dry_spell_days",
    "heavy_days_season",
    "prcp_3day_max",
    "cyclone_wind_kt",
    "cyclone_exposure",
    "coastal",
    "kbk",
)


def feature_columns(all_columns: list[str], feature_set: str) -> list[str]:
    if feature_set == "compact":
        return [c for c in COMPACT_FEATURES if c in all_columns]
    if feature_set == "monthly":
        compact_only = {"prcp_anom_recent", "gwet_anom_mean", "tmax_anom_mean", "heavy_days_season", "kbk"}
        return [c for c in all_columns if c not in compact_only]
    raise ValueError(feature_set)


@cache
def monthly_for(slug: str) -> pd.DataFrame:
    return monthly_table(daily(slug))


@cache
def climatology_for(slug: str) -> pd.DataFrame:
    return climatology(monthly_for(slug))


def feature_table(lead: str, years: range) -> pd.DataFrame:
    """Feature matrix (index: district_slug, year) for one lead time."""
    lead_month = config.LEAD_MONTHS[lead]
    rows = []
    for d in config.DISTRICTS:
        for year in years:
            feats = season_features(d.slug, year, lead_month)
            if feats is not None:
                rows.append({"district_slug": d.slug, "year": year, **feats})
    return pd.DataFrame(rows).set_index(["district_slug", "year"]).sort_index()


def weather_monthly_export() -> pd.DataFrame:
    """Monthly weather with 1991-2020 normals, for the app's 'season so far' panels."""
    frames = []
    for d in config.DISTRICTS:
        mon = monthly_for(d.slug)
        clim = climatology_for(d.slug)
        m = mon[mon["complete"]].reset_index()
        m = m.merge(clim[["prcp", "tmax", "tmin"]].add_suffix("_normal"), left_on="month", right_index=True)
        m.insert(0, "district_slug", d.slug)
        frames.append(m)
    out = pd.concat(frames, ignore_index=True)
    keep = [
        "district_slug",
        "year",
        "month",
        "prcp",
        "prcp_normal",
        "tmax",
        "tmax_normal",
        "tmin",
        "tmin_normal",
        "gwet",
        "heavy_days",
        "wet_days",
    ]
    out = out[keep]
    return out.round({"prcp": 1, "prcp_normal": 1, "tmax": 2, "tmax_normal": 2, "tmin": 2, "tmin_normal": 2, "gwet": 3})


# --------------------------------------------------------------------------------------
# Human-readable descriptions (used for the "what drives this forecast" panel)
# --------------------------------------------------------------------------------------
def describe(feature: str) -> dict[str, str]:
    """Label and display unit for a feature name."""
    parts = feature.rsplit("_", 1)
    month = next((m for m, a in MONTH_ABBR.items() if len(parts) == 2 and parts[1] == a), None)
    if month is not None:
        base, mname = parts[0], MONTH_NAME[month]
        table = {
            "prcp_anom": (f"{mname} rainfall vs normal", "pct"),
            "tmax_anom": (f"{mname} daytime temperature vs normal", "degC"),
            "tmin_anom": (f"{mname} night temperature vs normal", "degC"),
            "srad_anom": (f"{mname} sunshine (solar radiation) vs normal", "MJ"),
            "gwet_anom": (f"{mname} soil moisture vs normal", "frac"),
            "heavy_days": (f"{mname} heavy-rain days (>= 64.5 mm)", "days"),
        }
        if base in table:
            label, unit = table[base]
            return {"label": label, "unit": unit}
    static = {
        "prcp_anom_season": ("Season rainfall so far vs normal", "pct"),
        "prcp_anom_recent": ("Rainfall in the last two months vs normal", "pct"),
        "gwet_anom_mean": ("Soil moisture since July vs normal", "frac"),
        "tmax_anom_mean": ("Daytime temperature since August vs normal", "degC"),
        "heavy_days_season": ("Heavy-rain days (>= 64.5 mm) this season", "days"),
        "prcp_3day_max": ("Wettest 3-day spell", "mm"),
        "dry_spell_days": ("Longest dry spell since July", "days"),
        "hot_days": ("Hot days (>= 35 °C) since August", "days"),
        "cyclone_wind_kt": ("Cyclone wind within 150 km", "kt"),
        "cyclone_exposure": ("Cyclone exposure (wind, distance-weighted)", "kt"),
        "coastal": ("Coastal district", "flag"),
        "kbk": ("KBK (drought-prone) district", "flag"),
    }
    label, unit = static.get(feature, (feature, ""))
    return {"label": label, "unit": unit}
