"""Shared pytest fixtures.

Provides an authenticated `client` (pro-tier test user) for HTTP tests
so the new sign-in + quota gating doesn't break the existing suite.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient


def _read_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    if url:
        return url
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    return ""


BASE_URL = _read_base_url()
API = f"{BASE_URL}/api"


def _seed_test_user_and_session() -> str:
    """Synchronously upsert a pro-tier test user + an active session
    and return its session token. Used by the authed_client fixture."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")

    async def _do():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        user_id = "test-user-pytest"
        token = "test-session-" + secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc)
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "email": "pytest@example.com",
                    "name": "Pytest User",
                    "tier": "pro",
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        await db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": token,
            "expires_at": now + timedelta(days=1),
            "created_at": now,
        })
        client.close()
        return token

    return asyncio.run(_do())


@pytest.fixture(scope="session")
def authed_token() -> str:
    return _seed_test_user_and_session()


@pytest.fixture(scope="session")
def authed_client(authed_token):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {authed_token}",
    })
    return s
