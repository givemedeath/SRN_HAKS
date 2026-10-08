"""Fit, mirror or scale one detached donor against an explicit v2 target.

This path is separate from immutable Human receipts. Fits are in working
attachment-local coordinates; runtime conversion is a distinct, single step.
Every result remains diagnostic until the declared rig and client gates pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from mirror_stock_limb_part import detached_affine_bake, reflection_between_frames
from place_purposebuilt_pelvis import read_glb, rotation_xyz, write_glb


def pin(path, expected):
    path = Path(path).resolve()
    contract.require(contract.sha(path) == expected, 'Frozen input changed: ' + str(path))
    return path


def read_target(config):
    contract.require(config.get('schemaVersion') == 2, 'Explicit version 2 configuration required')
    path = pin(config['targetContract'], config['targetContractSha256'])
    return path, contract.load(path)


def verify_source_receipt(source, receipt_path, target_path, target, part, space, *, execution_adoption=None):
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('kind') == 'target-part-geometry' and receipt.get('schemaVersion') == 2,
                     'Target geometry receipt required; legacy receipts are not reinterpreted')
    contract.verify_binding(receipt, target_path, target, space)
    contract.require(receipt['part'] == part and receipt['joint'] == contract.PART_JOINTS[part],
                     'Source receipt part/attachment differs')
    contract.require(Path(receipt['candidate']).resolve() == source and receipt['candidateSha256'] == contract.sha(source),
                     'Receipt must associate the selected serialized candidate')
    contract.require(receipt['statureApplications'] == (0 if space == 'working' else 1),
                     'Geometry stature conversion count differs from coordinate space')
    if execution_adoption is None:
        for name, expected in receipt['frozenInputs'].items():
            pin(name, expected)
    else:
        from phenotype_execution_adoption import resolve_frozen_inputs
        resolve_frozen_inputs(execution_adoption, module_file=__file__,
            consumer='target_part_pipeline.verify_source_receipt', receipt_path=receipt_path,
            receipt=receipt, target_path=target_path, target=target, space=space)
    return receipt


def fit_matrix(config):
    factor = config['uniformScale']
    contract.require(isinstance(factor, (int, float)) and np.isfinite(factor) and factor > 0,
                     'Positive finite uniform fit scale required')
    rows = [np.asarray(config[name], dtype=float) for name in
            ('rotationDegreesXYZ', 'sourceAnchorNwn', 'targetAnchorLocal')]
    contract.require(all(value.shape == (3,) and np.isfinite(value).all() for value in rows),
                     'Finite three-component rotation and anchors required')
    rotation = rotation_xyz(rows[0])
    result = np.eye(4)
    result[:3, :3] = rotation * factor
    result[:3, 3] = rows[2] - result[:3, :3] @ rows[1]
    return result


def generation_source(source, receipt_path, target_path=None, target=None, part=None):
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('state') == 'success' and receipt.get('promptId'),
                     'Fit requires a successful collected donor job')
    if 'generationBinding' in receipt:
        contract.require(target_path is not None and target is not None and part in contract.PART_JOINTS,
                         'Bound generation requires explicit target and part')
        expected = contract.binding(target_path, target, 'working')
        expected.pop('coordinateSpace'); expected['part'] = part
        contract.require(receipt['generationBinding'] == expected,
                         'Collected generation belongs to another target, rig revision or part')
    matches = [row for row in receipt.get('outputs', [])
               if Path(row.get('localPath', '')).resolve() == source and row.get('sha256') == contract.sha(source)]
    contract.require(len(matches) == 1, 'Selected donor is not a collected generation output')
    return receipt



EXTERNAL_DONOR_KIND = 'user-provided-external-donor-intake'


def external_donor_pins(receipt):
    """Keep the external source, origin, inventory and every map in fit closure."""
    rows = dict(receipt['frozenInputs'])
    rows.update({receipt['source']: receipt['sourceSha256'],
                 receipt['origin']: receipt['originSha256'],
                 receipt['targetContract']: receipt['targetContractSha256'],
                 receipt['inventory']['path']: receipt['inventory']['sha256']})
    rows.update({row['path']: row['sha256'] for row in receipt['embeddedImageCopies']})
    return rows


def external_donor_source(source, receipt_path, target_path, target, part):
    """Verify an honest user-supplied static GLB without a synthetic job receipt."""
    source, receipt_path, target_path = map(lambda p: Path(p).resolve(),
                                          (source, receipt_path, target_path))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('kind') == EXTERNAL_DONOR_KIND and
                     type(receipt.get('schemaVersion')) is int and receipt['schemaVersion'] == 1,
                     'Explicit version 1 external donor intake required')
    allowed = {'schemaVersion','kind','providerDeclaredByUser','targetId','part','targetContract',
               'targetContractSha256','receivedUtc','origin','originSha256','source','sourceSha256',
               'byteLength','embeddedImageCopies','inventory','userDesignSteering','provenanceLimits',
               'selected','sourceUnchanged','frozenInputs'}
    contract.require(set(receipt) == allowed, 'External intake has missing/unsupported provenance fields')
    contract.require(part in contract.PART_JOINTS and receipt['part'] == part and
                     receipt['targetId'] == target['id'] and
                     Path(receipt['targetContract']).resolve() == target_path and
                     receipt['targetContractSha256'] == contract.sha(target_path),
                     'External donor belongs to another target or part')
    contract.require(Path(receipt['source']).resolve() == source and
                     receipt['sourceSha256'] == contract.sha(source) and
                     type(receipt['byteLength']) is int and receipt['byteLength'] == source.stat().st_size,
                     'External intake must associate the exact source path/hash/byte count')
    contract.require(all(isinstance(receipt[name], str) and receipt[name].strip()
                         for name in ('providerDeclaredByUser','origin','receivedUtc','userDesignSteering')) and
                     receipt['sourceUnchanged'] is True and receipt['selected'] is False and
                     isinstance(receipt['provenanceLimits'], list) and receipt['provenanceLimits'] and
                     all(isinstance(row, str) and row.strip() for row in receipt['provenanceLimits']),
                     'External donor requires declared user origin and unaccepted immutable provenance')
    contract.require(Path(receipt['origin']).is_absolute() and
                     receipt['originSha256'] == receipt['sourceSha256'],
                     'External origin must pin the unchanged user-supplied bytes')
    frozen = receipt['frozenInputs']
    contract.require(isinstance(frozen, dict) and frozen and
                     frozen.get(str(Path(receipt['origin']).resolve())) == receipt['originSha256'] and
                     frozen.get(str(target_path)) == receipt['targetContractSha256'],
                     'External intake must freeze original user input and exact target')
    for name, expected in frozen.items(): pin(name, expected)
    origin = pin(receipt['origin'], receipt['originSha256'])
    contract.require(origin.stat().st_size == receipt['byteLength'], 'External origin byte count differs')
    doc, binary = read_glb(source)
    contract.require(not doc.get('skins') and not doc.get('animations') and
                     all('skin' not in node for node in doc.get('nodes', [])) and
                     all(not any(key.startswith(('JOINTS_', 'WEIGHTS_')) for key in row.get('attributes', {}))
                         for mesh in doc.get('meshes', []) for row in mesh.get('primitives', [])),
                     'External donor must be detached static geometry; no external rig import')
    copies = receipt['embeddedImageCopies']; images = doc.get('images', [])
    contract.require(isinstance(copies, list) and len(copies) == len(images),
                     'External material image inventory must close every embedded image')
    seen = set(); image_paths = set()
    for row in copies:
        contract.require(isinstance(row, dict) and set(row) ==
                         {'imageIndex','path','sha256','mimeType','bufferView','length','nativeBytesCopiedWithoutEditing'},
                         'Explicit original embedded image copy required')
        index = row['imageIndex']
        contract.require(type(index) is int and 0 <= index < len(images) and index not in seen,
                         'External image ownership must be complete and unique')
        seen.add(index); image = images[index]
        contract.require('uri' not in image and type(image.get('bufferView')) is int and
                         0 <= image['bufferView'] < len(doc['bufferViews']) and
                         image.get('mimeType') in ('image/png', 'image/jpeg'),
                         'External maps must have explicit supported embedded bytes')
        view = doc['bufferViews'][image['bufferView']]; start = view.get('byteOffset', 0); length = view['byteLength']
        contract.require(view.get('buffer') == 0 and type(start) is int and type(length) is int and
                         start >= 0 and length > 0 and start+length <= len(binary),
                         'External image buffer range is invalid')
        data = binary[start:start+length]
        contract.require(row['nativeBytesCopiedWithoutEditing'] is True and
                         type(row['bufferView']) is int and row['bufferView'] == image['bufferView'] and
                         type(row['length']) is int and row['length'] == length and
                         row['mimeType'] == image['mimeType'] and
                         row['sha256'] == hashlib.sha256(data).hexdigest(),
                         'External image copy metadata differs from literal embedded source')
        path = pin(row['path'], row['sha256'])
        contract.require(path not in image_paths and path.stat().st_size == length,
                         'External image copy path/length must be unique and exact')
        image_paths.add(path)
    textures = doc.get('textures', [])
    contract.require(all(type(row.get('source')) is int and 0 <= row['source'] < len(images)
                         for row in textures), 'External texture image reference is unresolved')
    def material_closure(value):
        if isinstance(value, dict):
            for name, child in value.items():
                if name.endswith('Texture'):
                    contract.require(isinstance(child, dict) and type(child.get('index')) is int and
                                     0 <= child['index'] < len(textures),
                                     'External material texture reference is unresolved')
                material_closure(child)
        elif isinstance(value, list):
            for child in value: material_closure(child)
    material_closure(doc.get('materials', []))
    for mesh in doc.get('meshes', []):
        for primitive in mesh.get('primitives', []):
            if 'material' in primitive:
                contract.require(type(primitive['material']) is int and
                                 0 <= primitive['material'] < len(doc.get('materials', [])),
                                 'External primitive material reference is unresolved')
    inventory = receipt['inventory']
    contract.require(isinstance(inventory, dict) and set(inventory) == {'path','sha256'},
                     'External source inventory requires its exact pin')
    inventory_path = pin(inventory['path'], inventory['sha256'])
    expected = {name: doc.get(name) for name in
                ('asset','scenes','scene','nodes','meshes','materials','textures','samplers','accessors','buffers')}
    expected.update({name: doc.get(name, []) for name in
                     ('skins','animations','extensionsUsed','extensionsRequired')})
    expected['images'] = copies
    contract.require(json.loads(inventory_path.read_text(encoding='utf-8')) == expected,
                     'External inventory differs from decoded source geometry/material closure')
    for name, expected_hash in external_donor_pins(receipt).items(): pin(name, expected_hash)
    return receipt


def fit_source(source, receipt_path, target_path, target, part):
    """Dispatch only the explicit external intake; retain collected-job checks."""
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('kind') == EXTERNAL_DONOR_KIND:
        return external_donor_source(source, receipt_path, target_path, target, part)
    contract.require(not any(name in receipt for name in
                             ('providerDeclaredByUser','origin','originSha256','embeddedImageCopies','sourceUnchanged')),
                     'Unsupported external donor intake kind/schema; never reinterpret as a generation')
    return generation_source(source, receipt_path, target_path, target, part)


def execute(config_path, output):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path, target = read_target(config)
    operation = config['operation']
    contract.require(operation in ('fit', 'mirror', 'runtime'), 'Undeclared geometry operation')
    common = {'schemaVersion','operation','part','coordinateSpace','targetContract','targetContractSha256',
              'source','sourceSha256','sourceReceipt','sourceReceiptSha256','label','notes','protectedInputs'}
    controls = {'fit':{'uniformScale','rotationDegreesXYZ','sourceAnchorNwn','targetAnchorLocal'},
                'mirror':{'sourcePart','planeOriginWorld','planeNormalWorld'},'runtime':{'executionAdoption'}}
    contract.require(set(config) <= common | controls[operation], 'Unknown or inapplicable geometry controls')
    for name, expected in config.get('protectedInputs', {}).items(): pin(name, expected)
    part = config['part']
    contract.require(part in contract.PART_JOINTS, 'Undeclared target part')
    source = pin(config['source'], config['sourceSha256'])
    origin_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    dependencies = [config_path, target_path, source, origin_path, Path(__file__).resolve(),
                    Path(__file__).with_name('target_contract.py'),
                    Path(__file__).with_name('mirror_stock_limb_part.py'),
                    Path(__file__).with_name('place_purposebuilt_pelvis.py')]
    dependencies += [Path(name).resolve() for name in config.get('protectedInputs', {})]
    execution_evidence = None
    plane = None
    external_intake = None
    if operation == 'fit':
        contract.require(config['coordinateSpace'] == 'working', 'Fit at working height before runtime conversion')
        donor = fit_source(source, origin_path, target_path, target, part)
        if donor.get('kind') == EXTERNAL_DONOR_KIND:
            external_intake = donor
            dependencies += [Path(name).resolve() for name in external_donor_pins(donor)]
        matrix = fit_matrix(config)
        space, applications = 'working', 0
        source_part = None
    elif operation == 'runtime':
        contract.require(config['coordinateSpace'] == 'runtime', 'Runtime conversion output space must be explicit')
        context = None
        if 'executionAdoption' in config:
            value = config['executionAdoption']
            contract.require(isinstance(value,dict) and set(value)=={'proof'}, 'Exact runtime adoption proof required')
            row = value['proof']
            contract.require(isinstance(row,dict) and set(row)=={'path','sha256'}, 'Exact runtime proof pin required')
            pin(row['path'],row['sha256'])
            contract.require(contract.rig_mode(target)=='stock-exact' and target['rig']['runtimeScale']==1,
                             'Adopted runtime conversion requires stock-exact identity scale')
            from phenotype_execution_adoption import prepare_execution_adoption
            context = prepare_execution_adoption(row,target_path=target_path,target=target,space='working',
                         consumer='target_part_pipeline.verify_source_receipt',
                         receipt_pins=[{'path':str(origin_path),'sha256':contract.sha(origin_path)}])
            execution_evidence = dict(context.evidence())
        verify_source_receipt(source, origin_path, target_path, target, part, 'working',execution_adoption=context)
        matrix = np.diag([target['rig']['runtimeScale']] * 3 + [1.])
        space, applications = 'runtime', 1
        source_part = part
    else:
        source_part = config['sourcePart']
        contract.require(any({source_part, part} == set(pair) for pair in contract.PAIRS),
                         'Mirror requires a declared opposite limb pair')
        space = config['coordinateSpace']
        verify_source_receipt(source, origin_path, target_path, target, source_part, space)
        # Plane controls are measured in the selected target world coordinate space.
        matrix, plane = reflection_between_frames(
            contract.frame(target, contract.PART_JOINTS[source_part], space),
            contract.frame(target, contract.PART_JOINTS[part], space),
            config['planeOriginWorld'], config['planeNormalWorld'])
        applications = 0 if space == 'working' else 1
    doc, binary = read_glb(source)
    new_doc, new_bin, archive, proof = detached_affine_bake(doc, binary, matrix, operation == 'mirror')
    output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh output required; geometry receipts are immutable')
    output.mkdir(parents=True)
    candidate = output / 'candidate-local.glb'
    write_glb(candidate, new_doc, new_bin)
    corners = output / 'native-corners.npz'
    np.savez_compressed(corners, **archive)
    shutil.copyfile(__file__, output / 'executed-helper.py')
    joint = contract.PART_JOINTS[part]
    receipt = {'schemaVersion': 2, 'kind': 'target-part-geometry', 'operation': operation,
               **contract.binding(target_path, target, space), 'part': part, 'joint': joint,
               'model': contract.model(target, part), 'sourcePart': source_part,
               'source': str(source), 'sourceSha256': contract.sha(source),
               'sourceReceipt': str(origin_path), 'sourceReceiptSha256': contract.sha(origin_path),
               'candidate': str(candidate), 'candidateSha256': contract.sha(candidate),
               'nativeCornerArchive': {'path': str(corners), 'sha256': contract.sha(corners)},
               'statureApplications': applications, 'sourceToAttachmentLocal': matrix.tolist(),
               'attachmentWorld': contract.frame(target, joint, space).tolist(),
               'reflectionWorld': None if plane is None else plane.tolist(), 'proof': proof,
               'frozenInputs': {str(path): contract.sha(path) for path in dependencies},
               'diagnosticOnly': True, 'rigMode': contract.rig_mode(target),
               'rigValidated': contract.rig_ready(target), 'rigPilotAccepted': target['rig'].get('pilotAccepted', False),
               'clientAccepted': False, 'productionAccepted': False,
               'limitation': 'Serialized detached geometry only; anatomy, connectors, materials, bilateral motion and client review remain required.'}
    if execution_evidence is not None:
        from phenotype_infrastructure_adoption import plain
        execution_evidence = plain(execution_evidence)
        receipt['executionAdoptionEvidence'] = execution_evidence
        receipt['frozenInputs'].update(execution_evidence['verificationInputs'])
        proof_row = execution_evidence['proof']
        receipt['frozenInputs'][proof_row['path']] = proof_row['sha256']
        for module in ('phenotype_execution_adoption.py','phenotype_infrastructure_adoption.py'):
            path = Path(__file__).with_name(module).resolve()
            receipt['frozenInputs'][str(path)] = contract.sha(path)
    if external_intake is not None:
        for name, expected in external_donor_pins(external_intake).items(): pin(name, expected)
        receipt['sourceProvenance'] = {
            'kind': EXTERNAL_DONOR_KIND, 'schemaVersion': 1,
            'providerDeclaredByUser': external_intake['providerDeclaredByUser'],
            'origin': external_intake['origin'], 'originSha256': external_intake['originSha256'],
            'inventory': external_intake['inventory'],
            'embeddedImageCopies': external_intake['embeddedImageCopies'],
            'provenanceLimits': external_intake['provenanceLimits'],
            'collectedGenerationReceipt': False, 'externalRigImported': False}
    for name, expected in config.get('protectedInputs', {}).items(): pin(name, expected)
    result = output / 'geometry.json'
    result.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.config, args.output)
    print(json.dumps({'receipt': str(result), 'receiptSha256': contract.sha(result)}))
