"""Read-only, explicitly reviewed working pelvis diagnostic lineage for previews.

This separate kind never supplies canonical geometry/material/native lineage.
No geometry is transformed, compacted, normalized, staged or written here.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

import target_contract as contract
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, read_glb
from target_part_pipeline import generation_source, verify_source_receipt

KIND = 'target-part-diagnostic-geometry'
OPERATION = 'bounded-pelvis-index-diagnostic'
SCOPE = 'bounded-diagnostic-lineage-preview-only'
PREVIEW_SCOPE = 'offline-target-pelvis-geometry-review'
ROLES = {'0': 'unpartitioned-original-skin-and-underwear',
         '1': 'unowned-neutral-diagnostic-cap', '2': 'unowned-neutral-diagnostic-cap'}
FLAGS = ('closedExteriorClaim', 'geometryAccepted', 'anatomyAccepted', 'collisionAccepted',
         'materialAccepted', 'capOwnershipAccepted', 'clothBoundaryAccepted',
         'stagingAccepted', 'nativeAccepted', 'clientAccepted', 'productionAccepted', 'selectionMade')
SEMANTICS = ('POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT')
ARCHIVE_KEYS = set(SEMANTICS) | {'materialIds', 'primitiveIds', 'sourceOriginalFaceIds'}
EVIDENCE = ('proposal', 'proposalText', 'childDiagnostic', 'boundedConnectorParent',
            'properTargetFit', 'fitCandidate', 'originalSource', 'generationReceipt',
            'childMapping', 'parentMapping', 'properFitFloat64CornerArchive',
            'independentDecode', 'parentIndependentAudit', 'selectedFourFaceProposal',
            'capLeftGenerator', 'capRightGenerator', 'remainingDefects')


def fingerprint(value):
    value = np.ascontiguousarray(value)
    return {'dtype': str(value.dtype), 'shape': list(value.shape),
            'sha256': hashlib.sha256(value.tobytes()).hexdigest()}


def no_acceptance(value):
    """A preview declaration cannot smuggle broader acceptance in nested metadata."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith('Accepted') or key in ('closedExteriorClaim', 'selectionMade'):
                contract.require(child is False, 'Diagnostic acceptance must remain false: '+key)
            no_acceptance(child)
    elif isinstance(value, list):
        for child in value: no_acceptance(child)


def pin(item, inputs):
    contract.require(isinstance(item, dict) and isinstance(item.get('path'), str) and
                     isinstance(item.get('sha256'), str), 'Explicit evidence path/hash required')
    path = Path(item['path']).resolve()
    contract.require(path.is_file() and contract.sha(path) == item['sha256'],
                     'Diagnostic evidence changed: '+str(path))
    inputs[str(path)] = item['sha256']
    return path


def load_item(item, inputs):
    return json.loads(pin(item, inputs).read_text(encoding='utf-8'))


