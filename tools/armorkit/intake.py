"""An outfit made outside the kit's own generator, taken in for the bake: a textured mesh file turned into the
three files a bake reads, the mesh it cuts, the colour field and the fine surface its relief comes from.

The first such outfits are Meshy exports: one static mesh a file, about 10,000 triangles, y up, with texture
coordinates, a base colour texture and a metallic-roughness texture, no skeleton and no normal map. Three
things keep such a file from the bake as it stands, and `prepare` answers each without changing the bake:

* Its colours are a painted texture. The bake tells an outfit's materials apart by colour and keeps of a texel
  only how light it is for its material; a painted outfit is blacks, greys and browns. An intake document
  (`validate`) names the outfit's materials and the colours and metal of the texture each is told by; `flat`
  draws the texture again with every material in one flat colour and its own shading, and `colour_field`
  stores that round the surface as the kit's generator stores its colours.
* Its mesh is not one closed surface: sheets joined along shared edges, with open loops. `wrap` draws the
  surface again, closed, from the signed distance to it.
* It carries body skin (fingertips, bare arms, hands). The document says what skin looks like and which
  material it is drawn as; a slot left to the body is the brief's `bare`.

`load` reads a file and `views` draws it with its own texture, for a survey of what a file holds before any of
it is baked.
"""
import hashlib
import io
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from tools.headkit import gltf
from tools.robes import mesh_ops

from . import brief as briefs
from . import seams, texture
from .registry import require

KIND = 'srn-armorkit-intake'
KEYS = {'schemaVersion', 'kind', 'model', 'source', 'materials', 'skin', 'bare', 'faces'}
SIDE = 4096  # texels a side of the largest texture `load` reads whole: a larger one is refused
VIEWS = {'front': (0.0, -1.0, 0.0), 'side': (-1.0, 0.0, 0.0), 'back': (0.0, 1.0, 0.0)}  # the way each view looks, in the bodies' axes
METAL = 40.0  # how far apart, in Lab units, a texel that is all metal and one that is none are sorted (`features`)
SETTLE = 6  # texels of a texture `SIDE` a side: a texel is of the material most texels within this of it have (`settled`)
SAMPLES = 400000  # points of the surface a material's share and middle lightness are measured on
LEAST = 0.03  # a material has this share of the surface at least: `texture.materials` finds none smaller
SOFT = 0.05  # added to a texel's lightness and to its material's middle before the two are compared: a black cloth's noise is not shading
SHADE = (0.2, 1.5)  # the least and the most a texel is drawn lighter than its material's flat colour
# The flat colours materials are drawn in for the bake, by kind, the first of a kind first: hues well apart
# (`brief.APART`), and dim enough that `SHADE`'s lightest stays a colour.
PALETTE = {'cloth': ((110, 110, 110), (84, 130, 84)), 'leather': ((160, 130, 90), (150, 82, 68)), 'metal': ((98, 138, 188), (144, 98, 176))}
FILL = 0.95  # the share of the field's unit cube the mesh's longest side is scaled to
VOXEL = 0.00215  # of the field's frame: the grid the surface is drawn again on, about 4 mm of a worn outfit
OFFSET = 0.0011  # of the field's frame: how far outside the given faces the rebuilt surface lies, about 2 mm
FACES = 20000  # triangles the rebuilt mesh is brought down to
SMOOTHING = 5  # steps the fine surface is smoothed by, without shrinking
PIECE = 1e-4  # a piece of the rebuilt surface with less than this share of the largest's volume is left out
GRID = 60_000_000  # points of the grid at most
RESOLUTION = 1024  # voxels a side of the colour field: 1.8 mm of a worn outfit, finer than a part's texels
ROWS = 256  # points measured against every face at a time, without a library


def _image(document, binary, entry):
    """The image a material's texture entry names, as an RGB array, or None for no entry."""
    if entry is None:
        return None
    source = document['images'][document['textures'][entry['index']]['source']]
    require('bufferView' in source, 'An intake mesh holds its textures: one that names a file beside it is not read')
    view = document['bufferViews'][source['bufferView']]
    start = view.get('byteOffset', 0)
    with Image.open(io.BytesIO(binary[start:start + view['byteLength']])) as image:
        require(max(image.size) <= SIDE, f'A texture of {image.size[0]} by {image.size[1]} texels is larger than {SIDE} a side')
        return np.asarray(image.convert('RGB'))


