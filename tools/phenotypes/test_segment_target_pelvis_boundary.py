"""Synthetic planar cuts, exact unaffected rows and rejection/stage invariants."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import target_contract as contract
from conservative_face_selection import descendant, mesh_arrays
from mirror_stock_limb_part import detached_affine_bake
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import BASIS, accessor, read_glb, write_glb
from segment_target_pelvis_boundary import CORNER_KEYS, cut_polygons, execute, segment
from repair_target_part_faces import execute as repair_execute
from target_part_pipeline import execute as fit_execute
from target_part_stage import stage
from test_target_part_pipeline import target_fixture
from test_target_part_stage import textured_fixture
from toolchain_test_fixture import bindings as runtime_test_bindings


def source_fixture(change=None):
    doc, binary = textured_fixture()
    doc['meshes'][0]['primitives'][0]['attributes'].pop('COLOR_0')
    if change:
        semantic = 'NORMAL' if change == 'normal' else 'TANGENT'
        index = doc['meshes'][0]['primitives'][0]['attributes'][semantic]
        values = accessor(doc, binary, index)
        if change == 'normal':
            values[0] = [1, 0, 0]; values[1] = [-1, 0, 0]
        elif change == 'sign':
            values[1, 3] *= -1
        elif change == 'tangent':
            values[:, :3] = [0, 0, 1]
        view = doc['bufferViews'][doc['accessors'][index]['bufferView']]
        mutable = bytearray(binary)
        start = view.get('byteOffset', 0)
        mutable[start:start + values.nbytes] = values.tobytes()
        binary = bytes(mutable)
    return doc, binary


def canonical_fixture(change=None):
    doc, binary = source_fixture(change)
    matrix = np.eye(4); matrix[:3, :3] *= .731234567; matrix[:3, 3] = [.0199999997, -.083, .034]
    return detached_affine_bake(doc, binary, matrix)


def cut_map(doc, binary):
    rows = active_faces(doc, binary)
    first = [.5, .5, 0]; second = [.5, 0, .5]
    return {'faceIdSpace': 'parent-active-primitive-order', 'primitiveFaceCounts': [4],
            'sourceFaceLayoutSha256': face_layout_sha(rows), 'skinFaceIds': [3], 'garmentFaceIds': [],
            'ambiguousFaceIds': [], 'cutFaces': [
                {'sourceFaceId': index, 'boundarySegment': [first, second],
                 'skinPolygon': [first, [0, 1, 0], [0, 0, 1], second],
                 'garmentPolygon': [second, [1, 0, 0], first]} for index in range(3)],
            'review': {'reviewed': True, 'reviewedBy': 'root', 'scope': 'barycentric-pelvis-boundary-segmentation',
                       'sourceTopologyResolved': True, 'notes': 'Synthetic closed tetrahedron boundary only; no real source map.'}}


class PelvisBoundarySegmentationTests(unittest.TestCase):
    def test_append_only_original_rows_materials_maps_and_unaffected_primitive(self):
        doc, binary, archive, _ = canonical_fixture(); original = copy.deepcopy(doc)
        new, blob, result, proof = segment(doc, binary, archive, cut_map(doc, binary))
        self.assertEqual(doc, original); self.assertEqual(blob[:len(binary)], binary)
        self.assertEqual(new['accessors'][:len(doc['accessors'])], doc['accessors'])
        self.assertEqual(new['bufferViews'][:len(doc['bufferViews'])], doc['bufferViews'])
        for key in ('images', 'textures', 'samplers'):
            self.assertEqual(new.get(key), doc.get(key))
        self.assertEqual(new['materials'], doc['materials'] + [doc['materials'][0]])
        whole = new['meshes'][0]['primitives'][0]
        old = doc['meshes'][0]['primitives'][0]
        self.assertEqual(whole['attributes'], old['attributes'])
        for semantic, index in whole['attributes'].items():
            self.assertEqual(accessor(new, blob, index).tobytes(), accessor(doc, binary, index).tobytes())
        for key in CORNER_KEYS | {'tangents'}:
            self.assertEqual(result[key][0].tobytes(), archive[key][3].tobytes())
        self.assertEqual(proof['triangles'], 10); self.assertEqual(proof['facesAdded'], 6)
        self.assertEqual(proof['statureApplicationsAdded'], 0); self.assertFalse(proof['materialBoundaryAccepted'])

    def test_double_precision_planes_areas_uvs_original_corners_and_new_basis(self):
        doc, binary, old, _ = canonical_fixture()
        new, blob, result, proof = segment(doc, binary, old, cut_map(doc, binary))
        self.assertLess(proof['maximumAreaFractionError'], 1e-12)
        self.assertLess(proof['maximumPlaneDeviationMetres'], 1e-14)
        for out, parent_face in enumerate(result['parentTriangleIds']):
            bary = result['parentCornerBarycentrics'][out]
            np.testing.assert_allclose(result['positions'][out], bary @ old['positions'][parent_face], atol=1e-16)
            np.testing.assert_allclose(result['uvGltf'][out], bary @ old['uvGltf'][parent_face], atol=1e-16)
            for corner, source_corner in enumerate(result['sourceCornerOrder'][out]):
                if source_corner >= 0:
                    for key in CORNER_KEYS | {'tangents'}:
                        self.assertEqual(result[key][out, corner].tobytes(), old[key][parent_face, source_corner].tobytes())
                else:
                    normal = result['normals'][out, corner]; tangent = result['tangents'][out, corner]
                    self.assertAlmostEqual(np.linalg.norm(normal), 1, places=13)
                    self.assertAlmostEqual(np.linalg.norm(tangent[:3]), 1, places=13)
                    self.assertAlmostEqual(normal @ tangent[:3], 0, places=13)
                    self.assertEqual(tangent[3], -1)
        cut_attrs = new['meshes'][0]['primitives'][-1]['attributes']
        # Every original cut corner is also byte-exact in the serialized cut branch.
        rows = {key: accessor(new, blob, index) for key, index in cut_attrs.items()}
        self.assertTrue(any(np.array_equal(row, accessor(doc, binary, doc['meshes'][0]['primitives'][0]['attributes']['NORMAL'])[0])
                            for row in rows['NORMAL']))
        self.assertEqual(proof['materialRoles'], {0: 'skin', 1: 'garment'})

    def test_gap_overlap_winding_extra_vertices_and_complex_chords_rejected(self):
        doc, binary, archive, _ = canonical_fixture(); valid = cut_map(doc, binary)
        for change in ('overlap', 'winding', 'extra', 'interior', 'vertex', 'same-edge', 'three-endpoints'):
            bad = copy.deepcopy(valid); cut = bad['cutFaces'][0]
            if change == 'overlap': cut['garmentPolygon'] = copy.deepcopy(cut['skinPolygon'])
            elif change == 'winding': cut['skinPolygon'].reverse()
            elif change == 'extra': cut['skinPolygon'].insert(2, [0, .5, .5])
            elif change == 'interior': cut['boundarySegment'][0] = [.3, .3, .4]
            elif change == 'vertex': cut['boundarySegment'][0] = [1, 0, 0]
            elif change == 'same-edge': cut['boundarySegment'][1] = [.4, .6, 0]
            else: cut['boundarySegment'].append([0, .5, .5])
            with self.subTest(change=change), self.assertRaises(ValueError): segment(doc, binary, archive, bad)

    def test_exhaustive_review_and_no_classifier_controls_required(self):
        doc, binary, archive, _ = canonical_fixture(); valid = cut_map(doc, binary)
        for field, value in [('skinFaceIds', []), ('skinFaceIds', [0, 3]), ('garmentFaceIds', [3]),
                             ('ambiguousFaceIds', [2]), ('sourceFaceLayoutSha256', 'wrong'), ('primitiveFaceCounts', [4.0]), ('pixelThreshold', 40)]:
            bad = copy.deepcopy(valid); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): segment(doc, binary, archive, bad)
        for field, value in [('reviewed', False), ('reviewedBy', 'image-classifier'), ('sourceTopologyResolved', False),
                             ('scope', 'whole-face-material-ownership'), ('notes', ''), ('waivePlate', True)]:
            bad = copy.deepcopy(valid); bad['review'][field] = value
            with self.subTest(review=field), self.assertRaises(ValueError): segment(doc, binary, archive, bad)

    def test_nonconforming_edge_and_adjacent_role_conflicts_rejected(self):
        doc, binary, archive, _ = canonical_fixture(); valid = cut_map(doc, binary)
        bad = copy.deepcopy(valid); removed = bad['cutFaces'].pop(); bad['skinFaceIds'] = [2, 3]
        with self.assertRaisesRegex(ValueError, 'Every cut must match'): segment(doc, binary, archive, bad)
        bad = copy.deepcopy(valid); item = bad['cutFaces'][0]
        item['skinPolygon'], item['garmentPolygon'] = item['garmentPolygon'], item['skinPolygon']
        with self.assertRaisesRegex(ValueError, 'role polygons conflict'): segment(doc, binary, archive, bad)
        bad = copy.deepcopy(valid); item = bad['cutFaces'][0]
        item['boundarySegment'][0] = [.4, .6, 0]; item['skinPolygon'][0] = [.4, .6, 0]; item['garmentPolygon'][-1] = [.4, .6, 0]
        with self.assertRaisesRegex(ValueError, 'Every cut must match'): segment(doc, binary, archive, bad)

    def test_degenerate_interpolated_normals_tangents_and_signs_rejected(self):
        for change, message in [('normal', 'interpolated normal'), ('sign', 'handedness'), ('tangent', 'tangent basis')]:
            doc, binary, archive, _ = canonical_fixture(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message): segment(doc, binary, archive, cut_map(doc, binary))

    def test_unsupported_part_attributes_multiple_primitives_and_bad_archive_rejected(self):
        doc, binary, archive, _ = canonical_fixture()
        with self.assertRaisesRegex(ValueError, 'only to pelvis'): segment(doc, binary, archive, cut_map(doc, binary), 'chest')
        bad = copy.deepcopy(doc); bad['meshes'][0]['primitives'][0]['attributes']['COLOR_0'] = 5
        with self.assertRaisesRegex(ValueError, 'COLOR'): segment(bad, binary, archive, cut_map(bad, binary))
        bad = copy.deepcopy(doc); bad['meshes'][0]['primitives'].append(copy.deepcopy(bad['meshes'][0]['primitives'][0]))
        with self.assertRaisesRegex(ValueError, 'one canonical'): segment(bad, binary, archive, cut_map(doc, binary))
        for change in ('dtype', 'missing', 'extra', 'wrong-tangent', 'stale-uv'):
            bad = copy.deepcopy(archive)
            if change == 'dtype': bad['positions'] = bad['positions'].astype(np.float32)
            elif change == 'missing': bad.pop('tangents')
            elif change == 'extra': bad['unknown'] = np.ones(1)
            elif change == 'wrong-tangent': bad['tangentTriangleIds'][0] = 3
            else: bad['uvGltf'][0, 0, 0] += .01
            with self.subTest(change=change), self.assertRaises(ValueError): segment(doc, binary, bad, cut_map(doc, binary))

    def prepare(self, root, repaired=False):
        toolchain,migration=runtime_test_bindings(root)
        source = root / 'synthetic-generation.glb'; write_glb(source, *source_fixture())
        data = target_fixture(); data['rig'].update(revision='synthetic-offline-frozen', pilotAccepted=True,
                                                   offlineStructureAccepted=True, pilotAcceptanceScope='offline-rig-structure')
        target = root / 'target.json'; target.write_text(json.dumps(data))
        job = root / 'synthetic-job.json'; job.write_text(json.dumps({'state': 'success', 'promptId': 'synthetic-only',
            'outputs': [{'localPath': str(source), 'sha256': contract.sha(source)}]}))
        config = {'schemaVersion': 2, 'operation': 'fit', 'part': 'pelvis', 'coordinateSpace': 'working',
                  'targetContract': str(target), 'targetContractSha256': contract.sha(target), 'source': str(source),
                  'sourceSha256': contract.sha(source), 'sourceReceipt': str(job), 'sourceReceiptSha256': contract.sha(job),
                  'uniformScale': .731234567, 'rotationDegreesXYZ': [13, -7, 29], 'sourceAnchorNwn': [.03, .02, -.01],
                  'targetAnchorLocal': [.01, -.04, -.02]}
        path = root / 'fit-config.json'; path.write_text(json.dumps(config)); parent_path = fit_execute(path, root / 'fit')
        parent = json.loads(parent_path.read_text()); fitted = Path(parent['candidate'])
        if repaired:
            _, faces, _ = mesh_arrays(*read_glb(source))
            chosen = root / 'synthetic-source-face-trial.glb'; descendant(source, chosen, np.arange(4), np.empty((0, 3), dtype=np.int64))
            archive_path = root / 'synthetic-source-face-trial.npz'
            np.savez_compressed(archive_path, sourceFaces=faces, keptSourceFaceIds=np.arange(4),
                                deletedSourceFaceIds=np.empty(0, dtype=np.int64), addedSourceVertexFaces=np.empty((0, 3), dtype=np.int64))
            trial = {'schemaVersion': 2, 'kind': 'target-face-selection-trial', 'eligibleForOfflineReview': True,
                     'diagnosticOnly': True, 'sourceChanged': False, 'protectedNeighborsChanged': False,
                     **contract.binding(target, data, 'working'), 'part': 'pelvis', 'model': 'pmg0_pelvis001',
                     'source': str(source), 'sourceSha256': contract.sha(source), 'candidate': str(chosen),
                     'candidateSha256': contract.sha(chosen), 'faceSelectionArchive': {'path': str(archive_path), 'sha256': contract.sha(archive_path)},
                     'frozenInputs': {str(p): contract.sha(p) for p in (source, chosen, archive_path)}}
            trial_path = root / 'synthetic-selection-trial.json'; trial_path.write_text(json.dumps(trial))
            repair_config = {'schemaVersion': 2, 'kind': 'target-face-repair', 'diagnosticOnly': True,
                'targetContract': str(target), 'targetContractSha256': contract.sha(target), 'part': 'pelvis', 'coordinateSpace': 'working',
                'source': str(fitted), 'sourceSha256': contract.sha(fitted), 'sourceReceipt': str(parent_path),
                'sourceReceiptSha256': contract.sha(parent_path), 'selectionReceipt': str(trial_path), 'selectionReceiptSha256': contract.sha(trial_path)}
            repair_path = root / 'repair-config.json'; repair_path.write_text(json.dumps(repair_config))
            parent_path = repair_execute(repair_path, root / 'repaired')
            parent = json.loads(parent_path.read_text()); fitted = Path(parent['candidate'])
        selection = cut_map(*read_glb(fitted)); selection.update(schemaVersion=2, kind='target-pelvis-boundary-cut-map', diagnosticOnly=True,
            part='pelvis', joint='pelvis_g', model='pmg0_pelvis001', source=str(fitted), sourceSha256=contract.sha(fitted),
            sourceReceipt=str(parent_path), sourceReceiptSha256=contract.sha(parent_path), **contract.binding(target, data, 'working'))
        review = root / 'synthetic-root-review.txt'; review.write_text('Synthetic boundary fixture only; no production source selected.')
        selection['review']['evidence'] = [{'path': str(review), 'sha256': contract.sha(review)}]
        cut_path = root / 'cut-map.json'; cut_path.write_text(json.dumps(selection))
        config = {'schemaVersion': 2, 'kind': 'target-pelvis-boundary-segmentation', 'diagnosticOnly': True, 'part': 'pelvis',
                  'coordinateSpace': 'working', 'targetContract': str(target), 'targetContractSha256': contract.sha(target),
                  'source': str(fitted), 'sourceSha256': contract.sha(fitted), 'sourceReceipt': str(parent_path),
                  'sourceReceiptSha256': contract.sha(parent_path), 'cutMap': str(cut_path), 'cutMapSha256': contract.sha(cut_path),
                  'sharedToolchain': str(toolchain), 'sharedToolchainSha256': contract.sha(toolchain),
                  'migrationReceipt': str(migration), 'migrationReceiptSha256': contract.sha(migration)}
        path = root / 'segment-config.json'; path.write_text(json.dumps(config))
        return path, target, parent_path, parent, cut_path

    def test_real_guards_synthetic_fit_receipt_archive_and_unchanged_stage_compatibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); config, target, _, parent, _ = self.prepare(root)
            with patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root): receipt_path = execute(config, root / 'segmented')
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt['operation'], 'material-boundary-segmentation'); self.assertEqual(receipt['statureApplications'], 0)
            self.assertEqual(receipt['sourceToAttachmentLocal'], np.eye(4).tolist()); self.assertEqual(receipt['attachmentWorld'], parent['attachmentWorld'])
            self.assertFalse(receipt['geometryAccepted']); self.assertFalse(receipt['materialBindingsAccepted']); self.assertFalse(receipt['productionAccepted'])
            with np.load(receipt['nativeCornerArchive']['path']) as corners:
                self.assertEqual(corners['positions'].dtype, np.float64); self.assertEqual(corners['positions'].shape, (10, 3, 3))
            staging = {'schemaVersion': 2, 'kind': 'target-part-stage', 'diagnosticOnly': True, 'part': 'pelvis', 'coordinateSpace': 'working',
                       'targetContract': str(target), 'targetContractSha256': contract.sha(target), 'source': receipt['candidate'],
                       'sourceSha256': receipt['candidateSha256'], 'sourceReceipt': str(receipt_path), 'sourceReceiptSha256': contract.sha(receipt_path),
                       'materialRoles': receipt['materialRoles'], 'aoStrength': 0}
            config = root / 'stage-config.json'; config.write_text(json.dumps(staging)); stage_path = stage(config, root / 'stage')
            staged = json.loads(stage_path.read_text()); self.assertEqual(set(staged['rawAttributeAsciiProof']), {'skin', 'garment'})
            self.assertNotIn('texture0', (root / 'stage/resources/pmg0_pelvis001.mtr').read_text())
            self.assertIn('texture0 pmg0_pelvis001f', (root / 'stage/resources/pmg0_pelvis001f.mtr').read_text())
            self.assertFalse(staged['clientAccepted']); self.assertFalse(staged['nativeCompiled'])

    def test_stale_source_map_scope_part_runtime_and_missing_review_fail_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path, target, _, _, cut_path = self.prepare(root)
            valid = json.loads(path.read_text())
            for field, value in [('sourceSha256', 'wrong'), ('cutMapSha256', 'wrong'), ('part', 'chest'), ('coordinateSpace', 'runtime'), ('uniformScale', 2)]:
                bad = copy.deepcopy(valid); bad[field] = value; path.write_text(json.dumps(bad))
                with self.subTest(field=field), patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root), self.assertRaises(ValueError): execute(path, root / 'must-not-exist')
                self.assertFalse((root / 'must-not-exist').exists())
            path.write_text(json.dumps(valid)); selection = json.loads(cut_path.read_text()); selection['review']['evidence'] = []
            cut_path.write_text(json.dumps(selection)); valid['cutMapSha256'] = contract.sha(cut_path); path.write_text(json.dumps(valid))
            with patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root), self.assertRaisesRegex(ValueError, 'root-review evidence'): execute(path, root / 'must-not-exist')
            self.assertFalse((root / 'must-not-exist').exists())
            for scope in ('rigStructureOffline', 'production', None):
                data = json.loads(target.read_text()); data['rig']['pilotAcceptanceScope'] = scope; target.write_text(json.dumps(data))
                valid['targetContractSha256'] = contract.sha(target); path.write_text(json.dumps(valid))
                with self.subTest(scope=scope), patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root), self.assertRaisesRegex(ValueError, 'frozen offline'): execute(path, root / 'must-not-exist')

    def test_genuine_synthetic_repaired_parent_lineage_and_connector_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); config, _, parent_path, parent, _ = self.prepare(root, repaired=True)
            self.assertEqual(parent['operation'], 'face-repair')
            with patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root): output = execute(config, root / 'segmented')
            receipt = json.loads(output.read_text()); self.assertEqual(receipt['sourceReceipt'], str(parent_path))
            self.assertEqual(receipt['statureApplications'], 0)
            with np.load(parent['nativeCornerArchive']['path']) as old, np.load(receipt['nativeCornerArchive']['path']) as new:
                np.testing.assert_array_equal(new['addedConnectorMask'], old['addedConnectorMask'][new['parentTriangleIds']])
                np.testing.assert_array_equal(new['parentAddedSourceVertexFaces'], old['addedSourceVertexFaces'])
                np.testing.assert_array_equal(new['sourceTriangleIds'], old['sourceTriangleIds'][new['parentTriangleIds']])
                self.assertEqual(new['positions'][0].tobytes(), old['positions'][3].tobytes())

    def test_double_stature_count_and_unresolved_repair_proof_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path, _, parent_path, parent, cut_path = self.prepare(root, repaired=True)
            config = json.loads(path.read_text()); selection = json.loads(cut_path.read_text())
            for change in ('stature', 'closure'):
                bad = copy.deepcopy(parent)
                if change == 'stature': bad['statureApplications'] = 1
                else: bad['proof']['afterTopology']['boundaryEdges'] = 1
                parent_path.write_text(json.dumps(bad)); config['sourceReceiptSha256'] = contract.sha(parent_path)
                selection['sourceReceiptSha256'] = contract.sha(parent_path); cut_path.write_text(json.dumps(selection))
                config['cutMapSha256'] = contract.sha(cut_path); path.write_text(json.dumps(config))
                with self.subTest(change=change), patch('segment_target_pelvis_boundary.ARTIFACT_ROOT', root), self.assertRaises(ValueError): execute(path, root / 'must-not-exist')
                self.assertFalse((root / 'must-not-exist').exists())


if __name__ == '__main__':
    unittest.main()
