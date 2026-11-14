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
        # A depth face keeps its direction where the gain is constant; across the guard-blend ramp the thinned face
        # slopes along the length, so its normal tilts with it (test_straightness checks that it stays perpendicular).
        flat = hilt | tip; np.testing.assert_allclose(turned[flat], normals[flat], atol=2e-3)
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

    def test_stretch_lengthens_only_its_span_and_reapplies(self):
        p = pommelled(); mapping = s.fit_stretch(p, (.05, .2), 1.5)
        mean, axes = mapping['mean'], mapping['axes']; t = (p - mean) @ axes[:, 0]; (t0, t1) = mapping['span']
        normals = np.tile([0., 0., 1.], (len(p), 1)); out, turned = s.apply_stretch(p, mapping, normals)
        moved = (out - mean) @ axes[:, 0]; side = lambda q: (q - mean) @ axes[:, 1:]
        below, inside, above = t <= t0, (t > t0) & (t < t1), t >= t1
        np.testing.assert_allclose(out[below], p[below], atol=1e-12)                                     # one end stays put
        np.testing.assert_allclose(moved[above] - t[above], .5 * (t1 - t0), atol=1e-9)                  # the other moves rigidly
        np.testing.assert_allclose(moved[inside], t0 + 1.5 * (t[inside] - t0), atol=1e-9)
        np.testing.assert_allclose(side(out), side(p), atol=1e-9)                                        # width and depth unchanged
        self.assertAlmostEqual(np.ptp(moved), np.ptp(t) + .5 * (t1 - t0), places=9)
        self.assertTrue(np.allclose(np.linalg.norm(turned, axis=1), 1))
        with self.assertRaisesRegex(ValueError, 'factor'): s.fit_stretch(p, (.05, .2), .9)
        with self.assertRaisesRegex(ValueError, 'span'): s.fit_stretch(p, (.2, .05), 1.5)

    def test_glb_stretch_keeps_topology_and_uvs(self):
        rng = np.random.default_rng(2); p = pommelled()[::4]; n = len(p) // 3 * 3; p = p[:n]
        faces = np.arange(n).reshape(-1, 3); uv = rng.uniform(.1, .9, (len(faces), 3, 2))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder/'p.glb'; write_mesh(source, p, faces, uv)
            result = s.stretch(source, folder/'out', (.05, .2), 1.5); after = mesh(folder/'out/stretched.glb'); original = mesh(source)
            np.testing.assert_array_equal(after['faces'], original['faces']); np.testing.assert_array_equal(after['uv'], original['uv'])
            self.assertGreater(result['lengthAfter'], result['lengthBefore'])
            again = s.stretch(source, folder/'again', map_path=folder/'out/stretch-map.npz')
            self.assertEqual(again['output']['sha256'], result['output']['sha256']); self.assertEqual(again['map']['mode'], 'applied')
            with self.assertRaisesRegex(ValueError, 'own parameters'): s.stretch(source, folder/'x', (.05, .2), 1.5, folder/'out/stretch-map.npz')

    def test_narrow_pulls_guard_tips_in_rigidly(self):
        p = pommelled(); mean, axes = s.principal_frame(p); q = (p - mean) @ axes; length = np.ptp(q[:, 0])
        f = (q[:, 0] - q[:, 0].min()) / length; at = lambda x: float(f[np.argmin(np.abs(p[:, 0] - x))])
        span = tuple(sorted((at(-.035), at(.015))))           # the cross-guard (model X -0.02..0), on whichever end the frame puts it
        guard = (f >= span[0]) & (f <= span[1]); band = (.04 / length, .08 / length)
        mapping = s.fit_narrow(p, span, band, .5)
        normals = np.tile([0., 0., 1.], (len(p), 1)); out, turned = s.apply_narrow(p, mapping, normals)
        r = (out - mean) @ axes; a = q[:, 1] - mapping['centre']
        np.testing.assert_allclose(out[~guard], p[~guard], atol=1e-12)                                 # outside the span: unchanged
        np.testing.assert_allclose(r[:, [0, 2]], q[:, [0, 2]], atol=1e-9)                              # length and depth unchanged
        far = guard & (np.abs(a) >= .08); np.testing.assert_allclose(np.abs(r[far, 1] - mapping["centre"]), np.abs(a[far]) - .02, atol=1e-9)
        core = np.abs(a) <= .04; np.testing.assert_allclose(r[core], q[core], atol=1e-9)
        self.assertTrue(np.allclose(np.linalg.norm(turned, axis=1), 1))
        with self.assertRaisesRegex(ValueError, 'tear'): s.fit_narrow(p, (sum(span) / 2, span[1]), band, .5)   # cuts through the guard
        with self.assertRaisesRegex(ValueError, 'factor'): s.fit_narrow(p, span, band, 1.2)
        rng = np.random.default_rng(2); small = p[::4]; n = len(small) // 3 * 3; small = small[:n]
        faces = np.arange(n).reshape(-1, 3); uv = rng.uniform(.1, .9, (len(faces), 3, 2))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder/'p.glb'; write_mesh(source, small, faces, uv)
            result = s.narrow(source, folder/'out', span, band, .5)
            after = mesh(folder/'out/narrowed.glb'); np.testing.assert_array_equal(after['uv'], mesh(source)['uv'])
            self.assertLess(result['widthAfter'], result['widthBefore'])
            again = s.narrow(source, folder/'again', map_path=folder/'out/narrow-map.npz')
            self.assertEqual(again['output']['sha256'], result['output']['sha256'])
            low = np.asarray(result['lowEndVertex'])                     # the pommel or the blade tip, whichever the frame chose
            self.assertTrue(np.isclose(low[0], -.244, atol=.01) or np.isclose(low[0], .8, atol=.01), low)
            np.testing.assert_allclose(np.abs(result['longAxis']), [1, 0, 0], atol=.01)
            # The saved map's tear guard is checked on the mesh it is re-applied to (the donor), not only where it was fitted.
            moved = folder/'moved.glb'; write_mesh(moved, small + [.02, 0, 0], faces, uv)
            with self.assertRaisesRegex(ValueError, 'tear'): s.narrow(moved, folder/'torn', map_path=folder/'out/narrow-map.npz')

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
