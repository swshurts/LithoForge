"""Forge Suite SSO bridge tests.

Exercises the symmetric JWT bridge end-to-end against the live FastAPI
backend running on the same Mongo as conftest's seeded test user.

We never call out to a real peer here; we just verify the LithoForge
side correctly:
  - mints valid JWTs for authed users
  - rejects unauthed mint requests
  - accepts peer-minted tokens AND sets a session cookie
  - rejects expired / mis-signed / wrong-issuer tokens
  - upserts the user by email (creates new, updates existing)
  - refuses bridge sign-in for suspended accounts
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

from tests.conftest import API


def _backend_secret() -> str:
    """The backend reads FORGE_SUITE_SECRET from its own process env
    (loaded from backend/.env at startup). Reuse the same value so our
    mint matches the backend's verify."""
    # backend/.env is in the same repo — load it directly.
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("FORGE_SUITE_SECRET="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("FORGE_SUITE_SECRET not found in backend/.env")


SECRET = _backend_secret()


def _db():
    return AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    )[os.environ.get("DB_NAME", "test_database")]


def _run(coro):
    return asyncio.run(coro)


def _mint_peer_token(
    email="bridge-user@example.com",
    iss="forgeslicer",
    ttl_seconds=60,
    name="Bridge User",
    picture="",
    secret=None,
):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": email,
            "name": name,
            "picture": picture,
            "iss": iss,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
            "jti": "test-jti",
        },
        secret or SECRET,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _cleanup():
    async def _do():
        db = _db()
        await db.users.delete_many({"email": {"$regex": "^bridge-"}})
        await db.user_sessions.delete_many({"source": "sso-bridge"})
    _run(_do())
    yield
    _run(_do())


# ---------------------------------------------------------------------------
# /api/auth/sso-bridge/mint
# ---------------------------------------------------------------------------

class TestMint:
    def test_anonymous_mint_returns_401(self):
        # Override env via header passthrough: the backend reads
        # FORGE_SUITE_SECRET from os.environ which is preserved across
        # the test process. monkeypatch in this fixture changes the
        # value the FastAPI handler sees because both run in-process.
        r = requests.get(f"{API}/auth/sso-bridge/mint")
        assert r.status_code == 401

    def test_authed_mint_returns_jwt(self, authed_client):
        r = authed_client.get(f"{API}/auth/sso-bridge/mint")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body
        assert isinstance(body["peers"], list)
        # Decode the token with the same secret — must succeed and
        # carry the expected claims.
        payload = jwt.decode(body["token"], SECRET, algorithms=["HS256"])
        assert payload["sub"] == "pytest@example.com"
        assert payload["iss"] == "lithoforge"
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]
        # Expiry must be short (≤120 s) per spec.
        assert payload["exp"] - payload["iat"] <= 120

    def test_mint_includes_peer_list(self, authed_client):
        r = authed_client.get(f"{API}/auth/sso-bridge/mint")
        peers = r.json()["peers"]
        assert "https://forgeslicer.com" in peers
        assert "https://www.forgeslicer.com" in peers


# ---------------------------------------------------------------------------
# /api/auth/sso-bridge (accept)
# ---------------------------------------------------------------------------

class TestAccept:
    def test_missing_header_returns_400(self):
        r = requests.post(f"{API}/auth/sso-bridge")
        assert r.status_code == 400
        assert "Missing" in r.text

    def test_bad_token_returns_401(self):
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": "not.a.jwt"},
        )
        assert r.status_code == 401

    def test_expired_token_returns_401(self):
        token = _mint_peer_token(ttl_seconds=-10)
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 401
        assert "expired" in r.text.lower()

    def test_wrong_secret_returns_401(self):
        token = _mint_peer_token(secret="totally-different-secret")
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 401

    def test_unknown_issuer_returns_403(self):
        token = _mint_peer_token(iss="evil-app.example.com")
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 403
        assert "allowlist" in r.text.lower()

    def test_invalid_email_returns_400(self):
        token = _mint_peer_token(email="not-an-email")
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 400

    def test_valid_token_creates_user_and_sets_cookie(self):
        token = _mint_peer_token(
            email="bridge-new-user@example.com",
            name="Bridge Newbie",
            picture="https://example.com/p.png",
        )
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["user"]["email"] == "bridge-new-user@example.com"
        assert body["user"]["name"] == "Bridge Newbie"
        # Cookie should be set with SameSite=None; Secure; HttpOnly.
        sc = r.headers.get("set-cookie", "").lower()
        assert "session_token=" in sc
        assert "samesite=none" in sc
        assert "secure" in sc
        assert "httponly" in sc

    def test_user_persisted_in_db(self):
        token = _mint_peer_token(email="bridge-persist@example.com")
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 200

        async def _check():
            db = _db()
            user = await db.users.find_one({"email": "bridge-persist@example.com"})
            assert user is not None
            assert user["user_id"].startswith("user_")
            session = await db.user_sessions.find_one(
                {"user_id": user["user_id"], "source": "sso-bridge"}
            )
            assert session is not None
            assert session["source_iss"] == "forgeslicer"
        _run(_check())

    def test_existing_user_updates_not_duplicates(self):
        """Second bridge POST for the same email must update, not insert."""

        async def _seed():
            db = _db()
            await db.users.insert_one({
                "user_id": "user_bridge_existing",
                "email": "bridge-existing@example.com",
                "name": "Old Name",
                "picture": "",
                "is_admin": False,
                "is_super_admin": False,
                "is_suspended": False,
                "created_at": datetime.now(timezone.utc),
            })
        _run(_seed())

        token = _mint_peer_token(
            email="bridge-existing@example.com",
            name="New Name",
        )
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 200

        async def _verify():
            db = _db()
            count = await db.users.count_documents(
                {"email": "bridge-existing@example.com"}
            )
            assert count == 1
            user = await db.users.find_one({"email": "bridge-existing@example.com"})
            assert user["name"] == "New Name"
            assert user["user_id"] == "user_bridge_existing"  # preserved
        _run(_verify())

    def test_suspended_user_refused(self):
        async def _seed():
            db = _db()
            await db.users.insert_one({
                "user_id": "user_bridge_suspended",
                "email": "bridge-suspended@example.com",
                "name": "Banned",
                "is_suspended": True,
                "is_admin": False,
                "is_super_admin": False,
                "created_at": datetime.now(timezone.utc),
            })
        _run(_seed())

        token = _mint_peer_token(email="bridge-suspended@example.com")
        r = requests.post(
            f"{API}/auth/sso-bridge",
            headers={"X-Forge-Suite-Token": token},
        )
        assert r.status_code == 403
        assert "suspended" in r.text.lower()
