# Architecture — one page for the next person

The rule that explains everything else: **the engine is sovereign, the cab
is optional.** `python resurrector.py pull NAME` must work forever on a
headless box with no Tk installed. Everything visual is presentation over
the same engine, and gets to exist only as long as that stays true.

## Layers

```
resurrector.py        CLI + wizard. Owns commands, manifests, session logs.
lib/engine.py         The recovery core. Rate limiter, CDX, extraction
                      regexes, photo-page resolution, download chain.
                      No UI imports. This file is the product.
lib/truth.py          Authored copy for every kind of miss (shared by
                      terminal + GUI so both tell the same truth).
lib/grade.py          CAT wreckage grade. Pure functions.
lib/relief.py         Hangar scan for position-relief resume briefings.
lib/gallery.py        Offline gallery.html. No network, no CDN, file://.
lib/ui.py             rich terminal cab.
lib/scope_gui.py      tkinter scope. TRAINING mode = simple wizard;
                      PROFESSIONAL mode = the entire cascade. Talks to
                      the engine through cmd_pull(stats=, on_photo=,
                      on_phase=) — real events, never cosmetic counters.
lib/nas_brief.py      Live METAR/NAS for the Professional relief brief.
lib/adsb_feed.py      Live ADS-B overlay (Professional, toggleable).
lib/radio_bed.py      Synthesized HF static for the Professional intro.
                      No real recordings, ever.
lib/prefs.py          .ppty_prefs.json (git-ignored, machine-local).
tests/                Offline fixtures for the extraction grammar.
                      No archive.org traffic in tests. Ever.
```

## Doctrine (the short form)

- False negative is worse than slow. A photo left in the archive is a crash.
- The Wayback Machine is the only door. Raw megawarcs are 401-walled.
- The photo detail page's `<img src>` is the only truth for image URLs.
  Derivation from thumbnails is a last-resort guess (crawl era) — it is
  only reliable for the 2002–05 `/s/thumbN/` → `sym/imageN` path digit.
- Validate JPEG magic bytes, not HTTP status. Wayback archived 404 pages
  as 200s.
- Be a guest at archive.org: global ~1 req/s limiter, shared 429/503
  cooldown, honest User-Agent. Viral day tightens this, never loosens it.
- Resume never demotes. `_fs` on disk is final; `.fs404` means full-size
  is definitively absent; transient failures stay retryable.
- LIVE ≠ SIM. Mock panels are labeled SIM and never inject drama while a
  real pull is running. Live feeds (ADS-B/METAR/NAS) fail soft and never
  touch recovery status.
- Jargon decorates; plain English lands the plane. Every truth state in
  `lib/truth.py` carries both.

## Testing

```
python tests/test_extract.py      # no deps, no network
python -m pytest tests/           # same tests, if you have pytest
```

The extraction regexes shipped near-100% broken twice before the fixtures
existed. If you touch `lib/engine.py` extraction or `lib/gallery.py`,
run the tests, then live-verify once against the canonical account:
`python resurrector.py search bexbee12`.

## What not to build

Accounts, cloud sync, telemetry, an Electron wrapper, a general Wayback
downloader, one-key multi-user scraping, or a default rate increase.
Full reasoning lives with the maintainer.
