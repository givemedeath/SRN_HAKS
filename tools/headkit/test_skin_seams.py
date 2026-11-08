import unittest
import numpy as np
from headkit.skin_seams import reconcile


class SkinSeamTests(unittest.TestCase):
    def setUp(self):
        x = np.arange(20)*.006
        self.points = np.column_stack((np.tile(x, 2), np.repeat([0, .003], 20), np.zeros(40)))
        self.charts = np.repeat([0, 1], 20)
        self.normals = np.tile([0., 0., 1.], (40, 1))
        self.shades = 50 + np.tile(np.arange(20)*3, 2) + self.charts*7
        self.allowed = np.arange(0, 255)

    def check_seam(self, limit):
        return reconcile(self.points, self.normals, self.charts, self.shades, 1., self.allowed, limit)

    def test_blend_only_when_cross_chart_step_exceeds_limit(self):
        same, report = self.check_seam(100.)
        np.testing.assert_array_equal(same, self.shades)
        self.assertFalse(report['changed'])
        limit = report['ratioBefore'] - .14
        result, fixed = self.check_seam(limit)
        self.assertTrue(fixed['changed'])
        self.assertLessEqual(fixed['ratioAfter'], limit)
        self.assertLess(np.abs(result-self.shades).max(), 6)

    def test_opposite_surfaces_and_single_chart_are_preserved(self):
        self.normals[20:] *= -1
        same, report = self.check_seam(1.)
        np.testing.assert_array_equal(same, self.shades)
        self.assertFalse(report['changed'])
        self.charts[:] = 0
        self.assertFalse(self.check_seam(1.)[1]['changed'])
