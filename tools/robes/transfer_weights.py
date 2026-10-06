"""Region-restricted skin-weight transfer onto a fitted outfit (Blender).

Each segment of the fitted outfit receives weights only from its configured
donor faces: stock robe skin regions and/or the rigid stock body-part cage.
Transfer is barycentric interpolation at the nearest donor face (Blender BVH,
equivalent to Data Transfer POLYINTERP_NEAREST), followed by joint/border
smoothing, influence limiting, normalisation and validation against the
frozen control tolerances. Exposed skin is detected by colour only inside the
forearm/hand segments. When the fit ran in the generation (A-)pose, donors and
cage are posed into that pose and sampled there, away from the arms-down bind
pose where hands rest on the belt. Writes weights.npz and weights.json; approves nothing.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fit_math
import lbs
import mdl_ascii
from mesh_ops import neighbours, smooth_field, weld_ids
from blender_io import base_color_image, face_colours, import_single
from robe_common import FLAGS, fresh_directory, merge_pins, pin, read, require, skin_colour, utc, verify_pins, write_fresh
from robe_weights import limb_corrections, limit_and_normalize, validate
from stock_body import SKIN_BONES, Body

ARM_BONES = {"L": {"lbicep_g", "lforearm_g"}, "R": {"rbicep_g", "rforearm_g"}}
UPPER_BONES = {"torso_g", "pelvis_g"}


class Donor:
    """Triangle soup with per-vertex dense weights over SKIN_BONES."""

    def __init__(self):
        self.verts, self.faces, self.weights = [], [], []

    def add(self, verts, faces, weights):
        offset = sum(len(v) for v in self.verts)
        self.verts.append(np.asarray(verts, float))
        self.faces.append(np.asarray(faces, np.int64) + offset)
        self.weights.append(np.asarray(weights, float))

    def build(self):
        self.v, self.f, self.w = np.vstack(self.verts), np.vstack(self.faces), np.vstack(self.weights)
        self.tree = BVHTree.FromPolygons([tuple(p) for p in self.v.tolist()], [tuple(t) for t in self.f.tolist()])
        return self

    def sample(self, points):
        out = np.zeros((len(points), len(SKIN_BONES)))
        gaps = np.zeros(len(points))
        for row, point in enumerate(points):
            location, _, index, gap = self.tree.find_nearest(Vector(point))
            a, b, c = self.v[self.f[index]]
            p = np.array(location)
            v0, v1, v2 = b - a, c - a, p - a
            d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
            denominator = d00 * d11 - d01 * d01
            if abs(denominator) < 1e-18:
                bary = np.array([1.0, 0.0, 0.0])
            else:
                v = (d11 * d20 - d01 * d21) / denominator
                w = (d00 * d21 - d01 * d20) / denominator
                bary = np.clip([1 - v - w, v, w], 0, 1)
                bary /= bary.sum()
            out[row] = bary @ self.w[self.f[index]]
            gaps[row] = gap
        return out, gaps


def robe_donor_faces(rig, node, offset):
    weights, bones = mdl_ascii.skin_matrix(node)
    dense = np.zeros((len(weights), len(SKIN_BONES)))
    for column, bone in enumerate(bones):
        require(bone in SKIN_BONES, "Donor bone outside target skin bones: " + bone)
        dense[:, SKIN_BONES.index(bone)] = weights[:, column]
    world = lbs.bind_world(rig, node) + offset
    faces = np.asarray(node.arrays["faces"])[:, :3]
    dominant = np.array(bones)[weights.argmax(1)]
    return world, faces, dense, dominant


def cage_part(body, part, frames=None):
    verts = body.posed_part(part, frames)
    dense = np.zeros((len(verts), len(SKIN_BONES)))
    dense[:, SKIN_BONES.index(body.parts[part]["bone"])] = 1.0
    return verts, body.parts[part]["faces"], dense


def skin_mask(obj, tris, loops):
    image = base_color_image(obj)
    if image is None or not obj.data.uv_layers:
        return None
    return skin_colour(face_colours(obj, loops, image))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repaired", type=Path, required=True)
    parser.add_argument("--fit", type=Path, required=True, help="Fit output directory")
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--tolerances", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    inputs = [pin(args.config), pin(args.repaired), pin(args.fit / "fit.json"), pin(args.fit / "fit-arrays.npz"),
              pin(args.extraction), pin(args.tolerances)]
    config, tolerances = read(args.config), read(args.tolerances)
    require(tolerances["kind"] == "srn-robe-control-tolerances" and tolerances["frozen"], "Frozen tolerances required")
    fit_report = read(args.fit / "fit.json")
    output = fresh_directory(args.output)
    arrays = np.load(args.fit / "fit-arrays.npz")
    obj = import_single(args.repaired)
    require(len(obj.data.vertices) == len(arrays["fitted"]), "Repaired mesh order differs from the fit arrays")
    obj.data.vertices.foreach_set("co", arrays["fitted"].ravel())
    obj.data.update()
    obj.data.calc_loop_triangles()
    tris = np.empty(len(obj.data.loop_triangles) * 3, dtype=np.int64)
    obj.data.loop_triangles.foreach_get("vertices", tris)
    loops = np.empty(len(obj.data.loop_triangles) * 3, dtype=np.int64)
    obj.data.loop_triangles.foreach_get("loops", loops)
    tris, loops = tris.reshape(-1, 3), loops.reshape(-1, 3)
    require(np.array_equal(tris, arrays["tris"]), "Triangle order differs from the fit arrays")
    verts = arrays["fitted"]
    welded = weld_ids(verts, 1e-6)
    _, first = np.unique(welded, return_index=True)
    rows, cols = neighbours(tris, len(first), welded)
    labels = arrays["segmentLabels"][first]
    generation = "fittedGeneration" in arrays.files
    points = (arrays["fittedGeneration"] if generation else verts)[first]
    transforms = dict(zip(fit_math.PROXY, arrays["proxyTransforms"])) if generation else None
    extraction = read(args.extraction)
    ascii_dir = Path(extraction["asciiDirectory"])
    body = Body(ascii_dir, config["target"]["prefix"])
    merge_pins(inputs, body.sources)
    plan = config["weights"]
    donor_name = plan["upperDonor"]
    rig = lbs.Rig(ascii_dir / (donor_name + ".mdl"), lbs.chain_for(args.extraction, donor_name), ascii_dir)
    merge_pins(inputs, rig.sources)
    robe_node = next(n for n in rig.model.nodes if n.kind == "skin")
    offset = body.bind["rootdummy"][:3, 3] - rig.bind["rootdummy"][:3, 3]
    rv, rf, rw, dominant = robe_donor_faces(rig, robe_node, offset)
    frames = None
    if generation:
        rv = fit_math.pose_weighted(rv, rw, SKIN_BONES, transforms, fit_report.get("conversionBlend", "linear"))
        frames = fit_math.generation_pose_frames(body.bind, transforms)
    face_bone = dominant[rf[:, 0]]

    def robe_subset(bones):
        keep = np.isin(face_bone, list(bones))
        return rv, rf[keep], rw

    donors = {}
    torso = Donor()
    torso.add(*robe_subset(UPPER_BONES))
    torso.add(*cage_part(body, "neck", frames))
    donors["torso"] = torso.build()
    for side, lower in (("L", "l"), ("R", "r")):
        arm = Donor()
        arm.add(*robe_subset(ARM_BONES[side]))
        arm.add(*cage_part(body, "hand" + lower, frames))
        donors["arm_" + side] = arm.build()
        leg = Donor()
        for part in ("leg" + lower, "shin" + lower, "foot" + lower, "pelvis"):
            leg.add(*cage_part(body, part, frames))
        donors["leg_" + side] = leg.build()
    weights = np.zeros((len(points), len(SKIN_BONES)))
    gaps = np.zeros(len(points))
    for index, name in enumerate(fit_math.SEGMENTS):
        members = np.flatnonzero(labels == index)
        if len(members):
            weights[members], gaps[members] = donors[name].sample(points[members])
    hanging = plan.get("hangingBelowCrotch")
    hanging_count = 0
    if hanging:
        crotch = fit_report["stockTargets"]["crotch"]
        below = np.flatnonzero((labels == 0) & (points[:, 2] < crotch))
        alpha = np.clip((crotch - points[below, 2]) / hanging["ramp"], 0, 1) * hanging["maximumLegShare"]
        for side, sign in (("L", -1), ("R", 1)):
            chosen = below[np.sign(points[below, 0]) == sign]
            if len(chosen):
                leg, _ = donors["leg_" + side].sample(points[chosen])
                a = alpha[np.sign(points[below, 0]) == sign][:, None]
                weights[chosen] = (1 - a) * weights[chosen] + a * leg
        hanging_count = int(len(below))
    raw = weights.copy()
    smoothed = smooth_field(weights, rows, cols, len(points), plan.get("smoothingIterations", 8))
    masked_counts = {}
    for name, allowed in plan.get("segmentBoneMasks", {}).items():
        members = labels == fit_math.SEGMENTS.index(name)
        blocked = [i for i, bone in enumerate(SKIN_BONES) if bone not in allowed]
        masked_counts[name] = int((smoothed[np.ix_(members, blocked)] > 0).any(1).sum())
        smoothed[np.ix_(members, blocked)] = 0.0
    cap = plan.get("torsoArmShareCap")
    if cap is not None:
        torso_members = labels == 0
        arm_columns = [SKIN_BONES.index(b) for b in ("lbicep_g", "rbicep_g", "lforearm_g", "rforearm_g",
                                                     "lhand_g", "rhand_g")]
        share = smoothed[np.ix_(torso_members, arm_columns)].sum(1) / np.maximum(smoothed[torso_members].sum(1), 1e-12)
        scale = np.where(share > cap, cap / np.maximum(share, 1e-12), 1.0)
        rows_t = np.flatnonzero(torso_members)
        smoothed[np.ix_(rows_t, arm_columns)] *= scale[:, None]
        masked_counts["torsoArmShareCapped"] = int((share > cap).sum())
    joints = fit_report["outfitJoints"] if generation else fit_report["stockTargets"]
    masked_counts.update(limb_corrections(smoothed, points, labels, SKIN_BONES, plan, joints))
    limited = limit_and_normalize(smoothed, 4, plan.get("prune", 0.01))
    report_weights = validate(limited, SKIN_BONES, SKIN_BONES, sum_tolerance=tolerances["tolerances"]["weightSum"],
                              max_influences=tolerances["maximumInfluences"], bone_limit=None)
    mask = skin_mask(obj, tris, loops)
    arm_faces = np.isin(arrays["segmentLabels"][tris[:, 0]], [1, 2])
    proxy = arrays["proxyWeights"].argmax(1)
    forearm_hand = np.isin(proxy[tris].max(1), [fit_math.PROXY.index(n) for n in ("fa_L", "hand_L", "fa_R", "hand_R")])
    skin_faces = np.zeros(len(tris), bool) if mask is None else (mask & arm_faces & forearm_hand)
    weights_full = limited[welded]
    segments = arrays["segmentLabels"]
    np.savez_compressed(output / "weights.npz", weights=weights_full, bones=np.array(SKIN_BONES), tris=tris,
                        loops=loops, verts=verts, segmentLabels=segments, skinFaces=skin_faces,
                        rawWeld=raw, donorGap=gaps)
    uv = np.empty(len(obj.data.loops) * 2)
    obj.data.uv_layers.active.data.foreach_get("uv", uv)
    np.save(output / "loop-uv.npy", uv.reshape(-1, 2))
    verify_pins(inputs)
    per_segment = {}
    for index, name in enumerate(fit_math.SEGMENTS):
        members = labels == index
        if members.any():
            used = [SKIN_BONES[i] for i in np.flatnonzero(limited[members].max(0) > 0)]
            per_segment[name] = {"vertices": int(members.sum()), "bones": used, "boneCount": len(used),
                                 "maximumDonorGap": float(gaps[members].max()),
                                 "p95DonorGap": float(np.percentile(gaps[members], 95))}
    report = {"schemaVersion": 1, "kind": "srn-robe-weights", "createdUtc": utc(), "outfit": config["outfit"],
              "inputs": inputs, "samplingSpace": "generation" if generation else "bind", "method": "region-restricted nearest-face barycentric transfer (Blender BVH), "
                                         "Laplacian joint/border smoothing, 4-influence limit, normalisation",
              "donors": {"upper": donor_name, "upperOffsetApplied": offset.tolist(), "legs": "body-part cage",
                         "hands": "body-part cage", "neck": "body-part cage"},
              "bones": SKIN_BONES, "validation": report_weights, "boneLimitPerNode": tolerances["boneLimitPerSkinNode"],
              "segments": per_segment,
              "exposedSkin": {"faces": int(skin_faces.sum()), "method": "base-colour rule inside forearm/hand arm segments",
                              "available": mask is not None},
              "hangingItems": {"rule": hanging, "vertices": hanging_count},
              "corrections": {"segmentBoneMasks": plan.get("segmentBoneMasks"), "torsoArmShareCap": cap,
                              "verticesChanged": masked_counts},
              "rigidOrnaments": plan.get("rigidOrnaments"), "weights": pin(output / "weights.npz"), **FLAGS}
    print(json.dumps(write_fresh(output / "weights.json", report)))


if __name__ == "__main__":
    main()
