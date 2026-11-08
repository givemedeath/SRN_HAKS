"""Client trial specs and builds: both sexes of one race in one module, on the workspace's base HAKs."""
from pathlib import Path
import re
import tomllib
import subprocess

import guards
from head_files import complete, consumed, sha, write_json
import launcher
from workspace import PYTHON, RACE_DATA, TOOLS, prefix

BUILD = TOOLS/'heads'/'build_head_trial.py'
ALTERNATE_SKIN_ROWS = (3, 6, 13)
ALTERNATE_HAIR_ROWS = (65, 5, 21)


def pin(path):
    return {'path': Path(path).as_posix(), 'sha256': sha(path)}


def rows_with_alternates(chosen, others):
    return [chosen]+[row for row in others if row != chosen][:2]


def head_entry(workspace, name, slot):
    head = workspace.head(name)
    native = complete(head, 'native')
    if native is None or not (native/'native').is_dir():
        return None
    # The rows of the palette this HAK holds: a palette rerun after this native has other shades (RUNBOOK 195).
    export = consumed(head, native, 'export')
    palette = consumed(head, export, 'palette') if export else None
    if palette is None:
        raise guards.Refused(f'{name}: {native.name} of native has no palette lineage, so its rows are unknown')
    rows = guards.read(palette/'receipt.json')['result']['rows']
    material = guards.read(native/'receipt.json').get('result',{}).get('nativeMaterial')
    # metalRow 0: the game shows stock metal row 0 on heads without armour; palette metal pins only steer previews.
    return {'id': name, 'model': slot, 'native': (native/'native').as_posix(), **({'nativeMaterial':material} if material is not None else {}), 'skinRows': rows_with_alternates(rows['0'], ALTERNATE_SKIN_ROWS),
            'hairRows': rows_with_alternates(rows['1'], ALTERNATE_HAIR_ROWS),
            'tattoo1Rows': rows_with_alternates(rows.get('8',0),(0,26)),
            'tattoo2Rows': rows_with_alternates(rows.get('9',0),(0,26)), 'tattoo1Row': rows.get('8', 0), 'tattoo2Row': rows.get('9', 0), 'metalRow': 0, 'helmets': []}


def sized_trial_native(workspace, entry, version):
    """An existing reviewed head may predate the allowance. Derive a fresh trial variant."""
    head = workspace.head(entry['id'])
    manifest = guards.read(head/'manifest.json')
    if manifest.get('nativeSizing') != 'troll-build-allowance-r3':
        return
    native = Path(entry['native']).parent
    export = consumed(head, native, 'export')
    if guards.read(export/'receipt.json')['result'].get('nativeSizing'):
        return
    if not str(version).isdigit():
        raise guards.Refused('Use a numeric version for a sized trial')
    folder = workspace.root/'trials'/'sizing'/str(version)/entry['model']
    folder.mkdir(parents=True, exist_ok=False)
    policy = head/manifest['inputs']['nativeSizingPolicy']['path']
    if sha(policy) != manifest['inputs']['nativeSizingPolicy']['sha256']:
        raise guards.Refused('Trial sizing policy differs from the manifest')
    helper = Path(__file__).with_name('trial_sizing.py')
    args = [helper, native/'receipt.json', policy, head/'mdl-compiler.json', head/'bindings.json', folder]
    frozen = folder/'inputs.json'
    env = workspace.python_environment(packages=True, tools=True)
    with launcher.cpu_slot(workspace):
        subprocess.run([PYTHON,'-B',*args,frozen], env=env, check=True)
        launch = launcher.launch(workspace, folder/'launch', frozen, args, environment=env)
    if launch['exitCode']:
        raise guards.Refused('Trial sizing failed: '+str(folder/'launch'/'stderr.log'))
    entry['native'] = (folder/'native').as_posix()


def inspection_view(workspace, race):
    """Optional measured per-race framing; preserve established defaults when absent."""
    defaults = {'height':{'pmg0':2.52,'pfg0':2.31},'distance':1.05} if race=='troll' else {}
    choices=workspace.data.get('trialInspection',{})
    if not isinstance(choices,dict):
        raise guards.Refused('trialInspection must map race names to framing')
    view=choices.get(race,defaults)
    if not isinstance(view,dict) or set(view)-{'height','distance'}:
        raise guards.Refused('Trial inspection allows height and distance only')
    heights=view.get('height',{}); families={prefix(race,'male'),prefix(race,'female')}
    if (not isinstance(heights,dict) or set(heights)-families or
            any(type(v) not in (int,float) or not .3<=v<=6 for v in heights.values())):
        raise guards.Refused('Trial inspection heights need this race prefixes and 0.3-6 m')
    distance=view.get('distance',1.5)
    if type(distance) not in (int,float) or not .5<=distance<=25:
        raise guards.Refused('Trial inspection distance needs 0.5-25 m')
    return {**view,**({'height':dict(heights)} if 'height' in view else {})}


