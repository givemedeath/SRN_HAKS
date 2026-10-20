"""Membership and byte snapshots of the configured Comfy/Pixal implementation trees."""
import os
from pathlib import Path
from .common import require,verify

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
    inputs={(str(Path(p['path']).resolve()),p['sha256']) for p in prepared['inputs']}
    require(all((row['path'],row['sha256']) in inputs for row in inventory['files']),'Source inventory is absent from frozen request inputs')
    return inventory
