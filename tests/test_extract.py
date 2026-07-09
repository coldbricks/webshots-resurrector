"""Offline regression tests for the extraction core.

Extraction is load-bearing: one regex "cleanup" can silently murder
recovery (v1.0/v1.1 shipped near-100% broken because of exactly that).
These fixtures encode the URL grammar of both Webshots eras as verified
in live pulls and recorded in CLAUDE.md — no archive.org traffic, ever.

Run directly (no test framework needed):
    python tests/test_extract.py
or with pytest:
    python -m pytest tests/
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.engine import RE_PAGE_IMAGE, Engine  # noqa: E402
from lib.gallery import write_gallery  # noqa: E402
from lib.grade import grade_from_counts  # noqa: E402
from lib.truth import TRUTH, classify_recovery, mission_report, weather_state  # noqa: E402

WB = "https://web.archive.org"


# ── Fixtures: crawl-era album page (2006–2012 grammar) ──────────────────

CRAWL_ALBUM = f"""
<html><head><title>Webshots - the best in Wallpaper, Desktop Backgrounds</title></head>
<body>
<h1>SPAIN 2 Madrid continued</h1>

<!-- filmstrip widget: anchor-less thumb occurrence comes FIRST -->
<div class="filmstrip">
  <img src="/web/20081123170803im_/http://thumb13.webshots.net/t/56/756/3/31/97/2331331970104337331IcXbAe_th.jpg">
</div>

<!-- main grid: anchored occurrences -->
<div class="grid">
  <a href="/web/20081123170803/http://travel.webshots.com/photo/2331331970104337331IcXbAe">
    <img src="/web/20081123170803im_/http://thumb13.webshots.net/t/56/756/3/31/97/2331331970104337331IcXbAe_th.jpg">
  </a>
  <a href="{WB}/web/20081123170803/http://travel.webshots.com/photo/2331332510104337331qkErJs">
    <img src="{WB}/web/20081123170803im_/http://thumb09.webshots.net/t/56/756/3/32/51/2331332510104337331qkErJs_th.jpg">
  </a>
</div>

<!-- pagination, crawl era: ?start=N (with &amp; noise) -->
<a href="/web/20081123170803/http://travel.webshots.com/album/330301954fOVqeb?vhost=travel&amp;start=42">next</a>
<!-- pagination, old era: path digit -->
<a href="/web/20030614023537/http://community.webshots.com/album/51263986PbmSXK/1">2</a>

