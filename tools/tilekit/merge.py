"""One tileset made of several: every tile, group and rule of the source sets under one set file, with the names a
names file gives them.

A builder paints one area with tiles of all the source sets. The tile models stay in the source sets' packs; the
merged pack holds the set file, its palette and (later) the join tiles, and the edge table goes beside the others.
A merge is worked out whole from the source set files, their edge tables, the names file and a spec, so a second run
writes the same bytes: nothing else writes the merged files. `lock` pins what a merge read and wrote, and `stale`
says what has changed since, so a source set changed later (an envkit sheet's new tiles, say) is seen and merged again.

spec: {set (the merged set's resref), display, names (the names file), families: [{set, label}] in the order their
tiles are numbered (edge: false for a set with no edge table), general (the family whose GENERAL section is kept; envMap, where given, its EnvMap), grass (the family whose [GRASS] is kept),
joins: [[terrain key, terrain key]] the ground pairs join tiles are built for, raised: [terrain key] grounds with
raised tiles, numbers (the record of tile numbers, `numbered`), joinTiles (the joins spec), rooms (the folder of room
specs, `rooms`: each adds two groups of tiles of its own), doors}.

Tile numbers never move: an area keeps the numbers of the tiles it was painted with. The numbers record lists what has
each number, and a tile new to a source set, or a new join tile, takes the next number after the last. A room's tile does too.

names: {terrains, crossers: [{set, name, key, display, palette (false leaves it off the palette)}], folds: [{set,
name, into (a terrain key, or null for a name no tile uses)}], edgeNames: [{set, name, into}] spellings only an edge
table has, groups: [{set, name, display, palette (false leaves it off the palette), repeats (a display for each group
the set names so, where it names several alike; the later ones are called <name>_2, _3)}]}."""
import hashlib
import json
import re
from collections import deque
from pathlib import Path

from . import inventory, joins, require, rooms, walls
from .terrain import _sections

END = '\r\n'
CORNER = re.compile(r'(?m)^(TopLeft|TopRight|BottomLeft|BottomRight)=([^\r\n]*)')
CROSSER = re.compile(r'(?m)^(Top|Right|Bottom|Left)=([^\r\n]*)')
MEMBER = re.compile(r'(?m)^(Tile\d+)=(-?\d+)')
FEATURES, GROUPS, TERRAIN = (0, 63261), (1, 63262), (2, 8282)  # the tile palette's three lists: their ID and name
ERASER, RAISE = ('eraser', 63291), ('raiselower', 63292)
RESREF = 16


def maps(names):
    """({set: {old terrain, lower case: key}}, the same of crossers) from a names file. A fold's name maps to the key
    it folds into; a fold into nothing is a name no tile may use."""
    terrains, crossers = {}, {}
    for kind, found in (('terrains', terrains), ('crossers', crossers)):
        for entry in names[kind]:
            mine = found.setdefault(entry['set'], {})
            require(entry['name'].lower() not in mine, f'{entry["set"]} {entry["name"]} is named twice')
            mine[entry['name'].lower()] = entry['key']
    keys = [entry['key'] for entry in names['terrains'] + names['crossers']]
    require(len(keys) == len({key.lower() for key in keys}), 'Two names share a key')  # the game reads names in any case
    require(all(len(key) <= RESREF for key in keys), f'A key is longer than {RESREF} characters')
    for fold in names.get('folds', ()):
        mine = terrains.setdefault(fold['set'], {})
        require(fold['name'].lower() not in mine or mine[fold['name'].lower()] == fold['into'], f'{fold["set"]} {fold["name"]} is both named and folded')
        require(fold['into'] is None or fold['into'] in {entry['key'] for entry in names['terrains']}, f'{fold["name"]} folds into no terrain')
        if fold['into'] is not None:
            mine[fold['name'].lower()] = fold['into']
    return terrains, crossers


def _lines(text):
    return text.replace('\r', '').split('\n')


def _crlf(raw):
    return END.join(_lines(raw))


def _tile(raw, number, terrains, crossers, where):
    """A tile's section (or one of its doors') again as tile `number`, its corners and crossers under their new names."""
    def corner(found):
        require(found.group(2).lower() in terrains, f'{where}: no name for terrain {found.group(2)!r}')
        return f'{found.group(1)}={terrains[found.group(2).lower()]}'

    def crosser(found):
        require(not found.group(2) or found.group(2).lower() in crossers, f'{where}: no name for crosser {found.group(2)!r}')
        return f'{found.group(1)}={crossers[found.group(2).lower()] if found.group(2) else ""}'
    raw = re.sub(r'^\[TILE\d+', f'[TILE{number}', raw, count=1)
    return CROSSER.sub(crosser, CORNER.sub(corner, raw))


