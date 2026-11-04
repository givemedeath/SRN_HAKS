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
import gpu_job  # noqa: E402
import guards  # noqa: E402
import head_setup  # noqa: E402
import launcher  # noqa: E402
import presets  # noqa: E402
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
        self.root = Path(folder.name).resolve()  # the Windows runner's temp path is an 8.3 short name
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
        for path in HERE.rglob('*'):
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


class GpuJob(Base):
    GEOMETRY = {'961:raw.glb': {'path': 'raw.glb'}, '963:shape.pt': {'path': 'shape.pt'}}

    class Comfy:
        """Runs out of memory once per failure asked for, retrying as Comfy.run does."""
        def __init__(self, failures):
            self.failures = failures

        def run(self, graph, out, before_submit):
            before_submit()
            if self.failures:
                self.failures -= 1
                before_submit()
                raise SystemExit(f'{out.name} failed: out of memory')
            return {}, GpuJob.GEOMETRY, 1

    def run_geometry(self, head, ledger, failures=0):
        with unittest.mock.patch.object(gpu_job, 'compile_graph', return_value={}):
            return gpu_job.geometry(self.Comfy(failures), head, head/'gpu', ledger, 'prefix', 0)

    def ledger(self, submissions=0):
        return {'geometrySubmissions': submissions, 'stages': {'calibrate': {'fov': {'detail': 30.0}}, 'appearance': {'files': {}}}}

    def test_every_submission_counts_and_is_saved(self):
        head = self.head()
        ledger = self.ledger()
        self.run_geometry(head, ledger, failures=1)
        self.assertEqual(ledger['geometrySubmissions'], 3)
        self.assertEqual(json.loads((head/'gpu/gpu.json').read_text())['geometrySubmissions'], 3)

    def test_a_retry_stops_at_the_cap(self):
        head = self.head()
        ledger = self.ledger(4)
        with self.assertRaisesRegex(SystemExit, 'cap of 5'):
            self.run_geometry(head, ledger, failures=1)
        self.assertEqual(ledger['geometrySubmissions'], 5)

    def test_new_geometry_drops_the_appearance_made_from_the_old_shape(self):
        head = self.head()
        ledger = self.ledger()
        self.run_geometry(head, ledger)
        self.assertNotIn('appearance', ledger['stages'])

    def reused(self, stages):
        data = json.loads((self.root/'workspace.json').read_text())
        data['comfy'] = {'url': 'http://127.0.0.1:1', 'root': 'comfy'}
        write(self.root/'workspace.json', data)
        workspace = Workspace.load(self.root)
        return workspace, launcher.reused_gpu_inputs(workspace, workspace.head('elf-male-a'), 'label', stages)

    def test_partial_runs_declare_a_frozen_ledger_and_what_they_reuse(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'stages': {'calibrate': {}, 'geometry': {'files': self.GEOMETRY}}})
        _, (files, extra) = self.reused(['appearance'])
        self.assertEqual(extra, ['--upstream', head/'launches/gpu-label.json'])
        self.assertEqual(Path(files[0]), head/'launches/gpu-label.json')
        self.assertEqual(json.loads(Path(files[0]).read_text())['stages']['geometry']['files'], self.GEOMETRY)
        self.assertTrue(files[1].endswith('normalized.png'))
        self.assertEqual(files[2], 'shape.pt')
        self.assertEqual(len(self.reused(['geometry'])[1][0]), 2)
        self.assertEqual(len(self.reused(['calibrate', 'appearance'])[1][0]), 2)

    def test_full_runs_reuse_nothing(self):
        self.head()
        self.assertEqual(self.reused(['calibrate', 'geometry', 'appearance'])[1], ([], []))
        self.assertEqual(self.reused(['calibrate'])[1], ([], []))

    def test_only_geometry_runs_meet_the_cap(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'geometrySubmissions': 5, 'stages': {}})
        with self.assertRaisesRegex(guards.Refused, 'cap of 5'):
            launcher.run_gpu(self.workspace, head.name, ['--stages', 'geometry'])
        with self.assertRaisesRegex(guards.Refused, 'comfy'):  # past the cap check
            launcher.run_gpu(self.workspace, head.name, ['--stages', 'appearance'])

    def test_a_partial_run_needs_its_earlier_stages(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'stages': {}})
        with self.assertRaisesRegex(guards.Refused, 'must run before'):
            self.reused(['appearance'])


