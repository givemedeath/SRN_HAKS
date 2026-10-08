"""Typed diagnostic ownership of all twelve shared female standing roots.

This is an additional boundary. The existing single-Human verifier stays intact.
Only exact byte descendants and native source/controller checks grant ownership.
"""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import target_contract as contract
import target_animation_overlay as human
from shared_female_native_contract import (ROOTS, INHERITED, expected_identity,
    verify_root_token, ascii_bind, inherited_bind, check_native)

REPO = Path(__file__).resolve().parents[2]
TARGET = "human-female-fit-purposebuilt-v1"
KIND = "executed-shared-female-source-native-idle-overlay"
FAMILY_SHA = "e8c81b45f97249a83dbdba8cfed635233277d0ea0ebbab401151cf4b1a037198"
NUMERIC_SHA = "0739683550694507f1f4b0ae1152a191a55c0fbe1b9353dc37e0f583fdaa53d1"
COMPILER_SHA = "3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a"
FAMILY_FIELDS = {"kind", "sourceRoot", "sourceNativeOwner", "preparation", "compile",
    "rangePlan", "restoration", "independentReview", "rootLink", "resources"}
BINDING_FIELDS = {"targetContract", "targetContractSha256", "targetId", "rigRevision", "coordinateSpace"}
TOP_FIELDS = {"schemaVersion", "kind", "executed", "scope", "clientAccepted", "runtimeSelected",
    "productionAccepted", "familyPreparation", "numericCorrectedArrays", "families"} | BINDING_FIELDS
RACES = {"a": ((3, 3),), "d": ((0, 0),), "e": ((1, 1),), "g": ((2, 2),),
         "h": ((4, 4), (6, 6)), "o": ((5, 5),)}
FILE_SHA = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            contract.require(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("Nonfinite JSON scalar")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=pairs, parse_constant=nonfinite)


class Inputs:
    """One collector is used by verification and launch input preparation."""
    def __init__(self, area):
        self.area = Path(area).resolve()
        self.files = {}

    def add(self, path, digest=None, inside=False):
        path = Path(path).resolve()
        contract.require(path.is_file() and (not inside or path.is_relative_to(self.area)),
                         "Missing or outside-target consumed input")
        actual = FILE_SHA(path)
        if digest is not None:
            contract.require(isinstance(digest, str) and re.fullmatch("[a-f0-9]{64}", digest) and
                             actual == digest, "Consumed input hash differs")
        key = str(path)
        contract.require(key not in self.files or self.files[key] == actual, "Conflicting consumed input")
        self.files[key] = actual
        return path

    def pin(self, row, inside=True):
        contract.require(isinstance(row, dict) and set(row) == {"path", "sha256"}, "Exact file pin required")
        return self.add(row["path"], row["sha256"], inside)

    def read(self, row, inside=True):
        return strict_json(self.pin(row, inside))

    def finish(self):
        for path, digest in self.files.items():
            contract.require(FILE_SHA(path) == digest, "Consumed input drift")
        return dict(self.files)


def validate_family_plan(plan):
    contract.require(plan.get("kind") == "UNEXECUTED-source-native-female-family-extension-preparation" and
                     plan.get("pass") is True and type(plan.get("totalRoots")) is int and
                     plan["totalRoots"] == 12 and plan.get("standingActorCases") == 14 and
                     plan.get("productionAnimationResourceTotal") == 24, "Frozen family plan differs")
    rows = plan.get("rows")
    contract.require(isinstance(rows, list) and len(rows) == 12 and
                     {r.get("root") for r in rows} == set(ROOTS), "Complete family rows required")
    result = {}
    for row in rows:
        root = row["root"]
        parent, owner, scale = expected_identity(root)
        contract.require(row["carrier"] == "srn_fa_"+root[2:] and row["originalParent"] == parent and
            row["winningIdleOwner"] == owner and row["carrierScale"] == 1 and
            float(row["literalActorScaleToken"]) == float(scale) and row["actorOwnedCarrierStaticNodes"] == 56 and
            row["expectedEditedControllers"] == 16 and
            row["expectedUntouchedControllers"] == (78 if owner == "a_ba" else 84),
            "Family source identity/static/scale contract differs")
        cases = row["actorCases"]
        expected = {(race, appearance, int(root[3]), root) for race, appearance in RACES[root[2]]}
        actual = {(x["raceId"], x["appearanceId"], x["phenotypeId"], x["femaleRoot"]) for x in cases}
        contract.require(actual == expected and len(cases) == len(expected), "Family actor cases differ")
        result[root] = row
    return result


