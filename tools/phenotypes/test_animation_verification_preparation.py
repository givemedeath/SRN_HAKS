"""Prepared proof reuse stays bound to unchanged bytes and one target/selection."""
import copy,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import target_contract as contract
import shared_female_animation_overlay as overlay
from animation_verification_preparation import AnimationVerificationPreparation

class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.target=self.root/'target.json';self.target.write_text('{}')
        self.receipt=self.root/'overlay.json';self.receipt.write_text('{}')
        self.input=self.root/'selected.mdl';self.input.write_bytes(b'protected native bytes')
        self.pin={'path':str(self.receipt),'sha256':contract.sha(self.receipt)}
        self.report={'kind':'verified-shared-female-source-native-animation-overlay','resourceHashes':{'pfh0.mdl':'a'*64},
            'frozenInputs':{str(self.input):contract.sha(self.input)},'clientAccepted':False,'runtimeSelected':False,'productionAccepted':False}
        self.loader=patch.object(contract,'load',return_value={'rig':{'revision':'stock-v1'}});self.loader.start();self.addCleanup(self.loader.stop)
        self.target_guard=patch.object(overlay,'require_target');self.target_guard.start();self.addCleanup(self.target_guard.stop)
    def make(self):return AnimationVerificationPreparation(self.pin,self.target)
    def test_full_verifier_runs_once_and_reuse_keeps_gates_false(self):
        with patch.object(overlay,'verify_shared_female_animation_overlay',return_value=self.report) as full:
            prep=self.make();a=prep.verify(self.pin,self.target);b=prep.verify(self.pin,self.target)
        self.assertEqual(full.call_count,1);self.assertEqual(a,b);self.assertFalse(b['clientAccepted'])
        self.assertEqual(prep.receipt()['preparationCounts']['all-family-native-overlay-verification'],1)
    def test_caller_cannot_mutate_cached_report(self):
        with patch.object(overlay,'verify_shared_female_animation_overlay',return_value=self.report):
            prep=self.make();a=prep.verify(self.pin,self.target);a['resourceHashes'].clear();a['clientAccepted']=True
            b=prep.verify(self.pin,self.target)
        self.assertEqual(b['resourceHashes'],self.report['resourceHashes']);self.assertFalse(b['clientAccepted'])
    def test_source_drift_invalidates_reuse_without_recomputing(self):
        with patch.object(overlay,'verify_shared_female_animation_overlay',return_value=self.report) as full:
            prep=self.make();prep.verify(self.pin,self.target);self.input.write_bytes(b'changed')
            with self.assertRaises(ValueError):prep.verify(self.pin,self.target)
        self.assertEqual(full.call_count,1)
    def test_cross_target_foreign_selection_and_target_drift_reject(self):
        prep=self.make();foreign=self.root/'foreign.json';foreign.write_text('{}')
        for pin,target in ((self.pin,foreign),({**self.pin,'sha256':'b'*64},self.target)):
            with self.subTest(pin=pin,target=target),self.assertRaises(ValueError):prep.verify(pin,target)
        self.target.write_text('{"changed":true}')
        with self.assertRaises(ValueError):prep.verify(self.pin,self.target)
    def test_input_drift_during_full_verification_never_enters_cache(self):
        prep=self.make()
        def drift(*args,**kwargs):self.input.write_bytes(b'changed');return self.report
        with patch.object(overlay,'verify_shared_female_animation_overlay',side_effect=drift):
            with self.assertRaises(ValueError):prep.verify(self.pin,self.target)
        self.assertEqual(prep.context.counts,{})
    def test_verifier_failure_never_creates_a_prepared_result(self):
        prep=self.make()
        with patch.object(overlay,'verify_shared_female_animation_overlay',side_effect=ValueError('native proof failed')):
            with self.assertRaises(ValueError):prep.verify(self.pin,self.target)
        self.assertEqual(prep.context.counts,{})

if __name__=='__main__':unittest.main()
