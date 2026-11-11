"""Cut one outfit mesh into the rigid armor parts, on the joint planes of the seam contract.

The mesh and the joints are in one space with the bodies' axes: z up, facing +y, left at -x. The neck and waist
planes are level in it and a foot runs forward, so a source in other axes is turned first; `assign` refuses
joints that do not stand that way. Every joint plane cuts the triangles it crosses, but only near the joint,
so that the waist plane does not slice a forearm hanging beside it. The cuts leave the surface in connected
pieces. Each face votes for the part whose side of every plane it is on and whose bone it is nearest, and a
whole piece goes to the part most of its area voted for: a hand resting on a thigh stays a hand. At each
joint the under part also gets a rounded cap past the plane, grown from its own rim: turned about the joint,
the cap stays inside the over part and fills the gap that opens (docs/armorkit/plan.md, "Seam rules").
"""
import numpy as np

from tools.robes import mesh_ops

from . import registry, seams
from .registry import require

EPSILON = 1e-7  # a vertex this near a plane counts as on it
REACH = 1.35  # a plane cuts this many joint radii from the joint centre, measured in the plane
CAP_STEPS = 5  # rings a cap is built from
CAP_TOP = 80.0  # degrees of its dome a cap covers; it stops short of the pole, where faces would have no area
LEAN = 0.3  # how much more than a dome a cap draws in as it leaves the plane, to clear an over part that narrows there
WELD = 1e-5  # vertices this close are one point when pieces are traced (models repeat vertices at texture seams)
RIVAL = 0.35  # a piece whose second choice won this share of its area is two parts welded together: it is traced again unwelded
FREE_END = 0.12  # how far the bone of a neck, hand or foot runs on past its joint
SLEEVE_STEP = 0.01  # the arm is sectioned this far apart when the armpit is looked for
SLEEVE_FUSED = 1.6  # a section reaching this many times farther toward the torso than away from it is sleeve and torso in one
SLEEVE_ROOM = 0.003  # the sleeve seam stands this far inside the sleeve's inner side at the armpit


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


def regions(joints, radii, reach=REACH, reaches=None):
    """{token: {bone, radii, planes}}: a part's bone, its thickness at each end and its side of each joint plane.

    `planes` holds (point, normal, sign, limit). A plane only says anything within `limit` of its joint,
    measured in the plane: the shoulder plane runs on through the lower torso, which is still chest."""
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
        for slot, sign in ((spec['over'], -1.0), (spec['under'], 1.0)):
            result[token(slot, side)]['planes'].append((point, seams.unit(normal), sign, limit[(joint, side)]))
    return result


def cut(vertices, faces, uvs, point, normal, radius=None):
    """Split the triangles the plane crosses, so that none spans it. Returns (vertices, faces, uvs, origin).

    With `radius`, an edge is split only where it crosses within that distance of `point`, measured in the
    plane; a triangle at that rim is split on one edge only and still spans the plane. The choice is made per
    edge, so the two faces on an edge always agree and no new vertex is left on a whole edge. New vertices lie
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
            if radius is not None and np.linalg.norm(across - (across @ n) * n) > radius:
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


def pieces(vertices, faces, cuts, welded=True):
    """A piece number per face: faces joined edge to edge, never across a cut.

    `cuts` holds (point, normal, limit). An edge lying on a cut plane within its limit separates. With
    `welded`, vertices at one position are one point; without, only faces that share vertex numbers join."""
    weld = mesh_ops.weld_ids(vertices, WELD) if welded else np.arange(len(vertices))
    on_cut = np.zeros((len(vertices), len(cuts)), bool)
    for column, (point, normal, limit) in enumerate(cuts):
        relative = vertices - point
        height = relative @ normal
        on_cut[:, column] = (np.abs(height) < WELD) & (np.linalg.norm(relative - height[:, None] * normal, axis=1) <= limit)
    start, end = faces, np.roll(faces, -1, axis=1)  # edge i of a face runs from its corner i to the next
    joins = ~(on_cut[start] & on_cut[end]).any(axis=2)
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
    such a piece is traced again without welding, which takes the two shells apart, and each votes alone."""
    vote = classify(vertices[faces].mean(axis=1), parts)
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    weight = np.linalg.norm(np.cross(b - a, c - a), axis=1)

    def choose(piece):
        _, piece = np.unique(piece, return_inverse=True)
        tally = np.zeros((piece.max() + 1, len(parts)))
        np.add.at(tally, (piece, vote), weight)
        total = tally.sum(axis=1)
        return tally.argmax(axis=1)[piece], ((total > 0) & (np.sort(tally, axis=1)[:, -2] >= RIVAL * total))[piece]

    owner, torn = choose(pieces(vertices, faces, cuts))
    if torn.any():
        owner = np.where(torn, choose(pieces(vertices, faces, cuts, welded=False))[0], owner)
    return owner


