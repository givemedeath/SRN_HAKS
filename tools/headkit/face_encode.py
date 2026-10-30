"""PLT channels and colour treatment from the face masks (steps 2-3 of docs/heads/head-texture-quality-plan.md).

Channel roles (user rule 2026-10-29): iris -> tattoo1 (8); eye whites, lids, lips and nose -> skin (0); brows and hair locks ->
hair (1); other channels as owned. Each boundary sits in a dark line painted on both sides (iris rim, lid line, brow edge), and
each 4x4 block of 4K texels takes its 1K colour only from texels of its majority channel."""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation
from scipy.spatial import cKDTree
from .common import require
from .textures import surface, pad
from .uv import chart_ids, face_region

NEAR_EYE = 12   # 4K texels around the eye opening where hair-owned lash lines and old tattoo iris rings become skin (RUNBOOK 129)
CHANNEL_MASKS = ('iris', 'eye', 'brow', 'skin', 'lips', 'nose', 'hairlock')
TREATMENT_MASKS = ('iris', 'eye', 'brow', 'lips', 'nose', 'lipline', 'socket')
TREATMENT = {'delight': .8, 'smooth': .7, 'lipDark': .5, 'socket': .3, 'irisRim': .45, 'lidLine': .6, 'browEdge': .95}
BROW_FRINGE = .02   # head widths around the brow searched for leftover brow colour on skin


def luma(x): return x@np.array([.299, .587, .114], np.float32)


def masks_at(files, names):
    """Soft 4K masks (0..1) from the masks stage."""
    out = {}
    for name in names:
        with Image.open(files[name]['path']) as image:
            require(image.mode == 'L' and image.size == (4096, 4096), '4K L feature mask required: '+name); out[name] = np.asarray(image, np.float32)/255
    return out


def apply_channels(labels, masks, mapped):
    """Channel moves from the masks on a 4K ownership atlas; gutters re-padded so chart-border 1K blocks follow the edits."""
    o = labels.copy(); before = labels
    iris = masks['iris'] > .5; eye = masks['eye'] > .5; brow = (masks['brow'] > .5) & mapped
    skinlike = ((masks['skin'] > .5) | eye | (masks['lips'] > .5) | (masks['nose'] > .5)) & ~brow & ~iris
    near_eye = binary_dilation(eye, iterations=NEAR_EYE) & mapped
    ring = near_eye & ~iris & np.isin(o, (8, 9)); lash = near_eye & ~brow & (o == 1)
    report = {'oldIrisRingToSkin': int(ring.sum()), 'lashToSkin': int(lash.sum())}
    o[ring] = 0; o[lash] = 0
    o[skinlike & (o == 1)] = 0; o[eye & ~iris] = 0; o[brow & (o == 0)] = 1; o[iris] = 8
    lock = (masks['hairlock'] > .5) & mapped & (o == 0) & ~near_eye; report['hairLockToHair'] = int(lock.sum()); o[lock] = 1
    o = pad(o[..., None], mapped)[..., 0]
    report['moved'] = {f'{a}->{b}': int(((before == a) & (o == b) & mapped).sum()) for a in range(10) for b in range(10)
                       if a != b and ((before == a) & (o == b) & mapped).any()}
    return o, report


def majority(labels, block=4):
    """1K ownership: the majority channel of each 4x4 block of 4K texels (ties to the lowest id)."""
    n = labels.shape[0]//block; blocks = labels.reshape(n, block, n, block).transpose(0, 2, 1, 3).reshape(n, n, block*block)
    return np.stack([(blocks == k).sum(-1) for k in range(10)], -1).argmax(-1).astype(np.uint8)


def consistent_blocks(colour, labels, block=4):
    """Texels of a 4x4 block outside its majority channel take the majority texels' mean, so the 1K box filter never mixes
    channels (skin mixed into a hair edge texel ranks as the brightest hair shade: white dots, RUNBOOK 125)."""
    n = labels.shape[0]//block; blocks = labels.reshape(n, block, n, block).transpose(0, 2, 1, 3).reshape(n, n, block*block)
    top = majority(labels, block); cb = colour.reshape(n, block, n, block, 3).transpose(0, 2, 1, 3, 4).reshape(n, n, block*block, 3)
    same = blocks == top[..., None]; mean = (cb*same[..., None]).sum(2)/np.maximum(same.sum(2), 1)[..., None]
    cb = np.where(same[..., None], cb, mean[:, :, None, :])
    return cb.reshape(n, n, block, block, 3).transpose(0, 2, 1, 3, 4).reshape(colour.shape), int((~same).any(-1).sum())


def _surface_mean(points, values, k):
    """Mean of values over each point's k nearest 3D neighbours, from a 1/16 subsample, inverse-distance interpolated (k=8)."""
    sub = np.arange(0, len(points), 16); tree = cKDTree(points[sub]); _, nb = tree.query(points[sub], k=min(k, len(sub)))
    sampled = values[sub][nb].mean(1); distance, near = tree.query(points, k=min(8, len(sub))); w = 1/np.maximum(distance, 1e-9)
    return (sampled[near]*(w if sampled.ndim == 1 else w[..., None])).sum(1)/(w.sum(1) if sampled.ndim == 1 else w.sum(1)[:, None])


