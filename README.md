# Paisley Ponytail — the Webshots Resurrector

![Paisley Ponytail nose art](assets/nose_art.jpg)

**Bring lost photos back to life.**

Webshots was a photo sharing service with 14 million users at its peak. In December 2012, the final owner deleted everything. Archive Team ran an emergency crawl and saved what they could — 105.9 TB of photos locked inside 2,437 megawarc blobs on the Internet Archive.

The search tools died years ago. `warctozip.archive.org` has no DNS. The freeze-frame index links go nowhere, and the raw megawarcs are access-restricted now. But everything Archive Team saved was ingested into the **Wayback Machine** — and this tool is the key back in.

---

## Quick start

```
pip install -r requirements.txt

python resurrector.py search yourscreenname     # what's recoverable?
python resurrector.py pull   yourscreenname     # bring it home
```

Works on Windows, macOS, and Linux. Python 3.10+.

When the pull finishes you get a **`gallery.html` contact sheet** — open it in a browser and you're looking at your photos again, organized by album, with the original album names.

## What It Does

Given a Webshots username, Paisley Ponytail:

1. **Queries the Wayback Machine CDX API** for archived snapshots of the profile
2. **Walks every album** — including the pagination pages past page 1 that manual Wayback browsing makes easy to miss
3. **Resolves each photo's real image URL from its archived photo detail page** (the image servers can't be guessed from thumbnails — the photo page is the source of truth)
4. **Downloads the best surviving copy**: full-size original (`_fs`, camera resolution) → 800×600 (`_ph`) → archived thumbnail as a last resort, so you always get *something*
5. **Writes it all down**: per-photo manifest with album titles and captions, plus the gallery contact sheet

Interrupted? Run the same command again — finished photos are skipped, and photos that only got the 800×600 copy are automatically upgraded to full-size when it can be found.

## Going deeper

```
python resurrector.py search yourscreenname --deep
```

`--deep` enumerates every archived version of your profile from **2002 through 2013** via CDX prefix search. If you deleted albums years before Webshots died, older snapshots often still remember them. (Older-era captures are more likely to yield lower resolutions.)

```
python resurrector.py pull yourscreenname --album ALBUMID
```

Pull a single album (repeat `--album` for several). Album IDs are shown by `search`.

## Honest expectations

- **Account public in fall 2012** → odds are genuinely good; often most photos at full resolution
- **Account deleted before 2012** → sometimes! Try `--deep`; quality may be lower
- **Albums set to private** → they were never archived; nothing can recover them

## Etiquette

All requests are rate-limited (~1/sec sustained) with global backoff on 429/503. archive.org is the only reason any of this still exists — the tool treats their servers accordingly, and you should too.

## Why This Exists

Between 1995 and 2012, millions of people uploaded their only copies of family photos, travel pictures, and memories to Webshots. When Threefold Photos pulled the plug, most of those photos vanished. Archive Team's crawl saved a fraction, but the tools to search and extract them have been dead since ~2016. If someone's grandmother's photos are in there, this is how you get them back.

Built by [Tailstrike Studios × Ash Airfoil](https://github.com/coldbricks) — coldbricks.

## License

MIT
