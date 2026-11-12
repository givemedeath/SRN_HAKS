"""The envkit commands that change the packs and the additions catalog: `placeables`, `blueprints` and `install`.

They take everything from their arguments and name no pack themselves (the command line's defaults do, in
`__main__`), so a test can run them against a scratch repository. Each works out all it may refuse before it copies or
writes anything."""
import json
from pathlib import Path

from . import game_bytes, require


def _catalogued(args):
    """(catalog, its path, what a new entry says of itself): the additions catalog a command enters its work in."""
    import datetime
    from . import catalog
    repo = Path(args.repo); path = repo / args.catalog
    require(path.is_file(), 'The additions catalog is missing: ' + str(path))
    source = Path(args.models).resolve()
    source = source.relative_to(repo.resolve()).as_posix() if source.is_relative_to(repo.resolve()) else source.name
    return catalog.load(path), path, {'madeBy': 'envkit', 'source': source, 'provenance': args.provenance, 'added': datetime.date.today().isoformat()}


def _home(args, path):
    """Where a built file goes: into its model's pack, but the dark halo every lit model shares into the one pack that
    holds it (`--dark-pack`): the same file in two packs fails repository verification."""
    from . import convert
    return Path(args.repo) / (args.dark_pack if path.stem == convert.HALO_OUT else args.pack) / path.name


def _lit(old, core, lights):
    """`core` with what a script swaps to put the model's lights out; an entry of a model no longer lit forgets its own."""
    for entry in old:
        entry.pop('lights', None)
    return {**core, 'lights': lights} if lights else core


def _unlit(pack, name, built, models):
    """Remove from a pack the light files of a model built again without them, and return their names: a glow map
    left behind would read as a lit model whose entry records no lights. A fence's wire picture goes the same way
    when the model is built again without its fence. Only the three names of the lights standard and the wire
    picture's are looked at, and never one that is a model of the set in its own right."""
    gone = [path for stem in (f'{name}_i', f'{name}_o', f'{name}_h', f'{name}_w') if stem not in models for path in sorted(Path(pack).glob(stem + '.*'))
            if path.suffix in ('.mtr', '.dds', '.txi') and not (Path(built) / path.name).is_file()]
    for path in gone:
        path.unlink()
    return [path.name for path in gone]


def _entry(old, core, origin, what):
    """An entry for the catalog: one already there keeps what it says of its origin; a new one must name its
    PROVENANCE.md section."""
    if old:
        return core
    require(origin['provenance'], f'{what} is new to the catalog: name its PROVENANCE.md section with --provenance')
    return {**core, **origin}


def command_install(args):
    """Put a built tile group into the packs: its files into the shared pack, its records into each tileset named."""
    import shutil
    from . import convert, tile
    models = convert.load_models(args.models); built = Path(args.built) / args.model; repo = Path(args.repo)
    require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    made = json.loads((built / 'report.json').read_text(encoding='utf-8')); tiles = models[args.model]['tiles']; shared = repo / args.pack
    require(shared.is_dir() and (repo / args.dark_pack).is_dir() and all((repo / f'srn_t_{name}' / f'{name}.set').is_file() for name in tiles['sets']),
            'A pack or set file named is missing')
    # Every tileset is worked out before anything is copied or written, so a refusal on one leaves none half done.
    prepared = {name: tile.prepare(repo / f'srn_t_{name}' / f'{name}.set', repo / f'srn_t_{name}' / f'{name}palstd.itp', made, terrain=terrain,
                                   group_name=tiles['group'], label=tiles['label']) for name, terrain in tiles['sets'].items()}
    from . import catalog
    data, record, origin = _catalogued(args)
    numbers = {name: (one['firstTile'], one['group']) for name, one in prepared.items()}
    for name, (first, number) in numbers.items():  # refused here too, before anything is copied, if the catalog says otherwise
        old = [entry for entry in data['tileGroups'] if (entry['tileset'], entry['group']) == (name, number)]
        core = {'tileset': name, 'group': number, 'name': tiles['group'], 'label': tiles['label'], 'rows': made['rows'], 'columns': made['columns'],
                'tiles': [first + index for index in range(len(made['tiles']))], 'models': [one['model'] for one in made['tiles']], 'pack': args.pack}
        require(name in data['baseline']['tilesets'], f'The catalog has no baseline for {name}: add its imported tile and group counts first')
        catalog.put_group(data, _entry(old, _lit(old, core, convert.lights(args.model, built / 'shared')), origin, f'{tiles["group"]} in {name}'))
    copied = []
    for one in made['tiles']:
        copied += [shutil.copyfile(built / 'compiled' / f'{one["model"]}.mdl', shared / f'{one["model"]}.mdl'),
                   shutil.copyfile(built / 'source' / f'{one["model"]}.wok', shared / f'{one["model"]}.wok')]
    copied += [shutil.copyfile(path, shared / path.name) for path in sorted((built / 'source').glob('*.tga'))]  # area-map pictures and the lid's texture
    # The lights-out set goes with the tiles as it goes with a placeable: one standard for whoever scripts them.
    copied += [shutil.copyfile(path, _home(args, path)) for path in sorted((built / 'shared').iterdir())]
    removed = _unlit(shared, args.model, built / 'shared', models)
    placed = {name: tile.commit(one) for name, one in prepared.items()}
    catalog.save(record, data)
    print(json.dumps({'files': len(copied), 'removed': removed, 'sets': placed}), flush=True)


