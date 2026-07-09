"""Truth states — every kind of miss gets its own authored words.

"Name not found", "profile archived but albums weren't", "archive.org is
metering us", and "archive.org is down" are different griefs. Mixing them
is cruelty dressed as UX. Each state carries a controller callout, a
plain-English explanation, and exactly one suggested next move.

Used by the scope GUI. The terminal cab still carries its own authored
copy of these states from v1.6.x — if you change wording here, keep the
cab's copy in resurrector.py/lib/ui.py saying the same thing until the
CLI is wired through this matrix.
"""

from __future__ import annotations


class TruthState:
    __slots__ = ("key", "callout", "plain", "action", "action_kind", "tone")

    def __init__(self, key: str, callout: str, plain: str,
                 action: str, action_kind: str | None, tone: str):
        self.key = key
        self.callout = callout          # controller line (jargon decorates)
        self.plain = plain              # plain English (lands the plane)
        self.action = action            # one primary next move, human words
        self.action_kind = action_kind  # find | deep | retry | wait | gallery | None
        self.tone = tone                # ok | caution | alert | dim


TRUTH: dict[str, TruthState] = {
    # ── Search truths ────────────────────────────────────────────────
    "NO_PLAN": TruthState(
        "NO_PLAN",
        "NO BEACONS CORRELATED",
        "The archive has no captures for that exact screen name. Spelling "
        "is the number-one miss — Webshots names were often slightly "
        "different from what people remember.",
        "Try FIND with the first few letters — it lists every archived "
        "name that starts that way.",
        "find",
        "alert",
    ),
    "ZERO_ALBUMS": TruthState(
        "ZERO_ALBUMS",
        "STRIPS ON BOARD — NO TARGETS",
        "The profile page was archived, but no public albums were captured "
        "at this snapshot. Sometimes older snapshots hold more.",
        "Try DEEP — it sweeps every archived version of the profile, "
        "2002 through 2013.",
        "deep",
        "caution",
    ),
    # ── Archive weather (never the user's fault, never the tool's) ──
    "FLOW_CONTROL": TruthState(
        "FLOW_CONTROL",
        "FLOW CONTROL",
        "archive.org asked everyone to slow down, so we are pacing our "
        "requests on purpose. Nothing is broken, and everything already "
        "saved is safe on your machine.",
        "No action needed — the pull resumes by itself at the polite rate.",
        "wait",
        "caution",
    ),
    "FLOW_CONTROL_VPN": TruthState(
        "FLOW_CONTROL_VPN",
        "FLOW CONTROL — DATACENTER EXIT",
        "archive.org is rate-limiting the network you're on, which looks "
        "like a VPN or datacenter address. Those get metered much harder "
        "than home connections.",
        "If you're on a VPN, disconnect it (or exclude this tool) and run "
        "the same command again — it resumes where it left off.",
        "retry",
        "caution",
    ),
    "ATC_ZERO": TruthState(
        "ATC_ZERO",
        "ATC ZERO",
        "archive.org is unreachable right now. Your photos and progress "
        "are safe on disk.",
        "Try again later — the same command picks up exactly where it "
        "stopped.",
        "retry",
        "alert",
    ),
    # ── Pull outcome truths ──────────────────────────────────────────
    "COMPLETE": TruthState(
        "COMPLETE",
        "OPERATIONS NORMAL",
        "Everything the archive holds for this account is on your machine.",
        "Open the gallery — those are your photos back.",
        "gallery",
        "ok",
    ),
    "PARTIAL": TruthState(
        "PARTIAL",
        "PARTIAL RECOVERY — MISSION REPORT FOLLOWS",
        "Some photos landed and some were never archived. A partial wreck "
        "is still a landing: what's missing was usually never captured in "
        "2012, and that ceiling belongs to the archive, not to you.",
        "Open the gallery to see what made it. Re-running later sometimes "
        "finds more — the archive backfills.",
        "gallery",
        "caution",
    ),
    "ALL_TH": TruthState(
        "ALL_TH",
        "CIRCLING ON THUMBS",
        "Only small thumbnails were ever archived for these photos — the "
        "full-size images didn't make it into the 2012 crawl. Thumbnails "
        "are what survived, so thumbnails are what we saved.",
        "Open the gallery. If this account mattered to you, try DEEP once "
        "— older snapshots occasionally hold larger copies.",
        "deep",
        "caution",
    ),
    "MISSED_ALL": TruthState(
        "MISSED_ALL",
        "GO-AROUND",
        "Nothing landed on this pull. Three moves, in order: check the "
        "spelling with FIND; try DEEP for the 2002–2013 eras; and know "
        "that private albums were never archived at all — that one is an "
        "honest dead end, not a failure.",
        "Start with FIND — spelling is the most common miss.",
        "find",
        "alert",
    ),
    "HANGAR_FULL": TruthState(
        "HANGAR_FULL",
        "HANGAR FULL",
        "Your disk filled up mid-pull, so we stopped asking the archive "
        "for photos we couldn't save. Everything downloaded so far is "
        "safe.",
        "Free some space (or point -o at a bigger drive) and run the same "
        "command — it resumes without re-downloading.",
        "retry",
        "alert",
    ),
    "INTERRUPTED": TruthState(
        "INTERRUPTED",
        "POSITION RELIEF PENDING",
        "The pull stopped early, but progress was saved photo-by-photo.",
        "Run the same command again — it briefs itself on what's already "
        "at the gate and continues from there.",
        "retry",
        "caution",
    ),
}


