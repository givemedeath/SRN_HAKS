"""Write split parts as game models: an ASCII model and a tint texture per part, then the compiled binary.

A part model hangs on its bone, so its vertices and normals are written in that bone's space. A part's whole
texture is one tint texture named like its model. Normals are written out, not left to the compiler: taken on
the outfit before it is split and carried through the cut as extra columns beside the texture coordinates,
they keep the shading continuous across a joint, where normals taken on each part alone would crease.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from tools.headkit import native_reader
from tools.robes import mesh_ops

from . import registry, seams, toolchain
from .registry import require

# The layer a tint texture stores per pixel for each colour channel of the registry.
LAYERS = {'skin': 0, 'metal1': 2, 'metal2': 3, 'cloth1': 4, 'cloth2': 5, 'leather1': 6, 'leather2': 7}
TINT_HEADER = b'PLT V1  ' + (10).to_bytes(4, 'little') + bytes(4)
WELD = 1e-5  # vertices this close share one normal: a source repeats its vertices along texture seams


def vertex_normals(vertices, faces, weld=WELD):
    """A unit normal per vertex: the normals of the faces at its position, weighted by their area.

    Vertices at one position get one normal, so a texture seam does not show as a crease."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    of_face = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    place = mesh_ops.weld_ids(vertices, weld)
    total = np.zeros((place.max() + 1, 3))
    for corner in range(3):
        np.add.at(total, place[faces[:, corner]], of_face)
    length = np.linalg.norm(total, axis=1)
    return np.where(length[:, None] > 1e-12, total / np.maximum(length, 1e-12)[:, None], (0.0, 0.0, 1.0))[place]


def to_bone(points, bone, direction=False):
    """Body-space points in the space of a bone, given its 4x4 bind matrix; with `direction`, unit normals."""
    points, bone = np.asarray(points, float), np.asarray(bone, float)
    if direction:  # a normal goes through the transpose of the matrix its surface goes through the inverse of
        turned = points @ bone[:3, :3]
        return turned / np.maximum(np.linalg.norm(turned, axis=1), 1e-12)[:, None]
    return (points - bone[:3, 3]) @ np.linalg.inv(bone[:3, :3]).T


def model_text(name, vertices, faces, uvs, normals):
    """The ASCII model of one rigid part: a root and one mesh, laid out as the stock part models are."""
    vertices, faces, uvs, normals = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float), np.asarray(normals, float)
    require(len(name) <= 16 and name == name.lower(), 'A model name is a lowercase resref: ' + name)
    require(len(faces) and vertices.shape == normals.shape == (len(vertices), 3) and uvs.shape == (len(vertices), 2),
            name + ': a part needs faces, and a position, a normal and a texture coordinate per vertex')
    require(faces.shape[1:] == (3,) and faces.min() >= 0 and faces.max() < len(vertices), name + ': a face names a vertex that does not exist')
    require(all(np.isfinite(values).all() for values in (vertices, uvs, normals)), name + ': a coordinate is not a number')
    lines = ['#MAXMODEL ASCII', f'newmodel {name}', 'classification CHARACTER', f'setsupermodel {name} NULL', 'setanimationscale 1',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode',
             f'node trimesh {name}g', f'  parent {name}', '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 1',
             f'  bitmap {name}', '  render 1', '  shadow 1', f'  verts {len(vertices)}']
    lines += [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in vertices.tolist()]
    lines += [f'  tverts {len(uvs)}'] + [f'    {u:.6f} {v:.6f} 0' for u, v in uvs.tolist()]
    lines += [f'  normals {len(normals)}'] + [f'    {x:.6f} {y:.6f} {z:.6f}' for x, y, z in normals.tolist()]
    lines += [f'  faces {len(faces)}'] + [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in faces.tolist()]
    return '\n'.join(lines + ['endnode', f'endmodelgeom {name}', f'donemodel {name}']) + '\n'


def tint(shades, layers):
    """The bytes of a tint texture: per pixel a shade 0-255 and the layer of its colour channel.

    Rows are stored in the order given, and the game puts the first row at texture coordinate v = 0 (spike
    record, section 21)."""
    shades, layers = np.asarray(shades), np.asarray(layers)
    require(shades.ndim == 2 and shades.shape == layers.shape and shades.size, 'A tint texture needs a shade and a layer per pixel')
    require(set(np.unique(layers).tolist()) <= set(LAYERS.values()) and shades.min() >= 0 and shades.max() <= 255,
            'Tint layers are those of the colour channels and shades are 0-255')
    height, width = shades.shape
    return TINT_HEADER + width.to_bytes(4, 'little') + height.to_bytes(4, 'little') + np.stack([shades, layers], axis=2).astype(np.uint8).tobytes()


