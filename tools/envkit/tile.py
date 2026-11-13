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
onto it over the slab's outermost half metre. A strip of slab too narrow for that, a kerb or a step three quarters of
a metre to a metre wide, is climbed over its outer quarter metre instead; a narrower one is left on the ground.
A deck, a broad flat floor raised past the knee (the Saeder-Krupp yard's loading bay and its apron stand on one 0.55
metres high), is walked on at its own height and climbed over its outer half metre where it meets lower open ground;
what stands on it is closed as on the ground (`_decks`). A deck too high to step onto, a loading platform, is walked on
where stairs lead up to it, and climbed only by them: its edge is closed elsewhere (`_stairs`). Ground with no room to stand on, where no metre-square block
of open cells reaches (a gap between fence sections, a notch in a wall), is closed as well: a walk is not planned
through it.

A tile also carries what the stock tiles carry (read off Modern Exterior's and the stock city's tiles, 2026-11-11): a
32-pixel picture for the area map, two main lights a builder colours in the Toolset, the `day`, `night`, `day2night`
and `night2day` animations the game plays as the hour turns (here they fade the halo sheets, which belong to the
night), `tilefade` on what stands above a stated height so the game can hide it when a character is behind, and a
door: a line in the set file from which the Toolset makes the door when the tile is painted.

A walk from one tile to another is planned tile to tile, from each tile's path node in the set file: a letter that
says by which sides the tile can be left and which of those are joined inside it, and a turn. A group's tiles get the
nodes their own ground allows, chosen together, so a group can be of any size (`path_node`, `path_nodes`). The engine
puts each exit at its side's middle and walks a character from one to the next; where it cannot follow a route it
gives the walk up and walks straight at the target (the Saeder-Krupp yard, 2026-11-12). A wrong node does not always show in a
short walk. The Stuffer Shack's first nodes were turned half a turn wrong, and walks of a tile or two round it still
arrived; only walkers from four tiles away stopped short. Yet a walk of 7.5 metres into a walled yard failed from the
next tile while the yard's side was not an exit. So a new group is checked in the client with walkers sent from four
tiles away and more, and from the next tile onto any ground that has one way in. `group` notes ground no exit reaches.

