"""An authorized budget increase cannot erase jobs, race dispatch or reset a trial."""
import tempfile
import copy
import unittest
from pathlib import Path
from tools.headkit.common import read, write, digest
from tools.itemkit.generation import initialize_trial, set_trial_limit
from tools.headkit.generation import apply_geometry_seed_offset


class TrialPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.ledger = self.root/'ledger.json'
        self.evidence = self.root/'authorization.json'; self.output = self.root/'change'
        self.state = {'schemaVersion': 1, 'priorGenerationAttempts': 0,
                      'reconciliation': 'Original authorization',
                      'itemTrial': {'id': 'trial', 'maximumGeometryAttempts': 2},
                      'jobs': [{'token': 'old-1', 'stage': 'geometry', 'state': 'complete'},
                               {'token': 'old-2', 'stage': 'geometry', 'state': 'not-found'}]}
        write(self.ledger, self.state)
        write(self.evidence, {'scope': 'all-items', 'maximumGeometryAttempts': 5,
                              'authorization': 'Increase the attempt limit for this and future items to 5'})

    def change(self, **kwargs):
        return set_trial_limit(self.ledger, kwargs.get('trial', 'trial'), kwargs.get('maximum', 5),
                               self.evidence, self.output)

    def test_upgrade_retains_complete_history_and_snapshots(self):
        result = self.change(); current = read(self.ledger)
        self.assertEqual(read(self.output/'before.json'), self.state)
        self.assertEqual(read(self.output/'after.json'), current)
        self.assertEqual(current['jobs'], self.state['jobs'])
        self.assertEqual(current['reconciliation'], self.state['reconciliation'])
        self.assertEqual(current['itemTrial']['maximumGeometryAttempts'], 5)
        self.assertEqual(result['jobsUnchangedSha256'], digest(self.state['jobs']))
        self.assertEqual(len(current['itemTrial']['limitChanges']), 1)
        self.assertEqual(read(self.output/'receipt.json'), result)

    def test_pending_job_wrong_trial_and_unsupported_limit_leave_bytes_unchanged(self):
        for state in ('intent', 'submitted', 'timed-out'):
            with self.subTest(state=state):
                self.state['jobs'][0]['state'] = state; write(self.ledger, self.state)
                before = self.ledger.read_bytes()
                with self.assertRaisesRegex(ValueError, 'Reconcile'): self.change()
                self.assertEqual(self.ledger.read_bytes(), before)
                self.assertFalse(self.output.exists())
        self.state['jobs'][0]['state'] = 'complete'; write(self.ledger, self.state)
        for kwargs in ({'trial': 'other'}, {'maximum': 6}, {'maximum': True}):
            with self.subTest(kwargs=kwargs):
                before = self.ledger.read_bytes()
                with self.assertRaises(ValueError): self.change(**kwargs)
                self.assertEqual(self.ledger.read_bytes(), before)

    def test_missing_authorization_or_receipt_collision_cannot_modify_ledger(self):
        before = self.ledger.read_bytes()
        write(self.evidence, {'scope': 'all-items', 'maximumGeometryAttempts': 5, 'authorization': ''})
        with self.assertRaisesRegex(ValueError, 'authorization'): self.change()
        self.assertEqual(self.ledger.read_bytes(), before)
        write(self.evidence, {'scope': 'all-items', 'maximumGeometryAttempts': 5, 'authorization': 'Approved'})
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh'): self.change()
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_upgrade_cannot_be_repeated_and_new_trials_default_to_five(self):
        self.change(); after = self.ledger.read_bytes(); self.output = self.root/'second-change'
        with self.assertRaisesRegex(ValueError, 'never reset'): self.change()
        self.assertEqual(self.ledger.read_bytes(), after)
        new = self.root/'new.json'; initialize_trial(new, 'new', 'Five attempts approved')
        self.assertEqual(read(new)['itemTrial']['maximumGeometryAttempts'], 5)
        with self.assertRaises(FileExistsError): initialize_trial(new, 'replacement', 'Cannot reset')

    def test_seed_offset_changes_only_three_noise_seeds(self):
        graph=read(Path(__file__).parents[1]/'headkit/templates/geometry.json')
        before=copy.deepcopy(graph);apply_geometry_seed_offset(graph,1009)
        changed=[]
        for key,node in graph.items():
            if node['class_type']=='KSampler':
                self.assertEqual(node['inputs']['seed'],before[key]['inputs']['seed']+1009)
                changed.append(key);node['inputs']['seed']-=1009
        self.assertEqual(len(changed),3);self.assertEqual(graph,before)
        self.assertEqual(apply_geometry_seed_offset(copy.deepcopy(before),0),before)
        for bad in (-1,True,1.5,2147483648):
            with self.assertRaises(ValueError):apply_geometry_seed_offset(copy.deepcopy(before),bad)
        incomplete=copy.deepcopy(before);del incomplete[changed[0]]
        with self.assertRaises(ValueError):apply_geometry_seed_offset(incomplete,1)


if __name__ == '__main__': unittest.main()
