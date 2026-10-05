import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_selected_working_opposite as m
import diagnostic_opposite_lower_limb as old
from mirror_stock_limb_part import reflection_between_frames
class SelectedMirrorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.tp=Path(self.tmp.name)/'target.json';self.tp.write_text('{}');H=np.eye(4);H[:3,3]=[-.2,.04,1.];G=np.eye(4);G[:3,3]=[.2,.04,1.];M,R=reflection_between_frames(H,G,[0.,0.,0.],[1.,0.,0.]);self.H,self.G,self.M,self.R=H,G,M,R;self.target={'identity':{'race':'troll','gender':'male','prefix':'pmg0'},'rig':{'revision':'test','frames':{'working':{'lthigh_g':H,'rthigh_g':G,'lbicep_g':H,'rbicep_g':G}}},'models':{'legr':'pmg0_legr001','bicepr':'pmg0_bicepr001'}}
  self.c={'schemaVersion':1,'kind':'root-review-only-selected-working-diagnostic-mirror-config','coordinateSpace':'working','diagnosticOnly':True,'sourcePart':'legl','part':'legr','sourceKind':m.PAIRS['legl'][1],'sourceReceipt':{'sha256':m.PAIRS['legl'][2]},'sourceJoint':'lthigh_g','joint':'rthigh_g','model':'pmg0_legr001','targetContract':str(self.tp),'targetContractSha256':m.tc.sha(self.tp),'rigRevision':'test','statureApplications':0,'sourceFieldsOrFitReapplied':False,'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'sourceSpecificNativeRepresentationDifferenceRepaired':False,'planeOriginWorld':[0.,0.,0.],'planeNormalWorld':[1.,0.,0.],'sourceAttachmentWorld':H.tolist(),'attachmentWorld':G.tolist(),'sourceToAttachmentLocal':M.tolist(),'reflectionWorld':R.tolist()}
 def test_two_exact_parent_enums_accept(self):
  m.validate_config(self.c,self.tp,self.target);c=copy.deepcopy(self.c);c.update(sourcePart='bicepl',part='bicepr',sourceKind=m.PAIRS['bicepl'][1],sourceReceipt={'sha256':m.PAIRS['bicepl'][2]},sourceJoint='lbicep_g',joint='rbicep_g',model='pmg0_bicepr001');m.validate_config(c,self.tp,self.target)
 def test_old_back20_and_canonical_alias_rejected(self):
  for kind in [old.PAIRS['legl'][1],'target-part-geometry']:
   c=copy.deepcopy(self.c);c['sourceKind']=kind
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_foot_and_shin_are_not_added(self):
  for source in ['footl','shinl']:
   c=copy.deepcopy(self.c);c['sourcePart']=source
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_Human_female_runtime_and_wrong_joint_rejected(self):
  for field,val in [('race','human'),('gender','female'),('prefix','pmh0')]:
   target=copy.deepcopy(self.target);target['identity'][field]=val
   with self.assertRaises(ValueError):m.validate_config(self.c,self.tp,target)
  for field,val in [('coordinateSpace','runtime'),('joint','rfoot_g'),('model','pmh0_legr001')]:
   c=copy.deepcopy(self.c);c[field]=val
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_fit_field_scale_or_corner_repeat_rejected(self):
  for field,val in [('statureApplications',1),('sourceFieldsOrFitReapplied',True),('sourceSpecificNativeRepresentationDifferenceRepaired',True),('sourceCornerPermutation',[0,1,2]),('tangentWReflectionFactor',1)]:
   c=copy.deepcopy(self.c);c[field]=val
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_historical_parent_helper_enum_unchanged(self):
  self.assertEqual(old.PAIRS,{'shinl':('shinr','troll-left-leg-axis-radial-diagnostic'),'legl':('legr','target-part-diagnostic-thigh-proximal-backward-Y')});self.assertIs(m.PAIRS['legl'][3],m.verify_corrected30);self.assertIs(m.PAIRS['bicepl'][3],m.verify_upperarm110)
 def test_authoritative_archive_reflection_and_history_conservation(self):
  p=np.array([[[.1,.2,.3],[.5,.2,.3],[.1,.6,.3]]]);n=np.array([[[0.,0.,2.]]*3]);t=np.array([[[3.,0.,0.,1.]]*3]);uv=np.array([[[.1,.2],[.3,.4],[.5,.6]]]);arc={'positions':p,'normals':n,'tangents':t,'uvNative':uv,'uvGltf':uv.copy(),'sourceCornerOrder':np.array([[0,1,2]]),'sourceTriangleIds':np.array([98]),'primitiveIds':np.array([0]),'oneSidedParentPositions':p.copy(),'sourceNormals':n.copy()};out=m.mirror_archive(arc,self.M);self.assertTrue(np.array_equal(out['positions'],(p@self.M[:3,:3].T+self.M[:3,3])[:,[0,2,1]]));self.assertTrue(np.array_equal(out['normals'],(n@self.M[:3,:3].T)[:,[0,2,1]]));self.assertTrue(np.array_equal(out['tangents'][...,3],-t[:,[0,2,1],3]));self.assertTrue(np.array_equal(out['uvGltf'],uv[:,[0,2,1]]));self.assertTrue(np.array_equal(out['sourceCornerOrder'],[[0,2,1]]));self.assertEqual(out['oneSidedParentPositions'].tobytes(),p.tobytes());self.assertEqual(out['sourceNormals'].tobytes(),n.tobytes());self.assertEqual(out['sourceTriangleIds'].tobytes(),arc['sourceTriangleIds'].tobytes())
 def test_world_reflection_frame_conjugation_with_offsets(self):
  rng=np.random.default_rng(123);p=rng.normal(size=(17,3));q=p@self.M[:3,:3].T+self.M[:3,3];a=p@self.H[:3,:3].T+self.H[:3,3];b=q@self.G[:3,:3].T+self.G[:3,3];np.testing.assert_allclose(b,a@self.R[:3,:3].T+self.R[:3,3],rtol=0,atol=1e-15);self.assertEqual(np.linalg.det(self.M[:3,:3]),-1.)
 def test_root_approval_must_match_exact_config(self):
  a={'kind':'root-approved-selected-working-diagnostic-opposite-mirror','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':copy.deepcopy(self.c)};m.validate_approval(a,self.c);a['configuration']['statureApplications']=1
  with self.assertRaises(ValueError):m.validate_approval(a,self.c)
 def test_current_exact_executor_pin_accepts(self):
  pin={'path':str(Path(m.__file__).resolve()),'sha256':m.tc.sha(m.__file__)};self.assertEqual(m.validate_executor({'expectedExecutor':pin}),Path(m.__file__).resolve())
 def test_executor_wrong_path_stale_hash_and_missing_pin_reject(self):
  samebytes=Path(self.tmp.name)/'other-helper.py';samebytes.write_bytes(Path(m.__file__).read_bytes())
  for c in [{},{'expectedExecutor':{'path':str(samebytes),'sha256':m.tc.sha(samebytes)}},{'expectedExecutor':{'path':str(Path(m.__file__).resolve()),'sha256':'0'*64}},{'expectedExecutor':{'path':str(Path(m.__file__).resolve())}}]:
   with self.assertRaises(ValueError):m.validate_executor(c)
 def test_execute_enforces_executor_before_loading_parent_or_export(self):
  c=copy.deepcopy(self.c);c['expectedExecutor']={'path':str(Path(m.__file__).resolve()),'sha256':'0'*64};proposal=Path(self.tmp.name)/'proposal.json';proposal.write_text(json.dumps(c));a={'kind':'root-approved-selected-working-diagnostic-opposite-mirror','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':c,'proposal':{'path':str(proposal),'sha256':m.tc.sha(proposal)}};ap=Path(self.tmp.name)/'approval.json';ap.write_text(json.dumps(a));out=Path(self.tmp.name)/'out'
  with self.assertRaisesRegex(ValueError,'executing helper'):m.execute(ap,out)
  self.assertFalse(out.exists())
 def test_verify_enforces_executor_before_decoding_parent(self):
  target=copy.deepcopy(self.target);target['id']='test-troll';c=copy.deepcopy(self.c);c['expectedExecutor']={'path':str(Path(self.tmp.name)/'foreign.py'),'sha256':m.tc.sha(m.__file__)};r={**m.tc.binding(self.tp,target,'working'),'schemaVersion':1,'kind':m.KIND,'operation':m.OP,'diagnosticOnly':True,'canonicalNativeLineage':False,'fieldConfiguration':c,**{k:False for k in m.PENDING}};rp=Path(self.tmp.name)/'receipt.json';rp.write_text(json.dumps(r))
  with self.assertRaisesRegex(ValueError,'executing helper'):m.verify_receipt(rp,self.tp,target)
if __name__=='__main__':unittest.main()

