"""Terminal display layer for Webshots Resurrector.

Tower-cab aesthetic: Zulu-clock comms log, flight strips, radar-green
scope colors, N90 video map.  Every line still says what it means —
jargon decorates, it never obscures.  First open should feel like
walking into a live TRACON at night.
"""

import sys
import time
from datetime import datetime, timezone

# Windows consoles default to a legacy codepage (cp1252) that can't encode
# the banner's block glyphs; force UTF-8 before rich binds to the streams.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    BarColumn,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.spinner import SPINNERS
from rich.theme import Theme

from lib import __version__

# Distant-traffic anti-collision strobe: quick double-pulse, then dark.
# Runs as the spinner wherever the tool is working — like watching a
# far-off aircraft hold over the water at night.
SPINNERS["strobe"] = {
    "interval": 100,
    "frames": ["✸", "✦", "·", " ", "✸", "✦", "·", " ",
               " ", " ", " ", " ", " ", " ", " ", " "],
}

# FAA standard ATC display palette — hex codes copied from Table 1
# (Foreground Colors) of DOT/FAA/AM-20/08, *Evaluation of a New Color
# Palette for ATC Displays* (Gildea et al., Sept 2020). That report
# evaluates HF-STD-010 / HF-STD-010A on ERAM and STARS; the revised
# Red (ARTS/STARS, not the "too pink" original) is what shipped in
# HF-STD-010A (2020). Table 2 in the same report is weather colors —
# we do not use those here. Local source file often named
# dot_57391_DS1.pdf (NTL/DOT handle for AM-20/08).
# When LANDED prints green, that is #23E162 — scope green.
HF = {
    "white": "#FFFFFF",   # FFFFFF
    "pink": "#F684D8",    # F684D8
    "gray": "#B3B3B3",    # B3B3B3
    "blue": "#5E8DF6",    # 5E8DF6
    "orange": "#FE930D",  # FE930D
    "red": "#FF1320",     # FF1320  (HF-STD-010A revised Red)
    "green": "#23E162",   # 23E162
    "yellow": "#DFF334",  # DFF334
    "magenta": "#D822FF", # D822FF
    "aqua": "#07CDED",    # 07CDED
    "brown": "#C5955B",   # C5955B
}

THEME = Theme(
    {
        "phase": f"bold {HF['green']}",
        "ok": f"bold {HF['green']}",
        "warn": f"bold {HF['yellow']}",
        "err": f"bold {HF['red']}",
        "dim": "dim",
        "target": f"bold {HF['white']}",
        "heading": f"bold {HF['white']}",
        "scope": HF["green"],
        "amber": HF["orange"],
        "zulu": f"dim {HF['green']}",
        "strip": f"bold black on {HF['green']}",
        "brand": f"bold {HF['white']}",
        "deep": f"bold {HF['magenta']}",
        "ident": f"bold {HF['aqua']}",
        "trace": f"bold {HF['blue']}",
        # Sectional-chart backdrop: barely-there green, under the black.
        "chart": "#20362a",
        "chartlabel": "#3d6b4a",
        "chartfix": f"bold {HF['green']}",
        "chartwarn": f"dim {HF['yellow']}",
        "chartcoast": "#2a4a35",
        "datablock": f"dim {HF['aqua']}",
    }
)

# record=True feeds the flight recorder. Pulls save a session log so
# support reports arrive with the full transcript attached.
console = Console(theme=THEME, highlight=False, record=True)

VERSION = __version__


def _zulu() -> str:
    """Tower clock: every transmission gets a Zulu timestamp."""
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


# ── Banner ──────────────────────────────────────────────────────────────

LOGO_PAISLEY = (
    "  [phase]█▀█ █▀█ █ █▀▀ █   █▀▀ █ █[/]\n"
    "  [phase]█▀▀ █▀█ █ ▀▀█ █   █▀▀ ▀█▀[/]\n"
    "  [phase]▀   ▀ ▀ ▀ ▀▀▀ ▀▀▀ ▀▀▀  ▀ [/]"
)

LOGO_PONYTAIL = (
    "  [brand]█▀█ █▀█ █▀█ █ █ ▀█▀ █▀█ █ █  [/]\n"
    "  [brand]█▀▀ █ █ █ █ ▀█▀  █  █▀█ █ █  [/]\n"
    "  [brand]▀   ▀▀▀ ▀ ▀  ▀   ▀  ▀ ▀ ▀ ▀▀▀[/]"
)

