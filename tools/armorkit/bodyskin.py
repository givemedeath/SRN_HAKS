"""The body's own skin on a part an outfit only half covers: a short sleeve's upper arm.

A worn part takes the place of the body's part in its slot, so the upper-arm part of a short-sleeved shirt has to
be the sleeve and the bare arm below its hem. The arm is the body's own part, added to the outfit's: its
vertices and its authored normals as they are, so that it still meets the body's forearm at the elbow, and its
textures as they are. Those are a tint texture (the skin's shade), a normal map and a roughness map, bound by the
material file its model names (docs/phenotype-body-material-process.md).

The part's textures are doubled in size, to at most `limit` a side. The outfit's own lie in the quarter that
starts at texture coordinate 0, and the body's whole textures in the quarter that ends at 1, at whatever size
that leaves them. The body's texture coordinates are only halved and moved, never laid out again: a normal map
is read in the frame its coordinates span, and turned or sheared it would light the skin from another side.

What the sleeve hides of the arm is left out (`shown`): the two together would be over a part's budget.
"""
from pathlib import Path

import numpy as np

from tools.headkit import native_reader

from . import export, registry, seams
from .registry import require

BAND = 0.04  # the arm is kept this far up under the sleeve's hem: what a look up the sleeve can reach
SECTORS = 16  # the hem is found in this many directions round the arm
ROUGH = 0.8  # the roughness of the outfit's own surface, as `texture.write_relief` gives a part without a map
EDGE = 2  # texels the body's textures are continued past their quarter, into the two quarters nothing lies in
KEYS = ('skin', 'skin_at', 'skin_tint', 'skin_rough')  # what a part with skin holds beside a baked part's keys


def image(blob):
    """The rows of an uncompressed true-colour TGA as 0-1 RGB, the first at texture coordinate v = 0."""
    require(len(blob) > 18 and blob[1] == 0 and blob[2] == 2 and blob[16] in (24, 32), 'Only an uncompressed true-colour TGA is read')
    width, height, depth = int.from_bytes(blob[12:14], 'little'), int.from_bytes(blob[14:16], 'little'), blob[16] // 8
    require(len(blob) >= 18 + blob[0] + width * height * depth, 'The TGA is cut short')
    pixels = np.frombuffer(blob, np.uint8, count=width * height * depth, offset=18 + blob[0]).reshape(height, width, depth)[:, :, 2::-1]
    return (pixels[::-1] if blob[17] & 0x20 else pixels) / 255.0  # stored from the top row down, where the flag says so


def material(folder, name):
    """{normal, rough}: the maps a material file `<name>.mtr` binds as texture1 and texture3; `rough` is None without one."""
    path = Path(folder) / (name + '.mtr')
    require(path.is_file(), f'{path}: the body part has no material file')
    words = [line.split() for line in path.read_text(encoding='ascii').splitlines()]
    named = {row[0]: row[1] for row in words if len(row) == 2 and row[0].startswith('texture')}
    require('texture1' in named and 'texture0' not in named, f'{path}: a skin material binds a normal map and no colour texture')
    return {'normal': named['texture1'], 'rough': named.get('texture3')}


def body_part(pack, textures, body, token, bones, number=1):
    """One skin part of a body with its textures: `v`, `f`, `uv`, `n` in body space, `tint` (rows of shade and
    layer), `relief` (its normal map, 0-1) and `rough` (its roughness, 0-1), each from v = 0.

    `pack` is the folder of the body's models and tint textures, `textures` that of its material files and
    maps, `bones` its rig (`measure.body`)."""
    pack, textures, name = Path(pack), Path(textures), registry.model_name(body, token, number)
    meshes = native_reader.decode((pack / (name + '.mdl')).read_bytes(), name, require_tangents=False, apply_rigid_transforms=True)
    require(meshes, 'Model has no rigid mesh: ' + name)
    bitmaps = {mesh['textures'][0] for mesh in meshes}
    require(len(bitmaps) == 1, f'{name}: its meshes are of {len(bitmaps)} materials, and one part has one')
    world = np.asarray(bones[seams.BONES[token]], float)
    offsets = np.cumsum([0] + [len(mesh['position']) for mesh in meshes])
    normals = np.concatenate([mesh['normal'] for mesh in meshes]) @ world[:3, :3].T
    bound = material(textures, bitmaps.pop())
    relief = image((textures / (bound['normal'] + '.tga')).read_bytes())
    require(bound['rough'] is not None, f'{name}: its material binds no roughness map')
    return {'v': np.concatenate([mesh['position'] for mesh in meshes]) @ world[:3, :3].T + world[:3, 3],
            'f': np.concatenate([mesh['faces'].astype(int) + offset for mesh, offset in zip(meshes, offsets)]),
            'uv': np.concatenate([mesh['uv'] for mesh in meshes]).astype(float),
            'n': normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12),
            'tint': np.stack(export.read_tint((pack / (name + '.plt')).read_bytes()), axis=2),
            'relief': relief, 'rough': image((textures / (bound['rough'] + '.tga')).read_bytes())[:, :, 0]}


