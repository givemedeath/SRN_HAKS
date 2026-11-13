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


if __name__ == '__main__':
    unittest.main()
