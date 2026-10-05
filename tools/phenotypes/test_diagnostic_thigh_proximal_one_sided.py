import copy,unittest
import numpy as np
from diagnostic_thigh_proximal_one_sided import OneSidedBackward,retains_profile_directions,mapped_rows,native_child,validate_approval
from diagnostic_connector_shear import ConnectorShear
from place_purposebuilt_pelvis import BASIS
class OneSidedBackwardTests(unittest.TestCase):
    def test_lower_and_upper_plateaus_no_upper_return(self):
        f=OneSidedBackward();z=np.array([.5,.8,.85,.93,1.1,2.]);w,d=f.weight(z);self.assertTrue(np.array_equal(w[[0,1]],[0,0]));self.assertTrue(np.array_equal(w[[3,4,5]],[1,1,1]));self.assertTrue(np.array_equal(d[[0,1,3,4,5]],[0,0,0,0,0]));self.assertGreater(w[2],0)
    def test_c2_knots_finite_derivative_matches(self):
        f=OneSidedBackward();z=np.array([.81,.83,.865,.91,.92]);h=1e-7;_,d=f.weight(z);self.assertTrue(np.allclose((f.weight(z+h)[0]-f.weight(z-h)[0])/(2*h),d,rtol=2e-8,atol=1e-8));near=f.weight(np.array([np.nextafter(.8,1),np.nextafter(.93,0)]))[1];self.assertLess(abs(near).max(),1e-25)
    def test_world_xz_inverse_and_positive_det(self):
        f=OneSidedBackward();p=np.array([[.01,.2,.75],[.03,.4,.87],[.05,.6,1.1]]);q=f.transform(p);self.assertTrue(np.array_equal(p[:,[0,2]],q[:,[0,2]]));self.assertTrue(np.array_equal(np.linalg.det(f.jacobian(p)),np.ones(3)));q[:,1]+=f.amount*f.weight(q[:,2])[0];self.assertTrue(np.allclose(q,p,atol=1e-16));self.assertEqual(f.transform(p)[2,1],p[2,1]-.03)
    def test_inverse_transpose_normal_and_gs_tangent(self):
        f=OneSidedBackward();p=np.array([[.1,.2,.865]]);n=np.array([[1.,2.,3.]]);t=np.array([[3.,-1.,.5,-1.]]);nn,tt=f.transport(p,n,t);expected=np.linalg.solve(f.jacobian(p)[0].T,n[0]);expected*=np.linalg.norm(n[0])/np.linalg.norm(expected);self.assertTrue(np.allclose(nn[0],expected));self.assertAlmostEqual(np.linalg.norm(tt[0,:3]),np.linalg.norm(t[0,:3]));self.assertLess(abs(tt[0,:3]@nn[0]),1e-14);self.assertEqual(tt[0,3],-1)
    def test_identity_knots_and_nextafter_nonorthogonal_authored_shading_exact(self):
        f=OneSidedBackward();p=np.array([[0,0,.8],[0,0,.93],[0,0,np.nextafter(.93,1)],[0,0,1.2]]);n=np.tile([0,0,2.],(4,1));t=np.tile([1,0,1.,-1.],(4,1));nn,tt=f.transport(p,n,t);self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())
    def test_geometry_sub_ulp_effect_does_not_cleanup_authored_tangent(self):
        f=OneSidedBackward();p=np.array([[0,1.,np.nextafter(.8,1.)]]);n=np.array([[0,0,2.]]);t=np.array([[1,0,1.,1.]]);q=f.transform(p);self.assertEqual(q.tobytes(),p.tobytes());nn,tt=f.transport(p,n,t,np.any(q!=p,axis=1));self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())
    def test_degenerate_affected_shading_fails_without_outside_cleanup(self):
        f=OneSidedBackward();n=np.array([[0.,0,0]]);t=np.array([[1.,0,0,1]]);nn,tt=f.transport(np.array([[0,0,1.1]]),n,t);self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())
        with self.assertRaises(ValueError):f.transport(np.array([[0,0,.865]]),n,t)
    def test_unused_and_lower_rows_literal_in_serialized_mapping(self):
        world=np.array([[0,.1,.7],[0,.1,.84],[.1,.1,.96],[.2,.1,1.1]],float);P=(world@BASIS).astype('<f4');N=np.tile([0,0,1.],(4,1)).astype('<f4');T=np.tile([1,0,0,1.],(4,1)).astype('<f4');F=np.array([[0,1,2]]);rows,old,changed,shade=mapped_rows(P,N,T,F,np.eye(4),OneSidedBackward());self.assertEqual(rows['POSITION'][[0,3]].tobytes(),P[[0,3]].tobytes());self.assertEqual(rows['NORMAL'][3].tobytes(),N[3].tobytes());self.assertEqual(rows['TANGENT'][3].tobytes(),T[3].tobytes());self.assertEqual(rows['NORMAL'][2].tobytes(),N[2].tobytes());self.assertEqual(rows['TANGENT'][2].tobytes(),T[2].tobytes());self.assertTrue(np.array_equal(changed,[False,True,True,False]))
    def test_continuous_support_can_round_to_literal_position_without_shading_cleanup(self):
        world=np.array([[0,.1,.800001],[0,.1,.85],[.1,.1,.96]]);P=(world@BASIS).astype('<f4');N=np.tile([0,1,0.],(3,1)).astype('<f4');T=np.tile([1,1,0,-1.],(3,1)).astype('<f4');F=np.array([[0,1,2]]);f=OneSidedBackward();rows,old,changed,shade=mapped_rows(P,N,T,F,np.eye(4),f);self.assertGreater(f.weight(old[:,2])[0][0],0);self.assertFalse(changed[0]);self.assertFalse(shade[0]);self.assertEqual(rows['POSITION'][0].tobytes(),P[0].tobytes());self.assertEqual(rows['NORMAL'][0].tobytes(),N[0].tobytes());self.assertEqual(rows['TANGENT'][0].tobytes(),T[0].tobytes())
    def test_native64_parent_corners_and_plateau_attributes_retained(self):
        p=np.array([[[0,.1,.7],[0,.1,.85],[.1,.1,1.1]]]);a={'positions':p,'normals':np.tile([0,0,2.],(1,3,1)),'tangents':np.tile([1,0,1.,-1.],(1,3,1)),'uvGltf':np.zeros((1,3,2)),'sourceTriangleIds':np.array([17])};q=native_child(a,np.eye(4),OneSidedBackward());self.assertEqual(q['oneSidedParentPositions'].tobytes(),p.tobytes());self.assertEqual(q['uvGltf'].tobytes(),a['uvGltf'].tobytes());self.assertEqual(q['normals'][0,2].tobytes(),a['normals'][0,2].tobytes());self.assertEqual(q['tangents'][0,2].tobytes(),a['tangents'][0,2].tobytes());self.assertTrue(np.array_equal(q['positions'][0,:,2],p[0,:,2]))
    def test_positive_c2_symmetric_window_can_still_create_shelf_and_is_rejected(self):
        z=np.linspace(.88,.99,200);old=.5*z;bad=ConnectorShear(np.zeros(3),np.array([0.,0,1.]),np.array([0.,-.02,0.]),.9335863177830892);w,_=bad.weight(z);new=old-.02*w;self.assertFalse(retains_profile_directions(old,new));f=OneSidedBackward();w,_=f.weight(z);self.assertTrue(retains_profile_directions(old,old-.03*w));self.assertTrue(np.all(np.linalg.det(f.jacobian(np.c_[np.zeros(len(z)),old,z]))==1))
    def test_positive_j_and_c2_are_not_profile_acceptance(self):
        self.assertFalse(retains_profile_directions([0,1,2,3],[0,1,1,3]));self.assertFalse(retains_profile_directions([0,1,2,3],[0,2,1,3]));self.assertTrue(retains_profile_directions([3,2,1,0],[2,1.5,.9,-.1]))
    def test_bad_field_bounds_fail(self):
        for args in [(0,.8,.93),(.03,.93,.8),(.03,float('nan'),.93)]:
            with self.assertRaises(ValueError):OneSidedBackward(*args)
if __name__=='__main__':unittest.main()

