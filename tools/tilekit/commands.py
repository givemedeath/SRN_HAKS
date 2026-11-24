"""The command line of the restyle's working tools (`docs/tilesets/tilekit-tools.md`), kept apart from `__main__` so that
file gains only their registration. Nothing of a tool is imported before its command runs."""
import json
from pathlib import Path


def _tileset(parser, repo):
    parser.add_argument('--tileset', required=True); parser.add_argument('--repo', type=Path, default=repo)
    return parser


def _names(text):
    return [name for name in (text or '').split(',') if name]


def _told(told, out=None):
    text = json.dumps(told, indent=1)
    if out:
        Path(out).write_text(text + '\n', encoding='utf-8', newline='\n')
    print(text)


def repair_command(chosen):
    from . import repair
    told = repair.repair(chosen.repo, chosen.tileset, models=_names(chosen.models), write=chosen.write)
    _told({'written': chosen.write, 'models': told})
    return 0


def propose_command(chosen):
    from . import family
    written, told = family.propose(chosen.repo, family.read(chosen.spec), chosen.kit)
    chosen.out.write_text(json.dumps(written, indent=1) + '\n', encoding='utf-8', newline='\n'); _told(told)
    return 1 if told['over'] else 0


def openings_command(chosen):
    from . import openings
    told = openings.openings(chosen.repo, chosen.tileset, _names(chosen.black), tuple(_names(chosen.types)))
    chosen.out.write_text(json.dumps(told, indent=1) + '\n', encoding='utf-8', newline='\n')
    sizes = {}
    for one in told['hooks']:
        size = 'not measured' if 'note' in one else f"{one['width']} x {one['height']}"; sizes[size] = sizes.get(size, 0) + 1
    _told({'hooks': dict(sorted(sizes.items(), key=lambda one: -one[1])), 'black': {kind: sum(one['kind'] == kind for one in told['black']) for kind in ('door', 'window')}})
    return 0


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
    return {'repair': repair_command, 'propose': propose_command, 'openings': openings_command}
