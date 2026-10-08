"""Prepare hash-bound CPU pose measurements before an offline Blender review.

No renderer or GPU is initialized. Measurements establish preview inputs and
working/runtime transform consistency; they never accept visible anatomy or
replace mandatory client observations.
"""
import argparse
import json
from pathlib import Path
import numpy as np

from build_target_diagnostic import points
from pose_preview_bridge import pose, freeze_helpers, verify_helpers
from target_contract import PART_JOINTS, load, sha, require, verify_binding


def prepare(contract_path, working, runtime, baseline, output):
    contract=load(contract_path)
    require(not output.exists(),'Fresh CPU pose review directory required')
    output.mkdir(parents=True)
    helper_manifest=freeze_helpers(output,[Path(__file__),
        Path(__file__).with_name('build_target_diagnostic.py'),
        Path(__file__).with_name('audit_geometry.py'),
        Path(__file__).with_name('build_target_rig.py')])
    source_inputs={str(contract_path.resolve()):sha(contract_path)}
    for space,directory in [('working',working),('runtime',runtime)]:
        receipt=json.loads((directory/'diagnostic.json').read_text())
        verify_binding(receipt['target'],contract_path,contract,space)
        source_inputs[str((directory/'diagnostic.json').resolve())]=sha(directory/'diagnostic.json')
        for resource,pin in receipt['resources'].items():
            path=(directory/'ascii'/resource).resolve()
            require(sha(path)==pin,'Diagnostic resource changed: '+resource)
            source_inputs[str(path)]=pin
    prefix=contract['identity']['prefix'];source_prefix=contract['rig']['sourcePrefix']
    report={'schemaVersion':1,'kind':'offline-target-cpu-pose-review',
        'targetContractSha256':sha(contract_path),'rigRevision':contract['rig']['revision'],
        'measurements':[],'clientEvidence':False,'rendererStarted':False,'pilotAccepted':False,
        'coordinateSpaces':['stock-human','working','runtime'],'importedHelperSnapshots':helper_manifest,
        'note':'CPU measurements use actual stock geometry. Widened connectors require custom donor review; visible quality and client motion are unaccepted.'}
    datasets={}
    for key,directory,model in [('stock-human',baseline,source_prefix),
                                ('working',working,prefix),('runtime',runtime,prefix)]:
        datasets[key]={}
        for part in PART_JOINTS:
            path=(directory/'ascii'/(model+'_'+part+'001.mdl')).resolve()
            source_inputs[str(path)]=sha(path)
            datasets[key][part]=path.read_text(encoding='cp1252')
    factor=contract['rig']['runtimeScale']
    for clip in ('pause1','pause2','walk','run','conjure1','kneel','deadfnt'):
        _,initial=pose(working/'ascii',prefix,clip,0,baseline/'ascii')
        for fraction in (0.,.25,.5,.75,1.):
            time=initial['length']*fraction
            frames={};receipts={};bounds={};world_parts={}
            for key,directory,model in [('stock-human',baseline,source_prefix),
                                        ('working',working,prefix),('runtime',runtime,prefix)]:
                frames[key],receipts[key]=pose(directory/'ascii',model,clip,time,baseline/'ascii')
                require(receipts[key]['length']==initial['length'],'Comparison clip duration mismatch')
                for entry in receipts[key]['sourceInheritance']:
                    source_inputs[entry['file']]=entry['sha256']
                world_parts[key]={part:points(datasets[key][part],frames[key][joint])
                                  for part,joint in PART_JOINTS.items()}
                full=np.concatenate(list(world_parts[key].values()))
                bounds[key]={'minimum':full.min(axis=0).tolist(),'maximum':full.max(axis=0).tolist()}
            rotation_error=max(float(np.max(np.abs(frames['runtime'][joint][:3,:3]-
                frames['working'][joint][:3,:3]))) for joint in PART_JOINTS.values())
            translation_error=max(float(np.max(np.abs(frames['runtime'][joint][:3,3]-
                frames['working'][joint][:3,3]*factor))) for joint in PART_JOINTS.values())
            vertex_error=max(float(np.max(np.abs(world_parts['runtime'][part]-
                world_parts['working'][part]*factor))) for part in PART_JOINTS)
            require(max(rotation_error,translation_error,vertex_error)<1e-9,
                    'Preview bridge changed working/runtime transform consistency')
            report['measurements'].append({'clip':clip,'time':time,'fraction':fraction,
                'length':initial['length'],'worldBounds':bounds,'sourceReceipts':receipts,
                'maximumRuntimeRotationDifference':rotation_error,
                'maximumRuntimeTranslationScaleDifference':translation_error,
                'maximumRuntimeVertexScaleDifference':vertex_error,
                'jointWorldMatrices':{key:{joint:frame.tolist() for joint,frame in poses.items()
                                          if joint in PART_JOINTS.values()}
                                     for key,poses in frames.items()}})
    for path,pin in source_inputs.items():
        require(sha(Path(path))==pin,'CPU pose review input changed: '+path)
    verify_helpers(helper_manifest)
    report['sourceInputs']=source_inputs
    destination=output/'pose-review.json';destination.write_text(json.dumps(report,indent=2)+'\n')
    return destination,report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','working-assembly','runtime-assembly','baseline','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    destination,report=prepare(args.target_contract.resolve(),args.working_assembly.resolve(),
        args.runtime_assembly.resolve(),args.baseline.resolve(),args.output.resolve())
    print(json.dumps({'path':str(destination.resolve()),'sha256':sha(destination),
        'samples':len(report['measurements']),'rendererStarted':False,'clientAccepted':False,
        'maximumVertexScaleDifference':max(row['maximumRuntimeVertexScaleDifference'] for row in report['measurements'])}))
