"""Explicit selected working leaves to diagnostic runtime stages.

Old canonical/Human/neutral-cap receipt guards remain unchanged. Current
authoritative f64 positions receive 10/7 once; authored basis/history stay literal.
"""
import argparse
from io import BytesIO
import importlib
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

import numpy as np
from PIL import Image

import target_contract as tc
from place_purposebuilt_pelvis import read_glb, raw_corners
from stage_stock_part import geometry, write_ascii
from target_part_pipeline import verify_source_receipt
from target_part_stage import material_inputs

CONFIG_KIND = 'target-working-leaf-runtime-stage-config'
STAGE_KIND = 'target-working-leaf-runtime-stage'
COMPOSITION_KIND = 'target-working-leaf-runtime-composition'
SCALE = 10 / 7
CAP_ROLE = 'diagnostic-skin-cap'
ROLES = {'skin', 'garment', CAP_ROLE}
FLAGS = ('nativeAccepted', 'materialAccepted', 'clientAccepted', 'productionAccepted')
# Fixed part/type/operation enum, without historic back20 or neutral pelvis aliases.
SOURCES = {
    'chest': (2, 'target-part-geometry', 'face-repair', None),
    'forel': (2, 'target-part-geometry', 'fit', None),
    'forer': (2, 'target-part-geometry', 'mirror', None),
    'handr': (2, 'target-part-geometry', 'uniform-scale-selected-working-child', None),
    'handl': (2, 'target-part-geometry', 'mirror', None),
    'footl': (2, 'target-part-geometry', 'uniform-scale-original-working-foot', 'verify_diagnostic_foot_uniform120'),
    'footr': (2, 'target-part-geometry', 'mirror', None),
    'bicepl': (1, 'target-part-diagnostic-upper-arm-girth110', 'constant-frozen-shoulder-elbow-axis-transverse-scale', 'diagnostic_upper_arm_girth'),
    'bicepr': (1, 'target-part-diagnostic-selected-working-opposite-mirror', 'single-frozen-opposite-frame-reflection-of-explicit-typed-parent', 'diagnostic_selected_working_opposite'),
    'legl': (1, 'target-part-diagnostic-thigh-one-sided-proximal-backward-Y', 'replace-window-from-radial85-world-Z-ramp-backward-Y', 'diagnostic_thigh_proximal_one_sided'),
    'legr': (1, 'target-part-diagnostic-selected-working-opposite-mirror', 'single-frozen-opposite-frame-reflection-of-explicit-typed-parent', 'diagnostic_selected_working_opposite'),
    'shinl': (1, 'target-part-diagnostic-shin-girth90-after85', 'constant-frozen-knee-ankle-axis-additional-transverse-scale90', 'diagnostic_shin_girth90'),
    'shinr': (1, 'target-part-diagnostic-shin-girth90-after85-opposite-mirror', 'single-frozen-opposite-frame-shin90-reflection', 'diagnostic_shin_girth90_opposite'),
    'pelvis': (1, 'target-part-diagnostic-pelvis-skin-cap-material', 'append-exact-C3-RGBA-ORM-skin-cap-material-only', 'diagnostic_pelvis_cap_skin_material'),
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': tc.sha(path)}


def pinned(item, inputs):
    tc.require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'Exact path/hash pin required')
    path = Path(item['path']).resolve()
    tc.require(tc.sha(path) == item['sha256'], 'Frozen input changed: ' + str(path))
    tc.require(str(path) not in inputs or inputs[str(path)] == item['sha256'], 'Conflicting pin')
    inputs[str(path)] = item['sha256']
    return path


def deny_acceptance(row, required=False):
    tc.require(all(row.get(key, None if required else False) is False for key in FLAGS), 'Diagnostic acceptance flags must stay false')


def executor(config, inputs, path=None):
    actual = Path(__file__ if path is None else path).resolve()
    expected = config.get('expectedExecutor')
    tc.require(isinstance(expected, dict) and Path(expected.get('path', '')).resolve() == actual,
               'Expected executor must resolve to executing helper')
    pinned(expected, inputs)
    return actual


