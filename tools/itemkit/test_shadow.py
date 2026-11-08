import unittest
import tempfile
from pathlib import Path
from collections import Counter
import numpy as np
from .shadow import silhouette_proxy,build_candidates
from .geometry import topology,segment_hits
from tools.headkit.common import digest


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
    def test_sparse_interior_depth_is_preserved_at_measured_contacts(self):
        yz=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])
        p=np.r_[np.c_[np.full(4,-.05),yz],np.c_[np.full(4,.05),yz],[[-.3,0,0],[.3,0,0]]]
        f=[]
        for i in range(4):
            j=(i+1)%4;f.extend([[8,j,i],[9,4+i,4+j],[i,j,4+j],[i,4+j,4+i]])
        f=np.asarray(f);self.assertTrue(topology(p,f)['closedWound'])
        probe={'name':'sparse-depth','points':[[-.3,0,0],[.3,0,0]],'minimum':.5,'maximumSampleError':.0001}
        v,t,report=silhouette_proxy(p,f,{'thicknessProbes':[probe]},100,{'resolution':128})
        self.assertLessEqual(len(t),100)
        self.assertGreaterEqual(report['openings']['thickness'][0]['distance'],.5)
        self.assertLessEqual(report['openings']['thickness'][0]['maximumSampleError'],.0001)

    def test_candidate_preserves_and_binds_thickness_checks(self):
        p,f=ring()
        profile={'family':'firearm-sling','firearm':{'subtype':'smg'},'budgets':{'parts':{'m':{'shadow':100}}}}
        settings={'method':'projected-silhouette','resolution':128}
        probe={'name':'ring-wall','points':[[-.05,.8,0],[.05,.8,0]],'minimum':.08,'maximumSampleError':.002}
        processing={'shadowProxies':{'m':settings},'thicknessProbes':[probe]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.npz';np.savez(source,m_positions=p,m_faces=f)
            candidate=build_candidates(source,profile,processing,root/'valid')['m']
            self.assertEqual(candidate['checks']['openings']['thickness'][0]['name'],'ring-wall')
            self.assertEqual(candidate['policyHash'],digest({'settings':settings,'openingProbes':[],
                'thicknessProbes':[probe],'budget':100}))
            impossible={**processing,'thicknessProbes':[{**probe,'minimum':.2}]}
            with self.assertRaisesRegex(ValueError,'thickness'):
                build_candidates(source,profile,impossible,root/'rejected')
            legacy=build_candidates(source,profile,{'shadowProxies':{'m':settings}},root/'legacy')['m']
            self.assertEqual(legacy['policyHash'],digest({'settings':settings,'openingProbes':[],'budget':100}))

    def test_part_scoped_probe_is_not_measured_on_another_part(self):
        p,f=ring()
        profile={'family':'shortsword','budgets':{'parts':{'m':{'shadow':100}}}}
        settings={'method':'projected-silhouette','resolution':128}
        probe={'name':'blade-wall','points':[[-.05,9,0],[.05,9,0]],'minimum':.08,'maximumSampleError':.002,'parts':['t']}
        processing={'shadowProxies':{'m':settings},'thicknessProbes':[probe]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.npz';np.savez(source,m_positions=p,m_faces=f)
            candidate=build_candidates(source,profile,processing,root/'scoped')['m']
            self.assertEqual(candidate['policyHash'],digest({'settings':settings,'openingProbes':[],'budget':100}))
            unscoped={**processing,'thicknessProbes':[{k:v for k,v in probe.items() if k!='parts'}]}
            with self.assertRaisesRegex(ValueError,'thickness'):
                build_candidates(source,profile,unscoped,root/'rejected')

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
