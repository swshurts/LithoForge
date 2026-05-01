"""Photography-oriented filament library + palette suggestion.

Given an image, suggest a 6-filament palette that covers its colour
distribution well. The selection always includes White and Key (luminance
endpoints) and uses greedy forward selection in Lab space to pick 4
additional chromatic filaments that minimise the mean nearest-neighbour ΔE
from image pixels to palette."""

from __future__ import annotations

from typing import List

import numpy as np
from PIL import Image
from skimage import color as skcolor

from lithophane import Filament


# Curated filament library — tuned for photography subjects. Each entry has a
# representative hex and an estimated transmission distance in mm (higher =
# more translucent). TD values are coarse approximations of common PLA
# offerings; users can fine-tune them after the palette is suggested.
FILAMENT_LIBRARY: List[Filament] = [
    Filament("White",      "#f5f5f5", td=4.5),
    Filament("Cream",      "#f2e7c3", td=4.0),
    Filament("Skin",       "#e8b998", td=3.8),
    Filament("Yellow",     "#eab308", td=3.5),
    Filament("Orange",     "#f57f20", td=3.0),
    Filament("Red",        "#d01e32", td=2.5),
    Filament("Pink",       "#f08a9c", td=3.3),
    Filament("Magenta",    "#ec4899", td=3.0),
    Filament("Purple",     "#6d28d9", td=1.8),
    Filament("Blue",       "#1e45a8", td=2.0),
    Filament("Cyan",       "#06b6d4", td=3.0),
    Filament("Teal",       "#0f766e", td=2.2),
    Filament("Green",      "#2ea043", td=3.0),
    Filament("Olive",      "#556b1e", td=2.6),
    Filament("Brown",      "#78350f", td=1.6),
    Filament("Grey",       "#6b7280", td=2.0),
    Filament("Key",        "#111111", td=1.2),
]


def _sample_image_lab(image: Image.Image, max_samples: int = 4096) -> np.ndarray:
    """Return a (N, 3) Lab sample of the image."""
    img = image.convert("RGB")
    # Reduce size first for speed.
    img.thumbnail((256, 256))
    arr = np.asarray(img, dtype=np.float64) / 255.0
    lab = skcolor.rgb2lab(arr).reshape(-1, 3)
    if lab.shape[0] > max_samples:
        step = max(1, lab.shape[0] // max_samples)
        lab = lab[::step][:max_samples]
    return lab


def _filaments_to_lab(filaments: List[Filament]) -> np.ndarray:
    rgb = np.array([f.rgb for f in filaments])
    return skcolor.rgb2lab(rgb.reshape(-1, 1, 3)).reshape(-1, 3)


def suggest_palette(
    image: Image.Image,
    palette_size: int = 6,
    include_white: bool = True,
    include_key: bool = True,
) -> List[Filament]:
    """Greedy forward-selection of filaments from FILAMENT_LIBRARY.

    Always seeds with White and Key when requested; adds further filaments
    that most reduce the mean nearest-neighbour ΔE from image pixels to the
    current palette. Returns the selected filaments ordered bottom→top by
    luminance descending (W first, K last) which tends to give the brightest
    highlights and cleanest colour transitions when used as a print stack.
    """
    sample_lab = _sample_image_lab(image)
    library = list(FILAMENT_LIBRARY)
    library_lab = _filaments_to_lab(library)
    name_idx = {f.name: i for i, f in enumerate(library)}

    selected: List[int] = []
    if include_white:
        selected.append(name_idx["White"])
    if include_key:
        selected.append(name_idx["Key"])

    # nearest_d[i] = current minimum ΔE of sample i to selected palette
    if selected:
        d = np.linalg.norm(
            sample_lab[:, None, :] - library_lab[selected][None, :, :], axis=-1
        )
        nearest_d = d.min(axis=1)
    else:
        nearest_d = np.full(sample_lab.shape[0], 1e9)

    while len(selected) < palette_size:
        # For each candidate, what would the new mean-ΔE be if we added it?
        best_gain = -1.0
        best_idx = -1
        for cand in range(len(library)):
            if cand in selected:
                continue
            cand_d = np.linalg.norm(sample_lab - library_lab[cand], axis=-1)
            merged = np.minimum(nearest_d, cand_d)
            gain = nearest_d.mean() - merged.mean()
            if gain > best_gain:
                best_gain = gain
                best_idx = cand
        if best_idx == -1:
            break
        selected.append(best_idx)
        cand_d = np.linalg.norm(sample_lab - library_lab[best_idx], axis=-1)
        nearest_d = np.minimum(nearest_d, cand_d)

    chosen = [library[i] for i in selected]

    # Order bottom→top: White first, Key last, chromatic by descending L*.
    w = next((f for f in chosen if f.name == "White"), None)
    k = next((f for f in chosen if f.name == "Key"), None)
    middle = [f for f in chosen if f.name not in {"White", "Key"}]
    middle_lab = _filaments_to_lab(middle) if middle else np.zeros((0, 3))
    order = sorted(range(len(middle)), key=lambda i: -middle_lab[i, 0])
    middle = [middle[i] for i in order]

    result: List[Filament] = []
    if w is not None:
        result.append(w)
    result.extend(middle)
    if k is not None:
        result.append(k)
    return result
