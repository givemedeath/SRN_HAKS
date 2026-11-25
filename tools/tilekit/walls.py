"""A room shell drawn here: the outer walls, inner walls and doorways of a room that no tile of a source set has (an
apartment, a house). `rooms` uses it where a spec's shell says `box` in place of `group`:

 shell: {set, box: {rows, columns, like: [the source tile whose lights, doors, corners and crossers each of its tiles
   takes, row by row from the south-west], height (of the ceiling), repeat: {floor, wall, ceiling},
   look: {floor, wall, ceiling, base, crown, trim, top: textures},
   openings: [{side: n, e, s or w, at: metres along that side, width, high}],
   walls: [{from: [x, y], to: [x, y], doors: [{at: metres from `from` to the doorway's middle, width, high}],
           bars: the texture of bars that stand there in the wall's place}],
   zones: [{rect: [x0, y0, x1, y1], floor, wall, base, crown, repeat: {floor, wall: [across, up]}}]}}

in metres from the room's south-west corner. Inner walls run along x or y and stand on their line's middle. A zone's
looks take the place of the box's own on the floor it covers and on the walls that face it. Bars run from floor to
ceiling, are seen through, stop whoever walks as a wall does, and have no lintel or casing at their doorways."""
import numpy as np

from . import geometry, joins, require, terrain
from .unique import unique

TILE = 2 * geometry.HALF
OUTER = INNER = 0.2  # metres: the outer walls stand where the office's rooms have them (4.8 from a tile's middle)
TOP = 4.0  # metres: the walls' black tops, level with the source sets' own
SOLID, BLOCK = 7, 5.0  # the walk surface of a wall, and how high it stands in the walkmesh (the office's)
BASE, BASE_OUT, CROWN, CROWN_OUT, CASING, CASING_OUT = 0.14, 0.03, 0.12, 0.05, 0.1, 0.05
BAR, APART, RAIL, RAILS, POST = 0.03, 0.13, 0.05, (0.1, 1.15, 2.2), 0.08  # metres: bars, from one to the next, the rails across them and their heights, the posts at their ends
SPAN = 2.5  # metres: no drawn quad is wider
WAYS = {'e': (1, 0), 'n': (0, 1), 'w': (-1, 0), 's': (0, -1)}
BACK = {'e': 'w', 'w': 'e', 'n': 's', 's': 'n'}
GROUP = {'e': 1, 'n': 2, 'w': 4, 's': 8, 'u': 16, 'd': 32}  # a smoothing group each way, so no corner is rounded
SEEN, SHUT = ('open', 'bars'), ('wall', 'bars')  # what is drawn as room, and what nobody walks through
DOOR = {'high': 2.4, 'width': 1.4}
PATHS = {'': ('T', 0), 'n': ('N', 0), 'e': ('N', 270), 's': ('N', 180), 'w': ('N', 90), 'ns': ('L', 0), 'ew': ('L', 90), 'sw': ('H', 0), 'es': ('H', 90), 'en': ('H', 180), 'nw': ('H', 270),
         'nsw': ('I', 0), 'esw': ('I', 90), 'ens': ('I', 180), 'enw': ('I', 270), 'ensw': ('A', 0)}


def path(sides):
    """(PathNode, Orientation) of a tile open at `sides`, as the source sets' tiles say it (surveyed 2026-11-24)."""
    return PATHS[''.join(sorted(sides))]


