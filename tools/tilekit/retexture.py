"""A tileset's tiles pointed at their own copies of shared textures, and their coloured meshes made white.

A texture several tilesets draw is restyled for all of them at once. Where one of them should keep the old look, the
restyled set draws a copy under a new name instead: the starship interior keeps its beige slab floor `d_ground03`, and
the Futuristic City draws `fcx_ground03` (user, 2026-11-24). The material spec makes the copy (`copy`); here the
tiles' meshes are given its name.

A mesh also carries colours of its own, which the game multiplies into its texture and adds as glow. The Futuristic
City's monument was red and its sign yellow by those colours, whatever was drawn on them (2026-11-24): `whitened`
gives such a mesh white surface colours, and a white glow where it glowed.

The list (`docs/tilesets/<set>/retexture.json`): {"tileset", "copies": {shared texture: the set's own copy},
"white": [textures whose meshes take white colours]}. `write` puts the changed models in a review's overlay."""
import re
from pathlib import Path

from . import inventory, require
from .lamps import PACKS

RESREF = 16
MESH = re.compile(r'(?ims)^[ \t]*node[ \t]+(?:trimesh|danglymesh|skin|animmesh)[ \t]+(\S+).*?^[ \t]*endnode')
BITMAP = re.compile(r'(?im)^([ \t]*(?:bitmap|texture0)[ \t]+)(\S+)')
COLOUR = re.compile(r'(?im)^([ \t]*(selfillumcolor|ambient|diffuse)[ \t]+)([^\r\n]*?)([ \t]*)(?=\r?$)')
WHITE = '1.0 1.0 1.0'


def _geometry(text):
    """(a model's geometry, its animations): only the first is changed."""
    start = re.search(r'(?im)^[ \t]*newanim[ \t]', text)
    return (text[:start.start()], text[start.start():]) if start else (text, '')


def renamed(text, copies):
    """(the model's text with every mesh that draws a texture of `copies` drawing its copy, {texture: copy} as used).
    The walkmesh is no mesh here: what it names is left, as is everything else of it."""
    wanted = {old.lower(): new for old, new in copies.items()}; used = {}
    geometry, rest = _geometry(text)

    def one(found):
        new = wanted.get(found.group(2).lower())
        if new is None:
            return found.group(0)
        used[found.group(2).lower()] = new; return found.group(1) + new
    return MESH.sub(lambda mesh: BITMAP.sub(one, mesh.group(0)), geometry) + rest, used


def whitened(text, textures):
    """(the model's text with the meshes drawing one of `textures` white, their names). A mesh's surface colours become
    white; its glow becomes white only where it glowed, so a mesh that was unlit stays unlit."""
    wanted = {one.lower() for one in textures}; meshes = []
    geometry, rest = _geometry(text)

    def one(found):
        block = found.group(0); bitmap = BITMAP.search(block)
        if not bitmap or bitmap.group(2).lower() not in wanted:
            return block
        glows = any(float(value) > 0 for line in COLOUR.finditer(block) if line.group(2).lower() == 'selfillumcolor' for value in line.group(3).split())
        new = COLOUR.sub(lambda line: line.group(1) + (line.group(3) if line.group(2).lower() == 'selfillumcolor' and not glows else WHITE) + line.group(4), block)
        if new != block:
            meshes.append(found.group(1))
        return new
    return MESH.sub(one, geometry) + rest, meshes


def checked(spec):
    """A retexture list's ({texture: copy}, [white textures]), each name one a model can carry."""
    copies, white = spec.get('copies', {}), spec.get('white', [])
    require(isinstance(copies, dict) and isinstance(white, list) and (copies or white), 'A retexture list has `copies` or `white`')
    for name in list(copies) + list(copies.values()) + list(white):
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_\-]{1,%d}' % RESREF, name), f'{name}: a texture\'s name is at most {RESREF} letters, digits, _ or -')
    low = [new.lower() for new in copies.values()]
    require(len(set(low)) == len(low) and not set(low) & {old.lower() for old in copies}, 'Each copy has a name of its own, and none is a texture copied')
    return copies, white


def write(repo, tileset, spec, folder, *, shared=()):
    """Write the changed models of a tileset into `folder` (a review's overlay; a model already there is changed in
    place) and tell {model: {'copies': {texture: copy}, 'white': [meshes]} or 'shared with ...'}. A model another
    tileset draws too is left, unless that tileset is in `shared` (the merged set, which takes the change with the
    tile). A model whose walkmesh would differ afterwards is a refusal: nothing here touches one."""
    from .apply import noted
    copies, white = checked(spec); folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, PACKS):
        new, used = renamed(text, copies); new, meshes = whitened(new, white)
        if new == text:
            continue
        if set(others) - {one.lower() for one in shared}:
            told[name] = 'shared with ' + ', '.join(others); continue
        require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
        noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252'))
        told[name] = {**({'copies': used} if used else {}), **({'white': meshes} if meshes else {})}
    return told
