"""Cut one outfit mesh into the rigid armor parts, on the joint planes of the seam contract.

The mesh and the joints are in one space with the bodies' axes: z up, facing +y, left at -x. The neck and waist
planes are level in it and a foot runs forward, so a source in other axes is turned first; `assign` refuses
joints that do not stand that way. Every joint plane cuts the triangles it crosses, but only near the joint,
so that the waist plane does not slice a forearm hanging beside it. The cuts leave the surface in connected
pieces. Each face votes for the part whose side of every plane it is on and whose bone it is nearest, and a
whole piece goes to the part most of its area voted for: a hand resting on a thigh stays a hand. A sleeve that
is one surface with the torso is cut out along the arm as well, in the pose the outfit came in (`troughs`), and
a shoulder pad on it along its own outline, for a shoulder part. At each
joint the under part also gets a rounded cap past the plane, grown from its own rim: turned about the joint,
the cap stays inside the over part and fills the gap that opens (docs/armorkit/plan.md, "Seam rules").
"""
import numpy as np

from tools.robes import mesh_ops

from . import registry, seams
from .registry import require

EPSILON = 1e-7  # a vertex this near a plane counts as on it
REACH = 1.35  # a plane cuts this many joint radii from the joint centre, measured in the plane
CAP_STEPS = 3  # rings a cap is built from: it is seen only in the gap a bend opens, and five cost a worn outfit 8,000 faces
SEAM_RINGS = 1  # rings a rounded seam closing is built from, between its line and its hub
CAP_TOP = 90.0  # degrees of its dome a cap covers: all of it. Short of the pole it has a hole there, which shows once the joint turns far
LEAN = 0.3  # how much more than a dome a cap draws in as it leaves the plane, to clear an over part that narrows there
OWN, CLOSING, CAP = 0, 1, 2  # what made a face of a part: the outfit's own surface, or the split (`split`, `made`)
WELD = 1e-5  # vertices this close are one point when pieces are traced (models repeat vertices at texture seams)
RIVAL = 0.35  # a piece whose second choice won this share of its area is two parts welded together: it is traced again unwelded
FREE_END = 0.12  # how far the bone of a neck, hand or foot runs on past its joint
HIPS_EVEN = 0.01  # the line the two hip planes meet in lies this near the middle between the hip joints, or the body is refused
OVERRUN = 0.03  # two cuts that meet each run this far past the other: a cut stops at whole edges
SLEEVE_STEP = 0.01  # the arm is sectioned this far apart when the armpit is looked for
SLEEVE_FUSED = 1.6  # a section reaching this many times farther toward the torso than away from it is sleeve and torso in one
SLEEVE_ROOM = 0.003  # the sleeve seam stands this far inside the sleeve's inner side at the armpit
SLEEVE_WALL = 0.01  # the walls in front of the arm and behind it stand this far outside the sleeve
SLEEVE_ARMPIT = 0.03  # the sleeve's inner side is taken over this far below the armpit
PAD_RINGS = 3  # rings the chest's closing under a shoulder pad is built from: it is the shoulder that shows when the pad lifts off
PAD_SEED = 0.03  # a shoulder pad is looked for on the faces this near the line from the shoulder joint straight out, away from the torso
PAD_REACH = 0.8  # a shoulder pad lies within this share of the upper arm's length of the shoulder joint: what reaches farther is the sleeve
PAD_ISLAND = 0.25  # a patch of another material in or beside a pad, this share of the pad's area or less and touching nothing else, is the pad's


def token(slot, side):
    """The model token of a slot on a side (`l`, `r`, or `c` for the unpaired slots)."""
    tokens = registry.SLOTS[slot]['tokens']
    return tokens[0] if len(tokens) == 1 else tokens['lr'.index(side)]


def planes(joints):
    """{(joint, side): (point, normal)} for the joints given as {bone name: position}.

    A normal points from the over part into the under part, as in the seam contract."""
    rig = {name: np.array([[1.0, 0, 0, p[0]], [0, 1.0, 0, p[1]], [0, 0, 1.0, p[2]], [0, 0, 0, 1.0]]) for name, p in joints.items()}
    return {(joint, side): seams.plane(rig, joint, side) for joint in seams.JOINTS for side in seams.sides(joint)}


# The joints whose radii give a part its thickness at the start and the end of its bone.
THICKNESS = {'chest': ('waist', None), 'neck': ('neck', 'neck'), 'pelvis': ('waist', None), 'bicep': ('shoulder', 'elbow'),
             'forearm': ('elbow', 'wrist'), 'hand': ('wrist', 'wrist'), 'thigh': ('hip', 'knee'), 'shin': ('knee', 'ankle'),
             'foot': ('ankle', 'ankle')}
BONE_ENDS = {'chest': ('torso_g', 'neck_g'), 'neck': ('neck_g', None), 'pelvis': ('torso_g', None), 'bicep': ('{}bicep_g', '{}forearm_g'),
             'forearm': ('{}forearm_g', '{}hand_g'), 'hand': ('{}hand_g', None), 'thigh': ('{}thigh_g', '{}shin_g'),
             'shin': ('{}shin_g', '{}foot_g'), 'foot': ('{}foot_g', None)}


def limits(radii, reach=REACH, reaches=None):
    """{(joint, side): how far its plane cuts from the joint centre}: `reach` joint radii, or the distance
    `reaches` gives for that joint. An outfit bulkier than its tier at a joint (a shoulder guard, a boot) needs
    the longer reach to be cut through there, while its parts are still told apart by the tier's thickness."""
    reaches = reaches or {}
    require(set(reaches) <= set(radii) and all(value > 0 for value in reaches.values()), 'Reaches are distances above zero, by joint and side')
    return {key: float(reaches.get(key, reach * radius)) for key, radius in radii.items()}


def reaches(vertices, faces, joints, radii, reach=REACH, sleeves=None):
    """{(joint, side): distance} for the joints where an outfit is bulkier than its tier: how far the plane has to
    reach there to cut through the outfit's own section round the joint.

    Other limbs the plane also crosses do not count: only the closed curves of the section that run round the
    joint centre. A hip plane is measured on its own leg's side of the middle (and a little past it, to meet the
    cut between the legs): the two hip planes tilt apart, and where one reached across to the other leg, the
    band between the two planes would belong to neither thigh nor to the pelvis. A shoulder is measured only
    where the arm is a surface of its own: a fused sleeve's section there takes in the whole torso, and its
    seam sets that reach (`sleeve`); `sleeves`, the sleeves cut in the pose the outfit came in (`troughs`), says
    which arms are fused instead of the mesh as it is here. A torso that hangs round the hip joints (a coat, a
    skirt) also counts as a curve round them: such an outfit's hip reaches are not to be used."""
    v, f = np.asarray(vertices, float), np.asarray(faces, int)
    left, right = np.asarray(joints['lthigh_g'], float), np.asarray(joints['rthigh_g'], float)
    middle, across = (left + right) / 2, seams.unit(right - left)
    found = {}
    for (joint, side), (point, normal) in planes(joints).items():
        if joint == 'shoulder' and (side in sleeves if sleeves is not None else sleeve(v, f, joints, side) is not None):
            continue
        own = round_origin(seams.section(v, f, point, normal))
        if joint == 'hip' and len(own):
            ends = own.reshape(-1, 2, 2)  # the curves' segments: taken at points along them, not only at their ends
            own = (ends[:, :1] + np.linspace(0.0, 1.0, 9)[None, :, None] * (ends[:, 1:] - ends[:, :1])).reshape(-1, 2)
            a, b = seams.frame(normal)
            world = point + own[:, :1] * a + own[:, 1:] * b
            own = own[((world - middle) @ across) * (1.0 if side == 'r' else -1.0) >= -OVERRUN]
        if len(own) and 1.05 * np.linalg.norm(own, axis=1).max() > reach * radii[(joint, side)]:
            found[(joint, side)] = 1.05 * float(np.linalg.norm(own, axis=1).max())
    return found


