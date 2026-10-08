"""Pure-numpy parts of the LEAN reduction (welding, topology, sampling, silhouettes, node split); no Blender."""
import numpy as np

from uv_atlas_raster import raster


def weld(P, F, U, N, M):
    """Weld corners by 1 um position; drop degenerate and duplicate faces (UV/normal/material stay per corner)."""
    q = np.round(P/1e-6).astype(np.int64)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True); inv = inv.ravel()
    Fw = inv[F]; ok = (Fw[:, 0] != Fw[:, 1]) & (Fw[:, 1] != Fw[:, 2]) & (Fw[:, 0] != Fw[:, 2])
    key = np.sort(Fw, 1); _, keep = np.unique(key, axis=0, return_index=True); dup = np.ones(len(F), bool); dup[keep] = False
    ok &= ~dup
    return P[first], Fw[ok], U[F[ok]], N[F[ok]], M[ok], int((~ok).sum())


def topo(Fw):
    """Open boundary edges and the count of non-manifold edges."""
    e = np.sort(np.concatenate([Fw[:, [0, 1]], Fw[:, [1, 2]], Fw[:, [2, 0]]]), 1)
    ue, cnt = np.unique(e, axis=0, return_counts=True)
    return ue[cnt == 1], int((cnt > 2).sum())


def sample(P, F, n, seed):
    rng = np.random.default_rng(seed); area = 0.5*np.linalg.norm(np.cross(P[F[:, 1]]-P[F[:, 0]], P[F[:, 2]]-P[F[:, 0]]), axis=1)
    f = rng.choice(len(F), n, p=area/area.sum()); r1 = np.sqrt(rng.random(n)); r2 = rng.random(n)
    b = np.stack([1-r1, r1*(1-r2), r1*r2], 1)
    return (P[F[f]]*b[:, :, None]).sum(1), f, b


def bary(P, F, fi, X):
    a, b_, c = P[F[fi, 0]], P[F[fi, 1]], P[F[fi, 2]]
    v0 = b_-a; v1 = c-a; v2 = X-a
    d00 = (v0*v0).sum(1); d01 = (v0*v1).sum(1); d11 = (v1*v1).sum(1); d20 = (v2*v0).sum(1); d21 = (v2*v1).sum(1)
    den = d00*d11-d01*d01; den[den == 0] = 1e-30
    v = (d11*d20-d01*d21)/den; w = (d00*d21-d01*d20)/den
    return np.clip(np.stack([1-v-w, v, w], 1), 0, 1)


def mask(V2, F, W, H):
    fid, _ = raster(V2, F, W, H); return fid >= 0


def silhouette_metrics(Ph, Fh, Pl, Fl, px_m=0.0005):
    """Three axis-aligned orthographic silhouettes: xor fraction and mean offset (xor area / parent perimeter) in mm."""
    lo = np.minimum(Ph.min(0), Pl.min(0))-4*px_m; hi = np.maximum(Ph.max(0), Pl.max(0))+4*px_m; res = {}
    for ax, (i, j) in {'x': (1, 2), 'y': (0, 2), 'z': (0, 1)}.items():
        W = int(np.ceil((hi[i]-lo[i])/px_m))+1; H = int(np.ceil((hi[j]-lo[j])/px_m))+1

        def proj(P): return np.stack([(P[:, i]-lo[i])/px_m, (hi[j]-P[:, j])/px_m], 1)
        mh = mask(proj(Ph), Fh, W, H); ml = mask(proj(Pl), Fl, W, H); xor = int((mh ^ ml).sum())
        edge = mh & ~(np.roll(mh, 1, 0) & np.roll(mh, -1, 0) & np.roll(mh, 1, 1) & np.roll(mh, -1, 1))
        res[ax] = {'xorFractionOfArea': xor/max(int(mh.sum()), 1), 'meanOffsetMm': xor/max(int(edge.sum()), 1)*px_m*1000}
    res['worstMeanOffsetMm'] = max(v['meanOffsetMm'] for k, v in res.items() if k in 'xyz')
    return res


def split_by_material(names, P, F, U, N, Mi):
    """Restore one node per material index: render vertices unique by (vertex, uv, normal)."""
    nodes = {}
    for m, name in enumerate(names):
        s = Mi == m
        if not s.any(): continue
        Fm = F[s]; Um = U[s]; Nm = N[s]
        key = np.concatenate([Fm.reshape(-1, 1).astype(np.float64), np.round(Um.reshape(-1, 2)*2**20), np.round(Nm.reshape(-1, 3)*2**16)], 1)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        nodes[name] = dict(position=P[Fm.reshape(-1)[first]].astype('f4'), uv=Um.reshape(-1, 2)[first].astype('f4'),
                           normal=Nm.reshape(-1, 3)[first].astype('f4'), faces=inv.ravel().reshape(-1, 3).astype('<u2'))
    return nodes
