"""PLT channels and colour treatment from the face masks (steps 2-3 of docs/heads/head-texture-quality-plan.md).

Channel roles (user rule 2026-10-29): iris -> tattoo1 (8), and only the iris; eye whites, lids, lips and nose -> skin (0); brows,
beards and hair locks -> hair (1); other tattoo1 texels -> tattoo2 (9), which on orc and troll heads holds their tusks and horns
(user 2026-10-30: head metal/cloth/leather follow the worn armour); other channels as owned. Each boundary sits in a dark line painted on both sides (iris rim, lid line, brow edge), and
each 4x4 block of 4K texels takes its 1K colour only from texels of its majority channel."""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from .common import require
from .colour import lab
from .textures import surface, pad
from .uv import chart_ids, face_region

JOIN_SPACING = 3   # protected hair joins hair through texels within this x the atlas's median 3D texel pitch (RUNBOOK 161)
NEAR_EYE = 12   # 4K texels around the eye opening where hair-owned lash lines and old tattoo iris rings become skin (RUNBOOK 129)
CHANNEL_MASKS = ('iris', 'eye', 'brow', 'skin', 'lips', 'nose', 'hairlock', 'beard')
BEARD_RATIO = .8   # below the nose, hair-owned texels nearer the hair median than this x the skin median stay hair (RUNBOOK 145)
BEARD_LIGHTNESS = .5   # Lab L weight in that test: shading moves a beard's lightness, not its chroma
TREATMENT_MASKS = ('iris', 'eye', 'brow', 'lips', 'nose', 'lipline', 'socket')
TREATMENT = {'delight': .8, 'smooth': .7, 'lipDark': .5, 'socket': .3, 'irisRim': .45, 'lidLine': .6, 'browEdge': .95, 'scalpDelight': 0, 'browSkinRefill': 0}
BROW_FRINGE = .02   # head widths around the brow searched for leftover brow colour on skin


def luma(x): return x@np.array([.299, .587, .114], np.float32)


def masks_at(files, names):
    """Soft 4K masks (0..1) from the masks stage."""
    out = {}
    for name in names:
        require(name in files, 'Masks stage has no '+name+' mask; rerun masks with the current headkit')
        with Image.open(files[name]['path']) as image:
            require(image.mode == 'L' and image.size == (4096, 4096), '4K L feature mask required: '+name); out[name] = np.asarray(image, np.float32)/255
    return out


