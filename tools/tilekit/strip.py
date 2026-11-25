"""What of a furnished interior tile is its room and what is its furniture, and the tile without the furniture.

The Modern Interior set (tfb01) builds period furniture into its floor tiles: beds, bookcases, barrels, rugs. A room
shell is the tile without them. Texture names do not tell the two apart (a table and a door frame share one, a
bookcase and the floor another), and neither does the walkmesh (a bookcase against a wall is walked as wall). Where a
part stands does: the room's floor ends at its walls, so what stands on the floor is in the room.

A drawn part (`sort`) is
- `floor`: flat on the ground, with nothing flat under it;
- `rug`: flat, a finger above the floor it lies on and smaller than it;
- `top`: at or above the walls' top (the black lid over a wall, a lintel, a roof beam);
- `shell`: off the floor (a wall, a door frame), at the tile's very edge (a door leaf), or reaching from wall to wall;
- `builtin`: stands on the floor and reaches the walls' top, or lies within one that does (a bookcase, its shelves
  and books; a partition; a chimney breast), or would leave a hole in the room were it gone (`_holes`: the wall or
  the floor behind it was never drawn), or touches one that would (a bed's mattress on its frame): part of the room, kept and given a new look in place (user rule 2026-11-24);
- `furniture`: everything else, which stands on the floor inside the room.

Stripped (`stripped`), a tile keeps its floor, shell, tops and what is built in. A face of its walkmesh that is not walked and lay under
furniture becomes the room's own walked surface, on the ground; one no furniture stood on stays (a stair's void, a
wall). `shell` writes the stripped tile whole: its model with the new walkmesh in it, and its walkmesh file."""
import numpy as np

from . import geometry, require

LOW = 0.12  # metres: what lies no higher is on the ground
LIFT = 0.004  # metres: a flat part this far above another lies on it
LID = 2.9  # metres: the walls' top (3.0 in tfb01) less a little
REACH = 6.5  # metres: a part this long runs from wall to wall
EDGE = 4.4  # metres from the tile's middle: what lies wholly beyond is in a doorway or the tile's rim
ON = 0.5  # the share of a part's footprint on the floor that puts it in the room
TALL = 2.85  # metres: what stands on the floor and reaches this high is built in
WITHIN = 0.05  # metres of slack for a part lying within a built-in one's box
EYE = 1.5  # metres: the height a room is looked through from, to find what would leave a hole
SEEN = 12  # places on the floor it is looked from
HOLE = 0.15  # the share of a part's seen points with nothing behind them that makes it built in
KINDS = ('floor', 'rug', 'top', 'shell', 'builtin', 'furniture')


def _plan(points, faces):
    """[(three corners in x and y, area seen from above)] of a part's faces."""
    made = []
    for face in faces:
        corners = points[list(face[:3]), :2]
        made.append((corners, abs((corners[1][0] - corners[0][0]) * (corners[2][1] - corners[0][1]) - (corners[1][1] - corners[0][1]) * (corners[2][0] - corners[0][0])) / 2))
    return made


def _within(triangles, x, y):
    for corners, area in triangles:
        if area < 1e-9:
            continue
        (ax, ay), (bx, by), (cx, cy) = corners; whole = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        first = ((bx - x) * (cy - y) - (by - y) * (cx - x)) / whole; second = ((cx - x) * (ay - y) - (cy - y) * (ax - x)) / whole
        if first >= -1e-6 and second >= -1e-6 and first + second <= 1 + 1e-6:
            return True
    return False


def _share(plan, points, ground):
    """The share of a part's footprint that lies on `ground` ([plan triangle]): by its faces seen from above, each
    weighed by its area; of a part with none (an upright sheet), whether its middle does."""
    weighed = [(corners.mean(0), area) for corners, area in plan if area > 1e-6]
    if not weighed:
        return float(_within(ground, *points[:, :2].mean(0)))
    return sum(area for middle, area in weighed if _within(ground, *middle)) / sum(area for _, area in weighed)


def _hits(origins, ways, triangles):
    """How far along each ray (origin, way) the nearest of `triangles` [n, 3, 3] is met, from either side; inf where none."""
    if not len(triangles):
        return np.full(len(origins), np.inf)
    first, second = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    cross = np.cross(ways[:, None, :], second[None]); det = (first[None] * cross).sum(-1)
    with np.errstate(divide='ignore', invalid='ignore'):
        inverse = np.where(np.abs(det) > 1e-12, 1.0 / det, 0.0); off = origins[:, None, :] - triangles[None, :, 0]
        u = (off * cross).sum(-1) * inverse; other = np.cross(off, first[None]); v = (ways[:, None, :] * other).sum(-1) * inverse
        far = (second[None] * other).sum(-1) * inverse
    met = (np.abs(det) > 1e-12) & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (far > 1e-6)
    return np.where(met, far, np.inf).min(1)


def _solid(part):
    return np.array([part['points'][list(face[:3])] for face in part['faces']], float).reshape(-1, 3, 3)


