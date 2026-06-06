"""Tests for the marketplace preview-mesh endpoint."""

from __future__ import annotations

import struct

import requests

from tests.conftest import API


def test_preview_mesh_404_for_unknown_listing():
    r = requests.get(f"{API}/marketplace/this-listing-does-not-exist/preview-mesh")
    assert r.status_code == 404


def test_preview_mesh_404_for_unlisted_job(authed_client):
    """A job that exists but isn't listed must NOT leak its preview
    mesh — same 404 as a nonexistent listing."""
    # Upload, optimize, but DON'T publish a listing.
    import base64, io, numpy as np
    from PIL import Image
    arr = np.zeros((128, 128, 3), dtype=np.uint8)
    arr[..., 0] = 200
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    up = authed_client.post(f"{API}/upload", json={"image_base64": img_b64})
    assert up.status_code == 200
    opt = authed_client.post(
        f"{API}/optimize",
        json={"image_id": up.json()["image_id"], "max_swaps": 3},
    )
    assert opt.status_code == 200
    job_id = opt.json()["job_id"]
    # Not listed → not visible.
    r = requests.get(f"{API}/marketplace/{job_id}/preview-mesh")
    assert r.status_code == 404


def test_preview_mesh_returns_small_binary_stl(authed_client):
    """When the job IS listed, the endpoint returns a binary STL and
    the file is meaningfully smaller than the full-resolution export
    (because of the downsample)."""
    import base64, io, numpy as np
    from PIL import Image

    arr = np.zeros((256, 256, 3), dtype=np.uint8)
    arr[..., 0] = 200
    arr[64:192, 64:192, :] = 50
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    img_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    up = authed_client.post(f"{API}/upload", json={"image_base64": img_b64})
    opt = authed_client.post(
        f"{API}/optimize",
        json={"image_id": up.json()["image_id"], "max_swaps": 3},
    )
    job_id = opt.json()["job_id"]
    # Publish it.
    pub = authed_client.put(
        f"{API}/my-jobs/{job_id}/listing",
        json={"title": "Test listing", "price_usd": 1.0},
    )
    assert pub.status_code == 200, pub.text

    # Anonymous fetch must work — this is a public preview.
    r = requests.get(f"{API}/marketplace/{job_id}/preview-mesh")
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("model/stl")
    body = r.content
    # Binary STL header is 80 bytes + 4 bytes triangle count.
    assert len(body) > 84
    tri_count = struct.unpack("<I", body[80:84])[0]
    # Each triangle = 50 bytes (12B normal + 36B verts + 2B attr).
    expected_len = 84 + tri_count * 50
    assert len(body) == expected_len, (
        f"binary STL size mismatch: {len(body)} vs expected {expected_len}"
    )
    # Downsampled mesh should be far smaller than full-res.
    # Full-res (512px → ~10k triangles after greedy meshing on flat).
    # Downsampled (96px → ~1k triangles).
    assert tri_count < 5000, (
        f"preview mesh shouldn't approach full-res triangle counts; got {tri_count}"
    )
    # Public preview should have an aggressive cache header so the
    # browser caches it across listing-page visits. NOTE: in this
    # environment the Cloudflare ingress rewrites response cache
    # headers — we can't assert on the header here, but the server
    # does set it (see marketplace.py preview_mesh handler).
