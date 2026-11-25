"""What a room has overhead: its lamps and beams, and the pictures of its ceilings, all drawn in code.

A room's spec (`rooms`) lists

 lamps: [{kind: one of LAMPS, at: [x, y] its middle, under: the height of the ceiling it is fixed to,
   size: [along x, along y], drop: metres it hangs below that}]
 beams: [{rect: [x0, y0, x1, y1], z: [bottom, top], texture, repeat: metres a picture covers}]

in the metres its props are in. A lamp's face is lit by itself, as a screen is; it casts no light: a tile's light is its own.
"""
import math

import numpy as np

from . import geometry, require

LAMPS = {  # (size along x and y, how deep its housing is, how deep its lit part)
    'panel': ((1.2, 0.6), 0.02, 0.005), 'strip': ((1.2, 0.16), 0.04, 0.06), 'dome': ((0.56, 0.56), 0.03, 0.09), 'spot': ((0.2, 0.2), 0.015, 0.004)}
ROUND_ = {'dome': 16, 'spot': 10}
HOUSING, DIFFUSER = 'srx02_lamphous', 'srx02_lampdif'
LIT = ('ambient 1.0 1.0 1.0', 'diffuse 1.0 1.0 1.0', 'specular 0.0 0.0 0.0', 'shininess 1.0', 'selfillumcolor 1.0 1.0 1.0', 'bitmap {}')
PLAIN = ('ambient 0.588 0.588 0.588', 'diffuse 0.588 0.588 0.588', 'specular 0.0 0.0 0.0', 'shininess 10', 'bitmap {}')


def _hung(outline, bottom, top, repeat, fit=False):
    """(verts, tverts, faces) of a solid hung from a ceiling: its sides and its underside. outline: anticlockwise from
    above. fit: the underside shows the picture once, else one picture covers `repeat` metres."""
    verts, uvs, faces = [], [], []; low = [min(point[axis] for point in outline) for axis in (0, 1)]; size = [max(point[axis] for point in outline) - low[axis] for axis in (0, 1)]
    for number, (a, b) in enumerate(zip(outline, outline[1:] + outline[:1])):  # out of the solid: from a to b seen from outside
        at = len(verts); length = math.dist(a, b)
        verts += [(*a, bottom), (*b, bottom), (*b, top), (*a, top)]
        uvs += [(0, 0), (length / repeat, 0), (length / repeat, (top - bottom) / repeat), (0, (top - bottom) / repeat)] if not fit else [(0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95)]
        group = 1 << (number % 8)
        faces += [(at, at + 1, at + 2, group, at, at + 1, at + 2, 0), (at, at + 2, at + 3, group, at, at + 2, at + 3, 0)]
    at = len(verts); verts += [(x, y, bottom) for x, y in outline]; uvs += [((x - low[0]) / size[0], (y - low[1]) / size[1]) if fit else (x / repeat, y / repeat) for x, y in outline]
    faces += [(at, at + corner + 1, at + corner, 256, at, at + corner + 1, at + corner, 0) for corner in range(1, len(outline) - 1)]
    return verts, uvs, faces


def _outline(middle, size, kind):
    x, y = middle; wide, deep = size[0] / 2, size[1] / 2
    if kind in ROUND_:
        return [(x + wide * math.cos(2 * math.pi * step / ROUND_[kind]), y + deep * math.sin(2 * math.pi * step / ROUND_[kind])) for step in range(ROUND_[kind])]
    return [(x - wide, y - deep), (x + wide, y - deep), (x + wide, y + deep), (x - wide, y + deep)]


def overhead(root, lamps, beams):
    """The nodes of a tile's lamps and beams, one mesh for each picture; none casts a shadow."""
    by = {}

    def add(texture, lit, part):
        verts, uvs, faces = by.setdefault((texture, lit), ([], [], [])); at = len(verts)
        verts += part[0]; uvs += part[1]; faces += [(a + at, b + at, c + at, group, d + at, e + at, f + at, last) for a, b, c, group, d, e, f, last in part[2]]
    for lamp in lamps:
        require(lamp.get('kind') in LAMPS, f'{root}: a lamp is one of ' + ', '.join(LAMPS))
        size, house, lit = LAMPS[lamp['kind']]; size = lamp.get('size', size); under = lamp['under']; drop = lamp.get('drop', 0.0); foot = under - drop - house; margin = 0.03 if lamp['kind'] != 'spot' else 0.02
        if drop > 0.2:  # on two thin rods
            along = 0 if size[0] >= size[1] else 1
            for step in (-0.35, 0.35):
                middle = [lamp['at'][0], lamp['at'][1]]; middle[along] += step * size[along]
                add(HOUSING, False, _hung(_outline(middle, (0.02, 0.02), 'panel'), under - drop, under, 1.0))
        add(HOUSING, False, _hung(_outline(lamp['at'], size, lamp['kind']), foot, under - drop, 1.0))
        add(DIFFUSER, True, _hung(_outline(lamp['at'], [value - 2 * margin for value in size], lamp['kind']), foot - lit, foot, 1.0, fit=True))
    for beam in beams:
        x0, y0, x1, y1 = beam['rect']; require(x0 < x1 and y0 < y1 and beam['z'][0] < beam['z'][1], f'{root}: a beam bounds nothing')
        add(beam['texture'], False, _hung([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], *beam['z'], beam.get('repeat', 1.0)))
    out = []
    for number, ((texture, lit), (verts, uvs, faces)) in enumerate(sorted(by.items())):
        half = geometry.HALF; require(all(max(abs(x), abs(y)) <= half + 1e-6 for x, y, _ in verts), f'{root}: a lamp or beam leaves its tile')
        out += geometry.mesh_text(f'{root}_over{number:02d}', root, tuple(line.format(texture) for line in (LIT if lit else PLAIN)) + ('shadow 0',), verts, uvs, faces)
    return out


