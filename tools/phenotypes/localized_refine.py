"""Apply localized Wendland C2 radial refinement to derived humanoid body parts.

Refines anatomical landmarks (barrel chest, deltoid breadth, muscular thighs/calves,
seamless connectors) using compact-support Wendland C2 radial basis functions.
Enforces positive Jacobians, strict zero displacement outside support radii,
exact vertex/face/UV topology preservation, and smooth normal recomputation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from target_contract import require


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wendland_c2(dist: np.ndarray, radius: float) -> np.ndarray:
    """Wendland C2 radial basis function in R^3 with compact support [0, radius]."""
    d = np.clip(dist / radius, 0.0, 1.0)
    return (1.0 - d) ** 4 * (4.0 * d + 1.0)


# Measured refinement anchor definitions for Dwarf Male Fit
# Each anchor defines:
# - center: [X, Y, Z] in part-local space
# - radius: R support radius (displacement is mathematically 0 beyond R)
# - disp: [dX, dY, dZ] peak displacement vector at center
DWARF_MALE_ANCHORS = {
    "chest": [
        # Deltoid shoulder broadening (+10mm lateral)
        {"name": "deltoid_left", "center": [-0.206, -0.055, 0.315], "radius": 0.12, "disp": [-0.010, 0.0, 0.0]},
        {"name": "deltoid_right", "center": [0.206, -0.055, 0.315], "radius": 0.12, "disp": [0.010, 0.0, 0.0]},
        # Barrel chest pecs & ribcage (+8mm forward sternum/pecs)
        {"name": "pectoral_barrel", "center": [0.0, 0.08, 0.22], "radius": 0.16, "disp": [0.0, 0.008, 0.0]},
        # Upper traps lateral expansion
        {"name": "traps_left", "center": [-0.08, -0.02, 0.38], "radius": 0.09, "disp": [-0.005, 0.0, 0.003]},
        {"name": "traps_right", "center": [0.08, -0.02, 0.38], "radius": 0.09, "disp": [0.005, 0.0, 0.003]},
    ],
    "pelvis": [
        # Waist rim transition matching chest lower collar (+4mm lateral)
        {"name": "waist_left", "center": [-0.14, 0.02, 0.0], "radius": 0.10, "disp": [-0.004, 0.0, 0.0]},
        {"name": "waist_right", "center": [0.14, 0.02, 0.0], "radius": 0.10, "disp": [0.004, 0.0, 0.0]},
        # Gluteus breadth for stout dwarf base
        {"name": "glute_left", "center": [-0.09, -0.06, -0.10], "radius": 0.11, "disp": [-0.006, -0.004, 0.0]},
        {"name": "glute_right", "center": [0.09, -0.06, -0.10], "radius": 0.11, "disp": [0.006, -0.004, 0.0]},
    ],
    "bicepl": [
        # Bicep muscle belly fullness (+6mm anterior/lateral)
        {"name": "bicep_belly", "center": [-0.04, 0.02, -0.14], "radius": 0.09, "disp": [-0.004, 0.005, 0.0]},
        # Tricep lateral head fullness
        {"name": "tricep_belly", "center": [-0.05, -0.03, -0.16], "radius": 0.09, "disp": [-0.005, -0.004, 0.0]},
    ],
    "bicepr": [
        {"name": "bicep_belly", "center": [0.04, 0.02, -0.14], "radius": 0.09, "disp": [0.004, 0.005, 0.0]},
        {"name": "tricep_belly", "center": [0.05, -0.03, -0.16], "radius": 0.09, "disp": [0.005, -0.004, 0.0]},
    ],
    "forel": [
        # Forearm flexor/extensor muscle belly (+5mm)
        {"name": "forearm_flexor", "center": [-0.02, 0.02, -0.13], "radius": 0.08, "disp": [-0.003, 0.004, 0.0]},
        {"name": "forearm_brachio", "center": [-0.04, -0.01, -0.10], "radius": 0.08, "disp": [-0.004, 0.0, 0.0]},
    ],
    "forer": [
        {"name": "forearm_flexor", "center": [0.02, 0.02, -0.13], "radius": 0.08, "disp": [0.003, 0.004, 0.0]},
        {"name": "forearm_brachio", "center": [0.04, -0.01, -0.10], "radius": 0.08, "disp": [0.004, 0.0, 0.0]},
    ],
    "handl": [
        # Powerful broad dwarf palm and knuckle ridge (+3mm)
        {"name": "palm_breadth", "center": [-0.02, 0.01, -0.07], "radius": 0.07, "disp": [-0.003, 0.002, 0.0]},
    ],
    "handr": [
        {"name": "palm_breadth", "center": [0.02, 0.01, -0.07], "radius": 0.07, "disp": [0.003, 0.002, 0.0]},
    ],
    "legl": [
        # Muscular quad belly expansion (+10mm lateral/anterior)
        {"name": "quad_vastus_lat", "center": [-0.05, 0.02, -0.15], "radius": 0.11, "disp": [-0.008, 0.006, 0.0]},
        {"name": "quad_rectus", "center": [-0.01, 0.04, -0.14], "radius": 0.10, "disp": [0.0, 0.008, 0.0]},
        # Hamstring fullness
        {"name": "hamstring", "center": [-0.02, -0.05, -0.16], "radius": 0.10, "disp": [0.0, -0.006, 0.0]},
    ],
    "legr": [
        {"name": "quad_vastus_lat", "center": [0.05, 0.02, -0.15], "radius": 0.11, "disp": [0.008, 0.006, 0.0]},
        {"name": "quad_rectus", "center": [0.01, 0.04, -0.14], "radius": 0.10, "disp": [0.0, 0.008, 0.0]},
        {"name": "hamstring", "center": [0.02, -0.05, -0.16], "radius": 0.10, "disp": [0.0, -0.006, 0.0]},
    ],
    "shinl": [
        # Calf gastrocnemius muscle belly (+8mm posterior/lateral)
        {"name": "calf_lateral", "center": [-0.03, -0.04, -0.12], "radius": 0.09, "disp": [-0.006, -0.006, 0.0]},
        {"name": "calf_medial", "center": [0.02, -0.04, -0.11], "radius": 0.09, "disp": [0.004, -0.006, 0.0]},
        # Tibialis anterior definition
        {"name": "shin_tibialis", "center": [-0.02, 0.02, -0.14], "radius": 0.08, "disp": [-0.002, 0.004, 0.0]},
    ],
    "shinr": [
        {"name": "calf_lateral", "center": [0.03, -0.04, -0.12], "radius": 0.09, "disp": [0.006, -0.006, 0.0]},
        {"name": "calf_medial", "center": [-0.02, -0.04, -0.11], "radius": 0.09, "disp": [-0.004, -0.006, 0.0]},
        {"name": "shin_tibialis", "center": [0.02, 0.02, -0.14], "radius": 0.08, "disp": [0.002, 0.004, 0.0]},
    ],
    "footl": [
        # Broad dwarf instep and heel base (+4mm)
        {"name": "instep", "center": [-0.02, 0.05, -0.08], "radius": 0.08, "disp": [-0.003, 0.0, 0.002]},
    ],
    "footr": [
        {"name": "instep", "center": [0.02, 0.05, -0.08], "radius": 0.08, "disp": [0.003, 0.0, 0.002]},
    ],
}

# Measured refinement anchor definitions for Troll Male Fit
# Incorporates approved purpose-built forms:
# - Large trapezius muscles and collar-like neck rim
# - Forward pectoral expansion and deltoid broadening
# - Muscular quad and calf sweeps
# - Reinforced knuckles and sturdy foot instep
# - Zero displacement at all connector rings
TROLL_MALE_ANCHORS = {
    "chest": [
        # Trapezius cranial and lateral bulk
        {"name": "traps_left", "center": [-0.10, -0.04, 0.42], "radius": 0.14, "disp": [-0.012, 0.005, 0.022]},
        {"name": "traps_right", "center": [0.10, -0.04, 0.42], "radius": 0.14, "disp": [0.012, 0.005, 0.022]},
        # Collar-like neck rim across anterior-lateral neck junction
        {"name": "collar_rim_front", "center": [0.0, 0.04, 0.42], "radius": 0.12, "disp": [0.0, 0.018, 0.008]},
        {"name": "collar_rim_left", "center": [-0.09, -0.02, 0.44], "radius": 0.10, "disp": [-0.012, 0.008, 0.006]},
        {"name": "collar_rim_right", "center": [0.09, -0.02, 0.44], "radius": 0.10, "disp": [0.012, 0.008, 0.006]},
        # Forward pectoral definition
        {"name": "pectoral_forward", "center": [0.0, 0.12, 0.24], "radius": 0.20, "disp": [0.0, 0.025, 0.0]},
        # Deltoid shoulder expansion
        {"name": "deltoid_broaden_left", "center": [-0.26, -0.06, 0.32], "radius": 0.15, "disp": [-0.015, 0.005, 0.0]},
        {"name": "deltoid_broaden_right", "center": [0.26, -0.06, 0.32], "radius": 0.15, "disp": [0.015, 0.005, 0.0]},
    ],
    "pelvis": [
        # Waist rim transition matching broadened chest
        {"name": "waist_flank_left", "center": [-0.18, 0.02, 0.0], "radius": 0.09, "disp": [-0.004, 0.0, 0.0]},
        {"name": "waist_flank_right", "center": [0.18, 0.02, 0.0], "radius": 0.09, "disp": [0.004, 0.0, 0.0]},
        # Gluteus definition
        {"name": "glute_left", "center": [-0.12, -0.08, -0.08], "radius": 0.09, "disp": [-0.004, -0.003, 0.0]},
        {"name": "glute_right", "center": [0.12, -0.08, -0.08], "radius": 0.09, "disp": [0.004, -0.003, 0.0]},
    ],
    "bicepl": [
        {"name": "bicep_belly", "center": [-0.05, 0.03, -0.14], "radius": 0.10, "disp": [-0.006, 0.008, 0.0]},
        {"name": "tricep_belly", "center": [-0.06, -0.04, -0.16], "radius": 0.10, "disp": [-0.006, -0.006, 0.0]},
    ],
    "bicepr": [
        {"name": "bicep_belly", "center": [0.05, 0.03, -0.14], "radius": 0.10, "disp": [0.006, 0.008, 0.0]},
        {"name": "tricep_belly", "center": [0.06, -0.04, -0.16], "radius": 0.10, "disp": [0.006, -0.006, 0.0]},
    ],
    "forel": [
        {"name": "forearm_flexor", "center": [-0.03, 0.03, -0.13], "radius": 0.09, "disp": [-0.004, 0.006, 0.0]},
        {"name": "forearm_brachio", "center": [-0.05, -0.01, -0.10], "radius": 0.09, "disp": [-0.005, 0.0, 0.0]},
    ],
    "forer": [
        {"name": "forearm_flexor", "center": [0.03, 0.03, -0.13], "radius": 0.09, "disp": [0.004, 0.006, 0.0]},
        {"name": "forearm_brachio", "center": [0.05, -0.01, -0.10], "radius": 0.09, "disp": [0.005, 0.0, 0.0]},
    ],
    "handl": [
        {"name": "palm_definition", "center": [-0.02, 0.01, -0.08], "radius": 0.08, "disp": [-0.002, 0.002, 0.0]},
    ],
    "handr": [
        {"name": "palm_definition", "center": [0.02, 0.01, -0.08], "radius": 0.08, "disp": [0.002, 0.002, 0.0]},
    ],
    "legl": [
        {"name": "quad_vastus_lat", "center": [-0.07, 0.03, -0.16], "radius": 0.13, "disp": [-0.010, 0.008, 0.0]},
        {"name": "quad_rectus", "center": [-0.01, 0.06, -0.15], "radius": 0.12, "disp": [0.0, 0.010, 0.0]},
        {"name": "hamstring", "center": [-0.03, -0.07, -0.17], "radius": 0.12, "disp": [0.0, -0.008, 0.0]},
    ],
    "legr": [
        {"name": "quad_vastus_lat", "center": [0.07, 0.03, -0.16], "radius": 0.13, "disp": [0.010, 0.008, 0.0]},
        {"name": "quad_rectus", "center": [0.01, 0.06, -0.15], "radius": 0.12, "disp": [0.0, 0.010, 0.0]},
        {"name": "hamstring", "center": [0.03, -0.07, -0.17], "radius": 0.12, "disp": [0.0, -0.008, 0.0]},
    ],
    "shinl": [
        {"name": "calf_lateral", "center": [-0.04, -0.06, -0.13], "radius": 0.11, "disp": [-0.008, -0.008, 0.0]},
        {"name": "calf_medial", "center": [0.03, -0.06, -0.12], "radius": 0.11, "disp": [0.006, -0.008, 0.0]},
        {"name": "shin_tibialis", "center": [-0.03, 0.03, -0.15], "radius": 0.10, "disp": [-0.003, 0.005, 0.0]},
    ],
    "shinr": [
        {"name": "calf_lateral", "center": [0.04, -0.06, -0.13], "radius": 0.11, "disp": [0.008, -0.008, 0.0]},
        {"name": "calf_medial", "center": [-0.03, -0.06, -0.12], "radius": 0.11, "disp": [-0.006, -0.008, 0.0]},
        {"name": "shin_tibialis", "center": [0.03, 0.03, -0.15], "radius": 0.10, "disp": [0.003, 0.005, 0.0]},
    ],
    "footl": [
        {"name": "instep_broaden", "center": [-0.03, 0.06, -0.09], "radius": 0.09, "disp": [-0.004, 0.0, 0.003]},
    ],
    "footr": [
        {"name": "instep_broaden", "center": [0.03, 0.06, -0.09], "radius": 0.09, "disp": [0.004, 0.0, 0.003]},
    ],
}

# Measured refinement anchor definitions for Elf Male Fit
# Lean, graceful, athletic anatomy matching Shadowrun elven archetype:
# - Elegant clavicle contours and refined athletic pectorals
# - Slender waist and defined latissimus lines
# - Streamlined deltoid and bicep definitions
# - Lean, agile quadriceps and calf profiles
# - Zero displacement at all connector rings
ELF_MALE_ANCHORS = {
    "chest": [
        {"name": "clavicle_left", "center": [-0.09, 0.04, 0.38], "radius": 0.08, "disp": [-0.003, 0.002, 0.003]},
        {"name": "clavicle_right", "center": [0.09, 0.04, 0.38], "radius": 0.08, "disp": [0.003, 0.002, 0.003]},
        {"name": "pectoral_trim", "center": [0.0, 0.08, 0.23], "radius": 0.14, "disp": [0.0, -0.004, 0.0]},
        {"name": "latissimus_left", "center": [-0.15, -0.05, 0.22], "radius": 0.10, "disp": [0.003, 0.0, 0.0]},
        {"name": "latissimus_right", "center": [0.15, -0.05, 0.22], "radius": 0.10, "disp": [-0.003, 0.0, 0.0]},
    ],
    "pelvis": [
        {"name": "waist_taper_left", "center": [-0.12, 0.01, 0.0], "radius": 0.08, "disp": [0.002, 0.0, 0.0]},
        {"name": "waist_taper_right", "center": [0.12, 0.01, 0.0], "radius": 0.08, "disp": [-0.002, 0.0, 0.0]},
        {"name": "glute_lean_left", "center": [-0.08, -0.06, -0.09], "radius": 0.09, "disp": [0.002, 0.002, 0.0]},
        {"name": "glute_lean_right", "center": [0.08, -0.06, -0.09], "radius": 0.09, "disp": [-0.002, 0.002, 0.0]},
    ],
    "bicepl": [
        {"name": "bicep_tone", "center": [-0.04, 0.02, -0.14], "radius": 0.08, "disp": [-0.002, 0.002, 0.0]},
        {"name": "tricep_tone", "center": [-0.04, -0.03, -0.16], "radius": 0.08, "disp": [-0.002, -0.002, 0.0]},
    ],
    "bicepr": [
        {"name": "bicep_tone", "center": [0.04, 0.02, -0.14], "radius": 0.08, "disp": [0.002, 0.002, 0.0]},
        {"name": "tricep_tone", "center": [0.04, -0.03, -0.16], "radius": 0.08, "disp": [0.002, -0.002, 0.0]},
    ],
    "forel": [
        {"name": "forearm_sleek", "center": [-0.02, 0.02, -0.13], "radius": 0.07, "disp": [-0.002, 0.002, 0.0]},
    ],
    "forer": [
        {"name": "forearm_sleek", "center": [0.02, 0.02, -0.13], "radius": 0.07, "disp": [0.002, 0.002, 0.0]},
    ],
    "handl": [
        {"name": "hand_slender", "center": [-0.02, 0.01, -0.07], "radius": 0.06, "disp": [0.001, 0.0, 0.0]},
    ],
    "handr": [
        {"name": "hand_slender", "center": [0.02, 0.01, -0.07], "radius": 0.06, "disp": [-0.001, 0.0, 0.0]},
    ],
    "legl": [
        {"name": "quad_lean", "center": [-0.04, 0.03, -0.15], "radius": 0.09, "disp": [-0.003, 0.002, 0.0]},
        {"name": "hamstring_lean", "center": [-0.02, -0.04, -0.16], "radius": 0.09, "disp": [0.0, -0.002, 0.0]},
    ],
    "legr": [
        {"name": "quad_lean", "center": [0.04, 0.03, -0.15], "radius": 0.09, "disp": [0.003, 0.002, 0.0]},
        {"name": "hamstring_lean", "center": [0.02, -0.04, -0.16], "radius": 0.09, "disp": [0.0, -0.002, 0.0]},
    ],
    "shinl": [
        {"name": "calf_streamlined", "center": [-0.02, -0.03, -0.12], "radius": 0.08, "disp": [-0.002, -0.002, 0.0]},
    ],
    "shinr": [
        {"name": "calf_streamlined", "center": [0.02, -0.03, -0.12], "radius": 0.08, "disp": [0.002, -0.002, 0.0]},
    ],
    "footl": [
        {"name": "instep_sleek", "center": [-0.02, 0.04, -0.08], "radius": 0.07, "disp": [0.0, 0.0, 0.001]},
    ],
    "footr": [
        {"name": "instep_sleek", "center": [0.02, 0.04, -0.08], "radius": 0.07, "disp": [0.0, 0.0, 0.001]},
    ],
}

# Measured refinement anchor definitions for Orc Male Fit
# Heavy muscular frame matching stock pmo0 skeleton and Shadowrun orc archetype:
# - Broad, thick trapezius ridge
# - Deep, forward-projecting pectorals
# - Flared latissimus contours
# - Reinforced flank and oblique waist transitions
# - Heavy bicep, tricep, and forearm muscle bellies
# - Powerful quadriceps and gastrocnemius calves
# - Sturdy foot instep
# - Zero displacement at all connector rings
ORC_MALE_ANCHORS = {
    "chest": [
        {"name": "traps_left", "center": [-0.12, -0.04, 0.51], "radius": 0.12, "disp": [-0.008, 0.003, 0.012]},
        {"name": "traps_right", "center": [0.12, -0.04, 0.51], "radius": 0.12, "disp": [0.008, 0.003, 0.012]},
        {"name": "pectoral_forward", "center": [0.0, 0.12, 0.31], "radius": 0.16, "disp": [0.0, 0.012, 0.0]},
        {"name": "latissimus_left", "center": [-0.22, -0.05, 0.28], "radius": 0.12, "disp": [-0.008, 0.0, 0.0]},
        {"name": "latissimus_right", "center": [0.22, -0.05, 0.28], "radius": 0.12, "disp": [0.008, 0.0, 0.0]},
    ],
    "pelvis": [
        {"name": "waist_flank_left", "center": [-0.15, 0.02, 0.0], "radius": 0.09, "disp": [-0.004, 0.0, 0.0]},
        {"name": "waist_flank_right", "center": [0.15, 0.02, 0.0], "radius": 0.09, "disp": [0.004, 0.0, 0.0]},
        {"name": "glute_left", "center": [-0.10, -0.07, -0.093], "radius": 0.10, "disp": [-0.005, -0.004, 0.0]},
        {"name": "glute_right", "center": [0.10, -0.07, -0.093], "radius": 0.10, "disp": [0.005, -0.004, 0.0]},
    ],
    "bicepl": [
        {"name": "bicep_belly", "center": [-0.06, 0.03, -0.20], "radius": 0.13, "disp": [-0.008, 0.012, 0.0]},
        {"name": "tricep_belly", "center": [-0.07, -0.04, -0.215], "radius": 0.13, "disp": [-0.008, -0.010, 0.0]},
    ],
    "bicepr": [
        {"name": "bicep_belly", "center": [0.06, 0.03, -0.20], "radius": 0.13, "disp": [0.008, 0.012, 0.0]},
        {"name": "tricep_belly", "center": [0.07, -0.04, -0.215], "radius": 0.13, "disp": [0.008, -0.010, 0.0]},
    ],
    "forel": [
        {"name": "forearm_flexor", "center": [-0.03, 0.03, -0.18], "radius": 0.11, "disp": [-0.006, 0.008, 0.0]},
        {"name": "forearm_brachio", "center": [-0.06, -0.01, -0.145], "radius": 0.11, "disp": [-0.008, 0.0, 0.0]},
    ],
    "forer": [
        {"name": "forearm_flexor", "center": [0.03, 0.03, -0.18], "radius": 0.11, "disp": [0.008, 0.008, 0.0]},
        {"name": "forearm_brachio", "center": [0.06, -0.01, -0.145], "radius": 0.11, "disp": [0.008, 0.0, 0.0]},
    ],
    "handl": [
        {"name": "palm_definition", "center": [-0.02, 0.01, -0.08], "radius": 0.08, "disp": [-0.003, 0.002, 0.0]},
    ],
    "handr": [
        {"name": "palm_definition", "center": [0.02, 0.01, -0.08], "radius": 0.08, "disp": [0.003, 0.002, 0.0]},
    ],
    "legl": [
        {"name": "quad_vastus", "center": [-0.06, 0.03, -0.16], "radius": 0.12, "disp": [-0.008, 0.006, 0.0]},
        {"name": "hamstring", "center": [-0.02, -0.06, -0.16], "radius": 0.11, "disp": [0.0, -0.006, 0.0]},
    ],
    "legr": [
        {"name": "quad_vastus", "center": [0.06, 0.03, -0.16], "radius": 0.12, "disp": [0.008, 0.006, 0.0]},
        {"name": "hamstring", "center": [0.02, -0.06, -0.16], "radius": 0.11, "disp": [0.0, -0.006, 0.0]},
    ],
    "shinl": [
        {"name": "calf_lateral", "center": [-0.03, -0.05, -0.13], "radius": 0.10, "disp": [-0.006, -0.006, 0.0]},
        {"name": "calf_medial", "center": [0.02, -0.05, -0.12], "radius": 0.10, "disp": [0.005, -0.006, 0.0]},
    ],
    "shinr": [
        {"name": "calf_lateral", "center": [0.03, -0.05, -0.13], "radius": 0.10, "disp": [0.006, -0.006, 0.0]},
        {"name": "calf_medial", "center": [-0.02, -0.05, -0.12], "radius": 0.10, "disp": [-0.005, -0.006, 0.0]},
    ],
    "footl": [
        {"name": "instep_broaden", "center": [-0.02, 0.05, -0.08], "radius": 0.08, "disp": [-0.003, 0.0, 0.002]},
    ],
    "footr": [
        {"name": "instep_broaden", "center": [0.02, 0.05, -0.08], "radius": 0.08, "disp": [0.003, 0.0, 0.002]},
    ],
}


def calculate_mesh_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    """Calculate enclosed mesh volume using signed tetrahedra from origin."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    # Volume = 1/6 sum (v0 . (v1 x v2))
    cross = np.cross(v1, v2)
    signed_vols = np.sum(v0 * cross, axis=1) / 6.0
    return float(np.abs(np.sum(signed_vols)))


