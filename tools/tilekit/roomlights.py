"""Room lights switched by script (user, 2026-11-26: "script driven switching is probably best for interiors").

Every light fitting of the interior families glowed of its own at every hour, and a fitting's glow lights nothing: a
room's light is its tiles' main lights. So each lit mesh of a list's textures gets an unlit copy in its place (`<mesh>_off`: the
same mesh with no glow of its own, or another texture: a ceiling whose panels glow through its material's glow map
takes a material without the map), and the lit mesh rests parked `PARK` metres under its place. The tile's third loop
(`animloop03`) lifts the lit mesh home and parks the unlit copy, so a tile is lit while its AnimLoop3 is on: the set
file turns it on for every tile switched here (`loops_on`), and SR_NWN turns a room off and on with
Anvil's `NwArea.SetTiles` (NWScript has no tile loop call) (docs/tilesets/srx02/sr-nwn-room-lights.md). As the day and night of `daylight`, the loop plays
only on what hangs from the tile's animated node (`daylight.animated`).

A model is switched once: a mesh the loop moves already is left, and `unswitch` gives back the model as it was (the
prefab rooms and passage joins are cut from the family tiles: they read them unswitched and switch what they make).
A lit mesh another loop moves (a sign the builder switches) is refused, as is a third loop that moves anything else.
A third loop that moves nothing (a modeller's, written out with every node at rest) is dropped.

The list (`docs/tilesets/<set>/lights.json`): {"lit": {lit texture: the texture of its unlit copy, or null for its own},
"mapped": [lit textures that glow through their materials' glow maps], "offMaterials": {unlit material: the lit texture
whose material it is, without the glow map}}."""
import json
import re
from pathlib import Path

from . import daylight, inventory, lamps, require

LOOP = 'animloop03'
PARK = 60.0  # metres under its place a switched-off lit mesh rests: under any floor of the tile, out of every view
SUFFIX = '_off'
LENGTH = 0.03333


def load(path):
    spec = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    require(isinstance(spec.get('lit'), dict) and spec['lit'], f'{path}: a list of lights names its lit textures (`lit`)')
    mapped = {name.lower() for name in spec.get('mapped', ())}
    require(mapped <= {name.lower() for name in spec['lit']}, f'{path}: `mapped` names a texture `lit` does not')
    for off, lit in spec.get('offMaterials', {}).items():
        require((spec['lit'].get(lit) or '').lower() == off.lower(), f'{path}: {off} is the unlit texture of {lit} in `lit`')
    return spec


def _name(text):
    return re.search(r'(?mi)^[ \t]*newmodel[ \t]+(\S+)', text).group(1)


def _loop(text):
    return re.search(rf'(?mis)^[ \t]*newanim[ \t]+{LOOP}[ \t].*?^[ \t]*doneanim[ \t]+{LOOP}[ \t][^\n]*\n', text)


def _rests(text):
    """{node (lower case): (its name, its parent, its place)} of the model's geometry, the first node of a name."""
    found = {}
    for kind, name, body in daylight.NODE.findall(daylight._geometry(text)):
        found.setdefault(name.split()[0].lower(), (name.split()[0], (daylight._field(body, 'parent') or 'NULL').split()[0], tuple(daylight._numbers(daylight._field(body, 'position') or '0 0 0')[:3])))
    return found


def _keyed(block):
    """{node (lower case): its first key} of the nodes an animation places."""
    found = {}
    for kind, name, body in daylight.NODE.findall(block):
        rows = re.search(r'(?mi)^[ \t]*positionkey[^\r\n]*\r?\n((?:[ \t]*[-+0-9.eE \t]+\r?\n)+)', body); plain = daylight._field(body, 'position')
        keys = [row[1:4] for row in map(daylight._numbers, rows.group(1).splitlines()) if len(row) >= 4] if rows else [daylight._numbers(plain)[:3]] if plain else []
        if keys:
            found[name.split()[0].lower()] = tuple(keys[0])
    return found


def _moved(text):
    """{node: its key} of the nodes the third loop puts somewhere else than they rest."""
    at = _loop(text)
    if not at:
        return {}
    rests = _rests(text)
    return {node: key for node, key in _keyed(at.group(0)).items() if max(abs(a - b) for a, b in zip(key, rests.get(node, (None, None, (0, 0, 0)))[2])) > 0.01}


