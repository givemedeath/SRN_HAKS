"""Where a generated model's picture is smeared, found from what stood in front of each surface in its references.

Most of a generated model's picture is crisp and some of it is not (user, 2026-11-17: "most of the texture is crisp and
only some parts look smeared. Are those detectable and repairable in a systematic way?"). On the Shiawase Barrens power
station the smears followed straight lines: a warning sign on a transformer crisp below the height of the fence's razor
wire in the reference and smudged above it, and the same soft band along the rear wall at that height. The generator
makes a thing drawn in front of a surface (a wire, a rail, a pipe, a post) into geometry of its own and must then
invent the surface behind it, which it draws soft; and what was seen through a framed mesh (chain-link between rails and
posts) it prints onto the surface behind as it was drawn, mesh and all.

So the model's own geometry says where to look. Seen from the side each reference was drawn from, every point of the
surface is one of:

    clean    the first thing that side sees there, with nothing nearer close beside it
    behind   seen, but something at least `GAP` nearer stands within `WINDOW` of it: the band behind a wire or a rail
    framed   seen, inside a frame of nearer things on all four sides no more than `FRAME` apart: a panel behind a fence
    unseen   no reference saw it: it faces away from every one or lies behind another surface

A point clean from any reference is clean. Unseen surface is invented whole and comes out as detailed as the rest (the
power station's slab and side walls), so it is counted and not listed. The behind and framed points are gathered into
patches, and the picture confirms each: a patch behind something that holds less fine detail than the clean surface is
`smudged`, a framed one that holds more is `printed` (the mesh drawn on it), and one that reads like the clean surface
is left as `plain`, a place the geometry points at where the picture shows nothing wrong (a bare wall between two pipe
runs).

It reads square-on references only (a front or rear elevation, a side), and it knows only the geometry the generator
made: a thing drawn in front that it left out altogether is not found. A patch is a place to look, with its box in
metres on the model as `view` stands it, to state a `smooth`, `copy` or `paint` from."""
import json
import shutil
from pathlib import Path

import numpy as np

from . import convert, require

VIEWS = {'front': (1, 1.0), 'back': (1, -1.0), 'east': (0, 1.0), 'west': (0, -1.0)}  # side: (axis, the side of it the eye stands on)
RESOLUTION = 25   # pixels a metre of the depth pictures
GRAZE = 0.35      # a face turned further from the eye than this cosine is not seen by it
NEAR = 0.08       # metres a point may lie behind the first surface and still be it
GAP = 0.3         # metres nearer a thing must stand to count as in front
WINDOW = 0.3      # metres across that a wire or a rail spoils of what is behind it
FRAME = 3.8       # metres apart, at most, the sides of a frame: a fence's posts and rails
CELL = 0.5        # metres: points of one kind in touching cells are one patch
LEAST = 0.25      # square metres: a smaller patch is not told
SMUDGED, PRINTED = 0.8, 1.15  # a patch's fine detail against the clean surface's
KINDS = ('clean', 'unseen', 'behind', 'framed')
MARKS = {'smudged': (255, 40, 40), 'printed': (255, 230, 0), 'plain': (60, 140, 255)}


def _ndimage():
    try:
        from scipy import ndimage
    except ImportError as error:  # the bundled Python lacks scipy, as `onboard boxes` finds
        raise ValueError('smears needs scipy: put the pinned itemkit library folder on PYTHONPATH') from error
    return ndimage


def scatter(points, uvs, faces, *, resolution=RESOLUTION, seed=7):
    """Points strewn evenly over the surface, six to a depth pixel: (face, point, texel, area) of each, the area the
    share of its face's that it stands for."""
    a, b, c = points[faces[:, 0]], points[faces[:, 1]], points[faces[:, 2]]
    cross = np.cross(b - a, c - a); area = np.linalg.norm(cross, axis=1) / 2
    kept = np.flatnonzero(area > 1e-9); require(len(kept), 'The model has no surface')
    count = np.maximum(1, np.ceil(area[kept] * resolution * resolution * 6).astype(int)); face = np.repeat(kept, count)
    rng = np.random.default_rng(seed); r1, r2 = np.sqrt(rng.random(len(face))), rng.random(len(face))
    w = np.stack([1 - r1, r1 * (1 - r2), r1 * r2], axis=1)
    point = w[:, :1] * a[face] + w[:, 1:2] * b[face] + w[:, 2:] * c[face]
    corners = uvs[faces[face]]; texel = (w[:, :, None] * corners).sum(1)
    return face, point, texel, np.repeat(area[kept] / count, count), cross[face] / (2 * area[face, None])


