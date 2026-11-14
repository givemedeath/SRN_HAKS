"""Checks of a sheet's work in the game client, each in a throwaway module and user folder (`prop_fixture`).

`props` stands converted props in a row and looks at each from the front, the back and the side, by day or by night,
with a figure beside it for scale and one behind it to be seen through anything see-through. `lights` stands the lit
props of a game set as the pack holds them, by night, and puts their lights out and on again by script. `group` lays
a built tile group in an area of one of its tilesets and looks at it from the front, at its door, and along and over
its sides; its `near` mode frees the player with the client hiding upper storeys near the character, its `night` mode
puts the group's lights out for everyone and on again, and its `walk` mode sends walkers across the area to the door,
round the building and into any yard with few ways in, and refuses the group if one stops short. `doors` takes a
module saved by the Toolset with tile groups painted in it (`toolset`), gives each door the Toolset made an area
transition to a waypoint in front of the next, and logs where the player is while someone clicks the doors.

Every check waits while another game client runs and never closes it. These were one-off scripts for the Ares Depot
(2026-11-11, 2026-11-12); the layouts are worked out from each model's size, so they serve any sheet."""
import json
import math
import shutil
import subprocess
import time
from pathlib import Path

from tools.armorkit import client
from tools.armorkit.client_fixture import field, gff_float

from . import convert, prop_fixture as fixture, require, tile

FILL = {'dgt04': 0, 'udp1': 58}  # the plain tile each tileset's check area is laid with
TILE = 10.0
GAP = 6.0  # metres between props in a row
ROW = 5  # lit props to a row at most
ROW_END = 52.0  # how far along x a row of lit props may reach and still be held by its view, metres
STEP = 3.5  # how far in front of a door the player is put, metres
MAPS = ('.mtr', '.pwk', '.dds', '.txi')
REACHED = 1.0  # metres from its target a walker may stop and still have arrived
WALK_START = 5.0  # metres in from the check area's corners that walkers set out from
WALK_STAGES = 6  # shots after the one that sends the walkers, each logging where they are
WALK_HOLD = 8.0  # seconds a walk shot is held: six of them take a walker some 90 metres
AREA, MARGIN = 9, 3  # tiles across a check area at least, and of plain ground round the group on every side
DOOR_OUT = 1.2  # metres out of its door a walker is sent to


def wait_for_clients(limit=1500.0, *, running=client.running, sleep=time.sleep):
    """Wait while another session's game client runs; it is never closed."""
    deadline = time.monotonic() + limit
    while running():
        require(time.monotonic() < deadline, f'Another game client is still running after {int(limit / 60)} minutes')
        sleep(10)


def stage(built, model, resources):
    """Copy a converted model (`game`'s folder for it) into a fixture's resources. Returns its size in metres."""
    built, resources = Path(built) / model, Path(resources); resources.mkdir(parents=True, exist_ok=True)
    require((built / 'report.json').is_file(), 'No converted model at ' + str(built))
    shutil.copyfile(built / 'compiled' / f'{model}.mdl', resources / f'{model}.mdl')
    for path in (built / 'source').iterdir():
        if path.suffix in MAPS:
            shutil.copyfile(path, resources / path.name)
    return json.loads((built / 'report.json').read_text(encoding='utf-8'))['size']


def from_pack(pack, model, resources):
    """Copy a model as the pack holds it into a fixture's resources."""
    found = [path for path in Path(pack).glob(model + '*') if path.suffix in ('.mdl', *MAPS)]
    require(any(path.name == model + '.mdl' for path in found), f'{model} is not in {Path(pack).name}')
    Path(resources).mkdir(parents=True, exist_ok=True)
    for path in found:
        shutil.copyfile(path, Path(resources) / path.name)


def row_of_props(models, sizes, wanted, *, x=12.0, y=40.0):
    """(props, shots, people) for props stood in a row along x: each seen from the front, the back and the side, from
    far enough to hold it, with a figure at its front corner and one behind it. sizes: {model: [x, y, z] metres}."""
    props, shots, people = [], [], []
    for model in wanted:
        require(model in models, 'No such model in the game set: ' + model)
        size = sizes[model]; x += size[0] / 2
        props.append({'model': model, 'position': [x, y], 'static': not models[model].get('lit'), 'light': models[model].get('placeable', {}).get('light')})  # a lit prop is reached by script
        distance = max(3.5, max(size[0], size[2] + models[model].get('lift', 0.0)) * 1.5); view = {'distance': distance, 'height': 1.0}
        shots += [{'label': model + '-front', 'stand': [x, y - size[1] / 2 - 1.2], 'pitch': 76, **view},
                  {'label': model + '-back', 'stand': [x, y + size[1] / 2 + 1.2], 'facing': 270, 'pitch': 76, **view},
                  {'label': model + '-side', 'stand': [x + size[0] / 2 + 1.2, y], 'facing': 180, 'pitch': 70, **view}]
        people += [{'position': [x + size[0] / 2 + 0.8, y - size[1] / 2 - 0.3], 'facing': 270.0}, {'position': [x - 0.5, y + size[1] / 2 + 1.0], 'facing': 270.0}]
        x += size[0] / 2 + GAP
    require(x - GAP <= 78.0, 'These props do not fit one row of the check area: look at fewer at a time')
    return props, shots, people