def validate_config(config, target):
    tc.require(config.get('schemaVersion') == 1 and config.get('kind') == CONFIG_KIND and
               config.get('diagnosticOnly') is True, 'Explicit new diagnostic stage config required')
    tc.require(config.get('part') in SOURCES and config.get('coordinateSpaceFrom') == 'working' and
               config.get('coordinateSpaceTo') == 'runtime', 'Finite selected body owner and working->runtime only')
    tc.require(target['identity']['prefix'] == 'pmg0' and target['identity']['gender'] == 'male' and
               target['identity']['phenotype'] == 0 and target['identity']['raceId'] == 2 and
               target['rig']['runtimeScale'] == SCALE, 'Declared Troll male target with exact10/7 stature required')
    tc.require(config.get('runtimeScale') == {'numerator': 10, 'denominator': 7} and
               config.get('statureApplicationsBefore') == 0 and config.get('statureApplicationsAfter') == 1,
               'Only one stature application0->1; no fitting/mirror/display transforms')
    tc.require(config.get('aoStrength') == 0, 'Selected untreated AO0 only')
    deny_acceptance(config)


def validate_source_type(receipt, part):
    tc.require(part in SOURCES, 'Undeclared selected leaf')
    schema, kind, op, _ = SOURCES[part]
    tc.require((receipt.get('schemaVersion'), receipt.get('kind'), receipt.get('operation')) == (schema, kind, op),
               'Exact selected leaf type/operation required; no aliases')
    tc.require(receipt.get('part') == part and receipt.get('joint') == tc.PART_JOINTS[part] and
               receipt.get('statureApplications') == 0, 'Exact working owner/joint; runtime parents rejected')
    deny_acceptance(receipt)


def validate_original_right_foot(receipt, parent):
    tc.require(receipt.get('sourcePart') == 'footl' and
               receipt.get('sourceReceiptSha256') == 'a7d016161b0f040c33b1e3d8307dadf6d9470845f8580f023bc2ceda06061bd6' and
               parent.get('kind') == 'target-part-geometry' and parent.get('operation') == 'fit' and
               parent.get('part') == 'footl' and parent.get('statureApplications') == 0,
               'RIGHT foot is the explicit original LEFT-fit mirror baseline; no unselectedfoot120 alias')


def associated_pin(value, wanted):
    """Exact ref or finite known receipt-string/hash pairs, never kind alone."""
    if isinstance(value, dict):
        if value == wanted:
            return True
        for name, digest in [('receipt', 'receiptSha256'), ('sourceReceipt', 'sourceReceiptSha256'),
                             ('geometryReceipt', 'geometryReceiptSha256'), ('selectedGeometryReceipt', 'selectedGeometryReceiptSha256')]:
            if isinstance(value.get(name), str) and value.get(digest) == wanted['sha256'] and Path(value[name]).resolve() == Path(wanted['path']).resolve():
                return True
        return any(associated_pin(v, wanted) for v in value.values())
    if isinstance(value, list):
        return any(associated_pin(v, wanted) for v in value)
    return False


def validate_selection_authority(row, kind, source_pin):
    tc.require(row.get('kind') == kind and associated_pin(row, source_pin),
               'Working selection authority must identify exact source receipt/hash, not merely share its kind')


def validate_evidence(item, source_path, candidate, inputs):
    path = pinned({'path': item['path'], 'sha256': item['sha256']}, inputs)
    row = read(path)
    tc.require(row.get('kind') == item['kind'] and row.get('passed') is True, 'Pinned successful actual leaf proof required')
    wanted = [ref(source_path), ref(candidate)]
    tc.require(all(associated_pin(row, pin) for pin in wanted), 'Proof must associate exact source receipt and candidate')
    return row


