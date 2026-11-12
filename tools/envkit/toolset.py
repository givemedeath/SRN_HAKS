"""A Toolset check of tile groups from the built packs, in a user folder of its own.

Painting a group in the Toolset is the only proof that a builder can: that the palette lists it, that it goes down, and
that the Toolset makes a door at its hook. `prepare` makes a fresh user folder the Toolset is started on
(`-userdirectory`), so that the user's own Neverwinter Nights folder is never touched: a module with one plain area
for each tileset the groups are in, the project's talk table, and a `hak` folder that is a junction to the built packs.
The painting itself is done by hand or by computer use (`Toolset.ps1` reaches what simulated clicks cannot;
docs/envkit/sheet-runbook.md says how). `saved` then reads what the Toolset saved, which is what is checked: the group
tiles laid and the doors made. `retire` takes the junction away, after which the folder can be deleted; deleting it
with the junction in it would delete the built packs.

A module built outside the Toolset opens in it if each area has an `.are`, a `.git` and an empty `.gic`; its start
point stands in a corner tile, because the Toolset refuses to save while the start stands on a tile that has been
painted over with something not walkable. These were one-off scripts for the Stuffer Shack and the Ares Depot
(2026-11-10 to 2026-11-12)."""
import json
import os
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from tools.armorkit import client_fixture
from tools.armorkit.client_fixture import field

from . import require

MODULE = 'ektool'
AREAS = {'dgt04': ('ektdg', 'Modern Exterior', 0), 'udp1': ('ektud', 'Suburbs', 52)}  # tileset: area, its name, the tile it is laid with
HAKS = ('srn_t_dgt04', 'srn_t_udp1', 'srn_t_common', 'srn_door', 'srn_placeable', 'srn_2da')  # as a module lists them, first wins
TLK = 'srn'
START = (5.0, 5.0)  # the south-west corner tile
SIZE = 8
PLACED = ('Appearance', 'X', 'Y', 'Z', 'Bearing', 'Tag', 'TemplateResRef')


def documents(tilesets=tuple(AREAS), haks=HAKS, tlk=TLK, size=SIZE):
    """{file name: GFF document as JSON} of the module: one plain area for each tileset, the first the start area."""
    require(tilesets and all(tileset in AREAS for tileset in tilesets), 'A check area is laid in ' + ' or '.join(AREAS))
    made = client_fixture.module_documents(MODULE, list(haks), tlk, START); ifo = made['module.ifo']
    ifo['Mod_HakList']['value'] = ifo['Mod_HakList']['value'][1:]  # the fixture's own pack, which this module has none of
    ifo['Mod_OnClientEntr'] = field('resref', ''); ifo['Mod_Name'] = field('cexolocstring', {'0': 'Envkit toolset check'}); ifo['Mod_Area_list']['value'] = []
    empty = {'__data_type': 'GIC ', **{key: field('list', []) for key in ('Creature List', 'Door List', 'Encounter List', 'List', 'SoundList', 'StoreList',
                                                                           'TriggerList', 'WaypointList', 'Placeable List')}}
    for tileset in tilesets:
        name, title, fill = AREAS[tileset]; area = client_fixture.area_documents(name, [], size); are = area[name + '_a.are']
        are['Tileset'] = field('resref', tileset); are['Name'] = field('cexolocstring', {'0': title})
        for laid in are['Tile_List']['value']:
            laid['Tile_ID'] = field('int', fill)
        made.update(area); made[name + '_a.gic'] = json.loads(json.dumps(empty))
        ifo['Mod_Area_list']['value'].append({'__struct_id': 6, 'Area_Name': field('resref', name + '_a')})
    ifo['Mod_Entry_Area'] = field('resref', AREAS[tilesets[0]][0] + '_a')
    return made


def _tools():
    from tools.phenotypes import tool_runtime
    found = {}

    def run(tool, arguments, **more):
        found.setdefault(tool, tool_runtime.tool(tool))
        result = subprocess.run([str(found[tool]), *map(str, arguments)], capture_output=True, timeout=600, **more)
        require(result.returncode == 0, tool + ' failed: ' + result.stderr.decode(errors='replace')[-800:])
        return result.stdout
    return run


