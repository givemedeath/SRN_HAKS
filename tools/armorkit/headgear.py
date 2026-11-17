"""Open headgear on the neck slot: a generated piece that follows the head, in a neck part that keeps the body's neck.

The neck slot is the accessory slot (docs/armorkit/plan.md, slot rules). A piece that must follow the head is a
skinned mesh bound to the head bone, inside a neck part that also carries the body's own neck, so the neck
never disappears; both are drawn from one tint texture named like the model, the neck's skin in one quarter of
it (as `bodyskin.worn` lays a sleeve's), since the game colours a part's texture only under the model's name.

A piece is prepared once (`accessory.prepare`) and fitted per body here (`fit`). Race versions cannot scale it
(docs/armorkit/spikes.md, section 13): each body's piece is brought to the head envelope of its race and gender
(`head-envelopes.json`, the outer bounds of that race's published heads), direction by direction and level by
level, so it clears every published head of that race. That makes it roomier than any one head needs.
"""
import json
import shutil
from pathlib import Path

import numpy as np

from . import accessory, bodyskin, export, measure, registry, texture
from .registry import require

ENVELOPES = Path(__file__).resolve().parent / 'head-envelopes.json'
DIRECTIONS = 48  # the piece is fitted in this many directions round the head's axis
LEVELS = 0.01  # metres: and in levels this tall
CLEARANCE = 0.006  # metres the piece stands outside the head envelope
SHORT = 0.002  # metres a point of the piece's outside may stand short of the envelope and still clear it (`gates`)
OUTWARD = 0.2  # a face counts as the piece's outside where its normal leans this much away from the axis
RELIEF = (3, 5)  # directions and levels each way that what stands proud of the shell (a filter, a valve) is told from it
EVEN = 1.5  # cells the fit is evened over
RIM = 0.01  # metres the piece's lower edge hangs below the chin
FACE = (np.radians(55), 0.65)  # the face a piece must cover: this far to each side of straight ahead, this share of the head's height up from the chin


def envelope(body, path=ENVELOPES):
    """The head envelope of `body`'s race and gender: the row of its Fit body, heads being published for that build."""
    rows = json.loads(Path(path).read_text(encoding='utf-8'))['bodies']
    key = body[:3] + '0'
    require(key in rows, f'No head envelope is measured for {key}')
    return rows[key]


def field(row):
    """(radius, known, bottom): the envelope on the fitting grid, about its own axis in head-bone space.

    `radius[level, direction]` is the envelope's radius, level 0 starting at `bottom` metres, straight ahead (+y)
    at direction `DIRECTIONS / 4`. Where the envelope has nothing (under the jaw, ahead of the neck) the radius
    is read on from the directions and levels that have something, and `known` says where it was measured."""
    rings = np.asarray(row['rings'], float)
    slices, coarse = rings.shape
    filled = np.full(rings.shape, np.nan)
    index = np.arange(coarse)
    for k in range(slices):
        have = rings[k] > 0
        if have.any():
            filled[k] = np.interp(index, np.concatenate([index[have] - coarse, index[have], index[have] + coarse]), np.tile(rings[k][have], 3))
    rows_known = np.isfinite(filled[:, 0])
    require(rows_known.any(), 'The head envelope is empty')
    for k in range(slices):
        if not rows_known[k]:
            filled[k] = filled[np.flatnonzero(rows_known)[np.abs(np.flatnonzero(rows_known) - k).argmin()]]
    step = float(row['sliceHeight'])
    levels = int(round(slices * step / LEVELS))
    at = (np.arange(levels) + 0.5) * LEVELS / step - 0.5  # in slices, from the first slice's middle
    low = np.clip(np.floor(at).astype(int), 0, slices - 1)
    high = np.clip(low + 1, 0, slices - 1)
    share = np.clip(at - low, 0.0, 1.0)[:, None]
    tall = (1 - share) * filled[low] + share * filled[high]
    turn = (np.arange(DIRECTIONS) + 0.5) * coarse / DIRECTIONS  # the coarse rings' direction k is at angle 2 pi k / coarse
    first = np.floor(turn).astype(int)
    part = (turn - first)[None, :]
    radius = (1 - part) * tall[:, first % coarse] + part * tall[:, (first + 1) % coarse]
    measured = (rings > 0)[np.clip(np.round(at).astype(int), 0, slices - 1)][:, np.round(turn).astype(int) % coarse]
    return radius, measured, float(row['firstSlice'])


