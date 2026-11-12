"""Command line for envkit, in the order a set goes through it. `props` lists the props of every onboarded sheet by
type and refuses a duplicate nobody declared; `crops` writes every crop of a set for a look and `reference` redraws
assets on the bound ComfyUI; `meshy` makes paid models under the ledger's cap; `game` converts
generated models to compiled placeables, `placeables` puts them in the pack and the table and `blueprints` gives
them blueprints a builder can paint; `tiles` builds a model as a tile group and `install` puts that group in the shared
pack and its tilesets. Whatever is added to the table or a tileset is entered in the additions catalog, which
repository verification (tools/Test-Repository.ps1) checks against the packs.

A whole sheet is run with the commands beside those (docs/envkit/sheet-runbook.md): `contact` shows a reference run
against its crops, `sheet` sends a sheet's plan through Meshy and collects it, `view` draws a model square on with a
grid to read a game set's boxes from, `check` looks at props, lights, a tile group and doors in the game client, and
`toolset` prepares and reads back a Toolset check of tile groups.

Two commands stand beside a sheet's run. `onboard` brings a new concept sheet into the kit and reviews the sets
against each other: boxes proposed on the sheet, set files written from a spec, pictures of the boxes, the reused
props and the props of a type, a mechanical audit, and the decisions of a review applied. `study` reads the stock
tiles of a tileset, for a question about how the engine wants a tile made."""
import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.envkit'

from . import additions, fresh, local, reference, require

CATALOG = 'docs/additions/catalog.json'  # catalog.PATH, said here so that asking for help imports nothing
MESHY_NEEDS = {'init': ('cap',), 'cap': ('cap', 'reason'), 'prop': ('key', 'image', 'triangles', 'work'), 'building': ('key', 'image', 'work'),
               'remesh': ('key', 'source', 'triangles', 'work'), 'wait': ('key', 'work'), 'download': ('key', 'work', 'bank'),
               'master': ('key', 'work', 'bank')}


def _generated(root, model):
    """(folder, maps) of a generated model, as a Meshy download or a local job leaves it under the output root."""
    source = Path(root) / model['source']
    return source, {key: source / f'texture_0_{key}.png' for key in local.MAPS}


def _crunch():
    from tools import shared_tools
    return shared_tools.resolve_tool('crunch', Path(__file__).resolve().parents[2])['path']


def command_crops(args):
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    # A cut is shown as it will be redrawn where the chosen references are given, else by its box on the sheet.
    rows = {name: str(reference.source(data, name, sheet, args.selected, Path(args.output) / f'{name}.png') if args.selected
                      else reference.crop(sheet, asset['box'], Path(args.output) / f'{name}.png'))
            for name, asset in data['assets'].items() if (name in args.asset if args.asset else 'same' not in asset)}
    print(json.dumps(rows, indent=1))


def command_props(args):
    """The props of every onboarded sheet by type; fails when a type is shared without saying same or variant."""
    found = reference.register(args.sets)
    for kind, rows in found['types'].items():
        print(kind + ': ' + ' '.join(rows['original'] + ['variant ' + key for key in rows['variant']] + ['same ' + key for key in rows['same']]))
    print(f"{found['make']} to make, {found['reuse']} reused")


def command_reference(args):
    from tools.headkit.comfy import Client
    data = reference.load_set(args.set); sheet = reference.resolve_sheet(args.sheets, data['sheet'])
    unknown = [name for name in args.asset if name not in data['assets']]
    require(not unknown, 'Unknown assets: ' + ', '.join(unknown))
    names = args.asset or [name for name, asset in data['assets'].items() if 'same' not in asset]  # a same is not made
    for name in names:
        asset = data['assets'][name]
        require('cut' not in asset or args.selected, f'{name} is cut from the chosen reference of {asset.get("cut", {}).get("from")}: give --selected')
    local = json.loads(Path(args.bindings).read_text(encoding='utf-8')); client = Client(args.url); output = Path(args.output); missed = []
    for name in names:
        # With --wait the run waits for the shared queue before each asset, and an asset that fails is said and passed
        # over, so that one busy spell or lost poll does not stop the rest; the run fails at the end. Without it the
        # first failure stops the run, and a busy queue is refused at once.
        if args.wait and not reference.wait_for_queue(client, args.wait):
            missed.append(name); print(json.dumps({'asset': name, 'state': 'skipped', 'error': f'ComfyUI was still busy after {args.wait} seconds; nothing submitted'}), flush=True)
            continue
        asset = data['assets'][name]
        try:
            source = reference.source(data, name, sheet, args.selected, output / 'crops' / f'{name}.png')
            text = reference.prompt(asset['kind'], asset['subject'], asset.get('notes', ''), asset.get('unbranded', False))
            result = reference.make(client, local, args.bindings, name, text, source, args.seed, output, deadline=args.deadline)
        except Exception as failure:
            if not args.wait:
                raise
            missed.append(name); print(json.dumps({'asset': name, 'state': 'failed', 'error': str(failure)}), flush=True)
            continue
        print(json.dumps({'asset': name, 'state': result['state'], 'outputs': result['outputs'],
                          'elapsedSeconds': result['elapsedSeconds']}), flush=True)
    require(not missed, f'{len(missed)} of {len(names)} assets were not made: ' + ', '.join(missed))


