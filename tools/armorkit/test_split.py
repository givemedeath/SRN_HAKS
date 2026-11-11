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
        self.assertEqual((len(points), len(uvs), len(faces)), (split.CAP_STEPS * rim, split.CAP_STEPS * rim, 2 * split.CAP_STEPS * rim))
        height = points[:, 2] - 0.4
        self.assertAlmostEqual(height.min(), -self.DEPTH * np.sin(np.radians(split.CAP_TOP)), places=9)
        self.assertTrue(np.all((np.linalg.norm(points[:, :2], axis=1) / self.RADIUS) ** 2 + (height / self.DEPTH) ** 2 < 1.0))
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
        top = -rings[-1][:, 2] / np.sin(np.radians(split.CAP_TOP))
        self.assertTrue(np.allclose(top, np.minimum(self.DEPTH, reach)))

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
        self.assertAlmostEqual(((points - point) @ normal).min(), -depth * np.sin(np.radians(split.CAP_TOP)), places=6)

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


if __name__ == '__main__':
    unittest.main()
