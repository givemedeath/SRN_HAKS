"""A building terrain copied under a name of its own, and the palette's names made descriptive.

A copy (plan, stratum 4) is the source terrain's tiles under new model names, each with its walkmesh copied
unchanged and its textures renamed so that the copy can be given a look of its own: the set file gains the terrain,
its tiles (with their doors) and the groups made of them; the edge table gains the source's rows for the new terrain;
the palette gains its entries. Minimap pictures are the source tiles' own. The Toolset shows a terrain by its
palette name, so the descriptive names are written there alone: the set file, the edge table and every area built
with them keep the names they have.

Everything is written into a folder (a review's overlay) for `apply` to move into the packs once it has passed."""
import copy as copying
import datetime
import hashlib
import json
import re
import tempfile
from pathlib import Path

from . import inventory, require
from .apply import MADE_FROM

HEADER = re.compile(r'(?m)^\[([^\]]+)\][ \t]*\r?$')
CORNERS = ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')


def renamed(text, names):
    """`text` with each old name (any case) replaced, also where it begins a longer word: a tile's node names begin
    with its model's name."""
    for old, new in sorted(names.items(), key=lambda pair: -len(pair[0])):
        text = re.sub(r'(?i)(?<![A-Za-z0-9_])' + re.escape(old), new, text)
    return text


def retextured(text, textures):
    """A model's text with the textures and materials its meshes name (bitmap, textureN, materialname) renamed as
    `textures` says."""
    return re.sub(r'(?im)^([ \t]*(?:bitmap|texture\d|materialname)[ \t]+)(\S+)', lambda found: found.group(1) + textures.get(found.group(2).lower(), found.group(2)), text)


def _sections(text):
    """[(name, raw text)] of a set file, the text before the first section as ('', ...)."""
    marks = [(found.start(), found.group(1)) for found in HEADER.finditer(text)]
    parts = [('', text[:marks[0][0]] if marks else text)]
    for index, (start, name) in enumerate(marks):
        parts.append((name, text[start:marks[index + 1][0] if index + 1 < len(marks) else len(text)]))
    return parts


def _counted(raw, count):
    return re.sub(r'(?m)^Count=\d+', f'Count={count}', raw, count=1)


