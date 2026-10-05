"""Provisional stock Human head/neck in isolated, hash-bound Troll artifacts.

Reuse current frozen diagnostic placement; copy exact stock PLTs under declared
part names. Native compilation is a separate compile-only shared-tool run.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np

import target_contract as contract
import shared_toolchain
from audit_native_static_equipment import decode_static_equipment
from audit_stock_equipment_palettes import read_stock_plt
from build_target_diagnostic import convert_part
from pipeline import save_json
from review_held_equipment_surfaces import freeze_bridge
from stage_target_rigid_equipment import mesh_data
from retarget import nodes, transforms

PARTS = {'head': 'head_g', 'neck': 'neck_g'}
ARTIFACT_ROOT = Path(__file__).resolve().parents[2] / 'output/phenotypes'


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def ref(path): return {'path': str(Path(path).resolve()), 'sha256': contract.sha(path)}


def owned_plt_stage(original, diagnostic, source_name, target_name, factor):
    """Use exactly reviewed placement and change only one explicit PLT binding."""
    contract.require(source_name.startswith('pmh0_') and target_name.startswith('pmg0_') and
                     source_name.split('_', 1)[1] in ('head001', 'neck001') and
                     target_name.split('_', 1)[1] == source_name.split('_', 1)[1],
                     'Only declared Human head001/neck001 to Troll part ownership supported')
    contract.require(factor in (1.0, 10/7), 'Working or single runtime conversion required')
    contract.require(diagnostic == convert_part(original, source_name, target_name, factor),
                     'Diagnostic differs from exact stock placement or applies stature twice')
    bindings = re.findall(r'(?mi)^\s*(bitmap|materialname)\s+(\S+)\s*$', diagnostic)
    contract.require(bindings == [('bitmap', source_name)], 'Exactly one stock part PLT binding required')
    return re.sub(r'(?mi)^(\s*bitmap\s+)' + re.escape(source_name) + r'\s*$',
                  lambda m: m[1] + target_name, diagnostic)


def corner_correspondence(native_faces, ascii_faces, native_points, ascii_points, native_uv, ascii_uv):
    """Ordered faces prove seam ownership; proximity alone never selects donors."""
    contract.require(native_faces.shape == ascii_faces[:, :3].shape, 'Ordered triangle coverage differs')
    pc, expected_pc = native_points[native_faces], ascii_points[ascii_faces[:, :3]]
    uc, expected_uc = native_uv[native_faces], ascii_uv[ascii_faces[:, 4:7], :2]
    p_error, uv_error = float(np.max(abs(pc - expected_pc))), float(np.max(abs(uc - expected_uc)))
    contract.require(p_error < 1e-6 and uv_error < 1e-6, 'Ordered source/native position or UV correspondence unresolved')
    position_owners = [set() for _ in native_points]; uv_owners = [set() for _ in native_points]
    for native, positions, uvs in zip(native_faces, ascii_faces[:, :3], ascii_faces[:, 4:7], strict=True):
        for ni, pi, ui in zip(native, positions, uvs, strict=True):
            position_owners[ni].add(int(pi)); uv_owners[ni].add(int(ui))
    contract.require(all(len(x) == 1 for x in position_owners) and all(len(x) == 1 for x in uv_owners),
                     'Unused or ambiguous native vertex/UV ownership')
    contract.require(set.union(*position_owners) == set(range(len(ascii_points))), 'Unrepresented stock ASCII position')
    return {'positionIds': [next(iter(x)) for x in position_owners],
            'uvIds': [next(iter(x)) for x in uv_owners],
            'positionMaximumLegacyDifferenceMeters': p_error, 'uvMaximumLegacyDifference': uv_error,
            'orderedFaceCornersProved': True}


def native_details(path):
    blob = Path(path).read_bytes(); decoded = decode_static_equipment(blob)
    contract.require(len(decoded['meshes']) == 1 and decoded['declaredNodeCount'] == 2 and
                     not decoded['duplicateNames'], 'Exact detached stock head/neck hierarchy required')
    mesh = decoded['meshes'][0]
    contract.require(len(mesh['uv']) == 1, 'One installed stock UV channel required')
    node = next(n for n in decoded['nodes'] if n['offset'] == mesh['offset'])
    at = 12 + mesh['offset']
    shading = {key: list(struct.unpack_from('<3f', blob, at + offset)) for key, offset in
               [('diffuse', 0xac), ('ambient', 0xb8), ('specular', 0xc4)]}
    shading['shininess'] = struct.unpack_from('<f', blob, at + 0xd0)[0]
    for name, offset in [('shadow', 0xd4), ('beaming', 0xd8), ('render', 0xdc), ('transparencyHint', 0xe0)]:
        shading[name] = struct.unpack_from('<I', blob, at + offset)[0]
    shading['textures'] = [blob[at+0xe8+i*64:at+0xe8+(i+1)*64].split(b'\0')[0].decode('ascii') for i in range(4)]
    shading['tangentPointer'] = struct.unpack_from('<I', blob, at+0x258)[0]
    shading['handednessPointer'] = struct.unpack_from('<I', blob, at+0x260)[0]
    return decoded, mesh, node, shading


def prepare(args):
    output = args.output.resolve()
    contract.require(not output.exists() and output.is_relative_to(ARTIFACT_ROOT.resolve()) and
                     output != ARTIFACT_ROOT.resolve(), 'Fresh isolated provisional output required')
    shared_toolchain.load(args.shared_toolchain, args.migration)
    target_path = args.target_contract.resolve(); target = contract.load(target_path)
    contract.require(target['identity']['prefix'] == 'pmg0' and target['rig']['sourcePrefix'] == 'pmh0' and
                     target['rig']['runtimeScale'] == 10/7, 'Explicit frozen Troll/Human source and stature required')
    pins = {}
    def pin(path, expected=None):
        path = Path(path).resolve(); actual = contract.sha(path)
        contract.require(expected is None or actual == expected, 'Frozen source changed: ' + str(path))
        pins[str(path)] = actual; return path
    frozen_path = args.frozen_rig.resolve(); freeze_path = frozen_path/'freeze.json'
    freeze = read(freeze_path); old_target = pin(freeze['sourceContract'], freeze['sourceContractSha256'])
    bridge = freeze_bridge(old_target, contract.load(old_target), target_path, freeze_path, pin)
    for path in (target_path, args.shared_toolchain, args.migration, Path(__file__),
                 Path(__file__).with_name('build_target_diagnostic.py'),
                 Path(__file__).with_name('native_compile.py'),
                 Path(__file__).with_name('audit_native_static_equipment.py'),
                 Path(__file__).with_name('audit_stock_equipment_palettes.py'),
                 Path(__file__).with_name('stage_target_rigid_equipment.py'),
                 Path(__file__).with_name('target_contract.py'),
                 Path(__file__).with_name('retarget.py')): pin(path)
    stock = frozen_path/'source-inputs'
    source_root = pin(stock/'ascii/pmh0.mdl', target['frozenInputs'][str((stock/'ascii/pmh0.mdl').resolve())])
    source_frames = transforms(nodes(source_root.read_text(encoding='ascii')))
    evidence = {}; source_records = {}
    for part, joint in PARTS.items():
        source_name, model = 'pmh0_'+part+'001', target['models'][part]
        source_records[part] = {}
        for role, directory, suffix in [('ascii', 'ascii', '.mdl'), ('native', 'raw', '.mdl'), ('palette', 'raw', '.plt')]:
            path = stock/directory/(source_name+suffix)
            pin(path, target['frozenInputs'][str(path.resolve())]); source_records[part][role] = ref(path)
        contract.require(np.max(abs(source_frames[joint] - contract.frame(target, joint, 'working'))) < 1e-12,
                         'Provisional stock centerline attachment changed: ' + part)
        source_records[part]['paletteMetadata'] = read_stock_plt(Path(source_records[part]['palette']['path']).read_bytes())
        source_records[part]['sourceHumanAttachmentWorld'] = source_frames[joint].tolist()
    pending = []
    for space, diagnostic_dir in [('working', args.diagnostic_working), ('runtime', args.diagnostic_runtime)]:
        diagnostic_dir = diagnostic_dir.resolve(); receipt = read(pin(diagnostic_dir/'diagnostic.json'))
        contract.verify_binding(receipt['target'], target_path, target, space)
        factor = 1.0 if space == 'working' else target['rig']['runtimeScale']
        for part, joint in PARTS.items():
            source_name, model = 'pmh0_'+part+'001', target['models'][part]
            old = pin(diagnostic_dir/'ascii'/(model+'.mdl'), receipt['resources'][model+'.mdl'])
            original = Path(source_records[part]['ascii']['path']).read_text(encoding='ascii')
            text = owned_plt_stage(original, old.read_text(encoding='ascii'), source_name, model, factor)
            pending.append((space, part, joint, model, text, old))
    output.mkdir(parents=True)
    for space, part, joint, model, text, old in pending:
        stage = output/space; (stage/'ascii').mkdir(exist_ok=True, parents=True); (stage/'resources').mkdir(exist_ok=True)
        ascii_path = stage/'ascii'/(model+'.mdl'); ascii_path.write_text(text, encoding='ascii')
        palette_path = stage/'resources'/(model+'.plt')
        shutil.copyfile(source_records[part]['palette']['path'], palette_path)
        contract.require(contract.sha(palette_path) == source_records[part]['palette']['sha256'], 'Palette bytes changed')
        evidence.setdefault(space, {})[part] = {'model': model, 'joint': joint,
            'statureApplications': int(space == 'runtime'), 'attachmentWorld': contract.frame(target, joint, space).tolist(),
            'sourceDiagnostic': ref(old), 'ascii': ref(ascii_path), 'palette': ref(palette_path),
            'geometryPlacementReusedExact': True, 'onlyAdditionalChange': 'bitmap resref to exact target-owned PLT copy',
            'paletteBytesHeaderLayersExactInstalledSource': True, 'bodyAccepted': False, 'materialAccepted': False}
    (output/'helper-snapshots').mkdir()
    snapshots = {}
    for path in list(pins):
        path = Path(path)
        if path.suffix == '.py':
            destination = output/'helper-snapshots'/path.name
            shutil.copyfile(path, destination); snapshots[str(path)] = ref(destination)
    for path, expected in pins.items(): contract.require(contract.sha(path) == expected, 'Input changed during preparation')
    record = {'schemaVersion': 1, 'kind': 'target-provisional-head-neck-preparation',
        **contract.binding(target_path, target, 'working'), 'coordinateSpaces': ['working', 'runtime'],
        'structuralEquivalence': bridge, 'sourceRecords': source_records, 'stages': evidence,
        'frozenInputs': pins, 'helperSnapshots': snapshots, 'productionAccepted': False,
        'headNeckAccepted': False, 'materialsAccepted': False, 'equipmentAccepted': False, 'clientAccepted': False,
        'humanFemaleSharedResourcesModified': False, 'sourceGeometryEdited': False, 'packageOrTablesWritten': False}
    save_json(output/'preparation.json', record)
    print(json.dumps({'preparation': ref(output/'preparation.json'), 'parts': 2, 'spaces': 2}))


def audit(args):
    output = args.output.resolve(); record = read(output/'preparation.json')
    for path, expected in record['frozenInputs'].items(): contract.require(contract.sha(path) == expected, 'Prepared input changed: '+path)
    shared_toolchain.load(args.shared_toolchain, args.migration)
    target = contract.load(record['targetContract']); contract.verify_binding(record, record['targetContract'], target, 'working')
    contract.require(not (output/'audit.json').exists(), 'Fresh audit required')
    rows = {}; arrays = {}; sources = {}
    for part in PARTS:
        original = record['sourceRecords'][part]
        decoded, mesh, node, shading = native_details(original['native']['path'])
        ascii_meshes = mesh_data(Path(original['ascii']['path']).read_text(encoding='ascii'))
        contract.require(len(ascii_meshes) == 1, 'Single installed source mesh required')
        am = next(iter(ascii_meshes.values())); faces = np.asarray(am['arrays']['faces'], int)
        match = corner_correspondence(mesh['faces'], faces, mesh['worldPositions'], am['world'], mesh['uv'][0], np.asarray(am['arrays']['tverts']))
        source_normals = mesh['normals'][mesh['faces']] @ np.linalg.inv(np.asarray(node['worldFrame'])[:3,:3])
        sources[part] = (mesh, shading, source_normals, faces)
        rows[part] = {'source': original, 'nativeVertices': len(mesh['positions']), 'asciiPositionVertices': len(am['vertices']),
            'sourceAsciiNormalsPresent': bool(am['normals'].size), 'triangles': len(faces), 'sourceCorrespondence': match,
            'sourceShading': shading, 'spaces': {}}
        arrays[part+'_source_P'] = mesh['worldPositions'][mesh['faces']]
        arrays[part+'_source_N'] = source_normals; arrays[part+'_source_UV'] = mesh['uv'][0][mesh['faces']]
    for space in ('working', 'runtime'):
        stage = output/space; compile_record = read(stage/'native-compile.json')
        contract.require(compile_record.get('complete') is True and len(compile_record['models']) == 2 and
                         compile_record.get('executionMode') == 'compilemodel' and
                         compile_record.get('interactiveClientLaunched') is False, 'Complete isolated two-model native compile required')
        compile_rows = {row['name']: row for row in compile_record['models']}
        expected_resources = set()
        for part, joint in PARTS.items():
            staged = record['stages'][space][part]; model = staged['model']; expected_resources.update([model+'.mdl', model+'.plt'])
            for reference in (staged['ascii'], staged['palette']): contract.require(contract.sha(reference['path']) == reference['sha256'], 'Stage changed')
            path = stage/'resources'/(model+'.mdl'); compiler = compile_rows[model+'.mdl']
            contract.require(compiler['sourceSha256'] == staged['ascii']['sha256'] and compiler['binarySha256'] == contract.sha(path), 'Compiler model lineage differs')
            contract.require(compile_record['materialResourceHashes'].get(model+'.plt') == staged['palette']['sha256'], 'Compile-time stock palette changed')
            decoded, mesh, node, shading = native_details(path); source, stock_shading, stock_normals, faces = sources[part]
            contract.require(shading['textures'][0] == model, 'Native target PLT binding differs')
            expected_shading = copy_shading(stock_shading, model)
            contract.require(shading == expected_shading, 'Native stock material flags/fields changed')
            contract.require(mesh['faces'].shape == source['faces'].shape, 'Native triangle coverage differs')
            pc, nc, uc = mesh['worldPositions'][mesh['faces']], mesh['normals'][mesh['faces']] @ np.linalg.inv(np.asarray(node['worldFrame'])[:3,:3]), mesh['uv'][0][mesh['faces']]
            factor = 1.0 if space == 'working' else 10/7
            expected_p = arrays[part+'_source_P']*factor
            p_error = float(np.max(abs(pc-expected_p)))
            contract.require(p_error < 2e-6 and np.array_equal(uc.astype(np.float32), arrays[part+'_source_UV'].astype(np.float32)), 'Native source ordered geometry/UV transport differs')
            length = np.linalg.norm(stock_normals, axis=-1, keepdims=True); expected_direction = stock_normals/length
            actual_direction = nc/np.linalg.norm(nc, axis=-1, keepdims=True)
            angle = np.rad2deg(np.arccos(np.clip(np.sum(expected_direction*actual_direction, axis=-1), -1, 1)))
            normal_error = float(np.max(abs(nc-expected_direction)))
            actor = pc @ contract.frame(target, joint, space)[:3,:3].T + contract.frame(target, joint, space)[:3,3]
            arrays[part+'_'+space+'_P'] = pc; arrays[part+'_'+space+'_N'] = nc; arrays[part+'_'+space+'_UV'] = uc
            arrays[part+'_'+space+'_actorP'] = actor
            rows[part]['spaces'][space] = {'target': contract.binding(record['targetContract'], target, space),
                'nativeModel': ref(path), 'compileReceipt': ref(stage/'native-compile.json'),
                'compiledVertices': len(mesh['positions']), 'triangles': len(mesh['faces']), 'statureApplications': int(space == 'runtime'),
                'maximumSourceNativePositionTransportDifferenceMeters': p_error, 'nativeUvCornersExactSourceFloat32': True,
                'rawSourceNormalArraysEditedOrNormalized': False, 'expectedNormalPolicy': 'Explicit derived unit direction from unchanged source native normals; positive uniform scale preserves directions.',
                'normalMaximumComponentDifferenceVsExpectedUnitDirection': normal_error, 'normalMaximumAngleDegrees': float(angle.max()),
                'strictNormalFloat32ValuesExactExpectedDirection': bool(np.array_equal(nc.astype(np.float32), expected_direction.astype(np.float32))),
                'nativeNormalsDirectionDiagnosticPass': bool(normal_error < 2e-6 and angle.max() < .01),
                'shadingFieldsAndFlagsExactInstalledSource': True, 'explicitTextureOwnershipRemap': {'from': stock_shading['textures'][0], 'to': model},
                'sourcePaletteBytesExact': True, 'headNeckAccepted': False, 'materialAccepted': False, 'clientAccepted': False}
        contract.require({p.name for p in (stage/'resources').iterdir()} == expected_resources, 'Unexpected or missing provisional native resources')
    for part in PARTS:
        w, r = arrays[part+'_working_actorP'], arrays[part+'_runtime_actorP']
        error = float(np.max(abs(r-(10/7)*w)))
        contract.require(error < 2e-7, 'Runtime actor geometry applies stature twice')
        rows[part]['runtimeActorMaximumSingleScaleErrorMeters'] = error
        rows[part]['workingRuntimeNativeNormalMaximumDifference'] = float(np.max(abs(arrays[part+'_runtime_N']-arrays[part+'_working_N'])))
    archive = output/'literal-native-corners.npz'; np.savez_compressed(archive, **arrays)
    for path, expected in record['frozenInputs'].items(): contract.require(contract.sha(path) == expected, 'Source changed during native audit')
    result = {'schemaVersion': 1, 'kind': 'target-provisional-head-neck-native-audit',
        **contract.binding(record['targetContract'], target, 'working'), 'preparation': ref(output/'preparation.json'),
        'parts': rows, 'literalCornerArchive': ref(archive), 'nativeGeometryShadingIndependentlyDecoded': True,
        'existingWorkingRuntimeDiagnosticGeometryReused': True, 'humanFemaleSharedResourcesModified': False,
        'sourceNormalsEditedOrNormalized': False, 'headNeckAccepted': False, 'materialsAccepted': False,
        'equipmentAccepted': False, 'clientAccepted': False, 'productionAccepted': False,
        'limitations': ['Provisional stock Human head/neck anatomy only; purpose-built body connector/colour continuity needs review.',
            'Native normal regeneration is measured separately from strict float32 preservation; no adapter or replacement-normal policy accepted.',
            'Target-owned PLT bytes preserve source palette channels; literal engine binding, palettes, rendering and hidden helmet behaviour remain client gates.',
            'No final pack, shared Human/female/global resources or tables changed.']}
    save_json(output/'audit.json', result)
    print(json.dumps({'audit': ref(output/'audit.json'), 'parts': 2, 'normalDirectionsPass': all(v['nativeNormalsDirectionDiagnosticPass'] for p in rows.values() for v in p['spaces'].values())}))


def copy_shading(original, texture):
    copied = {key: list(value) if isinstance(value, list) else value for key, value in original.items()}
    copied['textures'][0] = texture
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'audit'))
    for name in ('target-contract', 'frozen-rig', 'diagnostic-working', 'diagnostic-runtime', 'shared-toolchain', 'migration', 'output'):
        parser.add_argument('--'+name, type=Path, required=name in ('shared-toolchain', 'migration', 'output'))
    args = parser.parse_args()
    if args.action == 'prepare':
        contract.require(all(getattr(args, name) for name in ('target_contract', 'frozen_rig', 'diagnostic_working', 'diagnostic_runtime')), 'Explicit source/target diagnostic inputs required')
    {'prepare': prepare, 'audit': audit}[args.action](args)


if __name__ == '__main__': main()