def treat(colour, labels, masks, value, settings=None):
    """Step 3 on a 4K colour atlas (0..255) with the final 4K ownership: darken-only broad de-light, skin smoothing away from the
    features, lip line and eye-socket darks, iris rim, lid line, brows in the hair mid tones with a darker outer edge and their
    skin fringe refilled from plain skin on the surface; then ownership-consistent blocks."""
    s = dict(TREATMENT, **(settings or {})); require(set(s) == set(TREATMENT) and all(0 <= v <= 1 for v in s.values()), 'Unknown face treatment setting')
    P = value['positions'].astype(float); F = value['faces']; width = np.ptp(P[:, 0])
    positions, owners, _ = surface(value, 4096, enforce=False); mapped = owners >= 0; fid = np.maximum(owners, 0)
    onface = mapped & face_region(P, F)[0][fid]; c = colour.astype(np.float32).copy(); o = labels; report = {}
    iris = masks['iris'] > .5; eye = masks['eye'] > .5; brow = (masks['brow'] > .5) & mapped
    if s['delight'] and (mapped & (o == 0) & onface).sum() > 16:
        # Darken only: broad baked highlights come down; shaded sides keep their form shading (lifting them read as cheek patches).
        sy, sx = np.nonzero(mapped & (o == 0) & onface); broad = _surface_mean(positions[sy, sx].astype(float), luma(c[sy, sx]), 256)
        gain = np.minimum(1.0, (np.median(broad)/np.maximum(broad, 1))**s['delight']); c[sy, sx] *= np.clip(gain, .6, 1)[:, None]
        report['delightGainP5P95'] = np.percentile(gain, [5, 95]).round(3).tolist()
    if s['smooth'] and (mapped & (o == 0)).sum() > 16:
        sy, sx = np.nonzero(mapped & (o == 0)); col = c[sy, sx]; local = _surface_mean(positions[sy, sx].astype(float), col, 32)
        near = np.clip(gaussian_filter(np.maximum.reduce([masks[k] for k in ('brow', 'eye', 'lips', 'nose')]), 24)*3, 0, 1)
        c[sy, sx] = local+(col-local)*(1-s['smooth']*(1-near[sy, sx]))[:, None]
    skin = mapped & (o == 0)
    c[skin] *= (1-s['lipDark']*masks['lipline'][skin])[:, None]; c[skin] *= (1-s['socket']*masks['socket'][skin])[:, None]
    c[iris & (gaussian_filter(iris.astype(np.float32), 3) < .8)] *= s['irisRim']
    charts = np.where(mapped, chart_ids(value['uv'], shared='vertex')[fid], -1)
    c[binary_dilation(eye, iterations=6) & ~eye & (o == 0) & np.isin(charts, np.unique(charts[eye & mapped]))] *= s['lidLine']   # eye's own charts only
    bm = brow & (o == 1); report['browFringeRefilled'] = 0
    if bm.any():
        lb = luma(c[bm]); cap = np.percentile(lb, 85); hot = np.flatnonzero(bm.ravel())[lb > cap]
        c[hot//4096, hot % 4096] *= (cap/lb[lb > cap])[:, None]   # skin-coloured texels caught in the soft mask edge: brow range
        hair = mapped & (o == 1) & ~bm
        if hair.any(): c[bm] *= np.clip((luma(c[bm])+np.median(luma(c[hair]))-np.median(luma(c[bm])))/np.maximum(luma(c[bm]), 1), 0, 4)[:, None]
        # Outer edge by surface distance to the nearest non-brow texel (UV blur would also darken chart seams inside the brow).
        by, bx = np.nonzero(bm); oy, ox = np.nonzero(binary_dilation(bm, iterations=8) & ~bm & mapped)
        if len(oy):
            edge = cKDTree(positions[oy, ox]).query(positions[by, bx], k=1)[0] < .006*width; c[by[edge], bx[edge]] *= s['browEdge']
        sy, sx = np.nonzero(mapped & (o == 0) & onface); distance, _ = cKDTree(positions[bm][::4]).query(positions[sy, sx], k=1)
        plain = (distance > BROW_FRINGE*width) & (distance < 3*BROW_FRINGE*width); ref = luma(c[sy, sx])
        if plain.any():
            fringe = (distance < BROW_FRINGE*width) & (ref < np.median(ref[plain])-12)   # darker than nearby plain skin: leftover brow colour
            if fringe.any():
                _, nn = cKDTree(positions[sy[plain], sx[plain]]).query(positions[sy[fringe], sx[fringe]], k=min(24, int(plain.sum())))
                c[sy[fringe], sx[fringe]] = c[sy[plain], sx[plain]][nn.reshape(int(fringe.sum()), -1)].mean(1)
            report['browFringeRefilled'] = int(fringe.sum())
    c, report['mixedBlocksFixed'] = consistent_blocks(np.clip(c, 0, 255), o)
    return pad(c, mapped), dict(report, settings=s)
