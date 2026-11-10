"""Measure the seam contract and the head envelopes from published pack folders.

Reads binary models as the packs ship them (rigid parts through headkit's native reader, skeletons and
animation through PhenoMorpher's animation library). Nothing here edits a pack. Stock supermodels that
the packs do not carry are read from an explicit folder of extracted game models.
"""
import hashlib
import math
from pathlib import Path

import numpy as np

from tools.headkit import native_reader
from tools.phenomorpher.phenomorpher.engine import anim_library, native_motion

from . import registry, seams
from .registry import require

GUARD = 0.01  # the rings are also taken 1 cm to each side of the plane, where a body part ends right on it
OVER_LIMIT = 1.6  # the over part's ring counts only this many under-ring radii from the centre
# Where a limb or the neck leaves the torso, the plane also cuts the torso itself. A plane section says
# nothing about the torso piece there (it is a wall with a hole, not a tube), so only the limb's ring
# counts and the over part is not measured.
TORSO_OPENINGS = ('neck', 'shoulder', 'hip')
SLICE = 0.02
SURFACE_STEP = 0.003  # head surfaces are sampled at least this densely before they are binned


def token(slot, side):
    """The model token of a slot on a side; unpaired slots have one token whatever the side."""
    tokens = registry.SLOTS[slot]['tokens']
    return tokens[0] if len(tokens) == 1 else next(name for name in tokens if name.endswith(side))


def rig(blob):
    """{bone: 4x4 world matrix} of a body model's bind pose."""
    return native_motion.sample(anim_library.load_model(None, blob)['nodes'])


def mesh(blob, name, world):
    """(vertices, faces) of a rigid part model, moved into body space by its bone's bind matrix."""
    meshes = native_reader.decode(blob, name, require_tangents=False, apply_rigid_transforms=True)
    require(meshes, 'Model has no rigid mesh: ' + name)
    offsets = np.cumsum([0] + [len(m['position']) for m in meshes])
    vertices = np.concatenate([m['position'] for m in meshes]) @ world[:3, :3].T + world[:3, 3]
    return vertices, np.concatenate([m['faces'].astype(int) + offset for m, offset in zip(meshes, offsets)])


def body_files(folder, name, number=1):
    """{model token: path} of the skin part models one body has in a pack folder."""
    folder = Path(folder)
    paths = {key: folder / f'{registry.model_name(name, key, number)}.mdl' for key in seams.BONES}
    return {key: path for key, path in paths.items() if path.is_file()}


def body(folder, name, number=1):
    """(rig, {model token: (vertices, faces)}) of one body from a pack folder."""
    bones = rig((Path(folder) / (name + '.mdl')).read_bytes())
    return bones, {key: mesh(path.read_bytes(), path.stem, bones[seams.BONES[key]])
                   for key, path in body_files(folder, name, number).items()}


def skin(parts, slot, side):
    name = token(slot, side)
    require(name in parts, 'The body has no skin part ' + name)
    return parts[name]


def part_ring(part, point, normal, offset=0.0, limit=None):
    vertices, faces = part
    return seams.ring(seams.section(vertices, faces, point + offset * seams.unit(normal), normal), limit=limit)


def joint_ring(parts, point, normal, joint, side='l'):
    """The body's own ring at a joint: both skin parts' sections at the plane and 1 cm to its two sides."""
    spec = seams.JOINTS[joint]
    inner = np.max([part_ring(skin(parts, spec['under'], side), point, normal, offset) for offset in (0.0, GUARD)], axis=0)
    if joint in TORSO_OPENINGS:
        return inner
    limit = OVER_LIMIT * inner.max()
    outer = np.max([part_ring(skin(parts, spec['over'], side), point, normal, offset, limit) for offset in (0.0, -GUARD)], axis=0)
    return np.maximum(inner, outer)


def joints(bones, parts):
    """Per joint and side: plane, body ring and how far each skin part runs past the plane.

    The right side is measured, not mirrored: a body need not be centred on x = 0. `overPastPlane` is
    left out at the torso openings, where the over part is the torso itself."""
    result = {}
    for joint, spec in seams.JOINTS.items():
        result[joint] = {}
        for side in seams.sides(joint):
            point, normal = seams.plane(bones, joint, side)
            ring = joint_ring(parts, point, normal, joint, side)
            require(ring.min() > 0, f'{joint} {side}: the body ring has an empty direction')
            row = {'point': point, 'normal': normal, 'bodyRing': ring,
                   'underPastPlane': max(0.0, -seams.extent(skin(parts, spec['under'], side)[0], point, normal)[0])}
            if joint not in TORSO_OPENINGS:
                row['overPastPlane'] = max(0.0, seams.extent(skin(parts, spec['over'], side)[0], point, normal)[1])
            result[joint][side] = row
    return result