class Plan:
    """A box room's floor cut in cells by every wall, doorway, zone and tile side."""

    def __init__(self, spec):
        box = self.box = spec['shell']['box']; self.name = spec['id']; self.rows, self.columns = box['rows'], box['columns']
        require(len(box['like']) == self.rows * self.columns, f'{self.name}: `like` names a source tile for each tile of the room')
        wide, deep = self.wide, self.deep = self.columns * TILE, self.rows * TILE; self.height = box.get('height', TOP); self.zones = box.get('zones', [])
        require(self.height <= TOP, f'{self.name}: its ceiling is over its walls')
        self.solid = [(0, 0, wide, OUTER), (0, deep - OUTER, wide, deep), (0, 0, OUTER, deep), (wide - OUTER, 0, wide, deep)]; self.gaps = []; self.bars = []
        for one in box.get('openings', ()):
            low, high = one['at'] - one['width'] / 2, one['at'] + one['width'] / 2
            rect = {'s': (low, 0, high, OUTER), 'n': (low, deep - OUTER, high, deep), 'w': (0, low, OUTER, high), 'e': (wide - OUTER, low, wide, high)}[one['side']]
            self.gaps.append((rect, one['high']))
        for wall in box.get('walls', ()):
            start, end = tuple(wall['from']), tuple(wall['to']); along = 0 if start[1] == end[1] else 1
            require(start[1 - along] == end[1 - along] and start[along] < end[along], f'{self.name}: the wall from {start} to {end} runs along neither x nor y, or backwards')
            across = start[1 - along]; rect = lambda low, high: (low, across - INNER / 2, high, across + INNER / 2) if along == 0 else (across - INNER / 2, low, across + INNER / 2, high)
            ways_in = []
            for door in wall.get('doors', ()):
                door = {**DOOR, **door}; low, high = (start[along] + door['at'] + way * door['width'] / 2 for way in (-1, 1))
                require(low - CASING >= start[along] - 1e-9 and high + CASING <= end[along] + 1e-9, f'{self.name}: a doorway at {door["at"]} leaves the wall from {start} to {end}')
                ways_in.append((low, high, door['high']))
            if wall.get('bars'):
                for low, high in zip([start[along], *sorted(high for _, high, _ in ways_in)], [*sorted(low for low, _, _ in ways_in), end[along]]):
                    self.bars.append((rect(low, high), wall['bars']))
            else:
                self.solid.append(rect(start[along], end[along])); self.gaps += [(rect(low, high), top) for low, high, top in ways_in]
        rects = self.solid + [rect for rect, _ in self.gaps + self.bars] + [tuple(zone['rect']) for zone in self.zones]
        lines = lambda axis, size, count: np.unique(np.round([0, size] + [index * TILE for index in range(count)] + [min(max(rect[side], 0), size) for rect in rects for side in (axis, axis + 2)], 4))
        self.xs, self.ys = lines(0, wide, self.columns), lines(1, deep, self.rows)
        self.cells = {(i, j): self.at((self.xs[i] + self.xs[i + 1]) / 2, (self.ys[j] + self.ys[j + 1]) / 2) for i in range(len(self.xs) - 1) for j in range(len(self.ys) - 1)}

    def at(self, x, y):
        """('gap', its lintel), ('wall', None), ('bars', their texture) or ('open', None) of a point."""
        inside = lambda rect: rect[0] < x < rect[2] and rect[1] < y < rect[3]
        lintel = next((high for rect, high in self.gaps if inside(rect)), None)
        if lintel or any(map(inside, self.solid)):
            return ('gap', lintel) if lintel else ('wall', None)
        bars = next((texture for rect, texture in self.bars if inside(rect)), None)
        return ('bars', bars) if bars else ('open', None)

    def looks(self, cell):
        """The looks at a cell: the last zone's over the box's own."""
        x, y = self.middle(cell); found = {**self.box['look'], 'repeat': {'floor': 5.0, 'wall': [4.0, TOP], 'ceiling': 5.0, **self.box.get('repeat', {})}}
        for zone in self.zones:
            if zone['rect'][0] < x < zone['rect'][2] and zone['rect'][1] < y < zone['rect'][3]:
                found = {**found, **{key: value for key, value in zone.items() if key not in ('rect', 'repeat')}, 'repeat': {**found['repeat'], **zone.get('repeat', {})}}
        return found

    def span(self, cell):
        return self.xs[cell[0]], self.ys[cell[1]], self.xs[cell[0] + 1], self.ys[cell[1] + 1]

    def middle(self, cell):
        x0, y0, x1, y1 = self.span(cell)
        return (x0 + x1) / 2, (y0 + y1) / 2

    def kind(self, cell, way=None):
        dx, dy = WAYS[way] if way else (0, 0)
        return self.cells.get((cell[0] + dx, cell[1] + dy), ('outside', None))

    def corner(self, index):
        return (index % self.columns) * TILE, (index // self.columns) * TILE

    def of_tile(self, index):
        x0, y0 = self.corner(index)
        return [cell for cell in self.cells if x0 < self.middle(cell)[0] < x0 + TILE and y0 < self.middle(cell)[1] < y0 + TILE]

    def sides(self, index):
        """The sides (n, e, s, w) a tile of the room is open at."""
        x0, y0 = self.corner(index); found = set()
        for cell in self.of_tile(index):
            a, b, c, d = self.span(cell)
            if self.kind(cell)[0] != 'wall':
                found |= {side for side, at in (('w', a == x0), ('e', c == x0 + TILE), ('s', b == y0), ('n', d == y0 + TILE)) if at and self.kind(cell, side)[0] != 'wall'}
        return found


class Drawn:
    """Quads gathered by texture, in the metres of the tile whose corner is `corner`."""

    def __init__(self, corner):
        self.corner = corner; self.by = {}

    def quad(self, texture, points, uv, way):
        verts, faces = self.by.setdefault(texture, ([], [])); at = len(verts)
        verts += [((x - self.corner[0] - geometry.HALF, y - self.corner[1] - geometry.HALF, z), one) for (x, y, z), one in zip(points, uv)]
        faces += [(at + a, at + b, at + c, GROUP[way], at + a, at + b, at + c, 0) for a, b, c in ((0, 1, 2), (0, 2, 3))]

    def wall(self, texture, way, at, low, high, bottom, top, repeat):
        """An upright face that looks `way`, on the line `at`, from `low` to `high` along it."""
        edges = np.linspace(low, high, max(1, int(np.ceil((high - low) / SPAN - 1e-9))) + 1); sign = 1 if way in 'se' else -1
        for a, b in zip(edges, edges[1:]):
            left, right = (a, b) if sign > 0 else (b, a)  # as seen from the room
            corners = [(left, bottom), (right, bottom), (right, top), (left, top)]
            self.quad(texture, [(at, along, z) if way in 'ew' else (along, at, z) for along, z in corners], [(sign * along / repeat[0], z / repeat[1]) for along, z in corners], way)

    def flat(self, texture, rect, z, up=True, repeat=1.0, span=SPAN):
        xs, ys = (np.linspace(rect[axis], rect[axis + 2], max(1, int(np.ceil((rect[axis + 2] - rect[axis]) / span - 1e-9))) + 1) for axis in range(2))
        for x0, x1 in zip(xs, xs[1:]):
            for y0, y1 in zip(ys, ys[1:]):
                ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)][::1 if up else -1]
                self.quad(texture, [(x, y, z) for x, y in ring], [(x / repeat, y / repeat) for x, y in ring], 'u' if up else 'd')

    def block(self, texture, rect, bottom, top, lid=False):
        x0, y0, x1, y1 = rect
        for way, at, low, high in (('e', x1, y0, y1), ('w', x0, y0, y1), ('n', y1, x0, x1), ('s', y0, x0, x1)):
            self.wall(texture, way, at, low, high, bottom, top, (1.0, 1.0))
        if lid:
            self.flat(texture, rect, bottom, up=False)

    def text(self, root, look):
        out = []
        for number, (texture, (verts, faces)) in enumerate(sorted(self.by.items())):
            lines = tuple(f'bitmap {texture}' if line.split()[0].lower() == 'bitmap' else line for line in look)
            out += geometry.mesh_text(f'{root}_box{number:02d}', root, lines + ('shadow 0',), [point for point, _ in verts], [uv for _, uv in verts], faces)
        return out


