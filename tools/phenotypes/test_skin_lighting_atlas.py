"""Measured C1 protection, exact texel centers and guarded padding rejection tests."""
import unittest
import numpy as np
from skin_lighting_atlas import smoothstep,sample_texels,geometry_masks,pad_lineage,apply_padding


class GeometryLightingAtlasTests(unittest.TestCase):
    def plane(self,zoffset=0):
        p=np.array([[[0,0,-.1+zoffset],[1,0,.1+zoffset],[0,1,.1+zoffset]]]);n=np.tile([0,0,1.],(1,3,1));uv=np.array([[[0,0],[1,0],[0,1]]]);return p,n,uv
    def regions(self):return [{'originLocal':[0,0,0],'normalLocal':[0,0,1],'halfWidthMeters':.02,'fadeWidthMeters':.04}]
    def test_c1_value_and_endpoint_derivative(self):
        np.testing.assert_array_equal(smoothstep(np.array([-1,0,1,2])),[0,0,1,1]);self.assertAlmostEqual(float(smoothstep(.5)),.5)
        epsilon=1e-5;self.assertLess(float(smoothstep(epsilon))/epsilon,4e-5);self.assertLess(float(1-smoothstep(1-epsilon))/epsilon,4e-5)
    def test_gltf_texel_centers_and_repeat_borders(self):
        image=np.array([[10,20],[70,90]],dtype=float);uv=np.array([[.25,.25],[.75,.25],[.25,.75],[.75,.75]])
        np.testing.assert_array_equal(sample_texels(image,uv),[10,20,70,90]);self.assertEqual(sample_texels(image,np.array([[0,0]]),repeat=True)[0],47.5)
    def test_geometry_mask_preserves_exact_band_and_fades_same_crossing_triangle(self):
        p,n,uv=self.plane();m=geometry_masks(p,n,uv,['skin'],64,self.regions(),1)
        distance=abs(m['positionLocal'][:,:,2]);band=m['coverage']&(distance<=.02)
        self.assertTrue(band.any());self.assertFalse(m['influence'][band].any())
        outside=m['coverage']&(distance>.06)&~m['protected'];self.assertTrue(outside.any());np.testing.assert_allclose(m['influence'][outside],1)
        middle=m['coverage']&(distance>.028)&(distance<.05)&~m['protected'];self.assertTrue(middle.any());self.assertTrue(((m['influence'][middle]>0)&(m['influence'][middle]<1)).all())
        self.assertFalse(m['influence'][~m['coverage']].any())
    def test_non_equivalent_overlap_protected_equivalent_duplicate_allowed(self):
        p,n,uv=self.plane(.5);a=geometry_masks(np.concatenate([p,p]),np.concatenate([n,n]),np.concatenate([uv,uv]),['skin','skin'],32,self.regions(),1)
        self.assertFalse(a['ambiguous'].any());self.assertGreater(a['influence'].max(),.99)
        b=geometry_masks(np.concatenate([p,p+[0,0,1]]),np.concatenate([n,n]),np.concatenate([uv,uv]),['skin','skin'],32,self.regions(),1)
        self.assertTrue(b['ambiguous'][b['coverage']].all());self.assertFalse(b['influence'].any())
    def test_garment_wins_over_same_surface_skin(self):
        p,n,uv=self.plane(.5);m=geometry_masks(np.concatenate([p,p]),np.concatenate([n,n]),np.concatenate([uv,uv]),['skin','garment'],32,self.regions(),1)
        self.assertTrue(m['garment'][m['coverage']].all());self.assertFalse(m['influence'].any())
    def test_padding_lineage_is_bounded_deterministic_and_cannot_cross_protection(self):
        coverage=np.zeros((9,9),dtype=bool);coverage[4,4]=True;blocked=np.zeros_like(coverage);blocked[:,2]=True
        lineage,distance,destination=pad_lineage(coverage,blocked,2)
        self.assertFalse(destination[blocked|coverage].any());self.assertEqual(lineage[5,5],40);self.assertEqual(distance[6,6],2);self.assertEqual(lineage[4,1],-1)
        for a,b in zip((lineage,distance,destination),pad_lineage(coverage,blocked,2)):np.testing.assert_array_equal(a,b)
        original=np.full((9,9),100,dtype='u1');treated=original.copy();treated[4,4]=130
        padded=apply_padding(original,treated,lineage,destination,.65);self.assertEqual(padded[5,5],130);np.testing.assert_array_equal(padded[blocked|~(destination|coverage)],original[blocked|~(destination|coverage)])
        np.testing.assert_array_equal(apply_padding(original,original,lineage,destination,0),original)
    def test_unknown_uv_and_bad_padding_masks_fail(self):
        p,n,uv=self.plane();uv[0,0,0]=1.1
        with self.assertRaises(ValueError):geometry_masks(p,n,uv,['skin'],32,self.regions())
        for mask,radius in [(np.zeros((9,9),dtype='u1'),2),(np.zeros((9,9),dtype=bool),0)]:
            with self.assertRaises(ValueError):pad_lineage(mask,np.zeros((9,9),dtype=bool),radius)

if __name__=='__main__':unittest.main()
