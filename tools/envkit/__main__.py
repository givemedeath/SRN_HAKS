"""Command line for envkit, in the order a set goes through it. `crops` writes every crop of a set for a look and
`reference` redraws assets on the bound ComfyUI; `meshy` makes paid models under the ledger's cap; `game` converts
generated models to compiled placeables, `placeables` puts them in the pack and the table and `blueprints` gives
them blueprints a builder can paint; `tiles` builds a model as a tile group and `install` puts that group in the shared
pack and its tilesets. Whatever is added to the table or a tileset is entered in the additions catalog, which
repository verification (tools/Test-Repository.ps1) checks against the packs."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.envkit'

from . import fresh, local, reference, require

CATALOG = 'docs/additions/catalog.json'  # catalog.PATH, said here so that asking for help imports nothing
MESHY_NEEDS = {'init': ('cap',), 'prop': ('key', 'image', 'triangles', 'work'), 'building': ('key', 'image', 'work'),
               'remesh': ('key', 'source', 'triangles', 'work'), 'wait': ('key', 'work'), 'download': ('key', 'work', 'bank'),
               'master': ('key', 'work', 'bank')}


def _generated(root, model):
    """(folder, maps) of a generated model, as a Meshy download or a local job leaves it under the output root."""
    source = Path(root) / model['source']
    return source, {key: source / f'texture_0_{key}.png' for key in local.MAPS}


def _crunch():
    from tools import shared_tools
    return shared_tools.resolve_tool('crunch', Path(__file__).resolve().parents[2])['path']


def _catalogued(args, kind):
    """(catalog, its path, what a new entry says of itself): the additions catalog to enter `kind` of thing in."""
    import datetime
    from . import catalog
    repo = Path(args.repo); path = repo / args.catalog
    require(path.is_file(), 'The additions catalog is missing: ' + str(path))
    source = Path(args.models).resolve()
    source = source.relative_to(repo.resolve()).as_posix() if source.is_relative_to(repo.resolve()) else source.name
    return catalog.load(path), path, {'madeBy': 'envkit', 'source': source, 'provenance': args.provenance, 'added': datetime.date.today().isoformat()}


def _entry(old, core, fresh, what):
    """An entry for the catalog: one already there keeps what it says of its origin; a new one must name its
    PROVENANCE.md section."""
    if old:
        return core
    require(fresh['provenance'], f'{what} is new to the catalog: name its PROVENANCE.md section with --provenance')
    return {**core, **fresh}


def command_crops(args):
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    rows = {name: str(reference.crop(sheet, asset['box'], Path(args.output) / f'{name}.png'))
            for name, asset in data['assets'].items() if not args.asset or name in args.asset}
    print(json.dumps(rows, indent=1))


def command_reference(args):
    from tools.headkit.comfy import Client
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    unknown = [name for name in args.asset if name not in data['assets']]
    require(not unknown, 'Unknown assets: ' + ', '.join(unknown))
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
    from tools.armorkit import export
    from . import convert
    models = convert.load_models(args.models); output = Path(args.output)
    unknown = [name for name in args.model if name not in models]
    require(not unknown, 'Unknown models: ' + ', '.join(unknown))
    crunch = _crunch()
    for name in args.model or list(models):
        model = models[name]; source, maps = _generated(args.root, model)
        with fresh(output / name) as folder:  # a model that fails leaves nothing in the way of the next attempt
            report = convert.placeable(name, source / 'model.glb', maps, folder / 'source', crunch, height=model['height'],
                                       colour=model.get('colour', 1024), sign_tilt=model.get('signTilt'), lit=model.get('lit'), halo=model.get('halo'),
                                       lift=model.get('lift', 0.0))
            report['compiled'] = {path.name: path.stat().st_size for path in export.compile_models([folder / 'source' / f'{name}.mdl'], folder / 'compiled')}
            (folder / 'report.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(report), flush=True)


def _ground_colour(pack, texture):
    """The mean colour (0-1) of a ground texture in a pack, for the area map; mid grey where it cannot be read."""
    from PIL import Image
    for path in (Path(pack) / f'{texture}.tga', Path(pack) / f'{texture}.dds'):
        try:
            with Image.open(path) as image:
                return [value / 255 for value in image.convert('RGB').resize((1, 1), Image.BOX).getpixel((0, 0))]
        except (OSError, ValueError):
            continue
    return [0.4, 0.4, 0.4]


def command_tiles(args):
    """Build a model's tile group: tile models (compiled), walkmeshes, area-map pictures and the shared material and maps."""
    import numpy as np
    from PIL import Image
    from . import convert, tile
    models = convert.load_models(args.models)
    require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    model = models[args.model]; source, maps = _generated(args.root, model)
    with fresh(Path(args.output) / args.model) as folder:  # a group that is refused leaves nothing in the way of the next attempt
        made = convert.shape(source / 'model.glb', maps, height=model['height'], colour=model.get('colour', 1024), sign_tilt=model.get('signTilt'),
                             lit=model.get('lit'), halo=model.get('halo'))
        tiles = model['tiles']
        with Image.open(maps['base_color']) as image:
            colour = np.asarray(image.convert('RGB').resize((512, 512)), float) / 255
        report = tile.group(args.model, made, folder / 'source', ground=tiles['ground'], colour=colour, fade=tiles.get('fade'), door=tiles.get('door'),
                            ground_colour=_ground_colour(Path(args.repo) / args.pack, tiles['ground']))
        compiled = tile.compile_tiles([folder / 'source' / f'{one["model"]}.mdl' for one in report['tiles']], folder / 'compiled')
        files = convert.skin(args.model, maps, folder / 'shared', _crunch(), made, colour=model.get('colour', 1024))
        report.update({'name': args.model, 'compiled': {path.name: path.stat().st_size for path in compiled}, 'textures': {path.name: path.stat().st_size for path in files}})
        (folder / 'report.json').write_text(json.dumps(report, indent=1) + chr(10), encoding='utf-8')
    print(json.dumps(report), flush=True)


