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
