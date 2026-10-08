"""Bounded C1 forward-Y chest terminal field with transported authored shading.

F(x,y,z)=(x,y+a*bX(abs(x))*bY(y)*bZ(z),z). For each fixed x/z, strict
monotonicity in y proves injectivity. A global determinant bound protects the
continuous field; serialized topology and discrete winding remain separate.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from conservative_face_selection import topology
from place_purposebuilt_pelvis import (BASIS, accessor, embedded_maps, node_matrix,
                                     raw_corners, read_glb, write_glb)


def step(values,left,right):
    contract.require(np.isfinite(left) and right>left,'Finite increasing transition required')
    t=np.clip((np.asarray(values,float)-left)/(right-left),0,1)
    value=t*t*(3-2*t);derivative=6*t*(1-t)/(right-left)
    return value,derivative


def bump(values,knots):
    a,b,c,d=knots;contract.require(a<b<=c<d,'Ordered C1 bump knots required')
    rising,rd=step(values,a,b);falling,fd=step(values,c,d)
    return rising*(1-falling),rd*(1-falling)-rising*fd


def determinant_bound(config):
    amplitude=config['maximumDisplacementMetres'];knots=config['yKnots']
    contract.require(np.isfinite(amplitude) and 0<amplitude<=.020,'Maximum forward displacement20mm required')
    a,b,c,d=knots;contract.require(a<b<=c<d,'Increasing forward-Y transition required')
    lower=1-amplitude*1.5/(d-c)
    contract.require(lower>.25,'Global positive determinant margin required')
    return lower


def field(points,config):
    points=np.asarray(points,float);bound=determinant_bound(config)
    contract.require(points.ndim==2 and points.shape[1]==3 and np.isfinite(points).all(),'Finite working-world positions required')
    amplitude=config['maximumDisplacementMetres']
    x,dx=step(abs(points[:,0]),*config['lateralTransition']);dx*=np.sign(points[:,0])
    y,dy=bump(points[:,1],config['yKnots']);z,dz=bump(points[:,2],config['zKnots'])
    delta=amplitude*x*y*z
    gradient=amplitude*np.column_stack((dx*y*z,x*dy*z,x*y*dz))
    result=points.copy();result[:,1]+=delta
    jac=np.tile(np.eye(3),(len(points),1,1));jac[:,1,:]+=gradient
    contract.require(np.min(np.linalg.det(jac))>=bound-1e-12,'Continuous determinant bound violated')
    return result,jac


def transport(normals,tangents,jacobian,edited):
    normals=np.asarray(normals,float);length=np.linalg.norm(normals,axis=1)
    contract.require(np.all(length>1e-8),'Valid authored normal magnitudes required')
    new=np.einsum('nij,nj->ni',np.linalg.inv(jacobian).transpose(0,2,1),normals)
    new*= (length/np.linalg.norm(new,axis=1))[:,None];new[~edited]=normals[~edited]
    transformed=None
    if tangents is not None:
        tangents=np.asarray(tangents,float);original_length=np.linalg.norm(tangents[:,:3],axis=1)
        direction=np.einsum('nij,nj->ni',jacobian,tangents[:,:3])
        unit=new/length[:,None];direction-=np.sum(direction*unit,axis=1)[:,None]*unit
        contract.require(np.all(np.linalg.norm(direction,axis=1)>1e-8),'Degenerate transported tangent')
        direction*= (original_length/np.linalg.norm(direction,axis=1))[:,None]
        transformed=tangents.copy();transformed[:,:3]=direction;transformed[~edited]=tangents[~edited]
    return new,transformed


def execute(config_path,output):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text())
    contract.require(config['schemaVersion']==2 and config['kind']=='target-terminal-field-trial' and
                     config['diagnosticOnly'] is True,'Explicit v2 diagnostic field configuration required')
    parent_path=Path(config['parentReceipt']).resolve();parent=json.loads(parent_path.read_text())
    target_path=Path(config['targetContract']).resolve();target=contract.load(target_path)
    contract.verify_binding(parent,target_path,target,'working')
    contract.require(parent['kind']=='target-part-geometry' and parent['part']=='chest' and parent['joint']=='torso_g' and
                     parent['statureApplications']==0,'Exact fitted working chest parent required')
    source=Path(parent['candidate']).resolve();archive_path=Path(parent['nativeCornerArchive']['path'])
    pins={str(parent_path):config['parentReceiptSha256'],str(source):parent['candidateSha256'],
          str(archive_path):parent['nativeCornerArchive']['sha256'],str(target_path):config['targetContractSha256'],
          **config['protectedInputs'],**parent['frozenInputs']}
    pins[str(config_path)]=contract.sha(config_path)
    for name in ('deform_target_terminal_caps.py','conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py'):
        path=Path(__file__).with_name(name).resolve();pins[str(path)]=contract.sha(path)
    for name,pin in pins.items():contract.require(contract.sha(name)==pin,'Frozen field input changed: '+name)
    document,binary=read_glb(source)
    contract.require(len(document['nodes'])==1 and document['nodes'][0].get('mesh')==0 and
                     np.array_equal(node_matrix(document['nodes'][0]),np.eye(4)), 'Canonical identity fitted geometry required')
    primitive=document['meshes'][0]['primitives'][0]
    contract.require(len(document['meshes'])==1 and len(document['meshes'][0]['primitives'])==1,'One chest primitive required')
    positions=accessor(document,binary,primitive['attributes']['POSITION']);normals=accessor(document,binary,primitive['attributes']['NORMAL'])
    faces=accessor(document,binary,primitive['indices']).reshape(-1,3).astype(int)
    active=np.zeros(len(positions),bool);active[np.unique(faces)]=True
    attachment=np.asarray(parent['attachmentWorld']);rotation=attachment[:3,:3];translation=attachment[:3,3]
    local=positions.astype(float)@BASIS.T;world=local@rotation.T+translation
    proposed,jac_world=field(world,config);jac_local=rotation.T[None,:,:]@jac_world@rotation[None,:,:]
    displacement=proposed-world;edited=active & np.any(displacement!=0,axis=1)
    # Unreferenced preserved source rows remain untouched, even within the field.
    proposed[~active]=world[~active];jac_local[~active]=np.eye(3)
    triangles=world[faces];cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    face_normals=cross/np.linalg.norm(cross,axis=1)[:,None]
    dorsal=face_normals[:,1]<=config['protectedDorsalMaximumNormalY']
    lo=triangles.min(1);hi=triangles.max(1);x_start=config['lateralTransition'][0]
    y_start,_,_,y_end=config['yKnots'];z_start,_,_,z_end=config['zKnots']
    intersects=((hi[:,0]>x_start)|(lo[:,0]<-x_start)) & (hi[:,1]>y_start)&(lo[:,1]<y_end)&(hi[:,2]>z_start)&(lo[:,2]<z_end)
    contract.require(not np.any(dorsal&intersects),'Continuous support intersects protected dorsal triangle geometry')
    central=abs(world[:,0])<=config['protectedCentralAbsXMaximum']
    contract.require(not np.any(edited[central]) and not np.any(edited[faces[dorsal]]),
                     'Protected central torso/dorsal vertex changed')
    old_normals=normals.astype(float)@BASIS.T;tangents=None
    if 'TANGENT' in primitive['attributes']:
        tangents=accessor(document,binary,primitive['attributes']['TANGENT']).astype(float);tangents[:,:3]=tangents[:,:3]@BASIS.T
    new_normals,new_tangents=transport(old_normals,tangents,jac_local,edited)
    proposed_local=(proposed-translation)@rotation
    new_positions=positions.copy();new_positions[edited]=(proposed_local[edited]@BASIS).astype('<f4')
    new_raw_normals=normals.copy();new_raw_normals[edited]=(new_normals[edited]@BASIS).astype('<f4')
    new_raw_tangents=None
    if new_tangents is not None:
        new_raw_tangents=accessor(document,binary,primitive['attributes']['TANGENT'])
        values=new_tangents.copy();values[:,:3]=values[:,:3]@BASIS
        new_raw_tangents[edited]=values[edited].astype('<f4')
    result=copy.deepcopy(document);payload=bytearray(binary)
    def append(values):
        payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(values.tobytes());payload.extend(b'\0'*(-len(payload)%4))
        result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':values.nbytes,'target':34962})
        info={'bufferView':len(result['bufferViews'])-1,'componentType':5126,'count':len(values),'type':'VEC'+str(values.shape[1])}
        if values.shape[1]==3:info.update(min=values.min(0).tolist(),max=values.max(0).tolist())
        result['accessors'].append(info);return len(result['accessors'])-1
    changed={'POSITION':new_positions,'NORMAL':new_raw_normals}
    if new_raw_tangents is not None:changed['TANGENT']=new_raw_tangents
    for semantic,rows in changed.items():result['meshes'][0]['primitives'][0]['attributes'][semantic]=append(rows)
    result['buffers'][0]['byteLength']=len(payload)
    before=topology(positions,faces);after=topology(new_positions,faces)
    contract.require(after['boundaryEdges']==after['nonmanifoldEdges']==after['inconsistentManifoldEdgeWindings']==
        after['nonmanifoldVertexLinks']==after['zeroAreaFaces']==0 and after['components']==1 and after['signedVolume']>0,
        'Serialized discrete field surface failed closed/oriented topology')
    new_triangle=(new_positions.astype(float)@BASIS.T@rotation.T+translation)[faces]
    discrete_cross=np.cross(new_triangle[:,1]-new_triangle[:,0],new_triangle[:,2]-new_triangle[:,0])
    winding_dot=np.sum(cross*discrete_cross,axis=1)/(np.linalg.norm(cross,axis=1)*np.linalg.norm(discrete_cross,axis=1))
    contract.require(np.all(winding_dot>0),'Discrete chord faces invert despite continuous field proof')
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable field trial required')
    output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,result,bytes(payload))
    actual,actualbin=read_glb(candidate);actual_primitive=actual['meshes'][0]['primitives'][0]
    contract.require(actualbin[:len(binary)]==binary and actual['materials']==document['materials'] and
                     embedded_maps(actual,actualbin)==embedded_maps(document,binary),'Source BIN/material/map definitions changed')
    for semantic,rows in changed.items():
        encoded=accessor(actual,actualbin,actual_primitive['attributes'][semantic]);original=accessor(document,binary,primitive['attributes'][semantic])
        contract.require(encoded[~edited].tobytes()==original[~edited].tobytes(),'Outside-support encoded attributes changed')
    for semantic,index in primitive['attributes'].items():
        if semantic not in changed:contract.require(actual_primitive['attributes'][semantic]==index,'Unedited UV/color accessor replaced')
    p,n,uv,records=raw_corners(actual,actualbin)
    base=np.load(archive_path,allow_pickle=False);durable={k:base[k] for k in base.files if k in
        {'sourceFaceIds','sourceTriangleIds','sourceCornerOrder','primitiveIds','sourcePositions','sourceNormals','sourceUVNative','sourceCornerIds'}}
    archive=output/'native-corners.npz';arrays={**durable,'positions':p,'normals':n,'uvGltf':uv,'uvNative':np.stack((uv[:,:,0],1-uv[:,:,1]),axis=2),
        'fieldEditedSourceVertexMask':edited,'fieldParentSourceFaces':faces,'fieldParentRawPositions':positions,
        'fieldParentRawNormals':normals,'fieldWorldDisplacement':displacement,'fieldJacobianLocal':jac_local}
    if new_raw_tangents is not None:
        arrays['tangents']=new_tangents[faces];arrays['tangentTriangleIds']=np.arange(len(faces),dtype=np.int64)
    np.savez_compressed(archive,**arrays)
    shutil.copy2(config_path,output/'config.json');(output/'tools').mkdir();snapshots={}
    for name in ('deform_target_terminal_caps.py','conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py'):
        source_code=Path(__file__).with_name(name).resolve();snapshot=output/'tools'/name;shutil.copy2(source_code,snapshot)
        snapshots[str(source_code)]={'snapshot':str(snapshot),'sha256':contract.sha(snapshot)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'bounded-posterior-terminal-field',
        **contract.binding(target_path,target,'working'),'part':'chest','joint':'torso_g','model':contract.model(target,'chest'),
        'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),
        'sourceReceiptSha256':contract.sha(parent_path),'candidate':str(candidate),'candidateSha256':contract.sha(candidate),
        'nativeCornerArchive':{'path':str(archive),'sha256':contract.sha(archive)},'statureApplications':0,
        'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),
        'nonlinearField':config,'frozenInputs':pins,'helperSnapshots':snapshots,
        'proof':{'globalContinuousDeterminantLowerBound':determinant_bound(config),
            'globalInjectivity':'For each unchanged x/z, y displacement derivative gives strictly increasing y mapping',
            'actualMinimumVertexDeterminant':float(np.linalg.det(jac_world[active]).min()),
            'actualMaximumDisplacementMetres':float(np.linalg.norm(displacement[active],axis=1).max()),
            'changedVertexCount':int(edited.sum()),'changedFaceCount':int(np.count_nonzero(np.any(edited[faces],axis=1))),
            'protectedDorsalFaceCount':int(dorsal.sum()),'protectedDorsalTriangleSupportIntersections':0,
            'centralTorsoAndDorsalGeometryExact':True,'outsideSupportEncodedPositionNormalTangentBytesExact':True,
            'uvColorMaterialImageDefinitionsExact':True,'sourceBinPrefixExact':True,'topologyUnchanged':True,
            'minimumDiscreteFaceNormalDot':float(winding_dot.min()),
            'maximumTransportedNormalMagnitudeError':float(np.max(abs(np.linalg.norm(new_normals,axis=1)-np.linalg.norm(old_normals,axis=1)))),
            'authoredTangentHandednessExact':True,'beforeTopology':before,'afterTopology':after},
        'diagnosticOnly':True,'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,
        'limitations':['Protected original terminal rims remain; a projected outline change is not implied by interior forward movement.',
            'Finite mesh chords are independently checked but client lighting/material continuity and raised/lowered shoulder poses remain gates.',
            'No arm/neck/rig geometry changed and no fit or selection was accepted.']}
    for name,pin in pins.items():contract.require(contract.sha(name)==pin,'Field input changed during execution: '+name)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    return path,receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();path,receipt=execute(args.config,args.output)
    print(json.dumps({'receipt':str(path),'receiptSha256':contract.sha(path),'candidateSha256':receipt['candidateSha256'],'proof':receipt['proof']}))
