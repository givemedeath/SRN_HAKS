"""Derived phenotype profile builder and target configuration generator.

Extracts attachment frames and bone lengths from stock supermodel definitions and constructs
valid phenotype-target contracts for derived races.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retarget import nodes, transforms, geometry
from derive_rig import read_mdl_text
from target_contract import PART_JOINTS, validate, require

CONFIG_DIR = Path(__file__).resolve().parent / "configurations" / "derived"


def build_target_profile(
    target_id: str,
    race: str,
    gender: str,
    phenotype: int,
    prefix: str,
    race_id: int,
    appearance_row: int,
    supermodel_path: Path | str,
    height_meters: float,
    source_prefix: str = "pmh0",
    supermodel_name: str = "pmd0",
    animation_supermodel: str = "a_da"
) -> dict:
    """Build a validated phenotype-target configuration dictionary."""
    text = read_mdl_text(supermodel_path)
    skel = nodes(text)
    xforms = transforms(skel)
    
    frames = {}
    for part, joint in PART_JOINTS.items():
        j_lower = joint.lower()
        require(j_lower in xforms, f"Missing joint '{joint}' in supermodel {supermodel_path}")
        matrix = xforms[j_lower]
        rot = matrix[:3, :3]
        require(np.allclose(rot.T @ rot, np.eye(3), atol=1e-8), f"Non-orthogonal rotation in {joint}")
        require(abs(np.linalg.det(rot) - 1.0) < 1e-8, f"Non-proper rotation in {joint}")
        frames[j_lower] = matrix.tolist()

    models = {part: f"{prefix}_{part}001" for part in PART_JOINTS}
    
    target_data = {
        "schemaVersion": 2,
        "kind": "phenotype-target",
        "id": target_id,
        "identity": {
            "race": race,
            "gender": gender,
            "phenotype": phenotype,
            "prefix": prefix,
            "raceId": race_id,
            "appearanceRow": appearance_row
        },
        "heightMeters": float(height_meters),
        "workingHeightMeters": float(height_meters),
        "rig": {
            "revision": f"{prefix}-stock-family-v1",
            "mode": "retargeted",
            "runtimeScale": 1.0,
            "positionPolicy": "bind-relative",
            "preserveRotations": True,
            "preserveTimingEvents": True,
            "sourcePrefix": source_prefix,
            "targetPrefix": prefix,
            "supermodel": supermodel_name,
            "animationSupermodel": animation_supermodel,
            "frames": {
                "working": frames,
                "runtime": frames
            }
        },
        "material": {
            "fixedGarmentParts": ["pelvis"]
        },
        "models": models
    }
    
    validate(target_data)
    return target_data


def generate_dwarf_male_target(
    supermodel_path: Path | str = Path("output/phenotypes/derived-v1/masters/human-male-v1/stock/pmd0.mdl"),
    output_path: Path | str = CONFIG_DIR / "target-dwarf-male-stock.json"
) -> dict:
    """Generate and validate the primary pilot dwarf male target contract."""
    target = build_target_profile(
        target_id="dwarf-male-stock-family",
        race="dwarf",
        gender="male",
        phenotype=0,
        prefix="pmd0",
        race_id=0,
        appearance_row=0,
        supermodel_path=supermodel_path,
        height_meters=1.4864,
        source_prefix="pmh0",
        supermodel_name="pmd0",
        animation_supermodel="a_da"
    )
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    return target


def emit_ascii_skeleton(model_name: str, supermodel_name: str, skel: dict) -> str:
    """Emit clean ASCII MDL text for a dummy rig hierarchy."""
    lines = [
        f"newmodel {model_name}",
        f"setsupermodel {model_name} {supermodel_name}",
        "classification Character",
        "setanimationscale 1.0",
        geometry(model_name, skel, 1),
        f"donemodel {model_name}",
        "",
    ]
    return "\n".join(lines)


def generate_troll_male_target(
    human_stock_mdl: Path | str = Path("output/phenotypes/derived-v1/masters/human-male-v1/stock/pmh0.mdl"),
    output_rig_path: Path | str = Path("output/phenotypes/derived-v1/rigs/troll-male/pmg0.mdl"),
    output_config_path: Path | str = CONFIG_DIR / "target-troll-male-fit.json"
) -> dict:
    """Generate, validate, and write the broadened reference-scaled Troll male target contract."""
    human_text = read_mdl_text(human_stock_mdl)
    skel = nodes(human_text)

    # Rename root model pmh0 -> pmg0
    skel["pmg0"] = skel.pop("pmh0")
    skel["pmg0"]["name"] = "pmg0"
    for k, v in skel.items():
        if v["parent"] == "pmh0":
            v["parent"] = "pmg0"

    # Broadened shoulder span: 0.5399375401 m (+/- 0.26996877 m)
    skel["lbicep_g"]["position"][0] = -0.26996877005
    skel["rbicep_g"]["position"][0] = 0.26996877005

    # Broadened hip span: 0.2476646136 m (+/- 0.12383231 m)
    skel["lthigh_g"]["position"][0] = -0.1238323068
    skel["rthigh_g"]["position"][0] = 0.1238323068

    # Emit broadened pmg0.mdl
    rig_path = Path(output_rig_path).resolve()
    rig_path.parent.mkdir(parents=True, exist_ok=True)
    rig_ascii = emit_ascii_skeleton("pmg0", "a_ba", skel)
    rig_path.write_text(rig_ascii, encoding="cp1252")

    xforms = transforms(skel)

    factor = 10.0 / 7.0
    working_h = 1.9339157
    runtime_h = working_h * factor

    working_frames = {}
    runtime_frames = {}

    for part, joint in PART_JOINTS.items():
        j_lower = joint.lower()
        require(j_lower in xforms, f"Missing joint '{joint}' in Troll rig")
        mat = xforms[j_lower]
        rot = mat[:3, :3]
        require(np.allclose(rot.T @ rot, np.eye(3), atol=1e-8), f"Non-orthogonal rotation in {joint}")
        require(abs(np.linalg.det(rot) - 1.0) < 1e-8, f"Non-proper rotation in {joint}")
        working_frames[j_lower] = mat.tolist()

        rmat = mat.copy()
        rmat[:3, 3] *= factor
        runtime_frames[j_lower] = rmat.tolist()

    models = {part: f"pmg0_{part}001" for part in PART_JOINTS}

    target_data = {
        "schemaVersion": 2,
        "kind": "phenotype-target",
        "id": "troll-male-fit",
        "identity": {
            "race": "troll",
            "gender": "male",
            "phenotype": 0,
            "prefix": "pmg0",
            "raceId": 2,
            "appearanceRow": 2,
        },
        "heightMeters": float(runtime_h),
        "workingHeightMeters": float(working_h),
        "rig": {
            "revision": "pmg0-troll-male-broadened-v1",
            "mode": "retargeted",
            "runtimeScale": float(factor),
            "positionPolicy": "bind-relative",
            "preserveRotations": True,
            "preserveTimingEvents": True,
            "sourcePrefix": "pmh0",
            "targetPrefix": "pmg0",
            "supermodel": "pmg0",
            "animationSupermodel": "a_ba",
            "frames": {
                "working": working_frames,
                "runtime": runtime_frames,
            }
        },
        "material": {
            "fixedGarmentParts": ["pelvis"]
        },
        "models": models,
    }

    validate(target_data)

    out = Path(output_config_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(target_data, indent=2) + "\n", encoding="utf-8")
    return target_data


def generate_elf_male_target(
    supermodel_path: Path | str = Path("output/phenotypes/derived-v1/masters/human-male-v1/stock/pme0.mdl"),
    output_rig_path: Path | str = Path("output/phenotypes/derived-v1/rigs/elf-male/pme0.mdl"),
    output_config_path: Path | str = CONFIG_DIR / "target-elf-male-fit.json"
) -> dict:
    """Generate, validate, and write the slender-scaled Elf male target contract."""
    elf_text = read_mdl_text(supermodel_path)
    skel = nodes(elf_text)

    # Emit rig to output rigs dir
    rig_path = Path(output_rig_path).resolve()
    rig_path.parent.mkdir(parents=True, exist_ok=True)
    rig_path.write_text(elf_text, encoding="cp1252")

    xforms = transforms(skel)

    factor = 1.90 / 1.75  # ~1.0857142857142857
    working_h = 1.9339157
    runtime_h = working_h * factor

    working_frames = {}
    runtime_frames = {}

    for part, joint in PART_JOINTS.items():
        j_lower = joint.lower()
        require(j_lower in xforms, f"Missing joint '{joint}' in Elf rig")
        mat = xforms[j_lower]
        rot = mat[:3, :3]
        require(np.allclose(rot.T @ rot, np.eye(3), atol=1e-8), f"Non-orthogonal rotation in {joint}")
        require(abs(np.linalg.det(rot) - 1.0) < 1e-8, f"Non-proper rotation in {joint}")
        working_frames[j_lower] = mat.tolist()

        rmat = mat.copy()
        rmat[:3, 3] *= factor
        runtime_frames[j_lower] = rmat.tolist()

    models = {part: f"pme0_{part}001" for part in PART_JOINTS}

    target_data = {
        "schemaVersion": 2,
        "kind": "phenotype-target",
        "id": "elf-male-fit",
        "identity": {
            "race": "elf",
            "gender": "male",
            "phenotype": 0,
            "prefix": "pme0",
            "raceId": 1,
            "appearanceRow": 1,
        },
        "heightMeters": float(runtime_h),
        "workingHeightMeters": float(working_h),
        "rig": {
            "revision": "pme0-elf-male-slender-v1",
            "mode": "retargeted",
            "runtimeScale": float(factor),
            "positionPolicy": "bind-relative",
            "preserveRotations": True,
            "preserveTimingEvents": True,
            "sourcePrefix": "pmh0",
            "targetPrefix": "pme0",
            "supermodel": "pme0",
            "animationSupermodel": "a_ba",
            "frames": {
                "working": working_frames,
                "runtime": runtime_frames,
            }
        },
        "material": {
            "fixedGarmentParts": ["pelvis"]
        },
        "models": models,
    }

    validate(target_data)

    out = Path(output_config_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(target_data, indent=2) + "\n", encoding="utf-8")
    return target_data


def generate_orc_male_target(
    supermodel_path: Path | str = Path("output/phenotypes/derived-v1/masters/human-male-v1/stock/pmo0.mdl"),
    output_rig_path: Path | str = Path("output/phenotypes/derived-v1/rigs/orc-male/pmo0.mdl"),
    output_config_path: Path | str = CONFIG_DIR / "target-orc-male-fit.json"
) -> dict:
    """Generate, validate, and write the broad stock-measured Orc male target contract."""
    orc_text = read_mdl_text(supermodel_path)
    skel = nodes(orc_text)

    # Emit rig to output rigs dir
    rig_path = Path(output_rig_path).resolve()
    rig_path.parent.mkdir(parents=True, exist_ok=True)
    rig_path.write_text(orc_text, encoding="cp1252")

    xforms = transforms(skel)

    factor = 1.90 / 1.75  # ~1.0857142857142857
    working_h = 1.9339157
    runtime_h = working_h * factor

    working_frames = {}
    runtime_frames = {}

    for part, joint in PART_JOINTS.items():
        j_lower = joint.lower()
        require(j_lower in xforms, f"Missing joint '{joint}' in Orc rig")
        mat = xforms[j_lower]
        rot = mat[:3, :3]
        require(np.allclose(rot.T @ rot, np.eye(3), atol=1e-8), f"Non-orthogonal rotation in {joint}")
        require(abs(np.linalg.det(rot) - 1.0) < 1e-8, f"Non-proper rotation in {joint}")
        working_frames[j_lower] = mat.tolist()

        rmat = mat.copy()
        rmat[:3, 3] *= factor
        runtime_frames[j_lower] = rmat.tolist()

    models = {part: f"pmo0_{part}001" for part in PART_JOINTS}

    target_data = {
        "schemaVersion": 2,
        "kind": "phenotype-target",
        "id": "orc-male-fit",
        "identity": {
            "race": "orc",
            "gender": "male",
            "phenotype": 0,
            "prefix": "pmo0",
            "raceId": 5,
            "appearanceRow": 5,
        },
        "heightMeters": float(runtime_h),
        "workingHeightMeters": float(working_h),
        "rig": {
            "revision": "pmo0-orc-male-broad-v1",
            "mode": "retargeted",
            "runtimeScale": float(factor),
            "positionPolicy": "bind-relative",
            "preserveRotations": True,
            "preserveTimingEvents": True,
            "sourcePrefix": "pmh0",
            "targetPrefix": "pmo0",
            "supermodel": "pmo0",
            "animationSupermodel": "a_da",
            "frames": {
                "working": working_frames,
                "runtime": runtime_frames,
            }
        },
        "material": {
            "fixedGarmentParts": ["pelvis"]
        },
        "models": models,
    }

    validate(target_data)

    out = Path(output_config_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(target_data, indent=2) + "\n", encoding="utf-8")
    return target_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=str, default="orc-male-fit", choices=["dwarf-male-fit", "troll-male-fit", "elf-male-fit", "orc-male-fit"])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.target == "dwarf-male-fit":
        out = args.output or (CONFIG_DIR / "target-dwarf-male-stock.json")
        target = generate_dwarf_male_target(output_path=out)
        print(f"Generated target contract: {target['id']} -> {out}")
    elif args.target == "troll-male-fit":
        out = args.output or (CONFIG_DIR / "target-troll-male-fit.json")
        target = generate_troll_male_target(output_config_path=out)
        print(f"Generated target contract: {target['id']} -> {out}")
    elif args.target == "elf-male-fit":
        out = args.output or (CONFIG_DIR / "target-elf-male-fit.json")
        target = generate_elf_male_target(output_config_path=out)
        print(f"Generated target contract: {target['id']} -> {out}")
    elif args.target == "orc-male-fit":
        out = args.output or (CONFIG_DIR / "target-orc-male-fit.json")
        target = generate_orc_male_target(output_config_path=out)
        print(f"Generated target contract: {target['id']} -> {out}")


if __name__ == "__main__":
    main()