def verify_leaf(config, target_path, target, inputs):
    part = config['part']
    path = pinned(config['sourceLeaf'], inputs)
    receipt = read(path)
    validate_source_type(receipt, part)
    tc.verify_binding(receipt, target_path, target, 'working')
    tc.require(receipt['model'] == tc.model(target, part), 'Declared target model owner differs')
    candidate = pinned({'path': receipt['candidate'], 'sha256': receipt['candidateSha256']}, inputs)
    tc.require(np.array_equal(receipt['attachmentWorld'], tc.frame(target, tc.PART_JOINTS[part], 'working')),
               'Frozen working attachment required')
    if 'candidateToAttachmentLocal' in receipt:
        tc.require(np.array_equal(receipt['candidateToAttachmentLocal'], np.eye(4)), 'No extra candidate placement')
    module_name = SOURCES[part][3]
    if module_name:
        module = importlib.import_module(module_name)
        tc.require(Path(config['sourceVerifier']['path']).resolve() == Path(module.__file__).resolve(),
                   'Exact typed public source verifier required')
        pinned(config['sourceVerifier'], inputs)
        result = module.verify_receipt(path, target_path, target, space='working')
        # The existing foot API returns an independent proof and portable row pair.
        if isinstance(result, tuple):
            proof, row = result
            tc.require(Path(row['receipt']).resolve() == path and row['receiptSha256'] == tc.sha(path) and
                       Path(row['candidate']).resolve() == candidate and row['candidateSha256'] == tc.sha(candidate),
                       'Foot verifier returned another source')
            for p, h in proof['frozenInputs'].items():
                pinned({'path': p, 'sha256': h}, inputs)
        else:
            tc.require(result['receipt'] == receipt and Path(result['candidate']).resolve() == candidate,
                       'Typed verifier returned another source')
            for p, h in result['inputs'].items():
                pinned({'path': p, 'sha256': h}, inputs)
    else:
        expected = Path(__file__).with_name('target_part_pipeline.py').resolve()
        tc.require(Path(config['sourceVerifier']['path']).resolve() == expected, 'Exact canonical source metadata verifier')
        pinned(config['sourceVerifier'], inputs)
        verify_source_receipt(candidate, path, target_path, target, part, 'working')
        for p, h in receipt['frozenInputs'].items():
            pinned({'path': p, 'sha256': h}, inputs)
        if part == 'footr':
            original = pinned({'path': receipt['sourceReceipt'], 'sha256': receipt['sourceReceiptSha256']}, inputs)
            parent = read(original)
            tc.verify_binding(parent, target_path, target, 'working')
            validate_original_right_foot(receipt, parent)
    if part in ('handl', 'handr'):
        tc.require(config.get('actualLeafEvidence') is not None, 'Hand operation needs exact independent proof beyond canonical header')
    if config.get('actualLeafEvidence') is not None:
        validate_evidence(config['actualLeafEvidence'], path, candidate, inputs)
    authority = pinned(config['workingSelectionAuthority'], inputs)
    validate_selection_authority(read(authority), config['workingSelectionAuthorityKind'], ref(path))
    return receipt, candidate


def load_archive(item, inputs):
    path = pinned(item, inputs)
    with np.load(path, allow_pickle=False) as data:
        tc.require(all(not data[k].dtype.hasobject for k in data.files), 'No object archive arrays')
        return {k: data[k].copy() for k in data.files}


def runtime_archive(archive, position_key, normal_key, tangent_key, applications=0):
    """Scale current f64 P only; history and authored basis stay byte literal."""
    tc.require(applications == 0 and not any(k.startswith('runtime') for k in archive),
               'Working archive only; stature must not be applied twice')
    p, n, t = [archive[k] for k in (position_key, normal_key, tangent_key)]
    tc.require(p.dtype == np.dtype('float64') and n.dtype == p.dtype and t.dtype == p.dtype and
               p.ndim == 3 and p.shape[1:] == (3, 3) and n.shape == p.shape and
               t.shape == (*p.shape[:2], 4) and len(p) > 0, 'Authoritative current f64 triangle P/N/T required')
    tc.require(all(np.isfinite(a).all() for a in (p, n, t)) and
               (np.linalg.norm(n, axis=2) > 0).all() and (np.linalg.norm(t[..., :3], axis=2) > 0).all() and
               np.isin(t[..., 3], [-1, 1]).all(), 'Finite nonzero active authored basis and literal tangent W')
    out = {k: v.copy() for k, v in archive.items()}
    out['runtimeWorkingPositions'] = p.copy()
    out['runtimeStatureFraction'] = np.asarray([10, 7], dtype=np.int64)
    out[position_key] = p * SCALE
    tc.require(np.isfinite(out[position_key]).all(), 'Runtime overflow')
    tc.require(all(out[k].dtype == v.dtype and out[k].shape == v.shape and out[k].tobytes() == v.tobytes()
                   for k, v in archive.items() if k != position_key), 'Runtime changed authored basis/history')
    return out


def archive_slots(receipt, inputs):
    if receipt['part'] == 'pelvis':
        spec = [('body', 'bodyFloat64Archive', 'positions', 'normals', 'tangents', 'uvNative'),
                ('caps', 'generatedCapFloat64Archive', 'derivedWorkingPositions', 'derivedWorkingNormals',
                 'derivedWorkingTangents', 'TEXCOORD_0')]
    else:
        spec = [('body', 'nativeCornerArchive', 'positions', 'normals', 'tangents', 'uvNative')]
    result = []
    for slot, field, pk, nk, tk, uk in spec:
        archive = load_archive(receipt[field], inputs)
        runtime = runtime_archive(archive, pk, nk, tk)
        uv = archive[uk]
        tc.require(uv.shape == (*archive[pk].shape[:2], 2) and np.isfinite(uv).all(), 'Ordered archive UV shape/values')
        if slot == 'caps':
            uv = uv.astype(np.float64).copy()
            uv[..., 1] = 1 - uv[..., 1]
        result.append({'slot': slot, 'source': receipt[field], 'arrays': runtime,
                       'keys': {'P': pk, 'N': nk, 'T': tk, 'UV': uk},
                       'current': {'position': runtime[pk], 'normal': runtime[nk], 'tangents': runtime[tk], 'uv': uv},
                       'primitiveIds': archive['primitiveIds']})
    return result


