"""Client package guards: identity/tables, shared ownership and userdir isolation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import target_contract as contract
from preflight_target_body_client import audit_tables, aliases, native_group, validate_payload
from test_target_part_pipeline import target_fixture


class TargetPreflightTests(unittest.TestCase):
    def baselines(self, root):
        payload = {'appearance.2da':b'2DA V2.0\n\nLABEL MODELTYPE RACE SIZECATEGORY HELMET_SCALE_F\n2 Gnome P G 2 .82\n6 Human P H 3 .85\n',
                   'racialtypes.2da':b'2DA V2.0\n\nLabel Name Appearance StrAdjust FeatsTable\n2 Gnome 26 2 -2 RACE_FEAT_GNOME\n6 Human 34 6 0 RACE_FEAT_HUMAN\n',
                   'phenotype.2da':b'2DA V2.0\n\nLabel Default\n0 Normal 0\n2 Large 0\n'}
        pins = {}
        for name,data in payload.items():
            path = root/name; path.write_bytes(data); pins[name] = {'path':str(path),'sha256':contract.sha(path)}
        payload['appearance.2da'] = payload['appearance.2da'].replace(b'Gnome P G 2',b'Troll P G 4')
        payload['racialtypes.2da'] = payload['racialtypes.2da'].replace(b'Gnome 26',b'Troll 16777217')
        return payload,pins

    def test_target_mapping_and_large_size_preserve_gameplay_and_human(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload,pins = self.baselines(Path(temporary)); report = audit_tables(payload,target_fixture(),pins)
            self.assertTrue(report['phenotype.2da']['unchanged'])
            self.assertTrue(report['appearance.2da']['otherInstalledRowsExact'])
            mutations = [('appearance.2da',b'Human P H 3',b'Human P H 4'),
                         ('appearance.2da',b'Troll P G 4',b'Troll P H 4'),
                         ('appearance.2da',b'Troll P G 4 .82',b'Troll P G 4 1.2'),
                         ('racialtypes.2da',b'2 -2 RACE_FEAT_GNOME',b'2 4 RACE_FEAT_TROLL'),
                         ('phenotype.2da',b'Normal 0',b'Normal 2')]
            for name,before,after in mutations:
                bad = dict(payload); bad[name] = bad[name].replace(before,after)
                with self.subTest(table=name,change=after),self.assertRaises(ValueError): audit_tables(bad,target_fixture(),pins)

    def test_declared_comparison_rows_and_missing_tables(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload,pins = self.baselines(Path(temporary))
            payload['appearance.2da'] += b'15100 StockHuman P X 3 .85\n'
            with self.assertRaisesRegex(ValueError,'Undeclared fixture'):
                audit_tables(payload,target_fixture(),pins)
            audit_tables(payload,target_fixture(),pins,[15100])
            del payload['phenotype.2da']
            with self.assertRaisesRegex(ValueError,'Required target table missing'):
                audit_tables(payload,target_fixture(),pins,[15100])

    def test_exact_packed_ownership_rejects_human_female_and_shared_overrides(self):
        data = b'actual-payload'; digest = hashlib.sha256(data).hexdigest()
        rows = [('pmg0_chest001',2002,data)]
        self.assertEqual(validate_payload(rows,{'body':{'pmg0_chest001.mdl':digest}}),{'pmg0_chest001.mdl'})
        for name in ['pmh0_chest001','pfg0','a_ba']:
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'override packed'):
                validate_payload([(name,2002,data)],{'body':{name+'.mdl':digest}})
        with self.assertRaisesRegex(ValueError,'exact declared'):
            validate_payload(rows+[('unknown',2002,data)],{'body':{'pmg0_chest001.mdl':digest}})
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            validate_payload(rows,{'body':{'pmg0_chest001.mdl':digest},'equipment':{'pmg0_chest001.mdl':digest}})

    def test_native_group_source_dependencies_and_client_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); (folder/'ascii').mkdir(); (folder/'resources').mkdir()
            source = folder/'ascii/pmg0.mdl'; source.write_bytes(b'ASCII-source')
            model = folder/'resources/pmg0.mdl'; model.write_bytes(b'\0\0\0\0native-data')
            receipt = folder/'native-compile.json'
            record = {'complete':True,'clientSha256':'pinned-client','materialResourceHashes':{},
                      'models':[{'name':'pmg0.mdl','sourceSha256':contract.sha(source),
                                 'binarySha256':contract.sha(model),'bytes':model.stat().st_size}]}
            receipt.write_text(json.dumps(record)); pin = contract.sha(receipt)
            self.assertEqual(native_group(folder,pin,'pinned-client',{'pmg0.mdl'}),{'pmg0.mdl':contract.sha(model)})
            with self.assertRaisesRegex(ValueError,'compiler differs'):
                native_group(folder,pin,'wrong-client',{'pmg0.mdl'})
            source.write_bytes(b'changed-source')
            with self.assertRaisesRegex(ValueError,'Stale native'):
                native_group(folder,pin,'pinned-client',{'pmg0.mdl'})

    def test_isolated_aliases_and_empty_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); (root/'override').mkdir()
            values = {'HD0':'','HAK':'hak','MODULES':'modules','OVERRIDE':'override','LOGS':'logs',
                      'CURRENTGAME':'currentgame','MODELCOMPILER':'modelcompiler'}
            (root/'nwn.ini').write_text('[Alias]\n'+'\n'.join(name+'='+str(root/path) for name,path in values.items()))
            aliases(root)
            (root/'override/stale.mdl').write_bytes(b'stale')
            with self.assertRaisesRegex(ValueError,'override must be empty'): aliases(root)


if __name__ == '__main__': unittest.main()
