"""The body's own skin on a part an outfit only half covers: a short sleeve's upper arm.

A worn part takes the place of the body's part in its slot, so the upper-arm part of a short-sleeved shirt has to
be the sleeve and the bare arm below its hem. The arm is the body's own part, added to the outfit's: its
vertices and its authored normals as they are, so that it still meets the body's forearm at the elbow, and its
textures as they are. Those are a tint texture (the skin's shade), a normal map and a roughness map, bound by the
material file its model names (docs/phenotype-body-material-process.md).

The part's textures are as large a side as the body's, and as twice the outfit's, to at most `limit`. The
outfit's own lie in the quarter that starts at texture coordinate 0, and the body's whole textures in the
quarter that ends at 1, at half their size or more. The body's texture coordinates are only halved and moved,
never laid out again: a normal map is read in the frame its coordinates span, and turned or sheared it would
light the skin from another side.

What the sleeve hides of the arm is left out (`shown`): the two together would be over a part's budget.
"""
from pathlib import Path

import numpy as np

from tools.headkit import native_reader

from . import export, measure, registry, seams, texture
from .registry import require

BAND = 0.04  # the arm is kept this far up under the sleeve's hem: what a look up the sleeve can reach
SECTORS = 16  # the hem is found in this many directions round the arm
APART = 0.015  # the outfit's surface in one direction, parted by more than this along the bone, is two pieces
TOP = 0.2  # a piece that begins within this share of the bone from its start comes down from the shoulder: a sleeve
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


