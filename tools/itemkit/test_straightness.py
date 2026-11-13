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


class EndCapNormalTests(unittest.TestCase):
    def test_squared_cap_normals_stay_perpendicular_through_the_fade(self):
        # A 22-degree cap tilt faded over 8 cm: the shear depends on x, so it also stretches along the length.
        ends = np.array([[0., 0., 0., np.tan(np.radians(22)), .1, .08, 0.]])
        rng = np.random.default_rng(1); grid = rng.uniform([-.1, -.03, -.02], [.1, .03, .02], (500, 3))
        for normal, tangents in ((np.array([0., 0., 1.]), ((1., 0, 0), (0, 1., 0))), (np.array([0., 1., 0.]), ((1., 0, 0), (0, 0, 1.)))):
            cap = lambda points: s._apply_ends(points, ends)
            moved, turned = cap(grid), s.turn_normals(cap, grid, np.tile(normal, (len(grid), 1)), .2)
            for t in tangents:                                         # the face through each point spanned by these two directions
                ahead = cap(grid + 1e-6 * np.asarray(t))
                along = (ahead - moved) / 1e-6; along /= np.linalg.norm(along, axis=1)[:, None]
                unit = turned / np.linalg.norm(turned, axis=1)[:, None]
                self.assertLess(np.abs((unit * along).sum(1)).max(), 1e-4)


class UnbendNormalTests(unittest.TestCase):
    def test_unbent_normals_stay_perpendicular_to_any_carried_face(self):
        mapping, _ = s.fit_map(sword(bow=.04)); rng = np.random.default_rng(2)
        points = sword(bow=.04)[::40]; normals = rng.normal(size=(len(points), 3)); normals /= np.linalg.norm(normals, axis=1)[:, None]
        moved, turned = s.apply_map(points, mapping, normals)
        for _ in range(2):                                             # two directions inside each point's own face
            t = np.cross(normals, rng.normal(size=(len(points), 3))); t /= np.linalg.norm(t, axis=1)[:, None]
            along = (s.apply_map(points + 1e-6 * t, mapping) - moved) / 1e-6; along /= np.linalg.norm(along, axis=1)[:, None]
            self.assertLess(np.abs((turned * along).sum(1)).max(), 1e-4)


class ThinNormalTests(unittest.TestCase):
    def test_thinned_normals_stay_perpendicular_through_the_ramp_and_a_sloped_mid_plane(self):
        centres = np.linspace(0, 1, s.SLICES); gain = np.clip(1.5 - centres * 2, .5, 1)       # ramps from 1 to 0.5
        mapping = {'mean': np.zeros(3), 'axes': np.eye(3), 'axis': np.array(2),
                   'table': np.column_stack([centres, .05 * centres, gain])}                 # mid-plane slopes along X
        x = np.linspace(.05, .95, 400); surface = lambda x: np.column_stack([x, np.zeros_like(x), .1 + .3 * x])   # a tilted face
        normals = np.tile(np.array([-.3, 0, 1]) / np.hypot(.3, 1), (len(x), 1))
        moved, turned = s.apply_thin(surface(x), mapping, normals); ahead = s.apply_thin(surface(x + 1e-6), mapping)
        along = (ahead - moved) / 1e-6; along /= np.linalg.norm(along, axis=1)[:, None]
        self.assertLess(np.abs((turned * along).sum(1)).max(), 1e-4)          # perpendicular to the moved surface
        self.assertTrue(np.allclose(turned[:, 1], 0))                           # the width direction is untouched


if __name__ == '__main__':
    unittest.main()


