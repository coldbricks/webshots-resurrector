# NTSB DOCKET WBS-2012-12-01

## Total Loss of Webshots (1995–2012) and the Recovery of the Wreckage

**Report adopted:** July 8, 2026
**Investigator-in-charge:** coldbricks — Tailstrike Studios × Ash Airfoil
**Status:** Investigation open. Public assistance requested (see §6).

> **Operator's statement:** *It took me 9+ years to put this together, but the
> biggest reverse engineering project in internet photo history has been
> achieved. Now, I just need everyone to break it again.*

Before the report, a word on the format. Yes, it's written like an NTSB
docket. I spent my working life around air traffic control, accident reports
are my native format for writing up a wreck, and this was a wreck. I was
also on board: my photos went down with everyone else's, which is why the
investigator-in-charge is listed as a complainant too. Everything below is
checkable against the live archive, photo IDs included.

---

## 1. Factual Information

### 1.1 History of Flight

Webshots entered service in 1995 as a consumer photo-sharing site and flew for
seventeen years, through the dial-up era, the digicam boom, and the arrival of
Facebook, peaking around **14 million monthly users**. For an enormous number
of ordinary families in the early 2000s, Webshots held the only copy of their
photos that existed anywhere. The memory card got erased to make room for the
next birthday party, the prints never got made, and the family hard drive died
in 2006 anyway. The album lived on Webshots, and that was fine, because
websites were forever.

The aircraft changed hands repeatedly in its final years. The last owner,
Threefold Photos, announced a pivot in late 2012: the service would relaunch
as something else, and existing user photos would not be coming along. On
**December 1, 2012**, image hosting ended and the photo libraries of fourteen
million users were deleted.

### 1.2 Injuries to Persons

No physical injuries. Approximately 14 million photo libraries lost, an
unknown but large fraction of them the only surviving copy of the images
they contained.

### 1.3 The Rescue Flight

In the final weeks before shutdown, **Archive Team**, the loose volunteer
collective that shows up when websites announce their own funerals, ran an
emergency distributed crawl using their "Warrior" clients. Thousands of
volunteers' machines walked `community.webshots.com` profile by profile,
album by album, photo by photo, and shipped what they captured to the
Internet Archive.

The haul: **2,437 items** in the `webshots-freeze-frame` collection,
**105.9 TB** of WARC data — web crawls bundled into ~50 GB "megawarc" blobs,
each accompanied by a CDX index mapping every captured URL to a byte offset.

### 1.4 The Second Accident

Rescue turned out to be only step one:

| Year | Event |
|---|---|
| ~2013 | `warctozip.archive.org` lets users extract per-user ZIPs from megawarcs. A search index maps screen names to blobs. The system works. |
| ~2016 | `warctozip.archive.org` loses DNS and never returns. Every download link in the search index now points at nothing. |
| ~2016–2018 | Users attempt the documented workaround — direct megawarc downloads. They discover the "sub-100 MB extract" is a 50 GB file and a 12-hour download. Forum threads fill with grief. |
| later | The freeze-frame items are flagged `access-restricted-item: true` — raw downloads now return **HTTP 401** for everyone. The search index item itself is darked (`is_dark: true`). Verified live, July 8, 2026. |

Result: 105.9 TB of family photos, rescued at great effort, locked in blobs
nobody could open, indexed by a search page nobody could reach. For nearly a
decade the practical recovery method was **manual Wayback Machine spelunking,
one page at a time**. I spent 9+ years doing exactly that for my own account.

### 1.5 The Aircraft: Consumer Photography, 1999–2005

To understand the wreckage, understand what people were flying.

The digicams of the Webshots era shot **1.3 to 4 megapixels**. A 1.3 MP
camera produces a **1280×960** frame. That is why the exact same resolution
appears throughout this investigation as "full size": for millions of photos
it is every pixel the camera ever captured, not a website's downscale.
Memory cards were 16–128 MB and expensive, so people shot at reduced quality
on purpose to fit the vacation on one card.

Display and network constraints shaped the rest of the site's file grammar.
Monitors were 15–17" CRTs running SVGA (800×600) or 1024×768, so the photo
you actually *viewed* on a Webshots page was the **800×600** rendition, sized
for the glass. Upload was worse: 56k modems, roughly 4 KB/s upstream. A
single full-size photo took a minute or more to send. And a grid page of 42
thumbnails at ~1 KB each existed because that was what dial-up could paint
before you gave up.

