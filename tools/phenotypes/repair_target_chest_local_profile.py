"""One diagnostic chest lower stock-profile transition, with source-face subdivision.

All original source sheets are retained. Local Z and every complete upper clipped
surface stay fixed; source maps/UVs remain archived and unchanged. New corners
record one shared authoritative-double source-face/barycentric ancestry.
"""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as contract
from conservative_face_selection import topology
from deform_target_terminal_envelope import transport
from repair_target_chest_connector import split_at_plane,face_diagnostics
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,node_matrix,raw_corners,read_glb,write_glb

def profile_field(points,controls,translation_ramp=None):
    """Positive per-Z affine map, C1 at each measured control, identity above last."""
    p=np.asarray(points,float)
    contract.require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'Finite attachment-local points required')
    contract.require(isinstance(controls,list) and len(controls)>=3,'Explicit measured stock-profile controls required')
    z=np.array([c['localZMetres'] for c in controls],float)
    scales=np.array([c['xyScale'] for c in controls],float);d=np.array([c['xyTranslationMetres'] for c in controls],float)
    contract.require(np.isfinite(z).all() and np.all(np.diff(z)>0) and scales.shape==(len(z),2) and
                     d.shape==scales.shape and np.isfinite(scales).all() and np.isfinite(d).all() and
                     np.all(scales>0) and np.all(scales<=1) and np.min(scales.prod(1))>=.25 and
                     np.array_equal(scales[-1],[1,1]) and np.array_equal(d[-1],[0,0]),
                     'Ordered positive stock-profile controls ending at identity required')
    actual_scale=np.tile(scales[0],(len(p),1));actual_d=np.tile(d[0],(len(p),1))
    derivative_s=np.zeros((len(p),2));derivative_d=np.zeros((len(p),2))
    for k in range(len(z)-1):
        mask=(p[:,2]>=z[k])&(p[:,2]<z[k+1]);t=(p[mask,2]-z[k])/(z[k+1]-z[k]);h=t*t*(3-2*t);dh=6*t*(1-t)/(z[k+1]-z[k])
        actual_scale[mask]=scales[k]+h[:,None]*(scales[k+1]-scales[k]);actual_d[mask]=d[k]+h[:,None]*(d[k+1]-d[k])
        derivative_s[mask]=dh[:,None]*(scales[k+1]-scales[k]);derivative_d[mask]=dh[:,None]*(d[k+1]-d[k])
    if translation_ramp is not None:
        rz=np.asarray(translation_ramp['localZMetres'],float);rd=np.asarray(translation_ramp['xyTranslationMetres'],float)
        contract.require(rz.shape==(2,) and rd.shape==(2,2) and np.isfinite(rd).all() and
                         np.array_equal(rz,z[[0,-1]]) and np.array_equal(rd[0],d[0]) and np.array_equal(rd[-1],[0,0]),
                         'Explicit one monotonic C1 terminal-to-identity translation ramp required')
        t=np.clip((p[:,2]-rz[0])/(rz[1]-rz[0]),0,1);h=t*t*(3-2*t);dh=6*t*(1-t)/(rz[1]-rz[0])
        actual_d=rd[0]+h[:,None]*(rd[1]-rd[0]);derivative_d=dh[:,None]*(rd[1]-rd[0])
    out=p.copy();out[:,:2]=p[:,:2]*actual_scale+actual_d
    jac=np.tile(np.eye(3),(len(p),1,1));jac[:,0,0]=actual_scale[:,0];jac[:,1,1]=actual_scale[:,1]
    jac[:,:2,2]=p[:,:2]*derivative_s+derivative_d
    protected=p[:,2]>=z[-1];out[protected]=p[protected];jac[protected]=np.eye(3)
    return out,jac

