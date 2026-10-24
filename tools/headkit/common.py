"""Strict file contracts, local tool bindings, and immutable run receipts."""
from __future__ import annotations
import hashlib
import importlib
import json
import math
import os
import time
from pathlib import Path
import re
import sys
import tempfile
from .comfy_nodes.verification import CURRENT_PASS,verification_pass

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


_HASHES = {}


def sha(path, *, fresh=False):
    """SHA-256 of a file. Inside an explicit verification pass each file is read once per pass, never reused
    across passes. Elsewhere, within one process an unchanged file (same identity, size and modification time,
    before and after reading) is hashed once; fresh=True always rereads, for checks that must catch edits made
    during a stage. Only files last modified more than two seconds before hashing are cached (the racy-timestamp
    rule), so a rewrite within one filesystem timestamp tick cannot reuse a stale digest."""
    session=CURRENT_PASS.get()
    if session is not None and not fresh:return session.hash(path)
    path = Path(path)
    before = path.stat()
    key = (str(path.resolve()), before.st_ino, before.st_size, before.st_mtime_ns)
    if not fresh and key in _HASHES:
        return _HASHES[key]
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    after = path.stat()
    if (after.st_ino, after.st_size, after.st_mtime_ns) == key[1:] and time.time_ns() - after.st_mtime_ns > 2_000_000_000:
        _HASHES[key] = result.hexdigest()
    return result.hexdigest()


