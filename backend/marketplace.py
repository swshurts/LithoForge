"""Marketplace routes — Phase A (browse + creator profiles, no payments).

Creators flip a job's `listing` to make it publicly visible.
Phase B will layer Stripe checkout on top of these same listings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

# Platform's cut of every sale, applied at Stripe checkout in Phase B.
PLATFORM_FEE_PCT = 6.0


class ListingIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    price_usd: float = Field(ge=0.0, le=10000.0)
    license: str = Field(default="All Rights Reserved", max_length=120)


class ListingPublic(BaseModel):
    job_id: str
    title: str
    description: str
    price_usd: float
    license: str = "All Rights Reserved"
    creator_id: str
    creator_name: str
    creator_picture: str = ""
    thumbnail_base64: str
    render_mode: str
    total_layers: int
    listed_at: str
    designed_for_printer: str = ""  # printer profile id (display only)
    width_mm: float = 0.0
    height_mm: float = 0.0
    geometry: str = "flat"


class ListingDetail(ListingPublic):
    preview_png_base64: str
    platform_fee_pct: float = PLATFORM_FEE_PCT
    filaments: List[Dict[str, Any]] = []


class CreatorProfile(BaseModel):
    user_id: str
    name: str
    picture: str = ""
    listings: List[ListingPublic]


def _iso(dt) -> str:
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return ""


def _job_to_listing_public(
    job: Dict[str, Any], user_map: Dict[str, Dict[str, Any]]
) -> ListingPublic:
    listing = job.get("listing", {})
    user = user_map.get(job["user_id"], {})
    request = job.get("request", {}) or {}
    return ListingPublic(
        job_id=job["job_id"],
        title=listing.get("title", "Untitled"),
        description=listing.get("description", ""),
        price_usd=float(listing.get("price_usd", 0.0)),
        license=listing.get("license", "All Rights Reserved"),
        creator_id=job["user_id"],
        creator_name=user.get("name") or user.get("email", "Anonymous"),
        creator_picture=user.get("picture", ""),
        thumbnail_base64=job.get("thumbnail_base64", ""),
        render_mode=job.get("render_mode", "lithophane"),
        total_layers=int(job.get("total_layers", 0)),
        listed_at=_iso(listing.get("listed_at")),
        designed_for_printer=request.get("printer_id", "") or "",
        width_mm=float(request.get("width_mm", 0.0) or 0.0),
        height_mm=float(request.get("height_mm", 0.0) or 0.0),
        geometry=request.get("geometry", "flat") or "flat",
    )


def build_marketplace_router(
    db: AsyncIOMotorDatabase, require_user, get_current_user_dep
) -> APIRouter:
    router = APIRouter(tags=["marketplace"])

    # --- Creator-side: publish / unpublish a job -------------------------
    @router.put("/my-jobs/{job_id}/listing", response_model=ListingPublic)
    async def publish_listing(
        job_id: str, body: ListingIn, user=Depends(require_user)
    ):
        job = await db.jobs.find_one(
            {"user_id": user.user_id, "job_id": job_id}, {"_id": 0}
        )
        if not job:
            raise HTTPException(404, "Job not found")
        listing = {
            "title": body.title.strip(),
            "description": body.description.strip(),
            "price_usd": float(body.price_usd),
            "license": body.license.strip() or "All Rights Reserved",
            "visibility": "listed",
            "listed_at": datetime.now(timezone.utc),
        }
        await db.jobs.update_one(
            {"user_id": user.user_id, "job_id": job_id},
            {"$set": {"listing": listing}},
        )
        job["listing"] = listing
        user_map = {
            user.user_id: {
                "name": user.name,
                "email": user.email,
                "picture": user.picture,
            }
        }
        return _job_to_listing_public(job, user_map)

    @router.delete("/my-jobs/{job_id}/listing")
    async def unpublish_listing(job_id: str, user=Depends(require_user)):
        result = await db.jobs.update_one(
            {"user_id": user.user_id, "job_id": job_id},
            {"$unset": {"listing": ""}},
        )
        if result.matched_count == 0:
            raise HTTPException(404, "Job not found")
        return {"ok": True}

    # --- Public: browse + detail + creator profile ----------------------
    @router.get("/marketplace", response_model=List[ListingPublic])
    async def browse(limit: int = 60, skip: int = 0):
        cursor = (
            db.jobs.find(
                {"listing.visibility": "listed"},
                {
                    "_id": 0,
                    "job_id": 1,
                    "user_id": 1,
                    "listing": 1,
                    "thumbnail_base64": 1,
                    "render_mode": 1,
                    "total_layers": 1,
                    "request": 1,
                },
            )
            .sort("listing.listed_at", -1)
            .skip(skip)
            .limit(min(limit, 120))
        )
        jobs = await cursor.to_list(120)
        if not jobs:
            return []
        user_ids = list({j["user_id"] for j in jobs})
        users = await db.users.find(
            {"user_id": {"$in": user_ids}}, {"_id": 0}
        ).to_list(len(user_ids))
        user_map = {u["user_id"]: u for u in users}
        return [_job_to_listing_public(j, user_map) for j in jobs]

    @router.get("/marketplace/{job_id}", response_model=ListingDetail)
    async def listing_detail(job_id: str):
        job = await db.jobs.find_one(
            {"job_id": job_id, "listing.visibility": "listed"},
            {"_id": 0},
        )
        if not job:
            raise HTTPException(404, "Listing not found")
        user = await db.users.find_one(
            {"user_id": job["user_id"]}, {"_id": 0}
        ) or {}
        user_map = {job["user_id"]: user}
        public = _job_to_listing_public(job, user_map)
        return ListingDetail(
            **public.model_dump(),
            preview_png_base64=job.get("preview_png_base64", ""),
            filaments=[
                {"name": f.get("name", ""), "hex": f.get("hex", "#000000"),
                 "td": float(f.get("td", 1.0))}
                for f in (job.get("filaments") or [])
            ],
        )

    @router.get("/creators/{user_id}", response_model=CreatorProfile)
    async def creator_profile(user_id: str):
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(404, "Creator not found")
        cursor = (
            db.jobs.find(
                {"user_id": user_id, "listing.visibility": "listed"},
                {
                    "_id": 0,
                    "job_id": 1,
                    "user_id": 1,
                    "listing": 1,
                    "thumbnail_base64": 1,
                    "render_mode": 1,
                    "total_layers": 1,
                    "request": 1,
                },
            )
            .sort("listing.listed_at", -1)
            .limit(120)
        )
        jobs = await cursor.to_list(120)
        user_map = {user_id: user}
        return CreatorProfile(
            user_id=user_id,
            name=user.get("name") or user.get("email", "Anonymous"),
            picture=user.get("picture", ""),
            listings=[_job_to_listing_public(j, user_map) for j in jobs],
        )

    # Discreet "is this job listed?" check for the creator's own UI.
    @router.get("/my-jobs/{job_id}/listing")
    async def my_listing_status(
        job_id: str, user=Depends(require_user)
    ):
        job = await db.jobs.find_one(
            {"user_id": user.user_id, "job_id": job_id},
            {"_id": 0, "listing": 1},
        )
        if not job:
            raise HTTPException(404, "Job not found")
        listing = job.get("listing") or None
        return {"listed": bool(listing), "listing": listing}

    # Suppress unused warning — kept for Phase B token routes.
    _ = get_current_user_dep
    return router
