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


def command_meshy(args):
    from . import meshy
    if args.action == 'init':
        meshy.Ledger.create(args.ledger, args.cap)
    ledger = meshy.Ledger(args.ledger)
    if args.action in ('prop', 'building', 'remesh'):
        arguments = (meshy.prop_arguments(args.image[0], args.triangles) if args.action == 'prop' else
                     meshy.building_arguments(args.image) if args.action == 'building' else
                     meshy.remesh_arguments(ledger.entry(args.source)['taskId'], args.triangles))
        print(json.dumps({'key': args.key, 'task': meshy.submit(ledger, args.key, args.asset, args.action, arguments, args.work)}))
    elif args.action == 'wait':
        print(json.dumps(meshy.wait(ledger, args.key, args.work)))
    elif args.action == 'download':
        print(json.dumps(meshy.download(ledger, args.key, args.work, args.bank)))
    rows = [{k: row.get(k) for k in ('key', 'asset', 'operation', 'state', 'estimate', 'credits', 'taskId')} for row in ledger.data['entries']]
    print(json.dumps({'cap': ledger.data['cap'], 'committed': ledger.committed(), 'entries': rows if args.action == 'status' else len(rows)}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='envkit')
    commands = parser.add_subparsers(dest='command', required=True)
    sub = commands.add_parser('meshy', help='paid Meshy calls under the ledger cap')
    sub.add_argument('action', choices=['init', 'status', 'prop', 'building', 'remesh', 'wait', 'download'])
    sub.add_argument('--ledger', required=True)
    sub.add_argument('--cap', type=int)
    sub.add_argument('--key', help='ledger key of this call')
    sub.add_argument('--asset')
    sub.add_argument('--image', action='append', default=[], help='reference image (repeat for building views)')
    sub.add_argument('--triangles', type=int, help='prop target, or remesh ceiling')
    sub.add_argument('--source', help='remesh: ledger key of the generation to remesh')
    sub.add_argument('--work', help='folder for CLI transcripts and task records')
    sub.add_argument('--bank', help='download: fresh folder for the model')
    sub.set_defaults(run=command_meshy)
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
