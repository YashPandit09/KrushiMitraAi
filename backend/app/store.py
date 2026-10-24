"""Read-only, in-memory store of the processed artifacts produced by the pipeline.

Everything the API serves (except the live weather/market proxies) comes from files in
``data/processed`` that are versioned with the code, so the app works right after a clone.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = (
    "districts.json",
    "districts.geojson",
    "yields_odisha.csv",
    "kharif_rice.csv",
    "backtest.csv",
    "forecasts.json",
    "evaluation.json",
    "weather_monthly.csv",
)


def _num(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class DataStore:
    districts: list[dict]
    by_slug: dict[str, dict]
    geojson: bytes
    geojson_etag: str
    kharif: dict[str, list[dict]]
    yields: dict[str, list[dict]]
    crops: dict[str, dict[str, list[str]]]
    backtest: dict[tuple[str, str], list[dict]]
    forecasts: dict
    evaluation: dict
    weather: dict[str, list[dict]]

    @classmethod
    def load(cls, data_dir: Path) -> DataStore:
        missing = [f for f in REQUIRED_FILES if not (data_dir / f).exists()]
        if missing:
            raise FileNotFoundError(
                f"processed data missing in {data_dir}: {missing}. Run `python -m pipeline all` to rebuild it."
            )
        districts = json.loads((data_dir / "districts.json").read_text(encoding="utf-8"))
        by_slug = {d["slug"]: d for d in districts}
        geojson = (data_dir / "districts.geojson").read_bytes()

        kharif: dict[str, list[dict]] = defaultdict(list)
        for r in _read_csv(data_dir / "kharif_rice.csv"):
            row = {
                "year": int(r["year"]),
                "yield_t_ha": _num(r["yield_t_ha"]),
                "area_ha": _num(r["area_ha"]),
                "production_t": _num(r["production_t"]),
                "source": r["source"],
                "qc_flag": r["qc_flag"] or None,
            }
            kharif[r["district_slug"]].append(row)
        for rows in kharif.values():
            rows.sort(key=lambda x: x["year"])

        yields: dict[str, list[dict]] = defaultdict(list)
        crops: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for r in _read_csv(data_dir / "yields_odisha.csv"):
            slug = r["district_slug"]
            yields[slug].append(
                {
                    "year": int(r["year"]),
                    "agri_year": r["agri_year"],
                    "crop": r["crop"],
                    "season": r["season"],
                    "area_ha": _num(r["area_ha"]),
                    "production": _num(r["production"]),
                    "production_unit": r["production_unit"],
                    "yield": _num(r["yield"]),
                    "yield_unit": r["yield_unit"],
                    "source": r["source"],
                }
            )
            crops[slug][r["crop"]].add(r["season"])

        backtest: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for r in _read_csv(data_dir / "backtest.csv"):
            backtest[(r["district_slug"], r["lead"])].append(
                {
                    "year": int(r["year"]),
                    "actual": _num(r["actual"]),
                    "forecast": _num(r["forecast"]),
                    "trend": _num(r["trend"]),
                    "lo80": _num(r["lo80"]),
                    "hi80": _num(r["hi80"]),
                    "lo90": _num(r["lo90"]),
                    "hi90": _num(r["hi90"]),
                    "persistence": _num(r["persistence"]),
                    "mean5": _num(r["mean5"]),
                    "qc_flag": r["qc_flag"] or None,
                }
            )

        weather: dict[str, list[dict]] = defaultdict(list)
        for r in _read_csv(data_dir / "weather_monthly.csv"):
            weather[r["district_slug"]].append(
                {k: (int(v) if k in ("year", "month") else _num(v)) for k, v in r.items() if k != "district_slug"}
            )

        return cls(
            districts=districts,
            by_slug=by_slug,
            geojson=geojson,
            geojson_etag='"' + hashlib.sha256(geojson).hexdigest()[:32] + '"',
            kharif=dict(kharif),
            yields=dict(yields),
            crops={s: {c: sorted(v) for c, v in cs.items()} for s, cs in crops.items()},
            backtest=dict(backtest),
            forecasts=json.loads((data_dir / "forecasts.json").read_text(encoding="utf-8")),
            evaluation=json.loads((data_dir / "evaluation.json").read_text(encoding="utf-8")),
            weather=dict(weather),
        )

    # ------------------------------------------------------------------ helpers
    @property
    def leads(self) -> list[str]:
        return list(self.evaluation["protocol"]["leads"].keys())

    def forecast_years(self) -> list[int]:
        return sorted({f["year"] for f in self.forecasts["forecasts"]})

    def leads_for_year(self, year: int) -> list[str]:
        available = {f["lead"] for f in self.forecasts["forecasts"] if f["year"] == year}
        return [lead for lead in self.leads if lead in available]

    def forecasts_for(self, year: int, lead: str) -> list[dict]:
        return [f for f in self.forecasts["forecasts"] if f["year"] == year and f["lead"] == lead]

    def forecasts_for_district(self, slug: str) -> list[dict]:
        return [f for f in self.forecasts["forecasts"] if f["district_slug"] == slug]
