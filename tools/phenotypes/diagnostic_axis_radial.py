"""Troll-only unaccepted constant .85 leg cross-section diagnostic, axial span unchanged."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from target_part_pipeline import verify_source_receipt
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,write_glb
from conservative_face_selection import mesh_arrays,topology
PART_FRAMES={'legl':('lthigh_g','lshin_g'),'shinl':('lshin_g','lfoot_g')}
TOPOLOGY_KEYS=('referencedSerializedVertices','exactPositionVertices','faces','boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings','zeroAreaFaces','nonmanifoldVertexLinks','components','eulerCharacteristic')
def radial_matrix(origin,distal,factor=.85):
    tc.require(type(factor) is float and factor==.85,'Exact reviewed .85 factor required')
    origin=np.asarray(origin,float);distal=np.asarray(distal,float)
    tc.require(origin.shape==distal.shape==(3,) and np.isfinite(origin).all() and np.isfinite(distal).all(),'Finite explicit joint origins required')
    d=distal-origin;length=np.linalg.norm(d);tc.require(length>1e-8,'Distinct proximal/distal joint origins required');d/=length
    J=factor*(np.eye(3)-np.outer(d,d))+np.outer(d,d);M=np.eye(4);M[:3,:3]=J;M[:3,3]=origin-J@origin
    return M,d,length

def transform_positions(p,M):
    p=np.asarray(p,float);tc.require(p.ndim==2 and p.shape[1]==3 and np.isfinite(p).all(),'Finite positions required')
    return p@M[:3,:3].T+M[:3,3]

def transport(n,t,J):
    n=np.asarray(n,float);t=np.asarray(t,float);J=np.asarray(J,float)
    tc.require(n.ndim==2 and n.shape[1]==3 and t.shape==(len(n),4) and J.shape==(3,3),'Matching N/T and constant Jacobian required')
    tc.require(np.isfinite(n).all() and np.isfinite(t).all() and np.isfinite(J).all() and np.linalg.det(J)>0,'Finite proper positive Jacobian required')
    nl=np.linalg.norm(n,axis=1);tl=np.linalg.norm(t[:,:3],axis=1)
    tc.require(np.all(nl>1e-8) and np.all(tl>1e-8) and np.all(abs(t[:,3])==1),'Valid active normal/tangent/W required')
    nn=n@np.linalg.inv(J);nn*= (nl/np.linalg.norm(nn,axis=1))[:,None];unit=nn/nl[:,None]
    tt=t.copy();direction=t[:,:3]@J.T;direction-=np.sum(direction*unit,axis=1)[:,None]*unit
    tc.require(np.all(np.linalg.norm(direction,axis=1)>1e-8),'Degenerate projected tangent rejected')
    tt[:,:3]=direction*(tl/np.linalg.norm(direction,axis=1))[:,None]
    return nn,tt

def append_attributes(doc,blob,newrows):
    result=copy.deepcopy(doc);payload=bytearray(blob)
    for semantic,values in newrows.items():
        values=np.asarray(values,dtype='<f4');tc.require(np.isfinite(values).all(),'Serialization overflow rejected')
        payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(values.tobytes());payload.extend(b'\0'*(-len(payload)%4))
        result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':values.nbytes});a={'bufferView':len(result['bufferViews'])-1,'componentType':5126,'count':len(values),'type':'VEC'+str(values.shape[1])}
        if semantic=='POSITION':a.update(min=values.min(0).astype(float).tolist(),max=values.max(0).astype(float).tolist())
        result['accessors'].append(a);result['meshes'][0]['primitives'][0]['attributes'][semantic]=len(result['accessors'])-1
    result['buffers'][0]['byteLength']=len(payload)
    return result,bytes(payload)

def verify_discrete(oldp,newp,faces):
    before=topology(oldp,faces);after=topology(newp,faces)
    for key in TOPOLOGY_KEYS:tc.require(before[key]==after[key],'Introduced discrete topology defect/change '+key)
    old=oldp.astype(float)[faces];new=newp.astype(float)[faces];oc=np.cross(old[:,1]-old[:,0],old[:,2]-old[:,0]);nc=np.cross(new[:,1]-new[:,0],new[:,2]-new[:,0]);a=np.linalg.norm(oc,axis=1);b=np.linalg.norm(nc,axis=1)
    tc.require(np.all(a>2e-15) and np.all(b>2e-15),'Zero/degenerate source or descendant face rejected')
    dot=np.sum(oc*nc,axis=1)/(a*b);tc.require(np.all(dot>0),'Serialized face inversion rejected')
    return before,after,float(dot.min())

def execute(config_path,output):
    config_path=Path(config_path).resolve();c=json.loads(config_path.read_text(encoding='utf-8-sig'))
    fields={'schemaVersion','kind','diagnosticOnly','part','coordinateSpace','targetContract','targetContractSha256','rigRevision','parentReceipt','parentReceiptSha256','parentCandidate','parentCandidateSha256','factor','originWorld','distalWorld','protectedInputs'}
    tc.require(set(c)==fields and c['schemaVersion']==1 and c['kind']=='troll-left-leg-axis-radial-diagnostic-config' and c['diagnosticOnly'] is True,'Exact separate diagnostic configuration required')
    part=c['part'];tc.require(part in PART_FRAMES and c['coordinateSpace']=='working','Only declared LEFT thigh/shin working diagnostic allowed')
    output=Path(output).resolve();tc.require(not output.exists(),'Fresh immutable diagnostic output required')
    tp=Path(c['targetContract']).resolve();tc.require(tc.sha(tp)==c['targetContractSha256'],'Target pin changed');target=tc.load(tp)
    tc.require(target['identity']['race']=='troll' and target['identity']['gender']=='male' and target['identity']['prefix']=='pmg0','Troll male declared identity required');tc.require(target['rig']['revision']==c['rigRevision'],'Frozen revision differs')
    parentpath=Path(c['parentReceipt']).resolve();source=Path(c['parentCandidate']).resolve();tc.require(tc.sha(parentpath)==c['parentReceiptSha256'] and tc.sha(source)==c['parentCandidateSha256'],'Exact fitted parent pins changed')
    parent=verify_source_receipt(source,parentpath,tp,target,part,'working');tc.require(parent['operation']=='fit' and parent['reflectionWorld'] is None,'Untreated positive-uniform actual fit only; cumulative/reflected geometry rejected')
    proximal,distal=PART_FRAMES[part];H=tc.frame(target,proximal,'working');K=tc.frame(target,distal,'working');tc.require(np.array_equal(np.asarray(parent['attachmentWorld']),H),'Parent attachment differs')
    origin=H[:3,3];end=K[:3,3];tc.require(np.array_equal(c['originWorld'],origin) and np.array_equal(c['distalWorld'],end),'Exact frozen joint origins required')
    Mworld,d,L=radial_matrix(origin,end,c['factor']);Mlocal=np.linalg.inv(H)@Mworld@H;J=Mlocal[:3,:3]
    pins={}
    def add(p,h):
        p=Path(p).resolve();key=str(p);tc.require(key not in pins or pins[key]==h,'Conflicting pin');tc.require(tc.sha(p)==h,'Frozen diagnostic input changed '+key);pins[key]=h
    for p,h in parent['frozenInputs'].items():add(p,h)
    for p,h in c['protectedInputs'].items():add(p,h)
    for p in [config_path,tp,parentpath,source]:add(p,tc.sha(p))
    ap=Path(parent['nativeCornerArchive']['path']);add(ap,parent['nativeCornerArchive']['sha256'])
    helpers=[Path(__file__).resolve()]+[Path(__file__).with_name(n) for n in ['target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','conservative_face_selection.py']]
    for p in helpers:add(p,tc.sha(p))
    doc,blob=read_glb(source);praw,faces,primitive=mesh_arrays(doc,blob);tc.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and doc['scenes']==[{'nodes':[0]}] and len(doc['buffers'])==1 and not doc['buffers'][0].get('uri'),'Exact embedded identity fitted parent required')
    attrs=primitive['attributes'];tc.require(set(attrs) in ({'POSITION','NORMAL','TANGENT','TEXCOORD_0'},{'POSITION','NORMAL','TANGENT','TEXCOORD_0','COLOR_0'}),'Declared P/N/T/UV only, optional original color')
    rows={s:accessor(doc,blob,attrs[s]) for s in ['POSITION','NORMAL','TANGENT','TEXCOORD_0']};tc.require(all(v.dtype==np.dtype('<f4') and len(v)==len(praw) and np.isfinite(v).all() for v in rows.values()),'Finite equal float32 attribute counts required')
    active=np.zeros(len(praw),bool);active[np.unique(faces)]=True;local=praw.astype(float)@BASIS.T;nlocal=rows['NORMAL'].astype(float)@BASIS.T;tlocal=rows['TANGENT'].astype(float).copy();tlocal[:,:3]=tlocal[:,:3]@BASIS.T
    proposed=transform_positions(local,Mlocal);nn,tt=transport(nlocal[active],tlocal[active],J)
    newrows={s:rows[s].copy() for s in ['POSITION','NORMAL','TANGENT']};newrows['POSITION'][active]=(proposed[active]@BASIS).astype('<f4');newrows['NORMAL'][active]=(nn@BASIS).astype('<f4');rawt=tt.copy();rawt[:,:3]=rawt[:,:3]@BASIS;newrows['TANGENT'][active]=rawt.astype('<f4')
    before,after,mindot=verify_discrete(praw,newrows['POSITION'],faces)
    with np.load(ap,allow_pickle=False) as archive:arc={key:archive[key].copy() for key in archive.files}
    tc.require(np.array_equal(arc['sourceTriangleIds'],np.arange(len(faces))) and np.array_equal(arc['sourceCornerOrder'],np.tile([0,1,2],(len(faces),1))) and np.array_equal(arc['primitiveIds'],np.zeros(len(faces),dtype=int)),'Exhaustive original face/corner association required')
    tc.require(arc['positions'].shape==(len(faces),3,3) and arc['normals'].shape==arc['positions'].shape and arc['tangents'].shape==(len(faces),3,4),'Original authoritative P/N/T corners required')
    tc.require(np.max(abs(arc['positions']-local[faces]))<=parent['proof']['maximumPositionFloat32ErrorMetres']+1e-14 and np.max(abs(arc['normals']-nlocal[faces]))<=parent['proof']['maximumNormalFloat32Error']+1e-14 and np.max(abs(arc['tangents']-tlocal[faces]))<2e-7 and np.array_equal(arc['uvGltf'],rows['TEXCOORD_0'][faces]),'Authoritative parent P/N/T/UV association rejected')
    uvnative=rows['TEXCOORD_0'].astype(float).copy();uvnative[:,1]=1-uvnative[:,1];tc.require(np.array_equal(arc['uvNative'],uvnative[faces]),'Native V exactly once required')
    arc['positions']=transform_positions(arc['positions'].reshape(-1,3),Mlocal).reshape(len(faces),3,3);an,at=transport(arc['normals'].reshape(-1,3),arc['tangents'].reshape(-1,4),J);arc['normals']=an.reshape(len(faces),3,3);arc['tangents']=at.reshape(len(faces),3,4)
    arc.update(radialParentFaces=faces,radialActiveVertexMask=active,radialWorldMatrix=Mworld,radialLocalMatrix=Mlocal,radialParentRawPositions=praw,radialParentRawNormals=rows['NORMAL'],radialParentRawTangents=rows['TANGENT'])
    newdoc,newblob=append_attributes(doc,blob,newrows);output.mkdir(parents=True);candidate=output/'candidate-local.glb';write_glb(candidate,newdoc,newblob);native=output/'native-corners.npz';np.savez_compressed(native,**arc)
    actual,ab=read_glb(candidate);aa=actual['meshes'][0]['primitives'][0]['attributes'];tc.require(ab[:len(blob)]==blob and embedded_maps(actual,ab)==embedded_maps(doc,blob),'Original BIN/maps changed')
    restored=copy.deepcopy(actual);restored['meshes'][0]['primitives'][0]['attributes']=attrs;restored['accessors']=restored['accessors'][:-3];restored['bufferViews']=restored['bufferViews'][:-3];restored['buffers'][0]['byteLength']=doc['buffers'][0]['byteLength'];tc.require(restored==doc,'Undeclared scene/index/map/material/accessor metadata change')
    for s,old in rows.items():tc.require(accessor(actual,ab,attrs[s]).tobytes()==old.tobytes(),'Stored original attribute accessor changed')
    for s,values in newrows.items():tc.require(accessor(actual,ab,aa[s]).tobytes()==values.tobytes() and values[~active].tobytes()==rows[s][~active].tobytes(),'Actual transformed array or unused rows changed')
    newlocal=newrows['POSITION'].astype(float)@BASIS.T;world=transform_positions(local,H);newworld=transform_positions(newlocal,H);oldaxis=(world-origin)@d;newaxis=(newworld-origin)@d;exactworld=transform_positions(world,Mworld)
    tc.require(np.max(abs(newworld-exactworld))<4e-8 and np.max(abs(newaxis-oldaxis))<4e-8,'Serialized axis/world precision exceeded')
    (output/'helpers').mkdir();snapshots={}
    for p in helpers:dest=output/'helpers'/p.name;shutil.copyfile(p,dest);snapshots[str(p)]={'path':str(dest),'sha256':tc.sha(dest)}
    shutil.copyfile(config_path,output/'config.json')
    receipt={'schemaVersion':1,'kind':'troll-left-leg-axis-radial-diagnostic','diagnosticOnly':True,**tc.binding(tp,target,'working'),'part':part,'joint':proximal,'model':tc.model(target,part),'parentGeometryReceipt':str(parentpath),'parentGeometryReceiptSha256':tc.sha(parentpath),'parentCandidate':str(source),'parentCandidateSha256':tc.sha(source),'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'nativeCornerArchive':{'path':str(native),'sha256':tc.sha(native)},'attachmentWorld':H.tolist(),'statureApplications':0,'factor':c['factor'],'axisOriginWorld':origin.tolist(),'axisDistalWorld':end.tolist(),'axisUnitWorld':d.tolist(),'jointSpanMetres':L,'worldAffine':Mworld.tolist(),'localAffine':Mlocal.tolist(),'frozenInputs':pins,'helperSnapshots':snapshots,'proof':{'originalStoredAccessorsAndBINprefixExact':True,'originalUVMapsMaterialsIndicesCornersExact':True,'unusedVertexRowsUnchangedNotAcceptedActive':True,'beforeTopology':before,'afterTopology':after,'minimumSerializedFaceNormalDot':mindot,'maximumWorldAffineSerializationErrorMetres':float(np.max(abs(newworld-exactworld))),'maximumAxialSerializationErrorMetres':float(np.max(abs(newaxis-oldaxis))),'projectedCoverageBeforeMetres':[-float(oldaxis.min()),float(oldaxis.max())-L],'projectedCoverageAfterMetres':[-float(newaxis.min()),float(newaxis.max())-L],'maximumNativePSerializationErrorMetres':float(np.max(abs(newlocal[faces]-arc['positions']))),'maximumNativeNSerializationError':float(np.max(abs((newrows['NORMAL'].astype(float)@BASIS.T)[faces]-arc['normals']))),'normalInverseTransposeMagnitudePreserved':True,'tangentLinearThenGramSchmidtMagnitudeWPreserved':True,'positiveDeterminant':float(np.linalg.det(J)),'continuousIntersectionPolicy':'One globally invertible affine map preserves existing same-part intersections in exact arithmetic; finite float32 residual reported separately, not a global numerical intersection proof.','activeVertices':int(active.sum()),'unusedVertices':int((~active).sum())},'sourceMastersChanged':False,'rigOrNeighborsChanged':False,'mirrorOrFitRepeated':False,'axisLengthChanged':False,'topologyAccepted':False,'connectorAccepted':False,'materialAccepted':False,'anatomyAccepted':False,'clientAccepted':False,'productionAccepted':False,'selectionMade':False}
    for p,h in pins.items():tc.require(tc.sha(p)==h,'Input changed during execute '+p)
    rp=output/'diagnostic.json';rp.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return rp

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=execute(a.config,a.output);print(json.dumps({'receipt':str(r),'sha256':tc.sha(r)}),flush=True)

