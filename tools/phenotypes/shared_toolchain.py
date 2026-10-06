"""Resolve byte-pinned shared tools for new phenotype runs."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared_tools import resolve_tool, resolve_addon, resolve_runtime, tools_root, reject_linked


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def load(path, migration=None, required=None):
    path=Path(path).resolve(); data=json.loads(path.read_text(encoding='utf-8'))
    repo=Path(__file__).resolve().parents[2]
    if data.get('schemaVersion')==2 and data.get('kind')=='phenotype-shared-toolchain':
        selected=set(required or data.get('requiredTools', ['python','blender','armory']))
        root,_=tools_root(repo, data.get('toolsRoot'))
        resolved={}
        for name in selected:
            if name in ('python','blender','nwn'):
                binding=data['runtimes'][name]
                resolved[name]=resolve_runtime(name,binding['path'],repo,binding['sha256'])
            else:
                resolved[name]=resolve_tool(name,repo,root)
        data={**data,'tools':resolved,'toolsRoot':str(root),
              'addons':resolve_addon(repo=repo,root=root) if 'blender' in selected else None}
    elif data.get('schemaVersion')!=1 or data.get('kind')!='phenotype-shared-toolchain':
        raise ValueError('Explicit shared toolchain required')
    retiring=Path(data['retiringWorktree']).resolve() if data.get('retiringWorktree') else None
    if data['schemaVersion']==1 and set(data['tools'])!={'armory','blender','python'}:
        raise ValueError('Explicit Armory/Blender/bundled Python tool inventory required')
    for tool in data['tools'].values():
        if retiring and Path(tool['path']).resolve().is_relative_to(retiring):
            raise ValueError('Active tool may not use the retiring worktree')
    for name,tool in data['tools'].items():
        if sha(tool['path'])!=tool['sha256']:raise ValueError('Shared tool binary changed: '+tool['path'])
        resolve_runtime(name,tool['path'],repo,tool['sha256'])
    if data['addons']:
        _verify_addons(data['addons'], retiring, repo)
    if migration:
        _verify_migration(path, migration)
        receipt=json.loads(Path(migration).read_text(encoding='utf-8'))
        requested=set(required) if required is not None else set(data['tools'])
        if receipt.get('scope')=='head-tools' and not requested <= set(receipt['allowedTools']):
            raise ValueError('Head-only migration does not cover this tool; run its full migration')
    return data


def _verify_addons(addons, retiring, repo):
    root=Path(addons['root']).resolve()
    if retiring and root.is_relative_to(retiring):raise ValueError('Active addons may not use the retiring worktree')
    reject_linked(root,repo)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and
            '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    if actual!=set(addons['files']):raise ValueError('Shared addon source inventory changed')
    for relative,expected in addons['files'].items():
        target=(root/relative).resolve()
        if not target.is_relative_to(root) or sha(target)!=expected:
            raise ValueError('Shared addon bytes changed: '+relative)
def _verify_migration(path, migration):
        receipt=json.loads(Path(migration).read_text(encoding='utf-8'))
        if receipt.get('kind')!='phenotype-shared-tool-migration' or not receipt.get('smokeChecksPassed'):
            raise ValueError('Passed shared tool migration receipt required')
        if Path(receipt['toolchain']['path']).resolve()!=path or receipt['toolchain']['sha256']!=sha(path):
            raise ValueError('Migration receipt does not bind this toolchain')
        for helper,expected in receipt.get('launchHelpers',{}).items():
            if sha(helper)!=expected['sha256']:
                raise ValueError('Migrated launch helper changed; freeze a new receipt: '+helper)
        if receipt.get('scope')=='head-tools':
            if set(receipt.get('allowedTools',[])) != {'python','blender'} or not receipt.get('frozenSmokeFiles'):
                raise ValueError('Head migration needs explicit bounded scope and frozen smokes')
            for item in receipt['frozenSmokeFiles']:
                if sha(item['path']) != item['sha256']:
                    raise ValueError('Head migration smoke changed: '+item['path'])