A door's record reads right long before the door works. The Ares Depot's hook was read back from the Toolset's saved
area twice, at its place and with a bearing, before anyone used it: in the client the invisible door stood out of the
wall at a right angle and a click on it took the player nowhere (`doorstep`). So a new group's door is given an area
transition and clicked in the client, there and back, with the group painted turned as well as straight."""
import itertools
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
# A deck is a floor flat to FLAT metres, no higher than DECK and of DECK_AREA square metres at least: the tops of crates,
# benches and barriers are smaller, and the Saeder-Krupp yard's bay floor is 68 (user, 2026-11-12: "more area on the
# pavement and in the bay should be walkable").
DECK, DECK_AREA, FLAT = 0.75, 9.0, 0.06
# A floor higher than DECK, up to PLATFORM, is a deck only where stairs lead up to it: steps no taller than RISER from its
# edge down to the ground, no steeper overall than STAIR, rise over run. The rail freight depot's loading platform is
# 1.2 metres high with five steps at one end (user, 2026-11-13: "the stairs up onto platform, and the platform itself
# should be walkable"); a platform with no stairs stays in the way.
PLATFORM, RISER, STAIR = 1.5, 0.35, 1.25
# The engine's path nodes whose exits are a tile's four sides, each as the sides its regions join at no turn
# (N, W, S, E; +y is north). A turn is counter-clockwise, in quarters. From the engine's table as nwn.wiki's page on
# tile path nodes gives it, checked against the walkmeshes of the 1,091 stock tiles of Modern Exterior and Suburbs on
# 2026-11-11: with turns counter-clockwise 93 of the 96 exits of their H tiles lie on walkable ground, clockwise 37.
# The first that fits is taken, so the letters the stock tiles use most come first.
PATH_NODES = {'A': ('NWSE',), 'I': ('NWS',), 'H': ('WS',), 'L': ('NS',), 'N': ('N',), 'T': (), 'J': ('WS', 'EN'), 'U': ('W', 'SNE'),
              'X': ('N', 'W'), 'Y': ('N', 'S'), 'V': ('N', 'SE'), 'W': ('N', 'SW'), 'w': ('N', 'W', 'E', 'S')}
EXIT = 4  # cells of a tile's side that must lie open together for the side to be an exit: a metre
# The engine's table puts every exit of these letters at the middle of its side (nwn.wiki, tile path nodes) and walks a
# character from exit to exit. It found an opening 2.75 metres off a side's middle (client, 2026-11-11); one farther
# than REACH cells is no exit. Where a route joins two exits a walk between cannot follow, the engine gives up the walk
# and walks straight at the target: the Saeder-Krupp yard's walkers to its apron gave up while the tiles south of it
# joined the ground outside its fence to the yard round the fence's ends, 3 metres aside, and arrived once those were
# not joined (client, 2026-11-12). ASIDE is how far aside a joined walk may go.
REACH = 12
ASIDE = 8  # cells: two metres
WALK_FACES = 500  # the most walk faces of any stock tile of Modern Exterior and Suburbs: a tile with more is noted
# A lit patch of fewer square metres than LIT does not say where a halo card goes: the least patch `glow.halo` gives a card to.
# A light must reach FOOT metres past the hiding height to count on that side of it too: less is its foot, or its head.
LIT, FOOT = 0.05, 0.25
# A door's hook lies where a character can stand: with ROOM metres of open ground before and behind it and SIDE metres
# to either hand (a doorway between bollards is not much wider), found within DOOR_REACH metres out from the door. The Ares
# Depot's first hook lay on its door leaf, in the closed ground of the wall: the player walked up to the door and nothing
# happened; drawn 0.6 metres out, the same door took them through (client, 2026-11-11).
DOOR_ROOM, DOOR_SIDE, DOOR_REACH = 0.4, 0.3, 2.0
DOOR_STEP = KNEE  # metres: how far in height the ground under a drawn-out hook may lie from the door's foot (the depot's is 0.33)
TILE_KEYS = ('Model', 'WalkMesh', 'TopLeft', 'TopLeftHeight', 'TopRight', 'TopRightHeight', 'BottomLeft', 'BottomLeftHeight', 'BottomRight',
             'BottomRightHeight', 'Top', 'Right', 'Bottom', 'Left', 'MainLight1', 'MainLight2', 'SourceLight1', 'SourceLight2', 'AnimLoop1',
             'AnimLoop2', 'AnimLoop3', 'Doors', 'Sounds', 'PathNode', 'Orientation', 'VisibilityNode', 'VisibilityOrientation', 'ImageMap2D')


def layout(vertices):
    """(rows, columns, south-west corner) of the group that holds the model centred."""
    low, high = vertices.min(0), vertices.max(0)
    columns, rows = (max(1, int(np.ceil((high[axis] - low[axis]) / SIZE - 1e-6))) for axis in (0, 1))
    middle = (low[:2] + high[:2]) / 2
    return rows, columns, middle - np.array([columns, rows]) * SIZE / 2


scatter = convert.scatter  # a mesh's surface as points: `convert` has it, for what it checks on a model before any tile is cut


def minimaps(vertices, uvs, faces, colour, rows, columns, corner, ground, *, more=()):
    """{(row, column): (MINIMAP, MINIMAP, 3) picture, 0-1}: each tile seen from straight above, north at the top, as
    the area map shows it. `colour` is the model's colour texture (0-1, any size); `ground` the colour round the model;
    `more` the other models of the group as (vertices, uvs, faces, colour), each seen with its own picture."""
    found = []
    for mesh_vertices, mesh_uvs, mesh_faces, mesh_colour in [(vertices, uvs, faces, colour), *more]:
        points, pick, weights = scatter(mesh_vertices, mesh_faces, spacing=SIZE / MINIMAP / 3, sources=True)
        size = np.array([mesh_colour.shape[1], mesh_colour.shape[0]])
        texel = np.clip(((mesh_uvs[mesh_faces[pick]] * weights[:, :, None]).sum(1) * size).astype(int), 0, size - 1)
        found.append((points, mesh_colour[texel[:, 1], texel[:, 0]]))
    points = np.vstack([points for points, _ in found]); shades = np.vstack([shades for _, shades in found])
    across = np.array([columns, rows]) * MINIMAP
    place = np.clip(((points[:, :2] - corner) / SIZE * MINIMAP).astype(int), 0, across - 1)
    picture = np.tile(np.asarray(ground, float), (across[1], across[0], 1)); count = np.zeros((across[1], across[0]))
    # What shows from above is the highest thing in each pixel: the mean colour of the points in its top 30 cm.
    top = np.full((across[1], across[0]), -np.inf); np.maximum.at(top, (place[:, 1], place[:, 0]), points[:, 2])
    upper = points[:, 2] >= top[place[:, 1], place[:, 0]] - 0.3
    total = np.zeros_like(picture); np.add.at(total, (place[upper, 1], place[upper, 0]), shades[upper])
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


def _decks(points, place, standing, shape):
    """(deck, stairs): the height of the deck each survey sample lies on, 0 off any deck, and of the stairs up to one,
    0 off any. A deck is a flat floor past the knee of DECK_AREA at least, and its rim, the samples beside it where the
    mesh stands no higher than the deck (its edge face, from the ground up); one higher than DECK is a deck only where
    stairs lead up to it (`_stairs`). What stands on a deck rises past it, and is not part of it."""
    lowest = np.full(shape, np.inf); top = np.zeros(shape); spot = (place[standing, 1], place[standing, 0])
    np.minimum.at(lowest, spot, points[standing, 2]); np.maximum.at(top, spot, points[standing, 2])
    surface = np.zeros(shape); under = points[:, 2] < HEAD  # the top of what is there, the ground's foot of a step included
    np.maximum.at(surface, (place[under, 1], place[under, 0]), points[under, 2])
    labels, count = _masses((lowest <= PLATFORM) & (top - lowest < FLAT)); deck = np.zeros(shape); stairs = np.zeros(shape)
    sizes = np.bincount(labels.ravel(), minlength=count + 1)[1:] * (SIZE / CELLS / FINE) ** 2
    for index in np.flatnonzero(sizes >= DECK_AREA):
        member = labels == index + 1
        if (deck[member] > 0).any():
            continue  # a bay of a platform already found from another
        height = float(np.median(lowest[member]))
        near = np.pad(member, 1); near = member | near[:-2, 1:-1] | near[2:, 1:-1] | near[1:-1, :-2] | near[1:-1, 2:]
        floor = member | (near & (top > 0) & (top <= height + FLAT))
        if height > DECK:
            # A platform's top is every sample level with it that joins it: the depot's is cut into five bays by seams a
            # few centimetres proud, and its edge faces stand between its bays and the head of its stairs.
            joined, _ = _masses(floor | (np.abs(surface - height) <= FLAT))
            floor = np.isin(joined, np.unique(joined[floor])) & (joined > 0)
            way = _stairs(surface, floor, height)
            if not way.any():
                continue  # too high to step onto, and nothing leads up: in the way, as a crate is
            stairs[way] = surface[way]
        deck[floor] = height
    return deck, stairs


def _stairs(surface, floor, height):
    """The survey samples of the stairs up to a deck `height` high whose samples are `floor`, False off them: from the
    deck's edge outwards, samples each no higher than the one before and at most RISER below it, down to where they
    meet the ground (STEP). A flight counts where it covers a square metre and comes down to the ground no steeper than
    STAIR, rise over run, from the deck's edge to its foot: a bench beside a platform drops too far at once to be a
    step, and a slope that meets the ground right at the edge is too steep."""
    from collections import deque
    step = SIZE / CELLS / FINE; reach = np.full(surface.shape, -1); queue = deque()
    for at in zip(*np.nonzero(floor)):
        reach[at] = 0; queue.append(at)
    rows, columns = surface.shape
    while queue:
        row, column = queue.popleft()
        for near in ((row + 1, column), (row - 1, column), (row, column + 1), (row, column - 1)):
            if 0 <= near[0] < rows and 0 <= near[1] < columns and reach[near] < 0 and STEP < surface[near] < height - FLAT / 2 \
                    and surface[row, column] - RISER <= surface[near] <= surface[row, column] + FLAT:
                reach[near] = reach[row, column] + 1; queue.append(near)
    way = reach > 0; flights, count = _masses(way); found = np.zeros(surface.shape, bool)
    padded = np.pad(surface, 1, constant_values=np.inf); off = np.pad(floor | way, 1, constant_values=True)
    meets = np.zeros(surface.shape, bool)  # a sample of the stairs beside the ground
    for down, along in ((0, 1), (2, 1), (1, 0), (1, 2)):
        beside = padded[down:down + rows, along:along + columns]; taken = off[down:down + rows, along:along + columns]
        meets |= (beside <= STEP) & ~taken
    gentle = meets & (height - surface <= STAIR * reach * step)  # a foot the flight comes down to no steeper than STAIR
    for flight in range(1, count + 1):
        member = flights == flight
        if member.sum() * step ** 2 >= 1.0 and (member & gentle).any():
            found |= member
    return found


def survey(vertices, faces, rows, columns, corner, barrier=None):
    """The group's walk cells, [row, column] from the south-west: {material, raised, depth, crest, slab, roof, footprint, lines,
    deck, deckDepth}.
    `barrier` is (vertices, faces) of what stands in the way without being part of the model's mesh: a fence's sheets
    (`convert.sheets`), which close the ground they stand on as a wall would and hide nothing behind them.

    material: Stone where one can walk, Obscuring for the building where it stands at eye height, Nonwalk for the
    lesser things in the way and for the parts of the building's mass that are lower than that.
    raised: the cell lies on the slab (or inside what stands on it). slab: the slab's height. roof: the building's.
    footprint: the building's outline at the survey's own grain, FINE samples to the cell.
    depth: how many cells a cell lies inside the slab's edge, counted to one past RAMP; 0 off the slab.
    crest: the cell is the top of a strip of slab too narrow to hold the ramp: more than one cell inside the edge, with
    no cell past the ramp within RAMP cells of it. The walkmesh is at the slab's height all round such a cell.
    lines: (columns, rows) of the cell boundaries the walkmesh is drawn on, through the whole group: the tiles' own
    edges, wherever the cells on either side differ anywhere along the line, RAMP cells inside the slab's edge, and
    round each crest, and at each deck's edge and RAMP cells inside it.
    deck: the height of the deck a walk cell lies on, 0 off any (`_decks`); deckDepth: how many cells it lies inside
    the deck's edge where that meets lower open ground, counted to one past RAMP, closed cells and stairs counting as
    deck. stairs: the height of the stairs a walk cell lies on, 0 off any; a deck higher than DECK has its outer cell
    closed where it meets lower open ground, and its stairs where they stand past the knee beside it."""
    points = scatter(vertices, faces); across = np.array([columns, rows]) * CELLS * FINE; step = SIZE / CELLS / FINE
    # A face that lies on the boundary between two samples falls to the far side of it, all of it: left to rounding its
    # points fall on either side by chance, and the outline they draw is ragged.
    place = np.clip(((points[:, :2] - corner) / step + 1e-6).astype(int), 0, across - 1)
    standing = (points[:, 2] > KNEE) & (points[:, 2] < HEAD)
    solid = np.zeros((across[1], across[0]), bool); solid[place[standing, 1], place[standing, 0]] = True
    decks, stairs = _decks(points, place, standing, solid.shape); solid &= (decks == 0) & (stairs == 0)  # a deck is floor, not something in the way, and its stairs too
    if barrier is not None:  # a generator leaves a fence's frames empty: without its sheets the ground between the posts would be open
        fence = scatter(*barrier); fence = fence[(fence[:, 2] > KNEE) & (fence[:, 2] < HEAD)]
        spot = np.clip(((fence[:, :2] - corner) / step + 1e-6).astype(int), 0, across - 1); solid[spot[:, 1], spot[:, 0]] = True
    solid = ~_outside(~solid)  # what the walls enclose is closed too
    looking = (points[:, 2] > EYE) & (points[:, 2] < HEAD)
    tall = np.zeros(solid.shape, bool); tall[place[looking, 1], place[looking, 0]] = True
    tall = ~_outside(~tall)
    low = np.zeros(solid.shape); under = points[:, 2] <= KNEE
    np.maximum.at(low, (place[under, 1], place[under, 0]), points[under, 2])
    rim = (low > STEP) & (decks == 0) & (stairs == 0)  # a deck's edge rises past the knee too, but it is no slab, nor are its stairs
    on_slab = ~_outside(~rim)  # and what the slab's rim encloses stands on it
    slab = float(np.median(low[rim])) if rim.any() else 0.0
    cells = lambda fine: fine.reshape(rows * CELLS, FINE, columns * CELLS, FINE).mean((1, 3))
    closed = cells(solid) >= 0.25; raised = cells(on_slab) > 0.5
    labels, count = _masses(closed); material = np.full(closed.shape, STONE); footprint = np.zeros_like(solid)
    if count:
        sizes = np.bincount(labels.ravel())[1:]; building = int(sizes.argmax()) + 1
        material[closed] = NONWALK; material[(labels == building) & (cells(tall) >= 0.25)] = OBSCURING
        footprint = tall & np.repeat(np.repeat(material == OBSCURING, FINE, 0), FINE, 1)
    require(not (closed[0].any() or closed[-1].any() or closed[:, 0].any() or closed[:, -1].any()) and not (raised[0].any() or raised[-1].any() or raised[:, 0].any() or raised[:, -1].any()),
            'The model reaches the edge of its tiles: the group leaves no ground around it')
    # A cell is on the deck or its stairs where most of it is either, and on whichever has more of it: a cell at the head
    # of the stairs, half each, is neither lower ground nor in the way.
    up = cells((decks > 0) | (stairs > 0)) > 0.5; on_deck = up & (cells(decks > 0) >= cells(stairs > 0))
    # Its height is its samples' own, not their mean: a mean over part of a cell comes out an ulp off, and a level of its own
    # would draw more walkmesh lines along the deck's rim.
    deck = np.where(on_deck & ~closed, decks.reshape(rows * CELLS, FINE, columns * CELLS, FINE).max((1, 3)), 0.0)
    stair = np.where(up & ~on_deck & ~closed, cells(stairs) / np.maximum(cells(stairs > 0), 1e-9), 0.0)
    # A deck too high to step onto is climbed only by its stairs: its outer cell is closed where it meets lower open
    # ground, and so are its stairs where they stand past the knee beside it, so no walk steps off either. One cell, not
    # RAMP: the depot's platform has a post at the head of its stairs, and half a metre closed left less than a metre
    # either side of it.
    lower = ~closed & (deck == 0) & (stair == 0); wide = np.pad(lower, 1)
    edge = ((deck > DECK) | (stair > KNEE)) & (lower | wide[:-2, 1:-1] | wide[2:, 1:-1] | wide[1:-1, :-2] | wide[1:-1, 2:])
    material[edge] = NONWALK; closed = closed | edge
    # Ground with no room to stand on is closed too: the engine plans a walk through any walk face, and a character
    # cannot pass a gap under a metre. The Saeder-Krupp yard's walkers went for the half-metre gaps between its fence
    # sections, and stopped at the fence (client, both tilesets, 2026-11-12; Codex review of PR 129).
    narrow = (material == STONE) & ~_roomy(material == STONE); material[narrow] = NONWALK; closed = closed | narrow
    depth = raised.astype(int); inner = raised
    for _ in range(RAMP):  # a cell is one deeper than the shallowest of the four beside it
        wide = np.pad(inner, 1); inner = inner & wide[:-2, 1:-1] & wide[2:, 1:-1] & wide[1:-1, :-2] & wide[1:-1, 2:]; depth += inner
    # Without a crest a strip up to 2 * RAMP cells wide has no cell past the ramp, so no line but its own edge, and
    # would be drawn flat on the ground with the slab standing through it.
    wide = np.pad(depth, RAMP); tall_cells, wide_cells = depth.shape; reach = range(2 * RAMP + 1)
    crest = (depth > 1) & (depth == np.max([wide[dy:dy + tall_cells, dx:dx + wide_cells] for dy in reach for dx in reach], axis=0)) & (depth <= RAMP)
    deck[closed] = 0.0; stair[closed] = 0.0
    inner = (deck > 0) | closed | (stair > 0); deck_depth = inner.astype(int)
    for _ in range(RAMP):  # as the slab's depth, but only open ground off the deck is its edge: a wall on it is not
        wide = np.pad(inner, 1); inner = inner & wide[:-2, 1:-1] & wide[2:, 1:-1] & wide[1:-1, :-2] & wide[1:-1, 2:]; deck_depth += inner
    levels = np.unique(deck[deck > 0]); level = (np.searchsorted(levels, deck) + 1) * (deck > 0)  # each deck's height its own kind
    kind = material * 8 + raised * 4 + (depth > RAMP) * 2 + crest  # past the ramp, and on a crest, the walkmesh has reached the slab's height
    kind = kind + 64 * (level * 2 + (deck > 0) * (deck_depth > RAMP))  # and on a deck, past its ramp, the deck's
    kind = kind + 1024 * np.round(stair / STEP).astype(int)  # and on stairs, a line wherever they rise
    lines = (sorted({column * CELLS for column in range(columns + 1)} | {int(x) for x in np.flatnonzero((kind[:, 1:] != kind[:, :-1]).any(0)) + 1}),
             sorted({row * CELLS for row in range(rows + 1)} | {int(y) for y in np.flatnonzero((kind[1:] != kind[:-1]).any(1)) + 1}))
    return {'material': material, 'raised': raised, 'slab': slab, 'roof': float(vertices[:, 2].max()), 'footprint': footprint, 'lines': lines, 'depth': depth,
            'crest': crest, 'roomy': _roomy(material == STONE), 'deck': deck, 'deckDepth': deck_depth, 'stairs': stair}


def lines(found, row, column):
    """(columns, rows) of one tile's grid lines, counted in cells from its south-west corner."""
    return tuple([value - first for value in found['lines'][axis] if first <= value <= first + CELLS] for axis, first in ((0, column * CELLS), (1, row * CELLS)))


