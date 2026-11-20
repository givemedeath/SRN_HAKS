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
AC_DRIP = (0.0, 0.4, -0.05)  # under a window air conditioner's front (scaled with it)
AC_WIDTH, AC_SHARE, AC_LARGEST = 0.66, 0.62, 2.0  # the kit's unit is this wide, and fills about this share of its window's width
AC_TALL = 0.47  # the kit's unit with its sash bar is this tall: it fits inside its window's height


def _ac_size(width, height=None):
    """A window air conditioner's scale for a window `width` wide: about AC_SHARE of it (at 45% they looked small,
    2026-11-20), never smaller than real size nor over AC_LARGEST times it, nor taller than the window `height` (None:
    the unit does not fit at real size)."""
    size = round(min(AC_LARGEST, max(1.0, width * AC_SHARE / AC_WIDTH)), 3)
    if height is None:
        return size
    return None if height < AC_TALL else round(min(size, height / AC_TALL), 3)
RUIN = (('barrel', 0.4, None),) * 3  # a ruin's upper floors: burn barrels (two at most), each smoking
ESCAPES = ('brick', 'timber', 'shopfront')  # looks whose storeys suit the kit's fire escape (`kit.STOREY`)
AIR = {'residential': (0, 3, 5), 'derelict': (), 'industrial': (), 'civic': (), 'secure': ()}  # the window patterns (of 7) that get an air conditioner, by look
BOARDS = {'residential': (), 'derelict': (1, 4, 5), 'industrial': (5,), 'civic': (), 'secure': ()}  # and that get boarded up
BARS = {'residential': (), 'civic': (), 'secure': tuple(range(7))}  # and, on the lowest row, barred (else patterns 2 and 6)
CORPORATE_ROOF = (('mast', 0.45, {'size': [0.8, 0.8], 'height': 0.3}), ('hvac', 1.0, None), ('vent', 0.5, None), ('dish', 0.6, None),
                  ('mast', 0.45, {'size': [0.8, 0.8], 'height': 0.3}))
ROOF = (('hvac', 1.0, None), ('tank', 1.0, None), ('vent', 0.5, None), ('dish', 0.6, None), ('antenna', 0.35, {'size': [0.6, 0.6], 'height': 0.5}), ('vent', 0.5, None))


def _facing(triangle):
    a, b, c = triangle; u = [b[axis] - a[axis] for axis in range(3)]; v = [c[axis] - a[axis] for axis in range(3)]
    nx, ny, nz = u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]; length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return None if length < 1e-9 or abs(nz) / length > 0.2 else (round(nx / math.hypot(nx, ny)), round(ny / math.hypot(nx, ny)))


def windows(nodes):
    """{(nx, ny): [(along, bottom, top, plane, width)]} of the upright window faces above head height, one per window: a face
    whose texture names a window (win..., ...window..., ..._win...)."""
    found = {}
    for node in nodes:
        if not node.rendered or not node.material or not (node.material.startswith(WINDOW) or 'window' in node.material or '_win' in node.material):
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
        merged[facing] = sorted(((box[0] + box[1]) / 2, box[2], box[3], box[4], round(box[1] - box[0], 3)) for box in boxes)
    return merged


def _fitted(nodes, facing, pane, reach=1.2):
    """Whether the tile already has something off its wall at a window (its own air conditioner, a sign, a lamp):
    nothing is added there."""
    along, bottom, top, plane, *_ = pane; moves = geometry.placed(nodes)
    for node in nodes:
        if not node.rendered:
            continue
        for x, y, z in map(moves[id(node)], node.verts):  # out in front of the window's wall, wherever the wall stands in the cell (a set-back facade's own units were missed, 2026-11-20)
            if 0.15 < x * facing[0] + y * facing[1] - plane < 2.0 and abs((y if facing[0] else x) - along) <= reach and bottom - 0.8 <= z <= top + 0.3:
                return True
    return False


def _turn(facing):
    """A wall piece's turn (degrees) that points its +y along `facing`."""
    return round(math.degrees(math.atan2(-facing[0], facing[1])), 1) % 360


def _on_wall(facing, along, plane, z):
    return [round(facing[0] * plane + (0 if facing[0] else along), 3), round(facing[1] * plane + (along if facing[0] else 0), 3), round(z, 3)]


DOORWAY = 5.0  # metres: a black opening taller than this is the dark inside of a building, not a door


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
            if door and max(p[2] for p in points) - min(p[2] for p in points) > DOORWAY:
                continue  # a black plane behind a whole facade's windows, not a doorway
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


