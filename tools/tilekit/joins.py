"""The join tiles of a merged tileset (srx01 plan, stage 3): the tiles on which one family's ground meets another's.

A join tile is cut from the families' own tiles: each side of the boundary is the plain ground tile of its family,
clipped to its side, so it draws that family's texture by name and follows that family's restyle when the joins are
built again. A flush strip of the city kit's concrete lies along the boundary. The boundary crosses a tile's edge at
its middle and at a right angle, so any two join tiles meet: a corner's ground is the quarter disc round it.

Shapes, by the corners the other family has (the city family has the rest): `1` the top left; `2` the bottom two;
`3` the top left and the bottom right; `4` all but the top left. `r` is `2` with a road across it: the north half of
the city's straight road tile and the south half of the other family's, whose heights fall to the city's flat ground
over the last `RAMP` metres. `s` and `t` are `2` with the city's road alone, ending at the boundary, and with the
other family's alone: the Toolset lays a road one tile edge at a time, and has no tile to lay without them. `z` is
`2` turned half round, for the area's border where the corners are named the other way about.

The walkmesh is the two sides' own, clipped the same way and made to share every vertex along the cut (a face whose
edge another face's corner lies on is split there: the game joins faces only by shared corners). Ground that is flat
and of one surface is two faces."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import geometry, kit, require

HALF = 5.0
ARC = 8  # segments of a corner's quarter circle
RAMP = 2.0  # metres over which a road's heights fall to the flat seam
STRIP = ('concrete', 0.3, 0.015)  # the boundary strip: its kit look, width and height above the ground
STRIP_LOOK = ('ambient 1.0 1.0 1.0', 'diffuse 1.0 1.0 1.0', 'specular 0.0 0.0 0.0', f'bitmap {kit.ATLAS}', 'render 1', 'shadow 0', 'tilefade 0')
CORNERS = {'TopLeft': (-HALF, HALF), 'TopRight': (HALF, HALF), 'BottomLeft': (-HALF, -HALF), 'BottomRight': (HALF, -HALF)}
SHAPES = {'1': ('TopLeft',), '2': ('BottomLeft', 'BottomRight'), '3': ('TopLeft', 'BottomRight'), '4': ('TopRight', 'BottomLeft', 'BottomRight'),
          'r': ('BottomLeft', 'BottomRight'), 's': ('BottomLeft', 'BottomRight'), 't': ('BottomLeft', 'BottomRight'), 'z': ('TopLeft', 'TopRight')}
ROADS = {'r': ('road', 'road'), 's': ('road', 'ground'), 't': ('ground', 'road')}  # shape: the tile each side is cut from, the city's first
SIDES = ('Top', 'Right', 'Bottom', 'Left')
MINIMAP = 32


def disc(corner):
    """The quarter disc round a tile corner as a polygon, counter-clockwise: the corner, then the arc."""
    x, y = CORNERS[corner]
    first, last = math.atan2(-y, 0.0), math.atan2(0.0, -x)  # from the corner toward the middle of each edge it lies on
    if (last - first) % (2 * math.pi) > math.pi:
        first, last = last, first
    sweep = (last - first) % (2 * math.pi)
    return [(x, y)] + [(x + HALF * math.cos(first + sweep * step / ARC), y + HALF * math.sin(first + sweep * step / ARC)) for step in range(ARC + 1)]


SOUTH = [(-HALF, -HALF), (HALF, -HALF), (HALF, 0.0), (-HALF, 0.0)]
NORTH = [(-HALF, 0.0), (HALF, 0.0), (HALF, HALF), (-HALF, HALF)]


def flat_area(triangle):
    """A triangle's area seen from above, positive where it is wound counter-clockwise."""
    (ax, ay), (bx, by), (cx, cy) = (corner[:2] for corner in triangle)
    return ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2


def _half(triangles, start, end, left=True):
    """The parts of `triangles` (each a 3 by n array, x and y first) on the left of the line start→end, or on its right."""
    start, end = np.asarray(start, float), np.asarray(end, float); along = end - start; kept = []
    for triangle in triangles:
        side = along[0] * (triangle[:, 1] - start[1]) - along[1] * (triangle[:, 0] - start[0])
        side = side if left else -side; side = np.where(np.abs(side) < 1e-9, 0.0, side); cut = []
        for index in range(3):
            here, there = triangle[index], triangle[(index + 1) % 3]; a, b = side[index], side[(index + 1) % 3]
            if a >= 0:
                cut.append(here)
            if a * b < 0:
                cut.append(here + (there - here) * (a / (a - b)))
        for index in range(1, len(cut) - 1):
            piece = np.array([cut[0], cut[index], cut[index + 1]])
            if abs(flat_area(piece)) > 5e-10:
                kept.append(piece)
    return kept