def _cells(points, bottom):
    """(direction, level, radius) of points about the vertical axis through the origin, as `field` numbers them."""
    angle = np.arctan2(points[:, 1], points[:, 0]) % (2 * np.pi)
    return (np.floor(angle / (2 * np.pi) * DIRECTIONS).astype(int) % DIRECTIONS,
            np.floor((points[:, 2] - bottom) / LEVELS).astype(int), np.hypot(points[:, 0], points[:, 1]))


def _blur(values, width=EVEN):
    """A grid of levels by directions, evened; round the circle in its directions, held at its ends in its levels."""
    reach = int(np.ceil(3 * width))
    kernel = np.exp(-0.5 * (np.arange(-reach, reach + 1) / width) ** 2)
    kernel /= kernel.sum()
    wide = np.concatenate([values[:, -reach:], values, values[:, :reach]], axis=1)
    values = np.stack([np.convolve(row, kernel, mode='valid') for row in wide])
    tall = np.concatenate([np.repeat(values[:1], reach, axis=0), values, np.repeat(values[-1:], reach, axis=0)], axis=0)
    return np.stack([np.convolve(column, kernel, mode='valid') for column in tall.T], axis=1)


def _spread(values):
    """A grid with its unknown cells (NaN) read from the known ones beside them, a ring at a time."""
    values = values.copy()
    require(np.isfinite(values).any(), 'The piece has no outside to fit')
    while np.isnan(values).any():
        known = np.isfinite(values)
        total, count = np.zeros(values.shape), np.zeros(values.shape)
        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            moved, there = np.roll(np.where(known, values, 0.0), shift, axis), np.roll(known, shift, axis)
            if axis == 0:  # levels do not wrap round
                edge = 0 if shift == 1 else -1
                moved[edge], there[edge] = 0.0, False
            total, count = total + moved, count + there
        fill = ~known & (count > 0)
        values[fill] = total[fill] / count[fill]
    return values


def _window(values, reach, pick):
    """The least or the most (`pick`) of a grid's known cells within `reach` = (directions, levels) each way."""
    out = np.full(values.shape, np.nan)
    stack = []
    for dz in range(-reach[1], reach[1] + 1):
        for da in range(-reach[0], reach[0] + 1):
            moved = np.roll(values, (dz, da), (0, 1))
            if dz > 0:
                moved[:dz] = np.nan
            elif dz < 0:
                moved[dz:] = np.nan
            stack.append(moved)
    stack = np.stack(stack)
    some = np.isfinite(stack).any(axis=0)
    out[some] = (np.nanmin if pick == 'least' else np.nanmax)(stack[:, some], axis=0)
    return out


def outside(points, faces, bottom, levels):
    """(radius, samples): the piece's outside per level and direction, NaN where it has none, and the points read.

    Only faces that lean away from the axis count: a mask generated as a shell with a wall across its back has
    that wall inside the head, and it is no surface the head must stay under."""
    points, faces = np.asarray(points, float), np.asarray(faces, int)
    corners = points[faces]
    normal = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    middle = corners.mean(axis=1)
    radial = middle * [1.0, 1.0, 0.0]
    radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-12)
    out = (normal * radial).sum(axis=1) > OUTWARD
    used, renumbered = np.unique(faces[out], return_inverse=True)
    # read no sparser than a third of a level: on a Troll's head the piece's faces are twice a Human's, and a grid of
    # points per face left cells of the face unread, which the cover gate then failed (2026-11-17)
    samples = measure.surface_points(points[used], renumbered.reshape(-1, 3), LEVELS / 3)
    way, level, radius = _cells(samples, bottom)
    inside = (level >= 0) & (level < levels)
    table = np.full((levels, DIRECTIONS), -np.inf)
    np.maximum.at(table, (level[inside], way[inside]), radius[inside])
    return np.where(np.isfinite(table), table, np.nan), samples


