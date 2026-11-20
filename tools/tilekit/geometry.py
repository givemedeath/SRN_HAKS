"""The geometry of an uncompiled tile model, for adding to it and rebuilding it without touching what a player walks on.

A tile is a 10 m cell centred on its root. Its walkmesh (the `aabb` node) is 2.5-dimensional: one walkable surface
over each spot, at ground level or on a walkable roof, balcony or stair. Everything here works in the tile's own
coordinates: a node's vertices are moved by its position and orientation, and by those of every node above it.

What a player stands in is the space above each walkable face, from `LOW` to `HEAD` metres over it. A face is sampled
every `STEP` metres across its surface (`samples`), and a sample is counted on a grid of `STEP`-metre cells (`grid`):
coarse enough to be quick on a thousand-face tile, fine enough that a pipe or a post shows."""
import math
import re

from . import require

LOW, HEAD = 0.25, 2.5  # metres over a walkable face: below LOW is the floor itself (kerbs, drains, decals), above HEAD is free
STEP = 0.25  # metres: how finely faces are sampled and counted
HALF = 5.0  # half a tile's side
EDGE = 0.02  # metres from the cell's side that count as on it
MESHES = {'trimesh', 'danglymesh', 'animmesh', 'skin'}
WALKABLE = {1, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 18, 19, 20, 21, 22, 30}  # surfacemat.2da rows with Walk = 1 (base game, 2026-11-19)
GEOMETRY = {'verts', 'faces', 'tverts', 'normals', 'tangents', 'colors', 'weights', 'constraints', 'aabb'}  # lists a node's header counts
TRANSFORM = {'parent', 'position', 'orientation', 'wirecolor', 'scale'}
NODE = re.compile(r'(?im)^[ \t]*node[ \t]+(\S+)[ \t]+(\S+)')


class Node:
    """One node of a model's geometry: its kind, name, parent, the line numbers it spans, its own property lines (as
    words), and for a mesh its vertices, texture vertices and faces."""

    def __init__(self, kind, name, start):
        self.kind, self.name, self.start, self.end = kind.lower(), name, start, None
        self.parent, self.position, self.orientation = None, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)
        self.verts, self.tverts, self.faces, self.properties, self.lists = [], [], [], [], {}

    @property
    def rendered(self):
        said = [words for words in self.properties if words[0].lower() == 'render']
        return self.kind in MESHES and not (said and said[-1][1:2] == ['0'])

    @property
    def look(self):
        """The property lines that decide how the mesh looks: what two meshes must share to be drawn as one."""
        return tuple(' '.join(words) for words in self.properties if words[0].lower() not in TRANSFORM)

    @property
    def material(self):
        for key in ('materialname', 'bitmap', 'texture0'):
            said = [words[1].lower() for words in self.properties if words[0].lower() == key and len(words) > 1]
            if said and said[-1] != 'null':
                return said[-1]
        return None


def parse(text):
    """(lines, root name, [Node]) of an uncompiled model's geometry, in the order the model lists them."""
    lines = text.replace('\r\n', '\n').split('\n'); nodes, node, index, root = [], None, 0, None
    while index < len(lines):
        words = lines[index].split()
        if not words:
            index += 1; continue
        head = words[0].lower()
        if head == 'beginmodelgeom' and len(words) > 1:
            root = words[1]
        elif head in ('endmodelgeom', 'newanim'):
            break
        elif head == 'node' and len(words) >= 3:
            node = Node(words[1], words[2], index); nodes.append(node)
        elif head == 'endnode' and node is not None:
            node.end = index; node = None
        elif node is not None:
            if head == 'parent' and len(words) > 1:
                node.parent = None if words[1].lower() == 'null' else words[1]
            elif head == 'position' and len(words) >= 4:
                node.position = tuple(float(value) for value in words[1:4])
            elif head == 'orientation' and len(words) >= 5:
                node.orientation = tuple(float(value) for value in words[1:5])
            if head in GEOMETRY and len(words) > 1 and words[1].isdigit():
                count = int(words[1]); rows = [lines[index + 1 + row].split() for row in range(count)]
                node.lists[head] = rows; index += count
                if head == 'verts':
                    node.verts = [tuple(float(value) for value in row[:3]) for row in rows]
                elif head == 'tverts':
                    node.tverts = [tuple(float(value) for value in row[:2]) for row in rows]
                elif head == 'faces':
                    node.faces = [tuple(int(value) for value in row[:8]) for row in rows]
            elif head not in ('parent', 'position', 'orientation'):
                node.properties.append(words)
        index += 1
    require(root, 'The model has no geometry (beginmodelgeom)')
    require(all(node.end is not None for node in nodes), 'A node of the model has no endnode')
    return lines, root, nodes


