"""Verify Armory's local SRT then bake reviewed rigid source frames once.

Skin/animated equipment needs a separate bind-aware conversion. Flattened
mesh ancestry is recorded; mesh names, UVs and material bindings survive.
"""
import re
import numpy as np
from retarget import NODE, nodes, rotations
from audit_geometry import arrays
from pipeline import digest


def profile_affine(transform):
    scale = np.asarray(transform['scale'], float)
    translation = np.asarray(transform['translate'], float)
    degrees = np.asarray(transform.get('rotate', [0, 0, 0]), float)
    if any(v.shape != (3,) or not np.isfinite(v).all() for v in (scale, translation, degrees)):
        raise RuntimeError('Equipment profile requires finite three-component SRT values')
    if np.any(scale <= 0):
        raise RuntimeError('Equipment scale must be positive; reflection/collapse needs separate review')
    # Pinned v1.3.4: X then Y then Z; X/Y signs are negated.
    rx = rotations([1, 0, 0, np.deg2rad(-degrees[0])])
    ry = rotations([0, 1, 0, np.deg2rad(-degrees[1])])
    rz = rotations([0, 0, 1, np.deg2rad(degrees[2])])
    rotation = rz @ ry @ rx
    for key in ('minimum', 'maximum', 'tscale', 'trotate', 'ttranslate', 'tminimum', 'tmaximum'):
        if key in transform:
            raise RuntimeError('Selective geometry/UV transforms require a different proof: ' + key)
    return rotation @ np.diag(scale), translation


def rigid_frames(text):
    skeleton = nodes(text)
    matches = list(NODE.finditer(text.split('endmodelgeom', 1)[0]))
    blocks = {block[2].lower(): block for block in matches}
    if len(blocks) != len(matches):
        raise RuntimeError('Duplicate equipment node names')
    frames, visiting = {}, set()
    def visit(name):
        if name in frames:
            return frames[name]
        if name in visiting:
            raise RuntimeError('Equipment parent cycle: ' + name)
        visiting.add(name)
        node = skeleton[name]
        field = re.search(r'(?mi)^\s*scale\s+(\S+)', blocks[name][3])
        scale = float(field[1]) if field else 1.
        if not np.isfinite(scale) or scale <= 0:
            raise RuntimeError('Rigid node scale must be positive: ' + name)
        matrix = np.eye(4)
        matrix[:3, :3] = rotations(node['orientation']) * scale
        matrix[:3, 3] = node['position']
        parent = node['parent']
        if parent != 'null':
            if parent not in skeleton:
                raise RuntimeError('Unresolved equipment parent: ' + parent)
            matrix = visit(parent) @ matrix
        visiting.remove(name)
        frames[name] = matrix
        return matrix
    for name in skeleton:
        visit(name)
    return skeleton, blocks, frames


def directions(values, linear):
    result = np.asarray(values, float) @ linear.T
    lengths = np.linalg.norm(result, axis=1)
    if not np.isfinite(result).all() or np.any(lengths < 1e-12):
        raise RuntimeError('Equipment has a nonfinite or zero directional vector')
    return result / lengths[:, None]


def replace_field(body, key, value):
    expression = r'(?mi)^\s*' + key + r'\s+[^\n]+'
    line = '  ' + key + ' ' + value
    return re.sub(expression, lambda _: line, body) if re.search(expression, body) else body + line + '\n'


def replace_array(body, key, rows):
    found = re.search(r'(?mi)^\s*' + key + r'\s+(\d+)\s*\n', body)
    if not found:
        raise RuntimeError('Missing equipment array: ' + key)
    end = found.end() + sum(len(line) for line in body[found.end():].splitlines(keepends=True)[:int(found[1])])
    replacement = '  ' + key + ' ' + str(len(rows)) + '\n'
    replacement += ''.join('    ' + ' '.join(f'{v:.10g}' for v in row) + '\n' for row in rows)
    return body[:found.start()] + replacement + body[end:]


def error(actual, expected, label, tolerance=1e-5):
    actual, expected = np.asarray(actual, float), np.asarray(expected, float)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise RuntimeError('Equipment ' + label + ' shape/data differ')
    value = float(np.max(np.abs(actual - expected))) if actual.size else 0.
    if value > tolerance:
        raise RuntimeError('Equipment ' + label + ' differs from profile: ' + str(value))
    return value


