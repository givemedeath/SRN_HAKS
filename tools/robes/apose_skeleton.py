"""Experiment: give a built robe model an A-pose rest skeleton (its own bone frames), so no pose conversion ships.

Limb bones of the robe's own skeleton are rotated into the outfit's generation (A-)pose with the
rotation part of the fit's inverse proxy transforms (stock bone lengths kept, torso chain unchanged),
and the skin vertices are re-posed with their weights to match. If the client skins against the
robe's own rest frames the robe renders as before; if it uses the stock skeleton the limbs show the
A-pose offset. Writes <resref>.mdl (+ <resref>.plt) and apose.json; approves nothing.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

import fit_math
import mdl_ascii
from robe_common import FLAGS, pin, require, utc, verify_pins, write_fresh


def axis_angle(rotation):
    """Axis-angle (x, y, z, radians) of a proper rotation, as MDL orientation lines store it."""
    angle = float(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1)))
    if angle < 1e-9:
        return np.array([0.0, 0.0, 0.0, 0.0])
    require(np.pi - angle > 1e-6, "Half-turn rest rotations are not expected")
    axis = np.array([rotation[2, 1] - rotation[1, 2], rotation[0, 2] - rotation[2, 0], rotation[1, 0] - rotation[0, 1]])
    return np.r_[axis / np.linalg.norm(axis), angle]


def generation_rest(model, transforms):
    """Robe-local rest frames with limb bones rotated into the generation pose (FK keeps bone lengths)."""
    bind = mdl_ascii.bind_frames(model)
    rotate = {name: fit_math._split(np.linalg.inv(matrix))[0] for name, matrix in transforms.items()}
    world_rotation, frames, local = {}, {}, {}
    root = model.name.lower()
    for node in model.nodes:
        if node.kind != "dummy" or node.key == root:
            continue
        world_rotation[node.key] = rotate[fit_math.BONE_PROXY.get(node.key, "torso")] @ bind[node.key][:3, :3]
        parent = node.parent.lower()
        if parent == root or parent not in frames:
            frames[node.key] = bind[node.key].copy()
            world_rotation[node.key] = bind[node.key][:3, :3]
            local[node.key] = None
            continue
        rotation = world_rotation[parent].T @ world_rotation[node.key]
        matrix = np.eye(4)
        matrix[:3, :3], matrix[:3, 3] = rotation, node.position
        frames[node.key] = frames[parent] @ matrix
        local[node.key] = rotation
    return bind, frames, local


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="Intended robe model from build_robe_model")
    parser.add_argument("--fit-arrays", type=Path, required=True)
    parser.add_argument("--resref", required=True)
    parser.add_argument("--node-prefix", nargs=2, metavar=("OLD", "NEW"), required=True)
    parser.add_argument("--skin-plt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [pin(args.model), pin(args.fit_arrays)] + ([pin(args.skin_plt)] if args.skin_plt else [])
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh output directory required")
    output.mkdir(parents=True)
    arrays = np.load(args.fit_arrays)
    require("proxyTransforms" in arrays.files, "Generation-space fit arrays required")
    transforms = dict(zip(fit_math.PROXY, arrays["proxyTransforms"]))
    model = mdl_ascii.read(args.model)
    old = model.name
    bind, frames, local = generation_rest(model, transforms)
    for node in model.nodes:
        if node.key in local and local[node.key] is not None:
            node.orientation = axis_angle(local[node.key])
    deviation = 0.0
    for node in model.nodes:
        if node.kind != "skin":
            continue
        weights, bones = mdl_ascii.skin_matrix(node)
        verts = np.asarray(node.arrays["verts"], float)
        world = (bind[node.key] @ np.c_[verts, np.ones(len(verts))].T).T
        posed = np.zeros((len(verts), 3))
        for column, bone in enumerate(bones):
            matrix = frames[bone.lower()] @ np.linalg.inv(bind[bone.lower()])
            posed += weights[:, column, None] * (world @ matrix.T)[:, :3]
        back = np.zeros_like(posed)
        for column, bone in enumerate(bones):
            matrix = bind[bone.lower()] @ np.linalg.inv(frames[bone.lower()])
            back += weights[:, column, None] * (np.c_[posed, np.ones(len(posed))] @ matrix.T)[:, :3]
        deviation = max(deviation, float(np.linalg.norm(back - world[:, :3], axis=1).max()))
        node.arrays["verts"] = (np.linalg.inv(bind[node.key]) @ np.c_[posed, np.ones(len(posed))].T).T[:, :3]
    check = mdl_ascii.bind_frames(model)
    require(all(np.allclose(check[k], frames[k], atol=1e-6) for k in frames), "Rest frames did not round-trip")
    model.name = args.resref
    for node in model.nodes:
        if node.name.lower() == old.lower():
            node.name = args.resref
        elif node.name.startswith(args.node_prefix[0]):
            node.name = args.node_prefix[1] + node.name[len(args.node_prefix[0]):]
        if node.parent.lower() == old.lower():
            node.parent = args.resref
        node.properties = [(k, args.resref if k == "bitmap" and v.lower() == old.lower() else v)
                           for k, v in node.properties]
    path = output / (args.resref + ".mdl")
    mdl_ascii.write(path, model)
    if args.skin_plt:
        shutil.copyfile(args.skin_plt, output / (args.resref + ".plt"))
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-generation-rest-experiment", "createdUtc": utc(), "inputs": inputs,
              "resref": args.resref, "source": old,
              "restRotationDegrees": {k: round(float(np.degrees(axis_angle(frames[k][:3, :3] @ bind[k][:3, :3].T)[3])), 2)
                                      for k in frames},
              "lbsRoundTripMaximumDeviation": deviation,
              "note": "Skin re-posed with linear blending; joint vertices deviate when posed back (lbsRoundTripMaximumDeviation).",
              "file": pin(path), "bindFramesChanged": True, "stockRigChanged": False, **FLAGS}
    print(write_fresh(output / "apose.json", report)["sha256"])


if __name__ == "__main__":
    main()
