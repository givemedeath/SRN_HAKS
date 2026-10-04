"""Recorded local waist-cap experiment; never a general exterior-shell repair."""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import io

import numpy as np


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_glb(path, allow_multiple=False):
    data = path.read_bytes()
    magic, version, length = struct.unpack_from('<4sII', data)
    if (magic, version, length) != (b'glTF', 2, len(data)):
        raise RuntimeError('Incomplete GLB')
    size, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4e4f534a:
        raise RuntimeError('JSON chunk required')
    document = json.loads(data[20:20 + size])
    offset = 20 + size
    size, kind = struct.unpack_from('<II', data, offset)
    if kind != 0x004e4942:
        raise RuntimeError('Embedded BIN required')
    binary = bytes(data[offset + 8:offset + 8 + size])
    if len(document['nodes']) != 1 or len(document['meshes']) != 1:
        raise RuntimeError('One isolated mesh required')
    if any(k in document['nodes'][0] for k in ['matrix', 'translation', 'rotation', 'scale']):
        raise RuntimeError('Baked identity-node placement required')
    primitives = document['meshes'][0]['primitives']
    if (len(primitives) != 1 and not allow_multiple) or any(p.get('mode', 4) != 4 for p in primitives):
        raise RuntimeError('One triangle primitive required')
    if any(p['attributes'].get(key) != primitives[0]['attributes'].get(key)
           for p in primitives for key in ['POSITION', 'NORMAL']):
        raise RuntimeError('Shared position/normal accessors required')
    primitive = primitives[0]
    def accessor(index):
        item = document['accessors'][index]
        view = document['bufferViews'][item['bufferView']]
        width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[item['type']]
        dtype = {5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}[item['componentType']]
        packed = np.dtype(dtype).itemsize * width
        if 'sparse' in item or item.get('normalized') or view.get('byteStride', packed) != packed:
            raise RuntimeError('Uncompressed packed source required')
        return np.frombuffer(binary, dtype=dtype, count=item['count'] * width,
                             offset=view.get('byteOffset', 0) + item.get('byteOffset', 0)).reshape(-1, width).copy()
    attrs = {key: accessor(index) for key, index in primitive['attributes'].items()}
    primitive_faces = [accessor(p['indices']).reshape(-1, 3).astype(np.int64) for p in primitives]
    faces = np.concatenate(primitive_faces)
    # Common-atlas packing can keep a different UV accessor per primitive.
    # Compose only referenced rows for diagnosis; the caller's document keeps
    # all original accessor references. Reject overlapping incompatible charts.
    assigned = np.zeros(len(attrs['POSITION']), dtype=bool)
    for p, pfaces in zip(primitives, primitive_faces):
        for key in p['attributes']:
            if key not in ['POSITION', 'NORMAL', 'TEXCOORD_0'] and p['attributes'][key] != primitive['attributes'][key]:
                raise RuntimeError('Unknown per-primitive attribute policy')
        uv = accessor(p['attributes']['TEXCOORD_0'])
        if len(uv) != len(attrs['POSITION']):
            raise RuntimeError('Per-primitive UV accessor has different vertex indexing')
        used = np.unique(pfaces)
        overlap = used[assigned[used]]
        if not np.array_equal(attrs['TEXCOORD_0'][overlap], uv[overlap]):
            raise RuntimeError('Conflicting UV charts share a referenced vertex index')
        attrs['TEXCOORD_0'][used] = uv[used]
        assigned[used] = True
    return document, binary, attrs, faces


