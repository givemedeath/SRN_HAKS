"""Typed, read-only all-race posture roster and matched package boundaries.

A diagnostic roster is separate from Human body selection and asset acceptance.
Native GFF decoding remains the caller's explicit, frozen tool operation.
"""
from pathlib import Path
import hashlib
import re
import target_contract as contract
from audit_pelvis_package import archive
import shared_female_animation_overlay as overlay
from shared_female_native_contract import ROOTS

BATCHES = ("batch-1", "batch-2", "batch-3", "batch-4")
ROSTER_FIELDS = {"schemaVersion", "kind", "familyPreparation", "batchId", "moduleName",
                "actorAreaResref", "bodySource", "actors"} | overlay.BINDING_FIELDS
ACTOR_FIELDS = {"tag", "purpose", "raceId", "appearanceId", "gender", "phenotypeId",
    "femaleRoot", "headStyle", "bodyStyle", "skinPalette", "poseId", "clip", "equipment", "placement"}
PLACEMENT_FIELDS = {"XPosition", "YPosition", "ZPosition", "XOrientation", "YOrientation"}
GFF_FIELDS = {"Appearance_Type": ("word", "appearanceId"), "Race": ("byte", "raceId"),
    "Gender": ("byte", "gender"), "Phenotype": ("int", "phenotypeId"),
    "Appearance_Head": ("byte", "headStyle"), "Color_Skin": ("byte", "skinPalette")}
BINDING = contract.binding


def validate_roster_document(roster, rows):
    contract.require(set(roster) == ROSTER_FIELDS and type(roster["schemaVersion"]) is int and
        roster["schemaVersion"] == 1 and roster["kind"] == "shared-female-posture-actor-roster" and
        roster["batchId"] in BATCHES and roster["moduleName"] == "srn_female_test" and
        roster["actorAreaResref"] == "sr_tm_floor" and roster["bodySource"] == "installed-stock-shared-female",
        "Typed shared female diagnostic roster required")
    actors = roster["actors"]
    contract.require(isinstance(actors, list) and len(actors) == 8 and
        {a.get("tag") for a in actors} == {"tm_"+str(i) for i in range(8)}, "Eight unique controllable actors required")
    required = []
    for actor in actors:
        contract.require(set(actor) == ACTOR_FIELDS and actor["purpose"] in {"required-case", "equipment-control"},
                         "Typed actor purpose/fields required")
        root = actor["femaleRoot"]
        contract.require(root in rows, "Undeclared actor family")
        cases = {(x["raceId"], x["appearanceId"], x["phenotypeId"]) for x in rows[root]["actorCases"]}
        contract.require((actor["raceId"], actor["appearanceId"], actor["phenotypeId"]) in cases and
            all(type(actor[k]) is int for k in ("raceId", "appearanceId", "gender", "phenotypeId",
                "headStyle", "bodyStyle", "skinPalette", "poseId")) and
            actor["gender"] == actor["headStyle"] == actor["bodyStyle"] == 1 and
            actor["skinPalette"] in (3, 8) and actor["poseId"] in (0, 1) and
            actor["clip"] == ("pause1", "pause2")[actor["poseId"]], "Actor identity/style/idle differs")
        placement = actor["placement"]
        contract.require(set(placement) == PLACEMENT_FIELDS and all(
            type(v) in (int, float) and v == v and abs(v) < 1e6 for v in placement.values()),
            "Explicit finite actor placement required")
        gear = actor["equipment"]
        contract.require(isinstance(gear, list) and len({g.get("slotMask") for g in gear}) == len(gear),
                         "Unique explicit equipment slots required")
        for item in gear:
            contract.require(set(item) == {"slotMask", "resref", "nativeUTI", "decodedUTI"} and
                type(item["slotMask"]) is int and item["slotMask"] > 0 and
                isinstance(item["resref"], str) and re.fullmatch("[a-z0-9_]{1,16}", item["resref"]),
                "Typed stock equipment input required")
        if actor["purpose"] == "required-case":
            required.append((actor["raceId"], actor["phenotypeId"], actor["clip"]))
    contract.require(len(required) == len(set(required)), "Duplicate required coverage cell")
    contract.require({a["skinPalette"] for a in actors} == {3, 8}, "Both declared palette indices required")
    return required