SCANLINE = "[zulu]" + "▔" * 68 + "[/]"

# Video map — N90 / Long Island south shore, drawn like a STARS scope
# at night: faint chart under black, real fixes, real warning areas,
# oceanic tracks.  Not a real facility product.  Just how this cab sees
# the world.  Fixes: LGA EWR JFK DPK ISP CCC HTO MONTK; water: CAMRN
# SHIPP MONEY; W-105A/B W-106; Y483.  ✦ / datablocks = distant traffic.
# Free-floating video map (no inner box — markup + double-line frames fight
# each other on Windows). Reads like a STARS chart under the black.
VIDEOMAP = """\
  [chartfix]N90 NEW YORK TRACON[/][chart]  ·  VIDEO MAP  ·  IFR  ·  RNG 60 NM  ·  [/][chartfix]BRIGHT[/]
  [chartcoast]              ~ ~  L O N G  I S L A N D  S O U N D  ~ ~[/]
  [chartfix]  ●LGA[/]
  [chartfix] ●EWR[/][chart]   ╲[/]
  [chart]        ╲    [/][chartfix]●JFK[/][chart]······[/][chartfix]DPK[/][chart]····[/][chartfix]ISP[/][chart]····[/][chartfix]CCC[/][chart]····[/][chartfix]HTO[/][chart]····[/][chartfix]MONTK[/]
  [chart]         ╲___˙·¸¸.·‾‾·¸¸.·‾‾‾·¸¸.·‾‾·¸¸.·‾‾·¸¸.·˙[/]  [chartlabel]LONG ISLAND[/]
  [chart]          ·[/][chartfix]CAMRN[/][chart]       ·[/][chartfix]SHIPP[/][chart]         ·[/][chartfix]MONEY[/][chart]      [/][datablock]✦ AAL114[/]
  [chart]           ╲           ·              ·             [/][datablock]JBU1804[/]
  [chart]  ──────────[/][dim]╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍[/][chart]───[/][chartfix]Y483[/][chart]⟶ OCA[/]
  [chart]            [/][dim]╏[/][chart]              [/][dim]╏[/][chart]             [/][dim]╏[/]
  [chart]            [/][dim]╏[/]  [dim]W-105A COLD[/] [dim]╏[/]  [dim]W-105B COLD[/] [dim]╏[/]  [dim]W-106 COLD[/]
  [chart]            [/][dim]╏[/][chart]              [/][dim]╏[/][chart]             [/][dim]╏[/]
  [chart]  ──────────[/][dim]╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍╍[/][chart]──────────────[/]
  [chartcoast]                 ~ ~ ~   A T L A N T I C   ~ ~ ~[/]
  [datablock]  B6  DAL488  350C  .N0XE                 AWE123  310C[/]
  [dim]  W-AREAS COLD  ·  COASTAL IFR  ·  GUEST ON THIS FREQUENCY[/]"""
def _scope_boot():
    """Cold-start power-on — only for the first impression (wizard / no-args)."""
    lines = [
        ("[zulu]◈[/]  [dim]PPTY SCOPE[/]              [scope]INITIALIZING…[/]", 0.04),
        ("[zulu]◈[/]  [dim]HF-STD-010A PALETTE[/]     [ok]LOADED[/]  [dim]#23E162 SCOPE GREEN[/]", 0.04),
        ("[zulu]◈[/]  [dim]VIDEO MAP[/]               [ok]N90 / W-105 / W-106[/]", 0.04),
        ("[zulu]◈[/]  [dim]WAYBACK RADAR[/]           [ok]ONLINE[/]  [dim]2,437 MEGAWARCS[/]", 0.05),
        ("[zulu]◈[/]  [dim]GUEST RATE[/]              [scope]~1 REQ/S[/]  [dim]ARCHIVE.ORG HOST[/]", 0.04),
        ("[zulu]◈[/]  [ok]RADAR CONTACT[/]           [brand]YOU HAVE THE POSITION[/]", 0.06),
    ]
    console.print()
    for line, delay in lines:
        console.print(f"  {line}")
        try:
            time.sleep(delay)
        except Exception:
            pass
    console.print()


