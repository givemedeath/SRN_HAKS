"""Weighted Taubin fairing of a measured crease band on a limb master descendant.

Weight w(theta, s) = angular cosine window x axial cosine window (part-local cylinder about the
limb centre curve); w = 0 outside, so joint rings and all other anatomy stay exact. Iterates
lambda/mu passes until the fold targets inside the full-weight band are met or the iteration
budget ends. Only positions and transported normals/tangents change.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from descendant_mesh_edit import Mesh, Descendant, summary, require, sha, write_receipt, laplacian_smooth, face_normals
from radial_envelope_field import Cylinder, cosine_falloff, angular_weight


def fold_angles(U, F):
    """Unsigned dihedral (degrees) and endpoint ids for every interior manifold edge."""
    fn = face_normals(U, F)
    fn = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-30)[:, None]
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); fid = np.tile(np.arange(len(F)), 3)
    e.sort(1)
    order = np.lexsort((e[:, 1], e[:, 0])); e = e[order]; fid = fid[order]
    same = np.all(e[1:] == e[:-1], axis=1)
    i = np.flatnonzero(same)
    ang = np.degrees(np.arccos(np.clip(np.sum(fn[fid[i]] * fn[fid[i + 1]], 1), -1, 1)))
    return ang, e[i]


def stats(a):
    if not len(a):
        return None
    return dict(edges=int(len(a)), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), p99=float(np.percentile(a, 99)),
                max=float(a.max()), over30=int((a > 30).sum()), over15=int((a > 15).sum()))


def radial_fair(cyl, X, w, sigma_s, sigma_arc, valley_only=False):
    """Radius of each weighted vertex -> Gaussian average of vertex radii in (s, arc) space (anisotropic)."""
    s, th, r, c, Y = cyl.coords(X)
    m = np.flatnonzero(w > 0)
    r_ref = float(np.median(r[m]))
    order = np.argsort(s); ss = s[order]
    target = r.copy()
    for k in range(0, len(m), 512):
        q = m[k:k + 512]
        lo = np.searchsorted(ss, s[q].min() - 3 * sigma_s); hi = np.searchsorted(ss, s[q].max() + 3 * sigma_s)
        cand = order[lo:hi]
        ds = (s[q][:, None] - s[cand][None, :]) / sigma_s
        dt = ((th[q][:, None] - th[cand][None, :] + 180) % 360 - 180) * np.pi / 180 * r_ref / sigma_arc
        kern = np.exp(-0.5 * (ds ** 2 + dt ** 2)); kern[(np.abs(ds) > 3) | (np.abs(dt) > 3)] = 0
        target[q] = (kern @ r[cand]) / np.maximum(kern.sum(1), 1e-12)
    delta = target - r
    if valley_only:
        delta = np.maximum(delta, 0)  # fill grooves only; ridges (muscle bellies) are kept
    newr = r + w * delta
    newY = Y.copy(); scale = np.where(r > 1e-9, newr / np.maximum(r, 1e-9), 1.0)
    newY[:, :2] = c + (Y[:, :2] - c) * scale[:, None]
    return newY @ cyl.R + cyl.origin


def tangential_relax(X, F, w, iterations, lam=0.5):
    """Umbrella Laplacian projected on the tangent plane (untangles folds without changing the surface much)."""
    from descendant_mesh_edit import neighbours, vertex_normals
    start, nb = neighbours(F, len(X)); deg = np.diff(start); rows = np.repeat(np.arange(len(X)), deg)
    for _ in range(iterations):
        mean = np.zeros_like(X); np.add.at(mean, rows, X[nb])
        L = mean / np.maximum(deg, 1)[:, None] - X; L[deg == 0] = 0
        n = vertex_normals(X, F)
        L -= n * np.sum(L * n, axis=1)[:, None]
        X = X + lam * w[:, None] * L
    return X


def radial_alignment(cyl, X, F):
    fn = face_normals(X, F); cen = X[F].mean(1); _, _, _, c, Y = cyl.coords(cen)
    radial = np.c_[Y[:, :2] - c, np.zeros(len(c))] @ cyl.R
    return np.sum(fn * radial, 1) / (np.linalg.norm(fn, axis=1) * np.linalg.norm(radial, axis=1) + 1e-30)


def fold_repair(cyl, X, F, w, threshold=0.2, rings=2, max_rounds=50, max_fold=None):
    """Full umbrella smoothing restricted to the rings around band faces whose normal turns inward."""
    from descendant_mesh_edit import neighbours
    start, nb = neighbours(F, len(X)); deg = np.diff(start); rows = np.repeat(np.arange(len(X)), deg)
    for k in range(max_rounds):
        d = radial_alignment(cyl, X, F)
        bad = (d < threshold) & (w[F] > 0).all(1)
        sel = np.zeros(len(X), bool); sel[np.unique(F[bad])] = True
        if max_fold is not None:
            ang, e = fold_angles(X, F)
            sharp = (ang > max_fold) & (w[e[:, 0]] > 0.5) & (w[e[:, 1]] > 0.5)
            sel[np.unique(e[sharp])] = True
        if not sel.any():
            return X, k
        for _ in range(rings):
            grow = sel.copy(); grow[nb[sel[rows]]] = True; sel = grow
        sel &= w > 0
        for _ in range(5):
            mean = np.zeros_like(X); np.add.at(mean, rows, X[nb])
            L = mean / np.maximum(deg, 1)[:, None] - X
            X = X + 0.5 * sel[:, None] * L
    return X, max_rounds


def weights(cyl, U, cfg):
    s, th, r, _, _ = cyl.coords(U)
    wt = angular_weight(th, cfg['thetaCentre'], cfg['thetaHalfFull'], cfg['thetaHalfZero'])
    lo, hi = cfg['sFull']; zlo, zhi = cfg['sZero']
    ws = cosine_falloff(s, lo, hi, zlo, zhi)
    return wt * ws


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh descendant directory required')
    cfg = json.loads(a.config.read_text())
    master = Path(cfg['master']); require(sha(master) == cfg['masterSha256'], 'Parent changed')
    mesh = Mesh(master)
    cyl = Cylinder(cfg.get('origin', [0, 0, 0]), cfg.get('axis', [0, 0, 1]), mesh.U, *cfg['sRange'], step=0.005)
    w = weights(cyl, mesh.U, cfg)
    ang0, e = fold_angles(mesh.U, mesh.F)
    full = (w[e[:, 0]] >= 0.99) & (w[e[:, 1]] >= 0.99)
    target_p95, target_max = cfg.get('targetP95', 10.0), cfg.get('targetMax', 30.0)
    X = mesh.U.copy(); done = 0; history = []
    step = cfg.get('iterationsPerCheck', 10)
    passes = 0
    if cfg.get('method', 'taubin') == 'radial':
        for _ in range(cfg.get('radialPasses', 2)):
            X = radial_fair(cyl, X, w, cfg.get('sigmaS', 0.003), cfg.get('sigmaArc', 0.006), cfg.get('valleyOnly', False)); passes += 1
            X = tangential_relax(X, mesh.F, w, cfg.get('tangentialIterations', 10))
        X, repair_rounds = fold_repair(cyl, X, mesh.F, w, max_fold=cfg.get('repairFoldAbove', 28.0))
        ang, _ = fold_angles(X, mesh.F); st = stats(ang[full])
        history.append(dict(radialPasses=passes, foldRepairRounds=repair_rounds, p95=st['p95'], max=st['max']))
    while done < cfg.get('maxIterations', 400) and not (history and history[-1]['p95'] <= target_p95 and history[-1]['max'] <= target_max):
        X = laplacian_smooth(X, mesh.F, w, step, cfg.get('lambda', 0.5), cfg.get('mu', -0.53), cfg.get('normalOnly', True))
        done += step
        ang, _ = fold_angles(X, mesh.F)
        st = stats(ang[full]); history.append(dict(iterations=done, p95=st['p95'], max=st['max']))
        if st['p95'] <= target_p95 and st['max'] <= target_max:
            break
    desc = Descendant(mesh); desc.U = X
    fn0 = face_normals(mesh.U, mesh.F); fn1 = face_normals(X, mesh.F)
    area_ratio = np.linalg.norm(fn1, axis=1) / np.maximum(np.linalg.norm(fn0, axis=1), 1e-30)
    inward = radial_alignment(cyl, X, mesh.F); band_faces = (w[mesh.F] > 0).all(1)
    inward0 = radial_alignment(cyl, mesh.U, mesh.F)
    a.output.mkdir(parents=True)
    out = a.output / (cfg.get('name', 'faired') + '-local.glb')
    desc.write(out)
    ang1, _ = fold_angles(X, mesh.F)
    band_any = (w[e[:, 0]] > 0) | (w[e[:, 1]] > 0)
    s0, th0, r0, _, _ = cyl.coords(mesh.U); s1, th1, r1, _, _ = cyl.coords(X)
    moved = w > 0
    record = dict(schemaVersion=1, kind='crease-band-descendant', part=cfg['part'], parent={'path': str(master), 'sha256': sha(master)},
                  descendant={'path': str(out), 'sha256': sha(out)}, config=cfg, configSha256=sha(a.config), helperSha256=sha(__file__),
                  iterations=done, history=history, targetsMet=bool(history[-1]['p95'] <= target_p95 and history[-1]['max'] <= target_max),
                  foldFullBand={'before': stats(ang0[full]), 'after': stats(ang1[full])},
                  foldWholeWeightedBand={'before': stats(ang0[band_any]), 'after': stats(ang1[band_any])},
                  foldWholePart={'before': stats(ang0), 'after': stats(ang1)},
                  radialChangeInBandMeters={'mean': float((r1 - r0)[moved].mean()), 'min': float((r1 - r0)[moved].min()), 'max': float((r1 - r0)[moved].max())},
                  summary=summary(desc, cfg.get('name')), minAreaRatio=float(area_ratio.min()),
                  facesBelow5PercentArea=int((area_ratio < 0.05).sum()),
                  inwardFacingBandFaces={'before': int(((inward0 < 0) & band_faces).sum()), 'after': int(((inward < 0) & band_faces).sum())},
                  policy='Positions/transported normals and tangents only; outside-band vertices exact; no approval implied.')
    write_receipt(a.output / 'descendant.json', record)
    shutil.copy2(__file__, a.output / 'executed-helper.py'); shutil.copy2(a.config, a.output / 'executed-config.json')
    print(json.dumps({'output': str(out), 'iterations': done, 'full': record['foldFullBand'], 'radial': record['radialChangeInBandMeters']}))


if __name__ == '__main__':
    main()
