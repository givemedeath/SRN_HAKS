"""Run a built itemkit fixture in the game client unattended and file what its scripted shots showed.

    python -m tools.itemkit.client_capture FIXTURE_DIR CAPTURES --nwn-root GAME_INSTALL

FIXTURE_DIR is the folder holding `fixture.json` (the fixture stage's output). The fixture's entry script carries a
dormant shot sequence (fixture.SHOTS): this driver switches it on with a 2DA in the fixture's own override folder,
starts the client through armorkit's client module, saves a short burst of window captures after every
`ITEMKIT_SHOT` line and stops the client it started. A client that is already running blocks the run.

The result is evidence to review, never a review: `evidence-draft.json` lists the captures and log per body and
required check with `result: "unreviewed"`. A person looks at the pictures and writes the client evidence.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.headkit.common import pin, read, require, verify, write
from tools.itemkit.fixture import CHECKS, SHOTS, SHOT_ACTORS, SHOT_CYCLE, SHOT_HOLD, SHOT_TOGGLE

PREFIX = 'ITEMKIT_'
DONE = 'ITEMKIT_SHOTS done'
TOGGLE_TABLE = '2DA V2.0\n\n   On\n0  1\n'
FRAMES, GAP, SETTLE = 3, 0.5, 0.3
BODIES = dict(SHOT_ACTORS)


def shot_rows(lines):
    """Every `ITEMKIT_SHOT` line as a dict with integer shot and step, in log order."""
    from tools.armorkit.client import parse_line
    rows = []
    for line in lines:
        if line.startswith('ITEMKIT_SHOT '):
            values = parse_line(line)
            rows.append({'shot': int(values['shot']), 'target': values['target'], 'check': values['check'],
                         'step': int(values['step']), 'valid': values.get('valid') == '1'})
    return rows


def evidence_draft(shots, log_name, checks=CHECKS):
    """Captures grouped by body and required check. Unreviewed by construction; lists what was not captured."""
    rows, missing = [], []
    for tag, body in SHOT_ACTORS:
        for check in checks:
            files = [name for shot in shots if shot['target'] == tag and shot['check'] == check and not shot.get('rejected')
                     for name in shot['captures']]
            if files:
                rows.append({'body': body, 'check': check, 'result': 'unreviewed', 'reviewedBy': '', 'notes': '',
                             'screenshots': files, 'logs': [log_name]})
            else:
                missing.append({'body': body, 'check': check})
    return {'observations': rows, 'missing': missing, 'reviewRequired': True}


def run(nwn_root, fixture_dir, captures, *, timeout=None, frames=FRAMES, gap=GAP, settle=SETTLE):
    from tools.armorkit import client
    fixture_dir = Path(fixture_dir); captures = Path(captures)
    record = read(fixture_dir / 'fixture.json'); verify([record['module'], record['hak'], *record['fixtureHaks']])
    user = Path(record['userDirectory']); module = Path(record['module']['path']).stem
    require(settle + (frames - 1) * gap + .3 <= SHOT_HOLD, 'The capture burst must end inside a shot')
    total = len(SHOTS) * len(SHOT_ACTORS)
    # Two full motion cycles reach every shot unless the camera was contended twice; allow a third.
    timeout = 60 + 3 * SHOT_CYCLE * 6 if timeout is None else timeout
    captures.mkdir(parents=True, exist_ok=False)
    toggle = user / 'override' / (SHOT_TOGGLE + '.2da'); toggle.parent.mkdir(exist_ok=True)
    require(not toggle.exists(), 'A scripted-shot toggle is already in this fixture; another capture may be running')
    (user / 'settings.tml').write_text(client.SETTINGS.format(width=1600, height=900), encoding='utf-8')
    toggle.write_text(TOGGLE_TABLE, encoding='ascii')
    shots, seen, finished = [], 0, False
    try:
        process = client.start(nwn_root, user, module)
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not finished:
                time.sleep(.2)
                require(process.poll() is None, 'The client exited before the fixture finished')
                lines = client.log_lines(user, PREFIX)
                for row in shot_rows(lines[seen:]):
                    body = BODIES.get(row['target']); require(body and row['valid'], f"Shot {row['shot']} has no actor to look at")
                    time.sleep(settle); names = []
                    for frame in range(frames):
                        name = f"{body}-{row['check']}-{row['shot']:02d}-{frame}.png"
                        client.capture(process.pid, captures / name); names.append(name)
                        if frame < frames - 1: time.sleep(gap)
                    # A burst that ran into the next shot shows the wrong thing: keep the files, never file them.
                    newest = shot_rows(client.log_lines(user, PREFIX))[-1]['shot']
                    shots.append({**row, 'body': body, 'captures': names, **({'rejected': 'next shot began'} if newest != row['shot'] else {})})
                seen = len(lines); finished = DONE in lines
        finally:
            client.stop(process)
    finally:
        toggle.unlink(missing_ok=True)
    log = user / 'logs' / 'nwclientLog1.txt'
    if log.is_file(): shutil.copyfile(log, captures / 'nwclientLog1.txt')
    lines = client.log_lines(user, PREFIX)
    result = {'fixture': pin(fixture_dir / 'fixture.json'), 'module': record['module'], 'hak': record['hak'],
              'fixtureHaks': record['fixtureHaks'], 'finished': finished, 'shotsExpected': total, 'shots': shots,
              'equipped': [line for line in lines if line.startswith('ITEMKIT_EQUIPPED')],
              'failures': [line for line in lines if 'FAILED' in line],
              'clientValidated': False, 'productionAccepted': False}
    write(captures / 'capture.json', result, fresh=True)
    write(captures / 'evidence-draft.json', {'module': record['module'], 'hak': record['hak'], 'fixtureHaks': record['fixtureHaks'],
                                             **evidence_draft(shots, 'nwclientLog1.txt')}, fresh=True)
    require(finished, f'The fixture did not finish its shots within {timeout} s ({len(shots)} of {total} captured)')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('fixture', type=Path); parser.add_argument('captures', type=Path)
    parser.add_argument('--nwn-root', type=Path, required=True, help='game install folder (holds bin/win32/nwmain.exe)')
    parser.add_argument('--timeout', type=float)
    a = parser.parse_args(argv)
    result = run(a.nwn_root, a.fixture, a.captures, timeout=a.timeout)
    rejected = [shot['shot'] for shot in result['shots'] if shot.get('rejected')]
    print(json.dumps({'captures': str(a.captures), 'shots': len(result['shots']), 'expected': result['shotsExpected'],
                      'rejected': rejected, 'equipped': result['equipped'], 'failures': result['failures']}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
