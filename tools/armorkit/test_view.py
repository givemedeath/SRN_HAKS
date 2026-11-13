"""Offline views: parts loaded from a re-split, moved with their bones, and drawn with the nearest face in front."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import bake, split, view


def square(z=0.0, size=0.2):
    """Two triangles of a square in the plane y = 0 at height z, facing the front view."""
    v = np.array([(-size, 0.0, z - size), (size, 0.0, z - size), (size, 0.0, z + size), (-size, 0.0, z + size)])
    return v, np.array([(0, 1, 2), (0, 2, 3)])


class ViewTests(unittest.TestCase):
    def test_the_nearest_face_is_drawn_and_nothing_else_is_coloured(self):
        near_v, near_f = square()
        far_v = near_v + np.array([0.0, -0.1, 0.0])  # behind it, seen from the front (looking along -y)
        parts = {'chest': {'v': near_v, 'f': near_f, 'made': np.array([split.OWN, split.CLOSING])},
                 'pelvis': {'v': far_v, 'f': near_f, 'made': np.zeros(2, int)}}
        image = view.render(parts, view.DIRECTIONS['front'], np.zeros(3), 0.5, size=100)
        self.assertTrue((image[2, 2] == 255).all())  # outside the square: white
        hue = lambda colour: np.asarray(colour, float) / np.linalg.norm(colour, axis=-1, keepdims=True)
        shows = lambda pixels, colour: bool((np.abs(hue(pixels) - hue(colour)).max(axis=1) < 0.02).any())  # flat shaded: its hue, darker or lighter
        middle = image[30:70, 30:70].reshape(-1, 3).astype(float)
        # the chest's own face and its closing show; the pelvis behind them nowhere
        self.assertTrue(shows(middle, view.PALETTE['chest']) and shows(middle, view.KINDS[split.CLOSING]))
        self.assertFalse(shows(middle, view.PALETTE['pelvis']))
        # turned round, the pelvis is the nearer
        back = view.render(parts, view.DIRECTIONS['back'], np.zeros(3), 0.5, size=100)[30:70, 30:70].reshape(-1, 3).astype(float)
        self.assertTrue(shows(back, view.PALETTE['pelvis']) and not shows(back, view.PALETTE['chest']))

    def test_each_kind_the_split_made_and_the_skin_have_their_colours(self):
        made = np.array([split.OWN, split.CLOSING, split.CAP, split.WALL, split.PADDED, split.GUSSET, -1, split.OWN])
        tint = view.colours('legl', {'f': np.zeros((8, 3), int), 'made': made, 'skin': np.arange(8) == 7})
        self.assertEqual(tint[0].tolist(), list(view.PALETTE['legl']))
        self.assertEqual([tint[k].tolist() for k in range(1, 6)], [list(view.KINDS[kind]) for kind in made[1:6]])
        self.assertEqual(tint[6].tolist(), list(view.ADDED))  # a kept part only says it was added
        self.assertEqual(tint[7].tolist(), list(view.SKIN))
        self.assertEqual(view.colours('robe', {'f': np.zeros((1, 3), int)})[0].tolist(), list(view.OTHER))

    def test_a_part_moves_with_its_bone_and_one_without_a_bone_stays(self):
        turn = np.eye(4)
        turn[:3, :3] = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]  # a quarter turn about z
        rest = {'lbicep_g': np.eye(4)}
        rest['lbicep_g'][:3, 3] = (0.2, 0.0, 1.4)
        moved = {'lbicep_g': rest['lbicep_g'] @ turn}
        parts = {'bicepl': {'v': np.array([(0.3, 0.0, 1.4)]), 'f': np.zeros((0, 3), int)}, 'robe': {'v': np.array([(1.0, 2.0, 3.0)]), 'f': np.zeros((0, 3), int)}}
        out = view.posed(parts, rest, moved)
        self.assertTrue(np.allclose(out['bicepl']['v'], [(0.2, 0.1, 1.4)]))  # turned about the joint
        self.assertTrue(np.allclose(out['robe']['v'], parts['robe']['v']))

    def test_a_view_is_framed_on_a_bone_or_on_everything(self):
        bones = {'torso_g': np.eye(4), 'pelvis_g': np.eye(4)}
        bones['torso_g'][:3, 3] = (0.0, 0.0, 1.1)
        centre, extent = view.framed({}, bones, 'shoulders')
        self.assertTrue(np.allclose(centre, (0.0, 0.0, 1.35)) and extent == 0.5)
        parts = {'chest': {'v': np.array([(-0.5, 0.0, 0.0), (0.5, 0.2, 1.8)])}}
        centre, extent = view.framed(parts, bones, 'body')
        self.assertTrue(np.allclose(centre, (0.0, 0.1, 0.9)) and np.isclose(extent, 0.55 * 1.8))
        with self.assertRaises(ValueError):
            view.framed(parts, bones, 'elbows')

    def test_parts_a_re_split_wrote_load_as_they_were(self):
        v, f = square()
        parts = {'chest': {'v': v, 'f': f, 'made': np.array([split.OWN, split.CAP]), 'pad': np.array([False, True])}}
        with tempfile.TemporaryDirectory() as folder:
            path = bake.keep_parts(parts, Path(folder) / 'parts.npz')
            loaded = view.load(path)
            self.assertEqual(set(loaded), {'chest'})
            for key in ('v', 'f', 'made', 'pad'):
                self.assertTrue(np.array_equal(loaded['chest'][key], parts['chest'][key]))
            self.assertFalse(loaded['chest']['skin'].any())
            np.savez(Path(folder) / 'other.npz', chest__v=v)
            with self.assertRaises(ValueError):  # not a re-split's parts
                view.load(Path(folder) / 'other.npz')
            # framed on the parts alone, at rest, the view needs no body
            record = view.views(path, Path(folder) / 'sheet.png', Path(folder) / 'no-body', focus='body', directions=('front',), size=40)
            self.assertEqual((record['parts'], record['clip']), (1, None))

    def test_a_sheet_has_a_tile_per_view_and_the_legend(self):
        images = [np.full((40, 40, 3), value, np.uint8) for value in (0, 100, 200, 250)]
        with tempfile.TemporaryDirectory() as folder:
            from PIL import Image
            path = view.sheet(images, 3, Path(folder) / 'sheet.png', ['a', 'b', 'c', 'd'])
            with Image.open(path) as image:
                self.assertEqual(image.size, (120, 80 + 24))


if __name__ == '__main__':
    unittest.main()
