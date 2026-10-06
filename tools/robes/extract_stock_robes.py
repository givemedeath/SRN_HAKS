"""Extract installed stock robe models, their dependencies and the body rig chain.

Reads the installed game with overrides disabled and writes only to a fresh
ignored output directory. Extraction approves nothing.
"""
import argparse
import re
import subprocess
from pathlib import Path

from robe_common import FLAGS, fresh_directory, require, sha, utc, write_fresh
from tool_runtime import tool as resolved_tool

COMPILER_SHA256 = "0e32070c3e00a07a5f9e93b7e4a63a40dd5486b974900bbb8a0d2f4424c612bb"
BODY_PARTS = ("belt", "bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer", "handl", "handr",
              "head", "legl", "legr", "neck", "pelvis", "shinl", "shinr", "shol", "shor")
TABLES = ("parts_robe.2da", "parts_chest.2da", "baseitems.2da", "appearance.2da", "pal_skin01.tga",
          "pal_hair01.tga", "pal_cloth01.tga", "pal_armor01.tga", "pal_armor02.tga", "pal_leath01.tga",
          "pal_tattoo01.tga")
TEXTURE_SUFFIXES = (".plt", ".tga", ".dds", ".mtr", ".txi")


class Extractor:
    def __init__(self, game_root, user_directory, output, tool_directory=None):
        self.common = ["--root", str(game_root), "--userdirectory", str(user_directory), "--no-ovr"]
        self.cat = resolved_tool("nwn_resman_cat", tool_directory)
        grep = resolved_tool("nwn_resman_grep", tool_directory)
        # mdlcomp is vendored in this checkout (tools/vendor), not part of the shared tool directory.
        self.compiler = resolved_tool("mdlcomp")
        require(sha(self.compiler) == COMPILER_SHA256, "Model compiler differs from the pinned compiler")
        listing = subprocess.run([str(grep), *self.common, "--all"], check=True,
                                 capture_output=True).stdout.decode("utf-8", errors="replace")
        self.available = set(name.lower() for name in
                             re.findall(r"(?m)^\s*([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)\s*$", listing))
        self.raw, self.ascii = output / "raw", output / "ascii"
        self.raw.mkdir()
        self.ascii.mkdir()
        self.extracted = {}

    def fetch(self, name, optional=False):
        name = name.lower()
        if name in self.extracted:
            return self.extracted[name]
        if name not in self.available:
            require(optional, "Required installed resource unavailable: " + name)
            return None
        result = subprocess.run([str(self.cat), *self.common, name], check=True, capture_output=True)
        require(bool(result.stdout), "Empty installed resource: " + name)
        path = self.raw / name
        path.write_bytes(result.stdout)
        row = {"name": name, "bytes": len(result.stdout), "rawSha256": sha(path)}
        if name.endswith(".mdl"):
            target = self.ascii / name
            binary = result.stdout[:4] == b"\0\0\0\0"
            if binary:
                subprocess.run([str(self.compiler), "-d", "-e", str(path), str(target)], check=True,
                               capture_output=True)
            else:
                target.write_bytes(result.stdout)
            require(target.is_file() and "newmodel" in target.read_text(encoding="cp1252").lower(),
                    "Invalid decompiled model: " + name)
            row.update(binaryInstalled=binary, asciiSha256=sha(target))
        self.extracted[name] = row
        return row

    def text(self, model):
        return (self.ascii / (model.lower() + ".mdl")).read_text(encoding="cp1252")

    def chain(self, model):
        names = []
        while model and model.lower() != "null" and model.lower() not in names:
            self.fetch(model + ".mdl")
            names.append(model.lower())
            parent = re.search(r"(?mi)^\s*setsupermodel\s+\S+\s+(\S+)", self.text(model))
            model = parent[1] if parent else None
        return names

    def dependencies(self, model):
        bitmaps = set()
        for field in ("bitmap", "texture0", "texture1", "texture2", "texture3", "materialname", "renderhint"):
            bitmaps.update(value.lower() for value in
                           re.findall(r"(?mi)^\s*" + field + r"\s+(\S+)", self.text(model)))
        found, pending, seen = [], sorted(bitmaps - {"null", "normalandspecmapped", "normaltangents"}), set()
        while pending:
            bitmap = pending.pop(0)
            if bitmap in seen:
                continue
            seen.add(bitmap)
            for suffix in TEXTURE_SUFFIXES:
                row = self.fetch(bitmap + suffix, optional=True)
                if row:
                    found.append(row["name"])
                    if row["name"].endswith(".mtr"):  # an MTR names its own maps
                        text = (self.raw / row["name"]).read_text(encoding="cp1252", errors="replace")
                        pending += [v.lower() for v in re.findall(r"(?mi)^\s*texture\d\s+(\S+)", text)
                                    if v.lower() != "null"]
        return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--user-directory", type=Path, required=True)
    parser.add_argument("--tool-directory", type=Path)
    parser.add_argument("--prefix", default="pmh0")
    parser.add_argument("--resource", action="append", default=[],
                        help="Explicit robe model resref; omit to extract every installed robe for the prefix")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = fresh_directory(args.output)
    extractor = Extractor(args.game_root.resolve(), args.user_directory.resolve(), output, args.tool_directory)
    pattern = re.compile(re.escape(args.prefix.lower()) + r"_robe(\d{3})\.mdl")
    installed = sorted(name for name in extractor.available if pattern.fullmatch(name))
    selected = [name.lower().removesuffix(".mdl") + ".mdl" for name in args.resource] or installed
    require(selected and set(selected) <= set(installed), "Requested robe models are not installed")
    for name in TABLES:
        extractor.fetch(name)
    body_chain = extractor.chain(args.prefix)
    body_parts = {}
    for part in BODY_PARTS:
        stem = f"{args.prefix}_{part}001"
        extractor.fetch(stem + ".mdl")
        body_parts[part] = {"model": stem, "dependencies": extractor.dependencies(stem)}
    robes = {}
    for name in selected:
        stem = name.removesuffix(".mdl")
        robes[stem] = {"chain": extractor.chain(stem), "dependencies": extractor.dependencies(stem)}
    report = {"schemaVersion": 1, "kind": "srn-robe-stock-extraction", "createdUtc": utc(),
              "prefix": args.prefix.lower(), "overridesDisabled": True,
              "installedRobeModels": installed, "selectedRobeModels": selected,
              "bodyChain": body_chain, "bodyParts": body_parts, "robes": robes,
              "resources": dict(sorted(extractor.extracted.items())), "asciiDirectory": str(extractor.ascii),
              "rawDirectory": str(extractor.raw), **FLAGS}
    print(write_fresh(output / "extraction.json", report)["sha256"])


if __name__ == "__main__":
    main()
