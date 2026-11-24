"""The command line of the restyle's working tools (`docs/tilesets/tilekit-tools.md`), kept apart from `__main__` so that
file gains only their registration. Nothing of a tool is imported before its command runs."""
import json
from pathlib import Path


def _tileset(parser, repo):
    parser.add_argument('--tileset', required=True); parser.add_argument('--repo', type=Path, default=repo)
    return parser


def _names(text, option=None):
    """The names of a comma separated list; a list of `option` that was given and names nothing is refused, not read as all."""
    from . import require
    found = [name for name in (text or '').split(',') if name]
    require(option is None or text is None or found, f'Nothing named in {option}')
    return found


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _told(told):
    print(json.dumps(told, indent=1))


def repair_command(chosen):
    from . import repair
    told = repair.repair(chosen.repo, chosen.tileset, models=_names(chosen.models, '--models'), write=chosen.write)
    _told({'written': chosen.write, 'models': told})
    return 0


def propose_command(chosen):
    from . import family
    written, told = family.propose(chosen.repo, family.read(chosen.spec), chosen.kit)
    chosen.out.write_text(json.dumps(written, indent=1) + '\n', encoding='utf-8', newline='\n'); _told(told)
    return 1 if told['over'] else 0


def openings_command(chosen):
    from . import openings
    told = openings.openings(chosen.repo, chosen.tileset, _names(chosen.black, '--black'), tuple(_names(chosen.types, '--types')))
    chosen.out.write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8', newline='\n')
    sizes = {}
    for one in told['hooks']:
        size = 'not measured' if 'note' in one else f"{one['width']} x {one['height']}"; sizes[size] = sizes.get(size, 0) + 1
    _told({'hooks': dict(sorted(sizes.items(), key=lambda one: -one[1])), 'black': {kind: sum(one['kind'] == kind for one in told['black']) for kind in ('door', 'window')}})
    return 0


def _most(chosen):
    from . import require
    require(chosen.all or chosen.most > 0, '--most is at least one view')
    return None if chosen.all else chosen.most


def family_review_command(chosen):
    from . import family_review
    _told(family_review.run(chosen.repo, _json(chosen.spec), chosen.out, chosen.name, chosen.game, chosen.built, overlay=chosen.overlay, base=chosen.spec.parent,
                            views=_names(chosen.views, '--views'), most=_most(chosen), start=not chosen.no_run))
    return 0


def perf_command(chosen):
    from . import perf
    told = perf.run(chosen.repo, _json(chosen.spec), chosen.out, chosen.name, chosen.game, chosen.built, overlay=chosen.overlay, base=chosen.spec.parent,
                    views=_names(chosen.views, '--views'), most=_most(chosen), cap=chosen.cap)
    _told({**told, 'captures': len(told['captures']), 'stamps': len(told['stamps'])})
    return 0


def rank_command(chosen):
    from . import audit
    told = audit.rank(chosen.repo, chosen.tileset, _names(chosen.ground, '--ground')); chosen.out.write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8', newline='\n')
    _told({'tiles': len(told), 'plainest': [row['tile'] for row in told[:chosen.show]]}); return 0


def shared_command(chosen):
    from . import audit
    _told(audit.shared(chosen.repo, chosen.tileset, _json(chosen.spec)['textures'])); return 0


def placements_command(chosen):
    from . import audit
    told = {path.as_posix(): audit.placements(chosen.repo, _json(path), chosen.kit) for path in chosen.spec}; _told(told); return 1 if any(told.values()) else 0


def sketch_command(chosen):
    from . import require, sketch
    from .family_review import texts_of
    wanted = [name.lower() for name in _names(chosen.models)]
    texts = texts_of(chosen.repo, chosen.tileset.lower(), chosen.overlay, wanted)
    missing = sorted(set(wanted) - set(texts)); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    _told({'sketched': sketch.sketches({name: texts[name] for name in wanted}, chosen.out)}); return 0


def props_command(chosen):
    from tools import shared_tools
    from . import sketch
    masters = chosen.masters or shared_tools.tools_root(chosen.repo)[0] / 'tilekit' / 'masters'
    _told(sketch.props(chosen.out, masters, chosen.blender)); return 0


