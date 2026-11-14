"""The seam contract: where rigid parts meet, which one lies over the other, and how much room each tier gets.

Parts meet at eight joints. Each joint has a fixed plane through a bone at the joint, a fixed layering
order (the part nearer the torso lies over the other; the chest lies over everything it touches) and,
per tier, an envelope around the body's own ring at that plane plus a minimum overlap for the under end
(docs/armorkit/plan.md, "Seam rules"). The numbers are measured on the locked Human Fit bodies by
`measure` and frozen in seam-contract.json; `load_contract`, `envelope`, `overlap` and `mixes` are what
the gates use.
"""
import json
import math
from pathlib import Path

import numpy as np

from . import registry
from .registry import require

CONTRACT = Path(__file__).with_name('seam-contract.json')
KIND = 'srn-armorkit-seam-contract'
DIRECTIONS = 16
# Room each tier gets outside the body's ring, in metres: skin-tight, cloth, padded or armored, heavy.
# Stock Human clothing sits 0-1 cm off the body at the joints, flared cuffs and boots 3-7 cm (seam-contract.md).
# These are what `measure` writes into a new contract; a frozen contract carries its own `tierOffsets`.
TIER_OFFSETS = {0: 0.004, 1: 0.012, 2: 0.025, 3: 0.05}
DESIGN_BENDS = ('p95', 'p99', 'max')  # the swing statistic a contract may build its minimum overlap on
AUTHORING_BODIES = ('pmh0', 'pfh0')  # every contract holds at least these
TOLERANCE = 0.0005  # stored tier numbers may differ this much from their recomputed value (inputs are rounded)
# How every end is closed (version 3, user decision 2026-11-13: every joint at least slightly domed, so the parts
# overlap as they turn and the engine's depth test hides whichever surface lies behind). An over part's opening on
# its joint's plane is closed by a dome on past it into the under part, its pole `domeDepth` of the opening's mean
# distance from its axis past it and `domeMost` metres at most, in `domeRings` rings; an under end runs on past the
# plane by the tier's minimum overlap, rounded in to its axis. What the split adds to an under end lies no more than
# `rest` metres outside the outfit as the body stands, and no more than `bent` outside the over part with the under
# part turned by the design bend (`bake.hidden`): Facility Security male, which the user saw clean in the client
# with every end domed, stands up to 0.7 cm out turned (its left hip and shoulder, 2026-11-13). These are what `measure`
# writes into a new contract; a frozen contract carries its own `ends`.
ENDS = {'domeDepth': 0.3, 'domeMost': 0.02, 'domeRings': 6, 'rest': 0.005, 'bent': 0.01}
# joint: over slot, under slot, bone at the joint centre, and the two bones whose line is the plane normal
# (pointing from the over part into the under part). `{}` takes the side letter of a paired joint.
JOINTS = {
    'neck': {'over': 'chest', 'under': 'neck', 'centre': 'neck_g', 'axis': None, 'normal': (0.0, 0.0, 1.0)},
    'shoulder': {'over': 'chest', 'under': 'bicep', 'centre': '{}bicep_g', 'axis': ('{}bicep_g', '{}forearm_g')},
    'elbow': {'over': 'bicep', 'under': 'forearm', 'centre': '{}forearm_g', 'axis': ('{}bicep_g', '{}forearm_g')},
    'wrist': {'over': 'forearm', 'under': 'hand', 'centre': '{}hand_g', 'axis': ('{}forearm_g', '{}hand_g')},
    'waist': {'over': 'chest', 'under': 'pelvis', 'centre': 'torso_g', 'axis': None, 'normal': (0.0, 0.0, -1.0)},
    'hip': {'over': 'pelvis', 'under': 'thigh', 'centre': '{}thigh_g', 'axis': ('{}thigh_g', '{}shin_g')},
    'knee': {'over': 'thigh', 'under': 'shin', 'centre': '{}shin_g', 'axis': ('{}thigh_g', '{}shin_g')},
    'ankle': {'over': 'shin', 'under': 'foot', 'centre': '{}foot_g', 'axis': ('{}shin_g', '{}foot_g')},
}
BONES = {'neck': 'neck_g', 'chest': 'torso_g', 'pelvis': 'pelvis_g', 'bicepl': 'lbicep_g', 'bicepr': 'rbicep_g',
         'forel': 'lforearm_g', 'forer': 'rforearm_g', 'handl': 'lhand_g', 'handr': 'rhand_g', 'legl': 'lthigh_g',
         'legr': 'rthigh_g', 'shinl': 'lshin_g', 'shinr': 'rshin_g', 'footl': 'lfoot_g', 'footr': 'rfoot_g',
         'belt': 'belt_g', 'shol': 'lshoulder_g', 'shor': 'rshoulder_g'}


