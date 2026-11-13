"""Railway track built here, not generated: a straight piece of standard-gauge track on ballast, written as a model
folder (model.glb and its four maps) that a game set reads as it reads a Meshy download.

A generator draws track a little crooked and to no gauge, and pieces laid end to end must meet: the rail freight depot's
tracks run straight through its tiles on their row centres and on into the tiles beside it (user, 2026-11-13: "is it
possible to incorporate the train tracks?"). So the piece is exact: its rails GAUGE metres apart between their heads,
a sleeper every PITCH metres from half a pitch in, and every map seamless along the track, so that pieces laid end to
end are one track. It is low, its rail tops HEIGHT metres up, under the knee, and a group lays it underfoot (the game
set's `underfoot`): the walkmesh runs flat across it, and it may run off the group's edges.

Measures are in metres in the game's frame: x along the track, y across it, z up."""
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

from . import convert, fresh, local, require

GAUGE = 1.435  # between the rails' heads: standard gauge
HEAD, HEAD_DEPTH, WEB, FOOT, FOOT_DEPTH, RAIL = 0.072, 0.045, 0.018, 0.15, 0.02, 0.172  # the rail's widths and depths
SLEEPER_LENGTH, SLEEPER_WIDTH, PITCH = 2.6, 0.26, 0.625
BED, BED_TOP, BED_BASE = 0.08, 1.45, 1.7  # the ballast's height, and its half widths at the top and at the foot
SLEEPER_FOOT, SLEEPER_TOP = BED - 0.01, BED + 0.06
HEIGHT = SLEEPER_TOP + RAIL
LENGTH = 10.0  # a tile's side: a piece to a tile, laid on its row or column centre
SEGMENT = LENGTH / 2  # the maps repeat along the track every SEGMENT metres
SIZE = 2048
# Bands of the maps, in rows from the top: the ballast's cross-section, two sleeper tops, the sleepers' sides and ends,
# the rail's polished top, its rusted sides and its foot. The rest is plain concrete.
BANDS = {'ballast': (0, 1280), 'sleeperA': (1280, 1408), 'sleeperB': (1408, 1536), 'sleeperSide': (1536, 1600), 'sleeperEnd': (1600, 1632),
         'railTop': (1664, 1712), 'railSide': (1712, 1904), 'railFoot': (1904, 1952)}
INSET = 2  # pixels kept off a band's edge, so that a filtered sample stays inside it
STONE = 16  # pixels to a ballast stone's cell: about four centimetres


def rails():
    """The y of each rail's middle."""
    middle = GAUGE / 2 + HEAD / 2
    return (-middle, middle)


def sleepers():
    """The x of each sleeper's middle on a piece centred on x = 0."""
    return [-LENGTH / 2 + PITCH * (index + 0.5) for index in range(round(LENGTH / PITCH))]


def _bed():
    """[(y, z, distance over the bed's surface from its south foot)] of the ballast's cross-section, and that distance across."""
    slope = float(np.hypot(BED_BASE - BED_TOP, BED))
    return [(-BED_BASE, 0.0, 0.0), (-BED_TOP, BED, slope), (BED_TOP, BED, slope + 2 * BED_TOP), (BED_BASE, 0.0, 2 * slope + 2 * BED_TOP)], 2 * slope + 2 * BED_TOP


def _v(band, across):
    """v of a point `across` (0-1) through a band, kept INSET pixels off its edges."""
    top, bottom = BANDS[band]
    return (top + INSET + across * (bottom - top - 2 * INSET)) / SIZE


class _Mesh:
    def __init__(self):
        self.vertices, self.normals, self.uvs, self.faces = [], [], [], []

    def quad(self, corners, uvs, facing):
        """Two faces over four corners given in order round the quad, wound to face `facing`, which is their normal."""
        corners = np.asarray(corners, float); facing = np.asarray(facing, float) / np.linalg.norm(facing); start = len(self.vertices)
        self.vertices += list(corners); self.uvs += list(np.asarray(uvs, float)); self.normals += [facing] * 4
        forward = np.cross(corners[1] - corners[0], corners[2] - corners[0]) @ facing > 0
        self.faces += ([[start, start + 1, start + 2], [start, start + 2, start + 3]] if forward else [[start, start + 2, start + 1], [start, start + 3, start + 2]])

    def strip(self, band, ends, low, high, facing, across=(0.0, 1.0)):
        """A face along the track from x `ends[0]` to `ends[1]`, between the (y, z) points `low` and `high`, its band's
        texture running along it from u = 0 to 1 and across it from `across[0]` to `across[1]`."""
        (x0, x1), (y0, z0), (y1, z1) = ends, low, high
        self.quad([(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)],
                  [(0.0, _v(band, across[0])), (1.0, _v(band, across[0])), (1.0, _v(band, across[1])), (0.0, _v(band, across[1]))], facing)


