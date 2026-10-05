"""Migration evidence drift, cross-configuration reuse and history guards."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from finalize_shared_tool_migration import finalize, verify_launch
from shared_toolchain import sha


class MigrationEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.config = self.root / 'toolchain.json'; self.config.write_text('{}')
        executable = self.root / 'python.exe'; executable.write_bytes(b'pinned test executable')
        helper = self.root / 'launcher.py'; helper.write_bytes(b'pinned test helper')
        self.helper = helper
        self.toolchain = {'tools': {'python': {'path': str(executable), 'sha256': sha(executable)}}}
        self.folder = self.root / 'smoke'; self.folder.mkdir()
        (self.folder / 'stdout.log').write_bytes(b'fresh execution output')
        (self.folder / 'stderr.log').write_bytes(b'')
        self.report = {'kind': 'verified-shared-tool-launch', 'tool': 'python', 'exitCode': 0,
            'preMigrationSmoke': True, 'migrationReceipt': None, 'toolchain': str(self.config),
            'toolchainSha256': sha(self.config), 'toolBinary': self.toolchain['tools']['python'],
            'command': [str(executable), '--version'],
            'frozenInputs': {str(self.config): sha(self.config), str(helper): sha(helper)},
            'helperSnapshots': {}, 'stdoutSha256': sha(self.folder / 'stdout.log'),
            'stderrSha256': sha(self.folder / 'stderr.log')}
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        (self.folder / 'launch.json').write_text(json.dumps(self.report))

    def verify(self):
        return verify_launch(self.folder, 'python', self.config, self.toolchain)

    def test_accepts_current_hash_bound_evidence(self):
        self.assertEqual(self.verify(), self.report)
        self.assertEqual(verify_launch(self.folder,'python',self.folder/'..'/'toolchain.json',self.toolchain),self.report)

    def test_changed_execution_logs_and_helper_are_rejected(self):
        (self.folder / 'stdout.log').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'logs changed'): self.verify()
        (self.folder / 'stdout.log').write_bytes(b'fresh execution output')
        self.helper.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'input changed'): self.verify()

    def test_failed_or_previously_migrated_launch_cannot_stamp_migration(self):
        for field, value, reason in [('exitCode', 1, 'successful'),
            ('preMigrationSmoke', False, 'pre-migration'), ('migrationReceipt', 'old-migration.json', 'pre-migration')]:
            original = copy.deepcopy(self.report); self.report[field] = value; self.save()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason): self.verify()
            self.report = original

    def test_same_bytes_at_another_configuration_path_are_rejected(self):
        other = self.root / 'other.json'; other.write_bytes(self.config.read_bytes())
        self.report['toolchain'] = str(other); self.save()
        with self.assertRaisesRegex(ValueError, 'another toolchain'): self.verify()

    def test_command_executable_and_binary_metadata_must_agree(self):
        self.report['command'][0] = str(self.root / 'other-python.exe'); self.save()
        with self.assertRaisesRegex(ValueError, 'executable differs'): self.verify()

    def test_existing_migration_is_preserved_before_any_other_work(self):
        output = self.root / 'migration.json'; output.write_bytes(b'preserved history')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            finalize(self.config, self.root / 'missing-smokes', output)
        self.assertEqual(output.read_bytes(), b'preserved history')


if __name__ == '__main__': unittest.main()
