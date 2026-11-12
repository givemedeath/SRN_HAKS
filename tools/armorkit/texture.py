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

from . import export, split
from .registry import require

PAD = 4  # texels between charts, and how far a chart's colours are copied outward into the empty texels round it
MIDDLE = 170  # the shade a material's middle lightness gets; lighter and darker texels spread from there
SHADES = (30, 240)  # the shades a texel may get. Texels at the very top of the range come out black in the client: with 254
# as the limit a part's brightest edges were black marks, with 240 they are not. Where between the two it starts is not known.
BLOCKS = ((1, 3), (4, 2), (32, 2))  # a point off the colour field's shell looks in blocks of this many voxels, this many blocks round
TEXEL = 0.0022  # metres of surface a texel should span at most. At 0.0015, the voxel of the generated colours, a worn outfit's
# tint textures came to 19 MB; at this size they are a third of that
COVER = 0.35  # the share of a texture its charts fill, as the layout packs a generated part
SIZES = (128, 1024)  # the smallest and the largest texture a part gets, in texels a side
LIGHT = np.array([0.2126, 0.7152, 0.0722])
BEND = 1.2  # how much lighter a raised edge and darker a crease gets, per unit the fine normal turns across a texel
SLOPE = 0.35  # how much darker a texel gets as the fine surface tilts away from the simplified one
BROAD = ((1, 1.0), (4, 0.6))  # the bend is taken across this many texels each way, with this weight: sharp edges and broad folds
RELIEF_SHADE = (0.72, 1.2)  # the least and the most the relief changes a shade by
WHITE = np.array((25.0, 0.0, 0.0))  # white, as `tone` has it
PALE = 0.8  # how far toward white a material's highlights run: all the way, every material would claim a white texel alike
SAME_LINE = 6.0  # a lighter material whose shaded tone lies this near another's line toward white is that one made lighter and nothing else
SPECK = 4  # a line or a speck of one material this many texels across or less, in another, is drawn as that other: a pocket's piping, a fleck
LIT = 75  # the percentile of a material's shades that is its evenly lit surface: its creases and folds are darker, and pull the middle down
TRIM_WIDTH = 0.012  # of the outfit's height: a plate has faces this far in from its outline, and a strip of metal with none is trim
UNDER_REACH = 0.05  # metres from its edge that what the split made finds the cloth it lies under: the cloth round the opening, not the belt above it
TRIM_LEAST = 0.03  # a patch of metal less than this share of the outfit's largest is trim too, whatever its shape
CAP_STREAK = 64  # on a cap, a streak of one material narrower than a texture's side over this is taken out
ARMHOLE_SHADE = 0.55  # what closes an upper arm at the shoulder is drawn this share of its shade: it lies in the armhole's shadow
ROWS = 256  # points measured against a set of others at a time: the whole table of an outfit's faces against each other is gigabytes
KINDS = ('cloth', 'leather', 'metal')  # the kinds of material the game tints, two colour channels each
SECOND = {'cloth': ('pelvis', 'thigh', 'shin', 'foot'), 'metal': ('pelvis', 'thigh', 'shin', 'foot'),
          'leather': ('shoulder', 'bicep', 'forearm', 'hand', 'thigh', 'shin', 'foot')}
# the slots a garment is worn on that takes its kind's second channel. Leather takes it on every limb: with forearms, hands,
# shins and feet only, the straps of an upper-arm guard and a knee pad were coloured with the vest and the forearm's with the gloves
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


