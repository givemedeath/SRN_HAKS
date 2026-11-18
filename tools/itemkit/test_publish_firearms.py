"""Firearm publication: the package survey, the carrier's ammunition and firing-effect models, on synthetic archives."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.itemkit import publish as P
from tools.itemkit.test_publish import erf, gff, make_repo, tga

SLING = (b'2DA V2.0\n\n     label        MaxRange   ItemClass   RangedWeapon\n'
         b'22   dagger       100        WSwDg       ****\n61   sling        65         WBwSl       27\n')
EFFECT = b'\0\0\0\0' + b'model wbwsl_b_076 srn_flash01 srn_casing'


def package(root, blueprint='srgun_6', base=61, parts=(76, 16, 16), table=True, tamper=False):
    folder = root/'firearm-package-fit-v1'; (folder/'native').mkdir(parents=True)
    models = [f'wbwsl_{slot}_{number:03}' for slot, number in zip('bmt', parts)]
    uti = gff(b'UTI ', [('BaseItem', 4, base), *[(f'ModelPart{i}', 0, v) for i, v in zip((1, 2, 3), parts)]])
    entries = {**{(m, 2002): f'model {m}'.encode() for m in models}, (f'i{models[0]}', 3): tga(32, 64), ('srgun_076', 3): b'diffuse',
               (blueprint, 2025): uti, **({('baseitems', 2017): b'private table'} if table else {})}
    hak = erf(b'HAK ', entries); (folder/'native/srgunh.hak').write_bytes(hak + (b'x' if tamper else b''))
    record = {'hak': {'path': 'X:/elsewhere/srgunh.hak', 'sha256': hashlib.sha256(hak).hexdigest()}, 'baseItem': base,
              'identity': {'blueprint': blueprint, 'displayName': 'Test Pistol'}, 'allocation': {'itemClass': 'wbwsl'}}
    (folder/'native/native.json').write_text(json.dumps(record), encoding='utf-8')
    modules = folder/'fixture/userdir/modules'; modules.mkdir(parents=True); (modules/'srgunm.mod').write_bytes(erf(b'MOD ', {('x', 2025): b'x'}))
    return folder


class FirearmSurveyTests(unittest.TestCase):
    def test_a_firearm_package_is_surveyed_without_its_private_table(self):
        with tempfile.TemporaryDirectory() as folder:
            found = P.survey('pistol', package(Path(folder)))
            self.assertTrue(found.firearm); self.assertEqual((found.blueprint, found.base_item, found.appearance), ('srgun_6', 61, 76))
            self.assertEqual(sorted(found.files), ['iwbwsl_b_076.tga', 'srgun_076.tga', 'srgun_6.uti', 'wbwsl_b_076.mdl', 'wbwsl_m_016.mdl', 'wbwsl_t_016.mdl'])

    def test_a_changed_package_an_unknown_carrier_or_a_missing_model_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(P.PublishError, 'missing or changed'): P.survey('pistol', package(Path(folder)/'a', tamper=True))
            with self.assertRaisesRegex(P.PublishError, 'no ammunition'): P.survey('pistol', package(Path(folder)/'b', base=22))
            run = package(Path(folder)/'c'); native = json.loads((run/'native/native.json').read_text())
            hak = erf(b'HAK ', {('srgun_6', 2025): gff(b'UTI ', [('BaseItem', 4, 61), ('ModelPart1', 0, 76), ('ModelPart2', 0, 16), ('ModelPart3', 0, 16)])})
            (run/'native/srgunh.hak').write_bytes(hak); native['hak']['sha256'] = hashlib.sha256(hak).hexdigest()
            (run/'native/native.json').write_text(json.dumps(native))
            with self.assertRaisesRegex(P.PublishError, 'does not carry'): P.survey('pistol', run)
            hak = erf(b'HAK ', {('srgun_6', 2025): gff(b'UTI ', [('BaseItem', 4, 61), ('ModelPart1', 0, 76)])})
            (run/'native/srgunh.hak').write_bytes(hak); native['hak']['sha256'] = hashlib.sha256(hak).hexdigest()
            (run/'native/native.json').write_text(json.dumps(native))
            with self.assertRaisesRegex(P.PublishError, 'lacks a ModelPart'): P.survey('pistol', run)

    def test_a_firearm_is_planned_and_its_carrier_row_reaches_the_shown_part(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'r').mkdir(); repo = make_repo(root/'r'); (repo/P.BASEITEMS).write_bytes(SLING)
            packages, needs, _ = P.plan(repo, [('pistol', package(root))])
            self.assertEqual(needs, {61: (65, 76)}); self.assertTrue(packages[0].firearm)


class FirearmEffectTests(unittest.TestCase):
    def test_an_effect_build_ships_in_place_of_the_package_model_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'r').mkdir(); repo = make_repo(root/'r'); found = P.survey('pistol', package(root))
            effects = root/'effects'; effects.mkdir(); (effects/'wbwsl_b_076.mdl').write_bytes(EFFECT); (effects/'other.mdl').write_bytes(EFFECT)
            P.with_effects(found, effects); self.assertEqual(list(found.effects), ['wbwsl_b_076.mdl'])
            pub, _ = P.load_exact(repo/P.PUBLICATION); pub['groupingPlan']['families'].append({'id': 'F7', 'baseItemId': 61})
            pub.update(sources={}, approvalEvidence={'userStatements': []}, clientReview='', blueprintPublicationPolicy='')
            P.dump(repo/P.PUBLICATION, pub, False)
            record = P.update_publication(repo, [found], {}, ['ok'], 'reviewed', 'policy')
            rows = {r['sourceResource']: r for r in record['resources']}; shown = rows['wbwsl_b_076.mdl']
            self.assertEqual((shown['sha256'], shown['bytes']), (hashlib.sha256(EFFECT).hexdigest(), len(EFFECT)))
            self.assertEqual(shown['preEffectsSha256'], shown['approvedSourceSha256']); self.assertNotEqual(shown['sha256'], shown['preEffectsSha256'])
            self.assertNotIn('preEffectsSha256', rows['wbwsl_m_016.mdl']); self.assertEqual(record['items'][0]['family'], 'F7')

    def test_an_effect_must_be_a_compiled_effect_model_of_a_firearm(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); found = P.survey('pistol', package(root)); effects = root/'effects'; effects.mkdir()
            with self.assertRaisesRegex(P.PublishError, 'a model of its own'): P.with_effects(found, effects)
            for body in (b'newmodel srn_flash', b'\0\0\0\0plain', b'\0\0\0\0srn_flash srp_test'):
                (effects/'wbwsl_b_076.mdl').write_bytes(body)
                with self.assertRaisesRegex(P.PublishError, 'not a compiled firing-effect model'): P.with_effects(found, effects)


class FirearmReviewerTests(unittest.TestCase):
    TEXT = ('void Equip(string name){\n if(name=="sr_cl36_1"||name=="sr3ab64906_5") {object bullets=CreateItemOnObject("nw_wambu001",actor,99);}\n'
            ' if(name=="sra84e4660_5"||name=="sr6abe18c_6") {object bolts=CreateItemOnObject("nw_wambo001",actor,99);}\n}\n'
            'void main(){\nCreateItemOnObject("sr_cl36_1",pc);SetLocalInt(pc,"SW2_ITEMS",1);}\n'
            'Equip("sw1_m0","old",INVENTORY_SLOT_RIGHTHAND,0);\nSendMessageToPC(pc,"Seventeen weapon/finish NPC pairs and more");\n}')

    def pair(self, blueprint, base, firearm=True):
        return {'package': P.Package('i', Path('.'), 'Item', blueprint, base, 76, Path('h'), Path('m'), firearm=firearm), 'prefix': 'sw9_', 'index': 0, 'x': 1.0}

    def test_each_firearm_reviewer_is_handed_its_carriers_ammunition(self):
        out = P.enter_script(self.TEXT, [self.pair('srpistol_6', 61), self.pair('srrifle_7', 6), self.pair('srknife', 22, False)], 20)
        self.assertIn('name=="sr3ab64906_5"||name=="srpistol_6") {object bullets=', out)
        self.assertIn('name=="sr6abe18c_6"||name=="srrifle_7") {object bolts=', out)
        self.assertNotIn('name=="srknife"', out); self.assertIn('Equip("sw9_m0","srrifle_7",INVENTORY_SLOT_RIGHTHAND,0);', out)

    def test_a_script_without_the_ammunition_line_is_refused(self):
        with self.assertRaisesRegex(P.PublishError, 'hands out bullets'):
            P.enter_script(self.TEXT.replace('object bullets', 'object rounds'), [self.pair('srpistol_6', 61)], 18)


if __name__ == '__main__':
    unittest.main()
