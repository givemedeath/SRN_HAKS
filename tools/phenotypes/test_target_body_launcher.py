"""Execute the target guard with harmless preflight/shared-launcher stubs only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PWSH = os.environ.get('PHENOTYPE_TEST_PWSH') or shutil.which('pwsh')


@unittest.skipUnless(PWSH, 'PowerShell is required for launcher integration tests')
class TargetBodyLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='female fixture guard ')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.helpers = self.root/'tools/phenotypes'
        self.helpers.mkdir(parents=True)
        self.fixture = self.root/'fixture with spaces'
        self.fixture.mkdir()
        self.launcher = self.helpers/'Launch-TargetBodyClient.ps1'
        shutil.copyfile(Path(__file__).with_name(self.launcher.name), self.launcher)
        self.target = self.root/'target contract.json'
        self.toolchain = self.root/'toolchain.json'; self.toolchain.write_text('{}')
        self.migration = self.root/'migration.json'; self.migration.write_text('{}')
        self.client = self.root/'unlaunchable client.exe'; self.client.write_text('No game can start')
        self.stock_ascii = self.root/'installed root.mdl'; self.stock_ascii.write_bytes(b'stock root')
        self.table = self.root/'appearance.2da'; self.table.write_bytes(b'installed table')
        self.palette = self.root/'pal_skin01.tga'; self.palette.write_bytes(b'palette')
        self.stock = self.root/'stock-reference.json'
        self.stock.write_text(json.dumps({
            'rootAscii':self.pin(self.stock_ascii),
            'frozenInputs':{str(path):self.sha(path) for path in (self.stock_ascii, self.palette)}}))
        self.target.write_text(json.dumps({
            'rig':{'mode':'stock-exact', 'stockReferenceReceipt':self.pin(self.stock)},
            'frozenInputs':{str(self.table):self.sha(self.table)}}))
        package = self.fixture/'userdir'; package.mkdir()
        (package/'nwn.ini').write_text('[Alias]\n')
        module = package/'srn_female_test.mod'; module.write_bytes(b'module')
        hak = package/'srn_female_test.hak'; hak.write_bytes(b'hak')
        stage = self.fixture/'test-module'; stage.mkdir()
        self.module_source = stage/'module-resources'; self.module_source.mkdir()
        (self.module_source/'module.ifo').write_bytes(b'literal native module')
        self.hak_source = stage/'hak-resources'; self.hak_source.mkdir()
        (self.hak_source/'sr_tm.set').write_bytes(b'literal tileset')
        self.gff = self.root/'gff.exe'; self.gff.write_bytes(b'nonexecutable tool')
        self.resman = self.root/'resman.exe'; self.resman.write_bytes(b'nonexecutable tool')
        self.equipment = stage/'equipment.json'
        self.equipment.write_text(json.dumps({'frozenInputs':{str(self.table):self.sha(self.table)}}))
        self.body = self.root/'native body'
        self.native_folder(self.body, composition=True)
        self.receipt = stage/'receipt.json'
        self.build = {'moduleName':'srn_female_test', 'module':str(module), 'hak':str(hak),
            'moduleSha256':self.sha(module), 'hakSha256':self.sha(hak),
            'gffTool':str(self.gff), 'gffToolSha256':self.sha(self.gff),
            'resmanTool':str(self.resman), 'resmanToolSha256':self.sha(self.resman),
            'equipmentSelection':self.pin(self.equipment),
            'stockTableBaselines':{'appearance.2da':self.pin(self.table)},
            'bodyConverted':str(self.body), 'validationScope':'full',
            # Historical source provenance is not a consumed preflight directory.
            'sourcePreparation':{'path':str(self.root/'unread historical receipt.json'), 'sha256':'a'*64}}
        self.write_build()
        (self.helpers/'consumed_helper.py').write_text('VALUE = 1\n')
        (self.helpers/'unrelated_test.py').write_text('raise AssertionError("must not be consumed")\n')
        (self.helpers/'launch_shared_tool.py').write_text("""