def materials(colours, count, cell=4.0, apart=14.0, least=0.03, rounds=25, sample=200000):
    """The materials of an outfit, from the colours of all its texels: {`tones`, `colours`, `light`}, each one per material.

    A source drawn in flat tones has one peak per material in the histogram of its colours (in `tone` space,
    cells of `cell`). Every cell belongs to the peak it climbs to, going each time to the heaviest cell beside
    it, the weights smoothed over the cells around; the `count` heaviest peaks start a k-means, each from the
    middle of what climbs to it. `tones` are the k-means' centres, `colours` the middle colour of each material
    and `light` its middle lightness, the material most of the colours belong to first. A peak with less than
    `least` of the colours is not a material, and
    fewer than `count` peaks is an error: the source does not show that many materials."""
    colours = np.asarray(colours, float).reshape(-1, 3)
    require(len(colours), 'No texel has a colour')
    rng = np.random.default_rng(0)
    some = tone(colours[rng.choice(len(colours), min(len(colours), sample), replace=False)])
    cells, inverse, counts = np.unique(np.round(some / cell).astype(int), axis=0, return_inverse=True, return_counts=True)
    index = {spot: number for number, spot in enumerate(map(tuple, cells.tolist()))}
    steps = list(product((-1, 0, 1), repeat=3))
    beside = [sorted(index[near] for near in ((x + i, y + j, z + k) for i, j, k in steps) if near in index) for x, y, z in index]
    weight = np.array([counts[near].sum() for near in beside])
    peak = np.array([near[int(np.argmax(weight[near]))] for near in beside])
    while not np.array_equal(peak, peak[peak]):
        peak = peak[peak]
    share = np.bincount(peak, weights=counts, minlength=len(cells)) / len(some)
    heaviest = [number for number in np.argsort(-share, kind='stable')[:count] if share[number] >= least]
    require(len(heaviest) == count, f'The colours show {len(heaviest)} materials, not {count}')
    mine = peak[inverse.reshape(-1)]
    centres = np.array([some[mine == number].mean(axis=0) for number in heaviest])
    for _ in range(rounds):
        nearest = np.argmin(np.linalg.norm(some[:, None] - centres[None], axis=2), axis=1)
        centres = np.array([some[nearest == k].mean(axis=0) if np.any(nearest == k) else centres[k] for k in range(count)])
    # One material can have two peaks; the k-means then halves it, and the two halves end up close together.
    # Materials that close are one.
    gaps = [np.linalg.norm(centres[i] - centres[j]) for i in range(count) for j in range(i)]
    require(not gaps or min(gaps) >= apart, f'The colours do not show {count} separate materials')
    which = labels(colours, centres)
    require(all(np.any(which == k) for k in range(count)), 'A material has no texel')
    order = np.argsort(-np.bincount(which, minlength=count), kind='stable')  # the commonest material first
    centres, which = centres[order], np.argsort(order)[which]
    middle = np.array([np.median(colours[which == k], axis=0) for k in range(count)])
    return {'tones': centres, 'colours': middle, 'light': np.array([float(np.median(colours[which == k] @ LIGHT)) for k in range(count)])}


def labels(colours, tones):
    """The material of each colour: the one whose `tones` it is nearest, or whose highlight.

    A generated colour is lit: where a plate catches the light it is paler, lighter and less coloured at
    once, and on the way to white it passes nearer a grey cloth's tone than its own. The middle of a blue
    arm guard was read as cloth, inside a rim of blue. So a colour is measured to the line from each
    material's tone toward white, `PALE` of the way along: a pale blue is a blue plate's highlight, and a
    pale warm grey is still the cloth's.

    A lighter material whose shaded texels lie on another's line is that one made lighter and nothing
    else (charcoal cloth and pale grey plates): every colour between the two was the darker one's
    highlight, and a pale plate kept only what was lighter than its tone. It is told by its tone, shaded
    halfway down to the darker one's lightness, lying within `SAME_LINE` of the line; a pale grey is not a
    blue plate's rival, though every line ends near it. A colour the darker of two such materials would
    get goes to the one of them whose tone it is nearer."""
    value, tones = tone(colours), np.asarray(tones, float)
    toward = WHITE - tones
    length = np.maximum((toward ** 2).sum(axis=1), 1e-12)
    along = np.clip(np.einsum('nmk,mk->nm', value[:, None] - tones[None], toward) / length, 0.0, PALE)
    found = np.argmin(np.linalg.norm(value[:, None] - (tones[None] + along[:, :, None] * toward[None]), axis=2), axis=1)
    shaded = np.repeat(tones[:, None], len(tones), axis=1)  # [j, m]: tone j, shaded halfway down to m's lightness
    shaded[:, :, 0] = (tones[:, None, 0] + tones[None, :, 0]) / 2
    share = np.clip(np.einsum('jmk,mk->jm', shaded - tones[None], toward) / length, 0.0, 1.0)
    lighter = (tones[:, None, 0] > tones[None, :, 0]) & (np.linalg.norm(shaded - (tones[None] + share[:, :, None] * toward[None]), axis=2) < SAME_LINE)
    if lighter.any():
        rival = lighter[:, found].T | (np.arange(len(tones))[None] == found[:, None])  # [colour, material]: its own, and those on its line
        found = np.argmin(np.where(rival, np.linalg.norm(value[:, None] - tones[None], axis=2), np.inf), axis=1)
    return found


def face_texels(uvs, faces, chosen, size):
    """(size, size) of flags: the texels on a face that `chosen` flags (one flag per face). With a row of flags
    per face, (size, size, flags in a row)."""
    owner, _ = raster(uvs, faces, size)
    picked = np.asarray(chosen, bool)[np.maximum(owner, 0)]
    return picked & (owner >= 0).reshape(owner.shape + (1,) * (picked.ndim - 2))


