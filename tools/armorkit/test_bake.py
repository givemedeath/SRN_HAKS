"""The bake's own choices and checks: what each face the split made is drawn as, what is kept, written and gated.

The stages it runs are tested where they live (test_repose, test_split, test_texture, test_export). Its whole run
needs a generated outfit and a body, and is checked against the first worn outfit instead
(docs/armorkit/pilot-corpsec.md)."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import bake, export, split


def part(faces=1, size=4):
    """A baked part of `faces` triangles with flat maps of `size` texels a side."""
    v = np.array([(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0)])
    f = np.tile([[0, 1, 2]], (faces, 1))
    relief = np.zeros((size, size, 3)); relief[..., 2] = 1.0
    none = np.zeros((size, size), bool)
    return {'v': v, 'f': f, 'uv': v[:, :2] * 5, 'n': np.tile([[0.0, 0.0, 1.0]], (3, 1)), 'rgb': np.full((size, size, 3), 0.5),
            'covered': ~none, 'relief': relief, 'closing': none, 'cap': none, 'padded': none, 'added': np.zeros(faces, bool),
            'domed': np.zeros(faces, bool), 'src': v, 'trimmed': np.full(faces, -1)}


class BakeTests(unittest.TestCase):
    def test_what_the_split_made_is_drawn_by_the_part_it_is_on(self):
        made = np.array([split.OWN, split.CLOSING, split.CAP, split.GUSSET, split.WALL, split.PADDED])
        flags = lambda name, key: bake.roles(name, made)[key].tolist()
        for name in ('chest', 'forel', 'shinr', 'legl', 'pelvis', 'bicepl'):  # the pelvis's strip is its own surface, like any face of the outfit
            self.assertEqual(flags(name, 'added'), [False, True, True, False, True, True])
            self.assertEqual(flags(name, 'domed'), [False, False, True, False, False, True])
            self.assertEqual(flags(name, 'padded'), [False, False, False, False, False, True])
        # a part like any other: its closing a closing, and its cap a cap with what grew from a pad's rim
        self.assertEqual(flags('shinr', 'closing'), [False, True, False, False, False, False])
        self.assertEqual(flags('shinr', 'cap'), [False, False, True, False, True, True])
        self.assertFalse(any(flags('shinr', 'under')))
        # a thigh's cap and its wall toward the other leg are shaded as the cloth round them, and so not drawn as a cap
        self.assertEqual(flags('legl', 'under'), [False, False, True, False, True, False])
        self.assertEqual(flags('legl', 'cap'), [False, False, False, False, False, True])
        self.assertEqual(flags('legl', 'closing'), [False, True, False, False, False, False])
        # the pelvis's lids likewise, and so not drawn as closings
        self.assertEqual(flags('pelvis', 'under'), [False, True, False, False, False, False])
        self.assertFalse(any(flags('pelvis', 'closing')))
        self.assertEqual(flags('pelvis', 'cap'), [False, False, True, False, True, True])
        # an upper arm's cap is neither a cap nor a closing: it is drawn as read, as the first outfit was seen
        for name in bake.ARMHOLE:
            self.assertEqual(flags(name, 'closing'), [False, True, False, False, False, False])
            self.assertEqual(flags(name, 'cap'), [False, False, False, False, True, True])
            self.assertFalse(any(flags(name, 'under')))

    def test_points_go_back_to_the_generated_meshs_axes(self):
        self.assertEqual(bake.to_field(np.array([(1.0, 2.0, 3.0)])).tolist(), [[-1.0, 3.0, 2.0]])

    def test_baked_parts_are_kept_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = {'chest': part(3), 'pelvis': part(2, size=8)}
            bake.store(parts, Path(folder) / 'kept')
            back = bake.stored(Path(folder) / 'kept')
            self.assertEqual(sorted(back), ['chest', 'pelvis'])
            for name in parts:
                self.assertEqual(set(back[name]), set(bake.KEYS))
                self.assertTrue(all(np.array_equal(back[name][key], parts[name][key]) for key in bake.KEYS))
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'nothing')
            np.savez(Path(folder) / 'kept' / 'shinl.npz', v=np.zeros((3, 3)))  # not a part
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')

    def written(self, folder, parts):
        tinted = {name: (np.full(one['covered'].shape, 170), np.full(one['covered'].shape, export.LAYERS['cloth1'])) for name, one in parts.items()}
        return bake.write(folder, parts, tinted, {'torso_g': np.eye(4), 'pelvis_g': np.eye(4)}, 'pmh0', 332)

    def test_an_outfit_is_written_as_models_tints_maps_and_materials(self):
        with tempfile.TemporaryDirectory() as folder:
            models = self.written(folder, {'chest': part(), 'pelvis': part()})
            self.assertEqual(models, {'chest': 'pmh0_chest332', 'pelvis': 'pmh0_pelvis332'})
            self.assertEqual(sorted(path.name for path in (Path(folder) / 'ascii').iterdir()),
                             ['pmh0_chest332.mdl', 'pmh0_chest332.plt', 'pmh0_pelvis332.mdl', 'pmh0_pelvis332.plt'])
            self.assertEqual(sorted(path.name for path in (Path(folder) / 'resources').iterdir()),
                             ['pmh0_chest332.mtr', 'pmh0_chest332.plt', 'pmh0_chest332n.tga', 'pmh0_pelvis332.mtr', 'pmh0_pelvis332.plt', 'pmh0_pelvis332n.tga'])
            shades, layers = export.read_tint((Path(folder) / 'resources' / 'pmh0_chest332.plt').read_bytes())
            self.assertTrue((shades == 170).all() and (layers == export.LAYERS['cloth1']).all())

    def test_the_gates_tell_budgets_names_and_missing_textures(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = {'chest': part(), 'pelvis': part()}
            models, resources = self.written(folder, parts), Path(folder) / 'resources'
            report = bake.gates(parts, models, resources, packs=[Path(folder) / 'pack'])
            self.assertEqual((report['passed'], report['failures']), (True, []))
            self.assertEqual(report['triangles'], {'chest': 1, 'pelvis': 1, 'outfit': 2})
            self.assertEqual(report['texels'], {'chest': 4, 'pelvis': 4})
            self.assertEqual(report['notBuilt'], list(bake.NOT_BUILT))  # a pass here is not the plan's
            json.dumps(report)
            # budgets: a chest may have more triangles than another part, and the outfit has a budget of its own
            fat = {'chest': part(bake.BUDGET['chest']), 'pelvis': part(bake.BUDGET['slot'])}
            self.assertTrue(bake.gates(fat, models, resources)['passed'])
            fat['pelvis'] = part(bake.BUDGET['slot'] + 1)
            self.assertEqual(bake.gates(fat, models, resources)['failures'],
                             [f'pelvis: {bake.BUDGET["slot"] + 1} triangles, over the budget of {bake.BUDGET["slot"]}'])
            many = {name: part(bake.BUDGET['slot']) for name in ('pelvis', 'legl', 'legr', 'shinl', 'shinr', 'footl', 'footr', 'bicepl', 'bicepr',
                                                                  'forel', 'forer', 'handl', 'handr', 'shol')}
            failures = bake.gates(many, {}, resources)['failures']
            self.assertEqual(failures, [f'the outfit: {14 * bake.BUDGET["slot"]} triangles, over the budget of {bake.BUDGET["outfit"]}'])
            wide = {'chest': part(size=2 * bake.BUDGET['texture'])}
            self.assertIn('over the budget of 1024', bake.gates(wide, {}, resources)['failures'][0])
            # a name a pack already holds
            (Path(folder) / 'pack').mkdir()
            (Path(folder) / 'pack' / 'pmh0_pelvis332.mdl').write_text('')
            self.assertEqual(bake.gates(parts, models, resources, packs=[Path(folder) / 'pack'])['failures'],
                             [f'pmh0_pelvis332: {Path(folder) / "pack"} holds a model of that name'])
            # texture closure: the tint texture, the material file, and the map it names
            (resources / 'pmh0_chest332.plt').unlink()
            (resources / 'pmh0_chest332n.tga').unlink()
            (resources / 'pmh0_pelvis332.mtr').unlink()
            self.assertEqual(bake.gates(parts, models, resources)['failures'],
                             ['pmh0_chest332: no tint texture', 'pmh0_chest332: its material file names pmh0_chest332n, which is not there',
                              'pmh0_pelvis332: no material file'])

    def test_a_run_is_a_fresh_bake_or_a_second_tint_of_kept_parts(self):
        document = {'model': 'outfit', 'materials': []}
        for wrong in ({}, {'mesh': 'mesh.glb'}, {'mesh': 'mesh.glb', 'colours': 'field.npz', 'raw': 'raw.glb'},
                      {'kept': 'kept', 'xatlas': object()}):
            with self.assertRaises(ValueError):
                bake.run(document, 'out', 'bodies', 332, **wrong)


if __name__ == '__main__':
    unittest.main()
