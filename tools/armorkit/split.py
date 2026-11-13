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
OWN, CLOSING, CAP, GUSSET, WALL, PADDED = 0, 1, 2, 3, 4, 5  # what made a face of a part: the outfit's own surface, or the split (`split`, `made`)
WELD = 1e-5  # vertices this close are one point when pieces are traced (models repeat vertices at texture seams)
POINT = 1e-6  # metres: two corners of a triangle this near are one point, and the model compiler drops the triangle
RIVAL = 0.35  # a piece whose second choice won this share of its area is two parts welded together: it is traced again unwelded
FREE_END = 0.12  # how far the bone of a neck, hand or foot runs on past its joint
HIPS_EVEN = 0.01  # the line the two hip planes meet in lies this near the middle between the hip joints, or the body is refused
OVERRUN = 0.03  # two cuts that meet each run this far past the other: a cut stops at whole edges
SLEEVE_STEP = 0.01  # the arm is sectioned this far apart when the armpit is looked for
SLEEVE_ABOVE = 0.10  # a trough cut with the arms held out reaches this far above the shoulder joint, along the arm. The
# shoulder plane closes the trough at its top and stands where the body's joint is, while the trough is placed by the
# outfit's own shoulder, which is estimated. Three steps above it, the wall behind one outfit's arm ended 2 cm under the
# plane: the strip between joined sleeve and torso, and the whole upper sleeve went to the chest. That outfit needs 0.075
SLEEVE_PARTED = 0.5  # at least this share of a trough's faces, by area, goes with the arm, or the sleeve was not parted
SLEEVE_FUSED = 1.6  # a section reaching this many times farther toward the torso than away from it is sleeve and torso in one
SLEEVE_ROOM = 0.003  # the sleeve seam stands this far inside the sleeve's inner side at the armpit
SLEEVE_WALL = 0.01  # the walls in front of the arm and behind it stand this far outside the sleeve
SLEEVE_ARMPIT = 0.03  # the sleeve's inner side is taken over this far below the armpit
GUSSET_WIDTH = 0.05  # the pelvis repeats the surface this near the cut between the legs: a thigh turned out 20 degrees opens the crotch 3.5 cm
GUSSET_BELOW = 0.0  # and what lies this far below the lowest point of the cut: farther, the strip is the insides of two trouser legs
GUSSET_CORNER = 1.0  # its lower corners are cut off this share of its half width, to a point: square, it hangs between parted legs as a flap
GUSSET_UNDER = 0.004  # and holds it this far under the thighs' own, which cover it as the body stands
HIP_TUCK = 0.1  # a thigh's cap starts this share of its rim's width inside the rim: turned out as the game stands a body, a cap as wide as its rim came through the pelvis along the hip line
SHOULDER_TUCK = 0.2  # an upper arm's cap starts this share inside its rim: beside a shoulder pad the rim is two arcs, and a cap as wide came through the chest in front of the pad and behind it
TUCKS = {'hip': HIP_TUCK, 'shoulder': SHOULDER_TUCK}  # by joint: how far inside its rim the under part's cap starts
TUCK_STEPS = 4  # a tucked cap is built from this many rings, the first of them the step in
TUCK_RISE = 0.06  # the ring a tucked cap steps in on stands this share of the cap's depth past the plane
PAD_RINGS = 3  # rings the chest's closing under a shoulder pad is built from: it is the shoulder that shows when the pad lifts off
PAD_SEED = 0.03  # a shoulder pad is looked for on the faces this near the line from the shoulder joint straight out, away from the torso
PAD_REACH = 0.8  # a shoulder pad lies within this share of the upper arm's length of the shoulder joint: what reaches farther is the sleeve
GUARD_REACH = 0.5  # a knee or elbow pad reaches up the limb no more than this share of the bone above its joint: what reaches farther is a sleeve or a trouser leg
GUARD_LEAST = 0.003  # square metres a pad is at least
GUARD_STEPS = 5  # rings the cap under a knee or elbow pad is built from: four across the gap a bend opens, and the pole
GUARD_SWEEP = 110.0  # degrees about the joint's hinge the pad's rim is carried through: a seat bends a knee 90
GUARD_TUCK = 0.05  # and how much nearer the hinge it is drawn on the way, to stay under the pad's own surface
GUARDS = {'knee': ('thigh_g', 'shin_g', 'foot_g'), 'elbow': ('bicep_g', 'forearm_g', 'hand_g')}  # a joint that may carry a pad: the joints above it, at it and below
PAD_ISLAND = 0.25  # a patch of another material in or beside a pad, this share of the pad's area or less and touching nothing else, is the pad's
SEAT_STEPS = 3  # rings a thigh's end runs in from its rim on the seat line to the hip plane, the last on the plane
SEAT_DOME = 3  # rings of its dome past the plane, the last the pole
SEAT_GAP = 0.004  # the end stands this far inside the pelvis's own surface
SEAT_SAMPLE = 0.004  # the pelvis's surface is read at points this far apart
SEAT_BINS, SEAT_ROW = 64, 0.01  # and per 64th of a turn round the thigh and per centimetre along it
SEAT_ROUND = 0.75  # a piece of the rim is the thigh's opening when it comes round this share of the turn: a pocket's edge does not
SEAT_HALVINGS = 8  # how finely the end is drawn in to stay inside the pelvis as the thigh turns
ARM_OPENING = 0.5  # an upper arm's opening at the shoulder lies within this share of the way to the elbow
ARM_FLOOR = 0.02  # an upper arm is cut no nearer its shoulder plane than this: its end needs the room to come in to the envelope


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


def cut(vertices, faces, uvs, point, normal, radius=None, bounds=(), height=None):
    """Split the triangles the plane crosses, so that none spans it. Returns (vertices, faces, uvs, origin).

    With `radius`, an edge is split only where it crosses within that distance of `point`, measured in the
    plane; a triangle at that rim is split on one edge only and still spans the plane. The choice is made per
    edge, so the two faces on an edge always agree and no new vertex is left on a whole edge. `bounds` are
    (point, normal) planes the cut stops at: an edge is not split where it crosses past one. New vertices lie
    on the plane and on an old edge, with texture coordinates carried along; `origin[i]` is the face that new
    face i came from. Face order and winding are kept. `height`, a value per vertex, is cut where it changes
    sign instead of the plane, each edge where its value runs straight through zero (`seated`); the plane,
    `radius` and `bounds` are then not used."""
    v, t = np.asarray(vertices, float), np.asarray(uvs, float)
    f = np.asarray(faces, int).reshape(-1, 3)
    if height is None:
        n = seams.unit(normal)
        point = np.asarray(point, float)
        d = (v - point) @ n
    else:
        require(radius is None and not bounds and np.shape(height) == (len(v),), 'A cut along values has one value per vertex and no radius or bounds')
        d = np.array(height, float)
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
            across = None if radius is None else p - point
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


