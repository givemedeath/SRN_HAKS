"""Declared Troll body ownership remains separate from immutable Human guards."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import target_contract as contract
from target_body_inventory import expected_body_resources, validate_body_ownership, compose
from test_target_part_pipeline import target_fixture


class TargetBodyInventoryTests(unittest.TestCase):
    def test_exact_namespace_complete_and_pelvis_garment(self):
        target = target_fixture(); parts = contract.BODY_PARTS
        models = {contract.model(target,part)+'.mdl':part for part in parts}
        resources = expected_body_resources(target,parts,{'pelvis'})
        self.assertEqual(validate_body_ownership(target,models,resources,True,{'pelvis'}),parts)
        for extra in ['pmh0_chest001.mdl','pfg0.mdl','a_ba.mdl','pmg0.mdl','appearance.2da','pmg0_handr001f.tga']:
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'undeclared'):
                validate_body_ownership(target,models,resources|{extra},True,{'pelvis'})
        with self.assertRaisesRegex(ValueError,'only to pelvis'):
            expected_body_resources(target,parts,{'chest'})
        with self.assertRaisesRegex(ValueError,'Complete body'):
            validate_body_ownership(target,models,resources,False,{'pelvis'})

    def test_diagnostics_can_stage_pilot_side_without_accepting_bilateral_body(self):
        target = target_fixture(); parts = {'chest','bicepl'}
        models = {contract.model(target,part)+'.mdl':part for part in parts}
        resources = expected_body_resources(target,parts,set())
        validate_body_ownership(target,models,resources,False,diagnostic=True)
        with self.assertRaisesRegex(ValueError,'opposite pairs'):
            validate_body_ownership(target,models,resources,False)
        bad = dict(models); bad['pmg0_bicepl002.mdl'] = bad.pop('pmg0_bicepl001.mdl')
        with self.assertRaisesRegex(ValueError,'namespace'):
            validate_body_ownership(target,bad,resources,False,diagnostic=True)

    def test_new_target_does_not_relax_historical_human_inventory(self):
        from effective_body_contract import validate_body_ownership as human_ownership
        target = target_fixture(); parts = contract.BODY_PARTS
        models = {contract.model(target,part)+'.mdl':part for part in parts}
        with self.assertRaisesRegex(RuntimeError,'namespace'):
            human_ownership(models,expected_body_resources(target,parts,{'pelvis'}),True)

    def test_composition_preserves_inputs_and_rejects_changed_stages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target_path = root/'target.json'
            target = target_fixture(); target_path.write_text(json.dumps(target))
            folder = root/'part'; (folder/'resources').mkdir(parents=True); (folder/'ascii').mkdir()
            model = 'pmg0_chest001'; ascii_path = folder/'ascii'/(model+'.mdl')
            ascii_path.write_bytes(b'authored-positions-normals-uv')
            for name in expected_body_resources(target,{'chest'},set())-{model+'.mdl'}:
                (folder/'resources'/name).write_bytes(('authored-'+name).encode())
            hashes = {path.name:contract.sha(path) for path in (folder/'resources').iterdir()}
            receipt = {'schemaVersion':2,'kind':'target-part-stage',**contract.binding(target_path,target,'working'),
                       'part':'chest','statureApplications':0,'materialRoles':{'0':'skin'},
                       'asciiModel':str(ascii_path),'asciiModelSha256':contract.sha(ascii_path),
                       'materialResourceHashes':hashes,'frozenInputs':{}}
            path = folder/'target-stage.json'; path.write_text(json.dumps(receipt))
            result = compose(target_path,[path],root/'composed','working')
            composition = json.loads(result.read_text())
            self.assertEqual(composition['asciiModelHashes'][model+'.mdl'],contract.sha(ascii_path))
            self.assertEqual(composition['materialResourceHashes'],hashes)
            self.assertTrue(composition['diagnosticOnly']); self.assertFalse(composition['nativeCompiled'])
            self.assertFalse(composition['completeBodyComposed']); self.assertFalse(composition['productionAccepted'])
            (folder/'resources'/(model+'n.tga')).write_bytes(b'wrong-normal')
            with self.assertRaisesRegex(ValueError,'inventory differs'):
                compose(target_path,[path],root/'wrong','working')

    def test_complete_composition_cannot_bypass_pilot_freeze(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); target_path = root/'target.json'; target = target_fixture()
            target_path.write_text(json.dumps(target)); receipts = []
            for part in sorted(contract.BODY_PARTS):
                folder = root/part; (folder/'resources').mkdir(parents=True); (folder/'ascii').mkdir()
                model = contract.model(target,part); ascii_path = folder/'ascii'/(model+'.mdl'); ascii_path.write_bytes(b'source')
                garments = {'pelvis'} if part == 'pelvis' else set()
                for name in expected_body_resources(target,{part},garments)-{model+'.mdl'}:
                    (folder/'resources'/name).write_bytes(b'dependencies')
                receipt = {'schemaVersion':2,'kind':'target-part-stage',**contract.binding(target_path,target,'runtime'),
                           'part':part,'statureApplications':1,'materialRoles':{'0':'skin',**({'1':'garment'} if garments else {})},
                           'asciiModel':str(ascii_path),'asciiModelSha256':contract.sha(ascii_path),
                           'materialResourceHashes':{path.name:contract.sha(path) for path in (folder/'resources').iterdir()},'frozenInputs':{}}
                path = folder/'target-stage.json'; path.write_text(json.dumps(receipt)); receipts.append(path)
            with self.assertRaisesRegex(ValueError,'pilot must freeze'):
                compose(target_path,receipts,root/'too-soon',require_complete=True)
            self.assertFalse((root/'too-soon').exists())


if __name__ == '__main__': unittest.main()
