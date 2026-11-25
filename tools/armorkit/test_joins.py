"""The joins Street Casual asked for (2026-11-25): hips cut like briefs, a boot's instep given to the foot, an end
read from what it is open on, a tier per joint, a belt levelled by its strap, and a bake's parts worked side by
side and kept between bakes."""
import tempfile
import unittest.mock
import unittest

import numpy as np

from . import __main__ as cli
from . import accessory, bake, ends, seams, split


def rings(radius, levels, count=32, centre=(0.0, 0.0)):
    """An open tube along z with a ring of vertices at each of `levels`: (vertices, faces)."""
    turn = np.arange(count) * 2 * np.pi / count
    v = np.array([(centre[0] + radius * np.cos(a), centre[1] + radius * np.sin(a), z) for z in levels for a in turn])
    f = []
    for row in range(len(levels) - 1):
        for k in range(count):
            a, b = row * count + k, row * count + (k + 1) % count
            f += [(a, b, b + count), (a, b + count, a + count)]
    return v, np.array(f)


def strip(points_a, points_b):
    """A sheet between two rows of points, as triangles: (vertices, faces)."""
    v = np.concatenate([points_a, points_b])
    n = len(points_a)
    f = [face for k in range(n - 1) for face in ((k, k + 1, n + k + 1), (k, n + k + 1, n + k))]
    return v, np.array(f)


def doubled(job):
    """Work a process can be handed (`bake.worked`)."""
    return {'x': np.asarray(job['x']) * 2}


class BriefsTests(unittest.TestCase):
    def test_the_line_is_deep_between_the_legs_and_high_at_the_outside_of_the_hip_alike_before_and_behind(self):
        normal = np.array((0.0, 0.0, -1.0))
        a, b = seams.frame(normal)
        middle = np.concatenate([np.linspace(-0.1, 0.09, 40), [0.22, 0.25]])  # the crotch 9 cm down; trouser legs touch again farther down
        reach = split.briefs(np.full(64, 0.08), middle, a, b, np.array((-0.1, 0.0, 0.0)))  # the left hip
        way = np.cos(np.arange(64) * 2 * np.pi / 64)[:, None] * a + np.sin(np.arange(64) * 2 * np.pi / 64)[:, None] * b
        inner, outer = int(np.argmax(way[:, 0])), int(np.argmin(way[:, 0]))
        self.assertAlmostEqual(reach[inner], 0.09 + split.BRIEF_MARGIN)  # below the outfit's own crotch, not where the legs touch
        self.assertAlmostEqual(reach[outer], split.BRIEF_TOP)
        front, back = way[:, 1] > 1e-9, way[:, 1] < -1e-9
        self.assertTrue(np.allclose(np.sort(reach[front]), np.sort(reach[back])))  # sloped behind as before
        self.assertTrue(np.all(np.diff(reach[np.argsort(way[:, 0])]) >= -1e-12))  # ever deeper toward the middle

    def test_a_shallow_crotch_leaves_the_bodys_own_depth_between_the_legs(self):
        a, b = seams.frame(np.array((0.0, 0.0, -1.0)))
        reach = split.briefs(np.full(64, 0.08), np.linspace(-0.1, 0.03, 20), a, b, np.array((0.1, 0.0, 0.0)))
        self.assertAlmostEqual(reach.max(), 0.08)


