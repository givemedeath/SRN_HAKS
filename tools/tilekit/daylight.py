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
PANE = re.compile(r'(?i)^day\d{2,}_\d+$')  # a day pane's name, as `with_daylight` gives it


def _geometry(text):
    return re.split(r'(?mi)^[ \t]*newanim ', text)[0]


def _field(body, word):
    found = re.search(r'(?mi)^[ \t]*' + word + r'[ \t]+(\S[^\r\n]*?)[ \t]*\r?$', body)
    return found.group(1) if found else None


def _numbers(line):
    return [float(word) for word in line.split()]


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
            pane = re.sub(r'(?mi)^([ \t]*shadow[ \t]+)\S+', lambda at: at.group(1) + '0', pane)  # the lit pane casts the one shadow of the outline
            text = text[:block.end()] + pane + text[block.end():]; faded.append((new, parent, 1, 0))
            # the pane goes where its lit pane goes: a tile loop that lifts the lit pane into place from where it is parked
            # lifts the day pane with it (the Modern Exterior windows that lit at night were bare wall by day, 2026-11-24)
            parts = re.split(r'(?mi)(?=^[ \t]*newanim[ \t])', text)
            for at, part in enumerate(parts[1:], 1):
                own = next((one for one in NODE.finditer(part) if word(one.group(2)) == word(node)), None)
                if own:
                    copy = re.sub(r'(?mi)^([ \t]*node[ \t]+\w+[ \t]+)[^\r\n]+?([ \t]*\r?)$', lambda one: one.group(1) + new + one.group(2), own.group(0), count=1)
                    parts[at] = part[:own.end()] + copy + part[own.end():]
            text = ''.join(parts)
    tree = {}  # by the name the game reads: to the first space, the first node of it, in any case
    for kind, node, body in NODE.findall(_geometry(text)):
        tree.setdefault(node.split()[0].lower(), (kind, node.split()[0], (_field(body, 'parent') or 'NULL').split()[0]))
    lines = []
    for anim, (start, finish, length) in ANIMS.items():
        lines += [f'newanim {anim} {name}', f'  length {length:.5f}', '  transtime 0.25', f'  animroot {name}', f'  node dummy {name}', '    parent NULL', '  endnode']
        said = {name.lower()}; keyed = {node.lower(): (node, parent, by_day, by_night) for node, parent, by_day, by_night in faded}

        def say(node, parent, by_day, by_night):
            # A node is named once. A lit window hung from a lit lamp lens had the lens named twice, with its keys and
            # then bare as the window's parent, and the night never came to that tile: the police and fire stations of
            # the suburb stood dark with their lights switched on (found 2026-11-24).
            if node.lower() in said:
                return
            chain, above = [], parent  # an animation names a node's whole line of parents: without them the client falls over as the area loads
            while above.lower() not in said and above.lower() in tree:
                chain.append(tree[above.lower()]); above = chain[-1][2]
            for kind, one, over in reversed(chain):
                if one.lower() in keyed:
                    say(*keyed[one.lower()])  # a parent that is faded itself is named with its keys
                elif one.lower() not in said:
                    said.add(one.lower()); lines.extend([f'  node {kind} {one}', f'    parent {over}', '  endnode'])
            first, last = (by_day, by_night)[start], (by_day, by_night)[finish]; said.add(node.lower())
            lines.extend([f'  node trimesh {node}', f'    parent {parent}', '    alphakey 2', f'      0.00000 {first}', f'      {length:.5f} {last}', '    endlist', '  endnode'])
        for one in faded:
            say(*one)
        lines += [f'doneanim {anim} {name}']
    at = re.search(r'(?mi)^[ \t]*donemodel', text); require(at, f'{name} has no donemodel line')
    return text[:at.start()] + ending.join(lines) + ending + text[at.start():], len(found), sum(1 for one in faded if one[2])


def without(text):
    """The model's text without the day and night `with_daylight` wrote: its four animations and its day panes. The
    lit meshes keep the names they were given."""
    for anim in ANIMS:
        text = re.sub(rf'(?mis)^[ \t]*newanim[ \t]+{anim}[ \t].*?^[ \t]*doneanim[ \t]+{anim}[ \t][^\n]*\n', '', text)
    panes = {name.lower() for kind, name, body in NODE.findall(_geometry(text)) if kind.lower() == 'trimesh' and PANE.match(name)}
    return NODE.sub(lambda at: '' if at.group(2).lower() in panes else at.group(0), text)  # in the geometry and in each animation that moves one