def copied_set(text, copies):
    """The set file with each copy's terrain, tiles and groups appended. copies: [{terrain, from, models: {old: new},
    groups: {old: new}}]. Returns (text, {terrain: {old tile number: new}})."""
    laid = inventory.read_set(text); parts = _sections(text); raw = dict(parts)
    terrains, tiles, groups = len(laid['terrains']), len(laid['tiles']), len(laid['groups'])
    added = {'TERRAIN': [], 'TILE': [], 'GROUP': []}; numbers = {}
    for one in copies:
        source, terrain = one['from'], one['terrain']
        require(source in laid['terrains'], f'The set has no terrain {source}'); require(terrain not in laid['terrains'], f'The set has a terrain {terrain} already')
        index = laid['terrains'].index(source)
        added['TERRAIN'].append(re.sub(r'^\[TERRAIN\d+\]', f'[TERRAIN{terrains}]', re.sub(r'(?m)^Name=.*?(\r?)$', f'Name={terrain}\\1', raw[f'TERRAIN{index}'], count=1)))
        terrains += 1
        mine = [tile for tile in laid['tiles'] if source in tile['corners']]
        missing = sorted({tile['model'] for tile in mine} - {name.lower() for name in one['models']})
        require(not missing, f'{terrain}: the copy names no new model for ' + ', '.join(missing))
        models = {old.lower(): new for old, new in one['models'].items()}; numbers[terrain] = {}
        for tile in mine:
            new = tiles; tiles += 1; numbers[terrain][tile['number']] = new
            body = re.sub(r'(?m)^Model=.*?(\r?)$', f'Model={models[tile["model"]]}\\1', raw[f'TILE{tile["number"]}'], count=1)
            for corner in CORNERS:
                body = re.sub(rf'(?m)^{corner}={re.escape(source)}(\r?)$', f'{corner}={terrain}\\1', body)
            added['TILE'].append(body.replace(f'[TILE{tile["number"]}]', f'[TILE{new}]', 1))
            for name, door in parts:
                if re.fullmatch(rf'TILE{tile["number"]}DOOR\d+', name):
                    added['TILE'].append(door.replace(f'[TILE{tile["number"]}DOOR', f'[TILE{new}DOOR', 1))
        for position, group in enumerate(laid['groups']):
            cells = [number for number in group['tiles'] if number >= 0]  # -1 is a blank cell
            copied = [number for number in cells if number in numbers[terrain]]
            name = one.get('groups', {}).get(group['name'])
            if copied and (len(copied) == len(cells) or name):  # a group of the terrain's tiles, or one the copy names that mixes them with others
                require(name, f'{terrain}: the copy names no new group for {group["name"]}')
                body = re.sub(r'(?m)^Name=.*?(\r?)$', f'Name={name}\\1', raw[f'GROUP{position}'], count=1)
                body = re.sub(r'(?m)^(Tile\d+)=(-?\d+)', lambda found: f'{found.group(1)}={numbers[terrain].get(int(found.group(2)), int(found.group(2)))}', body)
                added['GROUP'].append(body.replace(f'[GROUP{position}]', f'[GROUP{groups}]', 1)); groups += 1
    heads = {'TERRAIN': 'TERRAIN TYPES', 'TILE': 'TILES', 'GROUP': 'GROUPS'}  # where the first of a kind goes when the set has none
    last = {kind: max((index for index, (name, _) in enumerate(parts) if re.fullmatch(rf'{kind}\d+' + (r'(DOOR\d+)?' if kind == 'TILE' else ''), name)),
                      default=next((index for index, (name, _) in enumerate(parts) if name == heads[kind]), len(parts) - 1)) for kind in added if added[kind]}
    out = []
    for index, (name, body) in enumerate(parts):
        body = {'TERRAIN TYPES': lambda: _counted(body, terrains), 'TILES': lambda: _counted(body, tiles), 'GROUPS': lambda: _counted(body, groups)}.get(name, lambda: body)()
        out.append(body)
        for kind, at in last.items():
            if index == at and added[kind]:
                if not out[-1].endswith(('\n\n', '\r\n\r\n')):
                    out[-1] += '\r\n' if '\r\n' in text else '\n'
                out.extend(added[kind])
    return ''.join(out), numbers


def copied_edge(text, copies):
    """The edge table with each source terrain's rows again for its copy, the copied tiles' models renamed."""
    lines = text.split('\n'); end = '\r' if lines and lines[0].endswith('\r') else ''
    rows = [line for line in lines[3:] if line.strip()]; count = len(rows); extra = []
    for one in copies:
        models = {old.lower(): new for old, new in one['models'].items()}
        for line in rows:
            words = line.lower().split()  # the game reads a table's words in any case
            if one['from'].lower() in words[1:]:
                new = re.sub(rf'(?i)(?<!\S){re.escape(one["from"])}(?!\S)', one['terrain'], line)
                new = re.sub(r'(?<!\S)(\S+)(\s*)$', lambda found: models.get(found.group(1).lower(), found.group(1)) + found.group(2), new)
                extra.append(re.sub(r'^\d+', lambda found: str(count).ljust(len(found.group(0))), new)); count += 1
    body = '\n'.join(lines).rstrip('\r\n')
    return body + end + '\n' + ''.join(line.rstrip('\r') + end + '\n' for line in extra)


def _named(name, names):
    name = name.strip()  # a palette name may carry a line break the Toolset does not show
    for old, new in sorted(names.items(), key=lambda pair: -len(pair[0])):
        if name == old:
            return new
        if name.startswith(old + ','):
            return new + name[len(old):]
    return name


