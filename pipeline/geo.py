"""District geometry: extract Odisha's 30 districts from geoBoundaries and compute centroids."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

import numpy as np

from . import config

log = logging.getLogger(__name__)

RAW_BOUNDARIES = config.RAW / "boundaries" / "geoBoundaries-IND-ADM2_simplified.geojson"
# Rough Odisha bounding box; used together with names so that same-named districts elsewhere
# in India can never be picked up by mistake.
ODISHA_BBOX = (81.3, 17.7, 87.6, 22.7)


def _rings(geometry: dict) -> list[list[np.ndarray]]:
    """Return polygons as lists of rings (exterior first), each an (n, 2) lon/lat array."""
    if geometry["type"] == "Polygon":
        polys = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polys = geometry["coordinates"]
    else:
        raise ValueError(f"unsupported geometry {geometry['type']}")
    return [[np.asarray(ring, dtype=float) for ring in poly] for poly in polys]


def _ring_area_centroid(ring: np.ndarray) -> tuple[float, float, float]:
    x, y = ring[:, 0], ring[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    a = cross.sum() / 2.0
    if abs(a) < 1e-12:
        return 0.0, float(x.mean()), float(y.mean())
    cx = ((x + x1) * cross).sum() / (6.0 * a)
    cy = ((y + y1) * cross).sum() / (6.0 * a)
    return abs(a), float(cx), float(cy)


def centroid(geometry: dict) -> tuple[float, float]:
    """Area-weighted centroid (lon, lat). Planar in degrees, which is fine at district scale."""
    total, sx, sy = 0.0, 0.0, 0.0
    for poly in _rings(geometry):
        for i, ring in enumerate(poly):
            a, cx, cy = _ring_area_centroid(ring)
            sign = 1.0 if i == 0 else -1.0  # holes subtract
            total += sign * a
            sx += sign * a * cx
            sy += sign * a * cy
    return sx / total, sy / total


def _in_bbox(lon: float, lat: float) -> bool:
    x0, y0, x1, y1 = ODISHA_BBOX
    return x0 <= lon <= x1 and y0 <= lat <= y1


@lru_cache(maxsize=1)
def odisha_features() -> tuple[dict, ...]:
    if not RAW_BOUNDARIES.exists():
        from .fetch import fetch_boundaries

        fetch_boundaries()
    data = json.loads(RAW_BOUNDARIES.read_text(encoding="utf-8"))
    found: dict[str, dict] = {}
    for feature in data["features"]:
        slug = config.slug_for(feature["properties"]["shapeName"], "geo")
        if slug is None:
            continue
        lon, lat = centroid(feature["geometry"])
        if not _in_bbox(lon, lat):
            continue
        if slug in found:
            raise ValueError(f"duplicate boundary for {slug}")
        found[slug] = feature
    missing = sorted(set(config.BY_SLUG) - set(found))
    if missing:
        raise ValueError(f"boundaries missing for districts: {missing}")
    return tuple(found[d.slug] for d in config.DISTRICTS)


def district_centroids() -> dict[str, tuple[float, float]]:
    return {d.slug: centroid(f["geometry"]) for d, f in zip(config.DISTRICTS, odisha_features(), strict=True)}


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return float(2 * 6371.0 * np.arcsin(np.sqrt(a)))


def nearest_neighbours(k: int = 5) -> dict[str, list[str]]:
    """The k nearest districts to each district, by centroid distance."""
    cents = district_centroids()
    out = {}
    for slug, (lon, lat) in cents.items():
        dists = sorted((haversine_km(lon, lat, lo, la), other) for other, (lo, la) in cents.items() if other != slug)
        out[slug] = [other for _, other in dists[:k]]
    return out


def _round_ring(ring: list, ndigits: int) -> list:
    out: list[list[float]] = []
    for lon, lat in ring:
        pt = [round(lon, ndigits), round(lat, ndigits)]
        if not out or pt != out[-1]:
            out.append(pt)
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def _round_geometry(geometry: dict, ndigits: int = 4) -> dict:
    if geometry["type"] == "Polygon":
        coords = [_round_ring(r, ndigits) for r in geometry["coordinates"]]
    else:
        coords = [[_round_ring(r, ndigits) for r in poly] for poly in geometry["coordinates"]]
    return {"type": geometry["type"], "coordinates": coords}


def write_district_files() -> None:
    """Write data/processed/districts.json and districts.geojson."""
    config.PROCESSED.mkdir(parents=True, exist_ok=True)
    feats, meta = [], []
    for d, f in zip(config.DISTRICTS, odisha_features(), strict=True):
        lon, lat = centroid(f["geometry"])
        feats.append(
            {
                "type": "Feature",
                "properties": {"slug": d.slug, "name": d.name},
                "geometry": _round_geometry(f["geometry"]),
            }
        )
        meta.append(
            {
                "slug": d.slug,
                "name": d.name,
                "aliases": sorted({d.upag, d.geo} - {d.name}),
                "lon": round(lon, 4),
                "lat": round(lat, 4),
                "coastal": d.coastal,
                "kbk": d.kbk,
            }
        )
    geo = {
        "type": "FeatureCollection",
        "attribution": "District boundaries: geoBoundaries (gbOpen IND ADM2, 2021), ODbL 1.0",
        "features": feats,
    }
    (config.PROCESSED / "districts.geojson").write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    (config.PROCESSED / "districts.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("wrote districts.json and districts.geojson (%d districts)", len(meta))
