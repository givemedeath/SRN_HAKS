"""Freeze an installed Human normal rig without exporting or modifying it."""
import argparse
import copy
import json
from pathlib import Path
import re
import numpy as np
import target_contract as contract
from audit_geometry import arrays
from retarget import NODE, nodes
from rig_controller_audit import world_frames
from rig_pose_audit import inherited_clips


def freeze(baseline, output, gender='female', target_id='human-female-fit-purposebuilt-v1', body_type='fit'):
    baseline, output = Path(baseline).resolve(), Path(output).resolve()
    contract.require(not output.exists(), 'Fresh immutable stock target required')
    contract.require(gender in ('male', 'female'), 'Human male/female reference required')
    contract.require(body_type in ('fit', 'muscular'), 'Declared Human body type required')
    prefix = 'pfh0' if gender == 'female' else 'pmh0'
    extraction = baseline/'baseline.json'
    inventory = {row['name']:row for row in json.loads(extraction.read_text())['resources']}
    frozen = {str(extraction):contract.sha(extraction)}
    def text(name):
        row=inventory[name+'.mdl']; raw=baseline/'raw'/(name+'.mdl'); source=baseline/'ascii'/(name+'.mdl')
        contract.require(contract.sha(raw)==row['sha256'] and contract.sha(source)==row['asciiSha256'], 'Stock extraction changed: '+name)
        frozen[str(raw)]=row['sha256']; frozen[str(source)]=row['asciiSha256']
        value=source.read_text(encoding='cp1252')
        contract.require(all(float(v)==1 for v in re.findall(r'(?mi)^\s*scale\s+(\S+)',value)), 'Nonidentity stock node scale needs a measured adapter')
        return value
    root_text=text(prefix); frames=world_frames(nodes(root_text))
    contract.require(set(contract.PART_JOINTS.values())<=set(frames), 'Installed stock attachment missing')
    chain=[]; texts={}; current=prefix
    while current!='null':
        contract.require(current not in chain, 'Installed supermodel cycle')
        chain.append(current); texts[current]=text(current)
        parent=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',texts[current])
        contract.require(parent is not None, 'Missing installed supermodel declaration')
        current=parent[1].lower()
    points={}; stats={}
    for part,joint in contract.PART_JOINTS.items():
        value=text(prefix+'_'+part+'001'); local=world_frames(nodes(value)); chunks=[]
        for block in NODE.finditer(value.split('endmodelgeom',1)[0]):
            vertices=np.asarray(arrays(block[3],'verts'),float)
            if not len(vertices):continue
            contract.require(vertices.ndim==2 and vertices.shape[1]==3, 'Unsupported stock mesh positions')
            world=frames[joint] @ local[block[2].lower()]
            chunks.append((world @ np.c_[vertices,np.ones(len(vertices))].T).T[:,:3])
        contract.require(bool(chunks), 'Stock part has no rendered geometry: '+part)
        p=np.concatenate(chunks);points[part]=p
        stats[part]={'vertices':len(p),'minimum':p.min(axis=0).tolist(),'maximum':p.max(axis=0).tolist(),
                     'extent':np.ptp(p,axis=0).tolist(),'joint':joint,'attachment':frames[joint].tolist()}
    assembly=np.concatenate(list(points.values())); height=float(np.ptp(assembly[:,2]))
    overlaps=[]
    from inspect_stock_joints import PAIRS
    for parent,child in PAIRS:
        origin=frames[contract.PART_JOINTS[child]][:3,3]
        axis=origin-frames[contract.PART_JOINTS[parent]][:3,3]
        if np.linalg.norm(axis)<1e-9:axis=np.array([0.,0.,-1.])
        axis=axis/np.linalg.norm(axis);a=(points[parent]-origin)@axis;b=(points[child]-origin)@axis
        overlaps.append({'parent':parent,'child':child,'axis':axis.tolist(),'axialOverlap':float(a.max()-b.min())})
    for name,row in inventory.items():
        if name.endswith('.2da') or name.startswith('pal_') or name.endswith('.plt') and name.startswith(prefix):
            source=baseline/'raw'/name;contract.require(contract.sha(source)==row['sha256'],'Stock dependency changed: '+name)
            frozen[str(source)]=row['sha256']
    frame_rows={name:matrix.tolist() for name,matrix in frames.items()}
    clips=inherited_clips(chain,texts)
    receipt={'schemaVersion':1,'kind':'stock-target-reference','pass':True,'prefix':prefix,
             'heightMeters':height,'rootAscii':{'path':str(baseline/'ascii'/(prefix+'.mdl')),'sha256':contract.sha(baseline/'ascii'/(prefix+'.mdl'))},
             'frames':frame_rows,'parts':stats,'connections':overlaps,'chain':chain,
             'clips':{name:{'owner':item['owner'],'length':item['length']} for name,item in clips.items()},
             'shoulderPivotSpanMeters':float(np.linalg.norm(frames['lbicep_g'][:3,3]-frames['rbicep_g'][:3,3])),
             'hipPivotSpanMeters':float(np.linalg.norm(frames['lthigh_g'][:3,3]-frames['rthigh_g'][:3,3])),
             'frozenInputs':frozen,'rigModified':False,'privateRigExported':False,'clientAccepted':False,
             'limitation':'Installed bind geometry and inherited clip inventory only; overlap intervals do not prove motion contact.'}
    output.mkdir(parents=True);proof=output/'stock-reference.json';proof.write_text(json.dumps(receipt,indent=2)+'\n')
    target={'schemaVersion':2,'kind':'phenotype-target','id':target_id,
            'identity':{'race':'human','gender':gender,'phenotype':0,'bodyType':body_type,'prefix':prefix,'raceId':6,'appearanceRow':6},
            'heightMeters':height,'workingHeightMeters':height,
            'rig':{'mode':'stock-exact','revision':prefix+'-stock-reference-v1','sourcePrefix':prefix,'runtimeScale':1,
                   'positionPolicy':'stock-exact','preserveRotations':True,'preserveTimingEvents':True,
                   'frames':{'working':frame_rows,'runtime':copy.deepcopy(frame_rows)},
                   'privateAliases':{},'changedLocalPositions':{},'pilotAccepted':False,
                   'stockReferenceReceipt':{'path':str(proof),'sha256':contract.sha(proof)}},
            'models':{part:prefix+'_'+part+'001' for part in contract.PART_JOINTS},
            'material':{'fixedGarmentParts':['chest','pelvis'] if gender=='female' else ['pelvis'],
                        'normalStrength':1,'roughnessOverride':0},
            'equipment':{'mode':'stock-identity','sourcePrefix':prefix,'profileRequired':False},
            'frozenInputs':frozen}
    contract.validate(target);path=output/'target-contract.json';path.write_text(json.dumps(target,indent=2)+'\n');contract.load(path)
    return path,receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--gender',choices=('male','female'),default='female');parser.add_argument('--target-id',default='human-female-fit-purposebuilt-v1');parser.add_argument('--body-type',choices=('fit','muscular'),default='fit')
    args=parser.parse_args();path,proof=freeze(args.stock_baseline,args.output,args.gender,args.target_id,args.body_type)
    print(json.dumps({'targetContract':str(path),'sha256':contract.sha(path),'heightMeters':proof['heightMeters'],
                      'shoulderPivotSpanMeters':proof['shoulderPivotSpanMeters'],'hipPivotSpanMeters':proof['hipPivotSpanMeters'],'clips':len(proof['clips'])}))