def command_install(args):
    """Put a built tile group into the packs: its files into the shared pack, its records into each tileset named."""
    import shutil
    from . import convert, tile
    models = convert.load_models(args.models); built = Path(args.built) / args.model; repo = Path(args.repo)
    require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    made = json.loads((built / 'report.json').read_text(encoding='utf-8')); tiles = models[args.model]['tiles']; shared = repo / args.pack
    require(shared.is_dir() and all((repo / f'srn_t_{name}' / f'{name}.set').is_file() for name in tiles['sets']), 'A pack or set file named is missing')
    # Every tileset is worked out before anything is copied or written, so a refusal on one leaves none half done.
    prepared = {name: tile.prepare(repo / f'srn_t_{name}' / f'{name}.set', repo / f'srn_t_{name}' / f'{name}palstd.itp', made, terrain=terrain,
                                   group_name=tiles['group'], label=tiles['label']) for name, terrain in tiles['sets'].items()}
    copied = []
    for one in made['tiles']:
        copied += [shutil.copyfile(built / 'compiled' / f'{one["model"]}.mdl', shared / f'{one["model"]}.mdl'),
                   shutil.copyfile(built / 'source' / f'{one["model"]}.wok', shared / f'{one["model"]}.wok')]
    copied += [shutil.copyfile(path, shared / path.name) for path in sorted((built / 'source').glob('*.tga'))]  # area-map pictures and the lid's texture
    # The lights-out materials serve a placeable a script can reach; no script reaches a tile, so they stay behind.
    idle = (args.model + '_o', convert.HALO_OUT)
    copied += [shutil.copyfile(path, shared / path.name) for path in sorted((built / 'shared').iterdir()) if path.stem not in idle]
    from . import catalog
    data, path, fresh = _catalogued(args, 'tile group')
    numbers = {name: (one['firstTile'], one['group']) for name, one in prepared.items()}
    for name, (first, number) in numbers.items():  # refused here, before any set file is written, if the catalog says otherwise
        old = [entry for entry in data['tileGroups'] if (entry['tileset'], entry['group']) == (name, number)]
        core = {'tileset': name, 'group': number, 'name': tiles['group'], 'label': tiles['label'], 'rows': made['rows'], 'columns': made['columns'],
                'tiles': [first + index for index in range(len(made['tiles']))], 'models': [one['model'] for one in made['tiles']], 'pack': args.pack}
        require(name in data['baseline']['tilesets'], f'The catalog has no baseline for {name}: add its imported tile and group counts first')
        catalog.put_group(data, _entry(old, core, fresh, f'{tiles["group"]} in {name}'))
    placed = {name: tile.commit(one) for name, one in prepared.items()}
    catalog.save(path, data)
    print(json.dumps({'files': len(copied), 'sets': placed}), flush=True)


