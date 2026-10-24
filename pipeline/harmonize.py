"""Harmonise official district crop statistics (area, production, yield) for Odisha.

Two public sources, both via the India Data Portal (ODC-By licence):

* DES  - Directorate of Economics & Statistics, 1997-98 to 2022-23, all crops.
* UPAg - Unified Portal for Agricultural Statistics, 2013-14 to 2024-25.

On the years they share, UPAg re-labels Odisha's rice seasons: UPAg "Kharif" equals DES "Autumn",
UPAg "Rabi" equals DES "Winter" and "Summer" is unchanged (values match exactly). From 2023-24
UPAg reports a single combined "Kharif" (autumn + winter) figure. We therefore use DES for every
year it covers and take only the newer years from UPAg.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)

EXPLORER_COLUMNS = [
    "district_slug",
    "year",
    "agri_year",
    "crop",
    "season",
    "area_ha",
    "production",
    "production_unit",
    "yield",
    "yield_unit",
    "source",
]


def season_start_year(agri_year: str) -> int:
    """'1998-1999' -> 1998 (the calendar year in which the Kharif season is sown)."""
    return int(str(agri_year).split("-")[0])


def _short_agri_year(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def _map_slugs(df: pd.DataFrame, source: str) -> pd.DataFrame:
    names = df["district_name"].astype(str).str.strip()
    slugs = names.map(lambda n: config.slug_for(n, source))
    unknown = sorted(names[slugs.isna()].unique())
    if unknown:
        raise ValueError(f"unmapped {source} district names: {unknown}")
    return df.assign(district_slug=slugs)


def load_des(path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[df["state_name"].astype(str).str.strip().str.lower() == "odisha"].copy()
    df = _map_slugs(df, "des")
    year = df["year"].map(season_start_year)
    return pd.DataFrame(
        {
            "district_slug": df["district_slug"],
            "year": year,
            "agri_year": year.map(_short_agri_year),
            "crop": df["crop_name"].astype(str).str.strip(),
            "season": df["season"].astype(str).str.strip(),
            "area_ha": pd.to_numeric(df["area"], errors="coerce"),
            "production": pd.to_numeric(df["production"], errors="coerce"),
            "production_unit": df["production_unit"].astype(str).str.strip(),
            "yield": pd.to_numeric(df["yield"], errors="coerce"),
            "yield_unit": df["yield_unit"].astype(str).str.strip(),
            "source": "DES",
        }
    )


def load_upag(path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = df[df["state_name"].astype(str).str.strip().str.lower() == "odisha"].copy()
    df = _map_slugs(df, "upag")
    year = df["year"].map(season_start_year)
    return pd.DataFrame(
        {
            "district_slug": df["district_slug"],
            "year": year,
            "agri_year": year.map(_short_agri_year),
            "crop": df["crop_name"].astype(str).str.strip(),
            "season": df["season"].astype(str).str.strip(),
            "area_ha": pd.to_numeric(df["area"], errors="coerce"),
            "production": pd.to_numeric(df["production"], errors="coerce"),
            "production_unit": "Tonnes",
            "yield": pd.to_numeric(df["yield"], errors="coerce") / 1000.0,  # kg/ha -> t/ha
            "yield_unit": "Tonnes/Hectare",
            "source": "UPAg",
        }
    )


def build_explorer_table(des: pd.DataFrame, upag: pd.DataFrame) -> pd.DataFrame:
    """All DES crops and seasons, extended with UPAg rice for years DES does not cover yet."""
    last_des_year = int(des["year"].max())
    newer_rice = upag[(upag["crop"] == "Rice") & (upag["year"] > last_des_year)]
    table = pd.concat([des, newer_rice], ignore_index=True)
    table = table.sort_values(["district_slug", "crop", "season", "year"]).reset_index(drop=True)
    table["yield"] = table["yield"].round(3)
    return table[EXPLORER_COLUMNS]


def build_kharif_rice(des: pd.DataFrame, upag: pd.DataFrame, neighbours: dict[str, list[str]]) -> pd.DataFrame:
    """District-level Kharif (autumn + winter) rice: area, production and yield per season."""
    rows = []
    rice_des = des[des["crop"] == "Rice"]
    for (slug, year), grp in rice_des.groupby(["district_slug", "year"]):
        by_season = grp.set_index("season")
        if "Kharif" in by_season.index:
            area, prod, parts = by_season.at["Kharif", "area_ha"], by_season.at["Kharif", "production"], "Kharif"
        elif "Winter" in by_season.index:
            area, prod = by_season.at["Winter", "area_ha"], by_season.at["Winter", "production"]
            parts = "Winter"
            if "Autumn" in by_season.index and pd.notna(by_season.at["Autumn", "area_ha"]):
                area += by_season.at["Autumn", "area_ha"]
                prod += np.nan_to_num(by_season.at["Autumn", "production"])
                parts = "Autumn+Winter"
        else:
            continue
        rows.append((slug, year, area, prod, parts, "DES"))

    last_des_year = int(rice_des["year"].max())
    newer = upag[(upag["crop"] == "Rice") & (upag["season"] == "Kharif") & (upag["year"] > last_des_year)]
    for r in newer.itertuples(index=False):
        rows.append((r.district_slug, r.year, r.area_ha, r.production, "Kharif", "UPAg"))

    out = pd.DataFrame(rows, columns=["district_slug", "year", "area_ha", "production_t", "components", "source"])
    out["yield_t_ha"] = out["production_t"] / out["area_ha"]
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["yield_t_ha"])
    out = out[(out["area_ha"] > 0) & (out["production_t"] > 0)]
    out = flag_quality(out, neighbours)
    out["yield_t_ha"] = out["yield_t_ha"].round(4)
    return out.sort_values(["district_slug", "year"]).reset_index(drop=True)


HIGH_RATIO = 1.6  # far above what the district's own history and its region imply
LOW_RATIO = 0.6  # far below (cyclone, flood, drought, pest outbreak...)


def _year_window_median(series: pd.Series, half_window: int = 4) -> pd.Series:
    """For each year, the median of the surrounding +/- half_window years (the year itself excluded)."""
    values = series.to_dict()
    out = {}
    for year in series.index:
        around = [values[y] for y in range(year - half_window, year + half_window + 1) if y != year and y in values]
        out[year] = float(np.median(around)) if len(around) >= 3 else np.nan
    return pd.Series(out, dtype=float)


def flag_quality(df: pd.DataFrame, neighbours: dict[str, list[str]]) -> pd.DataFrame:
    """Label unusual district-years. Informational only - no observation is dropped.

    Official district statistics are noisy, but most extreme lows are real: the 1999 Super
    Cyclone, the 2000/2002/2015 droughts, Cyclone Phailin (2013), the 2017 brown planthopper
    outbreak. And a district far above its drought-hit neighbours may simply be better
    irrigated. Because no rule separates errors from real extremes reliably, every value is
    kept; the models use robust (Huber) losses instead, and the evaluation reports a
    sensitivity check that excludes the labelled rows.

    Each district-year is compared with its own neighbouring years and with how its five
    nearest districts moved in that same year:

        qc_ratio = value / (own_window_median x median(neighbour_value / neighbour_window_median))
    """
    df = df.copy()
    wide = df.pivot(index="year", columns="district_slug", values="yield_t_ha")
    window = wide.apply(_year_window_median)
    relative = wide / window  # how unusual each district-year is versus its own history
    ratio = pd.DataFrame(index=wide.index, columns=wide.columns, dtype=float)
    for slug in wide.columns:
        regional = relative[neighbours[slug]].median(axis=1, skipna=True)
        ratio[slug] = wide[slug] / (window[slug] * regional)
    long = ratio.stack().rename("qc_ratio").reset_index()
    df = df.merge(long, on=["year", "district_slug"], how="left")
    df["qc_ratio"] = df["qc_ratio"].round(3)
    df["qc_flag"] = np.select(
        [df["qc_ratio"] > HIGH_RATIO, df["qc_ratio"] < LOW_RATIO], ["unusually_high", "unusually_low"], default=""
    )
    return df
