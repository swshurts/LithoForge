"""HTTP-level checks that /api/optimize returns the cost_estimate field
with sensible values for both flat and disc geometries."""

import base64
import io
import os

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


def _make_image_b64(w=96, h=96):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 3) % 256, (y * 3) % 256, ((x + y) * 3) % 256)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="module")
def uploaded_id():
    img_b64 = _make_image_b64()
    r = requests.post(
        f"{API}/upload",
        json={"image_base64": img_b64, "filename": "TEST_cost.png"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["image_id"]


def _optimize(image_id, geometry="flat"):
    body = {
        "image_id": image_id,
        "width_mm": 100.0,
        "height_mm": 100.0,
        "thickness_mm": 2.4,
        "border_mm": 2.0,
        "layer_height_mm": 0.12,
        "max_swaps": 5,
        "geometry": geometry,
        "curve_radius_mm": 80.0,
    }
    r = requests.post(f"{API}/optimize", json=body, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_optimize_returns_cost_estimate_flat(uploaded_id):
    data = _optimize(uploaded_id, "flat")
    assert "cost_estimate" in data, list(data.keys())
    ce = data["cost_estimate"]
    for key in (
        "total_time_minutes",
        "total_weight_g",
        "total_length_mm",
        "total_cost_usd",
        "total_volume_mm3",
        "per_filament",
    ):
        assert key in ce, f"missing key {key}"

    assert ce["total_time_minutes"] > 0
    # Sanity ranges for a 100x100x2.4mm lithophane.
    assert 5.0 <= ce["total_weight_g"] <= 80.0, ce["total_weight_g"]
    assert 0.05 <= ce["total_cost_usd"] <= 10.0, ce["total_cost_usd"]
    assert isinstance(ce["per_filament"], list) and len(ce["per_filament"]) >= 1
    for f in ce["per_filament"]:
        for k in ("slot", "name", "hex", "layers", "volume_mm3", "weight_g", "length_mm", "cost_usd"):
            assert k in f, f"per_filament missing {k}"


def test_optimize_disc_is_roughly_pi_over_4_of_flat(uploaded_id):
    flat = _optimize(uploaded_id, "flat")["cost_estimate"]
    disc = _optimize(uploaded_id, "disc")["cost_estimate"]
    ratio = disc["total_volume_mm3"] / max(flat["total_volume_mm3"], 1e-6)
    # ~π/4 ≈ 0.785; allow slack for the discrete mask and image content.
    assert 0.6 < ratio < 0.95, f"unexpected disc/flat ratio {ratio:.3f}"
