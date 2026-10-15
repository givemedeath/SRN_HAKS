"""body_sweep: requested motion clips must be measurable, or the gap is recorded."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import body_sweep as bs

MODELS = {'pfd0': {'parent': 'a_fa', 'clips': {}}, 'pfh0': {'parent': 'a_fa', 'clips': {}},
          'a_fa': {'parent': 'a_ba', 'clips': {'pause1': {}}}, 'a_ba': {'parent': 'null', 'clips': {'walk': {}}},
          'pmd0': {'parent': 'a_ba', 'clips': {'tlknorm': {}}}, 'pmh0': {'parent': 'a_ba', 'clips': {}}}


class BodySweepClipTests(unittest.TestCase):
    def test_unresolved_clips_name_the_target_or_donor_chain(self):
        self.assertEqual(bs.unresolved_clips(MODELS, ['pfd0'], ['pause1', 'walk']), [])
        self.assertEqual(bs.unresolved_clips(MODELS, ['pfd0'], ['wlak']), ['pfd0:wlak', 'pfh0:wlak'])
        # A clip only the target owns is missing from its donor.
        self.assertEqual(bs.unresolved_clips(MODELS, ['pmd0'], ['tlknorm']), ['pmh0:tlknorm'])

    def test_an_explicit_unresolvable_clip_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root/'contract.json'; output = root/'out'
            manifest.write_text(json.dumps({'version': '1.1.0', 'targets': [{'modelPrefix': 'pfd0'}, {'modelPrefix': 'pfh0'}],
                                            'resources': []}))
            with patch.object(bs, 'consumed', return_value=[]), patch.object(bs.lib, 'stock_files', return_value=({}, {})), \
                    patch.object(bs.lib, 'release_models', return_value=(MODELS, None)), patch.object(bs, 'body') as body:
                with self.assertRaisesRegex(ValueError, 'Requested clip cannot be resolved: pfd0:wlak, pfh0:wlak'):
                    bs.sweep(root, manifest, output, ['pfd0'], stock_manifest=root/'stock.json', with_motion=True, clips=['wlak'])
                body.assert_not_called()
            self.assertFalse(output.exists())


class LineageDropTests(unittest.TestCase):
    def test_meshes_on_either_side_only_are_reported(self):
        import numpy as np
        mesh = lambda part, name: {'part': part, 'name': name, 'position': np.zeros((3, 3)), 'faces': np.array([[0, 1, 2]])}
        source = [mesh('neck', 'neckg'), mesh('head', 'head001g'), mesh('head', 'eyes')]
        candidate = [mesh('neck', 'neckg'), mesh('head', 'head001g'), mesh('chest', 'extra')]
        keep_s, keep_c, dropped = bs.aligned(source, candidate)
        self.assertEqual([m['name'] for m in keep_s], ['neckg', 'head001g']); self.assertEqual(len(keep_c), 2)
        self.assertEqual(dropped, ['chest/extra', 'head/eyes (source only)'])

    def test_partial_lineage_makes_the_link_unavailable_and_fails_the_aggregates(self):
        import numpy as np
        mesh = lambda part, name: {'part': part, 'name': name, 'position': np.zeros((3, 3)), 'faces': np.array([[0, 1, 2]])}
        measured = lambda parts: {'parts': parts, 'status': 'measured', 'sourceCalibratedClearanceGate': True, 'candidateActualContact': True}
        minimum = {'connectors': [measured(['chest', 'pelvis']), measured(['shinl', 'footl'])],
                   'allRequiredSourceCalibratedTerminalGates': True, 'allRequiredTerminalContacts': True}
        source = {'meshes': [mesh('pelvis', 'p0'), mesh('pelvis', 'p3'), mesh('chest', 'c0')], 'frames': {}}
        candidate = {'meshes': [mesh('pelvis', 'p0'), mesh('chest', 'c0')], 'frames': {}}
        with patch.object(bs.terminal, 'audit_minimum', return_value=minimum), patch.object(bs.surfaces, 'audit', return_value={}):
            result = bs.connectors(source, candidate, None)['minimum']
        chest, shin = result['connectors']
        self.assertEqual((chest['status'], chest['lineageComplete']), ('unavailable', False))
        self.assertIn('Incomplete mesh lineage for pelvis', chest['reason'])
        self.assertEqual((shin['status'], shin['lineageComplete']), ('measured', True))
        self.assertFalse(result['allRequiredSourceCalibratedTerminalGates']); self.assertFalse(result['allRequiredTerminalContacts'])


class MotionCollisionTests(unittest.TestCase):
    def test_the_worst_collision_is_kept_apart_from_the_clearance_extreme(self):
        import numpy as np
        foot = {'part': 'footl', 'name': 'f', 'position': np.zeros((3, 3)), 'faces': np.array([[0, 1, 2]])}
        b = {'prefix': 'pmd0', 'meshes': [foot], 'frames': {'j': np.eye(4)}, 'scale': 1.}
        donor = {'prefix': 'pmh0', 'meshes': [dict(foot)], 'frames': {'j': np.eye(4)}}
        now = {}; ours, theirs = [foot], [dict(foot)]
        def posed(models, prefix, clip, t):
            now['t'] = t; return {}, {'length': 1.}, 'a_ba'
        # Collision at t=0 (2 pairs, no gap); a 5 mm gap and no collision at t=1.
        def contact(meshes, inventory):
            mine = meshes is ours; t = now['t']
            return {'minimumTriangleClearanceMeters': (.005 if t == 1. else 0.) if mine else 0.,
                    'intersectingTrianglePairCount': (2 if t == 0. else 0) if mine else 0}
        with patch.object(bs, 'LINKS', [('shinl', 'footl')]), patch.object(bs, 'sample', return_value={'j': np.eye(4)}), \
                patch.object(bs, 'terminal_inventory', return_value='inv'), patch.object(bs, 'posed_frames', side_effect=posed), \
                patch.object(bs, 'sample_times', return_value=[0., 1.]), patch.object(bs, 'terminal_contact', side_effect=contact), \
                patch.object(bs, 'pose_rigid_meshes', side_effect=lambda meshes, *_: ours if meshes is b['meshes'] else theirs):
            row = bs.motion({'pmd0': {'nodes': {}}}, b, donor, ['walk'])['clips']['walk']['connectors']['shinl-footl']
        self.assertEqual((row['time'], row['intersections'], row['excessMeters']), (1., 0, .005))
        self.assertEqual((row['maxIntersections'], row['maxIntersectionsTime'], row['maxIntersectionsDonor']), (2, 0., 0))


if __name__ == '__main__':
    unittest.main()
