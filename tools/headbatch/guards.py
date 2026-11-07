"""Checks that refuse a launch before it spends CPU. Each one answers a confirmed batch mistake (docs/heads/race-heads-v1-runbook.md)."""
from contextlib import ExitStack, contextmanager
import json
import os
import re
import time

from gpu_job import geometry_limit, submissions
from head_files import attempts, current, fit_matrix, read
from headkit.comfy import locked
from workspace import TOOLS

DESIGN_CAP = 3
UV_MARGIN = 0.01
UV_DEFAULT_FLOOR = 0.30
LOOP_BUDGET = {'repair': 3, 'ownership': 2, 'tone': 4, 'palette': 3, 'render': 3}
STAGES_ON_REVIEWED_ROWS = {'export', 'native', 'render'}
DELETE_TRIES = 5
COVERAGE = re.compile(r'Insufficient useful UV coverage(?: after face priority)? \(([.\d]+) at 2K')


class Refused(Exception):
    pass


def coverage(receipt):
    """2K UV coverage from an unwrap receipt, passed or refused for coverage; None for any other failure."""
    if receipt.get('result'):
        return receipt['result']['pixelAudits']['2048']['coverageFraction']
    found = COVERAGE.search(str(receipt.get('error', '')))
    return float(found[1]) if found else None


def crlf_in_pinned_code():
    """Launches pin headkit bytes, and a CRLF copy never matches them (RUNBOOK 94)."""
    bad = [path.name for pattern in ('*.py', '*.json') for path in (TOOLS/'headkit').glob(pattern) if b'\r' in path.read_bytes()]
    if bad:
        raise Refused(f'CRLF in pinned headkit code (RUNBOOK 94): {bad}')


def clean_stray_bytecode(bindings):
    """Remove bytecode the package pins do not list, then refuse any other unpinned file (RUNBOOK 90, 155). Returns what it removed."""
    packages = read(bindings)['pythonPackages']
    key = lambda path: os.path.normcase(os.path.abspath(path))  # pins are canonical paths, and this runs on thousands of files per launch
    root = os.path.abspath(packages['directory'])
    pinned = {key(row['path'] if isinstance(row, dict) else row) for row in packages['files']}
    removed, left = [], []
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            if key(path) in pinned:
                continue
            relative = os.path.relpath(path, root).replace(os.sep, '/')
            if name.endswith('.pyc') and remove(path):
                removed.append(relative)
            else:
                left.append(relative)
    if left:
        raise Refused(f'Unpinned files in the bound package tree (RUNBOOK 90): {sorted(left)[:5]}')
    return sorted(removed)


def remove(path):
    """Launches that start together clean the same tree, and on Windows the loser of a delete can see access denied until the winner's finishes (RUNBOOK 194, 198)."""
    for _ in range(DELETE_TRIES):
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            time.sleep(.05)
    return not os.path.exists(path)


def ownership_rules(head):
    ownership = read(head/'manifest.json')['ownership']
    if ownership.get('mode') == 'rules' and not ownership.get('rules'):
        raise Refused(f'{head.name}: ownership has no rules (RUNBOOK 98)')


def uv_margin(head):
    """A repair moves coverage by up to 0.01, so a head must clear its floor by that much before the repair runs (RUNBOOK 87)."""
    floor = read(head/'manifest.json')['mesh'].get('uv', {}).get('minimumCoverage', UV_DEFAULT_FLOOR)
    for attempt in reversed(attempts(head, 'unwrap')):
        receipt = read(attempt/'receipt.json') if (attempt/'receipt.json').exists() else {}
        if receipt.get('result'):
            covered = coverage(receipt)
            if covered < floor+UV_MARGIN:
                raise Refused(f'{head.name}: {attempt.name} coverage {covered:.3f} is too close to floor {floor}: set a reviewed mesh.uv floor before rerunning repair (RUNBOOK 87)')
            return


