"""A measured curved cut stays identifiable after an item's native fit."""
import unittest
import numpy as np
from .geometry import hidden_cap_faces,transform


class CurvedCapTests(unittest.TestCase):
    def test_quadric_cut_survives_uniform_rotation_translation_and_float32(self):
        p=np.array([[0,0,0],[1,1,0],[1,-1,0],[2,0,1]],float)
        faces=np.array([[0,1,2],[0,2,3]])
        q=np.zeros((4,4));q[0,3]=q[3,0]=.5;q[1,1]=-1
        c,s=np.cos(.31),np.sin(.31);m=np.eye(4)
        m[:3,:3]=1.7*np.array([[c,-s,0],[s,c,0],[0,0,1]])
        m[:3,3]=(.23,-.17,.41);v=transform(p,m).astype(np.float32)
        inv=np.linalg.inv(m);native=inv.T@q@inv
        surface={'name':'measured curved cut','matrix':native.tolist(),'tolerance':2e-6,
                 'bounds':[(v.min(0)-.01).tolist(),(v.max(0)+.01).tolist()]}
        np.testing.assert_array_equal(hidden_cap_faces(v,faces,[],quadrics=[surface]),[True,False])
        surface['bounds']=[[10,10,10],[11,11,11]]
        self.assertFalse(hidden_cap_faces(v,faces,[],quadrics=[surface]).any())

    def test_invalid_quadric_cannot_classify_caps(self):
        p=np.array([[0,0,0],[1,1,0],[1,-1,0]],float);f=np.array([[0,1,2]])
        for matrix in (np.zeros((4,4)),np.full((4,4),np.nan),np.arange(16).reshape(4,4)):
            row={'name':'invalid','matrix':matrix.tolist(),'tolerance':1e-6,'bounds':[[-2,-2,-2],[2,2,2]]}
            with self.assertRaisesRegex(ValueError,'Finite symmetric cap quadric'):
                hidden_cap_faces(p,f,[],quadrics=[row])


if __name__=='__main__':unittest.main()
