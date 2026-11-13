"""The frozen seam contract and head envelopes still describe the published bodies, heads and animation."""
import json
import unittest
from pathlib import Path

import numpy as np

from . import measure, seams

REPO = Path(__file__).resolve().parents[2]
BODY_PACK = REPO / 'srn_body'
HEAD_PACK = REPO / 'srn_head'
ENVELOPES = Path(__file__).with_name('head-envelopes.json')


class SeatTests(unittest.TestCase):
    def test_the_seat_is_how_far_the_pelvis_runs_past_the_hip_plane_per_direction(self):
        # a thigh 8 cm round straight down from the joint, in a pelvis 11 cm round whose lower edge dips 3 cm toward +x
        around, along = 96, 40
        angle = 2 * np.pi * np.arange(around) / around
        pelvis = [(0.11 * np.cos(a), 0.11 * np.sin(a), z) for z in np.linspace(0.3, 0.0, along + 1) for a in angle]
        pelvis = np.array(pelvis)
        pelvis[:, 2] -= (0.07 + 0.03 * np.cos(angle))[np.arange(len(pelvis)) % around] * (pelvis[:, 2] == 0.0)
        faces = [(i * around + k, i * around + (k + 1) % around, (i + 1) * around + k) for i in range(along) for k in range(around)]
        faces += [(i * around + (k + 1) % around, (i + 1) * around + (k + 1) % around, (i + 1) * around + k) for i in range(along) for k in range(around)]
        thigh = np.array([(0.08 * np.cos(a), 0.08 * np.sin(a), z) for z in (0.06, -0.5) for a in angle])
        legs = [(k, (k + 1) % around, around + k) for k in range(around)] + [((k + 1) % around, around + (k + 1) % around, around + k) for k in range(around)]
        parts = {'pelvis': (pelvis, np.array(faces)), 'legl': (thigh, np.array(legs))}
        reach = measure.seat(parts, np.zeros(3), (0, 0, -1.0), 'l')
        a, _ = seams.frame((0, 0, -1.0))  # direction k of the seat at k turns over 64 from the frame's first axis, here +x
        self.assertEqual(len(reach), measure.SEAT_DIRECTIONS)
        expected = 0.07 + 0.03 * np.cos(2 * np.pi * np.arange(64) / 64) * a[0]
        self.assertTrue(np.allclose(reach, expected, atol=0.002), np.round(reach - expected, 4))
        # evened over an odd number of directions round each, gaps read across; never an even number, which has no centre
        line = np.array([0.0, np.nan, 2.0, 3.0, 4.0, np.nan])
        self.assertTrue(np.allclose(measure._evened(line, 1), [0.0, 1.0, 2.0, 3.0, 4.0, 2.0]))
        self.assertTrue(np.allclose(measure._evened(line, 3), [1.0, 1.0, 2.0, 3.0, 3.0, 2.0]))
        with self.assertRaises(ValueError):
            measure._evened(line, 4)


class ArmholeTests(unittest.TestCase):
    def test_the_armhole_is_where_the_arm_comes_out_of_the_chest_per_direction(self):
        # an arm 5 cm round straight down from the joint, up into a chest whose underside rises 2.5 cm toward -x
        around = 64
        angle = 2 * np.pi * np.arange(around) / around
        levels = np.arange(0.08, -0.3001, -0.005)
        arm = np.array([(0.05 * np.cos(a), 0.05 * np.sin(a), z) for z in levels for a in angle] + [(0, 0, levels[0]), (0, 0, levels[-1])])
        rows = len(levels)
        faces = [(i * around + k, (i + 1) * around + k, i * around + (k + 1) % around) for i in range(rows - 1) for k in range(around)]
        faces += [(i * around + (k + 1) % around, (i + 1) * around + k, (i + 1) * around + (k + 1) % around) for i in range(rows - 1) for k in range(around)]
        top, bottom = rows * around, rows * around + 1
        faces += [(top, k, (k + 1) % around) for k in range(around)] + [(bottom, (rows - 1) * around + (k + 1) % around, (rows - 1) * around + k) for k in range(around)]
        corners = [(x, y, 0.4 if high else 0.02 + 0.5 * x) for high in (False, True) for y in (-0.3, 0.3) for x in (-0.3, 0.3)]
        box = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
        parts = {'chest': (np.array(corners, float), np.array(box)), 'bicepl': (arm, np.array(faces))}
        line = measure.armhole(parts, np.zeros(3), (0, 0, -1.0), 'l')
        a, _ = seams.frame((0, 0, -1.0))  # direction k at k turns over 64 from the frame's first axis, here +x
        self.assertEqual(len(line), measure.SEAT_DIRECTIONS)
        # the arm shows below the chest: its highest such point is 2 cm, and 2.5 cm more toward +x, above the plane
        expected = -(0.02 + 0.025 * np.cos(2 * np.pi * np.arange(64) / 64) * a[0])
        self.assertTrue(np.allclose(line, expected, atol=0.006), np.round(line - expected, 4))
        self.assertGreater(np.ptp(line), 0.04)
        with self.assertRaises(ValueError):  # an open chest has no inside to tell the arm out of
            measure.armhole({**parts, 'chest': (np.array(corners, float), np.array(box[:-1]))}, np.zeros(3), (0, 0, -1.0), 'l')

    def test_the_winding_number_tells_inside_from_outside(self):
        corners = np.array([(x, y, z) for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)], float)
        box = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        wound = measure.winding(np.array([(0.5, 0.5, 0.5), (0.1, 0.9, 0.2), (1.5, 0.5, 0.5), (0.5, 0.5, -0.01)]), corners, box)
        self.assertTrue(np.allclose(np.abs(wound), (1, 1, 0, 0), atol=1e-9))
        # it means that only of a closed surface, and `armhole` asks for one
        self.assertTrue(measure.closed(corners, box))
        self.assertFalse(measure.closed(corners, box[:-1]))
        self.assertFalse(measure.closed(corners, box[:0]))


