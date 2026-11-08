import unittest
import numpy as np
from .textures import material_palette


class MaterialPaletteTests(unittest.TestCase):
    def test_constant_material_does_not_touch_any_mapped_colour(self):
        pixels=np.random.default_rng(31).random((16,16,3));before=pixels.copy()
        mapped=np.ones((16,16),bool);mapped[12:16,12:16]=False
        row={'name':'glass','uvMin':[.75,.75],'uvMax':[1,1],'linearColour':[.2,.3,.4]}
        result=material_palette(pixels,mapped,[row])
        np.testing.assert_array_equal(pixels[mapped],before[mapped])
        np.testing.assert_allclose(pixels[12:,12:],np.broadcast_to([.2,.3,.4],(4,4,3)))
        self.assertEqual(result[0]['pixelBounds'],[12,12,16,16])

    def test_invalid_later_cell_leaves_the_entire_image_unchanged(self):
        pixels=np.full((16,16,3),.5);mapped=np.zeros((16,16),bool);mapped[0,0]=True
        rows=[{'name':'glass','uvMin':[.75,.75],'uvMax':[1,1],'linearColour':[.2,.3,.4]},
              {'name':'bad','uvMin':[0,0],'uvMax':[.1,.1],'linearColour':[.2,.3,.4]}]
        with self.assertRaisesRegex(ValueError,'overlaps mapped'):
            material_palette(pixels,mapped,rows)
        np.testing.assert_array_equal(pixels,np.full((16,16,3),.5))


if __name__=='__main__':unittest.main()
