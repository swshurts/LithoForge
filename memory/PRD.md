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