def merge_corners(slots, primitives, roles, part):
    tc.require(set(roles) == set(range(len(primitives))) and set(roles.values()) <= ROLES and 'skin' in roles.values(),
               'Every active primitive needs one declared role')
    tc.require(part == 'pelvis' or set(roles.values()) == {'skin'}, 'Caps/garment belong only to pelvis')
    if part == 'pelvis':
        tc.require(len(primitives) == 6 and roles == {0: 'skin', 1: CAP_ROLE, 2: CAP_ROLE, 3: 'garment', 4: 'skin', 5: 'garment'},
                   'Exact six actual skin-cap/opaque-garment owners required')
    rows = {k: [] for k in ('position', 'normal', 'tangents', 'uv')}
    mapping = {k: [] for k in ('primitiveIds', 'primitiveFaceIds', 'archiveSlotIds', 'archiveRowIds')}
    owners = []
    used = [set() for _ in slots]
    for primitive, record in enumerate(primitives):
        found = [(j, np.flatnonzero(np.asarray(s['primitiveIds']) == primitive)) for j, s in enumerate(slots)]
        found = [(j, ids) for j, ids in found if len(ids)]
        tc.require(len(found) == 1, 'One authoritative archive owns each primitive')
        j, ids = found[0]
        tc.require(len(ids) == record['triangles'], 'Primitive archive/serialized face count differs')
        tc.require((slots[j]['slot'] == 'caps') == (roles[primitive] == CAP_ROLE), 'Body/cap provenance cannot be merged or relabeled')
        for key in rows:
            rows[key].append(slots[j]['current'][key][ids])
        mapping['primitiveIds'].extend([primitive] * len(ids))
        mapping['primitiveFaceIds'].extend(range(len(ids)))
        mapping['archiveSlotIds'].extend([j] * len(ids))
        mapping['archiveRowIds'].extend(ids)
        owners.extend([roles[primitive]] * len(ids))
        used[j].update(ids.tolist())
    tc.require(all(len(u) == len(s['current']['position']) for u, s in zip(used, slots)), 'No unaccounted active archive rows')
    return ({k: np.concatenate(v) for k, v in rows.items()},
            {k: np.asarray(v, dtype=np.int64) for k, v in mapping.items()}, np.asarray(owners))


def validate_cap_policy(policy, inputs):
    tc.require(isinstance(policy, dict) and set(policy) == {'declaration', 'rootReview'}, 'Explicit reviewed native cap pixel/filter policy required')
    declaration = policy['declaration']
    expected = {'dimensions': [3, 3], 'resampling': 'none', 'pltLayer': 0,
                'intensityPolicy': 'RGB-rec709-floor-byte', 'roughnessPolicy': 'ORM-green-times-factor-rounded-byte',
                'normalMap': 'absent', 'addedAO': 0, 'texture0': 'omitted', 'sourceUVChanged': False,
                'tiling': 'none', 'effectiveMetallicness': 0, 'specularity': .04, 'roughnessParameter': 0,
                'nativeFilterPolicy': 'engine-default-unverified-client-gate'}
    tc.require(declaration == expected, 'Only declared literal3x3 policy; no silent resize/neutral texture0')
    review = read(pinned(policy['rootReview'], inputs))
    tc.require(review.get('kind') == 'root-reviewed-pelvis-cap-native-pixel-policy' and review.get('reviewedBy') == '/root' and
               review.get('authorizeNativeDiagnosticStage') is True and review.get('policy') == declaration,
               'Concrete ROOT native cap policy review required')
    return declaration


