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
