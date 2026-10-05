"""Focused foot-stub Jacobian, authored shading and protected-anatomy regressions."""
import unittest
import numpy as np
import foot_upper_stub_math as m

class FootStubMathTests(unittest.TestCase):
    def values(self):
        p=np.array([[.03,-.02,.02],[.04,.01,.0273241988],[.05,-.03,.04],
                    [.04,.02,.055606],[.03,.01,.065],[0.,-0.,.04]],float)
        n=np.tile([.2,.3,2.4],(len(p),1));t=np.tile([1.7,.4,.3,-1.],(len(p),1))
        protected=np.array([True,True,False,False,False,False]);return p,n,t,protected
    def call(self,p,n,t,protected,k=.5855251506097975):
        return m.transport(p,n,t,protected,.0273241988,.055606,k)
    def test_all_lower_foot_and_axial_and_w_bytes_protected(self):
        p,n,t,pr=self.values();p[0,0]=-0.;q,nn,tt,_,_=self.call(p,n,t,pr)
        for old,new in zip((p,n,t),(q,nn,tt)):self.assertEqual(old[pr].tobytes(),new[pr].tobytes())
        self.assertEqual(p[:,2].tobytes(),q[:,2].tobytes());self.assertEqual(t[:,3].tobytes(),tt[:,3].tobytes())
    def test_explicit_original_protection_wins_over_current_nextafter_start(self):
        p,n,t,pr=self.values();p[0,2]=np.nextafter(.0273241988,np.inf)
        q,nn,tt,J,active=self.call(p,n,t,pr)
        self.assertFalse(active[0]);np.testing.assert_array_equal(J[0],np.eye(3))
        for old,new in zip((p,n,t),(q,nn,tt)):self.assertEqual(old[0].tobytes(),new[0].tobytes())
    def test_positive_determinant_and_monotone_scale_with_exact_knots(self):
        z=np.linspace(.02,.07,1000);s,d=m.profile(z,.0273241988,.055606,.5855251506097975)
        self.assertTrue(np.all(np.diff(s)<=1e-15));self.assertTrue(np.all(d<=0));self.assertGreater(s.min(),0)
        s,d=m.profile(np.array([.0273241988,.055606]),.0273241988,.055606,.5855251506097975)
        np.testing.assert_array_equal(s,[1.,.5855251506097975]);np.testing.assert_array_equal(d,[0.,0.])
        p,n,t,pr=self.values();_,_,_,J,_=self.call(p,n,t,pr)
        self.assertGreaterEqual(np.linalg.det(J).min(),.5855251506097975**2-1e-16)
    def test_analytic_jacobian_independent_finite_difference(self):
        p=np.array([[.03,-.02,.04],[.04,.01,.047]],float);pr=np.zeros(2,bool)
        q,J,_=m.field(p,pr,.0273241988,.055606,.5855251506097975);eps=1e-8
        for axis in range(3):
            step=np.eye(3)[axis]*eps
            finite=(m.field(p+step,pr,.0273241988,.055606,.5855251506097975)[0]-
                    m.field(p-step,pr,.0273241988,.055606,.5855251506097975)[0])/(2*eps)
            np.testing.assert_allclose(finite,J[:,:,axis],atol=1e-8,rtol=0)
    def test_c2_join_second_derivative_tends_to_zero(self):
        for boundary,side in [(.0273241988,1),(.055606,-1)]:
            errors=[]
            for eps in (1e-7,1e-8,1e-9):
                _,d=m.profile(np.array([boundary,boundary+side*eps]),.0273241988,.055606,.5855251506097975)
                errors.append(abs((d[1]-d[0])/eps))
            self.assertLess(errors[-1],.002);self.assertLess(errors[-1],errors[0]*.011)
    def test_authored_covectors_transport_direction_and_original_magnitude(self):
        p,n,t,pr=self.values();_,nn,tt,J,active=self.call(p,n,t,pr)
        for i in np.flatnonzero(active):
            expected=np.linalg.solve(J[i].T,n[i]);expected*=np.linalg.norm(n[i])/np.linalg.norm(expected)
            np.testing.assert_allclose(nn[i],expected,atol=5e-16,rtol=0)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=1),np.linalg.norm(n,axis=1),atol=5e-16,rtol=0)
        np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),np.linalg.norm(t[:,:3],axis=1),atol=5e-16,rtol=0)
        np.testing.assert_allclose(np.einsum('ij,ij->i',nn[active],tt[active,:3]),0,atol=1e-15,rtol=0)
    def test_factor_one_preserves_nonorthogonal_authored_shading_exactly(self):
        p,n,t,pr=self.values();out=self.call(p,n,t,pr,1.)
        for old,new in zip((p,n,t),out[:3]):self.assertEqual(old.tobytes(),new.tobytes())
    def test_exact_computed_identity_keeps_authored_nonorthogonality(self):
        p,n,t,pr=self.values();p[:]=[0.,-0.,np.nextafter(.0273241988,np.inf)];pr[:]=False
        out=self.call(p,n,t,pr)
        np.testing.assert_array_equal(out[3],np.tile(np.eye(3),(len(p),1,1)))
        for old,new in zip((p,n,t),out[:3]):self.assertEqual(old.tobytes(),new.tobytes())
    def test_invalid_or_nonfinite_points_protection_band_or_factor_rejected(self):
        p,n,t,pr=self.values()
        for bad in [np.full_like(p,np.nan),np.full_like(p,np.inf),p.astype(int),np.empty((0,3))]:
            with self.subTest(points=bad.shape),self.assertRaises(ValueError):m.field(bad,pr,.02,.06,.6)
        for bad in [pr.astype(int),pr[:-1],None]:
            with self.assertRaises(ValueError):m.field(p,bad,.02,.06,.6)
        for values in [(.02,.02,.6),(.06,.02,.6),(.02,np.nan,.6),(.02,.06,0),(.02,.06,1.1)]:
            with self.assertRaises(ValueError):m.field(p,pr,*values)
    def test_invalid_shading_is_rejected_even_on_protected_or_identity_rows(self):
        p,n,t,pr=self.values()
        for bad_n,bad_t in [(np.zeros_like(n),t),(n,np.zeros_like(t)),(n,t[:,:3]),(n,np.full_like(t,np.inf))]:
            with self.assertRaises(ValueError):self.call(p,bad_n,bad_t,np.ones(len(p),bool),1.)
        bad=t.copy();bad[0,3]=0
        with self.assertRaises(ValueError):self.call(p,n,bad,pr)
    def test_degenerate_transported_tangent_rejected(self):
        p=np.array([[.02,0,.06]]);n=np.array([[0.,0.,2.]]);t=np.array([[0.,0.,1.,-1.]])
        with self.assertRaisesRegex(ValueError,'projected tangent'):m.transport(p,n,t,np.array([False]),.02,.05,.6)
    def test_no_input_arrays_mutated(self):
        p,n,t,pr=self.values();before=[x.tobytes() for x in (p,n,t,pr)];self.call(p,n,t,pr)
        self.assertEqual(before,[x.tobytes() for x in (p,n,t,pr)])
if __name__=='__main__':unittest.main()