def show_banner(*, cold_start: bool = False):
    """Paint the cab. cold_start=True adds the power-on sequence (wizard)."""
    if cold_start and sys.stdout.isatty():
        _scope_boot()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    zulu = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    body = (
        f"[strip] PPTY TWR [/] [dim]│[/] [ident]SECTOR ARCHIVE[/] [dim]│[/] "
        f"[scope]WAYBACK RADAR[/] [dim]│[/] [zulu]{zulu}[/] [dim]│[/] "
        f"[brand]v{VERSION}[/]\n\n"
        f"{LOGO_PAISLEY}\n"
        f"{LOGO_PONYTAIL}\n\n"
        f"  {SCANLINE}\n"
        f"  [scope]THE WEBSHOTS RESURRECTOR[/]  [dim]▪[/]  "
        f"[brand]ARCHIVE PHOTO RECOVERY SYSTEM[/]\n"
        f"  [dim]2,437 MEGAWARCS ON FREQUENCY[/]  [dim]▪[/]  "
        f"[dim]105.9 TB[/]  [dim]▪[/]  [ok]RADAR ONLINE[/]\n"
        f"  {SCANLINE}\n"
        f"  [brand]TAILSTRIKE STUDIOS[/] [dim]×[/] [brand]ASH AIRFOIL[/]"
        f" [dim]// coldbricks // {now}[/]\n\n"
        f"{VIDEOMAP}"
    )
    console.print()
    console.print(
        Panel(
            body,
            border_style=HF["green"],
            box=box.DOUBLE,
            padding=(1, 1),
            title="[bold black on #23E162] ■ SCOPE LIVE ■ [/]",
            title_align="left",
            subtitle="[dim]not FAA equipment  ·  just how this hangar sees the wreck[/]",
            subtitle_align="right",
        )
    )
    console.print()


def show_atis():
    """Session ATIS — four lines max. Not an FAA product; product fiction PPTY."""
    # INFO letter advances with the minor version digit so it changes on release.
    try:
        letter = chr(ord("A") + (int(VERSION.split(".")[-1]) % 26))
    except (ValueError, IndexError):
        letter = "A"
    zulu = datetime.now(timezone.utc).strftime("%d%H%MZ")
    console.print(
        Panel(
            f"[zulu]ATIS PPTY INFO {letter}  {zulu}[/]\n"
            f"[scope]PPTY TWR[/] [dim]—[/] [brand]PAISLEY PONYTAIL[/] "
            f"[scope]v{VERSION}[/]\n"
            f"[dim]WX:[/] [scope]WAYBACK RADAR ONLINE[/] [dim]·[/] "
            f"[scope]RATE GUEST ~1/S[/] [dim]·[/] [ok]CEILING UNLIMITED[/]\n"
            f"[amber]RMK/[/] [dim]VPN EXITS EXPECT FLOW CONTROL · "
            f"PHOTOS STAY ON YOUR MACHINE · BE KIND TO THE ARCHIVE[/]",
            border_style=f"dim {HF['green']}",
            box=box.SQUARE,
            padding=(0, 1),
            title="[dim]ATIS[/]",
            title_align="left",
        )
    )
    console.print()


def show_front_door():
    """Terminal INTRO — weight without announcing the weight."""
    console.print(
        Panel(
            "[brand]There is a photo that should not be gone.[/]\n\n"
            "[dim]Birthday. Band practice. Someone who isn't around anymore.\n"
            "Webshots. For a lot of families — the only copy left anywhere.[/]\n\n"
            "[err]01 DEC 2012 — they deleted everything.[/]\n"
            "[dim]105.9 TB hauled into the archive. The door broke. Most people stopped.[/]\n\n"
            "[ok]The photos are still in there.[/]\n"
            "[scope]You are going in after them.[/]\n\n"
            "[brand]Busiest air traffic control radar facility on the planet.[/]\n"
            "[dim]Traffic is not airplanes. Traffic is only copies.[/]\n"
            "[ident]The only person who can save these photos is you.\n"
            "Good luck. We're all counting on you.[/]\n\n"
            "[warn]AVIATE · NAVIGATE · COMMUNICATE[/]\n"
            "[dim]Multiple plans. Always an out. FS → PH → TH. Go around if you have to.[/]\n\n"
            "[dim]Screen name below · empty line closes · scope: python resurrector.py scope[/]",
            border_style=HF["aqua"],
            box=box.HEAVY,
            padding=(1, 2),
            title="[bold black on #07CDED] PPTY  ·  SECTOR ARCHIVE [/]",
            title_align="left",
        )
    )
    console.print()


