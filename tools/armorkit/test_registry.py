"""The registry accepts only parts that follow the plan's part rules."""
import copy
import json
import unittest
from pathlib import Path

from . import registry

EXAMPLE = Path(__file__).with_name('examples') / 'registry.json'


def part(**changes):
    base = {'slot': 'chest', 'number': 6000, 'set': 'corpsec-t1', 'families': ['security'], 'genderedCut': True,
            'tiers': {'neck': 1, 'shoulder': 1, 'waist': 1}, 'coverage': {'skin': False, 'headgear': False},
            'channels': ['cloth1', 'metal1'], 'badge': None, 'bodies': list(registry.BODIES), 'mesh': 'rigid'}
    base.update(changes)
    return {key: value for key, value in base.items() if value is not ...}


def document(*parts):
    return {'schemaVersion': 1, 'kind': registry.KIND, 'parts': list(parts)}


class RegistryTests(unittest.TestCase):
    def rejected(self, message, *parts, publish=False):
        with self.assertRaisesRegex(ValueError, message):
            registry.validate(document(*parts), publish=publish)

    def test_example_registry_is_valid_and_publishable(self):
        parts = registry.load(EXAMPLE, publish=True)
        self.assertEqual([(p['slot'], p['number']) for p in parts], sorted((p['slot'], p['number']) for p in parts))
        self.assertEqual({p['slot'] for p in parts}, {'chest', 'belt', 'shoulder', 'neck', 'bicep'})

    def test_twenty_bodies_and_nineteen_item_parts(self):
        self.assertEqual(len(registry.BODIES), 20)
        self.assertEqual(len(set(registry.BODIES)), 20)
        self.assertEqual(sorted(i for row in registry.SLOTS.values() for i in row['models']), list(range(19)))
        self.assertEqual(len(registry.TABLES), 12)
        self.assertTrue(all(len(field) <= 16 for row in registry.SLOTS.values() for field in row['fields']))

    def test_model_names_use_three_digits_then_the_plain_number(self):
        self.assertEqual(registry.model_name('pmh0', 'chest', 300), 'pmh0_chest300')
        self.assertEqual(registry.model_name('pmh0', 'bicepl', 1000), 'pmh0_bicepl1000')
        self.assertEqual(len(registry.model_name('pfg2', 'bicepr', 65535)), 16)
        names = registry.model_names(part(slot='bicep', tiers={'shoulder': 1, 'elbow': 1}, genderedCut=False))
        self.assertEqual(names['pfo2'], ['pfo2_bicepl6000', 'pfo2_bicepr6000'])
        self.assertEqual(registry.texture_names(part()), ['pfh0_chest6000', 'pmh0_chest6000'])

    def test_numbers_stay_out_of_stock_rows_and_the_buffer(self):
        for number in (0, 200, 255, 299):
            self.rejected('numbers start at 300', part(number=number))
        self.rejected('numbers start at 300', part(number=65536))
        registry.validate(document(part(number=9000, families=['heavy'])))

    def test_block_decides_the_family(self):
        self.assertEqual([registry.block(n) for n in (300, 2999, 3000, 4500, 5999, 6000, 7000, 8999, 9000, 65535)],
                         ['accessory', 'accessory', 'civilian', 'workwear', 'corporate', 'security', 'runner', 'gang', None, None])
        self.rejected('belong to the security family', part(families=['civilian']))
        registry.validate(document(part(families=['security', 'corporate'])))

    def test_chest_is_always_a_gendered_cut(self):
        self.rejected('separate male and female cut', part(genderedCut=False))

    def test_fitted_parts_declare_every_joint_tier(self):
        self.rejected('declares a tier at each', part(tiers={'neck': 1, 'waist': 1}))
        self.rejected('tiers map', part(tiers={'neck': 1, 'shoulder': 4, 'waist': 1}))
        self.rejected('tiers map', part(tiers={'neck': 1, 'shoulder': 1, 'waist': 1, 'knee': 1}))
        registry.validate(document(part(slot='belt', number=300, families=['accessory'], set=..., genderedCut=False, tiers={})))

    def test_neck_category_belongs_to_neck_parts(self):
        neck = part(slot='neck', number=300, families=['accessory'], set=..., genderedCut=False, tiers={'neck': 0},
                    mesh='skinned', neckCategory='headgear', coverage={'skin': False, 'headgear': True})
        registry.validate(document(neck))
        self.rejected('every neck part has one', {k: v for k, v in neck.items() if k != 'neckCategory'})
        self.rejected('every neck part has one', part(neckCategory='back'))
        self.rejected('neckCategory must be one of', {**neck, 'neckCategory': 'hat'})
        self.rejected('headgear is a neck part of category headgear', {**neck, 'neckCategory': 'back'})

    def test_mesh_kind_is_limited_by_slot(self):
        self.rejected('not allowed on this slot', part(mesh='skinned'))
        self.rejected('not allowed on this slot', part(slot='shoulder', tiers={}, genderedCut=False, mesh='dangly'))

    def test_logos_only_on_shoulders_and_lanyards(self):
        self.rejected('logos live only on shoulder parts', part(badge={'positions': ['left']}))
        shoulder = part(slot='shoulder', tiers={'shoulder': 2}, genderedCut=False, badge={'positions': ['left', 'right']})
        self.assertEqual(registry.handoff(registry.validate(document(shoulder)))['parts'][0]['logoTexture'], 'srn_logo_0')
        self.rejected('badge positions', {**shoulder, 'badge': {'positions': ['chest']}})
        self.rejected('a badge needs its side', {**shoulder, 'sides': ['r'], 'badge': {'positions': ['left']}})

    def test_skin_channel_matches_exposed_skin(self):
        self.rejected('exposed skin uses the skin channel', part(coverage={'skin': True, 'headgear': False}))
        self.rejected('exposed skin uses the skin channel', part(channels=['cloth1', 'skin']))
        self.rejected('channels must be a list', part(channels=['tattoo1']))

    def test_duplicates_and_shared_numbers(self):
        self.rejected('Duplicate part chest 6000', part(), part())
        other = part(slot='pelvis', tiers={'waist': 1, 'hip': 1}, genderedCut=False)
        registry.validate(document(part(), other))
        self.rejected('used by two sets', part(), {**other, 'set': 'corpsec-t2'})

    def test_publication_needs_all_twenty_bodies(self):
        partial = part(bodies=['pmh0', 'pfh0'])
        registry.validate(document(partial))
        self.rejected('exists on all 20 bodies', partial, publish=True)
        self.rejected('bodies must be a list', part(bodies=['pmh1']))

    def test_one_sided_parts_and_handoff_fields(self):
        left = part(slot='shoulder', tiers={}, genderedCut=False, sides=['l'])
        row = registry.handoff(registry.validate(document(left)))['parts'][0]
        self.assertEqual((row['table'], row['itemFields'], row['itemModelIndices'], row['block']),
                         ('parts_shoulder', ['xArmorPart_LShou'], [15], 'security'))
        self.assertEqual(row['models']['pmd2'], ['pmd2_shol6000'])
        self.rejected('sides belongs to paired slots', part(sides=['l']))

    def test_unknown_keys_and_documents_are_rejected(self):
        self.rejected('Part keys must be', {**part(), 'acBonus': 4})
        with self.assertRaisesRegex(ValueError, 'Unsupported registry document'):
            registry.validate({**document(), 'schemaVersion': 2})
        original = part()
        snapshot = copy.deepcopy(original)
        registry.validate(document(original))
        self.assertEqual(original, snapshot)
        self.assertEqual(json.loads(EXAMPLE.read_text(encoding='utf-8'))['kind'], registry.KIND)


if __name__ == '__main__':
    unittest.main()
