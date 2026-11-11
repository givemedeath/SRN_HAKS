"""A part's tint texture is baked from the colours of the generated outfit the part was cut from.

Each part is laid out on its own, after the split. A texel is traced back through its face to the point of the
generated mesh it came from: the source positions ride through the cut as columns beside the normals, so a texel
of a re-posed, cut part still knows where it was on the mesh the colours were generated for. The outfit's colour
is read there. The colours are then sorted into materials over the whole outfit, so that a material is the same
tint channel on every part, and the shade follows the lightness.

A part's normal map is baked the same way from the generator's own high-detail mesh, whose relief the simplified
outfit lost: edges, seams and folds come back as light and shade (`normal_map`).

Texture rows run down from v = 0, as the game reads a tint texture (spike record, section 21): texel (row, column)
has its centre at u = (column + 0.5) / size, v = (row + 0.5) / size.
"""
from itertools import product
from pathlib import Path

import numpy as np

from tools.headkit.colour import lab
from tools.headkit.field import GeneratedField, load_generated_field
from tools.robes import mesh_ops

from . import export
from .registry import require

PAD = 4  # texels between charts, and how far a chart's colours are copied outward into the empty texels round it
MIDDLE = 170  # the shade a material's middle lightness gets; lighter and darker texels spread from there
SHADES = (30, 240)  # the shades a texel may get. Texels at the very top of the range come out black in the client: with 254
# as the limit a part's brightest edges were black marks, with 240 they are not. Where between the two it starts is not known.
BLOCKS = ((1, 3), (4, 2), (32, 2))  # a point off the colour field's shell looks in blocks of this many voxels, this many blocks round
TEXEL = 0.0015  # metres of surface a texel should span at most: finer than this the generated colours hold no more detail
COVER = 0.35  # the share of a texture its charts fill, as the layout packs a generated part
SIZES = (128, 1024)  # the smallest and the largest texture a part gets, in texels a side
LIGHT = np.array([0.2126, 0.7152, 0.0722])
BEND = 1.2  # how much lighter a raised edge and darker a crease gets, per unit the fine normal turns across a texel
SLOPE = 0.35  # how much darker a texel gets as the fine surface tilts away from the simplified one
BROAD = ((1, 1.0), (4, 0.6))  # the bend is taken across this many texels each way, with this weight: sharp edges and broad folds
RELIEF_SHADE = (0.72, 1.2)  # the least and the most the relief changes a shade by
TURN_LIMIT = 0.35  # the most one turn counts for: a jump in the map (a dropped reading beside a kept one) is not an edge that sharp


def layout(xatlas, vertices, faces, size, padding=PAD):
    """A part unwrapped into charts and packed into one square: (mapping, faces, uvs).

    `xatlas` is the loaded library; the caller resolves it, as `tools/headkit` does. A vertex on a chart's edge is
    repeated: `mapping[i]` is the given vertex that new vertex i repeats, `faces` name the new vertices and `uvs`
    are 0-1. The packing aims at `size` texels a side but is scaled to fill the square whatever it reached, so
    texels need not be square on the surface."""
    vertices, faces = np.asarray(vertices, np.float32), np.asarray(faces, np.uint32)
    atlas = xatlas.Atlas()
    atlas.add_mesh(vertices, faces)
    charts, pack = xatlas.ChartOptions(), xatlas.PackOptions()
    charts.max_iterations, charts.max_cost, charts.normal_deviation_weight = 4, 8.0, 1.0  # fewer, larger charts than the defaults
    pack.resolution, pack.padding, pack.bilinear = int(size), int(padding), True
    atlas.generate(chart_options=charts, pack_options=pack)
    require(atlas.atlas_count == 1, 'The part did not pack into one texture')
    mapping, new_faces, uvs = atlas[0]
    mapping, new_faces = np.asarray(mapping, int), np.asarray(new_faces, int)
    require(np.array_equal(vertices[mapping[new_faces]], vertices[faces.astype(int)]), 'The layout changed the part')
    return mapping, new_faces, np.asarray(uvs, float)


