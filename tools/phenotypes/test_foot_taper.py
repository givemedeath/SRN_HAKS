import unittest
import numpy as np
from taper_foot_ankle import field
class HiddenTaperTests(unittest.TestCase):
    def test_lower_anatomy_identity_and_smooth_differential(self):
        p=np.array([[.03,.02,z] for z in [-.137,-.02,.015,.03,.065,.07]])
        out,j=field(p,.015,.065,.7,[-.017,.003])
        np.testing.assert_array_equal(out[:3],p[:3]);np.testing.assert_array_equal(j[:3],np.tile(np.eye(3),(3,1,1)))
        np.testing.assert_array_equal(out[:,2],p[:,2]);self.assertGreater(np.linalg.det(j).min(),0)
        for row in p[3:]:
            eps=1e-7;numeric=np.column_stack([(field((row+np.eye(3)[k]*eps)[None],.015,.065,.7,[-.017,.003])[0][0]-field((row-np.eye(3)[k]*eps)[None],.015,.065,.7,[-.017,.003])[0][0])/(2*eps) for k in range(3)])
            index=np.flatnonzero(np.all(p==row,axis=1))[0];np.testing.assert_allclose(numeric,j[index],atol=1e-5)
    def test_visible_or_inverting_scope_rejected(self):
        for start,end,scale in [(-.02,.05,.7),(.05,.03,.7),(.01,.15,.7),(.01,.05,-1)]:
            with self.assertRaises(RuntimeError):field(np.zeros((1,3)),start,end,scale,[0,0])
if __name__=='__main__':unittest.main()
