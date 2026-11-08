"""Verify a native-sized export against its reviewed fit and pinned Troll policy."""
from pathlib import Path
import sys

from headbatch.head_files import fit_matrix, read
from headkit.common import require, sha
from headkit.native import troll_build_allowance


def check(head, attempt):
    head = Path(head)
    manifest = read(head/'manifest.json')
    result = read(head/'run'/'export'/attempt/'receipt.json')['result']
    require(manifest.get('nativeSizing') == 'troll-build-allowance-r3', 'Unknown native sizing rule')
    paths = []
    for role in ('nativeSizingPolicy', 'fitReference'):
        record = manifest['inputs'][role]
        path = head/record['path']
        require(sha(path) == record['sha256'], 'Native sizing input changed: '+role)
        paths.append(path)
    sizing = troll_build_allowance(*paths, manifest['fit']['model'])
    require(result.get('nativeSizing') == sizing, 'Export has a different allowance or reference')
    matrix = fit_matrix(head)
    expected = [[v*sizing['scale'] for v in row] if i < 3 else row for i, row in enumerate(matrix)]
    require(result['matrix'] == expected, 'Export differs from the uniformly scaled reviewed fit')


if __name__ == '__main__':
    check(*sys.argv[1:])
