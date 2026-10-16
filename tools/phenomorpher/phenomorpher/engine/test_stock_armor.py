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

    def test_troll_slots_take_human_sources(self):
        self.assertEqual([armor.source_slot(s) for s in ('pmg2', 'pfg0', 'pfd2')], ['pmh2', 'pfh0', 'pfd2'])


if __name__ == '__main__':
    unittest.main()