def read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def pin(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def verify(pins, *, fresh=False):
    verified={}
    for item in pins:
        require(isinstance(item, dict) and set(item) >= {'path', 'sha256'}, 'Expected file pin')
        path=str(item['path'])
        if 'slice' in item:actual=runner_slice_sha(item['path'], item['slice'], fresh=fresh)
        else:
            if path not in verified:verified[path]=sha(path, fresh=fresh)
            actual=verified[path]
        require(actual == item['sha256'], 'Stale file pin: ' + path)


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
    allowed = {'schemaVersion', 'id', 'inputs', 'features', 'alignment', 'matte', 'camera', 'mesh',
               'paint', 'ownership', 'tone', 'palette', 'fit', 'render', 'approval', 'profile'}
    require(set(data) <= allowed and data.get('schemaVersion') == 1, 'Unsupported manifest keys/version')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', data.get('id', '')) is not None, 'Safe asset ID required')
    require(data.get('profile', 'pixal-single-v1') in ('pixal-single-v1', 'pixal-multiview-v1'), 'Unsupported generation profile')
    require(isinstance(data.get('inputs'), dict), 'Named pinned inputs required')
    for item in data['inputs'].values():
        asset(path, item)
    budget = data.get('mesh', {}).get('triangleBudget', 20000)
    require(type(budget) is int and 4 <= budget <= 20000, 'Initial supported runtime budget is <=20K')
    return data


# Set by the runner around a stage: names of the byte-bound libraries the stage actually loads.
LIBRARIES_USED = None


def library(bindings, name):
    """Load only a completely inventoried, byte-bound installation."""
    if LIBRARIES_USED is not None: LIBRARIES_USED.add(name)
    row = bindings.get('libraries', {}).get(name)
    require(isinstance(row, dict) and isinstance(row.get('directory'), str)
            and isinstance(row.get('files'), list) and row['files'],
            'Missing local library binding: ' + name)
    verify(row['files'])
    directory = Path(row['directory']).resolve(strict=True)
    tools_root = Path(bindings['toolsRoot']).resolve()
    require(directory.is_relative_to(tools_root), 'Library must be inside the declared durable tools bank')
    require(directory.is_dir(), 'Library installation root must be a directory')

    def inventory():
        paths=set()
        is_junction=getattr(os.path,'isjunction',lambda path:False)
        for path in directory.rglob('*'):
            require(not path.is_symlink() and not is_junction(path),
                    'Library installation cannot contain unpinned links')
            if path.is_file():
                resolved=path.resolve(strict=True)
                require(resolved.is_relative_to(directory),
                        'Library file escapes its installation root')
                paths.add(resolved)
        return paths

    pinned=[Path(item['path']).resolve(strict=True) for item in row['files']]
    pinned_set=set(pinned)
    require(len(pinned)==len(pinned_set) and all(path.is_relative_to(directory) for path in pinned_set)
            and pinned_set==inventory(),
            'Library file pins must enumerate the complete installation membership')

    sys.path.insert(0, str(directory))
    write_bytecode=sys.dont_write_bytecode
    sys.dont_write_bytecode=True
    try:
        try:
            module = importlib.import_module(name)
        finally:
            sys.path.pop(0)
    finally:
        sys.dont_write_bytecode=write_bytecode
    verify(row['files'])
    require(pinned_set==inventory(),
            'Library installation membership changed while importing: ' + name)
    require(Path(module.__file__).resolve(strict=True) in pinned_set,
            'Imported library is not the byte-bound module: ' + name)
    return module


def bindings(path):
    data = read(path)
    require(data.get('schemaVersion') == 1 and isinstance(data.get('toolsRoot'), str), 'Local bindings version/root required')
    require(Path(data['toolsRoot']).is_absolute(), 'Local tools root must be absolute')
    tools_root = Path(data['toolsRoot']).resolve()
    for key in ('python', 'blender', 'client', 'embree'):
        if key in data:
            if key == 'embree':
                require(Path(data[key]['path']).resolve().is_relative_to(tools_root),
                        'Embree DLL must be inside the declared durable tools bank')
            verify([data[key]])
    for row in data.get('libraries', {}).values():
        verify(row['files'])
    return data


def python_package_pins(data, *, require_imports=False):
    """Verify the complete, byte-bound Python site-packages tree used by CPU stages."""
    row = data.get('pythonPackages')
    require(isinstance(row, dict) and isinstance(row.get('directory'), str)
            and isinstance(row.get('files'), list) and row['files'],
            'Missing complete Python package installation binding')
    configured_directory = Path(row['directory'])
    directory = configured_directory.resolve(strict=True)
    tools_root = Path(data['toolsRoot']).resolve()
    is_junction = getattr(os.path, 'isjunction', lambda path: False)

    def has_link_component(path):
        return any(candidate.is_symlink() or is_junction(candidate)
                   for candidate in (path, *path.parents))

    require(configured_directory.is_absolute() and not has_link_component(configured_directory)
            and directory.is_dir() and directory.is_relative_to(tools_root),
            'Python package installation must be a canonical directory inside the declared durable tools bank')

    pins = row['files']
    verify(pins)
    pinned = []
    for item in pins:
        configured_path = Path(item['path'])
        resolved = configured_path.resolve(strict=True)
        require(configured_path.is_absolute() and not has_link_component(configured_path),
                'Python package file pins must use canonical non-link paths')
        pinned.append(resolved)
    pinned_set = set(pinned)
    require(len(pinned) == len(pinned_set) and all(path.is_file() and path.is_relative_to(directory)
            for path in pinned_set), 'Python package file pins must be unique files under the installation root')

    def inventory():
        files = set()
        for path in directory.rglob('*'):
            require(not path.is_symlink() and not is_junction(path),
                    'Python package installation cannot contain unpinned links')
            if path.is_file():
                resolved = path.resolve(strict=True)
                require(resolved.is_relative_to(directory), 'Python package file escapes its installation root')
                files.add(resolved)
        return files

    files = inventory()
    require(pinned_set == files,
            'Python package file pins must enumerate the complete installation membership')

    if require_imports:
        sys.path.insert(0, str(directory))
        try:
            for name in ('numpy', 'PIL', 'scipy'):
                module = importlib.import_module(name)
                origin = Path(module.__file__).resolve(strict=True)
                require(origin.is_relative_to(directory) and origin in pinned_set,
                        'Required Python package resolves outside its byte-bound installation: ' + name)
                locations = list(getattr(module, '__path__', ()))
                require(locations and all(Path(location).resolve(strict=True).is_relative_to(directory)
                        for location in locations),
                        'Required Python package has an unbound search location: ' + name)
        finally:
            sys.path.remove(str(directory))
        verify(pins)
        require(pinned_set == inventory(),
                'Python package installation membership changed while importing required packages')
    return pins


def launched(bindings_path=None):
    """Identify the actual launcher and reject separately recorded runtime bindings."""
    require(os.environ.get('SRN_SHARED_TOOLCHAIN') and os.environ.get('SRN_SHARED_TOOL_MIGRATION'),
            'Run processing through tools/phenotypes/launch_shared_tool.py with a fresh migration receipt')
    sys.path.insert(0, str(ROOT / 'tools/phenotypes'))
    from shared_toolchain import load
    toolchain=Path(os.environ['SRN_SHARED_TOOLCHAIN']).resolve()
    migration=Path(os.environ['SRN_SHARED_TOOL_MIGRATION']).resolve()
    active=load(toolchain,migration,required=['python'])
    python=active['tools']['python']
    require(Path(sys.executable).resolve()==Path(python['path']).resolve() and pin(sys.executable)['sha256']==python['sha256'],
            'Executing Python differs from the verified launcher runtime')
    identity={'toolchain':pin(toolchain),'migrationReceipt':pin(migration),'python':pin(sys.executable),
              'toolsRoot':str(Path(active['toolsRoot']).resolve())}
    if bindings_path is not None:
        local=bindings(bindings_path)
        for name in ('toolchain','migrationReceipt'):
            require(name in local and pin(local[name])==identity[name], 'Local bindings differ from active launcher: '+name)
        require(local.get('python') and Path(local['python']['path']).resolve()==Path(identity['python']['path'])
                and local['python']['sha256']==identity['python']['sha256'], 'Local Python differs from active launcher')
        require(str(Path(local['toolsRoot']).resolve())==identity['toolsRoot'], 'Local tools bank differs from active launcher')
        if 'blender' in local:
            selected=active.get('runtimes',active['tools']).get('blender')
            require(selected and Path(selected['path']).resolve()==Path(local['blender']['path']).resolve()
                    and selected['sha256']==local['blender']['sha256'],'Local Blender differs from active toolchain')
    return identity


def code_pins():
    directory=Path(__file__).parent
    files=[p for p in sorted(directory.rglob('*')) if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts]
    files += [ROOT/path for path in ('tools/heads/head_export.py','tools/heads/head_workflow.py',
        'tools/heads/verify_head_hak.py','tools/phenomorpher/phenomorpher/__init__.py',
        'tools/phenomorpher/phenomorpher/engine/__init__.py','tools/phenomorpher/phenomorpher/engine/stock_armor.py',
        'tools/phenomorpher/phenomorpher/engine/silhouette_model.py','tools/phenomorpher/phenomorpher/engine/anim_library.py',
        'tools/phenomorpher/phenomorpher/engine/audit_geometry.py','tools/phenomorpher/phenomorpher/engine/retarget.py',
        'tools/phenomorpher/phenomorpher/engine/target_contract.py','tools/phenomorpher/phenomorpher/engine/measurement_common.py',
        'tools/phenomorpher/phenomorpher/engine/native_motion.py','tools/phenotypes/pipeline.py',
        'tools/phenotypes/height_targets.json','tools/shared-tools.lock.json',
        'tools/phenotypes/bootstrap_shared_blender_addons.py',
        'tools/phenotypes/native_compile.py','tools/phenotypes/launch_shared_tool.py',
        'tools/phenotypes/shared_toolchain.py','tools/phenotypes/tool_runtime.py','tools/shared_tools.py')]
    return [pin(p) for p in files]


def source_version():
    return digest({Path(item['path']).relative_to(ROOT).as_posix():item['sha256'] for item in code_pins()})


# Stage-scoped code identity: a receipt binds the code that can change its result, not the whole package, so a fix in
# one stage's module no longer stales every finished stage. Core: the runner (dispatch, inputs, gates) and common;
# tests, the CLI and GPU-side modules are excluded. Shared tooling binds every stage; native helpers bind the stages
# whose closure reaches native.py.
SHARED_TOOLING=('tools/shared-tools.lock.json','tools/phenotypes/bootstrap_shared_blender_addons.py','tools/phenotypes/launch_shared_tool.py',
    'tools/phenotypes/shared_toolchain.py','tools/phenotypes/tool_runtime.py','tools/shared_tools.py')
NATIVE_HELPERS=('tools/heads/head_export.py','tools/heads/head_workflow.py','tools/heads/verify_head_hak.py',
    'tools/phenomorpher/phenomorpher/__init__.py','tools/phenomorpher/phenomorpher/engine/__init__.py',
    'tools/phenomorpher/phenomorpher/engine/stock_armor.py','tools/phenomorpher/phenomorpher/engine/silhouette_model.py',
    'tools/phenomorpher/phenomorpher/engine/anim_library.py','tools/phenomorpher/phenomorpher/engine/audit_geometry.py',
    'tools/phenomorpher/phenomorpher/engine/retarget.py','tools/phenomorpher/phenomorpher/engine/target_contract.py',
    'tools/phenomorpher/phenomorpher/engine/measurement_common.py','tools/phenomorpher/phenomorpher/engine/native_motion.py',
    'tools/phenotypes/pipeline.py','tools/phenotypes/height_targets.json','tools/phenotypes/native_compile.py')
STAGE_SCRIPTS={'render':('blender_render.py',)}  # run in a subprocess, not imported
STAGE_DATA={'palette':('stock-shades.json',)}  # committed measured references the stage reads


def module_path(name, directory):
    """File of a closure name; a dotted name is a subpackage module, 'pkg.__init__' its package body."""
    return Path(directory).joinpath(*name.split('.')).with_suffix('.py')


def module_closure(names, directory):
    """Package modules reachable from names through relative imports, function-level imports included.
    Importing a subpackage module also runs its package __init__, so both are reached."""
    import ast
    seen=set();pending=list(names)
    while pending:
        name=pending.pop();path=module_path(name,directory)
        if name in seen or not path.is_file():continue
        seen.add(name);package=name.split('.')[:-1]
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not isinstance(node,ast.ImportFrom) or not node.level or node.level-1>len(package):continue
            base=package[:len(package)-node.level+1];module=base+(node.module.split('.') if node.module else [])
            for target in [module]*bool(node.module)+[module+[alias.name] for alias in node.names]:
                pending+=['.'.join(target[:i])+'.__init__' for i in range(1,len(target)+1)]+['.'.join(target)]
    return seen


def _stage_branch(node):
    """The stage name of an `if stage=='x':` statement, else None."""
    import ast
    test=getattr(node,'test',None)
    if (isinstance(node,ast.If) and isinstance(test,ast.Compare) and isinstance(test.left,ast.Name) and test.left.id=='stage'
            and len(test.ops)==1 and isinstance(test.ops[0],ast.Eq) and isinstance(test.comparators[0],ast.Constant)):
        return test.comparators[0].value
    return None


def _execute_node(tree):
    import ast
    return next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_execute')


_SLICES={}


def runner_slice(path, stage):
    """runner.py without the other stages' top-level `if stage=='x':` branches of Runner._execute: a receipt binds the shared
    dispatch, dependencies and gates plus its own branch, so an edit inside another stage's branch leaves it fresh.
    A branch with an else/elif is never dropped (its range would cover other code)."""
    import ast
    text=Path(path).read_text(encoding='utf-8');lines=text.splitlines(keepends=True);drop=set()
    for node in _execute_node(ast.parse(text)).body:
        name=_stage_branch(node)
        if name is not None and name!=stage and not node.orelse:drop.update(range(node.lineno-1,node.end_lineno))
    return ''.join(line for index,line in enumerate(lines) if index not in drop)


def runner_slice_sha(path, stage, *, fresh=False):
    path=Path(path);before=path.stat();key=(str(path.resolve()),before.st_ino,before.st_size,before.st_mtime_ns,stage)
    if not fresh and key in _SLICES:return _SLICES[key]
    value=hashlib.sha256(runner_slice(path,stage).encode('utf-8')).hexdigest()
    if path.stat().st_mtime_ns==before.st_mtime_ns and time.time()-before.st_mtime_ns/1e9>2:_SLICES[key]=value
    return value


def stage_entries(directory):
    """The modules each `if stage=='x':` branch of Runner._execute imports, read from the runner source."""
    import ast
    tree=ast.parse((directory/'runner.py').read_text(encoding='utf-8'));entries={}
    for node in ast.walk(_execute_node(tree)):
        name=_stage_branch(node)
        if name is not None:
            found=entries.setdefault(name,set())
            for inner in ast.walk(node):
                if isinstance(inner,ast.ImportFrom) and inner.level==1:
                    found.update([inner.module.split('.')[0]] if inner.module else [alias.name for alias in inner.names])
    return entries


def stage_code_files(stage, directory=None, root=None):
    directory=Path(directory or Path(__file__).parent);root=Path(root or ROOT)
    entries=stage_entries(directory);require(stage in entries,'No runner branch for stage: '+stage)
    modules=module_closure(entries[stage]|{'common'},directory)
    files={module_path(name,directory) for name in modules}|{directory/name for name in ('__init__.py','runner.py','manifest.schema.json')}
    files|={directory/name for name in STAGE_SCRIPTS.get(stage,())+STAGE_DATA.get(stage,())}
    files|={root/path for path in SHARED_TOOLING+(NATIVE_HELPERS if 'native' in modules else ())}
    return sorted(path for path in files if path.is_file())


def stage_code_pins(stage):
    # The runner is bound by this stage's slice; every other file whole.
    runner=(Path(__file__).parent/'runner.py').resolve()
    return [{'path':str(runner),'sha256':runner_slice_sha(runner,stage),'slice':stage} if Path(path).resolve()==runner else pin(path)
            for path in stage_code_files(stage)]


def stage_file_pins(stage):
    """Whole-file pins of the stage's code, for subprocess launchers that hash the files themselves."""
    return [pin(path) for path in stage_code_files(stage)]


def stage_source_version(stage):
    return digest({Path(item['path']).relative_to(ROOT).as_posix():item['sha256'] for item in stage_code_pins(stage)})
