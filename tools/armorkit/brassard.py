"""The brassard: a cloth band round the upper arm, on the shoulder slot, carrying the logo badge.

It is built, not generated: a tube that follows what the body wears on its upper arm (an outfit's sleeve, or
the arm's skin) ring by ring down its height, a hand's width below the shoulder, its two edges turned in to the arm,
and on its outer side a curved badge that names the shared logo material (`logo.py`). The band is tinted
(accent cloth, hemmed in leather); the badge is not, and shows the logo SR_NWN sets on the wearer.
"""
import json
import shutil
from pathlib import Path

import numpy as np

from . import export, logo, measure, registry, seams
from .registry import require

DIRECTIONS = 32  # the band's points round the arm
BELOW = 0.3  # of the upper arm's length from the shoulder joint: where the band's upper edge lies
TALL = 0.085  # metres from edge to edge
CLEARANCE = 0.003  # metres the band stands outside what is worn under it
RINGS = 25  # the band's rings from edge to edge: each follows what is worn at its own height, and a sleeve's end under the band is stepped over within two of them
OFF = 0.012  # metres nine tenths of the band may stand off what is worn under it (`fit`; beside a sharp fold of a sleeve it
# stands further, to clear the fold): one outline for its whole height, the widest
# of a baggy sleeve and its neighbours, stood round a lifted arm as a loose ring, most on the Large bodies (user, 2026-11-17)
INSIDE = 0.002  # metres what is worn may come through the band
LIP = 0.012  # metres each edge is turned in toward the arm, so that no gap shows the band's inside. At 3 cm, hemmed in
# leather, the edges stood round a lifted arm as wide flanges (client, 2026-11-17): they are short and the band's own cloth, in shadow
BADGE = 0.068  # metres a side
PROUD = 0.003  # metres the badge stands off the band
GRID = 4  # the badge's faces along each side: it is curved to the band
SURFACE = 0.003
TEXELS = 64
BUDGET = 4000
ARM = {'l': ('lbicep_g', 'lforearm_g', 'bicepl', 'shol'), 'r': ('rbicep_g', 'rforearm_g', 'bicepr', 'shor')}


def frame(bones, side):
    """(shoulder, axis, out, round, length) of an upper arm: its joint, the unit way down it, the unit way out
    from the body square to that, the third axis, and its length."""
    upper, fore = ARM[side][:2]
    start, end = bones[upper][:3, 3], bones[fore][:3, 3]
    axis = seams.unit(end - start)
    middle = (bones[ARM['l'][0]][:3, 3] + bones[ARM['r'][0]][:3, 3]) / 2
    out = start - middle
    out = seams.unit(out - (out @ axis) * axis)
    return start, axis, out, np.cross(axis, out), float(np.linalg.norm(end - start))


def _slices(under, start, axis, out, third):
    """(height down the arm, direction cell, radius) of points over what is worn on the arm."""
    points = measure.surface_points(np.asarray(under[0], float), np.asarray(under[1], int), SURFACE) - start
    angle = np.arctan2(points @ third, points @ out)
    return points @ axis, np.floor((angle + np.pi) / (2 * np.pi) * DIRECTIONS).astype(int) % DIRECTIONS, np.hypot(points @ out, points @ third)


def centred(under, start, axis, out, third, low, high):
    """The arm's middle line where the band goes: `start` moved square to the arm onto the middle of what is worn
    between `low` and `high` metres down it. The bone's own line runs near one side of a sleeve, and an outline read
    about it is lopsided: evened round the arm, it lifted the band off the near side (2026-11-17)."""
    points = measure.surface_points(np.asarray(under[0], float), np.asarray(under[1], int), SURFACE) - start
    mine = points[(points @ axis >= low) & (points @ axis <= high)]
    require(len(mine), 'Nothing is worn on the upper arm where the band goes')
    across = np.stack([mine @ out, mine @ third], axis=1)
    middle = (across.min(axis=0) + across.max(axis=0)) / 2
    return start + middle[0] * out + middle[1] * third


