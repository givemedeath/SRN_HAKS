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
    out.update(_older(rng, size))  # drawn after the others, so their pictures stay as they were
    return out


def _streaks(rng, size, across, along):
    """Seamless noise that changes fast across x (`across` cells) and slowly down y (`along` cells): wood grain, rust runs."""
    frequency = np.fft.fftfreq(size) * size
    wave = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) * np.exp(-(np.abs(frequency)[None, :] / across) ** 2) * np.exp(-(np.abs(frequency)[:, None] / along) ** 2)))
    return wave / (wave.std() or 1)


def _older(rng, size):
    """The ceilings of older and poorer rooms (user: the magic and Barrens rooms "need more appropriate ceilings",
    2026-11-26): dark timber boards, stained plaster, and rusted corrugated sheet. One picture covers 2.4 m."""
    out = {}; rows = np.arange(size); colour = lambda shade, tint: np.clip(shade[..., None] * np.asarray(tint, float), 0, 255).astype('uint8')
    # timber boards along x, 15 cm wide, each its own tone, with butt joints, nail heads and old water marks
    board = size // 16; which = rows // board; grain = _streaks(rng, size, 160, 3).T
    shade = 100 * (1 + rng.uniform(-0.13, 0.13, 16)[which][:, None]) + 7 * grain + 5 * _noise(rng, size, 6, 3)
    shade[(rows % board) < 2] *= 0.45; shade[(rows % board) == 2] *= 1.12
    for number in range(16):
        band = slice(number * board + 2, (number + 1) * board)
        for joint in rng.choice(size, 2, replace=False):
            shade[band, joint:joint + 2] *= 0.5
            for side in (-9, 9):
                for depth in (board // 3, 2 * board // 3):
                    away = np.hypot(*np.meshgrid((rows - (joint + side) % size), rows - (number * board + depth)))
                    shade[away < 2.5] *= 0.55
    stains = _noise(rng, size, 3, 3); shade *= 1 - 0.16 * np.clip(stains - 0.9, 0, 1.2)  # soft dark water marks
    out['srx02_clgbord'] = colour(shade, (1.0, 0.66, 0.43))
    # old plaster, yellowed, with tide-marked water stains and fine cracks
    shade = 212 + 4 * _noise(rng, size, 4, 3) + 2.5 * _noise(rng, size, 80, 3, 0.7); wet = _noise(rng, size, 3, 3)
    cracks = (np.abs(_noise(rng, size, 30, 3, 0.8)) < 0.03) & (_noise(rng, size, 4, 2) > 0.6)
    damp = np.clip(wet - 1.3, 0, 1); shade = shade - 14 * damp - 10 * np.exp(-((wet - 1.3) / 0.04) ** 2) - 30 * cracks  # faint tide line
    tint = (1.0, 0.975, 0.92) - damp[..., None] * np.array((0.0, 0.05, 0.13))
    out['srx02_clgplst'] = np.clip(shade[..., None] * tint, 0, 255).astype('uint8')
    # corrugated sheet: ridges along y every 7.5 cm, sheets lapped every 60 cm with screws on the crests, rust in runs
    ridges = 32; phase = 2 * np.pi * ridges * rows / size; light = np.tile(118 + 24 * np.sin(phase), (size, 1))
    sheet = size // 4; lap = rows % sheet; light = light * np.where(lap < 3, 0.55, np.where(lap < 6, 1.1, 1.0))[:, None]
    for lap in range(0, size, sheet):
        for crest in range(0, ridges, 3):
            x = int((crest + 0.25) * size / ridges); away = np.hypot(*np.meshgrid(rows - x, rows - (lap + 9))); light[away < 3] *= 0.5
    rust = np.clip(0.4 * (0.6 * _noise(rng, size, 5, 4, 0.6) + 0.5 * _streaks(rng, size, 40, 2) + 0.2), 0, 0.85)
    grime = np.clip(0.25 + _noise(rng, size, 6, 3) * 0.3, 0, 0.7)
    zinc = np.stack([light * 1.0, light * 1.01, light * 0.99], -1); red = np.stack([light * 0.8, light * 0.5, light * 0.32], -1)
    out['srx02_clgcorr'] = np.clip((zinc * (1 - rust[..., None]) + red * rust[..., None]) * (1 - 0.35 * grime[..., None]), 0, 255).astype('uint8')
    return out


def write(folder, crunch):
    """Write the pictures into a pack's folder as plain DDS. [file names]."""
    from . import material
    return [file for name, picture in pictures().items() for file in material.write(name, {'colour': picture, 'normal': picture, **dict.fromkeys(('metal', 'roughness'), np.zeros(picture.shape[:2]))}, folder, crunch, plain=True)]


# A tile open to the sky over its floor gets a ceiling at its walls' top (user, 2026-11-26: "appropriate ceilings on the
# rooms that are missing them"). Modern Interior (tfb01) was drawn without any.
COVERED = 0.95  # a tile whose walked floor is this much under something above `HEADROOM` has its ceiling already
HEADROOM = 2.4  # metres: what is higher over the floor than this is overhead
STOREY = 3.0  # metres: the walls' top of most of tfb01's rooms
CLEAR = 2.6  # metres a ceiling stays above any floor walked under it: a male troll is 2.5 m (contract 1.3.0)
UPPER = 0.8  # share of a tile's floor walked high that makes it an upper storey, not a stair


def _tops(nodes):
    """{height of a wall's top, to 0.1 m: faces}: the near-upright faces higher than two metres, by their top."""
    import collections
    told = collections.Counter()
    for a, b, c in geometry.triangles(nodes):
        across = np.cross(np.subtract(b, a), np.subtract(c, a)); length = np.linalg.norm(across)
        if length > 1e-9 and abs(across[2]) / length < 0.2 and max(a[2], b[2], c[2]) > 2:
            told[round(max(a[2], b[2], c[2]), 1)] += 1
    return told


def _faced(quads, repeat):
    """(verts, tverts, faces) of quads [(four corners, the way they face)], each turned to face that way, the picture
    laid flat on level ones and along the wall on upright ones, one picture to `repeat` metres."""
    verts, uvs, faces = [], [], []
    for corners, toward in quads:
        corners = [tuple(map(float, corner)) for corner in corners]
        if np.dot(np.cross(np.subtract(corners[1], corners[0]), np.subtract(corners[2], corners[0])), toward) < 0:
            corners = corners[::-1]
        at = len(verts); verts += corners
        level = abs(toward[2]) > 0.5
        uvs += [((x / repeat, y / repeat) if level else ((x + y) / repeat, z / repeat)) for x, y, z in corners]
        faces += [(at, at + 1, at + 2, 1, at, at + 1, at + 2, 0), (at, at + 2, at + 3, 1, at, at + 2, at + 3, 0)]
    return verts, uvs, faces


def _rect(x0, y0, x1, y1, z):
    return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]