def load_family_plan(pin, inputs):
    contract.require(pin["sha256"] == FAMILY_SHA, "Foreign family authority")
    return validate_family_plan(inputs.read(pin))


def require_target(target, target_path):
    identity = target["identity"]
    contract.require(target["id"] == TARGET and contract.rig_mode(target) == "stock-exact" and
        identity["prefix"] == "pfh0" and identity["gender"] == "female" and
        identity["raceId"] == identity["appearanceRow"] == 6 and identity["phenotype"] == 0 and
        target["rig"]["runtimeScale"] == 1, "Shared female experiment must have its original target authority")


def validate_family_entry(entry, root):
    contract.require(isinstance(entry, dict) and set(entry) == FAMILY_FIELDS and
        entry["kind"] == "executed-family-source-native-idle-overlay", "Typed family entry required")
    names = {root+".mdl", "srn_fa_"+root[2:]+".mdl"}
    contract.require(isinstance(entry["resources"], dict) and set(entry["resources"]) == names,
                     "Exact two-resource family ownership required")


def consume_family(entry, root, row, family_pin, numeric_pin, inputs):
    """All actual reads are registered here; unused historical mappings are not scanned."""
    validate_family_entry(entry, root)
    documents = {key: inputs.read(entry[key]) for key in
        ("preparation", "compile", "rangePlan", "restoration", "independentReview", "rootLink")}
    inputs.pin(entry["sourceRoot"])
    inputs.pin(entry["sourceNativeOwner"])
    for pin in entry["resources"].values():
        inputs.pin(pin)
    for key in ("sourceActorRoot", "sourceIdleNative", "sourceIdleASCII", "originalNativeArchive"):
        inputs.pin(row[key])
    for ancestor in row["sourceAncestry"]:
        inputs.pin(ancestor["native"])
        inputs.pin(ancestor["ascii"])
    for inherited in row["inheritedStaticOmissions"]:
        inputs.pin(inherited["native"])
    prep, compilation = documents["preparation"], documents["compile"]
    for key in ("sourceASCII", "numericExpectedArrays", "reservation"):
        inputs.pin(prep[key])
    execution = inputs.read(compilation["execution"])
    inputs.pin(compilation["native"])
    for key in ("stdout", "stderr"):
        inputs.pin(execution[key])
    # Direct compiler identity is bound to the compiled execution; old binding snapshots
    # are historical provenance and are not recursively treated as current dependencies.
    contract.require(compilation["resolvedNativeCompiler"]["sha256"] == COMPILER_SHA,
                     "Different native compiler identity")
    inputs.pin({k: compilation["resolvedNativeCompiler"][k] for k in ("path", "sha256")}, inside=False)
    return documents, execution


