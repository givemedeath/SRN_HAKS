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


if __name__ == '__main__':
    unittest.main()
