"""Client trial specs and builds: both sexes of one race in one module, on the workspace's base HAKs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import guards
import launcher
from workspace import PYTHON, RACE_DATA, TOOLS, prefix

BUILD = TOOLS/'heads'/'build_head_trial.py'
ALTERNATE_SKIN_ROWS = (3, 6, 13)
ALTERNATE_HAIR_ROWS = (65, 5, 21)


def pin(path):
    return {'path': Path(path).as_posix(), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def latest(head, stage):
    found = guards.attempts(head, stage)
    return found[-1] if found else None


def rows_with_alternates(chosen, others):
    return [chosen]+[row for row in others if row != chosen][:2]


def head_entry(workspace, name, slot):
    head = workspace.head(name)
    natives = [attempt/'native' for attempt in guards.attempts(head, 'native') if (attempt/'native').is_dir()]
    if not natives:
        return None
    rows = guards.read(latest(head, 'palette')/'receipt.json')['result']['rows']
    # metalRow 0: the game shows stock metal row 0 on heads without armour; palette metal pins only steer previews.
    return {'id': name, 'model': slot, 'native': natives[-1].as_posix(), 'skinRows': rows_with_alternates(rows['0'], ALTERNATE_SKIN_ROWS),
            'hairRows': rows_with_alternates(rows['1'], ALTERNATE_HAIR_ROWS), 'tattoo1Row': rows.get('8', 0), 'tattoo2Row': rows.get('9', 0), 'metalRow': 0, 'helmets': []}


def write_spec(workspace, race, version):
    """specs/trial-RACE-vN.json with each exported head's latest native folder and its chosen palette rows first."""
    base = workspace.data.get('trialBase')
    game = workspace.data.get('game')
    if not base or not game:
        raise guards.Refused('Trials need "trialBase" and "game" in workspace.json')
    heads = [entry for name, (head_race, _, slot) in sorted(workspace.head_ids().items()) if head_race == race
             for entry in [head_entry(workspace, name, slot)] if entry]
    race_row = RACE_DATA['races'][race]
    name = f'srn_rh_{race[:3]}{version}'
    spec = {'kind': 'srn-head-trial-spec', 'trial': f'race-heads-{race}-v{version}', 'hak': name, 'module': name,
            'prefix': [prefix(race, 'male'), prefix(race, 'female')], 'identity': {'appearanceRow': race_row['appearanceRow'], 'raceId': race_row['raceId'], 'visualScale': 1.0},
            'motion': True, 'lighting': 'ambient', 'gameRoot': game['root'], 'client': game['client'],
            'base': {'haks': [pin(workspace.path(hak)) for hak in base['haks']], 'module': pin(workspace.path(base['module'])), 'actorIdentity': base['actorIdentity']},
            'heads': heads}
    out = workspace.root/'specs'/f'trial-{race}-v{version}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=1)+'\n', encoding='utf-8', newline='\n')
    return out, len(heads)


def build(workspace, name, version):
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
    if settings:
        shutil.copy2(settings, output/'userdir'/'settings.tml')  # a windowed client lets screen capture work (RUNBOOK 67)
    return output
