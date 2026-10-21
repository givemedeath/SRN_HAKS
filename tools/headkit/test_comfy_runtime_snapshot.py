"""Focused regressions for the adapter's loaded-Comfy source identity guard."""
import ast
import asyncio
import functools
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

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

    def _import_literal_snapshot(self, *, value=1, reviewed=1, evict=False, reload=False,
                                 relative=False, alias=False, star=False, foreign=False, copy=False, retention=None, error=None):
        folder=self.core/'literal_package' if relative else self.core
        folder.mkdir(exist_ok=True)
        provider_name='literal_package.literal_provider' if relative else 'literal_provider'
        consumer_name='literal_package.literal_consumer' if relative else 'literal_consumer'
        provider_path=(Path(self.temp.name) if foreign else folder)/'literal_provider.py'
        consumer_path=folder/'literal_consumer.py'
        provider=types.ModuleType(provider_name);provider.__file__=str(provider_path)
        consumer=types.ModuleType(consumer_name);consumer.__file__=str(consumer_path)
        consumer.__package__='literal_package' if relative else ''
        member='*' if star else 'SCALE as copied' if alias else 'SCALE'
        prefix='.' if relative else ''
        used='copied' if alias else 'SCALE'
        setup=f'retained={used}\ndel {used}\n' if copy else ''
        result='retained' if copy else used
        if retention:setup,result=retention;setup=setup.replace('IMPORTED',used)
        source=f'from {prefix}literal_provider import {member}\n{setup}def read(): return {result}\n'
        consumer_path.write_text(source,encoding='utf-8')
        provider_source=f'SCALE={value}\n';provider_path.write_text(provider_source,encoding='utf-8')
        modules={provider_name:provider,consumer_name:consumer}
        if relative:
            package=types.ModuleType('literal_package');package.__file__=str(folder/'__init__.py')
            package.__path__=[str(folder)];(folder/'__init__.py').write_text('# package\n',encoding='utf-8')
            modules['literal_package']=package
        with patch.dict(sys.modules,modules,clear=True):
            exec(compile(provider_source,str(provider_path),'exec'),vars(provider))
            exec(compile(source,str(consumer_path),'exec'),vars(consumer))
            self.assertEqual(consumer.read(),value)
            provider_path.write_text(f'SCALE={reviewed}\n',encoding='utf-8')
            if evict:del sys.modules[provider_name]
            if reload:
                replacement=types.ModuleType(provider_name);replacement.__file__=str(provider_path)
                exec(compile(f'SCALE={reviewed}\n',str(provider_path),'exec'),vars(replacement))
                sys.modules[provider_name]=replacement
            if error:
                with self.assertRaisesRegex(ValueError,error):loaded_source_code([self.core])
                return
            rows=loaded_source_code([self.core])
            return next(row for row in rows if row['path']==str(consumer_path.resolve()))

    def test_evicted_imported_literal_providers_fail_closed(self):
        for options in ({},{'alias':True},{'relative':True},{'relative':True,'alias':True},{'star':True},{'copy':True}):
            with self.subTest(options=options):
                self._import_literal_snapshot(value=2,evict=True,error='import|provider',**options)

    def test_reloaded_providers_cannot_hide_stale_imported_literals(self):
        for options in ({},{'relative':True},{'star':True},{'copy':True}):
            with self.subTest(options=options):
                self._import_literal_snapshot(value=2,reload=True,error='import|provider',**options)

    def test_matching_imported_literals_are_fingerprinted(self):
        first=self._import_literal_snapshot(value=1,reviewed=1)
        second=self._import_literal_snapshot(value=2,reviewed=2)
        self.assertNotEqual(first['loadedCodeSha256'],second['loadedCodeSha256'])
        self._import_literal_snapshot(relative=True,alias=True)
        self._import_literal_snapshot(star=True)
        self._import_literal_snapshot(foreign=True)
        self._import_literal_snapshot(copy=True)

    def test_imported_literals_retained_in_containers_are_verified(self):
        retentions=(
            ("retained={'scale':IMPORTED}\ndel IMPORTED\n", "retained['scale']"),
            ("retained=[IMPORTED]\ndel IMPORTED\n", "retained[0]"),
            ("retained=(IMPORTED,)\ndel IMPORTED\n", "retained[0]"),
            ("retained={'nested':[IMPORTED]}\ndel IMPORTED\n", "retained['nested'][0]"),
            ("first={'scale':IMPORTED}\nretained=first\ndel first,IMPORTED\n", "retained['scale']"),
            ("retained=IMPORTED*2\ndel IMPORTED\n", "retained//2"),
        )
        for retention in retentions:
            for mode in ('evict','reload','star-evict','star-reload'):
                with self.subTest(retention=retention,mode=mode):
                    self._import_literal_snapshot(value=2,retention=retention,
                                                  error='import|provider',**({'star':True,mode.split('-')[1]:True} if mode.startswith('star-') else {mode:True}))
            with self.subTest(retention=retention,mode='matching'):
                self._import_literal_snapshot(retention=retention)
                self._import_literal_snapshot(retention=retention,star=True)

    def test_non_declarative_import_retention_fails_closed(self):
        retentions=(
            ("retained={}\nretained['scale']=IMPORTED\ndel IMPORTED\n", "retained['scale']"),
            ("retained=[]\nretained.append(IMPORTED)\ndel IMPORTED\n", "retained[0]"),
            ("retained=frozenset([IMPORTED])\ndel IMPORTED\n", "next(iter(retained))"),
            ("for retained in [IMPORTED]: pass\ndel IMPORTED\n", "retained"),
            ("retained,*rest=[IMPORTED]\ndel IMPORTED\n", "retained"),
            ("match IMPORTED:\n    case retained: pass\ndel IMPORTED\n", "retained"),
            ("match {'scale':IMPORTED}:\n    case {'scale':retained}: pass\ndel IMPORTED\n", "retained"),
            ("def retained(value=IMPORTED): return value\ndel IMPORTED\n", "retained()"),
            ("def initialize(): return {'scale':IMPORTED}\nretained=initialize()\ndel initialize,IMPORTED\n", "retained['scale']"),
        )
        for retention in retentions:
            for mode in ({},{'reload':True},{'evict':True}):
                with self.subTest(retention=retention,mode=mode):
                    self._import_literal_snapshot(retention=retention,error='import|provider|default expression',**mode)

    def test_source_path_aliases_are_resolved_fresh_for_each_inspection(self):
        alias=Path(self.temp.name)/'source-alias.py'
        targets=[]
        for value in (1,2):
            path=self.core/f'alias-target-{value}.py';path.write_text(f'def read(): return {value}\n',encoding='utf-8');targets.append(path)
        try:alias.symlink_to(targets[0])
        except OSError as exc:self.skipTest(f'Symlink creation unavailable: {exc}')
        paths=[]
        for value,target in enumerate(targets,1):
            if value==2:alias.unlink();alias.symlink_to(target)
            module=types.ModuleType('alias_fixture');module.__file__=str(alias)
            exec(compile(alias.read_bytes(),str(alias),'exec'),vars(module))
            with patch.dict(sys.modules,{module.__name__:module},clear=True):
                rows=loaded_source_code([self.core]);paths.append(next(row['path'] for row in rows if row['path']==str(target.resolve())))
                self.assertEqual(module.read(),value)
        self.assertNotEqual(*paths)

    def test_stale_module_and_class_annotations_are_rejected(self):
        sources=(
            "SETTING: 1\ndef read(): return __annotations__['SETTING']\n",
            "SETTING: 1=0\ndef read(): return __annotations__['SETTING']\n",
            "if True:\n    SETTING: 1\n",
            "class Holder:\n    SETTING: 1\n",
            "class Outer:\n    class Holder:\n        SETTING: 1\n",
            "def factory():\n    class Holder:\n        SETTING: 1\n    return Holder\nretained=factory()\n",
            "from __future__ import annotations\nSETTING: list[Unknown[1]]\n",
            "from __future__ import annotations\nclass Holder:\n    __private: Unknown[1]\n",
        )
        for source in sources:
            temporary=source.replace(': 1',': 2').replace('[1]','[2]')
            with self.subTest(source=source):
                self.assert_snapshot_matches_source(source,temporary,error='annotation')
                self.assert_snapshot_matches_source(source)

    def test_scope_annotation_additions_removals_and_mutation_are_rejected(self):
        for before,after in (
            ('pass\n','SETTING: 2\n'),
            ('SETTING: 1\n','pass\n'),
            ('SETTING: 1\n',"SETTING: 1\n__annotations__['SETTING']=2\n"),
            ('class Holder: pass\n','class Holder:\n    SETTING: 2\n'),
            ('class Holder:\n    SETTING: 1\n','class Holder: pass\n'),
            ('class Holder:\n    SETTING: 1\n',"class Holder:\n    SETTING: 1\nHolder.__annotations__['SETTING']=2\n"),
        ):
            with self.subTest(before=before,after=after):
                self.assert_snapshot_matches_source(before,after,error='annotation')

    def test_scope_annotation_native_storage_and_builtin_controls(self):
        prefix="class Metadata(dict):\n    def items(self): raise AssertionError('metadata hook invoked')\n"
        for source in (
            'SETTING: int\n',
            'def sample():\n    local: UnresolvedLocalType\n    return 1\n',
            'class Holder:\n    SETTING: int\n',
            'class Holder:\n    __private: int\n',
            prefix+'SETTING: 1\n__annotations__=Metadata(SETTING=1)\n',
            prefix+'class Holder:\n    SETTING: 1\nHolder.__annotations__=Metadata(SETTING=1)\n',
        ):
            with self.subTest(source=source):self.assert_snapshot_matches_source(source)
        for source in ('int=1\nSETTING: int\n','class Holder:\n    int=1\n    SETTING: int\n',
                       'SETTING: object()\n','class Holder:\n    SETTING: object()\n','__annotations__=1\n',
                       'SETTING: 1\nSETTING: 2\n','class Holder:\n    SETTING: 1\n    SETTING: 2\n'):
            with self.subTest(source=source):self.assert_snapshot_matches_source(source,error='annotation')

    def test_evicted_module_annotations_still_bind_retained_functions(self):
        path=self.core/'comfy'/'model.py'
        reviewed="SETTING: 1\ndef read(): return __annotations__['SETTING']\n"
        for live in (1,2):
            module=types.ModuleType('annotation_owner');module.__file__=str(path)
            holder=types.ModuleType('foreign_holder')
            exec(compile(reviewed.replace(': 1',f': {live}'),str(path),'exec'),vars(module))
            holder.read=module.read;path.write_text(reviewed,encoding='utf-8')
            with self.subTest(live=live),patch.dict(sys.modules,{'foreign_holder':holder},clear=True):
                self.assertEqual(holder.read(),live)
                if live==2:
                    with self.assertRaisesRegex(ValueError,'annotation'):loaded_source_code([self.core])
                else:loaded_source_code([self.core])

    def test_scope_annotations_change_loaded_fingerprints(self):
        path=self.core/'comfy'/'model.py';digests=[]
        for value in (1,2):
            module=types.ModuleType('annotation_fingerprint');module.__file__=str(path)
            source=f'SETTING: {value}\ndef read(): return __annotations__["SETTING"]\n'
            path.write_text(source,encoding='utf-8');exec(compile(source,str(path),'exec'),vars(module))
            with patch.dict(sys.modules,{module.__name__:module},clear=True):
                rows=loaded_source_code([self.core]);digests.append(next(row['loadedCodeSha256'] for row in rows if row['path']==str(path.resolve())))
        self.assertNotEqual(*digests)

    def test_stale_function_annotations_are_rejected(self):
        sources=(
            "def sample(x: 1): return sample.__annotations__['x']\n",
            "def sample() -> 1: return sample.__annotations__['return']\n",
            "def sample(x: 1, /, y: 1=0, *args: 1, key: 1=0, **kwargs: 1) -> 1: pass\n",
            "async def sample(x: 1) -> 1: return x\n",
            "class Holder:\n    def sample(self, x: 1) -> 1: return x\n",
            "def sample(x: int) -> str: return str(x)\n",
            "from __future__ import annotations\ndef sample(x: Missing[1]) -> Other[1]: pass\n",
        )
        for source in sources:
            temporary=source.replace(': 1', ': 2').replace('-> 1', '-> 2').replace('[1]', '[2]')
            if 'x: int' in source:temporary=source.replace('x: int','x: float')
            with self.subTest(source=source):
                self.assert_snapshot_matches_source(source,temporary,error='annotation')
                self.assert_snapshot_matches_source(source)

    def test_annotation_additions_removals_and_mutation_are_rejected(self):
        sources=(
            ('def sample(x): pass\n','def sample(x: 2): pass\n'),
            ('def sample(x: 1): pass\n','def sample(x): pass\n'),
            ('def sample(x: 1): pass\n',"def sample(x: 1): pass\nsample.__annotations__['x']=2\n"),
            ('def sample(): pass\n',"def sample(): pass\nsample.__annotations__['extra']=2\n"),
        )
        for source,temporary in sources:
            with self.subTest(source=source,temporary=temporary):
                self.assert_snapshot_matches_source(source,temporary,error='annotation')

    def test_annotation_type_names_cannot_use_shadowed_builtins(self):
        for source in (
            'int=1\ndef sample(x: int): pass\n',
            'def outer(int=1):\n    def sample(x: int): pass\n    return sample\nretained=outer()\n',
            'class Holder:\n    int=1\n    def sample(self,x: int): pass\n',
        ):
            with self.subTest(source=source):self.assert_snapshot_matches_source(source,error='annotation')

    def test_annotation_forward_strings_and_private_parameters_are_supported(self):
        sources=(
            "def sample(x: 'Unloaded') -> 'Other': pass\n",
            "from __future__ import annotations\ndef sample(x: list[Unknown] | None) -> 'Quoted': pass\n",
            "class Holder:\n    def sample(self, __value: int) -> None: pass\n",
        )
        for source in sources:
            with self.subTest(source=source):self.assert_snapshot_matches_source(source)

    def test_annotation_dictionary_inspection_uses_native_storage(self):
        source=("class Metadata(dict):\n    def items(self): raise AssertionError('metadata hook invoked')\n"
                "def sample(x: 1): pass\nsample.__annotations__=Metadata(x=1)\n")
        self.assert_snapshot_matches_source(source)

    def test_imported_class_state_cannot_hide_stale_values(self):
        retentions=(
            ("class Holder:\n    scale=IMPORTED\ndel IMPORTED\n", "Holder.scale"),
            ("class Holder:\n    if True: scale=IMPORTED\ndel IMPORTED\n", "Holder.scale"),
            ("class Holder:\n    config={'scale':IMPORTED}\ndel IMPORTED\n", "Holder.config['scale']"),
            ("class Outer:\n    class Holder:\n        scale=IMPORTED\ndel IMPORTED\n", "Outer.Holder.scale"),
            ("class Holder:\n    scale=IMPORTED\nretained=Holder()\ndel Holder,IMPORTED\n", "retained.scale"),
            ("def factory():\n    class Holder:\n        scale=IMPORTED\n    return Holder\nretained=factory()\ndel factory,IMPORTED\n", "retained.scale"),
        )
        for retention in retentions:
            for mode in ({},{'evict':True},{'reload':True},{'alias':True,'reload':True},{'star':True,'evict':True}):
                with self.subTest(retention=retention,mode=mode):
                    self._import_literal_snapshot(value=2,retention=retention,error='class.*expression|import|provider',**mode)

    def test_imported_instance_and_attribute_state_fails_closed(self):
        retentions=(
            ("class Holder:\n    def __init__(self): self.scale=IMPORTED\nretained=Holder()\ndel IMPORTED\n", "retained.scale"),
            ("class Holder: pass\nHolder.scale=IMPORTED\ndel IMPORTED\n", "Holder.scale"),
            ("class Holder:\n    __slots__=('scale',)\n    def __init__(self): self.scale=IMPORTED\nretained=Holder()\ndel IMPORTED\n", "retained.scale"),
            ("class Base:\n    def __init__(self): self.scale=IMPORTED\nclass Holder(Base): pass\nretained=Holder()\ndel IMPORTED\n", "retained.scale"),
            ("class Holder: pass\nretained=[Holder()]\nretained[0].scale=IMPORTED\ndel IMPORTED\n", "retained[0].scale"),
            ("class Holder: pass\nretained=Holder()\nretained.scale=IMPORTED\ndel IMPORTED\n", "retained.scale"),
        )
        for retention in retentions:
            for mode in ({},{'reload':True},{'evict':True}):
                with self.subTest(retention=retention,mode=mode):
                    self._import_literal_snapshot(value=2,retention=retention,error='attribute.*expression|import|provider',**mode)

    def test_dynamic_import_cannot_recover_execution_capabilities(self):
        sources=(
            "__import__('builtins').exec('SCALE=1')",
            "from builtins import __dict__ as state\nstate['exec']('SCALE=1')",
            "from sys import __dict__ as state\nstate['modules']['builtins'].exec('SCALE=1')",
            "from importlib import __dict__ as state\nstate['import_module']('builtins').exec('SCALE=1')",
            "getattr(__import__('builtins'),'exec')('SCALE=1')",
            "load=__import__\nload('builtins').eval('1')",
            "from builtins import __import__ as load\nload('builtins').exec('SCALE=1')",
            "import importlib\nimportlib.import_module('builtins').exec('SCALE=1')",
            "from importlib import import_module as load\nload('builtins').exec('SCALE=1')",
            "__import__('sys').modules['builtins'].exec('SCALE=1')",
            "__import__('sys').modules.get('builtins').exec('SCALE=1')",
            "__import__('sys').modules.__getitem__('builtins').exec('SCALE=1')",
            "getattr(__import__('importlib'),'import_module')('builtins').exec('SCALE=1')",
            "getattr(__import__('builtins'),'__import__')('builtins').exec('SCALE=1')",
            "__import__.__call__('builtins').exec.__call__('SCALE=1')",
            "load=__import__\nmodule='builtins'\nload(module).exec('SCALE=1')",
            "import importlib\nloaders=[importlib]\nloaders[0].import_module('builtins').exec('SCALE=1')",
            "import sys\nregistries=[sys]\nregistries[0].modules['builtins'].exec('SCALE=1')",
            "import importlib\nimportlib.__dict__['import_module']('builtins').exec('SCALE=1')",
            "import sys\nsys.__dict__['modules']['builtins'].exec('SCALE=1')",
            "getattr(__import__('importlib'),'__dict__')['import_module']('builtins').exec('SCALE=1')",
        )
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace|dynamic'):_source_constants(source)
        source="__import__('builtins').exec('SCALE=1')\ndef read(): return SCALE\n"
        self.assert_snapshot_matches_source(source,source.replace('SCALE=1','SCALE=2'),error='namespace|dynamic')

    def test_ordinary_dynamic_imports_are_supported(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for source in ("module=__import__('math')\nSCALE=1", "import importlib\nmodule=importlib.import_module('math')\nSCALE=1"):
            with self.subTest(source=source):
                self.assertEqual(_source_constants(source),{'SCALE':1})
                self.assert_snapshot_matches_source(source)

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

    def test_loaded_stale_module_constants_are_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('shape_scale = 1.0\nLOOKUP = {"quality": 12}\n'
                    'def loaded_value():\n    return shape_scale + LOOKUP["quality"]\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_constants_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.shape_scale = 1.5
        module.LOOKUP['quality'] = 24
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy module constants differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_lowercase_module_constant_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('shape_scale = 1.0\n'
                    'def loaded_value():\n    return shape_scale\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_lowercase_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.shape_scale = 1.5
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy module constants differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_lowercase_mutable_module_setting_is_rejected(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('shape_settings = {"scale": 1.0}\n'
                    'def loaded_value():\n    return shape_settings["scale"]\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_mutable_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.shape_settings['scale'] = 1.5
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy module constants differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_class_literal_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('class Sampler:\n    scale = 1\n'
                    '    def sample(self):\n        return self.scale\n')
        temporary = reviewed.replace('scale = 1', 'scale = 2')
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_class_literal_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'class attributes differ from source'):
                loaded_source_code([self.core])

    def test_loaded_stale_instance_class_literal_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('class Sampler:\n    scale = 1\n'
                    '    def sample(self):\n        return self.scale\n'
                    'Sampler = Sampler()\n')
        temporary = reviewed.replace('scale = 1', 'scale = 2')
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_instance_class_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        self.assertEqual(module.Sampler.sample(), 2)
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'class attributes differ from source'):
                loaded_source_code([self.core])

    def test_loaded_stale_callable_decorator_instance_class_literal_is_rejected(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('def singleton(cls):\n    return cls()\n'
                    '@singleton\n'
                    'class Sampler:\n    scale = 1\n'
                    '    def __call__(self):\n        return self.scale\n')
        temporary = reviewed.replace('scale = 1', 'scale = 2')
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_callable_decorator_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        self.assertTrue(callable(module.Sampler))
        self.assertEqual(module.Sampler(), 2)
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'class attributes differ from source'):
                loaded_source_code([self.core])

    def assert_snapshot_matches_source(self, reviewed, temporary=None, error=None, full_census=False, external_modules=None):
        path = self.core / 'comfy' / 'model.py'
        module = types.ModuleType('headkit_comfy_expression_fixture')
        module.__file__ = str(path)
        # Match real import initialization: the module is visible before its body executes.
        with patch.dict(sys.modules,{**(external_modules or {}),module.__name__:module}):
            exec(compile(temporary or reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        try:
            # Unit fixtures enumerate only their declared source module. A separate
            # full-census integration case exercises the real host module graph.
            with patch.dict(sys.modules, {module.__name__: module}, clear=not full_census):
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        loaded_source_code([self.core])
                else:
                    loaded_source_code([self.core])
        finally:
            values=tuple(vars(module).values())
            for value in values:
                if type(value).__module__=='weakref' and type(value).__name__ in ('ProxyType','CallableProxyType'):continue
                if isinstance(value, asyncio.Task):
                    value.cancel()
                    loop=value.get_loop()
                    loop.run_until_complete(asyncio.gather(value, return_exceptions=True))
                elif isinstance(value, (types.GeneratorType, types.CoroutineType)):
                    value.close()
                elif isinstance(value, types.AsyncGeneratorType):
                    asyncio.run(value.aclose())
            for value in values:
                if type(value).__module__=='weakref' and type(value).__name__ in ('ProxyType','CallableProxyType'):continue
                if isinstance(value, asyncio.AbstractEventLoop):value.close()

    def test_stale_arithmetic_class_attributes_are_rejected(self):
        reviewed = ('class Sampler:\n    SCALE: float = 1+2\n'
                    '    def sample(self):\n        return self.SCALE\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('1+2', '1+1'),
                                            'class attributes differ from source')

    def test_stale_arithmetic_module_constants_are_rejected(self):
        reviewed = 'SCALE = 1+2\ndef sample():\n    return SCALE\n'
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('1+2', '1+1'),
                                            'module constants differ')

    def test_stale_arithmetic_closure_bindings_are_rejected(self):
        reviewed = ('def make_sampler():\n    scale = 1+2\n'
                    '    return lambda: scale\nsample = make_sampler()\ndel make_sampler\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('1+2', '1+1'),
                                            'function defaults or closure differ')

    def test_stale_arithmetic_inside_literal_containers_is_rejected(self):
        for reviewed, error in (
                ('SETTINGS = {"scale": [1+2]}\ndef sample(): return SETTINGS\n', 'module constants differ'),
                ('class Sampler:\n    SETTINGS = {"scale": (1+2,)}\n'
                 '    def sample(self): return self.SETTINGS\n', 'class attributes differ from source'),
                ('def sample(scale={"values": [1+2]}): return scale\n', 'function defaults or closure differ')):
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('1+2', '1+1'), error)

    def test_matching_arithmetic_settings_are_accepted(self):
        reviewed = ('SCALE = 1+2\nclass Sampler:\n    SETTINGS = {"scale": [1+2]}\n'
                    '    def sample(self, bias=2**3): return self.SETTINGS, bias\n'
                    'def make_sampler():\n    scale = -(1+2)\n'
                    '    return lambda: scale\nsample = make_sampler()\n')
        self.assert_snapshot_matches_source(reviewed)

    def test_constant_expression_evaluation_is_bounded_and_never_calls_source(self):
        from headkit.comfy_nodes.source_snapshot import _constant_ast_value, _UNMATCHED_LITERAL
        for expression in ('danger()', '{"scale": danger()}', '2**1000000', '1<<1000000',
                           '{**{}}', '[x for x in ()]', '(1 / 0)'):
            with self.subTest(expression=expression):
                self.assertIs(_constant_ast_value(ast.parse(expression, mode='eval').body), _UNMATCHED_LITERAL)
        self.assertEqual(_constant_ast_value(ast.parse('{"scale": [1+2, -(2**3)]}', mode='eval').body),
                         {"scale": [3, -8]})

    def test_source_assigned_callable_instance_literal_is_checked(self):
        reviewed = ('class Holder:\n    def __call__(self): return self.scale\n'
                    'holder = Holder()\nholder.scale = 1\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('holder.scale = 1', 'holder.scale = 2'),
                                            'instance attributes differ from source')

    def test_source_assigned_plain_instance_literal_is_checked(self):
        reviewed = 'class Holder: pass\nholder = Holder()\nholder.scale = 1+2\n'
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('1+2', '1+1'),
                                            'instance attributes differ from source')

    def test_source_assigned_slotted_instance_literal_is_checked(self):
        reviewed = ('class Holder:\n    __slots__ = ("scale",)\n'
                    '    def __call__(self): return self.scale\n'
                    'holder = Holder()\nholder.scale: int = 1\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale: int = 1', 'scale: int = 2'),
                                            'instance attributes differ from source')

    def test_instance_literal_is_checked_through_a_container_reference(self):
        reviewed = 'class Holder: pass\nholders = [Holder()]\nholders[0].scale = 1\n'
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                            'instance attributes differ from source')

    def test_instance_settings_are_bound_to_the_exact_object(self):
        reviewed = ('class Holder: pass\nfirst = Holder()\nsecond = Holder()\n'
                    'first.scale = 1\nsecond.scale = 2\n')
        temporary = reviewed.replace('first.scale = 1', 'first.scale = 2').replace('second.scale = 2', 'second.scale = 1')
        self.assert_snapshot_matches_source(reviewed, temporary, 'instance attributes differ from source')
        self.assert_snapshot_matches_source(reviewed)

    def test_constructor_literals_and_module_overrides_match_without_descriptors(self):
        reviewed = ('class Holder:\n    def __init__(self):\n        self.scale = 1\n'
                    '    @property\n    def dangerous(self): raise AssertionError("descriptor invoked")\n'
                    'holder = Holder()\nobject.__setattr__(holder, "runtime_cache", {"hits": 2})\n')
        self.assert_snapshot_matches_source(reviewed)
        overridden = ('class Holder:\n    def __init__(self):\n        self.scale = 1\n'
                      'holder = Holder()\nholder.scale = 2\n')
        self.assert_snapshot_matches_source(overridden)

    def test_mutable_instance_caches_remain_runtime_state(self):
        reviewed = ('class Holder: pass\nholder = Holder()\n'
                    'holder.runtime_cache = {"hits": 0}\nholder.runtime_cache["hits"] = 2\n')
        self.assert_snapshot_matches_source(reviewed)

    def test_stale_callback_retained_only_in_instance_state_is_rejected(self):
        reviewed = ('class Holder:\n    def __call__(self): return self.callback()\n'
                    'def callback(): return "reviewed"\n'
                    'holder = Holder()\nholder.callback = callback\ndel callback\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                            'Python code differs from its source')

    def test_retained_execution_objects_cannot_hide_stale_code(self):
        for factory in ('def stream():\n    yield 1\n',
                        'async def stream():\n    return 1\n',
                        'async def stream():\n    yield 1\n'):
            reviewed = factory + 'pending = stream()\ndel stream\n'
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace(' 1\n', ' 2\n'),
                                                    'Python code differs from its source')

    def test_matching_execution_objects_are_inspected_without_advancing(self):
        for factory in ('def stream():\n    raise AssertionError("executed")\n    yield 1\n',
                        'async def stream():\n    raise AssertionError("executed")\n    return 1\n',
                        'async def stream():\n    raise AssertionError("executed")\n    yield 1\n'):
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(factory + 'pending = stream()\ndel stream\n')

    def test_execution_frames_preserve_literal_closure_provenance(self):
        reviewed = ('def make_stream():\n    scale = 1\n'
                    '    def stream():\n        yield scale\n'
                    '    return stream()\npending = make_stream()\ndel make_stream\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                            'frame.*closure|defaults or closure differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_execution_frames_preserve_default_provenance_after_factory_deletion(self):
        for factory in ('def stream(scale=1):\n    yield scale\n',
                        'async def stream(scale=1):\n    return scale\n',
                        'async def stream(scale=1):\n    yield scale\n'):
            reviewed = factory + 'pending = stream()\ndel stream\n'
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale=1', 'scale=2'),
                                                    'frame.*default|defaults or closure differ')
                self.assert_snapshot_matches_source(factory + 'pending = stream(2)\ndel stream\n')

    def test_required_frame_arguments_are_bound_to_literal_creation_sites(self):
        for factory, call in (('def stream(scale):\n    yield scale\n', 'stream(1)'),
                              ('def stream(*, scale):\n    yield scale\n', 'stream(scale=1)')):
            reviewed = factory + f'pending = {call}\ndel stream\n'
            temporary = reviewed.replace(call, call.replace('1', '2'))
            with self.subTest(call=call):
                self.assert_snapshot_matches_source(reviewed, temporary, 'frame defaults or closure differ')
                self.assert_snapshot_matches_source(reviewed)

    def test_suspended_generator_locals_cannot_hide_stale_callbacks(self):
        reviewed = ('def callback(): return "reviewed"\n'
                    'def stream(callback):\n    yield None\n    yield callback()\n'
                    'pending = stream(callback)\nnext(pending)\ndel stream, callback\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                            'Python code differs from its source')
        self.assert_snapshot_matches_source(reviewed)

    def test_generator_and_coroutine_delegates_are_traversed(self):
        generator = ('def inner():\n    yield 1\n'
                     'def outer():\n    yield from inner()\n'
                     'pending = outer()\nnext(pending)\ndel inner, outer\n')
        coroutine = ('class Pause:\n    def __await__(self):\n        yield None\n'
                     'async def inner():\n    await Pause()\n    return 1\n'
                     'async def outer():\n    return await inner()\n'
                     'pending = outer()\npending.send(None)\ndel inner, outer\n')
        for reviewed in (generator, coroutine):
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace(' 1\n', ' 2\n'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_generator_expression_closures_are_checked(self):
        reviewed = ('def make_stream():\n    scale = 1\n'
                    '    return (scale for _ in (None,))\n'
                    'pending = make_stream()\ndel make_stream\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                            'frame.*closure|defaults or closure differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_builtin_iterator_wrappers_cannot_hide_stale_callbacks(self):
        for expression in ('map(callback, (None,))', 'filter(callback, (None,))',
                           'zip(map(callback, (None,)))', 'enumerate(map(callback, (None,)))',
                           'itertools.starmap(callback, ((None,),))', 'iter(callback, None)'):
            reviewed = ('import itertools\ndef callback(value=None): return "reviewed"\n'
                        f'pending = {expression}\ndel callback\n')
            with self.subTest(expression=expression):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_native_containers_cannot_hide_stale_callbacks(self):
        for expression in ('{callback: None}', 'types.MappingProxyType({callback: None})',
                           '{callback: None}.keys()', '{None: callback}.values()',
                           '{callback: None}.items()', 'collections.deque([callback])'):
            reviewed = ('import types, collections\ndef callback(): return "reviewed"\n'
                        f'pending = {expression}\ndel callback\n')
            with self.subTest(expression=expression):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_native_tasks_futures_and_cached_results_cannot_hide_stale_code(self):
        cached = ('import functools\ndef callback(): return "reviewed"\n'
                  '@functools.lru_cache()\ndef produce(): return callback\n'
                  'pending = produce\nproduce()\ndel callback, produce\n')
        task = ('import asyncio\nasync def stream(): return "reviewed"\n'
                'loop = asyncio.new_event_loop()\npending = loop.create_task(stream())\ndel stream\n')
        future = ('import asyncio\ndef callback(): return "reviewed"\n'
                  'loop = asyncio.new_event_loop()\npending = loop.create_future()\n'
                  'pending.set_result(callback)\ndel callback\n')
        for reviewed in (cached, task, future):
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_exception_and_weakref_state_cannot_hide_stale_callbacks(self):
        exception = ('def capture():\n    scale = 1\n    raise ValueError("fixture")\n'
                     'try:\n    capture()\nexcept ValueError as error:\n    pending = error\n'
                     'del capture\n')
        weakref = ('import weakref\nclass Holder: pass\n'
                   'def callback(ref): return "reviewed"\n'
                   'target = Holder()\npending = weakref.ref(target, callback)\ndel callback\n')
        for reviewed, temporary in ((exception, exception.replace('scale = 1', 'scale = 2')),
                                    (weakref, weakref.replace('"reviewed"', '"temporary"'))):
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, temporary, 'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_execution_carriers_with_the_full_host_module_census(self):
        reviewed = ('import asyncio\nasync def stream(): return "reviewed"\n'
                    'loop = asyncio.new_event_loop()\npending = loop.create_task(stream())\ndel stream\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                            'Python code differs from its source', full_census=True)
        self.assert_snapshot_matches_source(reviewed, full_census=True)

    def test_bound_builtin_execution_methods_retain_their_owner(self):
        reviewed = ('def stream():\n    yield 1\n'
                    'pending = stream().send\ndel stream\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('yield 1', 'yield 2'),
                                            'Python code differs from its source')

    def test_explicit_frames_and_tracebacks_cannot_hide_stale_code(self):
        frame = ('import sys\ndef capture():\n    scale = 1\n    return sys._getframe()\n'
                 'pending = capture()\ndel capture\n')
        traceback = ('def capture():\n    scale = 1\n    raise ValueError("fixture")\n'
                     'try:\n    capture()\nexcept ValueError as error:\n    pending = error.__traceback__\n'
                     'del capture\n')
        for reviewed in (frame, traceback):
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                                    'Python code differs from its source')

    def test_foreign_holder_storage_cannot_hide_stale_callbacks(self):
        factories = [(source,None) for source in (
            'pending = types.SimpleNamespace(callback=callback)\n',
            'pending = collections.UserDict(callback=callback)\n',
            'pending = types.SimpleNamespace(child=types.SimpleNamespace(callback=callback))\n',
            'pending = types.SimpleNamespace(callback=callback)\npending.cycle = pending\n',
        )]
        for definition in ("class Holder:\n    __slots__ = ('callback',)\n",
                           "class Base:\n    __slots__ = ('callback',)\nclass Holder(Base):\n    __slots__ = ()\n",
                           'class Holder(list): pass\n',
                           'class Holder(list):\n    def __iter__(self): raise AssertionError("iterator invoked")\n',
                           'class Holder(dict):\n    def items(self): raise AssertionError("items invoked")\n'):
            # Construct genuinely foreign holders in the harness, outside covered
            # source. The tested module imports them without dynamic execution.
            foreign=types.ModuleType('external_holder')
            exec(definition,vars(foreign))
            factories.append(('import external_holder as foreign\n'
                              'pending = foreign.Holder()\npending.callback = callback\ndel foreign\n',
                              {'external_holder':foreign}))
        for factory,external_modules in factories:
            reviewed = ('import types, collections\ndef callback(): return "reviewed"\n'
                        + factory + 'del callback\n')
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source',external_modules=external_modules)
                self.assert_snapshot_matches_source(reviewed,external_modules=external_modules)

    def test_foreign_holder_source_settings_are_checked(self):
        reviewed = 'import types\npending = types.SimpleNamespace()\npending.scale = 1\n'
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                            'instance attributes differ from source')
        self.assert_snapshot_matches_source(reviewed)

    def test_foreign_holder_inspection_never_invokes_properties(self):
        definition = ('class Holder:\n    def __getattribute__(self, name):\n'
                      '        if name in ("__dict__", "callback"): raise AssertionError("getter invoked")\n'
                      '        return object.__getattribute__(self, name)\n'
                      '    @property\n    def callback(self): raise AssertionError("property invoked")\n')
        foreign=types.ModuleType('external_holder')
        exec(definition,vars(foreign))
        external_modules={'external_holder':foreign}
        reviewed = ('import external_holder as foreign\n'
                    'def callback(): return "reviewed"\n'
                    'pending = foreign.Holder()\npending.stored = callback\ndel foreign, callback\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                            'Python code differs from its source',external_modules=external_modules)
        self.assert_snapshot_matches_source(reviewed,external_modules=external_modules)

    def test_foreign_subclass_keeps_source_defined_base_visible(self):
        reviewed = ('class Base:\n    SCALE = 1\n    def __call__(self): return self.SCALE\n'
                    'Foreign = type("Foreign", (Base,), {"__module__": "external_holder", "__slots__": ()})\n'
                    'pending = Foreign()\ndel Base, Foreign\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('SCALE = 1', 'SCALE = 2'),
                                            'class attributes differ from source')
        self.assert_snapshot_matches_source(reviewed)

    def test_foreign_subclass_keeps_source_constructor_settings_visible(self):
        reviewed = ('class Base:\n    def __init__(self): self.scale = 1\n'
                    '    def __call__(self): return self.scale\n'
                    'Foreign = type("Foreign", (Base,), {"__module__": "external_holder"})\n'
                    'pending = Foreign()\ndel Base, Foreign\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('self.scale = 1', 'self.scale = 2'),
                                            'instance attributes differ from source')
        self.assert_snapshot_matches_source(reviewed)

    def test_callable_and_partial_attribute_holders_cannot_hide_callbacks(self):
        for factory in ('def holder(): return None\npending = holder\ndel holder\n',
                        'import functools\npending = functools.partial(int)\n'):
            reviewed = ('def callback(): return "reviewed"\n' + factory
                        + 'pending.callback = callback\ndel callback\n')
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_opaque_foreign_referents_cannot_hide_stale_callbacks(self):
        factories = (
            'import ctypes\npending = ctypes.py_object(callback)\n',
            'import contextvars\nkey = contextvars.ContextVar("callback")\npending = contextvars.Context()\n'
            'pending.run(key.set, callback)\ndel key\n',
            'import types\npending = types.ModuleType("unregistered_holder")\npending.callback = callback\n',
            'Foreign = type("Foreign", (), {"__slots__": (), "__module__": "external_holder", '
            '"callback": staticmethod(callback)})\npending = Foreign()\ndel Foreign\n',
        )
        for factory in factories:
            reviewed = 'def callback(): return "reviewed"\n' + factory + 'del callback\n'
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_dead_foreign_weak_proxy_is_safe_to_inspect(self):
        reviewed = ('import weakref\nclass Target: pass\n'
                    'target = Target()\npending = weakref.proxy(target)\ndel target\n')
        self.assert_snapshot_matches_source(reviewed)

    def test_callable_holder_source_settings_are_checked(self):
        for factory in ('def pending(): return pending.scale\n',
                        'import functools\npending = functools.partial(int)\n'):
            reviewed = factory + 'pending.scale = 1\n'
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                                    'instance attributes differ from source')
                self.assert_snapshot_matches_source(reviewed)

    def test_callable_and_descriptor_native_metadata_cannot_hide_callbacks(self):
        factories = (
            'def pending(): pass\npending.__annotations__ = {"return": callback}\n',
            'pending = staticmethod(int)\npending.callback = callback\n',
            'pending = classmethod(int)\npending.callback = callback\n',
            'Foreign = type("Foreign", (property,), {"__module__": "external_holder"})\n'
            'pending = Foreign()\npending.callback = callback\ndel Foreign\n',
        )
        for factory in factories:
            reviewed = 'def callback(): return "reviewed"\n' + factory + 'del callback\n'
            with self.subTest(factory=factory):
                if '__annotations__' in factory:
                    # Opaque callable annotations now require postponed/string metadata.
                    self.assert_snapshot_matches_source(reviewed,error='annotation')
                    self.assert_snapshot_matches_source(reviewed,reviewed.replace('"reviewed"','"temporary"'),error='annotation')
                    continue
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

    def test_module_namespace_assignments_match_reviewed_source(self):
        for factory in ('globals()', 'locals()', 'vars()', 'namespace', 'builtins.globals()', 'scope()'):
            prefix={'namespace':'namespace = globals()\n','builtins.globals()':'import builtins\n',
                    'scope()':'from builtins import vars as scope\n'}.get(factory,'')
            reviewed=prefix+factory+"['SCALE'] = 1\ndef read(): return SCALE\n"
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed,reviewed.replace(' = 1',' = 2'),'module constants differ')
                self.assert_snapshot_matches_source(reviewed)

    def test_namespace_factory_aliases_and_compound_assignments_are_checked(self):
        reviewed="factory = globals\nnamespace = factory()\nif True:\n    namespace['SCALE'] = 1\ndef read(): return SCALE\n"
        self.assert_snapshot_matches_source(reviewed,reviewed.replace(' = 1',' = 2'),'module constants differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_assignment_expression_namespace_aliases_match_source(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        prefixes=(
            'namespace=(alias:=globals())\n',
            'import sys\nnamespace=(alias:=sys.modules[__name__].__dict__)\n',
            'import sys\ncurrent=(alias:=sys.modules[__name__])\nnamespace=vars(current)\n',
        )
        for prefix in prefixes:
            reviewed=prefix+"namespace['SCALE']=1\ndef read(): return SCALE\n"
            with self.subTest(prefix=prefix):
                self.assertEqual(_source_constants(reviewed),{'SCALE':1})
        reviewed=prefixes[0]+"namespace['SCALE']=1\ndef read(): return SCALE\n"
        self.assert_snapshot_matches_source(reviewed,reviewed.replace("['SCALE']=1","['SCALE']=2"),
                                            'module constants differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_conditional_namespace_values_fail_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        expressions=('globals() if True else {}','{} if False else globals()',
                     'globals() or {}','{} or globals()',
                     'alias if True else {}','alias or {}',
                     'sys.modules[__name__] if True else None',
                     'sys.modules.get if True else None')
        for expression in expressions:
            source='import sys\nalias=globals()\nnamespace='+expression+"\nnamespace['SCALE']=1\n"
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)
        for source in ("register(globals() if True else {})",'register(globals() or {})',
                       'def factory(): return globals() if True else {}',
                       'factory=lambda: (globals() or {})',
                       'def factory(scope=globals() if True else {}): pass'):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)
        source="SCALE=1\nnamespace=globals()\nvalue=namespace.get('SCALE') if True else 0\nother=namespace.get('SCALE') or 0\n"
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_comprehensions_cannot_hide_namespace_capabilities(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        expressions=('next(globals() for _ in (0,))',
                     '[globals() for _ in (0,)][0]',
                     '{globals for _ in (0,)}',
                     '{key: globals() for key in (0,)}[0]',
                     '{globals: key for key in (0,)}')
        for expression in expressions:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(ValueError,'namespace'):
                    _source_constants('namespace='+expression+"\nnamespace['SCALE']=1\n")
        source="SCALE=1\nnamespace=globals()\nvalues=[namespace.get('SCALE') for _ in (0,)]\n"
        self.assertEqual(_source_constants(source),{'SCALE':1})

    def test_namespace_callable_wrappers_match_source(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        prefixes=(
            'factory=globals.__call__\nnamespace=factory()\n',
            'factory=globals.__call__.__call__\nnamespace=factory()\n',
            'import builtins\nfactory=builtins.vars.__call__\nnamespace=factory()\n',
            'import sys\nlookup=sys.modules.get.__call__\ncurrent=lookup(__name__)\nnamespace=current.__dict__\n',
            'import sys\nlookup=sys.modules.__getitem__.__call__\ncurrent=lookup(__name__)\nnamespace=vars.__call__(current)\n',
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(_source_constants(prefix+"namespace['SCALE']=1\n"),{'SCALE':1})
        reviewed=prefixes[0]+"namespace['SCALE']=1\ndef read(): return SCALE\n"
        self.assert_snapshot_matches_source(reviewed,reviewed.replace("['SCALE']=1","['SCALE']=2"),
                                            'module constants differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_namespace_callable_introspection_fails_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for statement in ("factory=globals.__getattribute__('__call__')",
                          'factory=globals.__setattr__',
                          "factory=sys.modules.get.__getattribute__('__call__')",
                          "factory=sys.modules.__getattribute__('__getitem__')"):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError,'namespace'):
                    _source_constants('import sys\n'+statement)

    def test_namespace_readers_cannot_expose_native_owners_or_reducers(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        readers=('globals','globals.__call__','vars.__call__.__call__',
                 'sys.modules.get','sys.modules.get.__call__','sys.modules.__getitem__')
        attributes=('__self__','__reduce__','__reduce_ex__','__get__','__dict__','__name__')
        for reader in readers:
            for attribute in attributes:
                source='import sys\nreader='+reader+'.'+attribute+'\n'
                with self.subTest(reader=reader,attribute=attribute):
                    with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)
        source="factory=globals.__call__.__self__\nnamespace=factory()\nnamespace['SCALE']=1\ndef read(): return SCALE\n"
        self.assert_snapshot_matches_source(source,error='namespace')
        source="factory,args=globals.__call__.__reduce__()\nreader=factory(*args)\nnamespace=reader()\nnamespace['SCALE']=1\n"
        self.assert_snapshot_matches_source(source,error='namespace')

    def test_ordinary_bound_method_owners_remain_supported(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        source=('class Holder:\n    def read(self): return 1\n'
                'holder=Holder()\nmethod=holder.read\nowner=method.__self__\nSCALE=1\n')
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_match_patterns_cannot_capture_namespace_capabilities(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "match globals():\n    case namespace:\n        namespace['SCALE']=1\n",
            "match locals():\n    case namespace: pass\n",
            "match vars():\n    case namespace: pass\n",
            "namespace=globals()\nmatch namespace:\n    case alias if True: pass\n",
            "match (namespace:=globals()):\n    case alias: pass\n",
            "match globals():\n    case dict() as namespace: pass\n",
            "match globals():\n    case (dict() | dict()) as namespace: pass\n",
            "match globals():\n    case {'SCALE': value, **namespace}: pass\n",
            "match globals():\n    case [*namespace]: pass\n",
            "match globals:\n    case factory: pass\n",
            "import sys\nmatch sys.modules[__name__]:\n    case current:\n        current.SCALE=1\n",
            "import sys\nmatch sys.modules.get:\n    case lookup: pass\n",
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)
        self.assert_snapshot_matches_source(sources[0],sources[0].replace("['SCALE']=1","['SCALE']=2"),error='namespace')
        self.assert_snapshot_matches_source(sources[10],sources[10].replace('SCALE=1','SCALE=2'),error='namespace')

    def test_ordinary_patterns_and_nonbinding_namespace_matches_work(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "match globals():\n    case _:\n        globals()['SCALE']=1\n",
            "match {'value':1}:\n    case {'value':number}: pass\nSCALE=1\n",
            "def read(value):\n    match value:\n        case [first,*rest]: return first\nSCALE=1\n",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(sources[0])
        self.assert_snapshot_matches_source(sources[1])

    def test_dynamic_execution_and_aliases_fail_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "exec('SCALE=1')", "SCALE=eval('1')",
            "execute=exec\nexecute('SCALE=1')",
            "from builtins import exec as execute\nexecute('SCALE=1')",
            "import builtins\nbuiltins.exec('SCALE=1')",
            "exec.__call__('SCALE=1')",
            "import builtins\ngetattr(builtins,'exec')('SCALE=1')",
            "__builtins__['exec']('SCALE=1')",
            "__builtins__.get('eval')('1')",
            "import builtins\nbuiltins.__dict__['exec']('SCALE=1')",
            "import builtins\nvars(builtins)['exec']('SCALE=1')",
            "import builtins\nbuiltins.__getattribute__('exec')('SCALE=1')",
            "exec('SCALE=1',{})",
            "import types\nforeign=types.ModuleType('foreign')\nexec('SCALE=1',vars(foreign))",
            "def initialize():\n    exec('global SCALE; SCALE=1')\ninitialize()\ndel initialize",
            "def initialize(): return eval('1')\nSCALE=initialize()\ndel initialize",
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace|dynamic'):_source_constants(source)
        for source in ("exec('SCALE=1')\ndef read(): return SCALE\n",
                       "SCALE=eval('1')\ndef read(): return SCALE\n"):
            temporary=source.replace('SCALE=1','SCALE=2').replace("eval('1')","eval('2')")
            self.assert_snapshot_matches_source(source,temporary,error='namespace|dynamic')

    def test_dynamic_executor_capabilities_cannot_escape(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for expression in ('exec','eval','compile','builtins','exec.__call__'):
            for use in ('register({value})','holder=[{value}]','def factory(): return {value}'):
                source='import builtins\n'+use.format(value=expression)
                with self.subTest(source=source):
                    with self.assertRaisesRegex(ValueError,'namespace|dynamic'):_source_constants(source)

    def test_top_level_compilation_is_rejected_but_runtime_comparison_is_supported(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for prefix in ('', 'compiler=compile\n', 'from builtins import compile as compiler\n'):
            name='compiler' if prefix else 'compile'
            with self.subTest(prefix=prefix):
                with self.assertRaisesRegex(ValueError,'namespace|dynamic'):
                    _source_constants(prefix+name+"('pass','<dynamic>','exec')")
        source="def compare(text): return compile(text,'<comparison>','exec')\nSCALE=1\n"
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_ordinary_methods_named_exec_and_eval_are_supported(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        source=('class Worker:\n    def exec(self): return 1\n    def eval(self): return 1\n'
                'worker=Worker()\nworker.exec()\nworker.eval()\nSCALE=1\n')
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_namespace_mutation_and_ambiguous_writes_fail_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "globals().update(SCALE=1)",
            "namespace=globals()\nnamespace.update(SCALE=1)",
            "namespace=globals()\nset_value=namespace.__setitem__\nset_value('SCALE',1)",
            "globals()[choose_key()] = 1",
            "globals()['SCALE'] = choose_value()",
            "globals()['SCALE'] += 1",
            "del globals()['SCALE']",
            "other.__dict__['SCALE'] = 1",
            "vars(other)['SCALE'] = 1",
            "def initialize():\n    globals()['SCALE'] = 1\ninitialize()\ndel initialize",
            "class Holder:\n    locals()['SCALE'] = 1",
            "namespace=globals()\ndict.__setitem__(namespace,'SCALE',1)",
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)

    def test_namespace_alias_escapes_and_nested_mutators_fail_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "namespace=globals()\nholder.table=namespace\nholder.table['SCALE']=1",
            "holder=[globals()]\nholder[0]['SCALE']=1",
            "def initialize():\n    namespace=globals()\n    setter=getattr(namespace,'__setitem__')\n    setter('SCALE',1)",
            "def initialize():\n    import operator\n    operator.setitem(globals(),'SCALE',1)",
            "globals()['SCALE']=1\nSCALE=2",
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace|Ambiguous'):_source_constants(source)

    def test_namespace_capabilities_cannot_escape_static_analysis(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        sources=(
            "factory=globals\nif True:\n    factory=locals\nfactory()['SCALE']=1",
            "factory=[globals]\nfactory[0]()['SCALE']=1",
            "def factory():\n    return globals()\nfactory()['SCALE']=1",
            "factory=lambda: globals()\nfactory()['SCALE']=1",
            "factory=lambda: globals().__setitem__('SCALE',1)\nfactory()",
            "def initialize(namespace=globals()):\n    namespace['SCALE']=1\ninitialize()",
            "setter=globals().__setitem__\nregister(setter)",
        )
        for source in sources:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)

    def test_current_module_dictionary_aliases_are_checked(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for namespace in ('system.modules[__name__].__dict__', 'vars(system.modules[__name__])',
                          "getattr(system.modules[__name__],'__dict__')", 'table[__name__].__dict__'):
            prefix='from sys import modules as table\n' if namespace.startswith('table') else 'import sys as system\n'
            source=prefix+namespace+"['SCALE']=1\n"
            with self.subTest(namespace=namespace):
                self.assertEqual(_source_constants(source),{'SCALE':1})
                with self.assertRaisesRegex(ValueError,'namespace'):
                    _source_constants(prefix+'exec(payload,'+namespace+')')

    def test_current_module_attribute_writes_match_reviewed_source(self):
        cases=(
            ('import sys\n', 'sys.modules[__name__].SCALE = 1\n'),
            ('import sys as runtime\ncurrent=runtime.modules[__name__]\n', 'current.SCALE = 1\n'),
            ('from sys import modules as table\ncurrent=table[__name__]\n', 'if True:\n    current.SCALE: int = 1\n'),
            ('import sys\ncurrent=sys.modules[__name__]\n', '(current.SCALE, other) = (1, 9)\n'),
        )
        for prefix,assignment in cases:
            reviewed=prefix+assignment+'def read(): return SCALE\n'
            temporary=reviewed.replace(' = 1',' = 2').replace('(1, 9)','(2, 9)')
            with self.subTest(assignment=assignment):
                self.assert_snapshot_matches_source(reviewed,temporary,'module constants differ')
                self.assert_snapshot_matches_source(reviewed)

    def test_current_module_registry_lookup_aliases_are_checked(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        prefixes=(
            'import sys\nname=__name__\ncurrent=sys.modules[name]\n',
            'import sys\nname=__name__\nother=name\ncurrent=sys.modules[other]\n',
            'from sys import modules as registry\nname=__name__\ncurrent=registry[name]\n',
            'import sys\ncurrent=sys.modules.get(__name__)\n',
            'import sys\ncurrent=sys.modules.get(__name__,object())\n',
            'import sys\nregistry=sys.modules\ncurrent=registry.__getitem__(__name__)\n',
            'import sys\nlookup=sys.modules.get\ncurrent=lookup(__name__,None)\n',
            'import sys\nlookup=sys.modules.__getitem__\ncurrent=lookup(__name__)\n',
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertEqual(_source_constants(prefix+'current.SCALE=1\n'),{'SCALE':1})
                self.assertEqual(_source_constants(prefix+"vars(current)['SCALE']=1\n"),{'SCALE':1})
                with self.assertRaisesRegex(ValueError,'namespace'):
                    _source_constants(prefix+"setattr(current,'SCALE',1)\n")
        for prefix in (prefixes[0],prefixes[3]):
            reviewed=prefix+'current.SCALE=1\ndef read(): return current.SCALE\n'
            self.assert_snapshot_matches_source(reviewed,reviewed.replace('SCALE=1','SCALE=2'),
                                                'module constants differ')
            self.assert_snapshot_matches_source(reviewed)

    def test_registry_lookup_capabilities_cannot_escape_analysis(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        for expression in ('sys.modules','sys.modules.get','sys.modules.__getitem__'):
            for statement in ('holder=[{value}]','register({value})',
                              'holder.lookup={value}','def lookup(): return {value}'):
                source='import sys\n'+statement.format(value=expression)
                with self.subTest(source=source):
                    with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(source)

    def test_current_module_setters_and_attribute_mutations_fail_closed(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        prefix='import sys\ncurrent=sys.modules[__name__]\n'
        statements=(
            "setattr(current,'SCALE',1)",
            "assign=setattr\nassign(current,'SCALE',1)",
            "import builtins\nbuiltins.setattr(current,'SCALE',1)",
            "from builtins import setattr as assign\nassign(current,'SCALE',1)",
            "delattr(current,'SCALE')",
            "current.__setattr__('SCALE',1)",
            "assign=current.__setattr__\nassign('SCALE',1)",
            "getattr(current,'__setattr__')('SCALE',1)",
            "object.__setattr__(current,'SCALE',1)",
            "import functools\nassign=functools.partial(setattr,current,'SCALE')\nassign(1)",
            "current.__getattribute__('__setattr__')('SCALE',1)",
            "current.SCALE += 1", "del current.SCALE", "current.SCALE = compute()",
            "class Holder:\n    current.SCALE = 1",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(prefix+statement)
        self.assert_snapshot_matches_source(prefix+"setattr(current,'SCALE',1)\n",error='namespace')

    def test_current_module_escapes_are_rejected_and_reads_still_work(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        prefix='import sys\ncurrent=sys.modules[__name__]\n'
        for statement in ('register(current)', 'holder.module=current', 'holder=[current]',
                          'def factory(): return current', 'factory=lambda:current',
                          'def initialize(module=current): pass'):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(ValueError,'namespace'):_source_constants(prefix+statement)
        source=prefix+"SCALE=1\ndef read(): return current.SCALE + getattr(current,'SCALE') + vars(current)['SCALE']\n"
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_namespace_readers_and_ordinary_dictionaries_remain_supported(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        source="SCALE=1\nnamespace=globals()\nvalue=namespace.get('SCALE')\ncache={}\ncache['hits']=1\ncache.update(hits=2)\n"
        self.assertEqual(_source_constants(source),{'SCALE':1})
        self.assert_snapshot_matches_source(source)

    def test_compound_module_settings_cannot_hide_stale_values(self):
        blocks = ('if True:\n    SCALE = 1\n',
                  'try:\n    SCALE = 1\nexcept Exception:\n    pass\n',
                  'import contextlib\nwith contextlib.nullcontext():\n    SCALE = 1\n',
                  'for _ in (0,):\n    SCALE = 1\n',
                  'match 1:\n    case 1:\n        SCALE = 1\n',
                  'if True:\n    try:\n        SCALE = 1\n    finally:\n        pass\n')
        for block in blocks:
            reviewed = block + 'def read(): return SCALE\n'
            with self.subTest(block=block):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('SCALE = 1', 'SCALE = 2'),
                                                    'module constants differ')
                self.assert_snapshot_matches_source(reviewed)

    def test_compound_class_settings_cannot_hide_stale_values(self):
        for block in ('if True:\n    SCALE = 1\n',
                      'try:\n    SCALE = 1\nfinally:\n    pass\n'):
            body = ''.join('    ' + line for line in block.splitlines(keepends=True))
            reviewed = 'class Holder:\n' + body + '    def read(self): return self.SCALE\n'
            self.assert_snapshot_matches_source(reviewed, reviewed.replace('SCALE = 1', 'SCALE = 2'),
                                                'class attributes differ')
            self.assert_snapshot_matches_source(reviewed)

    def test_compound_attribute_and_constructor_settings_are_checked(self):
        module = ('import types\npending = types.SimpleNamespace()\n'
                  'if True:\n    pending.scale = 1\n')
        constructor = ('class Holder:\n    def __init__(self):\n'
                       '        if True:\n            self.scale = 1\n'
                       '    def read(self): return self.scale\n'
                       'pending = Holder()\ndel Holder.__init__\n')
        for reviewed in (module, constructor):
            self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                                'instance attributes differ')
            self.assert_snapshot_matches_source(reviewed)

    def test_identical_branch_bindings_are_checked_in_closures(self):
        reviewed = ('def make():\n    if True:\n        scale = 1\n'
                    '    else:\n        scale = 1\n'
                    '    def read(): return scale\n    return read\n'
                    'pending = make()\ndel make\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('scale = 1', 'scale = 2'),
                                            'defaults or closure differ')
        self.assert_snapshot_matches_source(reviewed)
        named = 'pending = (lambda: ((scale := 1), lambda: scale)[1])()\n'
        self.assert_snapshot_matches_source(named, named.replace(':= 1', ':= 2'),
                                            'defaults or closure differ')
        self.assert_snapshot_matches_source(named)

    def test_compound_frame_creation_arguments_are_checked(self):
        reviewed = ('def stream(scale):\n    yield scale\n'
                    'if True:\n    pending = stream(1)\ndel stream\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('stream(1)', 'stream(2)'),
                                            'frame defaults or closure differ')
        self.assert_snapshot_matches_source(reviewed)

    def test_unpacking_and_named_expression_settings_are_checked(self):
        for assignment in ('SCALE, other = (1, 9)\n', '(SCALE := 1)\n',
                           'first, (SCALE, *rest) = (0, (1, 2, 3))\n', 'SCALE = (other := 1)\n'):
            reviewed = assignment + 'def read(): return SCALE\n'
            temporary = reviewed.replace('(1,', '(2,').replace(':= 1', ':= 2')
            with self.subTest(assignment=assignment):
                self.assert_snapshot_matches_source(reviewed, temporary, 'module constants differ')
                self.assert_snapshot_matches_source(reviewed)

    def test_conflicting_conditional_settings_fail_closed(self):
        sources = (
            'if True:\n    SCALE = 1\nelse:\n    SCALE = 2\ndef read(): return SCALE\n',
            'SCALE = 1\nif True:\n    SCALE = 2\ndef read(): return SCALE\n',
            'SCALE = 1\nSCALE += 1\ndef read(): return SCALE\n',
            'SCALE = 1\nmatch 2:\n    case SCALE:\n        pass\ndef read(): return SCALE\n',
            'class Holder:\n    if True:\n        SCALE = 1\n    else:\n        SCALE = 2\n',
            'def make():\n    if True:\n        scale = 1\n    else:\n        scale = 2\n'
            '    def read(): return scale\n    return read\npending = make()\ndel make\n',
            'import types\npending = types.SimpleNamespace()\n'
            'if True:\n    pending.scale = 1\nelse:\n    pending.scale = 2\n',
            'def stream(scale):\n    yield scale\n'
            'if True:\n    pending = stream(1)\nelse:\n    pending = stream(2)\ndel stream\n',
        )
        for reviewed in sources:
            with self.subTest(source=reviewed):
                self.assert_snapshot_matches_source(reviewed, error='Ambiguous|Conflicting')

    def test_compound_collection_preserves_lexical_scope(self):
        from headkit.comfy_nodes.source_snapshot import _source_constants
        self.assertEqual(_source_constants('if explode():\n    SCALE = 1\n'), {'SCALE': 1})
        reviewed = ('SCALE = 1\nclass Holder:\n    if True:\n        SCALE = 2\n'
                    'def make():\n    if True:\n        SCALE = 3\n    return SCALE\n')
        self.assert_snapshot_matches_source(reviewed)

    def test_conflicting_redeclared_classes_fail_closed(self):
        reviewed = ('if True:\n    class Holder:\n        SCALE = 1\n'
                    'else:\n    class Holder:\n        SCALE = 2\n')
        self.assert_snapshot_matches_source(reviewed, error='Ambiguous|Conflicting')
        constructor = ('class Holder:\n    if True:\n        def __init__(self): self.scale = 1\n'
                       '    else:\n        def __init__(self): self.scale = 2\n')
        self.assert_snapshot_matches_source(constructor, error='Ambiguous|Conflicting')

    def test_loaded_mutable_class_runtime_cache_is_not_a_source_constant(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ("class Sampler:\n    runtime_cache = {'hits': 0}\n"
                    '    def sample(self):\n        return self.runtime_cache\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_mutable_comfy_class_cache_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.Sampler = module.Sampler()
        module.Sampler.__class__.runtime_cache['hits'] = 1
        with patch.dict(sys.modules, {module.__name__: module}):
            loaded_source_code([self.core])


    def test_dynamic_module_settings_change_the_runtime_fingerprint(self):
        import os
        variants=(
            "SCALE=int(os.environ['HEADKIT_RUNTIME_SETTING'])",
            "scale=int(os.environ['HEADKIT_RUNTIME_SETTING'])",
            "SCALE: int=int(os.environ['HEADKIT_RUNTIME_SETTING'])",
            "SCALE,other=(int(os.environ['HEADKIT_RUNTIME_SETTING']),0)",
            "for SCALE in [int(os.environ['HEADKIT_RUNTIME_SETTING'])]: pass",
            "if (SCALE:=int(os.environ['HEADKIT_RUNTIME_SETTING'])): pass",
            "config=dict(scale=int(os.environ['HEADKIT_RUNTIME_SETTING']))",
            "temporary=int(os.environ['HEADKIT_RUNTIME_SETTING'])\nSCALE=temporary\ndel temporary",
            "def initialize():\n    global SCALE\n    SCALE=int(os.environ['HEADKIT_RUNTIME_SETTING'])\ninitialize()",
        )
        path=self.core/'comfy'/'model.py'
        for assignment in variants:
            with self.subTest(assignment=assignment):
                source='import os\n'+assignment+'\ndef read(): return 1\n'
                path.write_text(source,encoding='utf-8');snapshots=[]
                for value in ('1','2','1'):
                    module=types.ModuleType('dynamic_settings_fixture');module.__file__=str(path)
                    with patch.dict(os.environ,{'HEADKIT_RUNTIME_SETTING':value}):
                        exec(compile(source,str(path),'exec',dont_inherit=True),vars(module))
                    with patch.dict(sys.modules,{'os':os,module.__name__:module},clear=True):
                        snapshots.append(loaded_source_code([self.core]))
                self.assertEqual(snapshots[0],snapshots[2])
                self.assertNotEqual(snapshots[0],snapshots[1])

    def test_dynamic_settings_cannot_change_during_inspection(self):
        from headkit.comfy_nodes import source_snapshot
        source="SCALE=int('1')\ndef read(): return SCALE\n"
        path=self.core/'comfy'/'model.py';path.write_text(source,encoding='utf-8')
        module=types.ModuleType('changing_settings');module.__file__=str(path)
        exec(compile(source,str(path),'exec',dont_inherit=True),vars(module))
        original=source_snapshot._source_import_literals
        def mutate(*args,**kwargs):
            result=original(*args,**kwargs);module.SCALE=2;return result
        with patch.dict(sys.modules,{module.__name__:module},clear=True), \
             patch.object(source_snapshot,'_source_import_literals',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'runtime settings changed'):
                loaded_source_code([self.core])

    def test_dynamic_settings_in_retained_function_globals_are_bound(self):
        source='SCALE=int(seed)\ndef read(): return SCALE\n'
        path=self.core/'comfy'/'model.py';path.write_text(source,encoding='utf-8')
        snapshots=[]
        for seed in ('1','2'):
            module=types.ModuleType('evicted_dynamic_settings');module.__file__=str(path);module.seed=seed
            exec(compile(source,str(path),'exec',dont_inherit=True),vars(module))
            holder=types.ModuleType('retained_holder');holder.callback=module.read
            with patch.dict(sys.modules,{holder.__name__:holder},clear=True):
                snapshots.append(loaded_source_code([self.core]))
        self.assertNotEqual(snapshots[0],snapshots[1])

    def test_loaded_mutable_runtime_cache_is_not_a_source_constant(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('runtime_cache = {"hits": 0}\n'
                    'def loaded_value():\n    return runtime_cache["hits"]\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_mutable_comfy_cache_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.runtime_cache['hits'] = 1
        with patch.dict(sys.modules, {module.__name__: module}):
            loaded_source_code([self.core])

    def test_loaded_stale_function_literal_default_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value(scale=1):\n    return scale\n'
        temporary = 'def loaded_value(scale=2):\n    return scale\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_default_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_function_constant_expression_default_is_rejected(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value(scale=1+1):\n    return scale\n'
        temporary = 'def loaded_value(scale=1+2):\n    return scale\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_constant_default_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_unsupported_function_default_fails_closed(self):
        path = self.core / 'comfy' / 'model.py'
        source = ('def make_default():\n    return 2\n'
                  'def loaded_value(scale=make_default()):\n    return scale\n')
        path.write_text(source, encoding='utf-8')
        module = types.ModuleType('headkit_unmatched_comfy_default_fixture')
        module.__file__ = str(path)
        exec(compile(source, str(path), 'exec', dont_inherit=True), module.__dict__)
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'default expression cannot be safely matched'):
                loaded_source_code([self.core])

    def test_loaded_constant_expression_default_matching_source_is_accepted(self):
        path = self.core / 'comfy' / 'model.py'
        source = 'def loaded_value(scale=1+1):\n    return scale\n'
        path.write_text(source, encoding='utf-8')
        module = types.ModuleType('headkit_comfy_constant_default_fixture')
        module.__file__ = str(path)
        exec(compile(source, str(path), 'exec', dont_inherit=True), module.__dict__)
        with patch.dict(sys.modules, {module.__name__: module}):
            loaded_source_code([self.core])

    def test_loaded_stale_lambda_literal_default_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'loaded_value = lambda scale=1: scale\n'
        temporary = 'loaded_value = lambda scale=2: scale\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_lambda_default_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_same_line_lambda_default_is_matched_by_body_span(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'first = lambda scale=3: scale; second = lambda scale=2: scale\n'
        temporary = 'first = lambda scale=1: scale; second = lambda scale=2: scale\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_same_line_lambdas_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_lambda_literal_closure_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('def make_value():\n    scale = 1\n'
                    '    return lambda: scale\nloaded_value = make_value()\n')
        temporary = reviewed.replace('scale = 1', 'scale = 2')
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_lambda_closure_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_reviewed_lambdas_with_defaults_and_closures_are_accepted(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('def make_value():\n    scale = 1\n'
                    '    return lambda bias=2: scale + bias\n'
                    'first = lambda scale=3: scale; second = lambda scale=4: scale\n'
                    'loaded_value = make_value()\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_reviewed_comfy_lambdas_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        with patch.dict(sys.modules, {module.__name__: module}):
            loaded_source_code([self.core])

    def test_loaded_stale_decorated_function_literal_default_is_rejected(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('def identity(function):\n    return function\n'
                    '@identity\n'
                    'def loaded_value(scale=1):\n    return scale\n')
        temporary = reviewed.replace('scale=1', 'scale=2')
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_decorated_default_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])


    def test_loaded_stale_literal_closure_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = ('def make_value():\n    scale = 1\n'
                    '    def loaded_value():\n        return scale\n'
                    '    return loaded_value\nloaded_value = make_value()\n')
        path.write_text(reviewed, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_closure_literal_fixture')
        module.__file__ = str(path)
        exec(compile(reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        original = module.loaded_value
        def captured(value):
            def read(): return value
            return read.__closure__[0]
        module.loaded_value = types.FunctionType(original.__code__, module.__dict__,
                                                 closure=(captured(2),))
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'function defaults or closure differ'):
                loaded_source_code([self.core])

    def test_loaded_stale_function_in_partial_is_rejected_after_disk_restore(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value():\n    return "reviewed"\n'
        temporary = 'def loaded_value():\n    return "temporary"\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_partial_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)
        module.dispatch = functools.partial(module.loaded_value)
        del module.loaded_value
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy Python code differs'):
                loaded_source_code([self.core])

    def test_loaded_stale_function_in_callable_wrapper_is_rejected(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value():\n    return "reviewed"\n'
        temporary = 'def loaded_value():\n    return "temporary"\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_wrapper_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)

        class CallableWrapper:
            def __init__(self, function):
                self.__wrapped__ = function

            def __call__(self):
                return self.__wrapped__()

        module.dispatch = CallableWrapper(module.loaded_value)
        del module.loaded_value
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy Python code differs'):
                loaded_source_code([self.core])

    def test_loaded_decorator_closure_cannot_hide_stale_comfy_function(self):
        path = self.core / 'comfy' / 'model.py'
        reviewed = 'def loaded_value():\n    return "reviewed"\n'
        temporary = 'def loaded_value():\n    return "temporary"\n'
        path.write_text(temporary, encoding='utf-8')
        module = types.ModuleType('headkit_stale_comfy_closure_fixture')
        module.__file__ = str(path)
        exec(compile(temporary, str(path), 'exec', dont_inherit=True), module.__dict__)

        def decorate(function):
            def wrapper():
                return function()
            return wrapper

        module.loaded_value = decorate(module.loaded_value)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(ValueError, 'Loaded Comfy Python code differs'):
                loaded_source_code([self.core])

    def test_code_hash_is_independent_of_constant_object_sharing(self):
        from headkit.comfy_nodes.source_snapshot import _code_hash
        code = compile('def sample(): return ("a", "a")', '<fixture>', 'exec').co_consts[0]
        text = 'constant with spaces'
        duplicate = text.encode().decode()
        self.assertIsNot(text, duplicate)
        shared = code.replace(co_consts=(None, (text, text)))
        copied = code.replace(co_consts=(None, (text, duplicate)), co_filename='<other-file>')
        self.assertEqual(_code_hash(shared), _code_hash(copied))
        changed = code.replace(co_consts=(None, (text, 'changed')))
        self.assertNotEqual(_code_hash(shared), _code_hash(changed))

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

    def test_verified_loader_wrappers_pass_their_own_startup_source_guard(self):
        from headkit.comfy_nodes import verified_loaders
        class Loader:
            RETURN_TYPES = ('MODEL',)
            FUNCTION = 'load'
            @classmethod
            def INPUT_TYPES(cls):
                return {'required': {'unet_name': (['fixture.safetensors'],)}}
            def load(self, unet_name):
                return (unet_name,)
        wrappers = verified_loaders.verified_loader_mappings({'UNETLoader': Loader}, types.SimpleNamespace())
        self.assertEqual(len(wrappers), 1)
        with patch.dict(vars(verified_loaders), {'_SNAPSHOT_TEST_WRAPPERS': wrappers}):
            rows = loaded_source_code([Path(verified_loaders.__file__).parent])
        self.assertTrue(any(row['path'] == str(Path(verified_loaders.__file__).resolve()) for row in rows))

    def test_adapter_startup_capture_is_atomic_on_failure(self):
        source = Path(__file__).parent / 'comfy_nodes' / '__init__.py'
        tree = ast.parse(source.read_bytes())
        helper = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == '_capture_startup')
        inventory = {'roots': ['fixture']}
        loaded = [{'path': 'fixture'}]
        identity = {'fingerprint': 'fixture'}
        folders = types.SimpleNamespace(base_path='fixture')
        namespace = {'Path': Path, '__file__': str(source), 'folder_paths': folders,
                     'load_inventory': Mock(return_value=inventory),
                     'loaded_source_code': Mock(return_value=loaded),
                     'capture_runtime_identity': Mock(return_value=identity)}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), 'exec'), namespace)
        self.assertEqual(namespace['_capture_startup'](), (inventory, loaded, identity))
        namespace['loaded_source_code'].assert_called_once_with(inventory['roots'])
        namespace['capture_runtime_identity'].assert_called_once_with(folders, inventory, loaded)
        namespace['capture_runtime_identity'].side_effect = ValueError('invalid runtime')
        self.assertEqual(namespace['_capture_startup'](), (None, None, None))
        namespace['load_inventory'].side_effect = OSError('missing inventory')
        self.assertEqual(namespace['_capture_startup'](), (None, None, None))

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
