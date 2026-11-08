"""Reduce a measured skin shade discontinuity across neighbouring UV islands."""
import numpy as np
from scipy.spatial import cKDTree
from .quality import SEAM_RADIUS, THRESHOLDS
from .common import read
from .rays import outer_faces
from .textures import pad
from .uv import chart_ids


def reconcile(points, normals, charts, shades, width, allowed, limit):
    """Move only seam samples with similarly facing neighbours on another chart."""
    a, b = cKDTree(points).query_pairs(SEAM_RADIUS * width, output_type='ndarray').T
    cross = charts[a] != charts[b]
    if not cross.any() or cross.all():
        return shades, {'changed': False, 'reason': 'no comparable chart boundaries'}

    def ratio(levels):
        steps = np.abs(levels[a].astype(float) - levels[b])
        return round(float(steps[cross].mean() / max(steps[~cross].mean(), 1e-6)), 3)

    before = ratio(shades)
    report = {'changed': False, 'ratioBefore': before, 'limit': limit}
    if before <= limit:
        return shades, report
    i, j = a[cross], b[cross]
    close = np.linalg.norm(points[i] - points[j], axis=1) < .009 * width
    facing = np.einsum('ij,ij->i', normals[i], normals[j]) > .8
    i, j = i[close & facing], j[close & facing]
    if not len(i):
        return shades, report
    indices = np.concatenate((i, j))
    counts = np.bincount(indices, minlength=len(shades))
    target = counts > 0
    means = np.bincount(indices, weights=shades[np.concatenate((j, i))], minlength=len(shades))[target] / counts[target]
    eligible = np.asarray(allowed)
    snap = eligible[np.abs(eligible[:, None] - np.arange(256)).argmin(axis=0)]
    for amount in (.15, .25, .4):
        candidate = shades.copy()
        candidate[target] = snap[np.rint(shades[target] + amount * (means - shades[target])).astype(int)]
        after = ratio(candidate)
        if after <= limit:
            return candidate, {**report, 'changed': True, 'ratioAfter': after, 'strength': amount,
                               'changedSkinTexels': int((candidate != shades).sum())}
    return shades, {**report, 'reason': 'bounded blending insufficient'}


def reconcile_atlas(value, owners, points, embree, selected, picked, allowed):
    positions = value['positions'].astype(float)
    faces = value['faces']
    outer, _ = outer_faces(embree, positions, faces, float(np.ptp(positions[:, 1])))
    skin = (owners >= 0) & selected & outer[np.maximum(owners, 0)]
    if not skin.any():
        return picked, {'changed': False, 'reason': 'no eligible skin'}
    atlas = np.zeros(owners.shape, dtype=np.int16)
    atlas[selected] = picked
    ids = owners[skin]
    triangles = positions[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    levels, report = reconcile(points[skin].astype(float), normals[ids], np.asarray(chart_ids(value['uv']))[ids],
                               atlas[skin], float(np.ptp(positions[:, 0])), allowed, read(THRESHOLDS)['limits']['seamStepRatioMax'])
    if not report['changed']:
        return picked, report
    delta = np.zeros_like(atlas)
    delta[skin] = levels - atlas[skin]
    # Carry the correction into the existing gutters without bleeding into another channel.
    extended = pad(delta, owners >= 0)
    indices = np.clip(atlas[selected] + extended[selected], 0, 254)
    eligible = np.asarray(allowed)
    snap = eligible[np.abs(eligible[:, None] - np.arange(256)).argmin(axis=0)]
    return snap[indices], report
