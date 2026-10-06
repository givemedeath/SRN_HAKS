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
    def test_manifest_pins_and_path_lists_retain_drift_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);config=root/'binding.json';input=root/'input.txt';input.write_text('parent')
            write_json(config,{'schemaVersion':2,'kind':'phenotype-shared-toolchain','runtimes':{'python':{'path':sys.executable,'sha256':sha(sys.executable)}},'requiredTools':['python']},fresh=True)
            launcher=Path(__file__).with_name('launch_shared_tool.py')
            manifest=root/'pins.json';write_json(manifest,[{'path':str(input),'sha256':sha(input)}],fresh=True)
            paths=root/'paths.json';write_json(paths,[str(input)],fresh=True)
            for name,option,declaration,code,expected in [
                ('pinned','--input-manifest',manifest,'print("ok")',0),
                ('path-drift','--input-path-list',paths,'from pathlib import Path;Path('+repr(str(input))+').write_text("changed")',1),
                ('stale','--input-manifest',manifest,'print("must not run")',1)]:
                output=root/name
                result=subprocess.run([sys.executable,'-B',str(launcher),'--toolchain',str(config),'--migration-smoke','--tool','python','--output',str(output),option,str(declaration),'--','-c',code],capture_output=True)
                self.assertEqual(result.returncode,expected,result.stderr.decode('utf-8'))
                if name=='stale':
                    self.assertFalse((output/'stdout.log').exists());self.assertIn('Manifest input changed',result.stderr.decode('utf-8'))
                else:
                    receipt=json.loads((output/'launch.json').read_text());self.assertEqual(receipt['inputsUnchanged'],expected==0)
                    self.assertIn(str(input.resolve()),receipt['frozenInputs'])
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

if __name__=='__main__':unittest.main()
