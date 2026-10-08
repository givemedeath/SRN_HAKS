"""Independent encoded-array audit of a bounded terminal field descendant."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from place_purposebuilt_pelvis import accessor, embedded_maps, read_glb
from target_contract import require, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();receipt_path=args.receipt.resolve();receipt=json.loads(receipt_path.read_text())
    source=Path(receipt['source']);candidate=Path(receipt['candidate']);archive=Path(receipt['nativeCornerArchive']['path'])
    pins={str(receipt_path):sha(receipt_path),str(source):receipt['sourceSha256'],
          str(candidate):receipt['candidateSha256'],str(archive):receipt['nativeCornerArchive']['sha256']}
    for path,pin in pins.items():require(sha(path)==pin,'Audit input changed: '+path)
    old,ob=read_glb(source);new,nb=read_glb(candidate)
    op=old['meshes'][0]['primitives'][0];np_=new['meshes'][0]['primitives'][0]
    data=np.load(archive,allow_pickle=False);edited=data['fieldEditedSourceVertexMask']
    require(op['indices']==np_['indices'],'Index accessor changed')
    require(old['materials']==new['materials'] and embedded_maps(old,ob)==embedded_maps(new,nb),'Maps/materials changed')
    arrays={}
    for semantic,index in op['attributes'].items():
        original=accessor(old,ob,index,allow_normalized=True)
        actual=accessor(new,nb,np_['attributes'][semantic],allow_normalized=True)
        if semantic in ('POSITION','NORMAL','TANGENT'):
            require(actual[~edited].tobytes()==original[~edited].tobytes(),'Outside-support bytes changed')
        else:require(original.tobytes()==actual.tobytes(),'UV/color bytes changed')
        arrays[semantic]=(original.astype(float),actual.astype(float))
    p0,p1=arrays['POSITION'];n0,n1=arrays['NORMAL'];t0,t1=arrays['TANGENT']
    normal_error=float(np.max(abs(np.linalg.norm(n1,axis=1)-np.linalg.norm(n0,axis=1))))
    tangent_error=float(np.max(abs(np.linalg.norm(t1[:,:3],axis=1)-np.linalg.norm(t0[:,:3],axis=1))))
    require(normal_error<1e-6 and tangent_error<1e-6 and np.array_equal(t0[:,3],t1[:,3]),'Serialized authored direction budget failed')
    result={'schemaVersion':2,'kind':'target-terminal-serialized-array-audit','readOnly':True,
        'frozenInputs':pins,'sourceBinPrefixExact':nb[:len(ob)]==ob,
        'outsideSupportPositionNormalTangentEncodedBytesExact':True,'uvColorMapsMaterialsExact':True,
        'indexAccessorUnchanged':True,'serializedMaximumDisplacementMetres':float(np.linalg.norm(p1-p0,axis=1).max()),
        'serializedNormalMagnitudeDifferenceMaximum':normal_error,'serializedTangentMagnitudeDifferenceMaximum':tangent_error,
        'tangentHandednessExact':True,'maximumSerializedNormalTangentDot':float(np.max(abs(np.sum(n1*t1[:,:3],axis=1)))),
        'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,
        'limitation':'Encoded-array preservation and measured FLOAT32 direction error only; visual improvement remains unproved.'}
    output=args.output.resolve();require(not output.exists(),'Fresh independent audit output required')
    output.mkdir(parents=True);snapshots={}
    for name in ('audit_terminal_field_serialization.py','place_purposebuilt_pelvis.py','target_contract.py'):
        code=Path(__file__).with_name(name).resolve();destination=output/name;shutil.copy2(code,destination)
        snapshots[str(code)]={'snapshot':str(destination),'sha256':sha(destination)}
    result['helperSnapshots']=snapshots
    for path,pin in pins.items():require(sha(path)==pin,'Audit input changed during execution: '+path)
    path=output/'serialization-audit.json';path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt':str(path),'sha256':sha(path),'measurements':result}))


if __name__=='__main__':main()
