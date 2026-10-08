"""Opt-in child ownership and unbroken legacy stock-source boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pack_stock_target_fixture as packer
import target_contract as contract


class TransitionConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module = self.root/'candidate.mod'
        self.module.write_bytes(b'actual source module')
        self.proof_path = self.root/'proof.json'
        proof = {'nativeModule': {'path': str(self.module), 'sha256': contract.sha(self.module)},
            'fixtureResourceHashes': {'sr_tm.set': 'a'*64}, 'stockTableBaselines': {'appearance.2da': 'stock'}}
        self.proof_path.write_text(json.dumps(proof))
        self.pin = {'path': str(self.proof_path), 'sha256': contract.sha(self.proof_path)}
        self.authority = {'path': str(self.root/'selected.json'), 'sha256': 'b'*64}
        self.basis = {'path': str(self.root/'stock.json'), 'sha256': 'c'*64}
        self.prepared = {'sourceProof': self.pin, 'transitionSourceProof': self.pin,
            'transitionAnimationAuthority': self.authority, 'postureStockBinding': self.basis,
            'postureRoster': {'path': str(self.root/'roster.json'), 'sha256': 'd'*64},
            'moduleSha256': contract.sha(self.module), 'moduleResourceHashes': {'enter.ncs': 'e'*64},
            'fixtureResourceHashes': proof['fixtureResourceHashes'], 'stockTableBaselines': proof['stockTableBaselines']}
        self.report = {'kind': 'verified-shared-female-transition-source',
            'moduleResourceHashes': self.prepared['moduleResourceHashes'],
            'postureRoster': self.prepared['postureRoster'], 'postureStockBinding': self.basis,
            'clientAccepted': False}

    def run_child(self, **changes):
        prepared = copy.deepcopy(self.prepared)
        prepared.update(changes)
        return packer.verified_posture_source(self.basis, self.root/'target.json', prepared,
            self.root, self.module, self.root/'gff.exe', self.root,
            self.pin, self.authority)

    def test_old_source_uses_original_strict_guard(self):
        old = {k: v for k, v in self.prepared.items() if not k.startswith('transition')}
        with patch.object(packer, 'verified_posture_stock_basis', return_value={'original': True}) as legacy:
            result = packer.verified_posture_source(self.basis, self.root/'target.json', old,
                self.root, self.module, self.root/'gff.exe', self.root)
        self.assertEqual(result, {'original': True})
        legacy.assert_called_once()

    def test_declared_child_cannot_silently_use_legacy_path(self):
        with patch.object(packer, 'verified_posture_stock_basis') as legacy, self.assertRaises(ValueError):
            packer.verified_posture_source(self.basis, self.root/'target.json', self.prepared,
                self.root, self.module, self.root/'gff.exe', self.root)
        legacy.assert_not_called()

    def test_explicit_child_binds_independent_authority_and_actual_module(self):
        with patch('shared_female_transition_fixture.verify_source', return_value=self.report) as verifier:
            result = self.run_child()
        self.assertFalse(result['clientAccepted'])
        self.assertEqual(verifier.call_args.kwargs['selected_overlay_pin'], self.authority)

    def test_missing_cross_source_and_foreign_authority_fail_before_verifier(self):
        for change in ({'transitionSourceProof': None}, {'sourceProof': None},
                       {'transitionAnimationAuthority': {'path': 'foreign', 'sha256': 'f'*64}},
                       {'postureStockBinding': None}):
            with self.subTest(change=change), patch('shared_female_transition_fixture.verify_source') as verifier:
                with self.assertRaises(ValueError): self.run_child(**change)
                verifier.assert_not_called()

    def test_actual_module_mutation_and_changed_fixture_tables_reject(self):
        with patch('shared_female_transition_fixture.verify_source', return_value=self.report):
            for change in ({'moduleSha256': 'f'*64}, {'fixtureResourceHashes': {}}, {'stockTableBaselines': {}}):
                with self.subTest(change=change), self.assertRaises(ValueError): self.run_child(**change)
            self.module.write_bytes(b'edited native module')
            with self.assertRaises(ValueError): self.run_child()

    def test_stale_proof_and_mismatched_verified_scene_reject(self):
        with patch('shared_female_transition_fixture.verify_source', return_value=self.report):
            self.proof_path.write_text('{}')
            with self.assertRaises(ValueError): self.run_child()
        for field in ('postureRoster', 'postureStockBinding', 'moduleResourceHashes'):
            bad = copy.deepcopy(self.report); bad[field] = {}
            with self.subTest(field=field), patch('shared_female_transition_fixture.verify_source', return_value=bad):
                with self.assertRaises(ValueError): self.run_child()


class MatchedTransitionBoundaryTests(unittest.TestCase):
    def test_both_sides_and_independent_proof_are_required(self):
        from shared_female_posture_fixture import matched_transition_binding
        proof={'path':'source-proof.json','sha256':'a'*64}
        authority={'path':'approved-overlay.json','sha256':'b'*64}
        build={'transitionSourceProof':proof,'postureSourceProof':proof,
            'transitionAnimationAuthority':authority,'sourcePreparation':{'path':'parent.json','sha256':'c'*64}}
        self.assertTrue(matched_transition_binding(build,copy.deepcopy(build),proof,authority))
        self.assertFalse(matched_transition_binding({}, {}, None, authority))
        for stock,candidate,requested in ((build,build,None), ({},build,proof),
                (build,{**build,'postureSourceProof':None},proof),
                (build,{**build,'transitionAnimationAuthority':None},proof),
                (build,{**build,'sourcePreparation':None},proof)):
            with self.subTest(stock=stock,candidate=candidate,requested=requested),self.assertRaises(ValueError):
                matched_transition_binding(stock,candidate,requested,authority)


if __name__ == '__main__':
    unittest.main()
