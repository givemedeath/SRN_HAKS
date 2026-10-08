"""Target-aware frozen inputs and explicit connector regions for read-only audits."""
import json
from pathlib import Path
import re
import numpy as np
import target_contract as contract
from target_part_pipeline import verify_source_receipt


def pinned(value):
    contract.require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'Explicit path/hash connector input required')
    path = Path(value['path']).resolve()
    contract.require(contract.sha(path) == value['sha256'], 'Frozen connector input changed: ' + str(path))
    return path


def load_config(path):
    path = Path(path).resolve(); config = json.loads(path.read_text())
    contract.require(config.get('schemaVersion') == 1 and config.get('kind') == 'target-connector-surface-config', 'Target connector config schema1 required')
    target_path = pinned(config['targetContract']); target = contract.load(target_path)
    contract.require(config.get('coordinateSpace') == 'working', 'Connector surface audit requires explicit working space')
    contract.require(set(config['geometryReceipts']) == {'chest', 'bicepl', 'bicepr'}, 'Connector audit requires the declared chest and both upper arms')
    contract.require(set(config['stockParts']) == {'head', 'neck'}, 'Connector audit requires exact head/neck source ownership')
    pins = {str(path): contract.sha(path), str(target_path): contract.sha(target_path)}
    source_paths = {}
    for part, value in config['geometryReceipts'].items():
        receipt_path = pinned(value); receipt = json.loads(receipt_path.read_text())
        contract.verify_binding(receipt, target_path, target, 'working')
        contract.require(receipt.get('part') == part and receipt.get('statureApplications') == 0, 'Explicit unscaled working part required')
        candidate = Path(receipt['candidate']).resolve()
        contract.require(contract.sha(candidate) == receipt['candidateSha256'], 'Connector candidate changed')
        verify_source_receipt(candidate,receipt_path,target_path,target,part,'working')
        contract.require(np.array_equal(np.asarray(receipt['attachmentWorld']),contract.frame(target,contract.PART_JOINTS[part],'working')), 'Connector attachment frame differs')
        pins.update(receipt['frozenInputs'])
        source_paths[part] = receipt_path; pins[str(receipt_path)] = contract.sha(receipt_path); pins[str(candidate)] = contract.sha(candidate)
    stock_paths = {}
    proof = None
    if contract.rig_mode(target) == 'stock-exact':
        proof_path = Path(target['rig']['stockReferenceReceipt']['path']).resolve()
        proof = json.loads(proof_path.read_text()); pins[str(proof_path)] = contract.sha(proof_path)
    for part, value in config['stockParts'].items():
        source = pinned(value)
        expected_model = target['rig']['sourcePrefix'] + '_' + part + '001' if proof else target['models'][part]
        declaration = re.search(r'(?mi)^newmodel\s+(\S+)', source.read_text(encoding='cp1252'))
        contract.require(declaration is not None and declaration[1].lower() == expected_model, 'Cross-family stock head/neck source')
        if proof:
            originals=[Path(name) for name,digest in proof['frozenInputs'].items() if Path(name).name == expected_model+'.mdl' and Path(name).parent.name == 'ascii' and digest == value['sha256']]
            contract.require(len(originals)==1, 'Head/neck source is absent from the stock rig proof')
            pins[str(originals[0])]=contract.sha(originals[0])
        stock_paths[part] = source; pins[str(source)] = contract.sha(source)
    poses = []; labels = {'bind'}
    for item in config.get('poses', []):
        label = item['state']; contract.require(re.fullmatch(r'[a-z0-9-]+', label) is not None and label not in labels, 'Unique stable connector pose state required'); labels.add(label)
        comparison = pinned(item['comparison']); poses.append((label, comparison)); pins[str(comparison)] = contract.sha(comparison)
    regions = validate_regions(config['regions'])
    return config, target_path, target, source_paths, stock_paths, poses, regions, pins


def validate_regions(regions):
    contract.require(set(regions) == {'neckChestSurface', 'shoulderTerminalCaps', 'upperArmProximalCaps', 'neckCapFaces'}, 'Explicit measured connector regions required')
    neck = regions['neckChestSurface']; shoulders = regions['shoulderTerminalCaps']; arm = regions['upperArmProximalCaps']
    contract.require(set(neck) == {'absoluteXMaximum', 'bindZMinimum'} and np.isfinite(list(neck.values())).all() and neck['absoluteXMaximum'] > 0, 'Finite neck/chest surface region required')
    contract.require(set(shoulders) == {'left', 'right'}, 'Bilateral terminal chest regions required')
    for side, item in shoulders.items():
        contract.require(set(item) == {'lateralMinimum', 'bindZInterval', 'outwardNormalMinimumDot'}, 'Explicit terminal chest region limits required')
        interval = np.asarray(item['bindZInterval'], float)
        contract.require(interval.shape == (2,) and np.isfinite(interval).all() and interval[0] < interval[1] and np.isfinite(item['lateralMinimum']) and item['lateralMinimum'] > 0 and 0 <= item['outwardNormalMinimumDot'] <= 1, 'Invalid terminal chest region')
    contract.require(set(arm) == {'axialIntervalMetres', 'oppositeShaftNormalMinimumDot'}, 'Explicit arm cap region limits required')
    interval = np.asarray(arm['axialIntervalMetres'], float)
    contract.require(interval.shape == (2,) and np.isfinite(interval).all() and interval[0] < interval[1] and 0 <= arm['oppositeShaftNormalMinimumDot'] <= 1, 'Invalid arm proximal region')
    contract.require(type(regions['neckCapFaces']) is int and regions['neckCapFaces'] >= 3, 'Measured stock neck apex face count required')
    return regions


def verify_pose(specimen, target_path, target, receipts, stock_paths, pins):
    contract.verify_binding(specimen['target'], target_path, target, 'working')
    contract.require(specimen['displayScale'] == 1, 'Display scaling unsupported')
    for part, receipt in receipts.items():
        selected = [row for row in specimen['targetPartReceipts'] if row['part'] == part]
        contract.require(len(selected) == 1 and selected[0]['candidateSha256'] == receipt['candidateSha256'], 'Comparison uses a different part candidate')
    for source in stock_paths.values():
        matches=[Path(name).resolve() for name,digest in specimen['partInputs'].items() if Path(name).name == source.name and digest == pins[str(source)]]
        contract.require(len(matches)==1, 'Comparison stock geometry differs')
        contract.require(contract.sha(matches[0]) == pins[str(source)], 'Comparison stock source changed')
        pins[str(matches[0])]=pins[str(source)]