def verify_lineage(documents, execution, entry, row, family_pin, numeric_pin):
    root, carrier = row["root"], row["carrier"]
    prep, compilation = documents["preparation"], documents["compile"]
    plan, restoration, review, link = [documents[k] for k in ("rangePlan", "restoration", "independentReview", "rootLink")]
    source, native = row["sourceIdleNative"], entry["resources"][carrier+".mdl"]
    contract.require(entry["sourceRoot"] == row["sourceActorRoot"] and
        entry["sourceNativeOwner"] == source, "Cross-family source pins")
    contract.require(prep.get("kind") == "one-family-source-native-carrier-preparation" and
        prep.get("targetId") == TARGET and prep.get("familyPreparation") == family_pin and
        prep.get("sourceActorRoot") == row["sourceActorRoot"] and prep.get("sourceNativeOwner") == source and
        type(prep.get("compileCalls")) is int and prep["compileCalls"] == 0,
        "Family author lineage differs")
    contract.require(compilation.get("kind") == "one-family-source-native-compile" and
        compilation.get("rootId") == root and compilation.get("carrier") == carrier and
        compilation.get("familyPreparation") == family_pin and compilation.get("preparation") == entry["preparation"] and
        compilation.get("restorationApplied") is False, "Family compile lineage differs")
    contract.require(type(execution.get("compileCalls")) is int and execution["compileCalls"] == 1 and
        type(execution.get("exitCode")) is int and execution["exitCode"] == 0 and
        execution.get("interactiveClientLaunched") is False and
        execution.get("native") == compilation["native"] and
        execution.get("command", [])[-2:] == ["compilemodel", carrier] and
        Path(execution["command"][0]).resolve() == Path(compilation["resolvedNativeCompiler"]["path"]).resolve(),
        "Exactly one successful noninteractive compiler invocation required")
    common = plan.get("familyPreparation") == review.get("familyPreparation") == family_pin
    contract.require(common and plan.get("kind") == "independent-family-source-native-restoration-plan" and
        plan.get("pass") is True and plan.get("executed") is False and plan.get("rootId") == root and
        plan.get("carrier") == carrier and plan.get("compile") == entry["compile"] and
        plan.get("preparation") == entry["preparation"] and plan.get("parentNative") == compilation["native"] and
        plan.get("sourceNativeOriginal") == source and plan.get("numericArchive") == numeric_pin,
        "Frozen independent restoration plan differs")
    contract.require(restoration.get("kind") == "executed-family-source-native-payload-restoration" and
        restoration.get("rootId") == root and restoration.get("carrier") == carrier and
        restoration.get("familyPreparation") == family_pin and restoration.get("rangePlan") == entry["rangePlan"] and
        restoration.get("source") == source and restoration.get("parentNative") == compilation["native"] and
        restoration.get("native") == native and restoration.get("clientEvidence") is False and
        restoration.get("runtimeSelected") is False, "Executed restoration closure differs")
    contract.require(review.get("kind") == "independent-family-source-native-posture-review" and
        review.get("pass") is True and review.get("phase") == "after-restoration" and
        review.get("targetId") == TARGET and review.get("rootId") == root and review.get("carrier") == carrier and
        review.get("compile") == entry["compile"] and review.get("parentNative") == compilation["native"] and
        review.get("native") == native and review.get("originalSourceOwner") == source and
        review.get("root") == row["sourceActorRoot"] and review.get("numericArchive") == numeric_pin and
        review.get("executedRestorationReceipt") == entry["restoration"] and
        review.get("pendingRestoration") is False and review.get("allUneditedNativePayloadsExact") is True and
        review.get("outsideRestorationRangesByteExact") is True and review.get("editedTimestampWordsExact") is True and
        review.get("uneditedControllers") == row["expectedUntouchedControllers"] and
        review.get("editedControllers") == 16 and review.get("staticOwners") == 56 and
        review.get("clientEvidence") is False and review.get("runtimeSelected") is False,
        "Completed independent native review required")
    contract.require(link.get("kind") == "executed-family-parent-token-root-descendant" and link.get("targetId") == TARGET and
        link.get("rootId") == root and link.get("carrier") == carrier and link.get("familyPreparation") == family_pin and
        link.get("sourceRoot") == row["sourceActorRoot"] and link.get("rootResource") == entry["resources"][root+".mdl"] and link.get("carrierResource") == native and
        link.get("sourceNativeOwner") == source and link.get("preparation") == entry["preparation"] and
        link.get("compile") == entry["compile"] and link.get("rangePlan") == entry["rangePlan"] and
        link.get("restoration") == entry["restoration"] and link.get("independentReview") == entry["independentReview"] and
        link.get("originalActorScaleToken") == row["literalActorScaleToken"] and
        type(link.get("compilerCalls")) is int and link["compilerCalls"] == 0 and
        link.get("allOtherRootBytesExact") is True and link.get("staticHierarchyBytesPreserved") is True and
        link.get("productionAccepted") is False and link.get("clientEvidence") is False and link.get("runtimeSelected") is False,
        "Executed root-token lineage differs")