def _holes(parts, floor, half=5.0):
    """The names of the standing parts (kind furniture or rug) that would leave a hole in the room were they all
    gone. The room is looked through from places on its floor, at eye height and level with the part, toward each part's faces: where a part is
    seen and nothing of the room is behind it before the tile's side or under its floor, the room was never drawn
    there. A look that leaves over the walls' top is at the sky, not through a hole."""
    standing = [part for part in parts if part['kind'] in ('furniture', 'rug')]
    if not standing or not floor:
        return set()
    spots = sorted(((corners.mean(0), area) for part in floor for corners, area in part['plan'] if area > 0.05), key=lambda spot: -spot[1])
    spots = spots[::max(1, len(spots) // SEEN)][:SEEN]; eyes = np.array([(x, y, EYE) for (x, y), _ in spots], float)
    if not len(eyes):
        return set()
    kept = np.concatenate([_solid(part) for part in parts if part['kind'] not in ('furniture', 'rug')] or [np.zeros((0, 3, 3))])
    theirs = {part['name']: _solid(part) for part in standing}; found = set()
    for part in standing:
        mine = theirs[part['name']]; aims = mine.mean(1); aims = aims[::max(1, len(aims) // 40)][:40]
        origins = np.repeat(eyes, len(aims), axis=0); aimed = np.tile(aims, (len(eyes), 1))
        level = origins.copy(); level[:, 2] = np.maximum(aimed[:, 2], 0.05)  # and level with the part: a low bed hides the wall's foot, which a look from eye height passes over
        if part['kind'] == 'furniture':  # a rug is looked down on only: a level look skims the floor it lies on
            origins = np.concatenate([origins, level]); aimed = np.concatenate([aimed, aimed])
        ways = aimed - origins
        reach = np.linalg.norm(ways, axis=1); ways = ways / np.maximum(reach, 1e-9)[:, None]
        others = np.concatenate([theirs[name] for name in theirs if name != part['name']] or [np.zeros((0, 3, 3))])
        seen = (reach > 1e-6) & (_hits(origins, ways, kept) > reach - 1e-3)  # nothing of the room stands before the part
        if not seen.any():
            continue
        origins, ways, reach = origins[seen], ways[seen], reach[seen]; behind = _hits(origins, ways, kept)
        with np.errstate(divide='ignore', invalid='ignore'):  # where the look leaves the tile: its side, under its floor, or over its walls
            side = np.min(np.where(np.abs(ways[:, :2]) > 1e-9, (np.sign(ways[:, :2]) * half - origins[:, :2]) / ways[:, :2], np.inf), axis=1)
            under = np.where(ways[:, 2] < -1e-9, (-0.05 - origins[:, 2]) / ways[:, 2], np.inf); over = np.where(ways[:, 2] > 1e-9, (LID - origins[:, 2]) / ways[:, 2], np.inf)
        out = np.minimum(side, under); through = (behind > out) & (out < over)
        if through.sum() >= 2 and through.mean() >= HOLE:
            found.add(part['name'])
    return found


def sort(nodes, moves=None):
    """{node name: (kind, {low, high, span, area, onFloor})} of a tile's drawn parts (`KINDS`)."""
    moves = moves or geometry.placed(nodes); parts = []
    for node in nodes:
        if node.kind == 'aabb' or not node.rendered or not node.verts or not node.faces:
            continue
        points = np.array([moves[id(node)](vertex) for vertex in node.verts], float); plan = _plan(points, node.faces)
        parts.append({'name': node.name, 'points': points, 'plan': plan, 'faces': node.faces, 'low': float(points[:, 2].min()), 'high': float(points[:, 2].max()),
                      'span': float(max(np.ptp(points[:, 0]), np.ptp(points[:, 1]))), 'area': float(sum(area for _, area in plan))})
    flat = sorted((part for part in parts if part['high'] <= LOW and part['area'] > 1e-3), key=lambda part: (part['low'], -part['area']))
    floor = []
    for part in flat:  # from the lowest up: one lying on a wider one below it is a rug
        under = [other for other in floor if other['low'] < part['low'] - LIFT and other['area'] > part['area']]
        on = _share(part['plan'], part['points'], [triangle for other in under for triangle in other['plan']]) if under else 0.0
        part['kind'] = 'rug' if on >= 0.9 else 'floor'
        if part['kind'] == 'floor':
            floor.append(part)
    ground = [triangle for part in floor for triangle in part['plan']]; found = {}
    for part in parts:
        on = _share(part['plan'], part['points'], ground) if ground else 0.0; rim = np.abs(part['points'][:, :2]).max(1).min() > EDGE
        if 'kind' in part:
            kind = part['kind']
        elif part['high'] <= LOW:
            kind = 'rug' if on >= ON else 'shell'  # a flat scrap with no area to speak of
        elif part['low'] >= LID:
            kind = 'top'
        elif on < ON or rim or part['span'] >= REACH:
            kind = 'shell'
        else:
            kind = 'furniture'
        part['kind'] = kind; part['on'] = on
    standing = [part for part in parts if part['kind'] == 'furniture']; tall = [(part['points'].min(0) - WITHIN, part['points'].max(0) + WITHIN) for part in standing if part['high'] >= TALL]
    for part in standing:  # a bookcase's shelves and books are the bookcase's
        if any((part['points'].min(0) >= low).all() and (part['points'].max(0) <= high).all() for low, high in tall):
            part['kind'] = 'builtin'
    holed = _holes(parts, floor)
    for part in parts:
        if part['name'] in holed:
            part['kind'] = 'builtin'
    grew = True  # a bed's mattress stays with its frame: what touches a built-in part is of the same piece
    while grew:
        grew = False; built = [(part['points'].min(0) - WITHIN, part['points'].max(0) + WITHIN) for part in parts if part['kind'] == 'builtin']
        for part in parts:
            if part['kind'] == 'furniture' and any((part['points'].max(0) >= low).all() and (part['points'].min(0) <= high).all() for low, high in built):
                part['kind'] = 'builtin'; grew = True
    for part in parts:
        kind, on = part['kind'], part['on']
        found[part['name']] = (kind, {'low': round(part['low'], 2), 'high': round(part['high'], 2), 'span': round(part['span'], 2), 'area': round(part['area'], 2), 'onFloor': round(on, 2)})
    return found


def stripped(text, gone=('furniture', 'rug')):
    """(a tile's uncompiled model without its parts of the kinds `gone`, [the names left out], its walk faces as
    ([[x, y, z] * 3], surface), those not walked that furniture stood on made the room's walked surface)."""
    lines, _, nodes = geometry.parse(text); moves = geometry.placed(nodes); sorted_ = sort(nodes, moves)
    out = [node for node in nodes if sorted_.get(node.name, ('', {}))[0] in gone]
    stood = []
    for node in out:
        if sorted_[node.name][0] == 'furniture':
            points = np.array([moves[id(node)](vertex) for vertex in node.verts], float); stood += [triangle for triangle in _plan(points, node.faces) if triangle[1] > 1e-6]
            low, high = points[:, :2].min(0), points[:, :2].max(0)  # and its box: a table's legs leave most of its footprint undrawn from above
            box = np.array([[low[0], low[1]], [high[0], low[1]], [high[0], high[1]], [low[0], high[1]]])
            stood += [(box[[0, 1, 2]], 1.0), (box[[0, 2, 3]], 1.0)]
    walk = []
    for node in nodes:
        if node.kind == 'aabb':
            points = [moves[id(node)](vertex) for vertex in node.verts]
            walk += [([list(map(float, points[corner])) for corner in face[:3]], int(face[7]) if len(face) > 7 else 0) for face in node.faces]
    require(walk, 'The tile has no walkmesh')
    walked = {}
    for corners, surface in walk:
        if surface in geometry.WALKABLE:
            (ax, ay, _), (bx, by, _), (cx, cy, _) = corners; walked[surface] = walked.get(surface, 0.0) + abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2
    own = max(walked, key=walked.get) if walked else None; faces = []
    for corners, surface in walk:
        middle = np.mean(corners, axis=0)
        free = own is not None and surface not in geometry.WALKABLE and _within(stood, middle[0], middle[1])
        faces.append(([[x, y, 0.0] for x, y, _ in corners], own) if free else (corners, surface))  # a bed's top was walked as a raised block: the floor is under it
    kept = list(lines)
    for node in sorted(out, key=lambda node: -node.start):
        del kept[node.start:node.end + 1]
    return '\n'.join(kept), [node.name for node in out], faces


def shell(text, name=None, gone=('furniture', 'rug')):
    """(a tile's uncompiled model stripped (`stripped`) and carrying its new walkmesh, its walkmesh file's text, [the
    names left out]). name: the model's new name, where the shell is a tile of its own beside the furnished one."""
    from tools.envkit import tile
    from . import joins, terrain
    lines, root, nodes = geometry.parse(text); kept, out, faces = stripped(text, gone)
    solid = [np.array([[*corner, surface, 0.0] for corner in corners], float) for corners, surface in faces]
    solid = [triangle for triangle in solid if np.linalg.norm(np.cross(triangle[1, :3] - triangle[0, :3], triangle[2, :3] - triangle[0, :3])) > 1e-7]  # a block's side laid flat
    walk = joins.conformed(solid)
    lines, _, left = geometry.parse(kept); body = list(lines)
    for node in sorted((node for node in left if node.kind == 'aabb'), key=lambda node: -node.start):
        del body[node.start:node.end + 1]
    end = next(index for index, line in enumerate(body) if line.strip().lower().startswith('endmodelgeom'))
    body[end:end] = tile._walk_node(root, root, *walk); made = chr(10).join(body)
    if name:
        require(len(name) <= 16 and name == name.lower(), 'A tile model name is a lowercase resref: ' + name)
        made = terrain.renamed(made, {root: name}); root = name
    return made, tile.walk_text(root, walk), out
