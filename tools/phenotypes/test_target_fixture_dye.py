"""Dye fixture actors: dressed actors carry stock body fields; validation rejects invisible dressed actors."""
import copy
import unittest

from target_fixture_dye import ARMOR_PARTS, BODY_FIELDS, DYES, dress_actors, validate_dressed_actors


def git_fixture():
    actors = [{'__struct_id': 4, 'Tag': {'type': 'cexostring', 'value': 'tm_%d' % index},
               'Equip_ItemList': {'type': 'list', 'value': []}} for index in range(8)]
    return {'Creature List': {'type': 'list', 'value': actors}}


TEMPLATE = {'__data_type': 'UTI ', 'BaseItem': {'type': 'int', 'value': 16}, 'Tag': {'type': 'cexostring', 'value': 'NW_CLOTH001'}}


class TargetFixtureDyeTests(unittest.TestCase):
    def test_dressed_actors_get_item_and_stock_body_fields(self):
        git, dressed = dress_actors(git_fixture(), TEMPLATE)
        self.assertEqual(dressed, DYES)
        actors = {row['Tag']['value']: row for row in git['Creature List']['value']}
        for tag in DYES:
            row = actors[tag]
            self.assertEqual(row['Appearance_Head']['value'], 1)
            self.assertTrue(all(row[key]['value'] == value for key, value in BODY_FIELDS.items()))
            item = row['Equip_ItemList']['value'][0]
            self.assertEqual(item['__struct_id'], 2); self.assertNotIn('__data_type', item)
            self.assertEqual(item['Cloth1Color']['value'], DYES[tag]['Cloth1Color'])
            self.assertTrue(all(item[key]['value'] == value for key, value in ARMOR_PARTS.items()))
        self.assertEqual(actors['tm_2']['Equip_ItemList']['value'], [])
        self.assertEqual(validate_dressed_actors(git['Creature List']['value'])['tm_0']['Cloth1Color'], 88)
        self.assertNotIn('Appearance_Head', git_fixture()['Creature List']['value'][0])

    def test_dressed_actor_without_head_or_body_parts_is_rejected(self):
        git, _ = dress_actors(git_fixture(), TEMPLATE)
        for field in ('Appearance_Head', 'BodyPart_Torso'):
            broken = copy.deepcopy(git['Creature List']['value'])
            broken[0].pop(field)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'lacks'):
                validate_dressed_actors(broken)
        robed = copy.deepcopy(git['Creature List']['value']); robed[1]['Equip_ItemList']['value'][0]['ArmorPart_Robe']['value'] = 3
        with self.assertRaisesRegex(ValueError, 'naked 001'):
            validate_dressed_actors(robed)

    def test_naked_fixtures_pass_unchanged(self):
        self.assertEqual(validate_dressed_actors(git_fixture()['Creature List']['value']), {})
        with self.assertRaisesRegex(ValueError, 'missing'):
            dress_actors(git_fixture(), TEMPLATE, {'tm_9': DYES['tm_0']})


if __name__ == '__main__':
    unittest.main()
