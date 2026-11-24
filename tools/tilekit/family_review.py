"""Client views of a family of a tileset's tiles, laid to suit what is judged. `review` lays the whole set or a block as a
builder paints it; here a spec names the tiles and the views, so a run stays a handful of views:
{tileset, fill, haks, layouts: [{kind, name, lights, ...}]}

Each layout is an area for each of its `lights` (default: day and night), `name` (letters, unique) naming its areas:
- `tiles`: tiles apart on plain ground. {models or terrains (patterns), placements (a placement spec, for what is on
  them), space, across, room, glass (material patterns), views: [{kind, lights, every, also, only}]}. View kinds:
  `facade` (the wall with the most windows, or the glass), `wall` (the wall with street pieces), `roof` (from its
  highest walkable floor), `up` (at its top from the street), `glass` (straight at its largest glass). `every` n-th
  tile is taken, and those with one of the pieces `also`; `only` the tiles with one of those pieces.
- `block`: terrains painted by the set's rules: {width, height, patches, runs, ground} as a review's block, {crossings,
  views (of them, as 'x03y03-ne'), distance, pitch} its views.
- `street`: kerbed tiles, all their corners of the terrains, side by side as a street shows them: {terrains, placements, across, down}, seen from two
  sides; `close`: [{piece, light}] a near view of the first tile with that piece.
- `towers`: whole buildings painted by the set's rules: {terrains (one may be named twice), size, apart, room, across,
  ground, views: [{kind: side, sides, lights} | {kind: up, lights, back, pitch} | {kind: far, lights}]}.
- `doors`: door hooks (`openings` wrote them): {hooks (its file), models, clear ([[width, height]] left out), doors:
  {model: row of genericdoors.2da}, opened, turns: {model: degrees}}. Each hook is seen from its walkable side, with
  its door shut and opened where it has one."""
import fnmatch
import json
import math
from pathlib import Path

from . import detail, effects, geometry, inventory, merged, placer, require, review

LIGHTS = ('day', 'night')
MOST = 24  # views of a run unless more are asked for
WALL_PIECES = {'canopy', 'camera', 'ledge'}
SIDES = {'w': (-1, 0, 0), 'e': (1, 0, 180), 's': (0, -1, 90), 'n': (0, 1, 270)}
LARGEST = 32  # tiles an area is across at most
VIEWS = {'facade': (9.0, 14.0, 80.0, 7.0), 'wall': (10.0, 16.0, 82.0, 5.0), 'up': (35.0, 3.0, 128.0, 1.8), 'glass': (5.0, 14.0, 74.0, 2.0)}  # stood off, distance, pitch, height


def _is(name, patterns):
    return any(fnmatch.fnmatchcase((name or '').lower(), pattern.lower()) for pattern in patterns)


def _toward(facing):
    """The facing (degrees) of a camera looking at a wall that faces `facing`."""
    return round(math.degrees(math.atan2(-facing[1], -facing[0]))) % 360


def _short(name, tileset):
    return name[len(tileset) + 1:] if name.startswith(tileset + '_') else name


def texts_of(repo, tileset, overlay, names):
    """{model: text} of the uncompiled models a tileset draws, the overlay's first, with those of `names` it alone has (a
    copied terrain's)."""
    found = {name: text for name, _, text, _, _ in inventory.drawn_copies(repo, tileset, overlay, merged.packs(repo, tileset))}
    for name in names if overlay else ():
        path = Path(overlay) / f'{name}.mdl'
        if name not in found and path.is_file() and not inventory.compiled(data := path.read_bytes()):
            found[name] = data.decode('cp1252')
    return found


