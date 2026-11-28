"""A review module of a tileset on the built packs, and the views taken of it in the game client.

A restyle is judged in the game, from the same places before and after. Three kinds of area are laid: a `block` of
every building terrain as a builder would paint it, with streets between; a `grid` of every tile of the set, row on
row with plain ground between the rows; and any area someone built with the tileset. Each is laid once for every
lighting it is looked at in (day, night and overcast: LIGHTS), since an area's lighting is the area's.

The block is worked out from the set file the way the Toolset paints: every corner of the area is given a terrain, and
each cell takes a tile whose four corners and four crossers agree with it, turned as needed (`solve`). The module
lists the built packs in the order a module does, with a pack of its own first: whatever is put in that pack
(`overlay`) is shown instead of the packs' own, which is how a restyled texture is tried without building a pack.
The client run and its captures are envkit's (`prop_fixture.run`), so the same rules hold: no client is started while
another runs, and a view captured after it had passed is not kept as that view."""
import copy
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from tools.armorkit import client, client_fixture
from tools.armorkit.client_fixture import field
from tools.envkit import checks, prop_fixture

from . import PARTS, require
from .client_settings import settings

TILE = 10.0
HAKS = ('srn_t_dgt04', 'srn_t_udp1', 'srn_t_common', 'srn_door', 'srn_placeable', 'srn_envprop', 'srn_2da')  # as a module lists them, first wins
TLK = 'srn'
START, HOLD = 8.0, 6.0  # seconds before the first view, and each view is held
ARRIVE = 8.0  # seconds given to a view in another area than the last, for the area to load
STEP = 0.2  # seconds given to a view in the same area as the last, for the player to be stood there
REACH = 6  # tiles of a grid row one view holds
NAME = client_fixture.NAME


def colour(red, green, blue):
    return red | green << 8 | blue << 16


# Day and night are envkit's check lighting (client_fixture's area, prop_fixture's night), so a restyled tile is seen
# as the envkit buildings beside it were when they were approved. Overcast is the same day with the weaker, greyer sun
# of environment.2da's Exterior, Overcast. The game's own Exterior, Clear numbers (ambient 50/50/100, sun 255) were
# tried first and left these areas lit by little but the ambient light, too dark to judge a texture by (2026-11-18).
LIGHTS = {
    'day': {'IsNight': 0, 'SunAmbientColor': colour(176, 176, 176), 'SunDiffuseColor': colour(238, 238, 238), 'SunFogColor': colour(104, 126, 145),
            'SunFogAmount': 0, 'SunShadows': 1, 'ShadowOpacity': 20},
    'overcast': {'IsNight': 0, 'SunAmbientColor': colour(120, 124, 130), 'SunDiffuseColor': colour(168, 166, 147), 'SunFogColor': colour(122, 122, 122),
                 'SunFogAmount': 0, 'SunShadows': 1, 'ShadowOpacity': 20},
    'night': {'IsNight': 1, 'MoonAmbientColor': 0x302820, 'MoonDiffuseColor': 0x504840, 'MoonFogColor': colour(20, 20, 40),
              'MoonFogAmount': 0, 'MoonShadows': 1, 'ShadowOpacity': 20},
}
KINDS = {'IsNight': 'byte', 'SunFogAmount': 'byte', 'MoonFogAmount': 'byte', 'SunShadows': 'byte', 'MoonShadows': 'byte', 'ShadowOpacity': 'byte'}


def turned(tile, turn):
    """(corners, crossers) of a tile turned `turn` quarter turns counter-clockwise, as an area's Tile_Orientation turns
    it: corners top left, top right, bottom left, bottom right; crossers top, right, bottom, left. Held against the
    D20 Modern project's own outdoor area, whose 143 tiles in all four turns agree at every corner this way only."""
    (tl, tr, bl, br), (top, right, bottom, left) = tile['corners'], tile['crossers']
    for _ in range(turn % 4):
        tl, tr, br, bl = tr, br, bl, tl
        top, left, bottom, right = right, top, left, bottom
    return (tl, tr, bl, br), (top, right, bottom, left)


def _cell(column, row):
    """The corners and edges of a cell, as keys shared with its neighbours: corners top left, top right, bottom left,
    bottom right; edges top, right, bottom, left."""
    return (((column, row + 1), (column + 1, row + 1), (column, row), (column + 1, row)),
            (('h', column, row + 1), ('v', column + 1, row), ('h', column, row), ('v', column, row)))


def _folded(sides):
    """(corners, crossers) with every name in lower case: the game matches terrain and crosser names in any case, and
    a set may spell one two ways (dgt04: Freeway and freeway)."""
    return tuple(tuple(name.lower() for name in part) for part in sides)


def disagreements(width, laid, tiles):
    """Where the tiles of an area disagree with a neighbour, as lines: empty for an area a builder could have painted.
    laid: [(tile number, turn)] row by row from the south-west; tiles: {number: tile of the set}."""
    seen, lines = {}, []
    for index, (number, turn) in enumerate(laid):
        column, row = index % width, index // width; corners, crossers = turned(tiles[number], turn); keys = _cell(column, row)
        for key, name in [*zip(keys[0], corners), *zip(keys[1], crossers)]:
            if seen.setdefault(key, name).lower() != name.lower():  # told as each tile spells it
                lines.append(f'tile {number} at {column},{row}: {name or "nothing"} where a neighbour has {seen[key] or "nothing"}')
    return lines


