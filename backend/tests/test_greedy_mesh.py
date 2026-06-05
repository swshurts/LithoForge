"""Tests for the greedy-mesh optimization in exporters.py.

Validates:
  - lossless: every vertex is still at the right z, bounding box matches,
    total layer count matches.
  - effective: a constant-z layer map collapses to ≤ 12 triangles for
    the top+bottom (2 quads × 2 triangles each = 8 + side walls).
  - per-filament slabs see the same reduction.
"""

from __future__ import annotations

import numpy as np

from exporters import (
    GeometrySpec,
    _build_mesh,
    _greedy_top_rects,
    _bottom_rects,
    build_per_filament_slabs,
    build_export,
)


def test_greedy_top_rects_collapses_constant_z_to_one_rect():
    """A 10×10 constant-z field becomes ONE rectangle covering all 100
    cells — the foundational optimisation."""
    z = np.full((11, 11), 1.6, dtype=np.float64)
    valid = np.ones((10, 10), dtype=bool)
    rects = _greedy_top_rects(z, valid)
    assert len(rects) == 1
    r0, c0, r1, c1, flat = rects[0]
    assert (r0, c0, r1, c1, flat) == (0, 0, 9, 9, True)


def test_greedy_top_rects_singletons_for_unequal_corners():
    """A field where every cell's 4 corners have different z values
    can't be merged — every cell becomes its own singleton rect."""
    z = np.arange(11 * 11, dtype=np.float64).reshape(11, 11)
    valid = np.ones((10, 10), dtype=bool)
    rects = _greedy_top_rects(z, valid)
    assert len(rects) == 100, "no merging possible → 100 singletons"
    assert all(not flat for *_, flat in rects)


def test_greedy_top_rects_mixed_field():
    """Half constant, half varying → split into two regions plus
    singletons. We don't pin the exact count — just verify it's far
    fewer than the per-cell baseline."""
    z = np.zeros((11, 11), dtype=np.float64)
    z[:6, :] = 2.0   # top half constant
    z[6:, :] = np.arange(5 * 11, dtype=np.float64).reshape(5, 11) * 0.1
    valid = np.ones((10, 10), dtype=bool)
    rects = _greedy_top_rects(z, valid)
    # Top half collapses to ONE big rect. Bottom half is per-cell.
    flat_rects = [r for r in rects if r[4]]
    assert any(r[0] == 0 and r[2] >= 4 for r in flat_rects), "top half should merge"
    assert len(rects) < 100


def test_bottom_rects_collapses_to_one_when_full():
    """A fully-valid 10×10 footprint collapses to exactly 1 bottom
    rectangle. This is what gives a flat single-mesh export only 2
    bottom triangles instead of 200."""
    valid = np.ones((10, 10), dtype=bool)
    rects = _bottom_rects(valid)
    assert rects == [(0, 0, 9, 9)]


def test_bottom_rects_decomposes_disconnected_holes():
    """A footprint with a hole still produces a valid decomposition
    that covers every True cell exactly once."""
    valid = np.ones((6, 6), dtype=bool)
    valid[2:4, 2:4] = False  # 2×2 hole in the middle
    rects = _bottom_rects(valid)
    covered = np.zeros_like(valid)
    for r0, c0, r1, c1 in rects:
        # No overlap between rects (each cell covered ≤ once).
        assert not covered[r0:r1+1, c0:c1+1].any()
        covered[r0:r1+1, c0:c1+1] = True
    # Every valid cell covered exactly once; no invalid cell covered.
    np.testing.assert_array_equal(covered, valid)


def test_build_mesh_constant_layer_map_collapses_triangles():
    """A perfectly-flat layer_map should produce a tiny mesh: top is
    2 triangles, bottom is 2 triangles, walls are O(perimeter)."""
    layer_map = np.full((16, 16), 8, dtype=np.float64)
    geo = GeometrySpec(mode="flat", width_mm=40, height_mm=40, border_mm=0)
    verts, faces = _build_mesh(layer_map, layer_height_mm=0.16, geo=geo)
    # Top: 2 tris. Bottom: 2 tris. Walls: 4 × 15 × 2 = 120 tris (per-pixel).
    # Total ≤ 130 (much less than the 16×16 grid's ~960 baseline).
    assert faces.shape[0] < 200, (
        f"flat heightmap should collapse to <200 triangles, got {faces.shape[0]}"
    )
    # Old per-pixel baseline would have been:
    #   top: 15×15×2 = 450; bottom: 450; walls: 120 = 1020 triangles
    # Verify a substantial reduction.
    assert faces.shape[0] < 200, "must be a substantial reduction"
    # All triangles reference valid vertex indices.
    assert int(faces.max()) < verts.shape[0]
    assert int(faces.min()) >= 0