def face_materials(uvs, faces, colour, covered, found, size):
    """The material of each face: the one most of its texels show (`labels`), -1 for a face with no texel."""
    owner, _ = raster(uvs, faces, size)
    seen = (owner >= 0) & np.asarray(covered, bool)
    tally = np.zeros((len(faces), len(found['tones'])), int)
    np.add.at(tally, (owner[seen], labels(np.asarray(colour, float)[seen], found['tones'])), 1)
    return np.where(tally.sum(axis=1) > 0, tally.argmax(axis=1), -1)


def mesh_materials(positions, faces, read, count):
    """(material per face, materials) for an outfit's mesh before it is laid out: what `split.troughs` tells a
    shoulder pad from the sleeve by.

    `positions` holds the vertices in the frame `read` takes (`colour_map`). A face is read at its middle and
    toward each of its corners, and is of the material most of those four readings show; the materials are
    found from all the readings (`materials`). A face `read` finds no colour for is of the commonest material."""
    corners = np.asarray(positions, float)[np.asarray(faces, int)]
    points = [corners.mean(axis=1)] + [0.6 * corners[:, i] + 0.2 * corners[:, (i + 1) % 3] + 0.2 * corners[:, (i + 2) % 3] for i in range(3)]
    values, missed = read(np.concatenate(points))
    colours, seen = np.asarray(values, float)[:, :3], ~np.asarray(missed, bool)
    found = materials(colours[seen], count)
    tally = np.zeros((len(corners), count), int)
    np.add.at(tally, (np.tile(np.arange(len(corners)), 4)[seen], labels(colours[seen], found['tones'])), 1)
    return tally.argmax(axis=1), found


def nearest(points, targets, rows=ROWS):
    """(index, distance) of the nearest of `targets` for each of `points`, `rows` of them at a time."""
    points, targets = np.asarray(points, float).reshape(-1, 3), np.asarray(targets, float).reshape(-1, 3)
    index, far = np.zeros(len(points), int), np.zeros(len(points))
    for start in range(0, len(points), rows):
        apart = ((points[start:start + rows, None] - targets[None]) ** 2).sum(axis=2)
        index[start:start + rows] = apart.argmin(axis=1)
        far[start:start + rows] = np.sqrt(apart.min(axis=1))
    return index, far


def trimmed(vertices, faces, materials, metals):
    """The material per face of an outfit's mesh (`mesh_materials`), its metal trims given to what they lie on.

    A plate has an inside: faces whose middles lie `TRIM_WIDTH` of the outfit's height or more from its
    outline. Of one of `metals`, a face farther than that and its own size from every such face is trim, a
    line of metal narrower than twice that width: the frame a generator draws round a tab of cloth under a
    shoulder pad, the piping of a pocket. So is what is left of a metal in a patch of less than `TRIM_LEAST`
    of its largest, a knot of faces where a frame turns a corner. And so, twice over, is a face of what is
    left with two of its three neighbours outside it: a tooth standing out of a plate's outline, where the
    colour ends halfway into a face. A trim takes the material of the faces beside it.

    Worn, a frame was a band of metal round a patch of sleeve, a strip of it went to the shoulder part with
    the pad it touched and hung down the arm from it, and a pad was cut out along its teeth. `tint_maps`
    draws the texels of every face that is then no metal's accordingly (`trim`)."""
    v, f, materials = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(materials, int)
    require(materials.shape == (len(f),), 'One material per face is required')
    pairs, out = split.beside(v, f), materials.copy()
    area = 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    centre, width = v[f].mean(axis=1), TRIM_WIDTH * float(np.ptp(v, axis=0).max())
    weld = mesh_ops.weld_ids(v, split.WELD)
    for metal in metals:
        mine = materials == metal
        edge = pairs[mine[pairs[:, 0]] != mine[pairs[:, 1]]]
        if not mine.any() or not len(edge):
            continue
        # the outline: the edge each such pair of faces shares, as its two ends
        common = [np.isin(weld[f[a]], weld[f[b]]) for a, b in edge]
        ends = np.array([v[f[a][on]][:2] for (a, _), on in zip(edge, common) if on.sum() >= 2])
        own = np.flatnonzero(mine)
        along = ends[:, 1] - ends[:, 0]
        length, far = np.maximum((along ** 2).sum(axis=1), 1e-18), np.zeros(len(own))
        for start in range(0, len(own), ROWS):
            off = centre[own[start:start + ROWS], None] - ends[None, :, 0]
            share = np.clip(np.einsum('nek,ek->ne', off, along) / length, 0.0, 1.0)
            far[start:start + ROWS] = np.linalg.norm(off - share[:, :, None] * along[None], axis=2).min(axis=1)
        inside = own[far >= width]
        kept = np.zeros(len(f), bool)
        if len(inside):
            kept[own[nearest(centre[own], centre[inside])[1] <= width + np.sqrt(area[own])]] = True
        _, patch = np.unique(mesh_ops.union_find(len(f), pairs[kept[pairs].all(axis=1)].tolist()), return_inverse=True)
        size = np.bincount(patch, weights=np.where(kept, area, 0.0))
        kept &= size[patch] >= TRIM_LEAST * size.max()
        for _ in range(2):
            beside = pairs[kept[pairs[:, 0]] != kept[pairs[:, 1]]]
            kept &= np.bincount(np.where(kept[beside[:, :1]], beside, beside[:, ::-1])[:, 0], minlength=len(f)) < 2
        left = mine & ~kept
        for _ in range(len(f)):  # from the faces beside it inward
            near = pairs[left[pairs[:, 0]] != left[pairs[:, 1]]]
            near = np.where(left[near[:, :1]], near, near[:, ::-1])  # [a trim's face, the face beside it]
            near = near[out[near[:, 1]] != metal]
            if not len(near):
                break
            out[near[:, 0]] = out[near[:, 1]]
            left[near[:, 0]] = False
        out[left] = np.bincount(materials[~mine], minlength=1).argmax() if (~mine).any() else metal
    return out