def load(path):
    """A textured mesh file as the bake reads an outfit: {`vertices`, in the bodies' axes (z up, facing +y, as
    `repose.load` turns them) and not welded, a vertex per corner of the texture layout; `faces`; `uv`, per
    vertex, v counted down from the image's first row as glTF counts it; `colour`, the base colour texture as
    RGB; `rough` and `metal`, the roughness and metallic channels of its other texture, or None without one}.

    The file is one mesh with one material, as `tools.headkit.gltf` reads it: a skeleton, a moved node or a
    second material is refused there. A mesh without texture coordinates or a base colour texture is refused
    here: the bake has nothing else to read its colours from."""
    document, binary, primitive = gltf.load(Path(path).read_bytes())
    points, faces, attributes = gltf.arrays(document, binary, primitive)
    require('TEXCOORD_0' in attributes and 'material' in primitive, f'{path} has no texture coordinates or no material')
    shading = document['materials'][primitive['material']].get('pbrMetallicRoughness', {})
    colour = _image(document, binary, shading.get('baseColorTexture'))
    require(colour is not None, f'{path} has no base colour texture')
    other = _image(document, binary, shading.get('metallicRoughnessTexture'))
    points = np.asarray(points, float)
    return {'vertices': np.stack([-points[:, 0], points[:, 2], points[:, 1]], axis=1), 'faces': np.asarray(faces, np.int64),
            'uv': np.asarray(attributes['TEXCOORD_0'], float), 'colour': colour,
            'rough': None if other is None else other[:, :, 1], 'metal': None if other is None else other[:, :, 2]}


def texels(image, uv):
    """The texels of `image` at texture coordinates `uv` (..., 2), the nearest each, coordinates past an edge held to it."""
    height, width = image.shape[:2]
    column = np.clip((np.asarray(uv)[..., 0] * width).astype(int), 0, width - 1)
    row = np.clip((np.asarray(uv)[..., 1] * height).astype(int), 0, height - 1)
    return image[row, column]


def view(mesh, direction, size=520, margin=1.04, up=(0.0, 0.0, 1.0)):
    """An orthographic view of a loaded mesh along `direction`, drawn with its own base colour texture and no
    light: an RGB array `size` high, white where nothing is. Both sides of a face are drawn."""
    v, f, uv = mesh['vertices'], mesh['faces'], mesh['uv']
    d = np.asarray(direction, float) / np.linalg.norm(direction)
    right = np.cross(d, np.asarray(up, float))
    right /= np.linalg.norm(right)
    upward = np.cross(right, d)
    centre = (v.min(axis=0) + v.max(axis=0)) / 2
    scale = size / (margin * np.ptp(v @ upward))
    relative = v - centre
    x, y, z = relative @ right * scale + size / 2, size / 2 - relative @ upward * scale, relative @ d
    image = np.full((size, size, 3), 255, np.uint8)
    depth = np.full((size, size), np.inf)
    for a, b, c in f:
        xs, ys = np.array([x[a], x[b], x[c]]), np.array([y[a], y[b], y[c]])
        x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), size - 1)
        y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), size - 1)
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if x0 > x1 or y0 > y1 or abs(den) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
        l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        l2 = 1 - l0 - l1
        nearer = l0 * z[a] + l1 * z[b] + l2 * z[c]
        region = depth[y0:y1 + 1, x0:x1 + 1]
        better = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6) & (nearer < region)
        if better.any():
            region[better] = nearer[better]
            at = l0[better, None] * uv[a] + l1[better, None] * uv[b] + l2[better, None] * uv[c]
            image[y0:y1 + 1, x0:x1 + 1][better] = texels(mesh['colour'], at)
    return image


def views(mesh, size=520, directions=VIEWS):
    """The views of `VIEWS` of a loaded mesh side by side: one RGB array."""
    return np.concatenate([view(mesh, direction, size) for direction in directions.values()], axis=1)


