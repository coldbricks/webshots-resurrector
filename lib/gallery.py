"""Contact-sheet generator: a self-contained gallery.html after every pull.

The terminal is the tower cab; this page is the second scope — strip bay,
wreckage grade, callouts that match the terminal. No network, no CDN JS —
file:// friendly. Print stylesheet for the reunion / scrapbook case.
"""

from __future__ import annotations

import html
import os
from datetime import datetime, timezone

from lib import __version__
from lib.grade import count_variants, grade_from_albums

_CSS = """
/* Greens/ambers/reds from DOT/FAA/AM-20/08 Table 1 where applicable
   (scope green #23E162, yellow #DFF334, red #FF1320, orange #FE930D). */
:root { color-scheme: dark; --bg:#0c0f0c; --panel:#131a13; --line:#1f3d1f;
  --green:#23E162; --muted:#7a967a; --dim:#4a5f4a; --text:#d8e8d8;
  --amber:#FE930D; --yellow:#DFF334; --red:#FF1320; --white:#eaffea; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text);
  font-family: Segoe UI, system-ui, sans-serif; line-height: 1.4; }
a { color: var(--green); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Tower cab header ── */
header { padding: 24px 28px 18px; border-bottom: 2px solid var(--line);
  background: linear-gradient(180deg, #101810 0%, var(--bg) 100%); }
header .facility { font-size: 11px; letter-spacing: 2px; color: var(--muted);
  text-transform: uppercase; margin-bottom: 8px; }
header h1 { font-size: 22px; color: var(--green); letter-spacing: 1px; font-weight: 700; }
header h1 span { color: var(--white); font-weight: 500; }
header .rmk { color: var(--amber); font-size: 13px; margin-top: 6px; }
header .sub { color: var(--muted); margin-top: 6px; font-size: 13px; }
.stats { display: flex; gap: 18px; margin-top: 14px; flex-wrap: wrap; }
.stat b { color: var(--green); font-size: 20px; display: block; font-variant-numeric: tabular-nums; }
.stat.amber b { color: var(--amber); }
.stat.dim b { color: var(--muted); }
.stat.alert b { color: var(--red); }
.stat { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
.grade { margin-top: 12px; display: inline-block; padding: 4px 10px;
  border: 1px solid var(--green); color: var(--green); font-size: 12px;
  letter-spacing: 1px; text-transform: uppercase; }
.grade.miss { border-color: var(--red); color: var(--red); }
.grade.circ { border-color: var(--amber); color: var(--amber); }

/* ── Strip bay nav ── */
nav.strip-bay { position: sticky; top: 0; z-index: 10; background: #0a0e0aee;
  border-bottom: 1px solid var(--line); padding: 10px 28px;
  display: flex; flex-wrap: wrap; gap: 8px; backdrop-filter: blur(4px); }
nav.strip-bay a { font-size: 11px; color: var(--muted); border: 1px solid var(--line);
  padding: 3px 8px; border-radius: 3px; letter-spacing: 0.5px; }
nav.strip-bay a:hover { color: var(--green); border-color: var(--green); text-decoration: none; }

/* ── Album = flight strip ── */
section { padding: 22px 28px; border-bottom: 1px solid #152015; }
section .strip-head { display: flex; flex-wrap: wrap; align-items: baseline;
  gap: 10px 18px; margin-bottom: 4px; }
section .strip-num { font-family: ui-monospace, Consolas, monospace;
  color: var(--dim); font-size: 12px; }
section h2 { font-size: 17px; color: var(--white); }
section .squawk { font-family: ui-monospace, Consolas, monospace;
  color: var(--green); font-size: 12px; }
section .sector { color: var(--muted); font-size: 11px; text-transform: uppercase;
  letter-spacing: 1px; }
section .meta { color: var(--dim); font-size: 12px; margin-bottom: 12px; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.card a { display: block; }
.card img { width: 100%; height: 150px; object-fit: cover; display: block; background: #0a0e0a; }
.card .cap { padding: 6px 8px 2px; font-size: 11px; color: #9db89d;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.badge { float: right; font-size: 10px; letter-spacing: 0.5px; color: #557a55; margin-left: 6px; }
.badge.fs { color: var(--green); }
.badge.ph { color: var(--amber); }
.badge.th { color: var(--amber); }
.card .prov { padding: 0 8px 6px; font-size: 9px; color: var(--dim);
  letter-spacing: 0.3px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }

.missed-strips { background: #0e120e; }
.missed-strips h2 { color: var(--muted); }
.missed-strips ul { list-style: none; margin-top: 8px; }
.missed-strips li { color: var(--dim); font-size: 12px; padding: 2px 0; }
.missed-strips li b { color: var(--muted); font-weight: 600; }

footer { padding: 22px 28px; color: var(--dim); font-size: 12px; border-top: 1px solid var(--line); }
footer .credit { margin-top: 8px; color: var(--muted); }
footer .share { margin-top: 8px; color: var(--muted); }

@media print {
  nav.strip-bay { display: none; }
  body { background: #fff; color: #111; }
  header, section, footer { border-color: #ccc; }
  header h1, .stat b, section .squawk, .badge.fs { color: #0a0; }
  .card { break-inside: avoid; border-color: #ccc; }
  .card img { height: 120px; }
}
"""