def merged(plan, cells, key):
    """[(rectangle, its key)] covering the cells whose key is not None: joined along x, then those alike along y."""
    rows, out, last = {}, [], {}
    for i, j in sorted(cells, key=lambda cell: (cell[1], cell[0])):
        value = key((i, j))
        if value is not None:
            runs = rows.setdefault(j, [])
            if runs and runs[-1][1] == i and runs[-1][2] == value:
                runs[-1][1] = i + 1
            else:
                runs.append([i, i + 1, value])
    for j in sorted(rows):
        now = {}
        for i0, i1, value in rows[j]:
            before = last.get((i0, i1, value))
            if before is not None and out[before][3] == j:
                out[before][3] = j + 1; now[(i0, i1, value)] = before
            else:
                out.append([i0, j, i1, j + 1, value]); now[(i0, i1, value)] = len(out) - 1
        last = now
    return [((plan.xs[i0], plan.ys[j0], plan.xs[i1], plan.ys[j1]), value) for i0, j0, i1, j1, value in out]


def barred(out, texture, rect, height):
    """Bars, the rails across them and the posts at their ends, along the middle of a rectangle."""
    along = 0 if rect[2] - rect[0] > rect[3] - rect[1] else 1; low, high, middle = rect[along], rect[along + 2], (rect[1 - along] + rect[3 - along]) / 2
    part = lambda first, last, thick: (first, middle - thick / 2, last, middle + thick / 2) if along == 0 else (middle - thick / 2, first, middle + thick / 2, last)
    for start in (low, high - POST):
        out.block(texture, part(start, start + POST, POST), 0.0, height)
    count = max(1, round((high - low - 2 * POST) / APART)); step = (high - low - 2 * POST) / count
    for number in range(1, count):
        at = low + POST + number * step; out.block(texture, part(at - BAR / 2, at + BAR / 2, BAR), 0.0, height)
    for foot in (*RAILS, height - 0.1 - RAIL):
        out.block(texture, part(low + POST, high - POST, RAIL), foot, foot + RAIL, lid=True); out.flat(texture, part(low + POST, high - POST, RAIL), foot + RAIL)


