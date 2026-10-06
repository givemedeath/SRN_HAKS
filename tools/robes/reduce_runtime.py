"""Reduce a weighted outfit to a runtime face budget (Blender), keeping its weights.

The full-resolution weighted mesh stays the master for later baking. The
runtime copy is welded and collapse-decimated; bone weights, segment one-hot
labels and the outer-visibility mask ride along as vertex groups (interpolated
only between connected vertices), skin faces as a face attribute and UVs as
loop data. The configured segment bone masks and torso arm-share cap are then
re-applied, weights re-limited and validated. Writes weights.npz, loop-uv.npy
and runtime-arrays.npz (visible) in the transfer_weights layout; approves nothing.
"""
import argparse
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_math
from robe_common import FLAGS, fresh_directory, pin, read, require, utc, verify_pins, write_fresh
from robe_weights import limit_and_normalize, validate

ARM_COLUMNS = ("lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g", "lhand_g", "rhand_g")


def build(data, uv, visible):
    verts, tris, loops = data["verts"], data["tris"], data["loops"]
    mesh = bpy.data.meshes.new("runtime")
    mesh.from_pydata(verts.tolist(), [], tris.tolist())
    mesh.uv_layers.new(name="UVMap").data.foreach_set("uv", uv[loops].ravel())
    mesh.attributes.new("skin", "INT", "FACE").data.foreach_set("value", data["skinFaces"].astype(np.int32))
    obj = bpy.data.objects.new("runtime", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bones = data["bones"].tolist()
    channels = np.c_[data["weights"], np.eye(len(fit_math.SEGMENTS))[data["segmentLabels"]], visible.astype(float)]
    names = bones + ["seg_" + s for s in fit_math.SEGMENTS] + ["outer"]
    for name in names:
        obj.vertex_groups.new(name=name)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    layer = bm.verts.layers.deform.verify()
    for vert, row in zip(bm.verts, channels):
        for group in np.flatnonzero(row > 0):
            vert[layer][int(group)] = float(row[group])
    bm.to_mesh(mesh)
    bm.free()
    return obj, names


def weld(obj, distance):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    after = len(bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    return before - after


def decimate(obj, target):
    current = len(obj.data.polygons)
    if current <= target:
        return current
    modifier = obj.modifiers.new("runtime", "DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = target / current
    modifier.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="runtime")
    return len(obj.data.polygons)


def read_back(obj, names):
    mesh = obj.data
    require(all(len(p.vertices) == 3 for p in mesh.polygons), "Runtime mesh must be triangulated")
    verts = np.array([v.co[:] for v in mesh.vertices])
    tris = np.array([p.vertices[:] for p in mesh.polygons], dtype=np.int64)
    loops = np.array([[p.loop_start + k for k in range(3)] for p in mesh.polygons], dtype=np.int64)
    uv = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers.active.data.foreach_get("uv", uv)
    skin = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.attributes["skin"].data.foreach_get("value", skin)
    channels = np.zeros((len(verts), len(names)))
    for vert in mesh.vertices:
        for group in vert.groups:
            channels[vert.index, group.group] = group.weight
    return verts, tris, loops, uv.reshape(-1, 2), skin.astype(bool), channels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True, help="Full-resolution weights directory")
    parser.add_argument("--fit-arrays", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tolerances", type=Path, required=True)
    parser.add_argument("--target-faces", type=int, required=True)
    parser.add_argument("--weld-distance", type=float, default=1e-6)
    parser.add_argument("--space", choices=["bind", "generation"], default="bind",
                        help="generation: reduce and emit the outfit in its A-pose (for generation-rest robes)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    inputs = [pin(args.weights / "weights.npz"), pin(args.weights / "loop-uv.npy"), pin(args.fit_arrays),
              pin(args.config), pin(args.tolerances)]
    output = fresh_directory(args.output)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    data = np.load(args.weights / "weights.npz")
    uv = np.load(args.weights / "loop-uv.npy")
    fit_arrays = np.load(args.fit_arrays)
    visible = fit_arrays["visible"]
    if args.space == "generation":
        require("fittedGeneration" in fit_arrays.files, "Generation-space fit arrays required")
        data = dict(data, verts=fit_arrays["fittedGeneration"])
    require(len(visible) == len(data["verts"]), "Fit arrays do not match the weighted mesh")
    plan = read(args.config)["weights"]
    tolerances = read(args.tolerances)
    obj, names = build(data, uv, visible)
    merged = weld(obj, args.weld_distance)
    welded_faces = len(obj.data.polygons)
    final_faces = decimate(obj, args.target_faces)
    verts, tris, loops, loop_uv, skin, channels = read_back(obj, names)
    bones = data["bones"].tolist()
    count = len(bones)
    segments = channels[:, count:count + len(fit_math.SEGMENTS)].argmax(1)
    outer = channels[:, -1] > 0.5
    weights = channels[:, :count]
    masked = {}
    for name, allowed in plan.get("segmentBoneMasks", {}).items():
        members = segments == fit_math.SEGMENTS.index(name)
        blocked = [i for i, bone in enumerate(bones) if bone not in allowed]
        masked[name] = int((weights[np.ix_(members, blocked)] > 0).any(1).sum())
        weights[np.ix_(members, blocked)] = 0.0
    cap = plan.get("torsoArmShareCap")
    if cap is not None:
        rows = np.flatnonzero(segments == 0)
        columns = [bones.index(b) for b in ARM_COLUMNS]
        share = weights[np.ix_(rows, columns)].sum(1) / np.maximum(weights[rows].sum(1), 1e-12)
        weights[np.ix_(rows, columns)] *= np.where(share > cap, cap / np.maximum(share, 1e-12), 1.0)[:, None]
        masked["torsoArmShareCapped"] = int((share > cap).sum())
    require(np.all(weights.sum(1) > 0), "Runtime vertex lost every influence")
    limited = limit_and_normalize(weights, tolerances["maximumInfluences"], plan.get("prune", 0.01))
    report_weights = validate(limited, bones, bones, sum_tolerance=tolerances["tolerances"]["weightSum"],
                              max_influences=tolerances["maximumInfluences"], bone_limit=None)
    np.savez_compressed(output / "weights.npz", weights=limited, bones=data["bones"], tris=tris, loops=loops,
                        verts=verts, segmentLabels=segments, skinFaces=skin)
    np.save(output / "loop-uv.npy", loop_uv)
    np.savez_compressed(output / "runtime-arrays.npz", visible=outer)
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-runtime-reduction", "createdUtc": utc(), "inputs": inputs,
              "method": "weld, Blender collapse decimation (triangulated) carrying weights, segment one-hot, outer "
                        "mask and UVs; segment bone masks and torso arm-share cap re-applied; 4-influence limit",
              "masterPreserved": True, "space": args.space, "weldDistance": args.weld_distance, "verticesMerged": merged,
              "facesBefore": int(len(data["tris"])), "facesWelded": welded_faces, "facesAfter": final_faces,
              "targetFaces": args.target_faces, "vertices": int(len(verts)),
              "skinFaces": int(skin.sum()), "skinFacesBefore": int(data["skinFaces"].sum()),
              "segmentVertices": {s: int((segments == i).sum()) for i, s in enumerate(fit_math.SEGMENTS)},
              "maskedVertices": masked, "validation": report_weights,
              "files": [pin(output / n) for n in ("weights.npz", "loop-uv.npy", "runtime-arrays.npz")], **FLAGS}
    print(write_fresh(output / "reduction.json", report)["sha256"])


if __name__ == "__main__":
    main()
