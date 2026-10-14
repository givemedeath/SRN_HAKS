"""Small evidence primitives for the measurement-only phenotype workflow."""
import hashlib
import json
import os
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def pin(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def safe_relative(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root), 'Input escapes its declared root: ' + name)
    return path


def verified(path, expected):
    require(sha(path) == expected, 'Input bytes changed: ' + str(path))
    snapshot = os.environ.get('SRN_VERIFIED_INPUTS')
    if snapshot:
        require(read(snapshot)['files'].get(str(Path(path).resolve())) == expected,
                'Consumed input not declared to launcher: ' + str(path))
    return pin(path)
