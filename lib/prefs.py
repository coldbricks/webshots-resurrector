"""Local user preferences — .ppty_prefs.json at the repo root.

Git-ignored, machine-local, tiny. Holds the Training/Professional mode
choice and nothing the user would mind losing.
"""

from __future__ import annotations

import json
import os

_PREFS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".ppty_prefs.json",
)


def load_prefs() -> dict:
    try:
        with open(_PREFS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_pref(key: str, value) -> None:
    prefs = load_prefs()
    prefs[key] = value
    try:
        tmp = _PREFS_PATH + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
        os.replace(tmp, _PREFS_PATH)
    except OSError:
        pass  # preferences are never worth crashing over
