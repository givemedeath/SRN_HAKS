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


def token_of(slot, letter):
    """The model token of `slot` on side `letter`."""
    tokens = registry.SLOTS[slot]['tokens']
    return tokens[0] if len(tokens) == 1 else tokens['lr'.index(letter)]


def joints_of(token):
    """[(joint, side, other token)] for each joint part `token` meets, with the part across that joint."""
    found = []
    for joint, spec in seams.JOINTS.items():
        for side in seams.sides(joint):
            letter = 'l' if side == 'c' else side
            named = {key: token_of(spec[key], letter) for key in ('under', 'over')}
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


def across(token, contract, source, target, ways, bones=None):
    """How much wider the body `target` is than the body `source` at the joints part `token` meets in each of
    the directions `ways` (unit vectors square to the part's axis): the ratio of the contract's body rings
    there, each ring's radii weighed by how near their directions lie to that way, and its mean over the
    joints. `bones`, the source body's rig, places a ring's directions (`seams.frame` of its plane); without
    it a ring is weighed the same every way, the ratio of its mean radii."""
    found = []
    for joint, side, _ in joints_of(token):
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


def placement(token, source, target, contract=None, names=None):
    """(linear map, offset, report) carrying part `token` from body `source` to body `target`, each a (rig,
    parts by token) pair as `measure.body` gives them, as `map @ p + offset`. `contract` and `names`, the two
    bodies' names, give the scale across a part with two or more joints; without them it is the scale along
    (module notes)."""
    met = joints_of(token)
    require(met, f'{token} meets no joint')
    if len(met) > 1:
        start, goal = anchors(token, source[0]), anchors(token, target[0])
        run, aim = axis_of(start), axis_of(goal)
        require(np.linalg.norm(run) > 1e-9, f'The joints of {token} are one point')
        unit = run / np.linalg.norm(run)
        rotation, along = repose.turn(unit, aim / np.linalg.norm(aim)), float(np.linalg.norm(aim) / np.linalg.norm(run))
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


def seated(part, point, normal, over, gap=split.SEAT_GAP, others=()):
    """`part`'s vertices with the cap the bake grew past its under end's plane (`point`, unit `normal` toward
    the part) brought into the other body's part over the joint, `over` (vertices, faces of its outfit's own
    surface): drawn toward the plane until it runs no deeper than that part stands over the joint less `gap`
    (`split.room`, as a bake seats an end), then each of its points held `gap` inside it (`under_skin`). The
    cap is what only the split's faces (`added`) use, its points matched by position across the part's
    texture seams, nearer this joint's point than the part's other joints' (`others`): a pelvis's domes at the
    hips are no part of its end at the waist. The male's upper arm ran 10 cm into his chest, and on the Human
    female's own chest stood 4 to 5 cm out of it (Facility Security, 2026-11-13)."""
    v, f = np.asarray(part['v'], float), np.asarray(part['f'], int)
    added = np.asarray(part['added'], bool) & ~np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
    if 'skin' in part:
        added &= ~np.asarray(part['skin'], bool)
    weld = mesh_ops.weld_ids(v)
    cap = np.isin(weld, weld[f[added].ravel()]) & ~np.isin(weld, weld[f[~added].ravel()])
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
    there held inside the target body's own part across the joint (`under_skin`). A part holding the source
    body's skin is carried without it (`bodyskin.unworn`). Nothing else about a part changes. `report` maps a
    part to its turn in degrees and its scales along and across."""
    names = list(parts) if names is None else list(names)
    require(set(names) <= set(parts), f'No such part to refit: {", ".join(sorted(set(names) - set(parts)))}')
    out, report = {}, {}
    for name in names:
        linear, offset, scales = placement(name, source, target, contract, bodies)
        part = dict(bodyskin.unworn(parts[name]))
        v, f = np.asarray(part['v'], float) @ linear.T + offset, np.asarray(part['f'], int)
        n = np.asarray(part['n'], float) @ np.linalg.inv(linear)  # normals carried by the inverse transpose
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        if contract is not None:
            part_ends = ends.ends_of(name, target[0], contract, bodies[1], tier, bare=bare)
            if part_ends:
                measured = ~np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
                shaped = capped(v, ends.shaped(v, f, measured, part_ends), f, measured, part_ends)
                for joint, side in bare:  # under the body's own skin: its part across the joint on the other body
                    letter = 'l' if side == 'c' else side
                    over = token_of(seams.JOINTS[joint]['over'], letter)
                    if token_of(seams.JOINTS[joint]['under'], letter) == name and over in target[1]:
                        point, normal = seams.plane(target[0], joint, letter)
                        shaped = under_skin(shaped, np.asarray(point, float), seams.unit(normal), target[1][over][:2])
                n = n + ends.normals(shaped, f) - ends.normals(v, f)
                n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
                v = shaped
        part['v'], part['n'] = v, n
        part, dropped = whole(part)
        out[name] = part
        turn = linear / np.cbrt(np.linalg.det(linear))
        u, _, vt = np.linalg.svd(turn)
        report[name] = {'degrees': round(float(np.degrees(np.arccos(np.clip((np.trace(u @ vt) - 1) / 2, -1.0, 1.0)))), 2), **scales,
                        **({'dropped': dropped} if dropped else {})}
    return out, report


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
    Returns `refit`'s report."""
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
            if token_of(seams.JOINTS[joint]['under'], letter) == name and over in beside and over not in parts:
                moved = seated(parts[name], points[k], seams.unit(seams.plane(goal[0], joint, letter)[1]), bake._outfit(beside[over])[:2],
                               others=np.delete(points, k, axis=0))
                if not np.array_equal(moved, parts[name]['v']):
                    parts[name] = {**parts[name], 'v': moved}
                    report[name].setdefault('seated', []).append(f'{joint} {side}')
    if bake.shared_with_body(listed) & set(parts):
        require(body_textures is not None, f'{", ".join(sorted(bake.shared_with_body(listed) & set(parts)))} share their slots with the body\'s '
                                           'skin: give the body\'s textures to lay the other body\'s beside them')
        parts = bake.skinned(parts, listed, body_pack, body_textures, target, goal[0])
    bake.store(parts, output, {key: value for key, value in listed.items() if key != 'parts'})
    return report
