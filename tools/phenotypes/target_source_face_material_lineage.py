"""Exact source-face serializer and one-step original-material recipient lineage.

This is an additive, explicit protocol. Native-double working fields remain
separate from literal candidate float32 attributes; neither is a tolerance
substitute for the other. It never repairs, retextures or approves an asset.
"""
from pathlib import Path
import json
import numpy as np
import target_contract as c
from target_part_pipeline import pin
from replay_stage_skin_intensity import file_row, frozen_inputs
from place_purposebuilt_pelvis import read_glb, accessor, embedded_maps, BASIS

OPERATION = 'measured-convex-knee-endpoint-source-face-subdivision'
PROTOCOL = 'original-source-barycentric-plus-native-field-delta-v1'
LINEAGE_KIND = 'target-source-face-material-recipient-lineage-v1'
POLICY = ('Original raw source barycentric PNUT plus same frozen native field delta; protected/identity original fields copied literally '
          'including signed zeros; no new field controls.')


def exact_pin(row):
    c.require(isinstance(row,dict) and set(row)=={'path','sha256'} and isinstance(row['path'],str)
              and isinstance(row['sha256'],str) and len(row['sha256'])==64
              and all(x in '0123456789abcdef' for x in row['sha256']), 'Exact source-face lineage path/hash required')
    return pin(row['path'],row['sha256'])


def original_bary(values,faces,parents,bary):
    rows=values[faces[parents]]
    out=np.einsum('fci,fij->fcj',bary,rows.astype(float))
    one=(np.count_nonzero(bary,axis=2)==1)&(bary.max(2)==1)
    a,b=np.where(one);out[a,b]=rows[a,np.argmax(bary[a,b],axis=1)]
    return out


def _ancestor_metadata(source,rp,rec,tp,target,part,context):
    """Load explicitly pinned historical data; never execute old helper code."""
    c.require(rec.get('schemaVersion')==2 and rec.get('kind')=='target-part-geometry' and rec.get('diagnosticOnly') is True,
              'Typed historical width/mirror geometry receipt required')
    c.verify_binding(rec,tp,target,'working')
    c.require(rec['part']==part and rec['joint']==c.PART_JOINTS[part] and rec['model']==c.model(target,part)
              and rec['statureApplications']==0 and Path(rec['candidate']).resolve()==source and rec['candidateSha256']==c.sha(source)
              and np.array_equal(rec['attachmentWorld'],c.frame(target,c.PART_JOINTS[part],'working')), 'Historical ancestor target/source/frame differs')
    pins={str(source):c.sha(source),str(rp):c.sha(rp)};resolutions=[]
    helper_bank=Path(__file__).resolve().parent
    for name,digest in rec['frozenInputs'].items():
        p=Path(name).resolve()
        if p.is_file() and c.sha(p)==digest:pins[str(p)]=digest;continue
        # Exactly the already-declared historical pipeline migration; no data or arbitrary helper substitution.
        candidates=[Path(x).resolve() for x,h in context.items() if h==digest and Path(x).name=='historical-target_part_pipeline.py']
        c.require(p==helper_bank/'target_part_pipeline.py' and digest=='34ea6b0424c4cbce30635822fc3c1a4d821cfa4236897275e9021ee7294a41ed'
                  and len(set(candidates))==1, 'Historical ancestor missing explicit pipeline snapshot: '+name)
        saved=pin(candidates[0],digest);pins[str(saved)]=digest;resolutions.append({'originalPath':str(p),'recordedSha256':digest,'snapshot':file_row(saved)})
    ap=exact_pin(rec['nativeCornerArchive']);pins[str(ap)]=c.sha(ap)
    with np.load(ap,allow_pickle=False) as z:native={k:z[k].copy() for k in z.files}
    c.require({'positions','normals','tangents','uvGltf','uvNative'}<=set(native), 'Historical native PNUT archive required')
    doc,binary=read_glb(source)
    c.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1
              and not doc.get('skins') and not doc.get('animations'), 'Historical detached static one-primitive source required')
    return {'source':source,'receiptPath':rp,'receipt':rec,'document':doc,'binary':binary,'pins':pins,'resolutions':resolutions,'native':native}