def _rule(placed, adjacent, changed, heights=(0, 0, 0)):
    return {'Placed': placed, 'PlacedHeight': str(heights[0]), 'Adjacent': adjacent, 'AdjacentHeight': str(heights[1]), 'Changed': changed,
            'ChangedHeight': str(heights[2])}


def reach(tiles, joins=()):
    """{terrain: the terrains a tile (or a join to be built) lays beside it}, from tiles' corners under their new names."""
    beside = {}
    for corners in tiles:
        for one in corners:
            beside.setdefault(one, set()).update(other for other in corners if other != one)
    for one, other in joins:
        beside.setdefault(one, set()).add(other); beside.setdefault(other, set()).add(one)
    return beside


def toward(beside, start, goal):
    """The first terrain on the shortest way from `start` to `goal` over terrains that can lie side by side: None when
    they are neighbours already or no way leads there. Of equal ways the one first in name order, so a merge is the
    same each time."""
    if goal in beside.get(start, ()) or start == goal:
        return None
    seen, queue = {start: None}, deque([start])
    while queue:
        here = queue.popleft()
        for there in sorted(beside.get(here, ())):
            if there not in seen:
                seen[there] = here; queue.append(there)
                if there == goal:
                    while seen[there] != start:
                        there = seen[there]
                    return there
    return None


def rules(own, family, beside, raised=(), joins=()):
    """The merged set's primary rules: every source set's own (`own`, under their new names, the first of two alike
    kept), then one for each pair of terrains of two families that no tile lays side by side, changing the neighbour
    to the next terrain on the way there; then the rules that keep a raised ground from a join, which is built flat.
    family: {terrain key: its family}."""
    made, said = [], set()
    for rule in own:
        key = (rule['Placed'].lower(), rule['PlacedHeight'], rule['Adjacent'].lower(), rule['AdjacentHeight'])
        if key not in said:
            said.add(key); made.append(rule)
    for placed in sorted(family):
        for adjacent in sorted(family):
            if family[placed] != family[adjacent] and (placed.lower(), '0', adjacent.lower(), '0') not in said:
                changed = toward(beside, placed, adjacent)
                if changed is not None:
                    said.add((placed.lower(), '0', adjacent.lower(), '0')); made.append(_rule(placed, adjacent, changed))
    for one, other in joins:
        for high, flat in ((one, other), (other, one)):
            if high in raised:  # a raised corner of `high` beside `flat`: the flat ground gives way, and the height change stays within `high`
                made.append(_rule(high, flat, high, (1, 0, 0))); made.append(_rule(flat, high, high, (0, 1, 0)))
    return made


JOIN, ROOM = 'join', 'room'


def numbered(counts, joined, record=(), roomed=()):
    """({(set, its tile's number) or ('join' or 'room', model): the number in the merged set}, the record again with
    what is new) for source sets of `counts` tiles ({set: count}, in the families' order) and the join and room tiles'
    models. record: runs in the order of their numbers, [set, the first source tile, how many] or ['join' or 'room',
    model]. What the record names keeps its number; what it does not is numbered after it, each family's new tiles,
    then the new joins and the new rooms. A tile
    the record names and the sets no longer have is refused: its number would name another tile in a saved area."""
    record = [list(run) for run in record]; number, at = {}, 0; own = {JOIN: list(joined), ROOM: list(roomed)}
    for run in record:
        require(len(run) == 2 and run[0] in own and isinstance(run[1], str) or len(run) == 3 and run[0] not in own and all(isinstance(cell, int) and cell >= 0 for cell in run[1:]),
                f'The numbers record has a run that is neither [set, first tile, how many] nor ["join" or "room", model]: {run}')
        if run[0] in own:
            require(run[1] in own[run[0]], f'The numbers record names the {run[0]} tile {run[1]}, which is no longer built: tile {at} would be lost')
            number[(run[0], run[1])] = at; at += 1
        else:
            name, first, many = run
            require(name in counts and first + many <= counts[name], f'The numbers record names tiles {first} to {first + many - 1} of {name}, which the set no longer has')
            for index in range(many):
                number[(name, first + index)] = at; at += 1
    require(len(number) == at, 'The numbers record names a tile twice')
    for name, count in counts.items():
        for index in range(count):
            if (name, index) not in number:
                number[(name, index)] = at; at += 1
                if record and record[-1][0] == name and record[-1][1] + record[-1][2] == index:
                    record[-1][2] += 1
                else:
                    record.append([name, index, 1])
    for kind, models in own.items():
        for model in models:
            if (kind, model) not in number:
                number[(kind, model)] = at; at += 1; record.append([kind, model])
    return number, record


