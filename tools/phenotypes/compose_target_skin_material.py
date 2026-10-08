"""Compose calibrated skin materials (PLT shade, normal, roughness) for geometry-descendant body parts.

Per part, at its actual UVs:
  L       albedo luminance of the part master's embedded base colour (Rec.709), optional valley-only
          texture fill inside declared crease bands (removes painted crease lines),
  field   bind-pose diffuse lighting bake / its median; AO bake,
  S0      L * mix(1, field) * mix(1, AO),
  shade   affine-calibrated so the area-weighted surface distribution has the declared mean/std, plus a
          per-part offset solved by least squares so neighbouring parts match in their contact bands,
          soft-limited away from 0/255 (no clipping).
Normals: v1 native normal map with a bounded per-part detail gain (target median tilt), crease-band
smoothing, flat in rebuilt-face islands. Roughness: v1 map; declared parts are matched to a reference
part's distribution (hands -> forearms). Rebuilt-face islands take the mean albedo of the nearby skin.
Empty atlas texels are padded from neighbours. Previews colourize the PLT with the stock skin palette.
Optional (absent keys keep the earlier behaviour exactly):
  targets.matchReference  one constant shift so the area-weighted body palette luminance (mean of the palette
                          rows) equals the reference PLTs (v1) at the same UVs;
  fixedPartners           unchanged neighbours (stock neck): a constant contact-band target in the offset solve
                          (weight continuity.fixedWeight) and a neckline blend of the movable part's low-frequency
                          shade toward the partner's band tone with a smoothstep falloff (detail kept);
  part.featureContrast    disk deviations from a ring baseline scaled to the reference luminance contrast.
Outputs are new files only; no source map, GLB or published resource is modified.
"""
import argparse, json, shutil, struct, sys
from io import BytesIO
from pathlib import Path
import copy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from descendant_mesh_edit import Mesh, require, sha, write_receipt, transported_positions
from place_purposebuilt_pelvis import read_glb, accessor, BASIS
from round_generated_waist_cap import append_accessor, write_glb
from radial_envelope_field import Cylinder, cosine_falloff, angular_weight

LUMA = np.array([0.2126, 0.7152, 0.0722])


# ---------- image helpers (all arrays top-down, glTF V convention) ----------
def plt_read(path):
    d = Path(path).read_bytes(); require(d[:8] == b'PLT V1  ', 'PLT header')
    layers, _, w, h = struct.unpack_from('<IIII', d, 8)
    raw = np.frombuffer(d, np.uint8, offset=24).reshape(h, w, 2)
    return d[:24], raw[::-1].copy()


def plt_write(path, header, img):
    Path(path).write_bytes(header + np.ascontiguousarray(img[::-1]).tobytes())


def tga_read(path):
    d = Path(path).read_bytes(); idlen = d[0]
    w, h, bpp, desc = struct.unpack_from('<HHBB', d, 12)
    require(d[2] == 2 and bpp == 24, 'Uncompressed 24-bit TGA expected')
    off = 18 + idlen; n = w * h * 3
    px = np.frombuffer(d, np.uint8, offset=off, count=n).reshape(h, w, 3)[:, :, ::-1]
    top = bool(desc & 0x20)
    return dict(head=d[:off], tail=d[off + n:], top=top), (px if top else px[::-1]).copy()


def tga_write(path, meta, img):
    rows = img if meta['top'] else img[::-1]
    Path(path).write_bytes(meta['head'] + np.ascontiguousarray(rows[:, :, ::-1]).tobytes() + meta['tail'])


def glb_image(doc, binary, index):
    v = doc['bufferViews'][doc['images'][index]['bufferView']]
    return Image.open(BytesIO(bytes(binary[v.get('byteOffset', 0):v.get('byteOffset', 0) + v['byteLength']])))


def raster(uv_tris, values, size):
    img = Image.new('F', (size, size), 0.0); d = ImageDraw.Draw(img)
    for tri, val in zip(uv_tris, values):
        d.polygon([(float(u) * size, float(v) * size) for u, v in tri], fill=float(val))
    return np.asarray(img)


