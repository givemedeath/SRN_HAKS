"""Regression coverage for connector coverage, rig routing and frozen staging."""
import contextlib
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import derive_rig
import derived_review_configs as review
import stock_dwarf_control as controls
from derived_matrix import load_matrix, evaluate_target_eligibility
from test_derived_stock_controls import TABLE


class ConnectorCoverageTests(unittest.TestCase):
    def evaluate(self, parent, child, moved=False):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ('parent.mdl', 'child.mdl')]
            for path in paths:
                path.write_text('fixture')
            standing = {'clip': 'pause1', 'time': 0, 'label': 'standing', 'standing': True}
            frames = [(standing, {'p': np.eye(4), 'c': np.eye(4)})]
            if moved:
                motion = np.eye(4)
                motion[0, 3] = .3
                frames.append(({'clip': 'run', 'time': .3, 'label': 'motion'}, {'p': np.eye(4), 'c': motion}))
            with patch.object(review, 'arrays', side_effect=[parent, child]):
                return review.evaluate_connector_motion(*paths, 'p', 'c', Path(folder), posed_frames=frames)

    def test_one_touching_pair_cannot_hide_detached_ring(self):
        parent = np.array(list(itertools.product([-.02, .02], repeat=3)))
        child = parent.copy()
        child[1:, 0] += .02
        result = self.evaluate(parent, child)
        self.assertTrue(result['samples'][0]['has3DOverlap'])
        self.assertEqual(result['samples'][0]['minSurfaceDistanceMeters'], 0)
        self.assertGreaterEqual(result['worstMotionSurfaceDistance'], .02)
        self.assertFalse(result['allPosesPassed'])

    def test_reverse_coverage_and_empty_interface_fail(self):
        result = review.connector_vertex_distances(np.zeros((1, 3)), np.array([[0, 0, 0], [.03, 0, 0]]))
        self.assertEqual(result['parentCoverage'], 1)
        self.assertEqual(result['childCoverage'], .5)
        self.assertEqual(result['maximum'], .03)
        self.assertEqual(review.connector_vertex_distances(np.empty((0, 3)), np.zeros((1, 3)))['parentCoverage'], 0)

    def test_matching_ring_passes_and_motion_retains_interface_membership(self):
        ring = np.array(list(itertools.product([-.02, .02], repeat=3)))
        self.assertTrue(self.evaluate(ring, ring)['allPosesPassed'])
        result = self.evaluate(ring, ring, moved=True)
        self.assertFalse(result['allPosesPassed'])
        self.assertEqual(result['samples'][1]['childInterfaceVertexCount'], 8)
        self.assertGreater(result['worstMotionSurfaceDistance'], .25)
        self.assertEqual(result['worstMotionClip'], 'run')


class RigAndAcceptanceTests(unittest.TestCase):
    def test_human_and_dwarf_defaults_and_explicit_overrides(self):
        receipt = dict(nodeCount=1, supermodel='a', animationSupermodel='b', animationScale=1, maxJointDeviationMeters=0)
        for race, prefix in [('human', 'pmh0'), ('dwarf', 'pmd0')]:
            with self.subTest(race=race), patch.object(sys, 'argv', ['derive_rig.py', '--race', race]), patch.object(derive_rig, 'derive_stock_family_rig', return_value=receipt) as derive, contextlib.redirect_stdout(io.StringIO()):
                derive_rig.main()
                self.assertEqual(derive.call_args.args[1].name, prefix + '.mdl')
                self.assertEqual(derive.call_args.args[2].name, race + '-male')
        with patch.object(sys, 'argv', ['derive_rig.py', '--race', 'human', '--stock-root', 'custom.mdl', '--output-dir', 'custom']), patch.object(derive_rig, 'derive_stock_family_rig', return_value=receipt) as derive, contextlib.redirect_stdout(io.StringIO()):
            derive_rig.main()
            self.assertEqual(derive.call_args.args[1:], (Path('custom.mdl'), Path('custom')))

    def test_troll_aliases_allow_work_without_acceptance(self):
        matrix = load_matrix()
        for target in ['troll-male-fit', 'gnome-male-fit']:
            self.assertFalse(matrix['targets'][target]['productionAccepted'])
            eligible, reason = evaluate_target_eligibility(matrix, target)
            self.assertTrue(eligible)
            self.assertIn('pending', reason)


class FrozenStockInputsTests(unittest.TestCase):
    def test_snapshot_staging_and_changes_during_compilation(self):
        for mutation in [None, 'snapshot', 'live']:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                stage = Path(folder)
                manifest = stage / 'manifest.json'
                manifest.write_text(json.dumps({'combinations': []}))
                appearance = stage / 'fixture-resources/appearance.2da'
                appearance.parent.mkdir()
                appearance.write_text(TABLE)
                snapshots = [stage / 'input-manifest.json', stage / 'input-appearance.2da']
                for live, snapshot in zip([manifest, appearance], snapshots):
                    snapshot.write_bytes(live.read_bytes())
                originals = [p.read_bytes() for p in snapshots]
                def extract(name, *args):
                    if name == 'appearance.2da':
                        return TABLE.encode()
                    return b'newmodel pmd0\nbitmap pmd0\n' if name.endswith('.mdl') else b'palette'
                def compile_models(*args, **kwargs):
                    if mutation:
                        (snapshots[0] if mutation == 'snapshot' else manifest).write_text('{}')
                with patch.object(controls, 'extract_stock_resource', side_effect=extract), patch.object(controls.subprocess, 'run', side_effect=compile_models), contextlib.redirect_stdout(io.StringIO()):
                    if mutation:
                        with self.assertRaisesRegex(ValueError, 'changed during compilation'):
                            controls.stage_stock_control(stage, stage, stage / 'client', manifest_input=snapshots[0], appearance_input=snapshots[1])
                        self.assertEqual(appearance.read_bytes(), originals[1])
                    else:
                        controls.stage_stock_control(stage, stage, stage / 'client', manifest_input=snapshots[0], appearance_input=snapshots[1])
                        self.assertEqual([p.read_bytes() for p in snapshots], originals)
                        self.assertEqual(len(json.loads(manifest.read_text())['combinations']), 1)
                        with self.assertRaisesRegex(ValueError, 'differs from live stage'):
                            controls.stage_stock_control(stage, stage, stage / 'client', manifest_input=snapshots[0], appearance_input=snapshots[1])


if __name__ == '__main__':
    unittest.main()
