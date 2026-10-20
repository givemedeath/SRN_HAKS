"""Membership and byte snapshots of the configured Comfy/Pixal implementation trees."""
import os
from pathlib import Path
import re
from .common import digest,pin,require,verify

# Generated data and model weights have their own inputs; execution code/config/native binaries do not.
EXTENSIONS={'.py','.pyx','.pyi','.json','.yaml','.yml','.toml','.pyd','.so','.dll','.dylib','.ptx','.cubin','.h','.hpp','.c','.cpp','.cu','.cuh'}
CORE_DATA={'input','output','temp','models','user','.venv','venv'}
REQUIRED_CORE={'main.py','execution.py','nodes.py','server.py','folder_paths.py'}


def members(core,roots):
    core=Path(core).resolve();require(core in roots,'Inventory must cover the Comfy root')
    found=set()
    for root in roots:
        require(root.is_dir(),'Missing Comfy source root')
        for current,dirs,files in os.walk(root,followlinks=False):
            current=Path(current)
            dirs[:]=[name for name in dirs if name not in {'.git','.hg','.svn','__pycache__'}
                     and not (current==core and name in CORE_DATA)]
            for name in dirs:
                require((current/name).resolve()==(current/name).absolute(),'Linked source directories need an explicit unlinked installation')
            for name in files:
                path=current/name
                if path.name=='source-roots.json' and path.parent.name=='srn_headkit':continue
                if path.suffix.lower() in EXTENSIONS:
                    require(path.resolve()==path.absolute(),'Linked Comfy source file is unsupported')
                    found.add(path.resolve())
    require({core/name for name in REQUIRED_CORE}<=found,'Incomplete Comfy core source inventory')
    require(any(path.is_relative_to(core/'comfy') for path in found),'Missing Comfy model implementation tree')
    names={path.name for path in found}
    require({'nodes_trellis2.py','flexgemm.py','model.py'}<=names,'Missing Pixal/Trellis/FlexGEMM implementation inventory')
    require(any(path.suffix.lower() in {'.pyd','.so','.dll','.dylib'} for path in found),'Missing compiled implementation inventory')
    return found


def verify_sources(inventory):
    require(isinstance(inventory,dict) and set(inventory)=={'core','roots','files'},'Complete Comfy source inventory required')
    core=Path(inventory['core']).resolve();roots=[Path(p).resolve() for p in inventory['roots']]
    require(roots and len(set(roots))==len(roots),'Unique source roots required')
    actual=members(core,roots);rows=inventory['files']
    require(len(rows)==len(actual) and {Path(row['path']).resolve() for row in rows}==actual,'Comfy source inventory membership changed or incomplete')
    verify(rows)
    return inventory


def capture_sources(core,roots):
    core=Path(core).resolve();roots=[Path(root).resolve() for root in roots]
    paths=members(core,roots)
    return {'core':str(core),'roots':[str(root) for root in roots],
            'files':[pin(path) for path in sorted(paths,key=lambda value:str(value).casefold())]}


def _same_inventory(left,right):
    if not isinstance(left,dict) or not isinstance(right,dict):return False
    if set(left)!={'core','roots','files'} or set(right)!={'core','roots','files'}:return False
    try:
        left_files={row['path']:row['sha256'] for row in left['files']}
        right_files={row['path']:row['sha256'] for row in right['files']}
    except (TypeError,KeyError):return False
    return left['core']==right['core'] and left['roots']==right['roots'] and left_files==right_files \
        and len(left_files)==len(left['files']) and len(right_files)==len(right['files'])


