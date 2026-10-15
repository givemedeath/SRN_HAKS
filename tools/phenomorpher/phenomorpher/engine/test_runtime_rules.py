"""Runtime layout rules: shared libraries over the installed chain, no private carriers, 1K textures."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from . import anim_library as lib
from .runtime_release import adopt
from .runtime_rules import check
from . import test_runtime_release as fixtures


def staged(root):
    """Adopt the fixture release and return its contract plus the staged files as an overlay."""
    plan = fixtures.AdoptionTests().release(root); adopt(root, root/'plan.json', root/'staged')
    contract = json.loads((root/'staged/game-ready-assets.json').read_text())
    overlay = {p.relative_to(root/'staged/files').as_posix(): p.read_bytes() for p in (root/'staged/files').rglob('*') if p.is_file()}
    return plan, contract, overlay


def rules(report):
    return sorted({v['rule'] for v in report['violations']})


class RuntimeRuleTests(unittest.TestCase):
    def test_adopted_release_passes_and_the_carrier_release_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan, contract, overlay = staged(root)
            receipt = json.loads((root/'staged/adoption-receipt.json').read_text())
            self.assertTrue(receipt['runtimeRules']['passed'])
            report = check(root, contract, overlay=overlay)
            self.assertTrue(report['passed'], report['violations'])
            self.assertEqual(report['chains']['pfx0'], ['pfx0', 'srn_an_xf', 'a_fa'])
            old = check(root, root/plan['baseContract']['path'])
            self.assertFalse(old['passed'])
            self.assertEqual(old['violationCounts']['private-carrier'], 2)
            self.assertIn('stock-closure', rules(old))
            # The staged 4 px textures exceed a 2 px cap.
            self.assertEqual(rules(check(root, contract, max_texture=2, overlay=overlay)), ['texture-size'])

    def test_library_evidence_gender_and_fit_large_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, contract, overlay = staged(root)
            row = next(r for r in contract['resources'] if r['role'] == 'animation-library')
            broken = json.loads(json.dumps(contract)); next(r for r in broken['resources'] if r['path'] == row['path']).pop('restorationSHA256')
            self.assertEqual(rules(check(root, broken, overlay=overlay)), ['library-restoration'])
            # A Large root that skips the shared library diverges from its Fit pair.
            large = 'srn_body/pfx2.mdl'; blob = lib.repoint(overlay[large], 'a_fa')
            split = json.loads(json.dumps(contract)); split_overlay = {**overlay, large: blob}
            next(r for r in split['resources'] if r['path'] == large)['sha256'] = hashlib.sha256(blob).hexdigest()
            self.assertEqual(rules(check(root, split, overlay=split_overlay)), ['fit-large-divergence'])
            # A female library must sit on a_fa; a male root on it breaks the gender rule too.
            male = json.loads(json.dumps(contract)); male['targets'][1]['modelPrefix'] = 'pmx2'
            renamed = {**overlay, 'srn_body/pmx2.mdl': overlay[large]}
            row2 = next(r for r in male['resources'] if r['path'] == large); row2['path'] = 'srn_body/pmx2.mdl'
            report = check(root, male, overlay=renamed)
            self.assertIn('library-gender', rules(report)); self.assertIn('stock-closure', rules(report))

    def test_posture_layers_are_allowed_and_unknown_textures_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, contract, overlay = staged(root)
            dds = json.loads(json.dumps(contract)); (root/'srn_body/x.dds').write_bytes(b'DDS ' + bytes(120))
            dds['resources'].append({'path': 'srn_body/x.dds', 'sha256': '0'*64, 'bytes': 124, 'role': 'selected-map'})
            self.assertEqual(rules(check(root, dds, overlay=overlay)), ['texture-format'])
            with self.assertRaisesRegex(ValueError, 'Unsupported texture format'):
                lib.texture_header(root/'srn_body/x.dds')

    def test_adoption_refuses_a_release_that_breaks_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = fixtures.AdoptionTests().release(root); plan['maxTexture'] = 2
            (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'breaks the runtime rules: texture-size'):
                adopt(root, root/'plan.json', root/'staged')
            self.assertFalse((root/'staged').exists())


if __name__ == '__main__':
    unittest.main()