def show_relief_preview(username: str, sia: dict | None):
    """PREVIEW + BRIEF + ASSUME for a hot hangar; cold hangar gets one line."""
    if not sia:
        phase("RELIEF", f"cold hangar — first approach for [target]{username}[/]")
        return
    phase(
        "RELIEF",
        f"PREVIEW  hangar hot for [target]{username}[/]",
    )
    detail(
        f"[dim]SIA:[/] [ok]{sia.get('fs', 0)}[/] FS  "
        f"[amber]{sia.get('ph', 0)}[/] PH  "
        f"[amber]{sia.get('th', 0)}[/] TH  "
        f"[dim]{sia.get('fs404', 0)} fs404  "
        f"{sia.get('upgradeable', 0)} upgrade candidates[/]"
    )
    ver = sia.get("prior_version") or "?"
    grade = sia.get("prior_grade") or "—"
    intr = "yes" if sia.get("interrupted") else "no"
    detail(
        f"[dim]last pull v{ver} · grade {grade} · interrupted={intr} · "
        f"{sia.get('albums', 0)} albums on strip[/]"
    )
    phase("RELIEF", "BRIEF    resuming approach — AT GATE holds, upgrades still airborne")
    success("RELIEF", "ASSUME   [bold]YOU HAVE THE POSITION[/] — continuing recovery")


def show_relief_review(before: dict | None, after_counts: dict):
    """REVIEW after pull — what changed on the scope."""
    if not before:
        return
    bfs, bph, bth = before.get("fs", 0), before.get("ph", 0), before.get("th", 0)
    afs = after_counts.get("fs", 0)
    aph = after_counts.get("ph", 0)
    ath = after_counts.get("th", 0)
    dfs, dph, dth = afs - bfs, aph - bph, ath - bth
    phase(
        "RELIEF",
        f"REVIEW   [ok]{dfs:+d}[/] FS  [amber]{dph:+d}[/] PH  "
        f"[amber]{dth:+d}[/] TH  since briefing",
    )


# ── Comms log ───────────────────────────────────────────────────────────
#
#  Every line reads like a tower transmission:
#    21:04:11Z  RECON  ▸ radar contact: bexbee12


def _xmit(style: str, tag: str, msg: str):
    console.print(f" [zulu]{_zulu()}[/]  [{style}]{tag:<5}[/] [dim]▸[/] {msg}")


def phase(tag, msg):
    # DEEP wears TRACON magenta (special condition); SWEEP wears beacon
    # aqua; TRACE (social graph) wears datablock blue.
    style = {"DEEP": "deep", "SWEEP": "ident", "TRACE": "trace"}.get(tag, "phase")
    _xmit(style, tag, msg)


def success(tag, msg):
    _xmit("ok", tag, msg)


def warn(tag, msg):
    _xmit("warn", tag, msg)


def fail(tag, msg):
    _xmit("err", tag, msg)


def detail(msg):
    console.print(f"                    {msg}")


def ident_status(target):
    """Blinking SQUAWK IDENT while we interrogate the archive's radar.

    Terminals without blink support render it steady — still correct,
    just less fun.
    """
    return console.status(
        f"[blink ident]■ SQUAWK IDENT ■[/] "
        f"[dim]interrogating[/] [target]{target}[/] [dim]— awaiting reply[/]",
        spinner="strobe",
        spinner_style=HF["white"],
    )


# ── Download callouts ───────────────────────────────────────────────────
#
#  fs  = full-size original landed        → LANDED  FS
#  ph  = 800x600 fallback landed          → LANDED  PH
#  skip = already on disk                 → AT GATE
#  fail = both variants unrecoverable     → MISSED APCH


def _datablock(caption=None, strip=None, pid=None, filename=None):
    """Secondary datablock fields — caption · strip · id — scannable, one line."""
    bits = []
    if caption:
        bits.append(str(caption)[:36])
    if strip:
        bits.append(f"strip {strip}")
    tail = pid or filename or ""
    if tail:
        bits.append(str(tail)[:28])
    return "  [dim]" + "  ·  ".join(bits) + "[/]" if bits else ""