def correct_rigid(source, target, transform):
    if source.resolve() == target.resolve():
        raise RuntimeError('Equipment correction must not overwrite its frozen source')
    original, text = source.read_text(encoding='ascii'), target.read_text(encoding='ascii')
    before = digest(target)
    linear, translation = profile_affine(transform)
    source_nodes, source_blocks, source_world = rigid_frames(original)
    _, target_blocks, _ = rigid_frames(text)
    source_meshes = {k: v for k, v in source_blocks.items() if arrays(v[3], 'verts')}
    target_meshes = {k: v for k, v in target_blocks.items() if arrays(v[3], 'verts')}
    if not source_meshes or set(source_meshes) != set(target_meshes):
        raise RuntimeError('Rigid armory mesh inventory differs: ' + source.name)
    if any(b[1].lower() not in ('dummy', 'trimesh', 'danglymesh') for b in source_blocks.values()):
        raise RuntimeError('Skin/emitter equipment requires a separate conversion: ' + source.name)
    if re.search(r'(?mi)^newanim\s', original):
        raise RuntimeError('Local animated equipment requires separate retargeting')
    root = re.search(r'(?mi)^newmodel\s+(\S+)', text)[1]
    source_root = re.search(r'(?mi)^newmodel\s+(\S+)', original)[1].lower()
    if source_root not in source_blocks or root.lower() not in target_blocks:
        raise RuntimeError('Rigid equipment requires its declared root node')
    preserved = ('bitmap', 'materialname', 'ambient', 'diffuse', 'specular', 'shininess',
                 'render', 'shadow', 'beaming', 'rotatetexture', 'tilefade', 'alpha',
                 'transparencyhint', 'inheritcolor', 'selfillumcolor')
    proof, replacements = [], []
    for key, src in source_meshes.items():
        dst = target_meshes[key]
        if src[1].lower() != dst[1].lower():
            raise RuntimeError('Equipment mesh type changed: ' + key)
        if re.search(r'(?mi)^\s*(weights|bonemap|boneweights)\s', src[3] + dst[3]):
            raise RuntimeError('Skin bindings must not enter rigid conversion: ' + key)
        for field in preserved:
            expression = r'(?mi)^\s*' + field + r'\s+([^\n]+)'
            a, b = re.search(expression, src[3]), re.search(expression, dst[3])
            if (a[1].strip() if a else None) != (b[1].strip() if b else None):
                raise RuntimeError('Equipment material/binding changed: ' + key + ' ' + field)
        for field in ('faces', 'tverts', 'tverts1', 'tverts2', 'tverts3', 'colors', 'constraints'):
            if arrays(src[3], field) != arrays(dst[3], field):
                raise RuntimeError('Equipment topology/UV/constraint changed: ' + key + ' ' + field)
        if src[1].lower() == 'danglymesh':
            for field in ('displacement', 'period', 'tightness'):
                expression = r'(?mi)^\s*' + field + r'\s+(\S+)'
                a, b = re.search(expression, src[3]), re.search(expression, dst[3])
                if not a or not b or float(a[1]) != float(b[1]):
                    raise RuntimeError('Dangly physics changed: ' + key + ' ' + field)
        vertices = np.asarray(arrays(src[3], 'verts'))
        raw_error = error(arrays(dst[3], 'verts'), vertices @ linear.T + translation, 'Armory local vertices')
        source_frame = source_world[key]
        composite = linear @ source_frame[:3, :3]
        body = replace_array(dst[3], 'verts', vertices @ composite.T + linear @ source_frame[:3, 3] + translation)
        normals = arrays(src[3], 'normals')
        if bool(normals) != bool(arrays(dst[3], 'normals')):
            raise RuntimeError('Equipment authored normals appeared/disappeared: ' + key)
        normal_error = None
        if normals:
            normal_error = error(arrays(dst[3], 'normals'), directions(normals, np.linalg.inv(linear).T), 'Armory normals')
            final_normals = directions(normals, np.linalg.inv(composite).T)
            body = replace_array(body, 'normals', final_normals)
        tangents = arrays(src[3], 'tangents')
        if bool(tangents) != bool(arrays(dst[3], 'tangents')):
            raise RuntimeError('Equipment authored tangents appeared/disappeared: ' + key)
        if tangents:
            tangent_values = np.asarray(tangents, float)
            if tangent_values.ndim != 2 or tangent_values.shape[1] != 4:
                raise RuntimeError('Equipment tangents must contain XYZ and handedness')
            raw = np.c_[directions(tangent_values[:, :3], np.linalg.inv(linear).T), tangent_values[:, 3]]
            error(arrays(dst[3], 'tangents'), raw, 'Armory tangents')
            final_tangents = directions(tangent_values[:, :3], composite)
            if normals:
                if len(final_normals) != len(final_tangents):
                    raise RuntimeError('Tangent/normal association requires explicit handling')
                final_tangents -= np.sum(final_tangents * final_normals, axis=1)[:, None] * final_normals
                final_tangents = directions(final_tangents, np.eye(3))
            body = replace_array(body, 'tangents', np.c_[final_tangents, tangent_values[:, 3]])
        body = replace_field(body, 'parent', root)
        body = replace_field(body, 'position', '0 0 0')
        body = replace_field(body, 'orientation', '0 0 1 0')
        body = replace_field(body, 'scale', '1')
        replacements.append((dst.start(), dst.end(), f'node {dst[1]} {dst[2]}\n{body}endnode'))
        proof.append({'node': src[2], 'sourceParent': source_nodes[key]['parent'],
                      'sourceWorldFrame': source_frame.tolist(), 'vertexCount': len(vertices),
                      'rawLocalVertexError': raw_error, 'rawNormalError': normal_error})
    root_block = target_blocks[root.lower()]
    if root.lower() in target_meshes or root_block[1].lower() != 'dummy':
        raise RuntimeError('Equipment root must be a nonrendering dummy')
    root_body = replace_field(root_block[3], 'parent', 'NULL')
    root_body = replace_field(root_body, 'position', '0 0 0')
    root_body = replace_field(root_body, 'orientation', '0 0 1 0')
    root_body = replace_field(root_body, 'scale', '1')
    replacements.append((root_block.start(), root_block.end(), f'node dummy {root}\n{root_body}endnode'))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    text = re.sub(r'(?mi)^setsupermodel\s+\S+\s+\S+', f'setsupermodel {root} NULL', text)
    _, corrected_blocks, corrected_world = rigid_frames(text)
    errors, normal_errors = [], []
    for key, src in source_meshes.items():
        dst = corrected_blocks[key]
        vertices = np.asarray(arrays(src[3], 'verts'))
        source_frame, frame = source_world[key], corrected_world[key]
        expected = (vertices @ source_frame[:3, :3].T + source_frame[:3, 3]) @ linear.T + translation
        observed = np.asarray(arrays(dst[3], 'verts')) @ frame[:3, :3].T + frame[:3, 3]
        errors.append(error(observed, expected, 'corrected world vertices'))
        if arrays(src[3], 'normals'):
            expected_normal = directions(arrays(src[3], 'normals'), np.linalg.inv(linear @ source_frame[:3, :3]).T)
            observed_normal = directions(arrays(dst[3], 'normals'), np.linalg.inv(frame[:3, :3]).T)
            normal_errors.append(error(observed_normal, expected_normal, 'corrected world normals'))
    target.write_text(text, encoding='ascii')
    return {'armoryOutputSha256': before, 'correctedSha256': digest(target),
            'meshNodes': len(errors), 'maximumWorldTransformError': max(errors),
            'maximumWorldNormalError': max(normal_errors, default=0.),
            'meshTypes': [b[1].lower() for b in source_meshes.values()], 'danglyPhysicsPreserved': True,
            'vertexOrderTopologyUvsMaterialsPreserved': True, 'sourceFrames': proof,
            'affineLinearNwn': linear.tolist(), 'translationNwn': translation.tolist(),
            'method': 'Verify v1.3.4 local SRT; bake source hierarchy into identity root-local meshes; translate once',
            'parentHierarchyFlattened': True, 'skinBindingsSupported': False, 'clientAccepted': False}
