"""Forge Suite — route generated lithophanes (and lightbox parts) to
ForgeSlicer's inbox endpoint.

Flow: user is signed into Lithoforge → clicks "Send to ForgeSlicer" on
a generated job → this module:
    1. Reads the user's session_token (cookie OR Authorization Bearer
       header) off the incoming request.
    2. Builds the requested export part (lithophane mesh / lightbox
       frame / back / diffuser) in either STL or 3MF.
    3. POSTs it to https://forgeslicer.com/api/litho/inbox as
       multipart/form-data with the user's session_token forwarded as
       `Authorization: Bearer <session_token>` so ForgeSlicer attaches
       the file to the same Emergent identity.

The form fields ForgeSlicer expects:
    file            — bytes of the STL/3MF
    name            — filename + display label
    format          — "stl" | "3mf"
    source_shape    — one of: flat, curved, cylinder, disc,
                      lightbox_rect, lightbox_circle
    source_metadata — JSON string of {job_id, dimensions, …} (optional)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Literal, Optional

import httpx
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ForgeSlicer's inbox endpoint. Override-able via env for testing
# against the ForgeSlicer preview deployment.
# In-memory override (test-only, set via /_dev/inbox-url) takes
# precedence over the env var.
_INBOX_OVERRIDE: Optional[str] = None


def _inbox_url() -> str:
    if _INBOX_OVERRIDE is not None:
        return _INBOX_OVERRIDE
    return (
        os.environ.get("FORGESLICER_INBOX_URL")
        or "https://forgeslicer.com/api/litho/inbox"
    )


# Map (part, geometry, box_shape) → ForgeSlicer's `source_shape` enum.
def _resolve_source_shape(part: str, geometry: str, box_shape: str) -> str:
    if part == "lithophane":
        if geometry == "box":
            return "disc" if box_shape == "round" else "flat"
        # Backend's "cylindrical" maps to ForgeSlicer's "cylinder".
        if geometry == "cylindrical":
            return "cylinder"
        return geometry  # flat / curved / disc
    if part in ("lightbox_frame", "lightbox_back", "lightbox_diffuser"):
        return "lightbox_circle" if box_shape == "round" else "lightbox_rect"
    raise HTTPException(400, f"Unknown part: {part}")


class SendIn(BaseModel):
    """JSON body for /api/forgeslicer/send/{job_id}.

    `part` selects which artefact to ship. `format` is honoured only
    for `lithophane`; lightbox parts only ship as STL today.
    """
    part: Literal[
        "lithophane", "lightbox_frame", "lightbox_back", "lightbox_diffuser"
    ] = "lithophane"
    format: Literal["stl", "3mf"] = "3mf"
    name: Optional[str] = None  # defaults to lithophane_{job_id}_{part}.{ext}


class InboxOverrideIn(BaseModel):
    """Test-only inbox-URL override body."""
    url: Optional[str] = None


def _get_session_token(
    session_token_cookie: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    """Same precedence as auth.py: cookie wins, then Bearer header."""
    if session_token_cookie:
        return session_token_cookie
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip() or None
    return None


def build_forgeslicer_router(
    jobs_in_memory: Dict[str, Dict[str, Any]],
    build_export_fn,
    ensure_job_in_memory_fn,
    require_user_dep,
) -> APIRouter:
    """`jobs_in_memory` and `build_export_fn` are injected from server.py
    so this module stays decoupled from the JOBS singleton and the
    geometry pipeline."""
    router = APIRouter(prefix="/forgeslicer", tags=["forgeslicer"])

    @router.post("/send/{job_id}")
    async def send_to_forgeslicer(
        job_id: str,
        body: SendIn,
        user=Depends(require_user_dep),
        session_token: Optional[str] = Cookie(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        # 1) Grab the caller's session_token so we can hand it to
        # ForgeSlicer as Bearer auth.
        token = _get_session_token(session_token, authorization)
        if not token:
            # `require_user_dep` would normally catch this, but be
            # explicit since the token is the WHOLE point.
            raise HTTPException(401, "Missing session_token")

        # 2) Hydrate the job (in case it lives only in MongoDB).
        await ensure_job_in_memory_fn(job_id, user)
        job = jobs_in_memory.get(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")

        # 3) Build the requested artefact.
        export = build_export_fn(job_id)
        part = body.part
        fmt = body.format
        if part == "lithophane":
            if fmt == "stl":
                file_bytes = export["stl"]
                mime = "model/stl"
                ext = "stl"
            else:
                file_bytes = export["threemf"]
                mime = "model/3mf"
                ext = "3mf"
        else:
            key = f"{part}_stl"  # lightbox_frame_stl etc.
            if key not in export:
                raise HTTPException(
                    400,
                    f"Part '{part}' was not built for this job — "
                    "make sure geometry=box and the diffuser is enabled "
                    "when sending the diffuser.",
                )
            file_bytes = export[key]
            mime = "model/stl"
            ext = "stl"
            fmt = "stl"

        # 4) Compute source_shape from job geometry + part.
        req = job.get("request", {})
        geometry = req.get("geometry", "flat")
        box_shape = req.get("box_shape", "rect")
        source_shape = _resolve_source_shape(part, geometry, box_shape)

        # 5) Build display name + payload.
        display_name = (
            body.name
            or f"lithophane_{job_id}_{part}.{ext}"
        )

        metadata: Dict[str, Any] = {
            "job_id": job_id,
            "part": part,
            "geometry": geometry,
            "width_mm": req.get("width_mm"),
            "height_mm": req.get("height_mm"),
            "thickness_mm": req.get("thickness_mm"),
            "layer_height_mm": req.get("layer_height_mm"),
            "nozzle_mm": req.get("nozzle_mm"),
            "printer_id": req.get("printer_id"),
            "triangle_count": export.get("triangle_count"),
        }
        if geometry == "box":
            metadata.update({
                "box_shape": box_shape,
                "box_outer_w_mm": req.get("box_outer_w_mm"),
                "box_outer_h_mm": req.get("box_outer_h_mm"),
                "box_depth_mm": req.get("box_depth_mm"),
            })
        # Drop None fields so we don't ship empty keys.
        metadata = {k: v for k, v in metadata.items() if v is not None}

        files = {
            "file": (display_name, file_bytes, mime),
        }
        data = {
            "name": display_name,
            "format": fmt,
            "source_shape": source_shape,
            "source_metadata": json.dumps(metadata),
        }

        # 6) POST to ForgeSlicer with the caller's session_token forwarded.
        url = _inbox_url()
        headers = {
            "Authorization": f"Bearer {token}",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.post(url, headers=headers, files=files, data=data)
        except httpx.HTTPError as exc:
            logger.exception("ForgeSlicer inbox POST failed for job %s", job_id)
            raise HTTPException(502, f"ForgeSlicer unreachable: {exc!s}")

        # 7) Pass through ForgeSlicer's response. Try JSON first, then text.
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            payload = {"raw": resp.text[:500]}

        if resp.status_code >= 400:
            raise HTTPException(
                resp.status_code,
                detail={
                    "error": "forgeslicer_rejected",
                    "status": resp.status_code,
                    "forgeslicer_response": payload,
                },
            )

        return {
            "ok": True,
            "part": part,
            "format": fmt,
            "source_shape": source_shape,
            "bytes_sent": len(file_bytes),
            "forgeslicer_response": payload,
        }

    class _InboxOverride(BaseModel):
        url: Optional[str] = None

    @router.post("/_dev/inbox-url")
    async def set_inbox_url(body: InboxOverrideIn, user=Depends(require_user_dep)):
        """Test-only override for the ForgeSlicer inbox URL. Requires a
        super-admin (we lean on Forge's existing identity model — the
        super-admin flag is the same one that gates `/api/admin/*`).
        Pass `url: null` to clear and fall back to env / default."""
        if not (getattr(user, "is_super_admin", False) or getattr(user, "is_admin", False)):
            raise HTTPException(403, "admin required")
        global _INBOX_OVERRIDE  # noqa: PLW0603
        _INBOX_OVERRIDE = body.url
        return {"ok": True, "inbox_url": _inbox_url()}

    return router
