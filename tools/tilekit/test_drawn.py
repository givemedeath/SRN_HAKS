"""An atlas too small to redraw is drawn again in code, each region where the tiles' UVs take it."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.tilekit import drawn
from tools.tilekit.test_material import scan

PACKS = ('srn_t_tfb01',)  # what this reads: named so the test selector runs it when one changes


class Flood(unittest.TestCase):
    def test_the_banner_is_dark_cloth_with_its_emblem_and_the_cork_takes_its_old_colour(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup); masters = Path(folder.name)
        for name in ('Fabric026', 'WoodFloor051'):
            scan(masters / name)
        picture = drawn.flood(masters, size=128).astype(float)
        self.assertEqual(picture.shape, (128, 128, 3))
        banner, cork = picture[:35], picture[64:]
        self.assertLess(np.median(banner.mean(axis=2)), 70)  # dark cloth
        self.assertTrue(((banner[..., 2] > 150) & (banner[..., 0] < 120)).any())  # the teal emblem on it
        self.assertTrue(np.allclose(cork.reshape(-1, 3).mean(axis=0), (150, 112, 72), atol=12))  # cork, toned as the old one


if __name__ == '__main__':
    unittest.main()