def sleeve(vertices, faces, joints, side, padded=False, above=3 * SLEEVE_STEP):
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
    again. Along the arm the three planes run from `above` over the shoulder joint to a little past the
    elbow. The shoulder plane closes the trough at its top, so they have to reach it: three steps do where the
    trough is found on the body's own joints, and `troughs`, which finds it on an outfit's estimated ones with
    the arms held out, asks for `SLEEVE_ABOVE`. A sleeve wider farther down than the trough is cut by these planes there; both sides of that cut are
    the sleeve's, so nothing opens. With `padded`, a shoulder pad covers the arm's outer half above the armpit
    and is cut out by itself (`pad`): the walls are then measured right under the armpit alone, where the arm is
    no wider than its sleeve, and what the torso wears beside the pad stays on the torso.

    Returns the seam's `point`, `normal`, `radius` and `bounds`, its `walls` (each with the same four), the
    `depth` of the armpit below the shoulder plane, and the `reach` the shoulder plane needs to cut across the
    trough.

    The first sections may have no curve round the arm's line: an outfit's shoulder joint is an estimate, and
    that of an arm bare below a short sleeve lay 2 cm outside the shoulder's surface. They are passed over,
    for a quarter of the upper arm at most; taken for the arm's end, they left the sleeve on the torso."""
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
            if fused or depth > length / 4:
                break  # the arm has ended
            continue  # the joint lies just outside the outfit's shoulder: no curve runs round the arm's line yet
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
    # the planes run from above the shoulder joint to three steps past the elbow
    half = (length + 3 * SLEEVE_STEP + above) / 2
    middle = start + (half - above) * axis
    past = (end + 3 * SLEEVE_STEP * axis, axis)  # no plane cuts the forearm farther down for reaching higher up
    stop = [(start + seam * inward + OVERRUN * inward, inward), past]  # the walls end a little past the seam
    wall = lambda where, sign: {'point': middle + (seam + outer) / 2 * inward + where * across, 'normal': sign * across, 'bounds': stop,
                                'radius': float(np.hypot(half, (seam - outer) / 2 + OVERRUN))}
    return {'point': middle + seam * inward + (front + back) / 2 * across, 'normal': inward, 'depth': float(armpit),
            'radius': float(np.hypot(half, (front - back) / 2 + OVERRUN)),
            'bounds': [(start + (front + OVERRUN) * across, across), (start + (back - OVERRUN) * across, -across), past],
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
    return patch(v, f, materials, seed, lambda found: np.linalg.norm(centre[found], axis=1).max() <= PAD_REACH * length)


def patch(v, f, materials, seed, fits):
    """The patch of one material that face `seed` is in, one flag per face, with the small patches of other
    materials that touch it and nothing else; None unless `fits` says of the patch's flags that it is a pad."""
    pairs = beside(v, f)
    label = np.asarray(mesh_ops.union_find(len(f), pairs[materials[pairs[:, 0]] == materials[pairs[:, 1]]].tolist()))
    found = label == label[seed]
    if not fits(found):
        return None
    area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    _, rest = np.unique(mesh_ops.union_find(len(f), pairs[~found[pairs].any(axis=1)].tolist()), return_inverse=True)
    touching = np.unique(rest[pairs[found[pairs].sum(axis=1) == 1][~found[pairs[found[pairs].sum(axis=1) == 1]]]])
    sizes = np.bincount(rest, weights=np.where(found, 0.0, area))
    islands = [number for number in touching.tolist() if sizes[number] <= PAD_ISLAND * area[found].sum()]
    return found | (np.isin(rest, islands) & ~found)


def guard(vertices, faces, materials, joints, joint, side):
    """The faces of the pad over one knee or elbow, one flag per face, or None where the joint shows none.

    A pad is one patch of one material over the joint, as a shoulder pad is over the shoulder (`pad`): the
    patch the outermost face belongs to that lies on the line from the joint straight forward at a knee, and
    straight back or, failing that, straight out from the body at an elbow. Up the limb it reaches no more
    than `GUARD_REACH` of the bone above the joint; a sleeve or a trouser leg reaches farther. Down the limb
    it may run on as a guard along the shin or the forearm: on one outfit the left elbow pad was one patch
    with its forearm guard and the right one was not. A patch of less than `GUARD_LEAST` is a strap's end or
    a face read wrongly, and no pad. `split` rounds the under part's cap out as a ball under such a pad
    (`guards`)."""
    v, f, materials = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(materials)
    require(materials.shape == (len(f),), 'One material per face is required')
    require(joint in GUARDS and side in ('l', 'r'), f'A pad is told over one of {sorted(GUARDS)}, on the l or r side')
    above, at, below = (np.asarray(joints[side + name], float) for name in GUARDS[joint])
    axis = seams.unit(below - above)
    ways = [(0.0, 1.0, 0.0)] if joint == 'knee' else [(0.0, -1.0, 0.0), at - np.asarray(joints[('r' if side == 'l' else 'l') + GUARDS[joint][1]], float)]
    centre = v[f].mean(axis=1) - at
    area = 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
    fits = lambda found: (centre[found] @ axis).min() >= -GUARD_REACH * np.linalg.norm(at - above) and area[found].sum() >= GUARD_LEAST
    for way in ways:
        way = np.asarray(way, float)
        way = seams.unit(way - (way @ axis) * axis)
        near = (np.abs(centre @ axis) < PAD_SEED) & (np.abs(centre @ np.cross(axis, way)) < PAD_SEED) & (centre @ way > 0)
        if near.any():
            seed = np.flatnonzero(near)[np.argmax((centre @ way)[near])]
            found = patch(v, f, materials, seed, fits)
            if found is not None:
                return found
    return None


def troughs(vertices, faces, uvs, joints, materials=None, padded=()):
    """The mesh with its fused sleeves cut out along the arms, in the pose it is given in: (vertices, faces, uvs,
    origin, sleeves).

    An outfit comes with its arms held out, and is bent onto a body's rest pose before `split` cuts it on the
    joint planes. A sleeve's trough (`sleeve`) is found and cut here, before the bend: the armpit is open, the
    arm stands clear of whatever the torso wears beside it, and the seam and the walls are measured on the arm
    alone. At rest the sleeve lies against the torso's side again, pressed into it by the fit, and a trough
    placed there cuts the torso's flank as well. The bend carries the cut along as vertices of the surface.

    With `materials`, a material per face, a shoulder pad on an arm `padded` names is found too (`pad`) and parted from
    the rest along its own outline, the edges where its material ends: `split` gives what of it lies past the
    shoulder plane to a shoulder part, which rides on the arm, and what lies before it, over the top of the
    shoulder, to the chest (`topped`). Cut out by planes wide enough to hold it instead, the pad took what the torso wears
    round it along, and the torso ended a hand's width short of its own shoulder. `padded` names the sides the
    outfit is designed with a shoulder pad on: one that shows none there is refused. A pad of the sleeve's own
    material cannot be told from the sleeve, and would be cut in two on the shoulder plane without a word, its
    upper half left on the chest when the arm lifts. On a side `padded` does not name no pad is looked for:
    Facility Security's short right sleeve, a patch of cloth within a pad's reach of the shoulder, was taken
    for one, went whole to a shoulder part, and left nothing of the sleeve to go with the arm (2026-11-13).
    Shoulder pads are made apart from the outfit now, and the brief says which sides have one.

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
    require(set(padded) <= {'l', 'r'} and (materials is not None or not padded), 'Pads are expected on the l or r side, and told by materials')
    require(materials is None or np.shape(materials) == (len(f),), 'One material per face is required')
    pads = {side: pad(v, f, materials, joints, side) if side in padded else None for side in 'lr'}
    for side in 'lr':
        seam = sleeve(v, f, joints, side, padded=pads[side] is not None, above=SLEEVE_ABOVE)
        require(side not in padded or (seam is not None and pads[side] is not None),
                f'The {side} shoulder shows no pad: a pad is a patch of a material of its own, on a sleeve that is one surface with the torso')
        if seam is not None:
            found[side] = [seam, *seam['walls']]
            for plane in found[side]:
                v, f, t, o = cut(v, f, t, plane['point'], plane['normal'], plane['radius'], plane['bounds'])
                origin = origin[o]
    sleeves, centre, weld, below = {}, v[f].mean(axis=1), mesh_ops.weld_ids(v, WELD), {}
    for side, planes in found.items():
        start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
        along = (centre - start) @ seams.unit(end - start)
        inside = (along >= -SLEEVE_ABOVE) & (along <= np.linalg.norm(end - start))  # as far up as the planes reach
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


def cap(vertices, uvs, faces, base, point, normal, depth, limit, steps=CAP_STEPS, lean=LEAN, full=None, hinge=None, grown=None, tuck=0.0,
        bounded=True):
    """A rounded end past the joint plane for an under part: (vertices, uvs, faces) to add to it.

    `faces` are the part's faces. Its rim is the edges it has on the plane within `limit`, each on one face
    only, that face on the under side. Every rim point is carried past the plane on a dome about the joint
    centre, in `steps` rings, the last of them the dome's pole, where the cap closes in one fan; the new
    vertices are numbered from `base`. The dome is `depth` deep, but at no
    rim point deeper than that point is far from the centre: every cap point then stays within its rim
    point's distance of the centre however the joint turns, so the cap does not leave an over part as wide
    as the rim, and it shows in the gap that opens on the other side of the bend (seams.minimum_overlap).
    Not `bounded`, every rim point runs the whole `depth` deep: an end brought to the contract's envelope
    (`ends`) stands in an over part opened as wide, and the contract asks the whole overlap of it.
    `lean` draws the cap in a little more than a dome from the start, because the over part often narrows
    just past the plane.

    `full` flags the faces of a pad over the joint (`guard`), and `hinge` is the axis the joint bends about,
    turning the pad's side of the rim toward the over part. A pad stands proud of the limb and its two halves
    stay on the two parts: the gap a bend opens between them is as wide as the pad is far out, and a dome
    `depth` deep, closing on one pole, lay well under the halves' cut edges there. A rim point on a pad's
    face is carried round the hinge instead, `GUARD_SWEEP` degrees in the rings before the pole: bent that
    far or less, the over part's half of the pad ends where one of those rings is, whatever the outline of
    the pad. It is drawn `GUARD_TUCK` nearer the hinge on the way, under the pad's own surface. A knee and an
    elbow bend one way only, so what is carried round does not come out on the other side. `grown`, if a
    list is given, is filled with the face of `faces` each added face grew from.

    With `tuck`, the first ring is the rim drawn in by that share just past the plane, and the dome goes on
    from there: a part that turns about its own length as well (a thigh) has a rim that is not round, and a
    cap as wide as the rim came out through the over part beside the plane."""
    relative = vertices - point
    height = relative @ normal
    flat = relative - height[:, None] * normal
    on = (np.abs(height) < WELD) & (np.linalg.norm(flat, axis=1) <= limit)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    under, of = np.tile(height[faces].sum(axis=1) > 0, 3), np.tile(np.arange(len(faces)), 3)
    keep = on[edges].all(axis=1)
    edges, under, of = edges[keep], under[keep], of[keep]
    if len(edges):
        _, inverse, count = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
        keep = (count[inverse.reshape(-1)] == 1) & under
        edges, of = edges[keep], of[keep]
    if not len(edges):
        return np.zeros((0, 3)), np.zeros((0, uvs.shape[1])), np.zeros((0, 3), int)
    rim = np.unique(edges)
    slot = np.full(len(vertices), -1, int); slot[rim] = np.arange(len(rim))
    domed = steps - 1 if tuck and steps > 1 else steps
    angles = np.radians(CAP_TOP * np.arange(1, domed + 1) / domed)
    deep = (np.minimum(depth, np.linalg.norm(flat[rim], axis=1)) if bounded else np.full(len(rim), float(depth)))[:, None]
    wide = 1.0 - (tuck if domed < steps else 0.0)
    rings = [point + flat[rim] * wide - normal * (deep * TUCK_RISE)] if domed < steps else []
    rings += [point + flat[rim] * (wide * np.cos(a) * (1.0 - lean * np.sin(a))) - normal * (deep * np.sin(a)) for a in angles]
    # the pole: one point, held once per rim point so each keeps its texture coordinates, and no deeper than the
    # nearest rim point is far from the centre
    rings[-1] = np.tile(point - normal * deep.min(), (len(rim), 1))
    if full is not None and steps > 1:
        require(hinge is not None, 'The rim of a pad is carried round a hinge')
        whole = np.zeros(len(vertices), bool)
        whole[edges[np.asarray(full, bool)[of]]] = True
        whole, hinge = whole[rim], seams.unit(hinge)
        along = (flat[rim[whole]] @ hinge)[:, None] * hinge
        out = flat[rim[whole]] - along
        for k in range(steps - 1):
            a = np.radians(GUARD_SWEEP) * (k + 1) / (steps - 1)
            rings[k][whole] = point + along + (1.0 - GUARD_TUCK) * (out * np.cos(a) + np.cross(hinge, out) * np.sin(a))
    if grown is not None:
        grown.extend(np.tile(of, 2 * steps - 1).tolist())
    index = np.concatenate([rim[None], base + np.arange(steps * len(rim)).reshape(steps, len(rim))])  # [ring, rim point]
    a, b = slot[edges[:, 0]], slot[edges[:, 1]]  # the part's face runs a to b, so the cap's runs b to a
    near, far = index[:-1], index[1:]
    # two faces per rim edge between rings, one at the pole, where the second would have no area
    added = np.concatenate([np.stack([near[:, b], near[:, a], far[:, a]], axis=2).reshape(-1, 3),
                            np.stack([near[:-1, b], far[:-1, a], far[:-1, b]], axis=2).reshape(-1, 3)])
    return np.concatenate(rings), np.tile(uvs[rim], (steps, 1)), added


def lid(vertices, uvs, faces, base, point, normal, limit, on=None):
    """Faces that close what a part has open on a joint plane: (vertices, uvs, faces) to add, numbered from `base`.

    An over part is open on its joint plane, and the under part stands in the opening and fills it. A chest
    that a shoulder pad was cut off is open there as wide as the pad lay on it, a hand's width more than the
    upper arm from front to back: with the arm lifted, the corners the arm does not fill showed as holes, right
    through the chest. The part's edges on the plane within `limit` of `point`, each on one face only (vertices
    at one position being one point), are closed line by line from the middle of each line's points, the new
    faces wound against the faces they grow from: the lid then faces the way the surface round it does, out
    of the part. A line that does not come round is closed straight from its end to its start. The under part stands through the lid as it stood in the opening. Each new vertex has the
    texture coordinates of the point of the line it grew from. `on`, if given, flags the points of the lines to
    close instead of the plane: the pelvis's leg holes on the seat line (`seated`)."""
    if on is None:
        relative = vertices - point
        height = relative @ normal
        on = (np.abs(height) < WELD) & (np.linalg.norm(relative - height[:, None] * normal, axis=1) <= limit)
    else:
        on = np.asarray(on, bool)
    none = np.zeros((0, 3)), np.zeros((0, uvs.shape[1])), np.zeros((0, 3), int)
    if not on.any():
        return none
    spot = np.full(len(vertices), -1, int)
    spot[on] = mesh_ops.weld_ids(vertices[on], WELD)
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = edges[on[edges].all(axis=1)]
    edges = edges[spot[edges[:, 0]] != spot[edges[:, 1]]]
    if not len(edges):
        return none
    _, inverse, count = np.unique(np.sort(spot[edges], axis=1), axis=0, return_inverse=True, return_counts=True)
    edges = edges[count[inverse.reshape(-1)] == 1]
    if not len(edges):
        return none
    line = mesh_ops.union_find(int(spot.max()) + 1, spot[edges].tolist())[spot[edges[:, 0]]]
    middle, chords = np.zeros((len(edges), 3)), []
    for label in np.unique(line):
        mine = edges[line == label]
        _, first, uses = np.unique(spot[mine], return_index=True, return_counts=True)
        middle[line == label] = vertices[mine.reshape(-1)[first]].mean(axis=0)  # one position per point of the line
        # a line that does not come round is closed from its end back to its start: its faces alone leave the
        # triangle between its two ends and its middle open (the pelvis between the two hip planes, where its
        # front and its back end on the line the planes meet in and nothing joins them)
        loose = mine.reshape(-1)[first[uses == 1]].tolist()  # the two points the line has one edge at
        if len(loose) == 2:
            end, begin = loose[::-1] if loose[0] in mine[:, 0] else loose  # the faces' edges run from its start to its end
            chords.append((end, begin, middle[line == label][0]))
    if chords:
        edges = np.concatenate([edges, [chord[:2] for chord in chords]])
        middle = np.concatenate([middle, [chord[2] for chord in chords]])
    added = base + np.arange(len(edges))
    return middle, uvs[edges[:, 0]], np.stack([edges[:, 1], edges[:, 0], added], axis=1)


