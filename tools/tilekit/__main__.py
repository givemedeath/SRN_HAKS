"""Command line for tilekit. `inventory` writes what a tileset draws (inventory.json, textures.csv) and the hashes of
its walkmeshes (walkmesh.json); `walkmesh` holds the tileset's walkmeshes against such a baseline and fails on any
that changed; `review` builds a module of the tileset on the built packs and captures the same views of it in the
game client each time, with an overlay folder shown instead of the packs' own files. `material` makes restyled
textures into such an overlay, from pictures `enlarge` and `redraw` leave; `lamps` and `shadows` write changed tile
models into it; `terrain` writes a building terrain copied under a name of its own, and descriptive palette names, into one;
`apply` moves an overlay whose look the user passed into the packs."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.tilekit'

from . import PARTS, inventory, require

REPO = Path(__file__).resolve().parents[2]


def _json(path):
    """A JSON file as the kit's specs are kept, with or without a byte-order mark (as Windows tools may write one)."""
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def review_command(chosen):
    from . import review  # here, so that asking for help imports nothing of the client
    spec = _json(chosen.spec); require(isinstance(spec, dict) and spec.get('tileset'), 'A review spec names its tileset')
    tileset = spec['tileset']  # an overlay's set file (a copied terrain's) is the one shown, so it is the one laid
    set_of = lambda name: (chosen.overlay / f'{name}.set' if chosen.overlay and (chosen.overlay / f'{name}.set').is_file() else chosen.repo / f'srn_t_{name}' / f'{name}.set').read_bytes().decode('cp1252')
    shared = spec.get('shared', {}); haks = tuple(spec.get('haks', review.HAKS))
    try:
        areas, shots = review.plan(set_of(tileset), spec, parts=tuple(part for part in chosen.parts.split(',') if part),
                                   built_area=review.read_area(chosen.area) if chosen.area else None,
                                   sets={name: set_of(name) for name in shared.get('tilesets', {})},
                                   table=(chosen.repo / 'srn_2da' / 'placeables.2da').read_text(encoding='cp1252') if shared.get('placeables') else None)
    except KeyError as error:
        raise ValueError(f'The review spec lacks {error}') from error
    if chosen.views:
        shots = [shot for shot in shots if shot['label'].startswith(tuple(chosen.views.split(',')))]
        require(shots, 'No view begins with ' + ' or '.join(chosen.views.split(',')))
    shots = shots[::max(1, chosen.every)]; kept = {shot['area'] for shot in shots}; areas = [area for area in areas if area['tag'] in kept]
    lacking = sorted({f'srn_t_{area["tileset"]}' for area in areas} - set(haks))  # each tileset laid is one of this project's packs (its set file is read there)
    require(not lacking, 'The module would not load the pack of every tileset it lays: add ' + ', '.join(lacking) + ' to the spec\'s haks')
    record = review.build(chosen.name, areas, shots, chosen.out, chosen.game, chosen.built, overlay=chosen.overlay, haks=haks)
    told = {'module': record['module'], 'areas': [area['tag'] for area in areas], 'views': len(shots), 'overlay': record['overlay']}
    if not chosen.no_run:
        told.update(review.capture(chosen.game, record, chosen.out))
        told['captures'] = len(told['captures']); told['sheets'] = review.sheets(chosen.out)
    print(json.dumps(told, indent=2))
    return 0


def material_command(chosen):
    from tools import shared_tools
    from . import material
    spec = _json(chosen.spec)
    masters = chosen.masters or shared_tools.tools_root(chosen.repo)[0] / 'tilekit' / 'masters'
    crunch = shared_tools.resolve_tool('crunch', chosen.repo)['path']
    told = material.build(spec, chosen.repo, masters, chosen.out, crunch, only=chosen.only.split(',') if chosen.only else None, enlarged=chosen.enlarged,
                          redrawn=chosen.redrawn, stock=chosen.stock)
    print(json.dumps(told, indent=2))
    return 0


def redraw_command(chosen):
    from . import redraw
    spec = _json(chosen.spec)
    require(bool(chosen.codex) != bool(chosen.bindings), 'A redraw is drawn by --codex (the Codex CLI) or by --bindings (the local Qwen model on the shared ComfyUI)')
    if chosen.bindings:
        from tools.headkit.comfy import Client
        run = redraw.qwen(Client(chosen.url), _json(chosen.bindings), chosen.bindings, seed=chosen.seed)
    else:
        run = redraw.codex(chosen.codex)
    told = redraw.redraw(spec, chosen.repo, chosen.out, run, only=chosen.only.split(',') if chosen.only else None,
                         enlarged=chosen.enlarged, workers=1 if chosen.bindings else chosen.workers, stock=chosen.stock)
    failed = {name: state for name, state in told.items() if state.startswith('failed')}
    print(json.dumps({'redrawn': sum(state == 'redrawn' for state in told.values()), 'composed': sum(state == 'composed' for state in told.values()), 'kept': sum(state == 'kept' for state in told.values()), 'failed': failed}, indent=1))
    return 1 if failed else 0


