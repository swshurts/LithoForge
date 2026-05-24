"""Printer profile catalog.

The catalog is keyed by `printer_id` and organized by SLICER FAMILY (the
slicer determines the 3MF dialect + layer-change G-code template, so
that's the right primary axis).

Each profile carries:
  • bed_x_mm / bed_y_mm — build-plate size (for compatibility warnings)
  • max_z_mm           — Z height (rarely a limit for lithophanes)
  • default_layer_height_mm
  • multi_tool         — True for AMS / MMU / multi-extruder systems.
                         Multi-tool printers receive `T<n>` tool-change
                         commands instead of `M600` pauses.
  • slicer_family      — 'orca' | 'prusa' | 'super' | 'cura' | 'marlin'
  • supported_formats  — subset of {"stl", "3mf", "swaps"}. Some printers
                         only really make sense with 3MF (Flashforge's
                         Orca fork hard-relies on .gcode.3mf).
"""

from __future__ import annotations

from typing import Dict, List, Literal, TypedDict


class PrinterProfile(TypedDict):
    id: str
    name: str
    manufacturer: str
    slicer_family: Literal["orca", "prusa", "super", "cura", "marlin"]
    bed_x_mm: int
    bed_y_mm: int
    max_z_mm: int
    default_layer_height_mm: float
    multi_tool: bool
    supported_formats: List[str]
    notes: str


PRINTER_PROFILES: Dict[str, PrinterProfile] = {
    # ------ OrcaSlicer family (Bambu Studio, OrcaSlicer-Flashforge, etc.) ------
    "generic_orca": {
        "id": "generic_orca",
        "name": "Generic FDM (OrcaSlicer)",
        "manufacturer": "Generic",
        "slicer_family": "orca",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 250,
        "default_layer_height_mm": 0.12,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Catch-all profile for any printer using OrcaSlicer.",
    },
    "bambu_a1_mini": {
        "id": "bambu_a1_mini",
        "name": "Bambu A1 mini",
        "manufacturer": "Bambu Lab",
        "slicer_family": "orca",
        "bed_x_mm": 180,
        "bed_y_mm": 180,
        "max_z_mm": 180,
        "default_layer_height_mm": 0.12,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Single-extruder. AMS lite optional — assumes manual swaps.",
    },
    "bambu_a1": {
        "id": "bambu_a1",
        "name": "Bambu A1 (with AMS lite)",
        "manufacturer": "Bambu Lab",
        "slicer_family": "orca",
        "bed_x_mm": 256,
        "bed_y_mm": 256,
        "max_z_mm": 256,
        "default_layer_height_mm": 0.12,
        "multi_tool": True,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "AMS lite (4 spools). Tool changes via T0–T3, no M600.",
    },
    "bambu_p1s": {
        "id": "bambu_p1s",
        "name": "Bambu P1S (with AMS)",
        "manufacturer": "Bambu Lab",
        "slicer_family": "orca",
        "bed_x_mm": 256,
        "bed_y_mm": 256,
        "max_z_mm": 256,
        "default_layer_height_mm": 0.12,
        "multi_tool": True,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "AMS-equipped. Tool changes via T0–T3.",
    },
    "bambu_x1c": {
        "id": "bambu_x1c",
        "name": "Bambu X1C (with AMS)",
        "manufacturer": "Bambu Lab",
        "slicer_family": "orca",
        "bed_x_mm": 256,
        "bed_y_mm": 256,
        "max_z_mm": 256,
        "default_layer_height_mm": 0.12,
        "multi_tool": True,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "AMS-equipped flagship. Tool changes via T0–T3.",
    },
    "sovol_sv07": {
        "id": "sovol_sv07",
        "name": "Sovol SV07",
        "manufacturer": "Sovol",
        "slicer_family": "orca",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 250,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Klipper-based, runs OrcaSlicer. Manual filament swaps.",
    },
    "sovol_sv08": {
        "id": "sovol_sv08",
        "name": "Sovol SV08",
        "manufacturer": "Sovol",
        "slicer_family": "orca",
        "bed_x_mm": 350,
        "bed_y_mm": 350,
        "max_z_mm": 345,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Voron-style 350mm cube, runs OrcaSlicer.",
    },
    "elegoo_neptune4": {
        "id": "elegoo_neptune4",
        "name": "Elegoo Neptune 4 / 4 Pro",
        "manufacturer": "Elegoo",
        "slicer_family": "orca",
        "bed_x_mm": 225,
        "bed_y_mm": 225,
        "max_z_mm": 265,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "OrcaSlicer-Elegoo. Manual filament swaps.",
    },
    "elegoo_centauri": {
        "id": "elegoo_centauri",
        "name": "Elegoo Centauri Carbon",
        "manufacturer": "Elegoo",
        "slicer_family": "orca",
        "bed_x_mm": 256,
        "bed_y_mm": 256,
        "max_z_mm": 256,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "OrcaSlicer-Elegoo. Manual swaps via M600.",
    },
    "anycubic_kobra2": {
        "id": "anycubic_kobra2",
        "name": "Anycubic Kobra 2 Pro/Plus",
        "manufacturer": "Anycubic",
        "slicer_family": "orca",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 250,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Runs OrcaSlicer fork. Manual swaps via M600.",
    },
    "creality_k1": {
        "id": "creality_k1",
        "name": "Creality K1 / K1 Max",
        "manufacturer": "Creality",
        "slicer_family": "orca",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 250,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Klipper-based, OrcaSlicer-Creality fork.",
    },
    # ------ Flashforge family (Orca-Flashforge — 3MF only is the realistic path)
    "flashforge_ad5m": {
        "id": "flashforge_ad5m",
        "name": "Flashforge Adventurer 5M / 5M Pro",
        "manufacturer": "Flashforge",
        "slicer_family": "orca",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 220,
        "default_layer_height_mm": 0.16,
        "multi_tool": False,
        "supported_formats": ["3mf"],
        "notes": "Orca-Flashforge fork. Use the 3MF — the printer expects "
                 "the project format, not raw STL+swap notes.",
    },
    # ------ PrusaSlicer / SuperSlicer family ------
    "prusa_mk4": {
        "id": "prusa_mk4",
        "name": "Prusa MK4 / MK4S",
        "manufacturer": "Prusa Research",
        "slicer_family": "prusa",
        "bed_x_mm": 250,
        "bed_y_mm": 210,
        "max_z_mm": 220,
        "default_layer_height_mm": 0.15,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Single-extruder. Manual swaps via M600 (built-in).",
    },
    "prusa_mini": {
        "id": "prusa_mini",
        "name": "Prusa MINI+",
        "manufacturer": "Prusa Research",
        "slicer_family": "prusa",
        "bed_x_mm": 180,
        "bed_y_mm": 180,
        "max_z_mm": 180,
        "default_layer_height_mm": 0.15,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Compact. Same M600 swap flow as MK4.",
    },
    "prusa_xl": {
        "id": "prusa_xl",
        "name": "Prusa XL (5-tool)",
        "manufacturer": "Prusa Research",
        "slicer_family": "prusa",
        "bed_x_mm": 360,
        "bed_y_mm": 360,
        "max_z_mm": 360,
        "default_layer_height_mm": 0.15,
        "multi_tool": True,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Multi-toolhead. Tool changes via T0–T4 (no M600).",
    },
    "voron_24": {
        "id": "voron_24",
        "name": "Voron 2.4 (350)",
        "manufacturer": "Voron",
        "slicer_family": "super",
        "bed_x_mm": 350,
        "bed_y_mm": 350,
        "max_z_mm": 350,
        "default_layer_height_mm": 0.2,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Klipper. Most builders use SuperSlicer; manual swaps.",
    },
    # ------ Cura / generic Marlin fallback ------
    "ultimaker_s3": {
        "id": "ultimaker_s3",
        "name": "Ultimaker S3 / S5",
        "manufacturer": "Ultimaker",
        "slicer_family": "cura",
        "bed_x_mm": 230,
        "bed_y_mm": 190,
        "max_z_mm": 200,
        "default_layer_height_mm": 0.15,
        "multi_tool": True,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Dual-extruder S3/S5. Cura-only — see swap.txt OPTION B.",
    },
    "generic_marlin": {
        "id": "generic_marlin",
        "name": "Generic Marlin FDM",
        "manufacturer": "Generic",
        "slicer_family": "marlin",
        "bed_x_mm": 220,
        "bed_y_mm": 220,
        "max_z_mm": 250,
        "default_layer_height_mm": 0.2,
        "multi_tool": False,
        "supported_formats": ["stl", "3mf", "swaps"],
        "notes": "Use OPTION C raw-M600 G-code if your slicer can't template.",
    },
}


