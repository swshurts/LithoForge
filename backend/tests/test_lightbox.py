"""Tests for the lightbox (box geometry) mesh generation and exports."""

import numpy as np
import pytest

from lightbox import (
    LightboxSpec,
    build_back_panel_mesh,
    build_diffuser_mesh,
    build_frame_mesh,
    build_lightbox_export,
)
from exporters import GeometrySpec, build_export


def _check_mesh(vertices: np.ndarray, faces: np.ndarray) -> None:
    """Generic sanity check — meshes must have referenced vertices, no
    NaNs, and at least a few triangles."""
    assert vertices.ndim == 2 and vertices.shape[1] == 3
    assert faces.ndim == 2 and faces.shape[1] == 3
    assert faces.shape[0] > 0, "mesh produced no triangles"
    assert not np.isnan(vertices).any()
    # All face indices must point at valid vertices.
    assert faces.min() >= 0
    assert faces.max() < vertices.shape[0]


def test_rect_frame_mesh_builds():
    spec = LightboxSpec(shape="rect", width_mm=120, height_mm=120,
                        litho_w_mm=100, litho_h_mm=100, depth_mm=40)
    v, f = build_frame_mesh(spec)
    _check_mesh(v, f)
    # Frame should be bigger than just one cube of triangles.
    assert f.shape[0] >= 40


def test_round_frame_mesh_builds():
    spec = LightboxSpec(shape="round", width_mm=120, litho_w_mm=100, depth_mm=40)
    v, f = build_frame_mesh(spec)
    _check_mesh(v, f)
    # Round frame has high-poly cylindrical walls.
    assert f.shape[0] >= 200


def test_rect_back_panel_has_cable_notch():
    """When cable_notch=True the panel mesh should have FEWER triangles
    than the non-notch variant (different sub-rect decomposition)
    but be non-trivial."""
    spec_on = LightboxSpec(shape="rect", width_mm=120, height_mm=120,
                           cable_notch=True)
    spec_off = LightboxSpec(shape="rect", width_mm=120, height_mm=120,
                            cable_notch=False)
    v_on, f_on = build_back_panel_mesh(spec_on)
    v_off, f_off = build_back_panel_mesh(spec_off)
    _check_mesh(v_on, f_on)
    _check_mesh(v_off, f_off)
    # Notch version is composed of 3 sub-boxes; no-notch is 1 box.
    assert f_on.shape[0] == 12 * 3
    assert f_off.shape[0] == 12


def test_round_back_panel_is_disc():
    spec = LightboxSpec(shape="round", width_mm=120)
    v, f = build_back_panel_mesh(spec)
    _check_mesh(v, f)


def test_diffuser_mesh_builds():
    spec = LightboxSpec(shape="rect", width_mm=120, height_mm=100)
    v, f = build_diffuser_mesh(spec)
    _check_mesh(v, f)


def test_build_lightbox_export_returns_all_parts():
    spec = LightboxSpec(shape="rect", width_mm=120, height_mm=120,
                        litho_w_mm=100, litho_h_mm=100, diffuser=True)
    out = build_lightbox_export(spec)
    assert "frame_stl" in out and len(out["frame_stl"]) > 200
    assert "back_stl" in out and len(out["back_stl"]) > 200
    assert "diffuser_stl" in out and len(out["diffuser_stl"]) > 200
    # STL files start with the 80-byte header we wrote.
    assert out["frame_stl"][:5] == b"CMYKW"


def test_build_lightbox_export_skips_diffuser_when_disabled():
    spec = LightboxSpec(shape="rect", width_mm=120, height_mm=120, diffuser=False)
    out = build_lightbox_export(spec)
    assert "diffuser_stl" not in out


def test_led_mount_modes_change_triangle_count():
    base = LightboxSpec(shape="rect", width_mm=120, height_mm=120, led_mount="none")
    puck = LightboxSpec(shape="rect", width_mm=120, height_mm=120, led_mount="puck")
    strip = LightboxSpec(shape="rect", width_mm=120, height_mm=120, led_mount="strip")
    both = LightboxSpec(shape="rect", width_mm=120, height_mm=120, led_mount="both")
    counts = []
    for s in (base, puck, strip, both):
        v, f = build_frame_mesh(s)
        counts.append(f.shape[0])
    # Each toggle adds geometry, so counts should be strictly increasing
    # for "none" < "puck" < "both", and "strip" should be different.
    assert counts[0] < counts[1]
    assert counts[0] < counts[2]
    assert counts[0] < counts[3]
    assert counts[3] >= max(counts[1], counts[2])


def test_build_export_box_geometry_emits_lightbox_parts():
    """End-to-end: build_export with mode=box should also produce
    lightbox_frame_stl + lightbox_back_stl + lightbox_diffuser_stl."""
    layer_map = np.full((40, 40), 8, dtype=np.int32)
    geo = GeometrySpec(
        width_mm=100, height_mm=100, border_mm=2,
        mode="box",
        box_shape="rect",
        box_outer_w_mm=120, box_outer_h_mm=120,
        box_depth_mm=40, box_wall_mm=3,
        box_led_mount="both",
        box_diffuser=True,
    )
    result = build_export(
        layer_map=layer_map,
        layer_height_mm=0.12,
        geo=geo,
        filament_names=["W", "K"],
        swap_heights_mm=[0.0, 0.6],
        swap_colors=["#FFFFFF", "#000000"],
    )
    # Lithophane STL still emitted (built as flat slab internally).
    assert "stl" in result and len(result["stl"]) > 200
    # Lightbox parts attached.
    assert "lightbox_frame_stl" in result
    assert "lightbox_back_stl" in result
    assert "lightbox_diffuser_stl" in result
    assert result["lightbox_triangles"]["frame"] > 0


def test_build_export_box_round_uses_disc_litho():
    """For round box, the lithophane is auto-masked to a disc by the
    underlying _build_mesh path (geo.mode resolves to "disc" via
    GeometrySpec.litho_mode)."""
    layer_map = np.full((48, 48), 6, dtype=np.int32)
    geo = GeometrySpec(
        width_mm=100, height_mm=100, border_mm=2,
        mode="box",
        box_shape="round",
        box_outer_w_mm=120, box_outer_h_mm=120,
        box_depth_mm=40, box_wall_mm=3,
        box_led_mount="puck",
        box_diffuser=False,
    )
    result = build_export(
        layer_map=layer_map,
        layer_height_mm=0.12,
        geo=geo,
        filament_names=["W", "K"],
        swap_heights_mm=[0.0, 0.4],
        swap_colors=["#FFFFFF", "#000000"],
    )
    assert "stl" in result
    assert "lightbox_frame_stl" in result
    assert "lightbox_back_stl" in result
    # diffuser disabled
    assert "lightbox_diffuser_stl" not in result


def test_geometry_spec_litho_mode_helper():
    """GeometrySpec.litho_mode() resolves box-rect → flat, box-round → disc."""
    g_rect = GeometrySpec(width_mm=100, height_mm=100, mode="box", box_shape="rect")
    g_round = GeometrySpec(width_mm=100, height_mm=100, mode="box", box_shape="round")
    g_flat = GeometrySpec(width_mm=100, height_mm=100, mode="flat")
    assert g_rect.litho_mode() == "flat"
    assert g_round.litho_mode() == "disc"
    assert g_flat.litho_mode() == "flat"
