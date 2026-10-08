"""Apply a reviewed source face selection to its existing proper uniform fit.

The generation master and fitted parent remain immutable. This descendant only
changes triangle indexing, with explicit source-face/vertex provenance. Authored
attributes, embedded maps, fit, rig frames and stature are preserved exactly.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from conservative_face_selection import descendant, mesh_arrays
from place_purposebuilt_pelvis import raw_corners, read_glb
from target_part_pipeline import generation_source, pin, read_target, verify_source_receipt


def frozen_receipt_inputs(receipt):
    """Resolve recorded executable snapshots without reinterpreting old code."""
    result = {}
    for name, expected in receipt['frozenInputs'].items():
        snapshot = receipt.get('helperSnapshots', {}).get(name)
        path = snapshot['snapshot'] if snapshot else name
        pin(path, expected)
        result[str(Path(path).resolve())] = expected
    return result


def repair_archive(parent, faces, kept, added):
    """Select exact double-precision parent corners; reuse rows for micro caps."""
    count = len(faces)
    contract.require(np.array_equal(parent['sourceTriangleIds'], np.arange(count)) and
                     np.array_equal(parent['sourceCornerOrder'], np.tile([0, 1, 2], (count, 1))),
                     'Original ordered proper-fit corner provenance required')
    contract.require(np.all(parent['primitiveIds'] == 0), 'One original primitive required')
    keys = {'positions', 'normals', 'uvNative', 'uvGltf', 'sourcePositions',
            'sourceNormals', 'sourceUVNative'}
    contract.require(keys <= set(parent), 'Complete authoritative parent corner arrays required')
    if 'tangents' in parent:
        contract.require(np.array_equal(parent['tangentTriangleIds'], np.arange(count)),
                         'Complete ordered parent tangents required')
        keys.add('tangents')
    first = {}
    for face, row in enumerate(faces):
        for corner, vertex in enumerate(row):
            first.setdefault(int(vertex), (face, corner))
    retained_vertices = set(faces[kept].reshape(-1).tolist())
    contract.require(set(added.reshape(-1).tolist()) <= retained_vertices,
                     'Cap vertices must belong to retained neighboring source faces')
    result = {}
    for key in sorted(keys):
        rows = parent[key]
        contract.require(rows.ndim == 3 and rows.shape[:2] == (count, 3) and
                         np.isfinite(rows).all(), 'Finite ordered parent corner array required: ' + key)
        # A serialized vertex has one attribute row, even where distinct rows
        # share a position at a UV seam. Never coordinate-weld this lookup.
        for face, row in enumerate(faces):
            for corner, vertex in enumerate(row):
                a, b = first[int(vertex)]
                contract.require(np.array_equal(rows[face, corner], rows[a, b]),
                                 'Conflicting authoritative rows for serialized vertex: ' + key)
        cap = np.asarray([[rows[first[int(v)]] for v in row] for row in added], dtype=rows.dtype)
        cap = cap.reshape((len(added), 3, rows.shape[2]))
        result[key] = np.concatenate((rows[kept], cap))
        contract.require(np.array_equal(result[key][:len(kept)], rows[kept]),
                         'Retained authoritative corners changed: ' + key)
    total = len(kept) + len(added)
    result['primitiveIds'] = np.zeros(total, dtype=np.int64)
    result['sourceTriangleIds'] = np.concatenate((kept, np.full(len(added), -1, dtype=np.int64)))
    result['sourceCornerOrder'] = np.tile([0, 1, 2], (total, 1))
    result['addedConnectorMask'] = np.arange(total) >= len(kept)
    result['addedSourceVertexFaces'] = added
    if 'tangents' in result:
        result['tangentTriangleIds'] = np.arange(total, dtype=np.int64)
    return result


def execute(config_path, output):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    contract.require(config.get('kind') == 'target-face-repair' and config.get('diagnosticOnly') is True,
                     'Explicit diagnostic face repair configuration required')
    allowed = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'targetContractSha256',
               'part', 'coordinateSpace', 'source', 'sourceSha256', 'sourceReceipt',
               'sourceReceiptSha256', 'selectionReceipt', 'selectionReceiptSha256',
               'protectedInputs', 'notes'}
    contract.require(set(config) <= allowed, 'Unknown face repair controls')
    target_path, target = read_target(config)
    contract.require(config['coordinateSpace'] == 'working', 'Repair the working proper fit before stature conversion')
    part = config['part']
    source = pin(config['source'], config['sourceSha256'])
    parent_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    parent = verify_source_receipt(source, parent_path, target_path, target, part, 'working')
    contract.require(parent['operation'] == 'fit' and not parent['proof']['reflected'],
                     'Original proper uniform fitted parent required')
    origin = pin(parent['source'], parent['sourceSha256'])
    job = pin(parent['sourceReceipt'], parent['sourceReceiptSha256'])
    generation_source(origin, job)
    selection_path = pin(config['selectionReceipt'], config['selectionReceiptSha256'])
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    contract.require(selection.get('schemaVersion') == 2 and
                     selection.get('kind') == 'target-face-selection-trial' and
                     selection.get('eligibleForOfflineReview') is True and
                     selection.get('diagnosticOnly') is True and selection.get('sourceChanged') is False and
                     selection.get('protectedNeighborsChanged') is False,
                     'Eligible immutable source face-selection trial required')
    for key in ('targetContractSha256', 'targetId', 'rigRevision', 'part', 'model'):
        contract.require(selection[key] == parent[key], 'Selection target/source ownership differs: ' + key)
    contract.require(Path(selection['source']).resolve() == origin and
                     selection['sourceSha256'] == contract.sha(origin),
                     'Face selection must refer to the exact collected parent generation master')
    selected_source = pin(selection['candidate'], selection['candidateSha256'])
    selection_archive = pin(selection['faceSelectionArchive']['path'], selection['faceSelectionArchive']['sha256'])
    corner_path = pin(parent['nativeCornerArchive']['path'], parent['nativeCornerArchive']['sha256'])
    inputs = {str(p): contract.sha(p) for p in
              (config_path, target_path, source, parent_path, origin, job, selection_path,
               selected_source, selection_archive, corner_path)}
    inputs.update(frozen_receipt_inputs(parent))
    inputs.update(frozen_receipt_inputs(selection))
    for name, expected in config.get('protectedInputs', {}).items():
        inputs[str(pin(name, expected))] = expected
    for name in ('repair_target_part_faces.py', 'conservative_face_selection.py',
                 'target_contract.py', 'target_part_pipeline.py', 'place_purposebuilt_pelvis.py'):
        path = Path(__file__).with_name(name).resolve(); inputs[str(path)] = contract.sha(path)
    original_doc, original_bin = read_glb(origin)
    _, original_faces, original_primitive = mesh_arrays(original_doc, original_bin)
    doc, blob = read_glb(source)
    _, faces, primitive = mesh_arrays(doc, blob)
    contract.require(np.array_equal(original_faces, faces), 'Proper-fit source face/vertex indexing differs')
    contract.require(primitive['attributes'] == parent['proof']['primitives'][0]['outputAttributeAccessors'] and
                     original_primitive['attributes'] == parent['proof']['primitives'][0]['sourceAttributeAccessors'],
                     'Active fitted/source attribute mapping differs from immutable fit proof')
    with np.load(selection_archive, allow_pickle=False) as data:
        contract.require(np.array_equal(data['sourceFaces'], original_faces), 'Selection archive ordered source differs')
        kept = data['keptSourceFaceIds'].copy()
        added = data['addedSourceVertexFaces'].copy()
        deleted = data['deletedSourceFaceIds'].copy()
    contract.require(kept.ndim == 1 and len(kept) > 0 and np.all(np.diff(kept) > 0) and
                     kept[0] >= 0 and kept[-1] < len(faces) and
                     added.ndim == 2 and added.shape[1] == 3 and len(added) <= 6 and
                     np.issubdtype(kept.dtype, np.integer) and np.issubdtype(added.dtype, np.integer),
                     'Ordered source selection and bounded original-vertex cap required')
    contract.require(np.array_equal(np.sort(np.concatenate((kept, deleted))), np.arange(len(faces))),
                     'Kept/deleted source faces must partition original triangles')
    _, selected_faces, _ = mesh_arrays(*read_glb(selected_source))
    contract.require(np.array_equal(selected_faces, np.concatenate((faces[kept], added))),
                     'Selection trial candidate differs from declared face operation')
    with np.load(corner_path, allow_pickle=False) as data:
        archive = repair_archive({key: data[key] for key in data.files}, faces, kept, added)
    output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh immutable face repair output required')
    output.mkdir(parents=True)
    candidate = output / 'candidate-local.glb'
    proof = descendant(source, candidate, kept, added)
    topo = proof['afterTopology']
    contract.require(topo['boundaryEdges'] == topo['nonmanifoldEdges'] ==
                     topo['inconsistentManifoldEdgeWindings'] == topo['nonmanifoldVertexLinks'] ==
                     topo['zeroAreaFaces'] == 0 and topo['components'] == 1 and topo['signedVolume'] > 0,
                     'Fitted repaired exterior must remain coherent closed geometry')
    p, n, uv, _ = raw_corners(*read_glb(candidate))
    contract.require(np.max(np.abs(p - archive['positions'])) <= parent['proof']['maximumPositionFloat32ErrorMetres'] + 1e-12 and
                     np.max(np.abs(n - archive['normals'])) <= parent['proof']['maximumNormalFloat32Error'] + 1e-12 and
                     np.array_equal(uv, archive['uvGltf']), 'Serialized descendant differs from authoritative fit corners')
    corners = output / 'native-corners.npz'
    np.savez_compressed(corners, **archive)
    shutil.copyfile(__file__, output / 'executed-helper.py')
    joint = contract.PART_JOINTS[part]
    receipt = {'schemaVersion': 2, 'kind': 'target-part-geometry', 'operation': 'face-repair',
               **contract.binding(target_path, target, 'working'), 'part': part, 'joint': joint,
               'model': contract.model(target, part), 'sourcePart': part,
               'source': str(source), 'sourceSha256': contract.sha(source),
               'sourceReceipt': str(parent_path), 'sourceReceiptSha256': contract.sha(parent_path),
               'selectionReceipt': str(selection_path), 'selectionReceiptSha256': contract.sha(selection_path),
               'candidate': str(candidate), 'candidateSha256': contract.sha(candidate),
               'nativeCornerArchive': {'path': str(corners), 'sha256': contract.sha(corners)},
               'statureApplications': 0, 'sourceToAttachmentLocal': np.eye(4).tolist(),
               'attachmentWorld': contract.frame(target, joint, 'working').tolist(), 'reflectionWorld': None,
               'proof': {**proof, 'retainedDoublePrecisionParentCornersExact': True,
                         'capCornerPolicy': 'Original serialized vertex identity; exact parent attribute rows reused',
                         'addedFaceSourceTriangleId': -1, 'parentFitAndRigUnchanged': True},
               'frozenInputs': inputs, 'diagnosticOnly': True, 'rigPilotAccepted': False,
               'clientAccepted': False, 'productionAccepted': False,
               'limitation': 'Index-only outer-sheet/micro-hole trial; shoulder ownership, posed connectors, native shading and client review remain pending.'}
    for name, expected in inputs.items(): pin(name, expected)
    path = output / 'geometry.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = execute(args.config, args.output)
    print(json.dumps({'receipt': str(path), 'sha256': contract.sha(path)}))