def _client(parser, repo):
    parser.add_argument('--spec', required=True, type=Path, help='the family review spec (docs/tilesets/tilekit-tools.md)')
    parser.add_argument('--game', required=True, type=Path, help='the game install folder'); parser.add_argument('--built', required=True, type=Path, help='the folder the packs were built into')
    parser.add_argument('--out', required=True, type=Path, help='a fresh folder for the module and its captures'); parser.add_argument('--name', required=True, help='the module\'s name, a resref of at most 11 characters')
    parser.add_argument('--overlay', type=Path, help='a folder of files shown instead of the packs\' own'); parser.add_argument('--views', help='only the views whose label begins with one of these, comma separated')
    parser.add_argument('--most', type=int, default=24, help='views at most, taken evenly (default: 24)'); parser.add_argument('--all', action='store_true', help='every view, however many')
    parser.add_argument('--repo', type=Path, default=repo)
    return parser


def add(commands, repo):
    """Register the commands; {name: function of the parsed arguments}."""
    one = _tileset(commands.add_parser('repair', help='report broken animation blocks of a tileset\'s ASCII models, or put them right with --write'), repo)
    one.add_argument('--models', help='only these models, comma separated'); one.add_argument('--write', action='store_true', help='write the ASCII sources (then run compile)')
    two = commands.add_parser('propose', help='propose the kit pieces of a family of tiles: a placement spec for detail, each tile checked by it')
    two.add_argument('--spec', required=True, type=Path, help='the family spec'); two.add_argument('--kit', required=True, type=Path, help='the folder of kit pieces')
    two.add_argument('--out', required=True, type=Path, help='the placement spec written'); two.add_argument('--repo', type=Path, default=repo)
    three = _tileset(commands.add_parser('openings', help='measure the doorways of a tileset\'s door hooks, and list its black openings, into a JSON file'), repo)
    three.add_argument('--out', required=True, type=Path); three.add_argument('--black', help='materials that stand for an opening, comma separated patterns')
    three.add_argument('--types', default='0', help='the hook types measured, comma separated (default: 0, generic doors)')
    four = _client(commands.add_parser('family-review', help='capture a family of tiles in the client: tiles apart, streets, whole towers, door hooks'), repo)
    four.add_argument('--no-run', action='store_true', help='build the module and stop')
    five = _client(commands.add_parser('perf', help='measure frame rates and load times of the areas of a family review spec'), repo)
    five.add_argument('--cap', type=int, default=200, help='the frame limit, 1 to 200')
    six = _tileset(commands.add_parser('rank', help='rank a tileset\'s building tiles by how plain their own geometry is'), repo)
    six.add_argument('--ground', help='the terrains that are no building, comma separated (the default terrain is one)'); six.add_argument('--out', required=True, type=Path)
    six.add_argument('--show', type=int, default=40)
    seven = _tileset(commands.add_parser('shared', help='list the models outside a tileset that name its restyled textures'), repo)
    seven.add_argument('--spec', required=True, type=Path, help='the material spec')
    eight = commands.add_parser('placements', help='hold placement specs\' wall pieces against their tiles\' own geometry (exit 1 when any runs into it)')
    eight.add_argument('--spec', required=True, type=Path, nargs='+'); eight.add_argument('--kit', required=True, type=Path); eight.add_argument('--repo', type=Path, default=repo)
    nine = _tileset(commands.add_parser('sketch', help='draw tile models from the top, the front and the side'), repo)
    nine.add_argument('--models', required=True, help='comma separated'); nine.add_argument('--out', required=True, type=Path, help='the picture written'); nine.add_argument('--overlay', type=Path)
    ten = commands.add_parser('props', help='render every kit piece in Blender, by day and night, on sheets')
    ten.add_argument('--blender', required=True, type=Path); ten.add_argument('--out', required=True, type=Path, help='a folder for the renders')
    ten.add_argument('--masters', type=Path, help='the folder of tiling scans (default: tilekit/masters in the shared tool root)'); ten.add_argument('--repo', type=Path, default=repo)
    return {'repair': repair_command, 'propose': propose_command, 'openings': openings_command, 'family-review': family_review_command,
            'perf': perf_command, 'rank': rank_command, 'shared': shared_command, 'placements': placements_command, 'sketch': sketch_command, 'props': props_command}
