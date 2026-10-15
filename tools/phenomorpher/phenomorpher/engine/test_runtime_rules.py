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

    def test_target_roots_may_not_store_clips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, contract, overlay = staged(root)
            library = lib.load_model('fixture', overlay['srn_body/pfx0.mdl'])['parent']
            text = (f'newmodel pfx0\nsetsupermodel pfx0 {library}\nclassification CHARACTER\nsetanimationscale 1\n'
                    'beginmodelgeom pfx0\nnode dummy pfx0\n  parent NULL\nendnode\nendmodelgeom pfx0\n'
                    'newanim walk pfx0\n  length 1\n  transtime 0.25\n  animroot pfx0\n  node dummy pfx0\n    parent NULL\n  endnode\n'
                    'doneanim walk pfx0\ndonemodel pfx0\n').encode('ascii')
            c = json.loads(json.dumps(contract)); o = {**overlay, 'srn_body/pfx0.mdl': text}
            next(r for r in c['resources'] if r['path'] == 'srn_body/pfx0.mdl')['sha256'] = hashlib.sha256(text).hexdigest()
            report = check(root, c, overlay=o)
            self.assertEqual(rules(report), ['root-clips'])
            self.assertEqual(report['violations'][0]['detail'], 'root stores its own clips: walk')

    def test_only_declared_posture_layers_are_exempt(self):
        def layer(clips):
            text = 'newmodel srn_px_f\nsetsupermodel srn_px_f a_fa\nclassification CHARACTER\nsetanimationscale 1\n' \
                   'beginmodelgeom srn_px_f\nnode dummy srn_px_f\n  parent NULL\nendnode\nendmodelgeom srn_px_f\n'
            for clip in clips:
                text += f'newanim {clip} srn_px_f\n  length 1\n  transtime 0.25\n  animroot srn_px_f\n' \
                        f'  node dummy srn_px_f\n    parent NULL\n  endnode\ndoneanim {clip} srn_px_f\n'
            return (text + 'donemodel srn_px_f\n').encode('ascii')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, contract, overlay = staged(root)
            def release(blob):
                """Both roots name the layer instead of the shared library, which is dropped."""
                c = json.loads(json.dumps(contract)); o = dict(overlay)
                c['resources'] = [r for r in c['resources'] if r['role'] != 'animation-library']
                c['resources'].append({'path': 'srn_body/srn_px_f.mdl', 'sha256': hashlib.sha256(blob).hexdigest(), 'role': 'rig-inheritance'})
                o['srn_body/srn_px_f.mdl'] = blob
                for path in ('srn_body/pfx0.mdl', 'srn_body/pfx2.mdl'):
                    o[path] = lib.repoint(overlay[path], 'srn_px_f')
                    next(r for r in c['resources'] if r['path'] == path)['sha256'] = hashlib.sha256(o[path]).hexdigest()
                return c, o
            posture = layer(['pause1', 'pause2'])
            c, o = release(posture)
            declared = {'srn_px_f': {'sha256': hashlib.sha256(posture).hexdigest()}}
            report = check(root, c, overlay=o, posture_layers=declared)
            self.assertTrue(report['passed'], report['violations']); self.assertEqual(report['postureLayers'], ['srn_px_f'])
            # Undeclared, or declared with other bytes, it is a private carrier despite its idle clips.
            self.assertEqual(check(root, c, overlay=o, posture_layers={})['violationCounts'], {'private-carrier': 2})
            self.assertEqual(check(root, c, overlay=o, posture_layers={'srn_px_f': {'sha256': '0'*64}})['violationCounts'], {'private-carrier': 2})
            # A declared name with no clips is not a posture layer either.
            empty = layer([]); c, o = release(empty)
            report = check(root, c, overlay=o, posture_layers={'srn_px_f': {'sha256': hashlib.sha256(empty).hexdigest()}})
            self.assertEqual(report['violationCounts'], {'private-carrier': 2})

    def test_adoption_refuses_a_release_that_breaks_the_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = fixtures.AdoptionTests().release(root); plan['maxTexture'] = 2
            (root/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'breaks the runtime rules: texture-size'):
                adopt(root, root/'plan.json', root/'staged')
            self.assertFalse((root/'staged').exists())


if __name__ == '__main__':
    unittest.main()
