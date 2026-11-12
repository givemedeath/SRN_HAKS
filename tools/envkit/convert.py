"""Turn a generated model into a game placeable: ASCII model, material file, DDS textures and collision.

The layout is the one working PBR placeables use (SWLOR's SWTOR conversions, read 2026-11-10): a dummy root and trimesh
nodes whose `bitmap` is also the name of the material file, shadows off on the dense mesh, colour as DXT1, the normal map
as two-channel ATI2 and the one-channel maps as ATI1.

A generated model has no real size and faces glTF's way (Y up, front along +Z). `fit` turns it to the game's axes (Z up,
front along +Y), scales it to a stated height in metres, centres it and stands it on the ground."""
import json
import struct
import subprocess
from pathlib import Path

import numpy as np

from . import require

COMPONENT = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
TO_GAME = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])  # a rotation: glTF up (Y) to Z, glTF front (+Z) to +Y
NODE_VERTICES = 60000  # a compiled mesh node indexes its vertices with 16 bits
NAME_LENGTH = 14  # a resref is 16 characters and the maps add a two-character suffix
TILE_NAME_LENGTH = 12  # a tile group's models add four: _t and the tile's row and column
NON_WALK = 7
RETOUCH = 2048  # pixels: the finest map of places a colour picture is retouched by
WIRE = (118, 122, 126)  # galvanised steel
# A fence's wires are drawn on a small picture of their own, which its sheets repeat: its width in pixels, and the least
# pixels across a wire that still draw one.
WIRE_PICTURE, WIRE_TEXELS = 128, 2.5
PANEL_DEPTH = 0.6  # metres: the most a `mesh` box's texels may lie apart across the panel's run and still be one flat panel
FENCE_NEAR = 0.3  # metres: how near each end of a fence some part of the model must lie, since a fence hangs between its posts
OVERHEAD = 2.2  # metres: what hangs at least this high is walked under
DIELECTRIC = 0.04  # share of light a non-metal reflects head on
DOOR_LEAF = (1.9, 2.5)  # metres: how tall a door a character walks through may be
MEASURED = ('lit', 'paint', 'smooth', 'mesh', 'fence', 'close')  # what a game set states in metres on the finished model, beside a tile group's door and fade height
CLOSE_NEAR = 0.02  # how near one of the model's own vertices a closing face's stated corner lies, metres
DOOR_TYPE = 58  # the row of doortypes.2da every building's door hook takes: the invisible transition door (user, 2026-11-11, until further notice)


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
        of_face = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
        summed = np.zeros_like(normals)
        for corner in range(3):
            np.add.at(summed, faces[:, corner], of_face)
        normals[bad] = summed[bad]; lengths = np.linalg.norm(normals, axis=1)
        normals[lengths < 1e-12] = (0.0, 0.0, 1.0); lengths = np.linalg.norm(normals, axis=1)
    return normals / lengths[:, None], int(bad.sum())


def closed(vertices, normals, uvs, faces, parts):
    """`faces` with one more for each of `parts` ([{corners: three points in metres on the finished model}]): a hole a
    generator left in a surface, closed between three of the model's own vertices. The Ares fence section came back
    with two faces of its concrete base lying over each other and a wedge between them open to the ground behind
    (seen in the client, 2026-11-12). Each corner is the vertex nearest the stated point, within `CLOSE_NEAR`; where
    several stand at one place (a seam of the picture), those whose places on the picture lie nearest together are
    taken, so that the face is drawn with the picture round the hole. It faces the way its corners' normals do.
    No vertex is added, so nothing else of the model changes."""
    from itertools import product
    faces = np.asarray(faces); added = []; held = {tuple(sorted(face)) for face in faces.tolist()}
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
        require(tuple(sorted((a, b, c))) not in held, f'The model already has a face between these corners ({label})')
        if float(across @ (normals[a] + normals[b] + normals[c])) < 0:
            b, c = c, b
        added.append([a, b, c]); held.add(tuple(sorted((a, b, c))))
    return np.vstack([faces, np.asarray(added, faces.dtype)]) if added else faces


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


