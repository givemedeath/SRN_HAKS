"""Retarget one race and gender for the shared-library release layout (Phase 9, additive).

retarget.py (v1, lineage-pinned) gives every body its own carrier chain and bases Large on
a_fa2/a_ba2 with Large-scaled keys, so Fit and Large motion differ and cannot share a library.
v2 fits the motion once, from the Fit body, over the stock a_fa (female) or a_ba (male) chain.
The Large root keeps its own fitted skeleton and names the same top carrier, so Fit and Large
have identical effective motion. The carriers are an unpublished intermediate: anim-library build
turns them into one shared library and adopt-runtime retires them.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

import numpy as np

from .retarget import NODE, geometry, nodes, rotation_signature, rotations, signature, transforms

KIND = 'PhenoMorpher-retarget-v2'


def at_origin(data, label):
    """Stock rigs keep the model root at the origin (the compiler drops root transforms); so do ours."""
    if np.linalg.norm(data['position']) > 1e-9 or np.abs(rotations(data['orientation']) - np.eye(3)).max() > 1e-9:
        raise RuntimeError(f'Model root must sit at the origin: {label} position {list(data["position"])}, '
                           f'orientation {list(data["orientation"])}')


def fitted_skeleton(report, baseline):
    """Stock Human skeleton of the same gender, scaled and fitted to the report's joints."""
    if not report.get('bindPoseNormalization'):
        raise RuntimeError('Normalize sliced generation geometry and joints to the stock bind pose before animation export')
    prefix = report['modelPrefix']; source_root = f'p{prefix[1]}h0'
    skeleton = nodes((baseline/'ascii'/(source_root + '.mdl')).read_text(encoding='cp1252'))
    old = {name: {**data, 'position': data['position'].copy()} for name, data in skeleton.items()}
    height_scale = report['height']/report.get('stockReferenceHeight', 2.0)
    targets = {k.lower(): np.array(v) for k, v in report['jointWorldNwn'].items()}
    targets['rootdummy'] = targets['torso_g']; targets['belt_g1'] = targets['torso_g']
    for name, data in skeleton.items():
        data['position'] *= height_scale
        if name == source_root:
            data['name'] = prefix
        if data['parent'] == source_root:
            data['parent'] = prefix
    skeleton[prefix] = skeleton.pop(source_root)
    for _ in range(len(skeleton)):
        moved = False; world = transforms(skeleton)
        for name, target in targets.items():
            if name not in skeleton:
                raise RuntimeError('Missing skeleton attachment: ' + name)
            local = (np.linalg.inv(world.get(skeleton[name]['parent'], np.eye(4))) @ np.r_[target, 1])[:3]
            if np.linalg.norm(local - skeleton[name]['position']) > 1e-9:
                skeleton[name]['position'] = local; moved = True
        if not moved:
            break
    world = transforms(skeleton)
    for name, target in targets.items():
        if np.linalg.norm(world[name][:3, 3] - target) > 1e-6:
            raise RuntimeError('Joint fitting did not converge: ' + name)
    at_origin(skeleton[prefix], prefix)
    return prefix, skeleton, old, height_scale, world