def shown(vertices, faces, cover, start, end, band=BAND, sectors=SECTORS):
    """Per face of a body part, whether it is kept beside the outfit's: False where the outfit hides it.

    `cover` holds the points of the outfit's own surface on the part, `start` and `end` the part's bone. In
    each of `sectors` directions round the bone the outfit reaches some way along it, a sleeve to its hem; a
    vertex of the body is hidden where it lies more than `band` short of the least the outfit reaches in its
    own direction and the two beside it, and a face where all three of its vertices are. The band is what
    is seen up a sleeve that stands a centimetre off the arm."""
    start, axis = np.asarray(start, float), seams.unit(np.asarray(end, float) - np.asarray(start, float))
    u, w = seams.frame(axis)

    def round_bone(points):
        relative = np.asarray(points, float) - start
        turn = np.arctan2(relative @ w, relative @ u)
        return relative @ axis, np.floor((turn + np.pi) / (2 * np.pi) * sectors).astype(int) % sectors

    along, sector = round_bone(cover)
    hem = np.full(sectors, -np.inf)
    np.maximum.at(hem, sector, along)
    reach = np.minimum(hem, np.minimum(np.roll(hem, 1), np.roll(hem, -1)))
    along, sector = round_bone(vertices)
    return ~(along < reach[sector] - band)[np.asarray(faces, int)].all(axis=1)


def resized(image, side, kind='mean'):
    """A square image at `side` texels a side, both sizes powers of two: smaller by the mean of each block
    (`mean`), by one texel of each (`pick`, for what has no mean, a layer) or as normals (`normal`, 0-1
    coded, the mean made a unit vector again); larger by repeating each texel."""
    image = np.asarray(image)
    size = len(image)
    require(image.shape[0] == image.shape[1] and size and side and size & (size - 1) == 0 and side & (side - 1) == 0,
            'Textures are square, a power of two a side')
    if side >= size:
        return image.repeat(side // size, axis=0).repeat(side // size, axis=1)
    step = size // side
    if kind == 'pick':
        return image[step // 2::step, step // 2::step]
    blocks = image.astype(float).reshape(side, step, side, step, -1)
    if kind == 'normal':
        mean = (blocks * 2 - 1).mean(axis=(1, 3))
        return (mean / np.maximum(np.linalg.norm(mean, axis=2, keepdims=True), 1e-12) + 1) / 2
    return blocks.mean(axis=(1, 3)).reshape((side, side) + image.shape[2:])


def tinted(part, tint):
    """A part's tint texture, (shades, layers), with the body's own shade and layer on the texels of its skin."""
    if 'skin_at' not in part:
        return tint
    return tuple(np.where(part['skin_at'], part['skin_tint'][..., k], tint[k]) for k in (0, 1))


def worn(part, skin, start, end, limit=1024):
    """A baked part (`bake.bake`) with the body's skin part beside the outfit's surface, where the outfit shows it.

    `skin` is the body's part (`body_part`), `start` and `end` the part's bone. The maps are as large again a
    side, up to `limit`: the outfit's keep their texels where that doubles them and are halved where it
    cannot. Beside a baked part's keys the result holds `skin`, per face, whether it is the body's;
    `skin_at`, per texel, whether it is of the body's textures; `skin_tint`, the body's shade and layer
    there; and `skin_rough`, the roughness of every texel, the body's map there and the outfit's own
    elsewhere. The body's faces are no closing's or cap's and of no material: `added`, `domed` and `trimmed`
    say so, and their vertices have no place on the generated mesh (`src`, zero)."""
    size = len(part['rgb'])
    side = min(2 * size, limit)
    half = side // 2
    kept = shown(skin['v'], skin['f'], part['v'][np.unique(part['f'][~part['added']])], start, end)
    require(kept.any(), 'The outfit hides all of the body part: it needs no skin')
    used, faces = np.unique(skin['f'][kept], return_inverse=True)
    faces = faces.reshape(-1, 3) + len(part['v'])
    count = len(faces)

    def laid(mine, theirs, fill, kind='mean'):
        """A map of the part's: the outfit's in the first quarter, the body's in the last and a little past it."""
        mine = np.asarray(mine)
        whole = np.full((side, side) + mine.shape[2:], fill, dtype=np.result_type(mine.dtype, np.asarray(fill).dtype))
        whole[:half, :half] = resized(mine, half, kind)
        if theirs is not None:
            block = resized(theirs, half, kind).reshape((half, half) + mine.shape[2:])
            whole[half:, half:] = block
            whole[half - EDGE:half, half:] = block[:1]
            whole[half:, half - EDGE:half] = block[:, :1]
        return whole

    flags = lambda mine: laid(np.asarray(mine, float), None, 0.0) > 0.5
    skin_at = np.zeros((side, side), bool)
    skin_at[half:, half - EDGE:], skin_at[half - EDGE:half, half:] = True, True
    tint = laid(np.zeros((size, size, 2), np.uint8), None, 0)
    tint[..., 0] = np.round(laid(np.zeros((size, size)), skin['tint'][..., 0].astype(float), 0.0))
    tint[..., 1] = laid(np.zeros((size, size), np.uint8), skin['tint'][..., 1], 0, 'pick')
    return {'v': np.concatenate([part['v'], skin['v'][used]]), 'f': np.concatenate([part['f'], faces]),
            'uv': np.concatenate([np.asarray(part['uv'], float) / 2, 0.5 + skin['uv'][used] / 2]),
            'n': np.concatenate([part['n'], skin['n'][used]]), 'src': np.concatenate([part['src'], np.zeros((len(used), 3))]),
            'rgb': laid(part['rgb'], None, 0.5), 'covered': flags(part['covered']),
            'relief': laid(part['relief'], skin['relief'], np.array([0.5, 0.5, 1.0]), 'normal'),
            **{key: flags(part[key]) for key in ('closing', 'cap', 'padded')},
            **{key: np.concatenate([part[key], np.zeros(count, bool)]) for key in ('added', 'domed')},
            'trimmed': np.concatenate([part['trimmed'], np.full(count, -1)]),
            'skin': np.concatenate([np.zeros(len(part['f']), bool), np.ones(count, bool)]), 'skin_at': skin_at, 'skin_tint': tint,
            'skin_rough': np.clip(np.round(laid(np.full((size, size), ROUGH), skin['rough'], ROUGH) * 255), 0, 255).astype(np.uint8)}
