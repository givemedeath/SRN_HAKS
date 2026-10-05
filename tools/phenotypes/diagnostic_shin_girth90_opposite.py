"""Single RIGHTshin mirror of exact approved LEFTshin90-after85; prior types immutable."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from diagnostic_shin_girth90 import verify_receipt as verify_left
from diagnostic_selected_working_opposite import mirror_archive,proof
from mirror_stock_limb_part import reflection_between_frames,detached_affine_bake
from place_purposebuilt_pelvis import read_glb,write_glb,accessor
KIND='target-part-diagnostic-shin-girth90-after85-opposite-mirror'
OP='single-frozen-opposite-frame-shin90-reflection'
PARENT_SHA='1e141fc3c64aa0df228c2f3cb3f589c60e267445ea20318936a857373309420b'
PARENT_KIND='target-part-diagnostic-shin-girth90-after85'
PENDING=('geometryAccepted','anatomyAccepted','topologyAccepted','connectorAccepted','materialAccepted','nativeAccepted','stagingAccepted','clientAccepted','productionAccepted','selectionMade')
def pin(p,h,pins):
 p=Path(p).resolve();tc.require(tc.sha(p)==h,'Frozen shin90 opposite input differs '+str(p));tc.require(str(p) not in pins or pins[str(p)]==h,'Conflicting pin');pins[str(p)]=h;return p

def validate_executor(c):
 p=Path(__file__).resolve();e=c.get('expectedExecutor');tc.require(isinstance(e,dict) and set(e)=={'path','sha256'} and Path(e['path']).resolve()==p and e['sha256']==tc.sha(p),'Exact executing RIGHTshin90 helper required');return p

def validate_config(c,tp,target):
 exact={'schemaVersion':1,'kind':'root-review-only-shin90-after85-opposite-config','coordinateSpace':'working','diagnosticOnly':True,'sourcePart':'shinl','part':'shinr','sourceJoint':'lshin_g','joint':'rshin_g','sourceKind':PARENT_KIND,'statureApplications':0,'factor85Or90FitFieldReapplied':False,'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'planeOriginWorld':[0.,0.,0.],'planeNormalWorld':[1.,0.,0.]}
 tc.require(all(c.get(k)==v for k,v in exact.items()) and c['sourceReceipt']['sha256']==PARENT_SHA,'Only exact new LEFTshin90 parent; no85/back20/thigh/arm aliases')
 tc.require(target['identity'].get('race')=='troll' and target['identity']['gender']=='male' and target['identity']['prefix']=='pmg0','Troll male only');tc.require(Path(c['targetContract']).resolve()==Path(tp).resolve() and c['targetContractSha256']==tc.sha(tp) and c['rigRevision']==target['rig']['revision'] and c['model']==tc.model(target,'shinr'),'Exact frozen target/RIGHT model')
 H=tc.frame(target,'lshin_g','working');G=tc.frame(target,'rshin_g','working');M,R=reflection_between_frames(H,G,[0.,0.,0.],[1.,0.,0.]);tc.require(np.array_equal(c['sourceAttachmentWorld'],H) and np.array_equal(c['attachmentWorld'],G) and np.array_equal(c['sourceToAttachmentLocal'],M) and np.array_equal(c['reflectionWorld'],R),'Exact frozen opposite-frame conjugation');return H,G,M,R

def validate_approval(a,c):tc.require(a.get('kind')=='root-approved-shin-girth90-after85-opposite-mirror' and a.get('reviewedBy')=='/root' and a.get('authorizeImplementationAndOneFreshExport') is True and a.get('configuration')==c,'Exact ROOT RIGHTshin90 mirror approval')

def source(c,tp,target,pins):
 rp=pin(c['sourceReceipt']['path'],c['sourceReceipt']['sha256'],pins);v=verify_left(rp,tp,target,'working');r=v['receipt'];pins.update(v['inputs']);tc.require(r['kind']==PARENT_KIND and r['part']=='shinl' and r['candidate']==c['sourceCandidate']['path'] and r['candidateSha256']==c['sourceCandidate']['sha256'] and r['nativeCornerArchive']==c['sourceNativeCornerArchive'],'Exact actual LEFT parent/archival association')
 ap=pin(c['sourceIndependentAudit']['path'],c['sourceIndependentAudit']['sha256'],pins);a=json.loads(ap.read_text());tc.require(a['kind']=='independent-decoded-shin90-after85-proof' and a['pass'] is True and a['receipt']==c['sourceReceipt'] and a['candidate']==c['sourceCandidate'] and a['nativeCornerArchive']==c['sourceNativeCornerArchive'],'Successful exact actual LEFT independent audit');cl=pin(a['verifiedInputClosure']['path'],a['verifiedInputClosure']['sha256'],pins)
 for p,h in json.loads(cl.read_text()).items():pin(p,h,pins)
 sp=pin(c['sourceCandidate']['path'],c['sourceCandidate']['sha256'],pins);np_=pin(c['sourceNativeCornerArchive']['path'],c['sourceNativeCornerArchive']['sha256'],pins);doc,blob=read_glb(sp);tc.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and len(doc['meshes'][0]['primitives'])==1,'One identity LEFT primitive');prim=doc['meshes'][0]['primitives'][0];F=accessor(doc,blob,prim['indices']).reshape(-1,3).astype(np.int64);rows={s:accessor(doc,blob,prim['attributes'][s]) for s in ['POSITION','NORMAL','TANGENT','TEXCOORD_0']}
 with np.load(np_,allow_pickle=False) as z:arc={k:z[k].copy() for k in z.files}
 tc.require(np.array_equal(arc['sourceCornerOrder'],np.tile([0,1,2],(len(F),1))) and np.array_equal(arc['sourceTriangleIds'],np.arange(len(F))) and np.array_equal(arc['uvGltf'],rows['TEXCOORD_0'][F]),'Original current face/corner/UV lineage');return r,doc,blob,rows,F,arc

def execute(approval_path,output):
 ap=Path(approval_path).resolve();a=json.loads(ap.read_text());c=a['configuration'];validate_approval(a,c);validate_executor(c);pins={};pin(ap,tc.sha(ap),pins);p=pin(a['proposal']['path'],a['proposal']['sha256'],pins);tc.require(json.loads(p.read_text())==c,'Exact approved proposal');tp=pin(c['targetContract'],c['targetContractSha256'],pins);target=tc.load(tp);H,G,M,R=validate_config(c,tp,target);parent,doc,blob,rows,F,arc=source(c,tp,target,pins);nd,nb,unused,bake=detached_affine_bake(doc,blob,M,True);native=mirror_archive(arc,M);pr=proof(doc,blob,nd,nb,rows,F,native,H,G,M,R,PARENT_KIND);out=Path(output).resolve();tc.require(not out.exists(),'One fresh immutable RIGHTshin90 export');helpers=[Path(__file__),Path(__file__).with_name('test_diagnostic_shin_girth90_opposite.py')]+[Path(__file__).with_name(n) for n in ['diagnostic_shin_girth90.py','diagnostic_selected_working_opposite.py','mirror_stock_limb_part.py','target_contract.py','place_purposebuilt_pelvis.py']]
 for p in helpers:pin(p,tc.sha(p),pins)
 if 'sourceBoundPlan' in a:pin(a['sourceBoundPlan']['path'],a['sourceBoundPlan']['sha256'],pins)
 out.mkdir(parents=True);candidate=out/'candidate-local.glb';write_glb(candidate,nd,nb);archive=out/'native-float64-shin90-mirrored-corners.npz';np.savez_compressed(archive,**native);(out/'helpers').mkdir();snaps={}
 for p in helpers:q=out/'helpers'/p.name;shutil.copyfile(p,q);snaps[str(p.resolve())]={'path':str(q),'sha256':tc.sha(q)}
 r={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KIND,'operation':OP,'part':'shinr','sourcePart':'shinl','joint':'rshin_g','model':tc.model(target,'shinr'),'sourceKind':PARENT_KIND,'diagnosticOnly':True,'canonicalNativeLineage':False,'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':G.tolist(),'sourceAttachmentWorld':H.tolist(),'sourceToAttachmentLocal':M.tolist(),'reflectionWorld':R.tolist(),'sourceReceipt':c['sourceReceipt'],'sourceCandidate':c['sourceCandidate'],'parentNativeCornerArchive':c['sourceNativeCornerArchive'],'nativeCornerArchive':{'path':str(archive),'sha256':tc.sha(archive)},'rootApproval':{'path':str(ap),'sha256':tc.sha(ap)},'fieldConfiguration':c,'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'statureApplications':0,'factor85Or90FitFieldReapplied':False,'rigOrNeighborsChanged':False,'proof':pr,'bakeProof':bake,'frozenInputs':pins,'helperSnapshots':snaps,'limits':['Exact working diagnostic LEFT90 status retained; no fit/85/90/stature repetition.','Authoritative current f64 PNT/UV/corner order reflected once; all historical source arrays remain literal LEFT records.','Actual bilateral knee/ankle/fullbody/articulation/material/native/client review remains required.'],**{k:False for k in PENDING}};rp=out/'diagnostic-shin90-opposite-geometry.json';rp.write_text(json.dumps(r,indent=2)+'\n');verify_receipt(rp,tp,target);return rp

def verify_receipt(receipt_path,target_path,target,space='working'):
 path=Path(receipt_path).resolve();r=json.loads(path.read_text());tc.require(r['schemaVersion']==1 and r['kind']==KIND and r['operation']==OP and space=='working' and r['diagnosticOnly'] is True and r['canonicalNativeLineage'] is False and all(r[k] is False for k in PENDING),'Exact unpromoted typed RIGHTshin90 working mirror');tc.verify_binding(r,target_path,target,space);c=r['fieldConfiguration'];validate_executor(c);H,G,M,R=validate_config(c,target_path,target);tc.require(r['part']=='shinr' and r['sourcePart']=='shinl' and r['joint']=='rshin_g' and r['model']==tc.model(target,'shinr') and r['statureApplications']==0 and r['factor85Or90FitFieldReapplied'] is False and r['rigOrNeighborsChanged'] is False and np.array_equal(r['candidateToAttachmentLocal'],np.eye(4)) and np.array_equal(r['attachmentWorld'],G),'Single fixed-frame reflection no field promotion');pins={}
 for p,h in r['frozenInputs'].items():pin(p,h,pins)
 validate_approval(json.loads(Path(r['rootApproval']['path']).read_text()),c);parent,doc,blob,rows,F,arc=source(c,target_path,target,pins);pin(r['candidate'],r['candidateSha256'],pins);pin(r['nativeCornerArchive']['path'],r['nativeCornerArchive']['sha256'],pins);nd,nb=read_glb(r['candidate']);ed,eb,unused,bake=detached_affine_bake(doc,blob,M,True);tc.require(nd==ed and nb==eb,'Exact actual reflection storage/PNT/W/index/maps');ea=mirror_archive(arc,M)
 with np.load(r['nativeCornerArchive']['path'],allow_pickle=False) as z:tc.require(set(z.files)==set(ea) and all(z[k].dtype==v.dtype and z[k].shape==v.shape and z[k].tobytes()==v.tobytes() for k,v in ea.items()),'Exact mirrored authoritative f64 and literal historical arrays')
 tc.require(proof(doc,blob,nd,nb,rows,F,ea,H,G,M,R,PARENT_KIND)==r['proof'],'Mirror/frame/topology proof differs');pins[str(path)]=tc.sha(path);return {'receipt':r,'candidate':Path(r['candidate']),'inputs':pins,'primitiveInventory':[{'primitive':0,'part':'shinr','material':nd['meshes'][0]['primitives'][0]['material'],'faces':len(F)}]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rp=execute(a.approval,a.output);print(json.dumps({'path':str(rp),'sha256':tc.sha(rp)}),flush=True)