def lid(high, well=None, repeat=2.0):
    """(verts, tverts, faces) of a ceiling over a whole cell at `high`, facing down; with a `well` ([x0, y0, x1, y1],
    top) it is open over that rectangle, and a shaft with four sides and its own lid at `top` closes it (a stair rises
    into it)."""
    half = geometry.HALF; down = (0, 0, -1)
    if well is None:
        return _faced([(_rect(-half, -half, half, half, high), down)], repeat)
    (x0, y0, x1, y1), top = well
    quads = [(_rect(-half, -half, half, y0, high), down), (_rect(-half, y1, half, half, high), down),
             (_rect(-half, y0, x0, y1, high), down), (_rect(x1, y0, half, y1, high), down), (_rect(x0, y0, x1, y1, top), down)]
    for (ax, ay), (bx, by), inward in (((x0, y0), (x1, y0), (0, 1, 0)), ((x1, y0), (x1, y1), (-1, 0, 0)), ((x1, y1), (x0, y1), (0, -1, 0)), ((x0, y1), (x0, y0), (1, 0, 0))):
        quads.append(([(ax, ay, high), (bx, by, high), (bx, by, top), (ax, ay, top)], inward))
    return _faced([quad for quad in quads if _area(quad[0]) > 1e-6], repeat)


