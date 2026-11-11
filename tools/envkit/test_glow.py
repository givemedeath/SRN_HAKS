"""The lit parts of a model are found by where they are on it, glow with their own colour, and spread onto a card."""
import unittest
from pathlib import Path

import numpy as np

from . import convert, glow

# A wall facing front (+Y) in game space: 4 wide, 2 tall, its texture laid straight across it, +x on the picture's left.
POINTS = np.array([[2.0, 1.0, 0.0], [-2.0, 1.0, 0.0], [-2.0, 1.0, 2.0], [2.0, 1.0, 2.0]])
UVS = np.array([[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]])
FACES = np.array([[0, 1, 2], [0, 2, 3]])


class GlowTests(unittest.TestCase):
    def test_every_texel_knows_its_place_on_the_model(self):
        where, covered = glow.position_map(POINTS, UVS, FACES, 32)
        self.assertTrue(covered.all())
        np.testing.assert_allclose(where[..., 1], 1.0)
        np.testing.assert_allclose(where[0, 0], [2 - 2 / 32, 1, 2 - 1 / 32], atol=1e-9)  # the top left texel's centre
        np.testing.assert_allclose(where[31, 31], [-2 + 2 / 32, 1, 1 / 32], atol=1e-9)
        # An island's gutter shows the island's own edge, not a place off the model.
        half = UVS * [0.5, 1.0]; where, covered = glow.position_map(POINTS, half, FACES, 32)
        self.assertTrue(covered[:, 16].all()); self.assertFalse(covered[:, 20].any())
        np.testing.assert_allclose(where[5, 16, 0], -2.0, atol=1e-9)

    def test_only_the_named_parts_glow_and_with_their_own_colour(self):
        where, covered = glow.position_map(POINTS, UVS, FACES, 32)
        base = np.full((32, 32, 3), 0.5); base[:, :16] = [0.9, 0.1, 0.1]  # the +x half is red, the rest grey
        sign = {'box': [[-2.5, 0.5, 1.0], [2.5, 1.5, 2.5]]}  # the upper half of the wall
        lit = glow.glow(base, where, covered, [sign])
        np.testing.assert_allclose(lit[:16], base[:16]); self.assertEqual(float(lit[16:].max()), 0.0)
        vivid = glow.glow(base, where, covered, [{**sign, 'saturation': 0.4, 'gain': 2.0}])
        np.testing.assert_allclose(vivid[:16, :16] - [1.0, 0.2, 0.2], 0, atol=1e-9); self.assertEqual(float(vivid[:, 16:].max()), 0.0)  # grey fails the test
        both = glow.glow(base, where, covered, [{**sign, 'gain': 0.3}, {**sign, 'saturation': 0.4}])  # the brighter rule wins
        np.testing.assert_allclose(both[0, 0], [0.9, 0.1, 0.1]); np.testing.assert_allclose(both[0, 31], [0.15, 0.15, 0.15])
        with self.assertRaisesRegex(ValueError, 'low corner'):
            glow.glow(base, where, covered, [{'box': [[1, 0, 0], [0, 1, 1]]}])

    def test_the_halo_is_a_card_in_front_that_fades_away_from_the_glow_one_for_each_depth(self):
        where, covered = glow.position_map(POINTS, UVS, FACES, 64)
        base = np.full((64, 64, 3), 0.9)
        lit = glow.glow(base, where, covered, [{'box': [[-1.0, 0.5, 0.5], [1.0, 1.5, 1.5]]}])
        image, cards = glow.halo(lit, where, covered, reach=0.25, strength=0.5)
        self.assertEqual(len(cards), 1); corners = cards[0]
        places = np.array([place for place, _ in corners])
        np.testing.assert_allclose(places[:, 1], 1.04)  # just in front of the wall
        self.assertLess(places[:, 0].min(), -1.4); self.assertGreater(places[:, 0].max(), 1.4)  # past the glow on each side
        self.assertEqual([corner for _, corner in corners], [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)])
        self.assertGreater(places[0][0], places[1][0])  # the picture's left is the model's +x, as seen from the front
        picture = np.asarray(image, float); tall, wide = picture.shape[:2]
        edge, beside = picture[tall // 2, 0].max(), picture[tall // 2, wide // 5].max()
        self.assertLess(edge, 3); self.assertGreater(beside, edge + 10)  # dark at the card's rim, light beside the glow
        self.assertLessEqual(picture.max(), 0.5 * 0.9 * 255 + 1)
        held = np.asarray(glow.halo(lit, where, covered, reach=0.25, strength=0.5, core=1.0)[0], float)
        self.assertLess(held[tall // 2, wide // 2].max(), picture[tall // 2, wide // 2].max())  # held back over the lit part itself
        self.assertIsNone(glow.halo(np.zeros_like(lit), where, covered))
        # A sign standing a metre out from the wall gets its own card at its own depth; the two share one picture.
        deep = where.copy(); deep[:, 32:, 1] += 1.0
        image, cards = glow.halo(np.full_like(lit, 0.8), deep, covered, reach=0.25, strength=0.5)
        self.assertEqual([round(card[0][0][1], 2) for card in cards], [1.04, 2.04])
        (_, (_, lower)), _, (_, (_, upper)), _ = cards[0]; self.assertEqual((upper, lower), (0.0, 0.5))
        self.assertEqual(cards[1][0][1][1], 1.0); self.assertEqual(image.size[1], 2 * round((2 + 4 * 0.25) * 24))

    def test_the_card_is_a_node_of_the_model_that_takes_no_light(self):
        normals = np.tile([0, 1.0, 0], (4, 1))
        cards = glow.halo(np.full((16, 16, 3), 0.8), *glow.position_map(POINTS, UVS, FACES, 16))[1]
        text = convert.model_text('ek_test', POINTS, normals, UVS, FACES, cards)
        node = text[text.index('node trimesh ek_test_halo0'):]
        for line in ('  bitmap ek_test_h', '  ambient 0 0 0', '  diffuse 0 0 0', '  shadow 0', '  verts 4', '  faces 2'):
            self.assertIn(line, node)
        self.assertNotIn('selfillumcolor', text)  # the compiled model's read-back check knows no such controller
        self.assertNotIn('_halo', convert.model_text('ek_test', POINTS, normals, UVS, FACES))

    def test_a_script_puts_the_lights_out_by_swapping_in_materials_and_back_by_clearing_them(self):
        out = convert.lights_script('ek_test', 'OBJECT_SELF', on=False)
        self.assertEqual(out, 'ReplaceObjectTexture(OBJECT_SELF,"ek_test","ek_test_o");ReplaceObjectTexture(OBJECT_SELF,"ek_test_h","ek_off");')
        self.assertEqual(convert.lights_script('ek_test', 'OBJECT_SELF', on=True),
                         'ReplaceObjectTexture(OBJECT_SELF,"ek_test");ReplaceObjectTexture(OBJECT_SELF,"ek_test_h");')
        self.assertNotIn('_h', convert.lights_script('ek_test', 'OBJECT_SELF', on=False, halo=False))
        self.assertNotIn('_i', convert.material_text('ek_test'))  # what `ek_test_o` is written from: the material without its glow

    def test_the_shipped_game_set_loads_and_a_bad_one_is_refused(self):
        folder = Path(__file__).parent / 'sets'
        models = convert.load_models(folder / 'stuffer-shack-game.json')
        self.assertIn('halo', models['ek_ss_shack']); self.assertEqual(models['ek_ss_board']['signTilt'], 15.0)
        import json, tempfile
        with tempfile.TemporaryDirectory() as scratch:
            def refused(model, message):
                path = Path(scratch) / 'set.json'; path.write_text(json.dumps({'models': {'ek_x': model}}), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, message):
                    convert.load_models(path)
            refused({'source': 'C:/models/x', 'height': 1.0}, 'under the output root')
            refused({'source': '../x', 'height': 1.0}, 'under the output root')
            refused({'source': 'meshy/x', 'height': 0}, 'out of range')
            refused({'source': 'meshy/x', 'height': 1.0, 'halo': {'reach': 0.2}}, 'needs lit parts')
            refused({'source': 'meshy/x', 'height': 1.0, 'lit': [{'box': [[0, 0], [1, 1]]}]}, 'two corners')


if __name__ == '__main__':
    unittest.main()
