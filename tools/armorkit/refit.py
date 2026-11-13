"""Baked parts carried from one body to another, each by a rotation and a uniform scale where those serve, their
ends then brought to the other body's seam contract.

A part keeps its shape: each is turned, scaled and moved as one (`placement`), so that the parts of a design
made on the Human male go on the Human female without being generated again, plates round and pockets square.
The user asked for rotation and uniform scaling, used again for every refit where they serve (2026-11-13).

* A part between two or more joints is placed by the planes of those joints (`seams.plane`), the points the
  seam contract measures ends from: an upper arm, a thigh or a shin by its two, the pelvis by the waist and
  both hips. Its axis runs from its first joint to the middle of the others (`axis_of`) and is turned the
  shortest way onto the other body's; along it the part is scaled as the joints lie apart (`along`), across
  it as the body's own outline at those joints is wide (`across`, the contract's body rings).
* Where those two scales agree within `UNIFORM` the part is scaled by one, the two's geometric mean. Where they
  do not, it is scaled by each along and across its axis, which still bends nothing: the Human female's limbs
  are 0.95 to 1.0 the male's length and her body 0.70 to 0.79 as wide at the joints, and a thigh scaled to her
  leg's length kept the male's girth and stood out through the sides of a pelvis scaled to her hips (Facility
  Security, 2026-11-13).
* A part with one joint, a hand, a foot or the neck, turns as the part across that joint does, so a boot stays
  flat where the shin turns two degrees, and is scaled the same every way by how large the body's own part
  there is (`size`): a Human female foot is 0.85 the size of the male's and her hand 0.86, where the middle of
  her foot, which stands on its toes, lies farther from her ankle than his.
* The ends at the tube joints are then drawn in or spread out to the other body's envelopes as a bake shapes
  them (`ends.shaped`), a smooth slope with no shelf over the last `ends.LONGEST` at most, and the seam gate
  on the other body decides each part. The cap a bake grew past an under end's plane is scaled about the
  joint's axis as that end's ring was (`capped`): where the end was drawn in, shaping left the cap as wide as
  the scales made it, and a glove's cap stood at the Human female's forearm skin as a band above the cuff
  (2026-11-13). A thigh's end at the hip, a dome grown on the body's seat, is no tube
  and is left as the scales leave it: shaped as one, its dome flared into a lip that stood out through the
  pelvis (2026-11-13).

A part holding the body's own skin (`bodyskin.worn`) is not carried: that skin is the other body's, and the
part is baked on it.
"""
from pathlib import Path

import numpy as np

from . import bodyskin, ends, registry, repose, seams
from .registry import require

UNIFORM = 0.05  # a part is scaled the same every way where its scales along and across its axis differ by this share or less


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


def across(token, contract, source, target):
    """How much wider the body `target` is than the body `source` at the joints part `token` meets: the mean
    of the ratios of the contract's body rings there, each its mean radius."""
    ring = lambda joint, side, body: np.mean(contract['joints'][joint]['bodies'][body]['sides'][side]['bodyRing'])
    return float(np.mean([ring(joint, side, target) / ring(joint, side, source) for joint, side, _ in joints_of(token)]))


def size(vertices, faces):
    """How large a surface is: the root mean square distance of its area from its middle."""
    corners = np.asarray(vertices, float)[np.asarray(faces, int)]
    area = 0.5 * np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    middle = (corners.mean(axis=1) * area[:, None]).sum(axis=0) / area.sum()
    spread = (((corners - middle) ** 2).sum(axis=2).mean(axis=1) * area).sum() / area.sum()
    return float(np.sqrt(spread))


