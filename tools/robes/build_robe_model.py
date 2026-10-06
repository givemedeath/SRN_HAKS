"""Write the intended ASCII robe model: stock bind skeleton plus region skin nodes.

The skeleton is copied unchanged from the stock phenotype model (local bind
frames and parents); only nodes needed by the weights are included. Faces are
split into skin nodes by segment, with exposed-skin faces in their own nodes so
they can bind a skin-only PLT. The client applies a robe PLT only when it shares
the model's resref (as stock robes do), so skin nodes use bitmap <model> and
--skin-plt is copied in as <model>.plt. Writes <model>.mdl and model.json; approves nothing.
"""
import argparse
from pathlib import Path
import shutil

import numpy as np

import fit_math
import mdl_ascii
from robe_common import FLAGS, pin, read, require, utc, verify_pins, write_fresh

SEGMENT_NODES = ["torso", "arml", "armr", "legl", "legr"]


def skeleton_nodes(stock, bones):
    table = {node.key: node for node in stock.nodes}
    needed = set()
    for bone in bones:
        key = bone.lower()
        while key != "null" and key != stock.name.lower():
            require(key in table, "Bone missing from stock hierarchy: " + key)
            needed.add(key)
            key = table[key].parent.lower()
    return [node for node in stock.nodes if node.key in needed]


SEGMENT_START = {"ua": "shoulder", "fa": "elbow", "hand": "wrist", "th": "hip", "sh": "knee", "ft": "ankle"}


def generation_rest(stock, names, fit_report, transforms):
    """Robe rest frames at the outfit's own A-pose joints: each limb bone's stock bind frame taken back
    through the rigid part of its proxy transform (outfit joint -> stock joint). The client skins against
    these frames, so the A-pose mesh ships unconverted."""
    bind = mdl_ascii.bind_frames(stock)
    world = {}
    for key in names:
        proxy = fit_math.BONE_PROXY.get(key, "torso")
        frame = bind[key].copy()
        if proxy != "torso":
            rotation = fit_math._split(transforms[proxy])[0]
            segment, side = proxy.split("_")
            outfit = np.array(fit_report["outfitJoints"][SEGMENT_START[segment] + side])
            target = np.array(fit_report["stockTargets"][SEGMENT_START[segment] + side])
            frame[:3, :3] = rotation.T @ bind[key][:3, :3]
            frame[:3, 3] = rotation.T @ (bind[key][:3, 3] - target) + outfit
        world[key] = frame
    return world


def axis_angle(rotation):
    angle = float(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1)))
    if angle < 1e-9:
        return np.zeros(4)
    require(np.pi - angle > 1e-6, "Half-turn rest rotations are not expected")
    axis = np.array([rotation[2, 1] - rotation[1, 2], rotation[0, 2] - rotation[2, 0], rotation[1, 0] - rotation[0, 1]])
    return np.r_[axis / np.linalg.norm(axis), angle]


