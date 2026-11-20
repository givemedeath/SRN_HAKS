"""Placements of kit pieces proposed from a tile's own shape: its windows and its walkable roof.

A proposal is a starting point written into a placement spec for review: a person moves, removes or adds pieces by
editing the spec, and `detail` checks every placement the same whatever made it.

- **Windows** are the rendered faces whose texture names a window, upright, above `geometry.HEAD`. They are grouped
  into windows by facing and position, and a facade is the windows facing one way. A window the tile already fits
  out (its own air conditioner, a sign or lamp off the wall) gets nothing.
- **A fire escape** climbs the first column of windows of one facade: a platform under each window from the second
  storey up, each with its stair to the next.
- **Air conditioners** hang under some of the other windows, **boards** cover some and **bars** guard some of the
  lowest, chosen by a pattern from the tile's seed. A **downpipe** runs down one end of each facade, the other end where a street-level
  door or window is under the first, none where both have one.
- **Roof clutter** stands on the highest walkable surface, a margin in from the cell's side, clear of what the roof
  already has, apart from each other. It is cover (`blocks`).
- **Effects**, at most four a tile (the budget): on about one tile in four a broken **junction box** at street level
  between two windows, clear of the tile's own lamps and signs, with **sparks** (electric arcs) where its cable leaves
  it; a **drip** under the lowest fire escape platform and one under the lowest air conditioner; **smoke** from one
  roof vent on about half the tiles that have one."""
import math
import zlib

from . import geometry

WINDOW = ('win', 'window')
EDGE = 1.2  # metres from the cell's side roof clutter keeps
APART = 2.4  # metres between roof pieces
BOX_Z = 3.3  # the junction box's foot: its cable clear of a player's head on a raised sidewalk, below the first floor's windows
ARC = (-0.06, 0.24, 0.0)  # in the box's own coordinates: just out from its broken bottom, where the cable leaves it
ESCAPE_DRIP = (1.0, 1.0, -0.07)  # under a fire escape platform's outer corner
AC_DRIP = (0.1, 0.55, -0.01)  # under an air conditioner's front
ROOF = (('hvac', 1.0, None), ('tank', 1.0, None), ('vent', 0.5, None), ('dish', 0.6, None), ('antenna', 0.35, {'size': [0.6, 0.6], 'height': 0.5}), ('vent', 0.5, None))


def _facing(triangle):
    a, b, c = triangle; u = [b[axis] - a[axis] for axis in range(3)]; v = [c[axis] - a[axis] for axis in range(3)]
    nx, ny, nz = u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]; length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return None if length < 1e-9 or abs(nz) / length > 0.2 else (round(nx / math.hypot(nx, ny)), round(ny / math.hypot(nx, ny)))


def windows(nodes):
    """{(nx, ny): [(along, bottom, top, plane)]} of the upright window faces above head height, one per window."""
    found = {}
    for node in nodes:
        if not node.rendered or not node.material or not node.material.startswith(WINDOW) and 'window' not in node.material:
            continue
        for triangle in geometry.triangles(nodes, lambda other, node=node: other is node):
            facing = _facing(triangle)
            if facing is None or abs(facing[0]) + abs(facing[1]) != 1 or min(point[2] for point in triangle) < geometry.HEAD:
                continue
            along = [point[1] if facing[0] else point[0] for point in triangle]; plane = sum(point[0] * facing[0] + point[1] * facing[1] for point in triangle) / 3
            found.setdefault(facing, []).append((min(along), max(along), min(point[2] for point in triangle), max(point[2] for point in triangle), plane))
    merged = {}
    for facing, pieces in found.items():  # a window's two triangles, or more, meet: merge what overlaps
        boxes = []
        for low, high, bottom, top, plane in sorted(pieces):
            for box in boxes:
                if low < box[1] - 0.05 and high > box[0] + 0.05 and bottom < box[3] - 0.05 and top > box[2] + 0.05:
                    box[0], box[1], box[2], box[3] = min(box[0], low), max(box[1], high), min(box[2], bottom), max(box[3], top); break
            else:
                boxes.append([low, high, bottom, top, plane])
        merged[facing] = sorted(((box[0] + box[1]) / 2, box[2], box[3], box[4]) for box in boxes)
    return merged


def _fitted(nodes, facing, pane, reach=1.2):
    """Whether the tile already has something off its wall at a window (its own air conditioner, a sign, a lamp):
    nothing is added there."""
    along, bottom, top, _ = pane; moves = geometry.placed(nodes)
    for node in nodes:
        if not node.rendered:
            continue
        for x, y, z in map(moves[id(node)], node.verts):
            if max(abs(x), abs(y)) - geometry.HALF > 0.2 and abs((y if facing[0] else x) - along) <= reach and bottom - 0.8 <= z <= top + 0.3:
                return True
    return False


