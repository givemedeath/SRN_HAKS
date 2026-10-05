"""Append-only body material cuts for a separately typed diagnostic pelvis.

This adapter never relabels an open three-primitive child as canonical/closed.
Only a pinned exhaustive root-reviewed map may export an actual descendant.
Caps 1/2 remain neutral and byte exact; existing staging/preview guards stay closed.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

import shared_toolchain
import target_contract as contract
import target_diagnostic_lineage as diagnostic
import target_diagnostic_material_lineage as lineage
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import BASIS, accessor, raw_corners, read_glb, write_glb
from segment_target_pelvis_boundary import CORNER_KEYS, area_fraction, checked_archive, conforming_edges, new_corner

ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / 'output/phenotypes'
ROLES = ('skin', 'garment')


def subdivide_body(doc, binary, body_archive, cap_archive, original_ids, selection):
    """Pure writer; strict parent lineage/pins are additionally required by execute."""
    rows = active_faces(doc, binary)
    contract.require(len(rows) == 3 and [row[1].get('material') for row in rows] == [0, 1, 1] and
                     len(doc['materials']) == 2, 'Exactly original body and two shared neutral caps required')
    _, primitive, faces = rows[0]
    contract.require(set(primitive['attributes']) == set(diagnostic.SEMANTICS), 'Only float P/N/UV0/TANGENT supported')
    for index in primitive['attributes'].values():
        item = doc['accessors'][index]
        contract.require(item['componentType'] == 5126 and not item.get('normalized') and not item.get('sparse'),
                         'Unnormalized float attributes required')
    values = checked_archive(body_archive, faces, lineage.body_projection(doc), binary)
    contract.require(np.array_equal(body_archive['sourceTriangleIds'], original_ids), 'Original body face ancestry differs')
    # Cap provenance is compared directly to encoded active GLTF rows, never to
    # the original body's float64 archive or fitted source barycentric domain.
    decoded_caps = {key: np.concatenate([accessor(doc, binary, p['attributes'][key])[
        accessor(doc, binary, p['indices']).reshape(-1, 3)] for _, p, _ in rows[1:]]) for key in diagnostic.SEMANTICS}
    for key in diagnostic.SEMANTICS:
        contract.require(cap_archive[key].dtype == np.float32 and
                         cap_archive[key].tobytes() == decoded_caps[key].tobytes(), 'Separate cap serialized provenance differs: '+key)
    expected_cap_ids = np.concatenate([np.full(len(row[2]), row[0], dtype=np.int64) for row in rows[1:]])
    contract.require(set(cap_archive) == diagnostic.ARCHIVE_KEYS and
                     np.array_equal(cap_archive['primitiveIds'], expected_cap_ids) and
                     np.array_equal(cap_archive['sourceOriginalFaceIds'], np.full(len(expected_cap_ids), -1, dtype=np.int64)) and
                     np.array_equal(cap_archive['materialIds'], np.ones(len(expected_cap_ids), dtype=np.int64)),
                     'Exact distinct generated cap lineage required')
    roles, plans = lineage.reviewed_body_map(selection, rows, original_ids)
    canonical = conforming_edges(body_archive['positions'], plans)
    descriptor = doc['materials'][0]
    contract.require(descriptor.get('alphaMode', 'OPAQUE') == 'OPAQUE' and
                     descriptor.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1]) == [1, 1, 1, 1],
                     'Opaque unchanged original body/garment descriptor required')
    cap = doc['materials'][1]
    contract.require(cap.get('alphaMode') == 'OPAQUE' and cap.get('extras', {}).get('diagnosticOnly') is True and
                     cap.get('extras', {}).get('materialAccepted') is False and not cap.get('normalTexture') and
                     not cap.get('pbrMetallicRoughness', {}).get('baseColorTexture'), 'Unowned neutral caps required')
    new = copy.deepcopy(doc); blob = bytearray(binary)
    new['materials'].append(copy.deepcopy(descriptor)); garment_material = 2
    def append(array, component=5126):
        array = np.asarray(array, dtype='<f4' if component == 5126 else '<u4')
        contract.require(np.isfinite(array).all(), 'Nonfinite serialization rejected')
        blob.extend(b'\0' * (-len(blob) % 4)); offset = len(blob); blob.extend(array.tobytes()); blob.extend(b'\0' * (-len(blob) % 4))
        new['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': array.nbytes})
        width = array.shape[1] if array.ndim == 2 else 1
        new['accessors'].append({'bufferView': len(new['bufferViews'])-1, 'componentType': component,
                                'count': len(array), 'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[width]})
        return len(new['accessors'])-1
    generated = {key: [] for key in values}; cut_indices = {role: [] for role in ROLES}
    groups = {(branch, role): [] for branch in ('whole', 'cut') for role in ROLES}
    for face, role in roles.items(): groups[('whole', role)].append((face, np.eye(3)))
    vertex_lookup = {}
    for face, (_, polygons) in plans.items():
        for role, triangles in polygons.items():
            for triangle in triangles:
                indices = []
                for weights in triangle:
                    key = (face, tuple(weights))
                    if key not in vertex_lookup:
                        derived, corner = new_corner(body_archive, face, weights, canonical)
                        vertex_lookup[key] = len(generated['POSITION'])
                        if corner >= 0:
                            for semantic in generated: generated[semantic].append(values[semantic][faces[face, corner]].copy())
                        else:
                            generated['POSITION'].append(derived['positions'] @ BASIS)
                            generated['NORMAL'].append(derived['normals'] @ BASIS)
                            generated['TEXCOORD_0'].append(derived['uvGltf'])
                            generated['TANGENT'].append(np.r_[derived['tangents'][:3] @ BASIS, derived['tangents'][3]])
                    indices.append(vertex_lookup[key])
                cut_indices[role].append(indices); groups[('cut', role)].append((face, triangle))
    cut_attrs = {semantic: append(array) for semantic, array in generated.items()} if plans else None
    output_primitives = []; output_archive = {key: [] for key in CORNER_KEYS | {'tangents'}}
    parents = []; barycentrics = []; corner_orders = []; source_rows = []; primitive_ids = []
    correspondence = []; records = []
    for branch, role in [('whole', 'skin'), ('whole', 'garment'), ('cut', 'skin'), ('cut', 'garment')]:
        group = groups[(branch, role)]
        if not group: continue
        if output_primitives and len(output_primitives) == 1:
            output_primitives.extend(copy.deepcopy(doc['meshes'][0]['primitives'][1:3]))
        indices = np.asarray([faces[face] for face, _ in group] if branch == 'whole' else cut_indices[role], dtype=np.uint32).reshape(-1)
        output_primitive = copy.deepcopy(primitive)
        output_primitive.update(indices=append(indices, 5125), attributes=primitive['attributes'].copy() if branch == 'whole' else cut_attrs.copy(),
                                material=0 if role == 'skin' else garment_material)
        output_id = len(output_primitives); output_primitives.append(output_primitive)
        correspondence.append({'outputPrimitive': output_id, 'branch': branch, 'role': role, 'triangles': len(group)})
        for face, triangle in group:
            current = {key: [] for key in output_archive}; orders = []; accessor_rows = []
            for weights in triangle:
                derived, corner = new_corner(body_archive, face, weights, canonical) if branch == 'cut' else (
                    {key: body_archive[key][face, int(np.argmax(weights))].copy() for key in output_archive}, int(np.argmax(weights)))
                for key in current: current[key].append(derived[key])
                orders.append(corner); accessor_rows.append(int(faces[face, corner]) if corner >= 0 else -1)
            for key in output_archive: output_archive[key].append(current[key])
            parents.append(face); barycentrics.append(triangle); corner_orders.append(orders); source_rows.append(accessor_rows); primitive_ids.append(output_id)
            records.append({'parentBodyFaceId': face, 'originalSourceFaceId': int(original_ids[face]), 'role': role,
                            'branch': branch, 'barycentricCorners': triangle.tolist(), 'areaFraction': area_fraction(triangle)})
    if len(output_primitives) == 1: output_primitives.extend(copy.deepcopy(doc['meshes'][0]['primitives'][1:3]))
    new['meshes'][0]['primitives'] = output_primitives; new['buffers'][0]['byteLength'] = len(blob)
    parents = np.asarray(parents, dtype=np.int64)
    archive = {key: np.asarray(value, dtype=np.float64) for key, value in output_archive.items()}
    archive.update(primitiveIds=np.asarray(primitive_ids, dtype=np.int64), parentBodyFaceIds=parents,
                   originalSourceFaceIds=original_ids[parents], sourceTriangleIds=body_archive['sourceTriangleIds'][parents],
                   sourceCornerOrder=np.asarray(corner_orders, dtype=np.int64),
                   originalSourceAccessorRows=np.asarray(source_rows, dtype=np.int64),
                   parentBodyCornerBarycentrics=np.asarray(barycentrics, dtype=np.float64),
                   originalSourceCornerBarycentrics=np.asarray(barycentrics, dtype=np.float64),
                   tangentTriangleIds=np.arange(len(parents), dtype=np.int64))
    lineage.verify_unchanged_storage(new, bytes(blob), doc, binary)
    projected = copy.deepcopy(new); projected['meshes'][0]['primitives'] = [new['meshes'][0]['primitives'][row['outputPrimitive']] for row in correspondence]
    p, n, uv, _ = raw_corners(projected, bytes(blob))
    error_p = float(np.max(abs(p-archive['positions']))); error_n = float(np.max(abs(n-archive['normals'])))
    decoded_body = {semantic: np.concatenate([accessor(new, bytes(blob), p['attributes'][semantic])[
        accessor(new, bytes(blob), p['indices']).reshape(-1, 3)] for p in projected['meshes'][0]['primitives']]) for semantic in diagnostic.SEMANTICS}
    decoded_t = decoded_body['TANGENT'].astype(float); decoded_t[:, :, :3] = decoded_t[:, :, :3] @ BASIS.T
    error_t = float(np.max(abs(decoded_t-archive['tangents'])))
    contract.require(error_p <= 1e-6 and error_n <= 1e-6 and np.max(abs(uv-archive['uvGltf'])) <= 6e-8 and
                     error_t <= 1e-6 and np.array_equal(decoded_t[:, :, 3], archive['tangents'][:, :, 3]),
                     'Body serialized P/N/UV/tangent/sign transport bounds exceeded')
    original_mask = archive['sourceCornerOrder'] >= 0
    for semantic in diagnostic.SEMANTICS:
        contract.require(decoded_body[semantic][original_mask].tobytes() ==
                         values[semantic][archive['originalSourceAccessorRows'][original_mask]].tobytes(),
                         'An original serialized body corner changed: '+semantic)
    grouped = {}
    for out, face in enumerate(parents): grouped.setdefault(int(face), []).append(out)
    max_area_error = 0.; max_plane_error = 0.
    for face in range(len(faces)):
        parent_points = body_archive['positions'][face]; child = archive['positions'][grouped[face]]
        cross = np.cross(parent_points[1]-parent_points[0], parent_points[2]-parent_points[0]); area2 = float(np.linalg.norm(cross))
        contract.require(area2 > 1e-14, 'Degenerate original body plane rejected')
        crosses = np.cross(child[:, 1]-child[:, 0], child[:, 2]-child[:, 0])
        area_error = abs(float(np.linalg.norm(crosses, axis=1).sum())/area2-1)
        plane_error = float(np.max(abs((child-parent_points[0])@(cross/area2))))
        contract.require(np.all(crosses@cross > 0) and area_error <= 1e-10 and plane_error <= 1e-12,
                         'Body winding/plane/area footprint conservation failed')
        max_area_error = max(max_area_error, area_error); max_plane_error = max(max_plane_error, plane_error)
    proof = {'originalBinPrefixExact': True, 'originalAccessorViewDefinitionsExact': True, 'originalMaterialsAndMapsExact': True,
             'capPrimitiveIdsUnchanged': [1, 2], 'capDescriptorsSerializedExact': True, 'capAttributesIndicesBytesExact': True,
             'capPrimitiveDescriptorSha256': lineage.json_sha(doc['meshes'][0]['primitives'][1:3]),
             'neutralCapMaterialDescriptorSha256': lineage.json_sha(doc['materials'][1]),
             'inactiveStoredRowsPreservedExact': True, 'unchangedWholeBodyAttributesExact': True, 'originalCutCornersCopiedExact': True,
             'primitiveCorrespondence': correspondence, 'bodyTrianglesBefore': len(faces), 'bodyTrianglesAfter': len(parents),
             'capTriangles': len(cap_archive['primitiveIds']), 'cutParentBodyFaceIds': list(plans), 'subtriangles': records,
             'disjointExhaustiveBodyFootprintConservation': True, 'conformingGeometricEdgeCuts': True,
             'maximumAreaFractionError': max_area_error, 'maximumPlaneDeviationMetres': max_plane_error,
             'maximumPositionFloat32ErrorMetres': error_p, 'maximumNormalFloat32Error': error_n, 'maximumTangentFloat32Error': error_t, 'tangentSignsExact': True,
             'parentFaceLayoutSha256': face_layout_sha(rows), 'bodyMaterialRoles': {'0': 'skin', '2': 'garment'},
             'capMaterialRole': 'unowned-neutral-diagnostic-cap', 'fixedGarmentOpaque': True, 'garmentOwner': 'pelvis',
             'statureApplicationsAdded': 0, 'historicalFitReapplied': False, 'attachmentFrameReapplied': False,
             'bodyArchiveDomain': 'original-proper-fit-float64-body-corners-with-explicit-source-barycentrics',
             'capArchiveDomain': 'generated-cap-serialized-gltf-float32-corners; no original-body barycentric ancestry',
             'newCornerPolicy': 'Only new corners: barycentric P/UV/sourceP/sourceUV; normalized nondegenerate N/sourceN; Gram-Schmidt normalized T with unanimous original W. Original stored/cut corners exact. Existing proper GLTF/NWN BASIS rotation only.'}
    return new, bytes(blob), archive, {key: value.copy() for key, value in cap_archive.items()}, proof


def execute(config_path, output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    allowed = {'schemaVersion', 'kind', 'diagnosticOnly', 'coordinateSpace', 'part', 'targetContract',
               'sourceDiagnosticReceipt', 'cutMap', 'sharedToolchain', 'migrationReceipt', 'protectedInputs', 'notes'}
    contract.require(set(config) <= allowed and config.get('schemaVersion') == 2 and
                     config.get('kind') == 'target-diagnostic-pelvis-body-segmentation' and config.get('diagnosticOnly') is True and
                     config.get('coordinateSpace') == 'working' and config.get('part') == 'pelvis', 'Explicit working diagnostic body segmentation config required')
    diagnostic.no_acceptance(config); inputs = {str(config_path): contract.sha(config_path)}
    target_path = diagnostic.pin(config['targetContract'], inputs); target = contract.load(target_path)
    toolchain = diagnostic.pin(config['sharedToolchain'], inputs); migration = diagnostic.pin(config['migrationReceipt'], inputs)
    shared_toolchain.load(toolchain, migration)
    parent_path = diagnostic.pin(config['sourceDiagnosticReceipt'], inputs); parent = lineage.prepare_parent(parent_path, target_path, target)
    inputs.update(parent['inputs']); cut_path = diagnostic.pin(config['cutMap'], inputs)
    selection = json.loads(cut_path.read_text(encoding='utf-8'))
    lineage.reviewed_body_map(selection, parent['rows'], parent['originalIds'])
    lineage.verify_map_bindings(selection, parent, parent_path, target_path, inputs)
    for item in config.get('protectedInputs', []): diagnostic.pin(item, inputs)
    new, blob, body, caps, proof = subdivide_body(parent['doc'], parent['binary'], parent['body'], parent['caps'], parent['originalIds'], selection)
    for name in ('segment_target_diagnostic_pelvis_body.py', 'target_diagnostic_material_lineage.py', 'target_diagnostic_lineage.py',
                 'segment_target_pelvis_boundary.py', 'partition_target_pelvis_materials.py', 'target_contract.py',
                 'target_part_pipeline.py', 'mirror_stock_limb_part.py', 'place_purposebuilt_pelvis.py', 'shared_toolchain.py'):
        path = Path(__file__).with_name(name); inputs[str(path)] = contract.sha(path)
    output = Path(output).resolve()
    contract.require(ARTIFACT_ROOT.resolve() in output.parents and not output.exists(), 'Fresh diagnostic artifact output required')
    # All source/map/structural checks precede the first output creation.
    for path, expected in inputs.items(): diagnostic.pin({'path': path, 'sha256': expected}, {})
    output.mkdir(parents=True); candidate = output/'candidate-local.glb'; write_glb(candidate, new, blob)
    actual, actual_blob = read_glb(candidate)
    contract.require(actual == new and actual_blob == blob, 'Append-only serialized candidate differs')
    paths = {}
    for name, archive in [('body-float64-derived-corners', body), ('cap-serialized-float32-corners', caps)]:
        path = output/(name+'.npz'); np.savez_compressed(path, **archive)
        with np.load(path, allow_pickle=False) as reopened:
            contract.require(set(reopened.files) == set(archive) and all(reopened[key].dtype == value.dtype and
                             reopened[key].tobytes() == value.tobytes() for key, value in archive.items()), 'Serialized provenance archive differs')
        paths[name] = {'path': str(path), 'sha256': contract.sha(path)}
    receipt = {'schemaVersion': 2, 'kind': lineage.KIND, 'operation': lineage.OPERATION,
               **contract.binding(target_path, target, 'working'), 'part': 'pelvis', 'joint': 'pelvis_g', 'model': parent['receipt']['model'],
               'sourceDiagnosticReceipt': {'path': str(parent_path), 'sha256': contract.sha(parent_path)},
               'sourceCandidate': {'path': parent['receipt']['candidate'], 'sha256': parent['receipt']['candidateSha256']},
               'cutMap': {'path': str(cut_path), 'sha256': contract.sha(cut_path)}, 'rootBodyMapReview': selection['rootReview'],
               'candidate': str(candidate), 'candidateSha256': contract.sha(candidate),
               'bodyFloat64DerivedCornerArchive': paths['body-float64-derived-corners'],
               'capSerializedFloat32CornerArchive': paths['cap-serialized-float32-corners'],
               'statureApplications': 0, 'candidateToAttachmentLocal': np.eye(4).tolist(),
               'fitSourceToAttachmentLocal': parent['receipt']['fitSourceToAttachmentLocal'],
               'attachmentWorld': parent['receipt']['attachmentWorld'], 'primitive1And2Mode': lineage.CAP_MODE,
               'proof': proof, 'parentPendingTopology': parent['pendingTopology'], 'pendingRisks': parent['summary']['pendingRisks'],
               'diagnosticOnly': True, 'bodyRoleAssignmentReviewed': True, 'canonicalNativeLineage': False,
               **{flag: False for flag in lineage.FLAGS}, 'frozenInputs': inputs,
               'limitation': 'Only original body role cuts/partition reviewed. Neutral caps, topology, visible paint boundary, PLT/shader/native transport, collision and client remain pending. Existing canonical/preview/stage readers reject this separate kind.'}
    diagnostic.no_acceptance(receipt)
    for path, expected in inputs.items(): diagnostic.pin({'path': path, 'sha256': expected}, {})
    shutil.copyfile(__file__, output/'executed-helper.py')
    receipt_path = output/'diagnostic-material-geometry.json'; receipt_path.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return receipt_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--config', type=Path)
    group.add_argument('--inspect-source-receipt', type=Path, help='Read-only typed input-domain proof; never cuts/exports candidate')
    parser.add_argument('--target-contract', type=Path, help='Required only for read-only inspection')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.config:
        contract.require(args.target_contract is None, 'Config owns exact target binding')
        print(execute(args.config, args.output))
    else:
        contract.require(args.target_contract is not None, 'Explicit inspection target required')
        parent = lineage.prepare_parent(args.inspect_source_receipt, args.target_contract, contract.load(args.target_contract))
        for name in ('segment_target_diagnostic_pelvis_body.py', 'target_diagnostic_material_lineage.py',
                     'target_diagnostic_lineage.py', 'segment_target_pelvis_boundary.py',
                     'partition_target_pelvis_materials.py', 'place_purposebuilt_pelvis.py', 'target_contract.py'):
            path = Path(__file__).with_name(name); parent['inputs'][str(path)] = contract.sha(path)
        result = {'schemaVersion': 2, 'kind': 'diagnostic-pelvis-body-material-input-domain-proof',
                  'diagnosticOnly': True, 'sourceCandidateChanged': False, 'bodyCutsExecuted': False,
                  'bodyFaceCount': len(parent['originalIds']), 'originalBodyIds': diagnostic.fingerprint(parent['originalIds']),
                  'bodyFloat64Arrays': {key: diagnostic.fingerprint(value) for key, value in parent['body'].items()},
                  'separateGeneratedCapArrays': {key: diagnostic.fingerprint(value) for key, value in parent['caps'].items()},
                  'parentFaceLayoutSha256': face_layout_sha(parent['rows']), 'pendingTopology': parent['pendingTopology'],
                  'inputs': parent['inputs'], **{flag: False for flag in lineage.FLAGS}}
        output = args.output.resolve()
        contract.require(ARTIFACT_ROOT.resolve() in output.parents and not output.exists(), 'Fresh artifact inspection output required')
        output.mkdir(parents=True); path = output/'input-domain-proof.json'; path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(path)


if __name__ == '__main__': main()