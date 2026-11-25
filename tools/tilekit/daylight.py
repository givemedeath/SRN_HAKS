"""Day and night for a tileset's lit panes. The suburb tiles (udp1) draw their lit windows and lamp lenses as meshes
that glow of their own at every hour, so a street stood lit at noon (pilot, 2026-11-23). The meshes that draw one of a
list's lit textures with a glow are made clear by day and full by night, through the four animations the game plays
on a tile as the hour turns (`day`, `day2night`, `night`, `night2day`: envkit's `tile._daylight`). A lit pane whose
texture has a day texture in the list gets a day pane: a copy that draws it without the glow, full by day and clear
by night (the tiles' own unlit panes are parked some 20 m off; none is in place under a lit one). Compiled models and models another tileset uses (but a merged set named as sharing them) are left as they are; a copy already in the folder is
the one changed.

The game plays these animations only under a tile's animated node (the model's name with an `a`), so each lit mesh
is hung from it where it stands (`animated`). A lit texture that glows through its material's glow map has a day
material, the same material without the map (`day_materials`); a mesh that draws one is lit whatever its own glow,
and is left none, since the game tints a glow map by it (`mapped`).

The list (`docs/tilesets/<set>/daylight.json`): {"lit": {lit texture: its day texture, or null for none}, "switched":
[textures of signs a tile loop raises, lit at every hour: `lights_on` turns their loops on too], "dayMaterials": {day
material: the lit texture whose material it is made from}}."""
import math
import re
from pathlib import Path

from . import inventory, lamps, require

ANIMS = {'day': (0, 0, 1 / 30), 'day2night': (0, 1, 0.56667), 'night': (1, 1, 1 / 30), 'night2day': (1, 0, 0.6)}  # the stock city tiles' lengths
NODE = re.compile(r'(?ms)^[ \t]*node[ \t]+(\w+)[ \t]+([^\r\n]+?)[ \t]*\r?\n(.*?)^[ \t]*endnode[ \t]*\r?\n')
GLOW = 0.05  # a self-illumination under this is no light
LOOPS = (1, 2, 3)  # a tile's loops: AnimLoop1 to 3 in a set file, animloop01 to 03 in a model
PLACED = re.compile(r'(?mi)^[ \t]*(?:position|orientation|scale)(?:key)?\b')  # an animation placing a node: keyed, or a plain place, which is its one key (dgt04_e09_21)
PANE = re.compile(r'(?i)^day\d{2,}_\d+$')  # a day pane's name, as `with_daylight` gives it


def _geometry(text):
    return re.split(r'(?mi)^[ \t]*newanim ', text)[0]


def _field(body, word):
    found = re.search(r'(?mi)^[ \t]*' + word + r'[ \t]+(\S[^\r\n]*?)[ \t]*\r?$', body)
    return found.group(1) if found else None


def _numbers(line):
    return [float(word) for word in line.split()]


def mapped(spec):
    """The lit textures of a list that glow through their materials' glow maps: those a day material is made from."""
    return {lit.lower() for lit in spec.get('dayMaterials', {}).values()}


def lit_nodes(text, textures, glow=GLOW, mapped=()):
    """[(node, parent, texture)] of the meshes of a model's geometry that draw one of `textures` and glow of their
    own, as the model spells them. A mesh that draws one of `mapped` glows through its material whatever its own
    glow is: the arcology's wall bands have none and were as bright at noon as at night (2026-11-24)."""
    textures = {name.lower() for name in textures}; found = []
    for kind, name, body in NODE.findall(_geometry(text)):
        bitmap, shine, parent = _field(body, 'bitmap'), _field(body, 'selfillumcolor'), _field(body, 'parent')
        if kind.lower() == 'trimesh' and bitmap and parent and bitmap.lower() in textures and (bitmap.lower() in mapped or (shine and max(map(float, shine.split())) > glow)):
            found.append((name, parent, bitmap.lower()))
    return found


def _quaternion(turn):  # a model's orientation (an axis and an angle) as w x y z
    x, y, z, angle = turn; length = math.sqrt(x * x + y * y + z * z)
    if length < 1e-9 or abs(angle) < 1e-12:
        return (1.0, 0.0, 0.0, 0.0)
    part = math.sin(angle / 2) / length
    return (math.cos(angle / 2), x * part, y * part, z * part)


def _times(a, b):
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3], a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1], a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def _turned(q, v):
    return _times(_times(q, (0.0, *v)), (q[0], -q[1], -q[2], -q[3]))[1:]


