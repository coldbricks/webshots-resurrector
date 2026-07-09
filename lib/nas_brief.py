"""Live NAS / weather brief for the scope position-relief board.

Public sources only:
  - METARs: https://aviationweather.gov/api/data/metar
  - Traffic flow / airport events: https://nasstatus.faa.gov/api/*
  - Human OIS page (reference): https://www.fly.faa.gov/ois/?legacy=true

Guest etiquette: short timeouts, identifiable User-Agent, no hammering.
Failures degrade to UNAVAILABLE lines — relief still proceeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

UA = (
    f"PaisleyPonytail/NAS-Brief "
    f"(photo recovery UI; +https://github.com/coldbricks/paisley-ponytail)"
)
OIS_URL = "https://www.fly.faa.gov/ois/?legacy=true"
NAS_API = "https://nasstatus.faa.gov/api"
METAR_API = "https://aviationweather.gov/api/data/metar"

# N90 / Long Island sector flavor — real station IDs for the video map
DEFAULT_STATIONS = ("KJFK", "KLGA", "KEWR", "KISP", "KTEB")


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json"},
        timeout=12.0,
        follow_redirects=True,
    )


def fetch_metars(stations: tuple[str, ...] = DEFAULT_STATIONS) -> list[dict[str, Any]]:
    """Return list of {id, raw, fltCat, summary} for each station."""
    out: list[dict[str, Any]] = []
    try:
        with _client() as c:
            r = c.get(
                METAR_API,
                params={"ids": ",".join(stations), "format": "json"},
            )
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list):
                rows = []
    except Exception as exc:
        return [{"id": "?", "raw": f"METAR UNAVAILABLE — {exc}", "fltCat": "?", "summary": str(exc)}]

    by_id = {row.get("icaoId"): row for row in rows if isinstance(row, dict)}
    for sid in stations:
        row = by_id.get(sid)
        if not row:
            out.append({"id": sid, "raw": f"{sid} — no observation", "fltCat": "?", "summary": "missing"})
            continue
        raw = row.get("rawOb") or ""
        cat = row.get("fltCat") or "?"
        wind = ""
        if row.get("wdir") is not None and row.get("wspd") is not None:
            wind = f"{row['wdir']:03.0f}@{row['wspd']}"
            if row.get("wgst"):
                wind += f"G{row['wgst']}"
        vis = row.get("visib")
        cover = row.get("cover") or ""
        temp = row.get("temp")
        dewp = row.get("dewp")
        bits = [cat]
        if wind:
            bits.append(wind)
        if vis is not None:
            bits.append(f"{vis}SM")
        if cover:
            bits.append(str(cover))
        if temp is not None:
            bits.append(f"{temp:.0f}°C" if isinstance(temp, (int, float)) else str(temp))
            if dewp is not None:
                bits[-1] += f"/{dewp:.0f}" if isinstance(dewp, (int, float)) else f"/{dewp}"
        out.append({
            "id": sid,
            "raw": raw,
            "fltCat": cat,
            "summary": " ".join(bits),
        })
    return out


def fetch_nas_status() -> dict[str, Any]:
    """Airport + en route events from public NAS status API (OIS-family data)."""
    result: dict[str, Any] = {
        "ok": False,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ois_url": OIS_URL,
        "airport_events": [],
        "enroute_events": [],
        "error": None,
    }
    try:
        with _client() as c:
            r_a = c.get(f"{NAS_API}/airport-events")
            r_a.raise_for_status()
            airports = r_a.json() if r_a.content else []
            r_e = c.get(f"{NAS_API}/enroute-events")
            enroute = r_e.json() if r_e.status_code == 200 and r_e.content else []
        result["airport_events"] = airports if isinstance(airports, list) else []
        result["enroute_events"] = enroute if isinstance(enroute, list) else []
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)[:200]
    return result


def _event_blurb(ev: dict) -> str | None:
    """Human one-liner from an airport-events record."""
    aid = ev.get("airportId") or "?"
    parts: list[str] = []
    for key, label in (
        ("groundStop", "GROUND STOP"),
        ("groundDelay", "GDP"),
        ("airportClosure", "CLOSURE"),
        ("arrivalDelay", "ARR DELAY"),
        ("departureDelay", "DEP DELAY"),
    ):
        block = ev.get(key)
        if not block or not isinstance(block, dict):
            continue
        reason = block.get("reason") or ""
        ad = block.get("arrivalDeparture") or {}
        rng = ""
        if isinstance(ad, dict):
            mn, mx = ad.get("min"), ad.get("max")
            if mn or mx:
                rng = f" {mn or '?'}–{mx or '?'}"
            trend = ad.get("trend")
            if trend:
                rng += f" ({trend})"
        parts.append(f"{label}{rng}" + (f" — {reason}" if reason else ""))
    ff = ev.get("freeForm")
    if isinstance(ff, dict) and ff.get("simpleText"):
        txt = str(ff["simpleText"]).replace("\n", " ")
        parts.append(txt[:120] + ("…" if len(txt) > 120 else ""))
    if not parts:
        return None
    return f"{aid}: " + " | ".join(parts)


def format_relief_board(
    metars: list[dict[str, Any]] | None = None,
    nas: dict[str, Any] | None = None,
    initials: str = "??",
    version: str = "?",
) -> str:
    """Full JO 7110.65 App A–structured position relief board (public SOP).

    Includes live METAR + NAS/OIS traffic-flow status. Ridiculous on purpose.
    """
    if metars is None:
        metars = fetch_metars()
    if nas is None:
        nas = fetch_nas_status()

    zulu = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    lines: list[str] = []
    L = lines.append

    L("=" * 72)
    L("POSITION RELIEF BRIEFING  ·  JO 7110.65 APPENDIX A")
    L("STANDARD OPERATING PRACTICE — TRANSFER OF POSITION RESPONSIBILITY")
    L(f"PPTY SECTOR ARCHIVE  ·  PYSLY-R90  ·  {zulu}  ·  RELIEVING: {initials}  ·  v{version}")
    L("SECTOR BOARD  PORTR-R41 · PYSLY-R90 · RACHL-R67 · TAMMY-R11 · RILEY-R28 · …")
    L("=" * 72)
    L("")
    L("PRECAUTIONS (App A §4)")
    L("  [X] Do not rush the relief.")
    L("  [X] Status items recorded as soon as operationally feasible.")
    L("  [X] Simultaneous reliefs (combine/decombine) approached with caution.")
    L("")
    L("RESPONSIBILITIES (App A §5)")
    L("  [X] Specialist being relieved: pertinent status displayed or relayed.")
    L("  [X] Relieving specialist: unresolved questions resolved BEFORE accept.")
    L("  [X] EQUAL responsibility for completeness and accuracy of this brief.")
    L("  [X] Relief conducted at the position (unless ATM-authorized otherwise).")
    L("")
    L("-" * 72)
    L("6.a  PREVIEW THE POSITION  (relieving specialist)")
    L("-" * 72)
    L("  [X] 1. Follow checklist / review Status Information Area (SIA).")
    L("  [X] 2. Observe position equipment, operational situation, work environment.")
    L("  [X] 3. Listen to voice communications / observe operational actions.")
    L("  [X] 4. Observe current & pending traffic; correlate with flight data.")
    L("  [X] 5. Indicate preview complete — verbal briefing may begin.")
    L("")
    L("  SIA — EQUIPMENT / AUTOMATION")
    L(f"      SCOPE GLASS .......... ONLINE  (STARS/ERAM presentation · v{version})")
    L("      WAYBACK RADAR ........ ONLINE  (guest rate ~1/s · archive.org host)")
    L("      HF-STD-010A PALETTE .. LOADED  (#23E162 scope green · AM-20/08 T1)")
    L("      VIDEO MAP ............ N90 / W-105A / W-105B / W-106 / Y483")
    L("      STROBE / TRAFFIC ..... ACTIVE  (ambient + optional live ADS-B)")
    L("      ARTCC RINGER ......... ARMED   (assets/artcc_ringer.wav)")
    L("      CEDAR LOGIN .......... LEVEL 2 (presentation only · not real CEDAR)")
    L("")
    L("  SIA — CHANNELIZATION (dual-channel + tertiary hot spare)")
    L("      CHANNEL A ............ ACTIVE     ·  health NORM  ·  primary string")
    L("      CHANNEL B ............ STANDBY    ·  health NORM  ·  hot backup")
    L("      CHANNEL C ............ HOT SPARE  ·  tertiary     ·  failover armed")
    L("      SYNC .................. OK  ·  redundant pair  ·  click lamps to force switch")
    L("      (NAS automation class systems run dual-channel; tertiary = spare string.)")
    L("")
    L("  SIA — WORKING PRIORITIES (trainer mantra — does not move)")
    L("      1. AVIATE ........ protect the flight / what already landed")
    L("      2. NAVIGATE ...... know the route before you commit (search → pull)")
    L("      3. COMMUNICATE ... then talk — short, true status")
    L("      RESOLVE CONFLICTS WITH MULTIPLE PLANS — Plan A, Plan B, an out.")
    L("      (FS → PH → TH. If the approach fails: go around. Wreckage remains.)")
    L("")
    L("  SIA — VSCS (Voice Switching and Control System) — MOCK LANDLINE PANEL")
    L("      P/CG: computer-controlled switching for all voice circuits (A/G + G/G).")
    L("      Status ............. ONLINE (presentation only — no live circuits)")
    L("      Keylines ........... JFK/LGA/EWR/TEB/ISP/HPN TWR · N90 APP/DEP")
    L("                          ZNY/ZBW/ZDC/ZOB · ATCSCC · CIC · TMU · FD · EMERG")
    L("      Interphone ........ monitor continuously; terminate with operating initials")
    L("      (JO 7110.10 §2-2: LINE CLEAR? · facility ID · go ahead · initials)")
    L("")
    L("  SIA — OCEANIC COMS  ·  ZWY (NEW YORK OCEANIC) — MOCK")
    L("      ADS-C ............. LOGGED ON  ·  contracts / position reports")
    L("      CPDLC ............. ACTIVE     ·  FANS-1/A data authority")
    L("      SATCOM ............ UP         ·  primary voice/data (modern oceanic)")
    L("      HF ................ STANDBY    ·  classic backup · ARINC family")
    L("      ARINC ............. MONITOR    ·  G/G relay flavor")
    L("      Theater ........... WATRS / NAT · Y483 on video map · not live circuits")
    L("")
    L("  SIA — SPECIAL ACTIVITY / WARNING AREAS (Status Information Area)")
    L("      Status legend:  HOT = active/in use    COLD = inactive (dim on glass)")
    L("      ┌──────────┬────────┬─────────────────────────────────────────┐")
    L("      │ AREA     │ STATUS │ REMARKS                                 │")
    L("      ├──────────┼────────┼─────────────────────────────────────────┤")
    L("      │ W-105A   │ COLD   │ Warning Area · coastal · not active     │")
    L("      │ W-105B   │ COLD   │ Warning Area · coastal · not active     │")
    L("      │ W-106    │ COLD   │ Warning Area · coastal · not active     │")
    L("      │ Y483     │ OPEN   │ Oceanic track depiction (chart only)    │")
    L("      └──────────┴────────┴─────────────────────────────────────────┘")
    L("      All W-areas cold this relief — painted cool/dim on the video map.")
    L("      (If an area went HOT it would light amber/red on the SIA and map.)")
    L("")
    L("-" * 72)
    L("6.b  VERBAL BRIEFING  (specialist being relieved → relieving)")
    L("-" * 72)
    L("  [X] 1. Abnormal status / items of special interest not on SIA.")
    L("         → None recorded for this recovery sector (photo ops only).")
    L("  [X] 2. Reported weather and other weather-related information.")
    L("  [X] 3. Traffic (if applicable).")
    L("  [X] 4. Communication status of known aircraft (VCI N/A — not ERAM ops).")
    L("  [X] 5–6. Questions resolved; answers complete.")
    L("")
    L("  WEATHER — LIVE METAR (aviationweather.gov)")
    L("  Source: GET /api/data/metar  ·  stations N90 area")
    for m in metars:
        L(f"      {m['id']:<5}  [{m.get('fltCat', '?'):<4}]  {m.get('summary', '')}")
        raw = m.get("raw") or ""
        if raw and not raw.startswith(m["id"][:1] if False else ""):
            pass
        if raw:
            # wrap raw metar
            L(f"             {raw[:70]}")
            if len(raw) > 70:
                L(f"             {raw[70:140]}")
    L("")
    L("  TRAFFIC FLOW / TM — LIVE NAS STATUS (public OIS family)")
    L(f"  Human board: {OIS_URL}")
    L(f"  Machine API: {NAS_API}/airport-events  (+ enroute-events)")
    if nas.get("ok"):
        L(f"  Fetched:     {nas.get('fetched_at')}  ·  STATUS OK")
        # NY metro first, then others with content
        events = nas.get("airport_events") or []
        ny = {"JFK", "LGA", "EWR", "TEB", "ISP", "HPN", "NYC", "N90"}
        blurbs: list[str] = []
        for ev in events:
            b = _event_blurb(ev)
            if not b:
                continue
            aid = (ev.get("airportId") or "").upper()
            blurbs.append((0 if aid in ny else 1, b))
        blurbs.sort()
        if blurbs:
            L(f"  Active airport events with content: {len(blurbs)}")
            for _, b in blurbs[:18]:
                L(f"      · {b[:68]}")
                if len(b) > 68:
                    L(f"        {b[68:136]}")
        else:
            L("      · No non-null delay/stop/closure fields in current airport-events feed")
            L(f"      · Feed length: {len(events)} airport rows (many idle)")
        enr = nas.get("enroute_events") or []
        if enr:
            L(f"  En route events: {len(enr)}")
            for e in enr[:8]:
                L(f"      · {str(e)[:70]}")
        else:
            L("  En route events: NONE ACTIVE (API empty list)")
    else:
        L(f"  NAS STATUS UNAVAILABLE — {nas.get('error') or 'unknown'}")
        L(f"  CHECK MANUALLY: {OIS_URL}")
    L("")
    L("  TRAFFIC (sector metaphor — recovery, not radar tracks)")
    L("      Pending pulls ........ per hangar / callsign queue")
    L("      Ambient strobes ...... display only (not live surveillance)")
    L("      Archive Team haul .... 2,437 megawarcs / 105.9 TB on frequency")
    L("")
    L("-" * 72)
    L("6.c  ASSUMPTION OF POSITION RESPONSIBILITY")
    L("-" * 72)
    L("  Relieving specialist will state: position responsibility ASSUMED.")
    L("  Specialist being relieved will RELEASE the position and note the time.")
    L("")
    L("-" * 72)
    L("6.d  REVIEW THE POSITION  (after transfer — continuous)")
    L("-" * 72)
    L("  [ ] Verify/update information from 6.a and 6.b")
    L("  [ ] Check position equipment per directives")
    L("  [ ] Review checklist / SIA / written notes; advise of omissions")
    L("  [ ] Observe overall operation — assist if needed")
    L("  [ ] Sign-on relieving specialist with time of assumption")
    L("  [ ] Sign-off complete")
    L("")
    L("=" * 72)
    L("TYPE INITIALS AGAIN TO ACCEPT SECTOR RESPONSIBILITY")
    L("(Equal responsibility for completeness and accuracy of this brief.)")
    L("=" * 72)
    return "\n".join(lines)


def build_live_brief(initials: str = "??", version: str = "?") -> str:
    """Fetch live data and format the board (blocking — call off UI thread)."""
    metars = fetch_metars()
    nas = fetch_nas_status()
    return format_relief_board(metars, nas, initials=initials, version=version)