def animation_models(name, blob, folders):
    """({model name: model}, {model name: path}, chain) of a body and the animation models it inherits.

    The chain runs nearest first; each supermodel is read from the first folder that has it."""
    models, paths, chain = {name: anim_library.load_model(None, blob)}, {}, [name]
    parent = models[name]['parent']
    while parent and parent.lower() != 'null':
        require(parent not in models, 'Cyclic supermodel chain at ' + parent)
        path = next((Path(folder) / (parent + '.mdl') for folder in folders if (Path(folder) / (parent + '.mdl')).is_file()), None)
        require(path is not None, 'Supermodel not found in the given folders: ' + parent)
        models[parent], paths[parent] = anim_library.load_model(path), path
        chain.append(parent)
        parent = models[parent]['parent']
    return models, paths, chain


def ancestors(nodes, names):
    """The named nodes and every node above them: all a pose needs to place those bones."""
    keep = set()
    for name in names:
        while name is not None and name not in keep:
            keep.add(name)
            name = nodes[name]['parent']
    return {name: node for name, node in nodes.items() if name in keep}


def bends(name, body_blob, folders):
    """Per joint: how far the under part swings from the bind pose across the clips the body plays, in degrees.

    A clip name that several models in the chain carry plays from the nearest one, as in the client; the
    copies behind it are counted as shadowed and not sampled."""
    models, paths, chain = animation_models(name, body_blob, folders)
    owners = anim_library.effective(chain, models)
    pairs = [(joint, side, seams.BONES[token(spec['under'], side)], seams.BONES[token(spec['over'], side)])
             for joint, spec in seams.JOINTS.items() for side in seams.sides(joint)]
    nodes = ancestors(models[name]['nodes'], {bone for _, _, moving, reference in pairs for bone in (moving, reference)})
    rest = native_motion.sample(nodes)
    terms = {(joint, side): seams.swing_terms(rest, moving, reference, seams.plane(rest, joint, side)[1])
             for joint, side, moving, reference in pairs}
    samples = {joint: [] for joint in seams.JOINTS}
    worst = {joint: (0.0, '') for joint in seams.JOINTS}
    for clip_name, row in owners.items():
        owner = row['owner']
        clip = models[owner]['clips'][clip_name]
        animated = {(name if node == owner else node): keys for node, keys in clip['nodes'].items()}
        for time in native_motion.sample_times(clip):
            pose = native_motion.sample(nodes, animated, time)
            turned = {bone: seams.rotation(matrix) for bone, matrix in pose.items()}
            for joint, side, moving, reference in pairs:
                angle = seams.swing_angle(*terms[joint, side], turned[reference], turned[moving])
                samples[joint].append(angle)
                if angle > worst[joint][0]:
                    worst[joint] = (angle, f'{owner}:{clip_name}')
    return {'models': chain[1:], 'paths': paths, 'clips': len(owners), 'shadowedClips': sum(len(row['shadowed']) for row in owners.values()),
            'joints': {joint: {'max': worst[joint][0], 'maxClip': worst[joint][1],
                               'p99': float(np.percentile(samples[joint], 99)), 'p95': float(np.percentile(samples[joint], 95)),
                               'median': float(np.median(samples[joint]))} for joint in seams.JOINTS}}


def clearance(part, slot, bones, parts, joint, side='l'):
    """Per direction, how far a worn part's ring stands outside the body ring at a joint; nan where it has none.

    `slot` is the worn part's slot. It must end at the joint, and a torso piece cannot be measured at its
    neck hole, armholes or leg holes: a plane section there cuts the torso wall, not a tube."""
    spec = seams.JOINTS[joint]
    require(slot in (spec['over'], spec['under']), f'A {slot} part does not end at the {joint}')
    require(slot == spec['under'] or joint not in TORSO_OPENINGS,
            f'The {slot} cannot be measured at the {joint} by a plane section; only the {spec["under"]} can')
    side = 'l' if side == 'c' else side
    point, normal = seams.plane(bones, joint, side)
    base = joint_ring(parts, point, normal, joint, side)
    worn = np.max([part_ring(part, point, normal, offset, 3.0 * base.max()) for offset in (-GUARD, 0.0, GUARD)], axis=0)
    return np.where(worn > 0, worn - base, np.nan)


def surface_points(vertices, faces, step=SURFACE_STEP):
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


