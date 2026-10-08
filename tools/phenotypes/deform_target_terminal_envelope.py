"""Measured C1 terminal XY envelope trial preserving upper body and original maps.

Positive XY scaling at each unchanged Z proves global injectivity. Only a
pinned measured lower terminal support is affected. This trial does not infer
watertight coverage or acceptance from a neighbor radial envelope.
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
    scales=np.asarray(config['minimumXYScale'],float)
    vertical=np.asarray(config['zTransition'],float)
    centre=np.asarray(config['centreWorldXY'],float)
    contract.require(scales.shape==(2,) and np.isfinite(scales).all() and
                     np.all(scales>0) and np.all(scales<=1),
                     'Positive bounded terminal XY scales required')
    contract.require(vertical.shape==(2,) and np.isfinite(vertical).all() and vertical[0]<vertical[1],
                     'Finite increasing terminal-height transition required')
    contract.require(centre.shape==(2,) and np.isfinite(centre).all(),'Finite measured terminal centre required')
    bound=float(np.prod(scales))
    contract.require(bound>.2,'Global positive terminal determinant margin required')
    maximum=config['maximumDisplacementMetres']
    contract.require(type(maximum) in (int,float) and np.isfinite(maximum) and 0<maximum<=.08,
                     'Explicit measured terminal displacement bound up to80mm required')
    return bound


def field(points,config):
    points=np.asarray(points,float);bound=determinant_bound(config)
    contract.require(points.ndim==2 and points.shape[1]==3 and np.isfinite(points).all(),
                     'Finite working-world terminal positions required')
    step_z,dz=step(points[:,2],*config['zTransition'])
    minimum=np.asarray(config['minimumXYScale'],float)
    scale=1-(1-step_z[:,None])*(1-minimum[None,:])
    relative=points[:,:2]-np.asarray(config['centreWorldXY'])
    result=points.copy();result[:,:2]=np.asarray(config['centreWorldXY'])+relative*scale
    jac=np.tile(np.eye(3),(len(points),1,1))
    jac[:,0,0]=scale[:,0];jac[:,1,1]=scale[:,1]
    jac[:,:2,2]=relative*(1-minimum[None,:])*dz[:,None]
    upper=points[:,2]>=config['zTransition'][1]
    result[upper]=points[upper];jac[upper]=np.eye(3)
    contract.require(np.min(np.linalg.det(jac))>=bound-1e-12,'Continuous terminal determinant bound violated')
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
    contract.require(config['schemaVersion']==2 and config['kind']=='target-chest-terminal-envelope-trial' and
                     config['diagnosticOnly'] is True,'Explicit v2 diagnostic field configuration required')
    allowed={'schemaVersion','kind','diagnosticOnly','parentReceipt','parentReceiptSha256','targetContract',
             'targetContractSha256','protectedInputs','notes','maximumDisplacementMetres',
             'zTransition','centreWorldXY','minimumXYScale'}
    contract.require(set(config)<=allowed,'Unknown terminal envelope controls')
    parent_path=Path(config['parentReceipt']).resolve();parent=json.loads(parent_path.read_text())
    target_path=Path(config['targetContract']).resolve();target=contract.load(target_path)
    contract.verify_binding(parent,target_path,target,'working')
    contract.require(parent['kind']=='target-part-geometry' and parent['part']=='chest' and parent['joint']=='torso_g' and
                     parent['statureApplications']==0 and parent['operation'] in ('fit','bounded-inward-waist-field'),
                     'Original fit or single waist-taper working parent required; repeated terminal conversion rejected')
    source=Path(parent['candidate']).resolve();archive_path=Path(parent['nativeCornerArchive']['path'])
    pins={str(parent_path):config['parentReceiptSha256'],str(source):parent['candidateSha256'],
          str(archive_path):parent['nativeCornerArchive']['sha256'],str(target_path):config['targetContractSha256'],
          **config['protectedInputs'],**parent['frozenInputs']}
    pins[str(config_path)]=contract.sha(config_path)
    for name in ('deform_target_terminal_envelope.py','conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py'):
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
    central=np.zeros(len(world),bool)
    upper=world[:,2]>=config['zTransition'][1]
    contract.require(not np.any(edited[central|upper]),'Protected upper body vertex changed')
    contract.require(np.array_equal(proposed[:,2],world[:,2]),'Terminal field may change only XY')
    contract.require(np.max(np.linalg.norm(displacement[active],axis=1))<=config['maximumDisplacementMetres']+1e-12,
                     'Actual measured terminal displacement exceeds explicit bound')
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
    topology_keys=('boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings',
                   'nonmanifoldVertexLinks','zeroAreaFaces','components','eulerCharacteristic')
    contract.require(all(before[k]==after[k] for k in topology_keys),
                     'Serialized terminal field introduced a topology change')
    new_triangle=(new_positions.astype(float)@BASIS.T@rotation.T+translation)[faces]
    discrete_cross=np.cross(new_triangle[:,1]-new_triangle[:,0],new_triangle[:,2]-new_triangle[:,0])
    winding_dot=np.sum(cross*discrete_cross,axis=1)/(np.linalg.norm(cross,axis=1)*np.linalg.norm(discrete_cross,axis=1))
    contract.require(np.all(winding_dot>0),'Discrete chord faces invert despite continuous field proof')
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable terminal envelope trial required')
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
    # Transport the parent's double-precision native corners independently;
    # outside-support authoritative values are never round-tripped through GLB.
    cp=base['positions'];cn=base['normals'];cu=base['uvGltf']
    cw=cp.reshape(-1,3)@rotation.T+translation
    cq,cj=field(cw,config);ce=np.any(cq!=cw,axis=1)
    cl=rotation.T[None,:,:]@cj@rotation[None,:,:]
    ct=base['tangents'].reshape(-1,4) if 'tangents' in base.files else None
    nn,tt=transport(cn.reshape(-1,3),ct,cl,ce)
    lp=(cq-translation)@rotation;lp[~ce]=cp.reshape(-1,3)[~ce]
    arrays['positions']=lp.reshape(cp.shape);arrays['normals']=nn.reshape(cn.shape)
    arrays['uvGltf']=cu.copy();arrays['uvNative']=base['uvNative'].copy()
    if tt is not None: arrays['tangents']=tt.reshape(base['tangents'].shape)
    contract.require(np.max(abs(p-arrays['positions']))<1e-7 and np.max(abs(n-arrays['normals']))<1e-6,
                     'Serialized terminal field differs from authoritative corner transport')
    contract.require(np.array_equal(uv,cu),'Original UV corners changed')
    corner_outside=~ce.reshape(cp.shape[:2])
    contract.require(np.array_equal(arrays['positions'][corner_outside],cp[corner_outside]) and
                     np.array_equal(arrays['normals'][corner_outside],cn[corner_outside]),
                     'Outside-support authoritative native corners changed')
    np.savez_compressed(archive,**arrays)
    shutil.copy2(config_path,output/'config.json');(output/'tools').mkdir();snapshots={}
    for name in ('deform_target_terminal_envelope.py','conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py'):
        source_code=Path(__file__).with_name(name).resolve();snapshot=output/'tools'/name;shutil.copy2(source_code,snapshot)
        snapshots[str(source_code)]={'snapshot':str(snapshot),'sha256':contract.sha(snapshot)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'bounded-terminal-xy-envelope-field',
        **contract.binding(target_path,target,'working'),'part':'chest','joint':'torso_g','model':contract.model(target,'chest'),
        'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),
        'sourceReceiptSha256':contract.sha(parent_path),'candidate':str(candidate),'candidateSha256':contract.sha(candidate),
        'nativeCornerArchive':{'path':str(archive),'sha256':contract.sha(archive)},'statureApplications':0,
        'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),
        'nonlinearField':config,'frozenInputs':pins,'helperSnapshots':snapshots,
        'proof':{'globalContinuousDeterminantLowerBound':determinant_bound(config),
            'globalInjectivity':'For each unchanged Z, positive diagonal XY scales give an injective affine plane mapping; Z unchanged, hence global injectivity',
            'actualMinimumVertexDeterminant':float(np.linalg.det(jac_world[active]).min()),
            'actualMaximumDisplacementMetres':float(np.linalg.norm(displacement[active],axis=1).max()),
            'changedVertexCount':int(edited.sum()),'changedFaceCount':int(np.count_nonzero(np.any(edited[faces],axis=1))),
            'protectedCentralVertexCount':int(central.sum()),'protectedUpperVertexCount':int(upper.sum()),
            'upperBodyEncodedAttributesExact':True,'worldZExact':True,'lowerCentralAbdomenAffected':True,
            'outsideSupportEncodedPositionNormalTangentBytesExact':True,
            'uvColorMaterialImageDefinitionsExact':True,'sourceBinPrefixExact':True,'topologyUnchanged':True,
            'minimumDiscreteFaceNormalDot':float(winding_dot.min()),
            'maximumTransportedNormalMagnitudeError':float(np.max(abs(np.linalg.norm(new_normals,axis=1)-np.linalg.norm(old_normals,axis=1)))),
            'authoritativeOutsideSupportNativeCornersExact':True,'nativeCornerDerivation':'Parent double precision transported independently; no outside-support roundtrip','authoredTangentHandednessExact':True,'beforeTopology':before,'afterTopology':after},
        'diagnosticOnly':True,'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,
        'limitations':['Measured lower terminal XY trial only. It can affect central lower abdomen within declared support; upper abdomen and bra remain exact.',
            'Neighbor radial contours are finite measurements, not solid coverage proof. New pelvis descendants reopen full connector/motion checks.',
            'Original upper torso/cloth, rig and neighbor bytes stay exact. Original hidden inner-shell and garment defects remain unresolved; no production/client selection.']}
    for name,pin in pins.items():contract.require(contract.sha(name)==pin,'Field input changed during execution: '+name)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    return path,receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();path,receipt=execute(args.config,args.output)
    print(json.dumps({'receipt':str(path),'receiptSha256':contract.sha(path),'candidateSha256':receipt['candidateSha256'],'actualMaximumDisplacementMetres':receipt['proof']['actualMaximumDisplacementMetres'],'globalDeterminantLowerBound':receipt['proof']['globalContinuousDeterminantLowerBound']}))
