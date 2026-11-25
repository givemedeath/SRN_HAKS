import json
import tempfile
import unittest
from pathlib import Path

from tools.tilekit import apply, detail, effects, geometry, inventory
from tools.tilekit.test_detail import _repo

ANIMATED = """
newanim tiledefault t_a01
  length 0.03333
  transtime 0.0
  animroot t_a01
  node dummy t_a01
    parent null
  endnode
doneanim tiledefault t_a01
"""


def _with_animation(own):
    path = own / 't_a01.mdl'; text = path.read_text(encoding='cp1252')
    path.write_text(text.replace('donemodel t_a01', ANIMATED.strip() + '\ndonemodel t_a01'), encoding='cp1252')


def _spec(*placements):
    return {'tileset': 't', 'tiles': {'t_a01': list(placements)}}


class Life(unittest.TestCase):
    def test_a_drop_lives_as_long_as_its_fall(self):
        self.assertAlmostEqual(effects.life('drip', 4.9), 1.0, places=2)
        with self.assertRaisesRegex(ValueError, 'how far it falls'):
            effects.life('drip', None)


class Sheet(unittest.TestCase):
    def test_a_sparse_sheet_holds_every_frame_once_among_empty_ones(self):
        from PIL import Image
        plain = Image.new('RGBA', (4 * 8, 4 * 8))
        for index in range(16):
            plain.paste((index * 10 + 5, 0, 0, 255), ((index % 4) * 8, (index // 4) * 8, (index % 4 + 1) * 8, (index // 4 + 1) * 8))
        out = effects.sparse(plain)
        self.assertEqual(out.size, (64, 64)); self.assertEqual(out, effects.sparse(plain))
        shown = [out.getpixel((column * 8 + 4, row * 8 + 4)) for row in range(8) for column in range(8)]
        self.assertEqual(sorted(pixel[0] for pixel in shown if pixel[3]), [index * 10 + 5 for index in range(16)])
        self.assertEqual(sum(1 for pixel in shown if not pixel[3]), 48)

    def _picture(self, ring=False):
        from PIL import Image, ImageDraw
        picture = Image.new('RGB', (400, 400)); draw = ImageDraw.Draw(picture)
        for row in range(effects.GRID):
            for column in range(effects.GRID):
                x, y = column * 100 + 30 + row * 5, row * 100 + 40  # off the cell's middle: the frame is centred on it
                draw.ellipse((x, y, x + 24, y + 30), outline=(200, 220, 255), fill=None if ring else (255, 200, 120), width=3)
        return picture

    def test_every_frame_is_centred_on_its_shape(self):
        out = effects.sheet(self._picture(), frame=32)
        self.assertEqual(out.size, (32 * effects.GRID, 32 * effects.GRID))
        for row in range(effects.GRID):
            for column in range(effects.GRID):
                box = out.crop((column * 32, row * 32, column * 32 + 32, row * 32 + 32)).getchannel('A').getbbox()
                self.assertTrue(box); self.assertLessEqual(abs((box[0] + box[2]) / 2 - 16), 2); self.assertLessEqual(abs((box[1] + box[3]) / 2 - 16), 2)

    def test_a_filled_shape_has_a_body_and_an_empty_frame_is_refused(self):
        from PIL import Image
        hollow, filled = effects.sheet(self._picture(ring=True), frame=32), effects.sheet(self._picture(ring=True), frame=32, filled=True)
        self.assertLess(hollow.getpixel((16, 16))[3], 40); self.assertGreaterEqual(filled.getpixel((16, 16))[3], int(255 * 0.35) - 2)
        with self.assertRaisesRegex(ValueError, 'empty'):
            effects.sheet(Image.new('RGB', (400, 400)))


class Placed(unittest.TestCase):
    def test_effects_become_steady_emitters_and_leave_the_walkmesh_and_animations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root, z=0.0); _with_animation(own)
            (kit / 'dgt04_fx_arc.tga').write_bytes(b'spark'); (kit / 'dgt04_fx_drip.tga').write_bytes(b'drip')
            spec = _spec({'piece': 'sparks', 'at': [-4.9, 1.0, 3.2]}, {'piece': 'drip', 'at': [-4.0, -1.0, 6.0], 'fall': 6.0},
                         {'piece': 'smoke', 'at': [1.0, 1.0, 3.0]})
            told = detail.detail(root, spec, kit, root / 'out')
            self.assertEqual(told['t_a01']['effects'], 3); self.assertEqual(told['t_a01']['pieces'], 0)
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertIn('node emitter t_a01_fx00', made); self.assertIn('texture fxpa_mist', made)
            self.assertNotIn('birthratekey', made); self.assertIn('  xgrid 8', made)  # a steady rate: the sparse sheet makes it random
            self.assertEqual(made.count('newanim'), 1)  # the tile's animations are left as they were
            self.assertEqual(inventory.walk_hash(made), inventory.walk_hash((own / 't_a01.mdl').read_text(encoding='cp1252')))
            self.assertEqual((root / 'out' / 'dgt04_fx_arc.tga').read_bytes(), b'spark'); self.assertFalse((root / 'out' / 'fxpa_mist.tga').exists())
            record = json.loads((root / 'out' / apply.KIT_FILES).read_text(encoding='utf-8'))  # what apply brings to the pack: the pictures, no atlas (no kit piece)
            self.assertEqual(sorted(record['files']), ['dgt04_fx_arc.tga', 'dgt04_fx_drip.tga'])
            _, _, nodes = geometry.parse(made); self.assertEqual(sum(node.kind == 'emitter' for node in nodes), 3)
            again = detail.detail(root, spec, kit, root / 'out')  # a second run replaces, it does not add
            self.assertEqual(again, told); self.assertEqual((root / 'out' / 't_a01.mdl').read_text(encoding='cp1252'), made)

    def test_an_effect_without_its_picture_or_outside_the_cell_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root, z=0.0)
            with self.assertRaisesRegex(ValueError, 'No effect picture'):
                detail.detail(root, _spec({'piece': 'sparks', 'at': [0.0, 0.0, 3.0]}), kit, root / 'out')
            with self.assertRaisesRegex(ValueError, 'outside the cell'):
                detail.detail(root, _spec({'piece': 'smoke', 'at': [6.0, 0.0, 1.0]}), kit, root / 'out')


if __name__ == '__main__':
    unittest.main()


class Fixtures(unittest.TestCase):
    LAMP = """node trimesh lamp
  parent t_a01
  position -5.5 0.0 4.0
  orientation 0.0 0.0 0.0 0.0
  bitmap lamp_tex
  verts 3
    -0.2 -0.2 0
    0.2 -0.2 0
    0.2 0.2 0.3
  tverts 1
    0 0 0
  faces 1
    0 1 2 1 0 0 0 1
endnode
"""

    def test_a_wall_piece_running_into_the_tile_s_own_lamp_is_refused_and_one_beside_it_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root, z=0.0)
            path = own / 't_a01.mdl'; path.write_text(path.read_text(encoding='cp1252').replace('node aabb walk', self.LAMP + 'node aabb walk'), encoding='cp1252')
            with self.assertRaisesRegex(ValueError, r'runs into what the tile already has there \(lamp\)'):
                detail.detail(root, _spec({'piece': 'box', 'at': [-5.2, 0.0, 3.6], 'turn': 0}), kit, root / 'out')
            told = detail.detail(root, _spec({'piece': 'box', 'at': [-4.4, 3.0, 3.6], 'turn': 0}), kit, root / 'out')
            self.assertEqual(told['t_a01']['pieces'], 1)
