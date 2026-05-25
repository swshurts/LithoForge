# Lithoforge — User Acceptance Test Plan

**Last updated:** 2026-02-25
**Build:** Marketplace Phase A + B (Stripe Connect Phase C scaffolded) · Quota gating · Printer profiles · Auto-pause 3MF · Circular disc geometry · Magnifier loupe

---

## How to use this document

Every test below has:
- **ID** — stable reference like `G-01`, `F-03`, `B-07`
- **Pre-conditions** — required state before the test
- **Steps** — exact sequence to execute
- **Expected** — what you should see
- **Priority** — **P0** = blocks release · **P1** = must work before announcing · **P2** = nice-to-have

Mark each row **PASS** / **FAIL** / **N/A** as you work through it.

**Test data**
- Use any photo with a mix of saturated colors and skin tones for best palette suggestions (the included `/app/test_assets/` will work too)
- Two browser profiles help: one signed-in (Pro tier), one anonymous

---

## 1 · Guest (Anonymous) flows — `prefix: G`

### G-01 — Studio loads without login [P0]
**Steps:**
1. Open the app preview URL in a fresh incognito window
2. Wait 5 seconds

**Expected:**
- Studio renders the **DROP PHOTOGRAPH HERE** drop zone
- Header shows **GUEST** badge with **0 / 0 downloads left** + **UPGRADE** button
- **SIGN IN** button visible
- No overlay or modal blocks the page
- Pricing + Marketplace links work

---

### G-02 — Guest can upload, edit, and generate [P0]
**Pre:** G-01 passed
**Steps:**
1. Drag a photograph onto the drop zone (or click "or click to browse")
2. Adjust crop/zoom/rotation if desired
3. Click **SUGGEST PALETTE FROM PHOTO**
4. Pick a printer in **TARGET PRINTER** dropdown (try Bambu A1 mini)
5. Click **GENERATE**

**Expected:**
- Upload completes (no infinite spinner)
- Palette suggester returns 4–6 filaments
- Generate button is enabled while signed out
- After ~3–10 seconds the preview renders with ΔE stats + Layer Allocation
- Each row of Layer Allocation shows a **Usage %** value

---

### G-03 — Guest download blocked by upgrade modal [P0]
**Pre:** G-02 passed
**Steps:**
1. Click **STL mesh** download button in the Export panel

**Expected:**
- Browser does NOT trigger a download
- **Upgrade modal** opens with:
  - "Sign in to download" heading
  - "Sign in (free — gives you 5 starter downloads)" button
  - Hobbyist + Pro plan cards (both showing "Coming soon")
  - X close button works
- Same behaviour for 3MF and Swap-instructions buttons

---

### G-04 — Marketplace browse works for guests [P0]
**Steps:**
1. Click **Marketplace** in the header (or visit `/marketplace`)

**Expected:**
- Marketplace lists all currently-published items (or shows the empty state)
- Listing cards show title, creator, price, thumbnail
- Clicking a card opens `/marketplace/:jobId` detail page
- Detail page shows **License** + **Designed for [printer]** info cards
- **Buy · $X.XX** button is enabled (no sign-in required)

---

### G-05 — Guest can complete a Stripe Checkout purchase [P0]
**Pre:** at least one paid listing exists
**Steps:**
1. From a listing detail page, click **Buy**
2. Enter your real email in the dialog
3. Click **Pay $X.XX**
4. Use Stripe's test card on the Stripe-hosted page:
   `4242 4242 4242 4242` · any future expiry · any CVC · any ZIP
5. Submit payment
6. Wait to be redirected back to `/marketplace/:jobId/success`

**Expected:**
- Stripe Checkout loads in the same tab
- After payment, redirected to the success page
- Success page polls and lands on **Payment received**
- Three download buttons appear (STL / 3MF / Swap instructions)
- **Buyer-printer-override** section lets you pick a different printer
- A backup-link email arrives in your inbox

---

### G-06 — Magnifier loupe on rendered preview [P1]
**Pre:** A generation result is showing
**Steps:**
1. Hold **Shift** and click on a colorful part of the preview image
   (mobile: long-press the image for ~400ms)