def seated(vertices, faces, uvs, owner, origin, names, cuts, between, seat):
    """The thighs' faces that the body's own pelvis covers, given to the pelvis: (vertices, faces, uvs, owner,
    origin, on).

    The body's skin parts do not meet on the hip planes. Its pelvis is cut like briefs, round the seat to the
    fold under the buttock and down to the crotch, and its thigh runs up inside it. Cut on a hip plane, an
    outfit's thigh got half the trousers' seat, a section 7 cm outside the seam contract's envelope, which no
    other outfit's pelvis has room for. `seat` maps a side to how far the body's pelvis runs past that hip
    plane down the thigh, per direction round it (`measure.seat`, direction k at k turns over their number).
    Each thigh's faces are cut on that line, read straight between its directions, and what lies before it
    goes to the pelvis: the seat, the fold under it and the crotch. A vertex on the cut between the legs takes
    the mean of the two sides' lines, so the two thighs are cut alike where they meet. `on` flags the vertices
    on the line, where each thigh is then open, and the pelvis round it (`seat_end`, `lid`)."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    owner, origin = np.asarray(owner, int), np.asarray(origin, int)
    thighs = [names.index(token('thigh', side)) for side in seat if token('thigh', side) in names]
    if 'pelvis' not in names or not thighs:
        return v, f, t, owner, origin, np.zeros(len(v), bool)
    lines = {}
    for side, reach in seat.items():
        point, normal = np.asarray(cuts[('hip', side)][0], float), seams.unit(cuts[('hip', side)][1])
        a, b = seams.frame(normal)
        relative = v - point
        lines[side] = relative @ normal - seams.around(reach, np.arctan2(relative @ b, relative @ a))
    across = (v - between['point']) @ between['normal']  # toward the right thigh
    far = np.full(len(v), np.inf)
    value = np.where(across < 0, lines.get('l', far), lines.get('r', far))
    if len(lines) == 2:
        value = np.where(np.abs(across) < WELD, (lines['l'] + lines['r']) / 2, value)
    return handed(v, f, t, owner, origin, np.isin(owner, thighs), value, names.index('pelvis'))


def handed(vertices, faces, uvs, owner, origin, mine, value, to):
    """The faces flagged `mine` cut where `value`, per vertex, is zero, and what lies at or below zero given to
    part `to`: (vertices, faces, uvs, owner, origin, on), `on` flagging the vertices on the line."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    value = np.where(np.abs(value) < EPSILON, 0.0, value)
    count = len(v)
    v, cut_faces, t, o = cut(v, f[mine], t, None, None, height=value)
    level = np.concatenate([value, np.zeros(len(v) - count)])
    on = np.zeros(len(v), bool)  # only the faces cut: another part's vertex at zero is on no line of these
    on[np.unique(cut_faces)] = level[np.unique(cut_faces)] == 0
    moved = level[cut_faces].max(axis=1) <= 0
    return (v, np.concatenate([f[~mine], cut_faces]), t, np.concatenate([owner[~mine], np.where(moved, to, owner[mine][o])]),
            np.concatenate([origin[~mine], origin[mine][o]]), on)