def inside(triangles, polygon):
    for index, start in enumerate(polygon):
        triangles = _half(triangles, start, polygon[(index + 1) % len(polygon)])
    return triangles


def outside(triangles, polygon):
    kept = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        kept += _half(triangles, start, end, False); triangles = _half(triangles, start, end)
    return kept


def sides(shape, city, other):
    """(the city family's triangles, the other family's) of the join `shape`, each clipped to its side."""
    if shape in ('1', '4'):
        ours, theirs = outside(city, disc('TopLeft')), inside(other, disc('TopLeft'))
        return (ours, theirs) if shape == '1' else (inside(city, disc('TopLeft')), outside(other, disc('TopLeft')))
    if shape == '3':
        return outside(outside(city, disc('TopLeft')), disc('BottomRight')), inside(other, disc('TopLeft')) + inside(other, disc('BottomRight'))
    if shape == 'z':
        return inside(city, SOUTH), inside(other, NORTH)
    return inside(city, NORTH), inside(other, SOUTH)


def seams(shape):
    """The boundary of the join `shape`: [the points of a line along it]."""
    arc = lambda corner: disc(corner)[1:]
    return {'1': [arc('TopLeft')], '4': [arc('TopLeft')], '3': [arc('TopLeft'), arc('BottomRight')]}.get(shape, [[(-HALF, 0.0), (HALF, 0.0)]])


def other_side(shape, x, y):
    """Whether the point lies on the other family's side of the join `shape`."""
    near = lambda corner: math.hypot(x - CORNERS[corner][0], y - CORNERS[corner][1]) < HALF
    return {'1': near('TopLeft'), '4': not near('TopLeft'), '3': near('TopLeft') or near('BottomRight'), 'z': y > 0}.get(shape, y < 0)


def ramp(triangles):
    """A south half whose heights fall to nothing over the last `RAMP` metres before the seam at y = 0."""
    for line in (-RAMP, -RAMP / 2):
        triangles = _half(triangles, (-HALF, line), (HALF, line)) + _half(triangles, (-HALF, line), (HALF, line), False)
    made = []
    for triangle in triangles:
        triangle = triangle.copy(); triangle[:, 2] *= np.clip(-triangle[:, 1] / RAMP, 0.0, 1.0); made.append(triangle)
    return made


def bake(text, turn=0):
    """({look: [triangle]}, [walk triangle]) of a tile's uncompiled model, turned `turn` quarters counter-clockwise. A
    triangle is a 3 by 5 array of x, y, z, u, v; a walk triangle's u is its surface."""
    _, _, nodes = geometry.parse(text); moves = geometry.placed(nodes); drawn, walk = {}, []

    def turned(point):
        x, y, z = point
        for _ in range(turn % 4):
            x, y = -y, x
        return x, y, z
    for node in nodes:
        points = [turned(moves[id(node)](vertex)) for vertex in node.verts]
        if node.kind == 'aabb':
            walk += [np.array([[*points[corner], face[7] if len(face) > 7 else 0, 0.0] for corner in face[:3]], float) for face in node.faces]
        elif node.rendered:
            require(node.kind == 'trimesh', f'{node.name} is a {node.kind}: a join is cut from trimesh nodes')
            into = drawn.setdefault(node.look, [])
            for face in node.faces:
                at = face[4:7] if len(face) >= 7 and node.tverts else None
                into.append(np.array([[*points[corner], *(node.tverts[at[index]][:2] if at else (0.0, 0.0))] for index, corner in enumerate(face[:3])], float))
    return drawn, walk


def conformed(triangles):
    """(vertices, faces [a, b, c, surface]) of walk triangles, every corner shared: a face with another's corner on
    one of its edges is split there, and corners closer than a tenth of a millimetre are one."""
    faces = [(np.round(triangle[:, :3], 4), int(round(triangle[0, 3]))) for triangle in triangles]
    points = np.unique(np.vstack([corners for corners, _ in faces]), axis=0); done = []
    while faces:
        corners, surface = faces.pop()
        for index in range(3):
            start, end = corners[index], corners[(index + 1) % 3]; along = end - start; length = np.linalg.norm(along)
            reach = (points - start) @ along / length ** 2; off = np.linalg.norm(points - start - reach[:, None] * along, axis=1)
            on = np.flatnonzero((off < 1e-4) & (reach > 1e-6 / length + 1e-5) & (reach < 1 - 1e-5))
            if len(on):
                middle = points[on[0]]; apex = corners[(index + 2) % 3]
                faces += [(np.array([start, middle, apex]), surface), (np.array([middle, end, apex]), surface)]
                break
        else:
            done.append((corners, surface))
    index = {tuple(point): number for number, point in enumerate(points.tolist())}
    made = [[index[tuple(corner)] for corner in corners.tolist()] + [surface] for corners, surface in done
            if np.linalg.norm(np.cross(corners[1] - corners[0], corners[2] - corners[0])) > 1e-7]
    used = sorted({corner for face in made for corner in face[:3]}); again = {old: new for new, old in enumerate(used)}
    return points[used], np.array(sorted([again[a], again[b], again[c], surface] for a, b, c, surface in made), int)


