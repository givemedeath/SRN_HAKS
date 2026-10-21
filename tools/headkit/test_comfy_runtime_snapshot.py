"""Focused regressions for the adapter's loaded-Comfy source identity guard."""
import ast
import asyncio
import functools
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

    def assert_snapshot_matches_source(self, reviewed, temporary=None, error=None, full_census=False):
        path = self.core / 'comfy' / 'model.py'
        module = types.ModuleType('headkit_comfy_expression_fixture')
        module.__file__ = str(path)
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
        factories = [
            'pending = types.SimpleNamespace(callback=callback)\n',
            'pending = collections.UserDict(callback=callback)\n',
            'pending = types.SimpleNamespace(child=types.SimpleNamespace(callback=callback))\n',
            'pending = types.SimpleNamespace(callback=callback)\npending.cycle = pending\n',
        ]
        for definition in ("class Holder:\n    __slots__ = ('callback',)\n",
                           "class Base:\n    __slots__ = ('callback',)\nclass Holder(Base):\n    __slots__ = ()\n",
                           'class Holder(list): pass\n',
                           'class Holder(list):\n    def __iter__(self): raise AssertionError("iterator invoked")\n',
                           'class Holder(dict):\n    def items(self): raise AssertionError("items invoked")\n'):
            factories.append('foreign = types.ModuleType("external_holder")\n'
                             f'exec({definition!r}, vars(foreign))\n'
                             'pending = foreign.Holder()\npending.callback = callback\ndel foreign\n')
        for factory in factories:
            reviewed = ('import types, collections\ndef callback(): return "reviewed"\n'
                        + factory + 'del callback\n')
            with self.subTest(factory=factory):
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

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
        reviewed = ('import types\nforeign = types.ModuleType("external_holder")\n'
                    f'exec({definition!r}, vars(foreign))\n'
                    'def callback(): return "reviewed"\n'
                    'pending = foreign.Holder()\npending.stored = callback\ndel foreign, callback\n')
        self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                            'Python code differs from its source')
        self.assert_snapshot_matches_source(reviewed)

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
                self.assert_snapshot_matches_source(reviewed, reviewed.replace('"reviewed"', '"temporary"'),
                                                    'Python code differs from its source')
                self.assert_snapshot_matches_source(reviewed)

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