def outline(under, start, axis, out, third, heights):
    """The radius per ring and direction of what is worn on the arm at `heights` metres down it.

    Each ring reads what lies within one ring's spacing of its own height, so the band between two rings covers
    what is worn between them, and is evened round the arm without coming inside what it read."""
    along, cell, radius = _slices(under, start, axis, out, third)
    reach = float(heights[1] - heights[0])
    rings = np.zeros((len(heights), DIRECTIONS))
    for ring, height in enumerate(heights):
        mine = np.abs(along - height) <= reach
        require(mine.any(), 'Nothing is worn on the upper arm where the band goes')
        np.maximum.at(rings[ring], cell[mine], radius[mine])
        require((rings[ring] > 0).all(), 'The upper arm is open on a side where the band goes')
    even = (np.roll(rings, 1, axis=1) + 2 * rings + np.roll(rings, -1, axis=1)) / 4
    return np.maximum(rings, even)


def fit(under, start, axis, out, third, heights, radius):
    """(off, most, inside): how far the band stands off what is worn under it over nine tenths of itself and at
    most, and how far that comes through it.

    Read slice by slice between the rings, each direction's widest worn point against the band there."""
    along, cell, worn = _slices(under, start, axis, out, third)
    gaps = []
    step = float(heights[1] - heights[0])
    for ring in range(len(heights) - 1):
        for part in (0.25, 0.75):
            mine = np.abs(along - (heights[ring] + part * step)) <= step / 4
            widest = np.zeros(DIRECTIONS)
            np.maximum.at(widest, cell[mine], worn[mine])
            band = (1 - part) * radius[ring] + part * radius[ring + 1]
            have = widest > 0
            gaps.append((band - widest)[have])
    gaps = np.concatenate(gaps)
    require(len(gaps), 'Nothing is worn under the band')
    return float(np.percentile(gaps, 90)), float(gaps.max()), float(max(-gaps.min(), 0.0))


