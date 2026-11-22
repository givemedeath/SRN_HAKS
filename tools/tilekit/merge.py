"""One tileset made of several: every tile, group and rule of the source sets under one set file, with the names a
names file gives them.

A builder paints one area with tiles of all the source sets. The tile models stay in the source sets' packs; the
merged pack holds the set file, its palette and (later) the join tiles, and the edge table goes beside the others.
A merge is worked out whole from the source set files, their edge tables, the names file and a spec, so a second run
writes the same bytes: nothing else writes the merged files. `lock` pins what a merge read and wrote, and `stale`
says what has changed since, so a source set changed later (an envkit sheet's new tiles, say) is seen and merged again.

spec: {set (the merged set's resref), display, names (the names file), families: [{set, label}] in the order their
tiles are numbered, general (the family whose GENERAL section is kept), grass (the family whose [GRASS] is kept),
joins: [[terrain key, terrain key]] the ground pairs join tiles are built for, raised: [terrain key] grounds with
raised tiles}.

names: {terrains, crossers: [{set, name, key, display, palette (false leaves it off the palette)}], folds: [{set,
name, into (a terrain key, or null for a name no tile uses)}], edgeNames: [{set, name, into}] spellings only an edge
table has, groups: [{set, name, display}]}."""
import hashlib
import json
import re
from collections import deque
from pathlib import Path

from . import inventory, joins, require
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


def merged_set(sets, names, spec, joined=()):
    """(the merged set file's text, {family: the number its first tile takes}, [{set, name (in the merged set), was,
    display, tiles, model (its first tile's)}] of its groups) from the source set files' texts ({set: text}).
    joined: the join tiles (`joins.tiles`), numbered after the families' own."""
    terrains, crossers = maps(names); order = [family['set'] for family in spec['families']]
    require(set(order) <= set(sets), 'The spec names a set that was not given'); require(spec['general'] in order and spec['grass'] in order, 'general and grass name a family')
    read = {name: inventory.sections(sets[name]) for name in order}; laid = {name: inventory.read_set(sets[name]) for name in order}
    first, count = {}, 0
    for name in order:
        first[name] = count; count += len(laid[name]['tiles'])
        require([tile['number'] for tile in laid[name]['tiles']] == list(range(len(laid[name]['tiles']))), f'{name}: its tiles are not numbered from 0 in order')
    # tiles, each family's after the one before
    tiles = []
    for name in order:
        for section, raw in _sections(sets[name]):
            found = re.fullmatch(r'TILE(\d+)(DOOR\d+)?', section)
            if found:
                tiles.append(_crlf(_tile(raw, first[name] + int(found.group(1)), terrains.get(name, {}), crossers.get(name, {}), f'{name} tile {found.group(1)}')).rstrip(END) + END)
    for record in joined:  # flat, open ground with no light, door or sound of its own
        keys = {'Model': record['model'], 'WalkMesh': 'msb01'}
        for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'):
            keys[corner] = record['corners'][corner]; keys[corner + 'Height'] = 0
        keys.update({side: record['crossers'][side] for side in ('Top', 'Right', 'Bottom', 'Left')})
        keys.update(dict.fromkeys(('MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1', 'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds'), 0))
        keys.update({'PathNode': 'A', 'Orientation': 0, 'ImageMap2D': record['minimap']})
        tiles.append(f'[TILE{count}]{END}' + ''.join(f'{key}={value}{END}' for key, value in keys.items())); count += 1
    # groups
    shown = {(entry['set'], entry['name']): entry['display'] for entry in names['groups']}; groups, taken, begun = [], set(), set()
    for name in order:
        label = next(family['label'] for family in spec['families'] if family['set'] == name); models = {tile['number']: tile['model'] for tile in laid[name]['tiles']}
        for section, raw in _sections(sets[name]):
            if not re.fullmatch(r'GROUP\d+', section):
                continue
            keys = dict(line.split('=', 1) for line in _lines(raw) if '=' in line); was = keys['Name']
            require((name, was) in shown, f'{name}: no display name for group {was}')
            members = [int(keys[f'Tile{index}']) for index in range(int(keys['Rows']) * int(keys['Columns']))]
            require(all(member in models for member in members), f'{name} group {was} names a tile the set lacks')
            if models[members[0]].lower() in begun:  # the Toolset finds a group by its first tile's model, so a second one with that model lays the first
                continue  # (seen 2026-11-21: an envkit building's suburb copy laid its city copy); its tiles stay, its group is left out
            begun.add(models[members[0]].lower())
            called = was if was.lower() not in taken else f'{was}_{label}'  # an envkit building stands in two families under one name
            require(called.lower() not in taken, f'Two groups are named {called}'); taken.add(called.lower())
            raw = re.sub(r'^\[GROUP\d+', f'[GROUP{len(groups)}', raw, count=1)
            raw = re.sub(r'(?m)^Name=[^\r\n]*', lambda _: f'Name={called}', raw, count=1)
            raw = MEMBER.sub(lambda found: f'{found.group(1)}={first[name] + int(found.group(2))}', raw)
            groups.append({'set': name, 'name': called, 'was': was, 'display': shown[(name, was)], 'tiles': [first[name] + member for member in members],
                           'model': models[members[0]], 'raw': _crlf(raw).rstrip(END) + END})
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
    for key in ('Border', 'Default', 'Floor'):
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
    out += [tile + END for tile in tiles]
    out.append(block('GROUPS', {'Count': len(groups)}))
    out += [group.pop('raw') + END for group in groups]
    return ''.join(out), first, groups


