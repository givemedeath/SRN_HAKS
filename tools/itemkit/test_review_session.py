"""The shared review session: its scripts, item table, merged base-item table and resume rule (no client is started)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.headkit.common import pin
from tools.itemkit import review_session as R
from tools.itemkit.fixture import SHOTS, entry_script

TABLE = ('2DA V2.0\n\n     label  MaxRange  ItemClass\n'
         '6    xbow   {xbow}  WBwXh\n22   dagger 100  WSwDg\n61   sling  {sling}  {klass}\n')


class ScriptTests(unittest.TestCase):
    def test_the_session_script_reads_the_item_and_its_carry_at_run_time(self):
        text = R.session_script('right', 'sr_it_prior')
        self.assertNotIn('ITEM_RESREF', text); self.assertNotIn('@', text.replace('"@"', ''))
        self.assertIn('GetItemPossessedBy(t,GetLocalString(GetModule(),"ITK_ITEM"))', text)
        for number in range(len(R.CARRIES)): self.assertIn(f'if(GetLocalInt(GetModule(),"ITK_CARRY")=={number}) {{', text)
        self.assertEqual(len(R.PLAN_LINE.findall(text)), len(SHOTS) * len(R.CARRIES))
        self.assertEqual(text.count('ItkStart(0);'), 1); self.assertEqual(text.count('DelayCommand(4.0,ItkWatch(pc));'), 1)   # the routine does not call itself
        self.assertIn('  ItkStart(0);\n}', text); self.assertIn('ExecuteScript("sr_it_prior",GetModule());', text)
        self.assertEqual(text.count('void ItkDone()'), 1); self.assertIn('WriteTimestampedLogEntry("ITEMKIT_SESSION done")', text)
        self.assertLess(text.index('void ItkStart(int index)'), text.index('void ItkDone()'))     # declared before its first use
        self.assertIn('INVENTORY_SLOT_LEFTHAND));', R.session_script('left'))

    def test_the_heartbeat_follows_the_current_item(self):
        script = 'void main(){ object blade=GetItemPossessedBy(OBJECT_SELF,"sr_cougar"); }'
        self.assertEqual(R.session_heartbeat(script), 'void main(){ object blade=GetItemPossessedBy(OBJECT_SELF,GetLocalString(GetModule(),"ITK_ITEM")); }')
        with self.assertRaises(ValueError): R.session_heartbeat('void main(){}')

    def test_the_item_table_numbers_the_carries(self):
        table = R.items_table([{'item': 'sr_a', 'carry': 'hip'}, {'item': 'sr_b', 'carry': 'shoulder'}]).decode('ascii')
        self.assertEqual(table, '2DA V2.0\n\n   Item  Carry\n0  sr_a  0\n1  sr_b  1\n')

    def test_a_fixture_entry_script_names_its_item_hand_and_carry(self):
        # fixture_item reads these from a built module; the same expressions on the script the fixture stage writes.
        for carry in R.CARRIES:
            entry = entry_script('sr_gun_7', carry=carry)
            found = [name for name in R.CARRIES if all(line in entry for line in R.PLAN_LINE.findall(R.shot_script(R.SHOT_CARRY[name], 'right')))]
            self.assertEqual(found, [carry])


class BaseItemTests(unittest.TestCase):
    def test_each_carrier_row_comes_from_the_packages_that_use_it(self):
        pistol_a = TABLE.format(xbow=20, sling=76, klass='WBwSl').encode(); pistol_b = TABLE.format(xbow=20, sling=77, klass='WBwSl').encode()
        rifle = TABLE.format(xbow=100, sling=65, klass='WBwSl').encode()
        merged = R.merged_baseitems([(61, pistol_a), (61, pistol_b), (6, rifle)]).decode('latin-1')
        rows = {line.split()[0]: line.split() for line in merged.splitlines()[3:]}
        self.assertEqual((rows['61'][2], rows['6'][2], rows['22'][2]), ('77', '100', '100'))

    def test_packages_that_disagree_on_a_row_are_refused(self):
        one = TABLE.format(xbow=20, sling=76, klass='WBwSl').encode(); other = TABLE.format(xbow=20, sling=77, klass='WOther').encode()
        with self.assertRaisesRegex(ValueError, 'disagree on base-item row 61'): R.merged_baseitems([(61, one), (61, other)])
        with self.assertRaisesRegex(ValueError, 'different rows or columns'): R.merged_baseitems([(61, one), (61, one + b'70 new 1 X\n')])


class ResumeTests(unittest.TestCase):
    def test_a_session_whose_items_are_all_captured_starts_no_client(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); session = root/'session'; user = session/'userdir'; (user/'override').mkdir(parents=True)
            module = user/'itk.mod'; module.write_bytes(b'mod'); fixture = root/'fixture.json'; fixture.write_bytes(b'{}')
            record = {'module': pin(module), 'haks': [], 'userDirectory': str(user),
                      'items': [{'item': name, 'carry': 'hip', 'fixture': pin(fixture)} for name in ('sr_a', 'sr_b')]}
            (session/'session.json').write_text(json.dumps(record), encoding='utf-8'); captures = root/'captures'
            for name in ('sr_a', 'sr_b'):
                (captures/name).mkdir(parents=True); (captures/name/'capture.json').write_text(json.dumps({'finished': name == 'sr_a'}), encoding='utf-8')
            with mock.patch('tools.armorkit.client.start', side_effect=AssertionError('no client')), \
                 mock.patch('tools.armorkit.client.running', return_value=[]):
                self.assertEqual(R.capture(session, captures, root, only=['sr_a']), {'captured': [], 'alreadyCaptured': ['sr_a'], 'unfinished': []})
                with self.assertRaisesRegex(ValueError, 'Not in this session'): R.capture(session, captures, root, only=['sr_c'])
                with self.assertRaisesRegex(AssertionError, 'no client'): R.capture(session, captures, root)
            # the unfinished item alone was put in the table, and the toggle did not outlive the failed start
            self.assertEqual((user/'override'/'itk_items.2da').read_bytes(), R.items_table([{'item': 'sr_b', 'carry': 'hip'}]))
            self.assertFalse((user/'override'/'itk_shots.2da').exists())


if __name__ == '__main__':
    unittest.main()