def _area(corners):
    a, b, c, _ = (np.asarray(corner, float) for corner in corners)
    return np.linalg.norm(np.cross(b - a, c - a))


def capped(text, root, texture, repeat=2.0):
    """(the model with a ceiling over its cell, its height) or (None, why not). Seen from below only: a camera over the
    room looks through it. Every tile of a storey takes `STOREY`, so that neighbours open to each other meet with no
    step between their ceilings (a tile ceiled at its tallest walls' top left sky between it and the next, 2026-11-27).
    Over a stair, the part of the floor walked higher than `CLEAR` under it rises into a closed well; a floor walked
    higher all over (an upper storey) takes the lowest walls' top `CLEAR` above it, else a `STOREY` over it."""
    _, _, nodes = geometry.parse(text); walk = geometry.walkable(nodes, step=0.5)
    if not walk:
        return None, 'no floor walked'
    over = {}  # {cell: the highest bottom of what passes over it}
    for triangle in geometry.triangles(nodes):
        bottom = min(point[2] for point in triangle)
        for point in geometry.samples(triangle, 0.25):
            spot = geometry.cell(point, 0.5); over[spot] = max(over.get(spot, bottom), bottom)
    if sum(over.get(spot, -1e9) >= min(heights) + HEADROOM for spot, heights in walk.items()) >= COVERED * len(walk):
        return None, 'ceiled already'
    tops = _tops(nodes); high = STOREY  # one height for a storey: a tile's tall parts (a chimney, columns, an arch) run on above it
    up = [spot for spot, heights in walk.items() if max(heights) + CLEAR > high + 0.01]
    well = None
    if len(up) >= UPPER * len(walk):  # an upper storey: the lowest walls' top clear of its floor, else a storey over it
        walked = max(max(heights) for heights in walk.values())
        high = min((top for top, count in tops.items() if count >= 4 and top >= walked + CLEAR - 0.01), default=round(walked + STOREY, 1))
    elif up:  # a stair: a well over the part walked high, as high as its highest step needs
        step = 0.5; xs = [spot[0] * step for spot in up]; ys = [spot[1] * step for spot in up]; half = geometry.HALF
        rect = [max(-half, min(xs) - 0.25), max(-half, min(ys) - 0.25), min(half, max(xs) + step + 0.25), min(half, max(ys) + step + 0.25)]
        top = math.ceil((max(max(walk[spot]) for spot in up) + CLEAR) * 10) / 10
        well = (rect, max(top, high + 0.5))
    require(not any(node.name.lower() == f'{root}_ceil'.lower() for node in nodes), f'{root} has a node {root}_ceil already')
    from .rooms import _into
    verts, uvs, faces = lid(high, well, repeat)
    made = _into(text, geometry.mesh_text(f'{root}_ceil', root, tuple(line.format(texture) for line in PLAIN), verts, uvs, faces))
    return made, (high if well is None else [high, well[1]])


def cap(repo, tileset, folder, looks, *, shared=(), skip=()):
    """Write the ceiled models of a tileset's open tiles into `folder` (a review's overlay; a copy already there is the one
    changed) and tell {model: height or why not}. looks: {'default': texture, terrain: texture} by the tile's corners
    that are not the hub (`Wall`); skip: models left open on purpose (a stairwell shaft, a black filler)."""
    from pathlib import Path
    from . import inventory
    from .apply import noted
    from .lamps import PACKS
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    corners = {tile['model']: tile['corners'] for tile in inventory.read_set((Path(repo) / f'srn_t_{tileset}' / f'{tileset}.set').read_text(encoding='cp1252'))['tiles']}
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, PACKS):
        if name in skip:
            told[name] = 'left open'; continue
        if set(others) - {one.lower() for one in shared}:
            told[name] = 'shared with ' + ', '.join(others); continue
        terrains = sorted({corner for corner in corners.get(name, ()) if corner.lower() != 'wall'})
        texture = next((looks[terrain] for terrain in terrains if terrain in looks), looks['default'])
        new, said = capped(text, name, texture)
        if new is not None:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252'))
        told[name] = said
    return told