def drawn(plan, index):
    """What the tile draws."""
    x0, y0 = plan.corner(index); out = Drawn((x0, y0)); cells = plan.of_tile(index); repeat = lambda cell, what: plan.looks(cell)['repeat'][what]; kind = lambda cell: plan.kind(cell)[0]
    for rect, (texture, across) in merged(plan, cells, lambda cell: None if kind(cell) == 'wall' else (plan.looks(cell)['floor'], repeat(cell, 'floor'))):
        out.flat(texture, rect, 0.0, repeat=across)
    for rect, (texture, across) in merged(plan, cells, lambda cell: (plan.looks(cell)['ceiling'], repeat(cell, 'ceiling')) if kind(cell) in SEEN else None):
        out.flat(texture, rect, plan.height, up=False, repeat=across)
    for rect, texture in merged(plan, cells, lambda cell: None if kind(cell) in SEEN else plan.box['look']['top']):
        out.flat(texture, rect, TOP, span=TILE)
    runs = {}  # the faces that look the same way on one line and are drawn alike
    for cell in cells:
        if kind(cell) in SEEN:
            a, b, c, d = plan.span(cell); looks = plan.looks(cell)
            for way in WAYS:
                there, lintel = plan.kind(cell, way)
                if there in ('wall', 'gap'):
                    line = {'e': c, 'w': a, 'n': d, 's': b}[way]
                    runs.setdefault((BACK[way], line, lintel or 0.0, looks['wall'], tuple(looks['repeat']['wall']), looks.get('base'), looks.get('crown')), []).append((b, d) if way in 'ew' else (a, c))
    for (way, line, bottom, texture, across, base, crown), spans in sorted(runs.items(), key=str):
        joined = []
        for low, high in sorted(spans):
            if joined and abs(joined[-1][1] - low) < 1e-6:
                joined[-1][1] = high
            else:
                joined.append([low, high])
        for low, high in joined:
            out.wall(texture, way, line, low, high, bottom, TOP, across); sign = sum(WAYS[way])
            spot = lambda out_, along: plan.at(line + out_, along) if way in 'ew' else plan.at(along, line + out_)
            round_ = [all(spot(side * sign * 1e-3, end + step * 1e-3)[0] == 'open' for side in (1, -1)) for end, step in ((low, -1), (high, 1))]  # the wall ends and another goes back from it
            for look, proud, foot, head in ((base if not bottom else None, BASE_OUT, 0.0, BASE), (crown, CROWN_OUT, plan.height - CROWN, plan.height)):
                if look:
                    origin = y0 if way in 'ew' else x0; first, second = max(low - proud * round_[0], origin), min(high + proud * round_[1], origin + TILE); sides = sorted((line, line + sign * proud))
                    out.wall(look, way, line + sign * proud, first, second, foot, head, (1.0, 1.0))
                    out.flat(look, (sides[0], first, sides[1], second) if way in 'ew' else (first, sides[0], second, sides[1]), head if foot == 0.0 else foot, up=foot == 0.0)
    for rect, texture in merged(plan, cells, lambda cell: plan.kind(cell)[1] if kind(cell) == 'bars' else None):
        barred(out, texture, rect, plan.height)
    for (a, b, c, d), lintel in plan.gaps:  # a casing round each doorway, proud of its wall on both sides
        if a - CASING < x0 + TILE and c + CASING > x0 and b - CASING < y0 + TILE and d + CASING > y0:  # one on a tile's side is drawn by both tiles, each its own part
            held = lambda *rect: (max(rect[0], x0), max(rect[1], y0), min(rect[2], x0 + TILE), min(rect[3], y0 + TILE)); over, by = CASING_OUT, CASING
            if c - a > d - b:
                posts = held(a - by, b - over, a, d + over), held(c, b - over, c + by, d + over); head = held(a - by, b - over, c + by, d + over)
            else:
                posts = held(a - over, b - by, c + over, b), held(a - over, d, c + over, d + by); head = held(a - over, b - by, c + over, d + by)
            for post in (post for post in posts if post[0] < post[2] - 1e-6 and post[1] < post[3] - 1e-6):
                out.block(plan.box['look']['trim'], post, 0.0, lintel)
            if head[0] < head[2] - 1e-6 and head[1] < head[3] - 1e-6:
                out.block(plan.box['look']['trim'], head, lintel, lintel + CASING, lid=True)
    return out


