# Lithoforge — CMYKW Lithophane Generator

## Original Problem Statement
> Build an application that converts a photograph into a 3D-printed lithophane
> using a CMYKW palette. The system should match the colors in the original
> photograph as closely as possible, optimize the print layers to operate within
> the limitations of the printer/slicer, and output a format that transmits the
> color information to the slicer.

## User Choices (captured 2026-02)
- Output: **both** STL + colour swap instructions **and** 3MF bundle
- Geometry: flat rectangle + customizable width/height/thickness/border; curved + cylindrical variants
- Algorithm: **advanced Beer-Lambert + ΔE Lab** optimizer
- User-configurable: **max colour swaps / layers**
- Compute: **hybrid** — preview in browser, final compute on backend

## Architecture
- **Backend**: FastAPI + NumPy + Pillow + scikit-image + trimesh
  - `lithophane.py` — Beer-Lambert stack simulator, LUT, ΔE76 pixel matcher, histogram-based layer allocator
  - `exporters.py` — heightmap mesh builder (flat / curved / cylindrical), binary STL writer, 3MF OPC zip writer, M600 swap instruction text
  - `server.py` — REST endpoints + in-memory job/upload store
- **Frontend**: React + Shadcn UI + Tailwind
  - 3-column "Control Room" layout: Config · Viewport · Palette/Stats/Export
  - Dark high-contrast theme (Chivo display + JetBrains Mono technical)
  - Tabs to toggle colour preview / heightmap / source
  - Layer allocation list + bottom timeline with CMYKW swap bands

## Core Requirements (static)
1. Upload photograph (drag & drop or file-picker)
2. Configure geometry (flat/curved/cylindrical, dimensions, thickness, border)
3. Configure print limits (layer height, max colour swaps → uses N+1 filaments)
4. Edit CMYKW filament palette (hex + Transmission Distance per filament)
5. Run Beer-Lambert optimization in Lab space and report ΔE mean / p95
6. Download STL mesh, swap instructions (.txt with M600 markers), and 3MF bundle

## User Personas
- **3D-printing hobbyist**: wants a quick Hueforge-style workflow for a framed photo.
- **Maker / educator**: tunes filament TDs and geometry for custom signage.
- **Designer**: explores curved and cylindrical lithophane forms.

## Implemented (2026-02-10)
- [x] FastAPI endpoints: `/api/`, `/api/filaments/default`, `/api/upload`,
      `/api/optimize`, `/api/jobs/{id}`, `/api/export/{id}/{stl|swaps|3mf}`
- [x] Beer-Lambert LUT + ΔE76 nearest-neighbour matcher
- [x] Histogram-based layer allocation with min-per-colour floor
- [x] Heightmap → mesh (flat + curved + cylindrical)
- [x] Binary STL writer, swap `.txt`, 3MF OPC bundle
- [x] React UI (Control Room layout) with upload, config, palette editor,
      preview / heightmap tabs, stats, layer timeline, exports
- [x] Backend test suite: **17/17 passing** (health, filaments, upload,
      optimize, jobs, exports, geometry, legacy status)

## Implemented (2026-02-14)
- [x] Painting mode (reflective top-layer nearest-filament mapping)
- [x] Image edit suite: brightness/contrast/saturation + interactive crop overlay (8 handles)
- [x] Real-time histogram (R/G/B/luma) with clipping markers
- [x] A/B compare slider (source vs render)
- [x] Dynamic palette (1–8 filaments) with library picker
- [x] AI palette suggestion with `Accurate / Balanced / Vibrant` modes
- [x] Vibrant mode rewritten to use **hue-wheel angular coverage** (atan2(b*,a*))
      weighted by chroma, replacing prior Lab-spread heuristic
- [x] Cross-origin exports fixed via fetch → blob downloads
- [x] **Max colour swaps slider now caps at 7** (was hard-locked at 5)
- [x] **Crop overlay aspect-ratio lock**: hold `Shift` while dragging a corner
      handle to preserve current rect aspect (in image-pixel space)
- [x] **Preset Manager**: localStorage-backed presets capturing config + palette
      + render mode + vibrancy. Ships with 3 built-ins (Portrait, Landscape,
      Lithophane). Image edits intentionally excluded from presets.
- [x] **Safari iPad hardening**: removed problematic `crossOrigin` on blob URLs,
      Histogram canvas readback wrapped in try/catch, lazy original-image reload
      from sourceUrl, pixel-loop fallback for browsers without `ctx.filter`
      (Safari < 18), `willReadFrequently: true` for repeated readbacks.
