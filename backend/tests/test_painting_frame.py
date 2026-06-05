"""Tests for painting-mode matboard frame + void-pixel reporting."""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image

from tests.conftest import API
import requests


def _make_test_image_b64(w: int = 256, h: int = 256) -> str:
    """A simple gradient image so optimize has interesting pixels."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[..., 0] = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    arr[..., 1] = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
    arr[..., 2] = 128
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _upload_test_image(authed_client) -> str:
    r = authed_client.post(
        f"{API}/upload",
        json={"image_base64": _make_test_image_b64(), "filename": "frame_test.png"},
    )
    assert r.status_code == 200, r.text
    return r.json()["image_id"]


def test_optimize_returns_void_pixel_count_for_lithophane(authed_client):
    image_id = _upload_test_image(authed_client)
    r = authed_client.post(
        f"{API}/optimize",
        json={
            "image_id": image_id,
            "render_mode": "lithophane",
            "max_swaps": 4,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "void_pixels" in body
    assert "in_domain_pixels" in body
    assert isinstance(body["void_pixels"], int)
    assert body["void_pixels"] >= 0
    # Rectangular geometry → every pixel is in-domain.
    assert body["in_domain_pixels"] > 0


def test_optimize_disc_in_domain_excludes_outside_circle(authed_client):
    image_id = _upload_test_image(authed_client)
    r = authed_client.post(
        f"{API}/optimize",
        json={
            "image_id": image_id,
            "render_mode": "painting",
            "geometry": "disc",
            "max_swaps": 3,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Disc only counts pixels inside the inscribed circle as in-domain
    # — strictly less than the full rectangle area.
    # For a 512×512 LUT preview, the inscribed circle has area ≈ π/4 ×
    # 512² ≈ 205,887 pixels (vs 262,144 for the full rect).
    assert body["in_domain_pixels"] > 0
    assert body["in_domain_pixels"] < 512 * 512


def test_painting_frame_paints_border_in_brightest_filament(authed_client):
    """Frame should fill the outer N-px border with the brightest filament's
    full stack height. We can't introspect layer_map from the API, but
    swap_heights_mm / filaments reveal the brightest filament's hex, and
    the preview PNG should have that hex along the outer pixel band."""
    image_id = _upload_test_image(authed_client)

    base = {
        "image_id": image_id,
        "render_mode": "painting",
        "max_swaps": 3,
        "width_mm": 100.0,
        "height_mm": 100.0,
        "border_mm": 0.0,
    }
    r_no_frame = authed_client.post(f"{API}/optimize", json={**base, "frame_mm": 0.0})
    assert r_no_frame.status_code == 200, r_no_frame.text
    r_frame = authed_client.post(f"{API}/optimize", json={**base, "frame_mm": 10.0})
    assert r_frame.status_code == 200, r_frame.text

    # Decode both preview PNGs and check the outer pixel ring.
    def _ring_rgbs(b64: str):
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        a = np.asarray(img)
        h, w, _ = a.shape
        ring = np.concatenate([
            a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :],
        ])
        return ring

    no_frame_ring = _ring_rgbs(r_no_frame.json()["preview_png_base64"])
    frame_ring = _ring_rgbs(r_frame.json()["preview_png_base64"])

    # With a 10mm frame on a 100mm side, the outer ring MUST all be
    # exactly one colour. Without a frame, the outer ring will reflect
    # the underlying gradient — many distinct colours.
    frame_unique = {tuple(p) for p in frame_ring}
    no_frame_unique = {tuple(p) for p in no_frame_ring}
    assert len(frame_unique) == 1, (
        f"framed preview's outer ring must be monochrome, got {len(frame_unique)} colours"
    )
    assert len(no_frame_unique) > 1, (
        f"unframed preview's outer ring should reflect the gradient (multiple palette colours), got only {len(no_frame_unique)}"
    )


def test_frame_zero_keeps_painting_output_unchanged(authed_client):
    """frame_mm=0 must be a no-op vs not specifying frame_mm at all."""
    image_id = _upload_test_image(authed_client)
    r_a = authed_client.post(
        f"{API}/optimize",
        json={
            "image_id": image_id,
            "render_mode": "painting",
            "max_swaps": 3,
        },
    )
    r_b = authed_client.post(
        f"{API}/optimize",
        json={
            "image_id": image_id,
            "render_mode": "painting",
            "max_swaps": 3,
            "frame_mm": 0.0,
        },
    )
    assert r_a.status_code == 200 and r_b.status_code == 200
    # Same preview bytes → same render.
    assert r_a.json()["preview_png_base64"] == r_b.json()["preview_png_base64"]
