"""Verify the fixed pelvis diffuse and normal compiler dependency boundary."""
from pathlib import Path
import tempfile
import unittest
from build_test_module import validate_owned_normal_dependencies
from pipeline import digest


class FixedMaterialDependencies(unittest.TestCase):
    def test_both_fixed_diffuse_and_normal_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'pmh0_pelvis001f.mtr').write_text('renderhint NormalTangents\ntexture0 pmh0_pelvis001f\ntexture1 pmh0_pelvis001n\n')
            (root/'pmh0_pelvis001f.tga').write_bytes(b'frozen fixed cloth pixels')
            (root/'pmh0_pelvis001n.tga').write_bytes(b'frozen authored normal pixels')
            hashes = {p.name:digest(p) for p in root.iterdir()}
            validate_owned_normal_dependencies(root, hashes)
            for name in ('pmh0_pelvis001f.tga', 'pmh0_pelvis001n.tga'):
                missing = dict(hashes); missing.pop(name)
                with self.assertRaisesRegex(RuntimeError, 'Missing/stale compile-time'):
                    validate_owned_normal_dependencies(root, missing)
            (root/'pmh0_pelvis001f.tga').write_bytes(b'changed after compiler')
            with self.assertRaisesRegex(RuntimeError, 'Missing/stale compile-time'):
                validate_owned_normal_dependencies(root, hashes)


if __name__ == '__main__': unittest.main()
