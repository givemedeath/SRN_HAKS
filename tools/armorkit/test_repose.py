"""An outfit with its own stance and proportions is carried onto a body's joints and fitted round the body."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.headkit import gltf

from . import repose, seams
from .test_split import join, tube

# A stick body in metres, as the SRN bodies stand: z up, facing +y, left at -x, arms hanging a little away.
JOINTS = {'torso_g': (0, 0, 1.2), 'neck_g': (0, 0, 1.6)}
for letter, x in (('l', -1.0), ('r', 1.0)):
    JOINTS.update({letter + 'thigh_g': (0.11 * x, 0, 1.0), letter + 'shin_g': (0.11 * x, 0, 0.55), letter + 'foot_g': (0.11 * x, 0, 0.12),
                   letter + 'bicep_g': (0.22 * x, 0, 1.52), letter + 'forearm_g': (0.24 * x, 0, 1.25), letter + 'hand_g': (0.26 * x, 0, 0.98)})
CROTCH = 0.94


def body(thigh=0.08):
    """(bones, parts) like `measure.body` gives: a matrix per bone and a tube per skin part."""
    J = {name: np.array(p, float) for name, p in JOINTS.items()}
    bones = {}
    for name, p in J.items():
        bones[name] = np.eye(4); bones[name][:3, 3] = p
    parts = {'chest': tube(J['torso_g'], J['neck_g'], 0.16), 'neck': tube(J['neck_g'], J['neck_g'] + (0, 0, 0.1), 0.05, along=4),
             'pelvis': tube(J['torso_g'], (0, 0, CROTCH), 0.15, along=8)}
    for s in 'lr':
        down = seams.unit(J[s + 'hand_g'] - J[s + 'forearm_g'])
        parts.update({'leg' + s: tube(J[s + 'thigh_g'], J[s + 'shin_g'], thigh), 'shin' + s: tube(J[s + 'shin_g'], J[s + 'foot_g'], 0.06),
                      'foot' + s: tube(J[s + 'foot_g'], J[s + 'foot_g'] + (0, 0.1, -0.12), 0.04, along=4),
                      'bicep' + s: tube(J[s + 'bicep_g'], J[s + 'forearm_g'], 0.05), 'fore' + s: tube(J[s + 'forearm_g'], J[s + 'hand_g'], 0.04),
                      'hand' + s: tube(J[s + 'hand_g'], J[s + 'hand_g'] + 0.18 * down, 0.03, along=4)})
    return bones, {name: part[:2] for name, part in parts.items()}


# The doll below, at the body's size: legs that stand wider apart than the body's, and arms held far out.
LEG = lambda z: 0.11 + 0.08 * (CROTCH - z) / CROTCH
ARM = lambda z: 0.22 + 0.35 * (1.56 - z)
ARMPIT, NECK, TOP, HAND_END = 1.44, 1.60, 1.74, 0.75


def arm_half(z):
    """Half the arm's width at a height: a sleeve, a narrow wrist, a wider palm, then fingers."""
    return 0.05 if z > 0.98 else 0.03 if z > 0.94 else 0.06 if z > 0.80 else 0.04


def inside(x, z):
    """Whether the doll, arms hanging beside it, takes a point of its front view."""
    x = abs(x)
    if z < CROTCH:
        return abs(x - LEG(z)) < 0.07 or (z >= HAND_END and abs(x - ARM(z)) < arm_half(z))
    if z < ARMPIT:
        return x < 0.17 or abs(x - ARM(z)) < arm_half(z)
    if z < NECK:
        return x < ARM(z) + 0.05
    return x < 0.06


def held_out(x, z):
    """As `inside`, with the arms held out from the body instead: they end above the hips."""
    x = abs(x)
    arm = z >= 1.20 and abs(x - (0.22 + 1.5 * (1.56 - z))) < 0.07
    if z < CROTCH:
        return abs(x - LEG(z)) < 0.07
    if z < ARMPIT:
        return x < 0.17 or arm
    return x < 0.29 if z < NECK else x < 0.06


HEM = 1.30  # where a short sleeve ends: three quarters of the way from the shoulder to the elbow


def bare(x, z):
    """As `inside`, with nothing of the arms between a short sleeve's hem and a glove: the forearms there are the body's."""
    return inside(x, z) and not (1.0 <= z < HEM and abs(x) > 0.19)


