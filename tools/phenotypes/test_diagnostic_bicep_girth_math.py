import unittest
import numpy as np
from diagnostic_bicep_girth_math import matrix,points,shading
class BicepGirthMathTests(unittest.TestCase):
    def test_exact_factor_guard_not_leg_85_or_uniform_length_scale(self):
        for f in [.85,1.,1.15,1]:
            with self.assertRaises(ValueError):matrix([0,0,0],[1,2,3],f)
    def test_spd_eigenvalues_determinant_and_unchanged_joint_anchors(self):
        a=np.array([-.27,-.049,1.557]);b=np.array([-.24,-.064,1.266]);M,d,L=matrix(a,b);self.assertTrue(np.allclose(np.linalg.eigvalsh(M[:3,:3]),[1,1.1,1.1],atol=1e-15));self.assertAlmostEqual(np.linalg.det(M[:3,:3]),1.21);self.assertTrue(np.allclose(points(np.array([a,b]),M),[a,b],atol=3e-16));self.assertTrue(np.allclose(M[:3,:3]@d,d,atol=2e-16))
    def test_all_points_axial_projection_preserved_and_radial_times110(self):
        a=np.array([-.27,-.05,1.55]);b=np.array([-.24,-.065,1.27]);M,d,L=matrix(a,b);rng=np.random.default_rng(4);p=rng.normal(size=(100,3))*.1+a;q=points(p,M);x=(p-a)@d;y=(q-a)@d;self.assertTrue(np.allclose(x,y,atol=3e-16));rad=p-a-x[:,None]*d;new=q-a-y[:,None]*d;self.assertTrue(np.allclose(new,rad*1.1,atol=3e-16))
    def test_constant_affine_whole_contour_equivalence_no_station_window_or_new_shelf(self):
        a=np.zeros(3);M,d,L=matrix(a,[0,0,1]);z=np.linspace(-.08,1.008,50);r=.08+.02*np.sin(z*3);p=np.c_[r,.03+z*.005,z];q=points(p,M);self.assertTrue(np.array_equal(q[:,2],p[:,2]));self.assertTrue(np.allclose(q[:,0],p[:,0]*1.1));self.assertTrue(np.array_equal(np.sign(np.diff(q[:,0])),np.sign(np.diff(p[:,0]))));self.assertTrue(np.allclose(np.diff(q[:,0]),1.1*np.diff(p[:,0])));self.assertNotEqual(q[0,0],p[0,0]);self.assertNotEqual(q[-1,0],p[-1,0])
    def test_affine_surface_normal_cofactor_and_winding_orientation(self):
        M,d,L=matrix([0,0,0],[1,2,3]);p=np.array([[0,0,0],[.1,.2,.05],[-.02,.01,.1]]);q=points(p,M);n=np.cross(p[1]-p[0],p[2]-p[0]);g=np.cross(q[1]-q[0],q[2]-q[0]);expected=np.linalg.det(M[:3,:3])*np.linalg.solve(M[:3,:3].T,n);self.assertTrue(np.allclose(g,expected,atol=1e-17));self.assertGreater(g@n,0)
    def test_authored_magnitudes_inverse_transpose_gs_and_w(self):
        M,d,L=matrix([0,0,0],[1,2,3]);n=np.array([[1.,2,1.],[2,1.,3]]);t=np.array([[3.,1,0,1.],[1,1.,1,-1]]);nn,tt=shading(n,t,M[:3,:3]);self.assertTrue(np.allclose(np.linalg.norm(nn,axis=1),np.linalg.norm(n,axis=1)));self.assertTrue(np.allclose(np.linalg.norm(tt[:,:3],axis=1),np.linalg.norm(t[:,:3],axis=1)));self.assertEqual(tt[:,3].tobytes(),t[:,3].tobytes());self.assertTrue(np.allclose((nn*tt[:,:3]).sum(1),0,atol=2e-15))
    def test_rigid_frame_conjugation_proves_world_equivalence(self):
        angle=.37;H=np.eye(4);H[:3,:3]=[[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]];H[:3,3]=[.2,-.1,.9];M,d,L=matrix(H[:3,3],[-.2,.1,.4]);ML=np.linalg.inv(H)@M@H;p=np.array([[.1,.2,.3],[-.1,.05,.09]]);self.assertTrue(np.allclose(points(points(p,ML),H),points(points(p,H),M),atol=3e-16))
    def test_degenerate_bind_or_active_shading_rejected(self):
        with self.assertRaises(ValueError):matrix([0,0,0],[0,0,0])
        with self.assertRaises(ValueError):shading(np.array([[0.,0,0]]),np.array([[1.,0,0,1]]),np.eye(3))
if __name__=='__main__':unittest.main()
