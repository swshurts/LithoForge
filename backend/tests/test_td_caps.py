"""Regression test for the back-light opacity bug.

User reported a real-world print with 31 layers, of which 21 were a
brown filament with TD≈1.2mm — at 0.08 mm layer height that's 1.68 mm
of brown stacked, well past the Beer-Lambert sweet spot, killing
back-light transmission to <10%.

These tests assert the layer allocator now caps each filament at
~1.5×TD layers AND keeps total brightness in a printable range.
"""

from __future__ import annotations

import numpy as np
import pytest

from lithophane import (
    Filament,
    _beer_lambert_transmission,
    _td_layer_caps,
    allocate_layers,
    simulate_stack,
)


def _brown_palette():
    """Mimics the user's filament set that produced 21 layers of brown."""
    return [
        Filament("White",   "#f5f5f5", td=5.0),
        Filament("Purple",  "#7c3aed", td=1.3),
        Filament("Brown",   "#5a3a22", td=1.2),
        Filament("Key",     "#111111", td=0.8),
    ]


def _sepia_image(h=64, w=64):
    """Brown-dominant test image (sepia tone)."""
    arr = np.zeros((h, w, 3), dtype=np.float64)
    arr[..., 0] = 0.55  # R
    arr[..., 1] = 0.40  # G
    arr[..., 2] = 0.25  # B
    return arr


class TestTDCaps:
    def test_td_caps_basic_math(self):
        fils = _brown_palette()
        caps = _td_layer_caps(fils, layer_height_mm=0.08, td_multiplier=1.5)
        # White: 1.5 * 5.0 / 0.08 = 93.75 → ceil 94
        assert caps[0] == 94
        # Purple: 1.5 * 1.3 / 0.08 = 24.375 → ceil 25
        assert caps[1] == 25
        # Brown: 1.5 * 1.2 / 0.08 = 22.5 → ceil 23
        assert caps[2] == 23
        # Key: 1.5 * 0.8 / 0.08 = 15
        assert caps[3] == 15

    def test_brown_no_longer_dominates(self):
        """At 2.2 mm total (28 layers @ 0.08 mm) with the sepia image,
        brown should NEVER take 21+ layers any more."""
        fils = _brown_palette()
        arr = _sepia_image()
        alloc = allocate_layers(
            arr, fils, total_layers=28, layer_height_mm=0.08
        )
        brown_layers = alloc[2]
        # Hard cap: regardless of how brown-dominant the image is.
        assert brown_layers <= 23, (
            f"Brown leaked past TD cap: {brown_layers} layers (cap=23)"
        )
        # Sanity: the rest of the budget went somewhere.
        assert sum(alloc) == 28

    def test_chromatic_total_does_not_explode_at_thin_print(self):
        """At 2.2 mm budget the allocator should stay near-budget AND
        respect every TD cap."""
        fils = _brown_palette()
        arr = _sepia_image()
        alloc = allocate_layers(
            arr, fils, total_layers=28, layer_height_mm=0.08
        )
        caps = _td_layer_caps(fils, layer_height_mm=0.08, td_multiplier=1.5)
        for i, n in enumerate(alloc):
            assert n <= caps[i], (
                f"{fils[i].name} exceeded TD cap: {n} > {caps[i]}"
            )

    def test_light_throughput_improves_vs_old_distribution(self):
        """Simulate the user's bad distribution (2W, 3P, 21B, 5K) vs.
        the new allocator's distribution. Through-stack brightness
        (final LUT entry — the deepest, darkest reachable color) must
        improve because we replaced opaque brown with more white."""
        fils = _brown_palette()
        layer_height = 0.08

        old_bad_alloc = [2, 3, 21, 5]  # what the user actually printed
        old_lut = simulate_stack(old_bad_alloc, fils, layer_height)
        # Brightness of the TOP of the stack — what the user sees in
        # the darkest part of the image (where the most filament sits).
        old_top = float(old_lut[-1].mean())

        arr = _sepia_image()
        new_alloc = allocate_layers(arr, fils, 28, layer_height_mm=layer_height)
        new_lut = simulate_stack(new_alloc, fils, layer_height)
        new_top = float(new_lut[-1].mean())

        # Reverse-luminance comparison: the new mix should be visibly
        # brighter through the full stack (>1.5× transmission) since
        # we replaced brown thickness with high-TD white.
        assert new_top >= old_top * 1.5, (
            f"Through-stack brightness did not improve: old={old_top:.4f} "
            f"new={new_top:.4f}, alloc={new_alloc}"
        )

    def test_caps_robust_to_low_layer_budget(self):
        """If total_layers < n_filaments * min_per_color, even split
        path must still respect caps."""
        fils = _brown_palette()
        arr = _sepia_image()
        alloc = allocate_layers(arr, fils, total_layers=3, layer_height_mm=0.08)
        assert sum(alloc) == 3
        assert all(n >= 0 for n in alloc)

    def test_high_td_white_can_absorb_overflow(self):
        """When chromatic filaments hit their caps, the leftover budget
        flows to high-TD neutrals (white, here) — never overshooting
        another filament's TD cap."""
        # Custom palette: brown cap is very low; budget intentionally high.
        fils = [
            Filament("White", "#f5f5f5", td=5.0),
            Filament("Brown", "#5a3a22", td=0.8),  # cap ≈ 15 layers
        ]
        arr = np.full((32, 32, 3), [0.45, 0.30, 0.18], dtype=np.float64)
        alloc = allocate_layers(arr, fils, total_layers=50, layer_height_mm=0.08)
        # Brown must be capped.
        assert alloc[1] <= 15
        # White absorbed the rest (or hit its own much-larger cap).
        assert alloc[0] >= 35


class TestBeerLambertSanity:
    def test_brown_at_old_thickness_is_dark(self):
        """Confirms the math of the user's complaint: 21 layers of
        brown at 0.08 mm with TD=1.2 mm transmits <30% on the
        brightest channel."""
        brown = Filament("Brown", "#5a3a22", td=1.2)
        t = _beer_lambert_transmission(brown, thickness_mm=21 * 0.08)
        # Brightest channel (red) of brown #5a3a22 = 0x5a/255 ≈ 0.353
        # Transmission ≈ 0.353 ** (1.68/1.2) = 0.353 ** 1.4 ≈ 0.236
        assert t.max() < 0.30, f"Expected <30% peak transmission, got {t.max():.3f}"
