"""Exactly replayable analytic radial descendant maps (part-local NWN working frame, metres).

Each operator moves points along horizontal rays from the part's vertical axis (x=0, y=0); UVs, face order and
ownership never change. Normals transform by the inverse transpose of the central-difference Jacobian, tangents by
the Jacobian re-orthogonalized against the new normal (W handedness unchanged).
"""
import numpy as np


def chest_waist_cap_rounding(p, q):
    """r' = r - D a(theta) w(z) r/(r+D): fold-free inward rounding below z0, angular cosine blend front->back."""
    p = np.asarray(p, dtype=np.float64); x, y, z = p[..., 0], p[..., 1], p[..., 2]
    t = np.clip((np.degrees(np.abs(np.arctan2(x, y))) - q['frontDeg']) / (q['backDeg'] - q['frontDeg']), 0, 1)
    a = 0.5 - 0.5 * np.cos(np.pi * t)
    u = np.clip((q['z0'] - z) / (q['z0'] - q['zEnd']), 0, 1); c = q['c']
    w = (1 - np.sqrt(1 - (c * u) ** 2)) / (1 - np.sqrt(1 - c * c))
    r = np.hypot(x, y); rn = r - q['depth'] * a * w * r / (r + q['depth'])
    s = np.where(r > 1e-12, rn / np.where(r > 1e-12, r, 1), 1.0)
    out = p.copy(); out[..., 0] *= s; out[..., 1] *= s
    return out


def smoothstep(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def thigh_upper_back_slim_top_dome(p, q):
    """Upper-back slimming r -= aMax S(z) S(back cosine) S(r), then hidden top dome: r *= 1 - rTop S, z -= topCut S."""
    p = np.asarray(p, dtype=np.float64); x = p.reshape(-1, 3).copy()
    r = np.hypot(x[:, 0], x[:, 1]); c = np.where(r > 1e-9, -x[:, 1] / np.maximum(r, 1e-9), 0)
    d = q['aMax'] * smoothstep((x[:, 2] - q['z0']) / (q['z1'] - q['z0'])) * smoothstep((c - q['c0']) / (1 - q['c0'])) * smoothstep(r / q['rFull'])
    k = np.where(r > 1e-9, (r - d) / np.maximum(r, 1e-9), 1.0)
    st = smoothstep((x[:, 2] - q['zc']) / (q['zt'] - q['zc']))
    k = k * (1 - q['rTop'] * st); x[:, 0] *= k; x[:, 1] *= k
    x[:, 2] = x[:, 2] - q['topCut'] * st
    return x.reshape(p.shape)


OPERATORS = {'analytic-chest-waist-cap-rounding-v1': chest_waist_cap_rounding, 'analytic-thigh-upper-back-slim-top-dome-v1': thigh_upper_back_slim_top_dome}
# Only user-adopted parameter sets are replayable; anything else fails closed.
ADOPTED = {'analytic-chest-waist-cap-rounding-v1': ({'z0': 0.025, 'zEnd': -0.0615, 'depth': 0.095, 'frontDeg': 0.0, 'backDeg': 135.0, 'c': 0.95},),
           'analytic-thigh-upper-back-slim-top-dome-v1': ({'aMax': 0.016, 'z0': -0.065, 'z1': -0.02, 'c0': -0.45, 'rFull': 0.06, 'zc': -0.03, 'zt': 0.072, 'topCut': 0.055, 'rTop': 0.32},)}
PARTS = {'analytic-chest-waist-cap-rounding-v1': ('chest',), 'analytic-thigh-upper-back-slim-top-dome-v1': ('legl', 'legr')}
# literal-f32-decoded-glb: the archive is the decoded candidate GLB. native-f64: the archive is the f64 map of the parent archive.
AUTHORITY = {'analytic-chest-waist-cap-rounding-v1': 'literal-f32-decoded-glb', 'analytic-thigh-upper-back-slim-top-dome-v1': 'native-f64'}


def apply(kind, p, q):
    return OPERATORS[kind](p, q)


def jacobian(kind, p, q, h=1e-6):
    p = np.asarray(p, dtype=np.float64); J = np.empty(p.shape + (3,))
    for k in range(3):
        e = np.zeros(3); e[k] = h
        J[..., :, k] = (apply(kind, p + e, q) - apply(kind, p - e, q)) / (2 * h)
    return J


def transform_normals(kind, p, n, q):
    return transform(kind, p, n, None, q)[0]


def transform_tangents(kind, p, t, n_new, q):
    """Tangents for rows whose new normals are n_new (kept for callers that transform normals separately)."""
    J = jacobian(kind, p, q); v = np.einsum('...ij,...j->...i', J, t[..., :3]); nn = n_new / np.linalg.norm(n_new, axis=-1, keepdims=True)
    v = v - np.sum(v * nn, axis=-1, keepdims=True) * nn
    v = v / np.linalg.norm(v, axis=-1, keepdims=True) * np.linalg.norm(t[..., :3], axis=-1, keepdims=True)
    out = np.concatenate([v, t[..., 3:]], axis=-1); out[_identity(J)] = t[_identity(J)]
    return out


def _identity(J):
    return np.abs(J - np.eye(3)).max((-1, -2)) < 1e-8


def transform(kind, p, n, t, q):
    """Normals by inverse transpose, tangents by push-forward re-orthogonalized; lengths kept; identity rows keep authored values."""
    J = jacobian(kind, p, q); ident = _identity(J)
    m = np.einsum('...ij,...j->...i', np.linalg.inv(J).swapaxes(-1, -2), n)
    m = m / np.linalg.norm(m, axis=-1, keepdims=True) * np.linalg.norm(n, axis=-1, keepdims=True); m[ident] = n[ident]
    if t is None:
        return m, None
    nn = m / np.linalg.norm(m, axis=-1, keepdims=True); v = np.einsum('...ij,...j->...i', J, t[..., :3])
    v = v - np.sum(v * nn, axis=-1, keepdims=True) * nn
    v = v / np.linalg.norm(v, axis=-1, keepdims=True) * np.linalg.norm(t[..., :3], axis=-1, keepdims=True)
    out = np.concatenate([v, t[..., 3:]], axis=-1); out[ident] = t[ident]
    return m, out