def verify_roster(roster_pin, target_path):
    target = contract.load(target_path)
    overlay.require_target(target, target_path)
    inputs = overlay.Inputs(overlay.REPO/"output/phenotypes"/overlay.TARGET)
    inputs.add(target_path)
    roster = inputs.read(roster_pin)
    contract.verify_binding(roster, target_path, target, "runtime")
    rows = overlay.load_family_plan(roster["familyPreparation"], inputs)
    cells = validate_roster_document(roster, rows)
    for actor in roster["actors"]:
        for item in actor["equipment"]:
            inputs.pin(item["nativeUTI"])
            decoded = inputs.read(item["decodedUTI"])
            contract.require(decoded.get("TemplateResRef") == {"type": "resref", "value": item["resref"]},
                             "Stock equipment template identity differs")
    return {"kind": "verified-shared-female-posture-roster", "roster": roster_pin, "document": roster,
        "requiredCells": cells, "frozenInputs": inputs.finish(), "clientAccepted": False, "runtimeSelected": False}


def validate_native_actor_rows(roster, actors):
    """Validate actually decoded native GIT/UTC rows, including each GFF type."""
    expected = {a["tag"]: a for a in roster["actors"]}
    contract.require(isinstance(actors, list) and len(actors) == 8 and
        all(isinstance(a.get("Tag"), dict) and a["Tag"].get("type") == "cexostring" for a in actors) and
        {a["Tag"].get("value") for a in actors} == set(expected), "Native actor tag inventory differs")
    for actual in actors:
        wanted = expected[actual["Tag"]["value"]]
        for field, (kind, key) in GFF_FIELDS.items():
            contract.require(actual.get(field) == {"type": kind, "value": wanted[key]},
                             "Native typed actor field differs: "+field)
        for field, value in wanted["placement"].items():
            contract.require(actual.get(field) == {"type": "float", "value": value}, "Native actor placement differs")
        equipment = actual.get("Equip_ItemList", {})
        contract.require(equipment.get("type") == "list", "Native equipment list missing")
        actual_gear = [(g["__struct_id"], g.get("EquippedRes")) for g in equipment.get("value", [])]
        wanted_gear = [(g["slotMask"], {"type": "resref", "value": g["resref"]}) for g in wanted["equipment"]]
        contract.require(actual_gear == wanted_gear, "Native actor equipment differs")
        var_table = actual.get("VarTable", {})
        contract.require(var_table.get("type") == "list", "Native actor locals missing")
        locals_ = {}
        for var in var_table.get("value", []):
            name = var.get("Name", {})
            contract.require(name.get("type") == "cexostring" and name.get("value") not in locals_,
                             "Duplicate or untyped actor local")
            locals_[name.get("value")] = var
        for key, value in (("TM_POSE", wanted["poseId"]), ("TM_PALETTE", wanted["skinPalette"])):
            local = locals_.get(key, {})
            contract.require(local.get("Type") == {"type": "dword", "value": 1} and
                local.get("Value") == {"type": "int", "value": value}, "Native actor schedule/palette local differs")
    return {"typedActors": 8, "headFieldsPresent": True, "clientAccepted": False}


def verify_cumulative_coverage(manifest_pin, target_path):
    target = contract.load(target_path)
    inputs = overlay.Inputs(overlay.REPO/"output/phenotypes"/overlay.TARGET)
    manifest = inputs.read(manifest_pin)
    expected_fields = {"schemaVersion", "kind", "familyPreparation", "rosters"} | overlay.BINDING_FIELDS
    contract.require(set(manifest) == expected_fields and type(manifest["schemaVersion"]) is int and
        manifest["schemaVersion"] == 1 and manifest["kind"] == "shared-female-posture-cumulative-coverage",
        "Typed cumulative roster manifest required")
    contract.verify_binding(manifest, target_path, target, "runtime")
    rows = overlay.load_family_plan(manifest["familyPreparation"], inputs)
    contract.require(isinstance(manifest["rosters"], list) and len(manifest["rosters"]) == 4,
                     "Four explicitly pinned roster batches required")
    cells, batches = [], []
    for pin in manifest["rosters"]:
        verified = verify_roster(pin, target_path)
        roster = verified["document"]
        contract.require(roster["familyPreparation"] == manifest["familyPreparation"], "Cross-family roster authority")
        cells.extend(tuple(x) for x in verified["requiredCells"])
        batches.append(roster["batchId"])
        for path, digest in verified["frozenInputs"].items():
            inputs.add(path, digest)
    expected = {(case["raceId"], case["phenotypeId"], clip) for row in rows.values()
                for case in row["actorCases"] for clip in ("pause1", "pause2")}
    contract.require(set(batches) == set(BATCHES) and len(set(batches)) == 4 and len(cells) == 28 and
        len(set(cells)) == 28 and set(cells) == expected, "Complete 28-cell race/phenotype/idle coverage required")
    return {"kind": "verified-shared-female-posture-cumulative-coverage", "requiredCells": sorted(expected),
            "frozenInputs": inputs.finish(), "clientAccepted": False, "runtimeSelected": False}



