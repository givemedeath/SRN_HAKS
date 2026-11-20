"""A review overlay moved into the packs once its look has passed the user's gate. Each restyled texture of the spec
is its material file and the DDS maps that file names (or, for a plain one, its DDS and the TXI beside it), put in
every pack that held a copy of that name; the old TGA and DDS copies are deleted from every pack. A base-game texture,
which no pack held, goes to the tileset's own pack. A changed tile model replaces the one pack copy it was made from.
A name that ends up in more than one pack is an expected override in hakbuilder.json; one that no longer does is not.
A tileset's set file, edge table and palette replace their pack copies only with the record of the copy that made
them (`MADE_FROM`, a copied terrain's), only over the very pack file they were made from, and a set file or table only
when it keeps every entry of the pack copy (`_extends`); that record's additions catalog entries are written, checked and dated the day of the apply. A new tile
model and walkmesh (or a new edge tile the record names, with a walkmesh only where its source had one) come only with such a record (a copied
terrain's, `terrain`) and go to the tileset's own pack, and the textures the record says
they were renamed to must be in a pack or come with the same apply. A walkmesh a pack holds is replaced only as the
overlay's `cuts.WALK_CUTS` says (a blocking piece's footprint cut out of a roof, `detail`), over the very walkmesh it
was cut from, and the tileset's walkmesh baseline then records the cut one. Other files of the packs (a TXI of an old name, a placeable's own texture) are left as they are."""
import datetime
import hashlib
import json
import re
from pathlib import Path

from . import inventory, require
from .cuts import WALK_CUTS

OLD = ('.tga', '.dds')  # an original's copies, deleted once its restyle is in
HELD = OLD + ('.mtr',)  # what says which packs hold a name: a restyled one may keep its material alone (maps of another stem)
MODELS = ('.mdl', '.wok')  # a tile's model and walkmesh: a changed one replaces its pack copy, a new one goes to the tileset's pack
TABLES = ('.set', '.2da', '.itp')  # a tileset's set file, edge table and palette: each replaces its one pack copy
MADE_FROM = 'made-from.json'  # a copied terrain's record (terrain.copy): the pack files its tables were made from, and its catalog entries
KIT_FILES = 'kit-files.json'  # {kind, tileset, files: {name: sha256}}: the kit's atlas and effect pictures `detail` copied in, new to the packs
MODELS_FROM = 'models-from.json'  # {model file: hash of the pack copy it was changed from}, written by lamps and shadows (`noted`)


def noted(folder, file, source):
    """Record in the overlay `folder` the pack copy (`source`) its changed model `file` was first made from: apply
    then refuses it over a pack copy changed since, which it would otherwise undo."""
    path = Path(folder) / MODELS_FROM; held = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    if file.lower() not in held:  # a copy changed again (shadows after lamps) was still made from the first
        held[file.lower()] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        path.write_text(json.dumps(dict(sorted(held.items())), indent=1) + '\n', encoding='utf-8')


def _configuration(repo):
    return json.loads((repo / 'hakbuilder.json').read_text(encoding='utf-8-sig'))


def _extends(suffix, was, made):
    """Whether a set file or 2DA (`suffix`, the bytes of the pack copy and of the new one) keeps every entry of the pack
    copy it replaces, in place, adding only after them: areas name tiles, terrains and rows by number, and another
    session may have appended since the overlay was made."""
    old, new = (data.decode('cp1252') for data in (was, made))
    if suffix.lower() == '.set':
        old, new = inventory.read_set(old), inventory.read_set(new)
        return all(new[key][:len(old[key])] == old[key] for key in ('terrains', 'tiles', 'groups'))
    rows = lambda text: [line.split() for line in text.splitlines()[3:] if line.strip()]  # past the version, blank and column lines
    return new.splitlines()[:3] == old.splitlines()[:3] and rows(new)[:len(rows(old))] == rows(old)


