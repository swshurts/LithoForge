"""Catalog expansion tests — printers, nozzles, filament materials.

Covers the June 2026 catalog expansion:
  • ≥50 printer profiles with nozzle metadata + tool_slots
  • nozzle_layer_bounds 25–80% window
  • /api/printers exposes the new fields
  • filament catalog ≥400 SKUs with PLA + PETG materials
  • /api/filament-library material filters (browse + hex search)
  • nozzle_mm flows into the exported 3MF project settings
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import zipfile

import pytest
from PIL import Image

from manufacturer_library import CATALOG, MATERIALS, brands
from printers import (
    PRINTER_PROFILES,
    build_layer_change_gcode,
    get_profile,
    list_profiles,
    nozzle_layer_bounds,
)

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
def session(authed_client):
    return authed_client


@pytest.fixture(scope="module")
def nozzle_job(session):
    """Optimize a tiny image with an explicit nozzle_mm=0.6."""
    up = session.post(f"{API}/upload", json={"image_base64": _photo_b64()})
    assert up.status_code == 200, up.text
    image_id = up.json()["image_id"]
    r = session.post(f"{API}/optimize", json={
        "image_id": image_id,
        "width_mm": 50.0, "height_mm": 50.0,
        "layer_height_mm": 0.12, "max_swaps": 2,
        "printer_id": "bambu_a1",
        "nozzle_mm": 0.6,
    })
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


# ---------------------------------------------------------------------------
# Printer catalog (unit)
# ---------------------------------------------------------------------------

def test_printer_catalog_size():
    assert len(PRINTER_PROFILES) >= 50


def test_every_profile_has_nozzle_metadata():
    for p in list_profiles():
        assert p["nozzle_sizes_mm"], p["id"]
        assert p["default_nozzle_mm"] in p["nozzle_sizes_mm"], p["id"]
        assert p["tool_slots"] >= 1, p["id"]
        assert all(0.1 <= n <= 1.2 for n in p["nozzle_sizes_mm"]), p["id"]


def test_key_new_printers_present():
    for pid in [
        "bambu_h2d", "bambu_x1e", "bambu_p1p",
        "creality_k2_plus", "creality_k1c", "creality_ender3_v3",
        "anycubic_kobra3", "anycubic_kobra_s1",
        "qidi_plus4", "qidi_plus4_box",
        "flashforge_ad5x",
        "prusa_core_one", "prusa_core_one_l", "prusa_mk4_mmu3",
        "elegoo_neptune4_max", "sovol_sv06",
        "voron_trident", "ratrig_vcore3",
    ]:
        assert pid in PRINTER_PROFILES, pid


def test_legacy_printer_ids_unchanged():
    """Old jobs reference these ids — they must keep resolving."""
    for pid in [
        "generic_orca", "bambu_a1_mini", "bambu_a1", "bambu_p1s",
        "bambu_x1c", "sovol_sv07", "sovol_sv08", "elegoo_neptune4",
        "elegoo_centauri", "anycubic_kobra2", "creality_k1",
        "flashforge_ad5m", "prusa_mk4", "prusa_mini", "prusa_xl",
        "voron_24", "ultimaker_s3", "generic_marlin",
    ]:
        assert pid in PRINTER_PROFILES, pid


def test_nozzle_layer_bounds_window():
    lo, hi = nozzle_layer_bounds(0.4)
    assert lo == pytest.approx(0.1)
    assert hi == pytest.approx(0.32)
    lo2, hi2 = nozzle_layer_bounds(0.2)
    assert lo2 == pytest.approx(0.05)
    assert hi2 == pytest.approx(0.16)


def test_tool_slots_drive_gcode():
    # MMU3 has 5 lanes → 4 swaps stay tool changes; 5th overflows to M600.
    mmu = get_profile("prusa_mk4_mmu3")
    g = build_layer_change_gcode(mmu, [10, 20, 30, 40, 50])
    assert "T4" in g
    assert "M600 ; out of AMS slots" in g
    # IDEX J1s has only 2 lanes → second swap already overflows.
    j1 = get_profile("snapmaker_j1s")
    g2 = build_layer_change_gcode(j1, [10, 20])
    assert "T1" in g2
    assert "M600 ; out of AMS slots" in g2


def test_printers_endpoint_exposes_nozzles(session):
    r = session.get(f"{API}/printers")
    assert r.status_code == 200
    printers = r.json()["printers"]
    assert len(printers) >= 50
    for p in printers:
        assert "nozzle_sizes_mm" in p
        assert "default_nozzle_mm" in p
        assert "tool_slots" in p


# ---------------------------------------------------------------------------
# Filament catalog
# ---------------------------------------------------------------------------

def test_filament_catalog_size_and_materials():
    assert len(CATALOG) >= 400
    assert set(MATERIALS) == {"PLA", "PETG"}
    mats = {f.material for f in CATALOG}
    assert mats == {"PLA", "PETG"}
    petg = [f for f in CATALOG if f.material == "PETG"]
    assert len(petg) >= 80


def test_filament_catalog_brand_breadth():
    bs = brands()
    assert len(bs) >= 15
    for b in ["Bambu Lab", "Elegoo", "Creality", "Anycubic", "Inland",
              "Polymaker", "Prusament", "JAYO"]:
        assert b in bs, b


def test_filament_ids_unique_and_hex_valid():
    ids = [f.id for f in CATALOG]
    assert len(ids) == len(set(ids))
    for f in CATALOG:
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", f.hex), f.id
        assert 0 < f.td <= 20, f.id


def test_browse_material_filter(session):
    r = session.get(f"{API}/filament-library", params={"material": "PETG"})
    assert r.status_code == 200
    items = r.json()["filaments"]
    assert items and all(i["material"] == "PETG" for i in items)


def test_hex_search_material_filter(session):
    r = session.get(
        f"{API}/filament-library/search",
        params={"hex": "FFFFFF", "material": "PETG", "limit": 10},
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and all(x["material"] == "PETG" for x in results)


# ---------------------------------------------------------------------------
# Nozzle → export metadata
# ---------------------------------------------------------------------------

def test_nozzle_embedded_in_3mf(session, nozzle_job):
    r = session.get(f"{API}/export/{nozzle_job}/3mf")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        cfg = json.loads(z.read("Metadata/project_settings.config"))
    assert cfg["nozzle_diameter"] == [0.6]
    assert cfg["cmykw_nozzle_mm"] == 0.6


def test_nozzle_in_swap_txt(session, nozzle_job):
    r = session.get(f"{API}/export/{nozzle_job}/swaps")
    assert r.status_code == 200
    assert "nozzle         = 0.6 mm" in r.text
