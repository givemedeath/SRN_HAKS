"""An isolated client fixture for envkit placeables: a throwaway hak and module in a fresh user directory.

Built on armorkit's fixture pieces (flat area on a copied stock tileset, module documents, isolated user directory). The
props stand in a row; the entry script walks an unseen player along it, sets the camera at each one and writes
`ENVKIT shot=<n>` so a driver can capture the window. Nothing here touches the repository packs: the fixture's own
placeables table is the repository's with the props appended, inside the fixture hak."""
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path

from tools.armorkit import client, client_fixture
from tools.armorkit.client_fixture import field, gff_float
from tools.envkit import placeables, require

LOG_PREFIX = 'ENVKIT'
# A shot is held long enough that a capture after the settle, a poll and a whole second of stamp rounding is in time (`late`).
START, HOLD = 8.0, 5.0
NL = chr(10)
LABEL = re.compile(r'[A-Za-z0-9_-]+')


def table(stock_text, models, lights=None):
    """The placeables table with a row of its own appended for each model under test, whether or not the table names
    the model already, with its light where `lights` ({model: light}) gives one; returns (text, {model: row number})."""
    lights = lights or {}
    return placeables.register(stock_text, [{'model': model, 'label': model, 'sound': None, 'light': lights.get(model)} for model in models], again=True)


def placed(tag, appearance, position, bearing, static=True):
    """One placeable of a table row in an area's placeable list. A static one is scenery the server never sees again; one
    a script must reach by its tag (to swap a texture, say) is placed not static."""
    x, y = position
    values = {'TemplateResRef': field('resref', ''), 'Tag': field('cexostring', tag), 'LocName': field('cexolocstring', {'0': tag}),
              'Description': field('cexolocstring', {}), 'Appearance': field('dword', appearance), 'Static': field('byte', 1 if static else 0),
              'Useable': field('byte', 0), 'Plot': field('byte', 1), 'HP': field('short', 15), 'CurrentHP': field('short', 15),
              'Hardness': field('byte', 5), 'Fort': field('byte', 16), 'Ref': field('byte', 0), 'Will': field('byte', 0),
              'Faction': field('dword', 1), 'AnimationState': field('byte', 0), 'HasInventory': field('byte', 0),
              'Lockable': field('byte', 0), 'Locked': field('byte', 0), 'PortraitId': field('word', 0), 'Type': field('byte', 0),
              'BodyBag': field('byte', 0), 'TrapFlag': field('byte', 0), 'Conversation': field('resref', ''),
              'X': gff_float(x), 'Y': gff_float(y), 'Z': gff_float(0.0), 'Bearing': gff_float(bearing)}
    return {'__struct_id': 9, **values}


def person(template, tag, position, facing=270.0, height=0.0):
    """A stock human standing still, for scale: the template's own clothes and build, no scripts, no conversation.
    Facing 270 looks south, at a camera that looks north. `height` lifts them onto a slab the walkmesh does not know."""
    import copy
    c = copy.deepcopy(template); c.pop('__data_type', None); c['__struct_id'] = 4
    for key in list(c):
        if key.startswith('Script'):
            c[key] = field('resref', '')
    turn = math.radians(facing)
    c.update({'Tag': field('cexostring', tag), 'TemplateResRef': field('resref', tag), 'FactionID': field('word', 2), 'Plot': field('byte', 1),
              'Conversation': field('resref', ''), 'XPosition': gff_float(position[0]), 'YPosition': gff_float(position[1]),
              'ZPosition': gff_float(height), 'XOrientation': gff_float(math.cos(turn)), 'YOrientation': gff_float(math.sin(turn))})
    return c


LINE_DELAY = 1.0  # seconds after a shot starts that its log line is written


