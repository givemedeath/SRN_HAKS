"""Complete static rigid assemblies and triangle silhouettes, without runtime claims.

ASCII uses the repository node/parser and strict hierarchy evaluator. Native tree
layout follows the existing heads/native_reader.py; unlike that identity-only
reader, this measurement reader evaluates static position/orientation/scale.
Skins and animated local controllers fail rather than being approximated.
"""
from pathlib import Path
import re
import struct

import numpy as np
from PIL import Image, ImageDraw

from .audit_geometry import arrays
from .retarget import NODE, nodes, rotations
from .target_contract import PART_JOINTS
from .measurement_common import require


def frames(skeleton):
    result, visiting = {}, set()

    def visit(name):
        require(name in skeleton, 'Unresolved model parent: ' + name)
        require(name not in visiting, 'Model parent cycle: ' + name)
        if name in result:
            return result[name]
        visiting.add(name)
        row = skeleton[name]
        matrix = np.eye(4)
        matrix[:3, :3] = rotations(row['orientation']) * row.get('scale', 1.0)
        matrix[:3, 3] = row['position']
        if row['parent'] != 'null':
            matrix = visit(row['parent']) @ matrix
        require(np.isfinite(matrix).all(), 'Nonfinite model transform')
        visiting.remove(name)
        result[name] = matrix
        return matrix

    for name in skeleton:
        visit(name)
    return result


def ascii_model(text):
    geometry = text.split('endmodelgeom', 1)[0]
    matches = list(NODE.finditer(geometry))
    # Stock female has two distinct, unreferenced Impact attachment dummies.
    # Preserve both under internal identifiers; referenced duplicate parents or
    # mesh names remain ambiguous and must fail rather than choosing one.
    counts = {}
    parents = {p[1].lower() for p in re.finditer(r'(?mi)^\s*parent\s+(\S+)', geometry)}
    rewritten = []
    for match in matches:
        name = match[2].lower()
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > 1:
            require(match[1].lower() == 'dummy' and name not in parents and
                    all(m[1].lower() == 'dummy' for m in matches if m[2].lower() == name),
                    'Duplicate model nodes')
            name += '__duplicate_' + str(counts[name])
        rewritten.append('node ' + match[1] + ' ' + name + '\n' + match[3] + 'endnode\n')
    geometry = ''.join(rewritten)
    matches = list(NODE.finditer(geometry))
    require(len({m[2].lower() for m in matches}) == len(matches), 'Duplicate internal model nodes')
    skeleton = nodes(geometry)
    meshes = []
    for match in matches:
        kind, name, body = match[1].lower(), match[2].lower(), match[3]
        require(kind in ('dummy', 'trimesh', 'danglymesh'), 'Unsupported node type: ' + kind)
        scale = re.search(r'(?mi)^\s*scale\s+(\S+)', body)
        skeleton[name]['scale'] = float(scale[1]) if scale else 1.0
        require(not re.search(r'(?mi)^\s*(?:position|orientation|scale)(?:bezier)?key\b', body),
                'Animated geometry-local controller unsupported')
        if kind in ('trimesh', 'danglymesh'):
            points = np.asarray(arrays(body, 'verts'), dtype=float)
            face_rows = arrays(body, 'faces')
            faces_array = np.asarray([r[:3] for r in face_rows], dtype=float)
            require(points.ndim == 2 and points.shape[1] == 3 and len(points), 'Invalid vertices')
            require(faces_array.ndim == 2 and faces_array.shape[1] == 3 and len(faces_array), 'Invalid faces')
            require(np.isfinite(points).all() and np.isfinite(faces_array).all(), 'Nonfinite mesh')
            require(np.equal(faces_array, faces_array.astype(int)).all(), 'Noninteger face index')
            indices = faces_array.astype(int)
            require(indices.min() >= 0 and indices.max() < len(points), 'Face escapes mesh')
            render = re.search(r'(?mi)^\s*render\s+(\S+)', body)
            meshes.append({'name': name, 'position': points, 'faces': indices,
                           'render': int(render[1]) != 0 if render else True})
    require(skeleton, 'Empty model hierarchy')
    return skeleton, meshes


