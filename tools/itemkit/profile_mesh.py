"""Build a simple long weapon's mesh straight from its colour side view: no generated geometry.

    python -m tools.itemkit.profile_mesh SIDE_VIEW.png OUTPUT_DIR --length METRES [--blade-depth 0.3] [--hook-px 6]
                                         [--mask FOREGROUND.png] [--round] [--fill-openings "reviewer's words"]

For a design made of round parts on one axis (shaft, sockets, butt cap), a flat head and thin flat hooks, a generated
mesh only adds risk: from a side-on view it invents depth (the wave-1 Spear's head came back bent 90 degrees). This
reads the outline off the white-background image instead:

- columns from the butt to the head are revolved about the axis (round in section);
- the head, from where the outline narrows steadily to the tip, gets a diamond section `--blade-depth` x its width;
- outline that stands out beyond the head's base half-width near the head (hooks, prongs) is a flat plate `--hook-px`
  thick, joined to a round collar of that half-width.

The parts are unioned through one signed-distance grid and meshed by surface nets, so the result is one closed solid.
The colour image is projected from the side onto every vertex as its texture (`textured.glb`, 4K diffuse); the same
mesh without texture is `mesh.glb`. Nothing here approves the shape: the clay views go to the person who reviews it.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.headkit.common import pin, require, write

BACKGROUND = 18          # a pixel is object when it is this much darker than white in some channel
OPENING_SPECK_PX = 16    # enclosed regions smaller than this are antialias specks, not openings


def enclosed_regions(component):
    """Pixel areas of the background regions the silhouette encloses, largest first (antialias specks left out)."""
    from scipy import ndimage
    holes = ndimage.binary_fill_holes(component) & ~component
    labels, count = ndimage.label(holes)
    sizes = ndimage.sum(holes, labels, range(1, count + 1)) if count else []
    return sorted((int(s) for s in sizes if s >= OPENING_SPECK_PX), reverse=True)


def outline(image, foreground=None):
    """(mask, top, bottom, first, last, enclosed): the filled silhouette, its per-column extents in pixels and the
    areas of the enclosed regions the fill closed.

    Without `foreground` the object is keyed off a white background; a catalog detail image sits on black beside its
    reviewed foreground mask, which is then the silhouette. Revolving and extruding the outline cannot keep an opening,
    so every enclosed region is filled; build() refuses that unless a reviewer has said the fill is right."""
    from scipy import ndimage
    if foreground is not None:
        solid = np.asarray(foreground.convert('L')) >= 128
        require(solid.shape == (image.height, image.width), 'The foreground mask must match the image')
    else:
        rgb = np.asarray(image.convert('RGB')).astype(np.int32); solid = (255 - rgb.min(2)) > BACKGROUND
    labels, count = ndimage.label(solid); require(count > 0, 'No object on the background')
    sizes = ndimage.sum(solid, labels, range(1, count + 1)); component = labels == 1 + int(np.argmax(sizes))
    enclosed = enclosed_regions(component); mask = ndimage.binary_fill_holes(component)
    columns = np.flatnonzero(mask.any(0)); first, last = int(columns[0]), int(columns[-1])
    top = np.full(mask.shape[1], np.nan); bottom = np.full(mask.shape[1], np.nan)
    for x in columns:
        rows = np.flatnonzero(mask[:, x]); top[x], bottom[x] = rows[0], rows[-1] + 1
    return mask, top, bottom, first, last, enclosed


def layout(mask, top, bottom, first, last, round_only=False):
    """Axis row, shaft radius, head start and head base half-width, all in pixels, measured from the outline.

    `round_only`: the whole design is round in section (a bat, a baton, a plain staff): no flat head."""
    span = last - first; centre_cols = np.arange(first + int(.2 * span), first + int(.7 * span))
    axis = float(np.median((top[centre_cols] + bottom[centre_cols]) / 2))
    half = np.maximum(axis - top, bottom - axis)          # NaN outside the object
    # One-pixel jitter of a straight outline (inset slots, antialiasing) would ring the revolved shaft: a five-column
    # median removes it and keeps real steps (sockets, the butt cap), which are many columns long.
    from scipy import ndimage
    inside = np.isfinite(half); half[inside] = ndimage.median_filter(half[inside], size=5, mode='nearest')
    shaft = float(np.median(half[centre_cols]))
    if round_only:
        # Steps and tapers stay; the revolved outline would ring on whole-pixel steps along a long gentle taper.
        half[first:last + 1] = ndimage.gaussian_filter1d(half[first:last + 1], 1., mode='nearest')
        return {'axisRow': axis, 'shaftHalfWidth': shaft, 'headStart': int(last + 1), 'headBaseHalfWidth': float(np.nanmax(half))}, half
    # The head runs from where the outline narrows steadily to the tip: walk back from the tip while it keeps widening.
    x = last; tolerance = 1.0
    while x - 1 > first + .5 * span and half[x - 1] >= half[x] - tolerance and half[x - 1] <= half[x] + 6: x -= 1
    head = x; base = float(half[head])
    require(base > shaft, 'No head wider than the shaft was found')
    # The head's edges are straight or gently curved; their whole-pixel steps would rib its flat faces.
    half[head:last + 1] = ndimage.gaussian_filter1d(half[head:last + 1], 2., mode='nearest')
    return {'axisRow': axis, 'shaftHalfWidth': shaft, 'headStart': int(head), 'headBaseHalfWidth': base}, half


def distance_field(mask, half, plan, first, last, scale, blade_depth, hook_px, voxel):
    """Signed distance (metres, negative inside) of the union of the revolved body, the diamond head and the flat hooks."""
    from scipy import ndimage
    axis, head, base = plan['axisRow'], plan['headStart'], plan['headBaseHalfWidth']
    reach = float(np.nanmax(half)) * scale; pad = 4 * voxel
    # Single precision throughout: a 2.2 m spear at sub-millimetre voxels is tens of millions of cells per grid.
    xs = np.arange(-pad, (last + 1 - first) * scale + pad, voxel, dtype=np.float32)
    ys = np.arange(-reach - pad, reach + pad, voxel, dtype=np.float32)
    depth = max(base * scale, hook_px * scale) + pad; zs = np.arange(-depth, depth + voxel / 2, voxel, dtype=np.float32)
    px = xs / np.float32(scale) + np.float32(first)                              # image column of each grid x
    profile = lambda values: np.interp(px, np.arange(len(values)), np.nan_to_num(values)).astype(np.float32)
    radius = profile(np.where(np.arange(len(half)) < head, np.minimum(half, base), 0)) * scale
    width = profile(np.where(np.arange(len(half)) >= head, half, 0)) * scale
    X, Y, Z = xs[:, None, None], ys[None, :, None], zs[None, None, :]
    body_end = (head - first) * scale
    body = np.maximum(np.sqrt(Y ** 2 + Z ** 2) - radius[:, None, None], np.maximum(-X, X - body_end))
    if head > last: return body.astype(np.float32), (xs, ys, zs), False          # round only: no head, no hooks
    # At least a voxel deep, so the thin point is not lost long before its outline ends.
    w = np.maximum(width, 1e-6)[:, None, None]; d = np.maximum(blade_depth * w, voxel)
    blade = (np.abs(Y) * d + np.abs(Z) * w - w * d) / np.sqrt(w ** 2 + d ** 2)
    blade = np.maximum(blade, np.maximum(body_end - X - voxel, X - (last + 1 - first) * scale))
    field = np.minimum(body, blade)
    # Hooks: outline beyond the collar near the head, as a flat plate. 2D signed distance in the image plane.
    rows = np.arange(mask.shape[0])[:, None]; cols = np.arange(mask.shape[1])[None, :]
    near_head = (cols >= head - 4 * base) & (cols < head + base)
    hooks = mask & near_head & (np.abs(rows - axis) > .9 * base)
    if hooks.any():
        plane = (ndimage.distance_transform_edt(~hooks) - ndimage.distance_transform_edt(hooks)) * scale
        sample = ndimage.map_coordinates(plane, [np.clip(axis - ys / scale, 0, mask.shape[0] - 1)[None, :].repeat(len(xs), 0),
                                                np.clip(px, 0, mask.shape[1] - 1)[:, None].repeat(len(ys), 1)], order=1)
        plate = np.maximum(sample.astype(np.float32)[:, :, None], np.abs(Z) - np.float32(hook_px * scale / 2))
        field = np.minimum(field, plate)
    return field.astype(np.float32), (xs, ys, zs), bool(hooks.any())


def surface_nets(field, origin, voxel):
    """Closed triangle mesh of the zero level of a signed distance grid (negative inside), one vertex per surface cell."""
    # A grid node on the surface makes every cell around it place its vertex on that node (flat triangles): nudge
    # such nodes outside by a fiftieth of a voxel.
    s = np.where(np.abs(field) < .02 * voxel, np.float32(.02 * voxel), field)
    # Zero crossings on every grid edge, accumulated into the four cells around the edge.
    crossings = []
    for axis in range(3):
        a = [slice(None)] * 3; b = [slice(None)] * 3; a[axis] = slice(0, -1); b[axis] = slice(1, None)
        s0, s1 = s[tuple(a)], s[tuple(b)]; cross = (s0 < 0) != (s1 < 0)
        index = np.argwhere(cross); t = s0[cross] / (s0[cross] - s1[cross])
        point = index.astype(np.float64); point[:, axis] += t
        crossings.append((axis, index, point, s0[cross] < 0))
    shape = np.array(s.shape) - 1
    cell_ids, cell_points = [], []
    for axis, index, point, _ in crossings:
        others = [k for k in range(3) if k != axis]
        for db in (0, 1):
            for dc in (0, 1):
                cell = index.copy(); cell[:, others[0]] -= db; cell[:, others[1]] -= dc
                ok = (cell >= 0).all(1) & (cell < shape).all(1)
                cell_ids.append(np.ravel_multi_index(cell[ok].T, shape)); cell_points.append(point[ok])
    ids = np.concatenate(cell_ids); points = np.concatenate(cell_points)
    unique, compact = np.unique(ids, return_inverse=True)
    counts = np.bincount(compact); position = np.stack([np.bincount(compact, points[:, k]) for k in range(3)], 1) / counts[:, None]
    faces = []
    for axis, index, point, lower_inside in crossings:
        b, c = [(1, 2), (2, 0), (0, 1)][axis]
        corners = []
        for db, dc in ((1, 1), (0, 1), (0, 0), (1, 0)):                  # (b-1,c-1), (b,c-1), (b,c), (b-1,c)
            cell = index.copy(); cell[:, b] -= db; cell[:, c] -= dc; corners.append(cell)
        ok = np.all([((cell >= 0).all(1) & (cell < shape).all(1)) for cell in corners], 0)
        quad = np.stack([np.searchsorted(unique, np.ravel_multi_index(cell[ok].T, shape)) for cell in corners], 1)
        flip = ~lower_inside[ok]; quad[flip] = quad[flip][:, ::-1]
        # Split each quad along the diagonal that keeps both triangles fuller: the other one can be a sliver or flat.
        area = lambda a, b, c: np.linalg.norm(np.cross(position[quad[:, b]] - position[quad[:, a]], position[quad[:, c]] - position[quad[:, a]]), axis=1)
        other = np.minimum(area(0, 1, 3), area(1, 2, 3)) > np.minimum(area(0, 1, 2), area(0, 2, 3))
        faces += [np.where(other[:, None], quad[:, [0, 1, 3]], quad[:, [0, 1, 2]]), np.where(other[:, None], quad[:, [1, 2, 3]], quad[:, [0, 2, 3]])]
    faces = np.concatenate(faces).astype(np.int64)
    return np.asarray(origin) + position * voxel, faces


def vertex_normals(vertices, faces):
    n = np.zeros_like(vertices); face = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    for k in range(3): np.add.at(n, faces[:, k], face)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-30)[:, None]


def diffuse(image, mask, path, size=4096):
    """The side view as a 4K diffuse: background texels take the nearest object colour so edges never bleed white."""
    from PIL import Image
    from scipy import ndimage
    rgb = np.asarray(image.convert('RGB')); index = ndimage.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    Image.fromarray(rgb[index[0], index[1]]).resize((size, size), Image.Resampling.LANCZOS).save(path)
    return path


def build(image_path, output, length, *, blade_depth=.3, hook_px=6, voxel=None, mask_path=None, round_only=False,
          fill_openings=None):
    """`fill_openings`: the reviewer's words that the regions the silhouette encloses are not openings to keep (keyed
    highlights, say). Without them an enclosed region stops the build: this mesher cannot keep an opening."""
    from PIL import Image
    from tools.headkit.gltf import write_mesh
    from .donor import embed_diffuse
    from .geometry import topology
    require(length > 0 and 0 < blade_depth <= 1 and hook_px > 0, 'Positive length, blade depth and hook thickness required')
    require(fill_openings is None or fill_openings.strip(), "--fill-openings must quote the reviewer's words")
    with Image.open(image_path) as image:
        image.load()
        if mask_path:
            with Image.open(mask_path) as foreground: foreground.load(); mask, top, bottom, first, last, enclosed = outline(image, foreground)
        else: mask, top, bottom, first, last, enclosed = outline(image)
        require(not enclosed or fill_openings,
                f'The silhouette encloses {len(enclosed)} region(s) (largest {enclosed[0] if enclosed else 0} px) that meshing '
                'would fill: keep them through another route, or give --fill-openings with the review that they are not openings')
        output = Path(output); output.mkdir(parents=True, exist_ok=False)     # after validation: a bad call leaves no folder
        plan, half = layout(mask, top, bottom, first, last, round_only)
        scale = length / (last + 1 - first); voxel = voxel or max(scale * .75, .0008)
        field, (xs, ys, zs), hooked = distance_field(mask, half, plan, first, last, scale, blade_depth, hook_px, voxel)
        v, f = surface_nets(field, (xs[0], ys[0], zs[0]), voxel)
        report = topology(v, f)
        require(report['closedWound'], 'The meshed outline is not one closed outward solid')
        # glTF frame: the long axis on +X, image up on +Y, depth on Z. UVs project the side view. A small shear by depth
        # (under a pixel across the whole part) keeps faces seen edge-on from the side, such as the end caps, from
        # collapsing to zero UV area, which a textured donor may not have.
        depth_px = v[:, 2] / scale
        u = ((v[:, 0] / scale + first) + .02 * depth_px + .5) / mask.shape[1]
        w = ((plan['axisRow'] - v[:, 1] / scale) + .013 * depth_px + .5) / mask.shape[0]
        normals = vertex_normals(v, f)
        write_mesh(output/'mesh.glb', v, f, normals=normals)
        write_mesh(output/'uv.glb', v, f, uv=np.clip(np.c_[u, w], 0, 1)[f], normals=normals)
        texture = diffuse(image, mask, output/'diffuse-4096.png')
    textured = embed_diffuse(output/'uv.glb', texture, output/'textured.glb'); (output/'uv.glb').unlink()
    result = {'kind': 'profile-mesh', 'source': pin(image_path), 'lengthMetres': length, 'metresPerPixel': scale, 'voxel': voxel,
              'bladeDepthRatio': blade_depth, 'hookThicknessPixels': hook_px, 'layout': plan, 'hooks': hooked,
              'columns': [first, last], 'vertices': len(v), 'triangles': len(f), 'topology': report,
              'extents': (v.max(0) - v.min(0)).tolist(), 'mesh': pin(output/'mesh.glb'), 'textured': textured,
              'method': ('whole outline revolved about the axis' if round_only else
                         'outline revolved about the axis up to the head, diamond-section head, flat hooks') +
                        '; one signed distance union meshed by surface nets; side-view colour projected as the diffuse',
              'roundOnly': round_only, 'reviewRequired': True}
    if mask_path: result['foregroundMask'] = pin(mask_path)
    if enclosed: result['filledRegions'] = {'count': len(enclosed), 'pixels': enclosed, 'review': fill_openings}
    write(output/'profile-mesh.json', result, fresh=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('image', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--length', type=float, required=True, help='overall length in metres (the fit rescales it later)')
    parser.add_argument('--blade-depth', type=float, default=.3); parser.add_argument('--hook-px', type=float, default=6)
    parser.add_argument('--voxel', type=float)
    parser.add_argument('--mask', type=Path, help='the reviewed foreground mask of an image on black (catalog detail images)')
    parser.add_argument('--round', dest='round_only', action='store_true', help='round in section end to end: no flat head or hooks')
    parser.add_argument('--fill-openings', help="the reviewer's words that the enclosed regions are not openings to keep")
    a = parser.parse_args(argv)
    result = build(a.image, a.output, a.length, blade_depth=a.blade_depth, hook_px=a.hook_px, voxel=a.voxel,
                   mask_path=a.mask, round_only=a.round_only, fill_openings=a.fill_openings)
    print(json.dumps({k: result[k] for k in ('layout', 'vertices', 'triangles', 'extents', 'voxel')}, indent=1)); return 0


if __name__ == '__main__':
    sys.exit(main())
