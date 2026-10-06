"""Real narrow Python launches: no Blender dependency and mutation evidence retained."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from shared_toolchain import sha
from shared_tools import write_json

class LaunchTests(unittest.TestCase):
    def test_operation_specific_resolution_unicode_and_midrun_input_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'binding.json'
            write_json(config,{'schemaVersion':2,'kind':'phenotype-shared-toolchain',
                'runtimes':{'python':{'path':sys.executable,'sha256':sha(sys.executable)}},
                'requiredTools':['python']},fresh=True)
            input=root/'input.txt';input.write_text('parent',encoding='utf-8')
            launcher=Path(__file__).with_name('launch_shared_tool.py')
            for name,code,expected in [('unicode',"print('继续 — résumé')",0),
                ('drift','from pathlib import Path;Path('+repr(str(input))+').write_text("changed",encoding="utf-8")',1)]:
                output=root/name
                result=subprocess.run([sys.executable,'-B',str(launcher),'--toolchain',str(config),
                    '--migration-smoke','--tool','python','--output',str(output),'--input',str(input),'--','-c',code],capture_output=True)
                self.assertEqual(result.returncode,expected,result.stderr.decode('utf-8'))
                receipt=json.loads((output/'launch.json').read_text(encoding='utf-8'))
                self.assertEqual(receipt['inputsUnchanged'],expected==0)
                self.assertTrue(receipt['inventorySha256']);self.assertFalse(receipt['gameClientTesting'])
                if name=='unicode':self.assertIn('继续',(output/'stdout.log').read_text(encoding='utf-8'))
                else:self.assertIn('changed',receipt['verificationError'])

    def test_input_tree_freezes_nested_models_receipts_and_membership(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'binding.json'
            write_json(config, {'schemaVersion': 2, 'kind': 'phenotype-shared-toolchain',
                'runtimes': {'python': {'path': sys.executable, 'sha256': sha(sys.executable)}},
                'requiredTools': ['python']}, fresh=True)
            consumed = root / 'converted'
            (consumed / 'resources').mkdir(parents=True)
            model = consumed / 'resources/body.mdl'
            model.write_bytes(b'compiled model')
            receipt_file = consumed / 'native-compile.json'
            receipt_file.write_text('{}')
            launcher = Path(__file__).with_name('launch_shared_tool.py')
            mutations = [('unchanged', 'pass', 0),
                ('model', 'from pathlib import Path;Path(' + repr(str(model)) + ').write_bytes(b"drift")', 1),
                ('receipt', 'from pathlib import Path;Path(' + repr(str(receipt_file)) + ').write_text("changed")', 1),
                ('added', 'from pathlib import Path;Path(' + repr(str(consumed / 'resources/extra.mdl')) + ').write_bytes(b"extra")', 1)]
            for name, code, expected in mutations:
                with self.subTest(name=name):
                    output = root / name
                    result = subprocess.run([sys.executable, '-B', str(launcher), '--toolchain', str(config),
                        '--migration-smoke', '--tool', 'python', '--output', str(output), '--input-tree', str(consumed), '--', '-c', code], capture_output=True)
                    self.assertEqual(result.returncode, expected, result.stderr.decode('utf-8'))
                    receipt = json.loads((output / 'launch.json').read_text(encoding='utf-8'))
                    self.assertIn(str(model.resolve()), receipt['frozenInputs'])
                    self.assertIn(str(receipt_file.resolve()), receipt['frozenInputs'])
                    self.assertEqual(receipt['inputsUnchanged'], expected == 0)
                    if name == 'added':
                        self.assertIn('membership changed', receipt['verificationError'])

if __name__=='__main__':unittest.main()
