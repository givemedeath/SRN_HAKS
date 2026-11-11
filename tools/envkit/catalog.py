"""The catalog of what this project has added to shared game data on top of what it imported: rows of the placeables
table, and tiles and groups of the tilesets.

Imports record their rows under docs/imports (`*-global-row-allocations.json`). Nothing recorded what was added
afterwards, by envkit or by hand, and a row or a tile once placed in an area is named by its number for good. The
catalog is that record: one file, `docs/additions/catalog.json`, with the last imported number of each table and set
file (the baseline) and an entry for everything above it. `tools/Test-Repository.ps1` holds the two together, as it
holds the talk table to its allocations: a row or tile above the baseline that the catalog does not list fails
repository verification, and so does a listed one the packs do not have as listed.

envkit's own commands write their entries (`placeables`, `blueprints`, `install`); an addition made by hand gets its
entry by hand (docs/additions/README.md)."""
import json
from pathlib import Path

from . import require

KIND = 'srn-additions-catalog'
PATH = 'docs/additions/catalog.json'
PLACEABLE_KEYS = {'row', 'model', 'label', 'pack', 'madeBy', 'source', 'provenance', 'added'}
GROUP_KEYS = {'tileset', 'group', 'name', 'rows', 'columns', 'tiles', 'models', 'pack', 'madeBy', 'source', 'provenance', 'added'}


def load(path):
    """The catalog, checked for its own shape."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and data.get('kind') == KIND and data.get('schemaVersion') == 1, 'Additions catalog required: ' + str(path))
    require(set(data) == {'schemaVersion', 'kind', 'baseline', 'placeables', 'tileGroups'}, 'The catalog has a baseline, placeables and tile groups')
    table = data['baseline']['placeables']
    require(set(table) == {'table', 'lastImportedRow'} and type(table['lastImportedRow']) is int, 'The placeables baseline names its table and its last imported row')
    for name, tileset in data['baseline']['tilesets'].items():
        require(set(tileset) == {'set', 'importedTiles', 'importedGroups'} and type(tileset['importedTiles']) is int and type(tileset['importedGroups']) is int,
                'A tileset baseline names its set file and counts its imported tiles and groups: ' + name)
    for entry in data['placeables']:
        require(PLACEABLE_KEYS <= set(entry) <= PLACEABLE_KEYS | {'blueprint', 'category'} and type(entry['row']) is int, 'A placeable entry is incomplete: ' + str(entry.get('model')))
    for entry in data['tileGroups']:
        require(set(entry) >= GROUP_KEYS and set(entry) <= GROUP_KEYS | {'label', 'door'} and len(entry['tiles']) == len(entry['models']) == entry['rows'] * entry['columns'],
                'A tile group entry is incomplete: ' + str(entry.get('name')))
    numbers = [entry['row'] for entry in data['placeables']] + [(entry['tileset'], entry['group']) for entry in data['tileGroups']]
    twice = sorted({str(number) for number in numbers if numbers.count(number) > 1})
    require(not twice, 'The catalog has more than one entry for: ' + ', '.join(twice))
    return data


def save(path, data):
    """Write the catalog in a fixed order, so a change to it reads as that change alone."""
    data = {**data, 'placeables': sorted(data['placeables'], key=lambda entry: entry['row']),
            'tileGroups': sorted(data['tileGroups'], key=lambda entry: (entry['tileset'], entry['group']))}
    Path(path).write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8', newline='\n')


def put_placeable(data, entry):
    """Add a placeable's entry, or replace the one at its row. A row keeps the model it was given."""
    there = [old for old in data['placeables'] if old['row'] == entry['row']]
    require(all(old['model'] == entry['model'] for old in there), f'Row {entry["row"]} belongs to {there[0]["model"] if there else ""}')
    data['placeables'] = [old for old in data['placeables'] if old['row'] != entry['row']] + [{**(there[0] if there else {}), **entry}]


def put_group(data, entry):
    """Add a tile group's entry, or replace the one with its number in its tileset. A group keeps its tiles."""
    same = lambda old: (old['tileset'], old['group']) == (entry['tileset'], entry['group'])
    there = [old for old in data['tileGroups'] if same(old)]
    require(all(old['tiles'] == entry['tiles'] and old['name'] == entry['name'] for old in there), f'Group {entry["group"]} of {entry["tileset"]} is {there[0]["name"] if there else ""}')
    data['tileGroups'] = [old for old in data['tileGroups'] if not same(old)] + [{**(there[0] if there else {}), **entry}]
