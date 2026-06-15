"""FastAPI server for the CMYKW Lithophane generator."""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from exporters import GeometrySpec, build_export
from lithophane import (
    DEFAULT_FILAMENTS,
    Filament,
    layer_map_to_png_bytes,
    optimize,
    rendered_to_png_bytes,
)
from palette_suggest import FILAMENT_LIBRARY, suggest_palette
from printers import fits_on_bed, get_profile, list_profiles
from auth import build_auth
from presets import build_presets_router
from jobs_history import (
    JobPersistData,
    build_jobs_router,
    hydrate_in_memory_job,
    load_job,
    load_job_any_owner,
    persist_job,
)
from marketplace import build_marketplace_router
from marketplace_checkout import build_checkout_router, resolve_download_token
from marketplace_braintree import build_braintree_router
from admin import build_admin_router, build_require_admin
from sso_bridge import build_sso_bridge_router
from meshy import build_meshy_router
from paypal_payouts import (
    build_admin_payouts_router,
    build_paypal_webhook_router,
    build_payouts_router,
    run_payout_batch,
)
from filament_library_api import build_filament_library_router
from quota import enforce_quota, get_quota_state, record_download


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="CMYKW Lithophane API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lithophane")

# In-memory job store. Lithophane jobs are transient — we keep the
# heightmap + metadata so the user can request STL / 3MF exports on demand.
JOBS: Dict[str, Dict[str, Any]] = {}
UPLOADS: Dict[str, Image.Image] = {}

# Build auth EARLY so route handlers below can use the optional / required
# user dependencies. The actual routers are mounted at the bottom of this
# file alongside the main api_router.
auth_router, get_current_user_dep, require_user_dep = build_auth(db)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FilamentIn(BaseModel):
    name: str
    hex: str
    td: float = 3.0


class UploadIn(BaseModel):
    image_base64: str  # data URL or raw base64
    filename: Optional[str] = None


class UploadOut(BaseModel):
    image_id: str
    width: int
    height: int


class OptimizeIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image_id: str
    width_mm: float = 100.0
    height_mm: float = 100.0
    thickness_mm: float = 2.2
    border_mm: float = 2.0
    layer_height_mm: float = 0.12
    max_swaps: int = 5
    geometry: Literal["flat", "curved", "cylindrical", "disc", "box"] = "flat"
    curve_radius_mm: float = 80.0
    dome_mm: float = 0.0       # disc: gentle dome bump (mm) atop the disc
    filaments: Optional[List[FilamentIn]] = None
    auto_order: bool = True
    render_mode: Literal["lithophane", "painting"] = "lithophane"
    relief: float = 0.5              # painting mode only, 0..1
    smoothing: float = 0.0           # painting mode only — 0..1, softens speckle
    frame_mm: float = 0.0            # painting mode only — matboard border width (mm)
    printer_id: str = "generic_orca"  # printer profile id from /api/printers
    nozzle_mm: float = 0.4            # nozzle diameter (drives layer bounds + 3MF metadata)
    license: str = ""                 # creator-declared license (free text or preset)
    # Lightbox (box mode) parameters — ignored when geometry != "box".
    box_shape: Literal["rect", "round"] = "rect"
    box_outer_w_mm: float = 110.0
    box_outer_h_mm: float = 110.0
    box_depth_mm: float = 35.0
    box_wall_mm: float = 3.0
    box_led_mount: Literal["none", "puck", "strip", "both"] = "both"
    box_puck_diameter_mm: float = 65.0
    box_diffuser: bool = True
    box_cable_notch: bool = True


class OptimizeOut(BaseModel):
    job_id: str
    preview_png_base64: str
    heightmap_png_base64: str
    delta_e_mean: float
    delta_e_p95: float
    light_throughput_pct: float = 0.0  # Predicted back-light brightness 0..100
    total_layers: int
    layer_allocation: List[int]
    filaments: List[Dict[str, Any]]
    swap_heights_mm: List[float]
    timeline: List[Dict[str, Any]]  # [{color, name, layers, height_mm}]
    # Count of in-domain pixels whose heightmap resolved to zero layers.
    # The Base-fill slider in the UI fills these with N base-filament
    # layers on export so the print stays continuous — the count here
    # lets the UI surface a "Voids: N pixels · filled by base" badge.
    void_pixels: int = 0
    in_domain_pixels: int = 0


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _decode_image(data: str) -> Image.Image:
    if "," in data and data.strip().startswith("data:"):
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid base64 image") from exc
    try:
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Could not decode image") from exc


