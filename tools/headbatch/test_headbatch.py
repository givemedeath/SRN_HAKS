import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
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
        write(self.root/'design-bindings.json', {})
        write(self.root/'workspace.json', {
            'kind': 'srn-head-workspace', 'schemaVersion': 1, 'toolchain': 'runtime/toolchain.json', 'migrationReceipt': 'runtime/migration.json',
            'headBindings': 'head-bindings.json', 'toolsRoot':str(self.root/'shared-tools'), 'mdlCompiler': 'compiler.json', 'palettes': 'palettes', 'fitReferences': 'fit', 'bodyNecks': 'necks',
            'fitReferenceOverrides': {'pmg0': 'troll/pmg0_head014.mdl'}, 'slots': {'elf-male': [20, 21], 'troll-male': [31]}})
        self.workspace = Workspace.load(self.root)
        memory=unittest.mock.patch.object(launcher,'free_memory_gb',return_value=128)
        memory.start();self.addCleanup(memory.stop)

    def head(self, name='elf-male-a', manifest=None):
        head = self.workspace.head(name)
        write(head/'manifest.json', manifest or {'ownership': {'mode': 'rules', 'rules': [{'channel': 1}]}, 'mesh': {}, 'palette': {'rows': {'0': 7}}, 'fit': {'matrix': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}})
        return head

    def receipt(self, head, stage, number, data):
        write(head/'run'/stage/f'attempt-{number:02d}'/'receipt.json', data)


class MultiviewAdmissionTests(Base):
    def test_profile_horns(self):
        from PIL import Image
        from headkit.common import pin
        head = self.head()
        path = head/'review-evidence'/'cardinal-horns.json'
        roles = ('detail','geometry')
        images = {}
        for role in roles:
            for view in ('Front','Left','Right'):
                img = head/(role+view+'.png')
                Image.new('RGB',(704,704)).save(img)
                images[role+view] = pin(img)
        measurements = {'frontTips':[[171,100],[538,101]],'left':{'nearTip':[306,97],'farTip':None},
                        'right':{'nearTip':[396,94],'farTip':[402,94]}}
        review = {'images':images, **{role:measurements for role in roles}}
        write(path,review)
        contract = launcher.gpu_contract
        self.assertEqual(contract.cardinal_horn_pins(head,{'images':images}),[pin(path)])
        measurements['left']['farTip'] = [223,97]
        write(path,review)
        with self.assertRaisesRegex(Exception,'separated profile horns'):
            contract.cardinal_horn_pins(head,{'images':images})
        measurements['left']['farTip'] = None
        measurements['right']['farTip'] = [469,94]
        write(path,review)
        with self.assertRaisesRegex(Exception,'separated profile horns'):
            contract.cardinal_horn_pins(head,{'images':images})

    def test_saved_shape_prepare_replay(self):
        from headkit.common import pin
        head = self.head()
        def snapshot(attempt, changed=False):
            folder = head/'run'/'prepare'/attempt
            views = {}
            images = {}
            for view in ('Front','Left','Back','Right'):
                rows = {}
                for role in ('geometry','detail'):
                    name = role+'-pair.png'
                    key = role+view
                    img = pin(write(folder/'images'/view.lower()/name, key+str(changed and key=='detailLeft')))
                    rows[name] = images[key] = img
                views[view.lower()] = {'images':rows}
            receipt = {'stage':'prepare','state':'complete','manifestHash':'m','bindingsHash':'b',
                       'runtimeIdentity':'r','outputs':list(images.values()),'result':{'views':views,
                       'rigFovDegrees':20,'independentCropping':False}}
            return {'receipt':pin(write(folder/'receipt.json',receipt)), 'images':images}
        contract = launcher.gpu_contract
        original = snapshot('attempt-01')
        old = {'mode':'multiview','sharedFov':20,'fov':{'geometry':20,'detail':20},'prepared':original}
        current = snapshot('attempt-02')
        self.assertEqual(len(contract.identical_multiview_prepares(head,old,current)),18)
        with self.assertRaisesRegex(Exception,'byte-identical'):
            contract.identical_multiview_prepares(head,old,snapshot('attempt-03',True))
        with self.assertRaisesRegex(Exception,'another head'):
            contract.identical_multiview_prepares(head.parent/'other',old,current)



class Portable(unittest.TestCase):
    def test_no_machine_paths_in_the_package(self):
        for path in HERE.rglob('*'):
            if path.suffix in ('.py', '.json') and path.name != 'test_headbatch.py':
                with self.subTest(path.name):
                    self.assertIsNone(DRIVE_PATH.search(path.read_text(encoding='utf-8')))


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('scipy'),
                     'Fresh-master geometry test requires the bound headkit packages')
class CutDryTests(Base):
    def test_uncut_jaw_uses_lowest_triangle_at_neck_centre(self):
        import numpy as np
        from unittest import mock
        with mock.patch.object(sys, 'path', [str(HERE/'review'), str(HERE.parent), *sys.path]):
            from _frame import jaw_underside_at
        tri = np.array([[0.,0.,0.], [2.,0.,.2], [0.,2.,.4]])
        vertices = np.vstack([tri, tri + [0,0,1], tri + [4,0,-2]])
        faces = np.array([[2,1,0],[3,4,5],[6,7,8],[0,0,0]])
        self.assertAlmostEqual(jaw_underside_at(vertices, faces, [.5,.5]), .15)
        with self.assertRaisesRegex(ValueError,'misses the fitted head'):
            jaw_underside_at(vertices, faces, [2.,2.])

    def test_cut_proof_is_bound_to_master_audit_and_stops_before_reduction(self):
        import numpy as np
        mock = unittest.mock
        with mock.patch.object(sys, 'path', [str(HERE/'review'), str(HERE.parent), *sys.path]):
            import cutdry
            from headkit.common import pin, read, verify
            from headkit.gltf import write_mesh
        head = self.head()
        write(head/'bindings.json', {})
        body = write(head/'body.json', {})
        vertices = np.array([[0.,0.,0.], [1.,0.,0.], [0.,1.,0.], [0.,0.,1.]])
        faces = np.array([[0,2,1], [0,1,3], [0,3,2], [1,2,3]])
        self.receipt(head, 'fit', 1, {})
        self.receipt(head, 'precluster', 1, {})
        stages = {s:pin(head/'run'/s/'attempt-01/receipt.json') for s in ('fit','precluster')}
        runner = mock.Mock(state={'stages':stages})
        runner.input.return_value = body

        def run_to_master(stage, folder):
            write_mesh(folder/'master-uncut.glb', vertices, faces)
            v, f, _ = cutdry.N.neck_cut(vertices,faces,None,None)
            write_mesh(folder/'master.glb', v, f)
            cutdry.N.audit(folder/'master.glb')
            self.fail('The diagnostic continued past the master audit')

        runner._execute.side_effect = run_to_master
        cut_result = (vertices, faces, {'closure':'fan','loops':1})
        neck = {'frame':np.eye(4)}
        with mock.patch.object(cutdry,'Runner',return_value=runner), mock.patch.object(cutdry.N,'neck_cut',return_value=cut_result):
            cutdry.verified_cut_positions(head, neck, 'proof')
        evidence = read(head/'review-evidence/proof/cut-evidence.json')
        self.assertTrue(read(evidence['audit']['path'])['passed'])
        self.assertEqual(evidence['fit'], stages['fit'])
        verify([evidence['uncut'],evidence['master'],*evidence['inputs']],fresh=True)
        self.assertFalse((head/'run/repair').exists())

    def test_fresh_head_stops_before_cut_without_creating_a_repair_attempt(self):
        import numpy as np
        mock = unittest.mock
        with mock.patch.object(sys, 'path', [str(HERE/'review'), str(HERE.parent), *sys.path]):
            import cutdry
            from headkit.common import pin
            from headkit.gltf import write_mesh
            from headkit.runner import Runner

        head = self.root/'head'
        write(head/'manifest.json', {})
        source = head/'oriented.glb'
        vertices = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]])
        faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
        write_mesh(source, vertices, faces)
        fit = {'matrix': np.eye(4).tolist(), 'reviewed': True}
        mesh = {'neck': {'cut': {'height': 0.}}, 'shellInspection': {'visualReviewed': True}}
        runner = mock.Mock(data={'inputs': {'raw': {}}, 'mesh': mesh}, bindings={}, state={'stages': {}})
        runner.result.return_value = {'output': pin(source)}
        runner._fit.return_value = fit
        runner._body_neck.return_value = 'bound-body-neck'
        runner._execute.side_effect = lambda stage, folder: Runner._execute(runner, stage, folder)
        policy = cutdry.N.neck_policy(mesh['neck'], fit)
        with mock.patch.object(cutdry, 'Runner', return_value=runner), mock.patch.object(cutdry.N, 'body_neck'):
            positions = cutdry.dry_positions(head, policy, None)
            self.assertEqual(positions.shape, (4, 3))
            self.assertFalse((head/'run'/'repair').exists())
            runner.result.side_effect = ValueError('Stale stage')
            with self.assertRaisesRegex(ValueError, 'Stale stage'):
                cutdry.dry_positions(head, policy, None)
        with self.assertRaisesRegex(ValueError, 'No saved uncut master'):
            cutdry.dry_positions(head, policy, 'attempt-05')


class BoundedDesignOverrideTests(Base):
    def test_external_conditioning_and_local_design_share_the_cap(self):
        folder = self.root/'design'
        head = 'troll-male-a'
        for number in (1, 2):
            write(folder/'external-attempts'/head/f'{number:03}.json', {'attempt': number})
        write(folder/'external-attempts'/'troll-male-b'/'001.json', {'attempt': 1})
        guards.design_cap(folder, head)
        (folder/'launches'/f'launch-fixture-{head}-s7').mkdir(parents=True)
        with self.assertRaisesRegex(guards.Refused, '3 designs reached'):
            guards.design_cap(folder, head)

    def test_one_additional_design_stops_at_its_authorized_count(self):
        head = 'elf-male-a'
        folder = self.root/'design'
        for seed in range(3):
            (folder/'launches'/f'launch-1-{head}-s{seed}').mkdir(parents=True)
        override = folder/f'design-cap-override-{head}'
        write(override, 'unbounded text')
        with self.assertRaisesRegex(guards.Refused, 'bounded JSON'):
            guards.design_cap(folder, head)
        write(override, {'head': head, 'maximumDesigns': 4, 'approval': 'one extra fixture design'})
        guards.design_cap(folder, head)
        (folder/'launches'/f'launch-1-{head}-s3').mkdir()
        with self.assertRaisesRegex(guards.Refused, 'authorized cap of 4'):
            guards.design_cap(folder, head)


