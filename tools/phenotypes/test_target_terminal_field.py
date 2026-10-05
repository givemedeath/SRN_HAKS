"""Independent differential, continuity and authored-direction field checks."""
import copy
import unittest
import numpy as np
from deform_target_terminal_caps import determinant_bound, field, transport


def controls():
    return {'maximumDisplacementMetres':.020,'lateralTransition':[.2575,.265],
            'yKnots':[-.174,-.160,-.145,-.090],'zKnots':[1.505,1.520,1.570,1.590]}


class TerminalFieldTests(unittest.TestCase):
    def test_exact_central_outside_support_and_forward_only_twenty_millimetres(self):
        points=np.array([[.205,-.15,1.54],[.27,-.20,1.54],[.27,-.13,1.7],
                         [.27,-.15,1.54],[-.27,-.15,1.54]])
        changed,jac=field(points,controls())
        np.testing.assert_array_equal(changed[:3],points[:3])
        np.testing.assert_array_equal(jac[:3],np.tile(np.eye(3),(3,1,1)))
        np.testing.assert_allclose(changed[3:]-points[3:],[[0,.02,0],[0,.02,0]],atol=1e-14)

    def test_analytic_jacobian_matches_independent_finite_differences(self):
        points=np.array([[.261,-.168,1.511],[-.261,-.119,1.579],[.27,-.15,1.54]])
        _,jac=field(points,controls());numerical=np.zeros_like(jac);epsilon=1e-7
        for axis in range(3):
            offset=np.eye(3)[axis]*epsilon
            plus,_=field(points+offset,controls());minus,_=field(points-offset,controls())
            numerical[:,:,axis]=(plus-minus)/(2*epsilon)
        np.testing.assert_allclose(jac,numerical,atol=2e-8,rtol=1e-8)

    def test_global_positive_determinant_bound_and_fixed_xz_monotonicity(self):
        y=np.linspace(-.25,0,10001);points=np.column_stack((np.full(len(y),.27),y,np.full(len(y),1.54)))
        changed,jac=field(points,controls());bound=determinant_bound(controls())
        self.assertAlmostEqual(bound,5/11)
        self.assertGreater(np.diff(changed[:,1]).min(),0)
        self.assertGreaterEqual(np.linalg.det(jac).min(),bound-1e-12)
        self.assertAlmostEqual(np.linalg.det(field([[.27,-.1175,1.54]],controls())[1])[0],bound)

    def test_inverse_transpose_normal_and_forward_tangent_keep_authored_magnitudes(self):
        _,jac=field([[.261,-.168,1.511],[.2,-.168,1.511]],controls())
        n=np.tile(np.array([0,0,1.3]),(2,1));t=np.tile(np.array([1.2,0,0,-1]),(2,1))
        nn,tt=transport(n,t,jac,np.array([True,False]))
        expected=np.linalg.inv(jac[0]).T@n[0];expected*=1.3/np.linalg.norm(expected)
        np.testing.assert_allclose(nn[0],expected,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=1),1.3,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),1.2,atol=1e-12)
        self.assertEqual(float(np.dot(nn[0],tt[0,:3])),0.)
        np.testing.assert_array_equal(tt[:,3],t[:,3])
        np.testing.assert_array_equal(nn[1],n[1]);np.testing.assert_array_equal(tt[1],t[1])

    def test_c1_field_value_and_derivative_at_support_terminals(self):
        points=np.array([[.2575,-.15,1.54],[.27,-.174,1.54],[.27,-.09,1.54],
                         [.27,-.15,1.505],[.27,-.15,1.590]])
        changed,jac=field(points,controls())
        np.testing.assert_array_equal(changed,points)
        np.testing.assert_array_equal(jac,np.tile(np.eye(3),(len(points),1,1)))

    def test_unbounded_or_foldable_controls_rejected(self):
        bad=controls();bad['maximumDisplacementMetres']=.021
        with self.assertRaisesRegex(ValueError,'20mm'):determinant_bound(bad)
        bad=controls();bad['yKnots'][-1]=-.130
        with self.assertRaisesRegex(ValueError,'determinant'):determinant_bound(bad)


if __name__=='__main__':unittest.main()
