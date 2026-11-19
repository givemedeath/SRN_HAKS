import copy
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import patch

import numpy as np

from tools.headkit.common import pin, read, write
from tools.itemkit import miss_patch
from tools.itemkit.runner import BEFORE_BAKE, Runner, geometry_hashes, recovery_proofs, stage_manifest_hash
from tools.itemkit.test_itemkit import Fixture

POLICY = {'method': 'nearest-finished-donor', 'maximumDistance': .003, 'minimumNormalAlignment': .5}


def patched(policy, corner_hash, faces=(3,)):
    return {**policy, 'unorientedSourcePatch': {'faces': list(faces), 'maximumDistance': .001, 'reviewed': True,
                                                'targetCornerHash': corner_hash, 'notes': 'Reviewed.'}}


class StageViewTests(unittest.TestCase):
    def test_only_the_stages_before_the_bake_are_blind_to_the_policy(self):
        plain = {'id': 'x', 'processing': {'joinY': [], 'missCorrection': POLICY}}
        other = copy.deepcopy(plain); other['processing']['missCorrection'] = patched(POLICY, 'abc')
        for stage in BEFORE_BAKE: self.assertEqual(stage_manifest_hash(plain, stage), stage_manifest_hash(other, stage))
        for stage in ('bake', 'shadow', 'render', 'export', 'native'):
            self.assertNotEqual(stage_manifest_hash(plain, stage), stage_manifest_hash(other, stage))
        changed = copy.deepcopy(plain); changed['processing']['joinY'] = [.1]
        self.assertNotEqual(stage_manifest_hash(plain, 'fit'), stage_manifest_hash(changed, 'fit'))

    def test_geometry_hashes_are_found_at_any_depth(self):
        self.assertEqual(geometry_hashes({'a': {'geometryCornerHash': 'one'}, 'b': [{'c': {'geometryCornerHash': 'two'}}], 'geometryCornerHash': 3}),
                         {'one', 'two'})


class AdoptionTests(Fixture):
    def setUp(self):
        super().setUp()
        self.runtime = {'toolchain': pin(self.local), 'migrationReceipt': pin(self.local), 'python': pin(sys.executable)}
        for item in (patch('tools.itemkit.runner.python_package_pins', return_value=[]), patch('tools.itemkit.runner.code_pins', return_value=[]),
                     patch('tools.itemkit.runner.source_version', return_value='fixture-version')):
            item.start(); self.addCleanup(item.stop)
        self.data.setdefault('processing', {})['missCorrection'] = dict(POLICY); write(self.path, self.data)
        self.first = Runner(self.path, self.local, self.root/'run-a', runtime=self.runtime)

    @staticmethod
    def compute(stage, folder, **kwargs):
        file = folder/'output.txt'; file.write_text(stage)
        return {'artifact': pin(file), **({'visible': {'geometryCornerHash': 'reduced-geometry'}} if stage == 'reduce' else {})}

    def finish_first(self, stages=('fit', 'reduce', 'unwrap', 'finish'), review=True):
        with patch.object(self.first, '_execute', side_effect=self.compute):
            for stage in stages:
                self.first.execute(stage)
                if review: self.first.review(stage, 'approved', 'Reviewed '+stage)

    def second(self, change=None, corner_hash='reduced-geometry'):
        data = copy.deepcopy(self.data); data['processing']['missCorrection'] = patched(POLICY, corner_hash)
        if change: change(data)
        path = self.path.with_name('asset-patched.json'); write(path, data)
        return Runner(path, self.local, self.root/'run-b', runtime=self.runtime)

    def test_a_patched_manifest_takes_on_the_stages_before_the_bake(self):
        self.finish_first(); runner = self.second()
        self.assertEqual(runner.adopt(self.root/'run-a'), ['fit', 'reduce', 'unwrap', 'finish'])
        self.assertEqual(read(self.root/'run-b'/'adopted.json')['sources'][0]['stages'], ['fit', 'reduce', 'unwrap', 'finish'])
        with patch.object(runner, '_execute', side_effect=AssertionError('an adopted stage ran again')):
            for stage in ('fit', 'reduce', 'unwrap', 'finish'): self.assertTrue(runner.execute(stage)['reused'])
        self.assertEqual(runner.result('finish')['artifact'], self.first.result('finish')['artifact'])
        with patch.object(runner, '_execute', side_effect=self.compute): self.assertFalse(runner.execute('bake')['reused'])

    def test_an_adopted_stage_is_still_verified_when_used(self):
        self.finish_first(); runner = self.second(); runner.adopt(self.root/'run-a')
        Path(self.first.result('reduce')['artifact']['path']).write_text('altered')
        with self.assertRaisesRegex(ValueError, 'Stale'): Runner(runner.manifest_path, self.local, self.root/'run-b', runtime=self.runtime).result('unwrap')

    def test_any_other_difference_adopts_nothing(self):
        self.finish_first()
        def other(data): data['processing']['joinY'] = [.2]
        runner = self.second(other)
        self.assertEqual(runner.adopt(self.root/'run-a'), [])
        self.assertFalse((self.root/'run-b'/'adopted.json').exists())

    def test_a_patch_for_other_geometry_is_refused(self):
        self.finish_first(); runner = self.second(corner_hash='another-geometry')
        self.assertEqual(runner.adopt(self.root/'run-a'), ['fit'])            # the reduce link is refused, and all after it

    def test_an_unreviewed_stage_ends_the_adoption(self):
        self.finish_first(('fit', 'reduce')); self.finish_first(('unwrap',), review=False)
        self.assertEqual(self.second().adopt(self.root/'run-a'), ['fit', 'reduce'])

    def test_an_older_receipt_without_a_stage_view_is_not_adopted(self):
        self.finish_first(('fit',)); row = self.first.state['stages']['fit']; receipt = read(row['path']); del receipt['stageManifestHash']
        Path(row['path']).write_text(json.dumps(receipt)); state = read(self.root/'run-a'/'state.json')
        state['stages']['fit'] = pin(row['path']); write(self.root/'run-a'/'state.json', state)
        self.assertEqual(self.second().adopt(self.root/'run-a'), [])

    def test_recovery_proofs_come_from_adopted_runs_only(self):
        self.finish_first(); runner = self.second()
        proof = self.root/'run-a'/'bake'/'attempt-1'/'worker'/'bake-recovery.json'; proof.parent.mkdir(parents=True); proof.write_text('{}')
        self.assertEqual(recovery_proofs(self.root/'run-b'), [])
        runner.adopt(self.root/'run-a')
        self.assertEqual(recovery_proofs(self.root/'run-b'), [proof.resolve()])        # adoption records the run's resolved path
        self.assertIsNone(runner.recoverable_bake(self.first.result('finish')['artifact']['path']))     # not a valid proof