# --- The texture sorted into the outfit's materials, and drawn as the kit's own generator draws them ---

def features(colour, metal=None):
    """Texels in the space they are sorted in: the three Lab axes of a colour (0-255) and `METAL` times how
    metallic it is (0-1, none without a metallic texture)."""
    colour = np.asarray(colour, float).reshape(-1, 3)
    metal = np.zeros(len(colour)) if metal is None else np.asarray(metal, float).reshape(-1)
    return np.concatenate([texture.lab(colour), METAL * metal[:, None]], axis=1)


def anchors(document):
    """(features, material) of every anchor an intake document lists: the materials in order, then the skin's,
    numbered one past the last material."""
    listed = [(anchor, number) for number, material in enumerate(document['materials']) for anchor in material['anchors']]
    listed += [(anchor, len(document['materials'])) for anchor in document.get('skin', {}).get('anchors', [])]
    return (np.concatenate([features([anchor['colour']], [anchor.get('metal', 0.0)]) for anchor, _ in listed]),
            np.array([number for _, number in listed]))


def sort(mesh, document, rows=1 << 20):
    """The material of every texel of a loaded mesh's base colour texture, as an intake document's anchors tell
    them: (height, width) of numbers into its materials, the skin's one past the last. A texel is of the anchor
    nearest it in `features`' space."""
    spots, material = anchors(document)
    colour = mesh['colour'].reshape(-1, 3)
    metal = None if mesh['metal'] is None else mesh['metal'].reshape(-1) / 255.0
    found = np.zeros(len(colour), np.uint8)
    for start in range(0, len(colour), rows):
        value = features(colour[start:start + rows], None if metal is None else metal[start:start + rows])
        found[start:start + rows] = material[((value[:, None] - spots[None]) ** 2).sum(axis=2).argmin(axis=1)]
    return found.reshape(mesh['colour'].shape[:2])


def islands(mesh):
    """The texels of a loaded mesh's texture that lie on a face: (height, width) of flags."""
    height, width = mesh['colour'].shape[:2]
    image = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(image)
    for corners in (mesh['uv'][mesh['faces']] * (width, height)).tolist():
        draw.polygon([tuple(corner) for corner in corners], fill=1, outline=1)
    return np.asarray(image, bool)


def settled(found, on, count, reach):
    """Materials per texel (`sort`) with each texel on a face (`on`) given the material most of the texels on
    faces within `reach` of it have, a square of them. A painted texture lightens every worn edge of a strap,
    a pouch or a boot, and sorted texel by texel those lines, lighter than the cloth they are on, went to the
    grey plates: the outfit was outlined in plate. Texels off the faces do not vote, so the empty texture
    between two islands, which is some colour too, turns nothing at an island's edge."""
    if reach < 1:
        return found
    best, most = np.zeros(found.shape, np.int32), np.zeros(found.shape, np.uint8)
    for material in range(count):
        total = np.pad(np.cumsum(np.cumsum(on & (found == material), axis=0, dtype=np.int32), axis=1, dtype=np.int32), ((1, 0), (1, 0)))
        rows, columns = np.arange(found.shape[0]), np.arange(found.shape[1])
        top, bottom = np.maximum(rows - reach, 0), np.minimum(rows + reach + 1, found.shape[0])
        left, right = np.maximum(columns - reach, 0), np.minimum(columns + reach + 1, found.shape[1])
        votes = total[bottom][:, right] - total[top][:, right] - total[bottom][:, left] + total[top][:, left]
        more = votes > best
        best[more], most[more] = votes[more], material
    return np.where(on & (best > 0), most, found).astype(np.uint8)


def on_surface(mesh, count=SAMPLES, seed=0):
    """Texture coordinates of `count` points spread evenly over a loaded mesh's surface: what a share of the
    outfit is measured on, since a texture's texels are not all on a face and are not all one size worn."""
    v, f = mesh['vertices'], mesh['faces']
    corners = v[f]
    area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(f), count, p=area / area.sum())
    weight = rng.dirichlet((1.0, 1.0, 1.0), count)
    return (weight[:, :, None] * mesh['uv'][f[pick]]).sum(axis=1)


