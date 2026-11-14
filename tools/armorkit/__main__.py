"""Command line for the armorkit foundation: registry, parts tables, measurements, outfit briefs, bakes, client fixtures and publication."""
import argparse
import importlib
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.armorkit'

from . import registry, tables


def write_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1) + '\n', encoding='utf-8', newline='\n')


def command_registry(args):
    parts = registry.load(args.registry, publish=args.publish)
    if args.handoff:
        write_json(args.handoff, registry.handoff(parts))
    print(json.dumps({'parts': len(parts), 'slots': {slot: registry.numbers(parts, slot) for slot in registry.SLOTS
                                                     if registry.numbers(parts, slot)}}))


def command_tables(args):
    parts = registry.load(args.registry, publish=args.publish)
    stock = {table: (Path(args.stock) / (table + '.2da')).read_bytes().decode('cp1252') for table in registry.TABLES}
    made = tables.generate_all(stock, parts)
    report = [tables.check(table, text, parts, stock[table]) for table, text in made.items()]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for table, text in made.items():  # written only once every table has passed its check
        (output / (table + '.2da')).write_bytes(text.encode('cp1252'))
    print(json.dumps(report))


def command_measure(args):
    from . import measure
    output, written = Path(args.output), []
    registry.require(args.only == 'heads' or args.supermodels,
                     'The seam contract needs --supermodels: a folder of extracted stock animation models')
    if args.only in (None, 'heads'):  # seconds; first, so a wrong pack folder fails before the long measurement
        write_json(output / 'head-envelopes.json', measure.head_envelopes(args.head_pack, args.body_pack))
        written.append(str(output / 'head-envelopes.json'))
    if args.only in (None, 'seams'):
        write_json(output / 'seam-contract.json', measure.seam_contract(args.body_pack, [args.body_pack, *args.supermodels]))
        written.append(str(output / 'seam-contract.json'))
    print(json.dumps({'written': written}))


def command_brief(args):
    from . import brief
    document = brief.load(args.brief)
    if args.seal:  # refused where two materials are drawn too alike: nothing is written then
        brief.seal(document, args.seal)
    if args.adopt:
        brief.adopt(document, args.adopt)
    print(json.dumps({'model': document['model'], 'materials': {material['name']: material['kind'] for material in document['materials']},
                      'pads': document.get('pads', []), 'sealed': args.seal or args.adopt}))


def command_image(args):
    from . import reference
    images = reference.generate(args.brief, args.folder, args.seed, args.batch, args.reference, args.url, args.profile, args.deadline)
    print(json.dumps({'images': [str(path) for path in images]}))


def command_generate(args):
    from . import generate
    need = lambda *names: registry.require(all(getattr(args, name) is not None for name in names),
                                           f'{args.stage} needs ' + ', '.join('--' + name for name in names))
    if args.stage == 'calibrate':
        need('models')
        done = generate.calibrate(args.work, args.model, args.source, args.models, args.url)
    elif args.stage == 'geometry':
        need('models', 'fov')
        done = generate.geometry(args.work, args.model, args.source, args.fov, args.models, args.url)
    elif args.stage == 'appearance':
        need('models', 'fov', 'shape')
        done = generate.appearance(args.work, args.model, args.source, args.fov, args.shape, args.models, args.url)
    else:
        need('faces')
        done = generate.export(args.work, args.model, args.source, args.faces, args.fill, args.url)
    print(json.dumps({key: done.get(key) for key in ('folder', 'status', 'seconds', 'files', 'attempt', 'previews')}))


def command_register(args):
    from . import brief
    brief.register(args.folder, *args.image)
    print(json.dumps({'registered': [Path(path).name for path in args.image]}))


def command_admit(args):
    from . import brief
    document, folder = brief.admit(args.image, args.root)
    print(json.dumps({'model': document['model'], 'folder': str(folder)}))


def layout_library(folder):
    """The layout library `texture.layout` unwraps with, loaded from the folder that holds it."""
    registry.require(Path(folder).is_dir(), f'{folder} is no folder: --xatlas names the one that holds the layout library')
    sys.path.insert(0, str(Path(folder)))
    return importlib.import_module('xatlas')


