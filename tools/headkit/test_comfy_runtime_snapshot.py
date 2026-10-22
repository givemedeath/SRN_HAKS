"""CPU-only controlled-startup contract tests. No real Comfy server is contacted."""
import ast
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
from headkit.common import pin,write,read,digest
from headkit.comfy_nodes import managed_startup as startup
from headkit.comfy_nodes.source_snapshot import capture_inventory


class ControlledStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.core=self.root/'comfy';self.adapter=self.core/'custom_nodes'/'srn_headkit'
        self.adapter.mkdir(parents=True)
        for relative in ('main.py','execution.py','nodes.py','server.py','folder_paths.py','comfy/model.py',
                         'comfy_extras/nodes_trellis2.py','custom_nodes/plugin/flexgemm.py','custom_nodes/plugin/kernel.pyd'):
            path=self.core/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# fixture')
        for code in Path(startup.__file__).parent.glob('*.py'):shutil.copyfile(code,self.adapter/code.name)
        self.runtime=self.root/'runtime';self.runtime.mkdir()
        self.python=self.runtime/'python.exe';self.python.write_bytes(b'fixture interpreter')
        (self.runtime/'python.dll').write_bytes(b'fixture runtime')
        self.scratch=self.root/'scratch';self.scratch.mkdir()
        self.inventory=capture_inventory(self.core,[self.core])
        write(self.adapter/'source-roots.json',{'schemaVersion':1,'inventory':self.inventory})
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        self.config={'schemaVersion':1,'inventory':self.inventory,
                     'runtime':{'python':pin(self.python),'roots':[str(self.runtime)],'files':startup.runtime_inventory([self.runtime])},
                     'adapterSnapshot':pin(self.adapter/'source-roots.json'),
                     'launch':{'endpoint':f'http://127.0.0.1:{port}','arguments':['--cpu','--input-directory',str(self.root/'input'),'--output-directory',str(self.root/'output')],
                               'environment':{'TEMP':str(self.scratch),'HEADKIT_SETTING':'reviewed'}}}
        self.path=self.root/'startup.json';write(self.path,self.config)
        self.patch_file=patch.object(startup,'__file__',str(self.adapter/'managed_startup.py'));self.patch_file.start()
        self.addCleanup(self.patch_file.stop);self.addCleanup(self.temp.cleanup)

    def run_stub(self,callback=None):
        with patch.object(sys,'executable',str(self.python)),patch.object(sys,'flags',types.SimpleNamespace(isolated=1)), \
             patch.object(sys,'dont_write_bytecode',True),patch.object(startup,'_STARTED',False):
            return startup.start(self.path,self.root/'receipt.json',execute=callback or (lambda *a,**k:None))

    def test_sourceless_bytecode_is_pinned_and_changes_block_startup(self):
        import py_compile
        import subprocess
        from headkit.source_inventory import capture_sources,verify_sources
        source=self.root/'compiler-input.py';source.write_text('value=1\n')
        targets=[self.core/'standalone.pyc',self.core/'bytecode_package'/'__init__.pyc']
        for target in targets:
            target.parent.mkdir(exist_ok=True);py_compile.compile(str(source),cfile=str(target),doraise=True)
        startup_inventory=capture_inventory(self.core,[self.core]);client_inventory=capture_sources(self.core,[self.core])
        for target in targets:
            self.assertIn(pin(target),startup_inventory['files']);self.assertIn(pin(target),client_inventory['files'])
        self.config['inventory']=startup_inventory
        write(self.adapter/'source-roots.json',{'schemaVersion':1,'inventory':startup_inventory})
        self.config['adapterSnapshot']=pin(self.adapter/'source-roots.json');write(self.path,self.config)
        startup.verify_deployment(self.path)
        script="import sys; sys.pycache_prefix=sys.argv[2]; sys.path.insert(0,sys.argv[1]); import standalone,bytecode_package; print(standalone.value,bytecode_package.value)"
        result=subprocess.run([sys.executable,'-I','-B','-c',script,str(self.core),str(self.scratch/'fresh-cache')],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'1 1')
        for target in targets:
            before=target.read_bytes();source.write_text('value=2\n')
            py_compile.compile(str(source),cfile=str(target),doraise=True)
            execute=Mock()
            with self.subTest(target=target.name):
                with self.assertRaisesRegex(ValueError,'membership or bytes changed'):self.run_stub(execute)
                execute.assert_not_called()
                with self.assertRaisesRegex(ValueError,'Stale file pin'):verify_sources(client_inventory)
            target.write_bytes(before)

    def test_non_code_resources_are_pinned_and_rechecked_before_startup(self):
        from headkit.source_inventory import capture_sources,verify_sources
        resources=[self.core/'custom_nodes'/'plugin'/name for name in ('scale.ini','prompt.txt','settings.cfg','weights.bin','LICENSE')]
        for path in resources:path.write_bytes(b'reviewed resource')
        inventory=capture_inventory(self.core,[self.core]);client=capture_sources(self.core,[self.core])
        self.assertEqual(inventory,client)
        for path in resources:self.assertIn(pin(path),inventory['files'])
        self.config['inventory']=inventory
        write(self.adapter/'source-roots.json',{'schemaVersion':1,'inventory':inventory})
        self.config['adapterSnapshot']=pin(self.adapter/'source-roots.json');write(self.path,self.config)
        startup.verify_deployment(self.path)
        for path in resources:
            original=path.read_bytes();path.write_bytes(b'changed resource');execute=Mock()
            try:
                with self.subTest(resource=path.name):
                    with self.assertRaisesRegex(ValueError,'Stale file pin'):verify_sources(client)
                    with self.assertRaisesRegex(ValueError,'membership or bytes changed'):self.run_stub(execute)
                    execute.assert_not_called()
            finally:path.write_bytes(original)
        added=resources[0].with_name('new-resource.data');added.write_bytes(b'new')
        with self.assertRaisesRegex(ValueError,'membership changed'):verify_sources(client)
        with self.assertRaisesRegex(ValueError,'membership or bytes changed'):startup.verify_deployment(self.path)
        added.unlink()
        missing=resources[0];original=missing.read_bytes();missing.unlink()
        try:
            with self.assertRaisesRegex(ValueError,'membership changed'):verify_sources(client)
            with self.assertRaisesRegex(ValueError,'membership or bytes changed'):startup.verify_deployment(self.path)
        finally:missing.write_bytes(original)
        verify_sources(client);startup.verify_deployment(self.path)
        resource=resources[0];original=resource.read_bytes()
        try:
            with self.assertRaisesRegex(ValueError,'membership or bytes changed'):
                self.run_stub(lambda *a,**k:resource.write_bytes(b'changed in active session'))
            self.assertFalse(read(self.root/'receipt.json')['inputsUnchanged'])
        finally:resource.write_bytes(original)

    def test_separated_data_and_cache_files_stay_outside_source_inventory(self):
        from headkit.source_inventory import capture_sources
        from headkit.comfy_nodes.source_snapshot import CORE_DATA
        from headkit.source_inventory import CORE_DATA as client_data
        self.assertEqual(CORE_DATA,client_data)
        for name in sorted(CORE_DATA|{'.git','__pycache__'}):
            directory=self.core/name;directory.mkdir(exist_ok=True);(directory/'mutable.txt').write_text('generated data')
        source=capture_inventory(self.core,[self.core]);client=capture_sources(self.core,[self.core])
        self.assertEqual(source,client);self.assertEqual(source,self.inventory)

    def test_inventory_walk_errors_fail_closed_in_both_implementations(self):
        from headkit.source_inventory import capture_sources
        def unreadable(root,*,onerror,**kwargs):
            onerror(PermissionError('fixture directory unreadable'))
            return iter(())
        with patch('os.walk',side_effect=unreadable):
            for capture in (capture_sources,capture_inventory):
                with self.assertRaisesRegex(PermissionError,'fixture directory unreadable'):capture(self.core,[self.core])

    def test_pinned_startup_runs_once_and_writes_receipt(self):
        old_environment=dict(os.environ);old_path=list(sys.path);old_argv=sys.argv
        def entry(path,run_name):
            session,config=startup.session_context(self.core)
            self.assertEqual(config,self.config);self.assertEqual(path,str(self.core/'main.py'))
            self.assertEqual(run_name,'__main__');self.assertEqual(len(session['id']),32)
            self.assertEqual(set(os.environ),set(self.config['launch']['environment']))
            self.assertTrue(Path(sys.pycache_prefix).is_dir())
        result=self.run_stub(entry)
        self.assertEqual(result['state'],'complete');self.assertTrue(result['inputsUnchanged'])
        self.assertEqual(read(self.root/'receipt.json'),result)
        self.assertEqual(dict(os.environ),old_environment);self.assertEqual(sys.path,old_path);self.assertIs(sys.argv,old_argv)
        self.assertNotIn(startup.SESSION_MODULE,sys.modules)

    def test_second_start_requires_a_fresh_interpreter(self):
        with patch.object(sys,'executable',str(self.python)),patch.object(sys,'flags',types.SimpleNamespace(isolated=1)), \
             patch.object(sys,'dont_write_bytecode',True),patch.object(startup,'_STARTED',False):
            startup.start(self.path,self.root/'first.json',execute=lambda *a,**k:None)
            with self.assertRaisesRegex(ValueError,'fresh process'):
                startup.start(self.path,self.root/'second.json',execute=Mock())
        self.assertFalse((self.root/'second.json').exists())

    def test_restart_has_new_session_identity(self):
        first=self.run_stub();self.path=self.root/'same-startup.json';write(self.path,self.config)
        (self.root/'receipt.json').rename(self.root/'first-receipt.json')
        second=self.run_stub();self.assertNotEqual(first['session']['id'],second['session']['id'])

    def test_unmanaged_process_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unmanaged'):
            startup.session_context(self.core)

    def test_changed_sources_runtime_membership_and_snapshot_block_execution(self):
        for case in ('source','runtime','added-source','added-runtime','snapshot','configuration'):
            with self.subTest(case=case):
                originals={path:path.read_bytes() for path in [self.core/'nodes.py',self.python,self.adapter/'source-roots.json',self.path]}
                added=None
                if case=='source':(self.core/'nodes.py').write_text('changed')
                elif case=='runtime':self.python.write_bytes(b'changed')
                elif case.startswith('added'):
                    added=(self.core if case=='added-source' else self.runtime)/'new.py';added.write_text('changed')
                elif case=='snapshot':write(self.adapter/'source-roots.json',{})
                else:write(self.path,{'schemaVersion':0})
                execute=Mock()
                try:
                    with self.assertRaises((ValueError,KeyError)):self.run_stub(execute)
                    execute.assert_not_called();self.assertFalse((self.root/'receipt.json').exists())
                finally:
                    for path,data in originals.items():path.write_bytes(data)
                    if added:added.unlink()

    def test_declared_settings_and_configuration_changes_invalidate_session(self):
        for change in ('environment','arguments','configuration','source','runtime'):
            with self.subTest(change=change):
                originals={path:path.read_bytes() for path in (self.path,self.core/'nodes.py',self.python)}
                def entry(*args,**kwargs):
                    if change=='environment':os.environ['HEADKIT_SETTING']='different'
                    elif change=='arguments':sys.argv.append('--different')
                    elif change=='configuration':write(self.path,dict(self.config,launch=dict(self.config['launch'],arguments=[])))
                    elif change=='source':(self.core/'nodes.py').write_text('changed')
                    else:self.python.write_bytes(b'changed')
                try:
                    with self.assertRaises(ValueError):self.run_stub(entry)
                    self.assertFalse(read(self.root/'receipt.json')['inputsUnchanged'])
                    self.assertEqual(read(self.root/'receipt.json')['state'],'failed')
                finally:
                    for path,data in originals.items():path.write_bytes(data)
                    (self.root/'receipt.json').unlink(missing_ok=True)

    def test_exception_preserves_failure_and_does_not_reuse_receipt(self):
        def fail(*args,**kwargs):raise RuntimeError('fixture stopped')
        with self.assertRaisesRegex(RuntimeError,'fixture stopped'):self.run_stub(fail)
        self.assertEqual(read(self.root/'receipt.json')['state'],'failed')
        with self.assertRaisesRegex(ValueError,'fresh startup receipt'):self.run_stub()

    def test_busy_port_blocks_before_start_without_touching_owner(self):
        with socket.socket() as owner:
            owner.bind(('127.0.0.1',0));owner.listen()
            self.config['launch']['endpoint']=f'http://127.0.0.1:{owner.getsockname()[1]}';write(self.path,self.config)
            entry=Mock()
            with self.assertRaisesRegex(ValueError,'occupied; stop and wait'):self.run_stub(entry)
            entry.assert_not_called();self.assertGreater(owner.fileno(),0)
            self.assertFalse((self.root/'receipt.json').exists())

    def test_offline_configuration_preparation_never_starts_or_contacts_comfy(self):
        from headkit.__main__ import startup_config
        local={'comfyRoot':str(self.core),'comfyCustomNodes':str(self.adapter.parent),
               'comfySources':self.inventory['files'],'comfyUrl':self.config['launch']['endpoint'],
               'comfyPython':pin(self.python),'comfyRuntimeRoots':[str(self.runtime)],'comfyStartup':self.config['launch'],
               'comfyInput':str(self.root/'input'),'comfyOutput':str(self.root/'output')}
        output=self.root/'prepared.json'
        with patch('headkit.comfy.Client.request') as request,patch.object(startup,'start') as start:
            result=startup_config(local,output)
            self.assertFalse(result['started']);self.assertEqual(read(output),self.config)
            request.assert_not_called();start.assert_not_called()
        with self.assertRaisesRegex(ValueError,'outside deployment roots'):
            startup_config(local,self.runtime/'recursive.json')
        local['comfyInput']=str(self.root/'different-input')
        with self.assertRaisesRegex(ValueError,'directories must exactly match'):
            startup_config(local,self.root/'mismatch.json')

    def test_direct_isolated_script_help_needs_no_comfy_or_gpu(self):
        import subprocess
        result=subprocess.run([sys.executable,'-I','-B',str(self.adapter/'managed_startup.py'),'--help'],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('--config',result.stdout)

    def test_runtime_requires_isolated_python_and_matching_executable(self):
        with self.assertRaisesRegex(ValueError,'-I -B'):startup.start(self.path,self.root/'receipt.json')
        with patch.object(sys,'flags',types.SimpleNamespace(isolated=1)),patch.object(sys,'dont_write_bytecode',True):
            with self.assertRaisesRegex(ValueError,'Executing Python'):startup.start(self.path,self.root/'receipt.json')

    def test_launch_settings_reject_endpoint_overrides_and_python_injection(self):
        for launch in ({'endpoint':'http://0.0.0.0:8188'},{'arguments':['--port=8188']},
                       {'arguments':['--listen','0.0.0.0']},{'environment':{'PYTHONPATH':'unsafe'}}):
            with self.subTest(launch=launch):
                config=copy.deepcopy(self.config);config['launch'].update(launch)
                with self.assertRaises(ValueError):startup.launch_arguments(config)

    def test_endpoint_abbreviations_are_rejected_before_startup(self):
        import argparse
        parser=argparse.ArgumentParser()
        parser.add_argument('--listen');parser.add_argument('--port')
        for flag,value in (('--listen','0.0.0.0'),('--port','9999')):
            for length in range(3,len(flag)+1):
                option=flag[:length]
                for arguments in ([option,value],[option+'='+value]):
                    with self.subTest(arguments=arguments):
                        # Default argparse permits these overrides, including after bound values.
                        parsed=parser.parse_args(['--listen','127.0.0.1','--port','8188',*arguments])
                        self.assertEqual(getattr(parsed,flag[2:]),value)
                        config=copy.deepcopy(self.config);config['launch']['arguments']=arguments
                        with self.assertRaisesRegex(ValueError,'bound endpoint'):startup.launch_arguments(config)
        for flag in ('--input-directory','--output-directory'):
            for length in range(3,len(flag)):
                for arguments in ([flag[:length],'other'],[flag[:length]+'=other']):
                    with self.subTest(arguments=arguments):
                        config=copy.deepcopy(self.config);config['launch']['arguments']+=arguments
                        with self.assertRaisesRegex(ValueError,'abbreviations'):startup.launch_arguments(config)
        self.config['launch']['arguments']=['--preview-method','none','--listen-extra','fixture']
        self.assertEqual(startup.launch_arguments(self.config)[5:],self.config['launch']['arguments'])

    def test_runtime_links_and_configuration_mutation_are_rejected(self):
        link=self.runtime/'alias.py'
        try:link.symlink_to(self.python)
        except OSError:self.skipTest('Symlink privilege unavailable')
        with self.assertRaisesRegex(ValueError,'Linked runtime'):startup.runtime_inventory([self.runtime])

    def test_runtime_endpoint_returns_only_the_verified_current_session(self):
        source=Path(__file__).parent/'comfy_nodes'/'__init__.py'
        tree=ast.parse(source.read_bytes());handler=next(node for node in ast.walk(tree)
                if isinstance(node,ast.AsyncFunctionDef) and node.name=='verify_headkit_runtime_identity')
        handler.decorator_list=[]
        baseline={'schemaVersion':3,'fingerprint':'reviewed'};session={'id':'a'*32}
        context=Mock(return_value=(session,{}))
        namespace={'_STARTUP_RUNTIME_IDENTITY':baseline,'_STARTUP_SESSION':session,'session_context':context,
                   'folder_paths':types.SimpleNamespace(base_path=str(self.core)),
                   'web':types.SimpleNamespace(json_response=lambda body,status=200:(status,body))}
        exec(compile(ast.Module(body=[handler],type_ignores=[]),str(source),'exec'),namespace)
        run=lambda:asyncio.run(namespace['verify_headkit_runtime_identity'](None))
        self.assertEqual(run(),(200,baseline))
        context.return_value=({'id':'b'*32},{})
        self.assertEqual(run(),(409,{'verified':False}))
        context.side_effect=ValueError('deployment changed')
        self.assertEqual(run(),(409,{'verified':False}))
        namespace['_STARTUP_RUNTIME_IDENTITY']=None
        context.reset_mock();self.assertEqual(run(),(409,{'verified':False}));context.assert_not_called()

    def test_adapter_startup_capture_is_atomic_and_requires_managed_session(self):
        source=Path(__file__).parent/'comfy_nodes'/'__init__.py';tree=ast.parse(source.read_bytes())
        helper=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_capture_startup')
        session={'id':'fixture'};config={'inventory':self.inventory,'runtime':{'files':[]}}
        namespace={'session_context':Mock(return_value=(session,config)),'folder_paths':types.SimpleNamespace(base_path=str(self.core)),
                   'capture_runtime_identity':Mock(return_value={'files':[]})}
        exec(compile(ast.Module(body=[helper],type_ignores=[]),str(source),'exec'),namespace)
        self.assertEqual(namespace['_capture_startup'](),(self.inventory,session,{'files':[]}))
        namespace['session_context'].side_effect=ValueError('unmanaged')
        self.assertEqual(namespace['_capture_startup'](),(None,None,None))


class VerifiedLoaderBoundaryTests(unittest.TestCase):

    def test_verified_loader_factories_bind_each_original_and_input_schema(self):
            from headkit.comfy_nodes import verified_loaders
            class UnetLoader:
                RETURN_TYPES = ('MODEL',)
                FUNCTION = 'load'
                @classmethod
                def INPUT_TYPES(cls):
                    return {'required': {'unet_name': (['unet.safetensors'],)}}
                def load(self, unet_name):
                    return ('unet', unet_name)
            class VaeLoader:
                RETURN_TYPES = ('VAE',)
                FUNCTION = 'decode'
                @classmethod
                def INPUT_TYPES(cls):
                    return {'required': {'vae_name': (['vae.safetensors'],)}}
                def decode(self, vae_name):
                    return ('vae', vae_name)
            folders = types.SimpleNamespace()
            wrappers = verified_loaders.verified_loader_mappings({'UNETLoader': UnetLoader, 'VAELoader': VaeLoader}, folders)
            unet = wrappers['HeadkitVerifiedUNETLoaderV1']
            vae = wrappers['HeadkitVerifiedVAELoaderV1']
            self.assertIn('unet_name', unet.INPUT_TYPES()['required'])
            self.assertNotIn('vae_name', unet.INPUT_TYPES()['required'])
            self.assertIn('vae_name', vae.INPUT_TYPES()['required'])
            unet.INPUT_TYPES()['required']['mutated'] = ('STRING',)
            self.assertNotIn('mutated', unet.INPUT_TYPES()['required'])
            with patch.object(verified_loaders, 'verify_model_file') as verify:
                self.assertEqual(unet().load_verified('u-sha', 'u-path', unet_name='unet.safetensors'), ('unet', 'unet.safetensors'))
                self.assertEqual(vae().load_verified('v-sha', 'v-path', vae_name='vae.safetensors'), ('vae', 'vae.safetensors'))
            self.assertEqual([row.args for row in verify.call_args_list], [
                ('diffusion_models', 'unet.safetensors', 'u-path', 'u-sha', folders),
                ('vae', 'vae.safetensors', 'v-path', 'v-sha', folders)])

if __name__=='__main__':unittest.main()