def switched(text, textures, loop='animloop01'):
    """Whether a model's lit meshes are switched by a tile loop: one of them, or one of their parents, is moved in
    `loop`. The suburb tiles keep their lit panes parked under the tile and their unlit ones in place, and `animloop01`
    changes them over, so a tile whose AnimLoop1 is off is dark at every hour (found 2026-11-24). The Modern Exterior
    tiles move the lit mesh itself (found the same day, in the review of PR 194)."""
    at = re.search(rf'(?mis)^[ \t]*newanim[ \t]+{loop}[ \t].*?^[ \t]*doneanim[ \t]+{loop}[ \t]', text)
    if not at:
        return False
    nodes = list(reversed(NODE.findall(_geometry(text))))  # the first node of a name is the one the game reads
    rest = {name.split()[0].lower(): _numbers(_field(body, 'position') or '0 0 0')[:3] for kind, name, body in nodes}

    def away(name, body):  # a key that puts the node somewhere else than it rests: a loop written out of a modeller keys every node where it is
        rows = re.search(r'(?mi)^[ \t]*positionkey[^\r\n]*\r?\n((?:[ \t]*[-+0-9.eE \t]+\r?\n)+)', body)
        home = rest.get(name, [0.0, 0.0, 0.0])
        return bool(rows) and any(len(row) >= 4 and max(abs(a - b) for a, b in zip(row[1:4], home)) > 0.01 for row in map(_numbers, rows.group(1).splitlines()))
    moved = {name.split()[0].lower() for kind, name, body in NODE.findall(at.group(0)) if away(name.split()[0].lower(), body)}
    above = {name.split()[0].lower(): (_field(body, 'parent') or 'NULL').split()[0].lower() for kind, name, body in nodes}
    for node, parent, texture in lit_nodes(text, textures):
        seen, one = set(), node.split()[0].lower()
        while one in above and one not in seen:
            if one in moved:
                return True
            seen.add(one); one = above[one]
    return False


def lights_on(repo, tileset, lit, pack=None):
    """Turn AnimLoop1 on in a tileset's set file for every tile whose model's lit meshes are switched by it, and
    tell the models turned on. The standard (user, 2026-11-24): the hour drives the lights, through the day and night
    animations; AnimLoop1 is the builder's switch for a building that stands dark, and is on unless turned off."""
    from .compiled import SOURCES
    pack = pack or f'srn_t_{tileset.lower()}'; path = Path(repo) / pack / f'{tileset.lower()}.set'; text = path.read_bytes().decode('cp1252'); told = []

    def model(name):
        homes = dict.fromkeys((pack, *(one.format(tileset=tileset.lower()) for one in lamps.PACKS)))  # its own pack, then the common one: 109 Modern Exterior tiles live there
        for folder in (Path(repo) / kept / home for home in homes for kept in (SOURCES, '')):
            if (folder / f'{name}.mdl').is_file():
                return (folder / f'{name}.mdl').read_bytes().decode('cp1252', errors='replace')
        return ''

    def one(at):
        name = re.search(r'(?mi)^Model=(\S+)', at.group(0))
        if not name or not re.search(r'(?m)^AnimLoop1=0[ \t]*\r?$', at.group(0)) or not switched(model(name.group(1).lower()), lit):
            return at.group(0)
        told.append(name.group(1).lower())
        return re.sub(r'(?m)^AnimLoop1=0([ \t]*\r?)$', r'AnimLoop1=1\1', at.group(0))
    new = re.sub(r'(?ms)^\[TILE\d+\][^\[]*', one, text)
    if told:
        path.write_bytes(new.encode('cp1252'))
    return sorted(told)


def write(repo, tileset, folder, lit, shared=(), again=False):
    """Write the models of a tileset that have lit meshes, with their day and night, into `folder` (a review's
    overlay; a model already there is changed in place) and tell {'models': {model: lit meshes}, 'panes': day panes
    made, 'refused': {model: why}, 'done': how many had their day and night already (a second run, or the pack's own)}.
    again: a model that has its day and night is made anew from the list, and written where that changes it (a lit
    texture given a day texture since: the windows of eleven suburb tiles were blank by day, 2026-11-24). shared: the tilesets that draw these tiles too and take the change with them (a merged
    set); a model any other tileset draws is left."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {'models': {}, 'panes': 0, 'refused': {}, 'done': 0}
    from .apply import noted
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if set(others) - {one.lower() for one in shared}:  # another tileset draws it too
            continue
        if lit_nodes(text, lit) and {one.lower() for one in re.findall(r'(?mi)^[ \t]*newanim[ \t]+(\S+)', text)} >= set(ANIMS):
            told['done'] += 1
            if not again:
                continue
        try:
            new, count, panes = with_daylight(without(text) if again else text, lit)
        except ValueError as error:
            told['refused'][name] = str(error); continue
        if count and new != text:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told['models'][name] = count; told['panes'] += panes
    return told
