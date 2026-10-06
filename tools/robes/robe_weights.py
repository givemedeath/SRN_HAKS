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