<!-- album links on a profile page, incl. pagination-suffixed duplicate -->
<a href="/web/20081123170803/http://travel.webshots.com/album/330301954fOVqeb">SPAIN 2</a>
<a href="/web/20081123170803/http://travel.webshots.com/album/330301954fOVqeb/2">SPAIN 2 p2</a>
<a href="/web/20030614023537/http://community.webshots.com/album/51263986PbmSXK">old one</a>
</body></html>
"""

PROFILE_PAGE = """
<a href="/web/20081123170803/http://community.webshots.com:80/user/bexbee12/2">2</a>
<a href="/web/20060101000000/http://community.webshots.com/user/bexbee12-date/0">by date</a>
<a href="/web/20081123170803/http://community.webshots.com/user/otherguy/2">not ours</a>
"""

OLD_ERA_TITLE = """
<html><head><title>Webshots Community - Band Practice pictures from music photos on webshots</title></head>
<body>no h1 here</body></html>
"""


def test_extract_album_entries_prefers_anchored_occurrence():
    entries = Engine.extract_album_entries(CRAWL_ALBUM)
    by_thumb = {t: (ts, t, page) for ts, t, page in entries}
    thumb13 = (
        "http://thumb13.webshots.net/t/56/756/3/31/97/"
        "2331331970104337331IcXbAe_th.jpg"
    )
    assert thumb13 in by_thumb, "thumb13 not extracted at all"
    ts, _, page = by_thumb[thumb13]
    assert ts == "20081123170803"
    # The filmstrip occurrence has no anchor; the grid occurrence does.
    # Pairing must keep the anchored one — this is the #3 prime directive.
    assert page and page.endswith("/photo/2331331970104337331IcXbAe"), (
        f"anchored photo page lost (got {page!r})"
    )
    # Second thumb pairs with its own (absolute-host) anchor
    thumb09 = (
        "http://thumb09.webshots.net/t/56/756/3/32/51/"
        "2331332510104337331qkErJs_th.jpg"
    )
    assert by_thumb[thumb09][2].endswith("/photo/2331332510104337331qkErJs")


def test_extract_albums_dedupes_pagination_suffix():
    albums = Engine.extract_albums(CRAWL_ALBUM)
    ids = [aid for _url, _sub, aid in albums]
    assert ids.count("330301954fOVqeb") == 1, "pagination suffix made a dup"
    assert "51263986PbmSXK" in ids
    lookup = {aid: (url, sub) for url, sub, aid in albums}
    url, sub = lookup["330301954fOVqeb"]
    assert sub == "travel"
    assert url.endswith("/album/330301954fOVqeb")


def test_extract_profile_pages_same_user_only():
    pages = Engine.extract_profile_pages(PROFILE_PAGE, "bexbee12")
    assert any(p.endswith("/user/bexbee12/2") for p in pages)
    assert any(p.endswith("/user/bexbee12-date/0") for p in pages)
    assert not any("otherguy" in p for p in pages), "leaked another user"
    # :80 host form normalized away
    assert not any(":80/" in p for p in pages)


def test_extract_page_title_h1_beats_slogan():
    assert Engine.extract_page_title(CRAWL_ALBUM) == "SPAIN 2 Madrid continued"


def test_extract_page_title_old_era_prefix_and_suffix_stripped():
    assert Engine.extract_page_title(OLD_ERA_TITLE) == "Band Practice"


def test_page_variants_both_eras():
    crawl = Engine._extract_page_variants(
        CRAWL_ALBUM, "http://travel.webshots.com/album/330301954fOVqeb"
    )
    assert "http://travel.webshots.com/album/330301954fOVqeb?start=42" in crawl
    old = Engine._extract_page_variants(
        CRAWL_ALBUM, "http://community.webshots.com/album/51263986PbmSXK"
    )
    assert "http://community.webshots.com/album/51263986PbmSXK/1" in old


def test_thumb_candidates_old_era_path_digit_wins():
    # Verified 2003 mapping: /s/thumb4/ → sym/image4 via the PATH digit;
    # the HOST digit is load-balancer noise.
    thumb = "http://thumb4.webshots.com/s/thumb4/0/50/81/71105081mpCGrT_th.jpg"
    cands = Engine.thumb_candidates(thumb)
    assert cands[0] == (
        "http://community.webshots.com/sym/image4/0/50/81/71105081mpCGrT_fs.jpg"
    )


def test_thumb_candidates_crawl_era_drops_t_pair():
    thumb = "http://thumb13.webshots.net/t/56/756/3/31/97/2331331970104337331IcXbAe_th.jpg"
    cands = Engine.thumb_candidates(thumb)
    # /t/A/B/ pair dropped; host digit reused (guess only — photo page is truth)
    assert cands == [
        "http://image13.webshots.com/13/3/31/97/2331331970104337331IcXbAe_fs.jpg"
    ]


def test_photo_id():
    assert Engine.photo_id(
        "http://thumb13.webshots.net/t/56/756/3/31/97/84089383TXZkDE_th.jpg"
    ) == "84089383TXZkDE"
    assert Engine.photo_id("http://example.com/nope.jpg") is None


def test_page_image_regex_both_eras():
    html = """
    <img src="/web/20081123170803im_/http://image12.webshots.com/12/3/31/97/x_fs.jpg">
    <img src="/web/20030614023537im_/http://community.webshots.com/sym/image4/0/50/81/y_ph.jpg">
    """
    matches = RE_PAGE_IMAGE.findall(html)
    urls = [u for _ts, u in matches]
    assert any("image12.webshots.com" in u and u.endswith("_fs.jpg") for u in urls)
    assert any("/sym/image4/" in u and u.endswith("_ph.jpg") for u in urls)


def test_sample_timestamps_first_last_middles():
    ts = [str(i) for i in range(10)]
    out = Engine.sample_timestamps(ts, k=4)
    assert out[0] == "0" and out[-1] == "9" and len(out) == 4


# ── Truth / grade doctrine ───────────────────────────────────────────────

def test_classify_recovery_paths():
    assert classify_recovery({"fs": 9, "ph": 1, "th": 0, "failed": 0}).key == "COMPLETE"
    assert classify_recovery({"fs": 4, "ph": 0, "th": 0, "failed": 6}).key == "PARTIAL"
    assert classify_recovery({"fs": 0, "ph": 0, "th": 5, "failed": 0}).key == "ALL_TH"
    assert classify_recovery({"fs": 0, "ph": 0, "th": 0, "failed": 9}).key == "MISSED_ALL"
    assert classify_recovery({"fs": 1, "ph": 0, "th": 0, "failed": 1},
                             hangar_full=True).key == "HANGAR_FULL"
    assert classify_recovery({"fs": 1, "ph": 0, "th": 0, "failed": 0},
                             interrupted=True).key == "INTERRUPTED"
    # Killed in the first seconds: zero landings, but the truth is "resume",
    # not "check your spelling".
    assert classify_recovery({"fs": 0, "ph": 0, "th": 0, "failed": 3},
                             interrupted=True).key == "INTERRUPTED"


def test_weather_state_mapping():
    assert weather_state(429, None).key == "FLOW_CONTROL"
    assert weather_state(429, "Datacamp Limited").key == "FLOW_CONTROL_VPN"
    assert weather_state(0, None).key == "ATC_ZERO"
    assert weather_state(503, None).key == "ATC_ZERO"
    assert weather_state(200, None) is None
    # A fresh engine that hasn't completed a request is NOT an outage —
    # the instrument poll fired a false ATC ZERO card on every search
    # start when last_status initialized to 0.
    assert weather_state(None, None) is None
    assert weather_state(404, None) is None  # archive answering = clear


def test_mission_report_reads_like_a_human_wrote_it():
    line = mission_report({"fs": 44, "ph": 0, "th": 2, "failed": 18})
    assert "46 of 64 landed" in line
    assert "44 full-size originals" in line
    assert "ceiling" in line  # the archive's fault, not the user's


def test_mission_report_never_calls_weather_absence():
    # Transport failures are retryable; "never archived" would train the
    # false absence this tool exists to prevent.
    line = mission_report({"fs": 10, "ph": 0, "th": 0, "failed": 4,
                           "transport": 4})
    assert "never made it into the archive" not in line
    assert "retried automatically" in line
    # Mixed: only the truly-absent count gets the "never archived" claim.
    line = mission_report({"fs": 10, "ph": 0, "th": 0, "failed": 5,
                           "transport": 2})
    assert "3 never made it into the archive" in line
    assert "2 failed on archive weather" in line


def test_grade_thresholds():
    assert grade_from_counts(fs=90, ph=5, th=5)[0] == "CAT III"
    assert grade_from_counts(fs=40, ph=40, th=20)[0] == "CAT II"
    assert grade_from_counts(fs=0, ph=0, th=10)[0] == "CIRCLING"
    assert grade_from_counts()[0] == "MISSED"


# ── Gallery smoke (offline, synthetic manifest) ──────────────────────────

def test_gallery_provenance_and_honesty():
    albums = [
        {
            "id": "330301954fOVqeb", "title": "SPAIN 2", "category": "travel",
            "dir": "SPAIN_2_330301954fOVqeb",
            "photos": [
                {"id": "a1", "variant": "fs", "size": 1000, "file": "a1_fs.jpg",
                 "title": "Madrid", "source": "photo_page", "ts": "20081123170803"},
                {"id": "a2", "variant": "th", "size": 200, "file": "a2_th.jpg",
                 "title": None, "source": "thumb", "ts": "20060501000000"},
                {"id": "a3", "variant": "failed", "size": 0, "reason": "absent"},
            ],
        },
        {
            "id": "emptyone", "title": "Hollow Strip", "category": "family",
            "dir": "Hollow_emptyone",
            "photos": [
                {"id": "b1", "variant": "failed", "size": 0, "reason": "absent"},
            ],
        },
    ]
    with tempfile.TemporaryDirectory() as td:
        path = write_gallery(td, "bexbee12", albums,
                             {"bytes": 1200, "elapsed": 1.0}, remark="canary")
        with open(path, encoding="utf-8") as f:
            doc = f.read().replace("&#x27;", "'")  # un-escape for matching
    assert "address from the photo's own page" in doc, "provenance chip missing"
    assert "archived 2008-11" in doc
    assert "2 of 3 photos landed" in doc, "per-strip mission report missing"
    assert "1 never made it into the archive" in doc
    assert "STRIPS WITH NOTHING LANDED" in doc, "empty strip hidden = reads as bug"
    assert "Archive Team" in doc, "credit missing"
    assert "RMK/ canary" in doc


def _main() -> int:
    failures = 0
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {name}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
