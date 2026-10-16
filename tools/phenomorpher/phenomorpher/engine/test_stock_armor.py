"""Stock armour inventory: which installed parts are converted, and what they reference."""
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from . import stock_armor as armor


def key_file(path, entries):
    """Minimal KEY V1 with (resref, type) entries and no BIF table rows."""
    table = 64; data = bytearray(table + 22*len(entries))
    data[:8] = b'KEY V1  '; struct.pack_into('<IIII', data, 8, 0, len(entries), 64, table)
    for i, (name, kind) in enumerate(entries):
        at = table + 22*i; data[at:at+len(name)] = name.encode(); struct.pack_into('<HI', data, at+16, kind, i)
    path.write_bytes(bytes(data))


MODEL = '''newmodel {n}
setsupermodel {n} NULL
beginmodelgeom {n}
node dummy {n}
  parent NULL
endnode
node {kind} {n}g
  parent {n}
  bitmap {bitmap}
  verts 0
endnode
endmodelgeom {n}
donemodel {n}
'''


class InventoryTests(unittest.TestCase):
    def test_selection_keeps_real_armour_and_drops_robes_and_bare_parts(self):
        resources = {n: ['k'] for n in ('pfd0_chest001.mdl', 'pfd0_chest005.mdl', 'pfd0_belt001.mdl', 'pfd0_shol001.mdl',
                                        'pfd0_robe003.mdl', 'pfd0_head001.mdl', 'pfd0_footl001.mdl', 'pfd3_chest005.mdl',
                                        'pmg2_neck004.mdl', 'pfd0_chest005.plt', 'c_dog.mdl')}
        rows = armor.selected(resources, armor.SLOTS)
        self.assertEqual(sorted(rows), ['pfd0_belt001.mdl', 'pfd0_chest005.mdl', 'pfd0_shol001.mdl', 'pmg2_neck004.mdl'])
        self.assertEqual(rows['pmg2_neck004.mdl'], {'slot': 'pmg2', 'part': 'neck', 'style': 4})
        self.assertEqual(armor.classify('pfd0_shinl012'), ('pfd0', 'shinl', 12)); self.assertIsNone(armor.classify('pfd0_head001'))

    def test_extraction_pins_models_textures_and_flags_unresolved_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'game/data').mkdir(parents=True)
            bare = [('pfd0', 2002)] + [(f'pfd0_{part}001', 2002) for part in armor.BARE]
            key_file(root/'game/data/nwn_base.key', [('pfd0_chest005', 2002), ('pfd0_belt002', 2002), ('pmh0_chest005', 2002),
                                                     ('pfd0_chest005', 6), ('pfh0_chest001', 6), *bare])
            texts = {'pfd0_chest005.mdl': MODEL.format(n='pfd0_chest005', kind='danglymesh', bitmap='pfd0_chest005'),
                     'pfd0_belt002.mdl': MODEL.format(n='pfd0_belt002', kind='trimesh', bitmap='missing_tex'),
                     'pfd0_chest005.plt': 'PLT', 'pfh0_chest001.plt': 'PLT', **{n + '.mdl': 'native' for n, _ in bare}}
            def run(command, **_):
                out = Path(command[command.index('-d') + 1])
                for name in command[command.index('-d') + 2:]:
                    (out/name).write_text(texts[name], encoding='ascii')
                class Result: returncode = 0; stderr = b''
                return Result()
            tool = root/'extract.exe'; tool.write_bytes(b'x'); dec = root/'dec.exe'; dec.write_bytes(b'y')
            with patch.object(armor.subprocess, 'run', side_effect=run):
                manifest = armor.extract(tool, dec, root/'game', root/'out', ['pfd0'])
            self.assertEqual(sorted(manifest['models']), ['pfd0_belt002.mdl', 'pfd0_chest005.mdl'])
            self.assertEqual(manifest['counts'], {'models': 2, 'textures': 1, 'fitReferences': 16, 'danglymesh': 1, 'unsupportedMeshTypes': []})
            self.assertIn('pfd0.mdl', manifest['fitReferences']); self.assertNotIn('pfd0_chest001.mdl', manifest['models'])
            self.assertEqual(manifest['models']['pfd0_belt002.mdl']['unresolvedReferences'], ['missing_tex'])
            self.assertEqual(sorted(manifest['textures']), ['pfd0_chest005.plt'])
            self.assertEqual(json.loads((root/'out/stock-armor.json').read_text())['override'], False)
            with self.assertRaisesRegex(ValueError, 'Unknown body slot'):
                armor.extract(tool, dec, root/'game', root/'out2', ['pfa0'])


