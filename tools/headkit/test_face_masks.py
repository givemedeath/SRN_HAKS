"""Focused tests of the face-mask stages on synthetic inputs (no models, Embree or xatlas needed)."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from headkit.common import manifest, write, read
from headkit.face_masks import hair_locks, brow_seed, brow_mask, iris_circles, IRIS, BROW_RING, HAIR, SKIN
from headkit.face_encode import apply_channels, beard_hair, majority, consistent_blocks, treat, TREATMENT
from headkit.quality import eligible, shade_span_failures, CHECKS, THRESHOLDS
from headkit.uv import face_region
from headkit.runner import STAGES, stage_roles, stage_libraries


def flat(*names):
    return {name: np.zeros((4096, 4096), np.float32) for name in names}


class HairLocks(unittest.TestCase):
    def scene(self):
        S = 200; labels = np.full((S, S), SKIN, np.uint8); labels[:40] = HAIR
        rgb = np.full((S, S, 3), (150, 100, 70), np.uint8); rgb[:40] = (230, 220, 190)
        rgb[40:120, 20:28] = (230, 220, 190)     # a cream lock hanging from the hairline, labelled skin
        rgb[100:110, 90:100] = (230, 220, 190)   # the same colour inside the face, touching neither hairline nor edge
        face = np.zeros((S, S), bool); face[10:190, 10:190] = True
        return rgb, labels, face

    def test_lock_from_the_hairline_only(self):
        rgb, labels, face = self.scene(); plain = face & (labels == SKIN)
        lock = hair_locks(rgb, labels, np.ones_like(face), face, plain)
        self.assertTrue(lock[60:110, 20:28].all()); self.assertFalse(lock[100:110, 90:100].any())

    def test_close_colours_give_no_rule(self):
        rgb, labels, face = self.scene(); rgb[:40] = (152, 101, 72)
        self.assertIsNone(hair_locks(rgb, labels, np.ones_like(face), face, face & (labels == SKIN)))


class Brows(unittest.TestCase):
    def test_grows_by_colour_but_not_into_highlights(self):
        S = 200; labels = np.full((S, S), SKIN, np.uint8); rgb = np.full((S, S, 3), 180, np.uint8)
        rgb[50:60, 40:100] = np.clip(np.random.default_rng(1).normal(60, 6, (10, 60, 3)), 0, 255)
        labels[52:58, 50:90] = 2   # parser brow shorter than the painted one
        rgb[50:60, 100:110] = 250                                    # bright highlight at the brow end
        grown = brow_mask(rgb, labels, labels == 2, np.zeros((S, S), bool), np.ones((S, S), bool))
        self.assertGreater(grown[50:60, 41:99].mean(), .95); self.assertFalse(grown[:, 100:].any())

    @staticmethod
    def landmarks(S=220):
        """Landmark brow polygons over y 50-60: subject's right brow x 20-100, left x 120-200."""
        pts = np.zeros((478, 2))
        for ring, (outer, inner) in ((BROW_RING['R'], (20, 100)), (BROW_RING['L'], (200, 120))):
            xs = np.linspace(outer, inner, 5); pts[ring[:5]] = np.c_[xs, np.full(5, 50)]; pts[ring[5:]] = np.c_[xs[::-1], np.full(5, 60)]
        return pts

    def test_landmark_seed_for_white_brows_under_dark_marks(self):
        # dwarf-male-c (RUNBOOK 143): the parser labels black forehead ink as brows and the white brows as skin.
        S = 220; labels = np.full((S, S), SKIN, np.uint8); rgb = np.full((S, S, 3), (190, 130, 110), np.uint8)
        noise = np.random.default_rng(1).normal(235, 6, (11, 81, 3)).clip(0, 255)
        rgb[50:61, 20:101] = rgb[50:61, 120:201] = noise      # white brows on the landmark polygons
        rgb[20:35, 40:80] = rgb[20:35, 140:180] = 15          # forehead ink
        labels[20:35, 40:80] = labels[20:35, 140:180] = 2
        none, hit = np.zeros((S, S), bool), np.ones((S, S), bool)
        seed = brow_seed(labels, self.landmarks(), none, hit); grown = brow_mask(rgb, labels, seed, none, hit)
        self.assertFalse(seed[20:35].any()); self.assertFalse(grown[20:35].any())
        self.assertGreater(grown[51:60, 22:99].mean(), .95); self.assertGreater(grown[51:60, 122:199].mean(), .95)

    def test_parser_brows_on_the_landmarks_kept_whole(self):
        S = 220; labels = np.full((S, S), SKIN, np.uint8); labels[48:62, 15:105] = labels[48:62, 115:205] = 2   # past the polygons
        labels[20:30, 60:70] = 3                                                                                # a stray parser brow
        seed = brow_seed(labels, self.landmarks(), np.zeros((S, S), bool), np.ones((S, S), bool))
        self.assertTrue(seed[48:62, 15:105].all() and seed[48:62, 115:205].all()); self.assertFalse(seed[20:30].any())


