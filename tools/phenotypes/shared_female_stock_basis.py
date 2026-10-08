"""Read-only installed stock lineage for shared female posture diagnostics.

Archive binding and recorded lookup lineage grant no asset or client acceptance.
Only explicitly requested live lookups compare newly resolved resource bytes.
"""
import ast
import hashlib
from pathlib import Path
import re
import subprocess

import target_contract as contract
import shared_female_animation_overlay as overlay
import shared_female_posture_fixture as fixture
import shared_tools

REPO = Path(__file__).resolve().parents[2]
KIND = "executed-shared-female-installed-stock-basis"
FIELDS = {"schemaVersion", "kind", "familyPreparation", "coverage", "rosters", "rosterRecipe",
    "gameRoot", "sourceUserDirectory", "noOverrideLookup", "installedArchiveHashes",
    "installedArchiveCount", "BIFCount", "KEYCount", "sourceAncestryByResource",
    "sourceAncestryResourceCount", "resmanTool", "clientExecutable",
    "headNeckEquipmentIndividuallyDecoded", "effectiveHeadNeckMaterialResolution",
    "dynamicLimits", "commands", "frozenInputs", "HAKBuilt", "clientLaunched",
    "clientAccepted", "runtimeSelected", "productionAccepted"} | overlay.BINDING_FIELDS
COMMAND_FIELDS = {"command", "exitCode", "resourceName", "stdoutSha256", "stdoutBytes", "stderr"}
INVENTORY_FIELDS = {"schemaVersion", "kind", "gameRoot", "archiveHashes", "archiveCount",
    "BIFCount", "KEYCount", "resourceReadsExecuted", "clientLaunched", "clientAccepted"}
LIMITS = [
    "Exact archive bytes bind stock fallback resources; per-case head/neck/body/material/equipment resolution remains engine behavior.",
    "Both stock and candidate must be observed independently; no fitted-body or robe acceptance derives from this binding.",
    "Known inherited pfh2_robe035 missing source texture for pfd2/pfo2 is preserved and disclosed; no override or repair."]
FALSE_FLAGS = ("HAKBuilt", "clientLaunched", "clientAccepted", "runtimeSelected", "productionAccepted")


class Inputs:
    """Stream large installed archives; retain only actually consumed paths."""
    def __init__(self):
        self.files = {}

    def add(self, path, expected=None):
        path = Path(path).resolve(strict=True)
        contract.require(path.is_file(), "Consumed stock input must be a file")
        digest = shared_tools.sha(path)
        contract.require(expected is None or isinstance(expected, str) and
            re.fullmatch(r"[a-f0-9]{64}", expected) and digest == expected, "Consumed stock input hash differs")
        key = str(path)
        contract.require(key not in self.files or self.files[key] == digest, "Conflicting stock input")
        self.files[key] = digest
        return path

    def pin(self, entry, inside=True):
        contract.require(isinstance(entry, dict) and set(entry) == {"path", "sha256"},
                         "Exact stock file pin required")
        path = self.add(entry["path"], entry["sha256"])
        contract.require(not inside or path.is_relative_to(REPO/"output/phenotypes"/overlay.TARGET),
                         "Stock diagnostic input is outside its target")
        return path

    def read(self, entry, inside=True):
        return overlay.strict_json(self.pin(entry, inside))

    def merge(self, pins):
        contract.require(isinstance(pins, dict), "Actual consumed input mapping required")
        for path, digest in pins.items():
            self.add(path, digest)

    def finish(self):
        for path, digest in self.files.items():
            contract.require(shared_tools.sha(path) == digest, "Consumed stock input drift")
        return dict(self.files)


def helper_closure(inputs):
    """Freeze current loaded repository helpers and their local import closure."""
    pending = [Path(__file__).resolve(), Path(contract.__file__).resolve(),
               Path(overlay.__file__).resolve(), Path(fixture.__file__).resolve(),
               Path(shared_tools.__file__).resolve()]
    roots = (REPO/"tools/phenotypes", REPO/"tools")
    seen = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        contract.require(path.is_relative_to(REPO/"tools"), "Loaded helper is outside consuming checkout")
        inputs.add(path)
        imports = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        for name in imports:
            found = next((p for root in roots if (p := root/(name+".py")).is_file()), None)
            if found is not None:
                pending.append(found.resolve())


