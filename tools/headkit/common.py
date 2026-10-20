"""Strict file contracts, local tool bindings, and immutable run receipts."""
from __future__ import annotations
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def pin(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def verify(pins):
    for item in pins:
        require(isinstance(item, dict) and set(item) >= {'path', 'sha256'}, 'Expected file pin')
        require(sha(item['path']) == item['sha256'], 'Stale file pin: ' + str(item['path']))


def write(path, data, *, fresh=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if fresh:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    else:
        fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def positive(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and value > 0, 'Positive finite ' + name + ' required')
    return float(value)


def asset(manifest_path, item):
    require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'Assets need relative paths and SHA256')
    relative = Path(item['path'])
    require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts,
            'Portable asset paths must stay within the manifest folder')
    path = (Path(manifest_path).resolve().parent / relative).resolve()
    require(path.is_relative_to(Path(manifest_path).resolve().parent), 'Asset link escapes manifest folder')
    result = {'path': str(path), 'sha256': item['sha256']}
    verify([result])
    return result


def manifest(path):
    data = read(path)
    allowed = {'schemaVersion', 'id', 'inputs', 'features', 'alignment', 'camera', 'mesh',
               'ownership', 'tone', 'palette', 'fit', 'render', 'approval', 'profile'}
    require(set(data) <= allowed and data.get('schemaVersion') == 1, 'Unsupported manifest keys/version')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', data.get('id', '')) is not None, 'Safe asset ID required')
    require(data.get('profile', 'pixal-single-v1') in ('pixal-single-v1', 'pixal-multiview-v1'), 'Unsupported generation profile')
    require(isinstance(data.get('inputs'), dict), 'Named pinned inputs required')
    for item in data['inputs'].values():
        asset(path, item)
    budget = data.get('mesh', {}).get('triangleBudget', 20000)
    require(type(budget) is int and 4 <= budget <= 20000, 'Initial supported runtime budget is <=20K')
    return data


def library(bindings, name):
    """Load only the explicitly byte-bound installation; never another worktree's copy."""
    row = bindings.get('libraries', {}).get(name)
    require(isinstance(row, dict) and row.get('files'), 'Missing local library binding: ' + name)
    verify(row['files'])
    directory = Path(row['directory']).resolve()
    tools_root = Path(bindings['toolsRoot']).resolve()
    require(directory.is_relative_to(tools_root), 'Library must be inside the declared durable tools bank')
    sys.path.insert(0, str(directory))
    try:
        module = importlib.import_module(name)
    finally:
        sys.path.pop(0)
    require(Path(module.__file__).resolve() in {Path(p['path']).resolve() for p in row['files']},
            'Imported library is not the byte-bound module: ' + name)
    return module


def bindings(path):
    data = read(path)
    require(data.get('schemaVersion') == 1 and isinstance(data.get('toolsRoot'), str), 'Local bindings version/root required')
    require(Path(data['toolsRoot']).is_absolute(), 'Local tools root must be absolute')
    for key in ('python', 'blender', 'client', 'embree'):
        if key in data:
            verify([data[key]])
    for row in data.get('libraries', {}).values():
        verify(row['files'])
    return data


def launched():
    """Numerical/external work uses the maintained shared launcher and fresh migration."""
    require(os.environ.get('SRN_SHARED_TOOLCHAIN') and os.environ.get('SRN_SHARED_TOOL_MIGRATION'),
            'Run processing through tools/phenotypes/launch_shared_tool.py with a fresh migration receipt')
    sys.path.insert(0, str(ROOT / 'tools/phenotypes'))
    from shared_toolchain import load
    load(Path(os.environ['SRN_SHARED_TOOLCHAIN']), Path(os.environ['SRN_SHARED_TOOL_MIGRATION']), required=['python'])


def code_pins():
    directory=Path(__file__).parent
    files=[p for p in sorted(directory.rglob('*')) if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts]
    files += [ROOT/path for path in ('tools/heads/head_export.py','tools/heads/head_workflow.py',
        'tools/heads/verify_head_hak.py','tools/phenomorpher/phenomorpher/engine/stock_armor.py',
        'tools/phenotypes/native_compile.py','tools/phenotypes/launch_shared_tool.py',
        'tools/phenotypes/shared_toolchain.py','tools/phenotypes/tool_runtime.py','tools/shared_tools.py')]
    return [pin(p) for p in files]


def source_version():
    return digest({Path(item['path']).relative_to(ROOT).as_posix():item['sha256'] for item in code_pins()})
