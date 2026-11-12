"""Native area placement preserves both bodies and rejects unusable fixtures."""
import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools.itemkit.fixture import (field, place_review_actors, entry_script, audit_module_payload, require_unshadowed,
                                   gff_float, retarget_heartbeat)


class PlacementTests(unittest.TestCase):
    def test_heartbeat_retargets_any_donor_item(self):
        line = 'object blade=GetItemPossessedBy(OBJECT_SELF,"{}"); Gear("SHIELD","nw_ashlw001");'
        for donor in ('sr_cougar', 'sr_cl36_1'):
            self.assertEqual(retarget_heartbeat(line.format(donor), 'sr3ab64906_5'), line.format('sr3ab64906_5'))
        with self.assertRaises(ValueError): retarget_heartbeat('void main(){}', 'sr_cfs')
        with self.assertRaises(ValueError): retarget_heartbeat(line.format('a')+line.format('b'), 'sr_cfs')
        with self.assertRaises(ValueError): retarget_heartbeat(line.format('sr_cougar'), 'bad"resref')

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

    def test_placement_float_survives_the_native_float32_roundtrip(self):
        import struct
        value=gff_float(7.9+1.5)['value']
        self.assertEqual(struct.unpack('<f',struct.pack('<f',value))[0],value)

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

    def test_template_lineup_is_left_out_of_the_review_area(self):
        git = copy.deepcopy(self.git)
        git['Creature List']['value'] = [{'__struct_id': 4, 'Tag': field('cexostring', 'sw1_m%d' % i)} for i in range(30)]
        rows = place_review_actors(git, self.area, self.ifo, self.actors)['Creature List']['value']
        self.assertEqual([r['Tag']['value'] for r in rows], [a['Tag']['value'] for a in self.actors])
        self.assertEqual(len(git['Creature List']['value']), 30)                      # the caller's document is not changed

    def test_collision_and_outside_area_rejected(self):
        result = place_review_actors(self.git, self.area, self.ifo, self.actors)
        with self.assertRaisesRegex(ValueError, 'collision'):
            place_review_actors(result, self.area, self.ifo, self.actors)
        self.ifo['Mod_Entry_Y']['value'] = 39
        with self.assertRaisesRegex(ValueError, 'outside'):
            place_review_actors(self.git, self.area, self.ifo, self.actors)

    def test_dagger_and_legacy_entry_identity_are_isolated(self):
        knife = entry_script('sr_cfk', ('sr_cougar',))
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