def enter_script(shots, start=START, hold=HOLD):
    """Hide the player, then for each shot stand them at a spot and set the camera: {label, stand: [x, y], facing,
    distance, pitch, height, run}. Facing 90 looks north. `run` is script the shot runs first, to change the scene."""
    require(all(NL not in shot.get('run', '') for shot in shots), 'A shot runs one line of script')
    # The label goes into the script, the log line and the capture's file name.
    require(all(LABEL.fullmatch(str(shot['label'])) for shot in shots), 'A shot label is letters, digits, - and _')
    lines = ['void Shot(object pc,int n) {', f'  if(n>={len(shots)}) {{ WriteTimestampedLogEntry("{LOG_PREFIX} done"); return; }}',
             '  float x; float y; float facing; float distance; float pitch; float height; string label;']
    for index, shot in enumerate(shots):
        lines.append(f'  if(n=={index}) {{ x={shot["stand"][0]:.3f}; y={shot["stand"][1]:.3f}; facing={float(shot.get("facing", 90)):.3f}; '
                     f'distance={float(shot.get("distance", 5)):.3f}; pitch={float(shot.get("pitch", 75)):.3f}; '
                     f'height={float(shot.get("height", 1.0)):.3f}; label="{shot["label"]}"; {shot.get("run", "")} }}')
    lines += ['  AssignCommand(pc,ClearAllActions()); AssignCommand(pc,JumpToLocation(Location(GetArea(pc),Vector(x,y,0.0),facing)));',
              '  SetCameraHeight(pc,height); AssignCommand(pc,SetCameraFacing(facing,distance,pitch,CAMERA_TRANSITION_TYPE_SNAP));',
              f'  DelayCommand({LINE_DELAY:.1f},WriteTimestampedLogEntry("{LOG_PREFIX} shot="+IntToString(n)+" target="+label+" valid=1"));',
              f'  DelayCommand({hold:.1f},Shot(pc,n+1));', '}',
              'void main() {', '  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;', '  SetCameraLimits(pc,1.0,89.0,0.5,60.0);',
              '  ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectVisualEffect(VFX_DUR_CUTSCENE_INVISIBILITY),pc);',
              '  SetCutsceneMode(pc,TRUE,FALSE);', f'  WriteTimestampedLogEntry("{LOG_PREFIX} enter shots={len(shots)}");',
              f'  DelayCommand({start:.1f},Shot(pc,0));', '}']
    return '\n'.join(lines) + '\n'


