"""Subdivide only explicitly reviewed pelvis material-boundary triangles.

Supported: one canonical working-space primitive with float P/N/UV0/TANGENT,
one straight edge-to-edge chord per crossing face, conforming closed contours.
No image classifier, curve inference, fit operation or stature conversion.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

import shared_toolchain
import target_contract as contract
from partition_target_pelvis_materials import active_faces, face_layout_sha
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, raw_corners, read_glb, write_glb
from target_part_pipeline import generation_source, pin, read_target, verify_source_receipt
from target_part_stage import material_inputs

ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / 'output/phenotypes'
ROLES = ('skin', 'garment')
CORNER_KEYS = {'positions', 'normals', 'uvNative', 'uvGltf', 'sourcePositions', 'sourceNormals', 'sourceUVNative'}
TOL = 1e-12


def bary(value):
    row = np.asarray(value, dtype=float)
    contract.require(row.shape == (3,) and np.isfinite(row).all() and np.all(row >= 0)
                     and np.all(row <= 1) and abs(float(row.sum()) - 1) <= TOL,
                     'Finite unit-simplex barycentric coordinates required')
    return row


def area_fraction(triangle):
    return float(np.linalg.det(np.asarray(triangle, dtype=float)))


def same_cycle(actual, expected):
    return actual.shape == expected.shape and any(np.array_equal(actual, np.roll(expected, shift, axis=0))
                                                  for shift in range(len(expected)))


def cut_polygons(item):
    contract.require(set(item) == {'sourceFaceId', 'boundarySegment', 'skinPolygon', 'garmentPolygon'},
                     'Only explicit source-face chord and role polygons supported')
    endpoints = np.asarray([bary(value) for value in item['boundarySegment']])
    contract.require(endpoints.shape == (2, 3), 'One two-endpoint straight boundary segment required')
    zeros = []
    for row in endpoints:
        ids = np.flatnonzero(row == 0)
        contract.require(len(ids) == 1 and np.all(row[np.flatnonzero(row)] > TOL),
                         'Boundary endpoints must lie strictly inside triangle edges')
        zeros.append(int(ids[0]))
    contract.require(zeros[0] != zeros[1], 'Boundary chord must join two distinct triangle edges')
    cycle = []
    corners = np.eye(3)
    for index in range(3):
        cycle.append(corners[index])
        opposite = (index + 2) % 3
        for endpoint, zero in zip(endpoints, zeros):
            if zero == opposite:
                cycle.append(endpoint)
    cycle = np.asarray(cycle)
    first = next(index for index, row in enumerate(cycle) if np.array_equal(row, endpoints[0]))
    second = next(index for index, row in enumerate(cycle) if np.array_equal(row, endpoints[1]))
    def between(start, end):
        result = [cycle[start]]
        while start != end:
            start = (start + 1) % len(cycle)
            result.append(cycle[start])
        return np.asarray(result)
    expected = [between(first, second), between(second, first)]
    actual = [np.asarray([bary(value) for value in item[role + 'Polygon']]) for role in ROLES]
    matches = [next((index for index, shape in enumerate(expected) if same_cycle(polygon, shape)), None)
               for polygon in actual]
    contract.require(None not in matches and set(matches) == {0, 1},
                     'Role polygons must exactly form the two oriented chord regions; overlaps/gaps/extra vertices rejected')
    result = {}
    fractions = []
    for role, polygon in zip(ROLES, actual):
        triangles = [np.asarray([polygon[0], polygon[index], polygon[index + 1]])
                     for index in range(1, len(polygon) - 1)]
        areas = [area_fraction(row) for row in triangles]
        contract.require(all(value > TOL for value in areas), 'Positive nondegenerate oriented role triangles required')
        result[role] = triangles
        fractions.extend(areas)
    contract.require(abs(sum(fractions) - 1) <= TOL, 'Disjoint exhaustive triangle footprint conservation failed')
    return endpoints, result


def reviewed_map(selection, rows):
    allowed = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'targetContractSha256', 'targetId',
               'rigRevision', 'coordinateSpace', 'part', 'joint', 'model', 'source', 'sourceSha256',
               'sourceReceipt', 'sourceReceiptSha256', 'faceIdSpace', 'primitiveFaceCounts',
               'sourceFaceLayoutSha256', 'skinFaceIds', 'garmentFaceIds', 'cutFaces', 'ambiguousFaceIds', 'review'}
    contract.require(set(selection) <= allowed, 'Unknown/automatic classification or geometry controls rejected')
    count = len(rows[0][2])
    contract.require(type(selection.get('primitiveFaceCounts')) is list and len(selection['primitiveFaceCounts']) == 1
                     and type(selection['primitiveFaceCounts'][0]) is int,
                     'Explicit integer primitive face count required')
    contract.require(selection.get('faceIdSpace') == 'parent-active-primitive-order'
                     and selection.get('primitiveFaceCounts') == [count]
                     and selection.get('sourceFaceLayoutSha256') == face_layout_sha(rows),
                     'Exact current parent face layout required')
    review = selection.get('review', {})
    contract.require(type(review) is dict and set(review) <= {'reviewed', 'reviewedBy', 'scope', 'notes', 'evidence', 'sourceTopologyResolved'}
                     and review.get('reviewed') is True and review.get('reviewedBy') == 'root'
                     and review.get('scope') == 'barycentric-pelvis-boundary-segmentation'
                     and review.get('sourceTopologyResolved') is True
                     and isinstance(review.get('notes'), str) and bool(review['notes'].strip()),
                     'Explicit root-reviewed boundary map and resolved-source topology declaration required')
    contract.require(selection.get('ambiguousFaceIds') == [], 'Ambiguous faces cannot be waived')
    roles = {}
    for role in ROLES:
        ids = selection.get(role + 'FaceIds')
        contract.require(type(ids) is list and all(type(value) is int and 0 <= value < count for value in ids)
                         and all(a < b for a, b in zip(ids, ids[1:])), 'Ordered explicit whole-face IDs required')
        for value in ids:
            contract.require(value not in roles, 'Duplicated/overlapping whole-face role')
            roles[value] = role
    cuts = selection.get('cutFaces')
    contract.require(type(cuts) is list and bool(cuts), 'At least one explicitly declared crossing face required')
    plans = {}
    for item in cuts:
        face_id = item.get('sourceFaceId')
        contract.require(type(face_id) is int and 0 <= face_id < count and face_id not in roles and face_id not in plans,
                         'Distinct in-range crossing face IDs required')
        plans[face_id] = cut_polygons(item)
    contract.require(list(plans) == sorted(plans) and sorted([*roles, *plans]) == list(range(count)),
                     'Root map must disjointly and exhaustively cover every parent face')
    return roles, plans


def edge_keys(points):
    return [tuple(float(value) for value in row) for row in points]


def conforming_edges(positions, plans):
    edge_faces = {}
    for face_id, triangle in enumerate(positions):
        keys = edge_keys(triangle)
        for index in range(3):
            pair = tuple(sorted((keys[index], keys[(index + 1) % 3])))
            edge_faces.setdefault(pair, []).append(face_id)
    endpoint_records = {}
    canonical = {}
    for face_id, (endpoints, _) in plans.items():
        keys = edge_keys(positions[face_id])
        for endpoint in endpoints:
            nonzero = np.flatnonzero(endpoint)
            lower, upper = sorted(nonzero, key=lambda index: keys[index])
            pair = (keys[lower], keys[upper])
            fraction = float(endpoint[upper])
            key = (pair, fraction)
            endpoint_records.setdefault(pair, []).append((face_id, fraction))
            canonical[key] = np.asarray(pair[0]) * (1 - fraction) + np.asarray(pair[1]) * fraction
    for pair, records in endpoint_records.items():
        neighbors = edge_faces[pair]
        contract.require(len(neighbors) == 2 and len(records) == 2 and sorted(face for face, _ in records) == sorted(neighbors)
                         and records[0][1] == records[1][1],
                         'Every cut must match its adjacent geometric edge exactly; hanging/nonmanifold/open cuts rejected')
        # Each side must agree which original geometric endpoint lies in skin.
        for vertex in pair:
            vertex_roles = []
            for face_id in neighbors:
                triangle_keys = edge_keys(positions[face_id])
                corner = np.eye(3)[triangle_keys.index(vertex)]
                polygons = plans[face_id][1]
                found = [role for role, tris in polygons.items() if any(np.array_equal(row, corner) for tri in tris for row in tri)]
                contract.require(len(found) == 1, 'Unambiguous endpoint material role required')
                vertex_roles.append(found[0])
            contract.require(vertex_roles[0] == vertex_roles[1], 'Adjacent boundary role polygons conflict')
    return canonical


def checked_archive(parent, faces, doc, binary):
    required = CORNER_KEYS | {'primitiveIds', 'sourceTriangleIds', 'sourceCornerOrder', 'tangents', 'tangentTriangleIds'}
    allowed = required | {'addedConnectorMask', 'addedSourceVertexFaces'}
    count = len(faces)
    contract.require(required <= set(parent) and set(parent) <= allowed, 'Known complete proper-fit/repaired corner archive required')
    for key in CORNER_KEYS:
        width = 2 if key in ('uvNative', 'uvGltf', 'sourceUVNative') else 3
        contract.require(parent[key].shape == (count, 3, width) and parent[key].dtype == np.float64
                         and np.isfinite(parent[key]).all(), 'Authoritative float64 corner rows required: ' + key)
    contract.require(np.array_equal(parent['primitiveIds'], np.zeros(count, dtype=np.int64))
                     and parent['sourceTriangleIds'].shape == (count,) and np.issubdtype(parent['sourceTriangleIds'].dtype, np.integer)
                     and np.all(parent['sourceTriangleIds'] >= -1)
                     and np.array_equal(parent['sourceCornerOrder'], np.tile([0, 1, 2], (count, 1)))
                     and np.array_equal(parent['tangentTriangleIds'], np.arange(count))
                     and parent['tangents'].shape == (count, 3, 4) and parent['tangents'].dtype == np.float64
                     and np.isfinite(parent['tangents']).all(), 'Exact original ordered parent corner/tangent provenance required')
    primitive = doc['meshes'][0]['primitives'][0]
    values = {key: accessor(doc, binary, index) for key, index in primitive['attributes'].items()}
    p, n, uv, _ = raw_corners(doc, binary)
    contract.require(np.array_equal(uv, parent['uvGltf']) and np.array_equal(parent['uvNative'][:, :, 1], 1 - parent['uvGltf'][:, :, 1])
                     and np.array_equal(parent['uvNative'][:, :, 0], parent['uvGltf'][:, :, 0]), 'Parent UV provenance differs')
    contract.require(np.max(abs(p - parent['positions'])) <= 1e-6 and np.max(abs(n - parent['normals'])) <= 1e-6,
                     'Serialized P/N differs from authoritative parent')
    tangent = values['TANGENT'][faces].astype(float); tangent[:, :, :3] = tangent[:, :, :3] @ BASIS.T
    contract.require(np.max(abs(tangent - parent['tangents'])) <= 1e-6, 'Serialized tangent basis differs from authoritative parent')
    # A serialized source row may be shared, but distinct rows at UV seams are
    # never coordinate-welded for attribute transport.
    first_seen = {}
    for face_id, row in enumerate(faces):
        for corner, vertex in enumerate(row):
            current = (face_id, corner)
            first = first_seen.setdefault(int(vertex), current)
            if first != current:
                for key in CORNER_KEYS | {'tangents'}:
                    contract.require(np.array_equal(parent[key][current], parent[key][first]), 'Conflicting shared-vertex authoritative rows')
    if 'addedConnectorMask' in parent:
        contract.require(parent['addedConnectorMask'].shape == (count,) and parent['addedConnectorMask'].dtype == np.bool_
                         and parent['addedSourceVertexFaces'].ndim == 2 and parent['addedSourceVertexFaces'].shape[1] == 3,
                         'Known repaired connector provenance required')
    else:
        contract.require('addedSourceVertexFaces' not in parent and np.all(parent['sourceTriangleIds'] >= 0), 'Missing repaired cap provenance')
    return values


def new_corner(parent, face_id, weights, canonical):
    original = np.flatnonzero(weights == 1)
    if len(original) == 1:
        corner = int(original[0])
        return {key: parent[key][face_id, corner].copy() for key in CORNER_KEYS | {'tangents'}}, corner
    result = {key: weights @ parent[key][face_id] for key in CORNER_KEYS}
    normal = result['normals']
    source_normal = result['sourceNormals']
    contract.require(np.linalg.norm(normal) > 1e-10 and np.linalg.norm(source_normal) > 1e-10,
                     'Degenerate interpolated normal rejected')
    result['normals'] = normal / np.linalg.norm(normal)
    result['sourceNormals'] = source_normal / np.linalg.norm(source_normal)
    tangent = parent['tangents'][face_id]
    contract.require(np.all(abs(tangent[:, 3]) == 1) and np.all(tangent[:, 3] == tangent[0, 3]), 'Ambiguous tangent handedness rejected')
    t = weights @ tangent[:, :3]
    t -= result['normals'] * float(t @ result['normals'])
    contract.require(np.linalg.norm(t) > 1e-10, 'Degenerate interpolated tangent basis rejected')
    result['tangents'] = np.r_[t / np.linalg.norm(t), tangent[0, 3]]
    keys = edge_keys(parent['positions'][face_id]); nonzero = np.flatnonzero(weights)
    lower, upper = sorted(nonzero, key=lambda index: keys[index])
    result['positions'] = canonical[((keys[lower], keys[upper]), float(weights[upper]))].copy()
    result['uvNative'] = result['uvGltf'].copy(); result['uvNative'][1] = 1 - result['uvNative'][1]
    return result, -1


def segment(doc, binary, parent_archive, selection, part='pelvis'):
    contract.require(part == 'pelvis', 'Fixed opaque garment belongs only to pelvis')
    rows = active_faces(doc, binary)
    contract.require(len(rows) == 1, 'Initially only one canonical active primitive supported')
    _, primitive, faces = rows[0]
    contract.require(set(primitive['attributes']) == {'POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT'},
                     'Only float P/N/UV0/TANGENT supported; COLOR/missing/unknown attributes rejected')
    for index in primitive['attributes'].values():
        item = doc['accessors'][index]
        contract.require(item['componentType'] == 5126 and not item.get('normalized') and not item.get('sparse'), 'Unnormalized float attributes required')
    values = checked_archive(parent_archive, faces, doc, binary)
    roles, plans = reviewed_map(selection, rows)
    canonical = conforming_edges(parent_archive['positions'], plans)
    material = primitive['material']; descriptor = doc['materials'][material]
    contract.require(descriptor.get('alphaMode', 'OPAQUE') == 'OPAQUE'
                     and descriptor.get('pbrMetallicRoughness', {}).get('baseColorFactor', [1, 1, 1, 1]) == [1, 1, 1, 1],
                     'Original fixed garment material must be opaque with unchanged base factor')
    new = copy.deepcopy(doc); blob = bytearray(binary)
    material_roles = {material: 'skin'}
    new['materials'].append(copy.deepcopy(descriptor)); garment_material = len(new['materials']) - 1
    material_roles[garment_material] = 'garment'
    def append(array, component=5126):
        array = np.asarray(array, dtype='<f4' if component == 5126 else '<u4')
        contract.require(np.isfinite(array).all(), 'Serialization overflow/nonfinite attributes rejected')
        blob.extend(b'\0' * (-len(blob) % 4)); offset = len(blob); blob.extend(array.tobytes()); blob.extend(b'\0' * (-len(blob) % 4))
        new['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': array.nbytes})
        width = array.shape[1] if array.ndim == 2 else 1
        new['accessors'].append({'bufferView': len(new['bufferViews']) - 1, 'componentType': component,
                                 'count': len(array), 'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[width]})
        return len(new['accessors']) - 1
    generated = {key: [] for key in values}; cut_indices = {role: [] for role in ROLES}
    triangle_records = {('whole', role): [] for role in ROLES} | {('cut', role): [] for role in ROLES}
    for face_id, role in roles.items():
        triangle_records[('whole', role)].append((face_id, np.eye(3)))
    vertex_lookup = {}
    for face_id, (_, polygons) in plans.items():
        for role, triangles in polygons.items():
            for triangle in triangles:
                output_indices = []
                for weights in triangle:
                    key = (face_id, tuple(weights))
                    if key not in vertex_lookup:
                        derived, original_corner = new_corner(parent_archive, face_id, weights, canonical)
                        index = len(generated['POSITION']); vertex_lookup[key] = index
                        if original_corner >= 0:
                            source_vertex = int(faces[face_id, original_corner])
                            for semantic in generated:
                                generated[semantic].append(values[semantic][source_vertex].copy())
                        else:
                            generated['POSITION'].append(derived['positions'] @ BASIS)
                            generated['NORMAL'].append(derived['normals'] @ BASIS)
                            generated['TEXCOORD_0'].append(derived['uvGltf'])
                            generated['TANGENT'].append(np.r_[derived['tangents'][:3] @ BASIS, derived['tangents'][3]])
                    output_indices.append(vertex_lookup[key])
                cut_indices[role].append(output_indices)
                triangle_records[('cut', role)].append((face_id, triangle))
    cut_attrs = {semantic: append(array) for semantic, array in generated.items()}
    output_primitives = []; correspondence = []; records = []; output_archive = {key: [] for key in CORNER_KEYS | {'tangents'}}
    parent_ids = []; bary_rows = []; corner_orders = []; primitive_ids = []
    for branch in ('whole', 'cut'):
        for role in ROLES:
            group = triangle_records[(branch, role)]
            if not group:
                continue
            indices = np.asarray([faces[face] for face, _ in group] if branch == 'whole' else cut_indices[role], dtype=np.uint32).reshape(-1)
            output_primitive = copy.deepcopy(primitive)
            output_primitive['indices'] = append(indices, 5125)
            output_primitive['attributes'] = primitive['attributes'].copy() if branch == 'whole' else cut_attrs.copy()
            output_primitive['material'] = material if role == 'skin' else garment_material
            output_id = len(output_primitives); output_primitives.append(output_primitive)
            correspondence.append({'outputPrimitive': output_id, 'branch': branch, 'role': role, 'triangles': len(group),
                                    'outputAttributeAccessors': output_primitive['attributes'], 'outputIndexAccessor': output_primitive['indices']})
            for face_id, triangle in group:
                current = {key: [] for key in output_archive}; orders = []
                for weights in triangle:
                    derived, original_corner = new_corner(parent_archive, face_id, weights, canonical) if branch == 'cut' else (
                        {key: parent_archive[key][face_id, int(np.argmax(weights))].copy() for key in output_archive}, int(np.argmax(weights)))
                    for key in current:
                        current[key].append(derived[key])
                    orders.append(original_corner)
                for key in output_archive:
                    output_archive[key].append(current[key])
                parent_ids.append(face_id); bary_rows.append(triangle); corner_orders.append(orders); primitive_ids.append(output_id)
                records.append({'parentFaceId': face_id, 'role': role, 'branch': branch, 'barycentricCorners': triangle.tolist(),
                                'areaFraction': area_fraction(triangle)})
    new['meshes'][0]['primitives'] = output_primitives; new['buffers'][0]['byteLength'] = len(blob)
    parent_ids = np.asarray(parent_ids, dtype=np.int64)
    archive = {key: np.asarray(value, dtype=np.float64) for key, value in output_archive.items()}
    archive.update(primitiveIds=np.asarray(primitive_ids, dtype=np.int64), parentTriangleIds=parent_ids,
                   parentPrimitiveIds=parent_archive['primitiveIds'][parent_ids], sourceTriangleIds=parent_archive['sourceTriangleIds'][parent_ids],
                   sourceCornerOrder=np.asarray(corner_orders, dtype=np.int64), parentCornerBarycentrics=np.asarray(bary_rows, dtype=np.float64),
                   tangentTriangleIds=np.arange(len(parent_ids), dtype=np.int64))
    if 'addedConnectorMask' in parent_archive:
        archive['addedConnectorMask'] = parent_archive['addedConnectorMask'][parent_ids].copy()
        archive['parentAddedSourceVertexFaces'] = parent_archive['addedSourceVertexFaces'].copy()
    contract.require(blob[:len(binary)] == binary and new['accessors'][:len(doc['accessors'])] == doc['accessors']
                     and new['bufferViews'][:len(doc['bufferViews'])] == doc['bufferViews'], 'Original BIN/accessor/view prefixes changed')
    for key in ('images', 'textures', 'samplers'):
        contract.require(new.get(key) == doc.get(key), 'Original atlas bindings changed')
    contract.require(new['materials'][:len(doc['materials'])] == doc['materials']
                     and embedded_maps(new, blob) == embedded_maps(doc, binary), 'Original materials/maps changed')
    p, n, uv, _ = raw_corners(new, bytes(blob))
    error_p = float(np.max(abs(p - archive['positions']))); error_n = float(np.max(abs(n - archive['normals'])))
    contract.require(error_p <= 1e-6 and error_n <= 1e-6 and np.max(abs(uv - archive['uvGltf'])) <= 6e-8,
                     'Serialized derived corners exceed declared float32 transport bounds')
    grouped = {}
    for output_id, face_id in enumerate(parent_ids):
        grouped.setdefault(int(face_id), []).append(output_id)
    max_area_error = 0.; max_plane_error = 0.
    for face_id in range(len(faces)):
        ids = grouped[face_id]; parent_points = parent_archive['positions'][face_id]
        parent_cross = np.cross(parent_points[1] - parent_points[0], parent_points[2] - parent_points[0])
        parent_area2 = float(np.linalg.norm(parent_cross)); contract.require(parent_area2 > 1e-14, 'Degenerate source plane rejected')
        child = archive['positions'][ids]; crosses = np.cross(child[:, 1] - child[:, 0], child[:, 2] - child[:, 0])
        contract.require(np.all(crosses @ parent_cross > 0), 'Subtriangle winding changed')
        area_error = abs(float(np.linalg.norm(crosses, axis=1).sum()) / parent_area2 - 1)
        plane_error = float(np.max(abs((child - parent_points[0]) @ (parent_cross / parent_area2))))
        contract.require(area_error <= 1e-10 and plane_error <= 1e-12, 'Original plane/area footprint conservation failed')
        max_area_error = max(max_area_error, area_error); max_plane_error = max(max_plane_error, plane_error)
    proof = {'originalBinPrefixExact': True, 'originalAccessorViewDefinitionsExact': True, 'originalMaterialsAndMapsExact': True,
             'unaffectedAttributeAccessorsExact': True, 'originalCutCornersCopiedExact': True,
             'roleDescriptorsExactDuplicates': True, 'materialRoles': material_roles, 'primitiveCorrespondence': correspondence,
             'parentTriangles': len(faces), 'triangles': len(records), 'cutParentFaceIds': list(plans),
             'facesAdded': len(records) - len(faces), 'newCutBranchVertexRows': len(generated['POSITION']),
             'parentFaceLayoutSha256': face_layout_sha(rows), 'disjointExhaustiveFootprintConservation': True,
             'conformingGeometricEdgeCuts': True, 'maximumAreaFractionError': max_area_error,
             'maximumPlaneDeviationMetres': max_plane_error, 'maximumPositionFloat32ErrorMetres': error_p,
             'maximumNormalFloat32Error': error_n, 'subtriangles': records, 'boundarySegmentationPerformed': True,
             'statureApplicationsAdded': 0, 'fitFrameUnchanged': True, 'materialBoundaryAccepted': False,
             'newCornerPolicy': 'Authoritative parent barycentric P/UV; new N normalized linear interpolation; new T normalized Gram-Schmidt projection onto N with constant original W. Original corners remain exact. NWN/GLTF direction basis is the existing proper BASIS rotation only; no scaling/reflection.'}
    return new, bytes(blob), archive, proof


def parent_lineage(source, parent_path, target_path, target):
    parent = verify_source_receipt(source, parent_path, target_path, target, 'pelvis', 'working')
    contract.require(parent.get('diagnosticOnly') is True and parent.get('clientAccepted') is False
                     and parent.get('productionAccepted') is False and parent['model'] == contract.model(target, 'pelvis')
                     and np.array_equal(parent['attachmentWorld'], contract.frame(target, 'pelvis_g', 'working')),
                     'Unaccepted exact current pelvis/frame parent required')
    inputs = []
    fit = parent
    if parent['operation'] == 'face-repair':
        contract.require(np.array_equal(parent['sourceToAttachmentLocal'], np.eye(4)), 'Repaired parent cannot add a transform')
        fit_source = pin(parent['source'], parent['sourceSha256']); fit_path = pin(parent['sourceReceipt'], parent['sourceReceiptSha256'])
        inputs.extend((fit_source, fit_path)); fit = verify_source_receipt(fit_source, fit_path, target_path, target, 'pelvis', 'working')
        topology = parent['proof']['afterTopology']
        contract.require(all(topology[key] == 0 for key in ('boundaryEdges', 'nonmanifoldEdges', 'inconsistentManifoldEdgeWindings',
                                                           'nonmanifoldVertexLinks', 'zeroAreaFaces'))
                         and topology['components'] == 1 and topology['signedVolume'] > 0, 'Repaired topology closure proof required')
        selection = pin(parent['selectionReceipt'], parent['selectionReceiptSha256']); inputs.append(selection)
    contract.require(fit['operation'] == 'fit' and fit['proof']['reflected'] is False
                     and fit['proof']['uniformScale'] > 0 and np.isfinite(fit['proof']['uniformScale']),
                     'Original positive uniform proper fit lineage required')
    origin = pin(fit['source'], fit['sourceSha256']); job = pin(fit['sourceReceipt'], fit['sourceReceiptSha256'])
    generation_source(origin, job); inputs.extend((origin, job))
    return parent, inputs, fit['proof']


def execute(config_path, output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    allowed = {'schemaVersion', 'kind', 'diagnosticOnly', 'part', 'coordinateSpace', 'targetContract', 'targetContractSha256',
               'source', 'sourceSha256', 'sourceReceipt', 'sourceReceiptSha256', 'cutMap', 'cutMapSha256',
               'sharedToolchain', 'sharedToolchainSha256', 'migrationReceipt', 'migrationReceiptSha256', 'protectedInputs', 'notes'}
    contract.require(set(config) <= allowed and config.get('kind') == 'target-pelvis-boundary-segmentation'
                     and config.get('diagnosticOnly') is True and config.get('part') == 'pelvis'
                     and config.get('coordinateSpace') == 'working', 'Explicit working pelvis diagnostic segmentation required')
    target_path, target = read_target(config)
    contract.require(target['rig'].get('pilotAccepted') is True and target['rig'].get('offlineStructureAccepted') is True
                     and target['rig'].get('pilotAcceptanceScope') == 'offline-rig-structure', 'Actual frozen offline structural target required')
    toolchain = pin(config['sharedToolchain'], config['sharedToolchainSha256']); migration = pin(config['migrationReceipt'], config['migrationReceiptSha256'])
    shared_toolchain.load(toolchain, migration)
    source = pin(config['source'], config['sourceSha256']); parent_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    parent, lineage, fit_proof = parent_lineage(source, parent_path, target_path, target)
    cut_map = pin(config['cutMap'], config['cutMapSha256']); selection = json.loads(cut_map.read_text(encoding='utf-8'))
    contract.require(selection.get('schemaVersion') == 2 and selection.get('kind') == 'target-pelvis-boundary-cut-map'
                     and selection.get('diagnosticOnly') is True, 'Explicit immutable root boundary-cut map required')
    contract.verify_binding(selection, target_path, target, 'working')
    for key in ('part', 'joint', 'model'):
        contract.require(selection.get(key) == parent[key], 'Reviewed map ownership differs')
    contract.require(Path(selection.get('source', '')).resolve() == source and selection.get('sourceSha256') == contract.sha(source)
                     and Path(selection.get('sourceReceipt', '')).resolve() == parent_path
                     and selection.get('sourceReceiptSha256') == contract.sha(parent_path), 'Map must review exact current fitted/repaired parent')
    evidence = selection.get('review', {}).get('evidence')
    contract.require(type(evidence) is list and bool(evidence), 'Pinned explicit root-review evidence required')
    dependencies = [config_path, target_path, source, parent_path, cut_map, toolchain, migration, *lineage]
    for item in evidence:
        dependencies.append(pin(item['path'], item['sha256']))
    for name, expected in config.get('protectedInputs', {}).items():
        dependencies.append(pin(name, expected))
    corner_path = pin(parent['nativeCornerArchive']['path'], parent['nativeCornerArchive']['sha256']); dependencies.append(corner_path)
    doc, binary = read_glb(source)
    with np.load(corner_path, allow_pickle=False) as data:
        source_p, source_n, _, _ = raw_corners(doc, binary)
        contract.require(np.max(abs(source_p - data['positions'])) <= fit_proof['maximumPositionFloat32ErrorMetres'] + 1e-12
                         and np.max(abs(source_n - data['normals'])) <= fit_proof['maximumNormalFloat32Error'] + 1e-12,
                         'Current parent archive exceeds original measured fit transport errors')
        new, blob, archive, proof = segment(doc, binary, {key: data[key] for key in data.files}, selection)
    _, material_proof = material_inputs(new, blob, proof['materialRoles'], 'pelvis', 0)
    for name in ('segment_target_pelvis_boundary.py', 'partition_target_pelvis_materials.py', 'target_contract.py',
                 'target_part_pipeline.py', 'target_part_stage.py', 'mirror_stock_limb_part.py', 'place_purposebuilt_pelvis.py', 'shared_toolchain.py'):
        dependencies.append(Path(__file__).with_name(name))
    inputs = {str(path.resolve()): contract.sha(path) for path in dependencies}
    inputs.update(parent['frozenInputs'])
    output = Path(output).resolve()
    contract.require(ARTIFACT_ROOT.resolve() in output.parents and not output.exists(), 'Fresh diagnostic output inside artifact root required')
    output.mkdir(parents=True)
    candidate = output / 'candidate-local.glb'; write_glb(candidate, new, blob)
    actual, actual_blob = read_glb(candidate)
    contract.require(actual == new and actual_blob == blob, 'Serialized append-only segmentation differs')
    corners = output / 'native-corners.npz'; np.savez_compressed(corners, **archive)
    with np.load(corners, allow_pickle=False) as reopened:
        contract.require(set(reopened.files) == set(archive) and all(np.array_equal(reopened[key], value)
                         and reopened[key].dtype == value.dtype for key, value in archive.items()), 'Serialized authoritative corner archive differs')
    shutil.copyfile(__file__, output / 'executed-helper.py')
    receipt = {'schemaVersion': 2, 'kind': 'target-part-geometry', 'operation': 'material-boundary-segmentation',
               **contract.binding(target_path, target, 'working'), 'part': 'pelvis', 'joint': 'pelvis_g',
               'model': contract.model(target, 'pelvis'), 'sourcePart': 'pelvis',
               'source': str(source), 'sourceSha256': contract.sha(source), 'sourceReceipt': str(parent_path),
               'sourceReceiptSha256': contract.sha(parent_path), 'cutMap': str(cut_map), 'cutMapSha256': contract.sha(cut_map),
               'candidate': str(candidate), 'candidateSha256': contract.sha(candidate),
               'nativeCornerArchive': {'path': str(corners), 'sha256': contract.sha(corners)},
               'statureApplications': parent['statureApplications'], 'sourceToAttachmentLocal': np.eye(4).tolist(),
               'attachmentWorld': parent['attachmentWorld'], 'reflectionWorld': None, 'materialRoles': proof['materialRoles'],
               'proof': proof, 'materialBindingProof': material_proof, 'frozenInputs': inputs,
               'diagnosticOnly': True, 'rigPilotAccepted': True, 'geometryAccepted': False, 'materialBindingsAccepted': False,
               'visibleMaterialBoundaryAccepted': False, 'opaqueGarmentClientAccepted': False, 'clientAccepted': False, 'productionAccepted': False,
               'limitation': 'Explicit planar straight-chord subdivision only; painted boundary fidelity, anatomy, native shading and actual client palette/material behavior remain unaccepted.'}
    for name, expected in inputs.items():
        pin(name, expected)
    path = output / 'geometry.json'; path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = execute(args.config, args.output)
    print(json.dumps({'receipt': str(result), 'sha256': contract.sha(result), 'productionAccepted': False}))
