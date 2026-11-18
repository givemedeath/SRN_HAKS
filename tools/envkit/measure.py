"""A generated building measured before its game set is written: its footprint, its slab, the height that gives its
door the right leaf and the tiles that hold it at that height, and how far out its walls stand where boxes are wanted.

The Shiawase Barrens power station was sized by its door to 10 metres, its lit boxes, door and fence measured there by
eye from gridded views, and then scaled down twice to fit two tiles, everything measured again each time; the depth
of its front wall and the places of its floodlights were found with scratch scripts (2026-11-17). `envkit measure`
tells them at the start."""
import numpy as np

from . import convert, require

LEAF = 2.1  # metres: a door's leaf (user, 2026-11-11: size a building by its door)
TILE, RIM = 10.0, 0.25  # a tile's side, and the outermost walk cell of a group, which the model leaves free (`tile.survey`)


def stood(source, height):
    """(vertices, faces) of a generated model as `convert.shape` stands it at `height`, before anything is retouched."""
    vertices, normals, uvs, faces = convert.read_glb(source)
    vertices, _, _, _, _ = convert.fit(vertices, normals, uvs, float(height), faces=faces)
    return vertices, faces


def slab(vertices, faces, highest=1.2):
    """The slab a building stands on: {top, area, box} of the largest level surface no higher than `highest` above the
    model's foot, or None where less than a tenth of the footprint is level there."""
    corners = vertices[faces]; across = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = np.linalg.norm(across, axis=1) / 2; level = across[:, 2] / np.maximum(2 * area, 1e-12) > 0.95; middle = corners.mean(1)
    low = level & (middle[:, 2] > 0.02) & (middle[:, 2] < highest)
    footprint = float(np.prod(np.ptp(vertices[:, :2], axis=0)))
    if area[low].sum() < footprint / 10:
        return None
    share, edges = np.histogram(middle[low, 2], bins=int(highest / 0.02), range=(0, highest), weights=area[low]); most = int(share.argmax())
    on = low & (middle[:, 2] >= edges[max(most - 1, 0)]) & (middle[:, 2] <= edges[min(most + 2, len(edges) - 1)]); points = corners[on].reshape(-1, 3)
    return {'top': round(float(np.average(middle[on, 2], weights=area[on])), 3), 'area': round(float(area[on].sum()), 1),
            'box': [points[:, :2].min(0).round(2).tolist(), points[:, :2].max(0).round(2).tolist()]}


def tiles(size):
    """(columns, rows) of the group that holds a footprint of `size` metres with its outermost walk cells free."""
    return tuple(max(1, int(np.ceil((float(one) + 2 * RIM) / TILE - 1e-9))) for one in size)


def fits(height, size, leaf=None, target=LEAF):
    """The heights worth standing a building at, from its footprint `size` [x, y] at `height` and, where its door was
    measured there, the door's `leaf`: [{height, leaf, footprint, tiles}], first the one that gives the door `target`,
    then for each smaller group the tallest that still fits it, while its leaf is within a quarter of the target."""
    size = np.asarray(size, float); require((size > 0).all() and height > 0, 'A building has a height and a footprint')
    told = lambda scale: {'height': round(height * scale, 2), 'leaf': round(leaf * scale, 2) if leaf else None,
                          'footprint': (size * scale).round(2).tolist(), 'tiles': list(tiles(size * scale))}
    found = [told(target / leaf if leaf else 1.0)]; columns, rows = found[0]['tiles']
    for fewer in ((columns - 1, rows), (columns, rows - 1), (columns - 1, rows - 1)):
        if min(fewer) < 1:
            continue
        scale = float(min((np.array(fewer) * TILE - 2 * RIM - 0.01) / size))
        one = told(scale)
        if tuple(one['tiles']) != (columns, rows) and (not leaf or abs(leaf * scale - target) <= target / 4) and one not in found:
            found.append(one)
    return found


def probe(vertices, faces, box):
    """How far out the model stands within `box`, [[x0, y0, z0], [x1, y1, z1]] on the stood model: {points, low, high,
    median}, the corners of what it holds and the middle of it on each axis. A box drawn wide across a wall and deep
    through it tells the wall's own depth by its median."""
    low, high = (np.asarray(corner, float) for corner in box)
    require(low.shape == high.shape == (3,) and (high > low).all(), 'A box runs from its low corner to its high corner')
    points = convert.scatter(vertices, faces, spacing=0.05); held = points[((points >= low) & (points <= high)).all(1)]
    if not len(held):
        return {'points': 0}
    return {'points': int(len(held)), 'low': held.min(0).round(2).tolist(), 'high': held.max(0).round(2).tolist(), 'median': np.median(held, axis=0).round(2).tolist()}


def study(source, height, leaf=None, boxes=None):
    """What `envkit measure` prints: {height, bounds, footprint, slab, fits, probes}."""
    vertices, faces = stood(source, height); size = np.ptp(vertices[:, :2], axis=0)
    return {'height': float(height), 'bounds': [vertices.min(0).round(2).tolist(), vertices.max(0).round(2).tolist()], 'footprint': size.round(2).tolist(),
            'slab': slab(vertices, faces), 'fits': fits(float(height), size, leaf),
            'probes': {label: probe(vertices, faces, box) for label, box in (boxes or {}).items()}}