def build(name, resources, props, shots, output, nwn_root, stock_table, *, people=(), night=False, size=8, start=START, hold=HOLD, ground=None):
    """props: [{model, position: [x, y], bearing, static, appearance, light}] (bearing in radians; light as `placeables.light_values`; tagged `name`_p<index>). people: [{position, facing, height}], stock
    humans for scale. ground: {tileset, fill, tiles: {(column, row): tile}} lays the area with a tileset whose set file is
    among the resources, instead of the flat stock one: `fill` everywhere but the tiles named, counted from the south-west;
    its `lights` ({(column, row): [main light 1, main light 2]}) colour those tiles' main lights.
    Returns the fixture record."""
    from tools.phenotypes import tool_runtime
    require(client_fixture.NAME.fullmatch(name), 'Fixture name must be a lowercase resref of at most 11 characters')
    root, output = Path(nwn_root), Path(output).resolve()
    require((root / 'data').is_dir(), 'The game install folder is required (the one holding data/)')
    require(not output.exists(), 'A fixture is built into a fresh folder: ' + output.name)
    user, staged, documents, binary = (output / part for part in ('userdir', 'hak-resources', 'json', 'module'))
    for folder in (user / 'hak', user / 'modules', staged, documents, binary):
        folder.mkdir(parents=True)
    common = ['--root', root, '--userdirectory', user, '--no-ovr']; tools = {}

    def run(tool, args):
        tools.setdefault(tool, tool_runtime.tool(tool))
        result = subprocess.run([str(tools[tool]), *map(str, args)], capture_output=True, timeout=600,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0, tool + ' failed: ' + result.stderr.decode(errors='replace')[-2000:])
        return result.stdout

    for path in sorted(Path(resources).iterdir()):
        require(path.is_file() and len(path.stem) <= client_fixture.RESREF and path.name == path.name.lower(), 'Hak resources are lowercase resref files: ' + path.name)
        shutil.copyfile(path, staged / path.name)
    # A prop that names its own row (`appearance`) is placed by it: the table's row for that model is what is under test.
    text, rows = table(Path(stock_table).read_text(encoding='cp1252'), sorted({prop['model'] for prop in props if 'appearance' not in prop}),
                       {prop['model']: prop['light'] for prop in props if prop.get('light')})
    (staged / 'placeables.2da').write_text(text, encoding='cp1252', newline='')
    if ground is None:
        stock_set = run('nwn_resman_cat', [*common, client_fixture.TEMPLATE_TILESET + '.set']).decode('cp1252')
        (staged / (name + '.set')).write_text(client_fixture.tileset(stock_set, name), encoding='cp1252', newline='')
        (staged / (name + '_edge.2da')).write_bytes(run('nwn_resman_cat', [*common, client_fixture.TEMPLATE_TILESET + '_edge.2da']))
    else:
        require((staged / (ground['tileset'] + '.set')).is_file(), 'The tileset laid must be among the resources')
    hak = user / 'hak' / (name + '.hak')
    run('nwn_erf', ['-c', '-f', hak, '-e', 'HAK', staged])
    script = binary / (name + '_en.nss'); script.write_text(enter_script(shots, start, hold), encoding='ascii', newline='\n')
    run('nwn_script_comp', [*common, script])
    require(script.with_suffix('.ncs').is_file(), 'The entry script did not compile')
    creatures = []
    if people:
        stock = documents / client_fixture.TEMPLATE_CREATURE
        stock.write_bytes(run('nwn_resman_cat', [*common, client_fixture.TEMPLATE_CREATURE]))
        run('nwn_gff', ['-i', stock, '-o', documents / (stock.name + '.json')])
        template = json.loads((documents / (stock.name + '.json')).read_text(encoding='utf-8'))
        creatures = [person(template, f'{name}_h{index}', one['position'], one.get('facing', 270.0), one.get('height', 0.0))
                     for index, one in enumerate(people)]
    area = client_fixture.area_documents(name, creatures, size)
    if ground is not None:
        area[name + '_a.are']['Tileset'] = field('resref', ground['tileset'])
        for index, laid in enumerate(area[name + '_a.are']['Tile_List']['value']):
            laid['Tile_ID'] = field('int', ground['tiles'].get((index % size, index // size), ground['fill']))
            for number, colour in enumerate(ground.get('lights', {}).get((index % size, index // size), ()), 1):
                laid[f'Tile_MainLight{number}'] = field('byte', colour)  # rows of lightcolor.2da, as a builder sets them in the Toolset
    area[name + '_a.git']['Placeable List'] = field('list', [placed(f'{name}_p{index}', prop.get('appearance', rows.get(prop['model'])), prop['position'], prop.get('bearing', math.pi), prop.get('static', True))
                                                             for index, prop in enumerate(props)])
    if night:
        area[name + '_a.are'].update({'IsNight': field('byte', 1), 'MoonAmbientColor': field('dword', 0x302820),
                                      'MoonDiffuseColor': field('dword', 0x504840)})
    for filename, document in {**area, **client_fixture.module_documents(name, [], None, tuple(shots[0]['stand']) if shots else (40.0, 30.0))}.items():
        path = documents / (filename + '.json'); path.write_text(json.dumps(document), encoding='utf-8')
        run('nwn_gff', ['-i', path, '-o', binary / filename])
    module = user / 'modules' / (name + '.mod')
    run('nwn_erf', ['-c', '-f', module, '-e', 'MOD', binary])
    record = {'name': name, 'userDirectory': str(user), 'module': module.name, 'hak': hak.name, 'rows': rows, 'shots': [shot['label'] for shot in shots],
              'start': start, 'hold': hold, 'night': night, 'clientValidated': False}
    (output / 'fixture.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def grab(pid, path):
    """(the client window's pixels, `clock()` as the grab that made them began). A window that opened minimised (someone
    is using the machine) cannot be grabbed, so it is shown, without taking the focus, and grabbed again: the time is
    the second grab's, since the wait before it can carry the grab past its shot (review, 2026-11-14)."""
    try:
        began = clock(); return client.capture(pid, path), began
    except OSError:
        import ctypes
        ctypes.WinDLL('user32').ShowWindow(ctypes.c_void_p(client.window(pid)), 4)  # SW_SHOWNOACTIVATE
        time.sleep(0.7)
        began = clock(); return client.capture(pid, path), began


def capture(pid, path):
    """The client window's pixels (`grab`)."""
    return grab(pid, path)[0]


# The client stamps its log to the second. A capture that may have come after the shot's next view (`late`) is
# refused: the rail freight depot's client stalled for
# twenty seconds on its sixth shot, and its check took the last view five times under five names (2026-11-13).
STAMPED = re.compile(r'^\[\w{3} \w{3} +\d+ (\d\d):(\d\d):(\d\d)\]\s*')
DAY = 86400.0


def stamped_lines(user_directory, prefix=LOG_PREFIX):
    """[(seconds after midnight its line was stamped, or None, line)] of the fixture's lines in the client log."""
    path = Path(user_directory) / 'logs' / 'nwclientLog1.txt'
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(encoding='cp1252', errors='replace').splitlines():
        stamp = STAMPED.match(line.strip()); text = client.STAMP.sub('', line.strip())
        if text.startswith(prefix):
            found.append((int(stamp[1]) * 3600 + int(stamp[2]) * 60 + int(stamp[3]) if stamp else None, text))
    return found


def clock():
    """Seconds after local midnight now, as the client stamps its log."""
    now = time.localtime(); return now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec + time.time() % 1


def late(stamp, now, hold):
    """How many seconds after its shot's line a capture made `now` came, where that is too late for the shot's view
    still to be on screen; None where it is in time, or the line bore no stamp."""
    if stamp is None:
        return None
    # The line is written LINE_DELAY after its shot starts, so the next view comes hold - LINE_DELAY after it. The stamp
    # is cut to the whole second, so the line may have come up to a second after it: lag is measured from the stamp,
    # which only makes it longer, and a capture is late once it may have missed the view (review, 2026-11-14).
    lag = (now - stamp) % DAY
    return lag if lag > hold - LINE_DELAY - client.MARGIN else None


def run(nwn_root, record, captures, *, settle=1.5, width=1600, height=900, extra_settings=''):
    """Start the client on the fixture, capture the window after each shot line, stop the client; returns lines and
    captures. A capture made too late for its shot (`late`) is kept as `<name>-late.png`, and the run is refused once the
    fixture has finished."""
    user = Path(record['userDirectory']); timeout = record['start'] + len(record['shots']) * record['hold'] + 240
    # Every run states its own settings, so none are left over from the run before.
    (user / 'settings.tml').write_text(client.SETTINGS.format(width=width, height=height) + extra_settings, encoding='utf-8')
    process = client.start(nwn_root, user, Path(record['module']).stem, width=width, height=height)
    shots, seen, missed = [], 0, []
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(client.POLL)
            require(process.poll() is None, 'The client exited before the fixture finished')
            lines = stamped_lines(user, LOG_PREFIX)
            for stamp, line in lines[seen:]:
                values = client.parse_line(line)
                if 'shot' in values and 'target' in values:
                    time.sleep(settle)
                    # When the grab that made the picture starts: how long the grab itself takes does not make it late.
                    path, grabbed = grab(process.pid, Path(captures) / f'shot-{int(values["shot"]):02d}-{values["target"]}.png'); path = Path(path)
                    lag = late(stamp, grabbed, record['hold'])
                    if lag is None:
                        shots.append(str(path))
                    else:
                        path.replace(path.with_name(path.stem + '-late.png')); missed.append(f'{values["target"]} ({lag:.0f} s)')
            seen = len(lines)
            if f'{LOG_PREFIX} done' in [line for _, line in lines]:
                break
        else:
            raise ValueError('The fixture did not finish within the timeout')
        require(not missed, f'Captures came after their shot had passed and show a later view: {", ".join(missed)}. The client '
                f'stalled (loading what came into view) or its log came late; the captures are kept as -late.png in {captures}. Run the check again')
        return {'lines': client.log_lines(user, LOG_PREFIX), 'captures': shots}
    finally:
        client.stop(process)
