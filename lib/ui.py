"""Terminal display layer for Webshots Resurrector.

Tower-cab aesthetic: Zulu-clock comms log, flight strips, radar-green
scope colors.  Every line still says what it means — jargon decorates,
it never obscures.
"""

import sys
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
from rich.theme import Theme

from lib import __version__

THEME = Theme(
    {
        "phase": "bold bright_green",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "dim": "dim",
        "target": "bold white",
        "heading": "bold white",
        "scope": "green",
        "amber": "yellow",
        "zulu": "dim green",
        "strip": "bold black on green",
        "brand": "bold white",
    }
)

console = Console(theme=THEME, highlight=False)

VERSION = __version__


def _zulu() -> str:
    """Tower clock — every transmission gets a Zulu timestamp."""
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


# ── Banner ──────────────────────────────────────────────────────────────

LOGO_PAISLEY = (
    "  [bold green]█▀█ █▀█ █ █▀▀ █   █▀▀ █ █[/]\n"
    "  [bold green]█▀▀ █▀█ █ ▀▀█ █   █▀▀ ▀█▀[/]\n"
    "  [bold green]▀   ▀ ▀ ▀ ▀▀▀ ▀▀▀ ▀▀▀  ▀ [/]"
)

LOGO_PONYTAIL = (
    "  [bold white]█▀█ █▀█ █▀█ █ █ ▀█▀ █▀█ █ █  [/]\n"
    "  [bold white]█▀▀ █ █ █ █ ▀█▀  █  █▀█ █ █  [/]\n"
    "  [bold white]▀   ▀▀▀ ▀ ▀  ▀   ▀  ▀ ▀ ▀ ▀▀▀[/]"
)

SCANLINE = "[dim green]" + "▔" * 60 + "[/]"


def show_banner():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    body = (
        f"{LOGO_PAISLEY}\n"
        f"{LOGO_PONYTAIL}\n\n"
        f"  {SCANLINE}\n"
        f"  [scope]THE WEBSHOTS RESURRECTOR ▪ ARCHIVE PHOTO RECOVERY[/]"
        f"  [dim]│[/]  [scope]v{VERSION}[/]\n"
        f"  [dim]2,437 MEGAWARCS ON FREQUENCY ▪ 105.9 TB ▪"
        f" WAYBACK RADAR ONLINE[/]\n"
        f"  {SCANLINE}\n"
        f"  [brand]TAILSTRIKE STUDIOS[/] [dim]×[/] [brand]ASH AIRFOIL[/]"
        f" [dim]// coldbricks // {now}[/]"
    )
    console.print()
    console.print(
        Panel(body, border_style="green", box=box.DOUBLE, padding=(1, 1))
    )
    console.print()


# ── Comms log ───────────────────────────────────────────────────────────
#
#  Every line reads like a tower transmission:
#    21:04:11Z  RECON  ▸ radar contact: bexbee12


def _xmit(style: str, tag: str, msg: str):
    console.print(f" [zulu]{_zulu()}[/]  [{style}]{tag:<5}[/] [dim]▸[/] {msg}")


def phase(tag, msg):
    _xmit("phase", tag, msg)


def success(tag, msg):
    _xmit("ok", tag, msg)


def warn(tag, msg):
    _xmit("warn", tag, msg)


def fail(tag, msg):
    _xmit("err", tag, msg)


def detail(msg):
    console.print(f"                    {msg}")


# ── Download callouts ───────────────────────────────────────────────────
#
#  fs  = full-size original landed        → LANDED  FS
#  ph  = 800x600 fallback landed          → LANDED  PH
#  skip = already on disk                 → AT GATE
#  fail = both variants unrecoverable     → MISSED APCH


def dl_ok(variant, size, filename):
    if variant == "fs":
        v = "[ok]LANDED  FS[/]"
    else:
        v = "[amber]LANDED  PH[/]"
    console.print(
        f" [zulu]{_zulu()}[/]   {v}  {size:>9,}B  [dim]{filename}[/]"
    )


def dl_skip(filename):
    console.print(
        f" [zulu]{_zulu()}[/]   [dim]AT GATE      already on disk  {filename}[/]"
    )


def dl_thumb(size, filename):
    console.print(
        f" [zulu]{_zulu()}[/]   [amber]THUMB ONLY[/]  {size:>9,}B  [dim]{filename}  "
        f"(full image never archived)[/]"
    )


def dl_upgrade(size, filename):
    console.print(
        f" [zulu]{_zulu()}[/]   [ok]UPGRADED FS[/] {size:>9,}B  [dim]{filename}  "
        f"(replaced 800x600 with original)[/]"
    )


def dl_fail(filename):
    console.print(
        f" [zulu]{_zulu()}[/]   [err]MISSED APCH[/]  not recoverable  [dim]{filename}[/]"
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
        border_style="dim green",
        box=box.HEAVY_HEAD,
        title="[bold green]▮▮ FLIGHT STRIPS — ALBUMS ON SCOPE ▮▮[/]",
        title_justify="left",
    )
    table.add_column("STRIP", style="dim", width=5, justify="right")
    table.add_column("ALBUM", style="bold white", max_width=30)
    table.add_column("SQUAWK · ID", style="scope", max_width=20)
    table.add_column("SECTOR", style="bold green", max_width=14)
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


# ── Debrief (final summary) ─────────────────────────────────────────────


def show_summary(stats):
    """Display final operation summary.

    stats: dict with downloaded, failed, skipped, bytes, elapsed, output_dir
    """
    ok = stats["downloaded"]
    bad = stats["failed"]
    skip = stats["skipped"]
    total_found = ok + bad + skip + stats.get("thumbs_only", 0)

    table = Table(show_header=False, padding=(0, 2), box=None)
    table.add_column("K", style="dim green", width=22)
    table.add_column("V", style="bold white")

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

    if bad == 0:
        border, title = "green", "[bold green]■ OPERATIONS NORMAL — RUNWAY CLEAR ■[/]"
    else:
        border, title = "yellow", "[bold yellow]■ OPERATION COMPLETE — WITH MISSES ■[/]"
    console.print()
    console.print(
        Panel(table, title=title, border_style=border, box=box.DOUBLE, padding=(1, 2))
    )


# ── Progress bars ───────────────────────────────────────────────────────


def make_progress(transient=False):
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold green]{task.description}"),
        BarColumn(bar_width=30, complete_style="green", finished_style="bold green"),
        TextColumn("[bold]{task.completed}[/]/{task.total}"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=transient,
    )
