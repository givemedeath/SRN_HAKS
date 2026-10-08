"""Two-part no-shelf junction: reshape both parts' terminals onto ONE shared envelope.

Axis t runs (world bind frame) from the low part into the high part. Per theta column the shared
envelope E(t) is a cubic Hermite from the low part's untouched profile at tLowRef (value + one-sided
slope) to the high part's untouched profile at tHighRef. Targets:
  high part: t >= tSeam -> E + coverOffset ; t < tSeam -> min(r_high, E - margin - tuck*(tSeam - t))  (tucked)
  low part : t <= tSeam -> E               ; t > tSeam -> min(r_low,  E - margin - tuck*(t - tSeam))  (tucked)
so the visible surface is one continuous slope with the seam at tSeam, without a lip or second shoulder,
and each terminal cap hides inside its partner. Scale fields target/r are Gaussian-smoothed and applied
radially about the shared centre curve (injective); only positions and transported normals/tangents change.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from descendant_mesh_edit import Mesh, Descendant, summary, require, sha, write_receipt, face_normals
from radial_envelope_field import Cylinder, fill_nan_rows, smooth_grid, hermite, angular_weight, surface_samples


def shared_targets(t, r_low, r_high, cfg):
    lo_ref, hi_ref, seam = cfg['tLowRef'], cfg['tHighRef'], cfg['tSeam']
    m, tuck = cfg['margin'], cfg['tuck']
    d = t[1] - t[0]; k = max(1, int(round(cfg.get('slopeWindow', 0.01) / d)))
    il = int(np.argmin(np.abs(t - lo_ref))); ih = int(np.argmin(np.abs(t - hi_ref)))
    TL, TH = r_low.copy(), r_high.copy()
    if np.isnan(r_low[il]) or np.isnan(r_high[ih]) or il - k < 0 or ih + k >= len(t):
        return TL, TH, np.full_like(t, np.nan)
    s_low = (r_low[il] - r_low[il - k]) / (k * d) if not np.isnan(r_low[il - k]) else 0.0
    s_high = (r_high[ih + k] - r_high[ih]) / (k * d) if not np.isnan(r_high[ih + k]) else 0.0
    s_low *= cfg.get('slopeFactor', 1.0); s_high *= cfg.get('slopeFactor', 1.0)
    E = np.full_like(t, np.nan)
    band = (t >= t[il]) & (t <= t[ih])
    E[band] = hermite(t[band], t[il], r_low[il], s_low, t[ih], r_high[ih], s_high)
    cover = cfg.get('coverOffset', 0.0003); blend = cfg.get('tuckBlend', 0.008)
    def ramp(x):
        u = np.clip(x / blend, 0, 1); return u * u * (3 - 2 * u)
    # weights: full correction on a plateau next to the seam, cosine back to the untouched profile at the refs
    ph, pl = cfg.get('plateauHigh', 0.02), cfg.get('plateauLow', 0.02)
    wH = np.clip(np.where(t <= seam + ph, 1.0, 0.5 * (1 + np.cos(np.pi * np.clip((t - seam - ph) / max(hi_ref - seam - ph, 1e-9), 0, 1)))), 0, 1)
    wL = np.clip(np.where(t >= seam - pl, 1.0, 0.5 * (1 + np.cos(np.pi * np.clip((seam - pl - t) / max(seam - pl - lo_ref, 1e-9), 0, 1)))), 0, 1)
    ov = cfg.get('overlap', 0.0)  # both parts sit on the envelope over [seam - ov, seam + ov]: no groove at the seam
    hs = band & (t >= seam - ov); hb = band & (t < seam - ov)
    TH[hs] = r_high[hs] + (E[hs] + cover - r_high[hs]) * wH[hs]
    d = seam - ov - t[hb]
    cap = cfg.get('highCapLength')
    if cap:
        # rounded (quarter-ellipse) terminal below the seam: no squared edge to cut through the partner when the joint bends
        i0 = int(np.argmin(np.abs(t - (seam - ov))))
        r0 = E[i0] + cover if not np.isnan(E[i0]) else np.nan
        TH[hb] = np.fmin(r_high[hb], r0 * np.sqrt(np.clip(1 - (d / cap) ** 2, 0, 1)) - m * ramp(d))
    else:
        TH[hb] = np.fmin(r_high[hb], E[hb] + cover - (cover + m) * ramp(d) - tuck * d)   # smooth slide inside the low part
    grow = cfg.get('highMaxGrow')
    if grow is not None:  # keep the high terminal near its original volume (its bend behaviour); the low part carries the envelope
        TH[band] = np.fmin(TH[band], r_high[band] + grow)
    ls = band & (t <= seam + ov); la = band & (t > seam + ov)
    TL[ls] = r_low[ls] + (E[ls] - r_low[ls]) * wL[ls]
    d = t[la] - seam - ov
    TL[la] = np.fmin(r_low[la], E[la] - m * ramp(d) - tuck * d)
    return TL, TH, E


def scale_field(r, target, cyl, cfg, lo, hi, thetas):
    F = np.where(np.isnan(r) | np.isnan(target), 1.0, target / np.where(np.isnan(r), 1, r))
    F = np.clip(F, cfg.get('minScale', 0.6), cfg.get('maxScale', 1.6))
    F = smooth_grid(F, cfg.get('sigmaS', 0.003) / cyl.step, cfg.get('sigmaTheta', 12) / cfg.get('thetaStep', 10))
    if cfg.get('angular'):
        w = angular_weight(thetas, cfg['angular']['centre'], cfg['angular']['halfFull'], cfg['angular']['halfZero'])
        F = 1 + (F - 1) * w[None, :]
    t = cyl.s_grid
    F[(t < lo) | (t > hi)] = 1.0
    return np.where(np.abs(F - 1) < 1e-5, 1.0, F)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh descendant directory required')
    cfg = json.loads(a.config.read_text())
    meshes = {}
    for side in ('low', 'high'):
        p = Path(cfg[side]['master']); require(sha(p) == cfg[side]['sha256'], side + ' parent changed')
        meshes[side] = Mesh(p)
    J = {s: np.asarray(cfg[s]['joint'], float) for s in ('low', 'high')}
    world = {s: meshes[s].U + J[s] for s in meshes}
    samples = {s: surface_samples(world[s], meshes[s].F, cfg.get('samples', 400000)) for s in meshes}
    cyl = Cylinder(cfg['origin'], cfg['axis'], np.concatenate(list(samples.values())), *cfg['tRange'], step=cfg.get('step', 0.0025),
                   centre_sigma=cfg.get('centreSigma', 0.01))
    ts = cfg.get('thetaStep', 10)
    rL, thetas = cyl.outer_profile(samples['low'], ts); rH, _ = cyl.outer_profile(samples['high'], ts)
    rL = fill_nan_rows(rL, cfg.get('fillMaxMissing', 0.25)); rH = fill_nan_rows(rH, cfg.get('fillMaxMissing', 0.25))
    t = cyl.s_grid
    TL = np.empty_like(rL); TH = np.empty_like(rH); E = np.empty_like(rL)
    for j in range(len(thetas)):
        TL[:, j], TH[:, j], E[:, j] = shared_targets(t, rL[:, j], rH[:, j], cfg)
    g = cfg.get('guard', 0.01)
    FL = scale_field(rL, TL, cyl, cfg, -np.inf, cfg['tHighRef'], thetas)
    FL[t < cfg['tLowRef'] - g] = 1.0
    FH = scale_field(rH, TH, cyl, cfg, cfg['tLowRef'], np.inf, thetas)
    FH[t > cfg['tHighRef'] + g] = 1.0
    a.output.mkdir(parents=True)
    out = {}; recs = {}
    after = {}
    for side, F in (('low', FL), ('high', FH)):
        mesh = meshes[side]
        newW, scale = cyl.apply(world[side], F, thetas)
        newU = newW - J[side]
        fn0 = face_normals(mesh.U, mesh.F); fn1 = face_normals(newU, mesh.F)
        cosang = np.sum(fn0 * fn1, 1) / np.maximum(np.linalg.norm(fn0, axis=1) * np.linalg.norm(fn1, axis=1), 1e-30)
        require(cosang.min() > 0.0, 'Inverted triangles on ' + side)
        desc = Descendant(mesh); desc.U = newU
        path = a.output / (cfg[side]['name'] + '-local.glb'); desc.write(path)
        out[side] = path
        after[side], _ = cyl.outer_profile(surface_samples(newW, mesh.F, cfg.get('samples', 400000)), ts)
        recs[side] = dict(part=cfg[side]['part'], parent={'path': cfg[side]['master'], 'sha256': cfg[side]['sha256']},
                          descendant={'path': str(path), 'sha256': sha(path)}, summary=summary(desc, cfg[side]['name']),
                          scaleRange=[float(scale.min()), float(scale.max())], minFaceNormalCos=float(cosang.min()))
    # visible envelope before/after and seam continuity
    def env(a_, b_):
        return np.fmax(a_, b_)
    lo, hi = cfg['tLowRef'], cfg['tHighRef']
    win = (t >= lo) & (t <= hi)
    def jumps(e):
        dd = np.abs(np.diff(e[win], axis=0)); dd = dd[~np.isnan(dd)]
        return float(dd.max()) if len(dd) else None
    e0 = env(rL, rH); e1 = env(after['low'], after['high'])
    sectors = list(range(0, len(thetas), max(1, len(thetas) // 8)))
    table = [dict(t=float(tv), **{('theta%+d' % thetas[j]): [None if np.isnan(x) else round(float(x), 4) for x in
                                                           (rL[i, j], rH[i, j], after['low'][i, j], after['high'][i, j], E[i, j])] for j in sectors})
             for i, tv in enumerate(t) if lo - 0.02 <= tv <= hi + 0.02]
    record = dict(schemaVersion=1, kind='shared-junction-descendant', name=cfg['name'], config=cfg, configSha256=sha(a.config), helperSha256=sha(__file__),
                  parts=recs, visibleEnvelopeMaxJumpPerSample={'before': jumps(e0), 'after': jumps(e1), 'sampleMeters': cyl.step},
                  tableColumns='r_low_before, r_high_before, r_low_after, r_high_after, sharedEnvelope', profileTable=table,
                  policy='Positions/transported normals and tangents only, both parts; UV/index/map/material exact; no approval implied.')
    write_receipt(a.output / 'descendant.json', record)
    shutil.copy2(__file__, a.output / 'executed-helper.py'); shutil.copy2(a.config, a.output / 'executed-config.json')
    print(json.dumps({'outputs': {k: str(v) for k, v in out.items()}, 'jump': record['visibleEnvelopeMaxJumpPerSample'],
                      'scale': {k: v['scaleRange'] for k, v in recs.items()}}))


if __name__ == '__main__':
    main()
