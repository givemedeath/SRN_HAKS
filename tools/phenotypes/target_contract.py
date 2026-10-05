"""Explicit, hash-bound phenotype targets; legacy Human callers remain separate."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np

PART_JOINTS = {
    'chest':'torso_g', 'pelvis':'pelvis_g', 'neck':'neck_g', 'head':'head_g',
    'bicepl':'lbicep_g', 'bicepr':'rbicep_g', 'forel':'lforearm_g', 'forer':'rforearm_g',
    'handl':'lhand_g', 'handr':'rhand_g', 'legl':'lthigh_g', 'legr':'rthigh_g',
    'shinl':'lshin_g', 'shinr':'rshin_g', 'footl':'lfoot_g', 'footr':'rfoot_g',
}
BODY_PARTS = set(PART_JOINTS) - {'head', 'neck'}
PAIRS = [('bicepl','bicepr'), ('forel','forer'), ('handl','handr'),
         ('legl','legr'), ('shinl','shinr'), ('footl','footr')]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def load(path, verify_inputs=True):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    validate(data)
    if verify_inputs:
        for name, pin in data.get('frozenInputs', {}).items():
            require(sha(name) == pin, 'Target input changed: ' + name)
    return data

def validate(data):
    require(data.get('schemaVersion') == 2 and data.get('kind') == 'phenotype-target',
            'Explicit version 2 phenotype target required')
    require(re.fullmatch(r'[a-z0-9-]+', data.get('id', '')), 'Invalid target identity')
    identity = data['identity']
    require(identity['gender'] == 'male' and identity['phenotype'] == 0,
            'This production path supports male phenotype 0')
    require(re.fullmatch(r'pm[a-z]0', identity['prefix']), 'Invalid male normal model family')
    require(type(identity['raceId']) is int and type(identity['appearanceRow']) is int,
            'Explicit race and appearance rows required')
    rig = data['rig']
    factor = rig['runtimeScale']
    require(np.isfinite(factor) and factor > 0, 'Positive finite runtime scale required')
    require(abs(data['heightMeters'] - data['workingHeightMeters'] * factor) < 1e-9,
            'Working/runtime stature relationship differs')
    require(rig['positionPolicy'] == 'bind-relative' and
            rig['preserveRotations'] is True and rig['preserveTimingEvents'] is True,
            'Declared bind-relative animation preservation required')
    for space in ('working', 'runtime'):
        frames = rig['frames'][space]
        require(set(PART_JOINTS.values()) <= set(frames), 'Missing target attachment frames')
        for name, value in frames.items():
            frame = np.asarray(value, dtype=float)
            require(frame.shape == (4,4) and np.isfinite(frame).all(), 'Invalid frame: ' + name)
            require(np.allclose(frame[3], [0,0,0,1], atol=1e-12, rtol=0), 'Projective bind frame')
            rotation = frame[:3,:3]
            require(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-8, rtol=0)
                    and abs(np.linalg.det(rotation)-1) < 1e-8, 'Attachment orientation must be proper/rigid')
    for name, working in rig['frames']['working'].items():
        runtime = np.asarray(rig['frames']['runtime'][name])
        require(np.allclose(runtime[:3,:3], np.asarray(working)[:3,:3], atol=1e-10, rtol=0)
                and np.allclose(runtime[:3,3], np.asarray(working)[:3,3]*factor, atol=1e-9, rtol=0),
                'Runtime frame must apply stature conversion once: ' + name)
    expected = {part: identity['prefix'] + '_' + part + '001' for part in PART_JOINTS}
    require(data['models'] == expected, 'Native body inventory differs from target identity')
    require(all(re.fullmatch(r'[a-z0-9_-]{1,16}', model) for model in expected.values()),
            'Resource name exceeds native contract')
    return data

def frame(data, joint, space='working'):
    require(space in ('working','runtime'), 'Explicit working/runtime coordinate space required')
    return np.asarray(data['rig']['frames'][space][joint.lower()], dtype=float)

def binding(path, data, space):
    require(space in ('working','runtime'), 'Explicit working/runtime coordinate space required')
    return {'targetContract':str(Path(path).resolve()), 'targetContractSha256':sha(path),
            'targetId':data['id'], 'rigRevision':data['rig']['revision'], 'coordinateSpace':space}

def verify_binding(receipt, path, data, space):
    require(all(receipt.get(k) == v for k,v in binding(path,data,space).items()),
            'Receipt belongs to another target, rig revision or coordinate space')

def model(data, part):
    require(part in PART_JOINTS, 'Undeclared target body part')
    return data['models'][part]