def kinds(point, normal, views, *, resolution=RESOLUTION):
    """The kind of each strewn point (an index into `KINDS`), seen from each of `views` in turn."""
    ndimage = _ndimage(); require(views and all(view in VIEWS for view in views), 'A view is one of ' + ', '.join(VIEWS))
    low, high = point.min(0), point.max(0)
    clean = np.zeros(len(point), bool); behind = clean.copy(); framed = clean.copy()
    for view in views:
        axis, side = VIEWS[view]; across = 1 - axis
        depth = high[axis] - point[:, axis] if side > 0 else point[:, axis] - low[axis]
        col = ((point[:, across] - low[across]) * resolution).astype(int); row = ((point[:, 2] - low[2]) * resolution).astype(int)
        shape = (row.max() + 1, col.max() + 1); flat = row * shape[1] + col
        first = np.full(shape[0] * shape[1], np.inf); np.minimum.at(first, flat, depth)
        first = first.reshape(shape); first[~np.isfinite(first)] = depth.max() + 1  # nothing there: as far as can be
        seen = (side * normal[:, axis] > GRAZE) & (depth <= first.reshape(-1)[flat] + NEAR)
        window = max(3, int(WINDOW * resolution) | 1); frame = int(FRAME * resolution) | 1
        beside = ndimage.minimum_filter(first, size=window)
        by = seen & (depth > beside.reshape(-1)[flat] + GAP)
        # nearness with every gap between two near things closed, up and down and from side to side: inside both is a frame
        closed = np.minimum(ndimage.grey_closing(-first, size=(frame, 1)), ndimage.grey_closing(-first, size=(1, frame)))
        inside = seen & ~by & (depth > -closed.reshape(-1)[flat] + GAP)
        behind |= by; framed |= inside; clean |= seen & ~by & ~inside
    return np.where(clean, 0, np.where(behind, 2, np.where(framed, 3, 1)))


def detail(colour):
    """How much fine detail the picture holds round each texel: what a blur of one texel takes away, averaged over six."""
    ndimage = _ndimage()
    grey = np.asarray(colour.convert('RGB'), float) @ [0.299, 0.587, 0.114]
    return ndimage.gaussian_filter(np.abs(grey - ndimage.gaussian_filter(grey, 1.0)), 6)