def _pairs(text):
    """[(lit node, its unlit copy)] the third loop switches, as written here; refused when it moves anything else."""
    moved = _moved(text); rests = _rests(text)
    pairs = [(rests[node][0], rests[node + SUFFIX][0]) for node in moved if node + SUFFIX in moved]
    strange = sorted(set(moved) - {one.lower() for pair in pairs for one in pair})
    require(not strange, f'{_name(text)}: its {LOOP} moves ' + ', '.join(strange) + ', which are no lights switched here')
    return pairs


def _place(block, position):
    value = ' '.join(f'{one:.7g}' for one in position)
    if daylight._field(block, 'position') is not None:
        return re.sub(r'(?mi)^([ \t]*position[ \t]+)[^\r\n]*?([ \t]*\r?)$', lambda at: at.group(1) + value + at.group(2), block, count=1)
    return re.sub(r'(?mi)^([ \t]*)(parent[ \t][^\r\n]*?)(\r?\n)', lambda at: f'{at.group(0)}{at.group(1)}position {value}{at.group(3)}', block, count=1)


def _block(text, node):
    return next(at for at in daylight.NODE.finditer(daylight._geometry(text)) if at.group(2).split()[0].lower() == node.lower())


def _written(text, pairs):
    """The model's text with its third loop written anew for `pairs` [(lit, unlit copy, home)]."""
    if _loop(text):
        text = text[:_loop(text).start()] + text[_loop(text).end():]
    if not pairs:
        return text
    name = _name(text); rests = _rests(text); ending = '\r\n' if '\r\n' in text else '\n'; said = {name.lower()}
    lines = [f'newanim {LOOP} {name}', f'  length {LENGTH:.5f}', '  transtime 0.0', f'  animroot {name}', f'  node dummy {name}', '    parent NULL', '  endnode']

    def chain(node):  # an animation names a node's whole line of parents
        line, one = [], rests[node.lower()][1]
        while one.lower() not in said and one.lower() in rests:
            line.append(one); one = rests[one.lower()][1]
        for one in reversed(line):
            said.add(one.lower()); lines.extend([f'  node dummy {rests[one.lower()][0]}', f'    parent {rests[one.lower()][1]}', '  endnode'])
    for lit, off, home in pairs:
        parked = (home[0], home[1], home[2] - PARK)
        for node, key in ((lit, home), (off, parked)):
            chain(node); said.add(node.lower()); row = ' '.join(f'{one:.5f}' for one in key)
            lines.extend([f'  node trimesh {node}', f'    parent {rests[node.lower()][1]}', '    positionkey 2', f'      0.00000 {row}', f'      {LENGTH:.5f} {row}', '    endlist', '  endnode'])
    lines.append(f'doneanim {LOOP} {name}')
    at = re.search(r'(?mi)^[ \t]*donemodel', text); require(at, f'{name} has no donemodel line')
    return text[:at.start()] + ending.join(lines) + ending + text[at.start():]