def _turn(facing):
    """A wall piece's turn (degrees) that points its +y along `facing`."""
    return round(math.degrees(math.atan2(-facing[0], facing[1])), 1) % 360


def _on_wall(facing, along, plane, z):
    return [round(facing[0] * plane + (0 if facing[0] else along), 3), round(facing[1] * plane + (along if facing[0] else 0), 3), round(z, 3)]


def _openings(nodes):
    """[(low x, high x, low y, high y)] of the tile's street-level openings, from their upright rendered triangles that
    start below `geometry.OVER`: a door (its frame or its black opening) whole, as one box, since a door is often set
    back into the building and its frame is thin jambs; a window face by face, as one node may hold many windows."""
    found = []
    for node in nodes:
        name = (node.material or '').lower(); door = name.startswith('door') or 'black' in name
        if not node.rendered or not (door or name.startswith(WINDOW) or 'window' in name):
            continue
        low = [triangle for triangle in geometry.triangles(nodes, lambda other, node=node: other is node)
               if _facing(triangle) is not None and min(point[2] for point in triangle) < geometry.OVER]
        for group in ([low] if door and low else [[triangle] for triangle in low]):
            points = [point for triangle in group for point in triangle]
            found.append((min(p[0] for p in points), max(p[0] for p in points), min(p[1] for p in points), max(p[1] for p in points), door))
    return found


def _over_opening(openings, facing, plane, along, clear=0.3, depth=0.6, recess=2.5):
    """Whether a downpipe at `along` on the facade (`facing`, `plane`) would run down into a door or a shop window: one
    within `depth` of the wall, or a door within `recess` (its black opening may stand well back from its frame)."""
    for low_x, high_x, low_y, high_y, *door in openings:
        (across_low, across_high), (side_low, side_high) = ((low_x, high_x), (low_y, high_y)) if facing[0] else ((low_y, high_y), (low_x, high_x))
        out = plane * (facing[0] or facing[1])  # the facade's coordinate across it
        gap = max(across_low - out, out - across_high, 0.0)
        if gap <= (recess if door and door[0] else depth) and side_low - clear <= along <= side_high + clear:
            return True
    return False


def open_sides(corners, building):
    """The facings {(nx, ny)} of a tile's sides on a street: both corners of the side are not of a `building` terrain.
    Corners are top left, top right, bottom left, bottom right, as a set file gives them (+y is the top)."""
    sides = {(-1, 0): (0, 2), (1, 0): (1, 3), (0, 1): (0, 1), (0, -1): (2, 3)}
    return {facing for facing, (one, other) in sides.items() if not building(corners[one]) and not building(corners[other])}


