"""The universal door set (plan, stage 5): ten generic doors built in code, each filling its whole opening with no
frame above the leaf, on the base game's door structure.

A door model is laid out as the pack's doors are (`srn_door/fci_door_04.mdl`): a root dummy, the `grnd`, `head`,
`hhit` and `impc` dummies, a transparent `sam` mesh the player clicks, and the animations `opening1`/`opened1`/
`closing1` (one way), `opening2`/`opened2`/`closing2` (the other), `closed`, `die`, `dead` and `trans`. Its `.dwk` holds
three walkmeshes, `wg_closed`, `wg_open1` and `wg_open2`, of NonWalk faces, and the points a creature uses it from.
The door's origin is its hook: the middle of the doorway's foot, the leaf across x, the street and the room on +-y.

Kinds open as such doors do: a hinged leaf (`swing`) turns 90 degrees on its hinge, one way or the other; a shutter
(`roll`) rises into its housing and is gone; a strip curtain (`flap`) swings up on its rail. Every door draws one atlas
of its own, `ATLAS` in `srn_door`, made by `kit.atlas` from `LOOKS`, so it shows in any tileset. Each door is a row of
`genericdoors.2da` from `FIRST`, after the rows in use and before the reserved block (user, 2026-11-19 and -20)."""
import math
from pathlib import Path

from . import kit, material, require

ATLAS = 'srn_doors'
FIRST = 1094  # the first empty row of genericdoors.2da; 3000-3199 are reserved
HEIGHT = 3.0
LOOKS = {
    'door_green': (None, (38, 70, 58), 0.5, 0.1), 'door_red': (None, (96, 30, 28), 0.5, 0.1),
    'door_cream': (None, (200, 192, 172), 0.55, 0.0), 'door_steel': (None, (88, 96, 104), 0.45, 0.5),
    'steel': (None, (150, 155, 160), 0.32, 0.85), 'galvanised': (None, (132, 138, 142), 0.45, 0.7),
    'slats': (None, (140, 146, 150), 0.45, 0.7), 'glass': (None, (34, 44, 52), 0.08, 0.0),
    'wired': (None, (44, 54, 60), 0.1, 0.0), 'frame': (None, (62, 64, 68), 0.35, 0.8),
    'rubber': (None, (24, 24, 26), 0.85, 0.0), 'iron': ('MetalPlates013', (44, 42, 40), None, None),
    'yellow': (None, (222, 178, 24), 0.55, 0.0), 'hazard': (None, (222, 178, 24), 0.55, 0.0),
    'pvc': (None, (150, 168, 172), 0.25, 0.0), 'gate_paint': (None, (34, 36, 38), 0.6, 0.3),
}
ORDER = list(LOOKS)
GRIMY = {'door_green': 0.14, 'door_red': 0.14, 'door_cream': 0.1, 'door_steel': 0.12, 'galvanised': 0.14, 'slats': 0.16, 'gate_paint': 0.1, 'frame': 0.06}


def _slats(made, side):  # a roller shutter's curtain: a rib every 20 pixels, about 12 cm on a door, lit along its top
    rows = __import__('numpy').arange(side) % 20; made['colour'][rows < 3] = (70, 74, 78)
    made['normal'][rows == 3] = (128, 200, 220); made['normal'][rows == 19] = (128, 56, 220)


def _wired(made, side):  # wired glass: a fine square grid of wire
    rows = __import__('numpy').arange(side) % 24; wire = (rows == 0)[:, None] | (rows == 0)[None, :]; made['colour'][wire] = (120, 124, 126)