def _historical_width_ancestor(source,rp,rec,tp,target,part,context):
    """Independent raw and native width78/mirror equations, scoped to this protocol."""
    current=_ancestor_metadata(source,rp,rec,tp,target,part,context)
    c.require((part=='legl' and rec['operation']=='bone-axis-width-affine') or (part=='legr' and rec['operation']=='mirror'),
              'Unsupported historical source-face ancestor operation/part')
    old_source=pin(rec['source'],rec['sourceSha256']);old_rp=pin(rec['sourceReceipt'],rec['sourceReceiptSha256']);old_rec=json.loads(old_rp.read_text(encoding='utf-8'))
    if part=='legl':
        c.require(old_rec['operation']=='fit' and old_rec['part']=='legl' and rec['proof'].get('widthFactor')==.78,
                  'One installed-stock width78 left ancestor required')
        prior=_ancestor_metadata(old_source,old_rp,old_rec,tp,target,'legl',{**context,**current['pins']})
        hip=c.frame(target,'lthigh_g','working');knee=c.frame(target,'lshin_g','working');shaft=(np.linalg.inv(hip)@knee)[:3,3];u=shaft/np.linalg.norm(shaft)
        hint=hip[:3,:3].T@np.array([1.,0,0]);axis=hint-hint.dot(u)*u;axis/=np.linalg.norm(axis);measured=np.eye(3)-.22*np.outer(axis,axis)
        matrix=np.asarray(rec['proof']['matrixLocal'],float);translation=np.zeros(3);order=[0,1,2]
        c.require(matrix.shape==(3,3) and np.isfinite(matrix).all() and np.max(abs(matrix-measured))<1e-14
                  and np.linalg.det(matrix)>0 and np.max(abs(np.asarray(rec['proof']['widthAxisLocal'])-axis))<1e-14,
                  'Historical width78 actual stock-derived matrix differs')
    else:
        c.require(old_rec['operation']=='bone-axis-width-affine' and old_rec['part']=='legl', 'Mirror ancestor must immediately follow original width78 left')
        prior=_historical_width_ancestor(old_source,old_rp,old_rec,tp,target,'legl',{**context,**current['pins']})
        left=c.frame(target,'lthigh_g','working');right=c.frame(target,'rthigh_g','working')
        configs=[]
        for name,digest in current['pins'].items():
            path=Path(name)
            if path.suffix=='.json':
                value=json.loads(path.read_text(encoding='utf-8'))
                if value.get('kind')=='target-thigh-width-diagnostic' and value.get('widthFactor')==.78:configs.append((path,value))
        c.require(len(configs)==1, 'One exact historical width/mirror configuration required')
        cfg_path,cfg=configs[0];plane=cfg.get('mirrorPlaneWorldX')
        c.require(type(plane) in (int,float) and np.isfinite(plane) and abs(plane-(left[0,3]+right[0,3])/2)<1e-12,
                  'Original declared mirror plane differs from installed hip midplane')
        world=np.eye(4);world[0,0]=-1;world[0,3]=2*plane
        affine=np.linalg.inv(right)@world@left;matrix=affine[:3,:3];translation=affine[:3,3];order=[0,2,1]
        c.require(np.array_equal(rec['reflectionWorld'],world) and np.array_equal(rec['proof']['sourceToRightLocal'],affine)
                  and rec['proof']['triangleCornerOrder']==order and rec['proof']['tangentWFlipsExactly'] is True,
                  'Historical mirror actual frame/winding/sign declaration differs')
    old_doc,old_bin=prior['document'],prior['binary'];doc,binary=current['document'],current['binary'];old_pr=old_doc['meshes'][0]['primitives'][0];pr=doc['meshes'][0]['primitives'][0]
    c.require(set(old_pr['attributes'])==set(pr['attributes'])=={'POSITION','NORMAL','TEXCOORD_0','TANGENT'}
              and old_pr['material']==pr['material'] and binary[:len(old_bin)]==old_bin,
              'Historical primitive/attribute/material/BIN ancestor differs')
    for key in ('materials','textures','images','samplers'):c.require(old_doc.get(key)==doc.get(key),'Historical original material definition differs: '+key)
    c.require(embedded_maps(old_doc,old_bin)==embedded_maps(doc,binary),'Historical embedded maps differ')
    old_faces=accessor(old_doc,old_bin,old_pr['indices']).reshape(-1,3);faces=accessor(doc,binary,pr['indices']).reshape(-1,3)
    c.require(np.array_equal(faces,old_faces[:,order]) and pr['attributes']['TEXCOORD_0']==old_pr['attributes']['TEXCOORD_0'],
              'Historical literal UV accessor/index winding differs')
    p=accessor(old_doc,old_bin,old_pr['attributes']['POSITION']).astype(float)@BASIS.T
    n=accessor(old_doc,old_bin,old_pr['attributes']['NORMAL']).astype(float)@BASIS.T
    t=accessor(old_doc,old_bin,old_pr['attributes']['TANGENT']).astype(float);t[:,:3]=t[:,:3]@BASIS.T
    def transformed(N,T,mirror):
        if mirror:
            nn=N@matrix.T;tt=T.copy();tt[...,:3]=T[...,:3]@matrix.T;tt[...,3]*=-1;return nn,tt
        shape=N.shape;flat=N.reshape(-1,3);nn=np.linalg.solve(matrix.T,flat.T).T;nn*=np.linalg.norm(flat,axis=1)[:,None]/np.linalg.norm(nn,axis=1)[:,None];nn=nn.reshape(shape)
        tt=T.copy();unit=nn/np.linalg.norm(nn,axis=-1)[...,None];v=T[...,:3]@matrix.T;v-=(v*unit).sum(-1)[...,None]*unit
        v*=np.linalg.norm(T[...,:3],axis=-1)[...,None]/np.linalg.norm(v,axis=-1)[...,None];tt[...,:3]=v;return nn,tt
    nn,tt=transformed(n,t,part=='legr');q=p@matrix.T+translation;rt=tt.copy();rt[:,:3]=rt[:,:3]@BASIS
    expected={'POSITION':q@BASIS,'NORMAL':nn@BASIS,'TANGENT':rt,'TEXCOORD_0':accessor(old_doc,old_bin,old_pr['attributes']['TEXCOORD_0'])}
    for semantic,a in expected.items():
        got=accessor(doc,binary,pr['attributes'][semantic]);want=np.asarray(a,dtype='<f4')
        c.require(got.dtype==want.dtype and got.shape==want.shape and got.tobytes()==want.tobytes(),
                  'Historical raw-source literal attribute bytes differ: '+semantic)
    base=prior['native'];out=current['native'];P=(base['positions']@matrix.T+translation)[:,order];N,T=transformed(base['normals'],base['tangents'],part=='legr');N=N[:,order];T=T[:,order]
    c.require(np.array_equal(P,out['positions']) and np.array_equal(base['uvGltf'][:,order],out['uvGltf'])
              and np.array_equal(base['uvNative'][:,order],out['uvNative']) and np.array_equal(T[:,:,3],out['tangents'][:,:,3]),
              'Historical separate native P/UV/W transform differs')
    n_error=float(abs(N-out['normals']).max());t_error=float(abs(T-out['tangents']).max())
    c.require(n_error<5e-14 and t_error<5e-14, 'Historical independent native N/T transport differs')
    current['pins'].update(prior['pins']);current['resolutions'].extend(prior['resolutions'])
    current['ancestorRepresentationProof']={'kind':'independent-historical-width78-and-actual-frame-mirror-parent-replay','operation':rec['operation'],
        'source':file_row(source),'receipt':file_row(rp),'nativeArchive':rec['nativeCornerArchive'],'originalSource':file_row(old_source),
        'actualRawGLBPNUTUVIndexMapsAndBINPrefixByteExact':True,'separateNativeDoublePNUVTTransformVerified':True,
        'independentNativeNormalMaximumError':n_error,'independentNativeTangentMaximumError':t_error,
        'nativeDoubleEqualityWithRawFloat32NotClaimed':True,'actualFramesUnchanged':True}
    return current