def head_envelope(folder, prefix):
    """Outer bounds of the published heads of one body prefix, in the head bone's space.

    Returns the head numbers, the bounding box and, per 2 cm of height, the largest radius of the head
    surfaces in 16 directions about the vertical line through the box centre."""
    found = sorted((int(path.stem.rsplit('head', 1)[1]), path) for path in Path(folder).glob(prefix + '_head*.mdl'))
    require(found, 'No published heads for ' + prefix)
    cloud = np.concatenate([surface_points(*mesh(path.read_bytes(), path.stem, np.eye(4))) for _, path in found])
    low, high = cloud.min(axis=0), cloud.max(axis=0)
    centre = np.array([0.0, (low[1] + high[1]) / 2])
    flat = cloud[:, :2] - centre
    first = math.floor(low[2] / SLICE)
    rings = np.zeros((math.floor(high[2] / SLICE) - first + 1, seams.DIRECTIONS))
    np.maximum.at(rings, (np.floor(cloud[:, 2] / SLICE).astype(int) - first, seams.sectors(flat)), np.linalg.norm(flat, axis=1))
    return {'heads': [number for number, _ in found], 'min': low, 'max': high, 'axis': centre, 'sliceHeight': SLICE,
            'firstSlice': first * SLICE, 'rings': rings}


def rounded(value, digits=4):
    return [round(float(v), digits) for v in value] if np.ndim(value) else round(float(value), digits)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seam_contract(body_folder, supermodel_folders, bodies=seams.AUTHORING_BODIES, design_bend='p95'):
    """The seam contract document, measured from the body pack and the animation models the bodies inherit."""
    body_folder = Path(body_folder)
    document = {'schemaVersion': 1, 'kind': seams.KIND, 'version': 2, 'units': 'metres', 'directions': seams.DIRECTIONS,
                'tierOffsets': {str(tier): offset for tier, offset in seams.TIER_OFFSETS.items()},
                'designBend': design_bend, 'joints': {}, 'source': {'bodies': {}, 'animation': {}}}
    for name in bodies:
        bones, parts = body(body_folder, name)
        measured = joints(bones, parts)
        swing = bends(name, (body_folder / (name + '.mdl')).read_bytes(), supermodel_folders)
        document['source']['animation'][name] = {'models': {model: sha(swing['paths'][model]) for model in swing['models']},
                                                 'clips': swing['clips'], 'shadowedClips': swing['shadowedClips']}
        document['source']['bodies'][name] = {path.name: sha(path) for path in
                                              [body_folder / (name + '.mdl'), *sorted(body_files(body_folder, name).values())]}
        for joint, rows in measured.items():
            spec = seams.JOINTS[joint]
            entry = document['joints'].setdefault(joint, {'over': spec['over'], 'under': spec['under'], 'bodies': {}})
            angle = swing['joints'][joint]
            bend = {'max': rounded(angle['max'], 1), 'maxClip': angle['maxClip'], 'p99': rounded(angle['p99'], 1),
                    'p95': rounded(angle['p95'], 1), 'median': rounded(angle['median'], 1)}
            recorded = {side: {key: rounded(value, 5 if key == 'normal' else 4) for key, value in row.items()} for side, row in rows.items()}
            # Tier numbers come from the recorded (rounded) rings and bend, so the file agrees with itself exactly.
            tiers = {str(tier): {key: rounded(value) for key, value in
                                 seams.tier_values([row['bodyRing'] for row in recorded.values()], offset, bend[design_bend]).items()}
                     for tier, offset in seams.TIER_OFFSETS.items()}
            entry['bodies'][name] = {'sides': recorded, 'bend': bend, 'tiers': tiers}
    return seams.validate_contract(document)


def head_envelopes(head_folder, body_folder):
    """Head envelopes per race and gender (heads are published for the Fit build), with each body's head bone height."""
    document = {'schemaVersion': 1, 'kind': 'srn-armorkit-head-envelopes', 'version': 2, 'units': 'metres',
                'directions': seams.DIRECTIONS, 'space': 'head bone (head_g)', 'surfaceStep': SURFACE_STEP, 'bodies': {}}
    for name in registry.BODIES:
        if name[3] != '0':
            continue
        measured = head_envelope(head_folder, name)
        bones = rig((Path(body_folder) / (name + '.mdl')).read_bytes())
        document['bodies'][name] = {'heads': measured['heads'], 'min': rounded(measured['min']), 'max': rounded(measured['max']),
                                    'axis': rounded(measured['axis']), 'sliceHeight': measured['sliceHeight'],
                                    'firstSlice': rounded(measured['firstSlice']), 'rings': [rounded(row) for row in measured['rings']],
                                    'headBone': rounded(bones['head_g'][:3, 3]), 'neckBone': rounded(bones['neck_g'][:3, 3])}
    return document
