import unittest
import tempfile
from pathlib import Path
from collections import Counter
import numpy as np
from .shadow import silhouette_proxy,build_candidates,quadric_proxy
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


def tube(segments=48,rings=40,radius=.02,length=.6):
    """A closed capped cylinder along y with an elliptical, off-centre bulge: its section varies around the axis."""
    angle=np.linspace(0,2*np.pi,segments,endpoint=False);y=np.linspace(0,length,rings)
    rows=[]
    for value in y:
        bulge=1+.6*np.exp(-((value-length*.6)/(length*.08))**2)
        rows.append(np.c_[radius*np.cos(angle)*bulge,np.full(segments,value),radius*np.sin(angle)*(1+.3*(bulge-1))])
    p=np.concatenate(rows+[[[0,0,0]],[[0,length,0]]]);f=[]
    for r in range(rings-1):
        for s in range(segments):
            a=r*segments+s;b=r*segments+(s+1)%segments;f+=[[a,b+segments,b],[a,a+segments,b+segments]]
    bottom=len(p)-2;top=len(p)-1;last=(rings-1)*segments
    for s in range(segments):f+=[[bottom,s,(s+1)%segments],[top,last+(s+1)%segments,last+s]]
    return p,np.asarray(f)


class QuadricShadowTests(unittest.TestCase):
    def setUp(self):
        try:
            import pymeshlab,igl
        except ImportError:self.skipTest('pymeshlab and igl not on the path')
        self.meshlab,self.igl=pymeshlab,igl

    def test_quadric_keeps_probes_closed_and_within_budget(self):
        p,f=tube();self.assertTrue(topology(p,f)['closedWound'])
        probe={'name':'bulge','points':[[-.032,.36,0],[.032,.36,0]],'minimum':.05,'maximumSampleError':.0005}
        v,t,report=quadric_proxy(p,f,{'thicknessProbes':[probe]},120,{'method':'quadric'},self.meshlab,self.igl)
        self.assertLessEqual(len(t),120);self.assertTrue(topology(v,t)['closedWound'])
        self.assertGreater(report['probeProtectedFaces'],0)
        self.assertLessEqual(report['openings']['thickness'][0]['maximumSampleError'],.0005)
        self.assertLessEqual(report['maximumSourceDistance'],.006)
        self.assertGreaterEqual(report['maximumSourceGap'],0)                    # the reverse direction, recorded for review
        vertex,surface=report['maximumSourceDistance'],report['maximumSurfaceDistance'];self.assertGreater(surface,vertex)
        # Triangle interiors are bounded too: a bound between the vertex and surface deviation passes the vertices only.
        bound=(vertex+surface)/2;settings={'method':'quadric','maximumDistance':bound,'maximumSurfaceDistance':bound}
        with self.assertRaisesRegex(ValueError,'triangles cut away'):
            quadric_proxy(p,f,{'thicknessProbes':[probe]},120,settings,self.meshlab,self.igl)

    def test_quadric_candidate_binds_its_policy_and_needs_its_libraries(self):
        p,f=tube();settings={'method':'quadric'}
        profile={'family':'staff','budgets':{'parts':{'t':{'shadow':120}}}}
        probe={'name':'bulge','points':[[-.032,.36,0],[.032,.36,0]],'minimum':.05,'maximumSampleError':.0005}
        processing={'shadowProxies':{'t':settings},'thicknessProbes':[probe]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.npz';np.savez(source,t_positions=p,t_faces=f)
            candidate=build_candidates(source,profile,processing,root/'valid',meshlab=self.meshlab,igl=self.igl)['t']
            self.assertEqual(candidate['policyHash'],digest({'settings':settings,'openingProbes':[],'thicknessProbes':[probe],'budget':120}))
            self.assertEqual(candidate['checks']['method'],'quadric')
            with self.assertRaisesRegex(ValueError,'pymeshlab and igl'):build_candidates(source,profile,processing,root/'bare')

    def test_quadric_rejects_open_sources_crowded_probes_and_distant_results(self):
        p,f=tube()
        with self.assertRaisesRegex(ValueError,'closed outward'):
            quadric_proxy(p,f[:-3],{},120,{'method':'quadric'},self.meshlab,self.igl)
        crowded={'name':'wide','points':[[-.032,.36,0],[.032,.36,0]],'minimum':.05,'maximumSampleError':.0005}
        with self.assertRaisesRegex(ValueError,'half the shadow budget'):
            quadric_proxy(p,f,{'thicknessProbes':[crowded]},120,{'method':'quadric','probeRadius':.02},self.meshlab,self.igl)
        with self.assertRaisesRegex(ValueError,'acceptance'):
            quadric_proxy(p,f,{},16,{'method':'quadric','maximumDistance':1e-5},self.meshlab,self.igl)


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
