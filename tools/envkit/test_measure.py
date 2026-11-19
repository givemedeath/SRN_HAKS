"""A generated building is measured before its game set is written: its slab, the heights that fit it to tiles, its walls."""
import unittest

from tools.envkit import measure
from tools.envkit.test_tile import box, scene


class MeasureTests(unittest.TestCase):
    def test_the_height_for_the_door_and_the_tallest_that_fits_fewer_tiles(self):
        """The power station: 20.33 by 14.9 metres at 10, its door's leaf 2.11 there; two tiles hold it at 9.55."""
        found = measure.fits(10.0, [20.33, 14.9], leaf=2.11)
        self.assertEqual(found[0]['tiles'], [3, 2]); self.assertAlmostEqual(found[0]['leaf'], 2.1); self.assertAlmostEqual(found[0]['height'], 9.95)
        two = next(one for one in found if one['tiles'] == [2, 2])
        self.assertLessEqual(two['footprint'][0], 19.5); self.assertGreater(two['footprint'][0], 19.4); self.assertAlmostEqual(two['height'], 9.59, places=1)
        self.assertAlmostEqual(two['leaf'], 2.02, places=1)
        self.assertEqual(measure.tiles([19.5, 9.5]), (2, 1)); self.assertEqual(measure.tiles([19.51, 9.5]), (3, 1))
        self.assertEqual([one['tiles'] for one in measure.fits(4.0, [8.0, 6.0])], [[1, 1]])  # no door measured: as it stands, and nothing smaller
        self.assertFalse(any(one['tiles'] == [1, 1] for one in found))  # a door of a metre is no door

    def test_the_slab_and_a_wall_are_found(self):
        vertices, faces = scene(box((-6, -4, 0), (6, 4, 0.3)), box((-3, -2, 0.3), (3, 0.5, 5)))
        slab = measure.slab(vertices, faces)
        self.assertAlmostEqual(slab['top'], 0.3); self.assertEqual(slab['box'], [[-6.0, -4.0], [6.0, 4.0]])
        self.assertIsNone(measure.slab(*box((-3, -2, 0), (3, 2, 5))))  # a block on the ground has none
        wall = measure.probe(vertices, faces, [[-1, -1, 1], [1, 3, 2]])
        self.assertAlmostEqual(wall['high'][1], 0.5); self.assertEqual(measure.probe(vertices, faces, [[10, 10, 1], [11, 11, 2]]), {'points': 0})
        with self.assertRaisesRegex(ValueError, 'low corner'):
            measure.probe(vertices, faces, [[1, 1, 1], [0, 2, 2]])


if __name__ == '__main__':
    unittest.main()
