"""A tower terrain's crown: a parapet and cornice along its facades and a set-back screen on its roof, for `remesh`.

A tower tile fills its cell to the roof, and a facade stands on each side of the cell whose two corners are not of
the tower's terrain (the street's). The crown is drawn from those corners alone, so that every tile of the terrain
draws it alike and the pieces run on across the tiles' sides: `remesh --joins` checks that each side a crown crosses
meets a side of the same terrain that draws the same. Along each facade:

- a parapet `PARAPET` deep and high on the roof's edge, with a coping;
- a cornice under the roof, standing `CORNICE` out over the street, wrapped round an outer corner;
- a screen set `SCREEN` back from the facade, the tower's crown, with posts every `POST` metres.

A corner of the street's whose two sides are both the tower's (an inner corner) takes the parapet's and the screen's
turn there. The crown is written as `<tile>.mdl`, alone, into a folder that
`remesh --add --joins` draws over the tile's own meshes (user, 2026-11-20: a trial on a copy of Highrise_07, crown and parapet)."""
from pathlib import Path

from . import geometry, inventory, kit, require
from .compiled import source

HALF = geometry.HALF
PARAPET = (0.35, 1.5)  # metres: its depth into the roof and its height over it
COPING = (0.05, 0.08)  # metres: how far it stands out on each side of the parapet, and its thickness
CORNICE = (0.5, 1.0, 0.6)  # metres: out over the street, its depth, and its top under the roof
# metres: back from the facade, its height over the roof, its thickness. A first trial 4 m tall and 1.5 m back hardly
# showed from the street over a 58 m tower (2026-11-20).
SCREEN = (1.0, 6.0, 0.15)
POST = (2.5, 1.0)  # metres between the screen's posts, from the cell's middle so neighbouring tiles' keep the rhythm, and how far they rise over it
BAND = (0.3, 0.04)  # metres: the lit band along the screen's top, on its face to the street, and its depth: the crown at night
CORNERS = ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight')
SIDES = {'n': (1, 0), 'w': (0, 2), 's': (2, 3), 'e': (3, 1)}  # each side's two corners, counter-clockwise round the tile (`remesh`)
FRAME = {'w': ((-1, 0), (0, 1)), 'e': ((1, 0), (0, 1)), 's': ((0, -1), (1, 0)), 'n': ((0, 1), (1, 0))}  # (out, along) of each side
AT = {0: (-1, 1), 1: (1, 1), 2: (-1, -1), 3: (1, -1)}  # each corner's (x, y) signs


def facades(corners, terrain):
    """The sides of a tile, laid with `corners` (the set file's four terrains), that are facades: both ends the street's."""
    ours = [corner.lower() == terrain.lower() for corner in corners]
    return {side for side, (one, other) in SIDES.items() if not ours[one] and not ours[other]}


def inner(corners, terrain, fronts):
    """The street's corners that neither facade of the tile reaches: an inner corner of the tower."""
    ours = [corner.lower() == terrain.lower() for corner in corners]
    return {corner for corner in range(4) if not ours[corner] and not any(corner in SIDES[side] for side in fronts)}


def _box(mesh, side, inset, along, height, look, bevel=0.0):
    """A box on `side`'s frame: `inset` (from, to) metres in from the facade (negative: out over the street), `along`
    (from, to) along it, `height` (from, to)."""
    (ox, oy), (ux, uy) = FRAME[side]
    points = [(ox * (HALF - depth) + ux * run, oy * (HALF - depth) + uy * run) for depth in inset for run in along]
    low = (min(x for x, _ in points), min(y for _, y in points), height[0]); high = (max(x for x, _ in points), max(y for _, y in points), height[1])
    mesh.box(low, high, look, bevel=bevel)


def _ends(side):
    """The sides at the `along` ends of `side`: (at -HALF, at +HALF)."""
    (_, _), (ux, uy) = FRAME[side]
    return ('w', 'e') if ux else ('s', 'n')