- [x] **Touch-friendly filament × delete**: was `opacity-0 group-hover:opacity-100`
      (invisible on iPad → users couldn't remove palette colors). Now
      always-visible at 70% opacity, hover-pops to 100%; 20×20 px target.
- [x] **Remote error reporter** (`/api/client-error`) — captures uncaught JS
      errors + React render errors with UA & URL for debugging without
      requiring screenshots from the user.
- [x] **React ErrorBoundary** — graceful "Try again" fallback so runtime
      errors never blank the screen.
- [x] **Mobile / touch shell** — viewport < 1280 px gets a single-column
      layout: full-bleed viewport on top, fixed 2-tab bottom bar
      (Setup / Palette & stats) opening half-height bottom sheets with the
      respective panels. Desktop ≥ 1280 px keeps the original 3-column
      control-room layout. JS-driven switch via `matchMedia` so panels
      only mount once.
- [x] **Mobile sheet first-touch crash** — Radix Dialog auto-focused the
      first focusable element inside the sheet while the slide-in animation
      was still playing; Safari iPad threw an uncaught error sanitized to
      "Script error." on `window.onerror`. Fixed by `onOpenAutoFocus={e =>
      e.preventDefault()}` + `onCloseAutoFocus={e => e.preventDefault()}`
      on `SheetContent`.
- [x] **Pinch-to-zoom + pan viewport** — `ZoomPanView` wraps the image:
      2-finger pinch (or ctrl/cmd + wheel) zooms 1× – 5×, 1-finger drag
      pans when zoomed, double-tap / double-click resets. Pan bounds keep
      the image at least partially visible. Touch-action: none while
      zoomed prevents iOS Safari native page-zoom from hijacking the
      gesture. Wheel listener attached via native `addEventListener` with
      `passive: false` so `preventDefault` actually works.
- [x] **CropOverlay rewritten with pointer events** — previously used
      mouse events only and silently failed on iPad. Now uses
      `onPointerDown` + document-level `pointermove`/`pointerup`/
      `pointercancel`. Touch-action: none on handles & rect to keep
      iOS from intercepting drags as scrolls. Crop overlay is hidden when
      the viewport is zoomed to avoid gesture conflicts.
- [x] **Disk-cache poisoning fix** — added `setupProxy.js` that sends
      `Cache-Control: no-store, no-cache, must-revalidate` headers so
      popped-out Safari tabs always get the latest bundle.

## Implemented (2026-02-23) — Platform: Emergent-managed Google Auth
- [x] **`/api/auth/session`** — exchanges OAuth session_id for a
      persisted session_token, upserts the user, sets a secure httpOnly
      cookie with SameSite=None.
- [x] **`/api/auth/me`** — returns current user or 401.
- [x] **`/api/auth/logout`** — invalidates the session and clears cookie.
- [x] **MongoDB collections**: `users`, `user_sessions`, `presets`.
- [x] **`/api/presets`** GET/POST/DELETE + `/api/presets/import` — per-user
      cloud preset storage with one-shot localStorage import on first login.
- [x] **Frontend `AuthProvider`** + `useAuth()` hook + `AuthCallbackHandler`
      that strips `#session_id=…` after OAuth return.
- [x] **`UserMenu`** in header — Sign In button when anonymous; avatar +
      name + dropdown (email, sync status, Sign Out) when logged in.
- [x] **`PresetManager` upgraded** — dual-source: localStorage for
      anonymous users, MongoDB-backed cloud presets for logged-in users.
      One-shot migration of local presets to cloud on first login.
      "✓synced" badge next to the Presets label when authenticated.
- [x] App remains **NOT auth-gated** — every feature works anonymously;
      login is opt-in for cross-device preset sync.

## Implemented (2026-02-23) — Platform: Job history + Help system
- [x] **Per-user job persistence** — when a logged-in user runs
      `/api/optimize`, the full result (config, palette, layer map,
      preview, heightmap, timeline, ΔE stats) is saved to MongoDB
      `jobs` collection. Layer maps are stored as base64-encoded NumPy
      arrays so restored jobs can re-generate STL/3MF/swap exports.
- [x] **`GET /api/my-jobs`** — list current user's jobs (latest 60),
      returns small thumbnails (160px) for the history strip.
- [x] **`GET /api/my-jobs/{id}`** — restore: hydrates the stored job back
      into the in-memory JOBS dict so `/api/export` keeps working, and
      returns the full optimize-shaped payload so the frontend can
      rehydrate config + palette + viewport.
- [x] **`DELETE /api/my-jobs/{id}`** — remove from history.
- [x] **`JobHistory` component** in the right sidebar — 3-column
      thumbnail grid with hover-revealed Restore / Delete buttons,
      timestamp, ΔE summary. Auto-refreshes on `lithoforge:job-finished`
      window event after each generate.
- [x] **Viewport restore-aware** — accepts result-without-sourceUrl so
      restored jobs show the rendered preview, ΔE stats, layer
      allocation, and downloads immediately.
- [x] **`HelpHint` component** — tap "?" button → click-outside-dismiss
      popover. Mounted next to: Render Mode, Geometry, Print Limits,
      AI Palette section.

## Implemented (2026-02-23) — Platform: Marketplace Phase A
- [x] **Listings data model** — embedded `listing` field on `jobs`
      docs: `{title, description, price_usd, visibility: "listed",
      listed_at}`. Platform fee constant `PLATFORM_FEE_PCT = 6.0`.
- [x] **Creator endpoints** (auth required):
      `PUT /api/my-jobs/{job_id}/listing` (publish or update),
      `DELETE /api/my-jobs/{job_id}/listing` (unlist),
      `GET /api/my-jobs/{job_id}/listing` (status check).
- [x] **Public marketplace endpoints**:
      `GET /api/marketplace` (browse + pagination),
      `GET /api/marketplace/{job_id}` (full detail incl. preview),
      `GET /api/creators/{user_id}` (creator profile + their listings).
- [x] **`PublishDialog.jsx`** — modal with title / description /
      price inputs + **live payout math** (Buyer pays $X − 6% fee =
      $Y to creator). Supports both publish-new and edit-existing.
      Unlist button when editing.
- [x] **`MarketplacePage.jsx`** at `/marketplace` — public grid of
      every listed work with thumbnail / title / price / creator.
- [x] **`ListingDetailPage.jsx`** at `/marketplace/{job_id}` —
      full preview + creator attribution + disabled "Buy via Creator"
      CTA (Phase B will wire Stripe Checkout here).
- [x] **`CreatorPage.jsx`** at `/creator/{user_id}` — creator avatar +
      name + their listed works.
- [x] **Job tile UI** — green "LISTED" badge when a job is published,
      Store-icon button to open PublishDialog. `my-jobs` summary now
      includes `listed` flag.
- [x] **Header link** — "Marketplace" button in the studio header.
- [x] **React Router** wired at `/`, `/marketplace`, `/marketplace/:id`,
      `/creator/:id`.
- [x] **Tests**: 5 new marketplace tests + 17 existing = 22/22 passing.

## Implemented (2026-02-25) — Sign-in gate + per-user quota + pricing teaser + Usage % + magnifier loupe

- [x] **Sign-in REQUIRED to download**. `/api/export/{id}/{kind}` without
      an auth cookie or buyer token now returns `401 auth_required`.
      Marketplace token-based buyer downloads bypass the gate (they paid).
- [x] **Quota system (`quota.py`)** — per-user, per-tier download caps:
      - `free`: 5 lifetime downloads (hard 402 on the 6th).
      - `hobbyist`: 25 / calendar month (Stripe to be wired later).
      - `pro`: unlimited + publish + payouts.
      - A "use" = first download of a (user, job) pair. STL + 3MF + swap
        text for the same job count as ONE use so creators aren't
        penalized for grabbing all three formats.
      - Re-downloads of already-counted jobs are always permitted even
        when the user is over quota (so an old job stays accessible).
- [x] **`GET /api/me/quota`** returns the signed-in user's tier, limit,
      used, remaining, period_key, and a `blocked` flag. Guests get a
      sentinel `{tier: "guest", blocked: true}` so the UI shows the gate.
- [x] **Frontend `QuotaProvider`** (lib/quota.jsx) — global context
      caching the current quota state, with a `showUpgrade()` helper.
- [x] **`QuotaCounter`** in the studio header — tier badge + downloads
      remaining + Upgrade button. Anonymous = GUEST badge + "0 / 0".
- [x] **`UpgradeModal`** — opens on 401 / 402 / Upgrade-click. Shows
      sign-in CTA for anonymous users + Hobbyist / Pro plan cards
      (currently "Coming soon" pending Stripe).
- [x] **`/pricing` page** with all 3 plans + email-capture for launch alerts.
- [x] **Per-filament Usage %** column in Layer Allocation (StatsPanel)
      — each row shows `pct.toFixed(0)%` plus the existing layer count.
- [x] **Magnifier loupe** (`Loupe.jsx`) — long-press (mobile) or
      shift-click (desktop) on the rendered preview shows a 4× zoom
      circle anchored to the cursor with: source colour swatch, closest
      filament name + swatch, and live ΔE76 between them.
- [x] **Test fixtures consolidated** into `tests/conftest.py` — all 3
      test files now share the `authed_client` (pro-tier) fixture.
- [x] **43/43 backend tests pass**, including 6 new quota tests
      verifying first-5-OK, 6th-blocks, re-download-allowed, guest-401,
      pro-unlimited.

## Implemented (2026-02-25) — Marketplace Phase C: Stripe Connect creator payouts

- [x] **`payouts.py`** — Stripe Connect Express integration via the raw
      `stripe` Python SDK (not the emergentintegrations wrapper, since
      Connect endpoints aren't exposed by it).
      - `create_express_account(email)` — provisions a new connected
        account with `transfers` + `card_payments` capabilities.
      - `create_account_link(account_id, refresh_url, return_url)` —
        builds a one-shot Stripe-hosted onboarding URL.
      - `fetch_account_status(account_id)` — reads
        charges_enabled / payouts_enabled / details_submitted.
      - `transfer_to_creator(amount, destination, transfer_group)` —
        sends the creator's 94% share as a separate `stripe.Transfer`
        after the platform receives the buyer's payment.
- [x] **`settle_creator_payout`** is called from BOTH the polling
      `/marketplace/checkout/status/{id}` and the `/webhook/stripe`
      paths the moment `payment_status == paid`. Three outcomes
      recorded on the transaction:
      - `transferred` — creator got the money instantly.
      - `owed` — creator hasn't completed onboarding yet; we track
        the amount until they finish.
      - `failed` — Stripe returned an error (Connect not enabled, bank
        rejected, etc.); reason stored in `transfer_failed_reason`.
- [x] **Endpoints (auth required):**
      - `POST /api/payouts/onboard {return_url, refresh_url}` — creates
        a Connect account if needed, returns onboarding URL.
      - `GET /api/payouts/status` — pulls live status from Stripe and
        caches `charges_enabled` + `payouts_enabled` on the user doc.
      - `GET /api/payouts/transactions` — ledger of every paid sale
        with payout_status + lifetime totals.
- [x] **Frontend `/payouts` page** — auth-gated creator dashboard:
      Stripe Connect status card, "Set up payouts" / "Resume onboarding"
      / "Manage on Stripe" button, lifetime-paid + owed totals, recent
      sales ledger with per-row payout-status badges.
- [x] **UserMenu** dropdown gets a new "Payouts" link.
- [x] Graceful degradation: when `STRIPE_API_KEY` is the Emergent
      sandbox token (`sk_test_emergent`), the buyer-side checkout still
      works perfectly via emergentintegrations; only the Connect
      endpoints require a real Stripe test key. Sales for un-onboarded
      creators are marked `owed` so the platform can settle manually.

### Setup required for live Connect testing
1. Sign in to Stripe → Developers → API keys → copy the **Secret test key**
   (`sk_test_...`).
2. In Stripe → Settings → Connect → "Get started" — enable Connect for
   test mode if not already on.
3. Swap `STRIPE_API_KEY=sk_test_emergent` in `/app/backend/.env` for the
   real key and restart backend.
4. From the studio, sign in → User menu → Payouts → "Set up payouts".
   Stripe's hosted onboarding accepts test data (SSN 000-00-0000, DOB
   any past date, address any US address).

## Implemented (2026-02-25) — Printer catalog + licensing + buyer override + Resend scaffold + painting smoothing

- [x] **Printer profile catalog (`printers.py`)** — 18 profiles organized
      by SLICER FAMILY (OrcaSlicer / PrusaSlicer / SuperSlicer / Cura /
      Marlin) so any printer that runs Orca shows up under one umbrella.
      Includes Bambu A1 mini / A1 / P1S / X1C, Sovol SV07 / SV08,
      Elegoo Neptune 4 / Centauri Carbon, Anycubic Kobra 2, Creality K1,
      Flashforge Adventurer 5M (3MF-only), Prusa MK4 / MINI+ / XL,
      Voron 2.4, Ultimaker S3, plus two generics.
- [x] Per-printer flags: bed_x_mm/bed_y_mm, default layer height,
      `multi_tool` (drives `T<n>` vs `M600`), `supported_formats`.
- [x] **`GET /api/printers`** returns the catalog;
      **`GET /api/printers/{id}/fit?width_mm=&height_mm=`** reports
      whether a design fits on that printer's bed (5 mm safety margin).
- [x] **Multi-tool / AMS auto-pause flavour** — `build_layer_change_gcode`
      emits `T1 T2 T3` for AMS-style printers and `M600` for
      single-extruder. **AMS-slot overflow safety**: 5th+ swap on a
      4-lane AMS falls back to `M600 ; out of AMS slots` so the printer
      never errors trying to switch to a non-existent tool.
- [x] **Creator picks printer at generate time** — `OptimizeIn.printer_id`;
      ConfigPanel shows a "Target printer" grouped dropdown above Shape.
- [x] **License field on every listing** — `ListingIn.license` with 8
      presets (All Rights Reserved, Personal Use Only, CC0, CC-BY,
      CC-BY-SA, CC-BY-NC, CC-BY-NC-SA, CC-BY-ND). Surfaced on the
      Publish dialog + the listing detail page + embedded in the 3MF
      `cmykw_license` field.
- [x] **Buyer override on purchase-success page** — `PrinterSelect`
      lets the buyer regenerate the STL/3MF/swaps for their own printer
      via `/api/export/{id}/{kind}?printer=…&token=…`. **Bed-fit
      warning** flashes if the design exceeds the buyer's chosen bed.
- [x] **Resend email scaffold (`email_service.py`)** — sends a
      transactional "your lithophane is ready" email with tokenized
      download links the moment payment_status becomes paid (both
      polling + webhook paths). No-ops gracefully when
      `RESEND_API_KEY` is the placeholder so checkout still works.
- [x] **Painting-mode chromatic simplification** — new `smoothing`
      slider (0..1) applies a Lab-space median pre-pass before
      nearest-filament matching, softening the speckled boundaries
      between filament zones on continuous photos.
- [x] **Tests**: +5 printer tests (catalog, fit, creator printer,
      buyer override, AMS overflow). Total **37/37 backend pytest pass**.

## Implemented (2026-02-24) — Auto-pause slicer integration (Option B + C)
- [x] **3MF auto-pause** (Option B): `Metadata/project_settings.config`
      now embeds `before_layer_change_gcode` + `layer_change_gcode`
      with a chain of `{if layer_num == X}M600{endif}` blocks — one per
      colour swap. PrusaSlicer / SuperSlicer / OrcaSlicer / Bambu Studio
      honour this on project import, so the printer pauses + prompts
      for filament at every swap layer **without any manual UI clicks
      in the slicer**.
- [x] **Slicer-paste swap text** (Option C): `exports/swaps.txt` is now
      a paste-ready, multi-slicer document with three labelled sections:
      - OPTION A: Slic3r-family conditional snippet (Prusa/Orca/Bambu)
      - OPTION B: Cura post-processing instructions (per-layer entries)
      - OPTION C: Raw Marlin M600s at known Z heights
      Plus a load-order summary table at the top.
- [x] StatsPanel labels updated so users know the new output is
      slicer-aware ("Paste-ready for Prusa/Orca/Bambu/Cura",
      "Mesh + auto-pause at swap layers").
- [x] Tests upgraded to require OPTION A/B/C markers + the conditional
      snippet inside the 3MF config (29/29 still pass).

## Implemented (2026-02-24) — Circular disc geometry + Marketplace Phase B (guest checkout)
- [x] **New geometry: Circular disc** — round (coaster-shaped) print with
      optional gentle dome curvature on the top face. Backend masks the
      inscribed circle out of the rectangular layer grid, the STL/3MF
      exporter only emits triangles where all 4 cell corners lie inside
      the circle and traces side walls along the masked boundary so the
      mesh stays watertight.
      - `exporters.GeometrySpec.mode` accepts `"disc"`; `dome_mm` adds
        `(1 − r²) · dome_mm` to z_top for a gentle dome bump.
      - `/api/optimize` accepts `geometry: "disc"` + `dome_mm: float`;
        preview PNG is masked to the inscribed circle (black corners)
        so the user sees the actual print shape.
      - ConfigPanel relabels Width → Diameter when disc is selected,
        keeps width/height in sync, hides curve_radius, shows Dome slider.
- [x] **Marketplace Phase B — guest Stripe Checkout** (anonymous buyers).
      - New module `marketplace_checkout.py`:
        - `POST /api/marketplace/{job_id}/checkout` — accepts
          `{job_id, buyer_email, origin_url}`; price/currency derived
          from the listing on the backend (NEVER from the request);
          creates a Stripe checkout session via
          `emergentintegrations.payments.stripe.checkout.StripeCheckout`.
        - `GET /api/marketplace/checkout/status/{session_id}` — polled
          by the success page; mints a one-shot `download_token` once
          payment_status==paid (idempotent).
        - `POST /api/webhook/stripe` — webhook handler (also idempotent).
      - New collection `payment_transactions` records every checkout
        with status, payment_status, amount, fee split, buyer_email,
        download_token, timestamps.
      - `/api/export/{job_id}/{kind}` now accepts an optional `?token=`
        query param that grants buyer access without ownership.
      - `jobs_history.load_job_any_owner()` hydrates any job by id for
        verified paid downloads.
      - Frontend:
        - `PurchaseDialog.jsx` — email input + live 6% fee breakdown,
          redirects to Stripe Checkout.
        - `PurchaseSuccessPage.jsx` at `/marketplace/:jobId/success`
          polls until paid, then renders 3 download buttons (STL / 3MF
          / swap instructions) using the tokenized URL.
        - `ListingDetailPage` Buy button now opens PurchaseDialog
          (was disabled in Phase A).
      - Stricter pydantic `Literal` types for `geometry` and
        `render_mode` in `OptimizeIn` so typos 422 instead of silently
        falling back.
- [x] **AuthCallbackHandler timeout** — 12-second fallback + always-visible
      "Skip" button so stale `#session_id` fragments can never permanently
      mask the upload zone (lib/auth.js).
- [x] **Tests**: +1 disc geometry test, +marketplace_checkout tests
      (404 paths) — **29/29 backend tests pass**.

## Implemented (2026-02-26) — iPad / iOS "Script error." overlay suppression

- [x] **Root cause** — On iOS WebKit (Safari / iPad Firefox), any throw
      inside a cross-origin script (PostHog session-replay, Emergent
      analytics) is sanitized by the browser to a useless
      `message="Script error.", error=null, source="", lineno=0` event.
      CRA's webpack-dev-server client overlay catches `window.onerror`
      and renders a giant red `Uncaught runtime errors: Script error.`
      banner blocking the viewport, which fired every time the user
      touched the brightness / contrast / saturation sliders (the
      cross-origin script was reacting to the pointer events).
- [x] **Fix** (`public/index.html`) — extended the existing inline
      capture-phase error swallow so it also stops propagation for:
        - `message === "Script error."` with no `e.error` object, AND
        - `ResizeObserver loop limit exceeded` benign warnings.
      Both `error` and `unhandledrejection` listeners patched. Genuine
      errors with a stack still reach the overlay. This is the same
      defensive pattern already in place for `PerformanceServerTiming`
      DataCloneErrors.

## Implemented (2026-02-26) — Touch-friendly slider steppers + Max-swaps auto-grow

- [x] **`SteppedSlider` component** (`ImageEditPanel.jsx`) — every
      brightness / contrast / saturation slider is now flanked by `−`
      and `+` buttons (`data-testid={slider}-dec` / `-inc`). Holding
      Shift multiplies the step by 10× for coarse moves. 6×6 px hit
      targets feel comfortable on touch. Fixes "can't control it
      precisely" on iPad where 1-unit drags on a 0..200 continuous
      slider were impossible.
- [x] **Max colour swaps no longer capped by current palette size**
      (`ConfigPanel.jsx`). The slider's hard cap is always 7. When the
      user steps past `paletteLength - 1`, `growPaletteTo()` pulls the
      missing entries from `/api/filaments/default` (skipping any
      colour already present by name) so the palette auto-expands
      from e.g. CMYKW (6) → CMYKW + Blue + Key (8). Same `−` / `+`
      steppers added next to the slider, and the value label now reads
      `5 / 7` instead of just `5` so the available headroom is obvious.

## Implemented (2026-02-26) — Manufacturer filament library + ΔE closest-match + private library

- [x] **Catalog** (`manufacturer_library.py`) — ~120 curated PLA SKUs
      across 9 brands: Bambu Lab, Polymaker, Prusament, eSun, Sunlu,
      Overture, Hatchbox, uJoybio3d, FlashForge. Each entry stores
      `brand · name · hex · td · finish` (gloss / matte / silk /
      transparent). TDs follow Hueforge conventions tuned per colour
      family. Slugs (`bambu-lab-pla-basic-orange`) are stable for
      cross-referencing.
- [x] **Endpoints** (`filament_library_api.py`,
      `/api/filament-library/*`):
        - `GET   /`                      — paged browse + brand/text filter.
        - `GET   /brands`                — distinct brand list (chip filter).
        - `GET   /search?hex&algo`       — closest matches in Lab space
          with **ΔE76** or **ΔE2000** (Sharma 2005). Optional
          `include_private=true` mixes the caller's saved SKUs into the
          ranking.
        - `GET   /mine`                  — list signed-in user's
          private filaments.
        - `POST  /mine`                  — add a private SKU
          (per-user cap of 200).
        - `DELETE /mine/{id}`            — remove a private SKU.
        - `POST  /suggest`               — anonymous-OK brand
          suggestion → `library_suggestions` collection, status
          `pending` for moderation.
- [x] **`FilamentLibraryDialog.jsx`** — three-tab modal opened from
      every palette swatch's edit popover ("Match from manufacturer")
      and from the AddTile menu when there's room in the palette:
        - **Find by colour** — colour-picker + hex input + algorithm
          toggle (ΔE76 / ΔE2000) + brand chip filter. Live debounced
          search. Each result row shows the swatch, brand · name,
          finish badge (when not gloss), hex + TD, and a ΔE figure
          colour-coded green (≤5) / yellow (≤12) / orange (>12).
          Clicking a row drops the SKU into the palette in one go.
        - **My library** (auth required) — add/list/remove personal
          SKUs that automatically mix into the search ranking with a
          `MINE` badge.
        - **Suggest** — submit a missing brand/SKU for review.
- [x] **`PaletteEditor.jsx`** — each swatch's pencil popover and the
      AddTile dropdown now lead with a "Match from manufacturer"
      button next to the existing default-library quick-picker. Clicking
      it opens the new dialog pre-seeded with that swatch's current
      hex (or `#ff7a00` for fresh swatches).
- [x] **Tests** (`test_filament_library.py`) — +9 tests cover catalog
      count, brand filter, hex search ranking & sort order, ΔE2000
      mode, invalid-hex 400, auth required for private endpoints,
      add/list/delete round-trip for private SKUs, private SKUs
      appearing in search when `include_private=true`, suggestion
      submission. **52/52 backend tests passing.**

## Implemented (2026-02-26) — Library compatibility "closest match" warning

- [x] **New endpoint** `POST /api/filament-library/match-palette`
      scores any palette (`[{hex, name?}, ...]`) against three pools:
      `scope="mine"` (user's private library, auth required),
      `scope="manufacturer"` (global catalog) or `scope="both"`.
      Returns one `{best, delta_e, severity}` per filament, with
      severity bucketed as
      **ok** (ΔE ≤ 5) / **close** (ΔE ≤ 12) / **far** (> 12), plus
      the worst ΔE across the palette so callers can render a
      single-line summary.
- [x] **`LibraryMatchPanel.jsx`** — auto-fetches and renders:
        - sign-out prompt for anonymous users
        - empty-library prompt for signed-in users with no private SKUs
        - colour-coded banner: **warn** (any far row), **info**
          (any close row), **good** (all ok), with copy that explains
          the consequences in plain English
        - per-row table: input swatch · name → best swatch · brand ·
          name, ΔE coloured green/yellow/red, badge for MINE vs MFR
        - footnote explaining the ΔE 5/12 thresholds when warnings fire
- [x] **StatsPanel integration** — panel now sits between PaletteEditor
      and the Layer-allocation section, scoring the currently-active
      palette (`filaments.slice(0, maxActive)`) against the creator's
      private library. Fires the moment a swatch changes — no
      Generate needed.
- [x] **Marketplace listing integration** — `ListingDetail`
      response now embeds the creator's `filaments[]`. The buyer-facing
      listing page renders the same panel titled "Can I print this?"
      so signed-in shoppers see a green / yellow / red verdict on
      whether the listing is reproducible *before* they hit Buy.
- [x] **Tests**: +3 backend tests (manufacturer scope ranking & invalid
      hex handling, auth requirement on `scope=mine`, mine scope with
      private SKUs catching near / far matches). **55/55 backend
      pytests green.**

## Implemented (2026-02-26) — Landing copy + ForgeSlicer artwork

- [x] Hero copy correction: "In full colour" → **"In Multi colour"**
      (we're a multi-filament process; nobody has true full-gamut
      colour printing yet, the previous claim was inaccurate).
- [x] **ForgeSlicer logo added** to the sister-tool banner. Artwork
      (`/forgeslicer-logo.webp`, 1024×1024 anvil with hot steel +
      sparks) saved to `frontend/public/` and rendered as a 224 px
      square card on the left of the banner with an amber-accented
      "Sister tool" label, hover-zoom on the image, and an amber
      border-glow on hover that picks up the spark colour from the
      artwork.

## Implemented (2026-02-26) — Landing page + sister-tool link

- [x] **New `/` route** renders `LandingPage.jsx` (was Studio). Studio
      moved to `/studio`. Routes updated in `index.js`; all in-app
      "Back to studio" / pricing free-tier CTA / payouts shortcuts
      now point to `/studio`.
- [x] **Landing sections**:
        - Sticky `LandingHeader` with logo (links to `/`), sister-tool
          chip, Marketplace / Pricing / Sign-in nav, and a primary
          "Open studio" button on the right.
        - Hero with tagline ("Print photographs. In full colour."),
          subhead, primary "Open the studio" CTA + secondary "Browse
          marketplace", "5 free downloads" trust note, and a
          decorative CMYK quad / ΔE keystone visual.
        - **How it works** — three-step walkthrough: Upload → Tune
          palette → Generate & print, each with a lucide icon and a
          plain-English paragraph that mentions Beer-Lambert, the AI
          palette suggester, and the auto-pause 3MF export.
        - **What's inside** — six-card feature grid mentioning the
          Lab ΔE optimizer, the 9-brand manufacturer library, 3MF +
          M600 G-code injection, geometry options (flat / curve /
          cylindrical / disc), the marketplace + Stripe payouts and
          the new library compatibility check.
        - **Sister-tool plug** for **ForgeSlicer.com** — large
          clickable banner that opens in a new tab.
        - Final CTA ("Ready to print a photograph?") and footer with
          App / Adjacent columns including a ForgeSlicer.com link.
- [x] **Studio header** (`Header.jsx`) — logo now links to `/`
      (landing); a "Sister tool: ForgeSlicer.com →" chip sits left of
      Pricing / Marketplace, matching the landing-header version, so
      ForgeSlicer is reachable from every studio session.
- [x] **MarketplaceHeader / PricingPage / PayoutsPage** — every
      "Back to studio" or studio shortcut updated to `/studio` so
      navigation stays consistent now that `/` is the landing.

## Implemented (2026-02-26) — Export download flow hardening

- [x] **Root cause** — Recent `target="_blank"` added to the synthetic
      download anchor as a "belt-and-suspenders" iOS hack ended up
      silently breaking desktop Chrome: when an `<a>` carries both
      `download` AND `target="_blank"` AND is `.click()`'d *after* an
      `await fetch(...)`, Chrome's popup-blocker considers the user-
      gesture chain broken and silently blocks the action. Result on
      the user's laptop: clicking STL / 3MF / Swap Instructions did
      *nothing* — no file, no toast, no modal.
- [x] **Fix** (`StatsPanel.jsx::downloadFile`) — removed
      `link.target = "_blank"` from the desktop branch (it's still
      used in the iOS branch via `window.open(blobUrl, "_blank")`,
      which is the correct iOS-friendly path).
- [x] **Confirmation toast** — every successful download now fires a
      `toast.success("Downloaded {filename}")` so the user gets visible
      confirmation even if Chrome's downloads dock is collapsed or
      they missed the file landing.
- [x] **Verified end-to-end** with a seeded PRO user via Playwright:
      STL (9.6 MB · `model/stl`), Swap Instructions (2.1 KB ·
      `text/plain`) and 3MF (1.4 MB · `model/3mf`) all download
      cleanly, success toast surfaces.

## Implemented (2026-02-26) — Beta: unlimited free downloads (Stripe paused)

- [x] **Why**: launching with a "Coming soon" wall on the 6th download
      was a dead-end UX (no Stripe yet to actually monetize). User is
      busy with another product's beta launch and asked to remove the
      cap until Stripe is wired.
- [x] **Backend** (`quota.py`) — `TIER_LIMITS["free"]` flipped from
      `{"period": "lifetime", "limit": 5}` to `{"period": "lifetime",
      "limit": None}`. `get_quota_state` already returns `limit=None`
      and `blocked=False` when the tier limit is None, so the
      `enforce_quota` early-exit never fires for free users. Per-user
      `downloads_seen` counters still increment — we keep the usage
      analytics for the eventual paywall flip.
- [x] **UpgradeModal** — copy updated:
        * Signed-in modal title: "Subscriptions launch soon" (was
          "You've used all 5 free downloads").
        * Sign-in CTA: "Sign in (free — unlimited downloads during
          beta)" (was "…gives you 5 starter downloads").
        * Body text rewritten to set the beta expectation honestly
          and tease "early-bird discount when paid plans launch".
- [x] **QuotaCounter** — now renders three distinct states:
        * Guest: `[GUEST]   Sign in to download   [SIGN IN]`
          (was a misleading "0 / 0 downloads left").
        * Signed-in free during beta: `[FREE] ∞ Unlimited during beta`.
        * Pro: unchanged.
      The "Upgrade" CTA was only useful when free=5; now it's
      replaced by a "Sign in" CTA visible only to guests.
- [x] **LandingPage hero trust badge** — "5 free downloads" → "Unlimited
      downloads during beta".
- [x] **Tests** (`test_quota.py`) — old free-tier tests (`test_first_5
      _downloads_succeed`, `test_sixth_download_is_blocked`) replaced
      with `test_many_downloads_all_succeed_during_beta` (loops 8
      downloads, all 200 OK) and updated `_for_signed_in_free_user`
      to assert `limit=None, blocked=False`. **54/54 backend pytests
      green.** When Stripe is wired, restore the original tests from
      git history along with the `TIER_LIMITS["free"]` value.

## Implemented (2026-02-26) — "Send to ForgeSlicer" handoff button

- [x] **`lib/forgeslicerHandoff.js`** — production-grade implementation
      of the user's contract:
        * Opens `https://forgeslicer.com/handoff` in a new tab.
        * Fetches the STL via the existing `/api/export/{jobId}/stl`
          endpoint with credentials.
        * Listens for `{ type: "forgeslicer:handoff:ready" }` *only*
          from `https://forgeslicer.com` (strict `e.origin` check).
        * Posts back `{ type: "forgeslicer:handoff:stl", filename, data,
          sourceLabel: "LithoForge", sourceUrl }` with the ArrayBuffer
          *transferred* (zero-copy — important for 10 MB+ STLs).
        * 60 s handshake timeout, listener cleanup on resolve/reject/
          timeout, custom error classes (`PopupBlocked`,
          `AuthRequired`, `HandoffTimeout`) so the caller can decide
          which UX to show.
- [x] **`Header.jsx`** — new "Send to ForgeSlicer" button left of the
      Generate button. Amber outline matching the ForgeSlicer accent.
      Disabled until a generated job exists. Click handler:
        * `AuthRequired` → opens `<UpgradeModal>` (sign-in gate)
        * `PopupBlocked` → toast.error with hint to allow popups
        * `HandoffTimeout` → toast.error
        * success → toast.success("Sent to ForgeSlicer")
      `data-testid="header-send-to-forgeslicer"`.
- [x] **`App.js`** — passes `jobId={result?.job_id}` through to Header
      so the button enables itself the moment a Generate completes.
- [x] **Tests** — `src/lib/__tests__/forgeslicerHandoff.test.js`
      (Jest + jsdom): 3/3 passing for happy path, popup-blocker
      handling, and 401 auth-required path. The strict origin check is
      enforced by structure (early-return on bad `e.origin`) and is
      not separately tested due to jsdom + fake-timer flake; covered
      by code review.

## Implemented (2026-02-26) — Histogram reacts after Generate on iPad

- [x] **Root cause** — `Histogram.jsx` was setting
      `offCtx.filter = editsToCssFilter(edits)` to apply brightness /
      contrast / saturation before binning. iPad WebKit (Safari +
      iOS Firefox) honours `ctx.filter` the first few times the
      canvas is used, then silently no-ops it once the canvas has
      been reused enough — particularly after a Generate run
      invokes `renderEditedImage` which heavily exercises the same
      canvas APIs. So sliders updated the *number* but the histogram
      readback returned the same un-filtered pixels every time.
- [x] **Fix** — compute brightness/contrast/saturation directly on the
      ImageData pixel array (`applyEditsInPlace`) instead of trusting
      `ctx.filter`. ~80 µs at 200×H px, strictly faster than the CSS
      filter round-trip on every platform. `offCtx.filter = "none"` is
      explicit so any leftover state from a previous run is cleared.
      Crop is still applied via `drawImage` source-rect (unchanged).
- [x] **Verified end-to-end** (Playwright) — signature of the entire
      histogram canvas changes on every brightness/contrast/saturation
      adjustment, both before AND after a Generate run.

## Implemented (2026-02-26) — ForgeSlicer handoff race-condition fix

- [x] **Root cause** — ForgeSlicer mounts `/handoff` and fires
      `{type:"forgeslicer:handoff:ready"}` within ~200 ms. The STL
      fetch on LithoForge's side can take several seconds, especially
      on 10 MB+ files. v1 attached the `message` listener AFTER
      awaiting fetch, so the `ready` ping arrived before any listener
      existed and was silently dropped — ForgeSlicer's own 20 s
      timeout then surfaced "Handoff didn't complete".
- [x] **Fix** (`forgeslicerHandoff.js`) — rewrote as a small two-state
      machine. The `message` listener is attached IMMEDIATELY after
      `window.open()`, the fetch runs in parallel, and the
      `postMessage` to ForgeSlicer fires the moment BOTH conditions
      are met (ready buffered + STL fetched). Either ordering ends
      with a single post; listener and timer are cleaned up on
      resolve/reject. Timeout bumped from 60 s → 90 s to handle slow
      4G + large STLs.
- [x] **Jest tests** — 3/3 still passing for happy-path, popup-block
      and 401 paths. The "ready arrives before fetch" race is now
      structurally impossible.

### ⚠️ Receiver-side note for the ForgeSlicer side

While LithoForge is on a preview environment its `e.origin` is the
preview URL (e.g. `https://color-match-slicer.preview.emergentagent.com`),
NOT `https://lithoforge.com`. ForgeSlicer's `/handoff` listener needs
an origin allow-list to accept both during dev:
```js
const ALLOWED = new Set([
  "https://lithoforge.com",
  "https://color-match-slicer.preview.emergentagent.com",  // remove on prod launch
]);
window.addEventListener("message", e => {
  if (!ALLOWED.has(e.origin)) return;
  if (e.data?.type === "forgeslicer:handoff:stl") { /* ... */ }
});
```

## Implemented (2026-02-26) — Colour-aware 3MF export + ForgeSlicer handoff switch

- [x] **New per-filament slab geometry** (`exporters.py`):
        * `_build_slab_mesh(clipped_layers, z_floor_mm, lh, geo)`
          builds a watertight slab between a constant floor and a
          per-pixel top. Includes external perimeter walls AND step
          walls between adjacent valid pixels whose tops differ
          (necessary for the topmost filament whose slab reproduces
          the lithophane silhouette).
        * `build_per_filament_slabs(layer_map, swap_layer_indices,
          n_filaments, lh, geo)` returns
          `[(filament_idx, vertices, faces), ...]`. Filament k's slab
          covers Z ∈ [bottoms[k]·lh, min(layer_map, tops[k])·lh].
          Skips filaments whose entire band sits above the print's
          column heights (so a 3-filament palette where only 2
          actually print produces 2 objects, not 3 ghost ones).
- [x] **Colour-aware 3MF writer** (`exporters.py`):
        * `_color_3mf_model(slabs, filaments)` emits one `<object>`
          per filament that contributes geometry. Each carries a
          `<metadatagroup>` with:
            - `lithoforge:filament_slot` — 0-indexed swap order
            - `lithoforge:filament_name` — human-readable
            - `lithoforge:filament_hex`  — `#RRGGBB` upper-case
        * Uses only the 2015/02 3MF Core schema (no vendor extensions
          required to read the metadata back).
        * `_model_settings_config_color(slabs)` emits the
          Bambu/Orca-convention `Metadata/model_settings.config` with
          per-object `extruder` keys (1-indexed) so Bambu Studio /
          OrcaSlicer / PrusaSlicer auto-assign the correct filament.
        * `write_3mf(...)` gained an optional `per_filament_slabs=`
          argument. When supplied it emits the multi-object output;
          when omitted callers get the legacy single-mesh 3MF.
        * `build_export(...)` now always computes the slabs and
          passes them — every `/api/export/{id}/3mf` download is
          per-colour from this point on.
- [x] **Handoff switched to 3MF** (`forgeslicerHandoff.js` +
      `Header.jsx`):
        * Old `stlUrl: exportUrl(jobId, "stl")` → new `modelUrl:
          exportUrl(jobId, "3mf")` so ForgeSlicer receives the full
          per-colour palette instead of a flat colourless mesh.
        * New postMessage type `forgeslicer:handoff:model` (the old
          `forgeslicer:handoff:stl` is still emitted when a legacy
          caller passes `stlUrl=` — keeps any deployed ForgeSlicer
          build that pre-dates this change running).
        * Payload gained a `format: "3mf" | "stl"` discriminator so
          the receiver can branch cleanly.
        * The Bambu-style `<item extruder="N"/>` per-object info is
          on the ForgeSlicer side reachable via either the metadata
          group or the model_settings.config file inside the 3MF zip.
- [x] **Tests**: 4 new pytests in `test_color_3mf.py` (slab Z-bands,
      empty-band skip, full e2e through `build_export` asserting
      3 objects + correct metadata + correct extruder mapping,
      legacy single-mesh fallback). 3 Jest tests updated to
      `modelUrl` + `forgeslicer:handoff:model`. **58/58 backend +
      3/3 Jest** all green.
- [x] **Verified live** via `/api/export/{id}/3mf` curl: produced
      3-object 3MF tagged `White / Orange / Red`, each with 193 596
      triangles, model_settings.config with extruder 1/3/4 mapping.

### ForgeSlicer receiver-side spec

```js
window.addEventListener("message", (e) => {
  if (e.origin !== "https://lithoforge.com") return;
  if (e.data?.type !== "forgeslicer:handoff:model") return;
  // e.data.data        — ArrayBuffer of the 3MF zip
  // e.data.format      — "3mf"
  // e.data.filename    — e.g. "lithoforge-abc12345.3mf"
  // e.data.sourceLabel — "LithoForge"
  // e.data.sourceUrl   — deep-link back to the source job
});
// Tell LithoForge we're ready:
window.opener?.postMessage(
  {type: "forgeslicer:handoff:ready"},
  "https://lithoforge.com",
);
```

To parse the 3MF inside ForgeSlicer: unzip, read `3D/3dmodel.model`
XML, iterate `<object>` elements — each has a `<metadatagroup>` with
`lithoforge:filament_slot/name/hex`. Pair that with the optional
`Metadata/model_settings.config` for the Bambu-style extruder
indexing if your slicer pipeline needs it.

## Implemented (2026-02-27) — ForgeSlicer handoff diagnostics + env-configurable origin
- [x] **Root cause of "Handoff didn't complete" (revised)**: ForgeSlicer's deployed
      bundle (`https://forgeslicer.com/static/js/main.0f301007.js`) only listens
      for `forgeslicer:handoff:stl` and silently drops any other message type.
      When LithoForge introduced 3MF support it began posting
      `forgeslicer:handoff:model`, which ForgeSlicer's listener short-circuited
      at `if (t.type !== "forgeslicer:handoff:stl") return;`. ForgeSlicer's
      allowlist already includes the preview origin, so that part was a red
      herring. ForgeSlicer's STL handler's filename validator
      (`/\.(stl|obj|3mf|glb)$/i`) already accepts `.3mf` extensions, so the
      fix is simply to keep posting under the legacy `:stl` message type with
      the `.3mf` filename + bytes.
- [x] **Fix applied to `src/lib/forgeslicerHandoff.js`**: `messageType` is now
      hard-coded to `"forgeslicer:handoff:stl"` regardless of format. The
      payload still carries `format: "3mf"` metadata for forward-compat once
      ForgeSlicer ships an explicit `:model` handler. Comment in the file
      points to the exact ForgeSlicer build hash that was reverse-engineered.
- [x] **LithoForge-side diagnostics added**:
      - `console.info` on handoff start, logging our `window.location.origin`
        and the target ForgeSlicer origin (the exact string to paste into
        ForgeSlicer's allowlist if it ever changes).
      - `console.info` logging every inbound `message` event during the
        handshake window so we can spot ForgeSlicer changing its `ready`
        payload shape without us noticing.
      - `console.warn` when we receive a message from the right ForgeSlicer
        origin but with an unexpected `type` (contract mismatch).
      - `console.warn` when the 90 s timer expires, reporting
        `readyReceived` / `modelBuffered` state and a tailored hint.
- [x] **Env-configurable target**: `REACT_APP_FORGESLICER_ORIGIN` +
      `REACT_APP_FORGESLICER_HANDOFF_URL` override the hard-coded
      `https://forgeslicer.com` / `/handoff` for staging/dev pointing.
- [x] **Updated Jest test** asserts the outbound message type stays
      `forgeslicer:handoff:stl` (the contract ForgeSlicer's current build
      understands). 4/4 Jest tests passing.

## Implemented (2026-02-27) — Auth: rollback aggressive cookie-clear + fix sign-in loop
- [x] **Root cause of sign-in loop**: the earlier "auto-clear stale cookie on
      /auth/me 401" hardening raced with React.StrictMode's double-effect-invoke
      during sign-in. Sequence that caused the loop:
      1. POST /auth/session → 200, fresh cookie set.
      2. AuthCallback's refresh() → /auth/me → 200 ✓ (user resolved).
      3. StrictMode (dev) or any concurrent re-render fires a second /auth/me
         while the browser/server are mid-flight — token-doesn't-resolve path
         hit → 401 + `delete_cookie` zapped the freshly-set valid cookie.
      4. UI flips to signed-out → user clicks Sign in → cookie clean again →
         loop repeats indefinitely.
- [x] **Fix 1 (`backend/auth.py`)**: `/auth/me` no longer calls
      `delete_cookie` on 401. It just returns a plain HTTPException(401). Stale
      cookies are overwritten atomically on the next successful /auth/session
      (same name, host, path → browser replaces the value). Comment in the
      file explains why we deliberately do NOT clear cookies here.
- [x] **Fix 2 (`frontend/src/lib/auth.js`)**: `AuthCallbackHandler` now strips
      the `#session_id=…` hash BEFORE awaiting `refresh()`, not in the
      `finally`. This eliminates one race-amplification window where a
      Strict-Mode re-invocation could observe the hash again and re-fire the
      session exchange with a now-spent session_id.
- [x] **Tests rewritten** (`tests/test_auth.py`, 5 tests): valid 200, no-token
      401, stale Bearer 401, stale Cookie 401, plus an explicit **regression
      test** that asserts a 401 response does NOT carry a `Set-Cookie:
      session_token=…` header. Full backend suite: **63/63 passing**.
- [x] **Live-verified** via curl that 401 responses only carry Cloudflare's
      own `__cf_bm` cookie — never a `session_token` clear directive.

## Implemented (2026-02-27) — Base-fill option eliminates 3MF voids
- [x] **Bug**: 3MF exports had zero-thickness pixels where the input photo's
      heightmap resolved to layer 0 — slicers treat those as printable voids,
      breaking the print. STL already had a hard-coded 1-layer floor; the
      per-filament 3MF slabs did not, so the base slab simply skipped void
      pixels and ForgeSlicer / Orca / Bambu would slice them as holes.
- [x] **Fix (`backend/exporters.py`)**:
      - `_build_vertices` / `_build_mesh` take a `base_min_layers` (1..5,
        default 2) that drives `np.maximum(layer_map, base_min_layers)` —
        replaces the old hard-coded floor of 1.
      - `build_per_filament_slabs` takes the same arg; for the BASE slab
        (slot 0) the working layer map is bumped to the floor before
        clipping, so voids fill with base filament. Non-void pixels are
        untouched (they keep their original allocation).
      - `build_export` clamps to [1, 5] and propagates everywhere.
- [x] **API (`backend/server.py`)**: every export endpoint
      (`/api/export/{id}/stl|swaps|3mf`) accepts a `?base_layers=N` query
      param (1..5, default 2). Bad values are rejected with 422 (FastAPI
      auto-validates int).
- [x] **Frontend**:
      - `App.js`: added `base_min_layers: 2` to DEFAULT_CONFIG.
      - `ConfigPanel.jsx`: new "Base fill" slider 1..5 step 1, sits right
        below "Border" in Geometry (it's a print-physics value, not a
        download-time tweak).
      - `lib/api.js`: `exportUrl(jobId, kind, { baseMinLayers })` appends
        the query param when supplied.
      - `StatsPanel.jsx`: passes config value through to all three download
        buttons; 3MF subtitle now reads e.g. "Mesh + auto-pause · 2-layer
        base fill" so users see what they're exporting.
      - `Header.jsx`: "Send to ForgeSlicer" handoff URL also carries the
        param so the 3MF that lands in ForgeSlicer matches what the
        download button would produce.
- [x] **Tests**: 3 new pytests in `tests/test_color_3mf.py` covering:
      void-pixel filled to ≥1 layer of base, non-void pixels NOT inflated,
      out-of-range clamp to [1, 5]. Full backend suite: **66/66 passing**
      (was 63). Live curl confirms 422 on bad input, 404 on valid input
      with no job.

## Implemented (2026-02-27) — P2 batch: Replace photo · Histogram toggles · Matboard frame · Voids badge

### (c) Replace photo
- New ⇄ REPLACE button in the Viewport top bar (next to "← NEW IMAGE").
- `handleReplaceFile` in `App.js` swaps `sourceUrl` + `imageId` without
  touching `edits`, `filaments`, `config` (geometry, dimensions, base-fill,
  etc). Clears `result` since it's no longer in sync with the new source.
- Toast: "Replaced with WxH image · edits preserved".

### (d) Histogram channel toggles
- 4 toggle buttons (L / R / G / B) above the histogram canvas
  (`Histogram.jsx`). Each independently shows/hides its channel via
  `aria-pressed`. Luma drawn last so its grey overlay sits on top of the
  colour channels (Photoshop convention).

### (e) Auto-frame matboard
- Backend (`lithophane.py`): `_optimize_painting` takes `frame_px`; the
  outer N-pixel ring is painted with the brightest filament at full
  stack height. Translated from `frame_mm` using the print's shorter
  usable side (passed from `server.py`).
- OptimizeIn now has `frame_mm` (default 0). Painting-mode only.
- New "Frame" slider in ConfigPanel — 0..15 mm step 0.5, hidden when
  not in Painting mode.

### (f) Voids badge
- `OptimizeOut` returns `void_pixels` (zero-layer pixels) and
  `in_domain_pixels` (mask-aware: full rect for rect/flat/curved,
  inscribed circle for disc).
- StatsPanel renders an amber badge "Voids · N px → ML base" ONLY when
  `void_pixels > 0`. Updates live as the Base-fill slider changes.
  Hover tooltip explains what voids are.

### Tests
- 4 new pytests in `tests/test_painting_frame.py`: void count returned,
  disc in-domain mask excludes outside circle, frame paints outer ring
  monochrome, `frame_mm=0` is a no-op vs no-arg. **Full backend suite:
  70/70 passing** (was 66).
- E2E verified by testing agent across all four flows.

## Implemented (2026-02-27) — Greedy mesh decimation: 300×+ triangle reduction
- **Problem**: A 120×120mm lithophane like the ForgeSlicer anvil logo produced
  ~4M triangles in the 3MF (5 filament slabs × ~1M each). 99% of those
  triangles tessellated coplanar regions where adjacent pixels had identical
  z values — pure waste. 3MF file sizes hit ~9 MB and slicer 3D previews
  became sluggish. Slicing G-code was unaffected (slicers do 2D plane
  intersections), so this was purely a transport/UX issue, not a print
  quality issue.
- **Fix #1 — Greedy quad merging** (`exporters.py::_greedy_top_rects`,
  `_bottom_rects`): for flat geometry, decompose the cell grid into
  maximal rectangles of constant top-z (lossless). Each rectangle emits
  ONE quad (2 triangles) instead of N. Applied to `_build_mesh` and
  `_build_slab_mesh`. Curved/cylindrical/disc keep their per-cell
  tessellation because curved surfaces don't share equal-z neighbours.
- **Fix #2 — Flat-bottom 4-corner emission**: single-mesh exports for
  flat geometry use 2 triangles (4 corners) for the bottom face instead
  of the per-pixel grid. Slab exports use `_bottom_rects` for the same
  win on slabs whose footprint is non-trivial.
- **Fix #3 — Vertex compaction** (`_compact_mesh`): the per-pixel vertex
  grid (512×512×2 = 524k verts) was being shipped wholesale in the 3MF
  XML even though only a few hundred were referenced. `_compact_mesh`
  drops unreferenced vertices and re-indexes faces before serialisation.
  Applied to both `_mesh_to_3mf_object` (per-slab) and `_mesh_to_3mf_model`
  (single-mesh fallback).
- **Note on T-junctions**: greedy meshing can leave a vertex on the
  interior of an adjacent rectangle's edge. Slicers (Bambu / Orca /
  Prusa / Cura) slice via 2D plane intersections so T-junctions don't
  affect the printed contours. We accept this tradeoff because the
  target audience is 3D printing, not real-time rendering.