def mesh():
    """(vertices, normals, uvs, faces) of one piece, centred on x = y = 0 and standing on z = 0. Each face is flat, its
    corners its own. The faces that look down, the rail head's underside and every floor, are left out: no camera
    above the ground sees them."""
    made = _Mesh(); bed, across = _bed(); foot, web, head = SLEEPER_TOP + FOOT_DEPTH, SLEEPER_TOP + RAIL - HEAD_DEPTH, SLEEPER_TOP + RAIL
    for start in np.arange(-LENGTH / 2, LENGTH / 2 - 1e-9, SEGMENT):
        ends = (start, start + SEGMENT)
        for (y0, z0, d0), (y1, z1, d1) in zip(bed, bed[1:]):
            made.strip('ballast', ends, (y0, z0), (y1, z1), (0.0, z0 - z1, y1 - y0), (d0 / across, d1 / across))
        for middle in rails():
            made.strip('railTop', ends, (middle - HEAD / 2, head), (middle + HEAD / 2, head), (0, 0, 1))
            for side in (-1, 1):  # from the head down; the side band runs from the foot (0) to the head (1)
                made.strip('railSide', ends, (middle + side * HEAD / 2, web), (middle + side * HEAD / 2, head), (0, side, 0), (0.62, 1.0))
                made.strip('railSide', ends, (middle + side * WEB / 2, foot), (middle + side * WEB / 2, web), (0, side, 0), (0.12, 0.62))
                made.strip('railSide', ends, (middle + side * FOOT / 2, SLEEPER_TOP), (middle + side * FOOT / 2, foot), (0, side, 0), (0.0, 0.12))
                made.strip('railFoot', ends, (middle + side * WEB / 2, foot), (middle + side * FOOT / 2, foot), (0, 0, 1))
    for end in (-1, 1):  # the piece's ends, closed where the track stops: the bed's cross-section and each rail's
        x = end * LENGTH / 2
        made.quad([(x, -BED_BASE, 0.0), (x, BED_BASE, 0.0), (x, BED_TOP, BED), (x, -BED_TOP, BED)],
                  [(0.0, _v('ballast', 0.0)), (0.0, _v('ballast', 1.0)), (0.03, _v('ballast', 0.9)), (0.03, _v('ballast', 0.1))], (end, 0, 0))
        for middle in rails():
            for low, high, width, a, b in ((SLEEPER_TOP, foot, FOOT, 0.0, 0.12), (foot, web, WEB, 0.12, 0.62), (web, head, HEAD, 0.62, 1.0)):
                made.quad([(x, middle - width / 2, low), (x, middle + width / 2, low), (x, middle + width / 2, high), (x, middle - width / 2, high)],
                          [(0.0, _v('railSide', a)), (0.02, _v('railSide', a)), (0.02, _v('railSide', b)), (0.0, _v('railSide', b))], (end, 0, 0))
    half, length = SLEEPER_WIDTH / 2, SLEEPER_LENGTH / 2
    for index, x in enumerate(sleepers()):
        x0, x1, top = x - half, x + half, 'sleeperB' if index % 3 == 1 else 'sleeperA'
        down = lambda z: (SLEEPER_TOP - z) / (SLEEPER_TOP - SLEEPER_FOOT)
        made.quad([(x0, -length, SLEEPER_TOP), (x1, -length, SLEEPER_TOP), (x1, length, SLEEPER_TOP), (x0, length, SLEEPER_TOP)],
                  [(0.0, _v(top, 0.0)), (0.0, _v(top, 1.0)), (1.0, _v(top, 1.0)), (1.0, _v(top, 0.0))], (0, 0, 1))
        for side, at in ((-1, x0), (1, x1)):
            made.quad([(at, -length, SLEEPER_FOOT), (at, length, SLEEPER_FOOT), (at, length, SLEEPER_TOP), (at, -length, SLEEPER_TOP)],
                      [(0.0, _v('sleeperSide', down(SLEEPER_FOOT))), (1.0, _v('sleeperSide', down(SLEEPER_FOOT))), (1.0, _v('sleeperSide', 0.0)), (0.0, _v('sleeperSide', 0.0))], (side, 0, 0))
        for side in (-1, 1):
            made.quad([(x0, side * length, SLEEPER_FOOT), (x1, side * length, SLEEPER_FOOT), (x1, side * length, SLEEPER_TOP), (x0, side * length, SLEEPER_TOP)],
                      [(0.0, _v('sleeperEnd', 1.0)), (1.0, _v('sleeperEnd', 1.0)), (1.0, _v('sleeperEnd', 0.0)), (0.0, _v('sleeperEnd', 0.0))], (0, side, 0))
    return np.array(made.vertices), np.array(made.normals), np.array(made.uvs), np.array(made.faces)