def soft_map(uvs, faces, positions, read, size):
    """The outfit's colour per texel, (size, size, 3), read at the part's vertices only and spread evenly
    over each face between them: `colour_map` without anything smaller than a face. For what the split
    made and a stride shows much of (`under`)."""
    values = np.asarray(read(np.asarray(positions, float))[0], float)[:, :3]
    return colour_map(uvs, faces, values, lambda where: (where, np.zeros(len(where), bool)), size)[0]


def under(vertices, faces, made, outfit, cloth, kind=split.CAP, reach=UNDER_REACH):
    """Where a part's cap lies under the outfit: the part's vertices that only its cap's faces use, and for
    each the nearest of the `outfit`'s vertices that `cloth` flags, among those within `reach` of the cap's
    edge. `kind` is what made the faces meant, one kind or several: `split.CAP`, with `split.WALL` for a
    thigh's inner wall, or `split.CLOSING` for the lid over an opening.

    A cap repeats its rim's colours toward its pole, and `tint_maps` draws it in one shade (`cap`): right
    for a cap a bend shows a sliver of. A thigh's cap is the top of the trouser leg, a stride turns a
    hand's breadth of it out of the pelvis, and drawn so it was a flat pale patch in the crotch at every
    step; the pelvis's lids over its hip openings are the other half of that patch, where the thigh has
    turned back out of the opening. Give such a cap's vertices the source positions of the outfit's
    vertices they lie under, draw its texels from `soft_map`, and leave its faces out of `tint_maps`' `cap`
    or `closing`: it is then shaded as the cloth round it is, from its own edge inward. Baked with
    `colour_map`, it took whatever lay between those vertices' places in the outfit, and the seat showed
    patches of a strap's tan. `cloth` flags the outfit's vertices that are of the part's commonest
    material and show its colour, and `reach` keeps to the cloth round the opening: the middle of a cap
    lies deep under the surface, as near the belt as the seat. `made` is what made each face (`split.split`)."""
    v, f, made = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(made, int)
    outfit, cloth = np.asarray(outfit, float), np.asarray(cloth, bool)
    require(made.shape == (len(f),) and cloth.shape == (len(outfit),), 'One kind per face and one flag per vertex of the outfit are required')
    meant = np.isin(made, kind)
    only = np.setdiff1d(f[meant], f[~meant])
    if not len(only):
        return only, only
    require(cloth.any(), 'The outfit has no vertex the cap may lie under')
    allowed, edge = np.flatnonzero(cloth), v[np.intersect1d(f[meant], f[~meant])]
    if len(edge):
        close = nearest(outfit[allowed], edge)[1] <= reach
        allowed = allowed[close] if close.any() else allowed
    return only, allowed[nearest(v[only], outfit[allowed])[0]]


def edge_materials(material, closing, least=0.25):
    """The materials other than the first that a part shows along its cut edge: those `least` or more of its
    closings' texels were read as, a closing being coloured from its edge. `material` holds a material per
    texel (-1 for none), `closing` flags the closings' texels."""
    along = np.asarray(material)[np.asarray(closing, bool) & (np.asarray(material) >= 0)]
    share = np.bincount(along, minlength=1) / max(len(along), 1)
    return [k for k in range(1, len(share)) if share[k] >= least]


