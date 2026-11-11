"""A part's tint texture is baked from the colours of the generated outfit the part was cut from.

Each part is laid out on its own, after the split. A texel is traced back through its face to the point of the
generated mesh it came from: the source positions ride through the cut as columns beside the normals, so a texel
of a re-posed, cut part still knows where it was on the mesh the colours were generated for. The outfit's colour
is read there. The colours are then sorted into materials over the whole outfit, so that a material is the same
tint channel on every part, and the shade follows the lightness.

Texture rows run down from v = 0, as the game reads a tint texture (spike record, section 21): texel (row, column)
has its centre at u = (column + 0.5) / size, v = (row + 0.5) / size.
"""
from itertools import product

import numpy as np

from tools.headkit.colour import lab
from tools.headkit.field import load_generated_field

from . import export
from .registry import require

PAD = 4  # texels between charts, and how far a chart's colours are copied outward into the empty texels round it
MIDDLE = 170  # the shade a material's middle lightness gets; lighter and darker texels spread from there
SHADES = (30, 254)  # the shades a texel may get: 255 is left unused, as in the stock palettes' last column
BLOCKS = ((1, 3), (4, 2), (32, 2))  # a point off the colour field's shell looks in blocks of this many voxels, this many blocks round
TEXEL = 0.0015  # metres of surface a texel should span at most: finer than this the generated colours hold no more detail
COVER = 0.35  # the share of a texture its charts fill, as the layout packs a generated part
SIZES = (128, 1024)  # the smallest and the largest texture a part gets, in texels a side
LIGHT = np.array([0.2126, 0.7152, 0.0722])


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
    """(filled, *layers) with filled texels copied outward into empty neighbours, one texel a pass.

    The game blends neighbouring texels; without this a chart's edge would blend with whatever lies beside it."""
    filled, layers = np.array(filled, bool), [np.array(layer) for layer in layers]
    for _ in range(passes):
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
    """Colours (0-1) as Lab with the lightness counted half: shading must weigh less than a material's own colour."""
    value = lab(np.asarray(colours, float).reshape(-1, 3) * 255)
    value[:, 0] *= 0.5
    return value


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
    which = labels(colours, centres)
    require(all(np.any(which == k) for k in range(count)), 'A material has no texel')
    middle = np.array([np.median(colours[which == k], axis=0) for k in range(count)])
    return {'tones': centres, 'colours': middle, 'light': np.array([float(np.median(colours[which == k] @ LIGHT)) for k in range(count)])}


def labels(colours, tones):
    """The material of each colour: the nearest of the materials' `tones`."""
    return np.argmin(np.linalg.norm(tone(colours)[:, None] - np.asarray(tones, float)[None], axis=2), axis=1)


def tint_maps(colour, covered, found, channels, pad=PAD + 2):
    """(shades, layers) of one part's tint texture, for `export.tint`.

    `found` is the outfit's `materials`; `channels[k]` names the colour channel of material k. A texel's shade
    is `MIDDLE` at its material's middle lightness and follows its own lightness from there. Charts are spread
    `pad` texels into the empty texels round them; what is still empty gets the first channel at `MIDDLE`."""
    colour, covered = np.asarray(colour, float), np.asarray(covered, bool)
    require(len(channels) == len(found['tones']) and all(name in export.LAYERS for name in channels), 'A colour channel is needed per material')
    material, shade = np.zeros(covered.shape, int), np.full(covered.shape, float(MIDDLE))
    material[covered] = labels(colour[covered], found['tones'])
    shade[covered] = np.clip(MIDDLE * (colour[covered] @ LIGHT) / np.maximum(found['light'][material[covered]], 1e-6), *SHADES)
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
