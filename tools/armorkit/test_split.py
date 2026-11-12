"""An outfit mesh is cut on the joint planes into parts that keep its surface and overlap at the joints."""
import unittest

import numpy as np

from tools.robes import mesh_ops

from . import seams, split

# A stick figure in metres: left is negative x, arms hang away from the body, as on the SRN bodies.
JOINTS = {'torso_g': (0, 0, 1.2), 'pelvis_g': (0, 0, 1.2), 'neck_g': (0, 0, 1.65), 'head_g': (0, 0, 1.72)}
for side, x in (('l', -1.0), ('r', 1.0)):
    JOINTS.update({side + 'bicep_g': (0.2 * x, 0, 1.55), side + 'forearm_g': (0.3 * x, 0, 1.28), side + 'hand_g': (0.38 * x, 0, 1.02),
                   side + 'thigh_g': (0.12 * x, 0, 1.0), side + 'shin_g': (0.14 * x, 0, 0.55), side + 'foot_g': (0.15 * x, 0, 0.12)})
JOINT_RADIUS = {'neck': 0.07, 'waist': 0.16, 'shoulder': 0.07, 'elbow': 0.06, 'wrist': 0.045, 'hip': 0.1, 'knee': 0.07, 'ankle': 0.055}
RADII = {(joint, side): JOINT_RADIUS[joint] for joint in seams.JOINTS for side in seams.sides(joint)}
TOKENS = {'neck', 'chest', 'pelvis', 'bicepl', 'bicepr', 'forel', 'forer', 'handl', 'handr', 'legl', 'legr', 'shinl', 'shinr',
          'footl', 'footr'}


def tube(start, end, radius, around=12, along=24):
    """An open tube, with texture coordinates running around and along it."""
    start, end = np.asarray(start, float), np.asarray(end, float)
    axis = seams.unit(end - start)
    u, v = seams.frame(axis)
    points, uvs = [], []
    for i in range(along + 1):
        for k in range(around):
            angle = 2 * np.pi * k / around
            points.append(start + (end - start) * i / along + radius * (np.cos(angle) * u + np.sin(angle) * v))
            uvs.append((k / around, i / along))
    faces = []
    for i in range(along):
        for k in range(around):
            a, b = i * around + k, i * around + (k + 1) % around
            faces += [(a, b, b + around), (a, b + around, a + around)]
    return np.array(points), np.array(faces), np.array(uvs)


def join(*meshes):
    offset, points, faces, uvs = 0, [], [], []
    for p, f, t in meshes:
        points.append(p)
        faces.append(f + offset)
        uvs.append(t)
        offset += len(p)
    return np.concatenate(points), np.concatenate(faces), np.concatenate(uvs)


def area(vertices, faces):
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    return float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2)


def normals(vertices, faces):
    return np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])


def figure():
    J = {name: np.array(p, float) for name, p in JOINTS.items()}
    pieces = [tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube((0, 0, 1.58), (0, 0, 1.70), 0.06, along=6)]
    for s in 'lr':
        inside = J[s + 'bicep_g'] + 0.06 * seams.unit(J[s + 'bicep_g'] - J[s + 'forearm_g'])
        beyond = J[s + 'hand_g'] + 0.10 * seams.unit(J[s + 'hand_g'] - J[s + 'forearm_g'])
        pieces.append(tube(inside, J[s + 'forearm_g'], 0.05))
        pieces.append(tube(J[s + 'forearm_g'], beyond, 0.04))
        pieces.append(tube(J[s + 'thigh_g'] + (0, 0, 0.06), J[s + 'shin_g'], 0.08))
        pieces.append(tube(J[s + 'shin_g'], J[s + 'foot_g'] - (0, 0, 0.1), 0.05))
    return join(*pieces)


class CutTests(unittest.TestCase):
    def test_no_triangle_spans_the_plane_and_the_surface_is_kept(self):
        v, f, t = tube((0, 0, 0), (0, 0, 1), 0.1, along=3)
        nv, nf, nt, origin = split.cut(v, f, t, (0, 0, 0.4), (0, 0, 1))
        height = nv[nf][:, :, 2] - 0.4
        self.assertTrue(np.all((height.max(axis=1) <= 1e-9) | (height.min(axis=1) >= -1e-9)))
        self.assertAlmostEqual(area(nv, nf), area(v, f), places=9)
        self.assertEqual(len(origin), len(nf))
        self.assertTrue(np.all(origin < len(f)))
        self.assertTrue(len(nv) > len(v) and np.allclose(nv[len(v):, 2], 0.4))
        self.assertTrue(np.allclose(nt[len(v):, 1], 0.4))  # the along coordinate follows the height
        self.assertTrue(np.all((normals(v, f)[origin] * normals(nv, nf)).sum(axis=1) > 0))  # winding kept

    def test_a_plane_cuts_only_near_its_joint(self):
        near, far = tube((0, 0, 0), (0, 0, 1), 0.1, along=3), tube((1, 0, 0), (1, 0, 1), 0.1, along=3)
        v, f, t = join(near, far)
        nv, nf, _, _ = split.cut(v, f, t, (0, 0, 0.4), (0, 0, 1), radius=0.3)
        height = nv[nf][:, :, 2] - 0.4
        spans = (height.max(axis=1) > 1e-9) & (height.min(axis=1) < -1e-9)
        self.assertTrue(spans.any())
        self.assertTrue(np.all(nv[nf][spans][:, :, 0] > 0.5))  # only the far tube is left spanning the plane

    def test_a_cut_stops_at_its_bounds(self):
        v, f, t = tube((0, 0, 0), (0, 0, 1), 0.1, along=3)
        nv, nf, _, _ = split.cut(v, f, t, (0, 0, 0.4), (0, 0, 1), bounds=[(np.zeros(3), np.array([1.0, 0, 0]))])  # where x <= 0
        made = nv[len(v):]
        self.assertTrue(len(made) and np.all(made[:, 0] <= 1e-9))
        height = nv[nf][:, :, 2] - 0.4
        spans = (height.max(axis=1) > 1e-9) & (height.min(axis=1) < -1e-9)
        self.assertTrue(spans.any())
        self.assertTrue(np.all(nv[nf][spans][:, :, 0].max(axis=1) > -1e-9))  # what still spans the plane reaches past the bound
        on = split.on_cut(nv, np.array([0, 0, 0.4]), np.array([0, 0, 1.0]), 1.0, [(np.zeros(3), np.array([1.0, 0, 0]))])
        self.assertEqual(int(on.sum()), len(made))

    def test_faces_at_the_rim_of_a_cut_agree_on_their_shared_edge(self):
        v, f, t = tube((0, 0, 0), (0, 0, 1), 0.1, along=3)
        nv, nf, _, origin = split.cut(v, f, t, (0.1, 0, 0.4), (0, 0, 1), radius=0.1)  # reaches a third of the way round

        def open_edges(faces):
            return int((mesh_ops.edges(faces)[1] == 1).sum())
        self.assertGreater(len(nv), len(v))
        pieces = np.bincount(origin)
        self.assertTrue({1, 2, 3} <= set(pieces.tolist()))  # whole, split on one edge, split on both
        self.assertTrue(np.all((normals(v, f)[origin] * normals(nv, nf)).sum(axis=1) > 0))  # winding kept
        height = nv[nf][:, :, 2] - 0.4
        self.assertTrue(np.any((height.max(axis=1) > 1e-9) & (height.min(axis=1) < -1e-9)))  # the far side is left whole
        self.assertEqual(open_edges(nf), open_edges(f))  # a vertex left on a whole edge would open that edge
        self.assertAlmostEqual(area(nv, nf), area(v, f), places=9)
        self.assertTrue(np.all(np.diff(origin) >= 0))

    def test_a_vertex_on_the_plane_is_not_duplicated(self):
        v = np.array([(0, 0, 0), (1, 0, 1), (1, 0, -1)], float)
        nv, nf, _, _ = split.cut(v, np.array([(0, 1, 2)]), v[:, [0, 2]], (0, 0, 0), (0, 0, 1))
        self.assertEqual((len(nv), len(nf)), (4, 2))