class Beard(unittest.TestCase):
    def test_hair_coloured_beard_stays_hair_below_the_nose(self):
        # RUNBOOK 145: the parser calls beards skin. Grey beard (owned hair) and a skin-coloured patch the hair rule over-took,
        # both under the parser skin mask; only the beard zone is judged by colour.
        S = 64; labels = np.zeros((S, S), np.uint8); colour = np.zeros((S, S, 3), np.uint8); colour[:] = (190, 140, 100)
        labels[:8] = 1; colour[:8] = (120, 120, 120)                                   # scalp hair, outside the parser skin
        labels[40:50, 10:30] = 1; colour[40:50, 10:30] = (150, 150, 150)               # beard, a lighter grey
        labels[40:50, 34:54] = 1                                                       # skin-coloured, owned hair by a rule
        masks = {'skin': np.zeros((S, S), np.float32), 'brow': np.zeros((S, S), np.float32), 'beard': np.zeros((S, S), np.float32)}
        masks['skin'][8:] = 1; masks['beard'][32:] = 1; skinlike = masks['skin'] > .5; mapped = np.ones((S, S), bool)
        keep = beard_hair(labels, masks, mapped, colour, skinlike)
        self.assertTrue(keep[40:50, 10:30].all()); self.assertFalse(keep[40:50, 34:54].any()); self.assertFalse(keep[:32].any())


class Iris(unittest.TestCase):
    def test_refined_within_guards(self):
        S = 400; yy, xx = np.mgrid[0:S, 0:S]; luma = np.full((S, S), 230, np.float32); pts = np.zeros((478, 2))
        for side, (c, ring) in IRIS.items():
            centre = (120 if side == 'R' else 280, 200); luma[np.hypot(xx-centre[0], yy-centre[1]) < 20] = 40
            pts[c] = centre; pts[list(ring)] = [(centre[0]+22*np.cos(a), centre[1]+22*np.sin(a)) for a in np.linspace(0, 2*np.pi, 4, endpoint=False)]
        circles, refined = iris_circles(luma, pts)
        self.assertTrue(refined); self.assertAlmostEqual(circles['R'][1], 20, delta=1.5)


class Channels(unittest.TestCase):
    def test_moves(self):
        labels = np.zeros((4096, 4096), np.uint8); labels[100:110, 100:200] = 1   # hair-owned brow region partly
        masks = flat('iris', 'eye', 'brow', 'skin', 'lips', 'nose', 'hairlock'); mapped = np.ones((4096, 4096), bool)
        masks['eye'][1000:1020, 1000:1040] = 1; masks['iris'][1005:1015, 1015:1025] = 1
        masks['brow'][95:105, 100:200] = 1; masks['skin'][105:110, 100:200] = 1; masks['hairlock'][3000:3010, 3000:3010] = 1
        o, report = apply_channels(labels, masks, mapped)
        self.assertTrue((o[1005:1015, 1015:1025] == 8).all()); self.assertTrue((o[1000:1020, 1000:1010] == 0).all())
        self.assertTrue((o[95:105, 100:200] == 1).all()); self.assertTrue((o[105:110, 100:200] == 0).all())
        self.assertTrue((o[3000:3010, 3000:3010] == 1).all()); self.assertEqual(report['hairLockToHair'], 100)

    def test_tattoo1_holds_only_the_iris(self):
        # rule-owned tattoo1 away from the eye (troll horns, tusks) takes tattoo2; tattoo2 ink stays (user 2026-10-30)
        labels = np.zeros((4096, 4096), np.uint8); labels[2000:2010, 2000:2020] = 8; labels[2500:2510, 2500:2510] = 9
        masks = flat('iris', 'eye', 'brow', 'skin', 'lips', 'nose', 'hairlock'); mapped = np.ones((4096, 4096), bool)
        masks['eye'][1000:1020, 1000:1040] = 1; masks['iris'][1005:1015, 1015:1025] = 1
        o, report = apply_channels(labels, masks, mapped)
        self.assertTrue((o[2000:2010, 2000:2020] == 9).all()); self.assertTrue((o[2500:2510, 2500:2510] == 9).all())
        self.assertEqual(report['tattoo1ToTattoo2'], 200); self.assertEqual(int((o == 8).sum()), 100)

    def test_majority_and_consistent_blocks(self):
        labels = np.zeros((8, 8), np.uint8); labels[0, :3] = 1; labels[1, :3] = 1; labels[0:2, 3] = 9
        self.assertEqual(majority(labels).tolist(), [[0, 0], [0, 0]])
        colour = np.zeros((8, 8, 3), np.float32); colour[labels == 0] = 100; colour[labels != 0] = 250
        fixed, count = consistent_blocks(colour, labels)
        self.assertEqual(count, 1); self.assertTrue(np.allclose(fixed[:4, :4], 100))