def beard_hair(labels, masks, mapped, colour, skinlike):
    """Hair-owned texels below the nose that the skin, lip and nose masks would take but whose colour is clearly hair (nearer
    the owned hair's Lab median than BEARD_RATIO x the parser skin's, lightness weighted BEARD_LIGHTNESS): beards and moustaches,
    which the parser calls skin."""
    candidates = skinlike & (masks['beard'] > .5) & (labels == 1) & mapped; skin = masks['skin'] > .5
    hair_ref = (labels == 1) & ~skin & ~(masks['brow'] > .5) & mapped; skin_ref = (labels == 0) & skin & mapped
    if not candidates.any() or not hair_ref.any() or not skin_ref.any(): return np.zeros_like(candidates)
    weighted = lambda rgb: lab(rgb)*[BEARD_LIGHTNESS, 1, 1]; median = lambda sel: np.median(weighted(colour[sel][::max(1, int(sel.sum())//200000)]), 0)
    hair, plain = median(hair_ref), median(skin_ref); c = weighted(colour[candidates])
    keep = np.zeros_like(candidates); keep[candidates] = np.linalg.norm(c-hair, axis=1) < BEARD_RATIO*np.linalg.norm(c-plain, axis=1)
    return keep


def texel_pitch(positions, mapped):
    """Median 3D distance between horizontally adjacent mapped texels."""
    both = mapped[:, 1:] & mapped[:, :-1]; require(both.any(), 'No adjacent mapped texels')
    return float(np.median(np.linalg.norm(positions[:, 1:][both].astype(float)-positions[:, :-1][both], axis=1)))


def joined(candidates, anchors, positions, pitch):
    """Candidate texels linked in 3D to an anchor texel through candidates no more than JOIN_SPACING x the texel pitch apart:
    a fixed radius, so scattered dots (freckles) stay apart however sparse they are."""
    cy, cx = np.nonzero(candidates); out = np.zeros_like(candidates)
    if not len(cy) or not anchors.any(): return out
    P = positions[cy, cx].astype(float); tree = cKDTree(P); n = len(P); r = JOIN_SPACING*pitch; ay, ax = np.nonzero(anchors)
    touch = cKDTree(positions[ay, ax].astype(float)).query(P, distance_upper_bound=r)[0] < np.inf
    pairs = tree.query_pairs(r, output_type='ndarray')
    _, part = connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)), directed=False)
    good = np.isin(part, part[touch]); out[cy[good], cx[good]] = True; return out


def ear_skin(labels, masks, mapped, colour, channel=9):
    """Recover confident ear interiors only where color separates skin from the competing material."""
    ear = masks['ear'] > .8
    candidates = mapped & (labels == channel) & ear
    result = np.zeros_like(mapped)
    if not candidates.any():
        return result
    references = [mapped & (labels == 0) & (masks['skin'] > .8),
                  mapped & (labels == channel) & (masks['ear'] < .1)]
    if any(np.count_nonzero(region) < 32 for region in references):
        return result
    def median(region):
        samples = colour[region]
        return np.median(lab(samples[::max(1, len(samples)//10000)]), axis=0)
    skin, bone = map(median, references)
    if np.linalg.norm(skin-bone) >= 15:
        values = lab(colour[candidates])
        result[candidates] = np.linalg.norm(values-skin, axis=1) < .65*np.linalg.norm(values-bone, axis=1)
    return result


def apply_channels(labels, masks, mapped, colour=None, protected=None, positions=None, *, hair_ear_guard=False, lip_skin_guard=False):
    """Channel moves from the masks on a 4K ownership atlas; gutters re-padded so chart-border 1K blocks follow the edits.
    colour (the 4K bake) keeps hair-coloured beards hair (beard_hair). protected (hair rules marked overFaceMasks, with the 4K
    surface positions) stays hair where it joins hair the masks leave alone: a widow's peak or a hanging strand the parser
    calls skin on a head whose hair and skin colours are too close to tell apart; never near the eye (RUNBOOK 161)."""
    o = labels.copy(); before = labels
    iris = masks['iris'] > .5; eye = masks['eye'] > .5; brow = (masks['brow'] > .5) & mapped
    skinlike = ((masks['skin'] > .5) | eye | (masks['lips'] > .5) | (masks['nose'] > .5)) & ~brow & ~iris
    beard = beard_hair(labels, masks, mapped, colour, skinlike & ~eye) if colour is not None else np.zeros_like(skinlike)
    skinlike &= ~beard
    near_eye = binary_dilation(eye, iterations=NEAR_EYE) & mapped
    ring = near_eye & ~iris & np.isin(o, (8, 9)); lash = near_eye & ~brow & (o == 1)
    report = {'oldIrisRingToSkin': int(ring.sum()), 'lashToSkin': int(lash.sum()), 'beardKeptHair': int(beard.sum())}
    if protected is not None:
        require(positions is not None, 'Protected hair needs the 4K surface positions')
        moving = skinlike & ~near_eye & (labels == 1) & mapped   # lash lines and the eye opening still go to skin
        kept = joined(protected & moving, (labels == 1) & ~skinlike & ~near_eye & ~brow & mapped, positions, texel_pitch(positions, mapped))
        skinlike &= ~kept; report['protectedKeptHair'] = int(kept.sum())
    o[ring] = 0; o[lash] = 0
    o[skinlike & (o == 1)] = 0; o[eye & ~iris] = 0; o[brow & (o == 0)] = 1; o[iris] = 8
    # tattoo1 is the iris only; whatever else the rules owned there (troll horns and tusks, old ink) takes tattoo2 (user 2026-10-30)
    off_iris = (o == 8) & ~iris & mapped; report['tattoo1ToTattoo2'] = int(off_iris.sum()); o[off_iris] = 9
    lock = (masks['hairlock'] > .5) & mapped & (o == 0) & ~near_eye; report['hairLockToHair'] = int(lock.sum()); o[lock] = 1
    if 'ear' in masks and colour is not None:
        restore = ear_skin(o, masks, mapped, colour)
        o[restore] = 0
        report['earBoneToSkin'] = int(restore.sum())
    require(type(hair_ear_guard) is bool, 'hairEarGuard must be boolean')
    if hair_ear_guard:
        require('ear' in masks and colour is not None, 'Hair ear guard needs ear masks and baked color')
        restore = ear_skin(o, masks, mapped, colour, channel=1)
        o[restore] = 0
        report['earHairToSkin'] = int(restore.sum())
    require(type(lip_skin_guard) is bool, 'lipSkinGuard must be boolean')
    if lip_skin_guard:
        # Beard-color and connected overFaceMasks rules must not recolor the mouth.
        restore = mapped & (masks['lips'] > .5) & (o == 1)
        o[restore] = 0
        report['lipHairToSkin'] = int(restore.sum())
    o = pad(o[..., None], mapped)[..., 0]
    moved = np.bincount(before[mapped].astype(np.int64)*10+o[mapped], minlength=100)
    report['moved'] = {f'{a}->{b}': int(moved[a*10+b]) for a in range(10) for b in range(10) if a != b and moved[a*10+b]}
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


def treat(colour, labels, masks, value, settings=None, outer=None, preserve_skin=None):
    """Step 3 on a 4K colour atlas (0..255) with the final 4K ownership: darken-only broad de-light, skin smoothing away from the
    features, lip line and eye-socket darks, iris rim, lid line, brows in the hair mid tones with a darker outer edge and their
    skin fringe refilled from plain skin on the surface; then ownership-consistent blocks. outer (per face, rays.outer_faces) is
    needed with scalpDelight: only visible skin off the face is darkened, and only it sets the broad level."""
    s = dict(TREATMENT, **(settings or {}))
    require(set(s) == set(TREATMENT) and all(type(v) in (int, float) and 0 <= v <= 1 for v in s.values()), 'Unknown face treatment setting')
    require(not s['scalpDelight'] or outer is not None, 'scalpDelight needs the outer faces')
    P = value['positions'].astype(float); F = value['faces']; width = np.ptp(P[:, 0])
    positions, owners, _ = surface(value, 4096, enforce=False); mapped = owners >= 0; fid = np.maximum(owners, 0)
    onface = mapped & face_region(P, F)[0][fid]; c = colour.astype(np.float32).copy(); o = labels; report = {}
    iris = masks['iris'] > .5; eye = masks['eye'] > .5; brow = (masks['brow'] > .5) & mapped; skin = mapped & (o == 0)
    preserve = skin_preservation(preserve_skin, o, mapped)
    report['preservedSkinTexels'] = int(preserve.sum())
    def darken(sy, sx, broad, level, power):
        """Darken only, toward a broad luma level, never below 0.6 of the texel; returns the unclipped gain."""
        gain = np.minimum(1.0, (level/np.maximum(broad, 1))**power); c[sy, sx] *= np.clip(gain, .6, 1)[:, None]; return gain
    if s['delight'] and (skin & onface).sum() > 16:
        # Darken only: broad baked highlights come down; shaded sides keep their form shading (lifting them read as cheek patches).
        sy, sx = np.nonzero(skin & onface); broad = _surface_mean(positions[sy, sx].astype(float), luma(c[sy, sx]), 256)
        report['delightGainP5P95'] = np.percentile(darken(sy, sx, broad, np.median(broad), s['delight']), [5, 95]).round(3).tolist()
    scalp = skin & ~onface & outer[fid] if s['scalpDelight'] else None
    if s['scalpDelight'] and (skin & onface).sum() > 16 and scalp.any():
        # Visible skin off the face region, darkened only to the face skin's broad level: baked top light on a shaved scalp
        # (troll-female-a beside its horns, RUNBOOK 165) otherwise ranks onto the pale top of the skin row and steps against the
        # face at chart borders. The hidden inner wall is left alone and kept out of the broad means.
        sy, sx = np.nonzero(skin & (onface | scalp)); broad = _surface_mean(positions[sy, sx].astype(float), luma(c[sy, sx]), 256); off = scalp[sy, sx]
        gain = darken(sy[off], sx[off], broad[off], np.median(broad[~off]), s['scalpDelight'])
        report['scalpDelightGainP5P95'] = np.percentile(gain, [5, 95]).round(3).tolist()
    if s['smooth'] and skin.sum() > 16:
        sy, sx = np.nonzero(skin); col = c[sy, sx]; local = _surface_mean(positions[sy, sx].astype(float), col, 32)
        near = np.clip(gaussian_filter(np.maximum.reduce([masks[k] for k in ('brow', 'eye', 'lips', 'nose')]), 24)*3, 0, 1)
        c[sy, sx] = local+(col-local)*(1-s['smooth']*(1-near[sy, sx])*(~preserve[sy, sx]))[:, None]
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
        # Preserve authored orbital shadows; they can resemble leftover brow pigment.
        if s['browSkinRefill']:
            sy, sx = np.nonzero(mapped & (o == 0) & onface); distance, _ = cKDTree(positions[bm][::4]).query(positions[sy, sx], k=1)
            plain = ~preserve[sy, sx] & (distance > BROW_FRINGE*width) & (distance < 3*BROW_FRINGE*width); ref = luma(c[sy, sx])
            if plain.any():
                fringe = ~preserve[sy, sx] & (distance < BROW_FRINGE*width) & (ref < np.median(ref[plain])-12)   # darker than nearby plain skin: leftover brow colour
                if fringe.any():
                    _, nn = cKDTree(positions[sy[plain], sx[plain]]).query(positions[sy[fringe], sx[fringe]], k=min(24, int(plain.sum())))
                    current=c[sy[fringe], sx[fringe]]; donor=c[sy[plain], sx[plain]][nn.reshape(int(fringe.sum()), -1)].mean(1)
                    c[sy[fringe], sx[fringe]] = current+s['browSkinRefill']*(donor-current)
                report['browFringeRefilled'] = int(fringe.sum())
    c, report['mixedBlocksFixed'] = consistent_blocks(np.clip(c, 0, 255), o)
    return pad(c, mapped), dict(report, settings=s)

def skin_preservation(mask, labels, mapped):
    """Protect authored skin detail from smoothing/refill, never de-light or channel/quality gates."""
    if mask is None:
        return np.zeros(labels.shape, bool)
    mask=np.asarray(mask)
    require(mask.shape==labels.shape and np.isfinite(mask).all()
            and np.isin(mask,[0,1,255]).all(), 'Skin preservation must be a discrete atlas-sized mask')
    return (mask>0)&mapped&(labels==0)