def _placed(text):
    """{a node's name as the game reads it: (its spelling, its parent as read, position, quaternion, scale)} of the geometry."""
    placed = {}
    for kind, node, body in NODE.findall(_geometry(text)):
        position, turn, scale = (_field(body, word) for word in ('position', 'orientation', 'scale'))
        placed.setdefault(node.split()[0].lower(), (node.split()[0], (_field(body, 'parent') or 'NULL').split()[0].lower(),
                                                    tuple(_numbers(position)[:3]) if position else (0.0, 0.0, 0.0),
                                                    _quaternion(_numbers(turn)[:4]) if turn else (1.0, 0.0, 0.0, 0.0), float(scale.split()[0]) if scale else 1.0))
    return placed


def _line(placed, node):  # a node and the nodes over it, the root last
    line = []
    while node in placed and node not in line:
        line.append(node); node = placed[node][1]
    return line


def _world(placed, node):
    position, turn, scale = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), 1.0
    for one in reversed(_line(placed, node)):
        _, _, at, by, size = placed[one]
        position = tuple(a + scale * b for a, b in zip(position, _turned(turn, at))); turn = _times(turn, by); scale *= size
    return position, turn, scale


def animated(text, node, keep=()):
    """(the model's text with the mesh `node` under the tile's animated node, that node's name). The game plays a
    tile's animations on the node named as the model with an `a` after it and on what hangs from it, and on nothing
    else: a lit pane hung from the model's root kept its plain alpha at every hour, with its day pane over it (the
    arcology and School 3 never changed with the hour; found with the arcology's day materials, 2026-11-24). The
    node is made where the model has none; the mesh stays where it stands. A mesh under a node an animation keys
    (a sign's panes a tile loop lifts into place) stays under it, and that line of parents is hung from the animated
    node whole; one under a mesh of `keep` (a lit window hung from a lit lens) stays under it, and that mesh is hung
    there. Refused: a mesh an animation moves where the two parents are not placed alike."""
    name = re.search(r'(?mi)^[ \t]*newmodel[ \t]+(\S+)', text).group(1); ending = '\r\n' if '\r\n' in text else '\n'
    placed = _placed(text); key = node.split()[0].lower(); under = f'{name}a'.lower()
    require(key in placed, f'{name}: the mesh {node!r} was not found'); line = _line(placed, key)
    if under in line[1:]:
        return text, placed[placed[key][1]][0]
    require(under != key and key not in _line(placed, under)[1:], f'{name}: the mesh {node!r} holds the animated node')
    root = line[-1]
    keyed = {at.group(2).split()[0].lower() for part in re.split(r'(?mi)(?=^[ \t]*newanim[ \t])', text)[1:] for at in NODE.finditer(part) if re.search(r'(?i)key\b', at.group(3)) or PLACED.search(at.group(3))}
    held = next((one for one in reversed(line[1:-1]) if one in keyed or one in keep), None)
    if held:
        return animated(text, placed[line[-2] if keyed & set(line[1:-1]) else held][0], keep)[0], placed[placed[key][1]][0]
    if under not in placed:
        block = next(at for at in NODE.finditer(_geometry(text)) if at.group(2).split()[0].lower() == root)
        text = text[:block.end()] + ending.join([f'node dummy {name}a', f'  parent {placed[root][0]}', 'endnode']) + ending + text[block.end():]
        placed = _placed(text)
    spelt = placed[under][0]; old, new = _world(placed, placed[key][1]), _world(placed, under)
    alike = all(abs(a - b) < 1e-7 for a, b in zip(old[0] + (old[2],), new[0] + (new[2],))) and abs(abs(sum(a * b for a, b in zip(old[1], new[1]))) - 1) < 1e-9
    parts = re.split(r'(?mi)(?=^[ \t]*newanim[ \t])', text)

    def hung(block, word='parent', value=spelt):
        return re.sub(r'(?mi)^([ \t]*' + word + r'[ \t]+)[^\r\n]*?([ \t]*\r?)$', lambda at: at.group(1) + value + at.group(2), block, count=1)
    block = next(at for at in NODE.finditer(parts[0]) if at.group(2).split()[0].lower() == key); mesh = hung(block.group(0))
    if not alike:
        position, turn, scale = _world(placed, key); back = (new[1][0], -new[1][1], -new[1][2], -new[1][3])
        position = tuple(value / new[2] for value in _turned(back, tuple(a - b for a, b in zip(position, new[0])))); turn = _times(back, turn)
        half = math.sqrt(sum(value * value for value in turn[1:])); spin = (*((value / half for value in turn[1:]) if half > 1e-9 else (0.0, 0.0, 0.0)), 2 * math.atan2(half, turn[0]))
        for word, values in (('position', position), ('orientation', spin), ('scale', (scale / new[2],))):
            value = ' '.join(f'{one:.7g}' for one in values)
            if _field(mesh, word) is not None:
                mesh = hung(mesh, word, value)
            elif word != 'scale' or abs(values[0] - 1) > 1e-9:
                mesh = re.sub(r'(?mi)^([ \t]*)(parent[ \t][^\r\n]*?)(\r?\n)', lambda at: f'{at.group(0)}{at.group(1)}{word} {value}{at.group(3)}', mesh, count=1)
    parts[0] = parts[0][:block.start()] + mesh + parts[0][block.end():]
    for at, part in enumerate(parts[1:], 1):  # an animation names the mesh's line of parents: the animated node before it
        own = next((one for one in NODE.finditer(part) if one.group(2).split()[0].lower() == key), None)
        if not own:
            continue
        require(alike or not PLACED.search(own.group(3)), f'{name}: an animation moves the mesh {node!r}, whose parent is not placed as the animated node is')
        named = next((one for one in NODE.finditer(part) if one.group(2).split()[0].lower() == under), None)
        if named and named.start() > own.start():  # named after the mesh, which hung from the root: the animated node is named first, where the mesh is
            parts[at] = part[:own.start()] + named.group(0) + hung(own.group(0)) + part[own.end():named.start()] + part[named.end():]; continue
        dummy = '' if named else ending.join([f'  node dummy {spelt}', f'    parent {placed[root][0]}', '  endnode']) + ending
        parts[at] = part[:own.start()] + dummy + hung(own.group(0)) + part[own.end():]
    return ''.join(parts), spelt


