"""Ends brought to the seam contract's envelope (tools/armorkit/ends.py), on tubes along the left arm of a test rig."""
import unittest

import numpy as np

from . import bake, ends, seams
from .test_bake import arm, contract, rig


def radial(vertices, point=(0.3, 0.0, 0.0)):
    """Distance from the arm's axis (the x axis) and height along it from `point`."""
    v = np.asarray(vertices, float) - point
    return np.linalg.norm(v[:, 1:], axis=1), v[:, 0]


class TargetTests(unittest.TestCase):
    def test_the_target_is_the_envelope_read_straight_with_a_margin_to_its_side(self):
        envelope = np.full(seams.DIRECTIONS, 0.06)
        envelope[4] = 0.08
        step = 2 * np.pi / seams.DIRECTIONS
        angles = np.array([0.0, 3.5 * step, 4 * step])
        self.assertTrue(np.allclose(ends.target(envelope, angles, True), [0.06 - ends.MARGIN, 0.07 - ends.MARGIN, 0.08 - ends.MARGIN]))
        self.assertTrue(np.allclose(ends.target(envelope, angles, False), [0.06 + ends.MARGIN, 0.07 + ends.MARGIN, 0.08 + ends.MARGIN]))
        span = np.full(ends.BINS, np.radians(20.0))  # an edge spanning 20 degrees cuts across 1.5% inside its ends
        sag = 1 - np.cos(np.radians(10.0))
        self.assertAlmostEqual(float(ends.target(envelope, [0.0], False, span=span)[0]), 0.06 * (1 + sag) + ends.MARGIN)
        self.assertAlmostEqual(float(ends.target(envelope, [0.0], True, span=span)[0]), 0.06 * (1 - sag) - ends.MARGIN)


class RingTests(unittest.TestCase):
    def test_the_ring_is_read_on_the_ends_side_of_the_plane_and_filled_across_gaps(self):
        point, normal = np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        forearm = arm(0.3, 0.6, 0.05)  # ends on the plane: an under end is read just past it
        self.assertTrue(np.allclose(ends.ring(forearm['v'], forearm['f'], point, normal, True), 0.05, atol=1e-6))
        self.assertIsNone(ends.ring(forearm['v'], forearm['f'], point, normal, False))  # nothing on the over side
        upper = arm(0.0, 0.3, 0.07)
        self.assertTrue(np.allclose(ends.ring(upper['v'], upper['f'], point, normal, False), 0.07 * np.cos(np.pi / 32), atol=2e-4))
        half = forearm['f'][(forearm['v'][forearm['f']][:, :, 1] >= -1e-9).all(axis=1)]  # the half on +y
        read = ends.ring(forearm['v'], half, point, normal, True)
        self.assertTrue(np.all(read > 0.049))  # read across the missing half from its two edges


class EndTests(unittest.TestCase):
    def setUp(self):
        self.point, self.normal = np.array((0.3, 0.0, 0.0)), np.array((1.0, 0.0, 0.0))
        self.body = np.full(seams.DIRECTIONS, 0.04)
        self.envelope = self.body + 0.025

    def shape(self, part, under, length=0.1):
        rim = ends.ring(part['v'], part['f'], self.point, self.normal, under)
        return ends.end(part['v'], self.point, self.normal, rim, self.envelope, self.body, under, length)

    def test_a_wide_under_end_is_drawn_in_to_the_envelope_and_blends_back_in_one_slope(self):
        forearm = arm(0.25, 0.6, 0.08)
        r, h = radial(self.shape(forearm, True))
        self.assertTrue(np.allclose(r[h <= ends.PLATEAU], 0.065 - ends.MARGIN, atol=1e-6))  # past the plane and on the plateau
        self.assertTrue(np.allclose(r[h >= 0.1], 0.08))  # beyond its length, the outfit's own
        order = np.argsort(h)
        self.assertTrue(np.all(np.diff(r[order][h[order] >= 0]) >= -1e-9))  # widening all the way back: no shelf

    def test_a_narrow_over_end_is_spread_out_to_the_envelope(self):
        upper = arm(0.0, 0.3, 0.045)
        r, h = radial(self.shape(upper, False))
        self.assertTrue(np.all(r[h >= -ends.PLATEAU] >= 0.065 + ends.MARGIN - 1e-9))
        self.assertTrue(np.allclose(r[h <= -0.1], 0.045))

    def test_drawing_in_presses_nothing_inside_the_body_ring(self):
        forearm = arm(0.25, 0.6, 0.08)
        lining = arm(0.25, 0.6, 0.035)  # a closing inside the body ring
        both = {'v': np.concatenate([forearm['v'], lining['v']]), 'f': np.concatenate([forearm['f'], lining['f'] + len(forearm['v'])])}
        rim = ends.ring(forearm['v'], forearm['f'], self.point, self.normal, True)
        moved = ends.end(both['v'], self.point, self.normal, rim, self.envelope, self.body, True, 0.1)
        self.assertTrue(np.allclose(radial(moved)[0][len(forearm['v']):], 0.035))

    def test_the_body_ring_is_read_in_the_contracts_directions(self):
        # the contract's directions start at angle zero; a ring wider in one of them floors the drawing in there
        body = self.body.copy()
        body[4] = 0.06
        forearm, lining = arm(0.25, 0.6, 0.1), arm(0.25, 0.6, 0.055)
        both = np.concatenate([forearm['v'], lining['v']])
        rim = ends.ring(forearm['v'], forearm['f'], self.point, self.normal, True)
        moved = ends.end(both, self.point, self.normal, rim, body + 0.025, body, True, 0.1)
        u, v = seams.frame(self.normal)
        relative = both - self.point
        floor = np.minimum(radial(both)[0], seams.around(body, np.arctan2(relative @ v, relative @ u)))
        self.assertGreater((radial(moved)[0] - floor).min(), -1e-9)


