"""Command line for tilekit. `inventory` writes what a tileset draws (inventory.json, textures.csv) and the hashes of
its walkmeshes (walkmesh.json); `walkmesh` holds the tileset's walkmeshes against such a baseline and fails on any
that changed; `review` builds a module of the tileset on the built packs and captures the same views of it in the
game client each time, with an overlay folder shown instead of the packs' own files."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.tilekit'

from . import PARTS, inventory, require

REPO = Path(__file__).resolve().parents[2]


def review_command(chosen):
    from . import review  # here, so that asking for help imports nothing of the client
    spec = json.loads(chosen.spec.read_text(encoding='utf-8')); require(isinstance(spec, dict) and spec.get('tileset'), 'A review spec names its tileset')
    tileset = spec['tileset']
    set_text = (chosen.repo / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252')
    try:
        areas, shots = review.plan(set_text, spec, parts=tuple(part for part in chosen.parts.split(',') if part),
                                   built_area=review.read_area(chosen.area) if chosen.area else None)
    except KeyError as error:
        raise ValueError(f'The review spec lacks {error}') from error
    if chosen.views:
        shots = [shot for shot in shots if shot['label'].startswith(tuple(chosen.views.split(',')))]
        require(shots, 'No view begins with ' + ' or '.join(chosen.views.split(',')))
    shots = shots[::max(1, chosen.every)]; kept = {shot['area'] for shot in shots}; areas = [area for area in areas if area['tag'] in kept]
    record = review.build(chosen.name, areas, shots, chosen.out, chosen.game, chosen.built, overlay=chosen.overlay)
    told = {'module': record['module'], 'areas': [area['tag'] for area in areas], 'views': len(shots), 'overlay': record['overlay']}
    if not chosen.no_run:
        told.update(review.capture(chosen.game, record, chosen.out))
        told['captures'] = len(told['captures']); told['sheets'] = review.sheets(chosen.out)
    print(json.dumps(told, indent=2))
    return 0


def material_command(chosen):
    from tools import shared_tools
    from . import material
    spec = json.loads(chosen.spec.read_text(encoding='utf-8'))
    masters = chosen.masters or shared_tools.tools_root(chosen.repo)[0] / 'tilekit' / 'masters'
    crunch = shared_tools.resolve_tool('crunch', chosen.repo)['path']
    told = material.build(spec, chosen.repo, masters, chosen.out, crunch, only=chosen.only.split(',') if chosen.only else None, enlarged=chosen.enlarged)
    print(json.dumps(told, indent=2))
    return 0


def enlarge_command(chosen):
    from tools.headkit.comfy import Client
    from . import enlarge
    spec = json.loads(chosen.spec.read_text(encoding='utf-8')); local = json.loads(chosen.bindings.read_text(encoding='utf-8'))
    told = enlarge.enlarge(Client(chosen.url), local, chosen.bindings, chosen.repo, spec, chosen.out, only=chosen.only.split(',') if chosen.only else None)
    print(json.dumps({state: sum(one == state for one in told.values()) for state in ('enlarged', 'kept')}))
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
    three.add_argument('--parts', default=','.join(PARTS), help='block, grid, area (default: all)')
    three.add_argument('--views', help='only the views whose label begins with one of these, comma separated')
    three.add_argument('--every', type=int, default=1, help='only every nth view, for a short look')
    three.add_argument('--no-run', action='store_true', help='build the module and stop'); three.add_argument('--repo', type=Path, default=REPO)
    four = commands.add_parser('material', help='make the restyled textures of a material spec: DDS maps and material files into a folder')
    four.add_argument('--spec', required=True, type=Path, help='the tileset\'s material spec (docs/tilesets/<tileset>/materials.json)')
    four.add_argument('--out', required=True, type=Path, help='the folder written to: a review\'s overlay, until a texture is accepted')
    four.add_argument('--masters', type=Path, help='the folder of tiling scans (default: tilekit/masters in the shared tool root)')
    four.add_argument('--only', help='only these textures, comma separated'); four.add_argument('--repo', type=Path, default=REPO)
    four.add_argument('--enlarged', type=Path, help='the folder `enlarge` filled, for the textures the spec has `doubled`')
    five = commands.add_parser('enlarge', help='enlarge the textures a material spec has `doubled` with the upscaling model of the shared ComfyUI')
    five.add_argument('--spec', required=True, type=Path); five.add_argument('--out', required=True, type=Path, help='the folder the enlarged pictures are kept in')
    five.add_argument('--bindings', required=True, type=Path, help='local JSON with absolute comfyInput and comfyOutput')
    five.add_argument('--url', default='http://127.0.0.1:8188'); five.add_argument('--only', help='only these textures, comma separated'); five.add_argument('--repo', type=Path, default=REPO)
    chosen = parser.parse_args(arguments)
    try:
        if chosen.command == 'enlarge':
            return enlarge_command(chosen)
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
        baseline = json.loads(chosen.baseline.read_text(encoding='utf-8'))
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