class FootedTests(unittest.TestCase):
    def setUp(self):
        shaft = rings(0.05, np.linspace(0.0, 0.3, 16))
        rows = np.linspace(0.03, 0.2, 18)
        instep = strip(np.array([(-0.03, y, 0.02) for y in rows]), np.array([(0.03, y, 0.02) for y in rows]))  # the top of the foot, above the plane
        self.v = np.concatenate([shaft[0], instep[0]])
        self.f = np.concatenate([shaft[1], instep[1] + len(shaft[0])])
        self.names = [split.token('shin', 'l'), split.token('foot', 'l')]
        self.cuts = {('ankle', 'l'): (np.zeros(3), np.array((0.0, 0.0, -1.0)))}

    def test_what_lies_before_the_shaft_no_higher_than_the_top_of_the_foot_goes_to_the_foot(self):
        owner = np.zeros(len(self.f), int)
        v, f, _, owner, origin, line = split.footed(self.v, self.f, np.zeros((len(self.v), 2)), owner, np.arange(len(self.f)), self.names, self.cuts)
        front = 0.05 + split.FOOT_ROOM
        foot, shin = f[owner == 1], f[owner == 0]
        self.assertTrue(len(foot) and line.any())
        self.assertGreaterEqual(v[foot][:, :, 1].min(), front - 1e-9)  # nothing of the shaft
        ahead = v[shin][:, :, 1].max(axis=1) > front + 1e-9
        self.assertFalse(ahead.any())  # and the shin keeps nothing before it
        self.assertTrue(np.allclose(v[line, 2], 0.0))  # the line the two part on lies on the plane: both rims close from it
        self.assertTrue(np.allclose(v[line, 1], front))
        self.assertEqual(len(line), len(v))

    def test_a_shin_with_nothing_before_its_shaft_is_left_as_it_is(self):
        v, f = rings(0.05, np.linspace(0.0, 0.3, 16))
        out = split.footed(v, f, np.zeros((len(v), 2)), np.zeros(len(f), int), np.arange(len(f)), self.names, self.cuts)
        self.assertTrue(np.array_equal(out[0], v) and np.array_equal(out[1], f) and not out[5].any())

    def test_a_cap_grows_from_flagged_points_whichever_side_of_the_plane_their_faces_are_on(self):
        v, f = rings(0.05, [0.0, 0.05])  # a rim on the plane whose faces lie on the over side: what `footed` hands the foot
        point, normal = np.zeros(3), np.array((0.0, 0.0, -1.0))
        none = split.cap(v, np.zeros((len(v), 2)), f, len(v), point, normal, 0.03, 0.1)
        self.assertEqual(len(none[2]), 0)
        flags = np.abs(v[:, 2]) < 1e-9
        grown = split.cap(v, np.zeros((len(v), 2)), f, len(v), point, normal, 0.03, 0.01, rim=flags)  # and however far out
        self.assertGreater(len(grown[2]), 0)
        self.assertGreater(grown[0][:, 2].max(), 0.02)  # past the plane, into the part over it


class OpeningTests(unittest.TestCase):
    def setUp(self):
        shaft = rings(0.05, [0.0, -0.1, -0.2], count=64)  # a foot's shaft, open on the plane
        turn = np.radians(np.linspace(45, 135, 12))
        toe = strip(np.array([(0.1 * np.cos(a), 0.1 * np.sin(a), 0.004) for a in turn]),
                    np.array([(0.2 * np.cos(a), 0.2 * np.sin(a), -0.02) for a in turn]))  # a toe box the plane passes through, 12 cm out
        self.v = np.concatenate([shaft[0], toe[0]])
        self.f = np.concatenate([shaft[1], toe[1] + len(shaft[0])])
        self.point, self.normal = np.zeros(3), np.array((0.0, 0.0, -1.0))

    def test_an_under_ends_ring_is_read_no_farther_out_than_what_the_part_is_open_on(self):
        plain = ends.ring(self.v, self.f, self.point, self.normal, True)
        self.assertGreater(plain.max(), 0.1)  # the toe box, read as the end
        opened = ends.opening(self.v, self.f, np.arange(len(self.v)), self.point, self.normal)
        self.assertTrue(np.allclose(opened, 0.05, atol=1e-3))
        held = ends.ring(self.v, self.f, self.point, self.normal, True, opened)
        self.assertLessEqual(held.max(), ends.OPEN * 0.05 + 1e-9)

    def test_edges_that_do_not_come_round_the_axis_are_no_opening(self):
        half = self.f[(self.v[self.f][:, :, 1] >= -1e-9).all(axis=1)]
        self.assertIsNone(ends.opening(self.v, half, np.arange(len(self.v)), self.point, self.normal))
        closed = rings(0.05, [-0.01, -0.1])
        self.assertIsNone(ends.opening(closed[0], closed[1], np.arange(len(closed[0])), self.point, self.normal))  # nothing open on the plane

    def test_shaping_leaves_what_stands_far_outside_the_opening_where_it_is(self):
        envelope = body = np.full(16, 0.045)
        after = ends.shaped(self.v, self.f, np.ones(len(self.f), bool), [(self.point, self.normal, envelope, body - 0.01, True, False)])
        far = np.linalg.norm(self.v[:, :2], axis=1) > 0.15
        self.assertLess(np.abs(after[far] - self.v[far]).max(), 0.01)  # read from the toe box, it was drawn in by its whole 15 cm
        rim = (np.abs(self.v[:, 2]) < 1e-9) & ~far
        self.assertLess(np.linalg.norm(after[rim, :2], axis=1).max(), 0.045)


