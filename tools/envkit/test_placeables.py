"""A model's row is appended to the placeables table in the table's own layout, and no row there moves."""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from . import additions, catalog, convert, placeables

HEAD = '2DA V2.0\n\n      Label                    StrRef ModelName     LightColor LightOffsetX LightOffsetY LightOffsetZ SoundAppType ShadowSize BodyBag LowGore Reflection  Static \n'
TABLE = (HEAD + '0     Armoire                  5645   PLC_A01       ****       ****         ****         ****         13           1          0       ****    ****        1      \n'
         + '7     "[mdrn]Old Thing, Small" ****   old_thing     ****       ****         ****         ****         27           1          0       ****    ****        1      \n')


class PlaceableTests(unittest.TestCase):
    def test_rows_follow_the_last_row_column_for_column(self):
        text, rows = placeables.register(TABLE, [{'model': 'ek_a', 'label': 'Shop, Bin', 'sound': 28}, {'model': 'ek_b', 'label': 'Shop, Sign', 'sound': 27}])
        self.assertEqual(rows, {'ek_a': 8, 'ek_b': 9}); self.assertTrue(text.startswith(TABLE))  # nothing there moved
        old, first, second = text.rstrip('\n').split('\n')[-3:]
        self.assertEqual(first.split()[0], '8'); self.assertIn('"[envkit]Shop, Bin"', first)
        for column, value in (('****   old_thing', '****   ek_a'), ('27 ', '28 ')):
            self.assertEqual(old.index(column), first.index(value))  # the same columns as the row above
        self.assertEqual(placeables.TOKEN.findall(second)[1:], ['"[envkit]Shop, Sign"', '****', 'ek_b', '****', '****', '****', '****', '27', '1', '0', '****', '****', '1'])
        self.assertEqual(len(first), len(old)); self.assertTrue(text.endswith('\n'))

    def test_a_label_too_long_for_its_column_pushes_the_row_on_instead_of_running_into_the_next_value(self):
        text, _ = placeables.register(TABLE, [{'model': 'ek_a', 'label': 'A Label Much Longer Than The Column It Sits In', 'sound': 28}])
        self.assertEqual(len(placeables.TOKEN.findall(text.rstrip('\n').split('\n')[-1])), len(placeables.COLUMNS) + 1)

    def test_a_model_already_in_the_table_or_a_bad_entry_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'already names old_thing'):
            placeables.register(TABLE, [{'model': 'old_thing', 'label': 'Again', 'sound': 28}])
        with self.assertRaisesRegex(ValueError, 'already names ek_a'):
            placeables.register(TABLE, [{'model': 'ek_a', 'label': 'One', 'sound': 28}, {'model': 'ek_a', 'label': 'Two', 'sound': 28}])
        with self.assertRaisesRegex(ValueError, 'lowercase resref'):
            placeables.register(TABLE, [{'model': 'EK_A', 'label': 'One', 'sound': 28}])
        with self.assertRaisesRegex(ValueError, 'label and a sound'):
            placeables.register(TABLE, [{'model': 'ek_a', 'label': 'Say "hi"', 'sound': 28}])
        with self.assertRaisesRegex(ValueError, 'Unexpected placeables table'):
            placeables.register('not a table\n\nx\n', [{'model': 'ek_a', 'label': 'One', 'sound': 28}])

    def test_the_rows_already_there_are_found_by_model_so_a_placed_model_can_be_converted_again(self):
        self.assertEqual(placeables.rows(TABLE), {'plc_a01': 0, 'old_thing': 7})
        text, made = placeables.register(TABLE, [{'model': 'old_thing', 'label': 'Under Test', 'sound': None}], again=True)  # a fixture's own row
        self.assertEqual(made, {'old_thing': 8}); self.assertEqual(placeables.TOKEN.findall(text.rstrip('\n').split('\n')[-1])[8], '****')
        self.assertEqual(placeables.rows(text)['old_thing'], 7)  # the first row is the model's own

    def test_the_tables_own_line_ends_are_kept(self):
        text, _ = placeables.register(TABLE.replace('\n', '\r\n'), [{'model': 'ek_a', 'label': 'Shop, Bin', 'sound': 28}])
        self.assertNotIn('\n', text.replace('\r\n', '')); self.assertTrue(text.endswith('\r\n'))


    def test_a_light_fills_the_rows_light_columns_and_a_row_already_there_takes_a_new_light(self):
        light = {'colour': 3, 'at': [0, 0.5, 4.2]}
        text, made = placeables.register(TABLE, [{'model': 'ek_a', 'label': 'Yard, Lamp', 'sound': 28, 'light': light}])
        self.assertEqual(placeables.TOKEN.findall(text.rstrip('\n').split('\n')[-1])[4:8], ['3', '0.0000', '0.5000', '4.2000'])
        again = placeables.lights(text, {'ek_a': None, 'old_thing': {'colour': 6, 'at': [1, 2, 3]}})
        before, last = again.rstrip('\n').split('\n')[-2:]
        self.assertEqual(placeables.TOKEN.findall(last)[4:8], ['****'] * 4)
        self.assertEqual(placeables.TOKEN.findall(before)[4:8], ['6', '1.0000', '2.0000', '3.0000'])
        self.assertEqual(again.split('\n')[:4], text.split('\n')[:4])  # rows not named are left as they were
        self.assertEqual(placeables.lights(text, {'ek_a': light}), text)
        self.assertTrue(placeables.lights(text.replace('\n', '\r\n'), {'ek_a': None}).endswith('\r\n'))
        with self.assertRaisesRegex(ValueError, 'no row to light: ek_z'):
            placeables.lights(text, {'ek_z': light})
        for bad in ({'colour': 3}, {'colour': '3', 'at': [0, 0, 1]}, {'colour': 300, 'at': [0, 0, 1]}, {'colour': 3, 'at': [0, 1]}):
            with self.assertRaisesRegex(ValueError, 'A light is'):
                placeables.light_values(bad)


