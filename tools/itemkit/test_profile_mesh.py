import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from tools.itemkit import profile_mesh as pm
from tools.itemkit.geometry import topology


class SurfaceNetTests(unittest.TestCase):
    def test_a_sphere_is_one_closed_outward_solid_on_its_surface(self):
        h = .05; g = np.arange(-1.3, 1.3 + h / 2, h); X, Y, Z = np.meshgrid(g, g, g, indexing='ij')
        v, f = pm.surface_nets(np.sqrt(X ** 2 + Y ** 2 + Z ** 2) - 1, (g[0], g[0], g[0]), h)
        report = topology(v, f); self.assertTrue(report['closedWound']); self.assertEqual(report['totalGenus'], 0)
        self.assertLess(np.abs(np.linalg.norm(v, axis=1) - 1).max(), .03)
        self.assertAlmostEqual(report['signedVolume'], 4 / 3 * np.pi, delta=.1)


class ProfileMeshTests(unittest.TestCase):
    def test_a_drawn_spear_becomes_a_round_shaft_and_a_flat_head(self):
        image = Image.new('RGB', (600, 200), 'white'); draw = ImageDraw.Draw(image)
        draw.rectangle([20, 94, 470, 106], fill=(30, 30, 30))                       # shaft, 13 px thick
        draw.polygon([(470, 80), (580, 100), (470, 120)], fill=(150, 150, 160))     # head, 41 px at its base
        draw.rectangle([455, 60, 461, 140], fill=(60, 60, 60))                       # a cross bar standing out: flat hooks
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'side.png'; image.save(source)
            result = pm.build(source, Path(tmp)/'out', 1.2, voxel=.003)
            self.assertTrue(result['topology']['closedWound']); self.assertTrue(result['hooks'])
            length, height, depth = result['extents']
            self.assertAlmostEqual(length, 1.2, delta=.02)
            # The deepest part is the round collar at the head's base width: the head and the hooks stay flat.
            collar = 2 * result['layout']['headBaseHalfWidth'] * result['metresPerPixel']
            self.assertAlmostEqual(depth, collar, delta=.1 * collar); self.assertGreater(height, 1.8 * depth)
            self.assertGreater(result['layout']['headStart'], 440)
            self.assertTrue((Path(tmp)/'out/textured.glb').exists())


if __name__ == '__main__':
    unittest.main()
