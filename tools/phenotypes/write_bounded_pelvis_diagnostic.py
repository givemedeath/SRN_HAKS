"""Export a separately declared, unaccepted Troll pelvis port diagnostic.

Original BIN bytes and retained source corners remain exact. New cap charts and
neutral cap material are appended; this is not the existing closed-exterior
target-part lineage and must not be sent to its staging guard as though it were.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from bounded_pelvis_connector_v2 import chart_attributes, intersect_meshes
from conservative_face_selection import mesh_arrays, topology
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, read_glb, write_glb


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


CAP_MATERIAL = {'name': 'UNACCEPTED_Troll_connector_neutral_diagnostic',
    'pbrMetallicRoughness': {'baseColorFactor': [.36, .36, .36, 1.],
                           'metallicFactor': 0., 'roughnessFactor': 1.},
    'alphaMode': 'OPAQUE', 'doubleSided': False,
    'extras': {'diagnosticOnly': True, 'materialAccepted': False,
               'purpose': 'Neutral cap-only material pending explicit Troll PLT mapping'}}


def append_accessor(doc, binary, values, semantic=None):
    values = np.asarray(values)
    if semantic == 'indices':
        values = values.astype('<u4').reshape(-1, 1); component = 5125
    else:
        values = values.astype('<f4'); component = 5126
    require(values.ndim == 2 and values.shape[1] in (1, 2, 3, 4) and np.isfinite(values).all(), 'Finite appended accessor required')
    binary += b'\0' * (-len(binary) % 4); start = len(binary); payload = values.tobytes(order='C')
    binary += payload; view = len(doc.setdefault('bufferViews', []))
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': start, 'byteLength': len(payload),
                               'target': 34963 if semantic == 'indices' else 34962})
    index = len(doc.setdefault('accessors', []))
    item = {'bufferView': view, 'componentType': component, 'count': len(values),
            'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[values.shape[1]]}
    if semantic == 'POSITION':
        item.update(min=values.min(0).astype(float).tolist(), max=values.max(0).astype(float).tolist())
    doc['accessors'].append(item)
    return binary, index


def append_diagnostic(original_document, original_binary, kept_faces, cap_attributes):
    """Append only: keep all original accessors, map bytes and body material."""
    doc = copy.deepcopy(original_document); binary = bytes(original_binary)
    _, _, old_primitive = mesh_arrays(doc, binary)
    binary, index = append_accessor(doc, binary, kept_faces, 'indices')
    doc['meshes'][0]['primitives'][0]['indices'] = index
    material = len(doc.setdefault('materials', [])); doc['materials'].append(copy.deepcopy(CAP_MATERIAL))
    for side, attributes in cap_attributes:
        attrs = {}
        for semantic in ('POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT'):
            binary, attrs[semantic] = append_accessor(doc, binary, attributes[semantic], semantic)
        binary, capindex = append_accessor(doc, binary, attributes['faces'], 'indices')
        doc['meshes'][0]['primitives'].append({'attributes': attrs, 'indices': capindex, 'mode': 4,
            'material': material, 'extras': {'diagnosticOnly': True, 'sourcePort': side,
              'originalBodyAttributesModified': False, 'chart': 'new planar original-source XZ chart'}})
    binary += b'\0' * (-len(binary) % 4); doc['buffers'][0]['byteLength'] = len(binary)
    return doc, binary


def decoded_primitives(doc, binary):
    require(len(doc['nodes']) == 1 and doc['nodes'][0].get('mesh') == 0 and not set(doc['nodes'][0])-{'mesh', 'name'}, 'One identity diagnostic node required')
    require(len(doc['meshes']) == 1 and not doc.get('animations') and not doc.get('skins'), 'Static detached diagnostic required')
    rows = []
    for primitive in doc['meshes'][0]['primitives']:
        require(primitive.get('mode', 4) == 4 and not primitive.get('extensions'), 'Uncompressed triangles required')
        attrs = {key: accessor(doc, binary, value) for key, value in primitive['attributes'].items()}
        faces = accessor(doc, binary, primitive['indices']).reshape(-1, 3).astype(np.int64)
        require(faces.min() >= 0 and faces.max() < len(attrs['POSITION']), 'Diagnostic index bounds')
        rows.append({'primitive': primitive, 'attributes': attrs, 'faces': faces})
    return rows


def preservation(original_document, original_binary, document, binary, kept_faces):
    _, _, original = mesh_arrays(original_document, original_binary)
    rows = decoded_primitives(document, binary)
    require(binary[:len(original_binary)] == original_binary, 'Original BIN prefix changed')
    fields = ('accessors', 'bufferViews', 'materials', 'images', 'textures', 'samplers')
    for key in fields:
        count = len(original_document.get(key, []))
        require(document.get(key, [])[:count] == original_document.get(key, []), 'Original '+key+' metadata changed')
    for key in ('nodes', 'scenes', 'scene', 'asset'):
        require(document.get(key) == original_document.get(key), 'Original '+key+' changed')
    updated = copy.deepcopy(rows[0]['primitive']); updated['indices'] = original['indices']
    require(updated == original, 'Original primitive material/attribute/corner ownership changed')
    require(np.array_equal(rows[0]['faces'], kept_faces), 'Retained original corner index order changed')
    require(embedded_maps(document, binary)[:len(original_document.get('images', []))] == embedded_maps(original_document, original_binary), 'Original embedded map changed')
    attributes = {}
    for key, index in original['attributes'].items():
        old = accessor(original_document, original_binary, index)
        new = rows[0]['attributes'][key]
        require(np.array_equal(old, new) and old.dtype == new.dtype, 'Original authored '+key+' changed')
        attributes[key] = {'accessor': index, 'shape': list(old.shape), 'dtype': str(old.dtype),
                           'sha256': hashlib.sha256(old.tobytes()).hexdigest()}
    return {'originalBinPrefixExact': True, 'originalBinBytes': len(original_binary),
            'originalBinSha256': hashlib.sha256(original_binary).hexdigest(),
            'originalMetadataPrefixesExact': list(fields), 'originalSceneAndIdentityNodeExact': True,
            'originalAttributes': attributes, 'retainedCornerIndicesExact': True,
            'originalEmbeddedMaps': embedded_maps(original_document, original_binary)}


def source_to_fit_raw(points, matrix):
    points = np.asarray(points, float); matrix = np.asarray(matrix, float)
    nw = points @ BASIS.T
    placed = (np.column_stack((nw, np.ones(len(nw)))) @ matrix.T)[:, :3]
    return placed @ BASIS


def shade_with_uv(positions, faces, reference_uv):
    """Geometric unit cap normals/TBN on final serialized P with fixed chart UV."""
    corners = np.asarray(positions, float)[faces]; uv = np.asarray(reference_uv, float).reshape(-1, 3, 2)
    edges = corners[:, 1:]-corners[:, :1]; normal = np.cross(edges[:, 0], edges[:, 1])
    length = np.linalg.norm(normal, axis=1); require(np.all(length > 1e-15), 'Serialized cap degeneracy')
    normal /= length[:, None]; duv = uv[:, 1:]-uv[:, :1]
    det = duv[:, 0, 0]*duv[:, 1, 1]-duv[:, 0, 1]*duv[:, 1, 0]
    require(np.all(np.abs(det) > 1e-14), 'Serialized UV degeneracy')
    tangent = (edges[:, 0]*duv[:, 1, 1, None]-edges[:, 1]*duv[:, 0, 1, None])/det[:, None]
    bitangent = (edges[:, 1]*duv[:, 0, 0, None]-edges[:, 0]*duv[:, 1, 0, None])/det[:, None]
    tangent -= normal*np.einsum('ij,ij->i', tangent, normal)[:, None]
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    hand = np.sign(np.einsum('ij,ij->i', np.cross(normal, tangent), bitangent))
    return {'POSITION': corners.reshape(-1, 3).astype(np.float32),
            'NORMAL': np.repeat(normal, 3, axis=0).astype(np.float32),
            'TEXCOORD_0': uv.reshape(-1, 2).astype(np.float32),
            'TANGENT': np.repeat(np.column_stack((tangent, hand)), 3, axis=0).astype(np.float32),
            'faces': np.arange(corners.size//3, dtype=np.int64).reshape(-1, 3)}


def topo_summary(t):
    return {key: value for key, value in t.items() if key not in
            ('boundaryLoops', 'nonmanifoldVertexPositions', 'nonmanifoldEdgeRecords', 'boundaryIncidentFaceIds')}


def defect_guard(before, after):
    def edges(t):
        return {tuple(sorted(map(tuple, row['positions']))): len(row['incidentFaces']) for row in t['nonmanifoldEdgeRecords']}
    def boundaries(t):
        return {tuple(sorted(map(tuple, row['positions']))) for row in t['boundaryLoops']}
    require(edges(before) == edges(after), 'Original nonmanifold edge incidence changed')
    require(boundaries(before) == boundaries(after), 'Original micro-boundary loops changed')
    require(set(map(tuple, before['nonmanifoldVertexPositions'])) == set(map(tuple, after['nonmanifoldVertexPositions'])), 'Vertex link defects changed')
    for key in ('inconsistentManifoldEdgeWindings', 'zeroAreaFaces', 'components'):
        require(before[key] == after[key], 'Topology changed: '+key)
    return {'originalNonmanifoldEdgesAndIncidencesExact': True, 'originalMicroBoundaryLoopsExact': True,
            'originalBadVertexLinkPositionsExact': True, 'noIntroducedWindingDegeneracyOrDisconnectedComponent': True}


def audit_geometry(original_positions, original_faces, rows, eps):
    positions, faces = [], []; offset = 0
    for row in rows:
        p = row['attributes']['POSITION']; f = row['faces']
        positions.append(p); faces.append(f+offset); offset += len(p)
    before = topology(original_positions, original_faces)
    after = topology(np.concatenate(positions), np.concatenate(faces))
    checks = defect_guard(before, after); cap_audits = []; body = positions[0][rows[0]['faces']].astype(float)
    for i, row in enumerate(rows[1:], 1):
        xyz = row['attributes']['POSITION'][row['faces']].astype(float)
        body_contact = intersect_meshes(xyz, body, eps=eps)
        self_contact = intersect_meshes(xyz, xyz, eps=eps, same=True)
        require(not body_contact['forbiddenContacts'] and not self_contact['forbiddenContacts'], 'Serialized cap intersects body or itself')
        cap_topology = topology(row['attributes']['POSITION'], row['faces'])
        require(cap_topology['boundaryEdges'] == 68 and len(cap_topology['boundaryLoops']) == 1 and
                cap_topology['boundaryLoops'][0]['closedDegreeTwoRing'] and cap_topology['components'] == 1 and
                cap_topology['eulerCharacteristic'] == 1 and cap_topology['nonmanifoldEdges'] == 0 and
                cap_topology['nonmanifoldVertexLinks'] == 0 and cap_topology['zeroAreaFaces'] == 0 and
                cap_topology['inconsistentManifoldEdgeWindings'] == 0, 'Cap is not a coherent disk')
        cross = np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]); lengths = np.linalg.norm(cross, axis=1)
        require(np.all(cross[:, 1] < 0), 'Serialized projected cap fold')
        normals = row['attributes']['NORMAL'][row['faces']].astype(float)
        dots = np.einsum('ij,ikj->ik', cross/lengths[:, None], normals)
        tangents = row['attributes']['TANGENT'].astype(float)
        nt = np.sum(row['attributes']['NORMAL'].astype(float)*tangents[:, :3], axis=1)
        require(dots.min() > .999999 and np.max(np.abs(nt)) < 1e-6, 'Cap shading frame mismatch')
        cap_audits.append({'primitive': i, 'topology': topo_summary(cap_topology),
            'bodyIntersection': body_contact, 'selfIntersection': self_contact,
            'geometricAuthoredNormalDotMin': float(dots.min()), 'normalTangentDotMax': float(np.abs(nt).max()),
            'projectedFootprintArea': float(-cross[:, 1].sum()/2)})
    cross_ports = intersect_meshes(positions[1][rows[1]['faces']], positions[2][rows[2]['faces']], eps=eps)
    require(not cross_ports['forbiddenContacts'], 'Cross-port contact')
    checks.update(noCapBodyIntersection=True, noCapSelfIntersection=True, noCrossPortContact=True, capDisksCoherent=True,
                  capShadingFramesCorrect=True)
    return {'baselineTopology': topo_summary(before), 'diagnosticTopology': topo_summary(after),
            'checks': checks, 'caps': cap_audits, 'crossPortIntersection': cross_ports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve(); require(not output.exists(), 'Fresh output required')
    config = json.loads(args.config.read_text()); pins = config['inputs']
    for key, pin in pins.items():
        require(sha(pin['path']) == pin['sha256'], 'Changed pinned input: '+key)
    require(config['kind'] == 'authorized-bounded-troll-pelvis-diagnostic' and config['acceptance'] is False, 'Explicit unaccepted Troll configuration required')
    design = json.loads(Path(pins['geometryDesign']['path']).read_text())
    require(design['geometryExportEligible'] and all(design['checks'].values()), 'Design guards failed')
    fit = json.loads(Path(pins['properFit']['path']).read_text())
    require(fit['targetId'] == 'troll-male-muscular-purposebuilt-v1' and fit['part'] == 'pelvis' and
            fit['coordinateSpace'] == 'working' and fit['statureApplications'] == 0 and
            sha(fit['targetContract']) == fit['targetContractSha256'] and
            fit['sourceSha256'] == pins['source']['sha256'] and sha(fit['candidate']) == fit['candidateSha256'], 'Exact target working fit required')
    source_doc, source_bin = read_glb(pins['source']['path']); sp, sf, _ = mesh_arrays(source_doc, source_bin)
    fit_doc, fit_bin = read_glb(fit['candidate']); fp, ff, _ = mesh_arrays(fit_doc, fit_bin)
    require(np.array_equal(sf, ff), 'Source-to-fit original face correspondence changed')
    proposed = np.load(pins['faceSelection']['path'])
    kept = proposed['foundation4598IncludingOrphanKeptOriginalFaceIds']; deleted = proposed['foundation4598IncludingOrphanDeletedOriginalFaceIds']
    require(len(sf) == 49452 and len(kept) == 44854 and len(deleted) == 4598 and 35709 in deleted and
            len(np.intersect1d(deleted, [45990, 45991, 48153, 48154])) == 0 and
            np.array_equal(np.sort(np.concatenate((kept, deleted))), np.arange(len(sf))), 'Approved original face scope violated')
    output.mkdir(parents=True); mappings = {}; cap_by_space = {'source': [], 'working': []}; port_proofs = []
    matrix = np.asarray(fit['sourceToAttachmentLocal'], float)
    singular = np.linalg.svd(matrix[:3, :3], compute_uv=False)
    require(np.allclose(singular, .54, atol=1e-12) and np.linalg.det(matrix[:3, :3]) > 0, 'Proper declared 0.54 fit required')
    for side in ('left', 'right'):
        data = np.load(pins['cap'+side.title()]['path']); positions = data['positions'].astype(np.float32)
        faces = data['faces'].astype(np.int64); original_ring = data['originalRingVertexRows']
        require(len(original_ring) == 68 and np.array_equal(positions[:68], sp[original_ring]), 'Exact original 68-row port required')
        src_attrs = shade_with_uv(positions, faces, data['chartTEXCOORD_0'])
        transformed = source_to_fit_raw(positions, matrix).astype(np.float32)
        predicted_ring = transformed[:68].copy(); transformed[:68] = fp[original_ring]
        ring_difference = float(np.max(np.abs(predicted_ring-fp[original_ring])))
        require(ring_difference < 5e-8, 'Fit boundary bridge drift')
        work_attrs = shade_with_uv(transformed, faces, data['chartTEXCOORD_0'])
        cap_by_space['source'].append((side, src_attrs)); cap_by_space['working'].append((side, work_attrs))
        mappings[side+'CapOriginalPortRows'] = original_ring; mappings[side+'CapTopologyPositionsSource'] = positions
        mappings[side+'CapTopologyPositionsWorking'] = transformed; mappings[side+'CapTopologyFaces'] = faces
        mappings[side+'CapEarPartition'] = data['ears']; mappings[side+'CapFaceEarOwnership'] = data['faceEar']
        mappings[side+'CapCornerTopologyVertexIds'] = faces.reshape(-1)
        port_proofs.append({'side': side, 'ringRows': original_ring.tolist(), 'capFaces': len(faces),
            'newTopologyVertices': len(positions)-68, 'serializedCapCornerRows': len(src_attrs['POSITION']),
            'sourceToFitBoundaryRoundingMax': ring_difference, 'ringPreservedFromExistingFitExactly': True,
            'maximumAdditionalDepthBeyondOriginalMinimumWorking': float((positions[:, 1].min()-positions[:68, 1].min())*-.54),
            'footprintProof': 'A coherent disk, exactly the original 68-edge boundary, every serialized projected face orientation preserving, with zero non-shared cap intersections. Every pre-serialization face is assigned to its original constrained projected ear.',
            'uvChartPolicy': 'Same appended planar source-XZ chart in source/working; original body UV rows and maps immutable',
            'material': 'Neutral opaque matte diagnostic; no original map reused or changed; not accepted skin/underwear'})
    mapping = output/'original-face-and-cap-mapping.npz'
    np.savez_compressed(mapping, sourceOriginalFaces=sf, keptOriginalFaceIds=kept, deletedOriginalFaceIds=deleted, **mappings)
    exports = {}
    for space, odoc, obin, op, of in [('source', source_doc, source_bin, sp, sf), ('working', fit_doc, fit_bin, fp, ff)]:
        doc, binary = append_diagnostic(odoc, obin, of[kept], cap_by_space[space]); path = output/(space+'-diagnostic.glb')
        write_glb(path, doc, binary); final_doc, final_bin = read_glb(path); rows = decoded_primitives(final_doc, final_bin)
        proof = preservation(odoc, obin, final_doc, final_bin, of[kept])
        audit = audit_geometry(op, of, rows, config['intersectionToleranceSource']*(.54 if space == 'working' else 1.))
        corner_data = {}; material_ids = []; triangle_ids = []; prim_refs = []
        for i, row in enumerate(rows):
            for key, values in row['attributes'].items():
                corner_data.setdefault(key, []).append(values[row['faces']])
            material_ids.extend([row['primitive'].get('material')]*len(row['faces']))
            triangle_ids.extend(kept.tolist() if i == 0 else [-1]*len(row['faces'])); prim_refs.extend([i]*len(row['faces']))
        corner_path = output/(space+'-literal-corners.npz')
        np.savez_compressed(corner_path, **{key: np.concatenate(rows) for key, rows in corner_data.items()},
            materialIds=np.asarray(material_ids), sourceOriginalFaceIds=np.asarray(triangle_ids), primitiveIds=np.asarray(prim_refs))
        exports[space] = {'candidate': stamp(path), 'decodedCornerArchive': stamp(corner_path), 'preservation': proof, 'geometryAudit': audit}
    helpers = [Path(__file__), Path(__file__).with_name('bounded_pelvis_connector_v2.py'),
               Path(__file__).with_name('conservative_face_selection.py'), Path(__file__).with_name('place_purposebuilt_pelvis.py')]
    snapshots = {}; (output/'helper-snapshots').mkdir()
    for helper in helpers:
        dst = output/'helper-snapshots'/helper.name; shutil.copyfile(helper, dst); snapshots[str(helper.resolve())] = stamp(dst)
    for key, pin in pins.items():
        require(sha(pin['path']) == pin['sha256'], 'Protected input changed after export: '+key)
    receipt = {'schemaVersion': 1, 'kind': 'bounded-troll-pelvis-port-diagnostic', 'config': stamp(args.config),
        'targetContract': fit['targetContract'], 'targetContractSha256': fit['targetContractSha256'], 'targetId': fit['targetId'],
        'rigRevision': fit['rigRevision'], 'coordinateSpace': 'working', 'part': 'pelvis', 'joint': fit['joint'], 'model': fit['model'],
        'source': pins['source'], 'properFit': pins['properFit'], 'statureApplications': 0,
        'sourceToAttachmentLocal': fit['sourceToAttachmentLocal'], 'attachmentWorld': fit['attachmentWorld'],
        'faceMapping': stamp(mapping), 'deletedOriginalFaces': 4598, 'keptOriginalFaces': 44854, 'newCapFaces': 1444,
        'ports': port_proofs, 'exports': exports, 'frozenInputs': {v['path']: v['sha256'] for v in pins.values()},
        'helperSnapshots': snapshots, 'protectedInputsUnchanged': True,
        'unchangedOriginalDefects': '12 boundary edges, 144 nonmanifold edges, 491 bad vertex links; coincident pairs45990/45991 and48153/48154 and near-zero authored normal34936 retained outside repair scope.',
        'unsupportedExistingLineage': 'This is not target-part-geometry or a fully closed exterior repair. Existing target preview/stage cannot consume this lineage. Existing stage still rejects original coincident triangles. Any adapter must verify this exact bounded lineage, keep body roles separate from diagnostic caps, and preserve all original topology guards.',
        'closedExteriorClaim': False, 'materialAccepted': False, 'anatomyAccepted': False, 'selectionMade': False,
        'productionAccepted': False, 'clientAccepted': False, 'geometryDiagnosticGuardsPassed': True}
    path = output/'diagnostic.json'; path.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'receipt': stamp(path), 'workingCandidate': exports['working']['candidate'],
          'sourceCandidate': exports['source']['candidate'], 'topology': exports['working']['geometryAudit']['diagnosticTopology']}), flush=True)


if __name__ == '__main__':
    main()
