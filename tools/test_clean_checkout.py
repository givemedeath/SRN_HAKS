"""Export only committed infrastructure; prove import closure and local vendor pins."""
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

class CleanCheckoutTests(unittest.TestCase):
    def test_committed_infrastructure_without_source_worktrees_or_outputs(self):
        repo=Path(__file__).resolve().parent.parent
        archive=subprocess.run(['git','-C',str(repo),'archive','--format=zip','HEAD','tools'],check=True,capture_output=True).stdout
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with zipfile.ZipFile(BytesIO(archive)) as bundle:bundle.extractall(root)
            validation=json.loads((repo/'docs/shared-tool-validation.json').read_text(encoding='utf-8'))
            for name,pin in validation['boundBenchmarkHelperHashes'].items():
                actual=hashlib.sha256((root/'tools/phenotypes'/name).read_bytes()).hexdigest()
                self.assertEqual(actual,pin,'Regenerate the benchmark against the committed helper bytes: '+name)
            code='''import sys,pathlib
root=pathlib.Path.cwd().resolve()
sys.path[:0]=[str(root/'tools'),str(root/'tools/phenotypes')]
import shared_tools,shared_toolchain,launch_shared_tool,finalize_shared_tool_migration
import rig_pose_audit,rig_controller_audit,pose_preview_bridge,run_preparation,joint_review_packet,resume_summary
for module in [shared_tools,shared_toolchain,launch_shared_tool,finalize_shared_tool_migration,rig_pose_audit,rig_controller_audit,pose_preview_bridge,run_preparation,joint_review_packet,resume_summary]:
 assert pathlib.Path(module.__file__).resolve().is_relative_to(root)
if sys.platform=='win32':
 assert pathlib.Path(shared_tools.resolve_tool('mdlcomp',root,root=pathlib.Path(root.parent)/'durable-fixture')['path']).is_relative_to(root)
'''
            code+='\nassert {pathlib.Path(path).name:pin for path,pin in pose_preview_bridge.helper_inputs().items()} == '+repr(validation['boundBenchmarkHelperHashes'])+", 'Benchmark helper closure differs from the committed bytes'\n"
            result=subprocess.run([sys.executable,'-B','-c',code],cwd=root,capture_output=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse((root/'output').exists());self.assertFalse((root/'.tools').exists())

if __name__=='__main__':unittest.main()