def round_origin(segments):
    """The points of the section's closed curves that run round the plane's point, as (n, 2); empty where none
    does. A curve left open by the mesh's own edge is not counted: it has no inside."""
    segments = np.asarray(segments, float).reshape(-1, 2, 2)
    if not len(segments):
        return np.zeros((0, 2))
    _, ids = np.unique(np.round(segments.reshape(-1, 2) / WELD).astype(np.int64), axis=0, return_inverse=True)
    ids = ids.reshape(-1, 2)
    curve = mesh_ops.union_find(int(ids.max()) + 1, ids.tolist())[ids[:, 0]]
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


def sleeve(vertices, faces, joints, side):
    """Where a sleeve is cut from the torso it is fused with, or None where the arm is a surface of its own.

    The sleeve and the torso of a generated outfit are one surface from the shoulder down to the armpit. That
    is below the shoulder plane, which therefore cannot part them. The seam is a second plane, along the arm
    and facing the torso, where a shirt's sleeve is sewn on. It stands just inside the sleeve's inner side,
    taken where the sleeve is widest between the armpit and the elbow, so that it never cuts the sleeve itself,
    and it runs down to the elbow, so that it also cuts a stray bridge from the upper arm to the flank.
    Returns its `point`, `normal` and `radius`, the `depth` of the armpit below the shoulder plane, and the
    `reach` the shoulder plane needs to cut the sleeve's own side of the seam. Both cuts run a few centimetres
    past where they meet: a cut stops at whole edges, and a triangle left spanning one plane at its rim would
    join the two sides again."""
    start, end = (np.asarray(joints[side + name], float) for name in ('bicep_g', 'forearm_g'))
    other = np.asarray(joints[('r' if side == 'l' else 'l') + 'bicep_g'], float)
    length = float(np.linalg.norm(end - start))
    axis = seams.unit(end - start)
    inward = other - start
    inward = seams.unit(inward - (inward @ axis) * axis)
    u, v = seams.frame(axis)
    toward, along = np.array([inward @ u, inward @ v]), np.array([-(inward @ v), inward @ u])
    fused, clear, armpit = [], [], None
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
            clear.append(points)
    if not fused:
        return None
    require(clear, f'The {side} sleeve is one surface with the torso down to the elbow')
    seam = float(max((points @ toward).max() for points in clear)) + SLEEVE_ROOM
    own = np.concatenate(fused + clear)
    own = own[own @ toward <= seam]
    top = fused[0][fused[0] @ toward <= seam]
    return {'point': start + seam * inward + length / 2 * axis, 'normal': inward, 'depth': float(armpit),
            'radius': float(np.hypot(length / 2 + 3 * SLEEVE_STEP, np.abs(own @ along).max() + 3 * SLEEVE_STEP)),
            'reach': float(np.linalg.norm(top, axis=1).max()) + 3 * SLEEVE_STEP}


