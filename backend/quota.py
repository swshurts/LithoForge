"""Per-user download quota + subscription tier tracking.

Pricing (subject to change — Stripe not yet integrated):
  • free      → 5 lifetime downloads (hard block on the 6th)
  • hobbyist  → 25 downloads per calendar month
  • pro       → unlimited downloads, marketplace publishing, payouts

A "use" is counted at successful DOWNLOAD of the creator's own job
(STL / 3MF / swap text from /api/export/{id}/{kind}). Buyers using a
download_token from a paid marketplace purchase are NEVER counted —
they paid for that. Re-downloads of the same (job_id, kind) by the same
user are counted as a single use so users aren't punished for grabbing
the file twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

TIER_LIMITS = {
    "free": {"period": "lifetime", "limit": 5},
    "hobbyist": {"period": "monthly", "limit": 25},
    "pro": {"period": "monthly", "limit": None},  # None = unlimited
}


def current_period_key(period: str, now: Optional[datetime] = None) -> str:
    """Returns a string identifying the user's current usage window.
    'lifetime' → 'all'  ·  'monthly' → 'YYYY-MM'."""
    if period == "lifetime":
        return "all"
    now = now or datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


@dataclass
class QuotaState:
    tier: str
    period: str          # 'lifetime' or 'monthly'
    period_key: str      # 'all' or '2026-02'
    limit: Optional[int]  # None = unlimited
    used: int
    remaining: Optional[int]  # None when unlimited
    blocked: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "period": self.period,
            "period_key": self.period_key,
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "blocked": self.blocked,
        }


async def get_quota_state(
    db: AsyncIOMotorDatabase, user_id: str
) -> QuotaState:
    """Read tier + current-period usage from MongoDB."""
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "tier": 1, "downloads": 1},
    ) or {}
    tier = user.get("tier") or "free"
    cfg = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    period = cfg["period"]
    limit = cfg["limit"]
    period_key = current_period_key(period)

    downloads = user.get("downloads") or {}
    used = int(downloads.get(period_key, 0))

    remaining = None if limit is None else max(0, limit - used)
    blocked = (limit is not None) and (used >= limit)

    return QuotaState(
        tier=tier,
        period=period,
        period_key=period_key,
        limit=limit,
        used=used,
        remaining=remaining,
        blocked=blocked,
    )


async def record_download(
    db: AsyncIOMotorDatabase, user_id: str, job_id: str, kind: str
) -> QuotaState:
    """Increment the usage counter for this user. Idempotent on
    (user_id, job_id) — downloading STL + 3MF + swaps for the same job
    only counts as ONE use, so creators aren't penalized for grabbing
    all three formats. Returns the updated quota state.

    Note: we still allow the download even if the user is at their
    quota limit AT THE TIME OF CALL — the export endpoints call
    enforce_quota() FIRST to block, so by the time we reach here the
    user is within their allowance.
    """
    state = await get_quota_state(db, user_id)
    period_key = state.period_key

    # Track which (user, job) pairs we've already counted this period.
    seen_key = f"downloads_seen.{period_key}.{job_id}"
    user = await db.users.find_one(
        {"user_id": user_id, seen_key: {"$exists": True}},
        {"_id": 0},
    )
    if user is not None:
        # Already counted — record the kind for analytics but don't
        # bump the usage counter.
        await db.users.update_one(
            {"user_id": user_id},
            {"$addToSet": {seen_key: kind}},
        )
        return state

    await db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": {f"downloads.{period_key}": 1},
            "$set": {f"downloads_seen.{period_key}.{job_id}": [kind]},
        },
    )
    return await get_quota_state(db, user_id)


async def enforce_quota(
    db: AsyncIOMotorDatabase, user_id: str, job_id: str
) -> QuotaState:
    """Returns current quota state. Raises if blocked (and we haven't
    already counted this job for this period — re-downloads of an
    already-counted job are always permitted)."""
    from fastapi import HTTPException

    state = await get_quota_state(db, user_id)
    if not state.blocked:
        return state

    # Was this job already counted this period? If so, re-downloads OK.
    seen_path = f"downloads_seen.{state.period_key}.{job_id}"
    already = await db.users.find_one(
        {"user_id": user_id, seen_path: {"$exists": True}},
        {"_id": 0, "user_id": 1},
    )
    if already:
        return state

    raise HTTPException(
        status_code=402,
        detail={
            "error": "quota_exceeded",
            "tier": state.tier,
            "limit": state.limit,
            "used": state.used,
            "message": (
                f"You've used all {state.limit} downloads on the {state.tier} "
                f"plan. Upgrade to Hobbyist (25/mo) or Pro (unlimited) to "
                f"keep printing."
            ),
        },
    )
