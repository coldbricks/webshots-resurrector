#!/usr/bin/env python3
"""
Paisley Ponytail  --  the Webshots Resurrector
Internet Archive Photo Recovery System

Search for Webshots users and download their archived photos from
the Wayback Machine.  Full-size originals when available, 800x600
fallback, archived thumbnail as a last resort.

Usage:
    python resurrector.py search <username> [--deep]
    python resurrector.py pull   <username> [--deep] [--album ID] [-j JOBS] [-o DIR]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import webbrowser
from datetime import datetime, timezone

# Fail fast with a map, not a traceback -- the person running this may
# never have installed a Python package in their life.
try:
    import httpx     # noqa: F401
    import rich      # noqa: F401
except ImportError as exc:
    print()
    print(f" Missing part: {getattr(exc, 'name', exc)} -- the tool's dependencies")
    print(" aren't installed in this Python.")
    print()
    print(" On Windows, the easy way: double-click Start_Here.bat. It builds the")
    print(" tool a private workspace (.venv) and installs everything into it.")
    print()
    print(" By hand:   python -m venv .venv")
    print("            .venv\\Scripts\\activate      (Windows)")
    print("            source .venv/bin/activate    (macOS/Linux)")
    print("            pip install -r requirements.txt")
    raise SystemExit(1)

from lib import __version__
from lib.engine import Config, Engine, HangarFull, Stats
from lib.gallery import write_gallery
from lib.grade import count_variants, grade_from_albums
from lib.relief import scan_hangar
from lib.remarks import load_remarks, remark_for, save_remark
from lib.ui import (
    console,
    detail,
    dl_fail,
    dl_ok,
    dl_skip,
    dl_thumb,
    dl_upgrade,
    fail,
    ident_status,
    make_progress,
    phase,
    show_albums_table,
    show_atis,
    show_banner,
    show_callsigns_table,
    show_contacts_table,
    show_front_door,
    show_relief_preview,
    show_relief_review,
    show_summary,
    success,
    warn,
)

# ── Failure reporting ───────────────────────────────────────────────────


def radar_fail(phase_name: str, engine: Engine) -> None:
    """Report a dead CDX query with the RIGHT diagnosis.

    A 429 is not an outage -- archive.org is up and deliberately metering
    us. Calling that "the radar is down" sends the user off to wait for a
    recovery that already happened, and if they are on a VPN it will never
    clear no matter how long they wait: archive.org throttles datacenter
    exit IPs hard, and everyone sharing that exit spends the same quota.
    """
    if engine.last_status == 429:
        fail(phase_name, "FLOW CONTROL — archive.org is metering this connection")
        detail("[dim]The archive is fine; it's just rationing this connection.[/]")
        if engine.last_nid:
            detail(
                f"[dim]Their edge sees this connection as:[/] "
                f"[bold]{engine.last_nid}[/]"
            )
        detail("[dim]If that name isn't your home ISP, you're on a VPN — drop it[/]")
        detail("[dim]for this run (or split-tunnel this tool). Datacenter exits[/]")
        detail("[dim]are rate-limited far harder, and every user on that exit[/]")
        detail("[dim]shares one quota.[/]")
        if engine.last_retry_after:
            detail(f"[dim]archive.org asked us to wait {engine.last_retry_after}s.[/]")
        else:
            detail("[dim]Otherwise: wait a few minutes and call again.[/]")
        return
    fail(phase_name, "ATC ZERO — archive.org radar is down")
    detail("[dim]This is an outage. The photos aren't gone;[/]")
    detail("[dim]the radar is. Give it a few minutes and call again.[/]")


# ── Recon + Scan (shared by search and pull) ────────────────────────────


async def recon(
    username: str, engine: Engine
) -> tuple[str, list[list[str]]] | None:
    """RECON phase: locate user in Wayback CDX.

    Returns (latest_timestamp, cdx_rows) or None.
    """
    phase("RECON", f"Target: [target]{username}[/]")
    phase("RECON", "Querying Wayback Machine CDX API...")

    url = f"community.webshots.com/user/{username}"
    with ident_status(username):
        rows = await engine.cdx_search(url)

    if rows is None:
        radar_fail("RECON", engine)
        return None
    if not rows:
        fail(
            "RECON",
            f"NO BEACONS CORRELATED — no flight plan on file for CID [target]{username}[/]",
        )
        detail("[dim]ERAM shows no flight plan. STARS shows no primary target.[/]")
        detail("[dim]Check the spelling, or sweep the frequency for it:[/]")
        detail(
            f"[ok]▸[/] [bold]python resurrector.py find {username[:6]}[/] "
            f"[dim]lists every archived callsign matching a prefix[/]"
        )
        return None

    timestamps = [r[1] for r in rows]
    first, last = timestamps[0][:8], timestamps[-1][:8]
    first_fmt = f"{first[:4]}-{first[4:6]}-{first[6:8]}"
    last_fmt = f"{last[:4]}-{last[4:6]}-{last[6:8]}"

    success(
        "RECON",
        f"IDENT received — radar contact, [bold]{len(rows)}[/] beacons correlated"
        f"  ({first_fmt} .. {last_fmt})",
    )
    rmk = remark_for(load_remarks(), username)
    if rmk:
        phase("RECON", f"[amber]RMK/[/] [target]{rmk}[/]")
    phase("RECON", f"Latest capture: [bold]{timestamps[-1]}[/]")

    return timestamps[-1], rows


async def scan(
    username: str,
    ts: str,
    rows: list[list[str]],
    engine: Engine,
    deep: bool = False,
) -> tuple[str, list[tuple[str, str, str, str]]] | None:
    """SCAN phase: load profile page(s), extract album list.

    Returns (effective_timestamp, albums) or None.
    albums: [(original_url, category, album_id, wayback_ts), ...] —
    each album carries the profile snapshot it was discovered at.
    """
    phase("SCAN", "Loading profile...")
    _, html = await engine.load_profile(username, ts)

    albums: dict[str, tuple[str, str, str, str]] = {}  # album_id -> entry

    def absorb(page_html: str, snap_ts: str):
        for url, category, album_id in engine.extract_albums(page_html):
            albums.setdefault(album_id, (url, category, album_id, snap_ts))

    extra_pages: set[str] = set()
    if html:
        absorb(html, ts)
        extra_pages = engine.extract_profile_pages(html, username)

    # Profile pagination linked from the latest profile (/user/NAME/2)
    for page_url in sorted(extra_pages):
        page_html = await engine.load_page(page_url, ts)
        if page_html:
            absorb(page_html, ts)

    if not albums:
        warn("SCAN", "No albums at latest timestamp, probing alternates...")
        timestamps = [r[1] for r in rows]
        for alt_ts in list(reversed(timestamps[:-1]))[:8]:
            _, alt_html = await engine.load_profile(username, alt_ts)
            if alt_html:
                absorb(alt_html, alt_ts)
                if albums:
                    ts = alt_ts
                    success("SCAN", f"Found albums at {alt_ts}")
                    break

    if deep:
        phase("DEEP", "Enumerating profile-page variants via CDX prefix search...")
        pages = await engine.discover_profile_pages(username)
        if pages is None:
            warn("DEEP", "CDX unreachable — deep enumeration skipped this run")
            pages = []
        success("DEEP", f"{len(pages)} archived profile pages across all eras")
        probes = [
            (url, snap_ts)
            for url, ts_list in pages
            for snap_ts in engine.sample_timestamps(ts_list, 4)
        ]
        if len(probes) > engine.cfg.deep_probe_cap:
            warn(
                "DEEP",
                f"{len(probes)} probes capped at {engine.cfg.deep_probe_cap} "
                "to stay polite to archive.org",
            )
            probes = probes[: engine.cfg.deep_probe_cap]
        before = len(albums)
        with make_progress(transient=True) as progress:
            task = progress.add_task("Deep scan", total=len(probes))
            for url, snap_ts in probes:
                page_html = await engine.load_page(url, snap_ts)
                if page_html:
                    absorb(page_html, snap_ts)
                progress.advance(task)
        gained = len(albums) - before
        if gained:
            success("DEEP", f"[bold]+{gained}[/] albums not visible on the latest profile")
        else:
            phase("DEEP", "No additional albums beyond the latest profile")

    if not albums:
        fail("SCAN", "PRIMARY TARGET ONLY — beacon correlated, but no albums read off the strip")
        detail("[dim]The crawler saved the profile page but missed the album data. If you[/]")
        detail("[dim]didn't use --deep, try it — other eras of radar coverage sometimes hold the strips.[/]")
        return None

    success("SCAN", f"[bold]{len(albums)}[/] albums identified")
    return ts, list(albums.values())


def _merge_album_records(new: dict, old: dict) -> dict:
    """Union two manifest records for the same album at PHOTO level.

    An interrupted re-pull must never demote a previously saved photo
    to a failed record — keep whichever record actually has a file.
    """
    photos: dict[str, dict] = {}
    unkeyed: list[dict] = []
    for p in list(old.get("photos", [])) + list(new.get("photos", [])):
        pid = p.get("id")
        if not pid:
            unkeyed.append(p)
            continue
        prev = photos.get(pid)
        if prev and prev.get("file") and not p.get("file"):
            continue
        photos[pid] = p
    out = {**old, **new}
    out["photos"] = list(photos.values()) + unkeyed
    return out


def _go_around_card(username: str) -> None:
    """If a pull recovers nothing, hand the user the next three moves."""
    console.print()
    fail("PULL", "GO-AROUND — nothing recovered this pass")
    detail("[dim]Three things to try, in order:[/]")
    detail(
        f"[ok]1[/] [bold]python resurrector.py find {username[:4]}[/] "
        f"[dim]— misspelled names are the #1 cause; sweep for the real one[/]"
    )
    detail(
        f"[ok]2[/] [bold]python resurrector.py pull {username} --deep[/] "
        f"[dim]— digs through every site era, 2002-2013[/]"
    )
    detail(
        "[ok]3[/] [dim]If the albums were set private, they were never archived — "
        "that's an honest dead end.[/]"
    )
    detail(
        "[dim]Still stuck? File a report with the screen name:[/] "
        "[bold]github.com/coldbricks/paisley-ponytail/issues/new[/]"
    )


def _album_dir_name(category: str, album_id: str, title: str | None) -> str:
    """Human-readable, collision-proof album folder name."""
    label = title or category or "album"
    slug = re.sub(r"[^\w\-. ]", "", label).strip().replace(" ", "_")[:40]
    return f"{slug}_{album_id}" if slug else album_id


def _prefix_variants(query: str) -> list[str]:
    """People half-remember names with spaces; Webshots never had them.

    "cool dave" sweeps cooldave, cool_dave, and cool-dave.
    """
    q = query.strip().lower()
    if " " not in q:
        return [q]
    parts = q.split()
    return list(dict.fromkeys(["".join(parts), "_".join(parts), "-".join(parts)]))


async def cmd_find(
    query: str, engine: Engine, top: int = 30, output_root: str = "output"
) -> None:
    """Sweep the archive's index for screen names matching a prefix."""
    variants = _prefix_variants(query)
    if any(len(v) < 2 for v in variants):
        fail("SWEEP", "Prefix too short — give me at least 2 characters")
        return

    merged: dict[str, dict] = {}
    truncated = False
    for v in variants:
        phase("SWEEP", f"Scanning frequency for callsigns matching [target]{v}*[/]")
        with ident_status(f"{v}*"):
            result = await engine.find_usernames(v)
        if result is None:
            radar_fail("SWEEP", engine)
            return
        found, was_truncated = result
        truncated = truncated or was_truncated
        for r in found:
            key = r["name"].lower()
            prev = merged.get(key)
            if prev is None:
                merged[key] = r
            else:
                prev["pages"] += r["pages"]
                prev["first"] = min(prev["first"], r["first"])
                prev["last"] = max(prev["last"], r["last"])

    if not merged:
        fail(
            "SWEEP",
            f"SWEEP COMPLETE — no beacons correlated to that flight plan ([target]{query}[/])",
        )
        detail("[dim]The frequency is quiet. Try fewer letters — even just the first three.[/]")
        return

    ranked = sorted(merged.values(), key=lambda r: (-r["pages"], r["name"].lower()))
    shown = ranked[:top]

    console.print()
    show_callsigns_table(shown, len(ranked), remarks=load_remarks())
    console.print()
    success("SWEEP", f"[bold]{len(ranked)}[/] beacons correlated on frequency")
    if truncated:
        warn("SWEEP", "Index scan hit its cap; narrow the prefix to see the rest")

    await say_intentions(shown, engine, top, output_root)


