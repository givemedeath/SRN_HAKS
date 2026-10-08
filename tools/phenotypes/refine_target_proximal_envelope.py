"""Measured proximal (shoulder-ball) envelope refinement of an upper-arm master descendant.

Per (s, theta) cell of the limb's outer radius r0:
  reduced = r0 * (1 - p * b(s))          b = 1 on the dome plateau, cosine to 0 at the band ends
  fill    = monotone smooth bridge from reduced(peak) to r0(belly) between the dome peak and the belly
  target  = reduced + max(0, fill - reduced) * g(s)   g = cosine bump inside (belly, peak)
The scale field target/r0 is Gaussian-smoothed and applied radially about the limb centre curve
(injective for positive scale). Optionally the cap above capStart is compressed along the axis by a
C1 monotone map so the top reaches capTop (no reflection; s order preserved). Only positions and
transported normals/tangents change; UVs, indices, maps and materials stay exact.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from descendant_mesh_edit import Mesh, Descendant, summary, require, sha, write_receipt, face_normals
from radial_envelope_field import (Cylinder, fill_nan_rows, smooth_grid, cosine_falloff, width_depth_profile)


def cap_map(s, start, ramp, top_old, top_new):
    """Monotone C1 axial compression above start so that top_old maps to top_new."""
    require(top_new < top_old and start < top_new, 'Cap compression must lower the top above its start')
    def mapped(x, k):
        x = np.asarray(x, float)
        u = np.clip((x - start) / ramp, 0, 1)
        # integral of 1 - (1-k)*smoothstep(u) from start to x
        smooth_int = np.where(u < 1, u ** 3 - 0.5 * u ** 4, 0.5)  # integral of 3u^2-2u^3 over [0,u]
        over = np.clip(x - start - ramp, 0, None)
        integral = (x - start).clip(0) - (1 - k) * (ramp * smooth_int + over)
        return np.where(x <= start, x, start + integral)
    lo, hi = 1e-3, 1.0
    for _ in range(80):
        k = (lo + hi) / 2
        if mapped(top_old, k) > top_new:
            hi = k
        else:
            lo = k
    k = (lo + hi) / 2
    return mapped(s, k), k


def target_field(r0, s_grid, cfg):
    p = cfg['reduction']
    lo, hi = cfg['plateau']; zlo, zhi = cfg['falloff']
    b = cosine_falloff(s_grid, lo, hi, zlo, zhi)[:, None]
    reduced = r0 * (1 - p * b)
    peak, belly = cfg['fill']['peak'], cfg['fill']['belly']
    ip = int(np.argmin(np.abs(s_grid - peak))); ib = int(np.argmin(np.abs(s_grid - belly)))
    u = np.clip((peak - s_grid) / (peak - belly), 0, 1)[:, None]
    h = u * u * (3 - 2 * u)
    fill = reduced[ip][None, :] + (r0[ib][None, :] - reduced[ip][None, :]) * h
    g = cosine_falloff(s_grid, belly + 0.25 * (peak - belly), peak - 0.25 * (peak - belly), belly, peak)[:, None]
    target = reduced + np.maximum(0, fill - reduced) * g
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh descendant directory required')
    cfg = json.loads(a.config.read_text())
    master = Path(cfg['master']); require(sha(master) == cfg['masterSha256'], 'Parent master changed')
    mesh = Mesh(master)
    desc = Descendant(mesh)
    cyl = Cylinder(cfg.get('origin', [0, 0, 0]), cfg.get('axis', [0, 0, 1]), mesh.U, *cfg['sRange'], step=cfg.get('step', 0.005))
    r0, thetas = cyl.outer_profile(mesh.U, cfg.get('thetaStep', 10))
    r0 = fill_nan_rows(r0)
    valid = ~np.isnan(r0).any(axis=1)
    target = target_field(np.where(np.isnan(r0), 1, r0), cyl.s_grid, cfg)
    F = np.where(valid[:, None], target / np.where(np.isnan(r0), 1, r0), 1.0)
    F = smooth_grid(F, cfg.get('sigmaS', 0.008) / cyl.step, cfg.get('sigmaTheta', 15) / cfg.get('thetaStep', 10))
    zlo, zhi = cfg['falloff']
    outside = (cyl.s_grid <= zlo) | (cyl.s_grid >= zhi + 0.05)
    F[outside] = 1.0
    F = np.where(np.abs(F - 1) < 1e-5, 1.0, F)  # exact identity outside the measurable edit
    if cfg.get('skipRadial'):
        F = np.ones_like(F)  # axial-only use (e.g. squash a hidden garment rim under its neighbour)
    newU, scale = cyl.apply(mesh.U, F, thetas)
    k = None
    if cfg.get('capTop') is not None:
        top_old = float(mesh.U[:, 2].max())
        newU[:, 2], k = cap_map(newU[:, 2], cfg['capStart'], cfg['capRamp'], top_old, cfg['capTop'])
    desc.U = newU
    fn0 = face_normals(mesh.U, mesh.F); fn1 = face_normals(newU, mesh.F)
    cosang = np.sum(fn0 * fn1, 1) / np.maximum(np.linalg.norm(fn0, axis=1) * np.linalg.norm(fn1, axis=1), 1e-30)
    area_ratio = np.linalg.norm(fn1, axis=1) / np.maximum(np.linalg.norm(fn0, axis=1), 1e-30)
    require(cosang.min() > cfg.get('minNormalCos', 0.2) and area_ratio.min() > cfg.get('minAreaRatio', 0.2), 'Inverted or collapsed triangles')
    a.output.mkdir(parents=True)
    out = a.output / (cfg.get('name', 'refined') + '-local.glb')
    desc.write(out)
    z = np.round(np.arange(cfg['falloff'][1], cfg['falloff'][0] - 0.0001, -0.01), 3)
    record = dict(schemaVersion=1, kind='proximal-envelope-descendant', part=cfg['part'], parent={'path': str(master), 'sha256': sha(master)},
                  descendant={'path': str(out), 'sha256': sha(out)}, config=cfg, configSha256=sha(a.config), helperSha256=sha(__file__),
                  summary=summary(desc, cfg.get('name')), capCompressionK=k,
                  scaleRange=[float(scale.min()), float(scale.max())], minFaceNormalCos=float(cosang.min()), minAreaRatio=float(area_ratio.min()),
                  profileBefore=width_depth_profile(mesh.U, mesh.F, z), profileAfter=width_depth_profile(newU, mesh.F, z),
                  topBefore=float(mesh.U[:, 2].max()), topAfter=float(newU[:, 2].max()),
                  policy='Positions/transported normals and tangents only; UV/index/map/material exact; no approval implied.')
    write_receipt(a.output / 'descendant.json', record)
    shutil.copy2(__file__, a.output / 'executed-helper.py'); shutil.copy2(a.config, a.output / 'executed-config.json')
    print(json.dumps({'output': str(out), 'scale': record['scaleRange'], 'top': [record['topBefore'], record['topAfter']], 'k': k}))


if __name__ == '__main__':
    main()
