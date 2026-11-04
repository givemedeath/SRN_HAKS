"""Checks that refuse a launch before it spends CPU. Each one answers a confirmed batch mistake (docs/heads/race-heads-v1-runbook.md)."""
from pathlib import Path
import re

from gpu_job import GEOMETRY_CAP
from head_files import attempts, fit_matrix, read  # noqa: F401
from workspace import TOOLS

UV_MARGIN = 0.01
UV_DEFAULT_FLOOR = 0.30
LOOP_BUDGET = {'repair': 3, 'ownership': 2, 'tone': 4, 'palette': 3, 'render': 3}
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
    root = Path(packages['directory']).resolve()
    pinned = {Path(row['path'] if isinstance(row, dict) else row).resolve() for row in packages['files']}
    removed = []
    for path in sorted(root.rglob('*.pyc')):
        if path.resolve() not in pinned:
            path.unlink()
            removed.append(path.relative_to(root).as_posix())
    left = sorted(path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file() and path.resolve() not in pinned)
    if left:
        raise Refused(f'Unpinned files in the bound package tree (RUNBOOK 90): {left[:5]}')
    return removed


def ownership_rules(head):
    ownership = read(head/'manifest.json')['ownership']
    if ownership.get('mode') == 'rules' and not ownership.get('rules'):
        raise Refused(f'{head.name}: ownership has no rules (RUNBOOK 98)')


def uv_margin(head):
    """A repair moves coverage by up to 0.01, and a floor set afterwards stales it, so it must clear the floor first (RUNBOOK 87)."""
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
        if stage in budget and count >= budget[stage] and not (head/f'budget-override-{stage}').exists():
            raise Refused(f'{head.name}: {stage} already has {count} attempts (limit {budget[stage]}): report it, or add budget-override-{stage}')


def geometry_cap(head):
    """User rule: at most 5 geometry submissions per head slot, reseeds and out-of-memory failures included."""
    ledger = head/'gpu'/'gpu.json'
    count = read(ledger).get('geometrySubmissions', 0) if ledger.exists() else 0
    if count >= GEOMETRY_CAP and not (head/'geometry-cap-override').exists():
        raise Refused(f'{head.name}: {count} geometry submissions reached the cap of {GEOMETRY_CAP}: stop and ask the user')


def jaw_limit(head, landmarks):
    """Highest allowed jaw height: half the eye-to-lip distance below the lip seam (a chin is 0.6-0.9 of it below). None without marks."""
    marks = landmarks.get(head.name, {}).get('source') if landmarks else None
    matrix = fit_matrix(head) if marks else None
    if not matrix:
        return None
    height = {key: sum(a*b for a, b in zip(matrix[2], [*value, 1.0])) for key, value in marks.items()}
    eye = (height['eyeLeft']+height['eyeRight'])/2
    return height['lips']-.5*(eye-height['lips'])


def jaw(head, landmarks):
    """Refuse a repair approval whose neck cut can reach the mouth, unless HEAD/jaw-reviewed records a visual review (RUNBOOK 103)."""
    limit = jaw_limit(head, landmarks)
    if limit is None or (head/'jaw-reviewed').exists():
        return
    for attempt in reversed(attempts(head, 'repair')):
        audit = attempt/'reduction-audit.json'
        cut = read(audit)['neck'].get('cut') if audit.exists() else None
        if cut and 'jawLine' in cut:
            height = cut['jawLine']['point'][2]
            if height > limit:
                raise Refused(f'{head.name}: {attempt.name} jaw {height*100:.1f} cm is above the chin limit {limit*100:.1f} cm: review, then add jaw-reviewed (RUNBOOK 103)')
            return


def unwrap_gates(receipt):
    """(passed, summary) from one unwrap receipt's result: no bad faces, no gutter bleed, subtexel pass, geometry unchanged."""
    last = receipt['attempts'][-1]
    gutters = {size: sum(row['nearbyChartPixelsByRadius'].values()) for size, row in receipt['gutters'].items()}
    subtexel = all(row['passed'] for row in last['subtexel'].values())
    passed = last['badFaceCount'] == 0 and not any(gutters.values()) and subtexel and receipt['geometryUnchanged']
    return passed, f"charts {receipt['charts']} bad faces {last['badFaceCount']} gutters {gutters} subtexel {subtexel}"


def head_busy(workspace, name):
    """A head's manifest is a pinned input, so rewriting it under a queued or running launch invalidates that launch (RUNBOOK 49, 111)."""
    for marker in workspace.launches.glob('active-*.json'):
        if name in read(marker)['heads']:
            return marker
    return None
