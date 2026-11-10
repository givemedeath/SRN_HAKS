"""Bent, twisted and skewed long weapons are flagged; straightening is rigid per section and re-appliable."""
import tempfile, unittest
from pathlib import Path
import numpy as np
from tools.headkit.gltf import mesh, write_mesh
from . import straightness as s


def sword(bow=0., twist=0., skew=0., seed=0):
    """Surface point cloud: flat blade, round grip and a cross-guard; long axis X, blade width Y, depth Z."""
    rng = np.random.default_rng(seed)
    def box(n, lo, hi):
        p = rng.uniform(lo, hi, (n, 3)); face = rng.integers(0, 2, n); side = rng.integers(1, 3, n)   # width and depth faces only
        p[np.arange(n), side] = np.where(face, np.asarray(hi)[side], np.asarray(lo)[side]); return p
    blade = box(60000, [0, -.03, -.006], [.8, .03, .006]); grip = box(15000, [-.2, -.012, -.012], [-.02, .012, .012])
    guard = box(8000, [-.02, -.12, -.01], [0, .12, .01])
    if skew:
        a = np.radians(skew); x, y = guard[:, 0] + .01, guard[:, 1].copy()
        guard[:, 0] = x * np.cos(a) + y * np.sin(a) - .01; guard[:, 1] = -x * np.sin(a) + y * np.cos(a)
    if twist:
        a = np.radians(twist) * np.clip(blade[:, 0] / .8, 0, 1); y, z = blade[:, 1].copy(), blade[:, 2].copy()
        blade[:, 1] = y * np.cos(a) - z * np.sin(a); blade[:, 2] = y * np.sin(a) + z * np.cos(a)
    p = np.r_[blade, grip, guard]
    if bow:                                                       # true arc bend in depth, cross-sections stay rigid
        radius = 1 / bow; a = p[:, 0] / radius; r = radius - p[:, 2]
        p = np.column_stack([r * np.sin(a), p[:, 1], radius - r * np.cos(a)])
    return p


class StraightnessTests(unittest.TestCase):
    def test_straight_weapon_passes(self):
        m = s.measure(sword()); a = s.assess(m)
        self.assertTrue(a['straight'], a); self.assertLess(m['bendPctOfLength'], .5); self.assertLess(m['twistDegrees'], 3)
        self.assertLess(m['guardSkewDegrees'], 2)

    def test_bow_twist_and_skew_are_each_flagged(self):
        for kwargs, metric in (({'bow': .5}, 'bendPctOfLength'), ({'twist': 35}, 'twistDegrees'), ({'skew': 15}, 'guardSkewDegrees')):
            a = s.assess(s.measure(sword(**kwargs)))
            self.assertIn(metric, [f['metric'] for f in a['flags']], (kwargs, a))

    def test_straightening_removes_the_bow_and_keeps_sections(self):
        straight = sword(); bent = sword(bow=.5); mapping, history = s.fit_map(bent); out = s.apply_map(bent, mapping)
        self.assertGreater(history[0], 4); self.assertLess(s.measure(out)['bendPctOfLength'], .6)
        frame = lambda p: np.sort(np.ptp((p - p.mean(0)) @ s.principal_frame(p)[1], axis=0))[::-1]
        np.testing.assert_allclose(frame(out), frame(straight), rtol=.02, atol=.002)       # length, guard span and depth restored

    def test_saved_map_reapplies_identically_and_turns_normals(self):
        bent = sword(bow=.5); mapping, _ = s.fit_map(bent)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'map.npz'; s.save_map(path, mapping); loaded = s.load_map(path)
            with self.assertRaises(FileExistsError): s.save_map(path, mapping)
        np.testing.assert_array_equal(s.apply_map(bent, mapping), s.apply_map(bent, loaded))
        other = sword(bow=.5, seed=7)                                                    # another mesh in the same frame
        radius = 2.
        a = np.arctan2(other[:, 0], radius - other[:, 2]); normals = np.column_stack([-np.sin(a), np.zeros(len(a)), np.cos(a)])
        moved, turned = s.apply_map(other, loaded, normals)
        self.assertLess(s.measure(moved)['bendPctOfLength'], .8)
        depth = s.principal_frame(moved)[1][:, 2]; self.assertGreater(np.abs(turned @ depth).min(), .99)    # radial normals become parallel (within 8 degrees at the smoothed ends)

    def test_invalid_map_and_tiny_mesh_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '1000 vertices'): s.measure(np.zeros((10, 3)))
        mapping, _ = s.fit_map(sword())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'map.npz'; np.savez(path, **dict(mapping, tables=mapping['tables'][:, :10]))
            with self.assertRaisesRegex(ValueError, 'Invalid straightening map'): s.load_map(path)

    def test_long_weapons_need_a_reviewed_reference_view_before_geometry(self):
        from .generation import require_reference_view as check
        ok = {'view': 'oblique', 'decision': 'approved', 'notes': 'Angled pair reviewed.'}
        self.assertIsNone(check({'approval': {}}, 'dagger')); self.assertIsNone(check({}, 'firearm-sling'))
        self.assertEqual(check({'approval': {'referenceView': ok}}, 'longsword'), 'oblique')
        for family in s.LONG_FAMILIES:
            with self.assertRaisesRegex(ValueError, 'approval.referenceView'): check({'approval': {}}, family)
        for bad in (dict(ok, decision='pending'), dict(ok, notes=' '), dict(ok, view='front')):
            with self.assertRaisesRegex(ValueError, 'approval.referenceView'): check({'approval': {'referenceView': bad}}, 'staff')
        side = dict(ok, view='side')
        with self.assertRaisesRegex(ValueError, 'sideViewWaiver'): check({'approval': {'referenceView': side}}, 'greatsword')
        self.assertEqual(check({'approval': {'referenceView': dict(side, sideViewWaiver=True)}}, 'greatsword'), 'side')

    def test_glb_straightening_keeps_topology_uvs_and_source(self):
        rng = np.random.default_rng(1); bent = sword(bow=.5)[::8]; n = len(bent) // 3 * 3; bent = bent[:n]
        faces = np.arange(n).reshape(-1, 3); uv = rng.uniform(.1, .9, (len(faces), 3, 2))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder/'bent.glb'; write_mesh(source, bent, faces, uv); before = source.read_bytes()
            result = s.straighten(source, folder/'out'); after = mesh(folder/'out/straightened.glb'); original = mesh(source)
            self.assertEqual(source.read_bytes(), before); self.assertEqual(result['map']['mode'], 'measured')
            np.testing.assert_array_equal(after['faces'], original['faces']); np.testing.assert_array_equal(after['uv'], original['uv'])
            self.assertLess(result['after']['bendPctOfLength'], result['before']['bendPctOfLength'] / 4)
            again = s.straighten(source, folder/'again', folder/'out/straighten-map.npz')
            self.assertEqual(again['output']['sha256'], result['output']['sha256']); self.assertEqual(again['map']['mode'], 'applied')
            with self.assertRaises(FileExistsError): s.straighten(source, folder/'out')


if __name__ == '__main__':
    unittest.main()
