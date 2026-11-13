"""Bake-miss screening and reviewed colour patches, on CPU before or after a failed bake.

`screen` repeats the bake preflight's donor test (blender_worker.transfer_preflight) on a run's reduced target, so a
fit that cannot pass can be found before unwrap, finish and Cycles. `measure` takes the faces a bake preflight or
miss diagnostic reported and measures each against the fitted donor, for the review of an unoriented colour patch.
`add_patch` writes that reviewed patch into a new fit manifest. None of these changes geometry or approves anything:
the patch quotes the user's review and the worker re-validates it against the exact target.
"""
import copy
import json
import math
from pathlib import Path

import numpy as np

from tools.headkit.common import require
from .geometry import corner_hash
from .preflight import target_hash
from .transfer import PATCH_SCOPE, patch_distance_bound, patch_scope, validate_texture_patch

PART_ORDER = ('b', 'm', 't', 'whole')
DEFAULT_UNORIENTED = .0021                    # the worker's default maximumUnorientedDistance
SAMPLES = np.array([(i/8, j/8, 1 - i/8 - j/8) for i in range(9) for j in range(9 - i)])   # 45 points per triangle


def joined_target(values):
    """The bake's joined target from unwrap arrays (final atlas, or the extract's uv-source): parts in native order."""
    parts = [p for p in PART_ORDER if p + '_positions' in values]
    require(parts and (parts == ['whole'] or 'whole' not in parts), 'Unwrap arrays need b/m/t parts or one whole mesh')
    positions, faces, caps, uv, offset = [], [], [], [], 0
    for part in parts:
        p = np.asarray(values[part + '_positions'], float); f = np.asarray(values[part + '_faces'])
        positions.append(p); faces.append(f + offset); offset += len(p)
        caps.append(np.asarray(values[part + '_hiddenCaps'], bool))
        if part + '_uv' in values: uv.append(np.asarray(values[part + '_uv'], float))
    p, f = np.vstack(positions), np.vstack(faces)
    return {'parts': parts, 'corners': p[f], 'hiddenCaps': np.concatenate(caps),
            'uv': np.vstack(uv) if len(uv) == len(parts) else None}


def _one(run, patterns, explicit, what, option):
    """The run's only file for the first pattern that matches, or the explicit one; never a guess between attempts."""
    if explicit: require(Path(explicit).is_file(), f'{explicit} not found'); return Path(explicit)
    for pattern in patterns:
        found = sorted(Path(run).glob(pattern))
        if found:
            require(len(found) == 1, f'{run}: {len(found)} {what} ({", ".join(p.parent.as_posix() for p in found)}); choose one with {option}')
            return found[0]
    raise ValueError(f'{run}: no {what}')


def run_target(run, arrays=None):
    """The run's unwrap arrays: the final atlas when unwrap finished, else its extract."""
    path = _one(run, ('unwrap/attempt-*/atlas/final-atlas.npz', 'unwrap/attempt-*/extract/worker/uv-source.npz'), arrays,
                'unwrap arrays', '--arrays')
    with np.load(path, allow_pickle=False) as archive:
        target = joined_target({k: archive[k] for k in archive.files})
    return {**target, 'source': str(path)}


def fitted_donor(run, donor_glb, fit=None):
    """The textured donor in native coordinates, through the run's fit matrix (rawToNativeMatrix)."""
    from tools.headkit.gltf import mesh
    require(Path(donor_glb).is_file(), f'Donor {donor_glb} not found')
    path = _one(run, ('fit/attempt-*/worker/result.json',), fit, 'fit results', '--fit')
    matrix = np.asarray(json.loads(path.read_text(encoding='utf-8'))['rawToNativeMatrix'], float)
    require(matrix.shape == (4, 4), 'Fit matrix must be 4x4')
    m = mesh(donor_glb); v = np.asarray(m['positions'], float)
    return v @ matrix[:3, :3].T + matrix[:3, 3], np.asarray(m['faces'], np.int64)


def _uv_area(uv):
    """Atlas area of per-corner UV triangles (..., 3, 2)."""
    a = uv[..., 1, :] - uv[..., 0, :]; b = uv[..., 2, :] - uv[..., 0, :]
    return np.abs(a[..., 0]*b[..., 1] - a[..., 1]*b[..., 0])/2


def _normals(triangles):
    n = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(n, axis=1); require(np.all(length > 1e-12), 'Degenerate triangle')
    return n / length[:, None]


def screen(corners, caps, donor_vertices, donor_faces, *, distance=.003, alignment=.5):
    """Visible faces whose centroid has no donor triangle within `distance` facing within `alignment` (the preflight)."""
    import igl
    from scipy.spatial import cKDTree
    require(0 < distance <= PATCH_SCOPE['distance'] and .5 <= alignment <= 1, 'Bounded donor screen policy required')
    corners = np.asarray(corners, float); dv = np.asarray(donor_vertices, float); df = np.asarray(donor_faces, np.int64)
    donor = dv[df]; donor_normals = _normals(donor); centres = donor.mean(1)
    reach = np.linalg.norm(donor - centres[:, None], axis=2).max()
    tree = cKDTree(centres); visible = np.flatnonzero(~np.asarray(caps, bool))
    normals = _normals(corners[visible]); points = corners[visible].mean(1)
    failed = []
    for face, point, normal, near in zip(visible, points, normals, tree.query_ball_point(points, distance + reach)):
        ids = np.asarray(near, np.int64); ids = ids[donor_normals[ids] @ normal >= alignment]
        if not (len(ids) and igl.point_mesh_squared_distance(point[None], dv, df[ids])[0][0] <= distance**2): failed.append(int(face))
    return {'sample': 'visible-face-centroids', 'visibleFaces': int(len(visible)), 'failedFaces': failed,
            'policyDistance': distance, 'minimumNormalAlignment': alignment, 'continuousSurfaceProof': False}


