"""A sheet's plan sends each model through Meshy once, under the cap, and collects what finished."""
import json
import tempfile
import unittest
from pathlib import Path

from . import meshy, sheet
from .test_meshy import FakeMeshy

SHEET = {'file': 'sheet.png', 'sha256': '0' * 64, 'size': [100, 100]}
ASSETS = {'building-hero': {'kind': 'building', 'subject': 'warehouse', 'box': [0, 0, 50, 50]},
          'building-rear': {'kind': 'building', 'subject': 'rear of a warehouse', 'box': [50, 0, 100, 50]},
          'desk': {'kind': 'prop', 'type': 'console-desk', 'subject': 'office desk', 'box': [0, 50, 30, 100]},
          'gate': {'kind': 'prop', 'type': 'vehicle-gate', 'subject': 'yard gate', 'box': [30, 50, 60, 100]},
          'unit': {'kind': 'prop', 'type': 'rooftop-unit', 'same': 'other/rooftop-unit', 'subject': 'rooftop unit', 'box': [60, 50, 100, 100]}}
PLAN = {'set': 'yard', 'prefix': 'yd', 'props': {'desk': {'triangles': 9000}, 'gate': {'triangles': 8000, 'key': 'yd-gate-a2'}},
        'building': {'views': ['building-hero', 'building-rear'], 'triangles': 200000}}


class SheetTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)
        self.sets = self.root / 'sets'; self.sets.mkdir(); (self.sets / 'yard.json').write_text(json.dumps({'sheet': SHEET, 'assets': ASSETS}), encoding='utf-8')
        self.selected = self.root / 'selected'; self.selected.mkdir()
        for name in ('desk', 'gate', 'building-hero', 'building-rear'):
            (self.selected / f'{name}-s101-b0.png').write_bytes(b'png')
        self.work, self.models, self.masters = (self.root / part for part in ('work', 'models', 'masters'))
        self.said = []; self.say = lambda text, **_: self.said.append(json.loads(text))

    def plan(self, **changes):
        path = self.sets / 'yard-meshy.json'; path.write_text(json.dumps({**PLAN, **changes}), encoding='utf-8')
        return sheet.load_plan(path)

    def test_a_plan_names_every_call_and_is_checked_against_its_set(self):
        plan = self.plan()
        self.assertEqual(plan['props'], {'desk': {'triangles': 9000, 'key': 'yd-desk-a1'}, 'gate': {'triangles': 8000, 'key': 'yd-gate-a2'}})  # a refused call goes again under a new key
        self.assertEqual((plan['building']['key'], plan['building']['remesh']), ('yd-building-a1', 'yd-building-a1-remesh'))
        self.assertIsNone(self.plan(building=None)['building'])  # a sheet of props alone
        for changes, said in (({'props': {'unit': {'triangles': 9000}}}, 'that one serves'), ({'props': {'building-hero': {'triangles': 9000}}}, 'not a prop'),
                              ({'props': {'desk': {'triangles': 90000}}}, 'triangle target'), ({'props': {'desk': {'triangles': 9000, 'key': 'yd-gate-a2'}, 'gate': PLAN['props']['gate']}}, 'its own ledger key'),
                              ({'building': {'views': ['desk'], 'triangles': 100000}}, 'not a building view'), ({'building': {'views': ['building-hero'], 'triangles': 300000}}, 'at most 200000'),
                              ({'prefix': 'Yard Works'}, 'prefix')):
            with self.assertRaisesRegex(ValueError, said):
                self.plan(**changes)

    def test_submit_sends_each_call_once_and_nothing_when_the_sheet_cannot_be_finished(self):
        plan = self.plan(); fake = FakeMeshy(); ledger = meshy.Ledger.create(self.root / 'ledger.json', 100)
        self.assertEqual(sheet.cost(ledger, plan), 15 + 15 + 30 + 5)
        self.assertEqual(sheet.submit(ledger, plan, self.selected, self.work, run=fake, say=self.say), ['yd-desk-a1', 'yd-gate-a2', 'yd-building-a1'])
        building = next(call for call in fake.calls if call[0] == 'multi-image-to-3d')
        self.assertEqual(len(building[building.index('--image-urls') + 1].split(',')), 2)  # both views, in the plan's order
        self.assertEqual(sheet.submit(ledger, plan, self.selected, self.work, run=fake, say=self.say), []); self.assertEqual(len(fake.calls), 3)
        self.assertEqual(sheet.status(ledger, plan)['calls'], {'yd-desk-a1': 'submitted', 'yd-gate-a2': 'submitted', 'yd-building-a1': 'submitted', 'yd-building-a1-remesh': None})
        self.assertEqual(sheet.cost(ledger, plan), 5)  # the remesh is still to come
        # Every reference is found and the whole of what is unsent fits under the cap before anything is sent.
        short = meshy.Ledger.create(self.root / 'short.json', 40); fake = FakeMeshy()
        with self.assertRaisesRegex(ValueError, 'needs 65 more credits and the ledger has 40 left'):
            sheet.submit(short, plan, self.selected, self.work, run=fake, say=self.say)
        (self.selected / 'gate-s101-b0.png').unlink(); fresh = meshy.Ledger.create(self.root / 'fresh.json', 100)
        with self.assertRaisesRegex(ValueError, 'One selected reference is needed for gate'):
            sheet.submit(fresh, plan, self.selected, self.work, run=fake, say=self.say)
        (self.selected / 'desk-s102-b0.png').write_bytes(b'png')
        with self.assertRaisesRegex(ValueError, 'needed for desk; found 2'):
            sheet.image(self.selected, 'desk')
        self.assertEqual(fake.calls, []); self.assertEqual(short.committed() + fresh.committed(), 0)

    def test_collect_downloads_what_finished_keeps_a_master_and_remeshes_the_building(self):
        plan = self.plan(); fake = FakeMeshy(); ledger = meshy.Ledger.create(self.root / 'ledger.json', 100)
        sheet.submit(ledger, plan, self.selected, self.work, run=fake, say=self.say)
        told = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=fake, say=self.say)
        self.assertEqual(told, {'failed': [], 'downloaded': ['yd-desk-a1', 'yd-gate-a2', 'yd-building-a1', 'yd-building-a1-remesh'], 'unsent': []})
        self.assertTrue((self.models / 'yd-desk-a1' / 'model.glb').is_file()); self.assertTrue((self.masters / 'yd-building-a1' / 'model.glb').is_file())
        self.assertTrue((self.models / 'yd-building-a1-remesh' / 'model.glb').is_file()); self.assertFalse((self.models / 'yd-building-a1').exists())  # the full generation is never the game model
        remesh = next(call for call in fake.calls if call[0] == 'remesh' and call[1] == 'create')
        self.assertEqual(remesh[remesh.index('--target-polycount') + 1], str(int(200000 * meshy.REMESH_HEADROOM)))
        self.assertEqual(set(sheet.status(ledger, plan)['calls'].values()), {'succeeded'}); self.assertEqual(sheet.cost(ledger, plan), 0)
        calls = len(fake.calls); again = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=fake, say=self.say)
        self.assertEqual((again, len(fake.calls)), ({'failed': [], 'downloaded': [], 'unsent': []}, calls))  # run again, it finds nothing to do

    def test_one_failed_model_does_not_stop_the_rest(self):
        plan = self.plan(building=None); ledger = meshy.Ledger.create(self.root / 'ledger.json', 100)
        sheet.submit(ledger, plan, self.selected, self.work, run=FakeMeshy(), say=self.say)

        class OneFails(FakeMeshy):
            def __call__(self, arguments, folder):
                self.status = 'FAILED' if arguments[1] == 'wait' and arguments[2] == 'task-yd-desk-a1' else 'SUCCEEDED'
                return super().__call__(arguments, folder)

        told = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=OneFails(), say=self.say)
        self.assertEqual(told, {'failed': ['yd-desk-a1'], 'downloaded': ['yd-gate-a2'], 'unsent': []})
        self.assertIn('FAILED', next(row['error'] for row in self.said if row.get('error')))
        # Run again, the model that failed is still told: a sheet with a model missing never reads as complete.
        again = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=FakeMeshy(), say=self.say)
        self.assertEqual(again, {'failed': ['yd-desk-a1'], 'downloaded': [], 'unsent': []}); self.assertEqual(self.said[-1], {'key': 'yd-desk-a1', 'error': 'yd-desk-a1 is failed'})
        # A model that came back over its ceiling is left where it landed, and is not taken for collected because it is there.
        ledger.update('yd-gate-a2', accepted=False)
        over = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=FakeMeshy(), say=self.say)
        self.assertEqual(over['failed'], ['yd-desk-a1', 'yd-gate-a2']); self.assertIn('over its triangle ceiling', self.said[-1]['error'])

    def test_a_remesh_that_fails_is_told_under_its_own_key(self):
        plan = self.plan(props={}); ledger = meshy.Ledger.create(self.root / 'ledger.json', 100)
        sheet.submit(ledger, plan, self.selected, self.work, run=FakeMeshy(), say=self.say)

        class RemeshFails(FakeMeshy):
            def __call__(self, arguments, folder):
                self.status = 'FAILED' if arguments[1] == 'wait' and arguments[2] == 'task-yd-building-a1-remesh' else 'SUCCEEDED'
                return super().__call__(arguments, folder)

        told = sheet.collect(ledger, plan, self.work, self.models, self.masters, run=RemeshFails(), say=self.say)
        self.assertEqual(told, {'failed': ['yd-building-a1-remesh'], 'downloaded': ['yd-building-a1'], 'unsent': []})  # the generation is paid for and kept: a new remesh key is all it needs

    def test_the_plan_the_ares_depot_was_run_from_reads(self):
        plan = sheet.load_plan(Path(__file__).with_name('sets') / 'ares-depot-meshy.json')
        self.assertEqual(len(plan['props']), 15); self.assertEqual(plan['props']['turret']['key'], 'ares-turret-a2')  # its first call was refused: the queue was full
        self.assertEqual(plan['building']['remesh'], 'ares-building-a1-remesh2')  # remeshed again when the building budget went to 200k


if __name__ == '__main__':
    unittest.main()
