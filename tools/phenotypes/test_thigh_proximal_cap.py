"""Meaningful differential/scope guards for the local upper-thigh cap field."""
import unittest
import numpy as np
from refine_thigh_proximal_cap import taper_field,directions

KNOTS=[[-.01,1,1],[0,1,.9713],[.02,.9419,.8267],[.04,.851,.6936],[.06,.9088,.6434]]


class CapFieldTests(unittest.TestCase):
    def test_shaft_exact_identity(self):
        p=np.asarray([[.08,.11,-.25],[-.03,.10,-.04],[.04,-.06,-.01]])
        q,j=taper_field(p,KNOTS,[0,0])
        self.assertTrue(np.array_equal(p,q))
        self.assertTrue(np.array_equal(j,np.tile(np.eye(3),(len(p),1,1))))
        n=np.asarray([[.3,.4,.5],[1.2,0,0],[0,.8,.4]])
        self.assertTrue(np.array_equal(directions(n,j),n))

    def test_jacobian_matches_real_field(self):
        p=np.asarray([[.071,-.084,.013],[-.055,.062,.048],[.027,.011,.065]])
        _,analytic=taper_field(p,KNOTS,[.005,-.001])
        epsilon=1e-7;numerical=np.zeros_like(analytic)
        for axis in range(3):
            delta=np.eye(3)[axis]*epsilon
            plus,_=taper_field(p+delta,KNOTS,[.005,-.001])
            minus,_=taper_field(p-delta,KNOTS,[.005,-.001])
            numerical[:,:,axis]=(plus-minus)/(2*epsilon)
        self.assertLess(float(np.max(abs(analytic-numerical))),1e-7)
        self.assertGreater(float(np.linalg.det(analytic).min()),.2)

    def test_inverse_normal_is_orthogonal_to_deformed_surface(self):
        p=np.asarray([[.07,-.08,.015],[.03,.06,.051]])
        _,j=taper_field(p,KNOTS,[0,0])
        n=np.asarray([[0,1,0],[0,1,0]],float)*1.3
        nn=directions(n,j)
        tangent=np.tile([1,0,0],(2,1));other=np.tile([0,0,1],(2,1))
        for t in [tangent,other]:
            transformed=np.einsum('nij,nj->ni',j,t)
            self.assertLess(float(np.max(abs(np.sum(transformed*nn,axis=1)))),1e-12)
        self.assertLess(float(np.max(abs(np.linalg.norm(nn,axis=1)-1.3))),1e-12)

    def test_continuous_derivative_at_knots(self):
        for z in np.asarray(KNOTS)[:,0]:
            p=np.asarray([[.08,.09,z-1e-8],[.08,.09,z+1e-8]])
            q,j=taper_field(p,KNOTS,[0,0])
            self.assertLess(float(np.max(abs(q[1]-q[0]))),1e-6)
            self.assertLess(float(np.max(abs(j[1]-j[0]))),1e-4)

    def test_invalid_deformation_controls_rejected(self):
        p=np.asarray([[0,0,.03]])
        for knots in [[[-.01,1,1],[.02,0,1]],[[-.01,1,1],[.02,1.1,1]],
                      [[-.01,.9,1],[.02,.8,1]],[[-.01,1,1],[-.02,.9,.9]],
                      [[-.01,1,1],[float('nan'),.9,.9]]]:
            with self.subTest(knots=knots):
                with self.assertRaises(RuntimeError):taper_field(p,knots,[0,0])

    def test_centreshift_has_correct_derivative_and_keeps_height(self):
        knots=[[-.01,1,1,0,0],[0,1,.97,0,0],[.02,.94,.82,.017,-.010],[.04,.85,.69,.014,-.012]]
        p=np.asarray([[.08,.10,-.04],[.07,.09,.011]])
        q,j=taper_field(p,knots,[0,0])
        self.assertTrue(np.array_equal(q[:,2],p[:,2]))
        self.assertTrue(np.array_equal(q[0],p[0]))
        eps=1e-7
        plus,_=taper_field(p+np.asarray([0,0,eps]),knots,[0,0])
        minus,_=taper_field(p-np.asarray([0,0,eps]),knots,[0,0])
        self.assertLess(float(np.max(abs((plus-minus)/(2*eps)-j[:,:,2]))),1e-7)
        with self.assertRaises(RuntimeError):taper_field(p,[[-.01,1,1,.01,0],[.02,.9,.9,0,0]],[0,0])


if __name__=='__main__':unittest.main()
