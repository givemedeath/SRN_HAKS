"""Unused service atlas fill must not change skin/hair palette calibration."""
import unittest
import numpy as np
from propose_material_masks import choose_palette_row


class PaletteSamplingTests(unittest.TestCase):
    def test_unoccupied_pixels_cannot_bias_selected_source_palette_row(self):
        palette=np.array([[[200,160,120]]*256,[[60,40,20]]*256],float)
        values=np.zeros((20,20,3));mask=np.zeros((20,20),dtype=np.uint8);coverage=np.zeros((20,20),dtype=bool)
        coverage[:2,:2]=True;values[:2,:2]=[200,160,120]
        self.assertEqual(choose_palette_row(values,mask,coverage,palette,0),0)
        values[~coverage]=[60,40,20]
        self.assertEqual(choose_palette_row(values,mask,coverage,palette,0),0)
        with self.assertRaisesRegex(ValueError,'covered'):choose_palette_row(values,mask,np.zeros_like(coverage),palette,0)


if __name__=='__main__':unittest.main()