class CapTests(unittest.TestCase):
    """A tube of radius 0.1 along z, cut at z = 0.4; the under part is the piece above the cut."""
    RADIUS, DEPTH = 0.1, 0.08

    def setUp(self):
        self.point, self.normal = np.array((0.0, 0.0, 0.4)), np.array((0.0, 0.0, 1.0))
        v, f, t = tube((0, 0, 0), (0, 0, 1), self.RADIUS, along=3)
        self.v, f, self.t, _ = split.cut(v, f, t, self.point, self.normal)
        above = (self.v[f][:, :, 2] - 0.4).sum(axis=1) > 0
        self.under, self.over = f[above], f[~above]

    def cap(self, faces=None, limit=1.0):
        return split.cap(self.v, self.t, self.under if faces is None else faces, len(self.v), self.point, self.normal, self.DEPTH, limit)

    def test_a_cap_carries_the_rim_of_a_pad_round_the_hinge(self):
        centre = self.v[self.under].mean(axis=1)
        full, grown, steps = centre[:, 1] > 0.03, [], split.GUARD_STEPS  # the front of the tube is a pad
        hinge = np.cross((0.0, 1.0, 0.0), -self.normal)  # turns the front past the plane
        build = lambda **more: split.cap(self.v, self.t, self.under, len(self.v), self.point, self.normal, self.DEPTH, 1.0, steps=steps, **more)
        plain = build()
        points, uvs, faces = build(full=full, hinge=hinge, grown=grown)
        self.assertEqual((len(points), len(grown)), (len(plain[0]), len(faces)))
        self.assertTrue(np.array_equal(faces, plain[2]) and np.array_equal(uvs, plain[1]))
        every = np.concatenate([self.v, points])
        rim = np.abs(self.v[self.under][:, :, 2] - 0.4) < 1e-9  # each added face grew from a face with an edge on the plane
        self.assertTrue(np.all(rim[grown].sum(axis=1) == 2))
        count = len(points) // steps  # rim points
        moved = (np.linalg.norm(points - plain[0], axis=1) > 1e-9).reshape(steps, count)
        self.assertFalse(moved[-1].any())  # the pole stays
        self.assertTrue(moved[0].any() and not moved[0].all() and all(np.array_equal(row, moved[0]) for row in moved[:-1]))
        start = self.v[np.unique(self.under[rim.sum(axis=1) == 2][full[rim.sum(axis=1) == 2]])]
        start = start[np.abs(start[:, 2] - 0.4) < 1e-9] - self.point  # the pad's rim points
        self.assertEqual(len(start), int(moved[0].sum()))
        rings = (points - self.point).reshape(steps, count, 3)
        for k in range(steps - 1):
            turn = np.radians(split.GUARD_SWEEP) * (k + 1) / (steps - 1)
            ring = rings[k][moved[0]]
            self.assertTrue(np.allclose(np.sort(ring[:, 0]), np.sort(start[:, 0])))  # along the hinge it stays where it was
            self.assertTrue(np.allclose(np.sort(np.hypot(ring[:, 1], ring[:, 2])), np.sort((1 - split.GUARD_TUCK) * start[:, 1])))
            self.assertTrue(np.allclose(np.arctan2(-ring[:, 2], ring[:, 1]), turn))  # turned past the plane
        with self.assertRaises(ValueError):
            build(full=full)

    def test_a_tucked_cap_steps_in_from_its_rim_just_past_the_plane(self):
        plain = split.cap(self.v, self.t, self.under, len(self.v), self.point, self.normal, self.DEPTH, 1.0, steps=3)
        points, _, faces = split.cap(self.v, self.t, self.under, len(self.v), self.point, self.normal, self.DEPTH, 1.0, steps=4, tuck=0.1)
        count = len(points) // 4
        self.assertEqual((len(plain[0]) // 3, len(faces)), (count, 7 * count))
        rings = (points - self.point).reshape(4, count, 3)
        rim = np.linalg.norm((plain[0] - self.point).reshape(3, count, 3)[0][:, :2], axis=1) / (np.cos(np.pi / 6) * (1 - split.LEAN * 0.5))
        self.assertTrue(np.allclose(np.linalg.norm(rings[0][:, :2], axis=1), 0.9 * rim))  # a tenth of the way in
        self.assertTrue(np.allclose(rings[0][:, 2], -split.TUCK_RISE * self.DEPTH))  # and hardly past the plane
        self.assertTrue(np.allclose(rings[1:], 0.9 * (plain[0] - self.point).reshape(3, count, 3) * (1, 1, 1 / 0.9)))  # then the dome, as much narrower

    def test_a_cap_is_joined_to_the_rim_and_lies_inside_its_dome(self):
        points, uvs, faces = self.cap()
        rim = int((np.abs(self.v[np.unique(self.under)][:, 2] - 0.4) < 1e-9).sum())
        # two faces per rim edge between rings and one at the pole, where the cap closes
        self.assertEqual((len(points), len(uvs), len(faces)), (split.CAP_STEPS * rim, split.CAP_STEPS * rim, (2 * split.CAP_STEPS - 1) * rim))
        height = points[:, 2] - 0.4
        self.assertAlmostEqual(height.min(), -self.DEPTH, places=9)
        np.testing.assert_allclose(points[-rim:], [[0, 0, 0.4 - self.DEPTH]] * rim, atol=1e-12)  # the pole, once per rim point
        self.assertTrue(np.all((np.linalg.norm(points[:, :2], axis=1) / self.RADIUS) ** 2 + (height / self.DEPTH) ** 2 < 1.0 + 1e-9))
        self.assertTrue(np.all(np.linalg.norm(normals(np.concatenate([self.v, points]), faces), axis=1) > 0))  # no face without area
        whole_v, whole_f = np.concatenate([self.v, points]), np.concatenate([self.under, faces])
        pairs, count = mesh_ops.edges(whole_f)
        self.assertFalse(np.any((count == 1) & (np.abs(whole_v[pairs][:, :, 2] - 0.4) < 1e-9).all(axis=1)))  # no open edge on the plane
        self.assertTrue(np.all((normals(whole_v, faces) * (whole_v[faces].mean(axis=1) - self.point)).sum(axis=1) > 0))  # facing outward

    def test_a_cap_turned_about_the_joint_stays_inside_a_sleeve_as_wide_as_the_rim(self):
        relative = self.cap()[0] - self.point
        axis = np.array((1.0, 0.0, 0.0))
        for degrees in (20, 45, 90, 135):
            a = np.radians(degrees)
            turned = relative * np.cos(a) + np.cross(axis, relative) * np.sin(a) + axis * (relative @ axis)[:, None] * (1 - np.cos(a))
            inside_sleeve = turned[turned[:, 2] < 0]  # the over part's sleeve runs down from the plane
            self.assertTrue(len(inside_sleeve))
            self.assertLessEqual(np.linalg.norm(inside_sleeve[:, :2], axis=1).max(), self.RADIUS + 1e-9, degrees)

    def test_a_cap_is_nowhere_deeper_than_its_rim_point_is_far_from_the_joint(self):
        self.v = self.v * (0.4, 1.0, 1.0)  # an oval rim: 0.04 from the centre on its narrow sides, less than the depth
        points = self.cap()[0]
        rim = np.unique(self.under)
        rim = rim[np.abs(self.v[rim, 2] - 0.4) < 1e-9]
        reach = np.linalg.norm(self.v[rim] - self.point, axis=1)
        self.assertLess(reach.min(), self.DEPTH)
        rings = points.reshape(split.CAP_STEPS, len(rim), 3) - self.point  # ring by ring, in the rim's order
        self.assertTrue(np.all(np.linalg.norm(rings, axis=2) <= reach + 1e-9))  # so no turn about the joint takes a point farther out
        ring = -rings[-2][:, 2] / np.sin(np.radians(split.CAP_TOP * (split.CAP_STEPS - 1) / split.CAP_STEPS))
        self.assertTrue(np.allclose(ring, np.minimum(self.DEPTH, reach)))  # each rim point's own depth
        self.assertTrue(np.allclose(-rings[-1][:, 2], reach.min()))  # the pole: the least of them

    def test_a_cap_not_bounded_runs_the_whole_depth_from_every_rim_point(self):
        self.v = self.v * (0.4, 1.0, 1.0)  # an oval rim: narrower on two sides than the depth
        points = split.cap(self.v, self.t, self.under, len(self.v), self.point, self.normal, self.DEPTH, 1.0, bounded=False)[0]
        rim = np.unique(self.under)
        rim = rim[np.abs(self.v[rim, 2] - 0.4) < 1e-9]
        rings = points.reshape(split.CAP_STEPS, len(rim), 3) - self.point
        ring = -rings[-2][:, 2] / np.sin(np.radians(split.CAP_TOP * (split.CAP_STEPS - 1) / split.CAP_STEPS))
        self.assertTrue(np.allclose(ring, self.DEPTH) and np.allclose(-rings[-1][:, 2], self.DEPTH))

    def test_a_cap_grows_only_from_under_side_faces_within_the_planes_reach(self):
        self.assertEqual(len(self.cap(faces=self.over)[2]), 0)
        self.assertEqual(len(self.cap(limit=0.01)[2]), 0)
        self.assertEqual(len(self.cap(faces=np.concatenate([self.under, self.over]))[2]), 0)  # an edge inside the part is no rim


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.v, self.f, self.t = figure()

    def test_every_part_is_cut_out_and_the_surface_is_kept(self):
        made, origins = {}, {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, made=made, origins=origins)
        for name, (points, faces, _) in parts.items():  # the face of the outfit each face of a part was cut from
            own = made[name] == split.OWN
            self.assertEqual(len(origins[name]), len(faces))
            self.assertTrue(np.array_equal(origins[name] >= 0, own))
            source = self.v[self.f[origins[name][own]]]
            reach = np.linalg.norm(source - source.mean(axis=1, keepdims=True), axis=2).max(axis=1)
            self.assertTrue((np.linalg.norm(points[faces[own]].mean(axis=1) - source.mean(axis=1), axis=1) <= reach + 1e-9).all())
        self.assertEqual(set(parts), TOKENS)
        self.assertAlmostEqual(sum(area(p, f[made[name] == split.OWN]) for name, (p, f, _) in parts.items()), area(self.v, self.f), places=6)
        added = {name for name in parts if (made[name] != split.OWN).any()}
        self.assertEqual(added, {'pelvis'})  # open on both hip planes, where the thighs do not always stand: closed there
        regions = split.regions(JOINTS, RADII)
        for name, (points, faces, uvs) in parts.items():
            self.assertEqual(len(points), len(uvs))
            centres = points[faces].mean(axis=1)
            for point, normal, sign, limit in regions[name]['planes']:
                if name in ('chest', 'pelvis') and abs(point[0]) > 1e-9:
                    continue  # a limb plane only grazes the trunk: it does not cut a piece off, so the trunk keeps it
                relative = centres - point
                height = relative @ normal
                near = np.linalg.norm(relative - height[:, None] * normal, axis=1) <= limit
                self.assertTrue(np.all(sign * height[near] >= -1e-6), name)

    def test_a_hand_beside_the_thigh_stays_a_hand(self):
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII)
        self.assertLess(parts['handl'][0][:, 0].max(), -0.3)
        self.assertGreater(parts['legl'][0][:, 0].min(), -0.25)
        self.assertGreater(parts['pelvis'][0][:, 2].min(), 0.94)
        # the shoulder and elbow planes run on through the lower torso, which is still chest
        self.assertTrue(np.all(np.abs(parts['forel'][0][:, 0]) > 0.2))
        chest = parts['chest'][0]
        self.assertAlmostEqual(chest[:, 2].min(), 1.2, places=6)
        self.assertTrue(np.any((chest[:, 0] < -0.12) & (chest[:, 2] < 1.3)))

    def test_a_boot_wider_than_the_ankles_reach_is_cut_with_a_longer_reach(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        wide = 0.12  # the ankle plane reaches 1.35 x 0.055 m: a boot this wide is not cut through
        boot = tube(J['lshin_g'], J['lfoot_g'] - (0, 0, 0.1), wide)
        keep = [tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(J['lthigh_g'] + (0, 0, 0.06), J['lshin_g'], 0.08), boot]
        v, f, t = join(*keep)
        short = split.split(v, f, t, JOINTS, RADII)
        self.assertNotIn('footl', short)
        self.assertLess(short['shinl'][0][:, 2].min(), 0.05)
        parts = split.split(v, f, t, JOINTS, RADII, reaches={('ankle', 'l'): 0.15})
        ankle = J['lfoot_g'][2]
        self.assertLess(parts['footl'][0][:, 2].max(), ankle + 0.01)
        self.assertGreater(parts['shinl'][0][:, 2].min(), ankle - 0.01)
        # the boot's surface is kept (the shin also takes a sliver of the thigh's end at the knee)
        self.assertAlmostEqual(area(*parts['footl'][:2]) + area(*parts['shinl'][:2]), area(*boot[:2]), places=3)
        self.assertEqual(split.limits(RADII, reaches={('ankle', 'l'): 0.15})[('ankle', 'r')], split.REACH * RADII[('ankle', 'r')])
        for bad in ({('ankle', 'l'): 0.0}, {('ankle', 'x'): 0.1}):
            with self.assertRaises(ValueError):
                split.split(v, f, t, JOINTS, RADII, reaches=bad)

    def test_a_shape_hook_moves_each_part_before_its_cap_grows_and_deep_joints_cap_the_whole_overlap(self):
        overlaps = {('elbow', side): 0.09 for side in 'lr'}  # deeper than the forearm is wide (5 cm)
        calls, made = [], {}

        def shape(name, vertices, faces, uvs, origin):
            calls.append((name, len(origin), len(faces)))
            if name != 'forel':
                return vertices, uvs
            moved = np.array(vertices, float)
            used = np.unique(faces)
            moved[used, 1] += 0.01  # the forearm a centimetre forward
            return moved, uvs

        point, normal = split.planes({k: np.array(p, float) for k, p in JOINTS.items()})[('elbow', 'l')]
        depth = lambda parts, name: -((parts[name][0] - point) @ normal).min()
        plain = split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps)
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps, made=made, shape=shape, deep=('elbow',))
        self.assertEqual(sorted(call[0] for call in calls), sorted(parts))
        self.assertTrue(all(own <= count for _, own, count in calls))  # the part's own faces first, then what closes it
        self.assertLess(depth(plain, 'forel'), 0.05 + 1e-6)  # bounded: no deeper than the rim is wide
        self.assertAlmostEqual(depth(parts, 'forel'), 0.09, places=6)
        def rim(found, kinds):  # the y of the cap's rim on the plane, and of the rest of it
            cap = found['forel'][0][np.unique(found['forel'][1][kinds == split.CAP])]
            on = np.abs((cap - point) @ normal) < 1e-9
            return cap[on, 1].mean(), cap[~on, 1].mean()
        first = {}
        split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps, made=first, deep=('elbow',))
        before, after = rim(split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps, deep=('elbow',)), first['forel']), rim(parts, made['forel'])
        self.assertAlmostEqual(after[0] - before[0], 0.01, places=6)  # grown from the moved rim
        self.assertTrue(0.0 < after[1] - before[1] < 0.01)  # and drawn in to the joint's axis, which did not move
        self.assertTrue(np.allclose(parts['forer'][0][:, 1].mean(), plain['forer'][0][:, 1].mean()))

    def test_a_joint_left_whole_keeps_its_surface_on_the_part_beside_it(self):
        made = {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, {('neck', 'c'): 0.03}, whole={('neck', 'c')}, made=made)
        self.assertEqual(set(parts), TOKENS - {'neck'})
        self.assertAlmostEqual(parts['chest'][0][:, 2].max(), 1.70, places=6)  # the collar, above the neck plane at 1.65
        self.assertAlmostEqual(sum(area(p, f[made[name] == split.OWN]) for name, (p, f, _) in parts.items()), area(self.v, self.f), places=6)
        self.assertFalse(any((kinds == split.CAP).any() for kinds in made.values()))  # and no cap
        with self.assertRaises(ValueError):
            split.split(self.v, self.f, self.t, JOINTS, RADII, whole={('hip', 'l')})

    def test_reaches_are_found_where_the_outfit_is_bulkier_than_its_tier(self):
        # tubes as thick as their joints need none; the figure's torso hangs round the hip joints like a coat, which counts
        self.assertLessEqual(set(split.reaches(self.v, self.f, JOINTS, RADII)), {('hip', 'l'), ('hip', 'r')})
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        boot = tube(J['lshin_g'], J['lfoot_g'] - (0, 0, 0.1), 0.12)
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(J['lthigh_g'] + (0, 0, 0.06), J['lshin_g'], 0.08), boot)
        found = split.reaches(v, f, JOINTS, RADII)
        self.assertEqual(set(found) - {('hip', 'l'), ('hip', 'r')}, {('ankle', 'l')})  # the knee plane lies on the boot's open top
        self.assertTrue(0.12 < found[('ankle', 'l')] < 0.14)
        self.assertIn('footl', split.split(v, f, t, JOINTS, RADII, reaches={key: found[key] for key in found if key[0] != 'hip'}))

    def test_limbs_that_touch_are_not_mixed(self):
        joints = {**JOINTS, 'lforearm_g': (-0.14, 0, 1.28), 'lhand_g': (-0.145, 0, 1.03)}  # the left arm hangs onto the thigh
        for side, x in (('l', -0.06), ('r', 0.06)):  # and the legs stand closer than they are thick
            joints.update({side + 'thigh_g': (x, 0, 1.0), side + 'shin_g': (x, 0, 0.55), side + 'foot_g': (x, 0, 0.12)})
        J = {name: np.array(p, float) for name, p in joints.items()}
        legs = [tube(J[s + 'thigh_g'] + (0, 0, 0.06), J[s + 'foot_g'] - (0, 0, 0.1), 0.07) for s in 'lr']
        arm = tube(J['lforearm_g'], (-0.15, 0, 0.9), 0.04)
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), *legs, arm)
        parts = split.split(v, f, t, joints, RADII)
        for left, right in (('legl', 'legr'), ('shinl', 'shinr'), ('footl', 'footr')):
            self.assertLessEqual(parts[left][0][:, 0].max(), 0.011, left)
            self.assertGreaterEqual(parts[right][0][:, 0].min(), -0.011, right)
            self.assertAlmostEqual(area(*parts[left][:2]), area(*parts[right][:2]), delta=1e-3)
        self.assertNotIn('handr', parts)
        self.assertAlmostEqual(area(*parts['handl'][:2]), 2 * np.pi * 0.04 * 0.13, delta=0.004)  # the whole hand, though it lies in the thigh
        self.assertLess(parts['handl'][0][:, 2].max(), 1.05)

    def test_legs_joined_at_the_crotch_are_still_two_legs(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        legs = [tube(J[s + 'thigh_g'] + (0, 0, 0.06), J[s + 'foot_g'] - (0, 0, 0.1), 0.08, around=12, along=24) for s in 'lr']
        (lv, lf, lt), (rv, rf, rt) = legs
        # a bridge between the inner sides of the two legs, below both hip planes, sharing their vertices' positions
        inner_l = [i for i in range(len(lv)) if 0.86 < lv[i, 2] < 0.95 and lv[i, 0] > lv[:, 0].max() - 0.03 and abs(lv[i, 1]) < 1e-6]
        inner_r = [i for i in range(len(rv)) if 0.86 < rv[i, 2] < 0.95 and rv[i, 0] < rv[:, 0].min() + 0.03 and abs(rv[i, 1]) < 1e-6]
        self.assertEqual((len(inner_l), len(inner_r)), (2, 2))
        (a, b), (c, d) = sorted(inner_l, key=lambda i: lv[i, 2]), sorted(inner_r, key=lambda i: rv[i, 2])
        bridge = (np.array([lv[a], lv[b], rv[c], rv[d]]), np.array([(0, 2, 3), (0, 3, 1)]), np.zeros((4, 2)))
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), *legs, bridge)
        parts = split.split(v, f, t, JOINTS, RADII)
        self.assertAlmostEqual(area(*parts['legl'][:2]), area(*parts['legr'][:2]), delta=1e-3)
        self.assertLessEqual(parts['legl'][0][:, 0].max(), 1e-6)
        self.assertGreaterEqual(parts['legr'][0][:, 0].min(), -1e-6)

    def test_two_limbs_welded_at_a_point_are_not_handed_to_one_side(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        legs = [tube(J[s + 'thigh_g'], J[s + 'shin_g'] + (0, 0, 0.05), 0.07, around=12, along=8) for s in 'lr']
        # two faces far below the crotch that share an edge and reach one vertex of each leg: a weld, not a seam
        (lv, _, _), (rv, _, _) = legs
        a, b = lv[np.argmax(lv[:, 0] - 10 * abs(lv[:, 2] - 0.7))], rv[np.argmin(rv[:, 0] + 10 * abs(rv[:, 2] - 0.7))]
        middle = (a + b) / 2
        link = (np.array([a, middle + (0, 0.01, 0), middle - (0, 0.01, 0), b]), np.array([(0, 1, 2), (3, 2, 1)]), np.zeros((4, 2)))
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), *legs, link)
        parts = split.split(v, f, t, JOINTS, RADII)
        self.assertAlmostEqual(area(*parts['legl'][:2]), area(*parts['legr'][:2]), delta=2e-3)
        self.assertLess(parts['legl'][0][:, 0].mean(), -0.1)
        self.assertGreater(parts['legr'][0][:, 0].mean(), 0.1)

    def test_two_limbs_that_are_one_surface_off_the_cuts_are_refused(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        (lv, lf, lt), (rv, rf, rt) = [tube(J[s + 'thigh_g'], J[s + 'shin_g'] + (0, 0, 0.05), 0.07, around=12, along=8) for s in 'lr']
        # a strip from the left leg's inner side to the right leg's, far below the crotch, on the legs' own vertices
        a = sorted(np.argsort(lv[:, 0] - 10 * abs(lv[:, 2] - 0.7))[-2:], key=lambda i: lv[i, 2])
        b = sorted(len(lv) + np.argsort(-rv[:, 0] - 10 * abs(rv[:, 2] - 0.7))[-2:], key=lambda i: rv[i - len(lv), 2])
        legs = (np.concatenate([lv, rv]), np.concatenate([lf, rf + len(lv), [(a[0], b[0], b[1]), (a[0], b[1], a[1])]]), np.concatenate([lt, rt]))
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), legs)
        with self.assertRaisesRegex(ValueError, 'one surface that no cut parts'):
            split.split(v, f, t, JOINTS, RADII)

    def test_an_overlap_gives_only_the_under_part_a_cap_past_the_plane(self):
        key, depth = ('elbow', 'l'), 0.04
        plain = split.split(self.v, self.f, self.t, JOINTS, RADII)
        capped = split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps={key: depth})
        point, normal = split.planes(JOINTS)[key]
        normal = seams.unit(normal)
        for name in TOKENS - {'forel'}:
            self.assertAlmostEqual(area(*capped[name][:2]), area(*plain[name][:2]), places=9, msg=name)
        points, faces, uvs = capped['forel']
        self.assertEqual(len(points), len(uvs))
        self.assertGreater(len(faces), len(plain['forel'][1]))
        self.assertGreaterEqual(((plain['forel'][0] - point) @ normal).min(), -1e-6)
        deepest = -((points - point) @ normal).min()  # the cap's pole: the overlap deep, or as deep as its nearest rim point is far
        self.assertTrue(0.9 * depth < deepest <= depth + 1e-9, deepest)

    def test_inputs_are_checked(self):
        with self.assertRaisesRegex(ValueError, 'every joint and side'):
            split.split(self.v, self.f, self.t, JOINTS, {('waist', 'c'): 0.2})
        with self.assertRaisesRegex(ValueError, 'One texture coordinate per vertex'):
            split.split(self.v, self.f, self.t[:-1], JOINTS, RADII)
        with self.assertRaisesRegex(ValueError, 'no faces'):
            split.split(self.v, np.zeros((0, 3), int), self.t, JOINTS, RADII)
        self.assertEqual(set(split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps={('elbow', 'l'): None})), TOKENS)  # no cap
        for overlaps in ({('elbow', 'c'): 0.04}, {('elbow', 'l'): -0.04}):
            with self.assertRaisesRegex(ValueError, 'Overlaps are depths'):
                split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps=overlaps)
        y_up = {name: (x, z, -y) for name, (x, y, z) in JOINTS.items()}
        with self.assertRaisesRegex(ValueError, 'z up and face \\+y'):
            split.split(self.v, self.f, self.t, y_up, RADII)

    def test_a_face_without_area_does_not_send_the_mesh_through_a_second_trace(self):
        v, f, t = join((self.v, self.f, self.t), (np.full((3, 3), 5.0), np.array([(0, 1, 2)]), np.zeros((3, 2))))
        calls = []
        traced = split.pieces
        split.pieces = lambda *args, **kwargs: calls.append(kwargs) or traced(*args, **kwargs)
        self.addCleanup(setattr, split, 'pieces', traced)
        split.split(v, f, t, JOINTS, RADII)
        self.assertEqual(calls, [{}])


