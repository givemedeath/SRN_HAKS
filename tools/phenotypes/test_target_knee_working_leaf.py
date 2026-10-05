"""Selection/ownership and lossless working authority; no runtime output tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as tc
import target_knee_working_leaf as leaf
from test_target_part_pipeline import target_fixture


class KneeWorkingLeafTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = target_fixture()
        self.target['rig'].update(offlineStructureAccepted=True, pilotAcceptanceScope='offline-rig-structure')
        self.tp = self.root / 'target.json'
        self.tp.write_text(json.dumps(self.target))
        self.source = {'path': str(self.root / 'leaf.json'), 'sha256': leaf.SOURCES['shinl'][1]}
        self.candidate = {'path': str(self.root / 'candidate.glb'), 'sha256': leaf.SOURCES['shinl'][2]}
        self.archive = {'path': str(self.root / 'corners.npz'), 'sha256': '3' * 64}

    def receipt(self):
        return {**tc.binding(self.tp, self.target, 'working'), 'schemaVersion': 1,
                'kind': leaf.SOURCES['shinl'][0], 'scope': leaf.knee.SCOPE, 'operation': leaf.OPERATION,
                'part': 'shinl', 'joint': 'lshin_g', 'model': tc.model(self.target, 'shinl'),
                'candidate': self.candidate['path'], 'candidateSha256': self.candidate['sha256'],
                'statureApplications': 0, 'fieldApplications': 1, 'parentFieldsReapplied': False,
                'rigOrNeighborsChanged': False, 'diagnosticOnly': True, 'canonicalNativeLineage': False,
                'attachmentAppliedOnce': True, 'candidateToAttachmentLocal': np.eye(4).tolist(),
                'attachmentWorld': tc.frame(self.target, 'lshin_g').tolist(),
                'pendingGates': {k: False for k in leaf.FLAGS}}

    def authority(self):
        evidence, images = [], []
        portable = self.root / 'portable.json'
        portable.write_text(json.dumps({'kind': 'fully-validated-portable-local-knee-terminal-preview-row',
            'part': 'shinl', 'receiptKind': leaf.SOURCES['shinl'][0], 'receipt': self.source['path'],
            'receiptSha256': self.source['sha256'], 'candidate': self.candidate['path'],
            'candidateSha256': self.candidate['sha256'], 'nativeCornerArchive': self.archive}))
        pose_path = self.root / 'source-pose.json'
        pose_path.write_text('{}')
        for i, pose in enumerate(['standing', 'kneeling']):
            pins = []
            for role in ['source', 'child']:
                p = self.root / (pose + '-' + role + '.png')
                Image.fromarray(np.full((3, 4, 3), 20 + i + (role == 'child'), dtype='u1')).save(p)
                pins.append(leaf.ref(p))
            clip, time = ('pause1', 0.0) if i == 0 else ('kneel', 1.5)
            for variant, pin in zip(['parents', 'terminalChildren'], pins):
                images.append({'clip': clip, 'time': time, 'variant': variant, 'image': pin,
                    'camera': {'matrixWorld': np.eye(4).tolist(), 'projectionMatrix': np.eye(4).tolist(), 'orthoScale': 1.},
                    'sourcePose': leaf.ref(pose_path), 'heldFingerprints': {'neck': '4' * 64},
                    'actualChildRows': {'shinl': leaf.ref(portable)}, 'sourceMaterialsMapsPreserved': True,
                    'heldCurrentActorOriginalFoot120': True, 'fieldNotReapplied': True, 'statureApplications': 0,
                    'actualImportProof': {'shinl': {'candidate': self.candidate, 'maxPerror': 0., 'maxUVerror': 0.,
                        'orderedCorners': 149994, 'ordinaryDirectionBoundsPass': True, 'sourceAuthoredN_T_UVUnchanged': True}}})
            evidence.append({'poseClass': pose, 'reviewedBy': '/root', 'jointReviewPassed': True,
                             'sourceMatchedCameraAndNeighbors': True, 'sourceImage': pins[0],
                             'childImage': pins[1]})
        proof = self.root / 'proof.json'
        proof.write_text(json.dumps({'kind': 'actual-matched-two-knee-owner-terminal-four-view-review',
            'onlyTwoLeftOwnerChildrenDiffer': True, 'foot120Unchanged': True, 'images': images}))
        for item in evidence:
            item['comparisonProof'] = leaf.ref(proof)
        return {**tc.binding(self.tp, self.target, 'working'), 'schemaVersion': 1, 'kind': leaf.AUTHORITY_KIND,
                'reviewedBy': '/root', 'reviewed': True, 'selectedForWorkingContinuation': True,
                'pendingGates': {k: False for k in leaf.FLAGS}, 'selections': [
                    {'part': 'shinl', 'receipt': self.source, 'candidate': self.candidate,
                     'nativeCornerArchive': self.archive, 'selectedForWorkingContinuation': True,
                     'noNewUnintendedShelvesObserved': True,
                     'inheritedShadingDiagnosticSourceFaces': leaf.SOURCES['shinl'][4], 'jointEvidence': evidence}]}

    def selected(self, authority):
        return leaf.validate_selection(authority, 'shinl', self.source, self.candidate, self.archive,
                                       self.tp, self.target, {})

    def test_source_rejects_other_owner_old_kind_runtime_fields_and_frame_reapplication(self):
        receipt = self.receipt()
        leaf.validate_source(receipt, 'shinl', self.tp, self.target, self.source, self.candidate)
        for field, value in [('kind', 'target-part-diagnostic-shin-girth90-after85'), ('part', 'shinr'),
                             ('operation', 'mirror'), ('coordinateSpace', 'runtime'), ('statureApplications', 1),
                             ('fieldApplications', 2), ('parentFieldsReapplied', True), ('attachmentAppliedOnce', False)]:
            bad = copy.deepcopy(receipt)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                leaf.validate_source(bad, 'shinl', self.tp, self.target, self.source, self.candidate)
        bad = copy.deepcopy(receipt)
        bad['candidateToAttachmentLocal'][0][3] = .001
        with self.assertRaises(ValueError): leaf.validate_source(bad, 'shinl', self.tp, self.target, self.source, self.candidate)
        with self.assertRaises(ValueError): leaf.validate_source(receipt, 'legl', self.tp, self.target, self.source, self.candidate)
        source = dict(self.source, sha256='0' * 64)
        with self.assertRaises(ValueError): leaf.validate_source(receipt, 'shinl', self.tp, self.target, source, self.candidate)

    def test_single_selected_shin_does_not_force_unselected_thigh_acceptance(self):
        authority = self.authority()
        self.selected(authority)
        with self.assertRaisesRegex(ValueError, 'owner must be selected'):
            leaf.validate_selection(authority, 'legl', self.source, self.candidate, self.archive,
                                    self.tp, self.target, {})

    def test_export_review_unselected_wrong_root_and_final_acceptance_do_not_select(self):
        authority = self.authority()
        for field, value in [('kind', 'root-approved-local-knee-terminal-review'), ('reviewedBy', 'other'),
                             ('reviewed', False), ('selectedForWorkingContinuation', False),
                             ('coordinateSpace', 'runtime'), ('targetContractSha256', '0' * 64)]:
            bad = copy.deepcopy(authority)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.selected(bad)
        bad = copy.deepcopy(authority)
        bad['pendingGates']['nativeAccepted'] = True
        with self.assertRaises(ValueError): self.selected(bad)
        with self.assertRaisesRegex(ValueError, 'path/hash'):
            leaf.pinned(None, {})

    def test_same_kind_authority_requires_exact_receipt_candidate_archive_and_unique_owner(self):
        authority = self.authority()
        for field in ['receipt', 'candidate', 'nativeCornerArchive']:
            bad = copy.deepcopy(authority)
            bad['selections'][0][field]['sha256'] = '0' * 64
            with self.subTest(field=field), self.assertRaises(ValueError): self.selected(bad)
        for field, value in [('noNewUnintendedShelvesObserved', False), ('inheritedShadingDiagnosticSourceFaces', [])]:
            bad = copy.deepcopy(authority)
            bad['selections'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.selected(bad)
        bad = copy.deepcopy(authority)
        bad['selections'] *= 2
        with self.assertRaises(ValueError): self.selected(bad)

    def test_standing_and_kneel_image_pair_and_successful_literal_association_are_required(self):
        authority = self.authority()
        bad = copy.deepcopy(authority)
        bad['selections'][0]['jointEvidence'].pop()
        with self.assertRaises(ValueError): self.selected(bad)
        for field, value in [('sourceMatchedCameraAndNeighbors', False), ('jointReviewPassed', False)]:
            bad = copy.deepcopy(authority)
            bad['selections'][0]['jointEvidence'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.selected(bad)
        proof_pin = authority['selections'][0]['jointEvidence'][0]['comparisonProof']
        path = Path(proof_pin['path'])
        proof = json.loads(path.read_text())
        proof['images'][1]['actualImportProof']['shinl']['candidate']['sha256'] = '0' * 64
        path.write_text(json.dumps(proof))
        authority['selections'][0]['jointEvidence'][0]['comparisonProof'] = leaf.ref(path)
        with self.assertRaisesRegex(ValueError, 'child import proof'): self.selected(authority)

    def test_actual_comparison_rejects_wrong_portable_owner_pose_variant_camera_or_neighbors(self):
        for defect in ['owner', 'pose', 'variant', 'camera', 'neighbors', 'missingImport', 'scale']:
            authority = self.authority()
            pin = authority['selections'][0]['jointEvidence'][0]['comparisonProof']
            path = Path(pin['path'])
            proof = json.loads(path.read_text())
            child = proof['images'][1]
            if defect == 'owner':
                portable = Path(child['actualChildRows']['shinl']['path'])
                row = json.loads(portable.read_text())
                row['part'] = 'legl'
                portable.write_text(json.dumps(row))
                for image in proof['images']: image['actualChildRows']['shinl'] = leaf.ref(portable)
            if defect == 'pose': child['time'] = .5
            if defect == 'variant': child['variant'] = 'parents'
            if defect == 'camera': child['camera']['matrixWorld'][0][3] += .001
            if defect == 'neighbors': child['heldFingerprints']['neck'] = '5' * 64
            if defect == 'missingImport': child['actualImportProof'].pop('shinl')
            if defect == 'scale': child['statureApplications'] = 1
            path.write_text(json.dumps(proof))
            for item in authority['selections'][0]['jointEvidence']: item['comparisonProof'] = leaf.ref(path)
            with self.subTest(defect=defect), self.assertRaises(ValueError): self.selected(authority)

    def test_changed_or_nonimage_joint_input_is_rejected(self):
        authority = self.authority()
        pin = authority['selections'][0]['jointEvidence'][0]['childImage']
        path = Path(pin['path'])
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed input'): self.selected(authority)
        pin.update(leaf.ref(path))
        with self.assertRaisesRegex(ValueError, 'PNG'): self.selected(authority)

    def arrays(self):
        P = np.array([[[.123456789123, 0, 0], [1.123456789123, 0, 0], [.123456789123, 1, 0]]], '<f8')
        N = np.tile([0., 0., 1.3], (1, 3, 1))
        T = np.tile([1.2, 0., .17, -1.], (1, 3, 1))
        return {'positions': P, 'normals': N, 'tangents': T, 'uvNative': np.array([[[.1, .2], [.9, .2], [.1, .8]]]),
                'primitiveIds': np.array([0]), 'sourceTriangleIds': np.array([0]), 'sourceCornerOrder': np.array([[0, 1, 2]]),
                'kneeTerminalParentPositions': P.copy(), 'kneeTerminalParentNormals': N.copy(),
                'kneeTerminalParentTangents': T.copy(), 'oldRawBits': np.array([0x3F123456, 0x400001], '<u4')}

    def test_current_float64_and_all_historical_bits_remain_unscaled_and_read_only(self):
        original = self.arrays()
        path = self.root / 'working.npz'
        np.savez_compressed(path, **original)
        result = leaf.working_archive(leaf.ref(path), 1, {})
        self.assertFalse(np.array_equal(original['positions'], original['positions'].astype('f4').astype('f8')))
        self.assertEqual(set(result), set(original))
        for key, value in original.items():
            self.assertEqual(result[key].dtype, value.dtype)
            self.assertEqual(result[key].tobytes(), value.tobytes())
            self.assertFalse(result[key].flags.writeable)

    def test_working_archive_rejects_runtime_f32_malformed_source_order_and_invalid_basis(self):
        for defect in ['runtime', 'f32', 'badW', 'zeroN', 'sourceOrder', 'wrongOwner', 'missingHistory']:
            rows = self.arrays()
            if defect == 'runtime': rows['runtimeWorkingPositions'] = rows['positions'].copy()
            if defect == 'f32': rows['positions'] = rows['positions'].astype('f4')
            if defect == 'badW': rows['tangents'][0, 0, 3] = 0
            if defect == 'zeroN': rows['normals'][0, 0] = 0
            if defect == 'sourceOrder': rows['sourceCornerOrder'] = np.array([[0, 2, 1]])
            if defect == 'wrongOwner': rows['primitiveIds'][0] = 1
            if defect == 'missingHistory': rows.pop('kneeTerminalParentPositions')
            path = self.root / (defect + '.npz')
            np.savez_compressed(path, **rows)
            with self.subTest(defect=defect), self.assertRaises(ValueError): leaf.working_archive(leaf.ref(path), 1, {})
        with self.assertRaisesRegex(ValueError, 'Nonempty'): leaf.working_archive({}, 0, {})


if __name__ == '__main__':
    unittest.main()
