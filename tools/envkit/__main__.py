"""Command line for envkit. `crops` writes every crop of a set for a look; `reference` redraws assets on the bound ComfyUI;
`game` converts generated models to compiled placeables."""
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


def command_game(args):
    """Convert generated models to compiled game placeables, as the game set states them."""
    from .. import shared_tools
    from ..armorkit import export
    from . import convert
    models = convert.load_models(args.models); root, output = Path(args.root), Path(args.output)
    unknown = [name for name in args.model if name not in models]
    reference.require(not unknown, 'Unknown models: ' + ', '.join(unknown))
    crunch = shared_tools.resolve_tool('crunch', Path(__file__).resolve().parents[2])['path']
    for name in args.model or list(models):
        model, folder = models[name], output / name
        reference.require(not folder.exists(), 'A model is converted into a fresh folder: ' + str(folder))
        source = root / model['source']
        maps = {key: source / f'texture_0_{key}.png' for key in ('base_color', 'normal', 'metallic', 'roughness')}
        report = convert.placeable(name, source / 'model.glb', maps, folder / 'source', crunch, height=model['height'],
                                   colour=model.get('colour', 1024), sign_tilt=model.get('signTilt'), lit=model.get('lit'), halo=model.get('halo'))
        report['compiled'] = {path.name: path.stat().st_size for path in export.compile_models([folder / 'source' / f'{name}.mdl'], folder / 'compiled')}
        (folder / 'report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(report), flush=True)


def command_tiles(args):
    """Build a model's tile group: tile models (compiled), walkmeshes and the shared material and maps."""
    from .. import shared_tools
    from . import convert, tile
    models = convert.load_models(args.models); root, folder = Path(args.root), Path(args.output) / args.model
    reference.require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    reference.require(not folder.exists(), 'A group is built into a fresh folder: ' + str(folder))
    model = models[args.model]; source = root / model['source']
    maps = {key: source / f'texture_0_{key}.png' for key in ('base_color', 'normal', 'metallic', 'roughness')}
    made = convert.shape(source / 'model.glb', maps, height=model['height'], colour=model.get('colour', 1024), sign_tilt=model.get('signTilt'),
                         lit=model.get('lit'), halo=model.get('halo'))
    report = tile.group(args.model, made, folder / 'source', ground=model['tiles']['ground'])
    compiled = tile.compile_tiles([folder / 'source' / f'{one["model"]}.mdl' for one in report['tiles']], folder / 'compiled')
    files = convert.skin(args.model, maps, folder / 'shared', shared_tools.resolve_tool('crunch', Path(__file__).resolve().parents[2])['path'], made,
                         colour=model.get('colour', 1024))
    report.update({'name': args.model, 'compiled': {path.name: path.stat().st_size for path in compiled}, 'textures': {path.name: path.stat().st_size for path in files}})
    (folder / 'report.json').write_text(json.dumps(report, indent=1) + chr(10), encoding='utf-8')
    print(json.dumps(report), flush=True)


def command_install(args):
    """Put a built tile group into the packs: its files into the shared pack, its records into each tileset named."""
    import shutil
    from . import convert, tile
    models = convert.load_models(args.models); built = Path(args.built) / args.model; repo = Path(args.repo)
    reference.require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    made = json.loads((built / 'report.json').read_text(encoding='utf-8')); tiles = models[args.model]['tiles']; shared = repo / args.pack
    reference.require(shared.is_dir() and all((repo / f'srn_t_{name}' / f'{name}.set').is_file() for name in tiles['sets']), 'A pack or set file named is missing')
    # Every tileset is worked out before anything is copied or written, so a refusal on one leaves none half done.
    prepared = {name: tile.prepare(repo / f'srn_t_{name}' / f'{name}.set', repo / f'srn_t_{name}' / f'{name}palstd.itp', made, terrain=terrain,
                                   group_name=tiles['group'], label=tiles['label']) for name, terrain in tiles['sets'].items()}
    copied = []
    for one in made['tiles']:
        copied += [shutil.copyfile(built / 'compiled' / f'{one["model"]}.mdl', shared / f'{one["model"]}.mdl'),
                   shutil.copyfile(built / 'source' / f'{one["model"]}.wok', shared / f'{one["model"]}.wok')]
    # The lights-out materials serve a placeable a script can reach; no script reaches a tile, so they stay behind.
    idle = (args.model + '_o', convert.HALO_OUT)
    copied += [shutil.copyfile(path, shared / path.name) for path in sorted((built / 'shared').iterdir()) if path.stem not in idle]
    placed = {name: tile.commit(one) for name, one in prepared.items()}
    print(json.dumps({'files': len(copied), 'sets': placed}), flush=True)


def command_placeables(args):
    """Put converted models into the placeable pack and give each a row in the placeables table."""
    import shutil
    from . import convert, placeables
    models = convert.load_models(args.models); built, repo = Path(args.built), Path(args.repo); pack, table = repo / args.pack, repo / args.table
    unknown = [name for name in args.model if not models.get(name, {}).get('placeable')]
    reference.require(not unknown, 'The game set gives these no placeable row: ' + ', '.join(unknown))
    chosen = {name: model['placeable'] for name, model in models.items() if model.get('placeable') and (not args.model or name in args.model)}
    reference.require(chosen and pack.is_dir() and table.is_file(), 'No model to register, or the pack or table is missing')
    missing = [name for name in chosen if not (built / name / 'compiled' / f'{name}.mdl').is_file()]
    reference.require(not missing, 'Convert these first (envkit game): ' + ', '.join(missing))
    text, rows = placeables.register(table.read_bytes().decode('cp1252'), [{'model': name, **placed} for name, placed in chosen.items()])
    copied = 0
    for name in chosen:
        shutil.copyfile(built / name / 'compiled' / f'{name}.mdl', pack / f'{name}.mdl'); copied += 1
        for path in sorted((built / name / 'source').iterdir()):
            if path.suffix in ('.pwk', '.mtr', '.dds', '.txi'):
                shutil.copyfile(path, pack / path.name); copied += 1
    table.write_bytes(text.encode('cp1252'))
    print(json.dumps({'rows': rows, 'files': copied}), flush=True)


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
    elif args.action in ('download', 'master'):
        print(json.dumps(meshy.download(ledger, args.key, args.work, args.bank, master=args.action == 'master')))
    rows = [{k: row.get(k) for k in ('key', 'asset', 'operation', 'state', 'estimate', 'credits', 'taskId')} for row in ledger.data['entries']]
    print(json.dumps({'cap': ledger.data['cap'], 'committed': ledger.committed(), 'entries': rows if args.action == 'status' else len(rows)}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='envkit')
    commands = parser.add_subparsers(dest='command', required=True)
    sub = commands.add_parser('meshy', help='paid Meshy calls under the ledger cap')
    sub.add_argument('action', choices=['init', 'status', 'prop', 'building', 'remesh', 'wait', 'download', 'master'])
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
    sub = commands.add_parser('game', help='convert generated models to compiled placeables')
    sub.add_argument('--models', required=True, help='game set file: each model source, height and lit parts')
    sub.add_argument('--root', required=True, help="the set's output root, holding the generated models")
    sub.add_argument('--output', required=True, help='folder that takes one fresh folder per model')
    sub.add_argument('--model', action='append', default=[], help='limit to these models (repeatable)')
    sub.set_defaults(run=command_game)
    sub = commands.add_parser('tiles', help='build a model as a tile group')
    sub.add_argument('--models', required=True); sub.add_argument('--root', required=True); sub.add_argument('--output', required=True)
    sub.add_argument('--model', required=True)
    sub.set_defaults(run=command_tiles)
    sub = commands.add_parser('install', help='put a built tile group into the shared pack and its tilesets')
    sub.add_argument('--models', required=True); sub.add_argument('--built', required=True, help='the folder `tiles` built into')
    sub.add_argument('--model', required=True); sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_t_common')
    sub.set_defaults(run=command_install)
    sub = commands.add_parser('placeables', help='put converted models into the placeable pack and the placeables table')
    sub.add_argument('--models', required=True); sub.add_argument('--built', required=True, help='the folder `game` converted into')
    sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_placeable'); sub.add_argument('--table', default='srn_2da/placeables.2da')
    sub.add_argument('--model', action='append', default=[], help='limit to these models (repeatable)')
    sub.set_defaults(run=command_placeables)
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
