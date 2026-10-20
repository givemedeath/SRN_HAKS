"""Focused regressions for the adapter's loaded-Comfy source identity guard."""
import ast
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from headkit.comfy_nodes.runtime_identity import same_runtime_environment, seal_runtime_identity
from headkit.comfy_nodes.source_snapshot import capture_inventory, loaded_source_code, verify_inventory


class ComfyRuntimeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.core = Path(self.temp.name) / 'comfy'
        for relative in ('main.py','execution.py','nodes.py','server.py','folder_paths.py',
                         'comfy/model.py','comfy_extras/nodes_trellis2.py',
                         'custom_nodes/plugin/flexgemm.py','custom_nodes/plugin/kernel.pyd'):
            path = self.core / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# pinned fixture\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_startup_snapshot_detects_changed_then_restored_source(self):
        inventory = capture_inventory(self.core, [self.core])
        path = self.core / 'nodes.py'
        reviewed = path.read_bytes()
        path.write_text('# temporary implementation\n', encoding='utf-8')
        startup = capture_inventory(self.core, [self.core])
        path.write_bytes(reviewed)
        with self.assertRaisesRegex(ValueError, 'startup snapshot'):
            verify_inventory(startup)
        self.assertNotEqual(inventory['files'], startup['files'])

    def test_loaded_stale_function_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value():\n    return "reviewed"\n'
        path.write_text('def loaded_value():\n    return "temporary"\n', encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_fixture')
        module.__file__ = str(path)
        exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy Python code differs'):
                loaded_source_code([self.core])

    def test_runtime_endpoint_returns_the_live_loaded_code_identity(self):
        source = Path(__file__).parent / 'comfy_nodes' / '__init__.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        handler = next(node for node in ast.walk(tree)
                       if isinstance(node, ast.AsyncFunctionDef)
                       and node.name == 'verify_headkit_runtime_identity')
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == 'loaded_source_code' for node in ast.walk(handler)))
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == 'capture_runtime_identity' and len(node.args) == 3
                            and isinstance(node.args[2], ast.Name) and node.args[2].id == 'loaded'
                            for node in ast.walk(handler)))
        self.assertTrue(any(isinstance(node, ast.Return) and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Attribute)
                            and node.value.func.attr == 'json_response'
                            and len(node.value.args) == 1
                            and isinstance(node.value.args[0], ast.Name)
                            and node.value.args[0].id == 'current'
                            for node in ast.walk(handler)))

    def test_loaded_code_affects_identity_but_not_stable_runtime_comparison(self):
        baseline = seal_runtime_identity({'schemaVersion': 2, 'python': {'version': 'pinned'},
            'files': [{'path': '/runtime/python.exe', 'sha256': 'a' * 64}],
            'loadedSourceCode': [{'path': '/comfy/core.py', 'sourceSha256': 'b' * 64,
                                  'loadedCodeSha256': 'c' * 64}]})
        current = seal_runtime_identity({'schemaVersion': 2, 'python': {'version': 'pinned'},
            'files': [{'path': '/runtime/python.exe', 'sha256': 'a' * 64}],
            'loadedSourceCode': [{'path': '/comfy/core.py', 'sourceSha256': 'b' * 64,
                                  'loadedCodeSha256': 'd' * 64}]})
        changed_runtime = seal_runtime_identity({'schemaVersion': 2, 'python': {'version': 'changed'},
            'files': [{'path': '/runtime/python.exe', 'sha256': 'a' * 64}],
            'loadedSourceCode': [{'path': '/comfy/core.py', 'sourceSha256': 'b' * 64,
                                  'loadedCodeSha256': 'd' * 64}]})
        self.assertNotEqual(baseline['fingerprint'], current['fingerprint'])
        self.assertTrue(same_runtime_environment(current, baseline))
        self.assertFalse(same_runtime_environment(changed_runtime, baseline))


if __name__ == '__main__':
    unittest.main()