def drawn(document):
    """The flat colour (0-255) each material of an intake document is drawn in for the bake: `PALETTE`'s for its
    kind, the first of a kind its first."""
    seen, colours = {}, []
    for material in document['materials']:
        colours.append(PALETTE[material['kind']][seen.get(material['kind'], 0)])
        seen[material['kind']] = seen.get(material['kind'], 0) + 1
    return np.array(colours, float)


def flat(mesh, document):
    """(image, record): a loaded mesh's base colour texture drawn as the kit's own generator draws an outfit,
    every material one flat colour (`drawn`) that only its shading changes, as RGB 0-255 in the texture's own
    layout. The bake tells materials apart by colour and keeps of a texel only how light it is for its
    material (`texture.materials`, `texture.tint_maps`); a painted texture's blacks, greys and browns are no
    such colours. A texel is as much lighter than its material's flat colour as it is lighter in the texture
    than its material's middle there, measured over the surface (`on_surface`) with `SOFT` added to both so
    that the noise of a black cloth is not shading, and held within `SHADE`. Skin is drawn as the material the
    document names for it (`skin.as`). The record holds each material's share of the surface and its middle
    lightness in the texture, and the skin's share; a material with less than `LEAST` of the surface is
    refused, since the bake would not find it (`texture.materials`)."""
    names = [material['name'] for material in document['materials']]
    skin = len(names)
    found = settled(sort(mesh, document), islands(mesh), skin + 1, round(SETTLE * mesh['colour'].shape[1] / SIDE))
    at = on_surface(mesh)
    seen = texels(found, at)
    bare = float(np.mean(seen == skin))
    if bare or skin in found:
        require('as' in document.get('skin', {}), 'The texture shows skin: the intake document says what it is drawn as')
        as_material = names.index(document['skin']['as'])
        found, seen = np.where(found == skin, as_material, found).astype(np.uint8), np.where(seen == skin, as_material, seen)
    light = mesh['colour'].astype(np.float32) @ (texture.LIGHT / 255.0).astype(np.float32)
    light_seen = texels(light, at)
    share = np.bincount(seen, minlength=skin)[:skin] / len(seen)
    for name, part in zip(names, share):
        require(part >= LEAST, f'{name} is {part:.1%} of the surface: under {LEAST:.0%} the bake finds no such material, so give its anchors to another')
    middle = np.array([float(np.median(light_seen[seen == k])) for k in range(skin)], np.float32)
    ratio = np.clip((light + SOFT) / (middle[found] + SOFT), *SHADE)
    image = np.clip(drawn(document).astype(np.float32)[found] * ratio[:, :, None], 0, 255).astype(np.uint8)
    return image, {'materials': {name: {'share': round(float(part), 4), 'middle': round(float(level), 4)} for name, part, level in zip(names, share, middle)},
                   'skinShare': round(bare, 4)}


# --- The mesh rebuilt as one closed surface ---

def to_frame(vertices, scale):
    """Vertices in the bodies' axes, in the frame a colour field and the bake's source mesh share: glTF's axes
    (`bake.to_field`'s turn), scaled by `scale` into the unit cube about the origin."""
    vertices = np.asarray(vertices, float)
    return np.stack([-vertices[:, 0], vertices[:, 2], vertices[:, 1]], axis=1) * scale


def components(vertices, faces):
    """A number per face: the piece of the mesh it belongs to, faces that share a vertex being one piece."""
    faces = np.asarray(faces, int)
    group = np.asarray(mesh_ops.union_find(len(vertices), np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]]]).tolist()))
    return np.unique(group[faces[:, 0]], return_inverse=True)[1].reshape(-1)


def volumes(vertices, faces, piece):
    """The signed volume of each piece of a mesh (`components`): positive for a closed piece wound to face out."""
    corners = np.asarray(vertices, float)[np.asarray(faces, int)]
    return np.bincount(piece, weights=np.einsum('ij,ij->i', corners[:, 0], np.cross(corners[:, 1], corners[:, 2])) / 6)