def command_placeables(args):
    """Put converted models into the placeable pack and give each a row in the placeables table. Models that all have
    their rows already are converted again in place: their files are replaced and the table is left as it is."""
    import shutil
    from . import convert, placeables
    models = convert.load_models(args.models); built, repo = Path(args.built), Path(args.repo); pack, table = repo / args.pack, repo / args.table
    unknown = [name for name in args.model if not models.get(name, {}).get('placeable')]
    require(not unknown, 'The game set gives these no placeable row: ' + ', '.join(unknown))
    chosen = {name: model['placeable'] for name, model in models.items() if model.get('placeable') and (not args.model or name in args.model)}
    require(chosen and pack.is_dir() and table.is_file(), 'No model to register, or the pack or table is missing')
    missing = [name for name in chosen if not (built / name / 'compiled' / f'{name}.mdl').is_file()]
    require(not missing, 'Convert these first (envkit game): ' + ', '.join(missing))
    text = table.read_bytes().decode('cp1252'); there = placeables.rows(text)
    require(all(name in there for name in chosen) or not any(name in there for name in chosen), 'Some of these models have rows and some have none: register them apart')
    if all(name in there for name in chosen):
        rows = {name: there[name] for name in chosen}
    else:
        text, rows = placeables.register(text, [{'model': name, **placed} for name, placed in chosen.items()])
    copied = 0
    for name in chosen:
        shutil.copyfile(built / name / 'compiled' / f'{name}.mdl', pack / f'{name}.mdl'); copied += 1
        for path in sorted((built / name / 'source').iterdir()):
            if path.suffix in ('.pwk', '.mtr', '.dds', '.txi'):
                shutil.copyfile(path, pack / path.name); copied += 1
    from . import catalog
    data, path, fresh = _catalogued(args, 'placeable')
    for name, row in rows.items():
        old = [entry for entry in data['placeables'] if entry['row'] == row]
        catalog.put_placeable(data, _entry(old, {'row': row, 'model': name, 'label': placeables.PREFIX + chosen[name]['label'], 'pack': args.pack}, fresh, name))
    table.write_bytes(text.encode('cp1252')); catalog.save(path, data)
    print(json.dumps({'rows': rows, 'files': copied}), flush=True)


