"""Two selected LEFT knee leaves, returned in working space without any bake.

Export permission does not select a leaf. Existing staging/mirror consumers and
their enums remain closed; downstream runtime conversion is a separate action.
"""
import json
from pathlib import Path
import struct

import numpy as np

import target_contract as tc
import diagnostic_knee_terminal_connectors as knee

CONFIG_KIND = 'target-knee-selected-working-leaf-config'
AUTHORITY_KIND = 'root-local-knee-working-continuation-selection'
RESULT_KIND = 'target-selected-working-knee-leaf'
TARGET_SHA = '65e25102a970193786a6c6bffd1b9e1ee15c9c0e323f4a83e17deb5e23e97c0a'
VERIFIER_SHA = 'ee53bf97a68e223973070b9da5c2f92f88cc6365a4031179c9257149e19cf26d'
OPERATION = 'same-topology-source-owned-local-knee-terminal-field'
SOURCES = {
    'shinl': ('target-part-diagnostic-rounded-upper-shin-connector',
              'c7de54a4940542f784367cf1acce1ddb9beec06c41ea4a9102cd2fb5647bd47c',
              '963833de87fbb105fd2589c3dddc092bd74b3c67d15a839b381979ae994be130',
              'a35441459fc33959bcd7607769ab8e55a5ac044ea7f67c6d1b0b7e8ce0843a71',
              [25828, 25932, 30336]),
    'legl': ('target-part-diagnostic-distal-thigh-ridge',
             'e4e2f31f7ccb8e24974da53984e9e7630f173f5798300839e0ef70dd9f097214',
             '6051c6884e15fb9bf12440a469eb4d973edf20d39e4dcaee8bc1b3574c6f94fe',
             '40982da484578aa11c631856d6ffa653b7895bcd7ec0290284c88b66abb52911',
             [37038]),
}
FLAGS = knee.FLAGS


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': tc.sha(path)}


def pinned(item, inputs):
    tc.require(isinstance(item, dict) and set(item) == {'path', 'sha256'} and
               isinstance(item['path'], str) and isinstance(item['sha256'], str),
               'Explicit exact path/hash pin required')
    path = Path(item['path']).resolve()
    tc.require(tc.sha(path) == item['sha256'], 'Changed input: ' + str(path))
    tc.require(str(path) not in inputs or inputs[str(path)] == item['sha256'], 'Conflicting input pin')
    inputs[str(path)] = item['sha256']
    return path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pending(row):
    tc.require(row.get('pendingGates') == {k: False for k in FLAGS} and
               all(row.get(k, False) is False for k in FLAGS),
               'Separate body/material/native/client/production gates stay false')


def validate_source(receipt, part, target_path, target, source_pin, candidate_pin):
    tc.require(part in SOURCES, 'Only the two exact current LEFT knee owners')
    kind, digest, candidate_digest, _, _ = SOURCES[part]
    tc.require(source_pin['sha256'] == digest and candidate_pin['sha256'] == candidate_digest and
               Path(receipt['candidate']).resolve() == Path(candidate_pin['path']).resolve() and
               receipt['candidateSha256'] == candidate_digest, 'Exact selected actual leaf and candidate')
    tc.verify_binding(receipt, target_path, target, 'working')
    pending(receipt)
    tc.require(receipt.get('schemaVersion') == 1 and receipt.get('kind') == kind and
               receipt.get('scope') == knee.SCOPE and receipt.get('operation') == OPERATION and
               receipt.get('part') == part and receipt.get('joint') == tc.PART_JOINTS[part] and
               receipt.get('model') == tc.model(target, part), 'Finite source/part/operation/model contract')
    tc.require(receipt.get('statureApplications') == 0 and receipt.get('fieldApplications') == 1 and
               receipt.get('parentFieldsReapplied') is False and receipt.get('rigOrNeighborsChanged') is False and
               receipt.get('diagnosticOnly') is True and receipt.get('canonicalNativeLineage') is False and
               receipt.get('attachmentAppliedOnce') is True and
               np.array_equal(receipt['candidateToAttachmentLocal'], np.eye(4)) and
               np.array_equal(receipt['attachmentWorld'], tc.frame(target, tc.PART_JOINTS[part], 'working')),
               'Working-only current leaf; no scale/fit/frame/ancestor replay')


