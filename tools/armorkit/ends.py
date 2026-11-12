"""Each end of a cut outfit brought to its tier's envelope on its joint plane (docs/armorkit/seam-contract.md).

The contract asks an under end to stand inside the tier's envelope at the plane and an over end to stand at
least as far out, so that parts of different outfits mix. Cut from one surface, the two ends of an outfit's
seam are one ring, which stands wherever the outfit did: on the first worn outfit from 0 to 6 cm off the body.
Both ends are moved onto the envelope from either side, the under end `MARGIN` inside it and the over end
`MARGIN` outside it, and each blends back into its part over half the part's run on that side of the plane,
`LONGEST` at most: one slope from the outfit's own shape to the envelope's and back, with no ledge at the join
(the repository's no-shelves rule). Only the joints whose ends are both tubes round the limb are shaped
(`TUBES`); at the shoulders and hips the cut leaves the armpit and the wall between the legs on the plane.

Each vertex moves straight out from or in toward the joint's axis, by what its direction about the axis asks.
The end's ring at the plane is mapped onto the envelope's: an end wider than it is drawn in, what lies between
the body and the ring closing up in proportion and nothing pressed inside the body ring; an end narrower is
spread out, in proportion inside the ring. What stands outside the ring (a pad below the plane) keeps its
height over it. A pad over the joint is no part of the ring and rides with the cloth round it.

The split shapes a part's ends after its closings and lids and before its caps (`shaper`, `split.split`'s
`shape`), so that each cap grows from its shaped rim: a cap moved with the rim came out through the over part
where that part was its own shape again. At these joints the cap runs the contract's whole overlap deep
(`split.split`'s `deep`), `DEEPER` more, where it stopped as deep as its rim was wide.
"""
import numpy as np

from . import registry, seams

TUBES = ('elbow', 'wrist', 'waist', 'knee', 'ankle')  # joints whose two ends are tubes round the limb on the plane
MARGIN = 0.0005  # an under end stands this far inside the envelope, an over end this far outside it
PLATEAU = 0.012  # the end stands on the envelope this far from the plane before it blends back into the part
LONGEST = 0.12  # an end blends back over half the part's run on its side of the plane, and no farther than this
DEEPER = 0.005  # a cap at a tube joint runs this much deeper than the overlap: its surface is read in steps near the pole
BINS = 64  # directions about the axis the end's ring is read in
FAR = 1.3  # what stands this many times farther from the axis than the ring and the envelope moves less, the farther the less
STEP = 0.002  # the plane section is sampled this densely
PASSES = 2  # an end is read and moved again this many times
WIDEST = np.radians(45.0)  # an edge of the ring is taken to span this much at most when the margin is set
NEAR = 0.8  # an edge of the sections makes the ring when it stands this near it (an under end) or no farther than this inside out (an over end)
BAND = {True: (0.0002, 0.001, 0.005), False: (-0.0002, -0.001, -0.005, -0.01)}  # where an end's ring is read, from the plane toward
# the under part: an under part's own surface ends on the plane (only its cap crosses it), and an over end is read over the plateau


def _sampled(vertices, faces, point, normal):
    """In-plane points of the section, no more than `STEP` apart."""
    points = []
    for start, end in seams.section(vertices, faces, point, normal):
        count = max(2, int(np.linalg.norm(end - start) / STEP) + 2)
        points.append(start + np.linspace(0, 1, count)[:, None] * (end - start))
    return np.concatenate(points) if points else np.zeros((0, 2))


def _around(values, angles):
    """Values given at the centres of len(values) equal directions, read at `angles` along straight lines."""
    count = len(values)
    x = np.asarray(angles) / (2 * np.pi / count) - 0.5
    low = np.floor(x).astype(int)
    t = x - low
    return values[low % count] * (1 - t) + values[(low + 1) % count] * t


