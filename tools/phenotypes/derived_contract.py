"""Validation and contract enforcement for derived phenotype targets."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from target_contract import load, validate, frame, model, PART_JOINTS, require


def load_derived_target(path: Path | str) -> dict:
    """Load and strictly validate a derived phenotype target file."""
    data = load(path, verify_inputs=False)
    require(data.get("schemaVersion") == 2, "Explicit schemaVersion 2 target required")
    require(data.get("kind") == "phenotype-target", "Explicit phenotype-target kind required")
    return data


def verify_target_frames(data: dict) -> bool:
    """Verify that all 16 body part frames exist in working and runtime spaces."""
    for space in ("working", "runtime"):
        frames = data["rig"]["frames"][space]
        for part, joint in PART_JOINTS.items():
            require(joint.lower() in frames, f"Missing {space} frame for joint {joint}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Path to target JSON file")
    args = parser.parse_args()

    data = load_derived_target(args.target)
    verify_target_frames(data)
    print(f"Derived target '{data['id']}' passed all contract checks.")
    print(f"  Prefix: {data['identity']['prefix']}, Gender: {data['identity']['gender']}, Phenotype: {data['identity']['phenotype']}")
    print(f"  Stature: {data['heightMeters']} m, Rig Mode: {data['rig']['mode']}")


if __name__ == "__main__":
    main()