def _rotate(axis_angle, point):
    x, y, z, angle = axis_angle; length = math.sqrt(x * x + y * y + z * z)
    if length == 0 or angle == 0:
        return point
    x, y, z = x / length, y / length, z / length; c, s = math.cos(angle), math.sin(angle); px, py, pz = point
    dot = x * px + y * py + z * pz
    return (px * c + (y * pz - z * py) * s + x * dot * (1 - c),  # Rodrigues: v cos + (k x v) sin + k (k.v)(1 - cos)
            py * c + (z * px - x * pz) * s + y * dot * (1 - c),
            pz * c + (x * py - y * px) * s + z * dot * (1 - c))


def placed(nodes):
    """{node name (lowercase): function taking a point in the node's own space to the model's}."""
    named = {node.name.lower(): node for node in nodes}; made = {}

    def of(name, seen=()):
        key = name.lower()
        if key in made:
            return made[key]
        node = named.get(key)
        if node is None:
            return lambda point: point
        require(key not in seen, f'{node.name} is its own ancestor')
        above = of(node.parent, seen + (key,)) if node.parent else (lambda point: point)

        def move(point, node=node, above=above):
            turned = _rotate(node.orientation, point)
            return above(tuple(turned[axis] + node.position[axis] for axis in range(3)))
        made[key] = move
        return move
    return {node.name.lower(): of(node.name) for node in nodes}


def triangles(nodes, chosen=lambda node: node.rendered):
    """[(a, b, c)] of the chosen nodes' faces, in the model's coordinates."""
    moves, found = placed(nodes), []
    for node in nodes:
        if not chosen(node):
            continue
        points = [moves[node.name.lower()](vertex) for vertex in node.verts]
        for face in node.faces:
            if max(face[:3]) < len(points):
                found.append(tuple(points[corner] for corner in face[:3]))
    return found


def samples(triangle, step=STEP):
    """Points over a triangle, no more than about `step` apart, its corners among them."""
    a, b, c = triangle
    longest = max(math.dist(a, b), math.dist(b, c), math.dist(c, a)); count = max(1, math.ceil(longest / step))
    for i in range(count + 1):
        for j in range(count + 1 - i):
            u, v = i / count, j / count; w = 1 - u - v
            yield tuple(a[axis] * w + b[axis] * u + c[axis] * v for axis in range(3))


def cell(point, step=STEP):
    return (math.floor(point[0] / step), math.floor(point[1] / step))


def walkable(nodes, step=STEP):
    """{grid cell: [heights of the walkable surfaces over it]} from the model's walkmesh: each walkable face sampled."""
    told = {}
    for triangle, face in ((t, f) for node in nodes if node.kind == 'aabb' for t, f in zip(_corners(node, nodes), node.faces)):
        if len(face) < 8 or face[7] not in WALKABLE:
            continue
        for point in samples(triangle, step / 2):
            heights = told.setdefault(cell(point, step), [])
            if not any(abs(height - point[2]) < HEAD for height in heights):  # one surface per storey over a cell
                heights.append(point[2])
            else:
                index = next(index for index, height in enumerate(heights) if abs(height - point[2]) < HEAD)
                heights[index] = max(heights[index], point[2])
    return told


def _corners(node, nodes):
    move = placed(nodes)[node.name.lower()]; points = [move(vertex) for vertex in node.verts]
    return [tuple(points[corner] for corner in face[:3]) for face in node.faces if max(face[:3]) < len(points)]


def in_the_way(triangles_, walk, step=STEP, low=LOW, head=HEAD):
    """{grid cell: heights} of the samples of `triangles_` standing where a player stands: between `low` and `head`
    metres over a walkable surface of `walk`, whether that surface is the street or a roof."""
    found = {}
    for triangle in triangles_:
        for point in samples(triangle, step):
            key = cell(point, step)
            for height in walk.get(key, ()):
                if height + low < point[2] < height + head:
                    found.setdefault(key, set()).add(round(height, 2))
    return found


def floors(triangles_, walk, step=STEP, near=0.15):
    """The walkable grid cells over which `triangles_` draw a surface within `near` metres of the walkable height: the
    floor a player sees under their feet."""
    found = set()
    for triangle in triangles_:
        for point in samples(triangle, step):
            key = cell(point, step)
            if any(abs(point[2] - height) <= near for height in walk.get(key, ())):
                found.add(key)
    return found