class ProfileTests(unittest.TestCase):
    def test_a_known_scale_rotation_and_translation_is_recovered(self):
        import numpy as np
        from .retarget import rotations
        rng = np.random.default_rng(1)
        # An elongated limb-like cloud along -z; the new part is scaled, then rotated by a joint frame change, then moved.
        stock = rng.normal(size=(4000, 3))*[.04, .03, .0] + np.c_[np.zeros((4000, 2)), -rng.random(4000)*.3]
        frame = rotations([1, 0, 0, np.deg2rad(28.6)]); scale = np.array([.6, .7, 1.3]); shift = np.array([.002, -.004, .006])
        new = stock @ (frame @ np.diag(scale)).T + shift
        fit = armor.fit_part(stock, new, frame, False)
        np.testing.assert_allclose(fit['scale'], scale, rtol=1e-6); np.testing.assert_allclose(fit['translate'], shift, atol=1e-9)
        self.assertLess(fit['residualMm']['stockToNewMean'], 1e-6)
        # Armory rebuilds the same rotation from the recorded degrees (X, Y, Z with X/Y negated).
        x, y, z = np.deg2rad(armor.armory_rotate(fit['rotation']))
        rebuilt = rotations([0, 0, 1, z]) @ rotations([0, 1, 0, -y]) @ rotations([1, 0, 0, -x])
        np.testing.assert_allclose(rebuilt, frame, atol=1e-12)
        self.assertAlmostEqual(armor.armory_rotate(frame)[0], -28.6)

    def test_renaming_keeps_texture_references(self):
        text = ('newmodel pmh2_chest005\nsetsupermodel pmh2_chest005 NULL\nnode dummy pmh2_chest005\n  parent NULL\nendnode\n'
                'node trimesh pmh2_chest005g\n  parent pmh2_chest005\n  bitmap pmh2_chest005\n  materialname pmh2_chest005\nendnode\n'
                'node dummy pmh2_chest0051\nendnode\n')
        out = armor.renamed(text, 'pmh2_chest005', 'pmg2_chest005')
        self.assertIn('newmodel pmg2_chest005\n', out); self.assertIn('node trimesh pmg2_chest005g\n', out)
        self.assertIn('  parent pmg2_chest005\n', out); self.assertIn('  bitmap pmh2_chest005\n', out)
        self.assertIn('  materialname pmh2_chest005\n', out); self.assertIn('node dummy pmh2_chest0051\n', out)
        self.assertEqual(armor.renamed(text, 'pmh2_chest005', 'pmh2_chest005'), text)

    def test_a_mesh_named_like_its_model_is_renamed_once(self):
        text = ('newmodel pmh2_footl014\nnode dummy pmh2_footl014\n  parent NULL\nendnode\n'
                'node trimesh pmh2_footl014\n  parent pmh2_footl014\n  bitmap pmh2_footl014\nendnode\n')
        out, changes = armor.unique_mesh_names(text, 'pmh2_footl014')
        self.assertIn('node trimesh pmh2_footl014g\n  parent pmh2_footl014\n  bitmap pmh2_footl014\n', out)
        self.assertEqual(changes, [{'node': 'pmh2_footl014', 'type': 'trimesh', 'renamedTo': 'pmh2_footl014g'}])
        self.assertEqual(armor.unique_mesh_names(out, 'pmh2_footl014'), (out, []))
        child = text + 'node dummy hook\n  parent pmh2_footl014\nendnode\n'
        self.assertRaisesRegex(ValueError, 'Ambiguous', armor.unique_mesh_names, child, 'pmh2_footl014')

    def test_armory_values_output_is_parsed(self):
        log = ('scale=(1.2000, 1.1000, 1.3000)\nrotate=(5.00, -3.00, 2.00)\ntranslate=(0.0100, 0.0200, -0.0300)\n'
               '; verts fit: n=66 max_residual=0.00000 mean_residual=0.00000 (note)\n; tverts fit: n=67 max_residual=0.5\n')
        class Result: returncode = 0; stdout = log; stderr = ''
        with patch.object(armor.subprocess, 'run', return_value=Result()):
            scale, rotate, shift, residual, _ = armor.armory_values('armory', 'a.mdl', 'b.mdl')
        self.assertEqual((scale, rotate, shift, residual), ([1.2, 1.1, 1.3], [5., -3., 2.], [.01, .02, -.03], 0.))

    def test_style_sets_refuse_robes_and_bare_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'set.json'
            for styles, ok in (([['chest', 5], ['belt', 1]], True), ([['robe', 3]], False), ([['chest', 1]], False), ([['chest', 5], ['chest', 5]], False)):
                path.write_text(json.dumps({'kind': 'PhenoMorpher-stock-armor-style-set', 'styles': styles}))
                with self.subTest(styles=styles):
                    if ok:
                        self.assertEqual(armor.style_set(path), [('chest', 5), ('belt', 1)])
                    else:
                        self.assertRaisesRegex(ValueError, 'not converted', armor.style_set, path)
        ini = armor.armory_ini([('pmh0_chest005', {'scale': [1, 2, 3], 'translate': [0, 0, .5]})])
        self.assertEqual(ini, '[Global]\nntransforms=1\n[s0]\nmatch=pmh0_chest005\nsubstitute=*\nscale=(1,2,3)\nrotate=(0,0,0)\ntranslate=(0,0,0.5)\n')

    def test_every_non_human_body_converts_human_parts(self):
        self.assertEqual([armor.source_slot(s) for s in ('pmg2', 'pfg0', 'pfd2', 'pme0', 'pfo2')], ['pmh2', 'pfh0', 'pfh2', 'pmh0', 'pfh2'])
        self.assertEqual((len(armor.TARGETS), armor.SOURCES), (16, ('pfh0', 'pfh2', 'pmh0', 'pmh2')))
        with self.assertRaisesRegex(ValueError, 'Human bodies are sources only'):
            armor.source_slot('pfh0')