def write_spec(workspace, race, version):
    """specs/trial-RACE-vN.json with each exported head's latest native folder and its chosen palette rows first."""
    base = workspace.data.get('trialBase')
    game = workspace.data.get('game')
    if not base or not game:
        raise guards.Refused('Trials need "trialBase" and "game" in workspace.json')
    heads = [entry for name, (head_race, _, slot) in sorted(workspace.head_ids().items()) if head_race == race
             for entry in [head_entry(workspace, name, slot)] if entry]
    if race == 'troll':
        for entry in heads:
            sized_trial_native(workspace, entry, version)
    race_row = RACE_DATA['races'][race]
    name = f'srn_rh_{race[:3]}{version}'
    spec = {'kind': 'srn-head-trial-spec', 'trial': f'race-heads-{race}-v{version}', 'hak': name, 'module': name,
            'prefix': [prefix(race, 'male'), prefix(race, 'female')], 'identity': {'appearanceRow': race_row['appearanceRow'], 'raceId': race_row['raceId'], 'visualScale': 1.0},
            'captureCoverageRequired': True, 'inspectionTour': True, 'motion': True, 'lighting': 'ambient', 'gameRoot': workspace.path(game['root']).as_posix(), 'client': workspace.path(game['client']).as_posix(),
            'base': {'haks': [pin(workspace.path(hak)) for hak in base['haks']], 'module': pin(workspace.path(base['module'])), 'actorIdentity': base['actorIdentity']},
            'heads': heads}
    framing=inspection_view(workspace,race)
    if framing:
        spec['inspect']=framing
    from stock_materials import check
    with launcher.cpu_slot(workspace):
        material_check = check(workspace,spec,workspace.root/'specs'/f'materials-{race}-v{version}')
    if material_check is not None:
        spec['stockMaterialCheck'] = material_check
    out = workspace.root/'specs'/f'trial-{race}-v{version}.json'
    write_json(out, spec)
    return out, len(heads)


def inspection_settings(source, output):
    """Bound private QA rendering and neutralize selection feedback; preserve personal settings."""
    data = Path(source).read_text(encoding='utf-8-sig') if source else ''
    before = tomllib.loads(data)
    window = before.get('graphics', {}).get('window', {}).get('windowed', {})
    controls = {
        'ui': {'mouseover-feedback': False, 'targeting-feedback-mode': 0},
        'graphics.framelimiter': {'enabled': True},
        'graphics.framelimiter.foreground': {'target-fps': 30},
        'graphics.framelimiter.background': {'target-fps': 10},
        'graphics.framelimiter.non-interactive': {'target-fps': 10},
        'graphics.window': {'mode': 'windowed'},
        'graphics.window.windowed': {
            'borderless': False,
            'width': min(1920, max(640, int(window.get('width', 1920)))),
            'height': min(1080, max(480, int(window.get('height', 1080))))},
    }
    # Keep the embedded ~~schema byte-for-byte: it is not a live settings table.
    sections = re.split(r'(?m)^(?=[ \t]*\[)', data)
    for table, values in controls.items():
        index = next((i for i, text in enumerate(sections)
                      if text.partition('\n')[0].strip() == f'[{table}]'), None)
        if index is None:
            sections.extend(['\n', f'[{table}]\n'])
            index = len(sections)-1
        lines = sections[index].splitlines(keepends=True)
        if not lines[0].endswith('\n'):
            lines[0] += '\n'
        for key, value in values.items():
            literal = ('true' if value else 'false') if isinstance(value, bool) else (
                '"'+value+'"' if isinstance(value, str) else str(value))
            line = f'\t{key} = {literal}\n'
            old = next((i for i, text in enumerate(lines[1:], 1)
                        if re.match(r'^\s*'+re.escape(key)+r'\s*=', text)), None)
            if old is None:
                lines.insert(1, line)
            else:
                lines[old] = line
        sections[index] = ''.join(lines)
        expected = before
        for part in table.split('.'):
            expected = expected.setdefault(part, {})
        expected.update(values)
    result = ''.join(sections)
    if tomllib.loads(result) != before:
        raise ValueError('Inspection settings changed outside private QA controls')
    Path(output).write_text(result, encoding='utf8')


def build(workspace, name, version):
    """Keep trial freezing/compilation inside the same free-RAM CPU gate as head stages."""
    with launcher.cpu_slot(workspace):
        return _build(workspace,name,version)


def _build(workspace, name, version):
    """Build trials/NAME-vN from specs/trial-NAME-vN.json through the launcher, with its exact consumed inputs."""
    spec = workspace.root/'specs'/f'trial-{name}-v{version}.json'
    output = workspace.root/'trials'/f'{name}-v{version}'
    folder = workspace.root/'trials'/'launches'
    folder.mkdir(parents=True, exist_ok=True)
    inputs = folder/f'inputs-{name}-v{version}.json'
    subprocess.run([PYTHON, '-B', str(BUILD), '--spec', str(spec), '--inputs', str(inputs)], env=workspace.python_environment(), check=True)
    data = launcher.launch(workspace, folder/f'launch-{name}-v{version}', inputs, [BUILD, '--spec', spec, '--output', output])
    if data['exitCode']:
        raise launcher.LaunchFailed(f"Trial build failed (exit {data['exitCode']}): see {folder/f'launch-{name}-v{version}'/'stderr.log'} (RUNBOOK 119)")
    settings = workspace.setting('clientSettings')
    inspection_settings(settings, output/'userdir'/'settings.tml')
    return output
