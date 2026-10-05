"""Shin-only taper math, discrete conservation and provenance regressions."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import target_contract as contract
import target_part_pipeline as pipeline
import taper_target_shin_terminal as taper
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,rotation_xyz,write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture

class FieldTests(unittest.TestCase):
    def setUp(self):
        self.origin=np.array([.013,-.021,.17]);self.basis=rotation_xyz([13,-9,21])
        self.uvw=np.array([[.03,.02,-.02],[.045,-.013,.023],[-.06,.028,.059],[.04,.02,.075],[.08,-.07,.12]])
        self.p=self.uvw@self.basis.T+self.origin
    def test_axial_coordinate_and_exact_upper_calf_for_all_trials(self):
        for factor in taper.APPROVED_FACTORS:
            q,j,m,coords,s=taper.field(self.p,factor,.075,self.origin,self.basis)
            self.assertTrue(np.allclose(((q-self.origin)@self.basis)[:,2],self.uvw[:,2],atol=1e-15,rtol=0))
            self.assertTrue(np.array_equal(q[~m],self.p[~m]));self.assertTrue(np.array_equal(j[~m],np.tile(np.eye(3),(np.count_nonzero(~m),1,1))))
            self.assertAlmostEqual(s[0],factor);self.assertTrue(np.all(s>=factor));self.assertTrue(np.all(s<=1))
            self.assertTrue(np.allclose(np.linalg.det(j),s*s,atol=1e-15))
    def test_jacobian_matches_independent_finite_difference(self):
        q,j,*_=taper.field(self.p,.65,.075,self.origin,self.basis)
        for i in [0,1,2,4]:
            for d in range(3):
                delta=np.zeros(3);delta[d]=1e-7
                plus=taper.field(self.p[[i]]+delta,.65,.075,self.origin,self.basis)[0][0]
                minus=taper.field(self.p[[i]]-delta,.65,.075,self.origin,self.basis)[0][0]
                self.assertTrue(np.allclose((plus-minus)/2e-7,j[i,:,d],atol=3e-9,rtol=0))
    def test_smooth_identity_join(self):
        points=np.array([[.04,.02,t] for t in [.075-1e-8,.075,.075+1e-8]])@self.basis.T+self.origin
        q,j,*_=taper.field(points,.55,.075,self.origin,self.basis)
        self.assertLess(np.max(abs(j-np.eye(3))),1e-12)
        self.assertLess(np.max(abs(q-points)),1e-15)
    def test_covector_and_tangent_transport_magnitude_and_parity(self):
        q,j,m,*_=taper.field(self.p,.55,.075,self.origin,self.basis)
        n=np.tile(self.basis[:,2]*1.3,(len(self.p),1));t=np.tile(np.r_[self.basis[:,0]*1.2,-1.],(len(self.p),1))
        nn,tt=taper.transport(n,t,j,m)
        self.assertTrue(np.allclose(np.linalg.norm(nn,axis=1),1.3,atol=1e-15))
        self.assertTrue(np.allclose(np.linalg.norm(tt[:,:3],axis=1),1.2,atol=1e-15))
        self.assertTrue(np.array_equal(tt[:,3],t[:,3]));self.assertTrue(np.array_equal(nn[~m],n[~m]));self.assertTrue(np.array_equal(tt[~m],t[~m]))
        for i in np.flatnonzero(m):
            expected=np.linalg.solve(j[i].T,n[i]);expected*=1.3/np.linalg.norm(expected)
            self.assertTrue(np.allclose(nn[i],expected,atol=1e-15))
            self.assertAlmostEqual(nn[i]@(j[i]@t[i,:3]),0,places=13)
            self.assertAlmostEqual(nn[i]@tt[i,:3],0,places=13)
    def test_unknown_factors_and_nonproper_basis_rejected(self):
        for factor in [1.,0.,-.5,.7,float('nan')]:
            with self.subTest(factor=factor),self.assertRaises(ValueError):taper.field(self.p,factor,.075,self.origin,self.basis)
        for b in [self.basis*1.1,self.basis@np.diag([-1,1,1]),np.full((3,3),float('nan'))]:
            with self.assertRaises(ValueError):taper.field(self.p,.75,.075,self.origin,b)
        with self.assertRaises(ValueError):taper.field(self.p,.75,.08,self.origin,self.basis)
        with self.assertRaises(ValueError):taper.field(np.array([[0,0,float('nan')]]),.75,.075,self.origin,self.basis)
    def test_invalid_shading_and_negative_determinant_fail_closed(self):
        n=np.array([[0,0,1.3]]);t=np.array([[1.2,0,0,-1.]])
        for nn,tt,j in [(np.zeros((1,3)),t,np.eye(3)[None]),(n,np.array([[0,0,1.,1]]),np.eye(3)[None]),(n,np.array([[1,0,0,0.]]),np.eye(3)[None]),(n,t,np.diag([-1.,1,1])[None]),(n,t,np.full((1,3,3),float('nan')))]:
            with self.assertRaises(ValueError):taper.transport(nn,tt,j,[True])

class ConservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        td=target_fixture();td['identity']['race']='troll'
        for space,factor in [('working',1.),('runtime',10/7)]:
            td['rig']['frames'][space]['lshin_g']=(np.eye(4)+np.array([[0,0,0,0],[0,0,0,0],[0,0,0,.2*factor],[0,0,0,0]])).tolist()
        self.target=self.root/'target.json';self.target.write_text(json.dumps(td));self.td=td
        doc,blob=fixture();self.source=self.root/'source.glb';write_glb(self.source,doc,blob)
        self.job=self.root/'generation.json';self.job.write_text(json.dumps({'state':'success','promptId':'test','outputs':[{'localPath':str(self.source),'sha256':contract.sha(self.source)}]}))
        fc={'schemaVersion':2,'operation':'fit','part':'shinl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),'source':str(self.source),'sourceSha256':contract.sha(self.source),'sourceReceipt':str(self.job),'sourceReceiptSha256':contract.sha(self.job),'uniformScale':.3,'rotationDegreesXYZ':[0,0,0],'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[.02,.01,-.22]}
        fp=self.root/'fit-config.json';fp.write_text(json.dumps(fc));self.parent_path=pipeline.execute(fp,self.root/'parent');self.parent=json.loads(self.parent_path.read_text())
        self.protected=self.root/'unchanged-foot-rig-neighbors.bin';self.protected.write_bytes(b'untouched')
    def tearDown(self):self.tmp.cleanup()
    def config(self):
        origin,basis=taper.frozen_axis(self.td,'shinl')
        return {'schemaVersion':2,'kind':'target-shin-terminal-taper','diagnosticOnly':True,'part':'shinl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),'rigRevision':self.td['rig']['revision'],'source':self.parent['candidate'],'sourceSha256':self.parent['candidateSha256'],'sourceReceipt':str(self.parent_path),'sourceReceiptSha256':contract.sha(self.parent_path),'distalRadialFactor':.65,'unchangedFromAxialMetres':.075,'axisOriginAttachmentLocal':origin.tolist(),'axisBasisColumnsAttachmentLocal':basis.tolist(),'protectedInputs':{str(self.protected):contract.sha(self.protected)}}
    def run_config(self,c,name='trial'):
        p=self.root/(name+'-config.json');p.write_text(json.dumps(c));rp=taper.execute(p,self.root/name);return rp,json.loads(rp.read_text())
    def test_exact_attribute_face_and_source_bin_conservation(self):
        _,r=self.run_config(self.config());old,blob=read_glb(self.parent['candidate']);new,binary=read_glb(r['candidate']);oa=old['meshes'][0]['primitives'][0];na=new['meshes'][0]['primitives'][0]
        self.assertEqual(blob,binary[:len(blob)]);self.assertEqual(old['materials'],new['materials']);self.assertEqual(embedded_maps(old,blob),embedded_maps(new,binary));self.assertEqual(old['nodes'],new['nodes'])
        self.assertEqual(oa['indices'],na['indices']);self.assertEqual(oa['attributes']['TEXCOORD_0'],na['attributes']['TEXCOORD_0']);self.assertEqual(oa['attributes']['COLOR_0'],na['attributes']['COLOR_0'])
        self.assertEqual(old['accessors'],new['accessors'][:-3]);self.assertEqual(old['bufferViews'],new['bufferViews'][:-3])
        with np.load(r['nativeCornerArchive']['path'],allow_pickle=False) as a,np.load(self.parent['nativeCornerArchive']['path'],allow_pickle=False) as pa:
            mask=a['taperEditedSourceVertexMask'];self.assertTrue(mask.any());self.assertTrue((~mask).any());faces=a['taperParentSourceFaces'];corner_mask=mask[faces]
            for sem,key in [('POSITION','positions'),('NORMAL','normals'),('TANGENT','tangents')]:
                original=accessor(old,blob,oa['attributes'][sem]);actual=accessor(new,binary,na['attributes'][sem]);self.assertEqual(original[~mask].tobytes(),actual[~mask].tobytes());self.assertEqual(pa[key][~corner_mask].tobytes(),a[key][~corner_mask].tobytes())
            for key in ['sourceTriangleIds','sourceCornerOrder','uvGltf','uvNative','sourcePositions','sourceNormals']:self.assertTrue(np.array_equal(pa[key],a[key]))
        self.assertEqual(r['attachmentWorld'],self.parent['attachmentWorld']);self.assertEqual(r['statureApplications'],0);self.assertFalse(r['productionAccepted']);self.assertFalse(r['connectorAccepted']);self.assertEqual(self.protected.read_bytes(),b'untouched')
        for key in ['boundaryEdges','nonmanifoldEdges','nonmanifoldVertexLinks','inconsistentManifoldEdgeWindings','zeroAreaFaces','components','eulerCharacteristic','exactPositionVertices','faces']:self.assertEqual(r['proof']['beforeTopology'][key],r['proof']['afterTopology'][key])
        self.assertGreater(r['proof']['minimumDiscreteFaceNormalDot'],0)
    def test_parent_reuse_is_same_original_and_cumulative_rejected(self):
        path,r=self.run_config(self.config());c=self.config();c.update(source=r['candidate'],sourceSha256=r['candidateSha256'],sourceReceipt=str(path),sourceReceiptSha256=contract.sha(path))
        with self.assertRaisesRegex(ValueError,'cumulative'):self.run_config(c,'double')
    def test_part_runtime_unknown_fit_controls_rejected(self):
        for key,value in [('part','footl'),('coordinateSpace','runtime'),('uniformScale',.5),('perAxisScale',[.5,1,1]),('translation',[0,0,.01])]:
            c=self.config();c[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_config(c,key)
    def test_changed_neighbor_and_source_pin_rejected(self):
        c=self.config();self.protected.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen taper input'):self.run_config(c,'changed-foot')
        c=self.config();c['sourceSha256']='bad'
        with self.assertRaisesRegex(ValueError,'Frozen input'):self.run_config(c,'changed-source')
    def test_changed_axis_or_revision_rejected(self):
        c=self.config();c['axisOriginAttachmentLocal'][0]+=.001
        with self.assertRaisesRegex(ValueError,'frame differs'):self.run_config(c,'axis')
        c=self.config();c['rigRevision']='guessed'
        with self.assertRaisesRegex(ValueError,'revision differs'):self.run_config(c,'revision')
    def test_stature_count_and_global_target_ownership_rejected(self):
        c=self.config();changed=copy.deepcopy(self.parent);changed['statureApplications']=1;p=self.root/'bad-parent.json';p.write_text(json.dumps(changed));c.update(sourceReceipt=str(p),sourceReceiptSha256=contract.sha(p))
        with self.assertRaisesRegex(ValueError,'stature conversion'):self.run_config(c,'runtime-parent')
        td=copy.deepcopy(self.td);td['identity']['race']='human';self.target.write_text(json.dumps(td));c=self.config()
        with self.assertRaisesRegex(ValueError,'Troll male'):self.run_config(c,'human')
    def test_changed_authoritative_corner_correspondence_rejected(self):
        c=self.config();pa=self.parent['nativeCornerArchive']['path']
        with np.load(pa,allow_pickle=False) as a:arrays={k:a[k].copy() for k in a.files}
        arrays['positions'][0,0,0]+=.001
        archive=self.root/'wrong-corners.npz';np.savez_compressed(archive,**arrays)
        parent=copy.deepcopy(self.parent);parent['nativeCornerArchive']={'path':str(archive),'sha256':contract.sha(archive)}
        path=self.root/'wrong-parent.json';path.write_text(json.dumps(parent));c.update(sourceReceipt=str(path),sourceReceiptSha256=contract.sha(path))
        with self.assertRaisesRegex(ValueError,'parent correspondence'):self.run_config(c,'wrong-corners')
    def test_distinct_frozen_ankle_required(self):
        td=copy.deepcopy(self.td);td['rig']['frames']['working']['lshin_g']=td['rig']['frames']['working']['lfoot_g']
        with self.assertRaisesRegex(ValueError,'Distinct'):taper.frozen_axis(td,'shinl')
    def test_duplicate_output_is_rejected_without_overwrite(self):
        path,r=self.run_config(self.config());h=contract.sha(path)
        with self.assertRaisesRegex(ValueError,'Fresh immutable'):self.run_config(self.config())
        self.assertEqual(h,contract.sha(path))

if __name__=='__main__':unittest.main()
