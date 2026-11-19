"""Small trims of a tileset's tiles made to cast no shadow. The game draws the shadow of a window sill, ledge or cornice
on the wall behind it as a hard-edged wedge, which shows as triangles across a wall once its picture is even and dark
(dgt04, 2026-11-18). A mesh whose second-longest side is under `THIN` metres, or whose longest is under `SMALL`, is a
trim: its `shadow` is set to 0 in a copy of the model. Walls, roofs and whole buildings keep theirs, as do compiled
models and models another tileset uses. A copy already in the folder (the lamps') is the one changed."""
import re
from pathlib import Path

from . import inventory, lamps, require

THIN, SMALL = 0.75, 1.0
NODE = re.compile(r'(?ims)^([ \t]*node[ \t]+(?:trimesh|danglymesh)[ \t]+(\S+)[^\n]*\n)(.*?)(^[ \t]*endnode)')


def extent(body):
    """The sides of a mesh node's box, longest first, from its verts; None without verts."""
    found = re.search(r'(?im)^\s*verts\s+(\d+)\s*\n', body)
    if not found:
        return None
    rows = [line.split()[:3] for line in body[found.end():].splitlines()[:int(found.group(1))]]
    points = [[float(value) for value in row] for row in rows if len(row) == 3]
    if not points:
        return None
    return sorted((max(point[axis] for point in points) - min(point[axis] for point in points) for axis in range(3)), reverse=True)


def quieted(text, thin=THIN, small=SMALL):
    """(the model's text with its trims casting no shadow, their names): only the geometry, not the animations."""
    geometry, cut, rest = text.partition('\nnewanim ')
    names = []

    def one(match):
        head, name, body, end = match.groups(); sides = extent(body)
        if sides is None or not re.search(r'(?im)^\s*shadow\s+1\s*$', body) or not (sides[1] < thin or sides[0] < small):
            return match.group(0)
        names.append(name)
        return head + re.sub(r'(?im)^(\s*shadow\s+)1(\s*)$', r'\g<1>0\g<2>', body) + end
    geometry = NODE.sub(one, geometry)
    return geometry + cut + rest, names


def quiet(repo, tileset, folder, *, thin=THIN, small=SMALL):
    """Write the models of a tileset whose trims cast shadows, with those trims quiet, into `folder` (a review's
    overlay; a model already there is changed in place) and tell {model: count of trims}."""
    repo, folder = Path(repo), Path(folder); tileset = tileset.lower(); folder.mkdir(parents=True, exist_ok=True)
    tiles = {tile['model'].lower() for tile in inventory.read_set((repo / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252'))['tiles']}
    others = inventory._other_sets(repo, tileset); told = {}
    for pack in lamps.PACKS:
        for path in sorted((repo / pack.format(tileset=tileset)).glob('*.mdl')):
            name = path.stem.lower()
            if name not in tiles or name in told or others.get(name):
                continue
            source = folder / path.name if (folder / path.name).is_file() else path; data = source.read_bytes()
            if inventory.compiled(data):
                continue
            text = data.decode('cp1252'); new, names = quieted(text, thin, small)
            if names:
                require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
                (folder / path.name).write_bytes(new.encode('cp1252')); told[name] = len(names)
    return told
