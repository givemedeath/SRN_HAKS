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


class VoxelShellShadowTests(unittest.TestCase):
    def test_a_tunnelled_block_gets_a_closed_shadow_within_budget(self):
        try: import pymeshlab, igl
        except ImportError: self.skipTest('pymeshlab and igl not on this path')
        from .shadow import voxel_shell_proxy
        from .shell_repair import shell_from_donor
        g = np.zeros((40, 16, 12), bool); g[4:36, 3:13, 3:9] = True; g[10:12, 3:13, 5:7] = False     # a block with a 2 mm tunnel
        grid = np.argwhere(g) * .001; cube = np.array([[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]) * .001
        quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        tri = np.array([[q[0], q[1], q[2]] for q in quads] + [[q[0], q[2], q[3]] for q in quads])
        p = (grid[:, None] + cube[None]).reshape(-1, 3); f = (tri[None] + 8*np.arange(len(grid))[:, None, None]).reshape(-1, 3)
        p, f, _ = shell_from_donor(p, f, voxel=.0005, faces_target=6000, dilate=0, erode=0, sigma=.5)
        v, t, checks = voxel_shell_proxy(p, f, {}, 200, {'voxel': .001, 'closing': 2}, pymeshlab, igl)
        self.assertLessEqual(len(t), 200); self.assertTrue(checks['topology']['closedWound']); self.assertEqual(checks['method'], 'voxel-shell')
        with self.assertRaisesRegex(ValueError, 'Bounded voxel-shell'): voxel_shell_proxy(p, f, {}, 200, {'voxel': .02}, pymeshlab, igl)