def sides(joint):
    """The sides a joint is recorded on: left and right for a limb joint, `c` for the neck and waist."""
    return ('l', 'r') if '{}' in JOINTS[joint]['centre'] else ('c',)


def unit(vector):
    vector = np.asarray(vector, float)
    length = np.linalg.norm(vector)
    require(length > 1e-9, 'Zero-length joint axis')
    return vector / length


def frame(normal):
    """Two in-plane unit axes for a plane normal: u as close to body left-right (X) as the plane allows, v = n x u.

    The axes are in body space on both sides, so direction 0 of a right-side ring points the same way as
    direction 0 of a left-side ring; a right ring is the left ring mirrored, not the same list."""
    normal = unit(normal)
    u = np.array([1.0, 0.0, 0.0]) - normal[0] * normal
    if np.linalg.norm(u) < 0.2:
        u = np.array([0.0, 1.0, 0.0]) - normal[1] * normal
    u = unit(u)
    return u, np.cross(normal, u)


def plane(rig, joint, side='l'):
    """(point, normal) of a joint plane in the body's bind pose. `rig` maps bone name to its 4x4 world matrix."""
    spec = JOINTS[joint]
    point = rig[spec['centre'].format(side)][:3, 3]
    if spec['axis'] is None:
        return point, np.array(spec['normal'])
    a, b = (rig[name.format(side)][:3, 3] for name in spec['axis'])
    return point, unit(b - a)


def section(vertices, faces, point, normal):
    """Segments where the mesh's triangles cross the plane, as (n, 2, 2) in-plane coordinates about `point`."""
    u, v = frame(normal)
    relative = np.asarray(vertices, float) - point
    height = relative @ unit(normal)
    height = np.where(height == 0, 1e-12, height)  # a vertex on the plane counts as just past it
    faces = np.asarray(faces, int)
    h = height[faces]
    crossing = faces[(h.min(axis=1) < 0) & (h.max(axis=1) > 0)]
    if not len(crossing):
        return np.zeros((0, 2, 2))
    hit, points = [], []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        ha, hb = height[crossing[:, a]], height[crossing[:, b]]
        apart = ha * hb < 0  # the third edge of a crossing triangle lies on one side and is never used
        t = np.where(apart, ha / np.where(apart, ha - hb, 1.0), 0.0)
        on_edge = relative[crossing[:, a]] + t[:, None] * (relative[crossing[:, b]] - relative[crossing[:, a]])
        hit.append(ha * hb < 0)
        points.append(np.stack([on_edge @ u, on_edge @ v], axis=1))
    # Each crossing triangle has exactly two crossing edges; take them in edge order.
    order = np.argsort(~np.stack(hit, axis=1), axis=1, kind='stable')[:, :2]
    return np.stack(points, axis=1)[np.arange(len(crossing))[:, None], order]


def sectors(points, directions=DIRECTIONS):
    """The angular sector each in-plane point falls in, sector 0 centred on the first in-plane axis."""
    angle = np.arctan2(points[:, 1], points[:, 0]) % (2 * math.pi)
    return np.floor(angle / (2 * math.pi / directions) + 0.5).astype(int) % directions


def ring(segments, directions=DIRECTIONS, limit=None, step=0.002):
    """Largest radial distance of the section in each angular sector about the joint centre; 0 where it is absent.

    Segments are sampled every `step` metres so sparse meshes still fill their sectors; `limit` drops
    anything farther from the centre (the far side of a part the plane also cuts)."""
    radii = np.zeros(directions)
    for sector, distance, _ in _sampled(segments, directions, limit, step):
        np.maximum.at(radii, sector, distance)
    return radii


def around(values, angles):
    """A ring given in its directions (`ring`), read at `angles` straight from one direction's radius to the next."""
    values = np.asarray(values, float)
    x = (np.asarray(angles, float) % (2 * math.pi)) / (2 * math.pi / len(values))
    low = np.floor(x).astype(int)
    t = x - low
    return values[low % len(values)] * (1 - t) + values[(low + 1) % len(values)] * t