def walkmesh(found, row, column):
    """(vertices, faces with a material each) of one tile's walkmesh, in the tile's own space: a pair of faces to
    each box of the tile's grid lines, the floor's vertices first. Between two lines the cells are all alike, on both
    sides of every line, so a box has one material and one neighbour on each side."""
    material, depth, crest = found['material'], found['depth'], found['crest']; rows, columns = material.shape
    deck, deck_depth, stairs = found.get('deck'), found.get('deckDepth'), found.get('stairs')
    first_row, first_column = row * CELLS, column * CELLS; xs, ys = lines(found, row, column); cell = SIZE / CELLS

    def lift(y, x):
        """The rim of the slab is the ramp onto it: a corner on the slab's edge is on the ground, one RAMP cells in
        is up, and so is one on a crest."""
        around = [(r, c) for r in (first_row + y - 1, first_row + y) for c in (first_column + x - 1, first_column + x) if 0 <= r < rows and 0 <= c < columns]
        least = min(int(depth[cell]) for cell in around) if len(around) == 4 else 0
        ground = found['slab'] if least and any(crest[cell] for cell in around) else found['slab'] * min(least, RAMP) / RAMP
        if stairs is not None and len(around) == 4 and any(stairs[cell] > 0 for cell in around):
            # On stairs: the mean of the open cells round the corner, each at the height of its stairs, its deck or the ground
            return float(np.mean([float(stairs[cell]) if stairs[cell] > 0 else float(deck[cell]) if deck[cell] > 0 else ground
                                  for cell in around if material[cell] == STONE]))
        heights = [float(deck[cell]) for cell in around if deck[cell] > 0] if deck is not None else []
        if not heights or len(around) < 4:
            return ground
        if min(heights) > DECK:  # a deck climbed only by its stairs is at its height right to its closed edge
            return min(heights)
        # On a deck: up from the ground at its edge to its height RAMP cells in (`survey`)
        return ground + (min(heights) - ground) * min(min(int(deck_depth[cell]) for cell in around), RAMP) / RAMP
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


