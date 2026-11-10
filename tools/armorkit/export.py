"""Write split parts as game models: an ASCII model and a tint texture per part, then the compiled binary.

A part model hangs on its bone, so its vertices and normals are written in that bone's space. A part's whole
texture is one tint texture named like its model. Normals are written out, not left to the compiler: taken on
the outfit before it is split and carried through the cut as extra columns beside the texture coordinates,
they keep the shading continuous across a joint, where normals taken on each part alone would crease.
"""
import subprocess
from pathlib import Path

import numpy as np

from . import registry, seams, toolchain
from .registry import require

# The layer a tint texture stores per pixel for each colour channel of the registry.
LAYERS = {'skin': 0, 'metal1': 2, 'metal2': 3, 'cloth1': 4, 'cloth2': 5, 'leather1': 6, 'leather2': 7}
TINT_HEADER = b'PLT V1  ' + (10).to_bytes(4, 'little') + bytes(4)


def vertex_normals(vertices, faces):
    """A unit normal per vertex: its faces' normals weighted by their area."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    of_face = np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]])
    total = np.zeros_like(vertices)
    for corner in range(3):
        np.add.at(total, faces[:, corner], of_face)
    length = np.linalg.norm(total, axis=1)
    return np.where(length[:, None] > 1e-12, total / np.maximum(length, 1e-12)[:, None], (0.0, 0.0, 1.0))


def to_bone(points, bone, direction=False):
    """Body-space points in the space of a bone, given its 4x4 bind matrix; with `direction`, unit directions."""
    points, bone = np.asarray(points, float), np.asarray(bone, float)
    if direction:
        turned = points @ seams.rotation(bone)
        return turned / np.maximum(np.linalg.norm(turned, axis=1), 1e-12)[:, None]
    return (points - bone[:3, 3]) @ np.linalg.inv(bone[:3, :3]).T


def model_text(name, vertices, faces, uvs, normals):
    """The ASCII model of one rigid part: a root and one mesh, laid out as the stock part models are."""
    vertices, faces, uvs, normals = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float), np.asarray(normals, float)
    require(len(name) <= 16 and name == name.lower(), 'A model name is a lowercase resref: ' + name)
    require(len(faces) and vertices.shape == normals.shape == (len(vertices), 3) and uvs.shape == (len(vertices), 2),
            name + ': a part needs faces, and a position, a normal and a texture coordinate per vertex')
    require(faces.shape[1:] == (3,) and faces.min() >= 0 and faces.max() < len(vertices), name + ': a face names a vertex that does not exist')
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
    bone = rig[seams.BONES[token]]
    folder = Path(folder)
    text = model_text(name, to_bone(vertices, bone), faces, uvs, to_bone(normals, bone, direction=True))
    (folder / (name + '.mdl')).write_text(text, encoding='cp1252', newline='\n')
    (folder / (name + '.plt')).write_bytes(tint(*texture))
    return name


def compile_models(sources, output, *, tool=None, game=None, resources=()):
    """Compile ASCII models into the folder `output` with the pinned cleanmodels; returns the compiled paths.

    game: the game install folder, when cleanmodels cannot find it by itself. resources: folders or packs it
    may read supermodels and materials from. A model that fails, or leaves no file, raises ValueError."""
    tool = tool or toolchain.cleanmodels()
    output = Path(output)
    command = [tool['path'], 'compile', '--overwrite']
    if game is not None:
        command += ['--game-dir', str(game)]
    for resource in resources:
        command += ['--resource-dir', str(resource)]
    compiled = []
    for source in map(Path, sources):
        target = output / source.name
        result = subprocess.run([*command, str(source), str(target)], capture_output=True, text=True, timeout=300,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(result.returncode == 0 and target.is_file(), f'{source.name} did not compile: ' + (result.stdout + result.stderr)[-800:])
        compiled.append(target)
    return compiled