def size(vertices, faces):
    """The texels a side a part's texture needs: the power of two at which its surface gets a texel per `TEXEL`."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    area = float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2)
    need = np.sqrt(area / COVER) / TEXEL
    return int(np.clip(2 ** int(np.ceil(np.log2(max(need, 1.0)))), *SIZES))


def raster(uvs, faces, size):
    """(owner, weight): per texel the face covering its centre, -1 for none, and the weights of that face's
    three corners there. A face too small to cover any centre still gets the texel under its middle, if free."""
    owner, weight = np.full((size, size), -1, int), np.zeros((size, size, 3))
    corners = np.asarray(uvs, float)[np.asarray(faces, int)] * size
    for index, t in enumerate(corners):
        twice = (t[1, 1] - t[2, 1]) * (t[0, 0] - t[2, 0]) + (t[2, 0] - t[1, 0]) * (t[0, 1] - t[2, 1])
        if abs(twice) < 1e-12:
            continue
        low = np.clip(np.floor(t.min(axis=0)).astype(int), 0, size - 1)
        high = np.clip(np.ceil(t.max(axis=0)).astype(int), 0, size - 1)
        x, y = np.meshgrid(np.arange(low[0], high[0] + 1) + 0.5, np.arange(low[1], high[1] + 1) + 0.5)
        a = ((t[1, 1] - t[2, 1]) * (x - t[2, 0]) + (t[2, 0] - t[1, 0]) * (y - t[2, 1])) / twice
        b = ((t[2, 1] - t[0, 1]) * (x - t[2, 0]) + (t[0, 0] - t[2, 0]) * (y - t[2, 1])) / twice
        inside = (a >= -1e-6) & (b >= -1e-6) & (a + b <= 1 + 1e-6)
        if not inside.any():
            column, row = np.clip(t.mean(axis=0).astype(int), 0, size - 1)
            if owner[row, column] < 0:
                owner[row, column], weight[row, column] = index, 1 / 3
            continue
        row, column = np.nonzero(inside)
        owner[row + low[1], column + low[0]] = index
        weight[row + low[1], column + low[0]] = np.stack([a[inside], b[inside], 1 - a[inside] - b[inside]], axis=1)
    return owner, weight


def spread(filled, *layers, passes=PAD + 2):
    """(filled, *layers) with filled texels copied outward into empty neighbours, one texel a pass; with
    `passes` None, until no texel is empty.

    The game blends neighbouring texels; without this a chart's edge would blend with whatever lies beside it.
    Seen from afar it blends texels many at a time, so a tint texture is filled to the last texel."""
    filled, layers = np.array(filled, bool), [np.array(layer) for layer in layers]
    for _ in range(sum(filled.shape) if passes is None else passes):
        if filled.all() or not filled.any():
            break
        before, values = filled.copy(), [layer.copy() for layer in layers]  # a pass reaches the next texel only
        for axis, step in ((0, 1), (0, -1), (1, 1), (1, -1)):
            source = np.roll(before, step, axis=axis)
            border = [slice(None), slice(None)]
            border[axis] = 0 if step == 1 else -1
            source[tuple(border)] = False  # a roll wraps round; the border has no neighbour on that side
            take = source & ~filled
            for layer, value in zip(layers, values):
                layer[take] = np.roll(value, step, axis=axis)[take]
            filled |= take
    return (filled, *layers)


def colour_map(uvs, faces, positions, read, size):
    """(colour, covered, missed) for one laid-out part: the outfit's colour per texel, (size, size, 3) in 0-1.

    `positions` holds, per vertex, the point of the generated mesh it came from, in the frame `read` takes;
    `read(points)` returns (values, missed) with the colour in the first three columns. `covered` marks the
    texels a face covers; `missed` counts those `read` found no colour for, which are left uncovered."""
    faces, positions = np.asarray(faces, int), np.asarray(positions, float)
    owner, weight = raster(uvs, faces, size)
    covered = owner >= 0
    where = (weight[covered][:, :, None] * positions[faces[owner[covered]]]).sum(axis=1)
    values, missed = read(where)
    colour = np.zeros((size, size, 3))
    colour[covered] = np.asarray(values, float)[:, :3]
    covered[covered] = ~np.asarray(missed, bool)
    return colour, covered, int(np.count_nonzero(missed))


def tone(colours):
    """Colours (0-1) in the space materials are told apart in: a quarter of the Lab lightness, and the two Lab
    colour axes as shares of the lightness.

    Shading makes a texel darker and, in Lab, less coloured with it; its colour as a share of its lightness
    stays. So a tan strap's dark crease stays tan instead of drifting to the grey cloth beside it, while a pale
    plate and a mid-grey cloth, which differ mostly in lightness, are still apart."""
    value = lab(np.asarray(colours, float).reshape(-1, 3) * 255)
    light = np.maximum(value[:, 0], 10.0)  # below this a share of the lightness is noise
    return np.stack([0.25 * value[:, 0], 100 * value[:, 1] / light, 100 * value[:, 2] / light], axis=1)


def materials(colours, count, cell=6.0, apart=14.0, rounds=25, sample=200000):
    """The materials of an outfit, from the colours of all its texels: {`tones`, `colours`, `light`}, each one per material.

    A source drawn in flat tones has one heavy mode per material. The heaviest cells of the colours' histogram
    (in `tone` space) that lie at least `apart` from each other start a k-means; `tones` are its centres,
    `colours` the middle colour of each material and `light` its middle lightness. Fewer than `count` separate
    modes is an error: the source does not show that many materials."""
    colours = np.asarray(colours, float).reshape(-1, 3)
    require(len(colours), 'No texel has a colour')
    rng = np.random.default_rng(0)
    some = tone(colours[rng.choice(len(colours), min(len(colours), sample), replace=False)])
    cells, counts = np.unique(np.round(some / cell).astype(int), axis=0, return_counts=True)
    centres = []
    for index in np.argsort(-counts, kind='stable'):
        if all(np.linalg.norm(cells[index] * cell - other) > apart for other in centres):
            centres.append(cells[index] * cell)
        if len(centres) == count:
            break
    require(len(centres) == count, f'The colours show {len(centres)} materials, not {count}')
    centres = np.array(centres)
    for _ in range(rounds):
        nearest = np.argmin(np.linalg.norm(some[:, None] - centres[None], axis=2), axis=1)
        centres = np.array([some[nearest == k].mean(axis=0) if np.any(nearest == k) else centres[k] for k in range(count)])
    # A lone material's fringe can start a centre of its own; the k-means then halves that material, and the two
    # halves end up close together. Materials that close are one.
    gaps = [np.linalg.norm(centres[i] - centres[j]) for i in range(count) for j in range(i)]
    require(not gaps or min(gaps) >= apart, f'The colours do not show {count} separate materials')
    which = labels(colours, centres)
    require(all(np.any(which == k) for k in range(count)), 'A material has no texel')
    middle = np.array([np.median(colours[which == k], axis=0) for k in range(count)])
    return {'tones': centres, 'colours': middle, 'light': np.array([float(np.median(colours[which == k] @ LIGHT)) for k in range(count)])}


def labels(colours, tones):
    """The material of each colour: the nearest of the materials' `tones`."""
    return np.argmin(np.linalg.norm(tone(colours)[:, None] - np.asarray(tones, float)[None], axis=2), axis=1)