def with_daylight(text, lit, mapped=()):
    """(the model's text with the four animations written for its lit meshes, how many, how many day panes made).
    lit: {lit texture: day texture or None}. A model with none is given back as it is; one that has a day or night
    animation already, or a lit mesh that shares its name with an unlit one or has children, is refused. Each lit
    mesh is hung from the tile's animated node (`animated`), where the game plays the animations. A lit mesh that
    draws one of `mapped` (lit by its material's glow map) is left no glow of its own: the game tints a glow map by
    the mesh's glow colour, and the arcology's cyan bands came out blue at night (2026-11-24)."""
    lit = {name.lower(): (day.lower() if day else None) for name, day in lit.items()}; found = lit_nodes(text, lit, mapped=mapped)
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
    lights = {word(one[0]) for one in found}
    for index, (node, parent, texture) in enumerate(found):
        if len(node.split()) > 1 or words.count(word(node)) != 1:  # the game reads a name to its first space, and the first node of a name: the lit mesh takes a name of its own
            line = re.compile(r'(?mi)^([ \t]*node[ \t]+trimesh[ \t]+)' + re.escape(node) + r'([ \t]*\r?)$')
            require(words.count(word(node)) == sum(1 for one in found if word(one[0]) == word(node))
                    and not re.search(r'(?mi)^[ \t]*parent[ \t]+' + re.escape(word(node)) + r'(?:[ \t][^\r\n]*)?\r?$', text),
                    f'{name}: the lit mesh {node!r} shares its name with a mesh that is not lit, or has children')
            # meshes of one name are taken in their order: the first still under the old name, in the geometry and in each animation
            new = fresh('lit', index); parts = re.split(r'(?mi)(?=^[ \t]*newanim[ \t])', text)
            text = ''.join(line.sub(lambda at: at.group(1) + new + at.group(2), part, count=1) for part in parts); node = new
        text, parent = animated(text, node, lights)  # a parent is read to its first space, as a name is
        # a translucent pane keeps its own alpha where it shows: keyed 1, the arcology's half-clear glass was drawn solid (review of PR 198, 2026-11-24)
        own = next((_field(at.group(3), 'alpha') for at in NODE.finditer(_geometry(text)) if at.group(2) == node), None)
        require(own is None or re.fullmatch(r'\d*\.?\d+', own), f'{name}: the lit mesh {node!r} has an alpha that is no number ({own})')
        full = own if own is not None and float(own) != 1 else 1
        faded.append((node, parent, 0, full))
        if texture in mapped:
            block = next(at for at in NODE.finditer(_geometry(text)) if at.group(2) == node)
            text = text[:block.start()] + re.sub(r'(?mi)^([ \t]*selfillumcolor[ \t]+)[^\r\n]*?(\r?)$', lambda at: at.group(1) + '0 0 0' + at.group(2), block.group(0)) + text[block.end():]
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
            text = text[:block.end()] + pane + text[block.end():]; faded.append((new, parent, full, 0))
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