def consume_overlay(receipt_pin, target_path):
    target_path = Path(target_path).resolve()
    target = contract.load(target_path)
    require_target(target, target_path)
    inputs = Inputs(REPO/"output/phenotypes"/TARGET)
    inputs.add(target_path)
    for path, digest in target.get("frozenInputs", {}).items():
        inputs.add(path, digest)
    stock = inputs.read(target["rig"]["stockReferenceReceipt"], inside=False)
    for path, digest in stock.get("frozenInputs", {}).items():
        inputs.add(path, digest)
    inputs.pin(stock["rootAscii"], inside=False)
    for module in (__file__, human.__file__, contract.__file__):
        inputs.add(module)
    from shared_female_native_contract import __file__ as native_code
    inputs.add(native_code)
    receipt = inputs.read(receipt_pin)
    contract.require(set(receipt) == TOP_FIELDS and type(receipt["schemaVersion"]) is int and
        receipt["schemaVersion"] == 1 and receipt["kind"] == KIND and receipt["executed"] is True and
        receipt["scope"] == "all-shared-female-standing-races" and receipt["clientAccepted"] is False and
        receipt["runtimeSelected"] is False and receipt["productionAccepted"] is False,
        "Executed diagnostic all-family receipt required")
    contract.verify_binding(receipt, target_path, target, "runtime")
    contract.require(set(receipt["families"]) == set(ROOTS), "Exactly twelve declared families required")
    rows = load_family_plan(receipt["familyPreparation"], inputs)
    contract.require(receipt["numericCorrectedArrays"]["sha256"] == NUMERIC_SHA, "Foreign numeric corrections")
    inputs.pin(receipt["numericCorrectedArrays"])
    human_entry = receipt["families"]["pfh0"]
    contract.require(set(human_entry) == {"kind", "receipt"} and human_entry["kind"] == "existing-human-overlay",
                     "Human must use its unchanged original verifier")
    human_receipt = inputs.read(human_entry["receipt"])
    for key in ("compile", "preparation", "rangePlan", "restoration", "independentReview",
                "sourceRoot", "sourceNativeOwner", "numericCorrectedArrays"):
        inputs.pin(human_receipt[key])
    for pin in human_receipt["resources"].values():
        inputs.pin(pin)
    human_compile = inputs.read(human_receipt["compile"])
    inputs.pin(human_compile["native"])
    inputs.pin(human_compile["execution"])
    docs = {}
    for root in ROOTS:
        if root != "pfh0":
            docs[root] = consume_family(receipt["families"][root], root, rows[root],
                receipt["familyPreparation"], receipt["numericCorrectedArrays"], inputs)
    return target, receipt, rows, inputs, docs


def collect_overlay_inputs(receipt_pin, target_path):
    """Freeze exactly the selected verifier's data reads, without approving assets."""
    _, receipt, _, inputs, _ = consume_overlay(receipt_pin, target_path)
    human_result = human.verify_animation_overlay(receipt["families"]["pfh0"]["receipt"], target_path)
    for path, digest in human_result["frozenInputs"].items():
        inputs.add(path, digest)
    return inputs.finish()


def require_declared_inputs(consumed, declared):
    contract.require(isinstance(declared, dict) and all(declared.get(p) == h for p, h in consumed.items()),
                     "Verifier consumed an undeclared or changed input")