class VramPromptOwnershipTests(Base):
    def test_host_supervised_gpu_reserves_all_local_cpu_lanes(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from launcher import gpu_host_lease, locked
        ws = SimpleNamespace(data={'comfy': {'minimumFreeRAMGiB': 2}}, locks=self.root,
                             ram_gates=Mock(return_value={1:6,2:8,3:10,4:13,5:16,6:16}))
        with gpu_host_lease(ws):
            for lane in range(1, 7):
                with self.assertRaises(FileExistsError), locked(self.root/f'cpu-{lane}'):
                    pass
        with locked(self.root/'cpu-6'):
            pass
        ws.data['comfy'] = {}
        with gpu_host_lease(ws), locked(self.root/'cpu-1'):
            pass

    def test_face_quality_profile_uses_refined_unwrap(self):
        from head_setup import face_quality_profile
        uv = face_quality_profile()['mesh']['uv']
        self.assertEqual(uv['faceDensity'], 3)
        self.assertIs(uv['refinePacking'], True)

    def test_only_exact_candidate_in_its_workspace_can_be_interrupted(self):
        sys.path.insert(0, str(HERE/'compat'))
        from run_design_with_vram_limit import design_prompts
        token = 'a'*32
        root = self.root/'comfy/input'
        (root/'headkit-design'/token).mkdir(parents=True)
        def row(prompt, prefix):
            return [1, prompt, {'9': {'inputs': {'filename_prefix': prefix}}}]
        good = row('owned', f'headkit-design/{token}/elf-male-a-s44')
        other = row('other', f'headkit-design/{token}/elf-male-b-s44')
        missing = row('foreign', f'headkit-design/{"b"*32}/elf-male-a-s44')
        self.assertEqual(design_prompts([good, other, missing], 'elf-male-a-s44', root), ['owned'])


class WorkspaceTests(Base):
    def test_a_landmarks_file_not_written_yet_means_no_marks(self):
        data = json.loads((self.root/'workspace.json').read_text())
        data['landmarks'] = 'marks.json'
        write(self.root/'workspace.json', data)
        self.assertIsNone(Workspace.load(self.root).landmarks())

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

    def test_cpu_slots_read_what_windows_powershell_writes(self):
        for raw in ('4\r\n'.encode('utf-8-sig'), '4\r\n'.encode('utf-16')):
            (self.root/'cpu-slots').write_bytes(raw)
            self.assertEqual(self.workspace.cpu_slots(), 4)

    def test_a_spooler_child_loads_the_workspace_file_given(self):
        other = write(self.root/'other.json', json.loads((self.root/'workspace.json').read_text()))
        command = spool.Spool(Workspace.load(other)).command(['status'])
        self.assertEqual(command[command.index('--workspace')+1], str(other))

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
        write(head/'budget-override-ownership', {'head':head.name,'stage':'ownership',
              'maximumAttempts':3,'approval':'one additional correction'})
        guards.loop_budget(head, ['ownership'])
        (head/'run/ownership/attempt-03').mkdir()
        with self.assertRaises(guards.Refused):
            guards.loop_budget(head, ['ownership'])

    def test_geometry_cap(self):
        head = self.head()
        guards.geometry_cap(head)
        write(head/'gpu/gpu.json', {'geometrySubmissions': 5})
        with self.assertRaisesRegex(guards.Refused, 'stop and ask'):
            guards.geometry_cap(head)

    def test_geometry_extension_stops_at_exactly_one_extra(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'geometrySubmissions':5})
        write(head/'geometry-cap-override', {'head':head.name, 'maximumSubmissions':6, 'approval':'one more'})
        guards.geometry_cap(head)
        ledger = {'geometrySubmissions':5}
        gpu_job.spend_geometry_submission(head, head/'gpu', ledger)
        with self.assertRaisesRegex(guards.Refused, '6 geometry submissions'):
            guards.geometry_cap(head)
        with self.assertRaisesRegex(SystemExit, '6 geometry submissions'):
            gpu_job.spend_geometry_submission(head, head/'gpu', ledger)

    def test_a_ledger_older_than_its_counter_still_meets_the_cap(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'stages': {}})
        write(head/'gpu/geometry/node-961-node-961_00004.glb', '')
        self.assertEqual(gpu_job.submissions(head/'gpu', {}), 4)
        guards.geometry_cap(head)
        write(head/'gpu/geometry-02/node-961-node-961_00005_.glb', '')
        with self.assertRaisesRegex(guards.Refused, '5 geometry submissions'):
            guards.geometry_cap(head)

    def test_jaw_says_when_it_checked_nothing(self):
        head = self.head()
        marks = {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}}
        self.assertIn('no face marks', guards.jaw(head, None))
        self.assertIn('no repair audit', guards.jaw(head, marks))
        for audit in ({'neck': {'cut': {'jawLine': None}}}, {'neck': None}):
            write(head/'run/repair/attempt-01/reduction-audit.json', audit)
            self.assertIn('no jaw line', guards.jaw(head, marks))
        write(head/'jaw-reviewed')
        self.assertEqual(guards.jaw(head, marks), 'jaw reviewed visually')

    def test_jaw_reads_the_named_attempt(self):
        head = self.head()
        marks = {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}}
        write(head/'run/repair/attempt-01/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .03]}}}})
        write(head/'run/repair/attempt-02/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .05]}}}})
        self.assertIn('attempt-01', guards.jaw(head, marks, 'attempt-01'))

    def test_a_stray_another_launch_removed_is_no_failure(self):
        stray = self.root/'packages/gone.pyc'
        write(stray, '')
        with unittest.mock.patch.object(guards.os, 'unlink', side_effect=FileNotFoundError):
            self.assertEqual(guards.clean_stray_bytecode(self.root/'head-bindings.json'), ['gone.pyc'])

    def test_a_delete_racing_another_launch_is_no_failure(self):
        stray = self.root/'packages/gone.pyc'
        write(stray, '')
        real = guards.os.unlink

        def denied_then_gone(path):  # on Windows the loser of a delete sees access denied until the winner's finishes
            real(path)
            raise PermissionError(13, 'Access is denied')
        with unittest.mock.patch.object(guards.os, 'unlink', side_effect=denied_then_gone):
            self.assertEqual(guards.clean_stray_bytecode(self.root/'head-bindings.json'), ['gone.pyc'])

    def test_a_stray_that_cannot_be_deleted_is_refused(self):
        write(self.root/'packages/held.pyc', '')
        with unittest.mock.patch.object(guards.os, 'unlink', side_effect=PermissionError), unittest.mock.patch.object(guards.time, 'sleep'), \
                self.assertRaisesRegex(guards.Refused, 'held.pyc'):
            guards.clean_stray_bytecode(self.root/'head-bindings.json')

    def test_export_and_later_need_reviewed_rows_however_launched(self):
        head = self.head()
        guards.palette_rows(self.workspace, head.name, ['bake'])
        with self.assertRaisesRegex(guards.Refused, 'RUNBOOK 112'):
            guards.palette_rows(self.workspace, head.name, ['export', 'native'])
        write(self.workspace.spool/'reviewed-rows.json', {head.name: {'0': 7}})
        guards.palette_rows(self.workspace, head.name, ['export'])

    def test_run_refuses_unreviewed_rows(self):
        self.head()
        with unittest.mock.patch.object(launcher, 'cpu_slot') as slot, self.assertRaisesRegex(guards.Refused, 'RUNBOOK 112'):
            launcher.run_stages(self.workspace, 'n', 'export', ['elf-male-a'])
        slot.assert_not_called()

    def test_jaw_guard_uses_yawed_source_landmarks_with_a_pitched_fit(self):
        head = self.head()
        manifest = guards.read(head/'manifest.json')
        manifest['fit']['matrix'][2] = [0., .2, .9, .01]
        write(head/'manifest.json', manifest)
        marks = {head.name: {'source': {'eyeLeft': [-.03,.2,.1], 'eyeRight': [.03,.2,.1], 'lips': [0,.3,.06]}}}
        self.assertAlmostEqual(guards.jaw_limit(head, marks), .004 - .5*(.06-.004))

    def test_jaw_guard(self):
        head = self.head()
        marks = {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}}
        self.assertAlmostEqual(guards.jaw_limit(head, marks), .04)
        write(head/'run/repair/attempt-01/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .03]}}}})
        self.assertIn('jaw OK: attempt-01', guards.jaw(head, marks))
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

        def run(self, graph, out, before_submit, *, retry_oom=True):
            before_submit()
            if self.failures:
                self.failures -= 1
                if retry_oom:
                    before_submit()
                raise SystemExit(f'{out.name} failed: out of memory')
            return {}, GpuJob.GEOMETRY, 1

    def run_geometry(self, head, ledger, failures=0):
        with unittest.mock.patch.object(gpu_job, 'compile_graph', return_value={}):
            return gpu_job.geometry(self.Comfy(failures), head, head/'gpu', ledger, 'prefix', 0)

    def ledger(self, submissions=0):
        from headkit.common import pin
        conditioning=pin(write(self.root/'normalized.png','fixture conditioning'))
        return {'geometrySubmissions': submissions, 'stages': {'calibrate': {'fov': {'detail': 30.0},'sharedFov':30.0,'prepared':{'fixture':'verified'},'conditioning':{'geometry':conditioning,'detail':conditioning}}, 'appearance': {'files': {}}}}

    def test_shape_grid_changes_only_the_upsample_resolution(self):
        head, ledger = self.head(), self.ledger()
        baseline = gpu_job.geometry_graph(head, ledger, 'headkit/test/geometry', 0)
        compact = gpu_job.geometry_graph(head, ledger, 'headkit/test/geometry', 0, 1024)
        self.assertEqual(baseline['94']['inputs']['target_resolution'], 1536)
        self.assertEqual(compact['94']['inputs']['target_resolution'], 1024)
        baseline['94']['inputs']['target_resolution'] = 1024
        self.assertEqual(compact, baseline)

    def test_single_submission_retains_an_oom_without_retry_or_reseed(self):
        head, ledger = self.head(), self.ledger(3)
        status = {'completed': False, 'status_str': 'error', 'messages': ['out of memory']}
        server = self.Server(self.root, polls=[{'p1': {'status': status, 'outputs': {}}}])
        with self.assertRaisesRegex(SystemExit, 'out of memory'):
            gpu_job.geometry(server, head, head/'gpu', ledger, 'headkit/test/geometry', 0,
                             shape_grid=1024, single_submission=True)
        self.assertEqual(server.calls.count('/prompt'), 1)
        self.assertEqual(ledger['geometrySubmissions'], 4)
        self.assertTrue((head/'gpu/geometry/history.json').is_file())

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
        ledger = self.ledger()
        self.assertTrue(gpu_job.accept_geometry(ledger, {'files': self.GEOMETRY}, {'open': False}))
        self.assertNotIn('appearance', ledger['stages'])
        self.assertEqual(ledger['stages']['geometry']['files'], self.GEOMETRY)

    def test_a_rejected_shape_keeps_the_pair_it_found(self):
        ledger = self.ledger()
        ledger['stages']['geometry'] = {'files': 'accepted'}
        self.assertFalse(gpu_job.accept_geometry(ledger, {'files': self.GEOMETRY}, {'open': True, 'lowBands': [1], 'bandSquareCm': []}))
        self.assertEqual(ledger['stages']['geometry'], {'files': 'accepted'})
        self.assertIn('appearance', ledger['stages'])
        self.assertEqual(ledger['rejectedGeometry'], [{'files': self.GEOMETRY, 'occiput': {'open': True, 'lowBands': [1]}}])

    class Server(gpu_job.Comfy):
        """The ComfyUI routes as the job calls them, with the calls in order. polls answers /history; an exception in it is raised."""
        def __init__(self, root, reply=None, polls=()):
            super().__init__('http://comfy/', root)
            self.reply = reply or {'prompt_id': 'p1'}
            self.polls = list(polls)
            self.calls = []

        def send(self, route, data=None, **kwargs):
            self.calls.append(route)
            if route == '/queue':return b'{"queue_running":[],"queue_pending":[]}'
            if route == '/free':
                return b''
            if route == '/prompt':
                return json.dumps(self.reply).encode()
            answer = self.polls.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return json.dumps(answer).encode()

    DONE = {'p1': {'status': {'completed': True}, 'outputs': {'961': {'3d': [{'filename': 'raw_00001.glb'}]}}}}

    def server(self, **options):
        write(self.root/'output/raw_00001.glb', 'new bytes')
        return self.Server(self.root, **options)

    def test_a_trailing_slash_in_the_url_is_dropped(self):
        self.assertEqual(self.server().url, 'http://comfy')

    def test_the_cap_is_charged_only_when_comfyui_answered(self):
        calls = []
        server = self.server(polls=[self.DONE])
        server.run({}, self.root/'gpu/geometry', lambda: calls.append(list(server.calls)))
        self.assertEqual(calls, [['/queue','/free']])

    def test_a_stopped_server_spends_nothing(self):
        server = self.server()
        server.send = unittest.mock.Mock(side_effect=OSError('refused'))
        spent = unittest.mock.Mock()
        with self.assertRaises(OSError):
            server.run({}, self.root/'gpu/geometry', spent)
        spent.assert_not_called()

    def test_refused_nodes_stop_the_job(self):
        with self.assertRaisesRegex(SystemExit, 'refused nodes'):
            self.server(reply={'prompt_id': 'p1', 'node_errors': {'4': 'bad'}}).run({}, self.root/'gpu/geometry')

    def test_a_failed_poll_keeps_waiting_for_the_prompt(self):
        server = self.server(polls=[gpu_job.ComfyError('HTTP 500'), {}, self.DONE])
        with unittest.mock.patch.object(gpu_job.time, 'sleep'):
            _, files, _ = server.run({}, self.root/'gpu/geometry')
        self.assertEqual(len(files), 1)

    def test_a_prompt_past_the_deadline_stops_the_job(self):
        server = self.server()
        server.deadline = -1
        with self.assertRaisesRegex(SystemExit, 'p1 did not finish'):
            server.run({}, self.root/'gpu/geometry')

    def test_a_finished_prompt_with_no_files_is_a_failure(self):
        with self.assertRaisesRegex(SystemExit, 'no output files'):
            self.server(polls=[{'p1': {'status': {'completed': True}, 'outputs': {}}}]).run({}, self.root/'gpu/geometry')

    def test_a_reused_file_name_never_lands_on_an_earlier_run(self):
        old = write(self.root/'gpu/geometry/node-961-raw_00001.glb', 'old bytes')
        _, files, _ = self.server(polls=[self.DONE]).run({}, self.root/'gpu/geometry')
        row = files['961:raw_00001.glb']
        self.assertEqual(Path(row['path']), self.root/'gpu/geometry-02/node-961-raw_00001.glb')
        self.assertEqual(Path(row['path']).read_text(), 'new bytes')
        self.assertEqual(old.read_text().strip('"\n'), 'old bytes')

    def test_a_failed_geometry_keeps_the_pair_it_found(self):
        head = self.head()
        ledger = self.ledger()
        with self.assertRaises(SystemExit):
            self.run_geometry(head, ledger, failures=2)
        self.assertIn('appearance', ledger['stages'])

    def test_appearance_refuses_a_rejected_shape(self):
        head = self.head()
        ledger = self.ledger()
        ledger['stages']['geometry'] = {'files': self.GEOMETRY, 'occiput': {'open': True}}
        with self.assertRaisesRegex(SystemExit, 'open occiput'):
            gpu_job.appearance(None, head, head/'gpu', ledger, 'prefix', 0)

    def reused(self, stages):
        data = json.loads((self.root/'workspace.json').read_text())
        data['comfy'] = {'url': 'http://127.0.0.1:1', 'root': 'comfy'}
        write(self.root/'workspace.json', data)
        workspace = Workspace.load(self.root)
        return workspace, launcher.reused_gpu_inputs(workspace, workspace.head('elf-male-a'), 'label', stages)

    def approved_gpu_fixture(self,head):
        from headkit.common import pin
        import gpu_contract
        ledger=self.ledger();raw=pin(write(head/'gpu/raw.glb','geometry'));shape=pin(write(head/'gpu/shape.pt','shape'))
        row={'files':{'961:raw.glb':raw,'963:shape.pt':shape},'fov':30.,'submission':1,'occiput':{'open':False},
             'conditioningDigest':gpu_contract.calibration_id(ledger['stages']['calibrate'])}
        ledger['stages']['geometry']=row
        write(head/'gpu/gpu.json',ledger)
        evidence=gpu_contract.evidence_path(head,row);sheet=pin(write(evidence.parent/'sheet.png','fixture sheet'))
        write(evidence,{'geometryDigest':gpu_contract.geometry_id(row),'inputs':[raw,shape],'sheet':sheet})
        gpu_contract.review_geometry(head,'geometry-0001','synthetic fixture review')
        return guards.read(head/'gpu/gpu.json')

    def test_partial_runs_declare_a_frozen_ledger_and_what_they_reuse(self):
        head=self.head();ledger=self.approved_gpu_fixture(head)
        _,(files,extra)=self.reused(['appearance'])
        self.assertEqual(extra,['--upstream',head/'launches/gpu-label.json'])
        self.assertEqual(Path(files[0]),head/'launches/gpu-label.json')
        self.assertIn(ledger['geometryReview']['path'],files)
        self.assertIn(ledger['stages']['geometry']['files']['963:shape.pt']['path'],files)
        with self.assertRaisesRegex(ValueError,'Recalibration'):
            self.reused(['calibrate','appearance'])

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

    def launched_gpu(self, head, stages):
        data=guards.read(self.root/'workspace.json')
        data['comfy']={'url':'http://127.0.0.1:1','root':'comfy'}
        write(self.root/'workspace.json',data)
        self.approved_gpu_fixture(head)
        from headkit.common import pin
        write(head/'bindings.json',{'embree':pin(write(self.root/'embree.dll','fixture'))})
        ledger=guards.read(head/'gpu/gpu.json')
        preparation={'receipt':{'fixture':'prepare'},'images':{},'pins':[]}
        ledger['stages']['calibrate']['prepared']={'receipt':preparation['receipt'],'images':preparation['images']}
        import gpu_contract
        ledger['stages']['geometry']['conditioningDigest']=gpu_contract.calibration_id(ledger['stages']['calibrate'])
        row=ledger['stages']['geometry'];evidence=gpu_contract.evidence_path(head,row)
        record=guards.read(evidence);record['geometryDigest']=gpu_contract.geometry_id(row);write(evidence,record)
        approval_path=Path(ledger['geometryReview']['path']);approval=guards.read(approval_path)
        approval['geometryDigest']=gpu_contract.geometry_id(row);approval['evidence']=pin(evidence);write(approval_path,approval)
        ledger['geometryReview']=pin(approval_path);write(head/'gpu/gpu.json',ledger)
        def frozen(workspace,head,output):
            write(output,preparation);return preparation
        with unittest.mock.patch.object(launcher,'launch',return_value={'exitCode':0}) as launch:
            if stages=='appearance':
                with unittest.mock.patch.object(launcher,'freeze_prepared',side_effect=frozen):
                    launcher.run_gpu(Workspace.load(self.root),head.name,['--stages',stages])
            else:launcher.run_gpu(Workspace.load(self.root),head.name,['--stages',stages])
        return launch.call_args.args

    def test_calibrate_refuses_unreviewed_complete_prepare(self):
        head=self.head();self.receipt(head,'prepare',1,{'state':'complete'})
        with self.assertRaisesRegex(guards.Refused,'Prepared dependency verification failed'):
            self.launched_gpu(head,'calibrate')

    def test_calibrate_refuses_without_a_complete_prepare(self):
        head=self.head();self.receipt(head,'prepare',1,{'state':'failed'})
        with self.assertRaisesRegex(guards.Refused,'Prepared dependency verification failed'):
            self.launched_gpu(head,'calibrate')

    def test_stages_that_never_read_the_matte_do_not_declare_it(self):
        head=self.head()
        job=self.launched_gpu(head,'appearance')[3]
        self.assertNotIn('--matte',job);self.assertIn('--prepared',job)

    def test_a_partial_run_needs_its_earlier_stages(self):
        head = self.head()
        write(head/'gpu/gpu.json', {'stages': {}})
        with self.assertRaisesRegex(guards.Refused, 'must run before'):
            self.reused(['appearance'])


class Locks(Base):
    def test_lock_waits_then_takes_it(self):
        path = self.root/'locks/gpu'
        held = launcher.locked(path)
        held.__enter__()
        waits = []

        def free(_):
            waits.append(1)
            held.__exit__(None, None, None)
        with launcher.lock(lambda: [path], free):
            pass
        self.assertEqual(waits, [1])

    def test_cpu_slot_takes_the_next_free_one(self):
        with launcher.cpu_slot(self.workspace):
            with launcher.cpu_slot(self.workspace) as slot:
                self.assertEqual(slot.name, 'cpu-2')

    def test_a_slot_past_its_free_memory_gate_stays_shut(self):
        write(self.root/'cpu-slots', '5')
        names = lambda free: [path.name for path in launcher.open_slots(self.workspace, lambda: free)]
        self.assertEqual(names(9), ['cpu-1', 'cpu-2'])
        self.assertEqual(names(10), ['cpu-1', 'cpu-2', 'cpu-3'])
        self.assertEqual(names(16), ['cpu-1', 'cpu-2', 'cpu-3', 'cpu-4', 'cpu-5'])

    def test_every_slot_reads_memory_and_blocks_under_pressure(self):
        free=unittest.mock.Mock(return_value=1)
        self.assertEqual(launcher.open_slots(self.workspace,free),[])
        free.assert_called_once()

    def test_free_memory_reads_on_this_machine(self):
        self.assertGreater(launcher.free_memory_gb(), 0)

    def test_cpu_slot_released_when_the_body_raises(self):
        with self.assertRaises(RuntimeError):
            with launcher.cpu_slot(self.workspace) as slot:
                raise RuntimeError
        with launcher.lock(lambda: [slot], self.fail):
            pass

    def test_a_killed_holder_leaves_nothing_to_clear(self):
        path = self.root/'locks/gpu'
        code = 'import sys, time; sys.path.insert(0, sys.argv[1]); from headkit.comfy import locked; h = locked(sys.argv[2]); h.__enter__(); print(1, flush=True); time.sleep(60)'
        child = subprocess.Popen([sys.executable, '-B', '-c', code, str(HERE.parent), str(path)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        child.stdout.readline()
        with self.assertRaises(FileExistsError):
            with launcher.locked(path):
                pass
        child.kill()
        child.wait()
        with launcher.lock(lambda: [path], self.fail):
            pass


class Launches(Base):
    def setUp(self):
        super().setUp()
        idle=unittest.mock.patch.object(launcher.Comfy,'ensure_idle')
        idle.start();self.addCleanup(idle.stop)
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
        with unittest.mock.patch.object(launcher, 'cpu_slot') as slot, self.assertRaisesRegex(guards.Refused, 'limit 2'):
            launcher.run_stages(self.workspace, 'n', 'ownership', ['elf-male-a'])
        slot.assert_not_called()

    def test_a_busy_head_refuses_a_second_launch(self):
        self.head()
        with guards.head_lock(self.workspace, 'elf-male-a'), self.assertRaisesRegex(guards.Refused, 'RUNBOOK 190'):
            launcher.run_stages(self.workspace, 'n', 'bake', ['elf-male-a'])
        self.assertFalse(guards.head_busy(self.workspace, 'elf-male-a'))

    def designs(self, outcomes):
        data = json.loads((self.root/'workspace.json').read_text())
        data.update(designBindings='design-bindings.json', comfy={'url': 'http://127.0.0.1:1', 'root': 'comfy'})
        write(self.root/'workspace.json', data)
        workspace = Workspace.load(self.root)
        write(self.root/'design/designs-elf.json', {'designs': {}})
        with unittest.mock.patch.object(launcher, 'launch', side_effect=outcomes) as launch, unittest.mock.patch.object(launcher.Comfy, 'free') as free:
            rows = launcher.run_design(workspace, 'elf', ['elf-male-a:1', 'elf-male-b:2', 'elf-male-c:3'])
        return rows, launch, free

    def test_design_profile_controls_reference_arguments_and_input_pins(self):
        folder=self.root/'design';(folder/'launches').mkdir(parents=True)
        reference=write(self.root/'species.png','species reference')
        model=write(self.root/'model.safetensors','model weights')
        bindings=write(self.root/'design-bindings.json',{'models':{'model.safetensors':{'path':str(model)}}})
        self.workspace.data['designReferences']={'elf':{'male':str(reference)}}
        for profile in (None,'flux2-turbo-v1','qwen21-int8-v1'):
            with self.subTest(profile=profile):
                spec={'designs':{}}
                if profile is not None:spec['profile']=profile
                write(folder/'designs-elf.json',spec)
                with unittest.mock.patch.object(launcher,'launch',return_value={'exitCode':0,'elapsedSeconds':0}) as launch:
                    result=launcher.run_one_design(self.workspace,'elf',folder,bindings,'elf-male-a','1','1')
                self.assertEqual(result['exitCode'],0)
                inputs=guards.read(launch.call_args.args[2]);command=launch.call_args.args[3]
                if profile=='qwen21-int8-v1':
                    self.assertNotIn('--reference',command);self.assertNotIn(str(reference),inputs)
                    self.assertIn(str(model),inputs)
                else:
                    self.assertEqual(command[command.index('--reference')+1],reference)
                    self.assertIn(str(reference),inputs)
                    self.assertNotIn(str(model),inputs)

    def test_one_bad_design_keeps_the_rest_and_frees_the_card(self):
        good = {'exitCode': 0, 'elapsedSeconds': 1}
        rows, launch, free = self.designs([launcher.LaunchFailed('input changed'), good, good])
        self.assertEqual(launch.call_count, 3)
        self.assertEqual([row['exitCode'] for row in rows], [1, 0, 0])
        self.assertEqual(rows[0]['error'], 'input changed')
        free.assert_called_once()

    def test_a_crashed_design_still_frees_the_card(self):
        with unittest.mock.patch.object(launcher.Comfy, 'free') as free, self.assertRaises(KeyError):
            data = json.loads((self.root/'workspace.json').read_text())
            data.update(designBindings='design-bindings.json', comfy={'url': 'http://127.0.0.1:1', 'root': 'comfy'})
            write(self.root/'workspace.json', data)
            write(self.root/'design/designs-elf.json', {'designs': {}})
            with unittest.mock.patch.object(launcher, 'launch', side_effect=KeyError('x')):
                launcher.run_design(Workspace.load(self.root), 'elf', ['elf-male-a:1'])
        free.assert_called_once()

    def test_designs_stop_at_the_cap(self):
        for number in range(3):
            (self.root/f'design/launches/launch-{number}-elf-male-a-s{number}').mkdir(parents=True)
        rows, launch, _ = self.designs([{'exitCode': 0, 'elapsedSeconds': 1}]*2)
        self.assertEqual(launch.call_count, 2)
        self.assertIn('stop and ask', rows[0]['error'])
        write(self.root/'design/design-cap-override-elf-male-a', {'head': 'elf-male-a', 'maximumDesigns': 4, 'approval': 'one extra fixture design'})
        self.assertEqual(self.designs([{'exitCode': 0, 'elapsedSeconds': 1}]*3)[1].call_count, 3)

    def test_the_cap_is_counted_under_the_gpu_lock(self):
        def queued_then_another_ran(workspace):
            (self.root/'design/launches/launch-x-elf-male-a-s9').mkdir(parents=True, exist_ok=True)
            for number in range(3):
                (self.root/f'design/launches/launch-{number}-elf-male-a-s{number}').mkdir(parents=True, exist_ok=True)
            return unittest.mock.MagicMock()
        with unittest.mock.patch.object(launcher, 'gpu_lock', queued_then_another_ran):
            rows, launch, _ = self.designs([{'exitCode': 0, 'elapsedSeconds': 1}]*2)
        self.assertEqual(launch.call_count, 2)
        self.assertIn('stop and ask', rows[0]['error'])

    def test_two_labels_in_one_second_differ(self):
        self.assertGreaterEqual(len(launcher.stamp()), len('20261104-120000')+6)

    def launched_stages(self, inputs):
        self.head()
        write(self.workspace.spool/'reviewed-rows.json', {'elf-male-a': {'0': 7}})
        with unittest.mock.patch.object(launcher.subprocess, 'run', return_value=inputs), unittest.mock.patch.object(launcher, 'launch', return_value={'exitCode': 0, 'elapsedSeconds': 1}) as launch, \
                unittest.mock.patch.object(guards, 'crlf_in_pinned_code'):
            launcher.run_stages(self.workspace, 'n', 'bake', ['elf-male-a'], 'unwrap', '-a note')
        return launch.call_args.args[3]

    def test_a_replaced_attempt_is_refused_under_the_head_lock(self):
        head = self.head()
        write(head/'run/state.json', {'stages': {'bake': {'path': 'S:\\elsewhere\\run\\bake\\attempt-02\\receipt.json'}}})
        with unittest.mock.patch.object(guards, 'crlf_in_pinned_code'), unittest.mock.patch.object(launcher, 'cpu_slot') as slot, \
                unittest.mock.patch.object(guards, 'approved_attempt', wraps=guards.approved_attempt) as check, self.assertRaisesRegex(guards.Refused, 'current attempt is attempt-02'):
            def held(*arguments):
                self.assertTrue(guards.head_busy(self.workspace, head.name))
                raise guards.Refused('current attempt is attempt-02')
            check.side_effect = held
            launcher.run_stages(self.workspace, 'n', 'tone', [head.name], 'bake', 'ok', 'attempt-01')
        slot.assert_not_called()

    def test_a_note_can_start_with_a_dash(self):
        self.assertIn('--notes=-a note', self.launched_stages(unittest.mock.Mock(returncode=0)))

    def test_an_inputs_failure_keeps_its_reason(self):
        with self.assertRaisesRegex(launcher.LaunchFailed, 'Stale file pin'):
            self.launched_stages(unittest.mock.Mock(returncode=1, stderr='Traceback\nValueError: Stale file pin'))

    def test_a_blocked_stage_keeps_its_reason(self):
        row = {'stage': 'quality', 'status': 'blocked-on-dependency', 'dependency': 'unwrap', 'reason': 'Stale stage', 'next': 'Run unwrap'}
        out = write(self.root/'out.log', {'heads': [{'id': 'h', 'stages': [row]}]})
        self.assertEqual(launcher.results(out)[0]['stages'], [row])

    def test_design_reports_a_failed_launch(self):
        row = {'head': 'h', 'seed': '1', 'elapsedSeconds': 1, 'exitCode': 3}
        with unittest.mock.patch.object(launcher, 'run_design', return_value=[row]):
            self.assertEqual(run_headbatch.main(['--workspace', str(self.root), 'design', 'elf', 'h:1']), 3)

    def test_run_command_reports_a_refusal_as_a_result(self):
        self.head()
        for number in (1, 2):
            self.receipt(self.workspace.head('elf-male-a'), 'ownership', number, {})
        result = self.root/'result.json'
        with self.assertRaisesRegex(SystemExit, 'REFUSED'):
            run_headbatch.main(['--workspace', str(self.root), 'run', 'n', 'ownership', 'elf-male-a', '--result', str(result)])
        self.assertIn('limit 2', json.loads(result.read_text())['refused'])


class Setup(Base):
    def test_feature_remapped_bones_keep_auto_row_and_bone_tone(self):
        for ownership in ({'default':0,'rules':[{'channel':8}]},{'default':8,'rules':[]}):
            for sex in ('male','female'):
                with self.subTest(ownership=ownership,sex=sex):
                    data={'ownership':dict(ownership,mode='rules',featureChannels=True),
                          'palette':{'rows':{'0':'auto','1':'auto','8':'auto','9':'auto'}}}
                    head_setup.tone_every_channel(data,'troll',sex,'fixture')
                    self.assertEqual(data['palette']['rows']['9'],'auto')
                    self.assertEqual(data['palette']['toneMatch']['9'],{'reference':'head-metal-v1'})

    def test_remapped_bone_defaults_preserve_reviewed_overrides_and_opt_out(self):
        for opt_out in (False,True):
            data={'ownership':{'mode':'rules','default':0,'rules':[{'channel':8}],'featureChannels':True},
                  'palette':{'rows':{'9':'auto' if opt_out else 7},
                             'toneMatch':{'9':{'reference':'head-tattoo2-v1'}}}}
            if opt_out:data['palette']['toneMatchOff']=['9']
            head_setup.tone_every_channel(data,'troll','male','fixture')
            self.assertEqual(data['palette']['rows']['9'],'auto' if opt_out else 7)
            if opt_out:self.assertNotIn('9',data['palette']['toneMatch'])
            else:self.assertEqual(data['palette']['toneMatch']['9'],{'reference':'head-tattoo2-v1'})

    def test_feature_channels_without_legacy_bones_keep_tattoo2_unused(self):
        data={'ownership':{'mode':'rules','default':0,'rules':[{'channel':1}],'featureChannels':True},
              'palette':{'rows':{'8':'auto','9':'auto'}}}
        head_setup.tone_every_channel(data,'troll','male','fixture')
        self.assertEqual(data['palette']['rows'],{'8':'auto','9':0})
        self.assertNotIn('9',data['palette']['toneMatch'])

    def test_bone_channels_use_accessory_tones_and_preserve_reviewed_overrides(self):
        for race in ('troll', 'orc', 'elf', 'human', 'dwarf'):
            for sex in ('male', 'female'):
                with self.subTest(race=race, sex=sex):
                    data = {'ownership': {'default': 0, 'rules': [{'channel': 9}]},
                            'palette': {'toneMatch': {}}}
                    head_setup.tone_every_channel(data, race, sex, 'fixture')
                    expected = 'head-metal-v1' if race in ('troll', 'orc') else 'head-tattoo1-v1'
                    self.assertEqual(data['palette']['toneMatch']['9']['reference'], expected)
                    self.assertEqual(data['palette']['toneMatch']['0']['reference'], f'{race}-{sex}-skin-v1')
        data = {'ownership': {'default': 0, 'rules': [{'channel': 9}]},
                'palette': {'toneMatch': {'9': {'reference': 'head-tattoo2-v1'}}}}
        head_setup.tone_every_channel(data, 'troll', 'male', 'fixture')
        self.assertEqual(data['palette']['toneMatch']['9']['reference'], 'head-tattoo2-v1')

    def test_generated_design_keeps_its_frozen_prompt_and_requires_unchanged_pins(self):
        self.prepare()
        name = 'elf-male-a'
        image = write(self.root/'design/raw'/f'{name}-s42-b0.png', 'selected bytes')
        spec = write(self.root/'design/launches/spec-original.json', {'designs': {name: 'Hair: long silver locks.'}})
        receipt = write(image.with_name(f'{name}-s42.json'), {
            'kind': 'design', 'state': 'complete', 'head': name,
            'spec': {'path': str(spec), 'sha256': head_setup.sha(spec)},
            'outputs': [{'path': str(image), 'sha256': head_setup.sha(image)}]})
        self.assertEqual(head_setup.selected_prompt(self.workspace, name, 'elf', image)[0], 'Hair: long silver locks.')
        head_setup.set_up(self.workspace, name, image, approval='fixture selection', check=lambda *_: None)
        record = guards.read(self.workspace.head(name)/'design/design-receipt.json')
        self.assertEqual(record['featureInventory']['hair'], 'long silver locks.')
        self.assertEqual(record['proposalReceipt']['sha256'], head_setup.sha(receipt))
        write(spec, {'designs': {name: 'Hair: cropped.'}})
        with self.assertRaisesRegex(guards.Refused, 'frozen proposal spec changed'):
            head_setup.selected_prompt(self.workspace, name, 'elf', image)
        write(image, 'different bytes')
        with self.assertRaisesRegex(guards.Refused, 'image differs'):
            head_setup.selected_prompt(self.workspace, name, 'elf', image)

    def prepare(self):
        for file in ('pal-skin01.tga', 'pal-hair01.tga', 'pal-armor01.tga', 'pal-armor02.tga', 'pal-tattoo01.tga'):
            write(self.root/'palettes'/file, file)
        write(self.root/'compiler.json', {})
        write(self.root/'necks/pme0-neck001-ref.json', {})
        write(self.root/'fit/pme0_head001.mdl', 'model')
        write(self.root/'design/designs-elf.json', {'designs': {'elf-male-a': 'Hair: long\nEars: pointed\nOther: ignored'}})
        image = write(self.root/'design/raw/elf-male-a-s1-b0.png', 'image')
        spec = write(self.root/'design/launches/spec-fixture.json', guards.read(self.root/'design/designs-elf.json'))
        write(image.with_name('elf-male-a-s1.json'), {'kind':'design','state':'complete','head':'elf-male-a',
              'spec':{'path':str(spec),'sha256':head_setup.sha(spec)},
              'outputs':[{'path':str(image),'sha256':head_setup.sha(image)}]})
        return image

    def test_face_profile_setup_replaces_diagnostics_and_survives_rewrite(self):
        from headkit.cameras import review_cameras
        from headkit.review_images import render_plan, resolutions

        design = self.prepare()
        body = write(self.root/'body-skin.plt', 'body fixture')
        self.workspace.data['headQualityProfile'] = 'face-v1'
        self.workspace.data['bodySkinReferences'] = {'elf-male': body.name}
        path = head_setup.set_up(self.workspace, 'elf-male-a', design, approval='fixture selection', check=lambda *_: None)
        data = guards.read(path)
        config = data['render']
        self.assertTrue(config['runtimePalette'])
        self.assertEqual(resolutions(config), [2048, 1024])
        for key in ('$replace', 'diagnostic', 'size', 'ownershipView', 'views'):
            self.assertNotIn(key, config)
        self.assertEqual(data['mesh']['uv']['faceDensity'], 3)
        self.assertIn('cut', data['mesh']['neck'])
        self.assertNotIn('taper', data['mesh']['neck'])
        self.assertEqual(data['inputs']['bodySkin']['sha256'], head_setup.sha(body))
        overrides = guards.read(path.parent/'overrides.json')
        self.assertTrue(overrides['render']['$replace'])
        self.assertTrue(overrides['mesh']['neck']['$replace'])
        head_setup.write_manifest(self.workspace, 'elf-male-a', check=lambda *_: None)
        self.assertEqual(guards.read(path), data)

        config = dict(config, cameras=review_cameras([[0, 0, 0], [1, 1, 1]], config['frontAngleDegrees']))
        plan = render_plan(config)
        self.assertEqual(len(plan), 84)
        self.assertTrue({'left-three-quarter', 'right-three-quarter', 'left-back-three-quarter',
                         'right-back-three-quarter'} <= {view for _, _, view in plan})

    def test_set_up_writes_a_complete_head(self):
        design = self.prepare()
        path = head_setup.set_up(self.workspace, 'elf-male-a', design, approval='picked by test', check=lambda *_: None)
        data = json.loads(path.read_text())
        self.assertEqual(data['fit']['model'], 'pme0_head020')
        self.assertTrue(data['render']['diagnostic'])
        self.assertEqual(data['render']['size'], 1024)
        self.assertNotIn('sizes', data['render'])
        self.assertEqual({row['name'] for row in data['features']}, {'hair', 'ears', 'neck'})
        self.assertEqual(data['mesh']['neck']['cut']['slope'], -.2)
        self.assertNotIn('taper', data['mesh']['neck'])
        self.assertEqual(data['palette']['toneMatch']['0']['reference'], 'elf-male-skin-v1')
        self.assertFalse((path.parent/'manifest.check.json').exists())
        with self.assertRaisesRegex(guards.Refused, 'not empty'):
            head_setup.set_up(self.workspace, 'elf-male-a', design, check=lambda *_: None)
        with self.assertRaisesRegex(guards.Refused, 'not in workspace slots'):
            head_setup.set_up(self.workspace, 'elf-male-z', design)

    def test_a_blank_approval_is_refused(self):
        with self.assertRaisesRegex(guards.Refused, '--approval'):
            head_setup.set_up(self.workspace, 'elf-male-a', self.root/'d.png', approval='  ')

    def test_a_failed_setup_can_run_again(self):
        design = self.prepare()
        data = json.loads((self.root/'workspace.json').read_text())
        compiler = data.pop('mdlCompiler')
        write(self.root/'workspace.json', data)
        with self.assertRaises(WorkspaceError):
            head_setup.set_up(Workspace.load(self.root), 'elf-male-a', design, approval='t', check=lambda *_: None)
        data['mdlCompiler'] = compiler
        write(self.root/'workspace.json', data)
        path = head_setup.set_up(Workspace.load(self.root), 'elf-male-a', design, approval='t', check=lambda *_: None)
        self.assertFalse((path.parent/head_setup.SETUP_MARKER).exists())

    def test_no_neck_cut_preserves_body_reference_and_survives_presets(self):
        design = self.prepare()
        head = self.workspace.head('elf-male-a')
        head_setup.set_up(self.workspace, head.name, design, approval='test', no_neck_cut=True, check=lambda *_: None)
        manifest = guards.read(head/'manifest.json')
        self.assertNotIn('neck', manifest['mesh'])
        self.assertIn('bodyNeck', manifest['inputs'])
        planned, _, hold, _ = presets.plan(self.workspace, head.name)
        self.assertIsNone(planned['mesh']['neck'])
        self.assertFalse(hold)

    def test_components_count_the_extra_shells_not_the_table(self):
        design = self.prepare()
        head_setup.set_up(self.workspace, 'elf-male-a', design, approval='t', check=lambda *_: None)
        head = self.workspace.head('elf-male-a')
        write(head/'review-evidence/shells.json', {'count': 8, 'extra': [{}]*7, 'deletedAreaFraction': .001})
        self.assertEqual(head_setup.set_components(self.workspace, 'elf-male-a', 'studs', lambda *_: None), (7, .0011))
        components = guards.read(head/'manifest.json')['mesh']['components']
        self.assertEqual(components['expectedDeleted'], 7)
        self.assertNotIn('interiorOnly', components)
        write(head/'review-evidence/shells.json', {'count': 2, 'extra': [{'insideFraction': 1.0}], 'deletedAreaFraction': .00008})
        head_setup.set_components(self.workspace, head.name, 'inside', lambda *_: None)
        self.assertTrue(guards.read(head/'manifest.json')['mesh']['components']['interiorOnly'])
        write(head/'review-evidence/shells.json', {'count': 1, 'extra': [], 'deletedAreaFraction': 0})
        self.assertEqual(head_setup.set_components(self.workspace, head.name, 'one shell', lambda *_: None), (0, .0001))
        write(head/'review-evidence/shells.json', {'count': 7, 'extra': [{}]*7, 'deletedAreaFraction': .001})
        with self.assertRaisesRegex(guards.Refused, 'counts 7'):
            head_setup.set_components(self.workspace, 'elf-male-a', 'studs', lambda *_: None)

    def test_ownership_replaces_the_rule_set(self):
        design = self.prepare()
        head_setup.set_up(self.workspace, 'elf-male-a', design, approval='t', check=lambda *_: None)
        settings = self.workspace.head('elf-male-a')/'overrides.json'
        overrides = guards.read(settings)
        overrides['ownership'] = {'featureChannels':True, 'boneEarGuard':True, 'hairMaskRequiresRule':True}
        write(settings, overrides)
        rules = write(self.root/'rules.json', {'regions': {'hair': {}}, 'rules': [{'channel': 1}], 'notes': 'n'})
        path = head_setup.set_ownership(self.workspace, 'elf-male-a', rules, lambda *_: None)
        data = guards.read(path)['ownership']
        self.assertEqual((data['mode'], data['rules']), ('rules', [{'channel': 1}]))
        self.assertTrue(data['featureChannels'] and data['boneEarGuard'] and data['hairMaskRequiresRule'])
        self.assertNotIn('$replace', data)

    def test_route_declarations_name_their_gate(self):
        declared = head_setup.route_declarations({'raw': {'sha256': 'a'}, 'field': {'sha256': 'b'}})
        self.assertIn('repair gate', declared['shellInspection']['notes'])
        self.assertIn('bake gate', declared['appearanceField']['notes'])

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

    def test_a_presets_edit_the_manifest_refuses_changes_nothing(self):
        head = self.head()
        write(head/'overrides.json', {'mesh': {}})
        with unittest.mock.patch.object(head_setup, 'write_manifest', side_effect=guards.Refused('bad')), unittest.mock.patch.object(presets, 'plan', return_value=({'mesh': {'x': 1}}, [], [], True)):
            with self.assertRaises(guards.Refused):
                presets.apply(self.workspace, head.name)
        self.assertEqual(json.loads((head/'overrides.json').read_text()), {'mesh': {}})

    def test_manifest_refused_under_a_queued_launch(self):
        with guards.head_lock(self.workspace, 'elf-male-a'), self.assertRaisesRegex(guards.Refused, 'queued or running'):
            head_setup.write_manifest(self.workspace, 'elf-male-a')

    def test_a_refused_manifest_puts_a_replaced_input_back(self):
        head = self.workspace.head('elf-male-a')
        old = write(head/'inputs/raw.glb', 'old')
        replaced = []
        head_setup.link(head, write(self.root/'new.glb', 'new'), 'raw.glb', replaced)
        self.assertEqual(replaced, [(head/'inputs/raw.glb.replaced', head/'inputs/raw.glb')])

        def rewrite(*arguments):
            head_setup.link(head, write(self.root/'new.glb', 'new'), 'raw.glb', arguments[-1])
            raise guards.Refused('no')
        (head/'inputs/raw.glb').unlink()
        (head/'inputs/raw.glb.replaced').rename(old)
        with unittest.mock.patch.object(head_setup, 'rewrite_manifest', rewrite), self.assertRaises(guards.Refused):
            head_setup.write_manifest(self.workspace, 'elf-male-a')
        self.assertIn('old', old.read_text())
        self.assertFalse((head/'inputs/raw.glb.replaced').exists())

    def test_a_manifest_rewrite_holds_the_head(self):
        def rewrite(*arguments):
            self.assertTrue(guards.head_busy(self.workspace, 'elf-male-a'))
        with unittest.mock.patch.object(head_setup, 'rewrite_manifest', rewrite):
            head_setup.write_manifest(self.workspace, 'elf-male-a')

    def test_unused_channels_get_a_row_and_used_ones_stay_auto(self):
        data = {'ownership': {'mode': 'rules', 'default': 0, 'rules': [{'channel': 2}]}, 'palette': {'rows': {'0': 'auto', '1': 'auto', '2': 'auto', '8': 'auto', '9': 5}, 'toneMatch': {}}}
        head_setup.tone_every_channel(data, 'elf', 'male', 'h')
        self.assertEqual(data['palette']['rows'], {'0': 'auto', '1': 0, '2': 'auto', '8': 0, '9': 5})

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
        (head/'run/native/attempt-02/native').mkdir(parents=True)
        self.receipt(head, 'native', 1, {'state': 'complete', 'dependencies': {'export': {'path': 'S:\\elsewhere\\run\\export\\attempt-01\\receipt.json'}}})
        self.receipt(head, 'native', 2, {'state': 'failed'})
        self.receipt(head, 'export', 1, {'state': 'complete', 'dependencies': {'palette': {'path': 'S:\\elsewhere\\run\\palette\\attempt-01\\receipt.json'}}})
        self.receipt(head, 'palette', 1, {'state': 'complete', 'result': {'rows': {'0': 3, '1': 5, '9': 33}}})
        self.receipt(head, 'palette', 2, {'state': 'complete', 'result': {'rows': {'0': 40, '1': 41}}})  # rerun after the native: not in its HAK
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

    def test_a_native_with_no_palette_lineage_is_refused(self):
        head = self.workspace.head('elf-male-a')
        (head/'run/native/attempt-01/native').mkdir(parents=True)
        self.receipt(head, 'native', 1, {'state': 'complete', 'dependencies': {'export': {'path': 'run/export/attempt-01/receipt.json'}}})
        self.receipt(head, 'export', 1, {'state': 'complete', 'dependencies': {}})
        with self.assertRaisesRegex(guards.Refused, 'rows are unknown'):
            trials.head_entry(self.workspace, 'elf-male-a', 'pme0_head020')

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
        overrides, notes, hold, changed = presets.plan(self.workspace, head.name, uv_only=True, floor_review='charts checked')
        self.assertTrue(changed)
        self.assertEqual(overrides['mesh']['uv']['minimumCoverage'], .29)
        self.assertIn('charts checked', overrides['mesh']['uv']['coverageReview']['notes'])
        self.assertEqual(hold, [])
        self.assertIn('uv floor', notes[0])

    def test_a_round_coverage_keeps_its_floor(self):
        head = self.head()
        self.overrides(head, {})
        self.receipt(head, 'unwrap', 1, {'error': 'Insufficient useful UV coverage (0.291 at 2K)'})
        self.assertEqual(presets.plan(self.workspace, head.name, uv_only=True, floor_review='checked')[0]['mesh']['uv']['minimumCoverage'], .28)

    def test_no_review_notes_report_the_floor_and_record_nothing(self):
        head = self.head()
        self.overrides(head, {})
        self.receipt(head, 'unwrap', 1, {'result': RECEIPT_RESULT})
        overrides, notes, _, changed = presets.plan(self.workspace, head.name, uv_only=True)
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

    def test_fine_relief_defaults_to_the_approved_profile_off_human_heads(self):
        head = self.head()
        self.overrides(head, {})
        self.assertEqual(presets.plan(self.workspace, head.name)[0]['mesh']['fineRelief'], presets.FINE_RELIEF['fineRelief'])
        self.assertNotIn('fineRelief', presets.plan(self.workspace, head.name, uv_only=True)[0]['mesh'])
        data = json.loads((self.root/'workspace.json').read_text())
        data['slots']['human-male'] = [1]
        write(self.root/'workspace.json', data)
        human = self.head('human-male-a')
        self.overrides(human, {})
        self.assertNotIn('fineRelief', presets.plan(Workspace.load(self.root), human.name)[0]['mesh'])

    def test_fine_relief_comes_from_the_workspace(self):
        head = self.head()
        self.overrides(head, {})
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
        self.assertIn('RUNBOOK 47', presets.plan(workspace, head.name, scan=self.scan(results))[2][0])

    def test_report_only_plans_change_nothing(self):
        head = self.head()
        workspace = self.marks(head)
        self.overrides(head, {'slope': -.2, 'reach': .08})
        overrides = json.loads((head/'overrides.json').read_text())
        overrides['mesh']['fineRelief'] = {}
        write(head/'overrides.json', overrides)
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

    def views_of(self, *arguments):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'state': 'complete'})
        self.receipt(head, 'unwrap', 2, {'state': 'complete'})  # a rerun the bake never used
        self.receipt(head, 'bake', 1, {'state': 'complete', 'dependencies': {'unwrap': {'path': 'S:\\elsewhere\\run\\unwrap\\attempt-01\\receipt.json'}}})
        self.receipt(head, 'bake', 2, {'state': 'failed', 'dependencies': {'unwrap': {'path': 'run/unwrap/attempt-02/receipt.json'}}})
        with unittest.mock.patch.object(sys, 'argv', ['bakeviews.py', str(head), *arguments]), unittest.mock.patch.object(sys, 'path', [str(HERE.parent), *sys.path]), \
                unittest.mock.patch.object(subprocess, 'Popen') as popen, self.assertRaises(SystemExit):
            popen.return_value.wait.return_value = 0
            runpy.run_path(str(HERE/'review/bakeviews.py'), run_name='__main__')
        return ' '.join(str(item) for item in popen.call_args.args[0])

    def test_bakeviews_shows_a_bake_on_the_mesh_it_was_baked_on(self):
        job = self.views_of().replace('\\', '/')
        self.assertIn('run/unwrap/attempt-01/uv.glb', job)
        self.assertIn('run/bake/attempt-01/maps/basecolor-2048.png', job)
        self.assertIn('review-evidence/bake-grid-attempt-01.png', job)

    def test_bakeviews_takes_the_named_attempt(self):
        self.assertIn('run/bake/attempt-02/maps', self.views_of('attempt-02').replace('\\', '/'))

    def test_unknown_tool_is_refused(self):
        with self.assertRaises(SystemExit):
            run_headbatch.parser().parse_args(['review', 'no-such-tool'])

    def test_status_lists_a_head_that_has_never_launched(self):
        self.head()
        self.assertEqual(launcher.status(self.workspace), ['elf-male-a | no stage yet'])

    def test_rejected_geometry_sheet_and_status_name_the_failed_submission(self):
        import gpu_contract
        head = self.head()
        row = {'submission': 2, 'occiput': {'open': True}}
        ledger = {'geometrySubmissions': 2, 'stages': {}, 'rejectedGeometry': [row]}
        write(head/'gpu/gpu.json', ledger)
        self.assertEqual(gpu_contract.evidence_geometry(ledger, 'geometry-0002'), row)
        with self.assertRaisesRegex(ValueError, 'rejected'):
            gpu_contract.evidence_geometry(ledger, 'geometry-0001')
        self.assertIn('geometry-0002 | REJECTED', launcher.status(self.workspace)[0])

    def test_status_names_a_head_waiting_on_review(self):
        head = self.head()
        self.receipt(head, 'bake', 1, {'result': {}})
        self.assertEqual(launcher.status(self.workspace), ['elf-male-a | bake attempt-01 ran | WAITING ON REVIEW'])
        with guards.head_lock(self.workspace, 'elf-male-a'):
            self.assertIn('launch queued or running', launcher.status(self.workspace)[0])
        self.receipt(head, 'render', 1, {'result': {}})
        os.utime(head/'run/render/attempt-01/receipt.json', (2**31, 2**31))
        self.assertIn('WAITING ON REVIEW', launcher.status(self.workspace)[0])
        row = {'path': 'S:\\elsewhere\\run\\render\\attempt-01\\receipt.json', 'sha256': 'a'}
        review = {'path': 'S:\\elsewhere\\run\\reviews\\render-1.json'}
        write(head/'run/reviews/render-1.json', {'stageReceipt': row, 'decision': 'approved'})
        write(head/'run/state.json', {'stages': {'render': row}, 'reviews': {'render': review}})
        self.assertIn('DELIVERY RENDER REQUIRED', launcher.status(self.workspace)[0])
        write(head/'run/reviews/render-1.json', {'stageReceipt': row, 'decision': 'rejected'})
        self.assertIn('WAITING ON REVIEW', launcher.status(self.workspace)[0])
        write(head/'run/reviews/render-1.json', {'stageReceipt': dict(row, sha256='older'), 'decision': 'approved'})  # a rerender after approval
        self.assertIn('WAITING ON REVIEW', launcher.status(self.workspace)[0])


class SpoolTests(Base):
    def setUp(self):
        super().setUp()
        self.started = []
        self.attempts = []
        self.tools = []
        self.queued = []
        self.tool_result = (0, ['done'])
        self.spool = self.make(self.workspace)

    def make(self, workspace):
        return spool.Spool(workspace, self.start, self.tool, lambda *args: self.queued.append(args))

    def tool(self, *arguments):
        self.tools.append(arguments)
        return self.tool_result

    def start(self, name, stages, head, approve, notes, attempt=None):
        self.started.append((stages, head, approve))
        self.attempts.append(attempt)

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

    def test_a_second_spooler_is_refused(self):
        with guards.only_spooler(self.workspace), self.assertRaisesRegex(guards.Refused, 'Another spooler'):
            self.spool.loop(once=True)
        self.spool.loop(once=True)

    def test_a_held_report_does_not_end_the_loop(self):
        with unittest.mock.patch.object(self.spool, 'report', side_effect=PermissionError('held')):
            self.spool.step()
        self.assertIn('spool/report', self.spool.state['attention'])

    def test_a_closed_console_does_not_end_the_loop(self):
        with unittest.mock.patch('builtins.print', side_effect=OSError(22, 'Invalid argument')):
            self.spool.log('line')
        self.assertIn('line', (self.workspace.spool/'log.txt').read_text())

    def test_a_request_that_cannot_retire_fires_once(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'bake'})
        with unittest.mock.patch.object(Path, 'rename', side_effect=PermissionError('held')):
            self.spool.scan_requests()
            self.spool.scan_requests()
        self.assertEqual(self.started, [('bake', 'elf-male-a', None)])
        self.spool.scan_requests()
        self.assertEqual(list((self.workspace.spool/'queue').glob('*')), [])
        self.assertEqual(self.spool.state['taken'], {})

    def test_a_queue_file_edited_between_heads_launches_only_the_rest(self):
        self.head()
        self.head('elf-male-b')
        path = write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a', 'elf-male-b'], 'stages': 'repair'})

        def edit_at_the_second_head(*arguments):
            if arguments[1] == 'elf-male-b' and not self.tools:
                self.tools.append(arguments)
                path.write_text(path.read_text()+' ')
            return (0, ['done'])
        self.spool.tool = edit_at_the_second_head
        self.spool.scan_requests()
        self.assertEqual(self.started, [('repair', 'elf-male-a', None)])
        self.spool.scan_requests()
        self.assertEqual(self.started, [('repair', 'elf-male-a', None), ('repair', 'elf-male-b', None)])

    def test_a_stage_that_later_runs_closes_its_attention(self):
        head = self.head()
        self.spool.attention(head.name, 'tone', 'failed attempt-01')
        self.receipt(head, 'tone', 2, {'result': {}})
        self.finish(stage='tone')
        self.assertNotIn('elf-male-a/tone', self.spool.state['attention'])

    def test_a_blocked_stage_says_why(self):
        name = self.spool.launch('quality', 'elf-male-a')
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': 'elf-male-a', 'stages': [{'stage': 'quality', 'status': 'blocked-on-dependency', 'reason': 'Stale stage: unwrap'}]}]})
        self.spool.step()
        self.assertIn('Stale stage: unwrap', self.spool.state['attention']['elf-male-a/quality']['text'])

    def test_a_launcher_error_keeps_its_end(self):
        name = self.spool.launch('bake', 'elf-male-a')
        write(self.workspace.spool/'results'/f'{name}.json', {'error': 'x'*900+'ValueError: Stale file pin'})
        self.spool.step()
        self.assertIn('Stale file pin', self.spool.state['attention'][f'{name}/launch']['text'])

    def test_a_failed_row_sheet_reaches_attention_on_an_advance(self):
        head = self.head()
        write(self.workspace.spool/'reviewed-rows.json', {head.name: {'0': 7}})
        self.receipt(head, 'palette', 1, {'result': {'rows': {'0': 7}}})
        self.tool_result = (1, ['no attempt'])
        self.finish(stage='palette')
        self.assertEqual(self.started, [])
        self.assertIn('ROWRAMPS FAILED', self.spool.state['attention']['elf-male-a/palette']['text'])

    def test_a_repair_approved_as_next_gets_its_presets(self):
        head = self.head()
        self.current(head, 'fit', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'fit', 'attempts': {head.name: 'attempt-01'}, 'next': 'repair'})
        self.tool_result = (1, ['HOLD: no reach finds the chin'])
        self.spool.scan_requests()
        self.assertEqual(self.tools, [('presets', 'elf-male-a', '--apply')])
        self.assertEqual(self.started, [])

    def test_two_sheets_in_one_tick_keep_their_logs(self):
        with unittest.mock.patch.object(spool.subprocess, 'Popen') as popen:
            popen.side_effect = [unittest.mock.Mock(), unittest.mock.Mock()]
            self.spool.run_later('bakeviews', 'a')
            self.spool.run_later('bakeviews', 'b')
        self.assertEqual(len(self.spool.drawing), 2)

    def test_queue_launches_each_head(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'bake'})
        write(self.workspace.spool/'queue/b.json', {'heads': ['elf-male-b'], 'stages': 'tone'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [('bake', 'elf-male-a', None), ('tone', 'elf-male-b', None)])
        self.assertEqual(list((self.workspace.spool/'queue').glob('*')), [])
        self.assertEqual(len(list((self.workspace.spool/'done').glob('*'))), 2)

    def test_a_refused_launch_reaches_attention_with_its_reason(self):
        name = self.spool.launch('export', 'elf-male-a')
        write(self.workspace.spool/'results'/f'{name}.json', {'refused': 'elf-male-a: palette rows are not in reviewed-rows.json (RUNBOOK 112)'})
        self.spool.step()
        self.assertIn('RUNBOOK 112', self.spool.state['attention'][f'{name}/launch']['text'])

    def current(self, head, stage, attempt):
        write(head/'run/state.json', {'stages': {stage: {'path': f'S:\\elsewhere\\run\\{stage}\\{attempt}\\receipt.json'}}})

    def test_an_approval_of_an_attempt_no_longer_current_is_refused(self):
        head = self.head()
        self.current(head, 'repair', 'attempt-02')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'repair', 'attempts': {head.name: 'attempt-01'}, 'next': 'unwrap'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertIn('current attempt is attempt-02', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_an_approval_sends_its_attempt_to_the_launch(self):
        head = self.head()
        self.current(head, 'bake', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'bake', 'attempts': {head.name: 'attempt-01'}, 'next': 'tone'})
        self.spool.scan_requests()
        self.assertEqual(self.attempts, ['attempt-01'])

    def test_a_passed_gate_sends_the_attempt_it_judged(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'attempts': [{'badFaceCount': 0, 'subtexel': {}}], 'gutters': {}, 'geometryUnchanged': True, 'charts': 9}})
        self.finish()
        self.assertEqual(self.attempts[-1], 'attempt-01')

    def test_an_approval_must_name_what_was_reviewed(self):
        head = self.head()
        self.current(head, 'repair', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'repair', 'next': 'unwrap'})
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertIn('name the attempt', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_an_approval_with_no_next_launch_says_so(self):
        head = self.head()
        self.current(head, 'render', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'render', 'attempts': {head.name: 'attempt-01'}})
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertIn('give "next"', self.spool.state['attention']['elf-male-a/render']['text'])

    def test_approval_of_repair_runs_the_jaw_guard(self):
        head = self.head()
        data = json.loads((self.root/'workspace.json').read_text())
        data['landmarks'] = 'marks.json'
        write(self.root/'workspace.json', data)
        write(self.root/'marks.json', {head.name: {'source': {'eyeLeft': [0, 0, .1], 'eyeRight': [0, 0, .1], 'lips': [0, 0, .06]}}})
        write(head/'run/repair/attempt-01/reduction-audit.json', {'neck': {'cut': {'jawLine': {'point': [0, 0, .05]}}}})
        self.spool = self.make(Workspace.load(self.root))
        self.current(head, 'repair', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': [head.name], 'approve': 'repair', 'attempts': {head.name: 'attempt-01'}, 'next': 'unwrap', 'notes': 'ok'})
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
        self.assertEqual(self.queued, [('bakeviews', 'elf-male-a', 'attempt-01')])
        self.receipt(head, 'ownership', 1, {'result': {}})
        self.finish(stage='ownership')
        self.assertEqual(self.queued[-1][:3], ('ownsheet', 'elf-male-a', 'attempt-01'))

    def test_fit_compares_named_attempt_to_bound_reference_before_repair(self):
        head = self.head()
        self.receipt(head, 'fit', 1, {'result': {}})
        self.finish(stage='fit')
        self.assertEqual(self.queued[-1], ('fitcheck', '--reference', head.name, 'attempt-01',
                         self.workspace.spool/'sheets'/f'{head.name}-fit-attempt-01-reference.png'))
        self.assertFalse(self.started)

    def test_repair_without_a_cut_compares_master_to_final(self):
        head=self.head()
        self.receipt(head, 'repair', 1, {'result': {}})
        self.finish(stage='repair')
        self.assertTrue(any('before reduction=' in str(arg) and 'master.glb' in str(arg) for arg in self.queued[-1]))
        self.assertFalse(any('master-uncut' in str(arg) for arg in self.queued[-1]))

    def test_staged_repair_compares_saved_normals_for_the_named_attempt(self):
        head = self.head()
        self.receipt(head, 'repair', 2, {'dependencies': {'fit': {'path': 'pinned'}}, 'result': {}})
        self.finish(stage='repair')
        sheet = self.workspace.spool/'sheets'/f'{head.name}-repair-attempt-02-normals.png'
        self.assertEqual(self.queued, [('repairclay', head.name, 'attempt-02', sheet)])
        self.assertFalse(self.started)

    def test_direct_fit_approval_retires_only_its_own_verified_notice(self):
        from head_files import sha
        head = self.head()
        receipt = write(head/'run/fit/attempt-01/receipt.json', {'state': 'complete'})
        bound = {'path': str(receipt), 'sha256': sha(receipt)}
        review = write(head/'run/reviews/fit-selected.json', {'stageReceipt': bound, 'decision': 'approved'})
        write(head/'run/state.json', {'stages': {'fit': bound},
              'reviews': {'fit': {'path': str(review), 'sha256': sha(review)}}})
        self.spool.review(head.name, 'fit', 'attempt-02: ran')
        self.spool.reconcile_direct_reviews()
        self.assertIn(head.name+'/fit', self.spool.state['review'])
        self.spool.review(head.name, 'fit', 'attempt-01: ran')
        self.spool.review(head.name, 'palette', 'attempt-01: review rows')
        self.spool.reconcile_direct_reviews()
        self.assertNotIn(head.name+'/fit', self.spool.state['review'])
        self.assertIn(head.name+'/palette', self.spool.state['review'])
        review.write_bytes(review.read_bytes()+b' ')
        self.spool.review(head.name, 'fit', 'attempt-01: ran')
        self.spool.reconcile_direct_reviews()
        self.assertIn(head.name+'/fit', self.spool.state['review'])
        self.assertEqual(self.started, [])

    def test_precluster_queues_the_sheet_for_the_completed_attempt(self):
        head = self.head()
        self.receipt(head, 'precluster', 1, {'result': {}})
        self.finish(stage='precluster')
        self.assertEqual(self.queued[-1], ('gpuclay', head.name, '--precluster', 'attempt-01',
                         self.workspace.spool/'sheets'/f'{head.name}-precluster-attempt-01.png'))
        self.assertFalse(self.started)

    def test_palette_draws_the_row_ramps(self):
        head = self.head()
        self.receipt(head, 'palette', 1, {'result': {'rows': {'0': 7}}})
        self.finish(stage='palette')
        self.assertEqual(self.tools, [('review', 'rowramps', 'elf-male-a', 'attempt-01')])
        self.tool_result = (1, ['no such attempt'])
        self.finish(stage='palette')
        self.assertIn('ROWRAMPS FAILED: no such attempt', self.spool.state['review']['elf-male-a/palette']['text'])

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
        self.receipt(head, 'repair', 1, {'error': 'Neck cut failed (slope -0.2: Master has 3 separate shells; review them and declare mesh.components). Cut variants that pass: none'})
        write(head/'run/repair/attempt-01/master-uncut.glb')
        self.finish('failed', 'repair')
        self.assertEqual(self.queued[0][:2], ('cutshells', 'elf-male-a'))
        self.assertIn('cutshells queued', self.spool.state['attention']['elf-male-a/repair']['text'])

    def test_a_shell_refusal_before_the_cut_has_no_sheet_to_queue(self):
        head = self.head()
        self.receipt(head, 'repair', 1, {'error': 'Master has 3 separate shells; review them and declare mesh.components'})
        self.finish('failed', 'repair')
        self.assertEqual(self.queued, [])
        self.assertIn('3 separate shells', self.spool.state['attention']['elf-male-a/repair']['text'])

    def approved(self, row):
        self.current(self.workspace.head('elf-male-a'), 'bake', 'attempt-01')
        write(self.workspace.spool/'approve/a.json', {'heads': ['elf-male-a'], 'approve': 'bake', 'attempts': {'elf-male-a': 'attempt-01'}, 'next': 'paint'})
        self.spool.scan_requests()
        name = next(iter(self.spool.state['launches']))
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': 'elf-male-a', **row}]})
        self.spool.step()

    def test_a_refused_approval_stays_open_with_its_reason(self):
        self.head()
        self.spool.review('elf-male-a', 'bake', 'waiting')
        self.approved({'error': 'Approval not recorded: notes required', 'stages': []})
        self.assertIn('elf-male-a/bake', self.spool.state['review'])
        self.assertIn('Approval not recorded', self.spool.state['attention']['elf-male-a/bake']['text'])

    def test_a_recorded_approval_closes_its_review(self):
        self.head()
        self.spool.review('elf-male-a', 'bake', 'waiting')
        self.spool.attention('elf-male-a', 'bake', 'waiting')
        self.approved({'stages': [{'stage': 'paint', 'status': 'skipped'}, {'stage': 'tone', 'status': 'ran'}]})
        self.assertNotIn('elf-male-a/bake', self.spool.state['review'])
        self.assertNotIn('elf-male-a/bake', self.spool.state['attention'])

    def test_a_launch_where_nothing_ran_is_reported(self):
        self.head()
        self.approved({'stages': [{'stage': 'tone', 'status': 'skipped'}]})
        self.assertIn('nothing ran', self.spool.state['attention']['elf-male-a/launch']['text'])

    def test_a_reused_stage_is_judged_on_the_attempt_batch_named(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'attempts': [{'badFaceCount': 0, 'subtexel': {}}], 'gutters': {}, 'geometryUnchanged': True, 'charts': 9}})
        self.receipt(head, 'unwrap', 2, {'error': 'trial override failed'})
        name = self.spool.launch('unwrap', head.name)
        self.started.clear()
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': head.name, 'stages': [{'stage': 'unwrap', 'status': 'reused', 'attempt': str(head/'run/unwrap/attempt-01')}]}]})
        self.spool.step()
        self.assertEqual(self.started, [('bake', 'elf-male-a', 'unwrap')])

    def test_a_failure_before_any_attempt_shows_its_own_error(self):
        head = self.head()
        self.receipt(head, 'bake', 1, {'error': 'an old failure'})
        name = self.spool.launch('bake', head.name)
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': head.name, 'stages': [{'stage': 'bake', 'status': 'failed', 'error': 'Two stage failures retained', 'attempt': None}]}]})
        self.spool.step()
        self.assertIn('before any attempt: Two stage failures retained', self.spool.state['attention']['elf-male-a/bake']['text'])

    def test_a_gate_the_chain_passed_launches_nothing(self):
        head = self.head()
        self.receipt(head, 'unwrap', 1, {'result': {'attempts': [{'badFaceCount': 0, 'subtexel': {}}], 'gutters': {}, 'geometryUnchanged': True, 'charts': 9}})
        self.receipt(head, 'bake', 1, {'result': {}})
        name = self.spool.launch('unwrap', head.name)
        self.started.clear()
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': head.name, 'stages': [{'stage': 'unwrap', 'status': 'reused'}, {'stage': 'bake', 'status': 'ran'}]}]})
        self.spool.step()
        self.assertEqual(self.started, [])

    def test_a_bad_request_goes_to_attention_and_the_rest_still_run(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', '{"heads": [')
        write(self.workspace.spool/'queue/b.json', {'heads': ['no-such-head', 'elf-male-a'], 'stages': 'export'})
        started = self.spool.starter

        def start(name, stages, head, approve, notes, attempt=None):
            if head == 'no-such-head':
                raise FileNotFoundError(head)
            started(name, stages, head, approve, notes, attempt)
        self.spool.starter = start
        write(self.workspace.spool/'queue/c.json', '\ufeff'+json.dumps({'heads': ['elf-male-a'], 'stages': 'bake'}))
        write(self.workspace.spool/'approve/a.json', 'not json')
        self.spool.step()
        self.assertEqual(self.started, [('export', 'elf-male-a', None), ('bake', 'elf-male-a', None)])
        self.assertIn('a.json/queue', self.spool.state['attention'])
        self.assertIn('a.json/approve', self.spool.state['attention'])
        self.assertIn('no-such-head/export', self.spool.state['attention'])
        self.assertEqual(list((self.workspace.spool/'queue').glob('*')), [])

    def test_a_bad_result_goes_to_attention(self):
        name = self.spool.launch('bake', 'elf-male-a')
        write(self.workspace.spool/'results'/f'{name}.json', {'heads': [{'id': 'elf-male-a', 'stages': [{}]}]})
        self.spool.step()
        self.assertIn(f'{name}/launch', self.spool.state['attention'])

    def test_a_launch_is_on_disk_as_it_starts(self):
        name = self.spool.launch('bake', 'elf-male-a')
        self.assertIn(name, json.loads((self.workspace.spool/'state.json').read_text())['launches'])

    def test_a_queue_file_edited_during_the_presets_stays_queued(self):
        self.head()
        path = write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'repair'})

        def edit(*_):
            write(path, {'heads': ['elf-male-a'], 'stages': 'prepare'})
            return 0, ['done']
        self.spool.tool = edit
        self.spool.scan_requests()
        self.assertEqual(self.started, [])
        self.assertTrue(path.exists())

    def test_a_sheet_that_dies_goes_to_attention(self):
        self.spool.drawing[Path('clay-1.log')] = unittest.mock.Mock(poll=lambda: 2)
        self.spool.drawing[Path('clay-2.log')] = unittest.mock.Mock(poll=lambda: None)
        self.spool.scan_sheets()
        self.assertIn('exit 2', self.spool.state['attention']['clay-1/sheet']['text'])
        self.assertEqual(list(self.spool.drawing), [Path('clay-2.log')])

    def test_repair_evidence_says_what_the_jaw_check_did(self):
        head = self.head()
        self.receipt(head, 'repair', 1, {'result': {}})
        self.finish(stage='repair')
        self.assertIn('jaw not checked: no face marks', self.spool.state['review']['elf-male-a/repair']['text'])

    def test_queued_repair_runs_the_presets_and_a_hold_stops_it(self):
        self.head()
        write(self.workspace.spool/'queue/a.json', {'heads': ['elf-male-a'], 'stages': 'repair'})
        self.tool_result = (1, ['HOLD: no reach finds the chin'])
        self.spool.scan_requests()
        self.assertEqual(self.tools, [('presets', 'elf-male-a', '--apply')])
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

    def test_a_launch_from_before_a_restart_is_kept_while_it_holds_its_head(self):
        name = self.restored(600)
        with guards.head_lock(self.workspace, 'elf-male-a'):
            self.spool.scan_launches()
        self.assertIn(name, self.spool.state['launches'])
        self.assertEqual(self.spool.state['attention'], {})

    def test_a_restored_launch_gets_time_to_take_its_lock(self):
        name = self.restored(5)
        self.spool.scan_launches()
        self.assertIn(name, self.spool.state['launches'])

    def test_a_restored_launch_with_no_lock_and_no_result_goes_to_attention(self):
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

class ConditioningContracts(Base):
    def record(self):
        import reference_record
        image=write(self.root/'external.png','beauty')
        record=write(self.root/'reference.json',{'kind':'headbatch-reference-v1','head':'elf-male-a',
            'generator':'external fixture','prompt':'preserved original prompt',
            'design':{'path':image.name,'sha256':head_setup.sha(image)},
            'features':{key:'explicitly absent' for key in reference_record.FEATURES}})
        return image,record

    def test_external_intake_rejects_stale_prompt_fallback_and_changed_images(self):
        import reference_record
        image,record=self.record()
        with self.assertRaisesRegex(guards.Refused,'reference-record'):
            head_setup.selected_prompt(self.workspace,'elf-male-a','elf',image)
        prompt,lineage,expected=head_setup.selected_prompt(self.workspace,'elf-male-a','elf',image,record)
        self.assertEqual(prompt,'preserved original prompt')
        self.assertEqual(lineage['generator'],'external fixture')
        write(image,'modified')
        with self.assertRaisesRegex(guards.Refused,'missing or changed'):
            reference_record.load(record,'elf-male-a',image)

    def test_record_requires_complete_features_and_distinct_pair(self):
        import reference_record
        image,record=self.record();data=guards.read(record)
        del data['features']['horns'];write(record,data)
        with self.assertRaisesRegex(guards.Refused,'feature inventory'):reference_record.load(record,'elf-male-a')
        data['features']['horns']='two; one on each side'
        data['conditioning']={'clay':data['design'],'detail':data['design'],'alignment':{'landmarks':[{}, {}, {}]}}
        write(record,data)
        with self.assertRaisesRegex(guards.Refused,'collapse'):reference_record.load(record,'elf-male-a')

    def test_external_setup_uses_inventory_and_copies_record(self):
        fixture=Setup(methodName='test_set_up_writes_a_complete_head')
        fixture.root=self.root;fixture.workspace=self.workspace;fixture.prepare()
        image,record=self.record()
        manifest=head_setup.set_up(self.workspace,'elf-male-a',image,approval='user selected fixture',reference=record,check=lambda *_:None)
        receipt=guards.read(manifest.parent/'design/design-receipt.json')
        self.assertEqual(receipt['featureInventory']['hair'],'explicitly absent')
        self.assertEqual(receipt['approval'],'user selected fixture')
        self.assertEqual(head_setup.sha(manifest.parent/'design/reference-record.json'),head_setup.sha(record))
        self.assertNotIn('faceMasks',guards.read(manifest))

    def test_revised_clay_preserves_source_and_ledger_and_needs_exact_check(self):
        from PIL import Image, ImageDraw
        import reference_record
        from headkit.common import pin
        fixture = Setup(methodName='test_set_up_writes_a_complete_head')
        fixture.root, fixture.workspace = self.root, self.workspace
        fixture.prepare()
        name = 'elf-male-a'
        image, original = self.record()
        record = guards.read(original)
        def clay(label, color):
            path = self.root/(label+'.png')
            canvas = Image.new('RGBA', (64, 64))
            ImageDraw.Draw(canvas).ellipse((12, 10, 51, 55), fill=color)
            canvas.save(path)
            return pin(path)
        alignment = {'landmarks': [{'name': str(i), 'clay': xy, 'detail': xy}
                      for i, xy in enumerate([[.3,.3], [.6,.3], [.4,.6]])]}
        old = clay('original-clay', 'gray')
        record['conditioning'] = {'clay': old, 'detail': clay('detail', 'brown'), 'alignment': alignment}
        write(original, record)
        head = head_setup.set_up(self.workspace, name, image, approval='original', reference=original, check=lambda *_:None).parent
        ledger = write(head/'gpu/gpu.json', {'stages': {}, 'geometrySubmissions': 2})
        before = pin(ledger)
        record['conditioning']['clay'] = clay('revised-clay', 'silver')
        new = write(self.root/'revised.json', record)
        reference_record.check(new, name, self.root/'measured')
        checked = self.root/'measured/reference-check.json'
        def select():
            head_setup.revise_clay(self.workspace, name, image, new, checked, 'select this revision', check=lambda *_:None)
        select()
        select()
        active = guards.read(head/'manifest.json')['inputs']
        self.assertEqual(head_setup.sha(head/active['clay']['path']), record['conditioning']['clay']['sha256'])
        self.assertEqual(head_setup.sha(head/'inputs/clay.png'), old['sha256'])
        self.assertEqual(pin(ledger), before)
        candidate = pin(head/'manifest.json')
        with new.open('a',encoding='utf-8') as output:
            output.write(' ')
        with self.assertRaisesRegex(guards.Refused, 'exact revised pair'):
            select()
        self.assertEqual(pin(head/'manifest.json'), candidate)

    def test_face_profile_is_complete_and_feature_channels_get_tones(self):
        profile=head_setup.face_quality_profile()
        self.assertEqual(profile['mesh']['uv']['faceDensity'],3)
        self.assertEqual(profile['palette']['skinShadeContrast'],'auto')
        self.assertEqual(set(('faceMasks','quality'))-set(profile),set())
        data={'ownership':profile['ownership'],'palette':{'rows':{'1':'auto','8':'auto'}}}
        head_setup.tone_every_channel(data,'troll','female','fixture')
        self.assertEqual(set(data['palette']['toneMatch']),{'0','1','8'})
        self.assertEqual(data['palette']['rows'],{'1':'auto','8':'auto'})
        self.assertTrue(profile['render']['runtimePalette'])

    def test_multiview_stages_exact_roles_without_a_camera_job_and_reuses_saved_shape(self):
        from headkit.common import pin
        from PIL import Image
        head = self.head()
        stage_input = self.root/'staging'
        stage_input.mkdir()
        source = self.root/'view.png'
        im = Image.new('RGBA', (8,8), (240,4,180,0))
        im.putpixel((3,3), (50,60,70,255))
        im.save(source)
        keys = [role+v for role in ('geometry','detail') for v in gpu_job.MULTIVIEW_VIEWS]
        prepared = write(self.root/'prepared.json', {'profile':'pixal-multiview-v1', 'pins':[], 'attempt':'attempt-02',
                         'receipt':pin(source), 'images':{key:pin(source) for key in keys}})
        server = unittest.mock.Mock()
        calibrated = gpu_job.calibrate(server, head, head/'gpu', {}, stage_input, 'unused', prepared=prepared)
        server.run.assert_not_called()
        ledger = {'stages':{'calibrate':calibrated}}
        with Image.open(calibrated['conditioning']['geometryBack']['path']) as staged:
            self.assertEqual(staged.mode, 'RGB')
            self.assertEqual(staged.getpixel((0,0)), (0,0,0))
            self.assertEqual(staged.getpixel((3,3)), (50,60,70))
        for stage, nodes, role in [('geometry', ('364','377','378','379'), 'geometry'),
                                   ('appearance', ('1001','1002','1003','1004'), 'detail')]:
            graph = gpu_job.conditioned_graph(head, ledger, stage, 'headkit/fixture/run', pin(source) if stage=='appearance' else None)
            for node, view in zip(nodes, gpu_job.MULTIVIEW_VIEWS):
                self.assertEqual(Path(graph[node]['inputs']['image']).name, Path(calibrated['conditioning'][role+view]['path']).name)
            self.assertIn('Pixal3DMultiViewConditioning', {v['class_type'] for v in graph.values()})
        self.assertEqual(gpu_job.geometry_graph(head, ledger, 'headkit/fixture/run', 0, 1024)['94']['inputs']['target_resolution'], 1024)
        write(Path(calibrated['conditioning']['geometryBack']['path']), 'changed')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            gpu_job.geometry_graph(head, ledger, 'headkit/fixture/run', 0)

    def test_paired_calibration_preserves_geometry_and_detail_outputs(self):
        from PIL import Image
        from headkit.common import pin
        head=self.root/'head';stage=self.root/'input';stage.mkdir()
        images={}
        for role,color in (('geometry','grey'),('detail','red'),('mask','white')):
            path=self.root/(role+'.png');Image.new('RGBA',(8,8),color).save(path);images[role]=pin(path)
        receipt=write(self.root/'receipt.json',{})
        prepared=write(self.root/'prepared.json',{'attempt':'attempt-03','pins':[pin(receipt)],'receipt':pin(receipt),'images':images})
        outputs={role:write(self.root/(role+'.bin'),role) for role in ('geometry','detail')}
        class Comfy:
            def run(inner,graph,out):
                self.assertNotEqual(graph['1']['inputs']['image'],graph['2']['inputs']['image'])
                return {'outputs':{'10':{'text':['40']},'16':{'text':['42']}}}, {
                    '12:g':pin(outputs['geometry']),'13:d':pin(outputs['detail'])},1
        ledger={}
        row=gpu_job.calibrate(Comfy(),head,self.root/'gpu',ledger,stage,'headkit/fixture/calibrate',prepared=prepared)
        self.assertEqual(Path(row['conditioning']['geometry']['path']).read_text(),'geometry')
        self.assertEqual(Path(row['conditioning']['detail']['path']).read_text(),'detail')
        self.assertEqual(ledger['matteAttempt'],'attempt-03')
        self.assertEqual(row['sharedFov'],40)
        ledger['stages']={'calibrate':row}
        write(stage/'normalized-geometry.png','changed')
        with self.assertRaisesRegex(ValueError,'Stale'):
            gpu_job.conditioning_image(ledger,head,'geometry')

    def test_multiview_start_floor_applies_to_geometry_only(self):
        config = dict(memoryLimitBytes=100, minimumFreeRAMGiB=2, minimumStartRAMGiB=14,
                      multiviewGeometryStartRAMGiB=22)
        for profile, stages, floor in [('pixal-multiview-v1', ['geometry'], 22),
                                        ('pixal-multiview-v1', ['appearance'], 14),
                                        ('pixal-single-v1', ['geometry'], 14)]:
            result = launcher.gpu_memory_limits(config, profile, stages)
            self.assertEqual(result['minimumStartRAMGiB'], floor)
            self.assertEqual(result['minimumFreeRAMGiB'], 2)
            self.assertEqual(result['memoryLimitBytes'], 100)

    def test_resource_samples_fail_closed_and_keep_breach(self):
        from resource_budget import Budget,BudgetExceeded
        values=iter([(11_000_000_000,16),(12_000_000_001,8),(1,8)])
        budget=Budget({'memoryLimitBytes':12_000_000_000,'minimumFreeRAMGiB':2},self.root/'budget.json',lambda _:next(values))
        budget.sample();budget.check();budget.sample();budget.sample()
        with self.assertRaisesRegex(BudgetExceeded,'VRAM'):budget.check()
        budget.close()
        receipt = guards.read(self.root/'budget.json')
        self.assertEqual(receipt['samples'], 3)
        self.assertEqual(receipt['initialSample'], {'deviceBytes': 11_000_000_000, 'availableRAMGiB': 16})
        self.assertEqual(receipt['minimumAvailableRAMGiB'], 8)
        bad=Budget({'memoryLimitBytes':12_000_000_000},self.root/'bad.json',lambda _:(_ for _ in ()).throw(OSError('offline')))
        bad.sample()
        with self.assertRaisesRegex(BudgetExceeded,'failed'):bad.check()

    def test_memory_stop_interrupts_only_owned_prompt_without_retry(self):
        from resource_budget import BudgetExceeded
        comfy=gpu_job.Comfy('unused',self.root)
        comfy.budget=unittest.mock.Mock()
        comfy.budget.check.side_effect=BudgetExceeded('budget')
        interrupted=threading.Event()
        def call(route,**kwargs):
            if route=='/queue':return {'queue_running':[[0,'owned']],'queue_pending':[]}
            self.assertTrue(interrupted.wait(2))
            return {'owned':{'status':{'completed':True,'status_str':'error'}}}
        comfy.call=call
        comfy.send=unittest.mock.Mock(side_effect=lambda *a,**k:interrupted.set())
        comfy.unresolved=write(self.root/'unreconciled',{})
        with self.assertRaisesRegex(SystemExit,'Resource supervision stopped'):
            comfy.wait('owned')
        comfy.send.assert_called_once_with('/interrupt',{'prompt_id':'owned'},timeout=2)
        self.assertFalse(comfy.unresolved.exists())

    def test_dispatch_headroom_is_separate_from_running_floor(self):
        from resource_budget import Budget,BudgetExceeded
        values=iter([(10,9),(10,15),(10,4)])
        budget=Budget({'memoryLimitBytes':100,'minimumStartRAMGiB':14,'minimumFreeRAMGiB':2},
                      self.root/'admission.json',lambda _:next(values))
        budget.sample()
        with self.assertRaisesRegex(BudgetExceeded,'dispatch needs'):budget.admit_prompt()
        budget.sample();budget.admit_prompt()
        budget.sample();budget.check()

    def test_ram_floor_and_sampler_staleness(self):
        from resource_budget import Budget,BudgetExceeded
        budget=Budget({'memoryLimitBytes':12_000_000_000,'minimumFreeRAMGiB':2},self.root/'budget.json',lambda _:(1,1.9))
        budget.sample()
        with self.assertRaisesRegex(BudgetExceeded,'RAM'):budget.check()
        budget.reason=None;budget.last=0
        with self.assertRaisesRegex(BudgetExceeded,'unavailable'):budget.check()

class DeliveryAndRetryContracts(Base):
    def test_oom_attempt_keeps_its_own_history_and_charges_both_submissions(self):
        server=GpuJob.Server(self.root,polls=[
            {'p1':{'status':{'completed':False,'status_str':'error','messages':['out of memory']},'outputs':{}}},
            GpuJob.DONE])
        write(self.root/'output/raw_00001.glb','geometry')
        charged=[]
        with unittest.mock.patch.object(gpu_job.time,'sleep'):
            server.run({},self.root/'gpu/geometry',lambda:charged.append(True))
        self.assertEqual(len(charged),2)
        self.assertEqual(guards.read(self.root/'gpu/geometry/history.json')['status']['status_str'],'error')
        self.assertTrue((self.root/'gpu/geometry-02/history.json').is_file())

    def test_face_palette_sheet_takes_ram_slot_and_waits_for_user(self):
        head=self.head();data=guards.read(head/'manifest.json');data['quality']={};write(head/'manifest.json',data)
        worker=spool.Spool(self.workspace,starter=unittest.mock.Mock())
        self.receipt(head,'palette',1,{'state':'complete','result':{'rows':{'0':7}}})
        with unittest.mock.patch.object(worker,'tool',return_value=(0,['exact-sheet.png'])) as tool, unittest.mock.patch.object(worker,'launch') as launch:
            worker.on_success(head.name,'palette',{})
            self.assertIn(unittest.mock.call('review','--slot','gamesize',head.name,'attempt-01'),tool.call_args_list)
            launch.assert_not_called()
            self.assertIn('exact-sheet.png',worker.state['review'][head.name+'/palette']['text'])
            tool.side_effect=[(0,['ramp.png']),(1,['failed'])]
            worker.on_success(head.name,'palette',{})
            launch.assert_not_called()
            self.assertIn('incomplete',worker.state['review'][head.name+'/palette']['text'])

    def test_quality_routes_to_export_only_on_numeric_pass(self):
        head=self.head();data=guards.read(head/'manifest.json');data['quality']={};write(head/'manifest.json',data)
        worker=spool.Spool(self.workspace,starter=unittest.mock.Mock())
        with unittest.mock.patch.object(worker,'launch') as launch:
            self.receipt(head,'quality',1,{'state':'complete','result':{'passed':True,'failed':[]}})
            worker.on_success(head.name,'quality',{})
            self.assertEqual(launch.call_args.args[:3],('export',head.name,'quality'))
            self.receipt(head,'quality',2,{'state':'complete','result':{'passed':False,'failed':['blotch']}})
            worker.on_success(head.name,'quality',{})
            self.assertEqual(launch.call_count,1)

    def test_full_reviewed_render_waits_for_client(self):
        from head_files import sha
        head=self.head();delivery={'diagnostic':False,'sizes':[2048,1024],'runtimePalette':True,
             'modes':['clay','color-only','material-lit'],
             'views':['left-three-quarter','right-three-quarter','left-back-three-quarter','right-back-three-quarter']}
        self.receipt(head,'render',1,{'state':'complete','result':{'delivery':delivery}})
        receipt=head/'run/render/attempt-01/receipt.json';bound={'path':str(receipt),'sha256':sha(receipt)}
        review=write(head/'run/reviews/render.json',{'stageReceipt':bound,'decision':'approved'})
        write(head/'run/state.json',{'stages':{'render':bound},'reviews':{'render':{'path':str(review),'sha256':sha(review)}}})
        self.assertIn('WAITING ON CLIENT TRIAL',launcher.status(self.workspace)[0])

class FitLandmarkEvidence(Base):
    def test_paired_prepare_and_indexed_triangles_are_read_from_the_bound_attempts(self):
        import numpy as np
        from PIL import Image
        from headkit.common import pin
        from headkit.gltf import encode, load, write_mesh
        from review import design_landmarks as diagnostic

        head = self.head()
        prepare = head/'run/prepare/attempt-01'
        cluster = head/'run/precluster/attempt-01'
        prepare.mkdir(parents=True)
        cluster.mkdir(parents=True)
        diffuse = prepare/'detail-pair.png'
        Image.new('RGBA', (2,2), (15,40,80,255)).save(diffuse)
        source = cluster/'oriented.glb'
        vertices = np.array([[0,0,0], [1,0,0], [0,1,0]], dtype=np.float32)
        write_mesh(source, vertices, np.array([[0,1,2]]))
        # Store the opposite winding in the GLB index buffer without reordering POSITION.
        doc, blob, primitive = load(source.read_bytes())
        view = doc['bufferViews'][doc['accessors'][primitive['indices']]['bufferView']]
        offset = view['byteOffset']
        packed = bytearray(blob)
        packed[offset:offset+12] = np.array([0,2,1], dtype='<u4').tobytes()
        source.write_bytes(encode(doc, packed))
        self.receipt(head, 'prepare', 1, {'state':'complete','result':{'images':{'detail-pair.png':pin(diffuse)}}})
        self.receipt(head, 'precluster', 1, {'state':'complete','result':{'output':pin(source)}})
        self.receipt(head, 'precluster', 2, {'state':'failed'})
        write(head/'run/state.json', {'stages':{'prepare':pin(prepare/'receipt.json'), 'precluster':pin(cluster/'receipt.json')}})
        with unittest.mock.patch.object(diagnostic, 'HEADS', head.parent):
            rgb, mask, path = diagnostic.design(head.name)
            self.assertEqual(Path(path), diffuse)
            self.assertTrue(mask.all())
            np.testing.assert_array_equal(rgb[0,0], [15,40,80])
            np.testing.assert_allclose(diagnostic.positions(head.name), [[1/3,1/3,0,0,0,-1]], atol=1e-6)


class TextureSheetContract(Base):
    def test_eye_pair_keeps_both_halves_in_the_same_camera(self):
        from PIL import Image
        import numpy as np
        from review.texturesheet import eye_pair
        im = Image.new('RGB', (200, 100), 'black')
        im.putpixel((38, 40), (255, 0, 0))
        im.putpixel((138, 40), (0, 255, 0))
        overlay = self.root/'mask-pair.png'
        im.save(overlay)
        pts = np.zeros((478, 2))
        pts[[33, 263]] = [[30, 40], [70, 40]]
        landmarks = self.root/'landmarks.npy'
        np.save(landmarks, pts)
        pair = np.asarray(eye_pair(overlay, landmarks))
        half = pair.shape[1]//2
        np.testing.assert_array_equal(pair[:, :half, 0], pair[:, half:, 1])
        self.assertEqual(int(pair[:, :half, 0].sum()), 255)

    def test_projected_iris_count_reports_a_missing_eye(self):
        import numpy as np
        from review.texturesheet import projected_iris_pixels
        coverage = np.array([[.0,.8,.01,.1],[.0,.7,.0,.1]])
        circles = {'R': ([3,1], 1), 'L': ([1,1], 1)}
        self.assertEqual(projected_iris_pixels(coverage, circles), {'R': 0, 'L': 2})

    def test_sheet_binds_exact_attempt_and_refuses_drift(self):
        from PIL import Image
        from review.texturesheet import draw
        head=self.head();folder=head/'run/tone/attempt-01';folder.mkdir(parents=True)
        image=folder/'tone-1024.png';Image.new('RGB',(16,16),'red').save(image)
        write(folder/'receipt.json',{'state':'complete','outputs':[{'path':str(image),'sha256':head_setup.sha(image)}]})
        output=self.root/'review.png';draw(head,'tone','attempt-01',output)
        self.assertTrue(output.is_file())
        Image.new('RGB',(16,16),'blue').save(image)
        with self.assertRaisesRegex(ValueError,'changed'):draw(head,'tone','attempt-01',self.root/'changed.png')


if __name__ == '__main__':
    unittest.main()
