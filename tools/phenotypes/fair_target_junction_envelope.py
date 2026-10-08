"""No-shelf junction taper: reshape one part's terminal so its outer envelope meets the partner part
with a continuous slope and then tucks inside it.

Axis t points from the junction pivot into the edited part X. Per theta column, with outer radii
rX(t), rY(t) about the shared centre curve of both parts:
  t >= tFar           : rX (unchanged)
  tCross <= t < tFar  : cubic Hermite from (tCross, rY, rY') to (tFar, rX, rX')  -> continuous slope, no lip
  t < tCross          : min(rX, rY - margin - tuck*(tCross - t))                   -> terminal tucked inside Y
The scale field E/rX is Gaussian-smoothed, optionally weighted by angle, and applied radially (injective).
The partner part is read-only. Only positions and transported normals/tangents of X change.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from descendant_mesh_edit import Mesh, Descendant, summary, require, sha, write_receipt, face_normals, preview_corners
from radial_envelope_field import Cylinder, fill_nan_rows, smooth_grid, hermite, angular_weight, surface_samples


def column_target(t, rX, rY, cfg):
    t_far, t_cross = cfg['tFar'], cfg['tCross']
    m, tuck = cfg['margin'], cfg['tuck']
    E = rX.copy()
    i_far = int(np.argmin(np.abs(t - t_far))); i_cross = int(np.argmin(np.abs(t - t_cross)))
    if np.isnan(rX[i_far]) or np.isnan(rY[i_cross]):
        return E
    d = t[1] - t[0]
    k = max(1, int(round(cfg.get('slopeWindow', 0.01) / d)))
    def one_sided(r, i, j):
        if j < 0 or j >= len(r) or np.isnan(r[i]) or np.isnan(r[j]):
            return 0.0
        return (r[j] - r[i]) / ((j - i) * d)
    # X slope from its untouched side (above tFar); Y slope from its shaft side (below tCross)
    dX = one_sided(rX, i_far, i_far + k)
    dY = one_sided(rY, i_cross, i_cross - k) * cfg.get('partnerSlopeFactor', 1.0)
    band = (t >= t[i_cross]) & (t < t[i_far])
    if not cfg.get('tuckOnly'):
        E[band] = hermite(t[band], t[i_cross], rY[i_cross] + cfg.get('crossOffset', 0.0), dY, t[i_far], rX[i_far], dX)
    below = t < t[i_cross]
    dd = t[i_cross] - t[below]
    blend = cfg.get('tuckBlend')
    if cfg.get('capLength'):
        # rounded terminal below the crossing instead of a long slide: no flap standing off the partner in bends
        off = cfg.get('crossOffset', 0.0); r0 = rY[i_cross] + off
        u = np.clip(dd / cfg['capLength'], 0, 1)
        limit = np.fmin(rY[below] - m * np.clip(dd / 0.004, 0, 1), r0 * np.sqrt(np.clip(1 - u * u, 0, 1)))
    elif blend:
        u = np.clip(dd / blend, 0, 1); off = cfg.get('crossOffset', 0.0)
        limit = rY[below] + off - (off + m) * u * u * (3 - 2 * u) - tuck * dd   # smooth slide under the partner, no step
    else:
        limit = rY[below] - m - tuck * dd
    E[below] = np.where(np.isnan(limit), rX[below], np.fmin(rX[below], limit))
    cover = cfg.get('coverPartnerMargin')
    if cover is not None:
        # X must stay outside the partner wherever both exist on X's side of the crossing (no poke-through),
        # then the raised envelope is relaxed so the cover itself has no kink
        on = (t >= t[i_cross]) & ~np.isnan(rY) & ~np.isnan(E)
        for _ in range(3):
            E[on] = np.fmax(E[on], rY[on] + cover)
            k = np.array([0.25, 0.5, 0.25]); seg = np.flatnonzero(t >= t[i_cross])
            if len(seg) > 2:
                vals = E[seg].copy(); good = ~np.isnan(vals)
                sm = vals.copy(); sm[1:-1] = np.where(good[1:-1] & good[:-2] & good[2:], np.convolve(np.nan_to_num(vals), k, mode='same')[1:-1], vals[1:-1])
                E[seg] = np.fmax(sm, vals)
    return E


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh descendant directory required')
    cfg = json.loads(a.config.read_text())
    master = Path(cfg['master']); require(sha(master) == cfg['masterSha256'], 'Parent changed')
    partner = Path(cfg['partner']['master']); require(sha(partner) == cfg['partner']['sha256'], 'Partner changed')
    mesh = Mesh(master)
    # partner = published native geometry (preview corner soup in part-local NWN coordinates), read-only
    if cfg['partner'].get('kind', 'preview') == 'master':
        pm = Mesh(partner)
        Yp = surface_samples(pm.U + np.asarray(cfg['partner']['offset'], float), pm.F, cfg.get('samples', 400000))
    else:
        pc = preview_corners(partner)[0].reshape(-1, 3) + np.asarray(cfg['partner']['offset'], float)
        Yp = surface_samples(pc, np.arange(len(pc)).reshape(-1, 3), cfg.get('samples', 400000))
    Xs = surface_samples(mesh.U, mesh.F, cfg.get('samples', 400000))
    origin = np.asarray(cfg['origin'], float); axis = np.asarray(cfg['axis'], float)
    both = np.concatenate([Xs, Yp])
    cyl = Cylinder(origin, axis, both, *cfg['tRange'], step=cfg.get('step', 0.0025), centre_sigma=cfg.get('centreSigma', 0.01))
    ts = cfg.get('thetaStep', 10)
    rX, thetas = cyl.outer_profile(Xs, ts)
    rY, _ = cyl.outer_profile(Yp, ts)
    rX = fill_nan_rows(rX); rY = fill_nan_rows(rY, cfg.get('partnerFillMaxMissing', 1.0))
    t = cyl.s_grid
    E = np.stack([column_target(t, rX[:, j], rY[:, j], cfg) for j in range(len(thetas))], axis=1)
    F = np.where(np.isnan(rX) | np.isnan(E), 1.0, E / np.where(np.isnan(rX), 1, rX))
    F = np.clip(F, cfg.get('minScale', 0.6), cfg.get('maxScale', 1.25))
    F = smooth_grid(F, cfg.get('sigmaS', 0.004) / cyl.step, cfg.get('sigmaTheta', 15) / ts)
    if cfg.get('angular'):
        w = angular_weight(thetas, cfg['angular']['centre'], cfg['angular']['halfFull'], cfg['angular']['halfZero'])
        F = 1 + (F - 1) * w[None, :]
    F[t >= cfg['tFar'] + cfg.get('farGuard', 0.01)] = 1.0
    F = np.where(np.abs(F - 1) < 1e-5, 1.0, F)  # exact identity outside the measurable edit
    newU, scale = cyl.apply(mesh.U, F, thetas)
    fn0 = face_normals(mesh.U, mesh.F); fn1 = face_normals(newU, mesh.F)
    cosang = np.sum(fn0 * fn1, 1) / np.maximum(np.linalg.norm(fn0, axis=1) * np.linalg.norm(fn1, axis=1), 1e-30)
    area_ratio = np.linalg.norm(fn1, axis=1) / np.maximum(np.linalg.norm(fn0, axis=1), 1e-30)
    require(cosang.min() > 0.0 and area_ratio.min() > 0.1, 'Inverted or collapsed triangles')
    desc = Descendant(mesh); desc.U = newU
    a.output.mkdir(parents=True)
    out = a.output / (cfg.get('name', 'junction') + '-local.glb')
    desc.write(out)
    rX2, _ = cyl.outer_profile(surface_samples(newU, mesh.F, cfg.get('samples', 400000)), ts)
    sectors = list(range(0, len(thetas), max(1, len(thetas) // 8)))
    table = [dict(t=float(tv), **{('theta%+d' % thetas[j]): [None if np.isnan(rX[i, j]) else round(float(rX[i, j]), 4),
                                                              None if np.isnan(rX2[i, j]) else round(float(rX2[i, j]), 4),
                                                              None if np.isnan(rY[i, j]) else round(float(rY[i, j]), 4)] for j in sectors})
             for i, tv in enumerate(t) if cfg['tRange'][0] <= tv <= cfg['tFar'] + 0.02]
    # no-shelf metric: max outward radial step of the visible envelope max(rX', rY) between consecutive t samples
    env0 = np.fmax(rX, rY); env1 = np.fmax(rX2, rY)
    def worst_step(env):
        dd = np.diff(env, axis=0)
        dd = dd[~np.isnan(dd)]
        return float(np.abs(dd).max()) if len(dd) else None
    both = (t >= cfg['tCross'])[:, None] & ~np.isnan(rX2) & ~np.isnan(rY)
    if cfg.get('angular'):
        both &= (angular_weight(thetas, cfg['angular']['centre'], cfg['angular']['halfFull'], cfg['angular']['halfZero']) > 0.99)[None, :]
    clearance = (rX2 - rY)[both]
    record = dict(schemaVersion=1, kind='junction-envelope-descendant', part=cfg['part'], partner=cfg['partner'],
                  parent={'path': str(master), 'sha256': sha(master)}, descendant={'path': str(out), 'sha256': sha(out)},
                  config=cfg, configSha256=sha(a.config), helperSha256=sha(__file__), summary=summary(desc, cfg.get('name')),
                  scaleRange=[float(scale.min()), float(scale.max())], minFaceNormalCos=float(cosang.min()), minAreaRatio=float(area_ratio.min()),
                  coverClearanceAboveCrossMeters={'min': float(clearance.min()) if len(clearance) else None,
                                                   'p1': float(np.percentile(clearance, 1)) if len(clearance) else None,
                                                   'binsBelowZero': int((clearance < 0).sum()), 'bins': int(len(clearance))},
                  visibleEnvelopeMaxStepPerSampleMeters={'before': worst_step(env0), 'after': worst_step(env1), 'sampleMeters': cyl.step},
                  profileTable_rXbefore_rXafter_rY=table,
                  policy='Positions/transported normals and tangents only; partner read-only; UV/index/map/material exact; no approval implied.')
    write_receipt(a.output / 'descendant.json', record)
    shutil.copy2(__file__, a.output / 'executed-helper.py'); shutil.copy2(a.config, a.output / 'executed-config.json')
    print(json.dumps({'output': str(out), 'scale': record['scaleRange'], 'step': record['visibleEnvelopeMaxStepPerSampleMeters'],
                      'moved': record['summary']['movedVerticesOver0p1um'], 'cover': record['coverClearanceAboveCrossMeters'], 'maxDisp': record['summary']['maxDisplacementMeters']}))


if __name__ == '__main__':
    main()
