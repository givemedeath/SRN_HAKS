"""Derive explicit skin PLT intensity descendants (bounded int16 deltas) for the female Gate 3 texture fixes.

Operates on the effective (already calibrated) skin intensity atlases of the compiled body and its literal runtime
geometry, in the accepted idle offline-rig pose. Every operation writes only skin texels of its declared atlas:
  jointTone          tone continuity across a part join: per angular sector about the join axis, the median CURRENT intensity
                     of the visible skin of A and B next to the seam is measured; A receives shares[0] x (mB - mA) and B
                     shares[1] x (mA - mB), applied
                     with weight 1 at/inside the seam falling (cosine) to 0 at `falloff[1]` metres from B's surface.
  darkLift           lifts dark outlier texels (baked brief shadow / speckle) toward a robust local tone: I' = max(I, L - k).
  detailAttenuation  attenuates high-frequency striation: I' = L + alpha (I - L), region-weighted.
  pad                fills texels not covered by the atlas's skin faces from covered neighbours (bilinear/mip bleed guard).
L is a masked (covered-texel) Gaussian low-pass. Weights are interpolated per texel from per-vertex values, so every
correction is smooth. No geometry, UV, normal map, roughness or garment pixel changes; no approval implied.
"""
from pathlib import Path
import argparse, hashlib, json, time
import numpy as np
from PIL import Image, ImageDraw

SIZE = 2048
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fingerprint(a):
    a = np.ascontiguousarray(a); return hashlib.sha256(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes()).hexdigest()


def read_plt(path):
    data = Path(path).read_bytes()
    if data[:8] != b'PLT V1  ' or len(data) != 24 + SIZE * SIZE * 2:
        raise ValueError('Unexpected PLT')
    return np.frombuffer(data[24:], 'u1').reshape(SIZE, SIZE, 2)[::-1][..., 0].copy()


def texel_rows(uv):
    """Native UV -> (x, y) pixel coordinates of the top-down intensity array (row = (1 - v) * SIZE)."""
    return np.stack([uv[..., 0] * SIZE, (1 - uv[..., 1]) * SIZE], -1)


