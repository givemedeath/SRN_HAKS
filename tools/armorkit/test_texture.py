"""A part's texels are traced back to the generated outfit, coloured there and sorted into tint channels."""
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

from . import export, texture

SQUARE = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)  # texture coordinates of a part that fills its texture
FACES = np.array([[0, 1, 2], [0, 2, 3]])
FABRIC, TAN, PLATE = (0.35, 0.32, 0.29), (0.55, 0.44, 0.31), (0.58, 0.60, 0.60)


def shaded(colour, count, rng):
    """One flat material as a generated source shows it: shaded lighter and darker, with a little noise."""
    return np.clip(np.array(colour) * rng.uniform(0.8, 1.1, (count, 1)) + rng.normal(0, 0.006, (count, 3)), 0, 1)


class RasterTests(unittest.TestCase):
    def test_every_texel_of_a_covered_square_has_a_face_and_weights_that_give_its_centre(self):
        owner, weight = texture.raster(SQUARE, FACES, 8)
        self.assertTrue((owner >= 0).all())
        self.assertTrue(np.allclose(weight.sum(axis=2), 1.0))
        centre = (weight[:, :, :, None] * SQUARE[FACES[owner]]).sum(axis=2)
        rows, columns = np.mgrid[0:8, 0:8]
        self.assertTrue(np.allclose(centre, np.stack([(columns + 0.5) / 8, (rows + 0.5) / 8], axis=2)))  # u along a row, v down

    def test_a_face_covers_only_the_centres_inside_it(self):
        owner, _ = texture.raster(SQUARE, FACES[:1], 8)  # the half below the diagonal, counting v downward: u > v
        rows, columns = np.mgrid[0:8, 0:8]
        self.assertTrue(np.array_equal(owner >= 0, columns >= rows))

    def test_a_face_smaller_than_a_texel_still_gets_one(self):
        tiny = np.array([[0.51, 0.51], [0.52, 0.51], [0.51, 0.52]])
        owner, weight = texture.raster(tiny, np.array([[0, 1, 2]]), 8)
        self.assertEqual(np.argwhere(owner == 0).tolist(), [[4, 4]])
        self.assertTrue(np.allclose(weight[4, 4], 1 / 3))

    def test_colours_spread_into_empty_neighbours_and_not_round_the_border(self):
        filled = np.zeros((6, 6), bool); filled[2, 0] = True
        value = np.where(filled, 7, 0)
        wider, spreaded = texture.spread(filled, value, passes=1)
        self.assertEqual(sorted(np.argwhere(wider).tolist()), [[1, 0], [2, 0], [2, 1], [3, 0]])  # not column 5, across the border
        self.assertTrue((spreaded[wider] == 7).all() and (spreaded[~wider] == 0).all())
        self.assertFalse(filled[1, 0])  # the given arrays are left alone


class SizeTests(unittest.TestCase):
    def test_a_larger_part_gets_a_larger_texture_within_the_limits(self):
        square = lambda side: (np.array([[0, 0, 0], [side, 0, 0], [side, side, 0], [0, side, 0]], float), FACES)
        self.assertEqual(texture.size(*square(0.2)), 256)  # 0.04 m2 at 2.2 mm a texel and 35 % cover: 154, so 256
        self.assertEqual(texture.size(*square(0.4)), 512)
        self.assertEqual(texture.size(*square(0.01)), 128)
        self.assertEqual(texture.size(*square(5.0)), 1024)


class ColourMapTests(unittest.TestCase):
    def test_a_texel_takes_the_colour_of_the_point_it_came_from(self):
        # the part lies anywhere now; its vertices remember where they were on the generated mesh
        positions = np.array([[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 1, 5]], float)
        read = lambda points: (np.concatenate([points[:, :2], np.zeros((len(points), 4))], axis=1), np.zeros(len(points), bool))
        colour, covered, missed = texture.colour_map(SQUARE, FACES, positions, read, 4)
        self.assertTrue(covered.all() and missed == 0)
        self.assertTrue(np.allclose(colour[1, 2], [0.625, 0.375, 0.0]))  # row 1, column 2: u = 2.5 / 4, v = 1.5 / 4

    def test_a_texel_with_no_colour_found_is_left_uncovered(self):
        positions = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
        read = lambda points: (np.ones((len(points), 6)), points[:, 0] > 0.5)
        _, covered, missed = texture.colour_map(SQUARE, FACES, positions, read, 4)
        self.assertEqual(missed, 8)
        self.assertTrue(covered[:, :2].all() and not covered[:, 2:].any())


class MaterialTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.colours = np.concatenate([shaded(FABRIC, 6000, rng), shaded(TAN, 2500, rng), shaded(PLATE, 1500, rng)])
        self.truth = np.repeat([0, 1, 2], [6000, 2500, 1500])
        self.found = texture.materials(self.colours, 3)

    def test_shaded_flat_tones_are_sorted_into_their_materials(self):
        which = texture.labels(self.colours, self.found['tones'])
        order = [int(np.bincount(which[self.truth == k]).argmax()) for k in range(3)]
        self.assertEqual(sorted(order), [0, 1, 2])
        self.assertGreater(np.mean(np.array(order)[self.truth] == which), 0.995)  # shading does not move a texel to another material
        for k, colour in enumerate((FABRIC, TAN, PLATE)):
            self.assertTrue(np.allclose(self.found['colours'][order[k]], colour, atol=0.04))
        self.assertEqual(order[0], 0)  # the heaviest mode comes first
        # a deep crease is much darker than its material and still that material
        creases = np.array([FABRIC, TAN, PLATE]) * 0.55
        self.assertEqual(texture.labels(creases, self.found['tones']).tolist(), order)

    def test_a_mesh_face_is_of_the_material_most_of_its_readings_show(self):
        # a strip of 40 cells along x, two faces each; the colour at a point is fabric, from x = 2 tan, from x = 3 plate
        positions = np.array([(x, y, 0.0) for x in np.linspace(0, 4, 41) for y in (0.0, 0.1)])
        faces = np.array([face for i in range(40) for face in ([2 * i, 2 * i + 2, 2 * i + 1], [2 * i + 1, 2 * i + 2, 2 * i + 3])])
        rng = np.random.default_rng(5)
        asked = []

        def read(points):
            asked.append(len(points))
            kind = (points[:, 0] >= 2).astype(int) + (points[:, 0] >= 3)
            values = np.concatenate([shaded(colour, 1, rng) for colour in np.array([FABRIC, TAN, PLATE])[kind]])
            return values, (points[:, 0] > 2.5) & (points[:, 0] < 2.6)  # one cell of the tan has no colour
        which, found = texture.mesh_materials(positions, faces, read, 3)
        self.assertEqual(asked, [4 * len(faces)])  # each face at its middle and toward each corner
        fabric, tan, plate = texture.labels(np.array([FABRIC, TAN, PLATE]), found['tones']).tolist()
        self.assertEqual(fabric, 0)  # the commonest first
        middle = positions[faces].mean(axis=1)[:, 0]
        expected = np.where(middle < 2, fabric, np.where(middle < 3, tan, plate))
        expected[(middle > 2.5) & (middle < 2.6)] = fabric  # a face with no reading is of the commonest material
        self.assertEqual(which.tolist(), expected.tolist())
        # a face across the line between two materials goes to the one three of its four readings show
        across = np.array([(1.9, 0, 0), (2.02, 0, 0), (1.9, 0.1, 0)])
        again, _ = texture.mesh_materials(np.concatenate([positions, across]), np.concatenate([faces, [[82, 83, 84]]]), read, 3)
        self.assertEqual(again[-1], fabric)

    def test_a_tint_texture_is_filled_to_its_last_texel_from_the_nearest_chart(self):
        which = texture.labels(np.array([FABRIC, TAN, PLATE]), self.found['tones'])
        channels = [None] * 3
        for k, name in zip(which, ('cloth1', 'leather1', 'metal1')):
            channels[k] = name
        colour = np.zeros((32, 32, 3)); covered = np.zeros((32, 32), bool)
        colour[:, :4], covered[:, :4] = TAN, True
        colour[:, 28:], covered[:, 28:] = FABRIC, True
        shades, layers = texture.tint_maps(colour, covered, self.found, channels)
        self.assertTrue((layers[:, :16] == export.LAYERS['leather1']).all() and (layers[:, 16:] == export.LAYERS['cloth1']).all())
        self.assertTrue((shades[:, 4:16] == shades[:, 3:4]).all() and (shades[:, 16:28] == shades[:, 28:29]).all())
        filled, value = texture.spread(np.zeros((4, 4), bool), np.ones((4, 4)), passes=None)
        self.assertFalse(filled.any())  # nothing to spread from: it stops

    def test_a_source_with_fewer_materials_than_asked_for_is_refused(self):
        with self.assertRaises(ValueError):
            texture.materials(self.colours[self.truth < 2], 3)
        with self.assertRaises(ValueError):  # a tone on a hundredth of the texels is a mark, not a material
            texture.materials(np.concatenate([self.colours[self.truth < 2], self.colours[self.truth == 2][:80]]), 3)
        with self.assertRaises(ValueError):
            texture.materials(np.zeros((0, 3)), 3)

    def test_a_tint_texture_gives_each_material_its_channel_and_a_shade_by_lightness(self):
        which = texture.labels(np.array([FABRIC, TAN, PLATE]), self.found['tones'])
        channels = [None] * 3
        for k, name in zip(which, ('cloth1', 'leather1', 'metal1')):
            channels[k] = name
        colour = np.zeros((8, 8, 3)); covered = np.zeros((8, 8), bool)
        colour[:, :3], covered[:, :3] = TAN, True
        colour[0, 0], colour[1, 0] = np.array(TAN) * 1.1, np.array(TAN) * 0.8
        colour[:, 3], covered[:, 3] = PLATE, True
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, pad=1)
        self.assertTrue((layers[:, :3] == export.LAYERS['leather1']).all() and (layers[:, 3:5] == export.LAYERS['metal1']).all())
        self.assertTrue((layers[:, 5:] == export.LAYERS[channels[0]]).all())  # beyond the spread: the first channel
        middle = texture.MIDDLE * (np.array(TAN) @ texture.LIGHT) / self.found['light'][which[1]]
        self.assertAlmostEqual(shades[4, 1], middle, delta=1)
        self.assertAlmostEqual(shades[0, 0], 1.1 * middle, delta=2)
        self.assertAlmostEqual(shades[1, 0], 0.8 * middle, delta=2)
        self.assertTrue((shades[:, 5:] == texture.MIDDLE).all())
        self.assertTrue(shades.min() >= texture.SHADES[0] and shades.max() <= texture.SHADES[1])
        self.assertEqual(export.read_tint(export.tint(shades, layers))[1].tolist(), layers.tolist())  # it is a tint texture
        with self.assertRaises(ValueError):
            texture.tint_maps(colour, covered, self.found, ['cloth1', 'leather1', 'no such channel'])

    def test_a_closing_is_drawn_in_the_outfits_commonest_material_at_its_middle_shade(self):
        fabric = int(texture.labels(np.array([FABRIC]), self.found['tones'])[0])
        self.assertEqual(fabric, 0)  # most of the outfit's texels: the first material
        channels = ['cloth1', 'leather1', 'metal1']
        # a part of tan and plate; its closing's texels were read off its edge, dark tan
        colour = np.zeros((8, 8, 3)); covered = np.ones((8, 8), bool)
        colour[:, :4], colour[:, 4:] = TAN, PLATE
        colour[2:4, 1:3] = np.array(TAN) * 0.6
        closing = texture.face_texels(SQUARE * 0.25 + (0.125, 0.25), FACES, [True, True], 8)
        self.assertTrue(np.array_equal(np.argwhere(closing), [(2, 1), (2, 2), (3, 1), (3, 2)]))
        self.assertFalse(texture.face_texels(SQUARE * 0.25 + (0.125, 0.25), FACES, [False, False], 8).any())
        plain_shades, plain_layers = texture.tint_maps(colour, covered, self.found, channels)
        self.assertTrue((plain_layers[closing] != export.LAYERS['cloth1']).all() and (plain_shades[closing] < texture.MIDDLE - 30).all())
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, closing=closing)
        self.assertTrue((layers[closing] == export.LAYERS['cloth1']).all() and (shades[closing] == texture.MIDDLE).all())
        self.assertTrue(np.array_equal(layers[~closing], plain_layers[~closing]) and np.array_equal(shades[~closing], plain_shades[~closing]))

    def test_beside_a_pad_a_cap_is_the_outfits_cloth(self):
        channels = ['cloth1', 'leather1', 'metal1']
        # a cap of 120 texels square: a third repeats the rim's cloth, creased dark in a band, a third the pad's strap,
        # and a third, grown from the pad's rim, the pad
        colour = np.zeros((256, 256, 3)); covered = np.ones((256, 256), bool)
        colour[:] = TAN
        cap = np.zeros((256, 256), bool); cap[64:184, 64:184] = True
        colour[64:184, 64:104], colour[64:184, 104:144], colour[64:184, 144:184] = FABRIC, TAN, PLATE
        colour[64:184, 80:84] = np.array(FABRIC) * 0.6
        padded = np.zeros((256, 256), bool); padded[64:184, 144:184] = True
        strap = np.zeros((256, 256), bool); strap[64:184, 104:144] = True
        as_read = texture.tint_maps(colour, covered, self.found, channels, pad=0, cap=cap)
        self.assertTrue((as_read[1][strap] == export.LAYERS['leather1']).all())  # wide enough to be no streak
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, pad=0, cap=cap, padded=padded)
        cloth = cap & (as_read[1] == export.LAYERS['cloth1'])
        self.assertTrue((layers[strap] == export.LAYERS['cloth1']).all())
        self.assertTrue((np.abs(shades[strap] - as_read[0][cloth].mean()) <= 0.5).all())  # at the mean shade of the cap's cloth
        self.assertTrue(np.array_equal(shades[cloth], as_read[0][cloth]) and shades[cloth].min() < texture.MIDDLE - 30)  # its creases kept
        self.assertTrue((layers[padded] == export.LAYERS['metal1']).all() and np.array_equal(shades[padded], as_read[0][padded]))
        self.assertTrue(np.array_equal(layers[~cap], as_read[1][~cap]) and np.array_equal(shades[~cap], as_read[0][~cap]))
        none = texture.tint_maps(colour, covered, self.found, channels, pad=0, cap=cap, padded=np.zeros((256, 256), bool))
        self.assertTrue(np.array_equal(none[0], as_read[0]) and np.array_equal(none[1], as_read[1]))  # a cap with no pad is as it was

    def test_a_cap_keeps_its_rims_materials_without_their_streaks(self):
        channels = ['cloth1', 'leather1', 'metal1']
        # a cap of 128 texels square in a texture of 256: its left half repeats the rim's cloth, creased dark in a band and
        # with a streak of the plate two texels wide; its right half the pad over the knee
        colour = np.zeros((256, 256, 3)); covered = np.ones((256, 256), bool)
        colour[:] = TAN
        cap = np.zeros((256, 256), bool); cap[64:192, 64:192] = True
        colour[64:192, 64:128], colour[64:192, 128:192] = FABRIC, PLATE
        colour[64:192, 80:84] = np.array(FABRIC) * 0.6
        colour[64:192, 100:102] = PLATE
        plain_shades, plain_layers = texture.tint_maps(colour, covered, self.found, channels, pad=0)
        streak = np.zeros((256, 256), bool); streak[64:192, 100:102] = True
        self.assertTrue((plain_layers[streak] == export.LAYERS['metal1']).all())
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, pad=0, cap=cap)
        self.assertTrue((layers[streak] == export.LAYERS['cloth1']).all())  # the streak is the cloth round it
        cloth = cap & (plain_layers == export.LAYERS['cloth1'])
        self.assertTrue((np.abs(shades[streak] - plain_shades[cloth].mean()) <= 0.5).all())  # at the mean shade of the cap's cloth
        self.assertTrue(np.array_equal(shades[cloth], plain_shades[cloth]) and shades[cloth].min() < texture.MIDDLE - 30)  # its creases kept
        pad = np.zeros((256, 256), bool); pad[64:192, 128:192] = True
        self.assertTrue((layers[pad] == export.LAYERS['metal1']).all() and np.array_equal(shades[pad], plain_shades[pad]))  # the pad stays
        self.assertTrue(np.array_equal(layers[~cap], plain_layers[~cap]) and np.array_equal(shades[~cap], plain_shades[~cap]))
        # what lies round the cap has no say in it: tan on every side, and none on the cap
        self.assertNotIn(export.LAYERS['leather1'], layers[cap])
        # where a closing is flagged too, it is the closing's
        closing = np.zeros((256, 256), bool); closing[64:192, 160:192] = True
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, pad=0, closing=closing, cap=cap)
        self.assertTrue((layers[closing] == export.LAYERS['cloth1']).all() and (shades[closing] == texture.MIDDLE).all())
        self.assertTrue((layers[pad & ~closing] == export.LAYERS['metal1']).all())

    def test_what_the_torso_wears_over_a_limb_is_found_by_its_reaching_the_cut(self):
        # a strip of five squares along x, two faces each, and a closing on its left end (vertices of its own)
        v = np.array([(x, y, 0) for x in range(6) for y in (0, 1)] + [(0, 0, 0), (0, 1, 0), (-1, 0.5, 0)], float)
        f = np.array([face for x in range(5) for face in ((2 * x, 2 * x + 2, 2 * x + 3), (2 * x, 2 * x + 3, 2 * x + 1))] + [(12, 13, 14)])
        closing = np.arange(len(f)) == 10
        tan, plate = 1, 2
        material = np.repeat([tan, tan, 0, tan, plate, 0], [2, 2, 2, 2, 2, 1])
        over = texture.overlaid(v, f, material, closing, [tan])
        # the vest's colour next to the cut and joined to it; not the same colour farther along, past the cloth
        self.assertEqual(np.flatnonzero(over).tolist(), [0, 1, 2, 3])
        self.assertEqual(np.flatnonzero(texture.overlaid(v, f, material, closing, [tan, plate])).tolist(), [0, 1, 2, 3])  # a plate away from the cut
        self.assertFalse(texture.overlaid(v, f, material, closing, []).any())
        self.assertFalse(texture.overlaid(v, f, material, np.zeros(len(f), bool), [tan]).any())  # no cut, nothing reaches it

    def test_a_parts_materials_are_told_by_face_and_along_its_cut(self):
        colour = np.zeros((8, 8, 3)); covered = np.ones((8, 8), bool)
        colour[:] = FABRIC
        rows, columns = np.mgrid[0:8, 0:8]
        colour[rows > columns] = TAN  # the texels of the second face: v greater than u
        which = texture.face_materials(SQUARE, FACES, colour, covered, self.found, 8)
        wanted = texture.labels(np.array([FABRIC, TAN]), self.found['tones'])
        self.assertEqual(which.tolist(), wanted.tolist())
        self.assertEqual(texture.face_materials(SQUARE, FACES, colour, np.zeros((8, 8), bool), self.found, 8).tolist(), [-1, -1])
        # along a cut: what a quarter or more of the closings' texels show, the outfit's cloth aside
        seen = np.full((4, 4), 0); seen[0] = [1, 1, 1, 2]; seen[1] = [1, 0, 0, -1]
        closing = np.zeros((4, 4), bool); closing[:2] = True
        self.assertEqual(texture.edge_materials(seen, closing), [1])  # four of seven; the one texel of material 2 is a mark
        self.assertEqual(texture.edge_materials(seen, closing, least=0.1), [1, 2])
        self.assertEqual(texture.edge_materials(seen, np.zeros((4, 4), bool)), [])

    def test_an_outfits_materials_have_the_two_channels_of_their_kind(self):
        self.assertEqual(texture.channels(['cloth', 'leather', 'metal']), [('cloth1', 'cloth2'), ('leather1', 'leather2'), ('metal1', 'metal2')])
        # two materials of a kind have a channel each, the commoner the first
        self.assertEqual(texture.channels(['cloth', 'leather', 'cloth', 'metal', 'metal', 'leather']),
                         [('cloth1', 'cloth1'), ('leather1', 'leather1'), ('cloth2', 'cloth2'), ('metal1', 'metal1'), ('metal2', 'metal2'), ('leather2', 'leather2')])
        self.assertEqual(texture.channels(['metal', 'cloth', 'cloth']), [('metal1', 'metal2'), ('cloth1', 'cloth1'), ('cloth2', 'cloth2')])
        self.assertEqual({name for pair in texture.channels(texture.KINDS) for name in pair}, set(export.LAYERS) - {'skin', 'hair', 'tattoo1', 'tattoo2'})
        for kinds in ([], ['cloth', 'silk'], ['cloth', 'cloth', 'cloth']):
            with self.assertRaises(ValueError):
                texture.channels(kinds)

    def strip(self, squares):
        # squares along x, two faces each: the first is beside the next square, the second beside the one before
        v = np.array([(x, y, 0) for x in range(squares + 1) for y in (0, 1)], float)
        return v, np.array([face for x in range(squares) for face in ((2 * x, 2 * x + 2, 2 * x + 3), (2 * x, 2 * x + 3, 2 * x + 1))])

    def test_a_garment_takes_its_kinds_second_channel_by_the_slot_it_is_worn_on(self):
        # a shirt, a vest across it, trousers that reach up onto the chest part, boots: cloth and leather
        v, f = self.strip(7)
        cloth, leather = 0, 1
        materials = np.repeat([cloth, cloth, leather, cloth, cloth, cloth, leather], 2)
        slots = np.repeat(['chest', 'chest', 'chest', 'chest', 'thigh', 'thigh', 'foot'], 2)
        flags = texture.worn_second(v, f, materials, slots, ['cloth', 'leather'])
        self.assertEqual(flags.shape, (14, 2))
        # the shirt is worn on the chest; the trousers on the thighs, their top on the chest part with them
        self.assertEqual(flags[materials == cloth, cloth].tolist(), [False] * 4 + [True] * 6)
        # the vest is worn on the chest, the boots on the feet
        self.assertEqual(flags[materials == leather, leather].tolist(), [False, False, True, True])
        # cloth showing on the vest's faces is the trousers' on the face beside them and the shirt's on the other
        self.assertEqual(flags[4:6, cloth].tolist(), [True, False])
        # leather showing on cloth is the vest's or the boots' beside it, and elsewhere what the slot the face is on says:
        # on the chest part the vest's, on the thighs leather worn on a leg
        self.assertEqual(flags[materials == cloth, leather].tolist(), [False] * 6 + [True] * 4)
        # a face no material was read for answers as its neighbours and its own slot do
        unread = materials.copy(); unread[13] = -1
        self.assertEqual(texture.worn_second(v, f, unread, slots, ['cloth', 'leather'])[13].tolist(), [True, True])
        # decided by where a garment is worn, not by the part a face is on: with the vest gone, shirt and trousers are one
        whole = texture.worn_second(v, f, np.where(np.arange(14) < 12, cloth, leather), slots, ['cloth', 'leather'])
        self.assertFalse(whole[:12, cloth].any())  # two squares on the thighs, four on the chest
        # an outfit with one garment of a kind is coloured by that kind's first channel, wherever it is worn
        self.assertFalse(texture.worn_second(v, f, np.zeros(14, int), np.repeat('thigh', 14), ['cloth']).any())
        self.assertTrue(texture.worn_second(v, f, materials, slots, ['cloth', 'leather'], second={'cloth': ('chest',), 'leather': ()})[:4, cloth].all())
        for given, kinds in ((materials[:-1], ['cloth', 'leather']), (materials, ['cloth']), (materials, ['cloth', 'silk'])):
            with self.assertRaises(ValueError):
                texture.worn_second(v, f, given, slots, kinds)

    def test_every_strap_on_a_limb_is_coloured_with_the_gloves_and_boots(self):
        # a vest, then down one side: a strap on the upper arm, one on the forearm, a glove; one on the thigh, a boot.
        # Cloth lies between them all, so each is a patch of its own
        v, f = self.strip(11)
        cloth, leather = 0, 1
        materials = np.repeat([leather, cloth, leather, cloth, leather, cloth, leather, cloth, leather, cloth, leather], 2)
        slots = np.repeat(['chest', 'chest', 'bicep', 'bicep', 'forearm', 'forearm', 'hand', 'thigh', 'thigh', 'shin', 'foot'], 2)
        flags = texture.worn_second(v, f, materials, slots, ['cloth', 'leather'])
        self.assertEqual(flags[materials == leather, leather][::2].tolist(), [False, True, True, True, True, True])
        self.assertEqual(set(texture.SECOND['leather']), {'shoulder', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot'})
        # a strap too thin to have faces of its own shows on the sleeve's faces. The sleeve is the shirt's, worn on the
        # chest, but the strap is where the face is: on the forearm
        v, f = self.strip(5)
        thin = texture.worn_second(v, f, np.repeat([leather, cloth, cloth, cloth, cloth], 2),
                                   np.repeat(['chest', 'chest', 'chest', 'forearm', 'forearm'], 2), ['cloth', 'leather'])
        self.assertFalse(thin[:, cloth].any())  # one shirt, on the first cloth channel throughout
        self.assertEqual(thin[:, leather].tolist(), [False] * 6 + [True] * 4)

    def test_what_the_split_added_takes_the_channel_of_the_edge_it_grew_from(self):
        v, f = self.strip(2)
        # a closing of two rings on the strip's left edge, a cap on its right, and an added face that touches nothing
        v = np.concatenate([v, [(-1, 0, 0), (-1, 1, 0), (-2, 0.5, 0), (3, 0.5, 0), (9, 9, 9), (9, 8, 9), (8, 9, 9)]])
        f = np.concatenate([f, [(0, 1, 7), (0, 7, 6), (6, 7, 8), (4, 9, 5), (10, 11, 12)]])
        added = np.arange(9) >= 4
        rows = np.array([[True, False]] * 2 + [[False, True]] * 2 + [[True, True]] * 5)
        flags = texture.added_second(v, f, added, rows)
        self.assertTrue(np.array_equal(flags[:4], rows[:4]))
        self.assertEqual(flags[4:].tolist(), [[True, False]] * 3 + [[False, True]] + [[False, False]])
        self.assertTrue(np.array_equal(texture.added_second(v, f[:4], added[:4], rows[:4]), rows[:4]))
        self.assertTrue(rows[4:].all())  # the rows given are left as they were
        for flagged, given in ((added[:-1], rows), (added, rows[:-1])):
            with self.assertRaises(ValueError):
                texture.added_second(v, f, flagged, given)

    def test_a_texel_takes_its_materials_second_channel_where_its_garment_does(self):
        which = texture.labels(np.array([FABRIC, TAN, PLATE]), self.found['tones'])
        kinds = [None] * 3
        for k, kind in zip(which, texture.KINDS):
            kinds[k] = kind
        channels = texture.channels(kinds)
        fabric, tan = int(which[0]), int(which[1])
        colour = np.zeros((8, 8, 3)); covered = np.ones((8, 8), bool)
        colour[:, :4], colour[:, 4:] = TAN, FABRIC
        covered[:, 7] = False
        second = np.zeros((8, 8, 3), bool)
        second[:4, :, tan] = True  # the upper rows are a garment that takes the leather's second channel
        second[2:, :, fabric] = True
        shades, layers = texture.tint_maps(colour, covered, self.found, channels, pad=0, second=second)
        self.assertTrue((layers[:4, :4] == export.LAYERS['leather2']).all() and (layers[4:, :4] == export.LAYERS['leather1']).all())
        self.assertTrue((layers[:2, 4:7] == export.LAYERS['cloth1']).all() and (layers[2:, 4:7] == export.LAYERS['cloth2']).all())
        self.assertTrue((layers[:, 7] == export.LAYERS['cloth1']).all())  # not covered and not spread into: the first channel
        # without the flags every material is on its first channel, the shades the same
        plain_shades, plain = texture.tint_maps(colour, covered, self.found, channels, pad=0)
        self.assertTrue(np.array_equal(plain_shades, shades))
        self.assertEqual(sorted(np.unique(plain).tolist()), sorted([export.LAYERS['cloth1'], export.LAYERS['leather1']]))
        # a closing is the outfit's cloth, in the channel the cloth has there
        closing = np.zeros((8, 8), bool); closing[:, 0] = True
        closed = texture.tint_maps(colour, covered, self.found, channels, pad=0, second=second, closing=closing)[1]
        self.assertTrue((closed[:2, 0] == export.LAYERS['cloth1']).all() and (closed[2:, 0] == export.LAYERS['cloth2']).all())
        # spread, a chart's edge takes its channel outward with it
        spread = texture.tint_maps(colour, covered, self.found, channels, second=second)[1]
        self.assertTrue((spread[:2, 7] == export.LAYERS['cloth1']).all() and (spread[2:, 7] == export.LAYERS['cloth2']).all())
        # the flags of faces, a row of them per face, laid out per texel
        rows = texture.face_texels(SQUARE, FACES, [[True, False, True], [False, True, True]], 8)
        self.assertEqual(rows.shape, (8, 8, 3))
        self.assertTrue(np.array_equal(rows[:, :, 0], texture.face_texels(SQUARE, FACES, [True, False], 8)) and rows[:, :, 2].all())
        self.assertTrue(np.array_equal(rows[:, :, 1], ~rows[:, :, 0]))
        for given in (second[:, :, :2], second[:4]):
            with self.assertRaises(ValueError):
                texture.tint_maps(colour, covered, self.found, channels, second=given)
        with self.assertRaises(ValueError):
            texture.tint_maps(colour, covered, self.found, [('cloth1', 'cloth2'), ('leather1',), ('metal1', 'metal2')])


class FieldTests(unittest.TestCase):
    """A field of 256 voxels a side with one coloured sheet of voxels at x index 32."""

    @classmethod
    def setUpClass(cls):
        y, z = (axis.reshape(-1) for axis in np.mgrid[0:256, 0:256])
        coords = np.stack([np.full(len(y), 32), y, z], axis=1)
        attrs = np.tile(np.array([0.2, 0.4, 0.6, 0.0, 0.5, 1.0], np.float32), (len(y), 1))
        attrs[y >= 128, 0] = 0.8  # the upper half is redder
        with tempfile.TemporaryDirectory() as folder:
            np.savez(Path(folder) / 'field.npz', coords=coords, attrs=attrs, resolution=np.array(256))
            cls.field, cls.levels = texture.open_field(Path(folder) / 'field.npz')
        cls.on_sheet = (32 + 0.5) / 256 - 0.5

    def read(self, x_voxels, y):
        return texture.read_field(self.field, self.levels, np.array([[self.on_sheet + x_voxels / 256, y, 0.0]]))

    def test_a_point_on_the_shell_is_read_between_its_voxels(self):
        values, missed = self.read(0, -0.25)
        self.assertFalse(missed[0])
        self.assertTrue(np.allclose(values[0, :3], [0.2, 0.4, 0.6], atol=1e-5))
        self.assertAlmostEqual(float(self.read(0, 0.25)[0][0, 0]), 0.8, places=5)

    def test_a_point_a_few_voxels_off_the_shell_takes_the_nearest_voxel(self):
        values, missed = self.read(3, 0.25)
        self.assertFalse(missed[0])
        self.assertTrue(np.allclose(values[0, :3], [0.8, 0.4, 0.6], atol=1e-5))  # its own side of the sheet, not the other half

    def test_a_point_farther_off_takes_the_mean_of_the_nearest_block(self):
        y = (128 + 0.5) / 256 - 0.5  # just inside the redder half, whose blocks of 32 start at this row
        values, missed = self.read(20, y)
        self.assertFalse(missed[0])
        self.assertTrue(np.allclose(values[0, :3], [0.8, 0.4, 0.6], atol=1e-5))

    def test_a_point_far_from_any_voxel_is_missed(self):
        self.assertTrue(self.read(170, 0.25)[1][0])


class ReliefTests(unittest.TestCase):
    """A flat square of the simplified outfit, facing +z, u along +x and v along +y, under a tilted fine surface."""
    POSITIONS = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float) * 0.2
    NORMALS = np.tile([0.0, 0.0, 1.0], (4, 1))

    @staticmethod
    def reads(normal, missed=False):
        value = texture.tensors(np.array([normal], float))
        value[:, 3:] += 0.5
        return lambda points: (np.repeat(value, len(points), axis=0), np.full(len(points), missed))

    def bake(self, normal, **options):
        posed = options.pop('posed', self.POSITIONS * 1.8)
        return texture.normal_map(SQUARE, FACES, options.pop('positions', self.POSITIONS), self.NORMALS, posed, self.reads(normal, **options), 8)

    def test_a_fine_surface_tilted_along_u_or_v_shows_in_red_or_green(self):
        tilt = np.radians(30)
        along_u, covered, missed = self.bake((np.sin(tilt), 0, np.cos(tilt)))
        self.assertTrue(covered.all() and missed == 0)
        self.assertTrue(np.allclose(along_u, [0.5 + 0.5 * np.sin(tilt), 0.5, 0.5 + 0.5 * np.cos(tilt)]))
        along_v = self.bake((0, np.sin(tilt), np.cos(tilt)))[0]
        self.assertTrue(np.allclose(along_v, [0.5, 0.5 + 0.5 * np.sin(tilt), 0.5 + 0.5 * np.cos(tilt)]))
        self.assertTrue(np.allclose(self.bake((0, -np.sin(tilt), -np.cos(tilt)))[0], along_v))  # a face wound the other way reads the same

    def test_a_reading_of_another_surface_and_a_texel_with_no_reading_stay_flat(self):
        steep = np.radians(80)
        self.assertTrue(np.allclose(self.bake((np.sin(steep), 0, np.cos(steep)))[0], texture.FLAT))
        image, _, missed = self.bake((0.5, 0, 0.866), missed=True)
        self.assertTrue(np.allclose(image, texture.FLAT) and missed == 64)

    def test_a_face_the_split_made_stays_flat(self):
        # the second face is a cap's: on the generated mesh its vertices repeat the rim's, so it has no area there
        positions = self.POSITIONS.copy(); positions[3] = positions[0]
        image = self.bake((0.5, 0, 0.866), positions=positions, posed=self.POSITIONS * 1.8)[0]
        rows, columns = np.mgrid[0:8, 0:8]
        self.assertTrue(np.allclose(image[columns < rows], texture.FLAT))  # the half the second face covers
        self.assertTrue(np.allclose(image[columns > rows], [0.75, 0.5, 0.933], atol=1e-3))

    def test_the_directions_of_a_high_detail_mesh_are_read_whatever_its_winding(self):
        # a sheet of small triangles tilted 20 degrees about y, every other one wound backwards
        tilt = np.radians(20); grid = np.linspace(-0.2, 0.2, 81)
        x, y = (axis.reshape(-1) for axis in np.meshgrid(grid, grid, indexing='ij'))
        vertices = np.stack([x * np.cos(tilt), y, -x * np.sin(tilt)], axis=1)
        index = np.arange(81 * 81).reshape(81, 81)
        a, b, c, d = index[:-1, :-1].reshape(-1), index[1:, :-1].reshape(-1), index[1:, 1:].reshape(-1), index[:-1, 1:].reshape(-1)
        faces = np.concatenate([np.stack([a, b, c], axis=1), np.stack([a, d, c], axis=1)])  # the second set runs the other way round
        field, levels = texture.normal_field(vertices, faces, side=256)
        points = np.array([[0.05 * np.cos(tilt), 0.03, -0.05 * np.sin(tilt)], [-0.1 * np.cos(tilt), -0.07, 0.1 * np.sin(tilt) + 2 / 256]])
        values, missed = texture.read_field(field, levels, points)
        self.assertFalse(missed.any())
        fine = texture.fine_normals(values, np.tile([0.0, 0.0, 1.0], (2, 1)))
        self.assertTrue(np.allclose(fine, [np.sin(tilt), 0, np.cos(tilt)], atol=1e-3))
        self.assertTrue(np.allclose(texture.fine_normals(values, np.tile([0.0, 0.0, -1.0], (2, 1))), [-np.sin(tilt), 0, -np.cos(tilt)], atol=1e-3))

    def test_a_map_is_halved_by_averaging_two_by_two(self):
        image = np.zeros((4, 4, 3)); image[0, 0], image[0, 1], image[3, 3] = (1, 0, 0), (0, 1, 0), (0, 0, 1)
        half = texture.halved(image)
        self.assertEqual(half.shape, (2, 2, 3))
        self.assertTrue(np.allclose(half[0, 0], [0.25, 0.25, 0]) and np.allclose(half[1, 1], [0, 0, 0.25]) and np.allclose(half[0, 1], 0))

    def test_a_normal_map_is_written_bottom_row_first_with_the_material_that_binds_it(self):
        image = np.zeros((2, 4, 3)); image[0, 0] = (1.0, 0.5, 0.0)
        blob = texture.tga(image)
        self.assertEqual(len(blob), 18 + 2 * 4 * 3)
        self.assertEqual((blob[2], int.from_bytes(blob[12:14], 'little'), int.from_bytes(blob[14:16], 'little'), blob[16], blob[17]), (2, 4, 2, 24, 0))
        self.assertEqual(list(blob[18:21]), [0, 128, 255])  # the row at v = 0 comes first, stored blue, green, red
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(texture.write_relief(folder, 'pmh0_bicepl6030', image), 'pmh0_bicepl6030n')
            self.assertEqual((Path(folder) / 'pmh0_bicepl6030n.tga').read_bytes(), blob)
            material = (Path(folder) / 'pmh0_bicepl6030.mtr').read_text().splitlines()
            self.assertEqual(material[:2], ['renderhint NormalTangents', 'texture1 pmh0_bicepl6030n'])
            self.assertFalse(any(line.startswith('texture0') for line in material))  # the tint texture stays the colour
            with self.assertRaises(ValueError):
                texture.write_relief(folder, 'pmh0_bicepl60300', image)  # 17 characters with the n


class ReliefShadeTests(unittest.TestCase):
    """A normal map of 32 texels a side with one fold running down it: the fine surface leans along u on either side."""

    @staticmethod
    def fold(ridge):
        image = np.empty((32, 32, 3)); image[:] = texture.FLAT
        lean = np.sin(np.radians(30)) * (1 if ridge else -1)
        image[:, 12:16, 0], image[:, 16:20, 0] = 0.5 - 0.5 * lean, 0.5 + 0.5 * lean  # away from the middle on a ridge, toward it in a crease
        image[:, 12:20, 2] = 0.5 + 0.5 * np.cos(np.radians(30))
        return image

    def test_a_flat_map_leaves_the_shade_alone(self):
        image = np.empty((16, 16, 3)); image[:] = texture.FLAT
        self.assertTrue(np.allclose(texture.relief_shade(image), 1.0))

    def test_a_ridge_is_lighter_along_its_top_and_a_crease_darker_along_its_bottom(self):
        ridge, crease = texture.relief_shade(self.fold(True)), texture.relief_shade(self.fold(False))
        self.assertTrue((ridge[:, 15:17] > 1.15).all())  # the limit is 1.2
        self.assertTrue((crease[:, 15:17] < 0.8).all())
        self.assertTrue((ridge[:, 15:17] > crease[:, 15:17] + 0.4).all())
        self.assertTrue(np.allclose(ridge[:, :6], 1.0) and np.allclose(ridge[:, 26:], 1.0))  # nothing far from the fold
        self.assertTrue(np.allclose(ridge, ridge[:1]))  # the same all the way along it
        low, high = texture.RELIEF_SHADE
        for shade in (ridge, crease):
            self.assertTrue(shade.min() >= low and shade.max() <= high)

    def test_a_fold_along_u_shows_as_one_along_v_does(self):
        turned = np.transpose(self.fold(True), (1, 0, 2))[:, :, [1, 0, 2]]  # the same fold, running along u
        self.assertTrue(np.allclose(texture.relief_shade(turned), texture.relief_shade(self.fold(True)).T))

    def test_charts_lying_close_are_not_read_as_bends_at_each_others_edges(self):
        # two charts four texels apart, each level but leaning its own way, as the packing leaves them
        image = np.empty((16, 32, 3)); image[:] = texture.FLAT
        charts = np.full((16, 32), -1); charts[:, 4:14], charts[:, 18:28] = 0, 1
        for chart, lean in ((0, -0.4), (1, 0.4)):
            image[charts == chart] = (0.5 + 0.5 * lean, 0.5, 0.5 + 0.5 * np.sqrt(1 - lean * lean))
        level = 1 - texture.SLOPE * (1 - np.sqrt(1 - 0.16))
        self.assertTrue(np.allclose(texture.relief_shade(image, charts)[charts >= 0], level))
        self.assertFalse(np.allclose(texture.relief_shade(image)[charts >= 0], level))  # without the charts their edges show
        # the chart of a texel comes from the faces: two triangles that share no laid-out vertex are two charts
        uvs = np.array([[0, 0], [0.4, 0], [0, 0.4], [0.6, 0.6], [1, 0.6], [0.6, 1]], float)
        found = texture.chart_map(uvs, np.array([[0, 1, 2], [3, 4, 5]]), 16)
        self.assertEqual((found[1, 1] >= 0, found[10, 10] >= 0, found[1, 1] != found[10, 10], found[15, 0]), (True, True, True, -1))

    def test_a_tilted_surface_is_darker_however_it_tilts(self):
        image = np.empty((16, 16, 3)); image[:] = (0.5 + 0.5 * np.sin(np.radians(40)), 0.5, 0.5 + 0.5 * np.cos(np.radians(40)))
        self.assertTrue(np.allclose(texture.relief_shade(image), 1 - texture.SLOPE * (1 - np.cos(np.radians(40)))))

    def test_smoothing_keeps_a_level_map_level_to_its_border(self):
        self.assertTrue(np.allclose(texture.smooth(np.full((9, 7, 2), 0.3), 2), 0.3))
        step = np.zeros((8, 8)); step[:, 4:] = 1.0
        self.assertTrue(np.allclose(texture.smooth(step, 1)[3], [0, 0, 0, 1 / 3, 2 / 3, 1, 1, 1]))

    def test_the_relief_reaches_the_tint_texture(self):
        rng = np.random.default_rng(3)
        found = texture.materials(np.concatenate([shaded(FABRIC, 6000, rng), shaded(TAN, 2500, rng), shaded(PLATE, 1500, rng)]), 3)
        colour = np.empty((32, 32, 3)); colour[:] = TAN
        covered = np.ones((32, 32), bool)
        channels = ['cloth1', 'leather1', 'metal1']
        plain = texture.tint_maps(colour, covered, found, channels)[0]
        deep = texture.tint_maps(colour, covered, found, channels, relief=self.fold(False))[0]
        self.assertTrue((deep[:, 15:17] < plain[:, 15:17] - 20).all())  # the crease is darker in the shade
        self.assertTrue(np.array_equal(deep[:, :6], plain[:, :6]))
        colour[:, 15:17] = np.array(TAN) * 0.7  # the generated colour already shows the crease about as dark as the relief would
        twice = texture.tint_maps(colour, covered, found, channels, relief=self.fold(False))[0]
        once = texture.tint_maps(colour, covered, found, channels)[0]
        self.assertTrue((twice[:, 15:17] >= once[:, 15:17] - 5).all())  # the darker of the two, not one on top of the other


class FakeAtlas:
    """Stands in for the unwrapping library: every face becomes a chart of its own."""
    atlas_count = 1

    def add_mesh(self, vertices, faces):
        self.vertices, self.faces = vertices, faces

    def generate(self, chart_options, pack_options):
        self.options = chart_options, pack_options

    def __getitem__(self, index):
        mapping = self.faces.reshape(-1)
        uvs = np.tile(np.array([[0, 0], [1, 0], [0, 1]], np.float32), (len(self.faces), 1))
        return mapping.astype(np.uint32), np.arange(len(mapping), dtype=np.uint32).reshape(-1, 3), uvs


class LayoutTests(unittest.TestCase):
    def test_the_layout_repeats_vertices_and_keeps_the_part(self):
        made = []
        library = types.SimpleNamespace(Atlas=lambda: made.append(FakeAtlas()) or made[-1], ChartOptions=types.SimpleNamespace, PackOptions=types.SimpleNamespace)
        vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
        mapping, faces, uvs = texture.layout(library, vertices, FACES, 128)
        self.assertEqual((len(mapping), faces.shape, uvs.shape), (6, (2, 3), (6, 2)))
        self.assertTrue(np.array_equal(vertices[mapping[faces]], vertices[FACES]))
        self.assertEqual((made[0].options[1].resolution, made[0].options[1].padding), (128, texture.PAD))

    def test_a_layout_that_changes_the_part_is_refused(self):
        class Wrong(FakeAtlas):
            def __getitem__(self, index):
                mapping, faces, uvs = super().__getitem__(index)
                return mapping[::-1].copy(), faces, uvs
        library = types.SimpleNamespace(Atlas=Wrong, ChartOptions=types.SimpleNamespace, PackOptions=types.SimpleNamespace)
        with self.assertRaises(ValueError):
            texture.layout(library, np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float), FACES, 128)


if __name__ == '__main__':
    unittest.main()