def split_at_authoritative_plane(attributes,faces,plane,authoritative_positions):
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
    source_positions=attributes['POSITION'];positions=np.asarray(authoritative_positions,float)
    contract.require(positions.shape==source_positions.shape and np.isfinite(positions).all(),'Authoritative double indexed positions required')
    contract.require(all(v.dtype==np.dtype('<f4') and len(v)==len(source_positions) and np.isfinite(v).all()
                         for v in attributes.values()),'Finite float32 source attribute rows required')
    faces=np.asarray(faces,dtype=np.int64);plane=float(np.float32(plane))
    contract.require(faces.ndim==2 and faces.shape[1]==3 and faces.min()>=0 and
                     faces.max()<len(positions),'Indexed triangles required')
    rows={k:list(v.copy()) for k,v in attributes.items()};native_rows=list(positions.copy());edge_cache={};edge_lineage={}
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
                    # Preserve the original encoded parent field on the SAME authoritative cut edge.
                    if tuple(pa)>tuple(pb):ca,cb=eb,ea
                    else:ca,cb=ea,eb
                    ct=(plane-positions[ca,1])/(positions[cb,1]-positions[ca,1])
                    va=source_positions[ca].astype(float);vb=source_positions[cb].astype(float)
                    value=va+ct*(vb-va)
                if semantic=='TANGENT':
                    contract.require(values[ea,3]==values[eb,3] and abs(values[ea,3])==1,
                                     'Split edge crosses ambiguous tangent handedness')
                    value[3]=values[ea,3]
                rows[semantic].append(value.astype('<f4'))
            ca,cb=sorted((tuple(pa),tuple(pb)));ca=np.asarray(ca);cb=np.asarray(cb)
            ct=(plane-ca[1])/(cb[1]-ca[1]);new_position=ca+ct*(cb-ca);new_position[1]=plane;native_rows.append(new_position)
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
    contract.require(np.all(np.asarray(native_rows)[result[upper],1]>=plane) and
                     np.all(np.asarray(native_rows)[result[~upper],1]<=plane),
                     'A split child triangle crosses the protection plane')
    return {'attributes':result_attributes,'authoritativePositions':np.asarray(native_rows),'faces':result,'parentFaceIds':parents,
            'barycentric':weights,'upperFaceMask':upper,
            'crossingParentFaceIds':np.asarray(crossing,np.int64),
            'originalRowCount':original_count,'splitRowEdgeLineage':edge_lineage,'plane':plane}


def subdivide(attributes,faces,planes,native=None):
    """One authoritative-double cut partition drives BOTH original source representations."""
    contract.require(isinstance(planes,list) and len(planes)>=2 and all(np.isfinite(planes)) and
                     all(a<b for a,b in zip(planes,planes[1:])),'Ordered finite signed subdivision planes required')
    original_faces=np.asarray(faces,np.int64);a=attributes;f=original_faces.copy();parents=np.arange(len(f))
    weights=np.tile(np.eye(3),(len(f),1,1));values=None if native is None else {k:np.asarray(v).copy() for k,v in native.items()}
    ap=attributes['POSITION'].astype(float).copy()
    if values is not None:
        corner_positions=values['positions']@BASIS
        ap[f.reshape(-1)]=corner_positions.reshape(-1,3)
        contract.require(np.max(abs(ap[f]-corner_positions))<2e-15,'Native source has inconsistent shared indexed corner positions')
    steps=[]
    for value in planes:
        sp=split_at_authoritative_plane(a,f,value,ap);ids=sp['parentFaceIds'];w=sp['barycentric']
        if values is not None:
            values={k:np.einsum('fci,fij->fcj',w,v[ids]) for k,v in values.items()}
            cut=np.count_nonzero(w,axis=2)==2;values['positions'][:,:,2][cut]=sp['plane']
        weights=np.einsum('fci,fij->fcj',w,weights[ids])
        steps.append({'planeLocalZMetres':sp['plane'],'sourceStepFaces':len(f),'childFaces':len(sp['faces']),
                      'crossingStepFaceIds':sp['crossingParentFaceIds'].tolist(),
                      'splitRawRows':{str(k):{'sourceRawEdge':list(v[:2]),'bWeight':v[2]} for k,v in sp['splitRowEdgeLineage'].items()}})
        parents=parents[ids];a=sp['attributes'];f=sp['faces'];ap=sp['authoritativePositions']
    plane=float(np.float32(planes[-1]));upper=ap[f,1].min(1)>=plane
    contract.require(np.all(upper|(ap[f,1].max(1)<=plane)),'Authoritative child crosses upper protection plane')
    return {'attributes':a,'faces':f,'authoritativeRawPositions':ap,'parentFaceIds':parents,
            'barycentric':weights,'nativeBarycentric':weights.copy(),'nativeValues':values,'upperFaceMask':upper,
            'plane':plane,'steps':steps,'originalRowCount':len(attributes['POSITION'])}

