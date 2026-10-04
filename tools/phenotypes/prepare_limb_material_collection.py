"""Collect explicitly selected raw limb stages and measured skin offsets.

Only new limbs are owned here. Accepted body materials never enter this operation.
The output is an ASCII/material collection for the separate AO/roughness bake.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct

import numpy as np

from adjust_pelvis_skin_plt import adjust_plt
from stage_stock_part import require, sha, save
from stock_limb_contract import ATTACHMENTS, PAIRS

NEW_PARTS = {'bicepl', 'bicepr', 'forel', 'forer', 'handl', 'handr', 'footl', 'footr'}


def skin_offset(data, offset):
    """Prove both clipping directions without altering header/material ownership."""
    require(type(offset) is int, 'Explicit integer shade offset required')
    payload, before, after, clamped = adjust_plt(data, offset)
    skin = before[:, :, 1] == 0
    raw = before[:, :, 0].astype(np.int16) + offset
    require(np.any(skin), 'No skin pixels to calibrate')
    require(np.array_equal(after[:, :, 1], before[:, :, 1])
            and np.array_equal(after[~skin], before[~skin]), 'Material ownership changed')
    expected = before.copy()
    expected[:, :, 0][skin] = np.clip(raw[skin], 0, 255).astype(np.uint8)
    require(np.array_equal(expected, after) and payload[:24] == data[:24], 'Incorrect shade transport')
    return payload, {'offset': offset, 'skinPixels': int(skin.sum()),
        'changedShadePixels': int(np.count_nonzero(before[:, :, 0] != after[:, :, 0])),
        'lowClampedPixels': int(np.count_nonzero(skin & (raw < 0))),
        'highClampedPixels': int(np.count_nonzero(skin & (raw > 255))),
        'clampedPixels': int(clamped.sum()), 'layersExact': True, 'nonSkinPixelsExact': True,
        'skinMeanBefore': float(before[:, :, 0][skin].mean()),
        'skinMeanAfter': float(after[:, :, 0][skin].mean())}


def selected_parts(parts):
    require(set(parts) <= NEW_PARTS and len(parts) == len(set(parts)) and parts,
            'Only explicitly selected new limb stages may enter this collection')
    for pair in PAIRS:
        overlap = set(pair) & set(parts)
        require(not overlap or overlap == set(pair), 'Collect complete mirrored pairs')


def collect(config_path, output):
    config_path = Path(config_path).resolve(); output = Path(output).resolve()
    config = json.loads(config_path.read_text())
    require(config.get('schemaVersion') == 1 and config.get('kind') == 'new-limb-skin-calibration',
            'Explicit new-limb calibration required')
    rows = config['stages']; selected_parts([r['part'] for r in rows])
    inputs = {str(config_path): sha(config_path), str(Path(__file__).resolve()): sha(__file__)}
    inputs[str(Path(__file__).with_name('adjust_pelvis_skin_plt.py').resolve())] = sha(
        Path(__file__).with_name('adjust_pelvis_skin_plt.py'))
    for path, pin in config['calibrationInputs'].items():
        require(sha(path) == pin, 'Measured calibration input changed: '+path); inputs[path] = pin
    prepared = []
    for row in rows:
        stage = Path(row['stage']).resolve(); receipt_path = stage/'stock-part-stage.json'
        require(sha(receipt_path) == row['stageReceiptSha256'], 'Selected raw stage changed')
        receipt = json.loads(receipt_path.read_text()); cfg = receipt['configuration']
        model = 'pmh0_'+row['part']+'001'
        require(cfg['part'] == row['part'] and cfg['model'] == model and cfg['joint'] == ATTACHMENTS[row['part']]
                and cfg['stockHeightMeters'] == 1.9339157 and cfg['equipmentMode'] == 'stock-identity'
                and cfg['normalStrength'] == 1 and cfg['skinLayer'] == 0, 'Stock stage policy differs')
        require(receipt['nativeCompiled'] is False and receipt['stockControllersModified'] is False,
                'Untouched raw limb stage required')
        require(row['calibrationReceipt'] in config['calibrationInputs'] and row['rationale'].strip(),
                'Pin and explain the actual adjoining-map calibration')
        for path, pin in receipt['frozenInputs'].items():
            require(sha(path) == pin, 'Raw stage ancestor changed: '+path); inputs[path] = pin
        for relative, pin in receipt['stagedFiles'].items():
            path = (stage/relative).resolve()
            require(path.is_relative_to(stage) and sha(path) == pin, 'Raw stage payload changed: '+relative)
            inputs[str(path)] = pin
        for ancestor in cfg['sourceReceiptLineage']:
            for path_key, pin_key in [('receipt', 'receiptSha256'), ('candidate', 'candidateSha256')]:
                require(sha(ancestor[path_key]) == ancestor[pin_key], 'Fit ancestry changed')
                inputs[ancestor[path_key]] = ancestor[pin_key]
        converted = stage/cfg['slug']/'converted'
        resource_names = {model+'.plt', model+'.mtr', model+'n.tga'}
        require({p.name for p in (converted/'resources').iterdir()} == resource_names
                and {p.name for p in (converted/'ascii').iterdir()} == {model+'.mdl'}, 'Undeclared raw resource')
        require(sha(converted/'resources'/(model+'.plt')) == row['originalPltSha256'], 'Raw palette changed')
        require(cfg['expectedInputHashes']['source'] == sha(cfg['source']), 'Selected geometry changed')
        inputs[str(receipt_path)] = sha(receipt_path)
        payload, proof = skin_offset((converted/'resources'/(model+'.plt')).read_bytes(), row['shadeOffset'])
        require(struct.unpack_from('<II',payload,16)==(2048,2048)
                and proof['skinPixels'] == 2048*2048, 'Expected new 2K skin-only atlas')
        prepared.append((row, cfg, converted, payload, proof))
    require(not output.exists(), 'Fresh calibrated collection required')
    resources = output/'body-resources'; ascii_dir = output/'ascii'
    resources.mkdir(parents=True); ascii_dir.mkdir()
    changes = {}; selected = {}; origins = {}
    for row, cfg, converted, payload, proof in prepared:
        model = cfg['model']
        for path in (converted/'resources').iterdir(): shutil.copyfile(path, resources/path.name)
        source_ascii = converted/'ascii'/(model+'.mdl')
        shutil.copyfile(source_ascii, ascii_dir/source_ascii.name)
        shutil.copyfile(source_ascii, resources/source_ascii.name)
        (resources/(model+'.plt')).write_bytes(payload)
        selected[row['part']] = {'path': cfg['source'], 'sha256': cfg['expectedInputHashes']['source']}
        changes[row['part']] = {'model': model, 'sourcePltSha256': row['originalPltSha256'],
            'effectivePltSha256': sha(resources/(model+'.plt')), 'proof': proof,
            'calibrationReceipt': row['calibrationReceipt'], 'rationale': row['rationale'],
            'geometryUvNormalsAndNormalMapExact': True}
        origins[row['part']] = {'stage': row['stage'], 'stageReceiptSha256': row['stageReceiptSha256']}
    hashes = {p.name: sha(p) for p in sorted(resources.iterdir())}
    require(len(hashes) == 4*len(rows), 'Unexpected collected resources')
    for path, pin in inputs.items(): require(sha(path) == pin, 'Input changed during calibration: '+path)
    shutil.copyfile(__file__, output/'executed-collector.py')
    save(output/'body-resource-manifest.json', {'schemaVersion': 1, 'resources': hashes,
        'selectedGeometry': selected, 'stageOrigins': origins, 'nativeCompiled': False,
        'preservedNeighbourResourcesIncluded': False})
    save(output/'skin-calibration.json', {'schemaVersion': 1, 'kind': config['kind'],
        'frozenInputs': inputs, 'parts': changes, 'normalStrength': 1,
        'aoAlreadyBaked': False, 'nativeCompilerExecuted': False, 'clientAccepted': False})
    print(json.dumps({'output': str(output), 'parts': changes}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); collect(a.config, a.output)
