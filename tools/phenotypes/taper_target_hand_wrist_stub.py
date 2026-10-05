"""Source-bound RIGHT hand connector diagnostic; never refit or restature.

Execution requires an explicitly supplied hash of the reviewed config. Configs
alone are non-executable proposals. Outputs remain unaccepted diagnostics.
"""
import argparse, copy, json, shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from target_part_pipeline import pin, verify_source_receipt
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, raw_corners, read_glb, write_glb
from conservative_face_selection import mesh_arrays, topology
from diagnostic_axis_radial import append_attributes, TOPOLOGY_KEYS
from hand_stub_radial_math import parameters, profile, transport

START=-.015
END=.00736165652051568
FACTORS={.002:.9495134511569223,.004:.8990269023138446}
CONFIG_KEYS={'schemaVersion','kind','diagnosticOnly','reviewApproved','executable','meshExportAuthorized','targetContract','targetContractSha256','targetId','rigRevision','coordinateSpace','targetRevision','targetContractReference','targetSpace','part','sourceGeometry','sourceCandidate','sourceNativeCorners','mask','mathHelper','exporterHelper','profile','preservation','analyticSourcePrediction','acceptance','requiredNextReview','originalV1ReviewConfig','revisionCorrection','originalV2ReviewConfig','tests','protectedInputs','identityShadingCorrection','originalV3ReviewConfig','scalarRoundoffPolicy'}

def validate_radius_scalars(saved_radius,actual_radius,saved_factor,amount):
    values=np.asarray([saved_radius,actual_radius,saved_factor,amount],float)
    tc.require(np.isfinite(values).all() and saved_radius>0 and actual_radius>0 and amount>0 and 0<saved_factor<=1,'Finite positive source radius/factor/bound required')
    radius_ulp=float(np.spacing(saved_radius));factor_ulp=float(np.spacing(saved_factor))
    tc.require(abs(actual_radius-saved_radius)<=radius_ulp,'Source radius differs by more than 1 declared ULP')
    derived_factor=1.-amount/actual_radius
    tc.require(abs(derived_factor-saved_factor)<=factor_ulp,'Source-derived factor differs by more than 1 declared ULP')
    analytic_max=(1.-saved_factor)*actual_radius
    tc.require(analytic_max<=amount+float(np.spacing(amount)),'Physical analytic radial bound exceeded beyond 1 evaluation ULP')
    return {'radiusDifferenceMetres':actual_radius-saved_radius,'radiusDifferenceULPs':(actual_radius-saved_radius)/radius_ulp,'derivedFactorDifferenceULPs':(derived_factor-saved_factor)/factor_ulp,'analyticMaximumRadialMovementMetres':analytic_max,'radiusValidationULPs':1,'factorValidationULPs':1,'analyticBoundEvaluationULPs':1}
def checked_config(c,config_hash,approved_hash):
    tc.require(config_hash==approved_hash and len(config_hash)==64,'Explicit matching approved review SHA256 required')
    tc.require(set(c)==CONFIG_KEYS and c['schemaVersion']==1 and c['kind']=='target-hand-stub-radial-review-config' and c['diagnosticOnly'] is True,'Exact source-bound diagnostic review configuration required')
    tc.require(c['part']=='handr' and c['coordinateSpace']==c['targetSpace']=='working','Only RIGHT hand working connector allowed')
    tc.require(c['reviewApproved'] is False and c['executable'] is False and c['meshExportAuthorized'] is False,'Review config must remain immutable unadopted proposal; approval is explicit execution argument')
    tc.require(all(v is False for v in c['acceptance'].values()),'Unaccepted diagnostic gates required')
    p=c['profile'];tc.require(p['axisFrame']=='exact frozen handr attachment-local working coordinates' and p['axisOrigin']==[0.,0.,0.] and p['axisDirection']==[0.,0.,1.],'Exact unrecentered frozen hand-local frame required')
    start,end,k=parameters(p['startZMetres'],p['endZMetres'],p['terminalFactor']);amount=p['maximumRadialMovementMetres']
    tc.require(start==START and end==END and amount in FACTORS and k==FACTORS[amount],'Exact reviewed coherent source band and 2mm/4mm factor required')
    tc.require(c['preservation']['additionalUniformScaleApplications']==c['preservation']['additionalStatureApplications']==0,'Additional fit/stature forbidden')
    return start,end,k,amount

