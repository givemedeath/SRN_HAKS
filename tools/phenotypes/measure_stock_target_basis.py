"""Read-only stock body/held geometry measurements bound to a stock-exact target.

Native static body/held trees use pointer identities independently of decompiled
names. Measurements preserve installed axes and scales and do not accept game
socket hypotheses, equipment fit, joint continuity, or client rendering.
"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import target_contract as contract
from audit_native_static_equipment import decode_static_equipment
from measure_held_equipment import bounds
from audit_geometry import arrays
from retarget import NODE,nodes
from rig_controller_audit import world_frames
from inspect_stock_joints import PAIRS

LIMBS = {'leftUpperArm':('lbicep_g','lforearm_g'),'rightUpperArm':('rbicep_g','rforearm_g'),
         'leftForearm':('lforearm_g','lhand_g'),'rightForearm':('rforearm_g','rhand_g'),
         'leftThigh':('lthigh_g','lshin_g'),'rightThigh':('rthigh_g','rshin_g'),
         'leftShin':('lshin_g','lfoot_g'),'rightShin':('rshin_g','rfoot_g')}
SOCKETS = ('head_g','head','lhand_g','rhand_g','lhand','rhand','handconjure','headconjure')


def ascii_world_triangles(text, attachment):
    text=text.split('endmodelgeom',1)[0];local=world_frames(nodes(text));chunks=[]
    for block in NODE.finditer(text):
        vertices=np.asarray(arrays(block[3],'verts'),float);faces=np.asarray(arrays(block[3],'faces'),float)
        if not len(vertices) or not len(faces):continue
        ids=faces[:,:3].astype(int);contract.require(np.array_equal(ids,faces[:,:3]),'Integer stock triangle indices required')
        frame=attachment@local[block[2].lower()];world=vertices@frame[:3,:3].T+frame[:3,3]
        chunks.append(world[ids])
    contract.require(chunks,'Stock ASCII contains no body triangles');return np.concatenate(chunks)


def section_points(triangles, origin, axis, offset):
    triangles=np.asarray(triangles,float);origin=np.asarray(origin,float);axis=np.asarray(axis,float)
    contract.require(triangles.ndim==3 and triangles.shape[1:]==(3,3) and np.isfinite(triangles).all() and np.isfinite(axis).all() and np.linalg.norm(axis)>0,'Finite stock section triangles and nonzero axis required')
    axis=axis/np.linalg.norm(axis);signed=(triangles-origin)@axis-offset;points=[]
    for first,last in ((0,1),(1,2),(2,0)):
        a,b=signed[:,first],signed[:,last];cross=(a*b<0)
        if cross.any():
            fraction=a[cross]/(a[cross]-b[cross]);points.extend(triangles[cross,first]+fraction[:,None]*(triangles[cross,last]-triangles[cross,first]))
        points.extend(triangles[np.abs(a)<=1e-10,first])
    if not points:return np.empty((0,3))
    points=np.asarray(points,float);_,indices=np.unique(np.rint(points/1e-9).astype('i8'),axis=0,return_index=True)
    return points[np.sort(indices)]


def measure(target_path, baseline_path, equipment_path, held_path, output):
    target_path,baseline_path,equipment_path,held_path = [Path(path).resolve() for path in (target_path,baseline_path,equipment_path,held_path)]
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable stock measurements required')
    target=contract.load(target_path);contract.require(contract.rig_mode(target)=='stock-exact','Stock-exact reference required')
    proof_path=Path(target['rig']['stockReferenceReceipt']['path']).resolve();proof=json.loads(proof_path.read_text())
    baseline=json.loads(baseline_path.read_text());equipment=json.loads(equipment_path.read_text());held=json.loads(held_path.read_text())
    prefix=target['identity']['prefix'];contract.require(equipment['sourcePrefix']==prefix and held['sourcePrefix']==prefix,'Cross-family equipment measurements')
    contract.require(held['sourceInventory']['sha256']==contract.sha(equipment_path),'Held source inventory changed')
    contract.verify_binding(held['target'],target_path,target,'runtime')
    frozen={str(path):contract.sha(path) for path in (target_path,proof_path,baseline_path,equipment_path,held_path)}
    def pin(path,expected):
        path=Path(path).resolve();contract.require(contract.sha(path)==expected,'Frozen stock measurement input changed: '+str(path));frozen[str(path)]=expected;return path
    resources={row['name']:row for row in baseline['resources']};stock=baseline_path.parent
    frames={name:np.asarray(frame,float) for name,frame in proof['frames'].items()}
    limbs={name:{'fromJoint':start,'toJoint':end,'lengthMeters':float(np.linalg.norm(frames[start][:3,3]-frames[end][:3,3])),
                 'fromWorld':frames[start][:3,3].tolist(),'toWorld':frames[end][:3,3].tolist()} for name,(start,end) in LIMBS.items()}
    body={};archive={};failures=[];native_points=[];ascii_triangles={}
    for part,joint in contract.PART_JOINTS.items():
        name=prefix+'_'+part+'001.mdl';row=resources[name]
        raw=pin(stock/'raw'/name,row['sha256']);ascii_path=pin(stock/'ascii'/name,row['asciiSha256'])
        ascii_triangles[part]=ascii_world_triangles(ascii_path.read_text(encoding='ascii'),frames[joint])
        ascii_points=np.unique(ascii_triangles[part].reshape(-1,3),axis=0);archive[part+'_decompiledWorldPositions']=ascii_points
        body[part]={'nativeSha256':contract.sha(raw),'asciiSha256':contract.sha(ascii_path),'nativePointerHierarchyDecoded':False,
                    'decompiledWorldMinimum':ascii_points.min(0).tolist(),'decompiledWorldMaximum':ascii_points.max(0).tolist(),
                    'decompiledWorldExtentMeters':np.ptp(ascii_points,axis=0).tolist(),'attachment':frames[joint].tolist()}
        if part.startswith('foot'):
            minimum=float(ascii_points[:,2].min());band=ascii_points[ascii_points[:,2]<=minimum+.005]
            body[part]['decompiledSole']={'minimumWorldZ':minimum,'lowestFiveMillimetresVertices':len(band),
                                         'bandXYMinimum':band[:,:2].min(0).tolist(),'bandXYMaximum':band[:,:2].max(0).tolist(),
                                         'floorPlaneHypothesisZ':0,'floorPlacementClientAccepted':False}
        try:
            decoded=decode_static_equipment(raw.read_bytes())
            meshes=[mesh for mesh in decoded['meshes'] if mesh['render']]
            contract.require(meshes,'No rendered native stock mesh')
            points=np.vstack([mesh['worldPositions'] for mesh in meshes]);world=points@frames[joint][:3,:3].T+frames[joint][:3,3]
            native_points.append(world);archive[part+'_worldPositions']=world
            measured=bounds(ascii_path.read_text(encoding='ascii'))
            native_bounds=decoded['bounds'];delta=max(float(np.max(np.abs(np.asarray(native_bounds[key])-measured[key]))) for key in ('minimumModelLocalNwn','maximumModelLocalNwn'))
            contract.require(delta<=2e-6,'Native/decompiled body bounds differ')
            body[part].update({'nativeSha256':contract.sha(raw),'asciiSha256':contract.sha(ascii_path),'renderedVertices':len(world),
                        'worldMinimum':world.min(0).tolist(),'worldMaximum':world.max(0).tolist(),'worldExtentMeters':np.ptp(world,axis=0).tolist(),
                        'maximumNativeAsciiBoundsDifferenceMeters':delta,'nativePointerHierarchyDecoded':True,'attachment':frames[joint].tolist()})
            if part.startswith('foot'):
                minimum=float(world[:,2].min());band=world[world[:,2]<=minimum+.005]
                body[part]['sole']={'minimumWorldZ':minimum,'lowestFiveMillimetresVertices':len(band),
                                    'bandXYMinimum':band[:,:2].min(0).tolist(),'bandXYMaximum':band[:,:2].max(0).tolist(),
                                    'floorPlaneHypothesisZ':0,'floorPlacementClientAccepted':False}
        except (ValueError,RuntimeError) as error:
            failures.append({'resource':name,'measurement':'independent native/static body measurement','failure':str(error)})
    equipment_by_name={row['resource']:row for row in equipment['models']}
    held_by_name={row['resource']:row for row in held['weaponSamples']}
    selected={}
    names=['helm_001.mdl','helm_019.mdl','pfh0_chest020.mdl','pfh0_chest021.mdl'] if prefix=='pfh0' else ['helm_001.mdl','helm_019.mdl',prefix+'_chest020.mdl',prefix+'_chest021.mdl']
    names += sorted(name for name in held_by_name if name.startswith('wswls_'))
    names += sorted(name for name in equipment_by_name if name.startswith('ashls_') and name.endswith('_011.mdl'))
    for name in names:
        row=equipment_by_name.get(name) or held_by_name.get(name);contract.require(row is not None,'Missing declared representative: '+name)
        raw=pin(row['rawPath'],row.get('rawSha256') or row['sha256']);ascii_path=pin(row['asciiPath'],row['asciiSha256'])
        try:
            native=decode_static_equipment(raw.read_bytes());measured=None;ascii_failure=None
            try:measured=bounds(ascii_path.read_text(encoding='ascii'))
            except (ValueError,RuntimeError) as error:ascii_failure=str(error)
            delta=None
            if measured is not None and native['bounds'] is not None:
                delta=max(float(np.max(np.abs(np.asarray(native['bounds'][key])-measured[key]))) for key in ('minimumModelLocalNwn','maximumModelLocalNwn'))
                contract.require(delta<=2e-6,'Native/decompiled equipment bounds differ')
            archive[name[:-4]+'_modelPositions']=np.vstack([mesh['worldPositions'] for mesh in native['meshes'] if mesh['render']])
            selected[name]={'nativePath':str(raw),'nativeSha256':contract.sha(raw),'asciiPath':str(ascii_path),'asciiSha256':contract.sha(ascii_path),
                            'nativeBounds':native['bounds'],'maximumNativeAsciiBoundsDifferenceMeters':delta,'asciiMeasurementLimit':ascii_failure,
                            'duplicateNativeLabels':native['duplicateNames'],'nativePointerHierarchyDecoded':True,'renderTextureDependencies':row.get('renderTextureDependencies',[]),
                            'sharedResourceModified':False,'equipmentFitAccepted':False}
        except (ValueError,RuntimeError) as error:failures.append({'resource':name,'measurement':'independent native/static equipment measurement','failure':str(error)})
    native_height=None
    if all(row['nativePointerHierarchyDecoded'] for row in body.values()):
        points=np.vstack(native_points);native_height=float(np.ptp(points[:,2]));contract.require(abs(native_height-target['heightMeters'])<=3e-6,'Native assembled height differs from authoritative stock height')
    sections=[]
    for parent,child in PAIRS:
        origin=frames[contract.PART_JOINTS[child]][:3,3];axis=origin-frames[contract.PART_JOINTS[parent]][:3,3]
        if np.linalg.norm(axis)<1e-9:axis=np.array([0.,0.,-1.])
        axis=axis/np.linalg.norm(axis);reference=np.eye(3)[int(np.argmin(np.abs(axis)))];first=np.cross(axis,reference);first/=np.linalg.norm(first);second=np.cross(axis,first)
        row={'parent':parent,'child':child,'originWorld':origin.tolist(),'axisWorld':axis.tolist(),'inPlaneBasisWorld':[first.tolist(),second.tolist()],'sections':[]}
        for offset in (-.01,0,.01):
            band={'axialOffsetMeters':offset,'parts':{}}
            for part in (parent,child):
                points=section_points(ascii_triangles[part],origin,axis,offset);archive[parent+'_'+child+'_'+part+'_'+str(offset)+'_section']=points
                planar=(points-origin)@np.stack([first,second],axis=1) if len(points) else None
                band['parts'][part]={'intersectedPoints':len(points),'inPlaneMinimum':planar.min(0).tolist() if len(points) else None,
                                     'inPlaneMaximum':planar.max(0).tolist() if len(points) else None,'closedContourOrCoverageAccepted':False}
            row['sections'].append(band)
        sections.append(row)
    output.mkdir(parents=True);snapshots=output/'helper-snapshots';snapshots.mkdir()
    for name in ('measure_stock_target_basis.py','audit_native_static_equipment.py','measure_held_equipment.py','armory_rigid.py','inventory_target_equipment.py','target_contract.py','retarget.py','audit_geometry.py','rig_controller_audit.py','inspect_stock_joints.py'):
        path=Path(__file__).with_name(name);copy=snapshots/name;shutil.copyfile(path,copy);frozen[str(copy)]=contract.sha(copy)
    data=output/'native-positions.npz';np.savez_compressed(data,**archive)
    result={'schemaVersion':1,'kind':'stock-target-body-equipment-measurements',**contract.binding(target_path,target,'runtime'),
            'sourcePrefix':prefix,'sourceOverridesDisabled':equipment['overridesDisabled'],'authoritativeStockHeightMeters':target['heightMeters'],
            'independentlyDecodedNativeHeightMeters':native_height,'rigOrEquipmentFramesChanged':False,'limbPivotLengths':limbs,'nativeBodyParts':body,
            'decompiledJointPlaneSections':sections,'nativeDecodedBodyPartCount':sum(row['nativePointerHierarchyDecoded'] for row in body.values()),
            'heldSocketFrames':{name:frames[name].tolist() for name in SOCKETS},'installedHelmetScale':held['target']['helmetScaleRecommendation'],
            'representativeEquipment':selected,'nativeMeasurementFailures':failures,'sourceMissingMaterialReferences':equipment['missingDependencies'],
            'priorAsciiHeldMeasurementFailures':held['measurementFailures'],'nativePositionArchive':{'path':str(data),'sha256':contract.sha(data)},
            'frozenInputs':frozen,'clientAccepted':False,'equipmentFitAccepted':False,'materialDependencyClosureAccepted':False,
            'limitations':['Static pointer-tree decoding verifies native geometry only; socket and floor placement in the engine remain client gates.',
                           'Bounds and bone lengths do not prove connector coverage, joint motion or closed surfaces.',
                           'The full installed inventory contains unresolved material references listed independently of candidate resources.',
                           'Held source ASCII rejects duplicate labels such as helm_019; native pointer identities measure those trees independently.']}
    contract.require(all(contract.sha(path)==value for path,value in frozen.items()),'Frozen measurement input changed during audit')
    receipt=output/'measurements.json';receipt.write_text(json.dumps(result,indent=2)+'\n');return receipt,result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','stock-baseline','equipment-inventory','held-measurements','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();receipt,result=measure(args.target_contract,args.stock_baseline,args.equipment_inventory,args.held_measurements,args.output)
    print(json.dumps({'receipt':str(receipt),'sha256':contract.sha(receipt),'nativeBodyParts':result['nativeDecodedBodyPartCount'],
                      'nativeHeightMeters':result['independentlyDecodedNativeHeightMeters'],'equipmentSamples':len(result['representativeEquipment']),
                      'measurementFailures':result['nativeMeasurementFailures'],'clientAccepted':False}))
