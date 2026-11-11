"""A building as a group of tiles: tile models cut from one mesh, a walkmesh found from its shape, and its place in a
tileset's set file and palette.

A tile is 10 metres square with its origin at its middle. A building wider than that is a group: its mesh is shared
out by where each triangle lies, every tile gets its own ground and its own walkmesh, and the set file lists the tiles
from the south-west corner eastwards, row by row northwards (read off Modern Exterior's four-way street group, whose
kerbs sit in the outer corner of each tile, 2026-11-11).

The walkmesh is surveyed on a grid of quarter-metre cells and drawn with grid lines only where the ground changes:
a stretch of open ground is two large faces, as it is in the stock tiles, and the outline of what stands on it is
followed to the cell (the stock tiles of these tilesets have some 20 to 70 walk faces each and at most 500; a face
for every cell would be 3,200 a tile). The lines run through the whole group, so neighbouring tiles meet corner to
corner. A cell is closed where the mesh stands between knee and head height, so a sign or canopy overhead closes
nothing. The largest closed mass is the building: its cells, and upright faces round its outline up to
its roof, are Obscuring, which stops both movement and sight, as the upright faces of the stock tiles do. Smaller
closed things (bollards, bins) are Nonwalk: in the way, but seen over; so is whatever joins the building without
reaching eye height, such as bins standing against its wall. Where the mesh has a slab, the walkmesh rises
onto it over the slab's outermost half metre.

A tile also carries what the stock tiles carry (read off Modern Exterior's and the stock city's tiles, 2026-11-11): a
32-pixel picture for the area map, two main lights a builder colours in the Toolset, the `day`, `night`, `day2night`
and `night2day` animations the game plays as the hour turns (here they fade the halo sheets, which belong to the
night), `tilefade` on what stands above a stated height so the game can hide it when a character is behind, and a
door: a line in the set file from which the Toolset makes the door when the tile is painted."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import convert, game_bytes, require

SIZE = 10.0
MINIMAP = 32  # pixels across a tile's picture on the area map
CAP = 'ek_black'  # the texture of the lid that closes a building whose top is hidden
LIGHT_HEIGHT = 4.0
CELLS = 40  # walk cells across a tile: a quarter metre each
FINE = 2  # samples across a walk cell
RAMP = 2  # cells from the slab's edge to its full height: the half metre a character steps up over
STONE, OBSCURING, NONWALK = 4, 2, 7  # rows of surfacemat.2da
KNEE, EYE, HEAD, STEP = 0.45, 1.4, 2.2, 0.05
TILE_KEYS = ('Model', 'WalkMesh', 'TopLeft', 'TopLeftHeight', 'TopRight', 'TopRightHeight', 'BottomLeft', 'BottomLeftHeight', 'BottomRight',
             'BottomRightHeight', 'Top', 'Right', 'Bottom', 'Left', 'MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1',
             'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds', 'PathNode', 'Orientation', 'VisibilityNode', 'VisibilityOrientation', 'ImageMap2D')


def layout(vertices):
    """(rows, columns, south-west corner) of the group that holds the model centred."""
    low, high = vertices.min(0), vertices.max(0)
    columns, rows = (max(1, int(np.ceil((high[axis] - low[axis]) / SIZE - 1e-6))) for axis in (0, 1))
    middle = (low[:2] + high[:2]) / 2
    return rows, columns, middle - np.array([columns, rows]) * SIZE / 2


def scatter(vertices, faces, spacing=0.04, seed=0, *, sources=False):
    """Points spread evenly over the mesh's surface, about `spacing` apart: upright faces show as well as level ones,
    which a view from above would miss. With `sources`, also each point's face and its weights on that face's corners."""
    corners = vertices[faces]; area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) / 2
    count = np.maximum(1, np.ceil(area / spacing ** 2).astype(int)); pick = np.repeat(np.arange(len(faces)), count)
    weights = np.random.default_rng(seed).dirichlet((1, 1, 1), len(pick))
    points = (corners[pick] * weights[:, :, None]).sum(1)
    return (points, pick, weights) if sources else points


def minimaps(vertices, uvs, faces, colour, rows, columns, corner, ground):
    """{(row, column): (MINIMAP, MINIMAP, 3) picture, 0-1}: each tile seen from straight above, north at the top, as
    the area map shows it. `colour` is the model's colour texture (0-1, any size); `ground` the colour round the model."""
    points, pick, weights = scatter(vertices, faces, spacing=SIZE / MINIMAP / 3, sources=True)
    size = np.array([colour.shape[1], colour.shape[0]])
    texel = np.clip(((uvs[faces[pick]] * weights[:, :, None]).sum(1) * size).astype(int), 0, size - 1)
    across = np.array([columns, rows]) * MINIMAP
    place = np.clip(((points[:, :2] - corner) / SIZE * MINIMAP).astype(int), 0, across - 1)
    picture = np.tile(np.asarray(ground, float), (across[1], across[0], 1)); count = np.zeros((across[1], across[0]))
    # What shows from above is the highest thing in each pixel: the mean colour of the points in its top 30 cm.
    top = np.full((across[1], across[0]), -np.inf); np.maximum.at(top, (place[:, 1], place[:, 0]), points[:, 2])
    upper = points[:, 2] >= top[place[:, 1], place[:, 0]] - 0.3
    total = np.zeros_like(picture); np.add.at(total, (place[upper, 1], place[upper, 0]), colour[texel[upper, 1], texel[upper, 0]])
    np.add.at(count, (place[upper, 1], place[upper, 0]), 1)
    picture[count > 0] = total[count > 0] / count[count > 0, None]
    return {(row, column): picture[row * MINIMAP:(row + 1) * MINIMAP, column * MINIMAP:(column + 1) * MINIMAP][::-1]
            for row in range(rows) for column in range(columns)}


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
    """The group's walk cells, [row, column] from the south-west: {material, raised, depth, slab, roof, footprint, lines}.

    material: Stone where one can walk, Obscuring for the building where it stands at eye height, Nonwalk for the
    lesser things in the way and for the parts of the building's mass that are lower than that.
    raised: the cell lies on the slab (or inside what stands on it). slab: the slab's height. roof: the building's.
    footprint: the building's outline at the survey's own grain, FINE samples to the cell.
    depth: how many cells a cell lies inside the slab's edge, counted to one past RAMP; 0 off the slab.
    lines: (columns, rows) of the cell boundaries the walkmesh is drawn on, through the whole group: the tiles' own
    edges, wherever the cells on either side differ anywhere along the line, and RAMP cells inside the slab's edge."""
    points = scatter(vertices, faces); across = np.array([columns, rows]) * CELLS * FINE; step = SIZE / CELLS / FINE
    # A face that lies on the boundary between two samples falls to the far side of it, all of it: left to rounding its
    # points fall on either side by chance, and the outline they draw is ragged.
    place = np.clip(((points[:, :2] - corner) / step + 1e-6).astype(int), 0, across - 1)
    standing = (points[:, 2] > KNEE) & (points[:, 2] < HEAD)
    solid = np.zeros((across[1], across[0]), bool); solid[place[standing, 1], place[standing, 0]] = True
    solid = ~_outside(~solid)  # what the walls enclose is closed too
    looking = (points[:, 2] > EYE) & (points[:, 2] < HEAD)
    tall = np.zeros(solid.shape, bool); tall[place[looking, 1], place[looking, 0]] = True
    tall = ~_outside(~tall)
    low = np.zeros(solid.shape); under = points[:, 2] <= KNEE
    np.maximum.at(low, (place[under, 1], place[under, 0]), points[under, 2])
    on_slab = ~_outside(~(low > STEP))  # and what the slab's rim encloses stands on it
    slab = float(np.median(low[low > STEP])) if (low > STEP).any() else 0.0
    cells = lambda fine: fine.reshape(rows * CELLS, FINE, columns * CELLS, FINE).mean((1, 3))
    closed = cells(solid) >= 0.25; raised = cells(on_slab) > 0.5
    labels, count = _masses(closed); material = np.full(closed.shape, STONE); footprint = np.zeros_like(solid)
    if count:
        sizes = np.bincount(labels.ravel())[1:]; building = int(sizes.argmax()) + 1
        material[closed] = NONWALK; material[(labels == building) & (cells(tall) >= 0.25)] = OBSCURING
        footprint = tall & np.repeat(np.repeat(material == OBSCURING, FINE, 0), FINE, 1)
    require(not (closed[0].any() or closed[-1].any() or closed[:, 0].any() or closed[:, -1].any()) and not (raised[0].any() or raised[-1].any() or raised[:, 0].any() or raised[:, -1].any()),
            'The model reaches the edge of its tiles: the group leaves no ground around it')
    depth = raised.astype(int); inner = raised
    for _ in range(RAMP):  # a cell is one deeper than the shallowest of the four beside it
        wide = np.pad(inner, 1); inner = inner & wide[:-2, 1:-1] & wide[2:, 1:-1] & wide[1:-1, :-2] & wide[1:-1, 2:]; depth += inner
    kind = material * 4 + raised * 2 + (depth > RAMP)  # past the ramp the walkmesh has reached the slab's height
    lines = (sorted({column * CELLS for column in range(columns + 1)} | {int(x) for x in np.flatnonzero((kind[:, 1:] != kind[:, :-1]).any(0)) + 1}),
             sorted({row * CELLS for row in range(rows + 1)} | {int(y) for y in np.flatnonzero((kind[1:] != kind[:-1]).any(1)) + 1}))
    return {'material': material, 'raised': raised, 'slab': slab, 'roof': float(vertices[:, 2].max()), 'footprint': footprint, 'lines': lines, 'depth': depth}