def differential_orientation(before,after,controls,translation_ramp=None):
    a=np.asarray(before,float);b=np.asarray(after,float)
    old=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);new=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
    jac=profile_field(a.mean(1),controls,translation_ramp)[1]
    expected=np.linalg.solve(jac.transpose(0,2,1),old[...,None])[...,0]
    return np.sum(expected*new,axis=1)/(np.linalg.norm(expected,axis=1)*np.linalg.norm(new,axis=1))

def execute(config_path,output):
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text())
    allowed={'schemaVersion','kind','diagnosticOnly','parentReceipt','parentReceiptSha256','targetContract',
             'targetContractSha256','protectedInputs','notes','protectionPlaneLocalZMetres','controls',
             'braProtectionReceipt','braProtectionReceiptSha256','maximumDisplacementMetres','subdivisionPlanesLocalZMetres',
             'lowerSkinParentFaceIds','ownershipInspection','maximumFaces','translationRamp','maximumJacobianConditionNumber'}
    contract.require(set(cfg)<=allowed and cfg['schemaVersion']==2 and
                     cfg['kind']=='target-chest-local-stock-profile-trial' and cfg['diagnosticOnly'] is True,
                     'Explicit chest stock-profile diagnostic configuration required')
    parentpath=Path(cfg['parentReceipt']).resolve();parent=json.loads(parentpath.read_text())
    targetpath=Path(cfg['targetContract']).resolve();target=contract.load(targetpath)
    contract.verify_binding(parent,targetpath,target,'working')
    contract.require(parent['kind']=='target-part-geometry' and parent['part']=='chest' and parent['joint']=='torso_g'
                     and parent['statureApplications']==0 and parent['operation']=='bounded-inward-waist-field',
                     'One original waist-taper working chest parent required; repeated conversion/connector rejected')
    source=Path(parent['candidate']).resolve();archivepath=Path(parent['nativeCornerArchive']['path']).resolve()
    pins={str(parentpath):cfg['parentReceiptSha256'],str(source):parent['candidateSha256'],
          str(archivepath):parent['nativeCornerArchive']['sha256'],str(targetpath):cfg['targetContractSha256'],
          **cfg['protectedInputs'],**parent['frozenInputs'],str(config_path):contract.sha(config_path)}
    helpers=('repair_target_chest_local_profile.py','repair_target_chest_connector.py','deform_target_terminal_envelope.py',
             'conservative_face_selection.py','place_purposebuilt_pelvis.py','target_contract.py')
    for name in helpers:
        p=Path(__file__).with_name(name).resolve();pins[str(p)]=contract.sha(p)
    for p,h in pins.items():contract.require(contract.sha(p)==h,'Frozen chest connector input changed: '+p)
    document,binary=read_glb(source)
    contract.require(len(document['nodes'])==1 and document['nodes'][0].get('mesh')==0 and
                     np.array_equal(node_matrix(document['nodes'][0]),np.eye(4)) and len(document['meshes'])==1 and
                     len(document['meshes'][0]['primitives'])==1,'One identity-node chest primitive required')
    primitive=document['meshes'][0]['primitives'][0]
    attrs={k:accessor(document,binary,v) for k,v in primitive['attributes'].items()}
    faces=accessor(document,binary,primitive['indices']).reshape(-1,3).astype(np.int64)
    base=np.load(archivepath,allow_pickle=False)
    names=['positions','normals','uvGltf','uvNative']+(['tangents'] if 'tangents' in base.files else [])
    names+=[n for n in ('sourcePositions','sourceNormals','sourceUVNative') if n in base.files]
    planes=cfg['subdivisionPlanesLocalZMetres'];plane=float(np.float32(cfg['protectionPlaneLocalZMetres']));controls=cfg['controls'];ramp=cfg['translationRamp']
    contract.require(planes[-1]==cfg['protectionPlaneLocalZMetres'] and controls[-1]['localZMetres']==plane and
                     all(b-a<=.005000001 for a,b in zip(planes,planes[1:])) and
                     -.04000001<=planes[0]<0<plane<=.010000001,
                     'Frozen measured stock-profile band and at most 5mm source-face subdivision required')
    lowerparents=np.flatnonzero(attrs['POSITION'][faces,1].min(1)<plane)
    contract.require(cfg['lowerSkinParentFaceIds']==lowerparents.tolist(),'Explicit reviewed lower skin source-face set mismatch')
    protection_path=Path(cfg['braProtectionReceipt']).resolve();protection=json.loads(protection_path.read_text())
    contract.require(contract.sha(protection_path)==cfg['braProtectionReceiptSha256'], 'Frozen bra protection receipt changed')
    pins[str(protection_path)]=cfg['braProtectionReceiptSha256']
    pins.update(protection['frozenInputs']);pins[protection['arrays']['path']]=protection['arrays']['sha256']
    for name,h in pins.items():contract.require(contract.sha(name)==h,'Frozen bra closure input changed: '+name)
    bra=np.load(protection['arrays']['path'])['explicitOriginalBraAndFourTrackFaceMask']
    contract.require(len(bra)==len(faces) and attrs['POSITION'][faces[bra],1].min()>plane,
                     'Actual whole explicit bra/four-track surfaces intersect repair support')
    split=subdivide(attrs,faces,planes,{k:base[k] for k in names})
    raw=split['attributes'];fs=split['faces'];parents=split['parentFaceIds'];upper=split['upperFaceMask']
    contract.require(len(fs)<=cfg['maximumFaces']<=75000,'Diagnostic subdivision face budget exceeded')
    original=topology(attrs['POSITION'],faces);before=topology(raw['POSITION'],fs)
    keys=('nonmanifoldEdges','inconsistentManifoldEdgeWindings','nonmanifoldVertexLinks',
          'zeroAreaFaces','components','eulerCharacteristic')
    contract.require(all(original[k]==before[k] for k in keys),'Source subdivision changed topology')
    band_topology=topology(raw['POSITION'],fs[~upper])
    local=split['authoritativeRawPositions']@BASIS.T;source_encoded_local=raw['POSITION'].astype(float)@BASIS.T;proposed,jac=profile_field(local,controls,ramp)
    ref=np.zeros(len(local),bool);ref[np.unique(fs)]=True;proposed[~ref]=local[~ref];jac[~ref]=np.eye(3)
    condition=float(np.linalg.cond(jac[ref]).max())
    contract.require(1<cfg['maximumJacobianConditionNumber']<=20 and condition<=cfg['maximumJacobianConditionNumber'],
                     'Measured Jacobian conditioning guard exceeded')
    edited=ref&np.any(proposed!=local,axis=1);maximum=float(np.linalg.norm(proposed-local,axis=1).max())
    contract.require(0<cfg['maximumDisplacementMetres']<=.065 and maximum<=cfg['maximumDisplacementMetres'],
                     'Measured lower-skin profile displacement limit exceeded')
    changedparents=np.unique(parents[np.any(edited[fs],axis=1)])
    contract.require(np.isin(changedparents,lowerparents).all(),'Protected bra/upper source face changed')
    normals=raw['NORMAL'].astype(float)@BASIS.T;tangent=raw.get('TANGENT')
    if tangent is not None:tangent=tangent.astype(float);tangent[:,:3]=tangent[:,:3]@BASIS.T
    nn,tt=transport(normals,tangent,jac,edited);changed={k:v.copy() for k,v in raw.items()}
    changed['POSITION'][edited]=(proposed[edited]@BASIS).astype('<f4');changed['NORMAL'][edited]=(nn[edited]@BASIS).astype('<f4')
    if tt is not None:
        rt=tt.copy();rt[:,:3]=rt[:,:3]@BASIS;changed['TANGENT'][edited]=rt[edited].astype('<f4')
    winding,opposed=face_diagnostics(source_encoded_local[fs],(changed['POSITION'].astype(float)@BASIS.T)[fs],
                                   normals[fs],(changed['NORMAL'].astype(float)@BASIS.T)[fs])
    mapped_orientation=differential_orientation(local[fs],(changed['POSITION'].astype(float)@BASIS.T)[fs],controls,ramp)
    contract.require(np.all(mapped_orientation>0) and not len(opposed),'New serialized mapped chord reversal or authored mean-normal opposition')
    for k in raw:contract.require(raw[k][fs[upper]].tobytes()==changed[k][fs[upper]].tobytes(),
                                 'Actual whole upper clipped surface changed: '+k)
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
    result['meshes'][0]['primitives'][0]['indices']=append(fs.astype('<u4').reshape(-1),True);result['buffers'][0]['byteLength']=len(payload)
    contract.require(bytes(payload[:len(binary)])==binary and result['materials']==document['materials'] and
                     embedded_maps(result,bytes(payload))==embedded_maps(document,binary),'Original source BIN/material/image changed')
    for k,v in changed.items():
        protection=(local[:len(attrs['POSITION']),2]>=plane)|~ref[:len(attrs['POSITION'])]
        contract.require(v[:len(attrs['POSITION'])][protection].tobytes()==attrs[k][protection].tobytes(),
                         'Protected original attribute row changed')
    nv=split['nativeValues'];p=nv['positions'];n=nv['normals'];nt=nv.get('tangents')
    np_,nj=profile_field(p.reshape(-1,3),controls,ramp)
    ne=np.any(np_!=p.reshape(-1,3),axis=1);native_n,native_t=transport(n.reshape(-1,3),None if nt is None else nt.reshape(-1,4),nj,ne)
    arrays={**nv,'positions':np_.reshape(p.shape),'normals':native_n.reshape(n.shape),
            'sourceFaceIds':parents,'connectorParentFaceIds':parents,'connectorBarycentricPreview':split['barycentric'],
            'connectorBarycentricNative':split['nativeBarycentric'],'connectorUpperFaceMask':upper,
            'connectorParentFaces':faces,'connectorSplitFaces':fs,'connectorParentRawPositions':attrs['POSITION'],
            'connectorEditedVertexMask':edited,'connectorJacobianLocal':jac,'connectorAuthoritativeRawPositions':split['authoritativeRawPositions']} 
    if native_t is not None:arrays['tangents']=native_t.reshape(nt.shape);arrays['tangentTriangleIds']=np.arange(len(fs))
    for name in ('sourceTriangleIds','primitiveIds'):
        if name in base.files:arrays[name]=base[name][parents]
    for k in ('positions','normals','uvGltf','uvNative','tangents'):
        if k in arrays:contract.require(np.array_equal(arrays[k][upper],nv[k][upper]),'Authoritative whole upper surface changed: '+k)
    ep,en,eu,_=raw_corners(result,bytes(payload))
    contract.require(np.max(abs(ep-arrays['positions']))<1e-7 and np.max(abs(en-arrays['normals']))<2e-6 and
                     np.max(abs(eu-arrays['uvGltf']))<2e-7,'Serialized preview differs from authoritative native lineage')
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable chest stock-profile trial required')
    output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,result,bytes(payload))
    # Re-open exact disk serialization before completing its receipt.
    rd,rb=read_glb(candidate);rq=rd['meshes'][0]['primitives'][0]
    for k,v in changed.items():contract.require(accessor(rd,rb,rq['attributes'][k]).tobytes()==v.tobytes(),'Reopened serialized attributes differ')
    archive=output/'native-corners.npz';np.savez_compressed(archive,**arrays)
    lineage=output/'split-lineage.json';lineage.write_text(json.dumps({'steps':split['steps'],'originalRowCount':len(attrs['POSITION']),
       'rule':'Conforming horizontal source-face subdivisions preserve each original planar surface. New UV/authored normal/tangent rows interpolate their own raw edges without seam welding. Each final child pins original face IDs and preview/native barycentric lineage; W copied only for agreeing edge endpoints.',
       'oneAuthoritativeDoubleBarycentricPartition':True,'originalProtectedParentRepresentationsPreserved':True},indent=2)+'\n')
    shutil.copy2(config_path,output/'config.json');(output/'tools').mkdir();snapshots={}
    for name in helpers:
        p=Path(__file__).with_name(name).resolve();s=output/'tools'/name;shutil.copy2(p,s);snapshots[str(p)]={'snapshot':str(s),'sha256':contract.sha(s)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'chest-local-stock-profile-plane-subdivision',
      **contract.binding(targetpath,target,'working'),'part':'chest','joint':'torso_g','model':contract.model(target,'chest'),
      'source':str(source),'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parentpath),'sourceReceiptSha256':contract.sha(parentpath),
      'candidate':str(candidate),'candidateSha256':contract.sha(candidate),'nativeCornerArchive':{'path':str(archive),'sha256':contract.sha(archive)},
      'statureApplications':0,'attachmentWorld':parent['attachmentWorld'],'sourceToAttachmentLocal':np.eye(4).tolist(),
      'connectorConfiguration':cfg,'splitLineage':{'path':str(lineage),'sha256':contract.sha(lineage)},'frozenInputs':pins,
      'helperSnapshots':snapshots,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False,
      'proof':{'protectionPlaneLocalZMetres':plane,'sourceFaces':len(faces),'childFaces':len(fs),'originalRows':len(attrs['POSITION']),
       'newSplitRows':len(local)-len(attrs['POSITION']),'changedReferencedRows':int(edited.sum()),'upperProtectedChildFaces':int(upper.sum()),
       'changedParentSourceFaceIds':changedparents.tolist(),'actualMaximumDisplacementMetres':maximum,'maximumSampledJacobianConditionNumber':float(np.linalg.cond(jac[ref]).max()),
       'continuousDeterminantLowerBound':float(min(np.prod(c['xyScale']) for c in controls)),'minimumParentVsCandidateFaceNormalDot':float(winding.min()),'minimumMappedDifferentialChordOrientationDot':float(mapped_orientation.min()),'sourceBoundaryEdgeSubdivisionCountIncrease':before['boundaryEdges']-original['boundaryEdges'],
       'newAuthoredMeanNormalOppositionChildFaceIds':opposed.tolist(),'exactUpperOriginalRows':True,'exactWholeUpperClippedSurface':True,'wholeExplicitBraAndAllFourRearTracksExact':True,
       'originalBinPrefixAndAllImageBytesExact':True,'UVUnchangedOrExplicitSourceBarycentricInterpolation':True,
       'oneAuthoritativeDoubleCutPartitionForBothRepresentations':True,'noSourceFaceDeleted':True,'noInnerSheetDeletion':True,'originalAffectedBandTopology':band_topology,
       'sourceTopology':original,'subdividedTopology':before,'deformedTopology':after},
      'limitations':['One unselected diagnostic from original waist taper. Stock-profile lower skin transition retains all source sheets.',
       'Conforming source-face subdivision exceeds original 50,000 generation compact budget; no production/native performance acceptance.',
       'Whole upper surface, explicit bra/four tracks, all UV footprints and original maps exact. Complete garment/skin partition and sparse lower atlas-role ambiguity remain unaccepted.',
       'Original inner opening, collar, shoulder ownership and four rear strap topology remain unresolved.',
       'Positive continuous Jacobian is not a finite triangle-intersection certificate; independent actual serialized crossing audit and nine matched views required.',
       'No runtime conversion, staging, client validation or selection.']}
    for p,h in pins.items():contract.require(contract.sha(p)==h,'Frozen connector input changed during execution: '+p)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n');return path,receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();p,r=execute(args.config,args.output);print(json.dumps({'receipt':str(p),'sha256':contract.sha(p),
        'candidateSha256':r['candidateSha256'],'faces':r['proof']['childFaces'],'maxDisplacement':r['proof']['actualMaximumDisplacementMetres']}))