def _filaments_from_input(fils: Optional[List[FilamentIn]]) -> List[Filament]:
    if not fils:
        return list(DEFAULT_FILAMENTS)
    return [Filament(name=f.name, hex=f.hex, td=float(f.td)) for f in fils]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "CMYKW Lithophane API"}


class ClientErrorReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    message: str = ""
    stack: str = ""
    source: str = ""
    line: int = 0
    column: int = 0
    user_agent: str = ""
    url: str = ""
    reporter_version: str = "unknown"
    extra: Dict[str, Any] = {}


@api_router.post("/client-error")
async def client_error(body: ClientErrorReport) -> Dict[str, bool]:
    """Capture uncaught client-side errors so we can debug iPad/Safari
    failures without requiring screenshots from the user."""
    logger.error(
        "CLIENT_ERROR | rv=%s | ua=%s | url=%s | msg=%s | stack=%s",
        body.reporter_version,
        body.user_agent[:120],
        body.url[:160],
        body.message[:400],
        body.stack[:1500],
    )
    return {"ok": True}


@api_router.get("/filaments/default")
async def default_filaments() -> Dict[str, List[Dict[str, Any]]]:
    return {"filaments": [{"name": f.name, "hex": f.hex, "td": f.td}
                          for f in DEFAULT_FILAMENTS]}


@api_router.get("/filaments/library")
async def filament_library() -> Dict[str, List[Dict[str, Any]]]:
    """The full curated filament library used by the palette suggester."""
    return {"filaments": [{"name": f.name, "hex": f.hex, "td": f.td}
                          for f in FILAMENT_LIBRARY]}


@api_router.get("/printers")
async def printers_catalog() -> Dict[str, List[Dict[str, Any]]]:
    """Catalog of supported printers (grouped client-side by slicer family)."""
    return {"printers": [dict(p) for p in list_profiles()]}


@api_router.get("/printers/{printer_id}/fit")
async def printer_bed_fit(
    printer_id: str, width_mm: float, height_mm: float
) -> Dict[str, Any]:
    """Returns whether a width × height design fits this printer's bed."""
    profile = get_profile(printer_id)
    return {
        "printer_id": profile["id"],
        "printer_name": profile["name"],
        "bed_x_mm": profile["bed_x_mm"],
        "bed_y_mm": profile["bed_y_mm"],
        "fits": fits_on_bed(profile, width_mm, height_mm),
    }


class SuggestIn(BaseModel):
    image_id: str
    palette_size: int = 6
    vibrancy: float = 0.0


@api_router.post("/palette/suggest")
async def suggest_palette_endpoint(
    body: SuggestIn,
) -> Dict[str, List[Dict[str, Any]]]:
    if body.image_id not in UPLOADS:
        raise HTTPException(status_code=404, detail="image_id not found")
    image = UPLOADS[body.image_id]
    size = max(2, min(8, body.palette_size))
    vibrancy = max(0.0, min(1.0, body.vibrancy))
    chosen = suggest_palette(image, palette_size=size, vibrancy=vibrancy)
    return {
        "filaments": [
            {"name": f.name, "hex": f.hex, "td": f.td} for f in chosen
        ]
    }


@api_router.post("/upload", response_model=UploadOut)
async def upload(body: UploadIn) -> UploadOut:
    img = _decode_image(body.image_base64)
    # Clamp to reasonable dimensions to avoid memory blow-up before optimizer
    # down-samples it.
    if max(img.size) > 2048:
        ratio = 2048 / max(img.size)
        img = img.resize(
            (int(img.size[0] * ratio), int(img.size[1] * ratio)),
            Image.LANCZOS,
        )
    image_id = str(uuid.uuid4())
    UPLOADS[image_id] = img
    return UploadOut(image_id=image_id, width=img.width, height=img.height)


