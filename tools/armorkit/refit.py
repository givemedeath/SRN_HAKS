"""Baked parts carried from one body to another, each by a rotation and a scale along each of its axes, their
ends then brought to the other body's seam contract.

A part keeps its shape: each is turned, scaled and moved by one linear map (`placement`), which bends nothing,
so that the parts of a design made on the Human male go on the Human female without being generated again,
plates flat and pockets square. Rotation and a uniform scale were the user's guidance for the first refit
only; a part is scaled along each of its axes as the other body is (user, 2026-11-13).

* A part between two or more joints is placed by the planes of those joints (`seams.plane`), the points the
  seam contract measures ends from: an upper arm, a thigh or a shin by its two, the pelvis by the waist and
  both hips. Its axis runs from its first joint to the middle of the others (`axis_of`) and is turned the
  shortest way onto the other body's; along it the part is scaled as the joints lie apart (`along`), and
  across it in each of two directions as the body's own outline at those joints is wide that way (`across`,
  the contract's body rings). The Human female's limbs are 0.95 to 1.0 the male's length and her body 0.70
  to 0.79 as wide at the joints: a thigh scaled to her leg's length kept the male's girth and stood out
  through the sides of a pelvis scaled to her hips (Facility Security, 2026-11-13).
* The chest is carried by a slope, not one map (`taper`, `tapered`), slice by slice level with the waist
  plane and about a middle line through the neck, the middle of the shoulders and the waist, each of them
  set on the other body's: scaled across at its shoulder line as the two bodies' shoulders lie apart and
  their own chests are deep there, at the waist as the contract's body ring there, and between the two
  evenly; above the shoulder line as there, below the waist as there. Only the body under the part is
  scaled so: from the armpits down, what of the part stands outside the source body's own chest, read level
  by level round the middle line (`radii`), is set as far outside it on the other body as it stood on the
  source (`STANDOFF_*`). The Dwarf Large female's waist is 1.72 the Human female's and her shoulders 1.12: one scale, the
  mean of its joints' at 1.2, left the hem 0.5 short of the waist, the end shaping then spread it out over
  its last 12 cm, and the vest's row of pouches stood out round the belly as a shelf (user, 2026-11-14: no
  shelf; the vest is tapered over its whole length). Tapered, with all of it scaled about the middle line,
  the vest's 4 cm clear of the Human's waist and its pouches' 3 to 4 cm more came to 1.7 times as much on
  her and 3.0 times on the Troll Large female, and the pouch row still stood out round the belly as a band
  over the trousers (user, 2026-11-14: the pouches keep their depth).
* A part with one joint, a hand, a foot or the neck, turns as the part across that joint does, so a boot stays
  flat where the shin turns two degrees, and is scaled along each axis of the other body's own part there as
  that part spreads along it against the source's (`principal`, `spreads`): a Human female foot is about 0.85
  the size of the male's and her hand 0.86, but not by the same share every way.
* The ends at the tube joints are then drawn in or spread out to the other body's envelopes as a bake shapes
  them (`ends.shaped`), a smooth slope with no shelf over the last `ends.LONGEST` at most, and the seam gate
  on the other body decides each part. The cap a bake grew past an under end's plane is scaled about the
  joint's axis as that end's ring was (`capped`): where the end was drawn in, shaping left the cap as wide as
  the scales made it, and a glove's cap stood at the Human female's forearm skin as a band above the cuff
  (2026-11-13). Where the part across the joint is the body's own skin (`bare`), the cap is then held
  `UNDER_SKIN` inside the other body's part there (`under_skin`): her forearm is flatter above the wrist than
  the ring at the plane says, and drawn in with its rim the cap still showed through it in patches. A thigh's
  end at the hip, a dome grown on the body's seat, is no tube
  and is left as the scales leave it: shaped as one, its dome flared into a lip that stood out through the
  pelvis (2026-11-13).
* Each under end's cap is then stretched along its joint's axis until it runs the other body's own overlap
  past the plane (`deepened`), and each over end's dome is pressed back to the contract's `domeMost` past its
  rim (`flattened`): both were grown for the source body and carried by the part's scale along, while the
  overlap a body asks grows with its girth and the dome's height is one number for every body. Carried to
  the 18 other bodies, 57 caps were short of the overlap and 39 domes stood too far (2026-11-14).

A part holding the body's own skin (`bodyskin.worn`), a short sleeve's upper arm, is carried without it
(`bodyskin.unworn`): that skin is the other body's, and `run` lays the other body's own beside the outfit's
again (`bake.skinned`). The Human female's generated shirt had no cloth on the inside of the upper arm for
12 cm below the armpit, and her own arm showed through there standing and with her arms raised; the male's
sleeves, whole, are carried to her instead (Facility Security, 2026-11-13).
"""
from pathlib import Path

import numpy as np

from tools.robes import mesh_ops

from . import bodyskin, ends, measure, registry, repose, seams, split
from .registry import require