def propose(text, seed, *, look='brick', open=None):
    """[{piece, at, turn, blocks?, cover?}] for a tile model's text. `open`: the facings of its sides on a street
    (`open_sides`); a facade on the cell's side facing any other way meets the next building, and gets nothing."""
    _, _, nodes = geometry.parse(text); rng = zlib.crc32(str(seed).encode()); found = []
    facades = {facing: [pane for pane in panes if not _fitted(nodes, facing, pane)] for facing, panes in windows(nodes).items()}
    facades = {facing: panes for facing, panes in facades.items() if panes
               and (open is None or facing in open or abs(panes[0][3]) < geometry.HALF - 0.3)}
    walls, openings = [], _openings(nodes)
    for number, (facing, panes) in enumerate(sorted(facades.items())):
        turn = _turn(facing); plane = panes[0][3]; columns = sorted({round(along, 1) for along, *_ in panes}); walls.append((facing, plane, columns, turn))
        climbs = [column for column in columns if sum(round(along, 1) == column for along, *_ in panes) >= 2]  # two clear storeys at least
        escape = climbs[0] if number == 0 and climbs else None
        rows = sorted({round(bottom, 1) for _, bottom, *_ in panes})
        for along, bottom, top, _ in panes:
            column, row = columns.index(round(along, 1)), rows.index(round(bottom, 1)); pick = (rng >> (column * 3 + row)) % 7
            if escape is not None and round(along, 1) == escape:  # the highest platform has no stair up into the cornice
                top = bottom == max(low for at, low, *_ in panes if round(at, 1) == escape)
                found.append({'piece': 'fire_escape_top' if top else 'fire_escape', 'at': _on_wall(facing, along, plane, bottom - 0.12), 'turn': turn})
            elif pick in (0, 3) and bottom - 0.6 >= geometry.OVER:
                found.append({'piece': 'ac_unit', 'at': _on_wall(facing, along + 0.4, plane, bottom - 0.6), 'turn': turn})
            elif pick == 5 or (look == 'timber' and pick == 1):
                found.append({'piece': 'boards', 'at': _on_wall(facing, along, plane, bottom + 0.45), 'turn': turn})
            elif row == 0 and pick in (2, 6):
                found.append({'piece': 'bars', 'at': _on_wall(facing, along, plane, bottom + 0.45), 'turn': turn})
        ends = [end for end in (min(along for along, *_ in panes) - 1.0, max(along for along, *_ in panes) + 1.0)
                if abs(end) <= geometry.HALF - 0.3 and not _over_opening(openings, facing, plane, end)]
        if ends:
            end = ends[0]; roof = max(top for _, _, top, _ in panes)
            for z in [geometry.OVER + 3.0 * index for index in range(int((roof - geometry.OVER) // 3.0) + 1)]:
                found.append({'piece': 'downpipe', 'at': _on_wall(facing, end, plane, z), 'turn': turn})
    roof = _roof(nodes, rng); found += roof
    return found + _effects(nodes, found, walls, roof, rng)


def _fixtures(nodes):
    """The points of what a tile already has off its walls (as `detail` guards them)."""
    moves = geometry.placed(nodes)
    return [point for node in nodes if node.rendered for point in map(moves[id(node)], node.verts)
            if max(abs(point[0]), abs(point[1])) - geometry.HALF > 0.2]


def _effects(nodes, found, walls, roof, rng):
    from .detail import turned
    fx = []
    if walls and (rng >> 20) % 4 == 0:  # about one tile in four has a broken junction box
        facing, plane, columns, turn = walls[0]; fixtures = _fixtures(nodes)
        middles = [(one + other) / 2 for one, other in zip(columns, columns[1:])] or [columns[0] + 1.6]
        for along in [middle + shift for middle in middles for shift in (0.0, 1.0, -1.0)]:
            if abs(along) > geometry.HALF - 0.6:
                continue
            at = _on_wall(facing, along, plane, BOX_Z); move = turned(at, turn, 1.0)
            ends = [move(point) for point in ((-0.25, 0.0, -0.45), (0.25, 0.35, 1.4))]  # the box, its cable and conduit
            low = [min(end[axis] for end in ends) for axis in range(3)]; high = [max(end[axis] for end in ends) for axis in range(3)]
            if not any(all(low[axis] - 0.05 <= point[axis] <= high[axis] + 0.05 for axis in range(3)) for point in fixtures):
                fx += [{'piece': 'junction_box', 'at': at, 'turn': turn}, {'piece': 'sparks', 'at': [round(value, 3) for value in move(ARC)]}]
                break
    for pieces, offset in (([one for one in found if one['piece'].startswith('fire_escape')], ESCAPE_DRIP), ([one for one in found if one['piece'] == 'ac_unit'], AC_DRIP)):
        if pieces:
            lowest = min(pieces, key=lambda one: one['at'][2]); point = [round(value, 3) for value in turned(lowest['at'], lowest['turn'], 1.0)(offset)]
            fx.append({'piece': 'drip', 'at': point, 'fall': point[2]})  # Slums streets are at 0 m
    vents = [one for one in roof if one['piece'] == 'vent']
    if vents and (rng >> 23) % 2 == 0:
        x, y, z = vents[0]['at']; fx.append({'piece': 'smoke', 'at': [x, y, round(z + 0.75, 3)]})
    return fx


def _roof(nodes, rng):
    walk = geometry.walkable(nodes); heights = [height for both in walk.values() for height in both if height > geometry.HEAD]
    if not heights:
        return []
    roof = max(heights)
    taken = {geometry.cell(point) for triangle in geometry.triangles(nodes) for point in geometry.samples(triangle) if roof + 0.1 < point[2] < roof + 4.0}
    placed, found = [], []
    spots = [(x / 2, y / 2) for x in range(-8, 9) for y in range(-8, 9)]
    spots = spots[rng % len(spots):] + spots[:rng % len(spots)]
    for index, (piece, reach, cover) in enumerate(ROOF[: 3 + rng % 3]):
        for x, y in spots:
            if abs(x) > geometry.HALF - EDGE or abs(y) > geometry.HALF - EDGE or any(math.hypot(x - px, y - py) < APART for px, py in placed):
                continue
            cells = {geometry.cell((x + dx, y + dy)) for dx in (-reach, 0, reach) for dy in (-reach, 0, reach)}
            if all(any(abs(height - roof) < 0.05 for height in walk.get(one, ())) for one in cells) and not cells & geometry.grown(taken):
                placed.append((x, y)); entry = {'piece': piece, 'at': [x, y, round(roof, 3)], 'turn': (rng >> index) % 4 * 90, 'blocks': True}
                if cover:
                    entry['cover'] = cover
                found.append(entry); break
    return found