def conform(points, faces, row):
    """(points, record): a piece brought to a head envelope, in head-bone space.

    The piece (front +y, up +z, as generated) is scaled as a whole to the head's height from under the chin to
    its top and set with its foremost point ahead of the face. Then its shell is brought to the envelope: the
    shell is the piece's outside without what stands proud of it (`RELIEF`), and every point moves in or out
    along its own direction from the axis by what brings the shell there `CLEARANCE` outside the envelope, the
    move evened over the grid. Filters and a visor ride on the shell and keep their depth."""
    points = np.asarray(points, float)
    radius, known, bottom = field(row)
    levels = len(radius)
    ahead = DIRECTIONS // 4
    chin_level = int(np.flatnonzero(known[:, ahead]).min())  # the lowest level with a face straight ahead
    chin, top = bottom + chin_level * LEVELS, float(row['max'][2])
    low, high = points.min(axis=0), points.max(axis=0)
    # the rim hangs a level below the chin: an edge at the chin's own level turns under there and left cells of
    # the face unread and the envelope short on the Orc woman and both Trolls (2026-11-17)
    scale = (top - chin + 2 * CLEARANCE + RIM) / (high[2] - low[2])
    front = float(np.nanmax(radius[chin_level:, ahead - 2:ahead + 3])) + CLEARANCE
    placed = (points - [(low[0] + high[0]) / 2, high[1], low[2]]) * scale + [0.0, front, chin - CLEARANCE - RIM]
    target = radius + CLEARANCE
    moved_by = np.zeros((levels, DIRECTIONS))
    for attempt in range(12):
        shell, _ = outside(placed, faces, bottom, levels)
        if attempt == 0:  # the shell without what stands proud of it
            shell = _window(_window(shell, RELIEF, 'least'), RELIEF, 'most')
            move = _blur(_spread(target - shell))
        else:  # then only what is still short, outward
            short = np.where(np.isfinite(shell), np.maximum(target - shell, 0.0), 0.0)
            if short.max() <= SHORT / 2:
                break
            move = _blur(_window(short, (1, 1), 'most')) * 1.5
        way = (np.arctan2(placed[:, 1], placed[:, 0]) % (2 * np.pi)) / (2 * np.pi) * DIRECTIONS - 0.5
        level = np.clip((placed[:, 2] - bottom) / LEVELS - 0.5, 0, levels - 1)
        a0, l0 = np.floor(way).astype(int), np.floor(level).astype(int)
        l1 = np.minimum(l0 + 1, levels - 1)
        fa, fl = way - a0, level - l0
        shift = ((1 - fl) * ((1 - fa) * move[l0, a0 % DIRECTIONS] + fa * move[l0, (a0 + 1) % DIRECTIONS])
                 + fl * ((1 - fa) * move[l1, a0 % DIRECTIONS] + fa * move[l1, (a0 + 1) % DIRECTIONS]))
        r = np.hypot(placed[:, 0], placed[:, 1])
        grown = np.maximum(r + shift, 1e-4) / np.maximum(r, 1e-6)
        placed = np.stack([placed[:, 0] * grown, placed[:, 1] * grown, placed[:, 2]], axis=1)
        moved_by += move
    return placed, {'scale': round(float(scale), 4), 'moved': [round(float(moved_by.min()), 4), round(float(moved_by.max()), 4)],
                    'chin': round(chin, 3), 'top': round(top, 3)}


