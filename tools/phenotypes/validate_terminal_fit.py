"""Validate an executed terminal fit and its actual ASCII/GLB geometry.

The parent operation chain is validated by validate_headless_candidate. This
module verifies the terminal operation itself, current exports, retained ankle
coordinates, unchanged maps/unrelated parts, and frozen source/code receipts.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from audit_geometry import arrays
from scale_fitted_body import read_glb


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def triangle_keys(triangles, serialized=False):
    if serialized:
        triangles = np.asarray([[[float(f'{v:.8g}') for v in point] for point in tri] for tri in triangles])
    return Counter(tuple(tuple(float(v) for v in point) for point in tri) for tri in triangles)


def accessor(document, buffer, index):
    record = document['accessors'][index]
    require('sparse' not in record, 'Unsupported sparse terminal accessor')
    view = document['bufferViews'][record['bufferView']]
    require(view.get('buffer', 0) == 0, 'External terminal geometry buffer')
    types = {5120: '<i1', 5121: '<u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[record['type']]
    dtype = np.dtype(types[record['componentType']])
    return np.ndarray((record['count'], width), dtype=dtype, buffer=buffer,
        offset=view.get('byteOffset', 0)+record.get('byteOffset', 0),
        strides=(view.get('byteStride', width*dtype.itemsize), dtype.itemsize))


def glb_geometry(path):
    document, buffer = read_glb(path)
    for node in document.get('nodes', []):
        require('matrix' not in node and node.get('translation', [0, 0, 0]) == [0, 0, 0] and
            node.get('rotation', [0, 0, 0, 1]) == [0, 0, 0, 1] and node.get('scale', [1, 1, 1]) == [1, 1, 1],
            'Terminal GLB requires identity object transforms')
    triangles, uvs = [], []
    for mesh in document['meshes']:
        for primitive in mesh['primitives']:
            require(primitive.get('mode', 4) == 4, 'Terminal GLB contains non-triangle primitives')
            points = accessor(document, buffer, primitive['attributes']['POSITION'])
            # Blender's Z-up local coordinates are serialized in glTF Y-up.
            local = np.column_stack((points[:, 0], -points[:, 2], points[:, 1]))
            indices = accessor(document, buffer, primitive['indices']).reshape(-1, 3)
            triangles.extend(local[indices])
            tex = accessor(document, buffer, primitive['attributes']['TEXCOORD_0']).copy()
            tex[:, 1] = 1.-tex[:, 1]
            uvs.extend(tex[indices])
    return np.asarray(triangles), np.asarray(uvs)


def ascii_geometry(path):
    triangles, uvs = [], []
    for match in re.finditer(r'(?ms)^node trimesh \S+\n(.*?)^endnode', path.read_text()):
        points = np.asarray(arrays(match[1], 'verts'))
        faces = np.asarray(arrays(match[1], 'faces')).astype(int)
        triangles.extend(points[faces[:, :3]])
        tex = np.asarray(arrays(match[1], 'tverts'))[:, :2]
        uvs.extend(tex[faces[:, 4:7]])
    return np.asarray(triangles), np.asarray(uvs)


def validate_corner_uvs(actual_triangles, actual_uvs, expected_triangles, expected_uvs):
    expected = {}
    for tri, uv in zip(expected_triangles, expected_uvs):
        key = tuple(tuple(float(v) for v in point) for point in tri)
        require(key not in expected, 'UV comparison requires no coincident geometry triangles')
        expected[key] = uv
    maximum = 0.
    for tri, uv in zip(actual_triangles, actual_uvs):
        key = tuple(tuple(float(v) for v in point) for point in tri)
        require(key in expected, 'Missing expected terminal UV triangle')
        maximum = max(maximum, float(np.max(abs(uv-expected[key]))))
    require(maximum <= 1e-6, 'Actual terminal corner UVs differ from retention record')
    return maximum


def validate_operation(converted, report=None):
    converted = Path(converted).resolve()
    report = report or json.loads((converted/'conversion.json').read_text())
    require(report['currentGeometryOperation'] == 'terminalPartFit', 'Expected terminalPartFit as current operation')
    operation = report['operations']['terminalPartFit']
    source = Path(operation['source'])
    original = json.loads((source/'conversion.json').read_text())
    for path, expected in operation['frozenInputHashes'].items():
        snapshot = report['codeSnapshots'].get(path)
        actual = Path(snapshot['path'] if snapshot else path)
        require(sha(actual) == expected, 'Frozen terminal input changed: '+path)
    require(report['jointWorldNwn'] == original['jointWorldNwn'] and report['height'] == original['height'], 'Terminal fit changed rig/stature')
    require(report['materialPolicy'] == original['materialPolicy'], 'Terminal fit changed material policy')
    require(sha(converted/'ascii'/(report['modelPrefix']+'.mdl')) == sha(source/'ascii'/(report['modelPrefix']+'.mdl')), 'Terminal fit changed root/controllers')
    changes = {p['kitPart']: p for p in operation['parts']}
    config = operation['configuration']
    require(set(changes) == set(config['parts']) and not set(changes)&set(config['protectedParts']), 'Unexpected terminal part selection')
    results = []
    for entry in report['parts']:
        kit, model = entry['kitReport']['part'], entry['model']
        glb, ascii_path = converted/'parts'/(kit+'.glb'), converted/'ascii'/(model+'.mdl')
        if kit not in changes:
            require(sha(glb) == sha(source/'parts'/glb.name) and sha(ascii_path) == sha(source/'ascii'/ascii_path.name), 'Unrelated terminal export changed: '+kit)
        else:
            change = changes[kit]
            require(sha(glb) == change['glbSha256'] and sha(ascii_path) == change['asciiSha256'], 'Current terminal export differs from receipt: '+kit)
            record_path = Path(change['retentionRecord'])
            require(sha(record_path) == change['retentionSha256'], 'Terminal retention record changed')
            with np.load(record_path, allow_pickle=False) as record:
                before, after, faces, jacobians = [record[key] for key in ('before', 'after', 'faces', 'jacobians')]
                corner_uvs = record['uvs'].reshape(len(faces), 3, 2)
                attachment = record['attachmentBefore'] if 'attachmentBefore' in record else np.empty((0, 3))
                require(np.array_equal(before[:, 2], after[:, 2]), 'Terminal field moved the ground/vertical profile')
                det = np.linalg.det(jacobians)
                require(det.min() > .1 and abs(float(det.min())-change['minimumFieldJacobianDeterminant']) < 1e-10, 'Terminal field determinant gate failed')
                old, new = before[faces], after[faces]
                old_n = np.cross(old[:, 1]-old[:, 0], old[:, 2]-old[:, 0])
                new_n = np.cross(new[:, 1]-new[:, 0], new[:, 2]-new[:, 0])
                meaningful = np.linalg.norm(old_n, axis=1) > report['height']**2*1e-10
                predicted = np.linalg.solve(jacobians[len(before):].transpose(0, 2, 1), old_n[:, :, None])[:, :, 0]*det[len(before):, None]
                require(np.all(np.einsum('ij,ij->i', predicted[meaningful], new_n[meaningful]) > 0), 'Terminal winding reversal')
                require(np.min(np.linalg.norm(new_n[meaningful], axis=1)/np.linalg.norm(old_n[meaningful], axis=1)) > .1, 'Terminal triangle-area collapse')
                require(np.linalg.norm(after-before, axis=1).max() <= report['height']*config['parts'][kit]['maximumDisplacementFraction'], 'Terminal displacement exceeds configuration')
                actual_coordinates = {tuple(p) for p in after}
                require(all(tuple(p) in actual_coordinates for p in attachment), 'Protected terminal attachment coordinates missing/moved')
                require(len(attachment) == change.get('attachmentCoordinatesRetainedExactly', 0), 'Attachment receipt count mismatch')
                # Assignment to Blender mesh coordinates and GLB serialization
                # uses float32; verify complete actual triangle multisets.
                expected = after.astype(np.float32)[faces]
                glb_triangles, glb_uvs = glb_geometry(glb)
                ascii_triangles, ascii_uvs = ascii_geometry(ascii_path)
                require(triangle_keys(glb_triangles) == triangle_keys(expected), 'Actual terminal GLB triangles differ from field proof')
                require(triangle_keys(ascii_triangles) == triangle_keys(expected, serialized=True), 'Actual terminal ASCII triangles differ from field proof')
                glb_uv_error = validate_corner_uvs(glb_triangles, glb_uvs, expected, corner_uvs)
                serialized_expected = np.asarray([[[float(f'{v:.8g}') for v in point] for point in tri] for tri in expected])
                ascii_uv_error = validate_corner_uvs(ascii_triangles, ascii_uvs, serialized_expected, corner_uvs)
            conditioning = change['sourceConditioning']
            require(conditioning['originalUniqueVerticesRetainedExactly'] == conditioning['originalUniqueVertices'], 'Source conditioning removed donor coordinates')
            require(conditioning['maximumBidirectionalSampledSurfaceError'] <= report['height']*1e-7, 'Source conditioning exceeded surface budget')
            require(conditioning['conditionedFaces'] <= conditioning['sourceFaces']*(1+config['parts'][kit]['fieldTessellation']['maximumFaceGrowthFraction']), 'Source conditioning exceeded growth budget')
            topology = change['topology']
            require(not topology['boundaryEdges'] and not topology['nonmanifoldEdges'] and not topology['coincidentFaceGroups'] and
                len(topology['shells']) == 1 and topology['shells'][0]['signedVolume'] > 0, 'Terminal shell gate failed')
            results.append({'kitPart': kit, 'actualGlbAndAsciiTrianglesMatch': True, 'allAttachmentCoordinatesRetainedExactly': True,
                'groundZUnchanged': True, 'triangles': change['triangles'],
                'maximumGlbCornerUvError': glb_uv_error, 'maximumAsciiCornerUvError': ascii_uv_error})
        if model in report.get('partTextures', {}):
            for key in ('color', 'normal', 'hairMask'):
                if key in report['partTextures'][model]:
                    require(sha(Path(report['partTextures'][model][key])) == sha(Path(original['partTextures'][model][key])), 'Terminal geometry changed map: '+model+'/'+key)
    return {'complete': True, 'conversionSha256': sha(converted/'conversion.json'), 'parts': results,
        'note': 'Terminal operation/export integrity only; parent chain and matching map/native/client acceptance remain separate.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('converted', type=Path)
    args = parser.parse_args()
    result = validate_operation(args.converted)
    snapshot = args.converted/'code-snapshot/terminal-validator.py'
    snapshot.write_bytes(Path(__file__).read_bytes())
    result['validatorCodeSnapshot'] = str(snapshot.resolve())
    result['validatorCodeSha256'] = sha(snapshot)
    (args.converted/'terminal-fit-validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
