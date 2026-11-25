"""Screens drawn in code, and what is laid into the picture of a device."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from . import material, pictures, screens

ROOT = Path(__file__).resolve().parents[2]


class ScreenTests(unittest.TestCase):
    def test_every_kind_fills_its_picture_and_is_the_same_each_time(self):
        for kind in screens.KINDS:
            one = screens.draw(kind, 48, 36, 3); self.assertEqual(one.shape, (36, 48, 3)); np.testing.assert_array_equal(one, screens.draw(kind, 48, 36, 3)); self.assertGreater(one.std(), 5, kind)
        with self.assertRaisesRegex(ValueError, 'A screen is one of'):
            screens.draw('windows', 8, 8)

    def test_only_the_boxes_change(self):
        picture = np.full((64, 64, 3), 100, np.uint8); made = screens.laid(picture, [{'box': [0.25, 0.25, 0.75, 0.5], 'draw': 'bars', 'turn': 1}, {'box': [0, 0.75, 0.5, 1], 'sign': {'text': 'A', 'colour': [0, 0, 0], 'on': [255, 255, 255]}, 'dim': 0.5}])
        self.assertTrue((made[16:32, 16:48] != 100).any()); self.assertEqual(int(made[48:64, :32].max()), 128)
        untouched = np.ones((64, 64), bool); untouched[16:32, 16:48] = untouched[48:64, :32] = False; self.assertTrue((made[untouched] == 100).all())
        for wrong in ({'box': [0, 0, 2, 1], 'draw': 'bars'}, {'box': [0, 0, 1, 1]}, {'box': [0, 0, 1, 1], 'draw': 'bars', 'mend': True}):
            with self.assertRaises(ValueError):
                screens.laid(picture, [wrong])

    def test_a_logo_is_mended_from_round_it(self):
        picture = np.zeros((40, 40, 3), np.uint8); picture[:] = (np.arange(40) * 3)[None, :, None]; marked = picture.copy(); marked[15:25, 15:25] = (255, 0, 0)
        made = screens.laid(marked, [{'box': [0.35, 0.35, 0.65, 0.65], 'mend': True}]).astype(int)
        self.assertLess(np.abs(made - picture).max(), 25); self.assertLess(np.ptp(made, axis=2).max(), 2)  # no red is left

    def test_a_build_leaves_what_a_material_takes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'srn_placeable').mkdir(); Image.new('RGB', (16, 16), (90, 90, 90)).save(root / 'srn_placeable' / 'tv-1.tga')
            spec = {'packs': ['srn_placeable'], 'textures': {'tv-1': {'route': 'upscale', 'size': [64, 64], 'plain': True, 'redrawn': True, 'screen': [{'box': [0.25, 0.25, 0.75, 0.75], 'draw': 'wave'}]}}}
            self.assertEqual(screens.build(spec, root, root / 'made'), {'tv-1': 1})
            from .test_material import fake_compress
            told = material.build(spec, root, root, root / 'out', 'crunch', compress=fake_compress, redrawn=root / 'made'); self.assertEqual(told['tv-1']['files'], ['tv-1.dds'])  # its name keeps its hyphen
            Image.new('RGB', (16, 16)).save(root / 'srn_placeable' / 'tv-1.tga')
            with self.assertRaisesRegex(ValueError, 'made from another picture'):
                material.build(spec, root, root, root / 'out', 'crunch', compress=fake_compress, redrawn=root / 'made')

    def test_a_redrawn_picture_gets_its_colours_and_its_edges_back(self):
        rng = np.random.default_rng(2); old = np.zeros((64, 64, 3), np.uint8); old[:32] = (150, 60, 40); old[32:] = (60, 60, 60); new = np.uint8(np.full((128, 128, 3), (60, 90, 150)) + rng.integers(-20, 20, (128, 128, 1)))
        made = pictures.recoloured(new, old).astype(int); self.assertLess(np.abs(made[40:56].mean((0, 1)) - (150, 60, 40)).max(), 12); self.assertGreater(made[40:56].std(), 5)
        slope = np.repeat(np.linspace(40, 200, 128)[None, :, None], 128, 0).repeat(3, 2).astype(np.uint8); joined = pictures.joined(slope).astype(int)
        self.assertLess(np.abs(joined[:, 0] - joined[:, -1]).max(), 6); np.testing.assert_array_equal(joined[64, 40:88], slope[64, 40:88])

    def test_the_lists_of_the_placeables_do_not_overlap(self):
        lists = {name: json.loads((ROOT / 'docs' / 'placeables' / f'{name}.json').read_text(encoding='utf-8')) for name in ('materials', 'enlarged', 'screens')}
        seen = [texture for one in lists.values() for texture in one['textures']]; self.assertEqual(len(seen), len(set(seen)))
        for name, how in lists['screens']['textures'].items():
            screens.laid(np.zeros((64, 64, 3), np.uint8), how['screen'], name)


if __name__ == '__main__':
    unittest.main()