def solve(tiles, default, width, height, patches, runs=(), avoid=()):
    """{(column, row): (tile number, turn)} for an area of `default` terrain with `patches` of other terrains and `runs`
    of crossers, each cell laid with a tile that agrees with it. patches: [{terrain, at: [column, row], size: [columns,
    rows]}] in corners of the area (a patch of 2 by 2 corners is the smallest building: four corner tiles, four sides and
    a middle), a later one lying over an earlier only where it says `over`. runs: [{crosser, cells: [[column, row], [column, row]]}] straight from cell to cell, crossing every edge
    between and the area's edge where they reach it. avoid: tile numbers never laid (those of groups, which the Toolset
    lays only as groups). Tiles with a raised corner are not laid. Where several tiles fit, cells take them in turn."""
    corner, edge = {}, {}
    for patch in patches:
        (x0, y0), (columns, rows) = patch['at'], patch.get('size', (2, 2)); low = 0 if patch.get('border') else 1  # a `border` patch may meet the area's edge, where the edge table lays its edge tiles
        require(low <= x0 and x0 + columns <= width + 1 - low and low <= y0 and y0 + rows <= height + 1 - low, f'{patch["terrain"]} at {x0},{y0} reaches the area\'s edge')
        for x in range(x0, x0 + columns):
            for y in range(y0, y0 + rows):
                require(patch.get('over') or (x, y) not in corner, f'{patch["terrain"]} at {x0},{y0} lies over another patch')  # `over`: a building on a district's ground
                corner[(x, y)] = patch['terrain'].lower()  # names in any case, as the game reads them (`_folded`)
    for run in runs:
        (c0, r0), (c1, r1) = run['cells']; require(c0 == c1 or r0 == r1, 'A run of a crosser is straight')
        if c0 == c1:
            ends = sorted((r0, r1))
            for row in range(ends[0] + (0 if ends[0] == 0 else 1), ends[1] + (2 if ends[1] == height - 1 else 1)):
                edge[('h', c0, row)] = run['crosser'].lower()
        else:
            ends = sorted((c0, c1))
            for column in range(ends[0] + (0 if ends[0] == 0 else 1), ends[1] + (2 if ends[1] == width - 1 else 1)):
                edge[('v', column, r0)] = run['crosser'].lower()
    avoid = set(avoid); fits = {}; default = default.lower()
    for number in sorted(tiles):
        tile = tiles[number]
        if number in avoid or any(tile['heights']):
            continue
        for turn in range(4):
            fitting = fits.setdefault(_folded(turned(tile, turn)), [])
            if not fitting or fitting[-1][0] != number:  # each tile once, at its first turn that fits, however many do
                fitting.append((number, turn))
    laid, missing = {}, []
    for row in range(height):
        for column in range(width):
            corners, edges = _cell(column, row)
            want = (tuple(corner.get(key, default) for key in corners), tuple(edge.get(key, '') for key in edges))
            found = fits.get(want)
            if found:
                laid[(column, row)] = found[(column * 7 + row * 13) % len(found)]
            else:
                missing.append(f'{column},{row} needs corners {"/".join(want[0])}' + (f' with {"/".join(name or "-" for name in want[1])}' if any(want[1]) else ''))
    require(not missing, 'No tile of the set fits: ' + '; '.join(missing[:6]) + (f' and {len(missing) - 6} more' if len(missing) > 6 else ''))
    return laid


def stamped(cells, tiles, set_text, groups, width, height):
    """`cells` (`solve`) with whole groups laid over them: groups [{name, at: [column, row]}], the group's south-west
    tile at `at`, unturned, as the Toolset lays one. The ground under a group is the spec's to give (a patch of the
    group's terrain): a group whose tiles disagree with a neighbour is refused, where the Toolset would repaint round it.
    A group that says `loose` is laid to be looked at only: its walks and drives may end at its edge (a mall front or a
    school wants walks and driveways laid to fit, which no patch gives)."""
    from . import inventory
    shapes = {keys['Name'].lower(): (int(keys['Rows']), int(keys['Columns']), keys) for name, keys in inventory.sections(set_text) if name.startswith('GROUP') and 'Rows' in keys}
    cells = dict(cells); loose = set()
    for group in groups:
        require(group['name'].lower() in shapes, f'The set has no group {group["name"]}')
        rows, columns, keys = shapes[group['name'].lower()]; column0, row0 = group['at']
        require(0 <= column0 and column0 + columns <= width and 0 <= row0 and row0 + rows <= height, f'{group["name"]} at {column0},{row0} leaves the area')
        for row in range(rows):
            for column in range(columns):
                number = int(keys[f'Tile{row * columns + column}'])
                if number >= 0:
                    cells[(column0 + column, row0 + row)] = (number, 0)
                    if group.get('loose'):
                        loose |= {(column0 + column + x, row0 + row + y) for x in (-1, 0, 1) for y in (-1, 0, 1)}  # the tile and those round it
    wrong = disagreements(width, [cells[(column, row)] for row in range(height) for column in range(width)], tiles)
    cell = lambda line: re.search(r' at (\d+),(\d+):', line)  # a line whose cell cannot be read is kept
    wrong = [line for line in wrong if not cell(line) or tuple(map(int, cell(line).groups())) not in loose]
    require(not wrong, 'A group does not fit the ground it is laid on: ' + '; '.join(wrong[:4]) + (f' and {len(wrong) - 4} more' if len(wrong) > 4 else ''))
    return cells