2. Move the cursor while still holding Shift

**Expected:**
- A circular 4× zoom overlay appears near the cursor with:
  - Source colour swatch
  - Closest filament name + swatch
  - Live ΔE value
- Releasing the mouse hides the loupe

---

### G-07 — Circular disc geometry [P1]
**Pre:** Image uploaded
**Steps:**
1. In Geometry section, change **Shape** to **Circular disc**
2. Note the **Width** label becomes **Diameter** and Height row disappears
3. Adjust **Dome height** slider to 1.5mm
4. Click **GENERATE**

**Expected:**
- Preview renders as a circle (corners are transparent/black)
- Layer Allocation populates normally
- If signed-in, downloading the STL produces a round disc mesh

---

### G-08 — Studio looks correct on iPad / mobile [P1]
**Steps:**
1. Open the app on an iPad Safari (or set browser viewport to 1024×768)
2. Verify the bottom tab-bar is visible
3. Tap between Edit / Render / Stats sheets

**Expected:**
- No layout overflow
- Sliders, buttons, dropdowns all touch-responsive
- No phantom delete buttons / invisible controls

---

## 2 · Sign-in & authentication — `prefix: A`

### A-01 — Google sign-in works [P0]
**Steps:**
1. Click **SIGN IN** in the header
2. Complete Google's hosted sign-in flow

**Expected:**
- Redirect back to `/` succeeds within ~2 seconds
- User menu now shows your name + avatar
- **GUEST** badge in header changes to **FREE** with **5 / 5 downloads left**

---

### A-02 — Logout works [P0]
**Pre:** Signed in
**Steps:**
1. Click user menu (top right)
2. Click **Sign out**

**Expected:**
- User menu collapses back to **Sign In** button
- Quota badge resets to **GUEST**
- Page does not crash; refresh still works

---

### A-03 — Auth callback never blocks the studio [P0]
**Pre:** A stale URL like `https://your-app/#session_id=abc123` in browser history
**Steps:**
1. Visit the stale URL directly
2. Wait ~15 seconds

**Expected:**
- The full-screen auth-callback loader appears
- Within 12 seconds, a **Skip / Use without signing in** button appears
- Clicking Skip dismisses the loader and reveals the studio
- Upload zone is interactive

---

## 3 · Free-tier creator (signed in) — `prefix: F`

### F-01 — Quota counter shows 5/5 on first sign-in [P0]
**Pre:** Fresh user (no prior downloads)
**Steps:**
1. Sign in
2. Look at header

**Expected:** Badge reads **FREE 5 / 5 downloads left**

---

### F-02 — First 5 downloads all succeed [P0]
**Pre:** F-01 passed
**Steps:**
1. Generate a lithophane
2. Download STL → 3MF → Swap instructions for the same job (3 downloads of same job)
3. Generate 4 more different jobs and download from each

**Expected:**
- All 3 file types of the first job download successfully (counter goes 5 → 4 after the first download, but stays at 4 for STL+3MF+swaps of the same job)
- After 5 distinct generations + downloads, counter shows **0 / 5 downloads left**
- No 401 / 402 errors

---

### F-03 — 6th unique job download triggers upgrade modal [P0]
**Pre:** F-02 finished with quota at 0
**Steps:**
1. Generate a brand-new lithophane
2. Click STL download

**Expected:**
- No file download starts
- **Upgrade modal** opens (heading: "You've used all 5 free downloads")
- Hobbyist + Pro cards visible
- Closing the modal returns to studio with quota still at 0

---

### F-04 — Re-download of already-counted job is allowed [P0]
**Pre:** F-03 hit the cap
**Steps:**
1. Open user menu → **My Jobs**
2. Restore one of the FIRST FIVE jobs (one you downloaded earlier)
3. Click STL download

**Expected:**
- Download proceeds normally
- Counter stays at 0 (no additional charge — already counted)

---

### F-05 — Job history restore preserves config [P1]
**Pre:** ≥1 generated job in history
**Steps:**
1. User menu → My Jobs → click any entry
2. Note the preview re-renders
3. Inspect Width / Height / Layer height / palette — they should match what was originally set