GLOW_MAP = re.compile(r'(?mi)^([ \t]*texture5[ \t]+)(\S+)')
RESREF = re.compile(r'[a-z0-9_\-]{1,16}')


def unlit(material):
    """A material file's text without its glow map. A lit texture that is its own day texture still glowed by day where
    its material had one: the arcology's windows were as bright at noon as at night (review of PR 198, 2026-11-24)."""
    found = GLOW_MAP.search(material)
    require(found and found.group(2).lower() != 'null', 'The material has no glow map to leave out')
    require(re.search(r'(?mi)^[ \t]*texture0[ \t]+\S', material), 'The material names no texture0: under another name it would draw no picture')
    return GLOW_MAP.sub(lambda at: at.group(1) + 'null', material, count=1)


def day_materials(repo, spec, packs, *, check=False):
    """Write the day materials of a list (`dayMaterials`: {day texture: the lit texture whose material it is, without
    the glow map}) beside the materials they are made from, in the first of `packs` that holds each. Tells {day texture:
    pack} of those written; with `check` nothing is written and those that are missing or differ are told."""
    told = {}
    for day, lit in spec.get('dayMaterials', {}).items():
        require(RESREF.fullmatch(day) and day != lit.lower(), f'{day}: a day material has a lowercase name of its own, of 16 characters at most')
        home = next((Path(repo) / pack for pack in packs if (Path(repo) / pack / f'{lit}.mtr').is_file()), None)
        require(home, f'No material {lit}.mtr in ' + ', '.join(packs))
        made = unlit((home / f'{lit}.mtr').read_bytes().decode('ascii')).encode('ascii'); path = home / f'{day}.mtr'
        if not path.is_file() or path.read_bytes() != made:
            told[day] = home.name
            if not check:
                path.write_bytes(made)
    return told


def switched(text, textures, loop='animloop01', mapped=()):
    """Whether a model's lit meshes are switched by a tile loop: one of them, or one of their parents, is moved in
    `loop`. The suburb tiles keep their lit panes parked under the tile and their unlit ones in place, and `animloop01`
    changes them over, so a tile whose AnimLoop1 is off is dark at every hour (found 2026-11-24). The Modern Exterior
    tiles move the lit mesh itself (found the same day, in the review of PR 194)."""
    return bool(_switched(text, textures, loop, mapped))


def never(text, textures, mapped=()):
    """The lit meshes of a model that no tile loop moves, where a loop moves any of them: parked and never raised,
    such a pane never lights (the pawn shop window of dgt04_e09_06, 2026-11-24). A model no loop switches is not told:
    its lit panes are in place. mapped: as `lit_nodes`, here and in `switched` and `lights_on`: a pane lit by its
    material alone is parked and raised as any other."""
    moved = {node for loop in LOOPS for node in _switched(text, textures, f'animloop0{loop}', mapped)}
    return [node for node, parent, texture in lit_nodes(text, textures, mapped=mapped) if moved and node not in moved]


def _switched(text, textures, loop, mapped=()):
    at = re.search(rf'(?mis)^[ \t]*newanim[ \t]+{loop}[ \t].*?^[ \t]*doneanim[ \t]+{loop}[ \t]', text)
    if not at:
        return []
    nodes = list(reversed(NODE.findall(_geometry(text))))  # the first node of a name is the one the game reads
    rest = {name.split()[0].lower(): _numbers(_field(body, 'position') or '0 0 0')[:3] for kind, name, body in nodes}

    def away(name, body):  # a key that puts the node somewhere else than it rests: a loop written out of a modeller keys every node where it is
        rows = re.search(r'(?mi)^[ \t]*positionkey[^\r\n]*\r?\n((?:[ \t]*[-+0-9.eE \t]+\r?\n)+)', body)
        home = rest.get(name, [0.0, 0.0, 0.0]); plain = _field(body, 'position')  # a plain place in an animation is its one key (dgt04_e09_21)
        keys = [row[1:4] for row in map(_numbers, rows.group(1).splitlines()) if len(row) >= 4] if rows else [_numbers(plain)[:3]] if plain else []
        return any(len(key) == 3 and max(abs(a - b) for a, b in zip(key, home)) > 0.01 for key in keys)
    moved = {name.split()[0].lower() for kind, name, body in NODE.findall(at.group(0)) if away(name.split()[0].lower(), body)}
    above = {name.split()[0].lower(): (_field(body, 'parent') or 'NULL').split()[0].lower() for kind, name, body in nodes}
    told = []
    for node, parent, texture in lit_nodes(text, textures, mapped=mapped):
        seen, one = set(), node.split()[0].lower()
        while one in above and one not in seen:
            if one in moved:
                told.append(node); break
            seen.add(one); one = above[one]
    return told