def fused(armpit=1.44, depth=0.05, half=0.045, flare=0.0, panel=0.0):
    """A flat torso and left arm that are one surface down to the armpit, as a generated outfit's are.

    Its outline is extruded front to back: above the armpit one strip from the arm's outer side to the torso's
    right side, below it an arm strip and a torso strip, with the underside of the web between them. Vertices
    are shared, as in a real mesh. With `flare`, the sleeve is that much wider on each side near the elbow, as
    under an elbow guard. With `panel`, the torso stands that much farther out front and back, and above the
    armpit so does everything from 1 cm inside the arm's middle on: a vest whose edge lies beside the arm.
    (Its ledge under that edge at the armpit is left open.)"""
    arm = lambda z: -0.2 - (1.55 - z) * 0.1 / 0.27  # the arm's middle, through the shoulder and elbow joints
    levels = np.linspace(1.60, 1.00, 31)
    wide = lambda z: half + (flare if z < 1.37 else 0.0)
    deep = depth + panel
    index, points, faces = {}, [], []

    def vertex(x, y, z):
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in index:
            index[key] = len(points); points.append(key)
        return index[key]

    def quad(a, b, c, d):
        corners = [vertex(*p) for p in (a, b, c, d)]
        faces.extend([(corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])])

    def columns(z, joined):
        """The outline's strips at one height: (from, to, how far out front and back)."""
        if not joined:
            return [(arm(z) - wide(z), arm(z) + wide(z), depth), (-0.15, 0.15, deep)]
        inner = min(arm(z) + wide(z), -0.16)
        sleeve = [(arm(z) - wide(z), arm(z) + 0.01, depth), (arm(z) + 0.01, inner, deep)] if panel else [(arm(z) - wide(z), inner, depth)]
        return sleeve + [(inner, -0.15, deep), (-0.15, 0.15, deep)]

    for top, bottom in zip(levels[:-1], levels[1:]):
        joined = (top + bottom) / 2 > armpit
        for (a0, b0, out), (a1, b1, _) in zip(columns(top, joined), columns(bottom, joined)):
            for y in (out, -out):  # front and back
                quad((a0, y, top), (b0, y, top), (b1, y, bottom), (a1, y, bottom))
        walls = [([columns(z, joined)[0][0] for z in (top, bottom)], depth), ([0.15, 0.15], deep)]
        if not joined:  # the arm's inner side and the torso's left side
            walls += [([arm(z) + wide(z) for z in (top, bottom)], depth), ([-0.15, -0.15], deep)]
        for (x0, x1), out in walls:
            quad((x0, out, top), (x0, -out, top), (x1, -out, bottom), (x1, out, bottom))
        if joined and panel:  # the vest's edge beside the arm, front and back
            x0, x1 = arm(top) + 0.01, arm(bottom) + 0.01
            for sign in (1, -1):
                quad((x0, sign * depth, top), (x0, sign * deep, top), (x1, sign * deep, bottom), (x1, sign * depth, bottom))
    for a, b, out in columns(1.60, True):  # the top, and the underside of the web at the armpit
        quad((a, out, 1.60), (b, out, 1.60), (b, -out, 1.60), (a, -out, 1.60))
    z = levels[np.argmin(np.abs(levels - armpit))]
    quad((arm(z) + wide(z), deep, z), (-0.15, deep, z), (-0.15, -deep, z), (arm(z) + wide(z), -deep, z))
    return np.array(points), np.array(faces), np.zeros((len(points), 2))


def open_edges(faces, points=None):
    """The edges on one face only, as pairs of vertex numbers; with `points`, vertices at one position are one
    (a closing has a vertex per point of its line at its middle), each numbered as the first of them."""
    if points is not None:
        weld = mesh_ops.weld_ids(points, 1e-6)
        first = np.full(int(weld.max()) + 1, len(weld))
        np.minimum.at(first, weld, np.arange(len(weld)))
        faces = first[weld][faces]
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    edges, count = np.unique(edges, axis=0, return_counts=True)
    return edges[count == 1]