def _catalogued(repo, entries):
    """The additions catalog with a copy's entries merged in (`MADE_FROM`), or None when it has none; nothing is
    written. A number once given keeps what it was given: a terrain its tiles, a group its tiles and name (put_group)."""
    if not (entries.get('terrainTiles') or entries.get('tileGroups')):
        return None
    from tools.envkit import catalog
    data = catalog.load(repo / catalog.PATH); same = lambda one, other: (one['tileset'], one['terrain']) == (other['tileset'], other['terrain'])
    unknown = sorted({entry['tileset'] for kind in ('terrainTiles', 'tileGroups') for entry in entries.get(kind, [])} - set(data['baseline']['tilesets']))
    require(not unknown, 'The additions catalog has no baseline for ' + ', '.join(unknown) + ': give it one (docs/additions/README.md) before tiles are added to it')  # as envkit's install
    today = datetime.date.today().isoformat()  # the day the numbers reach the packs, as envkit's install records it
    for group in entries.get('tileGroups', []):  # an entry already there keeps the day it was first added
        there = [old for old in data['tileGroups'] if (old['tileset'], old['group']) == (group['tileset'], group['group'])]
        catalog.put_group(data, {**group, 'added': there[0]['added'] if there else today})
    for terrain in entries.get('terrainTiles', []):
        there = [old for old in data.get('terrainTiles', []) if same(old, terrain)]
        require(all(old['tiles'] == terrain['tiles'] for old in there), f'Terrain {terrain["terrain"]} of {terrain["tileset"]} has tiles {there[0]["tiles"] if there else ""} in the additions catalog')
        data['terrainTiles'] = [old for old in data.get('terrainTiles', []) if not same(old, terrain)] + [{**terrain, 'added': there[0]['added'] if there else today}]
    return catalog.checked(data)  # held to what a load requires, so a later load does not fail on it


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


def _loop_flags(repo, packs, model, number):
    """[whether AnimLoop`number` is on] for each tile of the packs' set files drawn by `model`."""
    found = []
    for pack in packs:
        for path in sorted((Path(repo) / pack).glob('*.set')):
            for section, keys in inventory.sections(path.read_bytes().decode('cp1252')):
                if re.fullmatch(r'TILE\d+', section, re.I) and keys.get('Model', '').lower() == model.lower():
                    found.append(keys.get(f'AnimLoop{number}', '0').strip() == '1')
    return found


