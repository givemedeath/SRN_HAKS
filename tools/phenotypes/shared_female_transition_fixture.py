"""Typed opt-in script descendants and logged transition protocol; no client approval.

The existing stock-basis/GIT-only verifier is called unchanged for the parent.
Source hashes and requested/logged queue states do not prove visible engine blends.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import re

import target_contract as contract

REPO = Path(__file__).resolve().parents[2]
TARGET = "human-female-fit-purposebuilt-v1"
ROOTS = {f"pf{family}{phenotype}" for family in "adegho" for phenotype in (0, 2)}
BINDING = {"targetContract", "targetContractSha256", "targetId", "rigRevision", "coordinateSpace"}
FALSE_FLAGS = {"HAKBuilt", "clientLaunched", "clientAccepted", "runtimeSelected", "productionAccepted"}
SOURCES = {"sr_tm_enter.nss", "sr_tm_next.nss"}
CHANGED = SOURCES | {"sr_tm_enter.ncs", "sr_tm_next.ncs"}
MODULE = {"module.ifo", "repute.fac", "sr_tm_floor.are", "sr_tm_floor.git", "sr_tm_target.utc"} | {
    stem + suffix for stem in ("sr_tm_enter", "sr_tm_next", "sr_tm_spawn", "sr_tm_damage", "sr_tm_death")
    for suffix in (".nss", ".ncs")}
FIXTURES = {"sr_tm.set", "sr_tm_edge.2da"}
SCHEDULE_FIELDS = BINDING | {"schemaVersion", "kind", "familyPreparation", "coverage", "rosters",
    "groups", "idleTimings", "camera", "outboundDistanceMetres", "arrivalToleranceMetres",
    "postureHoldSeconds", "samplingLimit", "sourceNSSHashes"}
PROOF_FIELDS = BINDING | FALSE_FLAGS | {"schemaVersion", "kind", "parentPreparation",
    "parentSourceProof", "postureRoster", "postureStockBinding", "selectedOverlay", "schedule",
    "compileExecution", "nativeModule", "nativeGIT", "decodedNativeGIT", "moduleResourceHashes",
    "fixtureResourceHashes", "stockTableBaselines", "protected11ModuleResourceHashes",
    "operationCounts"}
COMPILE_FIELDS = BINDING | FALSE_FLAGS | {"schemaVersion", "kind", "compilerTool", "header",
    "sources", "outputs", "commands", "scriptCompileCalls", "frozenInputs"}
EVENT_FIELDS = {"groupId", "actorTag", "runToken", "phase", "state", "elapsedSeconds",
                "requested", "action", "position", "facing", "pause"}
TRACE_FIELDS = {"schemaVersion", "kind", "schedule", "roster", "runToken", "events"}
DIGEST = re.compile(r"[a-f0-9]{64}")
require = contract.require


def strict_json(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=pairs, parse_constant=invalid)
    def finite(value):
        if type(value) is float:
            require(math.isfinite(value), "Nonfinite ordinary JSON number")
        elif isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)
    finite(data)
    return data


def number(value, positive=False):
    return type(value) in (int, float) and math.isfinite(value) and (not positive or value > 0)


def pin_shape(entry):
    require(isinstance(entry, dict) and set(entry) == {"path", "sha256"} and
        isinstance(entry["path"], str) and Path(entry["path"]).is_absolute() and
        isinstance(entry["sha256"], str) and DIGEST.fullmatch(entry["sha256"]),
        "Exact absolute path/hash pin required")


def hash_mapping(mapping, names=None):
    require(isinstance(mapping, dict) and (names is None or set(mapping) == set(names)) and
        all(isinstance(k, str) and isinstance(v, str) and DIGEST.fullmatch(v)
            for k, v in mapping.items()), "Exact hash inventory required")


class Inputs:
    def __init__(self):
        self.files = {}

    def add(self, path, expected=None):
        require(isinstance(path, (str, Path)) and Path(path).is_absolute(), "Absolute input path required")
        path = Path(path).resolve(strict=True)
        require(path.is_file(), "Input is not a file")
        digest = contract.sha(path)
        require(expected is None or isinstance(expected, str) and DIGEST.fullmatch(expected) and
                digest == expected, "Input hash differs: " + str(path))
        key = str(path)
        require(key not in self.files or self.files[key] == digest, "Conflicting input pin")
        self.files[key] = digest
        return path

    def pin(self, entry):
        pin_shape(entry)
        return self.add(entry["path"], entry["sha256"])

    def read(self, entry):
        return strict_json(self.pin(entry))

    def merge(self, mapping):
        hash_mapping(mapping)
        for path, digest in mapping.items():
            self.add(path, digest)

    def finish(self):
        for path, digest in self.files.items():
            require(contract.sha(path) == digest, "Consumed input changed: " + path)
        return dict(self.files)


def current_helper_closure(inputs):
    """Only local imports reachable from this consumer, never a directory glob."""
    pending, seen = [Path(__file__).resolve()], set()
    roots = (REPO / "tools/phenotypes", REPO / "tools")
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        require(path.is_relative_to(REPO / "tools"), "Runtime helper outside consuming checkout")
        inputs.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                candidate = next((root / (name.split(".")[0] + ".py") for root in roots
                                  if (root / (name.split(".")[0] + ".py")).is_file()), None)
                if candidate is not None:
                    pending.append(candidate.resolve())


def pending(document):
    require(all(document.get(flag) is False for flag in FALSE_FLAGS), "Acceptance flags must remain false")


def validate_schedule(schedule, rosters):
    require(isinstance(schedule, dict) and set(schedule) == SCHEDULE_FIELDS and
        type(schedule["schemaVersion"]) is int and schedule["schemaVersion"] == 1 and
        schedule["kind"] == "shared-female-transition-schedule", "Typed transition schedule required")
    require(isinstance(rosters, list) and len(rosters) == 4 and
        {r["batchId"] for r in rosters} == {"batch-" + str(i) for i in range(1, 5)},
        "Four unique roster batches required")
    require(isinstance(schedule["rosters"], list) and len(schedule["rosters"]) == 4,
            "Four explicit schedule roster pins required")
    for pin in (schedule["familyPreparation"], schedule["coverage"], *schedule["rosters"]):
        pin_shape(pin)
    require(len({(p["path"], p["sha256"]) for p in schedule["rosters"]}) == 4,
            "Duplicate schedule roster pin")
    hash_mapping(schedule["sourceNSSHashes"], SOURCES)
    expected, required_cells = [], []
    for roster in rosters:
        require(len(roster["actors"]) == 8 and
            {a["tag"] for a in roster["actors"]} == {"tm_" + str(i) for i in range(8)},
            "Eight unique actors required")
        for actor in roster["actors"]:
            require(all(type(actor[k]) is int for k in ("raceId", "phenotypeId", "poseId")) and
                actor["phenotypeId"] in (0, 2) and type(actor["poseId"]) is int and actor["poseId"] in (0, 1) and
                actor["clip"] == ("pause1", "pause2")[actor["poseId"]] and
                actor["femaleRoot"] in ROOTS and actor["purpose"] in ("required-case", "equipment-control"),
                "Actor idle or purpose differs")
            if actor["purpose"] == "required-case":
                required_cells.append((actor["raceId"], actor["phenotypeId"], actor["clip"]))
        for purpose in ("required-case", "equipment-control"):
            races = dict.fromkeys(a["raceId"] for a in roster["actors"] if a["purpose"] == purpose)
            for race in races:
                expected.append({"batchId": roster["batchId"],
                    "groupId": roster["batchId"] + "-" + purpose + "-race-" + str(race),
                    "actorTags": [a["tag"] for a in roster["actors"]
                                  if a["purpose"] == purpose and a["raceId"] == race]})
    require(len(required_cells) == len(set(required_cells)) == 28, "Exact 28 independent cells required")
    require(schedule["groups"] == expected, "Exact roster-derived group membership/order required")
    timings = schedule["idleTimings"]
    require(isinstance(timings, dict) and set(timings) == ROOTS, "All twelve idle timing owners required")
    for entry in timings.values():
        require(set(entry) == {"sourceNative", "owner", "pause1", "pause2"} and
            entry["owner"] in ("a_fa", "a_fa2", "a_ba"), "Explicit native timing owner required")
        pin_shape(entry["sourceNative"])
        for clip in ("pause1", "pause2"):
            require(set(entry[clip]) == {"length", "transition"} and
                number(entry[clip]["length"], True) and number(entry[clip]["transition"]) and
                entry[clip]["transition"] >= 0, "Finite native idle timing required")
    require(number(schedule["outboundDistanceMetres"], True) and
        number(schedule["arrivalToleranceMetres"], True) and
        schedule["arrivalToleranceMetres"] < schedule["outboundDistanceMetres"] and
        number(schedule["postureHoldSeconds"], True), "Finite diagnostic route/hold required")
    camera = schedule["camera"]
    require(isinstance(camera, dict) and set(camera) == {"distance", "pitch", "height"} and
        number(camera["distance"], True) and 1 <= camera["distance"] <= 25 and
        number(camera["pitch"]) and 1 <= camera["pitch"] <= 89 and number(camera["height"]),
        "Camera exceeds declared unlocked limits")
    require(isinstance(schedule["samplingLimit"], str) and schedule["samplingLimit"].strip(),
            "Diagnostic sampling limits required")
    return {"requiredCells": sorted(required_cells), "groups": expected}


def idle_seconds(schedule, actor):
    timing = schedule["idleTimings"][actor["femaleRoot"]][actor["clip"]]
    return timing["transition"] + 2 * timing["length"]


def validate_trace(schedule, roster, trace):
    """Validate requested/logged ordering; never infer visible motion from logs."""
    require(isinstance(trace, dict) and set(trace) == TRACE_FIELDS and
        type(trace["schemaVersion"]) is int and trace["schemaVersion"] == 1 and
        trace["kind"] == "shared-female-transition-logged-trace" and
        type(trace["runToken"]) is int and trace["runToken"] > 0 and isinstance(trace["events"], list),
        "Typed logged trace required")
    pin_shape(trace["schedule"])
    pin_shape(trace["roster"])
    require(trace["roster"] in schedule["rosters"], "Trace roster outside schedule")
    groups = [g for g in schedule["groups"] if g["batchId"] == roster["batchId"]]
    require(groups, "No declared groups for trace batch")
    actors = {a["tag"]: a for a in roster["actors"]}
    sequences = [["baseline-request", "baseline-complete"]] + [
        [family + "-request"] + ([family + "-out-arrived", family + "-home-arrived"]
        if family in ("walk", "run") else [family + "-complete"]) +
        ["idle-request", "idle-complete"] for family in ("walk", "run", "crouch", "kneel")]
    group_index = phase = 0
    progress = {tag: 0 for tag in groups[0]["actorTags"]}
    starts, previous_time, previous_positions = {}, -1, {}
    for event in trace["events"]:
        require(isinstance(event, dict) and set(event) == EVENT_FIELDS and
            all(type(event[k]) is int for k in ("runToken", "phase", "requested", "action", "pause")) and
            event["runToken"] == trace["runToken"] and event["pause"] == 0 and
            number(event["elapsedSeconds"]) and event["elapsedSeconds"] >= previous_time and
            isinstance(event["position"], list) and len(event["position"]) == 3 and
            all(number(v) for v in event["position"]) and number(event["facing"]), "Malformed/stale trace event")
        require(group_index < len(groups), "Events after group completion")
        group = groups[group_index]
        require(event["groupId"] == group["groupId"] and event["actorTag"] in progress and
            event["phase"] == phase, "Premature/wrong group or phase")
        tag = event["actorTag"]
        require(progress[tag] < len(sequences[phase]) and
            event["state"] == sequences[phase][progress[tag]], "Missing, duplicate or reordered actor action")
        actor, now = actors[tag], event["elapsedSeconds"]
        if event["state"] in ("baseline-request", "idle-request"):
            require(event["requested"] == actor["poseId"], "Return must use same assigned idle")
            starts[tag, "idle"] = now
        elif event["state"] in ("baseline-complete", "idle-complete"):
            require(now - starts[tag, "idle"] >= idle_seconds(schedule, actor),
                    "Idle blend and two complete cycles not logged")
        elif event["state"].endswith("-request"):
            require(event["requested"] == (0, 1, 12, 4)[phase - 1], "Wrong active command")
            starts[tag, "active"] = now
        elif phase in (1, 2):
            home = [actor["placement"][k] for k in ("XPosition", "YPosition", "ZPosition")]
            target = list(home)
            if event["state"].endswith("-out-arrived"):
                target[1] += (-1 if home[1] < 20 else 1) * schedule["outboundDistanceMetres"]
            distance = math.dist(event["position"], target)
            require(distance <= schedule["arrivalToleranceMetres"], "False arrival/wrong HOME")
            if event["state"].endswith("-home-arrived"):
                require(math.dist(previous_positions[tag], home) >=
                    schedule["outboundDistanceMetres"] - schedule["arrivalToleranceMetres"],
                    "No actual outbound movement logged")
            previous_positions[tag] = event["position"]
        else:
            require(now - starts[tag, "active"] >= schedule["postureHoldSeconds"],
                    "Active posture hold not logged")
        progress[tag] += 1
        previous_time = now
        if all(index == len(sequences[phase]) for index in progress.values()):
            phase += 1
            if phase == len(sequences):
                group_index += 1
                phase = 0
            if group_index < len(groups):
                progress = {tag: 0 for tag in groups[group_index]["actorTags"]}
    require(group_index == len(groups), "Incomplete actor/phase coverage")
    return {"kind": "verified-logged-transition-protocol", "loggedActors": len(actors),
            "loggedRequiredCells": sum(a["purpose"] == "required-case" for a in actors.values()),
            "visibleMotionProven": False, "clientAccepted": False, "runtimeSelected": False}


def _validate_compile(document, inputs, target_path, target, tools_root):
    import shared_tools
    require(isinstance(document, dict) and set(document) == COMPILE_FIELDS and
        type(document["schemaVersion"]) is int and document["schemaVersion"] == 1 and
        document["kind"] == "executed-shared-female-transition-script-compile" and
        type(document["scriptCompileCalls"]) is int and document["scriptCompileCalls"] == 2,
        "Typed two-script compile execution required")
    contract.verify_binding(document, target_path, target, "runtime")
    pending(document)
    compiler = inputs.pin(document["compilerTool"])
    resolved = shared_tools.resolve_tool("script_comp", repo=REPO, root=tools_root)
    require(str(compiler) == resolved["path"] and document["compilerTool"]["sha256"] == resolved["sha256"],
            "Compiler does not match maintained resolver")
    inputs.pin(document["header"])
    require(set(document["sources"]) == SOURCES and
        set(document["outputs"]) == {Path(n).with_suffix(".ncs").name for n in SOURCES},
        "Canonical source/output inventory differs")
    inputs.merge(document["frozenInputs"])
    require(isinstance(document["commands"], list) and len(document["commands"]) == 2,
            "Two recorded compiler commands required")
    rows = {}
    for command in document["commands"]:
        require(set(command) == {"source", "output", "argv", "exitCode", "stdout", "stderr"} and
            type(command["exitCode"]) is int and command["exitCode"] == 0 and
            command["source"] in SOURCES and command["source"] not in rows and
            command["output"] == Path(command["source"]).with_suffix(".ncs").name and
            isinstance(command["argv"], list) and all(isinstance(v, str) for v in command["argv"]) and
            len(command["argv"]) >= 2 and command["argv"][0] == str(compiler),
            "Compiler command/source/output differs")
        source = inputs.pin(document["sources"][command["source"]])
        output = inputs.pin(document["outputs"][command["output"]])
        require(source.name == command["source"] and output.name == command["output"] and
            str(source) in command["argv"] and len(output.read_bytes()) >= 13 and
            output.read_bytes()[:9] == b"NCS V1.0B" and
            int.from_bytes(output.read_bytes()[9:13], "big") == output.stat().st_size,
            "Actual fresh native script/source differs")
        inputs.pin(command["stdout"])
        inputs.pin(command["stderr"])
        rows[command["source"]] = command
    needed = {str(inputs.pin(pin)): pin["sha256"] for pin in (
        document["compilerTool"], document["header"], *document["sources"].values())}
    require(all(document["frozenInputs"].get(p) == h for p, h in needed.items()),
            "Compiler consumed input closure omits compiler/header/source")
    return document


def verify_source(proof_pin, target_path, game_root, gff_tool, *, selected_overlay_pin, tools_root=None, animation_preparation=None):
    """Independent script-only child guard; no mutation or generic exemptions."""
    import pack_stock_target_fixture as packer
    import preflight_target_body_client as preflight
    import shared_female_animation_overlay as overlay
    import shared_female_posture_fixture as fixture
    import shared_tools
    from target_animation_overlay import NativeIdleReader

    inputs = Inputs()
    current_helper_closure(inputs)
    inputs.add(Path(target_path).resolve())
    require(inputs.pin(proof_pin).is_relative_to(REPO / "output/phenotypes" / TARGET),
            "Transition proof outside consuming target")
    target = contract.load(target_path)
    require(target["id"] == TARGET and contract.rig_mode(target) == "stock-exact" and
            target["identity"]["gender"] == "female", "Stock-exact female transition target required")
    proof = inputs.read(proof_pin)
    require(isinstance(proof, dict) and set(proof) == PROOF_FIELDS and
        type(proof["schemaVersion"]) is int and proof["schemaVersion"] == 1 and
        proof["kind"] == "shared-female-stockbody-transition-native-source-proof",
        "Typed script-only transition source proof required")
    contract.verify_binding(proof, target_path, target, "runtime")
    pending(proof)
    pin_shape(selected_overlay_pin)
    require(proof["selectedOverlay"] == selected_overlay_pin, "Selected overlay authority differs")
    inputs.pin(selected_overlay_pin)
    resolved_gff = shared_tools.resolve_tool("gff", repo=REPO, root=tools_root)
    require(str(Path(gff_tool).resolve()) == resolved_gff["path"],
            "GFF decoder does not match maintained resolver")
    inputs.add(resolved_gff["path"], resolved_gff["sha256"])
    require(proof["operationCounts"] == {"nativeMODPackCalls": 1, "nativeGITEncodeCalls": 0,
        "modelCompileCalls": 0} and all(type(v) is int for v in proof["operationCounts"].values()),
        "Script-only operation counts differ")
    parent = inputs.read(proof["parentPreparation"])
    require(parent["sourceProof"] == proof["parentSourceProof"] and
        parent["postureRoster"] == proof["postureRoster"] and
        parent["postureStockBinding"] == proof["postureStockBinding"], "Original parent lineage differs")
    inputs.pin(proof["parentSourceProof"])
    parent_source = Path(proof["parentPreparation"]["path"]).resolve().parent
    # Never rewrite the old protected14/GIT-only proof to accommodate this child.
    parent_report = packer.verified_posture_stock_basis(proof["postureStockBinding"], target_path,
        parent, parent_source, inputs.add(parent["module"], parent["moduleSha256"]),
        inputs.add(Path(gff_tool).resolve()), game_root)
    require(parent_report.get("kind") == "verified-shared-female-installed-stock-basis" and
        parent_report.get("postureStockBinding") == proof["postureStockBinding"] and
        parent_report.get("postureRoster") == proof["postureRoster"],
        "Explicit verified original parent basis required")
    inputs.merge(parent_report["frozenInputs"])
    schedule = inputs.read(proof["schedule"])
    contract.verify_binding(schedule, target_path, target, "runtime")
    coverage = fixture.verify_cumulative_coverage(schedule["coverage"], target_path)
    inputs.merge(coverage["frozenInputs"])
    roster_reports = [fixture.verify_roster(pin, target_path) for pin in schedule["rosters"]]
    for report in roster_reports:
        inputs.merge(report["frozenInputs"])
    rosters = [report["document"] for report in roster_reports]
    validate_schedule(schedule, rosters)
    require(schedule["coverage"] == parent_report["coverage"] and
            proof["postureRoster"] in schedule["rosters"], "Cross-batch coverage or roster authority")
    family_rows = overlay.load_family_plan(schedule["familyPreparation"], inputs)
    for root, entry in schedule["idleTimings"].items():
        row = family_rows[root]
        require(entry["sourceNative"] == row["sourceIdleNative"] and
                entry["owner"] == row["winningIdleOwner"], "Native timing ancestry differs")
        decoded = NativeIdleReader(inputs.pin(entry["sourceNative"]).read_bytes()).decode(("pause1", "pause2"))
        for clip in ("pause1", "pause2"):
            require(entry[clip] == {k: decoded["clips"][clip][k] for k in ("length", "transition")},
                    "Actual native idle timing differs")
    animation = packer.verified_animation_overlay(proof["selectedOverlay"], target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
    inputs.merge(animation["frozenInputs"])
    animation_names = {name for root in ROOTS for name in (root + ".mdl", "srn_fa_" + root[2:] + ".mdl")}
    hash_mapping(animation["resourceHashes"], animation_names)
    compiled = _validate_compile(inputs.read(proof["compileExecution"]), inputs, target_path, target, tools_root)
    require({n: p["sha256"] for n, p in compiled["sources"].items()} == schedule["sourceNSSHashes"],
            "Compiled NSS differs from source hashes frozen in schedule")
    hash_mapping(proof["moduleResourceHashes"], MODULE)
    hash_mapping(parent["moduleResourceHashes"], MODULE)
    hash_mapping(proof["protected11ModuleResourceHashes"], MODULE - CHANGED)
    require(proof["protected11ModuleResourceHashes"] ==
        {n: h for n, h in parent["moduleResourceHashes"].items() if n not in CHANGED} ==
        {n: h for n, h in proof["moduleResourceHashes"].items() if n not in CHANGED},
        "Protected eleven resources or GIT differ")
    require(all(proof["moduleResourceHashes"][n] != parent["moduleResourceHashes"][n] for n in CHANGED),
            "Exactly four script entries must be new")
    module = inputs.pin(proof["nativeModule"])
    rows = packer.archive(module)
    expected = {(Path(n).stem, preflight.TYPE_BY_EXTENSION[Path(n).suffix]): h
                for n, h in proof["moduleResourceHashes"].items()}
    actual = {(n, k): hashlib.sha256(b).hexdigest() for n, k, b in rows}
    require(len(rows) == 15 and len(actual) == 15 and actual == expected, "Actual native MOD inventory differs")
    for name in CHANGED:
        pin = compiled["sources" if name in SOURCES else "outputs"][name]
        require(proof["moduleResourceHashes"][name] == pin["sha256"], "NSS/NCS differs from canonical compile")
    native_git = inputs.pin(proof["nativeGIT"])
    require(native_git.read_bytes() == (parent_source / "module-resources/sr_tm_floor.git").read_bytes() and
        proof["nativeGIT"]["sha256"] == proof["moduleResourceHashes"]["sr_tm_floor.git"],
        "Original native GIT bytes changed")
    current = preflight.decode_gff(rows, "sr_tm_floor", ".git", gff_tool)
    original = preflight.decode_gff(packer.archive(parent["module"]), "sr_tm_floor", ".git", gff_tool)
    require(current == original == inputs.read(proof["decodedNativeGIT"]), "Fresh native GIT decode differs")
    roster = next(r for pin, r in zip(schedule["rosters"], rosters) if pin == proof["postureRoster"])
    fixture.validate_native_actor_rows(roster, current["Creature List"]["value"])
    require(proof["fixtureResourceHashes"] == parent["fixtureResourceHashes"] and
        set(proof["fixtureResourceHashes"]) == FIXTURES and
        proof["stockTableBaselines"] == parent["stockTableBaselines"], "Fixture/table/equipment basis differs")
    return {"kind": "verified-shared-female-transition-source", **contract.binding(target_path, target, "runtime"),
        "proof": proof_pin, "sourceProof": proof_pin, "coverage": schedule["coverage"],
        "parentPreparation": proof["parentPreparation"], "schedule": proof["schedule"],
        "moduleResourceHashes": proof["moduleResourceHashes"], "postureStockBinding": proof["postureStockBinding"],
        "postureRoster": proof["postureRoster"], "selectedAnimationResourceHashes": animation["resourceHashes"],
        "frozenInputs": inputs.finish(), "visibleMotionProven": False, "clientAccepted": False,
        "runtimeSelected": False, "productionAccepted": False}


def verify_trace(trace_pin, target_path):
    """Read pinned schedule/rosters before validating logs; no visual approval."""
    import shared_female_posture_fixture as fixture
    inputs = Inputs()
    current_helper_closure(inputs)
    target = contract.load(inputs.add(Path(target_path).resolve()))
    trace = inputs.read(trace_pin)
    schedule = inputs.read(trace["schedule"])
    contract.verify_binding(schedule, target_path, target, "runtime")
    coverage = fixture.verify_cumulative_coverage(schedule["coverage"], target_path)
    inputs.merge(coverage["frozenInputs"])
    reports = [fixture.verify_roster(pin, target_path) for pin in schedule["rosters"]]
    for report in reports:
        inputs.merge(report["frozenInputs"])
    rosters = [report["document"] for report in reports]
    validate_schedule(schedule, rosters)
    require(trace["roster"] in schedule["rosters"], "Trace roster outside schedule")
    roster = rosters[schedule["rosters"].index(trace["roster"])]
    report = validate_trace(schedule, roster, trace)
    return {**report, "trace": trace_pin, "frozenInputs": inputs.finish()}


def collect_source_inputs(proof_pin, target_path):
    """Register direct reads for a later guarded verifier; no tool calls or approval."""
    import shared_female_animation_overlay as overlay
    import shared_female_posture_fixture as fixture
    import shared_female_stock_basis as basis
    inputs = Inputs()
    current_helper_closure(inputs)
    inputs.add(Path(target_path).resolve())
    proof = inputs.read(proof_pin)
    require(set(proof) == PROOF_FIELDS and proof['kind'] ==
        'shared-female-stockbody-transition-native-source-proof', 'Typed transition proof required')
    pending(proof)
    schedule = inputs.read(proof['schedule'])
    inputs.merge(fixture.verify_cumulative_coverage(schedule['coverage'], target_path)['frozenInputs'])
    for entry in schedule['rosters']:
        inputs.merge(fixture.verify_roster(entry, target_path)['frozenInputs'])
    inputs.merge(basis.collect_stock_basis_inputs(proof['postureStockBinding'], target_path, proof['postureRoster']))
    inputs.merge(overlay.collect_overlay_inputs(proof['selectedOverlay'], target_path))
    family = inputs.read(schedule['familyPreparation'])
    for entry in schedule['idleTimings'].values(): inputs.pin(entry['sourceNative'])
    parent = inputs.read(proof['parentPreparation'])
    inputs.add(Path(parent['module']), parent['moduleSha256'])
    ancestor = Path(proof['parentPreparation']['path']).resolve().parent
    for folder, key in (('module-resources','moduleResourceHashes'), ('hak-resources','fixtureResourceHashes')):
        for name,digest in parent[key].items(): inputs.add(ancestor/folder/name,digest)
    parent_proof = inputs.read(proof['parentSourceProof'])
    original = inputs.read(parent_proof['parentSourcePreparation'])
    original_folder = Path(parent_proof['parentSourcePreparation']['path']).resolve().parent
    for folder,key in (('module-resources','moduleResourceHashes'), ('hak-resources','fixtureResourceHashes')):
        for name,digest in original[key].items(): inputs.add(original_folder/folder/name,digest)
    for entry in parent_proof.values():
        if isinstance(entry,dict) and set(entry)=={'path','sha256'}: inputs.pin(entry)
    compiled = inputs.read(proof['compileExecution'])
    inputs.merge(compiled['frozenInputs'])
    inputs.pin(compiled['compilerTool']);inputs.pin(compiled['header'])
    for entry in (*compiled['sources'].values(),*compiled['outputs'].values()): inputs.pin(entry)
    for command in compiled['commands']:
        inputs.pin(command['stdout']);inputs.pin(command['stderr'])
    inputs.pin(proof['nativeModule']);inputs.pin(proof['nativeGIT']);inputs.pin(proof['decodedNativeGIT'])
    return inputs.finish()