def grid(numbers, fill, across=32):
    """(width, height, laid, rows) for every tile of `numbers` laid unturned in rows of `across`, each row with a row
    of the plain tile `fill` south of it and one north of the last: a view from either side of a row sees no other."""
    numbers = list(numbers); require(numbers and 1 <= across <= 32, 'A grid has tiles, 32 to a row at most')
    rows = -(-len(numbers) // across); height = rows * 2 + 1; require(height <= 32, 'These tiles do not fit one area: give fewer')
    laid = {(column, row): (fill, 0) for column in range(across) for row in range(height)}
    for index, number in enumerate(numbers):
        laid[(index % across, index // across * 2 + 1)] = (number, 0)
    return across, height, laid, rows


PITCH_LIMIT, DISTANCE_LIMIT = 150.0, 200.0  # a view's camera may look up from the street (pitch over 90) at a tower's top, and stand far off

def _shot(area, label, x, y, facing, distance, pitch, height=1.0):
    return {'area': area, 'label': label, 'stand': [round(x, 2), round(y, 2)], 'facing': facing, 'distance': distance, 'pitch': pitch, 'height': height}


def grid_shots(area, prefix, across, rows, *, reach=REACH, distance=55.0, pitch=52.0):
    """Views of a grid: each row from the south and from the north, `reach` tiles to a view, the camera standing on the
    plain row beside it."""
    shots = []
    for row in range(rows):
        for start in range(0, across, reach):
            x = (start + min(start + reach, across)) / 2 * TILE
            shots.append(_shot(area, f'{prefix}-r{row:02d}-c{start:02d}-s', x, (row * 2 + 0.5) * TILE, 90, distance, pitch))
            shots.append(_shot(area, f'{prefix}-r{row:02d}-c{start:02d}-n', x, (row * 2 + 2.5) * TILE, 270, distance, pitch))
    return shots


def corner_shots(area, prefix, crossings, *, distance=34.0, pitch=58.0):
    """Views of a block from where its streets cross: four from each crossing, one toward each building round it."""
    return [_shot(area, f'{prefix}-x{column:02d}y{row:02d}-{name}', (column + 0.5) * TILE, (row + 0.5) * TILE, facing, distance, pitch)
            for column, row in crossings for name, facing in (('ne', 45), ('nw', 135), ('sw', 225), ('se', 315))]


EYE = {'height': 1.7, 'distance': 1.0, 'turns': (45, 135, 225, 315), 'pitches': (90, 105)}  # a standing person's eye; pitch 90 is level, more looks up


def eye_shots(area, prefix, crossings, *, height=EYE['height'], distance=EYE['distance'], turns=EYE['turns'], pitches=EYE['pitches'], places=()):
    """Views from inside a room, at eye level: from the middle of each crossing's cell, turned each of `turns` degrees,
    once for each of `pitches` (90 level, more than 90 looking up). A view from above never shows a ceiling, nor how a
    room stands round a person; an interior is judged from these. Named x03y03-045-090: the turn, then the pitch. places:
    [{name, at: [column, row], parts of a cell too, turns, and distance, height or pitches of its own (pitch 10 looks down)}] for
    rooms a wall parts the middle of the cell from; named by their names."""
    return [_shot(area, f'{prefix}-x{column:02d}y{row:02d}-{int(turn):03d}-{int(pitch):03d}', (column + 0.5) * TILE, (row + 0.5) * TILE, turn, distance, pitch, height)
            for column, row in crossings for pitch in pitches for turn in turns] + [
            _shot(area, f'{prefix}-{place["name"]}-{int(turn):03d}-{int(pitch):03d}', place['at'][0] * TILE, place['at'][1] * TILE, turn, place.get('distance', distance), pitch, place.get('height', height))
            for place in places for turn in place['turns'] for pitch in place.get('pitches', pitches)]


def lattice_shots(area, prefix, width, height, *, step=4, distance=30.0, pitch=58.0):
    """Views of an area someone built: from the middle of every `step`th cell, looking north and looking south. An
    area smaller than a step is still looked at, from its first cell."""
    return [_shot(area, f'{prefix}-x{column:02d}y{row:02d}-{name}', (column + 0.5) * TILE, (row + 0.5) * TILE, facing, distance, pitch)
            for row in range(min(step // 2, (height - 1) // 2), height, step) for column in range(min(step // 2, (width - 1) // 2), width, step)
            for name, facing in (('n', 90), ('s', 270))]


def waits(shots, arrive=ARRIVE):
    """Seconds each view waits before its camera is set: `arrive` for the first and for one in another area than the
    last, STEP for the rest."""
    return [arrive if index == 0 or shots[index - 1]['area'] != shot['area'] else STEP for index, shot in enumerate(shots)]


def enter_script(shots, start=START, hold=HOLD, arrive=ARRIVE, more=None):
    """The module's entry script: the player, unseen, is stood at each view in turn, in whichever area it is of, and the
    camera set. Each view writes envkit's shot line a second after its camera is set, which is what a capture waits
    for; a view in another area than the last is given `arrive` seconds first. The line says valid=0 where the player
    is not standing in the view's area by then (`capture` names those views). more: (functions, statement), script of a
    caller's own (`walk`'s walkers): the functions are written before `main`, which runs the statement as it enters."""
    require(all(prop_fixture.LABEL.fullmatch(shot['label']) for shot in shots), 'A view\'s label is letters, digits, - and _')
    prefix = prop_fixture.LOG_PREFIX
    lines = ['void Line(object pc,int n,string label,string area) {',
             f'  WriteTimestampedLogEntry("{prefix} shot="+IntToString(n)+" target="+label+" valid="+IntToString(GetTag(GetArea(pc))==area));', '}',
             'void Shot(object pc,int n) {', f'  if(n>={len(shots)}) {{ WriteTimestampedLogEntry("{prefix} done"); return; }}',
             '  float x; float y; float facing; float distance; float pitch; float height; float wait; string label; string area;']
    for index, (shot, wait) in enumerate(zip(shots, waits(shots, arrive))):
        lines.append(f'  if(n=={index}) {{ x={shot["stand"][0]:.3f}; y={shot["stand"][1]:.3f}; facing={float(shot["facing"]):.3f}; distance={float(shot["distance"]):.3f}; '
                     f'pitch={float(shot["pitch"]):.3f}; height={float(shot["height"]):.3f}; wait={wait:.1f}; label="{shot["label"]}"; area="{shot["area"]}"; }}')
    lines += ['  AssignCommand(pc,ClearAllActions()); AssignCommand(pc,JumpToLocation(Location(GetObjectByTag(area),Vector(x,y,0.0),facing)));',
              '  DelayCommand(wait,SetCameraHeight(pc,height)); DelayCommand(wait,AssignCommand(pc,SetCameraFacing(facing,distance,pitch,CAMERA_TRANSITION_TYPE_SNAP)));',
              f'  DelayCommand(wait+{prop_fixture.LINE_DELAY:.1f},Line(pc,n,label,area));',
              f'  DelayCommand(wait+{hold:.1f},Shot(pc,n+1));', '}', *([more[0]] if more else []),
              'void main() {', '  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;', f'  SetCameraLimits(pc,1.0,{PITCH_LIMIT:.1f},0.5,{DISTANCE_LIMIT:.1f});',
              '  ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectVisualEffect(VFX_DUR_CUTSCENE_INVISIBILITY),pc);',
              *(['  ' + more[1]] if more else []), '  SetCutsceneMode(pc,TRUE,FALSE);', f'  WriteTimestampedLogEntry("{prefix} enter shots={len(shots)}");',
              f'  DelayCommand({start:.1f},Shot(pc,0));', '}']
    return '\n'.join(lines) + '\n'


def plain(laid):
    """The number of a set's plain tile: its default terrain at every corner, level, with no crosser, outside groups."""
    grouped = {number for group in laid['groups'] for number in group['tiles']}
    found = [tile['number'] for tile in laid['tiles'] if tile['number'] not in grouped and not any(tile['heights']) and not any(tile['crossers'])
             and {corner.lower() for corner in tile['corners']} == {laid['default'].lower()}]  # in any case, as the game reads them
    require(found, 'The set has no plain tile of its default terrain: give the review a fill')
    return found[0]


SOUTH = math.pi  # a placeable's bearing that faces south, toward the views of `prop_shots`
PROP_GROUP = {'across': 5, 'spacing': 6.0, 'apart': 12.0, 'distance': 24.0, 'pitch': 55.0, 'bearing': SOUTH, 'state': 0}  # a group of placeables of about one size; state 4: switched on


def prop_rows(models, appearance, *, across=5, spacing=6.0, apart=12.0, bearing=SOUTH, state=0):
    """(width, height, props, rows) of placeables stood `across` to a row, `spacing` metres apart, rows `apart` metres
    apart, a tile of ground round them. props: [{model, appearance, position, bearing}] (bearing pi faces south, toward
    the views of `prop_shots`); appearance: {model: placeables.2da row}."""
    require(models, 'No placeables to stand'); missing = sorted(set(models) - set(appearance))
    require(not missing, 'These models have no row of placeables.2da: ' + ', '.join(missing))
    count = -(-len(models) // across)
    width, height = 2 + math.ceil(across * spacing / TILE), 2 + math.ceil(count * apart / TILE)
    require(width <= 32 and height <= 32, 'These placeables do not fit one area: give fewer, or closer')
    props = [{'model': model, 'appearance': appearance[model], 'position': [TILE + spacing * (index % across + 0.5), TILE + apart * (index // across + 0.5)], 'bearing': bearing, **({'state': state} if state else {})}
             for index, model in enumerate(models)]
    return width, height, props, count


def prop_shots(area, prefix, rows, *, across=5, spacing=6.0, apart=12.0, distance=24.0, pitch=55.0):
    """One view of each row of `prop_rows`, from the south, the player standing just short of it."""
    return [_shot(area, f'{prefix}-r{row:02d}', TILE + spacing * across / 2, TILE + apart * (row + 0.5) - 3.0, 90, distance, pitch) for row in range(rows)]


def door(tag, generic, position, bearing, opened=0):
    """One generic door of an area's door list: `generic` its row of genericdoors.2da (a row past 255 is read from
    GenericType_New), standing at `position` (x, y, z) turned `bearing` degrees, `opened` 0 shut, 1 or 2 open that way."""
    x, y, z = position; gff_float = client_fixture.gff_float
    values = {'Tag': field('cexostring', tag), 'LocName': field('cexolocstring', {'0': tag}), 'Description': field('cexolocstring', {}),
              'TemplateResRef': field('resref', ''), 'Appearance': field('dword', 0), 'GenericType': field('byte', min(generic, 255)),
              'GenericType_New': field('dword', generic), 'OpenState': field('byte', opened), 'AnimationState': field('byte', opened),
              'Plot': field('byte', 1), 'HP': field('short', 15), 'CurrentHP': field('short', 15), 'Hardness': field('byte', 5),
              'Fort': field('byte', 16), 'Ref': field('byte', 0), 'Will': field('byte', 0), 'Faction': field('dword', 1),
              'Lockable': field('byte', 0), 'Locked': field('byte', 0), 'KeyRequired': field('byte', 0), 'KeyName': field('cexostring', ''),
              'Interruptable': field('byte', 1), 'Conversation': field('resref', ''), 'LinkedTo': field('cexostring', ''),
              'LinkedToFlags': field('byte', 0), 'PortraitId': field('word', 0), 'TrapFlag': field('byte', 0),
              'X': gff_float(x), 'Y': gff_float(y), 'Z': gff_float(z), 'Bearing': gff_float(math.radians(bearing))}
    return {'__struct_id': 8, **values}


def area_documents(tag, title, tileset, width, height, laid, light, lamps=None, props=(), doors=()):
    """{file: document} of one area: its tiles as laid ({(column, row): (tile number, turn)}, every cell), its lighting
    one of LIGHTS, nothing standing in it but `props` (`prop_rows`) and `doors` ([{row, position, bearing, opened}],
    `door`). lamps: {main, source} switches every tile's own lights on, as a builder does in the Toolset: each a row of
    lightcolor.2da for both of that kind, 0 for off."""
    require(NAME.fullmatch(tag) and len(tag) <= client_fixture.RESREF, 'An area\'s tag is a lowercase resref')
    require(light in LIGHTS, 'An area is lit by ' + ', '.join(LIGHTS)); require(len(laid) == width * height, f'{tag}: every cell of the area is laid')
    made = client_fixture.area_documents(tag, [], 1); are = made.pop(tag + '_a.are'); git = made.pop(tag + '_a.git'); template = are['Tile_List']['value'][0]  # a tile's fields, copied for every cell
    cells = []
    for row in range(height):
        for column in range(width):
            cell = copy.deepcopy(template); number, turn = laid[(column, row)]
            cell['Tile_ID'] = field('int', number); cell['Tile_Orientation'] = field('int', turn)
            for kind, key in (('main', 'Tile_MainLight'), ('source', 'Tile_SrcLight')):
                for which in (1, 2):
                    cell[f'{key}{which}'] = field('byte', int((lamps or {}).get(kind, 0)))
            loops = (lamps or {}).get('loops') or ()
            require(len(loops) <= 3, f'A tile has three animation loops, not {len(loops)}')
            for which, on in enumerate(loops, 1):  # a tile's animation loops as the area sets them (all on unless a lamp set says)
                cell[f'Tile_AnimLoop{which}'] = field('byte', int(bool(on)))
            cells.append(cell)
    are.update({'Tileset': field('resref', tileset), 'Width': field('int', width), 'Height': field('int', height), 'Tile_List': field('list', cells),
                'Name': field('cexolocstring', {'0': title}), 'Tag': field('cexostring', tag), 'ResRef': field('resref', tag),
                'Flags': field('dword', 0), 'DayNightCycle': field('byte', 0), 'SkyBox': field('byte', 1), 'FogClipDist': field('float', 9999.0)})
    are.update({key: field(KINDS.get(key, 'dword'), value) for key, value in LIGHTS[light].items()})
    if props:
        git['Placeable List'] = field('list', [prop_fixture.placed(f'{tag}_p{index}', prop['appearance'], prop['position'], prop.get('bearing', SOUTH), **({'static': False, 'state': prop['state']} if prop.get('state') else {}))
                                               for index, prop in enumerate(props)])
    if doors:
        git['Door List'] = field('list', [door(f'{tag}_d{index}', one['row'], one['position'], one['bearing'], one.get('opened', 0)) for index, one in enumerate(doors)])
    return {tag + '.are': are, tag + '.git': git}


def _tools():
    from tools.phenotypes import tool_runtime
    found = {}

    def run(tool, arguments):
        if tool not in found:  # resolved (and its use recorded) once per tool, not once per call
            found[tool] = tool_runtime.tool(tool)
        result = subprocess.run([str(found[tool]), *map(str, arguments)], capture_output=True, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0, tool + ' failed: ' + result.stderr.decode(errors='replace')[-2000:])
        return result.stdout
    return run


def read_area(path, run=None):
    """(width, height, [(tile number, turn)]) of an area file, binary or as JSON."""
    path = Path(path); run = run or _tools()
    are = json.loads(path.read_text(encoding='utf-8-sig') if path.suffix.lower() == '.json' else run('nwn_gff', ['-i', path, '-k', 'json']))  # with or without a byte-order mark
    return are['Width']['value'], are['Height']['value'], [(one['Tile_ID']['value'], one['Tile_Orientation']['value']) for one in are['Tile_List']['value']]


def build(name, areas, shots, output, game, built, *, overlay=None, haks=HAKS, tlk=TLK, start=START, hold=HOLD, arrive=ARRIVE, more=None):
    """Build the review module into the fresh folder `output`: a user folder of its own holding the module, the talk
    table and the built packs (as hard links to those in `built`, copies where the file system has none), with a pack
    of the module's own first in its list holding the files of `overlay`. areas: [{tag, title, tileset, width, height,
    laid, light}]; more: script of the caller's own (`enter_script`). Returns the record envkit's client run takes."""
    require(NAME.fullmatch(name), 'A review\'s name is a lowercase resref of at most 11 characters')
    require(name not in {pack.lower() for pack in haks}, f'A review is not named like a pack it loads ({name}): its own pack would be written over that one')
    root, output, built = Path(game), Path(output).resolve(), Path(built).resolve()
    require((root / 'data').is_dir(), 'The game install folder is required (the one holding data/)')
    require(not output.exists(), 'A review is built into a fresh folder: ' + str(output))
    require(areas and shots and {shot['area'] for shot in shots} <= {area['tag'] for area in areas}, 'Every view is of one of the areas')
    missing = [pack for pack in haks if not (built / f'{pack}.hak').is_file()] + ([] if (built / f'{tlk}.tlk').is_file() else [tlk + '.tlk'])
    require(not missing, f'The built packs are needed in {built}: ' + ', '.join(missing))
    from .apply import KIT_FILES, MADE_FROM, MODELS_FROM, WALK_CUTS  # an overlay's records, for apply: no game files
    laid_over = sorted(path for path in Path(overlay).iterdir() if path.name not in (MADE_FROM, MODELS_FROM, WALK_CUTS, KIT_FILES)) if overlay else []  # refused before anything is made: the folder stays fresh
    for path in laid_over:
        require(path.is_file() and len(path.stem) <= client_fixture.RESREF and path.name == path.name.lower(), 'Overlay files are lowercase resref files: ' + path.name)
        # a set file of bare LF lines crashed the client as the area loaded (a sed copy of srx02.set, 2026-11-27)
        require(path.suffix.lower() != '.set' or b'\n' not in path.read_bytes().replace(b'\r\n', b''), f'{path.name}: a set file has bare LF line ends, which the client falls over on: write it with CRLF')
    user, staged, documents, binary = (output / part for part in ('userdir', 'hak-resources', 'json', 'module'))
    for folder in (user / 'hak', user / 'modules', user / 'tlk', staged, documents, binary):
        folder.mkdir(parents=True)
    run = _tools()
    for pack in haks:
        client_fixture.place(built / f'{pack}.hak', user / 'hak' / f'{pack}.hak')
    shutil.copyfile(built / f'{tlk}.tlk', user / 'tlk' / f'{tlk}.tlk')
    (staged / f'{name}.txt').write_text('Review module of a tileset restyle; files beside this one are shown instead of the packs\' own.\n', encoding='ascii')
    held = []
    for path in laid_over:
        shutil.copyfile(path, staged / path.name); held.append(path.name)
    run('nwn_erf', ['-c', '-f', user / 'hak' / f'{name}.hak', '-e', 'HAK', staged])
    script = binary / f'{name}_en.nss'; script.write_text(enter_script(shots, start, hold, arrive, more), encoding='ascii', newline='\n')
    run('nwn_script_comp', ['--root', root, '--userdirectory', user, '--no-ovr', script])
    require(script.with_suffix('.ncs').is_file(), 'The entry script did not compile')
    made = client_fixture.module_documents(name, list(haks), tlk, tuple(shots[0]['stand'])); ifo = made['module.ifo']
    ifo['Mod_Area_list']['value'] = [{'__struct_id': 6, 'Area_Name': field('resref', area['tag'])} for area in areas]
    ifo['Mod_Entry_Area'] = field('resref', shots[0]['area']); ifo['Mod_Name'] = field('cexolocstring', {'0': 'Tilekit review ' + name})
    for area in areas:
        made.update(area_documents(area['tag'], area['title'], area['tileset'], area['width'], area['height'], area['laid'], area['light'], area.get('lamps'), area.get('props', ()),
                                   area.get('doors', ())))
    for filename, document in made.items():
        path = documents / (filename + '.json'); path.write_text(json.dumps(document), encoding='utf-8')
        run('nwn_gff', ['-i', path, '-o', binary / filename])
    module = user / 'modules' / f'{name}.mod'; run('nwn_erf', ['-c', '-f', module, '-e', 'MOD', binary])
    record = {'name': name, 'userDirectory': str(user), 'module': module.name, 'hak': f'{name}.hak', 'haks': list(haks), 'overlay': held,
              'areas': [{key: area[key] for key in ('tag', 'title', 'tileset', 'width', 'height', 'light')} for area in areas],
              # `hold` is what a capture is timed against; what the views wait before it counts toward the run's start.
              'shots': [shot['label'] for shot in shots], 'start': start + sum(waits(shots, arrive)), 'hold': hold,
              'clientValidated': False}
    (output / 'fixture.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def capture(game, record, folder, *, foreground=60, background=30):
    """Run the client on a built review and capture every view into `folder/captures`. Waits while another game
    client runs. Returns {captures, late, elsewhere}: `late` names the views captured after they had passed, kept as
    -late.png; `elsewhere` those whose area the player had not reached when the view was taken. Neither shows its view.
    foreground, background: the frame rates the client is held to. captures/run.json keeps the run's log lines."""
    checks.wait_for_clients(); captures = Path(folder) / 'captures'
    result = prop_fixture.run(game, record, captures, extra_settings=settings(foreground, background), late_ok=True)
    (captures / 'run.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    return {'captures': result['captures'], 'late': result['late'], 'elsewhere': elsewhere(result['lines'])}


def elsewhere(lines):
    """The views a run's log lines say were taken with the player outside the view's area."""
    return [values['target'] for values in map(client.parse_line, lines) if 'shot' in values and values.get('valid') == '0']


def plan(set_text, spec, *, parts=PARTS, built_area=None, sets=None, table=None):
    """(areas, shots) of a review from a tileset's set file and its review spec: {tileset, fill, block: {width, height,
    patches, runs, groups (`stamped`), crossings, lights, views (which of a crossing's views are taken, as 'x03y03-ne'; all without it),
    near: {distance, pitch, views}, eye: {crossings (the block's without it), height, distance, turns, pitches} (`eye_shots`), lamps: [{name, main, source, lights}] (the block again with
    every tile's own lights on, `area_documents`; views `lamp-<name>-<light>`)}, grid: {across, lights}, area: {step, lights},
    shared: {lights, tilesets: {tileset: {models, fill, lights}}, placeables: {lights, groups: [{name, models, lights, and
    the `PROP_GROUP` keys}]}}}. built_area: (width, height, laid)
    of an area someone built (`read_area`), without which the `area` part is left out, as is a part the spec lacks.
    The grid holds every tile that is not an envkit building's; the block is laid only with tiles outside groups.
    `shared` lays what else draws the restyled textures: each other tileset's tiles of `models` in a row on its plain
    tile (sets: {tileset: its set file's text}), and the placeables of each group stood in rows on this tileset's fill,
    a group of about one size to an area (table: the text of placeables.2da, whose rows place them)."""
    from . import inventory
    laid = inventory.read_set(set_text); tiles = {tile['number']: tile for tile in laid['tiles']}; tileset = spec['tileset']
    fill = spec['fill'] if 'fill' in spec else plain(laid)  # the set's plain tile, as for the shared tilesets: tile 0 is that in dgt04 alone
    require(all(part in PARTS for part in parts), 'A review\'s parts are ' + ', '.join(PARTS))
    require(fill in tiles, f'The fill tile {fill} is no tile of {tileset}')
    envkit = {number for number, tile in tiles.items() if tile['model'].startswith('ek_')}
    grouped = {number for group in laid['groups'] for number in group['tiles']}
    areas, shots = [], []

    def add(tag, title, width, height, cells, light, lamps=None, of=None, props=()):
        require(tag not in {area['tag'] for area in areas}, f'Two areas would be named {tag}: an area is named by the first letters of its lighting ({light}) and of its lamp set, so two of either begin with the same letter')
        areas.append({'tag': tag, 'title': title, 'tileset': of or tileset, 'width': width, 'height': height, 'laid': cells, 'light': light,
                      **({'lamps': lamps} if lamps else {}), **({'props': list(props)} if props else {})})

    if 'block' in parts and 'block' in spec:
        block = spec['block']
        # Of the four views of each crossing, some stand inside a roof or face a wall: a spec names the ones worth taking.
        # A view is the label's last two parts (x03y03-ne), however many parts its prefix has (lamp-main-night).
        chosen = lambda made, views: [shot for shot in made if not views or '-'.join(shot['label'].rsplit('-', 2)[-2:]) in views]
        eye = block.get('eye'); require(eye is None or set(eye) <= {'crossings', 'places', *EYE}, 'The eye views of a block take crossings, places, ' + ', '.join(EYE))
        eyes = lambda tag, prefix: eye_shots(tag, prefix, [tuple(cell) for cell in eye.get('crossings', block['crossings'])], **{key: eye[key] for key in (*EYE, 'places') if key in eye}) if eye is not None else []
        cells = solve(tiles, laid['default'], block['width'], block['height'], block['patches'], block.get('runs', ()), avoid=grouped | envkit)
        if block.get('groups'):  # whole buildings, as a builder lays them
            cells = stamped(cells, tiles, set_text, block['groups'], block['width'], block['height'])
        for light in block['lights']:
            tag = 'tkb' + light[0]; add(tag, f'Block, {light}', block['width'], block['height'], cells, light)
            shots += chosen(corner_shots(tag, f'block-{light}', [tuple(cell) for cell in block['crossings']]), block.get('views'))
            if 'near' in block:  # the same views from where a player's camera stands: a texture is judged there, a district from afar
                shots += chosen(corner_shots(tag, f'near-{light}', [tuple(cell) for cell in block['crossings']], distance=block['near']['distance'], pitch=block['near']['pitch']), block['near'].get('views'))
            shots += eyes(tag, f'eye-{light}')
        for lamps in block.get('lamps', ()):  # the block's own lights switched on: what a builder gets from a tile's light settings
            for light in lamps['lights']:
                tag = f'tkl{lamps["name"][0]}{light[0]}'; add(tag, f'Block, {light}, {lamps["name"]} lights', block['width'], block['height'], cells, light, {'main': lamps.get('main', 0), 'source': lamps.get('source', 0), **({'loops': lamps['loops']} if 'loops' in lamps else {})})
                shots += chosen(corner_shots(tag, f'lamp-{lamps["name"]}-{light}', [tuple(cell) for cell in block['crossings']]), block.get('views'))
                if 'near' in block:
                    shots += chosen(corner_shots(tag, f'lampnear-{lamps["name"]}-{light}', [tuple(cell) for cell in block['crossings']], distance=block['near']['distance'], pitch=block['near']['pitch']), block['near'].get('views'))
                shots += eyes(tag, f'lampeye-{lamps["name"]}-{light}')
    if 'grid' in parts and 'grid' in spec:
        width, height, cells, rows = grid([number for number in sorted(tiles) if number not in envkit], fill, spec['grid'].get('across', 32))
        for light in spec['grid']['lights']:
            tag = 'tkg' + light[0]; add(tag, f'Every tile, {light}', width, height, cells, light); shots += grid_shots(tag, f'grid-{light}', width, rows)
    if 'area' in parts and 'area' in spec and built_area is not None:
        width, height, cells = built_area
        unknown = sorted({number for number, _ in cells} - set(tiles))
        require(not unknown, 'The built area has tiles this set does not: ' + ', '.join(map(str, unknown[:8])))
        wrong = disagreements(width, cells, tiles); require(not wrong, 'The built area does not agree with this set: ' + '; '.join(wrong[:4]))
        cells = {(index % width, index // width): one for index, one in enumerate(cells)}
        for light in spec['area']['lights']:
            tag = 'tka' + light[0]; add(tag, f'Built area, {light}', width, height, cells, light)
            shots += lattice_shots(tag, f'area-{light}', width, height, step=spec['area'].get('step', 4))
    if 'shared' in parts and 'shared' in spec:
        shared = spec['shared']
        for other, how in sorted(shared.get('tilesets', {}).items()):
            require(sets and other in sets, f'The review needs the set file of {other}')
            theirs = inventory.read_set(sets[other]); wanted = {model.lower() for model in how['models']}
            numbers = [tile['number'] for tile in theirs['tiles'] if tile['model'] in wanted]
            missing = sorted(wanted - {tile['model'] for tile in theirs['tiles']}); require(not missing, f'No tile of {other} is ' + ', '.join(missing))
            filler = how['fill'] if 'fill' in how else plain(theirs)
            require(filler in {tile['number'] for tile in theirs['tiles']}, f'The fill tile {filler} is no tile of {other}')
            width, height, cells, rows = grid(numbers, filler, max(4, min(len(numbers), 32)))  # an area four tiles wide at least
            for light in how.get('lights', shared['lights']):
                tag = f'tk{other}{light[0]}'; add(tag, f'{other} tiles, {light}', width, height, cells, light, of=other)
                shots += grid_shots(tag, f'{other}-{light}', min(width, len(numbers)), rows)
        if shared.get('placeables'):
            from tools.envkit import placeables
            require(table, 'The review needs placeables.2da to stand the placeables'); appearance = placeables.rows(table)
            for number, group in enumerate(shared['placeables']['groups']):  # each size of placeable in an area of its own, spaced and seen to suit it
                how = {**PROP_GROUP, **{key: value for key, value in group.items() if key in PROP_GROUP}}
                width, height, props, rows = prop_rows([model.lower() for model in group['models']], appearance, across=how['across'], spacing=how['spacing'],
                                                       apart=how['apart'], bearing=how['bearing'], state=how['state'])
                cells = {(column, row): (fill, 0) for column in range(width) for row in range(height)}
                for light in group.get('lights', shared['placeables'].get('lights', shared['lights'])):
                    tag = f'tkp{number}{light[0]}'; add(tag, f'Placeables, {group["name"]}, {light}', width, height, cells, light, props=props)
                    shots += prop_shots(tag, f'props-{group["name"]}-{light}', rows, across=how['across'], spacing=how['spacing'], apart=how['apart'],
                                        distance=how['distance'], pitch=how['pitch'])
    require(areas, 'Nothing to review: no part of the spec was laid')
    return areas, shots


def sheet(pictures, output, *, columns=4, wide=480):
    """One picture of many captures, each under its name. Returns how many it shows."""
    from PIL import Image, ImageDraw
    pictures = [Path(path) for path in pictures]; require(pictures, 'No captures to show')
    cells, label = [], 16
    for path in pictures:
        with Image.open(path) as picture:
            picture = picture.convert('RGB'); picture.thumbnail((wide, wide))
        cell = Image.new('RGB', (wide, picture.height + label), (255, 255, 255)); cell.paste(picture, (0, label))
        ImageDraw.Draw(cell).text((4, 2), path.stem, fill=(0, 0, 0)); cells.append(cell)
    high = max(cell.height for cell in cells); rows = -(-len(cells) // columns)
    page = Image.new('RGB', (wide * columns, high * rows), (255, 255, 255))
    for index, cell in enumerate(cells):
        page.paste(cell, (index % columns * wide, index // columns * high))
    Path(output).parent.mkdir(parents=True, exist_ok=True); page.save(output, quality=88)
    return len(cells)


def sheets(folder, *, most=48):
    """Contact sheets of a review's captures in `folder/sheets`: one for each part and lighting (block-day, ...), in
    pages of `most` views. Returns {sheet name: views}."""
    folder = Path(folder); groups = {}

    def order(path):  # by the view's number, not its name: shot-100 comes after shot-99
        number = path.stem.split('-')[1]
        return (int(number) if number.isdigit() else 0, path.name)
    def group(path):  # the label up to its lighting: block-day, grid-night, lamp-main-night
        parts = path.stem.split('-')[2:]; lit = next((index for index, part in enumerate(parts) if part in LIGHTS), 1)
        return '-'.join(parts[:lit + 1])
    for path in sorted((folder / 'captures').glob('shot-*.png'), key=order):
        groups.setdefault(group(path), []).append(path)
    made = {}
    for name, pictures in groups.items():
        for start in range(0, len(pictures), most):
            page = name + (f'-{start // most + 1}' if len(pictures) > most else '')
            made[page + '.jpg'] = sheet(pictures[start:start + most], folder / 'sheets' / (page + '.jpg'), columns=6 if len(pictures) > 24 else 4)
    return made