def clip(attrs, faces, cut):
    rows = {key: list(values) for key, values in attrs.items()}
    original = attrs['POSITION']
    unique, inverse = np.unique(original, axis=0, return_inverse=True)
    geometry_edges = {}
    attribute_edges = {}
    output, retained, clipped, deleted = [], [], [], []
    def intersection(a, b):
        attribute_key = tuple(sorted((a, b)))
        if attribute_key in attribute_edges:
            return attribute_edges[attribute_key]
        geometry_key = tuple(sorted((int(inverse[a]), int(inverse[b]))))
        t = (cut - float(original[a, 1])) / (float(original[b, 1]) - float(original[a, 1]))
        if geometry_key not in geometry_edges:
            p, q = unique[list(geometry_key)].astype(float)
            tg = (cut - p[1]) / (q[1] - p[1])
            coord = (p + tg * (q - p)).astype(np.float32)
            coord[1] = np.float32(cut)
            geometry_edges[geometry_key] = coord
        index = len(rows['POSITION'])
        for key, values in attrs.items():
            value = (values[a].astype(float) * (1 - t) + values[b].astype(float) * t).astype(values.dtype)
            if key == 'POSITION':
                value = geometry_edges[geometry_key]
            elif key in ['NORMAL', 'TANGENT']:
                value[:3] /= np.linalg.norm(value[:3])
            rows[key].append(value)
        attribute_edges[attribute_key] = index
        return index
    for face_index, face in enumerate(faces):
        inside = original[face, 1] >= cut
        if inside.all():
            output.append(face.tolist())
            retained.append(face_index)
        elif not inside.any():
            deleted.append(face_index)
        else:
            polygon = []
            for a, b in zip(face, np.roll(face, -1)):
                ain, bin = original[a, 1] >= cut, original[b, 1] >= cut
                if ain:
                    polygon.append(int(a))
                if ain != bin:
                    polygon.append(intersection(int(a), int(b)))
            output.extend([[polygon[0], polygon[i], polygon[i + 1]] for i in range(1, len(polygon) - 1)])
            clipped.append(face_index)
    return {key: np.asarray(values, dtype=attrs[key].dtype) for key, values in rows.items()}, np.asarray(output), retained, clipped, deleted


def cut_loops(attrs, faces, cut):
    p, inverse = np.unique(attrs['POSITION'], axis=0, return_inverse=True)
    mapped = inverse[faces]
    counts = Counter()
    directed = {}
    original_ids = {}
    for triangle, raw in zip(mapped, faces):
        for a, b, ia, ib in zip(triangle, np.roll(triangle, -1), raw, np.roll(raw, -1)):
            edge = tuple(sorted((int(a), int(b))))
            counts[edge] += 1
            directed[edge] = (int(a), int(b))
            original_ids[edge] = (int(ia), int(ib))
    boundary = [edge for edge, n in counts.items() if n == 1 and p[edge[0], 1] == np.float32(cut) and p[edge[1], 1] == np.float32(cut)]
    adjacency = defaultdict(list)
    for a, b in boundary:
        adjacency[a].append(b)
        adjacency[b].append(a)
    if any(len(v) != 2 for v in adjacency.values()):
        raise RuntimeError('Cut contours branch; local cap is unsafe')
    remaining, loops = set(boundary), []
    while remaining:
        edge = next(iter(remaining))
        first, second = directed[edge]
        ordered, ids = [first], []
        a, b = first, second
        while True:
            key = tuple(sorted((a, b)))
            if key not in remaining:
                raise RuntimeError('Cut loop repeats an edge')
            if directed[key] != (a, b):
                raise RuntimeError('Cut contour winding inconsistent')
            remaining.remove(key)
            ids.append(original_ids[key][0])
            if b == first:
                break
            ordered.append(b)
            options = [c for c in adjacency[b] if c != a]
            a, b = b, options[0]
        coords = p[ordered]
        signed = float(np.sum(coords[:, 0] * np.roll(coords[:, 2], -1) - np.roll(coords[:, 0], -1) * coords[:, 2]) / 2)
        loops.append({'ids': ids, 'coords': coords, 'signedAreaXZ': signed})
    return sorted(loops, key=lambda row: abs(row['signedAreaXZ']), reverse=True)


def describe(loops):
    return [{'vertices': len(row['ids']), 'signedAreaXZ': row['signedAreaXZ'],
             'minimum': row['coords'].min(0).tolist(), 'maximum': row['coords'].max(0).tolist(),
             'mean': row['coords'].mean(0).tolist()} for row in loops]