def seam_fill(vertices, uvs, faces, base, seam, facing):
    """Faces that close a part's opening on a sleeve seam: (vertices, uvs, faces) to add, numbered from `base`.

    The part's edges on the seam plane, each on one face only, run from the shoulder plane down round the
    armpit and back up. Each such line is closed with a fan from the middle between its two ends, which lies
    on the shoulder plane: the sleeve's rim there is then a closed curve again, which its cap grows from.
    `facing` is +1 for the sleeve, whose fan faces the torso, and -1 for the chest."""
    relative = vertices - seam['point']
    height = relative @ seam['normal']
    on = (np.abs(height) < WELD) & (np.linalg.norm(relative - height[:, None] * seam['normal'], axis=1) <= seam['radius'])
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.sort(edges[on[edges].all(axis=1)], axis=1)
    if len(edges):
        edges, count = np.unique(edges, axis=0, return_counts=True)
        edges = edges[count == 1]
    new_v, new_t, new_f = [], [], []
    if len(edges):
        line = mesh_ops.union_find(len(vertices), edges.tolist())
        for label in np.unique(line[edges[:, 0]]):
            mine = edges[line[edges[:, 0]] == label]
            points, uses = np.unique(mine, return_counts=True)
            ends = points[uses == 1]
            centre = vertices[ends].mean(axis=0) if len(ends) == 2 else vertices[points].mean(axis=0)
            hub = base + len(new_v)
            new_v.append(centre); new_t.append(uvs[points].mean(axis=0))
            for a, b in mine.tolist():
                normal = np.cross(vertices[a] - centre, vertices[b] - centre)
                new_f.append((hub, a, b) if facing * (normal @ seam['normal']) > 0 else (hub, b, a))
    return np.array(new_v).reshape(-1, 3), np.array(new_t).reshape(-1, uvs.shape[1]), np.array(new_f, int).reshape(-1, 3)


def compact(vertices, faces, uvs):
    """(vertices, faces, uvs) holding only the vertices the faces use."""
    used = np.unique(faces)
    remap = np.full(len(vertices), -1, int); remap[used] = np.arange(len(used))
    return vertices[used], remap[faces], uvs[used]