def cap_pixels(doc, blob, material_id, policy, inputs):
    declaration = validate_cap_policy(policy, inputs)
    material = doc['materials'][material_id]
    tc.require(material.get('alphaMode', 'OPAQUE') == 'OPAQUE' and not material.get('normalTexture') and
               not material.get('occlusionTexture') and not material.get('extensions'), 'Cap absentnormal/noAO/opaque policy')
    pbr = material['pbrMetallicRoughness']
    tc.require(pbr.get('baseColorFactor', [1, 1, 1, 1]) == [1, 1, 1, 1] and
               pbr.get('roughnessFactor', 1) == 1 and pbr.get('metallicFactor', 1) == 1, 'Actual C original effective multipliers all1')
    def pixels(slot):
        texture = pbr[slot]
        tc.require(set(texture) <= {'index', 'texCoord'} and texture.get('texCoord', 0) == 0, 'Cap UV transform unsupported')
        item = doc['textures'][texture['index']]
        tc.require(not item.get('extensions'), 'Cap texture extension unsupported')
        image = doc['images'][item['source']]
        tc.require('bufferView' in image and not image.get('uri'), 'Embedded exact cap map required')
        view = doc['bufferViews'][image['bufferView']]
        tc.require(view.get('buffer', 0) == 0, 'External cap buffer')
        start = view.get('byteOffset', 0)
        value = np.asarray(Image.open(BytesIO(blob[start:start + view['byteLength']])).convert('RGBA'))
        tc.require(value.shape == (3, 3, 4) and (value[..., 3] == 255).all(), 'Literal opaque3x3 RGBA/ORM required')
        return value
    color, orm = pixels('baseColorTexture'), pixels('metallicRoughnessTexture')
    tc.require(not orm[..., 2].any(), 'Actual C ORM-blue0 requires effective native Metallicness0')
    rgb = color[..., :3]
    value = {'color': rgb, 'normal': None, 'roughness': orm[..., 1].copy(),
             'intensity': (rgb.astype(float) @ np.asarray([.2126, .7152, .0722])).clip(0, 255).astype(np.uint8)}
    return value, {'material': material_id, 'role': CAP_ROLE, 'sourceBindings': material,
                   'normalStrength': None, 'nativePixelPolicy': declaration, 'originalRGBA': color.tolist(), 'originalORM': orm.tolist()}


def materials(doc, blob, roles, part, cap_policy, inputs):
    ids = {}
    for primitive, role in roles.items():
        material = doc['meshes'][0]['primitives'][primitive]['material']
        tc.require(material not in ids or ids[material] == role, 'One source material cannot own incompatible roles')
        ids[material] = role
    body = {i: r for i, r in ids.items() if r != CAP_ROLE}
    result, proof = material_inputs(doc, blob, body, part, 0)
    caps = [i for i, r in ids.items() if r == CAP_ROLE]
    if caps:
        tc.require(part == 'pelvis' and len(caps) == 1, 'One actual C cap material required')
        result[CAP_ROLE], cap_proof = cap_pixels(doc, blob, caps[0], cap_policy, inputs)
        proof.append(cap_proof)
    else:
        tc.require(cap_policy is None, 'No stray cap policy on nonpelvis part')
    return result, proof


def material_name(model, role):
    tc.require(role in ROLES, 'Unknown material owner')
    name = model + ('f' if role == 'garment' else 'c' if role == CAP_ROLE else '')
    tc.require(len(name + 'r') <= 16, 'Material resref budget')
    return name


def expected_resources(model, roles):
    result = set()
    for role in roles:
        m = material_name(model, role)
        result.update({m + '.mtr', m + 'r.tga', m + ('.tga' if role == 'garment' else '.plt')})
        if role != CAP_ROLE:
            result.add(m + 'n.tga')
    return result


def write_model(path, model, corners, owners):
    lines = [f'newmodel {model}', f'setsupermodel {model} NULL', 'classification CHARACTER', 'setanimationscale 1',
             f'beginmodelgeom {model}', f'node dummy {model}', '  parent NULL', 'endnode']
    meshes = {}
    with tempfile.TemporaryDirectory() as temp:
        for index, role in enumerate(sorted(set(owners))):
            ids = np.flatnonzero(owners == role)
            part = Path(temp) / 'part.mdl'
            count = write_ascii(part, model, corners['position'][ids], corners['uv'][ids], corners['normal'][ids])
            block = re.search(r'(?ms)^node trimesh \S+\n.*?^endnode', part.read_text(encoding='ascii'))[0]
            node = model + 'p' + str(index)
            m = material_name(model, role)
            block = re.sub(r'^node trimesh \S+', 'node trimesh ' + node, block)
            block = re.sub(r'(?m)^  (bitmap|materialname) \S+', lambda x: '  ' + x[1] + ' ' + m, block)
            lines.append(block)
            meshes[node] = {'role': role, 'material': m, 'mergedCornerRows': ids.tolist(), 'asciiProof': count}
    lines += [f'endmodelgeom {model}', f'donemodel {model}']
    Path(path).write_text('\n'.join(lines) + '\n', encoding='ascii')
    return meshes


