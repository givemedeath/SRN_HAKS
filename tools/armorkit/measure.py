"""Measure the seam contract and the head envelopes from published pack folders.

Reads binary models as the packs ship them (rigid parts through headkit's native reader, skeletons and
animation through PhenoMorpher's animation library). Nothing here edits a pack. Stock supermodels that
the packs do not carry are read from an explicit folder of extracted game models.
"""
import math
from pathlib import Path

import numpy as np

from tools.headkit import native_reader
from tools.phenomorpher.phenomorpher.engine import anim_library, native_motion

from . import registry, seams
from .registry import require

TOKENS = {'neck': 'neck', 'chest': 'chest', 'pelvis': 'pelvis', 'bicep': 'bicep{}', 'forearm': 'fore{}', 'hand': 'hand{}',
          'thigh': 'leg{}', 'shin': 'shin{}', 'foot': 'foot{}'}
GUARD = 0.01  # the rings are also taken 1 cm to each side of the plane, where a body part ends right on it
OVER_LIMIT = 1.6  # the over part's ring counts only this many under-ring radii from the centre
# Where a limb or the neck leaves the torso, the plane also cuts the torso itself, so only the limb's ring counts.
TORSO_OPENINGS = ('neck', 'shoulder', 'hip')
SLICE = 0.02


def rig(blob):
    """{bone: 4x4 world matrix} of a body model's bind pose."""
    return native_motion.sample(anim_library.load_model(None, blob)['nodes'])


def mesh(blob, name, world):
    """(vertices, faces) of a rigid part model, moved into body space by its bone's bind matrix."""
    meshes = native_reader.decode(blob, name, require_tangents=False, apply_rigid_transforms=True)
    offsets = np.cumsum([0] + [len(m['position']) for m in meshes])
    vertices = np.concatenate([m['position'] for m in meshes]) @ world[:3, :3].T + world[:3, 3]
    return vertices, np.concatenate([m['faces'].astype(int) + offset for m, offset in zip(meshes, offsets)])


def body(folder, name, number=1):
    """(rig, {model token: (vertices, faces)}) of one body from a pack folder."""
    folder = Path(folder)
    bones = rig((folder / (name + '.mdl')).read_bytes())
    parts = {}
    for token, bone in seams.BONES.items():
        path = folder / f'{registry.model_name(name, token, number)}.mdl'
        if path.is_file():
            parts[token] = mesh(path.read_bytes(), path.stem, bones[bone])
    return bones, parts


def part_ring(part, point, normal, offset=0.0, limit=None):
    vertices, faces = part
    return seams.ring(seams.section(vertices, faces, point + offset * seams.unit(normal), normal), limit=limit)


def joint_ring(parts, point, normal, joint, side='l'):
    """The body's own ring at a joint: both skin parts' sections at the plane and 1 cm to its two sides."""
    spec = seams.JOINTS[joint]
    under = parts[TOKENS[spec['under']].format(side)]
    over = parts[TOKENS[spec['over']].format(side)]
    inner = np.max([part_ring(under, point, normal, offset) for offset in (0.0, GUARD)], axis=0)
    if joint in TORSO_OPENINGS:
        return inner
    limit = OVER_LIMIT * inner.max()
    outer = np.max([part_ring(over, point, normal, offset, limit) for offset in (0.0, -GUARD)], axis=0)
    return np.maximum(inner, outer)


def joints(bones, parts):
    """Per joint: plane, body ring and how far each skin part runs past the plane (left side; right is mirrored)."""
    result = {}
    for joint, spec in seams.JOINTS.items():
        point, normal = seams.plane(bones, joint)
        ring = joint_ring(parts, point, normal, joint)
        require(ring.min() > 0, joint + ': the body ring has an empty direction')
        under = seams.extent(parts[TOKENS[spec['under']].format('l')][0], point, normal)
        over = seams.extent(parts[TOKENS[spec['over']].format('l')][0], point, normal)
        result[joint] = {'point': point, 'normal': normal, 'bodyRing': ring,
                         'underPastPlane': max(0.0, -under[0]), 'overPastPlane': max(0.0, over[1])}
    return result


