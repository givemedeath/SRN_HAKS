"""Validate the purpose-built production contract without external packages.

Implements only the JSON Schema keywords used by the local contract and rejects
unsupported assertion keywords. This is a configuration/ledger validator, not a
production build runner or proof that assets passed geometry/client gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal(first, second):
    if isinstance(first, bool) or isinstance(second, bool):
        return type(first) is type(second) and first == second
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return first == second
    if type(first) is not type(second):
        return False
    if isinstance(first, list):
        return len(first) == len(second) and all(equal(a, b) for a, b in zip(first, second))
    if isinstance(first, dict):
        return first.keys() == second.keys() and all(equal(first[key], second[key]) for key in first)
    return first == second


def validate_schema(value, schema, root_schema, location="$instance"):
    known = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum",
             "required", "properties", "additionalProperties", "propertyNames", "items", "minItems", "maxItems",
             "uniqueItems", "contains", "minProperties", "minLength", "pattern", "minimum", "maximum",
             "exclusiveMinimum", "allOf", "oneOf", "if", "then"}
    unknown = set(schema) - known
    if unknown:
        raise ValueError("Unsupported contract keywords: " + str(sorted(unknown)))
    if "$ref" in schema:
        pointer = schema["$ref"]
        if not pointer.startswith("#/"):
            raise ValueError("Only local schema references are supported")
        referenced = root_schema
        for key in pointer[2:].split("/"):
            referenced = referenced[key.replace("~1", "/").replace("~0", "~")]
        validate_schema(value, referenced, root_schema, location)
    types = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
             "string": lambda x: isinstance(x, str), "null": lambda x: x is None,
             "boolean": lambda x: isinstance(x, bool),
             "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
             "integer": lambda x: isinstance(x, int) and not isinstance(x, bool)}
    if "type" in schema:
        wanted = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(types[name](value) for name in wanted):
            raise ValueError(location + ": wrong type")
    if "const" in schema and not equal(value, schema["const"]):
        raise ValueError(location + ": wrong constant")
    if "enum" in schema and not any(equal(value, option) for option in schema["enum"]):
        raise ValueError(location + ": not an allowed value")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            raise ValueError(location + ": missing required keys")
        if len(value) < schema.get("minProperties", 0):
            raise ValueError(location + ": too few properties")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if "propertyNames" in schema:
                validate_schema(key, schema["propertyNames"], root_schema, location + ".<key>")
            if key in properties:
                validate_schema(item, properties[key], root_schema, location + "." + key)
            elif schema.get("additionalProperties", True) is False:
                raise ValueError(location + ": unexpected property " + key)
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], root_schema, location + "." + key)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise ValueError(location + ": wrong array length")
        if schema.get("uniqueItems") and any(equal(item, prior) for index, item in enumerate(value) for prior in value[:index]):
            raise ValueError(location + ": duplicate array values")
        for index, item in enumerate(value):
            if "items" in schema:
                validate_schema(item, schema["items"], root_schema, location + "[" + str(index) + "]")
        if "contains" in schema:
            matches = 0
            for item in value:
                try:
                    validate_schema(item, schema["contains"], root_schema, location)
                    matches += 1
                except ValueError:
                    pass
            if matches == 0:
                raise ValueError(location + ": required array member missing")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and re.search(schema["pattern"], value) is None):
            raise ValueError(location + ": invalid string")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if ("minimum" in schema and value < schema["minimum"]) or ("maximum" in schema and value > schema["maximum"]):
            raise ValueError(location + ": numeric range failed")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValueError(location + ": exclusive minimum failed")
    for branch in schema.get("allOf", []):
        validate_schema(value, branch, root_schema, location)
    if "oneOf" in schema:
        matches = 0
        for branch in schema["oneOf"]:
            try:
                validate_schema(value, branch, root_schema, location)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            raise ValueError(location + ": oneOf needs exactly one matching branch")
    if "if" in schema:
        try:
            validate_schema(value, schema["if"], root_schema, location)
        except ValueError:
            pass
        else:
            validate_schema(value, schema.get("then", {}), root_schema, location)


def validate(config, schema, verify_files=False):
    validate_schema(config, schema, schema)
    target = config["target"]
    height = target["height"]
    factor = height["targetReferenceMetres"] / height["referenceHumanMaleMetres"]
    if abs(factor - height["scaleRelativeToStockHuman"]) > 1e-10:
        raise ValueError("Height ratio does not match the measured stock-Human basis")
    if abs(height["stockHumanMaleMetres"] * factor - height["targetAssembledMetres"]) > 1e-8:
        raise ValueError("Target assembled height does not match its ratio")
    if target["phenotype"] != {"fit": 0, "large": 2}[target["bodyType"]]:
        raise ValueError("Body type/phenotype mapping must use the project's fit0/large2 contract")
    if target["race"] == "troll" and (target["raceSlot"] != 2 or target["modelPrefix"][2] != "g"):
        raise ValueError("Troll must use the replaced Gnome slot/family")
    accepted = {name for name, entry in config["parts"].items() if entry["status"] == "accepted"}
    if accepted != set(config["acceptedReplacements"]):
        raise ValueError("Accepted ledger entries and cumulative replacement map disagree")
    for name in accepted:
        entry = config["parts"][name]
        replacement = config["acceptedReplacements"][name]
        if not equal(entry["promotionReceipt"], replacement["promotionReceipt"]):
            raise ValueError("Promotion receipts disagree for " + name)
    if config["fitting"]["currentPhase"] == "uniform-scale-diagnostic" and config["fitting"]["laterLocalizedCleanup"]["state"] == "complete":
        raise ValueError("Completed mesh cleanup cannot be represented as an unchanged scaling-only phase")
    if config["fitting"]["laterLocalizedCleanup"]["state"] in ("configured", "complete", "authorized-waist-cap-design") and config["fitting"]["similarityFitting"]["state"] not in ("exhausted", "adequate-user-selected"):
        raise ValueError("Exhaust uniform scale, proper rotation and placement before mesh changes")
    if config["fitting"]["laterLocalizedCleanup"]["state"] == "authorized-waist-cap-design" and config["fitting"]["laterLocalizedCleanup"]["permittedRegions"] != ["bottom-back-waist"]:
        raise ValueError("Current waist-cap phase permits only the bottom-back waist region")
    if config["equipment"]["mode"] == "stock-identity" and config["equipment"]["profiles"]:
        raise ValueError("Stock identity equipment must not carry resize profiles")
    if set(config["equipment"]["groups"]) != set(config["equipment"]["groupPartAssociations"]):
        raise ValueError("Every equipment group must have an explicit canonical-part association")
    if config["currentDiagnostic"]["selectionBasis"] == "user-selected-diagnostic-baseline" and config["currentDiagnostic"]["selectionReceipt"] is None:
        raise ValueError("User-selected diagnostic baseline requires its frozen selection receipt")
    checked = {}
    if verify_files:
        def check(path, expected):
            actual = digest(Path(path))
            if actual != expected:
                raise ValueError("Frozen file differs: " + path)
            checked[path] = actual

        baseline = target["baseline"]
        check(baseline["receipt"], baseline["receiptSha256"])
        for name, expected in baseline["frozenModels"].items():
            check(str(Path(baseline["asciiDirectory"]) / name), expected)
        for entry in config["parts"].values():
            for receipt in [entry["activeSource"], entry["promotionReceipt"]] + [gate["receipt"] for gate in entry["gates"]]:
                if receipt is not None:
                    check(receipt["path"], receipt["sha256"])
        for replacement in config["acceptedReplacements"].values():
            check(replacement["localGlb"], replacement["glbSha256"])
            check(replacement["nativeResource"], replacement["nativeSha256"])
        for profile in config["equipment"]["profiles"]:
            for key in ("profileReceipt", "acceptedAssemblyReceipt"):
                check(profile[key]["path"], profile[key]["sha256"])
        connectors = config["fitting"]["connectors"]
        if connectors["measurementReceipt"] is not None:
            check(connectors["measurementReceipt"]["path"], connectors["measurementReceipt"]["sha256"])
        for measurement in connectors["measurements"]:
            for key in ("capProfileReceipt", "targetOverlapReceipt"):
                check(measurement[key]["path"], measurement[key]["sha256"])
        for receipt in config["fitting"]["similarityFitting"]["trialReceipts"] + [config["currentDiagnostic"]["comparisonAudit"]]:
            check(receipt["path"], receipt["sha256"])
        diagnostic = config["currentDiagnostic"]
        check(diagnostic["stockReplacementMap"], diagnostic["stockReplacementMapSha256"])
        for key in ("selectedPlacementReceipt", "exportProofReceipt", "placedPartReceipt"):
            check(diagnostic[key]["path"], diagnostic[key]["sha256"])
        if diagnostic["selectionReceipt"] is not None:
            check(diagnostic["selectionReceipt"]["path"], diagnostic["selectionReceipt"]["sha256"])
    return {"configurationValid": True, "checkedFileHashes": checked, "acceptedParts": sorted(accepted),
            "geometryOrClientAcceptanceEstablished": False, "productionRunnerExecuted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("configurations") / "purpose-built-production.schema.json")
    parser.add_argument("--verify-files", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    schema = json.loads(args.schema.read_text())
    receipt = validate(config, schema, args.verify_files)
    receipt.update(configPath=str(args.config.resolve()), configSha256=digest(args.config),
                   schemaSha256=digest(args.schema), validatorSha256=digest(Path(__file__)))
    if args.output:
        if args.output.exists():
            raise RuntimeError("Use a fresh configuration validation receipt")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == "__main__":
    main()
