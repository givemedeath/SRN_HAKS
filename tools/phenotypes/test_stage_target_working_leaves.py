"""Once-only f64 runtime authority, strict leaf types and role/material tests."""
import copy
from io import BytesIO
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as tc
import stage_target_working_leaves as stage
from target_part_pipeline import execute
from place_purposebuilt_pelvis import write_glb
from test_target_part_pipeline import target_fixture
from test_target_part_stage import textured_fixture


def corner_archive():
    p = np.asarray([[[.123456789123, 0, 0], [1.123456789123, 0, 0], [.123456789123, 1, 0]]])
    n = np.tile([0., 0., 1.3], (1, 3, 1))
    # Deliberately authored nonorthogonality, nonunit tangent and negative W.
    t = np.tile([1.2, 0., .17, -1.], (1, 3, 1))
    return {'positions': p, 'normals': n, 'tangents': t,
            'uvNative': np.asarray([[[.1, .2], [.9, .2], [.1, .8]]]),
            'uvGltf': np.asarray([[[.1, .8], [.9, .8], [.1, .2]]]),
            'primitiveIds': np.asarray([0]), 'sourcePositions': p.copy(),
            'radialParentRawPositions': p.astype('f4'), 'sourceCornerOrder': np.asarray([[0, 2, 1]])}


def cap_policy(root):
    declaration = {'dimensions': [3, 3], 'resampling': 'none', 'pltLayer': 0,
                   'intensityPolicy': 'RGB-rec709-floor-byte', 'roughnessPolicy': 'ORM-green-times-factor-rounded-byte',
                   'normalMap': 'absent', 'addedAO': 0, 'texture0': 'omitted', 'sourceUVChanged': False,
                   'tiling': 'none', 'effectiveMetallicness': 0, 'specularity': .04, 'roughnessParameter': 0,
                   'nativeFilterPolicy': 'engine-default-unverified-client-gate'}
    path = root / 'native-cap-policy.json'
    path.write_text(json.dumps({'kind': 'root-reviewed-pelvis-cap-native-pixel-policy', 'reviewedBy': '/root',
                               'authorizeNativeDiagnosticStage': True, 'policy': declaration}), encoding='utf-8')
    return {'declaration': declaration, 'rootReview': stage.ref(path)}


def cap_fixture():
    color = np.zeros((3, 3, 4), dtype='u1')
    color[..., 3] = 255
    color[..., :3] = np.arange(27, dtype='u1').reshape(3, 3, 3) + 30
    orm = np.zeros((3, 3, 4), dtype='u1')
    orm[..., 0] = 255
    orm[..., 1] = np.arange(9, dtype='u1').reshape(3, 3) + 40
    orm[..., 3] = 255
    doc = {'bufferViews': [], 'images': [], 'textures': [], 'materials': []}
    blob = bytearray()
    for pixels in (color, orm):
        stream = BytesIO()
        Image.fromarray(pixels).save(stream, format='PNG')
        encoded = stream.getvalue()
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(blob), 'byteLength': len(encoded)})
        doc['images'].append({'bufferView': len(doc['bufferViews']) - 1})
        doc['textures'].append({'source': len(doc['images']) - 1})
        blob.extend(encoded)
    doc['materials'] = [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0},
                                                 'metallicRoughnessTexture': {'index': 1}}, 'alphaMode': 'OPAQUE'}]
    return doc, bytes(blob), color, orm


