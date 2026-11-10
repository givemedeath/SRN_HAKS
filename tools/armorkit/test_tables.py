"""Generated parts tables keep stock rows, pad every gap and null the mechanics of new rows."""
import unittest

from . import registry, tables
from .test_registry import part


def stock(table):
    """Synthetic stock text in the game's layout: rows 0-200, or 0-38 with hide columns for the robe table."""
    if table == 'parts_robe':
        columns = ['COSTMODIFIER', 'ACBONUS'] + ['HIDE' + name for name in registry.ROBE_HIDES]
        rows = [f'{i:<4}0             {"1.00" if i % 2 else "****"}     ' + '  '.join('0' for _ in registry.ROBE_HIDES) for i in range(39)]
    else:
        columns = ['COSTMODIFIER', 'ACBONUS']
        rows = [f'{i:<5}0             {"0.00" if i in (1, 5) else "****"}     ' for i in range(201)]
    return '\r\n'.join(['2DA V2.0', '', '     ' + '  '.join(columns) + '  ', *rows]) + '\r\n'


PARTS = [part(), part(number=9002, families=['heavy'], set='heavy-a'),
         part(slot='belt', number=300, families=['accessory'], set=..., genderedCut=False, tiers={})]
STOCK = {table: stock(table) for table in registry.TABLES}


class TableTests(unittest.TestCase):
    def test_stock_rows_are_kept_byte_for_byte_and_gaps_are_padded(self):
        text = tables.generate('parts_chest', STOCK['parts_chest'], PARTS)
        self.assertTrue(text.startswith(STOCK['parts_chest']))
        columns, rows = tables.parse(text)
        self.assertEqual((columns, len(rows)), (['COSTMODIFIER', 'ACBONUS'], 9003))
        self.assertEqual(rows[6000], ['0', '0.00'])
        self.assertEqual(rows[9002], ['0', '0.00'])
        self.assertTrue(all(rows[i] == ['****', '****'] for i in range(201, 9002) if i != 6000))
        self.assertTrue(text.endswith('\r\n') and '\n\n' not in text.replace('\r\n', '\n')[10:])
        self.assertEqual(tables.check('parts_chest', text, PARTS, STOCK['parts_chest']),
                         {'table': 'parts_chest', 'rows': 9003, 'live': [6000, 9002]})

    def test_all_twelve_tables_and_untouched_tables_equal_stock(self):
        made = tables.generate_all(STOCK, PARTS)
        self.assertEqual(set(made), set(registry.TABLES))
        self.assertEqual(len(tables.parse(made['parts_belt'])[1]), 301)
        for table in registry.TABLES:
            tables.check(table, made[table], PARTS, STOCK[table])
            if table not in ('parts_chest', 'parts_belt'):
                self.assertEqual(made[table], STOCK[table])
        with self.assertRaisesRegex(ValueError, 'exactly the twelve'):
            tables.generate_all({'parts_chest': STOCK['parts_chest']}, PARTS)

    def test_robe_rows_carry_hide_flags(self):
        robe = part(slot='robe', number=300, families=['accessory'], set=..., genderedCut=False, tiers={}, mesh='skinned',
                    hide=['CHEST', 'PELVIS'])
        text = tables.generate('parts_robe', STOCK['parts_robe'], [robe])
        columns, rows = tables.parse(text)
        self.assertEqual(len(rows), 301)
        live = dict(zip(columns, rows[300]))
        self.assertEqual((live['COSTMODIFIER'], live['ACBONUS'], live['HIDECHEST'], live['HIDEPELVIS'], live['HIDEHEAD']),
                         ('0', '0.00', '1', '1', '0'))
        self.assertEqual(set(rows[39]), {'****'})
        tables.check('parts_robe', text, [robe], STOCK['parts_robe'])

    def test_wrong_stock_is_refused(self):
        short = '\r\n'.join(STOCK['parts_chest'].split('\r\n')[:100]) + '\r\n'
        with self.assertRaisesRegex(ValueError, 'expected 201 stock rows'):
            tables.generate('parts_chest', short, PARTS)
        with self.assertRaisesRegex(ValueError, 'Not a 2DA'):
            tables.generate('parts_chest', 'nope', PARTS)
        with self.assertRaisesRegex(ValueError, 'Unknown parts table'):
            tables.generate('parts_head', STOCK['parts_chest'], PARTS)

    def check_fails(self, message, text, parts=PARTS):
        with self.assertRaisesRegex(ValueError, message):
            tables.check('parts_chest', text, parts, STOCK['parts_chest'])

    def test_check_fails_on_gap_duplicate_missing_and_stray_rows(self):
        text = tables.generate('parts_chest', STOCK['parts_chest'], PARTS)
        lines = text.split('\r\n')
        row = {int(line.split()[0]): index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].isdigit()}
        self.check_fails('rows must count from 0 with no gaps', '\r\n'.join(lines[:row[650]] + lines[row[651]:]))
        self.check_fails('rows must count from 0 with no gaps', '\r\n'.join(lines[:row[650]] + [lines[row[650]]] + lines[row[650]:]))
        self.check_fails('registry part 6000 has no row', '\r\n'.join(lines[:row[900]]) + '\r\n')
        self.check_fails('row 6000 is not the padding row', text, [PARTS[1]])
        self.check_fails('row 650 is not the padding row', text.replace(lines[row[650]], '650  0             0.00'))
        self.check_fails('row 6000 is not the live row', text.replace(lines[row[6000]], '6000 5             4.00'))
        self.check_fails('a stock row changed', text.replace(lines[row[5]], '5    0             8.00     '))
        self.check_fails('rows continue past the highest part number', text + '9003 ****          ****\r\n')
        self.check_fails('stock rows are missing', '\r\n'.join(lines[:row[100]]) + '\r\n', [])


if __name__ == '__main__':
    unittest.main()