def walk_of(triangles):
    surfaces = {int(round(triangle[0, 3])) for triangle in triangles}
    if len(surfaces) == 1 and all(abs(triangle[:, 2]).max() < 1e-6 for triangle in triangles):  # flat and of one surface: the plain tile's two faces
        surface = surfaces.pop(); corner = [(-HALF, -HALF), (HALF, -HALF), (-HALF, HALF), (HALF, HALF)]
        triangles = [np.array([[*corner[at], 0.0, surface, 0.0] for at in face], float) for face in ((2, 0, 3), (3, 0, 1))]
    return conformed(triangles)


def strip(shape):
    """The boundary strip's (vertices, texture vertices, faces)."""
    look, width, height = STRIP; mesh = kit.Mesh()
    for line in seams(shape):
        line = np.array(line, float); ways = np.diff(line, axis=0); ways /= np.linalg.norm(ways, axis=1)[:, None]
        at = np.vstack([ways[:1], (ways[:-1] + ways[1:]) / 2, ways[-1:]]); at /= np.linalg.norm(at, axis=1)[:, None]
        across = np.c_[-at[:, 1], at[:, 0]] * width / 2
        for index in range(len(line) - 1):
            corners = [line[index] - across[index], line[index + 1] - across[index + 1], line[index + 1] + across[index + 1], line[index] + across[index]]
            mesh.facing([(float(x), float(y), height) for x, y in np.clip(corners, -HALF, HALF)], look, (0, 0, 1))
    return mesh.verts, mesh.tverts, mesh.faces


def _node(name, parent, look, triangles):
    corners = np.round(np.vstack(triangles), 5); found, where = np.unique(corners, axis=0, return_inverse=True); where = where.reshape(-1, 3)
    faces = [(a, b, c, 1, a, b, c, 0) for a, b, c in where.tolist()]
    return geometry.mesh_text(name, parent, look, [tuple(row[:3]) for row in found.tolist()], [tuple(row[3:5]) for row in found.tolist()], faces)


