"""Prepare target-bound literal native material inputs; no compile/stage/conversion.

Candidate meshes require completed independently pinned native audits. Installed
stock neck references preserve literal P/N/UV/indices and optional native arrays.
Missing legacy tangents are recorded, never reconstructed. Output is offline only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

import numpy as np

import target_contract as c

KEYS = ('position', 'normal', 'uv', 'tangent', 'sign', 'faces')
MODES = ('emission-only-color', 'neutral-native-material')
VIEWS = {'anterior-yplus': (0, 1, 0), 'posterior-yminus': (0, -1, 0),
         'left-xplus': (1, 0, 0), 'right-xminus': (-1, 0, 0)}


def save(path, value):
    path = Path(path)
    c.require(not path.exists(), 'Fresh immutable preview output required')
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def digest_array(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def pin(row, frozen):
    c.require(isinstance(row, dict) and set(row) == {'path', 'sha256'}
              and isinstance(row['path'], str) and Path(row['path']).is_absolute()
              and isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']),
              'Explicit absolute path/hash pin required')
    path = Path(row['path']).resolve()
    c.require(path.is_file() and c.sha(path) == row['sha256'], 'Changed preview input: '+str(path))
    c.require(str(path) not in frozen or frozen[str(path)] == row['sha256'], 'Conflicting preview pin')
    frozen[str(path)] = row['sha256']
    return path


def validate_identity(target):
    identity = target['identity']
    c.require(c.rig_mode(target) == 'stock-exact' and identity['gender'] == 'female'
              and identity['prefix'] == 'pfh0' and identity['phenotype'] == 0
              and identity['raceId'] == 6 and identity['appearanceRow'] == 6,
              'Female Human pfh0 stock-exact preview target required')


def controls(cfg):
    required = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'coordinateSpace',
                'stockInventory', 'skinPalette', 'paletteRows', 'parts', 'poses', 'render'}
    c.require(isinstance(cfg, dict) and set(cfg) == required and cfg['schemaVersion'] == 1
              and cfg['kind'] == 'target-native-material-preview-inputs' and cfg['diagnosticOnly'] is True,
              'Explicit target native preview configuration required')
    c.require(cfg['coordinateSpace'] in ('working', 'runtime') and cfg['paletteRows'] == [3, 8]
              and all(type(row) is int for row in cfg['paletteRows']), 'Declared space and palettes 3/8 required')
    parts = cfg['parts']
    c.require(isinstance(parts, dict) and parts and set(parts) <= c.BODY_PARTS | {'neck'},
              'Declared body parts or stock neck only')
    for part, row in parts.items():
        c.require(isinstance(row, dict) and row.get('kind') in ('audited-candidate', 'installed-stock-neck',
                  'audited-derived-native-candidate', 'derivation-compiler-parent-control'),
                  'Explicit candidate audit or installed stock neck kind required')
        if row['kind'] == 'installed-stock-neck':
            expected = {'kind', 'binding', 'nativeModel', 'plt'}
        elif row['kind'] == 'audited-candidate':
            expected = {'kind', 'binding', 'nativeModel', 'nativeAudit'}
        else:
            expected = {'kind', 'binding', 'nativeModel', 'nativeAudit', 'nativeDerivation'}
        c.require(set(row) == expected, 'Unsupported preview part inputs')
        c.require((row['kind'] == 'installed-stock-neck' and part == 'neck')
                  or (row['kind'] != 'installed-stock-neck' and part in c.BODY_PARTS), 'Part/source ownership differs')
    poses = cfg['poses']
    c.require(isinstance(poses, list) and poses, 'Explicit nonempty pose list required')
    ids = set()
    for row in poses:
        c.require(isinstance(row, dict) and (set(row) == {'id'} or set(row) == {'id', 'clip', 'time'}),
                  'Stock bind or declared clip/time pose required')
        c.require(isinstance(row['id'], str) and re.fullmatch('[a-z0-9-]+', row['id']) and row['id'] not in ids,
                  'Distinct safe pose identifiers required')
        ids.add(row['id'])
        if 'clip' in row:
            c.require(isinstance(row['clip'], str) and re.fullmatch('[a-zA-Z0-9_]+', row['clip'])
                      and type(row['time']) in (int, float) and np.isfinite(row['time']) and row['time'] >= 0,
                      'Finite declared stock animation time required')
        else:
            c.require(row['id'] == 'stock-bind', 'Unanimated pose must explicitly be stock-bind')
    render = cfg['render']
    c.require(isinstance(render, dict) and set(render) == {'width', 'height', 'modes', 'views', 'focusParts', 'padding'},
              'Explicit bounded render controls required')
    c.require(all(type(render[k]) is int and 128 <= render[k] <= 1536 for k in ('width', 'height')),
              'Bounded integer pixel dimensions required')
    c.require(isinstance(render['modes'], list) and render['modes'] and len(set(render['modes'])) == len(render['modes'])
              and set(render['modes']) <= set(MODES), 'Declared offline material modes required')
    c.require(isinstance(render['views'], list) and render['views'] and len(set(render['views'])) == len(render['views'])
              and set(render['views']) <= set(VIEWS), 'Explicit cardinal camera directions required')
    c.require(isinstance(render['focusParts'], list) and render['focusParts']
              and len(set(render['focusParts'])) == len(render['focusParts']) and set(render['focusParts']) <= set(parts),
              'Declared present framing parts required')
    c.require(type(render['padding']) in (int, float) and np.isfinite(render['padding'])
              and 1.01 <= render['padding'] <= 2, 'Bounded common camera padding required')


def stock_neck_decode(data, model):
    """Bounded legacy detached tree; preserve missing T/sign and packed colors.

    This additive decoder is deliberately stock-neck only. Native stock colors
    must be identity white; non-white packed color semantics require a separate
    explicit shader implementation, not omission.
    """
    c.require(model == 'pfh0_neck001' and len(data) >= 12+0xe8, 'Installed female stock neck only')
    zero, raw_offset, raw_size = struct.unpack_from('<III', data)
    c.require(zero == 0 and 12+raw_offset+raw_size == len(data), 'Complete stock native sections required')
    end = 12+raw_offset

    def region(offset, count, width):
        c.require(offset >= 0 and count >= 0 and 12+offset+count*width <= end, 'Stock native model bounds exceeded')
        return 12+offset

    def u32(at):
        c.require(12 <= at and at+4 <= end, 'Stock native field bounds exceeded')
        return struct.unpack_from('<I', data, at)[0]

    def name(at, width):
        c.require(12 <= at and at+width <= end, 'Stock native name bounds exceeded')
        blob = data[at:at+width]
        c.require(b'\0' in blob, 'Unterminated stock native name')
        return blob.split(b'\0', 1)[0].decode('ascii')

    def array(at, width):
        c.require(12 <= at and at+12 <= end, 'Stock native array header bounds exceeded')
        off, count, capacity = struct.unpack_from('<III', data, at)
        c.require(count == capacity, 'Stock native array capacity differs')
        region(off, count, width)
        return off, count

    c.require(name(20, 64) == model and data[12+0x72] == 4 and array(12+0x78, 4)[1] == 0
              and name(12+0xa8, 64).lower() in ('', 'null') and struct.unpack_from('<f', data, 12+0xa4)[0] == 1,
              'Detached static stock CHARACTER identity required')
    root, count = u32(12+0x48), u32(12+0x4c)
    c.require(count == 2, 'One stock neck mesh required')
    pending = [(root, None)]; seen = set(); result = {}; root_record = None
    while pending:
        off, parent = pending.pop(0)
        c.require(off not in seen, 'Stock native cycle/shared child')
        seen.add(off); at = region(off, 1, 0x70); node = name(at+0x20, 32)
        flags = u32(at+0x6c)
        c.require((parent is None and node == model and flags == 1)
                  or (parent == model and node == model+'g' and flags == 33), 'Unexpected stock neck tree')
        child_off, child_count = array(at+0x48, 4)
        c.require(child_count == (1 if parent is None else 0), 'Nested/missing stock neck nodes')
        pending.extend((u32(region(child_off+4*i, 1, 4)), node) for i in range(child_count))
        key_off, key_count = array(at+0x54, 12); value_off, value_count = array(at+0x60, 4)
        types = set(); controllers = []
        allowed = {8: [0, 0, 0], 20: [0, 0, 0, 1], 36: [1], 100: [0, 0, 0], 128: [1]}
        for i in range(key_count):
            kind, rows, key, value, columns, _ = struct.unpack_from('<ihhhbb', data, region(key_off+12*i, 1, 12))
            c.require(kind in allowed and kind not in types and rows == 1 and columns == len(allowed[kind])
                      and 0 <= key < value_count and 0 <= value and value+columns <= value_count,
                      'Unsupported stock neck static controller')
            types.add(kind); time = struct.unpack_from('<f', data, region(value_off+4*key, 1, 4))[0]
            values = np.asarray(struct.unpack_from('<'+'f'*columns, data, region(value_off+4*value, columns, 4)))
            if kind == 20 and values[-1] == -1:
                values = -values
            c.require(time == 0 and np.array_equal(values, allowed[kind]), 'Nonidentity stock neck controller')
            controllers.append({'type': kind, 'values': values.tolist()})
        layout = {'nodeAbsoluteOffset': at, 'name': node, 'parentFromChildTree': parent,
                  'flags': flags, 'controllers': controllers, 'rawOffset': raw_offset, 'rawSize': raw_size}
        if parent is None:
            root_record = layout
            continue
        region(off, 1, 0x270)
        face_off, face_count = array(at+0x78, 32)
        n, uv_count = struct.unpack_from('<HH', data, at+0x230)
        c.require(n > 0 and face_count > 0 and uv_count == 1, 'Nonempty one-UV stock neck required')
        decoded = {}; offsets = {}
        for key, field, width, dtype in [('position', 0x22c, 3, '<f4'), ('uv', 0x234, 2, '<f4'),
                ('normal', 0x244, 3, '<f4'), ('color', 0x248, 1, '<u4'),
                ('tangent', 0x258, 3, '<f4'), ('sign', 0x260, 1, '<f4')]:
            ptr = u32(at+field); offsets[key] = ptr
            if ptr == 0xffffffff:
                c.require(key in ('color', 'tangent', 'sign'), 'Missing native stock '+key)
                continue
            c.require(ptr+n*width*4 <= raw_size, 'Stock native raw array bounds exceeded')
            value = np.frombuffer(data, dtype, n*width, end+ptr).reshape(n, width).copy()
            c.require(np.isfinite(value).all(), 'Nonfinite stock native '+key)
            decoded[key] = value
        c.require(('tangent' in decoded) == ('sign' in decoded), 'Incomplete stock native tangent pair')
        if 'sign' in decoded:
            c.require(np.isin(decoded['sign'], [-1, 1]).all(), 'Invalid stock tangent signs')
        if 'color' in decoded:
            c.require((decoded['color'] == 0xffffffff).all(), 'Non-white stock vertex colors unsupported')
        c.require((np.linalg.norm(decoded['normal'], axis=1) > 0).all(), 'Zero native stock normals')
        faces = np.ndarray((face_count, 3), dtype='<u2', buffer=data, offset=12+face_off+26, strides=(32, 2)).copy()
        c.require(faces.max() < n, 'Stock native index outside literal arrays')
        slots = [name(at+0xe8+64*i, 64) for i in range(4)]
        c.require(slots == [model, '', '', ''] and u32(at+0xdc) == 1, 'Stock neck bitmap/render inventory differs')
        decoded['faces'] = faces
        decoded['layout'] = {**layout, 'vertices': n, 'triangles': face_count, 'attributeOffsets': offsets,
                             'faceOffset': face_off, 'textureSlots': slots,
                             'diffuse': list(struct.unpack_from('<fff', data, at+0xac)),
                             'ambient': list(struct.unpack_from('<fff', data, at+0xb8)),
                             'specular': list(struct.unpack_from('<fff', data, at+0xc4)),
                             'shininess': struct.unpack_from('<f', data, at+0xd0)[0]}
        c.require(decoded['layout']['diffuse'] == [1, 1, 1], 'Nonidentity stock diffuse factor needs explicit policy')
        result[node] = decoded
    c.require(len(seen) == 2 and set(result) == {model+'g'}, 'Incomplete stock native neck tree')
    return result, root_record


def native_arrays(native):
    result = {key: np.asarray(native[key]) for key in (*KEYS, 'color') if key in native}
    p = result['position']; n = result['normal']; uv = result['uv']; f = result['faces']
    c.require(p.ndim == 2 and p.shape[1] == 3 and n.shape == p.shape and uv.shape == (len(p), 2)
              and p.dtype == np.dtype('<f4') and n.dtype == np.dtype('<f4') and uv.dtype == np.dtype('<f4')
              and f.ndim == 2 and f.shape[1] == 3 and f.dtype == np.dtype('<u2') and len(f)
              and f.max() < len(p) and all(np.isfinite(a).all() for a in result.values()),
              'Literal finite native float32 attributes/uint16 indices required')
    c.require(('tangent' in result) == ('sign' in result), 'Incomplete literal native tangent pair')
    if 'tangent' in result:
        c.require(result['tangent'].shape == p.shape and result['sign'].shape == (len(p), 1)
                  and result['tangent'].dtype == np.dtype('<f4') and result['sign'].dtype == np.dtype('<f4')
                  and np.isin(result['sign'], [-1, 1]).all(), 'Exact native tangent/sign arrays required')
    return result


def verify_loop_representation(native, loop_vertices, loop_positions, loop_normals, loop_uv, attributes,
                               maximum_normal_direction_error=.0007):
    """Check actual Blender loop data, not merely arrays given to the importer.

    Custom normals are normalized and quantized by Blender; compare unit
    directions with an explicit representation bound. Literal shader N/T/sign
    point attributes and P/UV/index order must remain byte-exact.
    """
    value = native_arrays(native); vertices = np.asarray(loop_vertices)
    expected_vertices = value['faces'].astype(np.int64).reshape(-1)
    c.require(np.array_equal(vertices, expected_vertices), 'Blender native loop order differs')
    c.require(np.array_equal(loop_positions, value['position'][vertices])
              and np.array_equal(loop_uv, value['uv'][vertices]), 'Blender literal P/UV differ')
    n = value['normal'][vertices].astype(float)
    length = np.linalg.norm(n, axis=1)
    actual = np.asarray(loop_normals, float)
    c.require(actual.shape == n.shape and np.isfinite(actual).all() and (length > 0).all()
              and (np.linalg.norm(actual, axis=1) > 0).all(), 'Finite effective custom loop normals required')
    actual = actual/np.linalg.norm(actual, axis=1)[:, None]; expected = n/length[:, None]
    error = float(np.max(np.abs(actual-expected)))
    c.require(error <= maximum_normal_direction_error, 'Native custom loop normal direction ineffective or exceeds representation bound')
    keys = [key for key in ('normal', 'tangent', 'sign') if key in value]
    c.require(set(attributes) == set(keys) and all(np.array_equal(attributes[key], value[key])
              and digest_array(attributes[key]) == digest_array(value[key]) for key in keys),
              'Literal native shader N/T/sign point attributes changed')
    return {'positionUvCornerOrderExact': True, 'shaderNativeVectorAndSignBytesExact': True,
            'actualCustomLoopNormalDirectionMaximumComponentError': error,
            'explicitBlenderNormalRepresentationBound': maximum_normal_direction_error,
            'nativeNormalMagnitudePreservedInShaderAttributes': True,
            'customLoopNormalsNormalizedOnlyForBlenderRepresentation': True,
            'missingNativeTangentArrays': 'tangent' not in value,
            'blenderRegeneratedTangentsUsed': False}



def input_pin(path, frozen):
    return pin({'path': str(Path(path).resolve()), 'sha256': c.sha(path)}, frozen)


def record_array(path, native):
    value = native_arrays(native)
    np.savez_compressed(path, **value)
    with np.load(path, allow_pickle=False) as reread:
        c.require(set(reread.files) == set(value) and all(np.array_equal(value[k], reread[k])
                  and digest_array(value[k]) == digest_array(reread[k]) for k in value),
                  'Native array serialization changed literal bytes')
    return {'path': str(path), 'sha256': c.sha(path),
            'digests': {k: digest_array(v) for k, v in value.items()},
            'dtypes': {k: str(v.dtype) for k, v in value.items()}, 'missingNativeArrays': [k for k in KEYS if k not in value]}


def palette_measurement(native, data, palette, rows):
    """Per-texel categorical palette lookup precedes byte-space bilinear samples."""
    from audit_target_joint_bands import BARYCENTRIC, sample_pixels, statistics
    from prepare_effective_body_preview import plt_pixels
    from offline_native_material_bridge import palette_rgba
    pixels = plt_pixels(data)
    c.require((pixels[..., 1] == 0).all(), 'Stock skin-only PLT measurement required')
    faces = native['faces']; p = native['position'][faces].astype(float); uv = native['uv'][faces].astype(float)
    area = np.linalg.norm(np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]), axis=1)/2
    c.require((area > 0).all(), 'Nonzero stock neck triangle areas required')
    weight = np.repeat(area/len(BARYCENTRIC), len(BARYCENTRIC))
    sample_uv = np.einsum('bc,tci->tbi', BARYCENTRIC, uv).reshape(-1, 2)
    sample_uv[:, 1] = 1-sample_uv[:, 1]
    sampled_shade = sample_pixels(pixels[..., 0], sample_uv, 33071, 33071)[:, 0]
    local = np.einsum('bc,tci->tbi', BARYCENTRIC, p).reshape(-1, 3)
    rgb = {str(row): sample_pixels(palette_rgba(data, palette, row)[..., :3], sample_uv, 33071, 33071) for row in rows}
    result = {'wholeMeshShade': statistics(sampled_shade, weight),
              'paletteRgbPerTexelBeforeByteSpaceBilinear': {row: statistics(value, weight) for row, value in rgb.items()},
              'oldLookupAfterShadeMaximumAbsoluteRgbDifference': {}}
    for row in rows:
        old = np.stack([np.interp(sampled_shade, np.arange(256), palette[row, :, channel]) for channel in range(3)], axis=1)
        result['oldLookupAfterShadeMaximumAbsoluteRgbDifference'][str(row)] = float(np.abs(old-rgb[str(row)]).max())
    result['localAxialBands'] = []
    for lower, upper in [(-.06, .02), (.02, .06), (.06, .14)]:
        mask = (local[:, 2] >= lower) & (local[:, 2] < upper)
        if mask.any():
            result['localAxialBands'].append({'localZMetres': [lower, upper], 'shade': statistics(sampled_shade[mask], weight[mask]),
                'paletteRgb': {row: statistics(value[mask], weight[mask]) for row, value in rgb.items()}})
    result['limitation'] = 'Four area-weighted barycentric points per native triangle; all faces, not visible chest/neck continuity. Byte-space filtering differs from sRGB texture filtering and engine mips.'
    return result


def cameras(world_points, render):
    points = np.asarray(world_points, float)
    c.require(points.ndim == 2 and points.shape[1] == 3 and np.isfinite(points).all() and len(points), 'Finite camera focus geometry required')
    target = (points.min(0)+points.max(0))/2; aspect = render['width']/render['height']
    rotations = {}; height = 0
    for name in render['views']:
        z = np.asarray(VIEWS[name], float); u = np.cross([0, 0, 1], z); v = np.cross(z, u)
        rotation = np.column_stack([u, v, z]); rotations[name] = rotation
        span = np.ptp((points-target)@rotation[:, :2], axis=0)
        height = max(height, span[1], span[0]/aspect)
    c.require(height > 0, 'Nonempty projected camera extent required')
    result = []
    for name, rotation in rotations.items():
        matrix = np.eye(4); matrix[:3, :3] = rotation; matrix[:3, 3] = target+rotation[:, 2]*3
        result.append({'id': name, 'matrixWorld': matrix.tolist(), 'target': target.tolist(),
                       'orthographicHeightMetres': float(height*render['padding']), 'commonMagnification': True})
    return result


def derived_preview_source(entry, audit, tp, target, space, part, native_path, frozen):
    """Replay a distinct T derivative or explicitly known-failing compiler control.

    The control is never labelled as an original native audit pass. Both paths
    require the independently audited exact child and original compiler/source
    association, and decode their own literal actual N/T/sign arrays.
    """
    from target_native_tangent_descendant import load_parent, KIND, POLICY, THRESHOLD
    from audit_derived_native_tangent import audit_emitted_bytes, KIND_AUDIT
    model = c.model(target, part)
    c.require(audit.get('kind') == KIND_AUDIT and audit.get('schemaVersion') == 1
              and audit.get('part') == part and audit.get('model') == model
              and audit.get('attributeTransportVerified') is True and audit.get('materialTransportVerified') is True
              and audit.get('nativeTangentProjectionIndependentlyReplayed') is True
              and audit.get('allNonTBytesExact') is True and audit.get('originalCompileReceiptRewritten') is False,
              'Completed explicit independently replayed derived-native audit required')
    dp = pin(entry['nativeDerivation'], frozen); derivative = json.loads(dp.read_text(encoding='utf-8'))
    c.verify_binding(derivative, tp, target, space)
    c.require(derivative.get('schemaVersion') == 1 and derivative.get('kind') == KIND
              and derivative.get('policy') == POLICY and type(derivative.get('derivationApplications')) is int
              and derivative['derivationApplications'] == 1 and derivative['part'] == part
              and derivative['model'] == model and derivative.get('originalCompileReceiptRewritten') is False
              and derivative.get('nativeCompilerExecuted') is False
              and audit['nativeDerivationReceipt'] == entry['nativeDerivation'],
              'Exact single T-only derivation/child audit association required')
    config = pin(derivative['configuration'], frozen); cfg = json.loads(config.read_text(encoding='utf-8'))
    context = load_parent(cfg)
    c.require(context['targetPath'] == tp and context['part'] == part and context['space'] == space,
              'Derived original compiler source belongs to another target/part/space')
    for name, h in context['frozenInputs'].items():
        pin({'path': name, 'sha256': h}, frozen)
    for name, h in derivative['frozenInputs'].items():
        pin({'path': name, 'sha256': h}, frozen)
    original = context['nativePath']; child = pin(derivative['nativeModel'], frozen)
    original_pin = {'path': str(original), 'sha256': c.sha(original)}
    c.require(derivative['originalCompiledNative'] == original_pin and audit['originalCompiledNative'] == original_pin
              and derivative['nativeModel'] == audit['nativeModel']
              and audit['nativeModelSha256'] == c.sha(child)
              and Path(audit['stageReceipt']).resolve() == context['stagePath']
              and audit['stageReceiptSha256'] == c.sha(context['stagePath']),
              'Original compiler/child/stage pin relabeled')
    _, _, proof, _ = audit_emitted_bytes(original.read_bytes(), child.read_bytes(), model, context['native'], context['roles'])
    c.require(set(proof) == set(audit['meshes']) and all(audit['meshes'][name]['role'] == row['role']
              and audit['meshes'][name]['nativeLayout'] == row['nativeLayout']
              and audit['meshes'][name]['eligibleVertices'] == row['eligibleVertices'] for name, row in proof.items()),
              'Derived audit ownership/layout/eligibility differs from actual byte replay')
    control = entry['kind'] == 'derivation-compiler-parent-control'
    expected_path = original if control else child
    c.require(native_path == expected_path and entry['nativeModel'] ==
              (derivative['originalCompiledNative'] if control else derivative['nativeModel']),
              'Literal original control or derived native model pin differs')
    failures = {}
    for name, row in context['native'].items():
        n, t = row['normal'].astype(float), row['tangent'].astype(float)
        n = n/np.linalg.norm(n, axis=1)[:, None];dot = np.abs(np.einsum('ij,ij->i', n, t))
        failures[name] = {'role': context['roles'][name], 'originalMaximumAbsUnitNormalDotTangent': float(dot.max()),
                          'originalVerticesBeyondStrictOrthogonality': int((dot >= THRESHOLD).sum())}
    c.require(any(row['originalVerticesBeyondStrictOrthogonality'] > 0 for row in failures.values()),
              'Original known-failing compiler tangent control must have a real preserved failure')
    return {'nativeDerivation': entry['nativeDerivation'], 'passingChildAudit': entry['nativeAudit'],
            'originalCompiledNative': original_pin, 'actualSourceKind': entry['kind'],
            'originalCompilerTangentOrthogonalityKnownFailed': control,
            'originalCompilerPassedNativeTangentAudit': False,
            'postcompileTangentXYZDerived': not control, 'originalCompilerTangentFailures': failures,
            'independentParentChildAllNonTByteReplayPassed': True,
            'ordinaryHQEngineLightingEmulated': False}


def prepare(config_path, output):
    import pose_preview_bridge  # freeze the renderer's actual sampler dependency closure
    from audit_target_native_part import decode, LAYOUT_COMMIT, LAYOUT_PINS
    from prepare_effective_body_preview import plt_pixels, mtr_fields
    from offline_native_material_bridge import palette_rgba
    from PIL import Image
    config_path = Path(config_path).resolve(); cfg = json.loads(config_path.read_text(encoding='utf-8')); controls(cfg)
    frozen = {}; input_pin(config_path, frozen)
    tp = pin(cfg['targetContract'], frozen); target = c.load(tp); validate_identity(target); space = cfg['coordinateSpace']
    for name, h in target['frozenInputs'].items():
        pin({'path': name, 'sha256': h}, frozen)
    inventory_path = pin(cfg['stockInventory'], frozen)
    c.require(target['frozenInputs'].get(str(inventory_path)) == c.sha(inventory_path), 'Stock inventory must belong to this exact target')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    stock_rows = {row['name']: row for row in inventory['resources']}
    c.require(len(stock_rows) == len(inventory['resources']), 'Duplicate installed stock resource names')
    palette_path = pin(cfg['skinPalette'], frozen)
    c.require(target['frozenInputs'].get(str(palette_path)) == c.sha(palette_path)
              and stock_rows.get(palette_path.name, {}).get('sha256') == c.sha(palette_path), 'Installed target skin palette required')
    palette = np.asarray(Image.open(palette_path).convert('RGB'))
    c.require(palette.ndim == 3 and palette.shape[1:] == (256, 3) and len(palette) > 8, 'Actual palette rows 3/8 unavailable')
    native_rows = {}; part_proofs = {}; measurements = {}
    for part, entry in cfg['parts'].items():
        c.require(isinstance(entry['binding'], dict) and set(entry['binding']) == set(c.binding(tp, target, space)), 'Exact part target/rig/space binding required')
        c.verify_binding(entry['binding'], tp, target, space)
        model = c.model(target, part); native_path = pin(entry['nativeModel'], frozen)
        c.require(native_path.name == model+'.mdl', 'Native file does not own declared female part')
        if entry['kind'] == 'installed-stock-neck':
            c.require(stock_rows.get(native_path.name, {}).get('sha256') == c.sha(native_path)
                      and target['frozenInputs'].get(str(native_path)) == c.sha(native_path), 'Stock native identity/hash differs')
            plt_path = pin(entry['plt'], frozen)
            c.require(plt_path.name == model+'.plt' and stock_rows.get(plt_path.name, {}).get('sha256') == c.sha(plt_path)
                      and target['frozenInputs'].get(str(plt_path)) == c.sha(plt_path), 'Stock neck PLT identity/hash differs')
            meshes, root = stock_neck_decode(native_path.read_bytes(), model)
            native_rows[part] = {name: {'native': row, 'role': 'skin', 'plt': plt_path, 'normal': None, 'roughness': None}
                                 for name, row in meshes.items()}
            measurements[part] = palette_measurement(next(iter(meshes.values())), plt_path.read_bytes(), palette, cfg['paletteRows'])
            part_proofs[part] = {'kind': entry['kind'], 'nativeModel': entry['nativeModel'], 'root': root,
                                'materialPolicy': 'Actual stock PLT; literal native normals; white native vertex colors. Neutral roughness .8; no normal map, no synthesized T/sign. Installed shader defaults beyond these extracted inputs are not asserted.'}
        else:
            audit_path = pin(entry['nativeAudit'], frozen); audit = json.loads(audit_path.read_text(encoding='utf-8'))
            c.verify_binding(audit, tp, target, space)
            derivative_proof = None
            if entry['kind'] in ('audited-derived-native-candidate', 'derivation-compiler-parent-control'):
                derivative_proof = derived_preview_source(entry, audit, tp, target, space, part, native_path, frozen)
            else:
                c.require(audit.get('kind') == 'target-native-part-audit' and audit.get('schemaVersion') == 2
                          and audit.get('part') == part and audit.get('model') == model
                          and audit.get('nativeModelSha256') == c.sha(native_path)
                          and audit.get('attributeTransportVerified') is True and audit.get('materialTransportVerified') is True,
                          'Completed native audit for exact declared source/target/part required')
            for name, h in audit['frozenInputs'].items():
                pin({'path': name, 'sha256': h}, frozen)
            c.require(audit['frozenInputs'].get(str(native_path)) == c.sha(native_path), 'Native model absent from audit closure')
            stage_path = pin({'path': audit['stageReceipt'], 'sha256': audit['stageReceiptSha256']}, frozen)
            stage = json.loads(stage_path.read_text(encoding='utf-8')); c.verify_binding(stage, tp, target, space)
            c.require(stage.get('schemaVersion') == 2 and stage.get('kind') == 'target-part-stage' and stage['part'] == part and stage['model'] == model, 'Native stage owner/type differs')
            meshes, root = decode(native_path.read_bytes(), model, set(audit['meshes']))
            roles = {name: row['role'] for name, row in audit['meshes'].items()}
            c.require(set(roles.values()) <= {'skin', 'garment'} and 'skin' in roles.values() and set(stage['materialRoles'].values()) == set(roles.values()), 'Audited explicit skin/cloth roles required')
            if part in c.fixed_garment_parts(target):
                c.require('garment' in roles.values(), 'Garment owner lacks audited cloth mesh')
            else:
                c.require('garment' not in roles.values(), 'Garment belongs to chest/pelvis only')
            native_rows[part] = {}
            for name, row in meshes.items():
                c.require(row['layout'] == audit['meshes'][name]['nativeLayout'], 'Native decoded layout differs from pinned audit')
                role = roles[name]; material = model+('f' if role == 'garment' else '')
                c.require(row['layout']['textureSlots'] == [material, '', '', material], 'Native material binding differs')
                resources = {}
                for resource_name, h in stage['materialResourceHashes'].items():
                    path = pin({'path': str(native_path.parent/resource_name), 'sha256': h}, frozen)
                    c.require(audit['frozenInputs'].get(str(path)) == h, 'Material dependency not independently audited')
                    resources[resource_name] = path
                mtr = resources[material+'.mtr']; textures, params = mtr_fields(mtr.read_text(encoding='ascii'))
                expected_textures = {1: material+'n', 3: material+'r'}
                if role == 'garment':
                    expected_textures[0] = material
                c.require(textures == expected_textures and params == {'roughness': 0.0, 'specularity': .04, 'metallicness': .001},
                          'Unsupported audited native material policy')
                if role == 'skin':
                    color = resources[material+'.plt']
                    c.require((plt_pixels(color.read_bytes())[..., 1] == 0).all(), 'Skin-only native PLT layer required')
                else:
                    color = resources[material+'.tga']
                    rgba = np.asarray(Image.open(color).convert('RGBA'))
                    c.require((rgba[..., 3] == 255).all(), 'Fixed garment must be opaque')
                native_rows[part][name] = {'native': row, 'role': role, 'plt': color if role == 'skin' else None,
                    'color': color if role == 'garment' else None, 'normal': resources[material+'n.tga'],
                    'roughness': resources[material+'r.tga']}
            part_proofs[part] = {'kind': entry['kind'], 'nativeModel': entry['nativeModel'], 'nativeAudit': entry['nativeAudit'],
                                'stage': {'path': str(stage_path), 'sha256': c.sha(stage_path)}, 'root': root,
                                'materialInputBasis': audit.get('materialInputBasis'), 'derivedMaterialProof': audit.get('derivedMaterialProof'),
                                'sourceSha256': stage['sourceSha256'], 'sourceReceiptSha256': stage['sourceReceiptSha256']}
            if derivative_proof is not None:
                part_proofs[part]['explicitNativeTangentDerivationOrControl'] = derivative_proof
    poses = []
    for definition in cfg['poses']:
        if 'clip' not in definition:
            matrices = {part: c.frame(target, c.PART_JOINTS[part], space) for part in cfg['parts']}
            proof = {'kind': 'exact-installed-bind-frames', 'clientEvidence': False}
        else:
            from pose_preview_bridge import pose
            values, proof = pose(inventory_path.parent/'ascii', target['identity']['prefix'], definition['clip'], definition['time'])
            for row in proof['sourceInheritance']:
                path = pin({'path': row['file'], 'sha256': row['sha256']}, frozen)
                c.require(stock_rows.get(path.name, {}).get('asciiSha256') == c.sha(path)
                          and target['frozenInputs'].get(str(path)) == c.sha(path), 'Pose inheritance differs from installed target stock')
            matrices = {part: values[c.PART_JOINTS[part]] for part in cfg['parts']}
        for matrix in matrices.values():
            c.require(matrix.shape == (4, 4) and np.isfinite(matrix).all() and np.allclose(matrix[3], [0, 0, 0, 1])
                      and np.allclose(matrix[:3, :3].T@matrix[:3, :3], np.eye(3), atol=2e-6, rtol=0)
                      and abs(np.linalg.det(matrix[:3, :3])-1) < 2e-6, 'Native display pose must remain proper rigid')
        focus = np.concatenate([row['native']['position']@matrices[part][:3, :3].T+matrices[part][:3, 3]
                  for part in cfg['render']['focusParts'] for row in native_rows[part].values()])
        poses.append({'definition': definition, 'matrices': {part: matrix.tolist() for part, matrix in matrices.items()},
                      'sourceProof': proof, 'cameras': cameras(focus, cfg['render'])})
    output = Path(output).resolve(); c.require(not output.exists(), 'Fresh immutable native preview preparation required')
    output.mkdir(); (output/'arrays').mkdir(); (output/'textures').mkdir(); (output/'helpers').mkdir()
    prepared = {}
    for part, rows in native_rows.items():
        prepared[part] = []
        for name, row in rows.items():
            archive = record_array(output/'arrays'/(name+'.npz'), row['native'])
            colors = {}
            for palette_row in cfg['paletteRows']:
                path = output/'textures'/(name+'-palette'+str(palette_row)+'.png')
                if row['role'] == 'skin':
                    rgba = palette_rgba(row['plt'].read_bytes(), palette, palette_row)
                else:
                    rgba = np.asarray(Image.open(row['color']).convert('RGBA'))
                Image.fromarray(rgba).save(path)
                colors[str(palette_row)] = {'path': str(path), 'sha256': c.sha(path),
                                           'pixelSha256': digest_array(rgba)}
            prepared[part].append({'name': name, 'role': row['role'], 'arrays': archive,
                'layout': row['native']['layout'], 'colors': colors,
                'normal': {'path': str(row['normal']), 'sha256': c.sha(row['normal'])} if row['normal'] else None,
                'roughness': {'path': str(row['roughness']), 'sha256': c.sha(row['roughness'])} if row['roughness'] else None})
    tools = Path(__file__).resolve().parent; helper_paths = {Path(__file__).resolve()}
    helper_paths.update(tools/name for name in ('render_target_native_material_preview.py', 'render_target_pilot_materials_v2.py',
                    'pose_preview_render_settings.py', 'shared_toolchain.py', 'launch_shared_tool.py'))
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and tools in path.parents:
                helper_paths.add(path)
    snapshots = {}
    for path in sorted(helper_paths):
        input_pin(path, frozen); destination = output/'helpers'/path.name
        c.require(not destination.exists(), 'Helper snapshot filename collision')
        shutil.copyfile(path, destination)
        snapshots[str(path)] = {'path': str(destination), 'sha256': c.sha(destination)}
    for path, h in frozen.items():
        c.require(c.sha(path) == h, 'Preview input changed during preparation')
    output_hashes = {str(path): c.sha(path) for path in sorted(output.rglob('*')) if path.is_file()}
    result = {'schemaVersion': 1, 'kind': 'target-offline-native-material-preview-preparation',
        **c.binding(tp, target, space), 'inputConfiguration': {'path': str(config_path), 'sha256': c.sha(config_path)},
        'parts': prepared, 'partProvenance': part_proofs, 'paletteRows': cfg['paletteRows'], 'render': cfg['render'],
        'poses': poses, 'stockNeckMeasurements': measurements, 'frozenInputs': frozen, 'helperSnapshots': snapshots,
        'postcompileTangentXYZDerivedParts': [part for part, row in part_proofs.items() if row['kind'] == 'audited-derived-native-candidate'],
        'knownFailingCompilerTangentControlParts': [part for part, row in part_proofs.items() if row['kind'] == 'derivation-compiler-parent-control'],
        'outputHashes': output_hashes, 'binaryLayoutSourceCommit': LAYOUT_COMMIT,
        'binaryLayoutPins': LAYOUT_PINS, 'nativeDisplayScale': 1, 'statureApplications': 0,
        'nativeCompilerExecuted': False, 'nativeGeometryEdited': False, 'nativeMapsEdited': False,
        'paletteLookupBeforeFiltering': True, 'offlineOnly': True, 'literalClientCapture': False,
        'clientAccepted': False, 'productionAccepted': False}
    path = output/'preparation.json'; save(path, result)
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.config, args.output)
    print(json.dumps({'receipt': str(result), 'sha256': c.sha(result)}))