- **Benchmark** on a synthetic ForgeSlicer-anvil 120×120×3mm @ 5 filaments:
  | Metric | Before | After | Ratio |
  | --- | --- | --- | --- |
  | STL triangles | ~4M | 11,676 | **~340× fewer** |
  | STL size | ~200 MB | 570 KB | **~360× smaller** |
  | 3MF size | ~9 MB | 141 KB | **~64× smaller** |
- **Tests**: 11 new pytests in `tests/test_greedy_mesh.py` covering
  decomposition correctness (constant z → 1 rect, varying z → singletons,
  mixed case), bounding-box preservation, slab triangle reduction,
  export triangle count, disc mode unaffected, and vertex compaction.
  **Full backend suite: 81/81 passing** (was 70).

## Implemented (2026-02-27) — In-browser 3D preview on Marketplace listings
- **Backend (`marketplace.py`)**: new public endpoint
  `GET /api/marketplace/{job_id}/preview-mesh` returns a binary STL
  generated from a heavily downsampled (96px max-dim, box-averaged + integer-
  re-quantised) copy of the job's layer_map. The downsample is the IP-
  protection mechanism — the preview is recognisable enough to spin around
  but its dimensions / resolution make it useless as a print substitute. The
  endpoint sets `Cache-Control: public, max-age=86400, immutable` so a single
  visit caches the file across sessions (the Cloudflare edge currently
  overrides this in the preview env, but the directive is correct).
  Returns 404 for both nonexistent and unlisted jobs — same response so
  unlisted jobs don't leak their existence.