def palette(document, copies, names):
    """The palette (nwn_gff JSON) with each copy's entries beside its source's (the terrain's, and those of the
    copied tiles' models) and every name made descriptive by `names` ({old: new}, also where it begins a name)."""
    document = copying.deepcopy(document)
    for category in document['MAIN']['value']:
        entries = category.get('LIST', {}).get('value', []); out = []
        for entry in entries:
            out.append(entry)
            resref = entry.get('RESREF', {}).get('value', '').lower()
            for one in copies:
                models = {old.lower(): new for old, new in one['models'].items()}
                if resref == one['from'].lower() or resref in models:
                    made = copying.deepcopy(entry); made['RESREF']['value'] = one['terrain'].lower() if resref == one['from'].lower() else models[resref]
                    if resref == one['from'].lower():
                        made['NAME'] = {'type': 'cexostring', 'value': one['display']}; made.pop('STRREF', None)
                    else:  # a name of its own, also where the source's was a talk-table reference
                        was = made['NAME']['value'].strip() if isinstance(made.get('NAME', {}).get('value'), str) else ''
                        made['NAME'] = {'type': 'cexostring', 'value': one['display'] + (was[was.find(','):] if ',' in was else '')}; made.pop('STRREF', None)
                    out.append(made)
        for entry in out:
            if 'NAME' in entry and isinstance(entry['NAME'].get('value'), str) and _named(entry['NAME']['value'], names) != entry['NAME']['value'].strip():
                entry['NAME']['value'] = _named(entry['NAME']['value'], names)
        if entries:
            category['LIST']['value'] = out
    return document


def _gff():
    from .review import _tools  # the kit's one tool runner
    run = _tools()
    return lambda arguments: run('nwn_gff', arguments)


