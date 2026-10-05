"""Strict, separate lineage for body-only diagnostic pelvis material subdivision.

Original body corners remain authoritative proper-fit float64. Generated caps
remain a distinct serialized float32 domain. This module grants no preview,
staging, closure, native, material, collision or client acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np

import target_contract as contract
import target_diagnostic_lineage as diagnostic
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import accessor, embedded_maps, read_glb
from segment_target_pelvis_boundary import CORNER_KEYS, checked_archive, cut_polygons

KIND = 'target-part-diagnostic-material-geometry'
OPERATION = 'body-only-segment-and-partition'
MAP_KIND = 'target-diagnostic-pelvis-body-cut-map'
SCOPE = 'body-only-material-boundary-subdivision'
CAP_MODE = 'literal-neutral-cap-passthrough'
BODY_KEYS = CORNER_KEYS | {'primitiveIds', 'sourceTriangleIds', 'sourceCornerOrder', 'tangents', 'tangentTriangleIds'}
FLAGS = diagnostic.FLAGS + ('materialBindingsAccepted', 'visibleMaterialBoundaryAccepted', 'opaqueGarmentClientAccepted')


def literal_json(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def json_sha(value):
    return hashlib.sha256(literal_json(value)).hexdigest()


def body_projection(doc):
    """An explicitly labeled in-memory body view for pure attribute checking only."""
    projected = copy.deepcopy(doc)
    projected['meshes'][0]['primitives'] = [copy.deepcopy(doc['meshes'][0]['primitives'][0])]
    return projected


def original_body_archive(fit_archive, original_ids):
    """Select original fit rows; never promote generated float32 cap corners."""
    count = len(fit_archive['positions'])
    contract.require(set(fit_archive) == BODY_KEYS and original_ids.dtype == np.int64 and
                     original_ids.ndim == 1 and len(original_ids) > 0 and
                     np.all(np.diff(original_ids) > 0) and original_ids.min() >= 0 and original_ids.max() < count,
                     'Complete original float64 fit and ordered original body source IDs required')
    contract.require(np.array_equal(fit_archive['sourceTriangleIds'], np.arange(count)) and
                     np.array_equal(fit_archive['primitiveIds'], np.zeros(count, dtype=np.int64)) and
                     np.array_equal(fit_archive['sourceCornerOrder'], np.tile([0, 1, 2], (count, 1))) and
                     np.array_equal(fit_archive['tangentTriangleIds'], np.arange(count)),
                     'Original one-primitive source-corner ancestry required')
    for key in CORNER_KEYS | {'tangents'}:
        width = 4 if key == 'tangents' else 2 if key in ('uvNative', 'uvGltf', 'sourceUVNative') else 3
        contract.require(fit_archive[key].dtype == np.float64 and fit_archive[key].shape == (count, 3, width) and
                         np.isfinite(fit_archive[key]).all(), 'Original float64 body attributes required: '+key)
    result = {key: value[original_ids].copy() for key, value in fit_archive.items()}
    result['tangentTriangleIds'] = np.arange(len(original_ids), dtype=np.int64)
    return result


def caps_from_serialized(active_archive, body_count):
    result = {key: value[body_count:].copy() for key, value in active_archive.items()}
    contract.require(set(result) == diagnostic.ARCHIVE_KEYS and all(result[key].dtype == np.float32
                     for key in diagnostic.SEMANTICS) and np.all(result['sourceOriginalFaceIds'] == -1) and
                     set(result['primitiveIds'].tolist()) == {1, 2} and np.all(result['materialIds'] == 1),
                     'Separate generated cap float32 provenance required; original body source IDs forbidden')
    return result


def prepare_parent(receipt_path, target_path, target):
    summary = diagnostic.verify_receipt(receipt_path, target_path, target, 'working')
    receipt = json.loads(Path(receipt_path).read_text(encoding='utf-8'))
    inputs = summary['inputs'].copy()
    review = diagnostic.load_item(receipt['rootReview'], inputs)
    mapping = diagnostic.load_archive(review['evidence']['childMapping'], inputs)
    original_ids = mapping['keptOriginalFaceIds']
    fit = diagnostic.load_archive(receipt['bodyFloat64FitArchive'], inputs)
    body = original_body_archive(fit, original_ids)
    active = diagnostic.load_archive(receipt['activeSerializedCornerArchive'], inputs)
    caps = caps_from_serialized(active, len(original_ids))
    doc, binary = read_glb(receipt['candidate'])
    rows = active_faces(doc, binary)
    contract.require(len(rows) == 3 and len(rows[0][2]) == len(original_ids), 'Exact diagnostic three-primitive parent required')
    checked_archive(body, rows[0][2], body_projection(doc), binary)
    return {'receipt': receipt, 'summary': summary, 'inputs': inputs, 'doc': doc, 'binary': binary,
            'rows': rows, 'body': body, 'caps': caps, 'originalIds': original_ids,
            'childMapping': review['evidence']['childMapping'],
            'pendingTopology': summary['spaces']['working']['pendingTopology']}


def reviewed_body_map(selection, rows, original_ids):
    allowed = {'schemaVersion', 'kind', 'scope', 'sourceDiagnosticReceipt', 'sourceCandidate', 'targetContract',
               'coordinateSpace', 'statureApplications', 'part', 'joint', 'faceIdSpace', 'parentBodyFaceCount',
               'parentFaceLayoutSha256', 'originalSourceFaceIdsBinding', 'primitive1And2Mode',
               'wholeSkinParentBodyFaceIds', 'wholeGarmentParentBodyFaceIds', 'cutFaces',
               'ambiguousParentBodyFaceIds', 'rootReview', 'complete', 'materialAccepted',
               'capOwnershipAccepted', 'clientAccepted', 'productionAccepted'}
    contract.require(type(selection) is dict and set(selection) <= allowed and
                     selection.get('schemaVersion') == 2 and selection.get('kind') == MAP_KIND and
                     selection.get('scope') == SCOPE and selection.get('coordinateSpace') == 'working' and
                     selection.get('statureApplications') == 0 and selection.get('part') == 'pelvis' and
                     selection.get('joint') == 'pelvis_g' and selection.get('primitive1And2Mode') == CAP_MODE,
                     'Explicit body-only working diagnostic map required; inference/transform controls rejected')
    diagnostic.no_acceptance(selection)
    count = len(rows[0][2])
    contract.require(len(rows) == 3 and original_ids.dtype == np.int64 and original_ids.shape == (count,) and
                     selection.get('faceIdSpace') == 'parent-active-primitive0-order' and
                     type(selection.get('parentBodyFaceCount')) is int and selection['parentBodyFaceCount'] == count and
                     selection.get('parentFaceLayoutSha256') == face_layout_sha(rows), 'Exact current three-primitive face layout required')
    contract.require(selection.get('complete') is True and selection.get('ambiguousParentBodyFaceIds') == [],
                     'Complete explicit root map required; ambiguous or pending maps rejected')
    for key in ('materialAccepted', 'capOwnershipAccepted', 'clientAccepted', 'productionAccepted'):
        contract.require(selection.get(key) is False, 'Diagnostic map cannot accept broader gates: '+key)
    review = selection.get('rootReview', {})
    contract.require(type(review) is dict and set(review) == {'reviewed', 'reviewedBy', 'approveImplementation',
                     'authorizeActualExport', 'scope', 'notes', 'evidence'} and review.get('reviewed') is True and
                     review.get('reviewedBy') == '/root' and review.get('approveImplementation') is True and
                     review.get('authorizeActualExport') is True and review.get('scope') == SCOPE and
                     isinstance(review.get('notes'), str) and bool(review['notes'].strip()) and
                     type(review.get('evidence')) is list and bool(review['evidence']),
                     'Explicit root review authorizing this exhaustive body map required; closure waiver rejected')
    roles = {}
    for role, key in [('skin', 'wholeSkinParentBodyFaceIds'), ('garment', 'wholeGarmentParentBodyFaceIds')]:
        ids = selection.get(key)
        contract.require(type(ids) is list and all(type(value) is int and 0 <= value < count for value in ids) and
                         all(a < b for a, b in zip(ids, ids[1:])), 'Ordered explicit whole body face IDs required')
        for value in ids:
            contract.require(value not in roles, 'Duplicated/overlapping body role')
            roles[value] = role
    contract.require(bool(selection['wholeSkinParentBodyFaceIds']),
                     'Nonempty unchanged whole-skin primitive0 required to keep caps at1/2')
    cuts = selection.get('cutFaces'); plans = {}
    contract.require(type(cuts) is list, 'Explicit list of body crossing records required')
    for item in cuts:
        contract.require(type(item) is dict and set(item) == {'parentBodyFaceId', 'originalSourceFaceId',
                         'boundarySegment', 'skinPolygon', 'garmentPolygon'}, 'Explicit original body cut record required')
        face = item['parentBodyFaceId']; source = item['originalSourceFaceId']
        contract.require(type(face) is int and 0 <= face < count and face not in roles and face not in plans and
                         type(source) is int and source == int(original_ids[face]), 'Cut must bind exact active body and original source face IDs')
        pure = {key: item[key] for key in ('boundarySegment', 'skinPolygon', 'garmentPolygon')}
        pure['sourceFaceId'] = face
        plans[face] = cut_polygons(pure)
    contract.require(list(plans) == sorted(plans) and sorted([*roles, *plans]) == list(range(count)),
                     'Root body map must disjointly and exhaustively cover every active original body face')
    return roles, plans


def verify_map_bindings(selection, parent, receipt_path, target_path, inputs):
    for actual, expected in [
        (selection.get('sourceDiagnosticReceipt'), {'path': str(Path(receipt_path).resolve()), 'sha256': contract.sha(receipt_path)}),
        (selection.get('sourceCandidate'), {'path': parent['receipt']['candidate'], 'sha256': parent['receipt']['candidateSha256']}),
        (selection.get('targetContract'), {'path': str(Path(target_path).resolve()), 'sha256': contract.sha(target_path)}),
        (selection.get('originalSourceFaceIdsBinding'), parent['childMapping'])]:
        contract.require(isinstance(actual, dict) and Path(actual.get('path', '')).resolve() == Path(expected['path']).resolve() and
                         actual.get('sha256') == expected['sha256'], 'Map must bind exact diagnostic/source/target/original-face mapping')
        diagnostic.pin(actual, inputs)
    for item in selection['rootReview']['evidence']:
        diagnostic.pin(item, inputs)


def verify_unchanged_storage(doc, binary, parent_doc, parent_binary):
    contract.require(binary[:len(parent_binary)] == parent_binary and
                     doc['accessors'][:len(parent_doc['accessors'])] == parent_doc['accessors'] and
                     doc['bufferViews'][:len(parent_doc['bufferViews'])] == parent_doc['bufferViews'],
                     'Original BIN/accessor/view prefix changed, including inactive rows')
    contract.require(len(doc['meshes']) == len(parent_doc['meshes']) == 1 and
                     literal_json(doc['meshes'][0]['primitives'][1:3]) == literal_json(parent_doc['meshes'][0]['primitives'][1:3]),
                     'Cap primitive1/2 descriptors must remain serialized literal copies')
    contract.require(literal_json(doc['materials'][:len(parent_doc['materials'])]) == literal_json(parent_doc['materials']) and
                     embedded_maps(doc, binary) == embedded_maps(parent_doc, parent_binary), 'Original material/map bytes changed')
    for key in set(doc) | set(parent_doc):
        if key not in ('accessors', 'bufferViews', 'buffers', 'meshes', 'materials'):
            contract.require(literal_json(doc.get(key)) == literal_json(parent_doc.get(key)), 'Original GLB metadata changed: '+key)
    new_mesh = dict(doc['meshes'][0]); old_mesh = dict(parent_doc['meshes'][0]); new_mesh.pop('primitives'); old_mesh.pop('primitives')
    contract.require(new_mesh == old_mesh and doc['buffers'] == [{'byteLength': len(binary)}], 'Mesh or buffer metadata changed')
    for number in (1, 2):
        old = parent_doc['meshes'][0]['primitives'][number]; new = doc['meshes'][0]['primitives'][number]
        for index in [old['indices'], *old['attributes'].values()]:
            contract.require(accessor(doc, binary, index).tobytes() == accessor(parent_doc, parent_binary, index).tobytes(),
                             'Generated cap serialized attribute/index bytes changed')
    return True