def merged_edge(edges, names, spec, joined=()):
    """The merged edge table's text from the source sets' ({set: text}): every row of each, in the families' order,
    under the new names; then the border rows of the join pairs (`joins.edges`)."""
    terrains, crossers = maps(names); rows = []
    terrains = {name: dict(found) for name, found in terrains.items()}; crossers = {name: dict(found) for name, found in crossers.items()}
    for other in names.get('edgeNames', ()):  # a name only an edge table spells: its rows never matched the source set, and do here
        kind = terrains if other['into'] in {entry['key'] for entry in names['terrains']} else crossers
        require(other['into'] in {entry['key'] for entry in names['terrains'] + names['crossers']}, f'{other["name"]} is spelled for no key')
        kind.setdefault(other['set'], {})[other['name'].lower()] = other['into']
    for name in (family['set'] for family in spec['families']):
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
    wide = [max(len(row[index]) for row in rows) + 2 for index in range(5)]; head = ('Corner1', 'Edge', 'Corner2', 'Height', 'Model'); number = len(str(len(rows))) + 2
    lines = ['2DA V2.0', '', ' ' * number + ''.join(cell.ljust(max(width, len(cell) + 2)) for cell, width in zip(head, wide)).rstrip()]
    lines += [str(index).ljust(number) + ''.join(cell.ljust(max(width, len(head[at]) + 2)) for at, (cell, width) in enumerate(zip(row, wide))).rstrip() for index, row in enumerate(rows)]
    return END.join(lines) + END


def palette(names, groups):
    """The merged set's palette as nwn_gff's JSON: single tiles under Features, groups of several under Groups, the
    terrains and crossers under Terrain with the eraser and the raise tool, each list in the order of its names."""
    entry = lambda shown, resref: {'__struct_id': 0, 'NAME': {'type': 'cexostring', 'value': shown}, 'RESREF': {'type': 'resref', 'value': resref}}
    tool = lambda resref, name: {'__struct_id': 0, 'RESREF': {'type': 'resref', 'value': resref}, 'STRREF': {'type': 'dword', 'value': name}}
    node = lambda which, listed: {'__struct_id': 0, 'ID': {'type': 'byte', 'value': which[0]}, 'LIST': {'type': 'list', 'value': listed}, 'STRREF': {'type': 'dword', 'value': which[1]}}
    ordered = lambda found: [entry(shown, resref) for shown, resref in sorted(found, key=lambda pair: (pair[0].lower(), pair[1]))]
    single = [(group['display'], group['model']) for group in groups if len(group['tiles']) == 1]
    several = [(group['display'], group['model']) for group in groups if len(group['tiles']) > 1]
    painted = [(one['display'], one['key'].lower()) for one in names['terrains'] + names['crossers'] if one.get('palette', True)]
    return {'__data_type': 'ITP ', 'MAIN': {'type': 'list', 'value': [node(FEATURES, ordered(single)), node(GROUPS, ordered(several)),
                                                                     node(TERRAIN, [tool(*ERASER), tool(*RAISE)] + ordered(painted))]}}


