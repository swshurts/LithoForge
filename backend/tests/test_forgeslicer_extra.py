"""Extra scenarios that weren't in the bridge tests:
- error pass-through (upstream 4xx/5xx)
- unreachable upstream → 502
- diffuser=False sending lightbox_diffuser → 400
"""
from __future__ import annotations

import base64
import io
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break
API = f"{BASE_URL}/api"


class _ErrorHandler(BaseHTTPRequestHandler):
    def log_message(self, *a, **k):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(413)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"detail":"file too big"}')


@pytest.fixture(scope="module")
def error_inbox():
    httpd = HTTPServer(("127.0.0.1", 0), _ErrorHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}/api/litho/inbox"
    httpd.shutdown()


def _solid_image_b64(rgb=(120, 200, 50), size=48) -> str:
    img = Image.new("RGB", (size, size), color=rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_optimized_job(authed_client, geometry="flat", extra_body=None) -> str:
    r = authed_client.post(f"{API}/upload", json={"image_base64": _solid_image_b64()})
    assert r.status_code == 200
    image_id = r.json()["image_id"]
    body = {
        "image_id": image_id,
        "geometry": geometry,
        "max_swaps": 2,
        "width_mm": 100, "height_mm": 100, "thickness_mm": 2.2, "border_mm": 2,
        "layer_height_mm": 0.12, "nozzle_mm": 0.4,
    }
    if extra_body:
        body.update(extra_body)
    r = authed_client.post(f"{API}/optimize", json=body)
    assert r.status_code == 200
    return r.json()["job_id"]


def test_forgeslicer_error_pass_through(authed_client, error_inbox):
    # Point to the 413 mock
    r = authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": error_inbox}, timeout=10)
    assert r.status_code == 200
    try:
        job_id = _make_optimized_job(authed_client, geometry="flat")
        r = authed_client.post(
            f"{API}/forgeslicer/send/{job_id}",
            json={"part": "lithophane", "format": "3mf"},
            timeout=20,
        )
        # Upstream 413 should surface
        assert r.status_code == 413, r.text
        detail = r.json().get("detail", {})
        assert isinstance(detail, dict)
        assert detail.get("status") == 413
        assert "forgeslicer_response" in detail
        assert detail["forgeslicer_response"].get("detail") == "file too big"
    finally:
        authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": None}, timeout=10)


def test_forgeslicer_unreachable_returns_502(authed_client):
    # Point at an unused port — connection will be refused
    bad = "http://127.0.0.1:1/api/litho/inbox"
    r = authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": bad}, timeout=10)
    assert r.status_code == 200
    try:
        job_id = _make_optimized_job(authed_client, geometry="flat")
        r = authed_client.post(
            f"{API}/forgeslicer/send/{job_id}",
            json={"part": "lithophane", "format": "3mf"},
            timeout=30,
        )
        assert r.status_code == 502, f"got {r.status_code}: {r.text[:300]}"
        # Detail may be JSON or plain depending on ingress; only require 502.
        try:
            body = r.json()
            assert "unreachable" in str(body.get("detail", "")).lower() or "unreachable" in r.text.lower()
        except ValueError:
            # Non-JSON 502 from edge layer is acceptable as long as status is 502.
            pass
    finally:
        authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": None}, timeout=10)


def test_diffuser_disabled_returns_400(authed_client):
    """Box job with box_diffuser=False, asking for lightbox_diffuser → 400 mentioning diffuser."""
    job_id = _make_optimized_job(
        authed_client, geometry="box",
        extra_body={
            "box_shape": "rect",
            "box_outer_w_mm": 130, "box_outer_h_mm": 130,
            "box_depth_mm": 40, "box_wall_mm": 3,
            "box_led_mount": "puck", "box_puck_diameter_mm": 65,
            "box_diffuser": False,
        },
    )
    r = authed_client.post(
        f"{API}/forgeslicer/send/{job_id}",
        json={"part": "lightbox_diffuser", "format": "stl"},
        timeout=20,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "diffuser" in str(detail).lower()
