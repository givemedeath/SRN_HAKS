"""Read-only source->ASCII->actual native stock-limb shading audit.

Constrained unskinned one-node decoder, based on NwnMdlNodes.h field layout.
It proves attribute/material transport, not visual acceptance or shading cause.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image
from stage_stock_part import arrays, raw_triangles
from stock_limb_contract import ATTACHMENTS


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(data, model):
    require(len(data) >= 12, 'Truncated binary header')
    zero, raw_offset, raw_size = struct.unpack_from('<III', data)
    require(not zero and 12 + raw_offset + raw_size == len(data), 'Complete expected binary header required')
    pattern = (model + 'p').encode() + b'\0'
    name = data.find(pattern)
    require(name >= 32 and data.find(pattern, name + 1) == -1, 'Expected unique isolated mesh node')
    node = name - 32
    require(node + 0x264 <= 12 + raw_offset, 'Mesh structure exceeds model section')
    require(struct.unpack_from('<I', data, node + 0x6c)[0] == 33, 'Expected unskinned trimesh flag33')
    face_offset, count, capacity = struct.unpack_from('<III', data, node + 0x78)
    vertices, texture_count = struct.unpack_from('<HH', data, node + 0x230)
    require(vertices and count and count == capacity and texture_count == 1, 'Expected packed one-UV triangle mesh')
    require(face_offset + count * 32 <= raw_offset, 'Face records exceed model section')
    raw_start = 12 + raw_offset
    offsets = {key: struct.unpack_from('<I', data, node + field)[0] for key, field in
               [('position', 0x22c), ('uv', 0x234), ('normal', 0x244), ('tangent', 0x258), ('sign', 0x260)]}

    def floats(key, width):
        require(offsets[key] != 0xffffffff, 'Missing actual native ' + key + ' array')
        require(offsets[key] + vertices * width * 4 <= raw_size, 'Native accessor exceeds raw section: ' + key)
        result = np.frombuffer(data, '<f4', vertices * width, raw_start + offsets[key]).reshape(-1, width)
        require(np.isfinite(result).all(), 'Nonfinite native ' + key)
        return result

    result = {key: floats(key, width) for key, width in [('position', 3), ('uv', 2), ('normal', 3), ('tangent', 3), ('sign', 1)]}
    faces = np.ndarray((count, 3), dtype='<u2', buffer=data, offset=12 + face_offset + 26, strides=(32, 2))
    require(faces.max() < vertices, 'Native face index outside native arrays')
    require(np.isin(result['sign'], [-1., 1.]).all(), 'Invalid native tangent handedness')
    result['faces'] = faces
    result['layout'] = {'nodeAbsoluteOffset': node, 'vertices': vertices, 'triangles': count,
                        'rawOffset': raw_offset, 'rawSize': raw_size, 'attributeOffsets': offsets,
                        'shadowFlag': struct.unpack_from('<I', data, node + 0xd4)[0]}
    return result


def maximum_errors(actual, expected):
    require(actual.shape == expected.shape, 'Ordered source/native shape mismatch')
    return float(np.abs(actual.astype(float) - expected).max())


def float32_ulp_distance(actual, expected):
    def ordered(value):
        bits=np.asarray(value,dtype=np.float32).view(np.uint32).astype(np.int64)
        return np.where(bits & 0x80000000, 0x80000000-(bits & 0x7fffffff), 0x80000000+bits)
    return np.abs(ordered(actual)-ordered(expected))


def validate_transport(source, ascii_corners, native_corners, native_uv_max_ulps=0):
    require(native_uv_max_ulps in (0,1), 'UV rounding policy must be exact or explicitly one FLOAT32 ULP')
    ascii_errors = {key: maximum_errors(ascii_corners[key], source[key]) for key in source}
    binary_errors = {key: maximum_errors(native_corners[key], source[key]) for key in source}
    float32_exact = {key: bool(np.array_equal(native_corners[key], source[key].astype(np.float32))) for key in source}
    require(all(value == 0 for value in ascii_errors.values()), 'ASCII ordered corners differ from selected source')
    require(float32_exact['position'] and float32_exact['normal'], 'Native ordered P/N differ from float32 selected source')
    require(float32_ulp_distance(native_corners['uv'],source['uv']).max()<=native_uv_max_ulps,
            'Native ordered UV differs beyond explicit float32 rounding policy')
    return ascii_errors, binary_errors, float32_exact


def validate_target(config):
    part=config.get('part');model=config.get('model')
    require(part in ATTACHMENTS and model == 'pmh0_' + part + '001'
            and config.get('joint') == ATTACHMENTS[part],
            'Explicit Human limb model/part/stock joint association required')
    return part,model


def audit(converted, config_path, output, foot_material_patch_sha256=None, effective_native_preparation=None, native_uv_max_ulps=0):
    require(not output.exists(), 'Fresh audit output required')
    config = json.loads(config_path.read_text())
    part,model = validate_target(config)
    require(config.get('normalStrength', 1) == 1 and config.get('skinLayer', 0) == 0, 'Unchanged skin-only material policy required')
    paths = {key: Path(config[key]) for key in ['source', 'color', 'normal']}
    for key, path in paths.items():
        require(sha(path) == config['expectedInputHashes'][key], 'Selected source/map hash changed: ' + key)
    ascii_path = converted / 'ascii' / (model + '.mdl')
    binary_path = converted / 'resources' / (model + '.mdl')
    receipt_path = converted / 'native-compile.json'
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('complete') is True and len(receipt.get('models', [])) == 1, 'Single-limb completed native receipt required')
    row = receipt['models'][0]
    require(row['name'] == model + '.mdl' and row['sourceSha256'] == sha(ascii_path) and
            row['binarySha256'] == sha(binary_path) and row['bytes'] == binary_path.stat().st_size,
            'Actual native compilation association changed')
    text = ascii_path.read_text(); native = decode(binary_path.read_bytes(), model)
    ap, an, au = [np.asarray(arrays(text, key)) for key in ['verts', 'normals', 'tverts']]
    af = np.asarray(arrays(text, 'faces'), dtype=int)
    require(len(af) == native['layout']['triangles'], 'ASCII/native triangle count mismatch')
    source_p, source_uv, source_n, _ = raw_triangles(paths['source'], paths['color'], paths['normal'])
    ascii_corners = {'position': ap[af[:, :3]], 'normal': an[af[:, :3]], 'uv': au[af[:, 4:7], :2]}
    source = {'position': source_p, 'normal': source_n, 'uv': source_uv}
    native_corners = {key: native[key][native['faces']] for key in source}
    ascii_errors, binary_errors, float32_exact = validate_transport(source, ascii_corners, native_corners,native_uv_max_ulps)
    uv_ulps=float32_ulp_distance(native_corners['uv'],source['uv'])
    n = native['normal'].astype(float); t = native['tangent'].astype(float)
    nl = np.linalg.norm(n, axis=1); tl = np.linalg.norm(t, axis=1)
    require(nl.min() > .5 and np.allclose(tl, 1, atol=2e-5), 'Invalid native normal/tangent magnitude')
    orthogonality = np.abs(np.einsum('ij,ij->i', n / nl[:, None], t))
    require(orthogonality.max() < 2e-5, 'Native tangent not orthogonal to authored normal')
    uv = native_corners['uv']; p = native_corners['position']
    d1, d2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    determinant = d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]
    valid = np.abs(determinant) > 1e-12
    dp1, dp2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    tangent_face = (dp1[valid] * d2[valid, 1, None] - dp2[valid] * d1[valid, 1, None]) / determinant[valid, None]
    bitangent_face = (dp2[valid] * d1[valid, 0, None] - dp1[valid] * d2[valid, 0, None]) / determinant[valid, None]
    nn = native['normal'][native['faces']][valid].astype(float)
    nt = native['tangent'][native['faces']][valid].astype(float)
    ns = native['sign'][native['faces']][valid]
    bitangent = np.cross(nn, nt) * ns
    def cosine_stats(a, b):
        values = np.einsum('tci,tci->tc', a, b[:, None, :]) / (np.linalg.norm(a, axis=2) * np.linalg.norm(b, axis=1)[:, None])
        return {'minimum': float(values.min()), 'median': float(np.median(values)), 'p01': float(np.percentile(values, 1)),
                'negativeCorners': int((values < 0).sum()), 'corners': int(values.size)}
    tangent_summary = {'minimumLength': float(tl.min()), 'maximumLength': float(tl.max()),
                       'maxAbsDotAuthoredNormal': float(orthogonality.max()),
                       'negativeHandednessVertices': int((native['sign'] == -1).sum()),
                       'positiveHandednessVertices': int((native['sign'] == 1).sum()),
                       'nondegenerateUvTriangles': int(valid.sum()), 'degenerateUvTriangles': int((~valid).sum()),
                       'faceUvDirectionCosinesDiagnosticOnly': {'tangent': cosine_stats(nt, tangent_face),
                                                                 'bitangent': cosine_stats(bitangent, bitangent_face)}}
    mtr_path = converted / 'resources' / (model + '.mtr')
    plt_path = converted / 'resources' / (model + '.plt')
    normal_path = converted / 'resources' / (model + 'n.tga')
    mtr = mtr_path.read_text()
    require(re.search(r'(?mi)^\s*renderhint\s+NormalTangents\s*$', mtr), 'Actual MTR lacks NormalTangents')
    require(re.search(r'(?mi)^\s*texture1\s+' + re.escape(model + 'n') + r'\s*$', mtr), 'MTR normal resref differs')
    for path in [mtr_path, plt_path, normal_path]:
        require(receipt['materialResourceHashes'].get(path.name) == sha(path), 'Compile-time material dependency not exact: ' + path.name)
    plt = plt_path.read_bytes()
    require(plt[:8] == b'PLT V1  ' and struct.unpack_from('<II', plt, 16) == (2048, 2048) and
            len(plt) == 24 + 2048 * 2048 * 2, 'Unexpected PLT structure')
    pixels = np.frombuffer(plt[24:], np.uint8).reshape(2048, 2048, 2)[::-1]
    color = np.asarray(Image.open(paths['color']).convert('RGB'))
    intensity = np.clip(color.astype(float) @ [.2126, .7152, .0722], 0, 255).astype(np.uint8)
    normal_exact = np.array_equal(np.asarray(Image.open(normal_path).convert('RGB')),
                                  np.asarray(Image.open(paths['normal']).convert('RGB')))
    source_intensity_exact=np.array_equal(pixels[:,:,0],intensity)
    material_descendant=None
    extra_files=[]
    if effective_native_preparation:
        require(not foot_material_patch_sha256, 'Ambiguous effective native material policy')
        from prepare_effective_native_unit import validate_preparation
        effective_config,preparation,operation=validate_preparation(effective_native_preparation,converted,require_native=True)
        require(effective_config==config, 'Effective native config differs from audited selected source')
        # The explicit AO/roughness descendant is frozen and independently
        # material-audited before compilation. Do not pretend its PLT is raw RGB
        # luminance or a single integer shade offset, and never rebake it here.
        expected_intensity=pixels[:,:,0]
        material_descendant={'kind':'compiled-effective-ao-roughness-materials',
            'preparationSha256':sha(effective_native_preparation),
            'materialOperationSha256':preparation['effectiveMaterialOperationSha256'],
            'runtimeManifestSha256':preparation['runtimeManifestSha256'],
            'frozenResourceHashesExact':True,'rebakedHere':False,'originalStageModified':False}
        require(re.search(r'(?mi)^\s*parameter\s+float\s+Roughness\s+0(?:\.0*)?\s*$',mtr)
                and re.search(r'(?mi)^\s*texture3\s+'+re.escape(model+'r')+r'\s*$',mtr),
                'Effective roughness transport missing/masked')
        rough=converted/'resources'/(model+'r.tga')
        require(receipt['materialResourceHashes'].get(rough.name)==sha(rough), 'Effective roughness absent during compilation')
        require(not re.search(r'(?mi)^\s*texture0\s+',mtr), 'Skin diffuse PLT overridden')
        extra_files=[Path(effective_native_preparation),Path(preparation['effectiveMaterialOperation']),
            Path(preparation['runtimeManifest']),rough,Path(__file__).with_name('prepare_effective_native_unit.py')]
    elif foot_material_patch_sha256:
        from foot_material_contract import validate_foot_material_stage
        _,stage_receipt,material_descendant=validate_foot_material_stage(converted.parents[1],foot_material_patch_sha256,allow_native=True)
        require(stage_receipt['configuration']==config,'Native foot material operation config differs')
        offset=material_descendant['shadeOffset']
        expected_intensity=np.clip(intensity.astype(np.int16)+offset,0,255).astype(np.uint8)
    else:
        require(not (converted.parents[1]/'foot-material-patch.json').exists(),'Foot shade native audit requires explicit material operation pin')
        expected_intensity=intensity
    require(normal_exact and np.array_equal(pixels[:, :, 0], expected_intensity) and not pixels[:, :, 1].any(),
            'Native palette/normal pixels differ from source material policy')
    files = [config_path, receipt_path, ascii_path, binary_path, mtr_path, plt_path, normal_path,
             *paths.values(), Path(__file__)]
    files+=extra_files
    result = {'pass': True, 'readOnly': True, 'model': model, 'part': part,
              'helperDependencyHashes': {'stock_limb_contract.py':sha(Path(__file__).with_name('stock_limb_contract.py'))},
              'sourceHashes': {str(path.resolve()): sha(path) for path in files},
              'nativeMesh': native['layout'], 'sourceToAsciiOrderedCornerMaximumErrors': ascii_errors,
              'sourceToNativeOrderedCornerMaximumErrors': binary_errors, 'nativeCornersExactSourceFloat32': float32_exact,
              'nativeUvFloat32Rounding':{'explicitMaximumAllowedUlps':native_uv_max_ulps,
                  'observedMaximumUlps':int(uv_ulps.max()),'nonexactValues':int((uv_ulps>0).sum()),
                  'maximumAbsoluteErrorVsRoundedSource':maximum_errors(native_corners['uv'],source['uv'].astype(np.float32)),
                  'geometryOrAsciiChanged':False},
              'actualNativeTangentArrays': tangent_summary,
              'material': {'mtr': mtr, 'compileTimeDependenciesExact': True, 'normalTgaPixelsExact': True,
                           'pltExpectedLuminancePixelsExact': bool(source_intensity_exact),
                           'pltExpectedDeclaredMaterialPixelsExact':True,
                           'explicitFootMaterialDescendant':material_descendant,'pltSkinLayer0Everywhere': True},
              'geometryModified': False, 'nativeCompilerExecuted': False, 'clientControlled': False,
              'binaryLayoutPrimarySource': 'https://github.com/niv/nwn-tools/blob/master/_NwnLib/NwnMdlNodes.h',
              'limitations': 'Constrained one-trimesh decoder. Exact transport and finite orthogonal tangent/sign arrays do not prove client shading or visual acceptance. Per-face differential comparisons are diagnostic; compiler vertex averaging and UV tangencies may differ.'}
    output.mkdir(parents=True)
    shutil.copy2(Path(__file__), output / Path(__file__).name)
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--converted', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--foot-material-patch-sha256',help='Explicit pinned foot PLT shade trial when audited native inputs use it.')
    parser.add_argument('--effective-native-preparation',type=Path,
                        help='Explicit frozen AO/roughness descendant compiled with all current dependencies; old stages remain immutable.')
    parser.add_argument('--native-uv-max-ulps',type=int,choices=(0,1),default=0,
                        help='Explicit measured native UV parser rounding policy; P/N remain FLOAT32-exact, ASCII remains exact. Default requires exact UV.')
    args = parser.parse_args()
    result = audit(args.converted, args.config, args.output,args.foot_material_patch_sha256,args.effective_native_preparation,args.native_uv_max_ulps)
    print(json.dumps({'pass': result['pass'], 'model': result['model'],
                      'nativeCornersExactSourceFloat32': result['nativeCornersExactSourceFloat32'],
                      'tangents': result['actualNativeTangentArrays']}))


if __name__ == '__main__':
    main()