class SleeveTests(unittest.TestCase):
    def setUp(self):
        self.v, self.f, self.t = fused()
        self.planes = split.planes(JOINTS)
        shoulder, elbow = (np.array(JOINTS[name], float) for name in ('lbicep_g', 'lforearm_g'))
        self.arm = shoulder, seams.unit(elbow - shoulder)  # the shoulder joint and the way the upper arm runs

    def on(self, points, key):
        point, normal = self.planes[key]
        return np.abs((points - point) @ seams.unit(normal)) < 1e-6

    def test_a_sleeve_fused_with_the_torso_is_found_and_an_arm_of_its_own_is_not(self):
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        self.assertGreater(seam['normal'][0], 0.9)  # it faces the torso
        self.assertTrue(0.09 < seam['depth'] < 0.15, seam['depth'])  # the armpit, down the arm from the shoulder plane
        inside = (np.array([-0.2 + 0.045, 0, 1.55]) - seam['point']) @ seam['normal']
        self.assertTrue(-0.02 < inside < 0.02, inside)  # at the sleeve's inner side
        self.assertIsNone(split.sleeve(self.v, self.f, JOINTS, 'r'))  # there is no right arm
        self.assertIsNone(split.sleeve(*figure()[:2], JOINTS, 'l'))  # tubes: the arm is its own surface

    def test_a_shoulder_joint_just_outside_the_outfit_still_finds_its_sleeve(self):
        shoulder, axis = self.arm
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        # an outfit's joint is an estimate: 9 cm back along the arm it stands above the shoulder's surface
        out = split.sleeve(self.v, self.f, {**JOINTS, 'lbicep_g': tuple(shoulder - 0.09 * axis)}, 'l')
        self.assertAlmostEqual(out['depth'], seam['depth'] + 0.09, delta=0.011)
        self.assertIsNone(split.sleeve(self.v, self.f, {**JOINTS, 'lbicep_g': tuple(shoulder - 0.2 * axis)}, 'l'))  # too far out to be this arm's

    def test_the_sleeve_is_cut_off_along_the_arm_and_both_openings_are_closed(self):
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII)
        self.assertLessEqual({'chest', 'bicepl', 'forel', 'pelvis'}, set(parts))  # the figure's arm ends at the wrist
        sleeve, sleeve_faces, _ = parts['bicepl']
        self.assertGreater(area(sleeve, sleeve_faces), 0.05)
        past = ((sleeve - seam['point']) @ seam['normal']).max()  # only its closing, rounded out toward the chest
        self.assertGreater(past, 0.01)
        loose = open_edges(sleeve_faces, sleeve)
        self.assertTrue(len(loose))
        for key in (('shoulder', 'l'), ('elbow', 'l')):  # its only open edges are its two joint rims
            loose = loose[~self.on(sleeve[loose], key).all(axis=1)]
        self.assertEqual(len(loose), 0)
        chest, chest_faces, _ = parts['chest']
        loose = open_edges(chest_faces, chest)
        for key in (('shoulder', 'l'), ('waist', 'c')):
            loose = loose[~self.on(chest[loose], key).all(axis=1)]
        self.assertEqual(len(loose), 0)
        # the chest's closing lies flat on the seam and faces the sleeve
        side = (chest - seam['point']) @ seam['normal']
        on_seam = np.abs(side)[chest_faces].max(axis=1) < 1e-6
        self.assertTrue(on_seam.any())
        self.assertTrue(np.all(normals(chest, chest_faces)[on_seam] @ seam['normal'] < 0))
        # the sleeve's is rounded out toward the chest: everything past the seam is the closing, and it faces that way
        side = (sleeve - seam['point']) @ seam['normal']
        closing = side[sleeve_faces].max(axis=1) > 1e-6
        self.assertGreater(np.count_nonzero(closing), 2 * np.count_nonzero(on_seam))  # a ring and the middle, not one fan
        self.assertTrue(np.all(normals(sleeve, sleeve_faces)[closing] @ seam['normal'] > -1e-9))
        # it is rounded toward the ball about the shoulder joint that the opening's two ends on the shoulder plane
        # lie on: it reaches that ball in the middle and nowhere leaves it, however far down the arm the seam runs
        point, normal = self.planes[('shoulder', 'l')]
        ends = sleeve[(np.abs(side) < 1e-6) & self.on(sleeve, ('shoulder', 'l'))]
        ball = np.linalg.norm(ends - point, axis=1).max()
        self.assertTrue(np.allclose(np.linalg.norm(ends - point, axis=1), ball, atol=1e-6))
        reach = np.linalg.norm(sleeve[side > 1e-6] - point, axis=1)
        self.assertAlmostEqual(reach.max(), ball, places=6)
        self.assertTrue(self.on(sleeve[side > 1e-6][[np.argmax(reach)]], ('shoulder', 'l')).all())  # the rim on the plane

    def test_a_sleeve_wider_at_the_elbow_is_still_cut_at_the_armpit(self):
        # under an elbow guard the sleeve reaches 3 cm nearer the torso than at the armpit
        v, f, t = fused(flare=0.03)
        seam = split.sleeve(v, f, JOINTS, 'l')
        inside = (np.array([-0.2 + 0.045, 0, 1.55]) - seam['point']) @ seam['normal']
        self.assertTrue(-0.01 < inside < 0.0, inside)  # just inside the sleeve as it is at the armpit, not at the guard
        reaches = split.reaches(v, f, JOINTS, RADII)  # the elbow plane has to reach across the guard
        sleeve, faces, _ = split.split(v, f, t, JOINTS, RADII, reaches=reaches)['bicepl']
        side = (sleeve - seam['point']) @ seam['normal']
        guard = (side > 0.02) & (sleeve[:, 2] < 1.36)  # the seam cut through the guard: both sides stay the sleeve's
        self.assertTrue(guard.any())
        loose = open_edges(faces, sleeve)
        for key in (('shoulder', 'l'), ('elbow', 'l')):
            loose = loose[~self.on(sleeve[loose], key).all(axis=1)]
        self.assertEqual(len(loose), 0)  # and nothing is left open there

    def test_the_sleeves_cap_grows_from_its_closed_rim(self):
        plain = split.split(self.v, self.f, self.t, JOINTS, RADII)['bicepl']
        capped = split.split(self.v, self.f, self.t, JOINTS, RADII, {('shoulder', 'l'): 0.05})['bicepl']
        point, normal = self.planes[('shoulder', 'l')]
        self.assertGreater(len(capped[1]), len(plain[1]))
        self.assertLess(((capped[0] - point) @ seams.unit(normal)).min(), -0.02)  # past the plane, under the chest
        loose = open_edges(capped[1], capped[0])
        self.assertFalse(self.on(capped[0][loose], ('shoulder', 'l')).all(axis=1).any())  # the whole rim is taken up

    def test_the_sleeves_cap_starts_inside_its_rim(self):
        made = {}
        sleeve, faces, _ = split.split(self.v, self.f, self.t, JOINTS, RADII, {('shoulder', 'l'): 0.05}, made=made)['bicepl']
        point, normal = self.planes[('shoulder', 'l')]
        normal = seams.unit(normal)
        cap = np.setdiff1d(faces[made['bicepl'] == split.CAP], faces[made['bicepl'] != split.CAP])  # the cap's own vertices
        rim = np.intersect1d(faces[made['bicepl'] == split.CAP], faces[made['bicepl'] != split.CAP])
        across = lambda points: np.linalg.norm((points - point) - ((points - point) @ normal)[:, None] * normal, axis=1)
        past = -((sleeve[cap] - point) @ normal)
        first = cap[past < 2 * split.TUCK_RISE * 0.05]  # the ring the cap steps in on, hardly past the plane
        self.assertEqual(len(first), len(rim))
        self.assertTrue(np.allclose(np.sort(across(sleeve[first])), np.sort((1 - split.SHOULDER_TUCK) * across(sleeve[rim]))))
        self.assertLess(across(sleeve[cap]).max(), (1 - split.SHOULDER_TUCK) * across(sleeve[rim]).max() + 1e-9)  # and nowhere wider

    def test_the_split_tells_what_made_each_face(self):
        made = {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, {('shoulder', 'l'): 0.05}, made=made)
        self.assertEqual(set(made), set(parts))
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        point, normal = self.planes[('shoulder', 'l')]
        for name, (points, faces, _) in parts.items():
            self.assertEqual(len(made[name]), len(faces), name)
        sleeve, faces, _ = parts['bicepl']
        kinds = made['bicepl']
        self.assertEqual(sorted(set(kinds.tolist())), [split.OWN, split.CLOSING, split.CAP])
        past_seam = ((sleeve - seam['point']) @ seam['normal'])[faces].max(axis=1) > 1e-6  # only its rounded closing
        self.assertTrue(np.all(kinds[past_seam & (kinds != split.CAP)] == split.CLOSING))
        above = ((sleeve - point) @ seams.unit(normal))[faces].min(axis=1) < -1e-6  # only its cap, under the chest
        self.assertTrue(np.array_equal(above, kinds == split.CAP))
        self.assertEqual(sorted(set(made['chest'].tolist())), [split.OWN, split.CLOSING])  # an over part: closed, no cap

    def test_walls_stand_in_front_of_the_sleeve_and_behind_it(self):
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        front, back = seam['walls']
        self.assertTrue(np.allclose(front['normal'], -back['normal']))  # they face apart
        for wall in (front, back):
            self.assertTrue(np.allclose(np.abs(wall['normal']), [0, 1, 0]))  # across the seam, along the arm
            self.assertAlmostEqual(wall['point'] @ wall['normal'], 0.05 + split.SLEEVE_WALL, places=6)  # just outside the sleeve
            (stop, facing), past = wall['bounds']  # and it ends a little past the seam
            self.assertTrue(np.allclose(facing, seam['normal']))
            self.assertAlmostEqual((stop - seam['point']) @ seam['normal'], split.OVERRUN, places=6)
        for stop, facing in seam['bounds'][:2]:  # as the seam ends a little past each wall
            self.assertAlmostEqual(stop @ facing, 0.05 + split.SLEEVE_WALL + split.OVERRUN, places=6)
        # along the arm all three reach well above the shoulder joint, where the shoulder plane has to cross them
        # wherever the body's joint stands, and stop a little past the elbow
        start, end = (np.asarray(JOINTS['l' + name], float) for name in ('bicep_g', 'forearm_g'))
        axis = seams.unit(end - start)
        for plane in (seam, front, back):
            top = (plane['point'] - start) @ axis - np.sqrt(plane['radius'] ** 2 - min(plane['radius'], np.linalg.norm(
                (plane['point'] - start) - ((plane['point'] - start) @ axis) * axis)) ** 2)
            self.assertLessEqual(top, -3 * split.SLEEVE_STEP + 1e-9)
            stop, facing = plane['bounds'][-1]
            self.assertTrue(np.allclose(facing, axis))
            self.assertAlmostEqual((stop - end) @ axis, 3 * split.SLEEVE_STEP, places=6)

    def test_what_the_torso_wears_beside_the_arm_stays_on_the_torso(self):
        # a vest standing 4 cm out in front of the arm and behind it, its edge 1 cm inside the arm's middle: on
        # the arm's side of the seam, and one surface with the sleeve
        v, f, t = fused(panel=0.04)
        seam = split.sleeve(v, f, JOINTS, 'l')
        parts = split.split(v, f, t, JOINTS, RADII)
        self.assertLess(np.abs(parts['bicepl'][0][:, 1]).max(), 0.05 + split.SLEEVE_WALL + 1e-6)  # the sleeve ends at its walls
        chest = parts['chest'][0]
        beside = (np.abs(chest[:, 1]) > 0.08) & ((chest - seam['point']) @ seam['normal'] < -0.01) & (chest[:, 2] < 1.54)
        self.assertTrue(beside.any())  # the vest's edge beside the arm, under the shoulder plane, is the chest's
        self.assertGreater(area(*parts['bicepl'][:2]), 0.05)

    def test_an_opening_that_turns_a_corner_is_closed_as_one_surface(self):
        # what a trough leaves of a square sleeve: its outer side x = -1, its back y = -1 and a floor, open on the
        # seam x = 0 and on the front wall y = 0.5, from the joint plane z = 1 down, round the corner and up again
        corners = [(-1, 0.5), (-1, -1), (0, -1), (0, 0.5)]
        v = np.array([(x, y, z) for z in (1.0, 0.0) for x, y in corners], float)  # 0 to 3 at the top, 4 to 7 on the floor
        f = np.array([[0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2], [4, 7, 6], [4, 6, 5]])
        t = np.arange(16, dtype=float).reshape(8, 2)
        seam = {'point': np.array([0.0, 0, 0.5]), 'normal': np.array([1.0, 0, 0]), 'radius': 5.0,
                'walls': [{'point': np.array([-0.5, 0.5, 0.5]), 'normal': np.array([0.0, 1, 0]), 'radius': 5.0}]}
        for facing in (1.0, -1.0):
            new_v, new_t, new_f = split.seam_fill(v, t, f, len(v), seam, facing)
            both = np.concatenate([v, new_v])
            # one line of four edges: down the seam, along the floor on it, along the floor on the wall, up the wall
            self.assertEqual(len(new_f), 4)
            np.testing.assert_allclose(new_v, [[-0.5, -0.25, 1.0]] * 5)  # its middle, between its two ends
            self.assertTrue(np.all(facing * (normals(both, new_f) @ np.array([1.0, 1, 0])) > 0))  # away from the sleeve, or into it
            place = lambda number: tuple(np.round(both[number], 6))
            runs = [(place(a), place(b)) for face in new_f.tolist() for a, b in zip(face, face[1:] + face[:1]) if place(a) != place(b)]
            self.assertEqual(len(runs), len(set(runs)))  # one surface: no edge is run twice the same way

    def test_a_line_through_a_vertex_repeated_at_a_texture_seam_is_closed_with_one_fan(self):
        # two faces hang from the cut x = 0; its line runs down and up again through a point both faces hold a
        # vertex of their own at, with unlike texture coordinates (numbers 1 and 3)
        v = np.array([[0, 0, 0], [0, 1, -1], [0, 2, 0], [0, 1, -1], [-1, 0.5, -0.5], [-1, 1.5, -0.5]], float)
        t = np.array([[0, 0], [0.4, 0], [1, 0], [0.6, 0], [0.2, 1], [0.8, 1]], float)
        f = np.array([[0, 1, 4], [3, 2, 5]])
        seam = {'point': np.array([0.0, 1, 0]), 'normal': np.array([1.0, 0, 0]), 'radius': 5.0}
        new_v, new_t, new_f = split.seam_fill(v, t, f, len(v), seam, 1.0)
        # one middle, between the line's two ends, held once per vertex of the line with that vertex's coordinates
        np.testing.assert_allclose(new_v, [[0, 1, 0]] * 4)
        np.testing.assert_allclose(new_t, t[:4])
        self.assertEqual(len(new_f), 2)
        for face, own in zip(sorted(sorted(face) for face in new_f.tolist()), ([0, 1], [2, 3])):
            self.assertEqual(face[:2], own)  # each face's own vertices of the line
            self.assertIn(face[2] - len(v), own)  # and the middle that belongs to one of them
        both = np.concatenate([v, new_v])
        self.assertAlmostEqual(area(both, new_f), 1.0, places=6)  # the whole triangle under the hub, no sliver
        self.assertTrue(np.all(normals(both, new_f) @ seam['normal'] > 0.99))

    def test_a_sleeve_its_cuts_leave_joined_to_the_torso_is_refused(self):
        v, f, t, _, sleeves = split.troughs(self.v, self.f, self.t, JOINTS)
        split.split(v, f, t, JOINTS, RADII, sleeves=sleeves)  # parted: the sleeve goes with the arm
        sleeves['l']['on'] = np.zeros_like(sleeves['l']['on'])  # as if the cuts had stopped short: sleeve and torso are one piece
        with self.assertRaises(ValueError) as refused:
            split.split(v, f, t, JOINTS, RADII, sleeves=sleeves)
        self.assertIn('stays joined to the torso', str(refused.exception))

    def test_a_shoulder_is_measured_only_where_the_arm_is_a_surface_of_its_own(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        inside = J['lbicep_g'] + 0.06 * seams.unit(J['lbicep_g'] - J['lforearm_g'])
        v, f, _ = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(inside, J['lforearm_g'], 0.11))  # a bulky sleeve
        found = split.reaches(v, f, JOINTS, RADII)
        self.assertTrue(0.11 < found[('shoulder', 'l')] < 0.14, found)
        self.assertNotIn(('shoulder', 'l'), split.reaches(self.v, self.f, JOINTS, RADII))  # fused: the seam sets it

    def own(self, mesh, faces, uvs, **more):
        """Per part, the area of the outfit's own faces and of its closings."""
        made = {}
        parts = split.split(mesh, faces, uvs, JOINTS, RADII, made=made, **more)
        return {name: tuple(round(area(points, part[made[name] == kind]), 6) for kind in (split.OWN, split.CLOSING))
                for name, (points, part, _) in parts.items()}

    def test_a_sleeve_cut_in_the_pose_the_outfit_came_in_is_parted_there(self):
        v, f, t, origin, sleeves = split.troughs(self.v, self.f, self.t, JOINTS)
        self.assertEqual(set(sleeves), {'l'})  # there is no right arm
        self.assertTrue(np.array_equal(v[:len(self.v)], self.v))  # the vertices given, then those on the cuts
        self.assertGreater(len(v), len(self.v))
        self.assertTrue(np.array_equal(np.unique(origin), np.arange(len(self.f))))
        self.assertEqual(sleeves['l']['on'].shape, (4, len(v)))  # the seam, the two walls and a pad's outline
        self.assertEqual(sleeves['l']['inside'].shape, (len(f),))
        seam = split.sleeve(self.v, self.f, JOINTS, 'l')
        on_seam = v[sleeves['l']['on'][0]]
        self.assertTrue(len(on_seam) and np.allclose((on_seam - seam['point']) @ seam['normal'], 0.0, atol=1e-9))
        self.assertTrue(np.all((v[f[sleeves['l']['inside']]].mean(axis=1) - seam['point']) @ seam['normal'] < 0))  # the arm's side
        # the trough is taken from a little above the shoulder joint down; without materials no pad is looked for
        start, axis = self.arm
        along = (v[f].mean(axis=1) - start) @ axis
        self.assertGreater(along[sleeves['l']['inside']].min(), -split.SLEEVE_ABOVE - 1e-9)
        self.assertFalse(sleeves['l']['on'][3].any() or sleeves['l']['pad'].any())
        # the torso has vertices of its own along the cuts, where the sleeve's are, and the trough's faces use none
        own = sleeves['l']['torso']
        self.assertEqual(own.shape, (len(v),))
        self.assertTrue(own.any() and not own[:len(self.v)].any())
        self.assertTrue(sleeves['l']['on'][:, own].any(axis=0).all())
        arm_side = v[sleeves['l']['on'].any(axis=0) & ~own]
        self.assertLess(np.abs(v[own][:, None] - arm_side[None]).sum(axis=2).min(axis=1).max(), 1e-9)
        self.assertFalse(own[f[sleeves['l']['inside'] & (along >= 0)]].any())  # from the shoulder joint down it is the arm's
        # nothing has moved since: the parts are those `split` finds and cuts by itself
        self.assertEqual(self.own(v, f, t, sleeves=sleeves), self.own(self.v, self.f, self.t))
        self.assertNotIn(('shoulder', 'l'), split.reaches(v, f, JOINTS, RADII, sleeves=sleeves))
        self.assertIn(('shoulder', 'l'), split.reaches(v, f, JOINTS, RADII, sleeves={}))  # told that no sleeve is fused
        with self.assertRaises(ValueError):  # flags for another mesh
            split.split(self.v, self.f, self.t, JOINTS, RADII, sleeves=sleeves)

    def patch(self, reach=0.085, outer=False):
        """A material per face: 1 within `reach` of the left shoulder joint (with `outer`, only on the arm's outer side), else 0."""
        away = self.v[self.f].mean(axis=1) - self.arm[0]
        return ((np.linalg.norm(away, axis=1) < reach) & (not outer or away[:, 0] < -0.02)).astype(int)

    def test_a_shoulder_pad_is_the_patch_of_one_material_over_the_shoulder_joint(self):
        for outer in (False, True):
            materials = self.patch(outer=outer)
            self.assertTrue(np.array_equal(split.pad(self.v, self.f, materials, JOINTS, 'l'), materials == 1))
        materials = self.patch()
        self.assertIsNone(split.pad(self.v, self.f, materials, JOINTS, 'r'))  # there is no right arm
        self.assertIsNone(split.pad(self.v, self.f, np.zeros(len(self.f), int), JOINTS, 'l'))  # one material: the sleeve itself
        length = np.linalg.norm(np.array(JOINTS['lforearm_g']) - np.array(JOINTS['lbicep_g']))
        self.assertIsNone(split.pad(self.v, self.f, self.patch(reach=1.1 * split.PAD_REACH * length), JOINTS, 'l'))  # too far down the arm
        # a face in the pad read as another material is the pad's; a patch as large as a quarter of it is not
        centre = self.v[self.f].mean(axis=1) - self.arm[0]
        inner = np.flatnonzero(materials == 1)[np.argmin(np.where(np.abs(centre[materials == 1, 1]) > 0.04, np.linalg.norm(centre[materials == 1], axis=1), 9.0))]
        spotted = materials.copy(); spotted[inner] = 2
        self.assertTrue(np.array_equal(split.pad(self.v, self.f, spotted, JOINTS, 'l'), materials == 1))
        halved = np.where((materials == 1) & (centre[:, 1] < -0.04), 2, materials)  # its rear face is of another material
        found = split.pad(self.v, self.f, halved, JOINTS, 'l')
        self.assertTrue(found is not None and found.sum() < (materials == 1).sum() and not found[halved == 2].any())
        with self.assertRaises(ValueError):
            split.pad(self.v, self.f, materials[:-1], JOINTS, 'l')

    def test_a_shoulder_pad_is_cut_out_along_its_outline_and_goes_to_a_shoulder_part(self):
        plain = self.own(self.v, self.f, self.t)
        for outer in (False, True):  # a pad all round the shoulder, and one on the arm's outer side alone
            materials = self.patch(outer=outer)
            v, f, t, origin, sleeves = split.troughs(self.v, self.f, self.t, JOINTS, materials)
            found = sleeves['l']
            self.assertTrue(np.array_equal(found['pad'], (materials == 1)[origin]))
            self.assertAlmostEqual(area(v, f[found['pad']]), area(self.v, self.f[materials == 1]), places=9)
            # the outline: the points both a face of the pad and another face hold
            weld = mesh_ops.weld_ids(v, 1e-6)
            held = [np.isin(weld, weld[f[chosen]]) for chosen in (found['pad'], ~found['pad'])]
            self.assertTrue(found['on'][3].any() and np.array_equal(found['on'][3], held[0] & held[1]))
            # it stays one edge through the bend: only on the trough has the torso vertices of its own
            self.assertFalse((found['torso'] & ~found['on'][:3].any(axis=0)).any())
            made = {}
            parts = split.split(v, f, t, JOINTS, RADII, made=made, sleeves=sleeves)
            self.assertEqual(set(parts) - set(plain), {'shol'})
            padded = {name: tuple(round(area(points, part[made[name] == kind]), 6) for kind in (split.OWN, split.CLOSING))
                      for name, (points, part, _) in parts.items()}
            # the pad goes whole to the shoulder part, from both sides of the shoulder plane, and nothing else does
            self.assertAlmostEqual(padded['shol'][0], area(self.v, self.f[materials == 1]), places=6)
            self.assertLess(padded['chest'][0], plain['chest'][0])
            self.assertLess(padded['bicepl'][0], plain['bicepl'][0])
            self.assertAlmostEqual(padded['chest'][0] + padded['bicepl'][0] + padded['shol'][0], plain['chest'][0] + plain['bicepl'][0], places=5)
            self.assertEqual({name: found for name, found in padded.items() if name not in ('chest', 'bicepl', 'shol')},
                             {name: found for name, found in plain.items() if name not in ('chest', 'bicepl')})
            # it is closed underneath, across its own outline; the chest and the upper arm are closed where it lay
            pad, faces, _ = parts['shol']
            self.assertEqual(len(open_edges(faces, pad)), 0)
            self.assertGreater(padded['chest'][1], plain['chest'][1])
            self.assertGreater(padded['bicepl'][1], plain['bicepl'][1])
            # the chest's closing there is the shoulder under the pad: rounded out from the shoulder plane, toward
            # the arm, and nowhere farther from the joint than the pad's outline on that plane
            chest, faces, _ = parts['chest']
            point, normal = self.planes[('shoulder', 'l')]
            closing = chest[np.unique(faces[made['chest'] == split.CLOSING])]
            above = closing[(closing - point) @ seams.unit(normal) < -1e-6]
            edge = v[found['on'][3]]
            self.assertTrue(len(above))
            self.assertLess(np.linalg.norm(above - self.arm[0], axis=1).max(), np.linalg.norm(edge - self.arm[0], axis=1).max() + 1e-6)
            # and nothing is left open on the shoulder plane, where the lifted arm no longer fills the chest's opening
            unit = seams.unit(normal)
            on = np.abs((chest - point) @ unit) < 1e-6
            left = [edge for edge in open_edges(faces, chest).tolist() if on[edge].all()]
            self.assertEqual(left, [])
        with self.assertRaises(ValueError):  # flags for another mesh
            split.split(self.v, self.f, self.t, JOINTS, RADII, sleeves=sleeves)

    def test_what_a_part_has_open_on_a_joint_plane_is_closed_facing_out_of_it(self):
        # a square tube standing on the plane z = 0, open at both ends, its faces outward
        ring = np.array([(1, 1), (-1, 1), (-1, -1), (1, -1)], float)
        v = np.concatenate([np.c_[ring, np.zeros(4)], np.c_[ring, np.ones(4)]])
        f = np.array([face for a in range(4) for b in [(a + 1) % 4] for face in ((a, b, b + 4), (a, b + 4, a + 4))])
        t = np.arange(16.0).reshape(8, 2)
        point, normal = np.zeros(3), np.array([0.0, 0, -1])
        more_v, more_t, more_f = split.lid(v, t, f, len(v), point, normal, 2.0)
        self.assertEqual((len(more_v), len(more_f)), (4, 4))
        self.assertTrue(np.allclose(more_v, 0.0))  # the middle of the opening, once per edge
        whole_v, whole_f = np.concatenate([v, more_v]), np.concatenate([f, more_f])
        self.assertTrue(all((whole_v[edge][:, 2] == 1).all() for edge in open_edges(whole_f, whole_v).tolist()))  # only the far end is open
        corners = whole_v[more_f]
        facing = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        self.assertTrue(np.allclose(facing / np.linalg.norm(facing, axis=1, keepdims=True), (0, 0, -1)))  # out of the tube
        self.assertTrue(np.array_equal(more_t, t[more_f[:, 1]]))  # drawn in what the part shows along that edge
        self.assertTrue((more_f[:, 2] >= len(v)).all() and (more_f[:, :2] < 4).all())
        # vertices repeated along the opening are one point of it
        twice = np.concatenate([v, v[:1]]); again = f.copy(); again[0, 0] = 8
        self.assertEqual(len(split.lid(twice, np.concatenate([t, t[:1]]), again, 9, point, normal, 2.0)[2]), 4)
        # a line that does not come round (the tube without one wall) is closed straight from its end to its start
        more_v, _, more_f = split.lid(v, t, f[:6], len(v), point, normal, 2.0)
        self.assertEqual((len(more_v), len(more_f)), (4, 4))
        self.assertTrue(np.allclose(more_v, 0.0))
        corners = np.concatenate([v, more_v])[more_f]
        facing = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        self.assertTrue(np.allclose(facing / np.linalg.norm(facing, axis=1, keepdims=True), (0, 0, -1)))
        self.assertAlmostEqual(float(np.linalg.norm(facing, axis=1).sum() / 2), 4.0)  # the whole square
        # nothing within reach, nothing on the plane, or nothing open there: nothing is added
        for given in ((v, f, 1.0), (v + (0, 0, 0.5), f, 2.0), (whole_v, whole_f, 2.0)):
            points, faces, limit = given
            added = split.lid(points, np.zeros((len(points), 2)), faces, len(points), point, normal, limit)
            self.assertEqual([len(part) for part in added], [0, 0, 0])
            self.assertEqual(added[1].shape[1], 2)

    def test_an_outfit_designed_with_a_pad_that_shows_none_is_refused(self):
        materials = self.patch()
        self.assertTrue(split.troughs(self.v, self.f, self.t, JOINTS, materials, padded='l')[4]['l']['pad'].any())
        for given, sides in ((np.zeros(len(self.f), int), 'l'),  # a pad of the sleeve's own material cannot be told
                             (materials, 'lr'),  # there is no right arm
                             (None, 'l'),  # nothing to tell a pad by
                             (materials, 'x')):
            with self.assertRaises(ValueError):
                split.troughs(self.v, self.f, self.t, JOINTS, given, padded=sides)
        v, f, t = figure()  # arms that are surfaces of their own: a pad on one is not cut out, so one expected there is refused
        patch = (np.linalg.norm(v[f].mean(axis=1) - self.arm[0], axis=1) < 0.085).astype(int)
        self.assertEqual(split.troughs(v, f, t, JOINTS, patch)[4], {})
        with self.assertRaises(ValueError):
            split.troughs(v, f, t, JOINTS, patch, padded='l')

    def test_under_a_shoulder_pad_the_walls_are_measured_right_under_the_armpit(self):
        # the shoulder stands 3 cm farther out front and back than the arm does under the armpit
        v = self.v.copy()
        wide = (v[:, 2] > 1.5) & (v[:, 0] < -0.21)
        v[wide, 1] += 0.03 * np.sign(v[wide, 1])
        start, axis = self.arm
        other = np.array(JOINTS['rbicep_g'], float) - start
        across = np.cross(axis, seams.unit(other - (other @ axis) * axis))
        stand = lambda seam: sorted(float((wall['point'] - start) @ across) for wall in seam['walls'])
        whole, padded = split.sleeve(v, self.f, JOINTS, 'l'), split.sleeve(v, self.f, JOINTS, 'l', padded=True)
        self.assertAlmostEqual(stand(whole)[1] - stand(whole)[0], 2 * (0.05 + 0.03 + split.SLEEVE_WALL), places=6)
        self.assertAlmostEqual(stand(padded)[1] - stand(padded)[0], 2 * (0.05 + split.SLEEVE_WALL), places=6)
        self.assertAlmostEqual(padded['point'] @ padded['normal'] - start @ padded['normal'], whole['point'] @ whole['normal'] - start @ whole['normal'], places=9)  # the seam stands where it stood

    def test_a_flank_pressed_into_the_sleeve_after_the_cut_stays_the_torsos(self):
        v, f, t, _, sleeves = split.troughs(self.v, self.f, self.t, JOINTS)
        came = self.own(v, f, t, sleeves=sleeves)
        # the bend and the fit: the torso's side under the armpit now stands 1.4 cm inside the sleeve's inner side
        flank = (np.abs(v[:, 0] + 0.15) < 1e-9) & (v[:, 2] < 1.43) & (v[:, 2] > 1.2)
        self.assertTrue(flank.any())
        pressed = v.copy(); pressed[flank, 0] = -0.21
        carried = self.own(pressed, f, t, sleeves=sleeves)
        self.assertEqual(carried['bicepl'], came['bicepl'])  # the sleeve is what it was, and so are both closings
        self.assertEqual(carried['chest'][1], came['chest'][1])
        self.assertGreater(carried['chest'][0], came['chest'][0] + 0.02)  # the wider flank is all the chest's
        # found and cut where it stands now, the trough takes a slab of the flank with the sleeve
        here = self.own(pressed, f, t)
        self.assertGreater(here['bicepl'][0], came['bicepl'][0] + 0.005)
        self.assertLess(here['chest'][0], carried['chest'][0] - 0.005)

    def test_a_sleeve_fused_down_to_the_elbow_is_refused(self):
        v, f, _ = fused(armpit=1.10)
        with self.assertRaises(ValueError):
            split.sleeve(v, f, JOINTS, 'l')