def inspect(args):
    source = args.source.resolve()
    before = sha(source)
    _, _, attrs, faces = read_glb(source)
    rows = []
    for cut in args.cuts:
        clipped_attrs, clipped_faces, retained, clipped, deleted = clip(attrs, faces, cut)
        try:
            loops = cut_loops(clipped_attrs, clipped_faces, cut)
            row = {'cutLocalGLB_Y': cut, 'contoursValid': True, 'loops': describe(loops)}
        except RuntimeError as error:
            row = {'cutLocalGLB_Y': cut, 'contoursValid': False, 'error': str(error)}
        row.update({'retainedSourceTriangles': len(retained), 'clippedSourceTriangles': len(clipped), 'deletedSourceTriangles': len(deleted)})
        rows.append(row)
    if before != sha(source):
        raise RuntimeError('Immutable source changed')
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, args.output / Path(__file__).name)
    receipt = {'source': str(source), 'sourceSha256': before, 'sourceUnchanged': True,
               'readOnly': True, 'meshWritten': False, 'coordinates': 'v5 placed-local GLB: Y is chest-local vertical; world Z = Y + stock chest pivot Z.',
               'scriptSha256': sha(Path(__file__)), 'planes': rows}
    (args.output / 'contour-inspection.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


def append_accessor(document, binary, values, semantic=None):
    binary.extend(b'\0' * ((-len(binary)) % 4))
    values = np.asarray(values)
    offset = len(binary)
    payload = values.tobytes()
    binary.extend(payload)
    view = len(document['bufferViews'])
    document['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(payload)})
    width = values.shape[1]
    item = {'bufferView': view, 'componentType': 5126 if values.dtype.kind == 'f' else 5125,
            'count': len(values), 'type': {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[width]}
    if semantic == 'POSITION':
        item.update({'min': values.min(0).tolist(), 'max': values.max(0).tolist()})
    index = len(document['accessors'])
    document['accessors'].append(item)
    return index


def write_glb(path, document, binary):
    binary.extend(b'\0' * ((-len(binary)) % 4))
    document['buffers'][0]['byteLength'] = len(binary)
    encoded = json.dumps(document, separators=(',', ':')).encode()
    encoded += b' ' * ((-len(encoded)) % 4)
    length = 12 + 8 + len(encoded) + 8 + len(binary)
    path.write_bytes(struct.pack('<4sII', b'glTF', 2, length) + struct.pack('<II', len(encoded), 0x4e4f534a) + encoded +
                     struct.pack('<II', len(binary), 0x004e4942) + binary)


def texture_image(document, binary, material, channel):
    from PIL import Image
    texture = (material['pbrMetallicRoughness']['baseColorTexture'] if channel == 'color' else material['normalTexture'] if channel == 'normal'
               else material['pbrMetallicRoughness']['metallicRoughnessTexture'] if channel == 'metallic-roughness' else material['occlusionTexture'])
    source = document['textures'][texture['index']]['source']
    view = document['bufferViews'][document['images'][source]['bufferView']]
    payload = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
    return np.asarray(Image.open(io.BytesIO(payload)).convert('RGB'), dtype=float) / 255


def sample(image, uv):
    # glTF UV origin is the upper left of the encoded raster.
    h, w = image.shape[:2]
    x = np.clip(uv[:, 0], 0, 1) * (w - 1)
    y = np.clip(uv[:, 1], 0, 1) * (h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    tx, ty = (x - x0)[:, None], (y - y0)[:, None]
    return image[y0, x0] * (1 - tx) * (1 - ty) + image[y0, x1] * tx * (1 - ty) + image[y1, x0] * (1 - tx) * ty + image[y1, x1] * tx * ty


def topology(attrs, faces):
    points, inverse = np.unique(attrs['POSITION'][np.unique(faces)], axis=0, return_inverse=True)
    used = np.unique(faces)
    mapping = {int(index): int(vertex) for index, vertex in zip(used, inverse)}
    triangles = np.asarray([[mapping[int(index)] for index in face] for face in faces])
    edges = Counter()
    winding = Counter()
    for triangle in triangles:
        for a, b in zip(triangle, np.roll(triangle, -1)):
            edge = tuple(sorted((int(a), int(b))))
            edges[edge] += 1
            winding[edge] += 1 if a < b else -1
    p, q, r = (points[triangles[:, i]].astype(float) for i in range(3))
    cross = np.cross(q - p, r - p)
    boundary = [edge for edge, count in edges.items() if count == 1]
    return {'usedUniqueCoordinates': len(points), 'triangles': len(faces),
            'boundaryEdges': len(boundary), 'nonmanifoldEdges': sum(count > 2 for count in edges.values()),
            'inconsistentManifoldWindingEdges': sum(edges[e] == 2 and value != 0 for e, value in winding.items()),
            'degenerateTriangles': int((np.linalg.norm(cross, axis=1) < 1e-13).sum()),
            'signedVolume': float(np.einsum('ij,ij->i', p, cross).sum() / 6),
            'boundaryPositions': [[points[a].tolist(), points[b].tolist()] for a, b in boundary]}


def cap_ring(attrs, faces, loop, depth, rings, rows, normal_transition_rings=3):
    ids = loop['ids']
    coords = np.asarray(loop['coords'], dtype=float)
    centre = (coords.min(0) + coords.max(0)) / 2
    radial = coords - centre
    radial[:, 1] = 0
    tangent = np.roll(coords, -1, axis=0) - np.roll(coords, 1, axis=0)
    distances = np.linalg.norm(np.roll(coords, -1, axis=0) - coords, axis=1)
    u = np.concatenate([[0], np.cumsum(distances)]) / distances.sum()
    originals = {key: np.asarray(value) for key, value in rows.items()}
    cap_faces, cap_rows, levels = [], [], []
    boundary_normals = attrs['NORMAL'][ids].astype(float)
    source_uv = attrs['TEXCOORD_0'][ids].astype(float)
    for level in range(rings):
        theta = np.pi / 2 * level / rings
        c, s = np.cos(theta), np.sin(theta)
        points = centre + radial * c
        points[:, 1] = centre[1] - depth * s
        derivative_theta = -radial * s
        derivative_theta[:, 1] = -depth * c
        normals = np.cross(derivative_theta, tangent * c)
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        if level == 0:
            normals = boundary_normals.copy()
        else:
            blend = min(1., level / normal_transition_rings)
            normals = normals * blend + boundary_normals * (1 - blend)
            normals /= np.linalg.norm(normals, axis=1)[:, None]
        ring_ids = []
        for index in range(len(ids) + 1):
            i = index % len(ids)
            new = len(rows['POSITION'])
            ring_ids.append(new)
            for key in rows:
                if key == 'POSITION':
                    value = points[i].astype(np.float32)
                elif key == 'NORMAL':
                    value = normals[i].astype(np.float32)
                elif key == 'TEXCOORD_0':
                    value = np.asarray([u[index], 1 - level / rings], dtype=np.float32)
                else:
                    raise RuntimeError('Unexpected source attribute; explicit cap policy required')
                rows[key].append(value)
        levels.append(ring_ids)
    for upper, lower in zip(levels, levels[1:]):
        for i in range(len(ids)):
            cap_faces.extend([[upper[i], lower[i], upper[i + 1]], [upper[i + 1], lower[i], lower[i + 1]]])
    # Separate poles per triangle keep periodic UV interpolation local at the
    # chart seam while exact-position diagnostics still see one closed pole.
    pole = centre.copy()
    pole[1] -= depth
    orientation = -1 if loop['signedAreaXZ'] < 0 else 1
    last = levels[-1]
    for i in range(len(ids)):
        pole_id = len(rows['POSITION'])
        rows['POSITION'].append(pole.astype(np.float32))
        rows['NORMAL'].append(np.asarray([0, orientation, 0], dtype=np.float32))
        rows['TEXCOORD_0'].append(np.asarray([(u[i] + u[i + 1]) / 2, 0], dtype=np.float32))
        cap_faces.append([last[i], pole_id, last[i + 1]])
    # Record tangent frames at the boundary for matching source normal maps.
    owner = {}
    for face in faces:
        for index in face:
            owner.setdefault(int(index), face)
    source_tangents, source_bitangents = [], []
    cap_tangents, cap_bitangents = [], []
    for i, index in enumerate(ids):
        face = owner[index]
        p = attrs['POSITION'][face].astype(float)
        uv = attrs['TEXCOORD_0'][face].astype(float)
        du1, du2 = uv[1] - uv[0], uv[2] - uv[0]
        denominator = du1[0] * du2[1] - du1[1] * du2[0]
        if abs(denominator) < 1e-12:
            raise RuntimeError('Source waist UV tangent is degenerate')
        t = ((p[1] - p[0]) * du2[1] - (p[2] - p[0]) * du1[1]) / denominator
        b = ((p[2] - p[0]) * du1[0] - (p[1] - p[0]) * du2[0]) / denominator
        n = boundary_normals[i]
        t -= n * np.dot(t, n)
        t /= np.linalg.norm(t)
        bit = np.cross(n, t)
        bit *= 1 if np.dot(bit, b) >= 0 else -1
        source_tangents.append(t)
        source_bitangents.append(bit)
        ct = tangent[i] - n * np.dot(tangent[i], n)
        ct /= np.linalg.norm(ct)
        cb = np.cross(n, ct)
        cb *= 1 if cb[1] >= 0 else -1
        cap_tangents.append(ct)
        cap_bitangents.append(cb)
    return np.asarray(cap_faces), {'ids': ids, 'u': u, 'sourceUv': source_uv, 'centre': centre.tolist(),
        'boundaryNormals': boundary_normals, 'sourceTangents': np.asarray(source_tangents),
        'sourceBitangents': np.asarray(source_bitangents), 'capTangents': np.asarray(cap_tangents),
        'capBitangents': np.asarray(cap_bitangents), 'depth': depth, 'rings': rings}


def cap_texture(out, label, details, color, normal, resolution, convention='raw-uv-tangent', packed=None, occlusion=None):
    from PIL import Image
    u = details['u']
    target = np.linspace(0, 1, resolution)
    boundary_color = sample(color, details['sourceUv'])
    sampled_normal = sample(normal, details['sourceUv']) * 2 - 1
    sampled_normal /= np.linalg.norm(sampled_normal, axis=1)[:, None]
    sign = -1 if convention == 'blender-uv-flipped-tangent' else 1
    world_normal = (details['sourceTangents'] * sampled_normal[:, :1] + sign * details['sourceBitangents'] * sampled_normal[:, 1:2] +
                    details['boundaryNormals'] * sampled_normal[:, 2:3])
    cap_normal = np.stack([np.einsum('ij,ij->i', world_normal, details[key])
                          for key in ['capTangents', 'capBitangents', 'boundaryNormals']], axis=1)
    cap_normal[:, 1] *= sign
    def periodic(values):
        values = np.vstack([values, values[0]])
        return np.stack([np.interp(target, u, values[:, i]) for i in range(values.shape[1])], axis=1)
    edge_color, edge_normal = periodic(boundary_color), periodic(cap_normal)
    # glTF V=1 is the bottom raster row, matching the cap seam coordinates.
    v = np.linspace(0, 1, resolution)[:, None, None]
    rgb = edge_color[None] * v ** 2 + edge_color.mean(0)[None, None] * (1 - v ** 2)
    normal_weight = np.clip((v - .75) / .25, 0, 1)
    n = edge_normal[None] * normal_weight + np.asarray([0, 0, 1])[None, None] * (1 - normal_weight)
    n /= np.linalg.norm(n, axis=2)[:, :, None]
    paths = {}
    outputs = [('base-color', rgb), ('normal', (n + 1) / 2)]
    for kind, source in [('metallic-roughness', packed), ('occlusion', occlusion)]:
        if source is not None:
            edge = periodic(sample(source, details['sourceUv']))
            continued = edge[None] * v ** 2 + edge.mean(0)[None, None] * (1 - v ** 2)
            outputs.append((kind, continued))
    for kind, data in outputs:
        path = out / (label + '-' + kind + '.png')
        Image.fromarray(np.clip(np.rint(data * 255), 0, 255).astype(np.uint8), 'RGB').save(path)
        paths[kind] = path
    return paths, {'sourceRingSampleRGBMean': boundary_color.mean(0).tolist(), 'resolution': resolution,
        'colorPolicy': 'Actual boundary UV bilinear skin samples, periodic piecewise color interpolation, gradual pole-average continuation.',
        'normalPolicy': 'Source waist tangent-space normal transferred through source and cap boundary tangent frames; neutralized away from edge.',
        'normalMapConvention': convention,
        'packedPolicy': 'Actual waist UV AO/roughness/metallic samples, periodic continuation to averaged pole; source material factors retained.' if packed is not None else 'Original atlas reference inherited; incorrect chart addressing remains in this older diagnostic.',
        'nativeCommonAtlasPending': True}


def embed_image(document, binary, path):
    payload = path.read_bytes()
    binary.extend(b'\0' * ((-len(binary)) % 4))
    view = len(document['bufferViews'])
    document['bufferViews'].append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(payload)})
    binary.extend(payload)
    index = len(document['images'])
    document['images'].append({'bufferView': view, 'mimeType': 'image/png', 'name': path.stem})
    texture = len(document['textures'])
    document['textures'].append({'source': index, 'sampler': document['textures'][0].get('sampler', 0)})
    return texture


def build(args):
    config = json.loads(args.configuration.read_text())
    if config.get('schemaVersion') != 1:
        raise RuntimeError('Explicit version-one waist configuration required')
    for key in ['cutChestLocalZ', 'outerDomeDepth', 'innerDomeDepth']:
        if not np.isfinite(float(config[key])):
            raise RuntimeError('Finite waist dimensions required')
    if not 0 < float(config['innerDomeDepth']) < float(config['outerDomeDepth']) / 2:
        raise RuntimeError('Separated positive shallow inner and outer depths required')
    for key in ['outerRings', 'innerRings']:
        if not 3 <= int(config[key]) <= 64 or int(config[key]) != config[key]:
            raise RuntimeError('Explicit integer ring count between 3 and 64 required')
    for key in ['outerNormalTransitionRings', 'innerNormalTransitionRings']:
        value = config.get(key, 3)
        if not 1 <= int(value) <= 64 or int(value) != value:
            raise RuntimeError('Explicit positive integer normal-transition ring count required')
    resolution = int(config['textureResolution'])
    if resolution not in [512, 1024, 2048, 4096]:
        raise RuntimeError('Supported power-of-two cap atlas resolution required')
    if config.get('normalMapConvention', 'raw-uv-tangent') not in ['raw-uv-tangent', 'blender-uv-flipped-tangent']:
        raise RuntimeError('Unknown normal map convention')
    source = args.source.resolve()
    before = sha(source)
    if before != config['sourceSha256']:
        raise RuntimeError('Selected immutable v5 source mismatch')
    if args.output.exists():
        raise RuntimeError('Fresh output required')
    doc, original_binary, attrs, faces = read_glb(source)
    if set(attrs) != {'POSITION', 'NORMAL', 'TEXCOORD_0'}:
        raise RuntimeError('Explicit position/normal/UV-only source policy required')
    normal_lengths = np.linalg.norm(attrs['NORMAL'], axis=1)
    if np.max(np.abs(normal_lengths - 1)) > .001:
        raise RuntimeError('Source must contain actual unit shading normals')
    cut = float(config['cutChestLocalZ'])
    low, high = attrs['POSITION'][:, 1].min(), attrs['POSITION'][:, 1].max()
    if not low < cut < low + .15 * (high - low):
        raise RuntimeError('Cut exceeds localized lower 15% source band')
    if float(config['outerDomeDepth']) > .15 * (high - low):
        raise RuntimeError('Outer dome exceeds localized lower 15% source span')
    new_attrs, new_faces, retained, clipped, deleted = clip(attrs, faces, cut)
    loops = cut_loops(new_attrs, new_faces, cut)
    if len(loops) != 2 or loops[0]['signedAreaXZ'] >= 0 or loops[1]['signedAreaXZ'] <= 0:
        raise RuntimeError('Expected exactly one outer and one inner contour, with opposite winding')
    star_shape = []
    for loop in loops:
        ring = loop['coords'].astype(float)
        centre = (ring.min(0) + ring.max(0)) / 2
        radial = ring - centre
        edge = np.roll(ring, -1, axis=0) - ring
        signed = np.sign(loop['signedAreaXZ']) * (radial[:, 0] * edge[:, 2] - radial[:, 2] * edge[:, 0])
        minimum = float(signed.min())
        if minimum <= 0:
            raise RuntimeError('Waist contour is not star-shaped about dome centre')
        star_shape.append({'minimumConsistentRadialEdgeCross': minimum, 'centre': centre.tolist(), 'strictStarShape': True})
    rows = {key: list(value) for key, value in new_attrs.items()}
    cap_faces, details = [], []
    for loop, depth, rings, normal_transition in zip(loops, [config['outerDomeDepth'], config['innerDomeDepth']],
                [config['outerRings'], config['innerRings']], [config.get('outerNormalTransitionRings', 3), config.get('innerNormalTransitionRings', 3)]):
        triangles, detail = cap_ring(new_attrs, new_faces, loop, float(depth), int(rings), rows, int(normal_transition))
        cap_faces.append(triangles)
        details.append(detail)
    final_attrs = {key: np.asarray(value, dtype=attrs[key].dtype) for key, value in rows.items()}
    all_faces = np.vstack([new_faces, *cap_faces])
    before_topology = topology(attrs, faces)
    after_topology = topology(final_attrs, all_faces)
    if (before_topology['boundaryEdges'] != after_topology['boundaryEdges'] or
        before_topology['nonmanifoldEdges'] != after_topology['nonmanifoldEdges'] or
        after_topology['inconsistentManifoldWindingEdges'] or after_topology['degenerateTriangles']):
        raise RuntimeError('Local cap introduced a new source topology defect')
    if before_topology['boundaryPositions'] != after_topology['boundaryPositions']:
        raise RuntimeError('Unrelated source boundary edge positions changed')
    protected = np.asarray(retained)
    if not np.array_equal(new_faces[:len(retained)], faces[protected]):
        # Clipped faces are interspersed; verify by explicit exact index tuple membership.
        new_tuples = {tuple(row) for row in new_faces}
        if any(tuple(row) not in new_tuples for row in faces[protected]):
            raise RuntimeError('Protected source triangles changed')
    for key in attrs:
        if not np.array_equal(final_attrs[key][:len(attrs[key])], attrs[key]):
            raise RuntimeError('Original source vertex attributes changed')
    args.output.mkdir(parents=True)
    shutil.copy2(source, args.output / 'frozen-v5-source.glb')
    shutil.copy2(args.configuration, args.output / 'configuration.json')
    shutil.copy2(__file__, args.output / Path(__file__).name)
    original_material = doc['materials'][doc['meshes'][0]['primitives'][0]['material']]
    color = texture_image(doc, original_binary, original_material, 'color')
    normal = texture_image(doc, original_binary, original_material, 'normal')
    packed = texture_image(doc, original_binary, original_material, 'metallic-roughness') if config.get('continuePackedMaterialMaps') else None
    occlusion = texture_image(doc, original_binary, original_material, 'occlusion') if config.get('continuePackedMaterialMaps') else None
    binary = bytearray(original_binary)
    attr_accessors = {key: append_accessor(doc, binary, value.astype('<f4'), key) for key, value in final_attrs.items()}
    primitives = [{'attributes': attr_accessors, 'indices': append_accessor(doc, binary, new_faces.astype('<u4').reshape(-1, 1)),
                   'material': doc['meshes'][0]['primitives'][0]['material']}]
    materials_receipt = []
    for label, triangles, detail in zip(['outer', 'inner'], cap_faces, details):
        maps, policy = cap_texture(args.output, label, detail, color, normal, int(config['textureResolution']), config.get('normalMapConvention', 'raw-uv-tangent'), packed, occlusion)
        material = copy.deepcopy(original_material)
        material['name'] = 'waist-' + label + '-continuation-diagnostic'
        material['pbrMetallicRoughness']['baseColorTexture']['index'] = embed_image(doc, binary, maps['base-color'])
        material['normalTexture']['index'] = embed_image(doc, binary, maps['normal'])
        if packed is not None:
            material['pbrMetallicRoughness']['metallicRoughnessTexture']['index'] = embed_image(doc, binary, maps['metallic-roughness'])
            material['occlusionTexture']['index'] = embed_image(doc, binary, maps['occlusion'])
        index = len(doc['materials'])
        doc['materials'].append(material)
        primitives.append({'attributes': attr_accessors, 'indices': append_accessor(doc, binary, triangles.astype('<u4').reshape(-1, 1)), 'material': index})
        materials_receipt.append({'label': label, 'maps': {key: {'path': str(path.resolve()), 'sha256': sha(path)} for key, path in maps.items()}, 'policy': policy})
    doc['meshes'][0]['primitives'] = primitives
    result = args.output / 'capped-local.glb'
    write_glb(result, doc, binary)
    final_doc, final_binary, reread_attrs, reread_faces = read_glb(result, allow_multiple=True)
    for key in attrs:
        if not np.array_equal(reread_attrs[key][:len(attrs[key])], attrs[key]):
            raise RuntimeError('Serialized GLB changed protected original attributes')
    if not np.array_equal(reread_faces, all_faces):
        raise RuntimeError('Serialized GLB changed triangle arrays')
    if final_binary[:len(original_binary)] != original_binary:
        raise RuntimeError('Serialized GLB changed original embedded buffer prefix')
    protected_hash = hashlib.sha256()
    for key in sorted(attrs):
        protected_hash.update(key.encode())
        protected_hash.update(attrs[key][faces[protected]].tobytes())
    if sha(source) != before:
        raise RuntimeError('Immutable v5 source changed')
    removed_coords = attrs['POSITION'][faces[np.asarray(deleted + clipped)]]
    np.savez_compressed(args.output / 'cap-provenance.npz', retainedSourceFaceIndices=protected,
                        clippedSourceFaceIndices=np.asarray(clipped), deletedSourceFaceIndices=np.asarray(deleted),
                        sourceFaces=faces, conditionedSourceFaces=new_faces, outerCapFaces=cap_faces[0], innerCapFaces=cap_faces[1])
    receipt = {'schemaVersion': 1, 'phase': 'localizedWaistCapDiagnostic', 'source': str(source), 'sourceSha256': before,
        'sourceUnchanged': True, 'configurationSha256': sha(args.configuration), 'scriptSha256': sha(Path(__file__)),
        'cutChestLocalZ': cut, 'stockChestPivotWorld': config['stockChestPivotWorld'],
        'geometryPolicy': 'Delete/clip only below the cut, preserve all source attribute rows and all complete triangles above it, add separated shallow outer and inner domes.',
        'retainedExactOriginalTriangles': len(retained), 'clippedSourceTriangles': len(clipped), 'deletedSourceTriangles': len(deleted),
        'protectedOriginalAttributeRowsExact': True, 'protectedOriginalTrianglesExact': True,
        'affectedSourceTriangleBoundsRawGLB': [removed_coords.min((0, 1)).tolist(), removed_coords.max((0, 1)).tolist()],
        'contours': describe(loops), 'outerDomeDepth': config['outerDomeDepth'], 'innerDomeDepth': config['innerDomeDepth'],
        'starShapeProof': star_shape, 'protectedTriangleAttributeSha256': protected_hash.hexdigest(),
        'actualSerializedProtectedAttributesExact': True, 'actualSerializedTrianglesExact': True,
        'capTriangleCounts': [len(row) for row in cap_faces], 'beforeTopology': before_topology, 'afterTopology': after_topology,
        'localCutBoundaryClosed': True, 'unrelatedSourceDefectsRemain': True, 'normalTextureStrength': original_material['normalTexture'].get('scale', 1),
        'originalEmbeddedBuffersPreservedPrefix': True, 'originalAtlasAndMaterialUnchanged': True,
        'materials': materials_receipt, 'result': str(result.resolve()), 'resultSha256': sha(result),
        'nativeCommonAtlasPending': True, 'productionAccepted': False, 'clientAccepted': False,
        'limitations': [f"Whole source still has {before_topology['boundaryEdges']} boundary edges and {before_topology['nonmanifoldEdges']} nonmanifold edges outside the local waist cap.",
                       'Upper connected inner wall and neck rim remain; this is not exterior-shell conditioning.',
                       'Separate cap atlases are offline diagnostics; native one-atlas packing requires a later recorded bake.',
                       'Boundary tangent transfer is analytic and requires rendered pose/material review.']}
    (args.output / 'waist-cap.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ['result', 'resultSha256', 'retainedExactOriginalTriangles', 'clippedSourceTriangles', 'deletedSourceTriangles', 'beforeTopology', 'afterTopology']}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cuts', type=float, nargs='+')
    parser.add_argument('--configuration', type=Path)
    args = parser.parse_args()
    if args.configuration:
        build(args)
    elif args.cuts:
        inspect(args)
    else:
        parser.error('Choose --cuts for inspection or --configuration for a localized cap')


if __name__ == '__main__':
    main()
