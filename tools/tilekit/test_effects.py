import tempfile
import unittest
from pathlib import Path

from tools.tilekit import detail, effects, geometry, inventory
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


class Bursts(unittest.TestCase):
    def test_bursts_are_irregular_and_differ_by_seed(self):
        one, other = effects.bursts('t:0'), effects.bursts('t:1')
        self.assertEqual(one, effects.bursts('t:0')); self.assertNotEqual(one, other)
        starts = [time for (time, rate), (_, before) in zip(one[1:], one) if rate > 0 and before == 0]
        gaps = [later - earlier for earlier, later in zip(starts, starts[1:])]
        self.assertGreater(len(starts), 6); self.assertGreater(max(gaps) - min(gaps), 1.0)  # not a steady beat

    def test_a_loop_starts_and_ends_quiet_and_keys_run_forward(self):
        keys = effects.bursts('t:3')
        self.assertEqual(keys[0], (0.0, 0.0)); self.assertEqual(keys[-1], (effects.LOOP, 0.0))
        self.assertTrue(all(earlier[0] <= later[0] for earlier, later in zip(keys, keys[1:])))

    def test_a_drop_lives_as_long_as_its_fall(self):
        self.assertAlmostEqual(effects.life('drip', 4.9), 1.0, places=2)
        with self.assertRaisesRegex(ValueError, 'how far it falls'):
            effects.life('drip', None)


class Sheet(unittest.TestCase):
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
    def test_effects_become_emitters_keyed_in_the_default_animation_and_leave_the_walkmesh(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root, z=0.0); _with_animation(own)
            (kit / 'dgt04_fx_spark.tga').write_bytes(b'spark'); (kit / 'dgt04_fx_drip.tga').write_bytes(b'drip')
            spec = _spec({'piece': 'sparks', 'at': [-4.9, 1.0, 3.2]}, {'piece': 'drip', 'at': [-4.0, -1.0, 6.0], 'fall': 6.0},
                         {'piece': 'smoke', 'at': [1.0, 1.0, 3.0]})
            told = detail.detail(root, spec, kit, root / 'out')
            self.assertEqual(told['t_a01']['effects'], 3); self.assertEqual(told['t_a01']['pieces'], 0)
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertIn('node emitter t_a01_fx00', made); self.assertIn('texture fxpa_mist', made)
            self.assertIn(f'  length {effects.LOOP:.5f}', made); self.assertEqual(made.count('birthratekey'), 1)  # only the sparks are keyed
            self.assertEqual(inventory.walk_hash(made), inventory.walk_hash((own / 't_a01.mdl').read_text(encoding='cp1252')))
            self.assertEqual((root / 'out' / 'dgt04_fx_spark.tga').read_bytes(), b'spark'); self.assertFalse((root / 'out' / 'fxpa_mist.tga').exists())
            _, _, nodes = geometry.parse(made); self.assertEqual(sum(node.kind == 'emitter' for node in nodes), 3)
            again = detail.detail(root, spec, kit, root / 'out')  # a second run replaces, it does not add
            self.assertEqual(again, told); self.assertEqual((root / 'out' / 't_a01.mdl').read_text(encoding='cp1252'), made)

    def test_sparks_are_keyed_in_every_animation_the_tile_plays(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); own, kit = _repo(root, z=0.0); _with_animation(own); (kit / 'dgt04_fx_spark.tga').write_bytes(b'spark')
            path = own / 't_a01.mdl'; text = path.read_text(encoding='cp1252')
            path.write_text(text.replace('donemodel t_a01', ANIMATED.strip().replace('tiledefault', 'animloop01') + '\ndonemodel t_a01'), encoding='cp1252')
            detail.detail(root, _spec({'piece': 'sparks', 'at': [0.0, 0.0, 3.0]}), kit, root / 'out')
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertEqual(made.count('birthratekey'), 2); self.assertEqual(made.count(f'  length {effects.LOOP:.5f}'), 2)
            for name in ('tiledefault', 'animloop01'):
                block = made[made.index(f'newanim {name}'):made.index(f'doneanim {name}')]
                self.assertIn('node emitter t_a01_fx00', block)

    def test_a_model_without_a_default_animation_gets_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); _, kit = _repo(root, z=0.0); (kit / 'dgt04_fx_spark.tga').write_bytes(b'spark')
            detail.detail(root, _spec({'piece': 'sparks', 'at': [0.0, 0.0, 3.0]}), kit, root / 'out')
            made = (root / 'out' / 't_a01.mdl').read_text(encoding='cp1252')
            self.assertIn('newanim tiledefault t_a01', made); self.assertLess(made.index('doneanim tiledefault'), made.index('donemodel'))

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
