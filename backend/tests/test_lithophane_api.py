"""Backend tests for the CMYKW Lithophane API.

Covers health, filaments, upload, optimize, jobs, exports (STL/swaps/3MF),
curved geometry, and legacy status endpoints.
"""

from __future__ import annotations

import base64
import io
import os
import struct
import zipfile

import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend .env (tests run in container without env var)
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break

API = f"{BASE_URL}/api"


# --- fixtures ---------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _make_photo_b64(size=(128, 96)) -> str:
    """Create a realistic-ish photo with gradients + coloured blobs."""
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        for x in range(w):
            r = int(255 * x / w)
            g = int(255 * y / h)
            b = int(255 * ((x + y) / (w + h)))
            px[x, y] = (r, g, b)
    # Add a few patches of primary colours
    for (x0, y0, col) in [
        (10, 10, (200, 30, 30)),
        (60, 20, (30, 180, 60)),
        (30, 60, (40, 60, 220)),
    ]:
        for dy in range(15):
            for dx in range(15):
                if 0 <= x0 + dx < w and 0 <= y0 + dy < h:
                    px[x0 + dx, y0 + dy] = col
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="session")
def image_b64():
    return _make_photo_b64()


@pytest.fixture(scope="session")
def uploaded(client, image_b64):
    r = client.post(f"{API}/upload", json={"image_base64": image_b64,
                                           "filename": "TEST_photo.png"})
    assert r.status_code == 200, r.text
    data = r.json()
    return data


