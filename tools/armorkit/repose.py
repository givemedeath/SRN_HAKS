"""A generated outfit is bent from its own stance onto a body's rest pose and widened to clear that body.

A generated outfit has its own proportions and stance: shorter legs, arms held out and bent. The joint planes of
the seam contract are the body's, so the outfit's knees, elbows and hips have to sit on the body's joints before
`split` can cut it. Its joints are found from horizontal sections (the floor, the crotch, the armpits and the
neck, with the limbs followed section to section), each of its bones is carried onto the body's bone, and the
result is widened about each bone wherever the body would stand outside it. The body is never changed.

Everything here works in the bodies' axes: z up, the figure facing +y, its left at -x."""
import math
from pathlib import Path

import numpy as np

from tools.headkit import gltf
from tools.robes import mesh_ops

from . import seams, split
from .registry import require

LEVELS = 240  # horizontal sections taken through the outfit
BIG, FINE = 0.15, 0.05  # a section curve counts as torso, arm or leg from this share of the outfit's height round; a wrist from this
NECK = 0.45  # the neck starts where the torso's curve is narrower than this share of its widest above the armpits
STEP_LIMIT = 0.05  # a limb is followed to the next section's curve only within this share of the height
FEW = 3  # sections a limb is followed for at least: fewer is a sliver
SLEEVE = 4  # sections in a row with something beside the torso, above a stretch with nothing: a short sleeve over a bare arm
JOINED = 1.15  # above a short sleeve the torso's curve is at least this much wider than beside it: the sleeves have joined it
GAP = 0.05  # a glove lies at least this share of the height below its sleeve's hem: less is a section missing from a whole arm
ARM = 0.6  # an outfit's arm, as far as it is followed, is at least this share of the body's from shoulder to fingertips
STRAY = 0.008  # a sleeve's ring lies this share of the height from the line through the others at most, or it is left out
ROUND, WIDE = 0.06, 0.45  # a short sleeve's ring has its middle within this share of the height of the line through its glove,
# and is no longer round than this share: a loose sleeve, and never the torso
CLEARANCE = 0.012  # how far the fitted outfit stands outside the body: the seam contract's cloth tier
SECTORS, RING = 24, 0.02  # the fit compares outfit and body in this many directions round a bone, in rings this tall
WIDEST = 1.8  # the fit never widens the outfit by more than this
LEGS_APART = 0.002  # each leg of the fitted outfit stays this far on its own side of the middle between the hips
# Bones as (name, joint at its start, joint at its end). `hips` is the point between the hip joints.
BONES = [('pelvis', 'waist', 'hips'), ('torso', 'waist', 'neck'), ('neck', 'neck', 'top')] + [
    (name + side, start + side, end + side) for side in 'lr' for name, start, end in
    (('thigh', 'hip', 'knee'), ('shin', 'knee', 'ankle'), ('foot', 'ankle', 'toe'), ('upper', 'shoulder', 'elbow'),
     ('fore', 'elbow', 'wrist'), ('hand', 'wrist', 'tip'))]
# How thick each bone's part of an outfit is, as a share of the outfit's height: what decides which bone a vertex follows.
THICK = {'pelvis': 0.115, 'torso': 0.115, 'neck': 0.05, 'thigh': 0.055, 'shin': 0.045, 'foot': 0.045, 'upper': 0.042,
         'fore': 0.036, 'hand': 0.03}
BLEND = 0.45  # a vertex also follows a bone this much farther away (in thicknesses) than its nearest, fading to nothing
SMOOTHING = 6  # passes that even the bone weights out over the surface, so no bone boundary tears it
THUMB = 1.3  # a glove's thumb side reaches at least this much farther from the middle of its flat than the other side
GLOVE = 20  # faces of an outfit that follow a hand, at least, for a glove to be turned
KNUCKLES = 0.55  # a glove's fingers start this share of its length from the wrist
CURL = math.radians(70)  # and bend toward its palm by this much at their tips, as a hand at rest curls
PALM = 0.002  # a glove's thumb lies this far to one side of its middle at least, or which side is its palm is not told
GLOVE_SKIN = 0.004  # a glove drawn in to the body's hand stands this far outside it a side: the seam contract's tier 0
HAND_RING = 0.01  # glove and hand are compared in rings this tall along the hand bone
HAND_ENDS = (0.01, 0.02)  # the hand's rings this near its wrist end and its fingertips are its rounded ends: the glove is held to the ring beside them
NARROWEST = 0.5  # a glove is never drawn in to less than this share of its width
# The body part the outfit is fitted round, per bone. Hands and feet are not fitted: gloves and boots replace the
# body's closed fists and bare toes, and widening a boot round the toes turns it into a flipper.
SKIN = {'pelvis': 'pelvis', 'torso': 'chest', 'neck': 'neck', 'thigh': 'leg', 'shin': 'shin', 'upper': 'bicep', 'fore': 'fore'}


def kind(bone):
    """A bone's name without its side letter."""
    return bone[:-1] if bone[:-1] in THICK else bone


def load(path):
    """(vertices, faces) of a generated mesh file, welded and turned from glTF's axes (y up, facing +z) to the bodies'."""
    mesh = gltf.mesh(Path(path))
    points = np.asarray(mesh['positions'], float)
    ids = mesh_ops.weld_ids(points, 1e-6)
    first = np.unique(ids, return_index=True)[1]
    faces = ids[np.asarray(mesh['faces'], int)]
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    return np.stack([-points[first, 0], points[first, 2], points[first, 1]], axis=1), faces


def slices(vertices, faces, levels):
    """Per level, the curves of the horizontal section there: dicts of `centre` (x, y), `perimeter`, `lo` and `hi`."""
    up = np.array([0.0, 0.0, 1.0])
    u, v = seams.frame(up)
    rows = []
    for z in levels:
        found = []
        segments = seams.section(vertices, faces, np.array([0.0, 0.0, z]), up)
        if len(segments):
            world = segments[..., :1] * u[:2] + segments[..., 1:] * v[:2]
            curve = split.curves(segments)[0]
            for label in np.unique(curve):
                mine = world[curve == label]
                length = np.linalg.norm(mine[:, 1] - mine[:, 0], axis=1)
                points = mine.reshape(-1, 2)
                found.append({'centre': ((mine[:, 0] + mine[:, 1]) / 2 * length[:, None]).sum(axis=0) / max(length.sum(), 1e-12),
                              'perimeter': float(length.sum()), 'lo': points.min(axis=0), 'hi': points.max(axis=0)})
        rows.append(sorted(found, key=lambda row: row['centre'][0]))
    return rows