class TierTests(unittest.TestCase):
    CONTRACT = {'tierOffsets': {'1': 0.01, '3': 0.03},
                'joints': {joint: {'bodies': {'b': {'sides': {'l': {'bodyRing': [0.05] * 16}},
                                                  'tiers': {'1': {'minimumOverlap': 0.02}, '3': {'minimumOverlap': 0.04}}}}}
                           for joint in ('knee', 'shoulder')}}

    def test_a_tier_is_one_for_every_joint_or_one_a_joint(self):
        tier = {'default': 3, 'shoulder': 1}
        self.assertEqual((seams.at(2, 'knee'), seams.at(tier, 'knee'), seams.at(tier, 'shoulder')), (2, 3, 1))
        self.assertAlmostEqual(seams.envelope(self.CONTRACT, 'knee', 'b', tier, 'l')[0], 0.08)
        self.assertAlmostEqual(seams.envelope(self.CONTRACT, 'shoulder', 'b', tier, 'l')[0], 0.06)
        self.assertEqual((seams.overlap(self.CONTRACT, 'knee', 'b', tier), seams.overlap(self.CONTRACT, 'shoulder', 'b', tier)), (0.04, 0.02))

    def test_the_command_line_names_the_joints_cut_at_another_tier(self):
        self.assertEqual(cli.tiers(2, []), 2)
        self.assertEqual(cli.tiers(3, ['shoulder=1', 'neck=0']), {'default': 3, 'shoulder': 1, 'neck': 0})
        for wrong in ('shoulder', 'shoulder=9', 'collar=1'):
            with self.assertRaises(ValueError):
                cli.tiers(3, [wrong])


class StrapTests(unittest.TestCase):
    def test_a_belt_is_levelled_by_its_strap_not_by_what_hangs_from_it(self):
        strap = rings(0.2, np.linspace(-0.02, 0.02, 5), count=384)  # as dense as a belt comes: the strap is told by its points
        turn = np.radians(np.linspace(-40, 40, 80))
        low = np.array([(0.24 * np.sin(a), -0.24 * np.cos(a), -0.02) for a in turn])
        holster = strip(low, low + (0.0, 0.0, -0.22))  # a plate hanging off the front, as much surface as the strap
        v = np.concatenate([strap[0], holster[0]])
        f = np.concatenate([strap[1], holster[1] + len(strap[0])])
        lean = np.radians(15)
        tilt = np.array([[1, 0, 0], [0, np.cos(lean), -np.sin(lean)], [0, np.sin(lean), np.cos(lean)]])
        levelled, _ = accessory.level(v @ tilt.T + [0.1, 0.2, 0.9], f)
        band = levelled[:len(strap[0])]
        self.assertLess(np.ptp(band[:, 2]), 0.041)  # a band 4 cm tall, level all the way round: by its surface alone it stood 15 cm tall
        self.assertLess(np.abs(band[:, :2].mean(axis=0)).max(), 0.002)  # and the body's axis through its middle


class WorkedTests(unittest.TestCase):
    def test_jobs_are_worked_in_their_order_here_or_in_processes(self):
        jobs = [{'x': np.arange(3) + k} for k in range(3)]
        for workers in (1, 2):
            results, fresh = bake.worked(jobs, doubled, workers)
            self.assertEqual([result['x'].tolist() for result in results], [[0, 2, 4], [2, 4, 6], [4, 6, 8]])
            self.assertEqual(fresh, {0, 1, 2})

    def test_a_job_met_again_is_read_from_the_cache_and_one_cut_short_is_worked_again(self):
        jobs = [{'x': np.arange(3)}, {'x': np.arange(4)}]
        with tempfile.TemporaryDirectory() as folder:
            keys = [bake.digest('how', job) for job in jobs]
            self.assertEqual(bake.worked(jobs, doubled, 1, folder, keys)[1], {0, 1})
            results, fresh = bake.worked(jobs, lambda job: self.fail('worked again'), 1, folder, keys)
            self.assertEqual((fresh, results[1]['x'].tolist()), (set(), [0, 2, 4, 6]))
            (bake.Path(folder) / (keys[0] + '.npz')).write_bytes(b'cut short')
            self.assertEqual(bake.worked(jobs, doubled, 1, folder, keys)[1], {0})
            self.assertNotEqual(bake.digest('how', jobs[0]), bake.digest('otherwise', jobs[0]))  # another way of working finds nothing

    def test_a_part_reduced_in_a_process_is_the_part_reduced_here(self):
        v, f = rings(0.05, np.linspace(0.0, 0.3, 40), count=48)
        job = {'name': 'shinl', 'v': v, 'f': f, 'c': np.c_[v, v, v], 'made': np.full(len(f), split.OWN), 'origins': np.arange(len(f)),
               'joints': {}, 'radii': {}, 'budget': 1000}
        with unittest.mock.patch.object(split, 'planes', lambda joints: {}):
            here = bake._reduced(job['name'], v, f, job['c'], job['made'], job['origins'], {}, {}, 1000, None)
            there = bake._reduced_job(job)
        self.assertLessEqual(len(here[1]), 1000)
        self.assertTrue(np.array_equal(here[1], there['f']) and np.array_equal(here[0], there['v']) and int(there['before']) == len(f))


if __name__ == '__main__':
    unittest.main()