def matched_stock_binding(stock, candidate):
    """Require one explicit installed stock, game, and roster authority per pair."""
    def valid_pin(value):
        return isinstance(value, dict) and set(value) == {"path", "sha256"} and \
            isinstance(value["path"], str) and Path(value["path"]).is_absolute() and \
            isinstance(value["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", value["sha256"])
    stock_pin = stock.get("postureStockBinding")
    contract.require(valid_pin(stock_pin) and stock_pin == candidate.get("postureStockBinding"),
                     "Exact same explicit postureStockBinding required")
    roster_pin = stock.get("postureRoster")
    contract.require(valid_pin(roster_pin) and roster_pin == candidate.get("postureRoster"),
                     "Exact same explicit posture roster required")
    game = stock.get("gameRoot")
    contract.require(isinstance(game, str) and Path(game).is_absolute() and
        game == candidate.get("gameRoot"), "Exact same explicit installed game root required")
    return stock_pin, game


def matched_payloads(stock, candidate, animation_hashes):
    """Read actual archive payloads; a claimed matching package is insufficient."""
    matched_stock_binding(stock, candidate)
    require_pin = lambda path, digest: contract.require(overlay.FILE_SHA(path) == digest, "Matched package hash differs")
    for build in (stock, candidate):
        for key in ("hak", "module"):
            require_pin(build[key], build[key+"Sha256"])
        contract.require(build.get("bodyConverted") is None and build.get("rigConverted") is None and
            build.get("provisionalConverted") is None and build.get("clientAccepted") is False,
            "Posture comparison must retain installed body/rig and pending acceptance")
    require_pin(stock["module"], candidate["moduleSha256"])
    contract.require(Path(stock["module"]).read_bytes() == Path(candidate["module"]).read_bytes() and
        stock["moduleResourceHashes"] == candidate["moduleResourceHashes"], "Matched native module differs")
    def payload(path):
        return {(name, kind): hashlib.sha256(value).hexdigest() for name, kind, value in archive(path)}
    a, b = payload(stock["hak"]), payload(candidate["hak"])
    fixture_names = {"sr_tm.set", "sr_tm_edge.2da"}
    contract.require(set(stock["fixtureResourceHashes"]) == fixture_names,
                     "Only the two declared fixture dependencies may be packed")
    fixture_payload = {("sr_tm", 2013): stock["fixtureResourceHashes"]["sr_tm.set"],
                       ("sr_tm_edge", 2017): stock["fixtureResourceHashes"]["sr_tm_edge.2da"]}
    contract.require(a == fixture_payload, "Stock fixture contains an undeclared body/rig/table resource")
    names = {name for root in ROOTS for name in (root+".mdl", "srn_fa_"+root[2:]+".mdl")}
    contract.require(set(animation_hashes) == names and len(animation_hashes) == 24, "Verified 24-resource group required")
    added = {(Path(name).stem, 2002): digest for name, digest in animation_hashes.items()}
    contract.require(not set(a) & set(added) and b == {**a, **added} and
        stock.get("animationResourceHashes", {}) == {} and candidate.get("animationResourceHashes") == animation_hashes,
        "Only the verified animation resources may differ")
    contract.require(stock["fixtureResourceHashes"] == candidate["fixtureResourceHashes"] and
        stock["configuration"] == candidate["configuration"], "Matched fixture configuration differs")
    return {"matchedModuleBytesExact": True, "animationOnlyPayloadDifference": True,
        "animationResources": 24, "clientAccepted": False, "nativeActorValidationRequired": True}


def matched_transition_binding(stock, candidate, proof_pin, overlay_pin):
    """A script child must be independently requested on both matched sides."""
    fields = ('transitionSourceProof','transitionAnimationAuthority')
    declared = any(field in build for build in (stock,candidate) for field in fields)
    if proof_pin is None:
        contract.require(not declared, 'Transition matched pair requires an explicit source proof')
        return False
    contract.require(isinstance(proof_pin,dict) and set(proof_pin)=={'path','sha256'} and
        all(build.get('transitionSourceProof') == build.get('postureSourceProof') == proof_pin and
            build.get('transitionAnimationAuthority') == overlay_pin for build in (stock,candidate)) and
        stock.get('sourcePreparation') == candidate.get('sourcePreparation'),
        'Matched transition source or animation authority differs')
    return True


def verify_matched_packages(stock_pin, candidate_pin, overlay_pin, roster_pin, target_path, declared_inputs=None, transition_source_proof=None, animation_preparation=None):
    # The stock basis imports this module for typed roster validation.
    # Import only when called, after both modules have finished loading.
    import shared_female_stock_basis as stock_basis
    inputs = stock_basis.Inputs()
    target_path = inputs.add(target_path)
    target = contract.load(target_path)
    overlay.require_target(target, target_path)
    stock, candidate = inputs.read(stock_pin), inputs.read(candidate_pin)
    basis_pin, game = matched_stock_binding(stock, candidate)
    transition_child = matched_transition_binding(stock,candidate,transition_source_proof,overlay_pin)
    for build in (stock, candidate):
        contract.verify_binding(build, target_path, target, "runtime")
        contract.require(build.get("postureRoster") == roster_pin, "Exact matched roster pin required")
        for key in ("hak", "module"):
            inputs.add(build[key], build[key+"Sha256"])
    installed = stock_basis.verify_stock_basis(basis_pin, target_path, roster_pin,
                                               game_root=game, live_source_lookup=False)
    roster = verify_roster(roster_pin, target_path)
    animation = overlay.verify_shared_female_animation_overlay(overlay_pin, target_path,**({'preparation':animation_preparation} if animation_preparation is not None else {}))
    for proof in (installed, roster, animation):
        inputs.merge(proof["frozenInputs"])

    if transition_child:
        from pack_stock_target_fixture import verified_posture_source
        prepared_path = inputs.pin(stock['sourcePreparation'])
        prepared = overlay.strict_json(prepared_path)
        source = verified_posture_source(basis_pin,target_path,prepared,prepared_path.parent,
            Path(stock['module']),inputs.add(Path(stock['gffTool']),stock['gffToolSha256']),Path(game),
            transition_source_proof,overlay_pin,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        inputs.merge(source['frozenInputs'])
    result = matched_payloads(stock, candidate, animation["resourceHashes"])
    consumed = inputs.finish()
    if declared_inputs is not None:
        overlay.require_declared_inputs(consumed, declared_inputs)
    return {**result, "kind": "verified-matched-shared-female-posture-packages",
        "postureStockBinding": basis_pin, "postureRoster": roster_pin, "gameRoot": game,
        "sourceAncestryResources": installed["sourceAncestryResources"],
        "headNeckEquipmentIndividuallyDecoded": installed["headNeckEquipmentIndividuallyDecoded"],
        "dynamicLimits": installed["dynamicLimits"],
        "liveSourceLookupExecuted": False, "recordedLookupsProveExecutionLineageOnly": True,
        "frozenInputs": consumed, "productionAccepted": False}


def collect_matched_package_inputs(stock_pin, candidate_pin, overlay_pin, roster_pin, target_path):
    """Collect the same read-only proof closure, streaming installed archives.

    This performs the bounded package/overlay/basis verification without live
    tool calls. It grants no actor visual, client, or production acceptance.
    """
    return verify_matched_packages(stock_pin, candidate_pin, overlay_pin, roster_pin,
                                   target_path)["frozenInputs"]