def write_gallery(
    output_dir: str,
    username: str,
    albums: list[dict],
    stats: dict,
    remark: str | None = None,
) -> str:
    """Write gallery.html into output_dir; returns its path.

    albums: [{"id", "title", "category", "dir", "photos": [record...]}]
    photo records: {"id", "variant", "size", "file", "title"}
    """
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    counts = count_variants(albums)
    # Prefer disk-accurate counts; skip already folded into fs/ph/th by count_variants
    fs_n = counts["fs"]
    ph_n = counts["ph"]
    th_n = counts["th"]
    failed_n = counts["failed"]
    recovered = fs_n + ph_n + th_n
    grade_code, grade_blurb = grade_from_albums(albums)

    grade_cls = "miss" if grade_code == "MISSED" else (
        "circ" if grade_code in ("CAT I", "CIRCLING") else ""
    )

    parts: list[str] = []
    parts.append("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
    parts.append(
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
    )
    parts.append(
        f"<title>{html.escape(username)} — recovered Webshots photos</title>"
    )
    parts.append(f"<style>{_CSS}</style></head><body>")

    # ── Header / tower cab ──
    parts.append("<header>")
    parts.append(
        "<div class='facility'>PPTY TWR · PYSLY-R90 · WAYBACK RADAR · "
        "AVIATE · NAVIGATE · COMMUNICATE · GUEST OF ARCHIVE.ORG</div>"
    )
    parts.append(
        f"<h1>PAISLEY PONYTAIL <span>// {html.escape(username)}</span></h1>"
    )
    if remark:
        parts.append(f"<div class='rmk'>RMK/ {html.escape(remark)}</div>")
    parts.append(
        "<p class='sub'>Pulled from the Internet Archive's Wayback Machine — "
        "originally shared on Webshots (1995–2012). Offline contact sheet; "
        "photos live in the folders next to this file.</p>"
    )
    parts.append(
        f"<div class='grade {grade_cls}'>{html.escape(grade_code)} — "
        f"{html.escape(grade_blurb)}</div>"
    )
    parts.append("<div class='stats'>")
    for label, value, cls in (
        ("Albums", len([a for a in albums if any(p.get("file") for p in a.get("photos") or [])]), ""),
        ("Photos recovered", recovered, ""),
        ("LANDED FS", fs_n, ""),
        ("LANDED PH", ph_n, "amber"),
        ("THUMB ONLY", th_n, "amber"),
        ("MISSED", failed_n, "alert" if failed_n else "dim"),
        ("Payload", f"{stats.get('bytes', 0) / 1024 / 1024:.1f} MB", "dim"),
    ):
        parts.append(
            f"<div class='stat {cls}'><b>{html.escape(str(value))}</b>{label}</div>"
        )
    parts.append("</div></header>")

    # ── Strip bay ──
    visible = []
    for i, album in enumerate(albums, 1):
        photos = [p for p in album.get("photos") or [] if p.get("file")]
        if photos:
            visible.append((i, album, photos))

    if visible:
        parts.append("<nav class='strip-bay' aria-label='Album strip bay'>")
        for i, album, photos in visible:
            title = album.get("title") or f"Album {album.get('id', '')}"
            aid = f"strip-{album.get('id', i)}"
            parts.append(
                f"<a href='#{html.escape(aid)}'>"
                f"{i:03d} {html.escape(str(title)[:28])} · {len(photos)}</a>"
            )
        parts.append("</nav>")

    # ── Albums ──
    for i, album, photos in visible:
        title = album.get("title") or f"Album {album['id']}"
        aid = f"strip-{album.get('id', i)}"
        parts.append(f"<section id='{html.escape(aid)}'>")
        parts.append("<div class='strip-head'>")
        parts.append(f"<span class='strip-num'>STRIP {i:03d}</span>")
        parts.append(f"<h2>{html.escape(title)}</h2>")
        parts.append(
            f"<span class='squawk'>SQUAWK {html.escape(str(album.get('id', '')))}</span>"
        )
        parts.append(
            f"<span class='sector'>{html.escape(str(album.get('category', '') or '—'))}</span>"
        )
        parts.append("</div>")
        all_records = album.get("photos") or []
        attempted = len(all_records)
        missed_here = sum(1 for p in all_records if not p.get("file"))
        meta_line = f"{len(photos)} of {attempted} photos landed on this strip"
        if missed_here:
            meta_line += (
                f" — {missed_here} never made it into the archive"
            )
        parts.append(f"<div class='meta'>{html.escape(meta_line)}</div>")
        parts.append("<div class='grid'>")
        for p in photos:
            rel = f"{album['dir']}/{p['file']}".replace(os.sep, "/")
            cap = p.get("title") or p.get("id") or ""
            variant = p.get("variant", "")
            # skip with file: infer badge from filename
            if variant == "skip":
                f = (p.get("file") or "").lower()
                if f.endswith("_fs.jpg"):
                    variant = "fs"
                elif f.endswith("_th.jpg"):
                    variant = "th"
                else:
                    variant = "ph"
            badge = {
                "fs": "LANDED FS",
                "ph": "LANDED PH",
                "th": "THUMB ONLY",
            }.get(variant, "")
            badge_cls = "fs" if variant == "fs" else ("th" if variant == "th" else "ph")
            # Provenance strip: where the address came from + capture year.
            # Older manifests lack these fields — show what we know.
            prov_bits = []
            src = p.get("source")
            if src == "photo_page":
                prov_bits.append("address from the photo's own page")
            elif src == "derived":
                prov_bits.append("address derived (best effort)")
            elif src == "thumb":
                prov_bits.append("archived thumbnail")
            ts = str(p.get("ts") or "")
            if len(ts) >= 6:
                prov_bits.append(f"archived {ts[:4]}-{ts[4:6]}")
            elif len(ts) >= 4:
                prov_bits.append(f"archived {ts[:4]}")
            prov = " · ".join(prov_bits)
            prov_html = (
                f"<div class='prov'>{html.escape(prov)}</div>" if prov else ""
            )
            parts.append(
                f"<div class='card'><a href='{html.escape(rel)}' target='_blank' rel='noopener'>"
                f"<img src='{html.escape(rel)}' loading='lazy' alt=''></a>"
                f"<div class='cap'>{html.escape(str(cap))}"
                f"<span class='badge {badge_cls}'>{badge}</span></div>"
                f"{prov_html}</div>"
            )
        parts.append("</div></section>")

    # Strips where nothing landed — a hidden album reads as a bug;
    # a listed one reads as the archive's honest ceiling.
    empty_strips = [
        (i, album) for i, album in enumerate(albums, 1)
        if (album.get("photos") or [])
        and not any(p.get("file") for p in album.get("photos") or [])
    ]
    if empty_strips and recovered:
        parts.append("<section class='missed-strips'>")
        parts.append("<h2>STRIPS WITH NOTHING LANDED</h2>")
        parts.append(
            "<p class='meta'>These albums were on the board, but none of "
            "their photos made it into the 2012 crawl at a recoverable "
            "size. That ceiling belongs to the archive — re-running later "
            "sometimes finds more as the archive backfills.</p>"
        )
        parts.append("<ul>")
        for i, album in empty_strips:
            title = album.get("title") or f"Album {album.get('id', '')}"
            n = len(album.get("photos") or [])
            parts.append(
                f"<li><b>{html.escape(str(title)[:48])}</b> — "
                f"{n} photo{'s' if n != 1 else ''} attempted, none archived</li>"
            )
        parts.append("</ul></section>")

    if not recovered:
        parts.append(
            "<section><h2>MISSED APCH</h2>"
            "<p class='meta'>Nothing landed on this pull. Three moves, in order: "
            "(1) <code>find</code> the first few letters of the screen name — "
            "spelling is the #1 miss; (2) pull again with <code>--deep</code> "
            "for 2002–2013 era coverage; (3) if albums were private, they were "
            "never archived — that's an honest dead end. "
            "Still stuck? github.com/coldbricks/paisley-ponytail/issues</p></section>"
        )

    parts.append("<footer>")
    parts.append(
        f"Recovered {when} · Paisley Ponytail v{__version__} "
        f"(the Webshots Resurrector) · Tailstrike Studios × Ash Airfoil · "
        f"github.com/coldbricks/paisley-ponytail"
    )
    parts.append(
        "<div class='credit'>These photos exist because Archive Team "
        "volunteers crawled a dying Webshots in 2012 and the Internet "
        "Archive has kept the copy alive ever since. This tool only digs. "
        "Some photos survived only at 800×600 or as thumbnails — what you "
        "see here is everything the archive holds.</div>"
    )
    parts.append(
        "<div class='share'>Good luck. We were all counting on you. "
        "To share: zip this whole folder (gallery.html + album subfolders). "
        "Be kind to archive.org — they kept these photos alive. "
        "Be decent with what you recover.</div>"
    )
    parts.append("</footer></body></html>")

    path = os.path.join(output_dir, "gallery.html")
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    os.replace(tmp, path)
    return path
