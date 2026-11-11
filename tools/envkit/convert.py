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
OVERHEAD = 2.2  # metres: what hangs at least this high is walked under
DIELECTRIC = 0.04  # share of light a non-metal reflects head on


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
    x, y, z = (glow.card_normal(card) + 0.0).round(5).tolist()
    return f'    {x:g} {y:g} {z:g}'


def model_text(name, vertices, normals, uvs, faces, cards=None):
    """The ASCII model. `cards` are a halo's sheets (`glow.halo`), four corners each, all showing `name`_h. That
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


def textures(name, maps, folder, crunch, *, colour=1024, illumination=None):
    """`maps` holds base_color, normal, metallic and roughness image paths. Colour at `colour` pixels, the rest at half."""
    from PIL import Image
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); half = max(colour // 2, 256)
    base = Image.open(maps['base_color']).convert('RGB')
    grey = lambda key: np.asarray(Image.open(maps[key]).convert('L').resize(base.size), float) / 255
    shine = np.clip(specular(np.asarray(base, float) / 255, grey('metallic')), 0, 1)
    channel = lambda values: Image.fromarray(np.repeat((values * 255).round().astype(np.uint8)[..., None], 4, axis=2), 'RGBA')
    written = [_compress(base, folder / f'{name}.dds', '-DXT1', colour, crunch, data=False),
               _compress(Image.open(maps['normal']).convert('RGB'), folder / f'{name}_n.dds', '-DXN', half, crunch, data=True),
               _compress(channel(shine), folder / f'{name}_s.dds', '-DXT5A', half, crunch, data=True),
               _compress(channel(grey('roughness')), folder / f'{name}_r.dds', '-DXT5A', half, crunch, data=True)]
    if illumination is not None:  # a path or an image; mostly black, so half size like the other maps
        lit = illumination if isinstance(illumination, Image.Image) else Image.open(illumination)
        written.append(_compress(lit.convert('RGB'), folder / f'{name}_i.dds', '-DXT1', half, crunch, data=False))
    return written


def load_models(path):
    """The game models of a set: {name: {source, height, colour, signTilt, lift, lit, halo, tiles}}. `lift` hangs the
    model that many metres above the ground it is placed on (a camera on a wall). `source` is the generated
    model's folder under the set's output root (never a machine path); `lit` boxes are in metres on the finished model;
    `tiles` makes the model a tile group too: its ground texture, its group name and palette label, the terrain its
    corners stand on in each tileset ({tileset: terrain}), and optionally `fade`, the height above which the game may
    hide it, and `door` ({at: [x, y, z], facing, type}: where a door stands on the finished model, the way it faces in
    degrees and its row of doortypes.2da); `placeable` gives it a row in the placeables table: its label
    and the row of placeableobjsnds.2da it sounds like, and optionally the palette `category` its blueprint is offered
    under and whether the blueprint is `static` (by default a model with lit parts is not, so a script can reach it)."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    require(isinstance(data, dict) and set(data) == {'models'} and isinstance(data['models'], dict) and data['models'], 'A game set has exactly models')
    for name, model in data['models'].items():
        require(name == name.lower() and name.isidentifier() and len(name) <= NAME_LENGTH, f'Model names are lowercase, at most {NAME_LENGTH} characters: {name}')
        require(isinstance(model, dict) and {'source', 'height'} <= set(model) <= {'source', 'height', 'colour', 'signTilt', 'lift', 'lit', 'halo', 'tiles', 'placeable'}, 'Model needs source and height: ' + name)
        require(isinstance(model.get('lift', 0), (int, float)) and 0 <= model.get('lift', 0) <= 20, 'A model is lifted by 0 to 20 metres: ' + name)
        source = Path(model['source'])
        require(not source.is_absolute() and '..' not in source.parts and ':' not in model['source'], 'Model source is a folder under the output root: ' + name)
        require(model['height'] > 0 and model.get('colour', 1024) in (512, 1024, 2048, 4096), 'Model height or colour size is out of range: ' + name)
        for region in model.get('lit', []):
            require(isinstance(region, dict) and 'box' in region and set(region) <= {'part', 'box', 'gain', 'saturation', 'value'}
                    and np.asarray(region['box'], float).shape == (2, 3), 'A lit part needs a box of two corners: ' + name)
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
        door = (tiles or {}).get('door')
        require(door is None or (isinstance(door, dict) and {'at'} <= set(door) <= {'at', 'facing', 'type'} and np.asarray(door['at'], float).shape == (3,)
                                 and type(door.get('type', 0)) is int and door.get('type', 0) >= 0), 'A door needs the place it stands at: ' + name)
        require((tiles or {}).get('fade') is None or 0 < tiles['fade'] < model['height'], 'The fade height lies within the model: ' + name)
    return data['models']


HALO_OUT = 'ek_off'  # one for every model: a black sheet added to the picture adds nothing
HALO_OUT_PACK = 'srn_placeable'  # the one pack that holds it: the same file in two packs fails repository verification


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


