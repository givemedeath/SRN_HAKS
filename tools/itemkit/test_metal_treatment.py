import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from .textures import finish_bake, metal_policy


class MetalTreatmentTests(unittest.TestCase):
    def test_the_treatment_is_a_bounded_reviewed_setting(self):
        self.assertEqual(metal_policy({'darken': .6, 'reflection': 0}), {'darken': .6, 'reflection': 0.0})
        for bad in ({'darken': .6}, {'darken': .2, 'reflection': 0}, {'darken': 1, 'reflection': 0}, {'darken': 1, 'reflection': .7},
                    {'darken': '0.6', 'reflection': 0}, {'darken': .6, 'reflection': .2, 'gloss': 1}, True):
            with self.assertRaisesRegex(ValueError, 'Metal treatment'): metal_policy(bad)

    def bake(self, folder, metal, **more):
        size = 4096; linear = np.full((size, size, 3), .5, np.float32); owners = np.full((size, size), -1, np.int32)
        owners[:2048] = 0                                         # the lower half of the atlas is mapped
        layer = np.full((size, size), np.nan, np.float32); layer[:2048, :2048] = 1; layer[:2048, 2048:] = 0
        layer[0, 0] = np.nan                                      # one missed metal texel, filled from its neighbours
        np.save(folder/'linear.npy', linear); np.save(folder/'metallic.npy', layer)
        np.savez(folder/'masks.npz', owners=owners, hiddenCaps=np.zeros((size, size), bool), visibleMisses=np.zeros((size, size), bool))
        return finish_bake(folder/'linear.npy', folder/'masks.npz', folder/'out', metal=metal,
                           metallic_path=folder/'metallic.npy' if metal else None, **more)

    def test_metal_is_darkened_and_masked_and_the_rest_is_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.bake(Path(tmp), {'darken': .5, 'reflection': .4})
            self.assertEqual(result['metalTreatment']['metallicTexelsFilled'], 1)
            self.assertAlmostEqual(result['metalTreatment']['metalFraction'], .5, places=3)
            for size in (4096, 1024):
                with Image.open(result['maps'][str(size)]['path']) as image:
                    self.assertEqual((image.mode, image.size), ('RGBA', (size, size)))
                    # The finished map is stored flipped: the mapped half is at the bottom, metal on its left.
                    metal, plain = image.getpixel((size//4, size - 2)), image.getpixel((3*size//4, size - 2))
                self.assertEqual(plain, (188, 188, 188, 255))     # linear 0.5, untouched and fully opaque
                self.assertEqual(metal, (137, 137, 137, 153))     # linear 0.25; alpha 1 - 0.4
            with Image.open(result['maps']['4096']['path']) as image: self.assertEqual(image.getpixel((0, 4095)), (137, 137, 137, 153))

    def test_darkening_alone_writes_no_alpha(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.bake(Path(tmp), {'darken': .5, 'reflection': 0}, sharpen={'radius': 1, 'amount': .5})
            with Image.open(result['maps']['2048']['path']) as image: self.assertEqual(image.mode, 'RGB')
            self.assertFalse(result['metalTreatment']['alphaChannel'])

    def test_a_treatment_without_its_map_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); self.bake(folder, None)
            with self.assertRaisesRegex(ValueError, 'go together'):
                finish_bake(folder/'linear.npy', folder/'masks.npz', folder/'again', metal={'darken': .5, 'reflection': 0})

    def test_a_reflective_texture_gets_the_txi_that_names_its_environment_map(self):
        from .native import reflection_txi
        with tempfile.TemporaryDirectory() as tmp:
            target = reflection_txi(Path(tmp)/'sr_gun_017.tga')
            self.assertEqual((target.name, target.read_bytes()), ('sr_gun_017.txi', b'envmaptexture chrome1
'))