def native_model(data, model):
    require(len(data) >= 12, 'Truncated native header')
    zero, raw_offset, raw_size = struct.unpack_from('<III', data)
    require(zero == 0 and 12 + raw_offset + raw_size == len(data), 'Invalid native sections')

    def block(offset, size):
        require(0 <= offset and offset + size <= raw_offset, 'Native pointer escapes model section')
        return 12 + offset

    def array(node, field, width):
        offset, count, capacity = struct.unpack_from('<III', data, node + field)
        require(count <= capacity, 'Invalid native array capacity')
        block(offset, count * width)
        return offset, count

    # Same bounded child-tree layout as audit_target_native_part.py.
    root, declared_count = struct.unpack_from('<II', data, block(0, 0x50) + 0x48)
    skeleton, meshes, visited = {}, [], set()
    source_names = {}

    def visit(offset, parent):
        require(offset not in visited and len(visited) < 4096, 'Native node cycle/shared child/excessive tree')
        visited.add(offset)
        node = block(offset, 0x70)
        flags = struct.unpack_from('<I', data, node + 0x6c)[0]
        require(flags in (1, 33, 289), 'Unsupported native node flags: ' + str(flags))
        name = data[node + 32:node + 64].split(b'\0')[0].decode('ascii').lower()
        require(name, 'Empty native node name')
        children, nchildren = array(node, 0x48, 4)
        if name in source_names:
            previous_flags, previous_children, copies = source_names[name]
            require(flags == previous_flags == 1 and nchildren == previous_children == 0
                    and name not in PART_JOINTS.values(), 'Duplicate native mesh/joint/parent name')
            source_names[name] = (flags, nchildren, copies + 1)
            name += '__duplicate_' + str(copies + 1)
            require(name not in skeleton, 'Duplicate internal native node name')
        else:
            source_names[name] = (flags, nchildren, 1)
        row = {'parent': parent, 'position': np.zeros(3), 'orientation': [0, 0, 0, 0], 'scale': 1.0}
        keys, count = array(node, 0x54, 12)
        values, nvalues = array(node, 0x60, 4)
        floats = np.frombuffer(data, '<f4', nvalues, 12 + values)
        seen = set()
        for index in range(count):
            kind, rows, key_start, value_start, columns, pad = struct.unpack_from('<ihhhbb', data, 12 + keys + 12 * index)
            require(rows == 1 and kind in (8, 20, 36, 100, 128) and kind not in seen,
                    'Unsupported animated/duplicate native controller')
            seen.add(kind)
            width = {8: 3, 20: 4, 36: 1, 100: 3, 128: 1}[kind]
            require(columns == width and 0 <= value_start and value_start + width <= nvalues, 'Invalid native controller')
            value = floats[value_start:value_start + width].astype(float)
            require(np.isfinite(value).all(), 'Nonfinite native controller')
            if kind == 8:
                row['position'] = value
            elif kind == 36:
                row['scale'] = float(value[0])
            elif kind == 20:
                require(abs(np.linalg.norm(value) - 1) < 1e-4, 'Invalid native quaternion')
                length = np.linalg.norm(value[:3])
                row['orientation'] = [*(value[:3] / length if length > 1e-12 else np.zeros(3)),
                                      float(2 * np.arctan2(length, value[3]))]
            elif kind == 128:
                require(value[0] == 1, 'Transparent native mesh needs explicit silhouette policy')
        skeleton[name] = row
        if flags in (33, 289):
            block(offset, 0x264)
            face_offset, nfaces = array(node, 0x78, 32)
            vertices = struct.unpack_from('<H', data, node + 0x230)[0]
            pointer = struct.unpack_from('<I', data, node + 0x22c)[0]
            require(vertices > 0 and nfaces > 0 and pointer != 0xffffffff
                    and pointer + vertices * 12 <= raw_size, 'Invalid native vertices')
            points = np.frombuffer(data, '<f4', vertices * 3, 12 + raw_offset + pointer).reshape(-1, 3).astype(float)
            faces_array = np.ndarray((nfaces, 3), dtype='<u2', buffer=data,
                                    offset=12 + face_offset + 26, strides=(32, 2)).astype(int)
            require(np.isfinite(points).all() and faces_array.max() < vertices, 'Invalid native mesh')
            if flags == 289:
                block(offset, 0x288)
                constraints, nconstraints = array(node, 0x270, 4)
                require(nconstraints == vertices, 'Dangly constraint count differs from vertices')
                values = np.frombuffer(data, '<f4', nconstraints, 12 + constraints)
                parameters = struct.unpack_from('<fff', data, node + 0x27c)
                require(np.isfinite(values).all() and np.isfinite(parameters).all(), 'Nonfinite dangly data')
            render = struct.unpack_from('<I',data,node+0xdc)[0]
            require(render in (0,1), 'Invalid native render flag')
            meshes.append({'name': name, 'position': points, 'faces': faces_array, 'render': bool(render)})
        for child in struct.unpack_from('<' + 'I' * nchildren, data, 12 + children):
            visit(child, name)

    visit(root, 'null')
    # Installed stock files can carry overreported exporter metadata (108 for
    # a two-node static foot/head). The bounded reachable tree is authoritative;
    # underreporting remains invalid. Preserve the discrepancy in measurements.
    require(len(visited) <= declared_count, 'Native tree does not match declared node count')
    for mesh in meshes:
        mesh['nativeNodeCounts'] = {'declared': declared_count, 'reachable': len(visited)}
        mesh['surfaceBasis'] = 'static bind; secondary dangly simulation unmeasured'
    require(model.lower() in skeleton, 'Declared native model root absent')
    require(skeleton[model.lower()]['parent'] == 'null', 'Named model is not native root')
    return skeleton, meshes