def sleeves_only(x, z):
    """As `bare`, without the gloves: nothing of the arms below the sleeves' hems."""
    return bare(x, z) and not (z < 1.0 and abs(abs(x) - ARM(z)) < 0.07 and abs(abs(x) - LEG(z)) >= 0.07)


def guarded(x, z):
    """As `inside`, with a guard standing off each shoulder, above the armpit: beside the torso and no sleeve."""
    return inside(x, z) or (1.50 <= z < 1.58 and 0.09 < abs(x) - ARM(z) < 0.13)


def parted(x, z):
    """As `inside`, with each arm parted by a thin stretch of nothing: a strap's width, and no bare forearm."""
    return inside(x, z) and not (1.20 <= z < 1.24 and abs(x) > 0.19)


def doll(cell=0.02, depth=0.08, inside=inside):
    """A flat figure with shared vertices and no open edge: every cell of a grid that `inside` takes, extruded front
    to back, with a wall wherever a taken cell borders a free one. It is one surface from the feet to the collar,
    as a generated outfit is, and its sections are closed curves."""
    xs = np.arange(-0.72, 0.72 + 1e-9, cell); zs = np.arange(0.0, TOP + 1e-9, cell)
    taken = np.array([[inside((xs[i] + xs[i + 1]) / 2, (zs[k] + zs[k + 1]) / 2) for k in range(len(zs) - 1)] for i in range(len(xs) - 1)])
    index, points, faces = {}, [], []

    def vertex(x, y, z):
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in index:
            index[key] = len(points); points.append(key)
        return index[key]

    def quad(a, b, c, d):
        corners = [vertex(*p) for p in (a, b, c, d)]
        faces.extend([(corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])])

    free = lambda i, k: not (0 <= i < taken.shape[0] and 0 <= k < taken.shape[1] and taken[i, k])
    for i, k in zip(*np.nonzero(taken)):
        x0, x1, z0, z1 = xs[i], xs[i + 1], zs[k], zs[k + 1]
        quad((x0, depth, z0), (x1, depth, z0), (x1, depth, z1), (x0, depth, z1))
        quad((x0, -depth, z0), (x0, -depth, z1), (x1, -depth, z1), (x1, -depth, z0))
        for x, beside in ((x0, i - 1), (x1, i + 1)):
            if free(beside, k):
                quad((x, depth, z0), (x, -depth, z0), (x, -depth, z1), (x, depth, z1))
        for z, beside in ((z0, k - 1), (z1, k + 1)):
            if free(i, beside):
                quad((x0, depth, z), (x1, depth, z), (x1, -depth, z), (x0, -depth, z))
    return np.array(points), np.array(faces)


SCALE, SHIFT = 0.5, np.array([0.1, -0.2, -0.3])  # the doll comes in its own units and place, as a generated mesh does


class JointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bones, cls.parts = body()
        cls.there = repose.body_joints(cls.bones, cls.parts)
        v, cls.faces = doll()
        cls.vertices = v * SCALE + SHIFT
        cls.here, cls.marks = repose.outfit_joints(cls.vertices, cls.faces, cls.there)

    def own(self, point):
        """A point of the scaled, shifted doll in the doll's own metres."""
        return (np.asarray(point, float) - SHIFT) / SCALE

    def test_the_bodys_joints_and_measures_are_read_from_its_bones_and_parts(self):
        self.assertAlmostEqual(self.there['crotch'], CROTCH, places=6)
        self.assertTrue(np.allclose(self.there['kneel'], (-0.11, 0, 0.55)))
        self.assertTrue(np.allclose(self.there['hips'], (0, 0, 1.0)))
        self.assertAlmostEqual(self.there['upper'], np.hypot(0.02, 0.27), places=6)
        self.assertAlmostEqual(self.there['hand'], 0.18, places=2)
        self.assertEqual(self.there['toel'][2], 0.0)

    def test_the_landmarks_are_found_whatever_the_outfits_units_and_place(self):
        for name, height in (('floor', 0.0), ('crotch', CROTCH), ('armpit', ARMPIT), ('neck', NECK), ('top', TOP)):
            self.assertAlmostEqual((self.marks[name] - SHIFT[2]) / SCALE, height, delta=0.03, msg=name)
        self.assertAlmostEqual(self.marks['middle'], SHIFT[0], delta=0.01)

    def test_leg_joints_lie_on_the_outfits_own_legs(self):
        for sign, side in ((-1, 'l'), (1, 'r')):
            for joint, height in (('knee', 0.55), ('ankle', 0.12)):
                x, _, z = self.own(self.here[joint + side])
                self.assertAlmostEqual(z, height, delta=0.03, msg=joint)
                self.assertAlmostEqual(x, sign * LEG(height), delta=0.02, msg=joint)  # wider apart than the body's 0.11
            self.assertAlmostEqual(self.own(self.here['hip' + side])[2], 1.0, delta=0.03)

    def test_arm_joints_follow_the_arm_and_the_wrist_is_found_above_the_palm(self):
        for sign, side in ((-1, 'l'), (1, 'r')):
            shoulder, elbow, wrist, tip = (self.own(self.here[joint + side]) for joint in ('shoulder', 'elbow', 'wrist', 'tip'))
            self.assertAlmostEqual(shoulder[2], 1.52, delta=0.03)
            self.assertAlmostEqual(shoulder[0], sign * ARM(1.52), delta=0.03)
            self.assertTrue(0.93 < wrist[2] < 0.99, wrist)  # the narrow sections, not the fingers below the palm
            self.assertAlmostEqual(wrist[0], sign * ARM(wrist[2]), delta=0.03)
            self.assertAlmostEqual(elbow[2], (shoulder[2] + wrist[2]) / 2, delta=0.03)  # the body's upper and fore arm are equal
            self.assertAlmostEqual(elbow[0], sign * ARM(elbow[2]), delta=0.03)
            self.assertLess(tip[2], 0.8)  # the arm is followed to the fingers, and not on into the leg beside them
            self.assertGreater(abs(tip[0]), 0.4)

    def test_the_armpit_of_arms_held_out_is_above_the_hands_and_not_at_the_bare_waist(self):
        vertices, faces = doll(inside=held_out)
        marks = repose.landmarks(vertices, faces)
        self.assertAlmostEqual(marks['armpit'], ARMPIT, delta=0.03)  # nothing is beside the torso from 0.9 to 1.2 either
        self.assertAlmostEqual(marks['crotch'], CROTCH, delta=0.03)

    def test_an_arm_bare_between_a_short_sleeve_and_a_glove_has_its_joints_where_the_whole_arm_has(self):
        v, faces = doll(inside=bare)
        vertices = v * SCALE + SHIFT
        here, marks = repose.outfit_joints(vertices, faces, self.there)
        self.assertAlmostEqual((marks['armpit'] - SHIFT[2]) / SCALE, ARMPIT, delta=0.03)  # and not just above the gloves
        for side in 'lr':
            for joint, most in (('shoulder', 0.03), ('elbow', 0.04), ('wrist', 0.03), ('tip', 0.01)):
                apart = float(np.linalg.norm(self.own(here[joint + side]) - self.own(self.here[joint + side])))
                self.assertLess(apart, most, (joint, side))
        gloves = repose.past(marks, -1, repose.centreline(marks, -1, marks['armpit'] - 0.005 * marks['height'], 'arm'))
        self.assertGreater(len(gloves), 10)
        self.assertLess((gloves[-1, 0] - SHIFT[2]) / SCALE, 1.02)  # the glove, from its upper end down
        self.assertEqual(len(repose.past(self.marks, -1, repose.centreline(self.marks, -1, self.marks['armpit'] - 0.005 * self.marks['height'], 'arm'))), 0)

    def test_a_guard_standing_off_the_shoulder_does_not_move_the_armpit_above_it(self):
        v, faces = doll(inside=guarded)
        here, marks = repose.outfit_joints(v * SCALE + SHIFT, faces, self.there)
        self.assertAlmostEqual((marks['armpit'] - SHIFT[2]) / SCALE, ARMPIT, delta=0.03)  # the arms joined the torso below the guard
        for side in 'lr':
            for joint in ('shoulder', 'elbow', 'wrist'):
                self.assertLess(float(np.linalg.norm(self.own(here[joint + side]) - self.own(self.here[joint + side]))), 0.01, (joint, side))

    def test_an_arm_parted_by_a_thin_stretch_is_followed_through_it_as_a_whole_arm(self):
        v, faces = doll(inside=parted)
        here, marks = repose.outfit_joints(v * SCALE + SHIFT, faces, self.there)
        self.assertAlmostEqual((marks['armpit'] - SHIFT[2]) / SCALE, ARMPIT, delta=0.03)
        for side in 'lr':  # no glove's joints: the shoulder as the whole arm's, the elbow on the arm and not on a sleeve's line
            for joint, most in (('shoulder', 0.01), ('elbow', 0.03), ('wrist', 0.03), ('tip', 0.01)):
                self.assertLess(float(np.linalg.norm(self.own(here[joint + side]) - self.own(self.here[joint + side]))), most, (joint, side))

    def test_a_short_sleeve_without_a_glove_beyond_it_is_refused(self):
        v, faces = doll(inside=sleeves_only)
        with self.assertRaisesRegex(ValueError, 'needs a glove'):
            repose.outfit_joints(v * SCALE + SHIFT, faces, self.there)

    def test_an_outfit_without_separate_legs_or_arms_is_refused(self):
        block = join(tube((0, 0, 0), (0, 0, 1.7), 0.2))
        with self.assertRaises(ValueError):
            repose.landmarks(block[0], block[1])


class ReposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bones, cls.parts = body()
        v, cls.faces = doll()
        cls.given = v * SCALE + SHIFT
        cls.result = repose.onto_body(cls.given, cls.faces, cls.bones, cls.parts)
        cls.there = repose.body_joints(cls.bones, cls.parts)

    def test_a_turn_takes_one_direction_to_the_other_and_is_a_rotation(self):
        a, b = seams.unit(np.array([0.3, -0.2, 0.9])), seams.unit(np.array([-0.1, 0.5, -0.4]))
        matrix = repose.turn(a, b)
        self.assertTrue(np.allclose(matrix @ a, b))
        self.assertTrue(np.allclose(matrix @ matrix.T, np.eye(3)))
        self.assertAlmostEqual(np.linalg.det(matrix), 1.0)
        self.assertTrue(np.allclose(repose.turn(a, a), np.eye(3)))
        with self.assertRaises(ValueError):
            repose.turn(a, -a)

    def test_the_outfits_joints_end_up_on_the_bodys(self):
        self.assertAlmostEqual(self.result['scale'], 1 / SCALE, delta=0.05)
        again, marks = repose.outfit_joints(self.result['vertices'], self.result['faces'], self.there)
        self.assertAlmostEqual(marks['floor'], 0.0, delta=0.01)  # the soles are on the ground
        for joint in ('knee', 'ankle', 'shoulder', 'elbow', 'wrist'):
            for side in 'lr':
                error = np.linalg.norm((again[joint + side] - self.there[joint + side])[[0, 2]])
                self.assertLess(error, 0.05, f'{joint}{side} {again[joint + side]} {self.there[joint + side]}')
        # the arms hang beside the body now, and the legs stand under the hips
        self.assertLess(np.abs(self.result['vertices'][:, 0]).max(), 0.45)

    def test_a_leg_pressed_past_the_middle_comes_back_to_its_own_side(self):
        there = {'hipl': np.array([-0.1, 0.0, 1.0]), 'hipr': np.array([0.1, 0.0, 1.0]), 'hips': np.array([0.0, 0.0, 1.0])}
        # a left thigh past the middle, one clear of it, a right thigh past it that half follows the pelvis, and
        # the left of a waistband, which follows the legs by a quarter, and of a chest, which does not
        points = np.array([[0.006, 0.01, 0.7], [-0.05, 0.0, 0.7], [-0.004, 0.0, 0.7], [0.01, 0.0, 1.05], [0.01, 0.0, 1.4]])
        result = repose.apart(points, np.array([-1.0, -1.0, 1.0, -1.0, -1.0]), np.array([1.0, 1.0, 0.5, 0.25, 0.0]), there)
        np.testing.assert_allclose(result[:, 0], [-repose.LEGS_APART, -0.05, repose.LEGS_APART, 0.01 - 0.5 * (0.01 + repose.LEGS_APART), 0.01])
        np.testing.assert_allclose(result[:, 1:], points[:, 1:])
        fitted, weights = self.result['vertices'], self.result['weights']
        legs = weights[[index for index, bone in enumerate(repose.BONES) if repose.kind(bone[0]) in ('thigh', 'shin', 'foot')]].sum(axis=0)
        left = (legs > 0.999) & (self.result['posed'][:, 0] < -0.02)
        self.assertTrue(left.any() and (fitted[left, 0] <= -repose.LEGS_APART + 1e-9).all())

    def test_the_ground_is_set_by_the_feet_and_not_by_a_hem_that_hangs_lower(self):
        # a sole, an ankle that half follows the foot, a shin that barely does, and a hem below them all
        points = np.array([[0, 0, 0.04], [0, 0, 0.12], [0, 0, 0.30], [0, 0, -0.05]], float)
        result = repose.grounded(points, np.array([1.0, 0.5, 0.02, 0.0]))
        np.testing.assert_allclose(result[:, 2], [0.0, 0.10, 0.2992, -0.05])
        np.testing.assert_allclose(repose.grounded(points, np.zeros(4)), points)  # no feet: nothing to set down

    def test_the_sleeves_are_cut_as_the_outfit_came_and_the_other_faces_are_kept(self):
        faces, origin, sleeves = self.result['faces'], self.result['origin'], self.result['sleeves']
        self.assertEqual(set(sleeves), {'l', 'r'})  # the doll's arms are one surface with its torso down to the armpit
        given = len(self.given)
        source = self.result['source']
        self.assertTrue(np.array_equal(source[:given], self.given))  # its own vertices, then those on the cuts
        self.assertEqual(len(source), len(self.result['vertices']))
        whole = np.bincount(origin, minlength=len(self.faces))[origin] == 1
        self.assertTrue(whole.any() and not whole.all())
        self.assertTrue(np.array_equal(faces[whole], self.faces[origin[whole]]))
        self.assertTrue(np.array_equal(np.unique(origin), np.arange(len(self.faces))))
        for side, found in sleeves.items():
            self.assertEqual(found['on'].shape, (4, len(source)))
            self.assertEqual(found['inside'].shape, (len(faces),))
            points = source[found['on'][0]]  # the seam is flat in the pose the outfit came in, wherever the bend took it
            self.assertGreater(len(points), 3)
            self.assertLess(np.linalg.svd(points - points.mean(axis=0), compute_uv=False)[-1], 1e-6)
            self.assertGreater(np.linalg.svd(self.result['vertices'][found['on'][0]] - self.result['vertices'][found['on'][0]].mean(axis=0), compute_uv=False)[-1], 1e-4)
            self.assertFalse(found['on'][1:3].any())  # the doll is flat: the walls in front of it and behind it meet nothing
            self.assertFalse(found['on'][3].any() or found['pad'].any())  # no materials were given: no pad is looked for
            # the torso's own vertices on the cuts follow no bone of that arm; the sleeve's, at the same places, do
            arm = [index for index, bone in enumerate(repose.BONES) if bone[0] in ('upper' + side, 'fore' + side, 'hand' + side)]
            weights = self.result['weights'][arm].sum(axis=0)
            self.assertTrue(found['torso'].any())
            self.assertEqual(weights[found['torso']].max(), 0.0)
            self.assertGreater(weights[found['on'].any(axis=0) & ~found['torso']].max(), 0.02)  # a little, this near the shoulder
            self.assertFalse(found['on'][:, :given].any())  # only vertices the cuts made lie on them
            inside = source[faces[found['inside']]].mean(axis=1)[:, 0] - SHIFT[0]
            self.assertTrue(np.all(inside < 0) if side == 'l' else np.all(inside > 0))

    def test_every_vertex_follows_bones_that_add_up_to_one(self):
        self.assertEqual(self.result['weights'].shape, (len(repose.BONES), len(self.result['vertices'])))
        self.assertTrue(np.allclose(self.result['weights'].sum(axis=0), 1.0))
        self.assertTrue(np.isfinite(self.result['vertices']).all())

    def test_a_shoulder_pad_told_by_its_material_is_parted_along_its_outline(self):
        # a patch of another material round each shoulder joint
        centre = self.given[self.faces].mean(axis=1)
        materials = np.zeros(len(self.faces), int)
        for side in 'lr':
            materials[np.linalg.norm(centre - self.result['joints']['shoulder' + side], axis=1) < 0.07 * SCALE] = 1
        result = repose.onto_body(self.given, self.faces, self.bones, self.parts, materials=materials)
        self.assertTrue(np.array_equal(np.any([found['pad'] for found in result['sleeves'].values()], axis=0), (materials == 1)[result['origin']]))
        for side, found in result['sleeves'].items():
            self.assertTrue(found['pad'].any() and found['on'][3].any())
            # the outline is one edge of the torso and the pad through the bend: no vertex of the torso's own lies on it alone
            self.assertFalse((found['torso'] & ~found['on'][:3].any(axis=0)).any())
        self.assertTrue(np.array_equal(result['source'][:len(self.given)], self.given))
        with self.assertRaises(ValueError):
            repose.onto_body(self.given, self.faces, self.bones, self.parts, materials=materials[:-1])
        with self.assertRaises(ValueError):  # designed with pads, and shows none
            repose.onto_body(self.given, self.faces, self.bones, self.parts, materials=np.zeros(len(self.faces), int), padded='lr')

    def test_a_vertex_follows_only_the_bones_it_is_free_to(self):
        names = [bone[0] for bone in repose.BONES]
        there = self.there  # a trouser leg on the body's own left leg, bent nowhere
        v, f = tube(there['hipl'], there['anklel'], 0.05, around=8, along=20)[:2]
        knee = np.abs(v[:, 2] - there['kneel'][2]) < 0.03
        self.assertTrue(knee.any())
        free = np.ones((len(repose.BONES), len(v)), bool)
        free[names.index('shinl'), knee] = False
        _, plain = repose.repose(v, f, there, there, 1.0, 1.8)
        _, held = repose.repose(v, f, there, there, 1.0, 1.8, free)
        self.assertGreater(plain[names.index('shinl'), knee].min(), 0.3)  # at the knee a vertex follows both bones
        self.assertEqual(held[names.index('shinl'), knee].max(), 0.0)
        self.assertTrue(np.allclose(held.sum(axis=0), 1.0))
        low = v[:, 2] < there['anklel'][2] + 0.1
        self.assertGreater(held[names.index('shinl'), low].min(), 0.5)  # farther down the shin it still does
        with self.assertRaises(ValueError):
            repose.repose(v, f, there, there, 1.0, 1.8, np.zeros_like(free))

    def test_a_vertex_in_the_middle_of_a_bone_follows_that_bone(self):
        names = [bone[0] for bone in repose.BONES]
        posed = self.result['posed']
        for name, point in (('shinl', (-0.11, 0.0, 0.33)), ('forer', (0.25, 0.0, 1.1)), ('torso', (0.0, 0.0, 1.4))):
            near = np.argmin(np.linalg.norm(posed - np.array(point), axis=1))
            self.assertEqual(names[int(np.argmax(self.result['weights'][:, near]))], name)