@api_router.post("/optimize", response_model=OptimizeOut)
async def optimize_endpoint(
    body: OptimizeIn,
    current_user=Depends(get_current_user_dep),
) -> OptimizeOut:
    if body.image_id not in UPLOADS:
        raise HTTPException(status_code=404, detail="image_id not found")
    image = UPLOADS[body.image_id]
    filaments = _filaments_from_input(body.filaments)

    # Frame width (matboard) is expressed in mm in the UI, but the
    # painter works in image pixels — pass the print's shorter usable
    # side so it can convert. Border (geo border) is excluded because
    # the matboard is a print-visible bezel, not the slicer's print
    # border.
    usable_short = max(
        1.0,
        min(body.width_mm, body.height_mm) - 2 * body.border_mm,
    )

    result = optimize(
        image=image,
        filaments=filaments,
        layer_height_mm=body.layer_height_mm,
        total_thickness_mm=body.thickness_mm,
        max_swaps=body.max_swaps,
        max_dimension_px=512,
        auto_order=body.auto_order,
        render_mode=body.render_mode,
        relief=body.relief,
        smoothing=body.smoothing,
        frame_mm=body.frame_mm,
        frame_target_mm=usable_short,
    )

    # Disc geometry: mask preview/heightmap to a circle so the user sees
    # the actual printed area. The STL exporter handles the geometric
    # masking; this only affects the visual preview images.
    # Box-round: same masking applies (the lithophane inside the round
    # lightbox is a disc).
    is_disc_preview = body.geometry == "disc" or (
        body.geometry == "box" and body.box_shape == "round"
    )
    if is_disc_preview:
        import numpy as _np
        h_px, w_px = result.layer_map.shape
        yy, xx = _np.ogrid[:h_px, :w_px]
        cy, cx = (h_px - 1) / 2.0, (w_px - 1) / 2.0
        radius = min(h_px, w_px) / 2.0
        mask = ((yy - cy) ** 2 + (xx - cx) ** 2) <= (radius * radius)
        # Layer map: outside circle → 0 layers (drops out in mesh anyway)
        result.layer_map = _np.where(mask, result.layer_map, 0).astype(_np.int32)
        # Rendered preview: outside circle → black
        result.rendered_rgb = result.rendered_rgb * mask[:, :, None]

    preview = base64.b64encode(rendered_to_png_bytes(result.rendered_rgb)).decode()
    heightmap = base64.b64encode(
        layer_map_to_png_bytes(result.layer_map, result.total_layers)
    ).decode()

    # Count zero-thickness pixels inside the print's actual footprint so
    # the UI can surface them as "voids" alongside the Base-fill slider.
    # For disc / box-round geometry, the mask above already zeroed
    # out-of-circle pixels — re-derive that mask here so we only count
    # voids that the exporter will actually try to print over.
    import numpy as _np
    lm = result.layer_map
    if is_disc_preview:
        h_px, w_px = lm.shape
        yy, xx = _np.ogrid[:h_px, :w_px]
        cy, cx = (h_px - 1) / 2.0, (w_px - 1) / 2.0
        radius = min(h_px, w_px) / 2.0
        in_domain = ((yy - cy) ** 2 + (xx - cx) ** 2) <= (radius * radius)
    else:
        in_domain = _np.ones(lm.shape, dtype=bool)
    void_pixels = int(((lm == 0) & in_domain).sum())
    in_domain_pixels = int(in_domain.sum())

    timeline = []
    z = 0.0
    for fil, n in zip(result.filaments, result.layer_allocation):
        timeline.append({
            "color": fil.hex,
            "name": fil.name,
            "layers": int(n),
            "start_z_mm": round(z, 4),
            "end_z_mm": round(z + n * result.layer_height_mm, 4),
        })
        z += n * result.layer_height_mm

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "image_id": body.image_id,
        "layer_map": result.layer_map,
        "layer_height_mm": result.layer_height_mm,
        "filaments": result.filaments,
        "swap_heights_mm": result.swap_heights_mm,
        "swap_colors": result.swap_colors,
        "allocation": result.layer_allocation,
        "request": body.model_dump(),
    }

    # Persist to user's job history if they're logged in. Failures here
    # must never block the optimize response — anonymous users still get
    # the in-memory path.
    if current_user is not None:
        try:
            await persist_job(
                db,
                current_user.user_id,
                JobPersistData(
                    job_id=job_id,
                    request=body.model_dump(),
                    filaments=result.filaments,
                    layer_map=result.layer_map,
                    layer_height_mm=result.layer_height_mm,
                    swap_heights_mm=result.swap_heights_mm,
                    swap_colors=result.swap_colors,
                    allocation=result.layer_allocation,
                    total_layers=result.total_layers,
                    delta_e_mean=result.delta_e_mean,
                    delta_e_p95=result.delta_e_p95,
                    preview_png_base64=preview,
                    heightmap_png_base64=heightmap,
                    timeline=timeline,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist job %s: %s", job_id, exc)

    return OptimizeOut(
        job_id=job_id,
        preview_png_base64=preview,
        heightmap_png_base64=heightmap,
        delta_e_mean=round(result.delta_e_mean, 3),
        delta_e_p95=round(result.delta_e_p95, 3),
        light_throughput_pct=round(result.light_throughput_pct, 1),
        total_layers=result.total_layers,
        layer_allocation=result.layer_allocation,
        filaments=[{"name": f.name, "hex": f.hex, "td": f.td}
                   for f in result.filaments],
        swap_heights_mm=result.swap_heights_mm,
        timeline=timeline,
        void_pixels=void_pixels,
        in_domain_pixels=in_domain_pixels,
    )


@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job_id,
        "filaments": [{"name": f.name, "hex": f.hex, "td": f.td}
                      for f in job["filaments"]],
        "allocation": job["allocation"],
        "swap_heights_mm": job["swap_heights_mm"],
        "layer_height_mm": job["layer_height_mm"],
    }


def _build_export(
    job_id: str,
    printer_override: Optional[str] = None,
    base_min_layers: int = 2,
) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    req = job["request"]
    geo = GeometrySpec(
        width_mm=req["width_mm"],
        height_mm=req["height_mm"],
        border_mm=req["border_mm"],
        mode=req["geometry"],
        curve_radius_mm=req["curve_radius_mm"],
        dome_mm=float(req.get("dome_mm", 0.0)),
        box_shape=str(req.get("box_shape", "rect") or "rect"),
        box_outer_w_mm=float(req.get("box_outer_w_mm", 110.0) or 110.0),
        box_outer_h_mm=float(req.get("box_outer_h_mm", 110.0) or 110.0),
        box_depth_mm=float(req.get("box_depth_mm", 35.0) or 35.0),
        box_wall_mm=float(req.get("box_wall_mm", 3.0) or 3.0),
        box_led_mount=str(req.get("box_led_mount", "both") or "both"),
        box_puck_diameter_mm=float(req.get("box_puck_diameter_mm", 65.0) or 65.0),
        box_diffuser=bool(req.get("box_diffuser", True)),
        box_cable_notch=bool(req.get("box_cable_notch", True)),
    )
    printer_id = printer_override or req.get("printer_id") or "generic_orca"
    export = build_export(
        layer_map=job["layer_map"],
        layer_height_mm=job["layer_height_mm"],
        geo=geo,
        filament_names=[f.name for f in job["filaments"]],
        swap_heights_mm=job["swap_heights_mm"],
        swap_colors=job["swap_colors"],
        printer_id=printer_id,
        license_text=req.get("license", "") or "",
        base_min_layers=base_min_layers,
        nozzle_mm=float(req.get("nozzle_mm", 0.4) or 0.4),
    )
    return export


async def _ensure_job_in_memory(job_id: str, current_user) -> None:
    """For restored jobs from history: if the in-memory dict doesn't have
    the job but the logged-in user owns it in MongoDB, hydrate it first
    so /api/export/{id}/{kind} can serve the file."""
    if job_id in JOBS:
        return
    if current_user is None:
        return
    stored = await load_job(db, current_user.user_id, job_id)
    if stored is not None:
        JOBS[job_id] = hydrate_in_memory_job(stored)


async def _ensure_job_for_paid_buyer(job_id: str, token: str) -> bool:
    """Buyer flow: if a valid download_token was provided, hydrate the
    seller's job (regardless of owner) into JOBS so the export endpoints
    can serve it. Returns True if the token was valid."""
    if job_id in JOBS:
        return True
    txn = await resolve_download_token(db, job_id, token)
    if txn is None:
        return False
    stored = await load_job_any_owner(db, job_id)
    if stored is None:
        return False
    JOBS[job_id] = hydrate_in_memory_job(stored)
    return True


async def _gate_creator_download(
    job_id: str, kind: str, current_user
) -> None:
    """For creator-side downloads (no buyer token): require sign-in,
    then enforce the per-tier quota and record the usage."""
    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "auth_required",
                "message": "Sign in to download your generated files.",
            },
        )
    await enforce_quota(db, current_user.user_id, job_id)
    # Hydrate the job from MongoDB if it's not in memory.
    await _ensure_job_in_memory(job_id, current_user)
    # Record AFTER hydration so we never bill a user for a missing job.
    await record_download(db, current_user.user_id, job_id, kind)