def image_pin(item, inputs):
    path = pinned(item, inputs)
    with path.open('rb') as stream:
        header = stream.read(24)
    tc.require(len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and
               header[12:16] == b'IHDR' and min(struct.unpack_from('>II', header, 16)) > 0,
               'Literal nonempty PNG joint image required')
    return path


def validate_comparison(proof, evidence, part, source_pin, candidate_pin, archive_pin, inputs):
    """Consume the real four-view renderer proof, without inventing acceptance."""
    tc.require(proof.get('kind') == 'actual-matched-two-knee-owner-terminal-four-view-review' and
               proof.get('onlyTwoLeftOwnerChildrenDiffer') is True and proof.get('foot120Unchanged') is True and
               all(proof.get(k, False) is False for k in FLAGS), 'Finite actual literal comparison proof')
    clip, time = {'standing': ('pause1', 0.0), 'kneeling': ('kneel', 1.5)}[evidence['poseClass']]
    rows = proof.get('images', [])
    tc.require(isinstance(rows, list) and len(rows) == 4 and
               {(r.get('clip'), r.get('time'), r.get('variant')) for r in rows} ==
               {('pause1', 0.0, 'parents'), ('pause1', 0.0, 'terminalChildren'),
                ('kneel', 1.5, 'parents'), ('kneel', 1.5, 'terminalChildren')},
               'Exact standing/kneeling parent and child literal image rows')
    pair = {r['variant']: r for r in rows if r['clip'] == clip and r['time'] == time}
    parent, child = pair['parents'], pair['terminalChildren']
    tc.require(parent.get('image') == evidence['sourceImage'] and child.get('image') == evidence['childImage'] and
               parent.get('camera') == child.get('camera') and parent.get('sourcePose') == child.get('sourcePose') and
               isinstance(parent.get('heldFingerprints'), dict) and bool(parent['heldFingerprints']) and
               parent['heldFingerprints'] == child.get('heldFingerprints'),
               'Literal proof requires exact image variants, camera, pose and protected neighbors')
    for row in (parent, child):
        tc.require(row.get('sourceMaterialsMapsPreserved') is True and row.get('heldCurrentActorOriginalFoot120') is True and
                   row.get('fieldNotReapplied') is True and row.get('statureApplications') == 0,
                   'Actual source maps/foot/field/scale comparison invariants')
        camera = row.get('camera', {})
        tc.require(np.shape(camera.get('matrixWorld')) == (4, 4) and
                   np.shape(camera.get('projectionMatrix')) == (4, 4) and
                   np.isfinite(camera['matrixWorld']).all() and np.isfinite(camera['projectionMatrix']).all() and
                   isinstance(camera.get('orthoScale'), (int, float)) and camera['orthoScale'] > 0,
                   'Finite literal camera/projection')
        pinned(row['sourcePose'], inputs)
    portable_pin = child.get('actualChildRows', {}).get(part)
    portable = read(pinned(portable_pin, inputs))
    tc.require(portable.get('kind') == 'fully-validated-portable-local-knee-terminal-preview-row' and
               portable.get('part') == part and portable.get('receiptKind') == SOURCES[part][0] and
               portable.get('receipt') == source_pin['path'] and portable.get('receiptSha256') == source_pin['sha256'] and
               portable.get('candidate') == candidate_pin['path'] and portable.get('candidateSha256') == candidate_pin['sha256'] and
               portable.get('nativeCornerArchive') == archive_pin and
               parent.get('actualChildRows', {}).get(part) == portable_pin,
               'Exact literal proof portable receipt/candidate/archive owner association')
    imported = child.get('actualImportProof', {}).get(part, {})
    tc.require(imported.get('candidate') == candidate_pin and imported.get('maxPerror') == 0 and
               imported.get('maxUVerror') == 0 and imported.get('ordinaryDirectionBoundsPass') is True and
               imported.get('sourceAuthoredN_T_UVUnchanged') is True and
               imported.get('orderedCorners') == {'shinl': 149994, 'legl': 149967}[part],
               'Exact actual child import proof; no geometry/UV replay')


