"""Terminal XY field protects upper body, preserves maps and rejects repeated edits."""
import copy,json,unittest
import numpy as np
import deform_target_terminal_envelope as terminal
import test_target_chest_waist as waist_fixture
from place_purposebuilt_pelvis import read_glb,raw_corners,accessor
import target_contract as contract


def controls():
    return dict(maximumDisplacementMetres=.08,minimumXYScale=[.5,.5],
                centreWorldXY=[-.003901888,.0293934],zTransition=[1.197406528,1.257406528])


class TerminalEnvelopeTests(unittest.TestCase):
    def test_affine_lower_planes_and_exact_upper_z(self):
        c=controls();centre=np.asarray(c['centreWorldXY'])
        p=np.array([[centre[0]+.12,centre[1]-.08,1.17],
                    [centre[0]-.12,centre[1]+.08,1.17],
                    [.15,.14,1.27]])
        q,j=terminal.field(p,c)
        np.testing.assert_allclose(q[:2,:2],centre+(p[:2,:2]-centre)*.5,atol=1e-15)
        np.testing.assert_array_equal(q[:,2],p[:,2])
        np.testing.assert_array_equal(q[2],p[2]);np.testing.assert_array_equal(j[2],np.eye(3))
        self.assertAlmostEqual(terminal.determinant_bound(c),.25)

    def test_jacobian_independent_finite_difference_and_c1_support(self):
        c=controls();p=np.array([[.12,-.08,1.218],[.08,.06,1.23]])
        _,j=terminal.field(p,c);eps=1e-7;numeric=np.zeros_like(j)
        for axis in range(3):
            delta=np.eye(3)[axis]*eps
            numeric[:,:,axis]=(terminal.field(p+delta,c)[0]-terminal.field(p-delta,c)[0])/(2*eps)
        np.testing.assert_allclose(j,numeric,atol=2e-8,rtol=2e-8)
        q,j=terminal.field([[.1,.05,c['zTransition'][1]]],c)
        np.testing.assert_array_equal(q,[[.1,.05,c['zTransition'][1]]]);np.testing.assert_array_equal(j[0],np.eye(3))
        _,j=terminal.field([[.1,.05,c['zTransition'][0]]],c)
        np.testing.assert_array_equal(j[0],np.diag([.5,.5,1]))

    def test_invalid_collapsing_nonfinite_or_unbounded_inputs_reject(self):
        for key,value in [('minimumXYScale',[0,1]),('minimumXYScale',[.1,.5]),
                          ('minimumXYScale',[1.1,.5]),('minimumXYScale',[float('nan'),1]),
                          ('centreWorldXY',[float('inf'),0]),('zTransition',[2,1]),
                          ('maximumDisplacementMetres',.081),('maximumDisplacementMetres',True)]:
            bad=controls();bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                terminal.determinant_bound(bad)

    def test_serialized_attributes_original_maps_and_tangent_sign_preserved(self):
        f=waist_fixture.WaistSerializationTests(methodName='test_repeated_waist_parent_is_rejected');f.setUp()
        try:
            cfg={k:v for k,v in f.config.items() if k not in ('lateralTransition','lateralCentreWorldX')}
            cfg.update(kind='target-chest-terminal-envelope-trial',minimumXYScale=[.97,.96],
                       centreWorldXY=[0,0],maximumDisplacementMetres=.08)
            path=f.root/'terminal.json';path.write_text(json.dumps(cfg))
            _,r=terminal.execute(path,f.root/'terminal')
            old,ob=read_glb(f.parent_data['candidate']);new,nb=read_glb(r['candidate'])
            self.assertEqual(nb[:len(ob)],ob);self.assertEqual(old['materials'],new['materials'])
            op,on,ou,_=raw_corners(old,ob);p,n,u,_=raw_corners(new,nb)
            np.testing.assert_array_equal(p[:,:,2],op[:,:,2]);np.testing.assert_array_equal(u,ou)
            self.assertTrue(r['proof']['upperBodyEncodedAttributesExact'])
            self.assertTrue(r['proof']['authoritativeOutsideSupportNativeCornersExact'])
            self.assertGreater(r['proof']['changedVertexCount'],0)
            self.assertLessEqual(r['proof']['actualMaximumDisplacementMetres'],.08)
            self.assertFalse(r['clientAccepted']);self.assertFalse(r['productionAccepted'])
            oi=old['meshes'][0]['primitives'][0];ni=new['meshes'][0]['primitives'][0]
            self.assertEqual(oi['indices'],ni['indices'])
            np.testing.assert_array_equal(accessor(old,ob,oi['attributes']['TANGENT'])[:,3],
                                          accessor(new,nb,ni['attributes']['TANGENT'])[:,3])
            cfg['parentReceipt']=str(f.root/'terminal/geometry.json')
            cfg['parentReceiptSha256']=contract.sha(cfg['parentReceipt'])
            path=f.root/'twice.json';path.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'repeated terminal'):
                terminal.execute(path,f.root/'twice')
        finally:
            f.tearDown()


if __name__=='__main__':
    unittest.main()