def clears(points, faces, row):
    """(failures, record): whether a fitted piece clears its head envelope and covers the face.

    Clear: in every level and direction where both the piece has an outside and the envelope was measured, the
    piece stands no more than `SHORT` inside the envelope. Covered: the piece has an outside in every direction
    within `FACE` of straight ahead, from the chin up `FACE`'s share of the head's height, so no face shows."""
    radius, known, bottom = field(row)
    levels = len(radius)
    shell, _ = outside(points, faces, bottom, levels)
    both = np.isfinite(shell) & known
    short = float(np.max(np.where(both, radius - shell, -np.inf))) if both.any() else 0.0
    ahead = DIRECTIONS // 4
    chin_level = int(np.flatnonzero(known[:, ahead]).min())
    upto = chin_level + int(FACE[1] * (float(row['max'][2]) - (bottom + chin_level * LEVELS)) / LEVELS)
    reach = int(FACE[0] / (2 * np.pi) * DIRECTIONS)
    face = np.isfinite(shell[chin_level:upto, ahead - reach:ahead + reach + 1])
    failures = []
    if short > SHORT:
        failures.append(f'up to {short * 100:.1f} cm inside the head envelope')
    if not face.all():
        failures.append(f'{int((~face).sum())} of {face.size} cells of the face are not covered')
    return failures, {'shortOfEnvelope': round(max(short, 0.0), 4), 'faceCovered': round(float(face.mean()), 3)}


def beside_neck(piece, tinted, skin, limit=1024):
    """(uv of the piece, uv of the neck, (shades, layers), relief, rough): one texture for the piece and the body's
    neck, the piece's maps in the first quarter and the neck's skin in the last, as `bodyskin.worn` lays a sleeve's."""
    size = len(piece['rgb'])
    side = min(max(2 * size, len(skin['tint'])), limit)
    half = side // 2

    def laid(mine, theirs, fill, kind='mean'):
        mine = np.asarray(mine)
        whole = np.full((side, side) + mine.shape[2:], fill, dtype=float)
        whole[:half, :half] = bodyskin.resized(mine, half, kind).reshape((half, half) + mine.shape[2:])
        block = bodyskin.resized(theirs, half, kind).reshape((half, half) + mine.shape[2:])
        whole[half:, half:] = block
        whole[:half, half:] = block[:1]
        whole[half:, :half] = block[:, :1]
        return whole
    shades = np.round(laid(tinted[0], skin['tint'][..., 0], 0.0)).astype(int)
    layers = np.round(laid(tinted[1], skin['tint'][..., 1], 0.0, 'pick')).astype(int)
    relief = laid(piece['relief'], skin['relief'], np.array([0.5, 0.5, 1.0]), 'normal')
    rough = laid(np.full((size, size), texture.ROUGHNESS), skin['rough'], texture.ROUGHNESS)
    return np.asarray(piece['uv'], float) / 2, 0.5 + np.asarray(skin['uv'], float) / 2, (shades, layers), relief, rough