def command_bake(args):
    from . import bake, brief
    sources = (args.mesh, args.colours, args.raw, args.xatlas)
    registry.require(all(sources) or (args.kept and not any(sources)),
                     'bake needs --mesh, --colours, --raw and --xatlas together, or --kept alone to tint stored parts again')
    record = bake.run(brief.load(args.brief), args.output, args.body_pack, args.number, mesh=args.mesh, colours=args.colours, raw=args.raw,
                      xatlas=layout_library(args.xatlas) if args.xatlas else None, kept=args.kept, body=args.body, tier=args.tier,
                      packs=args.pack, game=args.nwn_root, resources=args.resources, body_textures=args.body_textures,
                      capture=args.capture, say=lambda *words: print(*words, file=sys.stderr, flush=True))
    print(json.dumps({key: record.get(key) for key in ('model', 'body', 'number', 'models', 'gates', 'compiled')}))
    if not record['gates']['passed']:
        sys.exit(1)


def command_split(args):
    from . import bake
    parts, report = bake.resplit(args.capture, body_pack=args.body_pack)
    if args.output:
        bake.keep_parts(parts, args.output)
    print(json.dumps(report))
    if report['failures']:
        sys.exit(1)


def command_refit(args):
    from . import refit
    names = [name.strip() for name in args.parts.split(',')] if args.parts else None
    print(json.dumps(refit.run(args.kept, args.output, args.body_pack, args.source, args.target, names, body_textures=args.body_textures, seat_in=args.seat_in)))


def command_render(args):
    from . import view
    directions = tuple(name.strip() for name in args.views.split(',')) if args.views else tuple(view.DIRECTIONS)
    print(json.dumps(view.views(args.parts, args.output, args.body_pack, args.body, args.animations, args.clip, args.time,
                                args.focus, directions, args.size)))


def command_poses(args):
    from . import client, poses
    spec, labels = poses.spec(args.bake, args.output, args.stock, args.hak, tlk=args.tlk, preset=args.preset, without=args.without,
                              colours=json.loads(args.colours) if args.colours else None)
    if args.hold:
        spec['hold'] = args.hold  # seconds the game stays on each shot: longer where the machine is busy and the capture falls behind
    record = poses.build(spec, labels, args.output, args.nwn_root)
    if args.run:
        if args.wait:
            client.wait_free(args.wait)
        record['evidence'] = poses.run(args.nwn_root, record, labels, args.output, settle=args.settle)
    print(json.dumps({key: record[key] for key in ('module', 'shots', 'evidence') if key in record}))


def command_fixture(args):
    from . import client
    from . import client_fixture as fixture
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    record = fixture.build(spec, args.output, args.nwn_root)
    if args.run:
        record['evidence'] = client.run(args.nwn_root, record, Path(args.output) / 'captures',
                                        timeout=args.timeout, settle=args.settle)
    print(json.dumps(record))


