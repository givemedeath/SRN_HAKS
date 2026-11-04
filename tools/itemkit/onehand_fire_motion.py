"""Private, additive Human one-handed firearm animation candidate.

Only the explicitly mapped custom clips change motion. Existing root bytes are
preserved except for the supermodel pointer; the original chain is inherited.
"""
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from tools.phenomorpher.phenomorpher.engine.anim_library import (
    PARENT_FIELD, library_text, load_model, rename,
)
from tools.phenomorpher.phenomorpher.engine.native_motion import sample, value


def alias_weapon_clips(text, aliases):
    """Give attached weapon clips the names used by replaced body animations.

    Preserve the original clips for ordinary carriers. Geometry, controllers,
    transition times and events are copied verbatim; only clip labels change.
    """
    pattern = r'(?ms)^newanim (\w+) (\w+)\s*\n.*?^doneanim \1 \2[ \t]*\r?$'
    blocks = {}
    for match in re.finditer(pattern, text):
        name = match[1]
        if name in blocks:
            raise ValueError('Duplicate weapon animation: ' + name)
        blocks[name] = match
    additions = []
    for source, target in aliases.items():
        if not re.fullmatch(r'[a-z0-9_]{1,16}', target) or target in blocks:
            raise ValueError('Invalid or existing weapon animation alias: ' + target)
        if source not in blocks:
            raise ValueError('Missing weapon animation: ' + source)
        match = blocks[source]
        additions.append(re.sub(r'(?m)^(newanim|doneanim) '+re.escape(source)+r' ',
                                lambda m: m[1]+' '+target+' ', match[0]))
    ending = re.search(r'(?m)^donemodel \w+[ \t]*\r?$', text)
    if ending is None:
        raise ValueError('Missing model terminator')
    return text[:ending.start()]+'\n'.join(additions)+'\n'+text[ending.start():]


def rotation_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    cross = np.cross(a, b)
    sine = np.linalg.norm(cross)
    if sine < 1e-10:
        if np.dot(a, b) < 0:
            raise ValueError('Ambiguous opposite-vector twist')
        return np.eye(3)
    return Rotation.from_rotvec(cross / sine * np.arctan2(sine, np.dot(a, b))).as_matrix()


def fitted_frame(fit):
    """Ingram source landmarks: muzzle is -X; receiver top is +Z.

    Transform directions with the retained fit, never infer up from width.
    Columns are muzzle direction, receiver top and their perpendicular.
    """
    matrix = np.asarray(fit['fitMatrix'], float)[:3, :3]
    barrel = matrix @ np.array([-1., 0., 0.])
    barrel /= np.linalg.norm(barrel)
    up = matrix @ np.array([0., 0., 1.])
    up -= barrel * np.dot(barrel, up)
    up /= np.linalg.norm(up)
    return np.column_stack((barrel, up, np.cross(barrel, up)))


def clips(stock, rig, stance, weapon_frame):
    # Sample the native balanced stance once. Left arm stays free, not braced
    # against a two-handed weapon. Preserve all native joint translations.
    nodes = copy.deepcopy(rig['nodes'])
    animation = rename(stance['nodes'], next(n for n, r in stance['nodes'].items() if r['parent'] is None), rig['name'])
    for name, node in nodes.items():
        controls = {**node['controls'], **animation.get(name, {}).get('controls', {})}
        node['controls'] = {k: {'times': np.array([0.]), 'values': np.array([value(c, 0, k == 20)])}
                            for k, c in controls.items() if k in (8, 20)}
    world = sample(nodes)
    shoulder = world['rbicep_g'][:3, 3]
    upper = nodes['rforearm_g']['controls'][8]['values'][0]
    lower = nodes['rhand_g']['controls'][8]['values'][0]
    lengths = np.linalg.norm(upper), np.linalg.norm(lower)
    # Aim +Y, receiver top +Z. Include the actual weapon attachment's local
    # rotation instead of testing only the wrist bone or a library dummy.
    target_basis = np.column_stack(([0., 1., 0.], [0., 0., 1.], [1., 0., 0.]))
    attachment = world['rhand_g'][:3, :3].T @ world['rhand'][:3, :3]
    hand_rotation = target_basis @ weapon_frame.T @ attachment.T
    assert np.linalg.det(hand_rotation) > .99999
    keys = [0., .44, .50, .55, .64, .82, 1.]
    recoil = [0., 0., 0., 1., .45, 0., 0.]
    angles = {n: [] for n in ('rbicep_g', 'rforearm_g', 'rhand_g')}
    residuals = []
    for kick in recoil:
        reach = sum(lengths)
        wrist = shoulder + reach * np.array([.042, .88 - .042 * kick, -.126 + .030 * kick])
        direction = wrist - shoulder
        distance = np.linalg.norm(direction)
        assert abs(lengths[0] - lengths[1]) < distance < sum(lengths)
        axis = direction / distance
        bend = np.array([1., 0., -.8])
        bend -= np.dot(bend, axis) * axis
        bend /= np.linalg.norm(bend)
        along = (lengths[0] ** 2 - lengths[1] ** 2 + distance ** 2) / (2 * distance)
        elbow = shoulder + along * axis + np.sqrt(lengths[0] ** 2 - along ** 2) * bend
        upper_world = rotation_between(world['rbicep_g'][:3, :3] @ upper, elbow - shoulder) @ world['rbicep_g'][:3, :3]
        lower_world = rotation_between(world['rforearm_g'][:3, :3] @ lower, wrist - elbow) @ world['rforearm_g'][:3, :3]
        aim_world = Rotation.from_rotvec([np.deg2rad(3.) * kick, 0, 0]).as_matrix() @ hand_rotation
        rotations = {'rbicep_g': world['torso_g'][:3, :3].T @ upper_world,
                     'rforearm_g': upper_world.T @ lower_world,
                     'rhand_g': lower_world.T @ aim_world}
        for name, matrix in rotations.items():
            angles[name].append(Rotation.from_matrix(matrix).as_quat())
        residuals.append(float(np.linalg.norm(shoulder + upper_world @ upper + lower_world @ lower - wrist)))
    # Key only authored stance controllers, never copied static rig offsets.
    fire = {n: {**r, 'controls': {k: copy.deepcopy(nodes[n]['controls'][k]) for k in r['controls'] if k in (8, 20)}}
            for n, r in animation.items() if n in nodes}
    for name, values in angles.items():
        fire[name]['controls'][20] = {'times': np.array(keys), 'values': np.array(values)}
    ready = copy.deepcopy(fire)
    for name in angles:
        ready[name]['controls'][20] = {'times': np.array([0.]), 'values': np.array([angles[name][0]])}
    base = {'length': 1., 'transition': .15, 'animroot': 'rootdummy'}
    result = {'srf7ready': {**base, 'nodes': ready, 'events': []},
              'srf7fire': {**base, 'nodes': fire, 'events': [e for e in stock['clips']['throwr']['events'] if e[1] == 'hit']}}
    assert max(residuals) < 1e-8
    return result, max(residuals)


