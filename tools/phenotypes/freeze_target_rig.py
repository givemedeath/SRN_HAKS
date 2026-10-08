"""Prepare or explicitly freeze a byte-identical offline rig; never rebind parts."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil

import numpy as np

from retarget import nodes
from rig_controller_audit import world_frames
import target_contract as target

REQUIRED_CLIPS = {'pause1', 'pause2', 'walk', 'run', 'conjure1', 'kneel', 'deadfnt'}
PENDING_GATES = {'bodyGeometry', 'materials', 'equipment', 'client', 'production', 'nativeBounds', 'strideBehavior'}
SCOPE = 'rigStructureOffline'


def canonical_sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def immutable_structure(data):
    """Only review/revision/provenance fields may change during byte-copy freeze."""
    result = copy.deepcopy(data)
    result.pop('frozenInputs', None)
    result.pop('acceptance', None)
    result.pop('acceptanceMetadata', None)
    for name in ('revision', 'pilotAccepted', 'offlineStructureAccepted', 'pilotAcceptanceScope', 'frozenFrom'):
        result['rig'].pop(name, None)
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pin(path, expected, pins):
    path = Path(path).resolve()
    target.require(re.fullmatch(r'[0-9a-f]{64}', expected or ''), 'Explicit SHA256 required: ' + str(path))
    target.require(path.is_file() and target.sha(path) == expected, 'Pinned file differs: ' + str(path))
    target.require(str(path) not in pins or pins[str(path)] == expected, 'Conflicting dependency pin')
    pins[str(path)] = expected
    return path


def verify_map(mapping, pins):
    target.require(type(mapping) is dict, 'Explicit pinned dependency map required')
    for name, digest in mapping.items():
        pin(name, digest, pins)


def pending_only(data):
    target.require(data['rig'].get('pilotAccepted') is False, 'Source rig is already accepted/frozen')
    target.require(data.get('productionAccepted') is False and data.get('clientAccepted') is False,
                   'Production/client scope must remain pending')
    target.require(data['equipment'].get('profilesAccepted') is False, 'Equipment acceptance is a separate pending gate')
    if 'acceptance' in data:
        target.require(all(value is False for value in data['acceptance'].values()), 'Conflicting source acceptance scopes')


def inspect_source(contract_path, export_path, audit_path):
    contract_path, export_path, audit_path = [Path(value).resolve() for value in (contract_path, export_path, audit_path)]
    data = target.load(contract_path)
    pending_only(data)
    export, audit, pins = read(export_path), read(audit_path), {}
    for path in [contract_path, export_path, audit_path]:
        pin(path, target.sha(path), pins)
    target.require(export.get('schemaVersion') == 2 and export.get('kind') == 'target-rig-export', 'Version 2 rig export required')
    target.require(export['targetContractSha256'] == pins[str(contract_path)], 'Export contract binding differs')
    target.require(export.get('geometryScaleAppliedOnce') is True and export.get('sourceRotationsTimingEventsUnchanged') is True,
                   'Single-scale and unchanged rotation/timing/event export proof required')
    target.require(export.get('generationPoseInputs') is False and export.get('clientAccepted') is False,
                   'Stock-derived offline export scope required')
    verify_map(data['frozenInputs'], pins)
    verify_map(export['sourceInputs'], pins)
    target.require(export.get('exportHelpers'), 'Pinned rig export helper closure required')
    pin(export['python']['executable'], export['python']['sha256'], pins)
    target.require(export['sourceInputs'] == data['frozenInputs'], 'Export source dependency closure differs from contract')
    for entry in export.get('originalInputs', {}).values():
        pin(entry['snapshot'], entry['sha256'], pins)
    for name, digest in export.get('exportHelpers', {}).items():
        target.require(Path(name).name == name, 'Export helper name must be a basename')
        pin(contract_path.parent / 'source-inputs/tools' / name, digest, pins)
    target.require(audit.get('schemaVersion') == 1 and audit.get('kind') == 'target-rig-independent-audit' and
                   audit.get('verified') is True, 'Successful independent structural audit required')
    target.require(audit['targetContractSha256'] == pins[str(contract_path)] and
                   audit['rigExportSha256'] == pins[str(export_path)], 'Independent audit binding differs')
    target.require(audit.get('sourceNativeFilesChecked', 0) > 0 and audit.get('nonunitGeometryNodeScales') == 0,
                   'Native source closure and unit geometry-node scales required')
    target.require(audit.get('positionBezierControllers') == 0,
                   'Freeze supports the audited no-positional-Bezier chain; encoded Bezier proof requires a new adapter')
    for name in ('clientEvidence', 'pilotAccepted', 'nativeBoundsAccepted', 'strideBehaviorAccepted'):
        target.require(audit.get(name) is False, 'Independent offline scope differs: ' + name)
    target.require(audit.get('auditHelpers'), 'Pinned independent audit helper closure required')
    verify_map(audit['auditHelpers'], pins)
    target.require(Path(audit['python']['executable']).resolve() == Path(export['python']['executable']).resolve(),
                   'Independent audit Python executable differs from pinned export dependency')
    aliases = data['rig']['privateAliases']
    target.require(len(aliases) == len(set(aliases.values())) and data['rig']['sourcePrefix'] in aliases,
                   'Unique private rig model aliases required')
    expected = {(space, source, model) for space in ('working', 'runtime') for source, model in aliases.items()}
    rows = export['models']
    target.require(len(rows) == len(expected) and {(row['space'], row['source'], row['model']) for row in rows} == expected,
                   'Complete exact working/runtime private model closure required')
    model_paths, manifest = {}, {}
    for row in rows:
        target.require(re.fullmatch(r'[a-z0-9_]{1,16}', row['model']), 'Invalid private model resource name')
        path = contract_path.parent / row['space'] / 'ascii' / (row['model'] + '.mdl')
        pin(path, row['sha256'], pins)
        model_paths[(row['space'], row['model'])] = path
        manifest[row['space'] + '/' + row['model']] = row['sha256']
    target.require(set(audit['spaces']) == {'working', 'runtime'}, 'Both independent coordinate-space audits required')
    for space in ('working', 'runtime'):
        summary = audit['spaces'][space]
        records = summary['models']
        target.require(len(records) == len(aliases) and {(row['source'], row['target']) for row in records} == set(aliases.items()),
                       'Independent model ownership inventory differs')
        for row in records:
            exported = next(value for value in rows if value['space'] == space and value['model'] == row['target'])
            target.require(row['sha256'] == exported['sha256'] and row['clipCount'] == exported['clipCount'],
                           'Independent model bytes/clip ownership differ')
        target.require(summary['clips'] == sum(row['clipCount'] for row in records) and summary['clips'] > 0 and
                       summary['nodes'] > 0 and summary['positionKeyRows'] > 0 and summary['rotationKeyRows'] > 0,
                       'Nonempty controller audit and exact clip totals required')
        for field, limit in [('maxParentBasisError', 1e-6), ('maxPositionError', 1e-9)]:
            error = summary[field]
            target.require(np.isfinite(error) and 0 <= error <= limit, 'Independent error exceeds existing tolerance: ' + field)
        root_alias = aliases[data['rig']['sourcePrefix']]
        root = nodes(model_paths[(space, root_alias)].read_text(encoding='ascii').split('endmodelgeom', 1)[0])
        frames = world_frames(root)
        for joint, matrix in data['rig']['frames'][space].items():
            alias = aliases.get(joint, joint)
            target.require(alias in frames and np.allclose(frames[alias], matrix, atol=1e-9, rtol=0),
                           'Actual exported bind frame differs from contract: ' + space + '/' + joint)
    pose_rows = audit['poseSamples']
    target.require(len({row['clip'] for row in pose_rows}) == len(pose_rows) and REQUIRED_CLIPS <= {row['clip'] for row in pose_rows},
                   'Separate idle, locomotion, casting, kneel and death structural samples required')
    clip_pins = {row['clip']: row['sourceClipSha256'] for row in pose_rows}
    target.require(clip_pins['pause1'] != clip_pins['pause2'], 'PAUSE1/PAUSE2 must have distinct native source evidence')
    for row in pose_rows:
        target.require(re.fullmatch(r'[0-9a-f]{64}', row['sourceClipSha256']) and len(row['samples']) >= 9,
                       'Pinned nine-point motion sampling required')
        for sample in row['samples']:
            error = sample['maxWorldScaleError']
            target.require(np.isfinite(error) and 0 <= error <= 1e-9, 'Sampled motion scaling proof failed')
    target.require(set(audit.get('sockets', {})) >= {'rhand', 'lhand', 'head', 'headconjure', 'handconjure', 'impact', 'wings', 'cloak_g', 'tail'},
                   'Required auxiliary socket audit missing')
    for row in audit['sockets'].values():
        target.require(np.allclose(row['runtimePosition'], np.asarray(row['workingPosition']) * data['rig']['runtimeScale'], atol=1e-9, rtol=0),
                       'Socket stature conversion differs')
    target.require(audit['strideMetadata']['runtimeScale'] == data['rig']['runtimeScale'] and
                   audit['strideMetadata']['tableWalkRunCollisionValuesAccepted'] is False,
                   'Engine movement acceptance must remain separate')
    return {'contractPath': contract_path, 'exportPath': export_path, 'auditPath': audit_path,
            'contract': data, 'export': export, 'audit': audit, 'pins': pins, 'modelPaths': model_paths,
            'expectedModels': manifest, 'structureSha256': canonical_sha(immutable_structure(data))}


def verify_motion(entry, state):
    pins, data = state['pins'], state['contract']
    path = pin(entry['path'], entry['sha256'], pins)
    comparison = read(path)
    specimens = [row for row in comparison['specimens'] if row.get('target')]
    target.require(len(specimens) == 1, 'Exactly one reviewed target motion specimen required')
    specimen = specimens[0]
    target.verify_binding(specimen['target'], state['contractPath'], data, 'working')
    target.require(specimen['clip'] == entry['clip'] and specimen.get('clientAccepted') is False and
                   specimen.get('clientEvidence') is False and specimen['displayScale'] == 1,
                   'Reviewed unscaled offline clip binding differs')
    target.require(np.isfinite(specimen['time']) and 0 <= specimen['time'] <= specimen['length'], 'Invalid sampled motion time')
    root_model = data['rig']['privateAliases'][data['rig']['sourcePrefix']]
    target.require(specimen['rootSha256'] == state['expectedModels']['working/' + root_model], 'Reviewed motion root bytes differ')
    pin(specimen['rootFile'], specimen['rootSha256'], pins)
    pin(specimen['file'], specimen['sha256'], pins)
    target.require(specimen['sha256'] in {digest for name, digest in state['expectedModels'].items() if name.startswith('working/')},
                   'Reviewed working motion owner not in working rig model closure')
    for row in specimen['sourceInheritance']:
        target.require(row['sha256'] == state['expectedModels']['working/' + row['model']], 'Motion inheritance model differs')
        pin(row['file'], row['sha256'], pins)
    verify_map(specimen['partInputs'], pins)
    for row in specimen['targetPartReceipts']:
        receipt_path = pin(row['receipt'], row['receiptSha256'], pins)
        target.verify_binding(read(receipt_path), state['contractPath'], data, 'working')
        pin(row['candidate'], row['candidateSha256'], pins)
    for name, row in comparison.get('importedHelperSnapshots', {}).items():
        pin(row['snapshot'], row['sha256'], pins)
    for name, digest in specimen.get('samplerHelperInputs', {}).items():
        snapshot = comparison.get('importedHelperSnapshots', {}).get(name)
        if snapshot is not None:
            target.require(snapshot['sha256'] == digest, 'Motion sampler snapshot binding differs')
            pin(snapshot['snapshot'], digest, pins)
        else:
            pin(name, digest, pins)
    if comparison.get('codeSnapshot'):
        snapshot_path = Path(comparison['codeSnapshot'])
        if not snapshot_path.is_absolute():
            snapshot_path = path.parent / snapshot_path
        pin(snapshot_path, comparison['codeSha256'], pins)
    for joint in target.PART_JOINTS.values():
        frame = np.asarray(specimen['jointWorldMatrices'][joint])
        target.require(frame.shape == (4, 4) and np.isfinite(frame).all() and np.allclose(frame[3], [0, 0, 0, 1], atol=1e-12, rtol=0),
                       'Invalid reviewed motion frame')
        target.require(np.allclose(frame[:3, :3].T @ frame[:3, :3], np.eye(3), atol=1e-8, rtol=0) and
                       abs(np.linalg.det(frame[:3, :3]) - 1) <= 1e-8, 'Motion contains nonunit/doubled scale or reflection')


def verify_review(review_path, state, revision):
    path = Path(review_path).resolve()
    review = read(path)
    target.require(review.get('schemaVersion') == 1 and review.get('kind') == 'offline-rig-root-review', 'Explicit root review declaration required')
    target.require(review.get('reviewedBy') == 'root' and review.get('approved') is True and
                   review.get('decision') == 'freeze-offline-rig-structure', 'Root approval of offline structure required')
    target.require(review.get('acceptedScopes') == [SCOPE] and set(review.get('pendingGates', [])) == PENDING_GATES,
                   'Conflicting acceptance scopes or missing pending gates')
    target.require(review.get('geometryChangesAuthorized') is False and review.get('bodyRebindingAuthorized') is False,
                   'Freeze never edits geometry or rebinds body receipts')
    target.require(review.get('offlineMotionReviewed') is True and review.get('pendingIssues') and review.get('protectedUserShapePreferences'),
                   'Explicit motion review, unresolved issues and protected user shape preferences required')
    target.require(review.get('requestedRevision') == revision and re.fullmatch(r'[a-z0-9-]+', revision or '') and
                   revision != state['contract']['rig']['revision'], 'Explicit distinct reviewed rig revision required')
    for key, selected in [('sourceContract', state['contractPath']), ('sourceExport', state['exportPath']), ('independentAudit', state['auditPath'])]:
        entry = review[key]
        target.require(Path(entry['path']).resolve() == selected and entry['sha256'] == state['pins'][str(selected)],
                       'Root review source binding differs: ' + key)
    target.require(review.get('expectedStructureSha256') == state['structureSha256'] and
                   review.get('expectedModels') == state['expectedModels'], 'Root reviewed frames/models changed')
    motion = review.get('motionEvidence', [])
    target.require(motion and REQUIRED_CLIPS <= {row['clip'] for row in motion}, 'Root reviewed motion coverage incomplete')
    target.require(len({row['path'] for row in motion}) == len(motion), 'Duplicate motion evidence path')
    for entry in motion:
        verify_motion(entry, state)
    target.require(type(review.get('pilotReview')) is dict, 'Pinned root pilot review is mandatory for freeze')
    pilot = verify_pilot_review(review['pilotReview'], state)
    target.require(review['pendingIssues'] == pilot['remainingIssues'] and
                   review['protectedUserShapePreferences'] == pilot['userApprovals'],
                   'Root pilot outstanding obligations and protected shapes must be retained exactly')
    for entry in review.get('supportingEvidence', []):
        evidence = read(pin(entry['path'], entry['sha256'], state['pins']))
        target.require(entry.get('acceptanceScope') == 'pending' and evidence.get('kind') == entry['kind'],
                       'Supporting evidence must not promote separate acceptance scopes')
    pin(path, target.sha(path), state['pins'])
    return review


def verify_pilot_review(entry, state):
    """Verify the pinned existing root review without turning it into approval."""
    path = pin(entry['path'], entry['sha256'], state['pins'])
    pilot = read(path)
    target.require(pilot.get('schemaVersion') == 1 and pilot.get('kind') == 'root-offline-troll-pilot-review' and
                   pilot.get('offlineBindStructureReviewPassed') is True, 'Successful explicit root offline pilot review required')
    target.require(Path(pilot['targetContract']['path']).resolve() == state['contractPath'] and
                   pilot['targetContract']['sha256'] == state['pins'][str(state['contractPath'])], 'Pilot review source binding differs')
    for field in ('rigPilotAccepted', 'bodyGeometryAccepted', 'materialAccepted', 'equipmentAccepted', 'clientAccepted', 'productionAccepted'):
        target.require(pilot.get(field) is False, 'Pilot review promoted a separate acceptance scope: ' + field)
    target.require(pilot.get('remainingIssues') and pilot.get('userApprovals'), 'Pending obligations and user preferences required')
    pin(pilot['batch']['path'], pilot['batch']['sha256'], state['pins'])
    for entry in pilot['parts'].values():
        part = read(pin(entry['path'], entry['sha256'], state['pins']))
        target.verify_binding(part, state['contractPath'], state['contract'], 'working')
    cases = pilot['cases']
    target.require(REQUIRED_CLIPS <= {row['clip'] for row in cases} and len({row['key'] for row in cases}) == len(cases),
                   'Root pilot motion coverage incomplete or duplicated')
    for row in cases:
        verify_motion({**row['comparison'], 'clip': row['clip']}, state)
        comparison = read(row['comparison']['path'])
        specimen = next(value for value in comparison['specimens'] if value.get('target'))
        selected_parts = {value['part']: value for value in specimen['targetPartReceipts']}
        for part, entry in pilot['parts'].items():
            target.require(part in selected_parts and selected_parts[part]['receiptSha256'] == entry['sha256'],
                           'Pilot motion uses another reviewed body receipt')
        launch = read(pin(row['launch']['path'], row['launch']['sha256'], state['pins']))
        target.require(launch.get('kind') == 'verified-shared-tool-launch' and launch.get('exitCode') == 0 and
                       launch.get('tool') == 'blender' and launch.get('gameClientTesting') is False and
                       launch.get('preMigrationSmoke') is False, 'Pilot motion launch was not a successful passed offline run')
        verify_map(launch['frozenInputs'], state['pins'])
        for name in ('comparison', 'launch'):
            saved = row['preserved'][name]
            target.require(saved['sha256'] == row[name]['sha256'], 'Preserved pilot evidence bytes differ')
            pin(saved['path'], saved['sha256'], state['pins'])
        target.require(len(row['preserved']['images']) >= len(row['views']), 'Missing reviewed pilot view images')
        for image in row['preserved']['images']:
            pin(image['path'], image['sha256'], state['pins'])
    # These proofs retain their own original acceptance scopes and cannot waive body/material gates.
    for name in ('widerNwstabComparison', 'connectorReview', 'nativePilot'):
        if pilot.get(name):
            pin(pilot[name]['path'], pilot[name]['sha256'], state['pins'])
    if pilot.get('connectorReview'):
        connector = read(pilot['connectorReview']['path'])
        target.verify_binding(connector['target'], state['contractPath'], state['contract'], 'working')
        target.require(connector.get('rigOrBindChangeRequiredByThisEvidence') is False and
                       connector.get('clientAccepted') is False and connector.get('productionAccepted') is False,
                       'Connector evidence conflicts with offline-only unchanged-bind review')
        verify_map(connector['frozenInputs'], state['pins'])
    return pilot


def snapshot_helpers(output):
    directory = output / 'helper-snapshots'
    directory.mkdir()
    pins = {}
    for name in ('freeze_target_rig.py', 'target_contract.py', 'retarget.py', 'rig_controller_audit.py'):
        path = directory / name
        shutil.copyfile(Path(__file__).with_name(name), path)
        pins[str(path.resolve())] = target.sha(path)
    return pins


def prepare(contract_path, export_path, audit_path, output, pilot_review=None):
    state = inspect_source(contract_path, export_path, audit_path)
    pilot = None
    if pilot_review is not None:
        pilot_entry = {'path': str(Path(pilot_review).resolve()), 'sha256': target.sha(pilot_review)}
        pilot = verify_pilot_review(pilot_entry, state)
    output = Path(output).resolve()
    target.require(not output.exists(), 'Fresh diagnostic preparation directory required')
    output.mkdir(parents=True)
    helpers = snapshot_helpers(output)
    template = {'schemaVersion': 1, 'kind': 'offline-rig-root-review', 'reviewedBy': 'root', 'approved': False,
                'decision': 'freeze-offline-rig-structure', 'acceptedScopes': [], 'pendingGates': sorted(PENDING_GATES),
                'geometryChangesAuthorized': False, 'bodyRebindingAuthorized': False, 'offlineMotionReviewed': False,
                'requestedRevision': None, 'expectedStructureSha256': state['structureSha256'], 'expectedModels': state['expectedModels'],
                'pilotReview': None, 'motionEvidence': [], 'supportingEvidence': [], 'pendingIssues': [], 'protectedUserShapePreferences': []}
    for key, path in [('sourceContract', state['contractPath']), ('sourceExport', state['exportPath']), ('independentAudit', state['auditPath'])]:
        template[key] = {'path': str(path), 'sha256': state['pins'][str(path)]}
    if pilot is not None:
        template['pilotReview'] = pilot_entry
        template['motionEvidence'] = [{**row['comparison'], 'clip': row['clip']} for row in pilot['cases']]
        template['pendingIssues'] = pilot['remainingIssues']
        template['protectedUserShapePreferences'] = pilot['userApprovals']
    template_path = output / 'root-review-template.unapproved.json'
    template_path.write_text(json.dumps(template, indent=2) + '\n', encoding='utf-8')
    report = {'schemaVersion': 1, 'kind': 'offline-rig-freeze-preparation', 'createdUtc': datetime.now(timezone.utc).isoformat(),
              'sourceContract': str(state['contractPath']), 'sourceContractSha256': target.sha(state['contractPath']),
              'sourceRevision': state['contract']['rig']['revision'], 'structuralEvidenceVerified': True,
              'expectedStructureSha256': state['structureSha256'], 'expectedModels': state['expectedModels'],
              'requiredReviewScope': SCOPE, 'requiredMotionClips': sorted(REQUIRED_CLIPS), 'pendingGates': sorted(PENDING_GATES),
              'rootReviewTemplate': {'path': str(template_path), 'sha256': target.sha(template_path)},
              'pilotReviewVerified': pilot is not None, 'reviewedMotionCases': len(pilot['cases']) if pilot else 0,
              'frozenInputs': state['pins'], 'helperSnapshots': helpers,
              'contractCreated': False, 'modelsCopied': False, 'rigFrozen': False, 'bodyReceiptsRebound': False,
              'ledgerChanged': False, 'clientAccepted': False, 'productionAccepted': False,
              'policy': 'Preparation is not approval. An explicit root declaration and freeze invocation are required. Source rig, frames, aliases and model bytes remain immutable; every existing body/equipment receipt stays bound to the original contract until separately reviewed rebinding.',
              'api': {'prepare': 'prepare(contract_path, export_path, audit_path, output, pilot_review=None)',
                      'freeze': 'freeze(contract_path, export_path, audit_path, review_path, output, revision)',
                      'sourceInputsCopied': 'Pinned source-inputs closure, byte-for-byte, retaining relative paths',
                      'modelInputsCopied': 'Complete working/runtime private model closure, byte-for-byte, zero scale applications',
                      'legacyPilotBoolean': 'True only with pilotAcceptanceScope=offline-rig-structure; material/body/equipment/client/production gates remain false'}}
    path = output / 'preparation.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (output / 'README.md').write_text(
        '# Offline rig freeze preparation\n\n'
        'Structural export/audit pins and actual root bind frames have been verified. No rig has been frozen or copied.\n\n'
        'Root must create a fresh approved review declaration from the unapproved template, choose a distinct revision, '
        'list pinned reviewed motion comparisons covering PAUSE1, PAUSE2, walking, running, casting, kneeling and death, '
        'and retain all listed pending gates/issues and user shape protections. Only then may root invoke freeze.\n\n'
        'Freeze copies existing working/runtime models and source snapshots byte-for-byte; it performs no transform, scaling or model recompilation. '
        'It writes a new contract and freshly bound export plus a provenance receipt. The legacy pilot boolean means offline rig structure only; '
        'body geometry, materials, equipment, native bounds, stride behavior, client and production acceptance remain pending. '
        'Existing body receipts are not automatically compatible with the new hash/revision and are never rewritten by this helper.\n', encoding='utf-8')
    return path


def freeze(contract_path, export_path, audit_path, review_path, output, revision):
    state = inspect_source(contract_path, export_path, audit_path)
    review = verify_review(review_path, state, revision)
    output = Path(output).resolve()
    source_root = state['contractPath'].parent
    target.require(not output.exists() and not output.is_relative_to(source_root) and not source_root.is_relative_to(output),
                   'Fresh separate rig output required; original rig is immutable')
    # Validate every source before creating anything; partial copies never carry a completed contract.
    for name, digest in state['pins'].items():
        pin(name, digest, {})
    output.mkdir(parents=True)
    copied, closure, model_copies = {}, {}, []
    source_snapshots = source_root / 'source-inputs'
    for name, digest in state['contract']['frozenInputs'].items():
        original = Path(name).resolve()
        if original.is_relative_to(source_snapshots):
            destination = output / 'source-inputs' / original.relative_to(source_snapshots)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
            target.require(target.sha(destination) == digest, 'Copied source bytes differ')
            copied[name] = str(destination)
            closure[str(destination)] = digest
        else:
            closure[name] = digest
    for (space, model), original in state['modelPaths'].items():
        destination = output / space / 'ascii' / (model + '.mdl')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        digest = state['expectedModels'][space + '/' + model]
        target.require(target.sha(destination) == digest, 'Copied rig model bytes differ')
        closure[str(destination)] = digest
        model_copies.append({'space': space, 'model': model, 'source': str(original), 'destination': str(destination), 'sha256': digest})
    evidence_directory = output / 'freeze-evidence'
    evidence_directory.mkdir()
    for name, original in [('source-contract.json', state['contractPath']), ('source-rig-export.json', state['exportPath']),
                           ('source-independent-audit.json', state['auditPath']), ('root-review.json', Path(review_path).resolve())]:
        destination = evidence_directory / name
        shutil.copyfile(original, destination)
        closure[str(destination)] = target.sha(destination)
    helpers = snapshot_helpers(output)
    closure.update(helpers)
    # Pinned supporting inputs remain recoverable history; no body or image masters are duplicated or rewritten.
    for name, digest in state['pins'].items():
        if name not in copied:
            closure[name] = digest
    result = copy.deepcopy(state['contract'])
    result['rig'].update({'revision': revision, 'pilotAccepted': True, 'offlineStructureAccepted': True,
                          'pilotAcceptanceScope': 'offline-rig-structure',
                          'frozenFrom': {'targetContract': str(state['contractPath']), 'sha256': target.sha(state['contractPath']),
                                         'revision': state['contract']['rig']['revision'], 'structureSha256': state['structureSha256']}})
    result['acceptance'] = {SCOPE: True, **{name: False for name in sorted(PENDING_GATES)}}
    result['acceptanceMetadata'] = {'scope': 'offline-rig-structure-only', 'pendingIssues': review['pendingIssues'],
                                    'protectedUserShapePreferences': review['protectedUserShapePreferences'],
                                    'bodyResourceRebinding': 'Requires fresh fit/mirror/exterior-repair receipts reproducing selected bytes under this contract; historical v6 receipts remain incompatible.',
                                    'rootReview': {'path': str(Path(review_path).resolve()), 'sha256': target.sha(review_path)}}
    result['frozenInputs'] = closure
    target.require(immutable_structure(result) == immutable_structure(state['contract']), 'Rig structure/frames/identity changed during freeze')
    target.validate(result)
    for name, digest in state['pins'].items():
        pin(name, digest, {})
    contract_destination = output / 'target-contract.json'
    contract_destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    target.load(contract_destination)
    export = copy.deepcopy(state['export'])
    export['targetContractSha256'] = target.sha(contract_destination)
    export['sourceInputs'] = closure
    export['targetContract'] = str(contract_destination)
    export['rigRevision'] = revision
    export['parentRigExport'] = {'path': str(state['exportPath']), 'sha256': target.sha(state['exportPath'])}
    export['operation'] = 'byte-identical-offline-rig-freeze'
    export['scaleApplicationsDuringFreeze'] = 0
    export['rigStructureOfflineAccepted'] = True
    export['acceptance'] = result['acceptance']
    export_path_new = output / 'rig-export.json'
    export_path_new.write_text(json.dumps(export, indent=2) + '\n', encoding='utf-8')
    receipt = {'schemaVersion': 1, 'kind': 'offline-rig-freeze', 'createdUtc': datetime.now(timezone.utc).isoformat(),
               'target': target.binding(contract_destination, result, 'working'), 'coordinateSpaces': ['working', 'runtime'],
               'sourceContract': str(state['contractPath']), 'sourceContractSha256': target.sha(state['contractPath']),
               'rootReview': {'path': str(Path(review_path).resolve()), 'sha256': target.sha(review_path)},
               'structureSha256': state['structureSha256'], 'modelCopies': model_copies, 'sourceSnapshotCopies': copied,
               'newExport': {'path': str(export_path_new), 'sha256': target.sha(export_path_new)},
               'independentEvidenceInheritedByExactBytes': True, 'scaleApplicationsDuringFreeze': 0,
               'rigStructureOfflineAccepted': True, 'bodyGeometryAccepted': False, 'materialsAccepted': False,
               'equipmentAccepted': False, 'nativeBoundsAccepted': False, 'strideBehaviorAccepted': False,
               'clientAccepted': False, 'productionAccepted': False, 'bodyReceiptsRebound': False, 'ledgerChanged': False,
               'pendingIssues': review['pendingIssues'], 'protectedUserShapePreferences': review['protectedUserShapePreferences'],
               'frozenInputs': state['pins'], 'helperSnapshots': helpers,
               'compatibility': 'Existing fits/stages/equipment/preview receipts retain the original hash/revision. Byte-identical geometry does not authorize silently rebinding or accepting them.'}
    destination = output / 'freeze.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('prepare', 'freeze'), default='prepare')
    for name in ('contract', 'export', 'audit', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--revision')
    parser.add_argument('--pilot-review', type=Path)
    args = parser.parse_args()
    if args.mode == 'freeze':
        target.require(args.review is not None and args.revision, 'Explicit root review and revision required for freeze')
        target.require(args.pilot_review is None, 'Freeze consumes pilot review only through pinned explicit root declaration')
        result = freeze(args.contract, args.export, args.audit, args.review, args.output, args.revision)
    else:
        target.require(args.review is None and args.revision is None, 'Preparation never consumes approval or revision')
        result = prepare(args.contract, args.export, args.audit, args.output, args.pilot_review)
    print(json.dumps({'mode': args.mode, 'receipt': str(result), 'sha256': target.sha(result)}))


if __name__ == '__main__':
    main()
