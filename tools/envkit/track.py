"""Railway track built here, not generated: a straight piece of standard-gauge track on ballast, written as a model
folder (model.glb and its four maps) that a game set reads as it reads a Meshy download.

A generator draws track a little crooked and to no gauge, and pieces laid end to end must meet: the rail freight depot's
tracks run straight through its tiles on their row centres and on into the tiles beside it (user, 2026-11-13: "is it
possible to incorporate the train tracks?"). So the piece is exact: its rails GAUGE metres apart between their heads,
a sleeper every PITCH metres from half a pitch in, and every map seamless along the track, so that pieces laid end to
end are one track; and a merge brings a second track into the first, as a passing loop's ends do. It is low, its rail
tops HEIGHT metres up, under the knee, and a group lays it underfoot (the game set's `underfoot`): the walkmesh runs
flat across it, and it may run off the group's edges. A crane runway is built the same way (`crane_mesh`): the pair of
rails a gantry crane's leg runs on, one runway under each leg (user, 2026-11-13: "i think we need to add the crane
tracks, we'll need those as a prop anyway and the scene looks weird without it").

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
# A merge brings a track on the next row into the through track: OFFSET metres across in LENGTH metres, three tiles,
# on curves of RADIUS metres with a straight between (user, 2026-11-13: "can you make the tracks merge" at both ends of
# the depot). A main line's turnouts are far gentler; at the game's scale this reads as a yard's crossover. Each end
# of it runs straight for LEAD metres, so that it meets straight track, and the two tracks share long sleepers until
# their centre lines are SHARED metres apart.
MERGE_OFFSET, MERGE_LENGTH, MERGE_RADIUS, LEAD, SHARED = 10.0, 30.0, 15.0, 1.5, 3.2
# A crane runway: two heavy crane rails CRANE_GAUGE apart between their middles, each on a steel sole plate and clipped
# every CRANE_CLIP metres to one concrete ground beam whose top stands a little proud of the pavement. The depot's
# gantry crane came back with two short rails under each leg, about a metre apart and 0.23 metres high, its wheels on
# them: the runway carries on from those, which are taken off the crane (its `clear`).
CRANE_GAUGE, CRANE_BEAM, CRANE_BEAM_TOP = 1.0, 1.4, 0.06  # between the rails' middles; the beam's width, and how far its top stands up
CRANE_HEAD, CRANE_HEAD_DEPTH, CRANE_WEB, CRANE_FOOT, CRANE_FOOT_DEPTH, CRANE_RAIL = 0.1, 0.045, 0.035, 0.2, 0.025, 0.155
CRANE_PLATE, CRANE_PLATE_DEPTH, CRANE_CLIP = 0.3, 0.015, 0.5
CRANE_HEIGHT = CRANE_BEAM_TOP + CRANE_PLATE_DEPTH + CRANE_RAIL
SIZE = 2048
# Bands of the maps, in rows from the top: the ballast's cross-section, two sleeper tops, the sleepers' sides and ends,
# the rail's polished top, its rusted sides and its foot, and plain concrete (a crane runway's beam).
BANDS = {'ballast': (0, 1280), 'sleeperA': (1280, 1408), 'sleeperB': (1408, 1536), 'sleeperSide': (1536, 1600), 'sleeperEnd': (1600, 1632),
         'railTop': (1664, 1712), 'railSide': (1712, 1904), 'railFoot': (1904, 1952), 'concrete': (1952, 2048)}
INSET = 2  # pixels kept off a band's edge, so that a filtered sample stays inside it
STONE = 16  # pixels to a ballast stone's cell: about four centimetres


def rails():
    """The y of each rail's middle, across its track."""
    middle = GAUGE / 2 + HEAD / 2
    return (-middle, middle)


def sleepers():
    """The x of each sleeper's middle on a straight piece centred on x = 0."""
    return [-LENGTH / 2 + PITCH * (index + 0.5) for index in range(round(LENGTH / PITCH))]


def _bed():
    """[(y, z, distance over the bed's surface from its right-hand foot)] of the ballast's cross-section, and that distance across."""
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

    def arrays(self):
        return np.array(self.vertices), np.array(self.normals), np.array(self.uvs), np.array(self.faces)