def _roomy(walk, room=None):
    """The walk cells a character has room to stand on: those in some block of walk cells a metre square, all of it the
    group's own: a kerb at the group's edge is no way through it, however open the next tile. A strip narrower than
    that joins nothing: the Ares Depot's first nodes took a
    strip of half to three quarters of a metre down its east side for a way through, and walkers sent round it from
    four tiles away stopped at the corner or never set out (client, 2026-11-11)."""
    room = EXIT if room is None else room
    padded = np.pad(walk, room, constant_values=False)
    block = np.lib.stride_tricks.sliding_window_view(padded, (room, room)).all((-1, -2))
    wide = np.zeros_like(padded)
    for down in range(room):
        for along in range(room):
            wide[down:down + block.shape[0], along:along + block.shape[1]] |= block
    return wide[room:-room, room:-room]


def _turned(parts, quarter):
    """A letter's parts (PATH_NODES) turned counter-clockwise by `quarter` quarters."""
    return [''.join('NWSE'[('NWSE'.index(side) + quarter) % 4] for side in part) for part in parts]


def _sees(walk, one, other):
    """Whether a character can walk between two cells of a tile over walk cells without going more than ASIDE cells off
    the straight line between them."""
    rows, columns = np.indices(walk.shape); (y0, x0), (y1, x1) = one, other; dy, dx = y1 - y0, x1 - x0
    along = np.clip(((rows - y0) * dy + (columns - x0) * dx) / max(dy * dy + dx * dx, 1), 0, 1)
    near = np.hypot(rows - y0 - along * dy, columns - x0 - along * dx) <= ASIDE
    labels, _ = _masses(walk & near)
    return bool(labels[one] and labels[one] == labels[other])


def path_node(found, row, column):
    """One tile's path node, as the tile alone would take it: {node, turn, exits, offPath}.

    A side is an exit where the ground is open for a metre within REACH of its middle, on this tile and on the one
    beyond (ground is taken to lie beyond the group's own edge): the game finds its own way to an opening that is a
    little off the side's middle, where the engine puts the exit (a yard entered only by a gap 2.75 metres off the
    middle of a side was not walked into, from far or from the next tile, until that side was called an exit: client,
    2026-11-11). Where a side opens onto two grounds of the tile that do not join, the opening nearest its middle
    counts. Two exits are joined only where a walk between their openings, over ground with room to stand on, stays
    within ASIDE of the straight way: the engine walks a character from one to the other, and gives up a walk whose
    route goes round a wall (ASIDE). The node chosen has no exit that is not one and joins no two that are not joined;
    of those it is the one with the most exits, then the most of them joined, then the most ground reached. So what it
    gets wrong, where no letter fits, is a way left unsaid, never a way through a wall. A group takes its tiles' nodes
    together (`path_nodes`), and a walk check in the client can still show a tile needs another (`stated`).
    Only ground with room to stand on counts, as an opening or as a way between two (`_roomy`).
    exits: the sides the node leaves by, of N, W, S, E. offPath: the cells of the tile with room to stand on that no
    exit reaches: ground a walk from another tile will not be planned onto."""
    tile = _options(found, row, column); (*_, reached), letter, turn, exits, _ = tile['options'][0]
    return {'node': letter, 'turn': turn, 'exits': ''.join(side for side in 'NWSE' if side in exits), 'offPath': int(tile['walk'].sum()) - reached}


