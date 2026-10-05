"""Exact shin85 parent plus ONE shin90 transverse child; lengths/old guards literal."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from diagnostic_axis_radial import transform_positions,transport,append_attributes,TOPOLOGY_KEYS
from diagnostic_opposite_lower_limb import load_parent as load_shin85
from place_purposebuilt_pelvis import BASIS,accessor,read_glb,write_glb,embedded_maps
from conservative_face_selection import topology
KIND='target-part-diagnostic-shin-girth90-after85'
OP='constant-frozen-knee-ankle-axis-additional-transverse-scale90'
PARENT_SHA='dd165ebefefe72901c41cd7892def5b10f762cc082491e832f2cda9bd215729b'
RECOVERY_SHA='6ff643fa8f2adf6f5bfaff30b928470dd8c5f1b9d064dfb747a2917a6f305fa4'
PENDING=('geometryAccepted','anatomyAccepted','topologyAccepted','connectorAccepted','materialAccepted','nativeAccepted','stagingAccepted','clientAccepted','productionAccepted','selectionMade')
def pin(p,h,pins):
 p=Path(p).resolve();tc.require(tc.sha(p)==h,'Frozen shin90 input differs '+str(p));tc.require(str(p) not in pins or pins[str(p)]==h,'Conflicting current input');pins[str(p)]=h;return p

def matrix(a,b,factor=.90):
 tc.require(type(factor) is float and factor==.90,'Only exact additional shin90 factor; no85/XYZ/110 alias');a=np.asarray(a,float);b=np.asarray(b,float);tc.require(a.shape==b.shape==(3,) and np.isfinite(a).all() and np.isfinite(b).all(),'Finite frozen knee/ankle');d=b-a;L=float(np.linalg.norm(d));tc.require(L>1e-8,'Distinct knee/ankle');d/=L;J=.90*np.eye(3)+.10*np.outer(d,d);M=np.eye(4);M[:3,:3]=J;M[:3,3]=a-J@a;return M,d,L

def validate_executor(c):
 e=c.get('expectedExecutor');p=Path(__file__).resolve();tc.require(isinstance(e,dict) and set(e)=={'path','sha256'} and Path(e['path']).resolve()==p and e['sha256']==tc.sha(p),'Expected executor is exact executing shin90 helper');return p

def validate_config(c,tp,target):
 exact={'schemaVersion':1,'kind':'root-review-only-shin-girth90-after85-config','coordinateSpace':'working','diagnosticOnly':True,'part':'shinl','joint':'lshin_g','sourcePart':'shinl','sourceJoint':'lshin_g','sourceKind':'troll-left-leg-axis-radial-diagnostic','factor':.90,'axialFactor':1.,'parentFactor':.85,'effectiveOriginalDonorRadialFactor':.765,'statureApplications':0,'factor85OrFitReapplied':False,'uniformXYZScaleUsed':False,'terminalTaperOrWindowUsed':False,'mirrorApplied':False,'rigAndKneeAnkleAnchorsChanged':False}
 tc.require(all(c.get(k)==v for k,v in exact.items()) and c['sourceReceipt']['sha256']==PARENT_SHA,'Exact requested shin85 plus90 girth-only recipe')
 tc.require(target['identity'].get('race')=='troll' and target['identity']['gender']=='male' and target['identity']['prefix']=='pmg0','Only Troll male working target')
 tc.require(Path(c['targetContract']).resolve()==Path(tp).resolve() and c['targetContractSha256']==tc.sha(tp) and c['rigRevision']==target['rig']['revision'] and c['model']==tc.model(target,'shinl'),'Exact target revision/resource')
 H=tc.frame(target,'lshin_g','working');K=tc.frame(target,'lfoot_g','working');M,d,L=matrix(H[:3,3],K[:3,3],c['factor']);ML=np.linalg.inv(H)@M@H
 tc.require(np.array_equal(c['attachmentWorld'],H) and np.array_equal(c['axisOriginWorld'],H[:3,3]) and np.array_equal(c['axisDistalWorld'],K[:3,3]) and np.array_equal(c['axisUnitWorld'],d) and c['jointSpanMetres']==L and np.array_equal(c['worldAffine'],M) and np.array_equal(c['localAffine'],ML),'Frozen knee-ankle axis and exact constant SPD field')
 return H,M,ML,d,L

def validate_approval(a,c):
 tc.require(a.get('kind')=='root-approved-shin-girth90-after85-diagnostic' and a.get('reviewedBy')=='/root' and a.get('authorizeImplementationAndOneFreshExport') is True and a.get('configuration')==c,'Exact root shin90 approval')

def source(c,tp,target,pins):
 authority=c['historicalRecoveryAuthority'];tc.require(authority['sha256']==RECOVERY_SHA,'Exact existing two-file historical recovery authority');p=pin(authority['path'],authority['sha256'],pins);old=json.loads(p.read_text());aliases=c['historicalExecutedSourceRecoveries'];tc.require(aliases==old['historicalExecutedSourceRecoveries'] and {Path(k).name for k in aliases}=={'pose_preview.py','pose_preview_target_parts.py'} and len(aliases)==2,'Only exact two historical executed renderer snapshots')
 for p,h in c['protectedNeighborInputs'].items():pin(p,h,pins)
 for k in ['humanDirection','sourceReceipt','sourceCandidate','sourceNativeCornerArchive']:pin(c[k]['path'],c[k]['sha256'],pins)
 r,doc,blob,rows,F,arc=load_shin85(c,tp,target,pins);tc.require(r['part']=='shinl' and tc.sha(c['sourceReceipt']['path'])==PARENT_SHA,'Exact selected LEFTshin85 actual parent')
 return r,doc,blob,rows,F,arc

def mapped_rows(rows,F,ML):
 active=np.zeros(len(rows['POSITION']),bool);active[np.unique(F)]=True;result={s:rows[s].copy() for s in ['POSITION','NORMAL','TANGENT']};p=rows['POSITION'].astype(float)@BASIS.T;n=rows['NORMAL'][active].astype(float)@BASIS.T;t=rows['TANGENT'][active].astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T
 nn,tt=transport(n,t,ML[:3,:3]);result['POSITION'][active]=(transform_positions(p[active],ML)@BASIS).astype('<f4');result['NORMAL'][active]=(nn@BASIS).astype('<f4');tt[:,:3]=tt[:,:3]@BASIS;result['TANGENT'][active]=tt.astype('<f4')
 for s,v in result.items():tc.require(np.isfinite(v).all() and v[~active].tobytes()==rows[s][~active].tobytes(),'Unused original stored rows exact; finite activePNT')
 tc.require(result['TANGENT'][:,3].tobytes()==rows['TANGENT'][:,3].tobytes(),'AuthoredW unchanged');return result,active

def native_child(arc,ML):
 out={k:v.copy() for k,v in arc.items()};p,n,t=arc['positions'],arc['normals'],arc['tangents'];out.update(shin90ParentPositions=p.copy(),shin90ParentNormals=n.copy(),shin90ParentTangents=t.copy());out['positions']=transform_positions(p.reshape(-1,3),ML).reshape(p.shape);nn,tt=transport(n.reshape(-1,3),t.reshape(-1,4),ML[:3,:3]);out['normals']=nn.reshape(n.shape);out['tangents']=tt.reshape(t.shape);return out

def discrete(P,Q,F,H,M,d,L):
 before=topology(P,F);after=topology(Q,F)
 for k in TOPOLOGY_KEYS:tc.require(before[k]==after[k],'Introduced shin90 topology '+k)
 _,i=np.unique(P,axis=0,return_inverse=True);_,j=np.unique(Q,axis=0,return_inverse=True);tc.require(len(np.unique(np.c_[i,j],axis=0))==len(np.unique(i))==len(np.unique(j)),'Coordinate weld partition bijection')
 p=transform_positions(P.astype(float)@BASIS.T,H);q=transform_positions(Q.astype(float)@BASIS.T,H);active=np.unique(F);a=H[:3,3];x=(p-a)@d;y=(q-a)@d;r=p-a-x[:,None]*d;s=q-a-y[:,None]*d;ideal=transform_positions(p,M);we=float(np.max(abs(q[active]-ideal[active])));ae=float(np.max(abs(y[active]-x[active])));re=float(np.max(abs(s[active]-.90*r[active])));tc.require(we<4e-8 and ae<4e-8 and re<6e-8,'Strict serialized world/axial/radial correspondence')
 A=p[F];B=q[F];on=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]);gn=np.cross(B[:,1]-B[:,0],B[:,2]-B[:,0]);expected=np.linalg.det(M[:3,:3])*(on@np.linalg.inv(M[:3,:3]));area=np.linalg.norm(gn,axis=1);tc.require((area>2e-15).all(),'No new zero-area face');dot=np.sum(expected*gn,axis=1)/np.linalg.norm(expected,axis=1)/area;tc.require(dot.min()>.9999,'Actual serialized affine-cofactor winding proof')
 return {'beforeTopology':{k:before[k] for k in TOPOLOGY_KEYS},'afterTopology':{k:after[k] for k in TOPOLOGY_KEYS},'maximumWorldSerializationErrorMetres':we,'maximumAxialSerializationErrorMetres':ae,'maximumRadialContourHomothetyErrorMetres':re,'minimumSerializedCofactorExpectedDot':float(dot.min()),'parentProjectedConnectorCoverageMetres':[-float(x[active].min()),float(x[active].max())-L],'childProjectedConnectorCoverageMetres':[-float(y[active].min()),float(y[active].max())-L],'positiveConstantJacobianDeterminant':float(np.linalg.det(M[:3,:3])),'noUnintendedShelvesGuard':{'sourceMatchedContourVectorsChecked':len(active),'allAxialStationsSameRadialFactor':.90,'axialFactor':1.,'terminalWindowOrTaperUsed':False,'samePartAffineSurfaceCorrespondence':True,'actualKneeAnkleLiteralReviewStillRequired':True,'clientAcceptanceClaim':False}}

def verify_storage(od,ob,nd,nb,rows):
 tc.require(nb[:len(ob)]==ob and embedded_maps(nd,nb)==embedded_maps(od,ob),'Original BIN/maps exact');restore=copy.deepcopy(nd);restore['meshes'][0]['primitives'][0]['attributes']=od['meshes'][0]['primitives'][0]['attributes'];restore['accessors']=restore['accessors'][:-3];restore['bufferViews']=restore['bufferViews'][:-3];restore['buffers'][0]['byteLength']=od['buffers'][0]['byteLength'];tc.require(restore==od,'Original indices/corners/UV/material/accessor/nodes exact')
 for s,v in rows.items():tc.require(accessor(nd,nb,nd['meshes'][0]['primitives'][0]['attributes'][s]).tobytes()==v.tobytes(),'Exact active shin90 PNT')

def execute(approval_path,output):
 ap=Path(approval_path).resolve();a=json.loads(ap.read_text());c=a['configuration'];validate_approval(a,c);validate_executor(c);pins={};pin(ap,tc.sha(ap),pins);cp=pin(a['proposal']['path'],a['proposal']['sha256'],pins);tc.require(json.loads(cp.read_text())==c,'Exact approved configuration');tp=pin(c['targetContract'],c['targetContractSha256'],pins);target=tc.load(tp);H,M,ML,d,L=validate_config(c,tp,target);r,doc,blob,rows,F,arc=source(c,tp,target,pins);out=Path(output).resolve();tc.require(not out.exists(),'Fresh immutable shin90 child');newrows,active=mapped_rows(rows,F,ML)
 mask=pin(c['exactRAMArrays']['path'],c['exactRAMArrays']['sha256'],pins)
 with np.load(mask,allow_pickle=False) as z:tc.require(np.array_equal(z['parentFaces'],F) and np.array_equal(z['activeAccessorRows'],np.flatnonzero(active)) and all(z[s].tobytes()==v.tobytes() for s,v in newrows.items()),'Exact reviewed RAM array/mask')
 proof=discrete(rows['POSITION'],newrows['POSITION'],F,H,M,d,L);native=native_child(arc,ML);helpers=[Path(__file__),Path(__file__).with_name('test_diagnostic_shin_girth90.py')]+[Path(__file__).with_name(k) for k in ['diagnostic_opposite_lower_limb.py','diagnostic_axis_radial.py','diagnostic_thigh_proximal_back.py','target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','conservative_face_selection.py']]
 for p in helpers:pin(p,tc.sha(p),pins)
 if 'sourceBoundPlan' in a:pin(a['sourceBoundPlan']['path'],a['sourceBoundPlan']['sha256'],pins)
 out.mkdir(parents=True);nd,nb=append_attributes(doc,blob,newrows);candidate=out/'candidate-local.glb';write_glb(candidate,nd,nb);archive=out/'native-float64-shin90-corners.npz';np.savez_compressed(archive,**native);(out/'helpers').mkdir();snaps={}
 for p in helpers:q=out/'helpers'/p.name;shutil.copyfile(p,q);snaps[str(p.resolve())]={'path':str(q),'sha256':tc.sha(q)}
 receipt={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KIND,'operation':OP,'part':'shinl','joint':'lshin_g','model':tc.model(target,'shinl'),'diagnosticOnly':True,'canonicalNativeLineage':False,'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':H.tolist(),'sourceReceipt':c['sourceReceipt'],'sourceCandidate':c['sourceCandidate'],'parentNativeCornerArchive':r['nativeCornerArchive'],'nativeCornerArchive':{'path':str(archive),'sha256':tc.sha(archive)},'rootApproval':pin_record(ap),'fieldConfiguration':c,'factor':.90,'parentFactor':.85,'effectiveOriginalDonorRadialFactor':.765,'axialFactor':1.,'axisUnitWorld':d.tolist(),'jointSpanMetres':L,'worldAffine':M.tolist(),'localAffine':ML.tolist(),'statureApplications':0,'factor85OrFitReapplied':False,'uniformXYZScaleUsed':False,'terminalTaperOrWindowUsed':False,'mirrorApplied':False,'rigOrNeighborsChanged':False,'activeVertices':int(active.sum()),'unusedVertices':int((~active).sum()),'faces':len(F),'proof':proof,'frozenInputs':pins,'helperSnapshots':snaps,'limits':['Exact additional90% transverse child from85%; no prior85/fit/runtime/stature repetition.','Original donor open/nonmanifold/anatomy/material risks inherited; source histories and stored original BIN remain recoverable.','Affine source-contour equivalence excludes a station window; actual knee/ankle connections and bilateral/client/material/native review remain pending.'],**{k:False for k in PENDING}};rp=out/'diagnostic-shin-girth90-geometry.json';rp.write_text(json.dumps(receipt,indent=2)+'\n');verify_receipt(rp,tp,target);return rp

def pin_record(p):return {'path':str(Path(p).resolve()),'sha256':tc.sha(p)}

def verify_receipt(receipt_path,target_path,target,space='working'):
 path=Path(receipt_path).resolve();r=json.loads(path.read_text());tc.require(r['schemaVersion']==1 and r['kind']==KIND and r['operation']==OP and space=='working' and r['diagnosticOnly'] is True and r['canonicalNativeLineage'] is False and all(r[k] is False for k in PENDING),'Exact pending typed shin90 working child');tc.verify_binding(r,target_path,target,space);c=r['fieldConfiguration'];validate_executor(c);H,M,ML,d,L=validate_config(c,target_path,target);tc.require(r['part']=='shinl' and r['joint']=='lshin_g' and r['model']==tc.model(target,'shinl') and r['factor']==.90 and r['parentFactor']==.85 and r['effectiveOriginalDonorRadialFactor']==.765 and r['axialFactor']==1. and r['statureApplications']==0 and r['factor85OrFitReapplied'] is False and r['uniformXYZScaleUsed'] is False and r['terminalTaperOrWindowUsed'] is False and r['mirrorApplied'] is False and r['rigOrNeighborsChanged'] is False and np.array_equal(r['candidateToAttachmentLocal'],np.eye(4)) and np.array_equal(r['attachmentWorld'],H),'Single90 field without promotion or anchor repeat');pins={}
 for p,h in r['frozenInputs'].items():pin(p,h,pins)
 a=json.loads(Path(r['rootApproval']['path']).read_text());validate_approval(a,c);parent,doc,blob,rows,F,arc=source(c,target_path,target,pins);pin(r['candidate'],r['candidateSha256'],pins);pin(r['nativeCornerArchive']['path'],r['nativeCornerArchive']['sha256'],pins);nd,nb=read_glb(r['candidate']);newrows,active=mapped_rows(rows,F,ML);verify_storage(doc,blob,nd,nb,newrows);ea=native_child(arc,ML)
 with np.load(r['nativeCornerArchive']['path'],allow_pickle=False) as z:tc.require(set(z.files)==set(ea) and all(z[k].dtype==v.dtype and z[k].shape==v.shape and z[k].tobytes()==v.tobytes() for k,v in ea.items()),'All authoritative currentPNT and historical/source-corner arrays exact')
 tc.require(discrete(rows['POSITION'],newrows['POSITION'],F,H,M,d,L)==r['proof'],'Required axis/contour/cofactor/topology proof');pins[str(path)]=tc.sha(path);return {'receipt':r,'candidate':Path(r['candidate']),'inputs':pins,'primitiveInventory':[{'primitive':0,'part':'shinl','material':nd['meshes'][0]['primitives'][0]['material'],'faces':len(F),'activeVertices':int(active.sum())}]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rp=execute(a.approval,a.output);print(json.dumps(pin_record(rp)),flush=True)