class Set:
    """What the layouts need of a tileset: its set file, its tiles' texts, read once."""

    def __init__(self, repo, tileset, overlay, fill, base):
        self.repo, self.tileset, self.base = Path(repo), tileset, Path(base)
        path = Path(overlay) / f'{tileset}.set' if overlay else None
        path = path if path and path.is_file() else self.repo / f'srn_t_{tileset}' / f'{tileset}.set'
        self.laid = inventory.read_set(path.read_bytes().decode('cp1252')); self.tiles = {tile['number']: tile for tile in self.laid['tiles']}
        self.fill = review.plain(self.laid) if fill is None else fill; self.overlay, self._texts = overlay, None
        require(self.fill in self.tiles, f'The fill tile {self.fill} is no tile of {tileset}'); self.numbers = {}
        for tile in self.laid['tiles']:
            self.numbers.setdefault(tile['model'], tile['number'])

    @property
    def texts(self):
        if self._texts is None:
            self._texts = texts_of(self.repo, self.tileset, self.overlay, self.numbers)
        return self._texts

    def json(self, path):
        path = Path(path)
        return json.loads((path if path.is_absolute() else self.base / path).read_text(encoding='utf-8-sig'))

    def nodes(self, name):
        require(name in self.texts, f'No uncompiled model of {self.tileset} is {name}')
        return geometry.parse(effects.without_fx(detail.without_kit(self.texts[name])))[2]

    def chosen(self, layout):
        """The models of a layout, in order: named, or every one outside envkit with one of the terrains at a corner."""
        if 'models' in layout:
            names = [name.lower() for name in layout['models']]; missing = sorted(set(names) - set(self.numbers))
            require(not missing, f'No tile of {self.tileset} is ' + ', '.join(missing)); return names
        require(layout.get('terrains'), f'The layout {layout["name"]} names its models or its terrains')
        every = all if layout['kind'] == 'street' else any
        names = sorted({tile['model'] for tile in self.laid['tiles'] if not tile['model'].startswith('ek_') and every(_is(corner, layout['terrains']) for corner in tile['corners'])})
        require(names, 'No tile has the terrains ' + ', '.join(layout['terrains'])); return names


def _area(of, tag, title, width, height, cells, light, **more):
    require(width <= LARGEST and height <= LARGEST, f'{title}: {width} x {height} tiles is more than an area holds ({LARGEST})')
    return {'tag': tag, 'title': title, 'tileset': of.tileset, 'width': width, 'height': height, 'laid': cells, 'light': light, **more}


def _filled(of, width, height):
    return {(column, row): (of.fill, 0) for column in range(width) for row in range(height)}


def wall_facing(placements):
    """The way the tile's wall with street pieces faces, or None."""
    walls = [one for one in placements if one['piece'] in WALL_PIECES]
    if not walls:
        return None
    x, y, _ = walls[0]['at']
    return (int(math.copysign(1, x)), 0) if abs(x) >= abs(y) else (0, int(math.copysign(1, y)))


def largest_glass(nodes, materials):
    """(x, y, facing) of the widest upright face drawn with `materials`, or None."""
    moves, best = geometry.placed(nodes), None
    for node in nodes:
        for face in node.faces if node.rendered and _is(node.material, materials) else ():
            points = [moves[id(node)](node.verts[corner]) for corner in face[:3]]; facing = placer._facing(points)
            if facing and abs(facing[0]) + abs(facing[1]) == 1:
                span = sum(max(point[axis] for point in points) - min(point[axis] for point in points) for axis in (0, 1))
                if best is None or span > best[0]:
                    best = (span, sum(point[0] for point in points) / 3, sum(point[1] for point in points) / 3, facing)
    return best and best[1:]


def _tile_view(of, kind, name, placements, layout):
    """(x, y, facing, distance, pitch, height) of one view of a tile, from its middle, or None where it has none."""
    require(kind in (*VIEWS, 'roof'), 'A view of a tile is ' + ', '.join((*VIEWS, 'roof')))
    if kind in ('wall', 'up'):
        facing = wall_facing(placements) or ((-1, 0) if kind == 'up' else None)
        if facing is None:
            return None
        off, distance, pitch, height = VIEWS[kind]; return facing[0] * off, facing[1] * off, _toward(facing), distance, pitch, height
    nodes = of.nodes(name)
    if kind == 'glass':
        require(layout.get('glass'), 'A glass view needs the layout\'s glass materials'); found = largest_glass(nodes, layout['glass'])
        if found is None:
            return None
        x, y, facing = found; off, distance, pitch, height = VIEWS[kind]; return x + facing[0] * off, y + facing[1] * off, _toward(facing), distance, pitch, height
    walls = placer.windows(nodes); facing = max(walls, key=lambda one: len(walls[one])) if walls else (-1, 0); fx, fy = facing
    if kind == 'facade':
        off, distance, pitch, height = VIEWS[kind]; return fx * off, fy * off, _toward(facing), distance, pitch, height
    roof = max((height for heights in geometry.walkable(nodes).values() for height in heights), default=0.0)
    return (fx * 3.8 - fy * 3.8, fy * 3.8 + fx * 3.8, _toward(facing), 12.0, 52.0, 1.0) if roof > geometry.HEAD else None