def switches(spec):
    """The textures of a list whose lit meshes a tile loop may raise: its lit panes and its `switched` signs. A sign
    is lit at every hour, but only where its loop is on: the motel and cheque signs of the Modern Exterior rest parked
    under the tile (2026-11-24). The loops of a traffic light or a beacon are the builder's, and are not listed."""
    return {**spec['lit'], **dict.fromkeys(spec.get('switched', ()))}


def lights_on(repo, tileset, lit, pack=None, mapped=()):
    """Turn each of AnimLoop1 to 3 on in a tileset's set file for every tile whose model's lit meshes are switched by
    it, and tell the models turned on. The standard (user, 2026-11-24): the hour drives the lights, through the day and
    night animations; a tile loop is the builder's switch for a building that stands dark, and is on unless turned off.
    The Modern Exterior shops switch their upper windows by the first loop and the shop window by the second, which the
    set left off (2026-11-24)."""
    from .compiled import SOURCES
    pack = pack or f'srn_t_{tileset.lower()}'; path = Path(repo) / pack / f'{tileset.lower()}.set'; text = path.read_bytes().decode('cp1252'); told = []

    def model(name):
        homes = dict.fromkeys((pack, *(one.format(tileset=tileset.lower()) for one in lamps.PACKS)))  # its own pack, then the common one: 109 Modern Exterior tiles live there
        for folder in (Path(repo) / kept / home for home in homes for kept in (SOURCES, '')):
            if (folder / f'{name}.mdl').is_file():
                return (folder / f'{name}.mdl').read_bytes().decode('cp1252', errors='replace')
        return ''

    def one(at):
        name = re.search(r'(?mi)^Model=(\S+)', at.group(0)); tile = at.group(0)
        for loop in LOOPS:
            if name and re.search(rf'(?m)^AnimLoop{loop}=0[ \t]*\r?$', tile) and switched(model(name.group(1).lower()), lit, f'animloop0{loop}', mapped):
                told.append(name.group(1).lower()); tile = re.sub(rf'(?m)^AnimLoop{loop}=0([ \t]*\r?)$', rf'AnimLoop{loop}=1\1', tile)
        return tile
    new = re.sub(r'(?ms)^\[TILE\d+\][^\[]*', one, text)
    if told:
        path.write_bytes(new.encode('cp1252'))
    return sorted(set(told))


def write(repo, tileset, folder, lit, shared=(), again=False, mapped=()):
    """Write the models of a tileset that have lit meshes, with their day and night, into `folder` (a review's
    overlay; a model already there is changed in place) and tell {'models': {model: lit meshes}, 'panes': day panes
    made, 'refused': {model: why}, 'done': how many had their day and night already (a second run, or the pack's own),
    'parked': {model: its lit meshes no loop raises where a loop raises others (`never`)}}.
    again: a model that has its day and night is made anew from the list, and written where that changes it (a lit
    texture given a day texture since: the windows of eleven suburb tiles were blank by day, 2026-11-24). shared: the tilesets that draw these tiles too and take the change with them (a merged
    set); a model any other tileset draws is left. mapped: the lit textures that glow through their materials (`mapped`)."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {'models': {}, 'panes': 0, 'refused': {}, 'done': 0, 'parked': {}}
    from .apply import noted
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if set(others) - {one.lower() for one in shared}:  # another tileset draws it too
            continue
        if never(text, lit, mapped):
            told['parked'][name] = never(text, lit, mapped)
        if lit_nodes(text, lit, mapped=mapped) and {one.lower() for one in re.findall(r'(?mi)^[ \t]*newanim[ \t]+(\S+)', text)} >= set(ANIMS):
            told['done'] += 1
            if not again:
                continue
        try:
            new, count, panes = with_daylight(without(text) if again else text, lit, mapped)
        except ValueError as error:
            told['refused'][name] = str(error); continue
        if count and new != text:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told['models'][name] = count; told['panes'] += panes
    return told