def merged_set(sets, names, spec, joined=(), numbers=(), roomed=()):
    """(the merged set file's text, {family: the number its first tile takes}, [{set, name (in the merged set), was,
    display, tiles, model (its first tile's)}] of its groups) from the source set files' texts ({set: text}).
    joined: the join tiles (`joins.tiles`). roomed: the room groups (`rooms.records`). numbers: the numbers record
    (`numbered`); without one each family's tiles follow the one before, then the join tiles and the rooms'."""
    terrains, crossers = maps(names); order = [family['set'] for family in spec['families']]
    require(set(order) <= set(sets), 'The spec names a set that was not given'); require(spec['general'] in order and spec['grass'] in order, 'general and grass name a family')
    read = {name: inventory.sections(sets[name]) for name in order}; laid = {name: inventory.read_set(sets[name]) for name in order}
    for name in order:
        require([tile['number'] for tile in laid[name]['tiles']] == list(range(len(laid[name]['tiles']))), f'{name}: its tiles are not numbered from 0 in order')
    number, _ = numbered({name: len(laid[name]['tiles']) for name in order}, [record['model'] for record in joined], numbers, room_models(roomed))
    first = {name: number[(name, 0)] for name in order if laid[name]['tiles']}; count = len(number)
    tiles = {}; doors = {str(key): value for key, value in spec.get('doors', {}).items()}
    for name in order:
        for section, raw in _sections(sets[name]):
            found = re.fullmatch(r'TILE(\d+)(DOOR\d+)?', section)
            if found:
                if found.group(2):  # a door type keyed to a source set is one the Toolset does not know in the merged set: its copy, keyed to this set
                    raw = re.sub(r'(?m)^Type=(\d+)', lambda said: f'Type={doors.get(said.group(1), said.group(1))}', raw)
                tiles.setdefault(number[(name, int(found.group(1)))], []).append(
                    _crlf(_tile(raw, number[(name, int(found.group(1)))], terrains.get(name, {}), crossers.get(name, {}), f'{name} tile {found.group(1)}')).rstrip(END) + END)
    for record in joined:  # flat, open ground with no light, door or sound of its own
        keys = {'Model': record['model'], 'WalkMesh': 'msb01'}
        for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'):
            keys[corner] = record['corners'][corner]; keys[corner + 'Height'] = 0
        keys.update({side: record['crossers'][side] for side in ('Top', 'Right', 'Bottom', 'Left')})
        keys.update(dict.fromkeys(('MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1', 'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds'), 0))
        keys.update(dict.fromkeys(('MainLight1', 'MainLight2'), record.get('lights', 0)))  # a passage join has a main light over each half
        node, turned = record.get('path', ('A', 0))  # a passage join's is a straight passage's
        keys.update({'PathNode': node, 'Orientation': turned, 'ImageMap2D': record['minimap']})
        tiles[number[(JOIN, record['model'])]] = [f'[TILE{number[(JOIN, record["model"])]}]{END}' + ''.join(f'{key}={value}{END}' for key, value in keys.items())]
    for room in roomed:  # a tile of a room is its shell's tile under a model of its own: the same corners, crossers, lights and doors
        name = room['set']; members = [(*one, path) for one, path in zip(room['tiles'], room['paths']) if one]
        for section, said in _sections(sets[name]):
            found = re.fullmatch(r'TILE(\d+)(DOOR\d+)?', section); source = int(found.group(1)) if found else None
            for model, path in ((model, path) for member, model, path in members if member == source):  # a room drawn here may take several tiles from one
                at = number[(ROOM, model)]; raw = re.sub(r'(?m)^Model=[^\r\n]*', lambda _: f'Model={model}', said)
                if model.lower() in room.get('switched', ()) and not found.group(2):  # its lights switched (roomlights): lit when painted
                    raw = re.sub(r'(?m)^AnimLoop3=\d+', 'AnimLoop3=1', raw)
                if path and not found.group(2):  # and it is open where its own walls say
                    for key, value in (('PathNode', path[0]), ('VisibilityNode', path[0]), ('Orientation', path[1]), ('VisibilityOrientation', path[1])):
                        raw = re.sub(rf'(?m)^{key}=[^\r\n]*', f'{key}={value}', raw)
                if found.group(2):
                    raw = re.sub(r'(?m)^Type=(\d+)', lambda said: f'Type={doors.get(said.group(1), said.group(1))}', raw)
                tiles.setdefault(at, []).append(_crlf(_tile(raw, at, terrains.get(name, {}), crossers.get(name, {}), f'{name} tile {source}')).rstrip(END) + END)
        for one, hooks in zip(room['tiles'], room.get('hooks') or [()] * len(room['tiles'])):  # and a door hook in each of its own doorways
            if one and hooks:
                at = number[(ROOM, one[1])]; own = tiles[at]; had = int(re.search(r'(?m)^Doors=(\d+)', own[0]).group(1))
                own[0] = re.sub(r'(?m)^Doors=\d+', f'Doors={had + len(hooks)}', own[0], count=1)
                own += [f'[TILE{at}DOOR{had + index}]{END}Type={walls.GENERIC}{END}X={x:g}{END}Y={y:g}{END}Z=0{END}Orientation={turn}{END}' for index, (x, y, turn) in enumerate(hooks)]
    # groups
    shown = {(entry['set'], entry['name']): entry for entry in names['groups']}; groups, taken, begun, met = [], set(), set(), {}
    for name in order:
        label = next(family['label'] for family in spec['families'] if family['set'] == name); models = {tile['number']: tile['model'] for tile in laid[name]['tiles']}
        for section, raw in _sections(sets[name]):
            if not re.fullmatch(r'GROUP\d+', section):
                continue
            keys = dict(line.split('=', 1) for line in _lines(raw) if '=' in line); was = keys['Name']
            require((name, was) in shown, f'{name}: no display name for group {was}')
            members = [int(keys[f'Tile{index}']) for index in range(int(keys['Rows']) * int(keys['Columns']))]
            real = [member for member in members if member >= 0]  # -1 is a slot with no tile
            require(real and all(member in models for member in real), f'{name} group {was} names a tile the set lacks')
            if models[real[0]].lower() in begun:  # the Toolset finds a group by its first tile's model, so a second one with that model lays the first
                continue  # (seen 2026-11-21: an envkit building's suburb copy laid its city copy); its tiles stay, its group is left out
            begun.add(models[real[0]].lower())
            entry = shown[(name, was)]; again = met.get((name, was), 0); met[(name, was)] = again + 1
            if 'repeats' in entry:  # a set that names several groups alike (tbx78's three room2x1): a display for each, in the set's order
                require(again < len(entry['repeats']), f'{name}: group {was} stands more often than its names entry lists displays')
            display = entry['repeats'][again] if 'repeats' in entry else entry['display']
            called = f'{was}_{again + 1}' if again and 'repeats' in entry else was
            called = called if called.lower() not in taken else f'{called}_{label}'  # an envkit building stands in two families under one name
            require(called.lower() not in taken, f'Two groups are named {called}'); taken.add(called.lower())
            raw = re.sub(r'^\[GROUP\d+', f'[GROUP{len(groups)}', raw, count=1)
            raw = re.sub(r'(?m)^Name=[^\r\n]*', lambda _: f'Name={called}', raw, count=1)
            raw = MEMBER.sub(lambda found: f'{found.group(1)}={number[(name, int(found.group(2)))] if int(found.group(2)) >= 0 else -1}', raw)
            groups.append({'set': name, 'name': called, 'was': was, 'display': display, 'palette': entry.get('palette', True), 'tiles': [number[(name, member)] if member >= 0 else -1 for member in members],
                           'model': models[real[0]], 'raw': _crlf(raw).rstrip(END) + END})
    for room in roomed:
        require(room['name'].lower() not in taken, f'Two groups are named {room["name"]}'); taken.add(room['name'].lower())
        require(room['display'] not in {group['display'] for group in groups}, f'Two groups are shown as {room["display"]}')
        members = [number[(ROOM, one[1])] if one else -1 for one in room['tiles']]
        keys = {'Name': room['name'], 'Rows': room['rows'], 'Columns': room['columns'], **{f'Tile{index}': member for index, member in enumerate(members)}}
        groups.append({'set': room['set'], 'name': room['name'], 'was': None, 'display': room['display'], 'palette': True, 'tiles': members, 'model': next(filter(None, room['tiles']))[1],
                       'raw': f'[GROUP{len(groups)}]{END}' + ''.join(f'{key}={value}{END}' for key, value in keys.items())})
    # rules
    own = []
    for name in order:
        for section, keys in read[name]:
            if re.fullmatch(r'PRIMARY RULE\d+', section):
                rule = dict(keys)
                for key in ('Placed', 'Adjacent', 'Changed'):
                    require(rule[key].lower() in terrains.get(name, {}), f'{name}: a rule names terrain {rule[key]!r}, which has no name')
                    rule[key] = terrains[name][rule[key].lower()]
                own.append(rule)
    family = {entry['key']: entry['set'] for entry in names['terrains']}
    corners = [[terrains[name][corner.lower()] for corner in tile['corners']] for name in order for tile in laid[name]['tiles']]
    known = {entry['key'] for entry in names['terrains']}; lines = {entry['key'] for entry in names['crossers']} | {''}
    require(all(set(record['corners'].values()) <= known and set(record['crossers'].values()) <= lines for record in joined), 'A join tile names a terrain or crosser the set lacks')
    corners += [list(record['corners'].values()) for record in joined]
    joins = [tuple(pair) for pair in spec.get('joins', ())]
    require(all(key in family for pair in joins for key in pair) and all(key in family for key in spec.get('raised', ())), 'A join or a raised ground names no terrain')
    primary = rules(own, family, reach(corners, joins), spec.get('raised', ()), joins)
    # head
    general = dict(next(keys for section, keys in read[spec['general']] if section == 'GENERAL'))
    general.update({'Name': spec['set'].upper(), 'UnlocalizedName': spec['display'], 'DisplayName': '-1'})
    if spec.get('envMap'):  # the set's one reflection picture, its own rather than the general family's (srx02, 2026-11-27)
        general['EnvMap'] = spec['envMap']
    for key in ('Border', 'Default', 'Floor'):
        require(general.get(key, '').lower() in terrains.get(spec['general'], {}), f'{spec["general"]}: GENERAL has {key}={general.get(key)!r}, which has no name')
        general[key] = terrains[spec['general']][general[key].lower()]
    grass = next((keys for section, keys in read[spec['grass']] if section == 'GRASS'), None)

    def block(title, keys):
        return f'[{title}]{END}' + ''.join(f'{key}={value}{END}' for key, value in keys.items()) + END
    out = [block('GENERAL', general)] + ([block('GRASS', grass)] if grass else [])
    out.append(block('TERRAIN TYPES', {'Count': len(names['terrains'])}))
    out += [block(f'TERRAIN{index}', {'Name': entry['key']}) for index, entry in enumerate(names['terrains'])]
    out.append(block('CROSSER TYPES', {'Count': len(names['crossers'])}))
    out += [block(f'CROSSER{index}', {'Name': entry['key']}) for index, entry in enumerate(names['crossers'])]
    out.append(block('PRIMARY RULES', {'Count': len(primary)}))
    out += [block(f'PRIMARY RULE{index}', rule) for index, rule in enumerate(primary)]
    out.append(block('SECONDARY RULES', {'Count': 0}))
    out.append(block('TILES', {'Count': count}))
    out += [section + END for at in sorted(tiles) for section in tiles[at]]  # a tile's own section, then its doors'
    out.append(block('GROUPS', {'Count': len(groups)}))
    out += [group.pop('raw') + END for group in groups]
    return ''.join(out), first, groups