def ring(vertices, faces, point, normal, under):
    """The end's ring at the plane in `BINS` directions: its widest (an under end) or nearest (an over end) radius
    over the sections `BAND` lists, kept as wide or as near across each pair of neighbouring directions, so that
    read between them it still holds every point of the sections; directions it has no point in are read across
    from the nearest that do. None when the faces do not reach the plane."""
    normal = seams.unit(normal)
    points = np.concatenate([_sampled(vertices, faces, point + offset * normal, normal) for offset in BAND[under]])
    if not len(points):
        return None
    angle = np.arctan2(points[:, 1], points[:, 0]) % (2 * np.pi)
    radius = np.linalg.norm(points, axis=1)
    found = np.full(BINS, np.nan)
    at = np.floor(angle / (2 * np.pi / BINS)).astype(int) % BINS
    for k in np.unique(at):
        found[k] = radius[at == k].max() if under else radius[at == k].min()
    have = np.flatnonzero(~np.isnan(found))
    if len(have) < BINS:  # across the gaps, round the circle
        found = np.interp(np.arange(BINS), np.concatenate([have - BINS, have, have + BINS]), np.tile(found[have], 3))
    pick = np.maximum if under else np.minimum
    return pick(pick(np.roll(found, 1), found), np.roll(found, -1))


def spread(vertices, faces, point, normal, under, rim):
    """Per direction of `ring`, the widest angle about the axis an edge of the end's ring spans there in its
    sections: an edge between two points on the envelope cuts across inside it (or bulges out of it where it
    is hollow) by more the more it spans. Only the edges that make the ring count, not a closing across the
    inside of it."""
    normal = seams.unit(normal)
    widest = np.zeros(BINS)
    width = 2 * np.pi / BINS
    for offset in BAND[under]:
        segments = seams.section(vertices, faces, point + offset * normal, normal)
        if not len(segments):
            continue
        radius = np.linalg.norm(segments, axis=2)
        angle = np.arctan2(segments[:, :, 1], segments[:, :, 0]) % (2 * np.pi)
        turn = (angle[:, 1] - angle[:, 0] + np.pi) % (2 * np.pi) - np.pi
        near = _around(rim, (angle[:, 0] + turn / 2) % (2 * np.pi))
        keep = radius.min(axis=1) >= NEAR * near if under else radius.max(axis=1) <= near / NEAR
        for first, turned in zip(angle[keep, 0], turn[keep]):
            low, high = sorted((first, first + turned))
            covered = np.arange(int(np.floor(low / width)), int(np.floor(high / width)) + 1) % BINS
            widest[covered] = np.maximum(widest[covered], abs(turned))
    return np.maximum(np.maximum(np.roll(widest, 1), widest), np.roll(widest, -1))


def target(envelope, angles, under, margin=MARGIN, span=None):
    """The envelope at `angles`, read straight from one of its 16 directions' radius to the next as the gate reads
    it (`seams.around`), `margin` inside it for an under end and outside it for an over end, and as much again as
    an edge of the ring spanning `span` (per direction of `ring`, from `spread`) cuts across or bulges out."""
    value = seams.around(envelope, angles)
    sag = 0.0 if span is None else 1 - np.cos(np.minimum(span[np.floor(np.asarray(angles) / (2 * np.pi / BINS)).astype(int) % BINS], WIDEST) / 2)
    return value * (1 - sag) - margin if under else value * (1 + sag) + margin


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def end(vertices, point, normal, rim, envelope, body_ring, under, length, span=None, whole=None):
    """The vertices of a part with its end at one joint plane brought to the envelope. `rim` is the end's
    `ring`, `envelope` and `body_ring` the contract's 16 directions, `under` whether the part lies on the
    normal's side of the plane, `length` how far from the plane it blends back into the part; what it has past
    the plane moves whole, and so do the vertices `whole` flags. `span` is the end's `spread`."""
    vertices = np.asarray(vertices, float)
    normal = seams.unit(normal)
    u, v = seams.frame(normal)
    relative = vertices - point
    height = relative @ normal
    radial = relative - height[:, None] * normal
    r = np.linalg.norm(radial, axis=1)
    angle = np.arctan2(radial @ v, radial @ u) % (2 * np.pi)
    R, T = _around(rim, angle), target(envelope, angle, under, span=span)
    body = np.minimum(_around(np.asarray(body_ring, float), angle), T)  # nothing is drawn in past the body ring
    grown = r * T / R
    drawn = np.where(r <= body, r, body + (r - body) * (T - body) / np.maximum(R - body, 1e-9))
    new = np.where(r >= R, r + (T - R), np.where(T >= R, grown, drawn))
    reach = height if under else -height
    along = 1.0 - smooth((reach - PLATEAU) / max(length - PLATEAU, 1e-6))
    if whole is not None:
        along = np.where(whole, 1.0, along)
    outer = FAR * np.maximum(R, T)
    across = 1.0 - smooth((r - outer) / np.maximum(outer, 2 * np.abs(T - R)))
    final = r + along * across * (new - r)
    scale = np.where(r > 1e-9, final / np.maximum(r, 1e-9), 1.0)
    return point + height[:, None] * normal + radial * scale[:, None]


