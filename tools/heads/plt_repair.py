"""Direct repair of a published PLT texture against its native model, for heads (and other single-PLT parts) whose stage
runs are gone or must not be rerun. The geometry and UVs never change; only (shade, channel) texel pairs do.

Commands (all paths explicit; nothing is written outside --out):
  view   decoded views of a PLT on its model, optionally a channel false-colour sheet.
  probe  measure a selection (JSON predicate): per-channel counts, shade, decoded lightness and position percentiles,
         plus a views sheet with the selection in magenta. Read-only.
  apply  run a repair spec: writes the repaired PLT, a receipt and before/after sheets into --out.

Texel quantities for predicates (headkit.predicates.when): x, y, z (texel surface point in the model's unit bounding
box: y up, z toward the face, x toward the anatomical left, the headkit glTF frame), u, v (top-down texture coordinates),
channel, shade, mapped, the decoded colour r, g, b, lum, sat, red, rb, gb under the spec's preview rows, and
mask:NAME for each spec surfaceOutlines entry ({"axes": "xy", "points": [[0..1, 0..1], ...]}).

Operations, applied in order, each on the texels its "when" selects (mapped texels only):
  fill       shade := median shade of the k nearest unselected texels of the target channel (3D distance). With
             "channel", the texels move to that channel first. "donors" restricts donor texels. Repairs blotches,
             ovals and stray patches by the surrounding surface.
  despeckle  replace texels whose shade differs from the median of themselves and their k nearest same-channel
             neighbours by more than "threshold" shades ("passes" times; "side" both, darker or lighter limits it to low or high outliers, in
             shade terms). Repairs specks and streaks while keeping broad detail.
  match      quantile-map the selection's shades onto a reference selection's shade distribution ("reference"
             predicate, same channel), blended by "strength" (0..1) and an optional feather "ramp"
             ({"of": quantity, "from": a, "to": b}: weight 0 at a, 1 at b; "center" measures |quantity - center|;
             a list of ramps multiplies). Matches brows, evens out bright or dark ovals.
  clamp      clip shades to [lo, hi]; either absolute or percentiles of a "reference" selection.
  curve      remap shades through a piecewise-linear "points" curve ([[in, out], ...], ascending in, 0 and 255
             covered), with the optional feather "ramp". Compresses baked highlights or shadows and keeps detail.
  relabel    majority vote: a texel whose k nearest neighbours ("neighbours", default 24) mostly ("minShare", default
             0.6) belong to another channel moves to it, with their median shade. Repairs stray flecks of one channel
             inside another (skin specks in hair, hair bits on skin). "to" limits the channels texels may move to.
  channel    move texels to "channel" keeping their shades.
  shade      set an absolute "shade".
The spec's optional "texture" names the texture the trimeshes sample and the output PLT (default: the model name).
Every operation needs a unique "name" and takes only its documented keys; an operation that selects nothing refuses unless "allowEmpty" is true, and one
that changes more than "maxFraction" (default 0.25) of the mapped texels refuses. Unmapped padding texels follow their
nearest mapped texel wherever that texel changed, so filtering never bleeds the old value.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headkit.common import require  # noqa: E402
from headkit.predicates import when  # noqa: E402
from headkit.paint import colour_values, surface_outline  # noqa: E402

SCHEMA = 1
PLT_MAGIC = b'PLT V1  '
# Stock palette per PLT channel (headbatch names, pal-*.tga); cloth and leather are optional for heads.
PALETTE_FILES = {0: 'pal-skin01.tga', 1: 'pal-hair01.tga', 2: 'pal-armor01.tga', 3: 'pal-armor02.tga',
                 4: 'pal-cloth01.tga', 5: 'pal-cloth01.tga', 6: 'pal-leath01.tga', 7: 'pal-leath01.tga',
                 8: 'pal-tattoo01.tga', 9: 'pal-tattoo01.tga'}
CHANNEL_COLOURS = np.array([[205, 160, 130], [120, 70, 30], [150, 150, 170], [90, 90, 120], [60, 140, 60],
                            [30, 90, 30], [140, 100, 60], [90, 60, 30], [40, 120, 220], [230, 60, 160]], np.uint8)
VIEW_NAMES = ('front', 'right-three-quarter', 'left-three-quarter', 'back', 'right-back-three-quarter',
              'left-back-three-quarter', 'right temple profile', 'left temple profile')
COMMON_KEYS = {'name', 'op', 'when', 'allowEmpty', 'maxFraction'}
OP_KEYS = {'fill': {'channel', 'neighbours', 'donors'}, 'despeckle': {'neighbours', 'threshold', 'passes', 'side'},
           'match': {'reference', 'strength', 'ramp'}, 'clamp': {'reference', 'percentiles', 'lo', 'hi'},
           'curve': {'points', 'ramp'}, 'relabel': {'neighbours', 'minShare', 'to'}, 'channel': {'channel'},
           'shade': {'shade'}}
OPS = tuple(OP_KEYS)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_plt(data):
    """(header, shades, layers): header is the 24 bytes kept verbatim on write; planes are top-down."""
    require(data[:8] == PLT_MAGIC and len(data) >= 24, 'Not a PLT V1 file')
    width, height = (int(v) for v in np.frombuffer(data[16:24], '<u4'))
    require(width > 0 and height > 0 and len(data) == 24+2*width*height, 'PLT size differs from its header')
    pixels = np.frombuffer(data, np.uint8, offset=24).reshape(height, width, 2)[::-1]
    return bytes(data[:24]), pixels[..., 0].copy(), pixels[..., 1].copy()


def write_plt(header, shades, layers):
    require(shades.shape == layers.shape and shades.dtype == layers.dtype == np.uint8, 'Matching uint8 planes required')
    require(int(layers.max()) <= 9, 'PLT channels are 0..9')
    height, width = shades.shape
    require(np.array_equal(np.frombuffer(header[16:24], '<u4'), [width, height]), 'Header size differs from the planes')
    return header+np.ascontiguousarray(np.stack([shades, layers], -1)[::-1]).tobytes()


def native_mesh(data, model, texture=None):
    """Triangles of the native model's trimeshes that sample TEXTURE (default: the model name), in the headkit glTF
    frame (NWN +y forward, +z up -> z forward, y up; x mirrored to keep the rotation proper) with top-down UVs."""
    from headkit.native_reader import decode
    texture = (texture or model).lower()
    meshes = [m for m in decode(data, model, require_tangents=False) if m['textures'][0].lower() == texture]
    require(meshes, 'No native trimesh samples texture '+texture)
    positions, faces, uv, base = [], [], [], 0
    for m in meshes:
        p = m['position'].astype(float); t = m['uv'].astype(float).copy(); t[:, 1] = 1-t[:, 1]
        positions.append(np.c_[-p[:, 0], p[:, 2], p[:, 1]]); faces.append(m['faces'].astype(np.int64)+base); uv.append(t)
        base += len(p)
    positions, faces, uv = np.concatenate(positions), np.concatenate(faces), np.concatenate(uv)
    require(uv.min() >= -1e-4 and uv.max() <= 1+1e-4, 'UVs outside [0, 1] (tiled or wrapped) are not supported')
    return {'positions': positions, 'faces': faces, 'uv': np.clip(uv, 0, 1)[faces]}


class Texels:
    """Per-texel surface geometry of one mesh at one texture size: owners, unit-box positions, padding source."""
    def __init__(self, value, size):
        from scipy.ndimage import distance_transform_edt
        from headkit.textures import surface
        points, owners, _ = surface(value, size, enforce=False)
        self.owners = owners; self.mapped = owners >= 0
        require(self.mapped.any(), 'The model maps no texels')
        lo, hi = value['positions'].min(0), value['positions'].max(0)
        self.unit = (points-lo)/np.maximum(hi-lo, 1e-12)
        self.unit[~self.mapped] = -1
        self.nearest = distance_transform_edt(~self.mapped, return_distances=False, return_indices=True)
        self.size = size; self._trees = {}

    def values(self, shades, layers, decoded, outlines):
        size = self.size; vv, uu = np.mgrid[0:size, 0:size]
        axis = lambda i: self.unit[..., i]
        extra = {'x': lambda: axis(0), 'y': lambda: axis(1), 'z': lambda: axis(2), 'mapped': lambda: self.mapped,
                 'u': lambda: (uu+.5)/size, 'v': lambda: (vv+.5)/size, 'channel': lambda: layers,
                 'shade': lambda: shades.astype(np.int16)}
        for name, spec in (outlines or {}).items():
            def outline(spec=spec):
                inside = np.zeros(self.mapped.shape, bool)
                inside[self.mapped] = surface_outline(self.unit[self.mapped], spec); return inside
            extra['mask:'+name] = outline
        return colour_values(decoded, extra)


def load_palettes(directory, channels):
    from PIL import Image
    palettes = {}
    for channel in sorted(int(c) for c in channels):
        path = Path(directory)/PALETTE_FILES[channel]
        if path.is_file():
            palettes[channel] = np.asarray(Image.open(path).convert('RGB'))
        else:
            # Decoded colour only drives previews and colour predicates; a grey ramp keeps other channels usable.
            print(f'note: {path.name} missing; channel {channel} previews as a grey ramp', file=sys.stderr)
            palettes[channel] = np.repeat(np.arange(256, dtype=np.uint8)[None, :, None], 176, 0).repeat(3, 2)
    return palettes


def decode_colours(shades, layers, palettes, rows):
    out = np.zeros(shades.shape+(3,), np.uint8)
    for channel in np.unique(layers):
        c = int(channel); require(c in palettes, 'No palette for channel '+str(c)); k = layers == channel
        row = int(rows.get(c, 0)); require(0 <= row < palettes[c].shape[0], f'Preview row {row} outside the channel {c} palette')
        out[k] = palettes[c][row, shades[k]]
    return out


def knn_median(points, shades, queries, k):
    from scipy.spatial import cKDTree
    require(len(points) > 0, 'No donor texels')
    k = min(k, len(points)); _, index = cKDTree(points).query(queries, k=k)
    index = index.reshape(len(queries), -1)
    return np.median(shades[index], axis=1)


def ramp_weight(ramp, values, target):
    """Feather weight per target texel: 0 where quantity `of` is at `from`, 1 at `to` and beyond (linear). A list of
    ramps multiplies; no ramp is weight 1."""
    weight = np.ones(int(target.sum()))
    if ramp is None: return weight
    validate_ramp(ramp, 'ramp')
    for r in ramp if isinstance(ramp, list) else [ramp]:
        q = values[r['of']][target].astype(float)
        if 'center' in r: q = np.abs(q-float(r['center']))
        weight = weight*np.clip((q-r['from'])/(r['to']-r['from']), 0, 1)
    return weight


def operate(op, texels, shades, layers, selected, values, regions):
    """Apply one operation in place; returns its report."""
    kind = op['op']; report = {}
    mapped = texels.mapped; unit = texels.unit
    if kind == 'channel':
        layers[selected] = int(op['channel'])
    elif kind == 'shade':
        shades[selected] = int(op['shade'])
    elif kind == 'fill':
        if 'channel' in op: layers[selected] = int(op['channel'])
        k = int(op.get('neighbours', 16))
        donors_all = mapped & ~selected
        if 'donors' in op: donors_all &= when(op['donors'], values, regions)
        for channel in np.unique(layers[selected]):
            target = selected & (layers == channel); donors = donors_all & (layers == channel)
            require(donors.any(), f"{op['name']}: no donor texels on channel {int(channel)}")
            shades[target] = np.rint(knn_median(unit[donors], shades[donors].astype(float), unit[target], k)).astype(np.uint8)
            report[str(int(channel))] = int(target.sum())
    elif kind == 'despeckle':
        k = int(op.get('neighbours', 24)); threshold = float(op['threshold']); passes = int(op.get('passes', 1))
        side = op.get('side', 'both'); require(side in ('both', 'darker', 'lighter'), 'despeckle side: both, darker or lighter')
        require(threshold > 0 and 1 <= passes <= 8, 'despeckle needs threshold > 0 and 1..8 passes')
        replaced = 0
        for _ in range(passes):
            for channel in np.unique(layers[selected]):
                pool = mapped & (layers == channel); target = selected & pool
                med = knn_median(unit[pool], shades[pool].astype(float), unit[target], k+1)
                current = shades[target].astype(float); delta = current-med
                bad = {'both': np.abs(delta), 'darker': -delta, 'lighter': delta}[side] > threshold
                values_new = current.copy(); values_new[bad] = np.rint(med[bad])
                shades[target] = values_new.astype(np.uint8); replaced += int(bad.sum())
        report['replaced'] = replaced
    elif kind == 'match':
        reference = when(op['reference'], values, regions) & mapped & ~selected
        strength = float(op.get('strength', 1.0)); require(0 < strength <= 1, 'match strength in (0, 1]')
        for channel in np.unique(layers[selected]):
            target = selected & (layers == channel); ref = reference & (layers == channel)
            require(ref.sum() >= 16, f"{op['name']}: reference has under 16 texels on channel {int(channel)}")
            src = shades[target].astype(float)
            ranks = (np.argsort(np.argsort(src, kind='stable'), kind='stable')+.5)/len(src)
            mapped_values = np.quantile(shades[ref].astype(float), ranks)
            weight = strength*ramp_weight(op.get('ramp'), values, target)
            shades[target] = np.clip(np.rint(src+(mapped_values-src)*weight), 0, 255).astype(np.uint8)
            report[str(int(channel))] = {'texels': int(target.sum()), 'from': np.percentile(src, [5, 50, 95]).round(1).tolist(),
                                         'reference': np.percentile(shades[ref], [5, 50, 95]).round(1).tolist()}
    elif kind == 'relabel':
        from scipy.spatial import cKDTree
        k = int(op.get('neighbours', 24)); share = float(op.get('minShare', 0.6))
        require(1 <= k <= 256 and 0.5 <= share <= 1, 'relabel needs 1..256 neighbours and minShare 0.5..1')
        pool = np.flatnonzero(mapped.ravel()); k = min(k, len(pool)-1); require(k >= 1, 'relabel needs at least two mapped texels')
        _, index = cKDTree(unit.reshape(-1, 3)[pool]).query(unit[selected], k=k+1)
        found = pool[index.reshape(len(index), -1)]; own_index = np.flatnonzero(selected.ravel())
        # Drop the texel itself wherever it appears (coincident seam texels can rank ahead of it), keeping k neighbours.
        keep = found != own_index[:, None]; keep[keep.sum(1) > k, -1] = False
        near = found[keep].reshape(len(found), k); flat_l = layers.ravel(); flat_s = shades.ravel()
        near_l = flat_l[near]; own = layers[selected]
        allowed = op.get('to', list(range(10)))
        require(isinstance(allowed, list) and allowed and all(type(c) is int and 0 <= c <= 9 for c in allowed), 'relabel to: channels 0..9')
        counts = np.stack([(near_l == c).sum(1) if c in allowed else np.zeros(len(near_l), int) for c in range(10)], 1)
        top = counts.argmax(1)
        move = (top != own) & (counts.max(1) >= share*k)
        new_l = own.copy(); new_s = shades[selected].copy()
        for i in np.flatnonzero(move):
            same = near_l[i] == top[i]; new_l[i] = top[i]; new_s[i] = int(np.rint(np.median(flat_s[near[i]][same])))
        layers[selected] = new_l; shades[selected] = new_s; report['moved'] = int(move.sum())
        report['to'] = {str(int(c)): int((top[move] == c).sum()) for c in np.unique(top[move])}
    elif kind == 'curve':
        points = np.asarray(op['points'], float); src = shades[selected].astype(float)
        out = np.interp(src, points[:, 0], points[:, 1])
        weight = ramp_weight(op.get('ramp'), values, selected)
        shades[selected] = np.clip(np.rint(src+(out-src)*weight), 0, 255).astype(np.uint8)
    elif kind == 'clamp':
        if 'reference' in op:
            ref = when(op['reference'], values, regions) & mapped & ~selected
            require(ref.sum() >= 16, op['name']+': reference has under 16 texels')
            lo, hi = np.percentile(shades[ref], op.get('percentiles', [5, 95]))
        else:
            lo, hi = op.get('lo', 0), op.get('hi', 255)
        require(0 <= lo <= hi <= 255, 'clamp bounds 0 <= lo <= hi <= 255')
        shades[selected] = np.clip(shades[selected], int(round(lo)), int(round(hi)))
        report['bounds'] = [int(round(lo)), int(round(hi))]
    return report


def validate_ramp(ramp, name):
    ramps = ramp if isinstance(ramp, list) else [ramp]
    require(ramps, name+': empty ramp list')
    for r in ramps:
        require(isinstance(r, dict) and {'of', 'from', 'to'} <= set(r) <= {'of', 'center', 'from', 'to'}
                and isinstance(r['of'], str) and all(type(r[k]) in (int, float) for k in set(r)-{'of'}) and r['from'] != r['to'],
                name+': ramp needs of, numeric from and to (from != to), optionally numeric center')


def number(v):
    return type(v) in (int, float)


def validate_rows(rows, name='previewRows'):
    """Preview rows {channel: row}: channels 0..9, rows >= 0 (the palette height bounds them at decode)."""
    require(isinstance(rows, dict), name+' must map channels to rows')
    for k, v in rows.items():
        require(str(k).isdigit() and 0 <= int(k) <= 9 and type(v) is int and v >= 0, name+': channels 0..9, rows >= 0')
    return {int(k): v for k, v in rows.items()}


def validate_view(spec):
    """The parts of a spec that probe also reads: model, texture, preview rows, regions and outlines."""
    require(isinstance(spec, dict), 'Repair spec must be an object')
    require(isinstance(spec.get('model'), str) and spec['model'], 'Spec model name required')
    require(isinstance(spec.get('texture', 'x'), str) and spec.get('texture', 'x'), 'Spec texture must be a name')
    require(isinstance(spec.get('regions', {}), dict) and isinstance(spec.get('surfaceOutlines', {}), dict),
            'Spec regions and surfaceOutlines must be objects')
    return validate_rows(spec.get('previewRows', {}))


def validate_spec(spec):
    require(isinstance(spec, dict) and spec.get('schemaVersion') == SCHEMA, 'Repair spec schemaVersion 1 required')
    validate_view(spec)
    source = spec.get('source', {})
    for kind in ('plt', 'mdl'):
        require(isinstance(source.get(kind, {}).get('sha256'), str), 'Spec must pin source.'+kind+'.sha256')
    ops = spec.get('operations')
    require(isinstance(ops, list) and ops, 'Non-empty operations list required')
    require(all(isinstance(op, dict) for op in ops), 'Operations must be objects')
    names = [op.get('name') for op in ops]
    require(all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names), 'Unique operation names required')
    for op in ops:
        require(op.get('op') in OPS, 'Unknown operation '+str(op.get('op')))
        name = op['name']; extra = set(op)-COMMON_KEYS-OP_KEYS[op['op']]
        require(not extra, name+': unknown keys '+', '.join(sorted(extra)))
        require(isinstance(op.get('when'), dict), name+': when predicate required')
        require(type(op.get('allowEmpty', False)) is bool, name+': allowEmpty true or false')
        limit = op.get('maxFraction', 0.25); require(number(limit) and 0 < limit <= 1, name+': maxFraction in (0, 1]')
        if 'neighbours' in op: require(type(op['neighbours']) is int and 1 <= op['neighbours'] <= 256, name+': neighbours 1..256')
        if op['op'] == 'fill' and 'donors' in op: require(isinstance(op['donors'], dict), name+': donors predicate')
        if op['op'] == 'despeckle':
            require(number(op.get('threshold')) and op['threshold'] > 0, name+': despeckle threshold > 0 required')
            passes = op.get('passes', 1); require(type(passes) is int and 1 <= passes <= 8, name+': despeckle passes 1..8')
            require(op.get('side', 'both') in ('both', 'darker', 'lighter'), name+': despeckle side both, darker or lighter')
        if op['op'] == 'match':
            strength = op.get('strength', 1.0); require(number(strength) and 0 < strength <= 1, name+': match strength in (0, 1]')
        if op['op'] == 'relabel':
            share = op.get('minShare', 0.6); require(number(share) and 0.5 <= share <= 1, name+': relabel minShare 0.5..1')
            to = op.get('to', list(range(10)))
            require(isinstance(to, list) and to and all(type(c) is int and 0 <= c <= 9 for c in to), name+': relabel to: channels 0..9')
        if op['op'] in ('channel',) or 'channel' in op:
            require(type(op.get('channel')) is int and 0 <= op['channel'] <= 9, op['name']+': channel 0..9')
        if op['op'] == 'shade': require(type(op.get('shade')) is int and 0 <= op['shade'] <= 255, op['name']+': shade 0..255')
        if op['op'] == 'match': require(isinstance(op.get('reference'), dict), op['name']+': reference predicate required')
        if 'ramp' in op: validate_ramp(op['ramp'], op['name'])
        if op['op'] == 'clamp':
            if 'reference' in op:
                pct = op.get('percentiles', [5, 95])
                require(isinstance(op['reference'], dict) and isinstance(pct, list) and len(pct) == 2
                        and all(type(v) in (int, float) for v in pct) and 0 <= pct[0] <= pct[1] <= 100,
                        op['name']+': clamp reference predicate and percentiles [lo, hi] in 0..100')
            else:
                lo, hi = op.get('lo', 0), op.get('hi', 255)
                require(number(lo) and number(hi) and 0 <= lo <= hi <= 255, op['name']+': clamp 0 <= lo <= hi <= 255')
        if op['op'] == 'curve':
            points = op.get('points')
            require(isinstance(points, list) and len(points) >= 2
                    and all(isinstance(q, list) and len(q) == 2 and all(type(v) in (int, float) for v in q) for q in points),
                    op['name']+': curve points [[in, out], ...] required')
            xs = [q[0] for q in points]; ys = [q[1] for q in points]
            require(xs[0] == 0 and xs[-1] == 255 and all(a < b for a, b in zip(xs, xs[1:])) and all(0 <= y <= 255 for y in ys),
                    op['name']+': curve inputs ascend from 0 to 255 and outputs stay in 0..255')


def repair(spec, value, header, shades, layers, palettes, texels=None):
    """Pure repair: returns (shades, layers, report). The inputs are not modified."""
    validate_spec(spec); rows = validate_rows(spec.get('previewRows', {}))
    texels = texels or Texels(value, shades.shape[0])
    require(shades.shape[0] == shades.shape[1] == texels.size, 'Square texture of the measured size required')
    shades, layers = shades.copy(), layers.copy(); before_s, before_l = shades.copy(), layers.copy()
    regions = spec.get('regions', {}); outlines = spec.get('surfaceOutlines', {}); mapped_count = int(texels.mapped.sum())
    reports = []
    for op in spec['operations']:
        values = texels.values(shades, layers, decode_colours(shades, layers, palettes, rows), outlines)
        selected = when(op['when'], values, regions) & texels.mapped
        count = int(selected.sum())
        require(count or op.get('allowEmpty', False), op['name']+': selects no texels')
        limit = float(op.get('maxFraction', 0.25)); require(0 < limit <= 1, op['name']+': maxFraction in (0, 1]')
        pre_s, pre_l = shades.copy(), layers.copy()
        detail = operate(op, texels, shades, layers, selected, values, regions) if count else {}
        changed = (shades != pre_s) | (layers != pre_l)
        moved = int(changed.sum())
        require(moved <= limit*mapped_count,
                f"{op['name']}: changes {moved} texels ({moved/mapped_count:.3f} of {mapped_count} mapped), over maxFraction {limit}")
        reports.append({'name': op['name'], 'op': op['op'], 'selected': count, 'changed': int(changed.sum()),
                        'channelsSelected': {str(int(c)): int((pre_l[selected] == c).sum()) for c in np.unique(pre_l[selected])},
                        **({'detail': detail} if detail else {})})
    changed = texels.mapped & ((shades != before_s) | (layers != before_l))
    # Padding texels whose nearest mapped texel changed take its new value.
    near = tuple(texels.nearest); follow = ~texels.mapped & changed[near]
    shades[follow] = shades[near][follow]; layers[follow] = layers[near][follow]
    report = {'operations': reports, 'mappedTexels': mapped_count, 'changedMapped': int(changed.sum()),
              'changedPadding': int(follow.sum()), 'changedFraction': round(float(changed.sum())/mapped_count, 5)}
    return shades, layers, report


def render(value, decoded, embree, path, size=384, names=VIEW_NAMES, label=''):
    from headkit.diagnostics import views, pixels, sheet
    tiles = [((label+' ' if label else '')+n, pixels(v, decoded.astype(float), value['uv'])) for n, v in views(value, embree, size, names)]
    return sheet(tiles, path, size, columns=4)


def parse_rows(text):
    rows = {}
    for item in (text or '').split(','):
        if item:
            parts = item.split(':'); require(len(parts) == 2, '--rows takes channel:row pairs, e.g. 0:5,1:65')
            rows[int(parts[0])] = int(parts[1])
    return validate_rows(rows, '--rows')


def check_pins(spec, plt, mdl):
    """A spec repairs exactly the bytes it was measured on."""
    require(sha256(plt) == spec['source']['plt']['sha256'], 'PLT differs from the spec pin')
    require(sha256(mdl) == spec['source']['mdl']['sha256'], 'MDL differs from the spec pin')


def load(args, spec=None, pinned=True):
    """Inputs for a command. A spec's model and texture win; --texture must agree with the spec texture."""
    mdl = Path(args.mdl).read_bytes(); plt = Path(args.plt).read_bytes()
    spec = spec or {}
    if spec:
        if pinned:
            validate_spec(spec); check_pins(spec, plt, mdl)
        else:
            validate_view(spec)
    model = spec.get('model') or args.model or Path(args.mdl).stem
    flag = getattr(args, 'texture', None); texture = spec.get('texture') or flag or model
    require(not (spec and flag) or flag.lower() == texture.lower(), '--texture differs from the spec texture; put the texture in the spec')
    value = native_mesh(mdl, model, texture)
    header, shades, layers = read_plt(plt)
    require(shades.shape[0] == shades.shape[1], 'Only square PLTs are supported')
    return model, texture, mdl, plt, value, header, shades, layers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('view', 'probe', 'apply'):
        p = sub.add_parser(name)
        p.add_argument('--mdl', required=True); p.add_argument('--plt', required=True)
        p.add_argument('--palettes', required=True, help='folder with the stock pal-*.tga files')
        p.add_argument('--embree', required=True, help='embree4.dll for the view sheets')
        p.add_argument('--out', required=True); p.add_argument('--model'); p.add_argument('--texture', help='texture the trimeshes sample (default: the model name)')
        p.add_argument('--size', type=int, default=384)
        if name != 'apply': p.add_argument('--rows', default='', help='preview rows, e.g. 0:5,1:65,9:120')
        if name == 'view': p.add_argument('--channels', action='store_true', help='also a channel false-colour sheet')
        if name == 'probe':
            p.add_argument('--when', required=True, help='JSON predicate or @file'); p.add_argument('--spec')
        if name == 'apply': p.add_argument('--spec', required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if args.command == 'apply':
        spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
        model, texture, mdl, plt, value, header, shades, layers = load(args, spec)
        rows = validate_rows(spec.get('previewRows', {})); output = out/(texture+'.plt')
        out.mkdir(parents=True, exist_ok=True)
        require(not output.exists() and not (out/'receipt.json').exists(), 'Output PLT or receipt exists; use a fresh --out')
        palettes = load_palettes(args.palettes, set(np.unique(layers).tolist()) | set(rows) |
                                 {op['channel'] for op in spec['operations'] if 'channel' in op})
        new_s, new_l, report = repair(spec, value, header, shades, layers, palettes)
        data = write_plt(header, new_s, new_l)
        # Sheets first, so a render failure leaves no repaired PLT without its receipt.
        before = render(value, decode_colours(shades, layers, palettes, rows), args.embree, out/'before.png', args.size, label='before')
        after = render(value, decode_colours(new_s, new_l, palettes, rows), args.embree, out/'after.png', args.size, label='after')
        diff = decode_colours(new_s, new_l, palettes, rows); moved = (new_s != shades) | (new_l != layers)
        diff[moved] = [255, 0, 255]
        changed = render(value, diff, args.embree, out/'changed.png', args.size, label='changed')
        receipt = {'schemaVersion': SCHEMA, 'kind': 'plt-repair-receipt', 'model': model, 'texture': texture,
                   'tool': {'path': 'tools/heads/plt_repair.py', 'sha256': sha256(Path(__file__).read_bytes())},
                   'spec': {'path': Path(args.spec).as_posix(), 'sha256': sha256(Path(args.spec).read_bytes())},
                   'source': {'plt': {'path': Path(args.plt).as_posix(), 'sha256': sha256(plt)},
                              'mdl': {'path': Path(args.mdl).as_posix(), 'sha256': sha256(mdl)}},
                   'output': {'plt': {'path': output.as_posix(), 'sha256': sha256(data)}},
                   'sheets': {'before': before, 'after': after, 'changed': changed}, 'report': report,
                   'approval': 'none: sheets and measurements never approve appearance; client review and the user decide'}
        output.write_bytes(data)
        (out/'receipt.json').write_text(json.dumps(receipt, indent=1)+'\n', encoding='utf-8', newline='\n')
        print(json.dumps(report, indent=1)); print(out/'receipt.json')
        return 0
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8')) if getattr(args, 'spec', None) else {}
    model, texture, mdl, plt, value, header, shades, layers = load(args, spec, pinned=False)
    rows = parse_rows(args.rows) or validate_rows(spec.get('previewRows', {}))
    palettes = load_palettes(args.palettes, set(np.unique(layers).tolist()) | set(rows))
    decoded = decode_colours(shades, layers, palettes, rows); out.mkdir(parents=True, exist_ok=True)
    if args.command == 'view':
        print(render(value, decoded, args.embree, out/'views.png', args.size))
        if args.channels: print(render(value, CHANNEL_COLOURS[layers], args.embree, out/'channels.png', args.size))
        return 0
    text = args.when[1:] if args.when.startswith('@') else None
    condition = json.loads(Path(text).read_text(encoding='utf-8') if text else args.when)
    texels = Texels(value, shades.shape[0])
    values = texels.values(shades, layers, decoded, spec.get('surfaceOutlines', {}))
    selected = when(condition, values, spec.get('regions', {})) & texels.mapped
    result = {'selected': int(selected.sum()), 'channels': {}}
    for channel in np.unique(layers[selected]):
        k = selected & (layers == channel); pct = lambda a: np.percentile(a[k], [5, 50, 95]).round(3).tolist()
        result['channels'][str(int(channel))] = {'texels': int(k.sum()), 'shade': pct(shades), 'lum': pct(values['lum']),
                                                 'x': pct(values['x']), 'y': pct(values['y']), 'z': pct(values['z'])}
    print(json.dumps(result, indent=1))
    marked = decoded.copy(); marked[selected] = [255, 0, 255]
    print(render(value, marked, args.embree, out/'probe.png', args.size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
