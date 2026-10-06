"""Prepare staging and build the comparison test module for Derived Troll Male."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared_tools import resolve_tool
from stock_dwarf_control import resolve_game_root

DEFAULT_GAME_ROOT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition")
PYTHON = Path(sys.executable)

CANDIDATE_CONVERTED = REPO / "output/phenotypes/derived-troll-male-v1/candidate/converted"
STAGE_ROOT = REPO / "output/phenotypes/derived-troll-male-v1/test-stage"


def run_tool(name: str, args: list[str]) -> bytes:
    tool_path = resolve_tool(name, repo=REPO)["path"]
    res = subprocess.run([tool_path, *args], capture_output=True, check=True)
    return res.stdout


def stage_baseline(stage_dir: Path, temp_userdir: Path, game_root: Path | None = None):
    baseline_dir = stage_dir / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    root = resolve_game_root(game_root)

    # 1. ttr01.set
    set_data = run_tool("resman_cat", ["--root", str(root), "--userdirectory", str(temp_userdir), "--no-ovr", "ttr01.set"])
    (baseline_dir / "ttr01.set").write_bytes(set_data)

    # 2. ttr01_edge.2da
    edge_data = run_tool("resman_cat", ["--root", str(root), "--userdirectory", str(temp_userdir), "--no-ovr", "ttr01_edge.2da"])
    (baseline_dir / "ttr01_edge.2da").write_bytes(edge_data)

    # 3. human-template.json (from nw_commale.utc)
    raw_utc = run_tool("resman_cat", ["--root", str(root), "--userdirectory", str(temp_userdir), "--no-ovr", "nw_commale.utc"])
    temp_utc = stage_dir / "temp_peasant.utc"
    temp_json = stage_dir / "temp_peasant.utc.json"
    temp_utc.write_bytes(raw_utc)
    gff_tool = resolve_tool("gff", repo=REPO)["path"]
    subprocess.run([gff_tool, "-i", str(temp_utc), "-o", str(temp_json)], check=True)
    shutil.copyfile(temp_json, baseline_dir / "human-template.json")
    temp_utc.unlink(missing_ok=True)
    temp_json.unlink(missing_ok=True)
    print("Baseline fixture resources staged successfully.")


def stage_candidate(stage_dir: Path):
    slug_dir = stage_dir / "troll_male_fit" / "converted"
    ascii_dir = slug_dir / "ascii"
    resources_dir = slug_dir / "resources"
    ascii_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Copy ASCII models
    for p in (CANDIDATE_CONVERTED / "ascii").glob("*.mdl"):
        shutil.copyfile(p, ascii_dir / p.name)

    # Copy compiled resources (mdl, plt, mtr, tga)
    for p in (CANDIDATE_CONVERTED / "resources").iterdir():
        if p.is_file():
            shutil.copyfile(p, resources_dir / p.name)

    # Copy native-compile.json
    shutil.copyfile(CANDIDATE_CONVERTED / "native-compile.json", slug_dir / "native-compile.json")

    # Write conversion.json
    conversion = {
        "modelPrefix": "pmg0",
        "height": 2.7627367,
        "workingHeight": 1.9339157,
        "runtimeScale": 1.4285714285714286,
        "stockReferenceHeight": 1.0668,
        "parts": [
            {"part": "chest", "model": "pmg0_chest001"},
            {"part": "pelvis", "model": "pmg0_pelvis001"},
            {"part": "bicepl", "model": "pmg0_bicepl001"},
            {"part": "bicepr", "model": "pmg0_bicepr001"},
            {"part": "forel", "model": "pmg0_forel001"},
            {"part": "forer", "model": "pmg0_forer001"},
            {"part": "handl", "model": "pmg0_handl001"},
            {"part": "handr", "model": "pmg0_handr001"},
            {"part": "legl", "model": "pmg0_legl001"},
            {"part": "legr", "model": "pmg0_legr001"},
            {"part": "shinl", "model": "pmg0_shinl001"},
            {"part": "shinr", "model": "pmg0_shinr001"},
            {"part": "footl", "model": "pmg0_footl001"},
            {"part": "footr", "model": "pmg0_footr001"}
        ],
        "textures": {},
        "geometryStatus": "derived-phenotype",
        "rigMode": "retargeted",
        "stockOtherPartsFromGame": False,
        "diagnosticOnly": False,
        "clientAccepted": False
    }
    (slug_dir / "conversion.json").write_text(json.dumps(conversion, indent=2), encoding="utf-8")

    # Write manifest.json
    manifest = {
        "combinations": [
            {
                "slug": "troll_male_fit",
                "appearance": 2,
                "raceId": 2,
                "gender": "male",
                "phenotype": 0,
                "height": 2.7627367,
                "runtimeScale": 1.4285714285714286,
                "race": "Troll",
                "body_type": "Fit"
            }
        ]
    }
    (stage_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Candidate troll_male_fit staged successfully.")


def stage_fixture_resources(stage_dir: Path, temp_userdir: Path, appearance_path: Path | None = None, game_root: Path | None = None) -> str:
    fixture_res_dir = stage_dir / "fixture-resources"
    fixture_res_dir.mkdir(parents=True, exist_ok=True)
    out_app = fixture_res_dir / "appearance.2da"
    staged_base = False

    # 1. Explicitly supplied copy
    if appearance_path and Path(appearance_path).is_file():
        shutil.copyfile(appearance_path, out_app)
        staged_base = True
        print(f"Staged explicitly supplied appearance.2da from {appearance_path}")

    # 2. Extract base appearance.2da using resman_cat from resolved game root
    if not staged_base:
        try:
            root = resolve_game_root(game_root)
            if root.exists():
                raw_app = run_tool("resman_cat", ["--root", str(root), "--userdirectory", str(temp_userdir), "--no-ovr", "appearance.2da"])
                if raw_app.startswith(b"2DA"):
                    out_app.write_bytes(raw_app)
                    staged_base = True
                    print(f"Extracted and staged appearance.2da ({len(raw_app)} bytes) to {out_app}")
        except Exception:
            pass

    # 3. Verified durable/fallback copy with explicit SHA256 verification
    if not staged_base:
        durable_copies = [
            (REPO / "tools/phenotypes/references/fixtures/appearance.2da", None),
            (REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage/fixture-resources/appearance.2da", None),
        ]
        for candidate_path, expected_hash in durable_copies:
            if candidate_path.is_file():
                actual_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
                if expected_hash is None or actual_hash == expected_hash:
                    shutil.copyfile(candidate_path, out_app)
                    staged_base = True
                    print(f"Staged base appearance.2da (sha256={actual_hash[:8]}...) to {out_app}")
                    break

    if not staged_base:
        raise RuntimeError(
            "Missing appearance.2da: specify --appearance-2da, ensure GAME_ROOT is available, "
            "or provide a verified durable copy in tools/phenotypes/references/fixtures/appearance.2da"
        )

    # Patch Gnome replacement row (row 2) with Troll runtime scale
    runtime_scale = 10.0 / 7.0  # 1.4285714285714286
    raw_text = out_app.read_text(encoding="cp1252")
    lines = [l for l in raw_text.splitlines() if l.strip()]
    header_lines = [l for l in lines if not re.match(r"^\s*\d+\s", l)]
    data_lines = [l for l in lines if re.match(r"^\s*\d+\s", l)]
    cols = header_lines[-1].split()

    if not cols:
        raise RuntimeError(f"Missing or invalid 2DA header columns in appearance.2da at {out_app}")

    required_scale_cols = ["HEIGHT", "SIZECATEGORY", "WEAPONSCALE", "WALKDIST", "RUNDIST"]
    missing_cols = [c for c in required_scale_cols if c not in cols]
    if missing_cols:
        raise RuntimeError(f"Missing required scale columns {missing_cols} in appearance.2da at {out_app}")

    row_2_idx = None
    for idx, dl in enumerate(data_lines):
        parts = dl.split()
        if parts and parts[0] == "2":
            row_2_idx = idx
            break

    if row_2_idx is None:
        raise RuntimeError(f"Failed to find Gnome appearance row (row 2) in {out_app}; cannot apply Troll runtime scale")

    parts = data_lines[row_2_idx].split()
    row_id = parts[0]
    row_vals = list(parts[1:])
    col_patches = {
        "LABEL": "Troll",
        "HEIGHT": "2.7627",
        "SIZECATEGORY": "4",
        "WEAPONSCALE": f"{1.0 * runtime_scale:.5f}",
        "WING_TAIL_SCALE": f"{1.0 * runtime_scale:.5f}",
        "HELMET_SCALE_M": f"{0.9 * runtime_scale:.5f}",
        "HELMET_SCALE_F": f"{0.82 * runtime_scale:.5f}",
        "WALKDIST": f"{1.0 * runtime_scale:.5f}",
        "RUNDIST": f"{1.94 * runtime_scale:.5f}",
        "CREPERSPACE": f"{0.4 * runtime_scale:.5f}",
        "PREFATCKDIST": f"{1.3 * runtime_scale:.5f}",
    }
    for col_name, val in col_patches.items():
        if col_name in cols:
            row_vals[cols.index(col_name)] = val

    data_lines[row_2_idx] = f"{row_id:<6}" + " ".join(f"{v:<12}" for v in row_vals)
    new_app_text = "\n".join(header_lines) + "\n" + "\n".join(data_lines) + "\n"
    out_app.write_text(new_app_text, encoding="cp1252")
    patched_hash = hashlib.sha256(out_app.read_bytes()).hexdigest()
    print(f"Patched Gnome row (row 2) with Troll runtime scale ({runtime_scale:.6f}) in {out_app} (sha256={patched_hash})")
    return patched_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, default=STAGE_ROOT)
    parser.add_argument("--game-root", type=Path, default=None, help="NWN game root directory")
    parser.add_argument("--appearance-2da", type=Path, default=None, help="Explicit appearance.2da path")
    args = parser.parse_args()

    stage_dir = args.stage.resolve()
    temp_userdir = REPO / "output/phenotypes/derived-troll-male-v1/compiler-userdir"

    stage_baseline(stage_dir, temp_userdir, game_root=args.game_root)
    stage_candidate(stage_dir)
    app_hash = stage_fixture_resources(stage_dir, temp_userdir, appearance_path=args.appearance_2da, game_root=args.game_root)
    receipt = {
        "schemaVersion": 1,
        "kind": "derived-troll-fixture-staging-receipt",
        "stage": str(stage_dir),
        "runtimeScale": 1.4285714285714286,
        "targetHeight": 2.7627367,
        "appearanceResourceSha256": app_hash,
        "status": "staged-verified",
    }
    (stage_dir / "fixture-staging-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("Staging complete. Ready to build test module.")


if __name__ == "__main__":
    main()