def room_models(roomed):
    return [one[1] for room in roomed for one in room['tiles'] if one]


def merged_edge(edges, names, spec, joined=()):
    """The merged edge table's text from the source sets' ({set: text}): every row of each, in the families' order,
    under the new names; then the border rows of the join pairs (`joins.edges`)."""
    terrains, crossers = maps(names); rows = []
    terrains = {name: dict(found) for name, found in terrains.items()}; crossers = {name: dict(found) for name, found in crossers.items()}
    for other in names.get('edgeNames', ()):  # a name only an edge table spells: its rows never matched the source set, and do here
        kind = terrains if other['into'] in {entry['key'] for entry in names['terrains']} else crossers
        require(other['into'] in {entry['key'] for entry in names['terrains'] + names['crossers']}, f'{other["name"]} is spelled for no key')
        kind.setdefault(other['set'], {})[other['name'].lower()] = other['into']
    for name in (family['set'] for family in spec['families'] if family['set'] in edges):
        lines = [inventory.words(line) for line in _lines(edges[name])[3:] if line.strip()]
        for cells in lines:
            require(len(cells) == 6, f'{name}: an edge row has not six cells: ' + ' '.join(cells))
            _, one, edge, other, height, model = cells

            def corner(cell):  # a corner left open is ****; a raised one carries a + after its terrain
                if cell == '****':
                    return cell
                base, raised = (cell[:-1], '+') if cell.endswith('+') else (cell, '')
                require(base.lower() in terrains.get(name, {}), f'{name}: an edge row names terrain {cell!r}, which has no name')
                return terrains[name][base.lower()] + raised
            between = crossers.get(name, {}).get(edge.lower()) or (corner(edge) if edge == '****' or edge.rstrip('+').lower() in terrains.get(name, {}) else None)
            require(between, f'{name}: an edge row has {edge!r} between its corners, which is no crosser or terrain with a name')  # a terrain stands there too (a bridge's deck)
            rows.append((corner(one), between, corner(other), height, model))
    rows += [(one, '****', other, '0', model) for one, other, model in joined]
    wide = [max((len(row[index]) for row in rows), default=0) + 2 for index in range(5)]; head = ('Corner1', 'Edge', 'Corner2', 'Height', 'Model'); number = len(str(len(rows))) + 2
    lines = ['2DA V2.0', '', ' ' * number + ''.join(cell.ljust(max(width, len(cell) + 2)) for cell, width in zip(head, wide)).rstrip()]
    lines += [str(index).ljust(number) + ''.join(cell.ljust(max(width, len(head[at]) + 2)) for at, (cell, width) in enumerate(zip(row, wide))).rstrip() for index, row in enumerate(rows)]
    return '\n'.join(lines) + '\n'  # a 2DA is kept with plain line ends in the repository (.gitattributes): the bytes written are the bytes checked out


