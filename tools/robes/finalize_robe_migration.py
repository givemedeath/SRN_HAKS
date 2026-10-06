"""Finalize a robe-scoped Python/Blender migration from real isolated smokes.

The trial uses no Armory equipment path, so the receipt permits Python and Blender
launches only. It proves tool behavior and conveys no asset, native or client
acceptance.
"""
import argparse
import json
from pathlib import Path

from robe_common import pin, read, require, sha, utc, verify_pins, write_fresh
from finalize_shared_tool_migration import verify_launch
from shared_toolchain import load

CORE = {"launch_shared_tool.py", "shared_toolchain.py", "bootstrap_shared_blender_addons.py"}


def finalize(config, directory, output):
    config, root, output = Path(config).resolve(), Path(directory).resolve(), Path(output).resolve()
    require(not output.exists(), "Fresh migration receipt required")
    tools = load(config, required=["python", "blender"])
    inputs = read(root / "input-pins.json")
    require(Path(inputs["toolchain"]["path"]).resolve() == config, "Verification inputs belong to another binding")
    verify_pins([inputs["toolchain"], inputs["toolchainInitialSnapshot"], inputs["stockAscii"]])
    for name, value in inputs["launchHelpers"].items():
        verify_pins([{"path": name, "sha256": value["sha256"]},
                     {"path": value["snapshot"], "sha256": value["snapshotSha256"]}])
    saved = inputs["blenderSavedPreferencesBefore"]
    prefs = Path(saved["path"])
    require(prefs.exists() == saved["exists"] and (sha(prefs) if prefs.is_file() else None) == saved["sha256"],
            "Saved Blender preferences changed during verification")
    python = verify_launch(root / "python-smoke", "python", config, tools)
    extraction = verify_launch(root / "extraction-smoke", "python", config, tools)
    blender = verify_launch(root / "blender-smoke", "blender", config, tools)
    smoke = read(root / "python-smoke/stdout.log")
    require(smoke["kind"] == "srn-robe-python-smoke" and smoke["weightLimitPassed"] is True
            and Path(smoke["executable"]).resolve() == Path(tools["tools"]["python"]["path"]).resolve(),
            "Bundled robe Python smoke failed")
    extracted = read(root / "stock/extraction.json")
    require(extracted["kind"] == "srn-robe-stock-extraction" and extracted["overridesDisabled"] is True,
            "Stock extraction smoke failed")
    stock = Path(inputs["stockAscii"]["path"]).resolve()
    require(stock.is_relative_to(root / "stock/ascii"), "Import smoke must use the freshly extracted stock robe")
    imported = read(root / "blender-import.json")
    require(imported["kind"] == "shared-blender-import-smoke" and imported["result"] == ["FINISHED"]
            and imported["background"] is True and imported["sourceChanged"] is False
            and imported["enabledAndLoaded"] == [True, True] and imported["importedMeshes"]
            and all(row["vertices"] > 0 and row["faces"] > 0 for row in imported["importedMeshes"]),
            "Real stock robe import smoke required")
    require(Path(imported["source"]).resolve() == stock and imported["sourceSha256"] == inputs["stockAscii"]["sha256"]
            and blender["frozenInputs"].get(str(stock)) == imported["sourceSha256"],
            "Stock robe missing from frozen import declaration")
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
    helpers = {name: {"sha256": value["sha256"]} for name, value in inputs["launchHelpers"].items()
               if Path(name).name in CORE}
    require({Path(name).name for name in helpers} == CORE, "All launch helpers must be frozen")
    active = Path(inputs["activeWorktree"]).resolve()
    require(all(Path(name).resolve().is_relative_to(active) for name in helpers),
            "Launch helpers must belong to this worktree")
    frozen = [pin(path) for path in sorted(root.rglob("*")) if path.is_file()]
    verify_pins(frozen)
    receipt = {"schemaVersion": 1, "kind": "phenotype-shared-tool-migration", "scope": "robe-tools",
               "allowedTools": ["python", "blender"], "smokeChecksPassed": True, "toolchain": pin(config),
               "toolchainInitialSnapshot": inputs["toolchainInitialSnapshot"], "activeWorktree": str(active),
               "verificationInputs": pin(root / "input-pins.json"), "launchHelpers": helpers,
               "executedSmokeHelpers": {name: value for name, value in inputs["launchHelpers"].items()
                                        if Path(name).name not in CORE},
               "smokeLaunches": {"python": python["exitCode"], "extraction": extraction["exitCode"],
                                 "blender": blender["exitCode"]},
               "versions": {"python": smoke["version"], "numpy": smoke["numpy"], "pillow": smoke["pillow"],
                            "blender": imported["blenderVersion"], "neverblender": imported["neverblenderVersion"]},
               "frozenSmokeFiles": frozen, "executedFinalizer": pin(__file__), "createdUtc": utc(),
               "blenderSavedPreferencesBeforeAndAfter": saved, "gameClientTesting": False,
               "oldWorktreeOrToolsDeleted": False,
               "limits": "Robe Python, stock extraction and isolated stock robe import only; "
                         "no Armory/equipment, Neverblender export, asset, native or client acceptance."}
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
