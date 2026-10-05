"""Opt-in diagnostic UV-derived basis for genuinely new pelvis cut corners.

This module never rewrites an original corner or mutates the strict authored
tangent helper. Derivatives use authoritative original working-space positions
and raw GLTF UV, before the native provenance V flip.
"""
import copy
import numpy as np

import target_contract as contract
import target_diagnostic_material_lineage as lineage
from segment_target_pelvis_boundary import CORNER_KEYS, bary, edge_keys

POLICY_ID = 'original-triangle-raw-uv-new-corner-basis-v1'
MAP_KIND = 'target-diagnostic-pelvis-body-uv-basis-cut-map'
CONFIG_KIND = 'target-diagnostic-pelvis-body-uv-basis-segmentation'
KIND = 'target-part-diagnostic-uv-basis-material-geometry'
OPERATION = 'body-only-segment-and-partition-uv-derived-new-corners'
POLICY_DESCRIPTION = {
    'id': POLICY_ID,
    'scope': 'genuinely-new-cut-corners-only',
    'positionDerivativeSpace': 'original-working-attachment-local-triangle',
    'uvDerivativeSpace': 'original-raw-gltf-uv-before-native-v-flip',
    'normalPolicy': 'normalize-barycentric-original-normal; original-corners-literal',
    'tangentPolicy': 'normalize-dPdu-projected-orthogonal-to-new-normal',
    'handednessPolicy': 'sign-dot-cross-new-normal-new-tangent-with-normalized-dPdv',
    'originalCornerPolicy': 'copy-all-original-float64-and-serialized-attributes-exact',
    'uvAbsoluteDeterminantMinimum': 1e-15,
    'uvRelativeDeterminantMinimum': 1e-12,
    'normalLengthMinimum': 1e-10,
    'projectedTangentLengthMinimum': 1e-10,
    'projectedTangentRelativeLengthMinimum': 1e-12,
    'uvVDerivativeLengthMinimum': 1e-10,
    'orientationAbsoluteCosineMinimum': 1e-8,
    'statureApplicationsAdded': 0,
    'authoredTangentsPreservedAtNewCorners': False,
}


def require_policy(value):
    contract.require(value == POLICY_ID, 'Explicit diagnostic new-corner UV-derived shading policy required')


def reviewed_body_map(selection, rows, original_ids):
    """Validate distinct policy consent, then reuse unchanged topology/map rules."""
    contract.require(type(selection) is dict and selection.get('kind') == MAP_KIND,
                     'Distinct opt-in diagnostic UV-basis cut map required')
    require_policy(selection.get('newCornerShadingPolicy'))
    review = selection.get('rootReview', {})
    contract.require(type(review) is dict, 'Explicit UV-basis root review required')
    require_policy(review.get('newCornerShadingPolicy'))
    projected = copy.deepcopy(selection)
    projected['kind'] = lineage.MAP_KIND
    projected.pop('newCornerShadingPolicy')
    projected['rootReview'].pop('newCornerShadingPolicy')
    return lineage.reviewed_body_map(projected, rows, original_ids)


