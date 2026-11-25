"""The room groups of a merged interior tileset: each room unfurnished (u) and furnished (f), as tiles of their own.

A room is made from a group of a source set (`shell`). The group's tiles are copied under new names, stripped of the
furniture built into them (`strip.shell`), given a ceiling and new pictures on what is built into their walls: the
unfurnished room. The furnished one is that again with shipped placeables baked in (`detail.place`), so every
furnishing is a placeable too. The source set's own tiles are left as they are: no walkmesh of theirs changes. The
models go to `sources/<pack>/` and are compiled as the other tiles are; `merge` numbers them and lays out both groups.

A room's spec, `docs/tilesets/<set>/rooms/<id>.json`:
{id, category, name: what the palette shows, "<category>: <name>" and "<category>: <name>, furnished";
 shell: {set, group}; ceiling: {texture, height, repeat (metres a picture covers)};
 unshadowed: [textures of the room itself that cast no shadow];
 faces: [{tile, node, texture, corners: [bottom left, bottom right, top right, top left, as seen from the room],
   screen: {texture, box: [left, top, right, bottom] of the picture, of: the picture's size}}] a built-in piece's face
   drawn once across a picture of its own, and a screen on it lit by itself;
 props, what stands on another after it: [{tile, piece, at: [x, y, z], faces: a compass point or turn: degrees, front: the compass point the piece
   faces unturned (s without it, as nearly all do), scale, obstacle}];
 placeLater: [what a builder places as a blueprint: containers, terminals, cameras]}.
`tile` counts the group's tiles from 0 as the set file does, from the south-west; it may be left out of a room of one.

What is baked or built in casts no shadow: a placeable's stencil shadow is hard, and a room's furniture shadows were
taken for those of props that were gone (user, 2026-11-24). A node with no `shadow` line casts one, so each is written.

Refused: a piece that is no row of placeables.2da; a piece that `faces` a wall (two were put in backwards,
2026-11-24); furniture that cuts the room in two or stands in its doorway (`_lanes`); a furnished room whose
walkmesh differs from the unfurnished one anywhere but under its furniture, or at its sides (`_rim`)."""
import hashlib
import json
import math
import re
import tempfile
from pathlib import Path

import numpy as np

from . import cuts, detail, geometry, inventory, require, strip, terrain
from .unique import unique

VARIANTS = (('u', ''), ('f', ', furnished'))
COMPASS = {name: angle for name, angle in zip(('e', 'ne', 'n', 'nw', 'w', 'sw', 's', 'se'), range(0, 360, 45))}
PROPS = ('srn_placeable', 'srn_envprop')  # the packs whose placeables are baked: a module loads both
AHEAD = 0.4  # metres in front of a piece that must be floor
STEP = 0.125  # metres: the walk grid's cells, finer than geometry's, which a partition a hand thick slips through
CELLS = int(round(2 * geometry.HALF / STEP))  # walk grid cells across a tile
ROUND = 2  # cells all round a place that must be walked for a player to stand there: a lane is 0.6 m at least
DOORWAY = 6  # cells: how near a doorway the room's own floor must come
TOGETHER = 0.85  # the share of the floor a player can stand on that must be one piece
FLOOR = 0.05  # metres: what stands no higher stands on the floor


def read(path):
    """A room's spec, checked for what can be told from it alone."""
    path = Path(path); spec = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(spec, dict) and spec.get('id') == path.stem and re.fullmatch(r'[a-z0-9]{1,6}', path.stem), f'{path.name}: a room is kept under its id, at most 6 lower case letters and digits')
    for key in ('category', 'name'):
        require(isinstance(spec.get(key), str) and spec[key].strip(), f'{path.name}: a room has a {key}')
    require(isinstance(spec.get('shell'), dict) and {'set', 'group'} <= set(spec['shell']), f'{path.name}: `shell` is {{set, group}}')
    for prop in spec.get('props', ()):
        require(('faces' in prop) != ('turn' in prop), f'{path.name}: {prop.get("piece")} has one of `faces` and `turn`')
    for prop in spec.get('placeLater', ()):
        require(isinstance(prop, dict) and prop.get('what'), f'{path.name}: `placeLater` lists {{what, ...}}')
    return spec


def specs(folder):
    """{id: spec} of a folder's rooms, in the order of their ids."""
    return {path.stem: read(path) for path in sorted(Path(folder).glob('*.json'))} if folder and Path(folder).is_dir() else {}