class Locks(Base):
    def test_lock_waits_then_clears(self):
        path = self.root/'locks/gpu'
        path.mkdir(parents=True)
        waits = []
        with launcher.lock(lambda: [path.parent/'other'], 'me', waits.append):
            pass
        self.assertEqual(waits, [])

        def free(_):
            waits.append(1)
            path.rmdir()
        with launcher.lock(lambda: [path], 'me', free):
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

    def test_spec_resolves_game_paths_against_the_workspace(self):
        data = json.loads((self.root/'workspace.json').read_text())
        data.update(game={'root': 'game', 'client': 'game/client'}, trialBase={'haks': ['head.hak'], 'module': 'mod.mod', 'actorIdentity': {}})
        write(self.root/'workspace.json', data)
        write(self.root/'head.hak')
        write(self.root/'mod.mod')
        spec = json.loads(trials.write_spec(Workspace.load(self.root), 'elf', 1)[0].read_text())
        self.assertEqual(spec['gameRoot'], (self.root/'game').as_posix())
        self.assertEqual(spec['client'], (self.root/'game/client').as_posix())

    def test_spec_needs_the_trial_settings(self):
        with self.assertRaisesRegex(guards.Refused, 'trialBase'):
            trials.write_spec(self.workspace, 'elf', '1')


class Presets(Base):
    def overrides(self, head, cut):
        write(head/'overrides.json', {'mesh': {'neck': {'cut': cut}}})

    def marks(self, head):
        data = json.loads((self.root/'workspace.json').read_text())
        data['landmarks'] = 'marks.json'
        write(self.root/'workspace.json', data)
        write(self.root/'marks.json', {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}})
        return Workspace.load(self.root)

    @staticmethod
    def scan(results):
        def fake(_workspace, _head, _slope, reach):
            return results[reach]
        return fake

    def test_uv_floor_drops_to_the_reviewed_margin(self):
        head = self.head()
        self.overrides(head, {})
        self.receipt(head, 'unwrap', 1, {'result': RECEIPT_RESULT})
        overrides, notes, hold, changed = presets.plan(self.workspace, head.name, uv_only=True)
        self.assertTrue(changed)
        self.assertEqual(overrides['mesh']['uv']['minimumCoverage'], .29)
        self.assertEqual(hold, [])
        self.assertIn('uv floor', notes[0])

    def test_keep_floor_reports_the_floor_and_records_no_review(self):
        head = self.head()
        self.overrides(head, {})
        self.receipt(head, 'unwrap', 1, {'result': RECEIPT_RESULT})
        overrides, notes, _, changed = presets.plan(self.workspace, head.name, uv_only=True, keep_floor=True)
        self.assertNotIn('uv', overrides['mesh'])
        self.assertFalse(changed)
        self.assertIn('needs a person', notes[0])

    def test_coverage_reads_both_refusal_messages(self):
        for text in ('Insufficient useful UV coverage (0.281 at 2K, padding 8)', 'Insufficient useful UV coverage after face priority (0.281 at 2K)'):
            self.assertEqual(guards.coverage({'error': text}), .281)
        self.assertIsNone(guards.coverage({'error': 'something else'}))

    def test_uv_floor_holds_under_the_minimum(self):
        head = self.head()
        self.overrides(head, {})
        self.receipt(head, 'unwrap', 1, {'error': 'Insufficient useful UV coverage (0.19 at 2K)'})
        self.assertIn('needs fewer charts', presets.plan(self.workspace, head.name, uv_only=True)[2][0])
        self.assertEqual(presets.plan(self.workspace, head.name)[2], [])

    def test_fine_relief_comes_from_the_workspace(self):
        head = self.head()
        self.overrides(head, {})
        self.assertNotIn('fineRelief', presets.plan(self.workspace, head.name)[0]['mesh'])
        data = json.loads((self.root/'workspace.json').read_text())
        data['repairDefaults'] = {'fineRelief': {'maximumError': .02}, 'skipRaces': ['human']}
        write(self.root/'workspace.json', data)
        self.assertEqual(presets.plan(Workspace.load(self.root), head.name)[0]['mesh']['fineRelief'], {'maximumError': .02})

    def test_jaw_picks_the_largest_reach_that_finds_the_chin(self):
        head = self.head()
        workspace = self.marks(head)
        self.overrides(head, {'slope': -.2, 'reach': .08})
        results = {.08: {'jaw': .05, 'band': 0, 'top': 1, 'ok': True}, .06: {'jaw': .05, 'band': 0, 'top': 1, 'ok': True}, .04: {'jaw': .03, 'band': 0, 'top': 1, 'ok': True}, .03: {'jaw': .02, 'band': 0, 'top': 1, 'ok': True}}
        overrides, _, hold, _ = presets.plan(workspace, head.name, scan=self.scan(results))
        self.assertEqual(overrides['mesh']['neck']['cut']['reach'], .04)
        self.assertEqual(hold, [])

    def test_jaw_band_above_the_body_neck_holds(self):
        head = self.head()
        workspace = self.marks(head)
        self.overrides(head, {'slope': -.2, 'reach': .08})
        results = {.08: {'jaw': .03, 'band': .1, 'top': .05, 'ok': False}}
        self.assertIn('RUNBOOK 76', presets.plan(workspace, head.name, scan=self.scan(results))[2][0])

    def test_report_only_plans_change_nothing(self):
        head = self.head()
        workspace = self.marks(head)
        self.overrides(head, {'slope': -.2, 'reach': .08})
        before = (head/'overrides.json').read_bytes()
        results = {.08: {'jaw': .03, 'band': 0, 'top': 1, 'ok': True}}
        line, held = presets.apply(workspace, head.name, scan=self.scan(results))
        self.assertFalse(held)
        self.assertIn('jaw OK', line)
        self.assertEqual((head/'overrides.json').read_bytes(), before)