def crown(top, fronts, corners_in):
    """A kit `Mesh` of the crown on a roof at `top` for facades `fronts` and inner corners `corners_in`."""
    mesh = kit.Mesh(); depth, rise = PARAPET; out, band, under = CORNICE; back, tall, thick = SCREEN
    for side in sorted(fronts):
        low_end, high_end = _ends(side); wraps = (low_end in fronts, high_end in fronts)
        _box(mesh, side, (0.0, depth), (-HALF, HALF), (top, top + rise), 'galvanised')  # the parapet: corners overlap
        _box(mesh, side, (-COPING[0], depth + COPING[0]), (-HALF - (COPING[0] if wraps[0] else 0.0), HALF + (COPING[0] if wraps[1] else 0.0)),
             (top + rise, top + rise + COPING[1]), 'steel')  # its coping
        _box(mesh, side, (-out, 0.0), (-HALF - (out if wraps[0] else 0.0), HALF + (out if wraps[1] else 0.0)), (top - under - band, top - under), 'galvanised', bevel=0.03)
        start, end = (-HALF + back if wraps[0] else -HALF), (HALF - back if wraps[1] else HALF)  # the screen, meeting the next facade's
        _box(mesh, side, (back, back + thick), (start, end), (top, top + tall), 'grating')
        _box(mesh, side, (back - BAND[1], back), (start, end), (top + tall - BAND[0], top + tall), 'white')  # its lit band
        for run in (-1.5 * POST[0], -0.5 * POST[0], 0.5 * POST[0], 1.5 * POST[0]):  # its posts
            if start + 0.2 <= run <= end - 0.2:
                _box(mesh, side, (back - 0.05 - BAND[1], back + thick + 0.05), (run - 0.1, run + 0.1), (top, top + tall + POST[1]), 'steel')
    for corner in sorted(corners_in):  # an inner corner: the parapets' and screens' turn
        sx, sy = AT[corner]; cx, cy = sx * HALF, sy * HALF
        square = lambda size: (min(cx, cx - sx * size), min(cy, cy - sy * size))
        x0, y0 = square(depth); mesh.box((x0, y0, top), (x0 + depth, y0 + depth, top + rise), 'galvanised')
        x0, y0 = square(depth + COPING[0]); mesh.box((x0, y0, top + rise), (x0 + depth + COPING[0], y0 + depth + COPING[0], top + rise + COPING[1]), 'steel')
        inside = (cx - sx * back, cy - sy * back)  # the screen's turn, on lines `back` in from the two facades that meet here
        mesh.box((min(cx, inside[0]), min(inside[1], inside[1] - sy * thick), top), (max(cx, inside[0]), max(inside[1], inside[1] - sy * thick), top + tall), 'grating')
        far = inside[1] - sy * thick  # through the first leg's thickness, so the turn has no notch
        mesh.box((min(inside[0], inside[0] - sx * thick), min(cy, far), top), (max(inside[0], inside[0] - sx * thick), max(cy, far), top + tall), 'grating')
        lit = (top + tall - BAND[0], top + tall); edge = (inside[0], inside[1] + sy * BAND[1])  # the lit band round the turn, on the faces to the street
        mesh.box((min(cx, inside[0]), min(inside[1], edge[1]), lit[0]), (max(cx, inside[0]), max(inside[1], edge[1]), lit[1]), 'white')
        mesh.box((min(inside[0], inside[0] + sx * BAND[1]), min(cy, edge[1]), lit[0]), (max(inside[0], inside[0] + sx * BAND[1]), max(cy, edge[1]), lit[1]), 'white')
    return mesh


def rebuilt(text, name, corners, terrain):
    """A tile's crown as a model of its own in the tile's coordinates, for `remesh --add`, or None where the tile has
    no facade or inner corner. Its roof is the highest point the tile draws."""
    _, _, nodes = geometry.parse(text); shown = list(geometry.triangles(nodes)); require(shown, f'{name} draws nothing')
    top = max(point[2] for triangle in shown for point in triangle)
    fronts = facades(corners, terrain); turns = inner(corners, terrain, fronts)
    if not fronts and not turns:
        return None
    return crown(top, fronts, turns).text(name)


def write(repo, tileset, terrain, models, out, overlay=None):
    """Write the crowned rebuild of each of `models` (tiles of `terrain`) into `out`; the set file and models are read
    from `overlay` first (a copied terrain's). {model: facades and inner corners}."""
    repo, out = Path(repo), Path(out); out.mkdir(parents=True, exist_ok=True); told = {}
    where = [Path(overlay)] if overlay else []
    set_path = next((folder / f'{tileset}.set' for folder in where + [repo / f'srn_t_{tileset}'] if (folder / f'{tileset}.set').is_file()), None)
    require(set_path, f'No set file of {tileset}')
    laid = {}
    for tile in inventory.read_set(set_path.read_bytes().decode('cp1252'))['tiles']:
        laid.setdefault(tile['model'].lower(), []).append(tile['corners'])
    for model in models:
        require(model.lower() in laid, f'{model} is no tile of {set_path.name}')
        require(all([c.lower() for c in one] == [c.lower() for c in laid[model.lower()][0]] for one in laid[model.lower()]),
                f'{model} is laid by tiles with other corners: its crown would fit one of them only')
        path = next((folder / f'{model}.mdl' for folder in where + [repo / f'srn_t_{tileset}', repo / 'srn_t_common'] if (folder / f'{model}.mdl').is_file()), None)
        require(path, f'No {model}.mdl'); path = source(repo, path); data = path.read_bytes(); require(not inventory.compiled(data), f'{model} is compiled')
        corners = laid[model.lower()][0]; made = rebuilt(data.decode('cp1252'), model.lower(), corners, terrain)
        fronts = facades(corners, terrain)
        told[model] = {'facades': sorted(fronts), 'inner': sorted(CORNERS[corner] for corner in inner(corners, terrain, fronts))}
        if made is not None:
            (out / f'{model}.mdl').write_bytes(made.encode('cp1252'))
    return told