class Treatment(unittest.TestCase):
    def test_delight_only_darkens(self):
        value = {'positions': np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float),
                 'faces': np.array([[0, 1, 2], [0, 2, 3]]), 'uv': np.array([[[0, 0], [1, 0], [1, 1]], [[0, 0], [1, 1], [0, 1]]], float)*.999+.0005}
        value['positions'][:, 2] = 1; value['positions'] = np.r_[value['positions'], [[0, 0, 0]]]   # a front-facing plane (unused vertex sets the depth)
        yy, xx = np.mgrid[0:4096, 0:4096]; colour = np.repeat((120+60*np.exp(-((xx-2048)**2+(yy-2048)**2)/600**2))[..., None], 3, 2).astype(np.float32)
        settings = {k: 0 for k in TREATMENT}; settings['delight'] = .8
        out, report = treat(colour, np.zeros((4096, 4096), np.uint8), flat('iris', 'eye', 'brow', 'lips', 'nose', 'lipline', 'socket'), value, settings)
        self.assertLessEqual(float((out-colour).max()), 1e-3); self.assertLess(float(out[2048, 2048, 0]), float(colour[2048, 2048, 0]))


class Region(unittest.TestCase):
    def test_front_triangles(self):
        positions = np.array([[0, 0, 1], [1, 0, 1], [0, 1, 1], [0, 0, 0], [1, 0, 0], [0, 0, -1]], float)
        faces = np.array([[0, 1, 2], [3, 4, 5]]); face, area = face_region(positions, faces)
        self.assertEqual(face.tolist(), [True, False]); self.assertAlmostEqual(area[0], .5)

    def scene(self, shared):
        """A front quad (face) and a back quad at the same UV density; `shared` joins one face and one back triangle
        into a single chart (a shared UV vertex), as mixed charts do on the real heads."""
        positions = np.array([[0, 0, 1], [1, 0, 1], [1, .5, 1], [0, .5, 1], [0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]], float)
        faces = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
        x = .3 if shared else .5   # shared: the back chart's first corner is the face chart's (.3, .2) corner
        uv = np.array([[[.1, .1], [.3, .1], [.3, .2]], [[.1, .1], [.3, .2], [.1, .2]],
                       [[x, .2], [x, .4], [x+.2, .4]], [[x, .2], [x+.2, .4], [x+.2, .2]]])
        return positions, faces, uv

    def test_face_priority_reaches_the_ratio_on_pure_face_charts(self):
        from headkit.test_headkit import FakePacker
        from headkit.uv import face_priority
        positions, faces, uv = self.scene(False); _, report = face_priority(FakePacker(), uv, positions, faces, 3.0, 2)
        self.assertAlmostEqual(report['measuredDensityRatio'], 3.0, delta=.3)
        positions, faces, uv = self.scene(True); _, mixed = face_priority(FakePacker(), uv, positions, faces, 3.0, 2)
        self.assertLess(mixed['measuredDensityRatio'], 1.2)   # one chart, one scale: a mixed chart gives the face nothing extra

    def test_grown_charts_scale_on_top_of_the_ratio(self):
        # RUNBOOK 144: a chart the smaller page left sub-texel grows; growing the back chart by sqrt(3) evens out the densities.
        from headkit.test_headkit import FakePacker
        from headkit.uv import face_priority, chart_ids
        positions, faces, uv = self.scene(False); back = int(chart_ids(uv, shared='vertex')[2])
        _, report = face_priority(FakePacker(), uv, positions, faces, 3.0, 2, {back: 3**.5})
        self.assertAlmostEqual(report['measuredDensityRatio'], 1.0, delta=.1); self.assertEqual(report['grownCharts'], 1)


