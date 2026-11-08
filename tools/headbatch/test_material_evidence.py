"""Material mistakes exposed by actual decoded client looks."""
import unittest
import numpy as np
from headbatch.review.hairgaps import measure, restore_source_hair
from headbatch.review.irisrows import candidates


class MaterialEvidence(unittest.TestCase):
    def test_source_hair_gaps_exclude_bald_skin_and_uncertain_edges(self):
        parsed=np.ones((20,20),np.uint8);parsed[2:7,2:7]=17;parsed[12:17,12:17]=17
        channel=np.zeros_like(parsed);channel[12:17,12:17]=1
        region={'labels':parsed,'view':{'hit':np.ones_like(parsed,bool)}}
        metrics,missing=measure(region,channel)
        self.assertEqual(metrics['sourceHairCorePixels'],18)
        self.assertEqual(metrics['sourceHairOnSkinPixels'],9)
        self.assertFalse(missing[8:12].any())
        channel[missing]=1
        self.assertEqual(measure(region,channel)[0]['sourceHairOnSkinPixels'],0)

    def test_hair_rescue_preserves_bald_skin_lips_eyes_and_other_materials(self):
        labels=np.array([[0,0,0,0,0,8,3,0]],np.uint8)
        hair=np.array([[255,0,255,255,255,255,255,204]],np.uint8)
        eye=np.zeros_like(hair);eye[0,2]=26
        lips=np.zeros_like(hair);lips[0,3]=26
        mapped=np.ones_like(hair,bool);mapped[0,4]=False
        result,selected=restore_source_hair(labels,hair,eye,lips,mapped)
        np.testing.assert_array_equal(result,[[1,0,0,0,0,8,3,0]])
        self.assertEqual(int(selected.sum()),1)
        self.assertEqual(int(labels.sum()),11)

    def test_runtime_iris_comparison_keeps_current_row_and_finds_the_source_match(self):
        rgb=np.full((2,2,3),[80,100,110],np.uint8);layers=np.array([[8,0],[8,0]],np.uint8);shades=np.array([[20,0],[40,0]],np.uint8)
        palette=np.full((176,256,4),255,np.uint8);palette[:,:,:3]=[240,20,10]
        palette[26,:,:3]=[100,180,255];palette[23,:,:3]=[80,100,110]
        saved=[a.copy() for a in (rgb,layers,shades,palette)]
        rows,ranked=candidates(rgb,layers,shades,palette,26)
        self.assertEqual(rows[:2],[26,23]);self.assertEqual(ranked[0]['row'],23)
        for original,current in zip(saved,(rgb,layers,shades,palette)):np.testing.assert_array_equal(original,current)
        self.assertEqual(candidates(rgb,np.zeros_like(layers),shades,palette,26),([],[]))




class BrowReach(unittest.TestCase):
    def test_wider_source_bound_recovery_excludes_lids_and_remote_parser_marks(self):
        from headkit.brow_edges import fringe
        seed=np.zeros((25,25),bool);seed[12,2:23]=True
        core=np.zeros_like(seed);core[12,12]=True
        eyes=np.zeros_like(seed);eyes[12,5]=True
        excluded=np.zeros_like(seed);excluded[12,19]=True
        old=fringe(seed,core,eyes,excluded)
        new=fringe(seed,core,eyes,excluded,8)
        self.assertFalse(old[12,6]);self.assertTrue(new[12,6])
        self.assertFalse(new[12,3]);self.assertFalse(new[12,5]);self.assertFalse(new[12,19])
        self.assertFalse(new[11].any())
        for invalid in [True,0,9,2.5]:
            with self.assertRaises(ValueError):fringe(seed,core,eyes,excluded,invalid)


if __name__=='__main__':unittest.main()