def supermodels(base, folders):
    """The animation models a body inherits, nearest first; each is read from the first folder that has it."""
    name, chain = base['parent'], []
    while name and name.lower() != 'null':
        path = next((Path(folder) / (name + '.mdl') for folder in folders if (Path(folder) / (name + '.mdl')).is_file()), None)
        require(path is not None, 'Supermodel not found in the given folders: ' + name)
        model = anim_library.load_model(path)
        chain.append((name, model))
        name = model['parent']
    return chain


def bends(body_blob, folders):
    """Per joint: how far the under part swings from the bind pose across every inherited clip, in degrees."""
    base = anim_library.load_model(None, body_blob)
    rest = native_motion.sample(base['nodes'])
    samples = {joint: [] for joint in seams.JOINTS}
    worst = {joint: (0.0, '') for joint in seams.JOINTS}
    chain = supermodels(base, folders)
    for name, model in chain:
        for clip_name, clip in model['clips'].items():
            for time in native_motion.sample_times(clip):
                pose = native_motion.sample(base['nodes'], clip['nodes'], time)
                for joint, spec in seams.JOINTS.items():
                    for side in ('l', 'r') if '{}' in spec['centre'] else ('l',):
                        moving = seams.BONES[TOKENS[spec['under']].format(side)]
                        reference = seams.BONES[TOKENS[spec['over']].format(side)]
                        angle = seams.swing(rest, pose, moving, reference, seams.plane(rest, joint, side)[1])
                        samples[joint].append(angle)
                        if angle > worst[joint][0]:
                            worst[joint] = (angle, f'{name}:{clip_name}')
    return {'models': [name for name, _ in chain], 'clips': sum(len(model['clips']) for _, model in chain),
            'joints': {joint: {'max': worst[joint][0], 'maxClip': worst[joint][1],
                               'p99': float(np.percentile(samples[joint], 99)), 'p95': float(np.percentile(samples[joint], 95)),
                               'median': float(np.median(samples[joint]))} for joint in seams.JOINTS}}


def clearance(part, bones, parts, joint, side='l'):
    """Per direction, how far a worn part's ring stands outside the body ring at a joint; nan where it has none."""
    point, normal = seams.plane(bones, joint, side)
    base = joint_ring(parts, point, normal, joint, side)
    worn = np.max([part_ring(part, point, normal, offset, 3.0 * base.max()) for offset in (-GUARD, 0.0, GUARD)], axis=0)
    return np.where(worn > 0, worn - base, np.nan)


def head_envelope(folder, prefix, wanted=None):
    """Outer bounds of the published heads of one body prefix (all of them, or the `wanted` numbers), in the head bone's space.

    Returns the head numbers, the bounding box and, per 2 cm of height, the largest radius in 16
    directions about the vertical line through the box centre."""
    numbers, clouds = [], []
    for path in sorted(Path(folder).glob(prefix + '_head*.mdl')):
        number = int(path.stem.rsplit('head', 1)[1])
        if wanted is not None and number not in wanted:
            continue
        vertices, _ = mesh(path.read_bytes(), path.stem, np.eye(4))
        numbers.append(number)
        clouds.append(vertices)
    require(wanted is None or numbers == sorted(wanted), 'A recorded head is no longer published for ' + prefix)
    require(clouds, 'No published heads for ' + prefix)
    cloud = np.concatenate(clouds)
    low, high = cloud.min(axis=0), cloud.max(axis=0)
    centre = np.array([0.0, (low[1] + high[1]) / 2])
    flat = cloud[:, :2] - centre
    first = math.floor(low[2] / SLICE)
    rings = np.zeros((math.floor(high[2] / SLICE) - first + 1, seams.DIRECTIONS))
    np.maximum.at(rings, (np.floor(cloud[:, 2] / SLICE).astype(int) - first, seams.sectors(flat)), np.linalg.norm(flat, axis=1))
    return {'heads': numbers, 'min': low, 'max': high, 'axis': centre, 'sliceHeight': SLICE, 'firstSlice': first * SLICE, 'rings': rings}


