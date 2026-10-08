"""Gate 3 fix-pass audit rules: current-material branch routing and the exact float32 tie transport rule."""
import tempfile, unittest
from pathlib import Path
from unittest import mock
import numpy as np
import audit_target_native_part as audit
import current_skin_calibration_bridge as current

CURRENT = 'separately-verified-current-geometry-and-original-calibration-material-inputs'
BASIS = 'replayed-current-recipient-source-bound-skin-calibration-inputs'


class CurrentMaterialBranchTests(unittest.TestCase):
    def run_stage(self, kind, extra=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name); (root / 'stage' / 'ascii').mkdir(parents=True)
        np.savez(root / 'stage' / 'compiler-material-face-ownership.npz', materialIds=np.zeros(2, np.int64))
        derived = {'kind': kind}; slots = {'0': {'role': 'skin', 'atlasKey': 'skin'}}
        stage = {'materialRoles': {'0': 'skin'}, 'derivedMaterialProof': derived, 'materialInputBasis': BASIS, 'currentMaterialInputs': {}, 'nativeGeometryInputs': {},
                 'aoStrength': 0, 'asciiModel': str(root / 'stage' / 'ascii' / 'm.mdl'), 'materialSlots': slots, **(extra or {})}
        arrays = {'positions': np.zeros((2, 3, 3)), 'normals': np.zeros((2, 3, 3)), 'uvNative': np.zeros((2, 3, 2))}
        replay = {'proof': derived, 'materialRoles': {0: 'skin'}, 'materialSlots': slots, 'compilerMaterialIds': np.zeros(2, np.int64), 'document': None, 'binary': None,
                  'materialRows': {}, 'originalMaterialProof': [], 'auditFiles': []}
        with mock.patch.object(audit, 'replay_native_geometry', return_value=(object(), arrays)), mock.patch.object(current, 'staging_inputs', return_value=replay), \
                mock.patch.object(audit, 'raw_corners', return_value=(None, None, None, [])):
            return audit.audit_source_inputs(stage, None, None, None, {'rig': {'mode': 'other'}}, 'legl', 'working')

    def test_current_material_stage_does_not_fall_into_reviewed_branch(self):
        for kind in (CURRENT, 'separately-verified-current-geometry-and-skin-intensity-descendant-material-inputs'):
            result = self.run_stage(kind); self.assertEqual(result['materialInputBasis'], BASIS)
            np.testing.assert_array_equal(result['compilerMaterialIds'], np.zeros(2))

    def test_material_execution_without_source_bound_audit_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Material execution requires source-bound calibration audit'):
            audit.audit_source_inputs({'materialRoles': {'0': 'skin'}, 'derivedMaterialProof': {'kind': 'other'}, 'materialExecutionInputs': {}}, None, None, None, None, 'legl', 'working')


class Float32TieTests(unittest.TestCase):
    def test_exact_ties_resolve_to_either_neighbour_only(self):
        a = np.float32(9.702472e-11); b = np.nextafter(a, np.float32(1)); mid = (np.float64(a) + np.float64(b)) / 2          # exact float32 midpoint
        source = np.array([mid, 0.25, mid]); reference = source.astype(np.float32)
        other = np.where(reference == a, b, a).astype(np.float32)
        native = np.array([other[0], np.float32(0.25), reference[2]], np.float32)
        out, n = audit.resolve_float32_ties(source, native); self.assertEqual(n, 1); np.testing.assert_array_equal(out, reference)

    def test_non_tie_difference_is_not_resolved(self):
        source = np.array([0.1, 1e-10]); native = source.astype(np.float32).copy(); native[1] = np.nextafter(native[1], np.float32(1))
        out, n = audit.resolve_float32_ties(source, native); self.assertEqual(n, 0); self.assertFalse(np.array_equal(out, source.astype(np.float32)))

    def test_two_ulp_step_at_a_tie_is_not_resolved(self):
        a = np.float32(1.0); b = np.nextafter(a, np.float32(2)); mid = (np.float64(a) + np.float64(b)) / 2
        native = np.array([np.nextafter(b, np.float32(2))], np.float32); out, n = audit.resolve_float32_ties(np.array([mid]), native); self.assertEqual(n, 0)


if __name__ == '__main__':
    unittest.main()