FACE_KEYS = ('f', 'added', 'domed', 'trimmed', 'pad')  # what a kept part holds per face (`bake.KEYS`, `bake.OPTIONAL`)
UNDER_SKIN = 0.002  # a cap under the body's own skin (a glove's under a bare forearm) stands at least this far inside it
OVER_SKIN = 0.003  # a sleeve beside the body's own skin in its slot stands at least this far outside the other body's arm
OVER_ROUNDS = 6  # rings of neighbours a sleeve's push out over the arm is spread to
OVER_PASSES = 4  # times a sleeve is pushed out and read against the arm again
OVER_MOST = 0.03  # metres: a sleeve is pushed out over the arm no farther; a farther push fails the refit
TAPERED = {'chest': ('shoulder', 'waist')}  # a part scaled across by a slope: the joints its width is read at, down its axis
TAPER_EASE = 0.2  # a slope sets in over this share of its run from its first station: no crease on the line where it starts
STANDOFF_WAYS = 48  # directions round a tapered part's middle line its body's own part is read in at each level
STANDOFF_LEVELS = 0.01  # metres from one level it is read at to the next
STANDOFF_EVEN = 2  # times those radii are evened with their neighbours: no crease where the body's own surface turns or folds
TORSO_FIRST = ('chest', 'pelvis')  # carried before the parts whose ends run into them: an end runs no deeper than the torso carried stands over it


def joints_of(token):
    """[(joint, side, other token)] for each joint part `token` meets, with the part across that joint."""
    found = []
    for joint, spec in seams.JOINTS.items():
        for side in seams.sides(joint):
            letter = 'l' if side == 'c' else side
            named = {key: split.token(spec[key], letter) for key in ('under', 'over')}
            for key, other in (('under', 'over'), ('over', 'under')):
                if named[key] == token:
                    found.append((joint, side, named[other]))
    return found


def anchors(token, bones):
    """The plane points of the joints part `token` meets, on the body with rig `bones`."""
    return np.array([np.asarray(seams.plane(bones, joint, 'l' if side == 'c' else side)[0], float) for joint, side, _ in joints_of(token)])


def axis_of(points):
    """A part's axis from its anchors: from the first to the middle of the others."""
    return np.asarray(points[1:], float).mean(axis=0) - np.asarray(points[0], float)


def across(token, contract, source, target, ways, bones=None, only=None):
    """How much wider the body `target` is than the body `source` at the joints part `token` meets in each of
    the directions `ways` (unit vectors square to the part's axis): the ratio of the contract's body rings
    there, each ring's radii weighed by how near their directions lie to that way, and its mean over the
    joints. `bones`, the source body's rig, places a ring's directions (`seams.frame` of its plane); without
    it a ring is weighed the same every way, the ratio of its mean radii. `only` names the one joint read."""
    found = []
    for joint, side, _ in joints_of(token):
        if only is not None and joint != only:
            continue
        ring = lambda body: np.asarray(contract['joints'][joint]['bodies'][body]['sides'][side]['bodyRing'], float)
        new, old = ring(target), ring(source)
        if bones is None:
            weight = np.ones((len(old), len(ways)))
        else:
            u, w = seams.frame(seams.plane(bones, joint, 'l' if side == 'c' else side)[1])
            angle = 2 * np.pi * np.arange(len(old)) / len(old)
            weight = ((np.cos(angle)[:, None] * u + np.sin(angle)[:, None] * w) @ np.asarray(ways, float).T) ** 2
        found.append(list((weight * new[:, None]).sum(axis=0) / (weight * old[:, None]).sum(axis=0)))
    return [float(value) for value in np.mean(found, axis=0)]


def _moments(vertices, faces):
    """(corners less the middle, area) of a surface's faces, the middle its area's."""
    corners = np.asarray(vertices, float)[np.asarray(faces, int)]
    area = 0.5 * np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    return corners - (corners.mean(axis=1) * area[:, None]).sum(axis=0) / area.sum(), area


def spreads(vertices, faces, axes):
    """How far a surface spreads along each of the unit `axes` (rows): the root mean square distance of its
    area from its middle along each."""
    reach, area = _moments(vertices, faces)
    along = reach @ np.asarray(axes, float).T  # faces, corners, axes
    return np.sqrt(((along ** 2).mean(axis=1) * area[:, None]).sum(axis=0) / area.sum())


def principal(vertices, faces):
    """The axes a surface spreads along, most to least, as rows: those of its area's second moments."""
    reach, area = _moments(vertices, faces)
    return np.linalg.svd(reach.reshape(-1, 3) * np.repeat(np.sqrt(area / 3), 3)[:, None], full_matrices=False)[2]


def stretched(rotation, axes, scales):
    """The linear map that turns by `rotation` after scaling by each of `scales` along the unit `axes` (rows,
    square to one another)."""
    axes = np.asarray(axes, float)
    return rotation @ axes.T @ np.diag(np.asarray(scales, float)) @ axes


def width(mesh, point, normal, way):
    """How wide the surface `mesh` (vertices, faces) is along the unit `way` where the plane (`point`, `normal`)
    cuts it: from the first of its section to the last. 0 where the plane misses it."""
    segments = seams.section(mesh[0], mesh[1], point, normal)
    if not len(segments):
        return 0.0
    u, w = seams.frame(normal)
    reach = segments.reshape(-1, 2) @ np.array([u @ way, w @ way])
    return float(reach.max() - reach.min())


