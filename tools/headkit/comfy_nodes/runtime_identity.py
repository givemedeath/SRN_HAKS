"""Capture the Python and Torch runtime actually executing inside ComfyUI."""
import hashlib
import json
import os
from pathlib import Path
import sys
import sysconfig


def _pin(path):
    path=Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Comfy runtime file is missing')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return {'path':str(path),'sha256':digest.hexdigest()}


def _linked(path):
    return path.is_symlink() or getattr(os.path,'isjunction',lambda value:False)(path)


def _inside(path, roots):
    return any(path==root or path.is_relative_to(root) for root in roots)


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
    """Hash interpreter, standard library and active Python import roots, excluding separately pinned Comfy source."""
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
    files=set()
    def fail_walk(error):
        raise error
    for runtime_root in unique_roots:
        for current,dirs,names in os.walk(runtime_root,followlinks=False,onerror=fail_walk):
            current=Path(current)
            dirs[:]=[name for name in dirs if name!='__pycache__']
            for name in dirs:
                path=current/name
                if _linked(path):raise ValueError('Linked Comfy runtime directories are unsupported')
            for name in names:
                path=current/name
                if _linked(path):raise ValueError('Linked Comfy runtime files are unsupported')
                resolved=path.resolve(strict=True)
                if not resolved.is_relative_to(runtime_root):raise ValueError('Comfy runtime file escapes its inventory root')
                files.add(resolved)
    executable_path=Path(sys.executable).resolve(strict=True)
    files.add(executable_path)
    for sibling in executable_path.parent.iterdir():
        if sibling.is_file() and sibling.suffix.lower() in ('.dll','.so','.dylib') and sibling.name.lower().startswith('python'):
            files.add(sibling.resolve(strict=True))
    files.update(archives)
    files.add(torch_path)
    file_pins=sorted((_pin(path) for path in files),key=lambda item:item['path'].casefold())
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
