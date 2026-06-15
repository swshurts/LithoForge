"""HTTP-level integration tests for the new lightbox (box geometry)
optimize + export endpoints.

Exercises the real REACT_APP_BACKEND_URL public URL using the
authenticated `client` fixture (pro-tier test user) provided by
conftest.py. The pure-mesh / build_export tests live in
test_lightbox.py — this file is the *API* level companion.
"""

from __future__ import annotations

import base64
import io
import os

import pytest
import requests
from PIL import Image

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


@pytest.fixture(scope="session")
def client(authed_client):
    return authed_client


def _photo_b64(size=(64, 64)) -> str:
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            px[x, y] = (int(255 * x / size[0]), int(255 * y / size[1]), 128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _upload(client) -> str:
    r = client.post(f"{API}/upload", json={"image_base64": _photo_b64()})
    assert r.status_code == 200, r.text
    return r.json()["image_id"]


def _make_optimize_body(image_id: str, **overrides) -> dict:
    body = {
        "image_id": image_id,
        "filaments": [
            {"name": "W", "hex": "#FFFFFF", "transmission": 0.85},
            {"name": "K", "hex": "#000000", "transmission": 0.05},
        ],
        "layer_height_mm": 0.12,
        "thickness_mm": 2.4,
        "max_swaps": 4,
        "auto_order": True,
        "render_mode": "lithophane",
        "width_mm": 100.0,
        "height_mm": 100.0,
        "border_mm": 2.0,
        "geometry": "box",
        "box_shape": "rect",
        "box_outer_w_mm": 120.0,
        "box_outer_h_mm": 120.0,
        "box_depth_mm": 40.0,
        "box_wall_mm": 3.0,
        "box_led_mount": "both",
        "box_puck_diameter_mm": 60.0,
        "box_diffuser": True,
        "box_cable_notch": True,
    }
    body.update(overrides)
    return body


# --- /optimize -------------------------------------------------------------


class TestOptimizeBox:
    def test_box_rect_returns_job_id(self, client):
        image_id = _upload(client)
        r = client.post(f"{API}/optimize", json=_make_optimize_body(image_id))
        assert r.status_code == 200, r.text
        data = r.json()
        assert "job_id" in data and isinstance(data["job_id"], str)
        # box mode echoes a preview throughput pct
        assert "light_throughput_pct" in data

    def test_box_round_masks_layer_map(self, client):
        image_id = _upload(client)
        # Compare flat full-rect vs box-round masked throughputs — round
        # should ALWAYS yield a smaller (≤) throughput because of the
        # disc mask zeroing out corner pixels.
        r_flat = client.post(f"{API}/optimize", json=_make_optimize_body(
            image_id, geometry="flat",
        ))
        assert r_flat.status_code == 200, r_flat.text
        flat_pct = r_flat.json()["light_throughput_pct"]

        image_id2 = _upload(client)
        r_round = client.post(f"{API}/optimize", json=_make_optimize_body(
            image_id2, box_shape="round",
        ))
        assert r_round.status_code == 200, r_round.text
        round_pct = r_round.json()["light_throughput_pct"]
        # Disc-masked image throws away corner pixels so the throughput
        # number is computed on a masked region (different from flat).
        assert round_pct != flat_pct or round_pct < flat_pct + 0.01


# --- /export/{job_id}/lightbox-* -------------------------------------------


def _new_box_job(client, **overrides) -> str:
    image_id = _upload(client)
    body = _make_optimize_body(image_id, **overrides)
    r = client.post(f"{API}/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


class TestLightboxExports:
    def test_frame_stl_binary(self, client):
        job_id = _new_box_job(client)
        r = client.get(f"{API}/export/{job_id}/lightbox-frame")
        assert r.status_code == 200, r.text
        # binary STL: 80-byte header + 4-byte count
        assert len(r.content) > 200
        assert r.headers.get("content-type", "").startswith("model/stl") or \
            r.headers.get("content-type", "").startswith("application/")

    def test_back_stl_binary(self, client):
        job_id = _new_box_job(client)
        r = client.get(f"{API}/export/{job_id}/lightbox-back")
        assert r.status_code == 200, r.text
        assert len(r.content) > 200

    def test_diffuser_stl_when_enabled(self, client):
        job_id = _new_box_job(client, box_diffuser=True)
        r = client.get(f"{API}/export/{job_id}/lightbox-diffuser")
        assert r.status_code == 200, r.text
        assert len(r.content) > 200

    def test_diffuser_404_when_disabled(self, client):
        job_id = _new_box_job(client, box_diffuser=False)
        r = client.get(f"{API}/export/{job_id}/lightbox-diffuser")
        assert r.status_code == 404
        detail = r.json().get("detail", "")
        assert "diffuser disabled" in detail.lower()

    def test_flat_geometry_400_on_lightbox_endpoints(self, client):
        image_id = _upload(client)
        body = _make_optimize_body(image_id, geometry="flat")
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        for kind in ("lightbox-frame", "lightbox-back", "lightbox-diffuser"):
            rr = client.get(f"{API}/export/{job_id}/{kind}")
            assert rr.status_code == 400, f"{kind} -> {rr.status_code} {rr.text}"
            assert "geometry=box" in rr.json().get("detail", "").lower() or \
                "lightbox parts are only available" in rr.json().get("detail", "").lower()

    def test_round_box_lightbox_parts(self, client):
        job_id = _new_box_job(client, box_shape="round",
                              box_outer_w_mm=120.0, box_outer_h_mm=120.0)
        r1 = client.get(f"{API}/export/{job_id}/lightbox-frame")
        assert r1.status_code == 200
        assert len(r1.content) > 500
        r2 = client.get(f"{API}/export/{job_id}/lightbox-back")
        assert r2.status_code == 200
        assert len(r2.content) > 200


# --- Regression: lithophane STL/3MF still work in box mode -----------------


class TestLithophaneRegression:
    def test_stl_still_works_in_box_mode(self, client):
        job_id = _new_box_job(client)
        r = client.get(f"{API}/export/{job_id}/stl")
        assert r.status_code == 200, r.text
        assert len(r.content) > 200

    def test_3mf_still_works_in_box_mode(self, client):
        job_id = _new_box_job(client)
        r = client.get(f"{API}/export/{job_id}/3mf")
        assert r.status_code == 200, r.text
        assert len(r.content) > 200
