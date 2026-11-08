"""Reading a head folder and writing batch JSON. Standard library only and no sibling imports, so review tools can import it as headbatch.head_files."""
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{os.getpid()}.tmp')  # readers poll these files, so they never see half of one
    temporary.write_text(json.dumps(data, indent=1)+'\n', encoding='utf-8', newline='\n')
    temporary.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 22), b''):
            digest.update(block)
    return digest.hexdigest()


def attempts(head, stage):
    return sorted((Path(head)/'run'/stage).glob('attempt-*'))


def complete(head, stage):
    """The newest attempt with a complete receipt, or None: a failed one can still hold files (RUNBOOK 142)."""
    for attempt in reversed(attempts(head, stage)):
        if (attempt/'receipt.json').exists() and read(attempt/'receipt.json').get('state') == 'complete':
            return attempt
    return None


def consumed(head, attempt, stage):
    """The attempt of stage that a receipt was built from, or None. The newest attempt of an earlier stage may be a later rerun (RUNBOOK 195, 196).
    By folder name, because a head can be copied away from where it ran; receipts hold Windows paths."""
    row = read(Path(attempt)/'receipt.json').get('dependencies', {}).get(stage)
    return Path(head)/'run'/stage/PureWindowsPath(row['path']).parent.name if row else None


def state(head):
    path = Path(head)/'run'/'state.json'
    return read(path) if path.exists() else {}


def current(head, stage):
    """The attempt folder name headkit holds as this stage's result, or None. A review binds to it, whatever the newest folder is. By folder name: see consumed."""
    row = state(head).get('stages', {}).get(stage)
    return PureWindowsPath(row['path']).parent.name if row else None


def decision(head, stage):
    """A stage's review as headkit counts it (headkit __main__ chain): 'pending' unless it is bound to the current receipt."""
    progress = state(head)
    row = progress.get('reviews', {}).get(stage)
    path = Path(head)/'run'/'reviews'/PureWindowsPath(row['path']).name if row else None
    if path is None or not path.is_file():
        return 'pending'
    review = read(path)
    return review.get('decision') if review.get('stageReceipt') == progress.get('stages', {}).get(stage) else 'pending'


def fit_matrix(head):
    """The manifest's reviewed matrix first, then the fit stage's result (RUNBOOK 100)."""
    head = Path(head)
    fit = read(head/'manifest.json')['fit']
    if 'matrix' in fit:
        return fit['matrix']
    state = head/'run'/'state.json'
    stages = read(state)['stages'] if state.exists() else {}
    return read(stages['fit']['path'])['result']['matrix'] if 'fit' in stages else None
