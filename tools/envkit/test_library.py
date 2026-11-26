"""The imported placeables' names and blueprints."""
import json
import tempfile
import unittest
from pathlib import Path

from . import library, placeables

REPO = Path(__file__).resolve().parents[2]
TABLE = '2DA V2.0\r\n\r\n      ' + ' '.join(placeables.COLUMNS) + '\r\n' + '7      [mdrn]Chair_desk   ****  chair  **** **** **** **** 28 1 0 **** **** 1\r\n8      "[mdrn]A desk"   ****  desk   **** **** **** **** 28 1 0 **** **** 1\r\n'
CHAIR = {'row': 7, 'model': 'chair', 'name': 'Chair, Desk (Grey)', 'category': 174, 'blueprint': 'chair'}


class Library(unittest.TestCase):
    def test_a_row_takes_its_name_and_keeps_everything_else(self):
        made = library.relabelled(TABLE, [CHAIR]).split('\r\n'); self.assertEqual(made[4], TABLE.split('\r\n')[4])
        before, after = (placeables.TOKEN.findall(line) for line in (TABLE.split('\r\n')[3], made[3]))
        self.assertEqual(after, [before[0], '"[mdrn]Chair, Desk (Grey)"', *before[2:]]); self.assertEqual(library.relabelled('\r\n'.join(made), [CHAIR]), '\r\n'.join(made))

    def test_a_row_of_another_model_or_none(self):
        for entry, wanted in (({**CHAIR, 'model': 'desk'}, 'is chair, not desk'), ({**CHAIR, 'row': 9}, 'lacks rows 9')):
            with self.assertRaisesRegex(ValueError, wanted):
                library.relabelled(TABLE, [entry])

    def test_two_entries_of_one_name_or_blueprint_and_names_a_table_cannot_hold(self):
        other = {'row': 8, 'model': 'desk', 'name': 'Desk', 'category': 174, 'blueprint': 'desk'}; self.assertEqual(library.checked([CHAIR, other]), [CHAIR, other])
        for change, wanted in (({'name': 'chair, desk (grey)'}, 'the name'), ({'blueprint': 'chair'}, 'the blueprint'), ({'row': 7}, 'the row'), ({'name': 'A "desk"'}, 'no plain name'), ({'name': 'Desk '}, 'no plain name'), ({'blueprint': 'udp2-p-06'}, 'resref'), ({'row': 6}, 'order')):
            with self.assertRaisesRegex(ValueError, wanted):
                library.checked([CHAIR, {**other, **change}])

    def test_the_library_is_read_whole_or_not_at_all(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'library.json'; path.write_text(json.dumps({'schemaVersion': 1, 'kind': library.KIND, 'placeables': [CHAIR]}), encoding='utf-8')
            self.assertEqual(library.load(path), [CHAIR]); path.write_text('{"kind": "other"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'library required'):
                library.load(path)


class Pack(unittest.TestCase):
    def test_the_table_and_the_pack_are_as_the_library_says(self):
        self.assertEqual(library.wrong(REPO, library.load(REPO / library.PATH))[:5], [])


if __name__ == '__main__':
    unittest.main()