def palette(names, groups):
    """The merged set's palette as nwn_gff's JSON: single tiles under Features, groups of several under Groups, the
    terrains and crossers under Terrain with the eraser and the raise tool, each list in the order of its names."""
    entry = lambda shown, resref: {'__struct_id': 0, 'NAME': {'type': 'cexostring', 'value': shown}, 'RESREF': {'type': 'resref', 'value': resref}}
    tool = lambda resref, name: {'__struct_id': 0, 'RESREF': {'type': 'resref', 'value': resref}, 'STRREF': {'type': 'dword', 'value': name}}
    node = lambda which, listed: {'__struct_id': 0, 'ID': {'type': 'byte', 'value': which[0]}, 'LIST': {'type': 'list', 'value': listed}, 'STRREF': {'type': 'dword', 'value': which[1]}}
    ordered = lambda found: [entry(shown, resref) for shown, resref in sorted(found, key=lambda pair: (pair[0].lower(), pair[1]))]
    listed = [group for group in groups if group.get('palette', True)]  # a group off the palette stays in the set: an area laid with it still reads
    single = [(group['display'], group['model']) for group in listed if len(group['tiles']) == 1]
    several = [(group['display'], group['model']) for group in listed if len(group['tiles']) > 1]
    painted = [(one['display'], one['key'].lower()) for one in names['terrains'] + names['crossers'] if one.get('palette', True)]
    return {'__data_type': 'ITP ', 'MAIN': {'type': 'list', 'value': [node(FEATURES, ordered(single)), node(GROUPS, ordered(several)),
                                                                     node(TERRAIN, [tool(*ERASER), tool(*RAISE)] + ordered(painted))]}}


