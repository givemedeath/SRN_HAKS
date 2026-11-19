"""Small trims of a tileset's tiles made to cast no shadow. The game draws the shadow of a window sill, ledge or cornice
on the wall behind it as a hard-edged wedge, which shows as triangles across a wall once its picture is even and dark
(dgt04, 2026-11-18). So does a flat panel of any size (a facade sheet, a plinth face): an open surface's shadow falls
in wedges on what is behind it. A mesh whose second-longest side is under `THIN` metres, whose longest is under
`SMALL`, or whose shortest is under `FLAT`, has its `shadow` set to 0 in a copy of the model. That takes in every mesh
that is one plane, a plain wall or roof among them: only meshes with depth in all three directions keep their shadow
on the street. Compiled models and models another tileset uses are left as they are. A copy already in the folder
(the lamps') is the one changed."""
import re
from pathlib import Path

from . import inventory, lamps, require

THIN, SMALL, FLAT = 2.0, 2.0, 0.1
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


def quieted(text, thin=THIN, small=SMALL, flat=FLAT):
    """(the model's text with its trims casting no shadow, their names): only the geometry, not the animations."""
    geometry, cut, rest = text.partition('\nnewanim ')
    names = []

    def one(match):
        head, name, body, end = match.groups(); sides = extent(body)
        stated = re.search(r'(?im)^\s*shadow\s+(\d+)\s*$', body)  # a mesh that does not say casts one
        if sides is None or (stated and stated.group(1) == '0') or not (sides[1] < thin or sides[0] < small or sides[2] < flat):
            return match.group(0)
        names.append(name)
        if not stated:
            return head + '  shadow 0\n' + body + end
        return head + body[:stated.start(1)] + '0' + body[stated.end(1):] + end
    geometry = NODE.sub(one, geometry)
    return geometry + cut + rest, names


def quiet(repo, tileset, folder, *, thin=THIN, small=SMALL, flat=FLAT):
    """Write the models of a tileset whose trims cast shadows, with those trims quiet, into `folder` (a review's
    overlay; a model already there is changed in place) and tell {model: count of trims}."""
    repo, folder = Path(repo), Path(folder); tileset = tileset.lower(); folder.mkdir(parents=True, exist_ok=True)
    tiles = inventory.drawn_models(repo, tileset)  # the edge tiles round an area's border too
    others = inventory._other_sets(repo, tileset); told, seen = {}, set()
    for pack in lamps.PACKS:
        for path in sorted((repo / pack.format(tileset=tileset)).glob('*.mdl')):
            name = path.stem.lower()
            if name not in tiles or name in seen or others.get(name):  # the first pack's copy is the one the game shows
                continue
            seen.add(name)
            source = folder / path.name if (folder / path.name).is_file() else path; data = source.read_bytes()
            if inventory.compiled(data):
                continue
            text = data.decode('cp1252'); new, names = quieted(text, thin, small, flat)
            if names:
                require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
                (folder / path.name).write_bytes(new.encode('cp1252')); told[name] = len(names)
    return told
