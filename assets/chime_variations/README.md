# Chime audition pack — solid chord BEEPs

One sustained horn-style chord each. Not dual-tone.

| # | File | What |
|---|------|------|
| 1 | `chime_maj3.wav` | Major triad C–E–G |
| 2 | `chime_p4.wav` | **PRODUCTION** — power stack E–B–E |
| 3 | `chime_p5.wav` | Open fifths |
| 4 | `chime_tight.wav` | Short major blast |
| 5 | `chime_heavy.wav` | Low heavy stack |

```python
from lib.theme import synthesize_door_chime
synthesize_door_chime("assets/door_chime.wav", variant="p4")
```
