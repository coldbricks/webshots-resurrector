"""N90 theater videomap — load + project public geography for the scope glass.

MIT-clean. Hand-authored JSON under assets/videomap/.
NOT derived from vice (GPL-3.0) or any facility mappack.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "assets", "videomap", "n90.json")

# Keep in lockstep with lib.adsb_feed theater defaults
_DEFAULT_BBOX = {
    "lat_min": 40.35,
    "lat_max": 41.20,
    "lon_min": -74.40,
    "lon_max": -71.85,
}


@lru_cache(maxsize=2)
def load_videomap(path: str | None = None) -> dict[str, Any]:
    p = path or _DEFAULT_PATH
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if "bbox" not in data:
        data["bbox"] = dict(_DEFAULT_BBOX)
    return data


def geo_to_frac(
    lat: float,
    lon: float,
    bbox: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Map lat/lon → (x_frac, y_frac) in 0–1 scope space (y north-up inverted)."""
    b = bbox or _DEFAULT_BBOX
    x = (lon - b["lon_min"]) / (b["lon_max"] - b["lon_min"])
    y = (b["lat_max"] - lat) / (b["lat_max"] - b["lat_min"])
    return x, y


def frac_to_px(xf: float, yf: float, w: int, h: int) -> tuple[float, float]:
    return xf * w, yf * h


def project_point(
    lat: float,
    lon: float,
    w: int,
    h: int,
    bbox: dict[str, float] | None = None,
) -> tuple[float, float]:
    xf, yf = geo_to_frac(lat, lon, bbox)
    return frac_to_px(xf, yf, w, h)
