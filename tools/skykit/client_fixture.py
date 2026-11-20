"""Look at the dynamic skies in the game client: build an isolated test module, run it, capture each scripted view.

    python -m tools.skykit.client_fixture --nwn-root GAME_INSTALL [--out output/skykit/client] [--wait SECONDS]

Builds a HAK of the sky resources (srn_skybox's srn_sky* files and srn_2da's skyboxes.2da) and a one-area module in
an isolated user directory, starts the client on it (tools/armorkit/client.py: a client that is already running
blocks the run and is never closed), saves a window capture for every `SKYKIT shot=` line the module's script logs,
then stops the client it started. Captures are evidence to look at, not an approval.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'SKYKIT'
HOLD = 4.0  # seconds each view is held before the next
# (label, sky row, hour, minute, weather 0 clear / 1 rain, camera facings, camera pitch); the module's hour is 60 minutes
SHOTS = [
    ('denver-dawn', 16, 6, 30, 0, (0.0, 180.0), 86.0),
    ('denver-day', 16, 12, 0, 0, (0.0, 180.0), 86.0),
    ('denver-day-play', 16, 12, 0, 0, (90.0,), 62.0),
    ('denver-dusk', 16, 18, 30, 0, (0.0, 180.0), 86.0),
    ('denver-night', 16, 23, 0, 0, (0.0, 180.0), 86.0),
    ('denver-night-play', 16, 23, 0, 0, (270.0,), 62.0),
    ('acid-storm', 17, 23, 0, 1, (0.0, 120.0), 86.0),
    ('dusk-fixed-at-noon', 18, 12, 0, 0, (90.0,), 86.0),
    ('denver-day-fixed-at-night', 22, 23, 0, 0, (90.0,), 86.0),
    ('peaks-day-fixed-at-night', 23, 23, 0, 0, (90.0,), 86.0),
]
AREA, MODULE, HAK = 'sk_test', 'srn_skytest', 'srn_skytest'
# The transition run: two-minute hours, time left to run from just before dusk and just before dawn, a capture every
# TRANSITION_STEP seconds facing west (the dusk sun) and east (the dawn sun), to see the game's own crossfade.
TRANSITIONS = [('into-dusk', 17, 180.0), ('into-dawn', 5, 0.0)]
TRANSITION_STEP, TRANSITION_SHOTS = 15.0, 9


def field(kind, value):
    return {'type': kind, 'value': value}


def structure(kind, **values):
    return {'__data_type': kind, **values}


def script(shots):
    rows = []
    for label, row, hour, minute, rain, facings, pitch in shots:
        for facing in facings:
            rows.append((label, row, hour, minute, rain, facing, pitch))
    lines = ['void Shot(int n)', '{', '  object pc = GetFirstPC(); object area = GetArea(pc);']
    lines.append(f'  if (n >= {len(rows)}) {{ WriteTimestampedLogEntry("{PREFIX} done"); return; }}')
    for index, (label, row, hour, minute, rain, facing, pitch) in enumerate(rows):
        weather = 'WEATHER_RAIN' if rain else 'WEATHER_CLEAR'
        lines.append(f'  if (n == {index}) {{ SetSkyBox({row}, area); SetWeather(area, {weather}); SetTime({hour}, {minute}, 0, 0);'
                     f' AssignCommand(pc, SetCameraFacing({facing:.1f}, 12.0, {pitch:.1f}, CAMERA_TRANSITION_TYPE_SNAP));'
                     f' DelayCommand(2.5, WriteTimestampedLogEntry("{PREFIX} shot={index} name={label} row={row} hour={hour} rain={rain} facing={int(facing)}")); }}')
    lines.append(f'  DelayCommand({HOLD}, Shot(n + 1));')
    lines += ['}', '', 'void main()', '{', '  object pc = GetEnteringObject(); if (!GetIsPC(pc)) return;',
              '  SetCameraMode(pc, CAMERA_MODE_TOP_DOWN);',
              f'  WriteTimestampedLogEntry("{PREFIX} enter shots={len(rows)}");', '  DelayCommand(6.0, Shot(0));', '}', '']
    return '\n'.join(lines), len(rows)


def transition_script():
    rows = [(label, hour, facing, k) for label, hour, facing in TRANSITIONS for k in range(TRANSITION_SHOTS)]
    lines = ['void Shot(int n)', '{', '  object pc = GetFirstPC(); object area = GetArea(pc);']
    lines.append(f'  if (n >= {len(rows)}) {{ WriteTimestampedLogEntry("{PREFIX} done"); return; }}')
    for index, (label, hour, facing, k) in enumerate(rows):
        start = f' SetSkyBox(16, area); SetWeather(area, WEATHER_CLEAR); SetTime({hour}, 1, 0, 0);' if k == 0 else ''
        lines.append(f'  if (n == {index}) {{{start} AssignCommand(pc, SetCameraFacing({facing:.1f}, 12.0, 86.0, CAMERA_TRANSITION_TYPE_SNAP));'
                     f' WriteTimestampedLogEntry("{PREFIX} shot={index} name={label}-{k * int(TRANSITION_STEP)}s facing={int(facing)} hour="'
                     f' + IntToString(GetTimeHour()) + ":" + IntToString(GetTimeMinute()) + ":" + IntToString(GetTimeSecond())); }}')
    lines.append(f'  DelayCommand({TRANSITION_STEP}, Shot(n + 1));')
    lines += ['}', '', 'void main()', '{', '  object pc = GetEnteringObject(); if (!GetIsPC(pc)) return;',
              f'  WriteTimestampedLogEntry("{PREFIX} enter shots={len(rows)}");', '  DelayCommand(6.0, Shot(0));', '}', '']
    return '\n'.join(lines), len(rows)


PLAY_SKIES = [(16, 'Denver'), (17, 'Sprawl Acid Storm'), (20, 'Awakened Peaks')]
PLAY_HOUR = 2.5  # real seconds per game hour in the play module: a whole day in one minute (user, 2026-11-19)


def play_script():
    """No shots: the clock jumps an hour every PLAY_HOUR seconds and each new day shows the next of PLAY_SKIES, with
    the sky and the time floated over the player; the camera is the player's."""
    names = ' '.join(f'if (n == {i}) return "{label} (row {row})";' for i, (row, label) in enumerate(PLAY_SKIES))
    rows = ' '.join(f'if (n == {i}) return {row};' for i, (row, label) in enumerate(PLAY_SKIES))
    text = f"""string SkyName(int n) {{ {names} return ""; }}
int SkyRow(int n) {{ {rows} return 16; }}
void Tick(int day, int hour)
{{
  object pc = GetFirstPC();
  if (hour >= 24) {{ hour = 0; day = (day + 1) % {len(PLAY_SKIES)}; }}
  if (hour == 0 || GetLocalInt(GetModule(), "SK_STARTED") == 0) {{ SetSkyBox(SkyRow(day), GetArea(pc)); SetLocalInt(GetModule(), "SK_STARTED", 1); }}
  SetTime(hour, 0, 0, 0);
  string label = SkyName(day) + "  " + IntToString(hour) + ":00";
  FloatingTextStringOnCreature(label, pc, FALSE);
  WriteTimestampedLogEntry("{PREFIX} play " + label);
  DelayCommand({PLAY_HOUR}, Tick(day, hour + 1));
}}
void main()
{{
  object pc = GetEnteringObject(); if (!GetIsPC(pc)) return;
  SetWeather(GetArea(pc), WEATHER_CLEAR);
  DelayCommand(4.0, Tick(0, 4));
}}
"""
    return text, 0