def checked_parent_frame(parent,target):
    tc.require(parent['part']=='handr' and parent['joint']=='rhand_g' and parent['coordinateSpace']=='working' and parent['statureApplications']==0,'Exact RIGHT hand zero-stature source binding required')
    tc.require(parent['operation']=='fit' and parent['reflectionWorld'] is None,'Untreated original positive-uniform RIGHT hand fit required; cumulative/mirror field rejected')
    H=tc.frame(target,'rhand_g','working');tc.require(np.array_equal(parent['attachmentWorld'],H),'Frozen hand attachment changed')
    matrix=np.asarray(parent['sourceToAttachmentLocal'],float)
    tc.require(matrix.shape==(4,4) and np.isfinite(matrix).all() and np.array_equal(matrix[3],[0,0,0,1]),'Finite original source bind/fit matrix required')
    gram=matrix[:3,:3].T@matrix[:3,:3];scale_squared=float(np.trace(gram)/3)
    tc.require(scale_squared>0 and np.linalg.det(matrix[:3,:3])>0 and np.allclose(gram,np.eye(3)*scale_squared,atol=1e-14,rtol=0),'Original proper positive uniform fit required')
    return H
def complete_mask(mask,points,faces,start,end):
    tc.require(mask['kind']=='target-hand-stub-radial-review-mask' and mask['part']=='handr' and mask['coordinateSpace']=='working' and mask['axialBandMetres']==[start,end] and mask['reviewApproved'] is False and mask['exportAuthorized'] is False,'Exact complete unadopted hand-stub review mask required')
    active=points[:,2]>start
    expected={'activeOriginalVertexRows':np.flatnonzero(active),'protectedOriginalVertexRows':np.flatnonzero(~active),'fullAffectedOriginalFaceIds':np.flatnonzero(active[faces].all(1)),'mixedAffectedOriginalFaceIds':np.flatnonzero(active[faces].any(1)&~active[faces].all(1)),'protectedOriginalFaceIds':np.flatnonzero(~active[faces].any(1))}
    for key,ids in expected.items():
        tc.require(isinstance(mask[key],list) and all(type(v) is int for v in mask[key]),'Exact integer original row/face IDs required: '+key)
        tc.require(np.array_equal(np.asarray(mask[key],dtype=np.int64),ids),'Complete ordered mask differs: '+key)
    return active

