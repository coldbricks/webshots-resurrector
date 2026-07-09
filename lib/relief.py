"""Position relief — hangar Status Information Area (SIA) scan.

Maps to the public JO 7110.65 Appendix A relief idea:
PREVIEW the position from recorded status, then BRIEF, ASSUME, REVIEW.
No facility SOP content — structure only.
"""

from __future__ import annotations

import json
import os
from typing import Any


def scan_hangar(output_dir: str) -> dict[str, Any] | None:
    """Read hangar state if the bay is hot. None = cold hangar (first approach)."""
    if not os.path.isdir(output_dir):
        return None

    manifest_path = os.path.join(output_dir, "manifest.json")
    sia: dict[str, Any] = {
        "hot": False,
        "fs": 0,
        "ph": 0,
        "th": 0,
        "failed": 0,
        "fs404": 0,
        "upgradeable": 0,  # PH on disk without .fs404
        "interrupted": False,
        "prior_version": None,
        "prior_grade": None,
        "albums": 0,
        "manifest": False,
    }

    # Count markers and JPEGs on disk
    for root, _dirs, files in os.walk(output_dir):
        for name in files:
            low = name.lower()
            if low.endswith(".fs404"):
                sia["fs404"] += 1
            elif low.endswith("_fs.jpg"):
                sia["fs"] += 1
                sia["hot"] = True
            elif low.endswith("_ph.jpg"):
                sia["ph"] += 1
                sia["hot"] = True
                pid = name[: -len("_ph.jpg")]
                marker = os.path.join(root, f"{pid}.fs404")
                if not os.path.isfile(marker):
                    sia["upgradeable"] += 1
            elif low.endswith("_th.jpg"):
                sia["th"] += 1
                sia["hot"] = True

    if os.path.isfile(manifest_path):
        sia["manifest"] = True
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            sia["prior_version"] = data.get("version")
            sia["interrupted"] = bool(data.get("interrupted"))
            sia["prior_grade"] = data.get("grade")
            albums = data.get("albums") or []
            sia["albums"] = len(albums)
            # Prefer disk counts; fill failed from last totals if present
            totals = data.get("totals") or {}
            if totals.get("failed"):
                sia["failed"] = int(totals["failed"])
            sia["hot"] = True
        except (OSError, ValueError):
            pass

    if not sia["hot"] and not sia["manifest"]:
        return None
    return sia
