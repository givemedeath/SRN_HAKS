"""Cap-only corrections preserve the complete jaw and all existing attributes."""
import unittest
import numpy as np
from cap_head_holes import add_caps,boundary_loops


class CapOnlyTests(unittest.TestCase):
    def test_caps_an_oblique_hole_without_moving_or_trimming_any_corner(self):
        v=np.array([[-1,-1,0],[1,-1,.2],[1,1,.3],[-1,1,.1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)
        faces=np.array([[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7],[4,5,6],[4,6,7]])
        p=v[faces];normal=np.tile([0,0,1],(len(p),3,1));uv=np.tile([[.3,.3],[.6,.3],[.4,.6]],(len(p),1,1))
        pp,nn,uu,records=add_caps(p,normal,uv)
        self.assertEqual(len(records),1);self.assertEqual(len(pp),len(p)+2)
        np.testing.assert_array_equal(pp[:len(p)],p);np.testing.assert_array_equal(nn[:len(p)],normal);np.testing.assert_array_equal(uu[:len(p)],uv)
        self.assertFalse(boundary_loops(pp)[1])
        # A closed result is a no-op; caps never imply a neck taper or cut.
        p2,n2,u2,records2=add_caps(pp,nn,uu)
        self.assertFalse(records2);np.testing.assert_array_equal(p2,pp)

    def test_branching_boundary_fails_without_mutating_input(self):
        p=np.array([[[0,0,0],[1,0,0],[0,1,0]],[[0,0,0],[0,-1,0],[-1,0,0]]],float)
        original=p.copy()
        with self.assertRaisesRegex(ValueError,'Branching'):add_caps(p,np.tile([0,0,1],(2,3,1)),np.tile([[.3,.3],[.6,.3],[.4,.6]],(2,1,1)))
        np.testing.assert_array_equal(p,original)


if __name__=='__main__':unittest.main()