def bake(doc,blob,archive,mask,start,end,k):
    raw,faces,primitive=mesh_arrays(doc,blob);attrs=primitive['attributes']
    tc.require(set(attrs)=={'POSITION','NORMAL','TANGENT','TEXCOORD_0'},'Exact original P/N/T/UV required')
    tc.require(doc['scenes']==[{'nodes':[0]}] and len(doc['buffers'])==1 and not doc['buffers'][0].get('uri'),'One embedded static identity-node source required')
    rows={s:accessor(doc,blob,attrs[s]) for s in ['POSITION','NORMAL','TANGENT','TEXCOORD_0']}
    tc.require(all(v.dtype==np.dtype('<f4') and len(v)==len(raw) and np.isfinite(v).all() for v in rows.values()),'Finite exact float32 authored attribute rows required')
    tc.require(rows['NORMAL'].shape==(len(raw),3) and rows['TANGENT'].shape==(len(raw),4) and rows['TEXCOORD_0'].shape==(len(raw),2),'Complete original attribute correspondence required')
    local=raw.astype(float)@BASIS.T;n=rows['NORMAL'].astype(float)@BASIS.T;t=rows['TANGENT'].astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T
    active=complete_mask(mask,local,faces,start,end)
    q,nn,tt,J,math_active=transport(local,n,t,start,end,k);tc.require(np.array_equal(active,math_active),'Math/source mask differs')
    shading_active=active&np.any(J!=np.eye(3),axis=(1,2))
    newrows={s:rows[s].copy() for s in ['POSITION','NORMAL','TANGENT']}
    newrows['POSITION'][active]=(q[active]@BASIS).astype('<f4')
    newrows['NORMAL'][shading_active]=(nn[shading_active]@BASIS).astype('<f4')
    rt=tt.copy();rt[:,:3]=rt[:,:3]@BASIS;newrows['TANGENT'][shading_active]=rt[shading_active].astype('<f4')
    tc.require(newrows['POSITION'][:,1].tobytes()==rows['POSITION'][:,1].tobytes(),'Source rawGLTF Y / hand-local Z altered')
    tc.require(newrows['TANGENT'][:,3].tobytes()==rows['TANGENT'][:,3].tobytes(),'Tangent W changed')
    for s in newrows:tc.require(newrows[s][~active].tobytes()==rows[s][~active].tobytes(),'Protected authored P/N/T rows altered')
    for s in ['NORMAL','TANGENT']:tc.require(newrows[s][~shading_active].tobytes()==rows[s][~shading_active].tobytes(),'Computed-identity authored shading altered')
    # Exact source seam equivalence must neither split nor merge after float32.
    _,old_group=np.unique(raw,axis=0,return_inverse=True);_,new_group=np.unique(newrows['POSITION'],axis=0,return_inverse=True)
    pairs=np.unique(np.column_stack([old_group,new_group]),axis=0)
    tc.require(len(pairs)==len(np.unique(old_group))==len(np.unique(new_group)),'Source exact-position seam group split or merge')
    before=topology(raw,faces);after=topology(newrows['POSITION'],faces)
    for key in TOPOLOGY_KEYS:tc.require(before[key]==after[key],'Introduced serialized topology change: '+key)
    old_tri=local[faces];new_tri=(newrows['POSITION'].astype(float)@BASIS.T)[faces]
    old_cross=np.cross(old_tri[:,1]-old_tri[:,0],old_tri[:,2]-old_tri[:,0]);new_cross=np.cross(new_tri[:,1]-new_tri[:,0],new_tri[:,2]-new_tri[:,0])
    old_len=np.linalg.norm(old_cross,axis=1);new_len=np.linalg.norm(new_cross,axis=1)
    tc.require((old_len>2e-15).all() and (new_len>2e-15).all(),'Source/descendant degenerate face rejected')
    dots=np.einsum('ij,ij->i',old_cross,new_cross)/(old_len*new_len);tc.require((dots>0).all(),'Serialized chord-face inversion rejected')
    arc={key:value.copy() for key,value in archive.items()}
    tc.require(np.array_equal(arc['sourceTriangleIds'],np.arange(len(faces))) and np.array_equal(arc['sourceCornerOrder'],np.tile([0,1,2],(len(faces),1))) and np.array_equal(arc['primitiveIds'],np.zeros(len(faces),int)),'Complete original face/corner association required')
    tc.require(arc['positions'].shape==old_tri.shape and arc['normals'].shape==old_tri.shape and arc['tangents'].shape==(len(faces),3,4) and np.array_equal(arc['uvGltf'],rows['TEXCOORD_0'][faces]),'Original authoritative P/N/T/UV corners required')
    tc.require(float(abs(arc['positions']-old_tri).max())<5e-8 and float(abs(arc['normals']-n[faces]).max())<2e-7 and float(abs(arc['tangents']-t[faces]).max())<2e-7,'Authoritative source P/N/T correspondence differs')
    cm=active[faces];tc.require(np.array_equal(arc['positions'][:,:,2]>start,cm),'Source corner/serialized mask classification ambiguous')
    ap,an,at=arc['positions'].reshape(-1,3),arc['normals'].reshape(-1,3),arc['tangents'].reshape(-1,4)
    aq,ann,att,aJ,am=transport(ap,an,at,start,end,k);tc.require(np.array_equal(am.reshape(cm.shape),cm),'Authoritative source corner scope differs')
    arc['positions']=aq.reshape(old_tri.shape);arc['normals']=ann.reshape(old_tri.shape);arc['tangents']=att.reshape(len(faces),3,4)
    for key in ['positions','normals','tangents']:tc.require(arc[key][~cm].tobytes()==archive[key][~cm].tobytes(),'Protected authoritative corners altered')
    # Preserve all other exact source arrays, including nativeV/source ancestry.
    for key in archive:
        if key not in ('positions','normals','tangents'):tc.require(np.array_equal(arc[key],archive[key]),'Undeclared source corner array altered: '+key)
    arc.update(handStubActiveOriginalVertexMask=active,handStubParentOriginalFaces=faces,handStubParentRawP=rows['POSITION'],handStubParentRawN=rows['NORMAL'],handStubParentRawT=rows['TANGENT'],handStubJacobian=J)
    changed,payload=append_attributes(doc,blob,newrows)
    # Prove only append-only P/N/T accessor bindings changed.
    restored=copy.deepcopy(changed);restored['meshes'][0]['primitives'][0]['attributes']=attrs;restored['accessors']=restored['accessors'][:-3];restored['bufferViews']=restored['bufferViews'][:-3];restored['buffers'][0]['byteLength']=doc['buffers'][0]['byteLength']
    tc.require(restored==doc and payload[:len(blob)]==blob,'Scene/maps/material/index/BIN source changed')
    proof={'continuousDeterminantLowerBound':k*k,'actualMinimumJacobianDeterminant':float(np.linalg.det(J).min()),'maximumDisplacementMetres':float(np.linalg.norm(q-local,axis=1).max()),'maximumSerializedDisplacementMetres':float(np.linalg.norm(new_tri-old_tri,axis=2).max()),'maximumAuthoredNormalMagnitudeError':float(abs(np.linalg.norm(nn,axis=1)-np.linalg.norm(n,axis=1)).max()),'maximumAuthoredTangentMagnitudeError':float(abs(np.linalg.norm(tt[:,:3],axis=1)-np.linalg.norm(t[:,:3],axis=1)).max()),'protectedSerializedPNTRowsExact':True,'computedIdentitySerializedNTExact':True,'allAxialZExact':True,'tangentWExact':True,'sourceBINPrefixExact':True,'sourceUVMapsMaterialsFaceIndicesAndOrderExact':True,'sourceExactPositionSeamEquivalencePreserved':True,'activeOriginalRows':int(active.sum()),'protectedOriginalRows':int((~active).sum()),'identityJacobianRows':int((~shading_active).sum()),'affectedOriginalFaces':int(active[faces].any(1).sum()),'minimumDiscreteFaceNormalDot':float(dots.min()),'beforeTopology':before,'afterTopology':after,'maximumPositionFloat32ErrorMetres':float(abs(new_tri-arc['positions']).max()),'maximumNormalFloat32Error':float(abs((newrows['NORMAL'].astype(float)@BASIS.T)[faces]-arc['normals']).max()),'maximumTangentFloat32Error':float(abs((np.c_[newrows['TANGENT'][:,:3].astype(float)@BASIS.T,newrows['TANGENT'][:,3]])[faces]-arc['tangents']).max()),'normalPolicy':'Original authored covectors transported by inverse Jacobian transpose and original magnitude retained; exact computed identity preserves original bytes.','tangentPolicy':'Jacobian vector followed by normal orthogonalization/original magnitude; exact computed identity preserves authored nonorthogonality and W bytes.','injectivity':'Unchanged z plus strictly positive radial s(z); C2 quintic joins. No source recenter/fit/stature/socket change.'}
    return changed,payload,arc,proof