GRIDS = {'hr08_wall': (8, 10, 0.18, 0.98, 0.8), 'hr09_build': (4, 4, 0.2, 0.8, 0.7)}  # windows painted in a texture: columns, rows, the glass's bottom and top in a cell (of v), and its width (of the cell's)


def grid_windows(nodes, grids=GRIDS):
    """{(nx, ny): [(along, bottom, top, plane, width)]} of windows painted in a texture as a regular grid (`grids`:
    texture: (columns, rows, glass bottom, glass top, glass width)), found through each upright face's texture
    coordinates, above head height."""
    import numpy as np
    found = {}
    for node in nodes:
        if not node.rendered or (node.material or '').lower() not in grids:
            continue
        columns, rows, low, high, wide = grids[node.material.lower()]; move = geometry.placed(nodes)[id(node)]
        for face in node.faces:
            if max(face[4:7]) >= len(node.tverts):
                continue
            points = [move(node.verts[corner]) for corner in face[:3]]; uv = [tuple(node.tverts[corner][:2]) for corner in face[4:7]]
            facing = _facing(points)
            if facing is None or abs(facing[0]) + abs(facing[1]) != 1:
                continue
            solve = np.array([[u, v, 1.0] for u, v in uv])
            if abs(np.linalg.det(solve)) < 1e-9:
                continue
            to_world = np.linalg.solve(solve, np.array(points))  # [u, v, 1] @ to_world = (x, y, z)
            plane = sum(point[0] * facing[0] + point[1] * facing[1] for point in points) / 3
            width = float(np.linalg.norm(to_world[0])) / columns * wide  # a cell's width in metres, of its glass
            us, vs = [u for u, _ in uv], [v for _, v in uv]
            for column in range(int(np.floor(min(us) * columns)), int(np.ceil(max(us) * columns))):
                for row in range(int(np.floor(min(vs) * rows)), int(np.ceil(max(vs) * rows))):
                    centre = ((column + 0.5) / columns, (row + 0.5) / rows)
                    weights = np.linalg.solve(solve.T, np.array([centre[0], centre[1], 1.0]))  # barycentric: is the cell's middle on this face
                    if weights.min() < -1e-6:
                        continue
                    ends = [np.array([centre[0], (row + fraction) / rows, 1.0]) @ to_world for fraction in (low, high)]
                    middle = np.array([centre[0], centre[1], 1.0]) @ to_world
                    bottom, top = sorted(end[2] for end in ends)
                    if bottom >= geometry.HEAD:
                        along = middle[1] if facing[0] else middle[0]
                        found.setdefault(facing, set()).add((round(float(along), 2), round(float(bottom), 2), round(float(top), 2), round(plane, 3), round(width, 3)))
    return {facing: sorted(panes) for facing, panes in found.items()}


def _wall_top(nodes, facing, plane, near=0.05):
    """The highest point of the rendered faces in a wall's plane, the facade's top."""
    placed = geometry.placed(nodes); top = None
    for node in nodes:
        if not node.rendered:
            continue
        move = placed[id(node)]
        for face in node.faces:
            points = [move(node.verts[corner]) for corner in face[:3]]
            if all(abs(point[0] * facing[0] + point[1] * facing[1] - plane) < near for point in points):
                top = max([top or -1e9] + [point[2] for point in points])
    return top if top is not None else 1e9


PANEL = (1.1, 1.5)  # the kit's bars and boards, across and up
INSET, WIDEST, TALLEST = 0.04, 2.6, 3.2  # each panel is fitted inside its window, at most this wide (a wider window gets several) and tall


def _panels(piece, facing, along, bottom, top, plane, width, turn):
    """Bars or boards fitted over a whole window: scaled to its width and height, side by side over a wide one."""
    count = max(1, math.ceil((width - 2 * INSET) / WIDEST)); across = (width - 2 * INSET) / count; up = min(top - bottom - 2 * INSET, TALLEST)
    first = along - (width - 2 * INSET) / 2 + across / 2
    return [{'piece': piece, 'at': _on_wall(facing, first + across * index, plane, bottom + INSET), 'turn': turn,
             'scale': [round(across / PANEL[0], 3), 1.0, round(up / PANEL[1], 3)]} for index in range(count)]


