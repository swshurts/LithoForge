# Lithoforge — MANUAL UAT Checklist (12 tests)

**Last updated:** 2026-02-25
**Estimated time:** 30–45 min for a full sweep (10 min on a phone/iPad too)

These tests need a real human because they involve:
- Real Google OAuth (`A-01`)
- A real Stripe Checkout payment flow with the test card (`G-05`, `C-03`)
- An email inbox check (`B-04`)
- Tactile mobile gestures that headless browsers don't reproduce reliably (`G-08`, `M-01`, `M-02`, `M-03`)
- Visual quality assessment of generated prints (`S-02`, `S-05`)
- File inspection in a slicer / mongosh (`R-04`)

> **TIP:** Run the automated suite first via `bash /app/run_uat.sh` — if anything in there fails, the manual sweep can probably wait. If automated is green, this list is your release gate.

---

## ✅ Test execution log

Print this section or copy it into a spreadsheet. Mark **PASS / FAIL / SKIP** for each row.

| Test | Status | Tester | Date | Notes |
|---|---|---|---|---|
| A-01 Google sign-in |  |  |  |  |
| G-05 Stripe Checkout purchase |  |  |  |  |
| G-08 iPad layout |  |  |  |  |
| S-02 Smoothing visual |  |  |  |  |
| S-05 Relief visual |  |  |  |  |
| C-03 Payouts onboarding |  |  |  |  |
| B-04 Buyer email delivery |  |  |  |  |
| R-04 Mongo collections |  |  |  |  |
| M-01 Pinch-zoom |  |  |  |  |
| M-02 Bottom-sheet tabs |  |  |  |  |
| M-03 Filament × touch |  |  |  |  |
| (also re-confirm) S-01 lithophane visual |  |  |  |  |

---

## A-01 — Google sign-in works  [P0]

**Steps:**
1. Open the preview URL in a fresh window
2. Click **SIGN IN** in the header
3. Complete Google's hosted sign-in (real account)

**Expected:**
- Redirect back to `/` succeeds within ~2 seconds
- User menu shows your name + avatar
- **GUEST** badge changes to **FREE 5 / 5 downloads left**

**Why manual:** Google OAuth refuses scripted automation.

---

## G-05 — Guest completes Stripe Checkout purchase  [P0]

**Pre:** at least one paid listing exists (run `C-01` first via Playwright)

**Steps:**
1. From `/marketplace/:jobId`, click **Buy · $X.XX**
2. Enter your real email
3. Click **Pay $X.XX** → redirected to Stripe Checkout
4. Use Stripe's test card:
   - Number: `4242 4242 4242 4242`
   - Expiry: any future date · CVC: any 3 digits · ZIP: any
5. Submit
6. Wait to be redirected back to `/marketplace/:jobId/success`

**Expected:**
- Stripe page loads cleanly in the same tab
- After payment, redirected back to success page
- Success page polls and shows **Payment received**
- 3 download buttons appear (STL / 3MF / Swap instructions)
- **Buyer-printer-override** dropdown is visible
- Clicking STL triggers a real file download

**Why manual:** Stripe's hosted page can't be filled by scripts.

---

## G-08 — Studio on iPad / phone  [P1]

**Pre:** Real iPad or iPhone (preferred) or Chrome DevTools device emulation

**Steps:**
1. Open the preview URL on the device
2. Look at the bottom tab bar
3. Tap between Edit / Render / Stats sheets
4. Drag a finger to pan across the studio area

**Expected:**
- Layout fits without horizontal scroll
- Bottom sheets slide up smoothly
- No phantom delete buttons or invisible controls
- Status bar / safe-area padding is respected on iPhone

**Why manual:** Real touch + real Safari rendering can't be perfectly emulated.

---

## S-02 — Smoothing slider reduces speckled boundaries  [P2]

**Pre:** Painting mode + photo with continuous tones (a face / skin works best)