def _retouching(model):
    """What a game set says of turning a model and retouching its colour, as `convert.shape` takes it."""
    from . import convert
    return {key: model[key] for key in convert.RETOUCHING if key in model}


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
                                       lift=model.get('lift', 0.0), **_retouching(model))
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
    from . import convert, meshy, tile
    models = convert.load_models(args.models)
    require(args.model in models and models[args.model].get('tiles'), 'The game set gives this model no tiles: ' + args.model)
    model = models[args.model]; tiles = model['tiles']

    def shaped(name):
        """A model of the set as finished, its maps and its picture for the area map (as retouched, which `skin` still has to write)."""
        one = models[name]; source, maps = _generated(args.root, one)
        made = convert.shape(source / 'model.glb', maps, height=one['height'], colour=one.get('colour', 1024), sign_tilt=one.get('signTilt'),
                             lit=one.get('lit'), halo=one.get('halo'), lift=one.get('lift', 0.0), **_retouching(one))
        if made['colour'] is not None:
            colour = np.asarray(made['colour'].convert('RGB').resize((512, 512)), float) / 255
        else:
            with Image.open(maps['base_color']) as image:
                colour = np.asarray(image.convert('RGB').resize((512, 512)), float) / 255
        return made, maps, colour
    with fresh(Path(args.output) / args.model) as folder:  # a group that is refused leaves nothing in the way of the next attempt
        made, maps, colour = shaped(args.model); textures = convert.part_textures(args.model, tiles.get('parts', [])); placed, crunch = [], _crunch()
        counts = {args.model: len(made['faces'])}; shapes = {}
        for name in textures:  # each model placed in the group, shaped once; the building is counted before anything is written
            shapes[name] = shaped(name); counts[name] = len(shapes[name][0]['faces'])
        built = convert.building_triangles(models, args.model, counts)
        require(built <= meshy.BUILDING_TRIANGLES, f'The building of {args.model} is {built} triangles, its own and those of the models placed in it that are '
                f'no placeables: more than the building budget of {meshy.BUILDING_TRIANGLES}; remesh its pieces lower')
        files = convert.skin(args.model, maps, folder / 'shared', crunch, made, colour=model.get('colour', 1024))
        for name, texture in textures.items():  # each model placed in the group, once for its pictures, then where it stands
            part, part_maps, part_colour = shapes[name]
            files += convert.skin(texture, part_maps, folder / 'shared', crunch, part, colour=models[name].get('colour', 1024))
            placed += [(texture, convert.place(part, stand['at'], stand.get('turn', 0)), part_colour) for stand in tiles['parts'] if stand['model'] == name]
        report = tile.group(args.model, made, folder / 'source', ground=tiles['ground'], colour=colour, fade=tiles.get('fade'), door=tiles.get('door'),
                            ground_colour=_ground_colour(Path(args.repo) / args.pack, tiles['ground']),
                            parts=placed)  # a model placed twice is joined there into one model of the group
        compiled = tile.compile_tiles([folder / 'source' / f'{one["model"]}.mdl' for one in report['tiles']], folder / 'compiled')
        report['parts'] = textures; report['buildingTriangles'] = built
        report.update({'name': args.model, 'compiled': {path.name: path.stat().st_size for path in compiled}, 'textures': {path.name: path.stat().st_size for path in files}})
        (folder / 'report.json').write_text(json.dumps(report, indent=1) + chr(10), encoding='utf-8')
    print(json.dumps(report), flush=True)
    for note in report['notes']:  # beside the report, which stays the only thing on standard output
        print('note: ' + note, file=sys.stderr, flush=True)