def carrier_chain(fit_report, baseline, output):
    """Carrier chain fitted to the Fit body over a_fa/a_ba; never the phenotype-2 stock chain."""
    prefix, skeleton, old, height_scale, _ = fitted_skeleton(fit_report, baseline)
    if prefix[3] != '0':
        raise RuntimeError('The motion source must be the Fit (phenotype 0) body: ' + prefix)
    stock = json.loads((baseline/'baseline.json').read_text(encoding='utf-8-sig'))
    top = 'a_fa' if prefix[1] == 'f' else 'a_ba'; chain = []; current = top
    while current != 'null':
        chain.append(current); current = stock['animations'][current]['supermodel']
    aliases = {name: f'sr_a{prefix[1:3]}_{i}' for i, name in enumerate(chain)}
    output.mkdir(parents=True, exist_ok=True); receipts = []
    for name in chain:
        original = (baseline/'ascii'/(name + '.mdl')).read_text(encoding='cp1252'); alias = aliases[name]
        old_geom = nodes(original); fitted = {}
        for key, data in old_geom.items():
            data = {**skeleton[key], 'position': skeleton[key]['position'].copy()} if key in old else {**data, 'position': data['position']*height_scale}
            if key == name:
                data['name'] = alias
            if data['parent'] in (name, prefix):
                data['parent'] = alias
            fitted[key] = data
        at_origin(fitted[name], alias)
        parent = aliases.get(stock['animations'][name]['supermodel'], 'NULL')
        header = f'newmodel {alias}\nsetsupermodel {alias} {parent}\nclassification CHARACTER\nsetanimationscale 1\n'
        tail = original.split('endmodelgeom', 1)[1].split('\n', 1)[1]
        def adjust_node(match):
            node_name = match[2].lower(); body = match[3]
            old_position = old_geom.get(node_name, old.get(node_name, {})).get('position', np.zeros(3))
            delta = fitted.get(node_name, {}).get('position', old_position*height_scale) - old_position*height_scale
            def keys(block):
                label, count, lines = block[1], int(block[2]), block[3].splitlines()
                if len(lines) != count:
                    raise RuntimeError('Unexpected position controller count')
                rows = []
                for line in lines:
                    values = [float(v) for v in line.split()]
                    if len(values) not in (4, 10):
                        raise RuntimeError('Unexpected position controller arity')
                    values[1:4] = np.array(values[1:4])*height_scale + delta
                    if len(values) == 10:
                        values[4:] = np.array(values[4:])*height_scale
                    rows.append('      ' + ' '.join(f'{v:.9g}' for v in values))
                return f'    {label} {count}\n' + '\n'.join(rows) + '\n'
            body = re.sub(r'(?m)^\s*(position(?:bezier)?key)\s+(\d+)\s*\n((?:[ \t]+[\d+\-\.eE]+[^\n]*\n)+)', keys, body)
            return f'  node {match[1]} {match[2]}\n{body}  endnode'
        tail = re.sub(r'(?i)\b' + re.escape(name) + r'\b', alias, NODE.sub(adjust_node, tail))
        result = header + geometry(alias, fitted, height_scale) + '\n' + tail
        if signature(result) != signature(original):
            raise RuntimeError('Animation names, timing, or events changed')
        if rotation_signature(result) != rotation_signature(original):
            raise RuntimeError('Stock animation rotation controllers changed')
        (output/(alias + '.mdl')).write_text(result, encoding='ascii', newline='\n')
        receipts.append({'source': name, 'target': alias, 'clips': len(signature(result))})
    return prefix, aliases[top], receipts, height_scale


def root_model(report, baseline, top, output):
    """A root with its own fitted skeleton that names the shared top carrier."""
    prefix, skeleton, _, height_scale, world = fitted_skeleton(report, baseline)
    output.mkdir(parents=True, exist_ok=True)
    (output/(prefix + '.mdl')).write_text(f'newmodel {prefix}\nsetsupermodel {prefix} {top}\nclassification CHARACTER\nsetanimationscale 1\n'
                                          + geometry(prefix, skeleton, height_scale) + f'\ndonemodel {prefix}\n', encoding='ascii', newline='\n')
    return {'model': prefix, 'supermodel': top, 'heightScale': height_scale, 'joints': {k: list(v[:3, 3]) for k, v in world.items()}}


def destinations(fit_report, baseline, fit_converted, large_converted=None):
    """Every file a run writes: carriers, roots and the receipt."""
    prefix = fit_report['modelPrefix']; stock = json.loads((baseline/'baseline.json').read_text(encoding='utf-8-sig'))
    current = 'a_fa' if prefix[1] == 'f' else 'a_ba'; count = 0
    while current != 'null':
        count += 1; current = stock['animations'][current]['supermodel']
    paths = [fit_converted/'ascii'/f'sr_a{prefix[1:3]}_{i}.mdl' for i in range(count)]
    paths += [fit_converted/'ascii'/(prefix + '.mdl'), fit_converted/'retarget-v2.json']
    if large_converted is not None:
        large = json.loads((large_converted/'conversion.json').read_text(encoding='utf-8-sig'))['modelPrefix']
        paths.append(large_converted/'ascii'/(large + '.mdl'))
    return paths


