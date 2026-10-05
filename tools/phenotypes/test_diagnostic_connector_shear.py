"""Meaningful bounds, analytic inverse/J, shading and discrete failure guards."""
import unittest
import numpy as np
from diagnostic_connector_shear import ConnectorShear, verify_triangle_orientation


class ConnectorShearTests(unittest.TestCase):
    def setUp(self):
        self.o = np.array([-.12383180982238838, .0073932, 1.024964994])
        self.d = np.array([.06624573709529104, -.03563278972072993, -.9971668900507176])
        v = np.array([-.012701279638496299, -.04515376851652818, .0007697298361995616])
        v -= self.d*(v @ self.d)
        self.delta = v*.020/np.linalg.norm(v)
        self.f = ConnectorShear(self.o, self.d, self.delta, .12245397401993413)

    def test_exact_support_plateau_and_c2_derivatives(self):
        c = self.f.center
        w, dw = self.f.weight(c + np.array([-.036, -.035, -.005, 0., .005, .035, .036]))
        np.testing.assert_array_equal(w, [0, 0, 1, 1, 1, 0, 0])
        np.testing.assert_allclose(dw, np.zeros(7), atol=1e-28, rtol=0)
        for off in [-.035, -.005, .005, .035]:
            _, grad = self.f.weight(c+off+np.array([-1e-8, 1e-8]))
            self.assertLess(abs(grad[1]-grad[0])/2e-8, .05)

    def test_continuous_inverse_axial_identity_and_maximum(self):
        rng = np.random.default_rng(432)
        p = self.o + rng.normal(size=(300, 3))*.12
        q = self.f.transform(p)
        np.testing.assert_allclose(self.f.coordinates(q), self.f.coordinates(p), atol=2e-16, rtol=0)
        np.testing.assert_allclose(self.f.transform(q, inverse=True), p, atol=2e-16, rtol=0)
        self.assertLessEqual(np.linalg.norm(q-p, axis=1).max(), .020+1e-15)

    def test_protected_outside_and_joint_exact_identity(self):
        p = np.array([self.o, self.o+self.d*.46224559258737125, self.o+self.d*.03, self.o+self.d*.3])
        np.testing.assert_array_equal(self.f.transform(p), p)
        n = np.array([[.3, .4, 1.2]]*len(p), '<f4')
        t = np.array([[1.1, .03, .01, -1.]]*len(p), '<f4')
        nn, tt = self.f.transport(p, n, t)
        self.assertEqual(nn.tobytes(), n.tobytes())
        self.assertEqual(tt.tobytes(), t.tobytes())

    def test_plateau_identity_shading_with_nonorthogonal_authored_tangent(self):
        p = self.o+self.d[None]*self.f.center
        n = np.array([[0., 0., 1.3]], '<f4');t = np.array([[1.1, 0., .01, -1.]], '<f4')
        nn, tt = self.f.transport(p, n, t)
        self.assertEqual(nn.tobytes(), n.tobytes());self.assertEqual(tt.tobytes(), t.tobytes())

    def test_finite_difference_J_and_positive_determinant(self):
        p = self.o+self.d[None]*(self.f.center+.020)
        J = self.f.jacobian(p)[0]
        self.assertAlmostEqual(np.linalg.det(J), 1., places=14)
        for i in range(3):
            e = np.eye(3)[i]*1e-7
            np.testing.assert_allclose((self.f.transform(p+e)-self.f.transform(p-e))[0]/2e-7, J[:, i], atol=3e-9, rtol=0)
        np.testing.assert_allclose(np.linalg.inv(J), np.eye(3)- (J-np.eye(3)), atol=1e-15, rtol=0)

    def test_inverse_transpose_and_tangent_GS_magnitude_W(self):
        p = self.o+self.d[None]*(self.f.center-.02)
        n = np.array([[.3, .4, 1.7]]);t = np.array([[1.2, .05, .2, -1.]])
        nn, tt = self.f.transport(p, n, t);J=self.f.jacobian(p)[0]
        expected = np.linalg.solve(J.T, n[0]);expected *= np.linalg.norm(n)/np.linalg.norm(expected)
        np.testing.assert_allclose(nn[0], expected, atol=1e-15, rtol=0)
        self.assertAlmostEqual(np.linalg.norm(nn), np.linalg.norm(n), places=14)
        self.assertAlmostEqual(np.linalg.norm(tt[:, :3]), np.linalg.norm(t[:, :3]), places=14)
        self.assertAlmostEqual(nn[0]@tt[0, :3], 0., places=14)
        self.assertEqual(tt[0, 3], t[0, 3])

    def test_normals_orthogonal_to_transformed_surface_directions(self):
        p = self.o+self.d[None]*(self.f.center+.02)
        a=np.array([.3,.2,-.04]);b=np.array([-.08,.17,.1]);n=np.cross(a,b)[None];t=np.r_[a,1.][None]
        nn, _ = self.f.transport(p, n, t);J=self.f.jacobian(p)[0]
        self.assertAlmostEqual(nn[0]@(J@a),0.,places=14);self.assertAlmostEqual(nn[0]@(J@b),0.,places=14)

    def test_nonradial_large_guessed_axis_support_rejected(self):
        for axis, delta, center, inner, outer in [(self.d, self.delta+self.d*.001,self.f.center,.005,.035), (self.d,self.delta*1.01,self.f.center,.005,.035), (self.d*1.001,self.delta,self.f.center,.005,.035), (self.d,self.delta,.02,.005,.035), (self.d,self.delta,self.f.center,.004,.035), (self.d,self.delta,self.f.center,.005,.04)]:
            with self.subTest(axis=axis,delta=delta,center=center),self.assertRaises(ValueError):
                ConnectorShear(self.o,axis,delta,center,inner,outer)

    def test_active_degenerate_shading_rejected_without_waiver(self):
        p=self.o+self.d[None]*(self.f.center+.02)
        for n,t in [(np.zeros((1,3)), [[1,0,0,1]]), ([[0,0,1]], [[1,0,0,0]]), ([[0,0,1]], [[0,0,0,1]])]:
            with self.assertRaises(ValueError):self.f.transport(p,np.asarray(n,float),np.asarray(t,float))

    def test_serialized_face_orientation_and_degeneracy_guards(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4');faces=np.array([[0,1,2]])
        for q in [p[[0,2,1]],np.zeros_like(p)]:
            with self.assertRaises(ValueError):verify_triangle_orientation(p,q,faces)
        result=verify_triangle_orientation(p,p,faces)
        self.assertFalse(result['intersectionProof']);self.assertFalse(result['exportAuthorized'])

    def test_no_export_api_or_silent_immutable_vector_mutation(self):
        import diagnostic_connector_shear as module
        self.assertFalse(hasattr(module,'execute'))
        with self.assertRaises(ValueError):self.f.delta[0]=0




class ConnectorProfileTests(unittest.TestCase):
    def setUp(self):
        from diagnostic_connector_shear import ConnectorProfile
        self.d=np.array([.06624573709529104,-.03563278972072993,-.9971668900507176]);r=np.array([1.,0,0]);r-=self.d*(r@self.d);r/=np.linalg.norm(r);self.b=np.column_stack([r,np.cross(self.d,r)])
        self.o=np.array([-.12383180982238838,.0073932,1.024964994]);delta=self.b@np.array([-.005,-.018]);self.f=ConnectorProfile(self.o,self.d,delta,.12245397401993413,radial_basis=self.b,ratios=np.array([.798,.858]))

    def test_inverse_axial_support_and_positive_det(self):
        rng=np.random.default_rng(117);p=self.o+rng.normal(size=(80,3))*.12;q=self.f.transform(p)
        np.testing.assert_allclose(self.f.transform(q,inverse=True),p,atol=3e-16,rtol=0);np.testing.assert_allclose(self.f.coordinates(q),self.f.coordinates(p),atol=3e-16,rtol=0)
        w,_=self.f.weight(self.f.coordinates(p));np.testing.assert_allclose(np.linalg.det(self.f.jacobian(p)),np.prod(1+w[:,None]*(self.f.ratios-1),axis=1),atol=1e-15,rtol=0)
        self.assertTrue(np.all(np.linalg.det(self.f.jacobian(p))>=np.prod(self.f.ratios)-1e-15))
        outside=w==0;self.assertEqual(q[outside].tobytes(),p[outside].tobytes())

    def test_profile_exact_at_center_and_transition_finite_difference(self):
        p=self.o+self.f.center*self.d+np.array([[-.13,-.10],[.12,.12]])@self.b.T;q=self.f.transform(p)
        np.testing.assert_allclose(np.ptp((q-self.o)@self.b,axis=0),np.ptp((p-self.o)@self.b,axis=0)*self.f.ratios,atol=1e-15,rtol=0)
        p=p[:1]+.021*self.d;J=self.f.jacobian(p)[0]
        for i in range(3):
            e=np.eye(3)[i]*1e-7;np.testing.assert_allclose((self.f.transform(p+e)-self.f.transform(p-e))[0]/2e-7,J[:,i],atol=5e-9,rtol=0)

    def test_profile_shading_inverse_transpose_magnitude_W_outside(self):
        p=self.o+np.array([.03,self.f.center,self.f.center+.02])[:,None]*self.d+np.array([[.02,.03]]*3)@self.b.T
        n=np.array([[.3,.4,1.7]]*3);t=np.array([[1.2,.05,.2,-1.]]*3);nn,tt=self.f.transport(p,n,t);J=self.f.jacobian(p)
        self.assertEqual(nn[0].tobytes(),n[0].tobytes());self.assertEqual(tt[0].tobytes(),t[0].tobytes())
        for i in [1,2]:
            expected=np.linalg.solve(J[i].T,n[i]);expected*=np.linalg.norm(n[i])/np.linalg.norm(expected);np.testing.assert_allclose(nn[i],expected,atol=1e-15,rtol=0)
            self.assertAlmostEqual(np.linalg.norm(tt[i,:3]),np.linalg.norm(t[i,:3]),places=14);self.assertAlmostEqual(nn[i]@tt[i,:3],0,places=14);self.assertEqual(tt[i,3],-1)

    def test_profile_bad_ratios_basis_or_degenerate_shading_rejected(self):
        from diagnostic_connector_shear import ConnectorProfile
        for ratios,basis in [([0,.85],self.b),([.74,.85],self.b),([1.01,.85],self.b),([.8,.9],self.b*1.001),([.8,.9],self.b[:,::-1])]:
            with self.assertRaises(ValueError):ConnectorProfile(self.o,self.d,self.f.delta,self.f.center,radial_basis=basis,ratios=ratios)
        p=(self.o+self.f.center*self.d)[None]
        with self.assertRaises(ValueError):self.f.transport(p,np.zeros((1,3)),np.array([[1.,0,0,1.]]))



class KnotIdentityTests(unittest.TestCase):
    def setUp(self):ConnectorShearTests.setUp(self)
    def test_plateau_knots_nextafter_authored_T_exact(self):
        a=[]
        for knot in [self.f.center-self.f.inner,self.f.center+self.f.inner]:
            a.extend([np.nextafter(knot,-np.inf),knot,np.nextafter(knot,np.inf)])
        p=self.o+np.asarray(a)[:,None]*self.d
        J=self.f.jacobian(p)
        np.testing.assert_array_equal(J,np.broadcast_to(np.eye(3),J.shape))
        n=np.array([[.3,.4,1.7]]*len(p),'<f4');t=np.array([[1.2,.05,.2,-1.]]*len(p),'<f4');nn,tt=self.f.transport(p,n,t)
        self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())

    def test_outer_nextafter_no_cleanup_or_degenerate_active_waiver(self):
        a=np.array([self.f.center-self.f.outer,self.f.center+self.f.outer]);a=np.r_[np.nextafter(a,-np.inf),a,np.nextafter(a,np.inf)]
        p=self.o+a[:,None]*self.d;n=np.zeros(p.shape,dtype='<f4');t=np.zeros((len(p),4),dtype='<f4');t[:,3]=1
        np.testing.assert_array_equal(self.f.transform(p),p);nn,tt=self.f.transport(p,n,t);self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())
        with self.assertRaises(ValueError):self.f.transport((self.o+self.f.center*self.d)[None],n[:1],t[:1])

    def test_profile_identity_J_preserves_nonorthogonal_authored_T(self):
        from diagnostic_connector_shear import ConnectorProfile
        r=np.array([1.,0,0]);r-=self.d*(r@self.d);r/=np.linalg.norm(r);b=np.column_stack([r,np.cross(self.d,r)])
        f=ConnectorProfile(self.o,self.d,self.delta,self.f.center,radial_basis=b,ratios=np.ones(2))
        p=self.o+np.array([self.f.center,np.nextafter(self.f.center+self.f.inner,np.inf)])[:,None]*self.d
        np.testing.assert_array_equal(f.jacobian(p),np.broadcast_to(np.eye(3),(len(p),3,3)))
        n=np.array([[.3,.4,1.7]]*len(p),'<f4');t=np.array([[1.2,.05,.2,-1.]]*len(p),'<f4');nn,tt=f.transport(p,n,t)
        self.assertEqual(nn.tobytes(),n.tobytes());self.assertEqual(tt.tobytes(),t.tobytes())

if __name__=='__main__':unittest.main()
