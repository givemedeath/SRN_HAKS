"""Execute the robe-scoped migration smokes through the shared launcher, then finalize.

Steps run in order into a fresh verification directory: stock robe extraction
smoke, frozen input pins, bundled-Python smoke, isolated Blender stock robe
import, and the launched finalizer. Nothing here approves robe assets.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from robe_common import REPO, TOOLS, pin, read, require, sha, write_fresh

HELPERS = [TOOLS / "phenotypes" / name for name in (
    "launch_shared_tool.py", "shared_toolchain.py", "bootstrap_shared_blender_addons.py",
    "smoke_shared_blender_import.py", "finalize_shared_tool_migration.py", "tool_runtime.py")] + [
    TOOLS / "shared_tools.py"] + [TOOLS / "robes" / name for name in (
    "robe_common.py", "robe_weights.py", "smoke_robe_tools.py", "extract_stock_robes.py",
    "finalize_robe_migration.py", "run_robe_migration.py")]


def launch(binding, tool, folder, arguments, inputs=()):
    command = [sys.executable, "-B", str(TOOLS / "phenotypes/launch_shared_tool.py"), "--toolchain", str(binding),
               "--migration-smoke", "--tool", tool, "--output", str(folder)]
    for path in dict.fromkeys(str(Path(item).resolve()) for item in inputs):
        command += ["--input", path]
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command + ["--", *map(str, arguments)], cwd=REPO, env=environment)
    require(result.returncode == 0, "Smoke launch failed: " + str(folder))
    return read(Path(folder) / "launch.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--user-directory", type=Path, required=True, help="Empty isolated staging userdir")
    parser.add_argument("--blender-preferences", type=Path, required=True)
    args = parser.parse_args()
    binding, root, output = args.toolchain.resolve(), args.verification_dir.resolve(), args.output.resolve()
    require(not root.exists() and not output.exists(), "Fresh verification directory and receipt required")
    require(Path(sys.executable).resolve() == Path(read(binding)["runtimes"]["python"]["path"]).resolve(),
            "Run the driver with the bound bundled Python")
    args.user_directory.mkdir(parents=True, exist_ok=True)
    require(not any(args.user_directory.iterdir()), "Staging user directory must be empty")
    root.mkdir(parents=True)
    snapshot = root / "binding-initial.json"
    shutil.copyfile(binding, snapshot)
    bank = root / "helper-snapshots"
    bank.mkdir()
    helpers = {}
    for path in HELPERS:
        copied = bank / (sha(path)[:12] + "-" + path.name)
        shutil.copyfile(path, copied)
        helpers[str(path.resolve())] = {**pin(path), "snapshot": str(copied), "snapshotSha256": sha(copied)}
    launch(binding, "python", root / "extraction-smoke",
           ["-B", TOOLS / "robes/extract_stock_robes.py", "--game-root", args.game_root,
            "--user-directory", args.user_directory, "--resource", "pmh0_robe001", "--output", root / "stock"],
           [TOOLS / "robes/extract_stock_robes.py", TOOLS / "robes/robe_common.py", TOOLS / "phenotypes/tool_runtime.py"])
    stock = root / "stock/ascii/pmh0_robe001.mdl"
    prefs = args.blender_preferences
    write_fresh(root / "input-pins.json", {
        "schemaVersion": 1, "kind": "srn-robe-migration-inputs", "toolchain": pin(binding),
        "toolchainInitialSnapshot": pin(snapshot), "activeWorktree": str(REPO), "launchHelpers": helpers,
        "stockAscii": pin(stock),
        "blenderSavedPreferencesBefore": {"path": str(prefs), "exists": prefs.exists(),
                                          "sha256": sha(prefs) if prefs.is_file() else None}})
    launch(binding, "python", root / "python-smoke", ["-B", TOOLS / "robes/smoke_robe_tools.py"],
           [TOOLS / "robes/smoke_robe_tools.py", TOOLS / "robes/robe_weights.py"])
    launch(binding, "blender", root / "blender-smoke",
           ["--python", TOOLS / "phenotypes/smoke_shared_blender_import.py", "--", "--source", stock,
            "--source-sha256", sha(stock), "--output", root / "blender-import.json"],
           [stock, TOOLS / "phenotypes/smoke_shared_blender_import.py"])
    finalizer = root.parent / (root.name + "-finalize-launch")
    files = [path for path in root.rglob("*") if path.is_file()]
    launch(binding, "python", finalizer,
           ["-B", TOOLS / "robes/finalize_robe_migration.py", "--toolchain", binding,
            "--verification-dir", root, "--output", output], [*HELPERS, *files])
    print(json.dumps({"migration": str(output), "sha256": sha(output)}))


if __name__ == "__main__":
    main()
