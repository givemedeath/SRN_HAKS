"""What a tileset draws: its tile and edge models, the textures on their rendered faces by surface, every copy of
each texture in every pack, who else names it, and the hashes its walkmeshes must keep.

A restyle replaces textures in place, so three things have to be known before any is touched: how much of what a
player sees each texture covers (the order of work), where every copy of its name lies (a copy left behind is shown
instead, or beside, the new one), and which other tilesets, doors and placeables name it (they change with it). The
models are read as the game reads them: the set file names the tiles, the edge table names the edge tiles the set does
not, and only uncompiled models are measured (a compiled one is counted and left alone). Surface is the area of the
faces of rendered mesh nodes, in square metres, each model counted once however often it is painted."""
import csv
import hashlib
import io
import json
import re
import struct
from pathlib import Path

from . import require

MESHES = {'trimesh', 'danglymesh', 'animmesh', 'skin'}  # node kinds whose faces are drawn; an aabb node is the walkmesh
MARKS = (50, 80, 90, 95, 99)
PICTURES = ('tga', 'dds', 'plt', 'mtr')


def sections(text):
    """[(name, {key: value})] of a set file, in its order. A key said twice in a section keeps its last value."""
    found = []
    for line in text.replace('\r', '').split('\n'):
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            found.append((line[1:-1], {}))
        elif '=' in line and found:
            key, _, value = line.partition('=')
            found[-1][1][key.strip()] = value.strip()
    return found