def build(stock_path, roots, output, fit_result):
    output = Path(output); output.mkdir(exist_ok=False)
    stock = load_model(stock_path)
    female_parent = Path(roots[1]).parent / 'srn_fa_h0.mdl'
    inputs = [Path(stock_path), *map(Path, roots), female_parent, Path(fit_result), Path(__file__)]
    hashes = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    weapon_frame = fitted_frame(json.loads(Path(fit_result).read_text()))
    records = []
    for root_path in map(Path, roots):
        original = root_path.read_bytes(); root = load_model(root_path, original)
        assert root['name'] in ('pmh0', 'pfh0') and root['format'] == 'binary'
        name = 'srf7_' + root['name']
        stance = (load_model(female_parent) if root['name'] == 'pfh0' else stock)['clips']['pause1']
        custom, error = clips(stock, root, stance, weapon_frame)
        geometry = rename(root['nodes'], root['name'], name)
        mapped = {n: {**c, 'nodes': rename(c['nodes'], root['name'], name)} for n, c in custom.items()}
        text = library_text(name, root['parent'], stock['scale'], geometry, mapped)
        (output / (name + '.mdl')).write_text(text, encoding='ascii')
        begin, end = PARENT_FIELD
        patched = original[:begin] + name.encode().ljust(end-begin, b'\0') + original[end:]
        assert patched[:begin] == original[:begin] and patched[end:] == original[end:]
        (output / root_path.name).write_bytes(patched)
        parsed = load_model(output / (name + '.mdl'))
        assert set(parsed['clips']) == set(custom) and parsed['parent'] == root['parent']
        # Validate the actual body root plus emitted clips, not library dummies.
        aim_errors, up_errors = [], []
        for clip in parsed['clips'].values():
            animated = rename(clip['nodes'], name, root['name'])
            for time in np.linspace(0., 1., 101):
                pose = sample(root['nodes'], animated, time)
                frame = pose['rhand'][:3, :3] @ weapon_frame
                aim_errors.append(float(np.degrees(np.arccos(np.clip(frame[:, 0] @ [0, 1, 0], -1, 1)))))
                up_errors.append(float(np.degrees(np.arccos(np.clip(frame[:, 1] @ [0, 0, 1], -1, 1)))))
        assert max(aim_errors) < 3.01 and max(up_errors) < 3.01
        records.append({'root': root['name'], 'inheritedParent': root['parent'], 'library': name,
                        'protectedRootBytesExact': True, 'barrelAimMaxDegrees': max(aim_errors),
                        'receiverUpMaxDegrees': max(up_errors)})
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    result = {'inputs': hashes, 'roots': records, 'maxWristSolveError': error,
              'customClips': list(custom), 'hitEvents': custom['srf7fire']['events'],
              'changesBaseitems': False, 'clientValidated': False}
    (output.parent / (output.name + '-result.json')).write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', required=True, dest='stock_path')
    parser.add_argument('--roots', nargs=2, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--fit-result', required=True)
    print(json.dumps(build(**vars(parser.parse_args()))))
