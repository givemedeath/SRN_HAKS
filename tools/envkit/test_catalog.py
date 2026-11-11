"""The additions catalog keeps one entry per row and per group, and a blueprint and its palette entry are what the
Toolset reads."""
import json
import tempfile
import unittest
from pathlib import Path

from . import blueprints, catalog

PLACED = {'row': 22740, 'model': 'ek_a', 'label': '[envkit]Shop, Bin', 'pack': 'props', 'madeBy': 'envkit', 'source': 'tools/envkit/sets/shop.json',
          'provenance': 'Shop props', 'added': '2026-11-11'}
GROUP = {'tileset': 'dgt04', 'group': 57, 'name': 'Shop', 'rows': 1, 'columns': 2, 'tiles': [434, 435], 'models': ['ek_shop_t00', 'ek_shop_t01'], 'pack': 'tiles',
         'madeBy': 'envkit', 'source': 'tools/envkit/sets/shop.json', 'provenance': 'Shop tile group', 'added': '2026-11-11'}


def empty():
    return {'schemaVersion': 1, 'kind': catalog.KIND, 'placeables': [], 'tileGroups': [],
            'baseline': {'placeables': {'table': 'tables/placeables.2da', 'lastImportedRow': 22739},
                         'tilesets': {'dgt04': {'set': 'sets/dgt04.set', 'importedTiles': 429, 'importedGroups': 52}}}}