def topped(vertices, faces, uvs, owner, origin, names, cuts, sleeves, limit):
    """Each shoulder pad cut on its shoulder plane, and what of it lies before the plane, over the top of the
    shoulder, given to the chest: (vertices, faces, uvs, owner, origin, sides), `sides` those cut.

    The shoulder slot's bone is the upper arm's child: a pad turns as far as the arm. Overhead, as the Human
    male's conjure2 holds it (145 degrees), what of a pad lay over the top of the shoulder swung forward and down
    into the chest and showed there in shards; in the clips that lift the arms only those points went in. Below
    the plane the pad still rides on the arm. The cut's points on the pad's outline (`sleeves`, the outline's
    flags, which this extends) are on the outline too, so the closings along it end on the plane; `limit` is
    widened to the cut, where the chest and the pad's half on the arm are closed (`lid`)."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    owner, origin, sides = np.asarray(owner, int), np.asarray(origin, int), []
    for side, found in sleeves.items():
        name = token('shoulder', side)
        if 'on' not in found or name not in names or 'chest' not in names:
            continue
        mine = owner == names.index(name)
        point, normal = np.asarray(cuts[('shoulder', side)][0], float), seams.unit(cuts[('shoulder', side)][1])
        height = (v - point) @ normal
        if not mine.any() or (height[f[mine]] > EPSILON).all():
            continue  # all of it on the arm's side
        outline = np.asarray(found['on'][3], bool)
        edges = np.concatenate([f[mine][:, [0, 1]], f[mine][:, [1, 2]], f[mine][:, [2, 0]]])
        edges = edges[outline[edges].all(axis=1)]
        count = len(v)
        v, f, t, owner, origin, line = handed(v, f, t, owner, origin, mine, height, names.index('chest'))
        start, run = v[edges[:, 0]], v[edges[:, 1]] - v[edges[:, 0]]
        share = np.clip(np.einsum('nkd,kd->nk', v[count:, None] - start[None], run) / np.maximum((run * run).sum(axis=1), 1e-24), 0.0, 1.0)
        apart = np.linalg.norm(start[None] + share[..., None] * run[None] - v[count:, None], axis=2)
        found['on'] = [np.concatenate([np.asarray(row, bool), np.zeros(len(v) - len(row), bool)]) for row in found['on']]
        found['on'][3][count:] |= (apart < WELD).any(axis=1) if len(edges) else False
        relative = v[line] - point
        if len(relative):
            limit[('shoulder', side)] = max(limit[('shoulder', side)],
                                            float(np.linalg.norm(relative - (relative @ normal)[:, None] * normal, axis=1).max()) + WELD)
        sides.append(side)
    return v, f, t, owner, origin, sides


def armholed(vertices, faces, uvs, owner, origin, names, cuts, arms, floor=ARM_FLOOR):
    """The upper arms' faces that the body's own chest covers, given to the chest: (vertices, faces, uvs, owner,
    origin, on).

    The body's skin parts overlap at the shoulder, and the line its upper arm comes out of the chest on runs
    over the shoulder before the plane and down to the armpit past it (`measure.armhole`). `arms` maps a side
    to that line, per direction round the joint as `seated` reads a seat. Each upper arm's faces are cut on
    it, but never nearer the plane than `floor`, and what lies before it goes to the chest: the sleeve's top
    where it runs into the torso at the armpit, and the slivers of sleeve between a shoulder pad and the
    torso. The arm's own surface then stays off the plane, and its end comes in to the envelope there
    (`seat_end`). `on` flags the vertices on the lines."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    owner, origin, on = np.asarray(owner, int), np.asarray(origin, int), np.zeros(len(v), bool)
    if 'chest' not in names:
        return v, f, t, owner, origin, on
    for side, line in arms.items():
        if token('bicep', side) not in names:
            continue
        point, normal = np.asarray(cuts[('shoulder', side)][0], float), seams.unit(cuts[('shoulder', side)][1])
        a, b = seams.frame(normal)
        relative = v - point
        value = relative @ normal - np.maximum(seams.around(line, np.arctan2(relative @ b, relative @ a)), floor)
        count = len(v)
        v, f, t, owner, origin, more = handed(v, f, t, owner, origin, owner == names.index(token('bicep', side)), value, names.index('chest'))
        on = np.concatenate([on, np.zeros(len(v) - count, bool)]) | more
    return v, f, t, owner, origin, on


