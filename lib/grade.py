"""Recovery grade — wreckage category, not pilot score.

CAT labels borrow approach-minimum language so a controller reads them
instantly; plain English stays next to them for everyone else.
"""

from __future__ import annotations


def grade_from_counts(
    fs: int = 0,
    ph: int = 0,
    th: int = 0,
    failed: int = 0,
    skipped: int = 0,
) -> tuple[str, str]:
    """Return (code, plain_english) from variant counts.

    ``skipped`` (AT GATE) counts as recovered at whatever is on disk —
    callers should fold skip into fs/ph/th when known, or pass recovered
    totals via grade_from_stats.
    """
    recovered = fs + ph + th
    if recovered <= 0:
        return "MISSED", "nothing landed — go-around"

    fs_share = fs / recovered
    usable = (fs + ph) / recovered

    if fs_share >= 0.90:
        return "CAT III", "auto-land weather — originals almost everywhere"
    if usable >= 0.70:
        return "CAT II", "solid approach — mostly full-size or 800×600"
    if ph >= th and ph >= fs:
        return "CAT I", "visual with the field at photo-size"
    if th > (fs + ph):
        return "CIRCLING", "in the pattern on thumbnails"
    return "CAT I", "partial wreckage — mixed resolutions"


def grade_from_stats(stats: dict) -> tuple[str, str]:
    """Grade a pull totals dict (downloaded/upgraded/thumbs_only/failed/skipped).

    AT GATE (skipped) is treated as already recovered — we don't know FS vs PH
    from the counter alone, so skipped boosts the 'usable' pool as PH-weight
    unless the caller passes album-level detail via grade_from_albums.
    """
    fs = int(stats.get("downloaded", 0))  # imperfect: downloads mix fs/ph
    # Prefer explicit keys when present (Wave 1+ manifests may add them)
    if "fs" in stats or "ph" in stats:
        return grade_from_counts(
            fs=int(stats.get("fs", 0)),
            ph=int(stats.get("ph", 0)),
            th=int(stats.get("thumbs_only", 0) or stats.get("th", 0)),
            failed=int(stats.get("failed", 0)),
        )
    # Fall back: count recovered mass; upgraded implies FS wins
    upgraded = int(stats.get("upgraded", 0))
    thumbs = int(stats.get("thumbs_only", 0))
    skipped = int(stats.get("skipped", 0))
    downloaded = int(stats.get("downloaded", 0))
    # Rough: treat upgraded + half of downloaded as FS-ish, rest PH-ish
    fs_est = upgraded + max(0, downloaded - upgraded) // 2
    ph_est = downloaded - (downloaded - upgraded) // 2 + skipped
    if upgraded:
        fs_est = upgraded + max(0, downloaded // 3)
        ph_est = max(0, downloaded - fs_est) + skipped
    return grade_from_counts(fs=fs_est, ph=ph_est, th=thumbs)


def grade_from_albums(albums: list[dict]) -> tuple[str, str]:
    """Accurate grade from per-photo manifest records."""
    fs = ph = th = failed = 0
    for album in albums:
        for p in album.get("photos") or []:
            v = p.get("variant")
            if v == "fs":
                fs += 1
            elif v == "ph":
                ph += 1
            elif v == "th":
                th += 1
            elif v == "skip":
                # Infer from filename when possible
                f = (p.get("file") or "").lower()
                if f.endswith("_fs.jpg"):
                    fs += 1
                elif f.endswith("_th.jpg"):
                    th += 1
                else:
                    ph += 1
            elif v == "failed":
                failed += 1
    return grade_from_counts(fs=fs, ph=ph, th=th, failed=failed)


def count_variants(albums: list[dict]) -> dict[str, int]:
    """Return {fs, ph, th, failed, skip} from album photo records."""
    out = {"fs": 0, "ph": 0, "th": 0, "failed": 0, "skip": 0}
    for album in albums:
        for p in album.get("photos") or []:
            v = p.get("variant")
            if v == "fs":
                out["fs"] += 1
            elif v == "ph":
                out["ph"] += 1
            elif v == "th":
                out["th"] += 1
            elif v == "skip":
                out["skip"] += 1
                f = (p.get("file") or "").lower()
                if f.endswith("_fs.jpg"):
                    out["fs"] += 1
                elif f.endswith("_th.jpg"):
                    out["th"] += 1
                else:
                    out["ph"] += 1
            elif v == "failed":
                out["failed"] += 1
    return out
