"""Long file declarations retain exact pre/post-dispatch evidence checks."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_shared_tool as launcher


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LaunchInputManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.repo=Path(self.tmp.name)/'consumer'
        self.helpers=self.repo/'tools'/'phenotypes';self.helpers.mkdir(parents=True)
        self.local=self.repo/'.tmp';self.local.mkdir()
        for name in ('launch_shared_tool.py','shared_toolchain.py','historical_helper_bindings.py'):
            (self.helpers/name).write_bytes(b'# frozen current helper\n')
        (self.repo/'tools'/'shared_tools.py').write_bytes(b'# durable resolver\n')
        (self.repo/'tools'/'shared-tools.lock.json').write_bytes(b'{}\n')
        self.config=self.local/'runtime-bindings.json';self.config.write_bytes(b'{}\n')
        self.executable=self.local/'python.exe';self.executable.write_bytes(b'mocked, never launched')
        self.input=self.local/'actual-source.dat';self.input.write_bytes(b'unchanged source bytes')
        self.explicit=self.local/'explicit-input.json';self.explicit.write_bytes(b'{"explicit":true}\n')
        self.manifest=self.local/'launch-inputs.json'
        self.report={'schemaVersion':1,'kind':'shared-launch-inputs',
                     'inputs':[{'path':str(self.input),'sha256':sha(self.input)}]}
        self.save();self.sequence=0

    def save(self):
        self.manifest.write_text(json.dumps(self.report)+'\n',encoding='utf-8')

    def run_launch(self, *, effect=None, manifests=None):
        self.sequence+=1;output=self.local/('launch-'+str(self.sequence))
        argv=['launcher','--toolchain',str(self.config),'--migration-smoke','--tool','python',
              '--output',str(output),'--input',str(self.explicit)]
        for path in manifests or [self.manifest]:argv+=['--input-manifest',str(path)]
        argv+=['--','-c','pass']
        data={'schemaVersion':2,'toolsRoot':str(self.repo/'.tools'),'addons':None,
              'tools':{'python':{'path':str(self.executable),'sha256':sha(self.executable)}}}
        with patch.object(launcher,'__file__',str(self.helpers/'launch_shared_tool.py')), \
                patch.object(launcher,'load',return_value=data), \
                patch.object(launcher,'register_run',return_value=self.local/'dependency.json'), \
                patch.object(launcher,'tools_root',return_value=(self.repo/'.tools','explicit')), \
                patch.object(launcher.subprocess,'run',side_effect=effect or
                             (lambda *args,**kwargs:SimpleNamespace(returncode=0))) as process, \
                patch.object(sys,'argv',argv),patch('builtins.print'):
            try:
                launcher.main()
            except SystemExit as result:
                return result.code,json.loads((output/'launch.json').read_text(encoding='utf-8')),process
            except ValueError:
                self.assertFalse(process.called,'Invalid declaration must fail before subprocess dispatch')
                self.assertFalse((output/'launch.json').exists())
                raise
        self.fail('Launcher must return through its recorded exit status')

    def test_unchanged_explicit_list_and_repeatable_manifests_are_frozen(self):
        extra=self.local/'second-input.dat';extra.write_bytes(b'additional exact source')
        second=self.local/'second-manifest.json'
        second.write_text(json.dumps({'schemaVersion':1,'kind':'shared-launch-inputs',
            'inputs':[{'path':str(self.input),'sha256':sha(self.input)},
                      {'path':str(extra),'sha256':sha(extra)}]})+'\n',encoding='utf-8')
        code,receipt,process=self.run_launch(manifests=[self.manifest,second])
        self.assertEqual(code,0);self.assertTrue(receipt['inputsUnchanged'])
        self.assertEqual(len(receipt['inputManifests']),2)
        for path in (self.manifest,second,self.input,extra,self.explicit):
            self.assertEqual(receipt['frozenInputs'][str(path.resolve())],sha(path))
        self.assertNotIn('--input-manifest',process.call_args.args[0])
        self.assertEqual(process.call_args.args[0][-2:],['-c','pass'])

    def test_stale_actual_file_pin_rejected_before_dispatch(self):
        self.input.write_bytes(b'changed since declaration')
        with self.assertRaisesRegex(ValueError,'Declared launch input changed'):
            self.run_launch()

    def test_manifest_changed_midrun_retains_failed_receipt_and_initial_hash(self):
        before=sha(self.manifest)
        def change(*args,**kwargs):
            self.manifest.write_bytes(self.manifest.read_bytes()+b' ')
            return SimpleNamespace(returncode=0)
        code,receipt,_=self.run_launch(effect=change)
        self.assertEqual(code,1);self.assertFalse(receipt['inputsUnchanged'])
        self.assertIn('changed during execution',receipt['verificationError'])
        self.assertEqual(receipt['inputManifests'][0]['sha256'],before)
        self.assertEqual(receipt['frozenInputs'][str(self.manifest.resolve())],before)

    def test_input_changed_midrun_retains_failed_receipt_and_initial_hash(self):
        before=sha(self.input)
        def change(*args,**kwargs):
            self.input.write_bytes(b'changed by mocked subprocess')
            return SimpleNamespace(returncode=0)
        code,receipt,_=self.run_launch(effect=change)
        self.assertEqual(code,1);self.assertFalse(receipt['inputsUnchanged'])
        self.assertIn('changed during execution',receipt['verificationError'])
        self.assertEqual(receipt['frozenInputs'][str(self.input.resolve())],before)

    def test_directories_unhashed_rows_relative_paths_and_wrong_schema_rejected(self):
        rows=[{'path':str(self.local),'sha256':'0'*64},
              {'path':str(self.input)},
              {'path':'relative.dat','sha256':'0'*64}]
        for row in rows:
            with self.subTest(row=row):
                self.report['inputs']=[row];self.save()
                with self.assertRaises(ValueError):launcher.read_input_manifest(self.manifest)
        self.report['inputs']=[{'path':str(self.input),'sha256':sha(self.input)}]
        self.report['kind']='unrelated-receipt';self.save()
        with self.assertRaisesRegex(ValueError,'shared-launch-inputs'):
            launcher.read_input_manifest(self.manifest)


if __name__=='__main__':unittest.main()
