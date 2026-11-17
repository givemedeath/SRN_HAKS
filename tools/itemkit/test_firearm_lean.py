import unittest

import numpy as np

from .firearm_lean import LIMIT_DEGREES, reviewed_lean, sideways_lean


def box(low, high):
    low, high = np.asarray(low, float), np.asarray(high, float)
    corners = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], float) * (high - low) + low
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return corners, np.array(faces)


def gun(lever=True):
    """A slide, a grip under its rear, and a one-sided lever: native frame, x across, y up, the barrel down -z."""
    parts = [box((-.015, .08, -.18), (.015, .12, .03)), box((-.014, -.05, -.02), (.014, .08, .03))]
    if lever: parts.append(box((.015, .09, -.06), (.024, .10, -.03)))
    vertices, faces, offset = [], [], 0
    for v, f in parts:
        vertices.append(v); faces.append(f + offset); offset += len(v)
    return np.vstack(vertices), np.vstack(faces)


def rolled(vertices, degrees, toe=0.):
    r, t = np.radians(degrees), np.radians(toe)
    about_barrel = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]])
    about_up = np.array([[np.cos(t), 0, np.sin(t)], [0, 1, 0], [-np.sin(t), 0, np.cos(t)]])
    return vertices @ (about_barrel @ about_up).T


class SidewaysLeanTests(unittest.TestCase):
    def test_an_upright_gun_has_no_lean_despite_a_one_sided_lever(self):
        vertices, faces = gun()
        report = reviewed_lean(vertices, faces)
        self.assertLess(report['leanDegrees'], .3)
        self.assertEqual(report['limitDegrees'], LIMIT_DEGREES)

    def test_a_roll_about_the_barrel_is_measured(self):
        vertices, faces = gun()
        for degrees in (-10., -3., 6.):
            report = sideways_lean(rolled(vertices, degrees), faces)
            self.assertAlmostEqual(abs(report['rollDegrees']), abs(degrees), delta=.4)
            self.assertAlmostEqual(report['leanDegrees'], abs(degrees), delta=.4)

    def test_a_toe_to_one_side_is_measured(self):
        vertices, faces = gun(lever=False)
        report = sideways_lean(rolled(vertices, 0., 4.), faces)
        self.assertAlmostEqual(abs(report['toeDegrees']), 4., delta=.4)
        self.assertLess(abs(report['rollDegrees']), .4)

    def test_a_leaning_gun_is_refused_until_its_measurement_is_reviewed(self):
        vertices, faces = gun(); leaning = rolled(vertices, 6.)
        with self.assertRaisesRegex(ValueError, 'leans .* degrees sideways'): reviewed_lean(leaning, faces)
        measured = sideways_lean(leaning, faces)['leanDegrees']
        for bad in ({'decision': 'approved', 'leanDegrees': measured, 'notes': ' '}, {'decision': 'approved', 'leanDegrees': measured - .5, 'notes': 'x'},
                    {'decision': 'pending', 'leanDegrees': measured, 'notes': 'x'}):
            with self.assertRaisesRegex(ValueError, 'sidewaysLeanReview'): reviewed_lean(leaning, faces, bad)
        review = {'decision': 'approved', 'leanDegrees': round(measured, 2), 'notes': 'Published as shipped.'}
        self.assertEqual(reviewed_lean(leaning, faces, review)['review'], review)

    def test_a_flat_sheet_has_no_middle_to_measure(self):
        vertices = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 1], [0, 1, 1]], float); faces = np.array([[0, 1, 2], [1, 3, 2], [0, 2, 1], [1, 2, 3]])
        with self.assertRaisesRegex(ValueError, 'two sides'): sideways_lean(vertices, faces)
