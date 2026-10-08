"""Diagnostic face-aware chest connector confined below a measured split plane.

The source clean lower disk is retained and reshaped, never deleted. Exact
plane splitting prevents altered lower chord faces from crossing the protected
upper surface. All new corners carry source face and barycentric ancestry.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from conservative_face_selection import topology
from deform_target_terminal_envelope import transport
from place_purposebuilt_pelvis import (BASIS, accessor, embedded_maps, node_matrix,
                                     raw_corners, read_glb, write_glb)


def connector_field(points, plane, full_z, centre, scales):
    """Positive per-Z XY map in attachment-local coordinates, identity above plane."""
    points=np.asarray(points,float);centre=np.asarray(centre,float);scales=np.asarray(scales,float)
    contract.require(points.ndim==2 and points.shape[1]==3 and np.isfinite(points).all(),
                     'Finite attachment-local points required')
    contract.require(np.isfinite(plane) and np.isfinite(full_z) and full_z<plane<0,
                     'Connector support must end below the rig pivot')
    contract.require(centre.shape==(2,) and np.isfinite(centre).all() and
                     scales.shape==(2,) and np.isfinite(scales).all() and
                     np.all(scales>0) and np.all(scales<=1) and np.prod(scales)>=.25,
                     'Positive bounded connector XY scales and determinant margin required')
    t=np.clip((points[:,2]-full_z)/(plane-full_z),0,1)
    h=t*t*(3-2*t);dh=6*t*(1-t)/(plane-full_z)
    scale=scales[None,:]+h[:,None]*(1-scales[None,:])
    relative=points[:,:2]-centre
    output=points.copy();output[:,:2]=centre+relative*scale
    jac=np.tile(np.eye(3),(len(points),1,1));jac[:,0,0]=scale[:,0];jac[:,1,1]=scale[:,1]
    jac[:,:2,2]=relative*(1-scales[None,:])*dh[:,None]
    protected=points[:,2]>=plane
    output[protected]=points[protected];jac[protected]=np.eye(3)
    return output,jac


def split_at_plane(attributes, faces, plane):
    """Clip crossing faces into exact upper/lower polygons; retain all source rows.

    Plane is canonical float32 attachment-local Z (= glTF Y). Split-edge position
    is evaluated in canonical exact-coordinate endpoint order, making duplicate
    UV-seam edges coincide. Attribute rows are interpolated on their own raw
    edges; normals/tangents are never averaged across a seam.
    """
    attributes={k:np.asarray(v) for k,v in attributes.items()}
    contract.require(set(attributes)<= {'POSITION','NORMAL','TEXCOORD_0','TANGENT'} and
                     {'POSITION','NORMAL','TEXCOORD_0'}<=set(attributes),
                     'Explicit position/normal/UV and optional tangent semantics required')
    positions=attributes['POSITION']
    contract.require(all(v.dtype==np.dtype('<f4') and len(v)==len(positions) and np.isfinite(v).all()
                         for v in attributes.values()),'Finite float32 source attribute rows required')
    faces=np.asarray(faces,dtype=np.int64);plane=float(np.float32(plane))
    contract.require(faces.ndim==2 and faces.shape[1]==3 and faces.min()>=0 and
                     faces.max()<len(positions),'Indexed triangles required')
    rows={k:list(v.copy()) for k,v in attributes.items()};edge_cache={};edge_lineage={}
    result=[];parents=[];weights=[];upper=[];crossing=[]
    original_count=len(positions)

    def intersection(fid,ia,ib):
        a=int(faces[fid,ia]);b=int(faces[fid,ib]);edge=tuple(sorted((a,b)))
        if edge not in edge_cache:
            ea,eb=edge;pa=positions[ea].astype(float);pb=positions[eb].astype(float)
            t=(plane-pa[1])/(pb[1]-pa[1])
            contract.require(0<t<1,'A split edge must strictly cross the plane')
            for semantic,values in attributes.items():
                value=(1-t)*values[ea].astype(float)+t*values[eb].astype(float)
                if semantic=='POSITION':
                    # Identical coordinates with distinct seam rows use the same
                    # canonical endpoint direction and arithmetic.
                    ca,cb=sorted((tuple(pa),tuple(pb)));ca=np.asarray(ca);cb=np.asarray(cb)
                    ct=(plane-ca[1])/(cb[1]-ca[1]);value=ca+ct*(cb-ca);value[1]=plane
                if semantic=='TANGENT':
                    contract.require(values[ea,3]==values[eb,3] and abs(values[ea,3])==1,
                                     'Split edge crosses ambiguous tangent handedness')
                    value[3]=values[ea,3]
                rows[semantic].append(value.astype('<f4'))
            edge_cache[edge]=len(rows['POSITION'])-1
            edge_lineage[edge_cache[edge]]=(ea,eb,t)
        # Deliberately use double scalar source coordinates: float32 subtraction
        # would lose source-face barycentric reproducibility.
        t=(plane-float(positions[a,1]))/(float(positions[b,1])-float(positions[a,1]))
        w=np.zeros(3);w[ia]=1-t;w[ib]=t
        return edge_cache[edge],w

    def polygon(fid,keep_upper):
        poly=[]
        for i in range(3):
            j=(i+1)%3;zi=float(positions[faces[fid,i],1]);zj=float(positions[faces[fid,j],1])
            inside_i=zi>=plane if keep_upper else zi<=plane
            inside_j=zj>=plane if keep_upper else zj<=plane
            if inside_i:poly.append((int(faces[fid,i]),np.eye(3)[i]))
            if inside_i!=inside_j and zi!=plane and zj!=plane:
                poly.append(intersection(fid,i,j))
        # Remove duplicate on-plane endpoints, preserving orientation.
        compact=[]
        for row in poly:
            if not compact or row[0]!=compact[-1][0]:compact.append(row)
        if len(compact)>1 and compact[-1][0]==compact[0][0]:compact.pop()
        for i in range(1,len(compact)-1):
            tri=[compact[0],compact[i],compact[i+1]]
            result.append([x[0] for x in tri]);weights.append([x[1] for x in tri])
            parents.append(fid);upper.append(keep_upper)

    for fid,face in enumerate(faces):
        z=positions[face,1].astype(float)
        if z.min()<plane<z.max():
            crossing.append(fid);polygon(fid,True);polygon(fid,False)
        else:
            result.append(face.tolist());parents.append(fid);weights.append(np.eye(3))
            upper.append(bool(z.min()>=plane))
    result=np.asarray(result,np.int64);parents=np.asarray(parents,np.int64)
    weights=np.asarray(weights,float);upper=np.asarray(upper,bool)
    result_attributes={k:np.asarray(v,dtype='<f4') for k,v in rows.items()}
    contract.require(np.all(result_attributes['POSITION'][result[upper],1]>=plane) and
                     np.all(result_attributes['POSITION'][result[~upper],1]<=plane),
                     'A split child triangle crosses the protection plane')
    return {'attributes':result_attributes,'faces':result,'parentFaceIds':parents,
            'barycentric':weights,'upperFaceMask':upper,
            'crossingParentFaceIds':np.asarray(crossing,np.int64),
            'originalRowCount':original_count,'splitRowEdgeLineage':edge_lineage,'plane':plane}


def face_diagnostics(before,after,before_normals,after_normals):
    old=np.cross(before[:,1]-before[:,0],before[:,2]-before[:,0])
    new=np.cross(after[:,1]-after[:,0],after[:,2]-after[:,0])
    old_length=np.linalg.norm(old,axis=1);new_length=np.linalg.norm(new,axis=1)
    contract.require(np.all(old_length>1e-15) and np.all(new_length>1e-15),'Connector zero-area triangle')
    dot=np.sum(old*new,axis=1)/(old_length*new_length)
    old_sign=np.sum(old*before_normals.mean(1),axis=1)
    new_sign=np.sum(new*after_normals.mean(1),axis=1)
    return dot,np.flatnonzero((old_sign>=0)&(new_sign<0))


def execute(config_path,output):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text())
    allowed={'schemaVersion','kind','diagnosticOnly','parentReceipt','parentReceiptSha256','targetContract',
             'targetContractSha256','protectedInputs','notes','planeLocalZMetres','fullScaleLocalZMetres',
             'centreLocalXYMetres','minimumXYScale','maximumDisplacementMetres','ownershipInspection'}
    contract.require(set(config)<=allowed and config['schemaVersion']==2 and
                     config['kind']=='target-face-aware-lower-connector-trial' and config['diagnosticOnly'] is True,
                     'Explicit diagnostic connector configuration required')
    parent_path=Path(config['parentReceipt']).resolve();parent=json.loads(parent_path.read_text())
    target_path=Path(config['targetContract']).resolve();target=contract.load(target_path)
    contract.verify_binding(parent,target_path,target,'working')
    contract.require(parent['kind']=='target-part-geometry' and parent['part']=='chest' and
                     parent['joint']=='torso_g' and parent['statureApplications']==0 and
                     parent['operation']=='bounded-inward-waist-field','One original waist working parent required')
    source=Path(parent['candidate']).resolve();archive_path=Path(parent['nativeCornerArchive']['path'])
    pins={str(parent_path):config['parentReceiptSha256'],str(source):parent['candidateSha256'],
          str(archive_path):parent['nativeCornerArchive']['sha256'],str(target_path):config['targetContractSha256'],
          **config['protectedInputs'],**parent['frozenInputs'],str(config_path):contract.sha(config_path)}
    helpers=('repair_target_chest_connector.py','deform_target_terminal_envelope.py',
             'conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py')
    for name in helpers:
        path=Path(__file__).with_name(name).resolve();pins[str(path)]=contract.sha(path)
    for name,pin in pins.items():contract.require(contract.sha(name)==pin,'Connector frozen input changed: '+name)
    document,binary=read_glb(source)
    contract.require(len(document['nodes'])==1 and document['nodes'][0].get('mesh')==0 and
                     np.array_equal(node_matrix(document['nodes'][0]),np.eye(4)) and
                     len(document['meshes'])==1 and len(document['meshes'][0]['primitives'])==1,
                     'One identity-node chest mesh required')
    primitive=document['meshes'][0]['primitives'][0]
    attrs={k:accessor(document,binary,v) for k,v in primitive['attributes'].items()}
    faces=accessor(document,binary,primitive['indices']).reshape(-1,3).astype(np.int64)
    split=split_at_plane(attrs,faces,config['planeLocalZMetres'])
    plane=split['plane'];full=config['fullScaleLocalZMetres'];centre=config['centreLocalXYMetres'];scales=config['minimumXYScale']
    contract.require(abs(plane-config['planeLocalZMetres'])<1e-9 and plane<=-.015+1e-9,
                     'Measured below-minus15mm protection plane required')
    original_topology=topology(attrs['POSITION'],faces)
    before=topology(split['attributes']['POSITION'],split['faces'])
    keys=('boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings',
          'nonmanifoldVertexLinks','zeroAreaFaces','components','eulerCharacteristic')
    contract.require(all(original_topology[k]==before[k] for k in keys),'Plane subdivision changed topology')
    lower_topology=topology(split['attributes']['POSITION'],split['faces'][~split['upperFaceMask']])
    contract.require(lower_topology['components']==1 and lower_topology['eulerCharacteristic']==1 and
                     lower_topology['nonmanifoldEdges']==lower_topology['nonmanifoldVertexLinks']==0 and
                     lower_topology['boundaryEdges']>0 and len(lower_topology['boundaryLoops'])==1 and
                     lower_topology['boundaryLoops'][0]['closedDegreeTwoRing'],
                     'Measured split lower connector must be one clean manifold disk')
    raw=split['attributes'];local=raw['POSITION'].astype(float)@BASIS.T
    proposed,jac=connector_field(local,plane,full,centre,scales)
    referenced=np.zeros(len(local),bool);referenced[np.unique(split['faces'])]=True
    edited=referenced & np.any(proposed!=local,axis=1);proposed[~referenced]=local[~referenced];jac[~referenced]=np.eye(3)
    limit=config['maximumDisplacementMetres']
    contract.require(0<limit<=.08 and np.max(np.linalg.norm(proposed-local,axis=1))<=limit,
                     'Measured connector displacement exceeds bounded limit')
    normals=raw['NORMAL'].astype(float)@BASIS.T;tangent=None
    if 'TANGENT' in raw:
        tangent=raw['TANGENT'].astype(float);tangent[:,:3]=tangent[:,:3]@BASIS.T
    nn,tt=transport(normals,tangent,jac,edited)
    changed={k:v.copy() for k,v in raw.items()}
    changed['POSITION'][edited]=(proposed[edited]@BASIS).astype('<f4')
    changed['NORMAL'][edited]=(nn[edited]@BASIS).astype('<f4')
    if tt is not None:
        rt=tt.copy();rt[:,:3]=rt[:,:3]@BASIS;changed['TANGENT'][edited]=rt[edited].astype('<f4')
    fs=split['faces'];old_tri=local[fs];new_tri=(changed['POSITION'].astype(float)@BASIS.T)[fs]
    old_ns=normals[fs];new_ns=(changed['NORMAL'].astype(float)@BASIS.T)[fs]
    winding,new_opposed=face_diagnostics(old_tri,new_tri,old_ns,new_ns)
    contract.require(np.all(winding>0),'Connector trial flips discrete triangle winding')
    contract.require(not len(new_opposed),'Connector trial introduces authored mean-normal opposition')
    upper=split['upperFaceMask']
    for k in raw:
        contract.require(raw[k][fs[upper]].tobytes()==changed[k][fs[upper]].tobytes(),
                         'Protected actual upper surface attribute changed: '+k)
    after=topology(changed['POSITION'],fs)
    contract.require(all(before[k]==after[k] for k in keys),'Connector deformation changed topology')
    result=copy.deepcopy(document);payload=bytearray(binary)
    def append(values,indices=False):
        payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(values.tobytes());payload.extend(b'\0'*(-len(payload)%4))
        result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':values.nbytes,'target':34963 if indices else 34962})
        info={'bufferView':len(result['bufferViews'])-1,'componentType':5125 if indices else 5126,
              'count':values.size if indices else len(values),'type':'SCALAR' if indices else 'VEC'+str(values.shape[1])}
        if not indices and values.shape[1]==3:info.update(min=values.min(0).tolist(),max=values.max(0).tolist())
        result['accessors'].append(info);return len(result['accessors'])-1
    for k,v in changed.items():result['meshes'][0]['primitives'][0]['attributes'][k]=append(v)
    result['meshes'][0]['primitives'][0]['indices']=append(fs.astype('<u4').reshape(-1),True)
    result['buffers'][0]['byteLength']=len(payload)
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable connector trial required')
    candidate=output/'candidate-local.glb'
    actual,actual_bin=result,bytes(payload);q=actual['meshes'][0]['primitives'][0]
    contract.require(actual_bin[:len(binary)]==binary and actual['materials']==document['materials'] and
                     embedded_maps(actual,actual_bin)==embedded_maps(document,binary),'Original BIN/material/maps changed')
    for k,v in changed.items():
        contract.require(accessor(actual,actual_bin,q['attributes'][k]).tobytes()==v.tobytes(),'Serialized attributes changed')
        protection=(local[:len(attrs['POSITION']),2]>=plane) | ~referenced[:len(attrs['POSITION'])]
        contract.require(v[:len(attrs['POSITION'])][protection].tobytes()==attrs[k][protection].tobytes(),
                         'Protected original raw row changed')
    # Source native double-precision face corners are clipped independently using
    # the same topology classification; actual native intersection weights differ
    # from float32 preview weights and are separately recorded.
    base=np.load(archive_path,allow_pickle=False);cp=base['positions'];cn=base['normals']
    parent_ids=split['parentFaceIds'];bary=split['barycentric'].copy();native_bary=bary.copy()
    for cid,pid in enumerate(parent_ids):
        for corner,w in enumerate(bary[cid]):
            nz=np.flatnonzero(w)
            if len(nz)==2:
                ia,ib=nz;za=cp[pid,ia,2];zb=cp[pid,ib,2]
                t=(plane-za)/(zb-za);contract.require(0<t<1,'Native edge no longer crosses measured plane')
                native_bary[cid,corner]=0;native_bary[cid,corner,ia]=1-t;native_bary[cid,corner,ib]=t
    def interpolate(name):
        return np.einsum('fci,fij->fcj',native_bary,base[name][parent_ids])
    native_p=interpolate('positions');native_n=interpolate('normals')
    native_uv=interpolate('uvGltf');native_uv_original=interpolate('uvNative')
    native_t=interpolate('tangents') if 'tangents' in base.files else None
    # Clamp split-corner Z to the actual plane to avoid an epsilon field on upper children.
    split_corner=np.count_nonzero(native_bary,axis=2)==2
    native_p[:,:,2][split_corner]=plane
    flat=native_p.reshape(-1,3);np_,nj=connector_field(flat,plane,full,centre,scales);ne=np.any(np_!=flat,axis=1)
    nt=native_t.reshape(-1,4) if native_t is not None else None
    native_nn,native_tt=transport(native_n.reshape(-1,3),nt,nj,ne)
    arrays={'positions':np_.reshape(native_p.shape),'normals':native_nn.reshape(native_n.shape),
            'uvGltf':native_uv,'uvNative':native_uv_original,'sourceFaceIds':parent_ids,
            'connectorParentFaceIds':parent_ids,'connectorBarycentricPreview':bary,
            'connectorBarycentricNative':native_bary,'connectorUpperFaceMask':upper,
            'connectorCrossingParentFaceIds':split['crossingParentFaceIds'],
            'connectorParentFaces':faces,'connectorSplitFaces':fs,'connectorParentRawPositions':attrs['POSITION'],
            'connectorEditedVertexMask':edited,'connectorJacobianLocal':jac}
    for name in ('sourceTriangleIds','primitiveIds'):
        if name in base.files:arrays[name]=base[name][parent_ids]
    if native_tt is not None:
        arrays['tangents']=native_tt.reshape(native_t.shape);arrays['tangentTriangleIds']=np.arange(len(fs))
    for name in ('sourcePositions','sourceNormals','sourceUVNative'):
        if name in base.files:arrays[name]=np.einsum('fci,fij->fcj',native_bary,base[name][parent_ids])
    # Upper clipped native positions and attributes are exactly the interpolation
    # of the parent surface, with all uncut source corners copied exactly.
    contract.require(np.array_equal(arrays['positions'][upper],native_p[upper]) and
                     np.array_equal(arrays['normals'][upper],native_n[upper]),'Upper native surface changed')
    p,n,uv,_=raw_corners(actual,actual_bin)
    contract.require(np.max(abs(p-arrays['positions']))<1e-7 and np.max(abs(n-arrays['normals']))<2e-6 and
                     np.max(abs(uv-arrays['uvGltf']))<2e-7,'Serialized connector differs from authoritative interpolation')
    output.mkdir(parents=True);write_glb(candidate,result,bytes(payload))
    archive=output/'native-corners.npz';np.savez_compressed(archive,**arrays)
    ancestry=output/'split-lineage.json';ancestry.write_text(json.dumps({
        'originalRowCount':split['originalRowCount'],'splitRows':{
            str(k):{'sourceRawEdge':list(v[:2]),'bWeight':v[2]} for k,v in split['splitRowEdgeLineage'].items()},
        'nativeCornerArchive':str(archive),'previewNativeBarycentricDifferenceExplicit':True,
        'rule':'Each child face pins its parent face and three parent-corner weights. New UV/normal/tangent rows interpolate their raw edge without seam welding. Tangent W is copied only when both edge endpoints agree.'},indent=2)+'\n')
    shutil.copy2(config_path,output/'config.json');(output/'tools').mkdir();snapshots={}
    for name in helpers:
        helper=Path(__file__).with_name(name).resolve();snapshot=output/'tools'/name;shutil.copy2(helper,snapshot)
        snapshots[str(helper)]={'snapshot':str(snapshot),'sha256':contract.sha(snapshot)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'face-aware-lower-connector-plane-split',
             **contract.binding(target_path,target,'working'),'part':'chest','joint':'torso_g','model':contract.model(target,'chest'),
             'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),
             'sourceReceiptSha256':contract.sha(parent_path),'candidate':str(candidate),'candidateSha256':contract.sha(candidate),
             'nativeCornerArchive':{'path':str(archive),'sha256':contract.sha(archive)},
             'statureApplications':0,'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),
             'connectorConfiguration':config,'splitLineage':{'path':str(ancestry),'sha256':contract.sha(ancestry)},
             'frozenInputs':pins,'helperSnapshots':snapshots,'diagnosticOnly':True,
             'clientAccepted':False,'productionAccepted':False,
             'proof':{'protectionPlaneLocalZMetres':plane,'originalRows':len(attrs['POSITION']),'newSplitRows':len(local)-len(attrs['POSITION']),
                      'crossingParentTriangles':len(split['crossingParentFaceIds']),'sourceFaces':len(faces),'childFaces':len(fs),
                      'changedReferencedRows':int(edited.sum()),'upperProtectedChildFaces':int(upper.sum()),
                      'actualMaximumDisplacementMetres':float(np.linalg.norm(proposed-local,axis=1).max()),
                      'continuousDeterminantLowerBound':float(np.prod(scales)),
                      'minimumDiscreteFaceNormalDot':float(winding.min()),'newAuthoredMeanNormalOppositionChildFaceIds':new_opposed.tolist(),
                      'exactUpperOriginalRawRows':True,'exactUpperClippedSurface':True,'originalBinPrefixAndImageBytesExact':True,
                      'noSourceFaceDeleted':True,'noInnerSheetOperation':True,'sourceLowerDiskTopology':lower_topology,
                      'sourceTopology':original_topology,'subdividedTopology':before,'deformedTopology':after},
             'limitations':['One diagnostic lower cap trial, not acceptance. Only the measured clean disk below minus15mm is reshaped.',
                            'Plane intersections add explicit interpolated corners; UV/normal/tangent ancestry is retained separately from original rows.',
                            'Original inner sheet, collar, deltoid ownership and garment tracks remain unresolved. Neighbor radial contours and three poses cannot establish exhaustive hidden coverage.',
                            'No runtime conversion, native compile, client validation or selection.']}
    for name,pin in pins.items():contract.require(contract.sha(name)==pin,'Connector input changed during execution: '+name)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
    return path,receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();path,receipt=execute(args.config,args.output)
    print(json.dumps({'receipt':str(path),'sha256':contract.sha(path),'candidateSha256':receipt['candidateSha256'],
                      'maximumDisplacementMetres':receipt['proof']['actualMaximumDisplacementMetres'],
                      'newMeanNormalOppositionFaces':receipt['proof']['newAuthoredMeanNormalOppositionChildFaceIds']}))

