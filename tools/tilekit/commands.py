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


def add(commands, repo):
    """Register the commands; {name: function of the parsed arguments}."""
    one = _tileset(commands.add_parser('repair', help='report broken animation blocks of a tileset\'s ASCII models, or put them right with --write'), repo)
    one.add_argument('--models', help='only these models, comma separated'); one.add_argument('--write', action='store_true', help='write the ASCII sources (then run compile)')
    return {'repair': repair_command}