def overlaid(vertices, faces, material, closing, others):
    """Flags per face: a limb's faces that show what the torso wears over it.

    Where an arm rests against a vest, the generated outfit has one surface, and it is the vest's: cut off, the
    sleeve's side toward the torso is the vest's colour, and shows it once the arm lifts. `material` is the
    material per face (`face_materials`), `closing` flags the closings, `others` are the materials the torso
    shows along the same cut (`edge_materials` of the chest). A patch of one of those materials, faces joined
    edge to edge, that reaches a closing is flagged: it runs on across the cut as the torso's garment. A cap
    repeats its rim's colours and is part of the patch its rim is in. A patch that does not reach the cut (a
    strap round the arm) is the limb's own. Drawn with the closings (`tint_maps`), the flagged faces get the
    outfit's cloth."""
    faces, material = np.asarray(faces, int), np.asarray(material)
    closing = np.asarray(closing, bool)
    weld = mesh_ops.weld_ids(np.asarray(vertices, float), 1e-5)
    flagged = np.zeros(len(faces), bool)
    at_cut = np.zeros(int(weld.max()) + 1, bool)
    at_cut[weld[faces[closing]]] = True
    for other in others:
        mine = np.flatnonzero(~closing & (material == other))
        if not len(mine):
            continue
        corners = weld[faces[mine]]
        edges = np.sort(np.concatenate([corners[:, [0, 1]], corners[:, [1, 2]], corners[:, [2, 0]]]), axis=1)
        face = np.tile(np.arange(len(mine)), 3)
        order = np.lexsort((edges[:, 1], edges[:, 0]))
        edges, face = edges[order], face[order]
        same = (edges[1:] == edges[:-1]).all(axis=1)
        patch = mesh_ops.union_find(len(mine), zip(face[:-1][same].tolist(), face[1:][same].tolist()))
        reaches = np.unique(patch[at_cut[corners].any(axis=1)])
        flagged[mine[np.isin(patch, reaches)]] = True
    return flagged


def channels(kinds):
    """The two colour channels of each material, [(first, second)], from the kind of each (`KINDS`), the
    commonest material first as `materials` has them.

    The game tints six channels, two of each kind, and an outfit is to use them all. One that shows one
    material of a kind has both of that kind's channels for it: its garments worn on the slots of `SECOND`
    take the second (`worn_second`), so that trousers are coloured apart from the shirt, leg plates from arm
    plates, and boots, gloves and the straps on arms and legs from the vest. Where the colours show two materials of a kind, each has a channel
    to itself, the commoner the first. A third of a kind has no channel and is an error."""
    kinds = list(kinds)
    require(kinds and all(kind in KINDS for kind in kinds), f'A material is one of {KINDS}')
    require(all(kinds.count(kind) <= 2 for kind in kinds), 'The game tints two channels of a kind')
    return [(kind + '1', kind + '2') if kinds.count(kind) == 1 else (kind + str(1 + kinds[:index].count(kind)),) * 2
            for index, kind in enumerate(kinds)]


def worn_second(positions, faces, materials, slots, kinds, second=SECOND):
    """Flags (face, material): whether material k, where it shows on face i, takes its second colour channel
    (`channels`).

    The outfit's colours tell materials apart, not garments: a shirt and trousers of one cloth are one
    material. Garments are told as patches, faces of one material joined edge to edge (vertices at one
    position being one point). A patch ends where another material lies across it: a vest between shirt and
    trousers, a cuff between sleeve and glove. It is worn on the slot most of its area lies on, and takes the
    second channel if `second` lists that slot for its material's kind. Decided per part instead, the colour
    would change along the joint planes, across a garment.

    `positions` and `faces` are the outfit's own faces from all its parts together, without what the split
    added, in the frame the outfit came in, where the two sides of every cut still meet. `materials` holds a
    material per face (`face_materials`, -1 for none), `slots` the slot of the part each face is on, `kinds`
    the kind of each material.

    A texel is of the material its own colour shows, so along a patch's edge texels of one material lie on
    faces of the other. A face therefore answers for every material: for one it is not of as a patch of that
    material beside it does, and where there is none as the slot the face itself is on would. (Not as its own
    patch's slot would: a strap too thin to have faces of its own lies on a sleeve, and the sleeve's shirt is
    worn on the chest, so the strap was coloured with the vest.) A material whose patches
    would all take the second channel takes the first: an outfit with one garment of a kind is coloured by
    that kind's first channel."""
    positions, faces, materials = np.asarray(positions, float), np.asarray(faces, int), np.asarray(materials, int)
    names, slot = np.unique(np.asarray(slots), return_inverse=True)
    slot = slot.reshape(-1)
    require(len(materials) == len(faces) == len(slot) and len(faces), 'A material and a slot per face are required')
    require(materials.max() < len(kinds) and all(kind in second for kind in kinds), 'Every material needs a kind')
    a, b = split.beside(positions, faces).T
    same = (materials[a] == materials[b]) & (materials[a] >= 0)
    patch = mesh_ops.union_find(len(faces), zip(a[same].tolist(), b[same].tolist()))
    corners = positions[faces]
    area = 0.5 * np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    member = np.unique(patch, return_inverse=True)[1].reshape(-1)
    tally = np.zeros((member.max() + 1, len(names)))
    np.add.at(tally, (member, slot), area)
    home = tally.argmax(axis=1)[member]  # per face, the slot its patch is worn on
    listed = np.array([[name in second[kind] for name in names] for kind in kinds])  # (material, slot)
    flags = listed[:, slot].T.copy()  # a material a face is not of: as the slot the face is on says, unless a patch of it is beside
    read = materials >= 0
    flags[read, materials[read]] = listed[materials[read], home[read]]  # its own material: as the slot its patch is worn on
    for face, other in ((a, b), (b, a)):
        differ = (materials[face] != materials[other]) & (materials[other] >= 0)
        flags[face[differ], materials[other[differ]]] = listed[materials[other[differ]], home[other[differ]]]
    for k in range(len(kinds)):
        if flags[materials == k, k].all():
            flags[:, k] = False
    return flags


