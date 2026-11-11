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

    def test_a_cap_grows_only_from_under_side_faces_within_the_planes_reach(self):
        self.assertEqual(len(self.cap(faces=self.over)[2]), 0)
        self.assertEqual(len(self.cap(limit=0.01)[2]), 0)
        self.assertEqual(len(self.cap(faces=np.concatenate([self.under, self.over]))[2]), 0)  # an edge inside the part is no rim


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.v, self.f, self.t = figure()

    def test_every_part_is_cut_out_and_the_surface_is_kept(self):
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII)
        self.assertEqual(set(parts), TOKENS)
        self.assertAlmostEqual(sum(area(p, f) for p, f, _ in parts.values()), area(self.v, self.f), places=6)
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

    def test_a_joint_left_whole_keeps_its_surface_on_the_part_beside_it(self):
        parts = split.split(self.v, self.f, self.t, JOINTS, RADII, {('neck', 'c'): 0.03}, whole={('neck', 'c')})
        self.assertEqual(set(parts), TOKENS - {'neck'})
        self.assertAlmostEqual(parts['chest'][0][:, 2].max(), 1.70, places=6)  # the collar, above the neck plane at 1.65
        self.assertAlmostEqual(sum(area(p, f) for p, f, _ in parts.values()), area(self.v, self.f), places=6)  # and no cap
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


def fused(armpit=1.44, depth=0.05, half=0.045, flare=0.0):
    """A flat torso and left arm that are one surface down to the armpit, as a generated outfit's are.

    Its outline is extruded front to back: above the armpit one strip from the arm's outer side to the torso's
    right side, below it an arm strip and a torso strip, with the underside of the web between them. Vertices
    are shared, as in a real mesh. With `flare`, the sleeve is that much wider on each side near the elbow, as
    under an elbow guard."""
    arm = lambda z: -0.2 - (1.55 - z) * 0.1 / 0.27  # the arm's middle, through the shoulder and elbow joints
    levels = np.linspace(1.60, 1.00, 31)
    wide = lambda z: half + (flare if z < 1.37 else 0.0)
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
        inner = min(arm(z) + wide(z), -0.16)
        return [(arm(z) - wide(z), inner), (inner, -0.15), (-0.15, 0.15)] if joined else [(arm(z) - wide(z), arm(z) + wide(z)), (-0.15, 0.15)]

    for top, bottom in zip(levels[:-1], levels[1:]):
        joined = (top + bottom) / 2 > armpit
        for (a0, b0), (a1, b1) in zip(columns(top, joined), columns(bottom, joined)):
            for y in (depth, -depth):  # front and back
                quad((a0, y, top), (b0, y, top), (b1, y, bottom), (a1, y, bottom))
        walls = [columns(z, joined)[0][0] for z in (top, bottom)], [0.15, 0.15]
        if not joined:  # the arm's inner side and the torso's left side
            walls += ([arm(z) + wide(z) for z in (top, bottom)], [-0.15, -0.15])
        for x0, x1 in walls:
            quad((x0, depth, top), (x0, -depth, top), (x1, -depth, bottom), (x1, depth, bottom))
    for a, b in columns(1.60, True):  # the top, and the underside of the web at the armpit
        quad((a, depth, 1.60), (b, depth, 1.60), (b, -depth, 1.60), (a, -depth, 1.60))
    z = levels[np.argmin(np.abs(levels - armpit))]
    quad((arm(z) + wide(z), depth, z), (-0.15, depth, z), (-0.15, -depth, z), (arm(z) + wide(z), -depth, z))
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

    def test_a_shoulder_is_measured_only_where_the_arm_is_a_surface_of_its_own(self):
        J = {name: np.array(p, float) for name, p in JOINTS.items()}
        inside = J['lbicep_g'] + 0.06 * seams.unit(J['lbicep_g'] - J['lforearm_g'])
        v, f, _ = join(tube((0, 0, 0.95), (0, 0, 1.60), 0.15), tube(inside, J['lforearm_g'], 0.11))  # a bulky sleeve
        found = split.reaches(v, f, JOINTS, RADII)
        self.assertTrue(0.11 < found[('shoulder', 'l')] < 0.14, found)
        self.assertNotIn(('shoulder', 'l'), split.reaches(self.v, self.f, JOINTS, RADII))  # fused: the seam sets it

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


if __name__ == '__main__':
    unittest.main()
