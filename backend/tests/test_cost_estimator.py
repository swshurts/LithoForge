"""Tests for the print-time + filament-cost estimator."""

import numpy as np

from cost_estimator import estimate_print_costs
from lithophane import DEFAULT_FILAMENTS


def test_basic_flat_estimate_nonzero():
    layer_map = np.full((40, 40), 8, dtype=np.int32)
    fils = DEFAULT_FILAMENTS[:3]
    out = estimate_print_costs(
        layer_map=layer_map,
        layer_height_mm=0.12,
        swap_layer_indices=[3, 6],
        filaments=fils,
        usable_width_mm=100.0,
        usable_height_mm=100.0,
    )
    assert out.total_time_minutes > 0
    assert out.total_weight_g > 0
    assert out.total_length_mm > 0
    assert out.total_cost_usd > 0
    # Per-filament sums (approximately) match totals.
    pf_volume = sum(f.volume_mm3 for f in out.per_filament)
    assert abs(pf_volume - out.total_volume_mm3) < 1e-6


def test_estimate_scales_with_thickness():
    """Doubling layer count → doubles weight, length, cost."""
    fils = DEFAULT_FILAMENTS[:2]
    base = estimate_print_costs(
        layer_map=np.full((40, 40), 4, dtype=np.int32),
        layer_height_mm=0.12,
        swap_layer_indices=[2],
        filaments=fils,
        usable_width_mm=100.0,
        usable_height_mm=100.0,
    )
    double = estimate_print_costs(
        layer_map=np.full((40, 40), 8, dtype=np.int32),
        layer_height_mm=0.12,
        swap_layer_indices=[4],
        filaments=fils,
        usable_width_mm=100.0,
        usable_height_mm=100.0,
    )
    # Weight should roughly double (extrusion volume scales linearly).
    assert double.total_weight_g > 1.7 * base.total_weight_g
    assert double.total_weight_g < 2.3 * base.total_weight_g


def test_disc_estimate_is_less_than_flat():
    """A circular footprint uses ~π/4 the area of an equivalent square,
    so the disc estimate should be ~78% of the flat one."""
    fils = DEFAULT_FILAMENTS[:2]
    layer_map = np.full((40, 40), 6, dtype=np.int32)
    flat = estimate_print_costs(
        layer_map=layer_map.copy(), layer_height_mm=0.12,
        swap_layer_indices=[3], filaments=fils,
        usable_width_mm=100.0, usable_height_mm=100.0, shape="flat",
    )
    disc = estimate_print_costs(
        layer_map=layer_map.copy(), layer_height_mm=0.12,
        swap_layer_indices=[3], filaments=fils,
        usable_width_mm=100.0, usable_height_mm=100.0, shape="disc",
    )
    # Disc area = π/4 of square (0.785). Allow slack for the discrete mask.
    ratio = disc.total_volume_mm3 / flat.total_volume_mm3
    assert 0.7 < ratio < 0.85


def test_to_dict_serialises():
    fils = DEFAULT_FILAMENTS[:2]
    out = estimate_print_costs(
        layer_map=np.full((20, 20), 3, dtype=np.int32),
        layer_height_mm=0.12,
        swap_layer_indices=[1],
        filaments=fils,
        usable_width_mm=80.0,
        usable_height_mm=80.0,
    )
    d = out.to_dict()
    assert "total_time_minutes" in d
    assert "total_cost_usd" in d
    assert isinstance(d["per_filament"], list)
    assert d["per_filament"][0]["name"]
    assert d["per_filament"][0]["weight_g"] >= 0


def test_price_per_kg_brand_tier():
    """Premium brands cost more than budget brands for the same material."""
    from cost_estimator import price_per_kg_usd
    bambu = price_per_kg_usd("PLA", "Bambu Lab", "gloss")
    polymaker = price_per_kg_usd("PLA", "Polymaker", "silk")
    budget = price_per_kg_usd("PLA", "Generic", "gloss")
    assert polymaker > bambu > budget
    # PETG > PLA at same brand tier.
    assert price_per_kg_usd("PETG", "Bambu Lab", "gloss") > bambu


def test_estimate_uses_explicit_price_when_present():
    """If filament has price_per_kg_usd attribute, estimator must honour it
    over the material/brand defaults (powers the swap simulator)."""
    from types import SimpleNamespace
    cheap = [
        SimpleNamespace(name="Cheap White", hex="#FFFFFF", td=2.0,
                        material="PLA", price_per_kg_usd=10.0),
        SimpleNamespace(name="Cheap Black", hex="#000000", td=0.7,
                        material="PLA", price_per_kg_usd=10.0),
    ]
    pricey = [
        SimpleNamespace(name="Premium White", hex="#FFFFFF", td=2.0,
                        material="PLA", price_per_kg_usd=80.0),
        SimpleNamespace(name="Premium Black", hex="#000000", td=0.7,
                        material="PLA", price_per_kg_usd=80.0),
    ]
    common = dict(
        layer_map=np.full((20, 20), 4, dtype=np.int32),
        layer_height_mm=0.12, swap_layer_indices=[2],
        usable_width_mm=80.0, usable_height_mm=80.0,
    )
    out_cheap = estimate_print_costs(filaments=cheap, **common)
    out_pricey = estimate_print_costs(filaments=pricey, **common)
    # Pricey filaments cost ~8× more for the same volume.
    assert out_pricey.total_cost_usd > 6 * out_cheap.total_cost_usd