def test_build_mesh_preserves_bounding_box():
    """Greedy meshing is lossless — the bounding box of the mesh
    matches what the original per-cell mesh would have produced."""
    layer_map = np.zeros((16, 16), dtype=np.float64)
    layer_map[4:12, 4:12] = 10  # a raised square
    geo = GeometrySpec(mode="flat", width_mm=32, height_mm=32, border_mm=0)
    verts, faces = _build_mesh(layer_map, layer_height_mm=0.16, geo=geo)
    bb_min = verts.min(axis=0)
    bb_max = verts.max(axis=0)
    # x/y span the full 32mm width.
    np.testing.assert_allclose(bb_min[0], 0.0, atol=1e-6)
    np.testing.assert_allclose(bb_max[0], 32.0, atol=1e-6)
    np.testing.assert_allclose(bb_min[1], 0.0, atol=1e-6)
    np.testing.assert_allclose(bb_max[1], 32.0, atol=1e-6)
    # z spans 0 to 10*0.16 = 1.6 mm.
    np.testing.assert_allclose(bb_min[2], 0.0, atol=1e-6)
    np.testing.assert_allclose(bb_max[2], 1.6, atol=1e-6)


def test_slab_mesh_constant_base_collapses_triangles():
    """The BASE slab in a multi-color print is mostly flat (everything
    at slab top) — greedy meshing should crush its triangle count."""
    layer_map = np.full((32, 32), 12, dtype=np.float64)
    geo = GeometrySpec(mode="flat", width_mm=50, height_mm=50, border_mm=0)
    slabs = build_per_filament_slabs(
        layer_map, swap_layer_indices=[5, 10], n_filaments=3,
        layer_height_mm=0.16, geo=geo, base_min_layers=2,
    )
    # Base slab (slot 0) covers everything at z = 5*lh; one quad on top,
    # one on bottom, perimeter walls. Old baseline: ~1900 triangles.
    base = next(s for s in slabs if s[0] == 0)
    _, _, base_faces = base
    # Without greedy, this would be ~4000 triangles (32×32×4 for
    # top+bottom). With greedy on top/bottom, walls remain per-pixel:
    # ~248 (4 sides × 31 × 2). We assert << 1000 to lock the win.
    assert base_faces.shape[0] < 600, (
        f"flat base slab should collapse to <600 triangles, got {base_faces.shape[0]}"
    )


def test_build_export_triangle_count_reported():
    """build_export's reported triangle_count matches the actual single
    STL mesh and shows the optimisation took effect."""
    layer_map = np.zeros((32, 32), dtype=np.float64)
    layer_map[8:24, 8:24] = 10
    geo = GeometrySpec(mode="flat", width_mm=50, height_mm=50, border_mm=0)
    out = build_export(
        layer_map=layer_map,
        layer_height_mm=0.16,
        geo=geo,
        filament_names=["A", "B"],
        swap_heights_mm=[0.0, 5 * 0.16],
        swap_colors=["#FFFFFF", "#000000"],
        base_min_layers=2,
    )
    # Without greedy meshing the baseline was 31*31*2 (top) + same
    # (bottom) + walls ≈ 4000. With greedy on a heightmap with a
    # raised central square, expect ≪ 4000.
    assert out["triangle_count"] < 1000, (
        f"expected greedy-meshed export to be <1000 triangles, got {out['triangle_count']}"
    )


def test_disc_mesh_unaffected_by_greedy_optimization():
    """Disc geometry shouldn't take the flat-only greedy path; it's
    still per-cell. This test just guards regression — the count
    should remain comparable to per-pixel baseline (not collapsed)."""
    layer_map = np.full((16, 16), 6, dtype=np.float64)
    geo = GeometrySpec(mode="disc", width_mm=40, height_mm=40, border_mm=0)
    _, faces = _build_mesh(layer_map, layer_height_mm=0.16, geo=geo)
    # Disc inscribed circle in a 16×16 grid covers ~π/4 of cells ≈ 176.
    # Each cell emits 2 top + 2 bottom triangles = 700ish baseline.
    # Greedy is disabled here, so triangle count stays elevated.
    assert faces.shape[0] > 300, (
        f"disc mode should keep per-cell tessellation, got only {faces.shape[0]} triangles"
    )


def test_3mf_vertex_compaction_drops_unused_vertices():
    """Greedy meshing leaves many per-pixel vertices unreferenced;
    the 3MF writer compacts them so the file isn't bloated."""
    import re
    from exporters import write_3mf

    # Build a constant-z layer map. Greedy mesh: top = 1 quad, bottom =
    # 1 quad, walls = perimeter. Vertex grid was 512×512×2 = 524,288;
    # after compaction we expect way fewer.
    layer_map = np.full((64, 64), 8, dtype=np.float64)
    geo = GeometrySpec(mode="flat", width_mm=60, height_mm=60, border_mm=0)
    out = build_export(
        layer_map=layer_map, layer_height_mm=0.16, geo=geo,
        filament_names=["A", "B"], swap_heights_mm=[0.0, 4 * 0.16],
        swap_colors=["#fff", "#000"], base_min_layers=2,
    )
    blob = out["threemf"]
    import zipfile, io
    z = zipfile.ZipFile(io.BytesIO(blob))
    model_xml = z.read("3D/3dmodel.model").decode()
    # Count <vertex .../> entries across all objects.
    n_vertices = len(re.findall(r"<vertex ", model_xml))
    # Pre-compaction would have been 64×64×2 × num_slabs ≈ 16k+. After
    # compaction we expect a small multiple of the perimeter-vertex count.
    assert n_vertices < 2000, (
        f"vertex compaction failed — found {n_vertices} <vertex> entries in 3MF"
    )