def lamps_command(chosen):
    from . import lamps
    radius = lamps.RADIUS if chosen.radius is None else chosen.radius
    told = lamps.move(chosen.repo, chosen.tileset, chosen.out, radius=radius)
    states = sorted(set(told.values()))
    print(json.dumps({'radius': radius, **{state: sorted(name for name, one in told.items() if one == state) if state != 'moved' else sum(one == state for one in told.values()) for state in states}}, indent=1))
    return 0


def shadows_command(chosen):
    from . import shadows
    told = shadows.quiet(chosen.repo, chosen.tileset, chosen.out)
    print(json.dumps({'models': len(told), 'trims': sum(told.values())}))
    return 0


def apply_command(chosen):
    from . import apply
    spec = _json(chosen.spec) if chosen.spec else None  # none: the overlay's changed models alone
    print(json.dumps(apply.apply(chosen.repo, spec, chosen.overlay)))
    return 0


def enlarge_command(chosen):
    from tools.headkit.comfy import Client
    from . import enlarge
    spec = _json(chosen.spec); local = _json(chosen.bindings)
    told = enlarge.enlarge(Client(chosen.url), local, chosen.bindings, chosen.repo, spec, chosen.out, only=chosen.only.split(',') if chosen.only else None, stock=chosen.stock)
    print(json.dumps({state: sum(one == state for one in told.values()) for state in ('enlarged', 'kept')}))
    return 0


def terrain_command(chosen):
    from . import terrain
    source = chosen.spec.resolve().relative_to(chosen.repo.resolve()).as_posix() if chosen.spec.resolve().is_relative_to(chosen.repo.resolve()) else chosen.spec.name
    print(json.dumps(terrain.copy(chosen.repo, _json(chosen.spec), chosen.out, source=source), indent=1))
    return 0