def dl_ok(variant, size, filename, caption=None, strip=None, pid=None):
    if variant == "fs":
        v = "[ok]LANDED  FS[/]"
    else:
        v = "[amber]LANDED  PH[/]"
    console.print(
        f" [zulu]{_zulu()}[/]   {v}  {size:>9,}B"
        f"{_datablock(caption, strip, pid, filename)}"
    )


def dl_skip(filename, caption=None, strip=None, pid=None):
    console.print(
        f" [zulu]{_zulu()}[/]   [dim]AT GATE[/]      already on disk"
        f"{_datablock(caption, strip, pid, filename)}"
    )


def dl_thumb(size, filename, caption=None, strip=None, pid=None):
    console.print(
        f" [zulu]{_zulu()}[/]   [amber]THUMB ONLY[/]  {size:>9,}B"
        f"{_datablock(caption, strip, pid, filename)}"
        f"  [dim](full image never archived)[/]"
    )


def dl_upgrade(size, filename, caption=None, strip=None, pid=None):
    console.print(
        f" [zulu]{_zulu()}[/]   [ok]UPGRADED FS[/] {size:>9,}B"
        f"{_datablock(caption, strip, pid, filename)}"
        f"  [dim](replaced 800x600 with original)[/]"
    )


def dl_fail(filename, caption=None, strip=None, pid=None, reason=None):
    why = f"  [dim]{reason}[/]" if reason else "  [dim]not recoverable[/]"
    console.print(
        f" [zulu]{_zulu()}[/]   [err]MISSED APCH[/]"
        f"{why}"
        f"{_datablock(caption, strip, pid, filename)}"
    )


# ── Flight strips (album table) ─────────────────────────────────────────


def show_albums_table(albums):
    """Display album scan results as a flight-strip board.

    albums: list of (url, category, photo_count, title)
    """
    table = Table(
        show_header=True,
        header_style="strip",
        padding=(0, 1),
        border_style=f"dim {HF['green']}",
        box=box.HEAVY_HEAD,
        title="[phase]▮▮ FLIGHT STRIPS — ALBUMS ON SCOPE ▮▮[/]",
        title_justify="left",
    )
    table.add_column("STRIP", style="dim", width=5, justify="right")
    table.add_column("ALBUM", style="bold white", max_width=30)
    table.add_column("SQUAWK · ID", style="scope", max_width=20)
    table.add_column("SECTOR", style="phase", max_width=14)
    table.add_column("PHOTOS", style="bold white", justify="right", width=7)

    for i, (url, category, count, title) in enumerate(albums, 1):
        album_id = url.split("/album/")[1] if "/album/" in url else url[-30:]
        table.add_row(
            f"{i:03d}",
            (title or "—")[:30],
            album_id[:20],
            category[:14].upper(),
            str(count),
        )

    console.print(table)


def show_callsigns_table(rows, total_found, remarks=None):
    """Display username-sweep results.

    rows: list of {name, pages, first, last} dicts, already ordered.
    remarks: {name_lower: {rmk, ...}}; adds an RMK/ column when any
    shown name carries one.
    """
    remarks = remarks or {}
    has_rmk = any(r["name"].lower() in remarks for r in rows)
    table = Table(
        show_header=True,
        header_style="strip",
        padding=(0, 1),
        border_style=f"dim {HF['green']}",
        box=box.HEAVY_HEAD,
        title="[ident]▮▮ CALLSIGNS ON FREQUENCY ▮▮[/]",
        title_justify="left",
    )
    table.add_column("STRIP", style="dim", width=5, justify="right")
    table.add_column("SCREEN NAME", style="bold white", max_width=32)
    table.add_column("ARCHIVED PAGES", style="scope", justify="right", width=14)
    table.add_column("FIRST SEEN", style="dim", width=10)
    table.add_column("LAST SEEN", style="dim", width=10)
    if has_rmk:
        table.add_column("RMK/", style="amber", max_width=24)

    def _d(ts):
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if len(ts) >= 8 else ts

    for i, r in enumerate(rows, 1):
        cells = [
            f"{i:03d}", r["name"][:32], str(r["pages"]), _d(r["first"]), _d(r["last"])
        ]
        if has_rmk:
            entry = remarks.get(r["name"].lower())
            cells.append((entry["rmk"] if entry else "")[:24])
        table.add_row(*cells)
    console.print(table)
    if total_found > len(rows):
        console.print(
            f"         [dim]{total_found - len(rows)} more matches not shown — "
            f"narrow the prefix or raise -n[/]"
        )