def _noise(rows, columns, rng, across, along=None):
    """Smooth noise, periodic both ways, of features about `across` pixels down the rows and `along` along them; mean 0, spread 1."""
    along = across if along is None else along
    frequency = (np.fft.fftfreq(rows)[:, None] * across) ** 2 + (np.fft.fftfreq(columns)[None, :] * along) ** 2
    found = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((rows, columns))) * np.exp(-4 * frequency)))
    return (found - found.mean()) / max(found.std(), 1e-9)


def _stones(rows, columns, rng):
    """(gap, stone) of a field of stones periodic both ways, a stone to each STONE pixels square: the distance from a
    pixel's nearest stone middle to its next, less that to the nearest (0 on the cracks between stones), and the
    nearest stone's number."""
    cells_down, cells_along = rows // STONE, columns // STONE; jitter = rng.random((cells_down, cells_along, 2))
    y, x = np.mgrid[0:rows, 0:columns] / STONE; row, column = np.floor(y).astype(int), np.floor(x).astype(int)
    first = np.full((rows, columns), np.inf); second = first.copy(); stone = np.zeros((rows, columns), int)
    for down in (-1, 0, 1):
        for over in (-1, 0, 1):
            near_row, near_column = row + down, column + over; wrapped = (near_row % cells_down, near_column % cells_along)
            distance = np.hypot(y - near_row - jitter[wrapped][..., 0], x - near_column - jitter[wrapped][..., 1])
            closer = distance < first
            second = np.where(closer, first, np.minimum(second, distance)); stone = np.where(closer, wrapped[0] * cells_along + wrapped[1], stone)
            first = np.minimum(first, distance)
    return second - first, stone


