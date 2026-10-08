"""Exactly replayable normal/tangent rules for bounded positional descendants of sealed native corner archives.

Rule (per triangle corner, part-local NWN working frame, float64):
  1. Weld the parent corner positions by exact equality; the child must keep that weld (a welded vertex moves as one).
  2. g0, g1 = area-weighted vertex normals of the parent / child welded meshes, averaged over the 1-ring
     `geometricSmoothing` times (deterministic; no tolerance-based welding).
  3. Transport: corners whose vertex moved, or whose g changed, rotate the authored normal by the minimal rotation g0 -> g1.
  4. Optional declared smoothing regions blend the (unit) transported normal toward g1 with weight w in [0, 1].
  5. Every output normal is unit length (approved renormalisation: direction unchanged where w = 0 and nothing moved).
  Tangents (dense or sparse rows) rotate like the normal, are re-orthogonalised against the new unit normal and keep
  their stored length and W handedness.
Region weight: angular cosine window about a fixed vertical axis through `axisCentre` (theta 0 = +y, 90 = +x) times an
axial cosine window on z. Weights are evaluated at the PARENT position of each corner.
"""
import numpy as np

RULE = 'bounded-descendant-normal-rule-v1'


def cosine_window(x, full_lo, full_hi, zero_lo, zero_hi):
    x = np.asarray(x, float); out = np.zeros_like(x)
    out[(x >= full_lo) & (x <= full_hi)] = 1
    m = (x > zero_lo) & (x < full_lo)
    out[m] = 0.5 * (1 - np.cos(np.pi * (x[m] - zero_lo) / (full_lo - zero_lo)))
    m = (x > full_hi) & (x < zero_hi)
    out[m] = 0.5 * (1 + np.cos(np.pi * (x[m] - full_hi) / (zero_hi - full_hi)))
    return out


REGION_KEYS = {'axisCentre', 'thetaCentre', 'thetaHalfFull', 'thetaHalfZero', 'zFull', 'zZero', 'weight'}


def check_region(r):
    if not (isinstance(r, dict) and set(r) == REGION_KEYS):
        raise ValueError('Exact region keys required')
    ok = (len(r['axisCentre']) == 2 and 0 <= r['thetaHalfFull'] <= r['thetaHalfZero'] <= 180 and (r['thetaHalfFull'] < r['thetaHalfZero'] or r['thetaHalfFull'] == 180) and len(r['zFull']) == 2 and len(r['zZero']) == 2
          and r['zZero'][0] < r['zFull'][0] <= r['zFull'][1] < r['zZero'][1] and 0 < r['weight'] <= 1)
    if not ok:
        raise ValueError('Malformed region window')


def region_weight(points, regions):
    """Max over declared regions of weight x angular window x axial window, at the given points (N, 3)."""
    p = np.asarray(points, float); w = np.zeros(len(p))
    for r in regions:
        check_region(r)
        th = np.degrees(np.arctan2(p[:, 0] - r['axisCentre'][0], p[:, 1] - r['axisCentre'][1]))
        d = np.abs((th - r['thetaCentre'] + 180) % 360 - 180)
        a = cosine_window(d, -1, r['thetaHalfFull'], -2, r['thetaHalfZero']) if r['thetaHalfFull'] < 180 else np.ones(len(p))
        w = np.maximum(w, r['weight'] * a * cosine_window(p[:, 2], *r['zFull'], *r['zZero']))
    return w


def weld(corners):
    from fair_female_limb_creases import weld as tolerant_weld
    return tolerant_weld(corners)


def child_vertices(P0, P1, F, U0):
    """Child welded positions. Within one parent weld class every corner either keeps its exact parent position
    (unmoved class) or all corners carry one identical child position (moved class)."""
    p0 = np.asarray(P0, np.float64).reshape(-1, 3); p1 = np.asarray(P1, np.float64).reshape(-1, 3); ids = F.reshape(-1)
    changed = np.any(p1 != p0, axis=1); cls = np.zeros(len(U0), bool); np.logical_or.at(cls, ids, changed)
    V = U0.copy(); V[ids[changed]] = p1[changed]
    if not np.array_equal(p1[cls[ids]], V[ids[cls[ids]]]) or not np.array_equal(p1[~cls[ids]], p0[~cls[ids]]):
        raise ValueError('Child splits a parent-welded vertex')
    return V, cls


