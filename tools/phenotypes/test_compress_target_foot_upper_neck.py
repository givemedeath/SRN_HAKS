"""Foot upper-neck Jacobian, sole/toe preservation and provenance regressions."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import target_contract as contract
import target_part_pipeline as pipeline
import compress_target_foot_upper_neck as taper
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,rotation_xyz,write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture

class FieldTests(unittest.TestCase):
    def setUp(self):
        self.origin=np.zeros(3);self.basis=np.eye(3)
        self.uvw=np.array([[.03,.02,-.02],[.045,-.013,0.],[-.06,.028,.005],[.04,.02,.009],[.08,-.07,.015],[.08,-.07,.04]])
        self.p=self.uvw@self.basis.T+self.origin
    def test_positive_axial_compression_and_exact_lower_foot_for_both_trials(self):
        for factor in taper.APPROVED_FACTORS:
            q,j,m,coords,s=taper.field(self.p,factor,.015,self.origin,self.basis)
            self.assertTrue(np.array_equal(q[~m],self.p[~m]));self.assertTrue(np.array_equal(j[~m],np.tile(np.eye(3),(np.count_nonzero(~m),1,1))))
            self.assertEqual(s[0],1.);self.assertEqual(s[-1],factor)
            self.assertTrue(np.all(s>=factor));self.assertTrue(np.all(s<=1));self.assertTrue(np.all(q[m,2]>0));self.assertTrue(np.all(q[m,2]<self.p[m,2]))
            self.assertTrue(np.all(np.diff(q[:,2])>0));self.assertGreaterEqual(np.linalg.det(j).min(),factor*factor*.4-1e-15)
            self.assertAlmostEqual(q[-2,2],.0105);self.assertAlmostEqual(q[-1,2],.0205)
    def test_jacobian_matches_independent_finite_difference(self):
        q,j,*_=taper.field(self.p,.65,.015,self.origin,self.basis)
        for i in [0,2,3,5]:
            for d in range(3):
                delta=np.zeros(3);delta[d]=1e-7
                plus=taper.field(self.p[[i]]+delta,.65,.015,self.origin,self.basis)[0][0]
                minus=taper.field(self.p[[i]]-delta,.65,.015,self.origin,self.basis)[0][0]
                self.assertTrue(np.allclose((plus-minus)/2e-7,j[i,:,d],atol=3e-9,rtol=0))
    def test_smooth_identity_and_positive_linear_tail_joins(self):
        for factor in taper.APPROVED_FACTORS:
            for at,expected in [(0.,np.eye(3)),(.015,np.diag([factor,factor,.4]))]:
                points=np.array([[.04,.02,at+dt] for dt in [-1e-8,0.,1e-8]])
                q,j,*_=taper.field(points,factor,.015,self.origin,self.basis)
                self.assertLess(np.max(abs(j-expected)),5e-10)
            self.assertTrue(np.array_equal(taper.field(np.zeros((1,3)),factor,.015,self.origin,self.basis)[0],np.zeros((1,3))))
    def test_axial_integral_matches_slope_quadrature(self):
        p=np.c_[np.zeros((10001,2)),np.linspace(0,.015,10001)];q,j,*_=taper.field(p,.8,.015,self.origin,self.basis)
        quadrature=np.trapezoid(j[:,2,2],p[:,2]);self.assertAlmostEqual(quadrature,q[-1,2],places=12)
    def test_covector_and_tangent_transport_magnitude_and_parity(self):
        q,j,m,*_=taper.field(self.p,.80,.015,self.origin,self.basis)
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
        for factor in [1.,0.,-.5,.7,.55,float('nan')]:
            with self.subTest(factor=factor),self.assertRaises(ValueError):taper.field(self.p,factor,.015,self.origin,self.basis)
        for b in [self.basis*1.1,self.basis@np.diag([-1,1,1]),np.full((3,3),float('nan'))]:
            with self.assertRaises(ValueError):taper.field(self.p,.80,.015,self.origin,b)
        with self.assertRaises(ValueError):taper.field(self.p,.80,.08,self.origin,self.basis)
        with self.assertRaises(ValueError):taper.field(np.array([[0,0,float('nan')]]),.80,.015,self.origin,self.basis)
    def test_invalid_shading_and_negative_determinant_fail_closed(self):
        n=np.array([[0,0,1.3]]);t=np.array([[1.2,0,0,-1.]])
        for nn,tt,j in [(np.zeros((1,3)),t,np.eye(3)[None]),(n,np.array([[0,0,1.,1]]),np.eye(3)[None]),(n,np.array([[1,0,0,0.]]),np.eye(3)[None]),(n,t,np.diag([-1.,1,1])[None]),(n,t,np.full((1,3,3),float('nan')))]:
            with self.assertRaises(ValueError):taper.transport(nn,tt,j,[True])

class ConservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        td=target_fixture();td['identity']['race']='troll'
        for space,factor in [('working',1.),('runtime',10/7)]:
            td['rig']['frames'][space]['lfoot_g']=(np.eye(4)+np.array([[0,0,0,0],[0,0,0,0],[0,0,0,.2*factor],[0,0,0,0]])).tolist()
        self.target=self.root/'target.json';self.target.write_text(json.dumps(td));self.td=td
        doc,blob=fixture();self.source=self.root/'source.glb';write_glb(self.source,doc,blob)
        self.job=self.root/'generation.json';self.job.write_text(json.dumps({'state':'success','promptId':'test','outputs':[{'localPath':str(self.source),'sha256':contract.sha(self.source)}]}))
        fc={'schemaVersion':2,'operation':'fit','part':'footl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),'source':str(self.source),'sourceSha256':contract.sha(self.source),'sourceReceipt':str(self.job),'sourceReceiptSha256':contract.sha(self.job),'uniformScale':.3,'rotationDegreesXYZ':[0,0,0],'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[.02,.01,-.02]}
        fp=self.root/'fit-config.json';fp.write_text(json.dumps(fc));self.parent_path=pipeline.execute(fp,self.root/'parent');self.parent=json.loads(self.parent_path.read_text())
        pd,pb=read_glb(self.parent['candidate']);pp=pd['meshes'][0]['primitives'][0];summary=taper.topology(accessor(pd,pb,pp['attributes']['POSITION']),accessor(pd,pb,pp['indices']).reshape(-1,3));keys=['boundaryEdges','nonmanifoldEdges','nonmanifoldVertexLinks','inconsistentManifoldEdgeWindings','zeroAreaFaces','components','eulerCharacteristic','exactPositionVertices','faces','referencedSerializedVertices'];self.expected_topology={k:summary[k] for k in keys}
        self.protected=self.root/'unchanged-foot-rig-neighbors.bin';self.protected.write_bytes(b'untouched')
    def tearDown(self):self.tmp.cleanup()
    def config(self):
        origin,basis=taper.frozen_axis(self.td,'footl')
        return {'schemaVersion':2,'kind':'target-foot-upper-neck-compression','diagnosticOnly':True,'part':'footl','coordinateSpace':'working','targetContract':str(self.target),'targetContractSha256':contract.sha(self.target),'rigRevision':self.td['rig']['revision'],'source':self.parent['candidate'],'sourceSha256':self.parent['candidateSha256'],'sourceReceipt':str(self.parent_path),'sourceReceiptSha256':contract.sha(self.parent_path),'upperRadialFactor':.65,'transitionAxialMetres':.015,'axisOriginAttachmentLocal':origin.tolist(),'axisBasisColumnsAttachmentLocal':basis.tolist(),'protectedInputs':{str(self.protected):contract.sha(self.protected)},'axialDerivativeAboveTransition':.4,'expectedSourceTopology':self.expected_topology.copy()}
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
        for key,value in [('part','shinl'),('coordinateSpace','runtime'),('uniformScale',.5),('perAxisScale',[.5,1,1]),('translation',[0,0,.01])]:
            c=self.config();c[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_config(c,key)
    def test_changed_neighbor_and_source_pin_rejected(self):
        c=self.config();self.protected.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen taper input'):self.run_config(c,'changed-foot')
        c=self.config();c['sourceSha256']='bad'
        with self.assertRaisesRegex(ValueError,'Frozen input'):self.run_config(c,'changed-source')
    def test_changed_axis_or_revision_rejected(self):
        c=self.config();c['axisOriginAttachmentLocal'][0]+=.001
        with self.assertRaisesRegex(ValueError,'no recentering'):self.run_config(c,'axis')
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
    def test_no_axis_rotation_recenter_or_altered_axial_slope(self):
        c=self.config();c['axisBasisColumnsAttachmentLocal']=rotation_xyz([1,0,0]).tolist()
        with self.assertRaisesRegex(ValueError,'no recentering'):self.run_config(c,'rolled')
        c=self.config();c['axialDerivativeAboveTransition']=0.
        with self.assertRaisesRegex(ValueError,'positive upper axial derivative'):self.run_config(c,'collapsed')
    def test_declared_topology_cannot_waive_dropped_or_changed_metric(self):
        c=self.config();del c['expectedSourceTopology']['nonmanifoldEdges']
        with self.assertRaisesRegex(ValueError,'Complete explicit'):self.run_config(c,'missing-topology')
        c=self.config();c['expectedSourceTopology']['faces']+=1
        with self.assertRaisesRegex(ValueError,'declared original topology'):self.run_config(c,'guessed-topology')
    def test_coordinate_nm_owners_ignore_sorted_ids_but_reject_face_or_position_change(self):
        a={'nonmanifoldEdgeRecords':[{'exactPositionIds':[3,7],'positions':[[0,0,-1],[.1,0,-1]],'incidentFaces':[1,7,9]}]};b=copy.deepcopy(a);b['nonmanifoldEdgeRecords'][0]['exactPositionIds']=[5,12]
        self.assertEqual(taper.unresolved_topology_owners(a),taper.unresolved_topology_owners(b))
        b['nonmanifoldEdgeRecords'][0]['incidentFaces'][0]=2;self.assertNotEqual(taper.unresolved_topology_owners(a),taper.unresolved_topology_owners(b))
        b=copy.deepcopy(a);b['nonmanifoldEdgeRecords'][0]['positions'][0][0]=.001;self.assertNotEqual(taper.unresolved_topology_owners(a),taper.unresolved_topology_owners(b))
    def test_positive_band_quantization_ambiguity_is_not_waived(self):
        fc=json.loads((self.root/'fit-config.json').read_text());fc['targetAnchorLocal']=[0,0,0];fp=self.root/'zero-fit.json';fp.write_text(json.dumps(fc));path=pipeline.execute(fp,self.root/'zero-parent');parent=json.loads(path.read_text())
        with np.load(parent['nativeCornerArchive']['path'],allow_pickle=False) as a:arrays={k:a[k].copy() for k in a.files}
        self.assertEqual(arrays['positions'][0,0,2],0.);arrays['positions'][0,0,2]=1e-10;archive=self.root/'ambiguous-corners.npz';np.savez_compressed(archive,**arrays);parent['nativeCornerArchive']={'path':str(archive),'sha256':contract.sha(archive)};bad=self.root/'ambiguous-parent.json';bad.write_text(json.dumps(parent));c=self.config();c.update(source=parent['candidate'],sourceSha256=parent['candidateSha256'],sourceReceipt=str(bad),sourceReceiptSha256=contract.sha(bad))
        with self.assertRaisesRegex(ValueError,'boundary classification'):self.run_config(c,'ambiguous-positive-band')
    def test_duplicate_output_is_rejected_without_overwrite(self):
        path,r=self.run_config(self.config());h=contract.sha(path)
        with self.assertRaisesRegex(ValueError,'Fresh immutable'):self.run_config(self.config())
        self.assertEqual(h,contract.sha(path))

if __name__=='__main__':unittest.main()