def retarget(fit_converted, baseline, large_converted=None):
    fit_report = json.loads((fit_converted/'conversion.json').read_text(encoding='utf-8-sig'))
    # Earlier results are evidence: refuse before writing anything rather than replace them.
    existing = [str(p) for p in destinations(fit_report, baseline, fit_converted, large_converted) if p.exists()]
    if existing:
        raise RuntimeError('Retarget output already exists: ' + ', '.join(existing))
    if fit_report['modelPrefix'][3] != '0':
        raise RuntimeError('The motion source must be the Fit (phenotype 0) body: ' + fit_report['modelPrefix'])
    report = json.loads((large_converted/'conversion.json').read_text(encoding='utf-8-sig')) if large_converted is not None else None
    if report is not None and (report['modelPrefix'][:3] != fit_report['modelPrefix'][:3] or report['modelPrefix'][3] != '2'):
        raise RuntimeError('Large body must share race and gender with the Fit body: ' + report['modelPrefix'])
    # Everything is generated in scratch folders first; nothing reaches a destination unless all of it succeeded.
    fit_scratch = Path(tempfile.mkdtemp(prefix='.retarget-v2-', dir=fit_converted))
    large_scratch = Path(tempfile.mkdtemp(prefix='.retarget-v2-', dir=large_converted)) if report is not None else None
    try:
        prefix, top, carriers, scale = carrier_chain(fit_report, baseline, fit_scratch/'ascii')
        roots = [root_model(fit_report, baseline, top, fit_scratch/'ascii')]
        if report is not None:
            roots.append(root_model(report, baseline, top, large_scratch/'ascii'))
        receipt = {'schemaVersion': 1, 'kind': KIND, 'motionSource': prefix, 'stockTop': 'a_fa' if prefix[1] == 'f' else 'a_ba',
                   'topCarrier': top, 'carriers': carriers, 'roots': roots, 'motionHeightScale': scale,
                   'fitLargeShareMotion': True, 'carriersPublished': False, 'timingEventsUnchanged': True,
                   'rotationControllersUnchanged': True, 'engineObserved': False, 'assetApprovalCreated': False}
        (fit_scratch/'retarget-v2.json').write_text(json.dumps(receipt, indent=1) + '\n', encoding='utf-8', newline='\n')
        moves = [(p, fit_converted/p.relative_to(fit_scratch)) for p in sorted(fit_scratch.rglob('*')) if p.is_file()]
        if large_scratch is not None:
            moves += [(p, large_converted/p.relative_to(large_scratch)) for p in sorted(large_scratch.rglob('*')) if p.is_file()]
        if sorted(str(d) for _, d in moves) != sorted(str(p) for p in destinations(fit_report, baseline, fit_converted, large_converted)):
            raise RuntimeError('Retarget outputs differ from the preflighted destinations')
        # The receipt moves last, so its presence means every model is in place.
        moves.sort(key=lambda m: m[1].name == 'retarget-v2.json')
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True); os.replace(source, target)
    finally:
        shutil.rmtree(fit_scratch, ignore_errors=True)
        if large_scratch is not None:
            shutil.rmtree(large_scratch, ignore_errors=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit-converted', type=Path, required=True)
    parser.add_argument('--large-converted', type=Path)
    parser.add_argument('--baseline', type=Path, default=Path('output/phenotypes/baseline'))
    args = parser.parse_args()
    receipt = retarget(args.fit_converted, args.baseline, args.large_converted)
    print(json.dumps({k: receipt[k] for k in ('motionSource', 'topCarrier', 'fitLargeShareMotion')}))


if __name__ == '__main__':
    main()
