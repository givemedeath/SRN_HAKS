"""Female limb crease fairing on welded native corner geometry (positions only; pure functions).

Female-specific copy of the male crease-band method (valley-only anisotropic radial averaging, tangent-plane
relaxation and local fold repair inside a measured (s, theta) band about the limb centre curve). Band weight is an
angular cosine window times an axial cosine window, so vertices outside the band (joint ends, connectors, the front
of the limb) stay bit-exact. Muscle bellies are kept because only valleys are filled. Normals/tangents are not
handled here; the bounded descendant representation declares and verifies their rule separately.
Part-local NWN working frame: limb axis +z, theta 0 = anterior (+y), +/-180 = posterior.
"""
import numpy as np


WELD_QUANTUM = 1e-9


def weld(corners, quantum=WELD_QUANTUM):
    """Weld (T, 3, 3) corner positions on a 1e-9 m grid (near-duplicate dense-source splits join); the partition must
    agree with a half-cell-offset grid. Returns representative vertices U (first corner of each class) and faces F."""
    flat = np.ascontiguousarray(np.asarray(corners, np.float64).reshape(-1, 3))
    key = np.round(flat / quantum).astype(np.int64); alt = np.round(flat / quantum + 0.5).astype(np.int64)
    _, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True); inverse = inverse.reshape(-1)
    _, inv2 = np.unique(alt, axis=0, return_inverse=True); inv2 = inv2.reshape(-1)
    pairs = np.unique(np.stack([inverse, inv2], 1), axis=0)
    if len(pairs) != len(first) or len(np.unique(pairs[:, 1])) != len(first):
        raise ValueError('Ambiguous weld: near-duplicate vertices straddle the weld grid')
    return flat[first], inverse.reshape(-1, 3)


def child_corners(P0, U, X, F):
    """Corner positions of a welded edit: moved classes take X, unmoved corners keep their exact parent bits."""
    moved = np.any(X != U, axis=1)
    return np.where(moved[F][..., None], X[F], np.asarray(P0, np.float64))


def cosine_falloff(x, full_lo, full_hi, zero_lo, zero_hi):
    """1 on [full_lo, full_hi], cosine to 0 at zero_lo (< full_lo) and zero_hi (> full_hi)."""
    x = np.asarray(x, float); out = np.zeros_like(x)
    out[(x >= full_lo) & (x <= full_hi)] = 1
    m = (x > zero_lo) & (x < full_lo)
    out[m] = 0.5 * (1 - np.cos(np.pi * (x[m] - zero_lo) / (full_lo - zero_lo)))
    m = (x > full_hi) & (x < zero_hi)
    out[m] = 0.5 * (1 + np.cos(np.pi * (x[m] - full_hi) / (zero_hi - full_hi)))
    return out


def angular_weight(theta, centre, half_full, half_zero):
    d = np.abs((np.asarray(theta, float) - centre + 180) % 360 - 180)
    return cosine_falloff(d, -1, half_full, -2, half_zero)


class Cylinder:
    """Limb centre curve c(s): smoothed bounding-box midpoints of axial slices; theta 0 = +y (anterior)."""

    def __init__(self, points, s_min, s_max, step=0.005, centre_sigma=0.01):
        Y = np.asarray(points, float)
        self.s_grid = np.arange(s_min, s_max + step / 2, step); self.step = step
        centres = np.full((len(self.s_grid), 2), np.nan)
        for i, s in enumerate(self.s_grid):
            m = np.abs(Y[:, 2] - s) <= step / 2
            if m.sum() >= 8:
                centres[i] = (Y[m, :2].min(0) + Y[m, :2].max(0)) / 2
        good = ~np.isnan(centres[:, 0])
        if not good.any():
            raise ValueError('No geometry in the cylinder range')
        for k in range(2):
            centres[:, k] = np.interp(self.s_grid, self.s_grid[good], centres[good, k])
        sig = centre_sigma / step; r = int(np.ceil(3 * sig)); x = np.arange(-r, r + 1); g = np.exp(-0.5 * (x / sig) ** 2); g /= g.sum()
        self.centre = np.stack([np.convolve(np.pad(centres[:, k], r, mode='edge'), g, mode='valid') for k in range(2)], axis=1)

    def coords(self, X):
        Y = np.asarray(X, float); s = Y[:, 2]
        c = np.stack([np.interp(s, self.s_grid, self.centre[:, k]) for k in range(2)], axis=1)
        d = Y[:, :2] - c
        theta = np.degrees(np.arctan2(d[:, 0], d[:, 1]))  # 0 = +y anterior, +90 = +x, 180 = posterior
        return s, theta, np.hypot(d[:, 0], d[:, 1]), c, Y


