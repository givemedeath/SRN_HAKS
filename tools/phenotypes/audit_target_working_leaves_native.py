"""Independent f64 working-leaf -> runtime ASCII -> native diagnostic audit.

No compilation, rescaling of assets, acceptance, or old receipt reinterpretation.
Authoritative source T/W are retained as evidence; NWN compiles its own TBN.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image

import target_contract as tc
import stage_target_working_leaves as stage
from audit_geometry import arrays
from audit_native_limb_shading import validate_transport, float32_ulp_distance
from audit_target_native_part import decode, tangent_proof, LAYOUT_PINS, LAYOUT_COMMIT
from audit_target_diagnostic_uv_material_native import source_tangent_comparison

CONFIG_KIND = 'target-working-leaf-runtime-native-audit-config'
KIND = 'target-working-leaf-runtime-native-audit'
CLIENT_SHA = '3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a'


def independent_archive(source, actual, keys):
    """Recompute exactly once independently of the stage archive function."""
    pk, nk, tk = [keys[k] for k in ('P', 'N', 'T')]
    tc.require(set(actual) == set(source) | {'runtimeWorkingPositions', 'runtimeStatureFraction'}, 'Runtime/history inventory differs')
    tc.require(source[pk].dtype == np.dtype('float64') and actual[pk].dtype == source[pk].dtype and
               actual[pk].shape == source[pk].shape and
               np.array_equal(actual[pk], source[pk] * (10. / 7.)), 'Authoritative runtime P must apply10/7 exactly once')
    for k, v in source.items():
        if k != pk:
            tc.require(actual[k].dtype == v.dtype and actual[k].shape == v.shape and actual[k].tobytes() == v.tobytes(),
                       'Runtime authored/history bytes differ: ' + k)
    tc.require(actual['runtimeWorkingPositions'].dtype == source[pk].dtype and
               actual['runtimeWorkingPositions'].shape == source[pk].shape and
               actual['runtimeWorkingPositions'].tobytes() == source[pk].tobytes() and
               np.array_equal(actual['runtimeStatureFraction'], [10, 7]), 'Literal working authority/fraction missing')
    return {'currentPositionKey': pk, 'currentNormalKey': nk, 'currentTangentKey': tk,
            'positionScaleExactlyOnce': True, 'allOtherSourceAndHistoryArraysLiteral': True,
            'sourceTriangles': len(source[pk]), 'sourceTangentBasisVisualAccepted': False}


def ascii_meshes(text, model, meshes, source, primitive_roles):
    nodes = re.findall(r'(?ms)^node (\S+) (\S+)\n(.*?)^endnode\s*$', text)
    tc.require(len(nodes) == len(meshes) + 1 and nodes[0][:2] == ('dummy', model) and
               re.search(r'(?m)^\s*parent NULL\s*$', nodes[0][2]), 'Exact detached ASCII hierarchy required')
    tc.require(re.search(r'(?m)^newmodel ' + re.escape(model) + r'$', text) and
               re.search(r'(?m)^setsupermodel ' + re.escape(model) + r' NULL$', text) and
               re.search(r'(?m)^classification CHARACTER$', text) and
               re.search(r'(?m)^setanimationscale 1$', text) and 'newanim ' not in text,
               'Isolated ASCII model identity/animation scale required')
    result = {}
    covered = []
    for kind, name, body in nodes[1:]:
        tc.require(kind == 'trimesh' and name in meshes and name not in result, 'Undeclared ASCII mesh')
        owner = meshes[name]
        tc.require(owner['material'] == stage.material_name(model, owner['role']), 'Declared material owner differs')
        for line in ['parent ' + model, 'position 0 0 0', 'orientation 0 0 0 0', 'bitmap ' + owner['material'],
                     'materialname ' + owner['material'], 'render 1', 'shadow 1']:
            tc.require(re.search(r'(?m)^\s*' + re.escape(line) + r'\s*$', body), 'ASCII static transform/material differs')
        tc.require(not re.search(r'(?m)^\s*(?:scale|positionkey|orientationkey|scalekey)\b', body), 'Implicit ASCII transform/controller')
        p, n, uv, f = [np.asarray(arrays(body, k)) for k in ['verts', 'normals', 'tverts', 'faces']]
        tc.require(p.ndim == 2 and p.shape[1] == 3 and n.shape == p.shape and uv.ndim == 2 and uv.shape[1] == 3 and
                   f.ndim == 2 and f.shape[1] == 8 and len(p) < 65536 and len(f) > 0 and
                   all(np.isfinite(v).all() for v in [p, n, uv, f]) and np.array_equal(f, f.astype(int)), 'Malformed/budget ASCII arrays')
        f = f.astype(int)
        tc.require(f[:, :3].min() >= 0 and f[:, :3].max() < len(p) and f[:, 4:7].min() >= 0 and f[:, 4:7].max() < len(uv),
                   'ASCII corner index exceeds arrays')
        ids = np.asarray(owner['mergedCornerRows'], dtype=int)
        tc.require(ids.shape == (len(f),) and len(np.unique(ids)) == len(ids) and ids.min() >= 0 and
                   ids.max() < len(source['position']), 'Declared ordered runtime corner mapping differs')
        tc.require(all(primitive_roles[int(p)] == owner['role'] for p in source['primitiveIds'][ids]),
                   'ASCII material role differs from authoritative primitive ownership')
        corners = {'position': p[f[:, :3]], 'normal': n[f[:, :3]], 'uv': uv[f[:, 4:7], :2]}
        tc.require(all(np.array_equal(value, source[k][ids]) for k, value in corners.items()), 'ASCII .17g differs from authoritative f64 corners')
        result[name] = {'role': owner['role'], 'material': owner['material'], 'rows': ids, 'corners': corners}
        covered.extend(ids.tolist())
    tc.require(set(result) == set(meshes) and sorted(covered) == list(range(len(source['position']))),
               'Every runtime triangle must be owned exactly once')
    return result


def material_audit(folder, model, pixels, material_proof, declared_hashes):
    folder = Path(folder)
    tc.require(set(declared_hashes) == stage.expected_resources(model, set(pixels)), 'Declared material resource names differ')
    result = {}
    for role, value in pixels.items():
        m = stage.material_name(model, role)
        lines = ['renderhint NormalTangents']
        if role != stage.CAP_ROLE:
            lines.append('texture1 ' + m + 'n')
            tc.require(np.array_equal(np.asarray(Image.open(folder / (m + 'n.tga')).convert('RGB')), value['normal']), 'Normal pixels changed')
        lines += ['texture3 ' + m + 'r', 'parameter float Roughness 0', 'parameter float Specularity 0.04',
                  'parameter float Metallicness ' + ('0' if role == stage.CAP_ROLE else '0.001')]
        if role == 'garment':
            lines.append('texture0 ' + m)
            tc.require(np.array_equal(np.asarray(Image.open(folder / (m + '.tga')).convert('RGB')), value['color']), 'Opaque garment color changed')
        else:
            data = (folder / (m + '.plt')).read_bytes()
            h, w = value['intensity'].shape
            tc.require(data[:8] == b'PLT V1  ' and struct.unpack_from('<IIII', data, 8) == (10, 0, w, h) and
                       len(data) == 24 + w * h * 2, 'Exact declared PLT header/dimensions required')
            decoded = np.frombuffer(data[24:], dtype='u1').reshape(h, w, 2)[::-1]
            tc.require(np.array_equal(decoded[..., 0], value['intensity']) and not decoded[..., 1].any(), 'PLT intensity/layer0 differs')
            if role == stage.CAP_ROLE:
                tc.require((h, w) == (3, 3), 'Cap PLT may not be silently resized')
                proof = next(x for x in material_proof if x['role'] == role)
                raw = np.asarray(proof['originalRGBA'], dtype='u1')
                original_orm = np.asarray(proof['originalORM'], dtype='u1')
                expected = (raw[..., :3].astype(float) @ [.2126, .7152, .0722]).clip(0, 255).astype('u1')
                tc.require(np.array_equal(decoded[..., 0], expected) and np.array_equal(value['roughness'], original_orm[..., 1]) and
                           not original_orm[..., 2].any(), 'Independent literal C intensity/roughness/metallic source proof differs')
        tc.require((folder / (m + '.mtr')).read_text(encoding='ascii').splitlines() == lines, 'Exact role-specific MTR policy differs')
        rough = np.asarray(Image.open(folder / (m + 'r.tga')).convert('RGB'))
        tc.require(np.array_equal(rough, np.repeat(value['roughness'][..., None], 3, axis=2)), 'Linear ORM-green roughness pixels changed')
        for name in stage.expected_resources(model, {role}):
            tc.require(tc.sha(folder / name) == declared_hashes[name], 'Actual compiled material dependency changed')
        result[role] = {'material': m, 'PLTLayer': 0 if role != 'garment' else None, 'normalMapAbsent': role == stage.CAP_ROLE,
                        'skinTexture0Omitted': role != 'garment', 'roughnessSourceGreenExact': True,
                        'clientFilteringPaletteAndNormalAbsenceAccepted': False}
    return result


def validate_config(c):
    tc.require(c.get('schemaVersion') == 1 and c.get('kind') == CONFIG_KIND and c.get('diagnosticOnly') is True and
               c.get('coordinateSpace') == 'runtime' and c.get('part') in stage.SOURCES,
               'Explicit finite runtime diagnostic native audit config required')
    tc.require(type(c.get('nativeUvMaximumUlps')) is int and c['nativeUvMaximumUlps'] in (0, 1), 'Explicit exact/one-ULP UV policy required')
    tc.require(c.get('expectedClientSha256') == CLIENT_SHA, 'Exact frozen compiler client pin required')
    stage.deny_acceptance(c)


def composition_association(comp, config, target):
    tc.require(config.get('schemaVersion') == 1 and config.get('kind') == 'target-working-leaf-runtime-composition-config' and
               config.get('coordinateSpace') == 'runtime' and config.get('diagnosticOnly') is True,
               'Exact new composition configuration required')
    declared = config['declaredParts']
    tc.require(len(set(declared)) == len(declared) and bool(declared) and set(declared) <= tc.BODY_PARTS,
               'Finite unique declared body ownership')
    parts = {p: tc.model(target, p) + '.mdl' for p in declared}
    tc.require(comp['parts'] == parts and comp['modelParts'] == {m: p for p, m in parts.items()} and
               comp['completeBodyInventoryPresent'] == (set(parts) == tc.BODY_PARTS) and
               comp['provisionalHeadNeckRigEquipmentOwnedHere'] is False and
               (not config.get('requireAll14', False) or set(parts) == tc.BODY_PARTS), 'Composition target inventory differs')
    source = comp['sourceStages']
    tc.require(len(source) == len(parts) and {r['part'] for r in source} == set(parts) and
               len(config['stageReceipts']) == len(source) and
               sorted((r['receipt']['path'], r['receipt']['sha256']) for r in source) ==
               sorted((r['path'], r['sha256']) for r in config['stageReceipts']),
               'Composition source stages differ from declared exact config')
    return True


def audit(config_path, output):
    cp = Path(config_path).resolve()
    c, inputs = stage.read(cp), {}
    stage.executor(c, inputs, __file__)
    validate_config(c)
    inputs[str(cp)] = tc.sha(cp)
    tp = stage.pinned(c['targetContract'], inputs)
    target = tc.load(tp)
    sp = stage.pinned(c['stageReceipt'], inputs)
    receipt, prepared, source_inputs = stage.verify_stage(sp, tp, target)
    tc.require(receipt['part'] == c['part'], 'Native audit/stage part owner differs')
    inputs.update(source_inputs)
    archive_proofs = []
    for slot in receipt['runtimeArchives']:
        original = stage.load_archive(slot['source'], inputs)
        actual = stage.load_archive(slot['archive'], inputs)
        archive_proofs.append(independent_archive(original, actual, slot['keys']))
    source = stage.load_archive(receipt['orderedRuntimeCorners'], inputs)
    converted = Path(c['converted']).resolve()
    comp_path = stage.pinned(c['compositionReceipt'], inputs)
    comp = stage.read(comp_path)
    tc.require(comp_path == converted / 'conversion.json' and comp.get('schemaVersion') == 1 and
               comp.get('kind') == stage.COMPOSITION_KIND and comp.get('statureApplications') == 1 and
               comp.get('diagnosticOnly') is True, 'Distinct exact runtime composition required')
    tc.verify_binding(comp, tp, target, 'runtime')
    stage.deny_acceptance(comp, required=True)
    for p, h in comp['frozenInputs'].items():
        stage.pinned({'path': p, 'sha256': h}, inputs)
    ccp = stage.pinned(comp['configuration'], inputs)
    cc = stage.read(ccp)
    stage.executor(cc, inputs)
    tc.require(cc['targetContract'] == stage.ref(tp), 'Composition configuration target pin differs')
    composition_association(comp, cc, target)
    approval = stage.pinned(comp['rootApproval'], inputs)
    stage.root_approval(approval, ccp, converted, 'root-approved-working-leaf-runtime-composition')
    selected = [x for x in comp['sourceStages'] if x['part'] == c['part']]
    tc.require(len(selected) == 1 and selected[0]['receipt'] == stage.ref(sp), 'Composition must select exact source stage')
    npth = stage.pinned(c['nativeReceipt'], inputs)
    compiled = stage.read(npth)
    tc.require(npth == converted / 'native-compile.json' and compiled.get('complete') is True and
               compiled.get('executionMode') == 'compilemodel' and compiled.get('interactiveClientLaunched') is False and
               compiled.get('clientSha256') == CLIENT_SHA, 'Completed frozen compilemodel-only receipt required')
    stage.pinned({'path': compiled['client'], 'sha256': CLIENT_SHA}, inputs)
    tc.require(compiled['materialResourceHashes'] == comp['materialResourceHashes'], 'Compile-time material manifest changed')
    actual_ascii = {p.name: tc.sha(p) for p in (converted / 'ascii').iterdir()}
    actual_resources = {p.name: tc.sha(p) for p in (converted / 'resources').iterdir()}
    native_rows = {r['name']: r for r in compiled['models']}
    tc.require(actual_ascii == comp['asciiModelHashes'] and len(native_rows) == len(compiled['models']) and
               set(native_rows) == set(comp['modelParts']) and
               set(actual_resources) == set(comp['materialResourceHashes']) | set(native_rows), 'Exact compiled resource/model inventory differs')
    for name, digest in comp['materialResourceHashes'].items():
        tc.require(actual_resources[name] == digest, 'Compiled material dependency changed: ' + name)
    for name, row in native_rows.items():
        tc.require(row['sourceSha256'] == actual_ascii[name] and row['binarySha256'] == actual_resources[name] and
                   (converted / 'resources' / name).stat().st_size == row['bytes'], 'Compiled model association differs')
    model = receipt['model']
    tc.require(actual_ascii[model + '.mdl'] == receipt['asciiModel']['sha256'], 'Composed ASCII differs from exact stage')
    for name, digest in receipt['materialResourceHashes'].items():
        tc.require(comp['materialResourceHashes'].get(name) == digest, 'Part material ownership differs')
    ascii_path = stage.pinned(receipt['asciiModel'], inputs)
    ascii_rows = ascii_meshes(ascii_path.read_text(encoding='ascii'), model, receipt['meshes'], source,
                             {int(k): v for k, v in receipt['primitiveRoles'].items()})
    binary = converted / 'resources' / (model + '.mdl')
    inputs[str(binary)] = tc.sha(binary)
    native, root = decode(binary.read_bytes(), model, ascii_rows)
    proof = {}
    for name, row in ascii_rows.items():
        ids = row['rows']
        selected = {k: source[k][ids] for k in ('position', 'normal', 'uv')}
        actual = {k: native[name][k][native[name]['faces']] for k in selected}
        ae, be, exact = validate_transport(selected, row['corners'], actual, c['nativeUvMaximumUlps'])
        tc.require(native[name]['layout']['textureSlots'] == [row['material'], '', '', row['material']] and
                   native[name]['layout']['shadowFlag'] == 1, 'Native material slots/static shadow differ')
        proof[name] = {'role': row['role'], 'sourceToAsciiErrors': ae, 'sourceToNativeErrors': be,
                       'nativeCornersExactSourceFloat32': exact, 'explicitNativeUVMaximumUlps': c['nativeUvMaximumUlps'],
                       'observedUVMaximumUlps': int(float32_ulp_distance(actual['uv'], selected['uv']).max()),
                       'compilerTBN': tangent_proof(native[name]),
                       'sourceTangentComparison': source_tangent_comparison({'tangents': source['tangents'][ids]}, native[name])}
    materials = material_audit(converted / 'resources', model, prepared['pixels'], prepared['materialProof'], receipt['materialResourceHashes'])
    layouts = [stage.pinned({'path': str(Path(c['layoutDirectory']) / n), 'sha256': h}, inputs) for n, h in LAYOUT_PINS.items()]
    out = Path(output).resolve()
    tc.require(not out.exists(), 'Fresh immutable native diagnostic audit required')
    (out / 'helpers').mkdir(parents=True)
    for name in ['audit_target_working_leaves_native.py', 'stage_target_working_leaves.py', 'audit_target_native_part.py',
                 'audit_native_limb_shading.py', 'audit_target_diagnostic_uv_material_native.py', 'audit_geometry.py', 'target_contract.py']:
        path = Path(__file__).with_name(name)
        inputs[str(path.resolve())] = tc.sha(path)
        shutil.copyfile(path, out / 'helpers' / name)
    (out / 'layout').mkdir()
    for path in layouts:
        shutil.copyfile(path, out / 'layout' / path.name)
    row = {'schemaVersion': 1, 'kind': KIND, **tc.binding(tp, target, 'runtime'), 'part': c['part'], 'model': model,
           'statureApplications': 1, 'stageReceipt': stage.ref(sp), 'compositionReceipt': stage.ref(comp_path),
           'nativeReceipt': stage.ref(npth), 'nativeModel': stage.ref(binary), 'root': root,
           'independentArchiveProofs': archive_proofs, 'meshes': proof, 'materials': materials,
           'layoutSourceCommit': LAYOUT_COMMIT, 'frozenInputs': inputs, 'attributeTransportVerified': True,
           'materialTransportVerified': True, 'nativeCompilerExecuted': False, 'diagnosticOnly': True,
           'sourceAuthoredTangentsSerializedInAscii': False, 'sourceAuthoredTangentPreservationClaim': False,
           'nativeAccepted': False, 'materialAccepted': False, 'clientAccepted': False, 'productionAccepted': False,
           'limits': 'Independent f64/ASCII/native cast proofs and generated TBN measurements only. Inherited source defects, literal native/client material and all motion/equipment gates remain.'}
    path = out / 'native-audit.json'
    path.write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage.ref(audit(args.config, args.output))))