def prepare(user, built, *, tilesets=tuple(AREAS), haks=HAKS, tlk=TLK, game=None):
    """Make the fresh user folder `user` for the Toolset: the module, the talk table from `built` (the folder the packs
    were built into) and `hak` as a junction to it. Returns {module, user, launch}; `launch` starts the Toolset on the
    folder where the game install folder is given."""
    user, built = Path(user).resolve(), Path(built).resolve()
    require(not user.exists(), 'A fresh user folder is required: ' + str(user))
    missing = [name for name in haks if not (built / f'{name}.hak').is_file()] + ([] if (built / f'{tlk}.tlk').is_file() else [tlk + '.tlk'])
    require(not missing, f'The built packs are needed in {built}: ' + ', '.join(missing))
    work = user.parent / (user.name + '-work'); shutil.rmtree(work, ignore_errors=True); run = _tools()
    for folder in (user / 'modules', user / 'tlk', work / 'json', work / 'module'):
        folder.mkdir(parents=True)
    shutil.copyfile(built / f'{tlk}.tlk', user / 'tlk' / f'{tlk}.tlk')
    subprocess.run(['cmd', '/c', 'mklink', '/J', str(user / 'hak'), str(built)], check=True, capture_output=True)
    for name, document in documents(tilesets, haks, tlk).items():
        path = work / 'json' / (name + '.json'); path.write_text(json.dumps(document), encoding='utf-8')
        run('nwn_gff', ['-i', path, '-o', work / 'module' / name])
    module = user / 'modules' / f'{MODULE}.mod'; run('nwn_erf', ['-c', '-f', module, '-e', 'MOD', work / 'module'])
    launch = [str(Path(game) / 'bin' / 'win32' / 'nwtoolset.exe'), '-userdirectory', str(user)] if game else None
    return {'module': str(module), 'user': str(user), 'launch': launch}


def report(areas, first_group_tile):
    """What a saved module holds, from its areas' documents: {area: {tileset, size, groupTiles: [{tile, column, row,
    turn}], doors: [...]}}. areas: {name: (are, git)}; first_group_tile: {tileset: the tile number its envkit groups
    begin at}, so that the tiles the Toolset repainted round a group are not taken for the group."""
    told = {}
    for name, (are, git) in areas.items():
        tileset = are['Tileset']['value']; width = are['Width']['value']; first = first_group_tile.get(tileset)
        tiles = [{'tile': laid['Tile_ID']['value'], 'column': index % width, 'row': index // width, 'turn': laid['Tile_Orientation']['value']}
                 for index, laid in enumerate(are['Tile_List']['value']) if first is not None and laid['Tile_ID']['value'] >= first]
        told[name] = {'tileset': tileset, 'size': [width, are['Height']['value']], 'groupTiles': tiles,
                      'otherTiles': dict(sorted(Counter(laid['Tile_ID']['value'] for laid in are['Tile_List']['value']
                                                        if first is None or laid['Tile_ID']['value'] < first).items())),
                      'doors': [{key: door[key]['value'] for key in PLACED if key in door} for door in git['Door List']['value']]}
    return told


def first_envkit_tile(set_text):
    """The number of the first tile of a tileset whose model is an envkit one (`ek_...`), or None."""
    for block in set_text.split('[TILE')[1:]:
        number, _, rest = block.partition(']')
        if number.isdigit() and '\nModel=ek_' in rest.replace('\r', ''):
            return int(number)
    return None


def saved(module, repo):
    """Read a module the Toolset saved: its group tiles and doors by area (`report`), and its start point."""
    module, repo = Path(module).resolve(), Path(repo).resolve(); run = _tools()
    out = module.parent.parent.parent / (module.stem + '-saved'); shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    run('nwn_erf', ['-x', '-f', module], cwd=out)
    read = lambda name: json.loads(run('nwn_gff', ['-i', out / name, '-k', 'json']))
    ifo = read('module.ifo'); names = [row['Area_Name']['value'] for row in ifo['Mod_Area_list']['value']]
    areas = {name: (read(name + '.are'), read(name + '.git')) for name in names}
    first = {}
    for tileset in {are['Tileset']['value'] for are, _ in areas.values()}:
        path = repo / f'srn_t_{tileset}' / f'{tileset}.set'
        first[tileset] = first_envkit_tile(path.read_bytes().decode('cp1252')) if path.is_file() else None
    return {'areas': report(areas, first), 'start': [ifo['Mod_Entry_Area']['value'], ifo['Mod_Entry_X']['value'], ifo['Mod_Entry_Y']['value']]}


def retire(user):
    """Take away the user folder's junction to the built packs, leaving the packs: the folder may then be deleted."""
    link = Path(user) / 'hak'
    if not os.path.lexists(link):
        return False
    require(link.is_junction(), 'hak is a real folder here, not a junction: nothing is removed')
    os.rmdir(link)  # removes the junction itself, never what it points to
    return True
