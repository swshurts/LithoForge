"""Emergent-managed Google Auth integration.

This app is NOT auth-gated — login is opt-in to sync presets across devices.
Anonymous users can still use every feature; their presets live in localStorage.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

EMERGENT_SESSION_DATA_URL = (
    "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
)
SESSION_TTL_DAYS = 7
COOKIE_NAME = "session_token"


class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str = ""
    is_admin: bool = False
    is_super_admin: bool = False
    is_suspended: bool = False
    ai_quota_override: Optional[int] = None


def _super_admin_emails() -> set:
    """Parse the SUPER_ADMIN_EMAILS env var into a normalized set. Case-
    insensitive so a typo in capitalisation can't lock you out."""
    raw = os.environ.get("SUPER_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


class SessionExchangeIn(BaseModel):
    session_id: str


def _build_auth_router(db: AsyncIOMotorDatabase) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    async def _get_session_token(
        session_token_cookie: Optional[str],
        authorization: Optional[str],
    ) -> Optional[str]:
        if session_token_cookie:
            return session_token_cookie
        if authorization and authorization.lower().startswith("bearer "):
            return authorization.split(" ", 1)[1].strip() or None
        return None

    async def _resolve_user(token: str) -> Optional[User]:
        session_doc = await db.user_sessions.find_one(
            {"session_token": token}, {"_id": 0}
        )
        if not session_doc:
            return None
        expires_at = session_doc.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            await db.user_sessions.delete_one({"session_token": token})
            return None
        user_doc = await db.users.find_one(
            {"user_id": session_doc["user_id"]}, {"_id": 0}
        )
        if not user_doc:
            return None
        # If the user was suspended mid-session, drop the session token
        # so the next request gets a clean 401.
        if user_doc.get("is_suspended"):
            await db.user_sessions.delete_many({"user_id": user_doc["user_id"]})
            return None
        return User(**user_doc)

    # Exposed helper for route handlers that need the current user.
    async def get_current_user(
        session_token: Optional[str] = Cookie(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> Optional[User]:
        token = await _get_session_token(session_token, authorization)
        if not token:
            return None
        return await _resolve_user(token)

    async def require_user(
        session_token: Optional[str] = Cookie(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> User:
        user = await get_current_user(session_token, authorization)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    # Stash these on the router so server.py can wire them into other routes.
    router.dependency_get_current_user = get_current_user  # type: ignore[attr-defined]
    router.dependency_require_user = require_user  # type: ignore[attr-defined]

    @router.post("/session")
    async def exchange_session(body: SessionExchangeIn, response: Response):
        """Exchange a session_id (from the Emergent auth redirect) for a
        long-lived session_token, persist the user + session, and set a
        secure cookie."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                EMERGENT_SESSION_DATA_URL,
                headers={"X-Session-ID": body.session_id},
            )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        data = r.json()
        email = data["email"]
        name = data.get("name", "")
        picture = data.get("picture", "")
        session_token = data["session_token"]

        # Decide super-admin status from the env var allowlist on every
        # login. The flag is reset on each login so removing an email
        # from SUPER_ADMIN_EMAILS revokes admin powers at the next sign-in.
        is_super_admin = email.lower() in _super_admin_emails()

        # Upsert user by email (don't duplicate users if they re-login).
        existing = await db.users.find_one({"email": email}, {"_id": 0})
        if existing:
            # Refuse sign-in for suspended accounts and invalidate any
            # lingering sessions so a stale cookie can't bypass the ban.
            if existing.get("is_suspended"):
                await db.user_sessions.delete_many({"user_id": existing["user_id"]})
                raise HTTPException(
                    status_code=403,
                    detail="This account has been suspended.",
                )
            user_id = existing["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "name": name,
                        "picture": picture,
                        "is_super_admin": is_super_admin,
                        "last_login_at": datetime.now(timezone.utc),
                    }
                },
            )
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one(
                {
                    "user_id": user_id,
                    "email": email,
                    "name": name,
                    "picture": picture,
                    "is_admin": False,
                    "is_super_admin": is_super_admin,
                    "is_suspended": False,
                    "ai_quota_override": None,
                    "created_at": datetime.now(timezone.utc),
                    "last_login_at": datetime.now(timezone.utc),
                }
            )

        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
        await db.user_sessions.insert_one(
            {
                "user_id": user_id,
                "session_token": session_token,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc),
            }
        )

        response.set_cookie(
            key=COOKIE_NAME,
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            path="/",
            max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        )
        return {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
        }

    @router.get("/me", response_model=User)
    async def me(
        session_token: Optional[str] = Cookie(default=None),
        authorization: Optional[str] = Header(default=None),
    ):
        # Note on stale cookies: we INTENTIONALLY do not call
        # delete_cookie here when a token doesn't resolve to a live
        # session. Doing so creates a race during sign-in: between the
        # /auth/session POST setting the new cookie and the React UI
        # settling, a StrictMode-doubled /auth/me with the in-flight
        # cookie can hit a momentary mismatch, get 401'd, and the
        # delete_cookie would wipe the freshly-set valid session,
        # causing an infinite sign-in loop. Stale cookies are instead
        # overwritten on the next successful /auth/session because
        # `set_cookie` with the same (name, host, path) replaces the
        # previous value atomically.
        user = await get_current_user(session_token, authorization)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    @router.post("/logout")
    async def logout(
        response: Response,
        request: Request,
        session_token: Optional[str] = Cookie(default=None),
        authorization: Optional[str] = Header(default=None),
    ):
        _ = request  # unused but kept for future audit hooks
        token = await _get_session_token(session_token, authorization)
        if token:
            await db.user_sessions.delete_one({"session_token": token})
        response.delete_cookie(
            COOKIE_NAME, path="/", samesite="none", secure=True
        )
        return {"ok": True}

    return router


def build_auth(db: AsyncIOMotorDatabase):
    """Return (router, get_current_user_dep, require_user_dep)."""
    router = _build_auth_router(db)
    return (
        router,
        router.dependency_get_current_user,  # type: ignore[attr-defined]
        router.dependency_require_user,  # type: ignore[attr-defined]
    )
