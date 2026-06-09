"""Forge Suite SSO bridge — LithoForge side.

Symmetric JWT bridge between LithoForge and ForgeSlicer (and any future
sibling app in the Forge Suite). Two endpoints:

  GET  /api/auth/sso-bridge/mint   — current user gets a short-lived JWT
       to hand to a peer app.
  POST /api/auth/sso-bridge        — accept a JWT from a peer, upsert
       the user, set our session_token cookie.

The shared secret + peer list live in `FORGE_SUITE_*` env vars. See
`memory/FORGE_SUITE_SSO_BRIDGE.md` for the cross-app contract.
"""

from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Set

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

logger = logging.getLogger("lithoforge.sso_bridge")

SESSION_TTL_DAYS = 7
JWT_TTL_SECONDS = 60
JWT_ALGO = "HS256"
COOKIE_NAME = "session_token"  # must match auth.py


class MintTokenResponse(BaseModel):
    token: str
    peers: List[str]


def _peers_from_env() -> List[str]:
    raw = (os.environ.get("FORGE_SUITE_PEERS") or "").strip()
    if not raw:
        return []
    return [p.strip().rstrip("/") for p in raw.split(",") if p.strip()]


def _allowed_iss_set() -> Set[str]:
    """Build the allowlist of acceptable `iss` claims. Accept several
    common forms (full URL, host, host stem) so a tiny mismatch like
    `forgeslicer` vs `https://forgeslicer.com` doesn't break the bridge.
    """
    out: Set[str] = set()
    for peer in _peers_from_env():
        out.add(peer)
        try:
            host = peer.split("//", 1)[1].split("/", 1)[0]
            out.add(host)
            stem = host.replace("www.", "").split(".")[0]
            out.add(stem)
        except Exception:
            # Malformed peer entry — log and skip; bridge keeps working.
            logger.warning("Skipping malformed FORGE_SUITE_PEERS entry: %s", peer)
    return out


def _get_secret() -> str:
    secret = os.environ.get("FORGE_SUITE_SECRET")
    if not secret:
        raise HTTPException(
            500,
            detail="FORGE_SUITE_SECRET is not configured — SSO bridge disabled.",
        )
    return secret


def _public_user(doc: Dict) -> Dict:
    """Strip Mongo-internal fields and project the user doc into the
    shape /auth/me returns. Kept in lockstep with `auth.User`."""
    return {
        "user_id": doc.get("user_id", ""),
        "email": doc.get("email", ""),
        "name": doc.get("name", ""),
        "picture": doc.get("picture", ""),
        "is_admin": bool(doc.get("is_admin", False)),
        "is_super_admin": bool(doc.get("is_super_admin", False)),
        "is_suspended": bool(doc.get("is_suspended", False)),
        "ai_quota_override": doc.get("ai_quota_override"),
    }


def _set_session_cookie(response: Response, session_token: str) -> None:
    """SameSite=None; Secure is REQUIRED for cross-origin bridge to set
    a cookie on lithoforge.com from a forgeslicer.com fetch. See spec
    Step 4."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
    )


def build_sso_bridge_router(
    db: AsyncIOMotorDatabase,
    get_current_user_dep: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["sso-bridge"])

    @router.get("/sso-bridge/mint", response_model=MintTokenResponse)
    async def mint_token(user=Depends(get_current_user_dep)):
        """Mint a short-lived JWT for the signed-in user that any peer
        app in the Forge Suite can exchange for its own session cookie.
        """
        if not user:
            raise HTTPException(401, detail="Sign in first.")
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.email,
            "name": user.name or "",
            "picture": user.picture or "",
            "iss": (os.environ.get("FORGE_SUITE_APP_NAME") or "lithoforge").strip(),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=JWT_TTL_SECONDS)).timestamp()),
            "jti": secrets.token_hex(8),
        }
        token = jwt.encode(payload, _get_secret(), algorithm=JWT_ALGO)
        return MintTokenResponse(token=token, peers=_peers_from_env())

    @router.post("/sso-bridge")
    async def accept_bridge(request: Request, response: Response):
        """Verify a peer-minted JWT, upsert the user by email, set a
        LithoForge session cookie, return the user payload."""
        token = request.headers.get("X-Forge-Suite-Token")
        if not token:
            raise HTTPException(400, detail="Missing X-Forge-Suite-Token header.")
        try:
            payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, detail="SSO token expired.")
        except jwt.InvalidTokenError:
            raise HTTPException(401, detail="SSO token invalid.")

        iss = payload.get("iss") or ""
        if iss not in _allowed_iss_set():
            logger.warning(
                "Rejected SSO bridge: iss=%s not in allowlist=%s",
                iss, sorted(_allowed_iss_set()),
            )
            raise HTTPException(403, detail="Issuer not in Forge Suite allowlist.")

        email = (payload.get("sub") or "").lower().strip()
        if not email or "@" not in email:
            raise HTTPException(400, detail="Token sub is not a valid email.")

        now = datetime.now(timezone.utc)
        existing = await db.users.find_one({"email": email}, {"_id": 0})

        # Refuse bridge for suspended accounts — local admin moderation
        # always wins over a peer app's "this user is fine".
        if existing and existing.get("is_suspended"):
            await db.user_sessions.delete_many({"user_id": existing["user_id"]})
            raise HTTPException(
                403, detail="This account has been suspended on LithoForge."
            )

        if existing:
            await db.users.update_one(
                {"email": email},
                {
                    "$set": {
                        "name": payload.get("name") or existing.get("name") or "User",
                        "picture": payload.get("picture") or existing.get("picture") or "",
                        "last_login_at": now,
                    }
                },
            )
            user_doc = existing
            user_doc["name"] = payload.get("name") or existing.get("name") or "User"
            user_doc["picture"] = payload.get("picture") or existing.get("picture") or ""
        else:
            # Decide super-admin status from the env var allowlist —
            # bridged users get the same admin treatment as native sign-ins.
            from auth import _super_admin_emails
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            user_doc = {
                "user_id": user_id,
                "email": email,
                "name": payload.get("name") or email.split("@")[0],
                "picture": payload.get("picture") or "",
                "is_admin": False,
                "is_super_admin": email in _super_admin_emails(),
                "is_suspended": False,
                "ai_quota_override": None,
                "tier": "free",
                "created_at": now,
                "last_login_at": now,
            }
            await db.users.insert_one(dict(user_doc))
            user_doc.pop("_id", None)

        session_token = f"st_{uuid.uuid4().hex}"
        await db.user_sessions.insert_one(
            {
                "user_id": user_doc["user_id"],
                "session_token": session_token,
                "expires_at": now + timedelta(days=SESSION_TTL_DAYS),
                "created_at": now,
                "source": "sso-bridge",
                "source_iss": iss,
            }
        )
        _set_session_cookie(response, session_token)
        return {"ok": True, "user": _public_user(user_doc)}

    return router
