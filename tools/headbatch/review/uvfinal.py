"""Measure the final face-priority layout for one failed unwrap. Writes diagnostic evidence only."""
import argparse
from pathlib import Path
import re

import numpy as np
from PIL import Image

from headkit.common import pin, read, require, verify, write
from headkit.diagnostics import sheet
from headkit.gltf import mesh
from headkit.runner import Runner
from headkit.uv import unwrap


def probe(head, attempt, output):
    head = head.resolve()
    require(re.fullmatch(r'attempt-[0-9]+', attempt), 'Name the failed unwrap attempt')
    require(output.resolve().is_relative_to(head/'review-evidence'), 'Use a fresh head review-evidence folder')
    runner = Runner(head/'manifest.json', head/'bindings.json', head/'run')
    failed = pin(head/'run/unwrap'/attempt/'receipt.json')
    data = read(failed['path'])
    require(data['state'] == 'failed' and data['error'].startswith('Insufficient useful UV coverage ('),
            'Expected a pre-face-priority coverage failure')
    require(data['manifestHash'] == runner.manifest_digest('unwrap') and
            data['dependencies']['repair'] == runner.state['stages']['repair'], 'Unwrap policy or repair changed')
    source = runner.result('repair')['source']
    pins = [failed, source, data['dependencies']['repair'], pin(runner.manifest_path), pin(runner.bindings_path)]
    verify(pins, fresh=True)
    mesh_policy = runner.data['mesh']
    policy = dict(mesh_policy['uv'], maximumSubtexelFraction=mesh_policy.get('maximumSubtexelFraction', .005))
    require(policy.get('faceDensity', 1) > 1, 'A face-priority layout is required')
    output.mkdir(parents=True, exist_ok=False)
    layouts = {}
    tiles = {}

    def observe(label, owners, metrics, subtexel, charts, face):
        hit = owners >= 0
        colored = np.full((*owners.shape, 3), 31, np.uint8)
        palette = np.array([[138, 195, 194], [86, 146, 167], [158, 175, 217], [194, 186, 148]])
        colored[hit] = palette[charts[owners[hit]] % len(palette)]
        coverage = metrics['2048']['coverageFraction']
        tiles[label] = (f'{label}  |  {coverage:.2%} at 2K  |  {attempt}',
                        Image.fromarray(colored).resize((480, 480), Image.Resampling.BOX))
        layouts[label] = {'coverage2K': coverage, 'chartCount': int(np.unique(charts).size),
                          'overlapFaces': {s: len(m['overlapFaces']) for s, m in metrics.items()},
                          'subtexel': {s: {k: v for k, v in m.items() if k != 'failingFaces'}
                                       for s, m in subtexel.items()}, 'facePriority': face}

    report = {'attempt': attempt, 'pins': pins, 'policy': policy, 'coverageFloor': policy.get('minimumCoverage', .30),
              'layouts': layouts, 'productionAttempt': False, 'approved': False}
    value = mesh(source['path'])
    original = value['positions'][value['faces']].copy()
    try:
        unwrapped, result = unwrap(value, runner.bindings, policy, inspect_layout=observe)
        require(np.array_equal(original, unwrapped['positions'][unwrapped['faces']]), 'UV processing changed ordered geometry')
        audited = result['pixelAudits']['4096']
        require(not any(audited[k] for k in ('unmappedUvFaces', 'overlapFaces', 'degenerateUvFaces')), '4K UV audit failed')
    except ValueError as error:
        report.update(passedFinalChecks=False, error=str(error))
    else:
        report.update(passedFinalChecks=True, gutters=result['gutters'])
    verify(pins, fresh=True)
    if tiles:
        path = output/'sheet.png'
        sheet(list(tiles.values()), path, 480, columns=len(tiles))
        report['sheet'] = pin(path)
    write(output/'measurement.json', report, fresh=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('head', type=Path)
    p.add_argument('attempt')
    p.add_argument('output', type=Path)
    args = p.parse_args()
    result = probe(args.head, args.attempt, args.output)
    print(args.output/'measurement.json', result.get('error', 'passed final checks'))