def command_publish(args):
    from . import publish
    code = publish.command(args)
    if code:
        sys.exit(code)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='armorkit', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    # The handler lives under `handler`: `run` is the fixture command's own flag.
    p = commands.add_parser('registry', help='validate a registry and optionally write the SR_NWN handoff file')
    p.add_argument('registry'); p.add_argument('--publish', action='store_true'); p.add_argument('--handoff')
    p.set_defaults(handler=command_registry)
    p = commands.add_parser('tables', help='generate the twelve parts tables from a registry and stock tables')
    p.add_argument('registry'); p.add_argument('--stock', required=True, help='folder holding the stock parts_*.2da files')
    p.add_argument('--output', required=True); p.add_argument('--publish', action='store_true')
    p.set_defaults(handler=command_tables)
    p = commands.add_parser('measure', help='measure the seam contract and head envelopes from pack folders')
    p.add_argument('--body-pack', required=True); p.add_argument('--head-pack', required=True)
    p.add_argument('--supermodels', action='append', default=[], help='folder of extracted stock animation models')
    p.add_argument('--only', choices=('seams', 'heads'), help='measure one of the two files (heads need no --supermodels)')
    p.add_argument('--output', required=True)
    p.set_defaults(handler=command_measure)
    p = commands.add_parser('brief', help="check an outfit's brief, and seal a reference folder with it")
    p.add_argument('brief')
    p.add_argument('--seal', help='reference folder to seal: gets PROMPT.txt, the image prompt the materials give')
    p.add_argument('--adopt', help='reference folder whose image was made before the brief: its PROMPT.txt must be the brief\'s')
    p.set_defaults(handler=command_brief)
    p = commands.add_parser('image', help='make reference images from a brief on the local image engine')
    p.add_argument('brief'); p.add_argument('folder'); p.add_argument('--seed', type=int, required=True)
    p.add_argument('--batch', type=int, default=1); p.add_argument('--reference', action='append', default=[])
    p.add_argument('--url', default='http://127.0.0.1:8188'); p.add_argument('--profile', default='flux2-turbo-v1')
    p.add_argument('--deadline', type=float, default=1800)
    p.set_defaults(handler=command_image)
    p = commands.add_parser('generate', help='post one source job to the local engine: calibrate, geometry (counted), appearance or export')
    p.add_argument('stage', choices=('calibrate', 'geometry', 'appearance', 'export'))
    p.add_argument('work', help='folder holding one folder per model, and the attempts ledger')
    p.add_argument('model'); p.add_argument('source', help='the image, or for export the generated mesh')
    p.add_argument('--models', help="the engine's models folder (from the local runtime binding)")
    p.add_argument('--fov', type=float); p.add_argument('--shape', help='the saved shape of a geometry attempt')
    p.add_argument('--faces', type=int); p.add_argument('--fill', type=float, help='export a solid with its outside surface only')
    p.add_argument('--url', default='http://127.0.0.1:8188')
    p.set_defaults(handler=command_generate)
    p = commands.add_parser('register', help='record images as made from a sealed reference folder (another image route, a derived image)')
    p.add_argument('folder'); p.add_argument('image', nargs='+')
    p.set_defaults(handler=command_register)
    p = commands.add_parser('admit', help='check that an image comes from a sealed brief before it is taken further')
    p.add_argument('image'); p.add_argument('--root', required=True, help='folder searched for sealed reference folders')
    p.set_defaults(handler=command_admit)
    p = commands.add_parser('bake', help='bake a generated outfit into the parts a body wears, and check what was written')
    p.add_argument('brief'); p.add_argument('output'); p.add_argument('--number', type=int, required=True, help='the part number the models are written as')
    p.add_argument('--body-pack', required=True, help="folder holding the body's models"); p.add_argument('--body', default='pmh0')
    p.add_argument('--tier', type=int, default=2, choices=registry.TIERS, help='the seam tier the outfit is cut at')
    p.add_argument('--body-textures', help="folder holding the body's material files and maps, for an outfit that shows the body's skin")
    p.add_argument('--mesh', help='the exported mesh'); p.add_argument('--colours', help='the saved colour field of the appearance job')
    p.add_argument('--raw', help="the generator's own high-detail mesh, for the normal maps")
    p.add_argument('--xatlas', help='folder holding the layout library (from the local runtime binding)')
    p.add_argument('--kept', help='folder the baked parts are kept in; without --mesh they are tinted and written again from it')
    p.add_argument('--pack', action='append', default=[], help='pack folder whose model names the outfit may not take')
    p.add_argument('--nwn-root', help='game install folder: with it the models are compiled')
    p.add_argument('--resources', action='append', default=[], help='folder the compiler looks animations up in')
    p.add_argument('--capture', help='file to keep what the split is given in, for `split` to run it again')
    p.set_defaults(handler=command_bake)
    p = commands.add_parser('split', help="run a bake's split again, in seconds, on what `bake --capture` kept")
    p.add_argument('capture', help='the file `bake --capture` wrote')
    p.add_argument('--output', help='.npz file to write the parts to, for `render`')
    p.add_argument('--body-pack', help="folder of the body's models: an end under a slot left to the body is then measured against its skin")
    p.set_defaults(handler=command_split)
    p = commands.add_parser('refit', help="carry a bake's kept parts to another body by a rotation and a scale along each axis")
    p.add_argument('kept', help='the folder `bake --kept` kept the parts in'); p.add_argument('output', help='the folder the refit parts are kept in')
    p.add_argument('--body-pack', required=True, help="folder holding both bodies' models")
    p.add_argument('--from', dest='source', default='pmh0'); p.add_argument('--to', dest='target', required=True)
    p.add_argument('--parts', help='comma-separated parts to carry (default all)')
    p.add_argument('--body-textures', help="folder of the body's material files and maps: a part sharing its slot with the body's skin gets the other body's")
    p.add_argument('--seat-in', help="folder of parts baked on the other body: an end carried under one of them is seated in it")
    p.set_defaults(handler=command_refit)
    p = commands.add_parser('render', help="draw an outfit's parts offline, at rest or posed by one of the body's clips")
    p.add_argument('parts', help='the .npz `split --output` wrote, or a folder `bake --kept` kept parts in')
    p.add_argument('output', help='the image to write the views to')
    p.add_argument('--body-pack', required=True, help="folder holding the body's models"); p.add_argument('--body', default='pmh0')
    p.add_argument('--animations', action='append', default=[],
                   help='folder of extracted stock animation models the body inherits (game data, outside the repository); needed with --clip')
    p.add_argument('--clip', help='the clip to pose the parts by, as the game names it (conjure2: arms up)')
    p.add_argument('--time', type=float, default=0.5, help='how far through the clip, from 0 to 1')
    p.add_argument('--focus', default='shoulders', choices=('shoulders', 'hips', 'body'))
    p.add_argument('--views', help='comma-separated: left, right, front, back, left front, right back (default all)')
    p.add_argument('--size', type=int, default=520, help='pixels a side of each view')
    p.set_defaults(handler=command_render)
    p = commands.add_parser('poses', help='build the client check of a baked outfit in six poses, and optionally run it')
    p.add_argument('bake', help='the output folder of a bake compiled with --nwn-root')
    p.add_argument('output', help='a fresh folder for the fixture, its captures and the sheet')
    p.add_argument('--nwn-root', required=True, help='game install folder (from the local runtime binding)')
    p.add_argument('--stock', required=True, help='folder of the stock parts tables the outfit is added to')
    p.add_argument('--hak', action='append', default=[], required=True, help='built pack the fixture loads, highest priority first')
    p.add_argument('--tlk', help='talk table the fixture loads')
    p.add_argument('--preset', default='body', choices=('body', 'shoulders'), help='where the camera looks')
    p.add_argument('--without', action='append', default=[], help='also pose a second actor without the part in this slot (shoulder: no pads)')
    p.add_argument('--colours', help='JSON of the six armour colour channels, e.g. {"cloth1": 22}')
    p.add_argument('--run', action='store_true', help='start the game client on the fixture and capture its shots')
    p.add_argument('--wait', type=float, help='seconds to wait for another session\'s client to close first')
    p.add_argument('--settle', type=float, default=1.2, help='seconds between a shot line and its capture')
    p.add_argument('--hold', type=float, help='seconds the game stays on each shot (default 3): longer on a busy machine, where shots stall')
    p.set_defaults(handler=command_poses)
    p = commands.add_parser('fixture', help='build an isolated client fixture, and optionally run it')
    p.add_argument('--spec', required=True); p.add_argument('--output', required=True)
    p.add_argument('--nwn-root', required=True, help='game install folder (from the local runtime binding)')
    p.add_argument('--run', action='store_true', help='start the game client on the built fixture and capture its shots')
    p.add_argument('--timeout', type=float, help='seconds to wait for the run (default: scaled to the number of shots)')
    p.add_argument('--settle', type=float, default=1.5, help='seconds between a shot line and its capture')
    p.set_defaults(handler=command_fixture)
    p = commands.add_parser('publish', help='publish baked outfits into the srn_parts pack, with tables, registry, handoff and gates')
    p.add_argument('registry', help='the whole registry as it stands after the publication')
    p.add_argument('--bake', action='append', default=[], required=True, help="a bake's output folder, compiled at the part's registry number")
    p.add_argument('--stock', required=True, help="folder of the game's own parts_*.2da tables")
    p.add_argument('--record', action='append', default=[], help="MODEL=FILE: a file of the outfit's history to pin by hash (generation ledger, log, refit report)")
    p.add_argument('--brief', action='append', default=[], help='MODEL=FILE: the brief an outfit was baked from, where two briefs are of one model')
    p.add_argument('--body-pack', help="folder of the bodies' models (default: the repository's srn_body)")
    p.add_argument('--trial', help='scratch folder to write the publication into whatever the gates say, instead of the repository')
    p.add_argument('--dry-run', action='store_true', help='run the gates and print the report; write nothing')
    p.add_argument('--build', action='store_true', help='pack srn_parts and srn_2da once written (a trial: into its own output folder)')
    p.set_defaults(handler=command_publish)
    args = parser.parse_args(argv)
    args.handler(args)


if __name__ == '__main__':
    main()
