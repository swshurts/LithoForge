"""Tests for marketplace guest checkout (Phase B).

Validates:
- POST /api/marketplace/{job_id}/checkout: 404 for unknown job_id
- POST /api/marketplace/{job_id}/checkout: 404 for an unlisted job_id
- GET /api/marketplace and /api/marketplace/{job_id} are public (no auth)
- /api/upload and /api/optimize work without auth cookie (guest mode)
"""

from __future__ import annotations

import base64
import io
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
sync_db = MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def client(authed_client):
    return authed_client


def _make_photo_b64(size=(64, 48)) -> str:
    img = Image.new("RGB", size, (120, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------
# Guest browsing - marketplace endpoints must be public
# ------------------------------------------------------------------
class TestMarketplacePublicAccess:
    def test_marketplace_list_no_auth(self, client):
        r = client.get(f"{API}/marketplace")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_marketplace_detail_unknown(self, client):
        r = client.get(f"{API}/marketplace/this-job-does-not-exist")
        assert r.status_code == 404


# ------------------------------------------------------------------
# Guest upload + optimize (no auth header / cookie)
# ------------------------------------------------------------------
class TestGuestUploadOptimize:
    def test_guest_upload_and_optimize(self, client):
        # Upload (no auth)
        r = client.post(
            f"{API}/upload",
            json={"image_base64": _make_photo_b64(), "filename": "TEST_guest.png"},
        )
        assert r.status_code == 200, r.text
        image_id = r.json()["image_id"]

        # Optimize (no auth) — use modest size for speed
        body = {
            "image_id": image_id,
            "width_mm": 60.0,
            "height_mm": 60.0,
            "thickness_mm": 1.2,
            "border_mm": 1.5,
            "layer_height_mm": 0.2,
            "max_swaps": 2,
            "geometry": "flat",
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "job_id" in d
        assert d["preview_png_base64"]


# ------------------------------------------------------------------
# Checkout 404 paths
# ------------------------------------------------------------------
class TestCheckoutErrorPaths:
    def test_checkout_unknown_job_id(self, client):
        r = client.post(
            f"{API}/marketplace/this-job-does-not-exist/checkout",
            json={
                "job_id": "this-job-does-not-exist",
                "buyer_email": "buyer@example.com",
                "origin_url": "https://example.com",
            },
        )
        # Either 404 (job not found) or 400 — but per spec it should be 404.
        assert r.status_code == 404, (
            f"Expected 404 for unknown job, got {r.status_code}: {r.text}"
        )

    def test_checkout_unlisted_job(self, client):
        """Seed a job that is NOT published, expect 404 from checkout."""
        job_id = f"TEST_unlisted_{int(datetime.now().timestamp() * 1000)}"
        user_id = f"TEST_user_{int(datetime.now().timestamp() * 1000)}"
        sync_db.users.insert_one({
            "user_id": user_id,
            "email": f"{user_id}@test.local",
            "name": "Tester",
            "picture": "",
            "created_at": datetime.now(timezone.utc),
        })
        sync_db.jobs.insert_one({
            "job_id": job_id,
            "user_id": user_id,
            "name": "Unlisted job",
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
            # No "listing" field — not listed
        })
        try:
            r = client.post(
                f"{API}/marketplace/{job_id}/checkout",
                json={
                    "job_id": job_id,
                    "buyer_email": "buyer@example.com",
                    "origin_url": "https://example.com",
                },
            )
            assert r.status_code == 404, (
                f"Expected 404 for unlisted job, got {r.status_code}: {r.text}"
            )
        finally:
            sync_db.jobs.delete_one({"job_id": job_id})
            sync_db.users.delete_one({"user_id": user_id})


# ------------------------------------------------------------------
# Disc geometry sanity (also covered in test_lithophane_api.py)
# ------------------------------------------------------------------
class TestDiscOptimize:
    def test_disc_100x100_dome_1_5(self, client):
        up = client.post(
            f"{API}/upload",
            json={"image_base64": _make_photo_b64(), "filename": "TEST_disc.png"},
        )
        assert up.status_code == 200
        image_id = up.json()["image_id"]

        body = {
            "image_id": image_id,
            "width_mm": 100.0,
            "height_mm": 100.0,
            "thickness_mm": 2.4,
            "border_mm": 2.0,
            "layer_height_mm": 0.2,
            "max_swaps": 3,
            "geometry": "disc",
            "dome_mm": 1.5,
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["preview_png_base64"]
        job_id = d["job_id"]
        # Exports should all succeed
        for kind in ("stl", "swaps", "3mf"):
            x = client.get(f"{API}/export/{job_id}/{kind}")
            assert x.status_code == 200, f"{kind} export failed"
            assert len(x.content) > 0