class CatalogTests(unittest.TestCase):
    def test_an_entry_is_added_once_and_a_row_or_group_keeps_what_it_was_given(self):
        data = empty(); catalog.put_placeable(data, PLACED); catalog.put_group(data, GROUP)
        catalog.put_placeable(data, {'row': 22740, 'model': 'ek_a', 'label': '[envkit]Shop, Bin', 'pack': 'props', 'blueprint': 'ek_a', 'category': 158})  # converted again
        self.assertEqual(len(data['placeables']), 1)
        self.assertEqual((data['placeables'][0]['blueprint'], data['placeables'][0]['provenance']), ('ek_a', 'Shop props'))  # what it said of its origin stands
        with self.assertRaisesRegex(ValueError, 'Row 22740 belongs to ek_a'):
            catalog.put_placeable(data, {**PLACED, 'model': 'ek_b'})
        catalog.put_group(data, {**GROUP, 'label': 'Shop 1x2'}); self.assertEqual(len(data['tileGroups']), 1)
        with self.assertRaisesRegex(ValueError, 'Group 57 of dgt04 is Shop'):
            catalog.put_group(data, {**GROUP, 'tiles': [436, 437]})
        catalog.put_group(data, {**GROUP, 'tileset': 'udp1', 'group': 106, 'tiles': [676, 677]})  # the same group in another tileset is its own entry
        self.assertEqual(len(data['tileGroups']), 2)

    def test_the_file_is_written_in_a_fixed_order_and_read_back_whole(self):
        data = empty(); catalog.put_group(data, {**GROUP, 'tileset': 'udp1', 'group': 106}); catalog.put_group(data, GROUP)
        catalog.put_placeable(data, {**PLACED, 'row': 22741, 'model': 'ek_b'}); catalog.put_placeable(data, PLACED)
        data['baseline']['tilesets']['udp1'] = {'set': 'sets/udp1.set', 'importedTiles': 676, 'importedGroups': 106}
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / 'catalog.json'; catalog.save(path, data); again = catalog.load(path)
            self.assertEqual([entry['row'] for entry in again['placeables']], [22740, 22741])
            self.assertEqual([(entry['tileset'], entry['group']) for entry in again['tileGroups']], [('dgt04', 57), ('udp1', 106)])
            self.assertTrue(path.read_bytes().endswith(b'}\n')); self.assertNotIn(b'\r', path.read_bytes())
            path.write_text(json.dumps({**again, 'placeables': [{'row': 22740}]}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'placeable entry is incomplete'):
                catalog.load(path)
            path.write_text(json.dumps({**again, 'tileGroups': [{**GROUP, 'models': ['ek_shop_t00']}]}), encoding='utf-8')  # two tiles, one model
            with self.assertRaisesRegex(ValueError, 'tile group entry is incomplete'):
                catalog.load(path)
            path.write_text('{"kind": "something else"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Additions catalog required'):
                catalog.load(path)


class BlueprintTests(unittest.TestCase):
    def test_a_blueprint_is_scenery_of_its_row_that_a_script_can_reach_only_if_asked(self):
        made = blueprints.blueprint('ek_a', 22740, 'Shop, Bin', 158, comment='envkit: sets/shop.json')
        value = lambda key: made[key]['value']
        self.assertEqual((made['__data_type'], value('Appearance'), value('TemplateResRef'), value('Tag'), value('PaletteID')), ('UTP ', 22740, 'ek_a', 'ek_a', 158))
        self.assertEqual((value('LocName'), value('Static'), value('Plot'), value('Useable')), ({'0': 'Shop, Bin'}, 1, 1, 0))
        self.assertEqual(blueprints.blueprint('ek_a', 22740, 'Shop, Bin', 158, static=False)['Static']['value'], 0)  # its lights can be put out by script
        self.assertTrue(all(made[event] == {'type': 'resref', 'value': ''} for event in blueprints.EVENTS))
        for resref, category in (('EK_A', 158), ('ek_a_name_much_too_long', 158), ('ek_a', 300)):
            with self.assertRaisesRegex(ValueError, 'blueprint'):
                blueprints.blueprint(resref, 22740, 'Shop, Bin', category)

    def test_the_palette_is_the_games_own_with_ours_added_on_the_packs_tree(self):
        node = lambda **fields: {'__struct_id': 0, **{key: blueprints.field('list' if key == 'LIST' else 'dword' if key == 'STRREF' else 'byte', value) for key, value in fields.items()}}
        listed = lambda resref: {'__struct_id': 0, 'RESREF': blueprints.field('resref', resref), 'STRREF': blueprints.field('dword', 1)}
        skeleton = {'MAIN': blueprints.field('list', [node(ID=9, STRREF=1592), node(STRREF=7000, LIST=[node(ID=158, STRREF=7001), node(ID=156, STRREF=7002)]),
                                                      node(ID=16, STRREF=6000, LIST=[node(ID=17, STRREF=6001)]), node(STRREF=8000, LIST=[node(ID=200, STRREF=8001)])])}
        stock = {'MAIN': blueprints.field('list', [node(ID=9, STRREF=1592, LIST=[listed('plc_barrel')]), node(ID=16, STRREF=6000, LIST=[node(ID=17, STRREF=6001, LIST=[listed('plc_chest')])])])}
        ours = [{'resref': 'ek_trash', 'name': 'Shop, Trash Can', 'category': 158}, {'resref': 'ek_bin', 'name': 'Shop, Bin', 'category': 158}]
        made = blueprints.palette(skeleton, stock, ours)
        self.assertEqual(blueprints.listing(made), {'plc_barrel': 9, 'plc_chest': 17, 'ek_bin': 158, 'ek_trash': 158})
        top = made['MAIN']['value']; self.assertEqual(len(top), 3)  # the branch with nothing under it is left out
        streets = top[1]['LIST']['value']; self.assertEqual(len(streets), 1)  # and so is the empty category beside ours
        self.assertEqual([one['NAME']['value'] for one in streets[0]['LIST']['value']], ['Shop, Bin', 'Shop, Trash Can'])
        self.assertEqual(top[1]['STRREF']['value'], 7000); self.assertNotIn('ID', top[1])
        self.assertEqual(blueprints.listing(blueprints.palette(skeleton, stock, [])), {'plc_barrel': 9, 'plc_chest': 17})
        with self.assertRaisesRegex(ValueError, 'category 77'):
            blueprints.palette(skeleton, stock, [{'resref': 'ek_x', 'name': 'X', 'category': 77}])
        with self.assertRaisesRegex(ValueError, 'already lists plc_barrel'):
            blueprints.palette(skeleton, stock, [{'resref': 'plc_barrel', 'name': 'Again', 'category': 9}])
        with self.assertRaisesRegex(ValueError, 'the pack\'s tree lacks: 9'):
            blueprints.palette({'MAIN': blueprints.field('list', [node(ID=158, STRREF=7001)])}, stock, [])


if __name__ == '__main__':
    unittest.main()
