"""Shared, deterministic helpers for the LEAN reduction pipeline (no Blender, no client).

Every LEAN step reads declared {path, sha256} inputs, writes a fresh output directory and records a receipt whose
frozenInputs pin every consumed file and helper. Inputs are re-verified before the receipt is written.
"""
import hashlib
import json
from pathlib import Path
import re
import struct

import numpy as np

PARTS = ('bicepl', 'bicepr', 'chest', 'footl', 'footr', 'forel', 'forer', 'handl', 'handr', 'legl', 'legr', 'pelvis', 'shinl', 'shinr')
JOINTS = {'chest': 'torso_g', 'pelvis': 'pelvis_g', 'bicepl': 'lbicep_g', 'bicepr': 'rbicep_g', 'forel': 'lforearm_g',
          'forer': 'rforearm_g', 'handl': 'lhand_g', 'handr': 'rhand_g', 'legl': 'lthigh_g', 'legr': 'rthigh_g',
          'shinl': 'lshin_g', 'shinr': 'rshin_g', 'footl': 'lfoot_g', 'footr': 'rfoot_g'}
NEIGHBOURS = {'chest': ['pelvis', 'bicepl', 'bicepr'], 'pelvis': ['chest', 'legl', 'legr'], 'bicepl': ['chest', 'forel'],
              'bicepr': ['chest', 'forer'], 'forel': ['bicepl', 'handl'], 'forer': ['bicepr', 'handr'], 'handl': ['forel'],
              'handr': ['forer'], 'legl': ['pelvis', 'shinl'], 'legr': ['pelvis', 'shinr'], 'shinl': ['legl', 'footl'],
              'shinr': ['legr', 'footr'], 'footl': ['shinl'], 'footr': ['shinr']}
ATLAS = 2048


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pin(path):
    path = Path(path).resolve(); return {'path': str(path), 'sha256': sha(path)}


def exact(row):
    """Verify an exact {path, sha256} pin and return the resolved path."""
    require(isinstance(row, dict) and set(row) >= {'path', 'sha256'}, 'Exact path/sha256 pin required')
    path = Path(row['path']).resolve()
    require(path.is_file() and sha(path) == row['sha256'], 'Pinned input changed: '+str(path))
    return path


class Frozen:
    """Records every consumed file once; refuses a changed byte stream within one run."""
    def __init__(self):
        self.files = {}

    def take(self, path):
        path = Path(path).resolve(); digest = sha(path)
        require(self.files.get(str(path), digest) == digest, 'Input changed during the run: '+str(path))
        self.files[str(path)] = digest; return path

    def pinned(self, row):
        return self.take(exact(row))

    def verify(self):
        for path, digest in self.files.items():
            require(sha(path) == digest, 'Input changed before the receipt: '+path)
        return dict(sorted(self.files.items()))


def fresh(output):
    output = Path(output).resolve()
    require(not output.exists(), 'Fresh output directory required: '+str(output))
    output.mkdir(parents=True); return output


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=1)+'\n', encoding='utf-8'); return pin(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def helper_pins(*names):
    here = Path(__file__).resolve().parent
    return {str(here/name): sha(here/name) for name in ('lean_common.py', *names)}


def mode(values):
    unique, counts = np.unique(np.asarray(values), return_counts=True)
    return int(unique[np.argmax(counts)])


def mtr_textures(text):
    """texture slots and Roughness parameter of an MTR."""
    out = {}
    for line in re.sub(r'//[^\n]*', '', text).splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].lower().startswith('texture'):
            out[parts[0].lower()] = parts[1].lower()
        if len(parts) == 4 and parts[0] == 'parameter' and parts[2] == 'Roughness':
            out['roughness'] = float(parts[3])
    return out


def tga_read(path):
    data = Path(path).read_bytes(); id_length = data[0]
    width, height, depth, descriptor = struct.unpack_from('<HHBB', data, 12)
    require(data[2] == 2 and depth == 24, 'Uncompressed 24-bit TGA expected: '+str(path))
    offset = 18+id_length; count = width*height*3
    pixels = np.frombuffer(data, np.uint8, offset=offset, count=count).reshape(height, width, 3)[:, :, ::-1]
    top = bool(descriptor & 0x20)
    return {'head': data[:offset], 'tail': data[offset+count:], 'top': top}, (pixels if top else pixels[::-1]).copy()


def tga_write(path, meta, image):
    rows = image if meta['top'] else image[::-1]
    Path(path).write_bytes(meta['head']+np.ascontiguousarray(rows[:, :, ::-1]).tobytes()+meta['tail'])


def interp(values, faces, face_ids, bary):
    return (values[faces[face_ids]]*bary[:, :, None]).sum(1)


def tbn(normal, tangent, handedness):
    normal = normal/np.linalg.norm(normal, axis=1)[:, None]
    tangent = tangent/np.maximum(np.linalg.norm(tangent, axis=1), 1e-12)[:, None]
    signs = np.where(handedness < 0, -1.0, 1.0)
    return normal, tangent, np.cross(normal, tangent)*signs[:, None]


def dilate_values(buffer, filled, iterations):
    """4-neighbour mean dilation of a vector buffer into unfilled texels (np.roll wraps, as the study bake)."""
    buffer = buffer.copy(); filled = filled.copy()
    for _ in range(iterations):
        acc = np.zeros_like(buffer); count = np.zeros(filled.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(np.roll(filled, dy, 0), dx, 1)
            acc += np.roll(np.roll(buffer, dy, 0), dx, 1)*shifted[..., None]; count += shifted
        grown = ~filled & (count > 0); buffer[grown] = acc[grown]/count[grown][:, None]; filled = filled | grown
    return buffer, filled


def model_name(prefix, part):
    return '%s_%s001' % (prefix, part)