def basis_details(parent, face_id, weights):
    """Derive one append-only corner basis, without inspecting or changing old T/W."""
    weights = bary(weights)
    p = np.asarray(parent['positions'][face_id], dtype=np.float64)
    uv = np.asarray(parent['uvGltf'][face_id], dtype=np.float64)
    normals = np.asarray(parent['normals'][face_id], dtype=np.float64)
    contract.require(p.shape == (3, 3) and uv.shape == (3, 2) and normals.shape == (3, 3)
                     and np.isfinite(p).all() and np.isfinite(uv).all() and np.isfinite(normals).all(),
                     'Finite original triangle P/rawUV/N required')
    e1, e2 = p[1] - p[0], p[2] - p[0]
    d1, d2 = uv[1] - uv[0], uv[2] - uv[0]
    determinant = float(d1[0] * d2[1] - d1[1] * d2[0])
    uv_product = float(np.linalg.norm(d1) * np.linalg.norm(d2))
    contract.require(np.isfinite(determinant) and uv_product > 0
                     and abs(determinant) > POLICY_DESCRIPTION['uvAbsoluteDeterminantMinimum']
                     and abs(determinant) / uv_product > POLICY_DESCRIPTION['uvRelativeDeterminantMinimum'],
                     'Singular or ambiguous original raw-UV triangle rejected')
    dpu = (e1 * d2[1] - e2 * d1[1]) / determinant
    dpv = (-e1 * d2[0] + e2 * d1[0]) / determinant
    normal = weights @ normals
    length_n = float(np.linalg.norm(normal))
    contract.require(np.isfinite(normal).all() and length_n > POLICY_DESCRIPTION['normalLengthMinimum'],
                     'Degenerate interpolated normal rejected')
    normal /= length_n
    projected = dpu - normal * float(normal @ dpu)
    length_t = float(np.linalg.norm(projected))
    length_u = float(np.linalg.norm(dpu))
    length_v = float(np.linalg.norm(dpv))
    contract.require(np.isfinite(dpu).all() and np.isfinite(dpv).all()
                     and length_t > POLICY_DESCRIPTION['projectedTangentLengthMinimum']
                     and length_u > 0
                     and length_t / length_u > POLICY_DESCRIPTION['projectedTangentRelativeLengthMinimum'],
                     'Vanishing or ambiguous projected UV tangent rejected')
    contract.require(length_v > POLICY_DESCRIPTION['uvVDerivativeLengthMinimum'],
                     'Vanishing UV-v derivative rejected')
    tangent = projected / length_t
    orientation = float(np.cross(normal, tangent) @ (dpv / length_v))
    contract.require(np.isfinite(orientation)
                     and abs(orientation) > POLICY_DESCRIPTION['orientationAbsoluteCosineMinimum'],
                     'Ambiguous UV-v basis orientation rejected')
    sign = 1.0 if orientation > 0 else -1.0
    return np.r_[tangent, sign], {
        'rawUvDeterminant': determinant,
        'rawUvRelativeDeterminant': abs(determinant) / uv_product,
        'projectedTangentLength': length_t,
        'projectedTangentRelativeLength': length_t / length_u,
        'basisOrientationCosine': orientation,
        'interpolatedNormalLength': length_n,
        'tangentNormalDot': float(tangent @ normal),
        'tangentLength': float(np.linalg.norm(tangent)),
    }


def new_corner(parent, face_id, weights, canonical, *, policy):
    require_policy(policy)
    weights = bary(weights)
    original = np.flatnonzero(weights == 1)
    if len(original) == 1:
        corner = int(original[0])
        contract.require(np.array_equal(weights, np.eye(3)[corner]),
                         'Original corner must be literal one-hot barycentric weights')
        return {key: parent[key][face_id, corner].copy()
                for key in CORNER_KEYS | {'tangents'}}, corner
    nonzero = np.flatnonzero(weights)
    contract.require(len(nonzero) == 2 and np.all(weights[nonzero] > 0),
                     'Genuinely new strict edge cut corner required')
    result = {key: weights @ parent[key][face_id] for key in CORNER_KEYS}
    for key in ('normals', 'sourceNormals'):
        length = float(np.linalg.norm(result[key]))
        contract.require(np.isfinite(result[key]).all() and length > POLICY_DESCRIPTION['normalLengthMinimum'],
                         'Degenerate interpolated normal rejected')
        result[key] /= length
    result['tangents'], _ = basis_details(parent, face_id, weights)
    keys = edge_keys(parent['positions'][face_id])
    lower, upper = sorted(nonzero, key=lambda index: keys[index])
    key = ((keys[lower], keys[upper]), float(weights[upper]))
    contract.require(key in canonical, 'Pinned conforming geometric edge point required')
    result['positions'] = canonical[key].copy()
    result['uvNative'] = result['uvGltf'].copy()
    result['uvNative'][1] = 1 - result['uvNative'][1]
    return result, -1


