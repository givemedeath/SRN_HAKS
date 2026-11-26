"""Creatures sent across a tile's suspect floor edges in the game client, both ways, and the routes that bend or stop.

`plan` finds the crossings on a tile's `.wok` (the walkmesh the game walks): for each edge `floors` flags (met in
pieces, pinched by a face of no area, or of a face held twice), a point on either side with floor at the edge's height
and room for a creature; with `sides`, crossings over each of the tile's four sides into a tile of the set whose floor
is level with it there (floors that end short of the side, 2026-11-25). `layout` lays every tile twice, for a Human
and a Troll, in one area of the set, with the neighbours its side crossings need; `script` writes walkers that go to
each crossing's first point, across and back, and log where they are four times a second; `verdict` reads that log. A
crossing bent: the route strayed more than BENT metres from the straight line; short: the walker stopped more than
SHORT metres from its goal; missing: the walker never reached it at all. The same plan is walked before and after a
repair (the command keeps it in `--plan`): a repaired edge is no longer flagged, so its crossings would not be found
again. Walked so on 2026-11-25: 1,343 of 1,364 crossings of T-junctions bent before their repair, 4 after
(docs/tilesets/walkmesh-repairs.md)."""
import math
from pathlib import Path

import numpy as np

from . import floors, geometry, inventory, require

WALKERS = {'human': 6, 'troll': 15104}  # appearance.2da rows: the smallest and the largest walker repairs are judged by
BENT = .15  # metres a route may stray from the straight line between its two points
SHORT = .15  # metres a walker may stop from its goal
ROOM = .35  # metres of floor round a crossing's point, every way: a creature stands there
LEVEL = (.3, .8)  # how far a point's floor may lie from the edge's height, tried in turn (a ramp's edge needs the second)
OFF = (1.2, .9, .6, .4)  # how far from the edge a crossing's points are looked for, furthest first
EDGE = 4.95  # a point of a crossing over an edge lies this far from the tile's middle at most: past it is the neighbour's
AREA = 'wlk'  # the walk area's tag
COLUMNS = 6  # tiles across the walk area, three cells apart
LEG = 3.2  # seconds a walker is given for each leg of its walk
TICK = .25  # seconds between the walkers' logged positions
START = 12.0  # seconds after the player enters before the walkers set off: the area's models have loaded
PREFIX = 'ENVKIT'  # the client log lines a run keeps (envkit's prop fixture)
TURNS = ((1, 0), (0, 1), (-1, 0), (0, -1))  # (cos, sin) of a laid tile's turn, a quarter at a time


def load(text):
    """(corners, faces, placed) of a .wok's text: the walkmesh node's own corners and faces, and the corners in the tile."""
    _, _, nodes = geometry.parse(text if 'beginmodelgeom' in text.lower() else 'beginmodelgeom wok\n' + text)
    found = [node for node in nodes if node.kind == 'aabb' and node.faces]; require(len(found) == 1, f'{len(found)} walkmeshes, not one')
    node = found[0]; place = geometry.placed(nodes)[id(node)]
    return np.array(node.verts, dtype=float), node.faces, np.array([place(tuple(vertex)) for vertex in node.verts], dtype=float)


def triangles(corners, faces, placed):
    """The walked faces as corner triples in the tile, shape (faces, 3, 3)."""
    return placed[np.array(floors.numbered(corners, faces), dtype=int).reshape(-1, 3)]


def heights(floor, point):
    """The heights of the floor facing up over `point` (x, y), lowest first, to the millimetre."""
    if not len(floor):
        return []
    a, b, c = floor[:, 0], floor[:, 1], floor[:, 2]
    turn = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]); up = turn > 2e-6; turn = np.where(up, turn, 1)
    one = ((b[:, 0] - point[0]) * (c[:, 1] - point[1]) - (b[:, 1] - point[1]) * (c[:, 0] - point[0])) / turn
    two = ((c[:, 0] - point[0]) * (a[:, 1] - point[1]) - (c[:, 1] - point[1]) * (a[:, 0] - point[0])) / turn
    inside = up & (one >= -1e-7) & (two >= -1e-7) & (one + two <= 1 + 1e-7)
    return sorted({round(float(value), 3) for value in (one * a[:, 2] + two * b[:, 2] + (1 - one - two) * c[:, 2])[inside]})  # a point on an edge is under both faces


def near(floor, point, height, within):
    """The highest floor over `point` no further than `within` from `height`, or None."""
    found = [value for value in heights(floor, point) if abs(value - height) <= within]
    return found[-1] if found else None