def plan(repo, spec, overlay):
    """{'put': [(overlay file, pack file)], 'delete': [pack file], 'overrides': {resource: packs}, 'touched': names,
    'left': [overlay files that are of no texture of the spec and no model]} for a spec's textures (none where spec is
    None) and the overlay's models; nothing is changed. Names are compared in lower case, as the game reads them; a
    file a pack already holds is written and deleted as that pack spells it."""
    repo, overlay = Path(repo), Path(overlay); packs = [pack['Name'] for pack in _configuration(repo)['HakList']]
    record = json.loads((overlay / MADE_FROM).read_text(encoding='utf-8')) if (overlay / MADE_FROM).is_file() else {'kind': 'tilekit-terrain-copy', 'from': {}}
    require(record.get('kind') == 'tilekit-terrain-copy' and isinstance(record.get('from'), dict) and isinstance(record.get('textures', []), list)
            and isinstance(record.get('edges', []), list) and isinstance(record.get('catalog', {}), dict)  # each a list (a dict) before it is read as one
            and all(isinstance(name, str) and name for key in ('textures', 'edges') for name in record.get(key, [])),
            f'{MADE_FROM} is not a terrain copy\'s record')
    sources = json.loads((overlay / MODELS_FROM).read_text(encoding='utf-8-sig')) if (overlay / MODELS_FROM).is_file() else {}
    require(isinstance(sources, dict) and all(isinstance(sha, str) for sha in sources.values()), f'{MODELS_FROM} is not a record of the pack copies changed models were made from')
    cut = json.loads((overlay / WALK_CUTS).read_text(encoding='utf-8-sig')) if (overlay / WALK_CUTS).is_file() else {'tileset': None, 'models': {}}
    require(isinstance(cut, dict) and isinstance(cut.get('models'), dict) and all(isinstance(entry, dict) and all(isinstance(entry.get(key), str) for key in ('aabbFrom', 'aabbTo', 'wokFrom', 'wokTo'))
                                                                                  for entry in cut['models'].values()), f'{WALK_CUTS} is not a record of cut walkmeshes')
    require(not cut['models'] or (spec or {}).get('tileset', cut.get('tileset')) == cut.get('tileset'), f'{WALK_CUTS} is of {cut.get("tileset")}, not of the spec\'s tileset')
    named = {entry['tileset'] for kind in ('terrainTiles', 'tileGroups') for entry in record.get('catalog', {}).get(kind, [])}
    require(named <= {(spec or {}).get('tileset')}, f'{MADE_FROM} is a copy of ' + ', '.join(sorted(named)) + ', not of the spec\'s tileset')
    recorded = {str(model).lower() for entry in record.get('catalog', {}).get('terrainTiles', []) for model in entry.get('models', [])}  # the new tiles the record catalogues (its entries checked by `_catalogued`)
    made_from = {name.lower(): sha for name, sha in record['from'].items()}  # the record's tables, by name in any case
    edged = {name.lower() for name in record.get('edges', [])}  # the copied edge tiles, laid outside an area: no tile of the set, a walkmesh only where the source had one
    spec = {'textures': {}, **(spec or {})}  # an overlay of changed models alone, or a copied terrain's (its spec has no textures)
    held = {}  # lower-case name: {pack: its file there}
    for pack in packs:
        if (repo / pack).is_dir():
            for path in (repo / pack).iterdir():
                held.setdefault(path.name.lower(), {})[pack] = path
    require(not spec['textures'] or spec.get('tileset'), 'A spec with textures names its tileset')
    own = f"srn_t_{spec.get('tileset', '').lower()}"; require(not spec['textures'] or own in packs, f'{own} is no pack of hakbuilder.json'); put, delete, placed = [], [], {}
    for name in sorted(spec['textures']):
        holders = sorted({pack for suffix in HELD for pack in held.get((name + suffix).lower(), {})}) or [own]
        delete += [path for suffix in OLD for path in held.get((name + suffix).lower(), {}).values()]
        if not (overlay / f'{name}.mtr').is_file():  # a plain one: a material an earlier apply put in would still take it over, so it and its maps go
            for material in held.get(f'{name}.mtr'.lower(), {}).values():
                maps = {stem.lower() for stem in re.findall(r'(?m)^\s*texture\d\s+(\S+)', material.read_text(encoding='ascii', errors='replace')) if stem.lower() != 'null'}
                delete += [material] + [path for stem in sorted(maps) for path in held.get(f'{stem}.dds', {}).values() if path.parent == material.parent]
        for path in files_of(overlay, name):
            key = path.name.lower(); strangers = sorted(set(held.get(key, {})) - set(holders))
            require(not strangers, f'{name}: {path.name} is already a file of {", ".join(strangers)}')
            require(key not in placed or placed[key] == holders, f'{path.name} belongs to two textures')
            placed[key] = holders; put += [(path, held.get(key, {}).get(pack, repo / pack / path.name)) for pack in holders]
    kit = json.loads((overlay / KIT_FILES).read_text(encoding='utf-8-sig')) if (overlay / KIT_FILES).is_file() else {'kind': 'tilekit-kit-files', 'tileset': None, 'files': {}}
    require(kit.get('kind') == 'tilekit-kit-files' and isinstance(kit.get('files'), dict) and all(isinstance(sha, str) for sha in kit['files'].values()), f'{KIT_FILES} is not a record of kit files')
    require(not kit['files'] or not spec.get('tileset') or spec['tileset'] == kit.get('tileset'), f'{KIT_FILES} is of {kit.get("tileset")}, not of the tileset of the spec')
    kit_pack = f"srn_t_{str(kit.get('tileset') or '').lower()}"; require(not kit['files'] or kit_pack in packs, f'{kit_pack} is no pack of hakbuilder.json')
    for name, sha in sorted(kit['files'].items()):  # the kit's own files: new to the tileset's pack, or replacing its copy there
        path = overlay / name; require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha, f'{name}: not in the overlay as {KIT_FILES} records it: make the overlay again')
        holders = held.get(name.lower(), {}); strangers = sorted(set(holders) - {kit_pack})
        require(not strangers, f'{name} is already a file of {", ".join(strangers)}')
        put.append((path, holders.get(kit_pack, repo / kit_pack / name)))
    files = [path for path in overlay.iterdir() if path.is_file()]; present = {path.name.lower() for path in files}  # the overlay, listed once
    lacking = sorted((set(made_from) | {model + suffix for model in recorded for suffix in MODELS} | {model + '.mdl' for model in edged}) - present)
    require(not lacking, f'The overlay lacks what its {MADE_FROM} says the copy made: ' + ', '.join(lacking) + ': make the overlay again')  # a copy applies whole
    for path in sorted(path for path in files if path.suffix.lower() in MODELS + TABLES):
        holders = held.get(path.name.lower(), {})
        if not holders and path.suffix.lower() in MODELS:  # a new tile (a copied terrain's): to the tileset's own pack
            require(spec.get('tileset') and own in packs, f'{path.name} is new: the spec names the tileset whose pack takes it')
            require((overlay / MADE_FROM).is_file(), f'{path.name} is new, and the overlay has no {MADE_FROM}: only a whole terrain copy brings new tiles')
            require(path.stem.lower() in recorded | edged, f'{path.name} is new, and {MADE_FROM} catalogues no tile of it and names no edge tile of it')  # whose model and walkmesh are both here (`lacking`)
            put.append((path, repo / own / path.name)); continue
        require(len(holders) == 1, f'{path.name}: a changed file replaces the one pack copy it was made from, not {len(holders)}')
        (was,) = holders.values(); made, there = path.read_bytes(), was.read_bytes()  # each read once
        require(path.suffix.lower() not in TABLES or path.name.lower() in made_from or made == there,
                f'{path.name}: a set file, edge table or palette replaces its pack copy only with the {MADE_FROM} of the copy that made it')  # only terrain.copy makes them
        entry = cut['models'].get(path.stem.lower())
        if path.suffix.lower() == '.mdl':
            from .detail import turning_loops
            for number in sorted(turning_loops(made.decode('cp1252'))):  # a camera's sweep plays only where the set file turns its loop on
                flags = _loop_flags(repo, packs, path.stem, number)
                require(flags and all(flags), f'{path.name}: its turning heads sweep in animloop0{number}, and the set file has AnimLoop{number} off for it: turn it on first')
            was_walk, made_walk = inventory.walk_hash(there.decode('cp1252')), inventory.walk_hash(made.decode('cp1252'))
            require(made_walk == was_walk or (entry and (was_walk, made_walk) == (entry['aabbFrom'], entry['aabbTo'])),
                    f'{path.name}: its walkmesh differs from the pack copy it replaces' + (f', and not as {WALK_CUTS} records' if entry else ''))
        if path.suffix.lower() == '.wok':
            require(made == there or (entry and (hashlib.sha256(there).hexdigest(), hashlib.sha256(made).hexdigest()) == (entry['wokFrom'], entry['wokTo'])),
                    f'{path.name}: a walkmesh in a pack is replaced only as {WALK_CUTS} records its cut')
        if path.name.lower() in sources and made != there:  # a changed model (lamps', shadows') over the very pack copy it was made from
            require(hashlib.sha256(there).hexdigest() == sources[path.name.lower()], f'{path.name}: the pack copy changed since the overlay copy was made from it: make the overlay again')
        if path.name.lower() in made_from and made != there:  # the palette too, which cannot be compared entry by entry; one in place already is applied again
            require(hashlib.sha256(there).hexdigest() == made_from[path.name.lower()], f'{path.name}: the pack copy changed since the overlay was made from it: make the overlay again')
        if path.suffix.lower() in ('.set', '.2da'):
            require(_extends(path.suffix, there, made),f'{path.name}: it lacks or changes entries the pack copy has (added since the overlay was made?): make the overlay again')
        put.append((path, was))
    after = {name: set(holding) for name, holding in held.items()}  # what each pack holds once this apply is done
    for path in delete:
        after[path.name.lower()].discard(path.parent.name)
    for _, target in put:
        after.setdefault(target.name.lower(), set()).add(target.parent.name)
    bare = sorted(name for name in record.get('textures', []) if not any(after.get(name.lower() + suffix) for suffix in HELD))  # a copy's renamed textures
    require(not bare, f'The copied tiles name textures no pack holds and this apply brings none of: {", ".join(bare)} (apply them with the copies\' material spec)')
    touched = {path.name.lower() for path in delete} | {target.name.lower() for _, target in put}
    overrides = {name: sorted(after[name]) for name in sorted(touched) if len(after.get(name, ())) > 1}
    lacking = sorted(model + suffix for model in cut['models'] for suffix in MODELS if model + suffix not in present)
    require(not lacking, f'{WALK_CUTS} names cut walkmeshes the overlay lacks: ' + ', '.join(lacking))
    used = {path.name for path, _ in put} | {MADE_FROM, MODELS_FROM, WALK_CUTS, KIT_FILES}; left = sorted(path.name for path in files if path.name not in used)
    return {'put': put, 'delete': sorted(set(delete) - {target for _, target in put}), 'overrides': overrides, 'touched': touched, 'left': left,
            'catalog': _catalogued(repo, record.get('catalog', {})), 'cut': cut}  # merged before anything is written, so a refusal changes nothing


