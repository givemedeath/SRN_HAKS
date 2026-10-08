"""Compose actual stock parts on a declared target; never accept them as donors."""
import argparse
import json
from pathlib import Path
import re
import shutil
import numpy as np
import target_contract as contract

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


def build_retargeted(contract_path, rig_path, baseline, output, space):
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


def build_stock_exact(contract_path, baseline, output, space):
    """Copy installed stock bytes as identified diagnostic fallbacks, with no export."""
    contract_path,baseline,output=[Path(path).resolve() for path in (contract_path,baseline,output)]
    target=load(contract_path);require(contract.rig_mode(target)=='stock-exact','Stock-exact target required')
    require(space in ('working','runtime') and not output.exists(),'Explicit space and fresh diagnostic directory required')
    proof_path=Path(target['rig']['stockReferenceReceipt']['path']).resolve();proof=json.loads(proof_path.read_text())
    baseline_path=baseline/'baseline.json';extraction=json.loads(baseline_path.read_text());inventory={row['name']:row for row in extraction['resources']}
    inputs={str(contract_path):sha(contract_path),str(proof_path):sha(proof_path),str(baseline_path):sha(baseline_path)}
    prefix=target['rig']['sourcePrefix'];models=set(proof['chain'])|{prefix}|{prefix+'_'+part+'001' for part in PART_JOINTS}
    copies=[];entries=[];materials=set()
    for model in sorted(models):
        name=model+'.mdl';row=inventory[name];source=baseline/'ascii'/name;raw=baseline/'raw'/name
        require(sha(source)==row['asciiSha256'] and sha(raw)==row['sha256'],'Frozen stock diagnostic source changed: '+name)
        require(proof['frozenInputs'].get(str(source))==row['asciiSha256'] and proof['frozenInputs'].get(str(raw))==row['sha256'],'Stock fallback is absent from target proof: '+name)
        inputs[str(source)]=row['asciiSha256'];inputs[str(raw)]=row['sha256']
        copies.extend([(source,'ascii/'+name,row['asciiSha256']),(raw,'raw/'+name,row['sha256'])])
        text=source.read_text(encoding='cp1252')
        for bitmap in re.findall(r'(?mi)^\s*(?:bitmap|materialname)\s+(\S+)',text):
            for extension in ('.plt','.tga','.dds','.mtr','.txi'):
                resource=bitmap.lower()+extension
                if resource in inventory:materials.add(resource)
    materials.update(name for name in inventory if name.startswith('pal_'))
    for name in sorted(materials):
        row=inventory[name];source=baseline/'raw'/name
        require(sha(source)==row['sha256'],'Stock material dependency changed: '+name)
        inputs[str(source)]=row['sha256'];copies.append((source,'raw/'+name,row['sha256']))
    for part,joint in PART_JOINTS.items():
        model=prefix+'_'+part+'001';require(target['models'][part]==model,'Stock-exact fallback namespace differs')
        source=baseline/'ascii'/(model+'.mdl');actual=points(source.read_text(encoding='cp1252'),frame(target,joint,space))
        entries.append({'part':part,'model':model,'sourceAscii':str(source),'sourceSha256':sha(source),
                        'sourceNative':str(baseline/'raw'/(model+'.mdl')),'sourceNativeSha256':sha(baseline/'raw'/(model+'.mdl')),
                        'stockFallback':True,'byteExactStockSource':True,'maximumWorldTransformError':0,
                        'minimum':actual.min(0).tolist(),'maximum':actual.max(0).tolist(),'provisionalHeadNeck':False})
    output.mkdir(parents=True);(output/'ascii').mkdir();(output/'raw').mkdir();(output/'helper-snapshots').mkdir()
    for source,relative,pin in copies:
        destination=output/relative;shutil.copyfile(source,destination);require(sha(destination)==pin,'Stock fallback copy changed')
    helpers={}
    for name in ('build_target_diagnostic.py','target_contract.py','retarget.py','audit_geometry.py','build_target_rig.py'):
        source=Path(__file__).with_name(name);destination=output/'helper-snapshots'/name;shutil.copyfile(source,destination);helpers[str(source)]={'sha256':sha(source),'snapshot':str(destination)}
    require(all(sha(path)==pin for path,pin in inputs.items()),'Stock diagnostic input changed during copying')
    resources={path.name:sha(path) for path in (output/'ascii').iterdir()}
    raw_resources={path.name:sha(path) for path in (output/'raw').iterdir()}
    receipt={'schemaVersion':2,'kind':'target-stock-diagnostic','target':binding(contract_path,target,space),
             'height':target['heightMeters'],'modelPrefix':prefix,'parts':entries,'sourceInputs':inputs,'resources':resources,
             'rawResourceHashes':raw_resources,'stockMaterialResourceHashes':{name:raw_resources[name] for name in materials},
             'helperSnapshots':helpers,'rigMode':'stock-exact','rigExported':False,'rigOrAnimationBytesChanged':False,
             'statureOperation':'identity stock reference; diagnostic fallbacks are copied rather than converted',
             'allSixteenFallbackPartsIdentified':True,'clientAccepted':False,'donorAccepted':False,
             'limitation':'Byte-exact installed stock fallback geometry demonstrates measured frames; no purpose-built donor or client acceptance is inherited.'}
    (output/'diagnostic.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt


def build(contract_path, rig_path, baseline, output, space):
    target=load(contract_path)
    if contract.rig_mode(target)=='stock-exact':
        require(rig_path is None,'Stock-exact diagnostic must use installed sources without a private rig export')
        return build_stock_exact(contract_path,baseline,output,space)
    require(rig_path is not None,'Retargeted diagnostic requires its private rig export')
    return build_retargeted(contract_path,rig_path,baseline,output,space)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--rig',type=Path,help='Required only for legacy retargeted private-rig diagnostics')
    p.add_argument('--coordinate-space',choices=('working','runtime'),required=True)
    a=p.parse_args();r=build(a.target_contract.resolve(),a.rig.resolve() if a.rig else None,a.baseline.resolve(),a.output.resolve(),a.coordinate_space)
    print(json.dumps({'parts':len(r['parts']),'resources':len(r['resources']),
                      'maximumWorldTransformError':max(row['maximumWorldTransformError'] for row in r['parts'])}))
