"""Fit, mirror or scale one detached donor against an explicit v2 target.

This path is separate from immutable Human receipts. Fits are in working
attachment-local coordinates; runtime conversion is a distinct, single step.
Every result remains diagnostic until the target pilot and client gates pass.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

import target_contract as contract
from mirror_stock_limb_part import detached_affine_bake, reflection_between_frames
from place_purposebuilt_pelvis import read_glb, rotation_xyz, write_glb


def pin(path, expected):
    path = Path(path).resolve()
    try:
        return contract.verify_frozen_input(path, expected)
    except (ValueError, OSError) as error:
        raise ValueError('Frozen input changed: '+str(path)) from error


def read_target(config):
    contract.require(config.get('schemaVersion') == 2, 'Explicit version 2 configuration required')
    path = pin(config['targetContract'], config['targetContractSha256'])
    return path, contract.load(path)


def verify_source_receipt(source, receipt_path, target_path, target, part, space):
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
    for name, expected in receipt['frozenInputs'].items():
        pin(name, expected)
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


def generation_source(source, receipt_path):
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    contract.require(receipt.get('state') == 'success' and receipt.get('promptId'),
                     'Fit requires a successful collected donor job')
    matches = [row for row in receipt.get('outputs', [])
               if Path(row.get('localPath', '')).resolve() == source and row.get('sha256') == contract.sha(source)]
    contract.require(len(matches) == 1, 'Selected donor is not a collected generation output')
    return receipt


def execute(config_path, output):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path, target = read_target(config)
    operation = config['operation']
    contract.require(operation in ('fit', 'mirror', 'runtime'), 'Undeclared geometry operation')
    common = {'schemaVersion','operation','part','coordinateSpace','targetContract','targetContractSha256',
              'source','sourceSha256','sourceReceipt','sourceReceiptSha256','label','notes','protectedInputs'}
    controls = {'fit':{'uniformScale','rotationDegreesXYZ','sourceAnchorNwn','targetAnchorLocal'},
                'mirror':{'sourcePart','planeOriginWorld','planeNormalWorld'},'runtime':set()}
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
    plane = None
    if operation == 'fit':
        contract.require(config['coordinateSpace'] == 'working', 'Fit at working height before runtime conversion')
        generation_source(source, origin_path)
        matrix = fit_matrix(config)
        space, applications = 'working', 0
        source_part = None
    elif operation == 'runtime':
        contract.require(config['coordinateSpace'] == 'runtime', 'Runtime conversion output space must be explicit')
        verify_source_receipt(source, origin_path, target_path, target, part, 'working')
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
               'diagnosticOnly': True, 'rigPilotAccepted': target['rig']['pilotAccepted'],
               'clientAccepted': False, 'productionAccepted': False,
               'limitation': 'Serialized detached geometry only; anatomy, connectors, materials, bilateral motion and client review remain required.'}
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