def execute(config_path,output,approved_sha256):
    config_path=Path(config_path).resolve();c=json.loads(config_path.read_text(encoding='utf-8-sig'));h=tc.sha(config_path);start,end,k,amount=checked_config(c,h,approved_sha256)
    tp=pin(c['targetContract'],c['targetContractSha256']);target=tc.load(tp);tc.verify_binding(c,tp,target,'working')
    tc.require(target['identity']['race']=='troll' and target['identity']['gender']=='male' and target['identity']['prefix']=='pmg0','Troll male target ownership required')
    for key in ['sourceGeometry','sourceCandidate','sourceNativeCorners','mask','mathHelper','exporterHelper']:pin(c[key]['path'],c[key]['sha256'])
    tc.require(Path(c['mathHelper']['path']).resolve()==Path(__file__).with_name('hand_stub_radial_math.py').resolve() and Path(c['exporterHelper']['path']).resolve()==Path(__file__).resolve(),'Executing helpers must match reviewed source snapshots')
    source=Path(c['sourceCandidate']['path']).resolve();pp=Path(c['sourceGeometry']['path']).resolve();parent=verify_source_receipt(source,pp,tp,target,'handr','working')
    H=checked_parent_frame(parent,target)
    tc.require(parent['nativeCornerArchive']['path']==c['sourceNativeCorners']['path'] and parent['nativeCornerArchive']['sha256']==c['sourceNativeCorners']['sha256'],'Native corner parent differs')
    pins=dict(parent['frozenInputs'])
    def add(p,h):
        p=Path(p).resolve();key=str(p);tc.require(key not in pins or pins[key]==h,'Conflicting source pin');pin(p,h);pins[key]=h
    for p,h in c['protectedInputs'].items():add(p,h)
    helpers=[Path(__file__).resolve()]+[Path(__file__).with_name(n) for n in ['hand_stub_radial_math.py','target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','conservative_face_selection.py','diagnostic_axis_radial.py']]
    for p in helpers+[config_path,tp,source,pp,Path(c['mask']['path']),Path(c['sourceNativeCorners']['path'])]:add(p,tc.sha(p))
    mask=json.loads(Path(c['mask']['path']).read_text());tc.require(mask['sourceGeometry']==c['sourceGeometry'] and mask['sourceCandidate']==c['sourceCandidate'],'Mask actual source binding differs')
    pin(mask['maskArchive']['path'],mask['maskArchive']['sha256']);add(mask['maskArchive']['path'],mask['maskArchive']['sha256'])
    doc,blob=read_glb(source)
    with np.load(c['sourceNativeCorners']['path'],allow_pickle=False) as a:archive={key:a[key].copy() for key in a.files}
    raw,faces,primitive=mesh_arrays(doc,blob);local=raw.astype(float)@BASIS.T
    tc.require(np.max(abs(local[faces]-archive['positions']))<=parent['proof']['maximumPositionFloat32ErrorMetres']+1e-12,'Frozen authoritative/native source association differs')
    rho=np.linalg.norm(local[:,:2],axis=1);u=np.clip((local[:,2]-start)/(end-start),0,1);weight=rho*u**3*(10-15*u+6*u**2)
    scalar_proof=validate_radius_scalars(c['profile']['weightedSourceRadiusMaximumMetres'],float(weight.max()),k,amount)
    output=Path(output).resolve();base=tp.parents[1]/'repairs';tc.require(output.is_relative_to(base) and not output.exists(),'Fresh target-owned diagnostic repairs directory required')
    newdoc,newblob,arc,proof=bake(doc,blob,archive,mask,start,end,k)
    rounding_allowance=8*float(np.spacing(float(abs(local[local[:,2]>start]).max())))
    tc.require(proof['maximumDisplacementMetres']<=amount+rounding_allowance,'Reviewed source displacement exceeded beyond scoped8ULP subtraction/norm evaluation allowance')
    proof['sourceRadiusScalarProof']=scalar_proof
    proof['sourceDoubleDisplacementRoundingAllowanceMetres']=rounding_allowance
    output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,newdoc,newblob);corners=output/'native-corners.npz';np.savez_compressed(corners,**arc)
    actual,actualblob=read_glb(candidate);tc.require(actual==newdoc and actualblob==newblob,'Literal GLB round-trip altered source metadata/arrays')
    p,n,uv,_=raw_corners(actual,actualblob);tc.require(np.array_equal(uv,archive['uvGltf']) and actualblob[:len(blob)]==blob and actual['materials']==doc['materials'] and embedded_maps(actual,actualblob)==embedded_maps(doc,blob),'Actual source material/UV/BIN verification failed')
    # Old original authored accessors remain stored and byte-identical.
    oldattrs=primitive['attributes']
    for sem in oldattrs:tc.require(accessor(actual,actualblob,oldattrs[sem]).tobytes()==accessor(doc,blob,oldattrs[sem]).tobytes(),'Stored original attribute bytes changed')
    snapshots={};(output/'helpers').mkdir()
    for helper in helpers:
        dest=output/'helpers'/helper.name;shutil.copyfile(helper,dest);snapshots[str(helper)]={'snapshot':str(dest),'sha256':tc.sha(dest)}
    shutil.copyfile(config_path,output/'reviewed-config.json')
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'bounded-hand-wrist-stub-radial-taper',**tc.binding(tp,target,'working'),'part':'handr','joint':'rhand_g','model':tc.model(target,'handr'),'source':str(source),'sourceSha256':tc.sha(source),'sourceReceipt':str(pp),'sourceReceiptSha256':tc.sha(pp),'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'nativeCornerArchive':{'path':str(corners),'sha256':tc.sha(corners)},'attachmentWorld':H.tolist(),'sourceToAttachmentLocal':np.eye(4).tolist(),'statureApplications':0,'reflectionWorld':None,'frozenInputs':pins,'helperSnapshots':snapshots,'reviewedConfig':{'path':str(config_path),'sha256':h},'explicitDiagnosticApprovalSha256':approved_sha256,'proof':proof,'diagnosticOnly':True,'rigPilotAccepted':target['rig']['pilotAccepted'],'anatomyAccepted':False,'topologyAccepted':False,'capOwnershipAccepted':False,'connectorAccepted':False,'materialAccepted':False,'equipmentAccepted':False,'clientAccepted':False,'productionAccepted':False,'selectionMade':False,'limits':['Original9NM/doublewall geometry preserved, not accepted.','Radial-only field leaves original axial cap height/ownership unchanged; no cap-concealment/contact/motion acceptance.','Hand30 palm/finger/thumb/grip silhouette outside band exact; forearm, rig, sockets and original source generation unchanged.','Working zero-stature only; any mirror/runtime conversion is a separate reviewed step.']}
    for p,h in pins.items():pin(p,h)
    rp=output/'geometry.json';rp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return rp

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-config',type=Path,required=True);parser.add_argument('--approved-review-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();rp=execute(args.review_config,args.output,args.approved_review_sha256);print(json.dumps({'receipt':str(rp),'sha256':tc.sha(rp)}),flush=True)