def propose(text, seed, *, look='brick', open=None, grids=None, above=None, plant=ROOF):
    """[{piece, at, turn, blocks?, cover?}] for a tile model's text. `open`: the facings of its sides on a street
    (`open_sides`); a facade on the cell's side facing any other way meets the next building, and gets nothing, unless
    all its windows stand `above` the neighbours' roofs (a tower in the middle of a lower block). `grids`: windows
    painted in textures (`GRIDS`). `plant`: the roof's pieces (`ROOF`), None for none; a roofless ruin (`look`
    'ruin') has burn barrels smoking on its upper floors instead (`RUIN`)."""
    _, _, nodes = geometry.parse(text); rng = zlib.crc32(str(seed).encode()); found = []
    seen = windows(nodes)
    for facing, panes in (grid_windows(nodes, grids) if grids else {}).items():
        seen[facing] = sorted(seen.get(facing, []) + panes)
    facades = {facing: [pane for pane in panes if not _fitted(nodes, facing, pane)] for facing, panes in seen.items()}
    facades = {facing: panes for facing, panes in facades.items() if panes
               and (open is None or facing in open or abs(panes[0][3]) < geometry.HALF - 0.3
                    or above is not None and min(bottom for _, bottom, *_ in panes) >= above)}
    walls, openings = [], _openings(nodes)
    for number, (facing, panes) in enumerate(sorted(facades.items())):
        turn = _turn(facing); plane = panes[0][3]; columns = sorted({round(along, 1) for along, *_ in panes}); walls.append((facing, plane, columns, turn))
        climbs = [column for column in columns if sum(round(along, 1) == column for along, *_ in panes) >= 2]  # two clear storeys at least
        escape = climbs[0] if number == 0 and climbs and look in ESCAPES else None
        rows = sorted({round(bottom, 1) for _, bottom, *_ in panes})
        for along, bottom, top, _, width in panes:
            column, row = columns.index(round(along, 1)), rows.index(round(bottom, 1)); pick = (rng >> (column * 3 + row)) % 7
            if escape is not None and round(along, 1) == escape:  # the highest platform has no stair up into the cornice
                top = bottom == max(low for at, low, *_ in panes if round(at, 1) == escape)
                found.append({'piece': 'fire_escape_top' if top else 'fire_escape', 'at': _on_wall(facing, along, plane, bottom - 0.12), 'turn': turn})
            elif pick in AIR.get(look, (0, 3)) and _ac_size(width, top - bottom) and bottom - 0.35 * _ac_size(width, top - bottom) >= geometry.OVER:  # in the window, on its sill (units hung under the windows looked small and wrong, 2026-11-20)
                size = _ac_size(width, top - bottom)
                found.append({'piece': 'ac_unit', 'at': _on_wall(facing, along, plane, bottom), 'turn': turn, **({'scale': size} if size != 1.0 else {})})
            elif pick in BOARDS.get(look, (5,)) or (look == 'timber' and pick == 1):
                found += _panels('boards', facing, along, bottom, top, plane, width, turn)
            elif row == 0 and pick in BARS.get(look, (2, 6)):
                found += _panels('bars', facing, along, bottom, top, plane, width, turn)
        apart = min((b - a for a, b in zip(columns, columns[1:])), default=0.0); clear = max(1.0, 0.3 * apart)  # off a wide window's glass
        edges = (min(along - width / 2 for along, _, _, _, width in panes) - 0.3, max(along + width / 2 for along, _, _, _, width in panes) + 0.3)
        ends = [end for end in (min(min(along for along, *_ in panes) - clear, edges[0]), max(max(along for along, *_ in panes) + clear, edges[1]))
                if abs(end) <= geometry.HALF - 0.3 and not _over_opening(openings, facing, plane, end)]
        if ends:
            end = ends[0]; roof = max(top for _, _, top, *_ in panes)
            raised = open is not None and facing not in open and abs(plane) >= geometry.HALF - 0.3  # stands on its neighbours' roofs
            foot = min(bottom for _, bottom, *_ in panes) - 1.0 if raised else geometry.OVER
            crown = _wall_top(nodes, facing, plane)  # the last length ends under the wall's top, not above a roof
            for z in sorted({round(min(foot + 3.0 * index, max(foot, crown - 3.0)), 3) for index in range(int((roof - foot) // 3.0) + 1)}):
                found.append({'piece': 'downpipe', 'at': _on_wall(facing, end, plane, z), 'turn': turn})
    roof = _roof(nodes, rng, plant) if plant else []; found += roof
    fx = _effects(nodes, found, walls, roof, rng)
    if look == 'ruin':  # squatters' fires in the rubble of the upper floors
        barrels = _roof(nodes, rng, RUIN, underside=True)[:2]; found += barrels
        fx += [{'piece': 'smoke', 'at': [one['at'][0], one['at'][1], round(one['at'][2] + 1.0, 3)]} for one in barrels]
    return found + fx


def _fixtures(nodes):
    """The points of what a tile already has off its walls (as `detail` guards them)."""
    moves = geometry.placed(nodes)
    return [point for node in nodes if node.rendered for point in map(moves[id(node)], node.verts)
            if max(abs(point[0]), abs(point[1])) - geometry.HALF > 0.2]


def _effects(nodes, found, walls, roof, rng):
    from .detail import turned
    fx = []; walk = geometry.walkable(nodes)
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
            lowest = min(pieces, key=lambda one: one['at'][2]); point = [round(value, 3) for value in turned(lowest['at'], lowest['turn'], lowest.get('scale', 1.0))(offset)]
            below = [height for height in walk.get(geometry.cell(point), ()) if height < point[2]]  # the ground under it, else the street at 0 m
            fx.append({'piece': 'drip', 'at': point, 'fall': round(point[2] - max(below, default=0.0), 3)})
    vents = [one for one in roof if one['piece'] == 'vent']
    if vents and (rng >> 23) % 2 == 0:
        x, y, z = vents[0]['at']; fx.append({'piece': 'smoke', 'at': [x, y, round(z + 0.75, 3)]})
    return fx


def _ceiling(nodes, roof, depth=1.0):
    """The grid cells with a face drawn facing down under the floor at `roof`, within `depth`: a floor seen from below."""
    found = set()
    for a, b, c in geometry.triangles(nodes):
        if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) < -1e-6 and all(roof - depth < point[2] < roof + 0.01 for point in (a, b, c)):
            found |= {geometry.cell(point) for point in geometry.samples((a, b, c))}
    return found


def _roof(nodes, rng, plant=ROOF, underside=False):
    """Roof pieces on the highest walkable surface. `underside`: only where that floor is drawn from below too; a
    ruin's floors are drawn from above alone, and from the street its burn barrels hung in the air (2026-11-20)."""
    walk = geometry.walkable(nodes); heights = [height for both in walk.values() for height in both if height > geometry.HEAD]
    if not heights:
        return []
    roof = max(heights); below = _ceiling(nodes, roof) if underside else None
    taken = {geometry.cell(point) for triangle in geometry.triangles(nodes) for point in geometry.samples(triangle) if roof + 0.1 < point[2] < roof + 4.0}
    placed, found = [], []
    spots = [(x / 2, y / 2) for x in range(-8, 9) for y in range(-8, 9)]
    spots = spots[rng % len(spots):] + spots[:rng % len(spots)]
    for index, (piece, reach, cover) in enumerate(plant[: 3 + rng % 3]):
        for x, y in spots:
            if abs(x) > geometry.HALF - EDGE or abs(y) > geometry.HALF - EDGE or any(math.hypot(x - px, y - py) < APART for px, py in placed):
                continue
            cells = {geometry.cell((x + dx, y + dy)) for dx in (-reach, 0, reach) for dy in (-reach, 0, reach)}
            if all(any(abs(height - roof) < 0.05 for height in walk.get(one, ())) for one in cells) and not cells & geometry.grown(taken) and (below is None or cells <= below):
                placed.append((x, y)); entry = {'piece': piece, 'at': [x, y, round(roof, 3)], 'turn': (rng >> index) % 4 * 90, 'blocks': True}
                if cover:
                    entry['cover'] = cover
                found.append(entry); break
    return found


def facades(nodes, open=None):
    """{(nx, ny): (plane, low along, high along, top)} of a tile's tower walls: for each way out of the cell, the
    outermost wall within 3.5 m of the cell's side whose upright faces reach from below `geometry.OVER` to 8 m or more
    (towers stand back from the street behind a plaza); `open` as in `propose`."""
    walls = {}
    for triangle in geometry.triangles(nodes):
        facing = _facing(triangle)
        if facing is None or abs(facing[0]) + abs(facing[1]) != 1 or (open is not None and facing not in open):
            continue
        plane = sum(point[0] * facing[0] + point[1] * facing[1] for point in triangle) / 3
        if plane < geometry.HALF - 3.5:
            continue
        along = [point[1] if facing[0] else point[0] for point in triangle]
        one = walls.setdefault((facing, round(plane * 4) / 4), [plane, min(along), max(along), 99.0, -99.0])
        one[0] = max(one[0], plane); one[1] = min(one[1], min(along)); one[2] = max(one[2], max(along))
        one[3] = min(one[3], min(point[2] for point in triangle)); one[4] = max(one[4], max(point[2] for point in triangle))
    found = {}
    for (facing, _), (plane, low, high, bottom, top) in sorted(walls.items(), key=lambda item: item[1][0]):
        if bottom < geometry.OVER and top >= 8.0 and high - low >= 2.0:
            found[facing] = (round(plane, 3), max(low, -geometry.HALF), min(high, geometry.HALF), top)  # the outermost last
    return found


FLUSH = 0.06  # metres: faces this close to one plane are one flat wall
DEEPEST = 0.6  # metres a wall a fixture is screwed to may stand behind the facade's front


def _glassy(material):
    name = (material or '').lower()
    return name.startswith(WINDOW) or 'window' in name or '_win' in name or 'glass' in name


def _wall_faces(nodes, facing, plane):
    """[(triangle in (along, z), its plane, glass?)] of the tile's faces looking out of a wall, at most DEEPEST behind
    the facade's front `plane`: what a fixture on that wall could be screwed to."""
    found = []
    for node in nodes:
        if not node.rendered:
            continue
        glass = _glassy(node.material)
        for triangle in geometry.triangles(nodes, lambda other, node=node: other is node):
            depth = sum(point[0] * facing[0] + point[1] * facing[1] for point in triangle) / 3
            if _facing(triangle) == tuple(facing) and plane - DEEPEST <= depth <= plane + FLUSH:
                found.append(([((point[1] if facing[0] else point[0]), point[2]) for point in triangle], depth, glass))
    return found


def _inside(triangle, point):
    (ax, ay), (bx, by), (cx, cy) = triangle; px, py = point
    d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by); d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy); d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
    return not ((d1 < -1e-9 or d2 < -1e-9 or d3 < -1e-9) and (d1 > 1e-9 or d2 > 1e-9 or d3 > 1e-9))


def _solid(faces, along, z, size=1.0, reach=(0.12, -0.24, 0.17)):
    """The plane of the flat, solid wall where a fixture `size` times a camera's mount goes at (along, z), or None: the
    frontmost face behind every part of it is one plane and none of it glass, so no window set back into the wall and
    no doorway or edge is behind any of it (cameras hung over recessed windows, 2026-11-20)."""
    half, low, high = (value * size for value in reach); planes = []
    for a in (along - half, along, along + half):
        for h in (z + low, z + (low + high) / 2, z + high):
            under = [(depth, glass) for triangle, depth, glass in faces if _inside(triangle, (a, h))]
            if not under:
                return None
            depth, glass = max(under)
            if glass:
                return None
            planes.append(depth)
    return max(planes) if max(planes) - min(planes) <= FLUSH else None


SIGN_REACH = (0.5, -0.02, 0.65)  # a hazard plate's half width, and its foot and top over its origin
SIGN_LIFTS = (0.0, 0.4, 0.8)  # a plate goes up, never down below head height


def _mount(faces, along, z, low, high, size=1.0, reach=(0.12, -0.24, 0.17), lifts=(0.0, 0.4, -0.4)):
    """(along, z, plane) nearest to the wanted spot where the wall is solid behind a fixture of `reach` (a camera's by
    default) `size` times over, within 2.5 m along it and `lifts` up or down, or None."""
    for step in range(26):
        for shift in ((0.0,) if step == 0 else (step * 0.1, -step * 0.1)):
            for lift in lifts:
                if low + 0.3 <= along + shift <= high - 0.3:
                    plane = _solid(faces, along + shift, z + lift, size, reach)
                    if plane is not None:
                        return round(along + shift, 3), z + lift, plane
    return None


def propose_corporate(text, seed, *, open=None, plant=CORPORATE_ROOF, ledges=True, watch=False, beside='camera', sign=None, eye=1.0):
    """[{piece, at, turn, blocks?, cover?}] for a corporate tower tile: on each tower wall a canopy over each street door
    with a camera beside it, and a ledge on about half (`ledges`); `plant` on the roof (masts and plant), None for none.
    `watch`: a wall with no street door has a camera at each end (a secure site), and `sign` (a piece) in its middle.
    `beside`: the piece beside each door (a camera; a hospital's lit sign); `eye`: the cameras' scale."""
    _, _, nodes = geometry.parse(text); rng = zlib.crc32(str(seed).encode()); found = []; openings = _openings(nodes)
    for number, (facing, (plane, low, high, top)) in enumerate(sorted(facades(nodes, open).items())):
        turn = _turn(facing); bits = rng >> (number * 5); middle = (low + high) / 2
        doors = sorted({round((one[2] + one[3]) / 2 if facing[0] else (one[0] + one[1]) / 2, 2) for one in openings if one[4]
                        and _over_opening([one], facing, plane, (one[2] + one[3]) / 2 if facing[0] else (one[0] + one[1]) / 2)})
        wall = _wall_faces(nodes, facing, plane)  # cameras and signs go on solid wall, never over glass or a recessed window
        for door in doors:
            found.append({'piece': 'canopy', 'at': _on_wall(facing, door, plane, 3.4), 'turn': turn})
            side = door + 2.0 if door + 2.0 < high - 0.3 else door - 2.0
            size = eye if beside == 'camera' else 2.0
            spot = _mount(wall, side, 4.0 if beside == 'camera' else 3.0, low, high, size) if low + 0.3 < side < high - 0.3 else None
            if spot and abs(spot[0] - door) > 1.0:
                found.append({'piece': beside, 'at': _on_wall(facing, spot[0], spot[2], spot[1]), 'turn': turn,
                              **({'scale': eye} if beside == 'camera' and eye != 1.0 else {})})
        if watch and not doors and high - low > 1.2:
            # one watch camera a tile, at one end of one wall: one at each end of every wall put two a metre apart
            # where tiles meet, and four on a corner (too frequent, user 2026-11-20)
            for end in ((low + 0.6,) if bits % 2 else (high - 0.6,)) if not any(one['piece'] == 'camera' for one in found) else ():
                spot = _mount(wall, end, 4.0, low, high, eye)
                if spot:
                    found.append({'piece': 'camera', 'at': _on_wall(facing, spot[0], spot[2], spot[1]), 'turn': turn, **({'scale': eye} if eye != 1.0 else {})})
            spot = _mount(wall, (low + high) / 2, geometry.OVER + 0.05, low, high, reach=SIGN_REACH, lifts=SIGN_LIFTS) if sign and high - low > 3.0 else None
            if spot:  # on solid wall, as the cameras are: plates were put on a lab's glass (2026-11-20)
                found.append({'piece': sign, 'at': _on_wall(facing, spot[0], spot[2], spot[1]), 'turn': turn})
        if ledges and bits % 2 == 0:
            for along in [low + 1.25 + 2.5 * index for index in range(int((high - low) // 2.5))]:
                found.append({'piece': 'ledge', 'at': _on_wall(facing, along, plane, 4.7), 'turn': turn})
    return found + (_roof(nodes, rng, plant) if plant else [])


KERB = (0.1, 0.35)  # metres: how high a kerb stands over its road
SIDE_CLEAR = 0.8  # metres a street piece's cut keeps off the cell's side, so the neighbour's walkmesh still meets this one
# one tile in this many gets each street piece (at most one, or one row of bollards, a tile); every 6 m along every
# kerb drains, and bollards, hydrants and bins on most kerbs, were far too many (user, 2026-11-20)
ONE_IN = {'drain': 3, 'manhole': 4, 'bollards': 8, 'hydrant': 10, 'litter_bin': 8, 'steam': 4}
SETBACK = 0.45  # metres from the kerb's face to the middle of the furniture on the sidewalk behind it
FURNITURE = {'bollard': 0.1, 'hydrant': 0.24, 'litter_bin': 0.26}  # each piece's radius seen from above
BOLLARDS = 1.5  # metres between the bollards of a row
APART_STREET = 1.2  # metres kept between other furniture, beyond their radii
LIFT = 0.002  # metres a flat piece stands over the ground it lies on, so the two do not flicker


def _kerbs(nodes):
    """[(normal, plane, low along, high along, road z, sidewalk z)] of the tile's kerbs: walkmesh edges straight along x
    or y at the top of an upright step of `KERB` height, `normal` (nx, ny) pointing from the sidewalk to the road, and
    `plane` the kerb face's coordinate along it."""
    tris = [triangle for node in nodes if node.kind == 'aabb' for triangle, face in zip(geometry._corners(node, nodes), node.faces)
            if len(face) >= 8 and face[7] in geometry.WALKABLE and max(point[2] for point in triangle) < geometry.HEAD]
    walk = geometry.walkable(nodes); runs = {}
    for triangle in tris:
        for p, q in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            if abs(p[2] - q[2]) > 0.01 or (abs(p[0] - q[0]) > 0.01 and abs(p[1] - q[1]) > 0.01) or math.dist(p[:2], q[:2]) < 0.05:
                continue
            axis = 0 if abs(p[1] - q[1]) > 0.01 else 1  # the axis across the edge
            middle = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            sides = []
            for sign in (1, -1):
                probe = list(middle); probe[axis] += sign * 0.3; sides.append(walk.get(geometry.cell(probe), ()))
            for sign, here, there in ((1, sides[1], sides[0]), (-1, sides[0], sides[1])):  # the sidewalk on one side at the edge's height, the road on the other a kerb lower
                lower = [height for height in there if KERB[0] <= p[2] - height <= KERB[1]]
                if any(abs(height - p[2]) < 0.03 for height in here) and lower and not any(abs(height - p[2]) < 0.03 for height in there):
                    normal = (sign, 0) if axis == 0 else (0, sign)
                    runs.setdefault((normal, round(middle[axis] * sign, 3), round(max(lower), 3), round(p[2], 3)), []).append(sorted((p[1 - axis], q[1 - axis])))
                    break
    found = []
    for (normal, plane, road, top), spans in sorted(runs.items()):
        spans.sort(); joined = [list(spans[0])]
        for low, high in spans[1:]:
            if low <= joined[-1][1] + 0.01:
                joined[-1][1] = max(joined[-1][1], high)
            else:
                joined.append([low, high])
        found += [(normal, plane, low, high, road, top) for low, high in joined if high - low >= 1.0]
    return found


def _ground(nodes, step=geometry.STEP):
    """{grid cell: (lowest, [heights])} of the tile's rendered surfaces under `geometry.HEAD`: the ground drawn in
    each cell, and the heights of everything drawn there."""
    found = {}
    for triangle in geometry.triangles(nodes):
        if min(point[2] for point in triangle) > geometry.HEAD:
            continue
        for point in geometry.samples(triangle, step / 2):
            found.setdefault(geometry.cell(point, step), []).append(point[2])
    return {key: (min(heights), heights) for key, heights in found.items()}


def _near_cells(centre, radius, step=geometry.STEP):
    here = geometry.cell(centre, step); reach = math.ceil(radius / step) + 1
    return [(here[0] + dx, here[1] + dy) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)
            if math.dist(((here[0] + dx + 0.5) * step, (here[1] + dy + 0.5) * step), centre) <= radius + step * 0.75]


def _side_of(normal, plane, side):
    """A test of grid cells wholly on one side of a kerb's face: the road's (`side` 1) or the sidewalk's (-1)."""
    return lambda key: side * (((key[0] + 0.5) * normal[0] + (key[1] + 0.5) * normal[1]) * geometry.STEP - plane) > geometry.STEP / 2 + 0.01


def _clear_ground(ground, centre, radius, over=0.004, keep=lambda key: True):
    """The ground's height at `centre` where it is one level within `radius` and nothing the tile draws stands over
    it there (a lamp post, a kerb, a manhole of the tile's own), else None."""
    level = None
    for key in filter(keep, _near_cells(centre, radius)):
        if key not in ground:
            return None
        lowest, heights = ground[key]
        if level is not None and abs(lowest - level) > 0.03 or any(lowest + over < height < lowest + geometry.HEAD for height in heights):
            return None
        level = lowest if level is None else max(level, lowest)
    return level


def _on_walk(walk, centre, radius, height, keep=lambda key: True):
    """Whether the walkable surface at `height` runs under every cell within `radius` of `centre` (that `keep` keeps)."""
    return all(any(abs(found - height) < 0.05 for found in walk.get(key, ())) for key in filter(keep, _near_cells(centre, radius)))


def _within(point, margin):
    return max(abs(point[0]), abs(point[1])) <= geometry.HALF - margin


def propose_street(text, seed):
    """[{piece, at, turn, obstacle?}] for a street tile (the Concrete terrain), each piece on one tile in `ONE_IN`
    of it at most once: a drain in the gutter of a kerb; a row of three bollards, a hydrant or a litter bin on the
    sidewalk behind a kerb, each an `obstacle` (cut out of the street's walkmesh flat); a manhole in the road of a
    tile that has none of its own; and steam off a manhole. Every piece stands on clear ground, where the tile
    draws nothing over it (a lamp post, a traffic light, its own manhole), and furniture on walkable sidewalk all
    round, `SIDE_CLEAR` in from the cell's side."""
    _, _, nodes = geometry.parse(text); rng = zlib.crc32(str(seed).encode()); found, fx = [], []
    walk, ground, kerbs = geometry.walkable(nodes), _ground(nodes), _kerbs(nodes)
    standing = []  # (x, y, radius) of the furniture placed
    chance = lambda what: zlib.crc32(f'{seed}:{what}'.encode()) % ONE_IN[what] == 0  # each piece's own draw, so the rates are independent
    order = sorted(range(len(kerbs)), key=lambda number: zlib.crc32(f'{seed}:kerb{number}'.encode()))  # which kerb is tried first

    def spots(low, high, what):  # places along a kerb, from a point of the tile's own
        found = [low + 0.6 + 0.25 * index for index in range(max(0, int((high - low - 1.2) / 0.25)) + 1)]
        shift = zlib.crc32(f'{seed}:{what}'.encode()) % len(found) if found else 0
        return found[shift:] + found[:shift]

    def kerb(number):
        normal, plane, low, high, road, top = kerbs[number]
        return normal, plane, max(low, -geometry.HALF + SIDE_CLEAR), min(high, geometry.HALF - SIDE_CLEAR), road, top
    if chance('drain'):  # one drain in the gutter, the road side of a kerb's face
        for number in order:
            normal, plane, low, high, road, top = kerb(number); road_side = _side_of(normal, plane, 1); placed = False
            for along in spots(low, high, 'drain'):
                middle = _on_wall(normal, along, plane + 0.24, 0.0)[:2]; level = _clear_ground(ground, middle, 0.3, keep=road_side)
                if level is not None and abs(level - road) < 0.05 and _on_walk(walk, middle, 0.2, road, keep=road_side):
                    found.append({'piece': 'drain', 'at': _on_wall(normal, along, plane, level + LIFT), 'turn': _turn(normal)}); placed = True; break
            if placed:
                break
    for wish in [what for what in ('bollards', 'hydrant', 'litter_bin') if chance(what)]:  # furniture on the sidewalk behind a kerb
        piece = 'bollard' if wish == 'bollards' else wish; radius = FURNITURE[piece]; placed = False
        for number in order:
            normal, plane, low, high, road, top = kerb(number); behind = _side_of(normal, plane, -1)

            def fits(along):  # (x, y, ground) of the piece there, or None
                middle = tuple(_on_wall(normal, along, plane - SETBACK, 0.0)[:2])
                if not _within(middle, SIDE_CLEAR + radius) or any(math.dist(middle, (x, y)) < APART_STREET + radius + reach for x, y, reach in standing):
                    return None
                level = _clear_ground(ground, middle, radius + 0.3, keep=behind)
                return (*middle, level) if level is not None and abs(level - top) <= 0.05 and _on_walk(walk, middle, radius + 0.25, top, keep=behind) else None
            for along in spots(low, high, wish):
                row = [fits(along + BOLLARDS * index) for index in range(3 if wish == 'bollards' else 1)]  # a row of three bollards, or one piece
                if all(row):
                    for x, y, level in row:
                        found.append({'piece': piece, 'at': [round(x, 3), round(y, 3), round(level, 3)], 'turn': _turn(normal), 'obstacle': True})
                    standing.extend((x, y, radius) for x, y, _ in row); placed = True; break
            if placed:
                break
    moves = geometry.placed(nodes); holes = []
    for node in nodes:  # the tile's own manholes
        if node.rendered and node.verts and ('manhole' in node.name.lower() or 'manhole' in (node.material or '').lower()):
            points = [moves[id(node)](vertex) for vertex in node.verts]
            holes.append([round(sum(point[axis] for point in points) / len(points), 3) for axis in range(3)])
    if not holes and chance('manhole'):  # a manhole in the road, clear of the kerbs
        lowest = min((height for heights in walk.values() for height in heights if height < geometry.HEAD), default=None)
        spots = [(x / 2, y / 2) for x in range(-7, 8) for y in range(-7, 8)]; shift = (rng >> 14) % len(spots); spots = spots[shift:] + spots[:shift]
        for spot in spots if lowest is not None else []:
            if not _within(spot, 1.2) or any(abs(spot[0] * normal[0] + spot[1] * normal[1] - plane) < 1.0 for normal, plane, *_ in kerbs):
                continue
            level = _clear_ground(ground, spot, 0.5)
            if level is not None and abs(level - lowest) < 0.05 and _on_walk(walk, spot, 0.5, lowest):
                found.append({'piece': 'manhole', 'at': [spot[0], spot[1], round(level + LIFT, 3)], 'turn': (rng >> 15) % 4 * 90}); holes.append([spot[0], spot[1], round(level, 3)])
                break
    if holes and chance('steam'):  # steam off a manhole
        x, y, z = holes[0]; fx.append({'piece': 'steam', 'at': [x, y, round(z + 0.05, 3)]})
    return found + fx