def stretched(rotation, axis, along, round_):
    """The linear map that turns by `rotation` after scaling by `along` along unit `axis` and `round_` across it."""
    return rotation @ (round_ * np.eye(3) + (along - round_) * np.outer(axis, axis))


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
        round_ = along if contract is None else across(token, contract, *names)
        if abs(along / round_ - 1) <= UNIFORM:
            along = round_ = float(np.sqrt(along * round_))
        linear = stretched(rotation, unit, along, round_)
        return linear, goal.mean(axis=0) - linear @ start.mean(axis=0), {'along': round(along, 4), 'across': round(round_, 4)}
    (_, _, other), = met
    require(len(joints_of(other)) > 1, f'{token} and {other} each meet one joint: nothing turns them')
    start, goal = anchors(other, source[0]), anchors(other, target[0])
    rotation = repose.turn(*(seams.unit(axis_of(points)) for points in (start, goal)))
    require(token in source[1] and token in target[1], f'Both bodies have a {token} to scale a part by')
    scale = size(*target[1][token][:2]) / size(*source[1][token][:2])
    joint, aim = anchors(token, source[0])[0], anchors(token, target[0])[0]
    return scale * rotation, aim - scale * rotation @ joint, {'along': round(scale, 4), 'across': round(scale, 4)}


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


def refit(parts, source, target, names=None, contract=None, bodies=None, tier=2, bare=()):
    """(parts, report): baked parts (`bake.stored`) carried from the body `source` to the body `target`, each a
    (rig, parts by token) pair as `measure.body` gives them. `names` limits the parts carried; the rest are
    left out. Each part's vertices and normals are carried by its `placement`; with `contract` and `bodies`,
    the two bodies' names, its scale across follows the contract's body rings and its ends at the tube joints
    are brought to tier `tier`'s envelopes on the target (`ends.shaped`; a pad's
    faces, `pad`, are no part of a ring), skin-tight at the joints `bare` names (`ends.ends_of`). Nothing else
    about a part changes. `report` maps a part to its turn in degrees and its scales along and across."""
    names = list(parts) if names is None else list(names)
    require(set(names) <= set(parts), f'No such part to refit: {", ".join(sorted(set(names) - set(parts)))}')
    held = [name for name in names if set(bodyskin.KEYS) & set(parts[name])]
    require(not held, f'{", ".join(held)} hold the body\'s own skin: bake them on the other body instead')
    out, report = {}, {}
    for name in names:
        linear, offset, scales = placement(name, source, target, contract, bodies)
        part = dict(parts[name])
        v, f = np.asarray(part['v'], float) @ linear.T + offset, np.asarray(part['f'], int)
        n = np.asarray(part['n'], float) @ np.linalg.inv(linear)  # normals carried by the inverse transpose
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        if contract is not None:
            part_ends = ends.ends_of(name, target[0], contract, bodies[1], tier, bare=bare)
            if part_ends:
                measured = ~np.asarray(part.get('pad', np.zeros(len(f), bool)), bool)
                shaped = capped(v, ends.shaped(v, f, measured, part_ends), f, measured, part_ends)
                n = n + ends.normals(shaped, f) - ends.normals(v, f)
                n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
                v = shaped
        part['v'], part['n'] = v, n
        out[name] = part
        turn = linear / np.cbrt(np.linalg.det(linear))
        u, _, vt = np.linalg.svd(turn)
        report[name] = {'degrees': round(float(np.degrees(np.arccos(np.clip((np.trace(u @ vt) - 1) / 2, -1.0, 1.0)))), 2), **scales}
    return out, report


def run(kept, output, body_pack, source, target, names=None, tier=2):
    """Refit the parts kept in the folder `kept` (`bake.store`) from body `source` to body `target`, both read
    from `body_pack`, their ends shaped to the target's seam contract at tier `tier`, and keep them in the
    folder `output` with the slots the brief they were baked from left to the body and shared with its skin,
    for `bake --kept OUTPUT --body TARGET` to tint, write and gate on the other body. Returns `refit`'s report."""
    from . import bake, measure
    require(Path(output).resolve() != Path(kept).resolve(), 'Refit parts are kept in another folder than the parts they came from')
    listed = bake.listing(kept)
    left = [token for slot in listed['bare'] for token in registry.SLOTS[slot]['tokens']]
    parts, report = refit(bake.stored(kept), measure.body(body_pack, source), measure.body(body_pack, target), names,
                          seams.load_contract(), (source, target), tier, bake.bare_joints({'left': left}))
    bake.store(parts, output, {key: value for key, value in listed.items() if key != 'parts'})
    return report
