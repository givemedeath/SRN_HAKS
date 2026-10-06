"""Skin-weight limiting, normalization and validation for NWN skin nodes.

Weights are a dense (vertices x bones) matrix with an ordered bone-name list.
Validation reports measurements; it never approves visible deformation.
"""
import numpy as np


def limit_and_normalize(weights, max_influences=4, prune=0.001):
    """Keep the largest influences per vertex, prune tiny ones and renormalize."""
    weights = np.clip(np.asarray(weights, dtype=float), 0.0, None)
    totals = weights.sum(axis=1)
    if np.any(totals <= 0):
        raise ValueError("Vertex without any positive weight: " + str(int(np.argmax(totals <= 0))))
    weights = weights / totals[:, None]
    if weights.shape[1] > max_influences:
        order = np.argsort(-weights, axis=1, kind="stable")
        drop = order[:, max_influences:]
        np.put_along_axis(weights, drop, 0.0, axis=1)
    weights[weights < prune] = 0.0
    totals = weights.sum(axis=1)
    if np.any(totals <= 0):
        raise ValueError("Pruning removed every influence of a vertex")
    return weights / totals[:, None]


def quantize(weights, decimals):
    """Model the ASCII writer: round each weight, then renormalize as NWN reads it."""
    rounded = np.round(np.asarray(weights, dtype=float), decimals)
    totals = rounded.sum(axis=1)
    if np.any(totals <= 0):
        raise ValueError("Quantization removed every influence of a vertex")
    return rounded


def validate(weights, bones, hierarchy, *, sum_tolerance, max_influences=4, bone_limit=None):
    """Measure weight validity against the effective bind hierarchy."""
    weights = np.asarray(weights, dtype=float)
    if weights.ndim != 2 or weights.shape[1] != len(bones):
        raise ValueError("Weight matrix and bone list differ")
    hierarchy = {name.lower() for name in hierarchy}
    used = [bone for index, bone in enumerate(bones) if np.any(weights[:, index] > 0)]
    invalid = sorted({bone for bone in used if bone.lower() not in hierarchy})
    influences = (weights > 0).sum(axis=1)
    totals = weights.sum(axis=1)
    deviation = np.abs(totals - 1.0)
    report = {
        "vertices": int(weights.shape[0]),
        "bonesUsed": sorted(used),
        "boneCount": len(used),
        "invalidBones": invalid,
        "unweightedVertices": int(np.sum(influences == 0)),
        "negativeWeights": int(np.sum(weights < 0)),
        "maximumInfluences": int(influences.max()) if len(influences) else 0,
        "verticesOverInfluenceLimit": int(np.sum(influences > max_influences)),
        "maximumSumDeviation": float(deviation.max()) if len(deviation) else 0.0,
        "verticesOverSumTolerance": int(np.sum(deviation > sum_tolerance)),
        "sumTolerance": sum_tolerance,
        "influenceLimit": max_influences,
        "boneLimit": bone_limit,
    }
    report["pass"] = (not invalid and report["unweightedVertices"] == 0 and report["negativeWeights"] == 0
                      and report["verticesOverInfluenceLimit"] == 0 and report["verticesOverSumTolerance"] == 0
                      and (bone_limit is None or report["boneCount"] <= bone_limit))
    return report


def from_pairs(rows, bones=None):
    """Convert per-vertex [(bone, weight), ...] rows to a dense matrix."""
    names = list(bones) if bones is not None else sorted({bone.lower() for row in rows for bone, _ in row})
    index = {name.lower(): column for column, name in enumerate(names)}
    matrix = np.zeros((len(rows), len(names)))
    for vertex, row in enumerate(rows):
        for bone, weight in row:
            if bone.lower() not in index:
                raise ValueError("Bone outside declared list: " + bone)
            matrix[vertex, index[bone.lower()]] += float(weight)
    return matrix, names


