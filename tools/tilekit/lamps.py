"""Lamps of a tileset's tiles moved from source lights to main lights. The game draws a flame and a warm flicker at
every source light a tile switches on, whatever the model says of flares; a main light is a plain steady light. A tile
whose lamps are source lights (`<tile>sl1`, `sl2`) and that has no main light gets them renamed (`ml1`, `ml2`) with a
radius, in a copy of its model; a builder then switches them on with the tile's main lights. Tiles that already have
a main light are left as they are, as are compiled models and models another tileset uses.

The game finds a tile's lights by the model's own name (`<tile>ml1`). A light copied in with its first tile's name
(`tme01_z01_01ml1` in 45 Futuristic City tiles, 2026-11-24) is never switched on: `named` gives it the tile's."""
import re
from pathlib import Path

from . import inventory, require

RADIUS = 7.0
PACKS = ('srn_t_{tileset}', 'srn_t_common')
SOURCE, MAIN = re.compile(r'(?i)sl([12])$'), re.compile(r'(?i)ml[12]$')


def moved(text, radius=RADIUS):
    """(the model's text with its source lights as main lights, their new names), or (None, why) where it is left."""
    spelled = {}  # one name in any case, as the geometry's node (the first) spells it
    for name in re.findall(r'(?im)^\s*node[ \t]+light[ \t]+(\S+)', text):
        spelled.setdefault(name.lower(), name)
    names = sorted(spelled.values())
    source = [name for name in names if SOURCE.search(name)]
    if not source:
        return None, 'no source light'
    if any(MAIN.search(name) for name in names):
        return None, 'has a main light'
    made = []
    for name in source:
        new = SOURCE.sub(r'ml\1', name)
        text = re.sub(r'(?i)(?<!\S)' + re.escape(name) + r'(?!\S)', new, text)  # the node, and its keys in every animation, in any case
        node = re.search(r'(?is)^[ \t]*node[ \t]+light[ \t]+' + re.escape(new) + r'[ \t\r]*$.*?^[ \t]*endnode', text, re.M)
        require(node and re.search(r'(?im)^\s*radius\s+\S+', node.group(0)), f'The light {name} has no radius to set')
        text = text[:node.start()] + re.sub(r'(?im)^(\s*radius\s+)\S+', rf'\g<1>{radius}', node.group(0), count=1) + text[node.end():]
        made.append(new)
    return text, made


LAMP = re.compile(r'(?i)^(.*)((?:ml|sl)[12])$')


def named(text, model):
    """(the model's text with every lamp named after another model renamed to its own, the new names). A lamp whose own
    name is taken already is left under the old one, where the game never finds it, as before."""
    spelled = {}
    for name in re.findall(r'(?im)^\s*node[ \t]+light[ \t]+(\S+)', text):
        spelled.setdefault(name.lower(), name)
    made = []; taken = set(spelled)  # with the names given here: two lamps of other tiles never take one name
    for low, name in sorted(spelled.items()):
        lamp = LAMP.match(name)
        if not lamp or lamp.group(1).lower() == model.lower() or (model + lamp.group(2)).lower() in taken:
            continue
        new = model + lamp.group(2).lower(); taken.add(new.lower())
        text =re.sub(r'(?i)(?<!\S)' + re.escape(name) + r'(?!\S)', new, text); made.append(new)
    return text, made


def move(repo, tileset, folder, *, radius=RADIUS, shared=()):
    """Write the moved models of a tileset into `folder` (a review's overlay; a model already there is changed in
    place) and tell {model: state}. A model whose walkmesh would differ afterwards is a refusal: nothing here touches one."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    # the set's tiles and its edge tiles; a copy already in the folder (the shadows') is the one moved, so neither undoes the other
    from .apply import noted
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, PACKS):
        own, renamed = named(text, name)
        if renamed and not set(others) - {one.lower() for one in shared}:  # lamps under another tile's name: this tile's own now
            require(inventory.walk_hash(own) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(own.encode('cp1252')); told[name] = 'named'; text = own
        elif renamed:  # left for the other tileset's sake, and said so: its lamps stay dark
            told[name] = 'shared with ' + ', '.join(others)
        new, said = moved(text, radius)
        if new is None:
            if said != 'no source light' and name not in told:
                told[name] = said
        elif set(others) - {one.lower() for one in shared}:  # shared: a merged set that takes the change with the tiles
            told[name] = 'shared with ' + ', '.join(others)
        else:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told[name] = 'moved'
    return told