def _smooth(edge0, edge1, value):
    t = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def maps(seed=0):
    """{base_color, metallic, roughness, normal} of the piece as SIZE-square arrays (0-1; colour and normal RGB), each
    seamless from its first column to its last."""
    rng = np.random.default_rng(seed)
    colour = np.empty((SIZE, SIZE, 3)); metal = np.zeros((SIZE, SIZE)); rough = np.full((SIZE, SIZE), 0.9); height = np.zeros((SIZE, SIZE))
    concrete = np.array([0.56, 0.55, 0.53]); rust = np.array([0.36, 0.22, 0.13])
    colour[:] = concrete * (1 + 0.04 * _noise(SIZE, SIZE, rng, 24))[..., None]
    # Ballast: angular stones, each its own grey or brown and domed, lit from the north-west and shut in by the fines
    # between them; rust from the wheels on the stones by the rails, oil down the middle, dust towards the foot.
    top, bottom = BANDS['ballast']; rows = bottom - top
    gap, stone = _stones(rows, SIZE, rng); count = stone.max() + 1
    tones, warm, lift = rng.uniform(0.3, 0.68, count), rng.uniform(0, 1, count), rng.uniform(0.0, 0.4, count)
    base = tones[stone][..., None] * (np.array([0.95, 0.96, 0.98]) * (1 - warm[stone][..., None]) + np.array([1.0, 0.88, 0.76]) * warm[stone][..., None])
    dome = _smooth(0.0, 0.5, gap) ** 0.6 + lift[stone] + 0.05 * _noise(rows, SIZE, rng, 1.5)
    steep = 3.0 * np.stack([-(np.roll(dome, -1, 1) - np.roll(dome, 1, 1)) / 2, (np.roll(dome, -1, 0) - np.roll(dome, 1, 0)) / 2, np.ones_like(dome) / 3.0], -1)
    light = np.array([-0.35, 0.45, 0.82]); light /= np.linalg.norm(light)
    lit = ((steep / np.linalg.norm(steep, axis=-1, keepdims=True)) @ light / light[2]).clip(0.45, 1.35)
    shut = 0.3 + 0.7 * _smooth(0.0, 0.22, gap)
    ballast = base * (lit * shut * (1 + 0.08 * _noise(rows, SIZE, rng, 60)))[..., None]
    fines = (gap < 0.06)[..., None]; ballast = np.where(fines, np.array([0.2, 0.19, 0.17]) * (1 + 0.15 * _noise(rows, SIZE, rng, 1))[..., None], ballast)
    bed, across = _bed(); distance = ((np.arange(rows) + 0.5 - INSET) / (rows - 2 * INSET)).clip(0, 1) * across
    y = np.interp(distance, [d for _, _, d in bed], [one for one, _, _ in bed])[:, None]
    blotch = 0.5 + 0.5 * _noise(rows, SIZE, rng, 40)
    stained = (0.55 * np.exp(-((np.abs(y) - abs(rails()[0])) / 0.28) ** 2) + 0.35 * np.exp(-(y / 0.45) ** 2)) * blotch
    ballast = ballast * (1 - stained[..., None] * 0.55) + rust * 0.7 * stained[..., None] * 0.55
    dust = (0.25 * _smooth(1.1, BED_BASE, np.abs(y)) * (0.6 + 0.4 * blotch))[..., None]
    colour[top:bottom] = ballast * (1 - dust) + np.array([0.52, 0.46, 0.38]) * dust
    height[top:bottom] = dome; rough[top:bottom] = 0.95
    # Sleepers: concrete with dark pads and steel clips where the rails sit, rust run off them; B is the more worn.
    for band, wear in (('sleeperA', 0.0), ('sleeperB', 1.0)):
        top, bottom = BANDS[band]; rows = bottom - top
        u = (np.arange(SIZE) + 0.5)[None, :] / SIZE; v = ((np.arange(rows) + 0.5)[:, None] - INSET) / (rows - 2 * INSET)
        face = concrete * (1 - 0.05 * wear) * (1 + 0.06 * _noise(rows, SIZE, rng, 6) + 0.04 * _noise(rows, SIZE, rng, 1))[..., None]
        edge = np.minimum(np.minimum(v, 1 - v) / 0.08, np.minimum(u, 1 - u) / 0.012).clip(0, 1)
        face = face * (0.78 + 0.22 * edge)[..., None]
        for middle in rails():
            seat = (middle + SLEEPER_LENGTH / 2) / SLEEPER_LENGTH; reach = np.abs(u - seat) * SLEEPER_LENGTH
            stain = np.exp(-(reach / (0.16 + 0.1 * wear)) ** 2) * (0.35 + 0.25 * wear) * (0.7 + 0.3 * _noise(rows, SIZE, rng, 8))
            face = face * (1 - stain[..., None]) + rust * stain[..., None]
            pad = (reach < FOOT / 2 + 0.012) & (v > 0.04) & (v < 0.96)
            face[pad] = [0.12, 0.12, 0.12]
            clip = (np.abs(reach - FOOT / 2 - 0.04) < 0.025) & (np.abs(v - 0.5) < 0.2)
            face[np.broadcast_to(clip, pad.shape)] = [0.34, 0.33, 0.31]; metal[top:bottom][np.broadcast_to(clip, pad.shape)] = 0.7
        colour[top:bottom] = face; height[top:bottom] = 0.15 * _noise(rows, SIZE, rng, 3); rough[top:bottom] = 0.88
    for band in ('sleeperSide', 'sleeperEnd'):
        top, bottom = BANDS[band]; rows = bottom - top; down = (np.arange(rows)[:, None] + 0.5) / rows
        colour[top:bottom] = concrete * ((0.92 - 0.25 * down) * (1 + 0.06 * _noise(rows, SIZE, rng, 4)))[..., None]; rough[top:bottom] = 0.9
    # Rails: a polished running band on the head, rust on every other face.
    top, bottom = BANDS['railTop']; rows = bottom - top; v = ((np.arange(rows) + 0.5)[:, None] - INSET) / (rows - 2 * INSET)
    worn = np.exp(-((v - 0.55) / 0.28) ** 2) * (1 + 0.08 * _noise(rows, SIZE, rng, 2, 60))
    colour[top:bottom] = rust * 0.9 * (1 - worn[..., None]) + np.array([0.68, 0.68, 0.7]) * worn[..., None]
    metal[top:bottom] = 0.2 + 0.7 * worn; rough[top:bottom] = 0.75 - 0.45 * worn
    for band, light in (('railSide', 1.0), ('railFoot', 0.85)):
        top, bottom = BANDS[band]; rows = bottom - top; up = (np.arange(rows)[:, None] + 0.5) / rows
        tone = (0.8 + 0.25 * up if band == 'railSide' else 1.0) * light * (1 + 0.12 * _noise(rows, SIZE, rng, 3, 30))
        colour[top:bottom] = rust * tone[..., None]; metal[top:bottom] = 0.25; rough[top:bottom] = 0.8
    # The normal map from the heights, the way glTF reads it: green up the picture.
    rise_along = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / 2; rise_down = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / 2
    normal = np.stack([-rise_along, rise_down, np.ones_like(height)], -1); normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    return {'base_color': colour.clip(0, 1), 'metallic': metal.clip(0, 1), 'roughness': rough.clip(0, 1), 'normal': normal * 0.5 + 0.5}


