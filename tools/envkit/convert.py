"""Turn a generated model into a game placeable: ASCII model, material file, DDS textures and collision.

The layout is the one working PBR placeables use (SWLOR's SWTOR conversions, read 2026-11-10): a dummy root and trimesh
nodes whose `bitmap` is also the name of the material file, shadows off on the dense mesh, colour as DXT1, the normal map
as two-channel ATI2 and the one-channel maps as ATI1.

A generated model has no real size and faces glTF's way (Y up, front along +Z). `fit` turns it to the game's axes (Z up,
front along +Y), scales it to a stated height in metres, centres it and stands it on the ground."""
import json
import re
import struct
import subprocess
from pathlib import Path

import numpy as np

from . import placeables, require

COMPONENT = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
TO_GAME = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])  # a rotation: glTF up (Y) to Z, glTF front (+Z) to +Y
NODE_VERTICES = 60000  # a compiled mesh node indexes its vertices with 16 bits
NAME_LENGTH = 14  # a resref is 16 characters and the maps add a two-character suffix
TILE_NAME_LENGTH = 12  # a tile group's models add four: _t and the tile's row and column
MAP_SUFFIXES = ('_n', '_s', '_r', '_i', '_o', '_h', '_g', '_e')  # a model's other pictures: relief, shine, roughness, glow, lights out, halo, glass, embers
NON_WALK = 7
RETOUCH = 2048  # pixels: the finest map of places a colour picture is retouched by
SLAT_GROOVE, SLAT_SHADE = 0.15, 0.3  # of a slat's pitch, each side of the joint, that darkens towards it; how much darker the joint is
WIRE = (118, 122, 126)  # galvanised steel
# A fence's wires are drawn on a small picture of their own, which its sheets repeat: its width in pixels, and the least
# pixels across a wire that still draw one.
WIRE_PICTURE, WIRE_TEXELS = 128, 2.5
PANEL_DEPTH = 0.6  # metres: the most a `mesh` box's texels may lie apart across the panel's run and still be one flat panel
FENCE_NEAR = 0.3  # metres: how near each end of a fence some part of the model must lie, since a fence hangs between its posts
OVERHEAD = 2.2  # metres: what hangs at least this high is walked under
DIELECTRIC = 0.04  # share of light a non-metal reflects head on
DOOR_LEAF = (1.9, 2.5)  # metres: how tall a door a character walks through may be
MEASURED = ('lit', 'paint', 'copy', 'smooth', 'mesh', 'fence', 'frame', 'close', 'clear', 'wheels', 'fill', 'built', 'move', 'glass', 'embers')  # what a game set states in metres on the finished model, beside a tile group's door and fade height
FILL_NEAR, FILL_WELD, FILL_MOST = 0.1, 0.002, 64  # metres from a stated point to a hole's rim; how near two corners are one place; a hole's most corners
STEP_RISE, RAIL_HEIGHT, POST_EVERY = 0.19, 0.95, 1.2  # metres: a built stair's most rise a step, its handrail's height over the nosings, posts at most this far apart
STAIR_STEEPEST = 1.2  # a built stair flight's most rise over its run (about 50 degrees): steeper, it is a ladder
COIL, COIL_SIDES = 0.03, 10  # a built coil of barbed wire: its wire's thickness, metres (thicker than wire, to be seen from the yard), and the straight lengths to a turn
TREAD, STRINGER, RAIL, POST = (0.04,), (0.05, 0.22), (0.045, 0.045), (0.045, 0.045)  # built stair members' sections, metres: tread thickness, stringer, rails, posts
GLASS_COLOUR, GLASS_STRENGTH, GLASS_FLAT, GLASS_MOST, GLASS_PICTURE = (150, 170, 185), 0.25, 0.02, 8, 64  # a pane's colour and how much of it is added to what stands behind; metres its corners may stand off its plane; its most corners; its picture's width
LIGHT_NEAR = 0.3  # metres a placeable's cast light may stand from the model: the game draws a flare where it stands
CLOSE_NEAR = 0.02  # how near one of the model's own vertices a closing face's stated corner lies, metres
PLACING = ('lift', 'turn', 'signTilt', 'length', 'level')  # what, with its height, places a model's parts: the boxes of a game set are on the model as lifted, turned, tilted, stretched and levelled
RETOUCHING = ('turn', 'length', 'level', 'tone', 'paint', 'copy', 'smooth', 'mesh', 'fence', 'frame', 'close', 'clear', 'inside', 'wheels', 'fill', 'built', 'move', 'glass', 'embers')  # what of a game set `shape` takes to turn, clear, close and retouch a model
WHEEL_BACK = 0.68  # metres from a car's middle to the back of each wheel: a wheelset's backs stand 1.360 m apart on standard gauge (track.GAUGE)
WHEEL_BLEND = 0.15  # metres over which a truck drawn in to gauge eases back to the car round it
DOOR_TYPE = 58  # the row of doortypes.2da every building's door hook takes: the invisible transition door (user, 2026-11-11, until further notice)
LEVEL_MOST = 0.3  # metres: the thickest a levelled floor marking is left
WALK_CELLS = 4  # cells to the gap that parts are told apart by (`standing`)
WALK_GAP = 0.6  # metres of clear ground that part two legs of a model walked under (`standing`): narrower, and no character passes between
UNDERFOOT_MOST = 0.45 # metres: the knee (`tile.KNEE`), the highest a placeable laid underfoot stands, as a part laid underfoot in a group
# A bed of embers (`ember_beds`): its picture's pixels and lumps, the sides and rings of its mound, the share of its
# radius the mound rises, and the seed its lumps are scattered from, so a model built again is the same.
EMBER_PICTURE, EMBER_COALS, EMBER_SIDES, EMBER_RINGS, EMBER_RISE, EMBER_SEED = 256, 45, 16, 3, 0.2, 7
# The radius of a bed, metres: its picture is laid once over it, so its lumps grow with it (9 cm across in the Ghost
# Riders barrel's 0.29, 18 at the most here); a wider fire's embers are not made yet.
EMBER_RADIUS = (0.05, 0.6)
FIRE_BIRTHRATE, FIRE_ANIM = 10, 0.0333333  # particles a second a fire is born with; seconds each of its on and off animations lasts, the stock flame's
FIRE_WIDTH = (0.1, 3.0)  # metres across a fire the game draws: a candle's to a bonfire's
# A panel the size of a door drawn in one flat colour (`blank_panels`): the cell its picture is read by, metres; the most
# the brightness may vary within a cell, as a share of the cell's own brightness (a dark door's flecks are faint), and
# between the cells of one panel (0-1); the least a panel measures each way; the share of its rectangle it fills; how
# far above the model's foot its sill may stand; the depth of one wall plane.
BLANK_CELL, BLANK_WITHIN, BLANK_BETWEEN, BLANK_LEAST, BLANK_FILL, BLANK_SILL, BLANK_PLANE = 0.2, 0.05, 0.05, 1.8, 0.8, 1.2, 0.15
BLANK_SIZE = 1024  # pixels across the map of the model's places a blank panel is looked for on
BLANK_SLATS, BLANK_RADIUS = 0.12, 0.08  # the repair a blank panel's note proposes: a roller door's slat pitch and the smoothing's reach, metres


def _accessor(document, binary, index):
    accessor = document['accessors'][index]; view = document['bufferViews'][accessor['bufferView']]
    kind = np.dtype(COMPONENT[accessor['componentType']]); width = WIDTH[accessor['type']]; count = accessor['count']
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0); stride = view.get('byteStride') or kind.itemsize * width
    rows = np.ndarray((count, width), kind, binary, start, (stride, kind.itemsize)).astype(float)
    if accessor.get('normalized'):
        rows /= float(np.iinfo(kind).max)
    return rows


def _matrix(node):
    if 'matrix' in node:
        return np.array(node['matrix'], float).reshape(4, 4).T
    x, y, z, w = node.get('rotation', [0, 0, 0, 1])
    turn = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    matrix = np.eye(4); matrix[:3, :3] = turn * np.array(node.get('scale', [1, 1, 1]), float); matrix[:3, 3] = node.get('translation', [0, 0, 0])
    return matrix


def read_glb(path):
    """(vertices, normals, uvs, faces) of every triangle primitive in the file, in the file's own space and units."""
    data = Path(path).read_bytes()
    require(data[:4] == b'glTF', 'Binary glTF required: ' + str(path))
    length, kind = struct.unpack_from('<II', data, 12)
    require(kind == 0x4E4F534A, 'glTF JSON chunk missing')
    document = json.loads(data[20:20 + length]); offset = 20 + length
    size, kind = struct.unpack_from('<II', data, offset)
    require(kind == 0x004E4942, 'glTF binary chunk missing')
    binary = data[offset + 8:offset + 8 + size]
    vertices, normals, uvs, faces = [], [], [], []; total = 0

    def walk(index, parent):
        nonlocal total
        node = document['nodes'][index]; world = parent @ _matrix(node)
        if 'mesh' in node:
            turn = np.linalg.inv(world[:3, :3]).T
            for primitive in document['meshes'][node['mesh']]['primitives']:
                attributes = primitive['attributes']
                require(primitive.get('mode', 4) == 4 and {'POSITION', 'NORMAL', 'TEXCOORD_0'} <= set(attributes),
                        'A model needs triangles with positions, normals and texture coordinates')
                points = _accessor(document, binary, attributes['POSITION'])
                normal = _accessor(document, binary, attributes['NORMAL']) @ turn.T
                index_rows = (_accessor(document, binary, primitive['indices']).astype(int).reshape(-1, 3) if 'indices' in primitive
                              else np.arange(len(points)).reshape(-1, 3))
                vertices.append(points @ world[:3, :3].T + world[:3, 3]); normals.append(normal)
                uvs.append(_accessor(document, binary, attributes['TEXCOORD_0'])[:, :2]); faces.append(index_rows + total)
                total += len(points)
        for child in node.get('children', []):
            walk(child, world)

    for root in document['scenes'][document.get('scene', 0)]['nodes']:
        walk(root, np.eye(4))
    require(faces, 'The model holds no mesh')
    return np.concatenate(vertices), np.concatenate(normals), np.concatenate(uvs), np.concatenate(faces)


def repair_normals(vertices, normals, faces):
    """Unit normals throughout. A generated model can carry zero normals (rooftop unit, 2026-11-10), which a compiled
    model cannot hold; those take the area-weighted normal of their own faces, or straight up where they have no area."""
    normals = np.array(normals, float); lengths = np.linalg.norm(normals, axis=1); bad = lengths < 1e-6
    if bad.any():
        summed = _of_faces(vertices, faces)
        normals[bad] = summed[bad]; lengths = np.linalg.norm(normals, axis=1)
        normals[lengths < 1e-12] = (0.0, 0.0, 1.0); lengths = np.linalg.norm(normals, axis=1)
    return normals / lengths[:, None], int(bad.sum())


def _of_faces(vertices, faces):
    """Each vertex's area-weighted sum of its faces' normals, by their winding."""
    of_face = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    summed = np.zeros((len(vertices), 3))
    for corner in range(3):
        np.add.at(summed, faces[:, corner], of_face)
    return summed


SIGHT_CELLS = 256  # pixels along a model's longest side when it is looked at from all round (`seen`)
SIGHT_CELL = 0.01  # metres: the smallest pixel
SIGHT_VIEWS = 64  # how many ways it is looked at
BACK_TO_BACK = 0.005  # metres: a face this near another that faces the other way, over it, is half of a two-faced sheet


def seen(vertices, faces, cells=SIGHT_CELLS, views=SIGHT_VIEWS, *, holes=None, both=None):
    """(front, back, whole): how many pixels of each face are the first thing seen of the model from outside, from its
    front (the side its corners run counter-clockwise on) and from behind, and how many it would fill were nothing in front of it. It is looked at from `views` ways spread evenly over
    the sky, down to a little below the horizon (the game never looks up from under the ground), each a picture of
    `cells` pixels along its longest side. Each face is laid down as spots, four to a pixel on average and at least one,
    so a sliver costs no more than its area; the spot nearest the eye wins its pixel. `holes`, a list, takes for each
    way it is looked at (square metres, the way): the pixels showing a face's back whose four neighbours show one too,
    so a patch of the model seen from behind and not the odd pixel along an edge. A face marked in `both` (a mask) is
    drawn from both sides and is no hole."""
    corner = np.asarray(vertices, float)[np.asarray(faces)]; size = max(float(np.ptp(corner.reshape(-1, 3), 0).max()) / cells, SIGHT_CELL)
    of_face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0]); twice = np.linalg.norm(of_face, axis=1)
    unit = of_face / np.maximum(twice, 1e-12)[:, None]
    owner = np.repeat(np.arange(len(corner)), np.maximum(np.random.default_rng(0).poisson(twice * 2 / size ** 2), 1))
    a, b = np.random.default_rng(1).random((2, len(owner))); fold = a + b > 1; a[fold], b[fold] = 1 - a[fold], 1 - b[fold]
    mine = corner[owner]; spots = mine[:, 0] + a[:, None] * (mine[:, 1] - mine[:, 0]) + b[:, None] * (mine[:, 2] - mine[:, 0])
    golden = np.pi * (3 - np.sqrt(5)); rise = np.linspace(1, -0.15, views); round_ = np.sqrt(1 - rise ** 2); turn = golden * np.arange(views)
    front, back, whole = np.zeros(len(corner)), np.zeros(len(corner)), np.zeros(len(corner))
    for eye in np.stack([round_ * np.cos(turn), round_ * np.sin(turn), rise], 1):
        right = np.cross(eye, [0.0, 0.0, 1.0]) if abs(eye[2]) < 0.99 else np.array([1.0, 0.0, 0.0]); right /= np.linalg.norm(right); up = np.cross(right, eye)
        across, down = np.floor(spots @ right / size).astype(np.int64), np.floor(spots @ up / size).astype(np.int64)
        across -= across.min(); down -= down.min(); pixel = across * (down.max() + 1) + down
        order = np.lexsort((-(spots @ eye), pixel)); first = order[np.r_[True, pixel[order][1:] != pixel[order][:-1]]]
        winner = owner[first]; toward = unit[winner] @ eye
        np.add.at(front, winner[toward > 0.1], 1); np.add.at(back, winner[toward < -0.1], 1)
        if holes is not None:
            grid = np.zeros((across.max() + 3, down.max() + 3), bool); behind = (toward < -0.1) if both is None else (toward < -0.1) & ~np.asarray(both)[winner]; grid[across[first][behind] + 1, down[first][behind] + 1] = True
            solid = grid[1:-1, 1:-1] & grid[:-2, 1:-1] & grid[2:, 1:-1] & grid[1:-1, :-2] & grid[1:-1, 2:]
            holes.append((float(solid.sum()) * size ** 2, [round(float(value), 2) for value in eye]))
        slant = np.abs(unit @ eye); whole += np.where(slant > 0.1, twice / 2 * slant / size ** 2, 0)
    return front, back, whole


def back_to_back(vertices, faces, which):
    """Which of the faces picked by `which` (a mask) lie on another face of the model that faces the other way, within
    `BACK_TO_BACK` of its plane, at the face's middle or at a point two thirds of the way from it to a corner: the back
    half of a sheet made of two faces, each drawn on one side."""
    corner = np.asarray(vertices, float)[np.asarray(faces)]
    of_face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0]); twice = np.linalg.norm(of_face, axis=1)
    unit = of_face / np.maximum(twice, 1e-12)[:, None]; found = np.zeros(len(corner), bool)
    first, along, across = corner[:, 0], corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0]
    d00, d01, d11 = (along * along).sum(1), (along * across).sum(1), (across * across).sum(1); denominator = d00 * d11 - d01 ** 2
    low, high = corner.min(1) - BACK_TO_BACK, corner.max(1) + BACK_TO_BACK  # each face's box: only faces whose box holds a point can hold it
    for index in np.flatnonzero(which):
        middle = corner[index].mean(0); points = np.vstack([middle, middle + (corner[index] - middle) * 2 / 3])
        reach = np.all((high >= points.min(0)) & (low <= points.max(0)), axis=1)
        other = np.flatnonzero(reach & (unit @ unit[index] < -0.99) & (denominator > 1e-18))
        offset = points[None] - first[other][:, None]  # (others, points, 3)
        near = np.abs((offset * unit[other][:, None]).sum(2)) <= BACK_TO_BACK
        d20, d21 = (offset * along[other][:, None]).sum(2), (offset * across[other][:, None]).sum(2)
        v = (d11[other][:, None] * d20 - d01[other][:, None] * d21) / denominator[other][:, None]
        w = (d00[other][:, None] * d21 - d01[other][:, None] * d20) / denominator[other][:, None]
        found[index] = (near & (v >= -1e-6) & (w >= -1e-6) & (v + w <= 1 + 1e-6)).any()
    return found


def turn_faces(vertices, faces, cells=SIGHT_CELLS, views=SIGHT_VIEWS):
    """`_turn_faces`, a large model's kept for its next build (`cache`)."""
    from . import cache
    vertices, faces = np.asarray(vertices, float), np.asarray(faces)
    turned, count = cache.arrays('winding', (vertices, faces, cells, views, Path(__file__)), lambda: _turn_faces(vertices, faces, cells, views), faces=len(faces))
    return np.array(turned), int(count)


def _turn_faces(vertices, faces, cells=SIGHT_CELLS, views=SIGHT_VIEWS):
    """(faces, turned): a face seen from outside mostly from behind (`seen`: more than twice as much, at least three
    pixels and a fifth of all it would show were nothing in front of it) turned round. The fifth keeps a face hidden
    behind another from being judged by the few pixels where the spots of the face in front miss. The game draws a face only from the side its corners run counter-clockwise on, so such a face
    is a hole onto whatever is behind it. From 2% to a quarter of the surface of each of the rail yard's and depot's 25
    generated models was wound so (2026-11-13), on surfaces otherwise wound right and in folds of them. A face judged by
    which side of it is open air instead turned the inner skins of thin double walls outward. A sheet seen from both
    sides (a sign, a fence) and a face never seen (the inside of a wall) are left as they are, and so is the back half
    of a sheet of two faces back to back (`back_to_back`), which ties with its front for every pixel: turned, it lay
    over its front, two faces on one plane for the game to draw either of (a third to over half of what was turned
    on each of the rail yard's models, 2026-11-13). Run before `turn_normals`, which then turns only the normals that point against a face wound right."""
    front, back, whole = seen(vertices, faces, cells, views); wrong = (back > 2 * front) & (back >= 3) & (back >= whole / 5); faces = np.array(faces)
    wrong &= ~back_to_back(vertices, faces, wrong)
    faces[wrong] = faces[wrong][:, [0, 2, 1]]
    return faces, int(wrong.sum())


def turn_normals(vertices, normals, faces):
    """(normals, turned): a shading normal that points against its faces' winding turned round. The game draws a face
    by its winding and lights it by its normals, so such a face shades dark in daylight: about a sixth of the rail yard's
    boxcar did, on both of its generations (2026-11-13)."""
    normals = np.array(normals, float); against = (normals * _of_faces(vertices, faces)).sum(1) < 0
    normals[against] *= -1
    return normals, int(against.sum())


def _backs(vertices, faces, parts):
    """Which faces lie in the boxes given backs ([{box}]): those whose middle a box holds. A box that holds none is refused."""
    middle = vertices[np.asarray(faces)].mean(1); chosen = np.zeros(len(faces), bool)
    for part in parts:
        low, high = np.sort(np.asarray(part['box'], float), axis=0); held = np.all((middle >= low) & (middle <= high), axis=1)
        require(bool(held.any()), f"A box given backs holds no face of the model ({part.get('part', 'backed part')})"); chosen |= held
    return chosen


def backed(vertices, normals, uvs, faces, parts=None):
    """The model with a back for every face: each face again, wound the other way on copies of its corners whose normals
    point the other way, at the same place on the picture. A box the generator drew from outside only, with openings in
    it, showed through them what stood behind it: its far walls are not drawn from inside. The rail yard's dumpster
    (through the gaps of its slatted lid, seen in the client, 2026-11-13) shows its own inside instead. With `parts`
    ([{box}], metres on the finished model) only the faces whose middle lies in a box get backs: the rail yard's crane
    had faces of its leg sills wound inward, so that from outside the client showed gaps there (user, 2026-11-13)."""
    faces = np.asarray(faces)
    if parts is not None:
        chosen = _backs(vertices, faces, parts)
        used, local = np.unique(faces[chosen], return_inverse=True); local = local.reshape(-1, 3) + len(vertices)
        return (np.vstack([vertices, vertices[used]]), np.vstack([normals, -np.asarray(normals)[used]]), np.vstack([uvs, uvs[used]]),
                np.vstack([faces, local[:, [0, 2, 1]]]))
    count = len(vertices)
    return (np.vstack([vertices, vertices]), np.vstack([normals, -np.asarray(normals)]), np.vstack([uvs, uvs]),
            np.vstack([faces, faces[:, [0, 2, 1]] + count]))


def gauged(vertices, normals, wheels):
    """The model with its trucks drawn in to the track: in each of `wheels`' spans along the car (x, metres on the
    finished model) and below its `top`, everything is drawn in across (y) about the car's middle so that the backs of
    its wheels, measured at `back` metres either side, stand WHEEL_BACK either side as a standard-gauge wheelset's do;
    it eases back to the car as it was over WHEEL_BLEND past the spans' ends and above the top. A generator draws the
    wheels under the car's sides: the rail yard's cars had their wheels 0.15 to 0.2 m outside the rails (user: "fix the
    wheel spacing on the rolling stock", 2026-11-13)."""
    x, z = vertices[:, 0], vertices[:, 2]; along = np.zeros(len(vertices))
    for start, end in wheels['spans']:
        along = np.maximum(along, np.clip(np.minimum(x - start, end - x) / WHEEL_BLEND + 1.0, 0.0, 1.0))
    weight = along * np.clip((float(wheels['top']) + WHEEL_BLEND - z) / WHEEL_BLEND, 0.0, 1.0)
    across = 1.0 - weight * (1.0 - WHEEL_BACK / float(wheels['back']))
    vertices = np.array(vertices, float); vertices[:, 1] *= across
    normals = np.array(normals, float); normals[:, 1] /= across  # a normal is drawn the other way to its surface
    return vertices, normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)


def picture_at(vertices, uvs, faces, at):
    """The place on the picture (u, v) of the model's surface nearest `at`, metres on the finished model."""
    corners = np.asarray(vertices, float)[np.asarray(faces)]; at = np.asarray(at, float)
    a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]; across = np.cross(b - a, c - a); size = np.maximum((across ** 2).sum(1), 1e-18)
    flat = at - (((at - a) * across).sum(1) / size)[:, None] * across  # the point dropped on to each face's plane
    sign = lambda p, q: ((np.cross(q - p, flat - p) * across).sum(1) >= -1e-12)
    held = sign(a, b) & sign(b, c) & sign(c, a) & (size > 1e-12)  # faces the dropped point lies on, the nearest of them taken; else the nearest corner's face
    away = np.where(held, np.abs(((at - a) * across).sum(1)) / np.sqrt(size), np.linalg.norm(corners - at, axis=2).min(1) + 1.0)
    best = int(away.argmin()); a, b, c = corners[best]
    across = np.cross(b - a, c - a); flat = at - (at - a) @ across / max(float(across @ across), 1e-18) * across
    whole = max(float(np.linalg.norm(across)), 1e-12)
    share = np.clip([np.linalg.norm(np.cross(c - b, flat - b)), np.linalg.norm(np.cross(a - c, flat - c)), np.linalg.norm(np.cross(b - a, flat - a))], 0, None) / whole
    share = share / max(float(share.sum()), 1e-12)
    return share @ np.asarray(uvs, float)[np.asarray(faces)[best]]