This is why every Webshots photo exists in exactly three renditions, and why
recovery quality is graded the way it is:

| Suffix | Resolution | What it was for |
|---|---|---|
| `_fs.jpg` | up to 1280×960 (era-dependent; early files vary) | "Full size" — the camera's actual output. The prize. |
| `_ph.jpg` | 800×600 | "Photo size" — the on-page viewing copy, sized for CRTs |
| `_th.jpg` | 100×75 | Thumbnail — the dial-up grid unit |

---

## 2. Investigation and Methodology

### 2.1 Establishing the surviving route

With the raw megawarcs 401-walled and the index dark, the investigation
established that everything Archive Team captured was **ingested into the
Wayback Machine**. That means the *playback* system and its **CDX API**
(the Wayback Machine's URL-to-capture index) constitute a complete, publicly
navigable copy of the freeze-frame data. The 401s on the raw blobs stop
mattering.

Recovery therefore reduces to a URL-archaeology problem: given a screen name,
reconstruct every URL the 2002–2012 site *would have served* for that user,
and ask Wayback for each one.

### 2.2 Site archaeology: three eras of URL architecture

Webshots was rebuilt several times, and each era speaks a different dialect.
The tool implements all of them:

**Crawl era (~2006–2012)** — what Archive Team captured:

```
community.webshots.com/user/NAME            profile (paginated /NAME/2, /NAME-date/0)
SUBDOMAIN.webshots.com/album/ID             album; grid paginates ?start=N
SUBDOMAIN.webshots.com/photo/LONGID         photo detail page
thumbNN.webshots.net/t/A/B/path/ID_th.jpg   thumbnails
imageNN.webshots.com/NN/path/ID_fs.jpg      full-size images
```

**Old era (~2002–2005)** — reachable only through ordinary Wayback crawls:

```
community.webshots.com/album/ID             albums; paginate by PATH: /album/ID/1
thumbN.webshots.com/s/thumbM/path/ID_th.jpg thumbnails (.com, /s/ paths)
community.webshots.com/sym/imageM/path/ID_fs.jpg   full-size images
```

Two structural discoveries here carried the whole old-era recovery:

1. In `/s/thumbM/` thumbnails, the **host** digit `N` is a per-image load
   balancer — the same album serves thumbnails from `thumb1` through `thumb9`
   interchangeably. It encodes nothing.
2. The **path** digit `M` is real: it maps directly to the image path
   `community.webshots.com/sym/imageM/…`. Verified against the archived 2003
   photo page for `71105081mpCGrT`, the one photo page from that album the
   2003 crawlers happened to save.

### 2.3 The image-server problem (the finding that mattered most)

Every prior Webshots recovery tool assumed you could derive a photo's image
URL from its thumbnail URL: swap `thumb13` for `image13`, swap `_th` for
`_fs`, done. This assumption is false, and it is why those tools missed
almost everything.

Live CDX probes established the crawl-era mapping is not a mapping at all:

| Thumbnail host | Actual image host | Photo |
|---|---|---|
| `thumb13` | `image04` | `113686093oWWsjM` |
| `thumb13` | `image12` | `149910057gOoGRH` |
| `thumb13` | `image20` | `331307972aadgQz` |

The image server number is **not derivable from any part of the thumbnail
URL**. The only authoritative source is the **photo detail page**, whose
`<img src>` names the real server. The tool therefore resolves every
crawl-era photo through its archived detail page: one extra request per
photo, in exchange for recovery rates going from near-zero to near-total. As
a side effect, the detail page also yields the photo's **original caption**,
which comes home in the manifest and gallery.

### 2.4 The fallback ladder

Archived coverage is uneven. Pages without images, images without pages,
full-size captured as a 404 error page (the crawler arrived after the image
server gave up, and Wayback faithfully preserved the failure). Every photo
descends:

```
real _fs  →  real _ph  →  derived-guess _fs/_ph  →  archived thumbnail
```

Every downloaded body is validated by JPEG magic bytes, never by HTTP status.
Definitive absence (a true 404 on every candidate) is cached in a marker file
so future runs skip it. Anything ambiguous gets retried forever on purpose,
because the Internet Archive occasionally backfills.

### 2.5 Tests and research

I didn't take any of this on trust. Every claim got hammered against the
live archive until it broke or held: the non-derivable image servers, the
CDX `limit=-1` truncation footgun, the old-era host-digit red herring, the
filmstrip/grid double-emission of thumbnails. That process confirmed
twenty-two bugs in earlier versions of this tool, several of which would
have silently cost users most of their photos. Nothing that survived it has
been proven wrong since, and §6 is a standing invitation to try.

---

## 3. Findings

1. The photographs are not lost. The 2012 deletion destroyed the origin
   server; the Archive Team crawl, ingested into the Wayback Machine,
   preserves a recoverable copy of most public content.
2. The decade of apparent inaccessibility traces to lost tooling. The data
   itself never went anywhere.
3. Naive URL derivation — the design basis of every prior recovery tool — is
   unsound and silently loses nearly all photos.
4. Public albums from fall 2012 recover at high rates, frequently at original
   camera resolution.
5. Pre-2012 deletions are partially recoverable through era-specific URL
   grammars; early-era image coverage is patchy and thumbnail-only recovery
   is common.
6. Private albums were never crawled and are unrecoverable by any method.

## 4. Probable Cause

The National Transportation Safety Board of this README determines the
probable cause of this accident to be **controlled flight into terrain by
site ownership**, with contributing factors: (1) the industry-wide belief,
circa 2004, that websites are a form of permanent storage; (2) loss of the
sole extraction facility in 2016 with no replacement; and (3) subsequent
access restriction of the raw wreckage.

## 5. Recommendations

**To former Webshots users:** run `search yourscreenname`. It costs nothing,
takes about a minute, and your mom's albums might be in there.

**To builders working the Internet Archive:** the CDX API is the whole game.
Know that `limit=-1` means "last row," that playback rewrites hrefs in two
different shapes, and that an archived HTTP 404 is still a 200 from Wayback.
Validate bodies, not statuses.

**To the Internet Archive:** I have nothing to recommend to you. You kept
105.9 TB of strangers' family photos alive for fourteen years. Thank you.

## 6. Public Assistance Requested

My statement above stands: *now I just need everyone to break it again.*
If a screen name that should work comes back empty, an album recovers
partially, or an era dialect surfaces that this docket doesn't describe,
[file a report](../../issues) with the screen name. Every failure mode gets
investigated. That's how the last twenty-two got fixed.

---

## Appendix A: Glossary of Designators

| Term | Meaning |
|---|---|
| **FS / `_fs.jpg`** | "Full size" — the camera-resolution original, up to 1280×960 in the era's typical 1.3 MP frame |
| **PH / `_ph.jpg`** | "Photo size" — the 800×600 viewing copy, sized for SVGA-era CRT monitors |
| **TH / `_th.jpg`** | Thumbnail, 100×75 — the dial-up-era grid unit |
| **WARC** | Web ARChive format — a crawl's raw HTTP requests/responses in one file; the preservation standard |
| **Megawarc** | Archive Team's ~50 GB bundle of many WARCs; the freeze-frame collection is 2,437 of them |
| **CDX** | The index format (and Wayback's query API) mapping URLs to captures — timestamp, status, digest, offset |
| **Wayback `im_` modifier** | Playback flag requesting the raw archived image bytes instead of a rewritten HTML page |
| **Archive Team** | Volunteer collective performing emergency backups of dying websites since 2009 |
| **Freeze-frame** | The `webshots-freeze-frame` collection at archive.org — the wreckage this docket concerns |
| **LANDED / AT GATE / MISSED APCH** | This tool's recovery callouts — recovered / already on disk / genuinely not in the archive |

## Appendix B: Verified Reference Artifacts

- Crawl-era mismatch evidence: photos `113686093oWWsjM` (thumb13→image04),
  `149910057gOoGRH` (thumb13→image12), `331307972aadgQz` (thumb13→image20)
- Old-era mapping evidence: photo page `71105081mpCGrT`, capture
  `20030508174135` → `community.webshots.com/sym/image4/0/50/81/…`
- Restriction evidence: `archive.org/metadata/webshots-freeze-frame-*` →
  `access-restricted-item: true`; index item `is_dark: true` (2026-07-08)