class CommandTests(unittest.TestCase):
    def test_the_command_ships_a_models_files_and_enters_it_and_its_lights_in_the_catalog(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch); pack, dark, built = repo / 'props', repo / 'shared', repo / 'built' / 'ek_a'
            for folder in (pack, dark, built / 'compiled', built / 'source', repo / 'sets', repo / 'tables', repo / 'docs'):
                folder.mkdir(parents=True)
            given = lambda label: (repo / 'sets' / 'shop.json').write_text(json.dumps({'models': {'ek_a': {'source': 'models/a', 'height': 1.0, 'placeable': {'label': label, 'sound': 28}}}}),
                                                                           encoding='utf-8')
            given('Shop, Bin')
            (repo / 'tables' / 'placeables.2da').write_bytes(TABLE.encode('cp1252'))
            (built / 'compiled' / 'ek_a.mdl').write_bytes(b'compiled')
            files = {name: name.encode() for name in ('ek_a.mtr', 'ek_a.pwk', 'ek_a_i.dds', 'ek_a_o.mtr', 'ek_a_o.dds', 'ek_a_h.mtr', 'ek_a_s.dds', 'ek_a_w.dds', convert.HALO_OUT + '.mtr')}
            for name, content in files.items():
                (built / 'source' / name).write_bytes(content)
            listed = repo / 'docs' / 'catalog.json'
            catalog.save(listed, {'schemaVersion': 1, 'kind': catalog.KIND, 'placeables': [], 'tileGroups': [],
                                  'baseline': {'placeables': {'table': 'tables/placeables.2da', 'lastImportedRow': 7}, 'tilesets': {}}})

            def run(provenance=None):
                with contextlib.redirect_stdout(io.StringIO()) as said:
                    additions.command_placeables(argparse.Namespace(models=str(repo / 'sets' / 'shop.json'), built=str(repo / 'built'), repo=str(repo), pack='props', dark_pack='shared',
                                                                    table='tables/placeables.2da', catalog='docs/catalog.json', provenance=provenance, model=[]))
                return json.loads(said.getvalue())
            with self.assertRaisesRegex(ValueError, 'name its PROVENANCE.md section'):
                run()
            given('Shop \u2192 Bin')  # an arrow the game's code page lacks
            with self.assertRaisesRegex(ValueError, 'code page lacks'):
                run('Shop props')
            self.assertEqual(list(pack.iterdir()), [])  # each refused before anything was copied
            given('Shop, Bin'); self.assertEqual(run('Shop props')['rows'], {'ek_a': 8})
            self.assertEqual(run()['rows'], {'ek_a': 8})  # converted again: the row stands
            entry, = catalog.load(listed)['placeables']
            self.assertEqual((entry['row'], entry['model'], entry['label'], entry['provenance']), (8, 'ek_a', '[envkit]Shop, Bin', 'Shop props'))
            self.assertEqual(entry['lights'], {'lit': 'ek_a', 'out': 'ek_a_o', 'glow': 'ek_a_i', 'halo': 'ek_a_h', 'dark': convert.HALO_OUT})
            # What was built is only read: the catalog once went to the last file the copying had named.
            self.assertEqual({path.name: path.read_bytes() for path in (built / 'source').iterdir()}, files)
            self.assertTrue((dark / (convert.HALO_OUT + '.mtr')).is_file()); self.assertFalse((pack / (convert.HALO_OUT + '.mtr')).exists())  # the shared dark halo has one home
            self.assertEqual((repo / 'tables' / 'placeables.2da').read_bytes().count(b'ek_a'), 1)  # one row, however often it is converted
            self.assertEqual((pack / 'ek_a.mdl').read_bytes(), b'compiled'); self.assertTrue((pack / 'ek_a_o.mtr').is_file())
            self.assertTrue((pack / 'ek_a_w.dds').is_file())  # its fence's wire picture, shipped with it
            lit = ('ek_a_i.dds', 'ek_a_o.mtr', 'ek_a_o.dds', 'ek_a_h.mtr', 'ek_a_w.dds')
            for name in lit:  # built again with no lit parts and no fence
                (built / 'source' / name).unlink()
            self.assertEqual(run()['removed'], ['ek_a_i.dds', 'ek_a_o.dds', 'ek_a_o.mtr', 'ek_a_h.mtr', 'ek_a_w.dds'])
            self.assertNotIn('lights', catalog.load(listed)['placeables'][0])
            # Its light files leave the pack with its lights, and its wire picture with its fence: a glow map left behind would read as a lit model.
            self.assertFalse(any((pack / name).exists() for name in lit)); self.assertTrue((pack / 'ek_a_s.dds').is_file())


if __name__ == '__main__':
    unittest.main()