def normals(vertices, faces):
    """Area-weighted vertex normals."""
    corners = np.asarray(vertices, float)[faces]
    cross = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    out = np.zeros((len(vertices), 3))
    for k in range(3):
        np.add.at(out, faces[:, k], cross)
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def ends_of(name, bones, contract, body, tier, joints=TUBES):
    """[(point, normal, envelope, body ring, under)] for each end part `name` has at `joints`."""
    found = []
    for joint in joints:
        spec = seams.JOINTS[joint]
        for side in seams.sides(joint):
            letter, paired = ('l', None) if side == 'c' else (side, side)
            for key in ('under', 'over'):
                tokens = registry.SLOTS[spec[key]]['tokens']
                if name == (tokens[0] if len(tokens) == 1 else tokens['lr'.index(letter)]):
                    point, normal = seams.plane(bones, joint, letter)
                    envelope = np.asarray(seams.envelope(contract, joint, body, tier, paired), float)
                    found.append((point, seams.unit(normal), envelope, envelope - contract['tierOffsets'][str(tier)], key == 'under'))
    return found


def shaped(vertices, faces, measured, part_ends):
    """`vertices` with the part's ends (`ends_of`) brought to the envelope, its ring read from the faces
    `measured` flags. An end whose faces do not reach its plane is left as it is."""
    vertices = np.asarray(vertices, float)
    faces = np.asarray(faces, int)
    mine = faces[np.asarray(measured, bool)]
    for point, normal, envelope, body_ring, under in part_ends:
        reach = (vertices - point) @ normal * (1 if under else -1)
        length = min(LONGEST, 0.5 * float(reach[np.unique(faces)].max()))
        band = np.abs(np.asarray(BAND[under]))
        crossed = (reach[mine].min(axis=1) <= band.max()) & (reach[mine].max(axis=1) >= band.min())
        whole = np.zeros(len(vertices), bool)
        whole[mine[crossed]] = True  # every corner of a face the sections pass through: an edge to a corner moved less sagged into the section
        for _ in range(PASSES):
            rim = ring(vertices, mine, point, normal, under)
            if rim is None:
                break
            vertices = end(vertices, point, normal, rim, envelope, body_ring, under, length, spread(vertices, mine, point, normal, under, rim), whole)
    return vertices


def shaper(bones, contract, body, tier, pads=None, joints=TUBES):
    """The hook `split.split` calls on each part before its caps (`shape`): the part's ends at `joints` brought
    to tier `tier`'s envelope on body `body`, and the vertex normals the first three columns carry turned as the
    surface turned. `pads` maps (joint, side) to the flags of a pad's faces on the outfit (`split.guard`); a
    pad's faces are no part of a ring, and every other face is, the closings the split made included."""
    flags = [np.asarray(found, bool) for found in (pads or {}).values()]

    def shape(name, vertices, faces, columns, origin):
        part_ends = ends_of(name, bones, contract, body, tier, joints)
        if not part_ends:
            return vertices, columns
        faces = np.asarray(faces, int)
        used, local = np.unique(faces, return_inverse=True)
        local = local.reshape(-1, 3)
        held = np.ones(len(faces), bool)  # what the seam gate reads: all but a pad's own faces
        for found in flags:
            held[:len(origin)] &= ~found[np.asarray(origin, int)]
        before = np.asarray(vertices, float)[used]
        after = shaped(before, local, held, part_ends)
        vertices, columns = np.array(vertices, float), np.array(columns, float)
        vertices[used] = after
        turned = columns[used, :3] + normals(after, local) - normals(before, local)
        columns[used, :3] = turned / np.maximum(np.linalg.norm(turned, axis=1, keepdims=True), 1e-12)
        return vertices, columns
    return shape