def arm_opening(vertices, cuts, side, limit=np.inf):
    """Flags of the points in an arm's opening at the shoulder: from the plane on, as far as `ARM_OPENING` of the
    way to the elbow, and within `limit` of the joint's axis."""
    point, normal = np.asarray(cuts[('shoulder', side)][0], float), seams.unit(cuts[('shoulder', side)][1])
    relative = np.asarray(vertices, float) - point
    height = relative @ normal
    down = ARM_OPENING * ((np.asarray(cuts[('elbow', side)][0], float) - point) @ normal)
    return (height > -WELD) & (height < down) & (np.linalg.norm(relative - height[:, None] * normal, axis=1) <= limit)


def seat_end(vertices, uvs, faces, base, point, normal, on, ring, depth, over, bend=0.0, out=None, steps=SEAT_STEPS, dome=SEAT_DOME,
             gap=SEAT_GAP):
    """A thigh's end, grown from its rim on the seat line (`seated`), or an upper arm's from its opening at the
    shoulder (`split`, `arms`): (vertices, uvs, faces) to add, numbered from `base`.

    The rim is the part's edges with both points `on` the line (or for an arm in its opening, `arm_opening`), each
    on one face only, in pieces that come round the joint (`SEAT_ROUND`): a pocket's edge crossing the line is
    left as it is. Every rim point runs in
    `steps` rings to the hip plane, drawn in there to `ring`, the end's radius per direction read straight
    between its directions (never out), in one slope; then on a dome `depth` past the plane in `dome` rings,
    the last its pole on the joint's axis. Every point of it stands `gap` inside the over part's surface `over`
    (vertices, faces), read per direction round the limb and height along it, as the body stands and with the
    thigh turned about the joint forward and back by half of `bend` degrees and all of it, and in and out by a
    quarter and half of it: bounded at rest only, its sides came through the seat in a stride. Given `out`, the
    way from the torso to the joint, the limb is an arm: it turns forward and back as a thigh does, and out from
    the torso by half and all of `bend`, never in across it. Each point is drawn in toward the
    axis, at its height, as far as that takes; the pole stays, as deep as the seam contract asks. The seat covers
    the end as the body stands, and turned the end fills what the thigh leaves of the leg hole. Each new vertex
    keeps the columns of the rim point it grew from; the faces wind as the cap's (`cap`). Where two rim points
    beside each other are both drawn onto the axis at one height, the face between them has two corners at
    one `POINT` and no area, and is left out: the model compiler drops it, and Facility Security's left upper
    arm compiled to 16 faces fewer than it was written with (2026-11-13)."""
    none = np.zeros((0, 3)), np.zeros((0, uvs.shape[1])), np.zeros((0, 3), int)
    point, normal, on = np.asarray(point, float), seams.unit(normal), np.asarray(on, bool)
    if not on.any():
        return none
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = edges[on[edges].all(axis=1)]
    if not len(edges):
        return none
    _, inverse, count = np.unique(np.sort(edges, axis=1), axis=0, return_inverse=True, return_counts=True)
    edges = edges[count[inverse.reshape(-1)] == 1]
    if not len(edges):
        return none
    a, b = seams.frame(normal)
    relative = vertices - point
    height = relative @ normal
    angle = np.arctan2(relative @ b, relative @ a)
    spot = np.full(len(vertices), -1, int)
    points = np.unique(edges)
    spot[points] = mesh_ops.weld_ids(vertices[points], WELD)
    piece = np.asarray(mesh_ops.union_find(int(spot.max()) + 1, spot[edges].tolist()))[spot[edges[:, 0]]]
    span = np.abs((angle[edges[:, 1]] - angle[edges[:, 0]] + np.pi) % (2 * np.pi) - np.pi)  # the turn each edge runs round the axis
    keep = np.zeros(len(edges), bool)
    for label in np.unique(piece):
        mine = piece == label
        keep |= mine & (span[mine].sum() >= SEAT_ROUND * 2 * np.pi)
    edges = edges[keep]
    if not len(edges):
        return none
    rim = np.unique(edges)
    slot = np.full(len(vertices), -1, int)
    slot[rim] = np.arange(len(rim))
    r = np.linalg.norm(relative[rim] - height[rim, None] * normal, axis=1)
    h, turn = height[rim], angle[rim]
    end = np.minimum(seams.around(ring, turn), r)
    smooth = lambda x: x * x * (3 - 2 * x)
    rings = [(r + (end - r) * smooth(k / steps), h * (1 - k / steps)) for k in range(1, steps + 1)]
    rings += [(end * np.cos(phi), np.full(len(rim), -depth * np.sin(phi))) for phi in np.radians(90.0 * np.arange(1, dome) / dome)]
    # the pelvis's own surface, nearest the joint's axis per direction and height
    # only the points of its faces: `over` may hold the whole outfit's vertices, the limb's own among them
    used, local = np.unique(np.asarray(over[1], int), return_inverse=True)
    sample = seams.surface_points(np.asarray(over[0], float)[used], local.reshape(-1, 3), SEAT_SAMPLE) - point
    along = sample @ normal
    rows = np.floor(along / SEAT_ROW).astype(int)
    first = rows.min() - 1
    least = np.full((SEAT_BINS, rows.max() - first + 2), np.inf)
    turns = np.floor((np.arctan2(sample @ b, sample @ a) % (2 * np.pi)) / (2 * np.pi / SEAT_BINS)).astype(int) % SEAT_BINS
    np.minimum.at(least, (turns, rows - first), np.linalg.norm(sample - along[:, None] * normal, axis=1))
    near = np.minimum.reduce([np.roll(np.roll(least, i, axis=0), j, axis=1) for i in (-1, 0, 1) for j in (-1, 0, 1)])
    column = np.floor((turn % (2 * np.pi)) / (2 * np.pi / SEAT_BINS)).astype(int) % SEAT_BINS
    forward = seams.unit(np.array((0.0, 1.0, 0.0)) - normal[1] * normal)
    across = np.cross(normal, forward)
    swings = [(across, (bend / 2, bend, -bend / 2, -bend))]
    if out is None:  # a thigh, in and out
        swings.append((forward, (bend / 4, bend / 2, -bend / 4, -bend / 2)))
    else:  # an arm, out from the torso: turned about this axis the limb leans toward `out`
        out = np.asarray(out, float)
        swings.append((np.cross(normal, seams.unit(out - (out @ normal) * normal)), (bend / 2, bend)))
    turns = [np.eye(3)] + [rotation(axis, degrees) for axis, angles in swings for degrees in angles if degrees]

    def inside(points, turned):
        """Whether each point stands `gap` inside the over part's surface with the limb turned by `turned`."""
        moved = (points - point) @ turned.T
        level = moved @ normal
        row = np.floor(level / SEAT_ROW).astype(int) - first
        within = (row >= 0) & (row < least.shape[1])
        spin = np.floor((np.arctan2(moved @ b, moved @ a) % (2 * np.pi)) / (2 * np.pi / SEAT_BINS)).astype(int) % SEAT_BINS
        bound = np.where(within, near[spin, np.clip(row, 0, least.shape[1] - 1)], np.inf)
        return np.linalg.norm(moved - level[:, None] * normal, axis=1) <= bound - gap

    def fits(points, held):
        """Whether each point stands inside in every pose it is held in (`held`, per pose and point)."""
        good = np.ones(len(points), bool)
        for turned, mine in zip(turns, held):
            good &= ~mine | inside(points, turned)
        return good

    radial = np.cos(turn)[:, None] * a + np.sin(turn)[:, None] * b  # per rim point, its way out from the axis
    placed = []
    for radius, level in rings:
        at = lambda share: point + (share * radius)[:, None] * radial + level[:, None] * normal
        # Turned, a point on the axis leaves it as far as its height times the turn's sine: drawn in, a point is
        # held only in the poses its place on the axis fits in. As the body stands it always is.
        held = [np.ones(len(rim), bool)] + [inside(at(np.zeros(len(rim))), turned) for turned in turns[1:]]
        low, high = np.zeros(len(rim)), np.ones(len(rim))
        whole = fits(at(high), held)
        for _ in range(SEAT_HALVINGS):  # the largest share of its radius each point keeps and still fits
            middle = (low + high) / 2
            good = fits(at(middle), held)
            low, high = np.where(good, middle, low), np.where(good, high, middle)
        placed.append(at(np.where(whole, 1.0, low)))
    placed.append(np.tile(point - depth * normal, (len(rim), 1)))  # the pole, held once per rim point for its columns
    total = len(placed)
    index = np.concatenate([rim[None], base + np.arange(total * len(rim)).reshape(total, len(rim))])
    start, finish = slot[edges[:, 0]], slot[edges[:, 1]]  # the part's face runs start to finish, so the end's runs back
    nearer, farther = index[:-1], index[1:]
    added = np.concatenate([np.stack([nearer[:, finish], nearer[:, start], farther[:, start]], axis=2).reshape(-1, 3),
                            np.stack([nearer[:-1, finish], farther[:-1, start], farther[:-1, finish]], axis=2).reshape(-1, 3)])
    grown = np.concatenate(placed)
    corners = np.where((added < base)[..., None], vertices[np.minimum(added, len(vertices) - 1)], grown[np.maximum(added - base, 0)])
    sides = np.linalg.norm(corners - np.roll(corners, 1, axis=1), axis=2)
    return grown, np.tile(uvs[rim], (total, 1)), added[sides.min(axis=1) >= POINT]


