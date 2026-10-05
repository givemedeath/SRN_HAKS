"""Meaningful compact bubble/conservation tests; no actual pelvis export."""
import unittest
import numpy as np
import diagnostic_pelvis_cap_round as roundcap

class CapRoundTests(unittest.TestCase):
 def test_four_mm_center_fixedXY_and_protected_disk_exterior(self):
  p=np.array([[.10,0,.935],[.15,0,.935],[.16,0,.935],[.1,.01,.935]])
  q=roundcap.map_cap(p,[.1,0],.05);self.assertAlmostEqual(q[0,2]-p[0,2],-.004,places=14);np.testing.assert_array_equal(q[:,:2],p[:,:2]);self.assertEqual(q[2].tobytes(),p[2].tobytes());self.assertTrue(np.all(q[:,2]-p[:,2]>=-.004-1e-15))
 def test_zero_height_gradient_and_identityJ_at_support(self):
  center=np.array([0.,0.]);r=.05;p=np.array([[r,0,.935],[0,r,.935],[r*1.01,0,.935]]);h,g,J=roundcap.bubble(p,center,r);self.assertEqual(h.tobytes(),np.zeros(3).tobytes() if np.signbit(h).sum()==0 else (-np.zeros(3)).tobytes());np.testing.assert_array_equal(g,np.zeros_like(p));np.testing.assert_array_equal(J,np.broadcast_to(np.eye(3),J.shape))
 def test_positive_unit_determinant_finite_difference(self):
  p=np.array([[.012,.016,.94],[-.02,.005,.941]]);h,g,J=roundcap.bubble(p,[0,0],.05);np.testing.assert_array_equal(np.linalg.det(J),np.ones(2))
  for i in range(3):
   e=np.eye(3)[i]*1e-7;np.testing.assert_allclose((roundcap.map_cap(p+e,[0,0],.05)-roundcap.map_cap(p-e,[0,0],.05))/2e-7,J[:,:,i],atol=1e-9,rtol=0)
 def test_support_first_and_second_derivative_tends_zero(self):
  r=.05;eps=1e-6;p=np.array([[r-eps,0,.94],[r-eps/2,0,.94],[r,0,.94]]);h,g,J=roundcap.bubble(p,[0,0],r);self.assertLess(abs(g[1,0]/g[0,0]),.26);self.assertLess(abs(h[1]/h[0]),.13);self.assertEqual(h[2],0);self.assertEqual(g[2,0],0)
 def test_serialized_protectedrows_andXY_byte_exact(self):
  P=np.array([[.1,-.272,.02],[.18,-.271,.02],[.1,-.273,.03]],'<f4');world=np.array([[.1,.02,.935],[.18,.02,.936],[.1,.03,.934]]);Q,changed=roundcap.stored_cap_positions(P,world,[.1,.02],.05);self.assertEqual(Q[:,[0,2]].tobytes(),P[:,[0,2]].tobytes());self.assertEqual(Q[~changed].tobytes(),P[~changed].tobytes());self.assertFalse(changed[1]);self.assertTrue(changed[0])
 def test_exact_signedXY_graph_orientation_and_no_degenerate(self):
  p=np.array([[-.04,-.04,.94],[.04,-.04,.94],[0,0,.94],[.04,.04,.94],[-.04,.04,.94]]);F=np.array([[0,1,2],[1,3,2],[3,4,2],[4,0,2]]);q=roundcap.map_cap(p,[0,0],.03);old=np.cross(p[F[:,1]]-p[F[:,0]],p[F[:,2]]-p[F[:,0]]);new=np.cross(q[F[:,1]]-q[F[:,0]],q[F[:,2]]-q[F[:,0]]);np.testing.assert_array_equal(old[:,2],new[:,2]);self.assertTrue((np.linalg.norm(new,axis=1)>0).all())
 def test_generated_shading_mask_includes_boundary_when_coarse_triangle_touches_center(self):
  F=np.array([[0,1,2],[2,3,4]]);changed=np.array([False,False,True,False,False]);np.testing.assert_array_equal(roundcap.shading_rows(F,changed),[0,1,2,3,4])
 def test_invalid_field_inputs_and_depth_rejected(self):
  for p,c,r,d in [(np.array([[np.nan,0,1.]]),[0,0],.05,.004),(np.zeros((2,2)),[0,0],.05,.004),(np.zeros((2,3)),[0],.05,.004),(np.zeros((2,3)),[0,0],0,.004),(np.zeros((2,3)),[0,0],.05,.005)]:
   with self.assertRaises(ValueError):roundcap.bubble(p,c,r,d)

if __name__=='__main__':unittest.main()
