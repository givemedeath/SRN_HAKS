"""Blender-free preview bridge to the audited rigid-pose sampler."""
import json
from pathlib import Path
import re
import shutil

import retarget
import rig_controller_audit
import rig_pose_audit
import target_contract
from retarget import nodes
from rig_controller_audit import CLIP
from rig_pose_audit import sample
from target_contract import sha, require


def helper_paths():
    return [Path(module.__file__).resolve() for module in
            (retarget,rig_controller_audit,rig_pose_audit,target_contract)]+[Path(__file__).resolve()]


def helper_inputs():
    return {str(path):sha(path) for path in helper_paths()}


def freeze_helpers(output, additional=()):
    """Snapshot imported sampler dependencies; reject later source mutations."""
    directory=output/'executed-preview-helpers'
    require(not directory.exists(),'Fresh preview helper snapshot required')
    directory.mkdir()
    result={}
    for source in sorted(set(helper_paths()+[Path(path).resolve() for path in additional])):
        destination=directory/source.name
        require(not destination.exists(),'Preview helper snapshot filename collision')
        shutil.copy2(source,destination)
        result[str(source)]={'sha256':sha(source),'snapshot':str(destination.resolve())}
        require(sha(destination)==result[str(source)]['sha256'],'Preview helper copy changed')
    (directory/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def verify_helpers(manifest):
    for source,pin in manifest.items():
        require(sha(Path(source))==pin['sha256'],'Preview helper changed during execution: '+source)
        require(sha(Path(pin['snapshot']))==pin['sha256'],'Preview helper snapshot changed')


def pose(ascii_dir, prefix, clip, time, stock_dir=None):
    """Retain legacy lookup/defaults while sampling count/endlist/static data."""
    ascii_dir=Path(ascii_dir)
    root_path=(ascii_dir/(prefix+'.mdl')).resolve()
    skeleton=nodes(root_path.read_text(encoding='cp1252'))
    current=prefix.lower();visited=set();inheritance=[]
    while current!='null':
        if current in visited:
            raise RuntimeError('Supermodel cycle')
        visited.add(current)
        path=ascii_dir/(current+'.mdl')
        if not path.exists() and stock_dir is not None:
            path=Path(stock_dir)/(current+'.mdl')
        path=path.resolve()
        text=path.read_text(encoding='cp1252')
        inheritance.append({'model':current,'file':str(path),'sha256':sha(path)})
        match=next((row for row in CLIP.finditer(text) if row[1].lower()==clip.lower()),None)
        if match:
            length_match=re.search(r'(?mi)^\s*length\s+(\S+)',match[2])
            if not length_match:
                raise RuntimeError('Animation length missing: '+clip)
            length=float(length_match[1])
            if not 0 <= time <= length:
                raise RuntimeError(f'Time {time} outside clip length {length}')
            try:
                matrices=sample(skeleton,match[2],time)
            except ValueError as error:
                raise RuntimeError(str(error)) from error
            return matrices,{'file':str(path),'sha256':sha(path),'clip':clip,
                'time':time,'length':length,'rootFile':str(root_path),'rootSha256':sha(root_path),
                'sourceInheritance':inheritance,'sampler':'rig_pose_audit.sample',
                'samplerHelperInputs':helper_inputs(),
                'controllerEncodings':['explicit-count','endlist','static'],
                'clientEvidence':False}
        parent=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',text)
        if not parent:
            raise RuntimeError('Supermodel declaration missing: '+current)
        current=parent[1].lower()
    raise RuntimeError('Clip unavailable: '+clip)