def write_materials(folder, model, values):
    for role, value in values.items():
        m = material_name(model, role)
        Image.fromarray(np.repeat(value['roughness'][..., None], 3, axis=2)).save(folder / (m + 'r.tga'))
        lines = ['renderhint NormalTangents']
        if role != CAP_ROLE:
            Image.fromarray(value['normal']).save(folder / (m + 'n.tga'))
            lines.append('texture1 ' + m + 'n')
        lines += ['texture3 ' + m + 'r', 'parameter float Roughness 0', 'parameter float Specularity 0.04',
                  'parameter float Metallicness ' + ('0' if role == CAP_ROLE else '0.001')]
        if role == 'garment':
            Image.fromarray(value['color']).save(folder / (m + '.tga'))
            lines.append('texture0 ' + m)
        else:
            h, w = value['intensity'].shape
            plt = np.stack([value['intensity'], np.zeros((h, w), dtype='u1')], axis=2)[::-1].copy()
            (folder / (m + '.plt')).write_bytes(b'PLT V1  ' + struct.pack('<IIII', 10, 0, w, h) + plt.tobytes())
        (folder / (m + '.mtr')).write_text('\n'.join(lines) + '\n', encoding='ascii')


def prepare(config_path):
    config_path = Path(config_path).resolve()
    c, inputs = read(config_path), {}
    executor(c, inputs)
    inputs[str(config_path)] = tc.sha(config_path)
    tp = pinned(c['targetContract'], inputs)
    target = tc.load(tp)
    validate_config(c, target)
    r, candidate = verify_leaf(c, tp, target, inputs)
    doc, blob = read_glb(candidate)
    tc.require(doc['nodes'] == [{'name': 'detached_geometry', 'mesh': 0}] and len(doc['meshes']) == 1,
               'Only canonical detached identity-node candidate; no Blender display basis')
    _, _, _, primitives = raw_corners(doc, blob)
    roles = {int(k): v for k, v in c['primitiveRoles'].items()}
    slots = archive_slots(r, inputs)
    corners, mapping, owners = merge_corners(slots, primitives, roles, c['part'])
    geo = geometry(corners['position'])
    tc.require(not geo['degenerateTriangles'] and not geo['coincidentTriangles'], 'Coincident/degenerate triangles block new stage')
    pixel_rows, material_proof = materials(doc, blob, roles, c['part'], c.get('capNativePolicy'), inputs)
    H, G = [tc.frame(target, tc.PART_JOINTS[c['part']], space) for space in ('working', 'runtime')]
    S = np.diag([SCALE, SCALE, SCALE, 1.])
    tc.require(np.allclose(G @ S, S @ H, atol=1e-12, rtol=0), 'Runtime attachment/local/world conversion differs')
    for name in ['target_contract.py', 'target_part_pipeline.py', 'target_part_stage.py', 'stage_stock_part.py',
                 'place_purposebuilt_pelvis.py', 'mirror_stock_limb_part.py']:
        path = Path(__file__).with_name(name)
        inputs[str(path.resolve())] = tc.sha(path)
    return {'config': c, 'configPath': config_path, 'targetPath': tp, 'target': target, 'receipt': r,
            'candidate': candidate, 'slots': slots, 'corners': corners, 'mapping': mapping, 'owners': owners,
            'pixels': pixel_rows, 'materialProof': material_proof, 'geometry': geo, 'inputs': inputs}


def root_approval(path, config_path, output, kind):
    row = read(path)
    tc.require(row.get('kind') == kind and row.get('reviewedBy') == '/root' and
               row.get('authorizeOneFreshDiagnosticOutput') is True and row.get('configuration') == ref(config_path) and
               Path(row['intendedOutput']).resolve() == Path(output).resolve(), 'Concrete pinned ROOT config/output approval required')
    deny_acceptance(row)
    return ref(path)