import hashlib, json, subprocess, sys
from pathlib import Path
args=sys.argv[1:]; end=args.index('--')
output=Path(args[args.index('--output')+1]); output.mkdir()
inputs=[args[i+1] for i in range(end) if args[i]=='--input']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen={p:sha(p) for p in inputs}
result=subprocess.run([sys.executable,*args[end+1:]])
unchanged=all(Path(p).is_file() and sha(p)==h for p,h in frozen.items())
(output/'launch.json').write_text(json.dumps({
    'verifiedLauncherStub':True,'arguments':args,'frozenInputs':frozen,
    'inputsUnchanged':unchanged,'exitCode':result.returncode}))
if not unchanged:
    print('Consumed input changed during preflight',file=sys.stderr)
raise SystemExit(result.returncode if unchanged else 1)
""")
        (self.helpers/'preflight_target_body_client.py').write_text("""
import argparse, hashlib, json, sys
from pathlib import Path
import consumed_helper
p=argparse.ArgumentParser()
for key in ('fixture','receipt-sha256','client','target-contract','output'):
    p.add_argument('--'+key,required=True)
a=p.parse_args(); fixture=Path(a.fixture)
build=json.loads((fixture/'test-module/receipt.json').read_text())
(fixture/'dispatch.json').write_text(json.dumps({
    'python':sys.executable,'targetContract':a.target_contract,
    'receiptSha256':a.receipt_sha256,'client':a.client}))
if (fixture/'reject-preflight').exists(): sys.exit(7)
sha=lambda value:hashlib.sha256(Path(value).read_bytes()).hexdigest()
proof={'pass':True,'clientLaunched':False,'fixtureReceiptSha256':a.receipt_sha256,
    'targetContractSha256':sha(a.target_contract),'userDirectory':str(fixture/'userdir'),
    'moduleName':build['moduleName'],'hakSha256':build['hakSha256'],
    'moduleSha256':build['moduleSha256'],'clientSha256':sha(a.client)}
if (fixture/'wrong-module').exists(): proof['moduleName']='srn_troll_test'
if (fixture/'cross-target').exists(): proof['targetContractSha256']='a'*64
if (fixture/'incomplete').exists(): proof['pass']=False
if (fixture/'changed-client').exists(): Path(a.client).write_text('changed')
mutation=fixture/'mutate-during-preflight.json'
if mutation.exists(): Path(json.loads(mutation.read_text())['path']).write_bytes(b'changed during run')
Path(a.output).write_text(json.dumps(proof))
""")

    @staticmethod
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def pin(self, path):
        return {'path':str(path), 'sha256':self.sha(path)}

    def write_build(self):
        self.receipt.write_text(json.dumps(self.build))

    @staticmethod
    def native_folder(path, composition):
        path.mkdir()
        (path/'ascii').mkdir(); (path/'resources').mkdir()
        (path/'ascii/body.mdl').write_bytes(b'original ASCII')
        (path/'resources/body.mdl').write_bytes(b'compiled binary')
        (path/'resources/body.plt').write_bytes(b'material')
        (path/'native-compile.json').write_text('{}')
        if composition:
            (path/'conversion.json').write_text(json.dumps({'frozenInputs':{}}))

    def run_guard(self, omit=None, no_launch=True, receipt_hash=None):
        values = {'TargetContract':self.target, 'Fixture':self.fixture,
            'ReceiptSha256':receipt_hash or self.sha(self.receipt), 'Client':self.client,
            'WorkspacePython':sys.executable, 'Toolchain':self.toolchain,
            'MigrationReceipt':self.migration}
        command = [str(PWSH), '-NoProfile', '-NonInteractive', '-File', str(self.launcher)]
        if no_launch: command += ['-NoLaunch']
        for key, value in values.items():
            if key != omit: command += ['-'+key, str(value)]
        return subprocess.run(command, capture_output=True, text=True, timeout=30)

    def launches(self):
        return sorted((self.root/'.tmp').glob('hf-client-*-launch/launch.json'))

    def shared_roster(self):
        self.shared_input = self.root/'other-race-source.mdl'; self.shared_input.write_bytes(b'original shared source')
        self.roster_input = self.root/'stock-equipment.uti'; self.roster_input.write_bytes(b'original equipment')
        shared = self.root/'shared-overlay.json'
        shared.write_text(json.dumps({'kind':'executed-shared-female-source-native-idle-overlay'}))
        roster = self.root/'roster.json'; roster.write_text('{}')
        self.stock_archive=self.root/'installed-archive.bif';self.stock_archive.write_bytes(b'original archive')
        self.stock_binding=self.root/'stock-binding.json'
        self.stock_binding.write_text(json.dumps({'roster':self.pin(roster),'archive':self.pin(self.stock_archive)}))
        self.build.update(animationOverlay=self.pin(shared),postureRoster=self.pin(roster),
            postureStockBinding=self.pin(self.stock_binding),bodyConverted=None)
        self.write_build()
        code = """from pathlib import Path