class PackTests(unittest.TestCase):
    def fixture(self, root):
        """One converted, compiled part for pfd0 and its body contract."""
        from .anim_library import digest
        compiled = root/'compiled'; res = compiled/'pfd0/converted/resources'; res.mkdir(parents=True)
        binary = b'\0\0\0\0compiled'; (res/'pfd0_chest005.mdl').write_bytes(binary)
        (compiled/'pfd0/converted/native-compile.json').write_text(json.dumps({'complete': True, 'clientSha256': 'c', 'models': [
            {'name': 'pfd0_chest005.mdl', 'sourceSha256': 'a', 'binarySha256': digest(binary)}]}))
        conversion = root/'conversion.json'
        conversion.write_text(json.dumps({'kind': armor.CONVERT_KIND, 'stockInventorySHA256': 's', 'profilesSHA256': 'p',
            'armory': {'sha256': armor.ARMORY_SHA256}, 'slots': {'pfd0': {'source': 'pfh0', 'models': {'pfd0_chest005.mdl': {
                'source': 'pfh0_chest005.mdl', 'part': 'chest', 'style': 5, 'sourceAsciiSHA256': 'x', 'asciiSHA256': 'a',
                'meshTypes': ['trimesh'], 'textureReferences': ['pfh0_chest005']}}}}}))
        body = root/'body.json'; body.write_text(json.dumps({'resources': [{'path': 'srn_body/pfd0_chest001.mdl'}]}))
        return conversion, compiled, body

    def test_published_pack_verifies_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); conversion, compiled, body = self.fixture(root); manifest = root/'armor.json'
            result = armor.publish([(conversion, compiled)], body, root, manifest)
            self.assertEqual((result['resources'], result['targets']), (1, 1))
            self.assertEqual((root/'srn_armor/pfd0_chest005.mdl').read_bytes(), b'\0\0\0\0compiled')
            self.assertRaises(FileExistsError, armor.publish, [(conversion, compiled)], body, root, manifest)
            (root/'srn_armor/pfd0_chest006.mdl').write_bytes(b'\0\0\0\0x')
            self.assertRaisesRegex(ValueError, 'outside its contract', armor.verify_pack, root, manifest)
            (root/'srn_armor/pfd0_chest006.mdl').unlink(); (root/'srn_armor/pfd0_chest005.mdl').write_bytes(b'\0\0\0\0changed')
            self.assertRaisesRegex(ValueError, 'differs', armor.verify_pack, root, manifest)

    def test_publish_refuses_binaries_from_other_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); conversion, compiled, body = self.fixture(root)
            data = json.loads(conversion.read_text()); data['slots']['pfd0']['models']['pfd0_chest005.mdl']['asciiSHA256'] = 'b'
            conversion.write_text(json.dumps(data))
            self.assertRaisesRegex(ValueError, 'does not match', armor.publish, [(conversion, compiled)], body, root, root/'m.json')
            body.write_text(json.dumps({'resources': [{'path': 'srn_body/pfd0_chest005.mdl'}]})); data['slots']['pfd0']['models']['pfd0_chest005.mdl']['asciiSHA256'] = 'a'
            conversion.write_text(json.dumps(data))
            self.assertRaisesRegex(ValueError, 'shadows', armor.publish, [(conversion, compiled)], body, root, root/'m.json')


if __name__ == '__main__':
    unittest.main()
