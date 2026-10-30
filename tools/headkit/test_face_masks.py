"""Focused tests of the face-mask stages on synthetic inputs (no models, Embree or xatlas needed)."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from headkit.common import manifest, write, read
from headkit.face_masks import hair_locks, brow_mask, iris_circles, IRIS, HAIR, SKIN
from headkit.face_encode import apply_channels, majority, consistent_blocks, treat, TREATMENT
from headkit.quality import eligible, CHECKS, THRESHOLDS
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
        grown = brow_mask(rgb, labels, np.zeros((S, S), bool), np.ones((S, S), bool))
        self.assertGreater(grown[50:60, 41:99].mean(), .95); self.assertFalse(grown[:, 100:].any())


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


class Quality(unittest.TestCase):
    def test_thresholds_complete_and_eligible_range(self):
        self.assertEqual(set(read(THRESHOLDS)['limits']), CHECKS)
        row = np.zeros((256, 4), np.uint8); row[10:200, 3] = 255; self.assertEqual(eligible(row), (10, 198))


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


if __name__ == '__main__':
    unittest.main()