def shown(vertices, faces, cover, own, start, end, band=BAND, sectors=SECTORS):
    """Per face of a body part, whether it is kept beside the outfit's: False where the outfit hides it.

    `cover` and `own` are the vertices and faces of the outfit on the part, what the split made included:
    its closings and walls fill the partings the cut at the shoulder leaves in a sleeve. `start` and `end`
    are the part's bone. In each of `sectors` directions round the bone the outfit covers stretches of it, its
    pieces: a stretch ends where more than `APART` of the bone has none of the outfit. A piece hides the
    body under it but for `band` at each end, which is what is seen up a sleeve that stands a centimetre
    off the arm. A piece that begins within `TOP` of the bone hides all above it too: it is the sleeve, come
    down from the shoulder under the outfit's other parts. Taken from the outfit's own faces only, the sleeve
    was parted near the shoulder and the bound had to be half the bone, so a band in the upper half was taken
    for the sleeve. A band or a pad below the hem is another piece, and the skin between the two is seen:
    the first build took the farthest point of the outfit for the hem and hid it. A vertex of the body is hidden where the outfit hides it in its own
    direction and the two beside it, and a face where all three of its vertices are."""
    start, axis = np.asarray(start, float), np.asarray(end, float) - np.asarray(start, float)
    length = float(np.linalg.norm(axis))
    axis = seams.unit(axis)
    u, w = seams.frame(axis)

    def round_bone(points):
        relative = np.asarray(points, float) - start
        turn = np.arctan2(relative @ w, relative @ u)
        return relative @ axis, np.floor((turn + np.pi) / (2 * np.pi) * sectors).astype(int) % sectors

    used, own = np.unique(np.asarray(own, int).reshape(-1, 3), return_inverse=True)
    along, sector = round_bone(measure.surface_points(np.asarray(cover, float).reshape(-1, 3)[used], own.reshape(-1, 3), APART / 3))
    pieces = [[] for _ in range(sectors)]  # per direction, the stretches of the bone the outfit covers: (from, to)
    for k in range(sectors):
        mine = np.sort(along[sector == k])
        if len(mine):
            parted = np.flatnonzero(np.diff(mine) > APART)
            pieces[k] = list(zip(mine[np.concatenate([[0], parted + 1])], mine[np.concatenate([parted, [len(mine) - 1]])]))

    def under(k, at):
        """Whether the outfit hides the body in direction `k`, per place `at` along the bone."""
        hidden = np.zeros(len(at), bool)
        for top, bottom in pieces[k % sectors]:
            top = -np.inf if top <= TOP * length else top + band
            hidden |= (at > top) & (at < bottom - band)
        return hidden

    along, sector = round_bone(vertices)
    hidden = np.zeros(len(along), bool)
    for k in range(sectors):
        mine = sector == k
        hidden[mine] = under(k, along[mine]) & under(k - 1, along[mine]) & under(k + 1, along[mine])
    return ~hidden[np.asarray(faces, int)].all(axis=1)


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

    `skin` is the body's part (`body_part`), `start` and `end` the part's bone. The maps are as large a side
    as the body's and as twice the outfit's, up to `limit`: the body's are then at half their size or more,
    whatever size the sleeve was laid out at, and the outfit's keep their texels or more, or are halved
    where the limit leaves no room. Beside a baked part's keys the result holds `skin`, per face, whether it
    is the body's; `skin_at`, per texel, whether it is of the body's textures; `skin_tint`, the body's shade
    and layer there; and `skin_rough`, the roughness of every texel, the body's map there and the outfit's
    own (`texture.ROUGHNESS`) elsewhere. The body's faces are no closing's or cap's and of no material:
    `added`, `domed` and `trimmed` say so, and their vertices have no place on the generated mesh (`src`,
    zero)."""
    size = len(part['rgb'])
    side = min(max(2 * size, len(skin['tint'])), limit)
    half = side // 2
    kept = shown(skin['v'], skin['f'], part['v'], part['f'], start, end)
    require(kept.any(), 'The outfit hides all of the body part: it needs no skin')
    used, faces = np.unique(skin['f'][kept], return_inverse=True)
    faces = faces.reshape(-1, 3) + len(part['v'])
    count = len(faces)

    def laid(mine, theirs, fill, kind='mean'):
        """A map of the part's: the outfit's in the first quarter, the body's in the last, and its edge texels
        run on through the two quarters nothing lies in. A smaller copy of the map the client makes, however
        small, then mixes nothing into the skin's edge but skin."""
        mine = np.asarray(mine)
        whole = np.full((side, side) + mine.shape[2:], fill, dtype=np.result_type(mine.dtype, np.asarray(fill).dtype))
        whole[:half, :half] = resized(mine, half, kind)
        if theirs is not None:
            block = resized(theirs, half, kind).reshape((half, half) + mine.shape[2:])
            whole[half:, half:] = block
            whole[:half, half:] = block[:1]
            whole[half:, :half] = block[:, :1]
        return whole

    flags = lambda mine: laid(np.asarray(mine, float), None, 0.0) > 0.5
    skin_at = np.ones((side, side), bool)
    skin_at[:half, :half] = False
    tint = laid(np.zeros((size, size, 2), np.uint8), None, 0)
    tint[..., 0] = np.round(laid(np.zeros((size, size)), skin['tint'][..., 0].astype(float), 0.0))
    tint[..., 1] = laid(np.zeros((size, size), np.uint8), skin['tint'][..., 1], 0, 'pick')
    return {'v': np.concatenate([part['v'], skin['v'][used]]), 'f': np.concatenate([part['f'], faces]),
            'uv': np.concatenate([np.asarray(part['uv'], float) / 2, 0.5 + skin['uv'][used] / 2]),
            'n': np.concatenate([part['n'], skin['n'][used]]), 'src': np.concatenate([part['src'], np.zeros((len(used), 3))]),
            'rgb': laid(part['rgb'], None, 0.5), 'covered': flags(part['covered']),
            'relief': laid(part['relief'], skin['relief'], np.array([0.5, 0.5, 1.0]), 'normal'),
            **{key: flags(part[key]) for key in ('closing', 'cap', 'padded')},
            **{key: np.concatenate([part[key], np.zeros(count, bool)]) for key in ('added', 'domed', 'pad') if key in part},
            'trimmed': np.concatenate([part['trimmed'], np.full(count, -1)]),
            'skin': np.concatenate([np.zeros(len(part['f']), bool), np.ones(count, bool)]), 'skin_at': skin_at, 'skin_tint': tint,
            'skin_rough': np.clip(np.round(laid(np.full((size, size), texture.ROUGHNESS), skin['rough'], texture.ROUGHNESS) * 255), 0, 255).astype(np.uint8)}
