"""The room groups of a merged interior tileset: each room unfurnished (u) and furnished (f), as tiles of their own.

A room is made from a group of a source set (`shell`). The group's tiles are copied under new names, stripped of the
furniture built into them (`strip.shell`), given a ceiling and new pictures on what is built into their walls: the
unfurnished room. The furnished one is that again with shipped placeables baked in (`detail.place`), so every
furnishing is a placeable too. The source set's own tiles are left as they are: no walkmesh of theirs changes. The
models go to `sources/<pack>/` and are compiled as the other tiles are; `merge` numbers them and lays out both groups.

A room's spec, `docs/tilesets/<set>/rooms/<id>.json`:
{id, category, name: what the palette shows, "Prefab: <category>: <name>" and the same with ", furnished"
  (`SHOWN`: user, 2026-11-25);
 shell: {set, group}, or {set, box} for one drawn here (`walls`); textures: {a texture of the shell or of a
   baked prop: what it draws instead}; ceiling: {texture, height, repeat (metres a picture covers)};
 unshadowed: [textures of the room itself that cast no shadow];
 faces: [{tile, node, texture, corners: [bottom left, bottom right, top right, top left, as seen from the room],
   screen: {texture, box: [left, top, right, bottom] of the picture, of: the picture's size}}] a built-in piece's face
   drawn once across a picture of its own, and a screen on it lit by itself;
 lamps, beams: what hangs from the ceiling (`ceilings`), each on its `tile`;
 props, what stands on another after it: [{tile, piece, at: [x, y, z], faces: a compass point or turn: degrees, scale, obstacle}];
 placeLater: [what a builder places as a blueprint: containers, terminals, cameras]}.
`tile` counts the group's tiles from 0 as the set file does, from the south-west; it may be left out of a room of one.
A spec that says `"inRoom": true` gives `at` in metres from the room's south-west corner, and no `tile`.

What is baked or built in casts no shadow: a placeable's stencil shadow is hard, and a room's furniture shadows were
taken for those of props that were gone (user, 2026-11-24). A node with no `shadow` line casts one, so each is written.

`fronts.json` beside the folder says which way every piece that `faces` somewhere looks unturned, each seen in a picture
(a couch, armchairs, dressers and wardrobes stood back to front: user, 2026-11-25).

Refused: a piece that is no row of placeables.2da, or that names a texture no pack holds; a piece whose front is not
recorded, or a seat or a cabinet recorded back to front (`leaning`, `bare`); a seat out of line with the table it faces (`misplaced`);
a piece that hangs over the edge of what it stands on (`unrested`) or off its wall (`unhung`); a walkmesh with cracks; a tile whose own floor is in parts, or that is
open to the room's next tile in two places; a piece that `faces` a wall (two were put in backwards,
2026-11-24); furniture that cuts the room in two or stands in its doorway (`_lanes`); a furnished room whose
walkmesh differs from the unfurnished one anywhere but under its furniture, or at its sides (`_rim`)."""
import hashlib
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import ceilings, cuts, detail, geometry, inventory, require, strip, terrain, walls
from .unique import unique

VARIANTS = (('u', ''), ('f', ', furnished'))
SHOWN = 'Prefab: {category}: {name}'  # what the palette calls a room
COMPASS = {name: angle for name, angle in zip(('e', 'ne', 'n', 'nw', 'w', 'sw', 's', 'se'), range(0, 360, 45))}
PROPS = ('srn_placeable', 'srn_envprop')  # the packs whose placeables are baked: a module loads both
AHEAD = 0.4  # metres in front of a piece that must be floor
STEP = 0.125  # metres: the walk grid's cells, finer than geometry's, which a partition a hand thick slips through
SLACK = 5e-4  # metres: a cell's middle may lie in the crack between two faces of a cut floor
CELLS = int(round(2 * geometry.HALF / STEP))  # walk grid cells across a tile
ROUND = 2  # cells all round a place that must be walked for a player to stand there: a lane is 0.6 m at least
DOORWAY = 6  # cells: how near a doorway the room's own floor must come
TOGETHER = 0.85  # the share of the floor a player can stand on that must be one piece
MOST = 2500  # triangles of one baked prop: envkit's run to 12,000, and a store of them passed the 65,535 vertices a mesh may have (2026-11-25)
WHOLE = 0.93  # and of one tile's alone: a creature finds its way from tile to tile, then within each
THIN = 0.3  # metres: a seat is deeper
REACH, ALIGNED = 1.2, 0.12  # metres: how far before a seat its table is, and how far off its middle the seat may stand
SNAP, NEAR = 0.05, 0.12  # metres: what a footprint's box is squared to, and how near a wall it is taken out to it
FLOOR = 0.05  # metres: what stands no higher stands on the floor
RESTED = 0.75  # the share of a foot that is on what it stands on: a crate on a crate's raised lid has 0.77
HANGS = 0.5  # metres: what is placed at the floor and begins no lower hangs on a wall
HUNG = 0.03  # metres: how far its back may be off it