def model_text(name, vertices, normals, uvs, faces, cards=None, wire=None):
    """The ASCII model. `wire` is a fence's sheets (`sheets`), which show `name`_w, a plain picture with gaps.
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
    return '\n'.join(lines + [f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


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


def walk_text(name, vertices, *, overhead=False):
    """Collision: an upright block on the model's footprint (`outline`), as tall as the model, and where a character
    stands to use it (in front and behind). `overhead` leaves the block out: a thing hung above head height is walked
    under."""
    vertices = np.asarray(vertices, float); (x0, y0, _), (x1, y1, z1) = vertices.min(0), vertices.max(0); lines = []
    if not overhead:
        corners = outline(vertices); count = len(corners)
        verts = [(x, y, 0.0) for x, y in corners] + [(x, y, z1) for x, y in corners]
        faces = [face for index in range(count) for face in ((index, (index + 1) % count, (index + 1) % count + count), (index, (index + 1) % count + count, index + count))]
        faces += [(count, count + index, count + index + 1) for index in range(1, count - 1)]
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


def _compress(image, target, mode, size, crunch, *, data):
    """One PNG through the texture compressor to a mipmapped DDS. `data` maps are filtered without gamma."""
    source = target.with_suffix('.source.png'); image.resize((size, size)).save(source)
    command = [crunch, '-file', str(source), '-out', str(target), '-fileformat', 'dds', mode, '-mipMode', 'Generate', '-noprogress',
               '-gamma', '1.0' if data else '2.2'] + (['-renormalize'] if mode == '-DXN' else [])
    result = subprocess.run(command, capture_output=True, text=True, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    source.unlink()
    require(result.returncode == 0 and target.is_file(), f'{target.name} did not compress: {(result.stdout + result.stderr)[-400:]}')
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


def sheets(fences, size=WIRE_PICTURE):
    """Chain-link sheets hung between a fence's posts: {vertices, normals, uvs, faces, image}, a mesh of its own.

    fences: [{from: [x, y], to: [x, y], z: [low, high], pitch, wire, colour}] on the finished model; a sheet stands
    upright from one point to the other and is seen from both sides. A generator leaves a fence's frames empty and
    paints the mesh on whatever stands behind (the Ares Depot's perimeter, seen from an angle in the client,
    2026-11-11). The wires are drawn on `image`, a small picture of their own that is see-through between them, as
    many links of the pattern as leave a wire its pixels; the model's colour picture keeps its size and stays opaque
    (with an alpha channel the depot's, at 4096 pixels, was 22 MB). Each sheet is cut into squares one picture across,
    so a tile group can share them out among its tiles."""
    from PIL import Image
    first = fences[0]; pitch, wire, colour = first['pitch'], first['wire'], list(first.get('colour', WIRE))
    require(all((one['pitch'], one['wire'], list(one.get('colour', WIRE))) == (pitch, wire, colour) for one in fences), 'The fences of a model share one wire mesh')
    link = pitch * np.sqrt(2)  # the pattern repeats every `link` metres along and up
    links = int(wire * size / (WIRE_TEXELS * link)); require(links >= 1, f'A wire this thin cannot be drawn on a picture of {size} pixels')
    from . import glow
    period = links * link; at = (np.arange(size) + 0.5) / size * period; along, up = np.meshgrid(at, at)
    drawn = glow.wires(along, up, pitch, wire)  # the pattern a `mesh` panel is painted with
    pixels = np.empty((size, size, 4), np.uint8); pixels[..., :3] = colour; pixels[..., 3] = drawn * 255  # the wire's colour under the gaps too
    vertices, normals, uvs, faces = [], [], [], []
    for one in fences:
        start, end = np.asarray(one['from'], float), np.asarray(one['to'], float); low, high = (float(value) for value in one['z'])
        length = float(np.linalg.norm(end - start)); ahead = (end - start) / length; out = np.array([ahead[1], -ahead[0], 0.0])
        for i in range(int(np.ceil(length / period - 1e-9))):
            for j in range(int(np.ceil((high - low) / period - 1e-9))):
                s0, z0 = i * period, low + j * period; s1, z1 = min(length, s0 + period), min(high, z0 + period)
                corners = [(s0, z0), (s1, z0), (s1, z1), (s0, z1)]
                place = [[*(start + ahead * s), z] for s, z in corners]; spot = [[(s - s0) / period, (z - z0) / period] for s, z in corners]
                for way, order in ((out, ((0, 1, 2), (0, 2, 3))), (-out, ((0, 2, 1), (0, 3, 2)))):  # a face each way, each with its own normals
                    base = len(vertices); vertices += place; normals += [way.tolist()] * 4; uvs += spot
                    faces += [[base + a, base + b, base + c] for a, b, c in order]
    return {'vertices': np.array(vertices), 'normals': np.array(normals), 'uvs': np.array(uvs), 'faces': np.array(faces), 'image': Image.fromarray(pixels, 'RGBA'),
            'period': period}


def retouch(image, vertices, uvs, faces, *, tone=None, paint=(), smooth=(), mesh=(), size=RETOUCH, placed=None):
    """(colour, flat, plain): a model's colour picture as it ships, where its relief is to be flattened, and where its
    other maps are to be smoothed as its colour was: [(texels, reach in texels)] for each smoothed part, with its marked
    texels third for a marking, at the retouching's own grain (the last two, or None). `placed` is the model's position map at that grain
    (`glow.position_map`: where, covered), for a caller that has made one already.

    `tone` multiplies the whole picture (a model that came back paler than its reference). `paint` covers what a
    generator invented: [{box, colour}], every texel within the box in one colour (0-255). `mesh` makes a panel a
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
    the box's usual tint change, each to the rest of the box blurred over `radius` (the smeared red marking on the
    concrete base of the Ares fence section, which smoothing the whole face left a plain panel beside weathered ones,
    2026-11-12)."""
    from PIL import Image
    from . import glow
    colour = np.asarray(image.convert('RGB'), np.float32) / 255; alpha = flat = None; grain = min(size, image.width)
    plain = [] if smooth else None
    if tone is not None:
        colour = np.clip(colour * tone, 0, 1)
    if smooth or mesh:
        flat = np.zeros(colour.shape[:2], bool)
    if mesh:
        alpha = np.ones(colour.shape[:2], bool)
    if paint or smooth or mesh:
        where, covered = placed if placed is not None else glow.position_map(vertices, uvs, faces, grain)
        require(covered.shape == (grain, grain), f'The position map handed to the retouching is {grain} texels across')
        full = lambda mask: np.asarray(Image.fromarray(mask).resize(image.size, Image.NEAREST))
        for part in paint:
            colour[full(glow.held(where, covered, part, 'painted'))] = np.asarray(part['colour'], float) / 255
        for part in smooth:
            chosen = glow.held(where, covered, part, 'smoothed')
            beside = chosen[:, 1:] & chosen[:, :-1]  # how far apart on the model two texels side by side are
            step = float(np.median(np.linalg.norm(where[:, 1:][beside] - where[:, :-1][beside], axis=1))) if beside.any() else 0.0
            # No two texels side by side, or all at one place, leaves no step to measure by: the reach then stops at an
            # eighth of the picture, where an unbounded one would pad the blur by a hundred thousand texels.
            plain.append((chosen, max(int(round(min(part['radius'] / max(step, 1e-6), grain / 8))), 1)))
        if smooth:  # the picture is brought to the grain once, each part is smoothed there in turn, and it is brought back once
            small = np.asarray(Image.fromarray((colour * 255).round().astype(np.uint8)).resize((grain, grain), Image.BOX), np.float32) / 255
            for index, part in enumerate(smooth):
                if 'tint' in part:  # a marking: the tinted texels, and three texels round them for their soft edge
                    chosen, reach = plain[index]; tint = small - small.mean(-1, keepdims=True)
                    marked = chosen & (np.abs(tint - np.median(tint[chosen], 0)).max(-1) * 255 > part['tint'])
                    marked = chosen & (_blur(marked.astype(np.float32), 1) > 0.02)
                    require(bool(marked.any()) and bool((chosen & ~marked).any()), 'A marking is tinted texels on a surface that is not: the box holds '
                            + ('nothing but tint' if marked.any() else 'no tint') + ' (' + str(part.get('part', 'smoothed')) + ')')
                    plain[index] = (chosen & ~marked, reach, marked)
            small, done = _spread(small, [(chosen, reach, part.get('colour'), *marked) for (chosen, reach, *marked), part in zip(plain, smooth)])
            wide = np.asarray(Image.fromarray((np.clip(small, 0, 1) * 255).round().astype(np.uint8)).resize(image.size, Image.BILINEAR), np.float32) / 255
            done = full(done); colour[done] = wide[done]; flat |= done
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


def textures(name, maps, folder, crunch, *, colour=1024, illumination=None, base=None, flat=None, plain=None):
    """`maps` holds base_color, normal, metallic and roughness image paths. Colour at `colour` pixels, the rest at half.
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
    written = [_compress(shown, folder / f'{name}.dds', '-DXT5' if shown.mode == 'RGBA' else '-DXT1', colour, crunch, data=False),
               _compress(relief, folder / f'{name}_n.dds', '-DXN', half, crunch, data=True),
               _compress(channel(shine), folder / f'{name}_s.dds', '-DXT5A', half, crunch, data=True),
               _compress(channel(grey('roughness')), folder / f'{name}_r.dds', '-DXT5A', half, crunch, data=True)]
    if illumination is not None:  # a path or an image; mostly black, so half size like the other maps
        lit = illumination if isinstance(illumination, Image.Image) else Image.open(illumination)
        written.append(_compress(lit.convert('RGB'), folder / f'{name}_i.dds', '-DXT1', half, crunch, data=False))
    return written


