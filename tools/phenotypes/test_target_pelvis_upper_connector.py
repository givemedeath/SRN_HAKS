"""Focused tests of the upper pelvis map, complete lower-surface protection and provenance."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import repair_target_pelvis_upper_connector as c
import target_contract as contract
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,raw_corners,read_glb,write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture

class UpperFieldTests(unittest.TestCase):
    def test_c1_jacobian_and_whole_lower_clipped_surface(self):
        p=np.array([[.1,-.08,.027],[.09,.03,.015],[.08,.02,.04],[.04,.02,-.01]])
        q,j=c.upper_field(p,.015,.04,[0,.048],[.663,.562]);numeric=np.zeros_like(j);eps=1e-7
        for axis in range(3):
            delta=np.eye(3)[axis]*eps
            numeric[:,:,axis]=(c.upper_field(p+delta,.015,.04,[0,.048],[.663,.562])[0]-
                               c.upper_field(p-delta,.015,.04,[0,.048],[.663,.562])[0])/(2*eps)
        np.testing.assert_allclose(j,numeric,atol=3e-5,rtol=3e-5)
        np.testing.assert_array_equal(q[[1,3]],p[[1,3]])
        np.testing.assert_array_equal(j[[1,3]],np.tile(np.eye(3),(2,1,1)))
        np.testing.assert_array_equal(q[:,2],p[:,2]);self.assertGreaterEqual(np.linalg.det(j).min(),.663*.562)
        for scales in ([0,1],[.1,.5],[float('nan'),1]):
            with self.assertRaises(ValueError):c.upper_field(p,.015,.04,[0,0],scales)

    def test_multi_plane_ancestry_preserves_uv_seams_and_actual_lower_faces(self):
        p=np.array([[-.02,.01,0],[.02,.04,0],[0,.04,.02],[-.02,.01,0],[.02,.04,0],[0,.01,-.02]],dtype='<f4')
        attrs={'POSITION':p,'NORMAL':np.tile([0,0,1.3],(6,1)).astype('<f4'),
               'TEXCOORD_0':np.array([[0,0],[1,0],[.5,1],[.2,.3],[.7,.8],[1,1]],dtype='<f4'),
               'TANGENT':np.tile([1.2,0,0,-1],(6,1)).astype('<f4')}
        faces=np.array([[0,1,2],[3,5,4]])
        s=c.subdivide(attrs,faces,[.015,.020,.025,.030,.035,.040])
        for k,v in attrs.items():
            self.assertEqual(s['attributes'][k][:len(v)].tobytes(),v.tobytes())
            expected=np.einsum('fci,fij->fcj',s['barycentric'],v[faces[s['parentFaceIds']]])
            np.testing.assert_allclose(s['attributes'][k][s['faces']],expected,atol=6e-8)
        local=s['attributes']['POSITION'].astype(float)@BASIS.T
        q,j=c.upper_field(local,s['plane'],.04,[0,0],[.7,.7]);mask=s['lowerFaceMask']
        np.testing.assert_array_equal(q[s['faces'][mask]],local[s['faces'][mask]])
        self.assertTrue(np.all(local[s['faces'][mask],2]<=s['plane']))
        attrs['TANGENT'][1,3]=1
        with self.assertRaisesRegex(ValueError,'handedness'):c.subdivide(attrs,faces,[.015,.02])

class SerializedUpperTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target=self.root/'target.json';t=target_fixture();self.target.write_text(json.dumps(t))
        d,b=fixture();d['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0');payload=bytearray(b)
        p=np.array([[-.035,.005,0],[-.015,.005,0],[-.025,.005,.02],[-.025,.035,.007],
                    [.015,.005,0],[.035,.005,0],[.025,.005,.02],[.025,.035,.007]],dtype='<f4')
        f=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3],[4,6,5],[4,5,7],[5,6,7],[6,4,7]],dtype='<u4')
        a={'POSITION':p,'NORMAL':np.tile([0,1.2,0],(8,1)).astype('<f4'),
           'TEXCOORD_0':np.array([[.1,.1],[.2,.1],[.1,.2],[.2,.2]]*2,dtype='<f4'),
           'TANGENT':np.tile([1.1,0,0,-1],(8,1)).astype('<f4')}
        def append(v,indices=False):
            payload.extend(b'\0'*(-len(payload)%4));offset=len(payload);payload.extend(v.tobytes())
            d['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':v.nbytes})
            d['accessors'].append({'bufferView':len(d['bufferViews'])-1,'componentType':5125 if indices else 5126,
                'count':v.size if indices else len(v),'type':'SCALAR' if indices else 'VEC'+str(v.shape[1])})
            return len(d['accessors'])-1
        q=d['meshes'][0]['primitives'][0]
        for k,v in a.items():q['attributes'][k]=append(v)
        q['indices']=append(f.reshape(-1),True);d['buffers'][0]['byteLength']=len(payload)
        self.source=self.root/'parent.glb';write_glb(self.source,d,bytes(payload))
        pp,nn,uv,_=raw_corners(d,bytes(payload));tangent=a['TANGENT'].astype(float);tangent[:,:3]=tangent[:,:3]@BASIS.T
        self.native=self.root/'parent-native.npz'
        np.savez_compressed(self.native,positions=pp,normals=nn,uvGltf=uv,uvNative=np.stack((uv[:,:,0],1-uv[:,:,1]),2),
                            tangents=tangent[f],sourceTriangleIds=np.arange(len(f)))
        self.parent=self.root/'geometry.json'
        self.parent_data={'schemaVersion':2,'kind':'target-part-geometry','operation':'detached-component-removal',
          **contract.binding(self.target,t,'working'),'part':'pelvis','joint':'pelvis_g','statureApplications':0,
          'candidate':str(self.source),'candidateSha256':contract.sha(self.source),'attachmentWorld':np.eye(4).tolist(),
          'nativeCornerArchive':{'path':str(self.native),'sha256':contract.sha(self.native)},'frozenInputs':{}}
        self.parent.write_text(json.dumps(self.parent_data))
        self.cfg={'schemaVersion':2,'kind':'target-face-aware-pelvis-upper-connector-trial','diagnosticOnly':True,
          'parentReceipt':str(self.parent),'parentReceiptSha256':contract.sha(self.parent),'targetContract':str(self.target),
          'targetContractSha256':contract.sha(self.target),'protectedInputs':{},'planeLocalZMetres':.015,
          'fullScaleLocalZMetres':.025,'subdivisionPlanesLocalZMetres':[.015,.020,.025],
          'centreLocalXYMetres':[0,0],'endXYScale':[.99,.99],'maximumDisplacementMetres':.005,'maximumFaces':60000,
          'upperSkinParentFaceIds':np.flatnonzero(p[f,1].max(1)>float(np.float32(.015))).tolist()}
    def tearDown(self):self.tmp.cleanup()
    def run_trial(self,cfg,name):
        path=self.root/(name+'.json');path.write_text(json.dumps(cfg));return c.execute(path,self.root/name)

    def test_source_maps_attributes_and_complete_native_lower_surface(self):
        _,r=self.run_trial(self.cfg,'trial');old,ob=read_glb(self.source);new,nb=read_glb(r['candidate'])
        self.assertEqual(ob,nb[:len(ob)]);self.assertEqual(embedded_maps(old,ob),embedded_maps(new,nb))
        self.assertEqual(old['materials'],new['materials']);self.assertEqual(r['proof']['newAuthoredMeanNormalOppositionChildFaceIds'],[])
        self.assertFalse(r['clientAccepted']);self.assertFalse(r['productionAccepted'])
        a=np.load(r['nativeCornerArchive']['path']);b=np.load(self.native);w=a['connectorBarycentricNative'];ids=a['connectorParentFaceIds'];lower=a['connectorLowerFaceMask']
        for k in ('positions','normals','uvGltf','uvNative','tangents'):
            expected=np.einsum('fci,fij->fcj',w,b[k][ids]);np.testing.assert_allclose(a[k][lower],expected[lower],atol=8e-17)
        oq=old['meshes'][0]['primitives'][0];nq=new['meshes'][0]['primitives'][0]
        original=accessor(old,ob,oq['attributes']['POSITION']);mask=original[:,1]<=float(np.float32(.015))
        for k in oq['attributes']:
            before=accessor(old,ob,oq['attributes'][k]);after=accessor(new,nb,nq['attributes'][k])
            self.assertEqual(before[mask].tobytes(),after[:len(before)][mask].tobytes())
        self.assertEqual(r['proof']['twoUpperDiskTopology']['components'],2)

    def test_stale_parent_cross_target_and_repeated_connector_rejected(self):
        cfg=copy.deepcopy(self.cfg);cfg['parentReceiptSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen'):self.run_trial(cfg,'stale')
        p=copy.deepcopy(self.parent_data);p['targetId']='another-target';self.parent.write_text(json.dumps(p))
        cfg=copy.deepcopy(self.cfg);cfg['parentReceiptSha256']=contract.sha(self.parent)
        with self.assertRaises(ValueError):self.run_trial(cfg,'cross-target')
        p=copy.deepcopy(self.parent_data);p['operation']='face-aware-pelvis-upper-connector-plane-subdivision';self.parent.write_text(json.dumps(p))
        cfg=copy.deepcopy(self.cfg);cfg['parentReceiptSha256']=contract.sha(self.parent)
        with self.assertRaisesRegex(ValueError,'repeated'):self.run_trial(cfg,'repeated')

    def test_incomplete_skin_set_and_wider_support_rejected(self):
        cfg=copy.deepcopy(self.cfg);cfg['upperSkinParentFaceIds']=cfg['upperSkinParentFaceIds'][:-1]
        with self.assertRaisesRegex(ValueError,'skin'):self.run_trial(cfg,'ownership')
        cfg=copy.deepcopy(self.cfg);cfg['planeLocalZMetres']=.005;cfg['subdivisionPlanesLocalZMetres'][0]=.005
        with self.assertRaisesRegex(ValueError,'short'):self.run_trial(cfg,'wide')

if __name__=='__main__':unittest.main()