def paths(repo, spec):
    """(inputs {label: path}, outputs {label: path}) of a merge in a repository."""
    repo = Path(repo); name = spec['set']; pack = repo / f'srn_t_{name}'
    inputs = {'names': repo / spec['names']}
    for family in spec['families']:
        inputs[f'set:{family["set"]}'] = repo / f'srn_t_{family["set"]}' / f'{family["set"]}.set'
        inputs[f'edge:{family["set"]}'] = repo / 'srn_2da' / f'{family["set"]}_edge.2da'
    if spec.get('joinTiles'):
        inputs['joins'] = repo / spec['joinTiles']
    return inputs, {'set': pack / f'{name}.set', 'palette': pack / f'{name}palstd.itp', 'edge': repo / 'srn_2da' / f'{name}_edge.2da'}


def work(repo, spec):
    """What a merge writes, worked out and not written: {set, edge: text, palette: JSON, first, groups}."""
    inputs, _ = paths(repo, spec); names = json.loads(inputs['names'].read_text(encoding='utf-8'))
    order = [family['set'] for family in spec['families']]; cut = json.loads(inputs['joins'].read_text(encoding='utf-8')) if 'joins' in inputs else None
    text, first, groups = merged_set({name: inputs[f'set:{name}'].read_bytes().decode('cp1252') for name in order}, names, spec, joins.tiles(cut) if cut else ())
    edge = merged_edge({name: inputs[f'edge:{name}'].read_bytes().decode('cp1252') for name in order}, names, spec, joins.edges(cut) if cut else ())
    return {'set': text, 'edge': edge, 'palette': palette(names, groups), 'first': first, 'groups': groups}


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stale(repo, spec, spec_path, lock_path):
    """What has changed since the merge the lock records: the labels of the inputs and outputs whose bytes differ,
    'spec' for the spec itself, ['lock'] when there is no lock."""
    if not Path(lock_path).is_file():
        return ['lock']
    lock = json.loads(Path(lock_path).read_text(encoding='utf-8')); inputs, outputs = paths(repo, spec)
    now = {**{label: _hash(path) if path.is_file() else None for label, path in {**inputs, **outputs}.items()}, 'spec': _hash(spec_path)}
    return sorted(label for label in now if now[label] != {**lock['inputs'], **lock['outputs']}.get(label))


def merge(repo, spec_path, lock_path, *, gff=None):
    """Write the merged set, its palette and its edge table, and the lock of what was read and written. gff: runs
    nwn_gff with the arguments given (the kit's own without it). Returns {tiles, groups, rules, first}."""
    from .terrain import _gff
    repo, spec_path = Path(repo), Path(spec_path); spec = json.loads(spec_path.read_text(encoding='utf-8')); made = work(repo, spec)
    inputs, outputs = paths(repo, spec); outputs['set'].parent.mkdir(parents=True, exist_ok=True)
    outputs['set'].write_bytes(made['set'].encode('cp1252')); outputs['edge'].write_bytes(made['edge'].encode('cp1252'))
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
    name is "<district>: <label>" in the first family and "<district>: <label> (<family>)" in a later one, whose copy
    of a building the first family has is named and not laid out (`merged_set`); without a district it is filed under
    Unsorted, for a person to sort.
    Returns {merged set: what `merge` returned}."""
    repo = Path(repo); told = {}
    for spec_path in sorted((repo / 'docs' / 'tilesets').glob('*/merge.json')):
        spec = json.loads(spec_path.read_text(encoding='utf-8')); labels = {family['set']: family['label'] for family in spec['families']}
        if not set(added) & set(labels):
            continue
        names_path = repo / spec['names']; names = json.loads(names_path.read_text(encoding='utf-8')); known = {(entry['set'], entry['name']) for entry in names['groups']}
        for name, (group, label) in sorted(added.items()):
            if name in labels and (name, group) not in known:
                category = district or UNSORTED
                require(category in names['categories'], f'{category} is no category of {names_path.name}')
                names['groups'].append({'set': name, 'name': group, 'was': label, 'category': category, 'display': f'{category}: {label}' + ('' if name == spec['families'][0]['set'] else f' ({labels[name].lower()})'), 'envkit': True})
        names_path.write_text(json.dumps(names, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
        told[spec['set']] = merge(repo, spec_path, spec_path.with_name('merged.json'), gff=gff)
    return told
