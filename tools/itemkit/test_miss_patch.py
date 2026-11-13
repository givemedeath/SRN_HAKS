"""Bake-miss screening, patch measurement and reviewed patch manifests on synthetic spheres."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tools.itemkit import miss_patch as M
from tools.itemkit.geometry import corner_hash
from tools.itemkit.preflight import target_hash
from tools.itemkit.test_shell_repair import sphere


def planar_uv(corners):
    """Per-corner UVs from x/y, inside the atlas."""
    uv = corners[:, :, :2]; return (uv - uv.min((0, 1)))/(np.ptp(uv.reshape(-1, 2), 0).max()*1.01)


MANIFEST = {'processing': {'missCorrection': {'method': 'nearest-finished-donor', 'maximumDistance': .003, 'minimumNormalAlignment': .5}}}


class TargetTests(unittest.TestCase):
    def test_parts_join_in_native_order_with_offsets(self):
        (bv, bf), (tv, tf) = sphere(), sphere(centre=(0, 0, .2))
        values = {'t_positions': tv, 't_faces': tf, 't_hiddenCaps': np.zeros(len(tf), bool),
                  'b_positions': bv, 'b_faces': bf, 'b_hiddenCaps': np.r_[True, np.zeros(len(bf) - 1, bool)]}
        target = M.joined_target(values)
        self.assertEqual(target['parts'], ['b', 't']); self.assertIsNone(target['uv'])
        np.testing.assert_array_equal(target['corners'][len(bf):], tv[tf]); self.assertTrue(target['hiddenCaps'][0])
        with self.assertRaisesRegex(ValueError, 'one whole mesh'): M.joined_target({**values, 'whole_positions': bv})


class ScreenAndMeasureTests(unittest.TestCase):
    def setUp(self):
        try:
            import igl, scipy  # noqa: F401
        except ImportError: self.skipTest('igl and scipy not on the path (itemkit PYTHONPATH)')
        self.v, self.f = sphere(); self.corners = self.v[self.f]; self.caps = np.zeros(len(self.f), bool)

    def test_a_matching_donor_passes_and_a_reversed_or_distant_one_fails(self):
        self.assertEqual(M.screen(self.corners, self.caps, self.v, self.f)['failedFaces'], [])
        reversed_faces = M.screen(self.corners, self.caps, self.v, self.f[:, ::-1])['failedFaces']
        self.assertEqual(len(reversed_faces), len(self.f))                  # inside-out: nothing faces the same way
        far = M.screen(self.corners, self.caps, self.v*1.2, self.f)        # 10 mm outside everywhere
        self.assertEqual(len(far['failedFaces']), len(self.f))
        self.caps[:5] = True
        self.assertEqual(M.screen(self.corners, self.caps, self.v*1.2, self.f)['visibleFaces'], len(self.f) - 5)
        with self.assertRaisesRegex(ValueError, 'Bounded'): M.screen(self.corners, self.caps, self.v, self.f, distance=.01)

    def test_measure_reports_distances_texels_and_the_target_hashes(self):
        uv = planar_uv(self.corners); donor = self.v*1.02                  # 1 mm outside at the 50 mm radius
        result = M.measure(self.corners, uv, [3, 40], donor, self.f, 1024, 400000)
        self.assertEqual([r['face'] for r in result['faces']], [3, 40])
        for row in result['faces']:
            self.assertGreater(row['sampledMaxMm'], .9); self.assertLess(row['sampledMaxMm'], 1.1)
            self.assertGreater(row['nearestFacing'], .95); self.assertGreater(row['texels'], 0)
        self.assertGreaterEqual(result['maximumDistance'], max(r['sampledMaxMm'] for r in result['faces'])/1e3)
        self.assertEqual(result['cornerHash'], corner_hash(self.corners))
        self.assertEqual(result['targetHash'], target_hash(self.corners, uv))
        self.assertAlmostEqual(result['textureFraction'], result['texels']/400000)

    def test_measure_run_refuses_a_report_from_another_target(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)/'run-fit-v1'; atlas = run/'unwrap/attempt-1/atlas'; atlas.mkdir(parents=True)
            uv = planar_uv(self.corners)
            np.savez(atlas/'final-atlas.npz', whole_positions=self.v, whole_faces=self.f, whole_hiddenCaps=self.caps, whole_uv=uv)
            report = Path(folder)/'preflight.json'
            report.write_text(json.dumps({'targetHash': 'other', 'size': 1024, 'donorSampling': {'failedFaces': [3]}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'different target'): M.measure_run(run, 'unused.glb', report)
            report.write_text(json.dumps({'size': 1024, 'donorSampling': {'failedFaces': []}}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no failed faces'): M.measure_run(run, 'unused.glb', report)
            retry = run/'unwrap/attempt-2/atlas'; retry.mkdir(parents=True)
            np.savez(retry/'final-atlas.npz', whole_positions=self.v, whole_faces=self.f, whole_hiddenCaps=self.caps, whole_uv=uv)
            with self.assertRaisesRegex(ValueError, '2 unwrap arrays.*--arrays'): M.run_target(run)   # never a guess between attempts
            self.assertEqual(M.run_target(run, retry/'final-atlas.npz')['source'], str(retry/'final-atlas.npz'))


class PatchTests(unittest.TestCase):
    def setUp(self):
        v, f = sphere(); self.corners = v[f]

    def test_a_patch_is_bound_to_the_exact_target_and_raises_the_unoriented_bound(self):
        out = M.add_patch(MANIFEST, self.corners, [7, 3], .0025, 'Reviewed the seam faces.')
        policy = out['processing']['missCorrection']; patch = policy['unorientedSourcePatch']
        self.assertEqual((patch['faces'], patch['maximumDistance'], patch['maximumTextureFraction']), ([3, 7], .0025, .0001))
        self.assertEqual(patch['targetCornerHash'], corner_hash(self.corners)); self.assertTrue(patch['reviewed'])
        self.assertEqual(policy['maximumUnorientedDistance'], .0025)
        self.assertNotIn('unorientedSourcePatch', MANIFEST['processing']['missCorrection'])          # the source is not changed
        small = M.add_patch(MANIFEST, self.corners, [3], .0015, 'Reviewed.')['processing']['missCorrection']
        self.assertNotIn('maximumUnorientedDistance', small)                                          # the 2.1 mm default covers it

    def test_the_extended_scope_needs_the_users_words(self):
        with self.assertRaisesRegex(ValueError, "at most 3 mm without the user's approval"):
            M.add_patch(MANIFEST, self.corners, [3], .0032, 'Reviewed.')
        out = M.add_patch(MANIFEST, self.corners, [3], .0032, 'Reviewed.', user_approval='Allow 3.25 mm')
        patch = out['processing']['missCorrection']['unorientedSourcePatch']
        self.assertEqual((patch['userApproval'], patch['maximumTextureFraction']), ('Allow 3.25 mm', .0005))
        with self.assertRaisesRegex(ValueError, 'at most 3.25 mm'):
            M.add_patch(MANIFEST, self.corners, [3], .0034, 'Reviewed.', user_approval='Allow 3.25 mm')

    def test_a_patch_needs_its_review_the_bounded_policy_and_a_small_face_scope(self):
        with self.assertRaisesRegex(ValueError, 'quotes its review'): M.add_patch(MANIFEST, self.corners, [3], .002, ' ')
        with self.assertRaisesRegex(ValueError, 'nearest-finished-donor'): M.add_patch({'processing': {}}, self.corners, [3], .002, 'R.')
        with self.assertRaisesRegex(ValueError, 'bounded face/surface scope'):
            M.add_patch(MANIFEST, self.corners, list(range(40)), .002, 'Reviewed.')


if __name__ == '__main__':
    unittest.main()