def radii(mesh, frame):
    """(heights, radii): how far the surface `mesh` (vertices, faces) stands from the middle line of `frame`
    (one of `taper`'s) at the levels `heights`, `STANDOFF_LEVELS` apart over its whole height, in
    `STANDOFF_WAYS` directions round the line, the first the frame's way across and on toward its way deep:
    where the ray from the line last leaves it (`measure.beyond`), evened `STANDOFF_EVEN` times with its
    neighbours round the line and up and down it. A ray that crosses none of it, over the top of the surface
    or through an opening, is read as the nearest level's in its direction that does."""
    reach = (np.asarray(mesh[0], float) - frame['origin']) @ frame['axes'].T
    heights = np.arange(reach[:, 0].min(), reach[:, 0].max() + STANDOFF_LEVELS, STANDOFF_LEVELS)
    angle = 2 * np.pi * np.arange(STANDOFF_WAYS) / STANDOFF_WAYS
    far = 2 * float(np.abs(reach[:, 1:]).max()) + 1
    rays = far * (np.cos(angle)[:, None] * frame['axes'][1] + np.sin(angle)[:, None] * frame['axes'][2])
    table = np.empty((len(heights), STANDOFF_WAYS))
    for row, height in enumerate(heights):  # each level about its own point of the line: the surface as it stands, not sheared straight
        middle = frame['origin'] + np.array([height, *(np.polyval(np.polyfit(frame['line'][:, 0], frame['line'][:, k], 2), height) for k in (1, 2))]) @ frame['axes']
        table[row] = far - measure.beyond(middle + rays, middle, frame['axes'][0], mesh[0], mesh[1])[0]
    for way in range(STANDOFF_WAYS):
        found = ~np.isnan(table[:, way])
        require(found.any(), "A body's own part does not close round the middle line of a tapered part")
        table[:, way] = np.interp(heights, heights[found], table[found, way])
    for _ in range(STANDOFF_EVEN):
        table = (np.roll(table, 1, axis=1) + 2 * table + np.roll(table, -1, axis=1)) / 4
        table = (np.vstack([table[:1], table[:-1]]) + 2 * table + np.vstack([table[1:], table[-1:]])) / 4
    return heights, table


def _around(heights, table, height, angle):
    """`radii` read at each `height` and `angle`: straight between its levels and directions, its first and
    last level's beyond them."""
    x = np.clip((np.asarray(height, float) - heights[0]) / STANDOFF_LEVELS, 0.0, len(heights) - 1.0) if len(heights) > 1 else np.zeros(len(height))
    low = np.minimum(np.floor(x).astype(int), max(len(heights) - 2, 0))
    high, t = np.minimum(low + 1, len(heights) - 1), x - low
    y = (np.asarray(angle, float) % (2 * np.pi)) / (2 * np.pi / table.shape[1])
    left = np.floor(y).astype(int) % table.shape[1]
    right, s = (left + 1) % table.shape[1], y - np.floor(y)
    return (1 - t) * ((1 - s) * table[low, left] + s * table[low, right]) + t * ((1 - s) * table[high, left] + s * table[high, right])


def taper(token, source, target, contract=None, names=None):
    """The slope part `token` is carried by from body `source` to body `target` (`TAPERED`; None for any other
    part, or without a contract), as `tapered` takes it.

    The part is carried slice by slice, each slice level with the plane of its last station, the waist's: a
    slice stays level, is scaled in its own plane about the part's middle line, and is set on the other body's
    middle line as far down it as it lay on the source's. The middle line runs through three points on each
    body: the part's other joint (the neck), the middle of its first station's pair (the shoulders) and its
    last station (the waist), each of which is carried onto the other body's exactly, with one curve through
    the three and no corner at the middle one. Carried by one map about a straight axis from the neck, which
    leans 8 degrees from the upright, the Dwarf Large female's hem stood 1.8 cm above her waist plane in front
    and as far below it behind; and the Large Human male's shoulders lie 5 cm farther forward over the same
    waist, which no straight axis follows: scaled about one, his hem lay 5 cm off his waist.

    `frames` holds for the source and the target: `origin`, the neck; `axes`, the level plane's normal, the
    way along the line between the shoulders in that plane, and the way square to both; and `line`, per
    station, its height and its place along the two level ways, from the origin. `top` holds the scales
    across at the shoulders: as far as they lie apart on the two bodies, which puts the armholes where the
    sleeves are carried to, and as deep as the two bodies' own parts are on that line (`width`). `hem` holds
    those at the waist: the contract's body ring there (`across`). `radii` holds the source body's own part
    round its middle line (`radii`), what those scales carry; and `clear`, the height the part's standoff from
    it is carried whole from, the armpits: the shoulder line and the widest radius of the source's body ring
    at the shoulders below it. Above that the body's own part slopes away under the part over it, a shoulder
    or the root of the neck, and a level ray reads no standoff there."""
    if token not in TAPERED or contract is None:
        return None
    first, last = TAPERED[token]
    found = joints_of(token)
    met = [joint for joint, _, _ in found]
    require(len(met) == 4 and met.count(first) == 2 and met.count(last) == 1, f'{token} is tapered from a pair of joints to one, with one more above')
    require(token in source[1] and token in target[1], f'Both bodies have a {token} to read how deep a tapered part is by')
    pair, hem = [k for k, joint in enumerate(met) if joint == first], met.index(last)
    head = next(k for k in range(len(met)) if k not in pair and k != hem)
    frames, deep = [], []
    for bones, mesh in ((source[0], source[1][token][:2]), (target[0], target[1][token][:2])):
        points = anchors(token, bones)
        level = seams.unit(seams.plane(bones, last, 'l' if found[hem][1] == 'c' else found[hem][1])[1])
        span = points[pair[0]] - points[pair[1]]
        span = span - (span @ level) * level
        require(np.linalg.norm(span) > 1e-9, f'The {first} joints of {token} lie one above the other')
        axes = np.array([level, span / np.linalg.norm(span), np.cross(level, span / np.linalg.norm(span))])
        stations = np.array([points[head], points[pair].mean(axis=0), points[hem]])
        line = (stations - points[head]) @ axes.T
        require((np.diff(line[:, 0]) > 1e-6).all(), f'The joints of {token} do not lie one below the other, the {last} last')
        frames.append({'origin': points[head], 'axes': axes, 'line': line, 'span': float(np.linalg.norm(span))})
        deep.append(width(mesh, stations[1], level, axes[2]))
    require(min(deep) > 1e-6, f"A body's own {token} is not cut by the line of its {first} joints")
    armhole = max(max(contract['joints'][first]['bodies'][names[0]]['sides'][found[k][1]]['bodyRing']) for k in pair)
    return {'frames': frames, 'top': [frames[1]['span'] / frames[0]['span'], deep[1] / deep[0]],
            'hem': across(token, contract, *names, frames[0]['axes'][1:], source[0], only=last),
            'radii': radii(source[1][token][:2], frames[0]), 'clear': float(frames[0]['line'][1, 0] + armhole)}