def rotation(axis, degrees):
    """The matrix that turns `degrees` about `axis`."""
    axis, angle = seams.unit(axis), np.radians(degrees)
    k = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
    return np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * k @ k


def gusset(vertices, uvs, faces, base, seam, width=GUSSET_WIDTH, below=GUSSET_BELOW, under=GUSSET_UNDER):
    """The surface along the cut between the legs, to repeat on the pelvis: (vertices, uvs, faces) to add, numbered
    from `base`.

    The cut parts the crotch of a pair of trousers into the two thighs, each closed toward the other by a flat
    wall. The game stands a body with its thighs turned out and a little apart: the crotch then opens at the
    front, a hand's width at most, and showed the two walls and the inside of the pelvis between them. Stock
    parts have a pelvis that reaches down between the legs. `faces` are the two thighs' own faces, `seam` the
    cut (`point`, `normal`, `radius`, and `down`, the way the legs leave the hips in its plane). What they have
    within `width` of the cut's plane, and no farther down than the line they were cut along reaches, with
    `below` to spare, is cut out of a copy of them and repeated `under` inside the surface, along its normals: a strip from the front of the crotch
    round to the seat, which the thighs cover as the body stands and uncover as they turn. Its two lower
    corners are cut off at 45 degrees, `GUSSET_CORNER` of its half width in: left square, it hung between
    the parted legs as a flap with corners. Its vertices keep
    the columns of those they repeat, and so that surface's colours. Legs nothing joins have no point on the
    cut, and no strip."""
    none = np.zeros((0, 3)), np.zeros((0, uvs.shape[1])), np.zeros((0, 3), int)
    used = np.unique(faces)
    line = vertices[used[on_cut(vertices[used], seam['point'], seam['normal'], seam['radius'], seam.get('bounds', ()))]]
    if not len(line):
        return none
    down = seam['down']
    v, f, t = compact(vertices, faces, uvs)
    low = ((line - seam['point']) @ down).max() + below
    walls = [(seam['point'] + width * seam['normal'], seam['normal']), (seam['point'] - width * seam['normal'], -seam['normal']),
             (seam['point'] + low * down, down)]
    walls += [(seam['point'] + low * down + way * (1.0 - GUSSET_CORNER) * width * seam['normal'], seams.unit(down + way * seam['normal'])) for way in (1.0, -1.0)]
    for point, normal in walls:
        v, f, t, _ = cut(v, f, t, point, normal)
    centres = v[f].mean(axis=1)
    f = f[np.all([(centres - point) @ normal < 0 for point, normal in walls], axis=0)]
    if not len(f):
        return none
    v, f, t = compact(v, f, t)
    spot = mesh_ops.weld_ids(v, WELD)  # a vertex repeated at a texture seam is one point of the surface
    corners = v[f]
    normals = np.zeros((int(spot.max()) + 1, 3))
    np.add.at(normals, spot[f].reshape(-1), np.repeat(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), 3, axis=0))
    normals = normals / np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    return v - under * normals[spot], t, f + base


def assign(vertices, faces, uvs, joints, radii, reach=REACH, reaches=None, whole=(), sleeves=None):
    """The mesh cut on every plane, and the part each face goes to.

    `sleeves` is what `troughs` found on this mesh in the pose it came in, the vertices and faces unchanged
    since but for where they stand: the sleeves are then parted along those cuts. Without it a fused sleeve's
    trough is found and cut on the mesh as it stands here. A shoulder pad `troughs` found goes whole to that
    side's shoulder part here, whichever side of the shoulder plane its faces lie on, and `split` gives what of
    it lies before the plane back to the chest (`topped`): the rest rides on the arm, as the shoulder slot's
    bone does.

    Returns (vertices, faces, uvs, owner, names, origin, cuts, sleeves, between, limit): `owner[i]` indexes
    `names`, `origin[i]` is the face of the mesh given that face i was cut from, `cuts` maps (joint, side) to
    its plane, `sleeves` maps a side to the sleeve seam cut there (`sleeve`; for one cut in another pose, the
    flags of the vertices on its planes as `on`, with the `normal` toward the torso and the planes' `normals`), `between` is the cut
    between the legs (`point`, `normal`, `radius`, `down`) and `limit` maps (joint, side) to how far its plane cut."""
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
    down = normal_l + normal_r  # a hip plane's normal points to its thigh
    between = {'point': middle, 'normal': across, 'radius': max(limit[('hip', 'l')], limit[('hip', 'r')]), 'down': seams.unit(down - (down @ across) * across)}
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
        # The trough was cut so that the sleeve goes with the arm. Where its cuts and the shoulder plane leave a strip
        # that still joins sleeve and torso, they are one piece and the chest, the larger, takes it all: the arm then
        # lifts out of a sleeve that stays on the chest. Nothing shows of that standing, so it is refused here.
        bare = (np.asarray(found['inside'], bool) & ~np.asarray(found.get('pad', np.zeros(len(origin), bool)), bool))[origin]
        arm = np.isin(owner, [names.index(token(slot, side)) for slot in ('bicep', 'forearm', 'hand') if token(slot, side) in names])
        size = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
        require(size[bare & arm].sum() >= SLEEVE_PARTED * size[bare].sum(),
                f'The {side} sleeve stays joined to the torso: {size[bare & arm].sum() / max(size[bare].sum(), 1e-12):.0%} of it goes with the arm')
        mine = np.asarray(found.get('pad', np.zeros(len(origin), bool)), bool)[origin]
        if mine.any():
            owner = np.where(mine, len(names), owner)
            names.append(token('shoulder', side))
    return v, f, t, owner, names, origin, cuts, sleeves, between, limit