def build(nwn_root, out, transition=False, play=False):
    sys.path.insert(0, str(ROOT / 'tools' / 'phenotypes'))
    from tool_runtime import tool
    out = Path(out).resolve()
    staging, user = out / 'staging', out / 'user'
    if staging.exists():
        shutil.rmtree(staging)
    resources, binary = staging / 'hak', staging / 'module'
    for folder in (resources, binary, user / 'hak', user / 'modules', user / 'override'):
        folder.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / 'srn_skybox').glob('srn_sky*')):
        shutil.copyfile(path, resources / path.name)
    shutil.copyfile(ROOT / 'srn_2da' / 'skyboxes.2da', resources / 'skyboxes.2da')
    packed = [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(resources.iterdir())]
    erf, gff, compiler = tool('erf', inputs=packed), tool('gff'), tool('script_comp')

    def run(executable, *arguments):
        done = subprocess.run([str(executable), *map(str, arguments)], capture_output=True)
        if done.returncode != 0:
            raise RuntimeError(f'{Path(executable).name} failed: ' + (done.stdout + done.stderr).decode(errors='replace')[-800:])

    hak = user / 'hak' / (HAK + '.hak')
    hak.unlink(missing_ok=True)
    run(erf, '-c', '-f', hak, '-e', 'HAK', resources)
    tiles = [{'__struct_id': 1, 'Tile_ID': field('int', 120), 'Tile_Height': field('int', 0), 'Tile_Orientation': field('int', 0),
              **{k: field('byte', v) for k, v in {'Tile_AnimLoop1': 1, 'Tile_AnimLoop2': 1, 'Tile_AnimLoop3': 1, 'Tile_MainLight1': 0,
                                                    'Tile_MainLight2': 0, 'Tile_SrcLight1': 0, 'Tile_SrcLight2': 0}.items()}}
             for _ in range(64)]
    are = structure('ARE ', Tileset=field('resref', 'ttr01'), Width=field('int', 8), Height=field('int', 8),
                    Name=field('cexolocstring', {'0': 'Sky test'}), Tag=field('cexostring', AREA), ResRef=field('resref', AREA),
                    Tile_List=field('list', tiles), Version=field('dword', 2), Flags=field('dword', 4),
                    DayNightCycle=field('byte', 1), IsNight=field('byte', 0), SkyBox=field('byte', 16),
                    SunAmbientColor=field('dword', 7895160), SunDiffuseColor=field('dword', 13421772),
                    MoonAmbientColor=field('dword', 3947580), MoonDiffuseColor=field('dword', 6579300),
                    SunFogAmount=field('byte', 0), MoonFogAmount=field('byte', 0), FogClipDist=field('float', 200.0),
                    SunShadows=field('byte', 1), MoonShadows=field('byte', 0), ShadowOpacity=field('byte', 30),
                    ChanceRain=field('int', 0), ChanceSnow=field('int', 0), ChanceLightning=field('int', 0),
                    WindPower=field('int', 1))
    git = structure('GIT ', **{'Creature List': field('list', []), 'Door List': field('list', []), 'Placeable List': field('list', []),
                               'TriggerList': field('list', []), 'WaypointList': field('list', []), 'StoreList': field('list', [])})
    ifo = structure('IFO ', Mod_Name=field('cexolocstring', {'0': 'SRN sky test'}), Mod_Description=field('cexolocstring', {'0': 'skykit'}),
                    Mod_Tag=field('cexostring', 'SRN_SKYTEST'), Mod_Version=field('dword', 3), Mod_MinGameVer=field('cexostring', '1.69'),
                    Mod_IsSaveGame=field('byte', 0), Mod_Entry_Area=field('resref', AREA), Mod_Entry_X=field('float', 40.0),
                    Mod_Entry_Y=field('float', 40.0), Mod_Entry_Z=field('float', 0.0), Mod_Entry_Dir_X=field('float', 0.0),
                    Mod_Entry_Dir_Y=field('float', 1.0), Mod_Area_list=field('list', [{'__struct_id': 6, 'Area_Name': field('resref', AREA)}]),
                    Mod_HakList=field('list', [{'__struct_id': 8, 'Mod_Hak': field('cexostring', HAK)}]),
                    Mod_CustomTlk=field('cexostring', ''), Mod_OnClientEntr=field('resref', 'sk_enter'),
                    Mod_StartYear=field('dword', 2075), Mod_StartMonth=field('byte', 1), Mod_StartDay=field('byte', 1),
                    Mod_StartHour=field('byte', 12), Mod_DawnHour=field('byte', 6), Mod_DuskHour=field('byte', 18),
                    Mod_MinPerHour=field('byte', 2 if transition or play else 60), Mod_XPScale=field('byte', 10))
    factions = [{'__struct_id': i, 'FactionName': field('cexostring', name), 'FactionGlobal': field('word', 1),
                 'FactionParentID': field('dword', 4294967295)} for i, name in enumerate(('PC', 'Hostile', 'Commoner', 'Merchant', 'Defender'))]
    reps = [{'__struct_id': i * 5 + j, 'FactionID1': field('dword', i), 'FactionID2': field('dword', j),
             'FactionRep': field('dword', 0 if {i, j} == {1, 2} else 50)} for i in range(5) for j in range(5) if i != j]
    fac = structure('FAC ', FactionList=field('list', factions), RepList=field('list', reps))
    for filename, document in (('module.ifo', ifo), (AREA + '.are', are), (AREA + '.git', git), ('repute.fac', fac)):
        path = staging / (filename + '.json')
        path.write_text(json.dumps(document), encoding='utf-8')
        run(gff, '-i', path, '-o', binary / filename)
    text, count = play_script() if play else transition_script() if transition else script(SHOTS)
    source = binary / 'sk_enter.nss'
    source.write_text(text, encoding='ascii')
    run(compiler, '--root', nwn_root, '--userdirectory', user, source)
    if not source.with_suffix('.ncs').exists():
        raise RuntimeError('the script compiler wrote no sk_enter.ncs')
    module = user / 'modules' / (MODULE + '.mod')
    module.unlink(missing_ok=True)
    run(erf, '-c', '-f', module, '-e', 'MOD', binary)
    return user, count


