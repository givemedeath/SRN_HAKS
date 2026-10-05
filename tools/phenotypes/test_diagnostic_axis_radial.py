"""Affine axial conservation, shading, source archival and diagnostic rejection guards."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import diagnostic_axis_radial as radial
import target_contract as tc
import target_part_pipeline as pipeline
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,rotation_xyz,write_glb
from test_target_part_pipeline import target_fixture
from test_mirror_stock_limb_part import fixture

class AxisTests(unittest.TestCase):
 def setUp(self):self.h=np.array([-.14,.03,1.]);self.k=np.array([-.09,-.12,.57]);self.M,self.d,self.L=radial.radial_matrix(self.h,self.k)
 def test_pivots_axial_and_inverse_identity(self):
  rng=np.random.default_rng(142);p=rng.normal(size=(30,3));q=radial.transform_positions(p,self.M)
  np.testing.assert_allclose((q-self.h)@self.d,(p-self.h)@self.d,atol=1e-15,rtol=0);np.testing.assert_allclose(radial.transform_positions(np.array([self.h,self.k]),self.M),[self.h,self.k],atol=1e-15,rtol=0);np.testing.assert_allclose(radial.transform_positions(q,np.linalg.inv(self.M)),p,atol=1e-15,rtol=0)
  self.assertAlmostEqual(np.linalg.det(self.M[:3,:3]),.7225);np.testing.assert_allclose(np.sort(np.linalg.svd(self.M[:3,:3],compute_uv=False)),[.85,.85,1.],atol=1e-15)
 def test_width_depth_reduce_but_length_remains(self):
  r=np.array([1.,0,0]);r-=self.d*(r@self.d);r/=np.linalg.norm(r);b=np.column_stack([r,np.cross(self.d,r),self.d]);p=np.array([[-.1,-.2,-.04],[.13,.24,self.L+.02]])@b.T+self.h;q=radial.transform_positions(p,self.M)
  np.testing.assert_allclose(np.ptp((q-self.h)@b,axis=0),np.ptp((p-self.h)@b,axis=0)*[.85,.85,1],atol=1e-15,rtol=0)
 def test_jacobian_finite_difference(self):
  p=np.array([[.03,.17,.68]])
  for j in range(3):
   e=np.eye(3)[j]*1e-7;a=radial.transform_positions(p+e,self.M)[0];b=radial.transform_positions(p-e,self.M)[0];np.testing.assert_allclose((a-b)/2e-7,self.M[:3,j],atol=1e-9,rtol=0)
 def test_covector_and_GS_nonorthogonal_authored_tangent(self):
  n=np.array([[.3,.4,1.7]]);t=np.array([[1.2,.05,.2,-1.]]);nn,tt=radial.transport(n,t,self.M[:3,:3]);expected=np.linalg.solve(self.M[:3,:3].T,n[0]);expected*=np.linalg.norm(n)/np.linalg.norm(expected);np.testing.assert_allclose(nn[0],expected,atol=1e-15,rtol=0)
  self.assertAlmostEqual(np.linalg.norm(nn),np.linalg.norm(n));self.assertAlmostEqual(np.linalg.norm(tt[:,:3]),np.linalg.norm(t[:,:3]));self.assertAlmostEqual(nn[0]@tt[0,:3],0,places=14);self.assertEqual(tt[0,3],-1.)
 def test_directional_normal_is_perpendicular_to_transformed_surface(self):
  a=np.array([.3,.2,-.04]);b=np.array([-.08,.17,.1]);n=np.cross(a,b)[None];t=np.r_[a,-1.][None];nn,tt=radial.transport(n,t,self.M[:3,:3]);self.assertAlmostEqual(nn[0]@(self.M[:3,:3]@a),0,places=14);self.assertAlmostEqual(nn[0]@(self.M[:3,:3]@b),0,places=14)
 def test_bad_factor_axis_and_shading_rejected(self):
  for f in [1.,.84,0.,-.85,float('nan')]:
   with self.assertRaises(ValueError):radial.radial_matrix(self.h,self.k,f)
  for h,k in [(self.h,self.h),(self.h,[float('nan'),0,0]),([0,0],self.k)]:
   with self.assertRaises(ValueError):radial.radial_matrix(h,k)
  for n,t,j in [(np.zeros((1,3)),[[1,0,0,1]],np.eye(3)),([[0,0,1]],[[0,0,1,1]],np.eye(3)),([[0,0,1]],[[1,0,0,0]],np.eye(3)),([[0,0,1]],[[1,0,0,1]],np.diag([-1.,1,1]))]:
   with self.assertRaises(ValueError):radial.transport(n,t,j)
 def test_serialized_face_inversion_and_new_degeneracy_rejected(self):
  p=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4');f=np.array([[0,1,2]])
  for q in [p[[0,2,1]],np.zeros_like(p)]:
   with self.assertRaises(ValueError):radial.verify_discrete(p,q,f)

class LineageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);td=target_fixture();td['identity']['race']='troll'
  for j,p in [('lthigh_g',[-.14,.03,1]),('lshin_g',[-.09,-.04,.57]),('lfoot_g',[-.08,-.11,.16])]:
   H=np.eye(4);H[:3,:3]=rotation_xyz([12,-8,21]);H[:3,3]=p;td['rig']['frames']['working'][j]=H.tolist(); HR=H.copy();HR[:3,3]*=10/7;td['rig']['frames']['runtime'][j]=HR.tolist()
  self.target=self.root/'target.json';self.target.write_text(json.dumps(td));self.td=td;doc,bb=fixture();self.source=self.root/'source.glb';write_glb(self.source,doc,bb);self.job=self.root/'job.json';self.job.write_text(json.dumps({'state':'success','promptId':'fixture','outputs':[{'localPath':str(self.source),'sha256':tc.sha(self.source)}]}))
  fc={'schemaVersion':2,'operation':'fit','part':'legl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':tc.sha(self.target),'source':str(self.source),'sourceSha256':tc.sha(self.source),'sourceReceipt':str(self.job),'sourceReceiptSha256':tc.sha(self.job),'uniformScale':.45,'rotationDegreesXYZ':[13,-3,11],'sourceAnchorNwn':[.03,.05,.11],'targetAnchorLocal':[0,0,0]};fp=self.root/'fit.json';fp.write_text(json.dumps(fc));self.parentpath=pipeline.execute(fp,self.root/'parent');self.parent=json.loads(self.parentpath.read_text());self.protected=self.root/'foot-pelvis-rig.bin';self.protected.write_bytes(b'protected')
 def tearDown(self):self.tmp.cleanup()
 def config(self):return {'schemaVersion':1,'kind':'troll-left-leg-axis-radial-diagnostic-config','diagnosticOnly':True,'part':'legl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':tc.sha(self.target),'rigRevision':self.td['rig']['revision'],'parentReceipt':str(self.parentpath),'parentReceiptSha256':tc.sha(self.parentpath),'parentCandidate':self.parent['candidate'],'parentCandidateSha256':self.parent['candidateSha256'],'factor':.85,'originWorld':np.asarray(self.td['rig']['frames']['working']['lthigh_g'])[:3,3].tolist(),'distalWorld':np.asarray(self.td['rig']['frames']['working']['lshin_g'])[:3,3].tolist(),'protectedInputs':{str(self.protected):tc.sha(self.protected)}}
 def run_config(self,c,name='trial'):
  p=self.root/(name+'-config.json');p.write_text(json.dumps(c));rp=radial.execute(p,self.root/name);return rp,json.loads(rp.read_text())
 def test_stored_active_attrs_and_all_original_metadata_preserved(self):
  rp,r=self.run_config(self.config());old,bb=read_glb(self.parent['candidate']);new,nb=read_glb(r['candidate']);oa=old['meshes'][0]['primitives'][0];na=new['meshes'][0]['primitives'][0];self.assertEqual(nb[:len(bb)],bb);self.assertEqual(embedded_maps(old,bb),embedded_maps(new,nb));self.assertEqual(old['accessors'],new['accessors'][:-3]);self.assertEqual(old['bufferViews'],new['bufferViews'][:-3]);self.assertEqual(oa['indices'],na['indices']);self.assertEqual(oa['attributes']['TEXCOORD_0'],na['attributes']['TEXCOORD_0']);self.assertEqual(oa['attributes']['COLOR_0'],na['attributes']['COLOR_0'])
  for sem,aid in oa['attributes'].items():self.assertEqual(accessor(old,bb,aid,allow_normalized=True).tobytes(),accessor(new,nb,aid,allow_normalized=True).tobytes())
  self.assertEqual(r['kind'],'troll-left-leg-axis-radial-diagnostic');self.assertNotEqual(r['kind'],'target-part-geometry');self.assertEqual(r['statureApplications'],0);self.assertEqual(r['attachmentWorld'],self.parent['attachmentWorld']);self.assertFalse(r['materialAccepted']);self.assertEqual(self.protected.read_bytes(),b'protected')
  for key in radial.TOPOLOGY_KEYS:self.assertEqual(r['proof']['beforeTopology'][key],r['proof']['afterTopology'][key])
  with np.load(self.parent['nativeCornerArchive']['path']) as pa,np.load(r['nativeCornerArchive']['path']) as a:
   for key in ['sourceTriangleIds','sourceCornerOrder','uvGltf','uvNative','primitiveIds','sourcePositions','sourceNormals','sourceUVNative','tangentTriangleIds']:self.assertTrue(np.array_equal(pa[key],a[key]),key)
 def test_changed_origin_distal_revision_and_factor_rejected(self):
  for key,val in [('originWorld',[0,0,0]),('distalWorld',[0,0,0]),('rigRevision','guessed'),('factor',.9),('coordinateSpace','runtime'),('part','footl'),('uniformScale',.5)]:
   c=self.config();c[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):self.run_config(c,key)
 def test_changed_protected_source_and_parent_pins_rejected(self):
  c=self.config();self.protected.write_bytes(b'changed')
  with self.assertRaises(ValueError):self.run_config(c,'protected')
  for key in ['parentCandidateSha256','parentReceiptSha256','targetContractSha256']:
   c=self.config();c[key]='wrong'
   with self.assertRaises(ValueError):self.run_config(c,key)
 def test_cumulative_diagnostic_and_right_side_rejected(self):
  path,r=self.run_config(self.config());c=self.config();c.update(parentReceipt=str(path),parentReceiptSha256=tc.sha(path),parentCandidate=r['candidate'],parentCandidateSha256=r['candidateSha256'])
  with self.assertRaises(ValueError):self.run_config(c,'cumulative')
  c=self.config();c['part']='legr'
  with self.assertRaises(ValueError):self.run_config(c,'right')
 def test_wrong_archive_face_correspondence_rejected(self):
  with np.load(self.parent['nativeCornerArchive']['path']) as a:arc={k:a[k].copy() for k in a.files}
  arc['sourceTriangleIds'][0]=42;ap=self.root/'bad.npz';np.savez_compressed(ap,**arc);parent=copy.deepcopy(self.parent);parent['nativeCornerArchive']={'path':str(ap),'sha256':tc.sha(ap)};pp=self.root/'bad-parent.json';pp.write_text(json.dumps(parent));c=self.config();c.update(parentReceipt=str(pp),parentReceiptSha256=tc.sha(pp))
  with self.assertRaisesRegex(ValueError,'association'):self.run_config(c,'bad-archive')
 def test_duplicate_output_not_overwritten(self):
  path,r=self.run_config(self.config());h=tc.sha(path)
  with self.assertRaisesRegex(ValueError,'Fresh immutable'):self.run_config(self.config())
  self.assertEqual(h,tc.sha(path))
 def test_original_target_human_not_reinterpreted(self):
  td=copy.deepcopy(self.td);td['identity']['race']='human';self.target.write_text(json.dumps(td));c=self.config()
  with self.assertRaisesRegex(ValueError,'Troll male'):self.run_config(c,'human')

if __name__=='__main__':unittest.main()

