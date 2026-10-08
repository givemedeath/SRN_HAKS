"""Analytic radial descendant maps and fail-closed analytic representation contract tests."""
import hashlib, json, tempfile, unittest
from pathlib import Path
import numpy as np
import analytic_radial_maps as maps
import diagnostic_analytic_representation as ar
from diagnostic_descendant_representation import RepresentationError

KIND = 'analytic-chest-waist-cap-rounding-v1'
Q = maps.ADOPTED[KIND][0]


def ring_points(n=24):
    th = np.linspace(-np.pi, np.pi, n, endpoint=False); z = np.linspace(-0.07, 0.06, 14); r = np.linspace(0.02, 0.16, 8)
    T, Z, R = np.meshgrid(th, z, r, indexing='ij')
    return np.stack((R * np.sin(T), R * np.cos(T), Z), axis=-1).reshape(-1, 3)


class ChestWaistCapMapTests(unittest.TestCase):
    def test_identity_above_z0_and_on_front_meridian(self):
        p = ring_points(); out = maps.apply(KIND, p, Q)
        above = p[:, 2] >= Q['z0']; front = np.isclose(np.arctan2(p[:, 0], p[:, 1]), 0) & (p[:, 1] > 0)
        np.testing.assert_array_equal(out[above], p[above]); np.testing.assert_allclose(out[front], p[front], atol=1e-15)

    def test_heights_and_axis_fixed_and_only_inward(self):
        p = ring_points(); out = maps.apply(KIND, p, Q)
        np.testing.assert_array_equal(out[:, 2], p[:, 2])
        self.assertTrue(np.all(np.hypot(out[:, 0], out[:, 1]) <= np.hypot(p[:, 0], p[:, 1]) + 1e-15))
        np.testing.assert_array_equal(maps.apply(KIND, np.array([[0.0, 0.0, -0.05]]), Q), [[0.0, 0.0, -0.05]])

    def test_fold_free_radial_profile(self):
        r = np.linspace(0.0, 0.3, 3001); p = np.stack((np.zeros_like(r), -r, np.full_like(r, -0.07)), axis=-1)   # back, full weight
        self.assertTrue(np.all(np.diff(-maps.apply(KIND, p, Q)[:, 1]) > 0))

    def test_normals_unit_length_and_tangents_orthogonal(self):
        p = ring_points()[::7]; n = np.tile([0.3, -0.8, 0.2], (len(p), 1)); n /= np.linalg.norm(n, axis=1)[:, None]
        nn = maps.transform_normals(KIND, p, n, Q); np.testing.assert_allclose(np.linalg.norm(nn, axis=1), 1, atol=1e-12)
        t = np.c_[np.tile([1.0, 0.0, 0.0], (len(p), 1)), np.where(np.arange(len(p)) % 2, 1.0, -1.0)]
        tn = maps.transform_tangents(KIND, p, t, nn, Q); moved = ~maps._identity(maps.jacobian(KIND, p, Q))
        self.assertTrue(moved.any() and (~moved).any())
        np.testing.assert_allclose(np.sum(tn[moved, :3] * nn[moved], axis=1), 0, atol=1e-12); np.testing.assert_array_equal(tn[:, 3], t[:, 3])
        np.testing.assert_array_equal(tn[~moved], t[~moved]); np.testing.assert_array_equal(nn[~moved], n[~moved])

    def test_identity_jacobian_preserves_normals_outside_support(self):
        p = np.array([[0.05, -0.1, 0.05]]); n = np.array([[0.0, -1.0, 0.0]])
        np.testing.assert_allclose(maps.transform_normals(KIND, p, n, Q), n, atol=1e-9)


