"""Read-only source atlas/UV inventory and explicit boundary inspection probes.

No material roles or production face maps are inferred from colours. Optional
pixel polylines are manually authored atlas inspection evidence only.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import target_contract as contract
from place_purposebuilt_pelvis import accessor, raw_corners, read_glb


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def source(target_path, source_path, generation_path):
    target = contract.load(target_path)
    generation = json.loads(Path(generation_path).read_text(encoding='utf-8'))
    contract.require(generation.get('state') == 'success', 'Successful immutable generation receipt required')
    outputs = [row for row in generation['outputs'] if Path(row['localPath']).resolve() == Path(source_path).resolve()]
    contract.require(len(outputs) == 1 and contract.sha(source_path) == outputs[0]['sha256'], 'Collected source pin differs')
    document, binary = read_glb(source_path)
    extra = {}
    positions, normals, uvs, primitives = raw_corners(document, binary, extra=extra)
    return target, generation, document, binary, positions, normals, uvs, primitives, extra


def snapshot(output):
    result = {}
    for path in (Path(__file__).resolve(), Path(__file__).with_name('target_contract.py'),
                 Path(__file__).with_name('place_purposebuilt_pelvis.py')):
        copied = output / 'helper-snapshots' / path.name
        copied.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, copied)
        result[str(path)] = {'path': str(copied), 'sha256': contract.sha(copied)}
    return result


def map_info(document, binary, texture_info, output, name):
    contract.require(texture_info.get('texCoord', 0) == 0 and not texture_info.get('extensions'),
                     'Only untransformed TEXCOORD_0 supported for inspection')
    texture = document['textures'][texture_info['index']]
    image_index = texture['source']
    record = document['images'][image_index]
    contract.require('bufferView' in record and not record.get('uri'), 'Embedded image required')
    view = document['bufferViews'][record['bufferView']]
    start = view.get('byteOffset', 0)
    data = binary[start:start + view['byteLength']]
    image = Image.open(BytesIO(data))
    suffix = { 'image/png': '.png', 'image/jpeg': '.jpg' }[record['mimeType']]
    path = output / (name + suffix)
    path.write_bytes(data)
    sampler = document.get('samplers', [{}])[texture.get('sampler', 0)] if document.get('samplers') else {}
    return {'path': str(path), 'sha256': sha256(data).hexdigest(), 'imageIndex': image_index,
            'textureIndex': texture_info['index'], 'texCoord': 0, 'mimeType': record['mimeType'],
            'width': image.width, 'height': image.height, 'mode': image.mode,
            'sampler': sampler, 'textureInfo': texture_info, 'exactEmbeddedBytes': True}


def uv_pixels(uvs, width, height):
    # glTF UV v=0 addresses the top of the embedded image. NWN UV conversion
    # later flips v; this source inspection deliberately does not do so.
    return np.asarray(uvs, dtype=float) * np.asarray([width, height]) - .5


def wire_image(image, triangles, line=(0, 255, 255, 75)):
    image = image.convert('RGBA')
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for row in triangles:
        points = [tuple(float(x) for x in point) for point in row]
        draw.line(points + points[:1], fill=line, width=1)
    return Image.alpha_composite(image, overlay).convert('RGB')


def inventory(target_path, source_path, generation_path, output):
    output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh diagnostic directory required')
    target, generation, document, binary, positions, normals, uvs, primitives, extra = source(target_path, source_path, generation_path)
    output.mkdir(parents=True)
    original_sha = contract.sha(source_path)
    material_ids = []
    for record in primitives:
        material_ids.extend([record['material']] * record['triangles'])
    materials = []
    for index, material in enumerate(document.get('materials', [])):
        folder = output / ('material-' + str(index))
        folder.mkdir()
        pbr = material.get('pbrMetallicRoughness', {})
        maps = {}
        for name, texture_info in (('base-color', pbr.get('baseColorTexture')),
                                   ('normal', material.get('normalTexture')),
                                   ('orm', pbr.get('metallicRoughnessTexture'))):
            if texture_info:
                maps[name] = map_info(document, binary, texture_info, folder, name)
        if 'base-color' in maps:
            info = maps['base-color']
            face_uv = uvs[np.asarray(material_ids) == index]
            image = Image.open(info['path'])
            wires = wire_image(image, uv_pixels(face_uv, image.width, image.height))
            wire_path = folder / 'base-color-uv-wire.png'
            wires.save(wire_path)
            maps['base-color']['uvWire'] = {'path': str(wire_path), 'sha256': contract.sha(wire_path)}
        materials.append({'index': index, 'name': material.get('name'), 'gltfDefinition': material,
                          'alphaMode': material.get('alphaMode', 'OPAQUE'),
                          'normalScale': material.get('normalTexture', {}).get('scale', 1),
                          'roughnessFactor': pbr.get('roughnessFactor', 1),
                          'metallicFactor': pbr.get('metallicFactor', 1), 'maps': maps})
    encoded = []
    for record in primitives:
        attr = record['sourceAttributeAccessors']
        encoded.append({**record, 'encodedAccessors': {
            semantic: {**document['accessors'][index], 'accessorIndex': index,
                       'bufferViewDefinition': document['bufferViews'][document['accessors'][index]['bufferView']],
                       'valuesSha256': sha256(accessor(document, binary, index, allow_normalized=semantic == 'COLOR_0').tobytes()).hexdigest()}
            for semantic, index in attr.items()},
            'encodedIndexAccessor': document['accessors'][record['indexAccessor']]})
    archive = output / 'source-corners.npz'
    arrays = {'positions': positions, 'normals': normals, 'uvs': uvs,
              'materialIds': np.asarray(material_ids), 'sourceFaceIds': np.arange(len(positions), dtype=np.int64)}
    for semantic, data in extra.items():
        arrays[semantic] = np.asarray(data['rows'])
    np.savez_compressed(archive, **arrays)
    receipt = {'schemaVersion': 1, 'kind': 'target-garment-source-readiness-inventory',
               **contract.binding(target_path, target, 'working'),
               'geometryCoordinateSpace': 'unfitted-glTF-source', 'targetBindingDoesNotEstablishFit': True,
               'source': {'path': str(Path(source_path).resolve()), 'sha256': original_sha},
               'generation': {'path': str(Path(generation_path).resolve()), 'sha256': contract.sha(generation_path),
                              'promptId': generation['promptId'], 'state': generation['state']},
               'triangleCount': len(positions), 'activePrimitives': encoded,
               'meshCount': len(document.get('meshes', [])), 'materials': materials,
               'nodes': document['nodes'], 'scenes': document['scenes'],
               'uvRange': {'minimum': uvs.min(axis=(0, 1)).tolist(), 'maximum': uvs.max(axis=(0, 1)).tolist()},
               'authoredTangentPresent': 'TANGENT' in extra,
               'sourceCorners': {'path': str(archive), 'sha256': contract.sha(archive)},
               'normalLengthRange': [float(np.linalg.norm(normals, axis=2).min()), float(np.linalg.norm(normals, axis=2).max())],
               'helperSnapshots': snapshot(output), 'sourceBytesPreserved': contract.sha(source_path) == original_sha,
               'nativeCompiled': False, 'nativeTangentAcceptancePending': True,
               'garmentFaceMapAuthored': False, 'materialRolesInferred': False,
               'fitAccepted': False, 'boundaryAccepted': False, 'clientAccepted': False, 'complete': False,
               'limitation': 'Original serialized GLB inventory and source UV/image evidence only. NWN-native vertex/TBN/material behavior requires a separately selected fitted-parent partition and independent native compile audit.'}
    contract.require(receipt['sourceBytesPreserved'], 'Source changed during read-only inspection')
    save(output / 'inventory.json', receipt)
    print(json.dumps({'inventory': str(output / 'inventory.json'), 'sha256': contract.sha(output / 'inventory.json'),
                      'triangleCount': len(positions), 'materialCount': len(materials), 'complete': False}))


def segment_triangle_interior(segment, triangle, epsilon=1e-10):
    """Return segment t interval inside a nondegenerate triangle, excluding edges.

    Explicit linear clipping avoids colour-based classification. A segment
    running exactly along a triangle edge has no strict interior interval.
    """
    segment = np.asarray(segment, dtype=float)
    triangle = np.asarray(triangle, dtype=float)
    contract.require(segment.shape == (2, 2) and triangle.shape == (3, 2)
                     and np.isfinite(segment).all() and np.isfinite(triangle).all(), 'Finite 2D inputs required')
    if np.linalg.norm(segment[1] - segment[0]) <= epsilon:
        return None
    basis = np.column_stack((triangle[1] - triangle[0], triangle[2] - triangle[0]))
    determinant = float(np.linalg.det(basis))
    if abs(determinant) <= epsilon:
        return None
    bary2 = np.linalg.solve(basis, (segment - triangle[0]).T).T
    bary = np.column_stack((1 - bary2.sum(axis=1), bary2))
    delta = bary[1] - bary[0]
    low, high = 0., 1.
    for value, change in zip(bary[0], delta):
        if abs(change) <= epsilon:
            if value <= epsilon:
                return None
        elif change > 0:
            low = max(low, (epsilon - value) / change)
        else:
            high = min(high, (epsilon - value) / change)
    if high - low <= epsilon:
        return None
    return [float(low), float(high)]


def inspect(inventory_path, probes_path, output):
    output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh inspection directory required')
    inventory_data = json.loads(Path(inventory_path).read_text(encoding='utf-8'))
    target = contract.load(inventory_data['targetContract'])
    contract.verify_binding(inventory_data, inventory_data['targetContract'], target, 'working')
    for item in (inventory_data['source'], inventory_data['sourceCorners']):
        contract.require(contract.sha(item['path']) == item['sha256'], 'Inventory source changed')
    probes = json.loads(Path(probes_path).read_text(encoding='utf-8'))
    contract.require(probes.get('schemaVersion') == 1 and probes.get('kind') == 'atlas-boundary-inspection-probes'
                     and probes.get('scope') == 'inspection-only' and probes.get('sourceSha256') == inventory_data['source']['sha256'],
                     'Explicit source-bound inspection probes required')
    with np.load(inventory_data['sourceCorners']['path']) as archive:
        uvs, material_ids = archive['uvs'], archive['materialIds']
    output.mkdir(parents=True)
    shutil.copyfile(probes_path, output / 'inspection-probes.json')
    findings = []
    for region in probes['regions']:
        name = region['name']
        info = inventory_data['materials'][region['materialIndex']]['maps']['base-color']
        contract.require(info['sha256'] == region['atlasSha256'] and contract.sha(info['path']) == info['sha256'], 'Probe atlas pin differs')
        image = Image.open(info['path']).convert('RGB')
        triangles = uv_pixels(uvs, image.width, image.height)
        line = np.asarray(region['pixelPolyline'], dtype=float)
        contract.require(line.ndim == 2 and line.shape[1] == 2 and len(line) >= 2 and np.isfinite(line).all(), 'Pixel polyline required')
        crossing = {}
        for segment_index in range(len(line) - 1):
            segment = line[segment_index:segment_index + 2]
            lo, hi = segment.min(axis=0), segment.max(axis=0)
            candidates = np.flatnonzero((material_ids == region['materialIndex']) &
                                        (triangles.min(axis=1) <= hi).all(axis=1) &
                                        (triangles.max(axis=1) >= lo).all(axis=1))
            for face_id in candidates:
                interval = segment_triangle_interior(segment, triangles[face_id])
                if interval:
                    crossing.setdefault(int(face_id), []).append({'polylineSegment': segment_index, 'parameterInterval': interval,
                        'interiorLengthPixels': float(np.linalg.norm(segment[1] - segment[0]) * (interval[1] - interval[0]))})
        crop = tuple(int(value) for value in region['cropPixels'])
        contract.require(len(crop) == 4 and 0 <= crop[0] < crop[2] <= image.width and 0 <= crop[1] < crop[3] <= image.height,
                         'Valid in-atlas crop required')
        image.crop(crop).resize(((crop[2] - crop[0]) * 3, (crop[3] - crop[1]) * 3)).save(output / (name + '-atlas.png'))
        overlay = wire_image(image, triangles[(material_ids == region['materialIndex'])], (255, 255, 255, 45)).convert('RGBA')
        drawing = ImageDraw.Draw(overlay)
        for face_id in crossing:
            row = triangles[face_id]
            drawing.line([tuple(point) for point in row] + [tuple(row[0])], fill=(0, 255, 255, 255), width=2)
        drawing.line([tuple(point) for point in line], fill=(255, 0, 255, 255), width=2)
        overlay.crop(crop).resize(((crop[2] - crop[0]) * 3, (crop[3] - crop[1]) * 3)).convert('RGB').save(output / (name + '-uv-probe.png'))
        candidates = [{'sourceFaceId': face_id, 'uvPixels': triangles[face_id].tolist(), 'intersections': values}
                      for face_id, values in sorted(crossing.items())]
        findings.append({'name': name, 'materialIndex': region['materialIndex'], 'atlasSha256': info['sha256'],
                         'pixelPolyline': line.tolist(), 'cropPixels': list(crop),
                         'questionableSourceFaces': candidates, 'questionableFaceCount': len(candidates),
                         'interpretation': 'The manually placed inspection polyline passes through these source UV triangle interiors; this is not a skin/garment classification or a reviewed production boundary.',
                         'views': {name: {'path': str(output / (region['name'] + '-' + name + '.png')),
                                          'sha256': contract.sha(output / (region['name'] + '-' + name + '.png'))}
                                   for name in ('atlas', 'uv-probe')}})
    receipt = {'schemaVersion': 1, 'kind': 'target-garment-boundary-inspection',
               **contract.binding(inventory_data['targetContract'], target, 'working'),
               'geometryCoordinateSpace': 'unfitted-glTF-source', 'targetBindingDoesNotEstablishFit': True,
               'inventory': {'path': str(Path(inventory_path).resolve()), 'sha256': contract.sha(inventory_path)},
               'source': inventory_data['source'], 'inspectionProbes': {'path': str(output / 'inspection-probes.json'),
                                                                     'sha256': contract.sha(output / 'inspection-probes.json')},
               'regions': findings, 'helperSnapshots': snapshot(output),
               'sourceBytesPreserved': contract.sha(inventory_data['source']['path']) == inventory_data['source']['sha256'],
               'garmentFaceMapAuthored': False, 'materialRolesInferred': False, 'partitionAccepted': False,
               'boundaryAccepted': False, 'clientAccepted': False, 'complete': False,
               'limitation': 'Finite manually drawn pixel probes do not trace every cloth boundary or prove a lossless whole-face partition. Exact fitted-parent IDs, topology/attribute preservation, native material transport and actual client palette review remain mandatory.'}
    contract.require(receipt['sourceBytesPreserved'], 'Source changed during read-only inspection')
    save(output / 'inspection.json', receipt)
    print(json.dumps({'inspection': str(output / 'inspection.json'), 'sha256': contract.sha(output / 'inspection.json'),
                      'regionCounts': {row['name']: row['questionableFaceCount'] for row in findings}, 'complete': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    inventory_parser = sub.add_parser('inventory')
    for name in ('target-contract', 'source-glb', 'generation-receipt', 'output'):
        inventory_parser.add_argument('--' + name, type=Path, required=True)
    inspection_parser = sub.add_parser('inspect')
    for name in ('inventory', 'probes', 'output'):
        inspection_parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'inventory':
        inventory(args.target_contract, args.source_glb, args.generation_receipt, args.output)
    else:
        inspect(args.inventory, args.probes, args.output)
