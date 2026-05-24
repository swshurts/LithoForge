"""Additional tests for printer profile features explicitly called out
by the current review request:
  - Default (no printer_id) → 3MF must embed M600 and NOT T<n>
  - Painting mode `smoothing` slider produces a different layer_map
  - Marketplace listing `license` field flows through POST + GET
"""

from __future__ import annotations

import base64
import io
import os
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests
from PIL import Image
from pymongo import MongoClient

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


def _photo_b64(size=(96, 64)) -> str:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (
                int(255 * x / w),
                int(255 * y / h),
                int(255 * ((x + y) / (w + h))),
            )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def image_id(session):
    r = session.post(f"{API}/upload", json={"image_base64": _photo_b64()})
    assert r.status_code == 200
    return r.json()["image_id"]


# -- Default printer → M600 path --------------------------------------------

def test_default_printer_produces_m600(session, image_id):
    body = {
        "image_id": image_id,
        "width_mm": 100.0,
        "height_mm": 80.0,
        "thickness_mm": 3.0,
        "border_mm": 2.0,
        "layer_height_mm": 0.12,
        "max_swaps": 4,
    }
    r = session.post(f"{API}/optimize", json=body)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    threemf = session.get(f"{API}/export/{job_id}/3mf")
    assert threemf.status_code == 200
    with zipfile.ZipFile(io.BytesIO(threemf.content)) as z:
        cfg = z.read("Metadata/project_settings.config").decode("utf-8")
    assert "M600" in cfg
    # Must NOT contain tool-change references when single-extruder
    # (allow comments/words but not T1/T2/T3 layer-change markers)
    for tag in ("}T1{", "}T2{", "}T3{"):
        assert tag not in cfg


# -- Painting smoothing alters output ---------------------------------------

def test_painting_smoothing_changes_delta_e(session, image_id):
    base_body = {
        "image_id": image_id,
        "width_mm": 80.0,
        "height_mm": 60.0,
        "thickness_mm": 2.4,
        "border_mm": 2.0,
        "layer_height_mm": 0.2,
        "max_swaps": 4,
        "render_mode": "painting",
    }
    no_smooth = session.post(f"{API}/optimize", json={**base_body, "smoothing": 0.0})
    assert no_smooth.status_code == 200, no_smooth.text
    smoothed = session.post(f"{API}/optimize", json={**base_body, "smoothing": 0.8})
    assert smoothed.status_code == 200, smoothed.text
    a = no_smooth.json()
    b = smoothed.json()
    # ΔE stats should differ because the input was blurred for the second
    # run. Allow a tiny tolerance for floating-point determinism.
    assert (
        abs(a["delta_e_mean"] - b["delta_e_mean"]) > 1e-3
        or abs(a["delta_e_p95"] - b["delta_e_p95"]) > 1e-3
    )


# -- Marketplace listing.license round-trip ---------------------------------

@pytest.fixture
def authed_user():
    uid = f"user_lic_{int(datetime.now().timestamp() * 1000)}"
    tok = f"tok_lic_{int(datetime.now().timestamp() * 1000)}"
    sync_db.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@test.local",
        "name": "License Tester",
        "picture": "",
        "created_at": datetime.now(timezone.utc),
    })
    sync_db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": uid, "headers": {"Authorization": f"Bearer {tok}"}}
    sync_db.users.delete_one({"user_id": uid})
    sync_db.user_sessions.delete_one({"session_token": tok})
    sync_db.jobs.delete_many({"user_id": uid})


def _seed_job(user_id: str, job_id: str) -> None:
    sync_db.jobs.insert_one({
        "job_id": job_id,
        "user_id": user_id,
        "name": "License Test Job",
        "created_at": datetime.now(timezone.utc),
        "render_mode": "painting",
        "request": {"width_mm": 80, "height_mm": 60},
        "filaments": [{"name": "White", "hex": "#ffffff", "td": 5.0}],
        "allocation": [10],
        "total_layers": 10,
        "delta_e_mean": 4.0,
        "delta_e_p95": 9.0,
        "swap_heights_mm": [],
        "swap_colors": [],
        "layer_height_mm": 0.12,
        "layer_map_b64": "",
        "preview_png_base64": "iVBORw0KGgo",
        "heightmap_png_base64": "iVBORw0KGgo",
        "thumbnail_base64": "iVBORw0KGgo",
        "timeline": [],
    })


def test_listing_license_round_trip(session, authed_user):
    job_id = f"lic-job-{int(datetime.now().timestamp() * 1000)}"
    _seed_job(authed_user["user_id"], job_id)

    r = requests.put(
        f"{API}/my-jobs/{job_id}/listing",
        headers={**authed_user["headers"], "Content-Type": "application/json"},
        json={
            "title": "Licensed Print",
            "description": "Test",
            "price_usd": 12.5,
            "license": "CC-BY-NC",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("license") == "CC-BY-NC"

    # Public marketplace list returns it
    lst = requests.get(f"{API}/marketplace")
    assert lst.status_code == 200
    match = next((x for x in lst.json() if x.get("job_id") == job_id), None)
    assert match is not None, "listing not present in marketplace"
    assert match.get("license") == "CC-BY-NC"

    detail = requests.get(f"{API}/marketplace/{job_id}")
    assert detail.status_code == 200
    assert detail.json().get("license") == "CC-BY-NC"
