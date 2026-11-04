"""Native area placement preserves both bodies and rejects unusable fixtures."""
import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools.itemkit.fixture import field, place_review_actors, entry_script, audit_module_payload, require_unshadowed


class PlacementTests(unittest.TestCase):
    def test_module_payload_rejects_changed_missing_and_extra_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, extracted = Path(tmp)/'source', Path(tmp)/'extracted'
            source.mkdir(); extracted.mkdir()
            for folder in (source, extracted):
                (folder/'module.ifo').write_bytes(b'bound module')
                (folder/'variant.uti').write_bytes(b'bound variant')
            self.assertTrue(audit_module_payload(source, extracted)['exact'])
            (extracted/'variant.uti').write_bytes(b'changed variant')
            with self.assertRaisesRegex(ValueError, 'payload differs'): audit_module_payload(source, extracted)
            (extracted/'variant.uti').unlink()
            with self.assertRaisesRegex(ValueError, 'payload differs'): audit_module_payload(source, extracted)
            (extracted/'variant.uti').write_bytes(b'bound variant')
            (extracted/'unexpected.utc').write_bytes(b'additional actor')
            with self.assertRaisesRegex(ValueError, 'payload differs'): audit_module_payload(source, extracted)

    def setUp(self):
        self.git = {'__data_type': 'GIT ', '__struct_id': -1, 'Creature List': field('list', [])}
        self.area = {key: field('int', 4) for key in ('Width', 'Height')}
        self.ifo = {f'Mod_Entry_{key}': field('float', value) for key, value in
                    {'X': 12, 'Y': 12, 'Z': 0, 'Dir_X': 0, 'Dir_Y': 1}.items()}
        self.actors = [{'__data_type': 'UTC ', '__struct_id': -1, 'Tag': field('cexostring', tag),
                        'Race': field('byte', 6), 'Gender': field('byte', gender), 'Appearance_Type': field('word', 15100),
                        'BodyPart': field('byte', 7), 'ScriptHeartbeat': field('resref', 'sr_it_hb')}
                       for tag, gender in (('sr_it_male', 0), ('sr_it_female', 1))]

    def test_bound_hak_cannot_shadow_candidate_resources(self):
        class Archive:
            @staticmethod
            def payload(path):
                return {'candidate':{('sr_a',2017):'1',('baseitems',2017):'2'},'other':{('baseitems',2017):'3'},
                        'clean':{('sr_b',2017):'4'}}[path]
        with patch('tools.itemkit.native.archive_helpers',return_value=Archive):
            require_unshadowed({'path':'candidate'},{'path':'clean'},'clean')
            with self.assertRaisesRegex(ValueError,'shadows candidate'):
                require_unshadowed({'path':'candidate'},{'path':'other'},'other')

    def test_both_bodies_embedded_without_mutating_donors(self):
        before = copy.deepcopy(self.actors)
        result = place_review_actors(self.git, self.area, self.ifo, self.actors)
        rows = result['Creature List']['value']
        self.assertEqual([(r['XPosition']['value'], r['YPosition']['value']) for r in rows], [(13.5, 15), (10.5, 15)])
        for row, source in zip(rows, before):
            self.assertNotIn('__data_type', row); self.assertEqual(row['__struct_id'], 4)
            self.assertTrue(all(row[k] == v for k, v in source.items() if not k.startswith('__')))
        self.assertEqual(self.actors, before); self.assertEqual(self.git['Creature List']['value'], [])

    def test_collision_and_outside_area_rejected(self):
        result = place_review_actors(self.git, self.area, self.ifo, self.actors)
        with self.assertRaisesRegex(ValueError, 'collision'):
            place_review_actors(result, self.area, self.ifo, self.actors)
        self.ifo['Mod_Entry_Y']['value'] = 39
        with self.assertRaisesRegex(ValueError, 'outside'):
            place_review_actors(self.git, self.area, self.ifo, self.actors)

    def test_dagger_and_legacy_entry_identity_are_isolated(self):
        knife = entry_script('sr_cfk', True)
        sword = entry_script('sr_cougar')
        self.assertIn('CreateItemOnObject("sr_cfk",actor)', knife)
        self.assertIn('CreateItemOnObject("sr_cougar",pc)', knife)
        self.assertNotIn('sr_cfk', sword)
        with self.assertRaises(ValueError): entry_script('bad"resref')

    def test_shield_equip_and_report_use_offhand(self):
        script = entry_script('sr_shield', equipment_slot='left')
        self.assertIn('ActionEquipItem(item,INVENTORY_SLOT_LEFTHAND)', script)
        self.assertIn('GetItemInSlot(INVENTORY_SLOT_LEFTHAND,actor)', script)
        self.assertIn(' left=', script)
        self.assertNotIn('INVENTORY_SLOT_RIGHTHAND', script)
        self.assertIn('INVENTORY_SLOT_RIGHTHAND', entry_script('sr_blade'))
        with self.assertRaises(ValueError): entry_script('sr_shield', equipment_slot='bad')

    def test_two_comparison_items_are_safe_distinct_and_available(self):
        script = entry_script('sr_cfs', ['sr_cougar', 'sr_cfk'])
        self.assertIn('CreateItemOnObject("sr_cfs",actor)', script)
        for name in ('sr_cougar','sr_cfk'):
            self.assertEqual(script.count('CreateItemOnObject("'+name+'",pc)'),1)
        with self.assertRaises(ValueError): entry_script('sr_cfs',['sr_cfs'])
        with self.assertRaises(ValueError): entry_script('sr_cfs',['sr_cfk','sr_cfk'])


if __name__ == '__main__': unittest.main()
