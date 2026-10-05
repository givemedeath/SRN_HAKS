"""Create a fixture-only stock Dwarf alias (pmz0) alongside overridden Dwarf assets.

Uses private dynamic race letter Z and a new appearance row in fixture-resources/appearance.2da.
Stock dwarf models, PLTs and supermodel remain unchanged apart from names.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import os

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from shared_tools import resolve_tool

MDLCOMP = REPO / "tools/vendor/nwnmdlcomp/nwnmdlcomp.exe"

PARTS = [
    "bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer",
    "handl", "handr", "head", "neck", "legl", "legr", "pelvis",
    "shinl", "shinr", "belt", "shol", "shor"
]


def resolve_game_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        p = Path(explicit).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified game root does not exist: {explicit}")
    env_root = os.environ.get("NWN_ROOT") or os.environ.get("NWN_GAME_ROOT")
    if env_root and Path(env_root).exists():
        return Path(env_root).resolve()
    for default_path in [
        Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Neverwinter Nights"),
    ]:
        if default_path.exists():
            return default_path
    raise FileNotFoundError("NWN game root not found. Please provide --game-root or set NWN_ROOT.")


def resolve_client(explicit: Path | None = None, game_root: Path | None = None) -> Path:
    if explicit is not None:
        p = Path(explicit).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified client binary does not exist: {explicit}")
    env_client = os.environ.get("NWN_CLIENT")
    if env_client and Path(env_client).exists():
        return Path(env_client).resolve()
    if game_root is not None:
        for candidate in [
            game_root / "bin/win32/nwmain.exe",
            game_root / "bin/linux-x86/nwmain",
            game_root / "nwmain.exe",
            game_root / "bin/win32/nwserver.exe",
        ]:
            if candidate.exists():
                return candidate.resolve()
    raise FileNotFoundError("NWN client binary not found. Please provide --client or ensure nwmain exists in game root.")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_stock_resource(name: str, temp_userdir: Path, game_root: Path) -> bytes:
    tool_path = resolve_tool("resman_cat", repo=REPO)["path"]
    res = subprocess.run([tool_path, "--root", str(game_root), "--userdirectory", str(temp_userdir), "--no-ovr", name],
                         capture_output=True, check=True)
    return res.stdout


def decompile_model(bin_path: Path, ascii_path: Path):
    data = bin_path.read_bytes()
    if data[:4] != b"\0\0\0\0":
        # Already ASCII
        ascii_path.write_bytes(data)
    else:
        subprocess.run([str(MDLCOMP), "-d", "-e", str(bin_path), str(ascii_path)], check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage")
    parser.add_argument("--game-root", type=Path, default=None, help="Path to NWN game installation root")
    parser.add_argument("--client", type=Path, default=None, help="Path to nwmain.exe client binary")
    args = parser.parse_args()

    game_root = resolve_game_root(args.game_root)
    client = resolve_client(args.client, game_root)

    stage_dir = args.output.resolve()
    slug = "stock_dwarf_male_fit"
    converted = stage_dir / slug / "converted"
    ascii_dir = converted / "ascii"
    resources_dir = converted / "resources"
    ascii_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = stage_dir / "temp_stock"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_userdir = stage_dir / "compiler-stock-userdir"
    temp_userdir.mkdir(parents=True, exist_ok=True)

    receipt = []
    # 1. Root supermodel pmd0.mdl -> pmz0.mdl
    raw_root = extract_stock_resource("pmd0.mdl", temp_userdir, game_root)
    (temp_dir / "pmd0.mdl").write_bytes(raw_root)
    decompile_model(temp_dir / "pmd0.mdl", temp_dir / "pmd0_ascii.mdl")
    root_ascii = (temp_dir / "pmd0_ascii.mdl").read_text(encoding="cp1252").replace("pmd0", "pmz0")
    (ascii_dir / "pmz0.mdl").write_text(root_ascii, encoding="cp1252")
    receipt.append({"source": "pmd0.mdl", "alias": "pmz0.mdl", "sha256": digest(ascii_dir / "pmz0.mdl")})

    # 2. Body parts
    for part in PARTS:
        source_name = f"pmd0_{part}001"
        alias_name = f"pmz0_{part}001"

        # Decompile and inspect bitmap
        raw_mdl = extract_stock_resource(f"{source_name}.mdl", temp_userdir, game_root)
        (temp_dir / f"{source_name}.mdl").write_bytes(raw_mdl)
        decompile_model(temp_dir / f"{source_name}.mdl", temp_dir / f"{source_name}_ascii.mdl")
        original_ascii = (temp_dir / f"{source_name}_ascii.mdl").read_text(encoding="cp1252")

        bitmaps = [b for b in re.findall(r"(?mi)^\s*bitmap\s+(\S+)", original_ascii) if b.lower() != "null"]
        bitmap_source = bitmaps[0] if bitmaps else source_name

        mdl_text = original_ascii.replace("pmd0", "pmz0")
        mdl_text = re.sub(r"(?mi)^\s*bitmap\s+\S+", f"  bitmap {alias_name}", mdl_text)
        (ascii_dir / f"{alias_name}.mdl").write_text(mdl_text, encoding="cp1252")

        # Extract source PLT
        try:
            raw_plt = extract_stock_resource(f"{bitmap_source}.plt", temp_userdir, game_root)
        except Exception:
            # Fallback to srn_body or source_name
            if (REPO / f"srn_body/{bitmap_source}.plt").exists():
                raw_plt = (REPO / f"srn_body/{bitmap_source}.plt").read_bytes()
            else:
                raw_plt = extract_stock_resource(f"{source_name}.plt", temp_userdir, game_root)
        (resources_dir / f"{alias_name}.plt").write_bytes(raw_plt)

        receipt.append({
            "part": part,
            "sourceModel": f"{source_name}.mdl",
            "aliasModel": f"{alias_name}.mdl",
            "modelSha256": digest(ascii_dir / f"{alias_name}.mdl"),
            "pltSha256": digest(resources_dir / f"{alias_name}.plt")
        })

    # 3. Native compile the stock alias models
    print(f"Staged {len(receipt)} stock alias models. Compiling with nwmain...")
    compile_cmd = [
        sys.executable,
        str(REPO / "tools/phenotypes/native_compile.py"),
        "--client", str(client),
        "--user-directory", str(temp_userdir),
        "--converted", str(converted),
        "--without-material-resources",
        "--timeout", "180"
    ]
    subprocess.run(compile_cmd, check=True)

    # 4. appearance.2da fixture resource
    raw_app = extract_stock_resource("appearance.2da", temp_userdir, game_root).decode("cp1252")
    lines = [l for l in raw_app.splitlines() if l.strip()]
    header_lines = [l for l in lines if not re.match(r"^\s*\d+\s", l)]
    data_lines = [l for l in lines if re.match(r"^\s*\d+\s", l)]

    cols = header_lines[-1].split()
    row_0 = data_lines[0].split()  # Dwarf row 0
    row_id = len(data_lines)

    new_row = list(row_0[1:])  # drop index
    new_row[cols.index("LABEL")] = "SR_StockDwarfControl"
    new_row[cols.index("STRING_REF")] = "****"
    new_row[cols.index("RACE")] = "Z"

    fixture_res = stage_dir / "fixture-resources"
    fixture_res.mkdir(parents=True, exist_ok=True)
    new_app_text = "\n".join(header_lines) + "\n" + "\n".join(data_lines) + "\n" + f"{row_id} " + " ".join(new_row) + "\n"
    (fixture_res / "appearance.2da").write_text(new_app_text, encoding="cp1252")

    # 5. conversion.json
    conversion = {
        "modelPrefix": "pmz0",
        "height": 1.473,
        "parts": [],
        "textures": {},
        "geometryStatus": "stock-control",
        "fixtureControl": True,
        "stockAliases": receipt
    }
    (converted / "conversion.json").write_text(json.dumps(conversion, indent=2), encoding="utf-8")

    # 6. Update manifest.json
    manifest_path = stage_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["combinations"].append({
        "slug": slug,
        "appearance": row_id,
        "raceId": 0,
        "gender": "male",
        "phenotype": 0,
        "fixtureControl": True,
        "height": 1.473,
        "race": "Stock Dwarf",
        "body_type": "Fit"
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Cleanup temp
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"Stock dwarf control staged successfully as row {row_id} with prefix pmz0.")


if __name__ == "__main__":
    main()