def measure(corners, uv, faces, donor_vertices, donor_faces, size, mapped_texels):
    """Per reported face: centroid and sampled distance to the donor, nearest facing and mapped texels at `size`."""
    import igl
    require(faces and len(set(faces)) == len(faces), 'Faces to measure required')
    corners = np.asarray(corners, float); uv = np.asarray(uv, float)
    dv = np.asarray(donor_vertices, float); df = np.asarray(donor_faces, np.int64); donor_normals = _normals(dv[df])
    rows = []
    for face in faces:
        t = corners[face]; n = _normals(t[None])[0]
        centre, nearest, _ = igl.point_mesh_squared_distance(t.mean(0)[None], dv, df)
        sampled = np.sqrt(igl.point_mesh_squared_distance(SAMPLES @ t, dv, df)[0])
        texels = _uv_area(uv[face]) * size * size
        rows.append({'face': int(face), 'centroid': t.mean(0).round(4).tolist(), 'centroidMm': round(math.sqrt(centre[0]) * 1e3, 3),
                     'sampledMaxMm': round(float(sampled.max()) * 1e3, 3), 'nearestFacing': round(float(donor_normals[nearest[0]] @ n), 3),
                     'texels': round(float(texels), 1)})
    texels = sum(r['texels'] for r in rows)
    return {'faces': rows, 'texels': round(texels, 1), 'mappedTexels': int(mapped_texels), 'textureFraction': texels / mapped_texels,
            'maximumDistance': math.ceil(max(r['sampledMaxMm'] for r in rows) * 100) / 1e5,   # metres, rounded up to 0.01 mm
            'cornerHash': corner_hash(corners), 'targetHash': target_hash(corners, uv)}


def measure_run(run, donor_glb, report, arrays=None, fit=None):
    """`measure` on a run, for the faces of a bake `preflight.json` or `donor-miss-diagnostic.json`."""
    report = Path(report); data = json.loads(report.read_text(encoding='utf-8'))
    faces = data.get('donorSampling', {}).get('failedFaces'); require(faces, f'{report.name}: no failed faces')
    target = run_target(run, arrays); require(target['uv'] is not None, f"{run}: the unwrap atlas is needed to measure a patch")
    if data.get('targetHash'):
        require(data['targetHash'] == target_hash(target['corners'], target['uv']),
                f'{report.name} belongs to a different target than {target["source"]}')
    size = data.get('size') or 1024; mapped = data.get('raster', {}).get('mappedTexels')
    if mapped is None:                         # a miss diagnostic: count mapped texels of visible faces at the preflight size
        mapped = int(round(float(_uv_area(target['uv'][~target['hiddenCaps']]).sum()) * size * size))
    dv, df = fitted_donor(run, donor_glb, fit)
    return {**measure(target['corners'], target['uv'], faces, dv, df, size, mapped), 'report': str(report), 'size': size,
            'target': target['source']}


def add_patch(manifest, corners, faces, distance, notes, user_approval=None):
    """A copy of a fit manifest with a reviewed unoriented-source colour patch for exactly `faces` of this target.

    The patch may reach 3 mm and 0.01% of the mapped texels, or 3.25 mm and 0.05% when it quotes the user's approval.
    A distance above the policy's maximumUnorientedDistance (default 2.1 mm) raises that bound to it, since the worker
    caps the patch there. The worker re-validates the corner hash, distance and texel scope when it bakes.
    """
    manifest = copy.deepcopy(manifest)
    policy = manifest.get('processing', {}).get('missCorrection')
    require(isinstance(policy, dict) and policy.get('method') == 'nearest-finished-donor',
            'The manifest needs its nearest-finished-donor miss correction before a patch')
    require(isinstance(notes, str) and notes.strip(), "A patch quotes its review (--notes)")
    patch = {'faces': sorted(int(f) for f in faces), 'maximumDistance': float(distance), 'reviewed': True,
             'targetCornerHash': corner_hash(corners), 'notes': notes.strip()}
    if user_approval is not None:
        require(isinstance(user_approval, str) and user_approval.strip(), "userApproval is the user's own words")
        patch['userApproval'] = user_approval.strip()
    scope = patch_scope(patch); patch['maximumTextureFraction'] = scope['textureFraction']
    require(0 < patch['maximumDistance'] <= scope['distance'],
            f'A patch reaches at most {scope["distance"]*1e3:g} mm' + ('' if user_approval else " without the user's approval"))
    if patch['maximumDistance'] > policy.get('maximumUnorientedDistance', DEFAULT_UNORIENTED):
        policy['maximumUnorientedDistance'] = patch['maximumDistance']
    policy['unorientedSourcePatch'] = patch
    validate_texture_patch(corners, patch, maximum_distance=patch_distance_bound(policy))
    return manifest
