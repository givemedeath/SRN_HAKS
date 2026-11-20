"""Footprints cut out of a tile's walkable roofs, so roof clutter is cover: nothing walks through it or sees past it.

A blocking kit piece (`detail`, `"blocks": true`) stands on a walkable surface more than `geometry.HEAD` metres over
the tile's root: a roof, never the street. Its footprint, the convex hull of the piece seen from above, is cut out of
the walkable faces of that roof: each face it overlaps is split along the hull's sides, the part inside becomes
`NONWALK` (surfacemat.2da row 7, Nonwalk: no walking, and LineOfSight 1, so it blocks sight), and the rest keeps its
material. A vertex a split puts on the side of a face next to it splits that face too, so the walkmesh has no
T-junction. The box tree is built again as envkit builds its own (`tools.envkit.tile.tree`), and the model's `aabb`
node and its `.wok` are written the same.

Only the cut tiles' walkmeshes change, only on their roofs, and only with a record: `WALK_CUTS` in the overlay names
each tile's walkmesh before and after, and `apply` replaces a pack's walkmesh only as that record says, then records
the new hashes in the tileset's walkmesh baseline."""
import hashlib
import json
from pathlib import Path

from . import geometry, inventory, require

NONWALK = 7
WALK_CUTS = 'walk-cuts.json'  # {tileset, models: {model: {aabbFrom, aabbTo, wokFrom, wokTo, footprints}}}
NEAR = 1e-4
STOREY = 1.0  # metres: a face this close to a piece's base, over its footprint, is the roof it stands on


def hull(points):
    """The convex hull of (x, y) points, counter-clockwise, without repeated or collinear corners."""
    points = sorted(set((round(x, 4), round(y, 4)) for x, y in points))
    if len(points) < 3:
        return points
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _side(a, b, point):
    """Positive left of a→b, negative right."""
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def _split(polygon, a, b):
    """(left part, right part) of a convex polygon of 3-D points cut by the vertical plane through a→b."""
    left, right = [], []
    for index, point in enumerate(polygon):
        after = polygon[(index + 1) % len(polygon)]; here, there = _side(a, b, point), _side(a, b, after)
        if abs(here) <= NEAR:  # on the line: a corner of both parts
            left.append(point); right.append(point)
        else:
            (left if here > 0 else right).append(point)
        if (here > NEAR and there < -NEAR) or (here < -NEAR and there > NEAR):
            share = here / (here - there); crossing = tuple(point[axis] + (after[axis] - point[axis]) * share for axis in range(3))
            left.append(crossing); right.append(crossing)
    return left, right


