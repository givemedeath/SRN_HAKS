import unittest
import numpy as np
from .geometry import protected_checks


class VisibleOnlyOpeningProbeTests(unittest.TestCase):
    def setUp(self):
        self.p = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1.]]); self.f = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])
        self.blocked = {'name': 'guard', 'start': [.2, .2, -1], 'end': [.2, .2, 2]}       # a line through the solid

    def test_an_obstructed_probe_fails_both_kinds_unless_marked(self):
        for kind in ('visible', 'shadow'):
            with self.assertRaisesRegex(ValueError, 'obstructed'): protected_checks(self.p, self.f, {'openingProbes': [self.blocked]}, kind)

    def test_a_marked_probe_is_left_out_of_the_shadow_only_and_reported(self):
        row = {**self.blocked, 'visibleOnly': True, 'visibleOnlyReview': 'reviewed: the shadow closes the guard'}
        report = protected_checks(self.p, self.f, {'openingProbes': [row]}, 'shadow')
        self.assertEqual(report['openings'], [{'name': 'guard', 'notHeldAgainstShadow': True}])
        with self.assertRaisesRegex(ValueError, 'obstructed'): protected_checks(self.p, self.f, {'openingProbes': [row]})

    def test_the_mark_needs_its_review(self):
        with self.assertRaisesRegex(ValueError, 'visibleOnlyReview'):
            protected_checks(self.p, self.f, {'openingProbes': [{**self.blocked, 'visibleOnly': True}]}, 'shadow')