def band_weights(cyl, U, band):
    s, th, _, _, _ = cyl.coords(U)
    return angular_weight(th, band['thetaCentre'], band['thetaHalfFull'], band['thetaHalfZero']) * cosine_falloff(s, *band['sFull'], *band['sZero'])


def face_normals(U, F):
    return np.cross(U[F[:, 1]] - U[F[:, 0]], U[F[:, 2]] - U[F[:, 0]])


def edges(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    return np.unique(e, axis=0, return_counts=True)


def neighbours(F, count):
    ue, _ = edges(F)
    a = np.concatenate([ue[:, 0], ue[:, 1]]); b = np.concatenate([ue[:, 1], ue[:, 0]])
    order = np.argsort(a, kind='stable'); a = a[order]; b = b[order]
    return np.searchsorted(a, np.arange(count + 1)), b


def vertex_normals(U, F):
    acc = np.zeros_like(U); fn = face_normals(U, F)
    for k in range(3):
        np.add.at(acc, F[:, k], fn)
    return acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-30)[:, None]


def fold_angles(U, F):
    """Unsigned dihedral (degrees) and endpoint ids of every interior manifold edge."""
    fn = face_normals(U, F); fn = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); fid = np.tile(np.arange(len(F)), 3)
    e.sort(1); order = np.lexsort((e[:, 1], e[:, 0])); e = e[order]; fid = fid[order]
    i = np.flatnonzero(np.all(e[1:] == e[:-1], axis=1))
    ang = np.degrees(np.arccos(np.clip(np.sum(fn[fid[i]] * fn[fid[i + 1]], 1), -1, 1)))
    return ang, e[i]


def stats(a):
    a = np.asarray(a, float)
    if not len(a):
        return None
    return dict(edges=int(len(a)), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), p99=float(np.percentile(a, 99)),
                max=float(a.max()), over30=int((a > 30).sum()), over15=int((a > 15).sum()))


def band_fold_stats(U, F, w):
    ang, e = fold_angles(U, F); full = (w[e[:, 0]] >= .99) & (w[e[:, 1]] >= .99)
    return stats(ang[full])


def radial_fair(cyl, X, w, sigma_s, sigma_arc):
    """Valley-only: each weighted vertex radius -> max(r, anisotropic Gaussian (s, arc) average of radii)."""
    s, th, r, c, Y = cyl.coords(X)
    m = np.flatnonzero(w > 0); r_ref = float(np.median(r[m]))
    order = np.argsort(s); ss = s[order]; target = r.copy()
    for k in range(0, len(m), 512):
        q = m[k:k + 512]
        lo = np.searchsorted(ss, s[q].min() - 3 * sigma_s); hi = np.searchsorted(ss, s[q].max() + 3 * sigma_s); cand = order[lo:hi]
        ds = (s[q][:, None] - s[cand][None, :]) / sigma_s
        dt = ((th[q][:, None] - th[cand][None, :] + 180) % 360 - 180) * np.pi / 180 * r_ref / sigma_arc
        kern = np.exp(-0.5 * (ds ** 2 + dt ** 2)); kern[(np.abs(ds) > 3) | (np.abs(dt) > 3)] = 0
        target[q] = (kern @ r[cand]) / np.maximum(kern.sum(1), 1e-12)
    newr = r + w * np.maximum(target - r, 0)
    scale = np.where(r > 1e-9, newr / np.maximum(r, 1e-9), 1.0)
    out = Y.copy(); out[:, :2] = c + (Y[:, :2] - c) * scale[:, None]
    return out