def split(vertices, faces, uvs, joints, radii, overlaps=None, reach=REACH, reaches=None, whole=(), made=None, sleeves=None, guards=None, origins=None,
          shape=None, deep=(), seat=None, arms=None):
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
    `OWN` for the outfit's own surface, `CLOSING` and `CAP` for what the split added, `WALL` for a thigh's
    closing toward the other leg, `PADDED` for the faces of a cap that grew from a pad's rim, and `GUSSET` for
    the surface between the legs that the pelvis repeats under the thighs (`gusset`). `origins`, if a dict is
    given, is filled alike with the face of `faces` each face of a part was cut from, -1 for what the split
    added or repeated. `sleeves` is what `troughs`
    found on this mesh in the pose it came in. A shoulder pad found with them is a shoulder part (`assign`)
    as far as it lies past the shoulder plane, and the chest's before it (`topped`); the shoulder part is closed
    underneath across its own outline and on the plane. The outfit has no surface under a pad: the upper arm is
    closed flat under it, where the pad always covers it, and the chest where the pad's part lay on it. A pad
    the plane cuts leaves the chest open on the plane and, in the armpit, past it: that is closed as one round
    the arm (`arm_opening`, `lid`). A pad past the plane alone leaves it open along its outline, closed rounded
    out from the plane as the shoulder under the pad, and what is then left open on the plane is closed too. The pelvis is closed on both hip planes, and repeats the surface along the cut
    between the legs under the thighs (`gusset`).

    `guards` maps (joint, side), a knee or an elbow, to the flags of its pad's faces on the mesh given
    (`guard`). The pad is cut on the joint plane like the cloth round it, and each half stays on its part:
    given whole to the shin or the forearm it swung off the thigh at the slightest bend, with nothing behind
    it, and stood out behind a bent elbow like a paddle. The under part's cap carries the pad's rim round
    the joint's hinge instead (`cap`, `full`), in `GUARD_STEPS` rings, and fills the gap a bend opens between
    the two halves out to their cut edges; `made` reports those faces as `PADDED`, the rest of that cap as
    `CAP`. A knee's gap opens in front and an elbow's behind, about the axis across the limb.

    `shape`, if given, is called on each part after its closings and lids and before its caps, as
    `shape(name, vertices, faces, uvs, origin)` with the part's own faces first in `faces` and `origin` the face
    of `faces` given here each of those was cut from; it returns the part's (vertices, uvs), which the caps
    then grow from (`ends.shaper`). At the joints `deep` names a cap is not `bounded`.

    `seat` maps a hip, ('hip', side), to `reach`, how far the body's pelvis runs past that hip plane down the
    thigh per direction (`measure.seat`), and `ring`, the radius per direction the thigh's end stands at on
    the plane, and may give `bend`, the degrees the thigh turns that its end is to stay inside the pelvis
    through. What the body's pelvis covers then goes to the pelvis (`seated`), which is closed across each leg
    hole on that line (`lid`), and the thigh's end is grown from its rim there instead of a cap (`seat_end`),
    as deep past the plane as `overlaps` says; `made` reports its faces as `CAP`.

    `arms` maps a shoulder, ('shoulder', side), to `line`, where the body's upper arm comes out of its chest
    per direction round the joint (`measure.armhole`), and `ring` and `bend` as a seat does. What of the upper
    arm lies before that line, and before `ARM_FLOOR` past the plane, goes to the chest (`armholed`), which is
    closed across each armhole: every line it has open from the plane to `ARM_OPENING` of the way to the elbow,
    the sleeve it took and the closings along it (`lid`). The upper arm gets one end grown from its whole opening at the shoulder
    (`seat_end`, within `ARM_OPENING` of the way to the elbow): where the sleeve was cut on that line, parted
    from the torso and from its pad. It stands instead of a closing along each of those cuts and a cap on the
    plane: rounded out toward the chest, those closings stood up to 9 cm outside the seam contract's envelope
    beside a shoulder pad. The end is held inside the chest's own surface and its closings, with the arm turned
    forward, back and out from the torso."""
    overlaps = overlaps or {}
    require(all(key[0] in seams.JOINTS and key[1] in seams.sides(key[0]) for key in overlaps)
            and all((depth or 0) >= 0 for depth in overlaps.values()), 'Overlaps are depths of zero or more, by joint and side')
    seat = dict(seat or {})
    require(all(key in (('hip', 'l'), ('hip', 'r')) and key not in set(whole) and {'reach', 'ring'} <= set(entry) for key, entry in seat.items()),
            'A seat is a hip by joint and side, with how far the pelvis reaches past it and the ring its thigh ends at')
    arms = dict(arms or {})
    require(all(key in (('shoulder', 'l'), ('shoulder', 'r')) and key not in set(whole) and {'line', 'ring'} <= set(entry) for key, entry in arms.items()),
            'An arm is a shoulder by joint and side, with the line the body\'s arm leaves its chest on and the ring its upper arm ends at')
    v, f, t, owner, names, origin, cuts, sleeves, between, limit = assign(vertices, faces, uvs, joints, radii, reach, reaches, whole, sleeves)
    if 'chest' not in names or not np.any(owner == names.index('chest')):
        arms = {}  # no chest to hold an arm's end: its openings are closed and capped on the plane
    v, f, t, owner, origin, halved = topped(v, f, t, owner, origin, names, cuts, sleeves, limit)
    on_seat = np.zeros(len(v), bool)
    if seat:
        v, f, t, owner, origin, on_seat = seated(v, f, t, owner, origin, names, cuts, between, {key[1]: entry['reach'] for key, entry in seat.items()})
    if arms:
        v, f, t, owner, origin, _ = armholed(v, f, t, owner, origin, names, cuts, {key[1]: entry['line'] for key, entry in arms.items()})
        on_seat = np.concatenate([on_seat, np.zeros(len(v) - len(on_seat), bool)])
    # The cuts off the joint planes, each with the parts it leaves open and the way their closing faces: a
    # sleeve seam opens the sleeve and the chest, and where it cut a stray bridge near the elbow, the forearm and
    # the pelvis; the cut between the legs opens the two thighs toward each other wherever trousers joined them
    # below the hip planes.
    # A sleeve is rounded out toward the chest from its rim on the shoulder plane: lifted, it is round where it
    # left the torso. The other closings stay flat: the torso's own, those of a stray bridge, and the thighs',
    # which lie against each other, where a rounded one comes out through the other leg at the crotch.
    rim = lambda joint, side: (np.asarray(cuts[(joint, side)][0], float), seams.unit(cuts[(joint, side)][1]))
    closings, lids = [], []
    for side, found in sleeves.items():
        trough, outline = found, None
        if 'on' in found:  # cut in the pose the outfit came in: the trough's three planes, and the pad's outline
            trough = {**found, 'on': found['on'][:3], 'normals': found['normals'][:3]}
            outline = {**found, 'on': found['on'][3:], 'normals': found['normals'][3:]}
        arm = {} if ('shoulder', side) in arms else {token('bicep', side): (1.0, rim('shoulder', side))}  # or its end closes it
        closings.append((trough, {**arm, token('forearm', side): (1.0, None), 'chest': (-1.0, None), 'pelvis': (-1.0, None)}))
        if outline is not None:
            alone = ('shoulder', side) not in arms
            if np.any(outline['on']) and alone and side not in halved:  # a pad was cut off: the chest is open on the shoulder plane as wide as it lay
                lids.append(('chest', 'shoulder', side))
            arm = {token('bicep', side): (1.0, None)} if alone else {}
            # a pad halved, the chest is open where its half on the arm lay, on the plane and past it in the armpit:
            # closed as one, round the arm (below), as the chest round an arm's end is
            chest = {} if alone and side in halved else {'chest': (-1.0, rim('shoulder', side), PAD_RINGS)}
            closings.append((outline, {token('shoulder', side): (1.0, None), **arm, **chest}))
    closings.append((between, {token('thigh', 'l'): (1.0, None), token('thigh', 'r'): (-1.0, None)}))
    pads = {}  # per under part with a pad over its joint: the joint, and the pad's flags on the cut faces
    for key, flags in (guards or {}).items():
        require(len(key) == 2 and key[0] in GUARDS and key[1] in ('l', 'r') and np.shape(flags) == (len(faces),),
                f'A pad is the flags of its faces, over one of {sorted(GUARDS)} on the l or r side')
        pads[token(seams.JOINTS[key[0]]['under'], key[1])] = (tuple(key), np.asarray(flags, bool)[origin])
    # The pelvis is open on both hip planes, and between them it keeps the crotch: a front and a back of the trousers
    # with nothing under them. A thigh stands in each opening only as the body stands; turned (a stride, a seat), it
    # leaves the opening, and the crotch hung there as a loose sheet with the inside of the pelvis behind it.
    lids += [('pelvis', 'hip', side) for side in 'lr' if ('hip', side) not in whole and ('hip', side) not in seat]
    lids += [(token('shoulder', side), 'shoulder', side) for side in halved]  # a pad's half on the arm, open where the chest's half went
    opened = [side for _, side in arms] + [side for side in halved if ('shoulder', side) not in arms]
    legs = f[np.isin(owner, [names.index(token('thigh', side)) for side in 'lr' if token('thigh', side) in names])]
    seat_over = (v, f[owner == names.index('pelvis')]) if seat and 'pelvis' in names else None  # the pelvis's own surface
    arm_over = None  # the chest's own surface and its closings, which an upper arm's end stays inside
    result = {}
    for index in sorted(range(len(names)), key=lambda index: names[index] != 'chest'):  # the chest first
        name = names[index]
        mine = f[owner == index]
        if not len(mine):
            continue
        pv, pf, pt, closed, kinds = v, mine, t, np.zeros(0, int), [np.full(len(mine), OWN)]
        own = len(mine)
        for seam, facing in closings:  # closed first: an under part's cap then grows from a closed rim
            if name in facing:
                more = seam_fill(pv, pt, pf, len(pv), seam, *facing[name])
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                closed = np.concatenate([closed, len(pv) - len(more[0]) + np.arange(len(more[0]))])  # where the closing's vertices are
                kinds.append(np.full(len(more[2]), WALL if seam is between else CLOSING))
        if name == 'chest':
            arm_over = (pv, pf)
        for joint, side in [key[1:] for key in lids if key[0] == name]:
            more = lid(pv, pt, pf, len(pv), cuts[(joint, side)][0], seams.unit(cuts[(joint, side)][1]), limit[(joint, side)] + WELD)
            pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
            kinds.append(np.full(len(more[2]), CLOSING))
        if name == 'pelvis' and on_seat.any():  # open round each thigh on the seat line
            more = lid(pv, pt, pf, len(pv), None, None, None, on=np.concatenate([on_seat, np.zeros(len(pv) - len(v), bool)]))
            pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
            kinds.append(np.full(len(more[2]), CLOSING))
        if name == 'chest' and opened:  # open round each arm, from the plane down the sleeve it took and its closings
            zone = np.any([arm_opening(pv, cuts, side, limit[('shoulder', side)] + WELD) for side in opened], axis=0)
            more = lid(pv, pt, pf, len(pv), None, None, None, on=zone)
            pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
            kinds.append(np.full(len(more[2]), CLOSING))
        if shape is not None:
            pv, pt = shape(name, pv, pf, pt, np.asarray(origin)[owner == index])
        for (joint, side), depth in overlaps.items():
            if depth and (joint, side) in seat:
                if token('thigh', side) == name:
                    more = seat_end(pv, pt, pf, len(pv), cuts[(joint, side)][0], cuts[(joint, side)][1],
                                    np.concatenate([on_seat, np.zeros(len(pv) - len(v), bool)]), seat[(joint, side)]['ring'], depth, seat_over,
                                    seat[(joint, side)].get('bend', 0.0))
                    pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                    kinds.append(np.full(len(more[2]), CAP))
            elif depth and (joint, side) in arms:
                if token('bicep', side) == name:
                    point, normal = cuts[(joint, side)]
                    middle = (np.asarray(joints['lbicep_g'], float) + np.asarray(joints['rbicep_g'], float)) / 2
                    more = seat_end(pv, pt, pf, len(pv), point, normal, arm_opening(pv, cuts, side), arms[(joint, side)]['ring'], depth, arm_over,
                                    arms[(joint, side)].get('bend', 0.0), out=np.asarray(point, float) - middle)
                    pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                    kinds.append(np.full(len(more[2]), CAP))
            elif depth and (joint, side) not in whole and token(seams.JOINTS[joint]['under'], side) == name:
                point, normal = cuts[(joint, side)]
                # a rounded closing carries the part's rim on the plane out past the plane's own reach
                away = pv[closed] - point
                away = away - (away @ seams.unit(normal))[:, None] * seams.unit(normal)
                reach_here = max([limit[(joint, side)]] + (np.linalg.norm(away, axis=1) + WELD).tolist())
                full, grown, across = np.zeros(len(pf), bool), [], seams.unit(normal)
                if pads.get(name, (None,))[0] == (joint, side):
                    full[:len(mine)] = pads[name][1][owner == index]
                opens = np.array((0.0, 1.0 if joint == 'knee' else -1.0, 0.0))  # the side the bend opens the gap on
                options = {'tuck': TUCKS[joint], 'steps': TUCK_STEPS} if joint in TUCKS else {}
                options['bounded'] = joint not in deep
                if full.any():  # a pad's rim is carried round the hinge in its own number of rings, tucked or not
                    options.update(full=full, hinge=np.cross(opens - (opens @ across) * across, -across), steps=GUARD_STEPS)
                more = cap(pv, pt, pf, len(pv), point, across, depth, reach_here, grown=grown, **options)
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
                kinds.append(np.where(full[np.asarray(grown, int)], PADDED, CAP))
        if name == 'pelvis':  # last: its edges are no opening to close
            more = gusset(v, t, legs, len(pv), between)
            pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
            kinds.append(np.full(len(more[2]), GUSSET))
        result[name] = compact(pv, pf, pt)
        if made is not None:
            made[name] = np.concatenate(kinds)
        if origins is not None:
            origins[name] = np.concatenate([np.asarray(origin)[owner == index], np.full(len(pf) - own, -1)])
    return {name: result[name] for name in names if name in result}