def tapered(vertices, slope):
    """`vertices` of a tapered part, on the source body, carried to the target by its slope (`taper`): each to
    the height its own maps to, set as far from the target's middle line as it stood from the source's, times
    the scales across at its height: the slope's `top` down to the shoulders, its `hem` from the waist on, and
    between them evenly, the slope setting in over the first `TAPER_EASE` of the way.

    Those scales carry the body under the part, the slope's `radii`. What of a vertex stands outside them, its
    standoff, is not scaled: it is set as far outside the scaled body, the way its own direction from the
    middle line is carried, from the slope's `clear` height down, and from the shoulder line to there by a
    growing share of it (no step either end). A vertex inside the radii, a lid across the hem or cloth turned
    in, is scaled whole, as is everything above the shoulder line. A plate or a pouch on the vest so stays as
    deep as it was made and lies on the other body's belly, wider and taller or shorter as the body is."""
    a, b = slope['frames']
    reach = (np.asarray(vertices, float) - a['origin']) @ a['axes'].T  # height, and the two level ways
    height = reach[:, 0]
    through = lambda values: np.polyval(np.polyfit(a['line'][:, 0], values, 2), height)  # one curve through the three stations
    share = np.clip((height - a['line'][1, 0]) / (a['line'][2, 0] - a['line'][1, 0]), 0.0, 1.0)
    share = np.where(share < TAPER_EASE, share ** 2 / (2 * TAPER_EASE), share - TAPER_EASE / 2) / (1 - TAPER_EASE / 2)
    top, hem = np.asarray(slope['top'], float), np.asarray(slope['hem'], float)
    off = np.stack([reach[:, k] - through(a['line'][:, k]) for k in (1, 2)], axis=1)  # from the middle line, level
    scale = top + share[:, None] * (hem - top)
    carried = scale * off
    if slope.get('radii') is not None:
        far = np.linalg.norm(off, axis=1)
        stand = np.maximum(far - _around(*slope['radii'], height, np.arctan2(off[:, 1], off[:, 0])), 0.0)
        held = np.clip((height - a['line'][1, 0]) / max(slope['clear'] - a['line'][1, 0], 1e-9), 0.0, 1.0)
        grown = scale * off / np.maximum(far, 1e-12)[:, None]  # the vertex's unit way from the line, as the scales carry it
        carried = carried - (stand * held * held * (3 - 2 * held) * (1 - 1 / np.maximum(np.linalg.norm(grown, axis=1), 1e-12)))[:, None] * grown
    out = b['origin'] + through(b['line'][:, 0])[:, None] * b['axes'][0]
    for k in (1, 2):
        out = out + (through(b['line'][:, k]) + carried[:, k - 1])[:, None] * b['axes'][k]
    return out


def placement(token, source, target, contract=None, names=None):
    """(linear map, offset, report) carrying part `token` from body `source` to body `target`, each a (rig,
    parts by token) pair as `measure.body` gives them, as `map @ p + offset`. `contract` and `names`, the two
    bodies' names, give the scale across a part with two or more joints; without them it is the scale along
    (module notes). A tapered part is carried by its slope, not by one map (`taper`, `tapered`): the map
    returned for it is its top's, upright as the slope's slices are, with the neck where the other body's is,
    and the report holds the scales across at its shoulders (`across`) and at its waist (`hem`). A shoulder pad meets no joint: it rides its upper arm's bone, and is carried as that is."""
    if token in registry.SLOTS['shoulder']['tokens']:
        carrier = split.token('bicep', token[-1])
        linear, offset, report = placement(carrier, source, target, contract, names)
        return linear, offset, {**report, 'with': carrier}
    met = joints_of(token)
    require(met, f'{token} meets no joint')
    if len(met) > 1:
        start, goal = anchors(token, source[0]), anchors(token, target[0])
        run, aim = axis_of(start), axis_of(goal)
        require(np.linalg.norm(run) > 1e-9, f'The joints of {token} are one point')
        unit = run / np.linalg.norm(run)
        rotation, along = repose.turn(unit, aim / np.linalg.norm(aim)), float(np.linalg.norm(aim) / np.linalg.norm(run))
        slope = taper(token, source, target, contract, names)
        if slope is not None:
            a, b = slope['frames']
            along = float(b['line'][2, 0] / a['line'][2, 0])
            linear = b['axes'].T @ np.diag([along, *slope['top']]) @ a['axes']
            return linear, b['origin'] - linear @ a['origin'], {'along': round(along, 4), 'across': [round(value, 4) for value in slope['top']],
                                                              'hem': [round(value, 4) for value in slope['hem']]}
        ways = seams.frame(unit)
        round_ = [along, along] if contract is None else across(token, contract, *names, ways, source[0])
        linear = stretched(rotation, [unit, *ways], [along, *round_])
        return linear, goal.mean(axis=0) - linear @ start.mean(axis=0), {'along': round(along, 4), 'across': [round(value, 4) for value in round_]}
    (_, _, other), = met
    require(len(joints_of(other)) > 1, f'{token} and {other} each meet one joint: nothing turns them')
    start, goal = anchors(other, source[0]), anchors(other, target[0])
    rotation = repose.turn(*(seams.unit(axis_of(points)) for points in (start, goal)))
    require(token in source[1] and token in target[1], f'Both bodies have a {token} to scale a part by')
    axes = principal(*target[1][token][:2])  # the other body's own part's axes, the source's part turned onto them
    scales = spreads(*target[1][token][:2], axes) / spreads(np.asarray(source[1][token][0], float) @ rotation.T, source[1][token][1], axes)
    linear = axes.T @ np.diag(scales) @ axes @ rotation
    joint, aim = anchors(token, source[0])[0], anchors(token, target[0])[0]
    return linear, aim - linear @ joint, {'axes': [round(float(value), 4) for value in scales]}


