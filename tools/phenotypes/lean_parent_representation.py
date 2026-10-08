"""LEAN step 1: freeze the compiled parent (HIGH) body representation that a LEAN reduction descends from.

Reads an explicit declaration (every model's ASCII source and native binary, every material resource and optional
compile receipts as {path, sha256} pins), decodes each binary with the constrained native layout decoder
(audit_target_native_part.decode; node names come from the pinned ASCII) and writes per-node arrays (literal compiled
position, normal, UV, tangent, handedness, faces) plus a manifest binding each node to its material: skin nodes own
a PLT, garment nodes an opaque texture0 colour map; normal (texture1) and roughness (texture3 or the MTR Roughness
parameter) are recorded per node. Nothing is edited, compiled or accepted.

Usage: lean_parent_representation.py --declaration <json> --output <fresh dir>
"""
import argparse
from pathlib import Path

import numpy as np

import lean_common as L
from audit_target_native_part import decode
from nwn_ascii_trimesh import AsciiModel

KIND = 'lean-parent-representation'
DECLARATION = 'lean-parent-declaration'


def validate_declaration(data):
    L.require(data.get('kind') == DECLARATION and data.get('schemaVersion') == 1, 'Explicit LEAN parent declaration required')
    L.require(data.get('sex') in ('female', 'male') and data.get('prefix') == {'female': 'pfh0', 'male': 'pmh0'}[data['sex']],
              'Stock-exact Human sex/prefix required')
    expected = {L.model_name(data['prefix'], part) for part in L.PARTS}
    L.require(set(data['models']) == expected, 'Declaration must name exactly the fourteen body part models')
    poses = data.get('poses', {})
    L.require('idle' in poses and set(L.JOINTS.values()) <= set(poses['idle']), 'Idle joint matrices for every body joint required')
    for value in poses['idle'].values():
        matrix = np.asarray(value, float); L.require(matrix.shape == (4, 4) and np.isfinite(matrix).all(), 'Finite 4x4 joint matrices required')
    return expected


def compile_associations(frozen, receipts):
    """(source sha, binary sha) pairs proven by the declared native compile receipts."""
    pairs = set()
    for row in receipts:
        receipt = L.read_json(frozen.pinned(row))
        # Historical receipts predate the executionMode field; any declared mode must be the CLI compiler.
        L.require(receipt.get('complete') is True and receipt.get('executionMode', 'compilemodel') == 'compilemodel',
                  'Complete native compile receipt required')
        pairs |= {(model['name'], model['sourceSha256'], model['binarySha256']) for model in receipt['models']}
    return pairs


def build(declaration_path, output):
    frozen = L.Frozen(); declaration_path = frozen.take(declaration_path); data = L.read_json(declaration_path)
    models = validate_declaration(data)
    target = frozen.pinned(data['targetContract'])
    resources = {}
    for row in data['resources']:
        path = frozen.pinned(row); L.require(path.name.lower() not in resources, 'Duplicate declared resource: '+path.name)
        resources[path.name.lower()] = (path, row)
    associations = compile_associations(frozen, data.get('compileReceipts', []))
    output = L.fresh(output); (output/'arrays').mkdir()
    parts = {}
    for part in L.PARTS:
        model = L.model_name(data['prefix'], part); entry = data['models'][model]
        ascii_path = frozen.pinned(entry['ascii']); binary_path = frozen.pinned(entry['binary'])
        if associations:
            L.require((model+'.mdl', entry['ascii']['sha256'], entry['binary']['sha256']) in associations,
                      'Binary was not compiled from the declared ASCII: '+model)
        parsed = AsciiModel.read(ascii_path); nodes = [node.name for node in parsed.trimeshes()]
        meshes, _ = decode(binary_path.read_bytes(), model, nodes)
        rows = []
        for name in nodes:
            node = parsed.node(name); material = node.fields['materialname'][0].lower()
            L.require(node.fields['bitmap'][0].lower() == material, 'Parent bitmap/materialname differ: '+name)
            mtr_path, mtr_row = resources[material+'.mtr']; textures = L.mtr_textures(mtr_path.read_text(encoding='cp1252'))
            native = meshes[name]; arrays = output/'arrays'/(name+'.npz')
            np.savez_compressed(arrays, position=native['position'], normal=native['normal'], uv=native['uv'], tangent=native['tangent'],
                                sign=native['sign'], faces=native['faces'].astype('<u2'))
            row = {'mesh': name, 'material': material, 'arrays': L.pin(arrays), 'triangles': int(len(native['faces'])),
                   'vertices': int(len(native['position'])), 'mtr': mtr_row,
                   'normal': resources[textures['texture1']+'.tga'][1]}
            row['roughness'] = resources[textures['texture3']+'.tga'][1] if 'texture3' in textures else textures.get('roughness')
            L.require(row['roughness'] is not None, 'Roughness map or parameter required: '+material)
            if 'texture0' in textures:
                row.update(role='garment', garmentColor=resources[textures['texture0']+'.tga'][1], plt=None)
            else:
                L.require(material+'.plt' in resources, 'Skin material PLT required: '+material)
                row.update(role='skin', plt=resources[material+'.plt'][1], garmentColor=None)
            rows.append(row)
        parts[part] = {'joint': L.JOINTS[part], 'model': model, 'ascii': entry['ascii'], 'binary': entry['binary'], 'meshes': rows}
    context = []
    for row in data.get('context', []):
        context.append({'name': row['name'], 'joint': row['joint'], 'arrays': row['arrays']}); frozen.pinned(row['arrays'])
    for row in data.get('lineage', {}).values():
        if isinstance(row, dict) and set(row) >= {'path', 'sha256'}: frozen.pinned(row)
    helpers = L.helper_pins('lean_parent_representation.py', 'audit_target_native_part.py', 'nwn_ascii_trimesh.py')
    manifest = {'schemaVersion': 1, 'kind': KIND, 'sex': data['sex'], 'prefix': data['prefix'],
                'targetContract': L.pin(target), 'declaration': L.pin(declaration_path), 'lineage': data.get('lineage', {}),
                'parts': parts, 'poses': data['poses'], 'context': context,
                'decoder': 'audit_target_native_part.decode (constrained literal native layout)',
                'frozenInputs': {**frozen.verify(), **helpers}, 'geometryEdited': False, 'materialPixelsEdited': False,
                'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--declaration', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(build(args.declaration, args.output))