- **Frontend (`Lithophane3DPreview.jsx`)**: lean three.js component (no
  R3F / drei) that fetches the preview STL, parses it with a manual ~30-line
  binary-STL reader, centres + auto-fits the camera, and renders with a
  custom spherical-orbit controller (pointer-drag to rotate, wheel to zoom,
  auto-rotate until user grabs). Cleans up the WebGL context on unmount.
- **Frontend (`ListingDetailPage.jsx`)**: preview area now has two tabs —
  **Render** (existing colour PNG, default) and **3D** (the new three.js
  view). A "LOW-RES · IP-SAFE" / "Slicer colour render" caption shows the
  current mode. Defaults to Render because the colour preview is what
  buyers come to see; 3D is the relief inspector.
- **Dep added**: `three@0.184.0` (~250 KB gzipped). Did NOT add R3F or
  drei — overkill for one component.
- **Tests**: 3 new pytests in `tests/test_preview_mesh.py` — 404 on
  unknown listing, 404 on unlisted job (no leak), correct binary-STL
  format + downsampled triangle count. **Full backend suite: 84/84
  passing** (was 81). Frontend smoke test confirmed via Playwright:
  preview tab toggles, 3D component mounts, mesh loads, no error state.

## Backlog
### P1
- True 3D WebGL preview (three.js) instead of 2D rendered PNG
- Vectorised mesh / STL writer for large images (currently Python loop — slow for 512px meshes)
- Bambu/Prusa-specific 3MF project metadata (real project_settings.config key names so slicers auto-set filaments)
- Per-filament tune — optimise layer allocation via simulated annealing, not just histogram
- Soften step boundaries in Painting mode via median-filter pre-pass

### P2
- Persist jobs to Mongo with TTL
- Shareable link for a job (read-only preview + downloads)
- Per-filament "Usage %" column in Layer Allocation
- Histogram channel toggles (R / G / B / Luma)
- Auto-frame for Painting mode (bevelled matboard)
- "Replace photo" button that preserves edits/palette/geometry
- Refactor heavy `App.js` state into context/reducer
- Multi-object build-plate composer
- Printer profile presets (Bambu A1 / X1C, Prusa MK4, Voron)

### P3
- Stripe paywall for high-resolution exports (>512px)
- Community gallery of generated lithophanes
