"""Tests for the ForgeSlicer outbound bridge.

Strategy: instead of patching `httpx` in a separate process (the API
server runs under supervisor, so monkey-patching from the pytest
process doesn't reach it), we stand up a TINY in-process HTTP mock on
localhost and point `FORGESLICER_INBOX_URL` at it via the backend's
`/api/admin/dev/forgeslicer-inbox-url` test hook.

The hook is admin-only and only active when DEV_MODE=1 — production
deploys cannot reach it. Tests run with DEV_MODE=1 by default.
"""

from __future__ import annotations

import base64
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

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


# ---------------------------------------------------------------------------
# Pure unit tests on the shape-resolver
# ---------------------------------------------------------------------------


def test_resolve_source_shape_lithophane_modes():
    from forgeslicer_bridge import _resolve_source_shape
    assert _resolve_source_shape("lithophane", "flat", "rect") == "flat"
    assert _resolve_source_shape("lithophane", "curved", "rect") == "curved"
    # Backend uses "cylindrical"; ForgeSlicer expects "cylinder".
    assert _resolve_source_shape("lithophane", "cylindrical", "rect") == "cylinder"
    assert _resolve_source_shape("lithophane", "disc", "rect") == "disc"
    # Box collapses to flat/disc.
    assert _resolve_source_shape("lithophane", "box", "rect") == "flat"
    assert _resolve_source_shape("lithophane", "box", "round") == "disc"


def test_resolve_source_shape_lightbox_parts():
    from forgeslicer_bridge import _resolve_source_shape
    for part in ("lightbox_frame", "lightbox_back", "lightbox_diffuser"):
        assert _resolve_source_shape(part, "box", "rect") == "lightbox_rect"
        assert _resolve_source_shape(part, "box", "round") == "lightbox_circle"


def test_resolve_source_shape_unknown_part():
    from forgeslicer_bridge import _resolve_source_shape
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _resolve_source_shape("bogus", "flat", "rect")


def test_get_session_token_prefers_cookie():
    from forgeslicer_bridge import _get_session_token
    assert _get_session_token("cookie-token", "Bearer header-token") == "cookie-token"
    assert _get_session_token(None, "Bearer header-token") == "header-token"
    assert _get_session_token(None, "bearer lowercase-also-ok") == "lowercase-also-ok"
    assert _get_session_token(None, None) is None
    assert _get_session_token(None, "NotBearer foo") is None


# ---------------------------------------------------------------------------
# HTTP integration test — auth gating + 404 for unknown job
# ---------------------------------------------------------------------------


def test_send_requires_auth():
    r = requests.post(
        f"{API}/forgeslicer/send/whatever",
        json={"part": "lithophane", "format": "3mf"},
        timeout=10,
    )
    assert r.status_code == 401


def test_send_404_unknown_job(authed_client):
    r = authed_client.post(
        f"{API}/forgeslicer/send/job-that-does-not-exist",
        json={"part": "lithophane", "format": "3mf"},
        timeout=10,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Round-trip integration: point inbox at a localhost mock + verify the
# multipart payload + forwarded Bearer header
# ---------------------------------------------------------------------------


class _CapturingHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server that captures the most recent POST."""

    received: Dict[str, Any] = {}

    def log_message(self, *a, **k):  # silence default stderr logging
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingHandler.received = {
            "path": self.path,
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": body,
            "content_type": self.headers.get("Content-Type", ""),
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"received": true, "inbox_id": "fake-123"}')


@pytest.fixture(scope="module")
def mock_inbox():
    """Spin up a localhost HTTP server that ForgeSlicer's URL can be
    pointed at via the dev override. Yields the URL."""
    httpd = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/api/litho/inbox"
    yield url, _CapturingHandler
    httpd.shutdown()


def _solid_image_b64(rgb=(120, 200, 50), size=48) -> str:
    img = Image.new("RGB", (size, size), color=rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_optimized_job(authed_client, geometry="flat", extra_body=None) -> str:
    r = authed_client.post(f"{API}/upload", json={"image_base64": _solid_image_b64()})
    assert r.status_code == 200, r.text
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
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


def test_send_round_trip(authed_client, authed_token, mock_inbox):
    url, handler = mock_inbox
    # Override the inbox URL via the dev hook.
    r = authed_client.post(
        f"{API}/forgeslicer/_dev/inbox-url",
        json={"url": url},
        timeout=10,
    )
    assert r.status_code == 200, r.text

    job_id = _make_optimized_job(authed_client, geometry="flat")
    r = authed_client.post(
        f"{API}/forgeslicer/send/{job_id}",
        json={"part": "lithophane", "format": "3mf", "name": "my-lithophane.3mf"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["source_shape"] == "flat"
    assert out["bytes_sent"] > 300  # 3MF zip header

    # Capture from the mock — verify Bearer + multipart fields.
    recv = handler.received
    assert recv["path"] == "/api/litho/inbox"
    assert recv["headers"]["authorization"] == f"Bearer {authed_token}"
    assert "multipart/form-data" in recv["content_type"]
    body = recv["body"]
    assert b'name="file"' in body
    assert b'name="format"' in body
    assert b'name="source_shape"' in body
    assert b'name="source_metadata"' in body
    assert b"flat" in body  # source_shape value
    assert b"3mf" in body   # format value
    # Reset capture URL back to default so other tests aren't affected.
    authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": None}, timeout=10)


def test_send_box_lightbox_parts(authed_client, mock_inbox):
    url, handler = mock_inbox
    authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": url}, timeout=10)

    job_id = _make_optimized_job(
        authed_client, geometry="box",
        extra_body={
            "box_shape": "rect",
            "box_outer_w_mm": 130, "box_outer_h_mm": 130,
            "box_depth_mm": 40, "box_wall_mm": 3,
            "box_led_mount": "puck", "box_puck_diameter_mm": 65,
            "box_diffuser": True, "box_cable_notch": True,
        },
    )
    for part, expected_shape in [
        ("lithophane", "flat"),
        ("lightbox_frame", "lightbox_rect"),
        ("lightbox_back", "lightbox_rect"),
        ("lightbox_diffuser", "lightbox_rect"),
    ]:
        r = authed_client.post(
            f"{API}/forgeslicer/send/{job_id}",
            json={"part": part, "format": "stl"},
            timeout=20,
        )
        assert r.status_code == 200, f"{part}: {r.text}"
        assert r.json()["source_shape"] == expected_shape

    # Round-box with diffuser=False → diffuser part → 400
    job_id_round = _make_optimized_job(
        authed_client, geometry="box",
        extra_body={
            "box_shape": "round",
            "box_outer_w_mm": 130, "box_outer_h_mm": 130,
            "box_depth_mm": 40, "box_wall_mm": 3,
            "box_led_mount": "puck",
            "box_diffuser": False,
        },
    )
    r = authed_client.post(
        f"{API}/forgeslicer/send/{job_id_round}",
        json={"part": "lithophane", "format": "stl"},
        timeout=20,
    )
    assert r.json()["source_shape"] == "disc"
    r = authed_client.post(
        f"{API}/forgeslicer/send/{job_id_round}",
        json={"part": "lightbox_frame", "format": "stl"},
        timeout=20,
    )
    assert r.json()["source_shape"] == "lightbox_circle"
    r = authed_client.post(
        f"{API}/forgeslicer/send/{job_id_round}",
        json={"part": "lightbox_diffuser", "format": "stl"},
        timeout=20,
    )
    assert r.status_code == 400

    authed_client.post(f"{API}/forgeslicer/_dev/inbox-url", json={"url": None}, timeout=10)