def weather_state(last_status: int | None,
                  last_nid: str | None) -> TruthState | None:
    """Map engine transport state to a weather truth. None = clear skies.

    last_status None means no exchange has completed yet. A fresh engine
    polled mid-first-request must read as clear skies — reporting ATC
    ZERO before the archive has even been asked is how interface trust
    dies (this shipped as a live bug: the 500ms instrument poll fired
    the ATC ZERO card the same second every search started).
    """
    if last_status is None:
        return None
    if last_status == 429:
        if last_nid and "datacamp" in last_nid.lower():
            return TRUTH["FLOW_CONTROL_VPN"]
        return TRUTH["FLOW_CONTROL"]
    if last_status == 0 or last_status >= 500:
        return TRUTH["ATC_ZERO"]
    return None


def classify_recovery(counts: dict, *, interrupted: bool = False,
                      hangar_full: bool = False) -> TruthState:
    """Pick the one truth that describes a finished pull.

    counts: {fs, ph, th, failed} — grade-style variant counts.
    """
    if hangar_full:
        return TRUTH["HANGAR_FULL"]
    fs = counts.get("fs", 0)
    ph = counts.get("ph", 0)
    th = counts.get("th", 0)
    failed = counts.get("failed", 0)
    recovered = fs + ph + th
    # Interrupted beats MISSED_ALL: a pull killed in its first seconds has
    # zero landings, but "run it again" is the truth — not "check spelling".
    if interrupted:
        return TRUTH["INTERRUPTED"]
    if recovered == 0:
        return TRUTH["MISSED_ALL"]
    if fs == 0 and ph == 0 and th > 0:
        return TRUTH["ALL_TH"]
    if failed > 0:
        return TRUTH["PARTIAL"]
    return TRUTH["COMPLETE"]


def mission_report(counts: dict) -> str:
    """One plain sentence: what landed, what didn't, whose fault it isn't.

    counts may carry "transport" — the subset of failed that died on
    archive weather (5xx/network) rather than true absence. Those are
    retryable, and saying "never archived" about them would train the
    exact false absence this tool exists to prevent.
    """
    fs = counts.get("fs", 0)
    ph = counts.get("ph", 0)
    th = counts.get("th", 0)
    failed = counts.get("failed", 0)
    transport = min(counts.get("transport", 0), failed)
    absent = failed - transport
    recovered = fs + ph + th
    total = recovered + failed
    if total == 0:
        return "No photos were on the board for this pull."
    bits = []
    if fs:
        bits.append(f"{fs} full-size original{'s' if fs != 1 else ''}")
    if ph:
        bits.append(f"{ph} at photo size (800×600)")
    if th:
        bits.append(f"{th} as thumbnails only")
    landed = ", ".join(bits) if bits else "nothing"
    line = f"{recovered} of {total} landed — {landed}."
    if absent:
        line += (
            f" {absent} never made it into the archive; that's the 2012 "
            "crawl's ceiling, not yours."
        )
    if transport:
        line += (
            f" {transport} failed on archive weather this pass and will be "
            "retried automatically next run."
        )
    return line
