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

## Backlog
### P1
- True 3D WebGL preview (three.js) instead of 2D rendered PNG
- Vectorised mesh / STL writer for large images (currently Python loop — slow for 512px meshes)
- Bambu/Prusa-specific 3MF project metadata (real project_settings.config key names so slicers auto-set filaments)
- Per-filament tune — optimise layer allocation via simulated annealing, not just histogram
- Image pre-processing controls (brightness, contrast, levels, crop)

### P2
- Persist jobs to Mongo with TTL
- Shareable link for a job (read-only preview + downloads)
- Upload from URL / webcam
- Multi-object build-plate composer
- Printer profile presets (Bambu A1 / X1C, Prusa MK4, Voron)

### P3
- Stripe paywall for high-resolution exports (>512px)
- Community gallery of generated lithophanes
