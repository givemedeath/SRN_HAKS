"""Published binaries against their ASCII sources: normalised, sign-insensitive controller comparison."""
from pathlib import Path
import struct
import tempfile
import unittest

from . import anim_library as lib
from . import test_anim_library as fixtures
from .rig_native import compare


class NativeControllerTests(unittest.TestCase):
    def library(self, root):
        manifest, stock = fixtures.LibraryBuildTests().release(root); out = root/'build'
        lib.build(root, manifest, stock, 'pfx0', 'pfx2', 'srn_an_xf', out, allowed=['slash'])
        ascii_path = out/'converted/ascii/srn_an_xf.mdl'
        binary = root/'srn_an_xf.mdl'; binary.write_bytes(fixtures.simulated_compile(ascii_path.read_text()))
        return binary, ascii_path

    def test_compiled_library_matches_its_ascii_source_up_to_quaternion_sign(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            report = compare(binary, ascii_path)
            self.assertTrue(report['passed'], report['failures'])
            self.assertEqual(report['publishedInventory']['parent'], 'a_fa')
            # Negating every component of a stored quaternion is the same rotation.
            blob = bytearray(binary.read_bytes()); model = lib.NativeModel(bytes(blob)).decode()
            a, b = model['clips']['run']['nodes']['rootdummy']['controls'][20]['dataRange']
            values = struct.unpack(f'<{(b-a)//4}f', blob[a:b]); blob[a:b] = struct.pack(f'<{len(values)}f', *(-v for v in values))
            flipped = Path(tmp)/'flipped.mdl'; flipped.write_bytes(bytes(blob))
            self.assertTrue(compare(flipped, ascii_path)['passed'])

    def test_changed_keys_and_headers_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            blob = bytearray(binary.read_bytes()); model = lib.NativeModel(bytes(blob)).decode()
            a, _ = model['clips']['run']['nodes']['rootdummy']['controls'][20]['dataRange']; blob[a:a+4] = struct.pack('<f', 0.5)
            changed = Path(tmp)/'changed.mdl'; changed.write_bytes(bytes(blob))
            report = compare(changed, ascii_path)
            self.assertFalse(report['passed']); self.assertEqual(report['failures'], ['run'])
            self.assertGreater(report['clips']['run']['rotationDegrees'], 1.)
            repointed = Path(tmp)/'repointed.mdl'; repointed.write_bytes(lib.repoint(binary.read_bytes(), 'a_ba'))
            self.assertEqual(compare(repointed, ascii_path)['headerDifferences'], {'parent': ('a_ba', 'a_fa')})

    def test_zero_length_or_non_finite_quaternions_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            blob = bytes(binary.read_bytes()); model = lib.NativeModel(blob).decode()
            a, b = model['clips']['run']['nodes']['rootdummy']['controls'][20]['dataRange']
            def patched(value):
                bad = bytearray(blob); bad[a:b] = struct.pack(f'<{(b-a)//4}f', *[value]*((b-a)//4))
                path = Path(tmp)/'bad.mdl'; path.write_bytes(bytes(bad)); return path
            report = compare(patched(0.), ascii_path)
            self.assertFalse(report['passed']); self.assertEqual(report['failures'], ['run'])
            self.assertEqual(report['clips']['run']['invalidControllers'], {'published': ['rootdummy:orientation:zero-quaternion'], 'source': []})
            # The native reader already refuses non-finite keys outright.
            with self.assertRaisesRegex(ValueError, 'Nonfinite controller'):
                compare(patched(float('nan')), ascii_path)

    def test_static_hierarchy_and_bind_transforms_are_compared(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            report = compare(binary, ascii_path)
            self.assertEqual(report['staticRig']['differences'], []); self.assertGreater(report['staticRig']['nodes'], 1)
            model = lib.NativeModel(binary.read_bytes()).decode(); text = ascii_path.read_text()
            child = next(n for n, row in model['nodes'].items() if row['parent'] and row['parent'] != model['name'])
            line = text.index('parent ', text.index(f'node dummy {child}\n')); end = text.index('\n', line)
            def variant(name, replacement):
                path = Path(tmp)/name; path.write_text(text[:line] + replacement + text[end:]); return compare(binary, path)
            # A moved bind position fails although every clip is unchanged.
            report = variant('moved.mdl', text[line:end] + '\n  position 0 0 0.01')
            self.assertFalse(report['passed']); self.assertEqual(report['failures'], [])
            self.assertEqual(report['staticRig']['differences'], [f'{child}: bind transform differs (0.01 m, 0 deg)'])
            # So does a static bind scale.
            report = variant('scaled.mdl', text[line:end] + '\n  scale 1.5')
            self.assertFalse(report['passed']); self.assertEqual(report['staticRig']['differences'], [f'{child}: bind scale 1 != 1.5'])
            # So does a reparented node.
            report = variant('reparented.mdl', 'parent ' + model['name'])
            self.assertFalse(report['passed']); self.assertTrue(report['staticRig']['differences'][0].startswith(f'{child}: parent'))

    def test_published_controllers_the_ascii_source_cannot_hold_fail(self):
        from unittest.mock import patch
        import numpy as np
        from . import rig_native
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            def scaled(path, blob=None):
                model = lib.load_model(path, blob)
                if model['format'] == 'binary':
                    node = next(iter(model['clips']['run']['nodes'].values()))
                    node['controls'][36] = {'times': np.array([0.]), 'values': np.array([[1.5]])}
                return model
            with patch.object(rig_native, 'load_model', side_effect=scaled):
                report = compare(binary, ascii_path)
            self.assertFalse(report['passed']); self.assertEqual(report['failures'], ['run'])
            self.assertEqual(report['clips']['run']['notComparedControllers'], ['controller36'])

    def test_keyed_bind_controllers_fail(self):
        from unittest.mock import patch
        import numpy as np
        from . import rig_native
        with tempfile.TemporaryDirectory() as tmp:
            binary, ascii_path = self.library(Path(tmp))
            def keyed(path, blob=None):
                model = lib.load_model(path, blob)
                if model['format'] == 'binary':
                    name, node = next((n, row) for n, row in model['nodes'].items() if row['parent'])
                    node['controls'][8] = {'times': np.array([0., 1.]), 'values': np.array([[0., 0., 0.], [0., 0., .5]])}
                    keyed.node = name
                return model
            with patch.object(rig_native, 'load_model', side_effect=keyed):
                report = compare(binary, ascii_path)
            self.assertFalse(report['passed']); self.assertEqual(report['failures'], [])
            self.assertEqual(report['staticRig']['differences'], [f'{keyed.node}: published bind controllers keyed over time: position'])


if __name__ == '__main__':
    unittest.main()