def trousers(crotch=0.93, depth=0.06, half=0.07):
    """Flat trousers that are one surface down to the crotch, below both hip planes, with shared vertices."""
    leg = lambda z: 0.12 + (1.0 - z) * 0.02 / 0.45  # a leg's middle, through the hip and knee joints
    levels = np.linspace(1.30, 0.60, 36)
    index, points, faces = {}, [], []

    def vertex(x, y, z):
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in index:
            index[key] = len(points); points.append(key)
        return index[key]

    def quad(a, b, c, d):
        corners = [vertex(*p) for p in (a, b, c, d)]
        faces.extend([(corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])])

    def columns(z, joined):
        inner, outer = leg(z) - half, leg(z) + half
        return [(-outer, -inner), (-inner, inner), (inner, outer)] if joined else [(-outer, -inner), (inner, outer)]

    for top, bottom in zip(levels[:-1], levels[1:]):
        joined = (top + bottom) / 2 > crotch
        for (a0, b0), (a1, b1) in zip(columns(top, joined), columns(bottom, joined)):
            for y in (depth, -depth):
                quad((a0, y, top), (b0, y, top), (b1, y, bottom), (a1, y, bottom))
        walls = [[sign * (leg(z) + half) for z in (top, bottom)] for sign in (-1, 1)]
        if not joined:
            walls += [[sign * (leg(z) - half) for z in (top, bottom)] for sign in (-1, 1)]
        for x0, x1 in walls:
            quad((x0, depth, top), (x0, -depth, top), (x1, -depth, bottom), (x1, depth, bottom))
    z = levels[np.argmin(np.abs(levels - crotch))]
    quad((-(leg(z) - half), depth, z), (leg(z) - half, depth, z), (leg(z) - half, -depth, z), (-(leg(z) - half), -depth, z))
    return np.array(points), np.array(faces), np.zeros((len(points), 2))


