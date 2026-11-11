"""A building as a group of tiles: tile models cut from one mesh, a walkmesh found from its shape, and its place in a
tileset's set file and palette.

A tile is 10 metres square with its origin at its middle. A building wider than that is a group: its mesh is shared
out by where each triangle lies, every tile gets its own ground and its own walkmesh, and the set file lists the tiles
from the south-west corner eastwards, row by row northwards (read off Modern Exterior's four-way street group, whose
kerbs sit in the outer corner of each tile, 2026-11-11).

The walkmesh is a grid. A cell is closed where the mesh stands between knee and head height, so a sign or canopy
overhead closes nothing. The largest closed mass is the building: its cells, and upright faces round its outline up to
its roof, are Obscuring, which stops both movement and sight, as the upright faces of the stock tiles do. Smaller
closed things (bollards, bins) are Nonwalk: in the way, but seen over. Where the mesh has a slab, the walkmesh rises
onto it over the slab's outermost cells."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import convert, require

SIZE = 10.0
CELLS = 20  # walk cells across a tile: half a metre each
FINE = 4  # samples across a walk cell
STONE, OBSCURING, NONWALK = 4, 2, 7  # rows of surfacemat.2da
KNEE, HEAD, STEP = 0.45, 2.2, 0.05
TILE_KEYS = ('Model', 'WalkMesh', 'TopLeft', 'TopLeftHeight', 'TopRight', 'TopRightHeight', 'BottomLeft', 'BottomLeftHeight', 'BottomRight',
             'BottomRightHeight', 'Top', 'Right', 'Bottom', 'Left', 'MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1',
             'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds', 'PathNode', 'Orientation', 'VisibilityNode', 'VisibilityOrientation', 'ImageMap2D')


def layout(vertices):
    """(rows, columns, south-west corner) of the group that holds the model centred."""
    low, high = vertices.min(0), vertices.max(0)
    columns, rows = (max(1, int(np.ceil((high[axis] - low[axis]) / SIZE - 1e-6))) for axis in (0, 1))
    middle = (low[:2] + high[:2]) / 2
    return rows, columns, middle - np.array([columns, rows]) * SIZE / 2


def scatter(vertices, faces, spacing=0.04, seed=0):
    """Points spread evenly over the mesh's surface, about `spacing` apart: upright faces show as well as level ones,
    which a view from above would miss."""
    corners = vertices[faces]; area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) / 2
    count = np.maximum(1, np.ceil(area / spacing ** 2).astype(int)); pick = np.repeat(np.arange(len(faces)), count)
    weights = np.random.default_rng(seed).dirichlet((1, 1, 1), len(pick))
    return (corners[pick] * weights[:, :, None]).sum(1)


def _outside(open_cells):
    """The open cells that can be reached from the rim without crossing a closed one."""
    reached = np.zeros_like(open_cells); reached[0], reached[-1], reached[:, 0], reached[:, -1] = open_cells[0], open_cells[-1], open_cells[:, 0], open_cells[:, -1]
    while True:
        spread = reached.copy()
        spread[1:] |= reached[:-1]; spread[:-1] |= reached[1:]; spread[:, 1:] |= reached[:, :-1]; spread[:, :-1] |= reached[:, 1:]
        spread &= open_cells
        if (spread == reached).all():
            return reached
        reached = spread


def _masses(closed):
    """Label each joined mass of closed cells: (labels from 1, count)."""
    labels = np.zeros(closed.shape, int); count = 0
    for start in zip(*np.nonzero(closed)):
        if labels[start]:
            continue
        count += 1; labels[start] = count; stack = [start]
        while stack:
            row, column = stack.pop()
            for near in ((row + 1, column), (row - 1, column), (row, column + 1), (row, column - 1)):
                if 0 <= near[0] < closed.shape[0] and 0 <= near[1] < closed.shape[1] and closed[near] and not labels[near]:
                    labels[near] = count; stack.append(near)
    return labels, count


def survey(vertices, faces, rows, columns, corner):
    """The group's walk cells, [row, column] from the south-west: {material, raised, slab, roof}.

    material: Stone where one can walk, Obscuring for the building, Nonwalk for the lesser things in the way.
    raised: the cell lies on the slab (or inside what stands on it). slab: the slab's height. roof: the building's."""
    points = scatter(vertices, faces); across = np.array([columns, rows]) * CELLS * FINE; step = SIZE / CELLS / FINE
    place = np.clip(((points[:, :2] - corner) / step).astype(int), 0, across - 1)
    standing = (points[:, 2] > KNEE) & (points[:, 2] < HEAD)
    solid = np.zeros((across[1], across[0]), bool); solid[place[standing, 1], place[standing, 0]] = True
    solid = ~_outside(~solid)  # what the walls enclose is closed too
    low = np.zeros(solid.shape); under = points[:, 2] <= KNEE
    np.maximum.at(low, (place[under, 1], place[under, 0]), points[under, 2])
    on_slab = ~_outside(~(low > STEP))  # and what the slab's rim encloses stands on it
    slab = float(np.median(low[low > STEP])) if (low > STEP).any() else 0.0
    cells = lambda fine: fine.reshape(rows * CELLS, FINE, columns * CELLS, FINE).mean((1, 3))
    closed = cells(solid) >= 0.25; raised = cells(on_slab) >= 0.5
    labels, count = _masses(closed); material = np.full(closed.shape, STONE)
    if count:
        sizes = np.bincount(labels.ravel())[1:]; building = int(sizes.argmax()) + 1
        material[closed] = NONWALK; material[labels == building] = OBSCURING
    require(not (closed[0].any() or closed[-1].any() or closed[:, 0].any() or closed[:, -1].any()) and not (raised[0].any() or raised[-1].any() or raised[:, 0].any() or raised[:, -1].any()),
            'The model reaches the edge of its tiles: the group leaves no ground around it')
    return {'material': material, 'raised': raised, 'slab': slab, 'roof': float(vertices[:, 2].max())}


def walkmesh(found, row, column):
    """(vertices, faces with a material each) of one tile's walkmesh, in the tile's own space."""
    material, raised = found['material'], found['raised']; rows, columns = material.shape
    first_row, first_column = row * CELLS, column * CELLS
    lift = np.zeros((CELLS + 1, CELLS + 1))
    for y in range(CELLS + 1):
        for x in range(CELLS + 1):
            around = [raised[r, c] for r in (first_row + y - 1, first_row + y) for c in (first_column + x - 1, first_column + x) if 0 <= r < rows and 0 <= c < columns]
            lift[y, x] = found['slab'] if len(around) == 4 and all(around) else 0.0  # the rim of the slab is the ramp onto it
    side = np.linspace(-SIZE / 2, SIZE / 2, CELLS + 1)
    vertices = [[side[x], side[y], lift[y, x]] for y in range(CELLS + 1) for x in range(CELLS + 1)]
    at = lambda y, x: y * (CELLS + 1) + x; faces = []
    walls = lambda r, c: 0 <= r < rows and 0 <= c < columns and material[r, c] == OBSCURING
    for y in range(CELLS):
        for x in range(CELLS):
            kind = int(material[first_row + y, first_column + x])
            faces += [[at(y + 1, x), at(y, x), at(y + 1, x + 1), kind], [at(y + 1, x + 1), at(y, x), at(y, x + 1), kind]]
            if kind != OBSCURING:
                continue
            # An upright face on each side of the building that looks out on open ground, from the ground to the roof.
            for (dy, dx), (a, b) in (((0, -1), ((y + 1, x), (y, x))), ((0, 1), ((y, x + 1), (y + 1, x + 1))), ((-1, 0), ((y, x), (y, x + 1))), ((1, 0), ((y + 1, x + 1), (y + 1, x)))):
                if walls(first_row + y + dy, first_column + x + dx):
                    continue
                base = len(vertices); vertices += [[side[a[1]], side[a[0]], found['roof']], [side[b[1]], side[b[0]], found['roof']]]
                faces += [[at(*a), at(*b), base + 1, OBSCURING], [at(*a), base + 1, base, OBSCURING]]
    return np.array(vertices), np.array(faces)


def tree(vertices, faces):
    """The walkmesh's box tree as the model file lists it: each box, then its two halves in turn; a box holding one
    face names it, any other says -1."""
    corners = vertices[faces[:, :3]]; low, high, middle = corners.min(1), corners.max(1), corners.mean(1); lines = []

    def box(members):
        least, most = low[members].min(0), high[members].max(0)
        lines.append([*least, *most, int(members[0]) if len(members) == 1 else -1])
        if len(members) == 1:
            return
        axis = int((most - least).argmax()); order = members[np.argsort(middle[members, axis], kind='stable')]
        left = order[middle[order, axis] < middle[members, axis].mean()]
        if not 0 < len(left) < len(order):
            left = order[:len(order) // 2]
        box(left); box(order[len(left):])

    import sys
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    box(np.arange(len(faces)))
    return lines


def _walk_node(name, parent, vertices, faces):
    boxes = tree(vertices, faces)
    lines = [f'node aabb {name}_wm', f'  parent {parent}', '  position 0.0 0.0 0.0', '  orientation 1.0 0.0 0.0 0.0', '  wirecolor 0.03 0.03 0.53',
             '  ambient 1.0 1.0 1.0', '  diffuse 1.0 1.0 1.0', '  specular 0.0 0.0 0.0', '  shininess 0', '  bitmap NULL', f'  verts {len(vertices)}']
    lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in vertices.tolist()] + [f'  faces {len(faces)}']
    lines += [f'    {a} {b} {c}  1  0 0 0  {kind}' for a, b, c, kind in faces.tolist()]
    form = lambda b: ' '.join(f'{value:.5f}' for value in b[:6]) + f' {b[6]}'
    return lines + ['  aabb ' + form(boxes[0])] + ['    ' + form(b) for b in boxes[1:]] + ['endnode']


def model_text(name, parts, material, ground, cards, walk):
    """One tile's ASCII model. parts: [(vertices, normals, uvs, faces)] of the building, in the tile's space. ground: the
    texture of the ten-metre square under it, laid twice across the tile as the plain tiles lay theirs."""
    require(len(name) <= 16 and name == name.lower() and name.replace('_', '').isalnum(), 'A tile model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', 'setanimationscale 1.0',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    common = ['  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1', '  render 1', '  shadow 0', '  rotatetexture 0', '  tilefade 0']
    half = SIZE / 2
    lines += [f'node trimesh {name}_g', f'  parent {name}', *common, f'  bitmap {ground}', '  verts 4', f'    {-half} {-half} 0', f'    {half} {-half} 0',
              f'    {-half} {half} 0', f'    {half} {half} 0', '  tverts 4', '    0 2 0', '    2 2 0', '    0 0 0', '    2 0 0', '  normals 4', *['    0 0 1'] * 4,
              '  faces 2', '    2 0 3 1 2 0 3 1', '    3 0 1 1 3 0 1 1', 'endnode']
    number = 0
    for vertices, normals, uvs, faces in parts:
        for used, part in convert.split(faces):
            lines += [f'node trimesh {name}_m{number}', f'  parent {name}', *common, f'  bitmap {material}', f'  verts {len(used)}']; number += 1
            lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in vertices[used].tolist()]
            lines += [f'  tverts {len(used)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in uvs[used].tolist()]
            lines += [f'  normals {len(used)}'] + [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in normals[used].tolist()]
            lines += [f'  faces {len(part)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in part.tolist()] + ['endnode']
    for index, card in enumerate(cards):
        lines += [f'node trimesh {name}_halo{index}', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {material}_h', '  render 1', '  shadow 0', '  rotatetexture 0', '  tilefade 0', '  transparencyhint 1', '  verts 4']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for (x, y, z), _ in card] + ['  tverts 4'] + [f'    {u:.5f} {v:.5f} 0' for _, (u, v) in card]
        lines += ['  normals 4'] + ['    0 1 0'] * 4 + ['  faces 2', '    0 1 2 1 0 1 2 1', '    0 2 3 1 0 2 3 1', 'endnode']
    return '\n'.join(lines + _walk_node(name, name, *walk) + [f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


def walk_text(name, walk):
    return '\n'.join([f'beginwalkmeshgeom {name}', *_walk_node(name, name, *walk), f'endwalkmeshgeom {name}']) + '\n'


def share_cards(cards, rows, columns, corner):
    """{(row, column): [card]}: each halo card cut along the tile lines it crosses, in each tile's own space."""
    shared = {}
    for card in cards:
        (left, depth, bottom), (u_left, v_bottom) = card[0]; (right, _, _), (u_right, _) = card[1]; (_, _, top), (_, v_top) = card[2]
        row = int(np.clip((depth - corner[1]) // SIZE, 0, rows - 1))
        for column in range(columns):
            west, east = corner[0] + column * SIZE, corner[0] + (column + 1) * SIZE
            near, far = min(left, east), max(right, west)  # the card runs from its left (high x) to its right (low x)
            if near - far < 1e-6:
                continue
            u = lambda x: u_left + (left - x) / (left - right) * (u_right - u_left)
            centre = np.array([west + SIZE / 2, corner[1] + (row + 0.5) * SIZE, 0.0])
            piece = [((near, depth, bottom), (u(near), v_bottom)), ((far, depth, bottom), (u(far), v_bottom)),
                     ((far, depth, top), (u(far), v_top)), ((near, depth, top), (u(near), v_top))]
            shared.setdefault((row, column), []).append([(tuple(np.array(place) - centre), corner_uv) for place, corner_uv in piece])
    return shared


def group(name, made, folder, *, ground):
    """Write the tile models and walkmeshes of a finished model (`convert.shape`) into `folder`; returns
    {rows, columns, tiles: [{model, row, column, faces, walkFaces}]} with the tiles in the set file's order."""
    require(len(name) <= convert.TILE_NAME_LENGTH, 'A tile group name leaves four characters for the tile: ' + name)
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    vertices, normals, uvs, faces = made['vertices'], made['normals'], made['uvs'], made['faces']
    rows, columns, corner = layout(vertices); found = survey(vertices, faces, rows, columns, corner)
    middle = vertices[faces].mean(1); home = np.clip(((middle[:, :2] - corner) // SIZE).astype(int), 0, [columns - 1, rows - 1])
    cards = share_cards(made['card'][1] if made['card'] else [], rows, columns, corner); tiles = []
    for row in range(rows):
        for column in range(columns):
            model = f'{name}_t{row}{column}'; centre = np.array([corner[0] + (column + 0.5) * SIZE, corner[1] + (row + 0.5) * SIZE, 0.0])
            mine = faces[(home[:, 0] == column) & (home[:, 1] == row)]; used, local = np.unique(mine, return_inverse=True)
            parts = [(vertices[used] - centre, normals[used], uvs[used], local.reshape(-1, 3))] if len(mine) else []
            walk = walkmesh(found, row, column)
            (folder / f'{model}.mdl').write_text(model_text(model, parts, name, ground, cards.get((row, column), []), walk), encoding='cp1252', newline='\n')
            (folder / f'{model}.wok').write_text(walk_text(model, walk), encoding='cp1252', newline='\n')
            tiles.append({'model': model, 'row': row, 'column': column, 'faces': int(len(mine)), 'walkFaces': int(len(walk[1])),
                          'closedCells': int((found['material'][row * CELLS:(row + 1) * CELLS, column * CELLS:(column + 1) * CELLS] != STONE).sum())})
    return {'rows': rows, 'columns': columns, 'slab': round(found['slab'], 3), 'roof': round(found['roof'], 3), 'tiles': tiles}


def compile_tiles(sources, output):
    """Compile tile models with the pinned cleanmodels into `output`; returns the compiled paths. (armorkit's compile
    reads each model back with a reader that knows no walkmesh node, so the tiles are checked here by size alone.)"""
    from ..armorkit import toolchain
    sources, output = [Path(source) for source in sources], Path(output); output.mkdir(parents=True, exist_ok=True)
    require(all(source.parent.resolve() != output.resolve() for source in sources), 'Compile into a folder other than the sources\'')
    tool = toolchain.cleanmodels(); targets = []
    for source in sources:
        target = output / source.name; target.unlink(missing_ok=True)
        result = subprocess.run([tool['path'], 'compile', '--overwrite', '--json', str(source), str(target)], capture_output=True, text=True, timeout=600,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0 and target.is_file() and target.read_bytes()[:4] == b'\0\0\0\0',
                f'{source.name} did not compile: {(result.stdout + result.stderr)[-600:]}')
        targets.append(target)
    return targets


# One closed corner, as Modern Exterior's own tile with a building on one corner states it (H, turned 270 with the
# building top left): the turn that puts the closed corner where the building is in each tile of a group.
CORNER_TURN = {('Bottom', 'Left'): 0, ('Bottom', 'Right'): 90, ('Top', 'Right'): 180, ('Top', 'Left'): 270}


def tile_records(made, terrain):
    """The set file's record of each tile, in order: all four corners `terrain` at height 0, no crossers, no lights or
    doors. In a 2 by 2 group each tile has the building on its inner corner, and says so for pathfinding. Any other
    group is recorded only where its tiles are open: an open tile's path runs through its middle, which is wrong for a
    tile with something standing on it, and no other shape has had its path node worked out."""
    rows, columns = made['rows'], made['columns']; records = []
    for tile in made['tiles']:
        if rows == columns == 2:
            node, turn = 'H', CORNER_TURN[('Top' if tile['row'] == 0 else 'Bottom', 'Right' if tile['column'] == 0 else 'Left')]
        else:
            require(tile['closedCells'] == 0, 'Only a 2 by 2 group has the pathfinding of its closed tiles worked out')
            node, turn = 'A', 0
        values = {'Model': tile['model'], 'WalkMesh': 'msb01', **{corner: terrain for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')},
                  **{corner + 'Height': 0 for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')}, 'Top': '', 'Right': '', 'Bottom': '', 'Left': '',
                  **{key: 0 for key in ('MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1', 'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds')},
                  'PathNode': node, 'Orientation': turn, 'VisibilityNode': node, 'VisibilityOrientation': turn, 'ImageMap2D': ''}
        records.append([(key, values[key]) for key in TILE_KEYS])
    return records


def register(text, records, group_name, rows, columns):
    """The set file's text with the tiles and their group appended; returns (text, first tile, group number). No tile or
    group already there is renumbered. The file's own line ends are kept."""
    end = '\r\n' if '\r\n' in text else '\n'
    tiles = re.search(r'(?m)^\[TILES\]\r?\nCount=(\d+)', text); groups = re.search(r'(?m)^\[GROUPS\]\r?\nCount=(\d+)', text)
    require(tiles and groups and tiles.start() < groups.start(), 'The set file has no tiles and groups to add to')
    first, number = int(tiles.group(1)), int(groups.group(1))
    require(f'[TILE{first - 1}]' in text and f'[TILE{first}]' not in text and f'[GROUP{number}]' not in text, 'The set file\'s counts do not match its records')
    for record in records:
        require(not re.search(r'(?mi)^Model=' + re.escape(dict(record)['Model']) + r'\r?$', text), 'The set file already lists ' + dict(record)['Model'])
    require(not re.search(r'(?m)^Name=' + re.escape(group_name) + r'\r?$', text), 'The set file already has a group named ' + group_name)
    blocks = ''.join(f'[TILE{first + index}]{end}' + ''.join(f'{key}={value}{end}' for key, value in record) + end for index, record in enumerate(records))
    made = f'[GROUP{number}]{end}Name={group_name}{end}Rows={rows}{end}Columns={columns}{end}' + ''.join(f'Tile{index}={first + index}{end}' for index in range(len(records)))
    text = text[:groups.start()] + blocks + text[groups.start():]
    text = re.sub(r'(?m)^(\[TILES\]\r?\nCount=)\d+', lambda m: m.group(1) + str(first + len(records)), text, count=1)
    text = re.sub(r'(?m)^(\[GROUPS\]\r?\nCount=)\d+', lambda m: m.group(1) + str(number + 1), text, count=1)
    return text.rstrip('\r\n') + end + end + made, first, number


def terrains(text):
    """The terrain names a set file declares."""
    return re.findall(r'(?m)^\[TERRAIN\d+\]\r?\nName=([^\r\n]+)', text)


def palette(document, label, model, single=False):
    """The palette (as nwn_gff's JSON) with the group listed where the Toolset's palettes keep its kind: a group of
    one tile under Features, a larger one under Groups. `model` is its first tile's."""
    groups = [node for node in document['MAIN']['value'] if node['ID']['value'] == (0 if single else 1)]
    require(len(groups) == 1, 'The palette has no ' + ('Features' if single else 'Groups') + ' list')
    rows = groups[0]['LIST']['value']
    require(all(row['RESREF']['value'].lower() != model for row in rows), 'The palette already lists ' + model)
    rows.append({'__struct_id': 0, 'NAME': {'type': 'cexostring', 'value': label}, 'RESREF': {'type': 'resref', 'value': model}})
    return document


def prepare(set_path, palette_path, made, *, terrain, group_name, label):
    """Work out what installing a built group into a tileset will write, writing nothing: every refusal (a terrain the
    tileset lacks, a tile or group already there, a palette that cannot be read) comes before any file changes."""
    from ..phenotypes import tool_runtime
    set_path, palette_path = Path(set_path), Path(palette_path); text = set_path.read_bytes().decode('cp1252')
    require(terrain in terrains(text), f'{set_path.name} has no terrain named {terrain}: ' + ', '.join(terrains(text)))
    text, first, number = register(text, tile_records(made, terrain), group_name, made['rows'], made['columns'])
    tool = str(tool_runtime.tool('nwn_gff'))
    read = subprocess.run([tool, '-i', str(palette_path), '-k', 'json'], capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    require(read.returncode == 0, 'The palette could not be read: ' + read.stderr.decode(errors='replace')[-400:])
    document = palette(json.loads(read.stdout), label, made['tiles'][0]['model'], single=len(made['tiles']) == 1)
    return {'tool': tool, 'set': set_path, 'text': text, 'palette': palette_path, 'document': document, 'firstTile': first, 'group': number}


def commit(prepared):
    """Write what `prepare` worked out: the palette, then the set file; returns {firstTile, group}."""
    with tempfile.TemporaryDirectory() as folder:  # the JSON never lies in the pack, where a stopped run would leave it
        staged = Path(folder) / 'palette.json'; staged.write_text(json.dumps(prepared['document']), encoding='utf-8')
        wrote = subprocess.run([prepared['tool'], '-i', str(staged), '-l', 'json', '-o', str(prepared['palette']), '-k', 'gff'], capture_output=True, timeout=120,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(wrote.returncode == 0, 'The palette could not be written: ' + wrote.stderr.decode(errors='replace')[-400:])
    prepared['set'].write_bytes(prepared['text'].encode('cp1252'))
    return {'firstTile': prepared['firstTile'], 'group': prepared['group']}


def install(set_path, palette_path, made, *, terrain, group_name, label):
    """Append a built group to one tileset's set file and palette in place; returns {firstTile, group}."""
    return commit(prepare(set_path, palette_path, made, terrain=terrain, group_name=group_name, label=label))