def basis_summary(parent, plans):
    """Read-only eligibility and honest authored-versus-derived shading evidence."""
    records = []
    strict_rejected = []
    source_conflicts = 0
    all_source_conflicts = 0
    unavailable_original_basis = 0
    original_alignment = []
    new_alignment = []
    new_w_conflicts = 0
    old_original_count = 0
    for face, (_, polygons) in plans.items():
        old_t = parent['tangents'][face]
        contract.require(np.all(abs(old_t[:, 3]) == 1), 'Original cut-corner GLTF signs must remain plus/minus one')
        rejected = not np.all(old_t[:, 3] == old_t[0, 3])
        if rejected:
            strict_rejected.append(face)
        for c in range(3):
            try:
                t, _ = basis_details(parent, face, np.eye(3)[c])
            except ValueError:
                # The policy does not alter original corners. Do not normalize
                # or reject their preserved attributes merely for this metric.
                unavailable_original_basis += 1
                continue
            conflict = t[3] != old_t[c, 3]
            all_source_conflicts += int(conflict)
            if rejected:
                source_conflicts += int(conflict)
            auth_length = float(np.linalg.norm(old_t[c, :3]))
            if rejected and auth_length > 0:
                original_alignment.append(float(t[:3] @ (old_t[c, :3] / auth_length)))
        weights = sorted({tuple(w) for triangles in polygons.values() for triangle in triangles for w in triangle})
        for w in weights:
            w = np.asarray(w)
            if np.any(w == 1):
                old_original_count += 1
                continue
            t, metric = basis_details(parent, face, w)
            authored = w @ old_t[:, :3]
            normal = w @ parent['normals'][face]
            normal /= np.linalg.norm(normal)
            authored -= normal * float(normal @ authored)
            auth_length = float(np.linalg.norm(authored))
            if auth_length > 1e-10:
                new_alignment.append(float(t[:3] @ (authored / auth_length)))
            active_w = old_t[w > 0, 3]
            new_w_conflicts += int(not np.all(active_w == t[3]))
            records.append(metric)
    def bounds(key):
        values = [r[key] for r in records]
        return [min(values), max(values)] if values else None
    return {
        'policy': copy.deepcopy(POLICY_DESCRIPTION),
        'uniqueNewCornersChecked': len(records),
        'literalOriginalCutCornersChecked': old_original_count,
        'originalStrictAuthoredHandednessRejectedParentBodyFaceIds': strict_rejected,
        'originalStrictAuthoredHandednessRejectedFaces': len(strict_rejected),
        'originalWConflictsWithUvBasisOnStrictRejectedFaces': source_conflicts,
        'originalWConflictsWithUvBasisOnAllCutFaces': all_source_conflicts,
        'unavailableOriginalCornerBasisMetrics': unavailable_original_basis,
        'newCornersWithAuthoredContributingWNotAllEqualDerivedW': new_w_conflicts,
        'strictRejectedOriginalUvDerivedVsAuthoredTangentDotRange':
            [min(original_alignment), max(original_alignment)] if original_alignment else None,
        'strictRejectedOriginalUvDerivedVsAuthoredTangentDotMedian':
            float(np.median(original_alignment)) if original_alignment else None,
        'newUvDerivedVsInterpolatedAuthoredTangentDotRange':
            [min(new_alignment), max(new_alignment)] if new_alignment else None,
        'newUvDerivedVsInterpolatedAuthoredTangentDotMedian':
            float(np.median(new_alignment)) if new_alignment else None,
        'basisOrientationCosineRange': bounds('basisOrientationCosine'),
        'rawUvDeterminantRange': bounds('rawUvDeterminant'),
        'rawUvRelativeDeterminantRange': bounds('rawUvRelativeDeterminant'),
        'projectedTangentRelativeLengthRange': bounds('projectedTangentRelativeLength'),
        'maximumTangentNormalDotMagnitude':
            max(abs(r['tangentNormalDot']) for r in records) if records else 0.0,
        'authoredTangentsPreservedAtOriginalCorners': True,
        'authoredTangentsPreservedAtNewCorners': False,
        'originalCornersRecomputed': False,
        'statureApplicationsAdded': 0,
        'basisEvidenceComputedBeforeExport': True,
    }
