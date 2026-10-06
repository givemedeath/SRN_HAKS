"""Inventory installed equipment styles and audit connector compatibility for derived phenotypes.

Audits stock dwarf armor compatibility with derived naked body parts and checks
weapon and shield dummy attachment frames.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from target_contract import require

sys.path.insert(0, str(REPO / "tools"))
from shared_tools import resolve_tool

GAME_ROOT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition")


def get_resman_grep() -> Path:
    return Path(resolve_tool("resman_grep", repo=REPO)["path"])

PARTS = [
    "chest", "pelvis", "belt", "neck",
    "bicepl", "bicepr", "forel", "forer",
    "handl", "handr", "legl", "legr",
    "shinl", "shinr", "footl", "footr",
    "shol", "shor", "robe", "cloak"
]


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_installed_styles(game_root: Path, user_dir: Path, prefix: str = "pmd0") -> dict:
    """Find every installed model for the target prefix in game data."""
    user_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(get_resman_grep()),
        "--root", str(game_root),
        "--userdirectory", str(user_dir),
        "-p", f"{prefix}_"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [line.strip().lower() for line in res.stdout.splitlines() if line.strip().endswith(".mdl")]

    inventory = {part: [] for part in PARTS}
    unclassified = []

    pattern = re.compile(rf"^{re.escape(prefix)}_([a-z]+)(\d+)\.mdl$")
    for name in lines:
        m = pattern.match(name)
        if m:
            part_name, style_num = m.group(1), int(m.group(2))
            if part_name in inventory:
                inventory[part_name].append({"model": name, "style": style_num})
            else:
                unclassified.append(name)
        else:
            unclassified.append(name)

    for p in inventory:
        inventory[p].sort(key=lambda x: x["style"])

    total_styles = sum(len(v) for v in inventory.values())
    return {
        "prefix": prefix,
        "totalModelsFound": len(lines),
        "totalClassifiedStyles": total_styles,
        "parts": inventory,
        "unclassified": unclassified
    }


def audit_hand_dummies(ascii_dir: Path, rig_path: Path, prefix: str = "pmd0", *, target_config: dict | None = None) -> dict:
    """Verify that hands and rig contain weapon and shield attachment dummies."""
    dummy_checks = {}

    handl_path = ascii_dir / f"{prefix}_handl001.mdl"
    handr_path = ascii_dir / f"{prefix}_handr001.mdl"

    require(handl_path.exists(), f"Missing {handl_path}")
    require(handr_path.exists(), f"Missing {handr_path}")
    require(rig_path.exists(), f"Missing rig {rig_path}")

    from derive_rig import read_mdl_text
    rig_text = read_mdl_text(rig_path)

    # Match exact dummy node names: "node dummy <node_name>"
    dummy_nodes = {
        m.strip().lower()
        for m in re.findall(r"(?mi)^\s*node\s+dummy\s+(\S+)", rig_text)
    }

    for p_name, path, hook in [("handl", handl_path, "lhand"), ("handr", handr_path, "rhand")]:
        text = path.read_text(encoding="cp1252")
        hook_lower = hook.lower()
        has_in_rig = hook_lower in dummy_nodes
        has_g_in_rig = f"{hook_lower}_g" in dummy_nodes
        dummy_checks[p_name] = {
            "model": path.name,
            "attachmentNode": hook,
            "gripFrame": f"{hook}_g",
            "rigGripPresent": has_g_in_rig,
            "rigAttachmentPresent": has_in_rig
        }

    if target_config is not None:
        from equipment_frames import verify_attachment_frames
        measured = verify_attachment_frames(rig_path, target_config)
        for hand, meta in dummy_checks.items():
            meta.update(measured[hand])
    return dummy_checks


def audit_stock_armor_compatibility(
    target_config: dict,
    derived_ascii_dir: Path,
    output_receipt: Path,
    game_root: Path | None = None,
    connector_audit_path: Path | None = None,
) -> dict:
    """Audit stock armor connector compatibility with derived parts."""
    prefix = target_config["identity"]["prefix"]
    race = target_config["identity"]["race"]
    frames = target_config["rig"]["frames"]["working"]

    inventory_root = game_root or (
        Path(os.environ["NWN_ROOT"]) if "NWN_ROOT" in os.environ and Path(os.environ["NWN_ROOT"]).exists()
        else GAME_ROOT
    )
    inventory_result = inventory_installed_styles(
        inventory_root,
        REPO / f"output/phenotypes/derived-{race}-male-v1/compiler-userdir",
        prefix=prefix
    )

    rig_path = REPO / f"output/phenotypes/derived-v1/rigs/{race}-male/{prefix}.mdl"
    dummies_result = audit_hand_dummies(derived_ascii_dir, rig_path, prefix=prefix, target_config=target_config)
    hand_dummies_valid = all(
        dummies_result.get(hand, {}).get("rigGripPresent", False)
        and dummies_result.get(hand, {}).get("rigAttachmentPresent", False)
        and dummies_result.get(hand, {}).get("attachmentFramesValid", False)
        for hand in ("handl", "handr")
    )
    require(hand_dummies_valid, f"Weapon/shield dummy check failed: {dummies_result}")

    # Validate that all required stock equipment parts are present
    required_parts = ["chest", "pelvis", "bicepl", "bicepr", "forel", "forer", "legl", "legr", "shinl", "shinr", "footl", "footr"]
    missing_stock = [p for p in required_parts if len(inventory_result["parts"][p]) == 0]
    require(len(missing_stock) == 0, f"Missing installed stock styles for parts: {missing_stock}")

    # Validate required bone attachment frames
    required_frames = [
        "torso_g", "lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
        "lhand_g", "rhand_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g"
    ]
    missing_frames = [f for f in required_frames if f not in frames]
    require(len(missing_frames) == 0, f"Missing required armor mount frames: {missing_frames}")

    # Require present, passing, target-bound connector audit evidence
    target_id = target_config.get("id", f"{race}-male-fit")
    if connector_audit_path is not None and Path(connector_audit_path).is_file():
        conn_audit_file = Path(connector_audit_path)
    else:
        candidate_paths = [
            derived_ascii_dir / "connector-audit.json",
            derived_ascii_dir.parent / "review" / "connector-audit.json",
            REPO / f"output/phenotypes/derived-{race}-male-v1/review/connector-audit.json",
        ]
        conn_audit_file = next((p for p in candidate_paths if p.is_file()), None)

    require(
        conn_audit_file is not None,
        f"Gate 3 requires a present connector audit receipt: missing connector-audit.json for target '{target_id}'"
    )

    conn_audit = json.loads(conn_audit_file.read_text(encoding="utf-8"))
    conn_target = conn_audit.get("targetId")
    if conn_target:
        require(
            conn_target == target_id,
            f"Connector audit target mismatch in {conn_audit_file}: expected '{target_id}', got '{conn_target}'"
        )

    audited_parts = conn_audit.get("parts", {})
    require(bool(audited_parts), f"Connector audit {conn_audit_file} missing parts metadata")
    for part_name, meta in audited_parts.items():
        model_name = meta.get("model", f"{prefix}_{part_name}001")
        model_file = derived_ascii_dir / f"{model_name}.mdl"
        require(
            model_file.is_file(),
            f"Gate 3 connector audit mismatch: model {model_file} not found in {derived_ascii_dir}",
        )
        current_sha = sha256_file(model_file)
        expected_sha = meta.get("sha256")
        require(
            current_sha == expected_sha,
            f"Gate 3 connector audit hash mismatch for {model_file}: expected {expected_sha}, got {current_sha}",
        )

    surfaces_preserved = bool(conn_audit.get("allConnectorsPassed", False))
    require(surfaces_preserved, f"Connector audit failed in {conn_audit_file}")
    overlap_status = "verified-positive" if surfaces_preserved else "failed-overlap"

    audit_complete = bool(len(missing_stock) == 0 and hand_dummies_valid and len(missing_frames) == 0 and surfaces_preserved)
    require(audit_complete, "Gate 3 equipment compatibility audit failed")

    receipt = {
        "schemaVersion": 1,
        "target": target_config.get("id", f"{race}-male-fit"),
        "prefix": prefix,
        "race": race,
        "rigMode": target_config["rig"].get("mode", "retargeted"),
        "stockArmorInventory": {
            part: len(inventory_result["parts"][part]) for part in PARTS
        },
        "totalInstalledModels": inventory_result["totalModelsFound"],
        "handDummies": dummies_result,
        "connectorCompatibility": {
            "policy": f"stock-family attachment: stock armor pieces mount directly to {prefix} bone frames",
            "stockConnectorSurfacesPreserved": surfaces_preserved,
            "measuredOverlapStatus": overlap_status
        },
        "complete": audit_complete
    }

    for meta in dummies_result.values():
        for path, expected in meta.get("inputHashes", {}).items():
            require(sha256_file(path) == expected, f"Equipment frame input changed: {path}")
    output_receipt.parent.mkdir(parents=True, exist_ok=True)
    output_receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"Wrote equipment compatibility receipt to {output_receipt}")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_pos", nargs="?", default=None, help="Target configuration JSON path (positional)")
    parser.add_argument("--config", type=Path, default=None, help="Target configuration JSON path")
    parser.add_argument("--target", type=Path, default=None, help="Target configuration JSON path")
    parser.add_argument("--race", type=str, default=None, help="Target race (e.g. dwarf, troll, elf, orc)")
    parser.add_argument("--gender", type=str, default="male", help="Target gender (default: male)")
    parser.add_argument("--game-root", type=Path, default=None, help="Path to NWN game installation root")
    parser.add_argument("--ascii-dir", type=Path, default=None)
    parser.add_argument("--connector-audit", type=Path, default=None, help="Explicit path to connector-audit.json")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    config_path = args.config or args.target or args.config_pos
    if config_path is None:
        if args.race:
            from derive_rig import resolve_target_config
            config_path = resolve_target_config(args.race, args.gender)
        else:
            config_path = REPO / "tools/phenotypes/configurations/derived/target-dwarf-male-stock.json"

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    race = config["identity"]["race"]
    ascii_dir = args.ascii_dir or (REPO / f"output/phenotypes/derived-v1/parts/{race}-male/ascii")
    output_path = args.output or (REPO / f"output/phenotypes/derived-{race}-male-v1/review/equipment-receipt.json")

    game_root = args.game_root or (
        Path(os.environ["NWN_ROOT"]) if "NWN_ROOT" in os.environ and Path(os.environ["NWN_ROOT"]).exists()
        else None
    )

    audit_stock_armor_compatibility(
        config,
        ascii_dir,
        output_path,
        game_root=game_root,
        connector_audit_path=args.connector_audit,
    )


if __name__ == "__main__":
    main()