class CrotchTests(unittest.TestCase):
    REACHES = {('hip', 'l'): 0.2, ('hip', 'r'): 0.2}  # bulky trousers: the hip planes reach past the middle

    def setUp(self):
        self.v, self.f, self.t = trousers()
        self.planes = split.planes(JOINTS)

    def on(self, points, key):
        point, normal = self.planes[key]
        return np.abs((points - point) @ seams.unit(normal)) < 1e-6

    def test_thighs_fused_above_the_crotch_are_closed_toward_each_other(self):
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, reaches=self.REACHES)
        for name, side, facing in (('legl', 'l', 1.0), ('legr', 'r', -1.0)):
            points, faces, _ = parts[name]
            # nothing passes the middle: the closing lies flat on it, against the other leg's (rounded out, it
            # comes through the other leg's cloth at the crotch)
            self.assertLess((facing * points[:, 0]).max(), 1e-6, name)
            loose = open_edges(faces, points)
            loose = loose[points[loose][:, :, 2].min(axis=1) > 0.6 + 1e-6]  # the trouser leg's own end
            loose = loose[~self.on(points[loose], ('hip', side)).all(axis=1)]  # and its rim on the hip plane are open
            self.assertEqual(len(loose), 0, name)
            closing = np.abs(points[:, 0])[faces].max(axis=1) < 1e-6  # the faces on the middle
            self.assertTrue(closing.any(), name)
            self.assertTrue(np.all(facing * normals(points, faces)[closing][:, 0] > -1e-9), name)  # facing the other leg

    def test_the_pelvis_is_closed_on_both_hip_planes(self):
        made = {}
        points, faces, _ = split.split(self.v, self.f, self.t, JOINTS, RADII, reaches=self.REACHES, made=made)['pelvis']
        kinds = made['pelvis']
        self.assertEqual(sorted(set(kinds.tolist())), [split.OWN, split.CLOSING, split.GUSSET])
        mine = faces[kinds != split.GUSSET]
        loose = open_edges(mine, points)
        for side in 'lr':  # nothing is left open on either plane, the triangle between the two lids included
            self.assertFalse(self.on(points[loose], ('hip', side)).all(axis=1).any(), side)
            self.assertTrue(((kinds == split.CLOSING) & self.on(points, ('hip', side))[faces].all(axis=1)).any(), side)
        whole = split.split(self.v, self.f, self.t, JOINTS, RADII, reaches=self.REACHES)
        self.assertEqual(len(whole['pelvis'][1]), len(faces))  # the same parts whether or not it is asked what made them

    def test_the_pelvis_repeats_the_crotch_under_the_thighs(self):
        made = {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, reaches=self.REACHES, made=made)
        points, faces, _ = parts['pelvis']
        strip = faces[made['pelvis'] == split.GUSSET]
        used = points[np.unique(strip)]
        self.assertLessEqual(np.abs(used[:, 0]).max(), split.GUSSET_WIDTH + 1e-9)
        self.assertGreater(used[:, 2].min(), 0.93 - split.GUSSET_BELOW)  # down to the crotch, which is as low as the cut's line goes
        flat = used[used[:, 2] > 0.93 + 0.03]  # above the corner at the crotch: the front and the back, 0.06 from the middle
        self.assertTrue(len(flat) and np.allclose(np.abs(np.abs(flat[:, 1]) - 0.06), split.GUSSET_UNDER))  # along their normals
        under = [((points - point) @ seams.unit(normal))[strip].min(axis=1) for point, normal in (self.planes[('hip', side)] for side in 'lr')]
        self.assertTrue(np.all(np.maximum(*under) > -split.GUSSET_UNDER - 1e-9))  # every face of it under a hip plane, where a thigh is
        self.assertTrue(all(split.GUSSET not in made[name] for name in parts if name != 'pelvis'))

    def test_the_surface_along_the_cut_between_the_legs_is_repeated_under_it(self):
        # the front of a pair of trousers: a sheet facing +y, 0.1 in front of the cut's point, with a column of vertices on the cut
        xs, zs = np.linspace(-0.2, 0.2, 9), np.linspace(0.0, -0.3, 7)
        v = np.array([(x, 0.1, z) for z in zs for x in xs])
        f = np.array([face for row in range(6) for col in range(8) for a in [row * 9 + col]
                      for face in ((a, a + 1, a + 9), (a + 1, a + 10, a + 9))])
        self.assertTrue(np.all(normals(v, f)[:, 1] > 0))
        t = v[:, [0, 2]] * 3.0
        seam = {'point': np.zeros(3), 'normal': np.array([1.0, 0, 0]), 'radius': 0.15, 'down': np.array([0, 0, -1.0])}
        more_v, more_t, more_f = split.gusset(v, t, f, 100, seam)
        # the cut's line reaches down to z = -0.10 (0.15 from its point, the sheet standing 0.1 in front of it)
        self.assertEqual(more_f.min(), 100)
        strip = more_f - 100
        corner = split.GUSSET_CORNER * split.GUSSET_WIDTH  # its two lower corners are cut off at 45 degrees
        self.assertAlmostEqual(area(more_v, strip), 2 * split.GUSSET_WIDTH * (0.10 + split.GUSSET_BELOW) - corner ** 2, places=9)
        self.assertTrue(np.allclose(more_v[:, 1], 0.1 - split.GUSSET_UNDER))  # under the surface it repeats
        self.assertTrue(np.all(normals(more_v, strip)[:, 1] > 0))  # and facing as it does
        self.assertTrue(np.allclose(more_t, more_v[:, [0, 2]] * 3.0))  # with its columns
        wide = split.gusset(v, t, f, 0, seam, width=0.1, below=0.05)
        self.assertAlmostEqual(area(wide[0], wide[2]), 0.2 * 0.15 - (split.GUSSET_CORNER * 0.1) ** 2, places=9)
        # legs nothing joins have no point on the cut, and no strip
        apart = v + (0.02, 0, 0)
        self.assertEqual([len(part) for part in split.gusset(apart, t, f, 0, seam)], [0, 0, 0])
        self.assertEqual(split.gusset(apart, t, f, 0, seam)[1].shape[1], 2)

    def test_the_cut_between_the_legs_holds_the_line_the_hip_planes_meet_in(self):
        # one hip joint half a millimetre higher: midway between the joints the two planes are that far apart
        joints = {**JOINTS, 'rthigh_g': tuple(np.add(JOINTS['rthigh_g'], [0, 0, 0.0005]))}
        *_, cuts, _, between, _ = split.assign(self.v, self.f, self.t, joints, RADII, reaches=self.REACHES)
        for side in 'lr':
            point, normal = cuts[('hip', side)]
            for along in (-0.1, 0.1):  # two points of the cut, front and back
                spot = between['point'] + along * np.cross(between['normal'], [0, 0, 1.0])
                spot = spot - ((spot - point) @ seams.unit(normal)) / seams.unit(normal)[2] * np.array([0, 0, 1.0])
                self.assertLess(abs((spot - between['point']) @ between['normal']), 1e-9)
        overlaps = {('hip', 'l'): 0.05, ('hip', 'r'): 0.05}
        parts = split.split(self.v, self.f, self.t, joints, RADII, overlaps, reaches=self.REACHES)
        for side in 'lr':  # so each thigh's cap takes up its whole rim
            points, faces, _ = parts['leg' + side]
            point, normal = cuts[('hip', side)]
            loose = open_edges(faces, points)
            self.assertFalse((np.abs((points[loose] - point) @ seams.unit(normal)) < 1e-6).all(axis=1).any(), side)
        uneven = {**JOINTS, 'rthigh_g': tuple(np.add(JOINTS['rthigh_g'], [0, 0, 0.004]))}
        with self.assertRaises(ValueError):  # the planes would meet 4 cm off the middle
            split.assign(self.v, self.f, self.t, uneven, RADII, reaches=self.REACHES)

    def test_a_hip_plane_reaches_over_its_own_leg_only(self):
        thin = {**RADII, ('hip', 'l'): 0.05, ('hip', 'r'): 0.05}  # trousers much bulkier than the tier
        found = split.reaches(self.v, self.f, JOINTS, thin)
        for side in 'lr':
            # to the leg's outer side (0.07 m from the joint) and just past the middle (0.12 m), not to the far leg's (0.31 m)
            self.assertTrue(0.12 < found[('hip', side)] < 0.2, found)

    def test_a_thighs_cap_grows_from_its_closed_rim(self):
        overlaps = {('hip', 'l'): 0.05}
        capped = split.split(self.v, self.f, self.t, JOINTS, RADII, overlaps, reaches=self.REACHES)['legl']
        point, normal = self.planes[('hip', 'l')]
        self.assertLess(((capped[0] - point) @ seams.unit(normal)).min(), -0.02)  # past the plane, under the pelvis
        loose = open_edges(capped[1], capped[0])
        self.assertFalse(self.on(capped[0][loose], ('hip', 'l')).all(axis=1).any())  # the whole rim is taken up


