import tempfile,unittest
from pathlib import Path
import numpy as np
from headkit.common import pin
from headkit.gltf import positions,write_mesh
from headkit.hair_base import trim
from headkit.mesh import physical


class HairBaseTests(unittest.TestCase):
    def fixture(self,folder):
        # A tall closed tube, with fine lower faces: the top and upper sides are protected anatomy.
        rings=41;n=12
        v=np.array([[np.cos(a*2*np.pi/n),y/(rings-1),np.sin(a*2*np.pi/n)]
                    for y in range(rings) for a in range(n)])
        f=[]
        for y in range(rings-1):
            for a in range(n):
                i=y*n+a;j=y*n+(a+1)%n;k=i+n;l=j+n
                f.extend([[i,k,j],[j,k,l]])
        for a in range(1,n-1):f.extend([[0,a,a+1],[(rings-1)*n,(rings-1)*n+a+1,(rings-1)*n+a]])
        p=folder/'source.glb';write_mesh(p,v,np.array(f))
        policy={'sourceSha256':pin(p)['sha256'],'heightFraction':.037,'hairOnlyReviewed':True,'notes':'Reviewed hair-only base'}
        return p,policy

    def test_shared_cut_boundary_and_exact_upper_surface(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,policy=self.fixture(root);out=root/'out.glb'
            report=trim(p,out,policy);a,af=positions(p);b,bf=positions(out)
            self.assertTrue(report['exteriorRepairRequired'])
            self.assertGreaterEqual(float(b[:,1].min()),.037-1e-7)
            upper=a[af][np.min(a[af][:,:,1],axis=1)>.12]
            retained={tuple(t.ravel()) for t in b[bf]}
            self.assertTrue(all(tuple(t.ravel()) in retained for t in upper))
            b,bf=physical(b,bf)
            edges=np.sort(np.concatenate([bf[:,[0,1]],bf[:,[1,2]],bf[:,[2,0]]]),axis=1)
            e,c=np.unique(edges,axis=0,return_counts=True);boundary=e[c==1]
            self.assertGreater(len(boundary),0)
            self.assertTrue(np.all(np.bincount(boundary.ravel())[np.unique(boundary)]==2))
            self.assertTrue(np.allclose(b[np.unique(boundary),1],.037))

    def test_stale_source_and_invalid_policy_never_write_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,policy=self.fixture(root);out=root/'out.glb'
            for extra in [{'sourceSha256':'0'*64},{'heightFraction':float('nan')},{'heightFraction':True},
                          {'heightFraction':.1001},{'hairOnlyReviewed':False},{'notes':''},{'unknown':1}]:
                with self.subTest(extra=extra),self.assertRaises(ValueError):trim(p,out,dict(policy,**extra))
                self.assertFalse(out.exists())

    def test_large_triangle_cannot_reach_protected_surface(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,policy=self.fixture(root)
            v,f=positions(p);f=np.concatenate([f,[[0,30*12,30*12+1]]]);p=root/'changed.glb';write_mesh(p,v,f)
            policy['sourceSha256']=pin(p)['sha256']
            with self.assertRaisesRegex(ValueError,'protected upper'):trim(p,root/'out.glb',policy)

    def test_dense_low_band_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p,policy=self.fixture(root)
            v,f=positions(p);f=np.concatenate([f,np.tile(f[:12],(30,1))]);p=root/'changed.glb';write_mesh(p,v,f)
            policy['sourceSha256']=pin(p)['sha256']
            with self.assertRaisesRegex(ValueError,'ten percent of triangles'):trim(p,root/'out.glb',policy)


    def test_trim_policy_binds_precluster_and_fit_but_not_prepare(self):
        from headkit.runner import Runner
        runner=Runner.__new__(Runner)
        runner.data={'schemaVersion':1,'id':'hair-trim-test','inputs':{'raw':{'path':'raw.glb','sha256':'2'*64}},'mesh':{},'fit':{'matrixFrom':'fit'}}
        before={stage:runner.manifest_digest(stage) for stage in ('precluster','fit','prepare')}
        runner.data['mesh']['lowerHairTrim']={'heightFraction':.05,'sourceSha256':'1'*64,'hairOnlyReviewed':True,'notes':'Measured'}
        self.assertNotEqual(before['precluster'],runner.manifest_digest('precluster'))
        self.assertNotEqual(before['fit'],runner.manifest_digest('fit'))
        self.assertEqual(before['prepare'],runner.manifest_digest('prepare'))


if __name__=='__main__':unittest.main()