def read_set(text):
    """A set file as {default, terrains, crossers, tiles: [{number, model, corners, heights, crossers, doors}], groups:
    [{name, tiles}]}. Corners and their heights are top left, top right, bottom left, bottom right; crossers top,
    right, bottom, left."""
    told = {'default': '', 'terrains': [], 'crossers': [], 'tiles': [], 'groups': []}
    for name, keys in sections(text):
        if name == 'GENERAL':
            told['default'] = keys.get('Default', '')
        elif re.fullmatch(r'TERRAIN\d+', name):
            told['terrains'].append(keys.get('Name', ''))
        elif re.fullmatch(r'CROSSER\d+', name):
            told['crossers'].append(keys.get('Name', ''))
        elif re.fullmatch(r'TILE\d+', name):
            told['tiles'].append({'number': int(name[4:]), 'model': keys.get('Model', '').lower(),
                                  'corners': [keys.get(key, '') for key in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')],
                                  'heights': [int(keys.get(key + 'Height', '0') or 0) for key in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')],
                                  'crossers': [keys.get(key, '') for key in ('Top', 'Right', 'Bottom', 'Left')],
                                  'doors': int(keys.get('Doors', '0') or 0)})
        elif re.fullmatch(r'GROUP\d+', name):
            told['groups'].append({'name': keys.get('Name', ''),
                                   'tiles': [int(value) for key, value in keys.items() if re.fullmatch(r'Tile\d+', key) and value.lstrip('-').isdigit()]})
    require(told['tiles'], 'The set file names no tile')
    return told


WORD = re.compile(r'"[^"]*"|\S+')  # a 2DA cell: a quoted one holds its spaces ("Rock Wall")


def words(line):
    """The cells of a 2DA row as the game reads them: a quoted cell is one, spaces and all, without its quotes."""
    return [cell[1:-1] if len(cell) > 1 and cell[0] == cell[-1] == '"' else cell for cell in WORD.findall(line)]


def edge_models(text):
    """The models an edge table names, lower case, with its row count: (models, rows)."""
    lines = [words(line) for line in text.replace('\r', '').split('\n') if line.strip() and not line.lstrip().upper().startswith('DEFAULT:')]
    require(len(lines) >= 2 and lines[0][0].upper() == '2DA', 'An edge table is a 2DA file')  # the game reads its words in any case
    heads = [word.lower() for word in lines[1]]; column = heads.index('model') + 1 if 'model' in heads else None
    require(column is not None, 'The edge table has no Model column')
    rows = [line for line in lines[2:] if len(line) > column]
    return sorted({line[column].lower() for line in rows if line[column] != '****'}), len(rows)


def drawn_models(repo, tileset):
    """The models a tileset draws: its set's tiles and the edge tiles its edge table (srn_2da/<tileset>_edge.2da) lays
    round an area's border, lowercase."""
    repo = Path(repo); models = {tile['model'] for tile in read_set((repo / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252'))['tiles']}
    edge = repo / 'srn_2da' / f'{tileset}_edge.2da'
    return models | (set(edge_models(edge.read_bytes().decode('cp1252'))[0]) if edge.is_file() else set())


def compiled(data):
    """Whether a model's bytes are a compiled model: those begin with four zero bytes, an uncompiled one with text."""
    return data[:4] == b'\0\0\0\0'


def _nodes(text):
    """[(kind, name, lines)] of the geometry of an uncompiled model: every node before the first animation."""
    found, lines = [], None
    for line in text.replace('\r', '').split('\n'):
        words = line.split()
        if not words:
            continue
        if words[0] == 'newanim':
            break
        if words[0] == 'node' and len(words) >= 3:
            lines = []; found.append((words[1].lower(), words[2], lines))
        elif words[0] == 'endnode':
            lines = None
        elif lines is not None:
            lines.append(words)
    return found


def surfaces(text):
    """{texture: square metres} of an uncompiled model's rendered faces. A node that is not rendered, has no texture
    or is the walkmesh counts for nothing."""
    told = {}
    for kind, _, lines in _nodes(text):
        texture, rendered, points, area, index = None, True, [], 0.0, 0
        while index < len(lines):
            words = lines[index]; index += 1
            if words[0] in ('bitmap', 'texture0') and len(words) > 1:
                texture = words[1].lower()
            elif words[0] == 'render' and len(words) > 1:
                rendered = words[1] != '0'
            elif words[0] == 'verts' and len(words) > 1:
                count = int(words[1]); points = [tuple(float(value) for value in row[:3]) for row in lines[index:index + count]]; index += count
            elif words[0] == 'faces' and len(words) > 1:
                count = int(words[1])
                for row in lines[index:index + count]:
                    a, b, c = (int(value) for value in row[:3])
                    if max(a, b, c) < len(points):
                        ux, uy, uz = (points[b][axis] - points[a][axis] for axis in range(3))
                        vx, vy, vz = (points[c][axis] - points[a][axis] for axis in range(3))
                        area += 0.5 * ((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + (ux * vy - uy * vx) ** 2) ** 0.5
                index += count
        if kind in MESHES and rendered and texture not in (None, 'null') and area > 0:
            told[texture] = told.get(texture, 0.0) + area
    return told


def walk_hash(text):
    """SHA-256 of an uncompiled model's walkmesh nodes, whitespace apart, or None where it has none. Holding this
    still is how a restyle shows it changed no walkmesh inside a model."""
    nodes = [(name, lines) for kind, name, lines in _nodes(text) if kind == 'aabb']
    if not nodes:
        return None
    said = '\n'.join(name.lower() + '\n' + '\n'.join(' '.join(words) for words in lines) for name, lines in nodes)
    return hashlib.sha256(said.encode('utf-8')).hexdigest()


def picture_size(path):
    """(width, height) of a TGA, a standard DDS or a BioWare DDS, from its header; None for anything else."""
    path = Path(path); kind = path.suffix.lower()
    with path.open('rb') as file:
        head = file.read(20)
    if kind == '.tga' and len(head) >= 18:
        return struct.unpack_from('<HH', head, 12)
    if kind == '.dds' and len(head) >= 20:
        if head[:4] == b'DDS ':
            height, width = struct.unpack_from('<II', head, 12)
            return width, height
        return struct.unpack_from('<II', head, 0)
    return None


def _packs(repo):
    return sorted(path for path in Path(repo).iterdir() if path.is_dir() and path.name.startswith('srn_'))


def _other_sets(repo, tileset, *, edges=False):
    """{model: [tileset]} for the tiles of every other tileset in the repository, and with `edges` the models their
    edge tables lay round an area's border."""
    told = {}
    for pack in _packs(repo):
        for path in sorted(pack.glob('*.set')):
            if path.stem.lower() != tileset:
                for tile in read_set(path.read_bytes().decode('cp1252'))['tiles']:
                    told.setdefault(tile['model'], set()).add(path.stem.lower())
    for path in sorted((Path(repo) / 'srn_2da').glob('*_edge.2da')) if edges else ():
        other = path.stem.lower()[:-len('_edge')]
        if other != tileset:
            for model in edge_models(path.read_bytes().decode('cp1252'))[0]:
                told.setdefault(model, set()).add(other)
    return told


def drawn_copies(repo, tileset, folder, packs):
    """(name, file name, text, other tilesets using it, pack file) for each uncompiled model the tileset draws, in the
    first of `packs` that holds it (the copy the game shows), read from `folder` where a copy is already there."""
    tiles, others, seen = drawn_models(repo, tileset), _other_sets(repo, tileset, edges=True), set()
    for pack in packs:
        for path in sorted((Path(repo) / pack.format(tileset=tileset)).glob('*.mdl')):
            name = path.stem.lower()
            if name not in tiles or name in seen:
                continue
            seen.add(name); data = (Path(folder) / path.name if (Path(folder) / path.name).is_file() else path).read_bytes()
            if not compiled(data):
                yield name, path.name, data.decode('cp1252'), sorted(others.get(name, ())), path


def inventory(repo, tileset, *, walkmesh_only=False):
    """The inventory document of a tileset and its walkmesh baseline: (inventory, walkmesh). With `walkmesh_only` the
    other packs are not read and the inventory is None: the tileset's own models are all a walkmesh check needs."""
    repo = Path(repo); own = repo / f'srn_t_{tileset}'; homes = [own, repo / 'srn_t_common']
    require((own / f'{tileset}.set').is_file(), f'No set file for {tileset} in {own.name}')
    laid = read_set((own / f'{tileset}.set').read_bytes().decode('cp1252'))
    edge_path = repo / 'srn_2da' / f'{tileset}_edge.2da'
    edges, edge_rows = edge_models(edge_path.read_bytes().decode('cp1252')) if edge_path.is_file() else ([], 0)
    tiles_of, terrains_of = {}, {}
    for tile in laid['tiles']:
        tiles_of.setdefault(tile['model'], []).append(tile['number'])
        terrains_of.setdefault(tile['model'], set()).update(set(tile['corners']) - {laid['default'], ''} or {laid['default']})
    scope = sorted(set(tiles_of) | set(edges))

    held = {(pack.name, path.name.lower()): path for pack in homes if pack.is_dir() for path in pack.iterdir()}  # a file in any case, as the game finds it
    models, surface, users, terrains, walkmesh = {}, {}, {}, {}, {}
    for name in scope:
        home = next((pack for pack in homes if (pack.name, f'{name}.mdl') in held), None)
        entry = {'pack': home.name if home else None, 'form': 'absent', 'tiles': tiles_of.get(name, []), 'edge': name in edges}
        if home:
            data = held[(home.name, f'{name}.mdl')].read_bytes(); entry['form'] = 'compiled' if compiled(data) else 'uncompiled'
            wok = held.get((home.name, f'{name}.wok'))
            marks = {'wok': hashlib.sha256(wok.read_bytes()).hexdigest() if wok else None, 'aabb': None}
            if entry['form'] == 'uncompiled':
                text = data.decode('cp1252'); marks['aabb'] = walk_hash(text)
                for texture, area in ({} if walkmesh_only else surfaces(text)).items():
                    surface[texture] = surface.get(texture, 0.0) + area; users.setdefault(texture, []).append(name)
                    terrains.setdefault(texture, set()).update(terrains_of.get(name, ()))
            walkmesh[name] = marks  # a compiled model's walkmesh is its .wok
        models[name] = entry
    marked = {'schemaVersion': 1, 'tileset': tileset, 'models': dict(sorted(walkmesh.items()))}
    if walkmesh_only:
        return None, marked

    # Every copy of each name in every pack, and every model outside this tileset's own that names it.
    packs = _packs(repo); copies = {name: [] for name in surface}
    for pack in packs:
        for kind in PICTURES:
            for path in pack.glob(f'*.{kind}'):
                if path.stem.lower() in copies:
                    size = picture_size(path)
                    copies[path.stem.lower()].append({'pack': pack.name, 'type': kind, **({'width': int(size[0]), 'height': int(size[1])} if size else {})})
    other_sets = _other_sets(repo, tileset); named_by_sets, named_by_packs = {}, {}
    # A name is a whole word of a model's bytes, compiled or not: one pass for words, then a look in the set of names.
    words = re.compile(rb'[a-z0-9_]+'); wanted = {name.encode('ascii', 'ignore') for name in surface}
    for pack in packs:
        for path in sorted(pack.glob('*.mdl')):
            model = path.stem.lower()
            if model in models or not wanted:
                continue
            for texture in {word.decode('ascii') for word in set(words.findall(path.read_bytes().lower())) & wanted}:
                for other in other_sets.get(model, ()):
                    named_by_sets.setdefault(texture, set()).add(other)
                if model not in other_sets:
                    counts = named_by_packs.setdefault(texture, {}); counts[pack.name] = counts.get(pack.name, 0) + 1

    total = sum(surface.values()); running, marks, textures = 0.0, {}, []
    for count, name in enumerate(sorted(surface, key=lambda name: (-surface[name], name)), 1):
        running += surface[name]
        for mark in MARKS:
            if mark not in marks and total and running / total * 100 >= mark:
                marks[mark] = count
        sizes = [max(copy['width'], copy['height']) for copy in copies[name] if 'width' in copy]
        textures.append({'name': name, 'surface': round(surface[name], 2), 'share': round(surface[name] / total * 100, 3) if total else 0.0,
                         'cumulative': round(running / total * 100, 3) if total else 0.0, 'models': len(users[name]), 'terrains': sorted(terrains[name]),
                         'largest': max(sizes) if sizes else None, 'copies': sorted(copies[name], key=lambda copy: (copy['pack'], copy['type'])),
                         'otherSets': sorted(named_by_sets.get(name, ())), 'otherPacks': dict(sorted(named_by_packs.get(name, {}).items()))})
    unnamed = sorted(path.stem.lower() for path in own.glob('*.mdl') if path.stem.lower() not in models and path.stem.lower() not in other_sets)
    told = {'schemaVersion': 1, 'tileset': tileset,
            'set': {'terrains': len(laid['terrains']), 'crossers': len(laid['crossers']), 'tiles': len(laid['tiles']), 'models': len(tiles_of),
                    'groups': len(laid['groups'])},
            'edge': {'rows': edge_rows, 'models': len(edges), 'notInSet': len(set(edges) - set(tiles_of))},
            'forms': {form: sum(1 for entry in models.values() if entry['form'] == form) for form in ('uncompiled', 'compiled', 'absent')},
            'surface': round(total, 2), 'coverage': {str(mark): marks.get(mark) for mark in MARKS}, 'textures': textures,
            'models': models, 'unnamedModels': unnamed}
    return told, marked


def table(told):
    """The textures of an inventory as CSV text, largest surface first."""
    out = io.StringIO(); rows = csv.writer(out, lineterminator='\n')
    rows.writerow(['texture', 'surface_m2', 'share_pct', 'cumulative_pct', 'models', 'largest_px', 'copies', 'other_sets', 'other_packs', 'terrains'])
    for one in told['textures']:
        rows.writerow([one['name'], one['surface'], one['share'], one['cumulative'], one['models'], one['largest'] or '',
                       ' '.join(f"{copy['pack']}:{copy['type']}" + (f":{copy['width']}x{copy['height']}" if 'width' in copy else '') for copy in one['copies']),
                       ' '.join(one['otherSets']), ' '.join(f'{pack}:{count}' for pack, count in one['otherPacks'].items()), ' '.join(one['terrains'])])
    return out.getvalue()


def moved(baseline, now):
    """What differs between two walkmesh documents, as lines; empty when every walkmesh stands as it stood. A model
    the baseline lacks is new and is not a difference: new tiles bring their own walkmeshes."""
    lines = []
    for name, marks in baseline['models'].items():
        seen = now['models'].get(name)
        if seen is None:
            lines.append(f'{name}: gone')
            continue
        lines.extend(f'{name}: {key} changed' for key in ('wok', 'aabb') if marks.get(key) != seen.get(key))
    return lines


def write(folder, told, walkmesh):
    """Write inventory.json, textures.csv and walkmesh.json into `folder`."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    for name, text in (('inventory.json', json.dumps(told, indent=2) + '\n'), ('textures.csv', table(told)),
                       ('walkmesh.json', json.dumps(walkmesh, indent=2) + '\n')):
        (folder / name).write_text(text, encoding='utf-8', newline='\n')
    return [str(folder / name) for name in ('inventory.json', 'textures.csv', 'walkmesh.json')]