async def say_intentions(
    shown: list[dict], engine: Engine, top: int, output_root: str
) -> None:
    """The interactive board: act on a strip, or retask the scope.

    #=search strip · p#=pull strip · f#=friends of strip ·
    any other text = new callsign sweep · Enter = stand by.
    """
    if not sys.stdin.isatty():
        detail("[dim]Run [bold]search <name>[/bold] on a strip to see its albums.[/]")
        return

    while True:
        console.print()
        try:
            raw = console.input(
                " [phase]SAY INTENTIONS[/] [dim]▸[/] "
                "[bold]#[/][dim]=search · [/]"
                "[bold]p#[/][dim]=pull · [/]"
                "[bold]f#[/][dim]=friends · [/]"
                "[bold]r# txt[/][dim]=remark · [/]"
                "[bold]name[/][dim]=sweep · [/]"
                "[dim]Enter=stand by ▸ [/]"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            break
        # r3 Becca from HS  → file a FLIGHT PLAN REMARK on strip 3
        m_rmk = re.fullmatch(r"[rR]\s*(\d+)(?:\s+(.*))?", raw)
        if m_rmk:
            n = int(m_rmk.group(1))
            if not (1 <= n <= len(shown)):
                warn("SWEEP", f"Say again — that's not a strip number on the board (1-{len(shown)})")
                continue
            name = shown[n - 1]["name"]
            text = (m_rmk.group(2) or "").strip()
            if text:
                save_remark(name, text)
                success("SWEEP", f"RMK/ filed on [target]{name}[/]: [amber]{text}[/]")
            else:
                existing = remark_for(load_remarks(), name)
                if existing:
                    phase("SWEEP", f"[target]{name}[/] [amber]RMK/[/] {existing}")
                else:
                    phase("SWEEP", f"No remarks on file for [target]{name}[/] — "
                          f"[dim]r{n} <text> to file one[/]")
            continue
        m = re.fullmatch(r"([pPfF]?)\s*(\d+)", raw)
        if m:
            n = int(m.group(2))
            if not (1 <= n <= len(shown)):
                warn("SWEEP", f"Say again — that's not a strip number on the board (1-{len(shown)})")
                continue
            name = shown[n - 1]["name"]
            action = m.group(1).lower()
            console.print()
            if action == "p":
                await cmd_pull(name, engine, output_root)
                break
            if action == "f":
                await cmd_friends(name, engine, top=top, output_root=output_root)
                break
            await cmd_search(name, engine)
        else:
            # Anything that isn't a strip number is a new callsign —
            # controllers don't leave the scope to change targets.
            console.print()
            await cmd_find(raw, engine, top=top, output_root=output_root)
            break


def cmd_remarks(args_remark: list[str]) -> None:
    """File, read, or list FLIGHT PLAN REMARKS from the command line."""
    remarks = load_remarks()
    if not args_remark:
        if not remarks:
            phase("RMK", "No remarks on file — [dim]remarks NAME your note here[/]")
            return
        phase("RMK", f"[bold]{len(remarks)}[/] flight plans annotated:")
        for entry in sorted(remarks.values(), key=lambda e: e["name"].lower()):
            detail(f"[target]{entry['name']}[/]  [amber]RMK/[/] {entry['rmk']}")
        return
    name, text = args_remark[0], " ".join(args_remark[1:]).strip()
    if text:
        save_remark(name, text)
        success("RMK", f"RMK/ filed on [target]{name}[/]: [amber]{text}[/]")
    else:
        existing = remark_for(remarks, name)
        if existing:
            phase("RMK", f"[target]{name}[/]  [amber]RMK/[/] {existing}")
        else:
            phase("RMK", f"No remarks on file for [target]{name}[/]")


async def cmd_friends(
    username: str, engine: Engine, top: int = 30, output_root: str = "output"
) -> None:
    """List a user's archived friends & fans — their whole social graph."""
    phase("TRACE", f"Pulling associated traffic for [target]{username}[/]")
    with ident_status(f"{username}/people"):
        result = await engine.list_contacts(username)
    if result is None:
        radar_fail("TRACE", engine)
        return
    contacts, pages_read = result
    if not contacts:
        fail(
            "TRACE",
            f"NO ASSOCIATED TRAFFIC ON FILE — no friends/fans pages archived for "
            f"[target]{username}[/]",
        )
        detail("[dim]Their photos may still be fully recoverable —[/]")
        detail(f"[dim]run [bold]search {username}[/bold]; only the social pages are missing.[/]")
        return

    shown = contacts[:top]
    console.print()
    show_contacts_table(shown, username, remarks=load_remarks())
    console.print()
    success(
        "TRACE",
        f"[bold]{len(contacts)}[/] associated tracks off {pages_read} archived pages",
    )
    if len(contacts) > top:
        detail(f"[dim]{len(contacts) - top} more not shown — raise -n to see them all[/]")

    await say_intentions(shown, engine, top, output_root)


# ── Commands ────────────────────────────────────────────────────────────


async def cmd_search(username: str, engine: Engine, deep: bool = False) -> None:
    """Search for a user: show profile info and album listing."""
    result = await recon(username, engine)
    if not result:
        return
    ts, rows = result

    scan_result = await scan(username, ts, rows, engine, deep=deep)
    if not scan_result:
        return
    ts, albums_raw = scan_result

    phase("SCAN", f"Counting photos in {len(albums_raw)} albums...")
    album_data: list[tuple[str, str, int, str | None]] = []
    total_photos = 0
    pages_failed = 0

    with make_progress(transient=True) as progress:
        task = progress.add_task("Scanning", total=len(albums_raw))
        for url, category, album_id, album_ts in albums_raw:
            entries, meta = await engine.load_album(url, album_ts)
            album_data.append((url, category, len(entries), meta["title"]))
            total_photos += len(entries)
            pages_failed += meta["pages_failed"]
            progress.advance(task)

    console.print()
    show_albums_table(album_data)
    console.print()
    success("SCAN", f"[bold]{total_photos}[/] photos across {len(albums_raw)} albums")
    if pages_failed:
        warn("SCAN", f"{pages_failed} album pages unreachable — pull may find more on retry")
    # Hollow strips: albums boarded with zero photos
    hollow = sum(1 for _u, _c, n, _t in album_data if n == 0)
    if hollow:
        warn(
            "SCAN",
            f"[bold]{hollow}[/] strip(s) ON BOARD — NO TARGETS "
            f"(listed, but no photos extractable this pass)",
        )
    console.print()
    detail(
        f"[ok]CLEARED FOR PULL[/] [dim]▸[/] "
        f"[bold]python resurrector.py pull {username}[/] "
        f"[dim]to recover all photos[/]"
    )
    if sys.stdin.isatty():
        await say_album_intentions(username, albums_raw, album_data, engine)


async def say_album_intentions(
    username: str,
    albums_raw: list[tuple[str, str, str, str]],
    album_data: list[tuple[str, str, int, str | None]],
    engine: Engine,
    output_root: str = "output",
) -> None:
    """After search: act on album strips like the callsign board."""
    if not albums_raw:
        return
    while True:
        console.print()
        try:
            raw = console.input(
                " [phase]SAY INTENTIONS[/] [dim]▸[/] "
                "[bold]p[/][dim]=pull all · [/]"
                "[bold]p#[/][dim]=pull strip · [/]"
                "[bold]d[/][dim]=deep rescan · [/]"
                "[bold]r txt[/][dim]=remark · [/]"
                "[dim]Enter=stand by ▸ [/]"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            break
        if raw.lower() == "p":
            console.print()
            await cmd_pull(username, engine, output_root)
            break
        if raw.lower() == "d":
            console.print()
            await cmd_search(username, engine, deep=True)
            break
        m_rmk = re.fullmatch(r"[rR]\s*(.*)", raw)
        if m_rmk and not re.fullmatch(r"[rR]\s*\d+.*", raw):
            text = (m_rmk.group(1) or "").strip()
            if text:
                save_remark(username, text)
                success("RMK", f"RMK/ filed on [target]{username}[/]: [amber]{text}[/]")
            else:
                existing = remark_for(load_remarks(), username)
                if existing:
                    phase("RMK", f"[target]{username}[/] [amber]RMK/[/] {existing}")
                else:
                    phase("RMK", f"No remarks on file for [target]{username}[/]")
            continue
        m = re.fullmatch(r"[pP]\s*(\d+)", raw)
        if m:
            n = int(m.group(1))
            if not (1 <= n <= len(albums_raw)):
                warn("SCAN", f"Say again — strip 1-{len(albums_raw)}")
                continue
            album_id = albums_raw[n - 1][2]
            console.print()
            await cmd_pull(username, engine, output_root, only_albums=[album_id])
            break
        warn("SCAN", "Say again — p · p# · d · r <text> · Enter")


async def cmd_pull(
    username: str,
    engine: Engine,
    output_root: str = "output",
    deep: bool = False,
    only_albums: list[str] | None = None,
    no_open: bool = False,
    stats: Stats | None = None,
    on_photo=None,
    on_phase=None,
) -> None:
    """Download all photos for a user.

    stats: caller-owned Stats — a live UI can poll it mid-pull.
    on_photo(record, album): fired after each photo lands/misses.
    on_phase(name, **info): RECON / SCAN / PULL / DONE checkpoints.
    Both callbacks are best-effort; they must never kill the pull.
    """
    def _phase_cb(name: str, **info):
        if on_phase:
            try:
                on_phase(name, **info)
            except Exception:
                pass

    _phase_cb("RECON")
    result = await recon(username, engine)
    if not result:
        _phase_cb("DONE")
        return
    ts, rows = result

    _phase_cb("SCAN")
    scan_result = await scan(username, ts, rows, engine, deep=deep)
    if not scan_result:
        _phase_cb("DONE")
        return
    ts, albums_raw = scan_result

    if only_albums:
        wanted = set(only_albums)
        albums_raw = [a for a in albums_raw if a[2] in wanted]
        if not albums_raw:
            fail("SCAN", f"No albums matched --album {', '.join(only_albums)}")
            return
        phase("SCAN", f"Filtered to {len(albums_raw)} requested album(s)")

    # ── Build photo manifest ────────────────────────────────────────
    phase("SCAN", f"Building photo manifest from {len(albums_raw)} albums...")

    album_infos: list[dict] = []
    album_data: list[tuple[str, str, int, str | None]] = []
    pages_failed = 0

    with make_progress(transient=True) as progress:
        task = progress.add_task("Scanning albums", total=len(albums_raw))
        for url, category, album_id, album_ts in albums_raw:
            entries, meta = await engine.load_album(url, album_ts)
            pages_failed += meta["pages_failed"]
            album_data.append((url, category, len(entries), meta["title"]))
            album_infos.append({
                "id": album_id,
                "url": url,
                "category": category,
                "title": meta["title"],
                "ts": album_ts,
                "entries": entries,   # (thumb_ts, thumb_url, photo_page|None)
                "photos": [],
            })
            progress.advance(task)

    console.print()
    show_albums_table(album_data)

    total = sum(len(a["entries"]) for a in album_infos)
    console.print()
    success("SCAN", f"[bold]{total}[/] photos in manifest")
    hollow = sum(1 for a in album_infos if not a["entries"])
    if hollow:
        warn(
            "SCAN",
            f"[bold]{hollow}[/] strip(s) ON BOARD — NO TARGETS",
        )
    if not total:
        return

    # ── Download ────────────────────────────────────────────────────
    output_dir = os.path.join(output_root, username)
    os.makedirs(output_dir, exist_ok=True)

    # Position relief — PREVIEW hangar before burning archive requests
    sia_before = scan_hangar(output_dir)
    show_relief_preview(username, sia_before)

    # Windows still enforces ~260-char paths in most configurations;
    # deep OneDrive-nested output roots render as 100% MISSED APCH.
    if sys.platform == "win32":
        worst_case = len(os.path.abspath(output_dir)) + 1 + 52 + 1 + 44
        if worst_case > 247:
            fail("PULL", "RUNWAY TOO SHORT — output path risks Windows' 260-char limit")
            detail(f"[dim]Current hangar: {os.path.abspath(output_dir)}[/]")
            detail("[dim]Rerun with a shorter output root, e.g. [bold]-o C:\\webshots[/][/]")
            return

    stats = stats or Stats()
    stats.pages_failed = pages_failed
    _phase_cb("PULL", total=total, albums=len(album_infos))
    phase(
        "PULL",
        f"Extracting {total} photos  "
        f"([bold]{engine.cfg.max_concurrent}[/] concurrent)",
    )
    console.print()

    interrupted = False
    hangar_full = False
    with make_progress() as progress:
        task = progress.add_task(f"Pulling {username}", total=total)

        # Strip index per album for datablock callouts (1-based board order)
        strip_by_id = {
            a["id"]: f"{i:02d}/{len(album_infos):02d}"
            for i, a in enumerate(album_infos, 1)
        }

        async def _dl(album: dict, thumb_ts: str, thumb_url: str, photo_page: str | None):
            nonlocal hangar_full
            dir_name = _album_dir_name(album["category"], album["id"], album["title"])
            album_dir = os.path.join(output_dir, dir_name)
            os.makedirs(album_dir, exist_ok=True)
            album["dir"] = dir_name
            strip = strip_by_id.get(album["id"])

            if hangar_full:
                # Disk is full: stop asking archive.org for bytes we
                # cannot save.  These photos stay retryable.
                stats.failed += 1
                full_rec = {
                    "id": engine.photo_id(thumb_url), "variant": "failed",
                    "size": 0, "reason": "disk_full", "error": "disk full",
                }
                album["photos"].append(full_rec)
                if on_photo:
                    try:
                        on_photo(full_rec, album)
                    except Exception:
                        pass
                progress.advance(task)
                return

            try:
                record = await engine.download_photo(
                    thumb_ts, thumb_url, photo_page, album_dir, stats
                )
            except HangarFull:
                hangar_full = True
                stats.failed += 1
                record = {"id": engine.photo_id(thumb_url), "variant": "failed",
                          "size": 0, "reason": "disk_full", "error": "disk full"}
            except Exception as exc:  # one bad photo must never kill the run
                stats.failed += 1
                record = {"id": engine.photo_id(thumb_url), "variant": "failed",
                          "size": 0, "reason": "transport", "error": str(exc)[:200]}
            album["photos"].append(record)
            if on_photo:
                try:
                    on_photo(record, album)
                except Exception:
                    pass

            pid = record.get("id") or "unknown"
            variant = record.get("variant")
            cap = record.get("title")
            if variant in ("fs", "ph"):
                if variant == "fs" and record.get("upgraded"):
                    dl_upgrade(record["size"], record.get("file", pid),
                               caption=cap, strip=strip, pid=pid)
                else:
                    dl_ok(variant, record["size"], record.get("file", pid),
                          caption=cap, strip=strip, pid=pid)
            elif variant == "th":
                dl_thumb(record["size"], record.get("file", pid),
                         caption=cap, strip=strip, pid=pid)
            elif variant == "skip":
                dl_skip(record.get("file", pid), caption=cap, strip=strip, pid=pid)
            else:
                dl_fail(pid, caption=cap, strip=strip, pid=pid,
                        reason=record.get("reason"))
            progress.advance(task)

        tasks = [
            _dl(album, t_ts, t_url, photo)
            for album in album_infos
            for t_ts, t_url, photo in album["entries"]
        ]
        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            interrupted = True

    # ── Manifest + gallery ──────────────────────────────────────────
    for album in album_infos:
        album.pop("entries", None)
        album.setdefault("dir", _album_dir_name(
            album["category"], album["id"], album["title"]))

    # Merge with a previous manifest so partial pulls (--album, deep
    # reruns, interrupted runs) never drop earlier albums OR demote
    # previously saved photos — union happens at photo level.
    manifest_path = os.path.join(output_dir, "manifest.json")
    merged: dict = {}
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                for prev in json.load(f).get("albums", []):
                    if prev.get("id"):
                        merged[prev["id"]] = prev
        except (OSError, ValueError):
            pass
    for a in album_infos:
        current = {k: v for k, v in a.items() if k != "ts"}
        merged[a["id"]] = _merge_album_records(current, merged.get(a["id"], {}))
    all_albums = list(merged.values())

    grade_code, grade_blurb = grade_from_albums(all_albums)
    variant_counts = count_variants(all_albums)
    show_relief_review(sia_before, variant_counts)

    user_rmk = remark_for(load_remarks(), username)
    manifest = {
        "tool": "webshots-resurrector",
        "codename": "Paisley Ponytail",
        "version": __version__,
        "user": username,
        "remark": user_rmk,
        "wayback_timestamp": ts,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "interrupted": interrupted,
        "grade": grade_code,
        "grade_detail": grade_blurb,
        "totals": stats.as_dict(),
        "albums": all_albums,
    }
    tmp_manifest = manifest_path + ".part"
    with open(tmp_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp_manifest, manifest_path)

    gallery_path = write_gallery(
        output_dir, username, all_albums, stats.as_dict(), remark=user_rmk
    )

    if hangar_full:
        fail("PULL", "HANGAR FULL — the disk ran out of space mid-pull")
        detail("[dim]Everything saved so far is safe. Free up space (or rerun with[/]")
        detail("[dim]-o pointing at a bigger drive) and run the same command again.[/]")
    if interrupted:
        warn("PULL", "Interrupted — progress saved; rerun the same command to resume")
    show_summary(
        stats.as_dict(os.path.abspath(output_dir)),
        grade=grade_code,
        grade_blurb=grade_blurb,
    )
    console.print()
    success("PULL", f"Contact sheet: [bold]{os.path.abspath(gallery_path)}[/]")
    _phase_cb("DONE", gallery=gallery_path, interrupted=interrupted,
              hangar_full=hangar_full)

    # Flight recorder: what the user saw, for support reports.
    try:
        log_name = f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')}.log"
        console.save_text(os.path.join(output_dir, log_name), clear=False)
    except OSError:
        pass

    recovered_any = (
        stats.downloaded + stats.upgraded + stats.skipped + stats.thumbs_only
    ) > 0
    if not recovered_any and total:
        _go_around_card(username)
    elif recovered_any and not no_open and sys.stdin.isatty():
        target = os.path.abspath(gallery_path)
        try:
            os.startfile(target)  # Windows
        except AttributeError:
            webbrowser.open("file:///" + target.replace(os.sep, "/"))
        except OSError:
            pass
        detail("[dim]Opening the contact sheet in your browser — that's your photos back.[/]")
    else:
        detail("[dim]Open it in a browser — that's your photos back.[/]")


async def wizard() -> None:
    """The front door: no arguments, no manual, one question.

    A double-click on Start_Here.bat lands here — the person on the
    other end may never have used a terminal in their life. Make the
    glass look like a live scope; then make the next step idiot-proof.
    """
    show_front_door()
    cfg = Config()
    async with Engine(cfg) as engine:
        while True:
            console.print()
            try:
                name = console.input(
                    " [phase]SAY CALLSIGN[/] [dim]▸[/] "
                    "[brand]what was the Webshots screen name?[/] "
                    "[dim](Enter=close) ▸ [/]"
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not name:
                return
            console.print()
            if " " in name:
                # Names never had spaces — this is a half-memory: sweep it.
                await cmd_find(name, engine)
                continue
            result = await recon(name, engine)
            if not result:
                try:
                    ans = console.input(
                        " [ident]SWEEP?[/] [dim]▸ scan the archive for similar "
                        "names? (Enter=yes · n=no) ▸ [/]"
                    ).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    return
                if ans != "n":
                    console.print()
                    await cmd_find(name, engine)
                continue
            try:
                ans = console.input(
                    " [phase]INTENTIONS[/] [dim]▸ Enter=recover everything now · "
                    "s=just look first · d=deep (old eras) · n=different name ▸ [/]"
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            console.print()
            if ans == "n":
                continue
            if ans == "s":
                await cmd_search(name, engine)
            elif ans == "d":
                detail("[dim]Long-range Center scan — slower, finds older eras.[/]")
                await cmd_pull(name, engine, deep=True)
            else:
                await cmd_pull(name, engine)


# ── CLI ─────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resurrector",
        description="Paisley Ponytail (the Webshots Resurrector)  -  Internet Archive Photo Recovery System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python resurrector.py                    (STARS/ERAM-style scope window)\n"
            "  python resurrector.py --cli              (terminal wizard)\n"
            "  python resurrector.py scope              (force scope GUI)\n"
            "  python resurrector.py friends bexbee12\n"
            "  python resurrector.py find   cooldave\n"
            "  python resurrector.py search bexbee12\n"
            "  python resurrector.py pull   bexbee12 -j 6\n"
        ),
    )
    parser.add_argument(
        "--version", action="version",
        version=f"Paisley Ponytail v{__version__} (the Webshots Resurrector)",
    )
    parser.add_argument(
        "--cli", action="store_true",
        help="terminal wizard instead of the STARS/ERAM scope window",
    )

    deep_help = (
        "enumerate every archived profile-page variant via CDX prefix "
        "search — finds albums from older site eras (2002-2013)"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "scope",
        help="Open the STARS/ERAM-style scope window (default when you double-click)",
    )

    p_find = sub.add_parser(
        "find",
        help="Half-remember a screen name? List every archived name matching a prefix",
    )
    p_find.add_argument(
        "prefix", nargs="+",
        help="start of the screen name (spaces OK: 'cool dave' tries cooldave/cool_dave/cool-dave)",
    )
    p_find.add_argument(
        "-n", "--top", type=int, default=30, metavar="N",
        help="show at most N matches (default: 30)",
    )

    p_friends = sub.add_parser(
        "friends",
        help="List a screen name's archived friends & fans — everyone they knew, one search away",
    )
    p_friends.add_argument("username", help="Webshots username whose people pages to read")
    p_friends.add_argument(
        "-n", "--top", type=int, default=30, metavar="N",
        help="show at most N contacts (default: 30)",
    )

    p_remarks = sub.add_parser(
        "remarks",
        help="FLIGHT PLAN REMARKS — attach real names/notes to screen names (stays local)",
    )
    p_remarks.add_argument(
        "remark", nargs="*",
        help="NAME then your note ('remarks bexbee12 Becca from HS'); NAME alone reads it; nothing lists all",
    )

    p_search = sub.add_parser("search", help="Search for a user, list albums and photo counts")
    p_search.add_argument("username", help="Webshots username to look up")
    p_search.add_argument("--deep", action="store_true", help=deep_help)

    p_pull = sub.add_parser("pull", help="Download all photos for a user")
    p_pull.add_argument("username", help="Webshots username to download")
    p_pull.add_argument("--deep", action="store_true", help=deep_help)
    p_pull.add_argument(
        "--album", action="append", metavar="ID",
        help="only pull this album ID (repeatable)",
    )
    p_pull.add_argument(
        "-o", "--output", default="output", help="Output root directory (default: output/)"
    )
    p_pull.add_argument(
        "-j", "--jobs", type=int, default=4, metavar="N",
        help="Concurrent downloads (default: 4, max 8)",
    )
    p_pull.add_argument(
        "--no-open", action="store_true",
        help="don't auto-open gallery.html when the pull succeeds",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Default double-click → STARS/ERAM scope GUI. --cli keeps the tower cab terminal.
    want_scope = (
        args.command == "scope"
        or (not args.command and not getattr(args, "cli", False))
    )
    if want_scope and not getattr(args, "cli", False):
        try:
            from lib.scope_gui import main as scope_main
            scope_main()
            return
        except Exception as exc:
            # Headless / no display — fall through to terminal.
            print(f" Scope window unavailable ({exc}); falling back to terminal cab.")

    cold = not args.command and sys.stdin.isatty()
    show_banner(cold_start=cold)
    show_atis()

    if not args.command or args.command == "scope":
        if sys.stdin.isatty():
            try:
                asyncio.run(wizard())
            except KeyboardInterrupt:
                pass
            try:
                input("\n Press Enter to close the cab... ")
            except (EOFError, KeyboardInterrupt):
                pass
        else:
            parser.print_help()
        return

    if args.command == "remarks":
        cmd_remarks(args.remark)
        return

    cfg = Config()
    if hasattr(args, "jobs"):
        cfg.max_concurrent = max(1, min(args.jobs, 8))

    async def _run():
        async with Engine(cfg) as engine:
            deep = getattr(args, "deep", False)
            if args.command == "find":
                await cmd_find(" ".join(args.prefix), engine, top=max(1, args.top))
            elif args.command == "friends":
                await cmd_friends(args.username, engine, top=max(1, args.top))
            elif args.command == "search":
                await cmd_search(args.username, engine, deep=deep)
            elif args.command == "pull":
                out = getattr(args, "output", "output")
                await cmd_pull(
                    args.username, engine, out,
                    deep=deep, only_albums=getattr(args, "album", None),
                    no_open=getattr(args, "no_open", False),
                )

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n [warn]Interrupted.[/] [dim]Progress is saved — rerun the same"
                      " command to resume where you left off.[/]")
        sys.exit(130)


if __name__ == "__main__":
    main()
