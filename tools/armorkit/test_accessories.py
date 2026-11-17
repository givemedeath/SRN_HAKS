"""Accessories: a brief for one piece, a belt wrapped over what is worn, a logo badge that reads right, headgear on a head envelope."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import accessory, brassard, brief, headgear, logo
from .test_brief import BLUE, GREY, TAN, document


def tube(radius, low, high, around=48, rings=6, inward=False):
    """An open tube about the vertical axis, wound to face out (or in)."""
    angles = np.arange(around) * 2 * np.pi / around
    v = np.array([(radius * np.cos(a), radius * np.sin(a), z) for z in np.linspace(low, high, rings) for a in angles])
    f = []
    for ring in range(rings - 1):
        for k in range(around):
            a, b = ring * around + k, ring * around + (k + 1) % around
            f += [(a, b, b + around), (a, b + around, a + around)]
    f = np.array(f)
    return v, (f[:, [0, 2, 1]] if inward else f)


def accessory_brief(slot, *materials):
    made = document(*materials)
    del made['construction'], made['pads']
    made['accessory'] = slot
    made['prompt'] = 'A piece.\n\n' + brief.MARK + '\n\nPlain white background.'
    return made


def envelope_row(radius=0.11, low=-0.08, high=0.24, step=0.02, coarse=24):
    """A head envelope shaped like a tube: every slice measured in every direction."""
    slices = int(round((high - low) / step))
    return {'rings': np.full((slices, coarse), radius).tolist(), 'sliceHeight': step, 'firstSlice': low, 'max': [radius, radius, high],
            'axis': [0.0, 0.0, 0.0]}


class AccessoryBriefTests(unittest.TestCase):
    def test_an_accessory_names_its_slot_and_has_no_construction(self):
        made = accessory_brief('belt', ('gear', 'leather', TAN), ('shell', 'metal', BLUE))
        brief.validate(made)
        with self.assertRaises(ValueError):
            brief.validate({**made, 'accessory': 'wing'})
        with self.assertRaises(ValueError):
            brief.validate({**made, 'construction': max(brief.CONSTRUCTIONS)})

    def test_an_accessorys_materials_name_their_channels_and_share_none(self):
        made = accessory_brief('neck', ('visor', 'metal', BLUE), ('filters', 'metal', GREY))
        with self.assertRaises(ValueError):  # both on the first metal channel
            brief.validate(made)
        made['materials'][1]['channel'] = 2
        brief.validate(made)
        made['materials'][1]['channel'] = 3
        with self.assertRaises(ValueError):
            brief.validate(made)
        outfit = document()
        outfit['materials'][0]['channel'] = 2  # an outfit's channels are sorted by where its materials are worn
        with self.assertRaises(ValueError):
            brief.validate(outfit)


class BeltTests(unittest.TestCase):
    def test_a_tilted_hoop_is_stood_level(self):
        v, f = tube(0.2, -0.02, 0.02)
        lean = np.radians(20)
        turn = np.array([[1, 0, 0], [0, np.cos(lean), -np.sin(lean)], [0, np.sin(lean), np.cos(lean)]])
        levelled, _ = accessory.level(v @ turn.T + [0.3, 0.1, 0.5], f)
        self.assertLess(np.ptp(levelled[:, 2]), 0.045)
        self.assertLess(np.abs(levelled.mean(axis=0)).max(), 1e-6)

    def test_a_hoop_is_wrapped_outside_what_is_worn_under_it(self):
        v, f = tube(0.5, -0.025, 0.025)  # generated at no scale of its own
        centre = np.array([0.0, 0.0, 1.0])
        body, body_faces = tube(0.15, 0.8, 1.2, rings=40)
        body = body * [1.0, 0.7, 1.0]  # a waist wider than it is deep
        placed, record = accessory.wrap(v, f, [(body, body_faces)], centre)
        angle = np.arctan2(placed[:, 1], placed[:, 0])
        under = 1 / np.sqrt((np.cos(angle) / 0.15) ** 2 + (np.sin(angle) / 0.105) ** 2)  # the waist's radius in each point's direction
        off = np.hypot(placed[:, 0], placed[:, 1]) - under
        self.assertGreater(off.min(), 0.0)
        self.assertLess(off.max(), 0.03)
        self.assertAlmostEqual(float(placed[:, 2].mean()), 1.0, places=2)
        self.assertLess(record['scale'], 0.5)

    def test_slight_relief_is_laid_flat_and_a_rim_kept(self):
        tilt = lambda degrees: [(np.sin(np.radians(degrees)) + 1) / 2, 0.5, (np.cos(np.radians(degrees)) + 1) / 2]
        relief = np.array([[tilt(4.0), tilt(14.0), tilt(40.0)]])
        calmed = accessory.calm(relief, 8.0, 20.0)
        np.testing.assert_allclose(calmed[0, 0], [0.5, 0.5, 1.0], atol=1e-9)
        np.testing.assert_allclose(calmed[0, 2], relief[0, 2], atol=1e-9)
        self.assertTrue(0.5 < calmed[0, 1, 0] < relief[0, 1, 0])
        np.testing.assert_allclose(np.linalg.norm(calmed * 2 - 1, axis=-1), 1.0, atol=1e-9)


class LogoTests(unittest.TestCase):
    BADGE = (np.array([[0.0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]]), np.array([[0, 1, 2], [0, 2, 3]]))  # faces -y, its top up

    def test_a_badge_reads_right_only_when_it_faces_out_unmirrored_and_upright(self):
        v, f = self.BADGE
        outward, up = [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]
        uv = np.array([[0.0, 0], [1, 0], [1, 1], [0, 1]])
        self.assertEqual(logo.reads_right(v, f, uv, outward, up), [])
        self.assertIn('mirrored', ' '.join(logo.reads_right(v, f, uv * [-1, 1] + [1, 0], outward, up)))
        self.assertIn('upside down', ' '.join(logo.reads_right(v, f, uv * [1, -1] + [0, 1], outward, up)))
        self.assertIn('turned away', ' '.join(logo.reads_right(v, f[:, [0, 2, 1]], uv, outward, up)))
        self.assertIn('next cell', ' '.join(logo.reads_right(v, f, uv * 1.5, outward, up)))

    def test_the_strip_holds_every_logo_in_its_cell_and_none_reads_the_same_mirrored(self):
        strip = logo.strip()
        self.assertEqual(strip.shape, (logo.CELL, logo.CELL * len(logo.CELLS), 3))
        self.assertEqual(logo.cells(), {'ares': 1, 'renraku': 2, 'saeder-krupp': 3, 'wuxing': 4, 'mitsuhama': 5})
        np.testing.assert_allclose(strip[:, :logo.CELL], np.broadcast_to(logo.BLANK, (logo.CELL, logo.CELL, 3)))
        for name, cell in logo.cells().items():
            picture = strip[:, cell * logo.CELL:(cell + 1) * logo.CELL]
            # a mirrored badge shows only on a logo that is not its own mirror image
            self.assertGreater(float(np.abs(picture - picture[:, ::-1]).mean()), 0.01, name)

    def test_the_material_reads_the_strip_through_the_cell_parameter(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(logo.write(folder), ['srn_logo.mtr', 'srn_vslogo.shd', 'srn_logos.tga'])
            material = (Path(folder) / 'srn_logo.mtr').read_text(encoding='ascii')
            self.assertIn('customshaderVS srn_vslogo', material)
            self.assertIn('texture0 srn_logos', material)
            self.assertIn('parameter float LogoCell 0.0', material)
            self.assertIn(f'(vVertexTexCoords.x + LogoCell) / {len(logo.CELLS)}.0', (Path(folder) / 'srn_vslogo.shd').read_text(encoding='ascii'))


class BrassardTests(unittest.TestCase):
    def test_the_band_is_accent_cloth_hemmed_in_leather(self):
        from . import export
        shades, layers = brassard.tint()
        self.assertEqual(set(np.unique(layers).tolist()), {export.LAYERS['cloth2'], export.LAYERS['leather1']})
        self.assertEqual(int(layers[len(layers) // 2, 0]), export.LAYERS['cloth2'])
        self.assertTrue(30 <= shades.min() and shades.max() <= 240)

    def test_the_badge_is_a_node_on_the_logo_material(self):
        v = np.array([[0.0, 0, 0], [1, 0, 0], [0, 0, 1]])
        mesh = (v, np.array([[0, 1, 2]]), v[:, [0, 2]], np.tile([0.0, -1, 0], (3, 1)))
        text = brassard.model_text('pmh0_shol1000', mesh, mesh)
        self.assertIn('materialname srn_logo', text)
        self.assertIn('bitmap srn_logos', text)
        self.assertIn('bitmap pmh0_shol1000', text)
        with self.assertRaises(ValueError):
            brassard.model_text('pmh0_shoulderl01000', mesh, mesh)


class HeadgearTests(unittest.TestCase):
    def test_a_piece_is_brought_outside_the_head_envelope_and_covers_the_face(self):
        row = envelope_row()
        v, f = tube(0.4, 0.0, 1.0, around=64, rings=40)  # generated at no scale, far too wide
        placed, record = headgear.conform(v, f, row)
        failures, cleared = headgear.clears(placed, f, row)
        self.assertEqual(failures, [])
        self.assertEqual(cleared['faceCovered'], 1.0)
        radius = np.hypot(placed[:, 0], placed[:, 1])
        self.assertGreater(radius.min(), 0.11)
        self.assertLess(radius.max(), 0.14)
        # from under the chin to over the top
        self.assertLess(placed[:, 2].min(), row['firstSlice'])
        self.assertGreater(placed[:, 2].max(), 0.24)

    def test_a_piece_inside_the_envelope_or_open_at_the_face_fails(self):
        row = envelope_row()
        v, f = tube(0.10, -0.1, 0.25, around=64, rings=40)
        failures, _ = headgear.clears(v, f, row)
        self.assertIn('inside the head envelope', ' '.join(failures))
        v, f = tube(0.12, -0.1, 0.25, around=64, rings=40)
        middle = v[f].mean(axis=1)
        open_face = f[~((middle[:, 1] > 0.1) & (np.abs(middle[:, 0]) < 0.05) & (np.abs(middle[:, 2]) < 0.05))]
        failures, cleared = headgear.clears(v, open_face, row)
        self.assertIn('cells of the face are not covered', ' '.join(failures))
        self.assertLess(cleared['faceCovered'], 1.0)

    def test_a_hood_is_cut_down_to_the_face_with_its_edge_turned_in(self):
        row = envelope_row()
        v, f = tube(0.4, 0.0, 1.0, around=64, rings=40)
        placed, record = headgear.conform(v, f, row)
        uv = np.stack([np.arctan2(placed[:, 0], placed[:, 1]), placed[:, 2]], axis=1)
        cut, faces, cut_uv = headgear.trim(placed, f, uv, record['chin'], record['top'])
        self.assertEqual(len(cut), len(cut_uv))
        self.assertEqual(sorted(np.unique(faces).tolist()), list(range(len(cut))))
        middle = cut[faces].mean(axis=1)
        # nothing behind the ears or over the crown is left, and nothing hangs below the chin
        self.assertGreater(middle[:, 1].min(), -0.01)
        self.assertLess(cut[:, 2].max(), record['chin'] + 0.9 * (record['top'] - record['chin']))
        self.assertGreater(cut[:, 2].min(), record['chin'] - 0.01)
        # the cut edge is turned in towards the head, and a new corner's texture place is read along its edge
        radius = np.hypot(cut[:, 0], cut[:, 1])
        self.assertLess(radius.min(), np.hypot(placed[:, 0], placed[:, 1]).min() - headgear.LIP / 2)
        np.testing.assert_allclose(cut_uv[:, 1], cut[:, 2], atol=1e-9)
        # the envelope is cleared by the whole piece and the face covered by what is worn
        failures, cleared = headgear.clears(placed, f, row, worn=(cut, faces))
        self.assertEqual(failures, [])
        self.assertEqual(cleared['faceCovered'], 1.0)
        # a cut that leaves the face open fails, though the whole piece covered it
        failures, _ = headgear.clears(placed, f, row, worn=(cut, faces[middle[:, 0] > 0]))
        self.assertIn('cells of the face are not covered', ' '.join(failures))

    def test_the_hem_hangs_below_the_chin_by_a_share_of_the_piece(self):
        row = envelope_row()
        v, f = tube(0.4, 0.0, 1.0, around=64, rings=40)
        placed, record = headgear.conform(v, f, row)
        height = float(np.ptp(placed[:, 2]))
        self.assertAlmostEqual(record['chin'] - float(placed[:, 2].min()), headgear.HEM * height, places=3)

    def test_a_wall_facing_inward_is_no_outside(self):
        row = envelope_row()
        v, f = tube(0.05, -0.1, 0.25, around=64, rings=40, inward=True)
        shell, _ = headgear.outside(v, f, row['firstSlice'], 32)
        self.assertFalse(np.isfinite(shell).any())

    def test_the_neck_part_keeps_the_neck_and_binds_the_piece_to_the_head(self):
        v = np.array([[0.0, 0, 0], [1, 0, 0], [0, 0, 1]])
        mesh = (v, np.array([[0, 1, 2]]), v[:, [0, 2]], np.tile([0.0, -1, 0], (3, 1)))
        text = headgear.model_text('pmh0_neck1000', mesh, mesh)
        self.assertIn('node trimesh pmh0_neck1000g', text)
        self.assertIn('node skin pmh0_neck1000h', text)
        self.assertEqual(text.count('head_g 1.0000'), 3)
        self.assertEqual(text.count('bitmap pmh0_neck1000'), 2)  # one tint texture, named like the model

    def test_every_race_checked_has_an_envelope_and_a_published_head(self):
        from . import bodies
        for body in ('pmh0', 'pfh0', 'pmo0', 'pfo0', 'pmg0', 'pfg0', 'pmh2'):
            self.assertGreater(len(headgear.envelope(body)['rings']), 0)
        self.assertTrue(bodies.HEADS)
        with self.assertRaises(ValueError):
            headgear.envelope('xxx0')


class AccessoryPosesTests(unittest.TestCase):
    def test_an_accessory_is_looked_at_on_a_published_outfit_with_its_logos_in_turn(self):
        from . import bodies, poses
        from .test_poses import baked, stock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            document, layout = poses.spec(baked(root / 'bake', ('neck',)), root / 'check', stock(root / 'stock'), [], preset='head',
                                          under={'chest': 6020, 'pelvis': 6020}, cells=(1, 2))
            self.assertTrue(all(actor['parts'] == {'chest': 6020, 'pelvis': 6020, 'neck': 332} for actor in document['actors']))
            self.assertEqual([actor['vars']['CELL'] for actor in document['actors'][:4]], [1, 2, 1, 2])
            self.assertTrue(all(actor['head'] == bodies.HEADS.get('pmh', poses.HEAD) for actor in document['actors']))
            self.assertIn('LogoCell', document['scripts']['ak_pose'])
            self.assertEqual(layout['labels'][0], 'standing, head front')
            with self.assertRaises(ValueError):  # the bake's own slot is not also worn from a pack
                poses.spec(root / 'bake', root / 'check2', root / 'stock', [], preset='head', under={'neck': 6020})
            self.assertFalse((root / 'check2').exists())
            plain, _ = poses.spec(root / 'bake', root / 'check3', root / 'stock', [], preset='waist')
            self.assertTrue(all('CELL' not in actor['vars'] for actor in plain['actors']))


if __name__ == '__main__':
    unittest.main()
