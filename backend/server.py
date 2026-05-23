"""FastAPI server for the CMYKW Lithophane generator."""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Response
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
from auth import build_auth
from presets import build_presets_router


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
    thickness_mm: float = 3.0
    border_mm: float = 2.0
    layer_height_mm: float = 0.12
    max_swaps: int = 5
    geometry: str = "flat"     # flat | curved | cylindrical
    curve_radius_mm: float = 80.0
    filaments: Optional[List[FilamentIn]] = None
    auto_order: bool = True
    render_mode: str = "lithophane"  # "lithophane" | "painting"
    relief: float = 0.5              # painting mode only, 0..1


class OptimizeOut(BaseModel):
    job_id: str
    preview_png_base64: str
    heightmap_png_base64: str
    delta_e_mean: float
    delta_e_p95: float
    total_layers: int
    layer_allocation: List[int]
    filaments: List[Dict[str, Any]]
    swap_heights_mm: List[float]
    timeline: List[Dict[str, Any]]  # [{color, name, layers, height_mm}]


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
async def root():
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
async def client_error(body: ClientErrorReport):
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
async def default_filaments():
    return {"filaments": [{"name": f.name, "hex": f.hex, "td": f.td}
                          for f in DEFAULT_FILAMENTS]}


@api_router.get("/filaments/library")
async def filament_library():
    """The full curated filament library used by the palette suggester."""
    return {"filaments": [{"name": f.name, "hex": f.hex, "td": f.td}
                          for f in FILAMENT_LIBRARY]}


class SuggestIn(BaseModel):
    image_id: str
    palette_size: int = 6
    vibrancy: float = 0.0


@api_router.post("/palette/suggest")
async def suggest_palette_endpoint(body: SuggestIn):
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
async def upload(body: UploadIn):
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
async def optimize_endpoint(body: OptimizeIn):
    if body.image_id not in UPLOADS:
        raise HTTPException(status_code=404, detail="image_id not found")
    image = UPLOADS[body.image_id]
    filaments = _filaments_from_input(body.filaments)

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
    )

    preview = base64.b64encode(rendered_to_png_bytes(result.rendered_rgb)).decode()
    heightmap = base64.b64encode(
        layer_map_to_png_bytes(result.layer_map, result.total_layers)
    ).decode()

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

    return OptimizeOut(
        job_id=job_id,
        preview_png_base64=preview,
        heightmap_png_base64=heightmap,
        delta_e_mean=round(result.delta_e_mean, 3),
        delta_e_p95=round(result.delta_e_p95, 3),
        total_layers=result.total_layers,
        layer_allocation=result.layer_allocation,
        filaments=[{"name": f.name, "hex": f.hex, "td": f.td}
                   for f in result.filaments],
        swap_heights_mm=result.swap_heights_mm,
        timeline=timeline,
    )


@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str):
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


def _build_export(job_id: str) -> Dict[str, Any]:
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
    )
    export = build_export(
        layer_map=job["layer_map"],
        layer_height_mm=job["layer_height_mm"],
        geo=geo,
        filament_names=[f.name for f in job["filaments"]],
        swap_heights_mm=job["swap_heights_mm"],
        swap_colors=job["swap_colors"],
    )
    return export


@api_router.get("/export/{job_id}/stl")
async def export_stl(job_id: str):
    export = _build_export(job_id)
    return Response(
        content=export["stl"],
        media_type="model/stl",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}.stl"},
    )


@api_router.get("/export/{job_id}/swaps")
async def export_swaps(job_id: str):
    export = _build_export(job_id)
    return Response(
        content=export["swap_txt"],
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}_swaps.txt"},
    )


@api_router.get("/export/{job_id}/3mf")
async def export_3mf(job_id: str):
    export = _build_export(job_id)
    return Response(
        content=export["threemf"],
        media_type="model/3mf",
        headers={"Content-Disposition": f"attachment; filename=lithophane_{job_id}.3mf"},
    )


# ---- Legacy status demo endpoints (kept for template compatibility) ------

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.model_dump())
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check["timestamp"], str):
            check["timestamp"] = datetime.fromisoformat(check["timestamp"])
    return status_checks


app.include_router(api_router)

# Auth + per-user preset routers (mounted under /api).
auth_router, _, require_user_dep = build_auth(db)
presets_router = build_presets_router(db, require_user_dep)
app.include_router(auth_router, prefix="/api")
app.include_router(presets_router, prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
