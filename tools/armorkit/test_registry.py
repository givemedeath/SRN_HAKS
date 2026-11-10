"""The registry accepts only parts that follow the plan's part rules."""
import copy
import unittest
from pathlib import Path

from . import registry

EXAMPLE = Path(__file__).with_name('examples') / 'registry.json'


def part(**changes):
    base = {'slot': 'chest', 'number': 6000, 'set': 'corpsec-t1', 'group': 'corpsec', 'families': ['security'],
            'genderedCut': True,
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
        for number in (10000, registry.FIELD_LIMIT):
            self.rejected('kept for more runner and role sets', part(number=number, families=['runner']))
        registry.validate(document(part(number=9999, families=['runner'])))

    def test_block_decides_the_family(self):
        self.assertEqual([registry.block(n) for n in (300, 999, 1000, 2999, 3000, 4500, 5999, 6000, 7000, 8999, 9000, 9999)],
                         ['test', 'test', 'standalone', 'standalone', 'civilian', 'workwear', 'corporate', 'security',
                          'gang', 'heavy', 'runner', 'runner'])
        self.assertEqual(registry.LAST_NUMBER, 9999)  # runner sets are last so that they can grow past it
        with self.assertRaisesRegex(ValueError, 'outside every block'):
            registry.block(10000)
        self.rejected('belong to the security family', part(families=['civilian']))
        registry.validate(document(part(families=['security', 'corporate'])))

    def test_family_numbers_read_as_group_set_and_variant(self):
        for key in ('set', 'group'):
            self.rejected('names its set and its group', part(**{key: ...}))
            self.rejected(key + ' must be a lowercase tag', part(**{key: 'Corp Sec'}))
        variant = part(number=6001)
        registry.validate(document(part(), variant, part(number=6010, set='corpsec-t2')))
        self.rejected('6000-6009 are used by two sets', part(), part(number=6009, set='corpsec-t2'))
        self.rejected('6000-6099 are used by two groups', part(), part(number=6090, set='police-a', group='police'))
        registry.validate(document(part(), part(number=6100, set='police-a', group='police')))
        row = registry.handoff(registry.validate(document(part(number=6123))))['parts'][0]
        self.assertEqual((row['block'], row['group'], row['setNumber'], row['variant']), ('security', 'corpsec', 6120, 3))

    def test_standalone_pieces_belong_to_no_set_and_necks_follow_their_category(self):
        tee = part(number=1000, families=['civilian', 'workwear'], set=..., group=...)
        row = registry.handoff(registry.validate(document(tee), publish=True))['parts'][0]
        self.assertEqual(row['block'], 'standalone')
        self.assertFalse({'setNumber', 'variant'} & set(row))
        self.rejected('belong to no set or group', {**tee, 'set': 'tees'})
        self.rejected('belong to no set or group', {**tee, 'group': 'basics'})
        neck = part(slot='neck', families=['accessory'], set=..., group=..., genderedCut=False, tiers={}, neckCategory='back')
        for category, first, last in (('headgear', 1000, 1499), ('back', 1500, 1999), ('neckwear', 2000, 2499), ('torso', 2500, 2999)):
            for number in (first, last):
                registry.validate(document({**neck, 'neckCategory': category, 'number': number}))
            other = 2999 if first == 1000 else first - 1
            self.rejected(f'standalone {category} neck parts are numbered {first}-{last}', {**neck, 'neckCategory': category, 'number': other})
        registry.validate(document({**neck, 'number': 6000, 'set': 'corpsec-t1', 'group': 'corpsec', 'families': ['security']}))

    def test_test_numbers_are_free_but_never_published(self):
        scratch = part(number=300, families=['accessory'], set=..., group=...)
        registry.validate(document(scratch, {**scratch, 'number': 999, 'set': 'proof'}))
        self.rejected('test parts and are never published', scratch, publish=True)

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
        row = registry.handoff(registry.validate(document(shoulder)))['parts'][0]
        self.assertEqual(row['badge'], {'positions': ['left', 'right']})
        self.assertNotIn('logoTexture', row)  # the shared logo material joins the handoff in Phase 1
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
        for key, value, message in (('families', [['security']], 'families must be a list'), ('slot', ['chest'], 'Unknown slot'),
                                    ('mesh', {}, 'not allowed on this slot'), ('channels', [{'a': 1}], 'channels must be a list')):
            self.rejected(message, part(**{key: value}))
        with self.assertRaisesRegex(ValueError, 'Unsupported registry document'):
            registry.validate({**document(), 'schemaVersion': 2})
        original = part()
        snapshot = copy.deepcopy(original)
        registry.validate(document(original))
        self.assertEqual(original, snapshot)


if __name__ == '__main__':
    unittest.main()