def room(floor, point, height, within, reach=ROOM):
    """Whether a creature stands at `point` on the floor at `height`: floor there and `reach` away every way, in the tile."""
    for step in range(8):
        other = np.asarray(point) + reach * np.array([math.cos(step * math.pi / 4), math.sin(step * math.pi / 4)])
        if max(abs(other)) > 5 or near(floor, other, height, within) is None:
            return False
    return near(floor, point, height, within) is not None


def suspects(corners, faces, placed):
    """The edges (corner number pairs) `floors` finds at fault: met in pieces, pinched, or of a face held twice."""
    found = {edge for pair in floors.pieced(corners, faces, placed) for edge in pair} | set(floors.pinched(corners, faces))
    for face in floors.doubled(corners, faces):
        found |= {tuple(sorted((face[j], face[(j + 1) % 3]))) for j in range(3)}
    return sorted(found)


def edge_crossings(floor, placed, edges):
    """[{edge, t, a, b}]: across each edge at its middle (and its quarters, when it is longer than 1.2 m), from a point
    with room on one side (a: [[x, y], z]) to one on the other (b), as far from the edge as there is room for."""
    found = []
    for one, two in edges:
        p, q = placed[one], placed[two]; length = math.hypot(*(q - p)[:2])
        if length < .1:
            continue
        across = np.array([p[1] - q[1], q[0] - p[0]]) / length
        for t in ((.5,) if length < 1.2 else (.25, .5, .75)):
            middle = p + t * (q - p); height = float(middle[2]); ends = []
            for sign in (1, -1):
                end = next(([point.round(3).tolist(), round(near(floor, point, height, within), 3)] for within in LEVEL for off in OFF
                            for point in [middle[:2] + sign * off * across]
                            if max(abs(point)) < EDGE and room(floor, point, height, within, ROOM if off > .4 else .25)), None)
                ends.append(end)
            if all(ends):
                found.append({'edge': [p.round(3).tolist(), q.round(3).tolist()], 't': t, 'a': ends[0], 'b': ends[1]})
    return found


def turned(point, turn):
    """A point of the area, relative to a laid tile's middle, in the tile's own space when the tile is laid at `turn`."""
    cos, sin = TURNS[turn]
    return np.array([cos * point[0] + sin * point[1], -sin * point[0] + cos * point[1]])