def write_glb(path, vertices, normals, uvs, faces):
    """A binary glTF of one mesh under one node, from a mesh in the game's frame (`convert.TO_GAME` turned back)."""
    blobs = [np.asarray(vertices @ convert.TO_GAME, '<f4').tobytes(), np.asarray(normals @ convert.TO_GAME, '<f4').tobytes(),
             np.asarray(uvs, '<f4').tobytes(), np.asarray(faces, '<u4').tobytes()]
    views, offset = [], 0
    for blob in blobs:
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(blob)}); offset += len(blob)
    count = len(vertices); turned = vertices @ convert.TO_GAME
    document = {'asset': {'version': '2.0', 'generator': 'envkit track'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
                'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'NORMAL': 1, 'TEXCOORD_0': 2}, 'indices': 3}]}],
                'buffers': [{'byteLength': offset}], 'bufferViews': views,
                'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': count, 'type': 'VEC3', 'min': turned.min(0).tolist(), 'max': turned.max(0).tolist()},
                              {'bufferView': 1, 'componentType': 5126, 'count': count, 'type': 'VEC3'},
                              {'bufferView': 2, 'componentType': 5126, 'count': count, 'type': 'VEC2'},
                              {'bufferView': 3, 'componentType': 5125, 'count': len(faces) * 3, 'type': 'SCALAR'}]}
    text = json.dumps(document).encode(); text += b' ' * (-len(text) % 4); binary = b''.join(blobs)
    Path(path).write_bytes(b'glTF' + struct.pack('<II', 2, 28 + len(text) + len(binary)) + struct.pack('<II', len(text), 0x4E4F534A) + text
                           + struct.pack('<II', len(binary), 0x004E4942) + binary)


def build(output, seed=0):
    """Write a straight piece into the fresh folder `output`: model.glb, its maps as `texture_0_<map>.png` (`local.MAPS`)
    and track.json, which records its measures, its seed and each file's hash. Returns that record."""
    from PIL import Image
    require(isinstance(seed, int) and seed >= 0, 'A seed is a whole number from 0')
    with fresh(output) as folder:
        write_glb(folder / 'model.glb', *mesh())
        for kind, picture in maps(seed).items():
            require(kind in local.MAPS, 'An unknown map: ' + kind)
            Image.fromarray((picture * 255).round().astype(np.uint8)).save(folder / f'texture_0_{kind}.png')
        record = {'schemaVersion': 1, 'kind': 'envkit-track', 'seed': seed, 'length': LENGTH, 'height': HEIGHT, 'gauge': GAUGE, 'pitch': PITCH,
                  'width': 2 * BED_BASE, 'files': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.iterdir())}}
        (folder / 'track.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8')
    return record
