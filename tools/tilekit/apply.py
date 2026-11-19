"""A review overlay moved into the packs once its look has passed the user's gate. Each restyled texture of the spec
is its material file and the DDS maps that file names (or, for a plain one, its DDS and the TXI beside it), put in
every pack that held a copy of that name; the old TGA and DDS copies are deleted from every pack. A base-game texture,
which no pack held, goes to the tileset's own pack. A changed tile model replaces the one pack copy it was made from.
A name that ends up in more than one pack is an expected override in hakbuilder.json; one that no longer does is not.
Other files of the packs (a TXI of an old name, a placeable's own texture) are left as they are."""
import json
import re
from pathlib import Path

from . import inventory, require

OLD = ('.tga', '.dds')  # an original's copies, deleted once its restyle is in
HELD = OLD + ('.mtr',)  # what says which packs hold a name: a restyled one may keep its material alone (maps of another stem)


def _configuration(repo):
    return json.loads((repo / 'hakbuilder.json').read_text(encoding='utf-8-sig'))


def files_of(overlay, name):
    """The overlay's files that make up texture `name`: its material and the maps it names, or a plain DDS and TXI."""
    material = overlay / f'{name}.mtr'
    if material.is_file():
        maps = sorted({stem for stem in re.findall(r'(?m)^\s*texture\d\s+(\S+)', material.read_text(encoding='ascii')) if stem.lower() != 'null'})
        found = [material] + [overlay / f'{stem}.dds' for stem in maps]
    else:
        found = [overlay / f'{name}.dds'] + ([overlay / f'{name}.txi'] if (overlay / f'{name}.txi').is_file() else [])
    missing = [path.name for path in found if not path.is_file()]
    require(not missing, f'{name}: the overlay lacks ' + ', '.join(missing))
    return found


def plan(repo, spec, overlay):
    """{'put': [(overlay file, pack)], 'delete': [pack file], 'overrides': {resource: packs}} for a spec's textures and
    the overlay's models; nothing is changed."""
    repo, overlay = Path(repo), Path(overlay); packs = [pack['Name'] for pack in _configuration(repo)['HakList']]
    held = {}
    for pack in packs:
        if (repo / pack).is_dir():
            for path in (repo / pack).iterdir():
                held.setdefault(path.name.lower(), []).append(pack)
    own = f"srn_t_{spec['tileset'].lower()}"; put, delete, placed = [], [], {}
    for name in sorted(spec['textures']):
        holders = sorted({pack for suffix in HELD for pack in held.get(name + suffix, ())}) or [own]
        delete += [repo / pack / (name + suffix) for suffix in OLD for pack in held.get(name + suffix, ())]
        for path in files_of(overlay, name):
            strangers = sorted(set(held.get(path.name, ())) - set(holders))
            require(not strangers, f'{name}: {path.name} is already a file of {", ".join(strangers)}')
            require(path.name not in placed or placed[path.name] == holders, f'{path.name} belongs to two textures')
            placed[path.name] = holders; put += [(path, pack) for pack in holders]
    for path in sorted(overlay.glob('*.mdl')):
        holders = held.get(path.name, [])
        require(len(holders) == 1, f'{path.name}: a changed model replaces the one pack copy it was made from, not {len(holders)}')
        text, was = path.read_bytes().decode('cp1252'), (repo / holders[0] / path.name).read_bytes().decode('cp1252')
        require(inventory.walk_hash(text) == inventory.walk_hash(was), f'{path.name}: its walkmesh differs from the pack copy it replaces')
        put.append((path, holders[0]))
    after = {name: set(holding) for name, holding in held.items()}
    for path in delete:
        after[path.name].discard(path.parent.name)
    for path, pack in put:
        after.setdefault(path.name, set()).add(pack)
    touched = {path.name for path in delete} | {path.name for path, _ in put}
    overrides = {name: sorted(after[name]) for name in sorted(touched) if len(after.get(name, ())) > 1}
    return {'put': put, 'delete': sorted(set(delete) - {repo / pack / path.name for path, pack in put}), 'overrides': overrides, 'touched': touched}


def apply(repo, spec, overlay):
    """Carry out `plan`, rewrite hakbuilder.json's expected overrides for the names touched, and tell the counts."""
    repo = Path(repo); moves = plan(repo, spec, overlay)
    for path in moves['delete']:
        path.unlink()
    for path, pack in moves['put']:
        (repo / pack / path.name).write_bytes(path.read_bytes())
    configuration = _configuration(repo); before = configuration['ExpectedOverrides']
    kept = [entry for entry in before if entry['Resource'].lower() not in moves['touched']]  # in their order; new ones after
    added = [{'Resource': name, 'Packs': packs} for name, packs in moves['overrides'].items()]
    configuration['ExpectedOverrides'] = kept + added
    (repo / 'hakbuilder.json').write_text(json.dumps(configuration, indent=2) + '\n', encoding='utf-8', newline='\n')
    return {'put': len(moves['put']), 'deleted': len(moves['delete']), 'overrides': len(added), 'overrides before': len(before) - len(kept)}
