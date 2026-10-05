import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_shin_girth90 as m
import diagnostic_axis_radial as oldradial
import diagnostic_selected_working_opposite as oldmirror
class ShinGirth90Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.tp=Path(self.tmp.name)/'target.json';self.tp.write_text('{}');H=np.eye(4);H[:3,3]=[-.19,-.02,.63];K=np.eye(4);K[:3,3]=[-.15,.035,.12];self.H=H;self.M,self.d,self.L=m.matrix(H[:3,3],K[:3,3]);self.ML=np.linalg.inv(H)@self.M@H;self.target={'id':'test','identity':{'race':'troll','gender':'male','prefix':'pmg0'},'rig':{'revision':'test','frames':{'working':{'lshin_g':H,'lfoot_g':K}}},'models':{'shinl':'pmg0_shinl001'}}
  self.c={'schemaVersion':1,'kind':'root-review-only-shin-girth90-after85-config','coordinateSpace':'working','diagnosticOnly':True,'part':'shinl','joint':'lshin_g','sourcePart':'shinl','sourceJoint':'lshin_g','sourceKind':'troll-left-leg-axis-radial-diagnostic','factor':.90,'axialFactor':1.,'parentFactor':.85,'effectiveOriginalDonorRadialFactor':.765,'statureApplications':0,'factor85OrFitReapplied':False,'uniformXYZScaleUsed':False,'terminalTaperOrWindowUsed':False,'mirrorApplied':False,'rigAndKneeAnkleAnchorsChanged':False,'sourceReceipt':{'sha256':m.PARENT_SHA},'targetContract':str(self.tp),'targetContractSha256':m.tc.sha(self.tp),'rigRevision':'test','model':'pmg0_shinl001','attachmentWorld':H.tolist(),'axisOriginWorld':H[:3,3].tolist(),'axisDistalWorld':K[:3,3].tolist(),'axisUnitWorld':self.d.tolist(),'jointSpanMetres':self.L,'worldAffine':self.M.tolist(),'localAffine':self.ML.tolist()}
 def test_spd_and_both_frozen_joint_origins(self):
  np.testing.assert_allclose(np.linalg.eigvalsh(self.M[:3,:3]),[.9,.9,1.],rtol=0,atol=4e-16);self.assertAlmostEqual(np.linalg.det(self.M[:3,:3]),.81);a=np.asarray(self.c['axisOriginWorld']);b=np.asarray(self.c['axisDistalWorld']);np.testing.assert_allclose(m.transform_positions(np.array([a,b]),self.M),[a,b],rtol=0,atol=2e-16)
 def test_all_axial_coordinates_preserved_transverse_only90(self):
  rng=np.random.default_rng(8);a=np.asarray(self.c['axisOriginWorld']);p=rng.normal(size=(121,3))*.08+a;q=m.transform_positions(p,self.M);x=(p-a)@self.d;y=(q-a)@self.d;np.testing.assert_allclose(x,y,rtol=0,atol=2e-16);np.testing.assert_allclose(q-a-y[:,None]*self.d,.9*(p-a-x[:,None]*self.d),rtol=0,atol=2e-16)
 def test_additional90_after85_is765_not_repeated85_or_uniform_shortening(self):
  M85,_,_=oldradial.radial_matrix(self.c['axisOriginWorld'],self.c['axisDistalWorld']);rng=np.random.default_rng(15);p=rng.normal(size=(23,3))*.1+np.asarray(self.c['axisOriginWorld']);q=m.transform_positions(m.transform_positions(p,M85),self.M);a=np.asarray(self.c['axisOriginWorld']);x=(p-a)@self.d;rad=p-a-x[:,None]*self.d;np.testing.assert_allclose((q-a)@self.d,x,rtol=0,atol=2e-16);np.testing.assert_allclose(q-a-x[:,None]*self.d,.765*rad,rtol=0,atol=2e-16)
 def test_contour_directions_and_station_changes_homothetic_no_window(self):
  M,_,_=m.matrix([0,0,0],[0,0,1]);z=np.linspace(-.05,.65,101);r=.075+.015*np.sin(4*z);p=np.c_[r,.03+.005*z,z];q=m.transform_positions(p,M);self.assertEqual(q[:,2].tobytes(),p[:,2].tobytes());np.testing.assert_allclose(q[:,:2],.9*p[:,:2],rtol=0,atol=2e-17);self.assertTrue(np.array_equal(np.sign(np.diff(p[:,0])),np.sign(np.diff(q[:,0]))));self.assertNotEqual(q[0,0],p[0,0]);self.assertNotEqual(q[-1,0],p[-1,0])
 def test_normal_inverse_transpose_tangent_GS_magnitudes_W(self):
  n=np.array([[2.,3,1],[1.,2,4]]);t=np.array([[3.,1,2,1],[2.,3,1,-1]]);nn,tt=m.transport(n,t,self.M[:3,:3]);np.testing.assert_allclose(np.linalg.norm(nn,axis=1),np.linalg.norm(n,axis=1),atol=1e-15);np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),np.linalg.norm(t[:,:3],axis=1),atol=1e-15);self.assertEqual(tt[:,3].tobytes(),t[:,3].tobytes());np.testing.assert_allclose((nn*tt[:,:3]).sum(1)/np.linalg.norm(nn,axis=1)/np.linalg.norm(tt[:,:3],axis=1),0,rtol=0,atol=8*np.finfo(float).eps)
 def test_actual_affine_surface_cofactor_orientation(self):
  p=np.array([[.02,.04,.12],[.1,.03,.03],[.01,.08,.05]]);q=m.transform_positions(p,self.M);old=np.cross(p[1]-p[0],p[2]-p[0]);new=np.cross(q[1]-q[0],q[2]-q[0]);expected=np.linalg.det(self.M[:3,:3])*np.linalg.solve(self.M[:3,:3].T,old);np.testing.assert_allclose(new,expected,rtol=0,atol=2e-17);self.assertGreater(new@expected,0)
 def test_inactive_invalid_shading_is_literal_not_accepted_active(self):
  rows={'POSITION':np.array([[.1,.2,.3],[.11,.2,.3],[.1,.21,.3],[8.,9,10]],dtype='<f4'),'NORMAL':np.array([[0.,1,0]]*3+[[0,0,0]],dtype='<f4'),'TANGENT':np.array([[1.,0,0,1]]*3+[[0,0,0,0]],dtype='<f4')};out,active=m.mapped_rows(rows,np.array([[0,1,2]]),self.ML)
  for s in out:self.assertEqual(out[s][-1].tobytes(),rows[s][-1].tobytes())
  self.assertFalse(active[-1]);self.assertTrue((active[:3]).all())
 def test_f64_native_source_history_uv_corner_records_unchanged(self):
  p=np.array([[[.01,.02,.1],[.03,.02,.1],[.01,.04,.1]]]);n=np.array([[[0.,2.,0.]]*3]);t=np.array([[[3.,0.,0.,-1.]]*3]);arc={'positions':p,'normals':n,'tangents':t,'sourceTriangleIds':np.array([12]),'sourceCornerOrder':np.array([[0,1,2]]),'uvGltf':np.array([[[.1,.2],[.3,.4],[.5,.6]]]),'radialParentRawPositions':p.copy(),'sourceNormals':n.copy()};out=m.native_child(arc,self.ML)
  for k in arc:
   if k not in ['positions','normals','tangents']:self.assertEqual(out[k].tobytes(),arc[k].tobytes())
  self.assertEqual(out['shin90ParentPositions'].tobytes(),p.tobytes());np.testing.assert_allclose(out['positions'],m.transform_positions(p.reshape(-1,3),self.ML).reshape(p.shape),rtol=0,atol=0)
 def test_exact_parent_recipe_accepts_and_other_parts_runtime_repeats_reject(self):
  m.validate_config(self.c,self.tp,self.target)
  for k,v in [('part','legl'),('sourcePart','shinr'),('coordinateSpace','runtime'),('factor',.85),('factor',.765),('axialFactor',.9),('factor85OrFitReapplied',True),('statureApplications',1),('uniformXYZScaleUsed',True),('terminalTaperOrWindowUsed',True),('mirrorApplied',True)]:
   c=copy.deepcopy(self.c);c[k]=v
   with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
  c=copy.deepcopy(self.c);c['sourceReceipt']['sha256']='0'*64
  with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
 def test_Human_female_frozen_axis_and_factor_aliases_reject(self):
  for k,v in [('race','human'),('gender','female'),('prefix','pmh0')]:
   target=copy.deepcopy(self.target);target['identity'][k]=v
   with self.assertRaises(ValueError):m.validate_config(self.c,self.tp,target)
  c=copy.deepcopy(self.c);c['axisDistalWorld'][2]+=.01
  with self.assertRaises(ValueError):m.validate_config(c,self.tp,self.target)
  for f in [.85,.765,1.1,1.,.90+1e-12]:
   with self.assertRaises(ValueError):m.matrix([0,0,0],[0,0,1],f)
 def test_exact_executor_and_approval_not_alias(self):
  m.validate_executor({'expectedExecutor':{'path':str(Path(m.__file__).resolve()),'sha256':m.tc.sha(m.__file__)}})
  for c in [{},{'expectedExecutor':{'path':str(self.tp),'sha256':m.tc.sha(self.tp)}},{'expectedExecutor':{'path':str(Path(m.__file__).resolve()),'sha256':'0'*64}}]:
   with self.assertRaises(ValueError):m.validate_executor(c)
  a={'kind':'root-approved-shin-girth90-after85-diagnostic','reviewedBy':'/root','authorizeImplementationAndOneFreshExport':True,'configuration':copy.deepcopy(self.c)};m.validate_approval(a,self.c);a['kind']='root-approved-upper-arm-girth110-diagnostic'
  with self.assertRaises(ValueError):m.validate_approval(a,self.c)
 def test_degenerate_bind_or_active_shading_reject(self):
  with self.assertRaises(ValueError):m.matrix([0,0,0],[0,0,0])
  with self.assertRaises(ValueError):m.transport(np.array([[0.,0,0]]),np.array([[1.,0,0,1]]),self.M[:3,:3])
 def test_historical_radial_and_selected_mirror_meanings_unchanged(self):
  with self.assertRaises(ValueError):oldradial.radial_matrix([0,0,0],[0,0,1],.90)
  self.assertEqual(set(oldmirror.PAIRS),{'legl','bicepl'});self.assertNotIn('shinl',oldmirror.PAIRS)
if __name__=='__main__':unittest.main()
