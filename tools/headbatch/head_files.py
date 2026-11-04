"""Reading a head folder and writing batch JSON. Standard library only and no sibling imports, so review tools can import it as headbatch.head_files."""
import hashlib
import json
import os
from pathlib import Path


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


def fit_matrix(head):
    """The manifest's reviewed matrix first, then the fit stage's result (RUNBOOK 100)."""
    head = Path(head)
    fit = read(head/'manifest.json')['fit']
    if 'matrix' in fit:
        return fit['matrix']
    state = head/'run'/'state.json'
    stages = read(state)['stages'] if state.exists() else {}
    return read(stages['fit']['path'])['result']['matrix'] if 'fit' in stages else None
