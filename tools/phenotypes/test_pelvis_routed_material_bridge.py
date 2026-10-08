"""Portable typed pelvis routing/calibration guards and current-bridge dispatch; no actual assets."""
import hashlib, json, tempfile, unittest
from pathlib import Path
import numpy as np
import pelvis_routed_material_bridge as pm
import current_skin_calibration_bridge as current
import replay_stage_skin_calibration as cal
import audit_target_native_part as audit
from target_part_stage import validate_material_slots, material_resref
from target_body_inventory import expected_body_resources, skin_atlas_keys


def routing():
    doc = np.array([0, 0, 0, 1, 1, 2, 3, 0], np.int64); brief = np.array([0, 1, 0, 0, 0, 0, 0, 1], bool)
    return doc, np.where(brief, 4, doc), brief


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.p = Path(self.tmp.name) / 'x.json'; self.p.write_text('{}')
        row = {'path': str(self.p), 'sha256': hashlib.sha256(self.p.read_bytes()).hexdigest()}
        self.value = {'mode': pm.MODE, 'recipe': row, 'materialSlots': row}

    def test_exact_controls_and_dispatch(self):
        pm.controls(self.value); current.controls(self.value); self.assertEqual(current.PELVIS_MODE, pm.MODE)

    def test_extra_control_rejected_through_current_bridge(self):
        self.value['materialExecution'] = None
        with self.assertRaisesRegex(ValueError, 'Exact pelvis routed'): current.controls(self.value)

    def test_wrong_mode_falls_back_to_original_contract(self):
        self.value['mode'] = 'pelvis'
        with self.assertRaisesRegex(ValueError, 'Exact current calibration'): current.controls(self.value)

    def test_stale_pin_rejected(self):
        self.p.write_text('changed')
        with self.assertRaises(ValueError): pm.controls(self.value)

    def test_unsealed_native_geometry_rejected_through_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'Sealed current native'):
            current.staging_inputs(self.value, self.p, {}, 'pelvis', 'working', self.p, self.p, native_geometry=object())

    def test_original_bridge_still_rejects_pelvis(self):
        value = {'mode': current.MODE, 'recipe': self.value['recipe'], 'materialExecution': {'proof': self.value['recipe'], 'representation': self.value['recipe'], 'parentScope': self.value['recipe']}, 'faceRoleLineage': None}
        with self.assertRaisesRegex(ValueError, 'Sealed current native'):
            current.staging_inputs(value, self.p, {}, 'pelvis', 'working', self.p, self.p, native_geometry=object())

    def test_audit_replays_pelvis_adapter(self):
        self.assertEqual(audit.CURRENT_MATERIAL_ADAPTERS[pm.KIND], ('replayed-current-recipient-source-bound-skin-calibration-inputs', 'current_skin_calibration_bridge', 'currentMaterialInputs'))


class RoutingTests(unittest.TestCase):
    def test_valid_routing(self):
        doc, comp, brief = routing(); np.testing.assert_array_equal(pm.compiler_ids(doc, comp, brief, 2), comp)

    def test_brief_not_slot_four(self):
        doc, comp, brief = routing(); comp[1] = 0
        with self.assertRaisesRegex(ValueError, 'Compiler routing'): pm.compiler_ids(doc, comp, brief, 2)

    def test_brief_on_patch_document_material(self):
        doc, comp, brief = routing(); doc[2] = comp[2] = 2; brief[5] = True; comp[5] = 4
        with self.assertRaisesRegex(ValueError, 'another document material'): pm.compiler_ids(doc, comp, brief, 3)

    def test_brief_count_differs(self):
        doc, comp, brief = routing()
        with self.assertRaisesRegex(ValueError, 'Compiler routing'): pm.compiler_ids(doc, comp, brief, 10356)

    def test_missing_slot(self):
        doc, comp, brief = routing(); doc[6] = 2; comp[6] = 2
        with self.assertRaisesRegex(ValueError, 'Compiler routing'): pm.compiler_ids(doc, comp, brief, 2)

    def test_untyped_arrays(self):
        doc, comp, brief = routing()
        with self.assertRaisesRegex(ValueError, 'typed face routing'): pm.compiler_ids(doc.astype(float), comp, brief, 2)
        with self.assertRaisesRegex(ValueError, 'typed face routing'): pm.compiler_ids(doc, comp, brief.astype(int), 2)

    def test_typed_slots_match_stage_and_inventory(self):
        typed = pm.typed_slots(); validate_material_slots(typed); self.assertEqual(skin_atlas_keys(typed), ['skin1', 'skin2'])
        self.assertEqual({material_resref('pfh0_pelvis001', k, 'skin') for k in ('skin1', 'skin2')}, {'pfh0_pelviss1', 'pfh0_pelviss2'})
        target = {'models': {'pelvis': 'pfh0_pelvis001'}, 'material': {'fixedGarmentParts': ['pelvis']}, 'rig': {'mode': 'stock-exact'}}
        # The routed HIGH stage still names its typed per-atlas resources, but the single-PLT-per-part body contract
        # no longer accepts them: the part owns exactly its model-named .mdl/.mtr/.plt/n.tga/r.tga.
        with self.assertRaisesRegex(ValueError, 'superseded by the single-PLT'):
            expected_body_resources(target, {'pelvis'}, {'pelvis'}, {'pelvis': skin_atlas_keys(typed)})
        names = expected_body_resources(target, {'pelvis'}, {'pelvis'})
        self.assertEqual(names, {'pfh0_pelvis001' + s for s in ('.mdl', '.mtr', '.plt', 'n.tga', 'r.tga')})


