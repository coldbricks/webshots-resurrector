"""Live ADS-B for the PPTY scope — public cooperative surveillance.

Primary:  adsb.lol  (rich: squawk, emergency, type, registration)
Fallback: OpenSky Network REST  (bbox, no key)

N90 / Long Island theater of ops. Guest rate — poll every ~12s, not a firehose.
Not certified surveillance. Not ATC. Just ghosts on glass with real lat/lon.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

UA = (
    "PaisleyPonytail/ADS-B "
    "(scope glass overlay; +https://github.com/coldbricks/paisley-ponytail)"
)

# Theater of ops — N90 coastal / Long Island (matches video map framing)
LAT_MIN, LAT_MAX = 40.35, 41.20
LON_MIN, LON_MAX = -74.40, -71.85
CENTER_LAT, CENTER_LON = 40.64, -73.78
DIST_NM = 85

# OpenSky state vector indices
# 0 icao24 1 callsign 2 origin 5 lon 6 lat 7 baro_alt 8 on_ground
# 9 velocity 10 true_track 11 vertical_rate 14 squawk 16 position_source 17 category


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json"},
        timeout=18.0,
        follow_redirects=True,
    )


def _norm_callsign(s: str | None) -> str:
    if not s:
        return "????"
    return s.strip().upper() or "????"


def _alt_fl(meters: float | None, feet: float | None = None) -> str:
    if feet is not None and feet == feet:  # not NaN
        try:
            ft = float(feet)
            if ft < 0:
                return "GND"
            if ft >= 18000:
                return f"FL{int(round(ft / 100)):03d}"
            return f"{int(round(ft))}"
        except (TypeError, ValueError):
            pass
    if meters is None:
        return "----"
    try:
        ft = float(meters) * 3.28084
        if ft < 50:
            return "GND"
        if ft >= 18000:
            return f"FL{int(round(ft / 100)):03d}"
        return f"{int(round(ft))}"
    except (TypeError, ValueError):
        return "----"


def _kt(ms: float | None = None, gs: float | None = None) -> str:
    if gs is not None:
        try:
            return f"{int(round(float(gs)))}"
        except (TypeError, ValueError):
            pass
    if ms is None:
        return "---"
    try:
        return f"{int(round(float(ms) * 1.94384))}"
    except (TypeError, ValueError):
        return "---"


def fetch_adsb_lol() -> tuple[list[dict[str, Any]], str]:
    """adsb.lol circle query — includes squawk & emergency."""
    url = f"https://api.adsb.lol/v2/lat/{CENTER_LAT}/lon/{CENTER_LON}/dist/{DIST_NM}"
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        data = r.json()
    ac_list = data.get("ac") or data.get("aircraft") or []
    out: list[dict[str, Any]] = []
    for a in ac_list:
        if not isinstance(a, dict):
            continue
        lat, lon = a.get("lat"), a.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not (LAT_MIN <= lat_f <= LAT_MAX and LON_MIN <= lon_f <= LON_MAX):
            # keep slightly outside for edge targets near map border
            if not (LAT_MIN - 0.15 <= lat_f <= LAT_MAX + 0.15 and LON_MIN - 0.15 <= lon_f <= LON_MAX + 0.15):
                continue
        alt_baro = a.get("alt_baro")
        on_gnd = alt_baro == "ground" or a.get("alt_baro") == 0 and a.get("gs", 1) == 0
        if alt_baro == "ground":
            alt_ft = 0.0
            on_gnd = True
        else:
            try:
                alt_ft = float(alt_baro) if alt_baro is not None else None
            except (TypeError, ValueError):
                alt_ft = None
        sq = str(a.get("squawk") or "").strip()
        emerg = str(a.get("emergency") or "none").lower()
        if emerg in ("", "none", "null"):
            emerg = None
        # Special squawks
        if sq in ("7700", "7600", "7500"):
            emerg = {"7700": "general", "7600": "radio", "7500": "unlawful"}.get(sq, "general")
        call = _norm_callsign(a.get("flight") or a.get("r") or a.get("hex"))
        track = a.get("track") or a.get("true_heading") or a.get("mag_heading")
        out.append({
            "id": a.get("hex") or call,
            "callsign": call,
            "lat": lat_f,
            "lon": lon_f,
            "alt": _alt_fl(None, alt_ft),
            "alt_ft": alt_ft if alt_ft is not None else -1,
            "gs": _kt(gs=a.get("gs")),
            "track": float(track) if track is not None else None,
            "squawk": sq or "----",
            "emergency": emerg,
            "on_ground": bool(on_gnd),
            "type": a.get("t") or a.get("desc") or "",
            "reg": a.get("r") or "",
            "source": "adsb.lol",
        })
    return out, "adsb.lol"


def fetch_opensky() -> tuple[list[dict[str, Any]], str]:
    """OpenSky bbox — solid fallback, 186+ targets common over N90."""
    params = {
        "lamin": LAT_MIN,
        "lomin": LON_MIN,
        "lamax": LAT_MAX,
        "lomax": LON_MAX,
    }
    with _client() as c:
        r = c.get("https://opensky-network.org/api/states/all", params=params)
        r.raise_for_status()
        data = r.json()
    states = data.get("states") or []
    out: list[dict[str, Any]] = []
    for s in states:
        if not s or len(s) < 8:
            continue
        lon, lat = s[5], s[6]
        if lon is None or lat is None:
            continue
        on_gnd = bool(s[8])
        baro = s[7]
        sq = (s[14] if len(s) > 14 else None) or ""
        emerg = None
        if str(sq) in ("7700", "7600", "7500"):
            emerg = {"7700": "general", "7600": "radio", "7500": "unlawful"}.get(str(sq))
        out.append({
            "id": s[0],
            "callsign": _norm_callsign(s[1]),
            "lat": float(lat),
            "lon": float(lon),
            "alt": _alt_fl(baro),
            "alt_ft": (float(baro) * 3.28084) if baro is not None else -1,
            "gs": _kt(ms=s[9]),
            "track": float(s[10]) if s[10] is not None else None,
            "squawk": str(sq) if sq else "----",
            "emergency": emerg,
            "on_ground": on_gnd,
            "type": "",
            "reg": "",
            "source": "opensky",
        })
    return out, "opensky"


def fetch_traffic() -> dict[str, Any]:
    """Pull live traffic. Prefer adsb.lol; fall back to OpenSky."""
    errors: list[str] = []
    for fetcher in (fetch_adsb_lol, fetch_opensky):
        try:
            ac, src = fetcher()
            return {
                "ok": True,
                "source": src,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "count": len(ac),
                "aircraft": ac,
                "error": None,
                "errors": errors,
            }
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
    return {
        "ok": False,
        "source": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": 0,
        "aircraft": [],
        "error": " | ".join(errors)[:300],
        "errors": errors,
    }


def geo_to_frac(lat: float, lon: float) -> tuple[float, float]:
    """Map lat/lon → (x_frac, y_frac) in 0–1 scope space (y north-up inverted for canvas)."""
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN)
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN)
    return x, y


def altitude_color(alt_ft: float, on_ground: bool) -> str:
    """Rough ERAM-ish altitude banding for the glass (HF palette)."""
    if on_ground or alt_ft < 0:
        return "#B3B3B3"  # gray
    if alt_ft < 3000:
        return "#23E162"  # green — low
    if alt_ft < 10000:
        return "#07CDED"  # aqua
    if alt_ft < 18000:
        return "#5E8DF6"  # blue
    if alt_ft < 35000:
        return "#DFF334"  # yellow high
    return "#D822FF"  # magenta — stratosphere toys
