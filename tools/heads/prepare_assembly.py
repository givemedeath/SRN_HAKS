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
from head_workflow import pin, read, require, verify_pins, write_fresh
from head_export import triangles
from native_reader import decode


def prepare(manifest, repository, stock, fits, output):
    output=Path(output); require(not output.exists(),'Fresh assembly output required'); output.mkdir(parents=True)
    body=read(manifest); repository=Path(repository).resolve(); stock=Path(stock).resolve()
    root=stock/'ascii/pmh0.mdl'; bind=world_frames(nodes(root.read_text(encoding='cp1252')))
    parts=[]
    for resource in body['resources']:
        if not resource['path'].endswith('.mdl'): continue
        source=repository/resource['path']; verify_pins([{'path':str(source),'sha256':resource['sha256']}])
        joint=({**ATTACHMENTS,'chest':'torso_g','pelvis':'pelvis_g'})[source.stem[5:-3]]
        require(joint in bind,'Unknown body attachment')
        for index,row in enumerate(decode(source.read_bytes(),source.stem)):
            target=output/(source.stem+f'-{index}.npz')
            np.savez(target,position=row['position'][row['faces']],normal=row['normal'][row['faces']],uv=row['uv'][row['faces']])
            parts.append({'name':row['name'],'geometry':pin(target),'source':pin(source),'joint':joint})
    neckpath=stock/'ascii/pmh0_neck001.mdl'
    for index,row in enumerate(mesh_corners(neckpath.read_text(encoding='cp1252'))):
        target=output/f'stock-neck-{index}.npz'; np.savez(target,position=row['position'],normal=row['normal'],uv=row['uv'])
        parts.append({'name':'stock-neck','geometry':pin(target),'source':pin(neckpath),'joint':'neck_g'})
    heads=[]
    for path in fits:
        fit=read(path); verify_pins([fit['source'],fit['target']])
        p,_,_=triangles(fit['source']['path'],fit['localMatrix'])
        heads.append({'fit':pin(path),'bounds':[p.reshape(-1,3).min(0).tolist(),p.reshape(-1,3).max(0).tolist()]})
    clips={}
    for source in sorted((stock/'ascii').glob('a_ba*.mdl')):
        for row in CLIP.finditer(source.read_text(encoding='cp1252')):
            clips.setdefault(row[1],float(re.search(r'(?mi)^\s*length\s+(\S+)',row[2])[1]))
    choices={'idle':'pause1','talk':'tlknorm','locomotion':'walk','run':'run','casting':'castout',
             'combat':'1hslashr','crouch':'getlow','kneel':'kneel','death':'deadfnt'}
    samples=[{'label':'standing','frames':{key:value.tolist() for key,value in bind.items()}}]
    for kind,clip in choices.items():
        require(clip in clips,'Missing representative clip: '+clip)
        for fraction in np.linspace(0,1,9):
            frames,receipt=pose(stock/'ascii','pmh0',clip,float(fraction*clips[clip]),stock/'ascii')
            samples.append({'label':kind,'clip':clip,'time':receipt['time'],'pose':receipt,
                            'frames':{key:value.tolist() for key,value in frames.items()}})
    neck=np.concatenate([m['position'].reshape(-1,3) for m in mesh_corners((stock/'ascii/pmh0_neck001.mdl').read_text(encoding='cp1252'))])
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
    write_fresh(output/'assembly.json',{'kind':'srn-head-assembly-measurement','bodyManifest':pin(manifest),
        'parts':parts,'heads':heads,'neckHeadLocalBounds':[neck_local.min(0).tolist(),neck_local.max(0).tolist()],
        'samples':samples,'worstSample':worst,'standingAccepted':False,'motionAccepted':False,
        'clientValidated':False,'productionAccepted':False})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','repository','stock','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--fit',type=Path,action='append',required=True)
    a=p.parse_args(); prepare(a.manifest,a.repository,a.stock,a.fit,a.output)