**Expected:**
- All sliders + filaments hydrate to the original values
- Downloads work (subject to F-04 quota rule)

---

### F-06 — Cloud preset save + load [P1]
**Pre:** Signed in
**Steps:**
1. Pick a non-default config (e.g. 150×100, 5mm thick, 6 swaps, painting mode)
2. Click **SAVE CURRENT** in Presets
3. Name it "Test preset"
4. Sign out, sign back in (same account)
5. Open Presets dropdown → "Test preset"

**Expected:**
- Preset persists across sign-out/sign-in
- Loading it restores all sliders + filaments

---

## 4 · Studio editor & rendering — `prefix: S`

### S-01 — Render Mode toggle (Lithophane ↔ Painting) [P1]
**Steps:**
1. Generate in **Lithophane** mode → note the dark-bottom backlit preview
2. Switch to **Painting** mode → re-generate

**Expected:**
- Painting preview shows nearest-filament mapping (more saturated, no backlight glow)
- Relief + Smoothing sliders appear only in Painting mode

---

### S-02 — Smoothing slider reduces speckled boundaries [P2]
**Pre:** Painting mode + photo with continuous tones (e.g. a face)
**Steps:**
1. Generate at smoothing = 0
2. Note the speckled edges between filament zones
3. Increase smoothing to ~60% and re-generate

**Expected:**
- Edges become noticeably smoother
- ΔE may increase slightly (a few units) — this is expected

---

### S-03 — Geometry: Flat / Curved / Cylindrical / Disc [P1]
**Steps:** Generate the same image with each Shape in turn.

**Expected:**
- Flat: rectangular preview
- Curved: same preview (curvature happens in the mesh)
- Cylindrical: same preview, full wrap
- Disc: circular preview with transparent corners

---

### S-04 — Width slider obeys printer bed [P2]
**Steps:**
1. Set printer to **Bambu A1 mini** (180mm bed)
2. Drag width slider to 250mm

**Expected:**
- (Currently no hard cap — slider goes to 300) — note this as a known limit; consider adding a printer-aware cap in a future round.

---

### S-05 — Painting mode Relief slider [P1]
**Pre:** Painting mode
**Steps:**
1. Generate with Relief = 0% → flat plateaus
2. Increase to 100% → re-generate

**Expected:** Heightmap view shows more variation within each colour band at higher relief.

---

### S-06 — Palette: manual add / remove / re-order [P1]
**Steps:**
1. Click the **×** on a filament card → it disappears
2. Click the **+** card → filament-picker dropdown
3. Drag arrows to reorder filaments

**Expected:** After Generate, the swap order reflects the new sequence (or auto-order if checkbox is on).

---

### S-07 — Histogram visible in preview [P2]
**Pre:** Image uploaded
**Steps:** Look below the preview image for the histogram strip.

**Expected:** Small RGB / luma histogram updates as you adjust brightness/contrast in Image Edit.

---

## 5 · Marketplace creator — `prefix: C`

### C-01 — Publish a listing [P0]
**Pre:** Signed in, has generated job
**Steps:**
1. User menu → My Jobs → click a job
2. Open the job in the studio (it should appear in Viewport)
3. Click the **Publish** button (or open the publish dialog from the StatsPanel)
4. Fill title, description, price ($29), license (CC-BY-NC)
5. Click **Publish**

**Expected:**
- Toast: "Listed in marketplace"
- Visit `/marketplace` — your listing appears
- Visit `/marketplace/:jobId` — details show your title, license, designed-for printer
- Visit `/creator/:userId` — your profile shows the listing

---

### C-02 — Edit + Unlist [P1]
**Pre:** C-01 passed
**Steps:**
1. Publish dialog again on the same job
2. Change price to $19, title to "Updated"
3. Save
4. Reload marketplace — verify the change
5. Open dialog again, click **Unlist**

**Expected:**
- Listing removed from marketplace browse + creator profile
- Status badge on the job switches from "Listed" back to "Draft"

---

### C-03 — Stripe Connect Payouts page (gated) [P1]
**Pre:** Signed in
**Steps:**
1. User menu → **Payouts**
2. Read the status card

