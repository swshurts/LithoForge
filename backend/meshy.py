"""Meshy.ai text-to-image integration — turns a free-form voice prompt
into a lithophane-ready image.

Why text-to-image not text-to-3D: lithophanes are 2D grayscale → height
map, so we never need Meshy's full mesh output. The `nano-banana` model
is 3 credits/call (~$0.01) and produces good single-subject art with a
clear background, which is exactly what produces a clean lithophane.

We bias every prompt with a lithophane-tuned style suffix
("high contrast, single subject, plain background, photographic
detail") to nudge Meshy toward outputs that map cleanly into our
Beer-Lambert pipeline.

Flow:
    POST /api/meshy/text-to-image { prompt }     → { task_id }
    GET  /api/meshy/text-to-image/{task_id}      → { status, image_url? }

Frontend polls the second endpoint until status="SUCCEEDED", then
hands the image_url off to the existing /api/upload-by-url path.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("lithoforge.meshy")

MESHY_BASE = "https://api.meshy.ai"
LITHOPHANE_STYLE_SUFFIX = (
    " · high contrast, single subject centered, plain dark or solid "
    "background, dramatic studio lighting, photographic detail, no text"
)


def _meshy_key() -> str:
    key = (os.environ.get("MESHY_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            503,
            detail="Meshy API key not configured — set MESHY_API_KEY in backend/.env.",
        )
    return key


class TextToImageIn(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=600)


class TextToImageOut(BaseModel):
    task_id: str
    model: str
    biased_prompt: str


class TaskStatusOut(BaseModel):
    task_id: str
    status: str
    image_url: str | None = None
    progress: int = 0
    raw: Dict[str, Any] = Field(default_factory=dict)


def build_meshy_router(require_user_dep) -> APIRouter:
    router = APIRouter(prefix="/meshy", tags=["meshy"])

    @router.post("/text-to-image", response_model=TextToImageOut)
    async def create_task(body: TextToImageIn, _=Depends(require_user_dep)):
        biased = body.prompt.strip() + LITHOPHANE_STYLE_SUFFIX
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.post(
                f"{MESHY_BASE}/openapi/v1/text-to-image",
                headers={
                    "Authorization": f"Bearer {_meshy_key()}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": biased,
                    "ai_model": "nano-banana",
                    # Aspect ratio 1:1 is closest to LithoForge's
                    # default 100×100 mm canvas; the user can crop later.
                    "aspect_ratio": "1:1",
                },
            )
        if r.status_code != 200 and r.status_code != 202:
            logger.warning("Meshy create failed: %s %s", r.status_code, r.text[:300])
            raise HTTPException(
                502,
                detail=f"Meshy text-to-image failed: {r.status_code} {r.text[:200]}",
            )
        data = r.json()
        # Meshy returns either {"result": "<id>"} or {"id": "<id>"} depending
        # on the model — handle both.
        task_id = data.get("result") or data.get("id") or data.get("task_id")
        if not task_id:
            raise HTTPException(502, detail=f"Meshy returned no task id: {data}")
        return TextToImageOut(
            task_id=task_id, model="nano-banana", biased_prompt=biased
        )

    @router.get("/text-to-image/{task_id}", response_model=TaskStatusOut)
    async def get_status(task_id: str, _=Depends(require_user_dep)):
        async with httpx.AsyncClient(timeout=20.0) as http:
            r = await http.get(
                f"{MESHY_BASE}/openapi/v1/text-to-image/{task_id}",
                headers={"Authorization": f"Bearer {_meshy_key()}"},
            )
        if r.status_code != 200:
            raise HTTPException(
                502,
                detail=f"Meshy status fetch failed: {r.status_code} {r.text[:200]}",
            )
        d = r.json()
        # Image URL can live under several keys depending on the model
        # version — try the common ones in order.
        image_url = (
            d.get("image_url")
            or (d.get("image_urls") or [None])[0]
            or d.get("model_urls", {}).get("glb")  # fallback should never fire for text-to-image
        )
        return TaskStatusOut(
            task_id=task_id,
            status=str(d.get("status") or d.get("state") or "PENDING").upper(),
            image_url=image_url,
            progress=int(d.get("progress") or 0),
            raw={"prompt": d.get("prompt"), "model": d.get("model")},
        )

    return router
