"""The shared review session: its scripts, item table, merged base-item table and resume rule (no client is started)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.headkit.common import pin
from tools.itemkit import review_session as R
from tools.itemkit.fixture import SHOTS, entry_script, shot_script

TABLE = ('2DA V2.0\n\n     label  MaxRange  ItemClass\n'
         '6    xbow   {xbow}  WBwXh\n22   dagger 100  WSwDg\n61   sling  {sling}  {klass}\n')


class ScriptTests(unittest.TestCase):
    def test_the_session_script_reads_the_item_and_its_carry_at_run_time(self):
        text = R.session_script('right', 'sr_it_prior')
        self.assertNotIn('ITEM_RESREF', text); self.assertNotIn('@', text.replace('"@"', ''))
        self.assertIn('GetItemPossessedBy(t,GetLocalString(GetModule(),"ITK_ITEM"))', text)
        for number in range(len(R.CARRIES)): self.assertIn(f'if(GetLocalInt(GetModule(),"ITK_CARRY")=={number}) {{', text)
        self.assertEqual(len(R.PLAN_LINE.findall(text)), len(R.SESSION_SHOTS) * len(R.CARRIES))
        self.assertLess(len(R.SESSION_SHOTS) * 3, len(SHOTS))                                  # a third of a fixture's shots, or fewer
        self.assertEqual(text.count('"firing",n,'), len(R.CARRIES)); self.assertIn(',6,5.0));', text)   # one long hold a carry
        self.assertIn('if(n==4 || n==10) ItkAmmo(t);', text); self.assertIn('ItkClip(male,fire); ItkClip(female,fire);', text)
        self.assertIn('SetLocalInt(female,"STEP",36);', text); self.assertIn('if(n==13) ItkPark(t);', text)
        self.assertIn('SetCameraFacing(ItkFacing(t,check,facing),', text); self.assertIn('check!="firing"', text)
        self.assertEqual(text.count('ItkStart(0);'), 1); self.assertEqual(text.count('DelayCommand(4.0,ItkWatch(pc));'), 1)   # the routine does not call itself
        self.assertIn('  ItkStart(0);\n}', text); self.assertIn('ExecuteScript("sr_it_prior",GetModule());', text)
        self.assertEqual(text.count('void ItkDone()'), 1); self.assertIn('WriteTimestampedLogEntry("ITEMKIT_SESSION done")', text)
        self.assertLess(text.index('void ItkStart(int index)'), text.index('void ItkDone()'))     # declared before its first use
        self.assertIn('INVENTORY_SLOT_LEFTHAND));', R.session_script('left'))

    def test_the_heartbeat_follows_the_current_item(self):
        script = 'void main(){ object blade=GetItemPossessedBy(OBJECT_SELF,"sr_cougar"); }'
        self.assertEqual(R.session_heartbeat(script), 'void main(){ object blade=GetItemPossessedBy(OBJECT_SELF,GetLocalString(GetModule(),"ITK_ITEM")); }')
        with self.assertRaises(ValueError): R.session_heartbeat('void main(){}')

    def test_the_item_table_numbers_the_carries_and_names_the_firing_clip(self):
        table = R.items_table([{'item': 'sr_a', 'carry': 'hip', 'fire': 'fire_pst'}, {'item': 'sr_b', 'carry': 'shoulder', 'fire': ''}]).decode('ascii')
        self.assertEqual(table, '2DA V2.0\n\n   Item  Carry  Fire\n0  sr_a  0  fire_pst\n1  sr_b  1  ****\n')

    def test_the_session_shots_leave_the_two_bodies_apart_and_fit_the_item_time(self):
        # The female's step s falls in the male's step s + 40 - offset: no step of his may be shot then.
        male = {row[0] for row in R.SESSION_SHOTS}; shift = 40 - R.SESSION_OFFSET
        self.assertFalse(male & {step + shift for step in male})
        self.assertEqual(max(male) + shift + 1, R.SESSION_STEPS)
        self.assertEqual(R.SESSION_SHOTS[-1][2], R.FIRE_CHECK)

    def test_a_fixture_shot_keeps_its_line_and_a_row_may_hold_longer(self):
        # Built fixtures are told apart by these lines: a row without its own hold must be written as it always was.
        self.assertIn('  if(n==1) DelayCommand(1.3,ItkTry(pc,t,base+0,"front-rear-sides",n,270.0,3.2,80.0,1.00));', shot_script())
        with self.assertRaisesRegex(ValueError, 'holds inside its own step'): shot_script(((1, 2.0, 'idle', 0, 2, 80, 1, 4.5),), checks=('idle',))
        with self.assertRaisesRegex(ValueError, 'every melee client check'): shot_script(R.SESSION_SHOTS)

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
                      'schemaVersion': 2, 'items': [{'item': name, 'carry': 'hip', 'fire': 'fire_pst', 'fixture': pin(fixture)} for name in ('sr_a', 'sr_b')]}
            (session/'session.json').write_text(json.dumps(record), encoding='utf-8'); captures = root/'captures'
            for name in ('sr_a', 'sr_b'):
                (captures/name).mkdir(parents=True); (captures/name/'capture.json').write_text(json.dumps({'finished': name == 'sr_a'}), encoding='utf-8')
            with mock.patch('tools.armorkit.client.start', side_effect=AssertionError('no client')), \
                 mock.patch('tools.armorkit.client.running', return_value=[]):
                self.assertEqual(R.capture(session, captures, root, only=['sr_a']), {'captured': [], 'alreadyCaptured': ['sr_a'], 'unfinished': []})
                with self.assertRaisesRegex(ValueError, 'Not in this session'): R.capture(session, captures, root, only=['sr_c'])
                with self.assertRaisesRegex(ValueError, 'Name the items'): R.capture(session, captures, root, again=True)
                with self.assertRaisesRegex(AssertionError, 'no client'): R.capture(session, captures, root, only=['sr_a'], again=True)
                with self.assertRaisesRegex(AssertionError, 'no client'): R.capture(session, captures, root)
            # the unfinished item alone was put in the table, and the toggle did not outlive the failed start
            self.assertEqual((user/'override'/'itk_items.2da').read_bytes(), R.items_table([{'item': 'sr_b', 'carry': 'hip', 'fire': 'fire_pst'}]))
            self.assertFalse((user/'override'/'itk_shots.2da').exists())


class FlashTests(unittest.TestCase):
    def test_the_brightest_picture_of_a_burst_is_the_sheet_frame(self):
        from PIL import Image
        dark = Image.new('RGB', (640, 360), (40, 40, 40)); lit = dark.copy(); lit.paste((255, 250, 200), (100, 80, 120, 95))
        faint = dark.copy(); faint.paste((255, 250, 200), (100, 80, 104, 84)); pictures = iter([dark, dark, faint, lit, dark] + [dark] * 500)
        client = mock.Mock(); client.grab.side_effect = lambda pid: next(pictures); saved = {}
        client.save.side_effect = lambda image, path: saved.__setitem__(Path(path).name, image)
        client.log_lines.return_value = ['ITEMKIT_SHOT shot=4 target=sr_it_male check=firing step=12 valid=1']
        row = {'shot': 4, 'target': 'sr_it_male', 'check': 'firing', 'step': 12, 'valid': True}
        clock = iter(range(10 ** 6))
        with mock.patch.object(R.time, 'monotonic', side_effect=lambda: next(clock) * .1):
            shot = R.fire_burst(client, mock.Mock(pid=1), 'user', 'folder', row, previous_read=0.0)
        self.assertNotIn('rejected', shot); self.assertGreater(shot['flash'], 0); self.assertGreaterEqual(shot['pictures'], 5)
        self.assertEqual(shot['captures'], ['human-male-firing-04-0.png', 'human-male-firing-04-1.png', 'human-male-firing-04-2.png'])
        self.assertIs(saved['human-male-firing-04-1.png'], lit); self.assertIs(saved['human-male-firing-04-0.png'], faint)
        self.assertEqual((shot['flash'], shot['longestGap']), (300, .1))

    def test_a_flash_in_the_first_picture_counts_and_a_stalled_burst_is_rejected(self):
        from PIL import Image
        dark = Image.new('RGB', (640, 360), (40, 40, 40)); lit = dark.copy(); lit.paste((255, 250, 200), (100, 80, 120, 95))
        row = {'shot': 4, 'target': 'sr_it_male', 'check': 'firing', 'step': 12, 'valid': True}
        def burst(pictures, times):
            client = mock.Mock(); feed = iter(pictures + [dark] * 500); client.grab.side_effect = lambda pid: next(feed)
            client.log_lines.return_value = ['ITEMKIT_SHOT shot=4 target=sr_it_male check=firing step=12 valid=1']
            clock = iter(times)
            with mock.patch.object(R.time, 'monotonic', side_effect=lambda: next(clock)):
                return R.fire_burst(client, mock.Mock(pid=1), 'user', 'folder', row, previous_read=0.0)
        first = burst([lit], [n * .1 for n in range(200)])
        self.assertEqual((first['flash'], first.get('rejected')), (300, None))
        # two pictures two seconds apart: whatever happened between them was not seen
        stalled = burst([dark], [0.0, 0.1, 2.1, 4.7, 4.8, 4.9])
        self.assertEqual((stalled['pictures'], stalled['rejected']), (3, 'burst stalled'))


if __name__ == '__main__':
    unittest.main()