def decode(path):
    path = Path(path)
    data = path.read_bytes()
    return native_model(data, path.stem) if data[:4] == b'\0\0\0\0' else ascii_model(data.decode('cp1252'))


def assemble(rig_path, parts):
    skeleton, rig_meshes = decode(rig_path)
    rig_frames = frames(skeleton)
    output = []
    for mesh in rig_meshes:
        transform = rig_frames[mesh['name']]
        points = mesh['position'] @ transform[:3, :3].T + transform[:3, 3]
        output.append({**mesh, 'part': 'rig', 'position': points})
    for part, path in parts.items():
        require(part in PART_JOINTS, 'Unknown body part: ' + part)
        joint = PART_JOINTS[part].lower()
        require(joint in rig_frames, 'Rig joint missing: ' + joint)
        local_skeleton, meshes = decode(path)
        local_frames = frames(local_skeleton)
        require(meshes, 'Part has no mesh: ' + part)
        for mesh in meshes:
            transform = rig_frames[joint] @ local_frames[mesh['name']]
            points = mesh['position'] @ transform[:3, :3].T + transform[:3, 3]
            output.append({**mesh, 'part': part, 'position': points, 'attachmentFrame':rig_frames[joint].tolist()})
    return output, {name: matrix[:3, 3].tolist() for name, matrix in rig_frames.items()}


