import unittest
import numpy as np
import hand_stub_radial_math as math

class WristRadialMathTests(unittest.TestCase):
    def fixture(self):
        p=np.array([[.03,-.02,-.020],[.04,.01,-.015],[.05,-.03,-.005],[.04,.02,.00736165652051568],[0.,0.,.004]],dtype=float)
        n=np.tile([0.,0.,2.4],(len(p),1));t=np.tile([1.7,0.,0.,-1.],(len(p),1));return p,n,t
    def test_protected_values_and_negative_zero_exact(self):
        p,n,t=self.fixture();p[0,0]=-0.;out=math.transport(p,n,t,-.015,.00736165652051568,.9)
        for a,b in zip((p,n,t),out[:3]):self.assertEqual(a[:2].tobytes(),b[:2].tobytes())
    def test_endpoints_scale_and_slope(self):
        s,d=math.profile(np.array([-.03,-.015,.007,.02]),-.015,.007,.9)
        np.testing.assert_array_equal(s,[1,1,.9,.9]);np.testing.assert_array_equal(d,np.zeros(4))
    def test_c2_join_has_vanishing_second_derivative(self):
        for boundary,side in [(-.015,1),(.007,-1)]:
            approximations=[]
            for eps in (1e-6,1e-7,1e-8):
                _,d=math.profile(np.array([boundary,boundary+side*eps]),-.015,.007,.9)
                approximations.append(abs((d[1]-d[0])/eps))
            # The analytic second derivative tends linearly to zero at either join.
            self.assertLess(approximations[-1],.003)
            for a,b in zip(approximations,approximations[1:]):
                self.assertAlmostEqual(b/a,.1,delta=1e-4)
    def test_analytic_jacobian_agrees_with_finite_difference(self):
        p=np.array([[.03,-.02,-.004],[.04,.01,.002]])
        _,j,_=math.field(p,-.015,.007,.85);eps=1e-7
        for axis in range(3):
            step=np.eye(3)[axis]*eps
            finite=(math.field(p+step,-.015,.007,.85)[0]-math.field(p-step,-.015,.007,.85)[0])/(2*eps)
            np.testing.assert_allclose(finite,j[:,:,axis],rtol=0,atol=2e-9)
    def test_positive_determinant_is_scale_squared(self):
        p,n,t=self.fixture();_,j,_=math.field(p,-.015,.007,.85);s,_=math.profile(p[:,2],-.015,.007,.85)
        np.testing.assert_allclose(np.linalg.det(j),s*s,rtol=0,atol=2e-16);self.assertGreaterEqual(np.linalg.det(j).min(),.85**2-2e-16)
    def test_axial_values_always_byte_exact(self):
        p,n,t=self.fixture();q,_,_=math.field(p,-.015,.007,.85);self.assertEqual(q[:,2].tobytes(),p[:,2].tobytes())
    def test_magnitudes_orthogonality_and_w_preserved(self):
        p,n,t=self.fixture();q,nn,tt,j,active=math.transport(p,n,t,-.015,.007,.9)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=1),np.linalg.norm(n,axis=1),rtol=0,atol=5e-16)
        np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),np.linalg.norm(t[:,:3],axis=1),rtol=0,atol=5e-16)
        np.testing.assert_allclose(np.einsum('ij,ij->i',nn,tt[:,:3]),0,rtol=0,atol=1e-15);self.assertEqual(tt[:,3].tobytes(),t[:,3].tobytes())
    def test_inverse_jacobian_normal_remains_perpendicular_to_transported_surface(self):
        p=np.array([[.03,-.02,.001]]);n=np.array([[0.,2.,0.]]);t=np.array([[3.,0.,0.,1.]])
        _,nn,_,j,_=math.transport(p,n,t,-.015,.007,.9)
        self.assertLess(abs(nn[0]@(j[0]@np.array([0.,0.,1.]))),1e-15)
    def test_input_arrays_not_mutated(self):
        p,n,t=self.fixture();before=[a.tobytes() for a in (p,n,t)];math.transport(p,n,t,-.015,.007,.9);self.assertEqual(before,[a.tobytes() for a in (p,n,t)])
    def test_invalid_scale_or_band_rejected(self):
        for values in [(0,1,0),(0,1,-1),(0,1,1.1),(1,0,.9),(1,1,.9),(0,float('nan'),.9)]:
            with self.assertRaises(ValueError):math.parameters(*values)
    def test_invalid_authored_vectors_rejected(self):
        p,n,t=self.fixture()
        for bad_n,bad_t in [(np.zeros_like(n),t),(n,np.zeros_like(t)),(n,t[:,:3])]:
            with self.assertRaises(ValueError):math.transport(p,bad_n,bad_t,-.015,.007,.9)
    def test_global_displacement_bound_from_quintic_weight(self):
        p,n,t=self.fixture();q,_,_=math.field(p,-.015,.007,.9);s,_=math.profile(p[:,2],-.015,.007,.9)
        expected=(1-s)*np.linalg.norm(p[:,:2],axis=1);np.testing.assert_allclose(np.linalg.norm(q-p,axis=1),expected,rtol=0,atol=1e-17)

    def test_factor_one_is_exact_identity_with_nonorthogonal_authored_tangents(self):
        p,n,t=self.fixture();t[:,2]=.3;p[0,0]=-0.
        out=math.transport(p,n,t,-.015,.007,1.)
        for source,actual in zip((p,n,t),out[:3]):self.assertEqual(source.tobytes(),actual.tobytes())
        np.testing.assert_array_equal(out[3],np.tile(np.eye(3),(len(p),1,1)))
    def test_computed_identity_at_knot_nextafter_and_outside_preserves_shading_bytes(self):
        start=-.015
        p=np.array([[.03,-.02,start],[0.,-0.,np.nextafter(start,np.inf)],[.03,-.02,np.nextafter(start,-np.inf)]])
        n=np.tile([.2,.3,2.4],(len(p),1));t=np.tile([1.7,.4,.3,-1.],(len(p),1))
        out=math.transport(p,n,t,start,.007,.9)
        np.testing.assert_array_equal(out[3],np.tile(np.eye(3),(len(p),1,1)))
        for source,actual in zip((p,n,t),out[:3]):self.assertEqual(source.tobytes(),actual.tobytes())
    def test_identity_still_validates_all_authored_vectors(self):
        p,n,t=self.fixture()
        for bad_n,bad_t in [(np.zeros_like(n),t),(n,np.zeros_like(t))]:
            with self.assertRaises(ValueError):math.transport(p,bad_n,bad_t,-.015,.007,1.)
if __name__=='__main__':unittest.main()