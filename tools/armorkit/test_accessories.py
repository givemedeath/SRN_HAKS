"""Accessories: a brief for one piece, a belt wrapped over what is worn, a logo badge that reads right, headgear on a head envelope."""
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import numpy as np

from . import accessory, brassard, brief, export, headgear, logo
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
        with self.assertRaises(ValueError):  # the key alone would pass an outfit's brief for an accessory's, sealed without its construction rules
            brief.validate({**document(), 'accessory': None})

    def test_a_logo_cell_is_one_the_strip_has_and_an_arm_along_the_shoulders_has_no_badge_side(self):
        from . import poses
        with tempfile.TemporaryDirectory() as folder:
            for cells in ((len(logo.CELLS),), (-1,), (1.5,)):
                with self.assertRaisesRegex(ValueError, 'A logo cell is one of 0 to 15'):
                    poses.spec(folder, Path(folder) / 'out', folder, [], cells=cells)
        at = lambda x, y, z: np.array([[1.0, 0, 0, x], [0, 1.0, 0, y], [0, 0, 1.0, z], [0, 0, 0, 1.0]])
        bones = {'lbicep_g': at(0.2, 0, 1.4), 'rbicep_g': at(-0.2, 0, 1.4), 'lforearm_g': at(0.22, 0, 1.1), 'rforearm_g': at(-0.22, 0, 1.1)}
        out = brassard.frame(bones, 'l')[2]
        self.assertGreater(out[0], 0.99)  # arms hanging: the badge faces away from the body
        with self.assertRaisesRegex(ValueError, 'no outer side to put its badge on'):
            brassard.frame({**bones, 'lforearm_g': at(0.5, 0, 1.4)}, 'l')  # bound straight out

    def test_an_accessorys_materials_name_their_channels_and_share_none(self):
        made = accessory_brief('neck', ('visor', 'metal', BLUE), ('filters', 'metal', GREY))
        with self.assertRaises(ValueError):  # both on the first metal channel
            brief.validate(made)
        made['materials'][1]['channel'] = 2
        brief.validate(made)
        for wrong in (3, 2.0, True):  # 2.0 would name the channel "metal2.0"
            made['materials'][1]['channel'] = wrong
            with self.assertRaises(ValueError):
                brief.validate(made)
        outfit = document()
        outfit['materials'][0]['channel'] = 2  # an outfit's material may name its channel too (2026-11-24): it has it wherever it is worn
        self.assertEqual(brief.channels(brief.validate(outfit)['materials'])[0], ('cloth2', 'cloth2'))