def rasterize(meshes, view, metres_per_pixel=0.002):
    meshes = [m for m in meshes if m.get('render', True)]
    require(meshes, 'No rendered surface for silhouette')
    require(view in ('front', 'back', 'left', 'right'), 'Unknown view')
    require(np.isfinite(metres_per_pixel) and metres_per_pixel > 0, 'Invalid pixel scale')
    axis = 0 if view in ('front', 'back') else 1
    sign = -1 if view in ('back', 'right') else 1
    all_points = np.concatenate([m['position'] for m in meshes])
    horizontal = all_points[:, axis] * sign
    low = np.array([horizontal.min(), all_points[:, 2].min()])
    high = np.array([horizontal.max(), all_points[:, 2].max()])
    size = np.ceil((high - low) / metres_per_pixel).astype(int) + 3
    require(np.all(size > 0) and int(size[0]) * int(size[1]) <= 16000000, 'Raster size unsafe')
    mask = Image.new('1', tuple(size), 0)
    draw = ImageDraw.Draw(mask)
    labels = Image.new('I', tuple(size), 0)
    label_draw = ImageDraw.Draw(labels)
    mapping = {}
    for mesh in meshes:
        key = mesh['part']
        mapping.setdefault(key, len(mapping) + 1)
        points = mesh['position']
        xy = np.column_stack([(points[:, axis] * sign - low[0]) / metres_per_pixel + 1,
                              (high[1] - points[:, 2]) / metres_per_pixel + 1])
        for face in mesh['faces']:
            polygon = [tuple(v) for v in xy[face]]
            draw.polygon(polygon, fill=1)
            label_draw.polygon(polygon, fill=mapping[key])
    return np.asarray(mask, dtype=bool).copy(), labels, {
        'metresPerPixel': metres_per_pixel, 'horizontalMin': float(low[0]),
        'zMax': float(high[1]), 'paddingPixels': 1, 'parts': mapping,
        'labelPolicy': 'union ownership, later parts overwrite overlap; no visibility claim'}


def cross_section(meshes, z, axis):
    """Exact projected extent of triangle/plane intersections, in metres."""
    hits = []
    for mesh in meshes:
        if not mesh.get('render', True):
            continue
        triangle = mesh['position'][mesh['faces']]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            left, right = triangle[:, a], triangle[:, b]
            distance = right[:, 2] - left[:, 2]
            select = (np.minimum(left[:, 2], right[:, 2]) <= z) & (np.maximum(left[:, 2], right[:, 2]) >= z)
            select &= np.abs(distance) > 1e-12
            amount = (z - left[select, 2]) / distance[select]
            hits.extend((left[select, axis] + amount * (right[select, axis] - left[select, axis])).tolist())
    return float(max(hits) - min(hits)) if hits else None


def measure(meshes, joints):
    visible = [m for m in meshes if m.get('render',True)]
    require(visible, 'No rendered bind surfaces')
    points = np.concatenate([m['position'] for m in visible])
    low, high = points.min(axis=0), points.max(axis=0)
    height = float(high[2] - low[2])
    require(height > 0, 'Zero body stature')
    segments = {}
    for label, first, second in (
        ('upperArmLeft', 'lbicep_g', 'lforearm_g'), ('upperArmRight', 'rbicep_g', 'rforearm_g'),
        ('forearmLeft', 'lforearm_g', 'lhand_g'), ('forearmRight', 'rforearm_g', 'rhand_g'),
        ('thighLeft', 'lthigh_g', 'lshin_g'), ('thighRight', 'rthigh_g', 'rshin_g'),
        ('shinLeft', 'lshin_g', 'lfoot_g'), ('shinRight', 'rshin_g', 'rfoot_g')):
        if first in joints and second in joints:
            segments[label] = float(np.linalg.norm(np.array(joints[first]) - joints[second]))
    return {'bindStatureMeters': height, 'boundsMeters': [low.tolist(), high.tolist()],
            'jointSegmentMeters': segments, 'jointPositionsMeters': joints,
            'meshCount': len(meshes), 'renderedMeshCount':len(visible),
            'vertexCount': sum(len(m['position']) for m in meshes),
            'runtimeScaling': {'status': 'unverified', 'effectiveStatureMeters': None},
            'meshInventory': [{'part': m['part'], 'node': m['name'], 'render':m.get('render',True), 'vertices': len(m['position']),
                               'triangles': len(m['faces'])} for m in meshes]}
