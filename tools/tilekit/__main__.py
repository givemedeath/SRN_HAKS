"""Command line for tilekit. `inventory` writes what a tileset draws (inventory.json, textures.csv) and the hashes of
its walkmeshes (walkmesh.json); `walkmesh` holds the tileset's walkmeshes against such a baseline and fails on any
that changed."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.tilekit'

from . import inventory

REPO = Path(__file__).resolve().parents[2]


def main(arguments=None):
    parser = argparse.ArgumentParser(prog='tilekit', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    one = commands.add_parser('inventory', help='write the inventory and walkmesh baseline of a tileset')
    one.add_argument('--tileset', required=True); one.add_argument('--out', required=True, type=Path); one.add_argument('--repo', type=Path, default=REPO)
    two = commands.add_parser('walkmesh', help='compare the walkmeshes of a tileset with a baseline')
    two.add_argument('--tileset', required=True); two.add_argument('--baseline', required=True, type=Path); two.add_argument('--repo', type=Path, default=REPO)
    chosen = parser.parse_args(arguments)
    try:
        told, walkmesh = inventory.inventory(chosen.repo, chosen.tileset.lower())
        if chosen.command == 'inventory':
            written = inventory.write(chosen.out, told, walkmesh)
            print(json.dumps({'written': written, 'set': told['set'], 'edge': told['edge'], 'forms': told['forms'], 'textures': len(told['textures']),
                              'surface': told['surface'], 'coverage': told['coverage']}, indent=2))
            return 0
        lines = inventory.moved(json.loads(chosen.baseline.read_text(encoding='utf-8')), walkmesh)
        print('\n'.join(lines) if lines else f"{len(walkmesh['models'])} walkmeshes as the baseline has them")
        return 1 if lines else 0
    except ValueError as error:
        print(f'tilekit: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