def capped(before, after, faces, measured, part_ends):
    """`after`, a part's vertices with its ends shaped (`ends.shaped`), with what lies past each under end's
    plane, its cap, scaled about the joint's axis in each direction as the end's ring was (`ends.ring`, read
    on the faces `measured` flags) from `before`, where that draws it in farther than the shaping did: the cap
    stays as far inside its rim as the bake grew it. Where an end is spread out, the shaping grows its cap
    with it already."""
    before, out, mine = np.asarray(before, float), np.array(after, float), np.asarray(faces, int)[np.asarray(measured, bool)]
    for point, normal, _, _, under, _ in part_ends:
        old, new = (ends.ring(points, mine, point, normal, True) for points in (before, out)) if under else (None, None)
        if old is None or new is None:
            continue
        u, w = seams.frame(normal)
        relative = before - point
        height = relative @ normal
        radial = relative - height[:, None] * normal
        past = height < 0
        angle = np.arctan2(radial[past] @ w, radial[past] @ u) % (2 * np.pi)
        ratio = seams.around(new / np.maximum(old, 1e-9), angle - np.pi / len(old))  # read at the bins' centres, as `ends` reads a ring
        shaped = np.linalg.norm((out[past] - point) - ((out[past] - point) @ normal)[:, None] * normal, axis=1)
        ratio = np.minimum(ratio, shaped / np.maximum(np.linalg.norm(radial[past], axis=1), 1e-12))
        out[past] = point + height[past, None] * normal + radial[past] * ratio[:, None]
    return out


def deepened(vertices, point, normal, least, depth):
    """`vertices` with what lies past an under end's plane (`point`, unit `normal` toward the part), its cap,
    stretched along the normal until its deepest point lies `depth` past the plane, where it lies less than
    `least` past it: the cap keeps its rim and its width, and runs on as far as the other body's overlap asks.
    A cap as deep already, and a part with nothing past the plane, stay as they are."""
    out = np.array(vertices, float)
    height = (out - point) @ normal
    past = height < 0
    deepest = -float(height[past].min()) if past.any() else 0.0
    if deepest <= ends.MARGIN or deepest >= least:
        return out
    out[past] += (height[past] * (depth / deepest - 1))[:, None] * normal
    return out


def flattened(part, vertices, point, normal, here, most):
    """`vertices` of `part` with the dome that closes its over end at the plane (`point`, unit `normal` toward
    the under part) pressed back along the normal until it stands `most` past its rim's farthest point, where
    it stands farther by more than a bake lets it (`bake.DOME_SLACK`): read as the bake's gate reads a dome
    (`bake.hidden`), on the points `here` flags, those nearer this joint than the part's others. What of the
    dome lies no farther than the rim does stays where it is."""
    from . import bake
    out, f = np.array(vertices, float), np.asarray(part['f'], int)
    flag = lambda key: np.asarray(part.get(key, np.zeros(len(f), bool)), bool)
    added = bake._added(part) & ~flag('skin')
    closing, own = bake._used(out, f, added & ~flag('pad')), bake._used(out, f, ~added & ~flag('skin'))
    along = (out - point) @ normal
    shut = closing & np.asarray(here, bool)
    rim = shut & own & (along > -bake.ON_PLANE)
    if not rim.any():
        return out
    edge = float(along[rim].max())
    past = float(along[shut].max()) - edge
    if past <= most + bake.DOME_SLACK:
        return out
    dome = shut & ~own & (along > edge)
    out[dome] -= ((along[dome] - edge) * (1 - most / past))[:, None] * normal
    return out


def renormal(normals, faces, before, after):
    """Per-vertex `normals` carried from the vertices `before` to `after`: turned as the faces round each turned."""
    n = np.asarray(normals, float) + ends.normals(after, faces) - ends.normals(before, faces)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def under_skin(vertices, point, normal, skin, gap=UNDER_SKIN, which=None):
    """`vertices` with what lies past the plane (`point`, unit `normal` toward the part), or the vertices
    `which` flags, held `gap` inside the surface `skin` (vertices, faces), the body's own or an outfit's part:
    a vertex standing less far inside it, as read along the normal of the skin's nearest vertex, is moved in
    along that normal."""
    out = np.array(vertices, float)
    past = np.flatnonzero((out - point) @ normal < 0 if which is None else np.asarray(which, bool))
    skin_v = np.asarray(skin[0], float)
    if not len(past) or not len(skin_v):
        return out
    skin_n = ends.normals(skin_v, np.asarray(skin[1], int))
    nearest = np.argmin(np.linalg.norm(out[past][:, None] - skin_v[None], axis=2), axis=1)
    standing = ((out[past] - skin_v[nearest]) * skin_n[nearest]).sum(axis=1)  # how far outside the skin, inside negative
    out[past] -= np.maximum(standing + gap, 0.0)[:, None] * skin_n[nearest]
    return out