def stage(config_path, output, approval_path):
    p = prepare(config_path)
    out = Path(output).resolve()
    approval = root_approval(approval_path, p['configPath'], out, 'root-approved-working-leaf-runtime-stage')
    tc.require(not out.exists(), 'Fresh immutable stage output required')
    (out / 'ascii').mkdir(parents=True)
    (out / 'resources').mkdir()
    archives = []
    for slot in p['slots']:
        path = out / ('runtime-' + slot['slot'] + '-corners.npz')
        np.savez_compressed(path, **slot['arrays'])
        archives.append({'slot': slot['slot'], 'source': slot['source'], 'archive': ref(path), 'keys': slot['keys']})
    ordered = out / 'runtime-ordered-corners.npz'
    np.savez_compressed(ordered, **p['corners'], **p['mapping'])
    model = tc.model(p['target'], p['config']['part'])
    ascii_path = out / 'ascii' / (model + '.mdl')
    meshes = write_model(ascii_path, model, p['corners'], p['owners'])
    write_materials(out / 'resources', model, p['pixels'])
    hashes = {x.name: tc.sha(x) for x in sorted((out / 'resources').iterdir())}
    tc.require(set(hashes) == expected_resources(model, set(p['owners'])), 'Declared material resource inventory differs')
    inputs = dict(p['inputs'])
    inputs[approval['path']] = approval['sha256']
    snapshot = out / 'helpers'
    snapshot.mkdir()
    for path in inputs:
        if Path(path).parent == Path(__file__).resolve().parent and Path(path).suffix == '.py':
            shutil.copyfile(path, snapshot / Path(path).name)
    row = {'schemaVersion': 1, 'kind': STAGE_KIND, **tc.binding(p['targetPath'], p['target'], 'runtime'),
           'part': p['config']['part'], 'model': model, 'joint': tc.PART_JOINTS[p['config']['part']],
           'configuration': ref(p['configPath']), 'rootApproval': approval, 'sourceLeaf': p['config']['sourceLeaf'],
           'sourceCandidate': ref(p['candidate']), 'sourceWorkingStatureApplications': 0, 'statureApplications': 1,
           'runtimeScaleFraction': [10, 7], 'runtimeArchives': archives, 'orderedRuntimeCorners': ref(ordered),
           'attachmentWorld': tc.frame(p['target'], tc.PART_JOINTS[p['config']['part']], 'runtime').tolist(),
           'primitiveRoles': p['config']['primitiveRoles'], 'capNativePolicy': p['config'].get('capNativePolicy'),
           'asciiModel': ref(ascii_path), 'meshes': meshes, 'materialResourceHashes': hashes,
           'materialProof': p['materialProof'], 'geometry': p['geometry'], 'frozenInputs': inputs,
           'sourceTangentArraysSerializedInAscii': False, 'compilerGeneratesNativeTBN': True,
           'noFitFieldMirrorOrRigReapplication': True, 'diagnosticOnly': True, 'nativeCompiled': False,
           'nativeAccepted': False, 'materialAccepted': False, 'clientAccepted': False, 'productionAccepted': False,
           'limits': 'Current f64 corners scaled once. Inherited defects preserved. Native TBN/shader/client and full articulation gates remain.'}
    path = out / 'runtime-stage.json'
    path.write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')
    verify_stage(path, p['targetPath'], p['target'])
    return path


def verify_stage(path, target_path, target):
    path = Path(path).resolve()
    row = read(path)
    tc.require(row.get('schemaVersion') == 1 and row.get('kind') == STAGE_KIND and row.get('diagnosticOnly') is True,
               'Distinct runtime stage receipt required')
    tc.verify_binding(row, target_path, target, 'runtime')
    deny_acceptance(row, required=True)
    tc.require(row.get('part') in SOURCES and row['model'] == tc.model(target, row['part']) and
               row['joint'] == tc.PART_JOINTS[row['part']] and row['statureApplications'] == 1 and
               row['sourceWorkingStatureApplications'] == 0 and row['runtimeScaleFraction'] == [10, 7],
               'Runtime owner/stature count differs')
    inputs = {}
    for p, h in row['frozenInputs'].items():
        pinned({'path': p, 'sha256': h}, inputs)
    cpath = pinned(row['configuration'], inputs)
    prepared = prepare(cpath)
    tc.require(prepared['config']['part'] == row['part'] and row['sourceLeaf'] == prepared['config']['sourceLeaf'] and
               row['sourceCandidate'] == ref(prepared['candidate']), 'Runtime stage source association differs')
    root_approval(row['rootApproval']['path'], cpath, path.parent, 'root-approved-working-leaf-runtime-stage')
    tc.require(len(row['runtimeArchives']) == len(prepared['slots']), 'Runtime archive slot inventory differs')
    for actual, expected in zip(row['runtimeArchives'], prepared['slots']):
        tc.require(actual['slot'] == expected['slot'] and actual['source'] == expected['source'] and
                   actual['keys'] == expected['keys'], 'Runtime archive lineage differs')
        arrays = load_archive(actual['archive'], inputs)
        tc.require(set(arrays) == set(expected['arrays']) and all(arrays[k].dtype == v.dtype and arrays[k].shape == v.shape and
                   arrays[k].tobytes() == v.tobytes() for k, v in expected['arrays'].items()), 'Current/history runtime archive bytes differ')
    ordered = load_archive(row['orderedRuntimeCorners'], inputs)
    values = {**prepared['corners'], **prepared['mapping']}
    tc.require(set(ordered) == set(values) and all(ordered[k].dtype == v.dtype and ordered[k].shape == v.shape and
               ordered[k].tobytes() == v.tobytes() for k, v in values.items()), 'Ordered f64/corner map differs')
    pinned(row['asciiModel'], inputs)
    hashes = {x.name: tc.sha(x) for x in sorted((path.parent / 'resources').iterdir())}
    tc.require(hashes == row['materialResourceHashes'] and set(hashes) == expected_resources(row['model'], set(prepared['owners'])),
               'Exact declared material inventory changed')
    tc.require(row['primitiveRoles'] == prepared['config']['primitiveRoles'] and row['capNativePolicy'] == prepared['config'].get('capNativePolicy') and
               row['materialProof'] == prepared['materialProof'] and row['geometry'] == prepared['geometry'] and
               row['attachmentWorld'] == tc.frame(target, tc.PART_JOINTS[row['part']], 'runtime').tolist(),
               'Runtime frame/material/geometry declaration differs')
    inputs[str(path)] = tc.sha(path)
    return row, prepared, inputs