def archive_paths(game):
    folder = game/"data"
    contract.require(folder.is_dir(), "Installed data archive directory missing")
    return {str(p.resolve()) for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in (".key", ".bif")}


def require_isolation(user):
    for name in ("override", "hak"):
        folder = user/name
        contract.require(folder.is_dir() and not any(folder.iterdir()),
                         "Installed stock lookup requires empty override and HAK directories")


def source_ancestry(rows, inputs):
    native = {}
    for row in rows.values():
        for entry in row["sourceAncestry"]:
            contract.require(isinstance(entry["name"], str) and
                re.fullmatch(r"[a-z0-9_]{1,16}", entry["name"]), "Unsafe installed source resource")
            name = entry["name"]+".mdl"
            inputs.pin(entry["native"])
            inputs.pin(entry["ascii"])
            old = native.get(name)
            contract.require(old is None or old == entry["native"], "Conflicting installed source ancestry")
            native[name] = entry["native"]
        for key in ("sourceActorRoot", "sourceIdleNative", "sourceIdleASCII", "originalNativeArchive"):
            inputs.pin(row[key])
        for entry in row["inheritedStaticOmissions"]:
            inputs.pin(entry["native"])
    return native


def consume(binding_pin, target_path, roster_pin, game_root=None, client_path=None):
    inputs = Inputs()
    helper_closure(inputs)
    target_path = inputs.add(target_path)
    target = contract.load(target_path)
    overlay.require_target(target, target_path)
    inputs.merge(target.get("frozenInputs", {}))
    stock = inputs.read(target["rig"]["stockReferenceReceipt"], inside=False)
    inputs.merge(stock["frozenInputs"])
    inputs.pin(stock["rootAscii"], inside=False)
    basis = inputs.read(binding_pin)
    contract.require(set(basis) == FIELDS and type(basis["schemaVersion"]) is int and
        basis["schemaVersion"] == 1 and basis["kind"] == KIND, "Typed executed stock basis required")
    contract.verify_binding(basis, target_path, target, "runtime")
    contract.require(all(basis[k] is False for k in FALSE_FLAGS) and
        basis["headNeckEquipmentIndividuallyDecoded"] is False and basis["noOverrideLookup"] is True and
        basis["effectiveHeadNeckMaterialResolution"] == "installed-archives-dynamic-per-actor" and
        basis["dynamicLimits"] == LIMITS, "Diagnostic flags and exact dynamic stock limits required")
    contract.require(isinstance(basis["frozenInputs"], dict) and all(
        isinstance(p, str) and isinstance(h, str) and re.fullmatch(r"[a-f0-9]{64}", h)
        for p, h in basis["frozenInputs"].items()), "Typed historical stock input mapping required")

    rows = overlay.load_family_plan(basis["familyPreparation"], inputs)
    expected_sources = source_ancestry(rows, inputs)
    recipe = inputs.read(basis["rosterRecipe"])
    contract.verify_binding(recipe, target_path, target, "runtime")
    contract.require(recipe.get("kind") == "prepared-shared-female-stockbody-roster-recipe" and
        type(recipe.get("schemaVersion")) is int and recipe["schemaVersion"] == 1 and
        recipe.get("familyPreparation") == basis["familyPreparation"] and
        recipe.get("coverage") == basis["coverage"] and
        all(recipe.get(k) is False for k in FALSE_FLAGS), "Stock roster recipe lineage differs")
    config = inputs.read(recipe["config"])
    contract.require(config.get("kind") == "unexecuted-shared-female-stockbody-roster-preparation" and
        config.get("targetContract") == {"path":str(target_path), "sha256":shared_tools.sha(target_path)} and
        config.get("familyPreparation") == basis["familyPreparation"] and
        all(config.get(k) == recipe[k] for k in ("sourcePreparation", "sourceProof", "sourceGITDecoded")),
        "Stock recipe configuration lineage differs")
    parent = inputs.read(recipe["sourcePreparation"])
    contract.verify_binding(parent, target_path, target, "runtime")
    contract.require(parent.get("kind") == "target-fixture-source" and
        parent.get("runtimeBodySource") == "stock-human-female" and parent.get("clientAccepted") is False and
        parent.get("hakBuilt") is False, "Installed stock source preparation differs")
    inputs.read(recipe["sourceProof"])
    inputs.read(recipe["sourceGITDecoded"])
    game = Path(basis["gameRoot"]).resolve(strict=True)
    user = Path(basis["sourceUserDirectory"]).resolve(strict=True)
    expected_user = Path(recipe["sourcePreparation"]["path"]).resolve().parent/"source-userdir"
    contract.require(str(game) == basis["gameRoot"] and Path(config["gameRoot"]).resolve() == game and
        user == expected_user and str(user) == basis["sourceUserDirectory"] and
        (game_root is None or Path(game_root).resolve() == game), "Installed game/lookup user lineage differs")
    require_isolation(user)

    coverage = inputs.read(basis["coverage"])
    cv = fixture.verify_cumulative_coverage(basis["coverage"], target_path)
    inputs.merge(cv["frozenInputs"])
    rosters = basis["rosters"]
    contract.require(isinstance(rosters, list) and len(rosters) == 4 and
        len({(p["path"], p["sha256"]) for p in rosters}) == 4 and rosters == coverage["rosters"] and
        coverage["familyPreparation"] == basis["familyPreparation"] and roster_pin in rosters,
        "Exact complete coverage and selected roster membership required")
    batches = recipe["batches"]
    contract.require(isinstance(batches, list) and len(batches) == 4 and
        [b["roster"] for b in batches] == rosters and {b["batchId"] for b in batches} == set(fixture.BATCHES),
        "Recipe must bind the same four roster batches")
    for entry in rosters:
        verified = fixture.verify_roster(entry, target_path)
        contract.require(verified["document"]["familyPreparation"] == basis["familyPreparation"],
                         "Covered roster family authority differs")
        inputs.merge(verified["frozenInputs"])

    inventory = inputs.read(config["installedArchiveInventory"])
    contract.require(set(inventory) == INVENTORY_FIELDS and type(inventory["schemaVersion"]) is int and
        inventory["schemaVersion"] == 1 and inventory["kind"] == "unexecuted-installed-data-archive-binding-input" and
        Path(inventory["gameRoot"]).resolve() == game and inventory["resourceReadsExecuted"] is False and
        inventory["clientLaunched"] is False and inventory["clientAccepted"] is False,
        "Exact installed archive inventory input required")
    hashes = basis["installedArchiveHashes"]
    contract.require(isinstance(hashes, dict) and set(hashes) == archive_paths(game) and
        hashes == inventory["archiveHashes"], "Actual complete installed archive inventory differs")
    counts = (len(hashes), sum(Path(p).suffix.lower() == ".bif" for p in hashes),
              sum(Path(p).suffix.lower() == ".key" for p in hashes))
    for doc, keys in ((basis, ("installedArchiveCount", "BIFCount", "KEYCount")),
                      (inventory, ("archiveCount", "BIFCount", "KEYCount"))):
        contract.require(all(type(doc[k]) is int for k in keys) and
            tuple(doc[k] for k in keys) == counts == (63, 61, 2), "Installed 63/61/2 archive counts differ")
    inputs.merge(hashes)

    resolved = shared_tools.resolve_tool("resman_cat", REPO, config["toolsRoot"])
    contract.require(basis["resmanTool"] == resolved, "Stock lookup tool differs from merged resolver")
    inputs.add(resolved["path"], resolved["sha256"])
    inputs.add(REPO/"tools/shared-tools.lock.json", resolved["inventorySha256"])
    executable = inputs.pin(basis["clientExecutable"], inside=False)
    contract.require(executable == game/"bin/win32/nwmain.exe" and
        basis["clientExecutable"]["sha256"] == overlay.COMPILER_SHA and
        (client_path is None or Path(client_path).resolve() == executable),
        "Installed client identity differs")

    actual = basis["sourceAncestryByResource"]
    contract.require(isinstance(actual, dict) and set(actual) == set(expected_sources) and
        type(basis["sourceAncestryResourceCount"]) is int and basis["sourceAncestryResourceCount"] == len(actual),
        "Exact unique installed ancestry resource inventory required")
    for name, source_pin in expected_sources.items():
        row = actual[name]
        contract.require(isinstance(row, dict) and
            set(row) == {"native", "installedLookupSha256", "byteExactToPinnedSource"} and
            row["native"] == source_pin and row["installedLookupSha256"] == source_pin["sha256"] and
            row["byteExactToPinnedSource"] is True, "Installed ancestry source identity differs")
    commands = basis["commands"]
    contract.require(isinstance(commands, list) and len(commands) == len(actual),
                     "Exactly one recorded lookup per resource required")
    seen = set()
    for row in commands:
        contract.require(isinstance(row, dict) and set(row) == COMMAND_FIELDS, "Typed source lookup row required")
        name = row["resourceName"]
        contract.require(name in actual and name not in seen, "Duplicate or foreign source lookup")
        seen.add(name)
        argv = [resolved["path"], "--root", str(game), "--userdirectory", str(user), "--no-ovr", name]
        source = inputs.pin(expected_sources[name])
        contract.require(row["command"] == argv and type(row["exitCode"]) is int and row["exitCode"] == 0 and
            row["stdoutSha256"] == expected_sources[name]["sha256"] and
            type(row["stdoutBytes"]) is int and row["stdoutBytes"] == source.stat().st_size and
            isinstance(row["stderr"], str), "Recorded source lookup command/result lineage differs")
    contract.require(seen == set(actual), "Complete recorded source lookup inventory required")
    return inputs, basis, cv, game, user, expected_sources