class ThickShaftTests(unittest.TestCase):
    def test_a_bent_thick_shaft_keeps_its_flat_end_caps(self):
        # A club: slices near the ends of a bent thick shaft cut the caps obliquely and must not hook the centreline.
        rng = np.random.default_rng(3); n = 60000; t = rng.uniform(-.5, .5, n); a = rng.uniform(0, 2 * np.pi, n)
        side = np.column_stack([t, .06 * np.cos(a), .06 * np.sin(a)]); r = .06 * np.sqrt(rng.uniform(0, 1, n // 5)); b = a[:n // 5]
        caps = np.column_stack([np.where(rng.random(n // 5) < .5, -.5, .5), r * np.cos(b), r * np.sin(b)]); p = np.r_[side, caps]
        radius = 2.; ang = p[:, 0] / radius; rr = radius - p[:, 2]
        bent = np.column_stack([rr * np.sin(ang), p[:, 1], radius - rr * np.cos(ang)])
        mapping, history = s.fit_map(bent); out = s.apply_map(bent, mapping)
        self.assertGreater(history[0], 4); self.assertLess(s.measure(out)['bendPctOfLength'], 1)
        frame = lambda q: np.sort(np.ptp((q - q.mean(0)) @ s.principal_frame(q)[1], axis=0))[::-1]
        np.testing.assert_allclose(frame(out), [1, .12, .12], rtol=.08)       # caps stay square (the old hook measured 17%)

    def test_whole_straightening_lines_a_cocked_head_up_with_its_haft(self):
        # A mace: thin haft, a head three times wider tilted 3 degrees at the collar. The default bridges the wide head.
        rng = np.random.default_rng(8); n = 60000; a = rng.uniform(0, 2 * np.pi, 2 * n)
        haft = np.column_stack([rng.uniform(-.4, .3, n), .02 * np.cos(a[:n]), .02 * np.sin(a[:n])])
        head = np.column_stack([rng.uniform(.3, .55, n), .065 * np.cos(a[n:]), .065 * np.sin(a[n:])])
        tilt = np.radians(3); x, z = head[:, 0] - .3, head[:, 2].copy()
        head[:, 0] = .3 + x * np.cos(tilt) - z * np.sin(tilt); head[:, 2] = x * np.sin(tilt) + z * np.cos(tilt)
        p = np.r_[haft, head]; far, near = slice(n, None), slice(0, n)
        def head_tilt(q):                               # head axis against the haft axis, degrees
            axis = lambda rows: np.linalg.eigh(np.cov((rows - rows.mean(0)).T))[1][:, -1]
            return np.degrees(np.arccos(min(1., abs(axis(q[far]) @ axis(q[near])))))
        self.assertGreater(head_tilt(s.apply_map(p, s.fit_map(p)[0])), 2.5)
        mapping, _ = s.fit_map(p, whole=True); out = s.apply_map(p, mapping)
        self.assertLess(head_tilt(out), .6)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'map.npz'; s.save_map(path, mapping)
            np.testing.assert_array_equal(s.apply_map(p, s.load_map(path)), out)        # the choice travels in the map
            with self.assertRaisesRegex(ValueError, 'whole'): s.straighten(Path(folder)/'none.glb', Path(folder)/'out', path, whole=True)

    def test_a_tilted_flat_cap_is_squared_and_a_point_is_left_alone(self):
        rng = np.random.default_rng(5); n = 80000; a = rng.uniform(0, 2 * np.pi, n); r = .06 * np.sqrt(rng.uniform(0, 1, n))
        y, z = r * np.cos(a), r * np.sin(a); t = rng.uniform(-.5, .5, n)
        side = np.column_stack([t, .06 * np.cos(a), .06 * np.sin(a)]); slant = np.tan(np.radians(15))
        low = np.column_stack([np.full(n // 4, -.5), y[:n // 4], z[:n // 4]]); high = np.column_stack([.5 + slant * y[:n // 4], y[:n // 4], z[:n // 4]])
        side = side[side[:, 0] < .5 + slant * side[:, 1]]; p = np.r_[side, low, high]
        mapping, _ = s.fit_map(p); self.assertEqual(len(mapping['ends']), 1)          # only the slanted cap is corrected
        out, normals = s.apply_map(p, mapping, np.tile([1., 0, 0], (len(p), 1))); q = (out - out.mean(0)) @ s.principal_frame(out)[1]
        cap = q[q[:, 0] > q[:, 0].max() - .004] if np.ptp(q[q[:, 0] > q[:, 0].max() - .004, 1]) > .1 else q[q[:, 0] < q[:, 0].min() + .004]
        self.assertGreater(np.ptp(cap[:, 1]), .11); self.assertLess(np.ptp(cap[:, 0]), .004)       # the whole cap now lies in one plane
        self.assertTrue(np.allclose(np.linalg.norm(normals, axis=1), 1))
        self.assertEqual(len(s.fit_map(sword())[0]['ends']), 0)                        # blade point and pommel are not flat caps