def apply(repo, spec, overlay):
    """Carry out `plan`, rewrite hakbuilder.json's expected overrides for the names touched, and tell the counts."""
    repo = Path(repo); moves = plan(repo, spec, overlay)
    for path, target in moves['put']:  # written first: a write that fails leaves the old copies in place
        target.write_bytes(path.read_bytes())
    for path in moves['delete']:
        path.unlink()
    configuration = _configuration(repo); waiting = dict(moves['overrides']); entries, dropped = [], 0
    for entry in configuration['ExpectedOverrides']:  # each kept where it stands; a name touched gets its packs as they are now
        resource = entry['Resource'].lower()
        if resource not in moves['touched']:
            entries.append(entry)
        elif resource in waiting:
            entries.append({**entry, 'Packs': waiting.pop(resource)})
        else:
            dropped += 1
    configuration['ExpectedOverrides'] = entries + [{'Resource': name, 'Packs': packs} for name, packs in waiting.items()]
    (repo / 'hakbuilder.json').write_text(json.dumps(configuration, indent=2) + '\n', encoding='utf-8', newline='\n')
    if moves['cut']['models']:  # the cut walkmeshes are the tileset's walkmeshes now: its baseline says so
        path = repo / 'docs' / 'tilesets' / moves['cut']['tileset'] / 'walkmesh.json'
        baseline = json.loads(path.read_text(encoding='utf-8-sig'))
        for model, entry in moves['cut']['models'].items():
            baseline['models'][model] = {**baseline['models'].get(model, {}), 'wok': entry['wokTo'], 'aabb': entry['aabbTo'], 'cut': len(entry.get('footprints', []))}
        path.write_text(json.dumps(baseline, indent=2) + '\n', encoding='utf-8', newline='\n')
    told = {'put': len(moves['put']), 'deleted': len(moves['delete']), 'overrides': len(moves['overrides']), 'new overrides': len(waiting), 'dropped overrides': dropped,
            'not applied': moves['left']}
    if moves['catalog'] is not None:  # a copied terrain's numbers, recorded as envkit's install records its own
        from tools.envkit import catalog
        catalog.save(repo / catalog.PATH, moves['catalog']); told['catalogued'] = True
    return told