class ScriptedShotTests(unittest.TestCase):
    def test_entry_script_carries_a_dormant_shot_sequence_for_every_check(self):
        from tools.itemkit.fixture import CHECKS, SHOTS, SHOT_TOGGLE, shot_script
        script = entry_script('sr_blade')
        self.assertIn('Get2DAString("' + SHOT_TOGGLE + '","On",0)!="1") return;', script)   # nothing changes without the toggle
        self.assertIn('ItkBegin(pc,male,female);', script); self.assertNotIn('@', script)
        self.assertIn('DURATION_TYPE_PERMANENT', script)                                    # placeholders touch nothing else
        self.assertEqual(script.count(',ItkTry(pc,t,base+'), len(SHOTS)); self.assertIn('<' + str(2 * len(SHOTS)) + ')', script)
        self.assertEqual({row[2] for row in SHOTS}, set(CHECKS))
        with self.assertRaisesRegex(ValueError, 'every melee client check'): shot_script(SHOTS[:-2])
        with self.assertRaisesRegex(ValueError, 'time to aim'): shot_script(SHOTS + ((26, 3.0, 'gloves-armor', 0, 3, 80, 1),))
        with self.assertRaisesRegex(ValueError, 'inside its own'): shot_script(SHOTS + ((30, 5.9, 'idle', 0, 3, 80, 1),))

    def test_capture_evidence_is_grouped_unreviewed_and_names_what_is_missing(self):
        from tools.itemkit.client_capture import evidence_draft, shot_rows
        rows = shot_rows(['ITEMKIT_READY area=a', 'ITEMKIT_SHOT shot=4 target=sr_it_male check=idle step=3 valid=1',
                          'ITEMKIT_SHOT shot=20 target=sr_it_female check=idle step=3 valid=0'])
        self.assertEqual([(r['shot'], r['step'], r['valid']) for r in rows], [(4, 3, True), (20, 3, False)])
        shots = [{**rows[0], 'captures': ['a.png', 'b.png']}, {**rows[1], 'captures': ['c.png'], 'rejected': 'next shot began'}]
        draft = evidence_draft(shots, 'log.txt', checks=('idle', 'walk'))
        self.assertEqual(draft['observations'], [{'body': 'human-male', 'check': 'idle', 'result': 'unreviewed', 'reviewedBy': '',
                                                  'notes': '', 'screenshots': ['a.png', 'b.png'], 'logs': ['log.txt']}])
        self.assertEqual(draft['missing'], [{'body': 'human-male', 'check': 'walk'}, {'body': 'human-female', 'check': 'idle'},
                                            {'body': 'human-female', 'check': 'walk'}])
        self.assertTrue(draft['reviewRequired'])

    def test_a_burst_that_overruns_the_shot_hold_is_never_filed(self):
        import json, time
        from tools.headkit.common import pin
        from tools.itemkit import client_capture
        from tools.itemkit.fixture import SHOT_HOLD
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); user = root/'user'; (user/'override').mkdir(parents=True)
            for name in ('m.mod', 'h.hak'): (root/name).write_bytes(b'x')
            (root/'fixture.json').write_text(json.dumps({'module': pin(root/'m.mod'), 'hak': pin(root/'h.hak'), 'fixtureHaks': [],
                                                         'userDirectory': str(user)}), encoding='utf-8')
            shot = ['ITEMKIT_SHOT shot=1 target=sr_it_male check=idle step=3 valid=1']; reads = []
            def log_lines(_, prefix):
                reads.append(1); return [] if len(reads) < 3 else shot if len(reads) < 6 else shot + [client_capture.DONE]
            slow = lambda pid, path: (time.sleep(SHOT_HOLD + .1), Path(path).write_bytes(b'png'))   # a stalled window capture
            process = type('P', (), {'pid': 1, 'poll': lambda self: None})()
            with patch('tools.armorkit.client.start', return_value=process), patch('tools.armorkit.client.stop'), \
                 patch('tools.armorkit.client.log_lines', side_effect=log_lines), patch('tools.armorkit.client.capture', side_effect=slow):
                result = client_capture.run(root, root, root/'captures', timeout=30, frames=1, gap=0, settle=0)
            self.assertEqual(result['shots'][0]['rejected'], 'burst overran the shot hold')
            draft = json.loads((root/'captures/evidence-draft.json').read_text(encoding='utf-8'))
            self.assertEqual(draft['observations'], [])                         # the stale frame is kept but never filed

    def test_shoulder_carry_frames_the_same_moments_higher_and_further(self):
        from tools.itemkit.fixture import SHOTS, SHOULDER_SHOTS, shot_script
        self.assertEqual([row[:3] for row in SHOULDER_SHOTS], [row[:3] for row in SHOTS])     # same steps, times and checks
        for hip, shoulder in zip(SHOTS, SHOULDER_SHOTS):
            if hip[4] < 2: self.assertEqual(shoulder[3:], (225, 1.5, hip[5], 1.35))            # close-ups aim at the chest
            else: self.assertEqual(shoulder[3:], (hip[3], round(hip[4] + 1.0, 1), hip[5], 1.3))
        shoulder = entry_script('sr_blade', carry='shoulder'); self.assertNotEqual(shoulder, entry_script('sr_blade'))
        self.assertIn(',225.0,1.5,85.0,1.35));', shoulder); self.assertNotIn(',1.4,85.0,0.95));', shoulder)
        self.assertIn(',1.4,85.0,0.95));', shot_script())
        with self.assertRaisesRegex(ValueError, 'Unknown carry'): entry_script('sr_blade', carry='back')

    def test_reviewed_item_is_rearmed_after_the_off_hand_steps_and_never_cleared(self):
        from tools.itemkit.fixture import shot_script
        script = entry_script('sr_blade')
        self.assertIn('if(n==22) DelayCommand(1.0,ItkRearm(t));', script)                 # well before the armour of step 23
        self.assertIn('INVENTORY_SLOT_RIGHTHAND!=INVENTORY_SLOT_LEFTHAND) DelayCommand(5.0,ItkClear(t,INVENTORY_SLOT_LEFTHAND));', script)
        self.assertIn('GetTag(o)!="sr_blade") DestroyObject(o);', script)                  # the reviewed item is never destroyed
        self.assertIn('ActionEquipItem(item,INVENTORY_SLOT_RIGHTHAND)', script); self.assertNotIn('ITEM_RESREF', script)
        shield = entry_script('sr_shield', equipment_slot='left')
        self.assertIn('ActionEquipItem(item,INVENTORY_SLOT_LEFTHAND));\n}', shield)
        self.assertIn('if(n==22 && INVENTORY_SLOT_LEFTHAND!=INVENTORY_SLOT_LEFTHAND)', shield)   # a shield keeps its own hand
        with self.assertRaisesRegex(ValueError, 'equipment slot'): shot_script(slot='both')