def read_tint(blob):
    """(shades, layers) of a tint texture's bytes."""
    require(blob[:16] == TINT_HEADER and len(blob) >= 24, 'Not a tint texture')
    width, height = int.from_bytes(blob[16:20], 'little'), int.from_bytes(blob[20:24], 'little')
    require(len(blob) == 24 + 2 * width * height, 'The tint texture is cut short or overlong')
    pixels = np.frombuffer(blob, np.uint8, offset=24).reshape(height, width, 2)
    return pixels[:, :, 0], pixels[:, :, 1]


def write_part(folder, body, token, number, mesh, rig, texture):
    """Write `<model>.mdl` as ASCII and `<model>.plt` into `folder` for one part; returns the model name.

    mesh: (vertices, faces, uvs, normals) in body space. rig: {bone: 4x4 bind matrix} of the body.
    texture: (shades, layers) for `tint`."""
    name = registry.model_name(body, token, number)
    vertices, faces, uvs, normals = mesh
    bone = np.asarray(rig[seams.BONES[token]], float)
    require(np.linalg.det(bone[:3, :3]) > 0, name + ': a mirrored bone would turn the part inside out')
    folder = Path(folder)
    text = model_text(name, to_bone(vertices, bone), faces, uvs, to_bone(normals, bone, direction=True))
    (folder / (name + '.mdl')).write_text(text, encoding='cp1252', newline='\n')
    (folder / (name + '.plt')).write_bytes(tint(*texture))
    return name


def compile_models(sources, output, *, tool=None, game=None, resources=()):
    """Compile ASCII models into the folder `output` with the pinned cleanmodels; returns the compiled paths.

    The models go to the tool in one call, and each one's tint texture, where it lies beside the source, is
    copied along, so the folder holds everything the parts need. game: the game install folder, when
    cleanmodels cannot find it by itself. resources: folders or packs it may read supermodels and materials
    from. `output` must not be a folder the sources are in: the tool would compile them in place.

    A model the tool reports an error for, that leaves no file, or whose compiled mesh does not have the
    source's number of faces raises ValueError: a source cut short compiles without complaint to a model
    with no mesh."""
    sources, output = [Path(source) for source in sources], Path(output)
    if not sources:
        return []
    require(all(source.parent.resolve() != output.resolve() for source in sources), 'Compile into a folder other than the sources\'')
    require(len({source.name for source in sources}) == len(sources), 'Two sources share a name')
    tool = tool or toolchain.cleanmodels()
    command = [tool['path'], 'compile', '--overwrite', '--json']
    if game is not None:
        command += ['--game-dir', str(game)]
    for resource in resources:
        command += ['--resource-dir', str(resource)]
    targets = [output / source.name for source in sources]
    # One input names its output file; several name the folder their outputs go to.
    result = subprocess.run([*command, *map(str, sources), str(targets[0] if len(sources) == 1 else output)], capture_output=True,
                            text=True, timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    said = (result.stdout + result.stderr)[-800:]
    starts = [position for position in (result.stdout.find('['), result.stdout.find('{')) if position >= 0]
    try:  # the report is a list, or one object for one input; the tool may print a note before it
        report = json.JSONDecoder().raw_decode(result.stdout[min(starts):])[0] if starts else None
    except ValueError:
        report = None
    entries = report if isinstance(report, list) else [report] if isinstance(report, dict) else []
    failed = [Path(entry['file']).name for entry in entries if isinstance(entry, dict) and entry.get('error')]
    require(result.returncode == 0 and not failed and len(entries) == len(sources), f'{", ".join(failed) or "The models"} did not compile: {said}')
    for source, target in zip(sources, targets):
        require(target.is_file(), f'{source.name} did not compile: {said}')
        wanted = sum(int(count) for count in re.findall(r'^\s*faces (\d+)', source.read_text(encoding='cp1252'), re.M))
        require(wanted > 0, f'{source.name} holds no faces')
        try:
            got = sum(len(mesh['faces']) for mesh in native_reader.decode(target.read_bytes(), source.stem, require_tangents=False, apply_rigid_transforms=True))
        except ValueError as error:
            raise ValueError(f'{source.name} compiled to a model that cannot be read back: {error}') from error
        require(got == wanted, f'{source.name} compiled to {got} faces, not the {wanted} of its source')
        texture = source.with_suffix('.plt')
        if texture.is_file():
            shutil.copyfile(texture, output / texture.name)
    return targets