def over_skin(part, start, end, gap=OVER_SKIN, rounds=OVER_ROUNDS):
    """`part`, holding the other body's own skin beside the outfit's (`bake.skinned`), with everything drawn
    over that skin (the sleeve's cloth, and the dome closing it at the armpit) held `gap` outside it. Each
    vertex of the skin is read along the ray square out from the part's bone (`start` to `end`) through it
    (`measure.beyond`): where it stands less than `gap` inside, the corners of the last face the ray crosses
    that faces out (the client draws no face from behind) are pushed out from the bone by the difference, the push spread over `rounds` rings of their
    neighbours, never less than a point needs, so the cloth moves as one and creases nowhere, and read again
    until it settles. The skin and a pad are not moved; a push past `OVER_MOST` in all, over every pass, fails, rather than ship a
    spike where a fold is read as the outside. After the last pass the cloth is read once more
    (`short_of_skin`), and a sleeve the skin still stands out through by more than a bake lets it
    (`bake.THROUGH`) fails here: the passes used to end without a word, whatever they left
    (review of the Human female refit, 2026-11-14). The male's sleeves, scaled by the rings at the shoulder and
    the elbow, lay up to 2.7 cm inside the Human female's fuller upper arm, and the arm kept below the hem
    showed through them with her arms raised; held clear of her whole arm by the sleeve's cloth alone, her
    arm still stood up to 9 mm through the dome carried from the male's armpit, and, held clear of the cloth
    turned in over it, 1.2 cm out of the cloth drawn (Facility Security, 2026-11-13)."""
    v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
    skin = np.asarray(part.get('skin', np.zeros(len(f), bool)), bool)
    if not skin.any() or skin.all():
        return part
    pad = np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
    ids = mesh_ops.weld_ids(v)
    count = int(ids.max()) + 1
    free = np.zeros(count, bool)
    free[ids[f[~skin & ~pad].ravel()]] = True
    free[ids[f[skin].ravel()]] = False
    cloth, points = f[~skin], np.unique(f[skin])
    start, axis = np.asarray(start, float), seams.unit(np.asarray(end, float) - np.asarray(start, float))
    pairs = mesh_ops.edges(f, ids)[0]
    rows, cols = np.concatenate([pairs[:, 0], pairs[:, 1]]), np.concatenate([pairs[:, 1], pairs[:, 0]])
    degree = np.maximum(np.bincount(rows, minlength=count), 1)
    moved, pushed = v.copy(), np.zeros(count)
    for _ in range(OVER_PASSES):  # the cloth pushed out may still lie inside the arm between its points
        outside, face, _ = measure.beyond(moved[points], start, axis, moved, cloth, facing=True)
        short = np.flatnonzero(face >= 0)
        short = short[outside[short] > -gap]
        if not len(short):
            break
        need = np.zeros(count)
        np.maximum.at(need, ids[cloth[face[short]]].ravel(), np.repeat(outside[short] + gap, 3))
        need = np.where(free, need, 0.0)
        push = need.copy()
        for _ in range(rounds):
            push = np.where(free, np.maximum(need, np.bincount(rows, push[cols], minlength=count) / degree), 0.0)
        pushed += push
        require(pushed.max() <= OVER_MOST, f'Held outside the body\'s own skin, the outfit would move {pushed.max() * 100:.1f} cm, '
                                           f'past {OVER_MOST * 100:.0f} cm: a fold read as its outside, or a body too far from this one')
        radial = moved - start - ((moved - start) @ axis)[:, None] * axis
        moved = moved + push[ids][:, None] * radial / np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-12)
    from . import bake
    held = part if np.array_equal(moved, v) else {**part, 'v': moved, 'n': renormal(part['n'], f, v, moved)}
    left = short_of_skin(held, start, start + axis, gap)
    require(left <= gap + bake.THROUGH, f'Pushed out {OVER_PASSES} times, the outfit still lies up to {(left - gap) * 100:.1f} cm inside the '
                                        "body's own skin beside it: more passes, or a body too far from this one")
    return held


def short_of_skin(part, start, end, gap=OVER_SKIN):
    """How far, in metres, what is drawn over the body's own skin in `part` (`bake.skinned`) still stands short
    of `gap` outside it at most, read as `over_skin` reads it: 0 where it clears the skin by `gap` everywhere,
    `gap` where it lies on the skin, more where the skin stands out through it. A part with no skin, or none
    of the outfit's, is short of nothing."""
    v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
    skin = np.asarray(part.get('skin', np.zeros(len(f), bool)), bool)
    if not skin.any() or skin.all():
        return 0.0
    start = np.asarray(start, float)
    outside, face, _ = measure.beyond(v[np.unique(f[skin])], start, seams.unit(np.asarray(end, float) - start), v, f[~skin], facing=True)
    return max(float((outside[face >= 0] + gap).max()) if (face >= 0).any() else 0.0, 0.0)