class Quality(unittest.TestCase):
    def test_thresholds_complete_and_eligible_range(self):
        self.assertEqual(set(read(THRESHOLDS)['limits']), CHECKS)
        row = np.zeros((256, 4), np.uint8); row[10:200, 3] = 255; self.assertEqual(eligible(row), (10, 198))

    def test_flat_channels_keep_the_palette_exemption(self):
        palette = {'layers': {'0': {'shadeRange': {'checked': True}}, '2': {'shadeRange': {'checked': False}}, '9': {}}}
        fails, exempt = shade_span_failures({'0': .5, '2': 0.0, '9': .9}, palette, .75)
        self.assertEqual(fails, ['shadeSpan0']); self.assertEqual(exempt, ['2'])
        # A body-pinned skin needs only the body minimum (RUNBOOK 154); other channels keep the full one.
        palette['layers']['0']['shadeRange']['skinMedian'] = {'target': 99, 'achieved': 99.0}
        self.assertEqual(shade_span_failures({'0': .6, '9': .6}, palette, .75, .5)[0], ['shadeSpan9'])
        # RUNBOOK 159: hair whose brightest or darkest source value holds over the limit is exempt; other channels are not.
        palette['layers']['1'] = {'shadeRange': {'checked': True, 'endTie': .14}}; palette['layers']['9'] = {'shadeRange': {'checked': True, 'endTie': .14}}
        self.assertEqual(shade_span_failures({'1': .66, '9': .66}, palette, .75, .5, .1), (['shadeSpan9'], ['1']))
        palette['layers']['1']['shadeRange']['endTie'] = .05; self.assertEqual(shade_span_failures({'1': .66}, palette, .75, .5, .1)[0], ['shadeSpan1'])

    def test_seam_step_ratio_finds_tone_patches_at_chart_borders(self):
        # RUNBOOK 153: a plane of skin texels split into two charts at x=.5; even texture scores ~1, a flat offset at the seam more.
        from headkit.quality import seam_step_ratio
        ys, xs = np.mgrid[0:64, 0:64]/64.; points = np.c_[xs.ravel(), ys.ravel(), np.zeros(xs.size)]; charts = (points[:, 0] >= .5).astype(int)
        ramp = np.random.default_rng(1).integers(100, 104, len(points)).astype(np.uint8); patch = ramp+np.where(charts == 1, 12, 0).astype(np.uint8)
        smooth, stepped = (seam_step_ratio(points, charts, s, 1.5) for s in (ramp, patch))
        self.assertLess(smooth, 1.3); self.assertGreater(stepped, 2.0); self.assertIsNone(seam_step_ratio(points, np.zeros(len(points), int), ramp, 1.5))

    def test_skin_median_offset_needs_the_body_anchor(self):
        # RUNBOOK 154: a stretched skin without the body skin's median fails; a flat skin has nothing to anchor.
        from headkit.quality import skin_median_offset
        layer = lambda **range_: {'layers': {'0': {'shadeRange': range_}}}
        self.assertIsNone(skin_median_offset(layer(checked=True)))
        self.assertEqual(skin_median_offset(layer(checked=True, skinMedian={'target': 99, 'achieved': 104.0})), 5.0)
        self.assertEqual(skin_median_offset(layer(checked=False)), 0.0); self.assertEqual(skin_median_offset({'layers': {}}), 0.0)
        # RUNBOOK 158: the darkest face skin against the plain skin, measured only for a body-pinned skin.
        from headkit.quality import face_dark_ratio
        face, plain = np.r_[np.zeros(5), np.full(95, 60)], np.full(50, 100); pinned = layer(checked=True, skinMedian={'target': 99, 'achieved': 99.0})
        self.assertEqual(face_dark_ratio(pinned, face, plain), 0.0); self.assertEqual(face_dark_ratio(pinned, face+20, plain), .2)
        self.assertIsNone(face_dark_ratio(layer(checked=True), face, plain)); self.assertIsNone(face_dark_ratio(pinned, face[:0], plain))

    def test_cybereye_side_setting_is_checked_before_any_work(self):
        from headkit.quality import quality
        with tempfile.TemporaryDirectory() as root:
            for settings in ({'cybereyeImageSide': 'top'}, {'cybereye': 'left'}):
                with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, 'cybereyeImageSide'):
                    quality('uv.glb', {}, {}, {}, Path(root)/'q', settings=settings)
                self.assertFalse((Path(root)/'q').exists())


