"""The names the Toolset's door appearance list shows: each genericdoors.2da row's `Name` is a string of the shared TLK
that says the door's category and what it is (`docs/tilesets/doors/names.json`; user, 2026-11-26: "classify and rename
all the doors in the 2da palette appropriately"), so the list sorts doors of a kind together.

`python -B -m tools.tilekit.door_names` allocates a string for each named row (key `door.generic.<row>`, kept when the
row has one: its text follows names.json), and writes the 2da's Name column. The rows of the project's own door set
(`doorset`) keep their strings, `srx01.door.*`, which take the names here. `check` says what is out of step."""
import json
import os
import re
import sys
from pathlib import Path

from . import doorset, inventory, require

REPO = Path(__file__).resolve().parents[2]
NAMES = Path('docs/tilesets/doors/names.json'); TABLE = Path('srn_2da/genericdoors.2da')
ALLOCATIONS, TLK, LOCK = Path('srn_tlk/allocations.json'), Path('srn_tlk/srn.tlk.json'), Path('srn_tlk/.allocation.lock')
CUSTOM = 0x01000000  # a game string reference of the module's own TLK
KEY = 'door.generic.{}'


def owned():
    """{row: string id} of the door set's rows, whose strings are its own."""
    return {row: doorset.NAMES[model] - CUSTOM for row, _, model, *_ in doorset.rows()}


def named_rows(repo=REPO):
    """{row: (its line index, its cells)} of the rows of genericdoors.2da that name a model."""
    lines = (Path(repo) / TABLE).read_text(encoding='cp1252').splitlines(); found = {}
    for index, line in enumerate(lines[3:], 3):
        cells = inventory.words(line)
        if len(cells) > 3 and cells[3] != '****' and cells[1] not in ('****', 'OS_RESERVED'):
            found[int(cells[0])] = (index, cells)
    return found


def check(repo=REPO):
    """[what is wrong]: a named row without a name in names.json or with one of no known category, a name used twice,
    or a row whose Name is not its string, or a string whose text is not its name."""
    spec = json.loads((Path(repo) / NAMES).read_text(encoding='utf-8')); names = spec['rows']; rows = named_rows(repo); wrong = []
    keys = {entry['key']: entry['id'] for entry in json.loads((Path(repo) / ALLOCATIONS).read_text(encoding='utf-8'))['allocations']}
    texts = {entry['id']: entry['text'] for entry in json.loads((Path(repo) / TLK).read_text(encoding='utf-8'))['entries']}
    for row, (_, cells) in sorted(rows.items()):
        name = names.get(str(row))
        if not name or name.split(':', 1)[0] not in spec['categories'] or ': ' not in name:
            wrong.append(f'row {row} ({cells[1]}) has no name "<category>: <door>" in {NAMES}'); continue
        at = owned().get(row, keys.get(KEY.format(row)))
        if at is None or cells[-1] != str(CUSTOM + at) or texts.get(at) != name:
            wrong.append(f'row {row} ({cells[1]}) does not show "{name}"')
    wrong += [f'{NAMES} names row {row}, which names no model' for row in names if int(row) not in rows]
    seen = {}
    for row, name in names.items():
        seen.setdefault(name, []).append(row)
    return wrong + [f'"{name}" names rows {", ".join(rows_)}' for name, rows_ in seen.items() if len(rows_) > 1]


def apply(repo=REPO):
    """Allocate or update each row's string and write the Name column. Returns how many rows changed."""
    repo = Path(repo); spec = json.loads((repo / NAMES).read_text(encoding='utf-8')); rows = named_rows(repo)
    require(not (repo / LOCK).exists(), f'{LOCK} is held: another allocation is running')
    (repo / LOCK).write_text(str(os.getpid()))
    try:
        registry = json.loads((repo / ALLOCATIONS).read_text(encoding='utf-8')); tlk = json.loads((repo / TLK).read_text(encoding='utf-8'))
        keys = {entry['key']: entry['id'] for entry in registry['allocations']}; entries = {entry['id']: entry for entry in tlk['entries']}
        lines = (repo / TABLE).read_text(encoding='cp1252').splitlines(); changed = 0
        for row, (index, cells) in sorted(rows.items()):
            name = spec['rows'].get(str(row)); require(name, f'row {row} ({cells[1]}) has no name in {NAMES}')
            key = KEY.format(row)
            if row in owned():
                keys[key] = owned()[row]; require(keys[key] in entries, f'row {row}: the door set string {keys[key]} is missing')
            elif key not in keys:
                at = registry['nextId']; registry['nextId'] = at + 1; keys[key] = at
                registry['allocations'].append({'id': at, 'key': key, 'owner': 'shared', 'status': 'active'})
                entries[at] = {'id': at, 'text': name}; tlk['entries'].append(entries[at])
            entries[keys[key]]['text'] = name
            wanted = str(CUSTOM + keys[key])
            if cells[-1] != wanted:
                line = lines[index]; found = list(re.finditer(r'\S+', line))[-1]
                lines[index] = line[:found.start()] + wanted.ljust(len(found.group())) + line[found.end():]; changed += 1
        for path, value in ((ALLOCATIONS, registry), (TLK, tlk)):
            (repo / path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
        ending = '\r\n' if b'\r\n' in (repo / TABLE).read_bytes() else '\n'
        (repo / TABLE).write_text(ending.join(lines) + ending, encoding='cp1252', newline='')
        return changed
    finally:
        (repo / LOCK).unlink()


if __name__ == '__main__':
    print(apply(), 'rows renamed'); wrong = check(); print('\n'.join(wrong) or 'all door names in step'); sys.exit(1 if wrong else 0)
