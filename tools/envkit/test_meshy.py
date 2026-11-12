"""The credit cap holds across paid calls, and only a triangle-bounded model at or under 100k is taken off Meshy."""
import json
import struct
import tempfile
import unittest
from pathlib import Path

from . import meshy


def glb(path, triangle_counts):
    """A binary glTF whose primitives claim the given triangle counts (the count is read from the accessors alone)."""
    document = {'accessors': [{'count': count * 3} for count in triangle_counts],
                'meshes': [{'primitives': [{'indices': index, 'attributes': {'POSITION': index}}]}
                           for index in range(len(triangle_counts))]}
    body = json.dumps(document).encode(); body += b' ' * (-len(body) % 4)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'glTF' + struct.pack('<II', 2, 20 + len(body)) + struct.pack('<II', len(body), 0x4E4F534A) + body)
    return path


class FakeMeshy:
    """Stands in for the CLI: records every call, never spends."""

    def __init__(self, status='SUCCEEDED', credits=15, triangle_counts=(9000,), answer=True):
        self.calls = []; self.status = status; self.credits = credits; self.triangle_counts = triangle_counts; self.answer = answer

    def __call__(self, arguments, folder):
        self.calls.append(arguments)
        if arguments[1] == 'create':
            return (0, {'result': {'task': {'id': 'task-' + arguments[arguments.index('--operation-id') + 1]}}}) if self.answer else (1, {})
        if arguments[1] == 'wait':
            Path(arguments[arguments.index('--save-json') + 1]).parent.mkdir(parents=True, exist_ok=True)
            Path(arguments[arguments.index('--save-json') + 1]).write_text('{}', encoding='utf-8')
            return (0 if self.status == 'SUCCEEDED' else 1), {'result': {'task': {'id': arguments[2], 'status': self.status,
                                                                             'consumed_credits': self.credits}}}
        if arguments[0] == 'download':
            glb(Path(arguments[arguments.index('--output-dir') + 1]) / 'model.glb', self.triangle_counts)
            return 0, {}
        raise AssertionError('Unexpected call ' + ' '.join(arguments))


class MeshyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup); self.root = Path(self.folder.name)
        self.image = self.root / 'ref.png'; self.image.write_bytes(b'png')
        self.ledger = meshy.Ledger.create(self.root / 'ledger.json', 50)

    def test_arguments_bound_the_triangles_of_everything_that_can_be_downloaded(self):
        prop = meshy.prop_arguments(self.image, 6000)
        self.assertEqual(prop[prop.index('--model-type') + 1], 'smart-topology')
        self.assertEqual(prop[prop.index('--target-polycount') + 1], '6000')
        with self.assertRaisesRegex(ValueError, 'prop target'):
            meshy.prop_arguments(self.image, 20000)
        remesh = meshy.remesh_arguments('task-1', 100000)
        self.assertEqual(remesh[remesh.index('--target-polycount') + 1], '92000')  # asks low: a remesh overshoots
        with self.assertRaisesRegex(ValueError, 'ceiling'):
            meshy.remesh_arguments('task-1', 150000)
        building = meshy.building_arguments([self.image, self.image, self.image])
        self.assertNotIn('--target-polycount', building)
        with self.assertRaisesRegex(ValueError, 'one to four'):
            meshy.building_arguments([self.image] * 5)

    def test_the_cap_counts_estimates_until_meshy_reports_and_refuses_the_call_that_would_pass_it(self):
        run = FakeMeshy(credits=15)
        meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=run)
        meshy.submit(self.ledger, 'b', 'shack', 'building', meshy.building_arguments([self.image]), self.root / 'work', run=run)
        self.assertEqual(meshy.Ledger(self.ledger.path).committed(), 45)
        before = len(run.calls)
        with self.assertRaisesRegex(ValueError, 'cap would be exceeded'):
            meshy.submit(self.ledger, 'c', 'atm', 'prop', meshy.prop_arguments(self.image, 5000), self.root / 'work', run=run)
        self.assertEqual(len(run.calls), before)  # refused before anything was sent
        with self.assertRaisesRegex(ValueError, 'already used'):
            meshy.submit(self.ledger, 'a', 'vending', 'remesh', meshy.remesh_arguments('task-a', 9000), self.root / 'work', run=run)

    def test_a_ledger_held_during_a_wait_does_not_drop_entries_added_meanwhile(self):
        run = FakeMeshy()
        held = meshy.Ledger(self.ledger.path)
        meshy.submit(held, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=run)
        other = meshy.Ledger(self.ledger.path)  # a second process submits while the first is still waiting
        meshy.submit(other, 'b', 'atm', 'prop', meshy.prop_arguments(self.image, 5000), self.root / 'work', run=run)
        meshy.wait(held, 'a', self.root / 'work', run=run)
        self.assertEqual([row['key'] for row in meshy.Ledger(self.ledger.path).data['entries']], ['a', 'b'])

    def test_reservations_made_at_once_cannot_pass_the_cap_or_drop_each_other(self):
        import threading
        from tools.headkit.gpu_lock import locked
        refused = []

        def reserve(number):
            try:
                meshy.Ledger(self.ledger.path).reserve(f'k{number}', 'vending', 'prop', [])
            except ValueError as error:
                refused.append(str(error))
        threads = [threading.Thread(target=reserve, args=(number,)) for number in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        after = meshy.Ledger(self.ledger.path)  # a cap of 50 holds three props of 15, however the six calls fall
        self.assertEqual((len(after.data['entries']), after.committed(), len(refused)), (3, 45, 3))
        self.assertTrue(all('cap would be exceeded' in message for message in refused))
        impatient = meshy.Ledger(self.ledger.path); impatient.PATIENCE = 0.1
        with locked(self.ledger.path):  # another call is in the middle of its change
            with self.assertRaisesRegex(ValueError, 'held by another call'):
                impatient.update('k0', state='submitted')

    def test_an_unanswered_submission_stays_counted_and_uncertain(self):
        with self.assertRaisesRegex(ValueError, 'uncertain'):
            meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work',
                         run=FakeMeshy(answer=False))
        self.assertEqual((self.ledger.entry('a')['state'], self.ledger.committed()), ('uncertain', 15))

    def test_a_submission_meshy_refuses_gives_its_reservation_back(self):
        def full(arguments, folder):  # the plan's queue is full: Meshy answers, and creates nothing
            return 1, {'ok': False, 'error': {'http_status': 429, 'message': 'NoMorePendingTasks'}}
        with self.assertRaisesRegex(ValueError, 'Meshy refused a: NoMorePendingTasks'):
            meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=full)
        self.assertEqual((meshy.Ledger(self.ledger.path).data['entries'], self.ledger.committed()), ([], 0))

        def remembered(arguments, folder):  # the CLI keeps a refused operation id and answers for Meshy the next time
            return 1, {'ok': False, 'result': {'submission': {'state': 'rejected', 'task_id': None}, 'task': None},
                       'error': {'code': 'operation_conflict', 'http_status': None, 'message': 'already rejected'}}
        with self.assertRaisesRegex(ValueError, 'use a new one'):
            meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=remembered)
        self.assertEqual(self.ledger.committed(), 0)

    def test_a_call_refused_before_it_is_sent_gives_its_reservation_back(self):
        def refuse(arguments, folder):
            raise meshy.NotSent('npm not found')
        with self.assertRaisesRegex(ValueError, 'npm not found'):
            meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=refuse)
        self.assertEqual((meshy.Ledger(self.ledger.path).data['entries'], self.ledger.committed()), ([], 0))
        with self.assertRaises(TypeError):  # no work folder: refused before anything is reserved
            meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), None, run=FakeMeshy())
        self.assertEqual(meshy.Ledger(self.ledger.path).data['entries'], [])
        meshy.submit(self.ledger, 'a', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=FakeMeshy())  # the key is free

    def test_an_incomplete_download_leaves_no_folder_in_the_way_of_the_retry(self):
        run = FakeMeshy()
        meshy.submit(self.ledger, 'p', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=run)
        meshy.wait(self.ledger, 'p', self.root / 'work', run=run)

        def cut_short(arguments, folder):
            bank = Path(arguments[arguments.index('--output-dir') + 1]); bank.mkdir(parents=True); (bank / 'texture_0.png').write_bytes(b'x')
            return 1, {}
        with self.assertRaisesRegex(ValueError, 'Download incomplete'):
            meshy.download(self.ledger, 'p', self.root / 'work', self.root / 'bank', run=cut_short)
        self.assertFalse((self.root / 'bank').exists())
        self.assertEqual(list(meshy.download(self.ledger, 'p', self.root / 'work', self.root / 'bank', run=run).values()), [9000])

    def test_a_full_detail_generation_is_never_downloaded_but_its_remesh_is(self):
        run = FakeMeshy(credits=30, triangle_counts=(60000, 31000))
        task = meshy.submit(self.ledger, 'gen', 'shack', 'building', meshy.building_arguments([self.image]), self.root / 'work', run=run)
        meshy.wait(self.ledger, 'gen', self.root / 'work', run=run)
        with self.assertRaisesRegex(ValueError, 'remesh gen first'):
            meshy.download(self.ledger, 'gen', self.root / 'work', self.root / 'bank-gen', run=run)
        run.triangle_counts = (1873900,)  # as a master it comes down whole, with no ceiling, and is marked as one
        self.assertEqual(list(meshy.download(self.ledger, 'gen', self.root / 'work', self.root / 'master-gen', master=True, run=run).values()),
                         [1873900])
        self.assertTrue(self.ledger.entry('gen')['master'])
        run.triangle_counts = (60000, 31000); run.credits = 5
        meshy.submit(self.ledger, 'rm', 'shack', 'remesh', meshy.remesh_arguments(task, 100000), self.root / 'work', run=run)
        meshy.wait(self.ledger, 'rm', self.root / 'work', run=run)
        counts = meshy.download(self.ledger, 'rm', self.root / 'work', self.root / 'bank-rm', run=run)
        self.assertEqual(list(counts.values()), [91000]); self.assertIs(self.ledger.entry('rm')['accepted'], True)
        self.assertEqual(self.ledger.committed(), 35)
        with self.assertRaisesRegex(ValueError, 'already a reduced model'):
            meshy.download(self.ledger, 'rm', self.root / 'work', self.root / 'master-rm', master=True, run=run)

    def test_a_model_over_the_ceiling_is_reported_not_accepted(self):
        run = FakeMeshy(triangle_counts=(103196,))
        meshy.submit(self.ledger, 'p', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=run)
        meshy.wait(self.ledger, 'p', self.root / 'work', run=run)
        with self.assertRaisesRegex(ValueError, 'exceeds 100000'):
            meshy.download(self.ledger, 'p', self.root / 'work', self.root / 'bank', run=run)
        self.assertIs(self.ledger.entry('p')['accepted'], False)  # on record, so its folder is not taken for a working model

    def test_a_failed_task_is_settled_at_what_meshy_charged(self):
        run = FakeMeshy(status='FAILED', credits=0)
        meshy.submit(self.ledger, 'p', 'vending', 'prop', meshy.prop_arguments(self.image, 6000), self.root / 'work', run=run)
        with self.assertRaisesRegex(ValueError, 'FAILED'):
            meshy.wait(self.ledger, 'p', self.root / 'work', run=run)
        self.assertEqual((self.ledger.entry('p')['state'], self.ledger.committed()), ('failed', 0))

    def test_arguments_cmd_would_rewrite_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'cannot contain'):
            meshy.run_cli(['image-to-3d', 'create', '--texture-prompt', 'red & blue'], self.root / 'x')


if __name__ == '__main__':
    unittest.main()