def seated(part, point, normal, over, gap=split.SEAT_GAP, others=()):
    """`part`'s vertices with the cap the bake grew past its under end's plane (`point`, unit `normal` toward
    the part) brought into the other body's part over the joint, `over` (vertices, faces of its outfit's own
    surface): drawn toward the plane until it runs no deeper than that part stands over the joint less `gap`
    (`split.room`, as a bake seats an end), then each of its points held `gap` inside it (`under_skin`). The
    cap is what only the split's faces (`added`) use, its points matched by position across the part's
    texture seams, nearer this joint's point than the part's other joints' (`others`): a pelvis's domes at the
    hips are no part of its end at the waist. The male's upper arm ran 10 cm into his chest, and on the Human
    female's own chest stood 4 to 5 cm out of it (Facility Security, 2026-11-13)."""
    from . import bake
    v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
    added = np.asarray(part['added'], bool) & ~np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
    if 'skin' in part:
        added &= ~np.asarray(part['skin'], bool)
    cap = bake._used(v, f, added) & ~bake._used(v, f, ~added)
    here = np.linalg.norm(v - point, axis=1)
    for other in others:
        cap &= here < np.linalg.norm(v - np.asarray(other, float), axis=1)
    room = split.room(over[0], over[1], point, normal)
    if not cap.any() or room is None or (np.abs(measure.winding(v[cap], np.asarray(over[0], float), np.asarray(over[1], int))) >= 0.5).all():
        return v  # an end already inside the part over it stays as the bake made it: the pelvis's at the waist, drawn in, stood out turned
    height = (v - point) @ normal
    deepest, depth = -float(height[cap].min()), room - gap
    out = v.copy()
    if deepest > depth > 0:
        drawn = cap & (height < 0)
        out[drawn] -= (height[drawn] * (1 - depth / deepest))[:, None] * normal
    return under_skin(out, point, normal, over, gap, which=cap)


def refit(parts, source, target, names=None, contract=None, bodies=None, tier=2, bare=()):
    """(parts, report): baked parts (`bake.stored`) carried from the body `source` to the body `target`, each a
    (rig, parts by token) pair as `measure.body` gives them. `names` limits the parts carried; the rest are
    left out. Each part's vertices and normals are carried by its `placement`; with `contract` and `bodies`,
    the two bodies' names, its scale across follows the contract's body rings and its ends at the tube joints
    are brought to tier `tier`'s envelopes on the target (`ends.shaped`; a pad's
    faces, `pad`, are no part of a ring), skin-tight at the joints `bare` names (`ends.ends_of`) with the cap
    there held inside the target body's own part across the joint (`under_skin`). A tapered part is carried by
    its slope instead of its placement (`tapered`), its standoff from the source body's own part kept as it was. Each under end's cap then runs the target's overlap at `tier` past its plane
    (`deepened`; into a torso carried too no deeper than that stands over the joint, `split.room`, and where
    the torso is not carried the end is left for `seated`), and each over end's dome stands no more than the
    contract's `domeMost` past its rim (`flattened`). A part holding the source
    body's skin is carried without it (`bodyskin.unworn`). Nothing else about a part changes. `report` maps a
    part to its turn in degrees and its scales along and across; a shoulder pad's names the part it is carried
    with (`with`) and holds that part's scales. A part's faces the client would show a hole at are turned out
    (`bake.faced_out`), and the report holds how many (`turnedOut`)."""
    names = list(parts) if names is None else list(names)
    require(set(names) <= set(parts), f'No such part to refit: {", ".join(sorted(set(names) - set(parts)))}')
    from . import bake
    out, report = {}, {}
    for name in sorted(names, key=lambda name: name not in TORSO_FIRST):
        linear, offset, scales = placement(name, source, target, contract, bodies)
        part = dict(bodyskin.unworn(parts[name]))
        v, f, n = np.asarray(part['v'], float), np.asarray(part['f'], int), np.asarray(part['n'], float)
        slope = taper(name, source, target, contract, bodies)
        before, v = v, v @ linear.T + offset
        n = n @ np.linalg.inv(linear)  # normals carried by the inverse transpose
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        if slope is not None:  # by its slope instead, its normals turned on from the one map's as the faces round each turned
            n, v = renormal(n, f, v, tapered(before, slope)), tapered(before, slope)
        if contract is not None:
            part_ends = ends.ends_of(name, target[0], contract, bodies[1], tier, bare=bare)
            if part_ends:
                measured = ~np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
                shaped = capped(v, ends.shaped(v, f, measured, part_ends), f, measured, part_ends)
                for joint, side in bare:  # under the body's own skin: its part across the joint on the other body
                    letter = 'l' if side == 'c' else side
                    over = split.token(seams.JOINTS[joint]['over'], letter)
                    if split.token(seams.JOINTS[joint]['under'], letter) == name and over in target[1]:
                        point, normal = seams.plane(target[0], joint, letter)
                        shaped = under_skin(shaped, np.asarray(point, float), seams.unit(normal), target[1][over][:2])
                n, v = renormal(n, f, v, shaped), shaped
            met, centres = joints_of(name), anchors(name, target[0])
            cut = [k for k, (joint, side, _) in enumerate(met) if (joint, side) not in bake.UNCUT]
            nearest = np.array(cut)[np.linalg.norm(v[:, None] - centres[cut][None], axis=2).argmin(axis=1)] if cut else np.zeros(len(v), int)
            moved = v
            for k in cut:
                joint, side, other = met[k]
                letter = 'l' if side == 'c' else side
                normal = seams.unit(seams.plane(target[0], joint, letter)[1])
                if split.token(seams.JOINTS[joint]['under'], letter) != name:
                    moved = flattened(part, moved, centres[k], normal, nearest == k, contract.get('ends', seams.ENDS)['domeMost'])
                    continue
                least = seams.overlap(contract, joint, bodies[1], tier)
                depth = least + ends.DEEPER
                if joint in measure.TORSO_OPENINGS:
                    if other not in out:
                        continue  # the torso is the other body's own bake: `seated` brings the end into it
                    room = split.room(*bake._outfit(out[other])[:2], centres[k], normal)
                    if room is not None:  # as the bake's gate asks it (`bake.ends`)
                        least, depth = min(least, room - split.SEAT_GAP - bake.ROOM_SLACK), min(depth, room - split.SEAT_GAP)
                deeper = deepened(moved, centres[k], normal, least, depth)
                if (joint, side) in bare and other in target[1] and not np.array_equal(deeper, moved):
                    deeper = under_skin(deeper, centres[k], normal, target[1][other][:2])
                moved = deeper
            if not np.array_equal(moved, v):
                n, v = renormal(n, f, v, moved), moved
        part['f'], n, turned = bake.faced_out(name, v, f, n, target[0])  # before the other body's skin is laid beside it
        part['v'], part['n'] = v, n
        part, dropped = whole(part)
        out[name] = part
        turn = linear / np.cbrt(np.linalg.det(linear))
        u, _, vt = np.linalg.svd(turn)
        report[name] = {'degrees': round(float(np.degrees(np.arccos(np.clip((np.trace(u @ vt) - 1) / 2, -1.0, 1.0)))), 2), **scales,
                        **({'dropped': dropped} if dropped else {}), **({'turnedOut': turned} if turned else {})}
    return {name: out[name] for name in names}, {name: report[name] for name in names}


