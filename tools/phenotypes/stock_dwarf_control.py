"""Create a race-correct fixture-only stock alias (pmz0) alongside derived assets.

Uses private dynamic race letter Z and a new appearance row in fixture-resources/appearance.2da.
Troll uses the unchanged Human donor baseline. Stock resources retain their sizing.
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
    for bindings_path in [
        REPO / ".tools/runtime_bindings.json",
        REPO / ".tools/runtime-bindings.json",
        REPO / "runtime_bindings.json",
    ]:
        if bindings_path.exists():
            try:
                bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
                candidate = bindings.get("game_root") or bindings.get("nwn_root") or bindings.get("NWN_ROOT")
                if candidate and Path(candidate).exists():
                    return Path(candidate).resolve()
            except Exception:
                pass
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


CONTROL_SOURCES = {
    "dwarf": {"race": "dwarf", "prefix": "pmd0", "appearance": 0, "raceId": 0, "height": 1.4864},
    "elf": {"race": "elf", "prefix": "pme0", "appearance": 1, "raceId": 1, "height": 1.9339157},
    "orc": {"race": "orc", "prefix": "pmo0", "appearance": 5, "raceId": 5, "height": 1.9339157},
    "human": {"race": "human", "prefix": "pmh0", "appearance": 6, "raceId": 6, "height": 1.9339157},
    "troll": {"race": "human", "prefix": "pmh0", "appearance": 6, "raceId": 6, "height": 1.9339157},
}


def stage_stock_control(stage_dir: Path, game_root: Path, client: Path, race: str = "dwarf", *, manifest_input: Path | None = None, appearance_input: Path | None = None):
    source = CONTROL_SOURCES[race]
    source_prefix = source["prefix"]
    alias_prefix = "pmz0"
    stage_dir = stage_dir.resolve()
    if bool(manifest_input) != bool(appearance_input):
        raise ValueError("Supply both immutable manifest and appearance inputs")
    manifest_path = stage_dir / "manifest.json"
    appearance_path = stage_dir / "fixture-resources/appearance.2da"
    live_pins = {p: digest(p) for p in (manifest_path, appearance_path) if p.exists()}
    manifest_source = manifest_input or manifest_path
    appearance_source = appearance_input or appearance_path
    manifest_bytes = manifest_source.read_bytes()
    appearance_bytes = appearance_source.read_bytes() if appearance_source.exists() else None
    manifest = json.loads(manifest_bytes)
    frozen_sources = {manifest_source: hashlib.sha256(manifest_bytes).hexdigest()}
    if appearance_bytes is not None:
        frozen_sources[appearance_source] = hashlib.sha256(appearance_bytes).hexdigest()
    # Snapshot inputs must match the live stage they are authorized to replace.
    if manifest_input:
        for live, frozen in ((manifest_path, manifest_source), (appearance_path, appearance_source)):
            if live not in live_pins or live_pins[live] != frozen_sources[frozen]:
                raise ValueError(f"Stock-control input snapshot differs from live stage: {live}")
    slug = f"stock_{source['race']}_male_fit"
    converted = stage_dir / slug / "converted"
    ascii_dir = converted / "ascii"
    resources_dir = converted / "resources"
    for directory in (ascii_dir, resources_dir):
        if directory.exists():
            shutil.rmtree(directory)
    ascii_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = stage_dir / "temp_stock"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_userdir = stage_dir / "compiler-stock-userdir"
    temp_userdir.mkdir(parents=True, exist_ok=True)

    receipt = []
    # 1. Selected stock-family root -> private pmz0 alias
    raw_root = extract_stock_resource(source_prefix + ".mdl", temp_userdir, game_root)
    (temp_dir / (source_prefix + ".mdl")).write_bytes(raw_root)
    decompile_model(temp_dir / (source_prefix + ".mdl"), temp_dir / (source_prefix + "_ascii.mdl"))
    root_ascii = (temp_dir / (source_prefix + "_ascii.mdl")).read_text(encoding="cp1252").replace(source_prefix, alias_prefix)
    (ascii_dir / "pmz0.mdl").write_text(root_ascii, encoding="cp1252")
    receipt.append({"source": source_prefix + ".mdl", "sourceSha256": hashlib.sha256(raw_root).hexdigest(), "alias": "pmz0.mdl", "sha256": digest(ascii_dir / "pmz0.mdl")})

    # 2. Body parts
    for part in PARTS:
        source_name = f"{source_prefix}_{part}001"
        alias_name = f"pmz0_{part}001"

        # Decompile and inspect bitmap
        raw_mdl = extract_stock_resource(f"{source_name}.mdl", temp_userdir, game_root)
        (temp_dir / f"{source_name}.mdl").write_bytes(raw_mdl)
        decompile_model(temp_dir / f"{source_name}.mdl", temp_dir / f"{source_name}_ascii.mdl")
        original_ascii = (temp_dir / f"{source_name}_ascii.mdl").read_text(encoding="cp1252")

        # Collect distinct non-null bitmaps
        bitmaps = [b for b in re.findall(r"(?mi)^\s*bitmap\s+(\S+)", original_ascii) if b.lower() != "null"]
        distinct_bitmaps = []
        for b in bitmaps:
            if b not in distinct_bitmaps:
                distinct_bitmaps.append(b)

        # Build alias mapping for each bitmap:
        # Alias source-family bitmaps to pmz0; preserve shared palette names
        bitmap_aliases = {}
        for bmp in distinct_bitmaps:
            if bmp.lower().startswith(source_prefix):
                aliased_bmp = f"pmz0{bmp[4:]}"
            else:
                aliased_bmp = bmp
            bitmap_aliases[bmp] = aliased_bmp

            # Extract source PLT and write to resources_dir as {aliased_bmp}.plt
            try:
                raw_plt = extract_stock_resource(f"{bmp}.plt", temp_userdir, game_root)
            except Exception:
                if (REPO / f"srn_body/{bmp}.plt").exists():
                    raw_plt = (REPO / f"srn_body/{bmp}.plt").read_bytes()
                elif (REPO / f"srn_body/{aliased_bmp}.plt").exists():
                    raw_plt = (REPO / f"srn_body/{aliased_bmp}.plt").read_bytes()
                else:
                    raw_plt = extract_stock_resource(f"{source_name}.plt", temp_userdir, game_root)
            (resources_dir / f"{aliased_bmp}.plt").write_bytes(raw_plt)

        # Ensure primary part alias PLT exists if referenced
        primary_plt = resources_dir / f"{alias_name}.plt"
        if not primary_plt.exists() and distinct_bitmaps:
            first_alias_plt = resources_dir / f"{bitmap_aliases[distinct_bitmaps[0]]}.plt"
            if first_alias_plt.exists():
                shutil.copy2(first_alias_plt, primary_plt)

        # Rename source-family skeleton/nodes and their palette references
        mdl_text = original_ascii.replace(source_prefix, alias_prefix)
        def replace_bitmap(m):
            orig = m.group(1)
            if orig.lower() == "null":
                return m.group(0)
            return f"  bitmap {bitmap_aliases.get(orig, orig)}"

        mdl_text = re.sub(r"(?mi)^\s*bitmap\s+(\S+)", replace_bitmap, mdl_text)
        (ascii_dir / f"{alias_name}.mdl").write_text(mdl_text, encoding="cp1252")

        receipt.append({
            "part": part,
            "sourceModel": f"{source_name}.mdl",
            "sourceModelSha256": hashlib.sha256(raw_mdl).hexdigest(),
            "aliasModel": f"{alias_name}.mdl",
            "modelSha256": digest(ascii_dir / f"{alias_name}.mdl"),
            "pltSha256": digest(primary_plt) if primary_plt.exists() else None,
            "bitmaps": {
                bmp: {
                    "alias": alias_bmp,
                    "pltSha256": digest(resources_dir / f"{alias_bmp}.plt")
                }
                for bmp, alias_bmp in bitmap_aliases.items()
            }
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

    # Keep the target's patched appearance row; take the comparator row from
    # the unmodified installed table so the stock control is never target-scaled.
    raw_app = extract_stock_resource("appearance.2da", temp_userdir, game_root).decode("cp1252")
    fixture_res = stage_dir / "fixture-resources"
    appearance_path = fixture_res / "appearance.2da"
    if any(digest(path) != pin for path, pin in frozen_sources.items()):
        raise ValueError("Stock-control consumed input changed during compilation")
    if any(not path.exists() or digest(path) != pin for path, pin in live_pins.items()):
        raise ValueError("Stock-control live stage changed during compilation")
    row_id = stage_control_appearance(appearance_path, raw_app, source,
                                     fixture_text=appearance_bytes.decode("cp1252") if appearance_bytes is not None else None)

    # 5. conversion.json
    conversion = {
        "modelPrefix": "pmz0",
        "height": source["height"],
        "sourceRace": source["race"],
        "sourcePrefix": source_prefix,
        "sourceAppearance": source["appearance"],
        "controlTargetRace": race,
        "parts": [],
        "textures": {},
        "geometryStatus": "stock-control",
        "fixtureControl": True,
        "stockAliases": receipt
    }
    (converted / "conversion.json").write_text(json.dumps(conversion, indent=2), encoding="utf-8")

    # 6. Update manifest.json
    owned_slugs = {f"stock_{data['race']}_male_fit" for data in CONTROL_SOURCES.values()}
    manifest["combinations"] = [r for r in manifest["combinations"] if r.get("slug") not in owned_slugs]
    manifest["combinations"].append({
        "slug": slug,
        "appearance": row_id,
        "raceId": source["raceId"],
        "gender": "male",
        "phenotype": 0,
        "fixtureControl": True,
        "height": source["height"],
        "sourceRace": source["race"],
        "sourcePrefix": source_prefix,
        "sourceAppearance": source["appearance"],
        "controlTargetRace": race,
        "race": "Stock " + source["race"].title(),
        "body_type": "Fit"
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Cleanup temp
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"Stock {source['race']} control staged successfully as row {row_id} with prefix pmz0.")


def stage_control_appearance(path: Path, stock_text: str, source: dict, *, fixture_text: str | None = None) -> int:
    def parse(text):
        lines = [line for line in text.splitlines() if line.strip()]
        headers = [line for line in lines if not re.match(r"^\s*\d+\s", line)]
        rows = [line for line in lines if re.match(r"^\s*\d+\s", line)]
        if not headers or not rows:
            raise ValueError("Missing appearance header or rows")
        return headers, rows, headers[-1].split()
    stock_headers, stock_rows, stock_cols = parse(stock_text)
    source_rows = [line.split()[1:] for line in stock_rows if line.split()[0] == str(source["appearance"])]
    if len(source_rows) != 1 or len(source_rows[0]) != len(stock_cols):
        raise ValueError("Missing or malformed stock source appearance row")
    headers, rows, columns = parse(fixture_text if fixture_text is not None else (path.read_text(encoding="cp1252") if path.exists() else stock_text))
    if columns != stock_cols or not {"LABEL", "STRING_REF", "RACE"}.issubset(columns):
        raise ValueError("Incompatible stock and fixture appearance columns")
    # Replace the private Z row on a rerun, preserving its ID and all target rows.
    old_controls = [line for line in rows if len(line.split()) == len(columns) + 1 and line.split()[1 + columns.index("RACE")] == "Z"]
    if len(old_controls) > 1:
        raise ValueError("Multiple private stock-control appearance rows")
    row_id = int(old_controls[0].split()[0]) if old_controls else max(int(line.split()[0]) for line in rows) + 1
    rows = [line for line in rows if line not in old_controls]
    values = source_rows[0]
    values[columns.index("LABEL")] = "SR_Stock" + source["race"].title() + "Control"
    values[columns.index("STRING_REF")] = "****"
    values[columns.index("RACE")] = "Z"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(headers + rows + [str(row_id) + " " + " ".join(values)]) + "\n", encoding="cp1252")
    return row_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", choices=CONTROL_SOURCES, default="dwarf", help="Derived target race; Troll compares to the stock Human donor")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--client", type=Path)
    parser.add_argument("--manifest-input", type=Path, help="Immutable snapshot of the input manifest")
    parser.add_argument("--appearance-input", type=Path, help="Immutable snapshot of the patched fixture table")
    args = parser.parse_args()
    game_root = resolve_game_root(args.game_root)
    client = resolve_client(args.client, game_root)
    output = args.output or REPO / f"output/phenotypes/derived-{args.race}-male-v1/test-stage"
    stage_stock_control(output, game_root, client, args.race, manifest_input=args.manifest_input, appearance_input=args.appearance_input)


if __name__ == "__main__":
    main()