def _options(found, row, column):
    """The path nodes one tile's ground allows, its best first (`path_node`): {walk, masses, region, options}, an option
    (score, letter, turn, exits, the exits joined in each of its parts)."""
    material = found['material']; rows, columns = material.shape; r0, c0 = row * CELLS, column * CELLS
    roomy = found['roomy'] if 'roomy' in found else _roomy(material == STONE); walk = roomy[r0:r0 + CELLS, c0:c0 + CELLS]; masses, _ = _masses(walk); along = slice(None)
    inside = {'N': (CELLS - 1, along), 'S': (0, along), 'W': (along, 0), 'E': (along, CELLS - 1)}
    beyond = {'N': (r0 + CELLS, slice(c0, c0 + CELLS)), 'S': (r0 - 1, slice(c0, c0 + CELLS)), 'W': (slice(r0, r0 + CELLS), c0 - 1), 'E': (slice(r0, r0 + CELLS), c0 + CELLS)}
    region, opening = {}, {}
    for side in 'NWSE':
        at = beyond[side]; line, limit = (at[0], rows) if side in 'NS' else (at[1], columns)
        clear = walk[inside[side]] & (roomy[at] if 0 <= line < limit else True)
        edges = np.flatnonzero(np.diff(np.concatenate([[0], clear.astype(int), [0]]))).tolist()  # where each open stretch starts and ends
        # (how far the opening lies from the side's middle, its first cell), of the openings wide enough
        ways = [(max(start - CELLS / 2, CELLS / 2 - end, 0), start, end) for start, end in zip(edges[::2], edges[1::2]) if end - start >= EXIT]
        if ways and min(ways)[0] <= REACH:
            _, start, end = min(ways); along_side = min(max(CELLS // 2, start), end - 1)  # its cell nearest the middle
            region[side] = int(masses[inside[side]][start])
            opening[side] = (inside[side][0], along_side) if side in 'NS' else (along_side, inside[side][1])
    joined = {frozenset((one, other)): _sees(walk, opening[one], opening[other]) for one in opening for other in opening if one < other}
    options = []
    for letter, parts in PATH_NODES.items():
        for quarter in range(4):
            turned = _turned(parts, quarter); exits = ''.join(turned)
            if any(side not in region for side in exits) or not all(joined[frozenset((one, other))] for part in turned
                                                                  for at, one in enumerate(part) for other in part[at + 1:]):
                continue
            reached = int((walk & np.isin(masses, [region[side] for side in exits])).sum())
            score = (len(exits), sum(len(part) * (len(part) - 1) // 2 for part in turned), reached)
            options.append((score, letter, quarter * 90, exits, turned))
    options.sort(key=lambda option: option[0], reverse=True)  # stable: of equals, the first in the table; T, with no exit, fits any tile
    return {'walk': walk, 'masses': masses, 'region': region, 'options': options}


def _ways_out(parts):
    """Of the tiles' node parts, {(row, column): [part, ...]} as `_turned` gives them, those a walk from the ground round
    the group can be planned through: {(row, column, index)}. A side joins the part of the next tile that leaves by the
    facing side, and a side on the group's edge joins the ground round it."""
    parent = {}

    def find(at):
        while parent.setdefault(at, at) != at:
            at = parent[at]
        return at
    beyond = {'N': (1, 0, 'S'), 'S': (-1, 0, 'N'), 'W': (0, -1, 'E'), 'E': (0, 1, 'W')}
    for (row, column), turned in parts.items():
        for index, part in enumerate(turned):
            for side in part:
                down, along, facing = beyond[side]; there = (row + down, column + along)
                if there not in parts:
                    parent[find((row, column, index))] = find('round')
                for other, part_there in enumerate(parts.get(there, ())):
                    if facing in part_there:
                        parent[find((row, column, index))] = find((*there, other))
    return {(*key, index) for key, turned in parts.items() for index in range(len(turned)) if find((*key, index)) == find('round')}


def cut_off(nodes):
    """The exits of a group's path nodes ({(row, column): {node, turn, ...}}) that lead nowhere a walk from round the
    group comes: [(row, column, sides)], each a node part no way out joins (`_ways_out`)."""
    parts = {key: _turned(PATH_NODES[one['node']], one['turn'] // 90) for key, one in nodes.items()}; out = _ways_out(parts)
    return [(*key, part) for key, turned in sorted(parts.items()) for index, part in enumerate(turned) if (*key, index) not in out]


def path_nodes(found, rows, columns, stated=None, *, unplanned=False):
    """Each tile's path node, {(row, column): {node, turn, exits, offPath}}, chosen for the group as a whole: of the
    nodes each tile's ground allows (`path_node`), the ones that let a walk from the ground round the group be planned
    onto the most of its ground, then the ones that leave the fewest exits cut off from every way out (`cut_off`), then
    the ones the tiles would take alone. A tile's own best can leave ground no walk reaches: the Saeder-Krupp yard's
    apron tile alone would have left its north side, the bay's only way out, joined to nothing (2026-11-12). And two
    tiles can each leave alone the side they share where a building stands across the line between them: the walk
    reaches all their ground by their other sides, but the engine takes a target by that side for the side's own, and
    gives up the walk. The rail freight depot's walkers to its warehouse door and to its crane's north leg, both on the
    line between its middle columns, walked straight at them and stopped against the loading platform (client,
    2026-11-13). offPath: the ground of the tile no walk from round the group is planned onto. With `unplanned`,
    returns (nodes, those cells of the group's), [row, column] from the south-west.

    `stated` ({(row, column): (letter, turn)}) gives tiles the nodes a walk check in the client has shown walks need,
    where the engine does not walk as these rules expect; the others are chosen round them. A stated node leaves its
    tile only by sides open there. The engine gives up a walk whose route it cannot follow and walks straight at the
    target instead: the yard's walkers to its door gave up while the door's tile split its north ground between two
    regions, and to its bay while the apron's tile joined only its south side to the bay's (client, 2026-11-12)."""
    tiles = {(row, column): _options(found, row, column) for row in range(rows) for column in range(columns)}
    for tile in tiles.values():  # the walk cells of each mass, so a choice's reach is a sum
        labels, counts = np.unique(tile['masses'][tile['walk']], return_counts=True); tile['size'] = dict(zip(labels.tolist(), counts.tolist()))
    for (row, column), (letter, turn) in (stated or {}).items():
        require((row, column) in tiles, f'A stated path node is for a tile of the group: t{row}{column}')
        require(letter in PATH_NODES and turn in (0, 90, 180, 270), f'A stated path node is a letter of PATH_NODES turned 0, 90, 180 or 270: t{row}{column}')
        tile = tiles[(row, column)]
        turned = _turned(PATH_NODES[letter], turn // 90); exits = ''.join(turned)
        require(all(side in tile['region'] for side in exits), f'A stated path node leaves t{row}{column} only by sides open there: {letter} {turn} leaves by {exits}')
        reached = sum(tile['size'].get(mass, 0) for mass in {tile['region'][side] for side in exits})
        tile['options'] = [((len(exits), 0, reached), letter, turn, exits, turned)]
    chosen = dict.fromkeys(tiles, 0)

    def planned():
        """({(row, column): the walk cells a walk from round the group is planned onto}, how many parts are cut off)."""
        parts = {key: tile['options'][chosen[key]][4] for key, tile in tiles.items()}; out = _ways_out(parts)
        return ({key: sum(tile['size'].get(mass, 0) for mass in {tile['region'][side] for index, part in enumerate(parts[key]) for side in part
                                                                  if (*key, index) in out}) for key, tile in tiles.items()},
                sum(len(turned) for turned in parts.values()) - len(out))

    def value():
        reached, cut = planned()
        return sum(reached.values()), -cut, -sum(chosen.values())
    def better(keys):
        """Try every choice for these tiles together; keep the best if it beats what there is."""
        nonlocal best
        was = [chosen[key] for key in keys]; found_better = None
        for indices in itertools.product(*[range(len(tiles[key]['options'])) for key in keys]):
            chosen.update(zip(keys, indices)); now = value()
            if now > best:
                best, found_better = now, indices
        chosen.update(zip(keys, found_better or was))
        return found_better is not None
    best = value()
    # Each change reaches more, or as much from nodes the tiles would sooner take, so this ends. A way through two
    # tiles may need both to change at once: the yard's bay is reached only when its apron's tile joins its north side to
    # its south and the tile south of that joins its north side on.
    pairs = [(key, (key[0] + down, key[1] + along)) for key in tiles for down, along in ((1, 0), (0, 1)) if (key[0] + down, key[1] + along) in tiles]
    while any(better([key]) for key in tiles) or any(better(list(pair)) for pair in pairs):
        pass
    reached = planned()[0]
    if unplanned:
        parts = {key: tile['options'][chosen[key]][4] for key, tile in tiles.items()}; out = _ways_out(parts)
        cells = np.zeros((rows * CELLS, columns * CELLS), bool)
        for key, tile in tiles.items():
            masses = [tile['region'][side] for index, part in enumerate(parts[key]) for side in part if (*key, index) in out]
            cells[key[0] * CELLS:(key[0] + 1) * CELLS, key[1] * CELLS:(key[1] + 1) * CELLS] = tile['walk'] & ~np.isin(tile['masses'], masses)
    nodes = {key: {'node': letter, 'turn': turn, 'exits': ''.join(side for side in 'NWSE' if side in exits), 'offPath': int(tile['walk'].sum()) - reached[key]}
            for key, tile in tiles.items() for _, letter, turn, exits, _ in [tile['options'][chosen[key]]]}
    return (nodes, cells) if unplanned else nodes


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


def _level_cut(card, height, light=None):
    """A halo card cut level at the height above which things may be hidden: [(card, whether it is above)].

    light: the lit parts the card spreads, as `glow.halo` gives them. Each light, a patch of lit pixels that touch, is
    on the side of the height where it lies; one the height passes through is on both, unless it reaches less than FOOT
    metres past it (a sign whose foot dips under the height goes with its body: cut there, the glow under a hidden sign
    was left hanging over the door). This goes by how far a light reaches, not by how much of it: lights that stand
    close come as one patch, and a small sign on top of a wide lit wall is still a sign. A card goes or stays whole
    with its lights: a sign above the height takes the glow under it along when it is hidden, and the glow over a
    window stays. A card with light on both sides, a sign over windows on a small building or one tall light, is cut
    at the height, so the sign's glow goes with the sign and the windows' stays. A card whose light is not known, or is
    all in patches under LIT, is never cut and goes by its middle."""
    low, high = card[0][0][2], card[2][0][2]; whole = [(card, height is not None and (low + high) / 2 >= height)]
    if height is None or light is None or not low < height < high:
        return whole
    share = (height - low) / (high - low); line = int(round((1 - share) * len(light)))  # the picture's rows above the height
    patches, count = _masses(light > 0); metre = (high - low) / len(light); sides = set()
    for patch in np.flatnonzero(np.bincount(patches.ravel(), light.ravel(), count + 1) >= LIT):  # the ground between the lights, patch 0, holds no light
        rows = np.flatnonzero((patches == patch).any(1)); over, under = max(line - rows[0], 0) * metre, max(rows[-1] + 1 - line, 0) * metre
        sides |= {side for side, reach in ((True, over), (False, under)) if reach >= min(FOOT, (over + under) / 2)}  # a light shorter than two feet is on both sides at its middle
    if len(sides) < 2:
        return [(card, sides.pop())] if sides else whole

    def at(bottom, top):
        (start, (u0, v0)), (end, (u1, v1)) = bottom, top
        return tuple(start[axis] + share * (end[axis] - start[axis]) for axis in range(3)), (u0 + share * (u1 - u0), v0 + share * (v1 - v0))
    left, right = at(card[0], card[3]), at(card[1], card[2])
    return [([card[0], card[1], right, left], False), ([left, right, card[2], card[3]], True)]


def model_text(name, parts, material, ground, cards, walk, *, lights=(), fade=None, cap=(), card_light=None, card_bitmaps=None):
    """One tile's ASCII model. parts: [(vertices, normals, uvs, faces)] of the building, in the tile's space; a fifth
    value, true, marks a part the game may hide (`tilefade`), and a sixth names the picture a part shows where that is not
    `material` (a fence's sheets). ground: the texture of the ten-metre square under it, laid
    twice across the tile as the plain tiles lay theirs. lights: the places of its main lights. fade: the height above
    which things may be hidden; a halo card whose light is above it goes with them, and one with light on both sides of
    it is cut there (`_level_cut`). card_light: each card's light, as `glow.halo` gives it; without it no card is cut. cap: the
    lid drawn at that height only while they are hidden ([(x0, y0, x1, y1)]), so the building is not seen hollow.
    card_bitmaps: the halo picture each card shows, where a group's models each have their own (`material`_h else)."""
    require(len(name) <= 16 and name == name.lower() and name.replace('_', '').isalnum(), 'A tile model name is a lowercase resref: ' + name)
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', 'setanimationscale 1.0',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode']
    common = ['  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1', '  render 1', '  shadow 0', '  rotatetexture 0', '  tilefade 0']
    half = SIZE / 2
    lines += [f'node trimesh {name}_g', f'  parent {name}', *common, f'  bitmap {ground}', '  verts 4', f'    {-half} {-half} 0', f'    {half} {-half} 0',
              f'    {-half} {half} 0', f'    {half} {half} 0', '  tverts 4', '    0 2 0', '    2 2 0', '    0 0 0', '    2 0 0', '  normals 4', *['    0 0 1'] * 4,
              '  faces 2', '    2 0 3 1 2 0 3 1', '    3 0 1 1 3 0 1 1', 'endnode']
    number = 0
    for vertices, normals, uvs, faces, *more in parts:
        mesh = [*common[:-1], '  tilefade 1'] if more and more[0] else common
        for used, part in convert.split(faces):
            lines += [f'node trimesh {name}_m{number}', f'  parent {name}', *mesh, f'  bitmap {more[1] if len(more) > 1 else material}', f'  verts {len(used)}']; number += 1
            lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in vertices[used].tolist()]
            lines += [f'  tverts {len(used)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in uvs[used].tolist()]
            lines += [f'  normals {len(used)}'] + [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in normals[used].tolist()]
            lines += [f'  faces {len(part)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in part.tolist()] + ['endnode']
    require(card_light is None or len(card_light) == len(cards), 'Each halo card has its own light, or none has')
    bitmaps = card_bitmaps or [f'{material}_h'] * len(cards); require(len(bitmaps) == len(cards), 'Each halo card shows one picture')
    cut = [(piece, bitmap) for card, light, bitmap in zip(cards, card_light or [None] * len(cards), bitmaps) for piece in _level_cut(card, fade, light)]
    cards = [card for (card, _), _ in cut]
    for index, ((card, above), bitmap) in enumerate(cut):
        lines += [f'node trimesh {name}_halo{index}', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {bitmap}', '  render 1', '  shadow 0', '  rotatetexture 0', f'  tilefade {1 if above else 0}', '  transparencyhint 1', '  alpha 1', '  verts 4']
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


def share_cards(cards, rows, columns, corner, card_light=None):
    """{(row, column): [(card, light)]}: each halo card cut along the tile lines it crosses, in each tile's own space,
    with its part of the card's light (`card_light`, as `glow.halo` gives it; None without). A card stands upright
    facing along x or along y, so it runs along the other of the two and is cut along that."""
    require(card_light is None or len(card_light) == len(cards), 'Each halo card has its own light, or none has')
    shared = {}; counts = (columns, rows)
    for card, light in zip(cards, card_light or [None] * len(cards)):
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
            piece = [(at(near, start[2]), (u(near), v_bottom)), (at(far, start[2]), (u(far), v_bottom)), (at(far, upper[2]), (u(far), v_top)), (at(near, upper[2]), (u(near), v_top))]
            first, last = sorted(round(float((value - start[along]) / (end[along] - start[along]) * light.shape[1])) for value in (near, far)) if light is not None else (0, 0)
            shared.setdefault((row, column), []).append((piece, light[:, first:last] if light is not None else None))
    return shared


def doorstep(found, corner, at, facing):
    """Where a door's hook goes, and how it is turned: ((x, y, z), the set file's orientation, metres drawn out).

    `at` is the middle of the door's foot on the finished model and `facing` the way the door looks out, in degrees
    from east towards north (90 is north). The hook is drawn out along that way to the first spot with open ground all
    round it, since a player uses a door by walking to its hook and a hook in closed ground is never reached. The set
    file turns a door from the model's own lie, which is across x and looking south: a door that looks north is turned
    180, one that looks west 270. (Seen in the client on 2026-11-11: at the facing itself the invisible door stood
    out of the wall at a right angle; at facing + 90 it lay in the doorway and a player sent to it from another area
    arrived outside, in front of it.)"""
    import math
    material = found['material']; rows, columns = material.shape; cell = SIZE / CELLS
    out = np.array([math.cos(math.radians(facing)), math.sin(math.radians(facing))]); start = np.asarray(at[:2], float)
    room = DOOR_SIDE + (DOOR_ROOM - DOOR_SIDE) * np.abs(out)  # the open ground asked for, along x and along y
    for step in range(int(DOOR_REACH / (cell / 2)) + 1):
        point = start + out * step * cell / 2
        low = np.floor((point - room - corner) / cell).astype(int); high = np.floor((point + room - corner) / cell).astype(int)
        patch = (slice(low[1], high[1] + 1), slice(low[0], high[0] + 1))
        if (low >= 0).all() and high[0] < columns and high[1] < rows and (material[patch] == STONE).all():
            # The hook keeps the height of the door's foot, which both buildings so far have within a step of the ground
            # in front of them. Drawn out from a door on a high sill or at the head of steps it would hang in the air,
            # and no such door has been tried in the client: it is refused until one is.
            ground = found['slab'] * np.where(found['crest'][patch], RAMP, np.minimum(found['depth'][patch], RAMP)) / RAMP
            if found.get('deck') is not None:  # and onto a deck, as `walkmesh` raises it
                ground = np.where(found['deck'][patch] > 0, ground + (found['deck'][patch] - ground) * np.minimum(found['deckDepth'][patch], RAMP) / RAMP, ground)
            apart = max(float(at[2]) - float(ground.min()), float(ground.max()) - float(at[2]))
            require(apart <= DOOR_STEP, f"The ground the door's hook is drawn out to lies {apart:.2f} metres from the door's foot in height, more than the "
                    f'{DOOR_STEP} a hook has been seen to work at: a door on a sill or steps needs the height of its hook settled in the client first')
            return (round(float(point[0]), 3), round(float(point[1]), 3), float(at[2])), float((facing + 90.0) % 360.0), round(step * cell / 2, 3)
    require(False, f'The door has no open ground within {DOOR_REACH} metres in front of it: a player could not reach it')


def join(meshes, keys=('vertices', 'normals', 'uvs', 'faces')):
    """Meshes joined into one: their points stacked, and each one's faces moved past the points of those before it."""
    starts = np.cumsum([0, *(len(one['vertices']) for one in meshes[:-1])])
    # Only the faces are moved: adding nothing to the rest would still turn their -0.0 into 0.0, and the tiles written with them.
    return {key: np.vstack([np.asarray(one[key]) + start if key == 'faces' else one[key] for one, start in zip(meshes, starts)]) for key in keys}


def merge_parts(parts):
    """A group's parts, (texture, finished model, colour), with those of one texture joined into one model: a model
    placed more than once (the yard's five fence sections) is one model of the group, with its sheets and halo cards."""
    found = {}
    for texture, one, colour in parts:
        found.setdefault(texture, ([], colour))[0].append(one)
    merged = []
    for texture, (ones, colour) in found.items():
        whole = {**ones[0], **join(ones)} if len(ones) > 1 else ones[0]
        if len(ones) > 1 and ones[0].get('wire'):
            whole['wire'] = {**ones[0]['wire'], **join([one['wire'] for one in ones])}
        if len(ones) > 1 and ones[0].get('card'):
            whole['card'] = ones[0]['card']._replace(cards=[card for one in ones for card in one['card'].cards], light=[light for one in ones for light in one['card'].light])
        merged.append((texture, whole, colour))
    return merged


WALK_PICTURE = 'walk.png'  # beside a group's tile sources: its walk cells, a pixel each, north up
WALK_COLOURS = {'roomy': (60, 170, 60), 'narrow': (25, 85, 25), 'building': (170, 40, 40), 'closed': (205, 125, 40), 'unplanned': (150, 215, 150)}
POCKET = 5.0  # metres further than straight in that a walk must go round before ground counts as hard to reach
BACK_OFF = 2  # cells a side's walker stands off what stops it coming in


def walk_picture(found, unplanned=None):
    """A group's walk cells as one picture, a pixel a cell and north up: ground with room to stand on (`_roomy`), ground
    too narrow for that (which `survey` closes now; a picture of a survey before that has it), the building where it
    stands at eye height, and the lesser things in the way. It shows where a
    character can go, and the walkers of `checks.group` are sent by it (the Saeder-Krupp yard's were picked from one
    drawn by hand, 2026-11-12)."""
    from PIL import Image
    material = found['material']; picture = np.zeros((*material.shape, 3), np.uint8)
    picture[material == STONE] = WALK_COLOURS['narrow']; picture[found['roomy']] = WALK_COLOURS['roomy']
    if unplanned is not None:  # pale: ground with room that no walk from round the group is planned onto (`path_nodes`)
        picture[found['roomy'] & unplanned] = WALK_COLOURS['unplanned']
    picture[material == OBSCURING] = WALK_COLOURS['building']; picture[material == NONWALK] = WALK_COLOURS['closed']
    return Image.fromarray(picture[::-1])


def read_walk(path, planned=False):
    """The cells of a group's walk picture (`walk_picture`) a character has room to stand on, [row, column] from the
    south-west."""
    from PIL import Image
    with Image.open(path) as image:
        picture = np.asarray(image.convert('RGB'))[::-1]
    known = np.zeros(picture.shape[:2], bool)
    for colour in WALK_COLOURS.values():
        known |= (picture == colour).all(-1)
    require(known.all(), f'{path} is not a walk picture')
    roomy = (picture == WALK_COLOURS['roomy']).all(-1)
    return roomy if planned else roomy | (picture == WALK_COLOURS['unplanned']).all(-1)


def read_blocked(path):
    """The cells of a group's walk picture (`walk_picture`) where no one stands: what stands in the way and the closed
    edge round it, [row, column] from the south-west."""
    from PIL import Image
    with Image.open(path) as image:
        picture = np.asarray(image.convert('RGB'))[::-1]
    return (picture == WALK_COLOURS['building']).all(-1) | (picture == WALK_COLOURS['closed']).all(-1)


def walk_targets(roomy, planned=None):
    """Where walkers are sent in a group, {label: (x, y)} in metres from its south-west corner. On each side the ground
    a walker reaches last coming straight in from the middle of the group's edge, BACK_OFF cells short of what stops it
    (the building, a fence): none where nothing stands across the middle from that side, or where the edge is closed.
    And `pocket`: the ground a walk must go furthest round to reach, where that is more than POCKET metres further
    than straight in from the nearest edge: a yard with few ways in, which short walks reach and long ones may not
    (this module's docstring). Walks go over ground with room to stand on, eight ways, as the game's are planned.
    planned: the ground walks from round the group are planned onto (`read_walk`), where the pocket is sought: the rail
    freight depot's platform, reached only by its stairs at one end, is no tile's exit, and long walks to it give up."""
    import heapq
    rows, columns = roomy.shape; step = SIZE / CELLS; targets = {}
    lines = {'south': [(row, columns // 2) for row in range(rows)], 'north': [(row, columns // 2) for row in range(rows - 1, -1, -1)],
             'west': [(rows // 2, column) for column in range(columns)], 'east': [(rows // 2, column) for column in range(columns - 1, -1, -1)]}
    for label, cells in lines.items():
        open_run = next((index for index, cell in enumerate(cells) if not roomy[cell]), None)
        if open_run:  # None: nothing stands across; 0: the edge itself is closed
            row, column = cells[max(open_run - 1 - BACK_OFF, 0)]; targets[label] = ((column + 0.5) * step, (row + 0.5) * step)
    far = np.full(roomy.shape, np.inf); queue = []
    for row in range(rows):
        for column in range(columns):
            if roomy[row, column] and (row in (0, rows - 1) or column in (0, columns - 1)):
                far[row, column] = 0.0; queue.append((0.0, row, column))
    heapq.heapify(queue)
    while queue:
        cost, row, column = heapq.heappop(queue)
        if cost > far[row, column]:
            continue
        for down, along in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            near = (row + down, column + along)
            if 0 <= near[0] < rows and 0 <= near[1] < columns and roomy[near]:
                reach = cost + (1.4142 if down and along else 1.0)
                if reach < far[near]:
                    far[near] = reach; heapq.heappush(queue, (reach, *near))
    row_index, column_index = np.indices(roomy.shape)
    straight = np.minimum.reduce([row_index, rows - 1 - row_index, column_index, columns - 1 - column_index]).astype(float)
    detour = np.where(np.isfinite(far), far - straight, -np.inf) * step
    if planned is not None:  # ground no walk is planned onto (`path_nodes`) is reached only by short walks: no long walk is sent there
        detour = np.where(planned, detour, -np.inf)
    if detour.max() > POCKET:
        row, column = map(int, np.unravel_index(int(np.argmax(detour)), detour.shape)); targets['pocket'] = ((column + 0.5) * step, (row + 0.5) * step)
    return targets


def group(name, made, folder, *, ground, colour=None, ground_colour=(0.4, 0.4, 0.4), fade=None, door=None, parts=(), nodes=None):
    """Write the tile models and walkmeshes of a finished model (`convert.shape`) into `folder`; returns
    {rows, columns, tiles: [{model, row, column, faces, walkFaces, path, image, lights, doors}], notes} with the tiles
    in the set file's order. notes: what to look at before the group is installed, in words: ground no exit of its tile
    reaches, and a tile with more walk faces than any stock one.

    colour: the model's colour texture (0-1 array); with it each tile gets its picture for the area map, `image`, drawn
    over `ground_colour`. fade: the height in metres above which the building may be hidden. door: {at: [x, y, z],
    facing, type} on the finished model; it becomes a door record of the tile its hook lies in (`doorstep`). parts: the
    other models of the group as (texture, finished model placed in the group's space, colour), each drawn with its own
    picture, halo and fence sheets, and with the building one ground to walk on, cut into the same tiles; a model placed
    more than once comes once for each place, and they are joined (`merge_parts`). A part marked `underfoot` (railway
    track) is drawn but not surveyed: the ground is walked flat across it, and it may run off the group's edges, where
    a raised slab may not. It stands no higher than the knee."""
    require(len(name) <= convert.TILE_NAME_LENGTH, 'A tile group name leaves four characters for the tile: ' + name)
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    parts = merge_parts(parts); meshes = [(name, made, colour), *parts]
    require(len({texture for texture, _, _ in meshes}) == len(meshes), "A part of a group shows a texture of its own, not the group's")
    shaped = [one for _, one, _ in meshes]; vertices = np.vstack([one['vertices'] for one in shaped])
    laid = [texture for texture, one, _ in parts if one.get('underfoot') and one['vertices'][:, 2].max() > KNEE + 1e-6]
    require(not laid, f'A part laid underfoot stands no higher than the knee, {KNEE} metres: ' + ', '.join(laid))
    walked = join([one for one in shaped if not one.get('underfoot')], ('vertices', 'faces'))
    wires = [(texture, one['wire']) for texture, one, _ in meshes if one.get('wire') is not None]
    barrier = tuple(join([wire for _, wire in wires], ('vertices', 'faces')).values()) if wires else None
    rows, columns, corner = layout(vertices); found = survey(walked['vertices'], walked['faces'], rows, columns, corner, barrier=barrier)
    require(fade is None or found['slab'] < fade < found['roof'], 'The fade height lies between the slab and the roof')

    def shared(points, polygons):  # each face's tile, by its middle, and whether it is above the fade height
        middle = points[polygons].mean(1)
        return np.clip(((middle[:, :2] - corner) // SIZE).astype(int), 0, [columns - 1, rows - 1]), (middle[:, 2] >= fade if fade is not None else np.zeros(len(polygons), bool))
    homes = [shared(one['vertices'], one['faces']) for one in shaped]; wire_homes = [shared(wire['vertices'], wire['faces']) for _, wire in wires]
    cards = {}
    for texture, one, _ in meshes:
        for spot, held in (share_cards(one['card'].cards, rows, columns, corner, one['card'].light) if one['card'] else {}).items():
            cards.setdefault(spot, []).extend((card, light, f'{texture}_h') for card, light in held)
    tiles, notes = [], []
    pictures = (minimaps(made['vertices'], made['uvs'], made['faces'], colour, rows, columns, corner, ground_colour,
                         more=[(one['vertices'], one['uvs'], one['faces'], shade) for _, one, shade in parts])
                if colour is not None and all(shade is not None for _, _, shade in parts) else {})
    if door is not None:
        spot, orientation, drawn = doorstep(found, corner, door['at'], float(door.get('facing', 0.0)))
        at = np.asarray(spot, float); cell = np.clip(((at[:2] - corner) // SIZE).astype(int), 0, [columns - 1, rows - 1])
    if fade is not None:
        from PIL import Image
        Image.new('RGB', (4, 4)).save(folder / f'{CAP}.tga')
    nodes, unplanned = path_nodes(found, rows, columns, {(int(key[1]), int(key[2])): (value['node'], value['turn']) for key, value in (nodes or {}).items()},
                                  unplanned=True)
    for row in range(rows):
        for column in range(columns):
            model = f'{name}_t{row}{column}'; centre = np.array([corner[0] + (column + 0.5) * SIZE, corner[1] + (row + 0.5) * SIZE, 0.0])
            shown = []; counts = {'faces': 0, 'fading': 0}
            # Each model's faces, and each fence's sheets, shared out to the tile their middles lie in, with that model's picture.
            for (texture, one, _), (home, high) in [*zip(meshes, homes), *zip([(f'{texture}_w', wire, None) for texture, wire in wires], wire_homes)]:
                here = (home[:, 0] == column) & (home[:, 1] == row); counts['faces'] += int(here.sum()); counts['fading'] += int((here & high).sum())
                for chosen, hidden in ((here & ~high, False), (here & high, True)):
                    if chosen.any():
                        used, local = np.unique(one['faces'][chosen], return_inverse=True)
                        shown.append((one['vertices'][used] - centre, one['normals'][used], one['uvs'][used], local.reshape(-1, 3), hidden, texture))
            walk = walkmesh(found, row, column); lights = light_places(found, row, column)
            halos = cards.get((row, column), [])
            text = model_text(model, shown, name, ground, [card for card, _, _ in halos], walk, lights=lights, fade=fade, card_light=[light for _, light, _ in halos],
                              card_bitmaps=[bitmap for _, _, bitmap in halos], cap=lid(found, row, column) if fade is not None else ())
            (folder / f'{model}.mdl').write_text(text, encoding='cp1252', newline='\n')
            (folder / f'{model}.wok').write_text(walk_text(model, walk), encoding='cp1252', newline='\n')
            one = {'model': model, 'row': row, 'column': column, 'faces': counts['faces'], 'fadingFaces': counts['fading'], 'walkFaces': int(len(walk[1])),
                   'path': nodes[(row, column)], 'lights': len(lights), 'doors': []}
            if one['path']['offPath']:
                notes.append(f'{model}: {one["path"]["offPath"]} walk cells that no walk from round the group is planned onto (`path_nodes`)')
            for sides in [sides for at_row, at_column, sides in cut_off(nodes) if (at_row, at_column) == (row, column)]:
                notes.append(f'{model}: its path node leaves by {sides} to nowhere a walk from round the group comes (`cut_off`): a target by that side is not reached')
            if one['walkFaces'] > WALK_FACES:
                notes.append(f'{model}: {one["walkFaces"]} walk faces, where no stock tile has more than {WALK_FACES}')
            if (row, column) in pictures:
                from PIL import Image
                one['image'] = f'{name}_m{row}{column}'  # a 24-bit picture, stored bottom row first as the stock ones are
                Image.fromarray((np.clip(pictures[(row, column)], 0, 1) * 255).round().astype(np.uint8)).save(folder / f'{one["image"]}.tga')
            if door is not None and (cell == [column, row]).all():
                x, y, z = (at - centre).round(2).tolist()
                one['doors'].append({'type': int(door['type']), 'x': x, 'y': y, 'z': z, 'orientation': orientation, 'drawnOut': drawn})
            tiles.append(one)
    walk_picture(found, unplanned).save(folder / WALK_PICTURE)
    return {'rows': rows, 'columns': columns, 'slab': round(found['slab'], 3), 'roof': round(found['roof'], 3), 'fade': fade, 'tiles': tiles, 'notes': notes}


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


def tile_records(made, terrain):
    """The set file's record of each tile, in order: all four corners `terrain` at height 0, no crossers, and the
    main lights, doors and area-map picture the tile was built with (`doors` gives each tile's door records to write
    after it). Each tile states the path node it was built with (`path_node`); the same node serves for visibility, as
    it does in nearly every stock tile."""
    records = []
    for tile in made['tiles']:
        require('path' in tile, 'This group was built before each tile had its path node worked out: build it again')
        node, turn = tile['path']['node'], tile['path']['turn']
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