def whole(part):
    """(part, how many triangles it lost): `part` without the triangles that shrinking it left with two corners
    within `split.POINT` of each other, which the model compiler drops; its flags per face (`FACE_KEYS`) cut
    down alike. A glove's cap drawn in under the Human female's forearm closed two of its triangles at the pole
    to a point (Facility Security, 2026-11-13)."""
    v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
    sides = np.min([np.linalg.norm(v[f[:, i]] - v[f[:, (i + 1) % 3]], axis=1) for i in range(3)], axis=0) if len(f) else np.zeros(0)
    keep = sides >= split.POINT
    if keep.all():
        return part, 0
    return {**part, **{key: np.asarray(part[key])[keep] for key in FACE_KEYS if key in part}}, int((~keep).sum())


def run(kept, output, body_pack, source, target, names=None, tier=2, body_textures=None, seat_in=None):
    """Refit the parts kept in the folder `kept` (`bake.store`) from body `source` to body `target`, both read
    from `body_pack`, their ends shaped to the target's seam contract at tier `tier`, and keep them in the
    folder `output` with the slots the brief they were baked from left to the body and shared with its skin,
    for `bake --kept OUTPUT --body TARGET` to tint, write and gate on the other body. A part in a slot shared
    with the body's skin gets the target body's own beside it, read with its textures from `body_textures`
    (`bake.skinned`). Where the parts kept in the folder `seat_in`, baked on the target, hold the part over
    a carried part's under end, and it is not carried too, that end's cap is seated in it (`seated`).
    Returns `refit`'s report, with, for a part beside the body's skin, how far it was pushed out over it
    (`overSkin`) and how far it still stands short of `OVER_SKIN` outside it (`shortOfSkin`, 0 where it
    clears it), and for any part the area of its faces the client would show a hole at (`seenThrough`,
    `bake.facing`): more than a bake allows fails, after the parts are kept for a look."""
    from . import bake, measure
    require(Path(output).resolve() != Path(kept).resolve(), 'Refit parts are kept in another folder than the parts they came from')
    listed = bake.listing(kept)
    left = [token for slot in listed['bare'] for token in registry.SLOTS[slot]['tokens']]
    goal = measure.body(body_pack, target)
    parts, report = refit(bake.stored(kept), measure.body(body_pack, source), goal, names,
                          seams.load_contract(), (source, target), tier, bake.bare_joints({'left': left}))
    beside = bake.stored(seat_in) if seat_in is not None else {}
    for name in parts:
        met = joints_of(name)
        points = anchors(name, goal[0])
        for k, (joint, side, over) in enumerate(met):
            letter = 'l' if side == 'c' else side
            if split.token(seams.JOINTS[joint]['under'], letter) == name and over in beside and over not in parts:
                moved = seated(parts[name], points[k], seams.unit(seams.plane(goal[0], joint, letter)[1]), bake._outfit(beside[over])[:2],
                               others=np.delete(points, k, axis=0))
                if not np.array_equal(moved, parts[name]['v']):
                    parts[name] = {**parts[name], 'v': moved, 'n': renormal(parts[name]['n'], parts[name]['f'], parts[name]['v'], moved)}
                    report[name].setdefault('seated', []).append(f'{joint} {side}')
    if bake.shared_with_body(listed) & set(parts):
        require(body_textures is not None, f'{", ".join(sorted(bake.shared_with_body(listed) & set(parts)))} share their slots with the body\'s '
                                           'skin: give the body\'s textures to lay the other body\'s beside them')
        parts = bake.skinned(parts, listed, body_pack, body_textures, target, goal[0])
        for name in bake.shared_with_body(listed) & set(parts):
            held = over_skin(parts[name], *split.bone_line(goal[0], name))
            if held is not parts[name]:
                report[name]['overSkin'] = round(float(np.linalg.norm(held['v'] - parts[name]['v'], axis=1).max()), 4)
                parts[name] = held
            report[name]['shortOfSkin'] = round(short_of_skin(parts[name], *split.bone_line(goal[0], name)), 4)
    bake.store(parts, output, {key: value for key, value in listed.items() if key != 'parts'})
    faced, failures = bake.facing(parts, goal[0])
    for name, area in faced.items():
        if area:
            report[name]['seenThrough'] = area
    require(not failures, f'The parts kept in {output} do not pass: ' + '; '.join(failures))
    return report