def validate_comfy_runtime(identity, source_roots=None, source_inventory=None):
    """Validate the live Comfy interpreter/Torch identity returned by its installed adapter."""
    required={'schemaVersion','python','torch','coveredSourceRoots','roots','files','comfySourceInventory','loadedSourceCode','fingerprint'}
    require(isinstance(identity,dict) and set(identity)==required and identity['schemaVersion']==2,
            'Complete live Comfy runtime identity required')
    payload={key:value for key,value in identity.items() if key!='fingerprint'}
    require(isinstance(identity['fingerprint'],str) and digest(payload)==identity['fingerprint'],
            'Live Comfy runtime fingerprint is invalid')
    python=identity['python'];torch=identity['torch'];files=identity['files']
    require(isinstance(python,dict) and set(python)=={'path','sha256','version','implementation','cacheTag','prefix','basePrefix'}
            and isinstance(torch,dict) and set(torch)=={'path','sha256','version','cuda','hip','cudnn'},
            'Live Comfy Python/Torch details are incomplete')
    require(isinstance(identity['coveredSourceRoots'],list) and identity['coveredSourceRoots']
            and isinstance(identity['roots'],list) and identity['roots']
            and all(isinstance(path,str) and Path(path).is_absolute() for path in identity['coveredSourceRoots']+identity['roots']),
            'Live Comfy runtime roots must be absolute')
    inventory=identity['comfySourceInventory']
    require(isinstance(inventory,dict) and set(inventory)=={'core','roots','files'}
            and isinstance(inventory['core'],str) and Path(inventory['core']).is_absolute()
            and isinstance(inventory['roots'],list) and inventory['roots']
            and all(isinstance(path,str) and Path(path).is_absolute() for path in inventory['roots'])
            and isinstance(inventory['files'],list),'Live Comfy source snapshot is incomplete')
    if source_inventory is not None:
        require(_same_inventory(inventory,source_inventory),
                'Comfy startup source snapshot differs from the prepared source inventory')
    if source_roots is not None:
        expected={str(Path(value).resolve()) for value in source_roots}
        require(len(identity['coveredSourceRoots'])==1 and identity['coveredSourceRoots'][0] in expected,
                'Comfy runtime source coverage differs from the request')
    source_by_path={row.get('path'):row.get('sha256') for row in inventory['files'] if isinstance(row,dict)}
    require(len(source_by_path)==len(inventory['files']) and all(isinstance(path,str) and Path(path).is_absolute()
            and isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) for path,value in source_by_path.items()),
            'Live Comfy source snapshot contains malformed file pins')
    loaded=identity['loadedSourceCode']
    require(isinstance(loaded,list) and all(isinstance(row,dict) and set(row)=={'path','sourceSha256','loadedCodeSha256'}
            and isinstance(row['path'],str) and Path(row['path']).is_absolute()
            and isinstance(row['sourceSha256'],str) and re.fullmatch(r'[0-9a-f]{64}',row['sourceSha256'])
            and isinstance(row['loadedCodeSha256'],str) and re.fullmatch(r'[0-9a-f]{64}',row['loadedCodeSha256']) for row in loaded),
            'Loaded Comfy Python code identity is malformed')
    loaded_paths=[row['path'] for row in loaded]
    require(len(loaded_paths)==len(set(loaded_paths)) and loaded_paths==sorted(loaded_paths,key=str.casefold),
            'Loaded Comfy Python code identity must be unique and sorted')
    require(all(source_by_path.get(row['path'])==row['sourceSha256'] for row in loaded),
            'Loaded Comfy Python code is not bound to its reviewed source file')
    require(isinstance(files,list) and files,'Live Comfy runtime file inventory required')
    require(all(isinstance(row,dict) and set(row)=={'path','sha256'} and Path(row['path']).is_absolute()
                and re.fullmatch(r'[0-9a-f]{64}',row['sha256']) for row in files),
            'Malformed live Comfy runtime file inventory')
    paths=[row['path'] for row in files]
    require(len(paths)==len(set(paths)) and paths==sorted(paths,key=str.casefold),
            'Live Comfy runtime file inventory must be unique and sorted')
    by_path={row['path']:row['sha256'] for row in files}
    require(by_path.get(python['path'])==python['sha256'] and by_path.get(torch['path'])==torch['sha256'],
            'Live Comfy runtime omits the executing Python or Torch module')
    require(isinstance(python['version'],str) and isinstance(torch['version'],str)
            and (torch['cuda'] is None or isinstance(torch['cuda'],str))
            and (torch['hip'] is None or isinstance(torch['hip'],str))
            and (torch['cudnn'] is None or type(torch['cudnn']) is int),
            'Live Comfy runtime versions are malformed')
    return identity


def freeze_sources(local):
    require(local.get('comfyRoot') and local.get('comfySources'),'Complete Comfy source tree bindings required')
    core=Path(local['comfyRoot']).resolve()
    roots=[core]+[Path(p).resolve() for p in local.get('comfyDependencyRoots',[])]
    custom=Path(local['comfyCustomNodes']).resolve()
    require(any(custom.is_relative_to(root) for root in roots),'Custom nodes are outside the inventoried source roots')
    inventory={'core':str(core),'roots':[str(p) for p in roots],
               'files':[{'path':str(Path(p['path']).resolve()),'sha256':p['sha256']} for p in local['comfySources']]}
    return verify_sources(inventory)


def request_sources(prepared):
    inventory=verify_sources(prepared.get('comfySourceInventory'))
    runtime=validate_comfy_runtime(prepared.get('comfyRuntimeIdentity'),inventory['roots'],inventory)
    inputs={(str(Path(p['path']).resolve()),p['sha256']) for p in prepared['inputs']}
    require(all((row['path'],row['sha256']) in inputs for row in inventory['files']),'Source inventory is absent from frozen request inputs')
    require(all((row['path'],row['sha256']) in inputs for row in runtime['files']),'Comfy runtime inventory is absent from frozen request inputs')
    return inventory
