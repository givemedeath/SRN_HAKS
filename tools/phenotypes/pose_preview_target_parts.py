"""Verify explicit target-local GLB selections before an offline pose preview."""
import json
from pathlib import Path

import numpy as np

import target_contract as contract


def select_receipts(paths, target_path, target, space, assembly, *, execution_adoption=None):
    """Select only declared assembly parts; retain every receipt/input pin."""
    contract.require(assembly.get('kind') == 'target-stock-diagnostic' and
                     assembly.get('schemaVersion') == 2, 'Version 2 target assembly required')
    contract.verify_binding(assembly['target'], target_path, target, space)
    declared = {}
    for row in assembly['parts']:
        part = row['part']
        contract.require(part in contract.PART_JOINTS and part not in declared,
                         'Target assembly has undeclared or duplicate part ownership')
        contract.require(row['model'] == contract.model(target, part),
                         'Target assembly resource ownership differs')
        contract.require(row['model']+'.mdl' in assembly['resources'],
                         'Target assembly part has no frozen resource')
        declared[part] = row['model']
    selected = {}; inputs = {}; receipts = []
    for name in paths:
        path = Path(name).resolve()
        receipt = json.loads(path.read_text(encoding='utf-8'))
        contract.require(receipt.get('kind') == 'target-part-geometry' and
                         receipt.get('schemaVersion') == 2,
                         'Version 2 target-part-geometry receipt required')
        contract.verify_binding(receipt, target_path, target, space)
        part = receipt['part']
        contract.require(part in declared, 'Replacement part is not declared by target assembly')
        contract.require(part not in selected, 'Duplicate target part receipt: '+part)
        joint = contract.PART_JOINTS[part]
        contract.require(receipt['joint'] == joint and receipt['model'] == declared[part],
                         'Target part receipt attachment/resource ownership differs')
        contract.require(receipt['statureApplications'] == (0 if space == 'working' else 1),
                         'Target part stature conversion count differs from coordinate space')
        attachment = np.asarray(receipt['attachmentWorld'], dtype=float)
        contract.require(attachment.shape == (4,4) and np.isfinite(attachment).all() and
                         np.allclose(attachment, contract.frame(target, joint, space),
                                     atol=1e-10, rtol=0),
                         'Target part receipt attachment frame differs')
        candidate = Path(receipt['candidate']).resolve()
        contract.require(candidate.suffix.lower() == '.glb' and candidate.is_file(),
                         'Target part requires its selected serialized GLB candidate')
        contract.require(contract.sha(candidate) == receipt['candidateSha256'],
                         'Target part candidate changed: '+str(candidate))
        frozen = receipt.get('frozenInputs')
        contract.require(isinstance(frozen, dict) and frozen and
                         str(Path(target_path).resolve()) in frozen,
                         'Target part requires frozen inputs including its exact target')
        if execution_adoption is None:
            for source, pin in frozen.items():
                contract.require(contract.sha(source) == pin, 'Target part frozen input changed: '+source)
                inputs[str(Path(source).resolve())] = pin
        else:
            from phenotype_execution_adoption import resolve_frozen_inputs
            physical, _ = resolve_frozen_inputs(execution_adoption, module_file=__file__,
                consumer='pose_preview_target_parts.select_receipts', receipt_path=path,
                receipt=receipt, target_path=target_path, target=target, space=space)
            inputs.update(physical)
        for key in ('source', 'sourceReceipt'):
            source = (Path(receipt[key]).resolve() if execution_adoption is None
                      else Path(receipt[key]))
            contract.require(str(source) in frozen and
                             frozen[str(source)] == receipt[key+'Sha256'],
                             'Target part source provenance missing from frozen inputs: '+key)
        inputs[str(path)] = contract.sha(path)
        inputs[str(candidate)] = receipt['candidateSha256']
        selected[part] = candidate
        receipts.append({'receipt':str(path), 'receiptSha256':inputs[str(path)],
                         'part':part, 'joint':joint, 'model':receipt['model'],
                         'candidate':str(candidate), 'candidateSha256':receipt['candidateSha256'],
                         'coordinateSpace':space, 'statureApplications':receipt['statureApplications'],
                         'clientEvidence':False})
    result = {'parts':selected, 'inputs':inputs, 'receipts':receipts,
              'retainedTargetStockParts':[part for part in declared if part not in selected]}
    if execution_adoption is not None:
        result['executionAdoption'] = execution_adoption.evidence()
    return result
