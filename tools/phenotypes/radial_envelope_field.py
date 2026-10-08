"""Cylindrical measurement and smooth radial scaling fields about a limb centre curve.

Convention: unit axis a, anterior reference u (+Y projected), w = u x a. Angle 0 = anterior,
+90 = w (for a = +Z, w = +X), +/-180 = posterior. The centre curve c(s) is the smoothed
midpoint of each slice's bounding box, so scaling is about the actual limb centre.
For any positive scale field f(s, theta), X' = c(s) + a s + f (X_perp - c(s)) keeps s and
theta per point and changes only radius, hence it is injective.
"""
import numpy as np


def frame(axis, anterior=(0., 1., 0.)):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    u = np.asarray(anterior, float) - a * np.dot(a, anterior); u /= np.linalg.norm(u)
    w = np.cross(u, a)
    return np.stack([u, w, a])


def gaussian_1d(sigma_bins):
    if sigma_bins <= 0:
        return np.array([1.0])
    r = int(np.ceil(3 * sigma_bins)); x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / sigma_bins) ** 2)
    return k / k.sum()


def smooth_grid(G, sigma_s_bins, sigma_t_bins, periodic_theta=True):
    """Gaussian smoothing of a (s, theta) grid; theta periodic."""
    out = G.copy()
    ks = gaussian_1d(sigma_s_bins)
    if len(ks) > 1:
        r = len(ks) // 2
        pad = np.pad(out, ((r, r), (0, 0)), mode='edge')
        out = np.stack([np.convolve(pad[:, j], ks, mode='valid') for j in range(out.shape[1])], axis=1)
    kt = gaussian_1d(sigma_t_bins)
    if len(kt) > 1:
        r = len(kt) // 2
        pad = np.pad(out, ((0, 0), (r, r)), mode='wrap' if periodic_theta else 'edge')
        out = np.stack([np.convolve(pad[i], kt, mode='valid') for i in range(out.shape[0])], axis=0)
    return out


class Cylinder:
    def __init__(self, origin, axis, points, s_min, s_max, step=0.005, centre_sigma=0.01):
        self.origin = np.asarray(origin, float)
        self.R = frame(axis)
        self.s_grid = np.arange(s_min, s_max + step / 2, step)
        self.step = step
        Y = (np.asarray(points, float) - self.origin) @ self.R.T
        centres = np.full((len(self.s_grid), 2), np.nan)
        for i, s in enumerate(self.s_grid):
            m = np.abs(Y[:, 2] - s) <= step / 2
            if m.sum() >= 8:
                centres[i] = (Y[m, :2].min(0) + Y[m, :2].max(0)) / 2
        good = ~np.isnan(centres[:, 0])
        if not good.any():
            raise RuntimeError('No geometry in the cylinder range')
        for k in range(2):
            centres[:, k] = np.interp(self.s_grid, self.s_grid[good], centres[good, k])
        sig = centre_sigma / step
        self.centre = np.stack([np.convolve(np.pad(centres[:, k], int(np.ceil(3 * sig)) if sig > 0 else 0, mode='edge'),
                                            gaussian_1d(sig), mode='valid') for k in range(2)], axis=1)

    def coords(self, X):
        Y = (np.asarray(X, float) - self.origin) @ self.R.T
        s = Y[:, 2]
        c = np.stack([np.interp(s, self.s_grid, self.centre[:, k]) for k in range(2)], axis=1)
        d = Y[:, :2] - c
        theta = np.degrees(np.arctan2(d[:, 1], d[:, 0]))
        r = np.hypot(d[:, 0], d[:, 1])
        return s, theta, r, c, Y

    def outer_profile(self, X, theta_step=10.0, min_count=1):
        """Max radius per (s bin, theta bin); NaN where empty."""
        s, th, r, _, _ = self.coords(X)
        thetas = np.arange(-180, 180, theta_step) + theta_step / 2
        G = np.full((len(self.s_grid), len(thetas)), np.nan)
        si = np.round((s - self.s_grid[0]) / self.step).astype(int)
        ti = np.floor((th + 180) / theta_step).astype(int) % len(thetas)
        ok = (si >= 0) & (si < len(self.s_grid))
        flat = si[ok] * len(thetas) + ti[ok]
        best = np.full(G.size, -np.inf)
        np.maximum.at(best, flat, r[ok])
        cnt = np.bincount(flat, minlength=G.size)
        best[cnt < min_count] = np.nan
        best[np.isinf(best)] = np.nan
        return best.reshape(G.shape), thetas

    def apply(self, X, F, thetas, s_values=None):
        """Scale radius by bilinear F(s, theta) (rows = self.s_grid unless s_values); F must be 1 at both s ends."""
        s_axis = self.s_grid if s_values is None else s_values
        s, th, r, c, Y = self.coords(X)
        tstep = thetas[1] - thetas[0]
        fs = (s - s_axis[0]) / (s_axis[1] - s_axis[0])
        inside = (fs >= 0) & (fs <= len(s_axis) - 1)
        i0 = np.clip(np.floor(fs).astype(int), 0, len(s_axis) - 2); ws = np.clip(fs - i0, 0, 1)
        ft = (th - thetas[0]) / tstep
        j0 = np.floor(ft).astype(int); wt = ft - j0
        j0 %= len(thetas); j1 = (j0 + 1) % len(thetas)
        val = ((1 - ws) * ((1 - wt) * F[i0, j0] + wt * F[i0, j1]) + ws * ((1 - wt) * F[i0 + 1, j0] + wt * F[i0 + 1, j1]))
        val[~inside] = 1.0
        newY = Y.copy()
        newY[:, :2] = c + (Y[:, :2] - c) * val[:, None]
        return newY @ self.R + self.origin, val


