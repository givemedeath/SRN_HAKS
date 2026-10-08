"""Skin intensity descendant bridge and derivation operator tests (synthetic; tamper cases fail closed)."""
import hashlib, json, tempfile, unittest
from pathlib import Path
from unittest import mock
import numpy as np
import skin_intensity_descendant_bridge as sib
import derive_skin_intensity_descendant as dsi

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
pin = lambda p: {'path': str(Path(p).resolve()), 'sha256': sha(p)}


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        rng = np.random.default_rng(3); self.parent = rng.integers(20, 200, (2048, 2048)).astype(np.uint8)
        self.delta = np.zeros((2048, 2048), np.int16); self.delta[100:300, 50:90] = 7; self.delta[900, 900] = -12
        self.receipt = self.write(self.delta)
        self.rows = {'skin': {'color': np.zeros((2, 2, 3), np.uint8), 'normal': np.ones((2, 2, 3), np.uint8), 'roughness': np.zeros((2, 2), np.uint8), 'intensity': self.parent}}
        self.parent_result = {'materialRows': self.rows, 'materialSlots': {'0': {'role': 'skin', 'atlasKey': 'skin'}}, 'proof': {'kind': 'parent'}, 'frozenInputs': {},
                              'document': None, 'binary': None}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, delta, name='d', part='legl', key='skin', **over):
        new = (self.parent.astype(np.int32) + delta).clip(0, 255).astype(np.uint8)
        dp = self.root / f'{name}.npz'; np.savez(dp, delta=delta, parentIntensitySha256=np.array(sib.fingerprint(self.parent)), intensitySha256=np.array(sib.fingerprint(new)))
        row = {'part': part, 'atlasKey': key, 'material': 'm', 'delta': pin(dp), 'parentIntensitySha256': sib.fingerprint(self.parent), 'intensitySha256': sib.fingerprint(new),
               'changedTexels': int((delta != 0).sum()), 'maxAbsDelta': int(np.abs(delta).max()), 'coveredChanged': 0, 'uncoveredChanged': 0}
        row.update(over)
        rec = {'schemaVersion': 1, 'kind': sib.RECEIPT_KIND, 'atlases': {name: row}, 'geometryUvNormalRoughnessGarmentEdited': False, 'selected': False, 'clientAccepted': False, 'productionAccepted': False}
        p = self.root / f'{name}-receipt.json'; p.write_text(json.dumps(rec)); return p

    def stage(self, receipt):
        import current_skin_calibration_bridge as current
        value = {'mode': sib.MODE, 'parent': {'mode': 'x'}, 'descendant': pin(receipt)}
        with mock.patch.object(current, 'controls'), mock.patch.object(current, 'staging_inputs', return_value=self.parent_result):
            return sib.staging_inputs(value, None, None, 'legl', 'working', None, None)

    def test_delta_applied_exactly_once_and_protected_pixels_kept(self):
        out = self.stage(self.receipt); new = out['materialRows']['skin']['intensity']
        np.testing.assert_array_equal(new.astype(np.int32) - self.parent, self.delta)
        self.assertEqual(out['proof']['kind'], sib.KIND); self.assertEqual(out['proof']['intensityDescendantApplications'], 1)
        for k in ('color', 'normal', 'roughness'):
            np.testing.assert_array_equal(out['materialRows']['skin'][k], self.rows['skin'][k])

    def test_wrong_parent_calibration_rejected(self):
        self.parent_result['materialRows'] = {'skin': {**self.rows['skin'], 'intensity': self.parent ^ 1}}
        with self.assertRaisesRegex(ValueError, 'different parent calibration'):
            self.stage(self.receipt)

    def test_byte_range_enforced(self):
        d = self.delta.copy(); d[0, 0] = 300
        with self.assertRaisesRegex(ValueError, 'byte range|differs from its receipt'):
            self.stage(self.write(d, 'big'))

    def test_declared_extent_enforced(self):
        with self.assertRaisesRegex(ValueError, 'Declared delta extent'):
            self.stage(self.write(self.delta, 'ext', changedTexels=1))

    def test_foreign_atlas_or_part_rejected(self):
        with self.assertRaisesRegex(ValueError, 'does not own'):
            self.stage(self.write(self.delta, 'k1', key='skin1'))
        with self.assertRaisesRegex(ValueError, 'One delta per declared atlas'):
            self.stage(self.write(self.delta, 'p2', part='shinl'))

    def test_accepted_receipt_rejected(self):
        p = self.receipt; rec = json.loads(p.read_text()); rec['clientAccepted'] = True; p.write_text(json.dumps(rec))
        with self.assertRaisesRegex(ValueError, 'unaccepted'):
            self.stage(p)

    def test_tampered_delta_bytes_rejected(self):
        rec = json.loads(self.receipt.read_text()); dp = Path(next(iter(rec['atlases'].values()))['delta']['path'])
        b = bytearray(dp.read_bytes()); b[len(b) // 2] ^= 0xFF; dp.write_bytes(bytes(b))
        with self.assertRaisesRegex(ValueError, 'Changed intensity descendant input'):
            self.stage(self.receipt)

    def test_nested_descendant_controls_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Nested'):
            sib.controls({'mode': sib.MODE, 'parent': {'mode': sib.MODE}, 'descendant': pin(self.receipt)})


class DerivationOperatorTests(unittest.TestCase):
    def mesh(self):
        m = dsi.Mesh.__new__(dsi.Mesh); m.uv = np.array([[0.1, 0.1], [0.4, 0.1], [0.1, 0.4]]); m.faces = np.array([[0, 1, 2]])
        m.ys, m.xs, m.tf, m.tb = dsi.raster(m.uv, m.faces); m.covered = np.zeros((2048, 2048), bool); m.covered[m.ys, m.xs] = True
        return m

    def test_raster_covers_triangle_with_valid_barycentrics(self):
        m = self.mesh(); self.assertGreater(m.covered.sum(), 0.4 * 0.5 * (0.3 * 2048) ** 2)
        np.testing.assert_allclose(m.tb.sum(1), 1); self.assertTrue(np.all(m.tb >= 0))

    def test_pad_only_writes_uncovered_texels(self):
        m = self.mesh(); I = np.zeros((2048, 2048)); I[m.covered] = 90; out, n = dsi.pad(m, I, 3)
        np.testing.assert_array_equal(out[m.covered], I[m.covered]); self.assertGreater(n, 0); self.assertTrue(np.all(out[(out != 0) & ~m.covered] == 90))

    def test_dark_lift_only_raises_outliers(self):
        m = self.mesh(); I = np.full((2048, 2048), 100.0); ys, xs = m.ys[::50], m.xs[::50]; I[ys, xs] = 20
        out = dsi.dark_lift(m, I, np.ones(3), 6, 6); self.assertTrue(np.all(out >= I - 1e-9)); self.assertGreater(out[ys, xs].min(), 80)

    def test_detail_attenuation_identity_at_alpha_one(self):
        m = self.mesh(); I = np.random.default_rng(0).random((2048, 2048)) * 100
        np.testing.assert_allclose(dsi.detail_attenuation(m, I, np.ones(3), 4, 1.0), I)

    def test_falloff_and_circular_fill(self):
        np.testing.assert_allclose(dsi.cosine_falloff([0, 0.03, 0.06, 0.1], 0.0, 0.06), [1, 0.5, 0, 0], atol=1e-12)
        np.testing.assert_allclose(dsi.fill_circular([np.nan, 2.0, np.nan, 4.0]), [3.0, 2.0, 3.0, 4.0])


if __name__ == '__main__':
    unittest.main()
