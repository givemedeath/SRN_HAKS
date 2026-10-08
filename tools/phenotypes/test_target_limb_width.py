import unittest
import numpy as np
from scale_target_limb_width import width_matrix, transport, native_transform
from mirror_stock_limb_part import reflection_between_frames
class WidthTests(unittest.TestCase):
 def test_oblique_stock_axis_preserves_axial_and_ap_coordinates(self):
  M,a,b,u=width_matrix([.0147906,-.00482254,-.461701],[1,0,0],.78)
  P=np.array([[.12,.08,.04],[-.13,-.07,-.47],[.01,.02,.09]])
  out=P@M.T
  np.testing.assert_allclose(out@u,P@u,atol=1e-16)
  np.testing.assert_allclose(out@b,P@b,atol=1e-16)
  np.testing.assert_allclose(out@a,.78*(P@a),atol=1e-16)
  self.assertAlmostEqual(np.linalg.det(M),.78);self.assertAlmostEqual(np.linalg.cond(M),1/.78)
 def test_authored_magnitudes_and_tangent_sign_retained(self):
  M,a,b,u=width_matrix([.0147906,-.00482254,-.461701],[1,0,0],.78)
  N=np.array([[.3,.4,.5],[-.1,.8,-.2]]);T=np.array([[.4,-.3,0,1],[.8,.1,0,-1]])
  q,t=transport(N,T,M)
  np.testing.assert_allclose(np.linalg.norm(q,axis=-1),np.linalg.norm(N,axis=-1),atol=1e-15)
  np.testing.assert_allclose(np.linalg.norm(t[:,:3],axis=-1),np.linalg.norm(T[:,:3],axis=-1),atol=1e-15)
  np.testing.assert_allclose(np.sum(q*t[:,:3],axis=-1),0,atol=1e-15)
  np.testing.assert_array_equal(t[:,3],T[:,3])
  inv=N@np.linalg.inv(M);np.testing.assert_allclose(q/np.linalg.norm(q,axis=-1)[:,None],inv/np.linalg.norm(inv,axis=-1)[:,None])
 def test_actual_opposite_frames_reflect_winding_uv_and_handedness(self):
  L=np.eye(4);R=np.eye(4);L[:3,3]=[-.086064722,-.001916,1.016476482];R[:3,3]=[.078837478,-.001916,1.016476482]
  m,w=reflection_between_frames(L,R,[-.003613622,0,0],[1,0,0])
  P=np.array([[[0,0,0],[.1,0,0],[0,.1,0]]]);N=np.tile([0,0,1.],(1,3,1));T=np.tile([1.,0,0,1.],(1,3,1));UV=np.array([[[0,0],[1,0],[0,1]]],float)
  out=native_transform({'positions':P,'normals':N,'tangents':T,'uvNative':UV,'uvGltf':UV},m[:3,:3],m[:3,3],True)
  expected=P@m[:3,:3].T+m[:3,3];np.testing.assert_allclose(out['positions'],expected[:,[0,2,1]])
  np.testing.assert_array_equal(out['uvGltf'],UV[:,[0,2,1]]);np.testing.assert_array_equal(out['tangents'][:,:,3],-T[:,:,3])
  cross=np.cross(out['positions'][:,1]-out['positions'][:,0],out['positions'][:,2]-out['positions'][:,0]);self.assertGreater(float(np.sum(cross*out['normals'].mean(1))),0)
 def test_rejects_parallel_axis_and_nonpositive_scale(self):
  for shaft,hint,factor in [([0,0,1],[0,0,1],.78),([0,0,0],[1,0,0],.78),([0,0,1],[1,0,0],0)]:
   with self.assertRaises((ValueError,RuntimeError,AssertionError)):width_matrix(shaft,hint,factor)
if __name__=='__main__':unittest.main()