class CalibrationTests(unittest.TestCase):
    def rows(self):
        rng = np.random.default_rng(1); base = rng.integers(0, 256, (8, 8), dtype=np.uint8); out = {}
        for k in pm.SKIN_ATLASES + ('garment',):
            out[k] = {'color': rng.integers(0, 256, (8, 8, 3), dtype=np.uint8), 'normal': np.full((8, 8, 3), 128, np.uint8), 'roughness': np.full((8, 8), 200, np.uint8), 'intensity': base.copy()}
        return out

    def test_one_shared_calibration(self):
        rows = self.rows(); ao = {k: np.full((8, 8), 255, np.uint8) for k in pm.SKIN_ATLASES}
        out, stats = pm.calibrated_rows(rows, 1.0, -16.39122219823203, ao)
        expected = np.floor(np.clip(rows['skin']['intensity'].astype(float) - 16.39122219823203, 0, 255)).astype(np.uint8)
        for k in pm.SKIN_ATLASES:
            np.testing.assert_array_equal(out[k]['intensity'], expected)
        np.testing.assert_array_equal(out['garment']['intensity'], rows['garment']['intensity'])
        self.assertEqual(len({stats[k]['calibratedAO0IntensitySha256'] for k in pm.SKIN_ATLASES}), 1)

    def test_nonzero_ao_and_bounds_rejected(self):
        rows = self.rows(); ao = {k: np.full((8, 8), 255, np.uint8) for k in pm.SKIN_ATLASES}
        with self.assertRaisesRegex(ValueError, 'AO0'): pm.calibrated_rows(rows, 1.0, 0.0, ao, ao_strength=.15)
        with self.assertRaisesRegex(ValueError, 'offset'): pm.calibrated_rows(rows, 1.0, -200.0, ao)
        del rows['skin2']
        with self.assertRaisesRegex(ValueError, 'Complete pelvis'): pm.calibrated_rows(rows, 1.0, 0.0, ao)


class SeamTests(unittest.TestCase):
    def test_shared_edge_samples_and_palette_report(self):
        P = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[1, 0, 0], [0, 1, 0], [1, 1, 0]]], float)
        uv = np.array([[[.1, .1], [.4, .1], [.1, .4]], [[.6, .1], [.6, .4], [.9, .4]]])
        s = pm.seam_samples(P, uv, np.array(['skin', 'skin1']), [('skin1', 'skin')])
        ua, ub = s[('skin1', 'skin')]; self.assertEqual(len(ua), 5)
        np.testing.assert_allclose(ua[0], uv[1, 0] * .9 + uv[1, 1] * .1); np.testing.assert_allclose(ub[0], uv[0, 1] * .9 + uv[0, 2] * .1)
        flat = {k: np.full((16, 16), 90, np.uint8) for k in ('skin', 'skin1')}; palette = np.tile(np.arange(256, dtype=np.uint8)[None, :, None], (9, 1, 3))
        rep = pm.palette_seam_report(s, flat, palette)['skin1|skin']; self.assertAlmostEqual(rep['palettes']['3']['maxAbsRGB'], 0.0, places=9)
        flat['skin1'][:] = 100; rep = pm.palette_seam_report(s, flat, palette)['skin1|skin']
        self.assertAlmostEqual(rep['signedIntensityMeanBytes'], 10.0); self.assertAlmostEqual(rep['palettes']['8']['meanAbsRGB'], 10.0)

    def test_same_atlas_keeps_only_uv_seams(self):
        P = np.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[1, 0, 0], [0, 1, 0], [1, 1, 0]]], float)
        uv = np.array([[[.1, .1], [.4, .1], [.1, .4]], [[.4, .1], [.1, .4], [.4, .4]]])
        self.assertEqual(len(pm.seam_samples(P, uv, np.array(['skin', 'skin']), [('skin', 'skin')])[('skin', 'skin')][0]), 0)

    def test_bilinear_texel_centres(self):
        a = np.arange(16, dtype=np.uint8).reshape(4, 4); uv = np.array([[.125, .125], [.375, .625]])
        np.testing.assert_allclose(pm.bilinear(a, uv)[:, 0], [0, 9])


if __name__ == '__main__':
    unittest.main()
