"""Central configuration: paths, the district master table, sources and forecast settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
MODELS = ROOT / "models"


@dataclass(frozen=True)
class District:
    slug: str
    name: str  # canonical name, as spelled by DES (Directorate of Economics & Statistics)
    upag: str  # spelling used by the UPAg portal
    geo: str  # spelling used by geoBoundaries
    coastal: bool  # has a sea coast
    kbk: bool  # part of the Kalahandi-Balangir-Koraput (KBK) region


# fmt: off
DISTRICTS: tuple[District, ...] = (
    District("angul",          "Angul",          "Anugola",        "Anugul",         False, False),
    District("balangir",       "Balangir",       "Balangir",       "Balangir",       False, True),
    District("balasore",       "Balasore",       "Baleshwar",      "Baleshwar",      True,  False),
    District("bargarh",        "Bargarh",        "Baragada",       "Bargarh",        False, False),
    District("bhadrak",        "Bhadrak",        "Bhadrak",        "Bhadrak",        True,  False),
    District("boudh",          "Boudh",          "Boudh",          "Baudh",          False, False),
    District("cuttack",        "Cuttack",        "Kataka",         "Cuttack",        False, False),
    District("deogarh",        "Deogarh",        "Debagada",       "Debagarh",       False, False),
    District("dhenkanal",      "Dhenkanal",      "Dhenkanal",      "Dhenkanal",      False, False),
    District("gajapati",       "Gajapati",       "Gajapati",       "Gajapati",       False, False),
    District("ganjam",         "Ganjam",         "Ganjam",         "Ganjam",         True,  False),
    District("jagatsinghpur",  "Jagatsinghpur",  "Jagatsinghapur", "Jagatsinghapur", True,  False),
    District("jajpur",         "Jajpur",         "Jajpur",         "Jajapur",        False, False),
    District("jharsuguda",     "Jharsuguda",     "Jharsuguda",     "Jharsuguda",     False, False),
    District("kalahandi",      "Kalahandi",      "Kalahandi",      "Kalahandi",      False, True),
    District("kandhamal",      "Kandhamal",      "Kandhamala",     "Kandhamal",      False, False),
    District("kendrapara",     "Kendrapara",     "Kendrapada",     "Kendrapara",     True,  False),
    District("keonjhar",       "Keonjhar",       "Kendujhar",      "Kendujhar",      False, False),
    District("khordha",        "Khordha",        "Khordha",        "Khordha",        False, False),
    District("koraput",        "Koraput",        "Koraput",        "Koraput",        False, True),
    District("malkangiri",     "Malkangiri",     "Malkangiri",     "Malkangiri",     False, True),
    District("mayurbhanj",     "Mayurbhanj",     "Mayurbhanj",     "Mayurbhanj",     False, False),
    District("nabarangpur",    "Nabarangpur",    "Nabarangpur",    "Nabarangapur",   False, True),
    District("nayagarh",       "Nayagarh",       "Nayagada",       "Nayagarh",       False, False),
    District("nuapada",        "Nuapada",        "Nuapada",        "Nuapada",        False, True),
    District("puri",           "Puri",           "Puri",           "Puri",           True,  False),
    District("rayagada",       "Rayagada",       "Rayagada",       "Rayagada",       False, True),
    District("sambalpur",      "Sambalpur",      "Sambalpur",      "Sambalpur",      False, False),
    District("subarnapur",     "Subarnapur",     "Subarnapur",     "Subarnapur",     False, True),
    District("sundargarh",     "Sundargarh",     "Sundaragada",    "Sundargarh",     False, False),
)
# fmt: on

# DES spells two districts differently from the display names above.
DES_ALIASES = {"Jagatsinghapur": "jagatsinghpur", "Sonepur": "subarnapur"}

BY_SLUG = {d.slug: d for d in DISTRICTS}


def slug_for(name: str, source: str) -> str | None:
    """Map a district name from a given source ("des", "upag", "geo") to our slug."""
    name = name.strip()
    if source == "des" and name in DES_ALIASES:
        return DES_ALIASES[name]
    for d in DISTRICTS:
        candidate = {"des": d.name, "upag": d.upag, "geo": d.geo}[source]
        if candidate.lower() == name.lower():
            return d.slug
    return None


# --------------------------------------------------------------------------------------
# Remote sources (all public, no credentials required)
# --------------------------------------------------------------------------------------
APY_DES_URL = (
    "https://ckandev.indiadataportal.com/dataset/f2bbc28c-6c7c-462b-9064-ea4c4213d466/"
    "resource/f980409d-49a2-42ae-9eb0-182365005c04/download/crop-wise-area-production-yield.csv"
)
APY_UPAG_URL = (
    "https://ckandev.indiadataportal.com/dataset/f2bbc28c-6c7c-462b-9064-ea4c4213d466/"
    "resource/6f70d961-3a4f-4caa-b08f-f72f708791e1/download/cropwise-area-production-yield-upag.csv"
)
BOUNDARIES_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/"
    "geoBoundaries-IND-ADM2_simplified.geojson"
)
IBTRACS_URL = (
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
    "v04r01/access/csv/ibtracs.NI.list.v04r01.csv"
)
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = {
    "PRECTOTCORR": "prcp",  # precipitation, mm/day (bias-corrected)
    "T2M_MAX": "tmax",  # daily max 2 m air temperature, deg C
    "T2M_MIN": "tmin",  # daily min 2 m air temperature, deg C
    "ALLSKY_SFC_SW_DWN": "srad",  # all-sky surface shortwave radiation, MJ/m2/day (AG community)
    "GWETROOT": "gwet",  # root-zone soil wetness, 0-1
    "RH2M": "rh",  # relative humidity at 2 m, %
}
WEATHER_START = "1991-01-01"  # 1991-2020 is the WMO standard climate normal period

# --------------------------------------------------------------------------------------
# Forecast setup
# --------------------------------------------------------------------------------------
CLIMATOLOGY_YEARS = (1991, 2020)
SEASON_MONTHS = (6, 7, 8, 9, 10, 11)  # Jun..Nov: Kharif (autumn + winter) rice season in Odisha
CYCLONE_WINDOW_START_MONTH = 5  # May storms (e.g. Fani, Amphan, Yaas) disrupt Kharif preparation
LEAD_MONTHS = {"Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11}  # forecast issued at month end

FIRST_BACKTEST_YEAR = 2003  # needs >= 5 training seasons (1998-2002)
VALIDATION_YEARS = tuple(range(2006, 2015))  # model selection only
TEST_YEARS = tuple(range(2015, 2025))  # reported performance (never used for selection)
CALIBRATION_YEARS = 10  # conformal calibration window (most recent out-of-sample years)
INTERVAL_LEVELS = (0.8, 0.9)

HEAVY_RAIN_MM = 64.5  # IMD "heavy rainfall" threshold
WET_DAY_MM = 2.5  # IMD "rainy day" threshold
HOT_DAY_C = 35.0
CYCLONE_CORE_KM = 150.0
CYCLONE_EXPOSURE_KM = 300.0