def build(bones, under, side):
    """({'band': (v, f, uv), 'badge': (v, f, uv)}, facing, (off, most, inside)): one arm's brassard in body space, the
    badge's (outward, up) for `logo.reads_right`, and `fit`'s measures of the band."""
    start, axis, out, third, length = frame(bones, side)
    low = BELOW * length
    start = centred(under, start, axis, out, third, low, low + TALL)
    heights = low + TALL * np.arange(RINGS) / (RINGS - 1)
    radius = outline(under, start, axis, out, third, heights) + CLEARANCE
    angles = -np.pi + (np.arange(DIRECTIONS) + 0.5) * 2 * np.pi / DIRECTIONS
    at = lambda s, r, a: start + s * axis + r * (np.cos(a) * out + np.sin(a) * third)
    lip = lambda ring: np.maximum(radius[ring] - LIP, 0.5 * radius[ring])
    rings = ([(low - 0.004, lip(0), 0.0)] + [(heights[k], radius[k], 0.12 + 0.76 * k / (RINGS - 1)) for k in range(RINGS)]
             + [(low + TALL + 0.004, lip(-1), 1.0)])
    v, uv, f = [], [], []
    for s, r, row in rings:
        for k in range(DIRECTIONS + 1):  # the seam's column twice, for the texture
            v.append(at(s, r[k % DIRECTIONS], angles[k % DIRECTIONS]))
            uv.append((k / DIRECTIONS, 1.0 - row))
    wide = DIRECTIONS + 1
    for ring in range(len(rings) - 1):
        for k in range(DIRECTIONS):
            a, b, c, d = ring * wide + k, ring * wide + k + 1, (ring + 1) * wide + k, (ring + 1) * wide + k + 1
            f += [(a, b, d), (a, d, c)]
    v, f = np.array(v), np.array(f)
    centre = v.mean(axis=0)
    normal = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    if (normal * (v[f].mean(axis=1) - centre)).sum() < 0:  # wound to face out
        f = f[:, [0, 2, 1]]
    band = (v, f, np.array(uv))
    # the badge: square, on the outer side, curved to the band. Seen from outside its u runs to the viewer's right
    up = -axis
    right = np.cross(-out, up)
    sign = 1.0 if third @ right > 0 else -1.0
    round_about = np.concatenate([angles - 2 * np.pi, angles, angles + 2 * np.pi])

    def band_at(s, a):  # the band's radius at a height and an angle, read between its rings
        ring = float(np.clip((s - low) / TALL * (RINGS - 1), 0, RINGS - 1 - 1e-9))
        k, part = int(ring), ring - int(ring)
        return float(np.interp(a, round_about, np.tile((1 - part) * radius[k] + part * radius[k + 1], 3)))
    middle = low + TALL / 2
    span = BADGE / band_at(middle, 0.0)  # the angle a badge's side takes
    bv, buv, bf = [], [], []
    for j in range(GRID + 1):  # up the picture: from the elbow's side to the shoulder's
        for i in range(GRID + 1):  # along it, to the viewer's right
            a = sign * (i / GRID - 0.5) * span
            s = middle + (0.5 - j / GRID) * BADGE
            bv.append(at(s, band_at(s, a) + PROUD, a))
            buv.append((i / GRID, j / GRID))
    for j in range(GRID):
        for i in range(GRID):
            a, b, c, d = j * (GRID + 1) + i, j * (GRID + 1) + i + 1, (j + 1) * (GRID + 1) + i, (j + 1) * (GRID + 1) + i + 1
            bf += [(a, b, d), (a, d, c)]
    bv, bf = np.array(bv), np.array(bf)
    if (np.cross(bv[bf[:, 1]] - bv[bf[:, 0]], bv[bf[:, 2]] - bv[bf[:, 0]]) @ out).sum() < 0:
        bf = bf[:, [0, 2, 1]]
    return {'band': band, 'badge': (bv, bf, np.array(buv))}, (out, up), fit(under, start, axis, out, third, heights, radius)


def tint(size=TEXELS):
    """(shades, layers) of the band's tint texture: accent cloth with a woven grain, hemmed in leather at both edges."""
    rows = np.arange(size)[:, None] / (size - 1)  # v = 0 first
    columns = np.arange(size)[None, :]
    lip = (rows < 0.115) | (rows > 0.885)  # the edges turned in: the band's cloth, in the shadow under it
    hem = ~lip & ((rows < 0.2) | (rows > 0.8))
    shade = 168 + 14 * np.sin(columns * np.pi / 2) * np.cos(rows * size * np.pi / 2) + np.zeros((size, size))
    shade = np.where(hem, 150, np.where(lip, 85, shade))
    stitch = (np.abs(rows - 0.23) < 0.012) | (np.abs(rows - 0.77) < 0.012)
    shade = np.where(stitch & (columns % 4 < 2), 215, shade)
    layers = np.where(hem, export.LAYERS['leather1'], export.LAYERS['cloth2']) + np.zeros((size, size), int)
    return np.clip(np.round(shade), 30, 240).astype(int), layers