class FitTests(unittest.TestCase):
    def setUp(self):
        self.bones, self.parts = body(thigh=0.08)
        self.there = repose.body_joints(self.bones, self.parts)
        self.names = [bone[0] for bone in repose.BONES]

    def follow(self, count, name):
        weight = np.zeros((len(repose.BONES), count)); weight[self.names.index(name)] = 1.0
        return weight

    def radius(self, points, side='l'):
        a, b = self.there['hip' + side], self.there['knee' + side]
        axis = seams.unit(b - a); relative = points - a
        return np.linalg.norm(relative - (relative @ axis)[:, None] * axis, axis=1)

    def test_an_outfit_thinner_than_the_body_is_widened_to_stand_outside_it(self):
        sleeve = tube(self.there['hipl'] + (0, 0, -0.05), self.there['kneel'] + (0, 0, 0.05), 0.05, around=24)[0]
        fitted, report = repose.fit(sleeve, self.follow(len(sleeve), 'thighl'), self.there, self.parts)
        # the body's tube is a 12-sided prism: its flats lie 0.0773 m from the bone
        self.assertGreater(self.radius(fitted).min(), 0.0773 + repose.CLEARANCE / 2)
        self.assertLess(self.radius(fitted).max(), 0.08 + 3 * repose.CLEARANCE)
        self.assertTrue(np.allclose(fitted[:, 2], sleeve[:, 2], atol=1e-6))  # widened across the bone only
        self.assertGreater(report['thighl'][0], 1.5)

    def test_an_outfit_already_outside_the_body_is_left_alone(self):
        sleeve = tube(self.there['hipl'] + (0, 0, -0.05), self.there['kneel'] + (0, 0, 0.05), 0.12, around=24)[0]
        fitted, report = repose.fit(sleeve, self.follow(len(sleeve), 'thighl'), self.there, self.parts)
        self.assertTrue(np.allclose(fitted, sleeve))
        self.assertEqual(report['thighl'], (1.0, 0))

    def test_a_vertex_beside_a_shelf_of_the_body_is_not_set_out_as_far_as_the_shelf(self):
        # a thigh twice as wide above a shelf across the bone as below it, like a chest at the top of its shoulder
        hip, knee = self.there['hipl'], self.there['kneel']
        shelf = hip + (0, 0, -0.23)
        parts = dict(self.parts, legl=join(tube(hip, shelf, 0.12), tube(shelf, knee, 0.06))[:2])
        sleeve = tube(hip + (0, 0, -0.02), knee + (0, 0, 0.02), 0.2, around=48, along=40)[0]
        low = np.array([hip + (0.08, 0, -0.235), hip + (0.08, 0, -0.10)])  # just under the shelf, and well up in the wide half
        posed = np.concatenate([sleeve, low])
        fitted, report = repose.fit(posed, self.follow(len(posed), 'thighl'), self.there, parts)
        self.assertTrue(np.allclose(fitted[:len(sleeve)], sleeve))
        self.assertTrue(np.allclose(fitted[-2], low[0]))  # outside the body where it stands: the shelf a ring up has no say
        self.assertGreater(self.radius(fitted[-1:])[0], 0.1159 + repose.CLEARANCE / 2 - 1e-9)  # inside it: set outside
        self.assertTrue(np.allclose(fitted[-1, 2], low[1, 2]))
        self.assertEqual(report['thighl'], (1.0, 1))

    def test_the_widening_keeps_the_outfits_relief(self):
        sleeve = tube(self.there['hipl'] + (0, 0, -0.05), self.there['kneel'] + (0, 0, 0.05), 0.05, around=96)[0]
        ridge = np.arange(len(sleeve)) % 96 == 0  # a seam down one side, raised 1 cm
        outward = sleeve[ridge, :2] - self.there['hipl'][:2]
        sleeve[ridge, :2] += 0.01 * outward / np.linalg.norm(outward, axis=1, keepdims=True)
        fitted, _ = repose.fit(sleeve, self.follow(len(sleeve), 'thighl'), self.there, self.parts)
        self.assertGreater(self.radius(fitted[ridge]).mean() - self.radius(fitted[~ridge]).mean(), 0.004)

    def test_hands_and_feet_are_not_fitted(self):
        for name, start, end in (('handl', 'wristl', 'tipl'), ('footl', 'anklel', 'toel')):
            glove = tube(self.there[start], self.there[end], 0.01)[0]  # far inside the body's hand or foot
            fitted, report = repose.fit(glove, self.follow(len(glove), name), self.there, self.parts)
            self.assertTrue(np.allclose(fitted, glove), name)
            self.assertNotIn(name, report)


class LoadTests(unittest.TestCase):
    def test_a_generated_file_is_welded_and_turned_to_the_bodies_axes(self):
        # glTF: +y up, +z toward the viewer; a triangle pair that repeats two vertices
        points = np.array([(1, 2, 3), (4, 5, 6), (7, 8, 10), (4, 5, 6), (7, 8, 10), (0, 1, 0)], np.float32)
        faces = np.array([(0, 1, 2), (3, 5, 4)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mesh.glb'
            gltf.write_mesh(path, points, faces)
            vertices, read = repose.load(path)
        self.assertEqual(len(vertices), 4)
        self.assertEqual(len(read), 2)
        self.assertTrue(np.allclose(sorted(vertices.tolist()), sorted([(-1, 3, 2), (-4, 6, 5), (-7, 10, 8), (0, 0, 1)])))
        self.assertTrue(np.allclose(vertices[read[0]], [(-1, 3, 2), (-4, 6, 5), (-7, 10, 8)]))


if __name__ == '__main__':
    unittest.main()