def sample(img, uv):
    h, w = img.shape[:2]
    x = np.clip(uv[:, 0] * w - 0.5, 0, w - 1.001); y = np.clip(uv[:, 1] * h - 0.5, 0, h - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    a = img[y0, x0]; b = img[y0, x0 + 1]; c = img[y0 + 1, x0]; d = img[y0 + 1, x0 + 1]
    if img.ndim == 3:
        fx = fx[:, None]; fy = fy[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def gauss(img, sigma):
    """Separable Gaussian (edge-clamped) on the first two axes."""
    r = max(1, int(np.ceil(3 * sigma))); x = np.arange(-r, r + 1); k = np.exp(-0.5 * (x / sigma) ** 2); k /= k.sum()
    out = img.astype('f4')
    for axis in (0, 1):
        pad_w = [(0, 0)] * out.ndim; pad_w[axis] = (r, r)
        p = np.pad(out, pad_w, mode='edge'); acc = np.zeros_like(out); n = out.shape[axis]
        for i, w in enumerate(k):
            acc += w * (p[i:i + n] if axis == 0 else p[:, i:i + n])
        out = acc
    return out


def blur(img, sigma, mask=None):
    """Gaussian blur; with a mask, normalized so texels outside the mask (empty atlas) do not bleed in."""
    if mask is None:
        return gauss(img, sigma)
    m = mask.astype('f4'); num = gauss(img * (m[..., None] if img.ndim == 3 else m), sigma); den = gauss(m, sigma)
    den = np.maximum(den, 1e-6)
    return num / (den[..., None] if img.ndim == 3 else den)


def pad(img, valid, steps):
    """Fill invalid texels from valid neighbours (iterative 3x3 mean dilation)."""
    out = img.astype('f4').copy(); ok = valid.copy()
    for _ in range(steps):
        if ok.all():
            break
        acc = np.zeros_like(out); cnt = np.zeros(ok.shape, 'f4')
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                s_ok = np.roll(np.roll(ok, dy, 0), dx, 1)
                s_v = np.roll(np.roll(out, dy, 0), dx, 1)
                acc += s_v * (s_ok[..., None] if out.ndim == 3 else s_ok)
                cnt += s_ok
        grow = (~ok) & (cnt > 0)
        out[grow] = (acc[grow] / (cnt[grow][:, None] if out.ndim == 3 else cnt[grow]))
        ok = ok | grow
    return out, ok


def surface(P, T, n, seed):
    a, b, c = P[:, 0], P[:, 1], P[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(P), size=n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n); q = np.sqrt(r1)
    w = np.stack([1 - q, q * (1 - r2), q * r2], 1)
    return np.einsum('nk,nkd->nd', w, P[idx]), np.einsum('nk,nkd->nd', w, T[idx])


def soft_limit(x, lo, hi, knee=12.0):
    y = x.copy()
    over = y > hi - knee; y[over] = hi - knee + knee * np.tanh((y[over] - (hi - knee)) / knee)
    under = y < lo + knee; y[under] = lo + knee - knee * np.tanh(((lo + knee) - y[under]) / knee)
    return y


def stats(x):
    x = np.asarray(x, float)
    return dict(mean=float(x.mean()), std=float(x.std()), p1=float(np.percentile(x, 1)), p5=float(np.percentile(x, 5)),
                p95=float(np.percentile(x, 95)), p99=float(np.percentile(x, 99)), min=float(x.min()), max=float(x.max()))


def tilt(nimg, uv):
    n = sample(nimg.astype('f4'), uv) / 255 * 2 - 1
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    return np.degrees(np.arccos(np.clip(n[:, 2], -1, 1)))


def valley_clamp(X, cover, sigma, depth, wmap=None):
    """Limit thin dark valleys: X >= blur(X) * (1 - depth); inside crease bands (wmap) the floor rises to blur(X).
    Broad occlusion (where the blur is dark too) is kept; narrow grooves and contact lines are softened."""
    Xb = blur(X, sigma, cover)
    d = np.full(X.shape, depth, 'f4') if wmap is None else depth * (1 - wmap)
    return np.maximum(X, Xb * (1 - d))


def lit(L, p, suv, cfg, size, cover, wmap=None, contact=None):
    """S0 = L * mix(1, diffuse/median) * mix(1, AO) from the part's bind-pose bake (top-down npz).
    Returns S0 and the raw AO at the surface samples (visibility test for contact bands)."""
    bake = np.load(p['bake'])
    D = np.asarray(Image.fromarray(bake['diffuse']).resize((size, size), Image.BILINEAR))
    A = np.asarray(Image.fromarray(bake['ao']).resize((size, size), Image.BILINEAR))
    raw_ao = sample(A, suv)
    lc = cfg['lighting']
    if lc.get('valleyClamp'):
        vc = lc['valleyClamp']
        A = valley_clamp(A, cover, vc['sigmaPx'], vc['depth'], wmap)
        D = valley_clamp(D, cover, vc['sigmaPx'], vc['depth'], wmap)
    if lc.get('blurPx'):
        A = blur(A, lc['blurPx'], cover); D = blur(D, lc['blurPx'], cover)
    A = np.clip(A, lc.get('aoFloor', 0.0), 1)
    Dv = sample(D, suv); med = float(np.median(Dv[Dv > 0])) if (Dv > 0).any() else 1.0
    if contact is not None:
        A = A + (1 - A) * contact
        D = D + (np.maximum(D, med) - D) * contact
    lo, hi = lc.get('fieldClamp', [0.35, 1.7])
    field = np.clip(D / max(med, 1e-6), lo, hi)
    lm, am = lc['lightMix'], lc['aoMix']
    return L * (1 - lm + lm * field) * (1 - am + am * A), raw_ao


def smoothstep01(u):
    u = np.clip(u, 0, 1)
    return u * u * (3 - 2 * u)


def nearest(q, ref, chunk=2000, max_ref=None, seed=0):
    """Distance and index of the nearest reference point for every query point (brute force, chunked)."""
    ref = np.asarray(ref, 'f4'); sel = np.arange(len(ref))
    if max_ref and len(ref) > max_ref:
        sel = np.sort(np.random.default_rng(seed).choice(len(ref), max_ref, replace=False)); ref = ref[sel]
    q = np.asarray(q, 'f4'); d = np.empty(len(q), 'f4'); k = np.empty(len(q), np.int64)
    chunk = max(1, min(chunk, 4000000 // max(len(ref), 1)))
    for i in range(0, len(q), chunk):
        dd = ((q[i:i + chunk, None, :] - ref[None]) ** 2).sum(-1)
        k[i:i + chunk] = dd.argmin(1); d[i:i + chunk] = np.sqrt(dd.min(1))
    return d, sel[k]


def palette_mean(lum_row, values, weights=None):
    """Mean palette luminance of shade values (rounded to the PLT byte, as the client looks it up)."""
    v = lum_row[np.clip(np.rint(values), 0, 255).astype(int)]
    return float(v.mean()) if weights is None else float((v * weights).sum() / weights.sum())


def level_shift(samples, areas, reference, lum_rows, lo=-80.0, hi=60.0, iters=60, bias=0.0):
    """Constant shade shift d such that the area-weighted body palette luminance, averaged over the palette rows,
    equals the reference's plus `bias` (luminance units). samples/reference: {part: shade samples at the part's
    own UVs}; areas: {part: m^2}."""
    names = sorted(samples); tot = sum(areas[n] for n in names)
    def body(vals, d):
        return float(np.mean([sum(areas[n] * palette_mean(L, vals[n] + d) for n in names) / tot for L in lum_rows]))
    target = body(reference, 0.0) + bias
    f = lambda d: body(samples, d) - target
    a, b = lo, hi
    require(f(a) <= 0 <= f(b), 'Reference level outside the shift search range')
    for _ in range(iters):
        m = 0.5 * (a + b)
        if f(m) > 0:
            b = m
        else:
            a = m
    return 0.5 * (a + b), target


def contrast_gain(values, weight, disk, ring, base, target, lum_rows, gains=None):
    """Gain g for values + weight*(g-1)*(values-base) whose palette-luminance contrast (disk mean - ring mean,
    averaged over palette rows) is closest to `target`."""
    gains = np.arange(1.0, 4.0001, 0.01) if gains is None else np.asarray(gains)
    def con(g):
        v = values + weight * (g - 1) * (values - base)
        return float(np.mean([palette_mean(L, v[disk]) - palette_mean(L, v[ring]) for L in lum_rows]))
    errs = np.array([abs(con(g) - target) for g in gains]); g = float(gains[int(errs.argmin())])
    return g, con(g)


def ascii_corners(path, bitmap=None):
    """Corner positions and glTF-convention UVs of an NWN ASCII model's trimeshes (optionally one bitmap)."""
    from nwn_ascii_trimesh import AsciiModel
    am = AsciiModel.read(path); PP, TT = [], []
    for n in am.trimeshes():
        if bitmap and n.fields.get('bitmap', [''])[0].lower() != bitmap.lower():
            continue
        P, T, _ = am.corners(n); PP.append(P); TT.append(np.stack([T[..., 0], 1.0 - T[..., 1]], -1))
    require(len(PP) > 0, 'No trimesh with bitmap %s in %s' % (bitmap, path))
    return np.concatenate(PP), np.concatenate(TT)


def tri_area(P):
    return 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)


def texel_positions(UV, world, lowres):
    cen_ = world.mean(1)
    X = np.stack([raster(UV, cen_[:, k], lowres) for k in range(3)], -1)
    return X, raster(UV, np.ones(len(cen_)), lowres) > 0


def raster_interp(UV, values, size, tris):
    """Barycentric (per-texel interpolated) raster of per-corner values for the selected triangles (top-down,
    glTF UV, texel centres at (i + 0.5) / size). Returns (image, hit mask)."""
    values = np.asarray(values, 'f4'); out = np.zeros((size, size, values.shape[-1]), 'f4'); hit = np.zeros((size, size), bool)
    for t in tris:
        uv = UV[t] * size; a, b, c = uv
        x0, y0 = np.maximum(np.floor(uv.min(0)).astype(int), 0); x1, y1 = np.minimum(np.ceil(uv.max(0)).astype(int), size - 1)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if x1 < x0 or y1 < y0 or abs(den) < 1e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
        val = l1[..., None] * values[t, 0] + l2[..., None] * values[t, 1] + l3[..., None] * values[t, 2]
        yy, xx = ys[inside].astype(int), xs[inside].astype(int)
        out[yy, xx] = val[inside]; hit[yy, xx] = True
    return out, hit


def upsample(img, size):
    return np.asarray(Image.fromarray(img.astype('f4')).resize((size, size), Image.BILINEAR))


def distance_weight(UV, world, pts, fall, size, lowres=512):
    """Texel weight 1 at the given 3D points fading (smoothstep) to 0 at `fall` metres; triangle-centroid positions."""
    cen_ = world.mean(1)
    X = np.stack([raster(UV, cen_[:, k], lowres) for k in range(3)], -1); m = raster(UV, np.ones(len(cen_)), lowres) > 0
    q = X[m]; pts = np.asarray(pts, 'f4'); d = np.full(len(q), np.inf, 'f4')
    for i in range(0, len(q), 4000):
        d[i:i + 4000] = np.sqrt(((q[i:i + 4000, None, :] - pts[None]) ** 2).sum(-1)).min(1)
    u = np.clip(1 - d / fall, 0, 1); w = np.zeros((lowres, lowres), 'f4'); w[m] = u * u * (3 - 2 * u)
    wf, _ = pad(w, m, 8)
    return np.asarray(Image.fromarray(wf.astype('f4')).resize((size, size), Image.BILINEAR))


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    require(not a.output.exists(), 'Fresh output required')
    cfg = json.loads(a.config.read_text())
    for path, digest in cfg['frozen'].items():
        require(sha(path) == digest, 'Input changed: ' + path)
    out = a.output; out.mkdir(parents=True)
    (out / 'resources').mkdir(); (out / 'previews').mkdir(); (out / 'maps').mkdir()
    size = cfg.get('size', 2048); T = cfg['targets']
    palette = np.asarray(Image.open(cfg['palette']).convert('RGB'))
    parts = cfg['parts']
    data = {}
    # pass 1: per-part S0 and samples
    for name, p in parts.items():
        if p.get('kind') == 'pelvis-skin':
            mesh = None
            pdoc, pbin = read_glb(p['previewTemplate']); pr = pdoc['meshes'][0]['primitives'][p.get('skinPrimitive', 0)]
            idx_ = accessor(pdoc, pbin, pr['indices']).reshape(-1).astype(np.int64)
            P = (accessor(pdoc, pbin, pr['attributes']['POSITION']).astype(float) @ BASIS.T)[idx_].reshape(-1, 3, 3)
            UV = accessor(pdoc, pbin, pr['attributes']['TEXCOORD_0']).astype(float)[idx_].reshape(-1, 3, 2)
        else:
            mesh = Mesh(p['glb']); P, N, UV = mesh.corners()
        world = P + np.asarray(p['joint'])
        header, plt0 = plt_read(p['v1Plt'])
        cover = raster(UV, np.ones(len(UV)), size) > 0
        sp, suv = surface(world, UV, cfg.get('samples', 150000), 11)
        data[name] = dict(mesh=mesh, P=P, UV=UV, world=world, header=header, plt0=plt0, cover=cover, sp=sp, suv=suv)
    # articulated contact: no baked inter-part contact shadow next to a moving joint (parts move relative to each other)
    pairs_all = [tuple(x) for x in cfg['continuity']['pairs'] if x[0] in parts and x[1] in parts]
    contact = {}
    fade = cfg['lighting'].get('contactFadeMeters')
    if fade:
        rng0 = np.random.default_rng(3)
        for name in parts:
            partners = [b for a_, b in pairs_all if a_ == name] + [a_ for a_, b in pairs_all if b == name]
            if partners:
                pts = np.concatenate([data[q]['sp'] for q in partners])
                pts = pts[rng0.choice(len(pts), size=min(len(pts), 4000), replace=False)]
                contact[name] = distance_weight(data[name]['UV'], data[name]['world'], pts, fade, size)
    for name, p in parts.items():
        row = data[name]; mesh, P, UV, world, plt0, cover, suv = (row[k] for k in ('mesh', 'P', 'UV', 'world', 'plt0', 'cover', 'suv'))
        if p.get('kind') == 'pelvis-skin':
            # skin primitive only (the briefs use their own texture); the v1 shade is the albedo proxy
            L = plt0[:, :, 0].astype('f4')
            row['skinMask'] = (plt0[:, :, 1] == 0) & cover
            row['L'] = L
            S0, row['aoSamples'] = lit(L, p, suv, cfg, size, cover, None, contact.get(name)) if p.get('bake') else (L, None)
        else:
            doc = mesh.doc
            mat = doc['materials'][0]
            base = np.asarray(glb_image(doc, mesh.binary, doc['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']).convert('RGB'), 'f4')
            if base.shape[0] != size:
                base = np.asarray(Image.fromarray(base.astype(np.uint8)).resize((size, size), Image.BILINEAR), 'f4')
            L = base @ LUMA
            if p.get('lumaContrast'):
                m = L[cover].mean(); L = m + (L - m) * p['lumaContrast']
            # crease bands: valley-only texture fill
            wmap = np.zeros((size, size), 'f4')
            for band in p.get('creaseBands', []):
                src = Mesh(band['geometryMaster'])
                cyl = Cylinder([0, 0, 0], [0, 0, 1], src.U, -0.5, 0.1, step=0.005)
                from fair_target_crease_band import weights
                wv = weights(cyl, src.U, band)
                fw = wv[src.F].mean(1)
                # corner order of the final mesh equals the master order (position-only chain)
                sel = fw > 0
                wmap = np.maximum(wmap, raster(UV[sel], fw[sel], size))
            if wmap.any():
                Lb = blur(L, p.get('creaseBlurPx', 6), cover)
                L = L + wmap * np.maximum(0, Lb - L)
            row['creaseWeight'] = wmap
            # islands for rebuilt faces: mean albedo of retained skin within islandRadius of the island
            if p.get('faceSource'):
                fs = np.load(p['faceSource']); newf = fs < 0
                isl = raster(UV[newf], np.ones(newf.sum()), size) > 0
                isl = np.asarray(Image.fromarray(isl.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))) > 0
                cen = world[newf].mean(axis=1).mean(0)
                near = np.linalg.norm(world.mean(1) - cen, axis=1) < p.get('islandRadius', 0.08)
                nearv = sample(L, UV[near & ~newf].reshape(-1, 2))
                L[isl] = float(np.median(nearv))
                row['island'] = isl
            S0, row['aoSamples'] = lit(L, p, suv, cfg, size, cover, wmap if wmap.any() else None, contact.get(name))
            row['skinMask'] = cover
            row['L'] = L
        row['S0'] = S0
        sv = sample(S0, suv)
        row['mu'], row['sigma'] = float(sv.mean()), float(sv.std())
        data[name] = row
    # fixed partners (unchanged neighbouring resources, e.g. the stock neck): their shade is data, never edited
    fixed = cfg.get('fixedPartners', {})
    for name, f in fixed.items():
        P, UV = ascii_corners(f['ascii'], f.get('bitmap'))
        world = P + np.asarray(f['joint'])
        _, plt0 = plt_read(f['plt'])
        sp, suv = surface(world, UV, cfg.get('samples', 150000), 11)
        data[name] = dict(fixed=True, P=P, UV=UV, world=world, plt0=plt0, sp=sp, suv=suv, shade=plt0[:, :, 0].astype('f4'))
    LUMP = palette.astype('f4') @ LUMA
    lum_rows = [LUMP[r_] for r_ in cfg['paletteRows']]
    # pass 2: base calibration and contact bands
    def calibrated(name, offset=0.0):
        if data[name].get('fixed'):
            return data[name]['shade']
        r = data[name]; p = parts[name]
        tm, ts = T['mean'], T['std'] * p.get('stdScale', 1.0)
        return tm + (r['S0'] - r['mu']) * ts / max(r['sigma'], 1e-6) + offset
    cell = cfg['continuity'].get('cell', 0.008)
    def keys_of(pts):
        q = np.floor(pts / cell).astype(np.int64) + 100000
        return (q[:, 0] * 400000 + q[:, 1]) * 400000 + q[:, 2]
    def band_mean(a_name, b_name):
        """Samples of A whose voxel (or a 26-neighbour voxel) contains samples of B: the contact band."""
        A, B = data[a_name], data[b_name]
        qb = np.floor(B['sp'] / cell).astype(np.int64)
        offs = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)])
        dil = np.unique((qb[:, None, :] + offs[None]).reshape(-1, 3), axis=0)
        kb = keys_of(dil * cell + cell / 2)
        near = np.isin(keys_of(A['sp']), kb)
        # only the visible surface counts: tucked terminals hidden inside the partner are fully occluded (AO ~ 0)
        if A.get('aoSamples') is not None:
            near &= A['aoSamples'] > cfg['continuity'].get('visibleAO', 0.45)
        return near
    pairs = [tuple(x) for x in cfg['continuity']['pairs'] if x[0] in data and x[1] in data]
    names = list(parts); idx = {n: i for i, n in enumerate(names)}
    bands = {}
    rows_A, rhs = [], []
    lam = cfg['continuity'].get('lambda', 0.05)
    for a_name, b_name in pairs:
        na = band_mean(a_name, b_name); nb = band_mean(b_name, a_name)
        if na.sum() < 50 or nb.sum() < 50:
            continue
        ma = float(sample(calibrated(a_name), data[a_name]['suv'][na]).mean()); mb = float(sample(calibrated(b_name), data[b_name]['suv'][nb]).mean())
        bands[(a_name, b_name)] = (na, nb)
        fa, fb = data[a_name].get('fixed', False), data[b_name].get('fixed', False)
        if fa and fb:
            continue
        # a fixed partner has no offset variable: its contact band is a constant target for the movable side
        wgt = float(cfg['continuity'].get('fixedWeight', 1.0)) if (fa or fb) else 1.0
        row = np.zeros(len(names))
        if not fa:
            row[idx[a_name]] = 1
        if not fb:
            row[idx[b_name]] = -1
        rows_A.append(row * wgt); rhs.append((mb - ma) * wgt)
    for n in names:
        row = np.zeros(len(names)); row[idx[n]] = np.sqrt(lam); rows_A.append(row); rhs.append(0.0)
    offsets = np.linalg.lstsq(np.asarray(rows_A), np.asarray(rhs), rcond=None)[0]
    offsets = np.clip(offsets, -cfg['continuity'].get('maxOffset', 15), cfg['continuity'].get('maxOffset', 15))
    report = dict(kind='target-skin-material-composition', config=str(a.config), configSha256=sha(a.config), helperSha256=sha(__file__),
                  targets=T, offsets={n: float(offsets[idx[n]]) for n in names}, parts={}, continuity=[], localSeamCorrections=[])
    # local seam correction: the residual contact-band difference is split between both parts as a smooth field
    # that is full at the contact band and fades to zero at `falloff` metres from it (surface distance proxy: 3D)
    corr = {n: np.zeros((size, size), 'f4') for n in names}
    seam_pts = {}
    seam_unit = {}   # (a, b) -> {part: low-res unit falloff map} for the optional luminance-space refinement
    local = cfg['continuity'].get('local')
    if local:
        lowres = local.get('resolution', 512); fall = local['falloff']
        texpos = {}
        for n in names:
            cen_ = data[n]['world'].mean(1)
            X = np.stack([raster(data[n]['UV'], cen_[:, k], lowres) for k in range(3)], -1)
            texpos[n] = (X, raster(data[n]['UV'], np.ones(len(cen_)), lowres) > 0)
        rng = np.random.default_rng(5)
        for (a_name, b_name), (na, nb) in bands.items():
            if data[a_name].get('fixed') or data[b_name].get('fixed'):
                continue   # fixed partners: see the neckline blend below (only the movable side changes)
            ma = float(sample(calibrated(a_name, offsets[idx[a_name]]), data[a_name]['suv'][na]).mean())
            mb = float(sample(calibrated(b_name, offsets[idx[b_name]]), data[b_name]['suv'][nb]).mean())
            res = ma - mb
            pts = np.concatenate([data[a_name]['sp'][na], data[b_name]['sp'][nb]])
            pts = pts[rng.choice(len(pts), size=min(len(pts), local.get('bandPoints', 1500)), replace=False)].astype('f4')
            # residual per band point (angularly resolved): local mean of A minus local mean of B within `pointRadius`
            rp = np.full(len(pts), res, 'f4'); seam_pts[(a_name, b_name)] = pts
            prad = local.get('pointRadius')
            if prad:
                va = sample(calibrated(a_name, offsets[idx[a_name]]), data[a_name]['suv'][na]); xa = data[a_name]['sp'][na].astype('f4')
                vb = sample(calibrated(b_name, offsets[idx[b_name]]), data[b_name]['suv'][nb]); xb = data[b_name]['sp'][nb].astype('f4')
                def local_mean(xs, vs):
                    out_ = np.full(len(pts), np.nan, 'f4')
                    for i in range(0, len(pts), 200):
                        dd = np.sqrt(((pts[i:i + 200, None, :] - xs[None]) ** 2).sum(-1)); ww = dd < prad
                        cnt = ww.sum(1); out_[i:i + 200] = np.where(cnt >= 5, (ww * vs[None]).sum(1) / np.maximum(cnt, 1), np.nan)
                    return out_
                r_ = local_mean(xa, va) - local_mean(xb, vb)
                rp = np.where(np.isnan(r_), res, r_).astype('f4')
                # smooth along the band so the correction has no point-to-point noise
                sm = np.empty_like(rp)
                for i in range(0, len(pts), 200):
                    dd = np.sqrt(((pts[i:i + 200, None, :] - pts[None]) ** 2).sum(-1)); ww = np.exp(-0.5 * (dd / prad) ** 2)
                    sm[i:i + 200] = (ww * rp[None]).sum(1) / ww.sum(1)
                rp = sm
            for nm, sign in ((a_name, -0.5), (b_name, 0.5)):
                X, m = texpos[nm]; q = X[m]
                d = np.full(len(q), np.inf, 'f4'); near_i = np.zeros(len(q), np.int64)
                for i in range(0, len(q), 4000):
                    dd = np.sqrt(((q[i:i + 4000, None, :] - pts[None]) ** 2).sum(-1))
                    near_i[i:i + 4000] = dd.argmin(1); d[i:i + 4000] = dd.min(1)
                u = np.clip(1 - d / fall, 0, 1); w = np.zeros((lowres, lowres), 'f4'); w[m] = u * u * (3 - 2 * u) * rp[near_i]
                wf, _ = pad(w, m, 8)
                W = np.asarray(Image.fromarray(wf.astype('f4')).resize((size, size), Image.BILINEAR))
                corr[nm] += sign * W
                wu = np.zeros((lowres, lowres), 'f4'); wu[m] = u * u * (3 - 2 * u); seam_unit.setdefault((a_name, b_name), {})[nm] = pad(wu, m, 8)[0]
            report['localSeamCorrections'].append(dict(pair=[a_name, b_name], residualBeforeLocal=res, falloffMeters=fall,
                                                       pointResidualRange=[float(rp.min()), float(rp.max())]))
    X = {n: calibrated(n, offsets[idx[n]]) + corr[n] for n in names}
    # global level (optional): one constant shade shift for every movable part so that the area-weighted body
    # palette luminance (mean over the palette rows) equals the reference PLTs sampled at the same UVs
    lvl = T.get('matchReference')
    if lvl:
        refparts = [n for n in names if n in lvl.get('parts', names)]
        areas = {n: float(tri_area(data[n]['world']).sum()) for n in refparts}
        cur = {n: sample(X[n], data[n]['suv']) for n in refparts}
        ref = {n: sample(data[n]['plt0'][:, :, 0].astype('f4'), data[n]['suv']) for n in refparts}
        bias = float(lvl.get('luminanceBias', 0.0))
        shift, target_lum = level_shift(cur, areas, ref, lum_rows, bias=bias)
        for n in names:
            X[n] = X[n] + shift
        report['level'] = dict(reference=lvl.get('reference', 'v1Plt'), parts=refparts, areasM2=areas, shift=shift, luminanceBias=bias,
                               biasEvidence=lvl.get('biasEvidence'),
                               targetLuminanceMeanOfRows=target_lum, rows=cfg['paletteRows'])
    # fixed-partner neckline blend: the movable part's low-frequency shade is blended toward the fixed partner's
    # band tone (angularly resolved) with a smoothstep falloff; texture detail (shade - blur) is kept
    report['fixedBlends'] = []
    for (a_name, b_name), (na, nb) in bands.items():
        fa, fb = data[a_name].get('fixed', False), data[b_name].get('fixed', False)
        if fa == fb:
            continue
        mv, fx = (b_name, a_name) if fa else (a_name, b_name)
        bc = fixed[fx].get('blend')
        if not bc:
            continue
        A, F = data[mv], data[fx]
        br = bc.get('bandRadius', 0.01); fbr = bc.get('fixedBandRadius', br)
        lo_, hi_ = F['sp'].min(0) - br, F['sp'].max(0) + br
        candA = np.where(((A['sp'] >= lo_) & (A['sp'] <= hi_)).all(1))[0]
        dA, _ = nearest(A['sp'][candA], F['sp'], max_ref=20000); selA = candA[dA < br]
        dF, _ = nearest(F['sp'], A['sp'][candA], max_ref=20000); selF = np.where(dF < fbr)[0]
        require(len(selA) >= 50 and len(selF) >= 50, 'Fixed-partner band too small: %s/%s' % (mv, fx))
        xf = F['sp'][selF].astype('f4'); vf = sample(F['shade'], F['suv'][selF])
        rng = np.random.default_rng(7)
        pts = A['sp'][selA][rng.choice(len(selA), min(len(selA), bc.get('bandPoints', 1500)), replace=False)].astype('f4')
        prad = bc.get('pointRadius', 0.02)
        tone = np.empty(len(pts), 'f4')
        for i in range(0, len(pts), 200):
            dd = np.sqrt(((pts[i:i + 200, None, :] - xf[None]) ** 2).sum(-1)); ww = dd < prad; cnt = ww.sum(1)
            tone[i:i + 200] = np.where(cnt >= 5, (ww * vf[None]).sum(1) / np.maximum(cnt, 1), vf[dd.argmin(1)])
        sm = np.empty_like(tone)
        for i in range(0, len(pts), 200):
            dd = np.sqrt(((pts[i:i + 200, None, :] - pts[None]) ** 2).sum(-1)); ww = np.exp(-0.5 * (dd / prad) ** 2)
            sm[i:i + 200] = (ww * tone[None]).sum(1) / ww.sum(1)
        tone = sm
        lowres = bc.get('resolution', 512); fall = bc['falloff']
        Xp, m = texel_positions(A['UV'], A['world'], lowres)
        d, k = nearest(Xp[m], pts)
        core = float(bc.get('core', 0.0))   # full blend within `core` metres of the band, smoothstep to 0 at `falloff`
        w = smoothstep01(1 - np.maximum(d - core, 0) / (fall - core)) * float(bc.get('strength', 1.0))
        Wm = np.zeros((lowres, lowres), 'f4'); Tm = np.zeros((lowres, lowres), 'f4'); Wm[m] = w; Tm[m] = w * tone[k]
        Wm, _ = pad(Wm, m, 8); Tm, _ = pad(Tm, m, 8)
        Wf, Tf = upsample(Wm, size), upsample(Tm, size)
        Bm = blur(X[mv], bc.get('detailSigmaPx', 12), A['cover'])
        before = sample(X[mv], A['suv'][selA])
        keep = float(bc.get('detailKeep', 1.0))   # share of texture detail (shade - blur) kept where the blend is full
        X[mv] = X[mv] + Tf - Wf * Bm - (1.0 - keep) * Wf * (X[mv] - Bm)
        report['fixedBlends'].append(dict(movable=mv, fixed=fx, falloffMeters=fall, coreMeters=core, detailKeep=keep, pointRadius=prad, detailSigmaPx=bc.get('detailSigmaPx', 12),
                                          strength=float(bc.get('strength', 1.0)), movableBandSamples=int(len(selA)), fixedBandSamples=int(len(selF)),
                                          fixedBandShade=float(vf.mean()), toneRange=[float(tone.min()), float(tone.max())],
                                          movableBandShadeBefore=float(before.mean()), movableBandShadeAfter=float(sample(X[mv], A['suv'][selA]).mean())))
    # feature contrast (optional, per part): deviations from the surrounding ring inside a disk are scaled so the
    # palette-luminance contrast matches the reference PLT (v1) at the same UVs
    report['featureContrast'] = []
    for name in names:
        for fc in parts[name].get('featureContrast', []):
            r = data[name]; c = np.asarray(fc['center'], 'f4'); r0, r1 = fc['radius'], fc['outerRadius']; ring = fc['ring']
            require(r1 < ring[0], 'Feature weight must vanish before its baseline ring')
            ds = np.linalg.norm(r['sp'] - c, axis=1); disk = ds < r0; ringm = (ds > ring[0]) & (ds < ring[1])
            ws = 1 - smoothstep01((ds - r0) / (r1 - r0))
            Xs = sample(X[name], r['suv']); base = float(Xs[ringm].mean())
            Vs = sample(r['plt0'][:, :, 0].astype('f4'), r['suv'])
            refc = float(np.mean([palette_mean(L, Vs[disk]) - palette_mean(L, Vs[ringm]) for L in lum_rows]))
            beforec = float(np.mean([palette_mean(L, Xs[disk]) - palette_mean(L, Xs[ringm]) for L in lum_rows]))
            if 'gain' in fc:
                g = float(fc['gain']); v_ = Xs + ws * (g - 1) * (Xs - base)
                afterc = float(np.mean([palette_mean(L, v_[disk]) - palette_mean(L, v_[ringm]) for L in lum_rows]))
            else:
                g, afterc = contrast_gain(Xs, ws, disk, ringm, base, refc, lum_rows)
            near_t = np.where(np.linalg.norm(r['world'].mean(1) - c, axis=1) < r1 + 0.03)[0]
            pos, hit = raster_interp(r['UV'], r['world'], size, near_t)
            Wt = np.zeros((size, size), 'f4'); Wt[hit] = 1 - smoothstep01((np.linalg.norm(pos[hit] - c, axis=1) - r0) / (r1 - r0))
            Wt, _ = pad(Wt, hit, 4)
            X[name] = X[name] + Wt * (g - 1) * (X[name] - base)
            report['featureContrast'].append(dict(part=name, label=fc.get('label'), center=fc['center'], radius=r0, outerRadius=r1, ring=ring,
                                                  gain=g, ringBaseShade=base, contrastLuminanceMeanOfRows=dict(reference=refc, before=beforec, after=afterc),
                                                  diskSamples=int(disk.sum()), ringSamples=int(ringm.sum()), triangles=int(len(near_t))))
    # optional luminance-space refinement of the joint seams: the level shift moves every part along the palette's
    # nonlinear luminance curve, so contact bands matched in shade units can drift apart in luminance; each pair's
    # remaining band difference (mean of the palette rows) is converted to shade with the local palette slope and
    # split between both parts with the same smooth falloff maps as the local seam correction (Gauss-Seidel sweeps)
    report['luminanceRefinement'] = []
    if local and local.get('luminanceRefine'):
        lr = local.get('resolution', 512)
        for sweep in range(int(local.get('luminanceRefineSweeps', 3))):
            for (a_name, b_name), (na, nb) in bands.items():
                if (a_name, b_name) not in seam_unit:
                    continue
                va = sample(X[a_name], data[a_name]['suv'][na]); vb = sample(X[b_name], data[b_name]['suv'][nb])
                diff = float(np.mean([palette_mean(L, va) - palette_mean(L, vb) for L in lum_rows]))
                slope = float(np.mean([(palette_mean(L, v + 2) - palette_mean(L, v - 2)) / 4 for L in lum_rows for v in (va, vb)]))
                s = diff / max(slope, 0.05)
                for nm, sign in ((a_name, -0.5), (b_name, 0.5)):
                    X[nm] = X[nm] + sign * s * upsample(seam_unit[(a_name, b_name)][nm], size)
                report['luminanceRefinement'].append(dict(sweep=sweep, pair=[a_name, b_name], luminanceDiffBefore=diff, paletteSlope=slope, shadeCorrection=s))
    shades = {}
    for fx in fixed:
        shades[fx] = (data[fx]['shade'], np.ones(data[fx]['shade'].shape, bool))
    for name, p in parts.items():
        r = data[name]
        sh = soft_limit(X[name], T['clipLow'], T['clipHigh'])
        valid = r['skinMask']
        sh, ok = pad(sh * valid, valid, cfg.get('padSteps', 16))
        shades[name] = (sh, ok)
    # pass 3: write maps, previews, stats
    for name, p in parts.items():
        r = data[name]; sh, ok = shades[name]
        plt = r['plt0'].copy()
        # shade byte only; the palette-layer byte of every texel is kept from v1 (tattoo/other layers survive)
        write = r['skinMask'] if p.get('kind') == 'pelvis-skin' else ok
        plt[write, 0] = np.clip(np.rint(sh[write]), 0, 255).astype(np.uint8)
        res = out / 'resources' / (p['model'] + '.plt'); plt_write(res, r['header'], plt)
        nmeta, nimg = tga_read(p['v1Normal']); rmeta, rimg = tga_read(p['v1Rough'])
        nf = nimg.astype('f4') / 255 * 2 - 1
        gain = 1.0
        if p.get('kind') != 'pelvis-skin':
            cur = float(np.median(tilt(nimg, r['suv'])))
            gain = 1.0 if p.get('normalGain') == 1 else float(np.clip(cfg['normal']['targetMedianTilt'] / max(cur, 1e-3), 1.0, cfg['normal']['maxGain']))
            if 'normalGain' in p and p['normalGain'] != 'auto':
                gain = float(p['normalGain'])
            xy = nf[:, :, :2] * gain; xy_len = np.linalg.norm(xy, axis=2, keepdims=True)
            xy = np.where(xy_len > 0.95, xy / np.maximum(xy_len, 1e-9) * 0.95, xy)
            nf = np.concatenate([xy, np.sqrt(np.clip(1 - (xy ** 2).sum(2, keepdims=True), 0, 1))], 2)
            w = r.get('creaseWeight')
            if w is not None and w.any():
                nb_ = blur(nf, cfg['normal'].get('creaseBlurPx', 5), r['cover'])
                # optional flattening inside crease bands: painted crease lines in the normal map are removed, not just softened
                fl = float(cfg['normal'].get('creaseFlatten', 0.0))
                if fl:
                    nb_ = nb_ * (1 - fl) + np.array([0, 0, 1], 'f4') * fl
                nf = nf * (1 - w[..., None]) + nb_ * w[..., None]
            if r.get('island') is not None:
                nf[r['island']] = [0, 0, 1]
            nf /= np.linalg.norm(nf, axis=2, keepdims=True) + 1e-9
        nout = np.clip(np.rint((nf + 1) / 2 * 255), 0, 255).astype(np.uint8)
        rout = rimg.copy()
        if p.get('roughnessMatch') and p['roughnessMatch'] in parts:
            refp = parts[p['roughnessMatch']]; _, refimg = tga_read(refp['v1Rough']); ref = data[p['roughnessMatch']]
            rv = sample(refimg[:, :, 0].astype('f4'), ref['suv']); hv = sample(rimg[:, :, 0].astype('f4'), r['suv'])
            mapped = rv.mean() + (rimg[:, :, 0].astype('f4') - hv.mean()) * (rv.std() / max(hv.std(), 1e-6))
            rout = np.repeat(np.clip(np.rint(mapped), 0, 255).astype(np.uint8)[..., None], 3, 2)
        if r.get('island') is not None:
            ring = sample(rimg[:, :, 0].astype('f4'), r['suv']).mean(); rout[r['island']] = int(round(ring))
        tga_write(out / 'resources' / (p['model'] + 'n.tga'), nmeta, nout)
        tga_write(out / 'resources' / (p['model'] + 'r.tga'), rmeta, rout)
        shv = sample(sh, r['suv'])
        prow = dict(model=p['model'], plt={'path': str(res), 'sha256': sha(res)},
                    normal={'path': str(out / 'resources' / (p['model'] + 'n.tga')), 'gain': gain},
                    roughness={'path': str(out / 'resources' / (p['model'] + 'r.tga')), 'matchedTo': p.get('roughnessMatch')},
                    shadeAtUVs=stats(shv), clippedTexels=int(((plt[write, 0] == 0) | (plt[write, 0] == 255)).sum()),
                    offset=float(offsets[idx[name]]), s0Mean=r['mu'], s0Std=r['sigma'],
                    paletteLuminanceAtUVs={'skin%d' % rw: dict(new=palette_mean(LUMP[rw], shv), v1=palette_mean(LUMP[rw], sample(r['plt0'][:, :, 0].astype('f4'), r['suv'])))
                                           for rw in cfg['paletteRows']})
        if p.get('kind') != 'pelvis-skin':
            prow['normalTiltMedianDeg'] = {'v1': float(np.median(tilt(nimg, r['suv']))), 'm4': float(np.median(tilt(nout, r['suv'])))}
            prow['roughnessMean'] = {'v1': float(sample(rimg[:, :, 0].astype('f4'), r['suv']).mean()), 'm4': float(sample(rout[:, :, 0].astype('f4'), r['suv']).mean())}
        # previews: colourized PLT at each palette row
        for prow_ in cfg['paletteRows']:
            rgb = palette[prow_, plt[:, :, 0]]
            if p.get('kind') == 'pelvis-skin':
                write_pelvis_preview(p, rgb, nout, rout, out / 'previews' / ('%s-skin%d.glb' % (name, prow_)))
            else:
                write_part_preview(p, r['mesh'], rgb, nout, rout, out / 'previews' / ('%s-skin%d.glb' % (name, prow_)))
        report['parts'][name] = prow
    # continuity at palette rows (luminance of the palette lookup in each contact band)
    for (a_name, b_name), (na, nb) in bands.items():
        entry = dict(pair=[a_name, b_name])
        for rowp in cfg['paletteRows']:
            def lum(nm, sel):
                s_ = np.clip(np.rint(sample(shades[nm][0], data[nm]['suv'][sel])), 0, 255).astype(int)
                return float((palette[rowp, s_] @ LUMA).mean())
            v1 = {}
            for nm, sel in ((a_name, na), (b_name, nb)):
                s1 = data[nm]['plt0'][:, :, 0].astype('f4'); v1[nm] = float((palette[rowp, np.clip(np.rint(sample(s1, data[nm]['suv'][sel])), 0, 255).astype(int)] @ LUMA).mean())
            entry['skin%d' % rowp] = dict(m4=[lum(a_name, na), lum(b_name, nb)], v1=[v1[a_name], v1[b_name]],
                                          m4Diff=lum(a_name, na) - lum(b_name, nb), v1Diff=v1[a_name] - v1[b_name])
        if (a_name, b_name) in seam_pts:
            # local (angular) shade residual at the seam: |mean A - mean B| within 1.5 cm of each band point, PLT shade units
            pts_ = seam_pts[(a_name, b_name)]; loc = {}
            for nm, sel in ((a_name, na), (b_name, nb)):
                xs = data[nm]['sp'][sel].astype('f4'); vs = sample(shades[nm][0], data[nm]['suv'][sel]); o_ = np.full(len(pts_), np.nan)
                for i in range(0, len(pts_), 200):
                    dd = np.sqrt(((pts_[i:i + 200, None, :] - xs[None]) ** 2).sum(-1)); ww = dd < 0.015; cnt = ww.sum(1)
                    o_[i:i + 200] = np.where(cnt >= 5, (ww * vs[None]).sum(1) / np.maximum(cnt, 1), np.nan)
                loc[nm] = o_
            dv = np.abs(loc[a_name] - loc[b_name]); dv = dv[~np.isnan(dv)]
            v1loc = {}
            for nm, sel in ((a_name, na), (b_name, nb)):
                xs = data[nm]['sp'][sel].astype('f4'); vs = sample(data[nm]['plt0'][:, :, 0].astype('f4'), data[nm]['suv'][sel]); o_ = np.full(len(pts_), np.nan)
                for i in range(0, len(pts_), 200):
                    dd = np.sqrt(((pts_[i:i + 200, None, :] - xs[None]) ** 2).sum(-1)); ww = dd < 0.015; cnt = ww.sum(1)
                    o_[i:i + 200] = np.where(cnt >= 5, (ww * vs[None]).sum(1) / np.maximum(cnt, 1), np.nan)
                v1loc[nm] = o_
            dv1 = np.abs(v1loc[a_name] - v1loc[b_name]); dv1 = dv1[~np.isnan(dv1)]
            if len(dv) and len(dv1):
                entry['localShadeResidual'] = dict(m4P50=float(np.median(dv)), m4P95=float(np.percentile(dv, 95)),
                                                   v1P50=float(np.median(dv1)), v1P95=float(np.percentile(dv1, 95)))
        report['continuity'].append(entry)
    write_receipt(out / 'material.json', report)
    shutil.copy2(__file__, out / 'executed-helper.py'); shutil.copy2(a.config, out / 'executed-config.json')
    print(json.dumps({'offsets': report['offsets'], 'parts': {k: (round(v['shadeAtUVs']['mean'], 1), round(v['shadeAtUVs']['std'], 1), round(v['shadeAtUVs']['p1'], 1), v['clippedTexels']) for k, v in report['parts'].items()},
                      'continuity': [(c['pair'], round(c['skin3']['m4Diff'], 1), round(c['skin3']['v1Diff'], 1)) for c in report['continuity']]}, indent=1))