def _bar(start, end, size):
    """The 24 corners (each face its own four, for flat shading), normals and 12 faces of a square-cut bar between two
    points, `size` [width, depth] across it: width level, depth upright, as a rail or stringer lies."""
    start, end = np.asarray(start, float), np.asarray(end, float); along = end - start; length = float(np.linalg.norm(along)); along = along / length
    level = np.cross(along, [0.0, 0.0, 1.0]); level = level / np.linalg.norm(level) if np.linalg.norm(level) > 1e-6 else np.array([1.0, 0.0, 0.0])
    upright = np.cross(level, along); half = np.asarray(size, float) / 2
    corner = lambda s, w, d: (start if s == 0 else end) + level * w * half[0] + upright * d * half[1]
    sides = [((0, -1, -1), (1, -1, -1), (1, -1, 1), (0, -1, 1), -level), ((0, 1, 1), (1, 1, 1), (1, 1, -1), (0, 1, -1), level),
             ((0, -1, 1), (1, -1, 1), (1, 1, 1), (0, 1, 1), upright), ((0, 1, -1), (1, 1, -1), (1, -1, -1), (0, -1, -1), -upright),
             ((0, 1, -1), (0, -1, -1), (0, -1, 1), (0, 1, 1), -along), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1), along)]
    points, normals, faces = [], [], []
    for *four, outward in sides:
        base = len(points); quad = [corner(*one) for one in four]
        if float(np.cross(quad[1] - quad[0], quad[2] - quad[0]) @ outward) < 0:
            quad = quad[::-1]
        points += quad; normals += [outward] * 4; faces += [[base, base + 1, base + 2], [base, base + 2, base + 3]]
    return np.asarray(points), np.asarray(normals, float), np.asarray(faces)


def flight(foot, top, width, sides=('left', 'right')):
    """The members of a straight steel stair flight from the middle of its lowest nosing `foot` to that of its highest
    `top` (the landing's edge), `width` across: [(start, end, size, kind)], kind 'tread', 'stringer', 'rail' or 'post'.
    The flight climbs in steps of at most STEP_RISE; the landing is its last step. Stringers run under the treads' ends
    from the ground to the landing, and each side named has a handrail RAIL_HEIGHT over the nosings, a rail midway and
    posts at its ends and at most POST_EVERY apart. Left and right are as one climbs."""
    foot, top = np.asarray(foot, float), np.asarray(top, float); rise = top[2] - foot[2]; run = top[:2] - foot[:2]
    steps = max(int(np.ceil(rise / STEP_RISE)), 1); ahead = np.append(run / np.linalg.norm(run), 0.0); left = np.array([-ahead[1], ahead[0], 0.0])
    going = np.append(run / steps, 0.0); members = []
    for step in range(steps):  # the tread whose nosing is at height (step + 1) * rise / steps, the last the landing's own edge
        nosing = foot + going * step + [0, 0, rise / steps * step]
        if step:
            middle = nosing + going / 2 - [0, 0, TREAD[0] / 2]
            members.append((middle - left * width / 2, middle + left * width / 2, (float(np.linalg.norm(going)) + 0.03, TREAD[0]), 'tread'))
    slope = (top - foot) / np.linalg.norm(top - foot); low = foot - slope * (foot[2] / max(slope[2], 1e-6)) if foot[2] > 0 else foot
    for side in (-1, 1):
        edge = left * side * (width / 2 + STRINGER[0] / 2)
        members.append((low + edge - [0, 0, STRINGER[1] / 2], top + edge - [0, 0, STRINGER[1] / 2], STRINGER, 'stringer'))
    for name in sides:
        side = left * (width / 2 + STRINGER[0] / 2) * (1 if name == 'left' else -1)
        members += railing([foot + side, top + side], below=STRINGER[1] / 2)
    return members


def railing(path, height=RAIL_HEIGHT, below=0.0):
    """The members of a railing along `path` (points on the surface walked, level or sloped): a rail `height` over it
    and one midway, and posts from `below` under it to its top rail at every point of the path and at most POST_EVERY
    apart between them: [(start, end, size, kind)]."""
    path = [np.asarray(point, float) for point in path]; members = []
    for index, (start, end) in enumerate(zip(path, path[1:])):
        for over in (height, height / 2):
            members.append((start + [0, 0, over], end + [0, 0, over], RAIL, 'rail'))
        posts = max(int(np.ceil(np.linalg.norm(end - start) / POST_EVERY)), 1)
        for k in range(posts + (1 if index == len(path) - 2 else 0)):  # the last segment has a post at its end too
            at = start + (end - start) * k / posts
            members.append((at - [0, 0, below], at + [0, 0, height + RAIL[1] / 2], POST, 'post'))
    return members


def coil(start, end, radius, pitch):
    """A coil of barbed wire along the line from `start` to `end`, its axis: (vertices, normals, faces). Two strands of
    `radius`, each a turn every `pitch` metres, wound opposite ways from one point, so that they cross twice a turn as
    the clipped loops of concertina wire do; seen from the side one strand alone is a wave, not a coil (the first
    built, of six straight bars a turn, read in the client as a row of pointed arches: user, 2026-11-17, "Fix the fence
    razor wire first"). Each strand is a three-sided wire COIL thick, COIL_SIDES lengths to a turn, shaded round. A
    fence built after generation is topped with one (user, 2026-11-17: "Fences will generally need to be topped with
    spiral barbed wire"); a generator's own smudges what stands behind it (`smears`)."""
    start, end = np.asarray(start, float), np.asarray(end, float); along = end - start; length = float(np.linalg.norm(along)); along = along / length
    level = np.cross(along, [0.0, 0.0, 1.0]); level = level / np.linalg.norm(level) if np.linalg.norm(level) > 1e-6 else np.array([1.0, 0.0, 0.0])
    upright = np.cross(level, along); steps = max(int(round(length / pitch)), 1) * COIL_SIDES
    k = np.arange(steps + 1); angle = 2 * np.pi * k / COIL_SIDES; points, normals, faces = [], [], []
    for hand in (1.0, -1.0):
        out = np.cos(angle)[:, None] * level + hand * np.sin(angle)[:, None] * upright
        centre = start + along * (length * k / steps)[:, None] + radius * out; base = 3 * (steps + 1) * len(points)
        ring = [np.cos(turn) * out + np.sin(turn) * along for turn in 2 * np.pi * np.arange(3) / 3]  # across the wire: out from the axis, and along it
        points.append(np.stack([centre + COIL / 2 * one for one in ring], 1).reshape(-1, 3)); normals.append(np.stack(ring, 1).reshape(-1, 3))
        for j in range(3):
            a, b = base + 3 * k[:-1] + j, base + 3 * k[:-1] + (j + 1) % 3
            quads = np.concatenate([np.stack([a, b, b + 3], 1), np.stack([a, b + 3, a + 3], 1)])
            faces.append(quads if hand > 0 else quads[:, ::-1])
    points, normals, faces = np.vstack(points), np.vstack(normals), np.vstack(faces)
    across = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    if float((across * normals[faces[:, 0]]).sum()) < 0:  # wound outward, whichever way the axis runs
        faces = faces[:, ::-1]
    return points, normals, faces


# A fence's frame (`sheets`): its posts, rails, coils and gateway posts show the fence's own picture, which is then
# FRAME_SHEET wire pictures across and high: the wires in its first corner, and beside them a column of galvanised
# steel and one of concrete, each from the foot of a post (v 0) to its top, FRAME_MARGIN in from its edges.
FRAME_SHEET, FRAME_SIDES, FRAME_MARGIN = 4, 10, 1 / 64
FRAME_COLUMNS = {'steel': (0.3125, 0.625), 'concrete': (0.625, 0.9375)}
FRAME_COLOURS, FRAME_RUST = {'steel': WIRE, 'concrete': (150, 146, 138)}, (112, 66, 38)
FRAME_CAP = (0.04, 0.07, 0.07)  # metres: how far a gateway post's cap stands out, its height and the rise of its top


def _wound(points, normals, faces):
    """`faces` without those of no area, each wound to face the way its corners' normals do."""
    across = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    faces = faces[np.linalg.norm(across, axis=1) > 1e-12]
    across = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    back = (across * normals[faces].sum(1)).sum(1) < 0; faces[back] = faces[back][:, ::-1]
    return faces


def tube(start, end, radius, cap=False, sides=FRAME_SIDES):
    """A round tube from `start` to `end`, shaded round: (points, normals, uvs, faces), u once round it and v from its
    start (0) to its end (1). With `cap` its end is closed by a low dome, as a fence post's is. The first posts of a
    perimeter were square-cut bars in one flat colour (user, 2026-11-17: "the posts for the fences needs to be better
    than a square pole and they don't even look like they have any texture applied")."""
    start, end = np.asarray(start, float), np.asarray(end, float); along = end - start; along = along / np.linalg.norm(along)
    level = np.cross(along, [0.0, 0.0, 1.0]); level = level / np.linalg.norm(level) if np.linalg.norm(level) > 1e-6 else np.array([1.0, 0.0, 0.0])
    upright = np.cross(level, along); round_ = np.arange(sides + 1) / sides
    out = np.cos(2 * np.pi * round_)[:, None] * level + np.sin(2 * np.pi * round_)[:, None] * upright
    rings = [(start + radius * out, out, 0.0), (end + radius * out, out, 0.93 if cap else 1.0)]
    if cap:
        lean = out + along; lean = lean / np.linalg.norm(lean, axis=1, keepdims=True)
        rings += [(end + along * 0.45 * radius + 0.6 * radius * out, lean, 0.97), (end + along * 0.6 * radius + 0 * out, np.tile(along, (sides + 1, 1)), 1.0)]
    points = np.vstack([ring[0] for ring in rings]); normals = np.vstack([ring[1] for ring in rings])
    uvs = np.vstack([np.stack([round_, np.full(sides + 1, ring[2])], 1) for ring in rings]); faces = []
    for ring in range(len(rings) - 1):
        a = ring * (sides + 1) + np.arange(sides); b, c, d = a + 1, a + sides + 1, a + sides + 2
        faces += [np.stack([a, b, d], 1), np.stack([a, d, c], 1)]
    return points, normals, uvs, _wound(points, normals, np.vstack(faces))


