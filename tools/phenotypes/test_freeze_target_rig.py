"""Guarded freeze fixtures prove scope separation and immutable compatibility."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

from freeze_target_rig import freeze, inspect_source, prepare, verify_review, PENDING_GATES
from target_contract import PART_JOINTS, binding, load, sha, verify_binding


def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source-rig'
        self.source.mkdir()
        self.contract_path, self.export_path, self.audit_path = [self.source / name for name in
                                                               ['target-contract.json', 'rig-export.json', 'independent-audit.json']]
        self.review_path, self.output = self.base / 'review.json', self.base / 'frozen-rig'
        self.revision = 'reviewed-offline-structure-v1'
        self.factor = 10 / 7
        self.aliases = {'pmh0': 'pmg0', 'a_ba': 'sr_tmg0_01'}
        joints = ['pmh0', *PART_JOINTS.values(), 'rhand', 'lhand', 'head', 'headconjure', 'handconjure', 'impact', 'wings', 'cloak_g', 'tail']
        self.positions = {name: ([0, 0, 0] if name == 'pmh0' else [i * .01, -.02, 1 + i * .03]) for i, name in enumerate(joints)}
        frames = {}
        models = []
        for space, factor in [('working', 1), ('runtime', self.factor)]:
            frames[space] = {}
            for name in joints:
                matrix = np.eye(4)
                matrix[:3, 3] = np.asarray(self.positions[name]) * factor
                frames[space][name] = matrix.tolist()
            for original, model in self.aliases.items():
                text = 'newmodel ' + model + '\nsetsupermodel ' + model + (' sr_tmg0_01' if model == 'pmg0' else ' NULL') + '\nbeginmodelgeom ' + model + '\n'
                for name in joints:
                    renamed = 'pmg0' if name == 'pmh0' else name
                    # Only the root model is evaluated for declared attachment frames.
                    text += 'node dummy ' + renamed + '\n parent ' + ('NULL' if name == 'pmh0' else 'pmg0') + '\n position ' + ' '.join(format(value * factor, '.17g') for value in self.positions[name]) + '\n orientation 0 0 1 0\nendnode\n'
                text += 'endmodelgeom ' + model + '\ndonemodel ' + model + '\n'
                path = self.source / space / 'ascii' / (model + '.mdl')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='ascii')
                models.append({'space': space, 'source': original, 'model': model, 'sha256': sha(path),
                               'clipCount': int(original != 'pmh0'), 'positionalControllers': []})
        snapshots = self.source / 'source-inputs'
        fake_builder = snapshots / 'tools' / 'builder.py'
        fake_audit = snapshots / 'tools' / 'audit.py'
        fake_builder.parent.mkdir(parents=True)
        fake_builder.write_text('# synthetic fixture export proof\n', encoding='utf-8')
        fake_audit.write_text('# synthetic fixture independent proof\n', encoding='utf-8')
        frozen = {str(path): sha(path) for path in [fake_builder, fake_audit]}
        self.data = {'schemaVersion': 2, 'kind': 'phenotype-target', 'id': 'freeze-fixture-male-v1',
                     'identity': {'gender': 'male', 'phenotype': 0, 'prefix': 'pmg0', 'raceId': 2, 'appearanceRow': 2},
                     'workingHeightMeters': 1.9339157, 'heightMeters': 1.9339157 * self.factor,
                     'models': {part: 'pmg0_' + part + '001' for part in PART_JOINTS},
                     'rig': {'revision': 'fixture-unaccepted-v1', 'runtimeScale': self.factor, 'sourcePrefix': 'pmh0',
                             'positionPolicy': 'bind-relative', 'preserveRotations': True, 'preserveTimingEvents': True,
                             'frames': frames, 'privateAliases': self.aliases, 'pilotAccepted': False,
                             'sourceBindLocal': self.positions, 'targetWorkingBindLocal': self.positions, 'changedLocalPositions': {}},
                     'equipment': {'profilesAccepted': False}, 'material': {'normalStrength': 1, 'skinTexture0': False},
                     'productionAccepted': False, 'clientAccepted': False, 'frozenInputs': frozen}
        write(self.contract_path, self.data)
        self.export = {'schemaVersion': 2, 'kind': 'target-rig-export', 'targetContractSha256': sha(self.contract_path),
                       'models': models, 'sourceInputs': frozen, 'originalInputs': {}, 'exportHelpers': {'builder.py': sha(fake_builder)},
                       'python': {'executable': sys.executable, 'sha256': sha(sys.executable)},
                       'geometryScaleAppliedOnce': True, 'sourceRotationsTimingEventsUnchanged': True,
                       'generationPoseInputs': False, 'clientAccepted': False}
        write(self.export_path, self.export)
        self.audit = {'schemaVersion': 1, 'kind': 'target-rig-independent-audit', 'targetContractSha256': sha(self.contract_path),
                      'rigExportSha256': sha(self.export_path), 'sourceNativeFilesChecked': 1, 'nonunitGeometryNodeScales': 0,
                      'positionBezierControllers': 0, 'verified': True, 'clientEvidence': False, 'pilotAccepted': False,
                      'nativeBoundsAccepted': False, 'strideBehaviorAccepted': False,
                      'auditHelpers': {str(fake_audit): sha(fake_audit)}, 'python': {'executable': sys.executable},
                      'spaces': {}, 'poseSamples': [], 'sockets': {},
                      'strideMetadata': {'runtimeScale': self.factor, 'tableWalkRunCollisionValuesAccepted': False}}
        for space in ['working', 'runtime']:
            records = [{'source': row['source'], 'target': row['model'], 'sha256': row['sha256'], 'clipCount': row['clipCount']}
                       for row in models if row['space'] == space]
            self.audit['spaces'][space] = {'models': records, 'clips': 1, 'nodes': 2, 'positionKeyRows': 1, 'rotationKeyRows': 1,
                                           'maxParentBasisError': 0, 'maxPositionError': 0}
        clips = ['pause1', 'pause2', 'walk', 'run', 'conjure1', 'kneel', 'deadfnt']
        for clip in clips:
            self.audit['poseSamples'].append({'clip': clip, 'sourceClipSha256': hashlib.sha256(clip.encode()).hexdigest(),
                                              'samples': [{'maxWorldScaleError': 0} for _ in range(9)]})
        for name in ['rhand', 'lhand', 'head', 'headconjure', 'handconjure', 'impact', 'wings', 'cloak_g', 'tail']:
            self.audit['sockets'][name] = {'workingPosition': self.positions[name],
                                            'runtimePosition': (np.asarray(self.positions[name]) * self.factor).tolist()}
        write(self.audit_path, self.audit)
        state = inspect_source(self.contract_path, self.export_path, self.audit_path)
        self.review = {'schemaVersion': 1, 'kind': 'offline-rig-root-review', 'reviewedBy': 'root', 'approved': True,
                       'decision': 'freeze-offline-rig-structure', 'acceptedScopes': ['rigStructureOffline'],
                       'pendingGates': sorted(PENDING_GATES), 'geometryChangesAuthorized': False, 'bodyRebindingAuthorized': False,
                       'offlineMotionReviewed': True, 'pendingIssues': ['Casting cap, sole, microtopology and materials pending'],
                       'protectedUserShapePreferences': ['Retain approved collar, chest and arms'], 'requestedRevision': self.revision,
                       'expectedStructureSha256': state['structureSha256'], 'expectedModels': state['expectedModels'], 'motionEvidence': []}
        for key, path in [('sourceContract', self.contract_path), ('sourceExport', self.export_path), ('independentAudit', self.audit_path)]:
            self.review[key] = {'path': str(path), 'sha256': sha(path)}
        for clip in clips:
            path = self.base / 'motion' / (clip + '.json')
            specimen = {'target': binding(self.contract_path, self.data, 'working'), 'clip': clip, 'time': .5, 'length': 1,
                        'clientAccepted': False, 'clientEvidence': False, 'displayScale': 1,
                        'rootFile': str(self.source / 'working/ascii/pmg0.mdl'), 'rootSha256': state['expectedModels']['working/pmg0'],
                        'file': str(self.source / 'working/ascii/sr_tmg0_01.mdl'), 'sha256': state['expectedModels']['working/sr_tmg0_01'],
                        'sourceInheritance': [{'file': str(self.source / 'working/ascii/pmg0.mdl'), 'model': 'pmg0', 'sha256': state['expectedModels']['working/pmg0']}],
                        'partInputs': {}, 'targetPartReceipts': [], 'jointWorldMatrices': frames['working']}
            write(path, {'specimens': [specimen]})
            self.review['motionEvidence'].append({'path': str(path), 'sha256': sha(path), 'clip': clip})
        write(self.review_path, self.review)
        self.add_pilot_review()

    def invoke(self):
        return freeze(self.contract_path, self.export_path, self.audit_path, self.review_path, self.output, self.revision)

    def add_pilot_review(self):
        cases = []
        batch = self.base / 'batch.json'
        write(batch, {'fixture': True})
        for entry in self.review['motionEvidence']:
            launch_path = self.base / 'launches' / (entry['clip'] + '.json')
            write(launch_path, {'kind': 'verified-shared-tool-launch', 'exitCode': 0, 'tool': 'blender',
                                'gameClientTesting': False, 'preMigrationSmoke': False, 'frozenInputs': {}})
            image_path = self.base / 'images' / (entry['clip'] + '.png')
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b'synthetic opaque image fixture')
            comparison = {'path': entry['path'], 'sha256': entry['sha256']}
            launch = {'path': str(launch_path), 'sha256': sha(launch_path)}
            cases.append({'key': entry['clip'] + '-50', 'clip': entry['clip'], 'views': ['front'],
                          'comparison': comparison, 'launch': launch,
                          'preserved': {'comparison': comparison, 'launch': launch,
                                        'images': [{'path': str(image_path), 'sha256': sha(image_path)}]}})
        pilot = {'schemaVersion': 1, 'kind': 'root-offline-troll-pilot-review', 'offlineBindStructureReviewPassed': True,
                 'targetContract': self.review['sourceContract'], 'parts': {}, 'batch': {'path': str(batch), 'sha256': sha(batch)},
                 'cases': cases, 'remainingIssues': self.review['pendingIssues'], 'userApprovals': self.review['protectedUserShapePreferences'],
                 'rigPilotAccepted': False, 'bodyGeometryAccepted': False, 'materialAccepted': False,
                 'equipmentAccepted': False, 'clientAccepted': False, 'productionAccepted': False}
        path = self.base / 'pilot-review.json'
        write(path, pilot)
        self.review['pilotReview'] = {'path': str(path), 'sha256': sha(path)}
        write(self.review_path, self.review)
        return path, pilot

    def test_freeze_copies_bytes_once_preserves_frames_and_leaves_other_gates_pending(self):
        before = {str(path): sha(path) for path in self.source.rglob('*') if path.is_file()}
        result = json.loads(self.invoke().read_text())
        new_path = self.output / 'target-contract.json'
        new = load(new_path)
        self.assertEqual(new['rig']['frames'], self.data['rig']['frames'])
        self.assertEqual(new['models'], self.data['models'])
        self.assertEqual(new['material'], self.data['material'])
        self.assertEqual(new['rig']['pilotAcceptanceScope'], 'offline-rig-structure')
        self.assertTrue(new['rig']['pilotAccepted'])
        self.assertEqual(new['acceptance'], {'rigStructureOffline': True, **{key: False for key in PENDING_GATES}})
        self.assertEqual(new['acceptanceMetadata']['pendingIssues'], self.review['pendingIssues'])
        self.assertEqual(result['scaleApplicationsDuringFreeze'], 0)
        self.assertFalse(result['bodyReceiptsRebound'])
        for row in result['modelCopies']:
            self.assertEqual(Path(row['source']).read_bytes(), Path(row['destination']).read_bytes())
        self.assertEqual(before, {str(path): sha(path) for path in self.source.rglob('*') if path.is_file()})
        with self.assertRaisesRegex(ValueError, 'another target'):
            verify_binding(binding(self.contract_path, self.data, 'working'), new_path, new, 'working')
        self.assertEqual(json.loads((self.output / 'rig-export.json').read_text())['targetContractSha256'], sha(new_path))

    def test_prepare_does_not_create_contract_or_approval(self):
        path = prepare(self.contract_path, self.export_path, self.audit_path, self.output)
        self.assertFalse(json.loads(path.read_text())['rigFrozen'])
        self.assertFalse((self.output / 'target-contract.json').exists())
        self.assertFalse(json.loads((self.output / 'root-review-template.unapproved.json').read_text())['approved'])

    def test_root_approval_is_required_before_any_output(self):
        self.review['approved'] = False
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'Root approval'):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_conflicting_body_acceptance_or_missing_pending_gate_rejected(self):
        for field, value in [('acceptedScopes', ['rigStructureOffline', 'bodyGeometry']),
                             ('pendingGates', sorted(PENDING_GATES - {'client'})), ('bodyRebindingAuthorized', True)]:
            invalid = copy.deepcopy(self.review)
            invalid[field] = value
            write(self.review_path, invalid)
            with self.assertRaises(ValueError):
                self.invoke()
            self.assertFalse(self.output.exists())

    def test_changed_model_bytes_rejected(self):
        model = self.source / 'runtime/ascii/pmg0.mdl'
        model.write_text(model.read_text() + '# changed\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'Pinned file differs'):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_consistent_contract_frame_edit_cannot_hide_unchanged_actual_model(self):
        self.data['rig']['frames']['working']['torso_g'][0][3] += .01
        self.data['rig']['frames']['runtime']['torso_g'][0][3] += .01 * self.factor
        write(self.contract_path, self.data)
        self.export['targetContractSha256'] = sha(self.contract_path)
        write(self.export_path, self.export)
        self.audit['targetContractSha256'] = sha(self.contract_path)
        self.audit['rigExportSha256'] = sha(self.export_path)
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'Actual exported bind frame differs'):
            self.invoke()

    def test_double_stature_conversion_and_nonunit_motion_are_rejected(self):
        self.data['rig']['frames']['runtime']['torso_g'][0][3] *= self.factor
        write(self.contract_path, self.data)
        with self.assertRaisesRegex(ValueError, 'conversion once'):
            self.invoke()

    def test_failed_structural_audit_or_missing_rotation_preservation_rejected(self):
        self.audit['verified'] = False
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'Successful independent'):
            self.invoke()
        self.audit['verified'] = True
        write(self.audit_path, self.audit)
        self.export['sourceRotationsTimingEventsUnchanged'] = False
        write(self.export_path, self.export)
        with self.assertRaisesRegex(ValueError, 'rotation/timing/event'):
            self.invoke()

    def test_missing_private_resource_or_socket_proof_rejected(self):
        valid = copy.deepcopy(self.export)
        self.export['models'].pop()
        write(self.export_path, self.export)
        self.audit['rigExportSha256'] = sha(self.export_path)
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'Complete exact'):
            self.invoke()
        write(self.export_path, valid)
        self.audit['rigExportSha256'] = sha(self.export_path)
        self.audit['sockets'].pop('impact')
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'socket audit missing'):
            self.invoke()

    def test_positional_bezier_evidence_requires_explicit_future_adapter(self):
        self.audit['positionBezierControllers'] = 1
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'Bezier proof requires a new adapter'):
            self.invoke()

    def test_missing_pause2_motion_or_reused_idle_evidence_rejected(self):
        self.review['motionEvidence'] = [row for row in self.review['motionEvidence'] if row['clip'] != 'pause2']
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'coverage incomplete'):
            self.invoke()
        self.audit['poseSamples'][1]['sourceClipSha256'] = self.audit['poseSamples'][0]['sourceClipSha256']
        write(self.audit_path, self.audit)
        with self.assertRaisesRegex(ValueError, 'distinct native source'):
            self.invoke()

    def test_motion_frame_scale_and_wrong_target_binding_rejected(self):
        entry = self.review['motionEvidence'][0]
        motion = json.loads(Path(entry['path']).read_text())
        motion['specimens'][0]['jointWorldMatrices']['torso_g'][0][0] = self.factor
        write(entry['path'], motion)
        entry['sha256'] = sha(entry['path'])
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'nonunit/doubled scale'):
            self.invoke()
        motion['specimens'][0]['jointWorldMatrices']['torso_g'][0][0] = 1
        motion['specimens'][0]['target']['rigRevision'] = 'different-rig'
        write(entry['path'], motion)
        entry['sha256'] = sha(entry['path'])
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'another target'):
            self.invoke()

    def test_existing_output_and_nested_historical_output_are_rejected(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, 'Fresh separate'):
            self.invoke()
        self.output = self.source / 'nested-new-rig'
        with self.assertRaisesRegex(ValueError, 'Fresh separate'):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_existing_root_pilot_is_validated_but_preparation_is_unapproved(self):
        path, _ = self.add_pilot_review()
        result = prepare(self.contract_path, self.export_path, self.audit_path, self.output, path)
        report = json.loads(result.read_text())
        self.assertTrue(report['pilotReviewVerified'])
        self.assertEqual(report['reviewedMotionCases'], 7)
        template = json.loads((self.output / 'root-review-template.unapproved.json').read_text())
        self.assertFalse(template['approved'])
        self.assertFalse(template['offlineMotionReviewed'])
        self.assertEqual(template['pendingIssues'], self.review['pendingIssues'])

    def test_failed_pilot_launch_cannot_become_structural_acceptance(self):
        path, pilot = self.add_pilot_review()
        entry = pilot['cases'][0]['launch']
        bad = json.loads(Path(entry['path']).read_text())
        bad['exitCode'] = 1
        write(entry['path'], bad)
        entry['sha256'] = sha(entry['path'])
        pilot['cases'][0]['preserved']['launch'] = entry
        write(path, pilot)
        self.review['pilotReview']['sha256'] = sha(path)
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'successful passed offline run'):
            self.invoke()
        self.assertFalse(self.output.exists())

    def test_changed_reviewed_image_and_lost_obligation_rejected(self):
        path, pilot = self.add_pilot_review()
        image = Path(pilot['cases'][0]['preserved']['images'][0]['path'])
        image.write_bytes(b'changed image fixture')
        with self.assertRaisesRegex(ValueError, 'Pinned file differs'):
            self.invoke()
        image.write_bytes(b'synthetic opaque image fixture')
        self.review['pendingIssues'] = ['Materials only, missing body obligations']
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'obligations and protected shapes'):
            self.invoke()

    def test_root_pilot_body_acceptance_scope_conflict_rejected(self):
        path, pilot = self.add_pilot_review()
        pilot['bodyGeometryAccepted'] = True
        write(path, pilot)
        self.review['pilotReview']['sha256'] = sha(path)
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'promoted a separate acceptance scope'):
            self.invoke()

    def test_relative_executed_preview_snapshot_binds_to_receipt_directory(self):
        preview = self.base / 'motion' / 'executed-preview.py'
        preview.write_text('# fixed synthetic executed preview\n', encoding='utf-8')
        for entry in self.review['motionEvidence']:
            path = Path(entry['path'])
            data = json.loads(path.read_text())
            data['codeSnapshot'] = preview.name
            data['codeSha256'] = sha(preview)
            write(path, data)
            entry['sha256'] = sha(path)
        write(self.review_path, self.review)
        self.add_pilot_review()
        state = inspect_source(self.contract_path, self.export_path, self.audit_path)
        verify_review(self.review_path, state, self.revision)
        preview.write_text('# changed preview\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Pinned file differs'):
            self.invoke()

    def test_pinned_root_pilot_review_cannot_be_removed_to_drop_obligations(self):
        self.review.pop('pilotReview')
        write(self.review_path, self.review)
        with self.assertRaisesRegex(ValueError, 'pilot review is mandatory'):
            self.invoke()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