def model_text(name, band, badge):
    """The ASCII model of one arm's brassard, in its bone's space: the tinted band and the badge on the logo material."""
    def node(label, bitmap, mesh, extra=()):
        v, f, uv, n = mesh
        lines = [f'node trimesh {label}', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1',
                 f'  bitmap {bitmap}', *extra, '  render 1', '  shadow 0', f'  verts {len(v)}']
        lines += [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in np.asarray(v).tolist()]
        lines += [f'  tverts {len(uv)}'] + [f'    {a:.6f} {b:.6f} 0' for a, b in np.asarray(uv).tolist()]
        lines += [f'  normals {len(n)}'] + [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in np.asarray(n).tolist()]
        lines += [f'  faces {len(f)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in np.asarray(f).tolist()]
        return lines + ['endnode']
    require(len(name) <= 16 and name == name.lower(), 'A model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', 'classification CHARACTER', f'setsupermodel {name} NULL', 'setanimationscale 1',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode']
    lines += node(name + 'g', name, band) + node(name + 'b', logo.STRIP, badge, (f'  materialname {logo.MATERIAL}',))
    return '\n'.join(lines + [f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


def run(output, body_pack, number, *, body='pmh0', outfit=None, packs=(), game=None, resources=()):
    """Build both arms' brassards for `body` over `outfit` = (pack folder, number), write and gate them: the
    record, also written as `<output>/bake.json`. With `game` the models are compiled."""
    bones, skin = measure.body(body_pack, body)
    ascii_dir, written = Path(output) / 'ascii', Path(output) / 'resources'
    for made in (ascii_dir, written):
        made.mkdir(parents=True, exist_ok=True)
    logo.write(written)
    models, failures, triangles, stands = {}, [], {}, {}
    for side in 'lr':
        token_under, token = ARM[side][2:]
        path = None if outfit is None else Path(outfit[0]) / (registry.model_name(body, token_under, outfit[1]) + '.mdl')
        under = measure.mesh(path.read_bytes(), path.stem, bones[seams.BONES[token_under]]) if path is not None and path.is_file() else skin[token_under]
        made, (out, up), (off, most, inside) = build(bones, under, side)
        name = registry.model_name(body, token, number)
        bone = np.asarray(bones[seams.BONES[token]], float)
        require(np.linalg.det(bone[:3, :3]) > 0, name + ': a mirrored bone would turn the part inside out')
        meshes = []
        for v, f, uv in (made['band'], made['badge']):
            meshes.append((export.to_bone(v, bone), f, uv, export.to_bone(export.vertex_normals(v, f), bone, direction=True)))
        text = model_text(name, *meshes)
        (ascii_dir / (name + '.mdl')).write_text(text, encoding='cp1252', newline='\n')
        (ascii_dir / (name + '.plt')).write_bytes(export.tint(*tint()))
        shutil.copyfile(ascii_dir / (name + '.plt'), written / (name + '.plt'))
        models[token] = name
        triangles[token] = int(len(made['band'][1]) + len(made['badge'][1]))
        stands[token] = {'off': round(off, 4), 'most': round(most, 4), 'inside': round(inside, 4)}
        if off > OFF:
            failures.append(f'{name}: a tenth of the band stands {off * 100:.1f} cm or more off what is worn under it, over {OFF * 100:.1f} cm')
        if inside > INSIDE:
            failures.append(f'{name}: what is worn comes {inside * 100:.1f} cm through the band')
        # gates: the badge names the material and reads the right way round; budget; no name a pack holds
        failures += [f'{name}: the badge: {reason}' for reason in logo.reads_right(*made['badge'], out, up)]
        if f'materialname {logo.MATERIAL}' not in text or f'bitmap {logo.STRIP}' not in text:
            failures.append(f'{name}: the badge does not name the logo material and strip')
        if triangles[token] > BUDGET:
            failures.append(f'{name}: {triangles[token]} triangles, over the budget of {BUDGET}')
        failures += [f'{name}: {pack} holds a model of that name' for pack in packs if (Path(pack) / (name + '.mdl')).exists()]
    record = {'model': 'brassard', 'body': body, 'tier': 1, 'number': number, 'models': models,
              'logo': {'material': logo.MATERIAL, 'parameter': logo.PARAMETER, 'strip': logo.STRIP, 'cells': logo.cells()},
              'over': None if outfit is None else {'pack': Path(outfit[0]).name, 'number': outfit[1]},
              'gates': {'passed': not failures, 'failures': failures, 'triangles': triangles, 'texels': TEXELS, 'fit': stands}}
    if game is not None:
        compiled = export.compile_models(sorted(ascii_dir / (name + '.mdl') for name in models.values()), written, game=game, resources=list(resources))
        record['compiled'] = len(compiled)
    (Path(output) / 'bake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record