def validate_selection(authority, part, source_pin, candidate_pin, archive_pin, target_path, target, inputs):
    pending(authority)
    tc.verify_binding(authority, target_path, target, 'working')
    tc.require(authority.get('schemaVersion') == 1 and authority.get('kind') == AUTHORITY_KIND and
               authority.get('reviewedBy') == '/root' and authority.get('reviewed') is True and
               authority.get('selectedForWorkingContinuation') is True,
               'Explicit ROOT literal continuation selection; export permission is insufficient')
    rows = authority.get('selections', [])
    tc.require(isinstance(rows, list) and rows and len({r.get('part') for r in rows}) == len(rows) and
               all(r.get('part') in SOURCES for r in rows), 'Finite unique LEFT knee selection owners')
    chosen = [r for r in rows if r.get('part') == part]
    tc.require(len(chosen) == 1, 'Exact owner must be selected')
    row = chosen[0]
    tc.require(row.get('receipt') == source_pin and row.get('candidate') == candidate_pin and
               row.get('nativeCornerArchive') == archive_pin and row.get('selectedForWorkingContinuation') is True and
               row.get('noNewUnintendedShelvesObserved') is True and
               row.get('inheritedShadingDiagnosticSourceFaces') == SOURCES[part][4],
               'ROOT selection must bind exact receipt/candidate/archive and local no-shelf review')
    evidence = row.get('jointEvidence', [])
    tc.require(isinstance(evidence, list) and len(evidence) == 2 and
               {e.get('poseClass') for e in evidence} == {'standing', 'kneeling'},
               'Both source-matched standing and kneeling joint images required')
    for item in evidence:
        tc.require(item.get('reviewedBy') == '/root' and item.get('jointReviewPassed') is True and
                   item.get('sourceMatchedCameraAndNeighbors') is True, 'Actual paired ROOT joint review')
        source_image, child_image = item['sourceImage'], item['childImage']
        tc.require(source_image != child_image, 'Literal source and child comparison images must be distinct')
        image_pin(source_image, inputs)
        image_pin(child_image, inputs)
        proof = read(pinned(item['comparisonProof'], inputs))
        validate_comparison(proof, item, part, source_pin, candidate_pin, archive_pin, inputs)
    return row


def working_archive(item, triangles, inputs):
    tc.require(isinstance(triangles, int) and triangles > 0, 'Nonempty active source triangles required')
    path = pinned(item, inputs)
    with np.load(path, allow_pickle=False) as data:
        tc.require(all(not data[k].dtype.hasobject for k in data.files), 'No object archive arrays')
        rows = {k: data[k].copy() for k in data.files}
    required = {'positions', 'normals', 'tangents', 'uvNative', 'primitiveIds', 'sourceTriangleIds',
                'sourceCornerOrder', 'kneeTerminalParentPositions', 'kneeTerminalParentNormals', 'kneeTerminalParentTangents'}
    tc.require(required <= set(rows) and not any(k.startswith('runtime') for k in rows),
               'Current working float64 authority and literal knee ancestry; runtime parents rejected')
    P, N, T, UV = [rows[k] for k in ('positions', 'normals', 'tangents', 'uvNative')]
    tc.require(P.dtype == N.dtype == T.dtype == np.dtype('float64') and
               P.shape == N.shape == (triangles, 3, 3) and T.shape == (triangles, 3, 4) and
               UV.shape == (triangles, 3, 2) and all(np.isfinite(v).all() for v in (P, N, T, UV)) and
               (np.linalg.norm(N, axis=2) > 0).all() and (np.linalg.norm(T[..., :3], axis=2) > 0).all() and
               np.isin(T[..., 3], [-1, 1]).all(), 'Ordered active float64 P/N/T/UV basis required')
    tc.require(np.array_equal(rows['primitiveIds'], np.zeros(triangles, dtype=int)) and
               np.array_equal(rows['sourceTriangleIds'], np.arange(triangles)) and
               np.array_equal(rows['sourceCornerOrder'], np.tile([0, 1, 2], (triangles, 1))),
               'One source skin primitive with exact ordered corner lineage')
    for key, shape in [('kneeTerminalParentPositions', P.shape), ('kneeTerminalParentNormals', N.shape),
                       ('kneeTerminalParentTangents', T.shape)]:
        tc.require(rows[key].dtype == np.dtype('float64') and rows[key].shape == shape, 'Literal parent corner archive shape/type')
    for array in rows.values():
        array.flags.writeable = False
    return rows


