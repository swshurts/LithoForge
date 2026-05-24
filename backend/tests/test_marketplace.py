"""Smoke tests for marketplace + jobs persistence (Phase A)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from server import app  # noqa: E402

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
sync_db = MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed_user():
    """Seed a user + session token directly in MongoDB (sync driver) so
    fixtures don't fight motor's async event loop."""
    user_id = f"user_pytest_{int(datetime.now().timestamp() * 1000)}"
    token = f"token_pytest_{int(datetime.now().timestamp() * 1000)}"
    sync_db.users.insert_one({
        "user_id": user_id,
        "email": f"{user_id}@test.local",
        "name": "Pytest User",
        "picture": "",
        "created_at": datetime.now(timezone.utc),
    })
    sync_db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": user_id, "token": token,
           "headers": {"Authorization": f"Bearer {token}"}}
    sync_db.users.delete_one({"user_id": user_id})
    sync_db.user_sessions.delete_one({"session_token": token})
    sync_db.jobs.delete_many({"user_id": user_id})


def _seed_job(user_id: str, job_id: str = "test-job-1") -> None:
    sync_db.jobs.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "name": "Test Job",
        "created_at": datetime.now(timezone.utc),
        "render_mode": "painting",
        "request": {"width_mm": 100, "height_mm": 100},
        "filaments": [{"name": "White", "hex": "#ffffff", "td": 5.0}],
        "allocation": [10],
        "total_layers": 10,
        "delta_e_mean": 5.0,
        "delta_e_p95": 12.0,
        "swap_heights_mm": [],
        "swap_colors": [],
        "layer_height_mm": 0.12,
        "layer_map_b64": "",
        "preview_png_base64": "iVBORw0KGgo",
        "heightmap_png_base64": "iVBORw0KGgo",
        "thumbnail_base64": "iVBORw0KGgo",
        "timeline": [],
    })


def test_auth_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_auth_me_with_token(client, authed_user):
    r = client.get("/api/auth/me", headers=authed_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == authed_user["user_id"]


def test_publish_and_browse_marketplace(client, authed_user):
    _seed_job(authed_user["user_id"])
    # Publish
    r = client.put(
        "/api/my-jobs/test-job-1/listing",
        headers=authed_user["headers"],
        json={
            "title": "Test Lithophane",
            "description": "Pytest",
            "price_usd": 25.0,
        },
    )
    assert r.status_code == 200
    listing = r.json()
    assert listing["title"] == "Test Lithophane"
    assert listing["price_usd"] == 25.0
    assert listing["creator_name"] == "Pytest User"

    # Browse (public, no auth)
    r = client.get("/api/marketplace")
    assert r.status_code == 200
    titles = [lst["title"] for lst in r.json()]
    assert "Test Lithophane" in titles

    # Detail (public, no auth)
    r = client.get("/api/marketplace/test-job-1")
    assert r.status_code == 200
    detail = r.json()
    assert detail["platform_fee_pct"] == 6.0
    assert detail["preview_png_base64"] != ""

    # Creator profile (public, no auth)
    r = client.get(f"/api/creators/{authed_user['user_id']}")
    assert r.status_code == 200
    profile = r.json()
    assert profile["name"] == "Pytest User"
    assert len(profile["listings"]) == 1


def test_unpublish(client, authed_user):
    _seed_job(authed_user["user_id"], job_id="test-job-2")
    client.put(
        "/api/my-jobs/test-job-2/listing",
        headers=authed_user["headers"],
        json={"title": "Xyz", "description": "", "price_usd": 1.0},
    )
    r = client.delete(
        "/api/my-jobs/test-job-2/listing",
        headers=authed_user["headers"],
    )
    assert r.status_code == 200
    r = client.get("/api/marketplace/test-job-2")
    assert r.status_code == 404


def test_my_jobs_includes_listed_flag(client, authed_user):
    _seed_job(authed_user["user_id"], job_id="test-job-3")
    r = client.get("/api/my-jobs", headers=authed_user["headers"])
    assert r.status_code == 200
    jobs = r.json()
    target = next((j for j in jobs if j["job_id"] == "test-job-3"), None)
    assert target is not None
    assert target["listed"] is False  # not published yet

    pub = client.put(
        "/api/my-jobs/test-job-3/listing",
        headers=authed_user["headers"],
        json={"title": "Yes", "description": "", "price_usd": 9.99},
    )
    assert pub.status_code == 200, pub.text
    # Verify the doc actually has the listing field set
    raw = sync_db.jobs.find_one({"job_id": "test-job-3"}, {"_id": 0, "listing": 1})
    assert raw and raw.get("listing", {}).get("visibility") == "listed"

    r = client.get("/api/my-jobs", headers=authed_user["headers"])
    target = next(j for j in r.json() if j["job_id"] == "test-job-3")
    assert target["listed"] is True