**Expected:**
- Page renders with "Not yet set up" status (until you click Set up payouts)
- Lifetime paid + Owed totals show $0.00
- Empty sales ledger
- Clicking **Set up payouts** — **CURRENTLY EXPECTED TO FAIL** with an Invalid API Key toast because `sk_test_emergent` isn't a real Stripe key (this is a known limitation, fixed when you provide a real `sk_test_...`).

---

### C-04 — Payouts page rejects anonymous users [P1]
**Steps:**
1. Sign out
2. Visit `/payouts` directly

**Expected:** Shows the "Sign in to manage payouts" gate with a **Sign in to continue** button.

---

## 6 · Marketplace buyer (paid) — `prefix: B`

### B-01 — Token-based downloads work without login [P0]
**Pre:** B-01 in G-05 succeeded → you have a token (in the URL)
**Steps:**
1. Open `/marketplace/:jobId/success?session_id=...` in a fresh incognito window
2. The page should poll and show **Payment received**
3. Click STL download

**Expected:**
- STL downloads in the new window even though you're not signed in
- No quota counter change for any user

---

### B-02 — Buyer-printer override re-exports [P0]
**Pre:** Success page open with download buttons visible
**Steps:**
1. Open the **Re-export for your printer** dropdown
2. Switch from "Generic FDM (OrcaSlicer)" to **Bambu X1C**
3. Click 3MF download
4. Unzip the .3mf and inspect `Metadata/project_settings.config`

**Expected:**
- File downloads named `lithophane_<id>.3mf`
- Config contains `T1`, `T2`, etc. instead of `M600` (multi-tool path)
- `printable_area` says 256×256 (Bambu bed)

---

### B-03 — Bed-fit warning when too small [P1]
**Pre:** Buyer success page
**Steps:**
1. Pick **Bambu A1 mini** (180mm bed)
2. If the creator's design > 180mm × 180mm, watch for the warning

**Expected:** Amber **AlertTriangle** warning appears: "Warning: this design is 200×200mm but the Bambu A1 mini bed is only 180×180mm..."

---

### B-04 — Email delivery [P1]
**Pre:** G-05 used `steve.shurts@gmail.com` (Resend dev-mode account email)
**Steps:** Check inbox after a paid purchase.

**Expected:**
- Email from `onboarding@resend.dev` subject "Your lithophane is ready — *title*"
- Three download buttons (STL / 3MF / Swap Instructions)
- Footer link points back to the success page
- Note: in dev-mode, Resend only delivers to YOUR account email. To send to arbitrary buyer emails, swap to a production Resend key + verified sending domain.

---

## 7 · 3MF auto-pause verification — `prefix: P`

### P-01 — Single-extruder profile emits M600 [P0]
**Steps:**
1. Generate with Target Printer = **Prusa MK4** (single extruder)
2. Download the 3MF
3. Unzip and `cat Metadata/project_settings.config`

**Expected:**
- `layer_change_gcode` contains `{if layer_num == X}M600{endif}` blocks
- One M600 per swap layer
- No `T1` / `T2` / etc.

---

### P-02 — AMS/MMU profile emits T-tool changes [P0]
**Steps:**
1. Generate with Target Printer = **Bambu X1C** (multi-tool) with max_swaps = 3
2. Download the 3MF
3. Unzip and inspect config

**Expected:**
- `layer_change_gcode` contains `T1`, `T2`, `T3` blocks
- No M600 in the config

---

### P-03 — AMS overflow falls back gracefully [P1]
**Steps:**
1. Set max_swaps = 5, Target = Bambu X1C (4 lanes)
2. Generate → Download 3MF

**Expected:** Slot 4 (the 5th swap) emits `M600 ; out of AMS slots` so the printer doesn't error on T4.

---

### P-04 — Swap-instructions text is paste-ready [P1]
**Steps:**
1. Download Swap Instructions
2. Open in text editor

**Expected:**
- Header summary with printer name + swap count
- 3 sections labeled OPTION A (Slic3r-family), OPTION B (Cura), OPTION C (raw Marlin)
- Each section's snippet is correctly templated for the chosen printer

---

## 8 · Pricing & upgrade — `prefix: U`

