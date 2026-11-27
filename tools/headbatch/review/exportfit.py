"""Verify a sized export against its reviewed fit, the pinned Troll allowance and the race head standard."""
from pathlib import Path
import sys

import numpy as np

from headbatch.head_files import fit_matrix, read
from headkit.common import require, sha
from headkit.native import troll_build_allowance
from headkit.race_sizing import config, factor, fit_align, standard


def pinned(head, manifest, role):
    record = manifest['inputs'][role]
    path = head/record['path']
    require(sha(path) == record['sha256'], 'Sizing input changed: '+role)
    return path


def check(head, attempt):
    head = Path(head)
    manifest = read(head/'manifest.json')
    result = read(head/'run'/'export'/attempt/'receipt.json')['result']
    model = manifest['fit']['model']
    require(manifest.get('nativeSizing') in (None, 'troll-build-allowance-r3'), 'Unknown native sizing rule')
    require(manifest.get('nativeSizing') or manifest.get('raceSizing'), 'No sizing rule to check')
    matrix = np.asarray(fit_matrix(head), float)
    if manifest.get('nativeSizing'):
        sizing = troll_build_allowance(pinned(head, manifest, 'nativeSizingPolicy'), pinned(head, manifest, 'fitReference'), model)
        require(result.get('nativeSizing') == sizing, 'Export has a different allowance or reference')
        matrix[:3, :] *= sizing['scale']
    else:
        require('nativeSizing' not in result, 'Export carries an allowance the manifest does not declare')
    if manifest.get('raceSizing'):
        policy = pinned(head, manifest, 'raceHeadStandard')
        race = result.get('raceSizing')
        require(isinstance(race, dict) and race['policy']['sha256'] == manifest['inputs']['raceHeadStandard']['sha256'],
                'Export used a different race head standard')
        _, row = standard(policy, model)
        scale, _ = factor(row, config(manifest['raceSizing']), fit_align(manifest['fit']),
                          pinned(head, manifest, 'fitReference'), model[:4])
        pivot = np.asarray(race['pivot'], float)
        require(race['scale'] == scale and race['pivotRule'] == row['pivot'] and pivot[0] == pivot[1] == 0
                and (row['pivot'] == 'chin' and scale != 1 or pivot[2] == 0), 'Export has a different race scale or pivot')
        move = np.eye(4); move[:3, :3] *= scale; move[:3, 3] = (1-scale)*pivot
        matrix = move @ matrix
    else:
        require('raceSizing' not in result, 'Export carries race sizing the manifest does not declare')
    require(np.allclose(result['matrix'], matrix, rtol=0, atol=1e-9), 'Export differs from the uniformly scaled reviewed fit')


if __name__ == '__main__':
    check(*sys.argv[1:])