def shell_of(spec, set_text):
    """(rows, columns, [the group's tile numbers, -1 where it has none], [their models]) of a room's shell."""
    group = spec['shell']['group']
    keys = next((keys for name, keys in inventory.sections(set_text) if re.fullmatch(r'GROUP\d+', name) and keys['Name'] == group), None)
    require(keys, f'{spec["id"]}: {spec["shell"]["set"]} has no group {group}')
    rows, columns = int(keys['Rows']), int(keys['Columns']); members = [int(keys[f'Tile{index}']) for index in range(rows * columns)]
    models = {tile['number']: tile['model'] for tile in inventory.read_set(set_text)['tiles']}
    return rows, columns, members, [models.get(member) for member in members]


def model_name(prefix, room, variant, index):
    name = f'{prefix}_{room}{variant}_{index + 1:02d}'; require(len(name) <= 16, f'{name} is no resref'); return name


def records(rooms, sets, prefix):
    """[{room, name (of the group), display, set, rows, columns, tiles: [(the source tile, the new model) or None]}] of
    both variants of each room: what a merge adds to the set."""
    made = []
    for room, spec in rooms.items():
        require(spec['shell']['set'] in sets, f'{room}: {spec["shell"]["set"]} is no family of the set')
        rows, columns, members, _ = shell_of(spec, sets[spec['shell']['set']])
        for variant, said in VARIANTS:
            made.append({'room': room, 'name': f'{room}_{variant}', 'display': f'{spec["category"]}: {spec["name"]}{said}', 'set': spec['shell']['set'], 'rows': rows, 'columns': columns,
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
    made, wok, out = strip.shell(text, name)
    if 'ceiling' in spec:
        floor = next((node for node in nodes if kinds.get(node.name, ('',))[0] == 'floor'), None); require(floor, f'{name}: the shell draws no floor, whose look its ceiling takes')
        ceiling = spec['ceiling']; look = tuple(f'bitmap {ceiling["texture"]}' if line.split()[0].lower() in ('bitmap', 'materialname') else line for line in floor.look)
        made = ceiled(made, name, look, ceiling['height'], ceiling['repeat'])
    faces = [face for face in spec.get('faces', ()) if face.get('tile', 0) == index]
    made = faced(made, name, [{**face, 'node': terrain.renamed(face['node'], {root: name})} for face in faces])
    return unshadowed(made, casting), wok, out


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
        way = direction(COMPASS[prop['faces']]); middle = [(min(point[axis] for point in points) + max(point[axis] for point in points)) / 2 for axis in range(2)]
        reach = max((point[0] - middle[0]) * way[0] + (point[1] - middle[1]) * way[1] for point in points) + AHEAD
        require(geometry.cell((middle[0] + way[0] * reach, middle[1] + way[1] * reach), STEP) in walk, f'{piece} at {prop["at"]} faces {prop["faces"]}, and there is no floor before it: it stands back to front')
    obstacle = prop.get('obstacle', at[2] <= FLOOR and max(point[2] for point in points) > geometry.LOW)  # a rug is walked over
    return {'piece': piece, 'at': at, 'turn': turn, 'scale': scale, ('obstacle' if obstacle else 'rests'): True}


# --- what a room must hold to ----------------------------------------------------------------------------------------

def _floor(text):
    """{grid cell} of a tile whose middle is walked floor. Middles, not samples over each face: a face cut in many is
    sampled elsewhere, and cells at its sides came and went."""
    _, _, nodes = geometry.parse(text); at = (np.arange(CELLS) - CELLS // 2 + 0.5) * STEP + 1e-4; xs, ys = np.meshgrid(at, at, indexing='ij'); on = np.zeros_like(xs, bool)
    for node in nodes:
        if node.kind == 'aabb':
            for ((ax, ay, _), (bx, by, _), (cx, cy, _)), face in zip(geometry._corners(node, nodes), node.faces):
                whole = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
                if len(face) > 7 and face[7] in geometry.WALKABLE and abs(whole) > 1e-9:
                    first = ((bx - xs) * (cy - ys) - (by - ys) * (cx - xs)) / whole; second = ((cx - xs) * (ay - ys) - (cy - ys) * (ax - xs)) / whole
                    on |= (first >= -1e-9) & (second >= -1e-9) & (first + second <= 1 + 1e-9)
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


def _lanes(cells, openings):
    """What is wrong with a room's walked floor: `cells` {(column, row)} of the grid over the whole room, `openings`
    the cells at its sides. A player stands where the cells all round are walked too. [] when nothing is."""
    stands = {cell for cell in cells if all((cell[0] + x, cell[1] + y) in cells for x in range(-ROUND, ROUND + 1) for y in range(-ROUND, ROUND + 1))}; left = set(stands); biggest = set()
    while left:
        queue = [left.pop()]; piece = set(queue)
        while queue:
            x, y = queue.pop()
            for there in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if there in left:
                    left.discard(there); piece.add(there); queue.append(there)
        biggest = max(biggest, piece, key=len)
    if not stands or len(biggest) < TOGETHER * len(stands):
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
        require({one for one in rim if one[0] in outer} == {one for one in _rim(source) if one[0] in outer}, f'{names["u"]}: stripped, its floor meets the room\'s sides elsewhere than {model}\'s')
        bare = _floor(text); props = [prop for prop in spec.get('props', ()) if prop.get('tile', 0) == index]
        full, cut = (terrain.renamed(one, {names['u']: names['f']}) for one in (text, wok))
        if props:
            known = {prop['piece']: pieces[prop['piece']] for prop in props}
            full, _, walked, footprints = detail.place(full, names['f'], [placement(prop, known[prop['piece']], bare) for prop in props], None, dict(known), wok=cut)
            cut = walked or cut; full = unshadowed(full, {node.name.lower() for node in geometry.parse(full)[2] if not detail.is_kit(node.name)} - _quiet(full))
            floor = _floor(full); lost = sorted(bare - floor); gained = sorted(floor - bare)
            stray = [cell for cell in lost if not any(cuts.covers(polygon, ((cell[0] + 0.5) * STEP, (cell[1] + 0.5) * STEP), 0.02) for polygon, _, _ in footprints)]
            require(not stray and not gained, f'{names["f"]}: its walkmesh differs from the unfurnished room\'s elsewhere than under its furniture, at {(stray or gained)[:2]}')
            require(_rim(full) == rim, f'{names["f"]}: furniture stands at the tile\'s side')
        else:
            floor = bare
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
    return {piece: without_halos(geometry.parse(text)[2]) for piece, text in texts.items()}


def without_halos(nodes):
    """An envkit prop's nodes without its halo cards (material ek_..._h), which are drawn round a placeable's light: none is baked."""
    return [node for node in nodes if not re.fullmatch(r'ek_.*_h', node.material or '')]


def textured(repo, room, spec):
    """Refuse a room whose pictures no tile pack holds, or whose screen would not play: a flipbook is a TGA with a TXI
    that says `cycle`. In a DDS of either kind it drew as a pale film over what is behind it (client, 2026-11-24)."""
    held = lambda name, *ends: [path for end in ends for path in sorted(Path(repo).glob(f'srn_t_*/{name}{end}'))]
    for texture in {spec.get('ceiling', {}).get('texture')} | {face['texture'] for face in spec.get('faces', ())} - {None}:
        require(texture is None or held(texture, '.dds', '.tga', '.mtr'), f'{room}: no tile pack holds the texture {texture}')
    for texture in {face['screen']['texture'] for face in spec.get('faces', ()) if 'screen' in face}:
        require(held(texture, '.tga') and not held(texture, '.dds'), f'{room}: the screen {texture} is a TGA alone, with no DDS beside it: the game plays no other')
        require(any('proceduretype cycle' in path.read_text(encoding='ascii') for path in held(texture, '.txi')), f'{room}: the screen {texture} has no TXI that says cycle (`flipbook_txi`)')


def work(repo, merge_spec, blender=None, addon=None):
    """({file in the repository: its text} of every room, {room: what was done})."""
    repo = Path(repo); folder, sets = paths(repo, merge_spec); rooms = specs(folder); pack = f'srn_t_{merge_spec["set"]}'; files, told = {}, {}
    for room, spec in rooms.items():
        textured(repo, room, spec)
    pieces = pieces_of(repo, rooms, blender, addon)
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
    repo = Path(repo); folder, sets = paths(repo, merge_spec); rooms = specs(folder); found = {f'room:{room}': _hash((folder / f'{room}.json').read_bytes()) for room in rooms}
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