def command_blueprints(args):
    """Give every envkit placeable of a game set a blueprint in its pack and rebuild the pack's standard palette, so
    the Toolset offers them on the Standard tab. Needs the game: the palette is the game's own with these added."""
    import subprocess
    import tempfile
    from tools.phenotypes import tool_runtime
    from . import blueprints, catalog, convert, placeables
    models = convert.load_models(args.models); repo = Path(args.repo); pack = repo / args.pack; path = repo / args.catalog
    data = catalog.load(path); gff = str(tool_runtime.tool('nwn_gff'))
    run = lambda arguments: subprocess.run([str(value) for value in arguments], capture_output=True, timeout=300, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)

        def read(source):
            result = run([gff, '-i', source, '-k', 'json'])
            require(result.returncode == 0, f'{Path(source).name} could not be read: ' + result.stderr.decode(errors='replace')[-300:])
            return json.loads(result.stdout)

        def write(document, target):
            staged = scratch / (Path(target).name + '.json'); staged.write_text(json.dumps(document), encoding='utf-8')
            result = run([gff, '-i', staged, '-l', 'json', '-o', target, '-k', 'gff'])
            require(result.returncode == 0, f'{Path(target).name} could not be written: ' + result.stderr.decode(errors='replace')[-300:])
        stock = run([tool_runtime.tool('nwn_resman_cat'), '--root', args.game, blueprints.PALETTE])
        require(stock.returncode == 0 and stock.stdout, 'The game\'s own placeable palette could not be read from ' + str(args.game))
        (scratch / 'stock.itp').write_bytes(stock.stdout)
        made = []
        for entry in data['placeables']:
            placed = models.get(entry['model'], {}).get('placeable')
            if placed is None or 'category' not in placed:
                continue
            static = placed.get('static', not models[entry['model']].get('lit'))
            write(blueprints.blueprint(entry['model'], entry['row'], placed['label'], placed['category'], static=static, comment='envkit: ' + entry['source']),
                  pack / f'{entry["model"]}.utp')
            catalog.put_placeable(data, {**entry, 'blueprint': entry['model'], 'category': placed['category']}); made.append(entry['model'])
        listed = [{'resref': entry['blueprint'], 'name': entry['label'].removeprefix(placeables.PREFIX), 'category': entry['category']}
                  for entry in data['placeables'] if entry.get('blueprint')]
        write(blueprints.palette(read(pack / blueprints.SKELETON), read(scratch / 'stock.itp'), listed), pack / blueprints.PALETTE)
    catalog.save(path, data)
    print(json.dumps({'blueprints': made, 'palette': len(listed)}), flush=True)


def command_meshy(args):
    from . import meshy
    missing = ['--' + name for name in MESHY_NEEDS.get(args.action, ()) if not getattr(args, name)]
    require(not missing, f'envkit meshy {args.action} needs ' + ', '.join(missing))  # said before the ledger is touched
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
    sub.add_argument('--model', required=True); sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_t_common', help='pack holding the ground texture')
    sub.set_defaults(run=command_tiles)
    sub = commands.add_parser('install', help='put a built tile group into the shared pack and its tilesets')
    sub.add_argument('--models', required=True); sub.add_argument('--built', required=True, help='the folder `tiles` built into')
    sub.add_argument('--model', required=True); sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_t_common')
    sub.add_argument('--catalog', default=CATALOG); sub.add_argument('--provenance', help='PROVENANCE.md section of a group new to the catalog')
    sub.set_defaults(run=command_install)
    sub = commands.add_parser('placeables', help='put converted models into the placeable pack and the placeables table')
    sub.add_argument('--models', required=True); sub.add_argument('--built', required=True, help='the folder `game` converted into')
    sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_placeable'); sub.add_argument('--table', default='srn_2da/placeables.2da')
    sub.add_argument('--model', action='append', default=[], help='limit to these models (repeatable)')
    sub.add_argument('--catalog', default=CATALOG); sub.add_argument('--provenance', help='PROVENANCE.md section of models new to the catalog')
    sub.set_defaults(run=command_placeables)
    sub = commands.add_parser('blueprints', help='give catalogued placeables blueprints and list them in the standard palette')
    sub.add_argument('--models', required=True); sub.add_argument('--game', required=True, help='the game install folder (the one holding data/)')
    sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_placeable'); sub.add_argument('--catalog', default=CATALOG)
    sub.set_defaults(run=command_blueprints)
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