import hashlib
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def collect_overlay_inputs(entry,target):
    data={str(Path(entry['path']).resolve()):entry['sha256']}
    path=Path(__file__).resolve().parents[2]/'other-race-source.mdl'
    data[str(path)]=sha(path)
    return data
"""
        (self.helpers/'shared_female_animation_overlay.py').write_text(code)
        code = """from pathlib import Path
import hashlib
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify_roster(entry,target):
    path=Path(__file__).resolve().parents[2]/'stock-equipment.uti'
    return {'frozenInputs':{str(Path(entry['path']).resolve()):entry['sha256'],str(path):sha(path)}}
"""
        (self.helpers/'shared_female_posture_fixture.py').write_text(code)
        code = '''from pathlib import Path
import hashlib,json
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def collect_stock_basis_inputs(entry,target,roster):
    binding=json.loads(Path(entry['path']).read_text())
    if sha(entry['path'])!=entry['sha256'] or binding['roster']!=roster:
        raise ValueError('Exact stock binding/roster mismatch')
    archive=binding['archive']
    if sha(archive['path'])!=archive['sha256']:
        raise ValueError('Installed archive drift')
    return {entry['path']:entry['sha256'],archive['path']:archive['sha256']}
'''
        (self.helpers/'shared_female_stock_basis.py').write_text(code)
        return shared,roster

    def test_shared_family_and_typed_roster_inputs_are_frozen_by_launcher(self):
        shared,roster=self.shared_roster()
        result=self.run_guard()
        self.assertEqual(result.returncode,0,result.stderr)
        launch=json.loads(self.launches()[0].read_text())
        declared={Path(path).resolve() for path in launch['frozenInputs']}
        required={shared,roster,self.shared_input,self.roster_input,
            self.stock_binding,self.stock_archive,self.helpers/'shared_female_stock_basis.py',
            self.helpers/'shared_female_animation_overlay.py',self.helpers/'shared_female_posture_fixture.py'}
        self.assertTrue(required <= declared,required-declared)
        self.assertTrue(launch['inputsUnchanged'])
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_shared_input_drift_during_preflight_rejects_before_game_launch(self):
        self.shared_roster()
        (self.fixture/'mutate-during-preflight.json').write_text(json.dumps({'path':str(self.shared_input)}))
        result=self.run_guard()
        self.assertNotEqual(result.returncode,0)
        launch=json.loads(self.launches()[0].read_text())
        self.assertFalse(launch['inputsUnchanged'])
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_unbound_or_cross_roster_stock_basis_rejects_before_dispatch(self):
        self.shared_roster()
        original=dict(self.build)
        for key in ('postureRoster','postureStockBinding'):
            self.build={k:v for k,v in original.items() if k!=key};self.write_build()
            result=self.run_guard(no_launch=False)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(self.launches())
            self.assertFalse(list(self.fixture.glob('client-launch-*.json')))
        self.build=original;self.write_build()
        self.stock_binding.write_text(json.dumps({'roster':{'path':'wrong','sha256':'f'*64},
            'archive':self.pin(self.stock_archive)}))
        self.build['postureStockBinding']=self.pin(self.stock_binding);self.write_build()
        result=self.run_guard(no_launch=False)
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.launches())
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_installed_archive_drift_during_preflight_blocks_game_launch(self):
        self.shared_roster()
        (self.fixture/'mutate-during-preflight.json').write_text(json.dumps({'path':str(self.stock_archive)}))
        result=self.run_guard(no_launch=False)
        self.assertNotEqual(result.returncode,0)
        launch=json.loads(self.launches()[0].read_text())
        self.assertFalse(launch['inputsUnchanged'])
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_target_paths_receipt_and_bundled_interpreter_reach_preflight(self):
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        proof = json.loads(result.stdout)
        self.assertEqual(proof['moduleName'], 'srn_female_test')
        self.assertFalse(proof['clientLaunched'])
        dispatch = json.loads((self.fixture/'dispatch.json').read_text())
        self.assertEqual(Path(dispatch['python']).resolve(), Path(sys.executable).resolve())
        self.assertEqual(Path(dispatch['targetContract']).resolve(), self.target.resolve())
        self.assertEqual(dispatch['receiptSha256'], self.sha(self.receipt))
        self.assertEqual(len(self.launches()), 1)
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_declared_closure_covers_exact_stock_native_fixture_and_local_imports(self):
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = json.loads(self.launches()[0].read_text())
        declared = {Path(path).resolve() for path in launch['frozenInputs']}
        required = {self.target, self.receipt, self.client, self.launcher,
            self.stock, self.stock_ascii, self.table, self.palette, self.equipment,
            self.gff, self.resman, self.fixture/'userdir/nwn.ini',
            self.helpers/'preflight_target_body_client.py', self.helpers/'consumed_helper.py'}
        required.update(self.module_source.iterdir()); required.update(self.hak_source.iterdir())
        required.update(self.body/'resources'/name for name in ('body.mdl','body.plt'))
        required.update((self.body/'ascii/body.mdl', self.body/'conversion.json',
                         self.body/'native-compile.json', Path(self.build['module']), Path(self.build['hak'])))
        self.assertTrue(required <= declared, required-declared)
        self.assertNotIn(self.helpers/'unrelated_test.py', declared)
        self.assertNotIn(self.root/'unread historical receipt.json', declared)
        self.assertTrue(launch['inputsUnchanged'])
        inputs_file = next(path for path in declared if path.name.endswith('-inputs.json'))
        manifest = json.loads(inputs_file.read_text())
        self.assertIn(str((self.helpers/'consumed_helper.py').resolve()),
                      manifest['repositoryLocalImportEdges'][str((self.helpers/'preflight_target_body_client.py').resolve())])
        self.assertTrue(any(path.name.endswith('-request.json') for path in declared))
        self.assertTrue(any(path.name.endswith('-argv.py') for path in declared))

    def test_stale_literal_target_stock_equipment_and_receipt_pins_reject_before_dispatch(self):
        for path in (self.table, self.stock_ascii, self.stock, self.equipment):
            with self.subTest(path=path):
                original = path.read_bytes(); path.write_bytes(b'stale')
                result = self.run_guard(); path.write_bytes(original)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Declared consumed input changed', result.stderr)
                self.assertFalse((self.fixture/'dispatch.json').exists())
        result = self.run_guard(receipt_hash='a'*64)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.fixture/'dispatch.json').exists())
        self.assertFalse(self.launches())

    def test_consumed_native_material_helper_and_ini_drift_during_preflight_fail_closed(self):
        for path in (self.body/'ascii/body.mdl', self.body/'resources/body.plt',
                     self.helpers/'consumed_helper.py', self.fixture/'userdir/nwn.ini'):
            with self.subTest(path=path):
                original = path.read_bytes()
                (self.fixture/'mutate-during-preflight.json').write_text(json.dumps({'path':str(path)}))
                result = self.run_guard()
                path.write_bytes(original)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('preflight failed', result.stderr)
                # UUID lexical ordering is unrelated to execution ordering.
                failed = [json.loads(item.read_text()) for item in self.launches()]
                self.assertTrue(any(not row['inputsUnchanged'] for row in failed))
                self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_retargeted_native_groups_keep_their_declared_flat_inputs(self):
        self.target.write_text(json.dumps({'rig':{'mode':'retargeted'}, 'frozenInputs':{}}))
        for key in ('rigConverted','provisionalConverted','stockConverted'):
            path = self.root/key
            self.native_folder(path, composition=False)
            self.build[key] = str(path)
        self.build['validationScope'] = 'pilot'; self.write_build()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        declared = set(json.loads(self.launches()[0].read_text())['frozenInputs'])
        for key in ('rigConverted','provisionalConverted','stockConverted'):
            path = Path(self.build[key])
            self.assertTrue({str((path/rel).resolve()) for rel in (
                'native-compile.json','ascii/body.mdl','resources/body.mdl','resources/body.plt')} <= declared)
        self.assertNotIn(str(self.stock.resolve()), declared)

    def overlay_inputs(self):
        area = self.root/'explicit overlay'
        area.mkdir()
        top = {}
        for key in ('preparation','rangePlan','restoration','independentReview',
                    'sourceRoot','sourceNativeOwner','numericCorrectedArrays'):
            path = area/(key+'.json')
            # No historical opaque pin claims are read by the overlay verifier.
            path.write_text(json.dumps({'frozenInputs':{str(self.root/'unread cold backup.bin'):'b'*64}}))
            top[key] = self.pin(path)
        parent = area/'compiler-parent.mdl'; parent.write_bytes(b'actual compiler parent')
        execution = area/'compile-execution.json'; execution.write_text('{"exitCode":0}')
        compilation = area/'compile.json'
        compilation.write_text(json.dumps({'native':self.pin(parent), 'execution':self.pin(execution)}))
        top['compile'] = self.pin(compilation)
        top['resources'] = {}
        for name in ('pfh0.mdl','srn_fa_h0.mdl'):
            path = area/name; path.write_bytes(b'exact two-resource source '+name.encode())
            top['resources'][name] = self.pin(path)
        receipt = area/'overlay.json'; receipt.write_text(json.dumps(top))
        self.build['animationOverlay'] = self.pin(receipt)
        self.write_build()
        return area, parent, execution, receipt

    def test_executed_overlay_direct_pins_and_compiler_execution_are_declared_without_historical_scans(self):
        area, parent, execution, receipt = self.overlay_inputs()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        declared = set(json.loads(self.launches()[0].read_text())['frozenInputs'])
        self.assertTrue({str(path.resolve()) for path in area.iterdir()} <= declared)
        self.assertIn(str(parent.resolve()), declared)
        self.assertIn(str(execution.resolve()), declared)
        self.assertIn(str(receipt.resolve()), declared)
        self.assertNotIn(str(self.root/'unread cold backup.bin'), declared)

    def test_overlay_source_parent_and_execution_staleness_prevent_dispatch(self):
        area, parent, execution, receipt = self.overlay_inputs()
        for path in (receipt, area/'sourceRoot.json', area/'srn_fa_h0.mdl', parent, execution):
            with self.subTest(path=path):
                original = path.read_bytes(); path.write_bytes(b'stale overlay input')
                result = self.run_guard(); path.write_bytes(original)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Declared consumed input changed', result.stderr)
                self.assertFalse((self.fixture/'dispatch.json').exists())
        self.assertFalse(self.launches())

    def test_missing_required_inputs_prevent_dispatch(self):
        for key in ('TargetContract','WorkspacePython','Client','Toolchain','MigrationReceipt'):
            with self.subTest(key=key):
                result = self.run_guard(omit=key)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(key, result.stderr)
                self.assertFalse((self.fixture/'dispatch.json').exists())

    def test_rejected_preflight_prevents_launch_even_when_launch_requested(self):
        (self.fixture/'reject-preflight').touch()
        result = self.run_guard(no_launch=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('preflight failed', result.stderr)
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_cross_target_wrong_module_incomplete_proof_and_changed_client_fail_closed(self):
        for flag in ('wrong-module','cross-target','incomplete','changed-client'):
            with self.subTest(flag=flag):
                path = self.fixture/flag
                path.touch(); result = self.run_guard(); path.unlink()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(list(self.fixture.glob('client-launch-*.json')))


if __name__ == '__main__': unittest.main()
