"""Day and night for a tileset's lit panes. The suburb tiles (udp1) draw their lit windows and lamp lenses as meshes
that glow of their own at every hour, so a street stood lit at noon (pilot, 2026-11-23). The meshes that draw one of a
list's lit textures with a glow are made clear by day and full by night, through the four animations the game plays
on a tile as the hour turns (`day`, `day2night`, `night`, `night2day`: envkit's `tile._daylight`). A lit pane whose
texture has a day texture in the list gets a day pane: a copy that draws it without the glow, full by day and clear
by night (the tiles' own unlit panes are parked some 20 m off; none is in place under a lit one). Compiled models and models another tileset uses (but a merged set named as sharing them) are left as they are; a copy already in the folder is
the one changed.

The list (`docs/tilesets/<set>/daylight.json`): {"lit": {lit texture: its day texture, or null for none}}."""
import re
from pathlib import Path

from . import inventory, lamps, require

ANIMS = {'day': (0, 0, 1 / 30), 'day2night': (0, 1, 0.56667), 'night': (1, 1, 1 / 30), 'night2day': (1, 0, 0.6)}  # the stock city tiles' lengths
NODE = re.compile(r'(?ms)^[ \t]*node[ \t]+(\w+)[ \t]+([^\r\n]+?)[ \t]*\r?\n(.*?)^[ \t]*endnode[ \t]*\r?\n')
GLOW = 0.05  # a self-illumination under this is no light


def _geometry(text):
    return re.split(r'(?mi)^[ \t]*newanim ', text)[0]


def _field(body, word):
    found = re.search(r'(?mi)^[ \t]*' + word + r'[ \t]+(\S[^\r\n]*?)[ \t]*\r?$', body)
    return found.group(1) if found else None


def lit_nodes(text, textures, glow=GLOW):
    """[(node, parent, texture)] of the meshes of a model's geometry that draw one of `textures` and glow of their
    own, as the model spells them."""
    textures = {name.lower() for name in textures}; found = []
    for kind, name, body in NODE.findall(_geometry(text)):
        bitmap, shine, parent = _field(body, 'bitmap'), _field(body, 'selfillumcolor'), _field(body, 'parent')
        if kind.lower() == 'trimesh' and bitmap and shine and parent and bitmap.lower() in textures and max(map(float, shine.split())) > glow:
            found.append((name, parent, bitmap.lower()))
    return found