def side_crossings(floor, others):
    """([{edge, t, a, b}], {(dx, dy): [number, turn, model]}): across each of the tile's sides into the tile of `others`
    ({model: (number, floor)}) whose floor is level with it there at the most places, a point 1.4 m in from the side
    to one 1.4 m into the neighbour, at up to five places along the side."""
    found, beside = [], {}
    for step in TURNS:
        out = np.array(step, dtype=float); along = np.array([-out[1], out[0]]); level = {}
        for at in (value * .5 for value in range(-9, 10)):
            inner = 3.6 * out + at * along; under = heights(floor, inner)
            if under and room(floor, inner, under[-1], LEVEL[0]):
                edge = near(floor, 4.9 * out + at * along, under[-1], LEVEL[0])
                if edge is not None:
                    level[at] = edge
        best = (0, None, [])
        for model, (number, other) in sorted(others.items()):
            if not len(other) or abs(np.abs(other.reshape(-1, 3)[:, :2]).max() - 5) > 1e-3:
                continue  # a neighbour's floor reaches its sides
            for turn in range(4):
                fits = [at for at, height in level.items()
                        if all(near(other, turned(off * out + at * along, turn), height, .1) is not None for off in (-4.97, -4.6, -4, -3.4))
                        and room(other, turned(-3.6 * out + at * along, turn), height, .1, .4)]
                if len(fits) > best[0]:
                    best = (len(fits), [number, turn, model], fits)
        if not best[0]:
            continue
        beside[step] = best[1]; fits = best[2][::-(-len(best[2]) // 5)]
        for at in fits:
            height = level[at]; inner = 3.6 * out + at * along; outer = 6.4 * out + at * along
            found.append({'edge': [(5 * out + (at - .3) * along).round(3).tolist() + [height], (5 * out + (at + .3) * along).round(3).tolist() + [height]], 't': .5,
                          'a': [inner.round(3).tolist(), round(near(floor, inner, height, LEVEL[0]), 3)], 'b': [outer.round(3).tolist(), round(height, 3)]})
    return found, beside


def plan(models, set_text, wok_text, *, sides=False):
    """{model: {number, crossings, beside}} for the tiles `models` of a set: the crossings of their suspect edges and,
    with `sides`, of their sides. wok_text(model) is the text of a model's .wok, or None where it has none."""
    numbers = {}
    for tile in inventory.read_set(set_text)['tiles']:
        numbers.setdefault(tile['model'], tile['number'])
    lacking = [model for model in models if model not in numbers]; require(not lacking, 'Not tiles of the set: ' + ', '.join(lacking))
    cache = {}

    def floor_of(model):
        if model not in cache:
            text = wok_text(model)
            cache[model] = None if text is None else triangles(*load(text))
        return cache[model]
    found = {}
    for model in models:
        text = wok_text(model); require(text is not None, f'{model} has no .wok to walk')
        corners, faces, placed = load(text); floor = triangles(corners, faces, placed)
        crossings, beside = edge_crossings(floor, placed, suspects(corners, faces, placed)), {}
        if sides:
            others = {other: (number, floor_of(other)) for other, number in numbers.items() if other != model and floor_of(other) is not None}
            more, beside = side_crossings(floor, others); crossings += more
        found[model] = {'number': numbers[model], 'crossings': crossings, 'beside': [[list(step), held] for step, held in beside.items()]}
    return found


def layout(found, fill, columns=COLUMNS):
    """(width, height, laid, walkers): each tile of a plan laid twice, unturned, three cells apart with its neighbours
    about it, on the `fill` tile. walkers: [{tag, appearance, legs: [[crossing, way, [x, y, z]]]}], the way `to` the
    crossing's first point, `ab` across and `ba` back, in the area's own metres."""
    count = len([model for model, one in found.items() if one['crossings']]) * len(WALKERS); rows = -(-count // columns)
    width, height = columns * 3 + 2, rows * 3 + 2; laid = {(column, row): (fill, 0) for column in range(width) for row in range(height)}; walkers = []
    for model, one in found.items():
        if not one['crossings']:
            continue
        for who, appearance in WALKERS.items():
            index = len(walkers); column, row = 2 + 3 * (index % columns), 2 + 3 * (index // columns)
            laid[(column, row)] = (one['number'], 0)
            for (dx, dy), (number, turn, _) in one['beside']:
                laid[(column + dx, row + dy)] = (number, turn)
            middle = (column * 10 + 5, row * 10 + 5)
            at = lambda end: [round(middle[0] + end[0][0], 3), round(middle[1] + end[0][1], 3), end[1]]
            legs = [leg for number, crossing in enumerate(one['crossings'])
                    for leg in ([number, 'to', at(crossing['a'])], [number, 'ab', at(crossing['b'])], [number, 'ba', at(crossing['a'])])]
            walkers.append({'tag': f'{model}.{who}', 'appearance': appearance, 'legs': legs})
    return width, height, laid, walkers


def seconds(walkers):
    """How long the longest walk is given, from the walkers' start."""
    return max(len(walker['legs']) for walker in walkers) * LEG + 40.0


def script(walkers, area):
    """(functions, statement) of the walkers for review's entry script (`more`): each walker made in the area tagged
    `area` at its first point, as its appearance, sent along its legs and logging `<PREFIX> walk=<tag> leg=<n> at=x,y,z` on each arrival and
    `trace=x,y,z` four times a second."""
    at = 'FloatToString(v.x,7,2)+","+FloatToString(v.y,7,2)+","+FloatToString(v.z,6,2)'
    lines = [f'void Arrived(string who,int n) {{ vector v=GetPosition(OBJECT_SELF); WriteTimestampedLogEntry("{PREFIX} walk="+who+" leg="+IntToString(n)+" at="+{at}); }}',
             'void Go(string who,int n,float x,float y,float z) { ActionMoveToLocation(Location(GetArea(OBJECT_SELF),Vector(x,y,z),0.0),FALSE); ActionDoCommand(Arrived(who,n)); ActionWait(0.3); }',
             f'void Trace(string who,int n) {{ vector v=GetPosition(OBJECT_SELF); WriteTimestampedLogEntry("{PREFIX} walk="+who+" trace="+{at}); if(n>0) DelayCommand({TICK},Trace(who,n-1)); }}',
             'object Make(object a,float x,float y,float z,int app) { object c=CreateObject(OBJECT_TYPE_CREATURE,"nw_bandit001",Location(a,Vector(x,y,z),0.0)); '
             'ChangeToStandardFaction(c,STANDARD_FACTION_COMMONER); SetCreatureAppearanceType(c,app); AssignCommand(c,ClearAllActions(TRUE)); return c; }']
    calls = []
    for index, walker in enumerate(walkers):
        tag, legs = walker['tag'], walker['legs']; (x, y, z) = legs[0][2]; ticks = int(len(legs) * LEG / TICK) + 60
        body = [f'void W{index}() {{ object c=Make(GetObjectByTag("{area}"),{x:.3f},{y:.3f},{z:.3f},{walker["appearance"]}); '
                f'WriteTimestampedLogEntry("{PREFIX} walk={tag} made="+IntToString(GetIsObjectValid(c))+" app="+IntToString(GetAppearanceType(c))); '
                f'AssignCommand(c,DelayCommand(3.5,Trace("{tag}",{ticks})));']
        body += [f'  AssignCommand(c,DelayCommand({4 + number * .1:.1f},Go("{tag}",{number},{x:.3f},{y:.3f},{z:.3f})));' for number, (_, _, (x, y, z)) in enumerate(legs)]
        lines.append('\n'.join(body) + ' }'); calls.append(f'  DelayCommand({index * .2:.1f},W{index}());')
    lines.append('void Walk() {\n' + '\n'.join(calls) + '\n}')
    return '\n'.join(lines), f'DelayCommand({START:.1f},Walk());'


def _point(text):
    return [float(value) for value in text.replace(' ', '').split(',')]


def _strayed(point, start, goal):
    length = math.dist(start[:2], goal[:2])
    return abs((goal[0] - start[0]) * (point[1] - start[1]) - (goal[1] - start[1]) * (point[0] - start[0])) / length if length else math.dist(point[:2], start[:2])


def verdict(lines, walkers):
    """What a walk's log says: {walked, bent, short, missing, unmade}. walked: [{tag, crossing, way, off, strayed,
    longer}] for every leg across, `off` the metres the walker stopped from its goal, `strayed` the furthest its route
    went from the straight line, `longer` its length over the straight line's; bent and short name those over BENT and
    SHORT; missing the legs a walker never logged (it did not arrive), unmade the walkers the game did not make as asked."""
    from tools.armorkit import client
    events = {}
    for values in map(client.parse_line, lines):
        if 'walk' in values:
            events.setdefault(values['walk'].strip(), []).append(values)
    walked, missing, unmade = [], [], []
    for walker in walkers:
        tag, legs = walker['tag'], walker['legs']; path, done = [], set(); made = [values for values in events.get(tag, []) if 'made' in values]
        if not made or made[0]['made'].strip() != '1' or int(made[0].get('app', '-1')) != walker['appearance']:
            unmade.append(tag)
        for values in events.get(tag, []):
            if 'trace' in values:
                path.append(_point(values['trace']))
            elif 'leg' in values and int(values['leg']) not in done:
                number = int(values['leg']); done.add(number); crossing, way, goal = legs[number]; point = _point(values['at'])
                if way != 'to':
                    start = legs[number - 1][2]; route = path + [point]; straight = math.dist(start[:2], goal[:2])
                    walked.append({'tag': tag, 'crossing': crossing, 'way': way, 'off': round(math.dist(point[:2], goal[:2]), 3),
                                   'strayed': round(max(_strayed(one, start, goal) for one in route), 3),
                                   'longer': round(sum(math.dist(one[:2], two[:2]) for one, two in zip(route, route[1:])) / straight, 3) if straight else None})
                path = [point]
        missing += [{'tag': tag, 'crossing': legs[number][0], 'way': legs[number][1]} for number in range(len(legs)) if number not in done]
    return {'walked': walked, 'bent': [one for one in walked if one['strayed'] > BENT], 'short': [one for one in walked if one['off'] > SHORT],
            'missing': missing, 'unmade': unmade}


def woks(repo, overlay=None):
    """{model: path of its .wok}: the packs' (srn_t_*), and an overlay's over them."""
    found = {path.stem.lower(): path for path in sorted(Path(repo).glob('srn_t_*/*.wok'))}
    if overlay:
        found.update((path.stem.lower(), path) for path in Path(overlay).glob('*.wok'))
    return found


def packs(repo, models):
    """The tile packs (srn_t_*) whose models these are, in order of first use."""
    found = []
    for model in models:
        held = sorted(path.parent.name for path in Path(repo).glob(f'srn_t_*/{model}.mdl'))
        require(len(held) == 1, f'{model} is in {len(held)} tile packs, not one: ' + ', '.join(held))
        if held[0] not in found:
            found.append(held[0])
    return found