class Review(Base):
    def test_every_tool_documents_itself_and_needs_no_batch_names(self):
        tools = [path for path in (HERE/'review').glob('*.py') if not path.stem.startswith('_')]
        self.assertGreaterEqual(len(tools), 18)
        for path in tools:
            with self.subTest(path.name):
                text = path.read_text(encoding='utf-8')
                self.assertTrue(text.startswith('"""'))
                self.assertNotIn('race-heads-v1', text)
                self.assertNotIn('attempt-01/', text)

    def test_review_runs_in_the_heads_folder(self):
        self.workspace.heads.mkdir()
        with unittest.mock.patch.object(run_headbatch.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertEqual(run_headbatch.review(self.workspace, 'rowramps', ['elf-male-a'], False), 0)
        self.assertEqual(run.call_args.kwargs['cwd'], self.workspace.heads)
        self.assertTrue(run.call_args.args[0][2].endswith('rowramps.py'))

    def test_unknown_tool_is_refused(self):
        with self.assertRaises(SystemExit):
            run_headbatch.parser().parse_args(['review', 'no-such-tool'])

    def test_status_names_a_head_waiting_on_review(self):
        head = self.head()
        self.receipt(head, 'bake', 1, {'result': {}})
        self.assertEqual(launcher.status(self.workspace), ['elf-male-a | bake attempt-01 ran | WAITING ON REVIEW'])
        write(self.workspace.launches/'active-x.json', {'heads': ['elf-male-a']})
        self.assertIn('launch queued or running', launcher.status(self.workspace)[0])
        (self.workspace.launches/'active-x.json').unlink()
        self.receipt(head, 'render', 1, {'result': {}})
        os.utime(head/'run/render/attempt-01/receipt.json', (2**31, 2**31))
        self.assertIn('| finished', launcher.status(self.workspace)[0])


class SpoolTests(Base):
    def setUp(self):
        super().setUp()
        self.started = []
        self.tools = []
        self.queued = []
        self.tool_result = (0, ['done'])
        self.spool = self.make(self.workspace)

    def make(self, workspace):
        return spool.Spool(workspace, self.start, self.tool, lambda *args: self.queued.append(args))

    def tool(self, *arguments):
        self.tools.append(arguments)
        return self.tool_result

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
        self.spool.running[name] = unittest.mock.Mock(poll=lambda: 1)
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
        self.spool = self.make(Workspace.load(self.root))
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'repair', 'next': 'unwrap', 'notes': 'ok'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertIn('RUNBOOK 103', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_repair_gets_a_clay_sheet_and_the_skirt_zone(self):
        head = self.head(manifest={'mesh': {'neck': {'cut': {'skirt': {'gap': .02}}}}, 'fit': {'matrix': [[1, 0, 0, 0]]}, 'palette': {}})
        self.receipt(head, 'repair', 1, {'result': {}})
        self.finish(stage='repair')
        self.assertEqual([call[0] for call in self.queued], ['clay', 'skirtzone'])
        self.assertEqual(self.queued[1][-2:], (.02, .03))
        self.assertEqual(json.loads(self.queued[0][self.queued[0].index('--matrix')+1].read_text()), [[1, 0, 0, 0]])
        self.assertIn('skirt zone', self.spool.state['review']['elf-male-a/repair']['text'])

    def test_skirt_default_gap_is_the_toolkits(self):
        head = self.head(manifest={'mesh': {'neck': {'cut': {'skirt': {}}}}, 'fit': {'matrix': [[1, 0, 0, 0]]}, 'palette': {}})
        self.receipt(head, 'repair', 1, {'result': {}})
        self.finish(stage='repair')
        self.assertEqual(self.queued[1][-1:], (.03,))
        self.assertNotIn(.015, self.queued[1])

    def test_a_reused_stage_keeps_its_sheet(self):
        head = self.head()
        self.receipt(head, 'repair', 1, {'result': {}})
        write(self.workspace.spool/'sheets/elf-male-a-repair-attempt-01.png')
        self.finish('reused', 'repair')
        self.assertEqual(self.queued, [])

    def test_bake_queues_views_and_ownership_draws_its_rules(self):
        head = self.head()
        self.receipt(head, 'bake', 1, {'result': {}})
        self.finish(stage='bake')
        self.assertEqual(self.queued, [('bakeviews', 'elf-male-a')])
        self.receipt(head, 'ownership', 1, {'result': {}})
        self.finish(stage='ownership')
        self.assertEqual(self.queued[-1][:2], ('own_draft', 'elf-male-a'))
        self.assertEqual(json.loads(self.queued[-1][2].read_text())['mode'], 'rules')

    def test_palette_draws_the_row_ramps(self):
        head = self.head()
        self.receipt(head, 'palette', 1, {'result': {'rows': {'0': 7}}})
        self.finish(stage='palette')
        self.assertEqual(self.tools, [('review', 'rowramps', 'elf-male-a')])

    def test_coverage_failure_proposes_the_floor_and_waits_for_a_person(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'error': 'Insufficient useful UV coverage (0.281 at 2K)'})
        self.tool_result = (0, ['elf-male-a | uv floor 0.3 -> 0.27 | ready'])
        self.finish('failed')
        self.assertEqual(self.tools, [('presets', 'elf-male-a', '--uv-only')])
        self.assertEqual(self.started, [])
        self.assertIn('0.27', self.spool.state['attention']['elf-male-a/unwrap']['text'])

    def test_shell_failure_queues_the_shell_sheet(self):
        head = self.head()
        self.receipt(head, 'repair', 1, {'error': 'Master has 3 separate shells', 'attempts': {'shells': {'count': 3}}})
        write(head/'run/repair/attempt-01/master-uncut.glb')
        self.finish('failed', 'repair')
        self.assertEqual(self.queued[0][:2], ('cutshells', 'elf-male-a'))
        self.assertIn('cutshells queued', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_queued_repair_runs_the_presets_and_a_hold_stops_it(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'repair'})
        self.tool_result = (1, ['HOLD: no reach finds the chin'])
        self.spool.scan_requests()
        self.assertEqual(self.tools, [('presets', 'elf-male-a', '--apply', '--keep-floor')])
        self.assertEqual(self.started, [])
        self.assertIn('elf-male-a/repair', self.spool.state['attention'])

    def restored(self, age):
        self.head()
        self.spool.launch('bake', 'elf-male-a')
        name, info = next(iter(self.spool.state['launches'].items()))
        info['startedAt'] -= age
        self.spool.running.clear()
        self.spool.state['attention'].clear()
        return name

    def test_a_launch_from_before_a_restart_is_kept_while_its_marker_stands(self):
        name = self.restored(600)
        write(self.workspace.launches/f'active-20261104-120000-{name}.json', {'heads': ['elf-male-a']})
        self.spool.scan_launches()
        self.assertIn(name, self.spool.state['launches'])
        self.assertEqual(self.spool.state['attention'], {})

    def test_a_restored_launch_gets_time_to_write_its_marker(self):
        name = self.restored(5)
        self.spool.scan_launches()
        self.assertIn(name, self.spool.state['launches'])

    def test_a_restored_launch_with_no_marker_and_no_result_goes_to_attention(self):
        name = self.restored(600)
        self.spool.scan_launches()
        self.assertNotIn(name, self.spool.state['launches'])
        self.assertIn(f'{name}/launch', self.spool.state['attention'])

    def test_stop_file_ends_the_loop(self):
        write(self.workspace.spool/'STOP')
        worker = threading.Thread(target=self.spool.loop)
        worker.start()
        worker.join(5)
        self.assertFalse(worker.is_alive())


if __name__ == '__main__':
    unittest.main()