def regions(joints, radii, reach=REACH, reaches=None, whole=()):
    """{token: {bone, radii, planes}}: a part's bone, its thickness at each end and its side of each joint plane.

    `planes` holds (point, normal, sign, limit). A plane only says anything within `limit` of its joint,
    measured in the plane: the shoulder plane runs on through the lower torso, which is still chest. A joint in
    `whole` is not cut: its under part is left out, so that surface goes to a neighbour."""
    joints = {name: np.asarray(position, float) for name, position in joints.items()}
    cuts = planes(joints)
    limit = limits(radii, reach, reaches)
    result = {}
    for slot, (start, end) in BONE_ENDS.items():
        for side in ('lr' if '{}' in start else 'c'):
            a = joints[start.format(side)]
            first, last = (radii[(joint, side)] if joint else None for joint in THICKNESS[slot])
            if end is not None:
                b = joints[end.format(side)]
            elif slot == 'pelvis':  # down to between the hips, as wide there as the hips stand apart
                b = (joints['lthigh_g'] + joints['rthigh_g']) / 2
                last = np.linalg.norm(joints['lthigh_g'] - joints['rthigh_g']) / 2 + radii[('hip', 'l')]
            elif slot == 'neck':
                b = a + np.array((0.0, 0.0, FREE_END))
            elif slot == 'hand':
                b = a + FREE_END * seams.unit(a - joints[side + 'forearm_g'])
            else:  # the foot runs forward and down from the ankle
                b = a + FREE_END * seams.unit((0.0, 0.8, -0.6))
            if slot == 'chest':  # up to the neck, as wide there as the shoulders stand apart
                last = np.linalg.norm(joints['lbicep_g'] - joints['rbicep_g']) / 2
            result[token(slot, side)] = {'bone': (a, b), 'radii': (float(first), float(last)), 'planes': []}
    for (joint, side), (point, normal) in cuts.items():
        spec = seams.JOINTS[joint]
        if (joint, side) in whole:  # not cut: the under part does not exist, and its surface stays on a neighbour
            del result[token(spec['under'], side)]
            continue
        for slot, sign in ((spec['over'], -1.0), (spec['under'], 1.0)):
            if token(slot, side) in result:
                result[token(slot, side)]['planes'].append((point, seams.unit(normal), sign, limit[(joint, side)]))
    return result


def cut(vertices, faces, uvs, point, normal, radius=None, bounds=()):
    """Split the triangles the plane crosses, so that none spans it. Returns (vertices, faces, uvs, origin).

    With `radius`, an edge is split only where it crosses within that distance of `point`, measured in the
    plane; a triangle at that rim is split on one edge only and still spans the plane. The choice is made per
    edge, so the two faces on an edge always agree and no new vertex is left on a whole edge. `bounds` are
    (point, normal) planes the cut stops at: an edge is not split where it crosses past one. New vertices lie
    on the plane and on an old edge, with texture coordinates carried along; `origin[i]` is the face that new
    face i came from. Face order and winding are kept."""
    v, t = np.asarray(vertices, float), np.asarray(uvs, float)
    f = np.asarray(faces, int).reshape(-1, 3)
    n = seams.unit(normal)
    point = np.asarray(point, float)
    d = (v - point) @ n
    d[np.abs(d) < EPSILON] = 0.0
    side = np.sign(d).astype(int)[f]
    crossing = np.flatnonzero((side.max(axis=1) > 0) & (side.min(axis=1) < 0))
    made, new_v, new_t = {}, [], []

    def on_edge(a, b):
        """The new vertex where edge a-b crosses the plane, or None where that is past the radius."""
        key = (a, b) if a < b else (b, a)
        if key not in made:
            a, b = key
            s = d[a] / (d[a] - d[b])
            p = v[a] + s * (v[b] - v[a])
            across = p - point
            if (radius is not None and np.linalg.norm(across - (across @ n) * n) > radius) or any((p - stop) @ facing > 0 for stop, facing in bounds):
                made[key] = None
            else:
                new_v.append(p); new_t.append(t[a] + s * (t[b] - t[a]))
                made[key] = len(v) + len(new_v) - 1
        return made[key]

    out, origin = [], []
    for index in crossing.tolist():
        face, signs = f[index].tolist(), side[index].tolist()
        if 0 in signs:  # one vertex on the plane, the other two on opposite sides
            k = signs.index(0); a, b, c = face[k:] + face[:k]
            p = on_edge(b, c)
            new = [face] if p is None else [[a, b, p], [a, p, c]]
        else:  # one vertex alone on its side
            k = next(i for i in range(3) if signs[i] != signs[(i + 1) % 3] and signs[i] != signs[(i + 2) % 3])
            a, b, c = face[k:] + face[:k]
            ab, ca = on_edge(a, b), on_edge(c, a)
            if ab is None and ca is None:
                new = [face]
            elif ca is None:
                new = [[a, ab, c], [ab, b, c]]
            elif ab is None:
                new = [[a, b, ca], [b, c, ca]]
            else:
                new = [[a, ab, ca], [ab, b, c], [ab, c, ca]]
        out.extend(new); origin.extend([index] * len(new))
    whole = np.setdiff1d(np.arange(len(f)), crossing)
    f = np.concatenate([f[whole], np.array(out, int).reshape(-1, 3)])
    origin = np.concatenate([whole, np.array(origin, int)])
    order = np.argsort(origin, kind='stable')
    if new_v:
        v, t = np.concatenate([v, new_v]), np.concatenate([t, new_t])
    return v, f[order], t, origin[order]


