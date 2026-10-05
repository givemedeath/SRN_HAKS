import copy,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_shin_girth90_opposite as m
import diagnostic_selected_working_opposite as old
from mirror_stock_limb_part import reflection_between_frames
class Shin90OppositeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.tp=Path(self.tmp.name)/'target.json';self.tp.write_text('{}');H=np.eye(4);H[:3,3]=[-.1,-.009,.564];G=np.eye(4);G[:3,3]=[.1,-.009,.564];self.H,self.G=H,G;M,R=reflection_between_frames(H,G,[0.,0.,0.],[1.,0.,0.]);self.M,self.R=M,R;self.target={'identity':{'race':'troll','gender':'male','prefix':'pmg0'},'rig':{'revision':'test','frames':{'working':{'lshin_g':H,'rshin_g':G}}},'models':{'shinr':'pmg0_shinr001'}};self.c={'schemaVersion':1,'kind':'root-review-only-shin90-after85-opposite-config','coordinateSpace':'working','diagnosticOnly':True,'sourcePart':'shinl','part':'shinr','sourceJoint':'lshin_g','joint':'rshin_g','sourceKind':m.PARENT_KIND,'sourceReceipt':{'sha256':m.PARENT_SHA},'statureApplications':0,'factor85Or90FitFieldReapplied':False,'sourceCornerPermutation':[0,2,1],'tangentWReflectionFactor':-1,'planeOriginWorld':[0.,0.,0.],'planeNormalWorld':[1.,0.,0.],'targetContract':str(self.tp),'targetContractSha256':m.tc.sha(self.tp),'rigRevision':'test','model':'pmg0_shinr001','sourceAttachmentWorld':H.tolist(),'attachmentWorld':G.tolist(),'sourceToAttachmentLocal':M.tolist(),'reflectionWorld':R.tolist()}
 def test_exact_new_parent_pair_accepts(self):m.validate_config(self.c,self.tp,self.target)
 def test_historical85_thigh_arm_aliases_and_other_receipt_reject(self):
  for k,v in [('sourceKind','troll-left-leg-axis-radial-diagnostic'),('sourceKind','target-part-diagnostic-upper-arm-girth110'),('sourcePart','legl'),('part','legr')]:
   c=copy.deepcopy(self.c);c[k]=v
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
  c=copy.deepcopy(self.c);c['sourceReceipt']['sha256']='0'*64
  with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_Human_female_runtime_repeat_winding_and_W_reject(self):
  for k,v in [('race','human'),('gender','female'),('prefix','pmh0')]:
   target=copy.deepcopy(self.target);target['identity'][k]=v
   with self.assertRaises(ValueError):m.validate_config(self.c,self.tp,target)
  for k,v in [('coordinateSpace','runtime'),('factor85Or90FitFieldReapplied',True),('statureApplications',1),('sourceCornerPermutation',[0,1,2]),('tangentWReflectionFactor',1),('joint','rfoot_g')]:
   c=copy.deepcopy(self.c);c[k]=v
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_world_reflection_frozen_frame_conjugation(self):
  p=np.array([[.1,.2,.3],[-.05,.02,-.3]]);q=p@self.M[:3,:3].T+self.M[:3,3];w=p@self.H[:3,:3].T+self.H[:3,3];z=q@self.G[:3,:3].T+self.G[:3,3];np.testing.assert_allclose(z,w@self.R[:3,:3].T,rtol=0,atol=3e-16);self.assertEqual(np.linalg.det(self.M[:3,:3]),-1.)
 def test_authoritative_current_arrays_mirror_historical_fields_literal(self):
  p=np.array([[[.1,.2,.3],[.3,.2,.3],[.1,.4,.3]]]);n=np.array([[[0.,0.,2.]]*3]);t=np.array([[[3.,0.,0.,1.]]*3]);uv=np.array([[[.1,.2],[.3,.4],[.5,.6]]]);a={'positions':p,'normals':n,'tangents':t,'uvNative':uv,'uvGltf':uv.copy(),'sourceCornerOrder':np.array([[0,1,2]]),'sourceTriangleIds':np.array([1]),'primitiveIds':np.array([0]),'shin90ParentPositions':p.copy(),'radialParentRawNormals':n.copy()};out=m.mirror_archive(a,self.M);np.testing.assert_array_equal(out['positions'],(p@self.M[:3,:3].T+self.M[:3,3])[:,[0,2,1]]);np.testing.assert_array_equal(out['sourceCornerOrder'],[[0,2,1]]);np.testing.assert_array_equal(out['tangents'][...,3],-t[:,[0,2,1],3]);self.assertEqual(out['shin90ParentPositions'].tobytes(),p.tobytes());self.assertEqual(out['radialParentRawNormals'].tobytes(),n.tobytes())
 def test_reflected_winding_surface_orientation(self):
  p=np.array([[.1,.2,.3],[.3,.2,.3],[.1,.4,.3]]);q=p@self.M[:3,:3].T+self.M[:3,3];on=np.cross(p[1]-p[0],p[2]-p[0]);gn=np.cross(q[2]-q[0],q[1]-q[0]);np.testing.assert_array_equal(gn,on@self.M[:3,:3].T)
 def test_executor_and_root_approval_exact(self):
  m.validate_executor({'expectedExecutor':{'path':str(Path(m.__file__).resolve()),'sha256':m.tc.sha(m.__file__)}})
  for e in [{},{'expectedExecutor':{'path':str(self.tp),'sha256':m.tc.sha(self.tp)}},{'expectedExecutor':{'path':str(Path(m.__file__).resolve()),'sha256':'0'*64}}]:
   with self.assertRaises(ValueError):m.validate_executor(e)
  a={'kind':'root-approved-shin-girth90-after85-opposite-mirror','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':copy.deepcopy(self.c)};m.validate_approval(a,self.c);a['configuration']['factor85Or90FitFieldReapplied']=True
  with self.assertRaises(ValueError):m.validate_approval(a,self.c)
 def test_old_selected_helper_pair_enum_stays_unchanged(self):self.assertEqual(set(old.PAIRS),{'legl','bicepl'});self.assertNotIn('shinl',old.PAIRS)
if __name__=='__main__':unittest.main()
