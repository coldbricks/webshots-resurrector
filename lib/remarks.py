"""FLIGHT PLAN REMARKS — local notes on screen names.

"bexbee12" is a callsign; "Becca from high school" is who it was.
Remarks live in remarks.json next to where you run the tool, stay on
your machine, and are never uploaded anywhere.  Real flight plans put
free text behind RMK/ — so do we.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

REMARKS_FILE = "remarks.json"


def _path() -> str:
    return os.path.join(os.getcwd(), REMARKS_FILE)


def load_remarks() -> dict[str, dict]:
    """Load {name_lower: {name, rmk, updated}}; empty dict if none yet."""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_remark(name: str, text: str) -> dict[str, dict]:
    """Set (or clear, with empty text) the remark for a screen name.

    Atomic write — a crash mid-save must never eat the whole file.
    """
    remarks = load_remarks()
    key = name.lower()
    if text.strip():
        remarks[key] = {
            "name": name,
            "rmk": text.strip(),
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    else:
        remarks.pop(key, None)

    fd, tmp = tempfile.mkstemp(
        dir=os.getcwd(), prefix=".remarks_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(remarks, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _path())
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return remarks


def remark_for(remarks: dict[str, dict], name: str) -> str | None:
    entry = remarks.get(name.lower())
    return entry["rmk"] if entry else None
