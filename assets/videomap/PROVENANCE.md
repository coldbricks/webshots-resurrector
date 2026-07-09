# N90 theater videomap — provenance (MIT-clean)

**This is not a conversion of *vice* (GPL-3.0) video maps.**

Geometry is **hand-authored for presentation** from public sources:

| Layer | Source class |
|-------|----------------|
| Airports | Public FAA airport reference positions (sectional / Chart Supplement knowledge; lat/lon) |
| Fixes | Public charted fixes / navaids commonly labeled on NY TAC / enroute |
| Coast | Simplified Long Island / NJ shoreline polyline (illustrative, not surveyed) |
| Warning areas | Public special-use airspace labels (W-105A/B, W-106) as presentation boxes |
| Range rings | Synthetic scope decoration |

**Not for navigation.** Scope glass atmosphere only.  
**Not derived from** `ZNY-N90.mappack`, vSTARS XML, or any GPL facility pack.

Rebuild rule: if you need higher fidelity, pull FAA CIFP/NASR + public shoreline and regenerate this JSON — never import *vice* vertices.