def _fresh(base, name):
    """The resources folder of a new check `name` under `base`: a name used before is refused before anything is copied."""
    folder, resources = base / 'fixtures' / name, base / 'fixtures' / f'{name}-resources'
    require(not folder.exists() and not resources.exists(), f'A check is built into fresh folders: {name} was used before under {base / "fixtures"}; give it a new --name')
    resources.mkdir(parents=True)
    return resources


def _run(game, record, folder, **more):
    wait_for_clients(); captures = Path(folder) / 'captures'
    result = fixture.run(game, record, captures, **more)
    (captures / 'run.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    return {'captures': result['captures'], 'lines': len(result['lines'])}


def props(game, repo, base, name, models_path, built, wanted, *, night=False):
    """Converted props from `built` (the folder `game` converted into) in the client. The fixture and its captures go to
    `base/fixtures/<name>`."""
    repo, base = Path(repo).resolve(), Path(base).resolve(); models = convert.load_models(models_path)
    resources = _fresh(base, name)
    sizes = {model: stage(built, model, resources) for model in wanted}
    placed, shots, people = row_of_props(models, sizes, wanted)
    record = fixture.build(name, resources, placed, shots, base / 'fixtures' / name, game, repo / 'srn_2da/placeables.2da', people=people, night=night)
    return _run(game, record, base / 'fixtures' / name)


def lit_props(models):
    """The lit props of a game set, in the order the lights check stands and tags them."""
    return [model for model, stated in models.items() if stated.get('lit') and stated.get('placeable')]


def rows_of_lights(models, sizes, tags, halos):
    """(props, shots, people) for the lit props of a game set in rows, by night: every row with its lights on, then
    put out by script, then on again. A row holds `ROW` props at most and ends where its view does (`ROW_END`), so
    wide props stand fewer to a row. tags: {model: script expression for the placed object}; halos: the models that
    have a halo sheet."""
    lit = lit_props(models)
    require(lit, 'The game set has no lit props'); rows, x = [[]], 10.0
    for model in lit:
        if rows[-1] and (len(rows[-1]) == ROW or x + sizes[model][0] > ROW_END):
            rows.append([]); x = 10.0
        rows[-1].append(model); x += sizes[model][0] + 3.5
    require(len(rows) <= 4, 'More lit props than one check area holds: four rows at most')
    props, people = [], []
    for index, row in enumerate(rows):
        y = 62.0 - 16.0 * index; x = 10.0
        for model in row:
            size = sizes[model]; x += size[0] / 2
            props.append({'model': model, 'position': [x, y], 'static': False, 'light': models[model].get('placeable', {}).get('light')})
            people.append({'position': [x + size[0] / 2 + 0.8, y - size[1] / 2 - 0.3], 'facing': 270.0})
            x += size[0] / 2 + 3.5
    swap = lambda on: ''.join(convert.lights_script(model, tags[model], on, halo=model in halos, light=bool(models[model].get('placeable', {}).get('light'))) for model in lit)
    view = lambda index: {'stand': [28.0, 62.0 - 16.0 * index - 9.0], 'distance': 24.0, 'pitch': 62, 'height': 1.0}
    shots = []
    for stage_name, run in (('lit', None), ('out', swap(False)), ('on-again', swap(True))):
        for index in range(len(rows)):
            shots.append({'label': f'row{index}-{stage_name}', **view(index), **({'run': run} if run and index == 0 else {})})
    return props, shots, people


def lights(game, repo, base, name, models_path, built, *, pack='srn_placeable'):
    """The lit props of a game set as the pack holds them, by night: lit, put out by script, and on again. `built` (the
    folders `game` converted into, the first that holds a model serving) is read for their sizes only."""
    repo, base = Path(repo).resolve(), Path(base).resolve(); models = convert.load_models(models_path); pack = repo / pack
    lit = lit_props(models)
    resources = _fresh(base, name)
    for path in pack.glob('ek_off*'):  # the dark halo the lights-out set swaps in
        shutil.copyfile(path, resources / path.name)
    sizes = {}
    for model in lit:
        from_pack(pack, model, resources)
        reports = [Path(folder) / model / 'report.json' for folder in built if (Path(folder) / model / 'report.json').is_file()]
        require(reports, f'No converted {model} in ' + ', '.join(map(str, built)))
        sizes[model] = json.loads(reports[0].read_text(encoding='utf-8'))['size']
    tags = {model: f'GetObjectByTag("{name}_p{index}")' for index, model in enumerate(lit)}  # as `prop_fixture.build` tags them
    placed, shots, people = rows_of_lights(models, sizes, tags, {model for model in lit if (pack / f'{model}_h.mtr').is_file()})
    record = fixture.build(name, resources, placed, shots, base / 'fixtures' / name, game, repo / 'srn_2da/placeables.2da', people=people, night=True)
    return _run(game, record, base / 'fixtures' / name)


def laid_door(made):
    """The middle of the foot of a built group's door from the group's middle, (x, y), or None: from the tiles' own door
    records (`tiles`' report), each on its tile's middle. Not the game set's place of it on the model: the tiles are cut
    about what the group holds, and that need not be centred on the model's origin. The Saeder-Krupp yard's fence
    stands far out in front, and its door lay 7 metres from where the model put it (2026-11-12)."""
    found = [(one['column'], one['row'], door) for one in made['tiles'] for door in one.get('doors', [])]
    if not found:
        return None
    column, row, door = found[0]
    return [(column + 0.5 - made['columns'] / 2) * TILE + door['x'], (row + 0.5 - made['rows'] / 2) * TILE + door['y']]


def area_size(columns, rows):
    """Tiles across the square check area of a group of `columns` by `rows`: AREA, or as many as hold the group with
    MARGIN tiles of ground on every side. The rail freight depot is 8 by 8 (2026-11-13), and the area of 9 that held
    the Saeder-Krupp yard's 3 by 3 refused it."""
    return max(AREA, max(columns, rows) + 2 * MARGIN)


def walk_hold(size):
    """Seconds each walk shot is held in an area `size` tiles across: WALK_HOLD, and longer in a larger area, whose far
    corners lie further from the targets (the rail freight depot's area is 14 tiles, 2026-11-13)."""
    return WALK_HOLD * max(1.0, size / AREA)


def group_shots(columns, rows, door, mode, *, column0=3, row0=3, facing=90.0):
    """The views of a tile group laid with its south-west tile at (column0, row0): {label, stand, facing, distance,
    pitch, height}. `door` is the middle of its door's foot from the group's middle (`laid_door`), or None; `facing`
    the way out of it, in degrees. By `day` and `night` the group is seen from the front, at its door, slantwise along
    each side from just inside its edge, at two corners and from above; `near` frees the player (the first shot's `run`)
    at the door, off it, far from it and behind it."""
    hx, hy = columns * TILE / 2, rows * TILE / 2; cx, cy = column0 * TILE + hx, row0 * TILE + hy; reach = max(hx, hy)
    view = lambda label, x, y, facing, distance, pitch, height=2.2: {'label': label, 'stand': [cx + x, cy + y], 'facing': facing, 'distance': distance, 'pitch': pitch, 'height': height}
    front = view('front', 0.0, hy, 270, 2.5 * reach, 62, 1.5)
    out = math.radians(facing); step = [round(2.2 * math.cos(out), 6), round(2.2 * math.sin(out), 6)]
    at_door = [view('door', door[0] + step[0], door[1] + step[1], (facing + 180.0) % 360.0, 12.0, 66, 1.5)] if door is not None else []
    if mode == 'near':
        free = 'SetCutsceneMode(pc,FALSE); ExploreAreaForPlayer(GetArea(pc),pc,TRUE);'
        shots = [*at_door, {**front, 'label': 'near-front'}, view('near-side', hx - 2.0, 0.0, 180, 2.0 * reach, 60, 1.5),
                 view('far', 0.0, hy + 2.5 * TILE, 270, 2.0 * reach, 70, 1.5), view('behind', 0.0, hy, 90, 2.1 * reach, 55, 1.5),
                 view('behind-side', hx - 2.0, 0.0, 0, 2.1 * reach, 55, 1.5)]
        shots[0] = {**shots[0], 'label': 'near-door' if at_door else shots[0]['label'], 'run': free}
        return shots
    edge_x, edge_y = hx - 2.5, hy - 5.0
    return [view('east-slant', edge_x, 2.0, 240, 9.0, 80), view('east-square', edge_x, 0.0, 180, 7.0, 82), view('east-far-slant', edge_x + 0.5, -0.4 * hy, 120, 14.0, 76),
            view('nw-corner', -edge_x, edge_y, 315, 9.0, 75), view('west-slant', -edge_x, -2.0, 60, 9.0, 80), view('south-run', -0.5 * hx, -edge_y, 80, 8.0, 78),
            view('north-run', 0.6 * hx, edge_y, 225, 7.0, 78), view('se-corner', edge_x, -edge_y, 135, 9.0, 75), front, *at_door,
            view('east-above', hx - 1.0, 0.0, 180, 1.5 * reach, 45, 1.5)]


def blackout_shots(columns, rows, lit, *, column0=3, row0=3):
    """Shots that put a group's lights out for everyone and bring them back (`convert.blackout_script`): out, seen from
    the south; still out, seen from the north; and on again there. lit: [(texture, halo)], the lit models of the group
    (`convert.lights`). The Saeder-Krupp yard's lamps and screens were put out so, 2026-11-12."""
    if not lit:
        return []
    hx, hy = columns * TILE / 2, rows * TILE / 2; cx, cy = column0 * TILE + hx, row0 * TILE + hy; reach = max(hx, hy)
    script = lambda on: ''.join(convert.blackout_script(texture, 'pc', on, halo) for texture, halo in lit)
    south = {'stand': [cx, cy - 0.5 * hy], 'facing': 90, 'distance': 2.5 * reach, 'pitch': 62, 'height': 1.5}
    north = {**south, 'stand': [cx, cy + 0.7 * hy], 'facing': 270}
    return [{**south, 'label': 'out', 'run': script(False)}, {**north, 'label': 'out-behind'}, {**north, 'label': 'lit-again', 'run': script(True)}]


def own_targets(roomy, targets, chosen):
    """Refuse a target of a walk check's own (`group`'s targets) that is not on ground with room to stand on in the
    group's walk picture (`tile.read_walk`): a walker sent into a wall or off the group would fail as if the game could
    not find its way. Nor may one take a label of the walk picture's (`chosen`, `tile.walk_targets`), the door's, or
    `pocket`'s, which brings a second walker of its own (`walk_plan`) even where the picture finds no pocket."""
    clash = sorted(set(targets) & {*chosen, 'door', 'pocket', 'pocket-near'})
    require(not clash, 'A target of your own takes a label of its own: ' + ', '.join(clash))
    step = tile.SIZE / tile.CELLS
    for label, (x, y) in targets.items():
        row, column = math.floor(y / step), math.floor(x / step)
        require(0 <= row < roomy.shape[0] and 0 <= column < roomy.shape[1] and bool(roomy[row, column]),
                f'The target {label} ({x}, {y}) is not on ground with room to stand on in {tile.WALK_PICTURE}: a walker could not arrive there')


def walk_plan(columns, rows, door, facing, targets, *, column0=3, row0=3, size=9):
    """The walkers of a group's walk check, [{label, start: [x, y], target: [x, y]}] in the check area. `targets` are
    `tile.walk_targets` (from the group's south-west corner), and DOOR_OUT in front of the door is one more (`door` from
    the group's middle, as `laid_door` gives it; `facing` the way out of it, degrees). Each gets a walker from the
    corner of the area furthest from it, four tiles away and more; walkers that share a corner stand apart along it.
    Ground a walk must go round to reach (`pocket`) gets a second walker from the middle of the next tile out, nearest
    it: a short walk into a yard has failed where long ones arrived (`tile`'s docstring)."""
    west, south = column0 * TILE, row0 * TILE; wide, high = columns * TILE, rows * TILE; goals = {}
    if door is not None:
        out = math.radians(facing)
        goals['door'] = (west + wide / 2 + door[0] + DOOR_OUT * math.cos(out), south + high / 2 + door[1] + DOOR_OUT * math.sin(out))
    goals.update({label: (west + x, south + y) for label, (x, y) in targets.items()})
    far = size * TILE - WALK_START; corners = [(WALK_START, WALK_START), (far, WALK_START), (far, far), (WALK_START, far)]
    used, walkers = {}, []

    def place(label, start, goal):
        walkers.append({'label': label, 'start': [round(start[0], 3), round(start[1], 3)], 'target': [round(goal[0], 3), round(goal[1], 3)]})
    for label, goal in goals.items():
        corner = max(corners, key=lambda one: math.dist(one, goal)); count = used.get(corner, 0); used[corner] = count + 1
        place(label, (corner[0] + 1.5 * count * (1 if corner[0] < far else -1), corner[1]), goal)
    if 'pocket' in targets:
        x, y = targets['pocket']
        side = min((x, 'west'), (wide - x, 'east'), (y, 'south'), (high - y, 'north'))[1]
        start = {'west': (-TILE / 2, y), 'east': (wide + TILE / 2, y), 'south': (x, -TILE / 2), 'north': (x, high + TILE / 2)}[side]
        place('pocket-near', (west + start[0], south + start[1]), goals['pocket'])
    return walkers


def walk_shots(columns, rows, walkers, name, *, column0=3, row0=3, size=9):
    """The shots of a walk check: one from above that sends every walker (the fixture's people, `name`_h<index>, stood at
    their starts) running to its target and logs where each is, WALK_STAGES more that log them again as they go, and
    one at each target. The Saeder-Krupp yard's four walkers were sent so, 2026-11-12. The walkers are ghosts to one
    another: the yard's first walk check sent two from one corner side by side, and the one that bumped the other gave
    up after three metres, in both tilesets (2026-11-12). A ghost still keeps to the walkmesh."""
    hx, hy = columns * TILE / 2, rows * TILE / 2
    above = {'stand': [column0 * TILE + hx, row0 * TILE + hy], 'facing': 90, 'distance': round(0.65 * size * TILE, 1), 'pitch': 25, 'height': 1.0}

    def log(stage):
        return ''.join(f'{{ vector at=GetPosition(GetObjectByTag("{name}_h{index}")); WriteTimestampedLogEntry("{fixture.LOG_PREFIX} walker={index} stage={stage} '
                       f'x="+FloatToString(at.x,7,3)+" y="+FloatToString(at.y,7,3)); }}' for index in range(len(walkers)))
    go = ''.join(f'ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectCutsceneGhost(),GetObjectByTag("{name}_h{index}"));'
                 f'AssignCommand(GetObjectByTag("{name}_h{index}"),ActionMoveToLocation(Location(GetArea(pc),Vector({one["target"][0]:.3f},{one["target"][1]:.3f},0.0),0.0),TRUE));'
                 for index, one in enumerate(walkers))
    return [{**above, 'label': 'go', 'run': go + log(0)}, *({**above, 'label': f'w{stage}', 'run': log(stage)} for stage in range(1, WALK_STAGES + 1)),
            *({'label': 'at-' + one['label'], 'stand': one['target'], 'facing': 90, 'distance': 12.0, 'pitch': 62, 'height': 1.5} for one in walkers)]


def walks(lines, walkers):
    """Where each walker of a walk check ended, read off its log: [{label, start, target, stage, at, short}], `short`
    the metres it stopped from its target. A walker the log never placed is refused: no line is no result."""
    last = {}
    for values in map(client.parse_line, lines):
        if 'walker' in values and 'stage' in values:  # FloatToString pads with spaces, which float() takes
            last[int(values['walker'])] = (int(values['stage']), float(values['x']), float(values['y']))
    found = []
    for index, one in enumerate(walkers):
        require(index in last, f'The log never placed walker {one["label"]}: did the walk shots run?')
        stage, x, y = last[index]
        found.append({**one, 'stage': stage, 'at': [x, y], 'short': round(math.dist((x, y), one['target']), 2)})
    return found


def walled(blocked, at, target, corner):
    """Whether something in the way (`tile.read_blocked`, [row, column] from the group's south-west corner) lies on the
    straight line between where a walker stopped and its target, both (x, y) in the check area, `corner` the group's
    south-west corner there. A walker that stops near its target with a fence between has not arrived: the rail
    freight depot's walker from the next tile into the service bay's fenced yard stopped against the fence, half a
    metre from a target just inside it, and passed the check while only the distance counted (client, 2026-11-13)."""
    step = tile.SIZE / tile.CELLS; (x0, y0), (x1, y1) = at, target; count = max(math.ceil(math.dist(at, target) / (step / 4)), 1)
    for index in range(count + 1):
        row = math.floor((y0 + (y1 - y0) * index / count - corner[1]) / step); column = math.floor((x0 + (x1 - x0) * index / count - corner[0]) / step)
        if 0 <= row < blocked.shape[0] and 0 <= column < blocked.shape[1] and blocked[row, column]:
            return True
    return False


def _tile_field(set_text, number, field):
    """The value of one field of a tile's section of a set file, or None: whatever its line endings."""
    parts = set_text.split(f'[TILE{number}]', 1)
    for line in parts[1].split('[', 1)[0].splitlines() if len(parts) == 2 else ():
        key, _, value = line.partition('=')
        if key.strip() == field:
            return value.strip()
    return None


def _ground(repo, tileset, resources):
    """Stage the tileset's set file, palette and plain tile with its textures, and the shared tile pack's envkit files."""
    pack, common = repo / f'srn_t_{tileset}', repo / 'srn_t_common'; fill = FILL[tileset]
    for path in common.glob('ek_*'):
        shutil.copyfile(path, resources / path.name)
    for path in (repo / 'srn_placeable').glob('ek_off*'):
        shutil.copyfile(path, resources / path.name)
    for path in (pack / f'{tileset}.set', pack / f'{tileset}palstd.itp'):
        shutil.copyfile(path, resources / path.name)
    text = (pack / f'{tileset}.set').read_bytes().decode('cp1252')
    plain, picture = _tile_field(text, fill, 'Model'), _tile_field(text, fill, 'ImageMap2D')
    found = [folder / f'{plain}.mdl' for folder in (pack, common) if plain and (folder / f'{plain}.mdl').is_file()]
    require(found and picture, f'{tileset} has no plain tile {fill} with a model in its pack to lay the check area with')
    source, picture = found[0], picture.lower()
    bitmaps = {line.split()[1].lower() for line in source.read_text(encoding='cp1252').splitlines() if line.strip().startswith('bitmap') and line.split()[1].lower() != 'null'}
    for folder in (pack, common):
        for one in (plain, picture, 'pavement', *bitmaps):
            for path in folder.glob(one + '.*'):
                shutil.copyfile(path, resources / path.name.lower())
    return text


def laid_tiles(set_text, tileset, model, tiles, column0, row0):
    """{(column, row): tile number} for a built group laid with its south-west tile at (column0, row0), from the
    tileset's set file. The numbers are the pack's, so the pack must hold this very build: the tiles `tiles` (the
    built report's) in the same order from the group's first. A group built again with another split and not installed
    again would be laid with the old tiles, some of them not its own."""
    require(f'Model={model}_t00' in set_text, f'{tileset} does not hold {model} yet: install the group first')
    first = int(set_text[:set_text.index(f'Model={model}_t00')].rsplit('[TILE', 1)[1].split(']')[0]); laid = {}
    for index, one in enumerate(tiles):
        held = _tile_field(set_text, first + index, 'Model')
        require(held == one['model'], f'{tileset} holds another build of {model}: its tile {first + index} is {held}, not {one["model"]}; install the group again')
        laid[(column0 + one['column'], row0 + one['row'])] = first + index
    return laid


def group(game, repo, base, name, models_path, built, model, tileset, mode='day', *, second_storey='0', size=None, scale_prop='ek_ss_vending', targets=None):
    """A built tile group (`tiles`' folder) laid in an area of `tileset`, which must hold it already (`install`): the
    tile numbers are the pack's, the models and walkmeshes the built ones. mode: day, night (with its lights put out
    and on again), near or walk (`walk_plan`; refused if a walker stops more than REACHED metres short or with something in the way between (`walled`), after its
    captures and `walks.json` are written). targets: {label: (x, y)} more places a walk sends walkers to, in metres from
    the group's south-west corner as `walk.png` shows them (the Saeder-Krupp yard's bay, which no automatic target
    reaches). size: tiles across the area, by default as many as hold the group (`area_size`)."""
    require(tileset in FILL, 'A check area is laid in ' + ' or '.join(FILL)); require(mode in ('day', 'night', 'near', 'walk'), 'mode is day, night, near or walk')
    require(not targets or mode == 'walk', 'Targets are where a walk check sends walkers: give them with --mode walk')
    repo, base = Path(repo).resolve(), Path(base).resolve(); models = convert.load_models(models_path)
    require(model in models and models[model].get('tiles'), model + ' is not a tile group of the game set')
    resources = _fresh(base, name)
    folder = Path(built) / model; made = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    walk_picture = folder / 'source' / tile.WALK_PICTURE
    require(mode != 'walk' or walk_picture.is_file(), f'{folder} has no {tile.WALK_PICTURE}, which picks where walkers go: build the group again')
    text = _ground(repo, tileset, resources)
    column0 = row0 = MARGIN; laid = laid_tiles(text, tileset, model, made['tiles'], column0, row0); size = size or area_size(made['columns'], made['rows'])
    require(max(made['columns'], made['rows']) + column0 + 1 <= size, 'The group does not fit the check area')
    for one in made['tiles']:
        shutil.copyfile(folder / 'compiled' / f'{one["model"]}.mdl', resources / f'{one["model"]}.mdl')
        shutil.copyfile(folder / 'source' / f'{one["model"]}.wok', resources / f'{one["model"]}.wok')
    for path in [*(folder / 'shared').iterdir(), *(folder / 'source').glob('*.tga')]:
        shutil.copyfile(path, resources / path.name)
    from_pack(repo / 'srn_placeable', scale_prop, resources)  # something of a known size in the corner of the area
    door, night = laid_door(made), mode == 'night'; facing = float((models[model]['tiles'].get('door') or {}).get('facing', 90.0)); people, walkers = [], []
    if mode == 'walk':
        roomy = tile.read_walk(walk_picture); chosen = tile.walk_targets(roomy, tile.read_walk(walk_picture, planned=True))
        own_targets(roomy, targets or {}, chosen); chosen.update(targets or {})
        walkers = walk_plan(made['columns'], made['rows'], door, facing, chosen, column0=column0, row0=row0, size=size)
        shots = walk_shots(made['columns'], made['rows'], walkers, name, column0=column0, row0=row0, size=size); people = [{'position': one['start'], 'facing': 0.0} for one in walkers]
    else:
        shots = group_shots(made['columns'], made['rows'], door, mode, column0=column0, row0=row0, facing=facing)
    if night:
        lit = [(texture, 'halo' in found) for texture in [model, *made.get('parts', {}).values()] if (found := convert.lights(texture, folder / 'shared'))]
        shots += blackout_shots(made['columns'], made['rows'], lit, column0=column0, row0=row0)
    record = fixture.build(name, resources, [{'model': scale_prop, 'position': [3.0, 3.0], 'bearing': 0.0, 'static': True}], shots, base / 'fixtures' / name, game,
                           repo / 'srn_2da/placeables.2da', people=people, night=night, size=size, hold=walk_hold(size) if walkers else 6.0,
                           ground={'tileset': tileset, 'fill': FILL[tileset], 'tiles': laid, 'lights': {spot: [11, 0] for spot in laid} if night else {}})
    extra = f'[graphics.second-story-tiles]\nmode = {second_storey}\n' if mode == 'near' else ''
    result = _run(game, record, base / 'fixtures' / name, extra_settings=extra)
    if walkers:
        captures = base / 'fixtures' / name / 'captures'
        result['walkers'] = walks(json.loads((captures / 'run.json').read_text(encoding='utf-8'))['lines'], walkers)
        blocked = tile.read_blocked(walk_picture)
        for one in result['walkers']:
            one['walled'] = walled(blocked, one['at'], one['target'], (column0 * TILE, row0 * TILE))
        (captures / 'walks.json').write_text(json.dumps(result['walkers'], indent=1), encoding='utf-8')
        short = [f'{one["label"]} stopped {one["short"]} m short of {one["target"]}' + (' with something in the way between' if one['walled'] else '')
                 for one in result['walkers'] if one['short'] > REACHED or one['walled']]
        require(not short, 'Walkers did not arrive: ' + '; '.join(short) + f'. See {captures}')
    return result


def chained(doors, *, step=STEP):
    """Give each door an area transition to a waypoint in front of the next one, the last to the first, changing
    nothing else of it. doors: [(area, door struct of that area's .git, as JSON)], in the order they are to be walked.
    Returns {area: [waypoint structs]}. A door's front is the way it looks out, a quarter turn back from its bearing
    (checked for doors that look north, 2026-11-12)."""
    require(len(doors) >= 2, 'A walk through doors needs two at least'); waypoints = {}
    for index, (area, door) in enumerate(doors):
        out = door['Bearing']['value'] - math.pi / 2; x, y = door['X']['value'] + step * math.cos(out), door['Y']['value'] + step * math.sin(out)
        waypoints.setdefault(area, []).append({
            '__struct_id': 5, 'Appearance': field('byte', 1), 'Description': field('cexolocstring', {}), 'HasMapNote': field('byte', 0),
            'LinkedTo': field('cexostring', ''), 'LocalizedName': field('cexolocstring', {'0': f'ek_w{index + 1}'}), 'MapNote': field('cexolocstring', {}),
            'MapNoteEnabled': field('byte', 0), 'Tag': field('cexostring', f'ek_w{index + 1}'), 'TemplateResRef': field('resref', 'nw_waypoint001'),
            'XOrientation': gff_float(-math.cos(out)), 'YOrientation': gff_float(-math.sin(out)),  # facing the door
            'XPosition': gff_float(x), 'YPosition': gff_float(y), 'ZPosition': gff_float(0.0)})
        door['Tag']['value'] = f'ek_d{index + 1}'; door['LinkedTo']['value'] = f'ek_w{(index + 1) % len(doors) + 1}'
        door['LinkedToFlags']['value'] = 2  # to a waypoint: the Area Transition tab, and no more
    return waypoints


def watch_script(count, facing, ticks, begin):
    """The module's entry script: the player stood free at the first door's waypoint, in whichever area that is (the
    module's entry area need not be one with a door), each door probed, and their place logged every two seconds for
    `ticks` ticks."""
    probes = ' '.join(f'Probe("ek_d{index + 1}");' for index in range(count))
    return f'''void Watch(object pc,int n) {{
  object a=GetArea(pc); vector at=GetPosition(pc);
  WriteTimestampedLogEntry("{fixture.LOG_PREFIX} watch="+IntToString(n)+" area="+GetTag(a)+" x="+FloatToString(at.x,7,3)+" y="+FloatToString(at.y,7,3)+" z="+FloatToString(at.z,7,3));
  if(n>={ticks}) {{ WriteTimestampedLogEntry("{fixture.LOG_PREFIX} done"); return; }}
  DelayCommand(2.0,Watch(pc,n+1));
}}
void Probe(string tag) {{
  object d=GetObjectByTag(tag); object t=GetTransitionTarget(d); vector at=GetPosition(d);
  WriteTimestampedLogEntry("{fixture.LOG_PREFIX} probe="+tag+" valid="+IntToString(GetIsObjectValid(d))+" doorarea="+GetTag(GetArea(d))+" target="+GetTag(t)+" targetarea="+GetTag(GetArea(t))+" z="+FloatToString(at.z,6,3));
}}
void Place(object pc) {{
  AssignCommand(pc,ClearAllActions()); AssignCommand(pc,JumpToLocation(GetLocation(GetWaypointByTag("ek_w1"))));
  SetCameraHeight(pc,1.5); AssignCommand(pc,SetCameraFacing({facing + 30.0:.1f},9.0,68.0,CAMERA_TRANSITION_TYPE_SNAP));
  {probes}
  DelayCommand(2.0,Watch(pc,0));
}}
void main() {{
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  if(GetLocalInt(pc,"ekdr")) return; SetLocalInt(pc,"ekdr",1);
  SetCameraLimits(pc,1.0,89.0,0.5,60.0);
  WriteTimestampedLogEntry("{fixture.LOG_PREFIX} enter");
  DelayCommand({begin:.1f},Place(pc));
}}
'''


def stages(lines):
    """Where the player was each time they were somewhere new, another area or more than a metre from the last place
    told: [(tick, area, x, y)] from the watch lines."""
    seen = []
    for line in lines:
        values = client.parse_line(line)
        if 'watch' in values and values.get('area'):
            area, x, y = values['area'], float(values['x']), float(values['y'])
            if not seen or seen[-1][1] != area or math.hypot(x - seen[-1][2], y - seen[-1][3]) > 1.0:
                seen.append((int(values['watch']), area, x, y))
    return seen


def walked(lines, count):
    """What a door walk's log says: {probes: [{door, target, area}], stages}. A walk that never began or never ended, a
    door that was not probed, and a door whose transition leads nowhere are refused: an empty answer is no result."""
    prefix = fixture.LOG_PREFIX
    require(f'{prefix} enter' in lines, 'The module never ran its entry script: are the packs there (a retired user folder has no hak), and did the client load it?')
    require(f'{prefix} done' in lines, 'The watch did not finish: the client was closed or the module stopped before its last tick')
    probes = [values for values in map(client.parse_line, lines) if 'probe' in values]
    require(len(probes) == count, f'{count} doors were to be probed and {len(probes)} were')
    for values in probes:
        require(values.get('valid') == '1' and values.get('target', '').strip(), f'The door {values["probe"]} leads nowhere: its transition has no target')
    return {'probes': [{'door': values['probe'], 'target': values['target'].strip(), 'area': values.get('targetarea', '').strip()} for values in probes], 'stages': stages(lines)}


def doors(game, user, captures, *, module='ektool', name='ekdoors', ticks=150):
    """Run the Toolset-saved module `user/modules/<module>.mod` with its doors chained (`chained`), the player free in
    front of the first. Somebody clicks each door while this logs where the player is and captures the window at every
    change of area and every ten seconds. The module's entry area's doors come first, each area's from west to east.
    Returns {doors, probes, stages, captures} (`walked`)."""
    from tools.phenotypes import tool_runtime
    game, user, captures = Path(game), Path(user).resolve(), Path(captures).resolve()
    require((user / 'modules' / f'{module}.mod').is_file(), f'No module the Toolset saved in {user}: {module}.mod')
    require((user / 'hak').is_dir(), f'{user} has no hak folder: the module cannot load its packs (a retired folder is prepared again)')
    require(not captures.exists(), 'The captures go to a fresh folder: ' + str(captures))
    work = user.parent / (name + '-work'); shutil.rmtree(work, ignore_errors=True); (work / 'module').mkdir(parents=True); captures.mkdir(parents=True)
    tool = lambda which: str(tool_runtime.tool(which))
    run = lambda arguments, **more: subprocess.run([str(value) for value in arguments], check=True, capture_output=True, **more)
    run([tool('nwn_erf'), '-x', '-f', user / 'modules' / f'{module}.mod'], cwd=work / 'module')
    read = lambda file: json.loads(run([tool('nwn_gff'), '-i', work / 'module' / file, '-k', 'json']).stdout)

    def write(file, document):
        path = work / (file + '.json'); path.write_text(json.dumps(document), encoding='utf-8')
        run([tool('nwn_gff'), '-i', path, '-l', 'json', '-o', work / 'module' / file, '-k', 'gff'])

    ifo = read('module.ifo'); entry = ifo['Mod_Entry_Area']['value']
    areas = sorted((row['Area_Name']['value'] for row in ifo['Mod_Area_list']['value']), key=lambda area: (area != entry, area))
    gits = {area: read(area + '.git') for area in areas}
    walk = [(area, door) for area in areas for door in sorted(gits[area]['Door List']['value'], key=lambda door: door['X']['value'])]
    waypoints = chained(walk)
    for area in areas:
        gits[area]['WaypointList']['value'] = gits[area]['WaypointList']['value'] + waypoints.get(area, []); write(area + '.git', gits[area])
    first = waypoints[walk[0][0]][0]
    facing = math.degrees(math.atan2(first['YOrientation']['value'], first['XOrientation']['value'])) % 360
    script = work / 'module' / (name + '_en.nss'); script.write_text(watch_script(len(walk), facing, ticks, fixture.START), encoding='ascii', newline='\n')
    run([tool('nwn_script_comp'), '--root', game, '--userdirectory', user, '--no-ovr', script])
    require(script.with_suffix('.ncs').is_file(), 'The entry script did not compile'); script.unlink()
    ifo['Mod_OnClientEntr'] = field('resref', name + '_en'); write('module.ifo', ifo)
    run([tool('nwn_erf'), '-c', '-f', user / 'modules' / f'{name}.mod', '-e', 'MOD', work / 'module'])
    wait_for_clients(3000)
    (user / 'settings.tml').write_text(client.SETTINGS.format(width=1600, height=900), encoding='utf-8')
    process = client.start(game, user, name, width=1600, height=900)
    print(json.dumps({'started': process.pid, 'doors': [[area, door['Tag']['value'], door['X']['value'], door['Y']['value']] for area, door in walk]}), flush=True)
    taken, seen, state = [], 0, None
    try:
        limit = time.monotonic() + fixture.START + ticks * 2.0 + 240
        while time.monotonic() < limit:
            time.sleep(client.POLL)
            require(process.poll() is None, 'The client exited before the watch ended')
            lines = client.log_lines(user, fixture.LOG_PREFIX)
            for line in lines[seen:]:
                values = client.parse_line(line)
                if 'watch' in values and (values.get('area') != state or int(values['watch']) % 5 == 0):
                    state = values.get('area'); time.sleep(0.5)
                    taken.append(str(fixture.capture(process.pid, captures / f'watch-{int(values["watch"]):03d}.png')))
            seen = len(lines)
            if f'{fixture.LOG_PREFIX} done' in lines:
                break
        lines = client.log_lines(user, fixture.LOG_PREFIX)
    finally:
        client.stop(process)
    (captures / 'run.json').write_text(json.dumps({'lines': lines, 'captures': taken}, indent=1), encoding='utf-8')
    return {'doors': len(walk), **walked(lines, len(walk)), 'captures': len(taken)}  # after the log is kept: a walk that is refused can still be read