def loop_budget(head, stages, limits=None):
    """Stop iterating at the budget; a HEAD/budget-override-STAGE file records a deliberate exception."""
    budget = {**LOOP_BUDGET, **(limits or {})}
    for stage in stages:
        count = len(attempts(head, stage))
        if stage not in budget or count < budget[stage]:
            continue
        limit = budget[stage]
        override = head/f'budget-override-{stage}'
        if override.exists():
            try:
                record = read(override)
            except (ValueError,OSError) as exc:
                raise Refused(f'{head.name}: {stage} needs a bounded JSON budget exception') from exc
            maximum = record.get('maximumAttempts') if isinstance(record,dict) else None
            if (type(maximum) is not int or maximum <= limit or record.get('head') != head.name
                    or record.get('stage') != stage or not isinstance(record.get('approval'),str)
                    or not record['approval'].strip()):
                raise Refused(f'{head.name}: invalid head/stage/maximumAttempts/approval in {override.name}')
            limit = maximum
        if count >= limit:
            raise Refused(f'{head.name}: {stage} already has {count} attempts (limit {limit}): report it, or add budget-override-{stage}')


def geometry_cap(head):
    """User rule: at most 5 geometry submissions per head slot, reseeds and out-of-memory failures included."""
    ledger = head/'gpu'/'gpu.json'
    count = submissions(head/'gpu', read(ledger) if ledger.exists() else {})
    try:
        limit = geometry_limit(head)
    except ValueError as exc:
        raise Refused(str(exc)) from exc
    if count >= limit:
        raise Refused(f'{head.name}: {count} geometry submissions reached the cap of {limit}: stop and ask the user')


def design_cap(folder, head):
    """User rule: at most 3 designs per head slot, each launch counted, refused ones included. design/design-cap-override-HEAD records the user's exception."""
    count = len(list((folder/'launches').glob(f'launch-*-{head}-s*')))
    # External proposals and conditioning edits spend the same slot budget as local launches.
    count += sum(1 for entry in (folder/'external-attempts'/head).glob('*.json') if entry.is_file())
    if count < DESIGN_CAP:
        return
    exception = folder/f'design-cap-override-{head}'
    if not exception.exists():
        raise Refused(f'{head}: {count} designs reached the cap of {DESIGN_CAP}: stop and ask the user')
    try:
        data = json.loads(exception.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise Refused(f'{head}: design exception must contain an explicit bounded JSON approval') from error
    limit = data.get('maximumDesigns') if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get('head') != head or type(limit) is not int
            or limit <= DESIGN_CAP or not isinstance(data.get('approval'), str) or not data['approval'].strip()):
        raise Refused(f'{head}: invalid bounded design exception')
    if count >= limit:
        raise Refused(f'{head}: {count} designs reached the user-authorized cap of {limit}: stop and ask the user')


def rows_reviewed(workspace, name):
    path = workspace.spool/'reviewed-rows.json'
    return path.exists() and read(path).get(name) == read(workspace.head(name)/'manifest.json')['palette'].get('rows', {})


def palette_rows(workspace, name, stages):
    """Export and later stages ship the rows, so they run only on rows a person reviewed, however they are launched (RUNBOOK 112)."""
    if STAGES_ON_REVIEWED_ROWS & set(stages) and not rows_reviewed(workspace, name):
        raise Refused(f'{name}: palette rows are not in reviewed-rows.json (RUNBOOK 112)')


def approved_attempt(head, stage, attempt):
    """Headkit binds an approval to the stage's current attempt, so the one the approval was given for must still be it (RUNBOOK 200)."""
    now = current(head, stage)
    if attempt != now:
        raise Refused(f'{head.name}: {attempt} of {stage} was reviewed, but the current attempt is {now}: review that one')