class ThighUpperBackSlimMapTests(unittest.TestCase):
    K = 'analytic-thigh-upper-back-slim-top-dome-v1'

    def test_visible_lower_thigh_and_front_unchanged(self):
        q = maps.ADOPTED[self.K][0]; p = ring_points(); p[:, 2] -= 0.1          # z in [-0.17, -0.04]
        out = maps.apply(self.K, p, q); low = p[:, 2] <= q['z0']; front = p[:, 1] > -q['c0'] * np.hypot(p[:, 0], p[:, 1])          # outside the back-cosine support
        np.testing.assert_array_equal(out[low], p[low]); np.testing.assert_array_equal(out[front & (p[:, 2] <= q['zc'])], p[front & (p[:, 2] <= q['zc'])])

    def test_only_slims_and_lowers(self):
        q = maps.ADOPTED[self.K][0]; p = ring_points(); out = maps.apply(self.K, p, q)
        self.assertTrue(np.all(np.hypot(out[:, 0], out[:, 1]) <= np.hypot(p[:, 0], p[:, 1]) + 1e-15) and np.all(out[:, 2] <= p[:, 2]))
        self.assertLessEqual(float(np.max(p[:, 2] - out[:, 2])), q['topCut'] + 1e-15)

    def test_shape_preserved_for_corner_arrays(self):
        q = maps.ADOPTED[self.K][0]; p = ring_points()[:30].reshape(10, 3, 3)
        np.testing.assert_array_equal(maps.apply(self.K, p, q), maps.apply(self.K, p.reshape(-1, 3), q).reshape(10, 3, 3))


class AnalyticContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target = {'id': 't', 'rig': {'mode': 'stock-exact', 'runtimeScale': 1}}
        self.tp = self.root / 'target.json'; self.tp.write_text(json.dumps(self.target))
        self.contract = {'kind': ar.KIND, 'schemaVersion': 1, 'target': self.pin(self.tp), 'part': 'chest', 'space': 'working', 'parentRepresentation': self.pin(self.tp),
                         'operation': {'kind': KIND, 'parameters': dict(Q)}, 'final': {'candidate': self.pin(self.tp), 'geometry': self.pin(self.tp), 'nativeCorners': self.pin(self.tp)},
                         'consumers': [], 'physicalInputs': []}

    def tearDown(self):
        self.tmp.cleanup()

    def pin(self, p):
        return {'path': str(Path(p).resolve()), 'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()}

    def rejected(self, mutate, part='chest', message=None):
        c = json.loads(json.dumps(self.contract)); mutate(c); p = self.root / 'contract.json'; p.write_text(json.dumps(c))
        with self.assertRaises(RepresentationError) as caught:
            ar.prepare_analytic_representation(self.pin(p), target_path=self.tp, target=self.target, part=part)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_unknown_kind(self): self.rejected(lambda c: c.update(kind='diagnostic-descendant-representation'), message='Unknown analytic contract')
    def test_schema_version_bool(self): self.rejected(lambda c: c.update(schemaVersion=True), message='Unknown analytic contract')
    def test_extra_approval_field(self): self.rejected(lambda c: c.update(approval=True), message='Unexpected schema keys')
    def test_cross_owner(self): self.rejected(lambda c: None, part='pelvis', message='Cross owner/space')
    def test_runtime_space(self): self.rejected(lambda c: c.update(space='runtime'), message='Cross owner/space')
    def test_unknown_operator(self): self.rejected(lambda c: c['operation'].update(kind='analytic-free-form'), message='Unsupported analytic operator')
    def test_operator_wrong_part(self): self.rejected(lambda c: c.update(part='legl'), part='legl', message='Unsupported analytic operator')
    def test_unadopted_parameters(self): self.rejected(lambda c: c['operation']['parameters'].update(depth=0.1), message='user-adopted')
    def test_missing_parameter(self): self.rejected(lambda c: c['operation']['parameters'].pop('c'), message='user-adopted')
    def test_consumer_whitelist(self): self.rejected(lambda c: None, message='consumer whitelist')

    def test_stale_target_pin(self):
        c = self.contract; p = self.root / 'contract.json'; p.write_text(json.dumps(c)); self.tp.write_text('{"changed":1}')
        with self.assertRaises(RepresentationError):
            ar.prepare_analytic_representation(self.pin(p), target_path=self.tp, target=self.target, part='chest')


if __name__ == '__main__':
    unittest.main()