def command_placeables(args):
    """Put converted models into the placeable pack and give each a row in the placeables table. Models that all have
    their rows already are converted again in place: their files are replaced and the table is left as it is."""
    import shutil
    from . import convert, placeables
    models = convert.load_models(args.models); built, repo = Path(args.built), Path(args.repo); pack, table = repo / args.pack, repo / args.table
    unknown = [name for name in args.model if not models.get(name, {}).get('placeable')]
    require(not unknown, 'The game set gives these no placeable row: ' + ', '.join(unknown))
    chosen = {name: model['placeable'] for name, model in models.items() if model.get('placeable') and (not args.model or name in args.model)}
    require(chosen and pack.is_dir() and (repo / args.dark_pack).is_dir() and table.is_file(), 'No model to register, or the pack or table is missing')
    missing = [name for name in chosen if not (built / name / 'compiled' / f'{name}.mdl').is_file()]
    require(not missing, 'Convert these first (envkit game): ' + ', '.join(missing))
    text = table.read_bytes().decode('cp1252'); there = placeables.rows(text)
    require(all(name in there for name in chosen) or not any(name in there for name in chosen), 'Some of these models have rows and some have none: register them apart')
    if all(name in there for name in chosen):
        rows = {name: there[name] for name in chosen}
    else:
        text, rows = placeables.register(text, [{'model': name, **placed} for name, placed in chosen.items()])
    written = game_bytes(text, table.name)  # refused here, not after the copying, if a label has a character the game lacks
    from . import catalog
    data, record, origin = _catalogued(args)
    for name, row in rows.items():  # refused here, before anything is copied, if the catalog says otherwise
        old = [entry for entry in data['placeables'] if entry['row'] == row]; label = placeables.PREFIX + chosen[name]['label']
        # Converting again leaves the table as it is, so the label it gave the row stands too.
        require(not old or old[0]['label'] == label, f'Row {row} is labelled otherwise in the catalog: a label is changed by hand, in the table and the catalog together')
        core = _lit(old, {'row': row, 'model': name, 'label': label, 'pack': args.pack}, convert.lights(name, built / name / 'source'))
        catalog.put_placeable(data, _entry(old, core, origin, name))
    copied, removed = 0, []
    for name in chosen:
        removed += _unlit(pack, name, built / name / 'source', models)
        shutil.copyfile(built / name / 'compiled' / f'{name}.mdl', pack / f'{name}.mdl'); copied += 1
        for path in sorted((built / name / 'source').iterdir()):
            if path.suffix in ('.pwk', '.mtr', '.dds', '.txi'):
                shutil.copyfile(path, _home(args, path)); copied += 1
    table.write_bytes(written); catalog.save(record, data)  # `record`, not a name the copying above uses
    print(json.dumps({'rows': rows, 'files': copied, 'removed': removed}), flush=True)


def command_blueprints(args):
    """Give every envkit placeable of a game set a blueprint in its pack and rebuild the pack's standard palette, so
    the Toolset offers them on the Standard tab. Needs the game: the palette is the game's own with these added."""
    import subprocess
    import tempfile
    from tools.phenotypes import tool_runtime
    from . import blueprints, catalog, convert, placeables
    models = convert.load_models(args.models); repo = Path(args.repo); pack = repo / args.pack; record = repo / args.catalog
    require(pack.is_dir() and record.is_file(), 'The pack or the additions catalog is missing: ' + str(pack) + ', ' + str(record))
    data = catalog.load(record); gff = str(tool_runtime.tool('nwn_gff'))
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
        made = {}
        for entry in data['placeables']:
            placed = models.get(entry['model'], {}).get('placeable')
            if placed is None or 'category' not in placed:
                continue
            static = placed.get('static', not models[entry['model']].get('lit'))
            made[entry['model']] = blueprints.blueprint(entry['model'], entry['row'], entry['label'].removeprefix(placeables.PREFIX), placed['category'], static=static,
                                                        comment='envkit: ' + entry['source'])
            catalog.put_placeable(data, {**entry, 'blueprint': entry['model'], 'category': placed['category']})
        listed = [{'resref': entry['blueprint'], 'name': entry['label'].removeprefix(placeables.PREFIX), 'category': entry['category']}
                  for entry in data['placeables'] if entry.get('blueprint')]
        palette = blueprints.palette(read(pack / blueprints.SKELETON), read(scratch / 'stock.itp'), listed)
        for model, document in made.items():  # every blueprint and the palette are worked out before the first is written
            write(document, pack / f'{model}.utp')
        write(palette, pack / blueprints.PALETTE)
    catalog.save(record, data)
    print(json.dumps({'blueprints': list(made), 'palette': len(listed)}), flush=True)
