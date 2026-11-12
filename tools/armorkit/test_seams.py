"""Seam geometry on synthetic shapes, and the frozen contract's own rules."""
import copy
import math
import unittest

import numpy as np

from . import registry, seams
from .test_registry import part


def tube(radius, low, high, sides=48):
    """An open cylinder about Z as (vertices, faces)."""
    angles = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    circle = np.stack([radius * np.cos(angles), radius * np.sin(angles)], axis=1)
    vertices = np.concatenate([np.c_[circle, np.full(sides, low)], np.c_[circle, np.full(sides, high)]])
    faces = [(i, (i + 1) % sides, sides + i) for i in range(sides)] + [((i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    return vertices, np.array(faces)


def turn(axis, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    x, y, z = axis
    matrix = np.eye(4)
    matrix[:3, :3] = [[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                      [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                      [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]]
    return matrix


class GeometryTests(unittest.TestCase):
    def test_ring_of_a_tube_is_its_radius_in_every_direction(self):
        vertices, faces = tube(0.05, -0.1, 0.1)
        segments = seams.section(vertices, faces, np.zeros(3), (0, 0, -1))
        self.assertEqual(segments.shape[1:], (2, 2))
        ring = seams.ring(segments)
        self.assertEqual(len(ring), seams.DIRECTIONS)
        self.assertTrue(np.allclose(ring, 0.05, atol=2e-4))
        self.assertTrue(np.all(seams.ring(segments, limit=0.01) == 0))
        self.assertEqual(len(seams.section(vertices, faces, np.array([0, 0, 0.5]), (0, 0, 1))), 0)

    def test_inner_ring_is_how_far_open_a_section_stands_and_nan_where_it_has_none(self):
        vertices, faces = tube(0.05, -0.1, 0.1)
        inner = seams.inner_ring(seams.section(vertices, faces, np.zeros(3), (0, 0, 1)))
        self.assertTrue(np.allclose(inner, 0.05, atol=2e-4))
        half = faces[(vertices[faces][:, :, 1] >= -1e-9).all(axis=1)]  # the tube's half on +Y
        inner = seams.inner_ring(seams.section(vertices, half, np.array([0.0, 0.01, 0.0]), (0, 0, 1)))
        self.assertTrue(np.isnan(inner[10:15]).all() and not np.isnan(inner[:10]).any())  # of 16: none below the centre, 1 cm off the cut edge
        self.assertAlmostEqual(inner[4], 0.04, places=3)
        plugged = np.concatenate([vertices, tube(0.01, -0.1, 0.1)[0]]), np.concatenate([faces, tube(0.01, -0.1, 0.1)[1] + len(vertices)])
        self.assertTrue(np.allclose(seams.inner_ring(seams.section(*plugged, np.zeros(3), (0, 0, 1))), 0.01, atol=2e-4))  # a closed end stands open nowhere
        self.assertTrue(np.isnan(seams.inner_ring(seams.section(*plugged, np.zeros(3), (0, 0, 1)), limit=0.005)).all())

    def test_ring_is_measured_about_the_joint_centre_and_fills_sparse_meshes(self):
        vertices, faces = tube(0.05, -0.1, 0.1, sides=6)
        ring = seams.ring(seams.section(vertices, faces, np.array([0.02, 0.0, 0.0]), (0, 0, 1)))
        self.assertTrue(ring.min() > 0)
        self.assertAlmostEqual(ring[0], 0.03, places=3)
        self.assertAlmostEqual(ring[seams.DIRECTIONS // 2], 0.07, places=3)

    def test_extent_is_signed_along_the_normal(self):
        vertices, _ = tube(0.05, -0.1, 0.3)
        self.assertEqual(seams.extent(vertices, np.zeros(3), (0, 0, -1)), (-0.3, 0.1))

    def test_swing_ignores_twist(self):
        rest = {'over': np.eye(4), 'under': np.eye(4)}
        normal = (0, 0, -1)
        self.assertAlmostEqual(seams.swing(rest, {'over': np.eye(4), 'under': turn((1, 0, 0), 30)}, 'under', 'over', normal), 30, places=6)
        self.assertAlmostEqual(seams.swing(rest, {'over': np.eye(4), 'under': turn((0, 0, 1), 80)}, 'under', 'over', normal), 0, places=6)
        both = {'over': turn((1, 0, 0), 50), 'under': turn((1, 0, 0), 50)}
        self.assertAlmostEqual(seams.swing(rest, both, 'under', 'over', normal), 0, places=6)
        scaled = turn((0, 1, 0), 45); scaled[:3, :3] *= 1.2
        self.assertAlmostEqual(seams.swing(rest, {'over': np.eye(4), 'under': scaled}, 'under', 'over', normal), 45, places=6)

    def test_minimum_overlap_grows_with_the_bend_up_to_one_radius(self):
        self.assertAlmostEqual(seams.minimum_overlap(0.1, 20), 0.036397, places=6)
        self.assertAlmostEqual(seams.minimum_overlap(0.1, 45), 0.1, places=12)
        self.assertEqual(seams.minimum_overlap(0.1, 110), 0.1)

    def test_tier_numbers_come_from_the_wider_side(self):
        got = seams.tier_values([[0.04] * 16, [0.05] * 15 + [0.06]], 0.012, 30)
        self.assertAlmostEqual(got['envelopeRadius'], 0.072)
        self.assertAlmostEqual(got['meanRadius'], 0.050625 + 0.012)
        self.assertAlmostEqual(got['minimumOverlap'], (0.050625 + 0.012) * 0.577350, places=6)

    def test_planes_follow_the_limb_and_point_into_the_under_part(self):
        rig = {name: np.eye(4) for name in ('neck_g', 'torso_g', 'lbicep_g', 'lforearm_g')}
        rig['lbicep_g'][:3, 3] = (-0.2, 0, 1.5)
        rig['lforearm_g'][:3, 3] = (-0.2, 0, 1.2)
        point, normal = seams.plane(rig, 'elbow')
        self.assertTrue(np.allclose(point, (-0.2, 0, 1.2)) and np.allclose(normal, (0, 0, -1)))
        self.assertTrue(np.allclose(seams.plane(rig, 'neck')[1], (0, 0, 1)) and np.allclose(seams.plane(rig, 'waist')[1], (0, 0, -1)))
        u, v = seams.frame(normal)
        self.assertTrue(np.allclose(u, (1, 0, 0)) and abs(u @ v) < 1e-12 and abs(v @ normal) < 1e-12)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = seams.load_contract()

    def test_layering_puts_the_part_nearer_the_torso_over(self):
        order = {joint: (row['over'], row['under']) for joint, row in self.contract['joints'].items()}
        self.assertEqual(order, {'neck': ('chest', 'neck'), 'shoulder': ('chest', 'bicep'), 'elbow': ('bicep', 'forearm'),
                                 'wrist': ('forearm', 'hand'), 'waist': ('chest', 'pelvis'), 'hip': ('pelvis', 'thigh'),
                                 'knee': ('thigh', 'shin'), 'ankle': ('shin', 'foot')})
        for joint, (over, under) in order.items():
            self.assertIn(joint, registry.SLOT_JOINTS[over])
            self.assertIn(joint, registry.SLOT_JOINTS[under])

    def test_every_joint_has_both_bodies_and_growing_tiers(self):
        self.assertEqual({float(v) for v in self.contract['tierOffsets'].values()}, set(seams.TIER_OFFSETS.values()))
        for joint, row in self.contract['joints'].items():
            for body in ('pmh0', 'pfh0'):
                tiers = row['bodies'][body]['tiers']
                radii = [tiers[str(t)]['envelopeRadius'] for t in registry.TIERS]
                self.assertEqual(radii, sorted(radii), joint)
                self.assertAlmostEqual(radii[3] - radii[0], 0.046, places=3)
                for side in seams.sides(joint):
                    self.assertEqual(len(seams.envelope(self.contract, joint, body, 2, side)), seams.DIRECTIONS)
                self.assertEqual(seams.overlap(self.contract, joint, body, 1), tiers['1']['minimumOverlap'])

    def test_limb_joints_have_two_sides_and_the_rest_one(self):
        self.assertEqual({joint: seams.sides(joint) for joint in ('neck', 'waist', 'elbow')},
                         {'neck': ('c',), 'waist': ('c',), 'elbow': ('l', 'r')})
        for joint, row in self.contract['joints'].items():
            for body in seams.AUTHORING_BODIES:
                self.assertEqual(tuple(row['bodies'][body]['sides']), seams.sides(joint))
        with self.assertRaisesRegex(ValueError, 'side must be one of'):
            seams.envelope(self.contract, 'elbow', 'pmh0', 1)
        self.assertEqual(seams.envelope(self.contract, 'waist', 'pmh0', 1), seams.envelope(self.contract, 'waist', 'pmh0', 1, 'c'))
        left, right = (self.contract['joints']['shoulder']['bodies']['pfh0']['sides'][side]['point'] for side in 'lr')
        self.assertGreater(abs(left[0] + right[0]), 0.005)

    def test_envelope_is_the_body_ring_plus_the_tier_offset(self):
        ring = self.contract['joints']['elbow']['bodies']['pmh0']['sides']['r']['bodyRing']
        self.assertTrue(np.allclose(np.array(seams.envelope(self.contract, 'elbow', 'pmh0', 3, 'r')) - ring, 0.05))

    def test_tampered_contracts_are_refused(self):
        for change, message in ((lambda c: c['joints']['knee'].update(over='shin', under='thigh'), 'layering order'),
                                (lambda c: c['joints'].pop('ankle'), 'exactly the eight joints'),
                                (lambda c: c['tierOffsets'].update({'2': 0.001}), 'grow with the tier'),
                                (lambda c: c['joints']['neck']['bodies'].pop('pfh0'), 'both Human Fit bodies'),
                                (lambda c: c['joints']['neck']['bodies'].update(pmh1={}), 'on SRN bodies only'),
                                (lambda c: c['joints']['hip']['bodies']['pmh0']['sides'].pop('r'), 'sides must be'),
                                (lambda c: c['joints']['hip']['bodies']['pmh0']['sides']['l']['bodyRing'].__setitem__(3, 0.0), 'radius in every direction'),
                                (lambda c: c['joints']['hip']['bodies']['pmh0']['tiers']['2'].update(envelopeRadius=0.01), 'tier 2 disagrees'),
                                (lambda c: c['joints']['waist']['bodies']['pfh0']['bend'].update(p95=20.0), 'tier 0 disagrees'),
                                (lambda c: c['tierOffsets'].update({'3': 0.08}), 'tier 3 disagrees'),
                                (lambda c: c.update(designBend='median'), 'designBend must be'),
                                (lambda c: c.update(directions=8), 'records 16 directions')):
            broken = copy.deepcopy(self.contract)
            change(broken)
            with self.assertRaisesRegex(ValueError, message):
                seams.validate_contract(broken)

    def test_a_contract_may_hold_more_bodies_than_the_two_it_is_authored_on(self):
        wider = copy.deepcopy(self.contract)
        for joint in wider['joints'].values():
            joint['bodies']['pmo2'] = copy.deepcopy(joint['bodies']['pmh0'])
        self.assertEqual(len(seams.envelope(seams.validate_contract(wider), 'knee', 'pmo2', 0, 'l')), seams.DIRECTIONS)

    def test_parts_mix_cleanly_when_the_over_tier_is_at_least_the_under_tier(self):
        chest = part()
        sleeve = part(slot='bicep', genderedCut=False, tiers={'shoulder': 1, 'elbow': 1})
        plate = part(slot='bicep', genderedCut=False, tiers={'shoulder': 3, 'elbow': 2})
        self.assertTrue(seams.mixes(chest, sleeve, 'shoulder'))
        self.assertFalse(seams.mixes(chest, plate, 'shoulder'))
        self.assertIsNone(seams.mixes(sleeve, chest, 'shoulder'))
        self.assertIsNone(seams.mixes(chest, sleeve, 'elbow'))
        belt = part(slot='belt', number=300, families=['accessory'], set=..., genderedCut=False, tiers={})
        self.assertIsNone(seams.mixes(chest, belt, 'waist'))


if __name__ == '__main__':
    unittest.main()