def standoff(segments, body_ring, limit=None, step=0.002):
    """Per direction, how far the section stands off the body ring read straight between its directions
    (`around`): (farthest, nearest), nan where the section has no point. Sampled and limited as `ring`."""
    count = len(body_ring)
    farthest, nearest = np.full(count, -np.inf), np.full(count, np.inf)
    for sector, distance, angle in _sampled(segments, count, limit, step):
        off = distance - around(body_ring, angle)
        np.maximum.at(farthest, sector, off)
        np.minimum.at(nearest, sector, off)
    return np.where(np.isinf(farthest), np.nan, farthest), np.where(np.isinf(nearest), np.nan, nearest)


def _sampled(segments, directions, limit, step):
    """Per segment: (sector, distance from the centre, angle) of points along it no more than `step` apart, within `limit`."""
    for start, end in np.asarray(segments, float).reshape(-1, 2, 2):
        count = max(2, int(np.linalg.norm(end - start) / step) + 2)
        points = start + np.linspace(0, 1, count)[:, None] * (end - start)
        distance = np.linalg.norm(points, axis=1)
        keep = distance <= limit if limit is not None else np.ones(count, bool)
        yield sectors(points, directions)[keep], distance[keep], np.arctan2(points[keep, 1], points[keep, 0])


def surface_points(vertices, faces, step):
    """Points on every triangle no more than `step` apart, vertices included.

    Binning vertices alone misses every cell a triangle crosses without a vertex in it."""
    corners = np.asarray(vertices, float)[np.asarray(faces, int)]
    longest = np.max(np.linalg.norm(corners - np.roll(corners, 1, axis=1), axis=2), axis=1)
    counts = np.maximum(1, np.ceil(longest / step).astype(int))
    points = [np.asarray(vertices, float)]
    for count in np.unique(counts):
        if count == 1:
            continue
        i, j = np.meshgrid(np.arange(count + 1), np.arange(count + 1), indexing='ij')
        inside = i + j <= count
        weights = np.stack([count - i[inside] - j[inside], i[inside], j[inside]], axis=1) / count
        points.append(np.einsum('mk,nkd->nmd', weights, corners[counts == count]).reshape(-1, 3))
    return np.concatenate(points)


def extent(vertices, point, normal):
    """Signed range of the mesh along the normal, measured from the plane."""
    height = (np.asarray(vertices, float) - point) @ unit(normal)
    return float(height.min()), float(height.max())


def rotation(matrix):
    """The rotation part of a 4x4 world matrix with any uniform scale removed."""
    block = np.asarray(matrix, float)[:3, :3]
    return block / np.cbrt(np.linalg.det(block))


def swing_terms(rest, bone, reference, normal):
    """The parts of a swing that do not change with the pose: the plane normal as the over part's bone
    sees it in the bind pose, and as the under part's bone carries it."""
    normal = unit(normal)
    return rotation(rest[reference]).T @ normal, rotation(rest[bone]).T @ normal


def swing_angle(before, carried, reference_rotation, bone_rotation):
    """Degrees between the bind-pose normal and the normal a posed bone carries, both in the reference bone's frame."""
    return math.degrees(math.acos(float(np.clip(before @ (reference_rotation.T @ bone_rotation @ carried), -1, 1))))


def swing(rest, pose, bone, reference, normal):
    """Degrees the under part's axis has swung away from the over part since the bind pose.

    `normal` is the joint plane normal in the bind pose; it rides on `bone` and is compared in the
    frame of `reference` (the bone carrying the over part). Twist about the axis is left out: it
    turns the under end inside the over end without opening the seam."""
    before, carried = swing_terms(rest, bone, reference, normal)
    return swing_angle(before, carried, rotation(pose[reference]), rotation(pose[bone]))


def minimum_overlap(radius, degrees):
    """How far an under end of this radius must continue past the plane so the bend never opens a gap.

    A point on the under end's rim at the plane drops below the plane's far side by radius*tan(angle)
    when the joint turns; past 45 degrees a rounded cap one radius deep covers every angle."""
    return radius * min(1.0, math.tan(math.radians(min(degrees, 89.0))))


def tier_values(rings, offset, degrees):
    """A tier's numbers at a joint, from the body rings of its sides, the tier's offset and the design swing.

    The envelope radius and the mean radius are those of the wider side, so one rule serves left and right."""
    mean = max(float(np.mean(ring)) for ring in rings) + offset
    return {'envelopeRadius': max(float(np.max(ring)) for ring in rings) + offset, 'meanRadius': mean,
            'minimumOverlap': minimum_overlap(mean, degrees)}