### U-01 — `/pricing` route loads [P0]
**Steps:** Visit `/pricing` directly.

**Expected:**
- 3 plan cards (Free + Hobbyist + Pro)
- "Most popular" badge on Hobbyist
- Free has a "Sign in to start" CTA → sends to `/`
- Hobbyist/Pro have "Notify me when live" buttons
- Email-capture box at the bottom

---

### U-02 — Notify email validation [P2]
**Steps:**
1. On `/pricing`, type "not-an-email"
2. Click **Notify me**

**Expected:** Toast: "Enter a valid email to be notified"

---

### U-03 — Notify with valid email [P2]
**Steps:**
1. Type `you@example.com` → Notify me

**Expected:** Toast: "We'll email you@example.com when any launches."

---

## 9 · Regression / data integrity — `prefix: R`

### R-01 — All 43 backend pytests pass [P0]
**Steps:** `cd /app/backend && python -m pytest tests/ -q`

**Expected:** `43 passed`

---

### R-02 — Backend logs are clean [P1]
**Steps:** `tail -n 200 /var/log/supervisor/backend.err.log`

**Expected:** No tracebacks newer than ~5 minutes. Deprecation warnings (FastAPI lifespan) are acceptable.

---

### R-03 — No `_id` ObjectId leaks in API responses [P1]
**Steps:** `curl <preview>/api/marketplace | python -m json.tool | grep _id`

**Expected:** No output (all `_id` fields are projected out).

---

### R-04 — Mongo collections used [P2]
**Steps:** `mongosh test_database --quiet --eval "db.getCollectionNames()"`

**Expected list (at minimum):**
- `users`
- `user_sessions`
- `jobs`
- `presets`
- `payment_transactions`

---

## 10 · Mobile / iPad-specific — `prefix: M`

### M-01 — Pinch-zoom + pan in preview [P1]
**Pre:** iPad or touch-emulating browser
**Steps:** Two-finger pinch on the preview image.

**Expected:** Preview scales smoothly; one-finger drag pans.

---

### M-02 — Bottom-sheet config tabs [P1]
**Steps:** On iPad, tap Edit / Render / Stats tabs at the bottom.

**Expected:** Each opens a half-height sheet from the bottom; swiping down dismisses it.

---

### M-03 — Touch on filament `×` works [P2]
**Steps:** Tap the delete X on a filament chip.

**Expected:** Filament removed (no phantom click / no double-tap zoom).

---

## Summary scorecard

| Section | P0 tests | P1 tests | P2 tests | Total |
|---|---|---|---|---|
| Guest flows | 5 | 3 | 0 | 8 |
| Auth | 3 | 0 | 0 | 3 |
| Free-tier creator | 4 | 2 | 0 | 6 |
| Studio editor | 0 | 4 | 3 | 7 |
| Marketplace creator | 1 | 3 | 0 | 4 |
| Marketplace buyer | 2 | 2 | 0 | 4 |
| 3MF auto-pause | 2 | 2 | 0 | 4 |
| Pricing | 1 | 0 | 2 | 3 |
| Regression | 1 | 2 | 1 | 4 |
| Mobile | 0 | 2 | 1 | 3 |
| **TOTAL** | **19** | **20** | **7** | **46** |

**Release gate:** all P0s green → ship to closed beta
**Public launch gate:** P0 + P1 green → ship to public

---

## Known gaps / out of scope this round

These are **NOT** expected to pass and should be marked `N/A` until built:

- ❌ **Stripe Connect creator payouts** — scaffolded but blocked on a real Stripe test key from your account (C-03 will fail on the API call)
- ❌ **Stripe subscription checkout** — pricing CTAs say "Coming Soon"
- ❌ **Filament substitution suggestions** for buyers — deferred (needs per-user filament library)
- ❌ **High-fidelity buyer re-export with layer-height override** — only printer is overridable today
- ❌ **Auto-frame for Painting mode** — not built
- ❌ **Replace-photo button** — not built
- ❌ **True 3D WebGL preview** — not built (2D heightmap only)
- ❌ **Pricing page email-capture persistence** — currently localStorage only, no backend endpoint