def verify_stock_basis(binding_pin, target_path, roster_pin, *, game_root=None, client_path=None,
                       declared_inputs=None, live_source_lookup=False):
    """Verify current bytes; optionally execute fresh isolated resource lookups."""
    contract.require(type(live_source_lookup) is bool, "Explicit live source lookup mode required")
    inputs, basis, coverage, game, user, sources = consume(
        binding_pin, target_path, roster_pin, game_root, client_path)
    lookups = []
    if live_source_lookup:
        for row in basis["commands"]:
            require_isolation(user)
            result = subprocess.run(row["command"], capture_output=True, check=False)
            name = row["resourceName"]
            source = inputs.pin(sources[name])
            raw = source.read_bytes()
            digest = hashlib.sha256(result.stdout).hexdigest()
            contract.require(result.returncode == 0 and result.stdout == raw and
                digest == sources[name]["sha256"], "Fresh installed source lookup differs: "+name)
            lookups.append({"resourceName":name, "stdoutSha256":digest, "stdoutBytes":len(result.stdout),
                            "exitCode":result.returncode})
    require_isolation(user)
    contract.require(archive_paths(game) == set(basis["installedArchiveHashes"]),
                     "Installed archive inventory changed during stock verification")
    frozen = inputs.finish()
    if declared_inputs is not None:
        overlay.require_declared_inputs(frozen, declared_inputs)
    return {"kind":"verified-shared-female-installed-stock-basis", "postureStockBinding":binding_pin,
        "postureRoster":roster_pin, "familyPreparation":basis["familyPreparation"],
        "coverage":basis["coverage"], "requiredCells":coverage["requiredCells"],
        "installedArchiveHashes":basis["installedArchiveHashes"], "sourceAncestryResources":len(sources),
        "sourceLookupCommands":basis["commands"], "liveSourceLookupExecuted":live_source_lookup,
        "liveSourceLookupResults":lookups, "recordedLookupsProveExecutionLineageOnly":not live_source_lookup,
        "headNeckEquipmentIndividuallyDecoded":False, "dynamicLimits":list(LIMITS),
        "frozenInputs":frozen, "clientAccepted":False, "runtimeSelected":False, "productionAccepted":False}


def collect_stock_basis_inputs(binding_pin, target_path, roster_pin):
    """No resource tools are executed; hashes and recorded lineage are checked."""
    return verify_stock_basis(binding_pin, target_path, roster_pin)["frozenInputs"]