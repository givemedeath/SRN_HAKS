"""Every door of the Toolset's appearance list shows its category and what it is (user, 2026-11-26)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from . import door_names

HEAD = '2DA V2.0\n\n   Label        StrRef ModelName  Name \n'


def repo(folder, rows, names):
    (folder / 'srn_2da').mkdir(); (folder / 'srn_tlk').mkdir(); (folder / 'docs/tilesets/doors').mkdir(parents=True)
    (folder / door_names.TABLE).write_text(HEAD + ''.join(f'{row}  {label}  ****  {model}  ****\n' for row, label, model in rows), encoding='cp1252', newline='')
    (folder / door_names.NAMES).write_text(json.dumps({'categories': ['Home', 'Shop'], 'rows': names}), encoding='utf-8')
    (folder / door_names.ALLOCATIONS).write_text(json.dumps({'nextId': 7, 'allocations': []}), encoding='utf-8')
    (folder / door_names.TLK).write_text(json.dumps({'entries': []}), encoding='utf-8')


class DoorNameTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.folder)

    def test_each_named_row_gets_a_string_once_and_shows_it(self):
        repo(self.folder, [(0, 'Wood', 'door_a'), (1, '****', '****'), (2, 'Glass', 'door_b')], {'0': 'Home: Door', '2': 'Shop: Glass Door'})
        self.assertEqual(door_names.check(self.folder)[:1], ['row 0 (Wood) does not show "Home: Door"'])
        self.assertEqual(door_names.apply(self.folder), 2); self.assertEqual(door_names.check(self.folder), [])
        self.assertEqual(door_names.apply(self.folder), 0)  # run again, nothing moves
        lines = (self.folder / door_names.TABLE).read_text(encoding='cp1252').splitlines()
        self.assertEqual(lines[3].split()[-1], str(door_names.CUSTOM + 7)); self.assertEqual(lines[5].split()[-1], str(door_names.CUSTOM + 8))
        self.assertEqual(json.loads((self.folder / door_names.ALLOCATIONS).read_text())['nextId'], 9)
        self.assertFalse((self.folder / door_names.LOCK).exists())

    def test_a_row_without_a_category_or_a_name_used_twice_is_found(self):
        repo(self.folder, [(0, 'Wood', 'door_a'), (2, 'Glass', 'door_b')], {'0': 'Door', '2': 'Shop: Door', '3': 'Shop: Door'})
        wrong = door_names.check(self.folder)
        self.assertTrue(any('row 0' in one and 'no name' in one for one in wrong)); self.assertTrue(any('names row 3, which names no model' in one for one in wrong))
        self.assertTrue(any('"Shop: Door" names rows 2, 3' in one for one in wrong))

    def test_the_repository_s_doors_are_all_named(self):
        self.assertEqual(door_names.check(), [])


if __name__ == '__main__':
    unittest.main()