def verify_shared_female_animation_overlay(receipt_pin, target_path, declared_inputs=None, preparation=None):
    if preparation is not None:
        from animation_verification_preparation import AnimationVerificationPreparation
        contract.require(type(preparation) is AnimationVerificationPreparation, 'Exact run-scoped animation preparation required')
        report = preparation.verify(receipt_pin,target_path)
        if declared_inputs is not None: require_declared_inputs(report['frozenInputs'],declared_inputs)
        return report
    target, receipt, rows, inputs, docs = consume_overlay(receipt_pin, target_path)
    human_result = human.verify_animation_overlay(receipt["families"]["pfh0"]["receipt"], target_path)
    for path, digest in human_result["frozenInputs"].items():
        inputs.add(path, digest)
    require_target(target, target_path)
    resources = dict(human_result["resourceHashes"])
    paths = dict(human_result["resourcePaths"])
    reports = {"pfh0": human_result}
    numeric_path = inputs.pin(receipt["numericCorrectedArrays"])
    with np.load(numeric_path, allow_pickle=False) as archive:
        numeric = {name: archive[name] for name in archive.files}
    for root in ROOTS:
        if root == "pfh0":
            continue
        row, entry = rows[root], receipt["families"][root]
        documents, execution = docs[root]
        verify_lineage(documents, execution, entry, row, receipt["familyPreparation"], receipt["numericCorrectedArrays"])
        original = inputs.pin(entry["sourceRoot"]).read_bytes()
        descendant = inputs.pin(entry["resources"][root+".mdl"]).read_bytes()
        token = verify_root_token(row, original, descendant)
        contract.require(documents["rootLink"].get("parentTokenEdit") == {"sourceStart": token[0], "sourceEnd": token[1], "originalToken": row["originalParent"], "newToken": row["carrier"]}, "Root link token range differs")
        skeleton = inherited_bind(row, ascii_bind(original, root), inputs.pin)
        compilation = documents["compile"]
        source = inputs.pin(entry["sourceNativeOwner"]).read_bytes()
        parent = inputs.pin(compilation["native"]).read_bytes()
        result = inputs.pin(entry["resources"][row["carrier"]+".mdl"]).read_bytes()
        measured = check_native(row, source, parent, result, skeleton, numeric)
        plan, restoration = documents["rangePlan"], documents["restoration"]
        for item in plan["rows"]:
            contract.require(set(item) == {"clip", "node", "type", "field", "sourceRange", "destinationRange",
                "sourceBytesSHA256", "destinationBytesSHA256"} and type(item["type"]) is int and
                all(isinstance(item[k], list) and len(item[k]) == 2 and
                    all(type(x) is int for x in item[k]) for k in ("sourceRange", "destinationRange")),
                "Typed restoration range row required")
        contract.require(all(isinstance(span, list) and len(span) == 2 and
            all(type(x) is int for x in span) for span in plan["modifiedControllerRanges"]),
            "Typed protected controller ranges required")
        # The independent readers may visit children in different orders. Every
        # disjoint row's identity, ranges and hashes must still match exactly.
        row_key = lambda item: (item["clip"], item["node"], item["type"], item["field"])
        contract.require(sorted(plan["rows"], key=row_key) == sorted(measured["rows"], key=row_key) and
            sorted(plan["modifiedControllerRanges"]) == sorted(measured["modifiedControllerRanges"]) and
            plan["expectedResultSha256"] == measured["expectedResultSha256"] and
            plan["copyRangeCount"] == len(measured["rows"]) and
            plan["copyByteCount"] == sum(x["destinationRange"][1]-x["destinationRange"][0] for x in measured["rows"]),
            "Restoration plan differs from current native decode")
        contract.require(restoration.get("ranges") == plan["copyRangeCount"] and
            restoration.get("copiedBytes") == plan["copyByteCount"], "Restoration byte accounting differs")
        with np.load(inputs.pin(documents["preparation"]["numericExpectedArrays"]), allow_pickle=False) as expected:
            selected = {key.removeprefix(root+"|") for key in numeric if key.startswith(root+"|")}
            contract.require(set(expected.files) == selected and len(selected) == 32, "Exact family numeric closure required")
            for key in selected:
                actual, wanted = expected[key], numeric[root+"|"+key]
                contract.require(actual.dtype == wanted.dtype and actual.shape == wanted.shape and
                    actual.tobytes() == wanted.tobytes(), "Authored cross-family numeric values")
        reports[root] = measured
        for name, pin in entry["resources"].items():
            contract.require(name not in resources, "Duplicate animation resource ownership")
            resources[name], paths[name] = pin["sha256"], str(inputs.pin(pin))
    expected_names = {name for root in ROOTS for name in (root+".mdl", "srn_fa_"+root[2:]+".mdl")}
    contract.require(set(resources) == set(paths) == expected_names and len(resources) == 24 and
        human_result["compilerClientSha256"] == COMPILER_SHA, "Complete compatible 24-resource inventory required")
    frozen = inputs.finish()
    if declared_inputs is not None:
        require_declared_inputs(frozen, declared_inputs)
    return {"kind": "verified-shared-female-source-native-animation-overlay", "receipt": receipt_pin,
        "resourceHashes": resources, "resourcePaths": paths, "familyReports": reports,
        "compilerClientSha256": COMPILER_SHA, "frozenInputs": frozen,
        "isolatedRootParentTokensOnly": True, "stockStaticFramesPreserved": True,
        "continuousEngineBehaviorProven": False, "clientAccepted": False,
        "runtimeSelected": False, "productionAccepted": False}
