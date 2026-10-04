"""Verify the published Human body and an optional rebuilt HAK against tested pins.

This verifies resource identity, not a new visual/client test. The normal HAK
builder may create different archive metadata while preserving every payload.
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


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(root, manifest, hak=None):
    root = root.resolve()
    selected = json.loads(manifest.read_text(encoding="utf-8"))
    require(selected["schemaVersion"] == 1, "Unsupported publication manifest")
    require(selected["kind"] == "published-validated-human-male-body", "Wrong manifest kind")
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
    actual_names = {path.name for path in bank.iterdir()}
    require(actual_names == set(expected), "Unexpected/stale body pack resources")
    require(len(expected) == selected["resourceCount"] == 72, "Incomplete body payload")
    require({name for name in expected if name.endswith(".mdl")} ==
            {"pmh0_" + part + "001.mdl" for part in HUMAN_PARTS}, "Body ownership changed")
    for field in ("sourceBodyReceipt", "clientEvidence"):
        require(sha(root / selected[field]) == selected[field + "Sha256"],
                "Published evidence changed: " + field)
    original = json.loads((root / selected["sourceBodyReceipt"]).read_text(encoding="utf-8"))
    require(original["hakSha256"] == selected["sourceBodyHakSha256"] and
            original["resourceHashes"] == expected, "Published assets differ from tested selection")
    result = {"pack": "srn_body", "models": 14, "resources": len(expected),
              "payloadBytes": sum(row["bytes"] for row in selected["resources"]),
              "sourceAssetsExactTestedPayload": True, "clientRerun": False}
    require(result["payloadBytes"] == selected["payloadBytes"], "Payload size differs")
    if hak:
        rows = archive(hak)
        require(all(kind in EXTENSION_BY_TYPE for _, kind, _ in rows),
                "Unexpected resource type in rebuilt HAK")
        packed = {name + EXTENSION_BY_TYPE[kind]: hashlib.sha256(data).hexdigest()
                  for name, kind, data in rows}
        require(packed == expected and len(rows) == 72, "Rebuilt HAK payload differs")
        result.update({"rebuiltHakSha256": sha(hak), "rebuiltPayloadExactTestedSelection": True})
    return result


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=root / "docs/phenotypes/human-male-assets.json")
    parser.add_argument("--hak", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(root, args.manifest, args.hak), indent=2))


if __name__ == "__main__":
    main()
