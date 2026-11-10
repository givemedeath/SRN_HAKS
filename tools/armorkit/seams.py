"""The seam contract: where rigid parts meet, which one lies over the other, and how much room each tier gets.

Parts meet at eight joints. Each joint has a fixed plane through the child bone, a fixed layering order
(the part nearer the torso lies over the other; the chest lies over everything it touches) and, per
tier, an envelope around the body's own ring at that plane plus a minimum overlap for the under end
(docs/armorkit/plan.md, "Seam rules"). The numbers are measured on the locked Human Fit bodies by
`measure` and frozen in seam-contract.json; `load_contract` and `mixes` are what the gates use.
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
TIER_OFFSETS = {0: 0.004, 1: 0.012, 2: 0.025, 3: 0.05}
# joint: over slot, under slot, bone at the joint centre, the two bones whose line is the plane normal
# (pointing from the over part into the under part), and the bone whose rotation opens the seam.
# Paired joints are measured on the left side; `{}` takes the side letter.
JOINTS = {
    'neck': {'over': 'chest', 'under': 'neck', 'centre': 'neck_g', 'axis': None, 'normal': (0.0, 0.0, 1.0), 'moving': 'neck_g'},
    'shoulder': {'over': 'chest', 'under': 'bicep', 'centre': '{}bicep_g', 'axis': ('{}bicep_g', '{}forearm_g'), 'moving': '{}bicep_g'},
    'elbow': {'over': 'bicep', 'under': 'forearm', 'centre': '{}forearm_g', 'axis': ('{}bicep_g', '{}forearm_g'), 'moving': '{}forearm_g'},
    'wrist': {'over': 'forearm', 'under': 'hand', 'centre': '{}hand_g', 'axis': ('{}forearm_g', '{}hand_g'), 'moving': '{}hand_g'},
    'waist': {'over': 'chest', 'under': 'pelvis', 'centre': 'torso_g', 'axis': None, 'normal': (0.0, 0.0, -1.0), 'moving': 'torso_g'},
    'hip': {'over': 'pelvis', 'under': 'thigh', 'centre': '{}thigh_g', 'axis': ('{}thigh_g', '{}shin_g'), 'moving': '{}thigh_g'},
    'knee': {'over': 'thigh', 'under': 'shin', 'centre': '{}shin_g', 'axis': ('{}thigh_g', '{}shin_g'), 'moving': '{}shin_g'},
    'ankle': {'over': 'shin', 'under': 'foot', 'centre': '{}foot_g', 'axis': ('{}shin_g', '{}foot_g'), 'moving': '{}foot_g'},
}
BONES = {'neck': 'neck_g', 'chest': 'torso_g', 'pelvis': 'pelvis_g', 'bicepl': 'lbicep_g', 'bicepr': 'rbicep_g',
         'forel': 'lforearm_g', 'forer': 'rforearm_g', 'handl': 'lhand_g', 'handr': 'rhand_g', 'legl': 'lthigh_g',
         'legr': 'rthigh_g', 'shinl': 'lshin_g', 'shinr': 'rshin_g', 'footl': 'lfoot_g', 'footr': 'rfoot_g',
         'belt': 'belt_g', 'shol': 'lshoulder_g', 'shor': 'rshoulder_g'}


def unit(vector):
    vector = np.asarray(vector, float)
    length = np.linalg.norm(vector)
    require(length > 1e-9, 'Zero-length joint axis')
    return vector / length


def frame(normal):
    """Two in-plane unit axes for a plane normal: u as close to body left-right (X) as the plane allows, v = n x u."""
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
    for start, end in np.asarray(segments, float).reshape(-1, 2, 2):
        count = max(2, int(np.linalg.norm(end - start) / step) + 2)
        points = start + np.linspace(0, 1, count)[:, None] * (end - start)
        distance = np.linalg.norm(points, axis=1)
        keep = distance <= limit if limit is not None else np.ones(count, bool)
        np.maximum.at(radii, sectors(points, directions)[keep], distance[keep])
    return radii


def extent(vertices, point, normal):
    """Signed range of the mesh along the normal, measured from the plane."""
    height = (np.asarray(vertices, float) - point) @ unit(normal)
    return float(height.min()), float(height.max())


def rotation(matrix):
    """The rotation part of a 4x4 world matrix with any uniform scale removed."""
    block = np.asarray(matrix, float)[:3, :3]
    return block / np.cbrt(np.linalg.det(block))


def swing(rest, pose, bone, reference, normal):
    """Degrees the under part's axis has swung away from the over part since the bind pose.

    `normal` is the joint plane normal in the bind pose; it rides on `bone` and is compared in the
    frame of `reference` (the bone carrying the over part). Twist about the axis is left out: it
    turns the under end inside the over end without opening the seam."""
    normal = unit(normal)
    before = rotation(rest[reference]).T @ normal
    after = rotation(pose[reference]).T @ rotation(pose[bone]) @ rotation(rest[bone]).T @ normal
    return math.degrees(math.acos(float(np.clip(before @ after, -1, 1))))


def minimum_overlap(radius, degrees):
    """How far an under end of this radius must continue past the plane so the bend never opens a gap.

    A point on the under end's rim at the plane drops below the plane's far side by radius*tan(angle)
    when the joint turns; past 45 degrees a rounded cap one radius deep covers every angle."""
    return radius * min(1.0, math.tan(math.radians(min(degrees, 89.0))))


def validate_contract(data):
    require(isinstance(data, dict) and data.get('schemaVersion') == 1 and data.get('kind') == KIND, 'Unsupported seam contract')
    require(set(data['joints']) == set(registry.JOINTS), 'The contract covers exactly the eight joints')
    require(sorted(data['tierOffsets']) == [str(t) for t in registry.TIERS], 'Tier offsets for tiers 0-3 required')
    offsets = [data['tierOffsets'][str(t)] for t in registry.TIERS]
    require(offsets[0] >= 0 and all(a < b for a, b in zip(offsets, offsets[1:])), 'Tier offsets must grow with the tier')
    for name, joint in data['joints'].items():
        spec = JOINTS[name]
        require((joint['over'], joint['under']) == (spec['over'], spec['under']), name + ': layering order differs from the kit')
        require(set(joint['bodies']) == {'pmh0', 'pfh0'}, name + ': measured on both Human Fit bodies')
        for body, row in joint['bodies'].items():
            label = f'{name} {body}'
            require(abs(np.linalg.norm(row['normal']) - 1) < 1e-4 and len(row['point']) == 3, label + ': plane needs a point and a unit normal')
            require(len(row['bodyRing']) == DIRECTIONS and min(row['bodyRing']) > 0, label + ': body ring needs a radius in every direction')
            require(set(row['tiers']) == {str(t) for t in registry.TIERS}, label + ': tiers 0-3 required')
            previous = None
            for tier in registry.TIERS:
                values = row['tiers'][str(tier)]
                require(values['envelopeRadius'] > 0 and values['minimumOverlap'] > 0, label + ': positive envelope and overlap required')
                require(previous is None or (values['envelopeRadius'] > previous['envelopeRadius']
                                             and values['minimumOverlap'] >= previous['minimumOverlap']),
                        label + ': envelopes and overlaps must not shrink as the tier rises')
                previous = values
    return data


def load_contract(path=CONTRACT):
    with Path(path).open(encoding='utf-8') as stream:
        return validate_contract(json.load(stream))


def envelope(contract, joint, body, tier):
    """Per-direction envelope radii of a tier at a joint: the body's ring pushed out by the tier's offset."""
    row = contract['joints'][joint]['bodies'][body]
    return [radius + contract['tierOffsets'][str(tier)] for radius in row['bodyRing']]


def mixes(over_part, under_part, joint):
    """True when the two parts mix cleanly at the joint: the over part's tier is at least the under part's.

    Parts that do not both end at the joint in the contract's order have no seam there and return None."""
    spec = JOINTS[joint]
    if over_part['slot'] != spec['over'] or under_part['slot'] != spec['under']:
        return None
    if joint not in over_part['tiers'] or joint not in under_part['tiers']:
        return None
    return over_part['tiers'][joint] >= under_part['tiers'][joint]