def command_meshy(args):
    from . import meshy
    missing = ['--' + name for name in MESHY_NEEDS.get(args.action, ()) if not getattr(args, name)]
    require(not missing, f'envkit meshy {args.action} needs ' + ', '.join(missing))  # said before the ledger is touched
    if args.action == 'init':
        meshy.Ledger.create(args.ledger, args.cap)
    ledger = meshy.Ledger(args.ledger)
    if args.action == 'cap':
        ledger.raise_cap(args.cap, args.reason)
    elif args.action in ('prop', 'building', 'remesh'):
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


def command_contact(args):
    from . import view
    print(json.dumps({'references': view.contact(args.references, args.output, args.columns), 'picture': args.output}))


def command_sheet(args):
    from . import meshy, sheet
    plan = sheet.load_plan(args.plan); ledger = meshy.Ledger(args.ledger); root = Path(args.root); work = root / 'meshy' / 'work'
    failed = []
    if args.action == 'submit':
        print(json.dumps({'sent': sheet.submit(ledger, plan, root / 'references' / 'selected', work)}))
    elif args.action == 'collect':
        made = sheet.collect(ledger, plan, work, root / 'meshy' / 'models', root / 'meshy' / 'masters'); failed = made['failed']; print(json.dumps(made))
    print(json.dumps(sheet.status(ledger, plan), indent=1))
    require(not failed, 'Calls of the plan have no working model: ' + ', '.join(failed))  # after the status, so that a failed collect does not end as a good one


def _views(text):
    """name[:sides[:scale[:grid]]] as (name, sides, scale, grid): sides are digits, 0 the front."""
    parts = text.split(':'); parts += [''] * (4 - len(parts)); number = re.compile(r'\d+(\.\d+)?')
    require(len(parts) == 4 and parts[0] and re.fullmatch('[0-3]*', parts[1]) and re.fullmatch(r'\d*', parts[2]) and (not parts[3] or number.fullmatch(parts[3])),
            'A view is name[:sides[:scale[:grid]]], the sides digits 0 to 3, the scale whole pixels to the metre and the grid metres: ' + text)
    scale, grid = int(parts[2] or 0), float(parts[3] or 0)
    require((not parts[2] or scale > 0) and (not parts[3] or grid > 0), 'A view\'s scale and grid are more than nothing: ' + text)
    return parts[0], [int(side) for side in parts[1] or '0'], scale or None, grid or None


def command_view(args):
    from . import convert, view
    require(bool(args.models) != bool(args.source), 'Give a game set (--models, --root, --model) or generated models (--source, --height)')
    drawn = []  # (name, pictures) of each model, for the page
    if args.source:
        require(len(args.height) == len(args.source), 'Each generated model is stood at a height: give a --height in metres for each --source')
        require(not args.lit and not args.root and not args.eye and args.grid is None and len(args.model) <= 1,
                'A generated model has no set to give it lit boxes: it is drawn from --source, --height and one --model of its sides (0123)')
        _, sides, scale, grid = _views('raw:' + (args.model[0] if args.model else '0'))
        for source, height in zip(args.source, args.height):
            told = view.raw(source, height, args.output, sides=sides, scale=scale, grid=grid); drawn.append((Path(source).name, told['pictures']))
            print(json.dumps({'source': source, **told}), flush=True)
    else:
        require(args.root and args.model, 'A game set is drawn with --root and --model')
        require(args.grid is None or args.eye, 'A square-on view takes its grid in --model name:sides:scale:grid; --grid is for --eye views')
        models = convert.load_models(args.models)
        if args.eye:  # from stated eyes, in place of the square-on views
            require(not args.lit and all(':' not in name for name in args.model), 'With --eye a model is named alone, and its lit parts are not shown')
            eyes = [view.eye(text) for text in args.eye]; require(len({label for label, *_ in eyes}) == len(eyes), 'Each eye has a label of its own')
            for name in args.model:
                told = view.perspective(models, args.root, name, args.output, eyes, grid=args.grid); drawn.append((name, told['pictures']))
                print(json.dumps({'model': name, **told}), flush=True)
        else:
            for name, sides, scale, grid in map(_views, args.model):
                told = view.elevations(models, args.root, name, args.output, sides=sides, scale=scale, grid=grid, lit=args.lit); drawn.append((name, told['pictures']))
                print(json.dumps({'model': name, **told}), flush=True)
    if args.page:
        print(json.dumps({'page': args.page, 'models': view.page(drawn, args.page)}), flush=True)