def lines(found, row, column):
    """(columns, rows) of one tile's grid lines, counted in cells from its south-west corner."""
    return tuple([value - first for value in found['lines'][axis] if first <= value <= first + CELLS] for axis, first in ((0, column * CELLS), (1, row * CELLS)))


def walkmesh(found, row, column):
    """(vertices, faces with a material each) of one tile's walkmesh, in the tile's own space: a pair of faces to
    each box of the tile's grid lines, the floor's vertices first. Between two lines the cells are all alike, on both
    sides of every line, so a box has one material and one neighbour on each side."""
    material, depth = found['material'], found['depth']; rows, columns = material.shape
    first_row, first_column = row * CELLS, column * CELLS; xs, ys = lines(found, row, column); cell = SIZE / CELLS

    def lift(y, x):  # the rim of the slab is the ramp onto it: a corner on the slab's edge is on the ground, one RAMP cells in is up
        around = [depth[r, c] for r in (first_row + y - 1, first_row + y) for c in (first_column + x - 1, first_column + x) if 0 <= r < rows and 0 <= c < columns]
        return found['slab'] * min(min(around), RAMP) / RAMP if len(around) == 4 else 0.0
    vertices = [[x * cell - SIZE / 2, y * cell - SIZE / 2, lift(y, x)] for y in ys for x in xs]
    at = lambda j, i: j * len(xs) + i; faces = []
    walls = lambda r, c: 0 <= r < rows and 0 <= c < columns and material[r, c] == OBSCURING
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            south, west, north, east = first_row + ys[j], first_column + xs[i], first_row + ys[j + 1], first_column + xs[i + 1]
            kind = int(material[south, west])
            faces += [[at(j + 1, i), at(j, i), at(j + 1, i + 1), kind], [at(j + 1, i + 1), at(j, i), at(j, i + 1), kind]]
            if kind != OBSCURING:
                continue
            # An upright face on each side of the building that looks out on open ground, from the ground to the roof.
            for beyond, (a, b) in (((south, west - 1), ((j + 1, i), (j, i))), ((south, east), ((j, i + 1), (j + 1, i + 1))),
                                   ((south - 1, west), ((j, i), (j, i + 1))), ((north, west), ((j + 1, i + 1), (j + 1, i)))):
                if walls(*beyond):
                    continue
                base = len(vertices); vertices += [[*vertices[at(*a)][:2], found['roof']], [*vertices[at(*b)][:2], found['roof']]]
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


