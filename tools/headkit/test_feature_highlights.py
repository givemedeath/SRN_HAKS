import unittest
from pathlib import Path
import sys
import numpy as np
from headkit.feature_highlights import repair_channel
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headbatch'))
from headbatch.head_setup import face_quality_profile


class FeatureHighlights(unittest.TestCase):
    def setUp(self):
        y, x = np.mgrid[:128, :128]
        self.points = np.stack([x/127, y/127, np.zeros_like(x)], -1)
        self.mapped = np.ones((128,128), bool)
        self.features = {key: np.zeros((128,128)) for key in ('ear','brow','skin')}
        self.features['skin'][:] = 1
        self.selected = np.ones((128,128), bool)
        self.allowed = np.arange(0,254,2)

    def fix(self, field, channel, **extra):
        out, report = repair_channel(field[self.selected],self.selected,self.features,self.points,self.mapped,
                                     self.allowed,channel,**extra)
        result = field.copy()
        result[self.selected] = out
        return result, report

    def test_hot_brow_fringe_is_lowered_without_changing_interior_or_unrelated_hair(self):
        self.features['brow'][20:30,16:48] = 1
        self.features['brow'][19,16:48] = .1
        field = np.full((128,128),60,dtype=np.uint8)
        field[19,20:44] = 240
        out, report = self.fix(field,1)
        self.assertGreater(report['changedTexels'],0)
        self.assertLess(out[19,32],100)
        np.testing.assert_array_equal(out[21:28,16:48],field[21:28,16:48])
        np.testing.assert_array_equal(out[40:],field[40:])
        self.assertTrue(np.isin(out,self.allowed).all())

    def test_restored_brow_across_uv_seam_uses_bounded_surface_donors(self):
        self.features['brow'][20:30,16:48] = 1
        field = np.full((128,128),60,dtype=np.uint8)
        # A whole restored UV island can be wider than the old two-texel
        # growth or three-texel boundary, while lying on the same real brow.
        field[80:96,80:96] = 240
        yy,xx=np.mgrid[:16,:16]
        self.points[80:96,80:96,0]=(20+xx/2)/127
        self.points[80:96,80:96,1]=(22+yy/4)/127
        self.selected[85,85]=False  # a different material stays protected
        field[110,110]=240  # distant hair is never a donor/target
        out,report=self.fix(field,1)
        self.assertLess(out[88,88],100)
        self.assertEqual(out[85,85],240)
        self.assertEqual(out[110,110],240)
        self.assertGreater(report['changedTexels'],200)
        np.testing.assert_array_equal(out[21:28,16:48],field[21:28,16:48])

    def test_ear_shoulder_preserves_form_protected_ink_and_other_skin(self):
        self.features['ear'][16:48,16:48] = 1
        self.features['skin'][16:48,16:48] = 0
        field = np.full((128,128),100,dtype=np.uint8)
        field[16:48,16:48] = np.arange(32,dtype=np.uint8)[None,:]*4+120
        protected = np.zeros((128,128),bool)
        protected[20,45] = True
        out, report = self.fix(field,0,preserve=protected)
        self.assertGreater(report['changedTexels'],0)
        self.assertEqual(out[20,45],field[20,45])
        self.assertLess(out[21,45],140)
        self.assertTrue(np.all(np.diff(out[21,16:48].astype(int))>=0))
        np.testing.assert_array_equal(out[:10],field[:10])

    def test_light_hair_and_unexceptional_ear_highlights_are_preserved(self):
        for channel,name in ((0,'ear'),(1,'brow')):
            self.features[name][16:48,16:48] = 1
            field = np.full((128,128),230,dtype=np.uint8)
            out, report = self.fix(field,channel)
            np.testing.assert_array_equal(out,field)
            self.assertEqual(report['changedTexels'],0)

    def test_protected_bright_ear_ink_does_not_trigger_a_skin_correction(self):
        self.features['ear'][16:48,16:48] = 1
        self.features['skin'][16:48,16:48] = 0
        field = np.full((128,128),100,dtype=np.uint8)
        field[16:48,16:48] = 120
        field[16:20,16:48] = 240
        protected = np.zeros((128,128),bool)
        protected[16:20,16:48] = True
        out, report = self.fix(field,0,preserve=protected)
        np.testing.assert_array_equal(out,field)
        self.assertEqual(report['changedTexels'],0)

    def test_repaired_chart_samples_update_only_unprotected_same_channel_gutters(self):
        self.mapped[:,:6] = False
        self.selected[:,4] = False
        self.features['ear'][6:50,6:50] = 1
        self.features['skin'][6:50,6:50] = 0
        field = np.full((128,128),100,dtype=np.uint8)
        field[6:50,6:12] = 240
        field[:,:6] = 240
        protected = np.zeros_like(self.mapped)
        protected[20,3] = True
        out, report = self.fix(field,0,preserve=protected)
        self.assertGreater(report['gutterTexels'],0)
        self.assertLess(out[20,5],140)
        self.assertEqual(out[20,4],240)
        self.assertEqual(out[20,3],240)

    def test_uv_neighbours_on_distant_surfaces_are_not_brow_donors(self):
        self.features['brow'][20:30,16:48] = 1
        field = np.full((128,128),60,dtype=np.uint8)
        field[20,20:44] = 240
        self.points[20,:,2] = 10
        out, report = self.fix(field,1)
        np.testing.assert_array_equal(out,field)
        self.assertGreater(report['unsupportedTexels'],0)

    def test_ear_mask_growth_cannot_cross_to_a_distant_uv_neighbour(self):
        self.features['ear'][16:48,16:48] = 1
        self.features['skin'][16:48,16:48] = 0
        field = np.full((128,128),100,dtype=np.uint8)
        field[16:48,16:48] = 240
        # Atlas neighbours on a separate surface, outside the actual ear mask.
        field[14:16,16:48] = 240
        self.points[14:16,16:48,2] = 10
        out, report = self.fix(field,0)
        self.assertGreater(report['changedTexels'],0)
        np.testing.assert_array_equal(out[14:16,16:48],field[14:16,16:48])

    def test_mask_growth_needs_a_same_channel_feature_anchor(self):
        self.features['ear'][16:48,16:48] = 1
        self.features['skin'][16:48,16:48] = 0
        self.selected[16:48,16:48] = False
        field = np.full((128,128),100,dtype=np.uint8)
        field[14:16,16:48] = 240
        out, report = self.fix(field,0)
        np.testing.assert_array_equal(out,field)
        self.assertEqual(report['changedTexels'],0)

    def test_invalid_masks_fail_and_face_profile_enables_repair(self):
        self.assertTrue(face_quality_profile()['palette']['repairFeatureHighlights'])
        self.features['brow'][0,0] = np.nan
        with self.assertRaisesRegex(ValueError,'highlight masks'):
            self.fix(np.full((128,128),60,dtype=np.uint8),1)


if __name__ == '__main__':
    unittest.main()
