from __future__ import annotations

import pandas as pd
import pytest

from pipeline import config, harmonize


def _row(slug, year, crop, season, area, prod, source="DES"):
    return {
        "district_slug": slug,
        "year": year,
        "agri_year": f"{year}-{str(year + 1)[-2:]}",
        "crop": crop,
        "season": season,
        "area_ha": area,
        "production": prod,
        "production_unit": "Tonnes",
        "yield": prod / area,
        "yield_unit": "Tonnes/Hectare",
        "source": source,
    }


NEIGHBOURS = {"cuttack": ["puri"], "puri": ["cuttack"]}


def test_season_start_year():
    assert harmonize.season_start_year("1998-1999") == 1998


def test_slug_mapping_handles_source_spellings():
    assert config.slug_for("Kataka", "upag") == "cuttack"
    assert config.slug_for("Baleshwar", "geo") == "balasore"
    assert config.slug_for("Sonepur", "des") == "subarnapur"
    assert config.slug_for("Atlantis", "des") is None


def test_kharif_combines_autumn_and_winter_and_prefers_explicit_kharif():
    des = pd.DataFrame(
        [
            _row("cuttack", 2010, "Rice", "Autumn", 10_000, 15_000),
            _row("cuttack", 2010, "Rice", "Winter", 90_000, 180_000),
            _row("cuttack", 2010, "Rice", "Summer", 5_000, 15_000),  # not Kharif
            _row("cuttack", 2011, "Rice", "Kharif", 100_000, 210_000),
            _row("puri", 2010, "Rice", "Winter", 80_000, 160_000),
            _row("puri", 2011, "Rice", "Winter", 80_000, 168_000),
        ]
    )
    upag = pd.DataFrame(
        [
            _row("cuttack", 2011, "Rice", "Kharif", 1, 999_999, "UPAg"),  # overlaps DES: must be ignored
            _row("cuttack", 2012, "Rice", "Kharif", 100_000, 250_000, "UPAg"),  # newer: used
        ]
    )
    out = harmonize.build_kharif_rice(des, upag, NEIGHBOURS).set_index(["district_slug", "year"])
    assert out.loc[("cuttack", 2010), "yield_t_ha"] == pytest.approx(195_000 / 100_000)
    assert out.loc[("cuttack", 2010), "components"] == "Autumn+Winter"
    assert out.loc[("cuttack", 2011), "components"] == "Kharif"
    assert out.loc[("cuttack", 2011), "source"] == "DES"
    assert out.loc[("cuttack", 2012), "source"] == "UPAg"
    assert out.loc[("puri", 2010), "components"] == "Winter"


def test_explorer_extends_only_rice_with_newer_upag_years():
    des = pd.DataFrame([_row("puri", 2022, "Rice", "Winter", 1, 2), _row("puri", 2022, "Maize", "Kharif", 1, 2)])
    upag = pd.DataFrame(
        [
            _row("puri", 2022, "Rice", "Rabi", 1, 2, "UPAg"),
            _row("puri", 2023, "Rice", "Kharif", 1, 2, "UPAg"),
            _row("puri", 2023, "Maize", "Kharif", 1, 2, "UPAg"),
        ]
    )
    table = harmonize.build_explorer_table(des, upag)
    assert set(zip(table["year"], table["crop"], table["source"], strict=True)) == {
        (2022, "Rice", "DES"),
        (2022, "Maize", "DES"),
        (2023, "Rice", "UPAg"),
    }


def test_quality_flags_are_informational_only():
    slugs = ["cuttack", "puri", "khordha", "jajpur"]
    neighbours = {s: [o for o in slugs if o != s] for s in slugs}
    rows = []
    for year in range(2000, 2012):
        for s in slugs:
            prod = 40 if (s == "cuttack" and year == 2006) else 200
            rows.append(_row(s, year, "Rice", "Winter", 100, prod))
    des = pd.DataFrame(rows)
    out = harmonize.build_kharif_rice(des, des.iloc[0:0], neighbours)
    assert len(out) == 48  # nothing dropped
    flagged = out[out["qc_flag"] != ""]
    assert list(zip(flagged["district_slug"], flagged["year"], flagged["qc_flag"], strict=True)) == [
        ("cuttack", 2006, "unusually_low")
    ]
