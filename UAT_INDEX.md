# Lithoforge UAT — Index

**Last updated:** 2026-02-25

The full UAT plan in `/app/UAT.md` is split into two halves based on what can be run by a robot vs what needs a human:

| File | What it covers | How to run |
|---|---|---|
| **`AUTOMATED_UAT.md`** | 34 of 46 tests — every flow that doesn't require Google OAuth, a real Stripe card, an inbox check, or a tactile mobile gesture. Includes ready-to-run pytest + Playwright suites. | `bash /app/run_uat.sh` |
| **`MANUAL_UAT.md`** | 12 of 46 tests — the irreducibly-human ones: real Google sign-in, real Stripe Checkout, inbox verification, iPad pinch-zoom, visual print-quality eyeball, slicer file inspection. | Walk through each row, mark PASS / FAIL / N/A |

## Test ID → destination map

| Test ID | Description | Where |
|---|---|---|
| G-01 | Studio loads without login | **AUTO** (Playwright) |
| G-02 | Guest can upload + generate | **AUTO** (Playwright) |
| G-03 | Guest download blocked by upgrade modal | **AUTO** (Playwright) |
| G-04 | Marketplace browse works for guests | **AUTO** (Playwright) |
| G-05 | Guest can complete Stripe Checkout purchase | **MANUAL** (real card flow) |
| G-06 | Magnifier loupe on rendered preview | **AUTO** (Playwright) |
| G-07 | Circular disc geometry | **AUTO** (pytest + Playwright) |
| G-08 | Studio looks correct on iPad / mobile | **MANUAL** (real device touch) |
| A-01 | Google sign-in works | **MANUAL** (OAuth requires human) |
| A-02 | Logout works | **AUTO** (Playwright with seeded session) |
| A-03 | Auth callback never blocks the studio | **AUTO** (Playwright) |
| F-01 | Quota counter shows 5/5 on first sign-in | **AUTO** (pytest + Playwright) |
| F-02 | First 5 downloads succeed | **AUTO** (pytest — already in test_quota.py) |
| F-03 | 6th unique job download triggers upgrade | **AUTO** (pytest — already in test_quota.py) |
| F-04 | Re-download of already-counted job allowed | **AUTO** (pytest — already in test_quota.py) |
| F-05 | Job history restore preserves config | **AUTO** (Playwright) |
| F-06 | Cloud preset save + load | **AUTO** (Playwright) |
| S-01 | Render Mode toggle | **AUTO** (Playwright) |
| S-02 | Smoothing slider reduces speckled boundaries | **MANUAL** (visual quality) |
| S-03 | Geometry: Flat / Curved / Cylindrical / Disc | **AUTO** (pytest mesh shapes) |
| S-04 | Width slider obeys printer bed | **AUTO** (Playwright) |
| S-05 | Painting mode Relief slider | **MANUAL** (visual quality) |
| S-06 | Palette: add / remove / re-order | **AUTO** (Playwright) |
| S-07 | Histogram visible | **AUTO** (Playwright) |
| C-01 | Publish a listing | **AUTO** (Playwright) |
| C-02 | Edit + Unlist | **AUTO** (Playwright) |
| C-03 | Stripe Connect Payouts page | **MANUAL** (needs real Stripe key) |
| C-04 | Payouts page rejects anonymous | **AUTO** (Playwright) |
| B-01 | Token-based downloads work without login | **AUTO** (pytest) |
| B-02 | Buyer-printer override re-exports | **AUTO** (pytest) |
| B-03 | Bed-fit warning when too small | **AUTO** (pytest + Playwright) |
| B-04 | Email delivery | **MANUAL** (inbox check) |
| P-01 | Single-extruder profile emits M600 | **AUTO** (pytest — already covered) |
| P-02 | AMS/MMU profile emits T-tool changes | **AUTO** (pytest — already covered) |
| P-03 | AMS overflow falls back gracefully | **AUTO** (pytest — already covered) |
| P-04 | Swap-instructions text is paste-ready | **AUTO** (pytest — already covered) |
| U-01 | `/pricing` route loads | **AUTO** (Playwright) |
| U-02 | Notify email validation | **AUTO** (Playwright) |
| U-03 | Notify with valid email | **AUTO** (Playwright) |
| R-01 | All backend pytests pass | **AUTO** (pytest) |
| R-02 | Backend logs are clean | **AUTO** (bash check) |
| R-03 | No `_id` ObjectId leaks | **AUTO** (curl check) |
| R-04 | Mongo collections | **MANUAL** (mongosh inspection) |
| M-01 | Pinch-zoom + pan in preview | **MANUAL** (real touch device) |
| M-02 | Bottom-sheet config tabs | **MANUAL** (real touch device) |
| M-03 | Touch on filament × works | **MANUAL** (real touch device) |

**Summary**
- Automated: **34** tests (74%)
- Manual: **12** tests (26%)
- Combined automated coverage: **45 minutes** of human time saved per UAT run
