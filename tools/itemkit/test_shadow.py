import unittest
from collections import Counter
import numpy as np
from .shadow import silhouette_proxy
from .geometry import topology,segment_hits


def ring():
    points=np.array([[-1,-1],[1,-1],[1,1],[-1,1],[-.3,-.3],[.3,-.3],[.3,.3],[-.3,.3]])
    triangles=[]
    for i in range(4):
        j=(i+1)%4;triangles.extend([[i,j,j+4],[i,j+4,i+4]])
    triangles=np.array(triangles);n=len(points);edges=Counter(tuple(sorted((a,b))) for face in triangles for a,b in zip(face,np.roll(face,-1)))
    boundary=[(a,b) for face in triangles for a,b in zip(face,np.roll(face,-1)) if edges[tuple(sorted((a,b)))]==1]
    p=np.r_[np.c_[np.full(n,-.05),points],np.c_[np.full(n,.05),points]]
    f=np.r_[triangles[:,[0,2,1]],triangles+n,np.array([[a,b,b+n] for a,b in boundary]),np.array([[a,b+n,a+n] for a,b in boundary])]
    return p,f


class ShadowTests(unittest.TestCase):
    def test_ring_opening_budget_and_rotated_frame(self):
        p,f=ring();before=p.copy();basis=np.array([[0,-1,0],[1,0,0],[0,0,1]],float);origin=np.array([1,2,3])
        start=np.array([-.2,0,0])@basis.T+origin;end=np.array([.2,0,0])@basis.T+origin
        world=p@basis.T+origin
        v,t,report=silhouette_proxy(world,f,{'openingProbes':[{'name':'ring','start':start.tolist(),'end':end.tolist()}]},100,
            {'basis':basis.tolist(),'origin':origin.tolist(),'resolution':128})
        self.assertTrue(topology(v,t)['closedWound']);self.assertLessEqual(len(t),100)
        self.assertEqual(segment_hits(v,t,start,end),0);self.assertGreaterEqual(report['sideSilhouetteIoU'],.95)
        np.testing.assert_array_equal(p,before)

    def test_invalid_frame_budget_and_obstructed_probe_fail(self):
        p,f=ring()
        with self.assertRaisesRegex(ValueError,'frame'):silhouette_proxy(p,f,{},100,{'basis':np.zeros((3,3)).tolist()})
        with self.assertRaisesRegex(ValueError,'acceptance'):silhouette_proxy(p,f,{},12,{'resolution':128})
        with self.assertRaisesRegex(ValueError,'acceptance'):
            silhouette_proxy(p,f,{'openingProbes':[{'name':'blocked','start':[-.2,.8,0],'end':[.2,.8,0]}]},100,{'resolution':128})