def fill_nan_rows(G, max_missing=1.0):
    """Fill NaN along theta by periodic interpolation per row (rows fully NaN stay NaN).
    Rows missing more than max_missing of their bins are left as measured (no invented geometry)."""
    out = G.copy()
    n = G.shape[1]
    for i in range(G.shape[0]):
        row = G[i]; good = ~np.isnan(row)
        if good.all() or not good.any() or (1 - good.mean()) > max_missing:
            continue
        x = np.arange(n); xp = np.concatenate([x[good] - n, x[good], x[good] + n]); fp = np.tile(row[good], 3)
        out[i] = np.interp(x, xp, fp)
    return out


def hermite(t, t0, v0, d0, t1, v1, d1):
    """Cubic Hermite on [t0, t1] with values and derivatives (per column)."""
    h = t1 - t0
    u = (t - t0) / h
    h00 = 2 * u ** 3 - 3 * u ** 2 + 1; h10 = u ** 3 - 2 * u ** 2 + u; h01 = -2 * u ** 3 + 3 * u ** 2; h11 = u ** 3 - u ** 2
    return h00 * v0 + h10 * h * d0 + h01 * v1 + h11 * h * d1


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
    return cosine_falloff(d, -1, half_full, -2, half_zero) if half_zero > half_full else (d <= half_full).astype(float)


def section(verts, faces, axis, value):
    """Intersection points of triangle edges with the plane coordinate[axis] == value."""
    t = verts[:, axis] - value
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = faces[:, i], faces[:, j]
        ta, tb = t[a], t[b]
        m = ta * tb < 0
        if m.any():
            w = (ta[m] / (ta[m] - tb[m]))[:, None]
            pts.append(verts[a[m]] + w * (verts[b[m]] - verts[a[m]]))
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def width_depth_profile(verts, faces, z_values):
    rows = []
    for z in z_values:
        p = section(verts, faces, 2, z)
        if len(p) < 3:
            rows.append(dict(z=float(z))); continue
        rows.append(dict(z=float(z), xMin=float(p[:, 0].min()), xMax=float(p[:, 0].max()), widthX=float(np.ptp(p[:, 0])),
                         yMin=float(p[:, 1].min()), yMax=float(p[:, 1].max()), depthY=float(np.ptp(p[:, 1]))))
    return rows


def surface_samples(V, F, count=300000, seed=11):
    """Deterministic area-weighted surface samples plus all vertices (for dense outer profiles)."""
    V = np.asarray(V, float); F = np.asarray(F)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(F), size=count, p=area / area.sum())
    r1, r2 = rng.random(count), rng.random(count)
    q = np.sqrt(r1)
    pts = (1 - q)[:, None] * a[idx] + (q * (1 - r2))[:, None] * b[idx] + (q * r2)[:, None] * c[idx]
    return np.concatenate([V, pts])