def source_face_geometry(source,rp,rec,tp,target,part,space,doc,binary,*,material_execution=None):
    """Replay the declared serializer exactly; no catch-and-tolerate fallback."""
    c.require(space=='working' and rec['operation']==OPERATION and rec.get('diagnosticOnly') is True
              and rec.get('proof',{}).get('encodedRepresentationPolicy')==POLICY
              and 'nativeCornerArchive' in rec and 'lineage' in rec and rec['statureApplications']==0,
              'Explicit source-face serializer operation/policy/working archive required')
    from replay_stage_skin_calibration import geometry_input
    old_source=pin(rec['source'],rec['sourceSha256']);old_rp=pin(rec['sourceReceipt'],rec['sourceReceiptSha256'])
    old_rec=json.loads(old_rp.read_text(encoding='utf-8'))
    c.require(old_rec['operation'] in ('fit','mirror','bone-axis-width-affine','measured-angular-profile-ankle-taper') and old_rec['coordinateSpace']=='working'
              and old_rec['statureApplications']==0, 'Exactly one immediate source-face geometry operation required')
    if (part=='legl' and old_rec['operation']=='bone-axis-width-affine') or (part=='legr' and old_rec['operation']=='mirror' and 'sourceToRightLocal' in old_rec.get('proof',{})):
        parent=_historical_width_ancestor(old_source,old_rp,old_rec,tp,target,part,rec['frozenInputs'])
    else:
        parent=geometry_input(file_row(old_source),file_row(old_rp),tp,target,part,'working',material_execution=material_execution)
    c.require(np.array_equal(rec['attachmentWorld'],old_rec['attachmentWorld'])
              and np.array_equal(rec['sourceToAttachmentLocal'],np.eye(4)), 'Source-face rig/frame identity required')
    ap=exact_pin(rec['nativeCornerArchive']);basep=exact_pin(old_rec['nativeCornerArchive']);lp=exact_pin(rec['lineage'])
    lineage=json.loads(lp.read_text(encoding='utf-8'))
    c.require(lineage.get('sourceGeometry')==file_row(old_rp) and lineage.get('nativeSource')==file_row(basep)
              and lineage.get('originalSha256')==c.sha(old_source) and lineage.get('allSourceFacesRetained') is True,
              'Source-face native/geometry lineage differs')
    with np.load(ap,allow_pickle=False) as z:out={k:z[k].copy() for k in z.files}
    with np.load(basep,allow_pickle=False) as z:base={k:z[k].copy() for k in z.files}
    required={'positions','normals','uvGltf','uvNative','tangents','connectorParentFaceIds','connectorBarycentricNative',
              'connectorParentPositions','connectorParentNormals','connectorProtectedWholeFaceMask','connectorJacobianLocalCorners'}
    c.require(required<=set(out) and {'positions','normals','uvGltf','uvNative','tangents'}<=set(base), 'Complete native source-face PNUT lineage required')
    old_doc,old_bin=parent['document'],parent['binary']
    c.require(len(old_doc['meshes'])==len(doc['meshes'])==1 and len(old_doc['meshes'][0]['primitives'])==len(doc['meshes'][0]['primitives'])==1,
              'One literal source-face skin primitive required')
    old_pr=old_doc['meshes'][0]['primitives'][0];pr=doc['meshes'][0]['primitives'][0]
    semantics={'POSITION','NORMAL','TEXCOORD_0','TANGENT'}
    c.require(set(old_pr['attributes'])==set(pr['attributes'])==semantics and pr['material']==old_pr['material'],
              'Complete unchanged source-face PNUT/material semantics required')
    old_faces=accessor(old_doc,old_bin,old_pr['indices']).reshape(-1,3).astype('i8')
    faces=accessor(doc,binary,pr['indices']).reshape(-1,3).astype('i8')
    parents=out['connectorParentFaceIds'];bary=out['connectorBarycentricNative'];protected=out['connectorProtectedWholeFaceMask']
    count=len(parents)
    c.require(parents.ndim==1 and parents.dtype.kind in 'iu' and count>0 and parents.min()>=0
              and parents.max()<len(old_faces) and set(parents.tolist())==set(range(len(old_faces)))
              and bary.shape==(count,3,3) and np.isfinite(bary).all() and (bary>=0).all() and (bary<=1).all()
              and np.max(abs(bary.sum(2)-1))<1e-12 and protected.dtype==bool and protected.shape==(count,),
              'Typed complete finite source-face barycentric inventory required')
    child_area=np.linalg.det(bary)
    coverage=np.bincount(parents,weights=child_area,minlength=len(old_faces))
    c.require((child_area>0).all() and np.max(abs(coverage-1))<1e-12,
              'Positive winding and full original per-face barycentric area coverage required')
    c.require(np.array_equal(faces,np.arange(count*3).reshape(-1,3)) and binary[:len(old_bin)]==old_bin
              and lineage.get('sourceBinaryPrefixRetainedBytes')==len(old_bin), 'Original BIN prefix/current literal corner index order differs')
    for key in ('materials','textures','images','samplers'):
        c.require(doc.get(key)==old_doc.get(key), 'Original material definition changed: '+key)
    c.require(embedded_maps(doc,binary)==embedded_maps(old_doc,old_bin), 'Original embedded map bytes changed')
    native={key:np.einsum('fci,fij->fcj',bary,base[key][parents]) for key in ('positions','normals','uvGltf','uvNative','tangents')}
    for key,a in [('connectorParentPositions',native['positions']),('connectorParentNormals',native['normals']),
                  ('uvGltf',native['uvGltf']),('uvNative',native['uvNative'])]:
        c.require(np.array_equal(out[key],a), 'Original native-double barycentric field differs: '+key)
    j=out['connectorJacobianLocalCorners']
    c.require(j.shape==(count,3,3,3) and np.isfinite(j).all() and (np.linalg.det(j)>0).all(), 'Finite proper source-face Jacobian required')
    j=j.reshape(-1,3,3);p0=native['positions'];n0=native['normals'];t0=native['tangents']
    edited=np.any(out['positions']!=p0,axis=2).reshape(-1)
    raw_n=n0.reshape(-1,3);solved_n=np.linalg.solve(j.transpose(0,2,1),raw_n[:,:,None])[:,:,0]
    solved_n*=np.linalg.norm(raw_n,axis=1)[:,None]/np.linalg.norm(solved_n,axis=1)[:,None]
    solved_n[~edited]=raw_n[~edited];solved_n=solved_n.reshape(n0.shape);solved_n[protected]=n0[protected]
    n_error=float(abs(solved_n-out['normals']).max())
    vector=np.einsum('nij,nj->ni',j,t0.reshape(-1,4)[:,:3]);unit=solved_n.reshape(-1,3)/np.linalg.norm(solved_n.reshape(-1,3),axis=1)[:,None]
    vector-=np.einsum('ni,ni->n',vector,unit)[:,None]*unit
    vector*=np.linalg.norm(t0.reshape(-1,4)[:,:3],axis=1)[:,None]/np.linalg.norm(vector,axis=1)[:,None]
    vector[~edited]=t0.reshape(-1,4)[~edited,:3];solved_t=t0.copy();solved_t[:,:,:3]=vector.reshape(t0.shape[:2]+(3,));solved_t[protected]=t0[protected]
    t_error=float(abs(solved_t-out['tangents']).max())
    c.require(np.isfinite(out['positions']).all() and n_error<5e-14 and t_error<5e-14
              and np.array_equal(out['tangents'][:,:,3],t0[:,:,3])
              and np.array_equal(out['positions'][protected],p0[protected])
              and np.array_equal(out['normals'][protected],n0[protected])
              and np.array_equal(out['tangents'][protected],t0[protected]), 'Source-face native PN/T/W protection or transport differs')
    before={'POSITION':p0@BASIS,'NORMAL':n0@BASIS,'TEXCOORD_0':native['uvGltf']}
    after={'POSITION':out['positions']@BASIS,'NORMAL':out['normals']@BASIS,'TEXCOORD_0':native['uvGltf']}
    a=t0.copy();a[:,:,:3]=a[:,:,:3]@BASIS;b=out['tangents'].copy();b[:,:,:3]=b[:,:,:3]@BASIS;before['TANGENT']=a;after['TANGENT']=b
    attributes={}
    for semantic in sorted(semantics):
        old_values=accessor(old_doc,old_bin,old_pr['attributes'][semantic]);raw=original_bary(old_values,old_faces,parents,bary)
        delta=after[semantic]-before[semantic];expected=(raw+delta).astype('<f4');identity=np.all(delta==0,axis=2)
        expected[identity]=raw.astype('<f4')[identity];expected[protected]=raw.astype('<f4')[protected]
        actual=accessor(doc,binary,pr['attributes'][semantic])[faces]
        c.require(actual.dtype==expected.dtype and actual.shape==expected.shape and actual.tobytes()==expected.tobytes(),
                  'Exact literal source-barycentric serialized byte replay differs: '+semantic)
        c.require(actual[protected].tobytes()==raw.astype('<f4')[protected].tobytes(), 'Protected original attribute changed: '+semantic)
        import hashlib
        attributes[semantic]={'literalBytesExact':True,'protectedOriginalBytesExact':True,'sha256':hashlib.sha256(actual.tobytes()).hexdigest()}
    proof={'kind':PROTOCOL,'operation':OPERATION,'currentCandidate':file_row(source),'currentGeometryReceipt':file_row(rp),
           'parentCandidate':file_row(old_source),'parentGeometryReceipt':file_row(old_rp),'nativeCornerArchive':file_row(ap),
           'parentNativeCornerArchive':file_row(basep),'sourceLineage':file_row(lp),'originalFaces':len(old_faces),'currentFaces':count,
           'attributes':attributes,'sourceUVBarycentricAreaCoverageMaximumError':float(abs(coverage-1).max()),
           'minimumChildBarycentricAreaFraction':float(child_area.min()),'minimumJacobianDeterminant':float(np.linalg.det(j).min()),
           'nativeDoubleNormalTransportMaximumError':n_error,'nativeDoubleTangentTransportMaximumError':t_error,
           'candidateUvSamplePolicy':'Actual decoded serialized TEXCOORD_0 only; nativeDouble uvGltf/uvNative are separate lineage data.',
           'originalMaterialMapsBINPrefixExact':True,'parentRepresentationProof':parent.get('ancestorRepresentationProof'),'geometryOrMaterialAccepted':False}
    pins={**parent['pins'],str(ap):c.sha(ap),str(basep):c.sha(basep),str(lp):c.sha(lp)}
    for path,digest in pins.items():pin(path,digest)
    return proof,pins,parent['resolutions']