@api_router.get("/me/quota")
async def my_quota(current_user=Depends(get_current_user_dep)) -> Dict[str, Any]:
    """Return the signed-in user's current quota usage. For guests
    returns a sentinel that the frontend can use to show the gate."""
    if current_user is None:
        return {"tier": "guest", "blocked": True, "limit": 0, "used": 0,
                "remaining": 0, "period": "lifetime", "period_key": "all"}
    state = await get_quota_state(db, current_user.user_id)
    return state.to_dict()


@api_router.get("/export/{job_id}/stl")
async def export_stl(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        # Buyer flow — token grants access, no quota cost.
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "stl", current_user)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    return Response(
        content=export["stl"],
        media_type="model/stl",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}.stl"},
    )


@api_router.get("/export/{job_id}/swaps")
async def export_swaps(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "swaps", current_user)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    return Response(
        content=export["swap_txt"],
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}_swaps.txt"},
    )


@api_router.get("/export/{job_id}/3mf")
async def export_3mf(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "3mf", current_user)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    return Response(
        content=export["threemf"],
        media_type="model/3mf",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}.3mf"},
    )


# --- Lightbox part downloads (box geometry only) ---------------------------

def _require_box_geometry(job: Dict[str, Any], job_id: str) -> None:
    req = job.get("request") or {}
    if req.get("geometry") != "box":
        raise HTTPException(
            status_code=400,
            detail="lightbox parts are only available when geometry=box",
        )


