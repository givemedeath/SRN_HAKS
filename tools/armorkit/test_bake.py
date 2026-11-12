"""The bake's own choices and checks: what each face the split made is drawn as, what is kept, written and gated.

The stages it runs are tested where they live (test_repose, test_split, test_texture, test_export). Its whole run
needs a generated outfit and a body, and is checked against the first worn outfit instead
(docs/armorkit/pilot-corpsec.md)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from . import bake, bodyskin, export, measure, split


def box(centre=(0.0, 0.0, 0.0), side=0.1):
    """A closed cube: (vertices, faces), wound outward."""
    v = (np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], float) - 0.5) * side + centre
    f = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
    return v, f


def joined(*meshes):
    """Meshes as one: (vertices, faces)."""
    base = np.cumsum([0] + [len(v) for v, _ in meshes])
    return np.concatenate([v for v, _ in meshes]), np.concatenate([f + b for (_, f), b in zip(meshes, base)])


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
            # the folder used again for an outfit with fewer parts: the pelvis's file is still there, and is not read
            bake.store({'chest': part(2)}, Path(folder) / 'kept')
            self.assertTrue((Path(folder) / 'kept' / 'pelvis.npz').is_file())
            again = bake.stored(Path(folder) / 'kept')
            self.assertEqual((list(again), len(again['chest']['f'])), (['chest'], 2))
            np.savez(Path(folder) / 'kept' / 'shinl.npz', v=np.zeros((3, 3)))  # a file of another kind beside them is not a part
            self.assertEqual(list(bake.stored(Path(folder) / 'kept')), ['chest'])
            listing = Path(folder) / 'kept' / bake.KEPT
            listing.write_text(json.dumps({'schemaVersion': 1, 'kind': bake.KEPT_KIND, 'parts': ['chest', 'shinl']}))  # listed, and no part
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')
            listing.write_text(json.dumps({'schemaVersion': 1, 'kind': bake.KEPT_KIND, 'parts': ['chest', 'forel']}))  # listed, and not there
            with self.assertRaises(ValueError):
                bake.stored(Path(folder) / 'kept')
            listing.unlink()  # files without a list: a store that stopped halfway, or a folder of something else
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

    def test_holes_and_crumbs_of_the_generated_outfit_are_found_and_separate_pieces_are_not_faults(self):
        v, f = box(side=0.1)
        self.assertEqual(bake.surface(v, f), {'holes': [], 'debris': [], 'pieces': 1})
        seamed = f.copy()
        seamed[:2] = np.where(f[:2] < 4, f[:2] + 8, f[:2])  # a texture seam: two faces on their own copies of four vertices
        self.assertEqual(bake.surface(np.concatenate([v, v[:4]]), seamed), {'holes': [], 'debris': [], 'pieces': 1})
        self.assertTrue(np.allclose(bake.surface(v, f[1:])['holes'], [0.2 + 0.1 * np.sqrt(2)]))  # one face gone: an opening round its edges
        pin = box((0.0, 0.0, 0.05), 0.001)  # an opening under `HOLE` round, on a crumb set into the surface
        self.assertEqual(bake.surface(*joined((v, f), (pin[0], pin[1][1:]))), {'holes': [], 'debris': [], 'pieces': 2})
        crumb, pad, sunk = box((0.1, 0.0, 0.0), 0.01), box((0.085, 0.0, 0.0), 0.05), box((0.05, 0.0, 0.0), 0.01)
        found = bake.surface(*joined((v, f), crumb))
        self.assertTrue(found['holes'] == [] and found['pieces'] == 2 and np.allclose(found['debris'], [6 * 0.01 ** 2]))
        self.assertEqual(bake.surface(*joined((v, f), pad))['debris'], [])  # a pad standing off the rest is a piece, not debris
        self.assertEqual(bake.surface(*joined((v, f), sunk))['debris'], [])  # a crumb set into the rest touches it

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
            # with what the generated outfit holds of holes and debris, those are gated too
            clean, faulty = {'holes': [], 'debris': [], 'pieces': 1}, {'holes': [0.012], 'debris': [0.0004], 'pieces': 2}
            report = bake.gates(parts, models, resources, whole=clean)
            self.assertEqual((report['passed'], report['surface'], bake.WHOLE in report['notBuilt']), (True, clean, False))
            self.assertEqual(bake.gates(parts, models, resources, whole=faulty)['failures'],
                             ['the generated outfit: an opening 1.2 cm round', 'the generated outfit: a piece of 4.0 cm² standing apart from the rest'])
            json.dumps(bake.gates(parts, models, resources, whole=faulty))
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

    def test_a_slot_left_to_the_body_gets_no_part_and_a_shared_one_the_bodys_skin(self):
        from .test_bodyskin import arm
        bone = lambda *place: np.block([[np.eye(3), np.array(place, float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])
        bones = {'torso_g': np.eye(4), 'lbicep_g': bone(0, 0, 1.5), 'lforearm_g': bone(0, 0, 1.2), 'lhand_g': bone(0, 0, 0.9)}
        parts = {'chest': part(), 'bicepl': part(), 'handl': part()}
        document, said = {'model': 'outfit', 'materials': [], 'bare': ['forearm'], 'skin': ['bicep']}, []
        self.assertEqual((bake.left_to_body(document), bake.shared_with_body(document)), ({'forel', 'forer'}, {'bicepl', 'bicepr'}))
        with mock.patch.object(bodyskin, 'body_part', lambda pack, maps, body, name, rig: arm()):
            out = bake.skinned(parts, document, 'pack', 'maps', 'pmh0', bones, say=said.append)
            self.assertEqual(bake.skinned(parts, {'model': 'outfit', 'materials': []}, 'pack', None, 'pmh0', bones), parts)  # a brief that names neither
        self.assertEqual(sorted(out), ['bicepl', 'chest', 'handl'])
        self.assertTrue(said[0].startswith("bicepl: 384 of the body's 384 faces"), said)
        arm_part = out['bicepl']
        self.assertEqual((int(arm_part['skin'].sum()), len(arm_part['rgb']), 'skin' in out['chest']), (len(arm()['f']), 8, False))
        with tempfile.TemporaryDirectory() as folder:
            bake.store(out, Path(folder) / 'kept')  # kept with what the skin adds, and read back with it
            back = bake.stored(Path(folder) / 'kept')
            self.assertTrue(all(np.array_equal(back['bicepl'][key], arm_part[key]) for key in bake.KEYS + bodyskin.KEYS))
            self.assertEqual(set(back['chest']), set(bake.KEYS))
            # the tint: the body's own shade and skin layer on its texels, the outfit's elsewhere
            cloth = (np.full((8, 8), 170), np.full((8, 8), export.LAYERS['cloth1']))
            shades, layers = bodyskin.tinted(arm_part, cloth)
            at = arm_part['skin_at']
            self.assertTrue((layers[at] == export.LAYERS['skin']).all() and (layers[~at] == export.LAYERS['cloth1']).all())
            self.assertTrue(np.array_equal(shades[at], arm_part['skin_tint'][..., 0][at]) and (shades[~at] == 170).all())
            self.assertIs(bodyskin.tinted(out['chest'], cloth), cloth)
            # written: its normal map whole, and its roughness as a map the material binds
            tinted = {name: bodyskin.tinted(one, (np.full(one['covered'].shape, 170), np.full(one['covered'].shape, export.LAYERS['cloth1'])))
                      for name, one in out.items()}
            models = bake.write(folder, out, tinted, bones, 'pmh0', 332)
            resources = Path(folder) / 'resources'
            self.assertEqual(bodyskin.image((resources / 'pmh0_bicepl332n.tga').read_bytes()).shape, (8, 8, 3))
            self.assertEqual(bodyskin.image((resources / 'pmh0_chest332n.tga').read_bytes()).shape, (2, 2, 3))  # at half size, as before
            rough = bodyskin.image((resources / 'pmh0_bicepl332r.tga').read_bytes())[..., 0]
            self.assertTrue(np.allclose(rough, arm_part['skin_rough'] / 255, atol=1 / 255))
            self.assertEqual(bodyskin.material(resources, 'pmh0_bicepl332'), {'normal': 'pmh0_bicepl332n', 'rough': 'pmh0_bicepl332r'})
            self.assertIn('Roughness 0\n', (resources / 'pmh0_bicepl332.mtr').read_text())
            self.assertFalse((resources / 'pmh0_chest332r.tga').exists())
            self.assertTrue(bake.gates(out, models, resources)['passed'])
            (resources / 'pmh0_bicepl332r.tga').unlink()
            self.assertEqual(bake.gates(out, models, resources)['failures'], ['pmh0_bicepl332: its material file names pmh0_bicepl332r, which is not there'])

    def test_a_run_compiles_the_models_it_wrote_and_no_others(self):
        with tempfile.TemporaryDirectory() as folder:
            output, parts, compiled = Path(folder) / 'out', {'chest': part(), 'pelvis': part()}, []
            bake.store(parts, Path(folder) / 'kept')
            (output / 'ascii').mkdir(parents=True)
            (output / 'ascii' / 'pmh0_chest331.mdl').write_text('')  # an earlier run's, under another number
            (output / 'ascii' / 'pmh0_shol332.mdl').write_text('')  # and a part this outfit does not have
            tinted = {name: (np.full((4, 4), 170), np.full((4, 4), export.LAYERS['cloth1'])) for name in parts}
            with mock.patch.object(bake, 'tints', lambda parts, document: (tinted, {'materials': []})), \
                    mock.patch.object(measure, 'body', lambda pack, body: ({'torso_g': np.eye(4), 'pelvis_g': np.eye(4)}, {})), \
                    mock.patch.object(export, 'compile_models', lambda sources, into, **given: compiled.append((sources, into, given)) or sources):
                record = bake.run({'model': 'outfit', 'materials': []}, output, 'bodies', 332, kept=Path(folder) / 'kept', game='game', resources=['srn_body'])
            self.assertEqual(compiled, [([output / 'ascii' / 'pmh0_chest332.mdl', output / 'ascii' / 'pmh0_pelvis332.mdl'], output / 'resources',
                                         {'game': 'game', 'resources': ['srn_body']})])
            self.assertEqual((record['compiled'], record['models'], record['gates']['passed']),
                             (2, {'chest': 'pmh0_chest332', 'pelvis': 'pmh0_pelvis332'}, True))
            self.assertEqual(json.loads((output / 'bake.json').read_text(encoding='utf-8')), record)

    def test_kept_parts_baked_for_other_slots_left_to_the_body_or_its_skin_are_refused(self):
        skin = dict(part(), skin=np.zeros(1, bool))
        document = {'model': 'outfit', 'materials': [], 'bare': ['forearm'], 'skin': ['bicep']}
        plain = {'model': 'outfit', 'materials': []}
        cases = (({'chest': part(), 'forel': part()}, None, document),  # a part the brief now leaves to the body
                 ({'chest': part(), 'bicepl': part()}, None, document),  # an upper arm without the skin the brief now shows
                 ({'chest': part(), 'bicepl': skin}, None, plain),  # and with it, where the brief shows none
                 ({'chest': part()}, {**plain, 'bare': ['forearm']}, plain))  # no forearm, left to the body by the brief baked from and no longer
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(measure, 'body', lambda pack, body: ({'torso_g': np.eye(4)}, {})), \
                mock.patch.object(bake, 'tints', lambda parts, document: self.fail('tinted')):
            for parts, baked_from, brief in cases:
                bake.store(parts, Path(folder) / 'kept', baked_from)
                with self.assertRaisesRegex(ValueError, 'bake the outfit again'):
                    bake.run(brief, Path(folder) / 'out', 'bodies', 332, kept=Path(folder) / 'kept')
            self.assertEqual(bake.declared(Path(folder) / 'kept'), {'bare': {'forearm'}, 'skin': set()})
            # parts kept for the brief's own slots are tinted again
            bake.store({'chest': part(), 'bicepl': skin}, Path(folder) / 'kept', document)
            with mock.patch.object(bake, 'tints', mock.Mock(side_effect=RuntimeError('tinted'))):
                with self.assertRaisesRegex(RuntimeError, 'tinted'):
                    bake.run(document, Path(folder) / 'out', 'bodies', 332, kept=Path(folder) / 'kept')
            listed = json.loads((Path(folder) / 'kept' / bake.KEPT).read_text(encoding='utf-8'))
            (Path(folder) / 'kept' / bake.KEPT).write_text(json.dumps({**listed, 'skin': 'bicep'}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no list of baked parts'):  # the slots are checked with the list
                bake.declared(Path(folder) / 'kept')
            bake.store({'chest': part()}, Path(folder) / 'kept')  # stored without its brief, or before the list held the slots: none
            self.assertEqual(bake.declared(Path(folder) / 'kept'), {'bare': set(), 'skin': set()})

    def test_a_run_is_a_fresh_bake_or_a_second_tint_of_kept_parts(self):
        document = {'model': 'outfit', 'materials': []}
        for wrong in ({}, {'mesh': 'mesh.glb'}, {'mesh': 'mesh.glb', 'colours': 'field.npz', 'raw': 'raw.glb'},
                      {'kept': 'kept', 'xatlas': object()}):
            with self.assertRaises(ValueError):
                bake.run(document, 'out', 'bodies', 332, **wrong)


if __name__ == '__main__':
    unittest.main()
