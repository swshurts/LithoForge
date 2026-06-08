"""Admin / super-admin moderation surface.

Auth model:
  - SUPER_ADMIN_EMAILS env var (comma-separated) seeds `is_super_admin`
    on every login (see auth.py).
  - Super-admins are also implicitly admins.
  - Regular admins are granted/revoked by super-admins via the toggle
    endpoint below.

Endpoints (all prefixed with /api/admin):
  GET    /me                            — current admin's record
  GET    /users?q=&limit=&skip=         — search/paginate
  GET    /users/{id}                    — full record + recent activity
  POST   /users/{id}/admin              — toggle is_admin (super only)
  POST   /users/{id}/suspend            — toggle is_suspended
  PATCH  /users/{id}                    — update ai_quota_override
  GET    /audit?action=&limit=          — read audit log

Audit-log invariant: every state-changing endpoint in this module
writes an `admin_audit_log` entry. The read-only endpoints do not.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel


class AdminUser(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str = ""
    is_admin: bool = False
    is_super_admin: bool = False
    is_suspended: bool = False
    ai_quota_override: Optional[int] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class AuditEntry(BaseModel):
    actor_user_id: str
    actor_email: str
    action: str
    target_user_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    created_at: datetime


class UserPatch(BaseModel):
    ai_quota_override: Optional[int] = None


def build_require_admin(require_user_dep):
    """Factory returning a FastAPI dependency that allows only admins
    or super-admins. Reused by every admin-protected router."""

    async def require_admin(user=Depends(require_user_dep)):
        if not (user.is_admin or user.is_super_admin):
            raise HTTPException(status_code=403, detail="Admin only")
        return user

    return require_admin


def build_admin_router(
    db: AsyncIOMotorDatabase,
    require_user_dep,
) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin"])

    require_admin = build_require_admin(require_user_dep)

    async def require_super_admin(user=Depends(require_user_dep)):
        if not user.is_super_admin:
            raise HTTPException(status_code=403, detail="Super-admin only")
        return user

    async def _audit(actor, action: str, target_user_id: Optional[str], payload: dict):
        await db.admin_audit_log.insert_one(
            {
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "action": action,
                "target_user_id": target_user_id,
                "payload": payload,
                "created_at": datetime.now(timezone.utc),
            }
        )

    @router.get("/me", response_model=AdminUser)
    async def me(actor=Depends(require_admin)):
        # Authoritative source: the user doc itself, not the cached
        # `actor` Pydantic snapshot (might be stale wrt last_login_at).
        doc = await db.users.find_one(
            {"user_id": actor.user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(404, "User vanished")
        return AdminUser(**doc)

    @router.get("/users", response_model=List[AdminUser])
    async def list_users(
        q: Optional[str] = Query(None, description="case-insensitive substring of email or name"),
        limit: int = Query(50, ge=1, le=200),
        skip: int = Query(0, ge=0),
        _=Depends(require_admin),
    ):
        match: Dict[str, Any] = {}
        if q:
            # MongoDB $regex with $options i for case-insensitive substring.
            import re
            escaped = re.escape(q)
            match["$or"] = [
                {"email": {"$regex": escaped, "$options": "i"}},
                {"name": {"$regex": escaped, "$options": "i"}},
            ]
        cur = (
            db.users.find(match, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [AdminUser(**doc) async for doc in cur]

    @router.get("/users/{user_id}", response_model=AdminUser)
    async def user_detail(user_id: str, _=Depends(require_admin)):
        doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Not found")
        return AdminUser(**doc)

    @router.post("/users/{user_id}/admin")
    async def toggle_admin(user_id: str, actor=Depends(require_super_admin)):
        target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not target:
            raise HTTPException(404, "Not found")
        if target.get("is_super_admin"):
            # Super-admins are managed via env var, not via UI.
            raise HTTPException(
                400, "Super-admins are managed via SUPER_ADMIN_EMAILS"
            )
        new_val = not bool(target.get("is_admin"))
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": new_val}},
        )
        await _audit(actor, "toggle_admin", user_id, {"is_admin": new_val})
        return {"user_id": user_id, "is_admin": new_val}

    @router.post("/users/{user_id}/suspend")
    async def toggle_suspend(user_id: str, actor=Depends(require_admin)):
        target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not target:
            raise HTTPException(404, "Not found")
        if target.get("is_super_admin"):
            raise HTTPException(400, "Cannot suspend a super-admin")
        # A regular admin cannot suspend another admin — only super can.
        if target.get("is_admin") and not actor.is_super_admin:
            raise HTTPException(403, "Only super-admins can suspend admins")
        new_val = not bool(target.get("is_suspended"))
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_suspended": new_val}},
        )
        # Invalidate sessions on suspend so the user can't keep using
        # whatever cookie they had.
        if new_val:
            await db.user_sessions.delete_many({"user_id": user_id})
        await _audit(actor, "toggle_suspend", user_id, {"is_suspended": new_val})
        return {"user_id": user_id, "is_suspended": new_val}

    @router.patch("/users/{user_id}", response_model=AdminUser)
    async def patch_user(
        user_id: str,
        body: UserPatch,
        actor=Depends(require_admin),
    ):
        target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not target:
            raise HTTPException(404, "Not found")
        # Only fields explicitly in UserPatch are settable from the admin
        # UI; never let an admin write arbitrary keys.
        update_set: Dict[str, Any] = {}
        # `ai_quota_override` can explicitly be set to null to clear the
        # override; we need to distinguish "unset" from "set to null".
        if "ai_quota_override" in body.model_fields_set:
            update_set["ai_quota_override"] = body.ai_quota_override
        if not update_set:
            raise HTTPException(400, "Nothing to update")
        await db.users.update_one({"user_id": user_id}, {"$set": update_set})
        await _audit(actor, "patch_user", user_id, update_set)
        doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        return AdminUser(**doc)

    @router.get("/audit", response_model=List[AuditEntry])
    async def audit_log(
        action: Optional[str] = None,
        limit: int = Query(100, ge=1, le=500),
        skip: int = Query(0, ge=0),
        _=Depends(require_admin),
    ):
        match: Dict[str, Any] = {}
        if action:
            match["action"] = action
        cur = (
            db.admin_audit_log.find(match, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )
        return [AuditEntry(**doc) async for doc in cur]

    return router