def _area(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2


def _fan(polygon):
    return [(polygon[0], polygon[index], polygon[index + 1]) for index in range(1, len(polygon) - 1)
            if _area(polygon[0], polygon[index], polygon[index + 1]) > 1e-7]


def _overlaps(triangle, footprint):
    """Whether a triangle and a convex footprint overlap, seen from above (by more than a touch)."""
    inside = [list(triangle)]
    for index, a in enumerate(footprint):
        b = footprint[(index + 1) % len(footprint)]
        inside = [part for piece in inside for part in [_split(piece, a, b)[0]] if len(part) >= 3]
    return any(sum(_area(*one) for one in _fan(piece)) > 1e-5 for piece in inside)


def _clip(triangle, footprint):
    """The part of a triangle (3-D points) inside a convex counter-clockwise footprint, as a convex polygon."""
    inside = list(triangle)
    for index, a in enumerate(footprint):
        inside = _split(inside, a, footprint[(index + 1) % len(footprint)])[0]
        if len(inside) < 3:
            return []
    return _distinct(inside)


def _distinct(ring):
    """A ring without a point repeated next to itself."""
    out = []
    for point in ring:
        if not out or math_close(out[-1], point) is False:
            out.append(point)
    while len(out) > 1 and math_close(out[0], out[-1]):
        out.pop()
    return out


def _on_edge(point, a, b):
    return abs(_side(a, b, point)) <= NEAR * 10 and min(a[0], b[0]) - NEAR <= point[0] <= max(a[0], b[0]) + NEAR and min(a[1], b[1]) - NEAR <= point[1] <= max(a[1], b[1]) + NEAR


def _rest(triangle, inside):
    """The rings of a triangle (counter-clockwise from above) outside `inside`, a convex part of it."""
    if len(inside) < 3:
        return [list(triangle)]
    triangle = list(triangle) if _area_signed(triangle) > 0 else list(reversed(triangle))
    inside = inside if _area_signed(inside) > 0 else list(reversed(inside))
    rim = []  # the triangle's sides with the points of `inside` that lie on them, in order
    for index, a in enumerate(triangle):
        b = triangle[(index + 1) % 3]; rim.append(a)
        along = sorted((point for point in inside if _on_edge(point, a, b) and not math_close(point, a) and not math_close(point, b)),
                       key=lambda point: (point[0] - a[0]) ** 2 + (point[1] - a[1]) ** 2)
        rim += along
    rim = _distinct(rim)
    touching = [index for index, point in enumerate(inside) if any(math_close(point, other) for other in rim)]
    if not touching:  # a hole: bridged from the rim to a corner of it that a rim corner sees
        corner = rim[0]
        edge = next(index for index in range(len(inside)) if _side(inside[index], inside[(index + 1) % len(inside)], corner) < -NEAR)
        hole = inside[edge:] + inside[:edge]  # starting at a corner the rim corner sees
        return [rim + [corner] + [hole[0]] + list(reversed(hole[1:])) + [hole[0]]]
    rings = []
    count = len(inside)
    for start in touching:  # each run of `inside`'s sides through the triangle's middle cuts one ring off
        nxt = (start + 1) % count
        if nxt in touching and _on_rim(inside[start], inside[nxt], rim):
            continue  # this side of `inside` lies along the triangle's own side
        chain, at = [inside[start]], nxt
        while at not in touching:
            chain.append(inside[at]); at = (at + 1) % count
        chain.append(inside[at])
        begin = next(index for index, point in enumerate(rim) if math_close(point, inside[start]))
        arc, at = [], begin
        while True:  # along the rim, counter-clockwise, from where the run leaves it to where it comes back
            arc.append(rim[at]); at = (at + 1) % len(rim)
            if math_close(rim[at], chain[-1]):
                break
        ring = _distinct(arc + list(reversed(chain)))
        if len(ring) >= 3 and _area_signed(ring) > 1e-7:
            rings.append(ring)
    return rings


def _on_rim(a, b, rim):
    return any(_on_edge(a, rim[index], rim[(index + 1) % len(rim)]) and _on_edge(b, rim[index], rim[(index + 1) % len(rim)]) for index in range(len(rim)))


def _area_signed(ring):
    return sum(ring[index][0] * ring[(index + 1) % len(ring)][1] - ring[(index + 1) % len(ring)][0] * ring[index][1] for index in range(len(ring))) / 2


def _ears(ring):
    """Triangles of a counter-clockwise ring, simple or touching itself at a bridge, by cutting off ears."""
    ring = list(ring); found = []
    while len(ring) > 3:
        for index in range(len(ring)):
            a, b, c = ring[index - 1], ring[index], ring[(index + 1) % len(ring)]
            if _side(a, b, c) <= NEAR * NEAR:  # not a convex corner
                continue
            if any(_inside(point, a, b, c) for point in ring if not any(math_close(point, corner) for corner in (a, b, c))):
                continue
            found.append((a, b, c)); del ring[index]; break
        else:
            straight = next((index for index in range(len(ring)) if abs(_side(ring[index - 1], ring[index], ring[(index + 1) % len(ring)])) <= NEAR * NEAR
                             and math_close(ring[index - 1], ring[(index + 1) % len(ring)])), None)
            require(straight is not None, 'A cut left a piece of roof that could not be triangulated: move the piece a little')
            del ring[straight]  # a spike back along itself: no area
    if len(ring) == 3 and _side(*ring) > NEAR * NEAR:
        found.append(tuple(ring))
    return [triangle for triangle in found if _area(*triangle) > 1e-7]


def _inside(point, a, b, c):
    return _side(a, b, point) > NEAR * NEAR and _side(b, c, point) > NEAR * NEAR and _side(c, a, point) > NEAR * NEAR


class Walkmesh:
    """A walkmesh's vertices and faces [(a, b, c, smoothing, ta, tb, tc, material)], with vertices shared by position."""

    def __init__(self, verts, faces):
        self.verts = [tuple(vertex) for vertex in verts]; self.faces = [tuple(face) for face in faces]
        self.index = {self._key(vertex): number for number, vertex in enumerate(self.verts)}; self.made = set()

    @staticmethod
    def _key(point):
        return tuple(round(value / NEAR) for value in point)

    def vertex(self, point):
        key = self._key(point)
        if key not in self.index:
            self.index[key] = len(self.verts); self.verts.append(tuple(point)); self.made.add(self.index[key])
        return self.index[key]

    def corners(self, face):
        return tuple(self.verts[corner] for corner in face[:3])

    def cut(self, footprint, base):
        """Cut a convex footprint [(x, y)] out of the walkable faces near height `base`: inside is NONWALK. Each face
        it overlaps keeps the rest of itself, triangulated again with no vertex but its own corners and the points the
        footprint's sides cross it at. Returns the number of faces it covered."""
        kept, covered = [], 0
        for face in self.faces:
            triangle = self.corners(face)
            if face[7] not in geometry.WALKABLE or abs(sum(point[2] for point in triangle) / 3 - base) > STOREY or not _overlaps(triangle, footprint):
                kept.append(face); continue
            covered += 1; inside = _clip(triangle, footprint)
            kept += [self._face(part, face, NONWALK) for part in _fan(inside)]
            for ring in _rest(triangle, inside):
                kept += [self._face(part, face, face[7]) for part in _ears(ring)]
        self.faces = kept
        return covered

    def _face(self, triangle, like, material):
        a, b, c = (self.vertex(point) for point in triangle)
        return (a, b, c, like[3], 0, 0, 0, material)

    def mend(self):
        """Split every face with another face's vertex on one of its sides, until none has: no T-junctions."""
        changed = True
        while changed:
            changed = False
            for number, face in enumerate(self.faces):
                for side in range(3):
                    one, other = face[side], face[(side + 1) % 3]; p, q = self.verts[one], self.verts[other]
                    between = next((index for index in self.made if index not in face[:3] and _on(p, q, self.verts[index])), None)
                    if between is not None:
                        third = face[(side + 2) % 3]; rest = face[3:]
                        self.faces[number:number + 1] = [(one, between, third, *rest), (between, other, third, *rest)]
                        changed = True; break
                if changed:
                    break


def _on(p, q, point):
    """Whether `point` lies on segment p-q, strictly between its ends."""
    span = [q[axis] - p[axis] for axis in range(3)]; length = sum(value * value for value in span)
    if length < NEAR * NEAR:
        return False
    share = sum((point[axis] - p[axis]) * span[axis] for axis in range(3)) / length
    if not NEAR < share < 1 - NEAR:
        return False
    return sum((p[axis] + span[axis] * share - point[axis]) ** 2 for axis in range(3)) < (NEAR * 10) ** 2


def _walk_node(text):
    """(lines, aabb node) of a model's or walkmesh file's text; the walkmesh must sit at its parent's origin."""
    lines, _, nodes = geometry.parse(text if 'beginmodelgeom' in text.lower() else 'beginmodelgeom wok\n' + text)
    found = [node for node in nodes if node.kind == 'aabb']; require(len(found) == 1, f'{len(found)} walkmesh nodes, not one')
    node = found[0]
    require(all(abs(value) < 1e-6 for value in node.position) and (node.orientation[3] == 0 or node.orientation[:3] == (0.0, 0.0, 0.0)), 'The walkmesh node is moved or turned')
    return node


def rewritten(text, walk):
    """`text` (a model or a .wok) with its aabb node's vertices, faces and box tree made `walk`'s."""
    import numpy as np
    from tools.envkit import tile
    head = 'beginmodelgeom wok\n' if 'beginmodelgeom' not in text.lower() else ''
    ending = '\r\n' if '\r\n' in text else '\n'
    lines = (head + text).replace('\r\n', '\n').split('\n'); node = _walk_node(text)
    start = next(index for index in range(node.start, node.end) if lines[index].split()[:1] == ['verts'])
    indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
    boxes = tile.tree(np.array(walk.verts, dtype=float), np.array([face[:3] for face in walk.faces]))
    form = lambda box: ' '.join(f'{value:.5f}' for value in box[:6]) + f' {box[6]}'
    body = [f'{indent}verts {len(walk.verts)}'] + [f'{indent}  {x:.5f} {y:.5f} {z:.5f}' for x, y, z in walk.verts]
    body += [f'{indent}faces {len(walk.faces)}'] + [f'{indent}  ' + ' '.join(str(value) for value in face) for face in walk.faces]
    body += [f'{indent}aabb ' + form(boxes[0])] + [f'{indent}  ' + form(box) for box in boxes[1:]]
    new = lines[:start] + body + lines[node.end:]
    return ending.join(new[1:] if head else new)


def cut_walkmesh(model_text, wok_text, footprints, half=geometry.HALF):
    """(model text, wok text) with each footprint [(polygon, base)] cut out of its roof. The model's walkmesh and the
    .wok must be the same mesh to begin with."""
    model, wok = _walk_node(model_text), _walk_node(wok_text)
    require(len(model.verts) == len(wok.verts) and len(model.faces) == len(wok.faces) and all(math_close(a, b) for a, b in zip(model.verts, wok.verts)),
            'The model\'s walkmesh and its .wok differ: cut neither')
    walk = Walkmesh(model.verts, model.faces)
    for polygon, base in footprints:
        require(walk.cut(polygon, base), f'A blocking piece at {polygon[0]} stands on no walkable roof face at {base:.2f} m')
    walk.mend()
    edge = [walk.verts[index] for index in walk.made if abs(walk.verts[index][0]) >= half - 1e-3 or abs(walk.verts[index][1]) >= half - 1e-3]
    require(not edge, f'A cut reaches the side of the cell at {edge[:1]}: the neighbour\'s walkmesh would not meet it; move the piece inward')
    return rewritten(model_text, walk), rewritten(wok_text, walk)


def math_close(a, b):
    return all(abs(x - y) < 1e-4 for x, y in zip(a, b))


def noted(folder, tileset, model, before, after, wok_before, wok_after, footprints):
    """Record a tile's cut in the overlay: apply replaces the pack's walkmesh only as this says."""
    path = Path(folder) / WALK_CUTS; held = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {'tileset': tileset, 'models': {}}
    require(held.get('tileset') == tileset, f'{WALK_CUTS} in the overlay is of {held.get("tileset")}, not {tileset}')
    sha = lambda text: hashlib.sha256(text.encode('cp1252')).hexdigest()
    held['models'][model] = {'aabbFrom': inventory.walk_hash(before), 'aabbTo': inventory.walk_hash(after), 'wokFrom': sha(wok_before), 'wokTo': sha(wok_after),
                             'footprints': [{'base': round(base, 3), 'polygon': [list(point) for point in polygon]} for polygon, base in footprints]}
    path.write_text(json.dumps(held, indent=1) + '\n', encoding='utf-8')


def forget(folder, model):
    """Drop a tile's cut from the overlay's record: run again, it has none."""
    path = Path(folder) / WALK_CUTS
    if path.is_file():
        held = json.loads(path.read_text(encoding='utf-8-sig')); held['models'].pop(model, None)
        path.write_text(json.dumps(held, indent=1) + '\n', encoding='utf-8')