def tangential_relax(X, F, w, iterations, lam=0.5):
    start, nb = neighbours(F, len(X)); deg = np.diff(start); rows = np.repeat(np.arange(len(X)), deg)
    for _ in range(iterations):
        mean = np.zeros_like(X); np.add.at(mean, rows, X[nb])
        L = mean / np.maximum(deg, 1)[:, None] - X; L[deg == 0] = 0
        n = vertex_normals(X, F); L -= n * np.sum(L * n, axis=1)[:, None]
        X = X + lam * w[:, None] * L
    return X


def radial_alignment(cyl, X, F):
    fn = face_normals(X, F); cen = X[F].mean(1); _, _, _, c, Y = cyl.coords(cen)
    radial = np.c_[Y[:, :2] - c, np.zeros(len(c))]
    return np.sum(fn * radial, 1) / (np.linalg.norm(fn, axis=1) * np.linalg.norm(radial, axis=1) + 1e-30)


def fold_repair(cyl, X, F, w, threshold=0.2, rings=2, max_rounds=50, max_fold=None):
    """Umbrella smoothing restricted to rings around band faces turning inward or folding sharply."""
    start, nb = neighbours(F, len(X)); deg = np.diff(start); rows = np.repeat(np.arange(len(X)), deg)
    for k in range(max_rounds):
        bad = (radial_alignment(cyl, X, F) < threshold) & (w[F] > 0).all(1)
        sel = np.zeros(len(X), bool); sel[np.unique(F[bad])] = True
        if max_fold is not None:
            ang, e = fold_angles(X, F)
            sel[np.unique(e[(ang > max_fold) & (w[e[:, 0]] > 0.5) & (w[e[:, 1]] > 0.5)])] = True
        if not sel.any():
            return X, k
        for _ in range(rings):
            grow = sel.copy(); grow[nb[sel[rows]]] = True; sel = grow
        sel &= w > 0
        for _ in range(5):
            mean = np.zeros_like(X); np.add.at(mean, rows, X[nb])
            X = X + 0.5 * sel[:, None] * (mean / np.maximum(deg, 1)[:, None] - X)
    return X, max_rounds


def inverted_faces(X, F):
    """Faces whose orientation opposes their own corners' area-weighted vertex normals (local inversion)."""
    fn = face_normals(X, F); vn = vertex_normals(X, F)
    return np.einsum('ij,ij->i', fn, vn[F].sum(1)) <= 0


def flip_repair(U, X, F, w, min_area_ratio=0.02, rounds=40):
    """Pull vertices of newly inverted or collapsed faces back toward the parent (monotone blend) until no face
    is locally inverted beyond the parent's own inversions and every face keeps min_area_ratio of its area."""
    a0 = np.linalg.norm(face_normals(U, F), axis=1); base = inverted_faces(U, F); t = np.ones(len(U))
    for k in range(rounds):
        Y = U + t[:, None] * (X - U)
        bad = (inverted_faces(Y, F) & ~base) | (np.linalg.norm(face_normals(Y, F), axis=1) < min_area_ratio * a0)
        if not bad.any():
            return Y, k
        t[np.unique(F[bad])] *= 0.7
    return U + t[:, None] * (X - U), rounds


def fair(U, F, cfg):
    """Return faired welded positions (exact outside w > 0), band weights and a fold-angle history."""
    cyl = Cylinder(U, *cfg['sRange'], step=cfg.get('step', 0.005))
    w = band_weights(cyl, U, cfg['band'])
    X = U.copy(); history = [dict(stage='parent', **band_fold_stats(U, F, w))]
    for _ in range(cfg['radialPasses']):
        X = radial_fair(cyl, X, w, cfg['sigmaS'], cfg['sigmaArc'])
        X = tangential_relax(X, F, w, cfg['tangentialIterations'])
    X, rounds = fold_repair(cyl, X, F, w, max_fold=cfg['repairFoldAbove'])
    X = np.where((w > 0)[:, None], X, U)
    X, flips = flip_repair(U, X, F, w, cfg.get('minAreaRatio', 0.02))
    history.append(dict(stage='faired', foldRepairRounds=rounds, flipRepairRounds=flips, **band_fold_stats(X, F, w)))
    return X, w, history
