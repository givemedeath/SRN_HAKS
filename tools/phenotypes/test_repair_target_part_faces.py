"""A face repair preserves the fitted parent and rejects foreign provenance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import target_contract as contract
from conservative_face_selection import descendant, mesh_arrays
from place_purposebuilt_pelvis import raw_corners, read_glb, write_glb
from repair_target_part_faces import execute, repair_archive
from target_part_pipeline import execute as fit
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture


class TargetFaceRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target = self.root/'target.json'; self.target.write_text(json.dumps(target_fixture()))
        self.original = self.root/'raw.glb'; write_glb(self.original, *fixture())
        self.job = self.root/'generation.json'
        self.job.write_text(json.dumps({'state': 'success', 'promptId': 'one-collected-job',
            'outputs': [{'localPath': str(self.original), 'sha256': contract.sha(self.original)}]}))
        config = {'schemaVersion': 2, 'operation': 'fit', 'part': 'bicepl', 'coordinateSpace': 'working',
                  'targetContract': str(self.target), 'targetContractSha256': contract.sha(self.target),
                  'source': str(self.original), 'sourceSha256': contract.sha(self.original),
                  'sourceReceipt': str(self.job), 'sourceReceiptSha256': contract.sha(self.job),
                  'uniformScale': .63, 'rotationDegreesXYZ': [19, -7, 31],
                  'sourceAnchorNwn': [.11, .08, .02], 'targetAnchorLocal': [.03, -.02, -.04]}
        config_path = self.root/'fit-config.json'; config_path.write_text(json.dumps(config))
        self.parent_path = fit(config_path, self.root/'fit')
        self.parent = json.loads(self.parent_path.read_text())
        _, self.faces, _ = mesh_arrays(*read_glb(self.original))
        self.kept = np.array([0, 1, 2], dtype=np.int64)
        self.added = self.faces[[3]]
        self.trial = self.root/'source-trial.glb'
        descendant(self.original, self.trial, self.kept, self.added)
        self.archive = self.root/'selection.npz'
        self.save_selection()
        self.selection_path = self.root/'selection.json'
        self.selection = {'schemaVersion': 2, 'kind': 'target-face-selection-trial',
            'diagnosticOnly': True, 'eligibleForOfflineReview': True, 'sourceChanged': False,
            'protectedNeighborsChanged': False,
            **{k: self.parent[k] for k in ('targetContractSha256', 'targetId', 'rigRevision', 'part', 'model')},
            'source': str(self.original), 'sourceSha256': contract.sha(self.original),
            'candidate': str(self.trial), 'candidateSha256': contract.sha(self.trial),
            'faceSelectionArchive': {'path': str(self.archive), 'sha256': contract.sha(self.archive)},
            'frozenInputs': {str(self.original): contract.sha(self.original)}}
        self.config = {'schemaVersion': 2, 'kind': 'target-face-repair', 'diagnosticOnly': True,
            'targetContract': str(self.target), 'targetContractSha256': contract.sha(self.target),
            'part': 'bicepl', 'coordinateSpace': 'working',
            'source': self.parent['candidate'], 'sourceSha256': self.parent['candidateSha256'],
            'sourceReceipt': str(self.parent_path), 'sourceReceiptSha256': contract.sha(self.parent_path),
            'selectionReceipt': str(self.selection_path)}

    def tearDown(self): self.tmp.cleanup()

    def save_selection(self, faces=None, kept=None):
        np.savez_compressed(self.archive, sourceFaces=self.faces if faces is None else faces,
            keptSourceFaceIds=self.kept if kept is None else kept,
            deletedSourceFaceIds=np.array([3], dtype=np.int64), addedSourceVertexFaces=self.added)

    def run_repair(self, name='repair'):
        self.selection_path.write_text(json.dumps(self.selection))
        self.config['selectionReceiptSha256'] = contract.sha(self.selection_path)
        path = self.root/(name+'-config.json'); path.write_text(json.dumps(self.config))
        receipt = execute(path, self.root/name)
        return receipt, json.loads(receipt.read_text())

    def test_preserves_serialized_and_authoritative_corners_with_original_vertex_cap(self):
        source = Path(self.parent['candidate']); before = source.read_bytes()
        _, result = self.run_repair()
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(result['statureApplications'], 0)
        self.assertTrue(result['proof']['keptCornerEncodedBytesExact'])
        self.assertEqual(result['proof']['afterTopology']['boundaryEdges'], 0)
        self.assertEqual(result['proof']['afterTopology']['nonmanifoldVertexLinks'], 0)
        self.assertFalse(result['productionAccepted']); self.assertFalse(result['clientAccepted'])
        self.assertTrue(np.array_equal(raw_corners(*read_glb(source))[0],
                                       raw_corners(*read_glb(result['candidate']))[0]))
        with np.load(self.parent['nativeCornerArchive']['path']) as old, np.load(result['nativeCornerArchive']['path']) as new:
            for key in ('positions', 'normals', 'uvGltf', 'uvNative', 'sourcePositions', 'tangents'):
                self.assertTrue(np.array_equal(new[key], old[key]), key)
            self.assertEqual(new['sourceTriangleIds'].tolist(), [0, 1, 2, -1])
            self.assertEqual(new['addedConnectorMask'].tolist(), [False, False, False, True])

    def test_rejects_target_ownership_and_ineligible_trial(self):
        self.selection['rigRevision'] = 'foreign-rig'
        with self.assertRaisesRegex(ValueError, 'ownership differs'):
            self.run_repair()
        self.selection['rigRevision'] = self.parent['rigRevision']
        self.selection['eligibleForOfflineReview'] = False
        with self.assertRaisesRegex(ValueError, 'Eligible immutable'):
            self.run_repair()

    def test_rejects_reordered_faces_and_duplicate_selection(self):
        self.save_selection(faces=self.faces[::-1])
        self.selection['faceSelectionArchive']['sha256'] = contract.sha(self.archive)
        with self.assertRaisesRegex(ValueError, 'ordered source differs'):
            self.run_repair()
        self.save_selection(kept=np.array([0, 0, 2]))
        self.selection['faceSelectionArchive']['sha256'] = contract.sha(self.archive)
        with self.assertRaisesRegex(ValueError, 'Ordered source selection'):
            self.run_repair()

    def test_rejects_new_or_unreferenced_cap_vertices_and_conflicting_authored_rows(self):
        with np.load(self.parent['nativeCornerArchive']['path']) as data:
            parent = {k: data[k].copy() for k in data.files}
        with self.assertRaisesRegex(ValueError, 'retained neighboring'):
            repair_archive(parent, self.faces, self.kept, np.array([[42, 1, 2]]))
        vertex = int(self.faces[0, 0])
        corners = np.argwhere(self.faces == vertex)
        a, b = corners[-1]; parent['normals'][a, b] += .001
        with self.assertRaisesRegex(ValueError, 'Conflicting authoritative'):
            repair_archive(parent, self.faces, self.kept, self.added)

    def test_rejects_runtime_repair_and_protected_neighbor_changes(self):
        self.config['coordinateSpace'] = 'runtime'
        with self.assertRaisesRegex(ValueError, 'before stature'):
            self.run_repair()
        self.config['coordinateSpace'] = 'working'
        neighbor = self.root/'neck.bin'; neighbor.write_bytes(b'unchanged')
        self.config['protectedInputs'] = {str(neighbor): contract.sha(neighbor)}
        neighbor.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
            self.run_repair()


if __name__ == '__main__': unittest.main()
