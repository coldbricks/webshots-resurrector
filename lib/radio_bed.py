"""Optional ambient radio bed for the scope intro.

Default: synthesized HF static + faint squelch *breaks* (no sample pack
required). Guided by real squelch envelopes (abrupt open → rush → long
decay) — not roger beeps / walkie chirps.

Optional: drop custom loops in assets/radio/ (.wav/.mp3/.ogg).
Playback: pygame if available, else winsound loop for .wav.
"""

from __future__ import annotations

import math
import os
import struct
import sys
import threading
import time
import wave
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_RADIO_DIR = _ROOT / "assets" / "radio"
_DEFAULT_BED = _RADIO_DIR / "hf_bed.wav"
# v5: rare faint 400 Hz under ~15% of squelch opens (aviation power-freq nod)
_BED_VERSION = 5
_BED_VER_FILE = _RADIO_DIR / ".hf_bed_version"

_play_lock = threading.Lock()
_playing = False
_stop_flag = False
_mode: str | None = None


def radio_dir() -> Path:
    _RADIO_DIR.mkdir(parents=True, exist_ok=True)
    return _RADIO_DIR


def find_radio_files() -> list[Path]:
    d = radio_dir()
    seen: set[str] = set()
    out: list[Path] = []
    for ext in ("*.wav", "*.mp3", "*.ogg"):
        for p in d.glob(ext):
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    # Prefer user beds; never treat random packs as default over hf_bed
    user = [
        p for p in out
        if p.name.lower() != "hf_bed.wav"
        and "roger" not in p.name.lower()
    ]
    if user:
        return sorted(user, key=lambda p: p.stat().st_mtime, reverse=True)
    return sorted(
        [p for p in out if p.name.lower() == "hf_bed.wav"],
        key=lambda p: p.name.lower(),
    )


def _noise(seed: int) -> tuple[float, int]:
    seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
    return (seed / 0x7FFFFFFF) * 2.0 - 1.0, seed


