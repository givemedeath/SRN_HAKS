import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from tools.tilekit import sketch
from tools.tilekit.test_openings import model, wall


class SketchTest(unittest.TestCase):
    def test_models_from_three_sides(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'a.png'; text = model(wall('a', 'brick', 'x', 2, -2, 2, 0, 20))
            self.assertEqual(sketch.sketches({'t': text, 'u': text}, out), 2)
            with Image.open(out) as page:
                self.assertEqual(page.height, 22 * sketch.SCALE + 40); self.assertGreater(len(page.getcolors(1 << 24)), 4)
        with self.assertRaisesRegex(ValueError, 'draws nothing'):
            sketch.sketch(model(), 't')

    def test_what_lies_below_ground_is_drawn(self):
        page = sketch.sketch(model(wall('low', 'brick', 'x', 2, -2, 2, -10, -3)), 't'); self.assertEqual(page.height, 40 + max(12, 9) * sketch.SCALE)
        left = sketch.PAD * 3 + 4 * sketch.HALF * sketch.SCALE  # the side view
        self.assertTrue(any(page.getpixel((left + sketch.HALF * sketch.SCALE, y)) != (250, 250, 245) for y in range(50, 30 + 8 * sketch.SCALE)))

    def test_the_nearer_wall_is_drawn_over_the_farther(self):
        far, near = wall('far', 'b', 'y', 4, -2, 2, 0, 8), wall('near', 'b', 'y', -4, -4, 0, 0, 8).replace('0 1 2 1', '0 2 1 1')
        page = sketch.sketch(model(near, far), 't'); top = sketch.PAD + 2 * sketch.HALF * sketch.SCALE + sketch.PAD
        self.assertEqual(page.getpixel((top + int((sketch.HALF - 1.98) * sketch.SCALE), 30 + 60)) == (40, 40, 40), False)  # the far wall's edge, behind the near wall

    def test_the_pieces_that_glow(self):
        import numpy as np
        from tools.tilekit import kit
        glow = np.zeros((kit.SIZE, kit.SIZE, 3), np.uint8); side = kit.SIZE // kit.CELLS
        for look in kit.GLOWS:
            column, row = kit.cell_of(look, list(kit.LOOKS)); glow[row * side:(row + 1) * side, column * side:(column + 1) * side] = kit.GLOWS[look]
        found = {name for name, build in kit.PIECES.items() if name not in (*sketch.SKIPPED, 'camera') and sketch._glows(build()[0], glow)}
        self.assertEqual(found, {'mast', 'cross_sign', 'barrel', 'canopy'}); self.assertTrue(sketch._glows(kit.camera_whole()[0], glow))

    def test_props_are_exported_rendered_and_sheeted(self):
        with tempfile.TemporaryDirectory() as folder:
            def run(command, **_):
                self.assertEqual(command[command.index('-t') + 1], '4'); self.assertTrue(Path(command[command.index('--python') + 1]).is_file())
                for name in json.loads((Path(folder) / 'pieces.json').read_text()):
                    Image.new('RGB', (8, 6), 'red').save(Path(folder) / f'{name}-front.png')
                return SimpleNamespace(returncode=0, stderr=b'')
            import numpy as np
            maps = {'colour': np.zeros((4, 4, 3), np.uint8), 'glow': np.zeros((4, 4, 3), np.uint8), 'metal': np.zeros((4, 4)), 'roughness': np.ones((4, 4))}
            with mock.patch('tools.tilekit.kit.atlas', return_value=maps):
                (Path(folder) / 'mast-night.png').write_bytes(b'old'); (Path(folder) / 'mast-mine.png').write_bytes(b'kept')
                told = sketch.props(folder, 'masters', 'blender', run)
                self.assertEqual(told['sheets'], ['sheet-wall.jpg', 'sheet-roof.jpg']); self.assertTrue((Path(folder) / 'sheet-roof.jpg').is_file()); self.assertFalse((Path(folder) / 'mast-night.png').exists())
                self.assertTrue((Path(folder) / 'mast-mine.png').exists())

                def slow(*_, **__):
                    raise subprocess.TimeoutExpired('blender', 1)
                with self.assertRaisesRegex(ValueError, 'did not finish'):
                    sketch.props(folder, 'masters', 'blender', slow)
                with self.assertRaisesRegex(ValueError, 'Blender failed'):
                    sketch.props(folder, 'masters', 'blender', lambda *_, **__: SimpleNamespace(returncode=1, stderr=b'no'))


if __name__ == '__main__':
    unittest.main()