def jaw_limit(head, landmarks):
    """Highest allowed jaw height: half the eye-to-lip distance below the lip seam (a chin is 0.6-0.9 of it below). None without marks."""
    marks = landmarks.get(head.name, {}).get('source') if landmarks else None
    matrix = fit_matrix(head) if marks else None
    if not matrix:
        return None
    # design_landmarks gives yawed head-local xyz. The fit matrix consumes NWN
    # basis coordinates before that yaw; a tilted fit makes the depth sign matter.
    height = {key: -matrix[2][0]*x - matrix[2][1]*y + matrix[2][2]*z + matrix[2][3]
              for key, (x,y,z) in marks.items()}
    eye = (height['eyeLeft']+height['eyeRight'])/2
    return height['lips']-.5*(eye-height['lips'])


def jaw(head, landmarks, attempt=None):
    """Refuse a repair approval whose neck cut can reach the mouth, unless HEAD/jaw-reviewed records a visual review (RUNBOOK 103).
    Checks the named attempt, or else the newest with an audit. Returns what was checked: no marks, no audit, or an explicit cut height (no jaw line) checks nothing, and a report must say so (RUNBOOK 189)."""
    if (head/'jaw-reviewed').exists():
        return 'jaw reviewed visually'
    limit = jaw_limit(head, landmarks)
    if limit is None:
        return 'jaw not checked: no face marks'
    for folder in [head/'run'/'repair'/attempt] if attempt else reversed(attempts(head, 'repair')):
        audit = folder/'reduction-audit.json'
        if audit.exists():
            line = ((read(audit).get('neck') or {}).get('cut') or {}).get('jawLine')
            if line is None:
                return f'jaw not checked: {folder.name} has no jaw line'
            height = line['point'][2]
            if not height <= limit:  # a mark off the mesh gives a NaN limit, which must not pass
                raise Refused(f'{head.name}: {folder.name} jaw {height*100:.1f} cm is above the chin limit {limit*100:.1f} cm: review, then add jaw-reviewed (RUNBOOK 103)')
            return f'jaw OK: {folder.name} {height*100:.1f} cm <= {limit*100:.1f}'
    return 'jaw not checked: no repair audit'


def unwrap_gates(receipt):
    """(passed, summary) from one unwrap receipt's result: no bad faces, no gutter bleed, subtexel pass, geometry unchanged."""
    last = receipt['attempts'][-1]
    gutters = {size: sum(row['nearbyChartPixelsByRadius'].values()) for size, row in receipt['gutters'].items()}
    subtexel = all(row['passed'] for row in last['subtexel'].values())
    passed = last['badFaceCount'] == 0 and not any(gutters.values()) and subtexel and receipt['geometryUnchanged']
    return passed, f"charts {receipt['charts']} bad faces {last['badFaceCount']} gutters {gutters} subtexel {subtexel}"


def head_lock(workspace, name):
    """Held by a launch from queueing to its end; the system frees it if the process dies (RUNBOOK 190). Busy raises FileExistsError."""
    return locked(workspace.locks/f'head-{name}')


@contextmanager
def head_locks(workspace, names):
    """One launch per head: headkit refuses a second runner on a head outright, which would lose every head of that launch (RUNBOOK 190)."""
    with ExitStack() as stack:
        for name in names:
            try:
                stack.enter_context(head_lock(workspace, name))
            except FileExistsError:
                raise Refused(f'{name}: another launch of this head is queued or running (RUNBOOK 190)') from None
        yield


@contextmanager
def only_spooler(workspace):
    """Two spoolers would both pass one result's numeric gate and launch its next stage twice, and each would overwrite the other's state (RUNBOOK 207)."""
    with ExitStack() as stack:
        try:
            stack.enter_context(locked(workspace.locks/'spooler'))
        except FileExistsError:
            raise Refused('Another spooler is running on this workspace') from None
        yield


def head_busy(workspace, name):
    """A head's manifest is a pinned input, so rewriting it under a queued or running launch invalidates that launch (RUNBOOK 49, 111)."""
    try:
        with head_lock(workspace, name):
            return False
    except FileExistsError:
        return True
