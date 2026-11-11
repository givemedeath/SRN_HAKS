"""Command line for envkit. `crops` writes every crop of a set for a look; `reference` redraws assets on the bound ComfyUI."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.envkit'

from . import reference


def command_crops(args):
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    rows = {name: str(reference.crop(sheet, asset['box'], Path(args.output) / f'{name}.png'))
            for name, asset in data['assets'].items() if not args.asset or name in args.asset}
    print(json.dumps(rows, indent=1))


def command_reference(args):
    from ..headkit.comfy import Client
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    unknown = [name for name in args.asset if name not in data['assets']]
    reference.require(not unknown, 'Unknown assets: ' + ', '.join(unknown))
    local = json.loads(Path(args.bindings).read_text(encoding='utf-8')); client = Client(args.url); output = Path(args.output)
    for name in args.asset or list(data['assets']):
        asset = data['assets'][name]
        source = reference.crop(sheet, asset['box'], output / 'crops' / f'{name}.png')
        text = reference.prompt(asset['kind'], asset['subject'], asset.get('notes', ''))
        result = reference.make(client, local, args.bindings, name, text, source, args.seed, output, deadline=args.deadline)
        print(json.dumps({'asset': name, 'state': result['state'], 'outputs': result['outputs'],
                          'elapsedSeconds': result['elapsedSeconds']}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='envkit')
    commands = parser.add_subparsers(dest='command', required=True)
    parsers = {}
    for name, run in (('crops', command_crops), ('reference', command_reference)):
        sub = parsers[name] = commands.add_parser(name)
        sub.add_argument('--set', required=True, help='set file naming the sheet and each asset crop')
        sub.add_argument('--sheets', required=True, help='folder holding the concept sheets')
        sub.add_argument('--output', required=True)
        sub.add_argument('--asset', action='append', default=[], help='limit to these assets (repeatable)')
        sub.set_defaults(run=run)
    sub = parsers['reference']
    sub.add_argument('--bindings', required=True, help='local JSON with absolute comfyInput and comfyOutput')
    sub.add_argument('--url', default='http://127.0.0.1:8188')
    sub.add_argument('--seed', type=int, default=101)
    sub.add_argument('--deadline', type=int, default=2400)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