def paths(repo, spec):
    """(inputs {label: path}, outputs {label: path}) of a merge in a repository."""
    repo = Path(repo); name = spec['set']; pack = repo / f'srn_t_{name}'
    inputs = {'names': repo / spec['names']}
    for family in spec['families']:
        inputs[f'set:{family["set"]}'] = repo / f'srn_t_{family["set"]}' / f'{family["set"]}.set'
        if family.get('edge', True):  # false: a source set with no edge table (tfb01, nac01)
            inputs[f'edge:{family["set"]}'] = repo / 'srn_2da' / f'{family["set"]}_edge.2da'
    if spec.get('rooms'):
        inputs.update({f'room:{path.stem}': path for path in sorted((repo / spec['rooms']).glob('*.json'))})
    if spec.get('joinTiles'):
        inputs['joins'] = repo / spec['joinTiles']
    outputs = {'set': pack / f'{name}.set', 'palette': pack / f'{name}palstd.itp', 'edge': repo / 'srn_2da' / f'{name}_edge.2da'}
    if spec.get('numbers'):  # read and written: the merge before this one wrote what this one keeps
        outputs['numbers'] = repo / spec['numbers']
    return inputs, outputs


def work(repo, spec):
    """What a merge writes, worked out and not written: {set, edge: text, palette: JSON, first, groups, numbers (the
    numbers record's text, where the spec keeps one)}."""
    inputs, outputs = paths(repo, spec); names = json.loads(inputs['names'].read_text(encoding='utf-8'))
    order = [family['set'] for family in spec['families']]; cut = json.loads(inputs['joins'].read_text(encoding='utf-8')) if 'joins' in inputs else None
    sets = {name: inputs[f'set:{name}'].read_bytes().decode('cp1252') for name in order}; joined = joins.tiles(cut) if cut else (); record = None
    roomed = rooms.records(rooms.specs(Path(repo) / spec['rooms']), sets, spec['set']) if spec.get('rooms') else ()
    if spec.get('lights'):  # a room tile whose lights are switched (roomlights) is lit while its third loop is on
        from .compiled import SOURCES
        from .roomlights import switched
        source = lambda model: Path(repo) / SOURCES / f'srn_t_{spec["set"]}' / f'{model}.mdl'
        for room in roomed:
            room['switched'] = {one[1].lower() for one in room['tiles'] if one and source(one[1]).is_file() and switched(source(one[1]).read_bytes().decode('cp1252'))}
    if 'numbers' in outputs:
        kept = json.loads(outputs['numbers'].read_text(encoding='utf-8')) if outputs['numbers'].is_file() else {'tiles': []}
        require(isinstance(kept, dict) and isinstance(kept.get('tiles'), list), f'{outputs["numbers"].name} is no numbers record: it has no list of tiles')
        _, record = numbered({name: len(inventory.read_set(sets[name])['tiles']) for name in order}, [one['model'] for one in joined], kept['tiles'], room_models(roomed))
    text, first, groups = merged_set(sets, names, spec, joined, record or (), roomed)
    if 'numbers' in outputs and not outputs['numbers'].is_file() and outputs['set'].is_file():
        # The record is lost and the set is there: numbered afresh, a tile added since would take a number in the
        # middle. A set whose tiles all keep their numbers so is one the record is first kept for.
        models = lambda found: [tile['model'].lower() for tile in inventory.read_set(found)['tiles']]
        was, now = models(outputs['set'].read_bytes().decode('cp1252')), models(text)
        require(now[:len(was)] == was, f'The numbers record {outputs["numbers"].name} is missing, and without it tiles of {outputs["set"].name} would take other numbers: restore it')
    edge = merged_edge({name: inputs[f'edge:{name}'].read_bytes().decode('cp1252') for name in order if f'edge:{name}' in inputs}, names, spec, joins.edges(cut) if cut else ())
    numbers = None if record is None else '{\n "schemaVersion": 1,\n "kind": "tilekit-merge-numbers",\n "tiles": [\n' + ',\n'.join('  ' + json.dumps(run) for run in record) + '\n ]\n}\n'
    return {'set': text, 'edge': edge, 'palette': palette(names, groups), 'first': first, 'groups': groups, 'numbers': numbers}


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stale(repo, spec, spec_path, lock_path):
    """What has changed since the merge the lock records: the labels of the inputs and outputs whose bytes differ,
    'spec' for the spec itself, ['lock'] when there is no lock."""
    if not Path(lock_path).is_file():
        return ['lock']
    lock = json.loads(Path(lock_path).read_text(encoding='utf-8')); inputs, outputs = paths(repo, spec)
    now = {**{label: _hash(path) if path.is_file() else None for label, path in {**inputs, **outputs}.items()}, 'spec': _hash(spec_path)}
    said = {**lock['inputs'], **lock['outputs']}
    return sorted(label for label in {**said, **now} if now.get(label) != said.get(label))  # a room taken away too