def to_pairs(matrix, bones):
    """Dense matrix to ordered per-vertex pairs, largest influence first."""
    rows = []
    for values in np.asarray(matrix, dtype=float):
        order = np.argsort(-values, kind="stable")
        rows.append([(bones[column], float(values[column])) for column in order if values[column] > 0])
    return rows


def limb_corrections(weights, points, labels, bones, plan, joints):
    """Apply weights.rigidHands and weights.jointSharpening in place; returns per-rule vertex counts.

    points and joints must share one space (the outfit A-pose or the stock bind pose); labels are
    segment indices (1 left arm, 2 right arm). Runs after weight transfer and again after runtime
    reduction, whose decimation re-blends weights at collapsed vertices.
    """
    counts = {}
    rigid = plan.get("rigidHands")
    if rigid:
        # Gloves keep the Meshy hand shape: past a wrist band they follow only the hand bone.
        band = rigid.get("wristBand", 0.03)
        for side, segment in (("L", 1), ("R", 2)):
            wrist, tip = np.array(joints["wrist" + side]), np.array(joints["fingertip" + side])
            axis = (tip - wrist) / np.linalg.norm(tip - wrist)
            members = np.flatnonzero(labels == segment)
            share = np.clip(((points[members] - wrist) @ axis) / band, 0, 1)[:, None]
            rows = weights[members] / np.maximum(weights[members].sum(1, keepdims=True), 1e-12)
            hand = np.zeros_like(rows)
            hand[:, bones.index(side.lower() + "hand_g")] = 1.0
            weights[members] = (1 - share) * rows + share * hand
            counts["rigidHand" + side] = int((share[:, 0] >= 1).sum())
            counts["wristBand" + side] = int(((share[:, 0] > 0) & (share[:, 0] < 1)).sum())
    sharpening = plan.get("jointSharpening")
    if sharpening:
        torso_centre = np.array([0.0, 0.0, np.mean([joints["shoulderL"][2], joints["shoulderR"][2]])])
        for side in ("L", "R"):
            low = side.lower()
            shoulder, elbow, wrist = (np.array(joints[k + side]) for k in ("shoulder", "elbow", "wrist"))
            upper = (elbow - shoulder) / np.linalg.norm(elbow - shoulder)
            fore = (wrist - elbow) / np.linalg.norm(wrist - elbow)
            # Crease directions keep their blend: armpit faces the torso, the inner elbow faces forward (+Y).
            for joint, centre, axis, crease, proximal, distal in (
                    ("shoulder", shoulder, upper, torso_centre - shoulder, "torso_g", low + "bicep_g"),
                    ("elbow", elbow, fore, np.array([0.0, 1.0, 0.0]), low + "bicep_g", low + "forearm_g")):
                spec = sharpening.get(joint)
                if not spec:
                    continue
                crease = crease - (crease @ axis) * axis
                crease /= np.linalg.norm(crease)
                a, b = bones.index(proximal), bones.index(distal)
                total = weights[:, a] + weights[:, b]
                mixed = np.flatnonzero((weights[:, a] > 0) & (weights[:, b] > 0))
                radial = points[mixed] - centre
                radial -= np.outer(radial @ axis, axis)
                facing = (radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-9)) @ crease
                lo, hi = spec.get("creaseFrom", 0.3), spec.get("creaseTo", 0.7)
                keep = np.clip((facing - lo) / (hi - lo), 0, 1)
                share = weights[mixed, b] / np.maximum(total[mixed], 1e-12)
                half = spec.get("band", 0.15)
                x = np.clip((share - (0.5 - half)) / (2 * half), 0, 1)
                sharp = x * x * (3 - 2 * x)
                final = share + (1 - keep) * (sharp - share)
                weights[mixed, a] = total[mixed] * (1 - final)
                weights[mixed, b] = total[mixed] * final
                counts[f"sharpened{joint.title()}{side}"] = int(((1 - keep) > 0.5).sum())
    return counts