def show_contacts_table(rows, owner, remarks=None):
    """Display associated-traffic (friends & fans) results.

    rows: list of {name, hits, lists} dicts, already ordered.
    """
    remarks = remarks or {}
    has_rmk = any(r["name"].lower() in remarks for r in rows)
    table = Table(
        show_header=True,
        header_style=f"bold black on {HF['blue']}",
        padding=(0, 1),
        border_style=f"dim {HF['blue']}",
        box=box.HEAVY_HEAD,
        title=f"[trace]▮▮ ASSOCIATED TRAFFIC — {owner.upper()}'S PEOPLE ▮▮[/]",
        title_justify="left",
    )
    table.add_column("STRIP", style="dim", width=5, justify="right")
    table.add_column("SCREEN NAME", style="bold white", max_width=32)
    table.add_column("SEEN ON", style="trace", max_width=16)
    table.add_column("HITS", style="scope", justify="right", width=5)
    if has_rmk:
        table.add_column("RMK/", style="amber", max_width=24)

    for i, r in enumerate(rows, 1):
        cells = [
            f"{i:03d}", r["name"][:32], ",".join(r["lists"])[:16], str(r["hits"])
        ]
        if has_rmk:
            entry = remarks.get(r["name"].lower())
            cells.append((entry["rmk"] if entry else "")[:24])
        table.add_row(*cells)
    console.print(table)


# ── Debrief (final summary) ─────────────────────────────────────────────


def show_summary(stats, grade=None, grade_blurb=None):
    """Display final operation summary.

    stats: dict with downloaded, failed, skipped, bytes, elapsed, output_dir
    grade/grade_blurb: optional CAT wreckage category (not pilot score)
    """
    ok = stats["downloaded"]
    bad = stats["failed"]
    skip = stats["skipped"]
    total_found = ok + bad + skip + stats.get("thumbs_only", 0)

    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("K", style=f"dim {HF['green']}", width=24)
    table.add_column("V", style="bold white")

    if grade:
        table.add_row("WRECKAGE GRADE", f"[ok]{grade}[/]")
        if grade_blurb:
            table.add_row("", f"[dim]{grade_blurb}[/]")
    table.add_row("TRAFFIC (photos found)", str(total_found))
    table.add_row("RECOVERED (landed)", f"[ok]{ok}[/]")
    if stats.get("upgraded"):
        table.add_row("UPGRADED TO FULL-SIZE", f"[ok]{stats['upgraded']}[/]")
    if stats.get("thumbs_only"):
        table.add_row("THUMBNAIL ONLY", f"[amber]{stats['thumbs_only']}[/]")
    if bad:
        table.add_row("MISSED APPROACHES", f"[err]{bad}[/]")
    if skip:
        table.add_row("AT GATE (already had)", f"[dim]{skip}[/]")
    if stats.get("pages_failed"):
        table.add_row("ALBUM PAGES UNREACHED", f"[warn]{stats['pages_failed']}[/]")
    table.add_row("PAYLOAD", f"{stats['bytes'] / 1024 / 1024:.1f} MB")
    table.add_row("BLOCK TIME", f"{stats['elapsed']:.1f}s")
    if stats["elapsed"] > 0:
        table.add_row("RECOVERY RATE", f"{ok / stats['elapsed']:.2f} photos/sec")
    table.add_row("HANGAR (output dir)", stats["output_dir"])

    if bad == 0 and grade != "MISSED":
        border, title = HF["green"], "[phase]■ OPERATIONS NORMAL — RUNWAY CLEAR ■[/]"
    else:
        border, title = HF["yellow"], "[warn]■ OPERATION COMPLETE — WITH MISSES ■[/]"
    console.print()
    console.print(
        Panel(table, title=title, border_style=border, box=box.DOUBLE, padding=(1, 2))
    )


# ── Progress bars ───────────────────────────────────────────────────────


def make_progress(transient=False):
    return Progress(
        SpinnerColumn(spinner_name="strobe", style=HF["white"]),
        TextColumn("[phase]{task.description}"),
        BarColumn(bar_width=30, complete_style=HF["green"], finished_style=f"bold {HF['green']}"),
        TextColumn("[bold]{task.completed}[/]/{task.total}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=transient,
    )
