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
        with self.assertRaisesRegex(ValueError, 'lights nothing.*dim lamp'):  # nor does a part none of whose texels pass its own tests
            glow.glow(base, where, covered, [{**sign, 'part': 'dim lamp', 'value': 0.99, 'saturation': 0.99}])
        with self.assertRaisesRegex(ValueError, 'holds none of the model.*high sign'):  # a box off the model lights nothing, and says so
            glow.glow(base, where, covered, [sign, {'part': 'high sign', 'box': [[-2.5, 0.5, 5.0], [2.5, 1.5, 6.0]]}])

    def test_the_halo_is_a_card_in_front_that_fades_away_from_the_glow_one_for_each_depth(self):
        where, covered = glow.position_map(POINTS, UVS, FACES, 64)
        base = np.full((64, 64, 3), 0.9)
        lit = glow.glow(base, where, covered, [{'box': [[-1.0, 0.5, 0.5], [1.0, 1.5, 1.5]]}])
        image, cards, light = made = glow.halo(lit, where, covered, reach=0.25, strength=0.5)
        self.assertEqual(len(cards), 1); corners = cards[0]; self.assertIs(made.cards, cards); self.assertIs(made.light, light)  # read by name elsewhere
        # The card's light is the lit square metre, in the picture's own rows and columns: none of it in the rim the glow spreads into.
        self.assertEqual(light[0].shape, image.size[::-1]); self.assertAlmostEqual(float(light[0].sum()), 2.0, delta=0.3)
        self.assertEqual(float(light[0][:10].sum() + light[0][-10:].sum() + light[0][:, :10].sum() + light[0][:, -10:].sum()), 0.0)
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
        image, cards, light = glow.halo(np.full_like(lit, 0.8), deep, covered, reach=0.25, strength=0.5)
        self.assertEqual(len(light), 2)  # one to each card
        self.assertEqual([round(card[0][0][1], 2) for card in cards], [1.04, 2.04])
        (_, (_, lower)), _, (_, (_, upper)), _ = cards[0]; self.assertEqual((upper, lower), (0.0, 0.5))
        self.assertEqual(cards[1][0][1][1], 1.0); self.assertEqual(image.size[1], 2 * round((2 + 4 * 0.25) * 24))

    def test_light_on_a_side_wall_spreads_from_that_wall(self):
        where, covered, toward = glow.position_map(POINTS, UVS, FACES, 32, facing=True)
        np.testing.assert_allclose(toward[covered], np.tile([0, 1.0, 0], (int(covered.sum()), 1)), atol=1e-9)  # the test wall faces front
        # The same wall turned to face +X: x and y change places, and the surface says so.
        side = np.stack([where[..., 1] + 2.0, -where[..., 0], where[..., 2]], -1); east = np.zeros_like(toward); east[..., 0] = 1.0
        lit = np.full((32, 32, 3), 0.8)
        image, cards, _ = glow.halo(lit, side, covered, toward=east, reach=0.25, strength=0.5)
        self.assertEqual(len(cards), 1); places = np.array([place for place, _ in cards[0]])
        np.testing.assert_allclose(places[:, 0], 3.04)  # just out from the wall at x = 3
        np.testing.assert_allclose(glow.card_normal(cards[0]), [1, 0, 0], atol=1e-9)  # and facing the way the wall does
        self.assertLess(places[0][1], places[1][1])  # seen from the east, the picture's left is the south
        self.assertLess(places[:, 1].min(), -2.4); self.assertGreater(places[:, 1].max(), 2.4)
        front = glow.halo(lit, where, covered, toward=toward, reach=0.25, strength=0.5)[1]  # facing front it is the card it always was
        self.assertEqual(front, glow.halo(lit, where, covered, reach=0.25, strength=0.5)[1])
        up = np.zeros_like(toward); up[..., 2] = 1.0
        self.assertIsNone(glow.halo(lit, where, covered, toward=up, reach=0.25, strength=0.5))  # a skylight gets no upright card
        speck = np.zeros_like(lit); speck[10, 10] = 0.8
        self.assertIsNone(glow.halo(speck, where, covered, toward=toward, reach=0.25, strength=0.5))  # nor does a patch too small to matter
        text = convert.model_text('ek_test', POINTS, np.tile([0, 1.0, 0], (4, 1)), UVS, FACES, cards)
        self.assertIn('  normals 4\n    1 0 0\n', text[text.index('node trimesh ek_test_halo0'):])

    def test_light_the_model_hides_gets_no_card_and_patches_far_apart_get_one_each(self):
        # A wall 20 metres long facing front: columns run from x = 10 down to -10, rows from z = 2 down to 0.
        across, height = np.meshgrid(np.linspace(10, -10, 640), np.linspace(2, 0, 64))
        where = np.stack([across, np.ones_like(across), height], -1); covered = np.ones(across.shape, bool)
        toward = np.zeros_like(where); toward[..., 1] = 1.0
        ends = np.zeros((64, 640, 3)); ends[:, :60] = 0.8; ends[:, -60:] = 0.8  # lit for two metres at each end only
        cards = glow.halo(ends, where, covered, toward=toward, reach=0.25, strength=0.5)[1]
        self.assertEqual(len(cards), 2)  # not one card stretched across the dark middle
        self.assertTrue(all(abs(card[0][0][0] - card[1][0][0]) < 4 for card in cards))
        # The same light with another wall of the model standing two metres in front of it: seen by nobody, so no card.
        both = np.concatenate([where, where + [0, 2.0, 0]], 1); lit = np.concatenate([ends, np.zeros_like(ends)], 1)
        facing = np.concatenate([toward, toward], 1); all_covered = np.ones(both.shape[:2], bool)
        self.assertIsNone(glow.halo(lit, both, all_covered, toward=facing, reach=0.25, strength=0.5))
        near = np.concatenate([where, where + [0, 0.2, 0]], 1)  # a frame standing 20 cm proud of a window hides nothing
        self.assertEqual(len(glow.halo(lit, near, all_covered, toward=facing, reach=0.25, strength=0.5)[1]), 2)

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
        # For a tile or static scenery, per player: the glow map and the halo are overridden by name with dark textures.
        self.assertEqual(convert.blackout_script('ek_test', 'oPC', on=False), 'SetTextureOverride("ek_test_i","ek_test_o",oPC);SetTextureOverride("ek_test_h","ek_off",oPC);')
        self.assertEqual(convert.blackout_script('ek_test', 'OBJECT_INVALID', on=True, halo=False), 'SetTextureOverride("ek_test_i","",OBJECT_INVALID);')
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
            refused({'source': 'meshy/x', 'height': 1.0, 'lift': -1}, 'lifted by 0 to 20')
            refused({'source': 'meshy/x', 'height': 1.0, 'turn': 270}, 'turned by -180 to 180')
            refused({'source': 'meshy/x', 'height': 1.0, 'tone': 0}, 'tone is 0.2 to 2')
            refused({'source': 'meshy/x', 'height': 1.0, 'paint': [{'box': [[0, 0, 0], [1, 1, 1]], 'colour': [0, 0, 300]}]}, 'three 0-255 values')
            refused({'source': 'meshy/x', 'height': 1.0, 'mesh': [{'box': [[0, 0, 0], [1, 1, 1]], 'pitch': 0.05, 'wire': 0.05}]}, 'thinner wire')
            refused({'source': 'meshy/x', 'height': 1.0, 'smooth': [{'box': [[0, 0, 0], [1, 1, 1]], 'radius': 5}]}, 'radius of 0.01 to 1')
            sheet = {'from': [0, 0], 'to': [2, 0], 'z': [1, 2], 'pitch': 0.09, 'wire': 0.016}
            refused({'source': 'meshy/x', 'height': 1.0, 'fence': [{**sheet, 'z': [2, 1]}]}, 'between two heights')
            refused({'source': 'meshy/x', 'height': 1.0, 'fence': [{**sheet, 'to': [0, 0]}]}, 'from one point to another')
            refused({'source': 'meshy/x', 'height': 1.0, 'fence': [sheet, {**sheet, 'wire': 0.02}]}, 'share one wire mesh')
            # Boxes are on the model as lifted: the Ares wall sign's were left where it stood before its lift, and it shipped dark.
            refused({'source': 'meshy/x', 'height': 1.6, 'lift': 2.4, 'lit': [{'box': [[-1, 0, 0.55], [1, 1, 1.42]]}]}, 'wholly above or below')
            refused({'source': 'meshy/x', 'height': 1.0, 'fence': [{**sheet, 'z': [1.5, 2]}]}, 'wholly above or below')
            tiles = {'ground': 'pavement', 'group': 'Long', 'label': 'Long', 'sets': {'dgt04': 'Concrete'}}
            # A building is scaled to its door before its tiles are counted: a door says how tall its leaf came out.
            refused({'source': 'meshy/x', 'height': 9.5, 'tiles': {**tiles, 'door': {'at': [0, 1, 0.2], 'type': 58}}}, 'states its leaf')
            refused({'source': 'meshy/x', 'height': 9.5, 'tiles': {**tiles, 'door': {'at': [0, 1, 0.2], 'type': 58, 'leaf': 1.6}}}, 'scale the building to its door')
            # Every building's hook is the door with no model of its own: a visible door type, or none stated, is refused.
            refused({'source': 'meshy/x', 'height': 9.5, 'tiles': {**tiles, 'door': {'at': [0, 1, 0.2], 'type': 117, 'leaf': 2.1}}}, 'invisible transition door')
            refused({'source': 'meshy/x', 'height': 9.5, 'tiles': {**tiles, 'door': {'at': [0, 1, 0.2], 'leaf': 2.1}}}, 'invisible transition door')
            # Every box, fence, door and fade height is a measurement of the model at one height: a model that states any
            # says the height it had then, and one made taller or lower since has them measured again.
            cube = [[0, 0, 0], [1, 1, 1]]; door = {'at': [0, 1, 0.2], 'type': 58, 'leaf': 2.1}
            for stated in ({'lit': [{'box': cube}]}, {'paint': [{'box': cube, 'colour': [1, 2, 3]}]}, {'smooth': [{'box': cube, 'radius': 0.1}]},
                           {'mesh': [{'box': cube, 'pitch': 0.09, 'wire': 0.016}]}, {'fence': [sheet]}, {'tiles': {**tiles, 'door': door}}, {'tiles': {**tiles, 'fade': 3.0}}):
                refused({'source': 'meshy/x', 'height': 9.5, **stated}, 'says the height it had when they were measured')
                refused({'source': 'meshy/x', 'height': 9.5, 'measuredAt': 12.35, **stated}, 'measured with the model 12.35 metres tall and it is now 9.5')
                path = Path(scratch) / 'measured.json'; path.write_text(json.dumps({'models': {'ek_x': {'source': 'meshy/x', 'height': 9.5, 'measuredAt': 9.5, **stated}}}), encoding='utf-8')
                self.assertEqual(convert.load_models(path)['ek_x']['measuredAt'], 9.5)
            refused({'source': 'meshy/x', 'height': 9.5, 'tiles': {**tiles, 'door': {**door, 'measuredAt': 9.5}}}, 'needs the place it stands at')  # the model says it, not the door
            # A tile group is built standing on the ground: a lift would move its boxes and not the building.
            refused({'source': 'meshy/x', 'height': 9.5, 'lift': 2, 'tiles': tiles}, 'takes no lift')
            long_name = Path(scratch) / 'long.json'  # said when the set is read, not after the model has been shaped
            long_name.write_text(json.dumps({'models': {'ek_thirteen_c': {'source': 'meshy/x', 'height': 1.0, 'tiles': tiles}}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'at most 12'):
                convert.load_models(long_name)
        ares = convert.load_models(folder / 'ares-depot-game.json')
        self.assertEqual(ares['ek_ad_turret']['turn'], 90); self.assertEqual(len(ares['ek_ad_fence']['mesh']), 2); self.assertIn('paint', ares['ek_ad_depot'])
        self.assertEqual((len(ares['ek_ad_depot']['smooth']), len(ares['ek_ad_depot']['fence'])), (4, 6))  # its perimeter fence, and the wall behind
        self.assertEqual((ares['ek_ad_depot']['tiles']['door']['leaf'], models['ek_ss_shack']['tiles']['door']['leaf']), (2.1, 2.1))
        for model in (ares['ek_ad_depot'], ares['ek_ad_sign'], ares['ek_ad_fence'], models['ek_ss_shack'], models['ek_ss_vending']):
            self.assertEqual(model['measuredAt'], model['height'])
        self.assertNotIn('measuredAt', ares['ek_ad_crate'])  # nothing is measured on it


if __name__ == '__main__':
    unittest.main()
