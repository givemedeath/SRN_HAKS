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

    def test_a_source_with_fewer_materials_than_asked_for_is_refused(self):
        with self.assertRaises(ValueError):
            texture.materials(self.colours[self.truth < 2], 3)
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

    def test_a_point_a_few_voxels_off_the_shell_takes_the_nearest_blocks_mean(self):
        values, missed = self.read(3, 0.25)
        self.assertFalse(missed[0])
        self.assertTrue(np.allclose(values[0, :3], [0.8, 0.4, 0.6], atol=1e-5))  # its own side of the sheet, not the other half

    def test_a_point_far_from_any_voxel_is_missed(self):
        self.assertTrue(self.read(170, 0.25)[1][0])


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