def compose(config_path, output, approval_path):
    config_path = Path(config_path).resolve()
    c, inputs = read(config_path), {}
    executor(c, inputs)
    tc.require(c.get('schemaVersion') == 1 and c.get('kind') == 'target-working-leaf-runtime-composition-config' and
               c.get('diagnosticOnly') is True and c.get('coordinateSpace') == 'runtime',
               'Distinct diagnostic runtime composition config')
    deny_acceptance(c)
    tp = pinned(c['targetContract'], inputs)
    target = tc.load(tp)
    out = Path(output).resolve()
    approval = root_approval(approval_path, config_path, out, 'root-approved-working-leaf-runtime-composition')
    tc.require(not out.exists(), 'Fresh composition required')
    parts, ascii_hashes, resources, sources = {}, {}, {}, []
    for item in c['stageReceipts']:
        path = pinned(item, inputs)
        r, _, pins = verify_stage(path, tp, target)
        tc.require(r['part'] not in parts, 'Duplicate body part ownership')
        parts[r['part']] = r['model'] + '.mdl'
        ascii_hashes[r['model'] + '.mdl'] = r['asciiModel']['sha256']
        tc.require(not (set(resources) & set(r['materialResourceHashes'])), 'Duplicate material resource ownership')
        resources.update(r['materialResourceHashes'])
        inputs.update(pins)
        sources.append({'part': r['part'], 'receipt': item, 'ascii': r['asciiModel'], 'resources': str(path.parent / 'resources')})
    tc.require(bool(parts) and set(parts) == set(c['declaredParts']) <= tc.BODY_PARTS, 'Declared complete/partial body inventory differs')
    tc.require(not c.get('requireAll14', False) or set(parts) == tc.BODY_PARTS, 'Fourteen declared body parts required')
    (out / 'ascii').mkdir(parents=True)
    (out / 'resources').mkdir()
    for source in sources:
        shutil.copyfile(source['ascii']['path'], out / 'ascii' / Path(source['ascii']['path']).name)
        for file in Path(source['resources']).iterdir():
            shutil.copyfile(file, out / 'resources' / file.name)
    inputs.update({str(config_path): tc.sha(config_path), approval['path']: approval['sha256']})
    r = {'schemaVersion': 1, 'kind': COMPOSITION_KIND, **tc.binding(tp, target, 'runtime'), 'configuration': ref(config_path),
         'rootApproval': approval, 'parts': parts, 'modelParts': {m: p for p, m in parts.items()},
         'asciiModelHashes': ascii_hashes, 'materialResourceHashes': resources, 'sourceStages': sources,
         'completeBodyInventoryPresent': set(parts) == tc.BODY_PARTS, 'provisionalHeadNeckRigEquipmentOwnedHere': False,
         'statureApplications': 1, 'diagnosticOnly': True, 'nativeCompiled': False, 'frozenInputs': inputs,
         'nativeAccepted': False, 'materialAccepted': False, 'clientAccepted': False, 'productionAccepted': False}
    path = out / 'conversion.json'
    path.write_text(json.dumps(r, indent=2) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--compose', action='store_true')
    args = parser.parse_args()
    path = (compose if args.compose else stage)(args.config, args.output, args.approval)
    print(json.dumps(ref(path)))
