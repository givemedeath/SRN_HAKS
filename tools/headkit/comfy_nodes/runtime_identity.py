"""Capture the Python and Torch runtime actually executing inside ComfyUI."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import sysconfig
from .verification import CURRENT_PASS


def _pin(path, *, canonical=False):
    path=Path(path) if canonical else Path(path).resolve(strict=True)
    session=CURRENT_PASS.get()
    if session is not None:return {'path':str(path),'sha256':session.hash(path,canonical=True)}
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return {'path':str(path),'sha256':digest.hexdigest()}


def _linked(path):
    if isinstance(path,os.DirEntry):
        # Windows scandir already has the file attributes; reuse them instead of
        # resolving every ancestor and querying each leaf twice.
        return path.is_symlink() or bool(getattr(path.stat(follow_symlinks=False),'st_file_attributes',0)&0x400)
    return path.is_symlink() or getattr(os.path,'isjunction',lambda value:False)(path)


def _inside(path, roots):
    return any(path==root or path.is_relative_to(root) for root in roots)


# Runtime implementation/configuration, native kernels and compiler inputs.
# Documentation, sample images, test datasets and distribution RECORD listings
# are not executable inputs. Explicitly loaded module origins are always included.
RUNTIME_EXTENSIONS={'.py','.pyw','.pyi','.pyx','.pxd','.pxi','.pth','.pyd','.dll','.so','.dylib','.exe',
                    '.zip','.whl','.json','.yaml','.yml','.toml','.ini','.cfg','.conf',
                    '.h','.hpp','.c','.cc','.cpp','.cu','.cuh','.ptx','.cubin','.fatbin','.bc',
                    '.lib','.a','.o','.obj','.hsaco','.cl','.hlsl','.glsl','.vert','.frag',
                    '.jinja','.jinja2','.j2','.cmake','.lds'}


def runtime_members(roots):
    """Fresh membership census of active runtime roots, without inactive site trees."""
    roots=set(roots);files=set()
    def visit(directory):
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in {'__pycache__','.git','.hg','.svn'}:continue
                path=directory/entry.name
                if entry.is_dir(follow_symlinks=False):
                    # The base interpreter's bundled site-packages is not used
                    # by a venv unless it is an explicit active import root.
                    if entry.name in {'site-packages','dist-packages'} and path not in roots:continue
                    if _linked(entry):raise ValueError('Linked Comfy runtime directories are unsupported')
                    visit(path)
                else:
                    if _linked(entry):raise ValueError('Linked Comfy runtime files are unsupported')
                    if (path.suffix.lower() in RUNTIME_EXTENSIONS or '.so.' in path.name
                            or entry.name in {'CMakeLists.txt','Makefile'}
                            or (directory.name.endswith('.dist-info') and entry.name in {'METADATA','entry_points.txt'})):
                        files.add(path)
    for root in sorted(roots,key=lambda value:str(value).casefold()):
        if not any(root!=other and root.is_relative_to(other) for other in roots):visit(root)
    return files


def seal_runtime_identity(payload):
    payload=dict(payload)
    payload.pop('fingerprint',None)
    payload['fingerprint']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return payload


def same_runtime_environment(current, baseline):
    """Compare stable interpreter/runtime pins while allowing verified lazy imports."""
    ignored={'fingerprint','loadedSourceCode'}
    return ({key:value for key,value in current.items() if key not in ignored}
            == {key:value for key,value in baseline.items() if key not in ignored})


def capture_runtime_identity(folder_paths,comfy_source_inventory=None,loaded_source_code=None):
    """Hash runtime implementation bytes; Comfy source has its own complete census."""
    import torch
    core=Path(folder_paths.base_path).resolve(strict=True)
    covered=[str(core)]
    covered_paths=[core]
    roots=set()
    for key in ('stdlib','platstdlib','purelib','platlib'):
        value=sysconfig.get_paths().get(key)
        if value:
            path=Path(value)
            if path.is_dir():roots.add(path.resolve(strict=True))
    archives=set()
    for value in sys.path:
        path=Path(value or os.getcwd())
        if not path.exists():continue
        path=path.resolve(strict=True)
        if path.is_file() and path.suffix.lower() in ('.zip','.whl'):
            archives.add(path);continue
        if _inside(path,covered_paths):continue
        if path.is_dir():roots.add(path)
    torch_path=Path(torch.__file__).resolve(strict=True)
    if not any(torch_path==path or torch_path.is_relative_to(path) for path in roots):
        roots.add(torch_path.parent)

    ordered=sorted(roots,key=lambda value:(len(value.parts),str(value).casefold()))
    unique_roots=[]
    for path in ordered:
        if not _inside(path,unique_roots):unique_roots.append(path)
    # Keep nested explicit site roots available to the membership policy even
    # when the parent stdlib root covers them.
    files=runtime_members(roots)
    source_files={Path(row['path']) for row in (comfy_source_inventory or {}).get('files',[])}
    for module in tuple(sys.modules.values()):
        namespace=getattr(module,'__dict__',{})
        origin=namespace.get('__file__') if isinstance(namespace,dict) else None
        if isinstance(origin,str):
            path=Path(origin)
            if path.suffix.lower() in {'.pyc','.pyo'}:continue
            if path.is_absolute() and _inside(path,unique_roots):
                if path.resolve(strict=True)!=path or _linked(path):
                    raise ValueError('Linked loaded runtime module is unsupported')
                files.add(path)
    files.difference_update(source_files)
    executable_path=Path(sys.executable).resolve(strict=True)
    files.add(executable_path)
    for sibling in executable_path.parent.iterdir():
        if sibling.is_file() and sibling.suffix.lower() in ('.dll','.so','.dylib') and sibling.name.lower().startswith('python'):
            files.add(sibling.resolve(strict=True))
    files.update(archives)
    files.add(torch_path)
    # One explicit pass shares hashes with source/loaded-code verification.
    # ContextVars do not propagate into executor workers. Keep the four-reader
    # implementation for standalone callers, and bind each worker explicitly.
    session=CURRENT_PASS.get()
    def file_pin(path):
        token=CURRENT_PASS.set(session)
        try:return _pin(path,canonical=True)
        finally:CURRENT_PASS.reset(token)
    with ThreadPoolExecutor(max_workers=4) as workers:
        file_pins=list(workers.map(file_pin,sorted(files,key=lambda path:str(path).casefold())))
    cudnn=None
    try:cudnn=torch.backends.cudnn.version()
    except Exception:pass
    executable=str(Path(sys.executable).resolve(strict=True))
    payload={
        'schemaVersion':2,
        'python':{'path':executable,'sha256':next(item['sha256'] for item in file_pins if item['path']==executable),
                  'version':sys.version,'implementation':sys.implementation.name,'cacheTag':sys.implementation.cache_tag,
                  'prefix':str(Path(sys.prefix).resolve()),'basePrefix':str(Path(sys.base_prefix).resolve())},
        'torch':{'path':str(torch_path),'sha256':next(item['sha256'] for item in file_pins if item['path']==str(torch_path)),
                 'version':str(torch.__version__),'cuda':getattr(torch.version,'cuda',None),
                 'hip':getattr(torch.version,'hip',None),'cudnn':cudnn},
        'coveredSourceRoots':covered,
        'roots':[str(path) for path in unique_roots],
        'files':file_pins,
        'comfySourceInventory':comfy_source_inventory,
        'loadedSourceCode':loaded_source_code or [],
    }
    return seal_runtime_identity(payload)