def wrap(vertices, faces, igl, meshlab, voxel=VOXEL, offset=OFFSET, target=FACES, smoothing=SMOOTHING, say=lambda *_: None):
    """A mesh rebuilt as one closed surface: (fine vertices, fine faces, vertices, faces), the fine surface as it
    is rebuilt and the same brought down to about `target` triangles, both wound to face out.

    An exported mesh is not the single closed surface the bake cuts (`bake.surface`): the first fifteen, Meshy
    exports reduced to 10,000 triangles, each had 26 to 103 open edge loops up to 37 cm round and 45 to 353
    edges shared by three faces or more, sheets joined along an edge. The sections the kit reads joints and
    sleeves from came out open on them, and 11 of the 15 were refused before they were bent (2026-11-14). A
    repair that keeps a manifold part of the faces (MeshFix) kept a seventh of the pilot's.

    So the surface is drawn again from the distance to the given faces, signed by their winding number, which
    a hole or a sheet through the inside changes little (`igl.signed_distance`): the level `offset` outside
    them, on a grid of `voxel`, by marching cubes. Pieces closed the wrong way round (hollows inside the
    outfit) and pieces under `PIECE` of the largest are left out. The fine surface is smoothed (`smoothing`
    steps, no shrinking) and is what the bake reads its relief from; reduced by quadric collapses that keep its
    topology, it is the mesh the bake cuts. `vertices` are in the frame the colour field is in (`to_frame`),
    and `voxel` and `offset` are in its units. `igl` and `meshlab` are the loaded libraries."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, np.int64)
    if volumes(vertices, faces, np.zeros(len(faces), int))[0] < 0:
        faces = faces[:, ::-1].copy()
    low = vertices.min(axis=0) - 6 * voxel
    count = np.ceil((vertices.max(axis=0) + 6 * voxel - low) / voxel).astype(int) + 1
    require(int(np.prod(count)) <= GRID, f'A grid of {tuple(count.tolist())} is over {GRID:,} points: use a larger voxel')
    axes = [low[i] + voxel * np.arange(count[i]) for i in range(3)]
    grid = np.stack([axis.ravel(order='F') for axis in np.meshgrid(*axes, indexing='ij')], axis=1)
    distance = np.asarray(igl.signed_distance(grid, vertices, faces, sign_type=igl.SIGNED_DISTANCE_TYPE_FAST_WINDING_NUMBER)[0], float)
    made = igl.marching_cubes(distance, grid, int(count[0]), int(count[1]), int(count[2]), float(offset))
    fine_v, fine_f = np.asarray(made[0], float), np.asarray(made[1], np.int64)
    require(len(fine_f), 'No surface was found round the mesh')
    say('rebuilt', len(fine_f), 'triangles on a grid of', count.tolist())
    weld = mesh_ops.weld_ids(fine_v, voxel * 1e-4)
    first = np.unique(weld, return_index=True)[1]
    fine_v, fine_f = fine_v[first], weld[fine_f]
    fine_f = fine_f[(fine_f[:, 0] != fine_f[:, 1]) & (fine_f[:, 1] != fine_f[:, 2]) & (fine_f[:, 0] != fine_f[:, 2])]
    piece = components(fine_v, fine_f)
    size = volumes(fine_v, fine_f, piece)
    keep = size >= PIECE * size.max()
    fine_f = fine_f[keep[piece]]
    used, inverse = np.unique(fine_f, return_inverse=True)
    fine_v, fine_f = fine_v[used], inverse.reshape(-1, 3)
    say('pieces kept', int(keep.sum()), 'of', len(size))
    meshes = meshlab.MeshSet()
    meshes.add_mesh(meshlab.Mesh(fine_v, fine_f.astype(np.int32)))
    if smoothing:
        meshes.apply_coord_taubin_smoothing(lambda_=0.5, mu=-0.53, stepsmoothnum=int(smoothing))
    fine_v = np.asarray(meshes.current_mesh().vertex_matrix(), float).copy()
    meshes.meshing_decimation_quadric_edge_collapse(targetfacenum=int(target), preservetopology=True, preserveboundary=True,
                                                    preservenormal=True, qualitythr=0.3)
    reduced = meshes.current_mesh()
    reduced.compact()
    return fine_v, fine_f, np.asarray(reduced.vertex_matrix(), float).copy(), np.asarray(reduced.face_matrix(), np.int64).copy()


# --- A colour field read off the texture ---

def _nearest(points, corners):
    """(face, weights) of the nearest point of triangles `corners` (m, 3, 3) to each of `points`, measured to
    every triangle: for a mesh too small to need a library."""
    a, b, c = (corners[None, :, i] for i in range(3))
    p = points[:, None]
    normal = np.cross(b - a, c - a)
    area = np.maximum((normal ** 2).sum(axis=2), 1e-30)
    shape = (len(points), corners.shape[0])
    best, weights = np.full(shape, np.inf), np.zeros(shape + (3,))
    inside = np.stack([(np.cross(c - b, p - b) * normal).sum(axis=2), (np.cross(a - c, p - c) * normal).sum(axis=2),
                       (np.cross(b - a, p - a) * normal).sum(axis=2)], axis=2) / area[:, :, None]
    flat_on = (inside >= 0).all(axis=2)
    apart = ((p - a) * normal).sum(axis=2) ** 2 / area
    best[flat_on], weights[flat_on] = apart[flat_on], inside[flat_on]
    for i, (start, end) in enumerate(((a, b), (b, c), (c, a))):
        along = np.clip(((p - start) * (end - start)).sum(axis=2) / np.maximum(((end - start) ** 2).sum(axis=2), 1e-30), 0.0, 1.0)
        apart = ((p - start - along[:, :, None] * (end - start)) ** 2).sum(axis=2)
        on_edge = np.zeros(shape + (3,))
        on_edge[:, :, i], on_edge[:, :, (i + 1) % 3] = 1 - along, along
        nearer = apart < best
        best[nearer], weights[nearer] = apart[nearer], on_edge[nearer]
    face = best.argmin(axis=1)
    return face, weights[np.arange(len(points)), face]


def closest(points, vertices, faces, igl=None, rows=ROWS):
    """(face, weights): for each point the face of a mesh it is nearest and where on it, as three weights of
    the face's corners. With `igl`, the loaded library, its search tree is used; without, every face is
    measured, which a small mesh allows."""
    points, vertices, faces = np.asarray(points, float), np.asarray(vertices, float), np.asarray(faces, np.int64)
    if igl is None:
        found = [_nearest(points[start:start + rows], vertices[faces]) for start in range(0, len(points), rows)]
        return np.concatenate([face for face, _ in found]), np.concatenate([weight for _, weight in found])
    _, face, at = igl.point_mesh_squared_distance(points, vertices, faces)
    face = np.asarray(face, np.int64).reshape(-1)
    a, b, c = (vertices[faces[face, i]] for i in range(3))
    first, second, there = b - a, c - a, np.asarray(at, float) - a
    d00, d01, d11 = (first * first).sum(axis=1), (first * second).sum(axis=1), (second * second).sum(axis=1)
    d20, d21 = (there * first).sum(axis=1), (there * second).sum(axis=1)
    den = d00 * d11 - d01 * d01
    den = np.where(np.abs(den) < 1e-30, 1e-30, den)
    v, w = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
    weights = np.clip(np.stack([1 - v - w, v, w], axis=1), 0.0, 1.0)
    return face, weights / np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)


def reader(mesh, scale, image, igl=None):
    """`read(points)` for points in the field's frame (`to_frame` at `scale`): six values 0-1 a point, the colour
    of `image` (the texture's layout, as `flat` draws it), how metallic and how rough the loaded mesh is at
    the point of its surface nearest, and 1."""
    framed = to_frame(mesh['vertices'], scale)

    def read(points):
        face, weights = closest(points, framed, mesh['faces'], igl)
        at = (weights[:, :, None] * mesh['uv'][mesh['faces'][face]]).sum(axis=1)
        other = [np.zeros(len(at)) if mesh[key] is None else texels(mesh[key], at) / 255.0 for key in ('metal', 'rough')]
        return np.concatenate([texels(image, at) / 255.0, np.stack(other + [np.ones(len(at))], axis=1)], axis=1)
    return read


def shell(surfaces, resolution=RESOLUTION, reach=1):
    """The voxels of a field of `resolution` a side that surfaces [(vertices, faces), ...] in its frame pass
    through, and those within `reach` of them: (n, 3) whole numbers, each once."""
    step = 1.0 / resolution
    cells = np.concatenate([np.floor((seams.surface_points(vertices, faces, step) + 0.5) * resolution).astype(np.int64) for vertices, faces in surfaces])
    require(cells.min() >= reach and cells.max() < resolution - reach, 'The surfaces do not lie inside the field: scale them into the unit cube')
    key = np.unique((cells[:, 0] * resolution + cells[:, 1]) * resolution + cells[:, 2])
    for axis in (resolution * resolution, resolution, 1):  # one axis after another: a cube of neighbours
        key = np.unique(np.concatenate([key + shift * axis for shift in range(-reach, reach + 1)]))
    return np.stack([key // (resolution * resolution), key // resolution % resolution, key % resolution], axis=1)


def colour_field(surfaces, read, resolution=RESOLUTION, rows=1 << 20):
    """(coords, attrs) of a colour field as the bake opens one (`texture.open_field`): the voxels round
    `surfaces` (`shell`), each with what `read` gives at its middle."""
    coords = shell(surfaces, resolution)
    centres = (coords + 0.5) / resolution - 0.5
    attrs = np.concatenate([read(centres[start:start + rows]) for start in range(0, len(centres), rows)])
    return coords.astype(np.int32), np.clip(attrs, 0.0, 1.0).astype(np.float32)


# --- The intake document, and the files the bake takes ---

def validate(document):
    """An intake document, checked. It says of one outfit made elsewhere what a brief says of a generated one,
    and how to read that off its texture:

        {"schemaVersion": 1, "kind": "srn-armorkit-intake", "model": "meshy-urban-heavy",
         "source": {"provider": "Meshy", "file": "....glb", "sha256": "..."},
         "materials": [{"name": "fabric", "kind": "cloth", "wears": "the fatigues.",
                        "anchors": [{"colour": [40, 40, 40], "metal": 0.05}]}],
         "skin": {"anchors": [{"colour": [235, 185, 155]}], "as": "fabric", "note": "fingertips of the gloves"},
         "faces": 20000}

    A material is told by its `anchors`, colours of the texture with how metallic the texture is there (`sort`).
    `skin` holds the anchors of body skin the mesh carries and the material it is drawn as. `bare` lists the
    slots left to the body, as a brief does (`brief.validate`), and goes into the brief `brief` writes.
    `faces` is how many triangles the mesh is rebuilt at."""
    require(isinstance(document, dict) and document.get('schemaVersion') == 1 and document.get('kind') == KIND,
            f'An intake document is a JSON object of kind {KIND}, schemaVersion 1')
    require(set(document) <= KEYS and {'model', 'source', 'materials'} <= set(document), f'An intake document holds {sorted(KEYS)}')
    source = document['source']
    require(isinstance(source, dict) and set(source) == {'provider', 'file', 'sha256'} and all(isinstance(value, str) and value for value in source.values()),
            "The source names its provider, its file and the file's sha256")
    colour = lambda value: isinstance(value, list) and len(value) == 3 and all(isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 255 for part in value)
    number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
    anchor = lambda value: isinstance(value, dict) and set(value) <= {'colour', 'metal'} and colour(value.get('colour')) and number(value.get('metal', 0.0))
    listed = lambda value: isinstance(value, list) and bool(value) and all(anchor(item) for item in value)
    materials = document['materials']
    require(isinstance(materials, list) and 1 <= len(materials) <= 6, 'An intake document lists one to six materials')
    for material in materials:
        require(isinstance(material, dict) and set(material) == {'name', 'kind', 'wears', 'anchors'} and material['kind'] in texture.KINDS
                and all(isinstance(material[key], str) and material[key].strip() for key in ('name', 'wears')) and listed(material['anchors']),
                'A material holds its name, its kind, what wears it and its anchors, each a colour and how metallic')
    names, kinds = [material['name'] for material in materials], [material['kind'] for material in materials]
    require(len(set(names)) == len(names) and all(kinds.count(kind) <= 2 for kind in kinds), 'Material names are unique, and at most two are of one kind')
    skin = document.get('skin', {})
    require(isinstance(skin, dict) and set(skin) <= {'anchors', 'as', 'note'} and (not skin or (listed(skin.get('anchors')) and skin.get('as') in names)),
            'Skin holds its anchors and names the material it is drawn as')
    faces = document.get('faces', FACES)
    require(isinstance(faces, int) and not isinstance(faces, bool) and 2000 <= faces <= 40000, 'The mesh is rebuilt at 2,000 to 40,000 triangles')
    return document


def brief(document):
    """The brief the bake reads (`brief.validate`), written from an intake document: its materials in the flat
    colours `flat` draws them in. The prompt says where the outfit came from; no image is made from it."""
    document = validate(document)
    source = document['source']
    made = {'schemaVersion': 1, 'kind': briefs.KIND, 'model': document['model'], 'pads': [],
            'materials': [{'name': material['name'], 'kind': material['kind'], 'colour': [int(part) for part in colour],
                           'look': f'the flat colour {material["name"]} is drawn in for the bake', 'wears': material['wears']}
                          for material, colour in zip(document['materials'], drawn(document))],
            'prompt': f'Taken in from {source["provider"]} ({source["file"]}), not drawn from a prompt.\n\n{briefs.MARK}'}
    if 'bare' in document:
        made['bare'] = document['bare']
    return briefs.validate(made)


def digest(path):
    """The SHA-256 of a file, as an intake document names its source by."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(document, source, output, igl, meshlab, say=lambda *_: None):
    """What the bake takes of an outfit, made from a textured mesh file and its intake document: the record,
    also written as `<output>/intake.json`. `<output>` gets `mesh.glb` (the rebuilt mesh, `bake --mesh`),
    `raw.glb` (the fine surface, `--raw`), `colours.npz` (`--colours`) and `brief.json` (the bake's brief).
    The source file is the one the document names, by its hash. `igl` and `meshlab` are the loaded libraries."""
    document, output = validate(document), Path(output)
    require(digest(source) == document['source']['sha256'], f'{source} is not the file the intake document names')
    output.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    mesh = load(source)
    image, sorted_as = flat(mesh, document)
    say('materials', sorted_as)
    scale = FILL / float(np.ptp(mesh['vertices'], axis=0).max())
    framed = to_frame(mesh['vertices'], scale)
    weld = mesh_ops.weld_ids(framed, 1e-7)
    first = np.unique(weld, return_index=True)[1]
    faces = weld[mesh['faces']]
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    fine_v, fine_f, v, f = wrap(framed[first], faces, igl, meshlab, target=document.get('faces', FACES), say=say)
    say('rebuilt in', round(time.monotonic() - began, 1), 's:', len(f), 'triangles')
    coords, attrs = colour_field([(fine_v, fine_f), (v, f)], reader(mesh, scale, image, igl))
    say('colour field of', len(coords), 'voxels')
    gltf.write_mesh(output / 'mesh.glb', v, f)
    gltf.write_mesh(output / 'raw.glb', fine_v, fine_f)
    np.savez_compressed(output / 'colours.npz', coords=coords, attrs=attrs, resolution=np.array(RESOLUTION))
    (output / 'brief.json').write_text(json.dumps(brief(document), indent=1) + '\n', encoding='utf-8', newline='\n')
    record = {'schemaVersion': 1, 'kind': 'srn-armorkit-intake-record', 'model': document['model'], 'source': document['source'],
              'scale': scale, 'sourceTriangles': int(len(mesh['faces'])), 'triangles': int(len(f)), 'fineTriangles': int(len(fine_f)),
              'voxels': int(len(coords)), **sorted_as, 'seconds': round(time.monotonic() - began, 1),
              'files': {name: digest(output / name) for name in ('mesh.glb', 'raw.glb', 'colours.npz', 'brief.json')}}
    (output / 'intake.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8', newline='\n')
    return record