def smoothed_vertex_normals(U, F, iterations):
    fn = np.cross(U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]])
    acc = np.zeros_like(U)
    for k in range(3):
        np.add.at(acc, F[:, k], fn)
    n = acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-300)[:, None]
    if iterations:
        e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1); e = np.unique(e, axis=0)
        for _ in range(iterations):
            s = n.copy(); np.add.at(s, e[:, 0], n[e[:, 1]]); np.add.at(s, e[:, 1], n[e[:, 0]])
            n = s / np.maximum(np.linalg.norm(s, axis=1), 1e-300)[:, None]
    return n


def rotate_between(a, b, v):
    """Rotate rows v by the minimal rotation taking unit a onto unit b (Rodrigues)."""
    axis = np.cross(a, b); s = np.linalg.norm(axis, axis=1); c = np.sum(a * b, axis=1)
    out = v.copy(); m = s > 1e-15
    k = axis[m] / s[m, None]; vm = v[m]
    out[m] = vm * c[m, None] + np.cross(k, vm) * s[m, None] + k * np.sum(k * vm, axis=1)[:, None] * (1 - c[m])[:, None]
    return out


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def apply(P0, N0, P1, spec, tangents=None, tangent_rows=None):
    """Return (N1 corners, T1 rows or None, report). spec: geometricSmoothing int, smoothingRegions list."""
    P0 = np.asarray(P0, np.float64); N0 = np.asarray(N0, np.float64); P1 = np.asarray(P1, np.float64)
    if P0.shape != P1.shape or N0.shape != P0.shape or P0.ndim != 3 or P0.shape[1:] != (3, 3):
        raise ValueError('Corner array shapes differ')
    if not (np.isfinite(P1).all() and np.all(np.linalg.norm(N0, axis=2) > 0)):
        raise ValueError('Finite child positions and nonzero parent normals required')
    U0, F = weld(P0); U1, moved_vertex = child_vertices(P0, P1, F, U0); k = int(spec['geometricSmoothing'])
    if moved_vertex.any():
        g0 = smoothed_vertex_normals(U0, F, k); g1 = smoothed_vertex_normals(U1, F, k)
        changed = moved_vertex | np.any(g0 != g1, axis=1)
    else:
        g0 = g1 = smoothed_vertex_normals(U0, F, k) if spec['smoothingRegions'] else None; changed = moved_vertex
    vid = F.reshape(-1); flatN = N0.reshape(-1, 3); c = changed[vid]
    n = flatN.copy()
    if c.any():
        n[c] = rotate_between(g0[vid[c]], g1[vid[c]], flatN[c])
    n = unit(n)
    w = region_weight(P0.reshape(-1, 3), spec['smoothingRegions']) if spec['smoothingRegions'] else np.zeros(len(n))
    blend = w > 0
    if blend.any():
        n[blend] = unit((1 - w[blend, None]) * n[blend] + w[blend, None] * g1[vid[blend]])
    N1 = n.reshape(N0.shape)
    T1 = None
    if tangents is not None:
        rows = np.arange(len(P0)) if tangent_rows is None else np.asarray(tangent_rows)
        T = np.asarray(tangents, np.float64).reshape(-1, 4); cv = np.repeat(rows, 3) * 3 + np.tile(np.arange(3), len(rows))
        t = T[:, :3].copy(); cc = c[cv]
        if cc.any():
            t[cc] = rotate_between(g0[vid[cv[cc]]], g1[vid[cv[cc]]], t[cc])
        nn = n[cv]; t = t - np.sum(t * nn, axis=1, keepdims=True) * nn
        t = t / np.linalg.norm(t, axis=1, keepdims=True) * np.linalg.norm(T[:, :3], axis=1, keepdims=True)
        T1 = np.concatenate([t, T[:, 3:]], axis=1).reshape(np.asarray(tangents).shape)
    lengths = np.linalg.norm(flatN, axis=1)
    report = {'rule': RULE, 'geometricSmoothing': k, 'weldedVertices': int(len(U0)), 'movedVertices': int(moved_vertex.sum()),
              'transportedCorners': int(c.sum()), 'smoothedCorners': int(blend.sum()),
              'renormalisedCorners': int((np.abs(lengths - 1) > 1e-4).sum()), 'parentNormalLengthRange': [float(lengths.min()), float(lengths.max())],
              'maximumDisplacement': float(np.linalg.norm(U1 - U0, axis=1).max()), 'weldQuantumMetres': 1e-9}
    return N1, T1, report