def outside(points, bone, radii):
    """How far each point is outside a part's nominal surface: its distance to the bone less the thickness there."""
    a, b = bone
    ab = b - a
    s = np.clip(((points - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(points - (a + s[:, None] * ab), axis=1) - (radii[0] + s * (radii[1] - radii[0]))


def classify(centres, parts):
    """The index into `parts` (a `regions` result, in order) each point belongs to.

    A point belongs to the part whose nominal surface it is nearest to (or deepest inside), among the parts
    whose side it is on of every joint plane that reaches it; where there is no such part, among all."""
    centres = np.asarray(centres, float)
    distance = np.stack([outside(centres, part['bone'], part['radii']) for part in parts.values()], axis=1)
    allowed = np.ones(distance.shape, bool)
    for column, part in enumerate(parts.values()):
        for point, normal, sign, limit in part['planes']:
            relative = centres - point
            height = relative @ normal
            within = np.linalg.norm(relative - height[:, None] * normal, axis=1) <= limit
            allowed[:, column] &= ~within | (sign * height >= -EPSILON)
    constrained = np.where(allowed, distance, np.inf)
    return np.where(allowed.any(axis=1), constrained.argmin(axis=1), distance.argmin(axis=1))


def on_cut(vertices, point, normal, radius, bounds=()):
    """Which vertices lie on a cut: on its plane, within `radius` of its point measured in the plane, and not
    past any of `bounds`, the (point, normal) planes the cut stops at."""
    relative = vertices - point
    height = relative @ normal
    on = (np.abs(height) < WELD) & (np.linalg.norm(relative - height[:, None] * normal, axis=1) <= radius)
    for stop, facing in bounds:
        on &= (vertices - stop) @ facing <= WELD
    return on


def pieces(vertices, faces, cuts, welded=True):
    """A piece number per face: faces joined edge to edge, never across a cut.

    `cuts` holds (point, normal, limit) or (point, normal, limit, bounds), as `on_cut` takes them, or for a cut
    made in another pose (`troughs`) the vertices that lie on it, one flag each. An edge lying on a cut separates. With `welded`, vertices at one position are one point; without, only faces that share
    vertex numbers join."""
    weld = mesh_ops.weld_ids(vertices, WELD) if welded else np.arange(len(vertices))
    on = np.stack([found if isinstance(found, np.ndarray) else on_cut(vertices, *found) for found in cuts], axis=1)
    start, end = faces, np.roll(faces, -1, axis=1)  # edge i of a face runs from its corner i to the next
    joins = ~(on[start] & on[end]).any(axis=2)
    edge = np.sort(np.stack([weld[start], weld[end]], axis=2), axis=2)[joins]
    face = np.broadcast_to(np.arange(len(faces))[:, None], faces.shape)[joins]
    order = np.lexsort((edge[:, 1], edge[:, 0]))
    edge, face = edge[order], face[order]
    same = (edge[1:] == edge[:-1]).all(axis=1)  # neighbours in the sorted list that are one edge
    return mesh_ops.union_find(len(faces), zip(face[:-1][same].tolist(), face[1:][same].tolist()))


def owners(vertices, faces, parts, cuts):
    """The index into `parts` each face goes to: its piece's choice by area.

    A piece with one clear choice goes to it whole, however much of it lies past a plane that only grazes it.
    Two limbs that touch at a few coinciding vertices trace as one piece that votes for both about equally;
    such a piece is traced again without welding, which takes the two shells apart, and each votes alone. A
    piece that still votes for two parts then, and holds most of what votes for its second choice anywhere, is
    one surface no cut parts (two trouser legs pressed through each other below the cut between them): it is
    refused, since its first choice would get both parts. The few faces of a weld itself go where they vote."""
    vote = classify(vertices[faces].mean(axis=1), parts)
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    weight = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    names = list(parts)

    def choose(piece):
        _, piece = np.unique(piece, return_inverse=True)
        tally = np.zeros((piece.max() + 1, len(parts)))
        np.add.at(tally, (piece, vote), weight)
        total = tally.sum(axis=1)
        order = np.argsort(tally, axis=1)
        second = np.take_along_axis(tally, order[:, -2:-1], axis=1)[:, 0]
        return order[:, -1], (total > 0) & (second >= RIVAL * total), second, order[:, -2], tally.sum(axis=0), piece

    first, torn, _, _, _, piece = choose(pieces(vertices, faces, cuts))
    owner, torn = first[piece], torn[piece]
    if torn.any():
        first, still, second, rival, all_votes, piece = choose(pieces(vertices, faces, cuts, welded=False))
        for label in np.flatnonzero(still & (second >= all_votes[rival] / 2)):
            require(not torn[piece == label].any(), f'The {names[first[label]]} and the {names[rival[label]]} are one surface that no cut parts')
        owner = np.where(torn, first[piece], owner)
    return owner


def curves(segments):
    """(curve, ids) for a section's segments, (n, 2, 2): the number of the curve each segment belongs to and the
    numbers of its two end points. Segments that share an end point are one curve."""
    _, ids = np.unique(np.round(np.asarray(segments, float).reshape(-1, 2) / WELD).astype(np.int64), axis=0, return_inverse=True)
    ids = ids.reshape(-1, 2)
    return mesh_ops.union_find(int(ids.max()) + 1, ids.tolist())[ids[:, 0]], ids


def round_origin(segments):
    """The points of the section's closed curves that run round the plane's point, as (n, 2), the two ends of
    each segment in turn; empty where no curve does. A curve left open by the mesh's own edge is not counted:
    it has no inside."""
    segments = np.asarray(segments, float).reshape(-1, 2, 2)
    if not len(segments):
        return np.zeros((0, 2))
    curve, ids = curves(segments)
    found = []
    for label in np.unique(curve):
        mine = segments[curve == label]
        ends, uses = np.unique(ids[curve == label], return_counts=True)
        loose = mine.reshape(-1, 2)[np.isin(ids[curve == label].reshape(-1), ends[uses % 2 == 1])]
        # an end counts as closed when another end lies on it: one point can round to two neighbouring cells
        if len(loose) and np.any(np.sort(np.linalg.norm(loose[:, None] - loose[None], axis=2), axis=1)[:, 1] > 10 * WELD):
            continue
        y0, y1 = mine[:, 0, 1], mine[:, 1, 1]
        crosses = (y0 > 0) != (y1 > 0)  # a ray from the point along the first axis: an odd count means inside
        x = mine[:, 0, 0] - y0 / np.where(crosses, y1 - y0, 1.0) * (mine[:, 1, 0] - mine[:, 0, 0])
        if np.count_nonzero(crosses & (x > 0)) % 2:
            found.append(mine.reshape(-1, 2))
    return np.concatenate(found) if found else np.zeros((0, 2))


def sleeve(vertices, faces, joints, side, padded=False):
    """Where a sleeve is cut from the torso it is fused with, or None where the arm is a surface of its own.

    The sleeve and the torso of a generated outfit are one surface from the shoulder down to the armpit. That
    is below the shoulder plane, which therefore cannot part them. The sleeve is cut out by three more planes
    along the arm, a trough the arm lies in.

    The seam faces the torso, where a shirt's sleeve is sewn on. It stands just inside the sleeve's inner side
    as that is right under the armpit, and it runs down to the elbow, so that it also cuts a stray bridge from
    the upper arm to the flank. Standing where the sleeve is widest instead (an elbow guard), the seam lies
    inside the flank at the armpit, and the slab of the torso's side it cuts off goes with the arm.

    The two walls stand in front of the arm and behind it, across the seam, just outside the arm's outer half
    as it is from the shoulder plane to right under the armpit. Whatever the torso wears beside the arm there
    (a vest's side panel, a pouch behind the arm) is one surface with the sleeve too, and the walls leave it
    on the torso; the seam alone gives it to the arm, where it rides along when the arm lifts. The seam runs
    from wall to wall and each wall from the arm's outer side to the seam, each a little past where they meet:
    a cut stops at whole edges, and a triangle left spanning one plane at its rim would join the two sides
    again. A sleeve wider farther down than the trough is cut by these planes there; both sides of that cut are
    the sleeve's, so nothing opens. With `padded`, a shoulder pad covers the arm's outer half above the armpit
    and is cut out by itself (`pad`): the walls are then measured right under the armpit alone, where the arm is
    no wider than its sleeve, and what the torso wears beside the pad stays on the torso.

    Returns the seam's `point`, `normal`, `radius` and `bounds`, its `walls` (each with the same four), the
    `depth` of the armpit below the shoulder plane, and the `reach` the shoulder plane needs to cut across the
    trough."""
    start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
    other = np.asarray(joints[('r' if side == 'l' else 'l') + 'bicep_g'], float)
    length = float(np.linalg.norm(end - start))
    axis = seams.unit(end - start)
    inward = other - start
    inward = seams.unit(inward - (inward @ axis) * axis)
    u, v = seams.frame(axis)
    toward, along = np.array([inward @ u, inward @ v]), np.array([-(inward @ v), inward @ u])
    across = along[0] * u + along[1] * v  # the walls' normal: `along`, in space
    fused, clear, under, armpit = [], [], [], None
    for depth in np.arange(0.0, length, SLEEVE_STEP):
        points = round_origin(seams.section(vertices, faces, start + depth * axis, axis))
        if not len(points):
            break  # the arm has ended
        if (points @ toward).max() > SLEEVE_FUSED * -(points @ toward).min():
            if armpit is None:
                fused.append(points)
        else:
            if not fused:
                return None  # the arm is its own surface at the shoulder plane
            armpit = depth if armpit is None else armpit
            if depth <= armpit + SLEEVE_ARMPIT:
                under.append(points)
            clear.append(points)
    if not fused:
        return None
    require(clear, f'The {side} sleeve is one surface with the torso down to the elbow')
    seam = float(max((points @ toward).max() for points in under)) + SLEEVE_ROOM
    # the sleeve's width front to back, taken on its outer half: what the torso wears can lie on the inner one
    wide = np.concatenate([points[points @ toward <= 0] for points in (under if padded else under + fused)]) @ along
    back, front = float(wide.min()) - SLEEVE_WALL, float(wide.max()) + SLEEVE_WALL
    inside = lambda points: points[(points @ toward <= seam) & (points @ along >= back) & (points @ along <= front)]
    outer = float(min((inside(points) @ toward).min() for points in fused + clear)) - 3 * SLEEVE_STEP
    middle = start + length / 2 * axis
    stop = [(start + seam * inward + OVERRUN * inward, inward)]  # the walls end a little past the seam
    wall = lambda where, sign: {'point': middle + (seam + outer) / 2 * inward + where * across, 'normal': sign * across, 'bounds': stop,
                                'radius': float(np.hypot(length / 2 + 3 * SLEEVE_STEP, (seam - outer) / 2 + OVERRUN))}
    return {'point': middle + seam * inward + (front + back) / 2 * across, 'normal': inward, 'depth': float(armpit),
            'radius': float(np.hypot(length / 2 + 3 * SLEEVE_STEP, (front - back) / 2 + OVERRUN)),
            'bounds': [(start + (front + OVERRUN) * across, across), (start + (back - OVERRUN) * across, -across)],
            'walls': [wall(front, 1.0), wall(back, -1.0)],
            'reach': float(np.linalg.norm(inside(fused[0]), axis=1).max()) + 3 * SLEEVE_STEP}


def seam_fill(vertices, uvs, faces, base, seam, facing, rim=None, rings=SEAM_RINGS):
    """Faces that close a part's opening on a cut off the joint planes (a sleeve seam, the cut between the legs):
    (vertices, uvs, faces) to add, numbered from `base`. `seam` holds the cut's `point`, `normal` and `radius`,
    and may hold the `bounds` it stops at and the `walls` that cut the part beside it (`sleeve`). A cut made in
    another pose (`troughs`) holds `on` instead, per plane the vertices that lie on it, with the planes'
    `normals` as they stand here and the `normal` its closing is rounded along.

    The part's edges on the cut and on its walls, each on one face only, run from the joint plane down round
    the armpit or the crotch and back up, from one plane onto the next where the opening turns a corner. Each
    such line is closed from the middle between its two ends, which lies on the joint plane: the part's rim
    there is then a closed curve again, which its cap grows from. The closing's faces follow each other along
    the line, all wound one way, and as a whole it faces along the normals of the planes its edges lie on with
    `facing` +1 and against them with -1; a wall's normal points away from the arm. One face alone cannot be
    asked: where the opening turns a corner, a face from the middle to a wall may stand square to that wall.

    Every vertex of a closing has the texture coordinates of the point of the line it lies inward from, as a
    cap's have those of its rim, and the middle is one vertex per point of the line: a closing is then drawn
    in what the part shows along its edge. Coordinates blended across the opening would be read from inside
    the outfit, where a baked colour is whatever surface happens to be nearest.

    Without `rim` the closing is a flat fan. With `rim`, the joint's centre and the unit normal of its plane,
    it is rounded out the way it faces on the cut itself, in `rings` rings, toward
    the ball about the joint centre that the line's two ends lie on: the part's rim on the joint plane is then
    closed by an arc of that ball and not by a straight line, so a sleeve is round at the shoulder when the arm
    lifts off the chest. The closing nowhere leaves the ball, so however the joint turns it stays where the
    part's own rim already reaches; past the ball, down toward the armpit or the crotch, it is flat. The
    rounding leans into the joint plane, so the rim stays on it. A line that does not end twice on that plane
    (the hole or the stub a stray bridge left) is closed flat."""
    if 'on' in seam:  # flags for the vertices the cut left; those added since lie on none of its planes
        planes, normals = [np.concatenate([flags, np.zeros(len(vertices) - len(flags), bool)]) for flags in seam['on']], seam['normals']
    else:
        found = (seam, *seam.get('walls', ()))
        planes = [on_cut(vertices, plane['point'], plane['normal'], plane['radius'], plane.get('bounds', ())) for plane in found]
        normals = [plane['normal'] for plane in found]
    on = np.any(planes, axis=0)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    lies = np.stack([plane[edges].all(axis=1) for plane in planes])  # [plane, edge]: both ends on that plane
    edges, lies = edges[lies.any(axis=0)], lies.argmax(axis=0)[lies.any(axis=0)]
    # The line is traced by position, as `pieces` traces: a vertex repeated at a texture seam is one point of it.
    # The new faces keep the vertex numbers the part's own faces use there, and so their texture coordinates.
    spot = np.full(len(vertices), -1, int)
    spot[on] = mesh_ops.weld_ids(vertices[on], WELD)
    edges, lies = edges[spot[edges[:, 0]] != spot[edges[:, 1]]], lies[spot[edges[:, 0]] != spot[edges[:, 1]]]
    if len(edges):
        _, inverse, count = np.unique(np.sort(spot[edges], axis=1), axis=0, return_inverse=True, return_counts=True)
        edges, lies = edges[count[inverse.reshape(-1)] == 1], lies[count[inverse.reshape(-1)] == 1]
    new_v, new_t, new_f = [], [], []
    if len(edges):
        line = mesh_ops.union_find(int(spot.max()) + 1, spot[edges].tolist())[spot[edges[:, 0]]]
        for label in np.unique(line):
            mine = edges[line == label]
            spots, first, uses = np.unique(spot[mine], return_index=True, return_counts=True)
            where = vertices[mine.reshape(-1)[first]]  # one position per point of the line
            ends = where[uses == 1]
            centre = ends.mean(axis=0) if len(ends) == 2 else where.mean(axis=0)
            out, ball = np.zeros(3), 0.0
            if rim is not None and len(ends) == 2 and np.abs((ends - rim[0]) @ rim[1]).max() < WELD:
                out = facing * (seam['normal'] - (seam['normal'] @ rim[1]) * rim[1])
                if np.linalg.norm(out) > 1e-6:
                    out, ball = out / np.linalg.norm(out), float(np.linalg.norm(ends - rim[0], axis=1).mean())

            def rounded(flat, share):
                """`flat`, a point of the flat closing, carried out toward the ball about the joint."""
                away = flat - rim[0]
                along = float(away @ out)
                lift = -along + np.sqrt(max(ball * ball - float(away @ away) + along * along, 0.0))
                return flat + max(lift, 0.0) * np.sqrt(1 - share * share) * out
            middle = rounded(centre, 0.0) if ball else centre
            column = {}  # per vertex of the line, its vertices on the way in to the middle and at it, outermost first
            for vertex in np.unique(mine).tolist():
                column[vertex] = []
                for ring in range(rings if ball else 0, -1, -1):
                    share = ring / (rings + 1)  # of the way from the middle out to the line
                    column[vertex].append(base + len(new_v))
                    new_v.append(rounded(centre + share * (vertices[vertex] - centre), share) if ring else middle)
                    new_t.append(uvs[vertex])
            # the line's edges in the order they follow each other from one end, each turned to run that way
            faced = lambda p, q, plane: facing * float(np.cross(vertices[p] - centre, vertices[q] - centre) @ normals[plane])
            sides, at = lies[line == label].tolist(), {}
            for number, (a, b) in enumerate(mine.tolist()):
                at.setdefault(int(spot[a]), []).append(number); at.setdefault(int(spot[b]), []).append(number)
            here, left, run = int(spots[np.argmin(uses)]), set(range(len(mine))), []
            while True:
                number = next((number for number in at[here] if number in left), None)
                if number is None:
                    break
                left.discard(number)
                a, b = mine[number].tolist()
                run.append((a, b, sides[number]) if int(spot[a]) == here else (b, a, sides[number]))
                here = int(spot[run[-1][1]])
            if sum(faced(*edge) for edge in run) < 0:
                run = [(q, p, plane) for p, q, plane in run]
            for number in sorted(left):  # a line that branches: what the walk did not reach is faced edge by edge
                a, b = mine[number].tolist()
                run.append((a, b, sides[number]) if faced(a, b, sides[number]) > 0 else (b, a, sides[number]))
            for p, q, _ in run:
                inner_p, inner_q = [p] + column[p], [q] + column[q]
                for step in range(len(inner_p) - 2):
                    new_f.append((inner_p[step + 1], inner_p[step], inner_q[step]))
                    new_f.append((inner_p[step + 1], inner_q[step], inner_q[step + 1]))
                new_f.append((inner_p[-1], inner_p[-2], inner_q[-2]))
    return np.array(new_v).reshape(-1, 3), np.array(new_t).reshape(-1, uvs.shape[1]), np.array(new_f, int).reshape(-1, 3)


####
def beside(vertices, faces):
    """Pairs of faces that share an edge, vertices at one position being one point."""
    weld = mesh_ops.weld_ids(vertices, WELD)[faces]
    edge = np.sort(np.stack([weld, np.roll(weld, -1, axis=1)], axis=2), axis=2).reshape(-1, 2)
    face = np.repeat(np.arange(len(faces)), 3)
    order = np.lexsort((edge[:, 1], edge[:, 0]))
    edge, face = edge[order], face[order]
    same = (edge[1:] == edge[:-1]).all(axis=1)
    return np.stack([face[:-1][same], face[1:][same]], axis=1)


def pad(vertices, faces, materials, joints, side):
    """The faces of the shoulder pad on one arm, one flag per face, or None where the shoulder shows none.

    `materials` holds a material per face, as the outfit's colours show it (`texture.mesh_materials`). A pad is
    one patch of one material over the shoulder joint: the patch the outermost face belongs to that lies on the
    line from the joint straight out, away from the torso. It ends where the material does, which is the pad's
    own outline, and it lies within `PAD_REACH` of the upper arm's length of the joint; a patch that reaches
    farther is the sleeve itself, or a jacket of one material, and no pad. A small patch of another material
    that touches the pad and nothing else (a face read wrongly, a rivet) is the pad's too."""
    v, f, materials = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(materials)
    require(materials.shape == (len(f),), 'One material per face is required')
    start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
    other = np.asarray(joints[('r' if side == 'l' else 'l') + 'bicep_g'], float)
    length, axis = float(np.linalg.norm(end - start)), seams.unit(end - start)
    inward = other - start
    inward = seams.unit(inward - (inward @ axis) * axis)
    centre = v[f].mean(axis=1) - start
    near = (np.abs(centre @ axis) < PAD_SEED) & (np.abs(centre @ np.cross(axis, inward)) < PAD_SEED) & (centre @ inward < 0)
    if not near.any():
        return None
    seed = np.flatnonzero(near)[np.argmin((centre @ inward)[near])]
    pairs = beside(v, f)
    patch = np.asarray(mesh_ops.union_find(len(f), pairs[materials[pairs[:, 0]] == materials[pairs[:, 1]]].tolist()))
    found = patch == patch[seed]
    if np.linalg.norm(centre[found], axis=1).max() > PAD_REACH * length:
        return None
    area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    _, rest = np.unique(mesh_ops.union_find(len(f), pairs[~found[pairs].any(axis=1)].tolist()), return_inverse=True)
    touching = np.unique(rest[pairs[found[pairs].sum(axis=1) == 1][~found[pairs[found[pairs].sum(axis=1) == 1]]]])
    sizes = np.bincount(rest, weights=np.where(found, 0.0, area))
    islands = [number for number in touching.tolist() if sizes[number] <= PAD_ISLAND * area[found].sum()]
    return found | (np.isin(rest, islands) & ~found)


def troughs(vertices, faces, uvs, joints, materials=None):
    """The mesh with its fused sleeves cut out along the arms, in the pose it is given in: (vertices, faces, uvs,
    origin, sleeves).

    An outfit comes with its arms held out, and is bent onto a body's rest pose before `split` cuts it on the
    joint planes. A sleeve's trough (`sleeve`) is found and cut here, before the bend: the armpit is open, the
    arm stands clear of whatever the torso wears beside it, and the seam and the walls are measured on the arm
    alone. At rest the sleeve lies against the torso's side again, pressed into it by the fit, and a trough
    placed there cuts the torso's flank as well. The bend carries the cut along as vertices of the surface.

    With `materials`, a material per face, a shoulder pad on such an arm is found too (`pad`) and parted from
    the rest along its own outline, the edges where its material ends: `split` gives it to a shoulder part,
    which rides on the arm. Cut out by planes wide enough to hold it instead, the pad took what the torso wears
    round it along, and the torso ended a hand's width short of its own shoulder.

    `joints` holds the shoulder and elbow joints as `lbicep_g`, `lforearm_g` and so on, in the mesh's space and in
    metres. `origin[i]` is the face that new face i was cut from. `sleeves` maps a side with a fused sleeve to
    `on`, four rows of flags for the vertices on the seam, on each wall and on the pad's outline, `inside`, per
    face, whether it lies in the trough, from a little above the shoulder joint down to the elbow, and `pad`,
    per face, whether it is the pad's; `assign` takes it with the bent mesh.

    Along the trough's cuts the torso gets vertices of its own, at the same places: `torso` flags them. The
    bend can then keep the torso's edge of an armhole where the torso is, while the sleeve's edge goes with
    the arm; as one vertex, the edge went part of the way, and drew the torso's surface and its closing out
    with the arm. A pad's outline stays one edge through the bend: at rest the torso then ends exactly where
    the pad lies on it, and its closing shows only when the arm moves the pad away. The vertices given come
    first, then those the cuts made, then the torso's own."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    origin, found = np.arange(len(f)), {}
    pads = {side: None if materials is None else pad(v, f, materials, joints, side) for side in 'lr'}
    for side in 'lr':
        seam = sleeve(v, f, joints, side, padded=pads[side] is not None)
        if seam is not None:
            found[side] = [seam, *seam['walls']]
            for plane in found[side]:
                v, f, t, o = cut(v, f, t, plane['point'], plane['normal'], plane['radius'], plane['bounds'])
                origin = origin[o]
    sleeves, centre, weld, below = {}, v[f].mean(axis=1), mesh_ops.weld_ids(v, WELD), {}
    for side, planes in found.items():
        start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
        along = (centre - start) @ seams.unit(end - start)
        inside = (along >= -3 * SLEEVE_STEP) & (along <= np.linalg.norm(end - start))  # as far up as the planes reach
        for plane in planes:
            inside &= (centre - plane['point']) @ plane['normal'] < 0
        mine = np.zeros(len(f), bool) if pads[side] is None else pads[side][origin]
        used = np.zeros((2, int(weld.max()) + 1), bool)
        used[0, weld[f[mine]]], used[1, weld[f[~mine]]] = True, True
        sleeves[side] = {'on': np.stack([on_cut(v, plane['point'], plane['normal'], plane['radius'], plane['bounds']) for plane in planes]
                                        + [used.all(axis=0)[weld]]),
                         'inside': inside, 'pad': mine}
        below[side] = along >= 0
    if sleeves:
        # An arm is its pad and what the cuts leave joined to its trough from the shoulder joint down: the
        # sleeve, and past the elbow the forearm and the hand. The torso is the largest piece the cuts leave,
        # less the arms. A slice the seam cut off a sleeve wider than its trough (an elbow guard) is neither,
        # and keeps the sleeve's vertices.
        rows = [flags for found in sleeves.values() for flags in found['on']]
        for side, found in sleeves.items():
            down = np.flatnonzero(below[side])
            joined = np.asarray(pieces(v, f[down], rows))
            below[side] = found['pad'].copy()
            below[side][down[np.isin(joined, np.unique(joined[found['inside'][down]]))]] = True
        _, piece = np.unique(pieces(v, f, rows), return_inverse=True)
        area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
        torso = (piece == np.argmax(np.bincount(piece, weights=area))) & ~np.any(list(below.values()), axis=0)
        f, own = f.copy(), {}
        for side, found in sleeves.items():
            shared = np.zeros((2, len(v)), bool)
            shared[0, f[below[side]]], shared[1, f[torso]] = True, True
            twice = np.flatnonzero(shared.all(axis=0) & found['on'][:3].any(axis=0))  # on the trough: a pad's outline stays one edge
            remap = np.arange(len(v)); remap[twice] = len(v) + np.arange(len(twice))
            f[torso] = remap[f[torso]]
            own[side] = len(v) + np.arange(len(twice))
            v, t = np.concatenate([v, v[twice]]), np.concatenate([t, t[twice]])
            for other in sleeves.values():
                other['on'] = np.concatenate([other['on'], other['on'][:, twice]], axis=1)
        for side, found in sleeves.items():
            found['torso'] = np.zeros(len(v), bool); found['torso'][own[side]] = True
    return v, f, t, origin, sleeves


def compact(vertices, faces, uvs):
    """(vertices, faces, uvs) holding only the vertices the faces use."""
    used = np.unique(faces)
    remap = np.full(len(vertices), -1, int); remap[used] = np.arange(len(used))
    return vertices[used], remap[faces], uvs[used]


def cap(vertices, uvs, faces, base, point, normal, depth, limit, steps=CAP_STEPS, lean=LEAN):
    """A rounded end past the joint plane for an under part: (vertices, uvs, faces) to add to it.

    `faces` are the part's faces. Its rim is the edges it has on the plane within `limit`, each on one face
    only, that face on the under side. Every rim point is carried past the plane on a dome about the joint
    centre, in `steps` rings, the last of them the dome's pole, where the cap closes in one fan; the new
    vertices are numbered from `base`. The dome is `depth` deep, but at no
    rim point deeper than that point is far from the centre: every cap point then stays within its rim
    point's distance of the centre however the joint turns, so the cap does not leave an over part as wide
    as the rim, and it shows in the gap that opens on the other side of the bend (seams.minimum_overlap).
    `lean` draws the cap in a little more than a dome from the start, because the over part often narrows
    just past the plane."""
    relative = vertices - point
    height = relative @ normal
    flat = relative - height[:, None] * normal
    on = (np.abs(height) < WELD) & (np.linalg.norm(flat, axis=1) <= limit)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    under = np.tile(height[faces].sum(axis=1) > 0, 3)
    keep = on[edges].all(axis=1)
    edges, under = edges[keep], under[keep]
    if len(edges):
        _, inverse, count = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
        edges = edges[(count[inverse.reshape(-1)] == 1) & under]
    if not len(edges):
        return np.zeros((0, 3)), np.zeros((0, uvs.shape[1])), np.zeros((0, 3), int)
    rim = np.unique(edges)
    slot = np.full(len(vertices), -1, int); slot[rim] = np.arange(len(rim))
    angles = np.radians(CAP_TOP * np.arange(1, steps + 1) / steps)
    deep = np.minimum(depth, np.linalg.norm(flat[rim], axis=1))[:, None]
    rings = [point + flat[rim] * (np.cos(a) * (1.0 - lean * np.sin(a))) - normal * (deep * np.sin(a)) for a in angles]
    # the pole: one point, held once per rim point so each keeps its texture coordinates, and no deeper than the
    # nearest rim point is far from the centre
    rings[-1] = np.tile(point - normal * deep.min(), (len(rim), 1))
    index = np.concatenate([rim[None], base + np.arange(steps * len(rim)).reshape(steps, len(rim))])  # [ring, rim point]
    a, b = slot[edges[:, 0]], slot[edges[:, 1]]  # the part's face runs a to b, so the cap's runs b to a
    near, far = index[:-1], index[1:]
    # two faces per rim edge between rings, one at the pole, where the second would have no area
    added = np.concatenate([np.stack([near[:, b], near[:, a], far[:, a]], axis=2).reshape(-1, 3),
                            np.stack([near[:-1, b], far[:-1, a], far[:-1, b]], axis=2).reshape(-1, 3)])
    return np.concatenate(rings), np.tile(uvs[rim], (steps, 1)), added


def assign(vertices, faces, uvs, joints, radii, reach=REACH, reaches=None, whole=(), sleeves=None):
    """The mesh cut on every plane, and the part each face goes to.

    `sleeves` is what `troughs` found on this mesh in the pose it came in, the vertices and faces unchanged
    since but for where they stand: the sleeves are then parted along those cuts. Without it a fused sleeve's
    trough is found and cut on the mesh as it stands here. A shoulder pad `troughs` found goes whole to that
    side's shoulder part, whichever side of the shoulder plane its faces lie on: it then rides on the arm, as
    the shoulder slot's bone does.

    Returns (vertices, faces, uvs, owner, names, origin, cuts, sleeves, between, limit): `owner[i]` indexes
    `names`, `origin[i]` is the face of the mesh given that face i was cut from, `cuts` maps (joint, side) to
    its plane, `sleeves` maps a side to the sleeve seam cut there (`sleeve`; for one cut in another pose, the
    flags of the vertices on its planes as `on`, with the `normal` toward the torso and the planes' `normals`), `between` is the cut
    between the legs (`point`, `normal`, `radius`) and `limit` maps (joint, side) to how far its plane cut."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    require(len(v) == len(t), 'One texture coordinate per vertex is required')
    require(len(f), 'The mesh has no faces')
    cuts = planes(joints)
    require(set(radii) == set(cuts), 'A radius is required for every joint and side')
    whole = set(whole)
    require(whole <= {key for key in cuts if key[0] in ('neck', 'wrist', 'ankle')}, 'Only a neck, a wrist or an ankle can be left uncut')
    left, right = np.asarray(joints['lthigh_g'], float), np.asarray(joints['rthigh_g'], float)
    up = seams.unit(np.asarray(joints['neck_g'], float) - np.asarray(joints['torso_g'], float))
    require(up[2] > 0.8 and seams.unit(np.cross(up, right - left))[1] > 0.8, 'The joints must stand z up and face +y, as the bodies do')
    # A sleeve fused with the torso is cut off along the arm as well; the shoulder plane then reaches only as far
    # as the sleeve's own side of that seam, unless the caller says how far.
    carried = sleeves
    if carried is None:
        sleeves = {side: found for side, found in ((side, sleeve(v, f, joints, side)) for side in 'lr') if found is not None}
    else:
        # Cut in the pose the outfit came in. The shoulder plane reaches as far as the trough's faces cross it
        # here; the flags ride through the cuts below beside the texture coordinates: a new vertex on an edge
        # between two vertices of a cut lies on that cut.
        require(set(carried) <= {'l', 'r'} and all(np.shape(found['on']) == (4, len(v)) and np.shape(found['inside']) == (len(f),)
                                                    and np.shape(found.get('pad', found['inside'])) == (len(f),) for found in carried.values()),
                'Sleeves cut in another pose come with flags for this mesh: four per vertex and one per face')
        sleeves = {}
        for side, found in carried.items():
            start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
            axis, inward = seams.unit(end - start), np.asarray(joints[('r' if side == 'l' else 'l') + 'bicep_g'], float) - start
            point, normal = cuts[('shoulder', side)]
            # a pad goes whole to its shoulder part: the plane has to reach across the sleeve beside it, or across
            # the pad where the pad lies all round the arm there
            mine = np.asarray(found['inside'], bool)
            bare = mine & ~np.asarray(found.get('pad', np.zeros(len(f), bool)), bool)
            rim = seams.section(v, f[bare], point, seams.unit(normal)).reshape(-1, 2)
            if not len(rim):
                rim = seams.section(v, f[mine], point, seams.unit(normal)).reshape(-1, 2)
            require(len(rim), f'The shoulder plane does not cross the {side} sleeve as it was cut')
            inward = seams.unit(inward - (inward @ axis) * axis)
            sleeves[side] = {'normal': inward, 'normals': [inward, np.cross(axis, inward), -np.cross(axis, inward), inward],
                             'reach': float(np.linalg.norm(rim, axis=1).max()) + 3 * SLEEVE_STEP}
        t = np.concatenate([t] + [np.asarray(found['on'], float).T for found in carried.values()], axis=1)
    reaches = {**{('shoulder', side): found['reach'] for side, found in sleeves.items()}, **(reaches or {})}
    limit = limits(radii, reach, reaches)
    origin = np.arange(len(f))
    for key, (point, normal) in cuts.items():
        if key in whole:
            continue
        v, f, t, o = cut(v, f, t, point, normal, limit[key])
        origin = origin[o]
    # Trousers join the legs at the crotch, below both hip planes: without a cut between the legs there, the
    # two thighs would be one piece. The cut runs between the hip joints, as far as the hip planes reach.
    # It holds the line the two hip planes meet in: a thigh's edge on it then ends on that thigh's own hip plane,
    # where its closing and its cap start. Between the joints' middle alone, the two planes can miss each other
    # there by a fraction of a millimetre, and a cap is left open by that much. Hip joints so uneven that the
    # line lies off the middle are refused: the cut would no longer run between the legs.
    middle, across = (left + right) / 2, seams.unit(right - left)
    (point_l, normal_l), (point_r, normal_r) = ((np.asarray(point, float), seams.unit(normal)) for point, normal in (cuts[('hip', 'l')], cuts[('hip', 'r')]))
    line = np.cross(normal_l, normal_r)
    if np.linalg.norm(line) > 1e-6:
        line = seams.unit(line)
        middle = np.linalg.solve(np.stack([normal_l, normal_r, line]), [normal_l @ point_l, normal_r @ point_r, line @ middle])
        across = seams.unit(across - (across @ line) * line)
    require(np.linalg.norm(middle - (left + right) / 2) < HIPS_EVEN and abs((middle - point_r) @ normal_r) < WELD,
            'The two hip planes do not meet midway between the hip joints')
    between = {'point': middle, 'normal': across, 'radius': max(limit[('hip', 'l')], limit[('hip', 'r')])}
    here = [] if carried is not None else [plane for seam in sleeves.values() for plane in (seam, *seam['walls'])]
    walls = [(found['point'], found['normal'], found['radius'], found.get('bounds', ())) for found in (between, *here)]
    for wall in walls:
        v, f, t, o = cut(v, f, t, *wall)
        origin = origin[o]
    if carried:
        flags, t = t[:, -4 * len(carried):] > 1 - 1e-9, t[:, :-4 * len(carried)]
        for index, side in enumerate(carried):
            sleeves[side]['on'] = [flags[:, 4 * index + plane] for plane in range(4)]
            walls += sleeves[side]['on']
    parts = regions(joints, radii, reach, reaches, whole)
    owner = owners(v, f, parts, [(point, seams.unit(normal), limit[key]) for key, (point, normal) in cuts.items() if key not in whole] + walls)
    names = list(parts)
    for side, found in (carried or {}).items():
        mine = np.asarray(found.get('pad', np.zeros(len(origin), bool)), bool)[origin]
        if mine.any():
            owner = np.where(mine, len(names), owner)
            names.append(token('shoulder', side))
    return v, f, t, owner, names, origin, cuts, sleeves, between, limit


def split(vertices, faces, uvs, joints, radii, overlaps=None, reach=REACH, reaches=None, whole=(), made=None, sleeves=None):
    """{token: (vertices, faces, uvs)} for one outfit mesh.

    `joints` maps bone names to positions in the mesh's space. `radii` maps (joint, side) to the radius of the
    joint there (the largest of the body ring plus the part's tier room); a plane cuts within `reach` times
    it, or within the distance `reaches` gives for that joint and side. `overlaps` maps (joint, side) to how
    deep the under part's cap runs past the plane under the over part; a joint without one gets no cap. Where a
    part was cut from a neighbour off the joint planes (a sleeve along the arm, the thighs between the legs),
    its opening on that cut is closed, a sleeve's rounded out toward the chest. A joint in `whole` (a neck, wrist or ankle, by joint and side) is not
    cut: its under part is left out and that surface stays on the part beside it, as a collar stays on the
    chest of an outfit that has no neck part of its own. Parts with no faces are left out.
    `made`, if a dict is given, is filled with what made each face of each part, in the order of its faces:
    `OWN` for the outfit's own surface, `CLOSING` and `CAP` for what the split added. `sleeves` is what `troughs`
    found on this mesh in the pose it came in. A shoulder pad found with them is a shoulder part (`assign`),
    closed underneath across its own outline. The outfit has no surface under a pad: the chest is closed where
    the pad lay on it, rounded out from the shoulder plane as the shoulder under the pad, and the upper arm is
    closed flat under it, where the pad always covers it."""
    overlaps = overlaps or {}
    require(all(key[0] in seams.JOINTS and key[1] in seams.sides(key[0]) for key in overlaps)
            and all((depth or 0) >= 0 for depth in overlaps.values()), 'Overlaps are depths of zero or more, by joint and side')
    v, f, t, owner, names, _, cuts, sleeves, between, limit = assign(vertices, faces, uvs, joints, radii, reach, reaches, whole, sleeves)
    # The cuts off the joint planes, each with the parts it leaves open and the way their closing faces: a
    # sleeve seam opens the sleeve and the chest, and where it cut a stray bridge near the elbow, the forearm and
    # the pelvis; the cut between the legs opens the two thighs toward each other wherever trousers joined them
    # below the hip planes.
    # A sleeve is rounded out toward the chest from its rim on the shoulder plane: lifted, it is round where it
    # left the torso. The other closings stay flat: the torso's own, those of a stray bridge, and the thighs',
    # which lie against each other, where a rounded one comes out through the other leg at the crotch.
    rim = lambda joint, side: (np.asarray(cuts[(joint, side)][0], float), seams.unit(cuts[(joint, side)][1]))
    closings = []
    for side, found in sleeves.items():
        trough, outline = found, None
        if 'on' in found:  # cut in the pose the outfit came in: the trough's three planes, and the pad's outline
            trough = {**found, 'on': found['on'][:3], 'normals': found['normals'][:3]}
            outline = {**found, 'on': found['on'][3:], 'normals': found['normals'][3:]}
        closings.append((trough, {token('bicep', side): (1.0, rim('shoulder', side)), token('forearm', side): (1.0, None),
                                  'chest': (-1.0, None), 'pelvis': (-1.0, None)}))
        if outline is not None:
            closings.append((outline, {token('shoulder', side): (1.0, None), token('bicep', side): (1.0, None),
                                       'chest': (-1.0, rim('shoulder', side), PAD_RINGS)}))
    closings.append((between, {token('thigh', 'l'): (1.0, None), token('thigh', 'r'): (-1.0, None)}))
    result = {}
    for index, name in enumerate(names):
        mine = f[owner == index]
        if not len(mine):
            continue
        pv, pf, pt, closed, kinds = v, mine, t, np.zeros((0, 3)), [np.full(len(mine), OWN)]
        for seam, facing in closings:  # closed first: an under part's cap then grows from a closed rim
            if name in facing:
                more = seam_fill(pv, pt, pf, len(pv), seam, *facing[name])
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                closed = np.concatenate([closed, more[0]])
                kinds.append(np.full(len(more[2]), CLOSING))
        for (joint, side), depth in overlaps.items():
            if depth and (joint, side) not in whole and token(seams.JOINTS[joint]['under'], side) == name:
                point, normal = cuts[(joint, side)]
                # a rounded closing carries the part's rim on the plane out past the plane's own reach
                away = closed - point
                away = away - (away @ seams.unit(normal))[:, None] * seams.unit(normal)
                reach_here = max([limit[(joint, side)]] + (np.linalg.norm(away, axis=1) + WELD).tolist())
                more = cap(pv, pt, pf, len(pv), point, seams.unit(normal), depth, reach_here)
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                kinds.append(np.full(len(more[2]), CAP))
        result[name] = compact(pv, pf, pt)
        if made is not None:
            made[name] = np.concatenate(kinds)
    return result
