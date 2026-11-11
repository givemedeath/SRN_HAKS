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

COMPONENT = {5120: 'i1', 5121: 'u1', 5122: '<i2', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
TO_GAME = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])  # a rotation: glTF up (Y) to Z, glTF front (+Z) to +Y
NODE_VERTICES = 60000  # a compiled mesh node indexes its vertices with 16 bits
NAME_LENGTH = 14  # a resref is 16 characters and the maps add a two-character suffix
NON_WALK = 7
DIELECTRIC = 0.04  # share of light a non-metal reflects head on


def require(condition, message):
    if not condition:
        raise ValueError(message)


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


def fit(vertices, normals, uvs, height, *, square=True):
    """The mesh in game space: turned to the game's axes, squared to them, `height` metres tall, centred, standing on
    z = 0. Texture coordinates pass through unchanged: the game reads a DDS from its first row, as glTF does (flipping
    them scrambled every texture island in the first client check)."""
    require(height > 0, 'A height in metres is required')
    points, turned = vertices @ TO_GAME.T, normals @ TO_GAME.T
    yaw = square_up(points) if square else 0.0
    if yaw:
        c, s = np.cos(np.radians(yaw)), np.sin(np.radians(yaw)); turn = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        points, turned = points @ turn.T, turned @ turn.T
    low, high = points.min(0), points.max(0)
    scale = height / (high[2] - low[2])
    points = (points - np.array([(low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]])) * scale
    return points, turned, np.array(uvs[:, :2], float), scale, yaw


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


def model_text(name, vertices, normals, uvs, faces):
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
    return '\n'.join(lines + [f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


def material_text(name, illumination=False):
    lines = ['renderhint NormalAndSpecMapped', '', f'texture0 {name}', f'texture1 {name}_n', f'texture2 {name}_s', f'texture3 {name}_r',
             'texture4 null', f'texture5 {name}_i' if illumination else 'texture5 null']
    return '\n'.join(lines) + '\n'


def walk_text(name, low, high):
    """Collision: a box over the model's footprint, and where a character stands to use it (in front and behind)."""
    (x0, y0, _), (x1, y1, z1) = low, high
    corners = [(x1, y1), (x0, y1), (x0, y0), (x1, y0)]
    verts = [(x, y, 0.0) for x, y in corners] + [(x, y, z1) for x, y in corners]
    faces = [(0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7), (4, 5, 6), (4, 6, 7)]
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
    if illumination is not None:
        written.append(_compress(Image.open(illumination).convert('RGB'), folder / f'{name}_i.dds', '-DXT1', colour, crunch, data=False))
    return written


def placeable(name, model, maps, folder, crunch, *, height, colour=1024, illumination=None):
    """Write `name`.mdl (ASCII), .mtr, .pwk and the DDS maps into `folder`; returns what was measured."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    vertices, normals, uvs, faces = read_glb(model)
    vertices, normals, uvs, scale, yaw = fit(vertices, normals, uvs, height)
    normals, repaired = repair_normals(vertices, normals, faces)
    (folder / f'{name}.mdl').write_text(model_text(name, vertices, normals, uvs, faces), encoding='cp1252', newline='\n')
    (folder / f'{name}.mtr').write_text(material_text(name, illumination is not None), encoding='cp1252', newline='\n')
    (folder / f'{name}.pwk').write_text(walk_text(name, vertices.min(0), vertices.max(0)), encoding='cp1252', newline='\n')
    files = textures(name, maps, folder, crunch, colour=colour, illumination=illumination)
    return {'name': name, 'triangles': len(faces), 'vertices': len(vertices), 'nodes': len(split(faces)), 'scale': round(float(scale), 5),
            'repairedNormals': repaired, 'squaredByDegrees': yaw,
            'size': [round(float(v), 3) for v in vertices.max(0) - vertices.min(0)], 'textures': {f.name: f.stat().st_size for f in files}}
