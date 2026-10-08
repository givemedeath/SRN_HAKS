"""Independent waist field differential, direction, preservation and binding checks."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import target_contract as contract
from deform_target_chest_waist import determinant_bound,field,transport,execute
from target_part_pipeline import execute as fit
from test_target_part_pipeline import target_fixture
from test_mirror_stock_limb_part import fixture
from place_purposebuilt_pelvis import read_glb,write_glb,raw_corners,accessor

def controls():
    return dict(maximumDisplacementMetres=.025,lateralTransition=[.090,.145],
                zTransition=[1.227406528,1.287406528],lateralCentreWorldX=-.003901888)

class WaistFieldTests(unittest.TestCase):
    def test_only_sides_move_inward_with_exact_central_yz_and_upper_preservation(self):
        c=controls();x=c['lateralCentreWorldX']
        p=np.array([[x+.08,0,1.20],[x+.17,.12,1.20],[x-.17,-.1,1.20],[x+.17,.2,1.30]])
        q,j=field(p,c)
        np.testing.assert_array_equal(q[[0,3]],p[[0,3]])
        np.testing.assert_array_equal(q[:,1:],p[:,1:])
        np.testing.assert_allclose(q[1:3,0]-p[1:3,0],[-.025,.025],atol=1e-15)
        np.testing.assert_array_equal(j[[0,3]],np.tile(np.eye(3),(2,1,1)))

    def test_analytic_jacobian_agrees_with_independent_numerical_derivative(self):
        c=controls();p=np.array([[.110,0,1.25],[-.112,.04,1.26],[.2,0,1.20]])
        _,j=field(p,c);numerical=np.zeros_like(j);eps=1e-7
        for axis in range(3):
            v=np.eye(3)[axis]*eps
            numerical[:,:,axis]=(field(p+v,c)[0]-field(p-v,c)[0])/(2*eps)
        np.testing.assert_allclose(j,numerical,atol=2e-8,rtol=2e-8)

    def test_global_determinant_and_lateral_monotonicity_protect_against_fold(self):
        c=controls();x=np.linspace(-.3,.3,12001);p=np.column_stack((x,np.zeros_like(x),np.full_like(x,1.20)))
        q,j=field(p,c);bound=determinant_bound(c)
        self.assertAlmostEqual(bound,.318181818181818,places=12)
        self.assertGreater(np.diff(q[:,0]).min(),0)
        self.assertGreaterEqual(np.linalg.det(j).min(),bound-1e-12)
        self.assertAlmostEqual(np.linalg.det(field([[c['lateralCentreWorldX']+.1175,0,1.20]],c)[1])[0],bound)

    def test_c1_derivative_at_upper_and_lateral_support(self):
        c=controls();x=c['lateralCentreWorldX']
        p=np.array([[x+.09,0,1.20],[x-.09,0,1.20],[x+.18,0,c['zTransition'][1]]])
        q,j=field(p,c)
        np.testing.assert_array_equal(q,p);np.testing.assert_array_equal(j,np.tile(np.eye(3),(3,1,1)))

    def test_authored_normal_inverse_transpose_and_tangent_transport_keep_lengths_and_sign(self):
        _,j=field([[.11,0,1.25],[0,0,1.25]],controls())
        n=np.tile([0,0,1.3],(2,1));t=np.tile([1.2,0,0,-1],(2,1))
        nn,tt=transport(n,t,j,np.array([True,False]))
        expected=np.linalg.inv(j[0]).T@n[0];expected*=1.3/np.linalg.norm(expected)
        np.testing.assert_allclose(nn[0],expected,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(nn,axis=1),1.3,atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(tt[:,:3],axis=1),1.2,atol=1e-12)
        self.assertAlmostEqual(np.dot(nn[0],tt[0,:3]),0,places=12)
        np.testing.assert_array_equal(tt[:,3],t[:,3]);np.testing.assert_array_equal(nn[1],n[1])

    def test_unbounded_nonfinite_or_foldable_configurations_fail(self):
        for key,value in [('maximumDisplacementMetres',.036),('maximumDisplacementMetres',float('nan')),
                          ('maximumDisplacementMetres',True),('lateralCentreWorldX',float('inf')),
                          ('lateralTransition',[.09,.10]),('zTransition',[1.3,1.2])]:
            c=controls();c[key]=value
            with self.assertRaises(ValueError):determinant_bound(c)

class WaistSerializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target=self.root/'target.json';self.target.write_text(json.dumps(target_fixture()))
        d,b=fixture();self.raw=self.root/'raw.glb';write_glb(self.raw,d,b)
        job=self.root/'job.json';job.write_text(json.dumps(dict(state='success',promptId='fixture',
            outputs=[dict(localPath=str(self.raw),sha256=contract.sha(self.raw))])))
        fc=dict(schemaVersion=2,operation='fit',part='chest',coordinateSpace='working',
                targetContract=str(self.target),targetContractSha256=contract.sha(self.target),
                source=str(self.raw),sourceSha256=contract.sha(self.raw),sourceReceipt=str(job),
                sourceReceiptSha256=contract.sha(job),uniformScale=1,
                rotationDegreesXYZ=[0,0,0],sourceAnchorNwn=[0,0,0],targetAnchorLocal=[0,0,0])
        f=self.root/'fit.json';f.write_text(json.dumps(fc));self.parent=fit(f,self.root/'fitted')
        self.parent_data=json.loads(self.parent.read_text())
        self.config=dict(schemaVersion=2,kind='target-chest-waist-field-trial',diagnosticOnly=True,
            parentReceipt=str(self.parent),parentReceiptSha256=contract.sha(self.parent),
            targetContract=str(self.target),targetContractSha256=contract.sha(self.target),protectedInputs={},
            maximumDisplacementMetres=.025,lateralTransition=[.09,.145],zTransition=[-.5,.7],lateralCentreWorldX=0)

    def tearDown(self):self.tmp.cleanup()

    def run_config(self,c,name='taper'):
        p=self.root/(name+'.json');p.write_text(json.dumps(c));return execute(p,self.root/name)

    def test_serialized_maps_uv_indices_tangent_sign_and_outside_support_corners_are_exact(self):
        _,r=self.run_config(self.config)
        old,ob=read_glb(self.parent_data['candidate']);new,nb=read_glb(r['candidate'])
        self.assertEqual(nb[:len(ob)],ob);self.assertEqual(new['materials'],old['materials'])
        op,on,ou,_=raw_corners(old,ob);p,n,u,_=raw_corners(new,nb)
        np.testing.assert_array_equal(u,ou);np.testing.assert_array_equal(p[:,:,1:],op[:,:,1:])
        self.assertGreater(r['proof']['changedVertexCount'],0)
        self.assertTrue(r['proof']['authoritativeOutsideSupportNativeCornersExact'])
        self.assertFalse(r['productionAccepted']);self.assertFalse(r['clientAccepted'])
        self.assertEqual(old['meshes'][0]['primitives'][0]['indices'],new['meshes'][0]['primitives'][0]['indices'])
        ot=accessor(old,ob,old['meshes'][0]['primitives'][0]['attributes']['TANGENT'])
        nt=accessor(new,nb,new['meshes'][0]['primitives'][0]['attributes']['TANGENT'])
        np.testing.assert_array_equal(nt[:,3],ot[:,3])

    def test_stale_parent_target_and_unknown_controls_are_rejected(self):
        c=copy.deepcopy(self.config);c['parentReceiptSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen'):self.run_config(c,'stale')
        c=copy.deepcopy(self.config);c['unboundedExtra']=1
        with self.assertRaisesRegex(ValueError,'Unknown'):self.run_config(c,'unknown')
        self.target.write_text(self.target.read_text()+' ')
        with self.assertRaises(ValueError):self.run_config(self.config,'target_changed')

    def test_repeated_waist_parent_is_rejected(self):
        _,r=self.run_config(self.config)
        c=copy.deepcopy(self.config);c['parentReceipt']=str(self.root/'taper/geometry.json')
        c['parentReceiptSha256']=contract.sha(c['parentReceipt'])
        with self.assertRaisesRegex(ValueError,'Original fitted'):self.run_config(c,'twice')

if __name__=='__main__':unittest.main()
