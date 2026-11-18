"""Where a generated model's picture is smeared: the kinds of surface a reference saw, and the patches told."""
import unittest

import numpy as np

from tools.envkit import smears


def quad(a, b, c, d):
    return [a, b, c], [a, c, d]


def scene():
    """A wall 6 m wide and 4 m tall facing +y, with, a metre in front of it: a rail along its whole width at 3 m, and a
    frame of two posts and two rails round the square from x -2 to 0 and z 0.5 to 2.5; and a side wall facing +x."""
    corners = []
    def strip(x0, x1, z0, z1, y):  # facing +y
        corners.extend(quad((x1, y, z0), (x0, y, z0), (x0, y, z1), (x1, y, z1)))
    strip(-3, 3, 0, 4, 0.0)                       # the wall
    strip(-3, 3, 3.0, 3.1, 1.0)                   # the rail
    strip(-2.1, -2.0, 0.4, 2.6, 1.0); strip(0.0, 0.1, 0.4, 2.6, 1.0)   # the frame's posts
    strip(-2.1, 0.1, 2.5, 2.6, 1.0); strip(-2.1, 0.1, 0.4, 0.5, 1.0)   # and its rails
    corners.extend(quad((3, -2, 0), (3, 0, 0), (3, 0, 4), (3, -2, 4)))  # the side wall, facing +x
    points = np.array(corners, float).reshape(-1, 3); faces = np.arange(len(points)).reshape(-1, 3)
    return points, np.zeros((len(points), 2)), faces


class SmearTests(unittest.TestCase):
    def setUp(self):
        self.points, self.uvs, self.faces = scene()
        self.face, self.point, _, self.area, self.normal = smears.scatter(self.points, self.uvs, self.faces)
        self.kind = smears.kinds(self.point, self.normal, ['front'])

    def most(self, mask):
        found = np.bincount(self.kind[mask], minlength=4); return smears.KINDS[int(found.argmax())], found.max() / found.sum()

    def test_points_are_strewn_evenly_and_stand_for_the_whole_surface(self):
        self.assertAlmostEqual(float(self.area.sum()), 6 * 4 + 6 * 0.1 + 2 * 2.2 * 0.1 + 2 * 2.2 * 0.1 + 2 * 4, places=3)
        on_wall = (self.point[:, 1] == 0) | (np.abs(self.point[:, 1]) < 1e-9)
        self.assertGreater(on_wall.sum(), 6 * 4 * smears.RESOLUTION ** 2 * 5)

    def test_the_wall_is_clean_in_the_open_behind_beside_the_rail_and_framed_inside_the_frame(self):
        x, y, z = self.point.T; wall = np.abs(y) < 1e-9
        self.assertEqual(self.most(wall & (x > 1) & (z > 3.5))[0], 'clean')           # nothing near it
        self.assertEqual(self.most(wall & (x > 1) & (z < 2.5))[0], 'clean')           # beside the frame, not inside it
        kind, share = self.most(wall & (x > 1) & (z > 3.14) & (z < 3.2)); self.assertEqual(kind, 'behind'); self.assertGreater(share, 0.9)
        kind, share = self.most(wall & (x > 1) & (z > 3.02) & (z < 3.08)); self.assertEqual(kind, 'unseen')  # the rail hides it
        kind, share = self.most(wall & (x > -1.6) & (x < -0.4) & (z > 0.9) & (z < 2.1)); self.assertEqual(kind, 'framed'); self.assertGreater(share, 0.95)
        self.assertEqual(self.most(wall & (x > -1.6) & (x < -0.4) & (z > 2.7) & (z < 2.8))[0], 'clean')  # over the frame, under the rail: closed one way only

    def test_what_faces_no_reference_is_unseen_until_one_is_drawn_from_its_side(self):
        side = np.abs(self.point[:, 0] - 3) < 1e-9
        self.assertEqual(self.most(side), ('unseen', 1.0))
        again = smears.kinds(self.point, self.normal, ['front', 'east'])
        self.assertTrue((again[side] == 0).all())
        with self.assertRaisesRegex(ValueError, 'A view is one of'):
            smears.kinds(self.point, self.normal, ['above'])

    def test_the_picture_judges_each_patch(self):
        fine = np.ones(len(self.point)); x, z = self.point[:, 0], self.point[:, 2]
        fine[(self.kind == 2) & (x > 0.5)] = 0.4          # the band behind the rail drawn soft to the right of the frame
        fine[(self.kind == 3) & (z < 1.5)] = 2.0          # mesh printed on the lower half of the framed panel
        found = smears.patches(self.point, self.area, self.kind, fine, self.normal)
        told = {(patch['kind'], patch['verdict']) for patch in found}
        self.assertEqual(told, {('behind', 'smudged'), ('behind', 'plain'), ('framed', 'printed'), ('framed', 'plain')})
        smudged = next(patch for patch in found if patch['verdict'] == 'smudged' and patch['area'] > 0.25)
        self.assertEqual(smudged['facing'], '+y'); self.assertGreaterEqual(smudged['box'][0][0], 0.5)
        self.assertLess(smudged['box'][1][2] - smudged['box'][0][2], 0.5); self.assertAlmostEqual(smudged['detail'], 0.4)
        printed = next(patch for patch in found if patch['verdict'] == 'printed')
        self.assertAlmostEqual(printed['area'], 1.76 * 0.88, delta=0.15)  # the panel's lower half, less the band beside its posts and rail; self.assertLessEqual(printed['box'][1][2], 1.5)
        self.assertEqual([patch['area'] for patch in found], sorted((patch['area'] for patch in found), reverse=True))
        with self.assertRaisesRegex(ValueError, 'No reference sees any of the model cleanly'):
            smears.patches(self.point, self.area, np.full(len(self.point), 1), fine, self.normal)


if __name__ == '__main__':
    unittest.main()