def command_onboard(args):
    from . import onboard
    needs = {'boxes': ('sheet', 'output'), 'sets': ('spec', 'sheets'), 'crops': ('set', 'sheets', 'output'), 'overlay': ('sheets', 'output'), 'audit': ('sheets',),
             'types': ('sheets', 'output', 'type'), 'same': ('sheets', 'output'), 'revise': ('decisions',)}[args.action]
    missing = [name for name in needs if not getattr(args, name)]; require(not missing, f'onboard {args.action} needs ' + ', '.join('--' + name for name in missing))
    takes = needs + {'boxes': ('split',), 'same': ('only',)}.get(args.action, ())
    extra = [name for name in ('sheets', 'sheet', 'split', 'spec', 'set', 'type', 'only', 'decisions', 'output') if getattr(args, name) not in (None, []) and name not in takes]
    require(not extra, f'onboard {args.action} does not take ' + ', '.join('--' + name for name in extra))
    if args.action == 'boxes':
        told = onboard.propose(args.sheet, args.output, args.split)
    elif args.action == 'sets':
        told = onboard.write_sets(args.spec, args.sheets, args.sets)
    elif args.action == 'crops':
        told = {'crops': onboard.crops_page(args.set, args.sheets, args.output)}
    elif args.action == 'overlay':
        told = {'pages': onboard.overlay(args.sets, args.sheets, args.output)}
    elif args.action == 'audit':
        told = onboard.audit(args.sets, args.sheets)
    elif args.action == 'types':
        told = {'props': onboard.type_page(args.sets, args.sheets, args.output, args.type)}
    elif args.action == 'same':
        told = onboard.same_pages(args.sets, args.sheets, args.output, only=args.only)
    else:
        told = {'changed': onboard.revise(args.decisions, args.sets)}
    print(json.dumps(told, indent=1))


def command_study(args):
    from . import study
    if args.action == 'pathnodes':
        require(not args.tile and not args.output, 'study pathnodes takes --packs and --tileset alone')
        print(json.dumps(study.path_nodes(args.packs, args.tileset), indent=1))
        return
    require(args.tile and args.output and len(args.tileset) == 1, 'study tiles needs --tile and --output, and reads one --tileset')
    for row in study.tiles(args.packs, args.tileset[0], args.tile, args.output):
        print(json.dumps(row), flush=True)


def command_check(args):
    from . import checks
    if args.kind == 'doors':
        require(args.user and args.output, 'check doors needs --user (the Toolset user folder) and --output (a fresh folder for captures)')
        print(json.dumps(checks.doors(args.game, args.user, args.output, ticks=args.ticks)))
        return
    needs = {'props': ('models', 'root', 'name', 'built', 'model'), 'lights': ('models', 'root', 'name', 'built'), 'group': ('models', 'root', 'name', 'built', 'model', 'tileset')}[args.kind]
    missing = ['--' + name for name in needs if not getattr(args, name)]
    require(not missing, f'envkit check {args.kind} needs ' + ', '.join(missing))
    require(args.kind == 'lights' or len(args.built) == 1, 'One built folder is checked at a time')
    modes = {'props': ('day', 'night'), 'lights': ('night',), 'group': ('day', 'night', 'near', 'walk')}[args.kind]; mode = args.mode or modes[0]
    require(mode in modes, f'envkit check {args.kind} has no --mode {mode}: ' + ' or '.join(modes))
    if args.kind == 'props':
        made = checks.props(args.game, args.repo, args.root, args.name, args.models, args.built[0], args.model, night=mode == 'night')
    elif args.kind == 'lights':
        made = checks.lights(args.game, args.repo, args.root, args.name, args.models, args.built)
    else:
        require(len(args.model) == 1, 'One tile group is checked at a time')
        made = checks.group(args.game, args.repo, args.root, args.name, args.models, args.built[0], args.model[0], args.tileset, mode, second_storey=args.second_storey)
    print(json.dumps(made))