def load_models(path):
    """The game models of a set: {name: {source, height, colour, signTilt, lift, turn, tone, paint, smooth, mesh,
    fence, close, lit, halo, tiles, measuredAt}}. `lift` hangs the model that many metres above the ground it is placed on (a camera on a wall). `turn`
    turns it that many degrees counter-clockwise seen from above, where its front came back facing a side; boxes are
    on the model as turned. `tone`, `paint`, `smooth` and `mesh` retouch its colour picture (`retouch`); `fence` hangs
    chain-link sheets between its fence posts, with a picture of their own (`sheets`); `close` closes a hole in it
    with a face between three of its own vertices (`closed`). `source` is the generated
    model's folder under the set's output root (never a machine path); `lit` boxes are in metres on the finished model;
    `tiles` makes the model a tile group too: its ground texture, its group name and palette label, the terrain its
    corners stand on in each tileset ({tileset: terrain}), and optionally `fade`, the height above which the game may
    hide it, and `door` ({at: [x, y, z], facing, type, leaf}: the middle of the foot of a door on the finished model, the
    way it looks out in degrees from east towards north (90 is north), its row of doortypes.2da, which is the invisible
    transition door's, and `leaf`, the height in metres of the door leaf as measured on the finished model, which must
    be a door a character fits; `tile.doorstep` draws the hook out onto open ground and turns it). A tile group takes no `lift`.
    `measuredAt` is the height the model had when its boxes, fences, door and fade height were measured: a model that
    states any of them states it, and it must be the model's height still. `placeable` gives it a row in the placeables table: its label
    and the row of placeableobjsnds.2da it sounds like, and optionally the palette `category` its blueprint is offered
    under and whether the blueprint is `static` (by default a model with lit parts is not, so a script can reach it)."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and set(data) == {'models'} and isinstance(data['models'], dict) and data['models'], 'A game set has exactly models')
    for name, model in data['models'].items():
        require(name == name.lower() and name.isidentifier() and len(name) <= NAME_LENGTH, f'Model names are lowercase, at most {NAME_LENGTH} characters: {name}')
        require(isinstance(model, dict) and {'source', 'height'} <= set(model) <= {'source', 'height', 'colour', 'signTilt', 'lift', 'turn', 'tone', 'paint', 'smooth', 'mesh', 'fence', 'close', 'lit', 'halo', 'tiles', 'placeable', 'measuredAt'},
                'Model needs source and height: ' + name)
        number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        box = lambda part: np.asarray(part.get('box', 0), float).shape == (2, 3)
        require(number(model.get('turn', 0)) and -180 <= model.get('turn', 0) <= 180, 'A model is turned by -180 to 180 degrees: ' + name)
        require(number(model.get('tone', 1)) and 0.2 <= model.get('tone', 1) <= 2, 'A tone is 0.2 to 2 times the colour: ' + name)
        shade = lambda value: isinstance(value, list) and len(value) == 3 and all(type(part) is int and 0 <= part <= 255 for part in value)
        for part in model.get('paint', []):
            require(isinstance(part, dict) and {'box', 'colour'} <= set(part) <= {'part', 'box', 'colour'} and box(part) and shade(part['colour']),
                    'A painted part needs a box and a colour of three 0-255 values: ' + name)
        for part in model.get('mesh', []):
            require(isinstance(part, dict) and {'box', 'pitch', 'wire'} <= set(part) <= {'part', 'box', 'pitch', 'wire', 'colour'} and box(part)
                    and number(part['pitch']) and number(part['wire']) and 0 < part['wire'] < part['pitch'] <= 1 and shade(part.get('colour', [0, 0, 0])),
                    'A wire mesh needs a box, a pitch of at most a metre and a thinner wire: ' + name)
        for part in model.get('smooth', []):
            require(isinstance(part, dict) and {'box', 'radius'} <= set(part) <= {'part', 'box', 'radius', 'colour', 'tint'} and box(part) and number(part['radius'])
                    and 0.01 <= part['radius'] <= 1 and shade(part.get('colour', [0, 0, 0])), 'A smoothed part needs a box and a radius of 0.01 to 1 metres: ' + name)
            require('tint' not in part or (number(part['tint']) and 1 <= part['tint'] <= 255 and 'colour' not in part),
                    'A marking is taken off by its tint, 1 to 255 levels from the surface\'s, and the surface keeps its own colour: ' + name)
        for part in model.get('close', []):
            require(isinstance(part, dict) and {'corners'} <= set(part) <= {'part', 'corners'} and isinstance(part['corners'], list) and len(part['corners']) == 3
                    and all(isinstance(corner, list) and len(corner) == 3 and all(number(value) for value in corner) for corner in part['corners']),
                    'A closing face needs three corners, each a point in metres on the finished model: ' + name)
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
        spans = [np.asarray(part['box'], float)[:, 2] for key in ('lit', 'paint', 'smooth', 'mesh') for part in model.get(key, [])]
        require(all(high > foot and low < head for low, high in spans + [part['z'] for part in model.get('fence', [])]),
                f'A box or fence lies wholly above or below the model, which stands from {foot} to {head} metres up: {name}')
        require(set(model.get('halo', {})) <= {'reach', 'strength', 'core', 'least'} and ('halo' not in model or model.get('lit')),
                'A halo takes reach, strength, core and least, and needs lit parts: ' + name)
        placed = model.get('placeable')
        require(placed is None or ({'label', 'sound'} <= set(placed) <= {'label', 'sound', 'category', 'static'} and isinstance(placed['label'], str) and placed['label']
                                   and type(placed['sound']) is int and type(placed.get('category', 0)) is int and type(placed.get('static', True)) is bool),
                'A placeable needs a label and a sound row: ' + name)
        tiles = model.get('tiles')
        require(tiles is None or ({'ground', 'group', 'label', 'sets'} <= set(tiles) <= {'ground', 'group', 'label', 'sets', 'fade', 'door'} and isinstance(tiles['sets'], dict) and tiles['sets']
                                  and all(isinstance(value, str) and value for value in (tiles['ground'], tiles['group'], tiles['label'], *tiles['sets'], *tiles['sets'].values()))),
                'Tiles need a ground texture, a group name, a palette label and the terrain in each tileset: ' + name)
        require(tiles is None or len(name) <= TILE_NAME_LENGTH, f'A tile group model is named in at most {TILE_NAME_LENGTH} characters: {name}')
        # A tile group stands on the ground: `tiles` builds it there, and a lift would only move its boxes off it.
        require(tiles is None or not model.get('lift'), 'A tile group stands on the ground and takes no lift: ' + name)
        door = (tiles or {}).get('door')
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
        # Every box, fence, door and fade height is a measurement, and a measurement is of the model at one height. A
        # typed door leaf would go on passing after its building was made taller or lower, and a lit box would go on
        # holding some of the model and lighting the wrong part of it (found in review, 2026-11-12): so a model that
        # states any measurement says the height it had when they were made, and at another height they are made again.
        measured = any(model.get(key) for key in MEASURED) or door is not None or fade is not None
        require('measuredAt' in model if measured else True, 'A model that states boxes, fences, a door or a fade height says the height it had when they '
                f'were measured (measuredAt: {model["height"]}, if they were measured on the model as it is now): ' + name)
        require('measuredAt' not in model or (number(model['measuredAt']) and model['measuredAt'] == model['height']),
                f'The boxes, fences, door and fade height of a model were measured with the model {model.get("measuredAt")} metres tall and it is now '
                f'{model["height"]}: measure them again on the model as it is, and say so in measuredAt: ' + name)
    return data['models']


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


def lights_script(name, target, on, halo=True):
    """One line of NWScript that puts the lights of the object `target` (an expression) out, or back on."""
    swaps = [(name, f'{name}_o')] + ([(f'{name}_h', HALO_OUT)] if halo else [])
    return ''.join(f'ReplaceObjectTexture({target},"{old}"' + ('' if on else f',"{new}"') + ');' for old, new in swaps)


def blackout_script(name, player, on, halo=True):
    """One line of NWScript that puts out, or back on, the lights of every `name` the player `player` (an expression;
    OBJECT_INVALID for everyone) sees: tiles and static scenery as well as objects a script can reach."""
    swaps = [(f'{name}_i', f'{name}_o')] + ([(f'{name}_h', HALO_OUT)] if halo else [])
    return ''.join(f'SetTextureOverride("{old}","{"" if on else new}",{player});' for old, new in swaps)


def shape(model, maps, *, height, colour=1024, illumination=None, sign_tilt=None, lit=None, halo=None, lift=0.0, turn=0.0, tone=None, paint=None,
          smooth=None, mesh=None, fence=None, close=None):
    """The finished model in game space and what lights it: {vertices, normals, uvs, faces, scale, angles, repaired,
    illumination, card, colour, flat, plain, turn, wire}. `turn` turns it about the vertical before anything is measured on it; `close`
    closes holes in it with faces between its own vertices (`closed`), before its pictures are worked on; `tone`,
    `paint`, `smooth` and `mesh` give `colour`, `flat` and `plain`: its colour picture retouched, where its relief is levelled and
    where its other maps are smoothed (`retouch`; all None for a model left as generated). `fence` gives `wire`, the chain-link sheets hung on it and their picture (`sheets`). `sign_tilt`, in degrees, rebuilds a two-sided sign from its front sheet (`two_sided`). `lit`
    names the parts lit from within as boxes on the finished model (`glow.glow`); `illumination` is a ready-made glow
    map instead. `halo` ({reach, strength, core}) adds the cards that spread the lit parts' light (`glow.halo`)."""
    vertices, normals, uvs, faces = read_glb(model); card = None
    vertices, normals, uvs, scale, angles = fit(vertices, normals, uvs, height, faces=faces)
    if sign_tilt is not None:
        vertices, normals, uvs, faces = two_sided(vertices, normals, uvs, faces, sign_tilt)
        vertices, again = stand(vertices, height); scale *= again
    if turn:
        spin = _turn(float(turn), 0.0, 0.0); vertices, normals = vertices @ spin.T, normals @ spin.T
        vertices, _ = stand(vertices, height)
    normals, repaired = repair_normals(vertices, normals, faces)
    vertices = vertices + [0.0, 0.0, float(lift)]  # hung at its height before its lit parts are found: their boxes are on the finished model
    if close:
        faces = closed(vertices, normals, uvs, faces, close)
    require(not halo or lit, 'A halo spreads the lit parts: name them')
    require(not lit or illumination is None, 'Give the lit parts or a glow map, not both')
    wire = None
    if fence:  # before the long work on the pictures: a fence that is refused is refused in the first seconds
        _hung(vertices, faces, fence); wire = sheets(fence)
    shown = flat = plain = placed = None; retouched = tone is not None or paint or smooth or mesh
    if lit or retouched:
        from PIL import Image
        from . import glow
    if lit:
        size = max(colour // 2, 256); placed = glow.position_map(vertices, uvs, faces, size, facing=True)
    if retouched:
        with Image.open(maps['base_color']) as picture:
            same = placed is not None and size == min(RETOUCH, picture.width)  # the glow's map of places serves the retouching where their sizes agree
            shown, flat, plain = retouch(picture, vertices, uvs, faces, tone=tone, paint=paint or (), smooth=smooth or (), mesh=mesh or (),
                                         placed=placed[:2] if same else None)
    if lit:  # by the picture as it ships: what was painted over or toned down does not shine through by night as it was
        with Image.open(maps['base_color']) as picture:
            base = np.asarray((shown if shown is not None else picture).convert('RGB').resize((size, size)), float) / 255
        where, covered, toward = placed; shine = glow.glow(base, where, covered, lit)
        illumination = Image.fromarray((shine * 255).round().astype(np.uint8))
        card = glow.halo(shine, where, covered, toward=toward, **halo) if halo else None
    return {'vertices': vertices, 'normals': normals, 'uvs': uvs, 'faces': faces, 'scale': scale, 'angles': angles, 'repaired': repaired,
            'illumination': illumination, 'card': card, 'colour': shown, 'flat': flat, 'plain': plain, 'turn': float(turn), 'wire': wire}


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
    if made.get('wire'):  # a plain picture, see-through between the wires: it needs no material file; _w is a suffix like the maps'
        files.append(_compress(made['wire']['image'], folder / f'{name}_w.dds', '-DXT5', made['wire']['image'].width, crunch, data=False))
    if illumination is not None:
        files += lights_out(name, folder, crunch, bool(card))
    return files


def measured(name, made, files, sign_tilt=None):
    vertices, faces, card, angles = made['vertices'], made['faces'], made['card'], made['angles']
    return {'name': name, 'triangles': len(faces), 'vertices': len(vertices), 'nodes': len(split(faces)), 'scale': round(float(made['scale']), 5),
            'repairedNormals': made['repaired'], 'signTilt': sign_tilt, 'lit': made['illumination'] is not None, 'haloCards': len(card.cards) if card else 0,
            'turnedByDegrees': {'yaw': angles[0], 'pitch': angles[1], 'roll': angles[2]}, 'turn': made.get('turn', 0.0), 'seeThrough': made.get('colour') is not None and made['colour'].mode == 'RGBA', 'fenceFaces': len(made['wire']['faces']) if made.get('wire') else 0,
            'size': [round(float(v), 3) for v in vertices.max(0) - vertices.min(0)], 'textures': {f.name: f.stat().st_size for f in files}}


def placeable(name, model, maps, folder, crunch, *, height, colour=1024, sign_tilt=None, **keywords):
    """Write `name`.mdl (ASCII), .mtr, .pwk and the DDS maps into `folder`; returns what was measured. The keywords are
    `shape`'s. A model lifted clear of a standing character's head gets no block to walk into."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    made = shape(model, maps, height=height, colour=colour, sign_tilt=sign_tilt, **keywords)
    vertices, card = made['vertices'], made['card']
    (folder / f'{name}.mdl').write_text(model_text(name, vertices, made['normals'], made['uvs'], made['faces'], card.cards if card else None, made['wire']),
                                        encoding='cp1252', newline='\n')
    (folder / f'{name}.pwk').write_text(walk_text(name, vertices, overhead=float(vertices[:, 2].min()) >= OVERHEAD), encoding='cp1252', newline='\n')
    return measured(name, made, skin(name, maps, folder, crunch, made, colour=colour), sign_tilt)
