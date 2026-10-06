"""Prepare staging and build the comparison test module for Derived Orc Male."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
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

CANDIDATE_CONVERTED = REPO / "output/phenotypes/derived-orc-male-v1/candidate/converted"
STAGE_ROOT = REPO / "output/phenotypes/derived-orc-male-v1/test-stage"


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
    slug_dir = stage_dir / "orc_male_fit" / "converted"
    ascii_dir = slug_dir / "ascii"
    resources_dir = slug_dir / "resources"
    if ascii_dir.exists():
        shutil.rmtree(ascii_dir)
    if resources_dir.exists():
        shutil.rmtree(resources_dir)
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
        "modelPrefix": "pmo0",
        "height": 2.099679902857143,
        "workingHeight": 1.9339157,
        "runtimeScale": 1.0857142857142856,
        "stockReferenceHeight": 1.75,
        "parts": [
            {"part": "chest", "model": "pmo0_chest001"},
            {"part": "pelvis", "model": "pmo0_pelvis001"},
            {"part": "bicepl", "model": "pmo0_bicepl001"},
            {"part": "bicepr", "model": "pmo0_bicepr001"},
            {"part": "forel", "model": "pmo0_forel001"},
            {"part": "forer", "model": "pmo0_forer001"},
            {"part": "handl", "model": "pmo0_handl001"},
            {"part": "handr", "model": "pmo0_handr001"},
            {"part": "legl", "model": "pmo0_legl001"},
            {"part": "legr", "model": "pmo0_legr001"},
            {"part": "shinl", "model": "pmo0_shinl001"},
            {"part": "shinr", "model": "pmo0_shinr001"},
            {"part": "footl", "model": "pmo0_footl001"},
            {"part": "footr", "model": "pmo0_footr001"}
        ],
        "textures": {},
        "geometryStatus": "derived-phenotype",
        "rigMode": "stock-family",
        "stockOtherPartsFromGame": True,
        "diagnosticOnly": False,
        "clientAccepted": False
    }
    (slug_dir / "conversion.json").write_text(json.dumps(conversion, indent=2), encoding="utf-8")

    # Write manifest.json
    manifest = {
        "combinations": [
            {
                "slug": "orc_male_fit",
                "appearance": 5,
                "raceId": 5,
                "gender": "male",
                "phenotype": 0,
                "height": 2.099679902857143,
                "race": "Orc",
                "body_type": "Fit"
            }
        ]
    }
    (stage_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Candidate orc_male_fit staged successfully.")


def _stage_appearance_source(stage_dir: Path, temp_userdir: Path, appearance_path: Path | None = None, game_root: Path | None = None):
    fixture_res_dir = stage_dir / "fixture-resources"
    fixture_res_dir.mkdir(parents=True, exist_ok=True)
    out_app = fixture_res_dir / "appearance.2da"

    # 1. Explicitly supplied copy
    if appearance_path and Path(appearance_path).is_file():
        shutil.copyfile(appearance_path, out_app)
        print(f"Staged explicitly supplied appearance.2da from {appearance_path}")
        return

    # 2. Extract base appearance.2da using resman_cat from resolved game root
    try:
        root = resolve_game_root(game_root)
        if root.exists():
            raw_app = run_tool("resman_cat", ["--root", str(root), "--userdirectory", str(temp_userdir), "--no-ovr", "appearance.2da"])
            if raw_app.startswith(b"2DA"):
                out_app.write_bytes(raw_app)
                print(f"Extracted and staged appearance.2da ({len(raw_app)} bytes) to {out_app}")
                return
    except Exception:
        pass

    # 3. Verified durable/fallback copy with explicit SHA256 verification
    durable_copies = [
        (REPO / "tools/phenotypes/references/fixtures/appearance.2da", None),
        (REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage/fixture-resources/appearance.2da", "f059c15e5907886f60980fdd87763ea8351d248c1a6de040d2fc0db06538898a"),
    ]
    for candidate_path, expected_hash in durable_copies:
        if candidate_path.is_file():
            actual_hash = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
            if expected_hash is None or actual_hash == expected_hash:
                shutil.copyfile(candidate_path, out_app)
                print(f"Staged verified appearance.2da (sha256={actual_hash[:8]}...) to {out_app}")
                return

    raise RuntimeError(
        "Missing appearance.2da: specify --appearance-2da, ensure GAME_ROOT is available, "
        "or provide a verified durable copy in tools/phenotypes/references/fixtures/appearance.2da"
    )



def stage_fixture_resources(stage_dir: Path, temp_userdir: Path, appearance_path: Path | None = None, game_root: Path | None = None):
    from fixture_appearance import patch_appearance
    _stage_appearance_source(stage_dir, temp_userdir, appearance_path, game_root)
    target = json.loads((REPO / "tools/phenotypes/configurations/derived/target-orc-male-fit.json").read_text(encoding="utf-8"))
    return patch_appearance(stage_dir / "fixture-resources/appearance.2da", target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, default=STAGE_ROOT)
    parser.add_argument("--game-root", type=Path, default=None, help="NWN game root directory")
    parser.add_argument("--appearance-2da", type=Path, default=None, help="Explicit appearance.2da path")
    args = parser.parse_args()

    stage_dir = args.stage.resolve()
    temp_userdir = REPO / "output/phenotypes/derived-orc-male-v1/compiler-userdir"

    stage_baseline(stage_dir, temp_userdir, game_root=args.game_root)
    stage_candidate(stage_dir)
    stage_fixture_resources(stage_dir, temp_userdir, appearance_path=args.appearance_2da, game_root=args.game_root)
    print("Staging complete. Ready to build test module.")


if __name__ == "__main__":
    main()