def command_toolset(args):
    from . import toolset
    if args.action == 'prepare':
        made = toolset.prepare(args.user, Path(args.repo) / 'output', tilesets=tuple(args.tileset) or tuple(toolset.AREAS), game=args.game)
    elif args.action == 'saved':
        made = toolset.saved(Path(args.user) / 'modules' / f'{toolset.MODULE}.mod', args.repo)
    else:
        made = {'junctionRemoved': toolset.retire(args.user)}
    print(json.dumps(made, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='envkit')
    commands = parser.add_subparsers(dest='command', required=True)
    sub = commands.add_parser('meshy', help='paid Meshy calls under the ledger cap')
    sub.add_argument('action', choices=['init', 'status', 'cap', 'prop', 'building', 'remesh', 'wait', 'download', 'master'])
    sub.add_argument('--ledger', required=True)
    sub.add_argument('--cap', type=int); sub.add_argument('--reason', help='cap: the approval a raise rests on, in a few words')
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
    sub.add_argument('--dark-pack', default='srn_placeable', help='the one pack holding the dark halo lit models share')
    sub.set_defaults(run=additions.command_install)
    sub = commands.add_parser('placeables', help='put converted models into the placeable pack and the placeables table')
    sub.add_argument('--models', required=True); sub.add_argument('--built', required=True, help='the folder `game` converted into')
    sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_placeable'); sub.add_argument('--table', default='srn_2da/placeables.2da')
    sub.add_argument('--model', action='append', default=[], help='limit to these models (repeatable)')
    sub.add_argument('--catalog', default=CATALOG); sub.add_argument('--provenance', help='PROVENANCE.md section of models new to the catalog')
    sub.add_argument('--dark-pack', default='srn_placeable', help='the one pack holding the dark halo lit models share')
    sub.set_defaults(run=additions.command_placeables)
    sub = commands.add_parser('blueprints', help='give catalogued placeables blueprints and list them in the standard palette')
    sub.add_argument('--models', required=True); sub.add_argument('--game', required=True, help='the game install folder (the one holding data/)')
    sub.add_argument('--repo', default='.'); sub.add_argument('--pack', default='srn_placeable'); sub.add_argument('--catalog', default=CATALOG)
    sub.set_defaults(run=additions.command_blueprints)
    sub = commands.add_parser('contact', help='one picture of a reference run, each reference beside its crop')
    sub.add_argument('--references', required=True, help='a reference run folder, with its crops folder'); sub.add_argument('--output', required=True, help='the picture to write')
    sub.add_argument('--columns', type=int, default=3); sub.set_defaults(run=command_contact)
    sub = commands.add_parser('sheet', help="a sheet's models through Meshy, as its plan states them")
    sub.add_argument('action', choices=['status', 'submit', 'collect'])
    sub.add_argument('--plan', required=True, help="the sheet's plan, sets/<sheet>-meshy.json"); sub.add_argument('--ledger', required=True)
    sub.add_argument('--root', required=True, help="the sheet's output root: references/selected is read, meshy/ is written")
    sub.set_defaults(run=command_sheet)
    sub = commands.add_parser('view', help='a model seen square on with a metre grid, to read a game set\'s boxes from')
    sub.add_argument('--models', help='game set file'); sub.add_argument('--root', help="the set's output root")
    sub.add_argument('--source', action='append', default=[], help='instead of a game set: a generated model folder (repeatable, each with a --height)')
    sub.add_argument('--height', type=float, action='append', default=[], help='with --source: the height in metres it is stood at, one for each --source in order')
    sub.add_argument('--model', action='append', default=[], help='name[:sides[:scale[:grid]]], sides as digits (0 front, 1, 2 back, 3); with --source, the sides alone')
    sub.add_argument('--lit', action='store_true', help='show what the lit boxes light, and count what each holds and lights'); sub.add_argument('--output', required=True)
    sub.add_argument('--eye', action='append', default=[], help='instead of square on: label=ex,ey,ez,tx,ty,tz[,fov[,reach]], the eye and what it looks at in metres on the model (repeatable)')
    sub.add_argument('--grid', type=float, help='with --eye: a measuring grid this many metres apart on the upright plane through each target; the eyes level with their targets')
    sub.add_argument('--page', help='also one picture of every model drawn, side by side under their names')
    sub.set_defaults(run=command_view)
    sets = str(Path(__file__).with_name('sets'))
    sub = commands.add_parser('onboard', help='bring a concept sheet into the kit and review the sets against each other')
    sub.add_argument('action', choices=['boxes', 'sets', 'crops', 'overlay', 'audit', 'types', 'same', 'revise'])
    sub.add_argument('--sets', default=sets, help='the folder of set files'); sub.add_argument('--sheets', help='the folder holding the concept sheets')
    sub.add_argument('--sheet', help='boxes: the sheet to find drawings on'); sub.add_argument('--split', type=int, help='boxes: the row the prop set starts at')
    sub.add_argument('--spec', help='sets: the spec naming each box'); sub.add_argument('--set', help='crops: the set file')
    sub.add_argument('--type', action='append', default=[], help='types: a prop type (repeatable)'); sub.add_argument('--only', action='append', default=[], help='same: only rows with a prop of this set (repeatable)')
    sub.add_argument('--decisions', help='revise: the decisions of a review'); sub.add_argument('--output', help='the picture to write, or for overlay and same the start of its pages\' names')
    sub.set_defaults(run=command_onboard)
    sub = commands.add_parser('study', help='read the stock tiles of a tileset in the packs')
    sub.add_argument('action', choices=['pathnodes', 'tiles']); sub.add_argument('--packs', default=str(Path(__file__).resolve().parents[2]), help='the folder holding srn_t_<tileset> and srn_t_common')
    sub.add_argument('--tileset', action='append', required=True, help='a tileset name, as in srn_t_<name> (pathnodes: repeatable)')
    sub.add_argument('--tile', action='append', type=int, default=[], help='tiles: a tile number of the set file (repeatable)'); sub.add_argument('--output', help='tiles: a folder for the decompiled models')
    sub.set_defaults(run=command_study)
    sub = commands.add_parser('check', help='look at props, lights, a tile group or doors in the game client')
    sub.add_argument('kind', choices=['props', 'lights', 'group', 'doors'])
    sub.add_argument('--game', required=True, help='the game install folder (the one holding data/)'); sub.add_argument('--repo', default='.')
    sub.add_argument('--models', help='game set file'); sub.add_argument('--root', help="the set's output root: fixtures/<name> is written")
    sub.add_argument('--name', help='a new fixture name, a lowercase resref of at most 11 characters'); sub.add_argument('--built', action='append', default=[], help='the folder `game` or `tiles` built into (lights: repeatable, the first that holds a model serves)')
    sub.add_argument('--model', action='append', default=[]); sub.add_argument('--tileset', choices=['dgt04', 'udp1'])
    sub.add_argument('--mode', choices=['day', 'night', 'near', 'walk'], help='props: day (default) or night; group: day (default), night (lights put out and on again), near or walk (walkers sent across the area; refused if one stops short); lights are seen by night'); sub.add_argument('--second-storey', default='0', help='near: the client\'s second-storey setting')
    sub.add_argument('--user', help='doors: the Toolset user folder'); sub.add_argument('--output', help='doors: a fresh folder for captures')
    sub.add_argument('--ticks', type=int, default=150, help='doors: how long the player is watched, two seconds a tick')
    sub.set_defaults(run=command_check)
    sub = commands.add_parser('toolset', help='prepare a Toolset check of tile groups, read what it saved, retire it')
    sub.add_argument('action', choices=['prepare', 'saved', 'retire']); sub.add_argument('--user', required=True, help='the Toolset user folder (fresh for prepare)')
    sub.add_argument('--repo', default='.'); sub.add_argument('--game', help='prepare: the game install folder, to say how the Toolset is started')
    sub.add_argument('--tileset', action='append', default=[], choices=['dgt04', 'udp1']); sub.set_defaults(run=command_toolset)
    sub = commands.add_parser('props', help='the props of every onboarded sheet by type; refuses undeclared duplicates')
    sub.add_argument('--sets', default=str(Path(__file__).with_name('sets'))); sub.set_defaults(run=command_props)
    parsers = {}
    for name, run in (('crops', command_crops), ('reference', command_reference)):
        sub = parsers[name] = commands.add_parser(name)
        sub.add_argument('--set', required=True, help='set file naming the sheet and each asset crop')
        sub.add_argument('--sheets', required=True, help='folder holding the concept sheets')
        sub.add_argument('--output', required=True)
        sub.add_argument('--asset', action='append', default=[], help='limit to these assets (repeatable)')
        sub.add_argument('--selected', help='folder of the chosen references, which the pieces of a building (cut) are drawn from')
        sub.set_defaults(run=run)
    sub = parsers['reference']
    sub.add_argument('--bindings', required=True, help='local JSON with absolute comfyInput and comfyOutput')
    sub.add_argument('--url', default='http://127.0.0.1:8188')
    sub.add_argument('--seed', type=int, default=101)
    sub.add_argument('--deadline', type=int, default=2400)
    sub.add_argument('--wait', type=int, default=0, help='seconds to wait for the shared ComfyUI queue to empty before each asset; an asset that fails is passed over and the run fails at the end')
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