def node_for_faces(name, faces, verts, corner_uv, weights, bone_names, bitmap, decimals):
    used, local = np.unique(faces, return_inverse=True)
    local = local.reshape(-1, 3)
    uv_keys = np.round(corner_uv.reshape(-1, 2), 6)
    unique_uv, uv_index = np.unique(uv_keys, axis=0, return_inverse=True)
    uv_index = uv_index.reshape(-1, 3)
    node = mdl_ascii.Node("skin", name)
    node.parent = None
    for key, value in (("ambient", "1.0 1.0 1.0"), ("diffuse", "1.0 1.0 1.0"), ("specular", "0.0 0.0 0.0"),
                       ("shininess", "1"), ("bitmap", bitmap), ("render", "1"), ("shadow", "1"),
                       ("beaming", "0"), ("rotatetexture", "0"), ("transparencyhint", "0"), ("tilefade", "0")):
        node.properties.append((key, value))
    node.arrays["verts"] = verts[used]
    node.arrays["tverts"] = np.c_[unique_uv, np.zeros(len(unique_uv))]
    node.arrays["faces"] = np.c_[local, np.ones(len(local), int), uv_index, np.zeros(len(local), int)]
    rows = []
    for vertex in used:
        values = weights[vertex]
        order = np.argsort(-values, kind="stable")
        rows.append([(bone_names[i], round(float(values[i]), decimals)) for i in order if values[i] > 0])
    node.arrays["weights"] = rows
    return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True, help="Weights output directory")
    parser.add_argument("--stock-model", type=Path, required=True)
    parser.add_argument("--model", required=True, help="Robe model resref, e.g. pmh0_robe011")
    parser.add_argument("--prefix", required=True, help="Short node/texture prefix, e.g. ww11")
    parser.add_argument("--material-prefix", help="Bitmap/material prefix when sharing another candidate's textures")
    parser.add_argument("--tolerances", type=Path, required=True)
    parser.add_argument("--weight-decimals", type=int, default=6)
    parser.add_argument("--skin-plt", type=Path, help="Skin-only PLT, copied in as <model>.plt")
    parser.add_argument("--rest", choices=["bind", "generation"], default="bind",
                        help="generation: robe rest skeleton at the outfit's A-pose joints (weights dir must be A-pose)")
    parser.add_argument("--fit", type=Path, help="Fit output directory (required for --rest generation)")
    parser.add_argument("--merge-bone", action="append", default=[], metavar="FROM=TO",
                        help="Fold one bone's weights into another (repeatable). neck_g=torso_g keeps neck_g out of the "
                             "robe skeleton: a robe neck_g stops the client drawing the creature's neck part")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(len(args.model) <= 16 and len(args.prefix) <= 8, "Resref limits exceeded")
    inputs = [pin(args.weights / "weights.npz"), pin(args.weights / "loop-uv.npy"), pin(args.stock_model),
              pin(args.tolerances)]
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh model directory required")
    output.mkdir(parents=True)
    data = np.load(args.weights / "weights.npz")
    uv = np.load(args.weights / "loop-uv.npy")
    tolerances = read(args.tolerances)
    verts, tris, loops = data["verts"], data["tris"], data["loops"]
    weights, segments, skin_faces = data["weights"], data["segmentLabels"], data["skinFaces"]
    stock = mdl_ascii.read(args.stock_model)
    stock_names = {node.key: node.name for node in stock.nodes}
    keys = data["bones"].tolist()
    merged = []
    for rule in args.merge_bone:
        source, target = (part.strip().lower() for part in rule.split("="))
        require(source in keys and target in keys, "Unknown bone in --merge-bone " + rule)
        weights = weights.copy()
        weights[:, keys.index(target)] += weights[:, keys.index(source)]
        weights[:, keys.index(source)] = 0.0
        merged.append({"from": source, "to": target})
    bone_names = [stock_names[b] for b in data["bones"].tolist()]
    used_bones = [bone_names[i] for i in np.flatnonzero(weights.max(0) > 0)]
    model = mdl_ascii.Model(args.model)
    model.supermodel = stock.name
    model.classification = "character"
    root = mdl_ascii.Node("dummy", args.model)
    model.nodes.append(root)
    skeleton = skeleton_nodes(stock, used_bones)
    rest = None
    if args.rest == "generation":
        require(args.fit is not None, "--rest generation needs --fit")
        inputs += [pin(args.fit / "fit.json"), pin(args.fit / "fit-arrays.npz")]
        transforms = dict(zip(fit_math.PROXY, np.load(args.fit / "fit-arrays.npz")["proxyTransforms"]))
        rest = generation_rest(stock, [n.key for n in skeleton], read(args.fit / "fit.json"), transforms)
    for node in skeleton:
        copy = mdl_ascii.Node("dummy", node.name)
        copy.parent = args.model if node.parent.lower() == stock.name.lower() else node.parent
        copy.position, copy.orientation = node.position.copy(), node.orientation.copy()
        if rest is not None and node.parent.lower() in rest:
            local = np.linalg.inv(rest[node.parent.lower()]) @ rest[node.key]
            copy.position, copy.orientation = local[:3, 3], axis_angle(local[:3, :3])
        model.nodes.append(copy)
    if rest is not None:
        check = mdl_ascii.bind_frames(model)
        require(all(np.allclose(check[k], rest[k], atol=1e-6) for k in rest if k in check), "Rest frames did not round-trip")
    face_segment = np.array([np.bincount(segments[t], minlength=5).argmax() for t in tris])
    corner_uv = uv[loops]
    summary, mapping = [], {}
    material = args.material_prefix or args.prefix
    groups = [(f"{args.prefix}_{SEGMENT_NODES[i]}", (face_segment == i) & ~skin_faces, material + "a")
              for i in range(5)]
    groups += [(f"{args.prefix}_skin{s}", (face_segment == i) & skin_faces, args.model)
               for i, s in ((1, "l"), (2, "r"))]
    for name, selected, bitmap in groups:
        if not selected.any():
            continue
        node = node_for_faces(name, tris[selected], verts, corner_uv[selected], weights, bone_names, bitmap,
                              args.weight_decimals)
        node.parent = args.model
        bones = sorted({b for row in node.arrays["weights"] for b, _ in row})
        require(len(bones) <= tolerances["boneLimitPerSkinNode"], f"{name} exceeds the bone limit: {len(bones)}")
        require(len(node.arrays["verts"]) < 65535 and len(node.arrays["tverts"]) < 65535, name + " exceeds 16-bit limits")
        model.nodes.append(node)
        mapping[name] = np.unique(tris[selected])
        summary.append({"node": name, "bitmap": bitmap, "faces": int(selected.sum()),
                        "verts": len(node.arrays["verts"]), "tverts": len(node.arrays["tverts"]),
                        "bones": bones, "boneCount": len(bones)})
    path = output / (args.model + ".mdl")
    skin_plt = None
    if args.skin_plt:
        inputs.append(pin(args.skin_plt))
        skin_plt = output / (args.model + ".plt")
        shutil.copyfile(args.skin_plt, skin_plt)
    mdl_ascii.write(path, model, weight_decimals=args.weight_decimals)
    np.savez_compressed(output / "node-vertices.npz", **mapping)
    verify_pins(inputs)
    report = {"schemaVersion": 1, "kind": "srn-robe-intended-model", "createdUtc": utc(), "model": args.model,
              "supermodel": stock.name, "inputs": inputs, "skeleton": [n.name for n in model.nodes[1:]
                                                                       if n.kind == "dummy"],
              "skeletonSource": "stock bind frames copied unchanged" if rest is None else "limb rest frames at the outfit A-pose joints (rigid part of the proxy transforms)", "skinNodes": summary,
              "materials": {"fixed": material + "a", "skinPlt": args.model,
                            "skinPltFile": pin(skin_plt) if skin_plt else None},
              "triangles": int(len(tris)), "file": pin(path), "restPose": args.rest, "mergedBones": merged,
              "bindFramesChanged": args.rest != "bind", "stockRigChanged": False, **FLAGS}
    print(write_fresh(output / "model.json", report)["sha256"])


if __name__ == "__main__":
    main()
