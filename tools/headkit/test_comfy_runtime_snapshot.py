"""Focused regressions for the adapter's loaded-Comfy source identity guard."""
import ast
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

    def assert_snapshot_matches_source(self, reviewed, temporary=None, error=None):
        path = self.core / 'comfy' / 'model.py'
        module = types.ModuleType('headkit_comfy_expression_fixture')
        module.__file__ = str(path)
        exec(compile(temporary or reviewed, str(path), 'exec', dont_inherit=True), module.__dict__)
        path.write_text(reviewed, encoding='utf-8')
        with patch.dict(sys.modules, {module.__name__: module}):
            if error:
                with self.assertRaisesRegex(ValueError, error):
                    loaded_source_code([self.core])
            else:
                loaded_source_code([self.core])

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