class SeatTests(unittest.TestCase):
    """The seat cut (`seat`): the body's pelvis reaches 9 cm past each hip plane, below the trousers' crotch."""
    REACHES = CrotchTests.REACHES
    REACH, RING, DEPTH = 0.09, 0.06, 0.05

    def setUp(self):
        self.v, self.f, self.t = trousers()
        self.planes = split.planes(JOINTS)
        self.overlaps = {('hip', side): self.DEPTH for side in 'lr'}
        self.seat = {('hip', side): {'reach': np.full(64, self.REACH), 'ring': np.full(16, self.RING)} for side in 'lr'}
        self.made = {}
        self.parts = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, reaches=self.REACHES, made=self.made, seat=self.seat)

    def past(self, points, side):
        point, normal = self.planes[('hip', side)]
        return (points - point) @ seams.unit(normal)

    def test_what_the_bodys_pelvis_covers_goes_to_the_pelvis(self):
        own = lambda parts, made, name: (parts[name][0], parts[name][1][made[name] == split.OWN])
        cut = {}
        plain = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, reaches=self.REACHES, made=cut)
        for side in 'lr':  # a thigh keeps the trousers past the line only
            points, faces = own(self.parts, self.made, 'leg' + side)
            self.assertGreater(self.past(points[faces], side).min(), self.REACH - 1e-6, side)
        points, faces = own(self.parts, self.made, 'pelvis')
        corners = points[faces]
        seat = (self.past(corners, 'l').max(axis=1) > 0.01) & (corners[:, :, 0].max(axis=1) < 0)
        self.assertTrue(seat.any())  # the seat and crotch past the left hip plane are the pelvis's
        self.assertLess(self.past(corners[seat], 'l').max(), self.REACH + 1e-6)
        # nothing of the trousers is lost or doubled: what the thighs gave up the pelvis took
        total = lambda parts, made: sum(area(*own(parts, made, name)) for name in ('pelvis', 'legl', 'legr'))
        self.assertAlmostEqual(total(self.parts, self.made), total(plain, cut), places=9)
        self.assertNotIn(split.GUSSET, self.made['pelvis'])  # legs nothing joins past the line: no strip between them

    def test_each_thigh_ends_inside_its_ring_and_the_pelvis_and_past_the_plane(self):
        for side in 'lr':
            points, faces, _ = self.parts['leg' + side]
            end = faces[self.made['leg' + side] == split.CAP]
            used = points[np.unique(end)]
            height = self.past(used, side)
            point, normal = self.planes[('hip', side)]
            relative = used - point
            radius = np.linalg.norm(relative - height[:, None] * seams.unit(normal), axis=1)
            self.assertTrue(np.all(radius[np.abs(height) < 1e-6] <= self.RING + 1e-9), side)  # inside its ring on the plane
            self.assertAlmostEqual(height.min(), -self.DEPTH, places=9)  # and its pole as deep past it as the overlap
            above = height < self.REACH - 1e-6  # all but its rim, which is the trousers'
            self.assertTrue(np.all(np.abs(used[above, 1]) <= 0.06 - split.SEAT_GAP + 1e-9), side)  # inside the seat's front and back
            loose = open_edges(faces, points)
            self.assertFalse((np.abs(self.past(points[loose], side) - self.REACH) < 1e-6).all(axis=1).any(), side)  # the rim is taken up
            # wound as the trousers it grows from (this fixture's are wound both ways): each edge of the rim runs
            # one way in the trousers and the other in the end
            directed = lambda chosen: {tuple(edge) for edge in np.concatenate([chosen[:, [0, 1]], chosen[:, [1, 2]], chosen[:, [2, 0]]]).tolist()}
            cloth, grown = directed(faces[self.made['leg' + side] == split.OWN]), directed(end)
            rim = {edge for edge in grown if edge[::-1] in cloth}
            self.assertTrue(rim and not rim & cloth and not {edge[::-1] for edge in rim} & grown, side)

    def test_the_end_stays_inside_the_seat_as_the_thigh_turns(self):
        point, normal = self.planes[('hip', 'l')]
        normal = seams.unit(normal)
        across = np.cross(normal, seams.unit(np.array((0.0, 1.0, 0.0)) - normal[1] * normal))

        def poking(bend):  # points of the left thigh's end that come out of the seat's front or back, turned forward and back
            made = {}
            seat = {key: {**entry, 'bend': bend} for key, entry in self.seat.items()}
            points, faces, _ = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, reaches=self.REACHES, made=made, seat=seat)['legl']
            used = points[np.unique(faces[made['legl'] == split.CAP])]
            used = used[np.abs((used - point) @ normal - self.REACH) > 1e-6]  # not its rim, which is the trousers'
            count = 0
            for degrees in (-60, -30, 30, 60):
                moved = point + (used - point) @ split.rotation(across, degrees).T
                height = (moved - point) @ normal
                count += int((np.abs(moved[(height > -0.25) & (height < self.REACH - 0.01), 1]) > 0.06 + 1e-9).sum())
            return count

        self.assertGreater(poking(0.0), 0)  # bounded as the body stands only, its sides come through the seat
        self.assertEqual(poking(60.0), 0)

    def test_the_pelvis_is_closed_across_each_leg_hole_and_not_on_the_planes(self):
        points, faces, _ = self.parts['pelvis']
        kinds = self.made['pelvis']
        loose = open_edges(faces, points)
        for side in 'lr':
            self.assertFalse((np.abs(self.past(points[loose], side) - self.REACH) < 1e-6).all(axis=1).any(), side)
            plane = np.abs(self.past(points, side)) < 1e-6
            self.assertFalse(((kinds == split.CLOSING) & plane[faces].all(axis=1)).any(), side)
        self.assertTrue((kinds == split.CLOSING).any())

    def test_a_line_through_the_crotch_cuts_both_thighs_alike_on_the_middle(self):
        # 5 cm past the planes the trousers are still one surface: the thighs' walls toward each other start there
        seat = {key: {**entry, 'reach': np.full(64, 0.05)} for key, entry in self.seat.items()}
        made = {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, reaches=self.REACHES, made=made, seat=seat)
        middle = lambda name: parts[name][0][np.unique(parts[name][1][made[name] == split.OWN])]
        on = [points[np.abs(points[:, 0]) < 1e-9] for points in (middle('pelvis'), middle('legl'), middle('legr'))]
        self.assertTrue(all(len(found) for found in on))
        low = [found[:, 2].min() for found in on[1:]]
        self.assertAlmostEqual(low[0], low[1], places=9)  # the two thighs leave the middle at one height
        self.assertTrue(all((made['leg' + side] == split.WALL).any() for side in 'lr'))
        self.assertEqual(sum(area(parts[name][0], parts[name][1][made[name] == split.OWN]) for name in ('pelvis', 'legl', 'legr')),
                         sum(area(self.parts[name][0], self.parts[name][1][self.made[name] == split.OWN]) for name in ('pelvis', 'legl', 'legr')))

    def test_a_cut_along_values_splits_where_they_change_sign(self):
        v = np.array([(0, 0, 0), (1, 0, 0), (0, 1, 0)], float)
        moved, faces, uvs, origin = split.cut(v, np.array([[0, 1, 2]]), v[:, :2], None, None, height=np.array([-1.0, 3.0, 1.0]))
        self.assertTrue(np.allclose(moved[3:], [(0.25, 0, 0), (0, 0.5, 0)]))
        self.assertEqual(len(faces), 3)
        self.assertTrue(np.array_equal(origin, [0, 0, 0]))
        with self.assertRaises(ValueError):
            split.cut(v, np.array([[0, 1, 2]]), v[:, :2], None, None, radius=0.1, height=np.zeros(3))


