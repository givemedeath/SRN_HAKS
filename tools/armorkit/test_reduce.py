"""A part over its triangle budget is brought under it by taking vertices out, none that stays moving."""
import unittest

import numpy as np

from . import reduce
from .test_split import open_edges, tube


def edges_twice(faces):
    """Whether every edge of `faces` is on two faces."""
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    return bool((np.unique(edges, axis=0, return_counts=True)[1] == 2).all())


def sealed(radius=0.06, around=24, along=40):
    """A closed sausage: a tube along z with a fan over each end."""
    v, f, _ = tube((0, 0, 0), (0, 0, 0.4), radius, around=around, along=along)
    ring = lambda row: row * around + np.arange(around)
    bottom, top = len(v), len(v) + 1
    v = np.concatenate([v, [(0, 0, -0.02), (0, 0, 0.42)]])
    low, high = ring(0), ring(along)
    caps = [(bottom, low[(k + 1) % around], low[k]) for k in range(around)] + [(top, high[k], high[(k + 1) % around]) for k in range(around)]
    return v, np.concatenate([f, np.array(caps)])


class ReduceTests(unittest.TestCase):
    def test_a_closed_part_comes_under_its_budget_and_stays_closed_and_on_its_surface(self):
        v, f = sealed()
        self.assertTrue(edges_twice(f))
        kept, faces, which = reduce.reduce(v, f, 1200, None)
        self.assertLessEqual(len(faces), 1200)
        self.assertTrue(edges_twice(faces))  # nothing parted, nothing joined
        points = v[kept]
        a, b, c = (points[faces[:, i]] for i in range(3))
        self.assertGreater(float(np.linalg.norm(np.cross(b - a, c - a), axis=1).min()), 2 * reduce.THIN)
        # every vertex kept is where it was, and lies on the sausage's round side or an end's fan
        side = np.abs(np.linalg.norm(points[:, :2], axis=1) - 0.06) < 1e-9
        self.assertTrue((side | (np.abs(points[:, 2] - 0.2) > 0.19)).all())
        # each face kept is one given, with its corners among the vertices it had or their neighbours'
        self.assertEqual(len(which), len(faces))
        self.assertEqual(len(np.unique(which)), len(which))
        # the faces still turn outward, as given
        normal = np.cross(b - a, c - a)
        out = (a + b + c) / 3 - (0, 0, 0.2)
        out[np.abs(out[:, 2]) < 0.18, 2] = 0.0
        self.assertGreater(float((np.einsum('ij,ij->i', normal, out) > 0).mean()), 0.99)

    def test_locked_vertices_and_an_open_rim_stay(self):
        v, f, _ = tube((0, 0, 0), (0, 0, 0.4), 0.06, around=24, along=40)  # open at both ends
        locked = np.zeros(len(v), bool)
        locked[v[:, 2] > 0.3] = True
        kept, faces, _ = reduce.reduce(v, f, 600, locked)
        self.assertTrue(set(np.flatnonzero(locked)) <= set(kept.tolist()))
        rims = np.flatnonzero((v[:, 2] < 1e-9) | (v[:, 2] > 0.4 - 1e-9))
        self.assertTrue(set(rims.tolist()) <= set(kept.tolist()))
        self.assertEqual(len(open_edges(faces)), len(open_edges(f)))  # the rims are the edges they were
        self.assertLess(len(faces), len(f))

    def test_a_flat_stretch_goes_first_and_a_ridge_stays(self):
        # a strip of a plane with a 1 cm fold across its middle
        xs, ys = np.linspace(0, 0.3, 31), np.linspace(0, 0.1, 11)
        v = np.array([(x, y, 0.01 * max(0.0, 1 - abs(x - 0.15) / 0.01)) for y in ys for x in xs])
        index = lambda i, j: j * len(xs) + i
        f = np.array([face for j in range(len(ys) - 1) for i in range(len(xs) - 1)
                      for face in ((index(i, j), index(i + 1, j), index(i + 1, j + 1)), (index(i, j), index(i + 1, j + 1), index(i, j + 1)))])
        kept, faces, _ = reduce.reduce(v, f, 200, None)
        self.assertLessEqual(len(faces), 200)
        points = v[kept]
        for y in np.linspace(0.005, 0.095, 10):  # the fold stands its full centimetre all along: no face cuts across it
            heights = []
            for a, b, c in points[faces]:
                matrix = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
                if abs(np.linalg.det(matrix)) < 1e-12:
                    continue
                s, t = np.linalg.solve(matrix, [0.15 - a[0], y - a[1]])
                if s >= -1e-9 and t >= -1e-9 and s + t <= 1 + 1e-9:
                    heights.append(a[2] + s * (b[2] - a[2]) + t * (c[2] - a[2]))
            self.assertAlmostEqual(max(heights), 0.01, delta=1e-6)
        self.assertLess(float(np.mean(np.abs(points[:, 2]) > 0)), 0.5)  # the flat goes first, and the ridge is not all that is left

    def test_nothing_is_taken_where_everything_is_locked_or_under_budget(self):
        v, f = sealed(around=8, along=6)
        for target, locked in ((len(f), None), (10, np.ones(len(v), bool))):
            kept, faces, which = reduce.reduce(v, f, target, locked)
            self.assertTrue(np.array_equal(kept, np.arange(len(v))) and np.array_equal(faces, f) and np.array_equal(which, np.arange(len(f))))
        with self.assertRaises(ValueError):
            reduce.reduce(v, f, 10, np.ones(3, bool))

    def test_a_rim_loses_points_where_it_runs_straight_and_stays_on_its_cut(self):
        # an open tube cut from a dense mesh: each rim 48 points round, 6 cm across, on its own plane
        tube_v, tube_f, _ = tube((0, 0, 0), (0, 0, 0.4), 0.06, around=48, along=40)
        for seed in range(2):  # numbered anew (seed 1), the folds come in the order that sagged a rim 2.04 mm on Linux (2026-11-14)
            order = np.random.default_rng(seed).permutation(len(tube_v)) if seed else np.arange(len(tube_v))
            v, f = tube_v[order], np.argsort(order)[tube_f]
            lines = np.where(v[:, 2] < 1e-9, 1, 0) | np.where(v[:, 2] > 0.4 - 1e-9, 2, 0)
            kept, faces, _ = reduce.reduce(v, f, 60, None, lines)  # fewer than its two rims have points
            self.assertLess(len(faces), 2 * 48)
            points, loose = v[kept], open_edges(faces)
            ends = points[loose]
            self.assertTrue(np.all((np.abs(ends[:, :, 2]).max(axis=1) < 1e-9) | (np.abs(ends[:, :, 2] - 0.4).max(axis=1) < 1e-9)))  # on its plane
            self.assertLess(len(loose), 2 * 48)  # fewer points round
            self.assertGreater(len(loose), 2 * 12)
            for height in (0.0, 0.4):  # every point the rim had lies within `RIM_SHIFT` of the rim left
                was = v[lines == (1 if height == 0 else 2)]
                a, b = (ends[np.abs(ends[:, 0, 2] - height) < 1e-9][:, k] for k in range(2))
                share = np.clip(np.einsum('pej,ej->pe', was[:, None] - a, b - a) / np.einsum('ej,ej->e', b - a, b - a), 0, 1)
                near = np.linalg.norm(a + share[..., None] * (b - a) - was[:, None], axis=2).min(axis=1)
                self.assertLess(float(near.max()), reduce.RIM_SHIFT + 1e-9, seed)

    def test_a_line_on_a_plane_inside_the_surface_is_reduced_along_itself(self):
        # a closed part whose end meets its cap on a joint's plane (z = 0.2), 48 points round: that line loses
        # points only along itself, and no face is left across the plane
        v, f = sealed(around=48, along=40)
        lines = np.where(np.abs(v[:, 2] - 0.2) < 1e-9, 1, 0)
        kept, faces, _ = reduce.reduce(v, f, 150, None, lines)
        self.assertLessEqual(len(faces), 150)
        self.assertTrue(edges_twice(faces))
        heights = v[kept][faces][:, :, 2] - 0.2
        self.assertFalse(np.any((heights.max(axis=1) > 1e-9) & (heights.min(axis=1) < -1e-9)))  # none spans the plane
        ring = int(lines[kept].sum())
        self.assertTrue(12 <= ring < 48, ring)  # fewer points round, and still round
        # without the line, the plane is crossed
        kept, faces, _ = reduce.reduce(v, f, 150, None, np.zeros(len(v), np.int64))
        heights = v[kept][faces][:, :, 2] - 0.2
        self.assertTrue(np.any((heights.max(axis=1) > 1e-9) & (heights.min(axis=1) < -1e-9)))

    def test_a_rim_keeps_the_point_where_it_runs_from_one_cut_onto_another(self):
        # a flat sheet whose lower edge is straight, cut by one plane to the left of its middle and another to the right
        xs, ys = np.linspace(0, 0.3, 31), np.linspace(0, 0.1, 11)
        v = np.array([(x, y, 0.0) for y in ys for x in xs])
        index = lambda i, j: j * len(xs) + i
        f = np.array([face for j in range(len(ys) - 1) for i in range(len(xs) - 1)
                      for face in ((index(i, j), index(i + 1, j), index(i + 1, j + 1)), (index(i, j), index(i + 1, j + 1), index(i, j + 1)))])
        low = v[:, 1] < 1e-9
        lines = np.where(low & (v[:, 0] < 0.15 + 1e-9), 1, 0) | np.where(low & (v[:, 0] > 0.15 - 1e-9), 2, 0)
        turn = index(15, 0)
        self.assertNotIn(turn, reduce.reduce(v, f, 20, None, np.zeros(len(v), np.int64))[0])  # on no cut, it may go
        kept, faces, _ = reduce.reduce(v, f, 20, None, lines)
        self.assertIn(turn, kept)
        for a, b in kept[open_edges(faces)]:  # every edge on the lower rim joins points of one cut
            if low[a] and low[b]:
                self.assertTrue(lines[a] & lines[b])


if __name__ == '__main__':
    unittest.main()
