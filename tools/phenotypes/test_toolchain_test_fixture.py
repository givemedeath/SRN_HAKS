"""Standalone tests retain real byte guards and explicit unexecuted scope."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from shared_toolchain import load, sha
from toolchain_test_fixture import bindings

UNBOUND={'SRN_SHARED_TOOLCHAIN':'','SRN_SHARED_TOOL_MIGRATION':''}


class ToolchainTestFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_standalone_fixture_is_verified_and_explicitly_unexecuted(self):
        with patch.dict(os.environ,UNBOUND):toolchain,migration=bindings(self.root)
        data=load(toolchain,migration)
        self.assertEqual(set(data['tools']),{'python'})
        self.assertEqual(data['fixtureScope'],'synthetic-unexecuted-unit-test-only')
        self.assertFalse(data['runtimeExecutionAllowed'])
        proof=json.loads(migration.read_text(encoding='utf-8'))
        self.assertFalse(proof['smokeChecksActuallyExecuted'])
        self.assertFalse(proof['productionMigrationEvidence'])
        self.assertFalse(proof['runtimeExecutionAllowed'])
        declaration=json.loads((self.root/'test-fixture-runtime-inputs.json').read_text(encoding='utf-8'))
        self.assertEqual(declaration['inputs'],[{'path':str(path),'sha256':sha(path)} for path in (toolchain,migration)])

    def test_launcher_bindings_are_used_exactly_without_synthetic_fallback(self):
        source=self.root/'source';source.mkdir()
        with patch.dict(os.environ,UNBOUND):toolchain,migration=bindings(source)
        destination=self.root/'bound';destination.mkdir()
        with patch.dict(os.environ,{'SRN_SHARED_TOOLCHAIN':str(toolchain),
                                   'SRN_SHARED_TOOL_MIGRATION':str(migration)}):
            self.assertEqual(bindings(destination),(toolchain,migration))
        self.assertFalse((destination/'unexecuted-toolchain-test-fixture').exists())
        record=json.loads((destination/'test-fixture-runtime-inputs.json').read_text(encoding='utf-8'))
        self.assertEqual(record['scope'],'current-launcher-bound-runtimes')

    def test_supplied_runtime_drift_rejected_by_production_guard(self):
        source=self.root/'source';source.mkdir()
        with patch.dict(os.environ,UNBOUND):toolchain,migration=bindings(source)
        data=json.loads(toolchain.read_text(encoding='utf-8'))
        Path(data['runtimes']['python']['path']).write_bytes(b'changed runtime')
        destination=self.root/'bound';destination.mkdir()
        with patch.dict(os.environ,{'SRN_SHARED_TOOLCHAIN':str(toolchain),
                                   'SRN_SHARED_TOOL_MIGRATION':str(migration)}), \
                self.assertRaisesRegex(ValueError,'runtime changed'):
            bindings(destination)
        self.assertFalse((destination/'unexecuted-toolchain-test-fixture').exists())

    def test_partial_launcher_environment_rejected(self):
        for field in ('SRN_SHARED_TOOLCHAIN','SRN_SHARED_TOOL_MIGRATION'):
            with self.subTest(field=field),patch.dict(os.environ,{**UNBOUND,field:'missing.json'}), \
                    self.assertRaisesRegex(ValueError,'both current launcher'):
                bindings(self.root)


if __name__=='__main__':unittest.main()