def raster(uv, faces):
    """Per-texel face id (-1 none) and barycentric weights of covered texel centres."""
    img = Image.new('RGB', (SIZE, SIZE), (0, 0, 0)); d = ImageDraw.Draw(img); t = texel_rows(uv[faces])
    for i, tri in enumerate(t):
        k = i + 1; d.polygon([tuple(p) for p in tri], fill=(k & 255, (k >> 8) & 255, (k >> 16) & 255))
    a = np.asarray(img).astype(np.int64); fid = (a[..., 0] | (a[..., 1] << 8) | (a[..., 2] << 16)) - 1
    ys, xs = np.nonzero(fid >= 0); f = fid[ys, xs]; q = np.stack([xs + .5, ys + .5], 1); tt = t[f]
    v0 = tt[:, 1] - tt[:, 0]; v1 = tt[:, 2] - tt[:, 0]; v2 = q - tt[:, 0]
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]; den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    b1 = (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / den; b2 = (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / den
    b = np.clip(np.stack([1 - b1 - b2, b1, b2], 1), 0, 1); b /= b.sum(1, keepdims=True)
    return ys, xs, f, b


def gaussian_kernel(sigma):
    r = int(np.ceil(3 * sigma)); x = np.arange(-r, r + 1); k = np.exp(-0.5 * (x / sigma) ** 2); return k / k.sum()


def blur(a, sigma):
    k = gaussian_kernel(sigma); r = len(k) // 2
    p = np.pad(a, ((r, r), (0, 0)), mode='constant'); a = sum(k[i] * p[i:i + a.shape[0]] for i in range(len(k)))
    p = np.pad(a, ((0, 0), (r, r)), mode='constant'); return sum(k[i] * p[:, i:i + a.shape[1]] for i in range(len(k)))


def masked_lowpass(I, M, sigma):
    num = blur(I.astype(np.float64) * M, sigma); den = blur(M.astype(np.float64), sigma)
    return np.where(den > 1e-6, num / np.maximum(den, 1e-6), I)


def nearest(points, cloud, normals=None, chunk=4096):
    """Nearest cloud vertex distance (and signed side if normals given) for every point (brute force, float32)."""
    pts = np.asarray(points, np.float32); cl = np.asarray(cloud, np.float32); dist = np.empty(len(pts)); idx = np.empty(len(pts), np.int64)
    c2 = (cl * cl).sum(1)
    for s in range(0, len(pts), chunk):
        q = pts[s:s + chunk]; d2 = (q * q).sum(1)[:, None] - 2 * q @ cl.T + c2[None]
        j = np.argmin(d2, 1); idx[s:s + chunk] = j; dist[s:s + chunk] = np.sqrt(np.maximum(d2[np.arange(len(q)), j], 0))
    side = None if normals is None else np.einsum('ij,ij->i', pts - cl[idx], np.asarray(normals, np.float32)[idx])
    return dist, side


def circular_smooth(v, passes=2):
    for _ in range(passes):
        v = 0.25 * np.roll(v, 1) + 0.5 * v + 0.25 * np.roll(v, -1)
    return v


def fill_circular(v):
    v = np.asarray(v, float); good = ~np.isnan(v)
    if not good.any():
        return np.zeros_like(v)
    n = len(v); x = np.arange(n); xg = x[good]
    return np.interp(x, np.concatenate([xg - n, xg, xg + n]), np.tile(v[good], 3))


def cosine_falloff(d, d0, d1):
    d = np.asarray(d, float); w = np.ones_like(d); m = d > d0
    w[m] = np.where(d[m] >= d1, 0.0, 0.5 * (1 + np.cos(np.pi * (d[m] - d0) / (d1 - d0)))); return w


class Mesh:
    def __init__(self, name, arrays_path, matrix, plt_path):
        a = np.load(arrays_path); self.name = name
        self.local = a['position'].astype(np.float64); self.uv = a['uv'].astype(np.float64); self.faces = a['faces'].astype(np.int64)
        M = np.asarray(matrix, float); self.world = self.local @ M[:3, :3].T + M[:3, 3]
        n = a['normal'].astype(np.float64) @ M[:3, :3].T; self.normal = n / np.linalg.norm(n, axis=1, keepdims=True)
        self.plt = plt_path; self.I = read_plt(plt_path) if plt_path is not None else None
        self.ys, self.xs, self.tf, self.tb = raster(self.uv, self.faces)
        self.covered = np.zeros((SIZE, SIZE), bool); self.covered[self.ys, self.xs] = True

    def texel_values(self, per_vertex):
        """Barycentric interpolation of a per-vertex field onto the covered texels."""
        return np.einsum('tc,tc->t', per_vertex[self.faces[self.tf]], self.tb)


def occluded(X, occluders, distance):
    """Per-vertex sampling exclusion: within `distance` of any occluder (e.g. skin under or at the brief)."""
    hidden = np.zeros(len(X.world), bool)
    for O in occluders:
        hidden |= nearest(X.world, O.world)[0] < distance
    return hidden


def joint_tone(A, B, IA, IB, axis_origin, axis, shares, near, falloff, sectors, same_surface=False, occluders=(), occlusion_distance=0.004):
    axis = np.asarray(axis, float); axis /= np.linalg.norm(axis); ref = np.array([0., 1., 0.]) - axis * axis[1]
    if np.linalg.norm(ref) < 1e-6:
        ref = np.array([1., 0., 0.]) - axis * axis[0]
    ref /= np.linalg.norm(ref); side = np.cross(axis, ref)
    def theta(p):
        d = p - axis_origin; return np.degrees(np.arctan2(d @ side, d @ ref)) % 360
    dA, sA = nearest(A.world, B.world, B.normal); dB, sB = nearest(B.world, A.world, A.normal)
    # visible-near-seam texels: outside the partner and within `near` of its surface
    out = {}
    for key, X, d, s, I in (('A', A, dA, sA, IA), ('B', B, dB, sB, IB)):
        hid = occluded(X, occluders, occlusion_distance).astype(float) if occluders else np.zeros(len(X.world))
        td = X.texel_values(d); ts = np.ones(len(X.tf)) if same_surface else X.texel_values(s); th_hidden = X.texel_values(hid)
        th = theta(np.einsum('tcj,tc->tj', X.world[X.faces[X.tf]], X.tb))
        sel = (ts > 0) & (td < near) & (th_hidden < 0.5); vals = I[X.ys, X.xs].astype(float)
        bins = (th[sel] / (360 / sectors)).astype(int) % sectors; med = np.full(sectors, np.nan)
        for b in range(sectors):
            v = vals[sel][bins == b]
            if len(v) >= 40:
                med[b] = np.median(v)
        out[key] = med
    mA, mB = out['A'], out['B']; both = ~np.isnan(mA) & ~np.isnan(mB)
    diff = np.where(both, mB - mA, np.nan); diff = circular_smooth(fill_circular(diff))
    # per-vertex deltas: A moves shares[0] x (mB - mA), B moves shares[1] x (mA - mB); weight 1 at/inside the seam
    def field(X, d, s, sign, share):
        th = theta(X.world); pos = th / (360 / sectors); i0 = np.floor(pos).astype(int) % sectors; fr = pos - np.floor(pos)
        return X.texel_values(sign * share * ((1 - fr) * diff[i0] + fr * diff[(i0 + 1) % sectors]) * cosine_falloff(np.where(s < 0, 0, d), *falloff))
    report = {'sectorMedianA': [None if np.isnan(x) else float(x) for x in mA], 'sectorMedianB': [None if np.isnan(x) else float(x) for x in mB],
              'sectorsMeasuredBoth': int(both.sum()), 'appliedSectorDifference': [float(x) for x in diff], 'shares': list(shares),
              'meanAbsoluteStepBefore': float(np.nanmean(np.abs(mB - mA))) if both.any() else None}
    return field(A, dA, sA, 1, shares[0]), field(B, dB, sB, -1, shares[1]), report


def dark_lift(X, I, weight_vertex, sigma, k):
    M = X.covered.astype(float); L = masked_lowpass(I, M, sigma)
    robust = X.covered & (I >= L - k); L = masked_lowpass(I, robust.astype(float), sigma)
    w = np.zeros((SIZE, SIZE)); w[X.ys, X.xs] = X.texel_values(weight_vertex)
    target = np.maximum(I, L - k); return I + w * (target - I)


def detail_attenuation(X, I, weight_vertex, sigma, alpha):
    L = masked_lowpass(I, X.covered.astype(float), sigma)
    w = np.zeros((SIZE, SIZE)); w[X.ys, X.xs] = X.texel_values(weight_vertex)
    a = 1 - w * (1 - alpha); return L + a * (I - L)


def pad(X, I, iterations):
    out = I.copy(); filled = X.covered.copy()
    for _ in range(iterations):
        acc = np.zeros((SIZE, SIZE)); cnt = np.zeros((SIZE, SIZE))
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            acc += np.roll(np.roll(np.where(filled, out, 0.0), dy, 0), dx, 1); cnt += np.roll(np.roll(filled.astype(float), dy, 0), dx, 1)
        new = ~filled & (cnt > 0); out[new] = acc[new] / cnt[new]; filled |= new
    return out, int((filled & ~X.covered).sum())


def vertex_region_weight(X, spec, meshes):
    """Per-vertex weight: optional part-local z window and optional proximity to another mesh (cosine falloff)."""
    w = np.ones(len(X.local))
    if 'zWindow' in spec:
        lo, hi, blend = spec['zWindow']; z = X.local[:, 2]
        w *= np.clip(np.minimum(z - lo, hi - z) / blend + 1, 0, 1) if blend > 0 else ((z >= lo) & (z <= hi)).astype(float)
    if 'near' in spec:
        other = meshes[spec['near']['mesh']]; d, _ = nearest(X.world, other.world); w *= cosine_falloff(d, *spec['near']['falloff'])
    return w * spec.get('weight', 1.0)


def derive(config):
    rig = json.loads(Path(config['rigRecipe']['path']).read_text()); assert sha(config['rigRecipe']['path']) == config['rigRecipe']['sha256']
    pose = next(s for s in rig['samples'] if s['clip'] == config['pose']['clip'] and abs(s['fraction'] - config['pose']['fraction']) < 1e-9)
    meshes = {}; parents = {}
    for name, m in config['meshes'].items():
        for key in ('arrays', 'plt'):
            if m.get(key) is not None and sha(m[key]['path']) != m[key]['sha256']:
                raise ValueError('Changed derivation input: ' + m[key]['path'])
        meshes[name] = Mesh(name, m['arrays']['path'], pose['matrices'][m['joint']], m['plt']['path'] if m.get('plt') else None)
        if meshes[name].I is not None:
            parents[name] = meshes[name].I.copy()
    work = {n: parents[n].astype(np.float64) for n in config['targets']}
    reports = []
    for op in config['operations']:
        t = time.time(); kind = op['op']; r = {'op': kind, 'target': op['target']}
        X = meshes[op['target']]
        if kind == 'jointTone':
            J = np.asarray(pose['matrices'][op['axisJoint']], float); B = meshes[op['partner']]
            IA = work.get(op['target'], parents.get(op['target'])); IB = work.get(op['partner'], parents.get(op['partner']))
            dA, dB, rep = joint_tone(X, B, IA, IB, J[:3, 3], J[:3, :3] @ np.asarray(op.get('localAxis', [0, 0, 1.0])), op['shares'], op['near'], op['falloff'], op['sectors'],
                                     op.get('sameSurface', False), [meshes[n] for n in op.get('occluders', [])], op.get('occlusionDistance', 0.004))
            work[op['target']][X.ys, X.xs] += dA
            if op['shares'][1]:
                work[op['partner']][B.ys, B.xs] += dB
            r.update(rep, partner=op['partner'], texelsAffected=int((np.abs(dA) > 0.5).sum() + (np.abs(dB) > 0.5).sum()))
        elif kind == 'capTone':
            arch = op['archive']
            if sha(arch['path']) != arch['sha256']:
                raise ValueError('Changed cap archive')
            caps = np.load(arch['path'])['generatedCapFaceIds']; is_cap = np.zeros(len(X.faces), bool); is_cap[caps] = True
            if len(np.load(arch['path'])['positions']) != len(X.faces):
                raise ValueError('Cap archive/compiled face order differs')
            cap_tex = np.zeros((SIZE, SIZE), bool); cap_tex[X.ys[is_cap[X.tf]], X.xs[is_cap[X.tf]]] = True
            skin_tex = np.zeros((SIZE, SIZE), bool); skin_tex[X.ys[~is_cap[X.tf]], X.xs[~is_cap[X.tf]]] = True
            cc = X.world[X.faces[is_cap]].mean(1); d, _ = nearest(X.world, cc); nearv = d < op['near']
            sel = (~is_cap[X.tf]) & (X.texel_values(nearv.astype(float)) > 0.5)
            target = float(np.median(work[op['target']][X.ys[sel], X.xs[sel]])); only = cap_tex & ~skin_tex
            before = float(np.median(work[op['target']][only])); work[op['target']][only] = target
            r.update(capFaces=int(is_cap.sum()), capOnlyTexels=int(only.sum()), sharedTexels=int((cap_tex & skin_tex).sum()), capToneBefore=before, capToneAfter=target, neighbourTexels=int(sel.sum()))
        elif kind == 'darkLift':
            new = dark_lift(X, work[op['target']], vertex_region_weight(X, op.get('region', {}), meshes), op['sigma'], op['k'])
            r['texelsLifted'] = int((new - work[op['target']] > 0.5).sum()); work[op['target']] = new
        elif kind == 'detailAttenuation':
            new = detail_attenuation(X, work[op['target']], vertex_region_weight(X, op.get('region', {}), meshes), op['sigma'], op['alpha'])
            r['meanAbsoluteChange'] = float(np.abs(new - work[op['target']])[X.covered].mean()); work[op['target']] = new
        elif kind == 'pad':
            work[op['target']], r['paddedTexels'] = pad(X, work[op['target']], op['iterations'])
        else:
            raise ValueError('Unknown operation: ' + kind)
        r['seconds'] = round(time.time() - t, 1); reports.append(r)
    results = {}
    for name in config['targets']:
        X = meshes[name]; new = np.clip(np.rint(work[name]), 0, 255).astype(np.uint8); delta = new.astype(np.int16) - parents[name].astype(np.int16)
        results[name] = {'parent': parents[name], 'new': new, 'delta': delta, 'coveredChanged': int((delta[X.covered] != 0).sum()),
                         'uncoveredChanged': int((delta[~X.covered] != 0).sum()), 'maxAbsDelta': int(np.abs(delta).max())}
    return results, reports


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--config', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args(); out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False); cfg = json.loads(a.config.read_text())
    if cfg.get('kind') != 'skin-intensity-descendant-derivation-v1':
        raise ValueError('Explicit derivation config required')
    results, reports = derive(cfg); rows = {}
    for name, r in results.items():
        m = cfg['meshes'][name]; dest = out / f'{name}-intensity-delta.npz'
        np.savez_compressed(dest, delta=r['delta'], parentIntensitySha256=np.array(fingerprint(r['parent'])), intensitySha256=np.array(fingerprint(r['new'])))
        Image.fromarray(np.clip(128 + 4 * r['delta'], 0, 255).astype(np.uint8)).resize((1024, 1024)).save(out / f'{name}-delta-preview.png')
        rows[name] = {'part': m['part'], 'atlasKey': m['atlasKey'], 'material': m['material'], 'parentPlt': m['plt'], 'delta': {'path': str(dest), 'sha256': sha(dest)},
                      'parentIntensitySha256': fingerprint(r['parent']), 'intensitySha256': fingerprint(r['new']),
                      'changedTexels': int((r['delta'] != 0).sum()), 'coveredChanged': r['coveredChanged'], 'uncoveredChanged': r['uncoveredChanged'], 'maxAbsDelta': r['maxAbsDelta']}
    receipt = {'schemaVersion': 1, 'kind': 'skin-intensity-descendant-derivation', 'config': {'path': str(a.config.resolve()), 'sha256': sha(a.config)},
               'helper': {'path': str(Path(__file__).resolve()), 'sha256': sha(__file__)}, 'atlases': rows, 'operations': reports,
               'geometryUvNormalRoughnessGarmentEdited': False, 'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    (out / 'derivation.json').write_text(json.dumps(receipt, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'receipt': str(out / 'derivation.json'), 'atlases': {k: {x: v[x] for x in ('changedTexels', 'maxAbsDelta')} for k, v in rows.items()}}))


if __name__ == '__main__':
    main()
