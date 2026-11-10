"""The frozen seam contract and head envelopes still describe the published bodies and heads."""
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
        for name in ('pmh0', 'pfh0'):
            for filename, digest in contract['source']['bodies'][name].items():
                self.assertEqual(measure.sha(BODY_PACK / filename), digest, filename + ' changed since the contract was frozen')
            bones, parts = measure.body(BODY_PACK, name)
            for joint, row in measure.joints(bones, parts).items():
                frozen = contract['joints'][joint]['bodies'][name]
                for key in ('point', 'normal', 'bodyRing', 'underPastPlane', 'overPastPlane'):
                    self.assertTrue(np.allclose(row[key], frozen[key], atol=1e-4), f'{name} {joint} {key}')

    def test_left_and_right_planes_mirror_each_other(self):
        bones, _ = measure.body(BODY_PACK, 'pmh0')
        for joint in ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'):
            (lp, ln), (rp, rn) = seams.plane(bones, joint, 'l'), seams.plane(bones, joint, 'r')
            self.assertTrue(np.allclose(lp * (-1, 1, 1), rp, atol=2e-3) and np.allclose(ln * (-1, 1, 1), rn, atol=2e-2), joint)

    def test_recorded_head_envelopes_reproduce_from_the_published_heads(self):
        frozen = json.loads(ENVELOPES.read_text(encoding='utf-8'))
        self.assertEqual(len(frozen['bodies']), 10)
        made = measure.head_envelopes(HEAD_PACK, BODY_PACK, {name: row['heads'] for name, row in frozen['bodies'].items()})
        for name, row in frozen['bodies'].items():
            for key in ('min', 'max', 'rings', 'headBone', 'firstSlice'):
                self.assertTrue(np.allclose(made['bodies'][name][key], row[key], atol=1e-4), f'{name} {key}')
            self.assertTrue(all(len(ring) == seams.DIRECTIONS for ring in row['rings']))

    def test_clearance_of_the_body_over_itself_is_zero(self):
        bones, parts = measure.body(BODY_PACK, 'pfh0')
        gap = measure.clearance(parts['forel'], bones, parts, 'elbow')
        self.assertTrue(np.nanmax(np.abs(gap)) < 0.012)


if __name__ == '__main__':
    unittest.main()