def merge(repo, spec_path, lock_path, *, gff=None):
    """Write the merged set, its palette and its edge table, and the lock of what was read and written. gff: runs
    nwn_gff with the arguments given (the kit's own without it). Returns {tiles, groups, rules, first}."""
    from .terrain import _gff
    repo, spec_path = Path(repo), Path(spec_path); spec = json.loads(spec_path.read_text(encoding='utf-8')); made = work(repo, spec)
    inputs, outputs = paths(repo, spec); outputs['set'].parent.mkdir(parents=True, exist_ok=True)
    outputs['set'].write_bytes(made['set'].encode('cp1252')); outputs['edge'].write_bytes(made['edge'].encode('cp1252'))
    if made['numbers'] is not None:
        outputs['numbers'].parent.mkdir(parents=True, exist_ok=True); outputs['numbers'].write_text(made['numbers'], encoding='utf-8', newline='\n')
    staged = outputs['palette'].with_suffix('.itp.json'); staged.write_text(json.dumps(made['palette']), encoding='utf-8')
    try:
        (gff or _gff())(['-i', staged, '-o', outputs['palette']])
    finally:
        staged.unlink()
    lock = {'inputs': {**{label: _hash(path) for label, path in inputs.items()}, 'spec': _hash(spec_path)},
            'outputs': {label: _hash(path) for label, path in outputs.items()}}
    Path(lock_path).write_text(json.dumps(lock, indent=1) + '\n', encoding='utf-8', newline='\n')
    return {'tiles': made['set'].count(f'{END}Model='), 'groups': len(made['groups']), 'rules': made['set'].count('[PRIMARY RULE') - 1, 'first': made['first']}


