"""Finalize head-only Python/Blender migration from real isolated smokes.

Armory equipment migration remains a separate workflow. This receipt permits
Python/Blender launches only and conveys no asset or game-client acceptance.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phenotypes"))
from finalize_shared_tool_migration import verify_launch
from shared_toolchain import load
from head_workflow import pin, read, require, sha, verify_pins, write_fresh


def finalize(config, directory, output):
    config, root = Path(config).resolve(), Path(directory).resolve()
    require(not Path(output).exists(), "Fresh migration receipt required")
    tools = load(config, required=["python", "blender"])
    python = verify_launch(root / "python-smoke", "python", config, tools)
    blender = verify_launch(root / "blender-smoke", "blender", config, tools)
    smoke = read(root / "python-smoke/stdout.log")
    require(smoke["kind"] == "srn-head-python-smoke" and smoke["positiveSimilarityPassed"] is True
            and Path(smoke["executable"]).resolve() == Path(tools["tools"]["python"]["path"]).resolve(),
            "Bundled head Python smoke failed")
    imported = read(root / "blender-import.json")
    require(imported["kind"] == "shared-blender-import-smoke" and imported["result"] == ["FINISHED"]
            and imported["background"] is True and imported["sourceChanged"] is False
            and imported["enabledAndLoaded"] == [True, True] and imported["importedMeshes"]
            and all(row["vertices"] > 0 and row["faces"] > 0 for row in imported["importedMeshes"]),
            "Real stock import smoke required")
    require(blender["frozenInputs"].get(str(Path(imported["source"]).resolve())) == imported["sourceSha256"]
            == sha(imported["source"]), "Stock source missing from frozen import declaration")
    bootstrap = read(root / "blender-smoke/loaded-addons.json")
    require(bootstrap["factoryStartup"] is True and bootstrap["savedPreferencesChanged"] is False
            and bootstrap["preferencesChanged"] is False and bootstrap["migrationReceipt"] is None,
            "Isolated factory addon import required")
    addon = Path(tools["addons"]["root"]).resolve()
    require(imported["actuallyLoadedAddon"] == str(addon / "neverblender/__init__.py")
            and imported["loadedAddonSha256"] == sha(imported["actuallyLoadedAddon"]), "Import addon differs")
    require(bootstrap["loadedModules"], "Actually loaded addon inventory required")
    for row in bootstrap["loadedModules"]:
        path = Path(row["path"]).resolve()
        require(path.is_relative_to(addon) and tools["addons"]["files"].get(path.relative_to(addon).as_posix())
                == row["sha256"] == sha(path), "Loaded addon escaped pinned bank")
    helper_names = {"launch_shared_tool.py", "shared_toolchain.py", "bootstrap_shared_blender_addons.py"}
    helpers = {name: {"sha256": digest} for report in (python, blender)
               for name, digest in report["frozenInputs"].items() if Path(name).name in helper_names}
    require({Path(path).name for path in helpers} == helper_names, "All launch helpers must be frozen")
    frozen = [pin(path) for path in sorted(root.rglob("*")) if path.is_file()]
    verify_pins(frozen)
    receipt = {"schemaVersion": 1, "kind": "phenotype-shared-tool-migration", "scope": "head-tools",
               "allowedTools": ["python", "blender"], "smokeChecksPassed": True, "toolchain": pin(config),
               "launchHelpers": helpers, "frozenSmokeFiles": frozen, "executedFinalizer": pin(__file__),
               "createdUtc": datetime.now(timezone.utc).isoformat(), "gameClientTesting": False,
               "limits": "Head Python and isolated stock import only; no Armory/equipment or asset acceptance."}
    write_fresh(output, receipt)
    load(config, output, required=["python", "blender"])
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.toolchain, args.verification_dir, args.output)
    print(json.dumps({"migration": str(args.output), "sha256": sha(args.output)}))