def ensure_default_hf_bed(seconds: float = 16.0, rate: int = 22050) -> Path:
    """Closed-squelch hiss + rare open breaks with realistic tails.

    Envelope language taken from real squelch samples (guide only):
      hard open ~5–10 ms → open rush 40–120 ms → exp decay 80–250 ms.
    No pure-tone roger chirps.
    """
    radio_dir()
    ver_ok = (
        _DEFAULT_BED.is_file()
        and _DEFAULT_BED.stat().st_size > 1000
        and _BED_VER_FILE.is_file()
        and _BED_VER_FILE.read_text(encoding="utf-8").strip() == str(_BED_VERSION)
    )
    if ver_ok:
        return _DEFAULT_BED

    n = int(rate * seconds)
    samples: list[int] = []
    seed = 0x5A1E1E55
    lp = 0.0
    bp = 0.0

    # (start_sec, open_hold_sec, tail_sec, intensity 0..1, with_400hz)
    # irregular — like someone keying nearby, not a metronome
    # ~2/9 breaks (~22%) get a whisper of 400 Hz under the open only —
    # aviation AC power-freq nod. NOT a constant blanker. Hardly there.
    events = [
        (1.15, 0.055, 0.18, 0.55, False),
        (2.90, 0.040, 0.12, 0.40, False),
        (4.60, 0.090, 0.22, 0.70, True),   # 400 Hz
        (6.10, 0.035, 0.10, 0.35, False),
        (7.85, 0.070, 0.20, 0.60, False),
        (9.40, 0.045, 0.14, 0.45, False),
        (11.20, 0.100, 0.24, 0.75, True),  # 400 Hz
        (12.80, 0.050, 0.16, 0.50, False),
        (14.50, 0.065, 0.19, 0.55, False),
    ]

    def gate(t: float) -> tuple[float, float, float]:
        """Returns (noise_open 0..1, tail_ring 0..1, hz400_amt 0..1)."""
        noise_o, ring, hz400 = 0.0, 0.0, 0.0
        for start, hold, tail, inten, use_400 in events:
            for base in (0.0, -seconds, seconds):
                local = t - (start + base)
                if local < -0.015 or local > hold + tail:
                    continue
                if local < 0:
                    e = inten * 0.2 * (1.0 + local / 0.015)
                elif local < 0.007:
                    e = inten * (0.25 + 0.75 * (local / 0.007))
                elif local < hold:
                    e = inten
                else:
                    u = (local - hold) / max(tail, 1e-6)
                    e = inten * math.exp(-3.2 * u)
                    ring = max(ring, inten * math.exp(-5.5 * u) * (1.0 - u))
                noise_o = max(noise_o, e)
                # 400 Hz only while truly open / early tail, and only flagged events
                if use_400 and local >= 0 and local < hold + tail * 0.45:
                    # track envelope, keep quieter than the static rush
                    hz400 = max(hz400, e * 0.55)
        return max(0.0, noise_o), max(0.0, ring), max(0.0, hz400)

    for i in range(n):
        t = i / rate
        white, seed = _noise(seed)
        # colored noise: speaker + RF mush
        lp = 0.90 * lp + 0.10 * white
        bp = 0.55 * bp + 0.45 * (white - lp)

        open_amt, ring_amt, hz400_amt = gate(t)

        # Closed: whisper residual. Open: rush of static.
        closed_hiss = 0.028 * lp + 0.012 * bp
        open_rush = open_amt * (0.48 * lp + 0.32 * bp + 0.12 * white)

        # Weak carrier under open (not a roger beep — no pure end-chirp)
        carrier = 0.0
        if open_amt > 0.08:
            carrier = (
                open_amt
                * 0.05
                * math.sin(2 * math.pi * 420 * t)
                * (0.75 + 0.25 * math.sin(2 * math.pi * 3.0 * t))
            )

        # Soft ring-down as gate closes (filtered, short)
        ring = 0.0
        if ring_amt > 0.02:
            ring = (
                ring_amt
                * 0.055
                * math.sin(2 * math.pi * (640 + 90 * (1.0 - ring_amt)) * t)
            )

        # 400 Hz — aircraft electrical power frequency. Tiny. Rare.
        # Only rides selected squelch opens; never a continuous blanker.
        aviation_400 = 0.0
        if hz400_amt > 0.04:
            aviation_400 = (
                hz400_amt
                * 0.028  # very faint
                * math.sin(2 * math.pi * 400.0 * t)
            )

        # Almost subliminal pilot when closed (not 400)
        pilot = 0.008 * math.sin(2 * math.pi * 950 * t)

        sample = closed_hiss + open_rush + carrier + ring + aviation_400 + pilot

        edge = int(rate * 0.06)
        fade = 1.0
        if i < edge:
            fade = i / edge
        elif i > n - edge:
            fade = (n - i) / edge

        # overall faint
        samples.append(int(max(-1.0, min(1.0, sample * fade * 0.62)) * 9500))

    with wave.open(str(_DEFAULT_BED), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    _BED_VER_FILE.write_text(str(_BED_VERSION), encoding="utf-8")
    return _DEFAULT_BED


def start_intro_radio(*, volume: float = 0.13) -> str:
    """Start ambient bed for intro. Returns status string for UI."""
    global _playing, _stop_flag, _mode
    with _play_lock:
        stop_intro_radio()
        _stop_flag = False
        try:
            ensure_default_hf_bed()
        except Exception:
            pass
        files = find_radio_files()
        if not files:
            return "radio silent (no files)"

        path = files[0]
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=1024)
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(max(0.04, min(0.25, volume)))
            pygame.mixer.music.play(loops=-1)
            _playing = True
            _mode = "pygame"
            return f"radio bed  ·  {path.name}  ·  loop"
        except Exception:
            pass

        if path.suffix.lower() == ".wav" and sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(
                    str(path),
                    winsound.SND_FILENAME
                    | winsound.SND_ASYNC
                    | winsound.SND_LOOP
                    | winsound.SND_NODEFAULT,
                )
                _playing = True
                _mode = "winsound"
                return f"radio bed  ·  {path.name}  ·  loop"
            except Exception as exc:
                return f"radio silent ({exc})"

        return f"radio silent (need pygame for {path.suffix} or use .wav)"


def stop_intro_radio() -> None:
    """Stop ambient bed (intro end / sector open)."""
    global _playing, _stop_flag, _mode
    _stop_flag = True
    if not _playing and _mode is None:
        return
    try:
        if _mode == "pygame":
            import pygame

            if pygame.mixer.get_init():
                pygame.mixer.music.fadeout(500)
                time.sleep(0.05)
                pygame.mixer.music.stop()
        elif _mode == "winsound" and sys.platform == "win32":
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass
    _playing = False
    _mode = None


def is_playing() -> bool:
    return _playing
