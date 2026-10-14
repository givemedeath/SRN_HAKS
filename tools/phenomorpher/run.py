"""Managed repository entry point: declare consumed inputs, dispatch once, verify afterward."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def consumed(arguments):
    sys.path.insert(0, str(HERE))
    from phenomorpher.inputs import consumed as data_inputs
    files = set((HERE/'phenomorpher').rglob('*.py')) | {HERE/'run.py', HERE/'source-lineage.json'}
    files.update((HERE/'phenomorpher').rglob('*.json'))
    return files | data_inputs(arguments)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--migration-receipt', type=Path, required=True)
    parser.add_argument('--launch-output', type=Path, required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    inputs = sorted(str(p) for p in consumed(arguments))
    for p in inputs:
        if not Path(p).is_file():
            raise ValueError('Missing declared input: '+p)
    # Keep helper/input declaration outside the launch directory, which must be fresh.
    parent = args.launch_output.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', prefix='pheno-inputs-',
                                      dir=parent, encoding='utf-8', delete=False) as stream:
        json.dump(inputs, stream); declaration = Path(stream.name)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONPATH=str(HERE),
               OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', MKL_NUM_THREADS='4')
    launcher = REPO/'tools/phenotypes/launch_shared_tool.py'
    result = subprocess.run([sys.executable, '-B', str(launcher), '--toolchain', str(args.toolchain),
        '--migration-receipt', str(args.migration_receipt), '--tool', 'python',
        '--output', str(args.launch_output), '--input-path-list', str(declaration),
        '--', '-B', '-m', 'phenomorpher', *arguments], env=env, check=False)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