# --- the pictures -----------------------------------------------------------------------------------------------------

def _noise(rng, size, cells, octaves=4, fall=0.5):
    """Seamless noise about 0, from `cells` bumps across down to finer ones."""
    grid = np.fft.fftfreq(size) * size; reach = np.hypot(*np.meshgrid(grid, grid)); total = np.zeros((size, size)); share = 1.0
    for octave in range(octaves):
        middle = cells * 2 ** octave; band = np.exp(-((reach - middle) / (0.5 * middle)) ** 2)
        wave = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) * band)); total += share * wave / (wave.std() or 1); share *= fall
    return total / total.std()


def pictures(size=1024):
    """{name: an RGB array} of the ceilings' and lamps' pictures, each seamless."""
    rng = np.random.default_rng(20261125); grey = lambda shade, tint: np.clip(shade[..., None] * np.array(tint), 0, 255).astype('uint8'); out = {}
    out['srx02_clgplas'] = grey(238 + 2.2 * _noise(rng, size, 3, 3) + 2.6 * _noise(rng, size, 90, 3, 0.7), (1.0, 0.992, 0.972))
    board = size // 8; rows = np.arange(size); shade = 148 + 7 * _noise(rng, size, 4, 4) + 4 * _noise(rng, size, 60, 3)  # boards' marks, their seams and the ties' holes
    grain = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) * np.exp(-(np.abs(np.fft.fftfreq(size) * size)[None, :] / 3) ** 2) * np.exp(-(np.abs(np.fft.fftfreq(size) * size)[:, None] / 160) ** 2)))
    shade += 4 * grain / grain.std() + rng.uniform(-7, 7, 8)[rows // board][:, None]
    shade[(rows % board) < 2] -= 26; shade[(rows % board) == 2] += 10
    for x in range(size // 8, size, size // 4):
        for y in range(board + board // 2, size, 4 * board):
            away = np.hypot(*np.meshgrid(rows - x, rows - y)); shade[away < 7] -= 55; shade[(away >= 7) & (away < 10)] += 14
    out['srx02_clgconc'] = grey(shade, (1.0, 0.99, 0.97))
    tile = size // 4; fissures = _noise(rng, size, 70, 3, 0.8); specks = rng.random((size, size)) < 0.012  # four tiles of 0.6 m across, in a white grid
    shade = 226 + 1.5 * _noise(rng, size, 5, 2) - 22 * (fissures > 1.9) - 20 * specks + rng.uniform(-3, 3, (4, 4))[rows // tile][:, rows // tile]
    edge = np.minimum(rows % tile, tile - 1 - rows % tile); near = np.minimum(edge[:, None], edge[None, :])
    shade = np.where(near < 5, 240, np.where(near < 7, 150, np.where(near < 10, shade - 18, shade)))
    out['srx02_clgtile'] = grey(shade, (1.0, 0.998, 0.985))
    small = 256; rows = np.arange(small); ridge = ((rows // 4) % 2)[:, None] ^ ((rows // 4) % 2)[None, :]; edge = np.minimum(rows, small - 1 - rows); near = np.minimum(edge[:, None], edge[None, :])
    out['srx02_lampdif'] = grey(np.where(near < 6, 205, 246 + 7 * ridge - 10 * (near < 20)), (1.0, 0.985, 0.94))
    out['srx02_lamphous'] = grey(196 + 3 * _noise(rng, small, 20, 2), (1.0, 1.0, 1.0))
    return out


def write(folder, crunch):
    """Write the pictures into a pack's folder as plain DDS. [file names]."""
    from . import material
    return [file for name, picture in pictures().items() for file in material.write(name, {'colour': picture, 'normal': picture, **dict.fromkeys(('metal', 'roughness'), np.zeros(picture.shape[:2]))}, folder, crunch, plain=True)]