class AdoptedRunLookupTests(unittest.TestCase):
    def test_a_stage_adopted_from_another_run_is_found_through_the_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); attempt = root/'run-a'/'unwrap'/'attempt-1'; (attempt/'atlas').mkdir(parents=True)
            target = attempt/'atlas'/'final-atlas.npz'; np.savez(target, x=np.zeros(1)); (attempt/'receipt.json').write_text('{}')
            run = root/'run-b'; run.mkdir()
            (run/'state.json').write_text(json.dumps({'stages': {'unwrap': {'path': str(attempt/'receipt.json'), 'sha256': 'x'}}}))
            found = miss_patch._one(run, ('unwrap/attempt-*/atlas/final-atlas.npz',), None, 'unwrap arrays', '--arrays')
            self.assertEqual(found, target)
            with self.assertRaisesRegex(ValueError, 'no fit results'): miss_patch._one(run, ('fit/attempt-*/worker/result.json',), None, 'fit results', '--fit')


class ScreenedChainTests(unittest.TestCase):
    STAGES = ['fit', 'reduce', 'unwrap', 'finish', 'bake', 'shadow']

    def driver(self, screen):
        from tools.itemkit import drive
        with tempfile.TemporaryDirectory() as tmp:
            workspace = unittest.mock.Mock(handoff=Path(tmp), items=Path(tmp))
            item = drive.Driver(workspace); calls = []
            def launch(design, run, name, inputs, command, **more):
                stages = command[command.index('--stages')+1:command.index('--notes')]; calls.append(stages)
                return '', '\n'.join(json.dumps({'stage': stage, 'seconds': 1}) for stage in stages), 'launch'
            with patch.object(item, 'launch', side_effect=launch), patch.object(item, 'screen_before_bake', return_value=screen):
                return item.chain('sr4-x', 'v1', self.STAGES), calls

    def test_a_clean_screen_goes_on_to_the_bake(self):
        result, calls = self.driver({'failedCount': 0, 'failedFaces': []})
        self.assertEqual(calls, [self.STAGES[:4], self.STAGES]); self.assertNotIn('failed', result)
        self.assertEqual([row['stage'] for row in result['stages']], self.STAGES)

    def test_a_missed_face_stops_before_the_bake(self):
        result, calls = self.driver({'failedCount': 2, 'failedFaces': [7, 9]})
        self.assertEqual(calls, [self.STAGES[:4]]); self.assertIn('--faces 7,9', result['failed'])

    def test_a_failure_after_the_screen_keeps_the_first_launch(self):
        from tools.itemkit import drive
        with tempfile.TemporaryDirectory() as tmp:
            item = drive.Driver(unittest.mock.Mock(handoff=Path(tmp), items=Path(tmp)))
            def launch(design, run, name, inputs, command, **more):
                if 'bake' in command: raise SystemExit('Blender worker failed')
                return '', '\n'.join(json.dumps({'stage': stage, 'seconds': 1}) for stage in self.STAGES[:4]), 'launch'
            with patch.object(item, 'launch', side_effect=launch), patch.object(item, 'screen_before_bake', return_value={'failedCount': 0}):
                result = item.chain('sr4-x', 'v1', self.STAGES)
        self.assertEqual((len(result['stages']), result['screen'], result['failed']), (4, {'failedCount': 0}, 'Blender worker failed'))

    def test_a_screen_that_cannot_run_never_stops_the_chain(self):
        result, calls = self.driver({'skipped': 'no donor'})
        self.assertEqual(len(calls), 2); self.assertNotIn('failed', result)
