"""Stage one LEAN single-PLT part as a working target-part-stage (stock-exact Human; no stature, no compile).

The stage selects one part of a verified LEAN atlas assembly (lean_single_plt_atlas.py) and records its explicit
lineage: parent representation (the sealed/compiled HIGH parent) -> reduction -> optional bounded repair -> basis
composition -> compiled basis -> normal maps encoded in that compiled basis -> single-PLT atlas. The ASCII model is
the literal native compiler input (authority literalNativeArchive; identity conversion not yet applied), so
convert_native_stage_identity.py applies the stock-exact working->runtime identity exactly once. The stage declares
the compiled basis its normal maps were encoded against; the native audit verifies the final compile still matches it.

Usage: stage_lean_part.py --target-contract <json> --target-contract-sha256 <sha> --atlas <atlas.json>
       --atlas-sha256 <sha> --part <part> --output <fresh dir>
"""
import argparse
import os
from pathlib import Path
import shutil

import numpy as np

import lean_common as L
import single_plt_part_contract as single_plt
import target_contract as contract
from nwn_ascii_trimesh import AsciiModel


def lineage(frozen, atlas):
    """Verify the whole LEAN receipt chain behind an atlas; returns the lineage record and parent manifest."""
    basis = L.read_json(frozen.pinned(atlas['basis'])); normals = L.read_json(frozen.pinned(atlas['normalMaps']))
    compiled = L.read_json(frozen.pinned(atlas['compiledBasis']))
    L.require(basis['kind'] == 'lean-basis-composition' and normals['kind'] == 'lean-normal-maps', 'LEAN basis/normal-map receipts required')
    L.require(normals['basis']['sha256'] == atlas['basis']['sha256'] and normals['compiledBasis'] == atlas['compiledBasis'],
              'Atlas normal maps were not encoded for its basis')
    L.require(compiled.get('complete') is True and compiled.get('executionMode') == 'compilemodel', 'Complete compiled basis required')
    parent = L.read_json(frozen.pinned(basis['parent'])); L.require(parent['kind'] == 'lean-parent-representation', 'Parent representation required')
    reductions = [L.read_json(frozen.pinned(row)) for row in basis['reductions']]
    L.require(all(r['kind'] == 'lean-part-reduction' and r['parent'] == basis['parent'] for r in reductions), 'Reductions descend from another parent')
    repair = L.read_json(frozen.pinned(basis['repair'])) if basis.get('repair') else None
    record = {'parentRepresentation': basis['parent'], 'parentLineage': parent.get('lineage', {}), 'parentDeclaration': parent['declaration'],
              'reductions': [{k: row[k] for k in ('path', 'sha256')} for row in basis['reductions']], 'repair': basis.get('repair'),
              'basisComposition': atlas['basis'], 'compiledBasis': atlas['compiledBasis'], 'normalMaps': atlas['normalMaps'],
              'tier': reductions[0]['tier'], 'operation': 'versioned LEAN descendant of the parent representation'}
    return record, parent, basis, reductions, repair


def compiler_corners(text, nodes, path):
    model = AsciiModel(text); arrays = {}
    for name in nodes:
        verts, normals, tverts, faces = model.arrays(model.node(name))
        arrays[name+'/positions'] = verts[faces[:, :3]]; arrays[name+'/normals'] = normals[faces[:, :3]]; arrays[name+'/uvNative'] = tverts[faces[:, 4:7], :2]
    np.savez_compressed(path, **arrays)
    return sum(int(len(arrays[name+'/positions'])) for name in nodes)