DEFAULT_PRINTER_ID = "generic_orca"


def get_profile(printer_id: str) -> PrinterProfile:
    """Return a printer profile by id, falling back to the default."""
    return PRINTER_PROFILES.get(printer_id) or PRINTER_PROFILES[DEFAULT_PRINTER_ID]


def list_profiles() -> List[PrinterProfile]:
    """List all printer profiles sorted by slicer family, then name."""
    return sorted(
        PRINTER_PROFILES.values(),
        key=lambda p: (p["slicer_family"], p["manufacturer"], p["name"]),
    )


def build_layer_change_gcode(
    profile: PrinterProfile,
    swap_layer_indices: List[int],
) -> str:
    """Generate the layer-change G-code snippet appropriate for this
    printer.

    Multi-tool printers (Bambu AMS, Prusa XL, Ultimaker S3) get `T<n>`
    tool-change commands — the slicer pre-configures the AMS lanes and
    the printer auto-swaps.

    Single-extruder printers get `M600` filament-change pauses — the
    user manually swaps filament when the printer pauses.
    """
    if not swap_layer_indices:
        return ""

    if profile["multi_tool"]:
        # T0 is the BASE filament (loaded before print starts).
        # Each subsequent swap moves to the next tool slot.
        #
        # Most AMS-style printers cap at 4 lanes (T0-T3). The Prusa XL
        # has 5 tools (T0-T4). We assume a 4-tool maximum unless the
        # profile says otherwise — slots beyond that would error on the
        # printer, so we wrap with modulo and emit a comment marker so
        # the user notices.
        max_tools = 5 if profile.get("id") == "prusa_xl" else 4
        lines: List[str] = []
        for slot, idx in enumerate(swap_layer_indices):
            tool = slot + 1
            if tool >= max_tools:
                # Out of tool slots — fall back to an M600 manual pause so
                # the user still gets a swap prompt rather than a printer
                # error.
                lines.append(
                    f"{{if layer_num == {idx}}}M600 ; out of AMS slots{{endif}}"
                )
            else:
                lines.append(f"{{if layer_num == {idx}}}T{tool}{{endif}}")
        return "\n".join(lines)

    return "\n".join(
        f"{{if layer_num == {idx}}}M600{{endif}}"
        for idx in swap_layer_indices
    )


def fits_on_bed(profile: PrinterProfile, width_mm: float, height_mm: float) -> bool:
    """Returns True if a design with width × height fits on this printer's
    bed (with a small 5mm safety margin)."""
    return (
        width_mm <= profile["bed_x_mm"] - 5
        and height_mm <= profile["bed_y_mm"] - 5
    )