def capture(nwn_root, out, wait=0, transition=False):
    from tools.armorkit import client
    from PIL import ImageGrab  # noqa: F401  (the capture needs Pillow's grabber)
    user, count = build(nwn_root, out, transition)
    captures = Path(out).resolve() / 'captures'
    if captures.exists():
        shutil.rmtree(captures)
    captures.mkdir(parents=True)
    if wait:
        client.wait_free(wait)
    (user / 'settings.tml').write_text(client.SETTINGS.format(width=1600, height=900), encoding='utf-8')
    process = client.start(nwn_root, user, MODULE)
    tail = client.LogTail(user, PREFIX)
    taken, done = [], False
    try:
        deadline = time.monotonic() + 120 + count * ((TRANSITION_STEP if transition else HOLD) + 1)
        seen = 0
        while time.monotonic() < deadline and not done:
            time.sleep(0.1)
            if process.poll() is not None:
                raise RuntimeError('the client exited before the shots finished')
            lines = tail.lines()
            for line in lines[seen:]:
                values = client.parse_line(line)
                if 'shot' in values:
                    path = captures / f"{int(values['shot']):02d}-{values['name']}-{values['facing'].split()[0]}.png"
                    client.capture(process.pid, path)
                    taken.append({'line': line, 'file': path.name})
                if line.startswith(PREFIX + ' done'):
                    done = True
            seen = len(lines)
    finally:
        tail.close()
        client.stop(process)
    log = user / 'logs' / 'nwclientLog1.txt'
    if log.is_file():
        shutil.copyfile(log, captures / 'nwclientLog1.txt')
    (captures / 'captures.json').write_text(json.dumps({'finished': done, 'shots': taken, 'expected': count,
                                                        'clientValidated': False}, indent=2), encoding='utf-8')
    return captures, done, taken


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--nwn-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'output' / 'skykit' / 'client')
    parser.add_argument('--wait', type=float, default=0)
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--play', action='store_true', help='start the client on a module with no shots and leave it running for a person')
    parser.add_argument('--transition', action='store_true', help='let time run through dusk and dawn instead of the fixed shots')
    args = parser.parse_args(argv)
    if args.play:
        from tools.armorkit import client
        user, _ = build(args.nwn_root, args.out, play=True)
        if args.wait:
            client.wait_free(args.wait)
        (user / 'settings.tml').write_text(client.SETTINGS.format(width=1600, height=900), encoding='utf-8')
        process = client.start(args.nwn_root, user, MODULE)
        print(json.dumps({'pid': process.pid, 'userDirectory': str(user)}))
        return
    if args.build_only:
        print(build(args.nwn_root, args.out, args.transition))
        return
    captures, done, taken = capture(args.nwn_root, args.out, args.wait, args.transition)
    print(json.dumps({'captures': str(captures), 'finished': done, 'shots': len(taken)}))


if __name__ == '__main__':
    main()