def material_recipient(value,current,material,tp,target,part,space,*,material_execution=None):
    """Replay explicit immediate old material -> changed working mesh relation."""
    path=exact_pin(value);r=json.loads(path.read_text(encoding='utf-8'))
    required={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','targetId','rigRevision','coordinateSpace','part',
              'serializerProtocol','materialSource','currentWorkingSource','nativeCornerArchive','sourceLineage','independentGeometryReplay','diagnosticAuthorization'}
    c.require(set(r)==required and type(r['schemaVersion']) is int and r['schemaVersion']==1 and r['kind']==LINEAGE_KIND
              and r['diagnosticOnly'] is True and r['serializerProtocol']==PROTOCOL and r['part']==part
              and space=='working' and material['receipt']['coordinateSpace']=='working', 'Explicit one-step working material recipient required')
    c.verify_binding(r,tp,target,'working')
    if material_execution is not None:
        from phenotype_material_execution_adoption import resolve
        resolve(material_execution,module_file=__file__,path=path,value=r,tp=tp,target=target,part=part,space=space,consumer='sourceface.recipient')
    c.require(r['materialSource']=={'candidate':file_row(material['source']),'geometryReceipt':file_row(material['receiptPath'])}
              and r['currentWorkingSource']=={'candidate':file_row(current['source']),'geometryReceipt':file_row(current['receiptPath'])},
              'Stale/cross-source material recipient binding')
    rec=current['receipt']
    c.require(r['nativeCornerArchive']==rec['nativeCornerArchive'] and r['sourceLineage']==rec['lineage']
              and Path(rec['source']).resolve()==material['source'] and rec['sourceSha256']==c.sha(material['source'])
              and Path(rec['sourceReceipt']).resolve()==material['receiptPath'] and rec['sourceReceiptSha256']==c.sha(material['receiptPath']),
              'Immediate original-material geometry ancestry differs')
    replay=exact_pin(r['independentGeometryReplay']);approval=exact_pin(r['diagnosticAuthorization'])
    evidence=json.loads(replay.read_text(encoding='utf-8'));authorization=json.loads(approval.read_text(encoding='utf-8'))
    c.require(evidence.get('guardPass') is True and part in evidence.get('parts',{})
              and evidence['parts'][part]['geometry']==file_row(current['receiptPath'])
              and evidence['parts'][part]['candidate']==file_row(current['source']), 'Independent source-face recipient replay binding differs')
    c.require(authorization.get('kind')=='reviewed-diagnostic-source-face-material-transfer' and authorization.get('approved') is True
              and authorization.get('target')==file_row(tp) and part in authorization.get('parts',{})
              and authorization['parts'][part]==r['currentWorkingSource'] and authorization.get('materialOrClientAccepted') is False,
              'Explicit diagnostic-only material recipient authorization required')
    proof,pins,resolutions=source_face_geometry(current['source'],current['receiptPath'],rec,tp,target,part,space,current['document'],current['binary'],material_execution=material_execution)
    pins.update({str(path):c.sha(path),str(replay):c.sha(replay),str(approval):c.sha(approval)})
    return {'kind':'single-explicit-source-face-original-material-recipient','receipt':file_row(path),'serializerProtocol':PROTOCOL,
            'workingMaterialSource':file_row(material['source']),'workingMaterialReceipt':file_row(material['receiptPath']),
            'currentWorkingSource':file_row(current['source']),'currentWorkingReceipt':file_row(current['receiptPath']),
            'exactGeometryReplay':proof,'originalParentManifestRelabeled':False,'originalMapUVSamplerDefinitionExact':True},pins,resolutions