def tint_maps(colour, covered, found, channels, pad=None, relief=None, charts=None, bend=BEND, slope=SLOPE):
    """(shades, layers) of one part's tint texture, for `export.tint`.

    `found` is the outfit's `materials`; `channels[k]` names the colour channel of material k. A texel's shade is
    `MIDDLE` at its material's middle lightness and follows its own lightness from there, within `SHADES`; with
    `relief`, the part's `normal_map`, it is also lighter on raised edges and darker in creases (`relief_shade`,
    which wants the part's `chart_map` as `charts`), but a texel the colour already shows darker than its
    material is not darkened twice. Charts are spread outward until the whole texture is filled (or `pad`
    texels, if given, the rest then getting the first channel at `MIDDLE`)."""
    colour, covered = np.asarray(colour, float), np.asarray(covered, bool)
    require(len(channels) == len(found['tones']) and all(name in export.LAYERS for name in channels), 'A colour channel is needed per material')
    material, shade = np.zeros(covered.shape, int), np.full(covered.shape, float(MIDDLE))
    material[covered] = labels(colour[covered], found['tones'])
    ratio = (colour[covered] @ LIGHT) / np.maximum(found['light'][material[covered]], 1e-6)
    if relief is not None:
        # A generated colour is already darker in its creases. Where it is, the relief's darkening is not laid on
        # top of that: the texel takes the darker of the two, or a crease shaded twice comes out black.
        factor = relief_shade(relief, charts, bend, slope)[covered]
        ratio = np.maximum(factor, 1.0) * np.minimum(ratio, np.minimum(factor, 1.0) * np.maximum(ratio, 1.0))
    shade[covered] = np.clip(MIDDLE * ratio, *SHADES)
    _, material, shade = spread(covered, material, shade, passes=pad)
    return np.round(shade).astype(int), np.array([export.LAYERS[name] for name in channels])[material]