class WorkingLeafStageTests(unittest.TestCase):
    def test_once_only_scales_f64_current_positions_and_retains_all_other_bytes(self):
        original = corner_archive()
        result = stage.runtime_archive(original, 'positions', 'normals', 'tangents')
        np.testing.assert_array_equal(result['positions'], original['positions'] * (10 / 7))
        self.assertFalse(np.array_equal(result['positions'], original['positions'].astype('f4') * (10 / 7)))
        for key in original:
            if key != 'positions':
                self.assertEqual(result[key].dtype, original[key].dtype)
                self.assertEqual(result[key].tobytes(), original[key].tobytes())
        self.assertEqual(result['runtimeWorkingPositions'].tobytes(), original['positions'].tobytes())
        with self.assertRaisesRegex(ValueError, 'twice'):
            stage.runtime_archive(result, 'positions', 'normals', 'tangents')
        with self.assertRaises(ValueError):
            stage.runtime_archive(original, 'positions', 'normals', 'tangents', applications=1)

    def test_runtime_rejects_f32_current_basis_zero_normals_and_invalid_w(self):
        for defect in ('float32', 'zeroN', 'zeroT', 'badW', 'nonfinite'):
            a = corner_archive()
            if defect == 'float32': a['positions'] = a['positions'].astype('f4')
            if defect == 'zeroN': a['normals'][0, 0] = 0
            if defect == 'zeroT': a['tangents'][0, 0, :3] = 0
            if defect == 'badW': a['tangents'][0, 0, 3] = 0
            if defect == 'nonfinite': a['positions'][0, 0, 0] = np.nan
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                stage.runtime_archive(a, 'positions', 'normals', 'tangents')

    def test_no_diagnostic_alias_old_back20_neutral_cap_or_runtime_source(self):
        s, k, op, _ = stage.SOURCES['legl']
        receipt = {'schemaVersion': s, 'kind': k, 'operation': op, 'part': 'legl', 'joint': 'lthigh_g', 'statureApplications': 0}
        stage.validate_source_type(receipt, 'legl')
        for field, value in [('kind', 'target-part-geometry'), ('operation', 'symmetric-window'),
                             ('statureApplications', 1), ('part', 'legr'), ('clientAccepted', True)]:
            bad = copy.deepcopy(receipt)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                stage.validate_source_type(bad, 'legl')
        old = {'schemaVersion': 1, 'kind': 'target-part-diagnostic-pelvis-cuff-contour15',
               'operation': 'same-topology-world-XY-total15-cuff-contraction-from-pelvis35', 'part': 'pelvis',
               'joint': 'pelvis_g', 'statureApplications': 0}
        with self.assertRaises(ValueError): stage.validate_source_type(old, 'pelvis')

    def test_config_requires_troll_target_once_only_and_new_kind(self):
        c = {'schemaVersion': 1, 'kind': stage.CONFIG_KIND, 'diagnosticOnly': True, 'part': 'shinl',
             'coordinateSpaceFrom': 'working', 'coordinateSpaceTo': 'runtime',
             'runtimeScale': {'numerator': 10, 'denominator': 7}, 'statureApplicationsBefore': 0,
             'statureApplicationsAfter': 1, 'aoStrength': 0}
        target = target_fixture()
        stage.validate_config(c, target)
        for change in ('oldKind', 'wrongCount', 'workingOut', 'AO', 'Human', 'female'):
            config, t = copy.deepcopy(c), copy.deepcopy(target)
            if change == 'oldKind': config['kind'] = 'target-part-stage'
            if change == 'wrongCount': config['statureApplicationsBefore'] = 1
            if change == 'workingOut': config['coordinateSpaceTo'] = 'working'
            if change == 'AO': config['aoStrength'] = .15
            if change == 'Human': t['identity']['prefix'] = 'pmh0'
            if change == 'female': t['identity']['gender'] = 'female'
            with self.subTest(change=change), self.assertRaises(ValueError): stage.validate_config(config, t)

    def test_executor_path_and_hash_both_enforced(self):
        current = stage.ref(stage.__file__)
        stage.executor({'expectedExecutor': current}, {})
        for bad in ({'path': stage.__file__, 'sha256': '0' * 64}, stage.ref(__file__)):
            with self.assertRaises(ValueError): stage.executor({'expectedExecutor': bad}, {})

    def test_original_right_foot_is_not_reinterpreted_as120_mirror(self):
        receipt = {'sourcePart': 'footl', 'sourceReceiptSha256': 'a7d016161b0f040c33b1e3d8307dadf6d9470845f8580f023bc2ceda06061bd6'}
        parent = {'kind': 'target-part-geometry', 'operation': 'fit', 'part': 'footl', 'statureApplications': 0}
        stage.validate_original_right_foot(receipt, parent)
        for defect in ('parentUniform', 'runtime', 'otherOriginalPin'):
            r, p = copy.deepcopy(receipt), copy.deepcopy(parent)
            if defect == 'parentUniform': p['operation'] = 'uniform-scale-original-working-foot'
            if defect == 'runtime': p['statureApplications'] = 1
            if defect == 'otherOriginalPin': r['sourceReceiptSha256'] = '0' * 64
            with self.subTest(defect=defect), self.assertRaises(ValueError): stage.validate_original_right_foot(r, p)

    def test_same_kind_selection_without_exact_source_association_is_rejected(self):
        pin = {'path': str(Path('/selected/geometry.json').resolve()), 'sha256': 'a' * 64}
        stage.validate_selection_authority({'kind': 'review', 'actualReceipt': pin}, 'review', pin)
        stage.validate_selection_authority({'kind': 'review', 'receipt': pin['path'], 'receiptSha256': pin['sha256']}, 'review', pin)
        for bad in ({'kind': 'review'}, {'kind': 'review', 'actualReceipt': {'path': pin['path'], 'sha256': 'b' * 64}},
                    {'kind': 'review', 'receipt': '/other/geometry.json', 'receiptSha256': pin['sha256']}):
            with self.assertRaisesRegex(ValueError, 'exact source'): stage.validate_selection_authority(bad, 'review', pin)

    def test_role_merge_has_explicit_cap_and_body_provenance_and_no_lost_rows(self):
        slots = []
        for name, ids in [('body', [0, 3, 4, 5]), ('caps', [1, 2])]:
            a = corner_archive()
            arrays = {'position': np.repeat(a['positions'], len(ids), axis=0), 'normal': np.repeat(a['normals'], len(ids), axis=0),
                      'tangents': np.repeat(a['tangents'], len(ids), axis=0), 'uv': np.repeat(a['uvNative'], len(ids), axis=0)}
            slots.append({'slot': name, 'current': arrays, 'primitiveIds': np.asarray(ids)})
        primitives = [{'triangles': 1} for _ in range(6)]
        roles = {0: 'skin', 1: stage.CAP_ROLE, 2: stage.CAP_ROLE, 3: 'garment', 4: 'skin', 5: 'garment'}
        _, mapping, owners = stage.merge_corners(slots, primitives, roles, 'pelvis')
        np.testing.assert_array_equal(mapping['archiveSlotIds'], [0, 1, 1, 0, 0, 0])
        np.testing.assert_array_equal(mapping['archiveRowIds'], [0, 0, 1, 1, 2, 3])
        self.assertEqual(owners.tolist(), [roles[i] for i in range(6)])
        for defect in ('capRelabeled', 'wrongCount', 'otherOwner', 'lostRow'):
            s, p, r = copy.deepcopy(slots), copy.deepcopy(primitives), copy.deepcopy(roles)
            part = 'pelvis'
            if defect == 'capRelabeled': r[1] = 'skin'
            if defect == 'wrongCount': p[0]['triangles'] = 2
            if defect == 'otherOwner': part = 'chest'
            if defect == 'lostRow': s[0]['primitiveIds'][0] = 99
            with self.subTest(defect=defect), self.assertRaises(ValueError): stage.merge_corners(s, p, r, part)

    def test_cap_policy_is_required_and_exact_no_unreviewed_resampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = cap_policy(Path(tmp))
            stage.validate_cap_policy(p, {})
            for bad in (None, {'declaration': p['declaration']}, copy.deepcopy(p)):
                if isinstance(bad, dict) and 'rootReview' in bad: bad['declaration']['dimensions'] = [2048, 2048]
                with self.assertRaises(ValueError): stage.validate_cap_policy(bad, {})

    def test_cap_C3_pixels_PLT_roughness_and_absent_normal_texture0(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d, b, color, orm = cap_fixture()
            value, proof = stage.cap_pixels(d, b, 0, cap_policy(root), {})
            np.testing.assert_array_equal(value['roughness'], orm[..., 1])
            stage.write_materials(root, 'pmg0_pelvis001', {stage.CAP_ROLE: value})
            data = (root / 'pmg0_pelvis001c.plt').read_bytes()
            self.assertEqual(struct.unpack_from('<IIII', data, 8), (10, 0, 3, 3))
            decoded = np.frombuffer(data[24:], dtype='u1').reshape(3, 3, 2)[::-1]
            expected = (color[..., :3].astype(float) @ [.2126, .7152, .0722]).astype('u1')
            np.testing.assert_array_equal(decoded[..., 0], expected)
            self.assertFalse(decoded[..., 1].any())
            mtr = (root / 'pmg0_pelvis001c.mtr').read_text()
            self.assertNotIn('texture0', mtr)
            self.assertNotIn('texture1', mtr)
            self.assertIn('Metallicness 0\n', mtr)
            self.assertFalse((root / 'pmg0_pelvis001cn.tga').exists())
            self.assertEqual(set(p.name for p in root.iterdir()) - {'native-cap-policy.json'},
                             stage.expected_resources('pmg0_pelvis001', {stage.CAP_ROLE}))
            bad = copy.deepcopy(d)
            bad['materials'][0]['normalTexture'] = {'index': 0}
            with self.assertRaises(ValueError): stage.cap_pixels(bad, b, 0, cap_policy(root), {})

    def test_source_mat_cannot_alias_skin_cap_and_garment(self):
        d, b = textured_fixture()
        d['meshes'][0]['primitives'].append(copy.deepcopy(d['meshes'][0]['primitives'][0]))
        with self.assertRaisesRegex(ValueError, 'incompatible roles'):
            stage.materials(d, b, {0: 'skin', 1: 'garment'}, 'pelvis', None, {})

    def test_ascii_writer_preserves_f64_and_enforces_permesh16bit_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = corner_archive()
            c = {'position': a['positions'], 'normal': a['normals'], 'uv': a['uvNative']}
            path = Path(tmp) / 'exact.mdl'
            meshes = stage.write_model(path, 'pmg0_shinl001', c, np.asarray(['skin']))
            self.assertEqual(next(iter(meshes.values()))['asciiProof']['actualAsciiCornerMaximumErrors'],
                             {'position': 0, 'normal': 0, 'uv': 0})
            self.assertIn('.123456789', path.read_text())
            p = np.arange(65538 * 3, dtype=float).reshape(-1, 3, 3)
            too_big = {'position': p, 'normal': np.ones_like(p), 'uv': np.zeros((*p.shape[:2], 2))}
            with self.assertRaisesRegex(RuntimeError, '16-bit'):
                stage.write_model(Path(tmp) / 'too-big.mdl', 'pmg0_shinl001', too_big, np.repeat('skin', len(p)))

    def test_synthetic_stage_keeps_old_helpers_and_final_flags_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tp = root / 'target.json'
            tp.write_text(json.dumps(target_fixture()))
            source = root / 'source.glb'
            write_glb(source, *textured_fixture())
            job = root / 'job.json'
            job.write_text(json.dumps({'state': 'success', 'promptId': 'synthetic', 'outputs': [{'localPath': str(source), 'sha256': tc.sha(source)}]}))
            fit = {'schemaVersion': 2, 'operation': 'fit', 'part': 'forel', 'coordinateSpace': 'working',
                   'targetContract': str(tp), 'targetContractSha256': tc.sha(tp), 'source': str(source), 'sourceSha256': tc.sha(source),
                   'sourceReceipt': str(job), 'sourceReceiptSha256': tc.sha(job), 'uniformScale': .5,
                   'rotationDegreesXYZ': [0, 0, 0], 'sourceAnchorNwn': [0, 0, 0], 'targetAnchorLocal': [0, 0, 0]}
            fc = root / 'fit.json'
            fc.write_text(json.dumps(fit))
            source_receipt = execute(fc, root / 'fit')
            authority = root / 'working-review.json'
            authority.write_text(json.dumps({'kind': 'synthetic-working-review', 'selectedForContinuedWorkingReview': True,
                                             'actualReceipt': stage.ref(source_receipt)}))
            c = {'schemaVersion': 1, 'kind': stage.CONFIG_KIND, 'diagnosticOnly': True, 'part': 'forel',
                 'expectedExecutor': stage.ref(stage.__file__), 'targetContract': stage.ref(tp),
                 'sourceLeaf': stage.ref(source_receipt), 'sourceVerifier': stage.ref(Path(stage.__file__).with_name('target_part_pipeline.py')),
                 'workingSelectionAuthority': stage.ref(authority), 'workingSelectionAuthorityKind': 'synthetic-working-review',
                 'coordinateSpaceFrom': 'working', 'coordinateSpaceTo': 'runtime', 'runtimeScale': {'numerator': 10, 'denominator': 7},
                 'statureApplicationsBefore': 0, 'statureApplicationsAfter': 1, 'aoStrength': 0, 'primitiveRoles': {'0': 'skin'}}
            cp = root / 'stage.json'
            cp.write_text(json.dumps(c))
            approval = root / 'approval.json'
            approval.write_text(json.dumps({'kind': 'root-approved-working-leaf-runtime-stage', 'reviewedBy': '/root',
                                            'authorizeOneFreshDiagnosticOutput': True, 'configuration': stage.ref(cp), 'intendedOutput': str(root / 'runtime')}))
            old_pins = {name: tc.sha(Path(stage.__file__).with_name(name)) for name in ['target_part_pipeline.py', 'target_part_stage.py', 'target_body_inventory.py']}
            result = stage.stage(cp, root / 'runtime', approval)
            receipt = stage.read(result)
            self.assertEqual(receipt['kind'], stage.STAGE_KIND)
            self.assertEqual(receipt['statureApplications'], 1)
            self.assertFalse(any(receipt[k] for k in stage.FLAGS))
            self.assertFalse(receipt['sourceTangentArraysSerializedInAscii'])
            self.assertEqual(old_pins, {n: tc.sha(Path(stage.__file__).with_name(n)) for n in old_pins})
            with self.assertRaisesRegex(ValueError, 'Fresh'):
                stage.stage(cp, root / 'runtime', approval)


if __name__ == '__main__':
    unittest.main()