def stage(target_path, target_sha, atlas_path, atlas_sha, part, output):
    frozen = L.Frozen()
    target_path = frozen.pinned({'path': str(target_path), 'sha256': target_sha}); target = contract.load(target_path)
    L.require(single_plt.applies(target), 'LEAN single-PLT stages bind stock-exact Human targets')
    L.require(part in contract.BODY_PARTS, 'Declared body part required')
    atlas_path = frozen.pinned({'path': str(atlas_path), 'sha256': atlas_sha}); atlas = L.read_json(atlas_path)
    L.require(atlas.get('kind') == 'lean-single-plt-atlas' and atlas.get('materialLayout') == single_plt.LAYOUT, 'LEAN single-PLT atlas required')
    model = contract.model(target, part); L.require(atlas['prefix'] == target['identity']['prefix'], 'Atlas belongs to another prefix')
    record, parent, basis, reductions, repair = lineage(frozen, atlas)
    L.require(parent['targetContract']['sha256'] == target_sha, 'Parent representation belongs to another target contract')
    row = atlas['parts'][part]; ascii_source = frozen.pinned(row['ascii'])
    source_dir = atlas_path.parent/'resources'; names = sorted(single_plt.part_resources(model)-{model+'.mdl'})
    for name in names:
        L.require(L.sha(frozen.take(source_dir/name)) == row['resources'][name], 'Atlas resource changed: '+name)
    text = ascii_source.read_text(encoding='cp1252'); slots = single_plt.validate_slots(row['materialSlots'])
    proof = single_plt.check_part(model, text, (source_dir/(model+'.mtr')).read_text(encoding='cp1252'), (source_dir/(model+'.plt')).read_bytes(), slots)
    if part in contract.fixed_garment_parts(target):
        L.require(any(value['role'] == 'garment' for value in slots.values()), 'Fixed garment required for declared owner: '+part)
    output = L.fresh(output); (output/'ascii').mkdir(); (output/'resources').mkdir()
    shutil.copyfile(ascii_source, output/'ascii'/(model+'.mdl'))
    for name in names:
        try: os.link(source_dir/name, output/'resources'/name)
        except OSError: shutil.copyfile(source_dir/name, output/'resources'/name)
    corners = compiler_corners(text, list(slots), output/'authoritative-native-compiler-corners.npz')
    reduction_row = next(r['parts'][part] for r in reductions if part in r['parts'])
    receipt = {'schemaVersion': 2, 'kind': 'target-part-stage', **contract.binding(target_path, target, 'working'),
               'part': part, 'model': model, 'joint': contract.PART_JOINTS[part],
               'source': str(atlas_path), 'sourceSha256': atlas_sha,
               'sourceReceipt': basis['parent']['path'], 'sourceReceiptSha256': basis['parent']['sha256'],
               'statureApplications': 0, 'aoStrength': 0, 'untreatedParentSha256': basis['parent']['sha256'],
               'materialLayout': single_plt.LAYOUT, 'materialRoles': {node: value['role'] for node, value in slots.items()},
               'materialSlots': slots, 'materialInputBasis': 'lean-single-plt-atlas-of-parent-materials',
               'nativeGeometrySource': 'ascii', 'asciiModel': str(output/'ascii'/(model+'.mdl')),
               'asciiModelSha256': L.sha(output/'ascii'/(model+'.mdl')),
               'materialResourceHashes': {name: L.sha(output/'resources'/name) for name in names},
               'nativeCompilerInputProof': {'authority': 'literalNativeArchive', 'identityConversionApplied': False,
                                            'encodedPreviewSubstituted': False, 'triangleCount': corners,
                                            'compilerCornerArchive': L.pin(output/'authoritative-native-compiler-corners.npz'),
                                            'asciiIsCompilerInput': True},
               'leanReduction': {**record, 'budget': reduction_row['budget'], 'reducedTriangles': reduction_row['triangles'],
                                 'parentTriangles': reduction_row['parentTriangles'], 'surfaceError': reduction_row['highToLow'],
                                 'silhouette': reduction_row['silhouette']['worstMeanOffsetMm'],
                                 'repairedNodes': sorted(n for n in slots if repair and n in repair['nodes'])},
               'encodedNormalBasis': {'compileReceipt': atlas['compiledBasis']}, 'normalMapsEncodedAgainstCompiledBasis': True,
               'singlePltContract': proof['nodes'],
               'frozenInputs': {**frozen.verify(), **L.helper_pins('stage_lean_part.py', 'single_plt_part_contract.py', 'uv_atlas_raster.py',
                                                                   'nwn_ascii_trimesh.py', 'target_contract.py')},
               'diagnosticOnly': True, 'rigMode': contract.rig_mode(target), 'rigValidated': contract.rig_ready(target),
               'rigPilotAccepted': target['rig'].get('pilotAccepted', False), 'productionAccepted': False, 'nativeCompiled': False,
               'installedShaderVerified': False, 'clientAccepted': False,
               'limitation': 'LEAN candidate staging only; offline sheets, client appearance and production acceptance require review.'}
    result = output/'target-stage.json'; result.write_text(__import__('json').dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract', 'atlas', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--target-contract-sha256', required=True); parser.add_argument('--atlas-sha256', required=True)
    parser.add_argument('--part', required=True)
    args = parser.parse_args()
    result = stage(args.target_contract, args.target_contract_sha256, args.atlas, args.atlas_sha256, args.part, args.output)
    print(__import__('json').dumps({'receipt': str(result), 'receiptSha256': L.sha(result)}))
