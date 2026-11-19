"""Lamps of a tileset's tiles moved from source lights to main lights. The game draws a flame and a warm flicker at
every source light a tile switches on, whatever the model says of flares; a main light is a plain steady light. A tile
whose lamps are source lights (`<tile>sl1`, `sl2`) and that has no main light gets them renamed (`ml1`, `ml2`) with a
radius, in a copy of its model; a builder then switches them on with the tile's main lights. Tiles that already have
a main light are left as they are, as are compiled models and models another tileset uses."""
import re
from pathlib import Path

from . import inventory, require

RADIUS = 7.0
PACKS = ('srn_t_{tileset}', 'srn_t_common')
SOURCE, MAIN = re.compile(r'(?i)sl([12])$'), re.compile(r'(?i)ml[12]$')


def moved(text, radius=RADIUS):
    """(the model's text with its source lights as main lights, their new names), or (None, why) where it is left."""
    names = sorted(set(re.findall(r'(?im)^\s*node[ \t]+light[ \t]+(\S+)', text)))
    source = [name for name in names if SOURCE.search(name)]
    if not source:
        return None, 'no source light'
    if any(MAIN.search(name) for name in names):
        return None, 'has a main light'
    made = []
    for name in source:
        new = SOURCE.sub(r'ml\1', name)
        text = re.sub(r'(?<!\S)' + re.escape(name) + r'(?!\S)', new, text)  # the node, and its keys in every animation
        node = re.search(r'(?is)^[ \t]*node[ \t]+light[ \t]+' + re.escape(new) + r'[ \t\r]*$.*?^[ \t]*endnode', text, re.M)
        require(node and re.search(r'(?im)^\s*radius\s+\S+', node.group(0)), f'The light {name} has no radius to set')
        text = text[:node.start()] + re.sub(r'(?im)^(\s*radius\s+)\S+', rf'\g<1>{radius}', node.group(0), count=1) + text[node.end():]
        made.append(new)
    return text, made


def move(repo, tileset, folder, *, radius=RADIUS):
    """Write the moved models of a tileset into `folder` (a review's overlay; a model already there is changed in
    place) and tell {model: state}. A model whose walkmesh would differ afterwards is a refusal: nothing here touches one."""
    repo, folder = Path(repo), Path(folder); tileset = tileset.lower()
    tiles = inventory.drawn_models(repo, tileset)  # the edge tiles round an area's border too
    others = inventory._other_sets(repo, tileset); told, seen = {}, set(); folder.mkdir(parents=True, exist_ok=True)
    for pack in PACKS:
        for path in sorted((repo / pack.format(tileset=tileset)).glob('*.mdl')):
            name = path.stem.lower()  # a copy already in the folder (the shadows') is the one moved, so neither undoes the other
            data = (folder / path.name if (folder / path.name).is_file() else path).read_bytes()
            if name not in tiles or name in seen:  # the first pack's copy is the one the game shows
                continue
            seen.add(name)
            if inventory.compiled(data):
                continue
            text = data.decode('cp1252'); new, said = moved(text, radius)
            if new is None:
                if said != 'no source light':
                    told[name] = said
            elif others.get(name):
                told[name] = 'shared with ' + ', '.join(sorted(others[name]))
            else:
                require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
                (folder / path.name).write_bytes(new.encode('cp1252')); told[name] = 'moved'
    return told
