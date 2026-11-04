import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
import unittest.mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guards  # noqa: E402
import head_setup  # noqa: E402
import launcher  # noqa: E402
import run_headbatch  # noqa: E402
import spool  # noqa: E402
import trials  # noqa: E402
from workspace import ENVIRONMENT, Workspace, WorkspaceError, prefix  # noqa: E402

DRIVE_PATH = re.compile(r'\b[A-Za-z]:[\\/]')
RECEIPT_RESULT = {'pixelAudits': {'2048': {'coverageFraction': .305}}}


def write(path, data=''):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
    return path


class Base(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        packages = self.root/'packages'
        packages.mkdir()
        write(self.root/'head-bindings.json', {'pythonPackages': {'directory': str(packages), 'files': []}, 'libraries': {'igl': {'directory': 'lib'}}})
        write(self.root/'workspace.json', {
            'kind': 'srn-head-workspace', 'schemaVersion': 1, 'toolchain': 'runtime/toolchain.json', 'migrationReceipt': 'runtime/migration.json',
            'headBindings': 'head-bindings.json', 'mdlCompiler': 'compiler.json', 'palettes': 'palettes', 'fitReferences': 'fit', 'bodyNecks': 'necks',
            'fitReferenceOverrides': {'pmg0': 'troll/pmg0_head014.mdl'}, 'slots': {'elf-male': [20, 21], 'troll-male': [31]}})
        self.workspace = Workspace.load(self.root)

    def head(self, name='elf-male-a', manifest=None):
        head = self.workspace.head(name)
        write(head/'manifest.json', manifest or {'ownership': {'mode': 'rules', 'rules': [{'channel': 1}]}, 'mesh': {}, 'palette': {'rows': {'0': 7}}, 'fit': {'matrix': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}})
        return head

    def receipt(self, head, stage, number, data):
        write(head/'run'/stage/f'attempt-{number:02d}'/'receipt.json', data)


class Portable(unittest.TestCase):
    def test_no_machine_paths_in_the_package(self):
        for path in HERE.iterdir():
            if path.suffix in ('.py', '.json') and path.name != 'test_headbatch.py':
                with self.subTest(path.name):
                    self.assertIsNone(DRIVE_PATH.search(path.read_text(encoding='utf-8')))


class WorkspaceTests(Base):
    def test_paths_resolve_against_the_workspace_folder(self):
        self.assertEqual(self.workspace.path('a/b'), self.root/'a/b')
        self.assertEqual(self.workspace.path(str(self.root/'x')), self.root/'x')
        self.assertEqual(self.workspace.setting('landmarks'), None)
        with self.assertRaisesRegex(WorkspaceError, 'designBindings'):
            self.workspace.require('designBindings')

    def test_load_needs_a_workspace_and_its_required_keys(self):
        with unittest.mock.patch.dict('os.environ', {}, clear=False):
            os.environ.pop(ENVIRONMENT, None)
            with self.assertRaisesRegex(WorkspaceError, ENVIRONMENT):
                Workspace.load()
        write(self.root/'bad/workspace.json', {'kind': 'srn-head-workspace', 'schemaVersion': 1})
        with self.assertRaisesRegex(WorkspaceError, 'missing'):
            Workspace.load(self.root/'bad')

    def test_slot_ids_prefixes_and_references(self):
        self.assertEqual(prefix('troll', 'female'), 'pfg0')
        self.assertEqual(self.workspace.head_ids(), {'elf-male-a': ('elf', 'male', 'pme0_head020'), 'elf-male-b': ('elf', 'male', 'pme0_head021'), 'troll-male-a': ('troll', 'male', 'pmg0_head031')})
        self.assertEqual(self.workspace.fit_reference('elf', 'female'), self.root/'fit/pfe0_head009.mdl')
        self.assertEqual(self.workspace.fit_reference('troll', 'male'), self.root/'troll/pmg0_head014.mdl')
        with self.assertRaisesRegex(WorkspaceError, 'pfg0'):
            self.workspace.fit_reference('troll', 'female')

    def test_cpu_slots_follow_a_live_file(self):
        self.assertEqual(self.workspace.cpu_slots(), 2)
        write(self.root/'cpu-slots', '4\n')
        self.assertEqual(self.workspace.cpu_slots(), 4)
        write(self.root/'cpu-slots', '9')
        self.assertEqual(self.workspace.cpu_slots(), 2)

    def test_launch_environment_drops_the_callers_pythonpath(self):
        with unittest.mock.patch.dict('os.environ', {'PYTHONPATH': 'caller'}):
            plain = self.workspace.python_environment()
            bound = self.workspace.python_environment(packages=True, tools=True)
        self.assertNotIn('PYTHONPATH', plain)
        self.assertEqual(plain['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertNotIn('caller', bound['PYTHONPATH'])
        self.assertIn('lib', bound['PYTHONPATH'])


class Guards(Base):
    def test_stray_bytecode_goes_and_other_unpinned_files_refuse(self):
        packages = self.root/'packages'
        kept = write(packages/'pinned/__pycache__/kept.pyc')
        stray = write(packages/'x/__pycache__/stray.pyc')
        bindings = write(self.root/'b.json', {'pythonPackages': {'directory': str(packages), 'files': [{'path': str(kept)}]}})
        self.assertEqual(guards.clean_stray_bytecode(bindings), ['x/__pycache__/stray.pyc'])
        self.assertFalse(stray.exists())
        self.assertTrue(kept.exists())
        write(packages/'extra.py')
        with self.assertRaisesRegex(guards.Refused, 'extra.py'):
            guards.clean_stray_bytecode(bindings)

    def test_ownership_needs_rules(self):
        guards.ownership_rules(self.head())
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 98'):
            guards.ownership_rules(self.head(manifest={'ownership': {'mode': 'rules', 'rules': []}}))

    def test_uv_margin_reads_the_newest_result(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'pixelAudits': {'2048': {'coverageFraction': .4}}}})
        self.receipt(head, 'unwrap', 2, {'error': 'failed'})
        guards.uv_margin(head)
        self.receipt(head, 'unwrap', 3, {'result': RECEIPT_RESULT})
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 87'):
            guards.uv_margin(head)
        self.head(manifest={'mesh': {'uv': {'minimumCoverage': .25}}})
        guards.uv_margin(head)

    def test_loop_budget_and_its_override(self):
        head = self.head()
        for number in (1, 2):
            self.receipt(head, 'ownership', number, {})
        with self.assertRaisesRegex(guards.Refused, 'limit 2'):
            guards.loop_budget(head, ['ownership'])
        guards.loop_budget(head, ['ownership'], {'ownership': 3})
        write(head/'budget-override-ownership')
        guards.loop_budget(head, ['ownership'])

    def test_geometry_cap(self):
        head = self.head()
        guards.geometry_cap(head)
        write(head/'gpu/gpu.json', {'geometrySubmissions': 5})
        with self.assertRaisesRegex(guards.Refused, 'stop and ask'):
            guards.geometry_cap(head)

    def test_jaw_guard(self):
        head = self.head()
        marks = {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}}
        self.assertAlmostEqual(guards.jaw_limit(head, marks), .04)
        write(head/'run/repair/attempt-01/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .03]}}}})
        guards.jaw(head, marks)
        write(head/'run/repair/attempt-02/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .05]}}}})
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 103'):
            guards.jaw(head, marks)
        write(head/'jaw-reviewed')
        guards.jaw(head, marks)
        self.assertIsNone(guards.jaw_limit(head, None))

    def test_unwrap_gates(self):
        receipt = {'attempts': [{'badFaceCount': 0, 'subtexel': {'1024': {'passed': True}}}], 'gutters': {'1024': {'nearbyChartPixelsByRadius': {'1': 0}}}, 'geometryUnchanged': True, 'charts': 9}
        self.assertTrue(guards.unwrap_gates(receipt)[0])
        receipt['gutters']['1024']['nearbyChartPixelsByRadius']['1'] = 2
        self.assertFalse(guards.unwrap_gates(receipt)[0])


class Locks(Base):
    def test_lock_waits_then_clears(self):
        path = self.root/'locks/gpu'
        path.mkdir(parents=True)
        waits = []
        with launcher.lock(path.parent/'other', 'me', 1, waits.append):
            pass
        self.assertEqual(waits, [])

        def free(_):
            waits.append(1)
            path.rmdir()
        with launcher.lock(path, 'me', 1, free):
            self.assertEqual((path/'owner').read_text(), 'me')
        self.assertEqual(waits, [1])
        self.assertFalse(path.exists())

    def test_cpu_slot_takes_the_next_free_one(self):
        (self.workspace.locks/'cpu-1').mkdir(parents=True)
        with launcher.cpu_slot(self.workspace, 'me') as slot:
            self.assertEqual(slot.name, 'cpu-2')
        self.assertFalse(slot.exists())

    def test_cpu_slot_released_when_the_body_raises(self):
        with self.assertRaises(RuntimeError):
            with launcher.cpu_slot(self.workspace, 'me') as slot:
                raise RuntimeError
        self.assertFalse(slot.exists())


class Launches(Base):
    def test_a_launch_record_is_never_reused(self):
        output = self.root/'launch'
        output.mkdir()
        with self.assertRaisesRegex(launcher.LaunchFailed, 'never reused'):
            launcher.launch(self.workspace, output, self.root/'i.json', [])

    def test_results_read_the_batch_output(self):
        out = write(self.root/'out.log', {'heads': [{'id': 'h', 'stages': [{'stage': 'bake', 'status': 'ran', 'x': 1}]}]})
        self.assertEqual(launcher.results(out), [{'id': 'h', 'error': '', 'stages': [{'stage': 'bake', 'status': 'ran'}]}])
        self.assertEqual(launcher.results(write(self.root/'bad.log', 'not json')), [])

    def test_guards_run_before_any_slot(self):
        self.head()
        for number in (1, 2):
            self.receipt(self.workspace.head('elf-male-a'), 'ownership', number, {})
        with self.assertRaisesRegex(guards.Refused, 'limit 2'):
            launcher.run_stages(self.workspace, 'n', 'ownership', ['elf-male-a'])
        self.assertFalse(self.workspace.locks.exists())

    def test_run_command_reports_a_refusal_as_a_result(self):
        self.head()
        for number in (1, 2):
            self.receipt(self.workspace.head('elf-male-a'), 'ownership', number, {})
        result = self.root/'result.json'
        with self.assertRaisesRegex(SystemExit, 'REFUSED'):
            run_headbatch.main(['--workspace', str(self.root), 'run', 'n', 'ownership', 'elf-male-a', '--result', str(result)])
        self.assertIn('limit 2', json.loads(result.read_text())['refused'])


class Setup(Base):
    def prepare(self):
        for file in ('pal-skin01.tga', 'pal-hair01.tga', 'pal-armor01.tga', 'pal-tattoo01.tga'):
            write(self.root/'palettes'/file, file)
        write(self.root/'compiler.json', {})
        write(self.root/'necks/pme0-neck001-ref.json', {})
        write(self.root/'fit/pme0_head001.mdl', 'model')
        write(self.root/'design/designs-elf.json', {'designs': {'elf-male-a': 'Hair: long\nEars: pointed\nOther: ignored'}})
        return write(self.root/'pick.png', 'image')

    def test_set_up_writes_a_complete_head(self):
        design = self.prepare()
        path = head_setup.set_up(self.workspace, 'elf-male-a', design, approval='picked by test', check=lambda *_: None)
        data = json.loads(path.read_text())
        self.assertEqual(data['fit']['model'], 'pme0_head020')
        self.assertEqual({row['name'] for row in data['features']}, {'hair', 'ears', 'neck'})
        self.assertEqual(data['mesh']['neck']['cut']['slope'], -.2)
        self.assertNotIn('taper', data['mesh']['neck'])
        self.assertEqual(data['palette']['toneMatch']['0']['reference'], 'elf-male-skin-v1')
        self.assertFalse((path.parent/'manifest.check.json').exists())
        with self.assertRaisesRegex(guards.Refused, 'not empty'):
            head_setup.set_up(self.workspace, 'elf-male-a', design, check=lambda *_: None)
        with self.assertRaisesRegex(guards.Refused, 'not in workspace slots'):
            head_setup.set_up(self.workspace, 'elf-male-z', design)

    def test_overrides_merge_remove_and_replace(self):
        base = {'a': {'x': 1, 'y': 2}, 'b': {'z': 3}, 'c': 4}
        head_setup.merge(base, {'a': {'y': None}, 'b': {'$replace': True, 'w': 5}, 'c': None})
        self.assertEqual(base, {'a': {'x': 1}, 'b': {'w': 5}})

    def test_refused_manifest_leaves_the_old_one(self):
        design = self.prepare()
        path = head_setup.set_up(self.workspace, 'elf-male-a', design, approval='t', check=lambda *_: None)
        before = path.read_bytes()

        def refuse(*_):
            raise guards.Refused('bad key')
        with self.assertRaisesRegex(guards.Refused, 'bad key'):
            head_setup.write_manifest(self.workspace, 'elf-male-a', refuse)
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse((path.parent/'manifest.check.json').exists())

    def test_manifest_refused_under_a_queued_launch(self):
        write(self.workspace.launches/'active-x.json', {'heads': ['elf-male-a']})
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 111'):
            head_setup.write_manifest(self.workspace, 'elf-male-a')

    def test_tone_and_shade_offset_clash(self):
        data = {'ownership': {'default': 0, 'rules': [{'channel': 1}]}, 'palette': {'toneMatch': {}, 'shadeOffsets': {'1': 2}}}
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 83'):
            head_setup.tone_every_channel(data, 'elf', 'male', 'h')


class Trials(Base):
    def test_spec_uses_each_heads_newest_native_and_chosen_rows(self):
        for file in ('head.hak', 'mod.mod'):
            write(self.root/file, file)
        data = json.loads((self.root/'workspace.json').read_text())
        data.update(game={'root': 'game', 'client': 'game/client'}, trialBase={'haks': ['head.hak'], 'module': 'mod.mod', 'actorIdentity': {'appearanceRow': 2}})
        write(self.root/'workspace.json', data)
        workspace = Workspace.load(self.root)
        head = workspace.head('elf-male-a')
        (head/'run/native/attempt-01/native').mkdir(parents=True)
        (head/'run/native/attempt-02').mkdir()
        self.receipt(head, 'palette', 1, {'result': {'rows': {'0': 3, '1': 5, '9': 33}}})
        out, count = trials.write_spec(workspace, 'elf', '2')
        spec = json.loads(out.read_text())
        self.assertEqual(count, 1)
        self.assertEqual(spec['prefix'], ['pme0', 'pfe0'])
        self.assertEqual(spec['identity']['raceId'], 1)
        row = spec['heads'][0]
        self.assertTrue(row['native'].endswith('attempt-01/native'))
        self.assertEqual(row['skinRows'], [3, 6, 13])
        self.assertEqual(row['hairRows'], [5, 65, 21])
        self.assertEqual(row['tattoo2Row'], 33)

    def test_spec_needs_the_trial_settings(self):
        with self.assertRaisesRegex(guards.Refused, 'trialBase'):
            trials.write_spec(self.workspace, 'elf', '1')


class SpoolTests(Base):
    def setUp(self):
        super().setUp()
        self.started = []
        self.spool = spool.Spool(self.workspace, self.start)

    def start(self, name, stages, head, approve, notes):
        self.started.append((stages, head, approve))

    def finish(self, status='ran', stage='unwrap', head='elf-male-a'):
        name = self.spool.launch(stage, head)
        self.started.clear()
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': head, 'stages': [{'stage': stage, 'status': status}]}]})
        self.spool.step()

    def test_unwrap_gate_advances_to_bake(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'attempts': [{'badFaceCount': 0, 'subtexel': {}}], 'gutters': {}, 'geometryUnchanged': True, 'charts': 9}})
        self.finish()
        self.assertEqual(self.started, [('bake', 'elf-male-a', 'unwrap')])

    def test_failed_unwrap_gate_waits_for_a_person(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'attempts': [{'badFaceCount': 2, 'subtexel': {}}], 'gutters': {}, 'geometryUnchanged': True, 'charts': 9}})
        self.finish()
        self.assertEqual(self.started, [])
        self.assertIn('bad faces 2', (self.workspace.spool/'attention.md').read_text())

    def test_palette_advances_only_on_reviewed_pins(self):
        head = self.head()
        self.receipt(head, 'palette', 1, {'result': {'rows': {'0': 7, '1': 9}}})
        self.finish(stage='palette')
        self.assertEqual(self.started, [])
        self.assertIn('elf-male-a/palette', self.spool.state['review'])
        write(self.workspace.spool/'reviewed-rows.json', {'elf-male-a': {'0': 7}})
        self.finish(stage='palette')
        self.assertEqual(self.started, [('export', 'elf-male-a', 'palette')])

    def test_export_gate_checks_the_fit_matrix(self):
        head = self.head()
        matrix = guards.read(head/'manifest.json')['fit']['matrix']
        self.receipt(head, 'export', 1, {'result': {'matrix': matrix, 'triangles': 100, 'plt': {'sha256': 'x'}}})
        self.finish(stage='export')
        self.assertEqual(self.started, [('native', 'elf-male-a', 'export')])
        self.receipt(head, 'export', 2, {'result': {'matrix': [], 'triangles': 100, 'plt': {'sha256': 'x'}}})
        self.finish(stage='export')
        self.assertEqual(self.started, [])

    def test_native_gate_needs_an_exact_read_back(self):
        head = self.head()
        good = {'onlyFixedStringFieldsChanged': True, 'positionsMaximumError': 0, 'normalsMaximumError': 0, 'uvMaximumError': 0}
        self.receipt(head, 'native', 1, {'result': good})
        self.finish(stage='native')
        self.assertEqual(self.started, [('render', 'elf-male-a', 'native')])
        self.receipt(head, 'native', 2, {'result': {**good, 'uvMaximumError': 1}})
        self.finish(stage='native')
        self.assertEqual(self.started, [])

    def test_package_pin_failure_retries_once(self):
        head = self.head()
        self.receipt(head, 'bake', 1, {'error': 'Python package file pins changed'})
        self.finish('failed', 'bake')
        self.assertEqual(self.started, [('bake', 'elf-male-a', None)])
        self.finish('failed', 'bake')
        self.assertEqual(self.started, [])
        self.assertIn('elf-male-a/bake', self.spool.state['attention'])

    def test_a_launch_with_no_result_goes_to_attention(self):
        self.head()
        name = self.spool.launch('bake', 'elf-male-a')
        self.spool.step()
        self.assertIn(f'{name}/launch', self.spool.state['attention'])

    def test_a_refused_launch_goes_to_attention(self):
        name = self.spool.launch('bake', 'elf-male-a')
        write(self.workspace.spool/'results'/f'{name}.json', {'refused': 'too many'})
        self.spool.step()
        self.assertEqual(self.spool.state['attention'][f'{name}/launch']['text'], 'too many')

    def test_queue_launches_each_head_and_refuses_unreviewed_rows(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'bake'})
        write(self.workspace.spool/'queue/b.json', {'heads': ['elf-male-a'], 'stages': 'export'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [('bake', 'elf-male-a', None)])
        self.assertEqual(list((self.workspace.spool/'queue').glob('*')), [])
        self.assertEqual(len(list((self.workspace.spool/'done').glob('*'))), 2)
        self.assertIn('elf-male-a/export', self.spool.state['attention'])

    def test_approval_of_repair_runs_the_jaw_guard(self):
        head = self.head()
        data = json.loads((self.root/'workspace.json').read_text())
        data['landmarks'] = 'marks.json'
        write(self.root/'workspace.json', data)
        write(self.root/'marks.json', {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}})
        write(head/'run/repair/attempt-01/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .05]}}}})
        self.spool = spool.Spool(Workspace.load(self.root), self.start)
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'repair', 'next': 'unwrap', 'notes': 'ok'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertIn('RUNBOOK 103', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_stop_file_ends_the_loop(self):
        write(self.workspace.spool/'STOP')
        worker = threading.Thread(target=self.spool.loop)
        worker.start()
        worker.join(5)
        self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