def copy(repo, spec, folder, *, gff=None, source='tilekit terrain'):
    """Write each copy of `spec` ({tileset, provenance (its PROVENANCE.md section), names: {old: new}, copies:
    [{terrain, from, display, models, groups, textures: {old: new}}]}) into `folder`: the new models and walkmeshes,
    the set file, the edge table and the palette, and `MADE_FROM`: the hashes of the pack files those three were made
    from and the additions catalog's entries for the new tiles and groups, which `apply` checks and writes. A copied
    walkmesh must be the source's, names apart. Returns {terrain: {tiles, models}, palette names}."""
    repo, folder = Path(repo), Path(folder); tileset = spec['tileset']; own = repo / f'srn_t_{tileset}'; gff = gff or _gff()
    folder.mkdir(parents=True, exist_ok=True); copies = spec.get('copies', []); told = {}
    held = {(pack, path.name.lower()): path for pack in (own, repo / 'srn_t_common') if pack.is_dir() for path in pack.iterdir()}
    require(not copies or spec.get('provenance'), 'A terrain spec names its section of PROVENANCE.md (provenance)')
    writing = {f'{new}{suffix}'.lower() for one in copies for new in one['models'].values() for suffix in ('.mdl', '.wok')}
    stale = sorted(path.name for path in folder.iterdir() if path.suffix.lower() in ('.mdl', '.wok') and path.name.lower() not in writing)
    require(not stale, 'The folder holds models of an earlier run, which apply would install: ' + ', '.join(stale))
    for one in copies:
        require(re.fullmatch(r'[A-Za-z0-9_]{1,16}', one['terrain']), f'{one["terrain"]}: a terrain is named by at most 16 letters, digits and underscores (the palette keeps it as a resref)')
        textures = {old.lower(): new for old, new in one.get('textures', {}).items()}
        for old, new in one['models'].items():
            require(len(new) <= 16 and new == new.lower(), f'{new}: a model is named by a lowercase resref')
            home = next((pack for pack in (own, repo / 'srn_t_common') if (pack, f'{old.lower()}.mdl') in held), None); require(home, f'No pack holds {old}.mdl')
            require(not any((pack, f'{new}.mdl') in held for pack in (own, repo / 'srn_t_common')), f'A pack holds {new}.mdl already')
            data = held[(home, f'{old.lower()}.mdl')].read_bytes(); require(not inventory.compiled(data), f'{old} is compiled: its names cannot be changed here')
            text = data.decode('cp1252'); made = retextured(renamed(text, {old: new}), textures)
            require(inventory.walk_hash(renamed(made, {new: old})) == inventory.walk_hash(text), f'{new}: its walkmesh would differ from {old}\'s')
            (folder / f'{new}.mdl').write_bytes(made.encode('cp1252'))
            wok = held.get((home, f'{old.lower()}.wok'))
            if wok:
                was = wok.read_bytes().decode('cp1252'); moved = renamed(was, {old: new})
                require(renamed(moved, {new: old}).lower() == was.lower(), f'{new}.wok: its walkmesh would differ from {old}\'s')
                (folder / f'{new}.wok').write_bytes(moved.encode('cp1252'))
        told[one['terrain']] = {'models': len(one['models'])}
    made_from = {}; sha = lambda data: hashlib.sha256(data).hexdigest()  # each table hashed as the bytes it was made from, read once
    set_path = own / f'{tileset}.set'; data = set_path.read_bytes(); before = data.decode('cp1252'); text, numbers = copied_set(before, copies)
    (folder / set_path.name).write_bytes(text.encode('cp1252')); made_from[set_path.name] = sha(data)
    for terrain, tiles in numbers.items():
        told[terrain]['tiles'] = sorted(tiles.values())
    edge = repo / 'srn_2da' / f'{tileset}_edge.2da'
    if edge.is_file() and copies:
        data = edge.read_bytes(); (folder / edge.name).write_bytes(copied_edge(data.decode('cp1252'), copies).encode('cp1252')); made_from[edge.name] = sha(data)
    itp = own / f'{tileset}palstd.itp'
    with tempfile.TemporaryDirectory() as work:  # the overlay holds pack files alone
        data = itp.read_bytes(); read = Path(work) / itp.name; read.write_bytes(data); made_from[itp.name] = sha(data)
        document = json.loads(gff(['-i', read, '-k', 'json']))
        made = Path(work) / 'palette.json'; made.write_text(json.dumps(palette(document, copies, spec.get('names', {}))), encoding='utf-8')
        gff(['-i', made, '-o', folder / itp.name])
    (folder / MADE_FROM).write_text(json.dumps({'kind': 'tilekit-terrain-copy', 'from': made_from, 'catalog': catalogued(spec, before, text, numbers, source)}, indent=1) + '\n', encoding='utf-8')
    told['palette names'] = len(spec.get('names', {}))
    return told


def catalogued(spec, before, text, numbers, source):
    """The additions catalog's entries (docs/additions/README.md) for the tiles and groups a copy adds: each terrain's
    tiles under `terrainTiles`, each new group under `tileGroups`."""
    tileset = spec['tileset']; laid = inventory.read_set(text); models = {tile['number']: tile['model'] for tile in laid['tiles']}
    common = {'tileset': tileset, 'pack': f'srn_t_{tileset}', 'madeBy': 'tilekit', 'source': source, 'provenance': spec.get('provenance', ''),
              'added': datetime.date.today().isoformat()}
    terrains = [{**common, 'terrain': terrain, 'tiles': sorted(tiles.values()), 'models': [models[number] for number in sorted(tiles.values())]} for terrain, tiles in numbers.items()]
    first = len(inventory.read_set(before)['groups']); sizes = {name: keys for name, keys in inventory.sections(text) if re.fullmatch(r'GROUP\d+', name)}
    groups = [{**common, 'group': number, 'name': group['name'], 'rows': int(sizes[f'GROUP{number}'].get('Rows', 1)), 'columns': int(sizes[f'GROUP{number}'].get('Columns', 1)),
               'tiles': group['tiles'], 'models': [models.get(tile, '') for tile in group['tiles']]} for number, group in enumerate(laid['groups']) if number >= first]  # a blank cell (-1) has no model
    return {'terrainTiles': terrains, 'tileGroups': groups}
