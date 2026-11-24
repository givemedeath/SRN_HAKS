"""Command line for tilekit. `inventory` writes what a tileset draws (inventory.json, textures.csv) and the hashes of
its walkmeshes (walkmesh.json); `walkmesh` holds the tileset's walkmeshes against such a baseline and fails on any
that changed; `review` builds a module of the tileset on the built packs and captures the same views of it in the
game client each time, with an overlay folder shown instead of the packs' own files. `material` makes restyled
textures into such an overlay, from pictures `enlarge` and `redraw` leave; `lamps` and `shadows` write changed tile
models into it, `detail` adds kit pieces to tiles there and `remesh` replaces a tile's visible meshes there; `count`
says what each tile costs to draw (faces, mesh nodes, materials) against a budget; `terrain` writes a building terrain copied under a name of its own, and descriptive palette names, into one;
`apply` moves an overlay whose look the user passed into the packs; `compile` makes the packs' tile models from their
ASCII sources (`sources/<pack>/`) with NeverBlender. The working tools of a restyle (`commands`) are told of in
docs/tilesets/tilekit-tools.md."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.tilekit'

from . import PARTS, commands as extra, inventory, require

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
    views = tuple(view for view in (chosen.views or '').split(',') if view)  # a stray comma asks for no view, not every one
    if chosen.views is not None:
        require(views, 'No view named in --views')
        shots = [shot for shot in shots if shot['label'].startswith(views)]
        require(shots, 'No view begins with ' + ' or '.join(views))
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
    told = lamps.move(chosen.repo, chosen.tileset, chosen.out, radius=radius, shared=chosen.shared)
    states = sorted(set(told.values()))
    print(json.dumps({'radius': radius, **{state: sorted(name for name, one in told.items() if one == state) if state != 'moved' else sum(one == state for one in told.values()) for state in states}}, indent=1))
    return 0


def daylight_command(chosen):
    from . import daylight
    told = daylight.write(chosen.repo, chosen.tileset, chosen.out, _json(chosen.spec)['lit'], chosen.shared)
    print(json.dumps({'models': len(told['models']), 'lit': sum(told['models'].values()), 'panes': told['panes'], 'refused': told['refused']}, indent=1))
    return 0


def unique_command(chosen):
    from . import unique
    told = unique.write(chosen.repo, chosen.pack)
    print(json.dumps({'models': len(told), 'renamed': sum(told.values())}))
    return 0


def shadows_command(chosen):
    from . import shadows
    told = shadows.quiet(chosen.repo, chosen.tileset, chosen.out, shared=chosen.shared)
    print(json.dumps({'models': len(told), 'trims': sum(told.values())}))
    return 0


def detail_command(chosen):
    from . import detail
    told = detail.detail(chosen.repo, _json(chosen.spec), chosen.kit, chosen.out)
    print(json.dumps(told, indent=1))
    return 0


def remesh_command(chosen):
    from . import remesh
    told = remesh.remesh(chosen.repo, chosen.tileset, [name for name in chosen.tiles.split(',') if name], chosen.source, chosen.out, joins=chosen.joins, add=chosen.add)
    print(json.dumps(told, indent=1))
    return 0


def crown_command(chosen):
    from . import crown
    told = crown.write(chosen.repo, chosen.tileset, chosen.terrain, [name for name in chosen.tiles.split(',') if name], chosen.out, chosen.overlay)
    print(json.dumps(told, indent=1))
    return 0


def count_command(chosen):
    from . import count
    budget = {key: value for key, value in (('faces', chosen.faces), ('nodes', chosen.nodes), ('materials', chosen.materials)) if value is not None}
    told = count.count(chosen.repo, chosen.tileset, chosen.overlay, budget)
    if chosen.out:
        chosen.out.write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'tiles': len(told['tiles']), 'summary': told['summary'], 'over': told['over']}, indent=1))
    return 1 if told['over'] else 0


def doors_command(chosen):
    from . import doors
    found = doors.doors(chosen.repo); written = doors.write(chosen.out, found)
    print(json.dumps({'written': written, 'doors': len(found), 'used by tiles': sum(1 for door in found if door['tileHooks']),
                      'placed only': sum(1 for door in found if door['genericdoors'] and not door['doortypes'])}, indent=1))
    return 0


def apply_command(chosen):
    from . import apply
    spec = _json(chosen.spec) if chosen.spec else None  # none: the overlay's changed models alone
    from .compiled import compile_models, toolchain
    if chosen.blender or chosen.addon:
        toolchain(chosen.blender, chosen.addon)  # both, checked before anything is written
    compiler = (lambda keys: compile_models(chosen.repo, chosen.blender, chosen.addon, keys)) if chosen.blender or chosen.addon else None
    print(json.dumps(apply.apply(chosen.repo, spec, chosen.overlay, compiler)))
    return 0


def compile_command(chosen):
    from . import compiled
    if chosen.check:
        problems = compiled.check(chosen.repo); print(json.dumps({'problems': problems}, indent=1)); return 1 if problems else 0
    compiled.toolchain(chosen.blender, chosen.addon)  # before anything moves
    moved = compiled.adopt(chosen.repo, chosen.adopt) if chosen.adopt else []
    told = compiled.compile_models(chosen.repo, chosen.blender, chosen.addon, chosen.model or None)
    print(json.dumps({'adopted': len(moved), **told}, indent=1))
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


def merge_command(chosen):
    from . import merge
    lock = chosen.lock or chosen.spec.with_name('merged.json'); spec = _json(chosen.spec)
    if chosen.check:
        changed = merge.stale(chosen.repo, spec, chosen.spec, lock)
        print(json.dumps({'stale': changed}, indent=1))
        return 1 if changed else 0
    print(json.dumps(merge.merge(chosen.repo, chosen.spec, lock), indent=1))
    return 0


def joins_command(chosen):
    from . import joins
    lock = chosen.lock or chosen.spec.with_name('joins-built.json')
    if chosen.check:
        changed = joins.stale(chosen.repo, chosen.spec, lock)
        print(json.dumps({'stale': changed}, indent=1))
        return 1 if changed else 0
    print(json.dumps(joins.build(chosen.repo, chosen.spec, lock), indent=1))
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
    seven.add_argument('--shared', action='append', default=[], help='a tileset that draws these tiles too and takes the change with them (the merged set)')
    eight = commands.add_parser('shadows', help='make the small trims of a tileset\'s tiles cast no shadow, in model copies (a copy already in --out is changed)')
    eight.add_argument('--tileset', required=True); eight.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay')
    eight.add_argument('--repo', type=Path, default=REPO); eight.add_argument('--shared', action='append', default=[], help='a tileset that draws these tiles too and takes the change with them (the merged set)')
    lit = commands.add_parser('daylight', help='make the lit panes of a tileset\'s tiles clear by day and full by night, in model copies (a copy already in --out is changed)')
    lit.add_argument('--tileset', required=True); lit.add_argument('--spec', required=True, type=Path, help='the list of lit textures (docs/tilesets/<set>/daylight.json)')
    lit.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay'); lit.add_argument('--repo', type=Path, default=REPO)
    lit.add_argument('--shared', action='append', default=[], help='a tileset that draws these tiles too and takes the change with them (the merged set); repeat for more')
    named = commands.add_parser('unique', help='give the nodes of an adopted tile pack\'s ASCII sources names of one word that no other node has, in place (then: compile)')
    named.add_argument('--pack', required=True); named.add_argument('--repo', type=Path, default=REPO)
    nine = commands.add_parser('apply', help='move a review overlay whose look the user passed into the packs: materials, maps and changed models')
    nine.add_argument('--spec', type=Path, help='the tileset\'s material spec: the textures moved (without it, only the overlay\'s changed models)')
    nine.add_argument('--overlay', required=True, type=Path, help='the review overlay the look was passed on'); nine.add_argument('--repo', type=Path, default=REPO)
    nine.add_argument('--blender', type=Path, help='the Blender that runs NeverBlender: needed when the overlay changes tile models (compiled into the packs)')
    nine.add_argument('--addon', type=Path, help='the NeverBlender add-on folder, with its bundled cleanmodels')
    sixteen = commands.add_parser('compile', help='compile tile models from their ASCII sources (sources/<pack>/) into the packs, or --check the pairs')
    sixteen.add_argument('--blender', type=Path, help='the Blender that runs NeverBlender'); sixteen.add_argument('--addon', type=Path, help='the NeverBlender add-on folder, with its bundled cleanmodels')
    sixteen.add_argument('--model', action='append', help='<pack>/<name>.mdl to compile (default: every source whose binary is missing or out of date)')
    sixteen.add_argument('--adopt', action='append', help='a tile pack whose ASCII models move to sources/ first (once per pack)')
    sixteen.add_argument('--check', action='store_true', help='only check that every source has the binary the manifest pins'); sixteen.add_argument('--repo', type=Path, default=REPO)
    merged = commands.add_parser('merge', help='write one set file, palette and edge table of several tilesets, under the names of a names file')
    merged.add_argument('--spec', required=True, type=Path, help='the merge spec (docs/tilesets/<set>/merge.json)')
    merged.add_argument('--lock', type=Path, help='the record of what a merge read and wrote (merged.json beside the spec without it)')
    merged.add_argument('--check', action='store_true', help='write nothing: say what has changed since the last merge (exit 1 when anything has)')
    merged.add_argument('--repo', type=Path, default=REPO)
    cut = commands.add_parser('joins', help='write the join tiles of a merged tileset: the tiles where one family meets another (then: compile)')
    cut.add_argument('--spec', required=True, type=Path, help='the joins spec (docs/tilesets/<set>/joins.json)')
    cut.add_argument('--lock', type=Path, help='the record of what a build read and wrote (joins-built.json beside the spec without it)')
    cut.add_argument('--check', action='store_true', help='write nothing: say what has changed since the last build (exit 1 when anything has)')
    cut.add_argument('--repo', type=Path, default=REPO)
    ten = commands.add_parser('terrain', help='copy building terrains under names of their own and make the palette names descriptive, into a folder')
    ten.add_argument('--spec', required=True, type=Path, help='the tileset\'s terrain spec (docs/tilesets/<tileset>/terrains.json)')
    ten.add_argument('--out', required=True, type=Path, help='the folder written to: a review\'s overlay'); ten.add_argument('--repo', type=Path, default=REPO)
    eleven = commands.add_parser('detail', help='add kit pieces to a tileset\'s tiles from a placement spec, in model copies (a copy already in --out is changed)')
    eleven.add_argument('--spec', required=True, type=Path, help='the placement spec: {tileset, tiles: {model: [{piece, at, turn, scale}]}}')
    eleven.add_argument('--kit', required=True, type=Path, help='the folder of kit pieces, <piece>.mdl uncompiled')
    eleven.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay'); eleven.add_argument('--repo', type=Path, default=REPO)
    twelve = commands.add_parser('remesh', help='replace the visible meshes of tiles with rebuilt ones, keeping walkmesh, hooks and lamps, in model copies')
    twelve.add_argument('--tileset', required=True); twelve.add_argument('--tiles', required=True, help='the tile models rebuilt, comma separated')
    twelve.add_argument('--source', required=True, type=Path, help='the folder of rebuilds, <tile>.mdl uncompiled in the tile\'s coordinates')
    twelve.add_argument('--out', required=True, type=Path, help='the folder the changed models are written to: a review\'s overlay'); twelve.add_argument('--repo', type=Path, default=REPO)
    twelve.add_argument('--joins', help='a terrain whose tiles may change their sides where they meet one another alike (a crown)')
    twelve.add_argument('--add', action='store_true', help="keep the tiles' own meshes and draw the rebuilds as well (a crown)")
    thirteen = commands.add_parser('count', help='faces, rendered mesh nodes and materials of each tile, against a budget (exit 1 when any is over)')
    thirteen.add_argument('--tileset', required=True); thirteen.add_argument('--overlay', type=Path, help='a review overlay, read before the packs')
    thirteen.add_argument('--faces', type=int); thirteen.add_argument('--nodes', type=int); thirteen.add_argument('--materials', type=int)
    thirteen.add_argument('--out', type=Path, help='a JSON file for every tile\'s counts'); thirteen.add_argument('--repo', type=Path, default=REPO)
    fourteen = commands.add_parser('doors', help='list the door pack\'s models: family, kind, faces, textures, and the table rows and tile hooks that use them')
    fourteen.add_argument('--out', required=True, type=Path, help='the folder doors.json and doors.csv are written to'); fourteen.add_argument('--repo', type=Path, default=REPO)
    fifteen = commands.add_parser('crown', help='write rebuilds of a tower terrain\'s tiles with a parapet, cornice and set-back screen, for remesh --joins')
    fifteen.add_argument('--tileset', required=True); fifteen.add_argument('--terrain', required=True, help='the tower\'s terrain, as the set file names it')
    fifteen.add_argument('--tiles', required=True, help='its tile models, comma separated'); fifteen.add_argument('--out', required=True, type=Path, help='the folder of rebuilds: remesh --source')
    fifteen.add_argument('--overlay', type=Path, help='a review overlay read before the packs (a copied terrain\'s)'); fifteen.add_argument('--repo', type=Path, default=REPO)
    more = extra.add(commands, REPO)
    chosen = parser.parse_args(arguments)
    try:
        if chosen.command in more:
            return more[chosen.command](chosen)
        if chosen.command == 'doors':
            return doors_command(chosen)
        if chosen.command == 'crown':
            return crown_command(chosen)
        if chosen.command == 'detail':
            return detail_command(chosen)
        if chosen.command == 'remesh':
            return remesh_command(chosen)
        if chosen.command == 'count':
            return count_command(chosen)
        if chosen.command == 'merge':
            return merge_command(chosen)
        if chosen.command == 'joins':
            return joins_command(chosen)
        if chosen.command == 'terrain':
            return terrain_command(chosen)
        if chosen.command == 'apply':
            return apply_command(chosen)
        if chosen.command == 'compile':
            return compile_command(chosen)
        if chosen.command == 'daylight':
            return daylight_command(chosen)
        if chosen.command == 'unique':
            return unique_command(chosen)
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
    except KeyError as error:  # a spec (terrain, material, redraw, enlarge) without a key its command reads
        print(f'tilekit: the spec lacks {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
