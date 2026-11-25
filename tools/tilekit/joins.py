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
and of one surface is two faces.

A passage join (`passages`, shape `x`; srx02 plan, stage 3) is the tile on which one family's passage becomes
another's, between walls: the north half of one family's straight passage tile and the south half of the other's, and
across the seam a bulkhead with an opening as wide as both walk and as high as the lower ceiling. A side whose walked
floor is not level at the seam (a duct's round floor) is walked level over the last `RAMP` metres; what is drawn stays."""
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


def _half(triangles, start, end, left=True, solid=False):
    """The parts of `triangles` (each a 3 by n array, x and y first) on the left of the line start→end, or on its right.
    A part with no area seen from above is left out, as ground has none; solid: kept where it has area in space (a
    passage's upright walls)."""
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
            if (np.linalg.norm(np.cross(piece[1, :3] - piece[0, :3], piece[2, :3] - piece[0, :3])) > 1e-9) if solid else abs(flat_area(piece)) > 5e-10:
                kept.append(piece)
    return kept


def inside(triangles, polygon, solid=False):
    for index, start in enumerate(polygon):
        triangles = _half(triangles, start, polygon[(index + 1) % len(polygon)], solid=solid)
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


PASSAGE = 'x'
BULKHEAD = 0.2  # the thickness of the wall across a passage join
BAND = 0.05  # metres each side of the seam in which a passage's opening is measured
HEAD = 1.2  # what is drawn above this over the middle of a passage is its ceiling
PATH = ('L', 0)  # the path node of a straight passage, north to south


def walked(surface):
    return surface not in (2, 7)  # obscuring and non-walk faces are not walked


def _band(triangles, solid=False):
    return _half(_half(triangles, (-HALF, -BAND), (HALF, -BAND), solid=solid), (-HALF, BAND), (HALF, BAND), False, solid=solid)


def opening(side):
    """(west, east, clear height or None where nothing is overhead, top) of a baked passage tile where the seam cuts it."""
    drawn, walk = side; floor = _band([triangle for triangle in walk if walked(int(round(triangle[0, 3])))])
    require(floor, 'A passage tile is not walked across its middle')
    xs = np.concatenate([triangle[:, 0] for triangle in floor]); west, east = float(xs.min()), float(xs.max())
    cut = _band([triangle for triangles in drawn.values() for triangle in triangles], solid=True); points = np.vstack(cut) if cut else np.zeros((0, 5))
    over = points[(np.abs(points[:, 0] - (west + east) / 2) < (east - west) / 4) & (points[:, 2] > HEAD)]
    return west, east, (float(over[:, 2].min()) if len(over) else None), float(points[:, 2].max()) if len(points) else 0.0


def frame(north, south):
    """(west, east, height, top) of a passage join's opening and bulkhead, from its two sides' openings."""
    a, b = opening(north), opening(south); west, east = max(a[0], b[0]), min(a[1], b[1]); top = max(a[3], b[3])
    require(east - west > 1.0, 'The two passages do not meet: their walked floors overlap by less than a metre')
    clear = [height for height in (a[2], b[2]) if height is not None]
    return west, east, min(clear) if clear else top, top


def _space(triangle):
    return float(np.linalg.norm(np.cross(triangle[1, :3] - triangle[0, :3], triangle[2, :3] - triangle[0, :3])) / 2)


def wall_look(drawn):
    """(look, texture widths per metre) of a baked tile's walls: the look with the most upright surface."""
    best = None
    for look, triangles in drawn.items():
        upright = [triangle for triangle in triangles if _space(triangle) > 1e-6 and abs(flat_area(triangle)) < 0.3 * _space(triangle)]
        area = sum(_space(triangle) for triangle in upright)
        if upright and (best is None or area > best[0]):
            mapped = sum(abs(flat_area(triangle[:, 3:5])) for triangle in upright)
            best = (area, look, math.sqrt(mapped / area) if mapped > 1e-9 else 0.5)
    require(best is not None, 'A passage tile has no upright surface to take a wall look from')
    return best[1], best[2]


def bulkhead(north, south):
    """{look: [triangle]} of the wall across the seam, open where both passages are: each face in the wall look of the
    family it faces (`wall_look`), its picture laid by the metre; the opening's sides in the north family's."""
    thick = BULKHEAD; west, east, height, top = frame(north, south); near, far = -thick / 2, thick / 2; made = {}
    looks = {'north': wall_look(north[0]), 'south': wall_look(south[0])}

    def face(points, out, side):
        look, scale = looks[side]; points = [np.array(point, float) for point in points]
        if np.dot(np.cross(points[1] - points[0], points[2] - points[0]), out) < 0:
            points = points[::-1]
        across = max(range(3), key=lambda axis: abs(points[2][axis] - points[0][axis]) if axis != 2 else -1.0)  # the level axis the face runs along
        rows = [[*point, point[across] * scale, point[2] * scale] for point in points]
        made.setdefault(look, []).extend([np.array([rows[0], rows[1], rows[2]], float), np.array([rows[0], rows[2], rows[3]], float)])

    def box(x0, x1, z0, z1):
        if x1 - x0 < 1e-3 or z1 - z0 < 1e-3:
            return
        face([(x0, near, z0), (x1, near, z0), (x1, near, z1), (x0, near, z1)], (0, -1, 0), 'south')
        face([(x0, far, z0), (x1, far, z0), (x1, far, z1), (x0, far, z1)], (0, 1, 0), 'north')
        for x, out in ((x0, (-1, 0, 0)), (x1, (1, 0, 0))):
            face([(x, near, z0), (x, far, z0), (x, far, z1), (x, near, z1)], out, 'north')
        for z, out in ((z0, (0, 0, -1)), (z1, (0, 0, 1))):
            face([(x0, near, z), (x1, near, z), (x1, far, z), (x0, far, z)], out, 'north')
    box(-HALF, west, 0.0, top); box(east, HALF, 0.0, top); box(west, east, height, top)
    return made


def level(triangles, half):
    """A passage side's walk triangles with its walked floor falling to nothing over the last `RAMP` metres before the
    seam at y = 0, for a floor that is not level there. Only what is walked is kept, and the ground either side of it
    is plain and not walked: a duct's walkmesh folds back under its own wall, and laid flat its faces would overlap.
    half: the side's half of the tile (`NORTH` or `SOUTH`)."""
    floor = [triangle for triangle in triangles if walked(int(round(triangle[0, 3]))) and abs(flat_area(triangle)) > 1e-4]
    for line in (-RAMP, -RAMP / 2, RAMP / 2, RAMP):
        floor = _half(floor, (-HALF, line), (HALF, line)) + _half(floor, (-HALF, line), (HALF, line), False)
    made = []
    for triangle in floor:
        triangle = triangle.copy(); triangle[:, 2] *= np.clip(np.abs(triangle[:, 1]) / RAMP, 0.0, 1.0); made.append(triangle)
    xs = np.concatenate([triangle[:, 0] for triangle in made]); west, east = float(xs.min()), float(xs.max()); south, north = half[0][1], half[2][1]
    ground = [np.array([[*half[at], 0.0, 7.0, 0.0] for at in corners], float) for corners in ((0, 1, 2), (0, 2, 3))]  # surface 7: not walked
    return made + outside(ground, [(west, south), (east, south), (east, north), (west, north)])


def passage_model(name, north, south):
    """(a passage join's uncompiled model, its walkmesh file) from the two families' baked passage tiles (`bake`), each
    running north to south."""
    from tools.envkit import tile
    require(len(name) <= 16 and name == name.lower(), 'A tile model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', 'setanimationscale 1.0',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    walk, count = [], 0
    for letter, (drawn, floor), half in (('n', north, NORTH), ('s', south, SOUTH)):
        for look, triangles in drawn.items():
            cut = inside(triangles, half, solid=True)
            if cut:
                lines += _node(f'{name}_{letter}{count}', name, look, cut); count += 1
        cut = inside(floor, half); seam = _band([triangle for triangle in cut if walked(int(round(triangle[0, 3])))])
        walk += level(cut, half) if seam and max(abs(triangle[:, 2]).max() for triangle in seam) > 1e-3 else cut
    for index, (look, triangles) in enumerate(bulkhead(north, south).items()):
        lines += _node(f'{name}_b{index}', name, look, triangles)
    solid = lambda corners: np.linalg.norm(np.cross(corners[1] - corners[0], corners[2] - corners[0])) > 1e-7  # a sliver a cut left has no side to split
    walk = conformed([triangle for triangle in walk if solid(np.round(triangle[:, :3], 4))])
    lines += tile._walk_node(name, name, *walk) + [f'endmodelgeom {name}', f'donemodel {name}']
    return '\n'.join(lines) + '\n', tile.walk_text(name, walk)


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


def _cut(pair, shape):
    """Whether a pair has the join `shape`: the road joins only where both families have a road, since a road that
    ends at the boundary is laid only as part of one that crosses it."""
    return shape not in ROADS or ('road' in pair['city'] and 'road' in pair['other'])


def tiles(spec):
    """[{model, corners {TopLeft...: terrain}, crossers {Top...: crosser or ''}, minimap}] of the join tiles, in the
    order a merge numbers those new to it. One the merged set's numbers record holds keeps its number wherever it
    stands here (`merge.numbered`)."""
    made = []
    for passage in spec.get('passages', ()):  # between walls, one family's passage at the top and the other's at the bottom
        name = name_of(spec, passage, PASSAGE)
        made.append({'model': name, 'corners': dict.fromkeys(CORNERS, passage['wall']), 'minimap': 'mi_' + name, 'path': list(PATH),
                     'crossers': {**dict.fromkeys(SIDES, ''), 'Top': passage['north']['crosser'], 'Bottom': passage['south']['crosser']}})
    for pair in spec.get('pairs', ()):
        for shape in ('1', '2', '3', '4', 'r', 's', 't'):
            if not _cut(pair, shape):
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
    return [row for pair in spec.get('pairs', ()) for row in ((pair['city']['terrain'], pair['other']['terrain'], name_of(spec, pair, '2')),
                                                      (pair['other']['terrain'], pair['city']['terrain'], name_of(spec, pair, 'z')))]


def _find(repo, name, suffix):
    """A tile's file by its name: the kept source of a model first, then the packs."""
    found = sorted(Path(repo).glob(f'sources/srn_t_*/{name}{suffix}')) + sorted(Path(repo).glob(f'srn_t_*/{name}{suffix}'))
    require(found, f'No tile pack holds {name}{suffix}')
    return found[0]


def _picture(repo, name):
    """A tile's area-map picture: its TGA, or the DDS of a tile that has no other."""
    found = [path for suffix in ('.tga', '.dds') for path in sorted(Path(repo).glob(f'srn_t_*/{name}{suffix}'))]
    require(found, f'No tile pack holds the picture {name}')
    return found[0]


def inputs(repo, spec):
    """{what: path} of every file the joins are cut from."""
    found = {}
    for passage in spec.get('passages', ()):
        for side in ('north', 'south'):
            found[f'model:{passage[side]["model"]}'] = _find(repo, passage[side]['model'], '.mdl'); found[f'minimap:{passage[side]["minimap"]}'] = _picture(repo, passage[side]['minimap'])
    for pair in spec.get('pairs', ()):
        for side in ('city', 'other'):
            for kind in ('ground', 'road'):
                source = pair[side].get(kind)
                if source:
                    found[f'model:{source["model"]}'] = _find(repo, source['model'], '.mdl'); found[f'minimap:{source["minimap"]}'] = _find(repo, source['minimap'], '.tga')
    return found


def work(repo, spec):
    """{file path in the repository: its bytes} of everything a build writes."""
    repo = Path(repo); made = {}; baked = {}; from PIL import Image; import io
    from . import pictures

    def source(side, kind):
        key = (side[kind]['model'], side[kind].get('turn', 0))
        if key not in baked:
            baked[key] = bake(_find(repo, key[0], '.mdl').read_bytes().decode('cp1252'), key[1])
        picture = _picture(repo, side[kind]['minimap'])  # a BioWare DDS is read here, the image library does not know it
        return baked[key], (pictures.read(picture) if picture.suffix.lower() == '.dds' else Image.open(picture)).rotate(90 * key[1])
    for passage in spec.get('passages', ()):
        name = name_of(spec, passage, PASSAGE); (north, north_map), (south, south_map) = source(passage, 'north'), source(passage, 'south')
        text, walk = passage_model(name, north, south)
        made[f'sources/{spec["pack"]}/{name}.mdl'] = text.encode('ascii'); made[f'{spec["pack"]}/{name}.wok'] = walk.encode('ascii')
        held = io.BytesIO(); minimap('2', north_map, south_map).save(held, format='TGA'); made[f'{spec["pack"]}/mi_{name}.tga'] = held.getvalue()
    for pair in spec.get('pairs', ()):
        for shape in ('1', '2', '3', '4', 'r', 's', 't', 'z'):
            kinds = ROADS.get(shape, ('ground', 'ground'))
            if not _cut(pair, shape):
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