@api_router.get("/export/{job_id}/lightbox-frame")
async def export_lightbox_frame(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "lightbox_frame", current_user)
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    _require_box_geometry(job, job_id)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    if "lightbox_frame_stl" not in export:
        raise HTTPException(status_code=500, detail="lightbox frame not built")
    return Response(
        content=export["lightbox_frame_stl"],
        media_type="model/stl",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}_lightbox_frame.stl"},
    )


@api_router.get("/export/{job_id}/lightbox-back")
async def export_lightbox_back(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "lightbox_back", current_user)
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    _require_box_geometry(job, job_id)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    if "lightbox_back_stl" not in export:
        raise HTTPException(status_code=500, detail="lightbox back panel not built")
    return Response(
        content=export["lightbox_back_stl"],
        media_type="model/stl",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}_lightbox_back.stl"},
    )


@api_router.get("/export/{job_id}/lightbox-diffuser")
async def export_lightbox_diffuser(
    job_id: str,
    current_user=Depends(get_current_user_dep),
    token: Optional[str] = None,
    printer: Optional[str] = None,
    base_layers: int = 2,
) -> Response:
    if token:
        await _ensure_job_for_paid_buyer(job_id, token)
    else:
        await _gate_creator_download(job_id, "lightbox_diffuser", current_user)
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    _require_box_geometry(job, job_id)
    export = _build_export(job_id, printer_override=printer, base_min_layers=base_layers)
    if "lightbox_diffuser_stl" not in export:
        raise HTTPException(
            status_code=404,
            detail="diffuser disabled for this job",
        )
    return Response(
        content=export["lightbox_diffuser_stl"],
        media_type="model/stl",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}_lightbox_diffuser.stl"},
    )