**Steps:**
1. Generate at smoothing = 0%
2. Zoom in on a soft gradient (cheek, sky)
3. Note the speckled noise along filament zone boundaries
4. Move smoothing to ~60% → click GENERATE again
5. Compare same region

**Expected:** Boundaries look noticeably smoother in the second render.

**Why manual:** "Looks smoother" is a perceptual judgment.

---

## S-05 — Painting mode Relief slider  [P1]

**Pre:** Painting mode

**Steps:**
1. Generate with Relief = 0% — note flat color plateaus
2. Move to 100% → generate again
3. Switch to **Heightmap** view (icon below preview)

**Expected:** Heightmap shows clear bas-relief variation within each color band at 100%.

**Why manual:** Visual judgment about texture depth.

---

## C-03 — Stripe Connect Payouts page  [P1]

**Pre:** Signed in. *Status: will fail until you provide a real Stripe test key.*

**Steps:**
1. User menu → **Payouts**
2. Click **Set up payouts**

**Expected (current state, sandbox key):**
- Toast shows "Invalid API Key" error
- This is **expected** until you swap `sk_test_emergent` in `/app/backend/.env` for a real `sk_test_...` key.

**Expected (after real key):**
- Redirect to Stripe-hosted onboarding
- Enter test SSN `000-00-0000`, DOB any past, US address
- Return to `/payouts?payouts=ok` and badge shows **Payouts active**

**Why manual:** Stripe Connect onboarding can't be scripted; requires user interaction.

---

## B-04 — Buyer email delivery  [P1]

**Pre:** Completed G-05 with `steve.shurts@gmail.com` (Resend dev-mode account email)

**Steps:**
1. Check Gmail inbox (and Promotions tab)
2. Open the message from `onboarding@resend.dev`

**Expected:**
- Subject: "Your lithophane is ready — *title*"
- Three dark buttons: STL · 3MF · Swap Instructions
- Footer link points to `/marketplace/:jobId/success`
- Clicking any button starts the download in a new tab

**Note:** In dev mode, Resend only delivers to YOUR account email. Production keys + a verified sender domain are needed to email arbitrary buyer addresses.

---

## R-04 — MongoDB collections inventory  [P2]

**Steps:**
```bash
mongosh test_database --quiet --eval "db.getCollectionNames()"
```

**Expected list (at minimum):**
- `users`
- `user_sessions`
- `jobs`
- `presets`
- `payment_transactions`

**Why manual:** Database access happens from a privileged shell.

---

## M-01 — Pinch-zoom + pan in preview  [P1]

**Pre:** Real iPad / iPhone, image generated

**Steps:**
1. Two-finger pinch on the preview image
2. One-finger drag to pan

**Expected:** Smooth zoom + pan; double-tap resets.

**Why manual:** Multi-touch gestures need a real touchscreen.

---

## M-02 — Bottom-sheet config tabs  [P1]

**Pre:** Real iPad / iPhone

**Steps:** Tap Edit / Render / Stats tabs at the bottom of the screen.

**Expected:** Each opens a half-height sheet; swiping down dismisses.

**Why manual:** Touch-pull gesture.

---

## M-03 — Touch on filament × works  [P2]

**Pre:** Real iPad / iPhone

**Steps:** Tap the × on a filament chip.

**Expected:** Filament removed cleanly (no phantom click, no double-tap zoom).

**Why manual:** Touch precision.

---

## (Bonus) S-01 — Lithophane visual sanity  [P1]

After a generation, look at the **Lithophane** preview mode:
- Dark areas should glow softly when "backlit"
- Light areas should appear opaque
- The image should be readable from far away

**Why manual:** Aesthetic check. The preview is a 2D approximation; the real test is printing it.

---

## Recording results

Use one of:
1. Print this page and tick boxes by hand
2. Copy the test execution log table into Notion / Google Sheets
3. Run `bash /app/run_uat.sh --manual-template > my_run.md` for a per-run template

When all P0 manual + automated tests pass: **closed-beta ready**.
When all P0 + P1 pass: **public-launch ready**.