def _hazard(made, side):  # yellow and black stripes across at 45 degrees
    np = __import__('numpy'); index = np.arange(side); made['colour'][((index[:, None] + index[None, :]) // 48) % 2 == 1] = (22, 22, 24)


def _pvc(made, side):  # a strip curtain's PVC: faint streaks down it
    np = __import__('numpy'); rng = np.random.default_rng(7); streak = np.repeat(rng.random((1, side)) * 18, side, axis=0)
    made['colour'] = np.uint8(np.clip(made['colour'] - streak[..., None], 0, 255))


PAINTED = {'slats': _slats, 'wired': _wired, 'hazard': _hazard, 'pvc': _pvc}


def mesh():
    return kit.Mesh(ORDER, ATLAS)


def _framed(part, x0, x1, hole, look, glass, t=0.06, z1=HEIGHT):
    """A leaf from x0 to x1 and 0 to `z1` high, `t` thick, with a glazed hole (hx0, hx1, hz0, hz1) or none."""
    half = t / 2
    if not hole:
        part.box((x0, -half, 0.0), (x1, half, z1), look, bevel=0.008); return
    hx0, hx1, hz0, hz1 = hole
    for low, high in (((x0, -half, 0.0), (x1, half, hz0)), ((x0, -half, hz1), (x1, half, z1)),
                      ((x0, -half, hz0), (hx0, half, hz1)), ((hx1, -half, hz0), (x1, half, hz1))):
        part.box(low, high, look, bevel=0.006)
    part.box((hx0, -0.006, hz0), (hx1, 0.006, hz1), glass)  # the pane, set in the middle of the leaf's thickness


def _proud(part, x0, x1, z0, z1, look, t=0.06, rise=0.01):
    """A raised panel or plate on both faces of a leaf `t` thick."""
    for side in (-1, 1):
        y0, y1 = sorted((side * t / 2, side * (t / 2 + rise))); part.box((x0, y0, z0), (x1, y1, z1), look, bevel=min(0.004, rise / 2))


def _lever(part, x, z=1.05, t=0.06, look='steel'):
    """A lever handle and its rose on both faces, at `x` along the leaf."""
    for side in (-1, 1):
        y = side * t / 2; out = side * 0.06
        part.box((x - 0.035, min(y, y + side * 0.012), z - 0.07), (x + 0.035, max(y, y + side * 0.012), z + 0.07), look)
        part.box((x - 0.13 if x > 0 else x, min(y + side * 0.012, y + out), z - 0.012), (x if x > 0 else x + 0.13, max(y + side * 0.012, y + out), z + 0.012), look)


def _bar(part, x0, x1, z=1.05, t=0.06, look='steel'):
    """A push bar across both faces."""
    for side in (-1, 1):
        y = side * t / 2; part.box((x0, min(y, y + side * 0.07), z - 0.02), (x1, max(y, y + side * 0.07), z + 0.02), look)


def street(width):  # a painted panel door: a small wired-glass light high up, a raised panel below, a kickplate, a lever
    part = mesh(); w = width
    _framed(part, 0.0, w, (0.45, w - 0.45, 1.9, 2.6), 'door_green', 'wired'); _proud(part, 0.2, w - 0.2, 0.45, 1.6, 'door_green')
    _proud(part, 0.04, w - 0.04, 0.0, 0.25, 'steel', rise=0.003); _lever(part, w - 0.14)
    return part


def shop(width):  # an aluminium shop door, glass nearly whole, a push bar and a deep kick rail
    part = mesh(); w = width
    _framed(part, 0.0, w, (0.12, w - 0.12, 0.38, HEIGHT - 0.14), 'frame', 'glass', t=0.05); _bar(part, 0.15, w - 0.15, t=0.05)
    return part


def double_leaf(width):  # one leaf of a painted double door: a wired vision light, a raised panel, a kickplate, a push bar
    part = mesh(); w = width
    _framed(part, 0.0, w, (0.6, w - 0.6, 1.7, 2.5), 'door_red', 'wired'); _proud(part, 0.2, w - 0.2, 0.45, 1.45, 'door_red')
    _proud(part, 0.04, w - 0.04, 0.0, 0.25, 'steel', rise=0.003); _bar(part, 0.3, w - 0.1)
    return part


def steel_leaf(width):  # a security door of painted steel: stiffening ribs, a narrow vision slot, a heavy lever and a bolt
    part = mesh(); w = width
    _framed(part, 0.0, w, (w / 2 - 0.12, w / 2 + 0.12, 1.5, 2.1), 'door_steel', 'wired', t=0.07)
    for z in (0.6, 1.2, 2.4):
        _proud(part, 0.1, w - 0.1, z - 0.03, z + 0.03, 'door_steel', t=0.07, rise=0.012)
    _proud(part, 0.04, w - 0.04, 0.0, 0.3, 'galvanised', t=0.07, rise=0.004); _lever(part, w - 0.15, t=0.07)
    _proud(part, w - 0.2, w - 0.08, 1.35, 1.42, 'steel', t=0.07, rise=0.03)  # the deadbolt's case
    return part


def plain(width):  # a plain flush interior door with a lever
    part = mesh(); w = width; _framed(part, 0.0, w, None, 'door_cream', None, t=0.045); _lever(part, w - 0.12, t=0.045)
    return part


def gate_leaf(width):  # one leaf of a steel palisade gate: a frame, a middle rail and upright bars you see through
    part = mesh(); w = width; t = 0.06
    for low, high in (((0.0, -t / 2, 0.0), (0.07, t / 2, HEIGHT)), ((w - 0.07, -t / 2, 0.0), (w, t / 2, HEIGHT)),
                      ((0.0, -t / 2, 0.0), (w, t / 2, 0.07)), ((0.0, -t / 2, HEIGHT - 0.07), (w, t / 2, HEIGHT)),
                      ((0.0, -t / 2, 1.45), (w, t / 2, 1.53))):
        part.box(low, high, 'gate_paint', bevel=0.006)
    count = int((w - 0.14) / 0.14)
    for index in range(1, count + 1):
        x = 0.07 + index * (w - 0.14) / (count + 1); part.box((x - 0.014, -0.014, 0.07), (x + 0.014, 0.014, HEIGHT - 0.07), 'gate_paint')
    return part


def curtain(width, hazard=False):  # a roller shutter's curtain under its housing, a rubber seal at its foot
    part = mesh(); top = HEIGHT - 0.35
    part.box((-width / 2 + 0.06, -0.025, 0.06), (width / 2 - 0.06, 0.025, top), 'slats')
    part.box((-width / 2 + 0.06, -0.035, 0.0), (width / 2 - 0.06, 0.035, 0.06), 'rubber')
    if hazard:
        part.box((-width / 2 + 0.06, -0.028, 0.06), (width / 2 - 0.06, 0.028, 0.36), 'hazard')
    return part


def housing(width):  # the shutter's box and guide rails, which stay when it opens
    part = mesh(); top = HEIGHT - 0.35
    part.box((-width / 2, -0.2, top), (width / 2, 0.2, HEIGHT), 'galvanised', bevel=0.02)
    for side in (-1, 1):
        part.box((side * width / 2 - (0.06 if side > 0 else 0.0), -0.05, 0.0), (side * width / 2 + (0.0 if side > 0 else 0.06), 0.05, top), 'galvanised')
    return part


def strips(width):  # a strip curtain hanging from its rail: overlapping PVC strips, `0` at the rail
    part = mesh(); count = max(4, round(width / 0.25)); step = width / count
    for index in range(count):
        x = -width / 2 + index * step; y = 0.004 if index % 2 else -0.004
        part.box((x, y - 0.002, -(HEIGHT - 0.12)), (x + step + 0.03, y + 0.002, 0.0), 'pvc')
    return part


def rail(width):
    part = mesh(); part.box((-width / 2, -0.06, HEIGHT - 0.12), (width / 2, 0.06, HEIGHT), 'steel', bevel=0.01)
    return part


# model: (label, width, kind, sound appearance, blocks sight, build). Sizes are the user's (2026-11-19): 2 x 3 m
# singles, 4 x 3 m doubles and shutters, a 6 x 3 m gate and a 6 x 4 m loading shutter; and a 2 x 3 m shutter for the
# four hooks in Highrise_01's 8 m opening (2026-11-20).
DOORS = {
    'srn_dr_street': ('srn_StreetDoor', 2.0, 'swing', 0, 1, street),
    'srn_dr_shop': ('srn_ShopDoor', 2.0, 'swing', 0, 1, shop),
    'srn_dr_double': ('srn_DoubleDoor', 4.0, 'double', 0, 1, double_leaf),
    'srn_dr_steel': ('srn_SteelDoor', 2.0, 'swing', 7, 1, steel_leaf),
    'srn_dr_shut2': ('srn_Shutter2', 2.0, 'roll', 7, 1, None),
    'srn_dr_shut4': ('srn_Shutter4', 4.0, 'roll', 7, 1, None),
    'srn_dr_load': ('srn_LoadingShutter', 6.0, 'roll', 7, 1, None),
    'srn_dr_gate': ('srn_Gate', 6.0, 'double', 11, 0, gate_leaf),
    'srn_dr_inner': ('srn_InteriorDoor', 2.0, 'swing', 0, 1, plain),
    'srn_dr_strip': ('srn_StripCurtain', 2.0, 'flap', 24, 1, None),
}
TALL = {'srn_dr_load': 4.0}  # a door taller than `HEIGHT`
NAMES = dict(zip(DOORS, range(16777216 + 156, 16777216 + 166)))  # each door's name in the Toolset: custom talk table rows 156-165 (srx01.door.*), in DOORS' order
require(len(NAMES) == len(DOORS), 'A door has no name row: give the talk table a row for each door of DOORS and widen NAMES')


def _node(name, parent, part, position=(0.0, 0.0, 0.0)):
    lines = [f'node trimesh {name}', f'  parent {parent}', '  position {:.4f} {:.4f} {:.4f}'.format(*position), '  orientation 0.0 0.0 0.0 0.0',
             '  ambient 1.0 1.0 1.0', '  diffuse 1.0 1.0 1.0', '  specular 0.0 0.0 0.0', f'  bitmap {part.atlas}', '  render 1', '  shadow 1', '  tilefade 0']
    lines += [f'  verts {len(part.verts)}'] + [f'    {x:.4f} {y:.4f} {z:.4f}' for x, y, z in part.verts]
    lines += [f'  tverts {len(part.tverts)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in part.tverts]
    return lines + [f'  faces {len(part.faces)}'] + ['    ' + ' '.join(map(str, face)) for face in part.faces] + ['endnode']


def _dummy(name, parent, position=(0.0, 0.0, 0.0)):
    return [f'node dummy {name}', f'  parent {parent}', '  position {:.4f} {:.4f} {:.4f}'.format(*position), '  orientation 0.0 0.0 0.0 0.0', 'endnode']


def _sam(parent, width, height):  # the clicked mesh, `sam` as in the pack's doors: the doorway's face both ways, never drawn
    x, z = width / 2, height
    return ['node trimesh sam', f'  parent {parent}', '  position 0.0 0.0 0.0', '  orientation 0.0 0.0 0.0 0.0', '  render 1', '  shadow 0',
            '  alpha 0.0', '  transparencyhint 1', '  ambient 0.2 0.2 0.2', '  diffuse 0.8 0.8 0.8', '  specular 0.0 0.0 0.0', '  bitmap NULL',
            '  verts 4', f'    {-x} 0.0 0.0', f'    {x} 0.0 0.0', f'    {x} 0.0 {z}', f'    {-x} 0.0 {z}', '  tverts 1', '    0 0 0', '  faces 4',
            '    0 1 2 1 0 0 0 1', '    0 2 3 1 0 0 0 1', '    2 1 0 1 0 0 0 1', '    3 2 0 1 0 0 0 1', 'endnode']


def parts(model):
    """{name: (parent, mesh, position, motion)} of a door's moving and standing meshes and dummies. motion: ('turn',
    axis, angle one way) for a hinge, ('lift', rise) for a shutter's curtain, None for what stands."""
    label, width, kind, _, _, build = DOORS[model]; height = TALL.get(model, HEIGHT); found = {}
    if kind == 'swing':  # hinged on its left edge, as seen from -y
        found[f'{model}_hinge'] = (model, None, (-width / 2, 0.0, 0.0), ('turn', 'z', -90.0))
        found[f'{model}_leaf'] = (f'{model}_hinge', build(width), (0.0, 0.0, 0.0), None)
    elif kind == 'double':
        half = width / 2; leaf = build(half); other = mesh(); other.extend(leaf, lambda point: (-point[0], point[1], point[2]))
        other.faces = [(a, c, b, group, ta, tc, tb, look) for a, b, c, group, ta, tb, tc, look in other.faces]  # mirrored: wound back to face out
        found[f'{model}_hinge1'] = (model, None, (-half, 0.0, 0.0), ('turn', 'z', -90.0)); found[f'{model}_leaf1'] = (f'{model}_hinge1', leaf, (0.0, 0.0, 0.0), None)
        found[f'{model}_hinge2'] = (model, None, (half, 0.0, 0.0), ('turn', 'z', 90.0)); found[f'{model}_leaf2'] = (f'{model}_hinge2', other, (0.0, 0.0, 0.0), None)
    elif kind == 'roll':
        scale = height / HEIGHT; lifted = mesh(); body = curtain(width, hazard=model == 'srn_dr_load')
        lifted.extend(body, lambda point: (point[0], point[1], point[2] * scale)); box = mesh(); box.extend(housing(width), lambda point: (point[0], point[1], point[2] * scale))
        found[f'{model}_curtain'] = (model, lifted, (0.0, 0.0, 0.0), ('lift', height - 0.35 * scale))
        found[f'{model}_housing'] = (model, box, (0.0, 0.0, 0.0), None)
    else:  # flap: strips swinging up on the rail
        found[f'{model}_rail'] = (model, rail(width), (0.0, 0.0, 0.0), None)
        found[f'{model}_strips'] = (model, strips(width), (0.0, 0.0, HEIGHT - 0.12), ('turn', 'x', -75.0))
    return found


ANIMS = (('opening1', 1.0, 0.0, 1.0, 1), ('opened1', 0.0333, 1.0, 1.0, 1), ('closing1', 0.6667, 1.0, 0.0, 1),
         ('opening2', 1.0, 0.0, 1.0, -1), ('opened2', 0.0333, 1.0, 1.0, -1), ('closing2', 0.6667, 1.0, 0.0, -1),
         ('closed', 0.0333, 0.0, 0.0, 1), ('trans', 0.0333, 0.0, 0.0, 1))  # (name, length, open at its start, at its end, which way)


def _keys(motion, position, start, end, way, length):
    """An animated node's key lists at an animation's start and end: open 0 (closed) to 1 (opened)."""
    if motion[0] == 'turn':
        axis = {'x': (1, 0, 0), 'z': (0, 0, 1)}[motion[1]]
        turn = lambda amount: '{} {} {} {:.6f}'.format(*axis, math.radians(motion[2]) * way * amount)
        return ['    orientationkey', f'      0.0 {turn(start)}', f'      {length} {turn(end)}', '    endlist']
    rise = motion[1]; at = lambda amount: '{:.4f} {:.4f} {:.4f}'.format(position[0], position[1], position[2] + rise * amount)
    fade = lambda amount: f'{1.0 - amount:.2f}'  # rolled into its housing: up, and gone
    return (['    positionkey', f'      0.0 {at(start)}', f'      {length} {at(end)}', '    endlist',
             '    alphakey', f'      0.0 {fade(start)}', f'      {length} {fade(end)}', '    endlist'])


def model_text(model):
    """The door's model, uncompiled."""
    width = DOORS[model][1]; height = TALL.get(model, HEIGHT); found = parts(model)
    lines = [f'newmodel {model}', f'setsupermodel {model} NULL', 'classification Door', f'beginmodelgeom {model}', f'node dummy {model}', '  parent NULL', 'endnode']
    for suffix, z in (('grnd', 0.0), ('impc', height * 0.55), ('hhit', height * 0.72), ('head', height * 0.84)):
        lines += _dummy(f'{model}{suffix}', model, (0.0, 0.0, z))
    for name, (parent, part, position, _) in found.items():
        lines += _dummy(name, parent, position) if part is None else _node(name, parent, part, position)
    lines += _sam(model, width, height) + [f'endmodelgeom {model}', '']
    every = [(name, parent) for name, (parent, _, _, _) in found.items()] + [(f'{model}{suffix}', model) for suffix in ('grnd', 'impc', 'hhit', 'head')] + [('sam', model)]
    kind = lambda node: 'trimesh' if node == 'sam' or (node in found and found[node][1] is not None) else 'dummy'
    broken = (('die', 0.6667, 0.0, 1.0, 1), ('dead', 0.0333, 1.0, 1.0, 1))  # broken: thrown open the first way, and left so
    for name, length, start, end, way in ANIMS + broken:
        lines += [f'newanim {name} {model}', f'  length {length}', f'  transtime {0.0 if (name, length, start, end, way) in broken else 0.25}', f'  animroot {model}']
        lines += ['event 0.0333 detonate'] if name == 'die' else []
        lines += [f'  node dummy {model}', '    parent NULL', '  endnode']
        for node, parent in every:
            entry = found.get(node); motion = entry[3] if entry else None
            lines += [f'  node {kind(node)} {node}', f'    parent {parent}']
            if motion:
                lines += _keys(motion, entry[2], start, end, way, length)
            if node == 'sam':  # never drawn, and a quarter seen when the door is picked out (`trans`), as the pack's doors
                alpha = 0.25 if name == 'trans' else 0.0; lines += ['    alphakey', f'      0.0 {alpha}', f'      {length} {alpha}', '    endlist']
            lines += ['  endnode']
        lines += [f'doneanim {name} {model}', '']
    return '\n'.join(lines + [f'donemodel {model}', ''])


def _box_faces(low, high):
    """(verts, faces) of a closed box of NonWalk faces, wound to face out."""
    (x0, y0, z0), (x1, y1, z1) = low, high
    verts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return verts, [(a, b, c) for a, b, c, d in quads] + [(a, c, d) for a, b, c, d in quads]


def _turned(points, pivot, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [(pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s, pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c, z) for x, y, z in points]


def _walk(name, parent, boxes, position=(0.0, 0.0, 0.0)):
    verts, faces = [], []
    for points in boxes:
        box, made = _box_faces(*points) if isinstance(points[0], tuple) and len(points) == 2 else points
        faces += [(a + len(verts), b + len(verts), c + len(verts)) for a, b, c in made]; verts += box
    lines = [f'node trimesh {name}', f'  parent {parent}', '  position {:.4f} {:.4f} {:.4f}'.format(*position), '  orientation 0.0 0.0 0.0 0.0', '  bitmap NULL',
             f'  verts {len(verts)}'] + ['    {:.4f} {:.4f} {:.4f}'.format(*point) for point in verts]
    return lines + [f'  faces {len(faces)}'] + [f'    {a} {b} {c} 1 0 0 0 7' for a, b, c in faces] + ['endnode']


def walkmesh_text(model):
    """The door's .dwk: where it blocks closed and open each way, and the points a creature uses it from."""
    width = DOORS[model][1]; kind = DOORS[model][2]; height = TALL.get(model, HEIGHT); half = width / 2; t = 0.06
    closed = [((-half, -t, 0.0), (half, t, height))]
    if kind in ('swing', 'double'):
        leaves = [(-half, half, 1)] if kind == 'swing' else [(-half, 0.0, 1), (half, 0.0, -1)]  # (hinge x, other edge x, its side)

        def opened(way):
            boxes = []
            for hinge, other, side in leaves:
                verts, faces = _box_faces((min(hinge, other), -t / 2, 0.0), (max(hinge, other), t / 2, height))
                boxes.append((_turned(verts, (hinge, 0.0), -90.0 * way * side), faces))
            return boxes
        open1, open2 = opened(1), opened(-1)
    else:  # gone up or swung away: the doorway clear, slivers left at its jambs, as the pack's curtain door does
        open1 = open2 = [((-half, -t, 0.0), (-half + 0.1, t, height)), ((half - 0.1, -t, 0.0), (half, t, height))]
    lines = []
    for name, position in (('dp_closed_01', (0.0, -0.9, 0.0)), ('dp_closed_02', (0.0, 0.9, 0.0)), ('dp_open1_01', (0.0, -1.0 - half, 0.0)), ('dp_open2_01', (0.0, 1.0 + half, 0.0))):
        lines += _dummy(f'{model}_DWK_{name}', f'{model}_DWK', position)
    lines += _walk(f'{model}_DWK_wg_closed', f'{model}_DWK', closed)
    lines += _walk(f'{model}_DWK_wg_open1', f'{model}_DWK', open1) + _walk(f'{model}_DWK_wg_open2', f'{model}_DWK', open2)
    return '\n'.join(['# tilekit doorset: the door\'s walkmeshes', *lines, ''])


def rows(first=FIRST):
    """The doors' rows of genericdoors.2da: [(row, label, model, sound appearance, blocks sight)]."""
    return [(first + index, label, model, sound, sight) for index, (model, (label, _, _, sound, sight, _)) in enumerate(DOORS.items())]


def table(text, first=FIRST):
    """genericdoors.2da's text with the doors' rows written over the empty rows from `first`."""
    lines = text.replace('\r\n', '\n').split('\n'); ending = '\r\n' if '\r\n' in text else '\n'; wanted = {row: entry for row, *entry in rows(first)}
    for index, line in enumerate(lines):
        words = line.split()
        if words and words[0].isdigit() and int(words[0]) in wanted:
            require(words[1:] == ['****'] * 7 or words[1] == wanted[int(words[0])][0],
                    f'genericdoors.2da row {words[0]} is in use: the door set takes empty rows')
            label, model, sound, sight = wanted.pop(int(words[0]))
            lines[index] = f'{words[0]:<9}{label:<23}5349   {model:<16}{sight:<11}1            {sound:<13}{NAMES[model]}'
    require(not wanted, 'genericdoors.2da has no row ' + ', '.join(map(str, sorted(wanted))))
    return ending.join(lines)


def make(folder, masters, crunch, repo, *, compress=None):
    """Write every door's model and walkmesh, the atlas and genericdoors.2da with the doors' rows into `folder` (a
    review's overlay). {model: faces}."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for model in DOORS:
        text = model_text(model); (folder / f'{model}.mdl').write_text(text, encoding='ascii', newline='\n')
        (folder / f'{model}.dwk').write_text(walkmesh_text(model), encoding='ascii', newline='\n')
        told[model] = sum(len(part.faces) for _, part, _, _ in parts(model).values() if part is not None)
    made = kit.atlas(masters, LOOKS, GRIMY, {}, PAINTED); del made['glow']  # nothing on a door glows
    material.write(ATLAS, made, folder, crunch, compress=compress)
    source = Path(repo) / 'srn_2da' / 'genericdoors.2da'
    (folder / source.name).write_bytes(table(source.read_bytes().decode('cp1252')).encode('cp1252'))
    return told
