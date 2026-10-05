"""Two narrowly typed selected working parents; historical back20 meanings immutable."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from mirror_stock_limb_part import reflection_between_frames,detached_affine_bake
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,write_glb
from conservative_face_selection import topology
from diagnostic_axis_radial import TOPOLOGY_KEYS
from diagnostic_thigh_proximal_one_sided import verify_receipt as verify_corrected30
from diagnostic_upper_arm_girth import verify_receipt as verify_upperarm110
KIND='target-part-diagnostic-selected-working-opposite-mirror'
OP='single-frozen-opposite-frame-reflection-of-explicit-typed-parent'
PAIRS={
 'legl':('legr','target-part-diagnostic-thigh-one-sided-proximal-backward-Y','0d9a6cb0cb6f23abeba8cb564aab795ed74a596c2b09576582e02d52ee040175',verify_corrected30),
 'bicepl':('bicepr','target-part-diagnostic-upper-arm-girth110','fe08c6e8929cca48483f3a6255fe126adfb44587bed814036f206d90b82a8d7d',verify_upperarm110)}
PENDING=('geometryAccepted','anatomyAccepted','connectorAccepted','materialAccepted','nativeAccepted','stagingAccepted','clientAccepted','productionAccepted','selectionMade')
ORDER=np.array([0,2,1])
THIGH_SERIALIZED_IDENTITY_ROWS=np.array([234,2756,4113,7931,13669,15735,15907,16267,18143,20877,20972,21677,22168,25546,26693])
def input_pin(path,h,pins):
 p=Path(path).resolve();tc.require(tc.sha(p)==h,'Frozen typed mirror input differs '+str(p));tc.require(str(p) not in pins or pins[str(p)]==h,'Conflicting true input closure');pins[str(p)]=h;return p

def validate_config(c,tp,target):
 tc.require(c.get('schemaVersion')==1 and c.get('kind')=='root-review-only-selected-working-diagnostic-mirror-config' and c.get('coordinateSpace')=='working' and c.get('diagnosticOnly') is True,'Exact new working mirror config')
 tc.require(target['identity'].get('race')=='troll' and target['identity']['gender']=='male' and target['identity']['prefix']=='pmg0','Explicit Troll male; Human/female/default guards retained')
 src=c['sourcePart'];tc.require(src in PAIRS and (c['part'],c['sourceKind'],c['sourceReceipt']['sha256'])==PAIRS[src][:3],'Only exact corrected30 thigh or upperarm110 source; no historicalback20/shin/foot aliases')
 tc.require(c['sourceJoint']==tc.PART_JOINTS[src] and c['joint']==tc.PART_JOINTS[c['part']] and c['model']==tc.model(target,c['part']),'Exact declared opposite part/joint/model')
 tc.require(Path(c['targetContract']).resolve()==Path(tp).resolve() and c['targetContractSha256']==tc.sha(tp) and c['rigRevision']==target['rig']['revision'],'Exact frozen target/rig')
 tc.require(c['statureApplications']==0 and c['sourceFieldsOrFitReapplied'] is False and c['sourceCornerPermutation']==[0,2,1] and c['tangentWReflectionFactor']==-1 and c['sourceSpecificNativeRepresentationDifferenceRepaired'] is False,'Single mirror, no fit/field/stature/native policy cleanup')
 tc.require(c['planeOriginWorld']==[0.,0.,0.] and c['planeNormalWorld']==[1.,0.,0.],'Exact X0 plane')
 H=tc.frame(target,c['sourceJoint'],'working');G=tc.frame(target,c['joint'],'working');M,R=reflection_between_frames(H,G,c['planeOriginWorld'],c['planeNormalWorld']);tc.require(np.array_equal(c['sourceAttachmentWorld'],H) and np.array_equal(c['attachmentWorld'],G) and np.array_equal(c['sourceToAttachmentLocal'],M) and np.array_equal(c['reflectionWorld'],R),'Frozen opposite-frame conjugation')
 return H,G,M,R

def validate_executor(c):
 expected=c.get('expectedExecutor');tc.require(isinstance(expected,dict) and set(expected)=={'path','sha256'},'Exact expectedExecutor pin required')
 actual=Path(__file__).resolve();tc.require(Path(expected['path']).resolve()==actual and expected['sha256']==tc.sha(actual),'Expected executor must be the executing helper with exact current SHA');return actual

def validate_approval(a,c):
 tc.require(a.get('kind')=='root-approved-selected-working-diagnostic-opposite-mirror' and a.get('reviewedBy')=='/root' and a.get('authorizeImplementationAndOneFreshExport') is True and a.get('configuration')==c,'Exact new executed parent-specific root approval')

def load_parent(c,tp,target,pins):
 review=c['actualLiteralContinuationEvidence'];input_pin(review['path'],review['sha256'],pins)
 if 'actualLiteralImportCameraNeighborProof' in c:
  support=c['actualLiteralImportCameraNeighborProof'];input_pin(support['path'],support['sha256'],pins)
 rp=input_pin(c['sourceReceipt']['path'],c['sourceReceipt']['sha256'],pins);prepared=PAIRS[c['sourcePart']][3](rp,tp,target,'working');r=prepared['receipt'];pins.update(prepared['inputs']);source=input_pin(c['sourceCandidate']['path'],c['sourceCandidate']['sha256'],pins)
 tc.require(r['part']==c['sourcePart'] and r['kind']==c['sourceKind'] and r['joint']==c['sourceJoint'] and r['candidate']==str(source) and r['candidateSha256']==c['sourceCandidate']['sha256'] and r['nativeCornerArchive']==c['sourceNativeCornerArchive'] and r['statureApplications']==0,'Exact independently verified parent association')
 ap=input_pin(c['sourceNativeCornerArchive']['path'],c['sourceNativeCornerArchive']['sha256'],pins)
 auditpath=input_pin(c['sourceIndependentAudit']['path'],c['sourceIndependentAudit']['sha256'],pins);audit=json.loads(auditpath.read_text());tc.require(audit['pass'] is True and audit['receipt']==c['sourceReceipt'] and audit['candidate']==c['sourceCandidate'] and audit['kind']==c['sourceIndependentAuditKind'],'Successful exact parent independent audit')
 closure=input_pin(audit['verifiedInputClosure']['path'],audit['verifiedInputClosure']['sha256'],pins)
 for p,h in json.loads(closure.read_text()).items():input_pin(p,h,pins)
 with np.load(ap,allow_pickle=False) as a:arc={k:a[k].copy() for k in a.files}
 doc,blob=read_glb(source);tc.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1,'Explicit one-primitive detached identity candidate');p=doc['meshes'][0]['primitives'][0];F=accessor(doc,blob,p['indices']).reshape(-1,3).astype(np.int64);rows={s:accessor(doc,blob,p['attributes'][s]) for s in ['POSITION','NORMAL','TANGENT','TEXCOORD_0']};tc.require(np.array_equal(arc['sourceTriangleIds'],np.arange(len(F))) and np.array_equal(arc['sourceCornerOrder'],np.tile([0,1,2],(len(F),1))) and np.array_equal(arc['primitiveIds'],np.zeros(len(F),int)) and np.array_equal(arc['uvGltf'],rows['TEXCOORD_0'][F]),'Exact source face/corner/archive association')
 return r,doc,blob,rows,F,arc

def mirror_archive(arc,M):
 # Current authoritative fields are reflected/permuted. Every other parent lineage field is literal LEFT history.
 out={k:v.copy() for k,v in arc.items()};out['positions']=(arc['positions']@M[:3,:3].T+M[:3,3])[:,ORDER];out['normals']=(arc['normals']@M[:3,:3].T)[:,ORDER];t=arc['tangents'].copy();t[...,:3]=t[...,:3]@M[:3,:3].T;t[...,3]*=-1;out['tangents']=t[:,ORDER]
 for k in ['uvNative','uvGltf','sourceCornerOrder']:out[k]=arc[k][:,ORDER].copy()
 for k in ['positions','normals','tangents','uvNative','uvGltf']:out['mirrorParent'+k[0].upper()+k[1:]]=arc[k].copy()
 out['mirrorParentSourceCornerOrder']=arc['sourceCornerOrder'].copy();out['mirrorParentCornerOrder']=np.tile(ORDER,(len(arc['positions']),1));return out
def proof(old,blob,new,nb,rows,F,native,H,G,M,R,source_kind):
    p=new['meshes'][0]['primitives'][0];nr={s:accessor(new,nb,p['attributes'][s]) for s in rows};nf=accessor(new,nb,p['indices']).reshape(-1,3).astype(np.int64);tc.require(np.array_equal(nf,F[:,ORDER]) and nb[:len(blob)]==blob and embedded_maps(old,blob)==embedded_maps(new,nb),'Exact winding/BIN/maps');tc.require(new['accessors'][:len(old['accessors'])]==old['accessors'] and new['bufferViews'][:len(old['bufferViews'])]==old['bufferViews'] and new['materials']==old['materials'],'Original accessor/material definitions')
    for s,aid in old['meshes'][0]['primitives'][0]['attributes'].items():tc.require(accessor(old,blob,aid,allow_normalized=True).tobytes()==accessor(new,nb,aid,allow_normalized=True).tobytes(),'Stored original '+s)
    world=rows['POSITION'].astype(float)@BASIS.T@H[:3,:3].T+H[:3,3];nw=nr['POSITION'].astype(float)@BASIS.T@G[:3,:3].T+G[:3,3];err=float(np.max(abs(nw-(world@R[:3,:3].T+R[:3,3]))));tc.require(err<4e-8,'Frozen frame world reflection placement');tc.require(nr['TEXCOORD_0'].tobytes()==rows['TEXCOORD_0'].tobytes() and np.array_equal(native['uvGltf'],nr['TEXCOORD_0'][nf]),'UV literal; no V/U repeat');tc.require(nr['TANGENT'][:,3].tobytes()==(-rows['TANGENT'][:,3]).tobytes(),'Tangent W exact reflection')
    P=rows['POSITION'];Q=nr['POSITION'];before=topology(P,F);after=topology(Q,nf)
    for k in TOPOLOGY_KEYS:tc.require(before[k]==after[k],'Introduced mirrored topology '+k)
    _,a=np.unique(P,axis=0,return_inverse=True);_,b=np.unique(Q,axis=0,return_inverse=True);tc.require(len(np.unique(np.column_stack([a,b]),axis=0))==len(np.unique(a))==len(np.unique(b)),'Coordinate weld partition changed')
    oldlocal=P.astype(float)@BASIS.T;newlocal=Q.astype(float)@BASIS.T;gn=np.cross(newlocal[nf[:,1]]-newlocal[nf[:,0]],newlocal[nf[:,2]]-newlocal[nf[:,0]]);on=np.cross(oldlocal[F[:,1]]-oldlocal[F[:,0]],oldlocal[F[:,2]]-oldlocal[F[:,0]]);expected=on@M[:3,:3].T;areas=np.linalg.norm(gn,axis=1);tc.require((areas>2e-15).all(),'Mirrored zero area');dots=np.sum(expected*gn,axis=1)/np.linalg.norm(expected,axis=1)/areas;tc.require(dots.min()>0,'Serialized reflected/winding-corrected orientation reversal')
    errors={'positions':float(np.max(abs(native['positions']-newlocal[nf]))),'normals':float(np.max(abs(native['normals']-nr['NORMAL'].astype(float)[nf]@BASIS.T)))};tt=nr['TANGENT'].astype(float).copy();tt[:,:3]=tt[:,:3]@BASIS.T;errors['tangents']=float(np.max(abs(native['tangents']-tt[nf])));sourceLocal=rows['POSITION'].astype(float)@BASIS.T;sourceN=rows['NORMAL'].astype(float)@BASIS.T;sourceT=rows['TANGENT'].astype(float).copy();sourceT[:,:3]=sourceT[:,:3]@BASIS.T
    # Subtract the exactly inherited parent bridge: reflection is forbidden from adding a policy discrepancy.
    sourceNative=native['mirrorParentPositions'];sourceNativeN=native['mirrorParentNormals'];sourceNativeT=native['mirrorParentTangents'];sourceDelta=sourceNative-sourceLocal[F];sourceDeltaN=sourceNativeN-sourceN[F];sourceDeltaT=sourceNativeT-sourceT[F];expectedDelta=(sourceDelta@M[:3,:3].T)[:,ORDER];expectedDeltaN=(sourceDeltaN@M[:3,:3].T)[:,ORDER];expectedDeltaT=sourceDeltaT.copy();expectedDeltaT[...,:3]=expectedDeltaT[...,:3]@M[:3,:3].T;expectedDeltaT[...,3]*=-1;expectedDeltaT=expectedDeltaT[:,ORDER]
    delta=native['positions']-newlocal[nf];deltaN=native['normals']-nr['NORMAL'].astype(float)[nf]@BASIS.T;deltaT=native['tangents']-tt[nf];newBridge={'positions':float(np.max(abs(delta-expectedDelta))),'normals':float(np.max(abs(deltaN-expectedDeltaN))),'tangents':float(np.max(abs(deltaT-expectedDeltaT)))};tc.require(newBridge['positions']<4e-8 and newBridge['normals']<2e-7 and newBridge['tangents']<2e-7,'New reflection bridge error beyond exact inherited parent representation')
    exception=np.isin(F[:,ORDER],THIGH_SERIALIZED_IDENTITY_ROWS) if source_kind=='target-part-diagnostic-thigh-one-sided-proximal-backward-Y' else np.zeros(F.shape,bool);ordinary=~exception;tc.require(np.max(abs(delta[ordinary]))<1e-7 and np.max(abs(deltaN[ordinary]))<2e-7 and np.max(abs(deltaT[ordinary]))<2e-7,'Strict all ordinary mirrored corner bridge');return {'beforeTopology':{k:before[k] for k in TOPOLOGY_KEYS},'afterTopology':{k:after[k] for k in TOPOLOGY_KEYS},'originalStoredArraysBINUVMaterialsMapsExact':True,'coordinateWeldPartitionBijection':True,'minimumWindingCorrectedGeometricNormalDot':float(dots.min()),'worldReflectionSerializationMaxErrorMetres':err,'authoritativeCornerBridgeMaxErrors':errors,'newReflectionBridgeErrorBeyondExactInheritedParent':newBridge,'sourceSpecificInheritedRepresentationCornerCount':int(exception.sum()),'genericBridgeToleranceWidened':False,'sourceIntersectionAndOpenSurfaceRisksInherited':True,'noExhaustiveAllPoseClientClaim':True}


def execute(approval_path,output):
 ap=Path(approval_path).resolve();a=json.loads(ap.read_text());c=a['configuration'];validate_approval(a,c);validate_executor(c);pins={};input_pin(ap,tc.sha(ap),pins);cp=input_pin(a['proposal']['path'],a['proposal']['sha256'],pins);tc.require(json.loads(cp.read_text())==c,'Exact proposed mirror association');tp=input_pin(c['targetContract'],c['targetContractSha256'],pins);target=tc.load(tp);H,G,M,R=validate_config(c,tp,target);r,doc,blob,rows,F,arc=load_parent(c,tp,target,pins)
 nd,nb,discard_f32_native,bake=detached_affine_bake(doc,blob,M,True);native=mirror_archive(arc,M);pr=proof(doc,blob,nd,nb,rows,F,native,H,G,M,R,c['sourceKind']);out=Path(output).resolve();tc.require(not out.exists(),'Fresh immutable typed mirror child')
 helpers=[Path(__file__),Path(__file__).with_name('test_diagnostic_selected_working_opposite.py')]+[Path(__file__).with_name(n) for n in ['mirror_stock_limb_part.py','diagnostic_thigh_proximal_one_sided.py','diagnostic_upper_arm_girth.py','target_contract.py','place_purposebuilt_pelvis.py','conservative_face_selection.py','diagnostic_axis_radial.py']]
 for p in helpers:input_pin(p,tc.sha(p),pins)
 if 'sourceBoundPlan' in a:input_pin(a['sourceBoundPlan']['path'],a['sourceBoundPlan']['sha256'],pins)
 out.mkdir(parents=True);candidate=out/'candidate-local.glb';write_glb(candidate,nd,nb);archive=out/'native-float64-selected-mirrored-corners.npz';np.savez_compressed(archive,**native);(out/'helpers').mkdir();snaps={}
 for p in helpers:q=out/'helpers'/p.name;shutil.copyfile(p,q);snaps[str(p.resolve())]={'path':str(q),'sha256':tc.sha(q)}
 result={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KIND,'operation':OP,'part':c['part'],'joint':c['joint'],'model':c['model'],'sourcePart':c['sourcePart'],'sourceKind':c['sourceKind'],'diagnosticOnly':True,'canonicalNativeLineage':False,'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':G.tolist(),'sourceAttachmentWorld':H.tolist(),'sourceToAttachmentLocal':M.tolist(),'reflectionWorld':R.tolist(),'sourceReceipt':c['sourceReceipt'],'sourceCandidate':c['sourceCandidate'],'parentNativeCornerArchive':c['sourceNativeCornerArchive'],'nativeCornerArchive':{'path':str(archive),'sha256':tc.sha(archive)},'rootApproval':{'path':str(ap),'sha256':tc.sha(ap)},'fieldConfiguration':c,'parentArchiveAndHistoryRetainedUnchanged':True,'nativeCornersDerivedFromAuthoritativeFloat64NotBakeArchive':True,'untransformedHistoricalArchiveFields':[k for k in arc if k not in ['positions','normals','tangents','uvNative','uvGltf','sourceCornerOrder']],'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'statureApplications':0,'sourceFieldsOrFitReapplied':False,'rigOrNeighborsChanged':False,'sourceSpecificRepresentationDifferenceRepaired':False,'bakeProof':bake,'proof':pr,'frozenInputs':pins,'helperSnapshots':snaps,'limits':['Exact parent diagnostic/final-gate status retained; one mirror is not anatomy/articulation/material/staging/native/client acceptance.','Thigh inherits the explicit15 serialized-identity/f64 continuous-field representation rows, without generic tolerance widening, cleanup or a native claim.','Original source history arrays remain literal LEFT records; only current authoritative PNT/UV/sourceCornerOrder fields mirror/permuted.','Bilateral literal shoulder/elbow/hip/knee/whole-motion review remains required before continued selection.'],**{k:False for k in PENDING}}
 rp=out/'diagnostic-selected-opposite-geometry.json';rp.write_text(json.dumps(result,indent=2)+'\n');verify_receipt(rp,tp,target);return rp

def verify_receipt(receipt_path,target_path,target,space='working'):
 path=Path(receipt_path).resolve();r=json.loads(path.read_text());tc.require(r['schemaVersion']==1 and r['kind']==KIND and r['operation']==OP and space=='working' and r['diagnosticOnly'] is True and r['canonicalNativeLineage'] is False and all(r[k] is False for k in PENDING),'Exact new unpromoted typed working mirror');tc.verify_binding(r,target_path,target,space);c=r['fieldConfiguration'];validate_executor(c);H,G,M,R=validate_config(c,target_path,target);tc.require(r['part']==c['part'] and r['joint']==c['joint'] and r['sourcePart']==c['sourcePart'] and r['sourceKind']==c['sourceKind'] and r['model']==c['model'] and r['statureApplications']==0 and r['sourceFieldsOrFitReapplied'] is False and r['sourceSpecificRepresentationDifferenceRepaired'] is False and np.array_equal(r['candidateToAttachmentLocal'],np.eye(4)) and np.array_equal(r['attachmentWorld'],G),'Single reflection without promotion/field repeat')
 pins={}
 for p,h in r['frozenInputs'].items():input_pin(p,h,pins)
 validate_approval(json.loads(Path(r['rootApproval']['path']).read_text()),c);parent,doc,blob,rows,F,arc=load_parent(c,target_path,target,pins);input_pin(r['candidate'],r['candidateSha256'],pins);input_pin(r['nativeCornerArchive']['path'],r['nativeCornerArchive']['sha256'],pins);nd,nb=read_glb(r['candidate']);ed,eb,discard,bake=detached_affine_bake(doc,blob,M,True);tc.require(nd==ed and nb==eb,'Exact mirror arrays/active indices/storage/material/BIN')
 native=mirror_archive(arc,M)
 with np.load(r['nativeCornerArchive']['path'],allow_pickle=False) as z:tc.require(set(z.files)==set(native) and all(z[k].dtype==v.dtype and z[k].shape==v.shape and z[k].tobytes()==v.tobytes() for k,v in native.items()),'All currentf64 and literal historical/source-corner arrays exact')
 tc.require(proof(doc,blob,nd,nb,rows,F,native,H,G,M,R,c['sourceKind'])==r['proof'],'Mirror/decode/representation proof differs');pins[str(path)]=tc.sha(path);return {'receipt':r,'candidate':Path(r['candidate']),'inputs':pins,'primitiveInventory':[{'primitive':0,'part':r['part'],'sourcePart':r['sourcePart'],'faces':len(F),'material':nd['meshes'][0]['primitives'][0]['material']}]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rp=execute(a.approval,a.output);print(json.dumps({'receipt':str(rp),'sha256':tc.sha(rp)}),flush=True)


