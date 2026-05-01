"""CMYKW Lithophane optimizer.

Converts a photograph into a per-pixel layer height-map using Beer-Lambert
filament transmission modelling and ΔE (CIE76) nearest-neighbour matching
in CIE Lab colour space.

Pipeline
--------
1. Convert target image to sRGB float, then to Lab.
2. Build a stack of CMYKW filaments (user-configurable hex + Transmission
   Distance per channel). The stack order (bottom→top) is fixed per job and
   max_swaps+1 filaments are used.
3. Allocate `total_layers` across the chosen filaments using a histogram-
   based heuristic that reflects how much "presence" of each colour the
   image needs.
4. For each discrete height 0..total_layers compute the simulated light
   output using Beer-Lambert: L_out = L_in * exp(-thickness / TD) per
   channel. This produces an RGB look-up table (LUT).
5. For every pixel pick the LUT entry with the smallest ΔE against the
   target. That index is the printed height for that pixel (in layers).
6. Return the layer map, rendered preview, colour-swap heights, and stats.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image
from skimage import color as skcolor


# ---------------------------------------------------------------------------
# Filament model
# ---------------------------------------------------------------------------

@dataclass
class Filament:
    """Filament description used by the optimizer."""

    name: str          # e.g. "Cyan"
    hex: str           # "#06b6d4"
    td: float          # transmission distance in mm (higher => more translucent)

    @property
    def rgb(self) -> np.ndarray:
        h = self.hex.lstrip("#")
        return np.array(
            [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)],
            dtype=np.float64,
        )


# Printing order: bottom of the print (first layer, closest to the build
# plate — the side facing the back-light) to top (the side facing the
# viewer). Hueforge-style CMYKW lithophanes put W at the base so thin
# regions stay bright, then Y → M → C add colour, and K caps only the
# thickest, darkest regions.
DEFAULT_FILAMENTS: List[Filament] = [
    Filament("White",   "#f5f5f5", td=4.5),
    Filament("Yellow",  "#eab308", td=3.5),
    Filament("Magenta", "#ec4899", td=3.0),
    Filament("Cyan",    "#06b6d4", td=3.0),
    Filament("Key",     "#111111", td=1.2),
]


# ---------------------------------------------------------------------------
# Beer-Lambert stack simulation
# ---------------------------------------------------------------------------

def _beer_lambert_transmission(filament: Filament, thickness_mm: float) -> np.ndarray:
    """Per-channel RGB transmittance (0..1) through `thickness_mm` of filament.

    Uses the standard photographic-filament approximation
        T_channel(t) = rgb_channel ** (t / TD)
    where TD is the transmission distance in mm at which the filament reaches
    its characteristic colour. This naturally reproduces subtractive colour
    mixing (cyan attenuates R, magenta attenuates G, yellow attenuates B) and
    keeps each channel independent."""
    rgb = np.clip(filament.rgb, 0.01, 1.0)  # avoid log(0)
    td = max(filament.td, 0.05)
    return rgb ** (thickness_mm / td)


def simulate_stack(
    layer_allocation: List[int],
    filaments: List[Filament],
    layer_height_mm: float,
) -> np.ndarray:
    """Return the RGB LUT (shape: [total_layers+1, 3]) of light transmitted
    through stacked layers from bottom up to each layer index.

    layer_allocation[i] = number of layers of filaments[i] (bottom to top).
    LUT[k] is the colour seen when the printed height is k layers.
    """
    total = sum(layer_allocation)
    lut = np.ones((total + 1, 3), dtype=np.float64)  # start with white light
    current = np.ones(3, dtype=np.float64)
    idx = 0
    for fil, n_layers in zip(filaments, layer_allocation):
        t_per_layer = _beer_lambert_transmission(fil, layer_height_mm)
        for _ in range(n_layers):
            current = current * t_per_layer
            idx += 1
            lut[idx] = current
    return lut


# ---------------------------------------------------------------------------
# Layer allocation heuristic
# ---------------------------------------------------------------------------

def allocate_layers(
    image_rgb: np.ndarray,
    filaments: List[Filament],
    total_layers: int,
    min_per_color: int = 1,
) -> List[int]:
    """Heuristically distribute `total_layers` across the provided filaments.

    We look at how much of the image is "served" best by each filament
    (nearest filament colour in Lab) and allocate proportionally, ensuring
    each filament gets at least `min_per_color` layers.
    """
    n = len(filaments)
    if n == 0:
        return []
    if n * min_per_color >= total_layers:
        # Not enough room, distribute evenly.
        base = total_layers // n
        rem = total_layers - base * n
        alloc = [base] * n
        for i in range(rem):
            alloc[i] += 1
        return alloc

    # Nearest-filament histogram in Lab.
    img_lab = skcolor.rgb2lab(image_rgb.reshape(-1, 1, 3)).reshape(-1, 3)
    fil_rgb = np.array([f.rgb for f in filaments])
    fil_lab = skcolor.rgb2lab(fil_rgb.reshape(-1, 1, 3)).reshape(-1, 3)

    # sample for speed
    sample = img_lab[:: max(1, len(img_lab) // 20000)]
    d = np.linalg.norm(sample[:, None, :] - fil_lab[None, :, :], axis=-1)
    nearest = np.argmin(d, axis=1)
    counts = np.bincount(nearest, minlength=n).astype(np.float64)

    # Ensure at least some presence for visual thickness (especially W/K base).
    counts = counts + counts.sum() * 0.05

    remaining = total_layers - n * min_per_color
    raw = counts / counts.sum() * remaining
    alloc = [min_per_color + int(math.floor(x)) for x in raw]

    # distribute rounding errors
    deficit = total_layers - sum(alloc)
    fracs = [x - math.floor(x) for x in raw]
    order = np.argsort(fracs)[::-1]
    i = 0
    while deficit > 0:
        alloc[order[i % n]] += 1
        deficit -= 1
        i += 1
    return alloc


# ---------------------------------------------------------------------------
# Main optimization
# ---------------------------------------------------------------------------

@dataclass
class OptimizeResult:
    layer_map: np.ndarray          # int array (H, W) of layer heights 0..total_layers
    rendered_rgb: np.ndarray       # float (H, W, 3) simulated output
    lut: np.ndarray                # (total_layers+1, 3) float
    layer_allocation: List[int]
    filaments: List[Filament]
    total_layers: int
    layer_height_mm: float
    delta_e_mean: float
    delta_e_p95: float
    swap_heights_mm: List[float]   # Z heights at which colour changes
    swap_colors: List[str]         # hex of the colour active *above* the swap


def _evaluate_order(
    arr: np.ndarray,
    target_lab: np.ndarray,
    order: List[Filament],
    total_layers: int,
    layer_height_mm: float,
) -> Tuple[float, np.ndarray, np.ndarray, List[int], np.ndarray]:
    """Build LUT for `order` and match every pixel. Returns
    (mean_delta_e, layer_map_flat, min_d_flat, allocation, lut_clipped)."""
    allocation = allocate_layers(arr, order, total_layers)
    lut = simulate_stack(allocation, order, layer_height_mm)
    lut_clipped = np.clip(lut, 0.0, 1.0)
    lut_lab = skcolor.rgb2lab(lut_clipped.reshape(-1, 1, 3)).reshape(-1, 3)

    flat = target_lab.reshape(-1, 3)
    chunk = 16384
    layer_map_flat = np.empty(flat.shape[0], dtype=np.int32)
    min_d_flat = np.empty(flat.shape[0], dtype=np.float64)
    for start in range(0, flat.shape[0], chunk):
        end = min(start + chunk, flat.shape[0])
        d = np.linalg.norm(
            flat[start:end, None, :] - lut_lab[None, :, :], axis=-1
        )
        idx = np.argmin(d, axis=1)
        layer_map_flat[start:end] = idx
        min_d_flat[start:end] = d[np.arange(end - start), idx]
    return float(min_d_flat.mean()), layer_map_flat, min_d_flat, allocation, lut_clipped


# Orderings of the CMYKW palette to try. Bottom ↦ Top. Thin regions show the
# *first* entry (closest to the back-light), so we always start with W or K
# to bracket the luminance extremes. Between them we permute C/M/Y to cover
# the common gamut paths.
_CANDIDATE_ORDERS = [
    ("White",   "Yellow",  "Magenta", "Cyan",    "Key"),
    ("White",   "Yellow",  "Cyan",    "Magenta", "Key"),
    ("White",   "Cyan",    "Magenta", "Yellow",  "Key"),
    ("White",   "Magenta", "Yellow",  "Cyan",    "Key"),
    ("White",   "Cyan",    "Yellow",  "Magenta", "Key"),
    ("Key",     "Cyan",    "Magenta", "Yellow",  "White"),
]


def _reorder_by_names(filaments: List[Filament], names: Tuple[str, ...]) -> List[Filament]:
    """Return filaments reordered by `names` tuple. Filaments not matched by
    name are preserved in the order they appear."""
    by_name = {f.name: f for f in filaments}
    ordered: List[Filament] = []
    used = set()
    for n in names:
        if n in by_name:
            ordered.append(by_name[n])
            used.add(n)
    for f in filaments:
        if f.name not in used:
            ordered.append(f)
    return ordered


def optimize(
    image: Image.Image,
    filaments: List[Filament],
    layer_height_mm: float,
    total_thickness_mm: float,
    max_swaps: int,
    max_dimension_px: int = 512,
) -> OptimizeResult:
    """Run the full CMYKW lithophane optimization.

    Tries several physically-plausible stack orderings and keeps the one with
    the smallest mean ΔE. For custom palettes (filaments whose names don't
    match CMYKW) only the user-supplied order is evaluated."""

    # Down-sample for speed while preserving aspect.
    img = image.convert("RGB")
    w, h = img.size
    scale = max(w, h) / max_dimension_px
    if scale > 1:
        img = img.resize(
            (max(1, int(w / scale)), max(1, int(h / scale))), Image.LANCZOS
        )
    arr = np.asarray(img, dtype=np.float64) / 255.0  # (H, W, 3)
    target_lab = skcolor.rgb2lab(arr)

    # Constrain filaments to max_swaps+1.
    n_filaments = min(len(filaments), max_swaps + 1)
    base_palette = filaments[:n_filaments]
    total_layers = max(1, int(round(total_thickness_mm / layer_height_mm)))

    # Build candidate orderings. Always include the user-supplied order.
    known_names = {"White", "Yellow", "Magenta", "Cyan", "Key"}
    names_in_palette = {f.name for f in base_palette}
    candidates: List[List[Filament]] = [list(base_palette)]
    if names_in_palette.issubset(known_names) and len(base_palette) >= 2:
        for order_names in _CANDIDATE_ORDERS:
            cand = _reorder_by_names(
                base_palette, tuple(n for n in order_names if n in names_in_palette)
            )
            if len(cand) == len(base_palette) and cand != candidates[0]:
                candidates.append(cand)

    best = None  # (mean_de, order, layer_map_flat, min_d_flat, allocation, lut)
    for order in candidates:
        mean_de, lm_flat, min_d, alloc, lut_clipped = _evaluate_order(
            arr, target_lab, order, total_layers, layer_height_mm
        )
        if best is None or mean_de < best[0]:
            best = (mean_de, order, lm_flat, min_d, alloc, lut_clipped)

    _, used_filaments, layer_map_flat, min_d_flat, allocation, lut_clipped = best
    layer_map = layer_map_flat.reshape(arr.shape[:2]).astype(np.int32)
    rendered = lut_clipped[layer_map_flat].reshape(arr.shape)

    # Swap heights (Z at which filament changes, from bottom).
    swap_heights: List[float] = []
    swap_colors: List[str] = []
    z = 0.0
    for fil, nlayers in zip(used_filaments, allocation):
        swap_heights.append(round(z, 4))
        swap_colors.append(fil.hex)
        z += nlayers * layer_height_mm

    return OptimizeResult(
        layer_map=layer_map,
        rendered_rgb=rendered,
        lut=lut_clipped,
        layer_allocation=allocation,
        filaments=used_filaments,
        total_layers=total_layers,
        layer_height_mm=layer_height_mm,
        delta_e_mean=float(min_d_flat.mean()),
        delta_e_p95=float(np.percentile(min_d_flat, 95)),
        swap_heights_mm=swap_heights,
        swap_colors=swap_colors,
    )


# ---------------------------------------------------------------------------
# Preview PNG helper
# ---------------------------------------------------------------------------

def rendered_to_png_bytes(rendered_rgb: np.ndarray) -> bytes:
    arr = np.clip(rendered_rgb * 255.0, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def layer_map_to_png_bytes(layer_map: np.ndarray, total_layers: int) -> bytes:
    """Visualize the heightmap as a grey-scale image (brighter = thicker)."""
    arr = (layer_map.astype(np.float64) / max(1, total_layers) * 255.0).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="L").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
