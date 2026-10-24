"""Native firearm placeholders and assembly blueprints.

Byte offsets follow _NwnLib/NwnMdlNodes.h in niv/nwn-tools. Decode the bounded
rigid tree before examining render/shadow flags; never trust a name-only match.
"""
from pathlib import Path
import struct
import sys

import numpy as np

from tools.headkit.common import ROOT, require
from tools.headkit.native_reader import decode
from .contracts import resref
from .firearms import PART_FIELDS, validate_assembly
from .fixture import blueprint, field
from .geometry import topology


def placeholder_geometry(center=(0, 0, 0), radius=.0005):
    center = np.asarray(center, dtype=float)
    require(center.shape == (3,) and np.isfinite(center).all(), 'Finite placeholder center required')
    require(type(radius) in (float, int) and .0001 <= radius <= .001, 'Tiny nondegenerate placeholder radius required')
    vertices = np.array([[1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]], float)*radius+center
    faces = np.array([[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]])
    if not topology(vertices, faces)['closedWound']: faces = faces[:, ::-1].copy()
    require(topology(vertices, faces)['closedWound'], 'Invalid placeholder tetrahedron')
    positions = vertices[faces]
    normals = np.cross(positions[:, 1]-positions[:, 0], positions[:, 2]-positions[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    return {'positions': positions, 'normals': np.repeat(normals[:, None, :], 3, axis=1),
            'uv': np.tile([[0., 0.], [1., 0.], [0., 1.]], (4, 1, 1))}


def placeholder_ascii(name, geometry):
    resref(name)
    p, n, uv = (np.asarray(geometry[k]) for k in ('positions', 'normals', 'uv'))
    require(p.shape == n.shape == (4, 3, 3) and uv.shape == (4, 3, 2), 'Four valid placeholder triangles required')
    require(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all(), 'Finite placeholder attributes required')
    require(topology(p.reshape(-1, 3), np.arange(12).reshape(-1, 3))['closedWound'], 'Closed outward placeholder required')
    require(np.max(np.ptp(p.reshape(-1, 3), axis=0)) <= .00200001, 'Placeholder exceeds hidden size limit')
    require(np.allclose(np.linalg.norm(n, axis=2), 1, atol=1e-7), 'Unit placeholder normals required')
    require(np.all((uv >= 0) & (uv <= 1)), 'Placeholder UV range')
    lines = [f'newmodel {name}', f'setsupermodel {name} NULL', 'classification ITEM',
             'setanimationscale 1', f'beginmodelgeom {name}', f'node dummy {name}',
             '  parent NULL', 'endnode', f'node trimesh {name}v', f'  parent {name}',
             '  position 0 0 0', '  orientation 0 0 0 0', '  ambient 0 0 0',
             '  diffuse 0 0 0', '  specular 0 0 0', '  bitmap NULL', '  render 0', '  shadow 0']
    for key, rows in [('verts', p.reshape(-1, 3)), ('normals', n.reshape(-1, 3)),
                      ('tverts', np.c_[uv.reshape(-1, 2), np.zeros(12)])]:
        lines.append(f'  {key} {len(rows)}')
        lines.extend('    '+' '.join(format(float(v), '.17g') for v in row) for row in rows)
    lines.append('  faces 4')
    lines.extend(f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in np.arange(12).reshape(-1, 3))
    lines.extend(['endnode', f'endmodelgeom {name}', f'donemodel {name}'])
    return '\n'.join(lines)+'\n'


def mesh_flags(data, model):
    rows = decode(data, model, require_tangents=False)
    # native_nodes is safe here after the strict decoder has bounded every node.
    sys.path.insert(0, str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine.stock_armor import native_nodes
    result = {}
    for offset, flags in native_nodes(data):
        if flags != 33: continue
        name = data[offset+32:offset+64].split(b'\0')[0].decode('ascii')
        require(name not in result, 'Duplicate native mesh name')
        shadow, _, render = struct.unpack_from('<III', data, offset+0xd4)
        require(render in (0, 1) and shadow in (0, 1), 'Invalid render/shadow flag')
        result[name] = {'render': render, 'shadow': shadow}
    require(set(result) == {r['name'] for r in rows}, 'Native flag tree differs from decoded geometry')
    return result


def audit_placeholder(binary, name, expected):
    """Sanitize fresh binary and prove exact hidden geometry and no shadow node."""
    raw = Path(binary).read_bytes()
    before = decode(raw, name, require_tangents=False)
    require(len(before) == 1 and before[0]['name'] == name+'v', 'One placeholder mesh required')
    sys.path.insert(0, str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine.stock_armor import sanitize_binary, string_fields, leaked_text
    clean = sanitize_binary(raw)
    allowed = np.zeros(len(raw), bool)
    for offset, count in string_fields(raw): allowed[offset:offset+count] = True
    changed = np.frombuffer(raw, np.uint8) != np.frombuffer(clean, np.uint8)
    require(not changed[~allowed].any() and clean == sanitize_binary(clean) and not leaked_text(clean),
            'Placeholder sanitization changed non-string bytes or retained leaked text')
    flags = mesh_flags(clean, name)
    require(flags == {name+'v': {'render': 0, 'shadow': 0}}, 'Placeholder is rendered or casts a shadow')
    actual = decode(clean, name, require_tangents=False)[0]
    require(all(t.lower() in ('', 'null') for t in actual['textures']), 'Placeholder has a material dependency')
    for native_key, key in [('position', 'positions'), ('normal', 'normals'), ('uv', 'uv')]:
        corners = actual[native_key][actual['faces']]
        require(corners.shape == expected[key].shape and np.allclose(corners, expected[key], atol=2e-7, rtol=0),
                'Placeholder corner attribute mismatch: '+key)
    require(topology(actual['position'], actual['faces'])['closedWound'], 'Compiled placeholder not closed/outward')
    return clean, {'triangles': 4, 'shadowTriangles': 0, 'flags': flags, 'nativeRoundtrip': True,
                   'zeroedTailBytes': int(changed.sum())}


def variant_blueprint(allocation, variant, counts, display_name):
    validate_assembly(allocation, variant, counts)
    require(isinstance(display_name, str) and display_name.strip(), 'Named variant required')
    result = blueprint(61, {'modelIndex': allocation['modelIndex'], 'colourIndex': variant['colour']},
                       {'blueprint': variant['blueprint'], 'displayName': display_name})
    for p in PART_FIELDS: result[PART_FIELDS[p]] = field('byte', variant['utiParts'][PART_FIELDS[p]])
    return result


def audit_blueprint_roundtrip(binary, decoded, expected):
    """Check all fields and the root struct ID omitted by nwn_gff's JSON writer."""
    raw = Path(binary).read_bytes()
    require(len(raw) >= 56 and raw[:8] == b'UTI V3.2', 'Native UTI header required')
    offset, count = struct.unpack_from('<II', raw, 8)
    require(count >= 1 and offset >= 56 and offset+12*count <= len(raw), 'Invalid UTI struct table')
    require(expected.get('__struct_id') == -1 and struct.unpack_from('<I', raw, offset)[0] == 0xffffffff,
            'Native UTI root struct ID differs')
    require(decoded == {key: value for key, value in expected.items() if key != '__struct_id'},
            'Blueprint native field roundtrip differs')
    return {'allFieldsExact': True, 'rootStructId': -1}
