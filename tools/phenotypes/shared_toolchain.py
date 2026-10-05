"""Resolve byte-pinned shared tools for new phenotype runs."""
import hashlib
import json
from pathlib import Path


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def load(path, migration=None):
    path=Path(path).resolve(); data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('schemaVersion')!=1 or data.get('kind')!='phenotype-shared-toolchain':
        raise ValueError('Explicit shared toolchain required')
    retiring=Path(data['retiringWorktree']).resolve()
    if set(data['tools'])!={'armory','blender','python'}:
        raise ValueError('Explicit Armory/Blender/bundled Python tool inventory required')
    for tool in data['tools'].values():
        if Path(tool['path']).resolve().is_relative_to(retiring):
            raise ValueError('Active tool may not use the retiring worktree')
        if sha(tool['path'])!=tool['sha256']:raise ValueError('Shared tool binary changed: '+tool['path'])
    root=Path(data['addons']['root']).resolve()
    if root.is_relative_to(retiring):raise ValueError('Active addons may not use the retiring worktree')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and
            '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    if actual!=set(data['addons']['files']):raise ValueError('Shared addon source inventory changed')
    for relative,expected in data['addons']['files'].items():
        target=(root/relative).resolve()
        if not target.is_relative_to(root) or sha(target)!=expected:
            raise ValueError('Shared addon bytes changed: '+relative)
    if migration:
        receipt=json.loads(Path(migration).read_text(encoding='utf-8'))
        if receipt.get('kind')!='phenotype-shared-tool-migration' or not receipt.get('smokeChecksPassed'):
            raise ValueError('Passed shared tool migration receipt required')
        if Path(receipt['toolchain']['path']).resolve()!=path or receipt['toolchain']['sha256']!=sha(path):
            raise ValueError('Migration receipt does not bind this toolchain')
        for helper,expected in receipt.get('launchHelpers',{}).items():
            if sha(helper)!=expected['sha256']:
                raise ValueError('Migrated launch helper changed; freeze a new receipt: '+helper)
    return data
