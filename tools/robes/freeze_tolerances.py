"""Freeze export tolerances from measured stock-control round trips.

Each tolerance is max(2 x measured control loss, writer representation bound).
Frozen once before candidate evaluation; later losses are investigated, never
absorbed by editing this file.
"""
import argparse
from pathlib import Path

from robe_common import FLAGS, pin, read, require, utc, write_fresh

# Writer precision observed in the Neverblender 4.1.0 export (5-decimal positions,
# 4-decimal UVs, 3-decimal weights renormalized after dropping weights below 0.001).
BOUNDS = {"bindTranslation": 3e-5, "bindRotation": 1e-6, "position": 2e-5, "uv": 1e-4,
          "weight": 1.5e-3, "weightSum": 2e-3, "deformation": 1e-3, "smoothingEdges": 0}


def measure(reports):
    worst = {key: 0.0 for key in BOUNDS}
    for report in reports:
        require(report["kind"] == "srn-robe-model-comparison", "Control comparison required")
        require(not (report["missingNodes"] or report["kindChanges"] or report["parentChanges"]),
                "Control lost structure; investigate before freezing tolerances")
        worst["bindTranslation"] = max(worst["bindTranslation"], report["maximumBindTranslationError"])
        worst["bindRotation"] = max(worst["bindRotation"], report["maximumBindRotationError"])
        for mesh in report["meshes"]:
            for field, key in (("maximumPositionError", "position"), ("maximumUvError", "uv"),
                               ("maximumWeightError", "weight"), ("rightMaximumSumDeviation", "weightSum"),
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
    reports = [read(path) for path in args.comparison]
    worst = measure(reports)
    tolerances = {key: max(2 * worst[key], BOUNDS[key]) for key in BOUNDS}
    tolerances["smoothingEdges"] = 0
    report = {"schemaVersion": 1, "kind": "srn-robe-control-tolerances", "createdUtc": utc(),
              "controls": [pin(path) for path in args.comparison], "measuredControlLoss": worst,
              "representationBounds": BOUNDS, "rule": "max(2 x measured control loss, representation bound)",
              "tolerances": tolerances, "maximumInfluences": 4, "boneLimitPerSkinNode": args.bone_limit,
              "knownInformationalDifferences": ["per-face surface-material column written as 0 (render meshes ignore it)",
                                                "model classification case normalized to CHARACTER",
                                                "UV coordinates merged (tvert count may fall)"],
              "frozen": True, **FLAGS}
    print(write_fresh(args.output, report)["sha256"])


if __name__ == "__main__":
    main()