@pytest.fixture(scope="session")
def optimized(client, uploaded):
    body = {
        "image_id": uploaded["image_id"],
        "width_mm": 100.0,
        "height_mm": 80.0,
        "thickness_mm": 3.0,
        "border_mm": 2.0,
        "layer_height_mm": 0.12,
        "max_swaps": 5,
        "geometry": "flat",
        "curve_radius_mm": 80.0,
    }
    r = client.post(f"{API}/optimize", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --- health + filaments -----------------------------------------------------

class TestHealth:
    def test_root(self, client):
        r = client.get(f"{API}/")
        assert r.status_code == 200
        assert "Lithophane" in r.json().get("message", "")

    def test_default_filaments(self, client):
        r = client.get(f"{API}/filaments/default")
        assert r.status_code == 200
        body = r.json()
        assert "filaments" in body
        fils = body["filaments"]
        assert len(fils) == 8
        names = [f["name"] for f in fils]
        assert set(names) == {
            "White", "Yellow", "Orange", "Red",
            "Magenta", "Green", "Blue", "Key",
        }
        for f in fils:
            assert set(f.keys()) >= {"name", "hex", "td"}
            assert f["hex"].startswith("#")
            assert isinstance(f["td"], (int, float))


# --- upload -----------------------------------------------------------------

class TestUpload:
    def test_upload_raw_b64(self, client, image_b64):
        r = client.post(f"{API}/upload",
                        json={"image_base64": image_b64})
        assert r.status_code == 200
        data = r.json()
        assert "image_id" in data
        assert data["width"] > 0 and data["height"] > 0

    def test_upload_data_url(self, client, image_b64):
        r = client.post(
            f"{API}/upload",
            json={"image_base64": f"data:image/png;base64,{image_b64}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["width"] > 0 and data["height"] > 0

    def test_upload_invalid_base64(self, client):
        r = client.post(f"{API}/upload",
                        json={"image_base64": "!!!not-base64!!!"})
        assert r.status_code == 400


# --- optimize ---------------------------------------------------------------

class TestOptimize:
    def test_optimize_basic(self, optimized):
        d = optimized
        assert "job_id" in d
        assert d["preview_png_base64"]
        assert d["heightmap_png_base64"]
        assert isinstance(d["delta_e_mean"], (int, float))
        assert isinstance(d["delta_e_p95"], (int, float))
        # total_layers should match round(thickness / layer_height) = 3/0.12 = 25
        assert d["total_layers"] == round(3.0 / 0.12)
        assert sum(d["layer_allocation"]) == d["total_layers"]
        # max_swaps=5 → 6 filaments
        assert len(d["filaments"]) == 6
        # swap_heights count matches filaments (one entry per filament, origin included)
        assert len(d["swap_heights_mm"]) == 6
        # timeline entries have start/end Z
        assert len(d["timeline"]) == 6
        for t in d["timeline"]:
            assert {"color", "name", "layers", "start_z_mm", "end_z_mm"} <= set(t.keys())
            assert t["end_z_mm"] >= t["start_z_mm"]

    def test_optimize_preview_is_valid_png(self, optimized):
        png = base64.b64decode(optimized["preview_png_base64"])
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        hm = base64.b64decode(optimized["heightmap_png_base64"])
        assert hm[:8] == b"\x89PNG\r\n\x1a\n"

    def test_optimize_unknown_image(self, client):
        r = client.post(f"{API}/optimize",
                        json={"image_id": "does-not-exist"})
        assert r.status_code == 404

    def test_optimize_max_swaps_2(self, client, uploaded):
        body = {
            "image_id": uploaded["image_id"],
            "max_swaps": 2,
            "thickness_mm": 2.4,
            "layer_height_mm": 0.12,
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        # max_swaps=2 → exactly 3 filaments
        assert len(d["filaments"]) == 3
        # swap_heights list (including origin) length == 3 → 2 swap points beyond origin
        assert len(d["swap_heights_mm"]) == 3
        non_origin = [z for z in d["swap_heights_mm"] if z > 0]
        assert len(non_origin) == 2
        assert sum(d["layer_allocation"]) == d["total_layers"]


# --- jobs -------------------------------------------------------------------

class TestJobs:
    def test_get_job_metadata(self, client, optimized):
        r = client.get(f"{API}/jobs/{optimized['job_id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["job_id"] == optimized["job_id"]
        assert len(d["filaments"]) == len(optimized["filaments"])
        assert d["allocation"] == optimized["layer_allocation"]
        assert d["layer_height_mm"] == 0.12

    def test_get_job_unknown(self, client):
        r = client.get(f"{API}/jobs/nonexistent-id")
        assert r.status_code == 404


# --- exports ----------------------------------------------------------------

class TestExports:
    def test_stl(self, client, optimized):
        r = client.get(f"{API}/export/{optimized['job_id']}/stl")
        assert r.status_code == 200
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        content = r.content
        assert len(content) > 84, "STL too small"
        # Binary STL format: 80 byte header, uint32 triangle count, then tris
        header = content[:80]
        tri_count = struct.unpack("<I", content[80:84])[0]
        assert tri_count > 0
        # Expected file size = 84 + tri_count * 50
        assert len(content) == 84 + tri_count * 50
        assert b"CMYKW" in header or b"Lithophane" in header

    def test_swaps(self, client, optimized):
        r = client.get(f"{API}/export/{optimized['job_id']}/swaps")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        text = r.text
        assert "M600" in text
        # New paste-ready snippet sections must all be present
        assert "OPTION A" in text and "PrusaSlicer" in text
        assert "OPTION B" in text and "Cura" in text
        assert "OPTION C" in text and "Marlin" in text
        # Conditional Slic3r-family snippet present
        assert "{if layer_num ==" in text and "{endif}" in text

    def test_3mf(self, client, optimized):
        r = client.get(f"{API}/export/{optimized['job_id']}/3mf")
        assert r.status_code == 200
        content = r.content
        assert content[:2] == b"PK", "Not a valid zip"
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            names = z.namelist()
            assert "3D/3dmodel.model" in names
            assert "[Content_Types].xml" in names
            model = z.read("3D/3dmodel.model").decode("utf-8")
            assert "<vertices>" in model and "<triangles>" in model
            # Project config must include the auto-pause snippet
            cfg = z.read("Metadata/project_settings.config").decode("utf-8")
            assert "layer_change_gcode" in cfg
            assert "M600" in cfg
            assert "{if layer_num ==" in cfg

    def test_export_unknown_job(self, client):
        for kind in ("stl", "swaps", "3mf"):
            r = client.get(f"{API}/export/unknown-job/{kind}")
            assert r.status_code == 404, f"{kind} did not return 404"


# --- curved geometry --------------------------------------------------------

class TestCurvedGeometry:
    def test_curved_stl(self, client, uploaded):
        body = {
            "image_id": uploaded["image_id"],
            "width_mm": 120.0,
            "height_mm": 60.0,
            "thickness_mm": 2.4,
            "border_mm": 2.0,
            "layer_height_mm": 0.2,
            "max_swaps": 3,
            "geometry": "curved",
            "curve_radius_mm": 50.0,
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        stl = client.get(f"{API}/export/{job_id}/stl")
        assert stl.status_code == 200
        tri_count = struct.unpack("<I", stl.content[80:84])[0]
        assert tri_count > 0


# --- disc geometry ----------------------------------------------------------

class TestDiscGeometry:
    def test_disc_optimize_and_export(self, client, uploaded):
        body = {
            "image_id": uploaded["image_id"],
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
        data = r.json()
        job_id = data["job_id"]
        # All three exports should succeed.
        for kind in ("stl", "swaps", "3mf"):
            x = client.get(f"{API}/export/{job_id}/{kind}")
            assert x.status_code == 200, f"{kind} failed"
        stl = client.get(f"{API}/export/{job_id}/stl")
        tri_count = struct.unpack("<I", stl.content[80:84])[0]
        # Disc cuts away ~21% of cells compared to rectangle (π/4) and adds
        # boundary side walls, so triangle count should be > 0 and clearly
        # less than the un-masked rectangle's count would be.
        assert tri_count > 0


# --- printer profiles + buyer override --------------------------------------

class TestPrinters:
    def test_catalog(self, client):
        r = client.get(f"{API}/printers")
        assert r.status_code == 200
        data = r.json()
        assert "printers" in data and len(data["printers"]) >= 8
        # required keys
        for p in data["printers"]:
            for key in ("id", "name", "slicer_family", "bed_x_mm",
                        "bed_y_mm", "multi_tool", "supported_formats"):
                assert key in p, f"missing {key} in {p}"
        ids = {p["id"] for p in data["printers"]}
        # Sanity: cross-slicer printers are present
        assert "bambu_x1c" in ids
        assert "prusa_mk4" in ids
        assert "flashforge_ad5m" in ids
        assert "sovol_sv08" in ids
        assert "generic_orca" in ids

    def test_bed_fit_check(self, client):
        # Bambu A1 mini has a 180mm bed. A 200mm panel must NOT fit.
        r = client.get(
            f"{API}/printers/bambu_a1_mini/fit",
            params={"width_mm": 200, "height_mm": 200},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["fits"] is False
        # 150mm panel fits.
        r2 = client.get(
            f"{API}/printers/bambu_a1_mini/fit",
            params={"width_mm": 150, "height_mm": 150},
        )
        assert r2.json()["fits"] is True

    def test_export_3mf_picks_up_creator_printer(self, client, uploaded):
        # Creator chose a multi-tool Bambu X1C → 3MF should embed T<n>
        # tool changes, not M600. Use max_swaps=3 so all 3 swaps fit
        # within the 4-lane AMS (T1, T2, T3) without overflowing.
        body = {
            "image_id": uploaded["image_id"],
            "width_mm": 100.0,
            "height_mm": 100.0,
            "thickness_mm": 3.0,
            "border_mm": 2.0,
            "layer_height_mm": 0.12,
            "max_swaps": 3,
            "geometry": "flat",
            "printer_id": "bambu_x1c",
            "license": "CC-BY-NC",
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        threemf = client.get(f"{API}/export/{job_id}/3mf")
        assert threemf.status_code == 200
        with zipfile.ZipFile(io.BytesIO(threemf.content)) as z:
            cfg = z.read("Metadata/project_settings.config").decode("utf-8")
            # Multi-tool: tool changes, no M600
            assert "T1" in cfg or "T2" in cfg or "T3" in cfg
            assert "M600" not in cfg
            assert "cmykw_multi_tool" in cfg and "true" in cfg
            # License is included
            assert "CC-BY-NC" in cfg
        # Swap text mirrors the printer choice
        swaps = client.get(f"{API}/export/{job_id}/swaps").text
        assert "Bambu" in swaps and "tool change" in swaps

    def test_buyer_override_switches_printer(self, client, optimized):
        # Default printer is generic_orca (single extruder → M600).
        # Buyer asks for bambu_x1c (multi-tool → T<n>).
        # NOTE: `optimized` uses max_swaps=5, so the 5th swap will
        # overflow the 4-lane AMS and fall back to an M600 marker.
        # We verify both that tool changes appear AND that any leftover
        # M600 carries the explicit "out of AMS slots" marker (i.e.
        # we never silently emit a bare M600 to a multi-tool machine).
        job_id = optimized["job_id"]
        base = client.get(f"{API}/export/{job_id}/3mf")
        with zipfile.ZipFile(io.BytesIO(base.content)) as z:
            base_cfg = z.read("Metadata/project_settings.config").decode("utf-8")
        assert "M600" in base_cfg
        assert "T1" not in base_cfg  # generic profile is single-extruder

        override = client.get(
            f"{API}/export/{job_id}/3mf", params={"printer": "bambu_x1c"}
        )
        assert override.status_code == 200
        with zipfile.ZipFile(io.BytesIO(override.content)) as z:
            cfg = z.read("Metadata/project_settings.config").decode("utf-8")
        # AMS lanes assigned
        assert "T1" in cfg and "T2" in cfg and "T3" in cfg
        # Bambu's bed (256mm) is in the printable area
        assert "256x256" in cfg
        # Any leftover M600 must carry the overflow marker.
        if "M600" in cfg:
            assert "out of AMS slots" in cfg

    def test_ams_slot_overflow_falls_back_to_m600(self, client, uploaded):
        # Bambu AMS has 4 lanes. Asking for 6 filaments → 5 swaps →
        # slot 4 should fall back to M600 with a marker comment so the
        # printer doesn't error trying to switch to a non-existent T4.
        body = {
            "image_id": uploaded["image_id"],
            "width_mm": 100.0,
            "height_mm": 100.0,
            "thickness_mm": 3.0,
            "border_mm": 2.0,
            "layer_height_mm": 0.12,
            "max_swaps": 5,
            "geometry": "flat",
            "printer_id": "bambu_x1c",
        }
        r = client.post(f"{API}/optimize", json=body)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        threemf = client.get(f"{API}/export/{job_id}/3mf")
        with zipfile.ZipFile(io.BytesIO(threemf.content)) as z:
            cfg = z.read("Metadata/project_settings.config").decode("utf-8")
        # 4 valid tool slots (T1-T3) plus at least one overflow M600.
        assert "T1" in cfg and "T2" in cfg and "T3" in cfg
        assert "out of AMS slots" in cfg


# --- legacy status endpoints -----------------------------------------------

class TestLegacyStatus:
    def test_status_create_and_list(self, client):
        r = client.post(f"{API}/status", json={"client_name": "TEST_pytest"})
        assert r.status_code == 200
        data = r.json()
        assert data["client_name"] == "TEST_pytest"
        assert "id" in data and "timestamp" in data
        r2 = client.get(f"{API}/status")
        assert r2.status_code == 200
        items = r2.json()
        assert any(i["client_name"] == "TEST_pytest" for i in items)
