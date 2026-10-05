"""Extract installed NWN baselines and inventory their animation chains.

Extracted game resources stay in ignored output/, never in tracked tool sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tool_runtime import tool as resolved_tool

from pipeline import RACES, digest, save_json

PARTS = ("belt", "bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer",
         "handl", "handr", "head", "legl", "legr", "neck", "pelvis", "shinl", "shinr", "shol", "shor")
COMPILER_SHA256 = "0e32070c3e00a07a5f9e93b7e4a63a40dd5486b974900bbb8a0d2f4424c612bb"


def head_inventory(available):
    union, by_phenotype = {}, {}
    for race, family in RACES.items():
        for sex in "mf":
            key = f"{race}_{sex}"
            by_phenotype[key] = {str(p): sorted({int(m[1]) for r in available
                if (m := re.fullmatch(f"p{sex}{family['family']}{p}_head([0-9]{{3}})\\.mdl", r))}) for p in (0,2)}
            union[key] = sorted(set(by_phenotype[key]["0"]) | set(by_phenotype[key]["2"]))
    return union, by_phenotype


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--user-directory", type=Path, required=True)
    parser.add_argument("--tool-directory", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/phenotypes/baseline"))
    args = parser.parse_args()
    output = args.output.resolve()
    raw = output / "raw"
    ascii_dir = output / "ascii"
    raw.mkdir(parents=True, exist_ok=True)
    ascii_dir.mkdir(parents=True, exist_ok=True)
    compiler = resolved_tool("mdlcomp")
    if digest(compiler) != COMPILER_SHA256:
        raise RuntimeError("Model compiler hash differs from the pinned repository compiler")
    common = ["--root", str(args.game_root), "--userdirectory", str(args.user_directory), "--no-ovr"]
    grep = resolved_tool("nwn_resman_grep", args.tool_directory)
    listing = subprocess.run([str(grep), *common, "--all"], check=True, capture_output=True).stdout.decode("utf-8", errors="replace")
    available = set(re.findall(r"(?m)^\s*([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)\s*$", listing))
    save_json(output / "resource-inventory.json", sorted(available))
    cat = resolved_tool("nwn_resman_cat", args.tool_directory)
    extracted = {}

    def fetch(name):
        if name in extracted:
            return extracted[name]
        if name not in available:
            raise FileNotFoundError(f"Required installed resource unavailable: {name}")
        result = subprocess.run([str(cat), *common, name], check=True, capture_output=True)
        if not result.stdout:
            raise RuntimeError(f"Empty installed resource: {name}")
        path = raw / name
        path.write_bytes(result.stdout)
        metadata = {"name": name, "bytes": len(result.stdout), "sha256": digest(path)}
        if name.endswith(".mdl"):
            target = ascii_dir / name
            if result.stdout[:4] == b"\0\0\0\0":
                subprocess.run([str(compiler), "-d", "-e", str(path), str(target)], check=True, capture_output=True)
            else:
                target.write_bytes(result.stdout)
            if not target.is_file() or "newmodel" not in target.read_text(encoding="cp1252"):
                raise RuntimeError(f"Invalid decompiled model: {name}")
            metadata["asciiSha256"] = digest(target)
        extracted[name] = metadata
        return metadata

    for name in ("phenotype.2da", "racialtypes.2da", "appearance.2da", "ruleset.2da", "nwscript.nss",
                 "parts_chest.2da", "parts_robe.2da", "pal_skin01.tga", "pal_hair01.tga",
                 "pal_cloth01.tga", "pal_armor01.tga", "pal_armor02.tga", "pal_leath01.tga", "pal_tattoo01.tga", "ttr01.set"):
        fetch(name)
    (output / "ttr01.set").write_bytes((raw / "ttr01.set").read_bytes())
    for family in RACES.values():
        for sex in "mf":
            for phenotype in (0, 2):
                name = f"p{sex}{family['family']}{phenotype}"
                fetch(name + ".mdl")
    for sex in "mf":
        for part in PARTS:
            fetch(f"p{sex}h0_{part}001.mdl")
            palette = f"p{sex}h0_{part}001.plt"
            if palette in available:
                fetch(palette)
            text=(ascii_dir/f'p{sex}h0_{part}001.mdl').read_text(encoding='cp1252')
            for bitmap in set(re.findall(r'(?mi)^\s*bitmap\s+(\S+)',text)):
                actual=bitmap.lower()+'.plt'
                if bitmap.lower()!='null' and actual in available:fetch(actual)
        for resource in sorted(available):
            if re.fullmatch(f"p{sex}h0_(?:chest020|chest021|robe001)\\.(?:mdl|plt)", resource):
                fetch(resource)

    chains = {}
    def walk_chain(model):
        if model in chains:
            return
        fetch(model + ".mdl")
        text = (ascii_dir / (model + ".mdl")).read_text(encoding="cp1252")
        parent = re.search(r"(?mi)^setsupermodel\s+\S+\s+(\S+)", text)
        parent_name = parent[1].lower() if parent else "null"
        clips = []
        for match in re.finditer(r"(?mis)^newanim\s+(\S+)\s+\S+\s*\n(.*?)^doneanim[^\n]*", text):
            block = match[2]
            length = re.search(r"(?mi)^\s*length\s+(\S+)", block)
            transition = re.search(r"(?mi)^\s*transtime\s+(\S+)", block)
            events = re.findall(r"(?mi)^\s*event\s+(\S+)\s+(\S+)", block)
            clips.append({"name": match[1], "length": float(length[1]) if length else None,
                          "transition": float(transition[1]) if transition else None,
                          "events": [[float(t), e] for t, e in events],
                          "sha256": hashlib.sha256(match[0].encode()).hexdigest()})
        scale = re.search(r"(?mi)^setanimationscale\s+(\S+)", text)
        chains[model] = {"supermodel": parent_name, "animationScale": float(scale[1]) if scale else None,
                         "clips": clips, "sha256": digest(ascii_dir / (model + ".mdl"))}
        if parent_name != "null":
            walk_chain(parent_name)
    for family in RACES.values():
        for sex in "mf":
            for phenotype in (0, 2):
                walk_chain(f"p{sex}{family['family']}{phenotype}")
    heads, heads_by_phenotype = head_inventory(available)
    save_json(output / "baseline.json", {"schemaVersion": 1, "gameRoot": str(args.game_root),
        "resources": sorted(extracted.values(), key=lambda r: r["name"]), "heads": heads,
        "headsByPhenotype": heads_by_phenotype,
        "animations": chains, "engineObserved": False})
    print(json.dumps({"resources": len(extracted), "chains": len(chains),
                      "clips": sum(len(v["clips"]) for v in chains.values()), "headSlots": heads}))


if __name__ == "__main__":
    main()
