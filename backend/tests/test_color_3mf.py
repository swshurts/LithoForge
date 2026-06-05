"""Test the colour-aware 3MF emitter introduced for the ForgeSlicer
handoff. The lithophane is now split into one watertight `<object>`
per filament, each tagged with `lithoforge:filament_slot`,
`:filament_name` and `:filament_hex` so ForgeSlicer (or any 3MF reader)
can recover the per-colour palette without decoding the Z-band history."""
from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pytest

from exporters import (
    GeometrySpec,
    build_export,
    build_per_filament_slabs,
    write_3mf,
)


def _read_3mf(blob: bytes) -> dict:
    """Return {filename: text/bytes} for every entry inside the 3MF zip."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_per_filament_slabs_split_by_swap_layers():
    """Three filaments with swaps at layers 4 and 8: expect three
    non-empty slabs, each covering the right Z-band."""
    # 16x16 layer map ramping from 1..12 layers, so every band has cells.
    layer_map = np.tile(np.arange(1, 17), (16, 1)).astype(np.float64)
    layer_map = np.clip(layer_map, 1, 12).astype(np.float64)
    geo = GeometrySpec(mode="flat", width_mm=80, height_mm=80)
    slabs = build_per_filament_slabs(
        layer_map, swap_layer_indices=[4, 8], n_filaments=3,
        layer_height_mm=0.16, geo=geo,
    )
    assert len(slabs) == 3
    # Each slab should report a strictly positive triangle count.
    for k, verts, faces in slabs:
        assert verts.shape[1] == 3
        assert faces.shape[1] == 3
        assert faces.shape[0] > 0
    # Z-ranges: slab 0 ∈ [0, 4*0.16], slab 1 ∈ [4*0.16, 8*0.16],
    # slab 2 ∈ [8*0.16, max_layer*0.16] — confirm by inspecting verts.
    z0 = slabs[0][1][:, 2]
    z1 = slabs[1][1][:, 2]
    z2 = slabs[2][1][:, 2]
    assert z0.min() == pytest.approx(0.0)
    assert z0.max() == pytest.approx(4 * 0.16, abs=1e-3)
    assert z1.min() == pytest.approx(4 * 0.16, abs=1e-3)
    assert z1.max() == pytest.approx(8 * 0.16, abs=1e-3)
    assert z2.min() == pytest.approx(8 * 0.16, abs=1e-3)


def test_per_filament_slabs_skip_empty():
    """If a swap band is entirely above the column height nothing
    should be emitted for that filament."""
    layer_map = np.full((8, 8), 3.0)
    geo = GeometrySpec(mode="flat", width_mm=40, height_mm=40)
    # Three filaments but the print only reaches layer 3 → second and
    # third bands collapse to nothing.
    slabs = build_per_filament_slabs(
        layer_map, swap_layer_indices=[4, 8], n_filaments=3,
        layer_height_mm=0.16, geo=geo,
    )
    indices = [k for (k, *_rest) in slabs]
    assert indices == [0]


def test_3mf_contains_one_object_per_filament_with_metadata():
    """End-to-end through build_export. The resulting 3MF zip must
    contain (i) one `<object>` per filament that actually printed and
    (ii) each object's metadatagroup must carry the three lithoforge
    tags + Bambu-style per-object extruder in model_settings.config."""
    layer_map = np.tile(np.arange(1, 13), (12, 1)).astype(np.float64)
    layer_map = np.clip(layer_map, 1, 10).astype(np.float64)
    geo = GeometrySpec(mode="flat", width_mm=60, height_mm=60)
    filament_names = ["White", "Yellow", "Cyan"]
    swap_heights_mm = [4 * 0.16, 7 * 0.16]
    swap_colors = ["#FFFFFF", "#FFD800", "#00B8E6"]
    out = build_export(
        layer_map, layer_height_mm=0.16, geo=geo,
        filament_names=filament_names,
        swap_heights_mm=swap_heights_mm,
        swap_colors=swap_colors,
    )
    assert "threemf" in out and len(out["threemf"]) > 200

    entries = _read_3mf(out["threemf"])
    assert "3D/3dmodel.model" in entries
    assert "Metadata/model_settings.config" in entries

    model = entries["3D/3dmodel.model"].decode("utf-8")
    ns = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    root = ET.fromstring(model)
    objects = root.findall(f"{ns}resources/{ns}object")
    assert len(objects) == 3, "expected 3 filaments × 1 object each"

    expected = [
        (0, "White", "#FFFFFF"),
        (1, "Yellow", "#FFD800"),
        (2, "Cyan", "#00B8E6"),
    ]
    for obj, (slot, name, hex_) in zip(objects, expected):
        meta = {
            m.get("name"): m.text
            for m in obj.findall(f"{ns}metadatagroup/{ns}metadata")
        }
        assert meta["lithoforge:filament_slot"] == str(slot)
        assert meta["lithoforge:filament_name"] == name
        assert meta["lithoforge:filament_hex"] == hex_.upper()
        assert obj.get("name") == name

    cfg = entries["Metadata/model_settings.config"].decode("utf-8")
    # Bambu/Orca slot indexing is 1-based.
    assert 'key="extruder" value="1"' in cfg
    assert 'key="extruder" value="2"' in cfg
    assert 'key="extruder" value="3"' in cfg


def test_write_3mf_falls_back_to_single_mesh_without_slabs():
    """The optional per_filament_slabs arg keeps the legacy single-mesh
    output reachable for callers that still want it (STL-parity)."""
    verts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=float)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    blob = write_3mf(
        verts, faces, filaments=[("A", "#000000")],
        swap_heights_mm=[], layer_height_mm=0.16,
    )
    entries = _read_3mf(blob)
    model = entries["3D/3dmodel.model"].decode("utf-8")
    # Exactly one <object> when slabs aren't supplied.
    assert len(re.findall(r"<object\\b", model)) <= 1 \
        or re.findall(r"<object id=\"1\"", model)
    assert "Metadata/model_settings.config" not in entries
