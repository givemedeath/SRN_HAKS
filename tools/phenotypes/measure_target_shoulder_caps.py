"""CPU BVH shoulder ownership/exposure measurements; no trimming or adoption."""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import target_contract as contract
from place_purposebuilt_pelvis import raw_corners, read_glb


def world(corners,frame):
    shape=corners.shape
    return (np.c_[corners.reshape(-1,3),np.ones(corners.size//3)]@frame.T)[:,:3].reshape(shape)


def bvh(corners):
    vertices=corners.reshape(-1,3);faces=np.arange(len(vertices)).reshape(-1,3)
    return BVHTree.FromPolygons([Vector(v) for v in vertices],faces.tolist(),all_triangles=True)


def y_section(triangles,z):
    mask=(triangles[:,:,2].min(1)<=z)&(triangles[:,:,2].max(1)>=z)
    rows=triangles[mask];values=[]
    for a,b in ((0,1),(1,2),(2,0)):
        p,q=rows[:,a],rows[:,b];delta=q[:,2]-p[:,2]
        active=(np.minimum(p[:,2],q[:,2])<=z)&(np.maximum(p[:,2],q[:,2])>=z)&(abs(delta)>1e-12)
        factor=(z-p[active,2])/delta[active]
        values.extend((p[active,1]+factor*(q[active,1]-p[active,1])).tolist())
    return (min(values),max(values)) if values else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--chest-receipt',type=Path,required=True)
    parser.add_argument('--left-receipt',type=Path,required=True)
    parser.add_argument('--right-receipt',type=Path,required=True)
    parser.add_argument('--face-selection',type=Path,required=True)
    parser.add_argument('--pose-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    target_path=args.target_contract.resolve();target=contract.load(target_path);pins={str(target_path):contract.sha(target_path)}
    parts={};receipts={}
    for part,path in [('chest',args.chest_receipt),('bicepl',args.left_receipt),('bicepr',args.right_receipt)]:
        path=path.resolve();receipt=json.loads(path.read_text());contract.verify_binding(receipt,target_path,target,'working')
        contract.require(receipt['kind']=='target-part-geometry' and receipt['schemaVersion']==2 and receipt['part']==part,
                         'Exact target-working part receipt required')
        contract.require(receipt['joint']==contract.PART_JOINTS[part] and receipt['model']==contract.model(target,part) and
                         receipt['statureApplications']==0,'Part ownership or scale count differs')
        candidate=Path(receipt['candidate']).resolve();contract.require(contract.sha(candidate)==receipt['candidateSha256'],
                                                                      'Selected candidate changed')
        for name,pin in receipt['frozenInputs'].items():
            contract.require(contract.sha(name)==pin,'Geometry input changed: '+name);pins[name]=pin
        pins[str(path)]=contract.sha(path);pins[str(candidate)]=contract.sha(candidate)
        parts[part]=raw_corners(*read_glb(candidate))[0];receipts[part]=receipt
    selection_path=args.face_selection.resolve();selection=json.loads(selection_path.read_text())
    contract.require(selection['sourceSha256']==receipts['chest']['sourceSha256'] and
                     selection['targetContractSha256']==contract.sha(target_path),'Chest selection lineage differs')
    archive_path=Path(selection['faceSelectionArchive']['path']);contract.require(contract.sha(archive_path)==selection['faceSelectionArchive']['sha256'],
                                                                               'Face selection archive changed')
    kept=np.asarray(selection['keptOriginalFaceIds'],np.int64);data=np.load(archive_path,allow_pickle=False)
    contract.require(np.array_equal(kept,data['keptSourceFaceIds']) and len(parts['chest'])==len(data['sourceFaces']),
                     'Exact source/fitted face correspondence required')
    pins[str(selection_path)]=contract.sha(selection_path);pins[str(archive_path)]=contract.sha(archive_path)
    pose_path=args.pose_receipt.resolve();pose=json.loads(pose_path.read_text())
    specimen=next(row for row in pose['specimens'] if row.get('target'))
    contract.verify_binding(specimen['target'],target_path,target,'working')
    for part,receipt in receipts.items():
        matches=[row for row in specimen['targetPartReceipts'] if row['part']==part]
        contract.require(len(matches)==1 and matches[0]['candidateSha256']==receipt['candidateSha256'],
                         'Pose report refers to another chest/arm fit')
    pins[str(pose_path)]=contract.sha(pose_path)
    frames={'bind':{part:np.asarray(receipt['attachmentWorld']) for part,receipt in receipts.items()},
            'pause1':{part:np.asarray(specimen['jointWorldMatrices'][contract.PART_JOINTS[part]]) for part in parts}}
    cap_bind=world(parts['chest'],frames['bind']['chest']);side_masks={}
    cross=np.cross(cap_bind[:,1]-cap_bind[:,0],cap_bind[:,2]-cap_bind[:,0])
    bind_normals=cross/np.linalg.norm(cross,axis=1)[:,None]
    terminal_limits={}
    # Provisional measurement zones protect the central torso and entire back
    # inward of |X|=.205m. They identify a later bounded trial, not selected cuts.
    for side,sign in [('left',-1),('right',1)]:
        terminal_limits[side]=float(np.max(cap_bind[:,:,0]*sign)-.015)
        lateral=np.all(cap_bind[:,:,0]*sign>=max(.210,terminal_limits[side]),axis=1)
        vertical=np.all((cap_bind[:,:,2]>=1.43)&(cap_bind[:,:,2]<=1.68),axis=1)
        outward=bind_normals[:,0]*sign>=.8
        side_masks[side]=lateral&vertical&outward
    rows=[];archives={}
    for state,state_frames in frames.items():
        chest_world=world(parts['chest'],state_frames['chest']);outer=chest_world[kept];chest_tree=bvh(outer)
        for side,sign,part in [('left',-1,'bicepl'),('right',1,'bicepr')]:
            cap_mask=side_masks[side][kept];cap=outer[cap_mask]
            contract.require(len(cap)>0,'No measured lateral chest shoulder region')
            arm=world(parts[part],state_frames[part]);arm_tree=bvh(arm)
            cap_points=cap.reshape(-1,3);arm_points=arm.reshape(-1,3);centers=cap.mean(1)
            minimum=cap_points.min(0);maximum=cap_points.max(0)
            yvalues=np.linspace(minimum[1]-.005,maximum[1]+.005,160)
            zvalues=np.linspace(minimum[2]-.005,maximum[2]+.005,160)
            grid=np.zeros((160,160),np.uint8);posterior=[];anterior=[]
            for zi,z in enumerate(zvalues):
                section=y_section(arm,float(z))
                for yi,y in enumerate(yvalues):
                    origin=Vector((sign*2.,float(y),float(z)));direction=Vector((-sign,0,0))
                    chest_hit,_,face,chest_distance=chest_tree.ray_cast(origin,direction,4.)
                    if face is None or not cap_mask[face]:continue
                    _,_,arm_face,arm_distance=arm_tree.ray_cast(origin,direction,4.)
                    if arm_face is None:
                        grid[zi,yi]=2
                        if section:
                            posterior.append(max(0.,section[0]-y));anterior.append(max(0.,y-section[1]))
                    elif chest_distance<arm_distance-1e-6:grid[zi,yi]=3
                    else:grid[zi,yi]=1
            closest=[];nearest_signed=[]
            for point in centers:
                location,normal,_,distance=arm_tree.find_nearest(Vector(point))
                closest.append(distance);nearest_signed.append(float(np.dot(point-np.asarray(location),np.asarray(normal))))
            extent=np.minimum(maximum,arm_points.max(0))-np.maximum(minimum,arm_points.min(0))
            area=(yvalues[1]-yvalues[0])*(zvalues[1]-zvalues[0])
            actual_exposed=np.count_nonzero((grid==2)|(grid==3))
            rows.append({'state':state,'side':side,'chestShoulderSourceFaceCount':len(cap),
                'worldMinimum':minimum.tolist(),'worldMaximum':maximum.tolist(),
                'armWorldMinimum':arm_points.min(0).tolist(),'armWorldMaximum':arm_points.max(0).tolist(),
                'shoulderCapArmAabbIntersectionExtent':np.maximum(extent,0).tolist(),
                'shoulderCapArmAabbIntersectionVolume':float(np.maximum(extent,0).prod()),
                'sideProjectionGrid':{'resolution':[160,160],'projection':'orthographic along lateral X',
                    'cellAreaMetresSquared':area,'chestCapCoveredByArmCells':int(np.count_nonzero(grid==1)),
                    'capWithoutArmSilhouetteCells':int(np.count_nonzero(grid==2)),
                    'capInFrontOfArmCells':int(np.count_nonzero(grid==3)),
                    'exposedCapAreaMetresSquared':float(actual_exposed*area),
                    'maximumPosteriorBeyondArmSectionMetres':max(posterior,default=0.),
                    'maximumAnteriorBeyondArmSectionMetres':max(anterior,default=0.)},
                'nearestArmSurfaceFromCapCentroid':{'minimumDistanceMetres':min(closest),
                    'medianDistanceMetres':float(np.median(closest)),'withinOneMillimetre':int(np.count_nonzero(np.asarray(closest)<=.001)),
                    'withinFiveMillimetres':int(np.count_nonzero(np.asarray(closest)<=.005)),
                    'negativeNearestNormalDotCount':int(np.count_nonzero(np.asarray(nearest_signed)<0)),
                    'limitation':'Negative nearest-normal dot or AABB overlap is not a proof of inside volume or triangle collision.'}})
            archives[state+'_'+side+'_sideProjection']=grid
            archives[state+'_'+side+'_projectionY']=yvalues;archives[state+'_'+side+'_projectionZ']=zvalues
            archives[state+'_'+side+'_measuredSourceFaceIds']=kept[cap_mask]
            archives[state+'_'+side+'_nearestArmDistance']=np.asarray(closest)
    output=args.output.resolve();contract.require(not output.exists(),'Fresh read-only shoulder evidence required')
    output.mkdir(parents=True);(output/'tools').mkdir();helpers={}
    for name in ('measure_target_shoulder_caps.py','place_purposebuilt_pelvis.py','target_contract.py'):
        source=Path(__file__).with_name(name).resolve();pins[str(source)]=contract.sha(source)
        copy=output/'tools'/name;shutil.copy2(source,copy);helpers[str(source)]={'snapshot':str(copy),'sha256':contract.sha(copy)}
    archive=output/'shoulder-exposure.npz';np.savez_compressed(archive,**archives)
    report={'schemaVersion':2,'kind':'target-shoulder-cap-ownership-measurement','readOnly':True,
        'target':contract.binding(target_path,target,'working'),'bodyInputs':{part:receipt['candidateSha256'] for part,receipt in receipts.items()},
        'classificationZones':{'minimumLateralAbsX':.210,'worldZInterval':[1.43,1.68],
            'terminalLateralStripThicknessMetres':.015,'terminalLateralLowerBounds':terminal_limits,
            'minimumOutwardGeometricNormalLateralDot':.8,
            'protectedCentralAbsXMaximum':.205,'wholeArmGeometryProtected':True,
            'policy':'All candidate face vertices must lie outside the guard band and within the terminal shoulder height interval'},
        'measurements':rows,'archive':{'path':str(archive),'sha256':contract.sha(archive)},
        'boundedRecommendation':{'selected':False,'operation':'Later explicit shallow chest shoulder connector trimming only',
            'proposedMaximumWorkingDepthChangeMetres':.030,'protectedCentralTorsoAndBackAbsXMaximum':.205,
            'protectedArmGeometry':'Entire exact fitted left/right candidates',
            'controlsRequired':['Reviewed local connector bands and a smooth transition outside central protection',
                'Exact source face/vertex correspondence and kept exterior attribute preservation',
                'Closed topology, normal/UV continuity and shoulder motion across raised/lowered/forward/rear poses'],
            'limitation':'The30mm bound is a trial ceiling, not a measured accepted solution; larger projected excess remains for root review.'},
        'sourceOrFitChanged':False,'trimmedDescendantWritten':False,'rigPilotAccepted':False,'clientAccepted':False,
        'frozenInputs':pins,'helperSnapshots':helpers,
        'limitations':['Orthographic projection exposure does not establish3D collisions.',
            'Measured terminal zones are provisional, not an anatomical muscle ownership acceptance.',
            'Only bind and the exact archived pause1 pose are sampled here.']}
    for path,pin in pins.items():contract.require(contract.sha(path)==pin,'Shoulder input changed during measurement: '+path)
    path=output/'shoulder-cap-exposure.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'receipt':str(path),'sha256':contract.sha(path),'measurements':rows}),flush=True)


if __name__=='__main__':main()