def main(arguments=None):
    parser = argparse.ArgumentParser(prog='tilekit', description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    one = commands.add_parser('inventory', help='write the inventory and walkmesh baseline of a tileset')
    one.add_argument('--tileset', required=True); one.add_argument('--out', required=True, type=Path); one.add_argument('--repo', type=Path, default=REPO)
    two = commands.add_parser('walkmesh', help='compare the walkmeshes of a tileset with a baseline')
    two.add_argument('--tileset', required=True); two.add_argument('--baseline', required=True, type=Path); two.add_argument('--repo', type=Path, default=REPO)
    three = commands.add_parser('review', help='build the review module of a tileset on the built packs and capture its views in the client')
    three.add_argument('--spec', required=True, type=Path, help='the tileset\'s review spec (docs/tilesets/<tileset>/review.json)')
    three.add_argument('--game', required=True, type=Path, help='the game install folder'); three.add_argument('--built', required=True, type=Path, help='the folder the packs were built into')
    three.add_argument('--out', required=True, type=Path, help='a fresh folder for the module and its captures'); three.add_argument('--name', required=True, help='the module\'s name, a resref of at most 11 characters')
    three.add_argument('--area', type=Path, help='an area someone built with the tileset (.are, or its JSON)')
    three.add_argument('--overlay', type=Path, help='a folder of files shown instead of the packs\' own')
    three.add_argument('--parts', default=','.join(PARTS), help=', '.join(PARTS) + ' (default: all)')
    three.add_argument('--views', help='only the views whose label begins with one of these, comma separated')
    three.add_argument('--every', type=int, default=1, help='only every nth view, for a short look')
    three.add_argument('--no-run', action='store_true', help='build the module and stop'); three.add_argument('--repo', type=Path, default=REPO)
    four = commands.add_parser('material', help='make the restyled textures of a material spec: DDS maps and material files into a folder')
    four.add_argument('--spec', required=True, type=Path, help='the tileset\'s material spec (docs/tilesets/<tileset>/materials.json)')
    four.add_argument('--out', required=True, type=Path, help='the folder written to: a review\'s overlay, until a texture is accepted')
    four.add_argument('--masters', type=Path, help='the folder of tiling scans (default: tilekit/masters in the shared tool root)')
    four.add_argument('--only', help='only these textures, comma separated'); four.add_argument('--repo', type=Path, default=REPO)
    four.add_argument('--enlarged', type=Path, help='the folder `enlarge` filled, for the textures the spec has `doubled`')
    four.add_argument('--redrawn', type=Path, help='the folder `redraw` filled, for the textures the spec has `redrawn`')
    four.add_argument('--stock', type=Path, help='a folder of base-game pictures read out of the install, for base-game textures')
    five = commands.add_parser('enlarge', help='enlarge the textures a material spec has `doubled` with the upscaling model of the shared ComfyUI')
    five.add_argument('--spec', required=True, type=Path); five.add_argument('--out', required=True, type=Path, help='the folder the enlarged pictures are kept in')
    five.add_argument('--bindings', required=True, type=Path, help='local JSON with absolute comfyInput and comfyOutput')
    five.add_argument('--url', default='http://127.0.0.1:8188'); five.add_argument('--only', help='only these textures, comma separated'); five.add_argument('--repo', type=Path, default=REPO)
    five.add_argument('--stock', type=Path, help='a folder of base-game pictures read out of the install, for base-game textures')
    six = commands.add_parser('redraw', help='draw the textures of a redraw list again with an image generator, on the layout they have')
    six.add_argument('--spec', required=True, type=Path, help='the tileset\'s redraw list (docs/tilesets/<tileset>/redraw.json)')
    six.add_argument('--out', required=True, type=Path, help='the folder the redrawn pictures are kept in')
    six.add_argument('--codex', type=Path, help='the Codex CLI (codex.exe), whose image generation draws them')
    six.add_argument('--bindings', type=Path, help='instead of --codex: local JSON with absolute comfyInput and comfyOutput, for the Qwen edit model on the shared ComfyUI')
    six.add_argument('--url', default='http://127.0.0.1:8188'); six.add_argument('--seed', type=int, default=1)
    six.add_argument('--enlarged', type=Path, help='the folder `enlarge` filled: a cleaner reference where it has one')
    six.add_argument('--workers', type=int, default=3, help='how many are drawn at a time'); six.add_argument('--only', help='only these textures, comma separated')
    six.add_argument('--stock', type=Path, help='a folder of base-game pictures read out of the install, for base-game textures')
    six.add_argument('--repo', type=Path, default=REPO)
    seven = commands.add_parser('lamps', help='move the lamps of a tileset\'s tiles from source lights (drawn as fire) to main lights, in model copies')
    seven.add_argument('--tileset', required=True); seven.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay')
    seven.add_argument('--radius', type=float, help='the radius the moved lights are given (default: lamps.RADIUS, 7)'); seven.add_argument('--repo', type=Path, default=REPO)
    eight = commands.add_parser('shadows', help='make the small trims of a tileset\'s tiles cast no shadow, in model copies (a copy already in --out is changed)')
    eight.add_argument('--tileset', required=True); eight.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay')
    eight.add_argument('--repo', type=Path, default=REPO)
    nine = commands.add_parser('apply', help='move a review overlay whose look the user passed into the packs: materials, maps and changed models')
    nine.add_argument('--spec', type=Path, help='the tileset\'s material spec: the textures moved (without it, only the overlay\'s changed models)')
    nine.add_argument('--overlay', required=True, type=Path, help='the review overlay the look was passed on'); nine.add_argument('--repo', type=Path, default=REPO)
    ten = commands.add_parser('terrain', help='copy building terrains under names of their own and make the palette names descriptive, into a folder')
    ten.add_argument('--spec', required=True, type=Path, help='the tileset\'s terrain spec (docs/tilesets/<tileset>/terrains.json)')
    ten.add_argument('--out', required=True, type=Path, help='the folder written to: a review\'s overlay'); ten.add_argument('--repo', type=Path, default=REPO)
    chosen = parser.parse_args(arguments)
    try:
        if chosen.command == 'terrain':
            return terrain_command(chosen)
        if chosen.command == 'apply':
            return apply_command(chosen)
        if chosen.command == 'shadows':
            return shadows_command(chosen)
        if chosen.command == 'lamps':
            return lamps_command(chosen)
        if chosen.command == 'enlarge':
            return enlarge_command(chosen)
        if chosen.command == 'redraw':
            return redraw_command(chosen)
        if chosen.command == 'review':
            return review_command(chosen)
        if chosen.command == 'material':
            return material_command(chosen)
        told, walkmesh = inventory.inventory(chosen.repo, chosen.tileset.lower(), walkmesh_only=chosen.command == 'walkmesh')
        if chosen.command == 'inventory':
            written = inventory.write(chosen.out, told, walkmesh)
            print(json.dumps({'written': written, 'set': told['set'], 'edge': told['edge'], 'forms': told['forms'], 'textures': len(told['textures']),
                              'surface': told['surface'], 'coverage': told['coverage']}, indent=2))
            return 0
        baseline = _json(chosen.baseline)
        require(isinstance(baseline, dict) and baseline.get('tileset') == walkmesh['tileset'] and isinstance(baseline.get('models'), dict),
                f"{chosen.baseline.name} is not a walkmesh baseline of {walkmesh['tileset']}")
        lines = inventory.moved(baseline, walkmesh)
        print('\n'.join(lines) if lines else f"{len(walkmesh['models'])} walkmeshes as the baseline has them")
        return 1 if lines else 0
    except (ValueError, OSError) as error:  # a refusal, or a file that is not there: said, not thrown
        print(f'tilekit: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