def png(img):
    b = BytesIO(); Image.fromarray(img).save(b, format='PNG'); return b.getvalue()


def replace_images(doc, binary, mapping):
    for index, img in mapping.items():
        data = png(img)
        binary.extend(b'\0' * (-len(binary) % 4)); off = len(binary); binary.extend(data)
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data)})
        doc['images'][index] = {'bufferView': len(doc['bufferViews']) - 1, 'mimeType': 'image/png'}


def mr_image(rout):
    mr = np.zeros_like(rout); mr[:, :, 0] = 255; mr[:, :, 1] = rout[:, :, 0]; mr[:, :, 2] = 0
    return mr


def write_part_preview(p, mesh, rgb, nout, rout, path):
    doc, binary = read_glb(p['previewTemplate']); doc = copy.deepcopy(doc); binary = bytearray(binary)
    P, N, T = mesh.corners()
    prim = doc['meshes'][0]['primitives'][0]
    Nn = N.reshape(-1, 3); Nn = Nn / np.maximum(np.linalg.norm(Nn, axis=1), 1e-12)[:, None]
    prim['attributes'] = {'POSITION': append_accessor(doc, binary, (P.reshape(-1, 3) @ BASIS).astype('<f4'), 'POSITION'),
                          'NORMAL': append_accessor(doc, binary, (Nn @ BASIS).astype('<f4'), 'NORMAL'),
                          'TEXCOORD_0': append_accessor(doc, binary, T.reshape(-1, 2).astype('<f4'), 'TEXCOORD_0')}
    prim['indices'] = append_accessor(doc, binary, np.arange(len(P) * 3, dtype='<u4').reshape(-1, 1))
    mat = doc['materials'][prim.get('material', 0)]
    replace_images(doc, binary, {doc['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']: rgb,
                                 doc['textures'][mat['normalTexture']['index']]['source']: nout,
                                 doc['textures'][mat['pbrMetallicRoughness']['metallicRoughnessTexture']['index']]['source']: mr_image(rout)})
    write_glb(Path(path), doc, binary)


def write_pelvis_preview(p, rgb, nout, rout, path):
    doc, binary = read_glb(p['previewTemplate']); doc = copy.deepcopy(doc); binary = bytearray(binary)
    mat = doc['materials'][p.get('skinMaterial', 0)]
    replace_images(doc, binary, {doc['textures'][mat['pbrMetallicRoughness']['baseColorTexture']['index']]['source']: rgb})
    write_glb(Path(path), doc, binary)


if __name__ == '__main__':
    main()