def lid(found, row, column):
    """The lid over the building's outline in one tile, as strips: [(x0, y0, x1, y1)] in the tile's space. Rows of the
    outline that run alike are joined into one strip. The outline is the survey's, taken at eye height."""
    across = CELLS * FINE; closed = found['footprint'][row * across:(row + 1) * across, column * across:(column + 1) * across]
    side = np.linspace(-SIZE / 2, SIZE / 2, across + 1); strips, open_runs = [], {}
    for y in range(across + 1):
        edges = np.flatnonzero(np.diff(np.concatenate([[0], closed[y].astype(int), [0]]))) if y < across else np.array([], int)
        runs = set(zip(edges[::2].tolist(), edges[1::2].tolist()))
        for run in [run for run in open_runs if run not in runs]:  # a run that ends here closes its strip
            strips.append((float(side[run[0]]), float(side[open_runs.pop(run)]), float(side[run[1]]), float(side[y])))
        for run in runs:
            open_runs.setdefault(run, y)
    return strips


def light_places(found, row, column):
    """Where a tile's two main lights hang, in the tile's space: the first over its open ground, where people stand, at
    the spot farthest from both what is closed and the tile's edge; the second over the tile's middle, clear of the roof."""
    material = found['material'][row * CELLS:(row + 1) * CELLS, column * CELLS:(column + 1) * CELLS]
    cell = SIZE / CELLS; middle = lambda cells: (np.argwhere(cells)[:, ::-1] + 0.5) * cell - SIZE / 2  # (x, y) of each cell
    ground, closed = middle(material == STONE), middle(material != STONE); first = np.zeros(2)
    if len(ground):
        room = SIZE / 2 - np.abs(ground).max(1)
        if len(closed):
            room = np.minimum(room, np.linalg.norm(ground[:, None] - closed[None], axis=2).min(1))
        first = ground[int(room.argmax())]
    return [(float(first[0]), float(first[1]), LIGHT_HEIGHT), (0.0, 0.0, max(found['roof'] + 1.5, LIGHT_HEIGHT))]


