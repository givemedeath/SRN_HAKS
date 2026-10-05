"""Creation-helper provenance cannot substitute geometry or foreign files."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bind_shared_runtimes as binder
import historical_helper_bindings as bindings
import launch_shared_tool as launcher


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class HistoricalHelperBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'consumer'
        self.helpers = self.repo / 'tools' / 'phenotypes'
        self.helpers.mkdir(parents=True)
        self.history = self.repo / '.tmp' / 'creation-helper-snapshots'
        self.history.mkdir(parents=True)
        self.source = self.helpers / 'target_contract.py'
        self.source.write_bytes(b'# current infrastructure helper\n')
        self.snapshot = self.history / 'target_contract.py'
        # Validating this snapshot must not execute its bytes.
        self.snapshot.write_bytes(b'raise RuntimeError("Historical helper must never execute")\n')
        self.expected = sha(self.snapshot)
        self.contract = self.repo / '.tmp' / 'target-contract.json'
        self.contract.write_text('{"targetRevision":"frozen-troll"}\n', encoding='utf-8')
        self.manifest_path = self.repo / '.tmp' / 'historical-bindings.json'
        self.manifest = {
            'schemaVersion': 1,
            'kind': 'historical-creation-helper-bindings',
            'activeWorktree': str(self.repo),
            'targetContract': {'path': str(self.contract), 'sha256': sha(self.contract)},
            'entries': [{'source': {'path': str(self.source), 'sha256': self.expected},
                         'snapshot': {'path': str(self.snapshot), 'sha256': self.expected}}],
        }
        self.save()
        self.module = patch.object(bindings, '__file__', str(self.helpers / 'historical_helper_bindings.py'))
        self.module.start()
        self.addCleanup(self.module.stop)

    def save(self):
        self.manifest_path.write_text(json.dumps(self.manifest) + '\n', encoding='utf-8')
        self.pin = {'path': str(self.manifest_path), 'sha256': sha(self.manifest_path)}

    def environment(self):
        return patch.dict(os.environ, {
            bindings.ENV_PATH: str(self.manifest_path),
            bindings.ENV_SHA256: self.pin['sha256'],
        })

    def test_matching_original_uses_original_without_historical_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(bindings.resolve(self.source, sha(self.source)), self.source.resolve())

    def test_changed_original_requires_explicit_environment_and_exact_mapping(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'explicit historical'):
                bindings.resolve(self.source, self.expected)
        for missing in (bindings.ENV_PATH, bindings.ENV_SHA256):
            with self.environment():
                os.environ.pop(missing)
                with self.assertRaisesRegex(ValueError, 'explicit historical'):
                    bindings.resolve(self.source, self.expected)

    def test_historical_snapshot_and_consumed_files_are_verified_without_execution(self):
        before = {path: path.read_bytes() for path in (self.source, self.snapshot, self.contract, self.manifest_path)}
        manifest, paths = bindings.validate_manifest(self.pin, self.repo)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(set(paths), {self.manifest_path.resolve(), self.contract.resolve(), self.snapshot.resolve()})
        with self.environment():
            self.assertEqual(bindings.resolve(self.source, self.expected), self.snapshot.resolve())
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_corrupted_snapshot_rejected(self):
        self.snapshot.write_bytes(b'corrupted old helper')
        with self.environment(), self.assertRaisesRegex(ValueError, 'snapshot changed'):
            bindings.resolve(self.source, self.expected)

    def test_stale_manifest_and_contract_rejected(self):
        original = self.manifest_path.read_bytes()
        self.manifest_path.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            bindings.validate_manifest(self.pin, self.repo)
        self.manifest_path.write_bytes(original)
        self.contract.write_bytes(b'{"targetRevision":"different"}')
        with self.assertRaisesRegex(ValueError, 'target contract changed'):
            bindings.validate_manifest(self.pin, self.repo)

    def test_geometry_models_maps_and_configuration_cannot_be_mapped(self):
        original = dict(self.manifest['entries'][0]['source'])
        for extension in ('.glb', '.mdl', '.json', '.png', '.mtr'):
            with self.subTest(extension=extension):
                forged = self.helpers / ('geometry' + extension)
                forged.write_bytes(self.snapshot.read_bytes())
                self.manifest['entries'][0]['source'] = {'path': str(forged), 'sha256': self.expected}
                self.save()
                with self.assertRaisesRegex(ValueError, 'phenotype Python helper'):
                    bindings.validate_manifest(self.pin, self.repo)
        self.manifest['entries'][0]['source'] = original

    def test_wrong_worktree_and_foreign_source_rejected(self):
        self.manifest['activeWorktree'] = str(self.base / 'other')
        self.save()
        with self.assertRaisesRegex(ValueError, 'another worktree'):
            bindings.validate_manifest(self.pin, self.repo)
        self.manifest['activeWorktree'] = str(self.repo)
        other = self.base / 'other' / 'tools' / 'phenotypes'
        other.mkdir(parents=True)
        source = other / 'target_contract.py'
        source.write_bytes(self.source.read_bytes())
        self.manifest['entries'][0]['source']['path'] = str(source)
        self.save()
        with self.assertRaisesRegex(ValueError, 'consuming-worktree phenotype'):
            bindings.validate_manifest(self.pin, self.repo)

    def test_snapshot_escape_or_nonhelper_extension_rejected(self):
        for path in (self.base / 'outside.py', self.history / 'model.mdl'):
            with self.subTest(path=str(path)):
                path.write_bytes(self.snapshot.read_bytes())
                self.manifest['entries'][0]['snapshot']['path'] = str(path)
                self.save()
                with self.assertRaisesRegex(ValueError, 'snapshot escaped'):
                    bindings.validate_manifest(self.pin, self.repo)

    def test_manifest_and_contract_escape_rejected(self):
        outside = self.base / 'outside.json'
        outside.write_bytes(self.manifest_path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'manifest escaped'):
            bindings.validate_manifest({'path': str(outside), 'sha256': sha(outside)}, self.repo)
        outside.write_bytes(self.contract.read_bytes())
        self.manifest['targetContract'] = {'path': str(outside), 'sha256': sha(outside)}
        self.save()
        with self.assertRaisesRegex(ValueError, 'target contract escaped'):
            bindings.validate_manifest(self.pin, self.repo)

    def test_different_hash_or_missing_mapping_rejected(self):
        with self.environment(), self.assertRaisesRegex(ValueError, 'No exact historical'):
            bindings.resolve(self.source, '0' * 64)
        unmapped = self.helpers / 'another_helper.py'
        unmapped.write_bytes(self.source.read_bytes())
        with self.environment(), self.assertRaisesRegex(ValueError, 'No exact historical'):
            bindings.resolve(unmapped, self.expected)

    def test_source_snapshot_hash_mismatch_and_duplicate_mapping_rejected(self):
        self.manifest['entries'][0]['source']['sha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, 'hashes differ'):
            bindings.validate_manifest(self.pin, self.repo)
        self.manifest['entries'][0]['source']['sha256'] = self.expected
        self.manifest['entries'].append(self.manifest['entries'][0])
        self.save()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            bindings.validate_manifest(self.pin, self.repo)

    def launch(self, *, historical=True, subprocess_effect=None):
        for name in ('launch_shared_tool.py', 'shared_toolchain.py', 'historical_helper_bindings.py'):
            (self.helpers / name).write_bytes(b'# current launcher helper snapshot\n')
        (self.repo / 'tools' / 'shared_tools.py').write_bytes(b'# current durable resolver\n')
        (self.repo / 'tools' / 'shared-tools.lock.json').write_bytes(b'{}\n')
        config = self.repo / '.tmp' / 'runtime-binding.json'
        config.write_bytes(b'{"kind":"test-binding"}\n')
        executable = self.repo / '.tmp' / 'bundled-python.exe'
        executable.write_bytes(b'mocked executable, never launched')
        data = {'schemaVersion': 2, 'toolsRoot': str(self.repo / '.tools'), 'addons': None,
                'tools': {'python': {'path': str(executable), 'sha256': sha(executable)}}}
        if historical:
            data['historicalHelperBindings'] = self.pin
        output = self.repo / '.tmp' / 'mocked-launch'
        argv = ['launcher', '--toolchain', str(config), '--migration-smoke', '--tool', 'python',
                '--output', str(output), '--', '-c', 'pass']
        effect = subprocess_effect or (lambda *args, **kwargs: SimpleNamespace(returncode=0))
        with patch.object(launcher, '__file__', str(self.helpers / 'launch_shared_tool.py')), \
                patch.object(launcher, 'load', return_value=data), \
                patch.object(launcher, 'register_run', return_value=self.repo / '.tmp' / 'dependency.json'), \
                patch.object(launcher, 'tools_root', return_value=(self.repo / '.tools', 'explicit')), \
                patch.object(launcher.subprocess, 'run', side_effect=effect) as process, \
                patch.object(sys, 'argv', argv), patch('builtins.print'), \
                self.environment():
            with self.assertRaises(SystemExit) as result:
                launcher.main()
            return result.exception.code, json.loads((output / 'launch.json').read_text(encoding='utf-8')), process

    def test_launcher_freezes_historical_inputs_and_sets_explicit_environment(self):
        code, receipt, process = self.launch()
        self.assertEqual(code, 0)
        self.assertTrue(receipt['inputsUnchanged'])
        self.assertEqual(receipt['historicalHelperBindings'], self.pin)
        environment = process.call_args.kwargs['env']
        self.assertEqual(environment[bindings.ENV_PATH], str(self.manifest_path.resolve()))
        self.assertEqual(environment[bindings.ENV_SHA256], self.pin['sha256'])
        for path in (self.manifest_path, self.contract, self.snapshot,
                     self.source, self.helpers / 'historical_helper_bindings.py'):
            self.assertEqual(receipt['frozenInputs'][str(path.resolve())], sha(path))
        self.assertEqual(receipt['helperSnapshots'][str(self.snapshot)]['sha256'], self.expected)
        self.assertEqual(receipt['helperSnapshots'][str(self.source)]['sha256'], sha(self.source))

    def test_launcher_clears_inherited_historical_environment_when_unbound(self):
        code, receipt, process = self.launch(historical=False)
        self.assertEqual(code, 0)
        self.assertIsNone(receipt['historicalHelperBindings'])
        self.assertNotIn(bindings.ENV_PATH, process.call_args.kwargs['env'])
        self.assertNotIn(bindings.ENV_SHA256, process.call_args.kwargs['env'])
        self.assertNotIn(str(self.snapshot.resolve()), receipt['frozenInputs'])

    def test_launcher_preserves_failed_receipt_when_snapshot_changes_during_run(self):
        def change(*args, **kwargs):
            self.snapshot.write_bytes(b'changed during subprocess')
            return SimpleNamespace(returncode=0)
        code, receipt, _ = self.launch(subprocess_effect=change)
        self.assertEqual(code, 1)
        self.assertFalse(receipt['inputsUnchanged'])
        self.assertIn('snapshot changed', receipt['verificationError'])
        self.assertEqual(receipt['frozenInputs'][str(self.snapshot.resolve())], self.expected)

    def test_binder_creates_fresh_manifest_pin_without_rewriting_manifest(self):
        before = self.manifest_path.read_bytes()
        output = self.repo / '.tmp' / 'fresh-runtime-binding.json'
        argv = ['binder', '--python', str(self.source), '--historical-helper-bindings',
                str(self.manifest_path), '--output', str(output)]
        with patch.object(binder, '__file__', str(self.helpers / 'bind_shared_runtimes.py')), \
                patch.object(binder, 'tools_root', return_value=(self.repo / '.tools', 'explicit')), \
                patch.object(binder, 'resolve_runtime', return_value={'path': str(self.source), 'sha256': sha(self.source)}), \
                patch.object(sys, 'argv', argv):
            binder.main()
        result = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(result['historicalHelperBindings'], self.pin)
        self.assertEqual(before, self.manifest_path.read_bytes())


if __name__ == '__main__':
    unittest.main()