def model(name, shape, city, other):
    """(the join's uncompiled model, its walkmesh file) from the two families' baked tiles (`bake`). The other family's
    side of a road join is ramped (`ramp`)."""
    from tools.envkit import tile
    require(len(name) <= 16 and name == name.lower(), 'A tile model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', 'setanimationscale 1.0',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    walk, count = [], 0
    for letter, (drawn, walked), mine in (('c', city, 0), ('o', other, 1)):
        for look, triangles in drawn.items():
            cut = sides(shape, triangles, triangles)[mine]
            if mine and shape in ROADS:
                cut = ramp(cut)
            if cut:
                lines += _node(f'{name}_{letter}{count}', name, look, cut); count += 1
        cut = sides(shape, walked, walked)[mine]
        walk += ramp(cut) if mine and shape in ROADS else cut
    verts, tverts, faces = strip(shape)
    lines += geometry.mesh_text(f'{name}_s', name, STRIP_LOOK, verts, tverts, faces)
    walk = walk_of(walk)
    lines += tile._walk_node(name, name, *walk) + [f'endmodelgeom {name}', f'donemodel {name}']
    return '\n'.join(lines) + '\n', tile.walk_text(name, walk)


def minimap(shape, city, other):
    """The join's area-map picture from the two tiles' own (pictures, any size): MINIMAP square, north at the top."""
    from PIL import Image
    city, other = (np.asarray(picture.convert('RGB').resize((MINIMAP, MINIMAP))) for picture in (city, other)); made = city.copy()
    for row in range(MINIMAP):
        for column in range(MINIMAP):
            if other_side(shape, (column + 0.5) / MINIMAP * 2 * HALF - HALF, HALF - (row + 0.5) / MINIMAP * 2 * HALF):
                made[row, column] = other[row, column]
    return Image.fromarray(made)


def name_of(spec, pair, shape):
    return f'{spec["prefix"]}{pair["letter"]}{shape}_01'


def tiles(spec):
    """[{model, corners {TopLeft...: terrain}, crossers {Top...: crosser or ''}, minimap}] of the join tiles, in the
    order the merged set numbers them after its families' tiles."""
    made = []
    for pair in spec['pairs']:
        for shape in ('1', '2', '3', '4', 'r', 's', 't'):
            if shape in ROADS and not ('road' in pair['city'] and 'road' in pair['other']):
                continue
            name = name_of(spec, pair, shape)
            corners = {corner: pair['other' if corner in SHAPES[shape] else 'city']['terrain'] for corner in CORNERS}
            crossers = dict.fromkeys(SIDES, '')
            if ROADS.get(shape, ('', ''))[0] == 'road':
                crossers['Top'] = pair['city']['road']['crosser']
            if ROADS.get(shape, ('', ''))[1] == 'road':
                crossers['Bottom'] = pair['other']['road']['crosser']
            made.append({'model': name, 'corners': corners, 'crossers': crossers, 'minimap': 'mi_' + name})
    return made


def edges(spec):
    """[(corner 1, corner 2, model)]: the border rows of the join pairs, each way about."""
    return [row for pair in spec['pairs'] for row in ((pair['city']['terrain'], pair['other']['terrain'], name_of(spec, pair, '2')),
                                                      (pair['other']['terrain'], pair['city']['terrain'], name_of(spec, pair, 'z')))]


def _find(repo, name, suffix):
    """A tile's file by its name: the kept source of a model first, then the packs."""
    found = sorted(Path(repo).glob(f'sources/srn_t_*/{name}{suffix}')) + sorted(Path(repo).glob(f'srn_t_*/{name}{suffix}'))
    require(found, f'No tile pack holds {name}{suffix}')
    return found[0]


def inputs(repo, spec):
    """{what: path} of every file the joins are cut from."""
    found = {}
    for pair in spec['pairs']:
        for side in ('city', 'other'):
            for kind in ('ground', 'road'):
                source = pair[side].get(kind)
                if source:
                    found[f'model:{source["model"]}'] = _find(repo, source['model'], '.mdl'); found[f'minimap:{source["minimap"]}'] = _find(repo, source['minimap'], '.tga')
    return found


def work(repo, spec):
    """{file path in the repository: its bytes} of everything a build writes."""
    repo = Path(repo); made = {}; baked = {}; from PIL import Image; import io

    def source(side, kind):
        key = (side[kind]['model'], side[kind].get('turn', 0))
        if key not in baked:
            baked[key] = bake(_find(repo, key[0], '.mdl').read_bytes().decode('cp1252'), key[1])
        return baked[key], Image.open(_find(repo, side[kind]['minimap'], '.tga')).rotate(90 * key[1])
    for pair in spec['pairs']:
        for shape in ('1', '2', '3', '4', 'r', 's', 't', 'z'):
            kinds = ROADS.get(shape, ('ground', 'ground'))
            if kinds[0] not in pair['city'] or kinds[1] not in pair['other']:
                continue
            name = name_of(spec, pair, shape); (city, city_map), (other, other_map) = source(pair['city'], kinds[0]), source(pair['other'], kinds[1])
            text, walk = model(name, shape, city, other)
            made[f'sources/{spec["pack"]}/{name}.mdl'] = text.encode('ascii'); made[f'{spec["pack"]}/{name}.wok'] = walk.encode('ascii')
            if shape != 'z':
                held = io.BytesIO(); minimap(shape, city_map, other_map).save(held, format='TGA'); made[f'{spec["pack"]}/mi_{name}.tga'] = held.getvalue()
    return made


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def stale(repo, spec_path, lock_path):
    """What changed since the joins were built: the spec, a tile they are cut from, or a file they wrote."""
    repo = Path(repo); spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    if not Path(lock_path).is_file():
        return ['never built']
    lock = json.loads(Path(lock_path).read_text(encoding='utf-8')); now = {'spec': _hash(Path(spec_path).read_bytes())}
    now.update({key: _hash(path.read_bytes()) for key, path in inputs(repo, spec).items()})
    changed = sorted(key for key in set(now) | set(lock['inputs']) if now.get(key) != lock['inputs'].get(key))
    return changed + sorted(path for path, said in lock['outputs'].items() if not (repo / path).is_file() or _hash((repo / path).read_bytes()) != said)


def build(repo, spec_path, lock_path):
    """Write the join tiles' sources, walkmeshes and minimaps, and the lock. The sources are then compiled
    (`tilekit compile`). Returns {models, files}."""
    repo = Path(repo); spec = json.loads(Path(spec_path).read_text(encoding='utf-8')); made = work(repo, spec)
    for path, data in made.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True); (repo / path).write_bytes(data)
    lock = {'schemaVersion': 1, 'kind': 'tilekit-joins', 'inputs': {'spec': _hash(Path(spec_path).read_bytes()), **{key: _hash(path.read_bytes()) for key, path in sorted(inputs(repo, spec).items())}},
            'outputs': {path: _hash(data) for path, data in sorted(made.items())}}
    Path(lock_path).write_text(json.dumps(lock, indent=1) + '\n', encoding='utf-8', newline='\n')
    return {'models': sum(path.endswith('.mdl') for path in made), 'files': len(made)}