def outside(triangles_, half=HALF, tolerance=0.001):
    """The corners of `triangles_` outside the tile's cell, as (x, y)."""
    return sorted({(round(point[0], 3), round(point[1], 3)) for triangle in triangles_ for point in triangle
                   if abs(point[0]) > half + tolerance or abs(point[1]) > half + tolerance})


def reach(triangles_, half=HALF):
    """(west, east, south, north): how far `triangles_` reach from the tile's centre on each side, at least the cell's."""
    points = [point for triangle in triangles_ for point in triangle]
    return (max([half] + [-point[0] for point in points]), max([half] + [point[0] for point in points]),
            max([half] + [-point[1] for point in points]), max([half] + [point[1] for point in points]))


def beyond(triangles_, limits, tolerance=0.001):
    """The corners of `triangles_` reaching past `limits` (west, east, south, north), as (x, y)."""
    west, east, south, north = (limit + tolerance for limit in limits)
    return sorted({(round(point[0], 3), round(point[1], 3)) for triangle in triangles_ for point in triangle
                   if -point[0] > west or point[0] > east or -point[1] > south or point[1] > north})


def low_massing(triangles_, step=STEP, low=LOW, head=HEAD):
    """{grid cell} of the samples between `low` and `head` metres over the tile's root: the shape a player sees at street
    level, its floor apart (the street itself is everywhere)."""
    return {cell(point, step) for triangle in triangles_ for point in samples(triangle, step) if low <= point[2] < head}


def sides(triangles_, step=STEP, half=HALF, edge=EDGE):
    """{(side, along, height)} on a step grid of the samples lying on the cell's four sides: the profile a neighbour meets."""
    found = set()
    for triangle in triangles_:
        for point in samples(triangle, step):
            x, y, z = point
            for side, across, along in (('w', -x, y), ('e', x, y), ('s', -y, x), ('n', y, x)):
                if abs(across - half) <= edge:
                    found.add((side, math.floor(along / step), math.floor(z / step)))
    return found


def grown(cells):
    """`cells` with every cell next to one of them: a grid's tolerance of one step."""
    return {(key[0] + dx, key[1] + dy, *key[2:]) for key in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def mesh_text(name, parent, look, verts, tverts, faces, indent='  '):
    """An uncompiled trimesh node holding `verts` already in the parent's space."""
    out = [f'node trimesh {name}', f'{indent}parent {parent}', f'{indent}position 0.0 0.0 0.0', f'{indent}orientation 0.0 0.0 0.0 0.0']
    out += [indent + line for line in look]
    out.append(f'{indent}verts {len(verts)}'); out += [f'{indent}  {x:.5f} {y:.5f} {z:.5f}' for x, y, z in verts]
    out.append(f'{indent}tverts {len(tverts)}'); out += [f'{indent}  {u:.5f} {v:.5f} 0' for u, v in tverts]
    out.append(f'{indent}faces {len(faces)}'); out += [f'{indent}  ' + ' '.join(str(value) for value in face) for face in faces]
    out.append('endnode')
    return out


def merged(parts):
    """[(look, verts, tverts, faces)] of `parts` [(look, verts, tverts, faces)] joined wherever their look is the same:
    one node, one draw, for each material a tile's added pieces use."""
    joined = {}
    for look, verts, tverts, faces in parts:
        into = joined.setdefault(look, ([], [], []))
        tverts = tverts or [(0.0, 0.0)]  # a face names texture vertices even where the mesh has none
        base, tbase = len(into[0]), len(into[1])
        into[0].extend(verts); into[1].extend(tverts)
        for face in faces:
            a, b, c, group = face[:4]; ta, tb, tc = (face[4:7] if len(face) >= 7 else (0, 0, 0)); material = face[7] if len(face) >= 8 else 0
            into[2].append((a + base, b + base, c + base, group, ta + tbase, tb + tbase, tc + tbase, material))
    return [(look, *lists) for look, lists in joined.items()]


def baked(nodes, move=lambda point: point):
    """[(look, verts, tverts, faces)] of a model's rendered trimesh nodes, each vertex taken to the model's space and
    then by `move`. Any other kind of rendered mesh is refused: it moves, and a baked copy would not."""
    moves, parts = placed(nodes), []
    for node in nodes:
        if not node.rendered:
            continue
        require(node.kind == 'trimesh', f'{node.name} is a {node.kind}: only trimesh nodes are baked')
        to_model = moves[node.name.lower()]
        parts.append((node.look, [move(to_model(vertex)) for vertex in node.verts], list(node.tverts), list(node.faces)))
    return parts


def faces_of(parts):
    return [tuple(verts[corner] for corner in face[:3]) for _, verts, _, faces in parts for face in faces if max(face[:3]) < len(verts)]