def _daylight(name, halos):
    """The four animations the game plays on a tile as the hour turns, with the halo sheets clear by day and full by
    night. Lengths and the quarter-second blend are the stock city tiles'."""
    lines = []
    for anim, (start, finish, length) in {'day': (0, 0, 1 / 30), 'day2night': (0, 1, 0.56667), 'night': (1, 1, 1 / 30), 'night2day': (1, 0, 0.6)}.items():
        lines += [f'newanim {anim} {name}', f'  length {length:.5f}', '  transtime 0.25', f'  animroot {name}', f'  node dummy {name}', '    parent NULL', '  endnode']
        for halo in halos:
            lines += [f'  node trimesh {halo}', f'    parent {name}', '    alphakey 2', f'      0.00000 {start}', f'      {length:.5f} {finish}', '    endlist', '  endnode']
        lines += [f'doneanim {anim} {name}']
    return lines


def model_text(name, parts, material, ground, cards, walk, *, lights=(), fade=None, cap=()):
    """One tile's ASCII model. parts: [(vertices, normals, uvs, faces)] of the building, in the tile's space; a fifth
    value, true, marks a part the game may hide (`tilefade`). ground: the texture of the ten-metre square under it, laid
    twice across the tile as the plain tiles lay theirs. lights: the places of its main lights. fade: the height above
    which things may be hidden; a halo card whose middle is above it goes with them. cap: the lid drawn at that height
    only while they are hidden ([(x0, y0, x1, y1)]), so the building is not seen hollow."""
    require(len(name) <= 16 and name == name.lower() and name.replace('_', '').isalnum(), 'A tile model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', 'setanimationscale 1.0',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    common = ['  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1', '  render 1', '  shadow 0', '  rotatetexture 0', '  tilefade 0']
    half = SIZE / 2
    lines += [f'node trimesh {name}_g', f'  parent {name}', *common, f'  bitmap {ground}', '  verts 4', f'    {-half} {-half} 0', f'    {half} {-half} 0',
              f'    {-half} {half} 0', f'    {half} {half} 0', '  tverts 4', '    0 2 0', '    2 2 0', '    0 0 0', '    2 0 0', '  normals 4', *['    0 0 1'] * 4,
              '  faces 2', '    2 0 3 1 2 0 3 1', '    3 0 1 1 3 0 1 1', 'endnode']
    number = 0
    for vertices, normals, uvs, faces, *hidden in parts:
        mesh = [*common[:-1], '  tilefade 1'] if hidden and hidden[0] else common
        for used, part in convert.split(faces):
            lines += [f'node trimesh {name}_m{number}', f'  parent {name}', *mesh, f'  bitmap {material}', f'  verts {len(used)}']; number += 1
            lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in vertices[used].tolist()]
            lines += [f'  tverts {len(used)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in uvs[used].tolist()]
            lines += [f'  normals {len(used)}'] + [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in normals[used].tolist()]
            lines += [f'  faces {len(part)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in part.tolist()] + ['endnode']
    for index, card in enumerate(cards):
        above = fade is not None and (card[0][0][2] + card[2][0][2]) / 2 >= fade
        lines += [f'node trimesh {name}_halo{index}', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {material}_h', '  render 1', '  shadow 0', '  rotatetexture 0', f'  tilefade {1 if above else 0}', '  transparencyhint 1', '  alpha 1', '  verts 4']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for (x, y, z), _ in card] + ['  tverts 4'] + [f'    {u:.5f} {v:.5f} 0' for _, (u, v) in card]
        lines += ['  normals 4'] + [convert.card_normal_line(card)] * 4 + ['  faces 2', '    0 1 2 1 0 1 2 1', '    0 2 3 1 0 2 3 1', 'endnode']
    if cap:  # `tilefade 2`: drawn only while the parts above it are hidden
        corners = [corner for x0, y0, x1, y1 in cap for corner in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        lines += [f'node trimesh {name}_cap', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1', f'  bitmap {CAP}',
                  '  render 1', '  shadow 0', '  rotatetexture 0', '  tilefade 2', f'  verts {len(corners)}']
        lines += [f'    {x:.5f} {y:.5f} {fade:.5f}' for x, y in corners] + [f'  tverts {len(corners)}'] + ['    0 0 0'] * len(corners)
        lines += [f'  normals {len(corners)}'] + ['    0 0 1'] * len(corners) + [f'  faces {len(cap) * 2}']
        for first in range(0, len(corners), 4):
            lines += [f'    {first} {first + 1} {first + 2} 1 {first} {first + 1} {first + 2} 1', f'    {first} {first + 2} {first + 3} 1 {first} {first + 2} {first + 3} 1']
        lines += ['endnode']
    for index, (x, y, z) in enumerate(lights, 1):
        lines += [f'node light {name}ml{index}', f'  parent {name}', f'  position {x:.5f} {y:.5f} {z:.5f}', '  orientation 1 0 0 0', '  color 1 1 1', '  radius 14',
                  '  multiplier 1', '  ambientonly 0', '  nDynamicType 1', '  affectdynamic 1', '  shadow 0', '  lightpriority 5', '  fadinglight 1', 'endnode']
    lines += _walk_node(name, name, *walk) + [f'endmodelgeom {name}']
    if cards:
        lines += _daylight(name, [f'{name}_halo{index}' for index in range(len(cards))])
    return '\n'.join(lines + [f'donemodel {name}']) + '\n'


def walk_text(name, walk):
    return '\n'.join([f'beginwalkmeshgeom {name}', *_walk_node(name, name, *walk), f'endwalkmeshgeom {name}']) + '\n'


def share_cards(cards, rows, columns, corner):
    """{(row, column): [card]}: each halo card cut along the tile lines it crosses, in each tile's own space. A card
    stands upright facing along x or along y, so it runs along the other of the two and is cut along that."""
    shared = {}; counts = (columns, rows)
    for card in cards:
        (start, (u_start, v_bottom)), (end, (u_end, _)), (upper, (_, v_top)) = [(np.array(place, float), uv) for place, uv in card[:3]]
        along = int(np.abs(end - start)[:2].argmax()); fixed = 1 - along
        held = int(np.clip((start[fixed] - corner[fixed]) // SIZE, 0, counts[fixed] - 1))
        for index in range(counts[along]):
            low, high = corner[along] + index * SIZE, corner[along] + (index + 1) * SIZE
            near, far = np.clip([start[along], end[along]], low, high)  # in the card's own order, left corner to right
            if abs(near - far) < 1e-6:
                continue
            u = lambda value: u_start + (value - start[along]) / (end[along] - start[along]) * (u_end - u_start)
            cell = {along: index, fixed: held}; column, row = cell[0], cell[1]
            centre = np.array([corner[0] + (column + 0.5) * SIZE, corner[1] + (row + 0.5) * SIZE, 0.0])

            def at(value, height):
                point = start.copy(); point[along] = value; point[2] = height
                return tuple((point - centre).tolist())
            shared.setdefault((row, column), []).append([(at(near, start[2]), (u(near), v_bottom)), (at(far, start[2]), (u(far), v_bottom)),
                                                         (at(far, upper[2]), (u(far), v_top)), (at(near, upper[2]), (u(near), v_top))])
    return shared


def group(name, made, folder, *, ground, colour=None, ground_colour=(0.4, 0.4, 0.4), fade=None, door=None):
    """Write the tile models and walkmeshes of a finished model (`convert.shape`) into `folder`; returns
    {rows, columns, tiles: [{model, row, column, faces, walkFaces, image, lights, doors}]} with the tiles in the set
    file's order.

    colour: the model's colour texture (0-1 array); with it each tile gets its picture for the area map, `image`, drawn
    over `ground_colour`. fade: the height in metres above which the building may be hidden. door: {at: [x, y, z],
    facing, type} on the finished model; it becomes a door record of the tile it stands in."""
    require(len(name) <= convert.TILE_NAME_LENGTH, 'A tile group name leaves four characters for the tile: ' + name)
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    vertices, normals, uvs, faces = made['vertices'], made['normals'], made['uvs'], made['faces']
    rows, columns, corner = layout(vertices); found = survey(vertices, faces, rows, columns, corner)
    require(fade is None or found['slab'] < fade < found['roof'], 'The fade height lies between the slab and the roof')
    middle = vertices[faces].mean(1); home = np.clip(((middle[:, :2] - corner) // SIZE).astype(int), 0, [columns - 1, rows - 1])
    high = middle[:, 2] >= fade if fade is not None else np.zeros(len(faces), bool)
    cards = share_cards(made['card'][1] if made['card'] else [], rows, columns, corner); tiles = []
    pictures = minimaps(vertices, uvs, faces, colour, rows, columns, corner, ground_colour) if colour is not None else {}
    if door is not None:
        at = np.asarray(door['at'], float); cell = np.clip(((at[:2] - corner) // SIZE).astype(int), 0, [columns - 1, rows - 1])
    if fade is not None:
        from PIL import Image
        Image.new('RGB', (4, 4)).save(folder / f'{CAP}.tga')
    for row in range(rows):
        for column in range(columns):
            model = f'{name}_t{row}{column}'; centre = np.array([corner[0] + (column + 0.5) * SIZE, corner[1] + (row + 0.5) * SIZE, 0.0])
            here = (home[:, 0] == column) & (home[:, 1] == row); parts = []
            for chosen, hidden in ((here & ~high, False), (here & high, True)):
                if chosen.any():
                    used, local = np.unique(faces[chosen], return_inverse=True)
                    parts.append((vertices[used] - centre, normals[used], uvs[used], local.reshape(-1, 3), hidden))
            walk = walkmesh(found, row, column); lights = light_places(found, row, column)
            text = model_text(model, parts, name, ground, cards.get((row, column), []), walk, lights=lights, fade=fade,
                              cap=lid(found, row, column) if fade is not None else ())
            (folder / f'{model}.mdl').write_text(text, encoding='cp1252', newline='\n')
            (folder / f'{model}.wok').write_text(walk_text(model, walk), encoding='cp1252', newline='\n')
            one = {'model': model, 'row': row, 'column': column, 'faces': int(here.sum()), 'fadingFaces': int((here & high).sum()), 'walkFaces': int(len(walk[1])),
                   'closedCells': int((found['material'][row * CELLS:(row + 1) * CELLS, column * CELLS:(column + 1) * CELLS] != STONE).sum()),
                   'lights': len(lights), 'doors': []}
            if (row, column) in pictures:
                from PIL import Image
                one['image'] = f'{name}_m{row}{column}'  # a 24-bit picture, stored bottom row first as the stock ones are
                Image.fromarray((np.clip(pictures[(row, column)], 0, 1) * 255).round().astype(np.uint8)).save(folder / f'{one["image"]}.tga')
            if door is not None and (cell == [column, row]).all():
                x, y, z = (at - centre).round(2).tolist()
                one['doors'].append({'type': int(door.get('type', 0)), 'x': x, 'y': y, 'z': z, 'orientation': float(door.get('facing', 0.0))})
            tiles.append(one)
    return {'rows': rows, 'columns': columns, 'slab': round(found['slab'], 3), 'roof': round(found['roof'], 3), 'fade': fade, 'tiles': tiles}


def compile_tiles(sources, output):
    """Compile tile models with the pinned cleanmodels into `output`; returns the compiled paths. (armorkit's compile
    reads each model back with a reader that knows no walkmesh node, so the tiles are checked here by size alone.)"""
    from tools.armorkit import toolchain
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
    """The set file's record of each tile, in order: all four corners `terrain` at height 0, no crossers, and the
    main lights, doors and area-map picture the tile was built with (`doors` gives each tile's door records to write
    after it). In a 2 by 2 group each tile has the building on its inner corner, and says so for pathfinding. Any other
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
                  'MainLight1': int(tile.get('lights', 0) >= 1), 'MainLight2': int(tile.get('lights', 0) >= 2),
                  **{key: 0 for key in ('SourceLight1', 'SourceLight2', 'AnimLoop1', 'AnimLoop2', 'AnimLoop3', 'Sounds')}, 'Doors': len(tile.get('doors', [])),
                  'PathNode': node, 'Orientation': turn, 'VisibilityNode': node, 'VisibilityOrientation': turn, 'ImageMap2D': tile.get('image', '')}
        records.append([(key, values[key]) for key in TILE_KEYS])
    return records


def doors(made):
    """Each tile's door records, in the tiles' order."""
    return [tile.get('doors', []) for tile in made['tiles']]


def _tile_block(number, record, hooks, end):
    """One tile's lines in a set file: its record, then a block for each of its doors."""
    block = f'[TILE{number}]{end}' + ''.join(f'{key}={value}{end}' for key, value in record) + end
    for index, hook in enumerate(hooks):
        block += (f'[TILE{number}DOOR{index}]{end}Type={hook["type"]}{end}X={hook["x"]}{end}Y={hook["y"]}{end}Z={hook["z"]}{end}'
                  f'Orientation={hook["orientation"]}{end}{end}')
    return block


def revise(text, records, hooks=None):
    """The set file's text with tiles already there written again under the numbers they have, with their doors;
    returns (text, first tile). Every tile must be there: a tile once placed in areas keeps its number."""
    end = '\r\n' if '\r\n' in text else '\n'; first = None
    for record, mine in zip(records, hooks or [[] for _ in records]):
        model = dict(record)['Model']
        found = [block for block in re.finditer(r'(?ms)^\[TILE(\d+)\]\r?\n.*?(?=^\[)', text)
                 if re.search(r'(?mi)^Model=' + re.escape(model) + r'\r?$', block.group(0))]
        require(len(found) == 1, 'The set file does not list exactly one ' + model)
        number = found[0].group(1); first = int(number) if first is None else first
        after = re.compile(r'(?ms)(?:^\[TILE' + number + r'DOOR\d+\]\r?\n.*?(?=^\[))*').match(text, found[0].end())
        text = text[:found[0].start()] + _tile_block(number, record, mine, end) + text[after.end():]
    return text, first


def register(text, records, group_name, rows, columns, hooks=None):
    """The set file's text with the tiles and their group appended; returns (text, first tile, group number). No tile or
    group already there is renumbered. The file's own line ends are kept. `hooks` gives each tile's door records."""
    end = '\r\n' if '\r\n' in text else '\n'; hooks = hooks or [[] for _ in records]
    tiles = re.search(r'(?m)^\[TILES\]\r?\nCount=(\d+)', text); groups = re.search(r'(?m)^\[GROUPS\]\r?\nCount=(\d+)', text)
    require(tiles and groups and tiles.start() < groups.start(), 'The set file has no tiles and groups to add to')
    first, number = int(tiles.group(1)), int(groups.group(1))
    require(f'[TILE{first - 1}]' in text and f'[TILE{first}]' not in text and f'[GROUP{number}]' not in text, 'The set file\'s counts do not match its records')
    for record in records:
        require(not re.search(r'(?mi)^Model=' + re.escape(dict(record)['Model']) + r'\r?$', text), 'The set file already lists ' + dict(record)['Model'])
    require(not re.search(r'(?m)^Name=' + re.escape(group_name) + r'\r?$', text), 'The set file already has a group named ' + group_name)
    blocks = ''.join(_tile_block(first + index, record, hooks[index], end) for index, record in enumerate(records))
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
    tileset lacks, a group half there, a palette that cannot be read) comes before any file changes. A group already
    in the set file whole is built again in place: its tiles keep their numbers and its palette entry stands."""
    from tools.phenotypes import tool_runtime
    set_path, palette_path = Path(set_path), Path(palette_path); text = set_path.read_bytes().decode('cp1252')
    require(terrain in terrains(text), f'{set_path.name} has no terrain named {terrain}: ' + ', '.join(terrains(text)))
    there = [bool(re.search(r'(?mi)^Model=' + re.escape(one['model']) + r'\r?$', text)) for one in made['tiles']]
    if all(there):
        listed = re.search(r'(?ms)^\[GROUP(\d+)\]\r?\nName=' + re.escape(group_name) + r'\r?\nRows=' + str(made['rows']) + r'\r?\nColumns=' + str(made['columns']) + r'\r?$', text)
        require(listed, f'{set_path.name} lists the tiles but not their group {group_name} at {made["rows"]} by {made["columns"]}')
        text, first = revise(text, tile_records(made, terrain), doors(made))
        return {'tool': None, 'set': set_path, 'written': game_bytes(text, set_path.name), 'palette': palette_path, 'document': None, 'firstTile': first, 'group': int(listed.group(1))}
    require(not any(there), f'{set_path.name} lists some of the group\'s tiles and not others')
    text, first, number = register(text, tile_records(made, terrain), group_name, made['rows'], made['columns'], doors(made))
    written = game_bytes(text, set_path.name)  # refused here, before anything is written, if a name has a character the game lacks
    tool = str(tool_runtime.tool('nwn_gff'))
    read = subprocess.run([tool, '-i', str(palette_path), '-k', 'json'], capture_output=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    require(read.returncode == 0, 'The palette could not be read: ' + read.stderr.decode(errors='replace')[-400:])
    document = palette(json.loads(read.stdout), label, made['tiles'][0]['model'], single=len(made['tiles']) == 1)
    return {'tool': tool, 'set': set_path, 'written': written, 'palette': palette_path, 'document': document, 'firstTile': first, 'group': number}


def commit(prepared):
    """Write what `prepare` worked out: the palette (for a group new to the tileset), then the set file; returns
    {firstTile, group}."""
    if prepared['document'] is None:
        prepared['set'].write_bytes(prepared['written'])
        return {'firstTile': prepared['firstTile'], 'group': prepared['group']}
    with tempfile.TemporaryDirectory() as folder:  # the JSON never lies in the pack, where a stopped run would leave it
        staged = Path(folder) / 'palette.json'; staged.write_text(json.dumps(prepared['document']), encoding='utf-8')
        wrote = subprocess.run([prepared['tool'], '-i', str(staged), '-l', 'json', '-o', str(prepared['palette']), '-k', 'gff'], capture_output=True, timeout=120,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(wrote.returncode == 0, 'The palette could not be written: ' + wrote.stderr.decode(errors='replace')[-400:])
    prepared['set'].write_bytes(prepared['written'])
    return {'firstTile': prepared['firstTile'], 'group': prepared['group']}


def install(set_path, palette_path, made, *, terrain, group_name, label):
    """Append a built group to one tileset's set file and palette in place; returns {firstTile, group}."""
    return commit(prepare(set_path, palette_path, made, terrain=terrain, group_name=group_name, label=label))
