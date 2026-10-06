"""Inventory extracted stock robes and select per-garment-class weight donors.

Records skin nodes, bone sets, influences, weight sums, bind hierarchy,
supermodel chains, local animations, material dependencies and parts_robe HIDE
flags, then classifies hem coverage against the stock body. Selection is a
measured proposal, not visual approval.
"""
import argparse
from pathlib import Path

import numpy as np

import mdl_ascii
from robe_common import FLAGS, pin, read, require, utc, verify_pins, write_fresh
from robe_weights import validate

HIDE = ("HIDEFOOTR", "HIDEFOOTL", "HIDESHINR", "HIDESHINL", "HIDELEGR", "HIDELEGL", "HIDEPELVIS", "HIDECHEST",
        "HIDEBELT", "HIDENECK", "HIDEFORER", "HIDEFOREL", "HIDEBICEPR", "HIDEBICEPL", "HIDESHOR", "HIDESHOL",
        "HIDEHANDR", "HIDEHANDL", "HIDEHEAD")
LEFT_LEG, RIGHT_LEG = {"lthigh_g", "lshin_g", "lfoot_g"}, {"rthigh_g", "rshin_g", "rfoot_g"}
ARMS = {"lbicep_g", "lforearm_g", "rbicep_g", "rforearm_g", "lhand_g", "rhand_g"}


def read_2da(path):
    lines = [line for line in Path(path).read_text(encoding="cp1252").splitlines() if line.strip()]
    require(lines[0].startswith("2DA"), "2DA header required")
    columns = lines[1].split()
    rows = {}
    for line in lines[2:]:
        values = line.split()
        rows[int(values[0])] = dict(zip(columns, values[1:]))
    return columns, rows


def landmarks(body_frames):
    def z(name):
        return float(body_frames[name][2, 3])
    return {"pelvis": z("pelvis_g"), "knee": (z("lshin_g") + z("rshin_g")) / 2,
            "ankle": (z("lfoot_g") + z("rfoot_g")) / 2, "neck": z("neck_g")}


def classify(hem, marks):
    if hem <= marks["ankle"] + 0.08:
        return "floor"
    if hem <= marks["knee"] + 0.05:
        return "knee-to-ankle"
    if hem <= marks["pelvis"] - 0.05:
        return "thigh"
    return "waist"


def skin_report(model, node, frames, marks):
    weights, bones = mdl_ascii.skin_matrix(node)
    report = validate(weights, bones, model.names(), sum_tolerance=0.002)
    verts = np.asarray(node.arrays["verts"], dtype=float)
    world = (frames[node.key] @ np.c_[verts, np.ones(len(verts))].T).T[:, :3]
    left = weights[:, [i for i, b in enumerate(bones) if b in LEFT_LEG]].sum(axis=1) if set(bones) & LEFT_LEG else 0
    right = weights[:, [i for i, b in enumerate(bones) if b in RIGHT_LEG]].sum(axis=1) if set(bones) & RIGHT_LEG else 0
    bridging = int(np.sum((np.asarray(left) > 0.05) & (np.asarray(right) > 0.05))) if np.ndim(left) else 0
    return {"node": node.name, "parent": node.parent, "vertices": len(verts), "faces": len(node.arrays.get("faces", [])),
            "bitmap": node.get("bitmap"), "weights": report, "influenceHistogram":
                {str(k): int(v) for k, v in zip(*np.unique((weights > 0).sum(axis=1), return_counts=True))},
            "worldBounds": [world.min(axis=0).round(5).tolist(), world.max(axis=0).round(5).tolist()],
            "hemZ": float(world[:, 2].min()), "coverage": classify(float(world[:, 2].min()), marks),
            "verticesBridgingBothLegs": bridging, "usesArmBones": bool(set(bones) & ARMS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    extraction = read(args.extraction)
    require(extraction["kind"] == "srn-robe-stock-extraction", "Stock extraction receipt required")
    ascii_dir, raw_dir = Path(extraction["asciiDirectory"]), Path(extraction["rawDirectory"])
    consumed = [pin(args.extraction)] + [pin(ascii_dir / name) for name in extraction["resources"]
                                         if name.endswith(".mdl")] + [pin(raw_dir / "parts_robe.2da")]
    verify_pins(consumed)
    body = mdl_ascii.read(ascii_dir / (extraction["prefix"] + ".mdl"))
    body_frames = mdl_ascii.bind_frames(body)
    marks = landmarks(body_frames)
    _, table = read_2da(raw_dir / "parts_robe.2da")
    robes = {}
    for name in extraction["selectedRobeModels"]:
        stem = name.removesuffix(".mdl")
        model = mdl_ascii.read(ascii_dir / name)
        frames = mdl_ascii.bind_frames(model)
        row = table.get(int(stem[-3:]), {})
        meshes = [n for n in model.nodes if n.kind in mdl_ascii.MESHES and n.get("render", "1") != "0"]
        skins = [skin_report(model, node, frames, marks) for node in model.nodes if node.kind == "skin"]
        shared = sorted(set(frames) & set(body_frames))
        offsets = [float(np.abs(frames[k][:3, 3] - body_frames[k][:3, 3]).max()) for k in shared]
        robes[stem] = {
            "supermodelChain": extraction["robes"][stem]["chain"], "localAnimations": len(model.animations),
            "nodes": [{"name": n.name, "kind": n.kind, "parent": n.parent, "render": n.get("render", "1")}
                      for n in model.nodes],
            "renderedMeshes": [{"node": n.name, "kind": n.kind, "bitmap": n.get("bitmap")} for n in meshes],
            "skins": skins, "dependencies": extraction["robes"][stem]["dependencies"],
            "hide": {column: row.get(column) for column in HIDE},
            "bindOffsetFromBody": {"sharedNodes": shared, "maximumTranslation": max(offsets) if offsets else None},
            "coverage": classify(min(s["hemZ"] for s in skins), marks) if skins else None,
            "rigid": not skins}
    skinned = {k: v for k, v in robes.items() if v["skins"]}
    def pick(predicate, key):
        rows = [(k, v) for k, v in skinned.items() if predicate(v)]
        return min(rows, key=key)[0] if rows else None
    selection = {
        "fittedUpperAndArms": pick(lambda v: any(s["usesArmBones"] for s in v["skins"])
                                   and v["supermodelChain"][1:2] == [extraction["prefix"]],
                                   lambda kv: -max(s["weights"]["boneCount"] for s in kv[1]["skins"])),
        "fittedLegs": "body-part cage (rigid pmh0 *001 parts, blended across joints)",
        "longSkirtSameRig": pick(lambda v: v["supermodelChain"][1:2] == [extraction["prefix"]]
                                 and v["coverage"] in ("floor", "knee-to-ankle"),
                                 lambda kv: min(s["hemZ"] for s in kv[1]["skins"])),
        "longSkirtCoatBones": pick(lambda v: "a_ba_coat" in v["supermodelChain"], lambda kv: kv[0]),
    }
    verify_pins(consumed)  # the loop above read these files
    report = {"schemaVersion": 1, "kind": "srn-robe-stock-inventory", "createdUtc": utc(),
              "prefix": extraction["prefix"], "inputs": consumed, "bodyLandmarks": marks,
              "bodyChain": extraction["bodyChain"], "robes": robes, "donorSelection": selection,
              "selectionBasis": "measured coverage, bone sets and supermodel; reviewed in the stock control",
              "parts_robeRows": {str(k): v for k, v in sorted(table.items())}, **FLAGS}
    print(write_fresh(args.output, report)["sha256"])


if __name__ == "__main__":
    main()