def model_text(name, neck, piece, bone='head_g'):
    """The ASCII model of a neck part: the body's neck as a rigid mesh and the piece as a skin bound whole to `bone`."""
    def node(kind, label, mesh, weights=False):
        v, f, uv, n = mesh
        lines = [f'node {kind} {label}', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1',
                 f'  bitmap {name}', '  render 1', '  shadow 1', f'  verts {len(v)}']
        lines += [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in np.asarray(v).tolist()]
        lines += [f'  tverts {len(uv)}'] + [f'    {a:.6f} {b:.6f} 0' for a, b in np.asarray(uv).tolist()]
        lines += [f'  normals {len(n)}'] + [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in np.asarray(n).tolist()]
        lines += [f'  faces {len(f)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in np.asarray(f).tolist()]
        if weights:
            lines += [f'  weights {len(v)}'] + [f'    {bone} 1.0000'] * len(v)
        return lines + ['endnode']
    require(len(name) <= 16 and name == name.lower(), 'A model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', 'classification CHARACTER', f'setsupermodel {name} NULL', 'setanimationscale 1',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode']
    lines += node('trimesh', name + 'g', neck) + node('skin', name + 'h', piece, weights=True)
    return '\n'.join(lines + [f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


def fit(document, kept, output, body_pack, body_textures, number, *, body='pmh0', packs=(), game=None, resources=(), say=lambda *_: None):
    """Put a prepared piece of headgear on `body`'s head and check it: the record, also `<output>/bake.json`.

    `kept` is the folder `accessory.prepare`'s piece is stored in, `body_textures` the folder of the bodies'
    material files and maps (the neck's skin comes with its own). With `game` the model is compiled."""
    require(document.get('accessory') == 'neck', 'Headgear is an accessory on the neck slot')
    piece, whole = accessory.stored(kept)
    bones, _ = measure.body(body_pack, body)
    row = envelope(body)
    placed, record = conform(piece['v'], piece['f'], row)
    say('fitted', record)
    failures, cleared = clears(placed, piece['f'], row)
    head, neck_bone = np.asarray(bones['head_g'], float), np.asarray(bones['neck_g'], float)
    in_body = placed + [0.0, float(row['axis'][1]), 0.0] + head[:3, 3]  # the envelope is about its own axis, in the head bone's space
    skin = bodyskin.body_part(body_pack, body_textures, body, 'neck', bones)
    tinted, colours = accessory.tints(piece, document)
    piece_uv, neck_uv, tint, relief, rough = beside_neck(piece, tinted, skin)
    name = registry.model_name(body, 'neck', number)
    to_part = lambda v, n: (export.to_bone(v, neck_bone), export.to_bone(n, neck_bone, direction=True))
    neck_v, neck_n = to_part(skin['v'], skin['n'])
    piece_v, piece_n = to_part(in_body, export.vertex_normals(in_body, piece['f']))
    ascii_dir, written = Path(output) / 'ascii', Path(output) / 'resources'
    for made in (ascii_dir, written):
        made.mkdir(parents=True, exist_ok=True)
    text = model_text(name, (neck_v, skin['f'], neck_uv, neck_n), (piece_v, piece['f'], piece_uv, piece_n))
    (ascii_dir / (name + '.mdl')).write_text(text, encoding='cp1252', newline='\n')
    (ascii_dir / (name + '.plt')).write_bytes(export.tint(*tint))
    shutil.copyfile(ascii_dir / (name + '.plt'), written / (name + '.plt'))
    texture.write_relief(written, name, relief, rough=rough)
    triangles = int(len(piece['f']))
    if triangles > accessory.BUDGET['triangles']:
        failures.append(f'{triangles} triangles, over the budget of {accessory.BUDGET["triangles"]}')
    if len(tint[0]) > accessory.BUDGET['texture']:
        failures.append(f'a texture of {len(tint[0])} texels a side, over the budget of {accessory.BUDGET["texture"]}')
    failures += [f'{name}: {pack} holds a model of that name' for pack in packs if (Path(pack) / (name + '.mdl')).exists()]
    if whole is not None:
        failures += [f'the generated piece: an opening {hole * 100:.1f} cm round' for hole in whole['holes']]
        failures += [f'the generated piece: a piece of {loose * 1e4:.1f} cm² standing apart from the rest' for loose in whole['debris']]
    record = {'model': document['model'], 'body': body, 'tier': 1, 'number': number, 'models': {'neck': name}, **colours, 'fit': record,
              'gates': {'passed': not failures, 'failures': [f'{name}: {reason}' if not reason.startswith(name) else reason for reason in failures],
                        'triangles': triangles, 'texels': int(len(tint[0])), 'head': cleared, **({} if whole is None else {'surface': whole})}}
    if game is not None:
        compiled = export.compile_models([ascii_dir / (name + '.mdl')], written, game=game, resources=list(resources))
        record['compiled'] = len(compiled)
    (Path(output) / 'bake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    np.savez_compressed(Path(output) / 'fitted.npz', v=in_body, f=piece['f'])
    return record