def tiles(of, layout):
    names = of.chosen(layout); space, across, room = layout.get('space', 5), layout.get('across', 5), layout.get('room', 4)
    placements = {name.lower(): them for name, them in of.json(layout['placements'])['tiles'].items()} if 'placements' in layout else {}
    views = layout.get('views', [{'kind': 'facade'}]); across = min(across, (LARGEST - 1 - 2 * room) // space + 1); down = (LARGEST - 1 - 2 * room) // space + 1
    require(across > 0, 'These tiles do not fit an area: less space or room'); pages = [names[start:start + across * down] for start in range(0, len(names), across * down)]
    require(len(pages) <= 9, 'More tiles than nine areas hold: name fewer'); areas, shots, made = [], [], {}
    for light in layout.get('lights', LIGHTS):
        for page, group in enumerate(pages):
            rows = -(-len(group) // across); width, height = space * (min(len(group), across) - 1) + 1 + 2 * room, space * (rows - 1) + 1 + 2 * room
            cells = _filled(of, width, height); tag = f'{layout["name"]}{light[0]}{page or ""}'; taken = []
            for index, name in enumerate(group):
                column, row = space * (index % across) + room, space * (index // across) + room; cells[column, row] = (of.numbers[name], 0); pieces = {one['piece'] for one in placements.get(name, ())}
                for view in views:
                    if light not in view.get('lights', layout.get('lights', LIGHTS)) or 'only' in view and not pieces & set(view['only']):
                        continue
                    if (page * across * down + index) % view.get('every', 1) and not pieces & set(view.get('also', ())):
                        continue
                    if (view['kind'], name) not in made:
                        made[view['kind'], name] = _tile_view(of, view['kind'], name, placements.get(name, []), layout)
                    seen = made[view['kind'], name]
                    if seen:
                        x, y, facing, distance, pitch, up = seen
                        taken.append({**review._shot(tag, f'{light}-{_short(name, of.tileset)}-{view["kind"]}', (column + 0.5) * review.TILE + x, (row + 0.5) * review.TILE + y, facing, distance, pitch), 'height': up})
            if taken:
                areas.append(_area(of, tag, f'{layout["name"]}, {light}', width, height, cells, light)); shots += taken
    return areas, shots


def street(of, layout):
    across, down = layout.get('across', 4), layout.get('down', 3); spec = {name.lower(): them for name, them in of.json(layout['placements'])['tiles'].items()} if 'placements' in layout else {}
    kerbed = [name for name in of.chosen(layout) if name in of.texts and placer._kerbs(geometry.parse(of.texts[name])[2])]
    require(kerbed, 'None of these tiles has a kerb'); block = kerbed[::max(1, len(kerbed) // (across * down))][:across * down]; areas, shots = [], []
    width, height = across + 2, down + 2; middle = (width * review.TILE / 2, height * review.TILE / 2)
    for light in layout.get('lights', ('day',)):
        cells = _filled(of, width, height); tag = f'{layout["name"]}{light[0]}'
        for index, name in enumerate(block):
            cells[1 + index % across, 1 + index // across] = (of.numbers[name], 0)
        areas.append(_area(of, tag, f'{layout["name"]}, {light}', width, height, cells, light))
        shots += [review._shot(tag, f'{light}-{layout["name"]}-{side}', *middle, look, 34.0, 50.0) for side, look in (('south', 90), ('north', 270))]
    for number, close in enumerate(layout.get('close', ())):
        name = next((name for name, them in spec.items() if name in of.numbers and any(one['piece'] == close['piece'] for one in them)), None)
        require(name, f'No placed tile has a {close["piece"]}'); at = next(one['at'] for one in spec[name] if one['piece'] == close['piece'])
        cells = _filled(of, 3, 3); cells[1, 1] = (of.numbers[name], 0); tag = f'{layout["name"]}c{number}'
        areas.append(_area(of, tag, f'{layout["name"]}, {close["piece"]}', 3, 3, cells, close['light']))
        shots.append(review._shot(tag, f'{close["light"]}-{_short(name, of.tileset)}-{close["piece"]}', 15 + at[0], 15 + at[1], 90, 6.0, 65.0))
    return areas, shots


def _loose(of):
    """The tiles no painted layout lays: those of groups, and envkit's."""
    return {number for group in of.laid['groups'] for number in group['tiles']} | {number for number, tile in of.tiles.items() if tile['model'].startswith('ek_')}


def block(of, layout):
    width, height = layout['width'], layout['height']; require(max(width, height) <= LARGEST, f'{layout["name"]}: {width} x {height} tiles is more than an area holds ({LARGEST})'); areas, shots = [], []
    cells = review.solve(of.tiles, layout.get('ground', of.laid['default']), width, height, layout['patches'], layout.get('runs', ()), avoid=_loose(of)); views = layout.get('views')
    for light in layout.get('lights', LIGHTS):
        tag = f'{layout["name"]}{light[0]}'; areas.append(_area(of, tag, f'{layout["name"]}, {light}', width, height, cells, light))
        made = review.corner_shots(tag, f'{light}-{layout["name"]}', [tuple(cell) for cell in layout['crossings']], distance=layout.get('distance', 34.0), pitch=layout.get('pitch', 58.0))
        shots += [shot for shot in made if not views or '-'.join(shot['label'].rsplit('-', 2)[-2:]) in views]
    return areas, shots


def towers(of, layout):
    terrains, size, apart, room = layout['terrains'], layout.get('size', 4), layout.get('apart', 8), layout.get('room', 3)  # corners a side, corners between, empty tiles round the edge
    across = min(layout.get('across', 3), len(terrains)); rows = -(-len(terrains) // across); width, height = room * 2 + apart * (across - 1) + size, room * 2 + apart * (rows - 1) + size
    patches = [{'terrain': terrain, 'at': [room + apart * (index % across), room + apart * (index // across)], 'size': [size, size]} for index, terrain in enumerate(terrains)]
    require(max(width, height) <= LARGEST, f'{layout["name"]}: {width} x {height} tiles is more than an area holds ({LARGEST})')
    cells = review.solve(of.tiles, layout.get('ground', of.laid['default']), width, height, patches, avoid=_loose(of)); areas, shots = [], []
    for light in layout.get('lights', LIGHTS):
        tag = f'{layout["name"]}{light[0]}'; taken = []
        for number, patch in enumerate(patches):
            x, y = ((corner + size / 2) * review.TILE for corner in patch['at']); half = (size / 2 + 0.5) * review.TILE; label = f'{light}-{number}{patch["terrain"].lower()}'
            for view in layout.get('views', [{'kind': 'side'}, {'kind': 'up'}]):
                require(view['kind'] in ('side', 'up', 'far'), 'A view of a tower is side, up, far')
                if light not in view.get('lights', layout.get('lights', LIGHTS)):
                    continue
                if view['kind'] == 'side':
                    for side in view.get('sides', tuple(SIDES)):
                        dx, dy, look = SIDES[side]; taken.append({**review._shot(tag, f'{label}-{side}', x + dx * (half + 8.0), y + dy * (half + 8.0), look, 16.0, 82.0), 'height': 5.0})
                elif view['kind'] == 'up':
                    taken.append({**review._shot(tag, f'{label}-up', x - half - view.get('back', 25.0), y, 0, 3.0, view.get('pitch', 105.0)), 'height': 1.8})
                else:
                    taken.append({**review._shot(tag, f'{label}-far', x - half - 45.0, y - half - 45.0, 45, 4.0, 108.0), 'height': 1.8})
        if taken:
            areas.append(_area(of, tag, f'{layout["name"]}, {light}', width, height, cells, light)); shots += taken
    return areas, shots


def door_side(nodes, at, normal):
    """1 or -1: the side of a door a player stands on, at its height; past the tile is the plain ground beside it."""
    walk = geometry.walkable(nodes); x, y, z = at
    for side in (1, -1):
        point = (x + side * normal[0] * 2.0, y + side * normal[1] * 2.0)
        if max(abs(point[0]), abs(point[1])) > geometry.HALF or any(abs(height - z) < 0.6 for height in walk.get(geometry.cell(point), ())):
            return side
    return 1


def doors(of, layout):
    hooks = [one for one in of.json(layout['hooks'])['hooks'] if 'note' not in one]; clear = {tuple(one) for one in layout.get('clear', ())}
    wanted = [name.lower() for name in layout['models']] if 'models' in layout else None; stood, turns = ({name.lower(): value for name, value in layout.get(key, {}).items()} for key in ('doors', 'turns'))
    hooks = [one for one in hooks if (wanted is None or one['model'] in wanted) and (one['width'], one['height']) not in clear]
    missing = sorted(set(wanted or ()) - {one['model'] for one in hooks}); require(not missing, 'No measured hook is of ' + ', '.join(missing)); require(hooks, 'No door hook to look at')
    numbers = sorted({one['tile'] for one in hooks}); laid = [of.fill, *(value for number in numbers for value in (number, of.fill))]
    unknown = sorted((set(stood) | set(turns)) - {one['model'] for one in hooks}); require(not unknown, 'No measured hook, to stand or turn a door at, is of ' + ', '.join(unknown))
    opened = list(layout.get('opened', (0, 1))) if stood else [None]; areas, shots = [], []
    for light in layout.get('lights', ('day',)):
        width, height, cells, _ = review.grid(laid * len(opened), of.fill, across=len(laid)) if len(laid) <= LARGEST else (0, 0, None, 0)
        require(cells, f'{len(numbers)} tiles do not stand apart in a row: name fewer models'); tag = f'{layout["name"]}{light[0]}'; leaves = []
        for which, state in enumerate(opened):
            for one in hooks:
                x0, y0 = laid.index(one['tile']) * review.TILE + 5, (which * 2 + 1) * review.TILE + 5; (x, y, z), turn = one['at'], turns.get(one['model'], one['turn'])
                normal = (-math.sin(math.radians(turn)), math.cos(math.radians(turn))); side = door_side(of.nodes(one['model']), (x, y, z), normal)
                if one['model'] in stood:
                    leaves.append({'row': stood[one['model']], 'position': (x0 + x, y0 + y, z), 'bearing': turn, 'opened': state})
                off = side * min(9.5, max(7.0, 5.0 + (one['width'] or 0) * 0.6))  # on the plain tile beside it
                look = math.degrees(math.atan2(-side * normal[1], -side * normal[0])) % 360
                label = f'{light}-t{one["tile"]}-d{one["door"]}' + ('' if state is None else '-open' if state else '-shut')
                shots.append({**review._shot(tag, label, x0 + x + normal[0] * off, y0 + y + normal[1] * off, round(look, 1), 4.0, 84.0), 'height': round(z + 1.6, 2)})
        areas.append(_area(of, tag, f'{layout["name"]}, {light}', width, height, cells, light, **({'doors': leaves} if leaves else {})))
    return areas, shots


KINDS = {'tiles': tiles, 'block': block, 'street': street, 'towers': towers, 'doors': doors}


def plan(repo, spec, *, overlay=None, base='.', views=None, most=MOST):
    """(areas, shots, views left out) of a family review spec, whose files are named relative to `base`. At most `most`
    views (None: all) are taken, evenly through those asked for; `views`: only those whose label begins so."""
    require(isinstance(spec, dict) and spec.get('tileset') and spec.get('layouts'), 'A family review names its tileset and its layouts')
    of = Set(repo, spec['tileset'].lower(), overlay, spec.get('fill'), base); areas, shots = [], []
    for layout in spec['layouts']:
        require(layout.get('kind') in KINDS, 'A layout is ' + ', '.join(KINDS)); require(str(layout.get('name', '')).isalpha() and layout['name'].islower() and len(layout['name']) <= 8, 'A layout\'s name is 1 to 8 lowercase letters')
        unlit = sorted(set(layout.get('lights', LIGHTS)) - set(review.LIGHTS)); require(not unlit, 'A layout is lit by ' + ', '.join(review.LIGHTS))
        for area in (made := KINDS[layout['kind']](of, layout))[0]:
            require(area['tag'] not in {one['tag'] for one in areas}, f'Two areas would be named {area["tag"]}: another name for a layout'); areas.append(area)
        shots += made[1]
    sizes = {area['tag']: (area['width'] * review.TILE, area['height'] * review.TILE) for area in areas}
    outside = [shot['label'] for shot in shots if not all(0 < at < size for at, size in zip(shot['stand'], sizes[shot['area']]))]
    require(not outside, 'These views stand outside their area (give the layout more room): ' + ', '.join(outside[:4]))
    if views:
        shots = [shot for shot in shots if shot['label'].startswith(tuple(views))]
    require(shots, 'No view to take'); kept = shots if most is None or len(shots) <= most else [shots[index * len(shots) // most] for index in range(most)]
    tags = {shot['area'] for shot in kept}
    return [area for area in areas if area['tag'] in tags], kept, [shot['label'] for shot in shots if shot not in kept]


def haks(spec):
    """The packs the module loads (the spec's, or review's), with the tileset's own among them."""
    found = tuple(spec.get('haks', review.HAKS)); pack = f'srn_t_{spec["tileset"].lower()}'
    require(pack in found, f'The module would not load {pack}: add it to the spec\'s haks'); return found


def run(repo, spec, out, name, game, built, *, overlay=None, base='.', views=None, most=MOST, start=True):
    """Build the review into the fresh folder `out` and capture its views. Returns what was done."""
    areas, shots, left = plan(repo, spec, overlay=overlay, base=base, views=views, most=most)
    record = review.build(name, areas, shots, out, game, built, overlay=overlay, haks=haks(spec))
    told = {'module': record['module'], 'areas': [area['tag'] for area in areas], 'views': len(shots), 'leftOut': left, 'overlay': record['overlay']}
    if start:
        told.update(review.capture(game, record, out)); told['captures'] = len(told['captures']); told['sheets'] = review.sheets(out)
    return told