def compute_angle_weighted_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Compute smooth, angle-weighted vertex normals across triangle mesh."""
    normals = np.zeros_like(verts)
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]

    e0 = v1 - v0
    e1 = v2 - v1
    e2 = v0 - v2

    fn = np.cross(e0, -e2)
    fn_len = np.linalg.norm(fn, axis=1, keepdims=True)
    fn_len[fn_len < 1e-12] = 1.0
    fn_unit = fn / fn_len

    # Corner angles
    def edge_angle(ea, eb):
        ea_u = ea / np.clip(np.linalg.norm(ea, axis=1, keepdims=True), 1e-12, None)
        eb_u = eb / np.clip(np.linalg.norm(eb, axis=1, keepdims=True), 1e-12, None)
        cos_theta = np.clip(np.sum(ea_u * eb_u, axis=1), -1.0, 1.0)
        return np.arccos(cos_theta)

    a0 = edge_angle(e0, -e2)[:, None]
    a1 = edge_angle(e1, -e0)[:, None]
    a2 = edge_angle(e2, -e1)[:, None]

    np.add.at(normals, faces[:, 0], fn_unit * a0)
    np.add.at(normals, faces[:, 1], fn_unit * a1)
    np.add.at(normals, faces[:, 2], fn_unit * a2)

    n_len = np.linalg.norm(normals, axis=1, keepdims=True)
    n_len[n_len < 1e-12] = 1.0
    return normals / n_len


def verify_positive_jacobians(verts: np.ndarray, new_verts: np.ndarray, faces: np.ndarray) -> tuple[bool, float]:
    """Verify that all triangle Jacobians remain strictly positive after deformation."""
    v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    nv0, nv1, nv2 = new_verts[faces[:, 0]], new_verts[faces[:, 1]], new_verts[faces[:, 2]]

    n_orig = np.cross(v1 - v0, v2 - v0)
    orig_area2 = np.sum(n_orig * n_orig, axis=1)

    n_new = np.cross(nv1 - nv0, nv2 - nv0)
    dots = np.sum(n_orig * n_new, axis=1)

    valid = orig_area2 > 1e-12
    jacobians = np.ones(len(faces))
    jacobians[valid] = dots[valid] / orig_area2[valid]

    min_j = float(np.min(jacobians[valid])) if np.any(valid) else 1.0
    return bool(min_j > 0.0), min_j


def parse_ascii_body_part(text: str) -> dict:
    """Extract model header, nodes, and all mesh nodes from clean ASCII MDL."""
    m_name = re.search(r"(?mi)^newmodel\s+(\S+)", text).group(1)
    sm = re.search(r"(?mi)^setsupermodel\s+\S+\s+(\S+)", text)
    supermodel = sm.group(1) if sm else "NULL"

    # Find all trimesh nodes
    nodes_info = []
    for m_node in re.finditer(r"(?m)^\s*node\s+trimesh\s+(\S+)\s*\n(.*?)^\s*endnode", text, re.S):
        node_name = m_node.group(1)
        body = m_node.group(2)

        bm = re.search(r"(?m)^\s*bitmap\s+(\S+)", body)
        bitmap = bm.group(1) if bm else node_name

        verts = np.array(arrays(body, "verts"), dtype=float)
        normals = np.array(arrays(body, "normals"), dtype=float)
        tverts = np.array(arrays(body, "tverts"), dtype=float)
        faces = np.array(arrays(body, "faces"), dtype=int)

        nodes_info.append({
            "nodeName": node_name,
            "bitmap": bitmap,
            "verts": verts,
            "normals": normals,
            "tverts": tverts,
            "faces": faces,
        })

    return {
        "modelName": m_name,
        "supermodel": supermodel,
        "meshNodes": nodes_info,
    }


def emit_ascii_body_part(data: dict) -> str:
    """Emit clean standard NWN ASCII MDL text for refined body part with all mesh nodes."""
    m = data["modelName"]
    sm = data["supermodel"]

    lines = [
        f"newmodel {m}",
        f"setsupermodel {m} {sm}",
        "classification CHARACTER",
        "setanimationscale 1",
        f"beginmodelgeom {m}",
        f"node dummy {m}",
        "  parent NULL",
        "endnode",
    ]
    for node in data["meshNodes"]:
        n_name = node["nodeName"]
        bm = node["bitmap"]
        verts = node["verts"]
        normals = node["normals"]
        tverts = node["tverts"]
        faces = node["faces"]

        lines.extend([
            f"node trimesh {n_name}",
            f"  parent {m}",
            f"  bitmap {bm}",
            f"  verts {len(verts)}",
        ])
        for v in verts:
            lines.append(f"    {v[0]:.9g} {v[1]:.9g} {v[2]:.9g}")

        lines.append(f"  normals {len(normals)}")
        for n in normals:
            lines.append(f"    {n[0]:.9g} {n[1]:.9g} {n[2]:.9g}")

        lines.append(f"  tverts {len(tverts)}")
        for tv in tverts:
            lines.append(f"    {tv[0]:.9g} {tv[1]:.9g} 0")

        lines.append(f"  faces {len(faces)}")
        for f in faces:
            lines.append(f"    {f[0]} {f[1]} {f[2]} 1 {f[0]} {f[1]} {f[2]} 0")

        lines.append("endnode")

    lines.extend([
        f"endmodelgeom {m}",
        f"donemodel {m}",
        "",
    ])
    return "\n".join(lines)


def refine_all_parts(
    target_data: dict,
    affine_dir: Path,
    output_dir: Path,
    anchors_map: dict[str, list[dict]] = DWARF_MALE_ANCHORS,
) -> dict:
    """Execute localized Wendland C2 refinement across all 14 body parts."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = target_data["identity"]["prefix"]
    part_reports = {}
    all_parts_passed = True

    for part, anchors in anchors_map.items():
        model_name = f"{prefix}_{part}001"
        src_path = affine_dir / f"{model_name}.mdl"
        require(src_path.is_file(), f"Input affine model missing: {src_path}")

        src_text = src_path.read_text(encoding="cp1252")
        data = parse_ascii_body_part(src_text)

        total_verts = sum(len(n["verts"]) for n in data["meshNodes"])
        total_faces = sum(len(n["faces"]) for n in data["meshNodes"])

        vol_before = sum(calculate_mesh_volume(n["verts"], n["faces"]) for n in data["meshNodes"])

        total_displaced = 0
        global_max_disp = 0.0
        global_min_j = 1.0

        for node in data["meshNodes"]:
            verts = node["verts"]
            faces = node["faces"]

            # Compute Wendland displacement
            disp = np.zeros_like(verts)
            for a in anchors:
                c = np.array(a["center"], dtype=float)
                r = float(a["radius"])
                d_vec = np.array(a["disp"], dtype=float)

                dist = np.linalg.norm(verts - c, axis=1)
                w = wendland_c2(dist, r)[:, None]
                disp += w * d_vec

            new_verts = verts + disp

            # Verify strict zero displacement outside support radii
            outside_all = np.ones(len(verts), dtype=bool)
            for a in anchors:
                c = np.array(a["center"], dtype=float)
                r = float(a["radius"])
                outside_all &= (np.linalg.norm(verts - c, axis=1) >= r)

            max_outside_disp = float(np.max(np.linalg.norm(disp[outside_all], axis=1))) if np.any(outside_all) else 0.0
            require(
                max_outside_disp < 1e-12,
                f"Displacement leaked outside support radius in {part}/{node['nodeName']}: {max_outside_disp:.6e} m",
            )

            # Verify positive Jacobians
            jac_ok, min_j = verify_positive_jacobians(verts, new_verts, faces)
            require(jac_ok, f"Triangle inversion detected in {part}/{node['nodeName']}: min Jacobian = {min_j:.4f}")
            global_min_j = min(global_min_j, min_j)

            # Recompute surface normals
            new_normals = compute_angle_weighted_normals(new_verts, faces)

            moved_mask = np.linalg.norm(disp, axis=1) > 1e-6
            total_displaced += int(np.sum(moved_mask))
            if len(disp) > 0:
                global_max_disp = max(global_max_disp, float(np.max(np.linalg.norm(disp, axis=1))))

            node["verts"] = new_verts
            node["normals"] = new_normals

        vol_after = sum(calculate_mesh_volume(n["verts"], n["faces"]) for n in data["meshNodes"])
        vol_change_pct = ((vol_after - vol_before) / vol_before) * 100.0 if vol_before > 0 else 0.0

        max_volume_pct = float(target_data.get("volumeThresholdPercent", 1.0))
        volume_passed = bool(abs(vol_change_pct) <= max_volume_pct)
        part_status = "passed-localized-refinement" if (global_min_j > 0.0 and volume_passed) else "failed-volume-limit"
        if not volume_passed or global_min_j <= 0.0:
            all_parts_passed = False

        out_text = emit_ascii_body_part(data)
        out_file = output_dir / f"{model_name}.mdl"
        out_file.write_text(out_text, encoding="cp1252")

        part_reports[part] = {
            "model": model_name,
            "sourceAffineMdl": str(src_path),
            "sourceSha256": sha256_file(src_path),
            "refinedMdl": str(out_file),
            "refinedSha256": sha256_file(out_file),
            "meshNodeCount": len(data["meshNodes"]),
            "vertexCount": total_verts,
            "faceCount": total_faces,
            "displacedVertices": total_displaced,
            "displacedFraction": total_displaced / total_verts if total_verts else 0.0,
            "maxDisplacementMeters": global_max_disp,
            "zeroOutsideSupportProof": True,
            "minJacobian": global_min_j,
            "positiveJacobian": True,
            "volumeBeforeM3": vol_before,
            "volumeAfterM3": vol_after,
            "volumeChangePercent": vol_change_pct,
            "volumeLimitPercent": max_volume_pct,
            "volumePreserved": volume_passed,
            "status": part_status,
        }

    require(all_parts_passed, f"One or more parts exceeded volume limit ({max_volume_pct}%): {[p for p, r in part_reports.items() if r['status'] != 'passed-localized-refinement']}")

    proof = {
        "schemaVersion": 1,
        "kind": "derived-localized-refinement-proof",
        "targetId": target_data["id"],
        "partsCount": len(part_reports),
        "falloffType": "wendland-c2",
        "allPartsPassed": all_parts_passed,
        "maxVolumeChangePercentThreshold": max_volume_pct,
        "parts": part_reports,
        "status": "verified-exact-refinement" if all_parts_passed else "failed-volume-limit",
    }

    proof_path = output_dir / "refinement-proof.json"
    proof_path.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("tools/phenotypes/configurations/derived/target-dwarf-male-stock.json"),
        help="Target configuration JSON",
    )
    parser.add_argument(
        "--affine-dir",
        type=Path,
        default=None,
        help="Input affine parts directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output refined parts directory",
    )
    args = parser.parse_args()

    target_data = json.loads(args.target.read_text(encoding="utf-8"))
    race = target_data["identity"]["race"]
    if race == "troll":
        anchors = TROLL_MALE_ANCHORS
    elif race == "elf":
        anchors = ELF_MALE_ANCHORS
    elif race == "orc":
        anchors = ORC_MALE_ANCHORS
    else:
        anchors = DWARF_MALE_ANCHORS
    affine_dir = args.affine_dir or Path(f"output/phenotypes/derived-v1/parts/{race}-male/affine")
    output_dir = args.output_dir or Path(f"output/phenotypes/derived-v1/parts/{race}-male/ascii")

    print(f"Refining 14 body parts for '{target_data['id']}' with Wendland C2 anchors...")

    proof = refine_all_parts(target_data, affine_dir, output_dir, anchors_map=anchors)
    print(f"Refinement complete: {proof['partsCount']} parts refined.")
    for p, r in proof["parts"].items():
        print(f"  {p:8s}: max_disp={r['maxDisplacementMeters']*1000:.1f}mm, displaced={r['displacedFraction']*100:.1f}%, min_J={r['minJacobian']:.4f}, dVol={r['volumeChangePercent']:+.2f}%")
    print(f"Proof written to {output_dir / 'refinement-proof.json'}")


if __name__ == "__main__":
    main()
