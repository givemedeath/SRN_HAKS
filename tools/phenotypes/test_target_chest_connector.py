"""Whole-surface split protections, seam ancestry, serialization and binding guards."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import repair_target_chest_connector as c
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,raw_corners,read_glb,write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture
import target_contract as contract

def seam():
    p=np.array([[-.02,-.04,0],[.02,.01,0],[0,.01,-.02],[-.02,-.04,0],[.02,.01,0],[0,-.04,.02]],dtype='<f4')
    return dict(POSITION=p,NORMAL=np.tile([0.,0.,1.3],(6,1)).astype('<f4'),
                TEXCOORD_0=np.array([[0,0],[1,0],[.5,1],[.2,.3],[.7,.8],[1,1]],dtype='<f4'),
                TANGENT=np.tile([1.2,0,0,-1],(6,1)).astype('<f4'))

class ConnectorTests(unittest.TestCase):
    def test_entire_upper_child_surface_and_barycentric_attributes(self):
        a=seam();f=np.array([[0,1,2],[3,5,4]]);s=c.split_at_plane(a,f,-.015)
        self.assertEqual(len(s['crossingParentFaceIds']),2)
        for k,v in a.items():
            self.assertEqual(s['attributes'][k][:len(v)].tobytes(),v.tobytes())
            expected=np.einsum('fci,fij->fcj',s['barycentric'],v[f[s['parentFaceIds']]])
            np.testing.assert_allclose(s['attributes'][k][s['faces']],expected,atol=3e-8)
        p=s['attributes']['POSITION'].astype(float)@BASIS.T;q,j=c.connector_field(p,s['plane'],-.05,[0,0],[.5,.5]);upper=s['upperFaceMask']
        np.testing.assert_array_equal(q[s['faces'][upper]],p[s['faces'][upper]])
        self.assertTrue(np.all(p[s['faces'][~upper],2]<=s['plane']))
        self.assertTrue(np.all(p[s['faces'][upper],2]>=s['plane']))

    def test_uv_seam_exact_edge_geometry_and_ambiguous_handedness_rejection(self):
        a=seam();s=c.split_at_plane(a,np.array([[0,1,2],[3,5,4]]),-.015)
        edge=s['splitRowEdgeLineage'];left=next(i for i,e in edge.items() if e[:2]==(0,1));right=next(i for i,e in edge.items() if e[:2]==(3,4))
        self.assertEqual(s['attributes']['POSITION'][left].tobytes(),s['attributes']['POSITION'][right].tobytes())
        self.assertFalse(np.array_equal(s['attributes']['TEXCOORD_0'][left],s['attributes']['TEXCOORD_0'][right]))
        a['TANGENT'][1,3]=1
        with self.assertRaisesRegex(ValueError,'handedness'):c.split_at_plane(a,np.array([[0,1,2]]),-.015)

    def test_independent_jacobian_c1_identity_and_positive_determinants(self):
        p=np.array([[.09,.06,-.032],[.1,.05,-.015],[.1,-.03,-.050]]);q,j=c.connector_field(p,-.015,-.05,[0,0],[.5,.5]);numeric=np.zeros_like(j);eps=1e-7
        for axis in range(3):
            d=np.eye(3)[axis]*eps
            numeric[:,:,axis]=(c.connector_field(p+d,-.015,-.05,[0,0],[.5,.5])[0]-c.connector_field(p-d,-.015,-.05,[0,0],[.5,.5])[0])/(2*eps)
        np.testing.assert_allclose(j,numeric,atol=2e-5,rtol=2e-5)
        np.testing.assert_array_equal(q[1],p[1]);np.testing.assert_array_equal(j[1],np.eye(3));np.testing.assert_array_equal(q[:,2],p[:,2])
        self.assertGreaterEqual(np.linalg.det(j).min(),.25)
        for scales in ([0,1],[.1,.5],[float('nan'),1]):
            with self.assertRaises(ValueError):c.connector_field(p,-.015,-.05,[0,0],scales)
        with self.assertRaises(ValueError):c.connector_field(p,0,-.05,[0,0],[.5,.5])

class SerializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.target=self.root/'target.json';target=target_fixture();self.target.write_text(json.dumps(target))
        d,b=fixture();d['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0');blob=bytearray(b);start=d['bufferViews'][0]['byteOffset']
        pos=np.array([[0,-.04,0],[.03,.02,0],[0,.02,.03],[0,-.04,.03]],dtype='<f4');blob[start:start+pos.nbytes]=pos.tobytes()
        self.raw=self.root/'parent.glb';write_glb(self.raw,d,bytes(blob));p,n,uv,_=raw_corners(d,bytes(blob))
        f=accessor(d,bytes(blob),3).reshape(-1,3).astype(int);t=accessor(d,bytes(blob),4).astype(float);t[:,:3]=t[:,:3]@BASIS.T
        self.archive=self.root/'native.npz';np.savez_compressed(self.archive,positions=p,normals=n,uvGltf=uv,uvNative=np.stack((uv[:,:,0],1-uv[:,:,1]),2),tangents=t[f],sourceTriangleIds=np.arange(len(f)))
        self.parent=self.root/'geometry.json';self.parent_data={'schemaVersion':2,'kind':'target-part-geometry','operation':'bounded-inward-waist-field',
            **contract.binding(self.target,target,'working'),'part':'chest','joint':'torso_g','candidate':str(self.raw),'candidateSha256':contract.sha(self.raw),
            'nativeCornerArchive':{'path':str(self.archive),'sha256':contract.sha(self.archive)},'frozenInputs':{},'statureApplications':0,'attachmentWorld':np.eye(4).tolist()}
        self.parent.write_text(json.dumps(self.parent_data))
        self.config={'schemaVersion':2,'kind':'target-face-aware-lower-connector-trial','diagnosticOnly':True,'parentReceipt':str(self.parent),'parentReceiptSha256':contract.sha(self.parent),
            'targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),'protectedInputs':{},'planeLocalZMetres':-.015,'fullScaleLocalZMetres':-.035,
            'centreLocalXYMetres':[0,0],'minimumXYScale':[.99,.99],'maximumDisplacementMetres':.005}
    def tearDown(self):self.tmp.cleanup()
    def execute(self,cfg,name):
        path=self.root/(name+'.json');path.write_text(json.dumps(cfg));return c.execute(path,self.root/name)

    def test_original_bin_maps_rows_and_complete_native_upper_surface(self):
        _,r=self.execute(self.config,'trial');old,ob=read_glb(self.raw);new,nb=read_glb(r['candidate']);self.assertEqual(ob,nb[:len(ob)])
        self.assertEqual(embedded_maps(old,ob),embedded_maps(new,nb));self.assertEqual(old['materials'],new['materials'])
        self.assertEqual(r['proof']['sourceLowerDiskTopology']['eulerCharacteristic'],1);self.assertEqual(r['proof']['newAuthoredMeanNormalOppositionChildFaceIds'],[])
        self.assertFalse(r['productionAccepted']);self.assertFalse(r['clientAccepted'])
        a=np.load(r['nativeCornerArchive']['path']);b=np.load(self.archive);mask=a['connectorUpperFaceMask'];weights=a['connectorBarycentricNative'];ids=a['connectorParentFaceIds']
        for k in ('positions','normals','uvGltf','uvNative','tangents'):
            expected=np.einsum('fci,fij->fcj',weights,b[k][ids]);np.testing.assert_allclose(a[k][mask],expected[mask],atol=1e-17)
        op=old['meshes'][0]['primitives'][0];np_=new['meshes'][0]['primitives'][0];rows=accessor(old,ob,op['attributes']['POSITION']);upper=rows[:,1]>=float(np.float32(-.015))
        for k in op['attributes']:
            initial=accessor(old,ob,op['attributes'][k]);final=accessor(new,nb,np_['attributes'][k]);self.assertEqual(initial[upper].tobytes(),final[:len(initial)][upper].tobytes())

    def test_stale_cross_target_and_repeated_connector_rejected_before_output(self):
        cfg=copy.deepcopy(self.config);cfg['parentReceiptSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'frozen input'):self.execute(cfg,'stale')
        wrong=copy.deepcopy(self.parent_data);wrong['targetId']='wrong-target';self.parent.write_text(json.dumps(wrong));cfg=copy.deepcopy(self.config);cfg['parentReceiptSha256']=contract.sha(self.parent)
        with self.assertRaises(ValueError):self.execute(cfg,'cross')
        self.parent.write_text(json.dumps(self.parent_data));self.config['parentReceiptSha256']=contract.sha(self.parent);_,r=self.execute(self.config,'first')
        cfg=copy.deepcopy(self.config);cfg['parentReceipt']=str(self.root/'first/geometry.json');cfg['parentReceiptSha256']=contract.sha(cfg['parentReceipt'])
        with self.assertRaisesRegex(ValueError,'One original waist'):self.execute(cfg,'repeat')
        for name in ('stale','cross','repeat'):self.assertFalse((self.root/name).exists())

if __name__=='__main__':unittest.main()

