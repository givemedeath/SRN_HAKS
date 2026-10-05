"""Measure rigid upperarm axial ownership separately from radial silhouette bulk."""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from place_purposebuilt_pelvis import raw_corners, read_glb


def axial_measure(corners,shoulder,elbow):
    shoulder=np.asarray(shoulder,float);elbow=np.asarray(elbow,float)
    direction=elbow-shoulder;length=float(np.linalg.norm(direction))
    contract.require(length>0,'Distinct actual shoulder/elbow frames required')
    direction/=length
    points=np.asarray(corners,float);delta=points-shoulder
    axial=delta@direction;radial=np.linalg.norm(delta-axial[:,:,None]*direction,axis=2)
    beyond=axial-length;near=np.abs(beyond)<=.008;distal=(beyond>=-.050)&(beyond<=.008)
    crossing=np.any(beyond>0,axis=1)&np.any(beyond<=0,axis=1)
    return {'shoulderPosition':shoulder.tolist(),'elbowPosition':elbow.tolist(),'axisUnit':direction.tolist(),
        'boneLengthMetres':length,'axialMinimumMetres':float(axial.min()),'axialMaximumMetres':float(axial.max()),
        'proximalEnvelopeBeyondShoulderMetres':max(0.,-float(axial.min())),
        'distalEnvelopeBeyondElbowMetres':max(0.,float(beyond.max())),
        'trianglesEntirelyPastElbowPlane':int(np.count_nonzero(np.all(beyond>0,axis=1))),
        'trianglesCrossingElbowPlane':int(crossing.sum()),
        'triangleCornerCountPastElbowPlane':int(np.count_nonzero(beyond>0)),
        'nearElbowEightMillimetreBandRadialMaximumMetres':float(radial[near].max()) if near.any() else None,
        'distalFiftyMillimetreBandRadialMaximumMetres':float(radial[distal].max()) if distal.any() else None,
        'maximumRadialDistanceMetres':float(radial.max())},axial,radial


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--arm-receipt',type=Path,action='append',required=True)
    parser.add_argument('--pose-receipt',type=Path,action='append',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();target_path=args.target_contract.resolve();target=contract.load(target_path)
    pins={str(target_path):contract.sha(target_path)};poses=[]
    for path in args.pose_receipt:
        path=path.resolve();document=json.loads(path.read_text());specimen=next(row for row in document['specimens'] if row.get('target'))
        contract.verify_binding(specimen['target'],target_path,target,'working')
        for row in specimen['sourceInheritance']:
            contract.require(contract.sha(row['file'])==row['sha256'],'Archived pose animation source changed')
            pins[row['file']]=row['sha256']
        pins[str(path)]=contract.sha(path)
        poses.append((path.parent.name,np.asarray(specimen['jointWorldMatrices']['lbicep_g']),
                      np.asarray(specimen['jointWorldMatrices']['lforearm_g']),
                      {'clip':specimen['clip'],'time':specimen['time'],'poseReceipt':str(path)}))
    bind=(np.asarray(target['rig']['frames']['working']['lbicep_g']),
          np.asarray(target['rig']['frames']['working']['lforearm_g']))
    states=[('bind',*bind,{'clip':None,'time':None})]+poses
    results=[];archives={}
    for path in args.arm_receipt:
        path=path.resolve();receipt=json.loads(path.read_text());contract.verify_binding(receipt,target_path,target,'working')
        contract.require(receipt['kind']=='target-part-geometry' and receipt['schemaVersion']==2 and
                         receipt['part']=='bicepl' and receipt['joint']=='lbicep_g' and receipt['statureApplications']==0,
                         'Exact diagnostic left upperarm working geometry receipt required')
        source=Path(receipt['candidate']);contract.require(contract.sha(source)==receipt['candidateSha256'],'Arm candidate changed')
        for name,pin in receipt['frozenInputs'].items():contract.require(contract.sha(name)==pin,'Arm frozen input changed: '+name);pins[name]=pin
        pins[str(path)]=contract.sha(path);pins[str(source)]=contract.sha(source)
        local=raw_corners(*read_glb(source))[0];label=path.parent.parent.name
        for state,shoulder_frame,elbow_frame,metadata in states:
            shape=local.shape
            placed=(np.c_[local.reshape(-1,3),np.ones(local.size//3)]@shoulder_frame.T)[:,:3].reshape(shape)
            measure,axial,radial=axial_measure(placed,shoulder_frame[:3,3],elbow_frame[:3,3])
            results.append({'fit':label,'receipt':str(path),'candidateSha256':receipt['candidateSha256'],
                            'state':state,**metadata,**measure})
            archives[label+'_'+state+'_axial']=axial;archives[label+'_'+state+'_radial']=radial
    output=args.output.resolve();contract.require(not output.exists(),'Fresh immutable ownership evidence required')
    output.mkdir(parents=True);helpers={}
    for name in ('measure_target_upperarm_ownership.py','place_purposebuilt_pelvis.py','target_contract.py'):
        source=Path(__file__).with_name(name).resolve();pins[str(source)]=contract.sha(source)
        destination=output/name;shutil.copy2(source,destination);helpers[str(source)]={'snapshot':str(destination),'sha256':contract.sha(destination)}
    archive=output/'upperarm-longitudinal-ownership.npz';np.savez_compressed(archive,**archives)
    report={'schemaVersion':2,'kind':'target-upperarm-longitudinal-ownership','readOnly':True,
        'target':contract.binding(target_path,target,'working'),'measurements':results,
        'archive':{'path':str(archive),'sha256':contract.sha(archive)},'frozenInputs':pins,'helperSnapshots':helpers,
        'fittingChanged':False,'geometryChanged':False,'rigPilotAccepted':False,'clientAccepted':False,
        'interpretation':['Axial distance is measured against actual shoulder-to-elbow frames, independent of camera projection.',
            'A corner past the elbow plane measures placement overlap; it does not alone establish wrong muscle anatomy.',
            'Radial triceps/biceps bulk against the current stock forearm fallback is not a reason to remove muscle design or shrink further.',
            'Original source lower collar/anatomical elbow landmarks remain unaccepted.']}
    for path,pin in pins.items():contract.require(contract.sha(path)==pin,'Ownership input changed during measurement: '+path)
    path=output/'ownership.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'receipt':str(path),'sha256':contract.sha(path),'measurements':results},indent=2))


if __name__=='__main__':main()
