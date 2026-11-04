"""Up-front repair policies, so repairs do not fail for reasons already known (RUNBOOK 87, 96, 101, 103, 106).

Plans per head; apply writes overrides.json with notes and regenerates the manifest. A lowered UV floor records a review, so only a
person's --apply sets one: the spooler passes keep_floor and only reports the proposal.
1. Fine relief: the user-approved wide profile on non-Human heads that do not declare one. Workspace repairDefaults {"fineRelief": {...}, "skipRaces": [...]} replaces either key.
2. UV floor: when the newest unwrap cleared its floor by under .01, floor = coverage - .011 rounded down to .01, never under .20.
3. Neck cut jaw: slopescan at the declared slope and reach; if the jaw is above the chin limit, the largest reach of .06/.04/.03 that passes."""
import copy
import math
from pathlib import Path
import re
import subprocess

import guards
import head_setup
from workspace import PYTHON

SLOPESCAN = Path(__file__).with_name('review')/'slopescan.py'
UV_MINIMUM = .20
REACHES = (.06, .04, .03)
FINE_RELIEF = {'fineRelief': {'maximumError': .02, 'maximumExtent': .025, 'maximumAreaShare': .0075}, 'skipRaces': ['human']}  # user-approved r3 budget override
SCAN = re.compile(r'jaw z ([-+.\d]+) y ([-+.\d]+) band top ([-+.\d]+) body neck top ([-+.\d]+) (OK|FAIL)')


def slopescan(workspace, head, slope, reach):
    done = subprocess.run([PYTHON, '-B', str(SLOPESCAN), str(head), str(slope), '--reach', str(reach)], capture_output=True, text=True,
                          env=workspace.python_environment(packages=True, tools=True))
    found = SCAN.search(done.stdout)
    if found is None:
        raise guards.Refused(f"{head.name}: slopescan failed: {(done.stderr.strip().splitlines() or ['no output'])[-1]}")
    return {'jaw': float(found[1]), 'band': float(found[3]), 'top': float(found[4]), 'ok': found[5] == 'OK'}


def uv_floor(head, mesh, uv_only, keep_floor, notes, hold):
    uv = mesh.get('uv', {})
    floor = uv.get('minimumCoverage', guards.UV_DEFAULT_FLOOR)
    for attempt in reversed(guards.attempts(head, 'unwrap')):
        if not (attempt/'receipt.json').exists():
            continue
        receipt = guards.read(attempt/'receipt.json')
        coverage = guards.coverage(receipt)
        if coverage is None:
            continue
        if coverage < floor+guards.UV_MARGIN:
            new = math.floor(round((coverage-.011)*100, 6))/100  # .291 would otherwise land on .27
            if new >= UV_MINIMUM and keep_floor:
                notes.append(f'proposed uv floor {floor} -> {new} (coverage {coverage:.3f}), needs a person')
            elif new >= UV_MINIMUM:
                review = f'{attempt.name} coverage {coverage:.3f} cleared floor {floor} by under .01 (RUNBOOK 87): reviewed floor {new}.'
                mesh['uv'] = dict(uv, minimumCoverage=new, coverageReview={'reviewed': True, 'notes': review})
                notes.append(f'uv floor {floor} -> {new} (coverage {coverage:.3f})')
            elif uv_only:
                hold.append(f'UV coverage {coverage:.3f} leaves no floor >= {UV_MINIMUM} (needs fewer charts)')
            else:
                notes.append(f'previous master coverage {coverage:.3f} is under the minimum: the repair changes the mesh, so check the new unwrap')
        return


def jaw_reach(workspace, head, cut, limit, notes, hold, scan):
    if (head/'jaw-reviewed').exists():
        notes.append('jaw reviewed visually')
        return
    slope, reach = cut.get('slope', 0.), cut.get('reach', .04)  # the defaults of headkit neck_policy
    first = scan(workspace, head, slope, reach)
    if first['jaw'] <= limit and first['ok']:
        notes.append(f"jaw OK at reach {reach} (z {first['jaw']*100:.1f} <= {limit*100:.1f} cm)")
    elif first['jaw'] <= limit:  # the chin is right, but the nape band stands above the body neck: a reach change cannot fix it
        hold.append(f"chin OK but the band top {first['band']*100:.1f} cm is above the body neck top {first['top']*100:.1f} at slope {slope}: pick a shallower slope (RUNBOOK 76)")
    else:
        for candidate in REACHES:
            if candidate < reach:
                found = scan(workspace, head, slope, candidate)
                if found['jaw'] <= limit and found['ok']:
                    cut['reach'] = candidate
                    cut['notes'] = cut.get('notes', '')+f" At reach {reach} the jaw search found z {first['jaw']*100:.1f} cm, above the chin limit {limit*100:.1f} (RUNBOOK 103)."
                    notes.append(f"reach {reach} -> {candidate} (jaw {first['jaw']*100:.1f} -> {found['jaw']*100:.1f} cm)")
                    return
        hold.append(f'no reach finds the chin at slope {slope} (limit {limit*100:.1f} cm)')


def plan(workspace, name, uv_only=False, scan=slopescan, keep_floor=False):
    """(overrides, notes, hold, changed). uv_only is the path after an approved repair: fine relief and the cut are repair keys, and changing them stales it (RUNBOOK 106)."""
    head = workspace.head(name)
    overrides = guards.read(head/'overrides.json') if (head/'overrides.json').exists() else {}
    mesh = overrides.setdefault('mesh', {})
    before = copy.deepcopy(overrides)
    notes, hold = [], []
    defaults = {**FINE_RELIEF, **workspace.data.get('repairDefaults', {})}
    if not uv_only and defaults['fineRelief'] and 'fineRelief' not in mesh and name.split('-')[0] not in defaults['skipRaces']:
        mesh['fineRelief'] = dict(defaults['fineRelief'])
        notes.append(f"fineRelief {mesh['fineRelief']}")
    uv_floor(head, mesh, uv_only, keep_floor, notes, hold)
    cut = None if uv_only else mesh.get('neck', {}).get('cut')
    landmarks = workspace.landmarks()
    limit = guards.jaw_limit(head, landmarks) if cut else None
    if cut and limit is not None:
        jaw_reach(workspace, head, cut, limit, notes, hold, scan)
    elif cut:
        notes.append('no landmarks: jaw not checked (visual review)')
    return overrides, notes, hold, overrides != before


def summary(name, notes, hold):
    return f"{name} | {'; '.join(notes) or 'no change'} | {('HOLD: '+'; '.join(hold)) if hold else 'ready'}"


def apply(workspace, name, uv_only=False, scan=slopescan, check=head_setup.validate, keep_floor=False):
    """Returns (summary, held). Overrides change only when a policy actually changed something."""
    overrides, notes, hold, changed = plan(workspace, name, uv_only, scan, keep_floor)
    if changed:
        head_setup.write_manifest(workspace, name, check, overrides)
    return summary(name, notes, hold), bool(hold)
