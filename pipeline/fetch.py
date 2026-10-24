"""Download raw inputs into data/raw/. Every source is public and needs no credentials.

Downloads are cached: a file that already exists is reused unless ``refresh=True``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import requests

from . import config
from .geo import district_centroids

log = logging.getLogger(__name__)

USER_AGENT = "KrushiMitraAI-pipeline/1.0 (+https://github.com/YashPandit09/KrushiMitraAi)"
TIMEOUT = (15, 300)  # connect, read seconds


def _download(url: str, dest: Path, *, params: dict | None = None, refresh: bool = False) -> Path:
    if dest.exists() and dest.stat().st_size > 0 and not refresh:
        log.info("cached  %s", dest.relative_to(config.ROOT))
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, 5):
        try:
            log.info("fetch   %s (attempt %d)", url.split("?")[0], attempt)
            with requests.get(
                url, params=params, stream=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
            ) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            tmp.replace(dest)
            return dest
        except requests.RequestException as exc:
            log.warning("download failed: %s", exc)
            time.sleep(2**attempt)
    raise RuntimeError(f"could not download {url}")


def fetch_apy(refresh: bool = False) -> tuple[Path, Path]:
    des = _download(config.APY_DES_URL, config.RAW / "apy" / "apy_des.csv", refresh=refresh)
    upag = _download(config.APY_UPAG_URL, config.RAW / "apy" / "apy_upag.csv", refresh=refresh)
    return des, upag


def fetch_boundaries(refresh: bool = False) -> Path:
    return _download(
        config.BOUNDARIES_URL, config.RAW / "boundaries" / "geoBoundaries-IND-ADM2_simplified.geojson", refresh=refresh
    )


def fetch_ibtracs(refresh: bool = False) -> Path:
    return _download(config.IBTRACS_URL, config.RAW / "ibtracs" / "ibtracs.NI.list.v04r01.csv", refresh=refresh)


POWER_CHUNK_YEARS = 10
# Observed with the POWER daily API v2.10.1 (Oct 2026): when a request includes the current
# (near-real-time) year, *every* precipitation value in the response is multiplied by 24, while
# requests ending on or before 31 Dec of the previous year are correct. We therefore download
# history in 10-year chunks ending last year, fetch the current year separately with an overlap
# on the previous monsoon, estimate the scale factor on that overlap and correct for it. The merged record is
# then checked against physical limits for Odisha so that a silent unit change cannot slip through.
ANNUAL_RAIN_MM = (600.0, 4000.0)
MAX_DAILY_RAIN_MM = 800.0
KNOWN_SCALE_FACTORS = (1.0, 24.0)


def _power_chunk(lon: float, lat: float, start: date, end: date) -> dict:
    params = {
        "parameters": ",".join(config.POWER_PARAMETERS),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }
    for attempt in range(1, 5):
        try:
            resp = requests.get(config.POWER_URL, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            payload = resp.json()
            data = payload["properties"]["parameter"]
            missing = [p for p in config.POWER_PARAMETERS if p not in data]
            if missing:
                raise RuntimeError(f"NASA POWER response is missing {missing}")
            return data
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("POWER chunk %s..%s failed (attempt %d): %s", start, end, attempt, exc)
            time.sleep(2**attempt)
    raise RuntimeError(f"could not download NASA POWER data for {lon},{lat} {start}..{end}")


def fetch_power(refresh: bool = False, end: date | None = None) -> dict[str, Path]:
    """Daily NASA POWER weather at each district centroid, 1991 to ``end`` (default: today)."""
    end = end or date.today()
    first = date.fromisoformat(config.WEATHER_START)
    out: dict[str, Path] = {}
    for slug, (lon, lat) in district_centroids().items():
        dest = config.RAW / "power" / f"{slug}.json"
        out[slug] = dest
        if dest.exists() and not refresh:
            log.info("cached  %s", dest.relative_to(config.ROOT))
            continue
        merged: dict[str, dict[str, float]] = {p: {} for p in config.POWER_PARAMETERS}
        history_end = date(end.year - 1, 12, 31)
        for y0 in range(first.year, history_end.year + 1, POWER_CHUNK_YEARS):
            c_start = date(y0, 1, 1)
            c_end = min(date(y0 + POWER_CHUNK_YEARS - 1, 12, 31), history_end)
            log.info("fetch   NASA POWER %s %s..%s", slug, c_start, c_end)
            chunk = _power_chunk(lon, lat, c_start, c_end)
            for p in config.POWER_PARAMETERS:
                merged[p].update(chunk[p])
        overlap_start = date(end.year - 1, 6, 1)  # overlap the previous monsoon: plenty of rainy days
        log.info("fetch   NASA POWER %s %s..%s (current year)", slug, overlap_start, end)
        current = _power_chunk(lon, lat, overlap_start, end)
        factor = precipitation_scale(merged["PRECTOTCORR"], current["PRECTOTCORR"], overlap_start, history_end)
        if factor != 1.0:
            log.warning("%s: current-year precipitation arrived scaled by %.0f - corrected", slug, factor)
        for p in config.POWER_PARAMETERS:
            for day, value in current[p].items():
                if day > history_end.strftime("%Y%m%d"):
                    if p == "PRECTOTCORR" and value is not None and value >= 0:
                        value = round(value / factor, 2)
                    merged[p][day] = value
        validate_power(slug, merged)
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = {"source": config.POWER_URL, "lon": lon, "lat": lat, "properties": {"parameter": merged}}
        dest.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return out


def precipitation_scale(history: dict[str, float], current: dict[str, float], start: date, end: date) -> float:
    """Ratio between the current-year response and trusted history on their overlapping days."""
    lo, hi = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    ratios = [
        current[d] / history[d]
        for d in history
        if lo <= d <= hi and d in current and history[d] is not None and history[d] > 0.5 and current[d] is not None
    ]
    if len(ratios) < 3:  # too few rainy days: fall back to totals, then to "no scaling"
        tot_h = sum(v for d, v in history.items() if lo <= d <= hi and v is not None and v >= 0)
        tot_c = sum(v for d, v in current.items() if lo <= d <= hi and v is not None and v >= 0)
        ratio = tot_c / tot_h if tot_h > 1.0 else 1.0
    else:
        ratio = float(sorted(ratios)[len(ratios) // 2])
    for known in KNOWN_SCALE_FACTORS:
        if abs(ratio / known - 1.0) < 0.05:
            return known
    raise RuntimeError(f"unexpected precipitation scale factor {ratio:.3f} between POWER requests")


def validate_power(slug: str, parameter: dict[str, dict[str, float]]) -> None:
    """Fail loudly if precipitation is physically implausible (catches unit/scaling errors)."""
    rain = {k: v for k, v in parameter["PRECTOTCORR"].items() if v is not None and v >= 0}
    if not rain:
        raise RuntimeError(f"{slug}: no precipitation values")
    if max(rain.values()) > MAX_DAILY_RAIN_MM:
        raise RuntimeError(f"{slug}: daily rainfall above {MAX_DAILY_RAIN_MM} mm - check units")
    by_year: dict[str, list[float]] = {}
    for day, value in rain.items():
        by_year.setdefault(day[:4], []).append(value)
    for year, values in by_year.items():
        if len(values) >= 360 and not (ANNUAL_RAIN_MM[0] <= sum(values) <= ANNUAL_RAIN_MM[1]):
            raise RuntimeError(f"{slug}: {year} rainfall {sum(values):.0f} mm outside {ANNUAL_RAIN_MM} - check units")


def fetch_all(refresh: bool = False) -> None:
    fetch_apy(refresh)
    fetch_boundaries(refresh)
    fetch_ibtracs(refresh)
    fetch_power(refresh)