def block(foot, top, size):
    """An upright square post `size` across from `foot` to `top`, under a cap that stands out from it and rises to a
    point, as a cast gateway post has: (points, normals, uvs, faces), flat shaded, u across each side and v up."""
    foot, top = np.asarray(foot, float), np.asarray(top, float); half = size / 2; out, tall, rise = FRAME_CAP; wide = half + out
    points, normals, uvs, faces = [], [], [], []

    def face(corners, normal, spots):
        base = len(points); points.extend(corners); normals.extend([normal] * len(corners)); uvs.extend(spots)
        faces.extend([[base, base + 1, base + 2]] if len(corners) == 3 else [[base, base + 1, base + 2], [base, base + 2, base + 3]])
    square = lambda reach, z: [np.array([foot[0] + x * reach, foot[1] + y * reach, z]) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    low, high, under, over = square(half, foot[2]), square(half, top[2]), square(wide, top[2]), square(wide, top[2] + tall)
    apex = np.array([foot[0], foot[1], top[2] + tall + rise])
    for i, way in enumerate(([0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0])):
        j = (i + 1) % 4; way = np.array(way)
        face([low[i], low[j], high[j], high[i]], way, [[0, 0], [1, 0], [1, 0.9], [0, 0.9]])
        face([under[i], under[j], over[j], over[i]], way, [[0, 0.9], [1, 0.9], [1, 0.95], [0, 0.95]])
        slant = way * rise + np.array([0.0, 0.0, wide]); face([over[i], over[j], apex], slant / np.linalg.norm(slant), [[0, 0.95], [1, 0.95], [0.5, 1.0]])
    face(under, np.array([0.0, 0.0, -1.0]), [[0, 0.9], [1, 0.9], [1, 0.95], [0, 0.95]])  # the cap's underside, seen from the ground
    points, normals = np.array(points), np.array(normals)
    return points, normals, np.array(uvs, float), _wound(points, normals, np.array(faces))


def frame_picture(pixels, colours, seed=7):
    """Draw the steel and the concrete of a fence's frame on `pixels` (rows from the foot of a post up), in the columns
    FRAME_COLUMNS: galvanised steel mottled and streaked down its length, rusted at its foot and in spots; cast
    concrete speckled and pitted, damp at its foot and stained under its cap. Each in the tones of `colours`."""
    from PIL import Image
    high, wide = pixels.shape[:2]; rng = np.random.default_rng(seed); rows = (np.arange(high) + 0.5)[:, None] / high

    def grain(across, up, width):
        small = rng.standard_normal((max(high // up, 2), max(width // across, 2))).astype(np.float32)
        return np.asarray(Image.fromarray(small, 'F').resize((width, high), Image.BICUBIC), float)
    for kind, (u0, u1) in FRAME_COLUMNS.items():
        x0, x1 = int(round(u0 * wide)), int(round(u1 * wide)); width = x1 - x0; base = np.asarray(colours[kind], float)
        if kind == 'steel':
            shade = 1 + 0.08 * grain(12, 12, width) + 0.05 * grain(2, 2, width) + 0.07 * grain(3, high // 3, width)
            rust = np.clip(0.8 * grain(10, 14, width) + 1.5 * (1 - rows / 0.16) - 0.2, 0, 1) + 1.5 * np.clip(grain(6, 6, width) - 1.7, 0, 1)
            rust = (np.clip(rust, 0, 1) * 0.85)[..., None]
            colour = base * shade[..., None] * (1 - rust) + np.asarray(FRAME_RUST, float) * (0.8 + 0.2 * shade)[..., None] * rust
        else:
            shade = 1 + 0.06 * grain(20, 20, width) + 0.05 * grain(1, 1, width) - 0.18 * np.clip(1 - rows / 0.12, 0, 1)
            shade = shade - 0.12 * np.clip(grain(4, high // 2, width), 0, None) * np.clip((rows - 0.55) / 0.45, 0, 1) - 0.22 * (rng.random((high, width)) < 0.012)
            colour = base * shade[..., None]
        pixels[:, x0:x1, :3] = np.clip(colour, 0, 255).round(); pixels[:, x0:x1, 3] = 255


PERIMETER_POSTS, PERIMETER_POST, PERIMETER_END, PERIMETER_RAIL, PERIMETER_GATEPOST = 2.6, 0.04, 0.055, 0.022, 0.35  # metres: posts at most this far apart; the radius of a post, of one at a corner or a run's end and of a rail; a gateway's concrete post across
PERIMETER_SIDES = ('north', 'east', 'south', 'west')


def perimeter(spec):
    """A perimeter fence as the `frame` and `fence` parts that make it: (frame, fence).

    spec: {box: [[x0, y0], [x1, y1]], z: [foot, top], steel: [x, y, z], gateways: [{side, from, to}], concrete: [x, y,
    z], coil: {radius, pitch} or false, posts, pitch, wire, colour}, in metres on the finished model. The fence runs
    round `box` from `foot` (the ground it stands on) to `top`: round steel posts with caps at its corners and at most
    `posts` apart (stouter at a corner and at a run's end), a top and a bottom rail, chain-link sheets between them and
    a coil of barbed wire along the top of every run (user, 2026-11-17), in galvanised steel of the tone of the model's
    picture at `steel` (`frame_picture`). A gateway is an opening in one side, north, east,
    south or west, from one place along it to another (x for north and south, y for east and west), between two
    capped concrete posts of the tone at `concrete`. The Shiawase Barrens power station's fence was 46 built parts and 6 fences
    written by a script; this states it in a few lines. A fence is built, never generated (`reference.FENCE`)."""
    number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
    spot = lambda value: isinstance(value, list) and len(value) == 3 and all(number(one) for one in value)
    require(isinstance(spec, dict) and {'box', 'z', 'steel'} <= set(spec) <= {'box', 'z', 'steel', 'gateways', 'concrete', 'coil', 'posts', 'pitch', 'wire', 'colour'},
            'A perimeter needs box, z and steel, and may state gateways, concrete, coil, posts, pitch, wire and colour')
    require(np.asarray(spec['box'], float).shape == (2, 2) and np.asarray(spec['z'], float).shape == (2,) and spot(spec['steel']), 'A perimeter runs round a box [[x0, y0], [x1, y1]] from z [foot, top], coloured at a point of the model')
    (x0, y0), (x1, y1) = spec['box']; foot, top = (float(one) for one in spec['z']); gateways = spec.get('gateways', [])
    require(x1 - x0 > 1 and y1 - y0 > 1 and 1.0 <= top - foot <= 6.0, 'A perimeter is more than a metre across and one to six metres high')
    require(isinstance(gateways, list) and all(isinstance(one, dict) and set(one) == {'side', 'from', 'to'} and one['side'] in PERIMETER_SIDES and number(one['from'])
                                              and number(one['to']) and one['to'] - one['from'] >= 1.0 for one in gateways), 'A gateway is {side, from, to}: an opening of a metre or more in the north, east, south or west side')
    require(not gateways or spot(spec.get('concrete')), "A perimeter with gateways colours their posts at a point of the model: concrete")
    coiled = spec.get('coil', {'radius': 0.25, 'pitch': 0.5}); spacing = float(spec.get('posts', PERIMETER_POSTS))
    require(coiled is False or isinstance(coiled, dict) and set(coiled) == {'radius', 'pitch'}, 'A perimeter coil is {radius, pitch}, or false for a fence without one')
    require(0.5 <= spacing <= 6.0, 'A perimeter has a post every 0.5 to 6 metres')
    wire = {'pitch': spec.get('pitch', 0.09), 'wire': spec.get('wire', 0.016), **({'colour': spec['colour']} if 'colour' in spec else {})}
    fixed = lambda point: [round(float(value), 2) for value in point]
    ends = {'north': ((x0, y1), (x1, y1)), 'east': ((x1, y1), (x1, y0)), 'south': ((x1, y0), (x0, y0)), 'west': ((x0, y0), (x0, y1))}
    built, fence, stood, gateposts = [], [], set(), []
    for side in PERIMETER_SIDES:
        start, end = (np.array(one, float) for one in ends[side]); axis = 0 if side in ('north', 'south') else 1; low, high = sorted((start[axis], end[axis]))
        openings = sorted((float(one['from']), float(one['to'])) for one in gateways if one['side'] == side)
        require(all(low < a and b < high for a, b in openings) and all(first[1] < second[0] for first, second in zip(openings, openings[1:])),
                f'The gateways of the {side} side lie within it, from {low} to {high}, and apart from one another')
        cuts = [low, *(value for opening in openings for value in opening), high]; runs = list(zip(cuts[::2], cuts[1::2]))
        if start[axis] > end[axis]:  # the side is walked the other way: its runs too
            runs = [(b, a) for a, b in reversed(runs)]
        for index, (a, b) in enumerate(runs):
            one, other = start.copy(), start.copy(); one[axis], other[axis] = a, b; name = side if len(runs) == 1 else f'{side} {index + 1}'
            spans = int(np.ceil(abs(b - a) / spacing - 1e-9))
            for step in range(spans + 1):
                at = tuple(fixed(one + (other - one) * step / spans))
                if at in stood or any(abs(at[axis] - value) < 1e-6 for opening in openings for value in opening):
                    continue
                stood.add(at); ended = step in (0, spans)
                built.append({'part': f'{name} fence post', 'tube': [[*at, foot], [*at, round(top + (0.08 if ended else 0.04), 3)]], 'radius': PERIMETER_END if ended else PERIMETER_POST, 'cap': True, 'picture': spec['steel']})
            for label, height in (('top', round(top - 0.03, 3)), ('bottom', round(foot + 0.12, 3))):
                built.append({'part': f'{name} fence {label} rail', 'tube': [[*fixed(one), height], [*fixed(other), height]], 'radius': PERIMETER_RAIL, 'picture': spec['steel']})
            if coiled:
                built.append({'part': f'{name} fence barbed wire coil', 'coil': [[*fixed(one), round(top + coiled['radius'], 3)], [*fixed(other), round(top + coiled['radius'], 3)]], 'radius': coiled['radius'],
                              'pitch': coiled['pitch'], 'picture': spec['steel']})
            fence.append({'part': f'{name} fence', 'from': fixed(one), 'to': fixed(other), 'z': [round(foot + 0.1, 3), top], **wire})
        for a, b in openings:
            for value in (a, b):
                at = start.copy(); at[axis] = value; gateposts.append({'part': 'gateway post', 'block': [[*fixed(at), foot], [*fixed(at), round(top + 0.05, 3)]], 'size': PERIMETER_GATEPOST, 'picture': spec['concrete']})
    return built + gateposts, fence


def with_built(vertices, normals, uvs, faces, parts):
    """The model with straight members of its own made on to it: [{bar: [from, to], size}], [{railing: [points],
    height}] (`railing`) or [{stairs: {foot, top, width, sides}, rails}] (`flight`), each member a square-cut box drawn wholly in the colour of the model's picture at
    `picture` (and a flight's rails and posts at `rails`), a point on the model; or [{coil: [from, to], radius, pitch}], a coil of barbed wire (`coil`). A generator draws rails and stairs it
    cannot hold straight as wavy strands, or leaves them off: the rail yard's stair tower's handrails and the stairs up
    to its walkway (user, 2026-11-13). Returns (vertices, normals, uvs, faces)."""
    vertices, normals, uvs, faces = (np.asarray(one) for one in (vertices, normals, uvs, faces))
    for part in parts:
        place = picture_at(vertices, uvs, faces, part['picture'])
        rails = picture_at(vertices, uvs, faces, part['rails']) if 'stairs' in part and 'rails' in part else place
        if 'bar' in part:
            members = [(part['bar'][0], part['bar'][1], part['size'], 'bar')]
        elif 'railing' in part:
            members = railing(part['railing'], part.get('height', RAIL_HEIGHT))
        elif 'coil' in part:
            points, outward, local = coil(part['coil'][0], part['coil'][1], part['radius'], part['pitch']); count = len(vertices); members = []
            vertices = np.vstack([vertices, points]); normals = np.vstack([normals, outward]); uvs = np.vstack([uvs, np.tile(place, (len(points), 1))]); faces = np.vstack([faces, local + count])
        else:
            stairs = part['stairs']; members = flight(stairs['foot'], stairs['top'], stairs['width'], stairs.get('sides', ('left', 'right')))
        for start, end, size, kind in members:
            points, outward, local = _bar(start, end, size); count = len(vertices)
            vertices = np.vstack([vertices, points]); normals = np.vstack([normals, outward])
            uvs = np.vstack([uvs, np.tile(rails if kind in ('rail', 'post') else place, (len(points), 1))]); faces = np.vstack([faces, local + count])
    return vertices, normals, uvs, faces


def glazed(parts):
    """Panes of glass for a model: [{corners, colour, strength}] gives [{vertices, normals, uvs, faces, colour}], one for
    each part. A generator makes the frame of a glass front and leaves the glass out, or draws it solid: the Chop Shop
    clinic's cyberware case came back with the two bars of its slanted front and nothing between them (user,
    2026-11-14: "Fix the case glass too"). `corners` are three to GLASS_MOST points round a flat pane with no corner
    turned inward, in metres on the finished model. A pane is a sheet of one colour (`colour`, 0-255, GLASS_COLOUR
    where none is given) of which `strength` (GLASS_STRENGTH) is added to what is seen through it, as a halo's cards
    are added (`model_text`, `skin`): it takes the light of the place, so it is a pale sheen by day and next to
    nothing by night. Laid over what is behind it instead (a node's `alpha`), a pane hid the halo of every light
    behind it, whichever was written first (that case by night, 2026-11-14). It is seen from both sides, and is a
    node of the model's own, so no face of the model changes. The panes share one picture, `glass_picture`, each
    showing its own patch of it."""
    panes = []
    for index, part in enumerate(parts):
        label = str(part.get('part', 'pane of glass')); corners = np.asarray(part['corners'], float); count = len(corners)
        across = sum(np.cross(corners[k] - corners[0], corners[k + 1] - corners[0]) for k in range(1, count - 1)); size = float(np.linalg.norm(across))
        require(size > 1e-6, f'A pane of glass has an area ({label})')
        facing = across / size
        require(float(np.abs((corners - corners.mean(0)) @ facing).max()) <= GLASS_FLAT, f'A pane of glass is flat: a corner stands more than {GLASS_FLAT} metres off its plane ({label})')
        turns = [float(np.cross(corners[k] - corners[k - 1], corners[(k + 1) % count] - corners[k]) @ facing) for k in range(count)]
        require(min(turns) > 0, f'A pane of glass is convex, its corners stated in order round it ({label})')
        fan = np.array([[0, k, k + 1] for k in range(1, count - 1)])
        panes.append({'vertices': np.vstack([corners, corners]), 'normals': np.vstack([np.tile(facing, (count, 1)), np.tile(-facing, (count, 1))]),
                      'uvs': np.tile([(index + 0.5) / len(parts), 0.5], (2 * count, 1)), 'faces': np.vstack([fan, fan[:, ::-1] + count]),
                      'colour': [round(value * float(part.get('strength', GLASS_STRENGTH))) for value in part.get('colour', GLASS_COLOUR)]})
    return panes


def glass_picture(panes):
    """The picture a model's panes of glass share (`glazed`): a patch of each pane's colour, left to right."""
    from PIL import Image
    image = Image.new('RGB', (len(panes), 1))
    image.putdata([tuple(int(value) for value in pane['colour']) for pane in panes])
    return image.resize((GLASS_PICTURE, GLASS_PICTURE), Image.NEAREST)


def ember_beds(parts):
    """Beds of embers for a model: [{at, radius}] gives {vertices, normals, uvs, faces}, a low mound for each, `radius`
    across at `at` (the middle of its rim, metres on the finished model) and EMBER_RISE of that higher in the middle,
    its lumps a little up and down. They are nodes of their own that show `name`_e (`ember_picture`) as bright by
    night as by day (`model_text`). A generator makes the charred wood of a fire barrel and nothing under it, and a
    block of one glowing colour built there looked like a lid, not like embers (user, 2026-11-16)."""
    rng = np.random.default_rng(EMBER_SEED); points, uvs, faces = [], [], []
    for part in parts:
        at, radius = np.asarray(part['at'], float), float(part['radius']); first = len(points); rise = radius * EMBER_RISE
        points.append(at + [0, 0, rise]); uvs.append([0.5, 0.5])
        for ring in range(1, EMBER_RINGS + 1):
            share = ring / EMBER_RINGS
            for step in range(EMBER_SIDES):
                angle = 2 * np.pi * (step + ring / 2) / EMBER_SIDES; across = np.array([np.cos(angle), np.sin(angle)]) * share
                lump = rng.uniform(-0.3, 0.3) * rise if ring < EMBER_RINGS else 0.0  # the rim lies level against what holds the bed
                points.append(at + [*(across * radius), rise * (1 - share ** 2) + lump]); uvs.append((0.5 + across * 0.48).tolist())
        at_ring = lambda ring, step: first + 1 + (ring - 1) * EMBER_SIDES + step % EMBER_SIDES
        for step in range(EMBER_SIDES):
            faces.append([first, at_ring(1, step), at_ring(1, step + 1)])
            for ring in range(1, EMBER_RINGS):  # each ring is turned half a step on from the one inside it
                faces += [[at_ring(ring, step), at_ring(ring + 1, step), at_ring(ring, step + 1)], [at_ring(ring, step + 1), at_ring(ring + 1, step), at_ring(ring + 1, step + 1)]]
    return {'vertices': np.asarray(points, float), 'normals': np.tile([0.0, 0.0, 1.0], (len(points), 1)), 'uvs': np.asarray(uvs, float), 'faces': np.asarray(faces)}


def _soft(rng, size, step):
    """Smooth noise from 0 to 1, `size` pixels square: random values `step` pixels apart, drawn up."""
    from PIL import Image
    small = Image.fromarray((rng.uniform(0, 1, (max(2, size // step),) * 2) * 255).astype(np.uint8))
    return np.asarray(small.resize((size, size), Image.BICUBIC), float) / 255


def ember_picture(size=None, coals=None):
    """The picture a model's beds of embers show (`ember_beds`): lumps of charcoal seen from above, dark on their
    crowns under grey ash, the fire showing in the gaps between them and through their thin edges."""
    from PIL import Image
    size, coals = size or EMBER_PICTURE, coals or EMBER_COALS; rng = np.random.default_rng(EMBER_SEED)
    at = rng.uniform(0, 1, (coals, 2)); spent = rng.uniform(0, 1, coals); y, x = np.mgrid[0:size, 0:size]
    place = np.stack([(x + 0.5) / size, (y + 0.5) / size], -1) + (np.stack([_soft(rng, size, 16), _soft(rng, size, 16)], -1) - 0.5) * 0.08  # no lump is straight-sided
    away = np.linalg.norm(place[:, :, None, :] - at[None, None], axis=-1); order = np.argsort(away, axis=-1)[..., :2]
    first, second = (np.take_along_axis(away, order[..., n:n + 1], -1)[..., 0] for n in (0, 1)); lump = order[..., 0]
    inside = np.clip((second - first) * np.sqrt(coals) * 1.6, 0, 1)  # 0 in the gap between two lumps, 1 on a lump's crown
    fine = rng.uniform(0, 1, (size, size)); broad = _soft(rng, size, 24); patch = _soft(rng, size, 6)
    gap = np.exp(-(inside / 0.16) ** 2); rim = np.exp(-(inside / 0.45) ** 2) * 0.55 * (1 - spent[lump] * 0.7)
    crack = (patch > 0.62) * (1 - spent[lump]) * 0.5 * inside
    heat = np.clip((gap + rim + crack) * (0.45 + 0.75 * broad) + (fine - 0.5) * 0.08, 0, 1)
    stops = np.array([0.0, 0.22, 0.5, 0.78, 1.0]); ramp = np.array([[0.04, 0.035, 0.035], [0.30, 0.04, 0.02], [0.80, 0.18, 0.03], [1.0, 0.50, 0.08], [1.0, 0.86, 0.45]])
    colour = np.stack([np.interp(heat, stops, ramp[:, channel]) for channel in range(3)], -1)
    crust = (np.clip((inside - 0.35) / 0.4, 0, 1) * np.clip(spent[lump] * 1.3 - 0.25 + (patch - 0.5) * 0.9, 0, 1) * (1 - heat) ** 2)[..., None]  # ash on the cool crowns
    ash = (0.34 + 0.22 * fine)[..., None] * np.array([1.0, 0.97, 0.94])
    return Image.fromarray((np.clip(colour * (1 - crust) + ash * crust, 0, 1) * 255).round().astype(np.uint8))


def filled(vertices, normals, uvs, faces, parts):
    """`faces` with each hole of `parts` ([{at: a point in metres on the finished model}]) filled: the ring of open
    edges (each the edge of one face only, corners within FILL_WELD taken as one place) that passes nearest `at`,
    within FILL_NEAR, is closed with faces between its own corners, cut ear by ear as the ring lies on its own best
    plane. Each new face faces the way its corners' normals do, and is drawn with the picture of the faces round the
    hole. For a hole of more corners than `close` is worth stating face by face: the gaps in the rail yard's crane
    leg sills, 12 and 16 corners each, and a slit in its warehouse wall (user, 2026-11-13). A point near no rim, or
    near a rim that does not close on itself, is refused. No vertex is added, unless the part states `picture`, a
    point on the model: its faces are then drawn wholly in the colour of the model's picture there, on corners of
    their own. Corners that the picture draws far apart stretch whatever lies between them across the fill: the wedge
    at the foot of the Chop Shop clinic's back wall was closed with a streak of other walls (2026-11-14). Returns
    (vertices, normals, uvs, faces)."""
    from collections import defaultdict
    faces = np.asarray(faces); vertices = np.asarray(vertices, float); normals = np.asarray(normals, float); uvs = np.asarray(uvs, float)
    _, first, place = np.unique(np.round(vertices / FILL_WELD).astype(np.int64), axis=0, return_index=True, return_inverse=True)
    place = place.ravel(); where = vertices[first]
    for part in parts:
        label = str(part.get('part', 'filled hole')); at = np.asarray(part['at'], float)
        # The open edges, each the edge of one face only, counted by place: [place a, place b] and the face's own vertices
        pairs = faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2); ends = place[pairs]
        _, back, many = np.unique(np.sort(ends, axis=1), axis=0, return_inverse=True, return_counts=True)
        alone = many[back.ravel()] == 1; rim, owner = defaultdict(list), {}
        for (a, b), vertex_pair in zip(ends[alone].tolist(), pairs[alone].tolist()):
            rim[a].append(b); rim[b].append(a); owner[(a, b)] = tuple(vertex_pair)

        def distance(a, b):
            ab = where[b] - where[a]; s = np.clip((at - where[a]) @ ab / max(float(ab @ ab), 1e-12), 0, 1)
            return float(np.linalg.norm(where[a] + s * ab - at))
        edges = [(a, b) for a in rim for b in rim[a] if a < b]
        require(edges, f'The model has no open edge ({label})')
        start = min(edges, key=lambda edge: distance(*edge))
        require(distance(*start) <= FILL_NEAR, f"No hole's rim passes within {FILL_NEAR} metres of {at.tolist()} ({label})")
        ring = [start[0], start[1]]
        while ring[-1] != ring[0] and len(ring) <= FILL_MOST + 1:
            ahead = [other for other in rim[ring[-1]] if other != ring[-2]]
            require(len(rim[ring[-1]]) == 2 and ahead, f'The rim nearest {at.tolist()} does not close on itself ({label})')
            ring.append(ahead[0])
        ring = ring[:-1]; require(3 <= len(ring) <= FILL_MOST, f'A filled hole has 3 to {FILL_MOST} corners ({label})')
        drawn = {}  # each corner as the vertex the faces round the hole draw it with, so the fill takes their picture
        for a, b in zip(ring, ring[1:] + ring[:1]):
            pair = owner.get((a, b)) or owner.get((b, a))
            for vertex in pair:
                drawn.setdefault(int(place[vertex]), int(vertex))
        if 'picture' in part:  # corners of the fill's own, all at one place on the picture
            spot = picture_at(vertices, uvs, faces, part['picture']); corners = [drawn[one] for one in ring]; count = len(vertices)
            vertices = np.vstack([vertices, vertices[corners]]); normals = np.vstack([normals, normals[corners]]); uvs = np.vstack([uvs, np.tile(spot, (len(ring), 1))])
            place = np.append(place, ring); drawn = {one: count + index for index, one in enumerate(ring)}
        points = where[ring]; middle = points.mean(0); _, _, axes = np.linalg.svd(points - middle)
        flat = (points - middle) @ axes[:2].T
        cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        turn = 1.0 if sum(cross(np.zeros(2), flat[i], flat[(i + 1) % len(flat)]) for i in range(len(flat))) > 0 else -1.0
        left = list(range(len(ring))); made = []
        while len(left) > 3:
            for k in range(len(left)):
                i, j, n = left[k - 1], left[k], left[(k + 1) % len(left)]
                if cross(flat[i], flat[j], flat[n]) * turn <= 1e-12:
                    continue
                inside = lambda q: all(cross(u, w, q) * turn > 0 for u, w in ((flat[i], flat[j]), (flat[j], flat[n]), (flat[n], flat[i])))
                if any(inside(flat[m]) for m in left if m not in (i, j, n)):
                    continue
                made.append((i, j, n)); left.pop(k); break
            else:
                made.append(tuple(left[:3])); left.pop(1)  # a rim that folds over itself on its plane: cut on regardless
        made.append(tuple(left))
        for i, j, n in made:
            a, b, c = drawn[ring[i]], drawn[ring[j]], drawn[ring[n]]
            if float(np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a]) @ (normals[a] + normals[b] + normals[c])) < 0:
                b, c = c, b
            faces = np.vstack([faces, np.asarray([[a, b, c]], faces.dtype)])
    return vertices, normals, uvs, faces


def closed(vertices, normals, uvs, faces, parts):
    """`faces` with one more for each of `parts` ([{corners: three points in metres on the finished model}]): a hole a
    generator left in a surface, closed between three of the model's own vertices. The Ares fence section came back
    with two faces of its concrete base lying over each other and a wedge between them open to the ground behind
    (seen in the client, 2026-11-12). Each corner is the vertex nearest the stated point, within `CLOSE_NEAR`; where
    several stand at one place (a seam of the picture), those whose places on the picture lie nearest together are
    taken, so that the face is drawn with the picture round the hole. It faces the way its corners' normals do.
    No vertex is added, so nothing else of the model changes."""
    from itertools import product
    faces = np.asarray(faces)
    for part in parts:
        label = str(part.get('part', 'closing face')); stands = []
        for corner in np.asarray(part['corners'], float):
            away = np.linalg.norm(vertices - corner, axis=1); nearest = int(away.argmin())
            require(away[nearest] <= CLOSE_NEAR, f'A closing face stands on the model\'s own vertices: none lies within {CLOSE_NEAR} metres of {corner.tolist()} ({label})')
            stands.append(np.flatnonzero(np.linalg.norm(vertices - vertices[nearest], axis=1) < 1e-4))
        around = lambda chosen: sum(float(np.linalg.norm(uvs[chosen[a]] - uvs[chosen[b]])) for a, b in ((0, 1), (1, 2), (2, 0)))
        a, b, c = (int(index) for index in min(product(*stands), key=around))
        across = np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a])
        require(float(np.linalg.norm(across)) > 1e-6, f'A closing face has three corners apart from one another ({label})')
        # A face on these three places, through whichever of the vertices that stand at each: at a seam of the picture
        # the model's own face may use the other vertex of every pair.
        there = np.logical_and.reduce([np.isin(faces, stand).any(1) for stand in stands])
        require(not bool(there.any()), f'The model already has a face between these corners ({label})')
        if float(across @ (normals[a] + normals[b] + normals[c])) < 0:
            b, c = c, b
        faces = np.vstack([faces, np.asarray([[a, b, c]], faces.dtype)])
    return faces


def moved(vertices, normals, uvs, faces, parts):
    """The model with each of `parts` ([{box, by}], metres on the finished model) moved: the faces wholly in the box are
    carried `by` on copies of their corners, and the faces that tied them to the rest (some corners in the box, some
    out) are taken away, as they would be drawn out across the gap. The rail yard's walkway came back with one leg
    1.7 metres in from its corner (user, 2026-11-13: "one of the posts on the walkway is misplaced from the corner").
    A box that holds no whole face is refused. Returns (vertices, normals, uvs, faces)."""
    vertices, normals, uvs, faces = (np.asarray(one) for one in (vertices, normals, uvs, faces))
    for part in parts:
        low, high = np.sort(np.asarray(part['box'], float), axis=0); held = np.all((vertices >= low) & (vertices <= high), axis=1)[faces]
        whole, torn = held.all(1), held.any(1) & ~held.all(1)
        require(bool(whole.any()), f"A moved box holds no whole face of the model ({part.get('part', 'moved part')})")
        used, local = np.unique(faces[whole], return_inverse=True); count = len(vertices)
        vertices = np.vstack([vertices, vertices[used] + np.asarray(part['by'], float)]); normals = np.vstack([normals, normals[used]]); uvs = np.vstack([uvs, uvs[used]])
        faces = np.vstack([faces[~whole & ~torn], local.reshape(-1, 3) + count])
    used, local = np.unique(faces, return_inverse=True)
    return vertices[used], normals[used], uvs[used], local.reshape(-1, 3)


def cleared(vertices, normals, uvs, faces, parts):
    """The model without what the generator stood where a walk must pass: the faces whose middle lies in one of `parts`
    ([{box: two corners in metres on the finished model}]) taken away, and the vertices no face uses any more. The
    Saeder-Krupp yard's loading bay came back with a railed-off square on its floor, under a metre from the vehicle
    beside it: too narrow a way into the back of the bay (user, 2026-11-12: "going to need to be able to get through
    this gap"). A box above the floor takes what stands on it and leaves the floor. A part may instead be a rod
    ({from, to, radius}): the rail yard's stair tower had handrails drawn as wavy strands along its slanted flights
    (user, 2026-11-13), which no upright box holds without the treads. A part that takes nothing is
    refused: it is a mistake in the set. Returns (vertices, normals, uvs, faces)."""
    faces = np.asarray(faces); middle = vertices[faces].mean(1); kept = np.ones(len(faces), bool)
    for part in parts:
        if 'box' in part:
            low, high = np.sort(np.asarray(part['box'], float), axis=0)
            inside = np.all((middle >= low) & (middle <= high), axis=1)
        else:  # a rod {from, to, radius}: what lies within its radius of the line between its ends, as a slanted handrail does
            start, end = (np.asarray(part[key], float) for key in ('from', 'to')); along = end - start
            reach = np.clip((middle - start) @ along / float(along @ along), 0, 1)
            inside = np.linalg.norm(middle - (start + reach[:, None] * along), axis=1) <= float(part['radius'])
        require(bool((inside & kept).any()), f"A cleared box takes no face of the model away ({part.get('part', 'cleared part')})")
        kept &= ~inside
    used, local = np.unique(faces[kept], return_inverse=True)
    return vertices[used], normals[used], uvs[used], local.reshape(-1, 3)


VEIL_FACE, VEIL_DETAIL, VEIL_REACH, VEIL_SHARE, VEIL_LEAST = 0.15, 0.02, 0.4, 0.4, 8  # m² a veil is at least and a face of the detail under it at most; metres behind it the detail lies; how much of it the detail covers, and in how many faces


def veils(vertices, faces):
    """The large faces that lie just in front of fine detail looking the same way: [{m2, at, covers}], the largest
    first, `at` the face's middle and `covers` how much of it the detail under it would fill. The generator lays a
    stray face or two across an opening, drawn as a pale smear, and hides the window it modelled behind them: the
    Pulse Tech shop's front window had two and its west window three (user, 2026-11-15: "the front window has a
    pretty major defect"), which no measure of the face alone tells from a plain wall. A wall has nothing looking
    outward a hand's breadth behind it. What is told is looked at, not taken away: a pane the generator meant, with
    the room drawn behind it, reads the same (one is left in that shop's west window)."""
    faces = np.asarray(faces)
    # A face given a back (`backed`) is there twice, and the back of a wall has the backs of whatever stands proud of
    # it lying 'behind' it and looking its way: each face is read once, as it was generated.
    _, place = np.unique(vertices, axis=0, return_inverse=True)
    _, first = np.unique(np.sort(place.reshape(-1)[faces], axis=1), axis=0, return_index=True); faces = faces[np.sort(first)]
    a, b, c = (vertices[faces[:, corner]] for corner in range(3))
    cross = np.cross(b - a, c - a); area = np.linalg.norm(cross, axis=1) / 2
    normal = cross / np.maximum(area[:, None] * 2, 1e-12); middle = (a + b + c) / 3
    fine = area < VEIL_DETAIL; found = []; fine_middle, fine_normal, fine_area = middle[fine], normal[fine], area[fine]
    for face in np.flatnonzero(area >= VEIL_FACE):
        offset = fine_middle - a[face]; depth = offset @ normal[face]; facing = fine_normal @ normal[face]
        near = (depth < -0.02) & (depth > -VEIL_REACH) & (facing > 0.5)
        if near.sum() < VEIL_LEAST:
            continue
        flat = offset[near] - np.outer(depth[near], normal[face]); u, v = b[face] - a[face], c[face] - a[face]
        uu, uv, vv = u @ u, u @ v, v @ v; pu, pv = flat @ u, flat @ v; scale = uu * vv - uv * uv
        s, t = (pu * vv - pv * uv) / scale, (pv * uu - pu * uv) / scale
        under = (s >= 0) & (t >= 0) & (s + t <= 1); covers = min(float(fine_area[near][under].sum() / area[face]), 1.0)  # layers of detail one behind another fill it once
        if under.sum() >= VEIL_LEAST and covers >= VEIL_SHARE:
            found.append({'m2': round(float(area[face]), 3), 'at': [round(float(value), 2) for value in middle[face]], 'covers': round(covers, 2)})
    return sorted(found, key=lambda one: -one['m2'])


def square_up(points, limit=45.0, step=0.25):
    """Degrees to turn the model about the vertical so its footprint lies square to the axes. A model generated from a
    three-quarter view can come back still turned that way (the vending machine, 2026-11-10: about 30 degrees). The
    turn that gives the smallest bounding rectangle is taken, never more than `limit` either way, so the front stays
    the front; a footprint with no straight sides (a pile of rubbish) barely changes and is left as it is."""
    flat = points[:, :2] - points[:, :2].mean(0); best, area_at = 0.0, {}
    for degrees in np.arange(-limit, limit + step, step):
        c, s = np.cos(np.radians(degrees)), np.sin(np.radians(degrees))
        turned = flat @ np.array([[c, s], [-s, c]])
        area_at[float(degrees)] = float(np.ptp(turned[:, 0]) * np.ptp(turned[:, 1]))
    best = min(area_at, key=area_at.get)
    return best if area_at[best] < 0.97 * area_at[0.0] else 0.0


def _turn(yaw, pitch, roll):
    """Rotation in game space: `roll` about the front axis (Y), then `pitch` about the side axis (X), then `yaw` about up (Z)."""
    y, p, r = np.radians([yaw, pitch, roll])
    about_z = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1.0]])
    about_x = np.array([[1.0, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    about_y = np.array([[np.cos(r), 0, np.sin(r)], [0, 1.0, 0], [-np.sin(r), 0, np.cos(r)]])
    return about_z @ about_x @ about_y


def upright(points, faces, *, limit=(45.0, 35.0, 35.0), sample=6000):
    """`_upright`, a large model's kept for its next build (`cache`)."""
    from . import cache
    points, faces = np.asarray(points, float), np.asarray(faces)
    found = cache.arrays('upright', (points, faces, limit, sample, Path(__file__)), lambda: (np.asarray(_upright(points, faces, limit=limit, sample=sample), float),), faces=len(faces))
    return tuple(float(angle) for angle in found[0])


def _upright(points, faces, *, limit=(45.0, 35.0, 35.0), sample=6000):
    """(yaw, pitch, roll) in degrees that stand a made thing square to the axes, or zeros.

    A model generated locally comes back the way the reference was drawn: seen from above and to one side, so it leans
    (the trash can, 2026-11-10). The turn taken is the one that gives the smallest box around the model, searched
    within `limit` so up stays up and the front stays the front: a made thing, tapered or not, fills the least room
    standing straight. Two checks keep it from turning things that were right: the box must shrink by a clear margin,
    and the model's surface must not end up pointing less along the axes than before (a wall camera on its arm has a
    smaller box when tipped, but its housing then points nowhere)."""
    of_face = np.cross(points[faces[:, 1]] - points[faces[:, 0]], points[faces[:, 2]] - points[faces[:, 0]])
    area = np.linalg.norm(of_face, axis=1); keep = area > 1e-12
    of_face, area = of_face[keep] / area[keep, None], area[keep]
    if len(area) > sample:
        pick = np.random.default_rng(0).choice(len(area), sample, replace=False, p=area / area.sum())
        of_face, area = of_face[pick], np.ones(sample)
    area = area / area.sum()
    # Only points on the outside can touch the box: keep the farthest one in each of many directions.
    directions = np.random.default_rng(1).normal(size=(3000, 3))
    hull = points[np.unique(np.concatenate([(points @ directions.T).argmax(0), (points @ directions.T).argmin(0)]))] if len(points) > 4000 else points
    volume = lambda angles: float(np.prod(np.ptp(hull @ _turn(*angles).T, axis=0) + 1e-9))
    along = lambda angles: float(area @ (np.abs(of_face @ _turn(*angles).T).max(1) ** 8))
    step = 5.0; spans = [np.arange(-bound, bound + step, step) for bound in limit]
    best = min(((y, p, r) for y in spans[0] for p in spans[1] for r in spans[2]), key=volume)
    for step in (1.0, 0.25):
        offsets = np.arange(-4 * step, 4 * step + step / 2, step)
        best = min(((best[0] + y, best[1] + p, best[2] + r) for y in offsets for p in offsets for r in offsets), key=volume)
    best = tuple(float(np.clip(angle, -bound, bound)) for angle, bound in zip(best, limit))
    still = (0.0, 0.0, 0.0)
    # A lean of five degrees swells the box of an upright thing by about a fifth; a shapeless heap finds less than a
    # tenth by any turn, so a tenth is the margin.
    if volume(best) > 0.90 * volume(still) or along(best) < along(still) - 0.005 or max(abs(angle) for angle in best) < 0.5:
        return still
    return best


def fit(vertices, normals, uvs, height, *, faces=None, square=True):
    """The mesh in game space: turned to the game's axes, stood square to them, `height` metres tall, centred, on z = 0.
    With `faces` the model is stood upright from its flat sides (`upright`); without, or where that finds no evidence,
    only its footprint is squared (`square_up`). Texture coordinates pass through unchanged: the game reads a DDS from
    its first row, as glTF does (flipping them scrambled every texture island in the first client check)."""
    require(height > 0, 'A height in metres is required')
    points, turned = vertices @ TO_GAME.T, normals @ TO_GAME.T
    angles = upright(points, faces) if square and faces is not None else (0.0, 0.0, 0.0)
    if not any(angles) and square:
        angles = (square_up(points), 0.0, 0.0)
    if any(angles):
        turn = _turn(*angles); points, turned = points @ turn.T, turned @ turn.T
    points, scale = stand(points, height)
    return points, turned, np.array(uvs[:, :2], float), scale, angles


def stand(points, height):
    """(points, scale): `height` metres tall, centred over the origin, on z = 0."""
    low, high = points.min(0), points.max(0)
    scale = height / (high[2] - low[2])
    return (points - np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])) * scale, scale


def stretched(points, normals, length):
    """(points, normals): the model, centred over the origin, drawn out or drawn in along the longer side of its footprint
    to `length` metres, its height and width kept, its normals following (by the inverse of the stretch, then made
    whole again). Generated shipping containers came out a third to a half short of their 20 and 40 feet at their
    true height (rail freight yard, 2026-11-13), and scaling by height alone cannot mend a thing's proportions."""
    span = np.ptp(points[:, :2], axis=0); axis = int(span.argmax())
    require(length > 0 and span[axis] > 0, 'A length is a number of metres along a model that has one')
    factor = np.ones(3); factor[axis] = length / span[axis]
    normals = np.asarray(normals, float) / factor
    return points * factor, normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)


def levelled(points, faces, thickness):
    """(points, normals): a floor marking laid flat, `thickness` metres thick. A generator given a pad seen from a
    slant made a wedge of it: the Ghost Riders parking pad came back seven times as thick at its back as at its
    front, half a metre at its true width (2026-11-15). The plane of its top is found from the faces that look up
    (those standing proud of it, wheel stops and raised paint, left out of the fit), and every point is lowered by
    the plane's height there less `thickness`; nothing goes under the ground, so the sides and the underside close
    onto it. What stood proud of the top still does, by as much. The normals are made again from the faces, which
    are wound right by now."""
    require(0 < thickness <= LEVEL_MOST, f'A levelled floor marking is left over 0 and at most {LEVEL_MOST} metres thick')
    corners = points[faces]; out = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = np.linalg.norm(out, axis=1); up = out[:, 2] / np.maximum(area, 1e-12) > 0.9
    require(bool(up.any()), 'A model with no face looking up has no top to level')
    # Places spread evenly over what looks up, so a large face counts for its size however few faces the top is made of.
    places = scatter(points, faces[up], spacing=max(float(np.ptp(points[:, :2], axis=0).max()) / 80, 1e-4)); keep = np.ones(len(places), bool)
    for _ in range(4):  # the top is most of what looks up: what stands off the fitted plane is left out and the plane fitted again
        plane = np.linalg.lstsq(np.column_stack([places[keep, :2], np.ones(int(keep.sum()))]), places[keep, 2], rcond=None)[0]
        off = places[:, 2] - (places[:, :2] @ plane[:2] + plane[2])
        keep = np.abs(off) <= max(float(np.median(np.abs(off))) * 3, 1e-4)
        require(int(keep.sum()) >= 3, 'The top of the model is no plane: nothing to level it by')
    flat = points.copy(); flat[:, 2] = np.maximum(points[:, 2] - (points[:, :2] @ plane[:2] + plane[2]) + thickness, 0.0)
    corners = flat[faces]; out = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]); normals = np.zeros_like(flat)
    for corner in range(3):
        np.add.at(normals, faces[:, corner], out)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return flat, np.where(length > 1e-12, normals / np.maximum(length, 1e-12), [0.0, 0.0, 1.0])


def blank_panels(vertices, uvs, faces, colour, *, size=None, placed=None):
    """Panels the size of a door that the model's picture draws in one flat colour: [{side, box, m2, colour, repair}].

    A generator often draws a roller or bay door as a featureless panel, its slats lost (the Ghost Riders garage's
    door, a flat dark blue with a few stray flecks; user, 2026-11-15: "garage and bay doors seem to have problems on
    a lot of the meshy models, can we add reusable checks and repairs for that?"). Each upright wall plane is read in
    cells BLANK_CELL across: a cell is blank where its brightness varies by no more than BLANK_WITHIN of itself, and blank
    cells that touch are one panel where they fill a rectangle BLANK_LEAST each way, agree with each other within
    BLANK_BETWEEN and start within BLANK_SILL of the model's foot. `box` is the panel on the finished model, a little
    deeper than its plane, and `repair` the `smooth` entry that draws it again as a roller door's slats (`retouch`).
    A panel so found is a place to look, not a fault: a painted steel plate reads the same. One drawn with slats
    finer than its texels is not found here: it reads as a moiré, which the same repair mends (the Saeder-Krupp
    yard's dock doors). `colour` is the picture as it ships, so a door mended is found no more. `placed` is the
    model's position map with facing at `size` (`glow.position_map`), for a caller that has one."""
    from PIL import Image
    from . import glow

    def patches(grid):
        """The patches of touching true cells, each as its (column slice, row slice) and its cells within them."""
        left = grid.copy()
        for start in zip(*np.nonzero(grid)):
            if not left[start]:
                continue
            left[start] = False; stack, cells = [start], []
            while stack:
                a, b = stack.pop(); cells.append((a, b))
                for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= c < grid.shape[0] and 0 <= d < grid.shape[1] and left[c, d]:
                        left[c, d] = False; stack.append((c, d))
            cells = np.array(cells); low, high = cells.min(0), cells.max(0) + 1; panel = np.zeros(high - low, bool); panel[tuple((cells - low).T)] = True
            yield (slice(int(low[0]), int(high[0])), slice(int(low[1]), int(high[1]))), panel

    where, covered, toward = placed if placed is not None else glow.position_map(vertices, uvs, faces, size or BLANK_SIZE, facing=True)
    size = covered.shape[0]
    base = np.asarray(colour.convert('RGB').resize((size, size), Image.BOX), float) / 255; bright = base @ np.array([0.2126, 0.7152, 0.0722])
    foot = float(np.asarray(vertices, float)[:, 2].min()); found = []
    for side, (x, y) in enumerate(glow.SIDES):
        facing = covered & (toward[..., 0] * x + toward[..., 1] * y > 0.9)
        if not facing.any():
            continue
        depth = (where[..., 0] * x + where[..., 1] * y)[facing]; along = (where[..., 0] * y - where[..., 1] * x)[facing]
        height = where[..., 2][facing]; shade, tint = bright[facing], base[facing]
        for shift in (0.0, 0.5):  # planes are told twice, half a plane apart, so a wall on a line between two is whole in one
            plane = np.floor(depth / BLANK_PLANE + shift).astype(int)
            for one in np.unique(plane):
                mine = plane == one
                if mine.sum() < (BLANK_LEAST / BLANK_CELL) ** 2 * 4:
                    continue
                column = np.floor(along[mine] / BLANK_CELL).astype(int); row = np.floor(height[mine] / BLANK_CELL).astype(int)
                left, low = column.min(), row.min(); shape = (column.max() - left + 1, row.max() - low + 1); cell = (column - left, row - low)
                count = np.zeros(shape); total = np.zeros(shape); squares = np.zeros(shape)
                np.add.at(count, cell, 1); np.add.at(total, cell, shade[mine]); np.add.at(squares, cell, shade[mine] ** 2)
                mean = total / np.maximum(count, 1); varies = np.sqrt(np.maximum(squares / np.maximum(count, 1) - mean ** 2, 0))
                for (columns, rows), panel in patches((count >= 4) & (varies <= BLANK_WITHIN * np.maximum(mean, 0.1))):
                    wide, tall = (np.array(panel.shape) * BLANK_CELL).tolist()
                    sill = (low + rows.start) * BLANK_CELL
                    if (wide < BLANK_LEAST or tall < BLANK_LEAST or panel.mean() < BLANK_FILL or sill > foot + BLANK_SILL
                            or float(mean[columns, rows][panel].std()) > BLANK_BETWEEN):
                        continue
                    texels = mine.copy(); texels[mine] = (cell[0] >= columns.start) & (cell[0] < columns.stop) & (cell[1] >= rows.start) & (cell[1] < rows.stop)
                    lows, highs = (left + columns.start) * BLANK_CELL, (left + columns.stop) * BLANK_CELL
                    near, far = float(depth[texels].min()) - 0.05, float(depth[texels].max()) + 0.05
                    # back from the wall's own measures to the model's: along is x * y' - y * x' of the side's way (x', y')
                    ends = np.array([[lows * y + near * x, -lows * x + near * y], [highs * y + far * x, -highs * x + far * y]])
                    box = [[round(float(ends[:, 0].min()), 2), round(float(ends[:, 1].min()), 2), round(float(sill), 2)],
                           [round(float(ends[:, 0].max()), 2), round(float(ends[:, 1].max()), 2), round(float(sill + tall), 2)]]
                    found.append({'side': side, 'box': box, 'm2': round(wide * tall * float(panel.mean()), 1),
                                  'colour': (tint[texels].mean(0) * 255).round().astype(int).tolist(),
                                  'repair': {'part': 'roller door', 'box': box, 'radius': BLANK_RADIUS, 'slats': BLANK_SLATS}})
    kept = []  # told twice where one plane's shift held it whole both times, and from both faces of a thin door: the larger stays
    for one in sorted(found, key=lambda one: -one['m2']):
        # The two faces of a thin door look opposite ways and lie a door's thickness apart: along the way they face,
        # boxes within a wall plane of each other are one panel.
        reach = np.zeros(3); reach[0 if glow.SIDES[one['side']][0] else 1] = BLANK_PLANE
        low, high = np.array(one['box'], float) + [-reach, reach]
        if not any(one['side'] % 2 == other['side'] % 2 and (np.minimum(high, np.array(other['box'][1])) > np.maximum(low, np.array(other['box'][0]))).all() for other in kept):
            kept.append(one)
    return kept


def shipped_blank_panels(made, maps, smooth=None):
    """`blank_panels` of a finished model (`shape`) by its colour picture as it ships: retouched where it was, else as
    generated. Read at BLANK_SIZE: brought down to an eighth of its picture, the flecks that tell a blank door from a
    plain wall go, and the Ghost Riders garage's door was found from behind only. Where `shape` made a map of the
    model's places at that size for its lit parts (`placed`), it serves here too: making it again was a third of
    the garage's conversion after its shaping (46 of 58 seconds, 2026-11-16). A panel whose middle lies in a
    `smooth` box of the game set that draws `slats` is mended and left out: its joints are finer than the cells
    it is read by."""
    from PIL import Image
    placed = made.get('placed') if made.get('placed') is not None and made['placed'][1].shape[0] == BLANK_SIZE else None
    if made.get('colour') is not None:
        found = blank_panels(made['vertices'], made['uvs'], made['faces'], made['colour'], placed=placed)
    elif 'base_color' not in maps:
        return []
    else:
        with Image.open(maps['base_color']) as picture:
            found = blank_panels(made['vertices'], made['uvs'], made['faces'], picture, placed=placed)
    mended = [np.asarray(part['box'], float) for part in smooth or [] if 'slats' in part]
    middle = lambda one: np.asarray(one['box'], float).mean(0)
    return [one for one in found if not any((middle(one) >= box.min(0)).all() and (middle(one) <= box.max(0)).all() for box in mended)]


def blank_panels_of(shaped, models):
    """{name: its blank panels} of the models of a tile group that have any (`shipped_blank_panels`). shaped: {name:
    (made, maps)}, each a finished model of the game set `models`. Each model's map of places (`placed`) is let go
    once it is read by: it is large, and a group holds every model it places until it is built."""
    found = {}
    for name, (made, maps) in shaped.items():
        if panels := shipped_blank_panels(made, maps, models[name].get('smooth')):
            found[name] = panels
        made['placed'] = None
    return found


def blank_notes(name, panels):
    """What a build says of each blank panel found (`blank_panels`): where to look, and the entry that mends a door."""
    return [f'{name}: a panel of {one["m2"]} m² is drawn in one flat colour {one["colour"]} at {one["box"]}: look at it close up with `view --eye`; '
            f'a roller or bay door that lost its slats takes this under `smooth` (add "colour": [r, g, b] for another shade): {json.dumps(one["repair"])}'
            for one in panels]


def fire_values(part):
    """(at, width) of a fire a game set states: {at: [x, y, z], width}, metres on the finished model, where the game
    draws flames of its own (`fire_lines`)."""
    number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
    require(isinstance(part, dict) and {'at', 'width'} <= set(part) <= {'part', 'at', 'width'} and isinstance(part['at'], list) and len(part['at']) == 3
            and all(number(value) for value in part['at']) and number(part['width']) and FIRE_WIDTH[0] <= part['width'] <= FIRE_WIDTH[1],
            f'A fire is {{at: [x, y, z], width: {FIRE_WIDTH[0]} to {FIRE_WIDTH[1]} metres}} on the finished model')
    return [float(value) for value in part['at']], float(part['width'])


def fire_lines(name, number, part):
    """A fire as the game draws one: an emitter node at the fire's foot, the stock medium flame's (`plc_t05`, read from
    the game's own model on 2026-11-15: the flame sheet `fxpa_flame00` in sixteen frames, added to what is behind it,
    each particle added to what is behind it), its sizes scaled to the fire's width. The stock flame swells as it rises and hardly climbs, a ball of fire on the Ghost Riders barrel in the client; here each particle climbs its fire's width in its second of life and narrows, so the flames stand about twice as tall as the fire is wide. A generator makes flames a solid, still
    mesh (the Ghost Riders burn barrel; user, 2026-11-15: "we should remove the flames from the barrel and add that as
    a vfx"): clear them and state the fire. It burns by day and by night until a script puts it out (`fire_anim_lines`)."""
    (x, y, z), width = fire_values(part)
    values = {'deadspace': 0, 'blastRadius': 0, 'blastLength': 0, 'xgrid': 4, 'ygrid': 4, 'spawntype': 0, 'update': 'Fountain', 'render': 'Normal',
              'blend': 'Lighten', 'texture': 'fxpa_flame00', 'twosidedtex': 0, 'loop': 0, 'renderorder': 0, 'p2p': 0, 'p2p_sel': 1, 'affectedByWind': 0,
              'm_isTinted': 0, 'bounce': 0, 'random': 1, 'inherit': 1, 'inheritvel': 0, 'inherit_local': 0, 'splat': 0, 'inherit_part': 0,
              'alphaStart': 0.75, 'alphaMid': 0, 'alphaEnd': 0.1, 'colorStart': '0.254902 0.254902 0.254902', 'colorMid': '0 0 0', 'colorEnd': '1 1 1',
              'sizeStart': round(width * 2.0, 3), 'sizeMid': 0, 'sizeEnd': round(width * 1.0, 3), 'sizeStart_y': 0, 'sizeMid_y': 0, 'sizeEnd_y': 0,
              'birthrate': FIRE_BIRTHRATE, 'lifeExp': 1, 'mass': 0, 'spread': 0.2, 'particleRot': 0, 'velocity': round(width, 3), 'randvel': 0, 'bounce_co': 0,
              'blurlength': 10, 'fps': 24, 'frameStart': 0, 'frameEnd': 15, 'grav': 0, 'drag': 0, 'threshold': 0, 'combinetime': 0, 'percentStart': 0,
              'percentMid': 0, 'percentEnd': 0, 'lightningDelay': 0, 'lightningRadius': 0, 'lightningScale': 0, 'p2p_bezier2': 0, 'p2p_bezier3': 0,
              'xsize': round(width * 50), 'ysize': round(width * 50)}
    return [f'node emitter {name}_f{number}', f'  parent {name}', f'  position {x:.5f} {y:.5f} {z:.5f}', '  orientation 0 0 1 0',
            *(f'  {key} {value}' for key, value in values.items()), 'endnode']


def fire_anim_lines(name, fires):
    """The animations that put a model's fires out and light them again, as the stock flame's do (`plc_t05`): `on`,
    `off2on`, `on2off` and `off`, each keying every fire's birthrate. A placeable plays `on2off` then `off` when a
    script deactivates it (ANIMATION_PLACEABLE_DEACTIVATE) and `off2on` then `on` when it activates it; placed and left
    alone it burns by the birthrate of its emitter. Without them the Ghost Riders burn barrel's light went out with the
    lights and its flame burned on (2026-11-15). Their nodes are indented, so a line that starts `node emitter` is a
    fire of the model itself."""
    lines = []
    for anim, (first, last) in (('on', (FIRE_BIRTHRATE, FIRE_BIRTHRATE)), ('off2on', (0, FIRE_BIRTHRATE)), ('on2off', (FIRE_BIRTHRATE, 0)), ('off', (0, 0))):
        lines += [f'newanim {anim} {name}', f'  length {FIRE_ANIM:.7f}', '  transtime 0', f'  animroot {name}', f'  node dummy {name}', '    parent NULL', '  endnode']
        for number in range(fires):
            lines += [f'  node emitter {name}_f{number}', f'    parent {name}', '    birthratekey 2', f'      0 {first}', f'      {FIRE_ANIM:.7f} {last}', '    endlist', '  endnode']
        lines += [f'doneanim {anim} {name}']
    return lines


def compile_placeable(source, output):
    """Compile a placeable's ASCII model into `output`; returns the compiled paths. armorkit's compile reads each
    model back with a reader that knows only rigid dummy and mesh nodes, and refuses one with a fire's emitter. Such a
    model is checked in two halves: a twin without its fires goes through that compile and its read-back, so the
    meshes are checked as any prop's are; the model itself is compiled with the same pinned tool and decompiled
    again, and must still hold every fire and every face."""
    import tempfile
    from tools.armorkit import export, toolchain
    source, output = Path(source), Path(output); text = source.read_text(encoding='cp1252')
    fires = len(re.findall(r'(?m)^node emitter ', text))
    if not fires:
        return export.compile_models([source], output)
    require(source.parent.resolve() != output.resolve(), 'Compile into a folder other than the sources\'')
    output.mkdir(parents=True, exist_ok=True); target = output / source.name; target.unlink(missing_ok=True)
    tool = toolchain.cleanmodels(); run = lambda *said: subprocess.run([tool['path'], *said], capture_output=True, text=True, timeout=600,
                                                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    with tempfile.TemporaryDirectory() as scratch:
        twin = Path(scratch) / 'source' / source.name; twin.parent.mkdir()
        # the twin has neither the fires nor the animations that key them
        twin.write_text(re.sub(r'(?ms)^newanim .*?^doneanim [^\n]*\n', '', re.sub(r'(?ms)^node emitter .*?^endnode\n', '', text)), encoding='cp1252', newline='\n')
        export.compile_models([twin], Path(scratch) / 'compiled')
        result = run('compile', '--overwrite', '--json', str(source), str(target))
        require(result.returncode == 0 and target.is_file() and target.read_bytes()[:4] == b'\0\0\0\0',
                f'{source.name} did not compile: {(result.stdout + result.stderr)[-600:]}')
        back = Path(scratch) / 'back' / source.name; back.parent.mkdir()
        result = run('decompile', '--overwrite', str(target), str(back))
        require(result.returncode == 0 and back.is_file(), f'{source.name} compiled to a model that cannot be read back: {(result.stdout + result.stderr)[-600:]}')
        told = back.read_text(encoding='cp1252', errors='replace'); geometry = told.split('endmodelgeom')[0]
        faces = lambda told: sum(int(count) for count in re.findall(r'(?m)^\s*faces (\d+)', told))
        require(len(re.findall(r'(?m)^\s*newanim ', told)) == len(re.findall(r'(?m)^newanim ', text)),
                f'{source.name} compiled to a model without all of the animations that put its fires out')
        kept, wanted = (len(re.findall(r'(?m)^\s*node emitter ', geometry)), faces(geometry)), (fires, faces(text.split('endmodelgeom')[0]))
        require(kept == wanted, f'{source.name} compiled to a model of {kept[0]} fires and {kept[1]} faces, not its {wanted[0]} fires and {wanted[1]} faces')
    return [target]


def two_sided(points, normals, uvs, faces, tilt, *, gap=0.02):
    """(points, normals, uvs, faces) of a sign that reads the same from both sides: the front sheet leaning back `tilt`
    degrees and a half-turned copy of it behind, the two meeting along the top.

    A generator sees one side of a sandwich board. It invents the other (the sandwich board, 2026-11-10: scrambled
    lettering on the back) and guesses how the two halves stand (front sheet upright, rear one slanting). The front sheet
    is the part drawn from the reference, so it is the only part kept: everything within the sheet's own thickness of
    its face. The thickness is where the first empty band lies behind the face, measured on the surface of the lower
    half, under the hinge. The copy is turned, not mirrored, so its lettering reads the right way round."""
    require(0 <= tilt < 45, 'A sign leans back by less than 45 degrees')
    corners = points[faces]; of_face = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = np.linalg.norm(of_face, axis=1); unit = of_face / np.maximum(area, 1e-12)[:, None]
    middle = corners.mean(1); tall = float(np.ptp(points[:, 2]))
    # The sheet's face: the faces looking front that lie foremost. The rear sheet's inner side looks front too, from
    # further back, so the direction is found again from the foremost faces until it settles.
    front = np.array([0.0, 1.0, 0.0])
    for _ in range(3):
        facing = np.flatnonzero(unit @ front > 0.8)
        require(len(facing), 'The model has no face looking front')
        reach = middle[facing] @ front; foremost = facing[reach > np.percentile(reach, 98) - 0.05 * tall]
        front = of_face[foremost].sum(0); front /= np.linalg.norm(front)
    face = float(np.percentile(points[np.unique(faces[foremost])] @ front, 98))
    random = np.random.default_rng(0); pick = random.choice(len(faces), 40000, p=area / area.sum())
    weights = random.dirichlet((1, 1, 1), 40000); surface = (corners[pick] * weights[:, :, None]).sum(1)
    ordered = np.sort(face - surface[surface[:, 2] < points[:, 2].min() + tall / 2] @ front)  # 0 on the face, growing behind it
    steps = np.diff(ordered); empty = np.flatnonzero((steps > gap * tall) & (ordered[:-1] > 0))
    require(len(empty), 'Nothing stands apart behind the front sheet: not a two-sided sign')
    thick = float(ordered[empty[0]])
    keep = face - points @ front < thick + gap * tall / 2
    kept = faces[keep[faces].all(1)]; used = np.unique(kept)
    require(len(kept), 'The front sheet holds no faces')
    index = np.full(len(points), -1); index[used] = np.arange(len(used)); kept = index[kept]
    lean = np.radians(tilt); target = np.array([0.0, np.cos(lean), np.sin(lean)])
    cross, dot = np.cross(front, target), float(front @ target)
    skew = np.array([[0, -cross[2], cross[1]], [cross[2], 0, -cross[0]], [-cross[1], cross[0], 0]])
    turn = np.eye(3) + skew + skew @ skew / (1 + dot)  # the shortest turn that takes the sheet's face to its lean
    sheet, facing_out = points[used] @ turn.T, normals[used] @ turn.T
    # The hinge the copy turns about: the top of the sheet's back, so the two backs meet there and spread below.
    top = sheet[:, 2].max() - thick * np.sin(lean)
    centre = (sheet[:, 0].min() + sheet[:, 0].max()) / 2, (face - thick - top * np.sin(lean)) / np.cos(lean)
    behind = np.column_stack([2 * centre[0] - sheet[:, 0], 2 * centre[1] - sheet[:, 1], sheet[:, 2]])
    return (np.concatenate([sheet, behind]), np.concatenate([facing_out, facing_out * [-1, -1, 1]]), np.concatenate([uvs[used], uvs[used]]),
            np.concatenate([kept, kept + len(used)]))


def scatter(vertices, faces, spacing=0.04, seed=0, *, sources=False):
    """Points spread evenly over the mesh's surface, about `spacing` apart: upright faces show as well as level ones,
    which a view from above would miss. With `sources`, also each point's face and its weights on that face's corners."""
    corners = vertices[faces]; area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1) / 2
    count = np.maximum(1, np.ceil(area / spacing ** 2).astype(int)); pick = np.repeat(np.arange(len(faces)), count)
    weights = np.random.default_rng(seed).dirichlet((1, 1, 1), len(pick))
    points = (corners[pick] * weights[:, :, None]).sum(1)
    return (points, pick, weights) if sources else points


def light_gap(vertices, faces, at):
    """Metres from a placeable's cast light (`at`, on the finished model) to the nearest of the model. The game draws a
    flare where the light stands: one light set between a gate's two lamps, or over a row of three booths, hung a
    star in the air beside lamps that had none (the Ares and Saeder-Krupp gates and the Iron Sight Arms booths,
    2026-11-14). At a lamp's lens the flare is the lamp's; inside the model it is hidden and the light still reaches
    all round."""
    return float(np.linalg.norm(scatter(np.asarray(vertices, float), np.asarray(faces), spacing=0.03) - np.asarray(at, float), axis=1).min())


def split(faces, limit=NODE_VERTICES):
    """Face runs whose vertices each fit one mesh node: [(old vertex indices, faces renumbered to them)]."""
    parts, start = [], 0
    while start < len(faces):
        size = min(len(faces) - start, limit)
        while len(np.unique(faces[start:start + size])) > limit:
            size = size * 3 // 4
        used, renumbered = np.unique(faces[start:start + size], return_inverse=True)
        parts.append((used, renumbered.reshape(-1, 3))); start += size
    return parts


def card_normal_line(card):
    """A halo card's normal as a line of a model: the way the card faces."""
    from . import glow
    x, y, z = (glow.card_normal(card).round(5) + 0.0).tolist()  # rounded first: a zero keeps no sign
    return f'    {x:g} {y:g} {z:g}'


def model_text(name, vertices, normals, uvs, faces, cards=None, wire=None, glass=None, fire=None, embers=None):
    """The ASCII model. `wire` is a fence's sheets (`sheets`), which show `name`_w, a plain picture with gaps.
    `embers` is its beds of embers (`ember_beds`), one node that shows `name`_e as a halo's cards show theirs: it
    takes no light and its picture is in the glow slot of its own material file, so it is as bright by night as by day.
    `fire` is the fires the game draws on it ([{at, width}], `fire_lines`), each an emitter node.
    `glass` is its panes (`glazed`), each a node that shows its patch of `name`_g, added to what is behind it as the
    halo's cards are, and lit as the model is.
    `cards` are a halo's sheets (`glow.halo`), four corners each, all showing `name`_h. That
    texture's TXI makes the game add them to what is behind. They take no light (ambient and diffuse are black) and show
    their picture through the glow slot of their own material file, so they are as bright by night as by day. (A
    `selfillumcolor` line would do the same, but the compiled model then fails the read-back check, which knows no such
    controller.)"""
    require(len(name) <= NAME_LENGTH and name == name.lower() and name.replace('_', '').isalnum(),
            f'A model name is a lowercase resref of at most {NAME_LENGTH} characters: {name}')
    require(all(np.isfinite(values).all() for values in (vertices, normals, uvs)), name + ': a coordinate is not a number')
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', 'classification CHARACTER', f'setsupermodel {name} NULL', 'setanimationscale 1',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode']
    for number, (used, part) in enumerate(split(faces)):
        lines += [f'node trimesh {name}_m{number}', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0',
                  '  shininess 1', f'  bitmap {name}', '  render 1', '  shadow 0', f'  verts {len(used)}']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in vertices[used].tolist()]
        lines += [f'  tverts {len(used)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in uvs[used].tolist()]
        lines += [f'  normals {len(used)}'] + [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in normals[used].tolist()]
        lines += [f'  faces {len(part)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in part.tolist()] + ['endnode']
    for number, (used, part) in enumerate(split(wire['faces']) if wire else []):
        lines += [f'node trimesh {name}_w{number}', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0',
                  '  shininess 1', f'  bitmap {name}_w', '  render 1', '  shadow 0', f'  verts {len(used)}']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in wire['vertices'][used].tolist()]
        lines += [f'  tverts {len(used)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in wire['uvs'][used].tolist()]
        lines += [f'  normals {len(used)}'] + [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in wire['normals'][used].tolist()]
        lines += [f'  faces {len(part)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in part.tolist()] + ['endnode']
    for number, card in enumerate(cards or []):
        lines += [f'node trimesh {name}_halo{number}', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {name}_h', '  render 1', '  shadow 0', '  transparencyhint 1', '  verts 4']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for (x, y, z), _ in card] + ['  tverts 4'] + [f'    {u:.5f} {v:.5f} 0' for _, (u, v) in card]
        lines += ['  normals 4'] + [card_normal_line(card)] * 4 + ['  faces 2', '    0 1 2 1 0 1 2 1', '    0 2 3 1 0 2 3 1', 'endnode']
    for number, pane in enumerate(glass or []):
        lines += [f'node trimesh {name}_g{number}', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {name}_g', '  render 1', '  shadow 0', '  transparencyhint 1', f'  verts {len(pane["vertices"])}']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in pane['vertices'].tolist()]
        lines += [f'  tverts {len(pane["uvs"])}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in pane['uvs'].tolist()]
        lines += [f'  normals {len(pane["normals"])}'] + [f'    {x + 0.0:.5f} {y + 0.0:.5f} {z + 0.0:.5f}' for x, y, z in pane['normals'].tolist()]
        lines += [f'  faces {len(pane["faces"])}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in pane['faces'].tolist()] + ['endnode']
    if embers is not None:
        lines += [f'node trimesh {name}_e0', f'  parent {name}', '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1',
                  f'  bitmap {name}_e', '  render 1', '  shadow 0', f'  verts {len(embers["vertices"])}']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in embers['vertices'].tolist()]
        lines += [f'  tverts {len(embers["uvs"])}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in embers['uvs'].tolist()]
        lines += [f'  normals {len(embers["normals"])}'] + [f'    {x + 0.0:.5f} {y + 0.0:.5f} {z + 0.0:.5f}' for x, y, z in embers['normals'].tolist()]
        lines += [f'  faces {len(embers["faces"])}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in embers['faces'].tolist()] + ['endnode']
    for number, part in enumerate(fire or []):
        lines += fire_lines(name, number, part)
    return '\n'.join(lines + [f'endmodelgeom {name}', *(fire_anim_lines(name, len(fire)) if fire else []), f'donemodel {name}']) + '\n'


def material_text(name, illumination=False):
    lines = ['renderhint NormalAndSpecMapped', '', f'texture0 {name}', f'texture1 {name}_n', f'texture2 {name}_s', f'texture3 {name}_r',
             'texture4 null', f'texture5 {name}_i' if illumination else 'texture5 null']
    return '\n'.join(lines) + '\n'


def outline(points, sides=8):
    """The model's footprint as a polygon of at most `sides` corners that holds every point: the lines square to
    `sides` evenly spaced directions, each pushed out to the farthest point, cut where neighbours meet. A box comes out
    as its own four corners (north-east first, counter-clockwise); a heap or a thing on an arm loses its empty corners."""
    flat = np.asarray(points, float)[:, :2]; angles = np.arange(sides) * 2 * np.pi / sides
    square = np.stack([np.cos(angles), np.sin(angles)], 1); reach = (flat @ square.T).max(0); corners = []
    for index in range(sides):
        after = (index + 1) % sides
        corner = np.linalg.solve(square[[index, after]], reach[[index, after]])
        if not corners or np.abs(corner - corners[-1]).max() > 1e-4:
            corners.append(corner)
    if len(corners) > 1 and np.abs(corners[0] - corners[-1]).max() <= 1e-4:
        corners.pop()
    return [(round(float(x), 6) + 0.0, round(float(y), 6) + 0.0) for x, y in corners]


def standing(vertices, faces):
    """The parts of a model that stand in a walker's way, each as its points: what of its surface lies under head
    height (OVERHEAD), told apart wherever WALK_GAP of clear ground lies between (parts nearer than a quarter of it are one). A gantry crane is two legs and a beam
    twelve metres up: one block on its whole footprint shut the track it spans (user, 2026-11-15: "the crane
    placeable should NOT block walking underneath it")."""
    vertices = np.asarray(vertices, float)  # its own corners with the places spread over its faces: a block's corners are the model's
    points = np.vstack([vertices, scatter(vertices, np.asarray(faces), spacing=WALK_GAP / WALK_CELLS)]); points = points[points[:, 2] < OVERHEAD]
    require(len(points), 'Nothing of the model stands under head height: it is hung overhead and needs no parts to walk between')
    # Cells a quarter of the gap across: two that hold points are one part only where no two points in them can lie
    # the gap apart, so ground WALK_GAP clear and more is never closed, wherever the model lies on the cells. (Cells
    # the gap across joined posts 0.8 m apart that fell in neighbouring cells: found in review, 2026-11-15.)
    fine = WALK_GAP / WALK_CELLS; near = [(c, d) for c in range(-WALK_CELLS, WALK_CELLS + 1) for d in range(-WALK_CELLS, WALK_CELLS + 1)
                                          if (c or d) and (abs(c) + 1) ** 2 + (abs(d) + 1) ** 2 <= WALK_CELLS ** 2]
    cell = np.floor(points[:, :2] / fine).astype(int); cell -= cell.min(0); grid = np.zeros(cell.max(0) + 1, int); grid[tuple(cell.T)] = -1; parts = 0
    for start in zip(*np.nonzero(grid)):
        if grid[start] != -1:
            continue
        parts += 1; grid[start] = parts; stack = [start]
        while stack:
            a, b = stack.pop()
            for c, d in near:
                c, d = a + c, b + d
                if 0 <= c < grid.shape[0] and 0 <= d < grid.shape[1] and grid[c, d] == -1:
                    grid[c, d] = parts; stack.append((c, d))
    part = grid[tuple(cell.T)]
    return [points[part == number] for number in range(1, parts + 1)]


def walk_text(name, vertices, *, overhead=False, blocks=None):
    """Collision: an upright block on the model's footprint (`outline`), as tall as the model, and where a character
    stands to use it (in front and behind). `overhead` leaves the block out: a thing hung above head height is walked
    under. `blocks` are the points of each part that stands on the ground (`standing`), a block for each in place of
    the one: a thing on legs is walked under between them."""
    vertices = np.asarray(vertices, float); (x0, y0, _), (x1, y1, z1) = vertices.min(0), vertices.max(0); lines = []
    if not overhead:
        verts, faces = [], []
        for block in [vertices] if blocks is None else blocks:
            corners = outline(block); count = len(corners); first = len(verts)
            verts += [(x, y, 0.0) for x, y in corners] + [(x, y, z1) for x, y in corners]
            sides = [face for index in range(count) for face in ((index, (index + 1) % count, (index + 1) % count + count), (index, (index + 1) % count + count, index + count))]
            sides += [(count, count + index, count + index + 1) for index in range(1, count - 1)]
            faces += [tuple(corner + first for corner in face) for face in sides]
        lines = [f'node trimesh {name}_wg', f'  parent {name}_pwk', '  position 0 0 0', '  orientation 0 1 0 0', f'  verts {len(verts)}']
        lines += [f'    {x:.5f} {y:.5f} {z:.5f}' for x, y, z in verts]
        lines += [f'  faces {len(faces)}'] + [f'    {a} {b} {c} 1 0 0 0 {NON_WALK}' for a, b, c in faces] + ['endnode']
    for number, y in ((1, y1 + 0.5), (2, y0 - 0.5)):
        lines += [f'node dummy {name}_pwk_use0{number}', f'  parent {name}_pwk', f'  position 0 {y:.5f} 0', '  orientation 0 1 0 0', 'endnode']
    return '\n'.join(lines) + '\n'


def specular(base, metallic):
    """Head-on reflectance as one channel, 0-1: a non-metal's small fixed share, a metal's own brightness."""
    luminance = base[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    return DIELECTRIC + (luminance - DIELECTRIC) * metallic


COMPRESSED = Path(__file__).resolve().parents[2] / 'output' / 'envkit' / 'cache' / 'dds'  # ignored: maps as compressed, by what they were compressed from


def _compress(image, target, mode, size, crunch, *, data):
    """One PNG through the texture compressor to a mipmapped DDS. `data` maps are filtered without gamma.

    The same picture compressed the same way by the same compressor is copied from COMPRESSED, where each is kept under
    the hash of all three: a group built again after a change to its fence or its path nodes compressed every map
    again, about a third of each of the Shiawase Barrens power station's seven builds (2026-11-17). ENVKIT_NO_CACHE
    set compresses anew."""
    import hashlib, io, os, shutil
    pixels = io.BytesIO(); image.resize((size, size)).save(pixels, 'PNG'); tool = Path(crunch)
    renormal = ['-renormalize'] if mode == '-DXN' else []; settings = [mode, '-mipMode', 'Generate', '-noprogress', '-gamma', '1.0' if data else '2.2', *renormal]
    stamp = [tool.name, tool.stat().st_size, tool.stat().st_mtime_ns] if tool.is_file() else [str(crunch)]
    kept = COMPRESSED / (hashlib.sha256(pixels.getvalue() + repr([settings, stamp]).encode()).hexdigest() + '.dds')
    if kept.is_file() and not os.environ.get('ENVKIT_NO_CACHE'):
        shutil.copyfile(kept, target); return target
    source = target.with_suffix('.source.png'); source.write_bytes(pixels.getvalue())
    command = [crunch, '-file', str(source), '-out', str(target), '-fileformat', 'dds', *settings]
    result = subprocess.run(command, capture_output=True, text=True, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    source.unlink()
    require(result.returncode == 0 and target.is_file(), f'{target.name} did not compress: {(result.stdout + result.stderr)[-400:]}')
    if not os.environ.get('ENVKIT_NO_CACHE'):
        kept.parent.mkdir(parents=True, exist_ok=True); part = kept.with_suffix('.part'); shutil.copyfile(target, part); part.replace(kept)
    return target


def _blur(values, radius):
    """`values` (rows, columns, ...) blurred over about `radius` texels: three box blurs, near enough a Gaussian. Beyond
    the picture's edge there is nothing, so a blur of a mask says how much of each texel's neighbourhood was counted."""
    width = max(int(round(radius)), 1)
    for _ in range(3):
        for axis in (0, 1):
            pad = [(width + 1, width) if at == axis else (0, 0) for at in range(values.ndim)]
            total = np.cumsum(np.pad(values, pad), axis); count = values.shape[axis]
            values = (np.take(total, np.arange(2 * width + 1, 2 * width + 1 + count), axis) - np.take(total, np.arange(count), axis)) / (2 * width + 1)
    return values


def _soften(values, chosen, reach):
    """(box, soft, near): `values` (rows, columns) or (rows, columns, channels) blurred over `reach` texels among the
    `chosen` texels alone, which take nothing from what lies outside them. Only the texels the blur can reach are
    worked on: `box`, the chosen ones' own rows and columns and three reaches round them, which is as far as three box
    blurs carry anything out and back. `soft` is that box blurred, and `near` where in it the blur reached: the chosen
    texels and a margin past them, onto which their tones are carried."""
    rows, columns = np.flatnonzero(chosen.any(1)), np.flatnonzero(chosen.any(0)); pad = 3 * max(int(round(reach)), 1) + 1
    box = (slice(max(int(rows[0]) - pad, 0), int(rows[-1]) + pad + 1), slice(max(int(columns[0]) - pad, 0), int(columns[-1]) + pad + 1))
    mask = chosen[box].astype(np.float32); share = _blur(mask, reach); count = np.maximum(share, 1e-6)
    if values.ndim == 3:
        mask, count = mask[..., None], count[..., None]
    return box, _blur(values[box] * mask, reach) / count, share > 1e-3


def _spread(small, parts):
    """(picture, texels): `small`, a picture at the retouching's grain, with each part smoothed among its own texels
    in turn, and all the texels that changed together. parts: [(texels, reach, colour)], the colour (0-255) what the
    part is brought to on average, or None. Each part's tones are carried a little past its texels where no part lies,
    so that the picture enlarged has the part's own tones at its edge and not its neighbour's on the texture.

    A part of four, (texels, reach, None, marked), is a marking taken off a surface: its `texels` are the surface left
    as it is, and only the `marked` ones change, each to the surface about it blurred over the reach."""
    small = small.copy(); edged = small.copy(); done = np.zeros(small.shape[:2], bool)
    for chosen, reach, toward, *marked in parts:
        box, soft, near = _soften(small, chosen, reach); here = chosen[box]
        if marked:
            reached = np.zeros(chosen.shape, bool); reached[box] = near  # of the whole picture: a marking on an island of its own lies outside the box
            require(bool(reached[marked[0]].all()), 'A marking is filled from the surface about it, within its radius: this one lies further from any')
            here = marked[0][box]
            small[box][here] = soft[here]; edged[box][here] = soft[here]; done |= marked[0]
            continue
        if toward is not None:
            soft = soft * (np.asarray(toward, np.float32) / 255 / np.maximum(soft[here].mean(0), 1e-6))
        small[box][here] = soft[here]  # what the next part sees
        over = (near & ~done[box]) | here; edged[box][over] = soft[over]; done |= chosen
    return edged, done


def _levelled(values, plain):
    """A grey map (0-1) with what `retouch` smoothed off the colour picture smoothed off it too: `plain` is each
    smoothed part's texels and its reach among them (and its marked texels, for a marking), as the colour was smoothed. The generator that painted the Ares
    Depot's fence on the wall behind it put the same mesh into the wall's roughness and metallic, which the colour's
    smoothing left there to catch the light (2026-11-12)."""
    from PIL import Image
    grain = plain[0][0].shape[0]; size = values.shape[::-1]
    small = np.asarray(Image.fromarray((values * 255).round().astype(np.uint8)).resize((grain, grain), Image.BOX), np.float32) / 255
    small, done = _spread(small, [(chosen, reach, None, *marked) for chosen, reach, *marked in plain])
    wide = np.asarray(Image.fromarray((np.clip(small, 0, 1) * 255).round().astype(np.uint8)).resize(size, Image.BILINEAR), float) / 255
    marked = np.asarray(Image.fromarray(done).resize(size, Image.NEAREST)); values = values.copy(); values[marked] = wide[marked]
    return values


def _run(places):
    """The way a flat upright panel runs, a unit (x, y), from the places of its texels: the line they lie along seen
    from above. A panel within a degree of an axis runs along it exactly, so its pattern does not creep."""
    flat = np.asarray(places, float)[:, :2]; flat = flat - flat.mean(0)
    require(len(flat) > 1 and float(np.abs(flat).max()) > 1e-6, 'A wire mesh panel has a length to run along')
    ahead = np.linalg.eigh(flat.T @ flat)[1][:, -1]
    if ahead[0] < -1e-9 or (abs(ahead[0]) <= 1e-9 and ahead[1] < 0):  # towards +x, or +y for a panel along Y: one way for both faces
        ahead = -ahead
    if float(np.abs(ahead).max()) >= np.cos(np.radians(1.0)):
        ahead = (np.abs(ahead) == np.abs(ahead).max()).astype(float)
    across = flat @ np.array([-ahead[1], ahead[0]])
    require(float(np.ptp(across)) <= PANEL_DEPTH, f'A wire mesh box holds one flat panel: what this one holds is {float(np.ptp(across)):.2f} metres deep across its run')
    return ahead


def sheets(fences, size=WIRE_PICTURE, frame=None, colours=None):
    """Chain-link sheets hung between a fence's posts: {vertices, normals, uvs, faces, image}, a mesh of its own.

    fences: [{from: [x, y], to: [x, y], z: [low, high], pitch, wire, colour}] on the finished model; a sheet stands
    upright from one point to the other and is seen from both sides. A generator leaves a fence's frames empty and
    paints the mesh on whatever stands behind (the Ares Depot's perimeter, seen from an angle in the client,
    2026-11-11). The wires are drawn on `image`, a small picture of their own that is see-through between them, as
    many links of the pattern as leave a wire its pixels; the model's colour picture keeps its size and stays opaque
    (with an alpha channel the depot's, at 4096 pixels, was 22 MB). Each sheet is cut into squares one picture across,
    so a tile group can share them out among its tiles.

    frame: the fence's posts, rails, coils and gateway posts, [{tube: [from, to], radius, cap}], [{coil: [from, to],
    radius, pitch}] or [{block: [foot, top], size}], made as faces of the same mesh. The picture is then FRAME_SHEET
    times as wide and high, the wires in its first corner and steel and concrete beside them (`frame_picture`) in the
    tones `colours` {steel, concrete}; without a frame it is the wires alone, as it was."""
    from PIL import Image
    first = fences[0]; pitch, wire, colour = first['pitch'], first['wire'], list(first.get('colour', WIRE))
    require(all((one['pitch'], one['wire'], list(one.get('colour', WIRE))) == (pitch, wire, colour) for one in fences), 'The fences of a model share one wire mesh')
    link = pitch * np.sqrt(2)  # the pattern repeats every `link` metres along and up
    links = int(wire * size / (WIRE_TEXELS * link)); require(links >= 1, f'A wire this thin cannot be drawn on a picture of {size} pixels')
    from . import glow
    share = 1.0 / FRAME_SHEET if frame else 1.0; whole = size * FRAME_SHEET if frame else size  # the wires go on past their corner, so no edge of it shows
    period = links * link; at = (np.arange(whole) + 0.5) / size * period; along, up = np.meshgrid(at, at)
    drawn = glow.wires(along, up, pitch, wire)  # the pattern a `mesh` panel is painted with
    pixels = np.empty((whole, whole, 4), np.uint8); pixels[..., :3] = colour; pixels[..., 3] = drawn * 255  # the wire's colour under the gaps too
    if frame:
        frame_picture(pixels, {**FRAME_COLOURS, **(colours or {})})
    vertices, normals, uvs, faces = [], [], [], []
    for one in fences:
        start, end = np.asarray(one['from'], float), np.asarray(one['to'], float); low, high = (float(value) for value in one['z'])
        length = float(np.linalg.norm(end - start)); ahead = (end - start) / length; out = np.array([ahead[1], -ahead[0], 0.0])
        for i in range(int(np.ceil(length / period - 1e-9))):
            for j in range(int(np.ceil((high - low) / period - 1e-9))):
                s0, z0 = i * period, low + j * period; s1, z1 = min(length, s0 + period), min(high, z0 + period)
                corners = [(s0, z0), (s1, z0), (s1, z1), (s0, z1)]
                place = [[*(start + ahead * s), z] for s, z in corners]; spot = [[(s - s0) / period * share, (z - z0) / period * share] for s, z in corners]
                for way, order in ((out, ((0, 1, 2), (0, 2, 3))), (-out, ((0, 2, 1), (0, 3, 2)))):  # a face each way, each with its own normals
                    base = len(vertices); vertices += place; normals += [way.tolist()] * 4; uvs += spot
                    faces += [[base + a, base + b, base + c] for a, b, c in order]

    def laid(kind, spots, low=0.02, high=0.98):
        u0, u1 = FRAME_COLUMNS[kind]
        return np.stack([u0 + FRAME_MARGIN + spots[:, 0] * (u1 - u0 - 2 * FRAME_MARGIN), low + spots[:, 1] * (high - low)], 1)
    for part in frame or ():
        if 'tube' in part:
            (start, end) = part['tube']; points, outward, spots, local = tube(start, end, part['radius'], part.get('cap', False))
            stood = abs(end[2] - start[2]) > 0.9 * float(np.linalg.norm(np.subtract(end, start)))  # a post shows the column from its foot; a rail its clean middle
            spots = laid('steel', spots) if stood else laid('steel', spots, 0.35, 0.65)
        elif 'block' in part:
            points, outward, spots, local = block(part['block'][0], part['block'][1], part['size']); spots = laid('concrete', spots)
        else:
            points, outward, local = coil(part['coil'][0], part['coil'][1], part['radius'], part['pitch']); spots = laid('steel', np.full((len(points), 2), 0.5))
        base = len(vertices); vertices += points.tolist(); normals += outward.tolist(); uvs += spots.tolist(); faces += (local + base).tolist()
    return {'vertices': np.array(vertices), 'normals': np.array(normals), 'uvs': np.array(uvs), 'faces': np.array(faces), 'image': Image.fromarray(pixels, 'RGBA'),
            'period': period}


def _copied(colour, where, covered, target, source, part, kept=None):
    """`colour` with the texels of `target` showing what the texels of `source` show: a stretch of a wall laid over
    something the generator left blank or drew wrongly beside it (the Iron Sight Arms range wing came back with a plain
    grey slab on its rear end and its lettering mirrored on its far wall; user, 2026-11-14: "can you copy the wall
    texture over it?"). The source is read as a picture of its wall, by metres along the way it runs and metres up, and
    the target is given it by its own metres along and up: each height keeps its own band of the wall, and a target
    longer than the source takes it again from the start. With `mirror` in the part the target takes it from its far
    end backwards: the clean half of something drawn the same both ways, laid over its other half (the Chop Shop
    clinic's banner came back with the right half of its caduceus smeared, 2026-11-14). With `rise`, metres, each
    height of the target takes the wall that much higher (lower, if less than nothing): a band that sags along its
    length meets its copy a step out otherwise (that banner's stripes, 1.5 cm lower two stripes along). `target` and
    `source` are texels of the map of places. `kept`, a dict, holds the map of places at the picture's size from one
    copied part of a model to the next: it is the same for each, and four resizes of the whole picture to make."""
    from PIL import Image
    size = (colour.shape[1], colour.shape[0]); kept = {} if kept is None else kept
    if 'place' not in kept:
        up = lambda values: np.asarray(Image.fromarray(np.ascontiguousarray(values, np.float32), 'F').resize(size, Image.BILINEAR), np.float32)
        weight = np.maximum(up(covered), 1e-6); kept['place'] = np.dstack([up(where[..., axis] * covered) / weight for axis in range(3)])
    place = kept['place']
    full = lambda mask: np.asarray(Image.fromarray(mask).resize(size, Image.NEAREST))
    what = str(part.get('part', 'copied part'))

    def laid(mask):  # each texel's metres along the way its part runs and its metres up, and whether it lies on the part
        # A texel at the edge of the part's patch of the picture has its place blended with the patch beside it, which
        # may be anywhere on the model: read as part of the wall, such texels made it longer than it is and filled the
        # added length with blotches (the Iron Sight Arms shop's back wall, 2026-11-14). The part reaches only as far
        # as the map of places itself has it.
        exact = where[mask]; run = int(np.argmax(np.ptp(exact[:, :2], axis=0))); spots = place[full(mask)][:, [run, 2]]
        low, high = exact[:, [run, 2]].min(0), exact[:, [run, 2]].max(0)
        return np.clip(spots[:, 0], low[0], high[0]), np.clip(spots[:, 1], low[1], high[1]), np.all((spots >= low) & (spots <= high), axis=1)
    along, height, on = laid(source); along, height, texels = along[on], height[on], colour[full(source)][on]
    wide, tall = float(np.ptp(along)), float(np.ptp(height))
    require(wide > 0.05 and tall > 0.05, 'A copied wall has a length and a height: ' + what)
    # A cell is a texel of the wall as most of it is drawn (the usual step between two of its texels side by side). A
    # generated model spends its picture unevenly: where the wall is drawn coarser, cells are left empty and filled below.
    beside = source[:, 1:] & source[:, :-1]
    step = float(np.median(np.linalg.norm(where[:, 1:][beside] - where[:, :-1][beside], axis=1))) * covered.shape[1] / size[0] if beside.any() else 0.0
    cell = max(1.25 * step, float(np.sqrt(wide * tall / len(along))), max(wide, tall) / 2048)
    columns, rows = max(int(np.ceil(wide / cell)), 1), max(int(np.ceil(tall / cell)), 1)
    at = (np.minimum(((height - height.min()) / cell).astype(int), rows - 1), np.minimum(((along - along.min()) / cell).astype(int), columns - 1))
    total = np.zeros((rows, columns, 3), np.float64); count = np.zeros((rows, columns)); np.add.at(total, at, texels); np.add.at(count, at, 1)
    share = float((count > 0).mean())
    require(share > 0.1, f'The wall copied from covers {share:.0%} of its box, under a tenth: {what}')
    wall = total / np.maximum(count, 1)[..., None]; known = count > 0
    while not known.all():  # a cell no texel fell in takes the mean of its neighbours that have one
        sums = np.zeros_like(wall); near = np.zeros(known.shape)
        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            moved, had = np.roll(wall * known[..., None], shift, axis), np.roll(known, shift, axis).astype(float)
            edge = [slice(None)] * 2; edge[axis] = 0 if shift == 1 else -1; had[tuple(edge)] = 0  # nothing comes round the edge
            sums += moved * had[..., None]; near += had
        fresh = ~known & (near > 0); wall[fresh] = sums[fresh] / near[fresh][:, None]; known |= fresh
    over = full(target); along_t, height_t, _ = laid(target); height_t = height_t + float(part.get('rise', 0.0))
    require(height_t.max() > height.min() and height_t.min() < height.max(), 'A wall is copied to its own heights, and the two boxes share none: ' + what)
    row = np.clip(((height_t - height.min()) / cell).astype(int), 0, rows - 1)
    run = along_t.max() - along_t if part.get('mirror') else along_t - along_t.min()
    column = np.clip(((run % max(wide, cell)) / cell).astype(int), 0, columns - 1)
    colour[over] = wall[row, column]
    return colour


def retouch(image, vertices, uvs, faces, *, tone=None, paint=(), copy=(), smooth=(), mesh=(), size=RETOUCH, placed=None):
    """(colour, flat, plain): a model's colour picture as it ships, where its relief is to be flattened, and where its
    other maps are to be smoothed as its colour was: [(texels, reach in texels)] for each smoothed part, with its marked
    texels third for a marking, at the retouching's own grain (the last two, or None). `placed` is the model's position map at that grain
    (`glow.position_map`: where, covered), for a caller that has made one already.

    `tone` multiplies the whole picture (a model that came back paler than its reference), by one number or by one
    each for red, green and blue (a building's piece that came back another shade than the piece it stands against:
    the Iron Sight Arms range wing, paler and greyer than its shop; user, 2026-11-14). `paint` covers what a
    generator invented: [{box, colour}], every texel within the box in one colour (0-255). `copy` covers it with the
    wall beside it instead: [{box, from}], the texels within `box` showing the wall within the box `from`, height for
    height, or its mirror image with `mirror` (`_copied`), after the painting and before the smoothing. `mesh` makes a panel a
    chain-link fence: [{box, pitch, wire, colour}], the texels within the box in the wire's colour and see-through
    between the wires (`glow.wires`), which gives the picture an alpha channel; the pattern is laid along the way the
    panel runs (`_run`), whichever way that is. Boxes are in metres on the finished
    model, as a lit part's are. A generator cannot make a mesh that is seen through (the depot's fence came back as
    solid smeared panels, 2026-11-11); its posts, rails and base are kept and only the panels are redrawn.

    `smooth` takes a pattern off a surface and leaves its tones: [{box, radius, colour}], the texels within the box
    blurred over `radius` metres among themselves, then brought to `colour` on average if one is given, and their
    relief levelled (a wall the generator painted a fence's mesh on); `plain` has `textures` take the pattern off the
    roughness and the metal too. With `tint` in place of `colour` it takes a tinted marking off and leaves the surface,
    grain and all: only the texels whose tint (their colour less its own grey) is more than `tint` levels (0-255) from
    the box's usual tint change, each to the rest of the box blurred over `radius`. The surface is most of the box and
    the less tinted of the two; a box that is mostly marking, or a plain marking on a tinted surface, is refused (the smeared red marking on the
    concrete base of the Ares fence section, which smoothing the whole face left a plain panel beside weathered ones,
    2026-11-12). With `slats`, metres, the smoothed surface is drawn again as a roller door's slats, a joint every `slats`
    metres up the model, darkened over SLAT_GROOVE of the pitch each side by up to SLAT_SHADE: a generator draws slats
    finer than its texels as a wavy moiré (the Saeder-Krupp yard's dock doors L-01 and L-02, user, 2026-11-12). A pitch is
    refused under four texels, where the joints would alias again."""
    from PIL import Image
    from . import glow
    colour = np.asarray(image.convert('RGB'), np.float32) / 255; alpha = flat = None; grain = min(size, image.width)
    plain = [] if smooth else None
    if tone is not None:
        colour = np.clip(colour * np.asarray(tone, np.float32), 0, 1)
    if smooth or mesh:
        flat = np.zeros(colour.shape[:2], bool)
    if mesh:
        alpha = np.ones(colour.shape[:2], bool)
    if paint or copy or smooth or mesh:
        where, covered = placed if placed is not None else glow.position_map(vertices, uvs, faces, grain)
        require(covered.shape == (grain, grain), f'The position map handed to the retouching is {grain} texels across')
        full = lambda mask: np.asarray(Image.fromarray(mask).resize(image.size, Image.NEAREST))
        for part in paint:
            colour[full(glow.held(where, covered, part, 'painted'))] = np.asarray(part['colour'], float) / 255
        places = {}
        for part in copy:
            colour = _copied(colour, where, covered, glow.held(where, covered, part, 'copied-over'),
                             glow.held(where, covered, {'box': part['from'], 'part': f"{part.get('part', 'copied part')}, the wall copied from"}, 'copied'), part, places)
        rise = None
        for part in smooth:
            chosen = glow.held(where, covered, part, 'smoothed')
            beside = chosen[:, 1:] & chosen[:, :-1]  # how far apart on the model two texels side by side are
            step = float(np.median(np.linalg.norm(where[:, 1:][beside] - where[:, :-1][beside], axis=1))) if beside.any() else 0.0
            # No two texels side by side, or all at one place, leaves no step to measure by: the reach then stops at an
            # eighth of the picture, where an unbounded one would pad the blur by a hundred thousand texels.
            plain.append((chosen, max(int(round(min(part['radius'] / max(step, 1e-6), grain / 8))), 1)))
            if 'slats' in part:  # the height a texel spans, at the picture's own size, where the slats are drawn
                if rise is None:
                    rise = np.hypot(*np.gradient(where[..., 2]))
                drawn = float(np.median(rise[chosen])) * grain / image.width
                require(part['slats'] >= 4 * drawn, f"Slats {part['slats']} metres apart are under four texels of {drawn:.3f} metres in height "
                        f"each: the joints would alias as the generator's did ({part.get('part', 'smoothed')})")
        if smooth:  # the picture is brought to the grain once, each part is smoothed there in turn, and it is brought back once
            small = np.asarray(Image.fromarray((colour * 255).round().astype(np.uint8)).resize((grain, grain), Image.BOX), np.float32) / 255
            for index, part in enumerate(smooth):
                if 'tint' in part:  # a marking: the tinted texels, and three texels round them for their soft edge
                    chosen, reach = plain[index]; tint = small - small.mean(-1, keepdims=True)
                    marked = chosen & (np.abs(tint - np.median(tint[chosen], 0)).max(-1) * 255 > part['tint'])
                    marked = chosen & (_blur(marked.astype(np.float32), 1) > 0.02)
                    require(bool(marked.any()) and bool((chosen & ~marked).any()), 'A marking is tinted texels on a surface that is not: the box holds '
                            + ('nothing but tint' if marked.any() else 'no tint') + ' (' + str(part.get('part', 'smoothed')) + ')')
                    # The box's usual tint is taken for the surface's. In a box that is mostly marking it is the marking's,
                    # and the surface would be what is taken off. Which of the two is the marking cannot be told from
                    # their shares, so it is told by tint: the marking is the more tinted, and a plain marking on a
                    # tinted surface is not taken off this way.
                    strength = np.abs(tint).max(-1)
                    require(float(strength[marked].mean()) > float(strength[chosen & ~marked].mean()), 'A marking is more tinted than the surface it lies on, and here '
                            'what would be taken off is the less tinted: either most of the box is the marking (widen it to hold more of the surface), or the marking '
                            'is a plain one on a tinted surface, which tint does not take off (' + str(part.get('part', 'smoothed')) + ')')
                    plain[index] = (chosen & ~marked, reach, marked)
            small, done = _spread(small, [(chosen, reach, part.get('colour'), *marked) for (chosen, reach, *marked), part in zip(plain, smooth)])
            wide = np.asarray(Image.fromarray((np.clip(small, 0, 1) * 255).round().astype(np.uint8)).resize(image.size, Image.BILINEAR), np.float32) / 255
            done = full(done); colour[done] = wide[done]; flat |= done
            if any('slats' in part for part in smooth):  # the joints by the model's own height, read at the picture's size
                # Read as covered texels only: the empty texels round an island hold 0, which a plain resize blends into its edge.
                up = lambda values: np.asarray(Image.fromarray(values.astype(np.float32), 'F').resize(image.size, Image.BILINEAR), np.float32)
                height = up(where[..., 2] * covered) / np.maximum(up(covered), 1e-6); joints = np.zeros(height.shape, np.float32)
                for (chosen, *_), part in zip(plain, smooth):
                    if 'slats' in part:  # where two boxes of a door meet, a texel is darkened once
                        texels = full(chosen); phase = (height[texels] / part['slats']) % 1.0
                        joints[texels] = np.maximum(joints[texels], np.clip(1 - np.minimum(phase, 1 - phase) / SLAT_GROOVE, 0, 1))
                colour *= (1 - SLAT_SHADE * joints)[..., None]
        for part in mesh:
            panel = glow.held(where, covered, part, 'wire mesh'); ahead = _run(where[panel])
            wire = full(panel & glow.wires(where[..., :2] @ ahead, where[..., 2], part['pitch'], part['wire'])); panel = full(panel)
            colour[panel] = np.asarray(part.get('colour', WIRE), float) / 255  # under the gaps too: a filtered edge then blends wire with wire
            alpha &= ~panel | wire; flat |= panel
    picture = (colour * 255).round().astype(np.uint8)
    level = Image.fromarray(flat) if flat is not None else None
    if alpha is None:
        return Image.fromarray(picture), level, plain
    return Image.fromarray(np.dstack([picture, alpha.astype(np.uint8) * 255]), 'RGBA'), level, plain


def relief_size(colour):
    """Pixels across a model's relief map: half its colour picture's, and all of it for a building's 4096 (user,
    2026-11-17: "Yes, full 4K normals"). A building's one picture is spread thin, some 40 texels a metre on the
    Shiawase Barrens power station where a prop has 100 to 300, and Meshy's relief comes at 4096: at half, every
    crack and panel line of its walls was drawn 20 texels a metre."""
    return colour if colour >= 4096 else max(colour // 2, 256)


def textures(name, maps, folder, crunch, *, colour=1024, illumination=None, base=None, flat=None, plain=None):
    """`maps` holds base_color, normal, metallic and roughness image paths. Colour at `colour` pixels, the rest at half; the relief of a 4096 picture at 4096 too (`relief_size`).
    `base` is the colour picture retouched (`retouch`); with an alpha channel it is stored with one. `flat` marks where
    the relief map is levelled, `plain` the parts whose roughness and metal are smoothed as the colour was (`_levelled`)."""
    from PIL import Image
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); half = max(colour // 2, 256)
    shown = base if base is not None else Image.open(maps['base_color']).convert('RGB')
    base = shown.convert('RGB'); relief = Image.open(maps['normal']).convert('RGB')
    if flat is not None:
        relief.paste((128, 128, 255), mask=flat.resize(relief.size, Image.NEAREST))
    read = lambda key: np.asarray(Image.open(maps[key]).convert('L').resize(base.size), float) / 255
    grey = read if plain is None else lambda key: _levelled(read(key), plain)
    shine = np.clip(specular(np.asarray(base, float) / 255, grey('metallic')), 0, 1)
    channel = lambda values: Image.fromarray(np.repeat((values * 255).round().astype(np.uint8)[..., None], 4, axis=2), 'RGBA')
    # The maps are compressed side by side, four at a time: one after another they were 59 of the 146 seconds of the
    # Shiawase Barrens power station's first build (2026-11-17).
    from concurrent.futures import ThreadPoolExecutor
    wanted = [(shown, folder / f'{name}.dds', '-DXT5' if shown.mode == 'RGBA' else '-DXT1', colour, False), (relief, folder / f'{name}_n.dds', '-DXN', relief_size(colour), True),
              (channel(shine), folder / f'{name}_s.dds', '-DXT5A', half, True), (channel(grey('roughness')), folder / f'{name}_r.dds', '-DXT5A', half, True)]
    if illumination is not None:  # a path or an image; mostly black, so half size like the other maps
        lit = illumination if isinstance(illumination, Image.Image) else Image.open(illumination)
        wanted.append((lit.convert('RGB'), folder / f'{name}_i.dds', '-DXT1', half, False))
    with ThreadPoolExecutor(max_workers=4) as pool:
        written = list(pool.map(lambda one: _compress(one[0], one[1], one[2], one[3], crunch, data=one[4]), wanted))
    return written


def load_models(path):
    """The game models of a set: {name: {source, height, colour, signTilt, lift, turn, tone, paint, smooth, mesh,
    fence, close, clear, lit, halo, tiles, measuredAt}}. `lift` hangs the model that many metres above the ground it is placed on (a camera on a wall). `turn`
    turns it that many degrees counter-clockwise seen from above, where its front came back facing a side; boxes are
    on the model as turned. `tone`, `paint`, `smooth` and `mesh` retouch its colour picture (`retouch`); `fence` hangs
    chain-link sheets between its fence posts, with a picture of their own (`sheets`); `close` closes a hole in it
    with a face between three of its own vertices (`closed`); `fill` ([{at}]) closes the hole whose rim passes nearest
    each point with faces between its own vertices (`filled`); `move` ([{box, by}]) carries what is wholly in a box
    elsewhere, before anything is cleared (`moved`); `built` makes straight bars and stair flights on to it in
    colours of its own picture (`with_built`); `clear` takes away (boxes, or rods along a slant) what stands in its boxes (`cleared`); `inside` (true)
    gives every face a back, for a box with openings drawn from outside only, or ([{box}]) the faces in its boxes only (`backed`); `wheels` ({spans: [[start, end]
    along x], top, back}, metres on the finished model) draws a railway car's trucks in to standard gauge, `back` being
    where the backs of its wheels stand either side of its middle as generated (`gauged`); a car lifted by the track's
    height (`track.HEIGHT`) stands on the rails. `source` is the generated
    model's folder under the set's output root (never a machine path); `lit` boxes are in metres on the finished model;
    `tiles` makes the model a tile group too: its ground texture, its group name and palette label, the terrain its
    corners stand on in each tileset ({tileset: terrain}), and optionally `fade`, the height above which the game may
    hide it, and `door` ({at: [x, y, z], facing, type, leaf}: the middle of the foot of a door on the finished model, the
    way it looks out in degrees from east towards north (90 is north), its row of doortypes.2da, which is the invisible
    transition door's, and `leaf`, the height in metres of the door leaf as measured on the finished model, which must
    be a door a character fits; `tile.doorstep` draws the hook out onto open ground and turns it). A tile group takes no `lift`.
    A group may be made of several models (user, 2026-11-12: the concept's whole scene is the group, "that doesn't
    mean we have to generate it as one single mesh"): `parts` places other models of the set in it, each
    {model, at: [x, y, z], turn} in metres on this one and turned a quarter at a time, with a texture of its own (`part_textures`).
    `measuredAt` is how the model stood when its boxes, fences, door and fade height were measured: its height, or
    {height, lift, turn, signTilt, length, level} with each of the five the model states. `length` draws the model out (or in)
    along the longer side of its footprint to that many metres, its height and width kept (`stretched`). A model that states any measurement states
    it, and it must be how the model stands still. `placeable` gives it a row in the placeables table: its label
    and the row of placeableobjsnds.2da it sounds like, and optionally the palette `category` its blueprint is offered
    under and whether the blueprint is `static` (by default a model with lit parts is not, so a script can reach it),
    and a `light` {colour, at} that lights what stands round it, as a lamp post does (`placeables.light_values`).
    `underfoot` (true) lays the model on the ground as railway track is laid (`track`): a group it is placed in is walked
    flat across it, and it may run off the group's edges (`tile.group`). It is a part of groups, never a group itself;
    as a placeable it has no block to walk into and stands no higher than the knee (`placeable`). `walkUnder` (true)
    gives a placeable on legs a block for each part of it that stands under head height in place of one on its whole
    footprint, so it is walked under between them (`standing`; a gantry crane). `level` lays a floor
    marking that came back a wedge flat, that many metres thick (`levelled`), on a model that is neither lifted nor a
    group. `fire` is the fires the game draws on a placeable, [{part, at: [x, y, z], width}] on the finished model
    (`fire_lines`); a model with a fire is no part of a group, which draws none."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and set(data) == {'models'} and isinstance(data['models'], dict) and data['models'], 'A game set has exactly models')
    for name, model in data['models'].items():
        require(name == name.lower() and name.isidentifier() and len(name) <= NAME_LENGTH, f'Model names are lowercase, at most {NAME_LENGTH} characters: {name}')
        if isinstance(model, dict) and 'perimeter' in model:  # a fence stated in a few lines, built as the parts it is made of
            made, hung = perimeter(model['perimeter']); model['frame'] = [*model.get('frame', []), *made]; model['fence'] = [*model.get('fence', []), *hung]
        require(isinstance(model, dict) and {'source', 'height'} <= set(model) <= {'perimeter', 'source', 'height', 'length', 'colour', 'signTilt', 'lift', 'turn', 'tone', 'paint', 'copy', 'smooth', 'mesh', 'fence', 'frame', 'close', 'clear', 'fill', 'built', 'move', 'inside', 'wheels', 'glass', 'embers', 'lit', 'halo', 'tiles', 'placeable', 'measuredAt', 'underfoot', 'level', 'fire', 'walkUnder'},
                'Model needs source and height: ' + name)
        number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        box = lambda part: np.asarray(part.get('box', 0), float).shape == (2, 3)
        require(number(model.get('turn', 0)) and -180 <= model.get('turn', 0) <= 180, 'A model is turned by -180 to 180 degrees: ' + name)
        require('length' not in model or (number(model['length']) and 0 < model['length'] <= 100), 'A length is 0 to 100 metres along the model: ' + name)
        require('level' not in model or (number(model['level']) and 0 < model['level'] <= LEVEL_MOST and not model.get('lift') and not model.get('tiles')),
                f'level is the thickness a floor marking is laid flat at, over 0 and at most {LEVEL_MOST} metres, on a model that is neither lifted nor a tile group: ' + name)
        require('fire' not in model or (isinstance(model['fire'], list) and model['fire'] and model.get('placeable') and not model.get('tiles')),
                'fire is a list of the fires the game draws on a placeable, [{at, width}]; a tile group draws none: ' + name)
        for part in model.get('fire', []):
            fire_values(part)
        tones = model.get('tone', 1); tones = tones if isinstance(tones, list) and len(tones) == 3 else [tones]
        require(all(number(tone) and 0.2 <= tone <= 2 for tone in tones), 'A tone is 0.2 to 2 times the colour, one number or one each for red, green and blue: ' + name)
        shade = lambda value: isinstance(value, list) and len(value) == 3 and all(type(part) is int and 0 <= part <= 255 for part in value)
        for part in model.get('paint', []):
            require(isinstance(part, dict) and {'box', 'colour'} <= set(part) <= {'part', 'box', 'colour'} and box(part) and shade(part['colour']),
                    'A painted part needs a box and a colour of three 0-255 values: ' + name)
        for part in model.get('copy', []):
            require(isinstance(part, dict) and {'box', 'from'} <= set(part) <= {'part', 'box', 'from', 'mirror', 'rise'} and box(part) and box({'box': part['from']})
                    and type(part.get('mirror', False)) is bool and number(part.get('rise', 0.0)),
                    'A copied-over part needs its box and the box of the wall it is copied from (mirror: true or false; rise: metres): ' + name)
        for part in model.get('mesh', []):
            require(isinstance(part, dict) and {'box', 'pitch', 'wire'} <= set(part) <= {'part', 'box', 'pitch', 'wire', 'colour'} and box(part)
                    and number(part['pitch']) and number(part['wire']) and 0 < part['wire'] < part['pitch'] <= 1 and shade(part.get('colour', [0, 0, 0])),
                    'A wire mesh needs a box, a pitch of at most a metre and a thinner wire: ' + name)
        for part in model.get('smooth', []):
            require(isinstance(part, dict) and {'box', 'radius'} <= set(part) <= {'part', 'box', 'radius', 'colour', 'tint', 'slats'} and box(part) and number(part['radius'])
                    and 0.01 <= part['radius'] <= 1 and shade(part.get('colour', [0, 0, 0])), 'A smoothed part needs a box and a radius of 0.01 to 1 metres: ' + name)
            require('slats' not in part or (number(part['slats']) and 0.02 <= part['slats'] <= 0.5 and 'tint' not in part),
                    "A roller door's slats are 0.02 to 0.5 metres apart, drawn on a smoothed surface, not on a marking taken off: " + name)
            require('tint' not in part or (number(part['tint']) and 1 <= part['tint'] <= 255 and 'colour' not in part),
                    'A marking is taken off by its tint, 1 to 255 levels from the surface\'s, and the surface keeps its own colour: ' + name)
        for part in model.get('close', []):
            require(isinstance(part, dict) and {'corners'} <= set(part) <= {'part', 'corners'} and isinstance(part['corners'], list) and len(part['corners']) == 3
                    and all(isinstance(corner, list) and len(corner) == 3 and all(number(value) for value in corner) for corner in part['corners']),
                    'A closing face needs three corners, each a point in metres on the finished model: ' + name)
        point = lambda value: isinstance(value, list) and len(value) == 3 and all(number(one) for one in value)
        for part in model.get('clear', []):
            require(isinstance(part, dict) and (({'box'} <= set(part) <= {'part', 'box'} and box(part))
                                                or ({'from', 'to', 'radius'} <= set(part) <= {'part', 'from', 'to', 'radius'} and point(part['from']) and point(part['to'])
                                                    and number(part['radius']) and part['radius'] > 0 and part['from'] != part['to'])),
                    'A cleared part is a box, or a rod {from, to, radius}: ' + name)
        for part in model.get('move', []):
            require(isinstance(part, dict) and {'box', 'by'} <= set(part) <= {'part', 'box', 'by'} and box(part) and point(part['by']),
                    'A moved part is a box and how far it is moved, [x, y, z] metres: ' + name)
        for part in model.get('built', []):
            kinds = {'bar', 'stairs', 'railing', 'coil'} & set(part) if isinstance(part, dict) else set()
            require(len(kinds) == 1 and point(part.get('picture')), 'A built part is one bar, railing, stair flight or coil, coloured from a point of the model\'s picture: ' + name)
            if 'railing' in part:
                require(set(part) <= {'part', 'railing', 'height', 'picture'} and isinstance(part['railing'], list) and len(part['railing']) >= 2
                        and all(point(one) for one in part['railing']) and (number(part.get('height', 1.0)) and 0.3 <= part.get('height', 1.0) <= 1.5),
                        'A built railing is a path of two or more points on the surface walked and a height of 0.3 to 1.5 metres: ' + name)
            elif 'coil' in part:
                require(set(part) <= {'part', 'coil', 'radius', 'pitch', 'picture'} and isinstance(part['coil'], list) and len(part['coil']) == 2 and all(point(end) for end in part['coil'])
                        and part['coil'][0] != part['coil'][1] and number(part.get('radius')) and 0.1 <= part['radius'] <= 0.6 and number(part.get('pitch')) and 0.1 <= part['pitch'] <= 1.0,
                        'A built coil of barbed wire is the two ends of its axis, a radius of 0.1 to 0.6 metres and a pitch of 0.1 to 1 metre a turn: ' + name)
            elif 'bar' in part:
                require(set(part) <= {'part', 'bar', 'size', 'picture'} and isinstance(part['bar'], list) and len(part['bar']) == 2 and all(point(end) for end in part['bar'])
                        and part['bar'][0] != part['bar'][1] and isinstance(part.get('size'), list) and len(part['size']) == 2 and all(number(one) and one > 0 for one in part['size']),
                        'A built bar is two ends and a size [width, depth] in metres: ' + name)
            else:
                flight = part['stairs']
                require(set(part) <= {'part', 'stairs', 'picture', 'rails'} and isinstance(flight, dict) and set(flight) <= {'foot', 'top', 'width', 'sides'}
                        and {'foot', 'top', 'width'} <= set(flight) and point(flight['foot']) and point(flight['top']) and number(flight['width']) and flight['width'] > 0
                        and flight['top'][2] - flight['foot'][2] > 0.3
                        and flight['top'][2] - flight['foot'][2] <= STAIR_STEEPEST * float(np.hypot(flight['top'][0] - flight['foot'][0], flight['top'][1] - flight['foot'][1]))
                        and set(flight.get('sides', ['left', 'right'])) <= {'left', 'right'} and point(part.get('rails', part['picture'])),
                        'A built stair flight is {foot, top, width, sides} (its foot and top the middles of its lowest and highest nosings, the top higher, at most STAIR_STEEPEST rise to its run), coloured from a point and its rails from another: ' + name)
        for part in model.get('fill', []):
            require(isinstance(part, dict) and {'at'} <= set(part) <= {'part', 'at', 'picture'} and all(isinstance(part[key], list) and len(part[key]) == 3
                    and all(number(value) for value in part[key]) for key in ('at', 'picture') if key in part),
                    'A filled hole is a point on its rim, and it may be a point whose colour it takes, in metres on the finished model: ' + name)
        for part in model.get('glass', []):
            require(isinstance(part, dict) and {'corners'} <= set(part) <= {'part', 'corners', 'colour', 'strength'} and isinstance(part['corners'], list)
                    and 3 <= len(part['corners']) <= GLASS_MOST and all(isinstance(corner, list) and len(corner) == 3 and all(number(value) for value in corner) for corner in part['corners'])
                    and shade(part.get('colour', list(GLASS_COLOUR))) and number(part.get('strength', GLASS_STRENGTH)) and 0 < part.get('strength', GLASS_STRENGTH) <= 1,
                    f'A pane of glass is {{corners: 3 to {GLASS_MOST} points round it in metres on the finished model, colour: [r, g, b] of 0 to 255, strength: over 0, at most 1}}: ' + name)
        require(not model.get('glass') or (model.get('placeable') and not model.get('tiles')), 'Glass is made for a placeable only, not for a tile group: ' + name)
        for part in model.get('embers', []):
            require(isinstance(part, dict) and {'at', 'radius'} <= set(part) <= {'part', 'at', 'radius'} and point(part['at']) and number(part['radius']) and EMBER_RADIUS[0] <= part['radius'] <= EMBER_RADIUS[1],
                    f'A bed of embers is {{at: the middle of its rim, radius: {EMBER_RADIUS[0]} to {EMBER_RADIUS[1]}}}, in metres on the finished model '
                    '(its lumps grow with it: a wider one would show coals the size of paving stones): ' + name)
        require(not model.get('embers') or (model.get('placeable') and not model.get('tiles')), 'A bed of embers is made for a placeable only, not for a tile group: ' + name)
        # The burn barrel had both at first, and its flame burned on when one script swapped its lights-out material in
        # and played the animation that puts the fire out; each call alone did its work (client checks, 2026-11-16).
        require(not (model.get('fire') and model.get('lit')), 'A model with a fire has no lit parts: a script that puts both out leaves the flame burning. '
                'Its embers are a bed of their own (embers), and a lamp on it is another prop: ' + name)
        # The panes share a picture GLASS_PICTURE pixels wide, compressed in blocks of four: narrower patches run into each other.
        require(len(model.get('glass', [])) <= GLASS_PICTURE // 4, f'A model has at most {GLASS_PICTURE // 4} panes of glass: ' + name)
        for part in model.get('frame', []):
            kinds = {'tube', 'block', 'coil'} & set(part) if isinstance(part, dict) else set(); ends = part[next(iter(kinds))] if len(kinds) == 1 else None
            require(len(kinds) == 1 and point(part.get('picture')) and isinstance(ends, list) and len(ends) == 2 and all(point(end) for end in ends) and ends[0] != ends[1],
                    "A part of a fence's frame is one tube, block or coil between two points, toned from a point of the model's picture: " + name)
            if 'tube' in part:
                require(set(part) <= {'part', 'tube', 'radius', 'cap', 'picture'} and number(part.get('radius')) and 0.01 <= part['radius'] <= 0.3 and isinstance(part.get('cap', False), bool),
                        "A frame's tube has a radius of 0.01 to 0.3 metres, and a cap or none: " + name)
            elif 'block' in part:
                require(set(part) <= {'part', 'block', 'size', 'picture'} and number(part.get('size')) and 0.1 <= part['size'] <= 1.0 and ends[0][:2] == ends[1][:2] and ends[1][2] > ends[0][2],
                        "A frame's block stands upright from its foot to its top, 0.1 to 1 metre across: " + name)
            else:
                require(set(part) <= {'part', 'coil', 'radius', 'pitch', 'picture'} and number(part.get('radius')) and 0.1 <= part['radius'] <= 0.6 and number(part.get('pitch')) and 0.1 <= part['pitch'] <= 1.0,
                        "A frame's coil of barbed wire has a radius of 0.1 to 0.6 metres and a pitch of 0.1 to 1 metre a turn: " + name)
        require(not model.get('frame') or model.get('fence'), "A fence's frame stands with its fence, whose picture it shows: " + name)
        pair = lambda value: np.asarray(value, float).shape == (2,)
        for part in model.get('fence', []):
            require(isinstance(part, dict) and {'from', 'to', 'z', 'pitch', 'wire'} <= set(part) <= {'part', 'from', 'to', 'z', 'pitch', 'wire', 'colour'}
                    and pair(part['from']) and pair(part['to']) and pair(part['z']) and part['z'][0] < part['z'][1] and list(part['from']) != list(part['to'])
                    and number(part['pitch']) and number(part['wire']) and 0 < part['wire'] < part['pitch'] <= 1 and shade(part.get('colour', [0, 0, 0])),
                    'A fence runs from one point to another between two heights, with a pitch of at most a metre and a thinner wire: ' + name)
        require(len({(part['pitch'], part['wire'], tuple(part.get('colour', WIRE))) for part in model.get('fence', [])}) <= 1, 'The fences of a model share one wire mesh: ' + name)
        require(isinstance(model.get('lift', 0), (int, float)) and 0 <= model.get('lift', 0) <= 20, 'A model is lifted by 0 to 20 metres: ' + name)
        source = Path(model['source'])
        require(not source.is_absolute() and '..' not in source.parts and ':' not in model['source'], 'Model source is a folder under the output root: ' + name)
        require(model['height'] > 0 and model.get('colour', 1024) in (512, 1024, 2048, 4096), 'Model height or colour size is out of range: ' + name)
        for region in model.get('lit', []):
            require(isinstance(region, dict) and 'box' in region and set(region) <= {'part', 'box', 'gain', 'saturation', 'value'}
                    and np.asarray(region['box'], float).shape == (2, 3), 'A lit part needs a box of two corners: ' + name)
        # A box is on the finished model, which stands from its lift to its lift and its height. The Ares Depot's wall
        # sign, lifted 2.4 metres, had its lit boxes where it stood before the lift and shipped dark (review, 2026-11-12).
        foot, head = model.get('lift', 0), model.get('lift', 0) + model['height']
        boxed = [*(part for key in ('lit', 'paint', 'copy', 'smooth', 'mesh', 'clear', 'move') for part in model.get(key, [])),
                 *(part for part in (model['inside'] if isinstance(model.get('inside'), list) else []) if isinstance(part, dict) and 'box' in part)]
        spans = [np.asarray(part['box'] if 'box' in part else [part['from'], part['to']], float)[:, 2] for part in boxed]
        spans = [(min(low, high), max(low, high)) for low, high in spans]
        require(all(high > foot and low < head for low, high in spans + [part['z'] for part in model.get('fence', [])]),
                f'A box or fence lies wholly above or below the model, which stands from {foot} to {head} metres up: {name}')
        require(set(model.get('halo', {})) <= {'reach', 'strength', 'core', 'least'} and ('halo' not in model or model.get('lit')),
                'A halo takes reach, strength, core and least, and needs lit parts: ' + name)
        placed = model.get('placeable')
        require(placed is None or ({'label', 'sound'} <= set(placed) <= {'label', 'sound', 'category', 'static', 'light'} and isinstance(placed['label'], str) and placed['label']
                                   and type(placed['sound']) is int and type(placed.get('category', 0)) is int and type(placed.get('static', True)) is bool),
                'A placeable needs a label and a sound row: ' + name)
        # A glow map lights only the model's own faces. The Chop Shop clinic's surgical lamp was converted with glowing
        # lenses and no light (user, 2026-11-14: "the lamp needs a light", "make sure you are checking for when props
        # need lights from now on", "it should only be for things that should be bright").
        # A fire and a bed of embers are asked as lit parts are: the barrels' lit parts became a bed of embers, and with
        # them went the question (review, 2026-11-16).
        require(not (placed and (model.get('lit') or model.get('fire') or model.get('embers'))) or 'light' in placed,
                'A lit prop, and one with a fire or a bed of embers, says whether it lights what stands round it: give its placeable a light, {colour, at} for what '
                'should be bright (a lamp, a floodlight, a fire), null for what only glows (a screen, a sign, an indicator, trim, embers): ' + name)
        if placed and 'light' in placed:
            placeables.light_values(placed['light'])
        tiles = model.get('tiles')
        wheels = model.get('wheels')
        require(wheels is None or (isinstance(wheels, dict) and set(wheels) == {'spans', 'top', 'back'} and number(wheels['top']) and wheels['top'] > 0
                                   and number(wheels['back']) and 0.5 <= wheels['back'] <= 1.5 and isinstance(wheels['spans'], list) and wheels['spans']
                                   and all(isinstance(span, list) and len(span) == 2 and all(number(v) for v in span) and span[0] < span[1] for span in wheels['spans'])),
                'wheels are {spans: [[start, end], ...] along x, top, back: 0.5 to 1.5 metres}: ' + name)
        inside = model.get('inside', True)
        require(inside is True or (isinstance(inside, list) and inside and all(isinstance(part, dict) and {'box'} <= set(part) <= {'part', 'box'} and box(part) for part in inside)),
                'inside is true, for a box whose openings show what stands behind it, or a list of boxes whose faces get backs: ' + name)
        require(model.get('underfoot', True) is True and not ('underfoot' in model and tiles),
                'underfoot is true, for a model laid on the ground of the groups it is placed in, and that is no group itself: ' + name)
        require(model.get('walkUnder', True) is True and not ('walkUnder' in model and (tiles or not placed or model.get('underfoot'))),
                'walkUnder is true, for a placeable on legs that is walked under between them, and that is neither a group nor laid underfoot: ' + name)
        require(tiles is None or ({'ground', 'group', 'label', 'sets'} <= set(tiles) <= {'ground', 'group', 'label', 'sets', 'fade', 'door', 'parts', 'nodes'} and isinstance(tiles['sets'], dict) and tiles['sets']
                                  and all(isinstance(value, str) and value for value in (tiles['ground'], tiles['group'], tiles['label'], *tiles['sets'], *tiles['sets'].values()))),
                'Tiles need a ground texture, a group name, a palette label and the terrain in each tileset: ' + name)
        require(tiles is None or len(name) <= TILE_NAME_LENGTH, f'A tile group model is named in at most {TILE_NAME_LENGTH} characters: {name}')
        # A tile group stands on the ground: `tiles` builds it there, and a lift would only move its boxes off it.
        require(tiles is None or not model.get('lift'), 'A tile group stands on the ground and takes no lift: ' + name)
        door = (tiles or {}).get('door')
        require(not (isinstance(door, dict) and 'measuredAt' in door), 'measuredAt is stated on the model, beside its height, and covers its door: take it off the door of ' + name)
        require(door is None or (isinstance(door, dict) and {'at'} <= set(door) <= {'at', 'facing', 'type', 'leaf'} and np.asarray(door['at'], float).shape == (3,)),
                'A door needs the place it stands at: ' + name)
        require(door is None or number(door.get('facing', 0.0)), 'A door faces a number of degrees: ' + name)
        # The building's own modelled door is what is seen; the hook is the door that has no model of its own.
        require(door is None or door.get('type') == DOOR_TYPE, f'The door hook of a building is the invisible transition door, type {DOOR_TYPE}: ' + name)
        # A building is sized by its door, never by the tiles it would fill: the Ares Depot was first scaled to fit 2 by 2
        # tiles and its door leaf came out 1.6 metres, lower than the character standing at it (client, 2026-11-11).
        require(door is None or (number(door.get('leaf')) and DOOR_LEAF[0] <= door['leaf'] <= DOOR_LEAF[1]),
                f'A door states its leaf, measured on the finished model, {DOOR_LEAF[0]} to {DOOR_LEAF[1]} metres tall; scale the building to its door first: ' + name)
        fade = (tiles or {}).get('fade')
        require(fade is None or (number(fade) and 0 < fade < model['height']), 'The fade height is a number within the model: ' + name)
        nodes = (tiles or {}).get('nodes', {})
        require(isinstance(nodes, dict) and all(isinstance(key, str) and len(key) == 3 and key[0] == 't' and key[1:].isdigit() and isinstance(value, dict)
                                                and set(value) == {'node', 'turn'} and isinstance(value['node'], str) and len(value['node']) == 1
                                                and value['turn'] in (0, 90, 180, 270) for key, value in nodes.items()),
                'A stated path node is {"t<row><column>": {"node": letter, "turn": 0, 90, 180 or 270}}: ' + name)
        parts = (tiles or {}).get('parts', [])
        # A halo card and a fence's sheets stand along x or along y, and are cut at the tile lines along that (`tile.share_cards`):
        # a part turned by other than a quarter would leave them across the cut.
        require(isinstance(parts, list) and all(isinstance(part, dict) and {'model', 'at'} <= set(part) <= {'model', 'at', 'turn'} and isinstance(part['model'], str)
                                                and isinstance(part['at'], list) and len(part['at']) == 3 and all(number(value) for value in part['at'])
                                                and part.get('turn', 0) in (0, 90, 180, 270) for part in parts),
                'A part of a group is {model, at: [x, y, z], turn}, turned 0, 90, 180 or 270 degrees: ' + name)
        require(len(part_textures(name, parts)) <= MAX_PARTS, f'A group has at most {MAX_PARTS} models placed in it: ' + name)
        # Every box, fence, door and fade height is a measurement, and a measurement is of the model as it stood: at
        # one height, and lifted, turned and tilted as it then was. A typed door leaf would go on passing after its
        # building was made taller or lower, and a lit box would go on holding some of the model and lighting the wrong
        # part of it (found in review, 2026-11-12); so would the boxes of a sign hung at another lift or turned since
        # they were read. So a model that states any measurement says how it stood when they were made, and standing
        # otherwise they are made again.
        measured = any(model.get(key) for key in MEASURED) or bool(model.get('fire')) or isinstance(model.get('inside'), list) or door is not None or fade is not None or bool(parts)
        stands = {'height': model['height'], **{key: model[key] for key in PLACING if key in model}}
        told = lambda at: ', '.join(f'{key} {value}' for key, value in at.items())
        require('measuredAt' in model if measured else True, 'A model that states boxes, fences, a door or a fade height says how it stood when they were measured '
                f'(measuredAt: {json.dumps(stands if len(stands) > 1 else model["height"])}, if they were measured on the model as it is now): ' + name)
        stated = model.get('measuredAt'); stated = {'height': stated} if number(stated) else stated
        require('measuredAt' not in model or (isinstance(stated, dict) and all(number(value) for value in stated.values()) and stated == stands),
                f'The boxes, fences, door and fade height of a model were measured with the model at {told(stated) if isinstance(stated, dict) else json.dumps(stated)} '
                f'and it is now at {told(stands)}: measure them again on the model as it is, and say so in measuredAt: ' + name)
    for name, model in data['models'].items():
        for part in (model.get('tiles') or {}).get('parts', []):
            other = data['models'].get(part['model'])
            require(other is not None and part['model'] != name and not other.get('tiles'),
                    f'A part of {name} is another model of the set, and no tile group itself: {part["model"]}')
            require(not other.get('glass'), f'A part of {name} has glass, which a tile group does not draw: {part["model"]}')
            require(not other.get('embers'), f'A part of {name} has a bed of embers, which a tile group does not draw: {part["model"]}')
            # `shape` knows nothing of a fire: placed in a group the barrel would stand there cold, and nothing would say so.
            require(not other.get('fire'), f'A part of {name} has a fire, which a tile group does not draw: place it in the area as a placeable: {part["model"]}')
    # Every file a model ships is named from its own name: its pictures with a suffix (`MAP_SUFFIXES`), a group's tiles
    # with _t and the tile, the models placed in it with p and a number. A model named like one of those would write
    # over it in the pack: the rail yard's first copy of its office for the depot's group was ek_rf_admin_s, the name
    # of the office's own shine map (2026-11-13).
    names = set(data['models'])
    for name, model in data['models'].items():
        taken = {name + suffix for suffix in MAP_SUFFIXES}
        if model.get('tiles'):
            taken |= set(part_textures(name, model['tiles'].get('parts', [])).values())
        clash = sorted(names & taken) + sorted(other for other in names if model.get('tiles') and re.fullmatch(re.escape(name) + r'_t\d+', other))
        require(not clash, f'A model is named like a file of {name}, which it would write over: ' + ', '.join(clash))
    return data['models']


MAX_PARTS = 9  # models placed in one group: `<group>p1` to `p9`, which the repository check looks for


def part_textures(name, parts):
    """{model: texture} of the models placed in the group `name`: `name`p1, p2 and so on in the order they first come,
    one texture to a model however often it is placed. A model placed in a group is drawn there with its own picture
    under a name of the group's, so the group's pack holds all it shows and no file is in two packs."""
    order = list(dict.fromkeys(part['model'] for part in parts))
    return {model: f'{name}p{index}' for index, model in enumerate(order, 1)}


def building_triangles(models, name, triangles):
    """Triangles of the building a tile group shows, held to the building budget: those of the group's own model and of
    every model placed in it that is no placeable, as often as it is placed. `triangles` is each model's count. A
    building made in pieces is several models (the Saeder-Krupp yard: five, 2026-11-12), and a piece generated again
    from one view stands beside the one it mends, so the budget is counted on what the group places. A placeable placed
    in the group (a fence, a crate) is a prop, held to its own target."""
    parts = models[name]['tiles'].get('parts', [])
    return triangles[name] + sum(triangles[part['model']] for part in parts if not models[part['model']].get('placeable'))


def place(made, at, turn=0):
    """A finished model (`shape`) turned `turn` degrees about the vertical, counter-clockwise seen from above, and moved
    to `at`: its vertices, normals, fence sheets and halo cards; its pictures are its own as they were."""
    import math
    from . import glow
    cos, sin = (round(math.cos(math.radians(turn))), round(math.sin(math.radians(turn)))) if turn % 90 == 0 else (math.cos(math.radians(turn)), math.sin(math.radians(turn)))
    spin = np.array([[cos, -sin, 0.0], [sin, cos, 0.0], [0.0, 0.0, 1.0]]); shift = np.asarray(at, float)
    moved = lambda points: np.asarray(points, float) @ spin.T + shift
    # its map of places (`placed`) was measured where it stood before: it is not carried along
    placed = {**made, 'placed': None, 'vertices': moved(made['vertices']), 'normals': np.asarray(made['normals'], float) @ spin.T}
    if made.get('wire'):
        placed['wire'] = {**made['wire'], 'vertices': moved(made['wire']['vertices']), 'normals': np.asarray(made['wire']['normals'], float) @ spin.T}
    if made.get('card'):
        card = made['card']
        placed['card'] = glow.Halo(card.image, [[(tuple(moved(point).tolist()), uv) for point, uv in corners] for corners in card.cards], card.light)
    return placed


HALO_OUT = 'ek_off'  # one for every model: a black sheet added to the picture adds nothing


def lights_out(name, folder, crunch, halo):
    """Write what a script swaps in to put a lit model's lights out, and return the texture files.

    `ReplaceObjectTexture(object, old, new)` works on these models only when `old` is a mesh's `bitmap` and `new` is
    itself a material: a name with its own material file (client checks, 2026-11-10: a glow map's own name, or a
    replacement that was only a texture, changed nothing; a replacement with a material file took effect at once and
    an empty `new` brought the lights back). So the model gets `name`_o, its material without the glow map, and its
    halo gets `ek_off`, a black sheet. Each needs a texture of its own name to be found; a 16-pixel black one serves.
    The object must not be static: a static placeable is scenery no script can reach.

    A tile is no object, and static scenery is out of that call's reach. `SetTextureOverride(old, new, player)` reaches
    both, for one player or all, but it swaps textures by name and knows no material (client checks, 2026-11-11: the
    model's own name overridden with `name`_o drew the building in that 16-pixel black; the glow map `name`_i
    overridden with it put the lights out and left the rest as it was). So the same files serve both calls
    (`lights_script`, `blackout_script`); docs/envkit/lights.md is the account of them for those who write scripts."""
    from PIL import Image
    folder = Path(folder); dark = Image.new('RGB', (16, 16)); written = [_compress(dark, folder / f'{name}_o.dds', '-DXT1', 16, crunch, data=False)]
    (folder / f'{name}_o.mtr').write_text(material_text(name), encoding='cp1252', newline='\n')
    if halo:
        written.append(_compress(dark, folder / f'{HALO_OUT}.dds', '-DXT1', 16, crunch, data=False))
        (folder / f'{HALO_OUT}.mtr').write_text('\n'.join(['renderhint NormalAndSpecMapped', '', f'texture0 {HALO_OUT}'] + [f'texture{slot} null' for slot in range(1, 6)]) + '\n',
                                                encoding='cp1252', newline='\n')
        (folder / f'{HALO_OUT}.txi').write_text('blending additive\n', encoding='ascii', newline='\n')
    return written


def lights(name, folder):
    """What a script swaps to put a built model's lights out, read off the files in `folder`: {lit, out, glow}, the
    material, its lights-out twin and the glow map, and for a model with a halo {halo, dark} too. None for a model
    with no lit parts."""
    folder = Path(folder)
    if not (folder / f'{name}_o.mtr').is_file():
        return None
    found = {'lit': name, 'out': f'{name}_o', 'glow': f'{name}_i'}
    return {**found, 'halo': f'{name}_h', 'dark': HALO_OUT} if (folder / f'{name}_h.mtr').is_file() else found


def scripted(model):
    """Whether a script reaches a model of a game set as it stands: one with lit parts, put out by a swap of its
    pictures, or with a fire, put out by its animation. Such a prop is placed not static, and its blueprint is made so."""
    return bool(model.get('lit') or model.get('fire'))


def lights_script(name, target, on, halo=True, light=False, fire=False, glow=True):
    """One line of NWScript that puts the lights of the object `target` (an expression) out, or back on. `glow` False:
    the model has no lit parts of its own (a fire barrel: only its fire and its light go out). `light`: its
    row names a light colour (`placeables.light_values`), which lights what stands round it and is put out with it.
    `fire`: the model has fires the game draws (`fire_lines`), put out and lit again by its animations (`fire_anim_lines`)."""
    swaps = ([(name, f'{name}_o')] if glow else []) + ([(f'{name}_h', HALO_OUT)] if halo and glow else [])
    switch = f'SetPlaceableIllumination({target},{"TRUE" if on else "FALSE"});RecomputeStaticLighting(GetArea({target}));' if light else ''
    burn = f'AssignCommand({target},PlayAnimation(ANIMATION_PLACEABLE_{"" if on else "DE"}ACTIVATE));' if fire else ''
    return ''.join(f'ReplaceObjectTexture({target},"{old}"' + ('' if on else f',"{new}"') + ');' for old, new in swaps) + switch + burn


def blackout_script(name, player, on, halo=True):
    """One line of NWScript that puts out, or back on, the lights of every `name` the player `player` (an expression;
    OBJECT_INVALID for everyone) sees: tiles and static scenery as well as objects a script can reach."""
    swaps = [(f'{name}_i', f'{name}_o')] + ([(f'{name}_h', HALO_OUT)] if halo else [])
    return ''.join(f'SetTextureOverride("{old}","{"" if on else new}",{player});' for old, new in swaps)


def shape(model, maps, *, height, colour=1024, illumination=None, sign_tilt=None, lit=None, halo=None, lift=0.0, turn=0.0, length=None, level=None, tone=None, paint=None,
          copy=None, smooth=None, mesh=None, fence=None, frame=None, close=None, clear=None, fill=None, inside=False, wheels=None, built=None, move=None, glass=None, embers=None, sight=True):
    """The finished model in game space and what lights it: {vertices, normals, uvs, faces, scale, angles, repaired,
    illumination, card, colour, flat, plain, turn, wire}. `turn` turns it about the vertical before anything is measured on it; `clear`
    takes away what stands in its boxes (`cleared`) and `close` closes holes in it with faces between its own vertices
    (`closed`) and `fill` closes the hole round a point (`filled`), in that order, and `inside` then gives every face a back (`backed`); before them `wheels` draws a car's trucks in to the track (`gauged`), before its pictures are worked on; `tone`,
    `paint`, `smooth` and `mesh` give `colour`, `flat` and `plain`: its colour picture retouched, where its relief is levelled and
    where its other maps are smoothed (`retouch`; all None for a model left as generated). `fence` gives `wire`, the chain-link sheets hung on it and their picture (`sheets`). `sign_tilt`, in degrees, rebuilds a two-sided sign from its front sheet (`two_sided`). `lit`
    names the parts lit from within as boxes on the finished model (`glow.glow`); `illumination` is a ready-made glow
    map instead. `halo` ({reach, strength, core}) adds the cards that spread the lit parts' light (`glow.halo`).
    `glass` gives `glass`, its panes (`glazed`), which are no part of its own faces, and `embers` gives `embers`, its
    beds of embers (`ember_beds`), which are none either. `placed` is the map of its places its lit parts were found by."""
    vertices, normals, uvs, faces = read_glb(model); card = None
    vertices, normals, uvs, scale, angles = fit(vertices, normals, uvs, height, faces=faces)
    if sign_tilt is not None:
        vertices, normals, uvs, faces = two_sided(vertices, normals, uvs, faces, sign_tilt)
        vertices, again = stand(vertices, height); scale *= again
    if turn:
        spin = _turn(float(turn), 0.0, 0.0); vertices, normals = vertices @ spin.T, normals @ spin.T
        vertices, _ = stand(vertices, height)
    if length is not None:  # after the turn, so the side drawn out is the one that runs longest as the model stands
        vertices, normals = stretched(vertices, normals, float(length))
    faces, faces_turned = turn_faces(vertices, faces)
    normals, repaired = repair_normals(vertices, normals, faces); normals, turned = turn_normals(vertices, normals, faces)
    if level is not None:  # a floor marking that came back a wedge, laid flat (`levelled`): after its faces are wound right, before anything is measured on it
        vertices, normals = levelled(vertices, faces, float(level))
    vertices = vertices + [0.0, 0.0, float(lift)]  # hung at its height before its lit parts are found: their boxes are on the finished model
    if wheels:
        vertices, normals = gauged(vertices, normals, wheels)
    if move:
        vertices, normals, uvs, faces = moved(vertices, normals, uvs, faces, move)
    if clear:
        vertices, normals, uvs, faces = cleared(vertices, normals, uvs, faces, clear)
    if close:
        faces = closed(vertices, normals, uvs, faces, close)
    if fill:
        vertices, normals, uvs, faces = filled(vertices, normals, uvs, faces, fill)
    # The largest patch of the finished model seen from behind, from any way it is looked at, of the faces given no
    # back: the game draws nothing there, so it is a hole onto what stands past the model. The Chop Shop clinic's
    # biohazard bin had gaps under its rear rim, its dumpster a slot between its lids and its lamp a length of pole
    # seen through from one side, none of which the front, back and side of the client check showed (2026-11-14).
    # `sight` False leaves it out, for a caller that does not report it: it took 11 seconds on that clinic's building.
    behind = None
    if sight and inside is not True:
        patches = []; seen(vertices, faces, holes=patches, both=_backs(vertices, faces, inside) if inside else None); behind = max(patches)
    if inside:
        vertices, normals, uvs, faces = backed(vertices, normals, uvs, faces, None if inside is True else inside)
    require(not frame or fence, 'A frame stands with a fence, whose picture it shows')
    require(not halo or lit, 'A halo spreads the lit parts: name them')
    require(not lit or illumination is None, 'Give the lit parts or a glow map, not both')
    wire = None
    if fence:  # before the long work on the pictures: a fence that is refused is refused in the first seconds
        _hung(vertices, faces, fence); tones = {}
        if frame:  # its steel and concrete in the tones of the model's picture at the points stated
            from PIL import Image
            with Image.open(maps['base_color']) as picture:
                seen_ = np.asarray(picture.convert('RGB'), float)
            for kind, keys in (('steel', ('tube', 'coil')), ('concrete', ('block',))):
                at = next((part['picture'] for part in frame if any(key in part for key in keys)), None)
                if at is not None:
                    u, v = picture_at(vertices, uvs, faces, at); row, column = int(np.clip(v, 0, 1) * (seen_.shape[0] - 1)), int(np.clip(u, 0, 1) * (seen_.shape[1] - 1))
                    tones[kind] = seen_[max(row - 4, 0):row + 5, max(column - 4, 0):column + 5].reshape(-1, 3).mean(0)
        wire = sheets(fence, frame=frame, colours=tones)
    shown = flat = plain = placed = None; retouched = tone is not None or paint or copy or smooth or mesh
    if lit or retouched:
        from PIL import Image
        from . import glow
    if lit:
        size = max(colour // 2, 256); placed = glow.position_map(vertices, uvs, faces, size, facing=True)
    if retouched:
        with Image.open(maps['base_color']) as picture:
            same = placed is not None and size == min(RETOUCH, picture.width)  # the glow's map of places serves the retouching where their sizes agree
            shown, flat, plain = retouch(picture, vertices, uvs, faces, tone=tone, paint=paint or (), copy=copy or (), smooth=smooth or (), mesh=mesh or (),
                                         placed=placed[:2] if same else None)
    if lit:  # by the picture as it ships: what was painted over or toned down does not shine through by night as it was
        with Image.open(maps['base_color']) as picture:
            base = np.asarray((shown if shown is not None else picture).convert('RGB').resize((size, size)), float) / 255
        where, covered, toward = placed; shine = glow.glow(base, where, covered, lit)
        illumination = Image.fromarray((shine * 255).round().astype(np.uint8))
        card = glow.halo(shine, where, covered, toward=toward, parts=[glow.inside(where, covered, part['box']) for part in lit], **halo) if halo else None
    if built:  # after the pictures: a built member takes one place of the picture, which no retouching or glow should read as its
        vertices, normals, uvs, faces = with_built(vertices, normals, uvs, faces, built)
    panes = glazed(glass) if glass else None
    return {'embers': ember_beds(embers) if embers else None, 'emberBeds': len(embers or []), 'glass': panes, 'vertices': vertices, 'normals': normals, 'uvs': uvs, 'faces': faces, 'scale': scale, 'angles': angles, 'repaired': repaired, 'turned': turned, 'facesTurned': faces_turned,
            'illumination': illumination, 'card': card, 'colour': shown, 'flat': flat, 'plain': plain, 'turn': float(turn), 'wire': wire, 'behind': behind,
            'placed': placed}  # the map of the model's places its lit parts were found by, None where it has none: `shipped_blank_panels` reads by it


def _hung(vertices, faces, fences):
    """Refuse a fence either end of which is at no part of the model. A fence hangs between its posts, and its ends are
    stated on the finished model, turned and lifted; one measured before a turn would pass every check of its heights
    and be built hanging in the air (the wall sign's lit boxes went wrong the same way, 2026-11-12)."""
    surface = scatter(vertices, faces, spacing=FENCE_NEAR / 3)  # places all over the model: a post's flat side may have no corner near
    for one in fences:
        low, high = (float(value) for value in one['z'])
        level = surface[(surface[:, 2] >= low - FENCE_NEAR) & (surface[:, 2] <= high + FENCE_NEAR)][:, :2]
        for end in (one['from'], one['to']):
            away = float(np.linalg.norm(level - np.asarray(end, float), axis=1).min()) if len(level) else float('inf')
            require(away <= FENCE_NEAR, f'A fence hangs between posts of the model, and no part of the model lies within {FENCE_NEAR} metres of its end at {list(end)} '
                    f'between its heights (the nearest is {away:.2f} away); fences are on the finished model, turned and lifted: ' + str(one.get('part', '')))


def skin(name, maps, folder, crunch, made, *, colour=1024):
    """Write the model's material file and maps, its halo's and its lights-out set into `folder`; returns the textures."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); illumination, card = made['illumination'], made['card']
    (folder / f'{name}.mtr').write_text(material_text(name, illumination is not None), encoding='cp1252', newline='\n')
    files = textures(name, maps, folder, crunch, colour=colour, illumination=illumination, base=made.get('colour'), flat=made.get('flat'), plain=made.get('plain'))
    if card:
        files.append(_compress(card.image, folder / f'{name}_h.dds', '-DXT1', 512, crunch, data=False))
        card_material = ['renderhint NormalAndSpecMapped', '', f'texture0 {name}_h', 'texture1 null', 'texture2 null', 'texture3 null',
                         'texture4 null', f'texture5 {name}_h']
        (folder / f'{name}_h.mtr').write_text('\n'.join(card_material) + '\n', encoding='cp1252', newline='\n')
        (folder / f'{name}_h.txi').write_text('blending additive\n', encoding='ascii', newline='\n')
    if made.get('glass'):  # a plain picture, added to what is behind it: it needs no material file either
        files.append(_compress(glass_picture(made['glass']), folder / f'{name}_g.dds', '-DXT1', GLASS_PICTURE, crunch, data=False))
        (folder / f'{name}_g.txi').write_text('blending additive\n', encoding='ascii', newline='\n')
    if made.get('embers') is not None:  # its picture in the glow slot too, as a halo's is: the bed shows it whatever light falls on it
        files.append(_compress(ember_picture(), folder / f'{name}_e.dds', '-DXT1', EMBER_PICTURE, crunch, data=False))
        (folder / f'{name}_e.mtr').write_text('\n'.join(['renderhint NormalAndSpecMapped', '', f'texture0 {name}_e', *(f'texture{slot} null' for slot in range(1, 5)), f'texture5 {name}_e']) + '\n',
                                              encoding='cp1252', newline='\n')
    if made.get('wire'):  # a plain picture, see-through between the wires: it needs no material file; _w is a suffix like the maps'
        files.append(_compress(made['wire']['image'], folder / f'{name}_w.dds', '-DXT5', made['wire']['image'].width, crunch, data=False))
    if illumination is not None:
        files += lights_out(name, folder, crunch, bool(card))
    return files


def measured(name, made, files, sign_tilt=None):
    vertices, faces, card, angles = made['vertices'], made['faces'], made['card'], made['angles']
    return {'name': name, 'triangles': len(faces), 'vertices': len(vertices), 'nodes': len(split(faces)), 'scale': round(float(made['scale']), 5),
            'repairedNormals': made['repaired'], 'turnedNormals': made['turned'], 'turnedFaces': made['facesTurned'], 'signTilt': sign_tilt, 'lit': made['illumination'] is not None, 'haloCards': len(card.cards) if card else 0, 'glassPanes': len(made.get('glass') or []), 'emberBeds': made.get('emberBeds', 0),
            'turnedByDegrees': {'yaw': angles[0], 'pitch': angles[1], 'roll': angles[2]}, 'turn': made.get('turn', 0.0), 'seeThrough': made.get('colour') is not None and made['colour'].mode == 'RGBA', 'fenceFaces': len(made['wire']['faces']) if made.get('wire') else 0,
            # the largest patch seen from behind, and from which way: a hole, or glass wound inward (`inside` gives backs); None where every face has a back
            'seenFromBehind': {'cm2': round(made['behind'][0] * 1e4), 'from': made['behind'][1]} if made.get('behind') else None,
            'size': [round(float(v), 3) for v in vertices.max(0) - vertices.min(0)], 'textures': {f.name: f.stat().st_size for f in files}}


def placeable(name, model, maps, folder, crunch, *, height, colour=1024, sign_tilt=None, light=None, fire=None, underfoot=False, walk_under=False, **keywords):
    """Write `name`.mdl (ASCII), .mtr, .pwk and the DDS maps into `folder`; returns what was measured. The keywords are
    `shape`'s. A model lifted clear of a standing character's head gets no block to walk into, and nor does one laid
    `underfoot` (track, a floor marking), which is walked across. One to `walk_under` gets a block for each part of it
    that stands on the ground (`standing`) and the report tells how many, `walkBlocks`. `light` is the light
    its row of the placeables table casts ({colour, at}), refused further than LIGHT_NEAR from the model (`light_gap`).
    `fire` is the fires the game draws on it (`fire_lines`), each refused further than LIGHT_NEAR from the model as a
    light is: a fire stated before a turn or at another height would burn in the air. The report's `blankPanels` are
    the door-sized panels its picture draws in one flat colour (`blank_panels`)."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    made = shape(model, maps, height=height, colour=colour, sign_tilt=sign_tilt, **keywords)
    vertices, card = made['vertices'], made['card']; gap = light_gap(vertices, made['faces'], light['at']) if light else None
    require(gap is None or gap <= LIGHT_NEAR, f'The light of {name} stands {gap or 0:.2f} metres from the model, and the game draws a flare where it stands, in the '
            f'air beside the lamps: set it at a lamp\'s lens or inside the model (a beam, a housing), within {LIGHT_NEAR} metres')
    for part in fire or []:
        away = light_gap(vertices, made['faces'], fire_values(part)[0])
        require(away <= LIGHT_NEAR, f'A fire of {name} burns {away:.2f} metres from the model, in the air: state it on the finished model, within {LIGHT_NEAR} metres '
                f'of what burns ({part.get("part", part["at"])})')
    for part in keywords.get('embers') or []:  # here and not in `shape`: `view`, which its place is read from, draws a model whose bed is stated wrong
        away = light_gap(vertices, made['faces'], part['at'])
        require(away <= LIGHT_NEAR + float(part['radius']), f'A bed of embers of {name} lies {away:.2f} metres from the model, in the air: state it on the finished model '
                f'({part.get("part", part["at"])})')
    (folder / f'{name}.mdl').write_text(model_text(name, vertices, made['normals'], made['uvs'], made['faces'], card.cards if card else None, made['wire'], made.get('glass'), fire, made.get('embers')),
                                        encoding='cp1252', newline='\n')
    blocks = standing(vertices, made['faces']) if walk_under else None
    # What is walked across is low enough to step over, as a part laid underfoot in a group is (`tile.group`).
    require(not underfoot or float(vertices[:, 2].max()) <= UNDERFOOT_MOST + 1e-6, f'{name} is laid underfoot and stands {float(vertices[:, 2].max()):.2f} metres high: '
            f'what is walked across stands no higher than the knee, {UNDERFOOT_MOST} metres')
    (folder / f'{name}.pwk').write_text(walk_text(name, vertices, overhead=underfoot or float(vertices[:, 2].min()) >= OVERHEAD, blocks=blocks), encoding='cp1252', newline='\n')
    panels = shipped_blank_panels(made, maps, keywords.get('smooth'))
    # `lightAt` is the light this conversion measured: `envkit placeables` writes a row no other light (`additions.command_placeables`).
    return {'blankPanels': panels, 'fires': len(fire or []), **({} if blocks is None else {'walkBlocks': len(blocks)}), **measured(name, made, skin(name, maps, folder, crunch, made, colour=colour), sign_tilt),
            **({} if gap is None else {'lightFromModel': round(gap, 3), 'lightAt': [float(value) for value in light['at']]})}