class MeasuredContractTests(unittest.TestCase):
    def test_contract_planes_and_rings_match_the_locked_human_bodies(self):
        contract = seams.load_contract()
        for name in seams.AUTHORING_BODIES:
            for filename, digest in contract['source']['bodies'][name].items():
                self.assertEqual(measure.sha(BODY_PACK / filename), digest, filename + ' changed since the contract was frozen')
            bones, parts = measure.body(BODY_PACK, name)
            for joint, rows in measure.joints(bones, parts).items():
                frozen = contract['joints'][joint]['bodies'][name]['sides']
                self.assertEqual(set(rows), set(frozen), f'{name} {joint}')
                for side, row in rows.items():
                    self.assertEqual(set(row), set(frozen[side]), f'{name} {joint} {side}')
                    for key, value in row.items():
                        self.assertTrue(np.allclose(value, frozen[side][key], atol=1e-4), f'{name} {joint} {side} {key}')

    def test_animation_models_in_the_pack_are_the_ones_the_bends_were_sampled_from(self):
        contract = seams.load_contract()
        for name in seams.AUTHORING_BODIES:
            recorded = contract['source']['animation'][name]['models']
            carried = {model: BODY_PACK / (model + '.mdl') for model in recorded if (BODY_PACK / (model + '.mdl')).is_file()}
            self.assertTrue(carried, name + ': no inherited animation model is carried by the body pack')
            for model, path in carried.items():
                self.assertEqual(measure.sha(path), recorded[model], f'{model} changed since the bends were sampled: re-measure the seam contract')

    def test_the_male_body_is_centred_and_the_female_is_not(self):
        """Why the right side is recorded: a mirror of the left planes fits one authoring body and not the other."""
        bones, _ = measure.body(BODY_PACK, 'pmh0')
        for joint in ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'):
            (lp, ln), (rp, rn) = seams.plane(bones, joint, 'l'), seams.plane(bones, joint, 'r')
            self.assertTrue(np.allclose(lp * (-1, 1, 1), rp, atol=2e-3) and np.allclose(ln * (-1, 1, 1), rn, atol=2e-2), joint)
        bones, _ = measure.body(BODY_PACK, 'pfh0')
        left, right = seams.plane(bones, 'shoulder', 'l')[0], seams.plane(bones, 'shoulder', 'r')[0]
        self.assertGreater(abs(left[0] + right[0]), 0.005)

    def test_recorded_head_envelopes_reproduce_from_the_published_heads(self):
        frozen = json.loads(ENVELOPES.read_text(encoding='utf-8'))
        self.assertEqual(len(frozen['bodies']), 10)
        made = measure.head_envelopes(HEAD_PACK, BODY_PACK)
        for name, row in frozen['bodies'].items():
            self.assertEqual(made['bodies'][name]['heads'], row['heads'], name + ': published heads changed: re-measure the head envelopes')
            for key in ('min', 'max', 'rings', 'headBone', 'firstSlice'):
                self.assertTrue(np.allclose(made['bodies'][name][key], row[key], atol=1e-4), f'{name} {key}')
            self.assertTrue(all(len(ring) == seams.DIRECTIONS for ring in row['rings']))

    def test_head_rings_cover_surface_between_vertices(self):
        """One big triangle has vertices in three cells only; its surface crosses many more."""
        vertices = np.array([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.2, 0.1]])
        points = measure.surface_points(vertices, np.array([[0, 1, 2]]))
        self.assertGreater(len(points), 1000)
        gaps = np.linalg.norm(points[:, None] - np.array([[0.1, 0.05, 0.025]])[None], axis=2).min()
        self.assertLess(gaps, measure.SURFACE_STEP)
        self.assertEqual(len(measure.surface_points(vertices * 0.001, np.array([[0, 1, 2]]))), 3)

    def test_clearance_of_the_body_over_itself_is_zero(self):
        bones, parts = measure.body(BODY_PACK, 'pfh0')
        for side in ('l', 'r'):
            gap = measure.clearance(parts['fore' + side], 'forearm', bones, parts, 'elbow', side)
            self.assertTrue(np.nanmax(np.abs(gap)) < 0.012, side)

    def test_clearance_refuses_what_a_plane_section_cannot_measure(self):
        bones, parts = measure.body(BODY_PACK, 'pmh0')
        with self.assertRaisesRegex(ValueError, 'cannot be measured at the shoulder'):
            measure.clearance(parts['chest'], 'chest', bones, parts, 'shoulder')
        with self.assertRaisesRegex(ValueError, 'does not end at the knee'):
            measure.clearance(parts['chest'], 'chest', bones, parts, 'knee')
        gap = measure.clearance(parts['bicepl'], 'bicep', bones, parts, 'shoulder')
        self.assertTrue(np.nanmax(np.abs(gap)) < 0.012)


if __name__ == '__main__':
    unittest.main()