def shape(model, maps, *, height, colour=1024, illumination=None, sign_tilt=None, lit=None, halo=None, lift=0.0):
    """The finished model in game space and what lights it: {vertices, normals, uvs, faces, scale, angles, repaired,
    illumination, card}. `sign_tilt`, in degrees, rebuilds a two-sided sign from its front sheet (`two_sided`). `lit`
    names the parts lit from within as boxes on the finished model (`glow.glow`); `illumination` is a ready-made glow
    map instead. `halo` ({reach, strength, core}) adds the cards that spread the lit parts' light (`glow.halo`)."""
    vertices, normals, uvs, faces = read_glb(model); card = None
    vertices, normals, uvs, scale, angles = fit(vertices, normals, uvs, height, faces=faces)
    if sign_tilt is not None:
        vertices, normals, uvs, faces = two_sided(vertices, normals, uvs, faces, sign_tilt)
        vertices, again = stand(vertices, height); scale *= again
    normals, repaired = repair_normals(vertices, normals, faces)
    vertices = vertices + [0.0, 0.0, float(lift)]  # hung at its height before its lit parts are found: their boxes are on the finished model
    require(not halo or lit, 'A halo spreads the lit parts: name them')
    if lit:
        require(illumination is None, 'Give the lit parts or a glow map, not both')
        from PIL import Image
        from . import glow
        size = max(colour // 2, 256)
        base = np.asarray(Image.open(maps['base_color']).convert('RGB').resize((size, size)), float) / 255
        where, covered, toward = glow.position_map(vertices, uvs, faces, size, facing=True); shine = glow.glow(base, where, covered, lit)
        illumination = Image.fromarray((shine * 255).round().astype(np.uint8))
        card = glow.halo(shine, where, covered, toward=toward, **halo) if halo else None
    return {'vertices': vertices, 'normals': normals, 'uvs': uvs, 'faces': faces, 'scale': scale, 'angles': angles, 'repaired': repaired,
            'illumination': illumination, 'card': card}


def skin(name, maps, folder, crunch, made, *, colour=1024):
    """Write the model's material file and maps, its halo's and its lights-out set into `folder`; returns the textures."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); illumination, card = made['illumination'], made['card']
    (folder / f'{name}.mtr').write_text(material_text(name, illumination is not None), encoding='cp1252', newline='\n')
    files = textures(name, maps, folder, crunch, colour=colour, illumination=illumination)
    if card:
        files.append(_compress(card[0], folder / f'{name}_h.dds', '-DXT1', 512, crunch, data=False))
        card_material = ['renderhint NormalAndSpecMapped', '', f'texture0 {name}_h', 'texture1 null', 'texture2 null', 'texture3 null',
                         'texture4 null', f'texture5 {name}_h']
        (folder / f'{name}_h.mtr').write_text('\n'.join(card_material) + '\n', encoding='cp1252', newline='\n')
        (folder / f'{name}_h.txi').write_text('blending additive\n', encoding='ascii', newline='\n')
    if illumination is not None:
        files += lights_out(name, folder, crunch, bool(card))
    return files


def measured(name, made, files, sign_tilt=None):
    vertices, faces, card, angles = made['vertices'], made['faces'], made['card'], made['angles']
    return {'name': name, 'triangles': len(faces), 'vertices': len(vertices), 'nodes': len(split(faces)), 'scale': round(float(made['scale']), 5),
            'repairedNormals': made['repaired'], 'signTilt': sign_tilt, 'lit': made['illumination'] is not None, 'haloCards': len(card[1]) if card else 0,
            'turnedByDegrees': {'yaw': angles[0], 'pitch': angles[1], 'roll': angles[2]},
            'size': [round(float(v), 3) for v in vertices.max(0) - vertices.min(0)], 'textures': {f.name: f.stat().st_size for f in files}}


def placeable(name, model, maps, folder, crunch, *, height, colour=1024, illumination=None, sign_tilt=None, lit=None, halo=None, lift=0.0):
    """Write `name`.mdl (ASCII), .mtr, .pwk and the DDS maps into `folder`; returns what was measured. The keywords are
    `shape`'s. A model lifted clear of a standing character's head gets no block to walk into."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    made = shape(model, maps, height=height, colour=colour, illumination=illumination, sign_tilt=sign_tilt, lit=lit, halo=halo, lift=lift)
    vertices, card = made['vertices'], made['card']
    (folder / f'{name}.mdl').write_text(model_text(name, vertices, made['normals'], made['uvs'], made['faces'], card[1] if card else None),
                                        encoding='cp1252', newline='\n')
    (folder / f'{name}.pwk').write_text(walk_text(name, vertices, overhead=float(vertices[:, 2].min()) >= OVERHEAD), encoding='cp1252', newline='\n')
    return measured(name, made, skin(name, maps, folder, crunch, made, colour=colour), sign_tilt)
