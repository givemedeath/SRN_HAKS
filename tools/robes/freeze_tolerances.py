"""Freeze export tolerances from measured stock-control round trips.

Each tolerance is max(2 x measured control loss, writer representation bound).
Frozen once before candidate evaluation; later losses are investigated, never
absorbed by editing this file.
"""
import argparse
from pathlib import Path

from robe_common import FLAGS, pin, read, require, utc, verify_pins, write_fresh

# Writer precision observed in the Neverblender 4.1.0 export (5-decimal positions,
# 4-decimal UVs, 3-decimal weights renormalized after dropping weights below 0.001).
BOUNDS = {"bindTranslation": 3e-5, "bindRotation": 1e-6, "position": 2e-5, "uv": 1e-4,
          "weight": 1.5e-3, "weightSum": 2e-3, "deformation": 1e-3, "smoothingEdges": 0}


def invariant_changes(report):
    """Control differences no numeric tolerance can absorb: header, UV presence, render state, bitmap."""
    header, changes = report.get("header", {}), []
    for key in ("supermodel", "classification"):
        pair = header.get(key)
        if pair and str(pair[0]).lower() != str(pair[1]).lower():
            changes.append(key)
    scale = header.get("animationScale")
    if scale and abs(float(scale[0]) - float(scale[1])) > 1e-6:
        changes.append("animation scale")
    content = header.get("animationContent")
    if content and content[0] != content[1]:
        changes.append("local animations")
    for mesh in report["meshes"]:
        for key in ("uvPresent", "render"):
            if len(set(map(str, mesh.get(key, [])))) > 1:
                changes.append(f"{mesh.get('node')}: {key}")
        if "bitmap" in mesh and str(mesh["bitmap"][0]).lower() != str(mesh["bitmap"][1]).lower():
            changes.append(f"{mesh.get('node')}: bitmap")
    return changes


def measure(reports):
    worst = {key: 0.0 for key in BOUNDS}
    for report in reports:
        require(report["kind"] == "srn-robe-model-comparison", "Control comparison required")
        require(not (report["missingNodes"] or report["addedNodes"] or report["kindChanges"] or report["parentChanges"]),
                "Control structure changed; investigate before freezing tolerances")
        require(all(m.get("faces", [0, 0])[0] == m.get("faces", [0, 0])[1] for m in report["meshes"]),
                "Control face count changed; investigate before freezing tolerances")
        pairing = [f"{m.get('node')}: {key}" for m in report["meshes"]
                   for key in ("maximumFaceCentroidError", "maximumReferenceFaceGap", "maximumCornerPositionError")
                   if m.get(key, 0.0) > BOUNDS["position"]]
        require(not pairing, "Control face pairing differs beyond the representation bound: " + ", ".join(pairing))
        changes = invariant_changes(report)
        require(not changes, "Control changed untoleranced properties; investigate before freezing: " + ", ".join(changes))
        worst["bindTranslation"] = max(worst["bindTranslation"], report["maximumBindTranslationError"])
        worst["bindRotation"] = max(worst["bindRotation"], report["maximumBindRotationError"])
        for mesh in report["meshes"]:
            for field, key in (("maximumPositionError", "position"), ("maximumUvError", "uv"),
                               ("maximumWeightError", "weight"), ("maximumReverseWeightError", "weight"),
                               ("rightMaximumSumDeviation", "weightSum"),
                               ("smoothingEdgeMismatches", "smoothingEdges")):
                if field in mesh:
                    worst[key] = max(worst[key], mesh[field])
            if "sampledDeformation" in mesh:
                worst["deformation"] = max(worst["deformation"], mesh["sampledDeformation"]["maximumDisplacementError"])
    return worst


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, action="append", required=True)
    parser.add_argument("--bone-limit", type=int, required=True, help="Per-skin-node bone limit proven so far")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    controls = [pin(path) for path in args.comparison]  # hashed before reading, re-verified after measuring
    reports = [read(path) for path in args.comparison]
    worst = measure(reports)
    verify_pins(controls)
    tolerances = {key: max(2 * worst[key], BOUNDS[key]) for key in BOUNDS}
    tolerances["smoothingEdges"] = 0
    report = {"schemaVersion": 1, "kind": "srn-robe-control-tolerances", "createdUtc": utc(),
              "controls": controls, "measuredControlLoss": worst,
              "representationBounds": BOUNDS, "rule": "max(2 x measured control loss, representation bound)",
              "tolerances": tolerances, "maximumInfluences": 4, "boneLimitPerSkinNode": args.bone_limit,
              "knownInformationalDifferences": ["per-face surface-material column written as 0 (render meshes ignore it)",
                                                "model classification case normalized to CHARACTER",
                                                "UV coordinates merged (tvert count may fall)"],
              "frozen": True, **FLAGS}
    print(write_fresh(args.output, report)["sha256"])


if __name__ == "__main__":
    main()
