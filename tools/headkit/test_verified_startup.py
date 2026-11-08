"""Real subprocess tests of import-time source proof, including stale pyc files."""
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest

from headkit.comfy_nodes.source_snapshot import capture_inventory, _inside


class VerifiedStartupTests(unittest.TestCase):
    def run_fixture(self, helper, body='', stale=None, preload=False):
        with tempfile.TemporaryDirectory() as temporary:
            core=Path(temporary)/'core'; adapter=core/'custom_nodes'/'srn_headkit'
            adapter.mkdir(parents=True)
            for relative in ('comfy_nodes/source_snapshot.py','comfy_nodes/verified_startup.py','comfy_nodes/verification.py'):
                source=Path(__file__).parent/relative
                shutil.copyfile(source,adapter/source.name)
            for name in ('execution.py','nodes.py','server.py','folder_paths.py','comfy/model.py',
                         'comfy_extras/nodes_trellis2.py','comfy/flexgemm.py','comfy/kernel.pyd'):
                (core/name).parent.mkdir(parents=True,exist_ok=True)
                (core/name).write_text('# fixture\n',encoding='utf-8')
            helper_path=core/'fixture.py'
            helper_path.write_text(helper,encoding='utf-8')
            if stale:
                stat=helper_path.stat()
                self.assertEqual(len(stale.encode()),len(helper.encode()))
                helper_path.write_text(stale,encoding='utf-8')
                os.utime(helper_path,(stat.st_atime,stat.st_mtime))
                py_compile.compile(str(helper_path),doraise=True)
                helper_path.write_text(helper,encoding='utf-8')
                os.utime(helper_path,(stat.st_atime,stat.st_mtime))
            (core/'main.py').write_text(
                'import fixture\n'+body+
                '\nimport _srn_startup_snapshot as snapshot\n'
                'from pathlib import Path\n'
                'print("VERIFIED", len(snapshot.loaded_source_code([Path(__file__).parent])))\n',encoding='utf-8')
            inventory=capture_inventory(core,[core])
            (adapter/'source-roots.json').write_text(json.dumps({'schemaVersion':1,'inventory':inventory}),encoding='utf-8')
            environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
            environment.pop('PYTHONPATH',None)
            entry=str(adapter/'verified_startup.py')
            arguments=(['-c','import fixture, runpy, sys; sys.argv=[sys.argv[1]]; '
                        'runpy.run_path(sys.argv[0],run_name="__main__")',entry] if preload else [entry])
            return subprocess.run([sys.executable,'-B',*arguments],cwd=core,
                                  env=environment,capture_output=True,text=True,timeout=60)

    def test_source_proof_accepts_conditions_and_factory_defaults(self):
        source=('import sys\nclass Holder:\n'
                '    def __init__(self):\n'
                '        if sys.version_info.major >= 3: self.setting = True\n'
                '        else: self.setting = False\n'
                'def value(default=object()): return default\n'
                'pending=Holder()\ndel Holder.__init__\n')
        result=self.run_fixture(source)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('VERIFIED',result.stdout)

    def test_stale_cached_module_body_is_rejected_before_execution(self):
        source='def value(default=1): return default\n'
        result=self.run_fixture(source,stale=source.replace('default=1','default=2'))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Executed Python code differs',result.stderr)
        self.assertNotIn('VERIFIED',result.stdout)

    def test_retained_replaced_function_code_still_fails(self):
        result=self.run_fixture('def value(): return 1\n',
                                'fixture.value.__code__=fixture.value.__code__.replace(co_consts=(None,2))\n')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Loaded Comfy Python code differs',result.stderr)

    def test_proven_modules_reject_live_literal_mutations(self):
        cases=[('def value(default=1): return default\n','fixture.value.__defaults__=(2,)','defaults or closure'),
               ('def value(*, mode=1): return mode\n',"fixture.value.__kwdefaults__['mode']=2",'defaults or closure'),
               ('SCALE=1\n','fixture.SCALE=2','module constants'),
               ("SETTINGS={'steps':12}\n","fixture.SETTINGS['steps']=10",'module constants'),
               ('class Model:\n    SCALE=1\n','fixture.Model.SCALE=2','class attributes'),
               ('class Model:\n    def __init__(self): self.setting=1\npending=Model()\n',
                "setattr(fixture.pending,'setting',2)",'instance attributes'),
               ('def make():\n    mode=1\n    def value(): return mode\n    return value\npending=make()\n',
                'fixture.pending.__closure__[0].cell_contents=2','defaults or closure'),
               ("def make():\n    settings={'steps':12}\n    def value(): return settings\n    return value\npending=make()\n",
                "fixture.pending.__closure__[0].cell_contents['steps']=10",'defaults or closure')]
        for source,mutation,error in cases:
            with self.subTest(mutation=mutation):
                result=self.run_fixture(source,mutation+'\n')
                self.assertNotEqual(result.returncode,0,result.stderr)
                self.assertIn(error,result.stderr)
                self.assertNotIn('VERIFIED',result.stdout)

    def test_proven_registries_filled_by_their_own_source_still_verify(self):
        source=('NAMES={"A":"A"}\nENABLED=True\nSETTINGS={"steps":12}\n'
                'def register(name):\n    NAMES[name]=name\n'
                'def disable():\n    global ENABLED\n    ENABLED=False\n')
        result=self.run_fixture(source,'fixture.register("custom");fixture.disable()\n')
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('VERIFIED',result.stdout)
        # Another verified module changing an undeclared setting still fails.
        result=self.run_fixture(source,"fixture.SETTINGS['steps']=10\n")
        self.assertNotEqual(result.returncode,0);self.assertIn('module constants',result.stderr)

    def test_factory_defaults_do_not_exempt_other_literal_defaults(self):
        source='def value(factory=object(), mode=1): return mode\n'
        result=self.run_fixture(source,'fixture.value.__defaults__=(fixture.value.__defaults__[0],2)\n')
        self.assertNotEqual(result.returncode,0);self.assertIn('defaults or closure',result.stderr)

    def test_preloaded_stale_defaults_keep_static_verification(self):
        source='def value(default=1): return default\n'
        result=self.run_fixture(source,stale=source.replace('default=1','default=2'),preload=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('function defaults or closure differ',result.stderr)

    def test_source_change_after_execution_is_rejected(self):
        result=self.run_fixture('def value(): return 1\n',
                                'from pathlib import Path\nPath(fixture.__file__).write_text("def value(): return 2\\n")\n')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Executed source changed after startup',result.stderr)

    def test_source_scope_matches_inventory_and_explicit_dependency_roots(self):
        core=Path('/core').resolve(); dependency=core/'.venv'/'vendor'
        self.assertFalse(_inside(core/'.venv'/'unrelated.py',[core,dependency]))
        self.assertTrue(_inside(dependency/'runtime.py',[core,dependency]))
        self.assertTrue(_inside(core/'comfy'/'model.py',[core,dependency]))
        self.assertFalse(_inside(core/'input'/'data.py',[core,dependency]))


if __name__=='__main__':unittest.main()
