"""The brassard: a cloth band round the upper arm, on the shoulder slot, carrying the logo badge.

It is built, not generated: a tube that follows the outline of what the body wears on its upper arm (an
outfit's sleeve, or the arm's skin), a hand's width below the shoulder, its two edges turned in to the arm,
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
CLEARANCE = 0.005  # metres the band stands outside what is worn under it
LIP = 0.03  # metres each edge is turned in toward the arm, so that no gap shows the band's inside
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


def outline(under, start, axis, out, third, low, high):
    """The radius per direction of what is worn on the arm between `low` and `high` metres down it: its widest there, evened."""
    points = measure.surface_points(np.asarray(under[0], float), np.asarray(under[1], int), SURFACE) - start
    along = points @ axis
    mine = points[(along >= low) & (along <= high)]
    require(len(mine), 'Nothing is worn on the upper arm where the band goes')
    angle = np.arctan2(mine @ third, mine @ out)
    cell = np.floor((angle + np.pi) / (2 * np.pi) * DIRECTIONS).astype(int) % DIRECTIONS
    radius = np.zeros(DIRECTIONS)
    np.maximum.at(radius, cell, np.hypot(mine @ out, mine @ third))
    require((radius > 0).all(), 'The upper arm is open on a side where the band goes')
    widest = np.max([np.roll(radius, shift) for shift in (-1, 0, 1)], axis=0)
    return (np.roll(widest, 1) + 2 * widest + np.roll(widest, -1)) / 4


def build(bones, under, side):
    """({'band': (v, f, uv), 'badge': (v, f, uv)}, facing): one arm's brassard in body space, and the badge's
    (outward, up) for `logo.reads_right`."""
    start, axis, out, third, length = frame(bones, side)
    low = BELOW * length
    radius = outline(under, start, axis, out, third, low, low + TALL) + CLEARANCE
    angles = -np.pi + (np.arange(DIRECTIONS) + 0.5) * 2 * np.pi / DIRECTIONS
    at = lambda s, r, a: start + s * axis + r * (np.cos(a) * out + np.sin(a) * third)
    rings = [(low, np.maximum(radius - LIP, 0.5 * radius), 0.0), (low + 0.004, radius, 0.12), (low + TALL - 0.004, radius, 0.88),
             (low + TALL, np.maximum(radius - LIP, 0.5 * radius), 1.0)]
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
    at_out = float(np.interp(0.0, np.concatenate([angles - 2 * np.pi, angles, angles + 2 * np.pi]), np.tile(radius, 3)))
    span = BADGE / at_out  # the angle a badge's side takes
    middle = low + TALL / 2
    bv, buv, bf = [], [], []
    for j in range(GRID + 1):  # up the picture: from the elbow's side to the shoulder's
        for i in range(GRID + 1):  # along it, to the viewer's right
            a = sign * (i / GRID - 0.5) * span
            r = float(np.interp(a, np.concatenate([angles - 2 * np.pi, angles, angles + 2 * np.pi]), np.tile(radius, 3))) + PROUD
            bv.append(at(middle + (0.5 - j / GRID) * BADGE, r, a))
            buv.append((i / GRID, j / GRID))
    for j in range(GRID):
        for i in range(GRID):
            a, b, c, d = j * (GRID + 1) + i, j * (GRID + 1) + i + 1, (j + 1) * (GRID + 1) + i, (j + 1) * (GRID + 1) + i + 1
            bf += [(a, b, d), (a, d, c)]
    bv, bf = np.array(bv), np.array(bf)
    if (np.cross(bv[bf[:, 1]] - bv[bf[:, 0]], bv[bf[:, 2]] - bv[bf[:, 0]]) @ out).sum() < 0:
        bf = bf[:, [0, 2, 1]]
    return {'band': band, 'badge': (bv, bf, np.array(buv))}, (out, up)


def tint(size=TEXELS):
    """(shades, layers) of the band's tint texture: accent cloth with a woven grain, hemmed in leather at both edges."""
    rows = np.arange(size)[:, None] / (size - 1)  # v = 0 first
    columns = np.arange(size)[None, :]
    hem = (rows < 0.14) | (rows > 0.86)
    shade = 168 + 14 * np.sin(columns * np.pi / 2) * np.cos(rows * size * np.pi / 2) + np.zeros((size, size))
    shade = np.where(hem, 140, shade)
    stitch = (np.abs(rows - 0.17) < 0.012) | (np.abs(rows - 0.83) < 0.012)
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
    models, failures, triangles = {}, [], {}
    for side in 'lr':
        token_under, token = ARM[side][2:]
        path = None if outfit is None else Path(outfit[0]) / (registry.model_name(body, token_under, outfit[1]) + '.mdl')
        under = measure.mesh(path.read_bytes(), path.stem, bones[seams.BONES[token_under]]) if path is not None and path.is_file() else skin[token_under]
        made, (out, up) = build(bones, under, side)
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
              'gates': {'passed': not failures, 'failures': failures, 'triangles': triangles, 'texels': TEXELS}}
    if game is not None:
        compiled = export.compile_models(sorted(ascii_dir / (name + '.mdl') for name in models.values()), written, game=game, resources=list(resources))
        record['compiled'] = len(compiled)
    (Path(output) / 'bake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record
