"""Independent runtime authority, exact ASCII ownership and native/material proof."""
import copy
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

import stage_target_working_leaves as stage
import audit_target_working_leaves_native as audit
from test_stage_target_working_leaves import corner_archive, cap_fixture, cap_policy
from test_audit_target_native_part import fixture as native_fixture
from test_target_part_pipeline import target_fixture


class WorkingLeafNativeAuditTests(unittest.TestCase):
    def test_independent_archive_rejects_double_scale_history_or_basis_change(self):
        original = corner_archive()
        current = stage.runtime_archive(original, 'positions', 'normals', 'tangents')
        keys = {'P': 'positions', 'N': 'normals', 'T': 'tangents'}
        self.assertTrue(audit.independent_archive(original, current, keys)['positionScaleExactlyOnce'])
        for defect in ('scale', 'history', 'tangent', 'working', 'extra'):
            child = copy.deepcopy(current)
            if defect == 'scale': child['positions'] *= 10 / 7
            if defect == 'history': child['sourcePositions'] *= 10 / 7
            if defect == 'tangent': child['tangents'][0, 0, 2] = 0
            if defect == 'working': child['runtimeWorkingPositions'] *= 2
            if defect == 'extra': child['another'] = np.asarray([1])
            with self.subTest(defect=defect), self.assertRaises(ValueError): audit.independent_archive(original, child, keys)

    def test_ascii_ordered_source_f64_and_role_mapping_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = corner_archive()
            source = {'position': a['positions'], 'normal': a['normals'], 'uv': a['uvNative'], 'primitiveIds': a['primitiveIds']}
            path = Path(tmp) / 'source.mdl'
            meshes = stage.write_model(path, 'pmg0_shinl001', source, np.asarray(['skin']))
            rows = audit.ascii_meshes(path.read_text(), 'pmg0_shinl001', meshes, source, {0: 'skin'})
            np.testing.assert_array_equal(next(iter(rows.values()))['corners']['position'], a['positions'])
            for defect in ('mapping', 'implicitScale', 'sourceRoundoff', 'role'):
                text, mapping, expected, roles = path.read_text(), copy.deepcopy(meshes), copy.deepcopy(source), {0: 'skin'}
                if defect == 'mapping': next(iter(mapping.values()))['mergedCornerRows'] = [1]
                if defect == 'implicitScale': text = text.replace('  position 0 0 0', '  position 0 0 0\n  scale 1.4')
                if defect == 'sourceRoundoff': expected['position'] = expected['position'].astype('f4').astype(float)
                if defect == 'role': roles[0] = 'garment'
                with self.subTest(defect=defect), self.assertRaises(ValueError): audit.ascii_meshes(text, 'pmg0_shinl001', mapping, expected, roles)

    def test_decoder_is_strict_and_source_tangent_measurement_does_not_claim_preservation(self):
        data, model, names, offsets, raw = native_fixture(('skin',))
        meshes, _ = audit.decode(data, model, names)
        native = meshes[names[0]]
        source = {'tangents': np.tile([1.2, 0., .17, -1.], (1, 3, 1))}
        proof = audit.source_tangent_comparison(source, native)
        self.assertTrue(proof['nativeCompilerReconstructsTangents'])
        self.assertFalse(proof['sourceAuthoredTangentPreservationClaim'])
        self.assertFalse(proof['nativeTangentVisualAccepted'])
        self.assertEqual(proof['sameVFlippedSignCorners'], 3)
        self.assertNotEqual(proof['maximumTangentComponentDifference'], 0)
        invalid = data.copy()
        struct.pack_into('<I', invalid, 12 + offsets[0] + 0x6c, 97)
        with self.assertRaises(ValueError): audit.decode(invalid, model, names)

    def test_actual_native_f32_cast_is_not_accepted_as_f64_ascii(self):
        a = corner_archive()
        source = {'position': a['positions'], 'normal': a['normals'], 'uv': a['uvNative']}
        encoded = {k: v.astype('f4') for k, v in source.items()}
        # ASCII is exact f64, binary is its declared float32 cast.
        _, _, exact = audit.validate_transport(source, source, encoded, 0)
        self.assertTrue(all(exact.values()))
        with self.assertRaises(ValueError): audit.validate_transport(source, encoded, encoded, 0)
        bad = copy.deepcopy(encoded)
        bad['position'][0, 0, 0] = np.nextafter(bad['position'][0, 0, 0], np.float32(np.inf))
        with self.assertRaises(ValueError): audit.validate_transport(source, source, bad, 0)

    def test_cap_native_material_is_independently_decoded_and_missing_normal_is_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d, b, _, _ = cap_fixture()
            pixels, proof = stage.cap_pixels(d, b, 0, cap_policy(root), {})
            stage.write_materials(root, 'pmg0_pelvis001', {stage.CAP_ROLE: pixels})
            hashes = {n: stage.tc.sha(root / n) for n in stage.expected_resources('pmg0_pelvis001', {stage.CAP_ROLE})}
            result = audit.material_audit(root, 'pmg0_pelvis001', {stage.CAP_ROLE: pixels}, [proof], hashes)
            self.assertTrue(result[stage.CAP_ROLE]['normalMapAbsent'])
            self.assertFalse(result[stage.CAP_ROLE]['clientFilteringPaletteAndNormalAbsenceAccepted'])
            file = root / 'pmg0_pelvis001c.plt'
            data = bytearray(file.read_bytes())
            data[24] ^= 1
            file.write_bytes(data)
            with self.assertRaises(ValueError): audit.material_audit(root, 'pmg0_pelvis001', {stage.CAP_ROLE: pixels}, [proof], hashes)

    def test_audit_config_refuses_old_kind_wrong_space_unpinned_client_or_global_tolerance(self):
        c = {'schemaVersion': 1, 'kind': audit.CONFIG_KIND, 'part': 'shinl', 'diagnosticOnly': True,
             'coordinateSpace': 'runtime', 'nativeUvMaximumUlps': 0, 'expectedClientSha256': audit.CLIENT_SHA}
        audit.validate_config(c)
        for key, value in [('kind', 'target-native-part-audit'), ('coordinateSpace', 'working'),
                           ('nativeUvMaximumUlps', 2), ('nativeUvMaximumUlps', False),
                           ('expectedClientSha256', '0' * 64), ('clientAccepted', True)]:
            bad = copy.deepcopy(c)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): audit.validate_config(bad)

    def test_composition_owner_and_exact_source_config_are_verified(self):
        item = {'path': '/test-stage.json', 'sha256': 'a' * 64}
        config = {'schemaVersion': 1, 'kind': 'target-working-leaf-runtime-composition-config',
                  'coordinateSpace': 'runtime', 'diagnosticOnly': True, 'declaredParts': ['shinl'], 'stageReceipts': [item]}
        comp = {'parts': {'shinl': 'pmg0_shinl001.mdl'}, 'modelParts': {'pmg0_shinl001.mdl': 'shinl'},
                'completeBodyInventoryPresent': False, 'provisionalHeadNeckRigEquipmentOwnedHere': False,
                'sourceStages': [{'part': 'shinl', 'receipt': item}]}
        audit.composition_association(comp, config, target_fixture())
        for defect in ('wrongModel', 'missingStage', 'head', 'completePromotion', 'changedPin'):
            c, r = copy.deepcopy(config), copy.deepcopy(comp)
            if defect == 'wrongModel': r['parts']['shinl'] = 'pmh0_shinl001.mdl'
            if defect == 'missingStage': r['sourceStages'] = []
            if defect == 'head': c['declaredParts'] = ['head']
            if defect == 'completePromotion': r['completeBodyInventoryPresent'] = True
            if defect == 'changedPin': c['stageReceipts'][0]['sha256'] = 'b' * 64
            with self.subTest(defect=defect), self.assertRaises(ValueError): audit.composition_association(r, c, target_fixture())


if __name__ == '__main__':
    unittest.main()