# ---- Legacy status demo endpoints (kept for template compatibility) ------

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate) -> StatusCheck:
    status_obj = StatusCheck(**input.model_dump())
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks() -> List[Dict[str, Any]]:
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check["timestamp"], str):
            check["timestamp"] = datetime.fromisoformat(check["timestamp"])
    return status_checks


app.include_router(api_router)

# Mount the auth + per-user routers (built earlier so optimize endpoint
# can use the optional-user dep).
presets_router = build_presets_router(db, require_user_dep)
jobs_router = build_jobs_router(db, require_user_dep, JOBS)
marketplace_router = build_marketplace_router(db, require_user_dep, get_current_user_dep)
checkout_router = build_checkout_router(db)
braintree_router = build_braintree_router(db)
admin_router = build_admin_router(db, require_user_dep)
sso_bridge_router = build_sso_bridge_router(db, get_current_user_dep)
meshy_router = build_meshy_router(require_user_dep)
payouts_router = build_payouts_router(db, require_user_dep)
require_admin_dep = build_require_admin(require_user_dep)
admin_payouts_router = build_admin_payouts_router(db, require_admin_dep)
paypal_webhook_router = build_paypal_webhook_router(db)
filament_lib_router = build_filament_library_router(db, require_user_dep, get_current_user_dep)
app.include_router(auth_router, prefix="/api")
app.include_router(presets_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(marketplace_router, prefix="/api")
app.include_router(checkout_router, prefix="/api")
app.include_router(braintree_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(sso_bridge_router, prefix="/api")
app.include_router(meshy_router, prefix="/api")
app.include_router(admin_payouts_router, prefix="/api")
app.include_router(payouts_router, prefix="/api")
app.include_router(paypal_webhook_router, prefix="/api")
app.include_router(filament_lib_router)

def _cors_origins() -> list[str]:
    """Build the CORS allowlist from two env sources:
    - `CORS_ORIGINS` — the app's own frontend origins (preview + prod)
    - `FORGE_SUITE_PEERS` — every Forge Suite peer (ForgeSlicer + future siblings)
       so the cross-origin SSO bridge POST/preflight succeeds without
       hand-editing this list each time we add a peer.
    """
    primary = [
        o.strip().rstrip("/")
        for o in (os.environ.get("CORS_ORIGINS") or "").split(",")
        if o.strip()
    ]
    peers = [
        p.strip().rstrip("/")
        for p in (os.environ.get("FORGE_SUITE_PEERS") or "").split(",")
        if p.strip()
    ]
    # De-dup while preserving order so the most-likely origin (own
    # frontend) is checked first by the middleware.
    seen, out = set(), []
    for o in primary + peers:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    if _SCHEDULER is not None and _SCHEDULER.running:
        _SCHEDULER.shutdown(wait=False)
    client.close()


# ---------------------------------------------------------------------------
# Weekly PayPal payout scheduler — runs Mondays 00:00 UTC.
# Set PAYOUT_SCHEDULER_DISABLED=1 in tests or one-off jobs.
# ---------------------------------------------------------------------------

_SCHEDULER = None


@app.on_event("startup")
async def _start_payout_scheduler() -> None:
    global _SCHEDULER
    if os.environ.get("PAYOUT_SCHEDULER_DISABLED") == "1":
        logger.info("Payout scheduler disabled via env")
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed — payouts won't auto-run")
        return

    async def _job():
        try:
            result = await run_payout_batch(db, triggered_by="scheduler")
            logger.info("Weekly payout batch result: %s", result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Weekly payout batch crashed: %s", exc)

    _SCHEDULER = AsyncIOScheduler(timezone="UTC")
    _SCHEDULER.add_job(
        _job,
        CronTrigger(day_of_week="mon", hour=0, minute=0, timezone="UTC"),
        id="weekly_paypal_payouts",
        replace_existing=True,
    )
    _SCHEDULER.start()
    logger.info("Payout scheduler started — next run: Mondays 00:00 UTC")