def load_archive(item, inputs):
    with np.load(pin(item, inputs), allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def verify_preserved_child(doc, binary, parent_doc, parent_binary, keep):
    """An index-only child must preserve the complete original storage prefix."""
    contract.require(binary[:len(parent_binary)] == parent_binary,
                     'Original stored BIN prefix changed, including inactive rows')
    contract.require(len(doc['accessors']) == len(parent_doc['accessors'])+1 and
                     doc['accessors'][:-1] == parent_doc['accessors'] and
                     len(doc['bufferViews']) == len(parent_doc['bufferViews'])+1 and
                     doc['bufferViews'][:-1] == parent_doc['bufferViews'],
                     'Only one index accessor/view append is supported')
    contract.require(len(doc.get('meshes', [])) == len(parent_doc.get('meshes', [])) == 1,
                     'One detached mesh required')
    primitives = doc['meshes'][0]['primitives']; previous = parent_doc['meshes'][0]['primitives']
    contract.require(len(primitives) == len(previous) == 3 and primitives[1:] == previous[1:],
                     'Both cap primitives must remain literal copies')
    body = dict(primitives[0]); old_body = dict(previous[0])
    new_index = body.pop('indices'); old_index = old_body.pop('indices')
    contract.require(body == old_body and new_index == len(parent_doc['accessors']),
                     'Body ownership/attributes changed or new index accessor is not appended')
    contract.require(np.array_equal(accessor(doc, binary, new_index).reshape(-1, 3),
                                   accessor(parent_doc, parent_binary, old_index).reshape(-1, 3)[keep]),
                     'Body indices do not remove only the reviewed four faces')
    old_mesh = dict(parent_doc['meshes'][0]); new_mesh = dict(doc['meshes'][0])
    old_mesh.pop('primitives'); new_mesh.pop('primitives')
    contract.require(old_mesh == new_mesh, 'Mesh metadata changed')
    for key in set(doc) | set(parent_doc):
        if key not in ('accessors', 'bufferViews', 'buffers', 'meshes'):
            contract.require(doc.get(key) == parent_doc.get(key), 'Original GLB metadata changed: '+key)
    contract.require(len(doc['buffers']) == 1 and doc['buffers'][0] == {'byteLength': len(binary)},
                     'Unsupported buffer descriptor')
    contract.require(embedded_maps(doc, binary) == embedded_maps(parent_doc, parent_binary),
                     'Original material/map bytes changed')


def decode_active(doc, binary, archive, original_ids, mapping, space):
    """Decode active float32 corners while inventorying all preserved stored rows."""
    contract.require(not doc.get('animations') and not doc.get('skins') and
                     doc.get('scenes') == [{'nodes': [0]}] and doc.get('scene', 0) == 0 and
                     doc.get('nodes') == ([{'mesh': 0}] if space == 'source' else
                                           [{'name': 'detached_geometry', 'mesh': 0}]),
                     'Exact static source/working identity layout required')
    primitives = doc['meshes'][0]['primitives']
    contract.require(len(primitives) == 3 and set(archive) == ARCHIVE_KEYS,
                     'Three primitives and explicit serialized corner archive required')
    inventory = []; combined = {key: [] for key in SEMANTICS}; primitive_ids = []; materials = []
    for number, primitive in enumerate(primitives):
        contract.require(primitive.get('mode', 4) == 4 and not primitive.get('targets') and
                         not primitive.get('extensions') and set(primitive['attributes']) == set(SEMANTICS),
                         'Unsupported diagnostic geometry attributes/primitive')
        rows = {key: accessor(doc, binary, primitive['attributes'][key]) for key in SEMANTICS}
        count = len(rows['POSITION'])
        widths = {'POSITION': 3, 'NORMAL': 3, 'TEXCOORD_0': 2, 'TANGENT': 4}
        contract.require(all(value.dtype == np.float32 and value.shape == (count, widths[key]) and
                             np.isfinite(value).all() for key, value in rows.items()),
                         'Finite float32 stored P/N/UV/tangent rows required')
        indices = accessor(doc, binary, primitive['indices'])
        contract.require(indices.dtype.kind == 'u' and indices.size > 0 and indices.size % 3 == 0,
                         'Unsigned triangle indices required')
        indices = indices.reshape(-1, 3).astype(np.int64)
        contract.require(indices.min() >= 0 and indices.max() < count, 'Index outside stored rows')
        active = np.unique(indices)
        contract.require(np.array_equal(active, mapping[space+'_primitive'+str(number)+'ReferencedOriginalAccessorRows']),
                         'Referenced row inventory differs from the exact indices')
        lengths = np.linalg.norm(rows['NORMAL'].astype(float), axis=1)
        bad = np.flatnonzero(lengths <= .5)
        contract.require(not len(np.intersect1d(active, bad)), 'Referenced near-zero normal rejected')
        tangents = rows['TANGENT'][active].astype(float)
        normals = rows['NORMAL'][active].astype(float)
        cross = np.linalg.norm(np.cross(normals, tangents[:, :3]), axis=1)
        contract.require(np.all(np.linalg.norm(tangents[:, :3], axis=1) > .5) and
                         np.all(np.abs(tangents[:, 3]) == 1) and np.all(cross > .25),
                         'Degenerate or ambiguous active tangent basis rejected')
        for key in SEMANTICS: combined[key].append(rows[key][indices])
        primitive_ids.extend([number]*len(indices)); materials.extend([primitive['material']]*len(indices))
        inventory.append({'primitive': number, 'triangles': len(indices), 'material': primitive['material'],
            'attributeAccessors': primitive['attributes'], 'indexAccessor': primitive['indices'],
            'storedAttributeRows': count, 'referencedRows': len(active), 'inactiveRows': count-len(active),
            'activeRowInventory': fingerprint(active), 'activeIndexArray': fingerprint(indices),
            'storedNearZeroNormalRows': bad.tolist(),
            'inactiveNormalRawFloat32Hex': {str(i): rows['NORMAL'][i].tobytes().hex() for i in bad},
            'storedAttributes': {key: fingerprint(value) for key, value in rows.items()}})
    for key, values in combined.items():
        decoded = np.concatenate(values)
        contract.require(archive[key].dtype == np.float32 and fingerprint(decoded) == fingerprint(archive[key]),
                         'Serialized active corner archive mismatch: '+key)
    for key, values in (('primitiveIds', primitive_ids), ('materialIds', materials)):
        contract.require(archive[key].dtype.kind in 'iu' and np.array_equal(archive[key], values),
                         'Ordered primitive/material corner ownership differs: '+key)
    faces = np.concatenate((original_ids, np.full(len(primitive_ids)-len(original_ids), -1, dtype=np.int64)))
    contract.require(archive['sourceOriginalFaceIds'].dtype.kind in 'iu' and
                     np.array_equal(archive['sourceOriginalFaceIds'], faces),
                     'Original face / separate generated cap provenance differs')
    contract.require([row['material'] for row in inventory] == [0, 1, 1] and len(doc['materials']) == 2,
                     'Original body and two shared neutral cap materials required')
    cap = doc['materials'][1]
    contract.require(cap.get('alphaMode') == 'OPAQUE' and cap.get('extras', {}).get('diagnosticOnly') is True and
                     cap.get('extras', {}).get('materialAccepted') is False and not cap.get('normalTexture') and
                     not cap.get('pbrMetallicRoughness', {}).get('baseColorTexture'),
                     'Caps must remain unowned neutral diagnostics')
    return inventory


def verify_audits(decode, parent_audit, child_item, parent_item, child):
    contract.require(decode.get('kind') == 'independent-four-face-troll-pelvis-child-decode' and
                     decode['diagnostic'] == child_item and parent_audit.get('kind') ==
                     'independent-bounded-troll-pelvis-diagnostic-recipe-audit' and
                     parent_audit['diagnostic'] == parent_item,
                     'Independent audits must bind the exact child and bounded parent')
    contract.require(parent_audit.get('exactRecipeAndFootprintVerified') is True and
                     parent_audit.get('originalOutsideAttributeAndCornerBytesVerified') is True,
                     'Bounded cap/source audit failed')
    for space in ('source', 'working'):
        checked = decode['spaces'][space]
        for key in ('bodyAttributeBytesAndRetainedCornersExact', 'capBindingsCornerAndAttributeBytesExact',
                    'allMaterialAndMapBytesExact', 'onlyOneNewIndexAccessor',
                    'remainingBoundaryAndDefectPositionsPinned', 'activeArchiveMatchesDecodedPrimitives'):
            contract.require(checked.get(key) is True, 'Independent child audit failed: '+key)
        contract.require(checked['childCandidate'] == child['exports'][space]['candidate'] and
                         checked['parentCandidate'] == child['exports'][space]['parentCandidate'],
                         'Independent audit candidate binding differs')
        checks = parent_audit['topologyAndIntersections'][space]['checks']
        contract.require(checks and all(value is True for value in checks.values()),
                         'Bounded cap intersection/topology audit failed')
    no_acceptance(decode); no_acceptance(parent_audit)


def verify_receipt(path, target_path, target, space='working'):
    """Return exact preview input pins and measured inventory; never re-export GLB."""
    path = Path(path).resolve(); receipt = json.loads(path.read_text(encoding='utf-8'))
    inputs = {str(path): contract.sha(path)}
    contract.require(space == 'working', 'Diagnostic lineage supports working preview only')
    contract.require(receipt.get('schemaVersion') == 2 and receipt.get('kind') == KIND and
                     receipt.get('operation') == OPERATION and receipt.get('previewScope') == PREVIEW_SCOPE and
                     receipt.get('diagnosticOnly') is True, 'Explicit bounded diagnostic preview receipt required')
    contract.verify_binding(receipt, target_path, target, space)
    rig = target['rig']
    contract.require(rig.get('offlineStructureAccepted') is True and rig.get('pilotAccepted') is True and
                     rig.get('pilotAcceptanceScope') == 'offline-rig-structure',
                     'Frozen offline rig structure required; no final acceptance inferred')
    for flag in FLAGS: contract.require(receipt.get(flag) is False, 'False pending gate required: '+flag)
    no_acceptance(receipt)
    contract.require(receipt.get('part') == 'pelvis' and receipt.get('joint') == 'pelvis_g' and
                     receipt.get('model') == contract.model(target, 'pelvis') and
                     receipt.get('statureApplications') == 0 and receipt.get('primitiveRoleStatus') == ROLES,
                     'Working pelvis ownership, unowned cap roles and zero stature applications required')
    contract.require(np.array_equal(receipt['candidateToAttachmentLocal'], np.eye(4)) and
                     np.array_equal(receipt['attachmentWorld'], contract.frame(target, 'pelvis_g', 'working')),
                     'Candidate must already be attachment-local; frozen frame applies once')
    review = load_item(receipt['rootReview'], inputs)
    contract.require(review.get('schemaVersion') == 2 and review.get('kind') == 'target-diagnostic-preview-root-review' and
                     review.get('scope') == SCOPE and review.get('reviewedBy') == '/root' and
                     review.get('reviewed') is True and review.get('authorizeDiagnosticPreview') is True,
                     'Explicit root review of this bounded preview required')
    contract.verify_binding(review, target_path, target, space)
    no_acceptance(review)
    contract.require(review.get('pendingGates') == {flag: False for flag in FLAGS} and
                     review.get('candidate') == receipt['candidate'] and
                     review.get('candidateSha256') == receipt['candidateSha256'] and
                     review.get('part') == 'pelvis' and review.get('joint') == 'pelvis_g' and
                     review.get('model') == receipt['model'] and review.get('primitiveRoleStatus') == ROLES and
                     review.get('statureApplications') == 0 and
                     review.get('attachmentWorld') == receipt['attachmentWorld'] and
                     review.get('candidateToAttachmentLocal') == receipt['candidateToAttachmentLocal'] and
                     review.get('fitSourceToAttachmentLocal') == receipt['fitSourceToAttachmentLocal'],
                     'Root review identity/frames/scope differs from diagnostic receipt')
    evidence = review['evidence']
    contract.require(set(EVIDENCE) <= set(evidence), 'Required source/fit/audit/cap/proposal evidence missing')
    for item in evidence.values(): pin(item, inputs)
    child = load_item(evidence['childDiagnostic'], inputs)
    parent = load_item(evidence['boundedConnectorParent'], inputs)
    fit_path = pin(evidence['properTargetFit'], inputs); fit = json.loads(fit_path.read_text(encoding='utf-8'))
    contract.require(child.get('kind') == 'bounded-troll-pelvis-original-opposite-pair-index-repair' and
                     parent.get('kind') == 'bounded-troll-pelvis-port-diagnostic' and
                     child.get('schemaVersion') == parent.get('schemaVersion') == 1 and
                     child['parentDiagnostic'] == evidence['boundedConnectorParent'] and
                     child['properFit'] == parent['properFit'] == evidence['properTargetFit'] and
                     child['source'] == parent['source'] == evidence['originalSource'] and
                     child['selectedReadOnlyProposal'] == evidence['selectedFourFaceProposal'] and
                     child['faceAndActiveRowMapping'] == evidence['childMapping'] and
                     parent['faceMapping'] == evidence['parentMapping'], 'Diagnostic ancestry/evidence differs')
    for value in (child, parent):
        contract.verify_binding(value, target_path, target, space)
        contract.require(value['part'] == 'pelvis' and value['joint'] == 'pelvis_g' and
                         value['model'] == receipt['model'] and value['statureApplications'] == 0 and
                         value['attachmentWorld'] == receipt['attachmentWorld'] and
                         value['sourceToAttachmentLocal'] == receipt['fitSourceToAttachmentLocal'] and
                         (value.get('sourceMastersChanged') is False if value is child else
                          value.get('protectedInputsUnchanged') is True), 'Original working fit/attachment ancestry differs')
        no_acceptance(value)
        for name, digest in value['frozenInputs'].items(): pin({'path': name, 'sha256': digest}, inputs)
    fit_candidate = pin(evidence['fitCandidate'], inputs)
    verify_source_receipt(fit_candidate, fit_path, target_path, target, 'pelvis', 'working')
    contract.require(fit.get('operation') == 'fit' and fit['attachmentWorld'] == receipt['attachmentWorld'] and fit['sourceToAttachmentLocal'] == receipt['fitSourceToAttachmentLocal'] and
                     fit['nativeCornerArchive'] == evidence['properFitFloat64CornerArchive'] and
                     fit['source'] == evidence['originalSource']['path'] and
                     fit['sourceSha256'] == evidence['originalSource']['sha256'] and
                     fit['sourceReceipt'] == evidence['generationReceipt']['path'] and
                     fit['sourceReceiptSha256'] == evidence['generationReceipt']['sha256'] and
                     fit['candidate'] == str(fit_candidate) and fit['candidateSha256'] == evidence['fitCandidate']['sha256'] and
                     fit['proof']['reflected'] is False and fit['proof']['uniformScale'] > 0,
                     'Positive proper original fit/source proof required')
    linear = np.asarray(fit['sourceToAttachmentLocal'], float)[:3, :3]
    uniform = fit['proof']['uniformScale']
    contract.require(np.array_equal(np.asarray(fit['sourceToAttachmentLocal'], float)[3], [0,0,0,1]) and
                     np.linalg.det(linear) > 0 and np.allclose(linear.T@linear, np.eye(3)*uniform**2, atol=1e-12, rtol=0),
                     'Fit ancestry must remain proper positive uniform scale')
    generation_source(pin(evidence['originalSource'], inputs), pin(evidence['generationReceipt'], inputs))
    for name, digest in fit['frozenInputs'].items(): pin({'path': name, 'sha256': digest}, inputs)
    for name in ('capLeftGenerator', 'capRightGenerator'):
        item = evidence[name]
        contract.require(parent['frozenInputs'].get(item['path']) == item['sha256'], 'Cap generator provenance missing')
    proposal = load_item(evidence['proposal'], inputs)
    contract.require(proposal.get('kind') == 'target-pelvis-diagnostic-lineage-proposal' and
                     proposal['actualChild']['receipt']['path'] == evidence['childDiagnostic']['path'] and
                     proposal['actualChild']['receipt']['sha256'] == evidence['childDiagnostic']['sha256'],
                     'Root-approved proposal does not bind this child')
    verify_audits(load_item(evidence['independentDecode'], inputs), load_item(evidence['parentIndependentAudit'], inputs),
                  evidence['childDiagnostic'], evidence['boundedConnectorParent'], child)
    mapping = load_archive(evidence['childMapping'], inputs)
    parent_mapping = load_archive(evidence['parentMapping'], inputs)
    original_ids = mapping['keptOriginalFaceIds']; previous_ids = mapping['parentKeptOriginalFaceIds']
    keep = mapping['parentPrimitive0KeepMask']
    removed = mapping['removedOriginalFaceIds']
    contract.require(original_ids.dtype.kind in 'iu' and previous_ids.dtype.kind in 'iu' and keep.dtype == np.bool_ and
                     len(keep) == len(previous_ids) and np.array_equal(previous_ids, parent_mapping['keptOriginalFaceIds']) and
                     np.array_equal(previous_ids[keep], original_ids) and np.array_equal(previous_ids[~keep], removed) and
                     removed.tolist() == child['removedOnlyOriginalFaceIds'] == review['removedOriginalFaceIds'] and
                     len(removed) == len(set(removed.tolist())) == 4 and
                     np.array_equal(np.flatnonzero(~keep), mapping['removedParentPrimitive0FaceIds']) and
                     mapping['removedParentPrimitive0FaceIds'].tolist() == child['removedParentPrimitive0FaceIds'] and
                     np.array_equal(mapping['sourceOriginalFaces'], parent_mapping['sourceOriginalFaces']),
                     'Exhaustive ordered four-face source/index mapping differs')
    fit_archive = load_archive(evidence['properFitFloat64CornerArchive'], inputs)
    spaces = {}
    for export_space in ('source', 'working'):
        branch = child['exports'][export_space]
        candidate = pin(branch['candidate'], inputs); parent_candidate = pin(branch['parentCandidate'], inputs)
        contract.require(branch['parentCandidate'] == parent['exports'][export_space]['candidate'], 'Export parent differs')
        doc, binary = read_glb(candidate); parent_doc, parent_binary = read_glb(parent_candidate)
        verify_preserved_child(doc, binary, parent_doc, parent_binary, keep)
        archive = load_archive(branch['activeCornerArchive'], inputs)
        inventory = decode_active(doc, binary, archive, original_ids, mapping, export_space)
        expected = proposal['actualChild']['spaces'][export_space]['primitiveInventory']
        contract.require(len(expected) == len(inventory), 'Incomplete reviewed primitive inventory')
        for row, old in zip(inventory, expected):
            for key in ('primitive', 'triangles', 'material', 'attributeAccessors', 'indexAccessor', 'storedAttributeRows',
                        'referencedRows', 'inactiveRows', 'activeRowInventory', 'activeIndexArray', 'storedNearZeroNormalRows'):
                contract.require(row[key] == old[key], 'Reviewed primitive inventory changed: '+key)
            for key, value in row['storedAttributes'].items():
                contract.require(value == old['nativeStoredAttributes'][key], 'Reviewed stored attribute bytes changed: '+key)
        points = archive['POSITION'].astype(float)@BASIS.T
        normals = archive['NORMAL'].astype(float)@BASIS.T
        pkey, nkey = ('sourcePositions', 'sourceNormals') if export_space == 'source' else ('positions', 'normals')
        contract.require(fit_archive[pkey].dtype == fit_archive[nkey].dtype == np.float64 and
                         original_ids.min() >= 0 and original_ids.max() < len(fit_archive[pkey]),
                         'Original body float64 fit ancestry required')
        perror = float(np.max(abs(points[:len(original_ids)]-fit_archive[pkey][original_ids])))
        nerror = float(np.max(abs(normals[:len(original_ids)]-fit_archive[nkey][original_ids])))
        contract.require(perror <= fit['proof']['maximumPositionFloat32ErrorMetres']+1e-12 and nerror <=
                         fit['proof']['maximumNormalFloat32Error']+1e-12, 'Body differs from original proper-fit float64 lineage')
        contract.require(np.array_equal(archive['TEXCOORD_0'][:len(original_ids)], fit_archive['uvGltf'][original_ids]),
                         'Original body UV ancestry differs')
        contract.require(np.array_equal(fit_archive['tangentTriangleIds'], np.arange(len(fit_archive[pkey]))),
                         'Complete original tangent ancestry required')
        expected_tangent = fit_archive['tangents'][original_ids].copy()
        if export_space == 'source': expected_tangent[:, :, :3] = expected_tangent[:, :, :3]@(linear/uniform)
        decoded_tangent = archive['TANGENT'][:len(original_ids)].astype(float)
        decoded_tangent[:, :, :3] = decoded_tangent[:, :, :3]@BASIS.T
        tangent_error = float(np.max(abs(decoded_tangent-expected_tangent)))
        contract.require(tangent_error <= 1e-7 and np.array_equal(decoded_tangent[:, :, 3], expected_tangent[:, :, 3]),
                         'Original body tangent/sign ancestry differs')
        spaces[export_space] = {'primitiveInventory': inventory, 'bodyFloat64PositionErrorMetres': perror,
                               'bodyFloat64NormalError': nerror, 'bodyFloat64TangentError': tangent_error,
                               'pendingTopology': branch['topologyTransition']['after']}
    working = child['exports']['working']
    contract.require(receipt['candidate'] == working['candidate']['path'] and
                     receipt['candidateSha256'] == working['candidate']['sha256'] and
                     receipt['activeSerializedCornerArchive'] == working['activeCornerArchive'] and
                     receipt['bodyFloat64FitArchive'] == evidence['properFitFloat64CornerArchive'],
                     'Preview must consume exact working candidate and distinct archive domains')
    frozen = receipt['frozenInputs']
    contract.require(str(Path(target_path).resolve()) in frozen and all(frozen.get(name) == digest for name, digest in inputs.items()
                     if name != str(path)), 'Diagnostic receipt is missing exact evidence closure')
    for name, digest in frozen.items(): pin({'path': name, 'sha256': digest}, inputs)
    return {'receipt': str(path), 'receiptSha256': inputs[str(path)], 'part': 'pelvis', 'joint': 'pelvis_g',
            'model': receipt['model'], 'candidate': receipt['candidate'], 'candidateSha256': receipt['candidateSha256'],
            'coordinateSpace': 'working', 'statureApplications': 0, 'candidateToAttachmentLocal': np.eye(4).tolist(),
            'attachmentAppliedOnce': True, 'historicalFitReapplied': False, 'diagnosticOnly': True,
            'receiptKind': KIND, 'previewScope': PREVIEW_SCOPE, 'primitiveRoleStatus': ROLES,
            'activeArchiveEncoding': 'serialized-gltf-float32-corners', 'canonicalNativeLineage': False,
            'pendingGates': {flag: False for flag in FLAGS}, 'clientEvidence': False,
            'rootReview': receipt['rootReview'], 'pendingRisks': review['pendingRisks'], 'spaces': spaces, 'inputs': inputs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--target-contract', required=True, type=Path)
    parser.add_argument('--coordinate-space', required=True, choices=('working', 'runtime'))
    parser.add_argument('--output', required=True, type=Path, help='Fresh read-only validation output directory')
    args = parser.parse_args()
    target = contract.load(args.target_contract)
    result = verify_receipt(args.receipt, args.target_contract, target, args.coordinate_space)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'validation.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'validation': str((args.output/'validation.json').resolve()), 'candidate': result['candidate'],
                      'statureApplications': 0, 'diagnosticOnly': True, 'pendingGates': result['pendingGates']}))


if __name__ == '__main__': main()
