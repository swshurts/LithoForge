"""Tests for the per-user download quota + tier gating."""

from __future__ import annotations

import asyncio
import base64
import io
import os

import pytest
import requests
from PIL import Image
from motor.motor_asyncio import AsyncIOMotorClient

from tests.conftest import API


def _photo_b64() -> str:
    img = Image.new("RGB", (48, 36), (100, 60, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def _make_free_user(user_id: str, session_token: str) -> None:
    """Seed a fresh free-tier test user."""
    from datetime import datetime, timezone, timedelta

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    now = datetime.now(timezone.utc)
    # Wipe any prior state
    await db.users.delete_one({"user_id": user_id})
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.jobs.delete_many({"user_id": user_id})
    await db.users.insert_one({
        "user_id": user_id,
        "email": f"{user_id}@quota.test",
        "name": "Quota Test",
        "tier": "free",
        "created_at": now,
        "updated_at": now,
    })
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": now + timedelta(days=1),
        "created_at": now,
    })
    client.close()


@pytest.fixture(scope="module")
def free_client():
    user_id = "test-quota-free"
    token = "test-session-quota-free-token-12345"
    asyncio.run(_make_free_user(user_id, token))
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    return s


def _generate(client) -> str:
    """Upload + optimize + return job_id."""
    up = client.post(f"{API}/upload", json={"image_base64": _photo_b64()})
    assert up.status_code == 200, up.text
    image_id = up.json()["image_id"]
    body = {
        "image_id": image_id,
        "width_mm": 80.0, "height_mm": 60.0, "thickness_mm": 2.4,
        "border_mm": 2.0, "layer_height_mm": 0.2,
        "max_swaps": 2, "geometry": "flat",
    }
    r = client.post(f"{API}/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


class TestQuotaFreeTier:
    """During beta the free tier has unlimited downloads. When Stripe
    goes live and we flip the limit back to 5, restore the original
    "first 5 succeed / 6th blocks" tests from git history."""

    def test_quota_endpoint_for_signed_in_free_user(self, free_client):
        r = free_client.get(f"{API}/me/quota")
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "free"
        # Beta: limit is None (unlimited) for free tier.
        assert data["limit"] is None
        assert data["blocked"] is False

    def test_many_downloads_all_succeed_during_beta(self, free_client):
        """Free tier must permit far more than 5 downloads in beta."""
        for _ in range(8):
            job_id = _generate(free_client)
            r = free_client.get(f"{API}/export/{job_id}/stl")
            assert r.status_code == 200, r.text
        st = free_client.get(f"{API}/me/quota").json()
        assert st["used"] >= 8
        # Unlimited remaining means `remaining` is None (not 0).
        assert st["remaining"] is None
        assert st["blocked"] is False

    def test_re_download_of_counted_job_still_allowed(self, free_client):
        """Re-downloading a previously fetched job continues to be a no-op
        on the counter (the idempotency shortcut still applies)."""
        jobs = free_client.get(f"{API}/my-jobs").json()
        assert len(jobs) >= 1, "expected ≥1 job from earlier tests"
        first_job_id = jobs[-1]["job_id"]
        r = free_client.get(f"{API}/export/{first_job_id}/stl")
        assert r.status_code == 200, r.text


class TestQuotaGuestAndPro:
    def test_unauth_download_is_401(self):
        """Hitting export with no auth at all returns 401 (sign-in required)."""
        # First upload + optimize as the authed pro user, then try
        # downloading without auth.
        from tests.conftest import _seed_test_user_and_session
        token = _seed_test_user_and_session()
        s = requests.Session()
        s.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        })
        job_id = _generate(s)
        # Now drop auth and try to download
        anon = requests.Session()
        anon.headers.update({"Content-Type": "application/json"})
        r = anon.get(f"{API}/export/{job_id}/stl")
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["error"] == "auth_required"

    def test_pro_tier_unlimited(self, authed_client):
        """Pro tier has limit=None and is never blocked."""
        r = authed_client.get(f"{API}/me/quota")
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "pro"
        assert data["limit"] is None
        assert data["blocked"] is False