def rounded(value, digits=4):
    return [round(float(v), digits) for v in value] if np.ndim(value) else round(float(value), digits)


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seam_contract(body_folder, supermodel_folders, bodies=('pmh0', 'pfh0')):
    """The seam contract document, measured from the body pack and the animation models the bodies inherit."""
    body_folder = Path(body_folder)
    document = {'schemaVersion': 1, 'kind': seams.KIND, 'version': 1, 'units': 'metres', 'directions': seams.DIRECTIONS,
                'tierOffsets': {str(tier): offset for tier, offset in seams.TIER_OFFSETS.items()},
                'designBend': 'p95', 'joints': {}, 'source': {'bodies': {}, 'animation': {}}}
    for name in bodies:
        bones, parts = body(body_folder, name)
        measured = joints(bones, parts)
        swing = bends((body_folder / (name + '.mdl')).read_bytes(), supermodel_folders)
        document['source']['animation'][name] = {'models': swing['models'], 'clips': swing['clips']}
        document['source']['bodies'][name] = {path.name: sha(path) for path in
                                              [body_folder / (name + '.mdl')] + sorted(body_folder.glob(name + '_*001.mdl'))
                                              if path.stem == name or path.stem.split('_')[1][:-3] in seams.BONES}
        for joint, row in measured.items():
            spec = seams.JOINTS[joint]
            entry = document['joints'].setdefault(joint, {'over': spec['over'], 'under': spec['under'], 'bodies': {}})
            angle = swing['joints'][joint]
            mean = float(row['bodyRing'].mean())
            tiers = {str(tier): {'envelopeRadius': rounded(row['bodyRing'].max() + offset), 'meanRadius': rounded(mean + offset),
                                 'minimumOverlap': rounded(seams.minimum_overlap(mean + offset, angle['p95']))}
                     for tier, offset in seams.TIER_OFFSETS.items()}
            entry['bodies'][name] = {'point': rounded(row['point']), 'normal': rounded(row['normal'], 5), 'bodyRing': rounded(row['bodyRing']),
                                     'underPastPlane': rounded(row['underPastPlane']), 'overPastPlane': rounded(row['overPastPlane']),
                                     'bend': {'max': rounded(angle['max'], 1), 'maxClip': angle['maxClip'], 'p99': rounded(angle['p99'], 1),
                                              'p95': rounded(angle['p95'], 1), 'median': rounded(angle['median'], 1)},
                                     'tiers': tiers}
    return seams.validate_contract(document)


def head_envelopes(head_folder, body_folder, numbers=None):
    """Head envelopes per race and gender (heads are published for the Fit build), with each body's head bone height."""
    document = {'schemaVersion': 1, 'kind': 'srn-armorkit-head-envelopes', 'version': 1, 'units': 'metres',
                'directions': seams.DIRECTIONS, 'space': 'head bone (head_g)', 'bodies': {}}
    for name in registry.BODIES:
        if name[3] != '0':
            continue
        wanted = None if numbers is None else numbers[name]
        measured = head_envelope(head_folder, name, wanted)
        bones = rig((Path(body_folder) / (name + '.mdl')).read_bytes())
        document['bodies'][name] = {'heads': measured['heads'], 'min': rounded(measured['min']), 'max': rounded(measured['max']),
                                    'axis': rounded(measured['axis']), 'sliceHeight': measured['sliceHeight'],
                                    'firstSlice': rounded(measured['firstSlice']), 'rings': [rounded(row) for row in measured['rings']],
                                    'headBone': rounded(bones['head_g'][:3, 3]), 'neckBone': rounded(bones['neck_g'][:3, 3])}
    return document