def added_second(vertices, faces, added, flags):
    """`worn_second`'s flags for every face of one part: those of the faces the split `added` (its closings and
    caps) are taken from the own faces they grew from, ring by ring. `flags` has a row per face of the part;
    the rows of the added faces are not read. A closing is drawn in the outfit's commonest material
    (`tint_maps`), and so in the channel that material has on the edge it closes."""
    faces, known = np.asarray(faces, int), ~np.asarray(added, bool)
    flags = np.array(flags, bool)
    require(known.shape == (len(faces),) and len(flags) == len(faces), 'One flag and one row per face are required')
    flags[~known] = False
    a, b = split.beside(vertices, faces).T
    while True:
        reach = known[a] != known[b]
        if not reach.any():
            return flags
        source, target = np.where(known[a[reach]], a[reach], b[reach]), np.where(known[a[reach]], b[reach], a[reach])
        flags[target] = flags[source]
        known[target] = True


def lit_shades(colours, found):
    """The shade of each material's evenly lit surface, from the colours of the outfit's own texels (`tint_maps`, `lit`)."""
    colours = np.asarray(colours, float).reshape(-1, 3)
    material = labels(colours, found['tones'])
    shade = np.clip(MIDDLE * (colours @ LIGHT) / np.maximum(found['light'][material], 1e-6), *SHADES)
    return np.array([np.percentile(shade[material == k], LIT) if (material == k).any() else float(MIDDLE) for k in range(len(found['tones']))])