class ArmTests(unittest.TestCase):
    """The armhole cut (`arms`): the body's arm leaves its chest 6 cm past the shoulder plane toward the torso
    and 3 cm before it elsewhere, on a torso and sleeve that are one surface down to the armpit."""
    RING, DEPTH = 0.06, 0.05

    def setUp(self):
        self.v, self.f, self.t = fused()
        self.planes = split.planes(JOINTS)
        self.point, normal = self.planes[('shoulder', 'l')]
        self.normal = seams.unit(normal)
        turn = 2 * np.pi * np.arange(64) / 64
        self.line = np.where(np.cos(turn) > 0.5, 0.06, -0.03)  # direction 0 is +x, toward the torso
        self.overlaps = {('shoulder', 'l'): self.DEPTH}
        self.arms = {('shoulder', 'l'): {'line': self.line, 'ring': np.full(16, self.RING), 'bend': 0.0}}
        self.made = {}
        self.parts = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, made=self.made, arms=self.arms)

    def height(self, points):
        return (points - self.point) @ self.normal

    def on(self, points, key):
        point, normal = self.planes[key]
        return np.abs((points - point) @ seams.unit(normal)) < 1e-6

    def test_what_the_bodys_chest_covers_of_the_arm_goes_to_the_chest(self):
        points, faces, _ = self.parts['bicepl']
        used = points[np.unique(faces[self.made['bicepl'] == split.OWN])]
        a, b = seams.frame(self.normal)
        relative = used - self.point
        line = np.maximum(seams.around(self.line, np.arctan2(relative @ b, relative @ a)), split.ARM_FLOOR)
        self.assertGreater((self.height(used) - line).min(), -1e-3)  # the sleeve past the line only, read straight between directions
        self.assertGreater(self.height(used).min(), split.ARM_FLOOR - 1e-9)  # and never nearer the plane than the floor
        chest, chest_faces, _ = self.parts['chest']
        took = chest[np.unique(chest_faces[self.made['chest'] == split.OWN])]
        self.assertGreater(self.height(took[took[:, 0] < -0.16]).max(), 0.04)  # the sleeve's top toward the torso is the chest's
        # nothing of the outfit is lost or doubled
        plain = {}
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, made=plain)
        own = lambda parts, made: sum(area(parts[name][0], parts[name][1][made[name] == split.OWN]) for name in ('chest', 'bicepl'))
        self.assertAlmostEqual(own(self.parts, self.made), own(parts, plain), places=9)

    def test_the_upper_arm_has_one_end_inside_its_ring_and_past_the_plane(self):
        points, faces, _ = self.parts['bicepl']
        kinds = self.made['bicepl']
        self.assertNotIn(split.CLOSING, kinds)  # no closing along the sleeve's cuts: the end closes them all
        end = points[np.unique(faces[kinds == split.CAP])]
        height = self.height(end)
        radius = np.linalg.norm(end - self.point - height[:, None] * self.normal, axis=1)
        self.assertTrue(np.all(radius[np.abs(height) < 1e-9] <= self.RING + 1e-9))
        self.assertAlmostEqual(height.min(), -self.DEPTH, places=9)
        loose = open_edges(faces, points)
        self.assertTrue(len(loose))
        self.assertTrue(self.on(points[loose], ('elbow', 'l')).all())  # open at the elbow only

    def test_the_chest_is_closed_round_the_arm(self):
        points, faces, _ = self.parts['chest']
        loose = open_edges(faces, points)
        self.assertTrue(len(loose))
        self.assertTrue(self.on(points[loose], ('waist', 'c')).all())  # open at the waist only
        plain = split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps)['chest']
        loose = open_edges(plain[1], plain[0])
        self.assertTrue(self.on(plain[0][loose], ('shoulder', 'l')).all(axis=1).any())  # cut on the plane, it stood open there

    def test_an_arms_end_is_held_inside_what_it_turns_out_toward_and_not_across_the_torso(self):
        # an arm hanging down -z, its end 8 cm deep, and a wall of the over part 5.5 cm to its -x side above the joint
        normal, point = np.array((0.0, 0.0, -1.0)), np.zeros(3)
        v, f, t = tube((0, 0, -0.03), (0, 0, -0.2), 0.05, around=32, along=6)
        wall = np.array([(-0.055, -0.03, 0.0), (-0.055, 0.03, 0.0), (-0.055, 0.03, 0.15), (-0.055, -0.03, 0.15)]), np.array([(0, 1, 2), (0, 2, 3)])
        lean = np.cross(normal, (1.0, 0.0, 0.0))  # turned about this, the arm leans toward +x and its end toward the wall

        def through(out, degrees):  # points of the end, but its pole, in the wall once the arm leans
            grown, _, _ = split.seat_end(v, t, f, len(v), point, normal, (v - point) @ normal < 0.1, np.full(16, 0.06), 0.08, wall, 60.0,
                                         out=np.array(out))
            grown = grown[np.linalg.norm(grown[:, :2], axis=1) > 1e-9]
            moved = grown @ split.rotation(lean, degrees).T
            return int(((moved[:, 0] < -0.055) & (np.abs(moved[:, 1]) < 0.03) & (moved[:, 2] > 0)).sum())

        for degrees in (30, 60):
            self.assertEqual(through((1.0, 0.0, 0.0), degrees), 0)  # turned out, as far as the bend
            self.assertGreater(through((-1.0, 0.0, 0.0), degrees), 0)  # turned in across the torso: not held
        # the over part is read from its faces only: the split hands it the whole outfit's vertices, the limb's own among them
        grown = lambda over: split.seat_end(v, t, f, len(v), point, normal, (v - point) @ normal < 0.1, np.full(16, 0.06), 0.08, over, 60.0,
                                            out=np.array((1.0, 0.0, 0.0)))[0]
        stray = (np.concatenate([wall[0], v]), wall[1])  # the limb's vertices beside the wall's, no face of the wall using them
        self.assertTrue(np.array_equal(grown(stray), grown(wall)))

    def test_inputs_are_checked(self):
        with self.assertRaises(ValueError):
            split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, arms={('hip', 'l'): self.arms[('shoulder', 'l')]})
        with self.assertRaises(ValueError):
            split.split(self.v, self.f, self.t, JOINTS, RADII, self.overlaps, arms={('shoulder', 'l'): {'ring': np.full(16, self.RING)}})


def padded_leg(low=0.09, high=0.09):
    """A torso and a left leg that is one tube from hip to ankle, with a pad over the knee: (vertices, faces,
    uvs, materials). The pad is material 1 on the leg's front, `high` above the knee joint and `low` below it."""
    J = {name: np.array(p, float) for name, p in JOINTS.items()}
    v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(J['lthigh_g'] + (0, 0, 0.06), J['lfoot_g'] - (0, 0, 0.1), 0.07, around=16, along=58))
    centre = v[f].mean(axis=1) - J['lshin_g']
    pad = (centre[:, 2] < high) & (centre[:, 2] > -low) & (centre[:, 1] > 0.02) & (np.abs(centre[:, 0]) < 0.1)
    return v, f, t, pad.astype(int)


class KneeTests(unittest.TestCase):
    def setUp(self):
        self.v, self.f, self.t, self.materials = padded_leg()
        self.point, normal = split.planes(JOINTS)[('knee', 'l')]
        self.normal = seams.unit(normal)

    def test_a_knee_pad_is_the_patch_of_one_material_over_the_knee_joint(self):
        pad = split.guard(self.v, self.f, self.materials, JOINTS, 'knee', 'l')
        self.assertTrue(np.array_equal(pad, self.materials == 1))
        self.assertIsNone(split.guard(self.v, self.f, self.materials, JOINTS, 'knee', 'r'))  # no leg there
        self.assertIsNone(split.guard(self.v, self.f, np.zeros(len(self.f), int), JOINTS, 'knee', 'l'))  # the trousers reach farther
        v, f, _, guard = padded_leg(low=0.35)  # one patch with a guard down the shin is still the knee's pad
        self.assertTrue(np.array_equal(split.guard(v, f, guard, JOINTS, 'knee', 'l'), guard == 1))
        v, f, _, long = padded_leg(high=0.3)  # one that runs up the thigh is no pad
        self.assertIsNone(split.guard(v, f, long, JOINTS, 'knee', 'l'))
        small = (self.materials == 1) & (np.abs(self.v[self.f].mean(axis=1)[:, 2] - JOINTS['lshin_g'][2]) < 0.012)
        self.assertTrue(small.any())
        self.assertIsNone(split.guard(self.v, self.f, small.astype(int), JOINTS, 'knee', 'l'))  # a strap's end over the knee
        speck = self.materials.copy()
        inside = np.flatnonzero(self.materials == 1)
        middle = inside[np.argmin(np.linalg.norm(self.v[self.f[inside]].mean(axis=1) - (np.array(JOINTS['lshin_g']) + (0, 0.07, 0.04)), axis=1))]
        speck[middle] = 2  # a face read wrongly inside the pad is the pad's
        self.assertTrue(np.array_equal(split.guard(self.v, self.f, speck, JOINTS, 'knee', 'l'), self.materials == 1))
        with self.assertRaises(ValueError):
            split.guard(self.v, self.f, self.materials[:-1], JOINTS, 'knee', 'l')

    def test_a_knee_pad_is_cut_on_the_plane_and_the_shins_cap_carries_its_rim_round_the_knee(self):
        pad, depth = self.materials == 1, {('knee', 'l'): 0.04}
        height = lambda points: (points - self.point) @ self.normal  # past the plane on the shin's side
        was, made = {}, {}
        cut = split.split(self.v, self.f, self.t, JOINTS, RADII, depth, made=was)
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, depth, guards={('knee', 'l'): pad}, made=made)
        for name in parts:  # each half of the pad stays on its part: nothing but the shin's cap differs
            if name != 'shinl':
                self.assertEqual(len(parts[name][1]), len(cut[name][1]), name)
                self.assertTrue(np.array_equal(parts[name][0], cut[name][0]) and np.array_equal(made[name], was[name]), name)
        self.assertEqual(sorted(set(was['shinl'].tolist())), [split.OWN, split.CAP])
        self.assertEqual(sorted(set(made['shinl'].tolist())), [split.OWN, split.CAP, split.PADDED])
        self.assertEqual(int((made['shinl'] == split.OWN).sum()), int((was['shinl'] == split.OWN).sum()))
        self.assertEqual(int((made['shinl'] != split.OWN).sum()) * (2 * split.CAP_STEPS - 1), int((was['shinl'] != split.OWN).sum()) * (2 * split.GUARD_STEPS - 1))
        points, faces, _ = parts['shinl']
        self.assertAlmostEqual(-height(cut['shinl'][0]).min(), 0.04, places=6)  # a cap as deep as it was asked for
        reach = np.linalg.norm((self.v[self.f[pad]] - self.point)[np.abs(height(self.v[self.f[pad]])) < 0.01], axis=1).max()
        self.assertGreater(-height(points).min(), 0.9 * (1 - split.GUARD_TUCK) * reach)  # under a pad, as far past the plane as the pad is far out
        under = points[np.unique(faces[made['shinl'] == split.PADDED])] - self.point
        self.assertTrue(np.all(np.hypot(under[:, 1], under[:, 2]) < reach + 1e-6))  # carried round the hinge, across the leg
        self.assertGreater(under[:, 1].max(), 0.9 * reach)  # from the front of the knee
        self.assertAlmostEqual(under[:, 1].min(), (1 - split.GUARD_TUCK) * under[:, 1].max() * np.cos(np.radians(split.GUARD_SWEEP)), delta=0.003)
        for bad in ({('knee', 'l'): pad[:-1]}, {('knee', 'x'): pad}, {('hip', 'l'): pad}):
            with self.assertRaises(ValueError):
                split.split(self.v, self.f, self.t, JOINTS, RADII, guards=bad)

    def test_an_elbow_pad_is_found_behind_the_elbow_or_on_its_outer_side(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        inside = J['lbicep_g'] + 0.06 * seams.unit(J['lbicep_g'] - J['lforearm_g'])
        beyond = J['lhand_g'] + 0.10 * seams.unit(J['lhand_g'] - J['lforearm_g'])
        v, f, t = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(inside, beyond, 0.05, around=16, along=60))
        centre = v[f].mean(axis=1) - J['lforearm_g']
        behind = ((np.abs(centre[:, 2]) < 0.07) & (centre[:, 1] < -0.015) & (np.abs(centre[:, 0]) < 0.1)).astype(int)
        outside = ((np.abs(centre[:, 2]) < 0.07) & (centre[:, 0] < -0.015) & (np.abs(centre[:, 0]) < 0.1) & (np.abs(centre[:, 1]) < 0.035)).astype(int)
        for materials in (behind, outside):  # a pad behind the elbow, and one on its outer side only
            pad = split.guard(v, f, materials, JOINTS, 'elbow', 'l')
            self.assertTrue(np.array_equal(pad, materials == 1))
        self.assertIsNone(split.guard(v, f, np.zeros(len(f), int), JOINTS, 'elbow', 'l'))
        with self.assertRaises(ValueError):
            split.guard(v, f, behind, JOINTS, 'hip', 'l')
        pad, made = behind == 1, {}
        parts = split.split(v, f, t, JOINTS, RADII, {('elbow', 'l'): 0.03}, guards={('elbow', 'l'): pad}, made=made)
        self.assertEqual(sorted(set(made['forel'].tolist())), [split.OWN, split.CAP, split.PADDED])
        self.assertEqual(set(made['bicepl'].tolist()) - {split.CLOSING}, {split.OWN})  # the upper arm keeps its half as it was cut
        points, faces, _ = parts['forel']
        under = points[np.unique(faces[made['forel'] == split.PADDED])] - J['lforearm_g']
        self.assertTrue(under[:, 1].min() < -0.045 and under[:, 1].max() < 0.02)  # from behind the elbow, round its hinge
        self.assertAlmostEqual(sum(area(q, g[made[name] == split.OWN]) for name, (q, g, _) in parts.items()), area(v, f), places=6)

if __name__ == '__main__':
    unittest.main()