UNSORTED = 'Unsorted'


def refresh(repo, added, *, district=None, gff=None):
    """Merge again every merged set a changed source set belongs to, first giving each new group a display name.
    added: {source set: (the group's name in it, its palette label)}, the group an envkit sheet just put there. The
    name is "<district>: <label>", and "<district>: <label> (<family>)" for the copy of a building an earlier family
    has, which is named and not laid out (`merged_set`); without a district it is filed under Unsorted, for a person
    to sort.
    Returns {merged set: what `merge` returned}."""
    told = {}
    for spec_path, spec, names_path, names in named(repo, added, district=district):
        names_path.write_text(json.dumps(names, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
        told[spec['set']] = merge(repo, spec_path, spec_path.with_name('merged.json'), gff=gff)
    return told


def named(repo, added, *, district=None):
    """[(spec path, spec, names path, the names with each new group's entry)] of every merged set a source set of
    `added` belongs to (`refresh`), nothing written: what a caller checks before it changes a source set, since a
    district that is no category of a names file is refused here."""
    repo = Path(repo); found = []
    for spec_path in sorted((repo / 'docs' / 'tilesets').glob('*/merge.json')):
        spec = json.loads(spec_path.read_text(encoding='utf-8')); labels = {family['set']: family['label'] for family in spec['families']}
        if not set(added) & set(labels):
            continue
        names_path = repo / spec['names']; names = json.loads(names_path.read_text(encoding='utf-8')); known = {(entry['set'], entry['name']) for entry in names['groups']}
        order = list(labels); copy = lambda name: f' ({labels[name].lower()})'
        for at, name in enumerate(order):  # in the families' order: a family's copy is told from one an earlier family has
            if name not in added or (name, added[name][0]) in known:
                continue
            group, label = added[name]; category = district or UNSORTED
            require(category in names['categories'], f'{category} is no category of {names_path.name}')
            earlier = any((other, group) in known for other in order[:at])
            names['groups'].append({'set': name, 'name': group, 'was': label, 'category': category, 'display': f'{category}: {label}' + (copy(name) if earlier else ''), 'envkit': True})
            known.add((name, group))
            for entry in names['groups']:  # a later family had the building alone until now: its group gives way to this one, and its name says so
                if entry['name'] == group and entry['set'] in order[at + 1:] and entry.get('envkit') and not entry['display'].endswith(copy(entry['set'])):
                    entry['display'] += copy(entry['set'])
        found.append((spec_path, spec, names_path, names))
    return found