def with_daylight(text, lit):
    """(the model's text with the four animations written for its lit meshes, how many, how many day panes made).
    lit: {lit texture: day texture or None}. A model with none is given back as it is; one that has a day or night
    animation already, or a lit mesh that shares its name with an unlit one or has children, is refused."""
    lit = {name.lower(): (day.lower() if day else None) for name, day in lit.items()}; found = lit_nodes(text, lit)
    if not found:
        return text, 0, 0
    name = re.search(r'(?mi)^[ \t]*newmodel[ \t]+(\S+)', text).group(1)
    require(not {one.lower() for one in re.findall(r'(?mi)^[ \t]*newanim[ \t]+(\S+)', text)} & set(ANIMS), f'{name} has a day or night animation already')
    ending = '\r\n' if '\r\n' in text else '\n'
    every = [one[1] for one in NODE.findall(_geometry(text))]; taken = {one.lower() for one in every}

    def word(one):  # the name as the game reads it: to the first space, in any case
        return one.split()[0].lower()
    words = [word(one) for one in every]

    def fresh(stem, index):
        made = next(f'{stem}{index:02d}_{count}' for count in range(999) if f'{stem}{index:02d}_{count}' not in taken)
        taken.add(made); return made
    faded = []  # (node, parent, alpha by day, alpha by night)
    for index, (node, parent, texture) in enumerate(found):
        if len(node.split()) > 1 or words.count(word(node)) != 1:  # the game reads a name to its first space, and the first node of a name: the lit mesh takes a name of its own
            line = re.compile(r'(?mi)^([ \t]*node[ \t]+trimesh[ \t]+)' + re.escape(node) + r'([ \t]*\r?)$')
            require(words.count(word(node)) == sum(1 for one in found if word(one[0]) == word(node))
                    and not re.search(r'(?mi)^[ \t]*parent[ \t]+' + re.escape(word(node)) + r'(?:[ \t][^\r\n]*)?\r?$', text),
                    f'{name}: the lit mesh {node!r} shares its name with a mesh that is not lit, or has children')
            # meshes of one name are taken in their order: the first still under the old name, in the geometry and in each animation
            new = fresh('lit', index); parts = re.split(r'(?mi)(?=^[ \t]*newanim[ \t])', text)
            text = ''.join(line.sub(lambda at: at.group(1) + new + at.group(2), part, count=1) for part in parts); node = new
        parent = parent.split()[0]  # a parent is read to its first space, as a name is
        faded.append((node, parent, 0, 1))
        day = lit[texture]
        if day:
            block = next((at for at in NODE.finditer(_geometry(text)) if at.group(2) == node), None)
            require(block, f'{name}: the lit mesh {node!r} was not found again')
            # the tiles' own unlit panes are parked far off the tile, none in place: the wall would be blank by day
            new = fresh('day', index); pane = block.group(0)
            pane = re.sub(r'(?mi)^([ \t]*node[ \t]+trimesh[ \t]+)[^\r\n]+?([ \t]*\r?)$', lambda at: at.group(1) + new + at.group(2), pane, count=1)
            pane = re.sub(r'(?mi)^([ \t]*bitmap[ \t]+)\S+', lambda at: at.group(1) + day, pane)
            pane = re.sub(r'(?mi)^([ \t]*selfillumcolor[ \t]+)[^\r\n]*?(\r?)$', lambda at: at.group(1) + '0 0 0' + at.group(2), pane)
            text = text[:block.end()] + pane + text[block.end():]; faded.append((new, parent, 1, 0))
    tree = {}  # by the name the game reads: to the first space, the first node of it, in any case
    for kind, node, body in NODE.findall(_geometry(text)):
        tree.setdefault(node.split()[0].lower(), (kind, node.split()[0], (_field(body, 'parent') or 'NULL').split()[0]))
    lines = []
    for anim, (start, finish, length) in ANIMS.items():
        lines += [f'newanim {anim} {name}', f'  length {length:.5f}', '  transtime 0.25', f'  animroot {name}', f'  node dummy {name}', '    parent NULL', '  endnode']
        said = {name.lower()}
        for node, parent, by_day, by_night in faded:  # an animation names a node's whole line of parents: without them the client falls over as the area loads
            chain, above = [], parent
            while above.lower() not in said and above.lower() in tree:
                chain.append(tree[above.lower()]); above = chain[-1][2]
            for kind, one, over in reversed(chain):
                said.add(one.lower()); lines += [f'  node {kind} {one}', f'    parent {over}', '  endnode']
            first, last = (by_day, by_night)[start], (by_day, by_night)[finish]
            lines += [f'  node trimesh {node}', f'    parent {parent}', '    alphakey 2', f'      0.00000 {first}', f'      {length:.5f} {last}', '    endlist', '  endnode']
        lines += [f'doneanim {anim} {name}']
    at = re.search(r'(?mi)^[ \t]*donemodel', text); require(at, f'{name} has no donemodel line')
    return text[:at.start()] + ending.join(lines) + ending + text[at.start():], len(found), sum(1 for one in faded if one[2])


def write(repo, tileset, folder, lit, shared=()):
    """Write the models of a tileset that have lit meshes, with their day and night, into `folder` (a review's
    overlay; a model already there is changed in place) and tell {'models': {model: lit meshes}, 'panes': day panes
    made, 'refused': {model: why}}. shared: the tilesets that draw these tiles too and take the change with them (a merged
    set); a model any other tileset draws is left."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {'models': {}, 'panes': 0, 'refused': {}}
    from .apply import noted
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if set(others) - {one.lower() for one in shared}:  # another tileset draws it too
            continue
        try:
            new, count, panes = with_daylight(text, lit)
        except ValueError as error:
            told['refused'][name] = str(error); continue
        if count:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told['models'][name] = count; told['panes'] += panes
    return told
