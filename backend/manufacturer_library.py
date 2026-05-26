"""Curated manufacturer-specific filament catalog.

Each entry represents a publicly available PLA SKU from a named brand.
We capture brand, sku name, hex (taken from manufacturer marketing
swatches when published, otherwise approximated from product photos),
transmission distance (mm — Hueforge-compatible) and a coarse finish
classifier so the closest-match UI can surface both matte and gloss
variants of the same colour.

Approximate TD heuristics used when the brand doesn't publish a number:
  White / cream  : 4.5 – 6.0   (matte ≈ −0.5)
  Light pastels  : 2.5 – 3.5
  Yellow         : 1.8 – 2.2
  Orange / pink  : 1.4 – 1.8
  Red / magenta  : 1.2 – 1.5
  Green          : 1.3 – 1.7
  Blue / purple  : 1.0 – 1.4
  Browns / muted : 0.9 – 1.2
  Black / dark   : 0.7 – 0.9
  Transparent    : 8   – 12

This is a *starter* catalog. Users can extend it via the private-library
endpoints (per-user) or suggest a missing SKU via the suggestion endpoint
for moderation into the global list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class CatalogFilament:
    id: str           # stable, slug-form "brand-name"
    brand: str
    name: str
    hex: str          # "#RRGGBB"
    td: float
    finish: str       # "gloss" | "matte" | "silk" | "transparent"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "brand": self.brand,
            "name": self.name,
            "hex": self.hex.upper(),
            "td": round(self.td, 2),
            "finish": self.finish,
        }


def _f(brand: str, name: str, hex_: str, td: float, finish: str = "gloss") -> CatalogFilament:
    slug = (brand + "-" + name).lower().replace(" ", "-").replace("/", "-")
    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
    return CatalogFilament(slug, brand, name, hex_, td, finish)


# ---------------------------------------------------------------------------
# Bambu Lab — PLA Basic / Matte / Silk SKUs
# ---------------------------------------------------------------------------
BAMBU = [
    _f("Bambu Lab", "PLA Basic Jade White",       "#F4F5F0", 4.8),
    _f("Bambu Lab", "PLA Basic Bone White",       "#EAE2D0", 4.6),
    _f("Bambu Lab", "PLA Basic Black",            "#000000", 0.8),
    _f("Bambu Lab", "PLA Basic Silver",           "#A6A9AA", 1.6),
    _f("Bambu Lab", "PLA Basic Gray",             "#8E9089", 1.4),
    _f("Bambu Lab", "PLA Basic Red",              "#C12E1F", 1.3),
    _f("Bambu Lab", "PLA Basic Sunflower Yellow", "#FEC600", 1.9),
    _f("Bambu Lab", "PLA Basic Orange",           "#FF6A13", 1.5),
    _f("Bambu Lab", "PLA Basic Magenta",          "#EC008C", 1.5),
    _f("Bambu Lab", "PLA Basic Pink",             "#F55A74", 1.7),
    _f("Bambu Lab", "PLA Basic Bambu Green",      "#00AE42", 1.4),
    _f("Bambu Lab", "PLA Basic Cyan",             "#0086D6", 1.3),
    _f("Bambu Lab", "PLA Basic Blue",             "#0A2989", 1.0),
    _f("Bambu Lab", "PLA Basic Purple",           "#5E43B7", 1.1),
    _f("Bambu Lab", "PLA Basic Brown",            "#9D432C", 1.0),
    _f("Bambu Lab", "PLA Matte Ivory White",      "#FFFFFF", 4.2, "matte"),
    _f("Bambu Lab", "PLA Matte Charcoal",         "#1A1A1A", 0.7, "matte"),
    _f("Bambu Lab", "PLA Matte Lemon Yellow",     "#F7D959", 2.0, "matte"),
    _f("Bambu Lab", "PLA Matte Mandarin Orange",  "#F77F2E", 1.5, "matte"),
    _f("Bambu Lab", "PLA Matte Scarlet Red",      "#D8341A", 1.2, "matte"),
    _f("Bambu Lab", "PLA Matte Sakura Pink",      "#F2A3B8", 2.4, "matte"),
    _f("Bambu Lab", "PLA Matte Apple Green",      "#A8C04D", 1.7, "matte"),
    _f("Bambu Lab", "PLA Matte Ice Blue",         "#A6D1E4", 2.8, "matte"),
    _f("Bambu Lab", "PLA Matte Dark Blue",        "#0F2E54", 0.9, "matte"),
    _f("Bambu Lab", "PLA Silk Gold",              "#E2B53A", 1.9, "silk"),
    _f("Bambu Lab", "PLA Silk Silver",            "#C8CBC8", 1.7, "silk"),
]

# ---------------------------------------------------------------------------
# Polymaker — PolyLite (gloss) / PolyTerra (matte) / PolyMax
# ---------------------------------------------------------------------------
POLYMAKER = [
    _f("Polymaker", "PolyLite PLA White",        "#F4F4F4", 4.6),
    _f("Polymaker", "PolyLite PLA Black",        "#1C1C1C", 0.8),
    _f("Polymaker", "PolyLite PLA Red",          "#CE1F2C", 1.3),
    _f("Polymaker", "PolyLite PLA Yellow",       "#F6CB1C", 1.9),
    _f("Polymaker", "PolyLite PLA Orange",       "#F26A23", 1.4),
    _f("Polymaker", "PolyLite PLA Green",        "#28A745", 1.5),
    _f("Polymaker", "PolyLite PLA Blue",         "#1F4FA5", 1.1),
    _f("Polymaker", "PolyLite PLA Teal",         "#1AAFAA", 1.4),
    _f("Polymaker", "PolyLite PLA Pink",         "#E94B83", 1.7),
    _f("Polymaker", "PolyLite PLA Grey",         "#8C8C8C", 1.4),
    _f("Polymaker", "PolyTerra PLA Cotton White","#EFE9DE", 4.2, "matte"),
    _f("Polymaker", "PolyTerra PLA Charcoal Black","#222222", 0.7, "matte"),
    _f("Polymaker", "PolyTerra PLA Lava Red",    "#B82A2A", 1.2, "matte"),
    _f("Polymaker", "PolyTerra PLA Banana Yellow","#F2D14D", 2.0, "matte"),
    _f("Polymaker", "PolyTerra PLA Sunrise Orange","#F08442", 1.6, "matte"),
    _f("Polymaker", "PolyTerra PLA Forest Green","#2F6A45", 1.2, "matte"),
    _f("Polymaker", "PolyTerra PLA Sapphire Blue","#163A6E", 1.0, "matte"),
    _f("Polymaker", "PolyTerra PLA Lavender Purple","#9C8AC7", 1.9, "matte"),
    _f("Polymaker", "PolyTerra PLA Muted Pink",  "#E6A9B8", 2.6, "matte"),
    _f("Polymaker", "PolyTerra PLA Army Beige",  "#C7B27A", 2.2, "matte"),
    _f("Polymaker", "PolyMax PLA True White",    "#FAFAFA", 4.8),
    _f("Polymaker", "PolyMax PLA Jet Black",     "#0B0B0B", 0.7),
]

# ---------------------------------------------------------------------------
# Prusament — Prusa Research curated PLA SKUs
# ---------------------------------------------------------------------------
PRUSAMENT = [
    _f("Prusament", "PLA Vanilla White",         "#F1ECDF", 4.6),
    _f("Prusament", "PLA Galaxy Black",          "#0A0A0A", 0.7),
    _f("Prusament", "PLA Lipstick Red",          "#B12E36", 1.3),
    _f("Prusament", "PLA Prusa Orange",          "#FA6831", 1.5),
    _f("Prusament", "PLA Yellow",                "#F8C520", 1.9),
    _f("Prusament", "PLA Pineapple Yellow",      "#F4D34E", 2.1),
    _f("Prusament", "PLA Pearl Mouse",           "#9CA09F", 1.5),
    _f("Prusament", "PLA Royal Blue",            "#1A3FA0", 1.0),
    _f("Prusament", "PLA Azure Blue",            "#1F71BB", 1.2),
    _f("Prusament", "PLA Mystic Green",          "#345F40", 1.2),
    _f("Prusament", "PLA Pistachio Green",       "#A6C45B", 1.7),
    _f("Prusament", "PLA Diamond Black",         "#181818", 0.8),
    _f("Prusament", "PLA Lila Cloud Pink",       "#D8AED5", 2.5),
    _f("Prusament", "PLA Opal Green",            "#7DB098", 2.0),
]

# ---------------------------------------------------------------------------
# eSun — PLA+ gloss line plus matte PLA-Matte
# ---------------------------------------------------------------------------
ESUN = [
    _f("eSun", "PLA+ Cold White",                "#F2F2F2", 4.4),
    _f("eSun", "PLA+ Solid Black",               "#0C0C0C", 0.7),
    _f("eSun", "PLA+ Fire Engine Red",           "#D3211C", 1.3),
    _f("eSun", "PLA+ Orange",                    "#F4791F", 1.5),
    _f("eSun", "PLA+ Yellow",                    "#F8CB14", 1.9),
    _f("eSun", "PLA+ Light Blue",                "#67B3DF", 2.3),
    _f("eSun", "PLA+ Dark Blue",                 "#103A8A", 1.0),
    _f("eSun", "PLA+ Pink",                      "#E97AA0", 1.8),
    _f("eSun", "PLA+ Apple Green",               "#69B946", 1.6),
    _f("eSun", "PLA+ Olive Green",               "#6A7D34", 1.2),
    _f("eSun", "PLA+ Grey",                      "#888B8E", 1.4),
    _f("eSun", "PLA+ Brown",                     "#7A4329", 0.9),
    _f("eSun", "PLA-Matte Almond Yellow",        "#F1DA94", 2.4, "matte"),
    _f("eSun", "PLA-Matte Mint Green",           "#9BD6B7", 2.6, "matte"),
    _f("eSun", "PLA-Matte Coral Red",            "#D34B49", 1.5, "matte"),
]

# ---------------------------------------------------------------------------
# Sunlu — PLA+ value brand, matte, silk
# ---------------------------------------------------------------------------
SUNLU = [
    _f("Sunlu", "PLA+ White",                    "#F4F4F4", 4.5),
    _f("Sunlu", "PLA+ Black",                    "#0E0E0E", 0.8),
    _f("Sunlu", "PLA+ Red",                      "#CC1B26", 1.3),
    _f("Sunlu", "PLA+ Orange",                   "#F47120", 1.5),
    _f("Sunlu", "PLA+ Yellow",                   "#F4C913", 1.9),
    _f("Sunlu", "PLA+ Green",                    "#3CB14D", 1.5),
    _f("Sunlu", "PLA+ Blue",                     "#1F4DA8", 1.1),
    _f("Sunlu", "PLA+ Purple",                   "#603DA7", 1.1),
    _f("Sunlu", "PLA+ Grey",                     "#8B8C8E", 1.4),
    _f("Sunlu", "PLA+ Transparent",              "#E0EAEA", 9.5, "transparent"),
    _f("Sunlu", "PLA Matte Light Grey",          "#BFC1BE", 2.0, "matte"),
    _f("Sunlu", "PLA Matte Sand Yellow",         "#E6C77A", 2.4, "matte"),
    _f("Sunlu", "Silk PLA Gold",                 "#D6B33B", 2.0, "silk"),
    _f("Sunlu", "Silk PLA Copper",               "#B97A47", 1.5, "silk"),
]

# ---------------------------------------------------------------------------
# Overture — PLA / PLA Matte
# ---------------------------------------------------------------------------
OVERTURE = [
    _f("Overture", "PLA White",                  "#F0F0F0", 4.4),
    _f("Overture", "PLA Black",                  "#0D0D0D", 0.7),
    _f("Overture", "PLA Red",                    "#C6212A", 1.3),
    _f("Overture", "PLA Orange",                 "#F36E1B", 1.5),
    _f("Overture", "PLA Yellow",                 "#F2C81F", 1.9),
    _f("Overture", "PLA Green",                  "#2EAC4A", 1.5),
    _f("Overture", "PLA Sky Blue",               "#3BA3DB", 1.7),
    _f("Overture", "PLA Navy Blue",              "#11366E", 0.9),
    _f("Overture", "PLA Beige",                  "#D6C3A0", 3.0),
    _f("Overture", "PLA Pink",                   "#E97AA1", 1.8),
    _f("Overture", "Matte PLA Charcoal",         "#1C1C1C", 0.7, "matte"),
    _f("Overture", "Matte PLA Smoke White",      "#E9E6DE", 4.0, "matte"),
    _f("Overture", "Matte PLA Pumpkin Orange",   "#E16826", 1.4, "matte"),
    _f("Overture", "Matte PLA Olive Drab",       "#6A6B3B", 1.0, "matte"),
]

# ---------------------------------------------------------------------------
# Hatchbox — staple gloss PLA
# ---------------------------------------------------------------------------
HATCHBOX = [
    _f("Hatchbox", "PLA True White",             "#F4F4F4", 4.5),
    _f("Hatchbox", "PLA True Black",             "#0E0E0E", 0.7),
    _f("Hatchbox", "PLA True Red",               "#CD1F26", 1.3),
    _f("Hatchbox", "PLA Orange",                 "#F4751E", 1.5),
    _f("Hatchbox", "PLA Yellow",                 "#F1C512", 1.9),
    _f("Hatchbox", "PLA Green",                  "#2FAD46", 1.5),
    _f("Hatchbox", "PLA Blue",                   "#1E4FA9", 1.0),
    _f("Hatchbox", "PLA Silver",                 "#B5B7B8", 1.6),
    _f("Hatchbox", "PLA Brown",                  "#5C2F1A", 0.9),
    _f("Hatchbox", "PLA Transparent",            "#DAE7E7", 10.0, "transparent"),
]

# ---------------------------------------------------------------------------
# uJoybio3d — colour-rich budget brand
# ---------------------------------------------------------------------------
UJOYBIO3D = [
    _f("uJoybio3d", "PLA Pure White",            "#F6F6F6", 4.6),
    _f("uJoybio3d", "PLA Jet Black",             "#0B0B0B", 0.7),
    _f("uJoybio3d", "PLA Bright Red",            "#CC1F24", 1.3),
    _f("uJoybio3d", "PLA Lemon Yellow",          "#F0D33A", 2.0),
    _f("uJoybio3d", "PLA Sky Blue",              "#5DB1DD", 1.9),
    _f("uJoybio3d", "PLA Grass Green",           "#52B14B", 1.5),
    _f("uJoybio3d", "PLA Coral Pink",            "#F08B95", 2.1),
    _f("uJoybio3d", "PLA Royal Purple",          "#683AAF", 1.0),
    _f("uJoybio3d", "PLA Tangerine",             "#F47A30", 1.5),
    _f("uJoybio3d", "PLA Pearl Grey",            "#B6B6B5", 1.6),
]

# ---------------------------------------------------------------------------
# FlashForge — PLA / PLA Pro
# ---------------------------------------------------------------------------
FLASHFORGE = [
    _f("FlashForge", "PLA White",                "#F2F2F2", 4.4),
    _f("FlashForge", "PLA Black",                "#0E0E0E", 0.8),
    _f("FlashForge", "PLA Red",                  "#C92129", 1.3),
    _f("FlashForge", "PLA Orange",               "#F47422", 1.5),
    _f("FlashForge", "PLA Yellow",               "#F3CA1A", 1.9),
    _f("FlashForge", "PLA Green",                "#3FAE44", 1.5),
    _f("FlashForge", "PLA Blue",                 "#1F4FA0", 1.0),
    _f("FlashForge", "PLA Pink",                 "#EC7AA0", 1.8),
    _f("FlashForge", "PLA Pro Cool White",       "#FAFAFA", 4.8),
    _f("FlashForge", "PLA Pro Carbon Black",     "#0A0A0A", 0.7),
    _f("FlashForge", "PLA Pro Skin",             "#F0C9A8", 3.0),
]


CATALOG: List[CatalogFilament] = (
    BAMBU + POLYMAKER + PRUSAMENT + ESUN + SUNLU
    + OVERTURE + HATCHBOX + UJOYBIO3D + FLASHFORGE
)


def brands() -> List[str]:
    seen: List[str] = []
    for f in CATALOG:
        if f.brand not in seen:
            seen.append(f.brand)
    return seen


def by_id(filament_id: str) -> CatalogFilament | None:
    for f in CATALOG:
        if f.id == filament_id:
            return f
    return None
