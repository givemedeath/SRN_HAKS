"""Names and blueprints of the imported placeables: rows of the placeables table this project did not make.

An imported row came with its author's label ("Chair_desk", "Dirty ground 6 clear large") and no blueprint, so a builder
found it by its row alone. `docs/placeables/library.json` holds, for each row that has been named, what it is called,
the blueprint a builder paints it with and the palette category it stands in. `envkit library` writes the three places
that say so: the table's label column, a `.utp` in the placeable pack, and the standard palette (with the envkit props'
own, `blueprints`). A row's number and model never change: placed objects name the row.

{schemaVersion, kind, placeables: [{row, model, name, category, blueprint}]}, in the order of the rows."""
import json
import re
from pathlib import Path

from . import placeables, require

KIND = 'srn-placeable-library'
PATH = 'docs/placeables/library.json'
TREE = 'docs/placeables/categories.json'  # the branches of the palette the project made, {branch, categories: [{id, name}]}
KEYS = {'row', 'model', 'name', 'category', 'blueprint'}
PREFIX = '[mdrn]'  # what the imports' labels start with, as envkit's do with theirs
NAME = re.compile(r'[ -!#-~]{1,60}')  # printable, and no quotation mark: a label is quoted in the table


def load(path):
    """The library, checked for its own shape."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and data.get('kind') == KIND and data.get('schemaVersion') == 1, 'Placeable library required: ' + str(path))
    return checked(data['placeables'])


def checked(entries):
    seen = {'row': set(), 'name': set(), 'blueprint': set()}
    for entry in entries:
        require(isinstance(entry, dict) and set(entry) == KEYS and type(entry['row']) is int and type(entry['category']) is int, 'A library entry is incomplete: ' + str(entry.get('model')))
        require(NAME.fullmatch(entry['name']) and entry['name'] == ' '.join(entry['name'].split()), f'Row {entry["row"]} has no plain name: {entry["name"]!r}')
        require(placeables.RESREF.fullmatch(entry['blueprint']), f'Row {entry["row"]}: a blueprint is named by a lowercase resref: {entry["blueprint"]}')
        for key, taken in seen.items():
            value = entry[key].lower() if isinstance(entry[key], str) else entry[key]
            require(value not in taken, f'Two entries of the library have the {key} {entry[key]}'); taken.add(value)
    require([entry['row'] for entry in entries] == sorted(entry['row'] for entry in entries), 'The library is in the order of the rows')
    return entries


def label(entry):
    return PREFIX + entry['name']


def relabelled(text, entries):
    """The placeables table with each entry's row labelled as the library names it. Nothing else of it changes."""
    end = '\r\n' if '\r\n' in text else '\n'; lines = text.rstrip('\r\n').split(end); wanted = {entry['row']: entry for entry in entries}; done = set()
    for index in range(3, len(lines)):
        tokens = placeables.TOKEN.findall(lines[index])
        if not tokens or not tokens[0].isdigit() or int(tokens[0]) not in wanted:
            continue
        entry = wanted[int(tokens[0])]; require(len(tokens) == len(placeables.COLUMNS) + 1, f'Row {tokens[0]} of the placeables table is not a full row')
        require(tokens[3].lower() == entry['model'], f'Row {tokens[0]} is {tokens[3]}, not {entry["model"]}')
        done.add(entry['row'])
        if tokens[1].strip('"') != label(entry):
            spans = [match.start() for match in placeables.TOKEN.finditer(lines[index])]
            lines[index] = placeables._laid(spans, [tokens[0], f'"{label(entry)}"', *tokens[2:]], len(lines[index]))
    require(not set(wanted) - done, 'The placeables table lacks rows ' + ', '.join(map(str, sorted(set(wanted) - done)[:5])))
    return end.join(lines) + end


def listed(entries):
    """The entries as `blueprints.palette` takes them."""
    return [{'resref': entry['blueprint'], 'name': entry['name'], 'category': entry['category']} for entry in entries]


def categories(repo):
    """{id: "branch > name"} of the category tree; no id stands in it twice."""
    data = json.loads((Path(repo) / TREE).read_text(encoding='utf-8')); pairs = [(one['id'], f'{branch["branch"]} > {one["name"]}') for branch in data['branches'] for one in branch['categories']]
    require(len(dict(pairs)) == len(pairs) == len({name for _, name in pairs}), 'A palette category stands twice in ' + TREE); return dict(pairs)


def wrong(repo, entries):
    """[what is not as the library says] in the table, the category tree and the placeable pack."""
    repo = Path(repo); table = {}; known = categories(repo)
    for line in (repo / 'srn_2da' / 'placeables.2da').read_text(encoding='cp1252').splitlines()[3:]:
        tokens = placeables.TOKEN.findall(line)
        if len(tokens) > 3 and tokens[0].isdigit():
            table[int(tokens[0])] = (tokens[1].strip('"'), tokens[3].lower())
    packs = [{path.name.lower() for path in (repo / pack).iterdir()} for pack in ('srn_placeable', 'srn_envprop')]; out = []
    for entry in entries:
        if table.get(entry['row']) != (label(entry), entry['model']):
            out.append(f'row {entry["row"]} of the placeables table is {table.get(entry["row"])}, not {label(entry)}, {entry["model"]}')
        if entry['category'] not in known:
            out.append(f'{entry["name"]} stands in category {entry["category"]}, which the tree lacks')
        if f'{entry["blueprint"]}.utp' not in packs[0] or f'{entry["blueprint"]}.utp' in packs[1]:
            out.append(f'{entry["blueprint"]}.utp is not in the placeable pack alone')
    return out