def path(start, heading, pieces, *, step=0.5):
    """[(s, x, y, heading)] along a track's centre line from `start` (x, y) heading `heading` (radians from +x towards
    +y), through `pieces`: ('line', length) or ('arc', radius, turn), the turn in radians, to the left where it is more
    than 0. Each multiple of SEGMENT metres along it is a sample, where its maps start again, and an arc is sampled
    every `step` metres."""
    samples = [(0.0, float(start[0]), float(start[1]), float(heading))]
    for piece in pieces:
        s, x, y, h = samples[-1]
        if piece[0] == 'line':
            length = float(piece[1]); at = lambda d: (x + d * np.cos(h), y + d * np.sin(h), h)
            marks = set()
        else:
            radius, turn = float(piece[1]), float(piece[2]); length = radius * abs(turn); side = np.sign(turn)
            middle = (x - side * radius * np.sin(h), y + side * radius * np.cos(h))
            at = lambda d: (middle[0] + side * radius * np.sin(h + side * d / radius), middle[1] - side * radius * np.cos(h + side * d / radius), h + side * d / radius)
            marks = set(np.arange(step, length - 1e-6, step).tolist())
        require(length > 0, 'A piece of track has a length')
        marks |= {SEGMENT * count - s for count in range(int(s // SEGMENT) + 1, int((s + length) // SEGMENT) + 1)} | {length}
        for d in sorted(mark for mark in marks if 1e-6 < mark <= length + 1e-9):
            samples.append((s + d, *at(d)))
    return samples


def _place(sample, lateral, z):
    """A point `lateral` metres to the left of a sample of the centre line, `z` metres up."""
    _, x, y, h = sample
    return (x - lateral * np.sin(h), y + lateral * np.cos(h), z)


def _sweep(made, line, band, low, high, facing, across=(0.0, 1.0), start=0):
    """A face swept along `line` from its sample `start`: between the (lateral, z) points `low` and `high`, facing
    (lateral, up) as the track turns, its band's texture running along it, a whole picture to SEGMENT metres, and
    across it from `across[0]` to `across[1]`."""
    for one, two in zip(line[start:], line[start + 1:]):
        count = np.floor(one[0] / SEGMENT + 1e-9); u0, u1 = one[0] / SEGMENT - count, two[0] / SEGMENT - count
        middle = (one[3] + two[3]) / 2; normal = (-facing[0] * np.sin(middle), facing[0] * np.cos(middle), facing[1])
        made.quad([_place(one, *low), _place(two, *low), _place(two, *high), _place(one, *high)],
                  [(u0, _v(band, across[0])), (u1, _v(band, across[0])), (u1, _v(band, across[1])), (u0, _v(band, across[1]))], normal)


def _end(made, sample, outward, bed):
    """The track's end at `sample`, closed: the bed's cross-section and each rail's, facing along it (`outward` +1) or back."""
    _, _, _, h = sample; facing = (outward * np.cos(h), outward * np.sin(h), 0.0); top = BED_TOP
    made.quad([_place(sample, -BED_BASE, 0.0), _place(sample, BED_BASE, 0.0), _place(sample, top, bed), _place(sample, -top, bed)],
              [(0.0, _v('ballast', 0.0)), (0.0, _v('ballast', 1.0)), (0.03, _v('ballast', 0.9)), (0.03, _v('ballast', 0.1))], facing)
    foot, web, head = SLEEPER_TOP + FOOT_DEPTH, SLEEPER_TOP + RAIL - HEAD_DEPTH, SLEEPER_TOP + RAIL
    for middle in rails():
        for low, high, width, a, b in ((SLEEPER_TOP, foot, FOOT, 0.0, 0.12), (foot, web, WEB, 0.12, 0.62), (web, head, HEAD, 0.62, 1.0)):
            made.quad([_place(sample, middle - width / 2, low), _place(sample, middle + width / 2, low), _place(sample, middle + width / 2, high), _place(sample, middle - width / 2, high)],
                      [(0.0, _v('railSide', a)), (0.02, _v('railSide', a)), (0.02, _v('railSide', b)), (0.0, _v('railSide', b))], facing)


def _sleeper(made, sample, index, reach=(-SLEEPER_LENGTH / 2, SLEEPER_LENGTH / 2), foot=SLEEPER_FOOT):
    """A sleeper square across the track at `sample`, from `reach[0]` to `reach[1]` metres left of its centre line. Its
    top is the sleeper picture over the track's own 2.6 metres and plain concrete past them, where it carries a
    turnout's other track."""
    _, x, y, h = sample; along, left = np.array([np.cos(h), np.sin(h), 0.0]), np.array([-np.sin(h), np.cos(h), 0.0])
    half = SLEEPER_WIDTH / 2; point = lambda forward, lateral, z: np.array([x, y, z]) + forward * along + lateral * left
    top = 'sleeperB' if index % 3 == 1 else 'sleeperA'; low, high = reach; own = (max(low, -SLEEPER_LENGTH / 2), min(high, SLEEPER_LENGTH / 2))
    for start, stop in ((low, own[0]), own, (own[1], high)):
        if stop - start > 1e-6:
            plain = (start, stop) != own; u = (lambda lateral: 0.15 * (lateral - start) / (stop - start)) if plain else (lambda lateral: (lateral + SLEEPER_LENGTH / 2) / SLEEPER_LENGTH)
            made.quad([point(-half, start, SLEEPER_TOP), point(half, start, SLEEPER_TOP), point(half, stop, SLEEPER_TOP), point(-half, stop, SLEEPER_TOP)],
                      [(u(start), _v(top, 0.0)), (u(start), _v(top, 1.0)), (u(stop), _v(top, 1.0)), (u(stop), _v(top, 0.0))], (0, 0, 1))
    down = lambda z: (SLEEPER_TOP - z) / (SLEEPER_TOP - foot); span = lambda lateral: (lateral - low) / (high - low)
    for side in (-1, 1):
        made.quad([point(side * half, low, foot), point(side * half, high, foot), point(side * half, high, SLEEPER_TOP), point(side * half, low, SLEEPER_TOP)],
                  [(span(low), _v('sleeperSide', down(foot))), (span(high), _v('sleeperSide', down(foot))), (span(high), _v('sleeperSide', 0.0)), (span(low), _v('sleeperSide', 0.0))], side * along)
        lateral = low if side < 0 else high
        made.quad([point(-half, lateral, foot), point(half, lateral, foot), point(half, lateral, SLEEPER_TOP), point(-half, lateral, SLEEPER_TOP)],
                  [(0.0, _v('sleeperEnd', 1.0)), (1.0, _v('sleeperEnd', 1.0)), (1.0, _v('sleeperEnd', 0.0)), (0.0, _v('sleeperEnd', 0.0))], side * left)


def _rails(made, line, start=0):
    """Both rails along `line` from its sample `start`, but for the underside of the head, which no camera above the ground sees."""
    foot, web, head = SLEEPER_TOP + FOOT_DEPTH, SLEEPER_TOP + RAIL - HEAD_DEPTH, SLEEPER_TOP + RAIL
    for middle in rails():
        _sweep(made, line, 'railTop', (middle - HEAD / 2, head), (middle + HEAD / 2, head), (0, 1), start=start)
        for side in (-1, 1):  # from the head down; the side band runs from the foot (0) to the head (1)
            _sweep(made, line, 'railSide', (middle + side * HEAD / 2, web), (middle + side * HEAD / 2, head), (side, 0), (0.62, 1.0), start)
            _sweep(made, line, 'railSide', (middle + side * WEB / 2, foot), (middle + side * WEB / 2, web), (side, 0), (0.12, 0.62), start)
            _sweep(made, line, 'railSide', (middle + side * FOOT / 2, SLEEPER_TOP), (middle + side * FOOT / 2, foot), (side, 0), (0.0, 0.12), start)
            _sweep(made, line, 'railFoot', (middle + side * WEB / 2, foot), (middle + side * FOOT / 2, foot), (0, 1), start=start)


def _ballast(made, line, bed=BED):
    """The ballast bed along `line`, its top `bed` metres up."""
    profile, across = _bed(); scale = bed / BED  # a lower bed is as wide, and less steep
    for (y0, z0, d0), (y1, z1, d1) in zip(profile, profile[1:]):
        _sweep(made, line, 'ballast', (y0, z0 * scale), (y1, z1 * scale), ((z0 - z1) * scale, y1 - y0), (d0 / across, d1 / across))


def _at(line, distance):
    """The sample of `line` interpolated `distance` metres along it."""
    s = np.array([one[0] for one in line]); index = int(np.clip(np.searchsorted(s, distance) - 1, 0, len(line) - 2))
    one, two = line[index], line[index + 1]; part = (distance - one[0]) / (two[0] - one[0])
    return (distance, *(np.array(one[1:]) + part * (np.array(two[1:]) - np.array(one[1:]))))


def _pitches(line):
    """Where the sleepers of `line` lie: PITCH metres apart from half a pitch in."""
    return [_at(line, PITCH * (index + 0.5)) for index in range(int(line[-1][0] / PITCH + 1e-9))]


def mesh():
    """(vertices, normals, uvs, faces) of a straight piece LENGTH metres long, centred on x = y = 0 and standing on
    z = 0. Each face is flat, its corners its own. The faces that look down, the rail head's underside and every floor,
    are left out: no camera above the ground sees them."""
    made = _Mesh(); line = path((-LENGTH / 2, 0.0), 0.0, [('line', LENGTH)])
    _ballast(made, line); _rails(made, line); _end(made, line[0], -1, BED); _end(made, line[-1], 1, BED)
    for index, sample in enumerate(_pitches(line)):
        _sleeper(made, sample, index)
    return made.arrays()


def _block(made, x0, x1, y0, y1, z0, z1, band, against=0):
    """A box from x0 to x1 along the track and y0 to y1 across it, from z0 up to z1, but for its floor and the side
    that stands `against` something (-1 the y0 side, 1 the y1 side): each face in `band`. A clip's side against the
    rail is inside the rail's foot, and seen, if at all, from behind."""
    v0, v1 = _v(band, 0.0), _v(band, 1.0)
    made.quad([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], [(0.0, v0), (0.04, v0), (0.04, v1), (0.0, v1)], (0, 0, 1))
    for y, side in [(y, side) for y, side in ((y0, -1), (y1, 1)) if side != against]:
        made.quad([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [(0.0, v0), (0.04, v0), (0.04, v1), (0.0, v1)], (0, side, 0))
    for x, side in ((x0, -1), (x1, 1)):
        made.quad([(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)], [(0.0, v0), (0.04, v0), (0.04, v1), (0.0, v1)], (side, 0, 0))


def crane_rails():
    """The y of each crane rail's middle, across its runway."""
    return (-CRANE_GAUGE / 2, CRANE_GAUGE / 2)


def crane_clips():
    """The x of each pair of clips on a crane runway piece centred on x = 0, CRANE_CLIP apart from half a pitch in."""
    return [-LENGTH / 2 + CRANE_CLIP * (index + 0.5) for index in range(round(LENGTH / CRANE_CLIP))]


def crane_mesh():
    """(vertices, normals, uvs, faces) of a crane runway piece LENGTH metres long, centred on x = y = 0 and standing on
    z = 0, as `mesh` is: a concrete beam CRANE_BEAM wide whose top stands CRANE_BEAM_TOP up and on it two crane rails
    (`crane_rails`), each on a sole plate with a clip either side of its foot every CRANE_CLIP metres. The rails' tops
    are CRANE_HEIGHT up, under the knee, so a group lays it underfoot as it lays track."""
    made = _Mesh(); line = path((-LENGTH / 2, 0.0), 0.0, [('line', LENGTH)]); half, top = CRANE_BEAM / 2, CRANE_BEAM_TOP
    plate = top + CRANE_PLATE_DEPTH; foot, web, head = plate + CRANE_FOOT_DEPTH, plate + CRANE_RAIL - CRANE_HEAD_DEPTH, plate + CRANE_RAIL
    _sweep(made, line, 'concrete', (-half, top), (half, top), (0, 1))
    for side in (-1, 1):  # the beam's side darkens towards the ground (the band's foot, 1)
        _sweep(made, line, 'sleeperSide', (side * half, 0.0), (side * half, top), (side, 0), (1.0, 0.0))
    for middle in crane_rails():
        _sweep(made, line, 'railFoot', (middle - CRANE_PLATE / 2, plate), (middle + CRANE_PLATE / 2, plate), (0, 1))
        _sweep(made, line, 'railTop', (middle - CRANE_HEAD / 2, head), (middle + CRANE_HEAD / 2, head), (0, 1))
        for side in (-1, 1):  # the rail's side band runs from its foot (0) up
            _sweep(made, line, 'railFoot', (middle + side * CRANE_PLATE / 2, top), (middle + side * CRANE_PLATE / 2, plate), (side, 0), (0.0, 0.3))
            _sweep(made, line, 'railSide', (middle + side * CRANE_HEAD / 2, web), (middle + side * CRANE_HEAD / 2, head), (side, 0), (0.62, 1.0))
            _sweep(made, line, 'railSide', (middle + side * CRANE_WEB / 2, foot), (middle + side * CRANE_WEB / 2, web), (side, 0), (0.12, 0.62))
            _sweep(made, line, 'railSide', (middle + side * CRANE_FOOT / 2, plate), (middle + side * CRANE_FOOT / 2, foot), (side, 0), (0.0, 0.12))
            _sweep(made, line, 'railFoot', (middle + side * CRANE_WEB / 2, foot), (middle + side * CRANE_FOOT / 2, foot), (0, 1))
            for x in crane_clips():
                inner, outer = sorted((middle + side * (CRANE_FOOT / 2 - 0.015), middle + side * CRANE_PLATE / 2))
                _block(made, x - 0.04, x + 0.04, inner, outer, plate, foot + 0.012, 'railFoot', -side)
    for sample, outward in ((line[0], -1), (line[-1], 1)):  # each end closed: the beam's cross-section, and each plate's and rail's
        x = sample[1]; facing = (outward, 0.0, 0.0)
        sections = [(0.0, 0.0, top, CRANE_BEAM, 'sleeperEnd', 1.0, 0.0)] + [
            (middle, low, high, width, band, a, b) for middle in crane_rails()
            for low, high, width, band, a, b in ((top, plate, CRANE_PLATE, 'railFoot', 0.0, 0.3), (plate, foot, CRANE_FOOT, 'railSide', 0.0, 0.12),
                                                 (foot, web, CRANE_WEB, 'railSide', 0.12, 0.62), (web, head, CRANE_HEAD, 'railSide', 0.62, 1.0))]
        for middle, low, high, width, band, a, b in sections:
            made.quad([(x, middle - width / 2, low), (x, middle + width / 2, low), (x, middle + width / 2, high), (x, middle - width / 2, high)],
                      [(0.0, _v(band, a)), (0.03, _v(band, a)), (0.03, _v(band, b)), (0.0, _v(band, b))], facing)
    return made.arrays()


def merging(offset=MERGE_OFFSET, length=MERGE_LENGTH, radius=MERGE_RADIUS):
    """The pieces of a merge's other track, from its switch LEAD metres in from the west end: a curve off to the left,
    a straight across, and a curve back, so that it runs `offset` metres to the left of the through track for the last
    LEAD metres of the piece's `length`; and the angle it crosses at (radians). The angle is the least that fits the
    curves of `radius` metres into the length."""
    room = length - 2 * LEAD; rise = lambda angle: 2 * radius * (1 - np.cos(angle))
    reach = lambda angle: 2 * radius * np.sin(angle) + (offset - rise(angle)) / np.tan(angle)
    steepest = np.arccos(1 - offset / (2 * radius)) if offset < 4 * radius else np.pi / 2
    require(0 < offset and reach(steepest) <= room, f'A merge of {offset} metres needs more than {length} metres at a {radius} metre radius')
    low, high = 1e-4, steepest
    for _ in range(100):  # the reach shortens as the angle grows
        middle = (low + high) / 2; low, high = (middle, high) if reach(middle) > room else (low, middle)
    angle = high; across = (offset - rise(angle)) / np.sin(angle)
    return [('arc', radius, angle), *([('line', across)] if across > 1e-6 else []), ('arc', radius, -angle), ('line', LEAD)], float(angle)


def merge_mesh(offset=MERGE_OFFSET, length=MERGE_LENGTH, radius=MERGE_RADIUS):
    """(vertices, normals, uvs, faces) of a merge: a through track `length` metres long on y = 0, centred on x = 0, and
    from its switch another that curves off to the left and runs on beside it `offset` metres away. The other track's
    bed lies a little under the through track's, so the two never share a surface; its rails start where they have
    drawn clear of the through track's (the switch blades); its inner rail crosses the through track's left rail at
    the frog. Where the two tracks are too close for sleepers of their own, the through track's are drawn out under
    both."""
    made = _Mesh(); through = path((-length / 2, 0.0), 0.0, [('line', length)])
    pieces, _ = merging(offset, length, radius); other = path((-length / 2 + LEAD, 0.0), 0.0, pieces)
    _ballast(made, through); _rails(made, through); _end(made, through[0], -1, BED); _end(made, through[-1], 1, BED)
    lower = BED - 0.015; _ballast(made, other, lower); _end(made, other[-1], 1, lower)
    clear = next((index for index, sample in enumerate(other) if sample[2] >= HEAD), None)
    require(clear is not None, f"A merge of {offset} metres never draws its rails clear of the through track's: it needs more than {HEAD} metres")
    _rails(made, other, clear)
    beside = lambda x: float(np.interp(x, [sample[1] for sample in other], [sample[2] for sample in other], left=-np.inf, right=-np.inf))
    shared = []  # (x, reach) of the through track's drawn-out sleepers
    for index, sample in enumerate(_pitches(through)):
        apart = beside(sample[1]); reach = apart + SLEEPER_LENGTH / 2 if 0 <= apart < SHARED else SLEEPER_LENGTH / 2
        _sleeper(made, sample, index, (-SLEEPER_LENGTH / 2, reach)); shared += [(sample[1], reach)] if reach > SLEEPER_LENGTH / 2 else []
    for index, sample in enumerate(_pitches(other)):
        _, x, y, h = sample
        corners = [(x + forward * np.cos(h) - lateral * np.sin(h), y + forward * np.sin(h) + lateral * np.cos(h))
                   for forward in (-SLEEPER_WIDTH / 2, SLEEPER_WIDTH / 2) for lateral in (-SLEEPER_LENGTH / 2, SLEEPER_LENGTH / 2)]
        under = any(abs(cx - at) < SLEEPER_WIDTH / 2 + 0.05 and cy < reach + 0.05 for cx, cy in corners for at, reach in shared)
        if y >= SHARED and not under:  # one sleeper never stands in another
            _sleeper(made, sample, index, foot=lower - 0.01)
    return made.arrays()


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


def build(output, seed=0, kind='straight'):
    """Write a piece of `kind`, 'straight' (`mesh`), 'merge' (`merge_mesh`) or 'crane' (`crane_mesh`), into the fresh folder `output`:
    model.glb, its maps as `texture_0_<map>.png` (`local.MAPS`) and track.json, which records its measures, its seed
    and each file's hash. Returns that record."""
    from PIL import Image
    require(isinstance(seed, int) and seed >= 0, 'A seed is a whole number from 0')
    require(kind in ('straight', 'merge', 'crane'), 'A piece of track is straight, a merge or a crane runway: ' + str(kind))
    with fresh(output) as folder:
        write_glb(folder / 'model.glb', *{'straight': mesh, 'merge': merge_mesh, 'crane': crane_mesh}[kind]())
        for name, picture in maps(seed).items():
            require(name in local.MAPS, 'An unknown map: ' + name)
            Image.fromarray((picture * 255).round().astype(np.uint8)).save(folder / f'texture_0_{name}.png')
        laid = {'height': HEIGHT, 'gauge': GAUGE, 'pitch': PITCH, 'width': 2 * BED_BASE}
        shape = {'straight': {'length': LENGTH, **laid},
                 'merge': {'length': MERGE_LENGTH, 'offset': MERGE_OFFSET, 'radius': MERGE_RADIUS, 'angle': round(float(np.degrees(merging()[1])), 3), **laid},
                 'crane': {'length': LENGTH, 'height': CRANE_HEIGHT, 'gauge': CRANE_GAUGE, 'width': CRANE_BEAM, 'clip': CRANE_CLIP}}[kind]
        record = {'schemaVersion': 1, 'kind': 'envkit-track', 'piece': kind, 'seed': seed, **shape,
                  'files': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.iterdir())}}
        (folder / 'track.json').write_text(json.dumps(record, indent=1) + '\n', encoding='utf-8')
    return record