class BeltTests(unittest.TestCase):
    def test_a_tilted_hoop_is_stood_level(self):
        v, f = tube(0.2, -0.02, 0.02)
        lean = np.radians(20)
        turn = np.array([[1, 0, 0], [0, np.cos(lean), -np.sin(lean)], [0, np.sin(lean), np.cos(lean)]])
        levelled, _ = accessory.level(v @ turn.T + [0.3, 0.1, 0.5], f)
        self.assertLess(np.ptp(levelled[:, 2]), 0.045)
        self.assertLess(np.abs(levelled.mean(axis=0)).max(), 1e-6)

    def test_headgear_goes_through_the_head_bones_turn_and_a_logo_without_its_picture_is_named(self):
        angle = np.radians(10)
        head = np.array([[np.cos(angle), 0, np.sin(angle), 0.0], [0, 1.0, 0, 0.1], [-np.sin(angle), 0, np.cos(angle), 1.6], [0, 0, 0, 1.0]])
        worn = headgear.in_body(np.array([[0.0, 0.0, 0.2], [0.1, 0.0, 0.0]]), {'axis': [0.0, 0.03]}, head)
        np.testing.assert_allclose(worn[0], [0.2 * np.sin(angle), 0.13, 1.6 + 0.2 * np.cos(angle)])  # its top leans with the head
        np.testing.assert_allclose(headgear.in_body(np.zeros((1, 3)), {'axis': [0.0, 0.03]}, np.eye(4)), [[0.0, 0.03, 0.0]])
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'ares: the strip names this logo and .*ares.png is not there'):
                logo.strip(folder)

    def test_a_pack_folder_that_is_not_there_is_refused_and_the_fit_is_evened_alike_each_way(self):
        with tempfile.TemporaryDirectory() as folder:
            for fitted in (lambda: accessory.worn_under(folder, 'pmh0', {}, {}, (str(Path(folder) / 'srn_part'), 6020)),
                           lambda: brassard.run(Path(folder) / 'out', folder, 1000, outfit=(str(Path(folder) / 'srn_part'), 6020))):
                with self.assertRaisesRegex(ValueError, 'is no pack folder to fit over'):
                    fitted()
        peak = np.zeros(96)
        peak[48] = 1.0
        evened = accessory._evened(peak, width=1.5)  # an odd reach: the widest-of-neighbours window was a step longer one way
        np.testing.assert_allclose(evened[48 - 8:48], evened[48 + 8:48:-1], atol=1e-12)

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

    def test_a_pouch_keeps_the_shape_it_was_drawn_in_and_clips_into_what_it_hangs_over(self):
        # a strap 5 cm tall round a hoop 1 m across, drawn at twice its size, and a box hanging below it at the front
        v, f = tube(0.5, -0.025, 0.025, around=192)  # a vertex in every direction, as a generated strap has
        box = np.array([(x, y, z) for x in (-0.08, 0.08) for y in (0.5, 0.58) for z in (-0.2, -0.04)])
        sides = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        points, faces = np.concatenate([v, box]), np.concatenate([f, sides + len(v)])
        pieces = accessory.hanging(points, faces, least=4)
        self.assertEqual([sorted(which.tolist()) for which, _ in pieces], [list(range(len(v), len(v) + 8))])
        self.assertTrue((pieces[0][1] < len(v)).all())  # it hangs from the strap
        self.assertEqual(accessory.hanging(points, faces), [])  # eight vertices are a crease of the strap, not a pouch
        apart = lambda q: np.linalg.norm(q[:, None] - q[None], axis=2)
        with unittest.mock.patch.object(accessory, 'HANGING_LEAST', 4):
            body, body_faces = tube(0.12, 0.6, 1.2, rings=40)
            placed, record = accessory.wrap(points, faces, [(body * [1.0, 0.7, 1.0], body_faces)], np.array([0.0, 0.0, 1.0]))
            self.assertEqual(record['pieces'], 1)
            ratio = apart(placed[len(v):])[np.triu_indices(8, 1)] / apart(box)[np.triu_indices(8, 1)]
            self.assertLess(np.ptp(ratio), 1e-9)  # one scale every way: nothing flared or sheared
            self.assertAlmostEqual(float(ratio[0]), record['scale'] * record['taller'], places=3)  # the hoop's, made as much taller
            # a thigh bulging under it, below the strap: the box clips into it and is neither pushed, leaned nor bent
            # (user, 2026-11-26: "clipping is fine for belt and neck slot accessories and is expected")
            thigh, thigh_faces = tube(0.1, 0.6, 0.95, rings=40)
            thigh = thigh + [0.0, 0.12, 0.0]  # its front at y 0.22, the box's back at about 0.25 * scale * taller + 0.12
            clipped, again = accessory.wrap(points, faces, [(body * [1.0, 0.7, 1.0], body_faces), (thigh, thigh_faces)], np.array([0.0, 0.0, 1.0]))
            self.assertEqual(again['scale'], record['scale'])
            np.testing.assert_allclose(clipped[len(v):], placed[len(v):], atol=1e-9)
            self.assertGreater((np.abs(accessory.measure.winding(clipped[len(v):], thigh, thigh_faces)) >= 0.5).sum(), 0)  # it is inside

    def test_what_hangs_from_an_accessory_may_clip_deep_and_the_part_that_holds_it_on_may_not(self):
        thigh, thigh_faces = tube(0.1, 0.0, 1.0, rings=40)
        box = lambda z: np.array([(x, y, z + dz) for x in (-0.02, 0.02) for y in (0.05, 0.09) for dz in (0.0, 0.04)])  # 5 cm into the thigh
        sides = np.array([(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)])
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'belt.plt').write_bytes(b'')
            (Path(folder) / 'belt.mtr').write_text('shader x\n', encoding='ascii')
            for z, passed in ((0.3, True), (0.7, False)):
                part = {'v': box(z), 'f': sides, 'rgb': np.zeros((4, 4, 3))}
                report = accessory.gates(part, {'legl': (thigh, thigh_faces)}, 'belt', folder, hangs=0.5)
                self.assertEqual(report['passed'], passed, report['failures'])
                self.assertGreater(report['inside']['hanging' if passed else 'deepest'], 0.03)

    def test_a_belts_faces_turned_toward_the_body_are_no_metals(self):
        # four walls of a hoop, each on a quarter of the texture: outside and inside at the front, outside and inside at the back
        def wall(x, out, u, v):  # a square across the x axis at `x`, its normal along +x if `out`
            corners = np.array([(x, -0.1, 0.0), (x, 0.1, 0.0), (x, 0.1, 0.1), (x, -0.1, 0.1)])
            uv = np.array([(u, v), (u + 0.5, v), (u + 0.5, v + 0.5), (u, v + 0.5)]) * 0.98 + 0.01
            return corners, uv, np.array([(0, 1, 2), (0, 2, 3)] if out else [(0, 2, 1), (0, 3, 2)])
        walls = [wall(0.5, True, 0.0, 0.0), wall(0.45, False, 0.5, 0.0), wall(-0.5, False, 0.0, 0.5), wall(-0.45, True, 0.5, 0.5)]
        v, uv = np.concatenate([w[0] for w in walls]), np.concatenate([w[1] for w in walls])
        f = np.concatenate([w[2] + 4 * k for k, w in enumerate(walls)])
        size, tan, black = 64, np.array(TAN) / 255, np.array([34, 34, 32]) / 255
        rgb = np.tile(tan, (size, size, 1))
        rgb[:32, 16:32] = black  # the buckle, on the outside at the front
        rgb[:32, 32:] = black  # the strap's inner face there, which the one view never showed
        piece = {'v': v, 'f': f, 'uv': uv, 'n': np.zeros_like(v), 'rgb': rgb, 'covered': np.ones((size, size), bool),
                 'relief': np.tile([0.5, 0.5, 1.0], (size, size, 1)), 'src': v}
        given = accessory_brief('belt', ('gear', 'leather', TAN), ('buckles', 'metal', [40, 40, 40]))
        given['materials'][1]['channel'] = 2
        (shades, layers), record = accessory.tints(piece, given)
        leather, metal = export.LAYERS['leather1'], export.LAYERS['metal2']
        self.assertTrue((layers[4:28, 20:28] == metal).all())  # the buckle stays metal
        self.assertTrue((layers[4:28, 36:60] == leather).all())  # the inner face is the strap's leather
        self.assertTrue((layers[36:60, :] == leather).all())
        self.assertGreater(float(shades[4:28, 36:60].mean()), float(shades[4:28, 20:28].mean()) - 40)  # at a shade of its own, not black
        self.assertIsNone(accessory.body_side(piece, {**given, 'accessory': 'head'}, ['leather', 'metal'], size))  # a belt's rule
        self.assertIsNone(accessory.body_side(piece, given, ['leather', 'leather'], size))  # no metal, nothing to move

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
        self.assertEqual(logo.cells(), {'ares': 1, 'renraku': 2, 'saeder-krupp': 3, 'wuxing': 4, 'mitsuhama': 5, 'aztechnology': 6, 'evo': 7,
                                        'horizon': 8, 'neonet': 9, 'shiawase': 10, 'lone-star': 11})  # a cell keeps its number: SR_NWN stores it
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

    def test_the_band_follows_a_sleeve_that_ends_under_it(self):
        # a wide sleeve over the band's upper half and the bare arm under its lower, off the bone's line
        sleeve, arm = tube(0.07, -0.02, 0.045, around=64, rings=12), tube(0.04, 0.045, 0.12, around=64, rings=12)
        v = np.concatenate([sleeve[0], arm[0]]) + [0.02, 0.01, 0.0]
        under = (v, np.concatenate([sleeve[1], arm[1] + len(sleeve[0])]))
        start, axis, out, third = np.zeros(3), np.array([0.0, 0, 1]), np.array([1.0, 0, 0]), np.array([0.0, 1, 0])
        heights = brassard.TALL * np.arange(brassard.RINGS) / (brassard.RINGS - 1)
        middle = brassard.centred(under, start, axis, out, third, 0.0, brassard.TALL)
        np.testing.assert_allclose(middle, [0.02, 0.01, 0.0], atol=2e-3)
        radius = brassard.outline(under, middle, axis, out, third, heights) + brassard.CLEARANCE
        off, most, inside = brassard.fit(under, middle, axis, out, third, heights, radius)
        self.assertLess(off, brassard.OFF)
        self.assertEqual(inside, 0.0)  # every point read under the band is under it
        self.assertLess(radius[-1].max(), 0.05)  # on the arm at its lower edge, not out at the sleeve
        # one outline for the whole height, as the first brassard had, stands off the arm by the sleeve's depth
        one = np.tile(radius.max(axis=0), (brassard.RINGS, 1))
        self.assertGreater(brassard.fit(under, middle, axis, out, third, heights, one)[0], brassard.OFF)

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
        placed, record = headgear.conform(v, f, row, headgear.SPAN)
        uv = np.stack([np.arctan2(placed[:, 0], placed[:, 1]), placed[:, 2]], axis=1)
        cut, faces, cut_uv = headgear.trim(placed, f, uv, record['chin'], record['top'])
        self.assertEqual(len(cut), len(cut_uv))
        self.assertEqual(sorted(np.unique(faces).tolist()), list(range(len(cut))))
        middle = cut[faces].mean(axis=1)
        # the front of the face only: nothing at the side of the head or over the brow is left, nothing hangs below the chin
        self.assertLess(np.abs(np.degrees(np.arctan2(middle[:, 0], middle[:, 1]))).max(), 61)
        self.assertLess(cut[:, 2].max(), record['chin'] + 0.75 * (record['top'] - record['chin']))
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
        from . import bodies, registry
        for body in registry.BODIES:  # the Dwarves and Elves too: the Dwarf woman's head bone is the one that is turned
            self.assertGreater(len(headgear.envelope(body)['rings']), 0, body)
            self.assertIn(body[:3], bodies.HEADS)
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