def cap(vertices, uvs, faces, base, point, normal, depth, limit, steps=CAP_STEPS, lean=LEAN):
    """A rounded end past the joint plane for an under part: (vertices, uvs, faces) to add to it.

    `faces` are the part's faces. Its rim is the edges it has on the plane within `limit`, each on one face
    only, that face on the under side. Every rim point is carried past the plane on a dome about the joint
    centre, in `steps` rings; the new vertices are numbered from `base`. The dome is `depth` deep, but at no
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
    index = np.concatenate([rim[None], base + np.arange(steps * len(rim)).reshape(steps, len(rim))])  # [ring, rim point]
    a, b = slot[edges[:, 0]], slot[edges[:, 1]]  # the part's face runs a to b, so the cap's runs b to a
    near, far = index[:-1], index[1:]
    added = np.concatenate([np.stack([near[:, b], near[:, a], far[:, a]], axis=2), np.stack([near[:, b], far[:, a], far[:, b]], axis=2)])
    return np.concatenate(rings), np.tile(uvs[rim], (steps, 1)), added.reshape(-1, 3)


def assign(vertices, faces, uvs, joints, radii, reach=REACH, reaches=None):
    """The mesh cut on every plane, and the part each face goes to.

    Returns (vertices, faces, uvs, owner, names, origin, cuts, sleeves): `owner[i]` indexes `names`, `origin[i]`
    is the face of the mesh given that face i was cut from, `cuts` maps (joint, side) to its plane, and
    `sleeves` maps a side to the sleeve seam cut there (`sleeve`)."""
    v, f, t = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    require(len(v) == len(t), 'One texture coordinate per vertex is required')
    require(len(f), 'The mesh has no faces')
    cuts = planes(joints)
    require(set(radii) == set(cuts), 'A radius is required for every joint and side')
    left, right = np.asarray(joints['lthigh_g'], float), np.asarray(joints['rthigh_g'], float)
    up = seams.unit(np.asarray(joints['neck_g'], float) - np.asarray(joints['torso_g'], float))
    require(up[2] > 0.8 and seams.unit(np.cross(up, right - left))[1] > 0.8, 'The joints must stand z up and face +y, as the bodies do')
    # A sleeve fused with the torso is cut off along the arm as well; the shoulder plane then reaches only as far
    # as the sleeve's own side of that seam, unless the caller says how far.
    sleeves = {side: found for side, found in ((side, sleeve(v, f, joints, side)) for side in 'lr') if found is not None}
    reaches = {**{('shoulder', side): found['reach'] for side, found in sleeves.items()}, **(reaches or {})}
    limit = limits(radii, reach, reaches)
    origin = np.arange(len(f))
    for key, (point, normal) in cuts.items():
        v, f, t, o = cut(v, f, t, point, normal, limit[key])
        origin = origin[o]
    # Trousers join the legs at the crotch, below both hip planes: without a cut between the legs there, the
    # two thighs would be one piece. The cut runs between the hip joints, as far as the hip planes reach.
    between = ((left + right) / 2, seams.unit(right - left), max(limit[('hip', 'l')], limit[('hip', 'r')]))
    v, f, t, o = cut(v, f, t, *between)
    origin = origin[o]
    walls = [(found['point'], found['normal'], found['radius']) for found in sleeves.values()]
    for wall in walls:
        v, f, t, o = cut(v, f, t, *wall)
        origin = origin[o]
    parts = regions(joints, radii, reach, reaches)
    owner = owners(v, f, parts, [(point, seams.unit(normal), limit[key]) for key, (point, normal) in cuts.items()] + [between] + walls)
    return v, f, t, owner, list(parts), origin, cuts, sleeves


def split(vertices, faces, uvs, joints, radii, overlaps=None, reach=REACH, reaches=None):
    """{token: (vertices, faces, uvs)} for one outfit mesh.

    `joints` maps bone names to positions in the mesh's space. `radii` maps (joint, side) to the radius of the
    joint there (the largest of the body ring plus the part's tier room); a plane cuts within `reach` times
    it, or within the distance `reaches` gives for that joint and side. `overlaps` maps (joint, side) to how deep the under part's cap runs past the plane under the over
    part; a joint without one gets no cap. Parts with no faces are left out."""
    overlaps = overlaps or {}
    require(all(key[0] in seams.JOINTS and key[1] in seams.sides(key[0]) for key in overlaps)
            and all((depth or 0) >= 0 for depth in overlaps.values()), 'Overlaps are depths of zero or more, by joint and side')
    v, f, t, owner, names, _, cuts, sleeves = assign(vertices, faces, uvs, joints, radii, reach, reaches)
    limit = limits(radii, reach, {**{('shoulder', side): found['reach'] for side, found in sleeves.items()}, **(reaches or {})})
    result = {}
    for index, name in enumerate(names):
        mine = f[owner == index]
        if not len(mine):
            continue
        pv, pf, pt = v, mine, t
        for side, found in sleeves.items():  # close the sleeve seam first: the sleeve's cap grows from the closed rim
            facing = 1.0 if name == token('bicep', side) else -1.0 if name == 'chest' else 0.0
            if facing:
                more = seam_fill(pv, pt, pf, len(pv), found, facing)
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
        for (joint, side), depth in overlaps.items():
            if depth and token(seams.JOINTS[joint]['under'], side) == name:
                point, normal = cuts[(joint, side)]
                more = cap(pv, pt, pf, len(pv), point, seams.unit(normal), depth, limit[(joint, side)])
                pv, pt, pf = np.concatenate([pv, more[0]]), np.concatenate([pt, more[1]]), np.concatenate([pf, more[2]])
        result[name] = compact(pv, pf, pt)
    return result
