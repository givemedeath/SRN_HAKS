"""Decode preserved body resources and sample head/neck motion for clay review."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
from stock_limb_contract import ATTACHMENTS
from prepare_effective_body_preview import mesh_corners
from pose_preview_bridge import pose
from retarget import nodes
from rig_controller_audit import world_frames, CLIP
from head_workflow import pin, read, require, validate_target, verify_pins, write_fresh
from head_export import triangles
from native_reader import decode


def prepare(manifest, repository, stock, fits, output, target_path=None):
    output=Path(output); require(not output.exists(),'Fresh assembly output required'); output.mkdir(parents=True)
    body=read(manifest); repository=Path(repository).resolve(); stock=Path(stock).resolve()
    target = validate_target(read(target_path)) if target_path else None
    if target:
        require(target['bodyManifest'] == pin(manifest), 'Assembly body differs from approved head contract')
        root = Path(target['rig']['path']); prefix = target['prefix']
        neckpath = Path(target['neckGeometry']['path'])
        animation_paths = [Path(p['path']) for p in target['animations']]
    else:
        root=stock/'ascii/pmh0.mdl'; prefix='pmh0'
        neckpath=stock/'ascii/pmh0_neck001.mdl'
        animation_paths=sorted((stock/'ascii').glob('a_ba*.mdl'))
    bind=world_frames(nodes(root.read_text(encoding='cp1252')))
    if target:
        require(np.allclose(bind['head_g'], target['headBindMatrix'], atol=1e-8), 'Assembly head frame differs')
    parts=[]
    for resource in body['resources']:
        if not resource['path'].endswith('.mdl'): continue
        source=repository/resource['path']; verify_pins([{'path':str(source),'sha256':resource['sha256']}])
        joint=({**ATTACHMENTS,'chest':'torso_g','pelvis':'pelvis_g'})[source.stem[5:-3]]
        require(joint in bind,'Unknown body attachment')
        for index,row in enumerate(decode(source.read_bytes(),source.stem)):
            geometry_path=output/(source.stem+f'-{index}.npz')
            np.savez(geometry_path,position=row['position'][row['faces']],normal=row['normal'][row['faces']],uv=row['uv'][row['faces']])
            parts.append({'name':row['name'],'geometry':pin(geometry_path),'source':pin(source),'joint':joint})
    for index,row in enumerate(mesh_corners(neckpath.read_text(encoding='cp1252'))):
        geometry_path=output/f'stock-neck-{index}.npz'; np.savez(geometry_path,position=row['position'],normal=row['normal'],uv=row['uv'])
        parts.append({'name':'stock-neck','geometry':pin(geometry_path),'source':pin(neckpath),'joint':'neck_g'})
    heads=[]
    for path in fits:
        fit=read(path); verify_pins([fit['source'],fit['target']])
        if target: require(fit['target'] == pin(target_path), 'Head fit uses another body contract')
        p,_,_=triangles(fit['source']['path'],fit['localMatrix'])
        heads.append({'fit':pin(path),'bounds':[p.reshape(-1,3).min(0).tolist(),p.reshape(-1,3).max(0).tolist()]})
    clips={}
    for source in animation_paths:
        for row in CLIP.finditer(source.read_text(encoding='cp1252')):
            clips.setdefault(row[1],float(re.search(r'(?mi)^\s*length\s+(\S+)',row[2])[1]))
    choices={'idle':'pause1','talk':'tlknorm','locomotion':'walk','run':'run','casting':'castout',
             'combat':'1hslashr','crouch':'getlow','kneel':'kneel','death':'deadfnt'}
    samples=[{'label':'standing','frames':{key:value.tolist() for key,value in bind.items()}}]
    for kind,clip in choices.items():
        require(clip in clips,'Missing representative clip: '+clip)
        # The nearest supermodel owns the clip. A stock Dwarf override can have
        # a different duration from the generic clip encountered above.
        initial_frames,initial_receipt=pose(root.parent,prefix,clip,0.,stock/'ascii')
        duration=initial_receipt.get('length',clips[clip])
        for fraction in np.linspace(0,1,9):
            frames,receipt=pose(root.parent,prefix,clip,float(fraction*duration),stock/'ascii')
            samples.append({'label':kind,'clip':clip,'time':receipt['time'],'pose':receipt,
                            'frames':{key:value.tolist() for key,value in frames.items()}})
    neck=np.concatenate([m['position'].reshape(-1,3) for m in mesh_corners(neckpath.read_text(encoding='cp1252'))])
    # Compare head/neck relative transforms across all samples; choose the largest
    # displacement of the preserved neck's vertices in head attachment space.
    neck_bind=neck@bind['neck_g'][:3,:3].T+bind['neck_g'][:3,3]
    neck_local=neck_bind@bind['head_g'][:3,:3]-bind['head_g'][:3,3]@bind['head_g'][:3,:3]
    for sample in samples:
        frame={key:np.asarray(value) for key,value in sample['frames'].items()}
        world=neck@frame['neck_g'][:3,:3].T+frame['neck_g'][:3,3]
        local=(world-frame['head_g'][:3,3])@frame['head_g'][:3,:3]
        sample['neckDisplacement']=float(np.linalg.norm(local-neck_local,axis=1).max())
    worst=max(range(len(samples)),key=lambda i:samples[i]['neckDisplacement'])
    if target: validate_target(target)
    write_fresh(output/'assembly.json',{'kind':'srn-head-assembly-measurement','bodyManifest':pin(manifest),
        'parts':parts,'heads':heads,'neckHeadLocalBounds':[neck_local.min(0).tolist(),neck_local.max(0).tolist()],
        'samples':samples,'worstSample':worst,'standingAccepted':False,'motionAccepted':False,
        'clientValidated':False,'productionAccepted':False,
        'headTarget':pin(target_path) if target else None,
        'rig':pin(root),'neckGeometry':pin(neckpath),
        'coordinateSpace':'contract-working-space','runtimeScale':target.get('runtimeScale',1) if target else 1})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','repository','stock','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fit',type=Path,action='append',required=True)
    p.add_argument('--target',type=Path)
    a=p.parse_args(); prepare(a.manifest,a.repository,a.stock,a.fit,a.output,a.target)