def prepare(config_path):
    config_path = Path(config_path).resolve()
    c, inputs = read(config_path), {}
    tc.require(c.get('schemaVersion') == 1 and c.get('kind') == CONFIG_KIND and
               c.get('part') in SOURCES and c.get('coordinateSpace') == 'working' and
               c.get('statureApplications') == 0 and c.get('scaleOrFieldsPerformed') is False,
               'Explicit finite working-only knee adapter config')
    pending(c)
    authority_path = pinned(c.get('workingSelectionAuthority'), inputs)
    authority = read(authority_path)
    tp = pinned(c['targetContract'], inputs)
    tc.require(tc.sha(tp) == TARGET_SHA, 'Exact current frozen Troll target')
    target = tc.load(tp)
    tc.require(target['identity']['prefix'] == 'pmg0' and target['identity']['gender'] == 'male' and
               target['identity']['phenotype'] == 0 and target['identity']['raceId'] == 2 and
               target['rig']['pilotAcceptanceScope'] == 'offline-rig-structure', 'Frozen Troll male structural target')
    part = c['part']
    source_path = pinned(c['sourceLeaf'], inputs)
    r = read(source_path)
    candidate_pin = {'path': r['candidate'], 'sha256': r['candidateSha256']}
    candidate = pinned(candidate_pin, inputs)
    validate_source(r, part, tp, target, c['sourceLeaf'], candidate_pin)
    validate_selection(authority, part, c['sourceLeaf'], candidate_pin, r['nativeCornerArchive'], tp, target, inputs)
    verifier = pinned(c['sourceVerifier'], inputs)
    tc.require(verifier == Path(knee.__file__).resolve() and tc.sha(verifier) == VERIFIER_SHA, 'Exact full public knee verifier')
    expected = c.get('expectedAdapter')
    tc.require(isinstance(expected, dict) and Path(expected.get('path', '')).resolve() == Path(__file__).resolve(),
               'Exact executing named adapter')
    pinned(expected, inputs)
    audit_path = pinned(c['actualLeafEvidence'], inputs)
    audit = read(audit_path)
    tc.require(tc.sha(audit_path) == SOURCES[part][3] and audit.get('kind') ==
               'independent-raw-decoded-source-owned-local-knee-terminal-proof' and audit.get('passed') is True and
               audit.get('part') == part and audit.get('receipt') == c['sourceLeaf'] and audit.get('candidate') == candidate_pin,
               'Exact successful independent actual leaf proof')
    validated = knee.verify_receipt(source_path, tp, target, space='working')
    tc.require(validated['receipt'] == r and validated['candidate'].resolve() == candidate, 'Full public verifier source association')
    for path, digest in validated['inputs'].items():
        pinned({'path': path, 'sha256': digest}, inputs)
    inventory = validated['primitiveInventory']
    tc.require(len(inventory) == 1 and inventory[0]['primitive'] == 0 and inventory[0]['part'] == part,
               'Exact one-skin-primitive source inventory')
    archive = working_archive(r['nativeCornerArchive'], inventory[0]['faces'], inputs)
    inputs[str(config_path)] = tc.sha(config_path)
    for path, digest in inputs.items():
        tc.require(tc.sha(path) == digest, 'Source changed during preparation')
    return {'schemaVersion': 1, 'kind': RESULT_KIND, 'part': part, 'targetPath': tp, 'target': target,
            'receipt': r, 'candidate': candidate, 'inputs': inputs, 'primitiveInventory': inventory,
            'workingArchive': archive, 'archiveSource': r['nativeCornerArchive'],
            'archiveKeys': {'P': 'positions', 'N': 'normals', 'T': 'tangents', 'UV': 'uvNative'},
            'primitiveRoles': {0: 'skin'}, 'workingSelectionAuthority': ref(authority_path),
            'coordinateSpace': 'working', 'statureApplications': 0, 'scaleOrFieldsPerformed': False,
            'pendingGates': {k: False for k in FLAGS}, 'nativeTransportPolicySelected': False}