def patches(point, area, kind, fine, normal, *, cell=CELL, least=LEAST):
    """The behind and framed points gathered into patches, largest first: {kind, verdict, area, detail, facing, box} of
    each, `detail` the patch's fine detail against the clean surface's, `facing` the way its surface looks (+x, -y, ...)
    and `box` its corners in metres on the model. Points are one patch where they are of one kind, look the same way
    and lie in touching cells, so a band along a wall is told apart from the pipes and tanks it runs behind."""
    require((kind == 0).any(), 'No reference sees any of the model cleanly: are the views the sides it was drawn from?')
    usual = float(np.median(fine[kind == 0])); told = []; ratio = fine / max(usual, 1e-9)
    way = np.abs(normal).argmax(1) * 2 + (normal[np.arange(len(normal)), np.abs(normal).argmax(1)] < 0)  # 0 +x, 1 -x, 2 +y, ...
    # the picture judges each point where it lies: a patch of one kind can hold a smudged band and a sound one
    verdicts = np.where(kind == 2, np.where(ratio < SMUDGED, 0, 2), np.where(kind == 3, np.where(ratio > PRINTED, 1, 2), -1))
    for index, verdict, facing in ((index, verdict, facing) for index in (2, 3) for verdict in range(3) for facing in range(6)):
        chosen = np.flatnonzero((kind == index) & (verdicts == verdict) & (way == facing))
        if not len(chosen):
            continue
        cells = np.floor(point[chosen] / cell).astype(int); keys, inverse = np.unique(cells, axis=0, return_inverse=True)
        inverse = inverse.reshape(-1); where = {tuple(key): number for number, key in enumerate(keys)}
        group = np.full(len(keys), -1); groups = 0
        steps = [(x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
        for start in range(len(keys)):
            if group[start] >= 0:
                continue
            group[start] = groups; stack = [start]
            while stack:
                x, y, z = keys[stack.pop()]
                for dx, dy, dz in steps:
                    other = where.get((x + dx, y + dy, z + dz))
                    if other is not None and group[other] < 0:
                        group[other] = groups; stack.append(other)
            groups += 1
        owner = group[inverse]
        for number in range(groups):
            mine = chosen[owner == number]; size = float(area[mine].sum())
            if size < least:
                continue
            told.append({'kind': KINDS[index], 'verdict': list(MARKS)[verdict], 'area': round(size, 2), 'detail': round(float(np.median(ratio[mine])), 2),
                         'facing': '+-'[facing % 2] + 'xyz'[facing // 2], 'box': [np.round(point[mine].min(0), 2).tolist(), np.round(point[mine].max(0), 2).tolist()], '_points': mine})
    return sorted(told, key=lambda patch: -patch['area'])


def study(source, height, views, output=None, *, resolution=RESOLUTION):
    """What of a generated model's surface its references did not see cleanly, the model stood `height` metres tall as
    `view` stands it. Returns {surface, shares, patches, found}; with `output`, writes `smears.json` there and
    `marked`, a copy of the model with each patch painted on its colour map by its verdict (red smudged, yellow
    printed, blue plain), to draw with `envkit view --source <output>/marked --height <height>`."""
    from PIL import Image
    source = Path(source); vertices, normals, uvs, faces = convert.read_glb(source / 'model.glb')
    points, _, uvs, _, _ = convert.fit(vertices, normals, uvs, height, faces=faces)
    face, point, texel, area, normal = scatter(points, uvs, faces, resolution=resolution)
    kind = kinds(point, normal, views, resolution=resolution)
    with Image.open(source / 'texture_0_base_color.png') as opened:
        colour = opened.convert('RGB')
    width, tall = colour.size; fine = detail(colour)
    px = np.clip((texel[:, 0] % 1.0 * width).astype(int), 0, width - 1); py = np.clip((texel[:, 1] % 1.0 * tall).astype(int), 0, tall - 1)
    found = patches(point, area, kind, fine[py, px], normal); total = float(area.sum())
    report = {'source': str(source), 'height': height, 'views': list(views), 'surface': round(total, 1),
              'shares': {name: round(float(area[kind == index].sum()) / total, 3) for index, name in enumerate(KINDS)},
              'found': {verdict: round(sum(patch['area'] for patch in found if patch['verdict'] == verdict), 1) for verdict in MARKS},
              'patches': [{key: value for key, value in patch.items() if key != '_points'} for patch in found]}
    if output is not None:
        output = Path(output); marked = output / 'marked'; marked.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / 'model.glb', marked / 'model.glb')
        side = 2048; small = np.zeros((side, side), np.uint8)
        for patch in reversed(found):  # the largest last, so it shows
            mine = patch['_points']; small[py[mine] * side // tall, px[mine] * side // width] = list(MARKS).index(patch['verdict']) + 1
        marks = np.asarray(Image.fromarray(small).resize((width, tall), Image.NEAREST)); painted = np.asarray(colour, float).copy()
        for number, tint in enumerate(MARKS.values(), 1):
            painted[marks == number] = 0.45 * painted[marks == number] + 0.55 * np.array(tint, float)
        Image.fromarray(painted.astype(np.uint8)).save(marked / 'texture_0_base_color.png')
        (output / 'smears.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
        report['marked'] = str(marked)
    return report