def tint_maps(colour, covered, found, channels, pad=None, relief=None, charts=None, bend=BEND, slope=SLOPE, closing=None, second=None, cap=None, padded=None, lit=None, speck=SPECK, trim=None, shadow=None):
    """(shades, layers) of one part's tint texture, for `export.tint`.

    `found` is the outfit's `materials`; `channels[k]` names the colour channel of material k, or its two
    (`channels`), the second of which a texel takes where `second` flags it for its material: (size, size,
    materials), `face_texels` of the part's `worn_second` flags. A texel's shade is
    `MIDDLE` at its material's middle lightness and follows its own lightness from there, within `SHADES`; with
    `relief`, the part's `normal_map`, it is also lighter on raised edges and darker in creases (`relief_shade`,
    which wants the part's `chart_map` as `charts`), but a texel the colour already shows darker than its
    material is not darkened twice. Charts are spread outward until the whole texture is filled (or `pad`
    texels, if given, the rest then getting the first channel at `MIDDLE`).

    `closing` flags the texels of the part's closings (`face_texels` of the faces `split.split` reports as
    `CLOSING`). A closing has no surface of its own on the generated outfit; its colours are those of its
    edge, which runs along creases and through whatever lies over the limb where it left the torso. It gets
    the outfit's commonest material, the first of `found`: the cloth the outfit is made of. Left as read, a
    sleeve's closing was a vest's colour, most of its edge being cut through the vest. Its shade is its
    edge's, evened out over the closing, and no lighter than the cloth's lit shade: a closing lies in the
    crease it was cut along, and at the lit shade the slivers of one that stand in an armpit as the body
    rests were pale flecks in the shadow there. The texels of a limb's `overlaid` faces are flagged with
    them and drawn the same way.

    `shadow` flags the closing's texels that lie in an armhole: an upper arm's closings (`bake.ARMHOLE`).
    They are drawn at `ARMHOLE_SHADE` of that shade, and no darker than the darkest shade a texel may get.
    The game stands a body with its arms turned a little out of the pose the outfit was cut in, the
    sleeve's rim then stands off the chest's edge on one side, and what closes the sleeve shows in the gap
    between the two: as a pale strip at the shade of the sleeve's lit shoulder, and as the shadow under the
    chest's edge at this one. The sleeve's cap shows there too; drawing it in from its rim does not close
    the gap (at half the rim's width a quarter less of it showed), and `bake.roles` says how it is drawn.

    `cap` flags the texels of the part's cap (the faces reported as `CAP`). A cap repeats its rim's colours
    toward its pole, and shows in the gap a bent joint opens: it is what its rim is, the pad over a knee and
    the trousers behind it. Where the rim runs in and out of two materials, a sleeve and the edge of the
    guard strapped over it, the cap was streaked with both. Each of its texels takes the material most of
    the cap's texels show within a texture's side over `CAP_STREAK` of it: a streak goes, a pad stays. All
    the cap's texels of one material then get one shade, its lit shade. The rim's light and dark
    were repeated toward the pole with its colours, a stripe to each face, and the top of a thigh that a
    crouch turns out of the pelvis was a fan of flat facets; evenly shaded, it is lit round by its normals.

    `lit[k]` is the shade of material k where nothing shades it (`lit_shades` of the whole outfit); without
    it, the `LIT` percentile of the part's own texels of the material, or `MIDDLE` where it has none. What
    the split made has no shading of its own and gets this shade. The middle shade is too dark for it: a
    generated colour is darker in every crease and fold, and at the middle shade, let alone its rim's mean
    (a rim lies in the crease of its joint), the top of a thigh stood out of the seat of the trousers as a
    darker patch with straight edges.

    On the part's own surface, a line or a speck of one material `speck` texels across or less, in another,
    is drawn as that other, at the shade of that material's texels round it: most of the texels within
    `speck` decide. A generator pipes a sleeve pocket in the plates' colour and flecks a sleeve with it;
    worn, that is a patch of cloth in a wire of metal, and mottling. The texels of every chart within
    `speck` decide alike: keep it no wider than the charts stand apart (`PAD`, `layout`), or a narrow chart
    is outvoted by the one laid out beside it.

    `trim` holds, for the texels of the faces that are no metal's (as `trimmed` left them), the material
    of their face, and -1 elsewhere. A texel there that shows a metal is drawn in that material, at its own
    shade: a plate is drawn on its own faces and nowhere else, and the vote within `speck` does not give
    such a texel to a metal either, however much of one lies round it. The colours of a frame one face wide are
    still on its faces; the colour of a plate runs over its outline into the faces beside it, in blots
    and tails, and a shoulder pad that goes whole to the shoulder part along its faces' edges
    (`split.pad`) left that on the sleeve, where the arm carried it out from under the pad.
    A thigh's closing toward the other leg (`split.WALL`) is flagged with its
    cap, not as a closing: its rim is the trousers' own, and drawn as that it does not stand out beside the
    crotch.

    `padded` flags the texels of a cap that grew from a pad's rim (the faces reported as `PADDED`). On a cap
    that has any, the others are the limb beside the pad, and are drawn as the outfit's cloth, the first of
    `found`: a pad's strap runs round the joint along the rim, and read as its rim the side of a knee's cap
    was a flat triangle of webbing in the gap the bend opens."""
    colour, covered = np.asarray(colour, float), np.asarray(covered, bool)
    pairs = [(name, name) if isinstance(name, str) else tuple(name) for name in channels]
    require(len(pairs) == len(found['tones']) and all(len(pair) == 2 and all(name in export.LAYERS for name in pair) for pair in pairs),
            'A colour channel is needed per material')
    material, shade = np.zeros(covered.shape, int), np.full(covered.shape, float(MIDDLE))
    material[covered] = labels(colour[covered], found['tones'])
    ratio = (colour[covered] @ LIGHT) / np.maximum(found['light'][material[covered]], 1e-6)
    if relief is not None:
        # A generated colour is already darker in its creases. Where it is, the relief's darkening is not laid on
        # top of that: the texel takes the darker of the two, or a crease shaded twice comes out black.
        factor = relief_shade(relief, charts, bend, slope)[covered]
        ratio = np.maximum(factor, 1.0) * np.minimum(ratio, np.minimum(factor, 1.0) * np.maximum(ratio, 1.0))
    shade[covered] = np.clip(MIDDLE * ratio, *SHADES)
    if trim is not None:
        trim = np.asarray(trim, int)
        require(trim.shape == covered.shape and trim.max() < len(pairs), 'A material per texel, or -1, is required')
        metal = np.array([pair[0].startswith('metal') for pair in pairs])
        swap = covered & (trim >= 0) & metal[material]
        material[swap] = trim[swap]
    for name, flags in (('shadow', shadow), ('padded', padded)):
        require(flags is None or np.shape(flags) == covered.shape, f'`{name}` is one flag per texel')
    require(lit is None or len(lit) == len(pairs), 'A lit shade per material is required')
    plain = covered & np.asarray(closing, bool) if closing is not None else np.zeros(covered.shape, bool)
    dome = covered & np.asarray(cap, bool) & ~plain if cap is not None else plain & False
    worn = covered & ~plain & ~dome  # the part's own surface
    votes = np.stack([smooth(worn & (material == k), speck) for k in range(len(pairs))])
    most = np.argmax(votes, axis=0)
    moved = worn & (most != material)
    if trim is not None:  # a face that is no metal's gets none back from the texels round it
        moved &= ~((trim >= 0) & metal[most])
    for k in np.unique(most[moved]):
        mine = moved & (most == k)
        shade[mine] = (smooth(np.where(worn & (material == k), shade, 0.0), speck) / np.maximum(votes[k], 1e-9))[mine]
    material[moved] = most[moved]

    def even(k):  # the one shade what the split made gets, in material k
        mine = worn & (material == k)
        return float(lit[k]) if lit is not None else float(np.percentile(shade[mine], LIT)) if mine.any() else float(MIDDLE)
    if plain.any():  # as dark as the edge it grew from, evened out, and no lighter than the cloth's open surface
        reach = max(1, covered.shape[0] // CAP_STREAK)
        local = smooth(np.where(plain, shade, 0.0), reach) / np.maximum(smooth(plain, reach), 1e-9)
        material[plain], shade[plain] = 0, np.minimum(local, even(0))[plain]
        if shadow is not None:
            dark = plain & np.asarray(shadow, bool)
            shade[dark] = np.maximum(shade[dark] * ARMHOLE_SHADE, SHADES[0])
    if padded is not None and (dome & np.asarray(padded, bool)).any():
        beside = dome & ~np.asarray(padded, bool)
        material[beside], shade[beside] = 0, even(0)
        dome = dome & ~beside
    if dome.any():
        reach = max(1, covered.shape[0] // CAP_STREAK)
        settled = np.argmax([smooth(dome & (material == k), reach) for k in range(len(pairs))], axis=0)
        for k in np.unique(settled[dome]):
            shade[dome & (settled == k)] = even(k)
        material[dome] = settled[dome]
    other = np.zeros(covered.shape, int)
    if second is not None:
        second = np.asarray(second, bool)
        require(second.shape == covered.shape + (len(pairs),), 'A flag per texel and material is required')
        other[covered] = np.take_along_axis(second, material[:, :, None], axis=2)[:, :, 0][covered]
    layer = np.array([[export.LAYERS[name] for name in pair] for pair in pairs])[material, other]
    _, layer, shade = spread(covered, layer, shade, passes=pad)
    return np.round(shade).astype(int), layer


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


def normal_map(uvs, faces, positions, normals, posed, read, size, pad=PAD + 2, added=None):
    """(image, covered, missed): a part's normal map, (size, size, 3) in 0-1, rows running down from v = 0.

    `positions` and `normals` are the part's vertices and unit normals on the generated mesh, `posed` its
    vertices as the part is worn; `read(points)` returns (values, missed) off a `normal_field`. A texel holds
    the fine surface's normal in the simplified surface's own frame there: red along u, green along v, blue
    outward. That frame is taken on the generated mesh, where the fine surface is, and holds on the worn
    part, which was bent and widened but not sheared much. A cap or a closing was made by the split and has no
    surface of its own on the generated mesh (its vertices repeat its rim's): it stays flat, as does a texel
    nothing was read for. `added` flags the faces the split made (`split.split`, `made`: all but `OWN` and
    `GUSSET`). Without it they are told by being much smaller on the generated mesh than worn, which holds for
    a cap and a rounded closing but not for a flat one: a lid or a wall spans its opening from rim to rim, is
    as large there as worn, and was given the relief of whatever lies inside the limb at that place."""
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
    if added is not None:
        require(np.shape(added) == (len(faces),), 'One flag per face is required')
        made = made | np.asarray(added, bool)
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


def halved(image):
    """An image at half its size each way: each texel the mean of two by two. A normal map shows little in the
    game's even light once its relief is in the tint shade, and at half size it costs a quarter."""
    image = np.asarray(image, float)
    rows, columns = image.shape[0] // 2 * 2, image.shape[1] // 2 * 2
    return image[:rows, :columns].reshape(rows // 2, 2, columns // 2, 2, -1).mean(axis=(1, 3))


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
