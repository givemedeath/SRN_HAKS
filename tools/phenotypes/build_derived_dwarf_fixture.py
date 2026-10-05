"""Prepare staging and build the comparison test module for Derived Dwarf Male."""
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
from shared_tools import resolve_tool

GAME_ROOT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition")
PYTHON = Path(sys.executable)

CANDIDATE_CONVERTED = REPO / "output/phenotypes/derived-dwarf-male-v1/candidate/converted"
STAGE_ROOT = REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage"


def run_tool(name: str, args: list[str]) -> bytes:
    tool_path = resolve_tool(name, repo=REPO)["path"]
    res = subprocess.run([tool_path, *args], capture_output=True, check=True)
    return res.stdout


def stage_baseline(stage_dir: Path, temp_userdir: Path):
    baseline_dir = stage_dir / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    # 1. ttr01.set
    set_data = run_tool("resman_cat", ["--root", str(GAME_ROOT), "--userdirectory", str(temp_userdir), "--no-ovr", "ttr01.set"])
    (baseline_dir / "ttr01.set").write_bytes(set_data)

    # 2. ttr01_edge.2da
    edge_data = run_tool("resman_cat", ["--root", str(GAME_ROOT), "--userdirectory", str(temp_userdir), "--no-ovr", "ttr01_edge.2da"])
    (baseline_dir / "ttr01_edge.2da").write_bytes(edge_data)

    # 3. human-template.json (from nw_commale.utc)
    raw_utc = run_tool("resman_cat", ["--root", str(GAME_ROOT), "--userdirectory", str(temp_userdir), "--no-ovr", "nw_commale.utc"])
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
    slug_dir = stage_dir / "dwarf_male_fit" / "converted"
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
        "modelPrefix": "pmd0",
        "height": 1.4864,
        "stockReferenceHeight": 1.473,
        "parts": [
            {"part": "chest", "model": "pmd0_chest001"},
            {"part": "pelvis", "model": "pmd0_pelvis001"},
            {"part": "bicepl", "model": "pmd0_bicepl001"},
            {"part": "bicepr", "model": "pmd0_bicepr001"},
            {"part": "forel", "model": "pmd0_forel001"},
            {"part": "forer", "model": "pmd0_forer001"},
            {"part": "handl", "model": "pmd0_handl001"},
            {"part": "handr", "model": "pmd0_handr001"},
            {"part": "legl", "model": "pmd0_legl001"},
            {"part": "legr", "model": "pmd0_legr001"},
            {"part": "shinl", "model": "pmd0_shinl001"},
            {"part": "shinr", "model": "pmd0_shinr001"},
            {"part": "footl", "model": "pmd0_footl001"},
            {"part": "footr", "model": "pmd0_footr001"}
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
                "slug": "dwarf_male_fit",
                "appearance": 0,
                "raceId": 0,
                "gender": "male",
                "phenotype": 0,
                "height": 1.4864,
                "race": "Dwarf",
                "body_type": "Fit"
            }
        ]
    }
    (stage_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Candidate dwarf_male_fit staged successfully.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, default=STAGE_ROOT)
    args = parser.parse_args()

    stage_dir = args.stage.resolve()
    temp_userdir = REPO / "output/phenotypes/derived-dwarf-male-v1/compiler-userdir"

    stage_baseline(stage_dir, temp_userdir)
    stage_candidate(stage_dir)
    print("Staging complete. Ready to build test module.")


if __name__ == "__main__":
    main()