def landmarks(vertices, faces):
    """Heights of a standing outfit's `floor`, `crotch`, `armpit`, `neck` and `top`, with the sections they come from.

    The crotch is the lowest section with a curve across the middle (the legs never cross it), the armpit the
    lowest above it and above the hands with nothing beside that curve (the arms have joined the torso), and the
    neck where that curve has narrowed to a share of its widest. Arms held out from the body end above the hips,
    so the sections between have nothing beside the torso either; they are below the lowest one that has. An
    arm bare between a short sleeve and a glove has nothing beside the torso along the forearm either, and the
    first build of such an outfit put its armpit just above the gloves without a word: the armpit is above
    a stretch of `SLEEVE` sections that have something beside the torso, where the torso's curve is `JOINED`
    wider above that stretch than in it. That is a sleeve joining the torso. A shoulder guard that stands
    off above the armpit has something beside the torso too, and the torso is no wider above it: the arms
    joined it lower down. `torso(curve)` says whether a curve crosses the middle; `big` and `fine` hold the
    sections' curves above the two size limits."""
    vertices = np.asarray(vertices, float)
    floor, top = float(vertices[:, 2].min()), float(vertices[:, 2].max())
    height = top - floor
    require(height > 0, 'The outfit has no height')
    levels = np.linspace(floor + 0.002 * height, top - 0.002 * height, LEVELS)
    rows = slices(vertices, faces, levels)
    middle = float(np.median(vertices[:, 0]))
    big = [[curve for curve in row if curve['perimeter'] > BIG * height] for row in rows]
    torso = lambda curve: curve['lo'][0] < middle - 0.02 * height and curve['hi'][0] > middle + 0.02 * height
    crotch = next((i for i, row in enumerate(big) if any(torso(curve) for curve in row)), None)
    require(crotch is not None and crotch > 0, 'No crotch found: the legs must stand apart below the torso')
    alone = [bool(row) and all(torso(curve) for curve in row) for row in big]
    beside = [any(not torso(curve) for curve in row) for row in big]
    hands = next((i for i in range(crotch + 1, LEVELS) if beside[i]), LEVELS)
    armpit = next((i for i in range(max(hands, crotch + LEVELS // 10), LEVELS - 4) if all(alone[i:i + 4])), None)
    width = [max((curve['hi'][0] - curve['lo'][0] for curve in row if torso(curve)), default=0.0) for row in big]
    while armpit is not None:
        sleeve = next((i for i in range(armpit + 4, LEVELS - SLEEVE) if all(beside[i:i + SLEEVE])), None)
        above = None if sleeve is None else next((i for i in range(sleeve + SLEEVE, LEVELS - 4) if all(alone[i:i + 4])), None)
        if above is None or max(width[above:above + 4]) < JOINED * max(width[sleeve:sleeve + SLEEVE]):
            break
        armpit = above
    require(armpit is not None, 'No armpit found: the arms must hang clear of the torso and join it at the shoulders')
    neck = next((i for i in range(armpit + 3, LEVELS) if width[i] < NECK * max(width[armpit:])), None)
    require(neck is not None, 'No neck found: the outfit must narrow to a collar above the shoulders')
    return {'floor': floor, 'top': top, 'crotch': float(levels[crotch]), 'armpit': float(levels[armpit]), 'neck': float(levels[neck]),
            'middle': middle, 'height': height, 'levels': levels, 'torso': torso, 'big': big,
            'fine': [[curve for curve in row if curve['perimeter'] > FINE * height] for row in rows]}


def centreline(marks, side, top, limb):
    """Rows of (z, x, y, perimeter): one limb's section centres, followed down from `top` curve to curve.

    `side` is -1 for the left, +1 for the right. A `leg` starts at the curve nearest the middle, an `arm` at the
    outermost one; the walk ends where the next section has no curve close to the last one, so an arm is not
    followed into the leg beside the hand. A walk that ends before `FEW` sections is a sliver and starts again
    below it, once, within `STEP_LIMIT`: the top of a loose short sleeve, cut apart from the torso for a
    section or two above where the sleeve joins it (Facility Security, 2026-11-13: the armpit was found above
    that join and the arm was its one section). Rows run upward."""
    rows, last, dropped = [], None, None
    for index in range(len(marks['levels']) - 1, -1, -1):
        z = marks['levels'][index]
        if z > top:
            continue
        mine = [curve for curve in marks['big' if last is None else 'fine'][index]
                if not marks['torso'](curve) and (curve['centre'][0] - marks['middle']) * side > 0]
        if not mine:
            if last is None:
                if dropped is not None and z < dropped - STEP_LIMIT * marks['height']:
                    break
                continue
            if len(rows) < FEW and dropped is None:
                dropped, rows, last = rows[-1][0], [], None
                continue
            break
        if last is None:
            mine.sort(key=lambda curve: abs(curve['centre'][0] - marks['middle']))
            pick = mine[0] if limb == 'leg' else mine[-1]
        else:
            pick = min(mine, key=lambda curve: np.linalg.norm(curve['centre'] - last))
            if np.linalg.norm(pick['centre'] - last) > STEP_LIMIT * marks['height']:
                break
        last = pick['centre']
        rows.append((z, pick['centre'][0], pick['centre'][1], pick['perimeter']))
    require(len(rows) >= FEW, f'No {limb} found on the {"left" if side < 0 else "right"}')
    return np.array(rows[::-1])


def past(marks, side, line):
    """Rows like `centreline`'s of what lies beyond an arm's end: the glove of an arm bare below a short sleeve.

    `line` is the arm as `centreline` followed it, which ends at the sleeve's hem. Below that end, the first
    section curve beside the torso and farther from the middle than the hem is starts the glove, the
    outermost if there are several, and it is followed as a limb is. An arm held out from the body goes
    outward as it goes down, and a leg, beside the torso too, stands inside the shoulders. A sleeve's own
    few sections do not give a line to look along: on a sleeve that ends halfway down the upper arm they are
    five slivers of its hem. No rows where nothing is there: the arm of a long sleeve ends at its fingertips."""
    rows, last = [], None
    out = abs(line[0, 1] - marks['middle'])
    for index in range(len(marks['levels']) - 1, -1, -1):
        z = marks['levels'][index]
        if z >= line[0, 0]:
            continue
        mine = [curve for curve in marks['fine'][index]
                if not marks['torso'](curve) and (curve['centre'][0] - marks['middle']) * side > (out if last is None else 0)]
        if not mine:
            if last is None:
                continue
            break
        if last is None:
            pick = max(mine, key=lambda curve: abs(curve['centre'][0] - marks['middle']))
        else:
            pick = min(mine, key=lambda curve: np.linalg.norm(curve['centre'] - last))
            if np.linalg.norm(pick['centre'] - last) > STEP_LIMIT * marks['height']:
                break
        last = pick['centre']
        rows.append((z, pick['centre'][0], pick['centre'][1], pick['perimeter']))
    return np.array(rows[::-1]).reshape(-1, 4)


def rings(vertices, faces, start, toward, height):
    """Middles of a short sleeve's rings, or its glove's: the closed sections across the line from `start` to `toward`.

    `toward` is a first guess at a point inside the sleeve, `start` one inside the glove, or the other way round. Sections are taken across that line every 1% of
    the outfit's `height` round the guess, and a closed curve counts when its middle lies within `ROUND` of
    the line and it is no longer round than `WIDE`: the sleeve where it is a tube, between its hem and the
    armpit, where it joins the torso's curve. Of several such curves in one section the nearest the line is
    taken: a thigh beside a hanging hand is a ring too. Empty when no section there is a ring."""
    axis = seams.unit(toward - start)
    u, v = seams.frame(axis)
    found = []
    for step in range(-8, 9):
        point = toward + axis * step * 0.01 * height
        segments = seams.section(vertices, faces, point, axis)
        if not len(segments):
            continue
        curve, ids = split.curves(segments)
        here = []
        for label in np.unique(curve):
            mine, ends = segments[curve == label], ids[curve == label]
            length = np.linalg.norm(mine[:, 1] - mine[:, 0], axis=1)
            middle = ((mine[:, 0] + mine[:, 1]) / 2 * length[:, None]).sum(axis=0) / max(length.sum(), 1e-12)
            closed = (np.bincount(np.unique(ends, return_inverse=True)[1].ravel()) == 2).all()
            if closed and np.linalg.norm(middle) < ROUND * height and FINE * height < length.sum() < WIDE * height:
                here.append(middle)
        if here:
            middle = min(here, key=np.linalg.norm)
            found.append(point + middle[0] * u + middle[1] * v)
    return np.array(found).reshape(-1, 3)


def through(points, toward, height):
    """(point, direction) of the straight line through a sleeve's ring middles, pointing down the arm, `toward` its glove.

    A ring that takes in a fold or a pocket, or a hem cut aslant, has its middle off the others': the farthest
    middle, while it lies farther than `STRAY` from the line, is left out and the line laid again, as long as
    two are left on it. One at a time: two hem rings on one side tilt the line through all of them toward
    themselves, and leaving out everything far from that line kept one of them and dropped good rings
    (Facility Security, 2026-11-13: the sleeve lay 17 degrees below level instead of 38, and its shoulder
    4 cm inside the body's). `toward` only says which way is down the arm: the line from the sleeve to the
    glove is a bent arm's chord, and no stand-in for the sleeve's own. One ring gives no line and is refused."""
    points, toward = np.asarray(points, float), np.asarray(toward, float)
    require(len(points) >= 2, 'A sleeve gives the line of its arm from two rings on')
    kept = points
    while True:
        middle = kept.mean(axis=0)
        along = np.linalg.svd(kept - middle)[2][0]
        off = np.linalg.norm((kept - middle) - ((kept - middle) @ along)[:, None] * along, axis=1)
        if len(kept) <= 2 or off.max() < STRAY * height:
            break
        kept = np.delete(kept, np.argmax(off), axis=0)
    return middle, along * (1.0 if (toward - middle) @ along >= 0 else -1.0)


def at(line, z):
    """The point of a centreline at a height, held at its ends beyond them."""
    return np.array([np.interp(z, line[:, 0], line[:, 1]), np.interp(z, line[:, 0], line[:, 2]), z])


def central(marks, z):
    """The middle of the torso's curve at the section nearest a height."""
    index = int(np.argmin(np.abs(marks['levels'] - z)))
    for step in range(12):
        for near in (index + step, index - step):
            if 0 <= near < len(marks['levels']):
                row = [curve for curve in marks['big'][near] if marks['torso'](curve)]
                if row:
                    return np.array([marks['middle'], row[0]['centre'][1], z])
    raise ValueError('The outfit has no torso near the height asked for')


def body_joints(bones, parts):
    """A body's joints by the names used here, from its bones and skin parts (`measure.body`).

    Also its `crotch` height (the underside of the pelvis at the middle) and the lengths of its `upper` arm,
    `fore` arm and `hand`, which place the outfit's elbow along its arm."""
    at_bone = lambda name: np.asarray(bones[name], float)[:3, 3]
    pelvis = np.asarray(parts['pelvis'][0], float)
    joints = {'waist': at_bone('torso_g'), 'neck': at_bone('neck_g'), 'crotch': float(pelvis[np.abs(pelvis[:, 0]) < 0.03][:, 2].min())}
    joints['top'] = joints['neck'] + np.array([0.0, 0.0, 0.06])
    for side in 'lr':
        for joint, bone in (('hip', 'thigh_g'), ('knee', 'shin_g'), ('ankle', 'foot_g'), ('shoulder', 'bicep_g'), ('elbow', 'forearm_g'),
                            ('wrist', 'hand_g')):
            joints[joint + side] = at_bone(side + bone)
        foot = np.asarray(parts['foot' + side][0], float)
        joints['toe' + side] = np.array([joints['ankle' + side][0], foot[:, 1].max(), 0.0])
        axis = seams.unit(joints['wrist' + side] - joints['elbow' + side])
        hand = np.asarray(parts['hand' + side][0], float)
        joints['tip' + side] = joints['wrist' + side] + axis * float(((hand - joints['wrist' + side]) @ axis).max())
    joints['hips'] = (joints['hipl'] + joints['hipr']) / 2
    joints['upper'] = float(np.linalg.norm(joints['elbowl'] - joints['shoulderl']))
    joints['fore'] = float(np.linalg.norm(joints['wristl'] - joints['elbowl']))
    joints['hand'] = float(np.linalg.norm(joints['tipl'] - joints['wristl']))
    return joints


def outfit_joints(vertices, faces, body):
    """(joints, landmarks) of an outfit: its joints placed where the body's sit between the same landmarks.

    Heights map from the body's to the outfit's through the floor, the crotch and the neck, so an outfit with
    short legs gets its knees and ankles where its own legs have them. A leg joint lies on the leg's centreline
    at its height. The shoulder lies on the upper arm's line, continued up to its height; the wrist is the
    narrowest section just above the palm, which is the widest near the arm's end (below it the sections are
    fingers); the elbow divides shoulder to wrist as the body's does. An arm bare between a short sleeve and a
    glove is the sleeve and the glove beyond it (`past`). Its upper arm lies on the line through the middles
    of the sleeve's rings (`rings`, `through`): the shoulder where that line reaches the shoulder's height,
    the elbow where the upper arm and the forearm on to the wrist are as long as the body's are to each
    other. Level sections do not give that line: they cut a hem aslant, and on the first such outfit their
    middles lay 6 cm toward the armpit. Nor does the line from the glove to the sleeve: an arm is bent a
    little at the elbow, and a trough cut along that line left the sleeve on the torso. A glove lies `GAP`
    or more below its sleeve: what `past` finds nearer, and no farther across than a step along a limb, is
    the rest of an arm that a thin section parted, a cuff stopping short of a glove, and the arm is followed
    on through it as a whole one. A glove that far below is taken only beyond an arm too short to be whole,
    shorter than `ARM` of the body's from shoulder to fingertips: below a whole arm's fingers, a boot or a
    holster farther out than they are was taken for one. An arm still that short is refused: a sleeve with no glove beyond it has no wrist to
    find, and its hem was taken for a hand. A long sleeve followed to the wrist only, its fingers apart, is
    three quarters of the body's arm and passes. `marks` also holds the outfit's `scale` to the body, neck
    height over neck height."""
    vertices = np.asarray(vertices, float)
    marks = landmarks(vertices, faces)
    knots = [0.0, body['crotch'], body['neck'][2]], [marks['floor'], marks['crotch'], marks['neck']]

    def level(z):
        if z > knots[0][2]:  # above the neck, as the torso runs
            return knots[1][2] + (z - knots[0][2]) * (knots[1][2] - knots[1][1]) / (knots[0][2] - knots[0][1])
        return float(np.interp(z, *knots))

    marks['scale'] = scale = float(body['neck'][2] / (marks['neck'] - marks['floor']))
    whole = ARM * (body['upper'] + body['fore'] + body['hand'])  # the least an arm is long, followed from the shoulder
    followed = lambda start, rows: float(np.linalg.norm(np.diff(np.concatenate([start[None], rows[::-1][:, [1, 2, 0]]]), axis=0), axis=1).sum()) * scale
    joints = {'waist': central(marks, level(body['waist'][2])), 'neck': central(marks, marks['neck'])}
    joints['top'] = joints['neck'] + np.array([0.0, 0.0, marks['top'] - marks['neck']])
    for sign, side in ((-1, 'l'), (1, 'r')):
        leg = centreline(marks, sign, marks['crotch'] - 0.01 * marks['height'], 'leg')
        hip = at(leg, marks['crotch'] - 0.03 * marks['height'])
        joints['hip' + side] = np.array([hip[0], hip[1], level(body['hip' + side][2])])
        joints['knee' + side] = at(leg, level(body['knee' + side][2]))
        joints['ankle' + side] = at(leg, level(body['ankle' + side][2]))
        below = vertices[(vertices[:, 2] < joints['ankle' + side][2]) & ((vertices[:, 0] - marks['middle']) * sign > 0)]
        require(len(below), 'The outfit has no foot below its ankle')
        joints['toe' + side] = np.array([joints['ankle' + side][0], below[:, 1].max(), marks['floor']])
        arm = centreline(marks, sign, marks['armpit'] - 0.005 * marks['height'], 'arm')
        upper = arm[arm[:, 0] > marks['armpit'] - 0.12 * marks['height']]
        require(len(upper) >= 2, f'The {"left" if sign < 0 else "right"} arm leaves the torso too far below the other to place its shoulder')
        height = level(body['shoulder' + side][2])
        shoulder = np.array([np.polyval(np.polyfit(upper[:, 0], upper[:, 1], 1), height), np.polyval(np.polyfit(upper[:, 0], upper[:, 2], 1), height), height])
        glove, straight = past(marks, sign, arm), None
        apart = len(glove) >= 3 and arm[0, 0] - glove[-1, 0] > GAP * marks['height']  # a bare forearm between
        rest = len(glove) >= 3 and not apart and np.linalg.norm(glove[-1, 1:3] - arm[0, 1:3]) <= STEP_LIMIT * marks['height']
        apart = apart and followed(shoulder, arm) < whole  # below a whole arm, a boot or a holster
        glove = glove if apart or rest else glove[:0]
        if apart:
            start, sleeve = (np.average(rows[:, [1, 2, 0]], axis=0, weights=rows[:, 3]) for rows in (glove, arm))
            for _ in range(2):
                found = rings(vertices, faces, start, sleeve, marks['height'])
                require(len(found), f'The {"left" if sign < 0 else "right"} sleeve is nowhere a tube round the line to its glove')
                sleeve = found.mean(axis=0)
                found = rings(vertices, faces, sleeve, start, marks['height'])
                start = found.mean(axis=0) if len(found) else start
            tube = rings(vertices, faces, start, sleeve, marks['height'])
            require(len(tube) >= 2, f'The {"left" if sign < 0 else "right"} sleeve is a tube for too short a way to give the line of its arm')
            middle, straight = through(tube, start, marks['height'])
            require(straight[2] < -0.2, f'The {"left" if sign < 0 else "right"} sleeve does not point down the arm')
            shoulder = middle + straight * (height - middle[2]) / straight[2]
        arm = np.concatenate([glove, arm])
        path = np.concatenate([shoulder[None], arm[::-1][:, [1, 2, 0]]])  # from the shoulder down the arm
        girth = np.concatenate([[arm[-1, 3]], arm[::-1, 3]])
        arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        require(arc[-1] * scale >= whole,
                f'The {"left" if sign < 0 else "right"} arm ends {arc[-1] * scale * 100:.0f} cm from the shoulder, short of a wrist: '
                'an arm bare below a short sleeve needs a glove beyond that sleeve')
        end = np.flatnonzero(arc > 0.8 * arc[-1])
        palm = end[np.argmax(girth[end])]
        window = np.flatnonzero((arc <= arc[palm]) & (arc > arc[palm] - 0.14 * arc[-1]))
        wrist = arc[window][np.argmin(girth[window])]
        point = lambda along: np.array([np.interp(along, arc, path[:, axis]) for axis in range(3)])
        joints['shoulder' + side], joints['wrist' + side], joints['tip' + side] = shoulder, point(wrist), point(arc[-1])
        joints['elbow' + side] = point(wrist * body['upper'] / (body['upper'] + body['fore']))
        if straight is not None:
            # the elbow on the sleeve's line, where the upper arm and the forearm on to the wrist are as long as the body's are to each other
            reach, ratio = joints['wrist' + side] - shoulder, body['fore'] / body['upper']
            a, b, c = 1 - ratio ** 2, -2 * float(reach @ straight), float(reach @ reach)
            far = c / -b if abs(a) < 1e-9 else (-b - np.sqrt(max(b * b - 4 * a * c, 0.0))) / (2 * a)
            joints['elbow' + side] = shoulder + straight * far
    joints['hips'] = (joints['hipl'] + joints['hipr']) / 2
    return joints, marks


def turn(a, b):
    """The smallest rotation taking unit vector a to unit vector b."""
    cross, dot = np.cross(a, b), float(a @ b)
    if np.linalg.norm(cross) < 1e-12:
        require(dot > 0, 'A bone cannot be turned to point the opposite way')
        return np.eye(3)
    skew = np.array([[0.0, -cross[2], cross[1]], [cross[2], 0.0, -cross[0]], [-cross[1], cross[0], 0.0]])
    return np.eye(3) + skew + skew @ skew / (1 + dot)


def turned(points, origin, axis, angle):
    """Points turned about the line through `origin` along unit `axis` by `angle` in radians, one or one per point."""
    points = np.asarray(points, float)
    angle = np.broadcast_to(np.asarray(angle, float), (len(points),))[:, None]
    relative = points - origin
    return origin + relative * np.cos(angle) + np.cross(axis, relative) * np.sin(angle) + axis * (relative @ axis)[:, None] * (1 - np.cos(angle))


def thumb_turn(points, wrist, tip):
    """The angle in radians a glove's `points` turn about the hand bone from `wrist` to `tip` to lie as the body's
    hand does, or 0 where no thumb stands out.

    The bodies hang their hands palm to thigh, the thumb forward (+y, the way they face). Across the bone a
    glove is widest across the palm and the thumb, and its thumb's side reaches `THUMB` or more farther from
    the bone than the other side does: the glove's own wrist and fingertips, which the bone runs through, lie
    on its middle, and the middle of its points does not (a large thumb drew it 3 cm aside). A flat glove from
    a front-view image hangs palm forward or back, and a fist or a mitten has no thumb to tell which way it
    faces: it is not turned."""
    axis = seams.unit(np.asarray(tip, float) - wrist)
    relative = np.asarray(points, float) - wrist
    across = relative - (relative @ axis)[:, None] * axis
    wide = np.linalg.svd(across - across.mean(axis=0), full_matrices=False)[2][0]
    reach = across @ wide
    out, back = float(np.percentile(reach, 99.5)), float(-np.percentile(reach, 0.5))
    if min(out, back) <= 0 or max(out, back) < THUMB * min(out, back):
        return 0.0
    thumb = wide * (1.0 if out > back else -1.0)
    forward = seams.unit(np.array([0.0, 1.0, 0.0]) - axis[1] * axis)
    return math.atan2(float(np.cross(thumb, forward) @ axis), float(thumb @ forward))


def repose(vertices, faces, here, there, scale, height, free=None):
    """(vertices, weights): the outfit with each of its bones carried onto the body's.

    `here` and `there` are the outfit's and the body's joints, `scale` the outfit's overall scale to the body
    and `height` the outfit's own height. Each bone turns the outfit onto its body bone, stretches it along the
    bone to the body's length and scales it across by `scale`. A vertex follows the bones it is nearest to,
    counted in each bone's own thickness; `weights[bone, vertex]` is evened out over the surface so that
    joints bend smoothly. `free[bone, vertex]`, if given, says which bones a vertex may follow at all: the
    torso's edge of a sleeve cut follows no bone of that arm, and the evening carries that into the torso.

    A bone turned the shortest way keeps its twist, and a glove that came flat, palm to the camera, hung palm
    forward round the body's fist (Facility Security, 2026-11-13). Each hand is also turned about its bone till
    its thumb lies forward (`thumb_turn`), and the forearm by a share of that growing from the elbow to the
    wrist, as a forearm turns a hand, so the cuff between them is not wrung."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    moved, distance = [], []
    for name, start, end in BONES:
        a, b, c, d = here[start], here[end], there[start], there[end]
        from_axis, to_axis = seams.unit(b - a), seams.unit(d - c)
        relative = vertices - a
        along = relative @ from_axis
        across = relative - along[:, None] * from_axis
        stretch = np.linalg.norm(d - c) / np.linalg.norm(b - a)
        moved.append(c + (across * scale + (along * stretch)[:, None] * from_axis) @ turn(from_axis, to_axis).T)
        nearest = np.clip(along, 0.0, np.linalg.norm(b - a))
        distance.append(np.linalg.norm(relative - nearest[:, None] * from_axis, axis=1) / (THICK[kind(name)] * height))
    distance = np.array(distance)
    free = np.ones(distance.shape, bool) if free is None else np.asarray(free, bool)
    require(free.shape == distance.shape and free.any(axis=0).all(), 'Every vertex is free to follow at least one bone')
    distance = np.where(free, distance, np.inf)
    weight = np.clip(1 - (distance - distance.min(axis=0)) / BLEND, 0.0, None)
    weight /= weight.sum(axis=0)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    count = np.maximum(np.bincount(edges[:, 0], minlength=len(vertices)), 1)
    for _ in range(SMOOTHING):
        around = np.array([np.bincount(edges[:, 0], weights=row[edges[:, 1]], minlength=len(vertices)) for row in weight])
        weight = np.where(free, 0.5 * weight + 0.5 * around / count, 0.0)
    weight /= weight.sum(axis=0)
    moved, names = np.array(moved), [bone[0] for bone in BONES]
    for side in 'lr':
        hand, fore = names.index('hand' + side), names.index('fore' + side)
        held = faces[(weight[hand][faces] > 0.5).all(axis=1)]
        if len(held) < GLOVE:
            continue
        wrist, elbow = there['wrist' + side], there['elbow' + side]
        angle = thumb_turn(surface(moved[hand], held, 4000, np.random.default_rng(0)), wrist, there['tip' + side])
        moved[hand] = turned(moved[hand], wrist, seams.unit(there['tip' + side] - wrist), angle)
        axis, length = seams.unit(wrist - elbow), float(np.linalg.norm(wrist - elbow))
        moved[fore] = turned(moved[fore], elbow, axis, angle * np.clip((moved[fore] - elbow) @ axis / length, 0.0, 1.0))
    return np.einsum('bv,bvk->vk', weight, moved), weight


def surface(vertices, faces, count, rng):
    """Points spread evenly over a mesh's surface."""
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    pick = rng.choice(len(faces), count, p=area / area.sum())
    s, t = rng.random(count), rng.random(count)
    over = s + t > 1
    s[over], t[over] = 1 - s[over], 1 - t[over]
    return a[pick] + s[:, None] * (b[pick] - a[pick]) + t[:, None] * (c[pick] - a[pick])


def fit(posed, weight, there, parts, clearance=CLEARANCE):
    """(vertices, report): the posed outfit widened about each bone until it stands outside the body's part there.

    Round each fitted bone, outfit and body are compared by direction and height. Where the body would stand
    outside the outfit, the outfit is scaled out from the bone by a factor that is evened over neighbouring
    directions and heights, so its relief keeps its shape; a vertex still inside after that is set
    `clearance / 2` outside the body. Vertices move only by the share they follow each bone. `report` maps a
    bone to its largest factor and the number of vertices set outside one by one.

    One by one, the body is as wide as the narrowest of a vertex's own ring and the rings next to it along
    the bone. A ring holds the body's largest radius in it, and where the body's surface turns across the
    bone (the top of a shoulder) that is the shoulder's width for a vertex lying on the slope above it: set
    outside that, it went centimetres out sideways, away from the vertices beside it, and folded the cloth
    between them."""
    posed = np.asarray(posed, float)
    rng = np.random.default_rng(0)
    result, used, report = np.zeros_like(posed), np.zeros(len(posed)), {}
    for index, (name, start, end) in enumerate(BONES):
        if kind(name) not in SKIN:
            continue
        origin, axis = there[start], seams.unit(there[end] - there[start])
        u, v = seams.frame(axis)

        def polar(points):
            relative = points - origin
            return relative @ axis, np.arctan2(relative @ v, relative @ u), np.hypot(relative @ u, relative @ v)

        skin = parts[SKIN[kind(name)] + (name[-1] if kind(name) != name else '')]
        body_h, body_angle, body_r = polar(surface(np.asarray(skin[0], float), np.asarray(skin[1], int), 60000, rng))
        low = math.floor(body_h.min() / RING) - 1
        rings = math.ceil(body_h.max() / RING) + 1 - low
        cell = lambda h, angle: (np.clip(np.floor(h / RING).astype(int) - low, 0, rings - 1),
                                 np.floor((angle + math.pi) / (2 * math.pi) * SECTORS).astype(int) % SECTORS)
        body = np.zeros((rings, SECTORS))
        np.maximum.at(body, cell(body_h, body_angle), body_r)
        mine = np.flatnonzero(weight[index] > 0.02)
        h, angle, r = polar(posed[mine])
        ring, sector = cell(h, angle)
        beside = (h >= body_h.min() - RING) & (h <= body_h.max() + RING)
        total, count = np.zeros((rings, SECTORS)), np.zeros((rings, SECTORS))
        np.add.at(total, (ring[beside], sector[beside]), r[beside])
        np.add.at(count, (ring[beside], sector[beside]), 1)
        outfit = np.where(count > 0, total / np.maximum(count, 1), 0.0)
        factor = np.where((body > 0) & (outfit > 0), np.clip((body + clearance) / np.maximum(outfit, 1e-6), 1.0, WIDEST), 1.0)
        for _ in range(2):
            padded = np.pad(factor, ((1, 1), (0, 0)), mode='edge')
            factor = np.maximum(sum(np.roll(padded[1 + dr:rings + 1 + dr], dc, axis=1) for dr in (-1, 0, 1) for dc in (-1, 0, 1)) / 9, 1.0)
        grown = r * np.where(beside, factor[ring, sector], 1.0)
        along_bone = np.pad(np.where(body > 0, body, np.inf), ((1, 1), (0, 0)), constant_values=np.inf)
        level = np.minimum(np.minimum(along_bone[:-2], along_bone[2:]), along_bone[1:-1])  # the body's width, a ring either way
        least = np.where(beside & (body[ring, sector] > 0), level[ring, sector] + clearance / 2, 0.0)
        relative = posed[mine] - origin
        along = (relative @ axis)[:, None] * axis
        moved = origin + along + (relative - along) * (np.maximum(grown, least) / np.maximum(r, 1e-9))[:, None]
        result[mine] += weight[index][mine, None] * moved
        used[mine] += weight[index][mine]
        report[name] = (round(float(factor.max()), 3), int(np.count_nonzero(least > grown)))
    return result + (1 - used)[:, None] * posed, report


def gloved(posed, weight, there, parts):
    """(vertices, report): each glove's fingers bent toward its palm, and the glove drawn in to the body's hand.

    A generated glove is an open hand, its fingers spread and its thumb out, as the figure was drawn with its
    arms held out; the bodies hang a closed hand at their sides, and the glove takes its place. Facility
    Security's gloves stood up to 3 cm wider than the body's hands, 3 cm forward of them, and 2 cm past
    their knuckles, and in the client they were large flat paddles at the ends of the arms (2026-11-13).

    Past `KNUCKLES` of its length from the wrist a glove is bent about the line across its knuckles toward its
    palm, by `CURL` at its fingertips, as a hand at rest curls. Its palm is the side its thumb lies on, the
    thumb being what reaches farthest forward (`thumb_turn` turned it there): the bodies hang their hands palm
    to thigh. A glove whose thumb lies within `PALM` of its middle is not bent. Then, in rings `HAND_RING` tall
    along the hand bone, the glove is drawn onto the body's hand: across the thumb the middle of each ring
    onto the hand's, and across the thumb and the palm its width, where wider than the hand's and
    `GLOVE_SKIN` a side, down to that, never below `NARROWEST` of what it was. Across the palm a ring keeps
    its middle: there the curl moved it, and set back on the hand's middle the fingertips stood straight again. The hand's rounded ends (`HAND_ENDS`) say nothing of
    its width, and the rings past them are held to the ring beside them. Rings are evened with their
    neighbours, so the glove does not step from one to the next. A vertex moves by the share it follows the
    hand, and is then kept outside the forearm's skin where that runs on into the hand (`outside_forearm`). `report` maps a hand bone to its narrowest share across and its knuckles' height, None where no glove
    follows it."""
    posed = np.array(posed, float)
    names = [bone[0] for bone in BONES]
    rng = np.random.default_rng(0)
    report = {}
    for side in 'lr':
        share = weight[names.index('hand' + side)]
        mine, held = np.flatnonzero(share > 0), share > 0.5
        if held.sum() < GLOVE:
            report['hand' + side] = None
            continue
        wrist = there['wrist' + side]
        axis = seams.unit(there['tip' + side] - wrist)
        forward = seams.unit(np.array([0.0, 1.0, 0.0]) - axis[1] * axis)
        across = np.cross(axis, forward)
        relative = posed[mine] - wrist
        h, w, p = relative @ axis, relative @ forward, relative @ across
        hold = held[mine]
        thumb = hold & (w >= np.percentile(w[hold], 96))
        lean = float(p[thumb].mean() - p[hold].mean())
        length = float(np.percentile(h[hold], 99.5))
        knuckle = KNUCKLES * length
        if abs(lean) >= PALM:  # bent about the knuckles' line, the centre of the bend toward the palm
            palm = math.copysign(1.0, lean)
            radius = (length - knuckle) / CURL
            q = np.minimum(palm * p, 0.9 * radius)
            s = h - knuckle
            angle = np.clip(s / radius, 0.0, CURL)
            beyond = np.maximum(s - radius * CURL, 0.0)
            h, p = (np.where(s > 0, knuckle + (radius - q) * np.sin(angle) + beyond * math.cos(CURL), h),
                    np.where(s > 0, palm * (radius - (radius - q) * np.cos(angle) + beyond * math.sin(CURL)), p))
        hand = np.asarray(parts['hand' + side][0], float), np.asarray(parts['hand' + side][1], int)
        body = surface(hand[0], hand[1], 20000, rng) - wrist
        body_h = body @ axis
        centres = np.arange(h[hold].min(), h[hold].max() + HAND_RING, HAND_RING)
        lookup = np.clip(centres, body_h.min() + HAND_ENDS[0] + HAND_RING / 2, body_h.max() - HAND_ENDS[1] - HAND_RING / 2)
        narrowest, moved = 1.0, []
        for values, body_values, centred in ((w, body @ forward, True), (p, body @ across, False)):
            middle, factor, shift = [], [], []
            for centre, look in zip(centres, lookup):
                ring = hold & (np.abs(h - centre) <= HAND_RING / 2)
                there_ring = np.abs(body_h - look) <= HAND_RING / 2
                if not ring.any() or not there_ring.any():
                    middle.append(np.nan); factor.append(np.nan); shift.append(np.nan)
                    continue
                low, high = values[ring].min(), values[ring].max()
                body_low, body_high = body_values[there_ring].min(), body_values[there_ring].max()
                middle.append((low + high) / 2)
                factor.append(min(1.0, max(NARROWEST, (body_high - body_low + 2 * GLOVE_SKIN) / max(high - low, 1e-6))))
                shift.append((body_low + body_high) / 2 - (low + high) / 2 if centred else 0.0)
            rows = np.array([middle, factor, shift])
            have = ~np.isnan(rows[0])
            rows = np.array([np.interp(centres, centres[have], row[have]) for row in rows])
            for _ in range(2):  # evened with the rings either side
                padded = np.pad(rows, ((0, 0), (1, 1)), mode='edge')
                rows = (padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]) / 3
            middle, factor, shift = (np.interp(h, centres, row) for row in rows)
            moved.append(middle + shift + (values - middle) * factor)
            narrowest = min(narrowest, float(rows[1].min()))
        new = wrist + h[:, None] * axis + moved[0][:, None] * forward + moved[1][:, None] * across
        posed[mine] += share[mine, None] * (new - posed[mine])
        posed[mine] = outside_forearm(posed[mine], wrist, seams.unit(wrist - there['elbow' + side]), parts['fore' + side], rng)
        report['hand' + side] = (round(narrowest, 3), round(knuckle, 3))
    return posed, report


def outside_forearm(points, wrist, axis, fore, rng):
    """`points` of a glove set `GLOVE_SKIN` outside the body's forearm (`fore`, its vertices and faces) where that
    runs on past the wrist into the hand: a forearm left bare is drawn over the glove there, and the glove drawn
    in to the hand lay inside its end, which showed through the cuff in patches (Facility Security, 2026-11-13).
    Compared round the forearm's `axis` past the `wrist`, as the seam contract's wrist plane is, in rings
    `HAND_RING` / 2 tall and `SECTORS` directions, each point against the skin's widest in its own direction and
    the two beside it."""
    skin = surface(np.asarray(fore[0], float), np.asarray(fore[1], int), 20000, rng) - wrist
    along = skin @ axis
    skin, along = skin[along > 0], along[along > 0]
    if not len(skin):
        return points
    u, v = seams.frame(axis)
    step = HAND_RING / 2
    rings = int(math.ceil(along.max() / step))
    cell = lambda h, a: (np.clip(np.floor(h / step).astype(int), 0, rings - 1), np.floor((a + math.pi) / (2 * math.pi) * SECTORS).astype(int) % SECTORS)
    radius = lambda rel, h: rel - h[:, None] * axis
    across = radius(skin, along)
    widest = np.zeros((rings, SECTORS))
    np.maximum.at(widest, cell(along, np.arctan2(across @ v, across @ u)), np.linalg.norm(across, axis=1))
    widest = np.maximum(np.maximum(np.roll(widest, 1, axis=1), widest), np.roll(widest, -1, axis=1))
    relative = np.asarray(points, float) - wrist
    h = relative @ axis
    flat = radius(relative, h)
    r = np.linalg.norm(flat, axis=1)
    inside = (h > 0) & (h < rings * step)
    least = np.zeros(len(points))
    found = widest[cell(h[inside], np.arctan2(flat[inside] @ v, flat[inside] @ u))]
    least[inside] = np.where(found > 0, found + GLOVE_SKIN, 0.0)
    grow = np.where((least > r) & (r > 1e-9), least / np.maximum(r, 1e-9), 1.0)
    return wrist + h[:, None] * axis + flat * grow[:, None]


def apart(vertices, side, legs, there):
    """The vertices with each leg kept on its own side of the middle between the body's hip joints.

    `side[i]` is -1 for a vertex of the outfit's left half and +1 for one of its right, as the outfit came;
    `legs[i]` is the share vertex i follows leg bones. Wide trouser legs fitted round a body's thighs press into
    each other, and each then lies partly past the middle. The cut between the legs cannot part such legs: the
    strip of one leg past the middle is one surface with the other leg over the crotch, and with its own leg
    below where that cut ends. A vertex past the middle, or nearer to it than `LEGS_APART`, moves back across:
    all the way if it follows the legs by half or more, as the inside of a thigh does, which also follows the
    pelvis, and by twice its share below that. The inner sides then lie flat against each other, as cloth does,
    and the torso above the crotch stays where it is."""
    vertices = np.array(vertices, float)
    across = seams.unit(there['hipr'] - there['hipl'])
    short = np.maximum(LEGS_APART - side * ((vertices - there['hips']) @ across), 0.0)
    return vertices + (side * np.minimum(2 * legs, 1.0) * short)[:, None] * across


def grounded(vertices, feet):
    """The vertices with the soles set on the ground: `feet[i]` is the share vertex i follows a foot.

    The lowest vertex that mostly follows a foot comes down (or up) to z = 0, and every vertex with it by its own
    share. A hem or a fingertip may hang lower than the feet; it does not set the ground and is not moved."""
    vertices = np.array(vertices, float)
    soles = np.flatnonzero(feet > 0.5)
    if len(soles):
        lowest = soles[np.argmin(vertices[soles, 2])]
        vertices[:, 2] -= vertices[lowest, 2] * np.minimum(feet / feet[lowest], 1.0)
    return vertices


def onto_body(vertices, faces, bones, parts, clearance=CLEARANCE, materials=None, padded=()):
    """An outfit carried onto a body: its `vertices` in the body's rest pose and fitted round it, with what was found.

    `bones` and `parts` are the body's (`measure.body`). Sleeves that are one surface with the torso are first
    cut out along the arms, in the pose the outfit came in (`split.troughs`), where the armpit is open: `faces`
    are the outfit's with the faces those cuts crossed divided, `origin` the face each came from, `source` the
    vertices given followed by the new ones on those cuts, and `sleeves` what `split.split` takes to part the
    sleeves there. With `materials`, a material per face (`texture.mesh_materials`), a shoulder pad on such an
    arm is parted along its outline too; `padded` names the sides the outfit is designed with one on, and an
    outfit that shows none there is refused. The torso's own vertices on those cuts follow no bone of that arm.
    Each glove is curled and drawn in to the body's hand (`gloved`, reported as `gloves`). Each leg is kept on its
    own side of the middle (`apart`), and the soles are set on the ground by the share each vertex follows a
    foot. Also returned: the outfit's own `joints` and `landmarks`,
    its `scale` to the body (neck height over neck height), the bone `weights`, the `posed` vertices before the
    fit and the fit's `widening` report."""
    vertices, faces = np.asarray(vertices, float), np.asarray(faces, int)
    there = body_joints(bones, parts)
    here, marks = outfit_joints(vertices, faces, there)
    scale = marks['scale']
    arms = {side + bone: here[joint + side] * scale for side in 'lr' for bone, joint in (('bicep_g', 'shoulder'), ('forearm_g', 'elbow'))}
    cut, faces, _, origin, sleeves = split.troughs(vertices * scale, faces, np.zeros((len(vertices), 0)), arms, materials, padded)
    vertices = np.concatenate([vertices, cut[len(vertices):] / scale])
    free = np.ones((len(BONES), len(vertices)), bool)  # the torso's own vertices on a sleeve cut follow no bone of that arm
    for side, found in sleeves.items():
        arm = [index for index, bone in enumerate(BONES) if bone[0] in ('upper' + side, 'fore' + side, 'hand' + side)]
        free[np.ix_(arm, np.flatnonzero(found['torso']))] = False
    posed, weight = repose(vertices, faces, here, there, scale, marks['height'], free)
    fitted, report = fit(posed, weight, there, parts, clearance)
    fitted, gloves = gloved(fitted, weight, there, parts)
    follows = lambda kinds: weight[[index for index, bone in enumerate(BONES) if kind(bone[0]) in kinds]].sum(axis=0)
    fitted = apart(fitted, np.where(vertices[:, 0] < marks['middle'], -1.0, 1.0), follows(('thigh', 'shin', 'foot')), there)
    fitted = grounded(fitted, follows(('foot',)))
    return {'vertices': fitted, 'faces': faces, 'origin': origin, 'source': vertices, 'sleeves': sleeves, 'joints': here, 'landmarks': marks,
            'scale': scale, 'weights': weight, 'posed': posed, 'widening': report, 'gloves': gloves}