def read(path):
    """A room's spec, checked for what can be told from it alone."""
    path = Path(path); spec = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(spec, dict) and spec.get('id') == path.stem and re.fullmatch(r'[a-z0-9]{1,6}', path.stem), f'{path.name}: a room is kept under its id, at most 6 lower case letters and digits')
    for key in ('category', 'name'):
        require(isinstance(spec.get(key), str) and spec[key].strip(), f'{path.name}: a room has a {key}')
    require(isinstance(spec.get('shell'), dict) and 'set' in spec['shell'] and ('group' in spec['shell']) != ('box' in spec['shell']), f'{path.name}: `shell` is {{set, group}} or {{set, box}}')
    for prop in spec.get('props', ()):
        require(('faces' in prop) != ('turn' in prop), f'{path.name}: {prop.get("piece")} has one of `faces` and `turn`')
    for prop in spec.get('placeLater', ()):
        require(isinstance(prop, dict) and prop.get('what'), f'{path.name}: `placeLater` lists {{what, ...}}')
    if spec.get('inRoom'):
        columns, rows = columns_rows = (spec['shell'].get('box') or spec)['columns'], (spec['shell'].get('box') or spec)['rows']
        for prop in [*spec.get('props', ()), *spec.get('lamps', ()), *spec.get('beams', ())]:
            middle = prop['at'] if 'at' in prop else [(prop['rect'][axis] + prop['rect'][axis + 2]) / 2 for axis in (0, 1)]
            column, row = (int(middle[axis] // walls.TILE) for axis in range(2)); require('tile' not in prop and column in range(columns) and row in range(rows), f'{path.name}: what is at {middle} is not in the room of {columns_rows}')
            prop['tile'] = row * columns + column; corner = (column * walls.TILE + geometry.HALF, row * walls.TILE + geometry.HALF)
            for key in ('at', 'rect'):
                if key in prop:
                    prop[key] = [round(value - corner[axis % 2], 4) if key == 'rect' or axis < 2 else value for axis, value in enumerate(prop[key])]
    return spec


def fronts_path(folder):
    return Path(folder).parent / 'fronts.json'


def specs(folder):
    """{id: spec} of a folder's rooms, in the order of their ids, each piece with its recorded front."""
    found = {path.stem: read(path) for path in sorted(Path(folder).glob('*.json'))} if folder and Path(folder).is_dir() else {}
    fronts = json.loads(fronts_path(folder).read_text(encoding='utf-8')) if found else {}
    for room, spec in found.items():
        for prop in spec.get('props', ()):
            if 'faces' in prop:
                require(prop['piece'] in fronts, f'{room}: {prop["piece"]} faces {prop["faces"]}, and fronts.json does not say which way it looks: look at it first'); prop['front'] = fronts[prop['piece']]
    return found


def shell_of(spec, set_text):
    """(rows, columns, [the group's tile numbers, -1 where it has none], [their models]) of a room's shell."""
    models = {tile['number']: tile['model'] for tile in inventory.read_set(set_text)['tiles']}
    if 'box' in spec['shell']:
        box = spec['shell']['box']; require(all(member in models for member in box['like']), f'{spec["id"]}: `like` names a tile the set lacks')
        return box['rows'], box['columns'], list(box['like']), [models[member] for member in box['like']]
    group = spec['shell']['group']
    keys = next((keys for name, keys in inventory.sections(set_text) if re.fullmatch(r'GROUP\d+', name) and keys['Name'] == group), None)
    require(keys, f'{spec["id"]}: {spec["shell"]["set"]} has no group {group}')
    rows, columns = int(keys['Rows']), int(keys['Columns']); members = [int(keys[f'Tile{index}']) for index in range(rows * columns)]
    return rows, columns, members, [models.get(member) for member in members]


def model_name(prefix, room, variant, index):
    name = f'{prefix}_{room}{variant}_{index + 1:02d}'; require(len(name) <= 16, f'{name} is no resref'); return name


def records(rooms, sets, prefix):
    """[{room, name (of the group), display, set, rows, columns, tiles: [(the source tile, the new model) or None]}] of
    both variants of each room: what a merge adds to the set."""
    made = []
    for room, spec in rooms.items():
        require(spec['shell']['set'] in sets, f'{room}: {spec["shell"]["set"]} is no family of the set')
        rows, columns, members, _ = shell_of(spec, sets[spec['shell']['set']]); plan = walls.Plan(spec) if 'box' in spec['shell'] else None
        for variant, said in VARIANTS:
            made.append({'room': room, 'name': f'{room}_{variant}', 'display': SHOWN.format(**spec) + said, 'set': spec['shell']['set'], 'rows': rows, 'columns': columns, 'paths': [walls.path(plan.sides(index)) for index in range(len(members))] if plan else [None] * len(members),
                         'tiles': [(member, model_name(prefix, room, variant, index)) if member >= 0 else None for index, member in enumerate(members)]})
    return made


# --- what a room is made of ------------------------------------------------------------------------------------------

def _into(text, parts):
    lines = text.split('\n'); end = next(index for index, line in enumerate(lines) if line.strip().lower().startswith('endmodelgeom'))
    return '\n'.join(lines[:end] + parts + lines[end:])


def ceiled(text, root, look, high, repeat):
    """The model with a ceiling over its whole cell, seen from below only: a camera over the room looks through it."""
    half = geometry.HALF; verts = [(-half, -half, high), (half, -half, high), (half, half, high), (-half, half, high)]
    return _into(text, geometry.mesh_text(f'{root}_ceil', root, look, verts, [(x / repeat, y / repeat) for x, y, _ in verts], [(0, 2, 1, 1, 0, 2, 1, 0), (0, 3, 2, 1, 0, 3, 2, 0)]))


def _quad(name, root, look, corners):
    return geometry.mesh_text(name, root, look, corners, [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 1, 2, 1, 0, 1, 2, 0), (0, 2, 3, 1, 0, 2, 3, 0)])


def faced(text, root, faces):
    """The model with each of `faces` in place of the mesh it names, and its screen a centimetre before it."""
    for number, face in enumerate(faces):
        lines, _, nodes = geometry.parse(text); old = [node for node in nodes if node.name.lower() == face['node'].lower() and node.rendered]
        require(len(old) == 1, f'{root} has no mesh {face["node"]}'); old = old[0]
        corners = [tuple(map(float, corner)) for corner in face['corners']]; require(len(corners) == 4 and all(len(corner) == 3 for corner in corners), f'{root} {face["node"]}: `corners` is four points')
        look = tuple(line for line in old.look if line.split()[0].lower() not in ('bitmap', 'texture0', 'materialname')) + (f'bitmap {face["texture"]}',)
        left, right, _, top = corners; across = [b - a for a, b in zip(left, right)]; up = [b - a for a, b in zip(left, top)]
        out = (across[1] * up[2] - across[2] * up[1], across[2] * up[0] - across[0] * up[2], across[0] * up[1] - across[1] * up[0]); length = math.hypot(*out)
        require(length > 1e-9, f'{root} {face["node"]}: `corners` bound nothing')
        parts = _quad(f'{root}_face{number}', root, look, corners)
        if 'screen' in face:
            screen = face['screen']; x0, y0, x1, y1 = (value / screen['of'] for value in screen['box']); require(0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, f'{root} {face["node"]}: a screen lies on its face')
            at = lambda u, v: tuple(left[axis] + across[axis] * u + up[axis] * (1 - v) + out[axis] / length * 0.01 for axis in range(3))
            lit = ('ambient 1.0 1.0 1.0', 'diffuse 1.0 1.0 1.0', 'specular 0.0 0.0 0.0', 'shininess 1.0', 'selfillumcolor 1.0 1.0 1.0', f'bitmap {screen["texture"]}')
            parts += _quad(f'{root}_screen{number}', root, lit, [at(x0, y1), at(x1, y1), at(x1, y0), at(x0, y0)])
        del lines[old.start:old.end + 1]; text = _into('\n'.join(lines), parts)
    return text


def unshadowed(text, casting):
    """The model with every drawn mesh not named in `casting` (lower case) casting no shadow."""
    lines, _, nodes = geometry.parse(text)
    for node in sorted((node for node in nodes if node.kind in geometry.MESHES and node.name.lower() not in casting), key=lambda node: -node.start):
        block = [line for line in lines[node.start:node.end + 1] if line.split()[:1] != [] and line.split()[0].lower() != 'shadow']
        lines[node.start:node.end + 1] = block[:2] + ['  shadow 0'] + block[2:]
    return '\n'.join(lines)


def unfurnished(text, name, spec, index):
    """(the unfurnished tile's model, its walkmesh file, [what was left out]) from a shell tile's uncompiled model."""
    text = unique(text.replace('\r\n', '\n'))[0]; lines, root, nodes = geometry.parse(text); kinds = strip.sort(nodes)
    quiet = {texture.lower() for texture in spec.get('unshadowed', ())}
    casting = {terrain.renamed(node.name, {root: name}).lower() for node in nodes if kinds.get(node.name, ('',))[0] in ('floor', 'shell', 'top') and node.material not in quiet}
    here = lambda key: [one for one in spec.get(key, ()) if one.get('tile', 0) == index]; hung = ceilings.overhead(name, here('lamps'), here('beams'))
    if 'box' in spec['shell']:
        made, wok, out = walls.shell(text, name, spec, index)
        return _into(made, hung), wok, out
    made, wok, out = strip.shell(text, name)
    if 'ceiling' in spec:
        floor = next((node for node in nodes if kinds.get(node.name, ('',))[0] == 'floor'), None); require(floor, f'{name}: the shell draws no floor, whose look its ceiling takes')
        ceiling = spec['ceiling']; look = tuple(f'bitmap {ceiling["texture"]}' if line.split()[0].lower() in ('bitmap', 'materialname') else line for line in floor.look)
        made = ceiled(made, name, look, ceiling['height'], ceiling['repeat'])
    faces = [face for face in spec.get('faces', ()) if face.get('tile', 0) == index]
    made = faced(made, name, [{**face, 'node': terrain.renamed(face['node'], {root: name})} for face in faces])
    return _into(terrain.retextured(unshadowed(made, casting), {old.lower(): new for old, new in spec.get('textures', {}).items()}), hung), wok, out


def direction(angle):
    return (math.cos(math.radians(angle)), math.sin(math.radians(angle)))


def placement(prop, nodes, walk):
    """A prop as `detail.place` takes it; `nodes` its model's, `walk` the unfurnished tile's floor (`_floor`)."""
    piece = prop['piece']; at = [float(value) for value in prop['at']]; scale = prop.get('scale', 1.0)
    if 'faces' in prop:
        require(prop['faces'] in COMPASS and prop.get('front', 's') in COMPASS, f'{piece}: `faces` and `front` are compass points, ' + ', '.join(COMPASS))
        turn = (COMPASS[prop['faces']] - COMPASS[prop.get('front', 's')]) % 360
    else:
        turn = prop['turn']
    parts = geometry.baked(nodes, detail.turned(at, turn, scale)); points = [vertex for _, verts, _, _ in parts for vertex in verts]; require(points, f'{piece} draws nothing')
    if 'faces' in prop:
        seat = leaning(nodes, prop.get('front', 's')); require(seat is None or seat > -0.1, f'{piece}: its back is at its recorded front, {prop.get("front", "s")}')
        require(bare(nodes, prop.get('front', 's')) > 1 / 3, f'{piece}: its back has far more on it than its recorded front, {prop.get("front", "s")}')
        way = direction(COMPASS[prop['faces']]); middle = [(min(point[axis] for point in points) + max(point[axis] for point in points)) / 2 for axis in range(2)]
        reach = max((point[0] - middle[0]) * way[0] + (point[1] - middle[1]) * way[1] for point in points) + AHEAD
        require(geometry.cell((middle[0] + way[0] * reach, middle[1] + way[1] * reach), STEP) in walk, f'{piece} at {prop["at"]} faces {prop["faces"]}, and there is no floor before it: it stands back to front')
    obstacle = prop.get('obstacle', at[2] <= FLOOR and max(point[2] for point in points) > geometry.LOW)  # a rug is walked over
    return {'piece': piece, 'at': at, 'turn': turn, 'scale': scale, ('obstacle' if obstacle else 'rests'): True}


def leaning(nodes, front):
    """How far back from a seat's middle its upper third lies, as a share of its depth: a chair's or a couch's is at its
    back. None of a piece of another height than a seat's, or too thin for one (a wall screen)."""
    points = [vertex for _, verts, _, _ in geometry.baked(nodes) for vertex in verts]; low, high = min(point[2] for point in points), max(point[2] for point in points)
    if not 0.6 <= high - low <= 1.25:
        return None
    way = direction(COMPASS[front]); along = [point[0] * way[0] + point[1] * way[1] for point in points]; total = weighed = 0.0
    if max(along) - min(along) < THIN:
        return None
    for triangle in geometry.faces_of(geometry.baked(nodes)):
        a, b, c = (np.array(point) for point in triangle); middle = (a + b + c) / 3
        if middle[2] > low + 0.65 * (high - low):
            area = float(np.linalg.norm(np.cross(b - a, c - a))); total += area; weighed += area * (middle[0] * way[0] + middle[1] * way[1])
    return ((min(along) + max(along)) / 2 - weighed / total) / (max(along) - min(along)) if total else None


def bare(nodes, front):
    """The triangles that look a piece's way against those that look back: a bookcase's shelves and doors are at its
    front (one was recorded by its plain back, 0.15; the least of 94 right ones is 0.50: 2026-11-25)."""
    way = direction(COMPASS[front]); seen = [0, 0]
    for triangle in geometry.faces_of(geometry.baked(nodes)):
        a, b, c = (np.array(point, float) for point in triangle); normal = np.cross(b - a, c - a); size = float(np.linalg.norm(normal))
        if size > 1e-9 and abs(look := (normal[0] * way[0] + normal[1] * way[1]) / size) > 0.7:
            seen[0 if look > 0 else 1] += 1
    return seen[0] / max(seen[1], 1) if max(seen) >= 12 else 1.0


def misplaced(props, pieces):
    """[what is wrong] with the seats of a tile: one that faces a table, a desk or a coffee table within `REACH` stands
    before its middle, or before some of it where it is long enough for several, and not in it (an armchair stood beside
    the coffee table it faced: user, 2026-11-25)."""
    boxes = []
    for prop in props:
        points = [vertex for _, verts, _, _ in geometry.baked(pieces[prop['piece']], detail.turned(prop['at'], (COMPASS[prop['faces']] - COMPASS[prop.get('front', 's')]) % 360 if 'faces' in prop else prop['turn'], prop.get('scale', 1.0))) for vertex in verts]
        low, high = ([pick(point[axis] for point in points) for axis in range(3)] for pick in (min, max)); boxes.append((prop, low, high))
    wrong = []
    for prop, low, high in boxes:
        if prop.get('faces') not in ('n', 'e', 's', 'w') or (leaning(pieces[prop['piece']], prop.get('front', 's')) or 0) < 0.1:
            continue
        axis = 0 if prop['faces'] in 'ew' else 1; ahead = prop['faces'] in 'en'; edge = (high if ahead else low)[axis]; across = 1 - axis; middle, half = (low[across] + high[across]) / 2, (high[across] - low[across]) / 2
        for other, start, end in boxes:
            if other is prop or other['at'][2] > FLOOR or not 0.3 <= end[2] <= 0.95 or (leaning(pieces[other['piece']], other.get('front', 's')) or 0) >= 0.1:
                continue
            gap = start[axis] - edge if ahead else edge - end[axis]; wide = end[across] - start[across]; off = abs(middle - (start[across] + end[across]) / 2)
            if not -0.3 <= gap <= REACH or off > half + wide / 2 or (start[axis] + end[axis]) / 2 < (low[axis] + high[axis]) / 2 and ahead or (start[axis] + end[axis]) / 2 > (low[axis] + high[axis]) / 2 and not ahead:
                continue
            if gap < 0.02 or (off > ALIGNED if wide < 1.4 else off + min(half, wide / 2) > wide / 2 + ALIGNED):
                wrong.append(f'{prop["piece"]} at {prop["at"][:2]} faces {other["piece"]} at {other["at"][:2]}, ' + ('and stands in it' if gap < 0.02 else f'{off:.2f} m off its middle'))
    return wrong


def _laid(prop, pieces):
    """A prop's triangles where it stands, as an array."""
    turn = (COMPASS[prop['faces']] - COMPASS[prop.get('front', 's')]) % 360 if 'faces' in prop else prop['turn']
    return np.array(geometry.faces_of(geometry.baked(pieces[prop['piece']], detail.turned(prop['at'], turn, prop.get('scale', 1.0)))), float).reshape(-1, 3, 3)


def unrested(props, pieces):
    """[what is wrong] with what stands on other furniture: at least `RESTED` of its foot is on it (a phone hung half
    off a desk: user, 2026-11-25). Its foot is the hull of what is within 3 cm of its lowest point."""
    stood = [(prop, _laid(prop, pieces)) for prop in props]; wrong = []
    for prop, mesh in stood:
        points = mesh.reshape(-1, 3); low = points[:, 2].min() if len(points) else 0
        if low <= FLOOR or prop['at'][2] <= FLOOR:
            continue
        foot = points[points[:, 2] < low + 0.03][:, :2]
        corners = np.array(cuts.hull([tuple(point) for point in foot.round(4).tolist()]), float)
        if len(corners) < 3:
            continue
        xs, ys = np.meshgrid(*(np.linspace(corners[:, axis].min(), corners[:, axis].max(), 15)[1:-1] for axis in (0, 1))); spots = np.stack([xs.ravel(), ys.ravel()], 1); inside = np.ones(len(spots), bool)
        for a, b in zip(corners, np.roll(corners, -1, 0)):
            inside &= (b[0] - a[0]) * (spots[:, 1] - a[1]) - (b[1] - a[1]) * (spots[:, 0] - a[0]) >= 0
        spots = spots[inside]; held = np.zeros(len(spots), bool)
        for other, under in stood:
            if other is prop or not len(under):
                continue
            normal = np.cross(under[:, 1] - under[:, 0], under[:, 2] - under[:, 0]); length = np.linalg.norm(normal, axis=1); up = (np.abs(normal[:, 2]) > 0.5 * length) & (length > 1e-9) & (np.abs(under[:, :, 2].mean(1) - low) < 0.5)
            for a, b, c in under[up]:
                whole = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
                if abs(whole) < 1e-12:
                    continue
                second = ((spots[:, 0] - a[0]) * (c[1] - a[1]) - (spots[:, 1] - a[1]) * (c[0] - a[0])) / whole; third = ((b[0] - a[0]) * (spots[:, 1] - a[1]) - (b[1] - a[1]) * (spots[:, 0] - a[0])) / whole
                height = a[2] + second * (b[2] - a[2]) + third * (c[2] - a[2]); held |= (second >= -1e-6) & (third >= -1e-6) & (second + third <= 1 + 1e-6) & (height > low - 0.035) & (height < low + 0.12)
        if len(spots) and held.mean() < RESTED:
            wrong.append(f'{prop["piece"]} at {prop["at"]}: {held.mean():.0%} of its foot is on what it stands on')
    return wrong


def unhung(props, pieces, text):
    """[what is wrong] with what hangs on a wall: its back is within `HUNG` of it (posters and white boards hung 8 to
    20 cm before theirs, 2026-11-25). text: the unfurnished tile."""
    wall = np.array(geometry.faces_of(geometry.baked(geometry.parse(text)[2])), float).reshape(-1, 3, 3); wrong = []
    for prop in props:
        mesh = _laid(prop, pieces) if 'faces' in prop else np.zeros((0, 3, 3))
        if not len(mesh) or prop['at'][2] > FLOOR or mesh[:, :, 2].min() < HANGS:
            continue
        points = mesh.reshape(-1, 3); way = -np.array([*direction(COMPASS[prop['faces']]), 0.0]); deep = points @ way; back = points[deep > deep.max() - 0.03]; spot = back.mean(0); spot = spot + way * (deep.max() - spot @ way)
        first, second = wall[:, 1] - wall[:, 0], wall[:, 2] - wall[:, 0]; across = np.cross(way, second); whole = (first * across).sum(1); safe = np.where(np.abs(whole) > 1e-9, whole, 1.0)
        away = spot - wall[:, 0]; u = (away * across).sum(1) / safe; turned = np.cross(away, first); v = (turned @ way) / safe; gap = (second * turned).sum(1) / safe
        met = gap[(np.abs(whole) > 1e-9) & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (np.abs(gap) < 0.5)]
        if not len(met) or abs(met[np.argmin(np.abs(met))]) > HUNG:
            wrong.append(f'{prop["piece"]} at {prop["at"]}: ' + (f'its back is {met[np.argmin(np.abs(met))] * 100:.0f} cm off its wall' if len(met) else 'there is no wall behind it'))
    return wrong


# --- what a room must hold to ----------------------------------------------------------------------------------------

def _floor(text, slack=0.0):
    """{grid cell} of a tile whose middle is walked floor. Middles, not samples over each face: a face cut in many is
    sampled elsewhere, and cells at its sides came and went. slack: metres by which a face reaches past its sides."""
    _, _, nodes = geometry.parse(text); at = (np.arange(CELLS) - CELLS // 2 + 0.5) * STEP + 1e-4; xs, ys = np.meshgrid(at, at, indexing='ij'); on = np.zeros_like(xs, bool)
    for node in nodes:
        if node.kind == 'aabb':
            for ((ax, ay, _), (bx, by, _), (cx, cy, _)), face in zip(geometry._corners(node, nodes), node.faces):
                whole = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
                if len(face) > 7 and face[7] in geometry.WALKABLE and abs(whole) > 1e-9:
                    first = ((bx - xs) * (cy - ys) - (by - ys) * (cx - xs)) / whole; second = ((cx - xs) * (ay - ys) - (cy - ys) * (ax - xs)) / whole
                    off = [1e-9 + slack * math.hypot(q[0] - p[0], q[1] - p[1]) / abs(whole) for p, q in (((ax, ay), (cx, cy)), ((ax, ay), (bx, by)), ((bx, by), (cx, cy)))]
                    on |= (first >= -off[0]) & (second >= -off[1]) & (first + second <= 1 + off[2])
    return {(int(x) - CELLS // 2, int(y) - CELLS // 2) for x, y in np.argwhere(on)}


def _rim(text):
    """{(side, grid step along it)} where a tile's walked floor reaches the side of its cell."""
    found = set()
    _, _, nodes = geometry.parse(text)
    for node in nodes:
        if node.kind == 'aabb':
            for triangle, face in zip(geometry._corners(node, nodes), node.faces):
                if len(face) > 7 and face[7] in geometry.WALKABLE:
                    found |= {(side, along) for side, along, _ in geometry.sides([triangle], STEP)}
    return found


def _alike(first, second):
    """Whether two rims are one, but for a cell at either end: a doorway's side on a cell's side falls to one or the other."""
    near = lambda one, others: any((one[0], one[1] + step) in others for step in (-1, 0, 1))
    return all(near(one, second) for one in first) and all(near(one, first) for one in second)


def crossed(set_text, number):
    """The sides (n, e, s, w) of a source tile a crosser lies on."""
    keys = dict(inventory.sections(set_text))[f'TILE{number}']
    return {side for side, key in (('n', 'Top'), ('e', 'Right'), ('s', 'Bottom'), ('w', 'Left')) if keys.get(key)}


def _walk(text):
    """[(three corners, surface)] of a tile's walkmesh."""
    _, _, nodes = geometry.parse(text)
    return [(np.round(np.array(triangle, float), 5), face[7]) for node in nodes if node.kind == 'aabb' for triangle, face in zip(geometry._corners(node, nodes), node.faces) if len(face) > 7]


def squared(polygon, lines):
    """The box round a footprint, out to the grid of `SNAP` and to a wall (`lines`: the floor's own along x and y) it
    nearly touches."""
    out = []
    for axis, (low, high) in enumerate((min(point[axis] for point in polygon), max(point[axis] for point in polygon)) for axis in (0, 1)):
        low, high = math.floor(low / SNAP + 1e-6) * SNAP, math.ceil(high / SNAP - 1e-6) * SNAP
        out.append([next((line for line in lines[axis] if abs(line - edge) <= NEAR), round(edge, 4)) for edge in (low, high)])
    return out[0][0], out[1][0], out[0][1], out[1][1]


def furnished_walk(text, name, footprints):
    """(the model, its walkmesh file, [the boxes nothing walks on]) with the floor of `text` laid again in rectangles
    round the footprints' boxes. Furniture cut out of the triangles there were left splinters and cracks a hair wide,
    and a creature stopped dead at them (a Troll in the apartment's middle, client, 2026-11-25). None for a floor
    whose sides run askew (its cut is kept, where `cracks` finds none)."""
    from types import SimpleNamespace
    from tools.envkit import tile
    from . import joins
    triangles = _walk(text); floor = [corners for corners, surface in triangles if surface in geometry.WALKABLE]; surface = next(surface for _, surface in triangles if surface in geometry.WALKABLE); edges = {}
    require(np.ptp(np.vstack(floor)[:, 2]) < 1e-3, f'{name}: its floor is not level'); high = float(np.vstack(floor)[0, 2])
    for corners in floor:
        for index in range(3):
            edges.setdefault(frozenset((tuple(corners[index]), tuple(corners[(index + 1) % 3]))), []).append(1)
    sides = [tuple(edge) for edge, owners in edges.items() if len(owners) == 1 and len(edge) == 2]
    if not all(abs(a[0] - b[0]) < 2e-3 or abs(a[1] - b[1]) < 2e-3 for a, b in sides):
        return None
    lines = [sorted({round(point[axis], 4) for side in sides for point in side if abs(side[0][axis] - side[1][axis]) < 2e-3}) for axis in (0, 1)]
    for axis in (0, 1):  # two lines a hair apart are one
        lines[axis] = [line for at, line in enumerate(lines[axis]) if not at or line - lines[axis][at - 1] > 2e-3]
    boxes = [squared(polygon, lines) for polygon, _, _ in footprints]
    xs, ys = (np.unique(np.round([*lines[axis], *(min(max(box[side], lines[axis][0]), lines[axis][-1]) for box in boxes for side in (axis, axis + 2))], 4)) for axis in (0, 1))
    flat = np.array(floor)[:, :, :2]; a, b, c = flat[:, 0], flat[:, 1], flat[:, 2]; whole = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    a, b, c, whole = (one[np.abs(whole) > 1e-9] for one in (a, b, c, whole))

    def kind(cell):
        x, y = (xs[cell[0]] + xs[cell[0] + 1]) / 2, (ys[cell[1]] + ys[cell[1] + 1]) / 2
        first = ((b[:, 0] - x) * (c[:, 1] - y) - (b[:, 1] - y) * (c[:, 0] - x)) / whole; second = ((c[:, 0] - x) * (a[:, 1] - y) - (c[:, 1] - y) * (a[:, 0] - x)) / whole
        if not ((first >= -1e-6) & (second >= -1e-6) & (first + second <= 1 + 1e-6)).any():
            return None
        return any(box[0] < x < box[2] and box[1] < y < box[3] for box in boxes)
    laid = walls.merged(SimpleNamespace(xs=xs, ys=ys), [(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)], kind); made = []
    for (x0, y0, x1, y1), taken in laid:
        for ring in (((x0, y0), (x1, y0), (x1, y1)), ((x0, y0), (x1, y1), (x0, y1))):
            made.append(np.array([[x, y, high, walls.SOLID if taken else surface, 0.0] for x, y in ring], float))
    near = lambda value, axis: next((line for line in lines[axis] if abs(line - value) <= 2e-3), value)
    for corners, of in triangles:
        if of not in geometry.WALKABLE:
            moved = np.array([[near(x, 0), near(y, 1), z, of, 0.0] for x, y, z in corners], float)
            if np.linalg.norm(np.cross(moved[1, :3] - moved[0, :3], moved[2, :3] - moved[0, :3])) > 1e-7:
                made.append(moved)
    mesh = joins.conformed(made); rows, _, nodes = geometry.parse(text); old = [node for node in nodes if node.kind == 'aabb']; require(len(old) == 1, f'{name} has one walkmesh')
    rows[old[0].start:old[0].end + 1] = tile._walk_node(old[0].name[:-3] if old[0].name.endswith('_wm') else name, name, *mesh)
    return '\n'.join(rows), tile.walk_text(name, mesh), boxes


def cracks(text):
    """[[x, y] of its middle] of each edge of a walked face that meets no other face's while there is floor on both sides,
    where a player can stand: behind a couch it stops nobody; and of each that more than two faces meet at."""
    floor = [corners for corners, surface in _walk(text) if surface in geometry.WALKABLE]; edges = {}
    for corners in floor:
        for index in range(3):
            edges.setdefault(frozenset((tuple(corners[index]), tuple(corners[(index + 1) % 3]))), []).append(corners)
    flat = np.array([corners for corners in floor if cuts._area(*corners) > 1e-6])[:, :, :2]; a, b, c = flat[:, 0], flat[:, 1], flat[:, 2]; whole = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])

    def covered(point):
        first = ((b[:, 0] - point[0]) * (c[:, 1] - point[1]) - (b[:, 1] - point[1]) * (c[:, 0] - point[0])) / whole; second = ((c[:, 0] - point[0]) * (a[:, 1] - point[1]) - (c[:, 1] - point[1]) * (a[:, 0] - point[0])) / whole
        return bool(((first >= -1e-7) & (second >= -1e-7) & (first + second <= 1 + 1e-7)).any())
    found, stands = [], _stands(_floor(text))
    for edge, owners in edges.items():
        if len(owners) > 2 or len(edge) < 2:
            found.append(np.array(list(edge))[:, :2].mean(0).round(2).tolist())
        elif len(owners) == 1:
            p, q = (np.array(point[:2]) for point in edge); length = np.hypot(*(q - p))
            if length > 0.02:
                across = np.array([p[1] - q[1], q[0] - p[0]]) / length * 0.01
                at = [(p + (q - p) * share) for share in (0.1, 0.5, 0.9)]; stood = any(geometry.cell(spot, STEP) in stands for spot in at)
                if stood and covered((p + q) / 2 + across) and covered((p + q) / 2 - across):
                    found.append(((p + q) / 2).round(2).tolist())
    return found


def _stands(cells):
    """The cells a player can stand on: those all round are walked too."""
    return {cell for cell in cells if all((cell[0] + x, cell[1] + y) in cells for x in range(-ROUND, ROUND + 1) for y in range(-ROUND, ROUND + 1))}


def _lanes(cells, openings, together=TOGETHER):
    """What is wrong with a room's walked floor: `cells` {(column, row)} of the grid over the whole room, `openings`
    the cells at its sides. A player stands where the cells all round are walked too. [] when nothing is."""
    stands = _stands(cells); left = set(stands); biggest = set()
    while left:
        queue = [left.pop()]; piece = set(queue)
        while queue:
            x, y = queue.pop()
            for there in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if there in left:
                    left.discard(there); piece.add(there); queue.append(there)
        biggest = max(biggest, piece, key=len)
    if not stands or len(biggest) < together * len(stands):
        return [f'of {len(stands)} places to stand only {len(biggest)} can be reached from one another']
    near = {(x + dx, y + dy) for x, y in biggest for dx in range(-DOORWAY, DOORWAY + 1) for dy in range(-DOORWAY, DOORWAY + 1)}
    shut = sorted(set(openings) - near)
    return [f'the way in at {shut[0][0] * STEP:.1f}, {shut[0][1] * STEP:.1f} m is blocked'] if shut else []


def _moved(cells, column, row):
    return {(x + CELLS // 2 + column * CELLS, y + CELLS // 2 + row * CELLS) for x, y in cells}


def made(room, spec, set_text, text_of, pieces, prefix):
    """{model: (its uncompiled model, its walkmesh file)} of both variants of a room, checked, and what was done:
    {left: {model: [parts left out]}, floor: square metres walked {u, f}, faces: {model: triangles drawn}}.
    text_of: a shell tile's uncompiled model by its name. pieces: {piece: its model's nodes}."""
    rows, columns, members, models = shell_of(spec, set_text); out = {}; told = {'left': {}, 'faces': {}, 'floor': {}}
    for prop in spec.get('props', ()):
        require(prop.get('tile', 0) in range(len(members)) and members[prop.get('tile', 0)] >= 0, f'{room}: {prop["piece"]} stands on no tile of the room')
        require('tile' in prop or len(members) == 1, f'{room}: {prop["piece"]} names no tile of the room\'s {len(members)}')
    floors = {'u': set(), 'f': set()}; openings = set()
    for index, (member, model) in enumerate(zip(members, models)):
        if member < 0:
            continue
        row, column = divmod(index, columns); names = {variant: model_name(prefix, room, variant, index) for variant, _ in VARIANTS}
        source = text_of(model); text, wok, left = unfurnished(source, names['u'], spec, index); told['left'][names['u']] = sorted(left)
        outer = {side for side, edge in (('w', column == 0), ('e', column == columns - 1), ('s', row == 0), ('n', row == rows - 1)) if edge}
        rim = _rim(text)
        ways = outer if 'box' not in spec['shell'] else outer & crossed(set_text, member)  # a tile a drawn room is like may itself be open to its group's next tile
        require(_alike({one for one in rim if one[0] in outer}, {one for one in _rim(source) if one[0] in ways}), f'{names["u"]}: its floor meets the room\'s sides elsewhere than {model}\'s')
        bare = _floor(text); props = [prop for prop in spec.get('props', ()) if prop.get('tile', 0) == index]
        full, cut = (terrain.renamed(one, {names['u']: names['f']}) for one in (text, wok))
        if props:
            known = {prop['piece']: pieces[prop['piece']] for prop in props}; wrong = misplaced(props, known) + unrested(props, known) + unhung(props, known, text); require(not wrong, f'{names["f"]}: ' + '; '.join(wrong))
            boxes = []

            def lay(new, footprints, uncut=cut):  # its floor is laid again round the furniture, from the unfurnished tile's; cutting the old one first took minutes a tile
                laid = furnished_walk(terrain.renamed(text, {names['u']: names['f']}), names['f'], footprints)
                if not laid:
                    boxes.extend(tuple(pick(point[axis] for point in polygon) for pick in (min, max) for axis in (0, 1)) for polygon, _, _ in footprints); return cuts.cut_walkmesh(new, uncut, footprints)
                boxes.extend(laid[2]); return detail.with_walkmesh_of(new, laid[0]), laid[1]
            full, _, walked, _ = detail.place(full, names['f'], [placement(prop, known[prop['piece']], bare) for prop in props], None, dict(known), wok=cut, lay=lay); cut = walked or cut
            full = terrain.retextured(full, {old.lower(): new for old, new in spec.get('textures', {}).items()})  # a prop's weak picture swapped
            full = unshadowed(full, {node.name.lower() for node in geometry.parse(full)[2] if not detail.is_kit(node.name)} - _quiet(full))
            torn = cracks(full); require(not torn, f'{names["f"]}: its walkmesh is cracked at {torn[:2]}, and nothing walks over a crack'); floor = _floor(full); lost = sorted(bare - _floor(full, SLACK)); gained = sorted(floor - _floor(text, SLACK))
            stray = [cell for cell in lost if not any(box[0] - 0.02 <= (cell[0] + 0.5) * STEP <= box[2] + 0.02 and box[1] - 0.02 <= (cell[1] + 0.5) * STEP <= box[3] + 0.02 for box in boxes)]
            require(not stray and not gained, f'{names["f"]}: its walkmesh differs from the unfurnished room\'s elsewhere than under its furniture, at {(stray or gained)[:2]}')
            require(_rim(full) == rim, f'{names["f"]}: furniture stands at the tile\'s side')
        else:
            floor = bare
        for name, one in ((names['u'], bare), (names['f'], floor)):
            wrong = _lanes(one, (), WHOLE); require(not wrong, f'{name}: within the tile, ' + '; '.join(wrong))
        for side in sorted({one[0] for one in rim} - outer):  # the game finds its way from tile to tile by whether they are open to one another at all
            along = sorted(step for way, step in rim if way == side); require(all(b - a <= 2 for a, b in zip(along, along[1:])), f'{names["u"]}: it is open to the next tile at its {side} side in two places, and a creature would take the wrong one')
        floors['u'] |= _moved(bare, column, row); floors['f'] |= _moved(floor, column, row)
        place = {'w': lambda a: (-CELLS // 2, a), 'e': lambda a: (CELLS // 2 - 1, a), 's': lambda a: (a, -CELLS // 2), 'n': lambda a: (a, CELLS // 2 - 1)}
        openings |= _moved({place[side](along) for side, along in rim if side in outer}, column, row)
        out[names['u']], out[names['f']] = (text, wok), (full, cut)
    for variant, floor in floors.items():
        wrong = _lanes(floor, openings); require(not wrong, f'{room}{variant}: ' + '; '.join(wrong)); told['floor'][variant] = round(sum(_walked(one[0]) for name, one in out.items() if name[:-3].endswith(variant)), 1)
    told['faces'] = {name: sum(len(node.faces) for node in geometry.parse(text)[2] if node.rendered) for name, (text, _) in out.items()}
    return out, told


def _walked(text):
    _, _, nodes = geometry.parse(text)
    return sum(cuts._area(*triangle) for node in nodes if node.kind == 'aabb' for triangle, face in zip(geometry._corners(node, nodes), node.faces) if len(face) > 7 and face[7] in geometry.WALKABLE)


def _quiet(text):
    """The meshes (lower case names) whose own lines say they cast no shadow."""
    return {node.name.lower() for node in geometry.parse(text)[2] if any(words[0].lower() == 'shadow' and words[1:2] == ['0'] for words in node.properties)}


# --- building ---------------------------------------------------------------------------------------------------------

def paths(repo, merge_spec):
    """(the folder of the set's room specs, {family: its set file})."""
    repo = Path(repo); require(merge_spec.get('rooms'), f'{merge_spec["set"]}: its merge spec names no `rooms` folder')
    return repo / merge_spec['rooms'], {family['set']: repo / f'srn_t_{family["set"]}' / f'{family["set"]}.set' for family in merge_spec['families']}


def _model(repo, name, set_name):
    from .compiled import source
    for pack in (f'srn_t_{set_name}', 'srn_t_common'):
        path = Path(repo) / pack / f'{name}.mdl'
        if path.is_file():
            return source(repo, path)
    require(False, f'No pack of {set_name} holds {name}.mdl')


def piece_paths(repo, rooms):
    """{piece: its pack model} of every prop, each refused where it is no row of placeables.2da."""
    table = {cells[3].lower() for cells in (inventory.words(line) for line in (Path(repo) / 'srn_2da' / 'placeables.2da').read_text(encoding='cp1252').splitlines()[3:]) if len(cells) > 3}; found = {}
    for room, spec in rooms.items():
        for prop in spec.get('props', ()):
            piece = prop['piece']; require(piece.lower() in table, f'{room}: {piece} is no model of placeables.2da: a furnishing is a placeable too')
            found[piece] = next((path for path in (Path(repo) / pack / f'{piece}.mdl' for pack in PROPS) if path.is_file()), None)
            require(found[piece], f'{room}: no pack of {", ".join(PROPS)} holds {piece}.mdl')
    return found


def _decompiled(paths_, blender, addon):
    from . import compiled
    tools = compiled.toolchain(blender, addon)
    with tempfile.TemporaryDirectory(prefix='tilekit-rooms-') as work:
        compiled._nvb().run(tools, [{'op': 'decompile', 'input': path, 'output': Path(work) / path.name, 'dirs': [path.parent]} for path in paths_.values()])
        return {piece: (Path(work) / path.name).read_bytes().decode('cp1252') for piece, path in paths_.items()}


def pieces_of(repo, rooms, blender=None, addon=None):
    """{piece: its model's nodes} of every prop; a compiled one is decompiled (`blender`, `addon`)."""
    found = piece_paths(repo, rooms); binary = {piece: path for piece, path in found.items() if inventory.compiled(path.read_bytes())}
    texts = {piece: path.read_bytes().decode('cp1252') for piece, path in found.items() if piece not in binary}
    if binary:
        require(blender and addon, 'These props are compiled, and only Blender with NeverBlender reads them (--blender, --addon): ' + ', '.join(sorted(binary)))
        texts.update(_decompiled(binary, blender, addon))
    return lighter({piece: without_halos(geometry.parse(text)[2]) for piece, text in texts.items()}, blender)


def lighter(pieces, blender):
    """{piece: nodes} with every piece of more than `MOST` triangles brought down to about that many (Blender); its
    drawn parts are then one mesh for each look, under its root."""
    heavy = {piece: geometry.merged(geometry.baked(nodes)) for piece, nodes in pieces.items() if sum(len(node.faces) for node in nodes if node.rendered) > MOST}
    if not heavy:
        return pieces
    require(blender, 'These props are baked with fewer triangles, and Blender does that (--blender): ' + ', '.join(sorted(heavy))); jobs = []
    for piece in sorted(heavy):
        whole = sum(len(faces) for _, _, _, faces in heavy[piece])
        jobs += [{'verts': [list(vertex) for vertex in verts], 'faces': [list(face[:3]) for face in faces], 'uvs': [list((tverts[corner] if tverts else (0, 0))[:2]) for face in faces for corner in face[4:7]],
                  'most': max(1, round(MOST * len(faces) / whole))} for _, verts, tverts, faces in heavy[piece]]
    with tempfile.TemporaryDirectory(prefix='tilekit-reduce-') as work_:
        source, target = Path(work_) / 'in.json', Path(work_) / 'out.json'; source.write_text(json.dumps(jobs), encoding='utf-8')
        ran = subprocess.run([str(blender), '-b', '-t', '4', '--factory-startup', '--python', str(Path(__file__).with_name('reduce_blender.py')), '--', str(source), str(target)], capture_output=True, text=True)
        require(ran.returncode == 0 and target.is_file(), 'Blender could not reduce the props: ' + (ran.stderr or ran.stdout).strip()[-400:]); done = iter(json.loads(target.read_text(encoding='utf-8')))
    out = dict(pieces)
    for piece in sorted(heavy):
        lines = [f'newmodel {piece}', f'beginmodelgeom {piece}', f'node dummy {piece}', '  parent null', 'endnode']
        for number, (look, *_) in enumerate(heavy[piece]):
            part = next(done); lines += geometry.mesh_text(f'{piece}_{number:02d}', piece, look, part['verts'], part['uvs'], [(*face, 1, 3 * at, 3 * at + 1, 3 * at + 2, 0) for at, face in enumerate(part['faces'])])
        out[piece] = geometry.parse('\n'.join(lines + [f'endmodelgeom {piece}', f'donemodel {piece}']))[2]
    return out


def without_halos(nodes):
    """An envkit prop's nodes without its halo cards (material ek_..._h), which are drawn round a placeable's light: none is baked."""
    return [node for node in nodes if not re.fullmatch(r'ek_.*_h', node.material or '')]


def drawn_by(spec):
    """The textures a room drawn here (`box`) names, and those of its lamps and beams."""
    box = spec['shell'].get('box', {}); said = [value for looks in [box.get('look', {})] + box.get('zones', []) for value in looks.values()]
    lamps = {ceilings.HOUSING, ceilings.DIFFUSER} if spec.get('lamps') else set()
    return {value for value in said if isinstance(value, str)} | lamps | {beam['texture'] for beam in spec.get('beams', ())} | {wall['bars'] for wall in box.get('walls', ()) if 'bars' in wall}


def textured(repo, room, spec):
    """Refuse a room whose pictures no tile pack holds, or whose screen would not play: a flipbook is a TGA with a TXI
    that says `cycle`. In a DDS of either kind it drew as a pale film over what is behind it (client, 2026-11-24)."""
    held = lambda name, *ends: [path for end in ends for pack in ('srn_t_*', 'srn_door', *PROPS) for path in sorted(Path(repo).glob(f'{pack}/{name}{end}'))]  # a tile draws what any pack of the module holds: the sets' black is a placeable's too
    for texture in {spec.get('ceiling', {}).get('texture')} | set(spec.get('textures', {}).values()) | drawn_by(spec) | {face['texture'] for face in spec.get('faces', ())} - {None}:
        require(texture is None or held(texture, '.dds', '.tga', '.mtr'), f'{room}: no tile pack holds the texture {texture}')
    for texture in {face['screen']['texture'] for face in spec.get('faces', ()) if 'screen' in face}:
        require(held(texture, '.tga') and not held(texture, '.dds'), f'{room}: the screen {texture} is a TGA alone, with no DDS beside it: the game plays no other')
        require(any('proceduretype cycle' in path.read_text(encoding='ascii') for path in held(texture, '.txi')), f'{room}: the screen {texture} has no TXI that says cycle (`flipbook_txi`)')


def untextured(repo, pieces):
    """Refuse a piece that names a texture no pack holds (the rifle stand's white rifles, user 2026-11-25). A name is
    cut to a resref's 16 characters, as the game cuts it."""
    held = {path.stem.lower() for pack in Path(repo).glob('srn_*') for path in pack.iterdir() if path.suffix.lower() in ('.dds', '.tga', '.plt', '.mtr')}
    for piece, nodes in pieces.items():
        missing = sorted({node.material for node in nodes if node.rendered and node.material and node.material.lower()[:16] not in held})
        require(not missing, f'{piece} draws {", ".join(missing)}, which no pack holds')


def work(repo, merge_spec, blender=None, addon=None):
    """({file in the repository: its text} of every room, {room: what was done})."""
    repo = Path(repo); folder, sets = paths(repo, merge_spec); rooms = specs(folder); pack = f'srn_t_{merge_spec["set"]}'; files, told = {}, {}
    for room, spec in rooms.items():
        textured(repo, room, spec)
    pieces = pieces_of(repo, rooms, blender, addon); untextured(repo, pieces)
    for room, spec in rooms.items():
        require(spec['shell']['set'] in sets, f'{room}: {spec["shell"]["set"]} is no family of the set')
        text_of = lambda name: _model(repo, name, spec['shell']['set']).read_bytes().decode('cp1252')
        tiles, told[room] = made(room, spec, sets[spec['shell']['set']].read_bytes().decode('cp1252'), text_of, pieces, merge_spec['set'])
        for name, (text, wok) in tiles.items():
            files[f'sources/{pack}/{name}.mdl'] = text.replace('\r\n', '\n'); files[f'{pack}/{name}.wok'] = wok.replace('\r\n', '\n')
    return files, told


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def inputs(repo, merge_spec):
    """{what: its hash} of everything the rooms are made from."""
    repo = Path(repo); folder, sets = paths(repo, merge_spec); rooms = specs(folder); found = {'fronts': _hash(fronts_path(folder).read_bytes()), **{f'room:{room}': _hash((folder / f'{room}.json').read_bytes()) for room in rooms}}
    for room, spec in rooms.items():
        name = spec['shell']['set']
        for model in filter(None, shell_of(spec, sets[name].read_bytes().decode('cp1252'))[3]):
            found[f'shell:{model}'] = _hash(_model(repo, model, name).read_bytes())
    found.update({f'piece:{piece}': _hash(path.read_bytes()) for piece, path in piece_paths(repo, rooms).items()})
    return dict(sorted(found.items()))


def stale(repo, merge_spec, lock_path):
    """What changed since the rooms were built: a room's spec, a tile or prop they are made from, a file they wrote."""
    if not Path(lock_path).is_file():
        return ['never built']
    repo = Path(repo); lock = json.loads(Path(lock_path).read_text(encoding='utf-8')); now = inputs(repo, merge_spec)
    changed = sorted(key for key in set(now) | set(lock['inputs']) if now.get(key) != lock['inputs'].get(key))
    return changed + sorted(path for path, said in lock['outputs'].items() if not (repo / path).is_file() or _hash((repo / path).read_bytes()) != said)


def build(repo, merge_spec, lock_path, blender=None, addon=None):
    """Write the rooms' sources and walkmeshes and the lock (then: merge, compile). {room: what was done}."""
    repo = Path(repo); files, told = work(repo, merge_spec, blender, addon)
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True); (repo / path).write_bytes(text.encode('cp1252'))
    lock = {'schemaVersion': 1, 'kind': 'tilekit-rooms', 'inputs': inputs(repo, merge_spec), 'outputs': {path: _hash(text.encode('cp1252')) for path, text in sorted(files.items())}}
    Path(lock_path).write_text(json.dumps(lock, indent=1) + '\n', encoding='utf-8', newline='\n')
    return told


# --- a screen that plays ----------------------------------------------------------------------------------------------

def flipbook(frames, across):
    """One picture of a screen's `frames` (pictures of one size, in order), `across` to a row. The game plays a sheet's
    rows from the bottom up, each from left to right (a recording, 2026-11-24): laid from the top down it plays out of order."""
    from PIL import Image
    width, height = frames[0].size; down = -(-len(frames) // across); require(len(frames) == across * down, 'A sheet\'s rows are full')
    sheet = Image.new('RGB', (width * across, height * down))
    for index, frame in enumerate(frames):
        require(frame.size == (width, height), 'A screen\'s frames are of one size')
        sheet.paste(frame.convert('RGB'), (index % across * width, (down - 1 - index // across) * height))
    return sheet


def flipbook_txi(frame, across, down, rate):
    return '\n'.join(['proceduretype cycle', f'defaultwidth {frame[0]}', f'defaultheight {frame[1]}', f'numx {across}', f'numy {down}', f'fps {rate}', ''])
