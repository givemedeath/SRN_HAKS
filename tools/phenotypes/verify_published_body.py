"""Verify the published Human body and an optional rebuilt HAK against tested pins.

This verifies resource identity, not a new visual/client test. The normal HAK
builder may create different archive metadata while preserving every payload.

Two manifest contracts are supported. The historical male v1 manifest
(`published-validated-human-male-body`, schema 1) keeps its exact 72-resource
layout and whole-pack ownership. Target manifests (`published-validated-target-body`,
schema 2) declare their stock-exact prefix and the single-PLT-per-part layout; their
closure is derived from the fourteen body parts (5 resources each) and ownership is
scoped to that prefix, so female and male bodies can share the pack.
"""
import argparse
import hashlib
import json
from pathlib import Path

from audit_pelvis_package import archive, require

EXTENSION_BY_TYPE = {3: ".tga", 6: ".plt", 2002: ".mdl", 2072: ".mtr"}
HUMAN_PARTS = {
    "chest", "pelvis", "bicepl", "bicepr", "forel", "forer", "handl", "handr",
    "legl", "legr", "shinl", "shinr", "footl", "footr",
}
LEGACY_KIND = "published-validated-human-male-body"
TARGET_KIND = "published-validated-target-body"
SINGLE_PLT_LAYOUT = "single-plt-per-part-v1"
SINGLE_PLT_SUFFIXES = (".mdl", ".mtr", ".plt", "n.tga", "r.tga")
STOCK_EXACT_PREFIXES = {"pmh0": "male", "pfh0": "female"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def manifest_contract(selected):
    """Return (prefix, expected resource names or None for legacy count, legacy?)."""
    if selected.get("kind") == LEGACY_KIND:
        require(selected["schemaVersion"] == 1, "Unsupported publication manifest")
        return "pmh0", None, True
    require(selected.get("kind") == TARGET_KIND and selected.get("schemaVersion") == 2, "Wrong manifest kind")
    prefix = selected.get("prefix")
    require(prefix in STOCK_EXACT_PREFIXES and selected.get("gender") == STOCK_EXACT_PREFIXES[prefix],
            "Stock-exact Human prefix/gender required")
    require(selected.get("materialLayout") == SINGLE_PLT_LAYOUT, "Single-PLT-per-part layout required")
    expected = {prefix + "_" + part + "001" + suffix for part in HUMAN_PARTS for suffix in SINGLE_PLT_SUFFIXES}
    return prefix, expected, False


def verify(root, manifest, hak=None):
    root = root.resolve()
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    prefix, contract_names, legacy = manifest_contract(selected)
    require(selected["pack"] == "srn_body", "Unexpected body pack")
    bank = root / "srn_body"
    expected = {}
    for row in selected["resources"]:
        path = (root / row["path"]).resolve()
        require(path.parent == bank.resolve(), "Resource escaped the flat body pack")
        require(path.is_file() and path.name not in expected, "Missing or duplicate body resource")
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"],
                "Published body bytes differ: " + path.name)
        require(path.stat().st_size <= 15 * 1024 ** 2, "Undeclared body size exception")
        expected[path.name] = row["sha256"]
    owned = (lambda name: True) if legacy else (lambda name: name.startswith(prefix + "_"))
    actual_names = {path.name for path in bank.iterdir() if owned(path.name)}
    require(actual_names == set(expected), "Unexpected/stale body pack resources")
    if legacy:
        require(len(expected) == selected["resourceCount"] == 72, "Incomplete body payload")
    else:
        require(set(expected) == contract_names and len(expected) == selected["resourceCount"] == len(contract_names),
                "Body payload differs from the derived single-PLT closure")
    require({name for name in expected if name.endswith(".mdl")} ==
            {prefix + "_" + part + "001.mdl" for part in HUMAN_PARTS}, "Body ownership changed")
    for field in ("sourceBodyReceipt", "clientEvidence"):
        require(sha(root / selected[field]) == selected[field + "Sha256"],
                "Published evidence changed: " + field)
    original = json.loads((root / selected["sourceBodyReceipt"]).read_text(encoding="utf-8"))
    require(original["hakSha256"] == selected["sourceBodyHakSha256"] and
            original["resourceHashes"] == expected, "Published assets differ from tested selection")
    result = {"pack": "srn_body", "prefix": prefix, "models": 14, "resources": len(expected),
              "materialLayout": "legacy-human-male-v1" if legacy else SINGLE_PLT_LAYOUT,
              "payloadBytes": sum(row["bytes"] for row in selected["resources"]),
              "sourceAssetsExactTestedPayload": True, "clientRerun": False}
    require(result["payloadBytes"] == selected["payloadBytes"], "Payload size differs")
    if hak:
        rows = archive(hak)
        require(all(kind in EXTENSION_BY_TYPE for _, kind, _ in rows),
                "Unexpected resource type in rebuilt HAK")
        packed = {name + EXTENSION_BY_TYPE[kind]: hashlib.sha256(data).hexdigest()
                  for name, kind, data in rows if owned(name + EXTENSION_BY_TYPE[kind])}
        require(packed == expected and (not legacy or len(rows) == 72), "Rebuilt HAK payload differs")
        result.update({"rebuiltHakSha256": sha(hak), "rebuiltPayloadExactTestedSelection": True})
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=root / "docs/phenotypes/human-male-v2-assets.json")
    parser.add_argument("--hak", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(root, args.manifest, args.hak), indent=2))


if __name__ == "__main__":
    main()
