"""Remove isolated PLT highlight halos at parsed brow/ear edges, in surface space.

Shade stretching can turn a modest baked edge into a white outline. Brows use
nearby interior samples; excessive ear highlights take a continuous shoulder
relative to plain face skin. Never change ownership or borrow across materials.
"""
import numpy as np
from scipy.ndimage import binary_erosion, binary_dilation, distance_transform_edt
from scipy.spatial import cKDTree
from .common import require

CONTRAST = 32
HEADROOM = 12
RADIUS = .035  # head widths; a UV neighbour alone is never a valid donor
NEIGHBOURS = 32
MIN_DONORS = 6


def _feature_region(mask, selected, mapped, positions):
    """Grow the soft feature only from same-material samples close in 3D.

    Adjacent UV islands need not be adjacent on the head. A parser feature on
    another material is not an anchor for a newly included skin/hair texel.
    """
    seed = mapped & selected & (mask > .02)
    extra = mapped & selected & binary_dilation(mask > .5, iterations=2) & ~seed
    if not extra.any():
        return seed, 0
    if not seed.any():
        return seed, int(extra.sum())
    width = float(np.ptp(positions[mapped, 0]))
    require(width > 0, 'Feature highlights need a nonzero head width')
    distance = cKDTree(positions[seed]).query(positions[extra], distance_upper_bound=RADIUS*width)[0]
    supported = np.isfinite(distance)
    region = seed.copy()
    region[extra] = supported
    return region, int((~supported).sum())


def repair_channel(picked, selected, features, positions, mapped, allowed, channel, preserve=None):
    """Return eligible shades and measurements for one channel's final 1K atlas.

    `features` are box-reduced 0..1 masks from the same UV mesh. Skin preservation
    masks protect authored ink. Insufficient local evidence leaves a texel alone
    and is reported, rather than guessing a material or a colour.
    """
    name = {0: 'ear', 1: 'brow'}.get(int(channel))
    report = {'feature': name, 'changedTexels': 0}
    if name is None:
        return picked, report
    selected, mapped = np.asarray(selected, bool), np.asarray(mapped, bool)
    positions, allowed = np.asarray(positions), np.asarray(allowed)
    require(selected.shape == mapped.shape and positions.shape == mapped.shape+(3,)
            and np.isfinite(positions[mapped]).all(), 'Feature highlights need matching finite surface points')
    require(name in features, 'Feature highlights need the '+name+' mask')
    mask = np.asarray(features[name])
    require(mask.shape == mapped.shape and np.isfinite(mask).all() and np.all((mask >= 0) & (mask <= 1)),
            'Feature highlight masks must be atlas-sized values from 0 to 1')
    require(np.shape(picked) == (int(selected.sum()),) and len(allowed) and np.all(np.diff(allowed) > 0),
            'Feature highlights need channel shades and sorted eligible shades')
    protected = np.zeros_like(mapped) if preserve is None else np.asarray(preserve, bool)
    require(protected.shape == mapped.shape, 'Feature highlight preservation must match the atlas')
    region, rejected = _feature_region(mask, selected, mapped, positions)
    report['maskExpansionRejectedTexels'] = rejected
    field = np.zeros(mapped.shape, float)
    field[selected] = picked
    if name == 'ear':
        require('skin' in features, 'Ear highlights need the plain-skin mask')
        skin = np.asarray(features['skin'])
        require(skin.shape == mapped.shape and np.isfinite(skin).all() and np.all((skin >= 0) & (skin <= 1)),
                'Plain-skin highlight mask must be atlas-sized values from 0 to 1')
        plain = mapped & selected & (skin > .8) & (mask < .02) & ~protected
        report.update(referenceTexels=int(plain.sum()), featureTexels=int(region.sum()))
        active = region & ~protected
        if plain.sum() < 32 or not active.any():
            return picked, report
        # Ear rims are broad baked highlights, not just isolated bad texels.
        # A continuous shoulder retains their form instead of clipping a flat
        # stripe. Trigger only when the ear's upper tail exceeds the face's.
        face90, face95 = np.percentile(field[plain], [90, 95])
        if np.percentile(field[active], 95) > face95+CONTRAST:
            chosen = active & (field > face90)
            old = field[chosen].copy()
            rolled = face90+24*(-np.expm1(-(old-face90)/24))
            indices = np.searchsorted(allowed, np.floor(rolled), side='right')-1
            field[chosen] = np.minimum(old, allowed[np.maximum(indices, 0)])
        report.update(referenceP90=float(face90), referenceP95=float(face95), shoulder=24)
        return _finish(field, picked, selected, mapped, protected, allowed, report)
    core = binary_erosion(region) & (mask > .75) & ~protected
    edge = region & ~binary_erosion(region, iterations=3) & ~protected
    report.update(edgeTexels=int(edge.sum()), donorTexels=int(core.sum()), unsupportedTexels=int(edge.sum()))
    if core.sum() < MIN_DONORS or not edge.any():
        return picked, report
    # Trim the highest interior samples: a soft parser edge can reach a core
    # texel, but a few hot samples must not authorize a whole white outline.
    core &= field <= np.percentile(field[core], 80)
    report['donorTexels'] = int(core.sum())
    if core.sum() < MIN_DONORS:
        return picked, report
    points = positions[mapped]
    width = float(np.ptp(points[:, 0]))
    require(width > 0, 'Feature highlights need a nonzero head width')
    tree = cKDTree(positions[core])
    distance, index = tree.query(positions[edge], k=min(NEIGHBOURS, int(core.sum())),
                                 distance_upper_bound=RADIUS*width)
    valid = np.isfinite(distance)
    supported = valid.sum(1) >= MIN_DONORS
    values = field[core]
    samples = np.where(valid, values[np.minimum(index, len(values)-1)], np.nan)
    local = np.full(len(samples), np.inf)
    local[supported] = np.nanpercentile(samples[supported], 75, axis=1)
    old = field[edge]
    change = supported & (old > local+CONTRAST)
    if change.any():
        cap = np.floor(local[change]+HEADROOM)
        indices = np.searchsorted(allowed, cap, side='right')-1
        repaired = allowed[np.maximum(indices, 0)]
        values = old.copy()
        values[change] = np.minimum(old[change], repaired)
        field[edge] = values
    report.update(unsupportedTexels=int((~supported).sum()), contrast=CONTRAST, headroom=HEADROOM,
                  radiusHeadWidths=RADIUS)
    return _finish(field, picked, selected, mapped, protected, allowed, report)


def _finish(field, picked, selected, mapped, protected, allowed, report):
    original = np.zeros(mapped.shape, float)
    original[selected] = picked
    changed = mapped & selected & (field < original)
    # Follow corrected chart-edge samples into their existing same-channel
    # gutters; never take colours from the adjacent island/material.
    distance, (iy, ix) = distance_transform_edt(~mapped, return_indices=True)
    gutter = ~mapped & selected & ~protected & (distance <= 4) & changed[iy, ix] & selected[iy, ix]
    gutter &= field > field[iy, ix]
    field[gutter] = np.minimum(field[gutter], field[iy[gutter], ix[gutter]])
    out = field[selected].astype(np.asarray(picked).dtype)
    require(np.all(out <= picked) and np.isin(out, allowed).all(),
            'Feature highlight repair must only lower to eligible shades')
    report.update(changedTexels=int(changed.sum()), gutterTexels=int(gutter.sum()),
                  maximumReduction=int(np.max(np.asarray(picked, float)-out, initial=0)))
    return out, report
