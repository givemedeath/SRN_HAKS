"""Which tilesets are merged into one (`docs/tilesets/<set>/merge.json`, `merge`): a merged set draws its families' models
from their own packs, and is meant to show whatever is changed in them."""
import json
from pathlib import Path

from . import lamps


def families(repo, tileset):
    """The tilesets merged into `tileset`, in the merge's order; () for one that is no merge."""
    path = Path(repo) / 'docs' / 'tilesets' / tileset.lower() / 'merge.json'
    return tuple(one['set'].lower() for one in json.loads(path.read_text(encoding='utf-8-sig'))['families']) if path.is_file() else ()


def over(repo, tileset):
    """The merged tilesets `tileset` is a family of."""
    return {path.parent.name.lower() for path in (Path(repo) / 'docs' / 'tilesets').glob('*/merge.json') if tileset.lower() in families(repo, path.parent.name)}


def packs(repo, tileset):
    """The packs a tileset's models are read from (`inventory.drawn_copies`): its own and the common one, and a merged
    set's families'."""
    return (*lamps.PACKS, *(f'srn_t_{family}' for family in families(repo, tileset)))
