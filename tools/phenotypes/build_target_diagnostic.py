"""Compose actual stock parts on a declared target; never accept them as donors."""
import argparse
import json
from pathlib import Path
import re
import shutil
import numpy as np

from audit_geometry import arrays
from build_target_rig import replace_position, scale_vector_arrays
from retarget import NODE, nodes, transforms
from target_contract import PART_JOINTS, binding, frame, load, require, sha


def convert_part(text, source_name, target_name, scale):
    require('newanim' not in text.lower(), 'Animated stock part needs controller handling')
    def convert(match):
        row=nodes(match[0])[match[2].lower()]
        body=scale_vector_arrays(replace_position(match[3],row['position']*scale),scale)
        name=target_name if match[2].lower()==source_name else match[2]
        body=re.sub(r'(?mi)^(\s*parent\s+)'+re.escape(source_name)+r'\s*$',
                    lambda m:m[1]+target_name,body)
        return 'node '+match[1]+' '+name+'\n'+body+'endnode'
    result=NODE.sub(convert,text)
    for directive in ('newmodel','beginmodelgeom','endmodelgeom','donemodel','setsupermodel'):
        result=re.sub(r'(?mi)^('+directive+r'\s+)'+re.escape(source_name)+r'\b',
                      lambda m:m[1]+target_name,result)
    # Stock PLT texture names can equal their model names. They are distinct
    # resources and remain unchanged by the model namespace conversion.
    before=re.findall(r'(?mi)^\s*(bitmap|materialname)\s+(\S+)',text)
    after=re.findall(r'(?mi)^\s*(bitmap|materialname)\s+(\S+)',result)
    require(before==after, 'Stock shading resource was renamed')
    return result


def points(text, attachment):
    local=transforms(nodes(text)); output=[]
    for block in NODE.finditer(text.split('endmodelgeom')[0]):
        values=arrays(block[3],'verts')
        if values:
            matrix=attachment@local[block[2].lower()]
            output.extend((np.c_[values,np.ones(len(values))]@matrix.T)[:,:3])
    require(bool(output),'Stock part has no geometry')
    return np.asarray(output)


def build(contract_path, rig_path, baseline, output, space):
    target=load(contract_path); require(not output.exists(),'Fresh diagnostic directory required')
    rig=json.loads((rig_path/'rig-export.json').read_text())
    require(rig['targetContractSha256']==sha(contract_path),'Rig export belongs to another target')
    factor=1 if space=='working' else target['rig']['runtimeScale']
    directory=output/'ascii'; directory.mkdir(parents=True)
    inputs={}; resources={}; entries=[]
    for row in rig['models']:
        if row['space']!=space:continue
        source=rig_path/space/'ascii'/(row['model']+'.mdl')
        require(sha(source)==row['sha256'],'Rig output changed')
        destination=directory/source.name;shutil.copy2(source,destination)
        inputs[str(source.resolve())]=sha(source);resources[destination.name]=sha(destination)
    for part,joint in PART_JOINTS.items():
        source_name=target['rig']['sourcePrefix']+'_'+part+'001'
        source=baseline/'ascii'/(source_name+'.mdl')
        original=source.read_text(encoding='cp1252')
        result=convert_part(original,source_name,target['models'][part],factor)
        destination=directory/(target['models'][part]+'.mdl');destination.write_text(result,encoding='ascii')
        actual=points(result,frame(target,joint,space))
        # Source parts are detached. Scaling their mesh-local positions and
        # vertices once must match scaling the complete working assembly.
        expected=points(original,frame(target,joint,'working'))*factor
        error=float(np.max(abs(actual-expected)))
        require(error<1e-9,'Diagnostic geometry was scaled/placed twice: '+part)
        entries.append({'part':part,'model':target['models'][part],'sourceSha256':sha(source),
                        'maximumWorldTransformError':error,'minimum':actual.min(0).tolist(),
                        'maximum':actual.max(0).tolist(),'provisionalHeadNeck':part in ('head','neck')})
        inputs[str(source.resolve())]=sha(source);resources[destination.name]=sha(destination)
    receipt={'schemaVersion':2,'kind':'target-stock-diagnostic','target':binding(contract_path,target,space),
             'height':target['workingHeightMeters']*factor,'modelPrefix':target['identity']['prefix'],
             'parts':entries,'sourceInputs':inputs,'resources':resources,'clientAccepted':False,
             'donorAccepted':False,'limitation':'Stock geometry demonstrates placement; widened joints leave connector gaps until purpose-built donors pass the pilot.'}
    (output/'diagnostic.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','rig','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--coordinate-space',choices=('working','runtime'),required=True)
    a=p.parse_args();r=build(a.target_contract.resolve(),a.rig.resolve(),a.baseline.resolve(),a.output.resolve(),a.coordinate_space)
    print(json.dumps({'parts':len(r['parts']),'resources':len(r['resources']),
                      'maximumWorldTransformError':max(row['maximumWorldTransformError'] for row in r['parts'])}))