class ShapedTests(unittest.TestCase):
    def test_shaped_ends_pass_the_seam_gate_where_the_cut_outfit_did_not(self):
        bones, terms = rig(), contract(rings={'shoulder': 0.08, 'wrist': 0.03})
        cut = {'forel': arm(0.25, 0.6, 0.08), 'bicepl': arm(-0.05, 0.3, 0.045)}  # 1.5 cm outside the elbow's tier 2 envelope, 2 cm inside it
        failures = bake.ends(cut, bones, 'test', 2, terms)[1]
        self.assertTrue(any('forel at the elbow' in failure for failure in failures) and any('bicepl at the elbow' in failure for failure in failures))
        fitted = {name: {**part, 'v': ends.shaped(part['v'], part['f'], np.ones(len(part['f']), bool), ends.ends_of(name, bones, terms, 'test', 2))}
                  for name, part in cut.items()}
        report, failures = bake.ends(fitted, bones, 'test', 2, terms)
        self.assertEqual(failures, [])
        self.assertEqual((report['elbow']['l']['under']['tier'], report['elbow']['l']['over']['tier']), (2, 2))
        self.assertEqual(ends.ends_of('chest', bones, terms, 'test', 2, joints=('elbow',)), [])

    def test_the_hook_leaves_pads_out_of_the_ring_and_turns_the_normals(self):
        bones, terms = rig(), contract()
        forearm = arm(0.25, 0.6, 0.08)
        pad = arm(0.25, 0.45, 0.12)  # far outside the ring: as part of it, it would draw the forearm in less
        v = np.concatenate([forearm['v'], pad['v']])
        f = np.concatenate([forearm['f'], pad['f'] + len(forearm['v'])])
        flags = np.r_[np.zeros(len(forearm['f']), bool), np.ones(len(pad['f']), bool)]
        columns = np.c_[ends.normals(v, f), np.zeros((len(v), 3))]
        shape = ends.shaper(bones, terms, 'test', 2, pads={('elbow', 'l'): flags}, joints=('elbow',))
        moved, turned = shape('forel', v, f, columns, np.arange(len(f)))
        r, h = radial(moved[:len(forearm['v'])])
        sides = 1 - np.cos(np.pi / 32)  # what an edge of the forearm's ring cuts across: the end stands that much farther in
        self.assertTrue(np.allclose(r[h <= ends.PLATEAU], 0.065 * (1 - sides) - ends.MARGIN, atol=2e-4))
        self.assertTrue(np.allclose(turned[:, :3], ends.normals(moved, f)))  # carried normals turn as the surface did
        self.assertFalse(np.allclose(turned[:, :3], columns[:, :3]))
        self.assertTrue(np.array_equal(shape('chest', v, f, columns, np.arange(len(f)))[0], v))  # a part with no end at the joints is left

    def test_an_end_under_the_bodys_own_skin_is_brought_skin_tight(self):
        bones, terms = rig(), contract()
        forearm = arm(0.25, 0.6, 0.08)
        columns = np.c_[ends.normals(forearm['v'], forearm['f']), np.zeros((len(forearm['v']), 3))]
        sides = 1 - np.cos(np.pi / 32)
        reached = {}
        for bare in ((), {('elbow', 'l')}):
            shape = ends.shaper(bones, terms, 'test', 2, joints=('elbow',), bare=bare)
            r, h = radial(shape('forel', forearm['v'], forearm['f'], columns, np.arange(len(forearm['f'])))[0])
            reached[bool(bare)] = r[h <= ends.PLATEAU]
        ring = 0.065 - terms['tierOffsets']['2']  # the body's own outline at the elbow
        self.assertTrue(np.allclose(reached[False], (ring + terms['tierOffsets']['2']) * (1 - sides) - ends.MARGIN, atol=2e-4))
        # on the skin, its edges clear the envelope: its vertices stand out by what an edge cuts across
        self.assertTrue(np.allclose(reached[True], (ring + terms['tierOffsets'][str(ends.BARE)]) * (1 + sides) - ends.MARGIN, atol=2e-4))
        # the forearm's other end, over the hand at the wrist, and the upper arm's over it at the elbow keep the outfit's tier
        for name in ('forel', 'bicepl'):
            told, plain = (ends.ends_of(name, bones, terms, 'test', 2, bare=bare) for bare in ({('elbow', 'l')}, ()))
            for (_, _, envelope, floor, under, skin), (_, _, before, _, _, _) in zip(told, plain):
                on_skin = under and name == 'forel'
                self.assertEqual((np.allclose(envelope, before), skin, np.array_equal(floor, envelope)), (not on_skin, on_skin, on_skin), name)

    def test_the_bake_shapes_skin_tight_the_ends_under_a_slot_left_to_the_body(self):
        # the forearms over the hands; the pelvis is over the thighs at the hips, which are not shaped (`ends.TUBES`)
        self.assertEqual(bake.bare_joints({'left': ['forel', 'forer', 'pelvis']}), {('wrist', 'l'), ('wrist', 'r')})
        self.assertEqual(bake.bare_joints({'left': ['legl']}), {('knee', 'l')})
        self.assertEqual(bake.bare_joints({}), set())


if __name__ == '__main__':
    unittest.main()