def walked(plan, index, surface):
    """(vertices, faces [a, b, c, surface]) of the tile's walkmesh, in its own metres."""
    x0, y0 = plan.corner(index); cells = plan.of_tile(index); triangles = []

    def quad(points, kind):
        points = [(x - x0 - geometry.HALF, y - y0 - geometry.HALF, z) for x, y, z in points]
        triangles.extend(np.array([[*points[corner], kind, 0.0] for corner in three], float) for three in ((0, 1, 2), (0, 2, 3)))

    def key(cell):  # cells on a seam keep their corners: the next tile's has the same
        a, b, c, d = plan.span(cell); seam = lambda low, high, origin, size: (low == origin and origin > 0) or (high == origin + TILE and high < size)
        return plan.kind(cell)[0] in SHUT, cell[1] if seam(a, c, x0, plan.wide) else None, cell[0] if seam(b, d, y0, plan.deep) else None
    for (a, b, c, d), (solid, *_) in merged(plan, cells, key):
        quad([(x, y, BLOCK if solid else 0.0) for x, y in ((a, b), (c, b), (c, d), (a, d))], SOLID if solid else surface)
    for cell in cells:
        a, b, c, d = plan.span(cell)
        for way, (p, q) in (('e', ((c, b), (c, d))), ('w', ((a, d), (a, b))), ('n', ((c, d), (a, d))), ('s', ((a, b), (c, b)))):
            if plan.kind(cell)[0] not in SHUT and plan.kind(cell, way)[0] in SHUT:
                quad([(*q, 0.0), (*p, 0.0), (*p, BLOCK), (*q, BLOCK)], SOLID)
    return joins.conformed(triangles)


def _unanimated(lines, name):
    """The lines without the meshes' nodes of the animations: the source's animations move none of them."""
    out, held, moving = [], None, False
    for line in lines:
        words = line.split(); first = words[0].lower() if words else ''; moving = moving or first == 'newanim'
        if moving and first == 'node' and words[1].lower() in geometry.MESHES | {'aabb'}:
            held = []
        if held is None:
            out.append(line); continue
        held.append(line)
        if first == 'endnode':
            require(len(held) == 3, f'{name}: the tile it is like moves {" ".join(words[2:]) or held[0].strip()}'); held = None
    return out


def shell(text, name, spec, index):
    """(a box room's tile, its walkmesh file, [the parts of the source tile left out]): the source tile `text` with all
    it draws and walks on replaced by the room's own; its lights and dummies are kept."""
    from tools.envkit import tile
    plan = Plan(spec); text = unique(text.replace('\r\n', '\n'))[0]; lines, root, nodes = geometry.parse(text)
    floors = [node for node in nodes if node.rendered and node.verts and node.name.lower().startswith('floor')]; require(floors, f'{name}: the tile it is like draws no floor, whose look the walls take')
    look = tuple(line for line in floors[0].look if line.split()[0].lower() not in ('materialname', 'texture0'))
    walk = [face[7] for node in nodes if node.kind == 'aabb' for face in node.faces if len(face) > 7 and face[7] in geometry.WALKABLE]; require(walk, f'{name}: the tile it is like is not walked')
    gone = [node for node in nodes if node.kind in geometry.MESHES or node.kind == 'aabb']
    for node in sorted(gone, key=lambda node: -node.start):
        del lines[node.start:node.end + 1]
    lines = _unanimated(lines, name); mesh = walked(plan, index, max(set(walk), key=walk.count)); end = next(number for number, line in enumerate(lines) if line.strip().lower().startswith('endmodelgeom'))
    lines[end:end] = drawn(plan, index).text(root, look) + tile._walk_node(root, root, *mesh)
    return terrain.renamed('\n'.join(lines), {root: name}), tile.walk_text(name, mesh), sorted(node.name for node in gone if node.kind != 'aabb')
