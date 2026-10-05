"""Exercise launcher dispatch without starting NWN or using real fixture assets.

Set PHENOTYPE_TEST_PWSH to your PowerShell executable if pwsh is not on PATH.
The preflight stub tests orchestration only; real resource audits remain separate.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PWSH = os.environ.get('PHENOTYPE_TEST_PWSH') or shutil.which('pwsh')


@unittest.skipUnless(PWSH, 'PowerShell is needed for client launcher integration tests')
class CompleteBodyLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='body launcher ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.launcher = self.root / 'tools/phenotypes/Launch-CompleteBodyClient.ps1'
        self.launcher.parent.mkdir(parents=True)
        shutil.copyfile(Path(__file__).with_name(self.launcher.name), self.launcher)
        shutil.copyfile(Path(__file__).resolve().parents[1]/'SrnTools.psm1',self.root/'tools/SrnTools.psm1')
        self.fixture = self.root / 'fixture with spaces'
        self.fixture.mkdir()
        # This non-executable file deliberately cannot be launched as a game.
        self.client = self.root / 'not a real client.exe'
        self.client.write_text('No game process may start in this test.')
        self.launcher.with_name('preflight_complete_body_client.py').write_text('''
import argparse, json, sys
from pathlib import Path
p = argparse.ArgumentParser()
for key in ('fixture', 'receipt-sha256', 'client', 'output'):
    p.add_argument('--' + key, required=True)
a = p.parse_args()
fixture = Path(a.fixture)
(fixture / 'dispatch.json').write_text(json.dumps({
    'python': sys.executable, 'fixture': a.fixture,
    'receiptSha256': a.receipt_sha256, 'client': a.client}))
if (fixture / 'reject-preflight').exists():
    sys.exit(7)
Path(a.output).write_text(json.dumps({
    'pass': True, 'completeBodySelected': True,
    'userDirectory': str(fixture / 'userdir'), 'clientLaunched': False}))
''')

    def run_launcher(self, *, python=True, client=True, interpreter=None):
        args = [str(PWSH), '-NoProfile', '-NonInteractive', '-File', str(self.launcher),
                '-Fixture', str(self.fixture), '-ReceiptSha256', 'a' * 64, '-NoLaunch']
        if python:
            args += ['-WorkspacePython', str(interpreter or sys.executable)]
        if client:
            args += ['-Client', str(self.client)]
        return subprocess.run(args, capture_output=True, text=True, timeout=30)

    def test_explicit_interpreter_and_paths_reach_preflight_without_launch(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        dispatch = json.loads((self.fixture / 'dispatch.json').read_text())
        self.assertEqual(Path(dispatch['python']).resolve(), Path(sys.executable).resolve())
        self.assertEqual(Path(dispatch['fixture']).resolve(), self.fixture.resolve())
        self.assertEqual(dispatch['receiptSha256'], 'a' * 64)
        self.assertEqual(Path(dispatch['client']).resolve(), self.client.resolve())
        proof = json.loads(result.stdout)
        self.assertTrue(proof['pass'])
        self.assertFalse(proof['clientLaunched'])
        self.assertEqual(len(list(self.fixture.glob('client-preflight-*.json'))), 1)
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_missing_interpreter_fails_before_dispatch(self):
        result = self.run_launcher(python=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WorkspacePython', result.stderr)
        self.assertFalse((self.fixture / 'dispatch.json').exists())

    def test_missing_client_fails_before_dispatch(self):
        result = self.run_launcher(client=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Client', result.stderr)
        self.assertFalse((self.fixture / 'dispatch.json').exists())

    def test_nonexistent_interpreter_fails_before_dispatch(self):
        result = self.run_launcher(interpreter=self.root / 'missing python.exe')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('WorkspacePython', result.stderr)
        self.assertFalse((self.fixture / 'dispatch.json').exists())

    def test_failed_preflight_produces_no_launch_receipt(self):
        (self.fixture / 'reject-preflight').touch()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Complete-body client preflight failed', result.stderr)
        self.assertTrue((self.fixture / 'dispatch.json').exists())
        self.assertFalse(list(self.fixture.glob('client-launch-*.json')))

    def test_store_shim_is_rejected_before_preflight(self):
        shim=self.root/'WindowsApps/python.exe';shim.parent.mkdir();shim.write_bytes(b'non-executable shim fixture')
        result=self.run_launcher(interpreter=shim)
        self.assertNotEqual(result.returncode,0);self.assertIn('Store Python shim',result.stderr)
        self.assertFalse((self.fixture/'dispatch.json').exists())


if __name__ == '__main__':
    unittest.main()
