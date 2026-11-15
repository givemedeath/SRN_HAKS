"""Parts carried from one body to another (tools/armorkit/refit.py), on the test rig's left arm."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bake, bodyskin, measure, publish, refit, registry, seams, split
from .test_bake import arm, closed, contract, part, rig
from .test_seams import tube as upright
from .test_bodyskin import arm as body_arm
from .test_publish import joined, tube as standing


def moved(bones, rotation, scale, offset):
    """The rig `bones` with every joint carried by `scale * rotation @ p + offset`."""
    out = {name: matrix.copy() for name, matrix in bones.items()}
    for matrix in out.values():
        matrix[:3, 3] = scale * rotation @ matrix[:3, 3] + offset
    return out


def about_z(degrees):
    angle = math.radians(degrees)
    return np.array([[math.cos(angle), -math.sin(angle), 0.0], [math.sin(angle), math.cos(angle), 0.0], [0.0, 0.0, 1.0]])


def two_bodies(source_ring=0.04, target_ring=0.04):
    """A seam contract holding two bodies, `a` and `b`, with body rings of these radii at every joint."""
    a, b = contract(ring=source_ring), contract(ring=target_ring)
    for joint, spec in a['joints'].items():
        spec['bodies'] = {'a': spec['bodies']['test'], 'b': b['joints'][joint]['bodies']['test']}
    return a


def sleeved():
    """An upper arm's two faces of sleeve with the body's own arm beside them (`bodyskin.worn`)."""
    sleeve = part(faces=2)
    sleeve['v'] = np.array([(0.07, 0.0, 1.5), (0.07, 0.01, 1.5), (0.07, 0.0, 1.45)])
    return bodyskin.worn(sleeve, body_arm(), (0, 0, 1.5), (0, 0, 1.2))


def hand(scale=1.0, round_=None):
    """The body's own left hand: a short tube past the wrist plane (x = 0.55), `scale` times as long and
    `round_` (or `scale`) times as wide."""
    piece = arm(0.55, 0.55 + 0.12 * scale, 0.03 * (scale if round_ is None else round_))
    return piece['v'], piece['f']


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.rotation, self.offset = about_z(30.0), np.array((0.1, -0.2, 0.05))
        self.source = (rig(), {'handl': hand()})

    def test_a_part_between_two_joints_is_carried_as_its_joints_are(self):
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': hand(0.9)})
        forearm = arm(0.3, 0.55, 0.05)
        linear, offset, scales = refit.placement('forel', self.source, target)
        self.assertTrue(np.allclose(forearm['v'] @ linear.T + offset, 0.9 * forearm['v'] @ self.rotation.T + self.offset))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.9, 0.9]})

    def test_a_shoulder_pad_is_carried_as_its_upper_arm_is(self):
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': hand(0.9)})
        linear, offset, scales = refit.placement('shol', self.source, target)
        arm_linear, arm_offset, arm_scales = refit.placement('bicepl', self.source, target)
        self.assertTrue(np.allclose(linear, arm_linear) and np.allclose(offset, arm_offset))
        self.assertEqual(scales, {**arm_scales, 'with': 'bicepl'})

    def test_a_body_narrower_than_its_length_says_scales_the_part_across_its_axis_apart(self):
        target = (moved(rig(), np.eye(3), 0.9, np.zeros(3)), {'handl': hand(0.9)})
        linear, offset, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.028), ('a', 'b'))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.7, 0.7]})
        forearm = arm(0.3, 0.55, 0.05)
        carried = forearm['v'] @ linear.T + offset
        self.assertTrue(np.allclose(np.linalg.norm(carried[:, 1:], axis=1), 0.7 * 0.05))  # round, and as much narrower as the rings
        self.assertTrue(np.allclose(carried[:, 0], 0.9 * forearm['v'][:, 0]))  # and as long as the joints lie apart
        # however near the scales lie, each is its own: no one scale stands for them
        linear, _, scales = refit.placement('forel', self.source, target, two_bodies(0.04, 0.04 * 0.88), ('a', 'b'))
        self.assertEqual(scales, {'along': 0.9, 'across': [0.88, 0.88]})
        # a ring narrower one way than the other: 0.8 the source's across y (the frame's u at the elbow and the
        # wrist, square to the arm), 0.6 across z, between as cos and sin squared weigh them
        terms = two_bodies(0.04, 0.04)
        angle = 2 * np.pi * np.arange(seams.DIRECTIONS) / seams.DIRECTIONS
        for joint in terms['joints'].values():
            for ring in joint['bodies']['b']['sides'].values():
                ring['bodyRing'] = list(0.04 * (0.8 * np.cos(angle) ** 2 + 0.6 * np.sin(angle) ** 2))
        linear, offset, scales = refit.placement('forel', self.source, target, terms, ('a', 'b'))
        self.assertEqual((scales['along'], scales['across']), (0.9, [0.75, 0.65]))
        carried = forearm['v'] @ linear.T + offset
        self.assertAlmostEqual(float(np.ptp(carried[:, 1])), 0.75 * float(np.ptp(forearm['v'][:, 1])), places=9)
        self.assertAlmostEqual(float(np.ptp(carried[:, 2])), 0.65 * float(np.ptp(forearm['v'][:, 2])), places=9)

    def test_a_part_with_one_joint_turns_as_the_part_beside_it_and_scales_by_the_bodys_own(self):
        own = hand(0.8)
        target = (moved(rig(), self.rotation, 0.9, self.offset), {'handl': (own[0] @ self.rotation.T, own[1])})
        linear, offset, scales = refit.placement('handl', self.source, target)
        self.assertTrue(np.allclose(scales['axes'], 0.8, atol=1e-3))
        self.assertTrue(np.allclose(linear, 0.8 * self.rotation, atol=1e-3))
        wrist = np.array((0.55, 0.0, 0.0))
        self.assertTrue(np.allclose(linear @ wrist + offset, 0.9 * self.rotation @ wrist + self.offset))  # its joint where the other body's is
        # a hand as long but narrower: scaled along its own length and across it apart
        target = (rig(), {'handl': hand(0.9, 0.7)})
        linear, offset, scales = refit.placement('handl', self.source, target)
        self.assertTrue(np.allclose(sorted(scales['axes']), [0.7, 0.7, 0.9], atol=1e-3))
        carried = self.source[1]['handl'][0] @ linear.T + offset
        self.assertAlmostEqual(float(np.ptp(carried[:, 0])), 0.9 * 0.12, places=4)
        self.assertTrue(np.allclose(np.linalg.norm(carried[:, 1:], axis=1), 0.7 * 0.03, atol=1e-4))


def torso(span=0.4, lean=0.0):
    """The test rig with a torso stood up in it: the neck over the waist, `lean` in front of it, and the
    shoulders `span` apart, each arm straight out to its side."""
    bones = rig()
    at = {'neck_g': (0, lean, 1.6), 'torso_g': (0, 0, 1.1), 'lbicep_g': (span / 2, 0, 1.5), 'rbicep_g': (-span / 2, 0, 1.5),
          'lforearm_g': (span / 2 + 0.3, 0, 1.5), 'rforearm_g': (-span / 2 - 0.3, 0, 1.5)}
    for name, point in at.items():
        bones[name][:3, 3] = point
    return bones


def waisted(ring):
    """A seam contract of the bodies `a` and `b`, alike at every joint but the waist, where b's ring is `ring` times a's."""
    a, b = contract(ring=0.04), contract(ring=0.04, rings={'waist': 0.04 * ring})
    for joint, spec in a['joints'].items():
        spec['bodies'] = {'a': spec['bodies']['test'], 'b': b['joints'][joint]['bodies']['test']}
    return a


class TaperTests(unittest.TestCase):
    def setUp(self):
        # the other body's shoulders 1.5 times as far apart, its own chest 1.3 times as deep and its waist twice as wide
        self.source = (torso(0.4), {'chest': upright(0.10, 1.0, 1.7)})
        self.target = (torso(0.6), {'chest': upright(0.13, 1.0, 1.7)})
        self.terms = waisted(2.0)

    def test_only_the_chest_is_tapered_and_only_with_a_contract(self):
        self.assertIsNone(refit.taper('pelvis', self.source, self.target, self.terms, ('a', 'b')))
        self.assertIsNone(refit.taper('chest', self.source, self.target))
        self.assertEqual(refit.across('chest', self.terms, 'a', 'b', [np.array((1.0, 0, 0))], only='waist'), [2.0])
        self.assertLess(refit.across('chest', self.terms, 'a', 'b', [np.array((1.0, 0, 0))])[0], 1.3)  # the mean of four joints

    def test_a_vest_is_scaled_from_the_shoulders_width_to_the_waists_in_one_slope(self):
        slope = refit.taper('chest', self.source, self.target, self.terms, ('a', 'b'))
        self.assertTrue(np.allclose(slope['top'], [1.5, 1.3], atol=1e-3) and np.allclose(slope['hem'], [2.0, 2.0]))
        linear, offset, scales = refit.placement('chest', self.source, self.target, self.terms, ('a', 'b'))
        self.assertEqual((scales['along'], scales['hem']), (1.0, [2.0, 2.0]))
        vest = upright(0.09, 1.05, 1.65, sides=64)[0]  # inside the body's own chest: all of it is carried by the scales
        vest = np.concatenate([vest[:64] * (1, 1, 0) + (0, 0, z) for z in np.linspace(1.05, 1.65, 61)])  # a ring each centimetre
        carried = refit.tapered(vest, slope)
        self.assertTrue(np.allclose(carried[:, 2], vest[:, 2]))  # each slice level where it was
        top = vest[:, 2] >= 1.5  # down to the shoulder line the part's one map carries it as the slope does
        self.assertTrue(np.allclose(carried[top], vest[top] @ linear.T + offset))
        wide = lambda low, high, axis: float(np.ptp(carried[(vest[:, 2] > low) & (vest[:, 2] < high)][:, axis])) / 0.18
        self.assertAlmostEqual(wide(1.495, 1.66, 0), 1.5, places=3)  # from the shoulder line up, the shoulders' scales
        self.assertAlmostEqual(wide(1.495, 1.66, 1), 1.3, places=3)
        self.assertAlmostEqual(wide(1.045, 1.105, 0), 2.0, places=3)  # from the waist down, the waist's
        self.assertAlmostEqual(wide(1.045, 1.105, 1), 2.0, places=3)
        rings = [wide(z - 0.005, z + 0.005, 0) for z in np.linspace(1.1, 1.5, 41)]
        steps = -np.diff(rings)  # up the vest it narrows at every ring, by no more than the slope's own step and half as much again: no shelf
        self.assertTrue((steps > 0).all() and steps.max() < 1.5 * (2.0 - 1.5) / 40 / (1 - refit.TAPER_EASE / 2))
        self.assertLess(steps[-1], 0.25 * steps.max())  # and the slope sets in gently below the shoulder line

    def test_what_stands_outside_the_bodys_own_chest_stays_as_far_outside_it(self):
        slope = refit.taper('chest', self.source, self.target, self.terms, ('a', 'b'))
        self.assertAlmostEqual(slope['clear'], 0.1 + 0.04)  # the armpits: the shoulder ring's radius below the shoulder line
        heights, table = slope['radii']
        self.assertTrue((table > 0.095).all() and (table <= 0.1 + 1e-9).all())  # the body's own chest, a tube of 10 cm, facets and all
        angle = np.linspace(0, 2 * np.pi, 96, endpoint=False)
        ring = lambda radius, z: np.c_[radius * np.cos(angle), radius * np.sin(angle), np.full(len(angle), z)]
        radius = lambda points: np.linalg.norm(points[:, :2], axis=1)
        # at the waist the body is twice as wide: cloth 5 cm outside it stays 5 cm outside, where scaled it stood 10 cm
        hem = radius(refit.tapered(ring(0.15, 1.1), slope))
        self.assertTrue((hem > 2 * 0.095 + 0.05).all() and (hem < 2 * 0.1 + 0.05 + 1e-3).all())
        # and a pouch 4 cm deep on it stays 4 cm deep, all the way up to the armpits
        for z in (1.1, 1.3, 1.46):
            deep = radius(refit.tapered(ring(0.19, z), slope)) - radius(refit.tapered(ring(0.15, z), slope))
            self.assertTrue(np.allclose(deep, 0.04, atol=1e-9), z)
        # from the shoulder line up everything is scaled, standoff too: the armholes lie where the sleeves are carried to
        top = refit.tapered(ring(0.15, 1.5), slope)
        self.assertAlmostEqual(float(np.ptp(top[:, 0])) / 0.30, 1.5, places=3)
        self.assertAlmostEqual(float(np.ptp(top[:, 1])) / 0.30, 1.3, places=3)
        # between the two the standoff's own scale falls with no step: a column of points down the vest's front stays one line
        column = refit.tapered(np.c_[np.zeros(81), np.full(81, 0.15), np.linspace(1.55, 1.15, 81)], slope)
        self.assertLess(np.abs(np.diff(column[:, 1], 2)).max(), 2e-3)
        self.assertLess(np.abs(np.diff(column[:, 1])).max(), 6e-3)
        # a lid across the hem, inside the body's own chest, is scaled whole: its middle stays on the middle line
        lid = refit.tapered(np.array([(0.0, 0.0, 1.1), (0.05, 0.0, 1.1)]), slope)
        self.assertTrue(np.allclose(lid, [(0.0, 0.0, 1.1), (0.10, 0.0, 1.1)]))

    def test_a_leaning_vest_is_set_on_the_other_bodys_neck_shoulders_and_waist(self):
        # the source's neck 8 cm in front of its waist; the other body upright, 0.7 as long from neck to waist,
        # its shoulders 5 cm farther forward
        source = (torso(0.4, lean=0.08), self.source[1])
        bones = torso(0.6)
        for name in ('neck_g', 'lbicep_g', 'rbicep_g', 'lforearm_g', 'rforearm_g'):
            bones[name][2, 3] = 1.1 + 0.7 * (bones[name][2, 3] - 1.1)
            bones[name][1, 3] += 0.05 * (name != 'neck_g')
        target = (bones, {'chest': (self.target[1]['chest'][0] + (0, 0.05, 0), self.target[1]['chest'][1])})
        slope = refit.taper('chest', source, target, self.terms, ('a', 'b'))
        self.assertTrue(np.allclose(slope['top'], [1.5, 1.3], atol=1e-3))
        # the body's own chest is read about the middle line where it stands: at the waist a tube of 10 cm all round,
        # though the line bows 6 cm off the tube's axis between the stations
        heights, table = slope['radii']
        self.assertTrue(np.allclose(table[np.abs(heights - 0.5).argmin()], 0.1, atol=6e-3))
        linear, offset, scales = refit.placement('chest', source, target, self.terms, ('a', 'b'))
        self.assertEqual((scales['along'], scales['across']), (0.7, [1.5, 1.3]))
        hem = upright(0.09, 1.1, 1.3)[0][:48]
        carried = refit.tapered(hem, slope)
        self.assertTrue(np.allclose(carried[:, 2], 1.1))  # the hem on the waist plane, about the waist
        self.assertTrue(np.allclose(carried.mean(axis=0), (0, 0, 1.1)))
        self.assertAlmostEqual(float(np.ptp(carried[:, 0])) / 0.18, 2.0, places=3)
        at = lambda body: np.array([body['neck_g'][:3, 3], (body['lbicep_g'][:3, 3] + body['rbicep_g'][:3, 3]) / 2, body['torso_g'][:3, 3]])
        self.assertTrue(np.allclose(refit.tapered(at(source[0]), slope), at(bones)))
        self.assertTrue(np.allclose(source[0]['neck_g'][:3, 3] @ linear.T + offset, bones['neck_g'][:3, 3]))
        # between the stations the middle line is one curve: no step in its lean from slice to slice
        line = refit.tapered(np.c_[np.zeros(61), np.linspace(0.08, 0.0, 61), np.linspace(1.6, 1.1, 61)], slope)
        self.assertLess(np.abs(np.diff(line[:, 1], 3)).max(), 2e-4)


class EndTests(unittest.TestCase):
    def test_a_cap_short_of_the_other_bodys_overlap_is_stretched_to_it(self):
        point, normal = np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        cap = np.array([(0.3, 0.05, 0.0), (0.29, 0.04, 0.0), (0.27, 0.0, 0.0), (0.4, 0.05, 0.0)])  # its rim, two rings to the pole, the part
        deeper = refit.deepened(cap, point, normal, 0.05, 0.055)
        self.assertTrue(np.allclose(deeper, [(0.3, 0.05, 0.0), (0.3 - 0.055 / 3, 0.04, 0.0), (0.245, 0.0, 0.0), (0.4, 0.05, 0.0)]))
        self.assertTrue(np.array_equal(refit.deepened(cap, point, normal, 0.029, 0.035), cap))  # as deep as asked already
        self.assertTrue(np.array_equal(refit.deepened(cap[[0, 3]], point, normal, 0.05, 0.055), cap[[0, 3]]))  # no cap

    def test_a_dome_standing_too_far_past_its_rim_is_pressed_back(self):
        sleeve = closed(0.3, 0.55, 0.05, near=None, far='dome', shape={'depth': 1.0, 'most': 0.04})
        point, normal, here = np.array((0.55, 0.0, 0.0)), np.array((1.0, 0.0, 0.0)), np.ones(len(sleeve['v']), bool)
        self.assertAlmostEqual(float(sleeve['v'][:, 0].max()), 0.59, places=6)
        held = refit.flattened(sleeve, sleeve['v'], point, normal, here, 0.02)
        self.assertAlmostEqual(float(held[:, 0].max()), 0.57, places=6)
        own = np.unique(sleeve['f'][~sleeve['added']])
        self.assertTrue(np.array_equal(held[own], sleeve['v'][own]))  # the part's own surface and the dome's rim stay
        self.assertTrue(np.allclose(held[:, 1:], sleeve['v'][:, 1:]))  # pressed straight back
        self.assertTrue(np.array_equal(refit.flattened(sleeve, held, point, normal, here, 0.02), held))
        self.assertTrue(np.array_equal(refit.flattened(sleeve, sleeve['v'], point, normal, here, 0.04), sleeve['v']))
        self.assertTrue(np.array_equal(refit.flattened(sleeve, sleeve['v'], point, normal, ~here, 0.02), sleeve['v']))  # another joint's

    def test_a_refit_brings_caps_and_domes_to_the_other_bodys_contract(self):
        # a forearm with a cap 3.2 cm past the elbow and a dome 4 cm past the wrist, carried to a body that asks 4 cm of overlap
        forearm = closed(0.3, 0.55, 0.045, near='cap', far='dome', depth=0.032, shape={'depth': 1.0, 'most': 0.04})
        piece = {**part(), **forearm, 'n': np.tile([[0.0, 0.0, 1.0]], (len(forearm['v']), 1))}
        terms = contract(ring=0.04, overlaps=(0.02, 0.03, 0.04, 0.06))
        for tier, deepest in ((1, 0.032), (2, 0.04 + refit.ends.DEEPER)):
            out, _ = refit.refit({'forel': piece}, (rig(), {}), (rig(), {}), contract=terms, bodies=('test', 'test'), tier=tier)
            self.assertAlmostEqual(0.3 - float(out['forel']['v'][:, 0].min()), deepest, places=6)
            rim = float(out['forel']['v'][np.unique(forearm['f'][~forearm['added']])][:, 0].max())
            self.assertAlmostEqual(float(out['forel']['v'][:, 0].max()) - rim, seams.ENDS['domeMost'], places=6)
            self.assertEqual(bake.hidden(out, rig(), 'test', terms)[1], [])


class HeldTests(unittest.TestCase):
    """An under end held to the part carried over it, a hairline closed, a sleeve brought under its budget."""

    def under_end(self):
        # a forearm's end at the elbow (x = 0.3): its ring of 5 cm on the plane, a point 5 mm past the plane and
        # 7.5 cm out (a pouch's corner), a copy of it, its pole 4 cm past the plane, and the part beyond
        angle = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        ring = np.c_[np.full(8, 0.3), 0.05 * np.cos(angle), 0.05 * np.sin(angle)]
        v = np.concatenate([ring, [(0.295, -0.075, 0.0), (0.295, -0.075, 0.0), (0.26, 0.0, 0.0), (0.4, 0.05, 0.0)]])
        f = np.array([(0, 1, 8), (1, 2, 9), (2, 3, 10), (3, 4, 11), (4, 5, 10), (5, 6, 10), (6, 7, 10), (7, 0, 10)])
        return {'v': v, 'f': f}

    def test_what_would_show_past_the_over_part_in_the_bend_is_drawn_in_under_it(self):
        piece = self.under_end()
        point, normal = np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        upper = closed(0.0, 0.3, 0.09)  # the upper arm carried over it: at rest the corner lies inside it
        over = (upper['v'], upper['f'])
        self.assertTrue(bake._inside(piece['v'][[8]], [over])[0])
        turns = bake._turns('elbow', normal, 40.0, None)
        out = refit.tucked(piece, piece['v'], point, normal, 0.2, turns, over, 0.01)
        self.assertAlmostEqual(float(np.linalg.norm(out[8] - point)), 0.05 + 0.01 - refit.TUCK, places=9)  # within the ring's reach: it turns within the ring
        self.assertAlmostEqual(float(out[8, 0]), 0.295)  # drawn in toward the axis, as far past the plane as it was
        self.assertTrue(np.array_equal(out[8], out[9]))  # its copy with it
        rest = [k for k in range(len(out)) if k not in (8, 9)]
        self.assertTrue(np.array_equal(out[rest], piece['v'][rest]))  # the ring, the pole and the part stay
        self.assertTrue(np.array_equal(refit.tucked(piece, out, point, normal, 0.2, turns, over, 0.01), out))
        # under an over part that still covers it in the bend, it stays where it is
        long_ = closed(0.0, 0.5, 0.12)
        self.assertTrue(np.array_equal(refit.tucked(piece, piece['v'], point, normal, 0.2, turns, (long_['v'], long_['f']), 0.01), piece['v']))
        # a pole deeper past the plane than the reach itself comes up the axis to it: left at its depth and set on
        # the axis, it stayed as far from the joint as it was (review, 2026-11-14)
        deep = {**piece, 'v': piece['v'].copy()}
        deep['v'][10] = (0.22, 0.01, 0.0)
        away = closed(1.0, 1.3, 0.05)  # nothing over it: every point past the reach would show
        out = refit.tucked(deep, deep['v'], point, normal, 0.2, turns, (away['v'], away['f']), 0.01)
        self.assertAlmostEqual(float(np.linalg.norm(out[10] - point)), 0.05 + 0.01 - refit.TUCK, places=9)
        self.assertAlmostEqual(float(np.linalg.norm(out[10, 1:])), 0.0, places=9)

    def test_a_hairline_on_an_ends_plane_is_closed(self):
        # a face of the part and a face of its lid along one edge on the plane (x = 0.3), 30 microns apart: farther than
        # the gate welds, so the edge is open twice
        v = np.array([(0.3, 0.0, 0.0), (0.3, 0.01, 0.0), (0.35, 0.0, 0.0), (0.3, 0.0, 3e-5), (0.3, 0.01, 3e-5), (0.28, 0.005, 0.0),
                      (0.3, 0.0, 0.0), (0.35, -0.01, 0.0)])  # and a copy of the first, at a texture seam, on a face of its own
        piece = {'v': v, 'f': np.array([(0, 1, 2), (4, 3, 5), (6, 2, 7)])}
        planes = [(np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0)))]

        def open_on_plane(points):
            loose = bake._open_edges(points, piece['f'])[0]
            return int((np.abs(points[loose][:, :, 0] - 0.3) < bake.ON_PLANE).all(axis=1).sum())
        self.assertEqual(open_on_plane(v), 2)
        out = refit.healed(piece, v, planes)
        self.assertEqual(open_on_plane(out), 0)
        self.assertTrue(np.array_equal(out[0], out[3]) and np.array_equal(out[1], out[4]) and np.array_equal(out[0], out[6]))
        self.assertTrue(np.array_equal(out[[2, 5]], v[[2, 5]]))
        apart = v.copy()
        apart[[3, 4], 2] = 5e-4  # half a millimetre apart is no hairline: an opening is left to the gate
        self.assertTrue(np.array_equal(refit.healed(piece, apart, planes), apart))
        self.assertTrue(np.array_equal(refit.healed({**piece, 'pad': np.array([True, True, False])}, v, planes), v))  # a pad's edges are left open
        wide = v.copy()
        wide[[3, 4], 2] = 2.5e-4  # carried to a body three times as wide, a crack three times as wide is still that crack
        self.assertEqual(open_on_plane(refit.healed(piece, wide, planes, grown=3.0)), 0)
        # a sliver along the plane, its long edge open and its other one shared: the point across it lies on no open edge
        v = np.array([(0.3, 0.0, 0.0), (0.3, 0.006, 0.0), (0.3, 0.006, 2e-5), (0.35, 0.0, 0.0), (0.28, 0.003, 0.0)])
        piece = {'v': v, 'f': np.array([(0, 1, 2), (0, 2, 3), (1, 0, 4), (2, 1, 4)])}
        self.assertEqual(open_on_plane(v), 0)
        piece = {'v': v, 'f': piece['f'][:3]}  # without the face that closed the sliver's short edge, as a bake left it
        self.assertEqual(open_on_plane(v), 1)
        out = refit.healed(piece, v, planes)
        self.assertTrue(np.array_equal(out[1], out[2]))

    def test_a_sleeve_is_brought_under_its_budget_with_the_other_bodys_skin_counted(self):
        sleeve = arm(0.05, 0.25, 0.05)
        count = len(sleeve['f'])
        added = np.zeros(count, bool)
        added[:16] = True
        piece = {**part(), 'v': sleeve['v'], 'f': sleeve['f'], 'uv': sleeve['v'][:, :2], 'n': sleeve['v'] * 0 + (0, 0, 1.0), 'src': sleeve['v'],
                 'added': added, 'domed': np.zeros(count, bool), 'trimmed': np.arange(count)}
        planes = [(np.array((0.0, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))), (np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0)))]
        same, lost = refit.budgeted(piece, lambda v, f: 100, count + 100, planes)
        self.assertTrue(same is piece and lost == 0)  # within its budget with the skin: as it was
        out, lost = refit.budgeted(piece, lambda v, f: 100, count + 100 - 40, planes)
        self.assertTrue(lost >= 40 and len(out['f']) == count - lost)
        self.assertEqual({len(out[key]) for key in ('v', 'uv', 'n', 'src')}, {int(out['f'].max()) + 1})
        self.assertEqual({len(out[key]) for key in ('added', 'domed', 'trimmed')}, {len(out['f'])})
        self.assertEqual(int(out['added'].sum()), 16)  # nothing the split made lost a face
        self.assertTrue(np.array_equal(out['rgb'], piece['rgb']))
        self.assertTrue(np.allclose(np.linalg.norm(out['v'][:, 1:], axis=1), 0.05))  # every vertex left is one the sleeve had
        with self.assertRaisesRegex(Exception, 'stay over the budget'):
            refit.budgeted(piece, lambda v, f: 100, 120, planes)
        # a sleeve that is mostly what the split made: its own surface locked whole (here by its joints' planes), the
        # points inside its caps go, and nothing else
        shut = closed(0.0, 0.3, 0.05, near='cap', far='cap', depth=0.04)
        piece = {**part(), 'v': shut['v'], 'f': shut['f'], 'uv': shut['v'][:, :2], 'n': shut['v'] * 0 + (0, 0, 1.0), 'src': shut['v'],
                 'added': shut['added'], 'domed': np.zeros(len(shut['f']), bool), 'trimmed': np.arange(len(shut['f']))}
        tight = [(np.array((x, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))) for x in np.linspace(0.0, 0.3, 9)]  # every ring of the tube within a plane's band
        own = int((~shut['added']).sum())
        out, lost = refit.budgeted(piece, lambda v, f: 0, len(shut['f']) - 8, tight)
        self.assertGreaterEqual(lost, 8)
        self.assertEqual(int((~out['added']).sum()), own)


class OrderTests(unittest.TestCase):
    def test_a_part_is_carried_before_the_parts_whose_ends_run_into_it(self):
        self.assertEqual(refit.in_order(['handl', 'forel', 'bicepl', 'chest']), ['chest', 'bicepl', 'forel', 'handl'])
        every = [token for slot in ('foot', 'hand', 'shin', 'forearm', 'thigh', 'bicep', 'pelvis', 'chest') for token in registry.SLOTS[slot]['tokens']]
        for names in (every, every[::-1]):
            order = refit.in_order(names)
            for joint, spec in seams.JOINTS.items():
                for side in seams.sides(joint):
                    letter = 'l' if side == 'c' else side
                    over, under = split.token(spec['over'], letter), split.token(spec['under'], letter)
                    if under in order:
                        self.assertLess(order.index(over), order.index(under), joint)


class NeckTests(unittest.TestCase):
    NECK = standing(0.1, -0.07, 0.2)
    PLANE = (np.zeros(3), np.array((0.0, 0.0, 1.0)))
    GRAIN = 0.008

    def chest(self, dent=0.0):
        """A torso to 2 cm above the neck plane and a collar on it to 8 cm, 4 mm off the neck, drawn `dent` inside
        the neck at one point halfway up."""
        v, f = joined(standing(0.3, -0.5, 0.02), standing(0.104, 0.0, 0.04), standing(0.104, 0.04, 0.08))
        v = v.copy()
        at = np.linalg.norm(v - (0.104, 0.0, 0.04), axis=1) < 1e-9
        v[at, 0] = 0.1 - dent
        return {'v': v, 'f': f, 'n': v * 0 + (0, 0, 1.0)}, int(at.sum())

    def through(self, vertices, faces):
        return publish.neck((vertices, faces), self.NECK, *self.PLANE, grain=self.GRAIN)[0]['through']['share']

    def test_a_chest_the_neck_comes_through_below_its_collar_is_lifted_over_it(self):
        sound, _ = self.chest(-0.004)
        self.assertIs(refit.over_neck(sound, self.NECK, *self.PLANE, grain=self.GRAIN), sound)  # nothing through: as it was
        chest, dented = self.chest(0.005)
        self.assertEqual(dented, 2)  # the two tubes of the collar meet there: copies that must move as one
        self.assertGreater(self.through(chest['v'], chest['f']), 0)
        held = refit.over_neck(chest, self.NECK, *self.PLANE, grain=self.GRAIN)
        self.assertEqual(self.through(held['v'], chest['f']), 0)
        moved = np.linalg.norm(held['v'] - chest['v'], axis=1)
        self.assertLess(moved.max(), 0.012)
        self.assertTrue((moved[np.linalg.norm(chest['v'][:, :2], axis=1) > 0.2] == 0).all())  # the torso under the collar stays
        at = np.linalg.norm(chest['v'] - (0.095, 0.0, 0.04), axis=1) < 1e-9
        self.assertEqual(len(np.unique(held['v'][at].round(9), axis=0)), 1)
        with self.assertRaisesRegex(Exception, 'past 3 cm'):  # a neck bare between the chest and a band is no patch to lift cloth over
            v, f = joined(standing(0.3, -0.5, 0.0), standing(0.3, 0.06, 0.08))
            refit.over_neck({'v': v, 'f': f, 'n': v * 0 + (0, 0, 1.0)}, self.NECK, *self.PLANE, grain=self.GRAIN)


class RefitTests(unittest.TestCase):
    def test_parts_are_carried_with_their_normals_and_one_with_the_bodys_skin_without_it(self):
        source = (rig(), {'handl': hand()})
        target = (moved(rig(), about_z(90.0), 1.0, np.zeros(3)), {'handl': (hand()[0] @ about_z(90.0).T, hand()[1])})
        glove = part(faces=1)
        glove['v'] = glove['v'] + (0.6, 0.0, 0.0)
        sleeve = sleeved()
        out, report = refit.refit({'handl': glove, 'bicepl': sleeve}, source, target, ['handl'])
        self.assertEqual(report['handl']['degrees'], 90.0)
        self.assertTrue(np.allclose(out['handl']['n'], [[0.0, 0.0, 1.0]] * 3))  # turned about z, a normal along z stays
        self.assertTrue(np.allclose(out['handl']['v'], glove['v'] @ about_z(90.0).T))
        self.assertTrue(np.array_equal(out['handl']['rgb'], glove['rgb']))  # nothing else changes
        out, _ = refit.refit({'bicepl': sleeve}, source, target)  # the source body's skin left behind, the sleeve carried
        self.assertFalse(set(bodyskin.KEYS) & set(out['bicepl']))
        self.assertEqual((len(out['bicepl']['f']), len(out['bicepl']['v']), len(out['bicepl']['rgb'])), (2, 3, 4))

    def test_a_triangle_shrunk_to_a_sliver_the_compiler_drops_is_left_out(self):
        # two triangles of a glove, the second with two corners 2 microns apart: on a hand 0.4 the size, 0.8 apart
        glove = part(faces=2)
        glove['v'] = np.array([(0.6, 0.0, 0.0), (0.7, 0.0, 0.0), (0.6, 0.1, 0.0), (0.7 + 2e-6, 0.0, 0.0)])
        glove['f'], glove['n'] = np.array([[0, 1, 2], [1, 3, 2]]), np.tile([[0.0, 0.0, 1.0]], (4, 1))
        glove['added'], glove['pad'] = np.array([False, True]), np.array([False, True])
        source, target = (rig(), {'handl': hand()}), (rig(), {'handl': hand(0.4)})
        out, report = refit.refit({'handl': glove}, source, target)
        self.assertEqual((out['handl']['f'].tolist(), report['handl']['dropped']), ([[0, 1, 2]], 1))
        self.assertEqual((out['handl']['added'].tolist(), out['handl']['pad'].tolist(), len(out['handl']['trimmed'])), ([False], [False], 1))
        self.assertEqual(bake._collapsed(out['handl']['v'], out['handl']['f']), 0)
        self.assertNotIn('dropped', refit.refit({'handl': glove}, source, source)[1]['handl'])  # nothing shrunk, nothing dropped

    def test_a_stretched_parts_normals_stay_square_to_its_surface(self):
        source = (rig(), {})
        target = (moved(rig(), np.eye(3), 0.9, np.zeros(3)), {})
        forearm = arm(0.32, 0.53, 0.05)
        piece = {**part(), 'v': forearm['v'], 'f': forearm['f'], 'n': np.c_[np.zeros(len(forearm['v'])), forearm['v'][:, 1:] / 0.05]}
        out, report = refit.refit({'forel': piece}, source, target)
        self.assertEqual((report['forel']['along'], report['forel']['across']), (0.9, [0.9, 0.9]))  # no contract: the scale along every way
        linear, offset, _ = refit.placement('forel', source, target, two_bodies(0.04, 0.028), ('a', 'b'))
        normals = piece['n'] @ np.linalg.inv(linear)
        normals /= np.linalg.norm(normals, axis=1, keepdims=True)
        self.assertTrue(np.allclose(normals, piece['n']))  # a tube's radial normals stay radial when it is narrowed

    def test_a_cap_past_an_end_drawn_in_stays_as_far_inside_its_rim(self):
        # a forearm 5 cm round under the elbow plane (x = 0.3), its cap past the plane 3.5 cm round: drawn in to a
        # 4 cm body ring at tier 0, the cap is drawn in with it
        forearm, cap = arm(0.3, 0.55, 0.05), arm(0.27, 0.3, 0.035)
        piece = {**part(), 'v': np.concatenate([forearm['v'], cap['v']]), 'f': np.concatenate([forearm['f'], cap['f'] + len(forearm['v'])])}
        piece['n'] = np.c_[np.zeros(len(piece['v'])), piece['v'][:, 1:] / np.linalg.norm(piece['v'][:, 1:], axis=1, keepdims=True)]
        out, _ = refit.refit({'forel': piece}, (rig(), {}), (rig(), {}), contract=contract(ring=0.04), bodies=('test', 'test'), tier=0)
        radius = np.linalg.norm(out['forel']['v'][:, 1:], axis=1)
        rim, past = radius[np.abs(out['forel']['v'][:, 0] - 0.3) < 1e-9][:len(forearm['v'])].max(), radius[len(forearm['v']):][cap['v'][:, 0] < 0.3]
        self.assertLess(rim, 0.045)  # the end is drawn in to the envelope
        self.assertTrue(np.allclose(past / rim, 0.7, atol=0.01))  # the cap as far inside it as before
        # where the upper arm is left to the body, the cap stays inside the other body's own upper arm, 3 cm round
        skin = arm(0.0, 0.3, 0.03)
        out, _ = refit.refit({'forel': piece}, (rig(), {}), (rig(), {'bicepl': (skin['v'], skin['f'])}), contract=contract(ring=0.04),
                             bodies=('test', 'test'), tier=0, bare={('elbow', 'l')})
        past = np.linalg.norm(out['forel']['v'][len(forearm['v']):][cap['v'][:, 0] < 0.3][:, 1:], axis=1)
        self.assertLess(past.max(), 0.03 - refit.UNDER_SKIN + 1e-3)
        self.assertGreater(past.min(), 0.02)  # moved in to the skin, not onto the axis

    def test_a_sleeve_is_held_outside_the_other_bodys_arm(self):
        # a sleeve to x = 0.3, its end capped 3 cm back past x = 0.05, with the other body's arm 4 cm round kept beside it
        # from x = 0.18 (the left arm runs along +X from the origin)
        bones = rig()
        start, end = bones['lbicep_g'][:3, 3], bones['lforearm_g'][:3, 3]

        def worn(radius, dome=False, fuller=0.04):
            sleeve, arm_ = closed(0.05, 0.3, radius, near='cap', far=None), closed(0.0, 0.35, fuller, near=None, far=None)
            below = arm_['f'][arm_['v'][arm_['f']][:, :, 0].min(axis=1) > 0.18]
            v = np.concatenate([sleeve['v'], arm_['v']])
            added = np.concatenate([sleeve['added'] | dome, np.zeros(len(below), bool)])
            return {'v': v, 'n': np.zeros_like(v), 'f': np.concatenate([sleeve['f'], below + len(sleeve['v'])]), 'added': added,
                    'skin': np.arange(len(added)) >= len(sleeve['f'])}
        for dome in (False, True):  # the sleeve's own cloth, or a dome closing it, drawn over the arm all the same
            near = worn(0.035, dome)
            self.assertNotEqual(bake.through({'bicepl': near}, bones)[1], [])
            out = refit.over_skin(near, start, end)
            self.assertEqual(bake.through({'bicepl': out}, bones), ({'bicepl': 0.0}, []))  # held clear of the arm kept beside it
            skin = np.unique(near['f'][near['skin']])
            self.assertTrue(np.array_equal(out['v'][skin], near['v'][skin]))  # the arm itself is not moved
            pushed = np.linalg.norm(out['v'] - near['v'], axis=1)
            self.assertLessEqual(pushed.max(), 0.04 + refit.OVER_SKIN - 0.035 + 1e-6)  # by no more than it needs
            self.assertGreater(refit.short_of_skin(near, start, end), refit.OVER_SKIN + 0.004)  # the arm stands 5 mm out through it
            self.assertEqual(refit.short_of_skin(out, start, end), 0.0)
            # read once more after the last pass: a sleeve the passes left inside the arm fails, and says by how much
            with mock.patch.object(refit, 'OVER_PASSES', 0), self.assertRaisesRegex(Exception, r'Pushed out 0 times, the outfit still lies up to 0\.5 cm inside'):
                refit.over_skin(near, start, end)
        clear = worn(0.05)
        self.assertIs(refit.over_skin(clear, start, end), clear)  # a sleeve clear of the arm is not touched
        bare = closed(0.05, 0.3, 0.035, near=None, far=None)
        self.assertIs(refit.over_skin(bare, start, end), bare)  # nor a part with no skin beside it
        with self.assertRaisesRegex(Exception, 'would move 4.8 cm, past 3 cm'):  # an arm far fuller than the sleeve fails
            refit.over_skin(worn(0.035, fuller=0.08), start, end)

    def test_a_part_with_no_skin_beside_it_is_short_of_none(self):
        bones = rig()
        bare = closed(0.05, 0.3, 0.035, near=None, far=None)
        self.assertEqual(refit.short_of_skin(bare, bones['lbicep_g'][:3, 3], bones['lforearm_g'][:3, 3]), 0.0)

    def test_a_carried_parts_faces_turned_in_are_turned_out_and_counted(self):
        forearm = arm(0.3, 0.55, 0.05)
        piece = {**part(faces=len(forearm['f'])), 'v': forearm['v'], 'f': forearm['f'].copy(), 'n': np.zeros_like(forearm['v'])}
        out, report = refit.refit({'forel': piece}, (rig(), {}), (rig(), {}))
        self.assertTrue(np.array_equal(out['forel']['f'], forearm['f']) and 'turnedOut' not in report['forel'])
        piece['f'][[5, 6]] = piece['f'][[5, 6]][:, ::-1]  # two faces wound to face the arm: the client would show a hole there
        out, report = refit.refit({'forel': piece}, (rig(), {}), (rig(), {}))
        self.assertTrue(np.array_equal(out['forel']['f'], forearm['f']))
        self.assertEqual(report['forel']['turnedOut'], 2)

    def test_an_end_carried_under_the_other_bodys_own_part_is_seated_in_it(self):
        # an upper arm 4 cm round, its cap 10 cm back past the shoulder plane (x = 0.05), under a chest that stands
        # 8 cm over the joint, 8 cm round: the cap is drawn in to the chest's room less the gap, and held inside it
        sleeve, chest = closed(0.05, 0.3, 0.04, near='cap', far=None, depth=0.1), closed(-0.03, 0.05, 0.06)
        point, normal = np.array((0.05, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        out = refit.seated(sleeve, point, normal, (chest['v'], chest['f']))
        own = np.unique(sleeve['f'][~sleeve['added']])
        self.assertTrue(np.array_equal(out[own], sleeve['v'][own]))  # the sleeve itself is not moved
        cap = np.setdiff1d(np.unique(sleeve['f'][sleeve['added']]), own)
        self.assertAlmostEqual(float(((out[cap] - point) @ normal).min()), -(0.08 - split.SEAT_GAP), places=6)
        self.assertTrue(bake._inside(out[cap], [(chest['v'], chest['f'])]).all())
        self.assertTrue(np.array_equal(refit.seated(sleeve, point, normal, (chest['v'][:0], chest['f'][:0])), sleeve['v']))  # no room: as it was
        # read against the chest's nearest vertex a point may pass and still lie outside it between its vertices:
        # whatever that reading leaves outside is drawn in toward the cap's middle
        with mock.patch.object(refit, 'under_skin', lambda vertices, *_, **__: np.array(vertices, float)):
            held = refit.seated(sleeve, point, normal, (chest['v'], chest['f']))
        cap = np.unique(sleeve['f'][sleeve['added']])
        self.assertTrue((np.abs(measure.winding(sleeve['v'][cap], chest['v'], chest['f'])) < 0.5).any())
        self.assertTrue((np.abs(measure.winding(held[cap], chest['v'], chest['f'])) >= 0.5).all())
        shallow = closed(0.05, 0.3, 0.04, near='cap', far=None, depth=0.03)  # an end already inside the chest stays as it was
        self.assertTrue(np.array_equal(refit.seated(shallow, point, normal, (chest['v'], chest['f'])), shallow['v']))
        pole = np.argmin(sleeve['v'][:, 0])  # what lies nearer another joint of the part is that end's, and stays
        self.assertTrue(np.array_equal(refit.seated(sleeve, point, normal, (chest['v'], chest['f']), others=[sleeve['v'][pole]])[pole], sleeve['v'][pole]))

    def test_the_command_keeps_the_refit_parts_with_the_slots_the_brief_gave(self):
        with tempfile.TemporaryDirectory() as folder:
            kept, out = Path(folder) / 'kept', Path(folder) / 'out'
            glove = part(faces=1)
            bake.store({'handl': glove}, kept, {'bare': ['forearm'], 'skin': ['bicep']})
            bodies = {'pmh0': (rig(), {'handl': hand()}), 'pfh0': (rig(), {'handl': hand(0.8)})}
            with mock.patch.object(measure, 'body', side_effect=lambda pack, name: bodies[name]), \
                    mock.patch.object(seams, 'load_contract', return_value=None):
                report = refit.run(kept, out, 'pack', 'pmh0', 'pfh0')
            self.assertTrue(np.allclose(report['handl']['axes'], 0.8, atol=1e-3))
            self.assertEqual(bake.declared(out), {'bare': {'forearm'}, 'skin': {'bicep'}})
            self.assertEqual(list(bake.stored(out)), ['handl'])
            with self.assertRaises(ValueError):
                refit.run(kept, kept, 'pack', 'pmh0', 'pfh0')
            # a sleeve sharing its slot with the body's skin: carried without the male's, given the female's
            bake.store({'bicepl': sleeved()}, Path(folder) / 'sleeve', {'skin': ['bicep']})
            with mock.patch.object(measure, 'body', side_effect=lambda pack, name: bodies[name]), \
                    mock.patch.object(seams, 'load_contract', return_value=None), \
                    mock.patch.object(bodyskin, 'body_part', return_value=body_arm()) as read:
                with self.assertRaisesRegex(ValueError, "give the body's textures"):
                    refit.run(Path(folder) / 'sleeve', out / 'a', 'pack', 'pmh0', 'pfh0')
                refit.run(Path(folder) / 'sleeve', out / 'b', 'pack', 'pmh0', 'pfh0', body_textures='maps')
            self.assertEqual(read.call_args.args[:4], ('pack', 'maps', 'pfh0', 'bicepl'))
            self.assertEqual(int(bake.stored(out / 'b')['bicepl']['skin'].sum()), len(body_arm()['f']))


if __name__ == '__main__':
    unittest.main()