def open_field(path):
    """A saved colour field of a generated outfit (`tools/headkit/field.py`), with the blocks `read_field` falls back on.

    The field holds a colour per voxel of the generated surface's thin shell, in the generated mesh's own
    frame. Its own search for the nearest voxel needs a library this kit does not otherwise use; `read_field`
    fills such points from the blocks instead, so the search is switched off here."""
    field = load_generated_field(path, allow_decoder_overshoot=True)
    field.nearest = lambda query: np.zeros(len(query), np.int64)  # placeholders: read_field replaces every one
    return field, [(block, reach, blocks(field, block)) for block, reach in BLOCKS]


def blocks(field, block):
    """A field averaged over cubes of `block` voxels: (sorted cube keys, mean values, cubes per axis). Cubes of
    one voxel are the field's own voxels."""
    keys, side = field.keys, field.resolution
    if block == 1:
        return keys, field.attrs, side
    cubes = np.stack([keys // (side * side), keys // side % side, keys % side], axis=1) // block
    per_axis = -(-side // block)
    key = (cubes[:, 0] * per_axis + cubes[:, 1]) * per_axis + cubes[:, 2]
    order = np.argsort(key, kind='stable')
    found, start = np.unique(key[order], return_index=True)
    total = np.add.reduceat(field.attrs[order].astype(np.float64), start, axis=0)
    return found, (total / np.diff(np.append(start, len(key)))[:, None]).astype(np.float32), per_axis


def nearest_block(points, level, block, side, reach):
    """(values, found): the mean of the nearest filled cube within `reach` cubes of each point."""
    keys, mean, per_axis = level
    grid = (np.asarray(points, float) + 0.5) * side / block
    base = np.floor(grid).astype(np.int64)
    best, value = np.full(len(grid), np.inf), np.zeros((len(grid), mean.shape[1]), np.float32)
    for step in product(range(-reach, reach + 1), repeat=3):
        cube = base + np.array(step)
        key = (cube[:, 0] * per_axis + cube[:, 1]) * per_axis + cube[:, 2]
        index = np.searchsorted(keys, key).clip(max=len(keys) - 1)
        distance = np.linalg.norm(cube + 0.5 - grid, axis=1)
        take = ((cube >= 0) & (cube < per_axis)).all(axis=1) & (keys[index] == key) & (distance < best)
        best[take], value[take] = distance[take], mean[index[take]]
    return value, np.isfinite(best)


def read_field(field, levels, points):
    """(values, missed) of a colour field at points in its frame, for `colour_map`.

    A point on the shell is read between its voxels. A simplified mesh leaves the shell by a few voxels in
    places; such a point takes the nearest voxel within a few, and failing that the mean of the nearest filled
    block, small blocks first. `missed` marks the
    points with no block near them either."""
    points = np.asarray(points, np.float32)
    values, missed = field.sample(points)
    for block, reach, level in levels:
        if not missed.any():
            break
        index = np.flatnonzero(missed)
        value, found = nearest_block(points[index], level, block, field.resolution, reach)
        values[index[found]] = value[found]
        missed[index[found]] = False
    return np.clip(values, 0.0, 1.0), missed


# --- Relief: a normal map per part, from the generator's own high-detail mesh ---

TURN = 75.0  # degrees the fine surface may turn from the simplified one; past that the reading is of another surface nearby
MADE = 0.2  # a face this much smaller on the generated mesh than its part's faces are on average was made by the split
FLAT = (0.5, 0.5, 1.0)  # the colour of a texel with no relief
MATERIAL = 'renderhint NormalTangents\ntexture1 {}\nparameter float Roughness {:g}\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n'


def tensors(normals):
    """Six channels per normal (xx, yy, zz, xy, xz, yz of n n^T), which do not change when a normal is turned round."""
    n = np.asarray(normals, float)
    return np.stack([n[:, 0] * n[:, 0], n[:, 1] * n[:, 1], n[:, 2] * n[:, 2], n[:, 0] * n[:, 1], n[:, 0] * n[:, 2], n[:, 1] * n[:, 2]], axis=1)


def normal_field(vertices, faces, side=1536):
    """(field, levels) for `read_field`: the directions of a high-detail mesh's surface, per voxel of its frame.

    The generator's own mesh has millions of faces and no consistent winding, so its normals cannot simply be
    added up. Each voxel holds the area-weighted sum of its faces' `tensors`, scaled to trace 1 and with the
    last three channels shifted by a half, so that all six lie in 0-1 as a colour field's do. `side` is the
    number of voxels along the frame's unit cube."""
    vertices, faces = np.asarray(vertices, np.float32), np.asarray(faces, int)
    require(len(faces), 'The high-detail mesh has no faces')
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    normal = np.cross(b - a, c - a)
    twice = np.maximum(np.linalg.norm(normal, axis=1), 1e-30)  # twice the face's area
    cell = np.clip(np.floor(((a + b + c) / 3 + 0.5) * side).astype(np.int64), 0, side - 1)
    key = (cell[:, 0] * side + cell[:, 1]) * side + cell[:, 2]
    order = np.argsort(key, kind='stable')
    found, start = np.unique(key[order], return_index=True)
    total = np.add.reduceat((tensors(normal) / twice[:, None])[order], start, axis=0)
    total /= np.maximum(total[:, :3].sum(axis=1, keepdims=True), 1e-30)
    total[:, 3:] += 0.5
    coords = np.stack([found // (side * side), found // side % side, found % side], axis=1)
    field = GeneratedField(coords, np.clip(total, 0.0, 1.0).astype(np.float32), int(side))
    field.nearest = lambda query: np.zeros(len(query), np.int64)  # placeholders, as in open_field
    return field, [(block, reach, blocks(field, block)) for block, reach in BLOCKS]


def fine_normals(values, low, turn=TURN):
    """Unit normals of the fine surface from values read off a `normal_field`, on the side `low` faces.

    The direction is the one the tensor is largest along. Where it turns more than `turn` degrees from `low`,
    the simplified surface's own normal, `low` is kept: the reading belongs to some other surface close by."""
    value, low = np.array(values, float), np.asarray(low, float)
    value[:, 3:6] -= 0.5
    matrix = np.stack([value[:, [0, 3, 4]], value[:, [3, 1, 5]], value[:, [4, 5, 2]]], axis=1)
    fine = np.linalg.eigh(matrix)[1][:, :, 2]
    along = (fine * low).sum(axis=1)
    fine = fine * np.where(along < 0, -1.0, 1.0)[:, None]
    return np.where((np.abs(along) > np.cos(np.radians(turn)))[:, None], fine, low)


def normal_map(uvs, faces, positions, normals, posed, read, size, pad=PAD + 2):
    """(image, covered, missed): a part's normal map, (size, size, 3) in 0-1, rows running down from v = 0.

    `positions` and `normals` are the part's vertices and unit normals on the generated mesh, `posed` its
    vertices as the part is worn; `read(points)` returns (values, missed) off a `normal_field`. A texel holds
    the fine surface's normal in the simplified surface's own frame there: red along u, green along v, blue
    outward. That frame is taken on the generated mesh, where the fine surface is, and holds on the worn
    part, which was bent and widened but not sheared much. A cap or a closing was made by the split and has no
    surface of its own on the generated mesh (its vertices repeat its rim's): it stays flat, as does a texel
    nothing was read for."""
    uvs, faces = np.asarray(uvs, float), np.asarray(faces, int)
    positions, normals, posed = (np.asarray(rows, float) for rows in (positions, normals, posed))
    owner, weight = raster(uvs, faces, size)
    covered = owner >= 0
    corner, w = faces[owner[covered]], weight[covered][:, :, None]
    low = (w * normals[corner]).sum(axis=1)
    low /= np.maximum(np.linalg.norm(low, axis=1, keepdims=True), 1e-12)
    values, missed = read((w * positions[corner]).sum(axis=1))
    p, t, q = positions[faces], uvs[faces], posed[faces]
    area = lambda corners: np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    made = area(p) < MADE * area(q) * (area(p).sum() / max(area(q).sum(), 1e-30))
    fine = np.where((np.asarray(missed, bool) | made[owner[covered]])[:, None], low, fine_normals(values, low))
    e1, e2, d1, d2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]
    det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    det = np.where(np.abs(det) < 1e-20, 1e-20, det)[:, None]
    along_u = ((e1 * d2[:, 1:] - e2 * d1[:, 1:]) / det)[owner[covered]]
    along_v = ((e2 * d1[:, :1] - e1 * d2[:, :1]) / det)[owner[covered]]
    tangent = along_u - low * (low * along_u).sum(axis=1, keepdims=True)
    length = np.linalg.norm(tangent, axis=1, keepdims=True)
    tangent = tangent / np.maximum(length, 1e-12)
    other = np.cross(low, tangent)
    other *= np.where((other * along_v).sum(axis=1) < 0, -1.0, 1.0)[:, None]
    inside = np.stack([(fine * tangent).sum(axis=1), (fine * other).sum(axis=1), (fine * low).sum(axis=1)], axis=1)
    inside = np.where(length > 1e-9, inside, (0.0, 0.0, 1.0))  # no direction along u: nothing to tilt against
    image = np.empty((size, size, 3))
    image[:] = FLAT
    image[covered] = inside * 0.5 + 0.5
    return spread(covered, image, passes=pad)[1], covered, int(np.count_nonzero(missed))


def tga(image):
    """The bytes of an uncompressed 24-bit TGA from 0-1 RGB rows that run from v = 0: its first stored row is
    the picture's bottom row, which is where the game puts v = 0."""
    pixels = (np.clip(np.asarray(image, float), 0.0, 1.0) * 255 + 0.5).astype(np.uint8)
    require(pixels.ndim == 3 and pixels.shape[2] == 3 and pixels.size, 'An image is rows of RGB pixels')
    height, width = pixels.shape[:2]
    return bytes([0, 0, 2]) + bytes(9) + width.to_bytes(2, 'little') + height.to_bytes(2, 'little') + bytes([24, 0]) + pixels[:, :, ::-1].tobytes()


def write_relief(folder, model, image, roughness=0.8):
    """Write a part's normal map as `<model>n.tga` and the material file `<model>.mtr` that binds it; returns the map's name.

    The material file is named like the model's texture, so the game applies it to that part, and leaves out
    `texture0`, so the tint texture stays the part's colour (docs/phenotype-body-material-process.md)."""
    name = model + 'n'
    require(len(name) <= 16 and name == name.lower(), 'A normal map name is a lowercase resref: ' + name)
    folder = Path(folder)
    (folder / (name + '.tga')).write_bytes(tga(image))
    (folder / (model + '.mtr')).write_text(MATERIAL.format(name, roughness), encoding='ascii', newline='\n')
    return name


# --- Relief in the shade: edges and creases painted into the tint texture, where they show in any light ---


def smooth(image, radius):
    """The mean over the (2 radius + 1) texels square round each texel, the border repeated outward."""
    if radius < 1:
        return np.asarray(image, float)
    edge = ((radius + 1, radius), (radius + 1, radius)) + ((0, 0),) * (np.ndim(image) - 2)
    total = np.pad(np.asarray(image, float), edge, mode='edge').cumsum(axis=0).cumsum(axis=1)
    side = 2 * radius + 1
    return (total[side:, side:] - total[:-side, side:] - total[side:, :-side] + total[:-side, :-side]) / side ** 2


def chart_map(uvs, faces, size):
    """Per texel the number of the chart covering it, -1 for none. Faces that share a laid-out vertex are one chart."""
    faces = np.asarray(faces, int)
    label = np.asarray(mesh_ops.union_find(int(faces.max()) + 1, np.concatenate([faces[:, :2], faces[:, 1:]]).tolist()))
    owner = raster(uvs, faces, size)[0]
    return np.where(owner >= 0, label[faces[:, 0]][owner], -1)


def beside(value, chart, step, axis):
    """Each texel's neighbour `step` texels along an axis, or the texel's own value where that neighbour is
    off the texture or on another chart: across a chart's edge there is nothing to compare with."""
    same = np.roll(chart, -step, axis=axis) == chart
    border = [slice(None), slice(None)]
    border[axis] = slice(-step, None) if step > 0 else slice(None, -step)
    same[tuple(border)] = False
    return np.where(same, np.roll(value, -step, axis=axis), value)


def relief_shade(image, charts=None, bend=BEND, slope=SLOPE, broad=BROAD, limits=RELIEF_SHADE):
    """The factor a part's `normal_map` changes each texel's shade by: above 1 on a raised edge, below 1 in a
    crease and wherever the fine surface tilts away.

    The game lights these parts evenly, so a normal map alone shows little. Where the fine normal turns outward
    across a texel (it leans along u more with rising u, or along v with rising v) the surface is a ridge
    there, and where it turns inward a crease: the sum of the two turns is the bend. It is taken sharp and,
    smoothed, over a few texels, so that both a stitched edge and a fold show. With `charts` (`chart_map`) a
    texel is compared only with texels of its own chart; without, charts lying a few texels apart would read
    as bends at each other's edges."""
    image = np.asarray(image, float)
    lean, out = image[:, :, :2] * 2 - 1, image[:, :, 2] * 2 - 1
    chart = np.zeros(image.shape[:2], int) if charts is None else np.asarray(charts, int)
    inside = (chart >= 0).astype(float)
    total = np.zeros(image.shape[:2])
    for step, weight in broad:
        radius = step // 2
        soft = lean if radius < 1 else smooth(lean * inside[:, :, None], radius) / np.maximum(smooth(inside, radius), 1e-9)[:, :, None]
        for axis, channel in ((1, 0), (0, 1)):  # the lean along u across columns, the lean along v across rows
            turn = (beside(soft[:, :, channel], chart, step, axis) - beside(soft[:, :, channel], chart, -step, axis)) / 2
            total += weight * np.clip(turn, -TURN_LIMIT, TURN_LIMIT)
    return np.clip(1 + bend * total - slope * (1 - out), *limits)
