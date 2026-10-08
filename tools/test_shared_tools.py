"""Shared cross-language fixtures, real Git topology, byte drift and retirement."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from shared_tools import *

PS=shutil.which('pwsh')
MODULE=HERE/'SrnTools.psm1'

class SharedToolsTests(unittest.TestCase):
    def test_launcher_snapshot_registration_avoids_duplicate_input_hashing(self):
        source=self.repo/'payload.bin';source.write_bytes(b'consumed bytes');digest=sha(source)
        real_sha=sha
        with patch('shared_tools.sha',side_effect=real_sha) as hashing:
            receipt=register_run(self.repo,inputs=[{'path':source,'sha256':digest}],_verified_inputs={str(source.resolve()):digest})
            self.assertFalse(any(Path(call.args[0]).resolve()==source.resolve() for call in hashing.call_args_list))
        self.assertEqual(read_json(receipt)['references'][0]['sha256'],digest)
        with self.assertRaisesRegex(ValueError,'changed'):
            register_run(self.repo,inputs=[{'path':source,'sha256':'0'*64}],_verified_inputs={str(source.resolve()):digest})
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            register_run(self.repo,inputs=[{'path':source,'sha256':digest}])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name).resolve()
        self.repo=self.base/'primary space';self.repo.mkdir()
        self.env=patch.dict(os.environ,{'SRN_TOOLS_ROOT':''});self.env.start()
        for command in [('init',),('config','user.name','Fixture'),('config','user.email','fixture@example.invalid')]:
            self.git(*command)
        (self.repo/'first').write_text('fixture',encoding='utf-8');self.git('add','.');self.git('commit','-qm','fixture')
        self.link=self.base/'linked space';self.git('worktree','add','--detach',str(self.link))
        self.bank=self.repo/'.tools';(self.bank/'package').mkdir(parents=True)
        self.exe=self.bank/'package/tool.exe';self.exe.write_bytes(b'pinned tool')
        self.data={'schemaVersion':1,'tools':{'erf':{'origin':'shared','version':'test','platforms':
            {key:{'relativePath':'package/tool.exe','sha256':sha(self.exe)} for key in ['windows-x64','linux-x64']}}},'addons':{}}
        (self.repo/'tools').mkdir();write_json(self.repo/'tools/shared-tools.lock.json',self.data)
        (self.link/'tools').mkdir();write_json(self.link/'tools/shared-tools.lock.json',self.data)

    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def git(self,*args):
        subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)

    def ps(self,statement):
        if not PS:self.skipTest('pwsh unavailable')
        command="Import-Module '"+str(MODULE).replace("'","''")+"' -Force; "+statement
        result=subprocess.run([PS,'-NoProfile','-Command',command],capture_output=True,encoding='utf-8')
        if result.returncode:raise ValueError(result.stderr)
        return json.loads(result.stdout)

    def test_primary_linked_explicit_environment_and_parity(self):
        for repo in [self.repo,self.link]:
            py=resolve_tool('erf',repo)
            ps=self.ps(f"Resolve-SrnTool erf -RepositoryRoot '{repo}' | ConvertTo-Json")
            self.assertEqual(py,ps)
        # Windows runner TEMP can use an 8.3 alias such as RUNNER~1.
        alias=Path(self.tmp.name)/'primary space/.tools'
        py=resolve_tool('erf',self.link,root=alias)
        ps=self.ps(f"Resolve-SrnTool erf -ToolsRoot '{alias}' -RepositoryRoot '{self.link}' | ConvertTo-Json")
        self.assertEqual(py,ps)
        other=self.base/'override space';shutil.copytree(self.bank,other)
        with patch.dict(os.environ,{'SRN_TOOLS_ROOT':str(other)}):
            self.assertEqual(tools_root(self.link)[0],other)
            self.assertEqual(tools_root(self.link,self.bank)[0],self.bank)
            self.assertEqual(self.ps(f"(Get-SrnToolsRoot -RepositoryRoot '{self.link}').path | ConvertTo-Json"),str(other))

    def test_missing_metadata_bare_and_explicit(self):
        empty=self.base/'empty';empty.mkdir()
        with self.assertRaises(ValueError):tools_root(empty)
        self.assertEqual(tools_root(empty,self.bank)[0],self.bank)
        bare=self.base/'bare';subprocess.run(['git','init','--bare',str(bare)],check=True,capture_output=True)
        with self.assertRaises(ValueError):tools_root(bare)
        with self.assertRaises(ValueError):self.ps(f"Get-SrnToolsRoot -RepositoryRoot '{empty}' | ConvertTo-Json")

    def test_linked_and_foreign_worktree_rejected(self):
        for path in [self.link/'.tools',self.link/'tool.exe']:
            with self.assertRaisesRegex(ValueError,'linked worktree'):tools_root(self.repo,path)
            with self.assertRaisesRegex(ValueError,'linked worktree'):self.ps(f"Get-SrnToolsRoot -ToolsRoot '{path}' -RepositoryRoot '{self.repo}' | ConvertTo-Json")
        with self.assertRaises(ValueError):tools_root(self.base,self.link/'.tools')

    def test_junction_or_symlink_escape_rejected(self):
        shortcut=self.bank/'escape'
        if os.name=='nt':
            subprocess.run(['cmd','/c','mklink','/J',str(shortcut),str(self.link)],check=True,capture_output=True)
        else:shortcut.symlink_to(self.link,target_is_directory=True)
        with self.assertRaises(ValueError):tools_root(self.repo,shortcut)
        with self.assertRaises(ValueError):self.ps(f"Get-SrnToolsRoot -ToolsRoot '{shortcut}' -RepositoryRoot '{self.repo}' | ConvertTo-Json")

    def test_bytes_marker_and_override_escape(self):
        write_json(self.bank/'package/.complete.json',{'complete':True})
        self.exe.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'binary changed'):resolve_tool('erf',self.repo)
        with self.assertRaisesRegex(ValueError,'binary changed'):self.ps(f"Resolve-SrnTool erf -RepositoryRoot '{self.repo}' | ConvertTo-Json")
        with self.assertRaises(ValueError):resolve_tool('erf',self.repo,override=self.repo/'first')

    def test_addon_cache_excluded_source_drift_rejected(self):
        bank=self.bank/'addons';bank.mkdir();(bank/'addon.py').write_bytes(b'addon')
        self.data['addons']['neverblender']={'relativePath':'addons','version':'test','files':{'addon.py':sha(bank/'addon.py')},'installation':'Install pinned addon'}
        write_json(self.repo/'tools/shared-tools.lock.json',self.data)
        (bank/'__pycache__').mkdir();(bank/'__pycache__/derived.pyc').write_bytes(b'cache')
        resolve_addon(repo=self.repo)
        (bank/'addon.py').write_bytes(b'drift')
        with self.assertRaises(ValueError):resolve_addon(repo=self.repo)

    def test_runtime_store_shim_and_linked_rejected(self):
        with self.assertRaisesRegex(ValueError,'Store'):resolve_runtime('python',self.base/'WindowsApps/python.exe',self.repo)
        with self.assertRaisesRegex(ValueError,'linked'):resolve_runtime('blender',self.link/'tool',self.repo)
        py=resolve_runtime('python',self.exe,self.repo)
        ps=self.ps(f"Resolve-SrnRuntime python -Path '{self.exe}' -RepositoryRoot '{self.repo}' | ConvertTo-Json")
        self.assertEqual(py,ps)

    def test_vendored_tools_belong_to_the_consuming_checkout(self):
        entry={'origin':'vendored','version':'fixture','platforms':{key:{'relativePath':'vendor/tool.exe',
            'sha256':sha(self.exe)} for key in ['windows-x64','linux-x64']}}
        self.data['tools']['mdlcomp']=entry
        for repo in [self.repo,self.link]:
            vendor=repo/'tools/vendor';vendor.mkdir();shutil.copyfile(self.exe,vendor/'tool.exe')
            write_json(repo/'tools/shared-tools.lock.json',self.data)
        resolved=resolve_tool('mdlcomp',self.link)
        self.assertTrue(inside(resolved['path'],self.link))
        self.assertEqual(resolved,self.ps(f"Resolve-SrnTool mdlcomp -RepositoryRoot '{self.link}' | ConvertTo-Json"))
        with self.assertRaises(ValueError):resolve_tool('mdlcomp',self.link,override=self.repo/'tools/vendor/tool.exe')

    def test_retirement_live_migrated_missing_provenance_and_incomplete(self):
        required=self.link/'borrowed';required.write_bytes(b'input')
        register_run(self.repo,inputs=[required],complete=True)
        report=retirement_audit(self.repo,self.link)
        self.assertEqual(len(report['dependencies']),1);self.assertFalse(report['dependencyClear'])
        durable=self.repo/'durable';shutil.copyfile(required,durable)
        register_run(self.repo,inputs=[durable],provenance=[required],complete=True)
        self.assertTrue(retirement_audit(self.repo,self.link)['dependencyClear'])
        required.unlink();self.assertTrue(retirement_audit(self.repo,self.link)['dependencyClear'])
        durable.unlink();self.assertTrue(retirement_audit(self.repo,self.link)['missingDependencies'])
        register_run(self.repo,inputs=[],complete=False)
        self.assertTrue(retirement_audit(self.repo,self.link)['incompleteConsumers'])

    def test_windows_case_or_linux_case_is_platform_correct(self):
        self.assertEqual(inside(self.repo/'first',str(self.repo).upper()),os.name=='nt')

    def test_registration_lock_and_reference_union_are_cross_language(self):
        if not PS:self.skipTest('pwsh unavailable')
        identity=hashlib.sha256(os.path.normcase(str(self.repo)).encode('utf-8')).hexdigest()
        folder=self.bank/'consumers'/identity
        lock=folder/'registration.lock'
        statement=(f"$stream=[IO.File]::Open('{lock}','OpenOrCreate','ReadWrite','ReadWrite'); "
                   "try { $stream.Lock(0,1); $stream.Unlock(0,1) } catch { exit 9 } finally { $stream.Dispose() }")
        with locked(lock):
            attempt=subprocess.run([PS,'-NoProfile','-Command',statement],capture_output=True)
            self.assertEqual(attempt.returncode,9,'PowerShell ignored the Python byte-range lock')
        self.assertEqual(subprocess.run([PS,'-NoProfile','-Command',statement],capture_output=True).returncode,0)
        first=self.repo/'CaseInput';first.write_bytes(b'first')
        inputs=[first]
        if os.name!='nt':
            other=self.repo/'caseinput';other.write_bytes(b'case-sensitive other');inputs.append(other)
        literals=','.join("'"+str(path)+"'" for path in inputs)
        self.ps(f"$tool=Resolve-SrnTool erf -RepositoryRoot '{self.repo}'; Register-SrnToolUse $tool -Inputs @({literals}) -RepositoryRoot '{self.repo}'; 'registered' | ConvertTo-Json")
        second=self.repo/'second';second.write_bytes(b'second')
        register_run(self.repo,inputs=[second])
        current=read_json(folder/'current.json')
        required={row['path'] for row in current['references']}
        self.assertTrue({str(path) for path in [self.exe,*inputs,second]}<=required)
        self.assertFalse(current['completeDeclaration'])

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        if not PS:self.skipTest('pwsh unavailable')
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.repo=self.base/'repo';self.tools=self.repo/'tools';self.tools.mkdir(parents=True)
        for name in ['SrnTools.psm1','Bootstrap-Tools.ps1']:shutil.copyfile(HERE/name,self.tools/name)
        self.root=self.base/'cache';(self.root/'downloads').mkdir(parents=True)
        self.key=platform_key();self.destination=self.root/'neverwinter/test'/self.key
        payload=b'fixture executable';archive=self.root/'downloads/fixture.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('tool.exe',payload)
        self.lock={'releaseTag':'test','sourceRepository':'fixture','commit':'fixture','platforms':{self.key:{'fileName':'fixture.zip','url':'https://example.invalid/no-download','sha256':sha(archive),'executables':{'erf':'tool.exe'},'executableSha256':{'erf':hashlib.sha256(payload).hexdigest()}}}}
        self.inventory={'schemaVersion':1,'tools':{'erf':{'origin':'shared','version':'test','platforms':{self.key:{'relativePath':f'neverwinter/test/{self.key}/tool.exe','sha256':hashlib.sha256(payload).hexdigest()}}}}}
        write_json(self.tools/'toolchain.lock.json',self.lock);write_json(self.tools/'shared-tools.lock.json',self.inventory)
    def tearDown(self):self.tmp.cleanup()
    def process(self):return subprocess.Popen([PS,'-NoProfile','-File',str(self.tools/'Bootstrap-Tools.ps1'),'-ToolsRoot',str(self.root),'-Force'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def test_existing_empty_lock_initialization_waits_for_its_owner(self):
        import time
        lock=self.root/'locks'/f'neverwinter-test-{self.key}.lock'
        lock.parent.mkdir(parents=True)
        with lock.open('w+b') as stream:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.lockf(stream,fcntl.LOCK_EX|fcntl.LOCK_NB,1,0,os.SEEK_SET)
            job=self.process()
            try:
                time.sleep(1)
                # The child must wait instead of writing/flushing a locked byte.
                self.assertIsNone(job.poll(),"Bootstrap tried to initialize another owner's lock")
                self.assertEqual(lock.stat().st_size,0)
            finally:
                stream.seek(0)
                if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.lockf(stream,fcntl.LOCK_UN,1,0,os.SEEK_SET)
            out,err=job.communicate(timeout=45)
            self.assertEqual(job.returncode,0,err.decode())
            self.assertEqual(lock.read_bytes(),b'0')

    def test_concurrent_cache_reuse_ignores_interrupted_staging(self):
        abandoned=self.root/'staging/abandoned';abandoned.mkdir(parents=True);(abandoned/'partial').write_bytes(b'bad')
        jobs=[self.process(),self.process()]
        for job in jobs:
            out,err=job.communicate(timeout=45);self.assertEqual(job.returncode,0,err.decode())
        tool=self.destination/'tool.exe';stamp=tool.stat().st_mtime_ns
        job=self.process();out,err=job.communicate(timeout=45);self.assertEqual(job.returncode,0,err.decode());self.assertEqual(tool.stat().st_mtime_ns,stamp)
        self.assertTrue(abandoned.exists())
    def test_stale_marker_failed_extraction_does_not_destroy_prior(self):
        self.destination.mkdir(parents=True);tool=self.destination/'tool.exe';tool.write_bytes(b'prior invalid diagnostic')
        write_json(self.destination/'.complete.json',{'releaseTag':'test','archiveSha256':self.lock['platforms'][self.key]['sha256']})
        self.lock['platforms'][self.key]['executableSha256']['erf']='0'*64;write_json(self.tools/'toolchain.lock.json',self.lock)
        job=self.process();out,err=job.communicate(timeout=45);self.assertNotEqual(job.returncode,0);self.assertEqual(tool.read_bytes(),b'prior invalid diagnostic')
    def test_failed_download_cannot_damage_valid_package(self):
        job=self.process();out,err=job.communicate(timeout=45);self.assertEqual(job.returncode,0,err.decode())
        (self.root/'downloads/fixture.zip').write_bytes(b'corrupt cache')
        job=self.process();out,err=job.communicate(timeout=45);self.assertEqual(job.returncode,0,err.decode())

if __name__=='__main__':unittest.main()
