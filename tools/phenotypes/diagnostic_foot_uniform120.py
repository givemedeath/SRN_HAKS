"""Narrow original-LEFTfoot120 diagnostic, append POSITION only, no rig/stature edits."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from target_part_pipeline import verify_source_receipt
from place_purposebuilt_pelvis import BASIS,read_glb,write_glb,node_matrix,accessor,embedded_maps
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'output/phenotypes/troll-male-purposebuilt-v1'
LEFT=BASE/'fits/foot-imagegen-v1-working-fit-v1/left/geometry.json'
LEFT_SHA='a7d016161b0f040c33b1e3d8307dadf6d9470845f8580f023bc2ceda06061bd6'
RIGHT_SHA='ddeb1edb0f4dda9bd7e88c48294f0f4146463c07955117222ba739ed34143c25'
TARGET=BASE/'rig-frozen-v1/target-contract.json'
TARGET_SHA='65e25102a970193786a6c6bffd1b9e1ee15c9c0e323f4a83e17deb5e23e97c0a'
DIRECTION=ROOT/'docs/phenotypes/evidence/troll-male-feet120-uniform-direction-v1/root-direction.json'
DIRECTION_SHA='09f97892d3ae68f2cd1c4a3d1c09fcc5f67d3f6003d51bb523468e96f3c32047'
SHIN=BASE/'inspection/lower-limb-bulk-review-v1/radial85-trial-v1/shinl/diagnostic.json'
SHIN_SHA='dd165ebefefe72901c41cd7892def5b10f762cc082491e832f2cda9bd215729b'
FACTOR=1.2
# Two explicit historic preview-only owners; never replace geometric/controller/material pins.
NEIGHBOR_PREVIEW_SNAPSHOTS={
 str(ROOT/'tools/phenotypes/pose_preview.py'):('53892b59b76eebb3713674d2e259905d5e4dd6de4645e9f6a9307a21c77b725f',BASE/'integrated-regression-v7/source-snapshot/tools/phenotypes/pose_preview.py'),
 str(ROOT/'tools/phenotypes/pose_preview_target_parts.py'):('3488252c73562d0138d674f6c931ee0833d26426ed5274f85f80121ded2f177a',BASE/'fits/body-assembled-working-v2/pause1/executed-preview-helpers/pose_preview_target_parts.py')}


def pin_neighbor_ancestry(inputs,pin):
 resolutions=[]
 for name,expected in inputs.items():
  if name in NEIGHBOR_PREVIEW_SNAPSHOTS:
   h,snapshot=NEIGHBOR_PREVIEW_SNAPSHOTS[name];require(expected==h,'Unknown historical neighbor preview version');pin(snapshot,h);resolutions.append({'historicalOwner':name,'expectedSha256':h,'exactFrozenSnapshot':ref(snapshot),'scope':'Inherited preview-only helper bytes; unchanged source geometry/controller/material pins still checked literally.'})
  else:pin(name,expected)
 return resolutions

def require(ok,message):
 if not ok:raise ValueError(message)

def ref(p):return {'path':str(Path(p).resolve()),'sha256':tc.sha(p)}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def exact(a,b):return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()
def finite(p,shape=None):
 a=np.asarray(p,dtype=float);require((shape is None or a.shape==shape) and np.isfinite(a).all(),'Finite expected-shaped values required');return a

def check_direction(d):
 require(d.get('kind')=='root-human-feet120-uniform-XYZ-direction' and d.get('scaleXYZ')==[FACTOR]*3 and d.get('ratioFromCurrentOriginalBaseline')==FACTOR,'Exact feet120 uniform XYZ authority required')
 require(d.get('leftOriginalBaseline')==ref(LEFT) and d['leftOriginalBaseline']['sha256']==LEFT_SHA and d.get('rightOriginalBaselineHistorical',{}).get('sha256')==RIGHT_SHA,'Original selected foot baselines required')
 require(d.get('statureApplications')==0 and d.get('priorLargerFootTrialsOrCompressionReapplied') is False and d.get('noTerminalTaperOrWindow') is True,'No prior enlarged/deformed lineage or stature operation allowed')

def sole_projection(frame,positions):
 A=finite(frame,(4,4));P=finite(positions);require(P.ndim>=2 and P.shape[-1]==3 and P.size>0,'Nonempty XYZ positions required')
 require(np.array_equal(A[3],[0,0,0,1]) and np.allclose(A[:3,:3].T@A[:3,:3],np.eye(3),atol=1e-13,rtol=0) and np.linalg.det(A[:3,:3])>0,'Proper frozen attachment frame required')
 w=P@A[:3,:3].T+A[:3,3];z=float(w[...,2].min());cw=np.array([A[0,3],A[1,3],z]);cl=A[:3,:3].T@(cw-A[:3,3]);return cl,cw,z

def uniform_positions(positions,pivot,scale=FACTOR):
 require(isinstance(scale,(float,int)) and scale==FACTOR,'Only explicit uniform1.20 is supported');P=finite(positions);c=finite(pivot,(3,));require(P.shape[-1]==3,'XYZ rows required');Q=c+(P-c)*scale;require(np.isfinite(Q).all(),'Scaled positions overflow');return Q

def append_position(d,b,pivot):
 require(len(d.get('nodes',[]))==len(d.get('meshes',[]))==len(d.get('scenes',[]))==1 and np.array_equal(node_matrix(d['nodes'][0]),np.eye(4)),'Detached identity source required')
 require(not d.get('animations') and not d.get('skins') and len(d['meshes'][0]['primitives'])==1,'Single static primitive required')
 pr=d['meshes'][0]['primitives'][0];attrs=pr['attributes'];require(set(attrs)=={'POSITION','NORMAL','TANGENT','TEXCOORD_0'},'Exact authored attribute inventory required')
 rows={k:accessor(d,b,i) for k,i in attrs.items()};require(all(a.dtype==np.dtype('<f4') and np.isfinite(a).all() for a in rows.values()),'Finite float32 source attributes required')
 require(np.all(np.linalg.norm(rows['NORMAL'],axis=1)>0) and np.all(np.linalg.norm(rows['TANGENT'][:,:3],axis=1)>0) and np.all(abs(rows['TANGENT'][:,3])==1),'Authored N/T/W ownership invalid')
 cg=finite(pivot,(3,))@BASIS;newP=uniform_positions(rows['POSITION'].astype(float),cg).astype('<f4');require(np.isfinite(newP).all(),'Float32 position overflow')
 nd=copy.deepcopy(d);nb=bytearray(b);require(len(nb)%4==0,'Original padded BIN required');off=len(nb);nb.extend(newP.tobytes());nb.extend(b'\0'*(-len(nb)%4));nd['bufferViews'].append({'buffer':0,'byteOffset':off,'byteLength':newP.nbytes});nd['accessors'].append({'bufferView':len(nd['bufferViews'])-1,'componentType':5126,'count':len(newP),'type':'VEC3','min':newP.min(0).astype(float).tolist(),'max':newP.max(0).astype(float).tolist()});nd['meshes'][0]['primitives'][0]['attributes']['POSITION']=len(nd['accessors'])-1;nd['buffers'][0]['byteLength']=len(nb)
 for sem in ('NORMAL','TANGENT','TEXCOORD_0'):require(exact(rows[sem],accessor(nd,nb,nd['meshes'][0]['primitives'][0]['attributes'][sem])),'Authored shading/UV bytes changed')
 require(bytes(nb[:len(b)])==b and d['materials']==nd['materials'] and embedded_maps(d,b)==embedded_maps(nd,bytes(nb)),'Original BIN/maps/materials changed')
 require(pr['indices']==nd['meshes'][0]['primitives'][0]['indices'],'Indices changed');return nd,bytes(nb),newP

def checked():
 pins={}
 def pin(p,h=None):
  p=Path(p).resolve();v=tc.sha(p);require(h is None or h==v,'Input changed: '+str(p));pins[str(p)]=v;return p
 pin(LEFT,LEFT_SHA);pin(TARGET,TARGET_SHA);pin(DIRECTION,DIRECTION_SHA);direction=read(DIRECTION);check_direction(direction);right=direction['rightOriginalBaselineHistorical'];pin(right['path'],RIGHT_SHA)
 target=tc.load(TARGET);src=read(LEFT);require(src.get('operation')=='fit' and src.get('sourcePart') is None,'Only original fitted LEFT baseline allowed')
 src=verify_source_receipt(Path(src['candidate']).resolve(),LEFT.resolve(),TARGET.resolve(),target,'footl','working');pins.update(src['frozenInputs']);pin(src['candidate'],src['candidateSha256']);pin(src['nativeCornerArchive']['path'],src['nativeCornerArchive']['sha256'])
 require(np.array_equal(src['attachmentWorld'],tc.frame(target,'lfoot_g','working')) and src['reflectionWorld'] is None,'Frozen LEFT foot frame/lineage changed')
 shin=read(pin(SHIN,SHIN_SHA));tc.verify_binding(shin,TARGET.resolve(),target,'working');require(shin['part']=='shinl' and shin['factor']==.85 and shin['statureApplications']==0 and np.array_equal(shin['attachmentWorld'],tc.frame(target,'lshin_g','working')),'Exact current LEFTshin85 required')
 pin_neighbor_ancestry(shin['frozenInputs'],pin)
 pin(shin['candidate'],shin['candidateSha256']);pin(shin['nativeCornerArchive']['path'],shin['nativeCornerArchive']['sha256'])
 for p in [Path(__file__),Path(__file__).with_name('target_contract.py'),Path(__file__).with_name('target_part_pipeline.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py')]:pin(p)
 d,b=read_glb(src['candidate']);pr=d['meshes'][0]['primitives'][0];P=accessor(d,b,pr['attributes']['POSITION']);F=accessor(d,b,pr['indices']).reshape(-1,3).astype(int);require(P.shape==(32800,3) and F.shape==(50000,3) and F.min()>=0 and F.max()<32800,'Exact original foot vertex/face inventory required')
 with np.load(src['nativeCornerArchive']['path'],allow_pickle=False) as z:arc={k:z[k].copy() for k in z.files}
 require(arc['positions'].dtype==np.dtype('float64') and arc['positions'].shape==(50000,3,3),'Authoritative original f64 corner positions required');require(abs(arc['positions']-(P.astype(float)@BASIS.T)[F]).max()<2e-8,'Source f64/f32 corner correspondence changed')
 require(np.array_equal(arc['uvGltf'],accessor(d,b,pr['attributes']['TEXCOORD_0']).astype(float)[F]),'UV corner ownership differs')
 c,cw,sole=sole_projection(src['attachmentWorld'],arc['positions']);nd,nb,newP=append_position(d,b,c);Q=uniform_positions(arc['positions'],c);return src,target,d,b,arc,c,cw,sole,nd,nb,newP,Q,pins

def fresh(output,kind):
 p=Path(output).resolve();require(not p.exists(),'Fresh output required before any input reads')
 if kind=='prepare':require(p.parent==BASE/'inspection' and p.name.startswith('foot120-uniform-preparation-v'),'Preparation must be target-owned inspection output')
 else:require(p.name=='left' and p.parent.parent==BASE/'repairs' and p.parent.name.startswith('foot120-uniform'),'Export must be target-owned LEFT diagnostic output')
 return p

def prepare(output):
 out=fresh(output,'prepare');src,target,d,b,arc,c,cw,sole,nd,nb,newP,Q,pins=checked();out.mkdir()
 proposal=out/'arithmetic-proposal.npz';np.savez_compressed(proposal,parentPositions=arc['positions'],proposedPositions=Q,pivotLocal=c,pivotWorld=cw,plannedFloat32GLTFPositionRows=newP)
 M=np.diag([FACTOR]*3+[1.]);M[:3,3]=(1.-FACTOR)*c;A=np.array(src['attachmentWorld']);before=arc['positions']@A[:3,:3].T+A[:3,3];after=Q@A[:3,:3].T+A[:3,3]
 cfg={'schemaVersion':1,'kind':'review-proposed-original-left-foot120-uniform','operation':'uniform-scale-original-working-foot',**tc.binding(TARGET,target,'working'),'part':'footl','sourceGeometry':ref(LEFT),'sourceCandidate':ref(src['candidate']),'sourceNativeCorners':src['nativeCornerArchive'],'humanDirection':ref(DIRECTION),'rightBaselineHistorical':read(DIRECTION)['rightOriginalBaselineHistorical'],'unchangedLeftShin85':ref(SHIN),'shinHistoricalPreviewClosure':[{'historicalOwner':name,'sha256':h,'snapshot':ref(path)} for name,(h,path) in NEIGHBOR_PREVIEW_SNAPSHOTS.items()],'scaleXYZ':[FACTOR]*3,'pivotLocal':c.tolist(),'pivotWorld':cw.tolist(),'originalMeasuredBindSolePlaneWorldZ':sole,'sourceCandidateToNewLocal':M.tolist(),'proposedArithmeticArchive':ref(proposal),'originalVertexCount':32800,'originalTriangles':50000,'onlyPOSITIONAccessorAppended':True,'normalTangentWUVMapsMaterialIndicesBINLiteralPreservation':True,'authoritativeParentCornerPositionsOwnCoordinatesScaledOnce':True,'statureApplications':0,'parentSizeScaleApplications':0,'sizeScaleApplicationsOnOriginalBaseline':1,'priorLargerOrCompressedFootReapplied':False,'rootReviewRequiredBeforeActualExport':True,'fieldApproved':False,'actualModelExported':False,'geometryAccepted':False,'connectorAccepted':False,'materialAccepted':False,'clientAccepted':False,'productionAccepted':False,'protectedInputs':pins}
 cp=out/'review-config.json';cp.write_text(json.dumps(cfg,indent=2)+'\n')
 pp={'schemaVersion':2,'kind':'foot120-original-left-uniform-arithmetic-preparation',**tc.binding(TARGET,target,'working'),'configuration':ref(cp),'pivotLocal':c.tolist(),'pivotWorld':cw.tolist(),'originalBindSoleMinimumZ':float(before[:,:,2].min()),'proposedBindSoleMinimumZ':float(after[:,:,2].min()),'sourceLocalAnkleAnchorShift':uniform_positions(np.zeros((1,3)),c)[0].tolist(),'sourceTopWorldZ':float(before[:,:,2].max()),'proposedTopWorldZ':float(after[:,:,2].max()),'originalWorldBounds':[before.min((0,1)).tolist(),before.max((0,1)).tolist()],'proposedWorldBounds':[after.min((0,1)).tolist(),after.max((0,1)).tolist()],'serializedVsAuthoritativeProposedPositionMaxMetres':float(abs((newP.astype(float)@BASIS.T)[accessor(d,b,d['meshes'][0]['primitives'][0]['indices']).reshape(-1,3).astype(int)]-Q).max()),'normalTangentWUVMaterialIndicesMapsAndOriginalBINExact':True,'modelExported':False,'contactAccepted':False,'soleContactAccepted':False,'solePlanarityAccepted':False,'noShelvesRule':'Uniform global affine has no taper/window or new support-return band; actual source/child outline and ankle/sole motion/contact still require literal review. Existing39 nonmanifold edges/topology unchanged, not accepted.','unchangedNeighbor':ref(SHIN),'neighborHistoricalPreviewClosure':cfg['shinHistoricalPreviewClosure'],'next':'Independent arithmetic proof/root configuration review, one fresh LEFT export, then target_helpers matched original/120 ankle and sole motion before RIGHT mirror.','protectedInputs':pins}
 p=out/'preparation.json';p.write_text(json.dumps(pp,indent=2)+'\n');print(json.dumps({'configuration':ref(cp),'preparation':ref(p),'pivotLocal':c.tolist(),'ankleAnchorShift':pp['sourceLocalAnkleAnchorShift'],'modelExported':False}));return pp

def validate_review_config(cfg,src,target,c,cw,sole):
 require(cfg.get('schemaVersion')==1 and cfg.get('kind')=='review-proposed-original-left-foot120-uniform' and cfg.get('part')=='footl','Dedicated LEFTfoot120 review config required')
 tc.verify_binding(cfg,TARGET.resolve(),target,'working')
 require(cfg.get('scaleXYZ')==[FACTOR]*3 and cfg.get('pivotLocal')==c.tolist() and cfg.get('pivotWorld')==cw.tolist() and cfg.get('originalMeasuredBindSolePlaneWorldZ')==sole,'Reviewed scale/pivot/sole differs')
 require(cfg.get('sourceGeometry')==ref(LEFT) and cfg.get('sourceCandidate')==ref(src['candidate']) and cfg.get('sourceNativeCorners')==src['nativeCornerArchive'] and cfg.get('humanDirection')==ref(DIRECTION) and cfg.get('unchangedLeftShin85')==ref(SHIN),'Reviewed original source/direction/neighbor differs')
 M=np.diag([FACTOR]*3+[1.]);M[:3,3]=(1.-FACTOR)*c
 require(cfg.get('sourceCandidateToNewLocal')==M.tolist() and cfg.get('statureApplications')==0 and cfg.get('parentSizeScaleApplications')==0 and cfg.get('sizeScaleApplicationsOnOriginalBaseline')==1 and cfg.get('priorLargerOrCompressedFootReapplied') is False,'Exactly one originalbaseline size operation required')


def export(config_path,output,approved_review_sha256):
 out=fresh(output,'export');cp=Path(config_path).resolve();require(approved_review_sha256 and tc.sha(cp)==approved_review_sha256,'Exact explicit reviewed config SHA required');cfg=read(cp);require(cfg['kind']=='review-proposed-original-left-foot120-uniform','Dedicated proposed foot120 config required')
 for p,h in cfg['protectedInputs'].items():require(tc.sha(p)==h,'Prepared input changed: '+p)
 src,target,d,b,arc,c,cw,sole,nd,nb,newP,Q,pins=checked();validate_review_config(cfg,src,target,c,cw,sole);require(tc.sha(cfg['proposedArithmeticArchive']['path'])==cfg['proposedArithmeticArchive']['sha256'],'Arithmetic proposal changed');proposal=np.load(cfg['proposedArithmeticArchive']['path']);require(exact(proposal['parentPositions'],arc['positions']) and exact(proposal['proposedPositions'],Q),'Reviewed authoritative field differs');arc['positions']=Q
 out.mkdir(parents=True);glb=out/'candidate-local.glb';write_glb(glb,nd,nb);ap=out/'native-corners.npz';np.savez_compressed(ap,**arc);shutil.copyfile(__file__,out/'executed-foot120-helper.py');shutil.copyfile(cp,out/'reviewed-config.json');pins[str(cp)]=tc.sha(cp)
 M=np.diag([FACTOR]*3+[1.]);M[:3,3]=(1.-FACTOR)*c
 proof={'schemaVersion':1,'uniformScale':FACTOR,'orthogonalFactorNwn':np.eye(3).tolist(),'reflected':False,'triangleCornerOrder':[0,1,2],'triangles':50000,'identityOutputNode':True,'originalBinPrefixExact':True,'onlyPOSITIONAccessorAppended':True,'normalPolicy':'Identity proper rotation: original authored serialized/f64N bytes and magnitude literal; no normalization.','tangentPolicy':'OriginalXYZ/W bytes retained, no orthogonalization/mirror.','uvPolicy':'All original UV/index/map/material bindings and bytes exact.','rigPolicy':'Frozen ankle/frame/joint/socket untouched; zero stature.','pivotLocal':c.tolist()}
 r={'schemaVersion':2,'kind':'target-part-geometry','operation':'uniform-scale-original-working-foot',**tc.binding(TARGET,target,'working'),'part':'footl','joint':'lfoot_g','model':tc.model(target,'footl'),'sourcePart':'footl','source':src['candidate'],'sourceSha256':src['candidateSha256'],'sourceReceipt':str(LEFT.resolve()),'sourceReceiptSha256':LEFT_SHA,'candidate':str(glb),'candidateSha256':tc.sha(glb),'nativeCornerArchive':ref(ap),'statureApplications':0,'sourceToAttachmentLocal':M.tolist(),'attachmentWorld':tc.frame(target,'lfoot_g','working').tolist(),'reflectionWorld':None,'proof':proof,'configuration':ref(cp),'explicitReviewedConfigurationSha256':approved_review_sha256,'humanDirection':ref(DIRECTION),'sourceOriginalRatio':1.20,'sizeScaleApplicationsOnOriginalBaseline':1,'priorLargerOrCompressedFootReapplied':False,'frozenInputs':pins,'diagnosticOnly':True,'rigPilotAccepted':target['rig']['pilotAccepted'],'geometryAccepted':False,'topologyAccepted':False,'capOwnershipAccepted':False,'connectorAccepted':False,'soleContactAccepted':False,'materialAccepted':False,'clientAccepted':False,'productionAccepted':False,'limits':['Sole plane minimum preservation is arithmetic, not sole planarity or locomotion contact acceptance.','Actual LEFT with currentshin85 must be reviewed before frozen-frame RIGHT mirror.']}
 p=out/'geometry.json';p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'geometry':ref(p),'candidate':ref(glb),'nativeCorners':ref(ap)}));return r

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True);a=s.add_parser('prepare');a.add_argument('--output',required=True);a=s.add_parser('export');a.add_argument('--config',required=True);a.add_argument('--output',required=True);a.add_argument('--approved-review-sha256',required=True);args=p.parse_args()
 if args.mode=='prepare':prepare(args.output)
 else:export(args.config,args.output,args.approved_review_sha256)
if __name__=='__main__':main()
