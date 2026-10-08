"""Focused field derivative/protection, UV-seam lineage and invalid-control tests."""
import copy,unittest
import numpy as np
import repair_target_chest_local_profile as c
from place_purposebuilt_pelvis import BASIS
class ProfileTests(unittest.TestCase):
 def setUp(self):
  self.controls=[{'localZMetres':-.04,'xyScale':[.66,.57],'xyTranslationMetres':[0,-.025]},
    {'localZMetres':-.03,'xyScale':[.82,.53],'xyTranslationMetres':[0,.009]},
    {'localZMetres':.01,'xyScale':[1,1],'xyTranslationMetres':[0,0]}]
 def test_c1_derivative_positive_jacobian_and_z_unchanged(self):
  p=np.array([[.1,-.08,-.034],[.09,.03,-.024],[.04,.02,-.05],[.04,.02,.02]])
  q,j=c.profile_field(p,self.controls);eps=1e-7;numeric=np.zeros_like(j)
  for axis in range(3):
   delta=np.eye(3)[axis]*eps;numeric[:,:,axis]=(c.profile_field(p+delta,self.controls)[0]-c.profile_field(p-delta,self.controls)[0])/(2*eps)
  np.testing.assert_allclose(j,numeric,atol=1e-8);np.testing.assert_array_equal(q[:,2],p[:,2])
  self.assertGreater(np.linalg.det(j).min(),.34)
  for z in [-.04,-.03,.01]:
   a=np.array([[.1,.07,z]]);left=c.profile_field(a-[0,0,1e-10],self.controls)[1];right=c.profile_field(a+[0,0,1e-10],self.controls)[1]
   np.testing.assert_allclose(left,right,atol=2e-7)
 def test_complete_crossed_upper_surface_and_uv_seam_protection(self):
  plane=float(np.float32(.01));controls=copy.deepcopy(self.controls);controls[-1]['localZMetres']=plane
  p=np.array([[-.02,-.05,0],[.02,.02,0],[0,.04,.02],[-.02,-.05,0],[.02,.02,0],[0,.04,-.02]],dtype='<f4')
  attrs={'POSITION':p,'NORMAL':np.tile([0,0,1.3],(6,1)).astype('<f4'),'TEXCOORD_0':np.array([[0,0],[1,0],[.5,1],[.2,.3],[.7,.8],[1,1]],dtype='<f4'),'TANGENT':np.tile([1.2,0,0,-1],(6,1)).astype('<f4')};faces=np.array([[0,1,2],[3,5,4]])
  sp=c.subdivide(attrs,faces,[-.04,-.035,-.03,-.025,-.02,-.015,-.01,-.005,0,.005,.01]);q,j=c.profile_field(sp['attributes']['POSITION'].astype(float)@BASIS.T,controls)
  fs=sp['faces'];upper=sp['upperFaceMask'];self.assertTrue(upper.any());self.assertTrue((~upper).any())
  np.testing.assert_array_equal(q[fs[upper]],(sp['attributes']['POSITION'].astype(float)@BASIS.T)[fs[upper]])
  for k,v in attrs.items():
   self.assertEqual(sp['attributes'][k][:len(v)].tobytes(),v.tobytes())
   expected=np.einsum('fci,fij->fcj',sp['barycentric'],v[faces[sp['parentFaceIds']]])
   np.testing.assert_allclose(sp['attributes'][k][fs],expected,atol=6e-8)
  self.assertEqual(set(sp['parentFaceIds']),{0,1})
 def test_nonpositive_unordered_or_nonidentity_controls_rejected(self):
  for idx,value in [(0,{'xyScale':[0,1]}),(0,{'xyScale':[.1,.5]}),(1,{'localZMetres':-.05}),(2,{'xyScale':[.9,1]})]:
   controls=copy.deepcopy(self.controls);controls[idx].update(value)
   with self.assertRaises(ValueError):c.profile_field(np.array([[.1,.1,0]]),controls)
 def test_global_translation_ramp_is_monotonic_c1_and_has_measured_derivative(self):
  ramp={'localZMetres':[-.04,.01],'xyTranslationMetres':[[0,-.025],[0,0]]}
  p=np.column_stack((np.zeros(1001),np.zeros(1001),np.linspace(-.04,.01,1001)))
  q,j=c.profile_field(p,self.controls,ramp);self.assertTrue(np.all(np.diff(q[:,1])>=0))
  np.testing.assert_allclose(j[:,1,2],np.gradient(q[:,1],p[:,2]),atol=.0016)
  np.testing.assert_array_equal(q[-1],p[-1]);np.testing.assert_array_equal(j[-1],np.eye(3))
  sample=np.array([[.1,.03,-.036],[.05,-.01,-.023],[.03,.02,.012]])
  expected=c.profile_field(sample,self.controls,ramp)[1];numerical=np.zeros_like(expected)
  for axis in range(3):
   delta=np.eye(3)[axis]*1e-7;numerical[:,:,axis]=(c.profile_field(sample+delta,self.controls,ramp)[0]-c.profile_field(sample-delta,self.controls,ramp)[0])/(2e-7)
  np.testing.assert_allclose(expected,numerical,atol=1e-8)
  # A positive large shear may turn a proper mapped normal opposite its old direction.
  before=np.array([[[.1,0,-.039],[.1,.001,-.039],[.1,0,-.038]]])
  after=c.profile_field(before.reshape(-1,3),self.controls,ramp)[0].reshape(1,3,3)
  self.assertGreater(c.differential_orientation(before,after,self.controls,ramp)[0],.95)
 def test_ambiguous_tangent_handedness_rejected(self):
  a={'POSITION':np.array([[0,-.02,0],[.01,.03,0],[0,.03,.01]],dtype='<f4'),'NORMAL':np.tile([0,0,1],(3,1)).astype('<f4'),'TEXCOORD_0':np.array([[0,0],[1,0],[.5,1]],dtype='<f4'),'TANGENT':np.array([[1,0,0,1],[1,0,0,-1],[1,0,0,1]],dtype='<f4')}
  with self.assertRaisesRegex(ValueError,'handedness'):c.subdivide(a,np.array([[0,1,2]]),[-.01,.01])
if __name__=='__main__':unittest.main()