class Wiring(unittest.TestCase):
    def test_stage_order_and_declarations(self):
        self.assertLess(STAGES.index('masks'), STAGES.index('ownership')); self.assertLess(STAGES.index('palette'), STAGES.index('quality'))
        self.assertLess(STAGES.index('quality'), STAGES.index('export'))
        self.assertEqual(stage_libraries('masks', {}), {'mediapipe', 'onnxruntime'})
        self.assertEqual(stage_roles('masks', {'inputs': {'uvMesh': {}, 'design': {}}}), {'uvMesh'})

    def test_face_sections_go_together(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'m.json'; base = {'schemaVersion': 1, 'id': 'x', 'inputs': {}}
            write(path, base); manifest(path)
            full = dict(base, faceMasks={}, quality={}, ownership={'featureChannels': True}, tone={'faceTreatment': {}},
                        palette={'fullShadeRange': True})
            path.write_text(json.dumps(full)); manifest(path)
            for drop in ('faceMasks', 'quality', 'palette'):
                path.write_text(json.dumps({k: v for k, v in full.items() if k != drop}))
                with self.assertRaises(ValueError): manifest(path)

    def test_face_masks_refuse_imported_runtime_atlases(self):
        """Export must ship the shades the quality gate measured, built through the channel moves and treatment."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'atlas.png').write_bytes(b'x'); path = root/'m.json'
            full = {'schemaVersion': 1, 'id': 'x', 'inputs': {}, 'faceMasks': {}, 'quality': {}, 'ownership': {'featureChannels': True},
                    'tone': {'faceTreatment': {}}, 'palette': {'fullShadeRange': True}}
            for role in ('runtimeColor', 'runtimeShades', 'ownership1k'):
                data = dict(full, inputs={role: {'path': 'atlas.png', 'sha256': hashlib.sha256(b'x').hexdigest()}})
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, role): manifest(path)
                path.write_text(json.dumps({k: v for k, v in data.items() if k not in ('faceMasks', 'quality', 'ownership', 'tone', 'palette')}))
                manifest(path)


class ToneWithFaceTreatment(unittest.TestCase):
    def runner(self, root, data):
        from headkit.runner import Runner
        from PIL import Image
        colour, ownership, imported, detail = (root/n for n in ('colour.png', 'own.png', 'imported.png', 'detail.png'))
        Image.new('RGB', (4096, 4096), (120, 90, 70)).save(colour); Image.new('L', (4096, 4096), 0).save(ownership)
        Image.new('L', (4096, 4096), 1).save(imported); Image.new('RGB', (64, 64)).save(detail)
        r = Runner.__new__(Runner); r.data = data; r.bindings = {}
        results = {'ownership': {'fourk': {'path': str(ownership)}}, 'masks': {'files': {}}}
        r.result = lambda stage, **_: results[stage]; r.source = lambda *a: None
        r.input = lambda name: str({'ownership4k': imported, 'detail': detail}[name]); r._color4k = lambda **_: str(colour)
        return r, ownership

    def test_reference_matching_and_imported_atlas(self):
        """Face treatment with reference tone matching and an imported ownership4k: tone_match gets only its skin/hair
        samples, and the treatment reads the ownership stage's feature-adjusted atlas, not the imported one."""
        from unittest import mock
        data = {'inputs': {'ownership4k': {}, 'detail': {}}, 'ownership': {'featureChannels': True}, 'palette': {'inputs': {}},
                'tone': {'skin': {'x': 1}, 'hair': {'x': 2}, 'faceTreatment': {}}}
        self.assertNotIn('ownership4k', stage_roles('tone', data))
        from headkit.runner import Runner
        bare = Runner.__new__(Runner); bare.data = dict(data, fit={}); self.assertIn('ownership', bare.dependencies('tone'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); r, adjusted = self.runner(root, data); seen = {}
            def fake_match(color, ownership, reference, config, output):
                seen['config'] = set(config); seen['ownership'] = Path(ownership)
                from PIL import Image
                Image.open(color).save(output); return {}
            def fake_treat(rgb, labels, masks, value, settings):
                seen['labels'] = int(labels.max()); return rgb, {}
            with mock.patch('headkit.textures.tone_match', fake_match), mock.patch('headkit.face_encode.treat', fake_treat),                  mock.patch('headkit.face_encode.masks_at', lambda *a: {}), mock.patch('headkit.gltf.mesh', lambda *a: None):
                result = r._execute('tone', root)
        self.assertEqual(seen['config'], {'skin', 'hair'}); self.assertEqual(seen['ownership'], adjusted)
        self.assertEqual(seen['labels'], 0); self.assertEqual(result['ownershipInputRole'], 'ownership')


if __name__ == '__main__':
    unittest.main()