def switch(text, lit, mapped=()):
    """(the model's text with its lit meshes switched by the third loop, how many switched now). lit: {lit texture:
    the texture of its unlit copy or None}. A model with no lit mesh to switch is given back as it is."""
    lit = {key.lower(): (value.lower() if value else None) for key, value in lit.items()}; mapped = {one.lower() for one in mapped}
    at = _loop(text)
    if at and not _moved(text):  # a modeller's loop that keys every node where it rests
        text = text[:at.start()] + text[at.end():]
    done = _pairs(text); switched = {one.lower() for pair in done for one in pair}
    found = [one for one in daylight.lit_nodes(text, lit, mapped=mapped) if one[0].split()[0].lower() not in switched and not one[0].lower().endswith(SUFFIX)]
    if not found:
        return text, 0
    name = _name(text); original = text
    for loop in ('animloop01', 'animloop02'):
        held = daylight._switched(text, lit, loop, mapped)
        require(not held, f'{name}: {loop} moves the lit meshes ' + ', '.join(held) + ': a light the builder switches is left to them')
    rests = _rests(text); words = [node.split()[0].lower() for kind, node, body in daylight.NODE.findall(daylight._geometry(text))]
    pairs = [(rests[lit_.lower()][0], rests[off.lower()][0], _keyed(_loop(text).group(0))[lit_.lower()]) for lit_, off in done]
    lights = {node.split()[0].lower() for node, parent, texture in found}
    for node, parent, texture in found:
        node = node.split()[0]; off = f'{node}{SUFFIX}'
        require(words.count(node.lower()) == 1 and off.lower() not in words, f'{name}: the lit mesh {node!r} shares its name with another mesh')
        require(not re.search(r'(?mi)^[ \t]*parent[ \t]+' + re.escape(node) + r'[ \t]*\r?$', daylight._geometry(text)), f'{name}: the lit mesh {node!r} has children')
        text, _ = daylight.animated(text, node, lights)
        block = _block(text, node); home = tuple(daylight._numbers(daylight._field(block.group(0), 'position') or '0 0 0')[:3])
        copy = re.sub(r'(?mi)^([ \t]*node[ \t]+trimesh[ \t]+)\S+', lambda one: one.group(1) + off, block.group(0), count=1)
        copy = re.sub(r'(?mi)^([ \t]*selfillumcolor[ \t]+)[^\r\n]*?([ \t]*\r?)$', lambda one: one.group(1) + '0 0 0' + one.group(2), copy)
        if lit[texture]:
            copy = re.sub(r'(?mi)^([ \t]*bitmap[ \t]+)\S+', lambda one: one.group(1) + lit[texture], copy)
        parked = _place(block.group(0), (home[0], home[1], home[2] - PARK))
        text = text[:block.start()] + parked + copy + text[block.end():]; pairs.append((node, off, home))
    made = _written(text, pairs)
    require(inventory.walk_hash(made) == inventory.walk_hash(original), f'{name}: the walkmesh would change')
    return made, len(found)


def unswitch(text):
    """The model's text as it was before `switch`: each lit mesh home, its unlit copy and the third loop gone. The
    lit meshes stay hung from the animated node, which changes nothing the game shows."""
    pairs = _pairs(text)
    if not pairs:
        return text
    keys = _keyed(_loop(text).group(0)); text = _written(text, [])
    for lit, off in pairs:
        block = _block(text, lit); text = text[:block.start()] + _place(block.group(0), keys[lit.lower()]) + text[block.end():]
        block = _block(text, off); text = text[:block.start()] + text[block.end():]
    return text


def switched(text):
    """Whether the model's third loop switches lights written here."""
    return bool(_pairs(text))


def loops_on(set_path, text_of):
    """Turn AnimLoop3 on in a set file for every tile whose model (`text_of(name)`: its ASCII text, or '' where none is
    found) is switched here, so a painted room is lit; tell the models turned on."""
    path = Path(set_path); text = path.read_bytes().decode('cp1252'); told = []

    def one(at):
        name = re.search(r'(?mi)^Model=(\S+)', at.group(0)); tile = at.group(0)
        if name and re.search(r'(?m)^AnimLoop3=0[ \t]*\r?$', tile) and switched(text_of(name.group(1).lower())):
            told.append(name.group(1).lower()); tile = re.sub(r'(?m)^AnimLoop3=0([ \t]*\r?)$', r'AnimLoop3=1\1', tile)
        return tile
    new = re.sub(r'(?ms)^\[TILE\d+\][^\[]*', one, text)
    if told:
        path.write_bytes(new.encode('cp1252'))
    return sorted(set(told))


def off_materials(repo, spec, packs, *, check=False):
    """Write the unlit materials of a list beside the materials they are made from (as `daylight.day_materials`)."""
    return daylight.day_materials(repo, {'lit': spec['lit'], 'dayMaterials': spec.get('offMaterials', {})}, packs, check=check)


def write(repo, tileset, folder, spec, shared=()):
    """Write the tileset's models that have lights to switch, switched, into `folder` (a review's overlay; a copy already
    there is the one changed). {'models': {model: meshes switched}, 'refused': {model: why}}. shared: as `daylight.write`."""
    from .apply import noted
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {'models': {}, 'refused': {}}
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if set(others) - {one.lower() for one in shared}:
            continue
        try:
            new, count = switch(text, spec['lit'], spec.get('mapped', ()))
        except ValueError as error:
            told['refused'][name] = str(error); continue
        if count:
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told['models'][name] = count
    return told
