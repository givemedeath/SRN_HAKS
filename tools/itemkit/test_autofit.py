"""Automatic landmarks, stock-length grip span, vertex-free cuts, blade thinning and thick-part flags."""
import tempfile, unittest
from pathlib import Path
import numpy as np
from tools.headkit.gltf import mesh, write_mesh
from . import autofit, straightness as s
from .test_straightness import sword


def pommelled(blade_depth=.006, guard_depth=.01):
    """The synthetic sword with a ball pommel, an adjustable blade thickness and guard depth."""
    rng = np.random.default_rng(3); p = sword()
    blade = p[:, 0] > 0; p[blade, 2] *= blade_depth / .006
    guard = (p[:, 0] >= -.02) & (p[:, 0] <= 0) & (np.abs(p[:, 1]) > .013); p[guard, 2] *= guard_depth / .01
    u = rng.normal(size=(6000, 3)); ball = u / np.linalg.norm(u, axis=1)[:, None] * .022 + [-.222, 0, 0]
    return np.r_[p, ball]


class AutofitTests(unittest.TestCase):
    def test_landmarks_find_pommel_grip_guard_and_blade(self):
        found = autofit.landmarks(pommelled()); m = found['landmarks']; length = found['length']
        self.assertEqual(found['method'], 'cross-guard'); self.assertAlmostEqual(length, 1.044, delta=.01)
        at = lambda fraction: fraction * length - .244                       # back to the model's X
        self.assertAlmostEqual(at(m['pommelEnd']), -.2, delta=.012); self.assertEqual(m['gripStart'], m['pommelEnd'])
        self.assertAlmostEqual(at(m['gripEnd']), -.02, delta=.012); self.assertAlmostEqual(at(m['bladeStart']), 0, delta=.012)
        mirrored = autofit.landmarks(pommelled() * [-1, 1, 1])['landmarks']     # blade direction is found, not assumed
        for key in m: self.assertAlmostEqual(mirrored[key], m[key], delta=.011)

    def test_grip_span_targets_the_stock_length_and_never_cuts_the_strict_span(self):
        m = {'pommelEnd': .055, 'gripStart': .055, 'gripEnd': .2, 'bladeStart': .26}       # the wave-1 Sword
        start = autofit.grip_start_for_length(m, .1831918, 1.10)
        self.assertAlmostEqual(start, .0335, delta=.0005)
        self.assertAlmostEqual(.1831918 / (m['gripEnd'] - start), 1.10, delta=1e-9)       # resulting weapon length
        knife = {'pommelEnd': .085, 'gripStart': .085, 'gripEnd': .475, 'bladeStart': .54}
        self.assertEqual(autofit.grip_start_for_length(knife, .1831918, .612), .085)       # already shorter: unchanged
        self.assertEqual(autofit.grip_start_for_length(m, .1831918, .5), 0.)
        with self.assertRaisesRegex(ValueError, 'exceed the grip'): autofit.grip_start_for_length(m, .2, .1)

    def test_part_cut_moves_off_vertices_within_its_reach(self):
        ys = np.r_[np.full(40, .1), np.linspace(.0996, .1004, 9), .5]
        cut, clearance = autofit.clear_cut(ys, .1)
        self.assertLessEqual(abs(cut - .1), .0003 + 1e-12); self.assertGreater(clearance, .00004)
        self.assertGreater(np.abs(ys - cut).min(), .00004)
        self.assertEqual(autofit.clear_cut(ys, .3), (.3, None))

    def test_thick_blade_and_slab_guard_are_flagged(self):
        flags = lambda p: [f['metric'] for f in s.assess(s.measure(p))['flags']]
        self.assertEqual(flags(pommelled()), [])
        self.assertNotIn('bladeDepthToWidth', flags(pommelled(blade_depth=.012)))                  # 0.40, the accepted Sword
        self.assertIn('bladeDepthToWidth', flags(pommelled(blade_depth=.02)))                      # 0.67, the rejected Claymore
        self.assertIn('guardSectionRatio', flags(pommelled(guard_depth=.06)))

    def test_thinning_scales_only_blade_depth_and_reapplies(self):
        fat = pommelled(blade_depth=.014); mapping, report = s.fit_thin(fat, .2); out = s.apply_thin(fat, mapping)
        self.assertGreater(report['bladeDepthToWidthBefore'], .4); self.assertAlmostEqual(s.measure(out)['bladeDepthToWidth'], .2, delta=.03)
        hilt = fat[:, 0] < -.04; np.testing.assert_allclose(out[hilt], fat[hilt], atol=1e-9)          # grip and pommel untouched
        np.testing.assert_allclose(out[:, :2], fat[:, :2], atol=2e-5)                              # length and width unchanged
        tip = fat[:, 0] > .3; np.testing.assert_allclose(out[tip, 2], fat[tip, 2] * report['depthFactor'], atol=5e-5)
        normals = np.tile([0., 0., 1.], (len(fat), 1)); _, turned = s.apply_thin(fat, mapping, normals)
        np.testing.assert_allclose(turned, normals, atol=2e-3)                                    # a face normal along depth keeps its direction
        with self.assertRaisesRegex(ValueError, 'No cross-guard'): s.fit_thin(fat[(fat[:, 0] > .02)], .2)
        with self.assertRaisesRegex(ValueError, 'target'): s.fit_thin(fat, .9)
        halved = s.fit_thin(fat)[1]; self.assertEqual(halved['depthFactor'], .5)                  # the reviewed default
        self.assertAlmostEqual(halved['target'], halved['bladeDepthToWidthBefore'] / 2)
        self.assertEqual(s.fit_thin(fat, factor=.7)[1]['depthFactor'], .7)
        with self.assertRaisesRegex(ValueError, 'not both'): s.fit_thin(fat, .2, .5)
        with self.assertRaisesRegex(ValueError, 'factor'): s.fit_thin(fat, factor=.05)

    def test_glb_thinning_keeps_topology_and_uvs(self):
        rng = np.random.default_rng(2); fat = pommelled(blade_depth=.014)[::4]; n = len(fat) // 3 * 3; fat = fat[:n]
        faces = np.arange(n).reshape(-1, 3); uv = rng.uniform(.1, .9, (len(faces), 3, 2))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder/'fat.glb'; write_mesh(source, fat, faces, uv); before = source.read_bytes()
            result = s.thin(source, folder/'out', target_ratio=.2); after = mesh(folder/'out/thinned.glb'); original = mesh(source)
            self.assertEqual(source.read_bytes(), before); self.assertTrue(result['outlineExtentsUnchanged'])
            np.testing.assert_array_equal(after['faces'], original['faces']); np.testing.assert_array_equal(after['uv'], original['uv'])
            again = s.thin(source, folder/'again', folder/'out/thin-map.npz')
            self.assertEqual(again['output']['sha256'], result['output']['sha256'])

    def test_shell_thinning_keeps_a_closed_solid(self):
        try: import pymeshlab
        except ImportError: self.skipTest('pymeshlab not on the path')
        ms = pymeshlab.MeshSet(); ms.create_sphere(radius=1, subdiv=5); c = ms.current_mesh()
        v, f = c.vertex_matrix() * [3, 1, .5], c.face_matrix()
        out_v, out_f, report = autofit.thin_shell(v, f, pymeshlab, triangles=2000, tolerance=.03)
        self.assertLessEqual(len(out_f), 2100); self.assertEqual(report['genus'], 0); self.assertAlmostEqual(report['volumeRatio'], 1, delta=.02)
        same_v, same_f, same = autofit.thin_shell(out_v, out_f, pymeshlab, triangles=5000); self.assertTrue(same['unchanged'])
        with self.assertRaisesRegex(ValueError, 'Closed outward'): autofit.thin_shell(v, f[:-10], pymeshlab, triangles=2000)


if __name__ == '__main__':
    unittest.main()
