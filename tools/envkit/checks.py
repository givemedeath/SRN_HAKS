"""Checks of a sheet's work in the game client, each in a throwaway module and user folder (`prop_fixture`).

`props` stands converted props in a row and looks at each from the front, the back and the side, by day or by night,
with a figure beside it for scale and one behind it to be seen through anything see-through. `lights` stands the lit
props of a game set as the pack holds them, by night, and puts their lights out and on again by script. `group` lays
a built tile group in an area of one of its tilesets and looks at it from the front, at its door, and along and over
its sides; its `near` mode frees the player with the client hiding upper storeys near the character. `doors` takes a
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

from . import convert, prop_fixture as fixture, require

FILL = {'dgt04': 0, 'udp1': 58}  # the plain tile each tileset's check area is laid with
TILE = 10.0
GAP = 6.0  # metres between props in a row
ROW = 5  # lit props to a row at most
ROW_END = 52.0  # how far along x a row of lit props may reach and still be held by its view, metres
STEP = 3.5  # how far in front of a door the player is put, metres
MAPS = ('.mtr', '.pwk', '.dds', '.txi')


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
        props.append({'model': model, 'position': [x, y], 'static': not models[model].get('lit')})  # a lit prop is reached by script
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
            props.append({'model': model, 'position': [x, y], 'static': False})
            people.append({'position': [x + size[0] / 2 + 0.8, y - size[1] / 2 - 0.3], 'facing': 270.0})
            x += size[0] / 2 + 3.5
    swap = lambda on: ''.join(convert.lights_script(model, tags[model], on, halo=model in halos) for model in lit)
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


def group_shots(columns, rows, door, mode, *, column0=3, row0=3):
    """The views of a tile group laid with its south-west tile at (column0, row0): {label, stand, facing, distance,
    pitch, height}. `door` is the middle of its door's foot from the group's middle, or None. By `day` and `night` the
    group is seen from the front, at its door, slantwise along each side from just inside its edge, at two corners and
    from above; `near` frees the player (the first shot's `run`) at the door, off it, far from it and behind it."""
    hx, hy = columns * TILE / 2, rows * TILE / 2; cx, cy = column0 * TILE + hx, row0 * TILE + hy; reach = max(hx, hy)
    view = lambda label, x, y, facing, distance, pitch, height=2.2: {'label': label, 'stand': [cx + x, cy + y], 'facing': facing, 'distance': distance, 'pitch': pitch, 'height': height}
    front = view('front', 0.0, hy, 270, 2.5 * reach, 62, 1.5)
    at_door = [view('door', door[0], door[1] + 2.2, 270, 12.0, 66, 1.5)] if door is not None else []
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


def group(game, repo, base, name, models_path, built, model, tileset, mode='day', *, second_storey='0', size=9, scale_prop='ek_ss_vending'):
    """A built tile group (`tiles`' folder) laid in an area of `tileset`, which must hold it already (`install`): the
    tile numbers are the pack's, the models and walkmeshes the built ones. mode: day, night or near."""
    require(tileset in FILL, 'A check area is laid in ' + ' or '.join(FILL)); require(mode in ('day', 'night', 'near'), 'mode is day, night or near')
    repo, base = Path(repo).resolve(), Path(base).resolve(); models = convert.load_models(models_path)
    require(model in models and models[model].get('tiles'), model + ' is not a tile group of the game set')
    resources = _fresh(base, name)
    text = _ground(repo, tileset, resources); folder = Path(built) / model; made = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    column0 = row0 = 3; laid = laid_tiles(text, tileset, model, made['tiles'], column0, row0)
    require(max(made['columns'], made['rows']) + column0 + 1 <= size, 'The group does not fit the check area')
    for one in made['tiles']:
        shutil.copyfile(folder / 'compiled' / f'{one["model"]}.mdl', resources / f'{one["model"]}.mdl')
        shutil.copyfile(folder / 'source' / f'{one["model"]}.wok', resources / f'{one["model"]}.wok')
    for path in [*(folder / 'shared').iterdir(), *(folder / 'source').glob('*.tga')]:
        shutil.copyfile(path, resources / path.name)
    from_pack(repo / 'srn_placeable', scale_prop, resources)  # something of a known size in the corner of the area
    door = (models[model]['tiles'].get('door') or {}).get('at'); night = mode == 'night'
    shots = group_shots(made['columns'], made['rows'], door[:2] if door else None, mode, column0=column0, row0=row0)
    record = fixture.build(name, resources, [{'model': scale_prop, 'position': [3.0, 3.0], 'bearing': 0.0, 'static': True}], shots, base / 'fixtures' / name, game,
                           repo / 'srn_2da/placeables.2da', night=night, size=size, hold=6.0,
                           ground={'tileset': tileset, 'fill': FILL[tileset], 'tiles': laid, 'lights': {spot: [11, 0] for spot in laid} if night else {}})
    extra = f'[graphics.second-story-tiles]\nmode = {second_storey}\n' if mode == 'near' else ''
    return _run(game, record, base / 'fixtures' / name, extra_settings=extra)


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
