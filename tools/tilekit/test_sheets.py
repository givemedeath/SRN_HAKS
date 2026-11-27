"""Small pictures enlarged on shared sheets: how they are laid, and that each comes back as it would alone."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from . import enlarge, sheets
from .test_enlarge import doubling


class SheetTests(unittest.TestCase):
    def test_pictures_are_laid_on_sheets_without_touching(self):
        sizes = {f'p{index}': (8 + 4 * (index % 3), 8 + 4 * (index % 2)) for index in range(20)}
        pages = sheets.packed(sizes, 32)
        self.assertEqual(sorted(name for page in pages for name in page), sorted(sizes)); self.assertGreater(len(pages), 1)
        for page in pages:
            seen = np.zeros((32, 32), int)
            for name, (x, y) in page.items():
                width, height = sizes[name]; self.assertTrue(x + width <= 32 and y + height <= 32); seen[y:y + height, x:x + width] += 1
            self.assertEqual(seen.max(), 1)
        with self.assertRaisesRegex(ValueError, 'larger than a sheet'):
            sheets.packed({'big': (40, 8)}, 32)

    def test_each_picture_comes_back_doubled_and_whole(self):
        rng = np.random.default_rng(1); pictures = {name: rng.integers(0, 256, (height, width, 3), np.uint8) for name, height, width in (('a', 8, 16), ('b', 4, 4), ('c', 16, 8))}
        made = sheets.doubled(pictures, lambda page: page.repeat(2, 0).repeat(2, 1), margin=4, side=48)
        for name, one in pictures.items():
            np.testing.assert_array_equal(made[name], one.repeat(2, 0).repeat(2, 1))

    def test_a_run_leaves_what_enlarge_leaves(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'srn_t_common').mkdir(); pane = np.zeros((8, 8, 3), np.uint8); pane[:, :4] = (200, 220, 240)
            Image.fromarray(pane).save(root / 'srn_t_common' / 'pane.tga'); Image.new('RGB', (4, 8), (9, 8, 7)).save(root / 'srn_t_common' / 'wall.tga'); Image.new('RGB', (8, 8)).save(root / 'srn_t_common' / 'door.tga')
            spec = {'textures': {'pane': {'route': 'upscale', 'size': [32, 32], 'doubled': 2}, 'wall': {'route': 'upscale', 'size': [8, 16], 'doubled': 1}, 'door': {'route': 'upscale', 'size': [8, 8]}}}
            sent = []
            with mock.patch('tools.headkit.design._execute', side_effect=doubling(sent)):
                self.assertEqual(sheets.run(None, {}, None, root, spec, root / 'big', say=None), {'pane': 'enlarged', 'wall': 'enlarged'})
                self.assertEqual(sent, [(sheets.SIDE, sheets.SIDE)] * 2)  # both on one sheet, then the one that is doubled again
                self.assertEqual(enlarge.enlarge(None, {}, None, root, spec, root / 'big', say=None), {'pane': 'kept', 'wall': 'kept'})  # its records are enlarge's
                self.assertEqual(sheets.run(None, {}, None, root, spec, root / 'big', say=None), {'pane': 'kept', 'wall': 'kept'})
            self.assertEqual((enlarge.picture_of(root / 'big', 'pane').shape, tuple(enlarge.picture_of(root / 'big', 'wall')[15, 7])), ((32, 32, 3), (9, 8, 7)))
            self.assertEqual(json.loads((root / 'big' / 'pane.json').read_text())['doubled'], 2)


if __name__ == '__main__':
    unittest.main()