def validate_contract(data):
    require(isinstance(data, dict) and data.get('schemaVersion') == 1 and data.get('kind') == KIND, 'Unsupported seam contract')
    require(data.get('directions') == DIRECTIONS, f'The contract records {DIRECTIONS} directions')
    require(data.get('designBend') in DESIGN_BENDS, f'designBend must be one of {list(DESIGN_BENDS)}')
    require(set(data['joints']) == set(registry.JOINTS), 'The contract covers exactly the eight joints')
    require(sorted(data['tierOffsets']) == [str(t) for t in registry.TIERS], 'Tier offsets for tiers 0-3 required')
    offsets = [data['tierOffsets'][str(t)] for t in registry.TIERS]
    require(offsets[0] >= 0 and all(a < b for a, b in zip(offsets, offsets[1:])), 'Tier offsets must grow with the tier')
    ends = data.get('ends')
    require(isinstance(ends, dict) and set(ends) == set(ENDS), f'The contract says how every end is closed: {sorted(ENDS)}')
    require(0 < ends['domeDepth'] <= 1 and ends['domeMost'] > 0 and isinstance(ends['domeRings'], int) and ends['domeRings'] >= 1,
            'A dome stands past its opening, no deeper than the opening is wide, in one ring or more')
    require(ends['rest'] >= 0 and ends['bent'] >= 0, 'What the split adds is hidden within a tolerance of zero or more')
    for name, joint in data['joints'].items():
        spec = JOINTS[name]
        require((joint['over'], joint['under']) == (spec['over'], spec['under']), name + ': layering order differs from the kit')
        require(set(AUTHORING_BODIES) <= set(joint['bodies']) <= set(registry.BODIES),
                name + ': measured on both Human Fit bodies, and on SRN bodies only')
        for body, row in joint['bodies'].items():
            label = f'{name} {body}'
            require(set(row['sides']) == set(sides(name)), f'{label}: sides must be {list(sides(name))}')
            for side in row['sides'].values():
                require(abs(np.linalg.norm(side['normal']) - 1) < 1e-4 and len(side['point']) == 3, label + ': plane needs a point and a unit normal')
                require(len(side['bodyRing']) == DIRECTIONS and min(side['bodyRing']) > 0, label + ': body ring needs a radius in every direction')
            require(set(row['tiers']) == {str(t) for t in registry.TIERS}, label + ': tiers 0-3 required')
            rings = [side['bodyRing'] for side in row['sides'].values()]
            for tier, offset in zip(registry.TIERS, offsets):
                stored, wanted = row['tiers'][str(tier)], tier_values(rings, offset, row['bend'][data['designBend']])
                require(set(stored) == set(wanted) and all(abs(stored[key] - wanted[key]) <= TOLERANCE for key in wanted),
                        f'{label}: tier {tier} disagrees with the body ring, the tier offsets and the design bend')
    return data


def load_contract(path=CONTRACT):
    with Path(path).open(encoding='utf-8') as stream:
        return validate_contract(json.load(stream))


def envelope(contract, joint, body, tier, side=None):
    """Per-direction envelope radii of a tier at a joint: the body's ring pushed out by the tier's offset.

    A limb joint needs its side, `l` or `r`: the two rings are recorded separately, in body axes."""
    rows = contract['joints'][joint]['bodies'][body]['sides']
    side = 'c' if side is None and set(rows) == {'c'} else side
    require(side in rows, f'{joint}: side must be one of {sorted(rows)}')
    return [radius + contract['tierOffsets'][str(tier)] for radius in rows[side]['bodyRing']]


def overlap(contract, joint, body, tier):
    """How far an under end of this tier continues past the joint plane, at the least."""
    return contract['joints'][joint]['bodies'][body]['tiers'][str(tier)]['minimumOverlap']


def mixes(over_part, under_part, joint):
    """True when the two parts mix cleanly at the joint: the over part's tier is at least the under part's.

    Parts that do not both end at the joint in the contract's order have no seam there and return None."""
    spec = JOINTS[joint]
    if over_part['slot'] != spec['over'] or under_part['slot'] != spec['under']:
        return None
    if joint not in over_part['tiers'] or joint not in under_part['tiers']:
        return None
    return over_part['tiers'][joint] >= under_part['tiers'][joint]
