"""A model's row is appended to the placeables table in the table's own layout, and no row there moves."""
import unittest

from . import placeables

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

    def test_the_tables_own_line_ends_are_kept(self):
        text, _ = placeables.register(TABLE.replace('\n', '\r\n'), [{'model': 'ek_a', 'label': 'Shop, Bin', 'sound': 28}])
        self.assertNotIn('\n', text.replace('\r\n', '')); self.assertTrue(text.endswith('\r\n'))


if __name__ == '__main__':
    unittest.main()
