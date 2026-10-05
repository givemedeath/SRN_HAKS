"""Exact diagnostic-parent, opposite-frame, authoritative-corner and preservation tests."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_opposite_lower_limb as mir
import diagnostic_axis_radial as radial
import target_part_pipeline as pipeline
import target_contract as tc
from place_purposebuilt_pelvis import accessor,read_glb,rotation_xyz,write_glb,BASIS
from test_target_part_pipeline import target_fixture
from test_mirror_stock_limb_part import fixture

class MirrorLineageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.td=target_fixture();self.td['identity']['race']='troll'
  for joint,pos,rot in [('lshin_g',[-.09,-.02,.57],[13,8,-21]),('lfoot_g',[-.07,-.08,.14],[0,0,0]),('rshin_g',[.090003,-.02,.57],[-12,7,29]),('rfoot_g',[.069999,-.08,.14],[0,0,0])]:
   H=np.eye(4);H[:3,:3]=rotation_xyz(rot);H[:3,3]=pos;self.td['rig']['frames']['working'][joint]=H.tolist();RH=H.copy();RH[:3,3]*=10/7;self.td['rig']['frames']['runtime'][joint]=RH.tolist()
  self.tp=self.root/'target.json';self.tp.write_text(json.dumps(self.td));doc,bb=fixture();self.source=self.root/'source.glb';write_glb(self.source,doc,bb);job=self.root/'job.json';job.write_text(json.dumps({'state':'success','promptId':'fixture','outputs':[{'localPath':str(self.source),'sha256':tc.sha(self.source)}]}));fc={'schemaVersion':2,'operation':'fit','part':'shinl','coordinateSpace':'working','targetContract':str(self.tp),'targetContractSha256':tc.sha(self.tp),'source':str(self.source),'sourceSha256':tc.sha(self.source),'sourceReceipt':str(job),'sourceReceiptSha256':tc.sha(job),'uniformScale':.45,'rotationDegreesXYZ':[13,-3,11],'sourceAnchorNwn':[.03,.05,.11],'targetAnchorLocal':[0,0,0]};fp=self.root/'fit.json';fp.write_text(json.dumps(fc));fitp=pipeline.execute(fp,self.root/'fit');fit=json.loads(fitp.read_text());H=tc.frame(self.td,'lshin_g','working');K=tc.frame(self.td,'lfoot_g','working');rc={'schemaVersion':1,'kind':'troll-left-leg-axis-radial-diagnostic-config','diagnosticOnly':True,'part':'shinl','coordinateSpace':'working','targetContract':str(self.tp),'targetContractSha256':tc.sha(self.tp),'rigRevision':self.td['rig']['revision'],'parentReceipt':str(fitp),'parentReceiptSha256':tc.sha(fitp),'parentCandidate':fit['candidate'],'parentCandidateSha256':fit['candidateSha256'],'factor':.85,'originWorld':H[:3,3].tolist(),'distalWorld':K[:3,3].tolist(),'protectedInputs':{}};rcp=self.root/'radial.json';rcp.write_text(json.dumps(rc));self.rp=radial.execute(rcp,self.root/'radial');self.r=json.loads(self.rp.read_text())
 def tearDown(self):self.tmp.cleanup()
 def config(self):
  H=tc.frame(self.td,'lshin_g','working');G=tc.frame(self.td,'rshin_g','working');M,R=mir.reflection_between_frames(H,G,[0.,0.,0.],[1.,0.,0.]);return {'schemaVersion':1,'kind':'troll-opposite-lower-limb-diagnostic-mirror-config','coordinateSpace':'working','diagnosticOnly':True,'sourcePart':'shinl','part':'shinr','sourceKind':self.r['kind'],'sourceJoint':'lshin_g','joint':'rshin_g','model':tc.model(self.td,'shinr'),'targetContract':str(self.tp),'targetContractSha256':tc.sha(self.tp),'rigRevision':self.td['rig']['revision'],'sourceReceipt':{'path':str(self.rp),'sha256':tc.sha(self.rp)},'sourceCandidate':{'path':self.r['candidate'],'sha256':self.r['candidateSha256']},'sourceNativeCornerArchive':self.r['nativeCornerArchive'],'sourceAttachmentWorld':H.tolist(),'attachmentWorld':G.tolist(),'planeOriginWorld':[0.,0.,0.],'planeNormalWorld':[1.,0.,0.],'reflectionWorld':R.tolist(),'sourceToAttachmentLocal':M.tolist(),'statureApplications':0,'factor85Reapplied':False,'proximalBackFieldReapplied':False,'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'historicalExecutedSourceRecoveries':{}}
 def run_config(self,c,name='child'):
  cp=self.root/(name+'-config.json');cp.write_text(json.dumps(c));a={'kind':'root-approved-opposite-lower-limb-diagnostic-mirror','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':c,'proposal':{'path':str(cp),'sha256':tc.sha(cp)}};ap=self.root/(name+'-approval.json');ap.write_text(json.dumps(a));rp=mir.execute(ap,self.root/name);return rp,json.loads(rp.read_text())
 def test_actual_source_bound_export_world_frames_attributes_and_f64(self):
  rp,r=self.run_config(self.config());od,ob=read_glb(self.r['candidate']);nd,nb=read_glb(r['candidate']);op=od['meshes'][0]['primitives'][0];np_=nd['meshes'][0]['primitives'][0];F=accessor(od,ob,op['indices']).reshape(-1,3);NF=accessor(nd,nb,np_['indices']).reshape(-1,3);np.testing.assert_array_equal(NF,F[:,[0,2,1]]);self.assertEqual(nb[:len(ob)],ob);self.assertEqual(nd['materials'],od['materials']);self.assertEqual(nd['images'],od['images']);self.assertEqual(nd['accessors'][:len(od['accessors'])],od['accessors'])
  for sem,aid in op['attributes'].items():self.assertEqual(accessor(od,ob,aid,allow_normalized=True).tobytes(),accessor(nd,nb,aid,allow_normalized=True).tobytes())
  H=np.asarray(r['sourceAttachmentWorld']);G=np.asarray(r['attachmentWorld']);P=accessor(od,ob,op['attributes']['POSITION']).astype(float)@BASIS.T;Q=accessor(nd,nb,np_['attributes']['POSITION']).astype(float)@BASIS.T;W=P@H[:3,:3].T+H[:3,3];NW=Q@G[:3,:3].T+G[:3,3];np.testing.assert_allclose(NW,W@np.diag([-1.,1,1]),atol=3e-8,rtol=0)
  with np.load(self.r['nativeCornerArchive']['path']) as pa,np.load(r['nativeCornerArchive']['path']) as ca:
   M=np.asarray(r['sourceToAttachmentLocal']);np.testing.assert_array_equal(ca['positions'],(pa['positions']@M[:3,:3].T+M[:3,3])[:,[0,2,1]]);np.testing.assert_array_equal(ca['mirrorParentPositions'],pa['positions']);np.testing.assert_array_equal(ca['sourceCornerOrder'],pa['sourceCornerOrder'][:,[0,2,1]]);np.testing.assert_array_equal(ca['uvNative'],pa['uvNative'][:,[0,2,1]]);np.testing.assert_array_equal(ca['tangents'][...,3],-pa['tangents'][:,[0,2,1],3])
  self.assertEqual(r['kind'],mir.KIND);self.assertNotEqual(r['kind'],'target-part-geometry');self.assertEqual(r['statureApplications'],0);self.assertFalse(r['factor85Reapplied']);self.assertTrue(all(r[k] is False for k in mir.PENDING));self.assertEqual(r['proof']['beforeTopology'],r['proof']['afterTopology']);mir.verify_receipt(rp,self.tp,self.td)
 def test_canonical_source_guard_stays_strict(self):
  with self.assertRaisesRegex(ValueError,'Target geometry receipt'):pipeline.verify_source_receipt(Path(self.r['candidate']),self.rp,self.tp,self.td,'shinl','working')
 def test_source_kind_pair_runtime_and_repeat_controls_fail_closed(self):
  for k,v in [('part','legr'),('sourcePart','shinr'),('sourceKind','target-part-geometry'),('coordinateSpace','runtime'),('statureApplications',1),('factor85Reapplied',True),('proximalBackFieldReapplied',True),('sourceCornerPermutation',[0,1,2]),('tangentWReflectionFactor',1)]:
   c=self.config();c[k]=v
   with self.subTest(key=k),self.assertRaises(ValueError):mir.validate_config(c,self.tp,self.td)
 def test_guessed_plane_frame_scale_and_model_rejected(self):
  for k,v in [('planeOriginWorld',[.001,0.,0.]),('planeNormalWorld',[.9,.1,0.]),('attachmentWorld',np.eye(4).tolist()),('sourceToAttachmentLocal',np.eye(4).tolist()),('model','pmh0_shinr001')]:
   c=self.config();c[k]=v
   with self.subTest(key=k),self.assertRaises(ValueError):mir.validate_config(c,self.tp,self.td)
 def test_source_archive_candidate_pins_and_face_association_rejected(self):
  for k in ['sourceCandidate','sourceNativeCornerArchive','sourceReceipt']:
   c=self.config();c[k]['sha256']='0'*64
   with self.subTest(key=k),self.assertRaises(ValueError):self.run_config(c,k)
 def test_cumulative_mirror_and_human_not_promoted(self):
  rp,r=self.run_config(self.config());c=self.config();c['sourceReceipt']={'path':str(rp),'sha256':tc.sha(rp)};c['sourceCandidate']={'path':r['candidate'],'sha256':r['candidateSha256']}
  with self.assertRaises(ValueError):self.run_config(c,'cumulative')
  td=copy.deepcopy(self.td);td['identity']['race']='human'
  with self.assertRaisesRegex(ValueError,'Troll male'):mir.validate_config(self.config(),self.tp,td)
 def test_duplicate_output_and_missing_authorization_rejected(self):
  rp,r=self.run_config(self.config());h=tc.sha(rp)
  with self.assertRaisesRegex(ValueError,'Fresh immutable'):self.run_config(self.config())
  self.assertEqual(tc.sha(rp),h)
  with self.assertRaisesRegex(ValueError,'root mirror approval'):mir.validate_approval({'configuration':self.config()},self.config())

class NativePrecisionTests(unittest.TestCase):
 def test_authoritative_f64_is_not_rebuilt_from_serialized_geometry(self):
  p=np.array([[[.100000000111,.2,.3],[.1,.200000000222,.3],[.1,.2,.300000000333]]]);n=np.array([[[.3,.4,1.7]]*3]);t=np.array([[[1.2,.05,.2,-1.]]*3]);uv=np.array([[[.1,.2],[.3,.4],[.5,.6]]]);a={'positions':p,'normals':n,'tangents':t,'uvNative':uv,'uvGltf':uv.copy(),'sourceCornerOrder':np.array([[0,1,2]]),'sourceTriangleIds':np.array([17]),'primitiveIds':np.array([0]),'tangentTriangleIds':np.array([17])};M=np.diag([-1.,1,1,1]);M[0,3]=-.000002794;b=mir.mirror_archive(a,M)
  np.testing.assert_array_equal(b['positions'],(p@M[:3,:3].T+M[:3,3])[:,[0,2,1]]);self.assertGreater(np.max(abs(b['positions']-b['positions'].astype('<f4').astype(float))),1e-9);self.assertEqual(b['mirrorParentPositions'].tobytes(),p.tobytes());np.testing.assert_array_equal(b['sourceTriangleIds'],[17]);np.testing.assert_array_equal(b['tangents'][...,3],[[1,1,1]]);np.testing.assert_array_equal(b['uvGltf'],uv[:,[0,2,1]])

if __name__=='__main__':unittest.main()
