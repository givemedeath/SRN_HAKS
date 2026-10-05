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
    if verify_inputs and rig_mode(data) == 'stock-exact':
        verify_stock_reference(data)
    return data

def validate(data):
    require(data.get('schemaVersion') == 2 and data.get('kind') == 'phenotype-target',
            'Explicit version 2 phenotype target required')
    require(re.fullmatch(r'[a-z0-9-]+', data.get('id', '')), 'Invalid target identity')
    identity = data['identity']
    mode = rig_mode(data)
    require(mode in ('retargeted', 'stock-exact'), 'Undeclared rig mode')
    if mode == 'stock-exact':
        require(identity['gender'] in ('male', 'female') and identity['phenotype'] == 0,
                'Stock-exact Human normal gender required')
        require(identity['prefix'] == ('pmh0' if identity['gender'] == 'male' else 'pfh0')
                and identity['raceId'] == 6 and identity['appearanceRow'] == 6,
                'Stock-exact Human identity/family mismatch')
        require(data['rig']['sourcePrefix'] == identity['prefix'], 'Stock source prefix differs')
    else:
        require(identity['gender'] == 'male' and identity['phenotype'] == 0,
                'This production path supports male phenotype 0')
        require(re.fullmatch(r'pm[a-z]0', identity['prefix']), 'Invalid male normal model family')
    require(type(identity['raceId']) is int and type(identity['appearanceRow']) is int,
            'Explicit race and appearance rows required')
    rig = data['rig']
    factor = rig['runtimeScale']
    require(type(factor) in (int, float) and np.isfinite(factor) and factor > 0,
            'Positive finite runtime scale required')
    require(all(type(data.get(name)) in (int, float) and np.isfinite(data[name]) and data[name] > 0
                for name in ('heightMeters', 'workingHeightMeters')), 'Positive finite stature required')
    require(abs(data['heightMeters'] - data['workingHeightMeters'] * factor) < 1e-9,
            'Working/runtime stature relationship differs')
    require(rig['positionPolicy'] == ('stock-exact' if mode == 'stock-exact' else 'bind-relative') and
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
    if mode == 'stock-exact':
        require(factor == 1 and data['heightMeters'] == data['workingHeightMeters'],
                'Stock-exact stature must remain identity')
        require(not rig.get('privateAliases') and not rig.get('changedLocalPositions'),
                'Stock-exact rig cannot export private aliases or moved binds')
        require(rig['frames']['working'] == rig['frames']['runtime'], 'Stock-exact frames must remain identical')
        receipt = rig.get('stockReferenceReceipt', {})
        require(set(receipt) == {'path', 'sha256'} and bool(receipt['path'])
                and re.fullmatch(r'[a-f0-9]{64}', receipt['sha256']), 'Pinned stock reference receipt required')
    fixed_garment_parts(data)
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


def rig_mode(data):
    return data['rig'].get('mode', 'retargeted')


def fixed_garment_parts(data):
    material = data.get('material', {})
    values = material.get('fixedGarmentParts', [material.get('fixedGarmentPart', 'pelvis')])
    require(isinstance(values, list) and all(isinstance(value, str) for value in values) and len(values) == len(set(values))
            and set(values) <= {'chest', 'pelvis'}, 'Explicit chest/pelvis garment owners required')
    if rig_mode(data) == 'retargeted':
        require(set(values) == {'pelvis'}, 'Legacy fixed garment belongs only to pelvis')
    return set(values)


def verify_stock_reference(data):
    from retarget import NODE, nodes
    from rig_controller_audit import world_frames
    pin = data['rig']['stockReferenceReceipt']
    path = Path(pin['path']).resolve()
    require(sha(path) == pin['sha256'], 'Stock reference receipt changed')
    proof = json.loads(path.read_text(encoding='utf-8'))
    require(proof.get('kind') == 'stock-target-reference' and proof.get('pass') is True
            and proof.get('prefix') == data['identity']['prefix'], 'Stock reference identity/proof differs')
    require(proof['heightMeters'] == data['heightMeters']
            and proof['frames'] == data['rig']['frames']['working'], 'Stock reference height/frames differ')
    for name, expected in proof['frozenInputs'].items():
        require(sha(name) == expected, 'Frozen stock input changed: ' + name)
    source = Path(proof['rootAscii']['path']).resolve()
    require(proof['frozenInputs'].get(str(source)) == proof['rootAscii']['sha256']
            and sha(source) == proof['rootAscii']['sha256'], 'Stock root is not frozen')
    text = source.read_text(encoding='cp1252')
    root = re.search(r'(?mi)^newmodel\s+(\S+)\s*$', text)
    require(root is not None and root[1].lower() == data['identity']['prefix'],
            'Installed stock root family differs')
    geometry = text.split('endmodelgeom', 1)[0]
    skeleton = nodes(text)
    names = [match[2].lower() for match in NODE.finditer(geometry)]
    duplicates = {name for name in names if names.count(name) > 1}
    # Installed pfh0 has two non-attachment impact dummies. Preserve those bytes;
    # an ambiguous body attachment or model root cannot define a fitting frame.
    require(not duplicates & (set(PART_JOINTS.values()) | {data['identity']['prefix']}),
            'Duplicate stock attachment/root hierarchy nodes')
    require(all(float(value) == 1 for value in re.findall(r'(?mi)^\s*scale\s+(\S+)', geometry)),
            'Nonidentity stock node scale')
    world = world_frames(skeleton)
    require(set(world) == set(proof['frames']) and all(np.array_equal(world[name], proof['frames'][name])
            for name in world), 'Declared frames differ from actual installed stock hierarchy')
    return proof


def rig_ready(data):
    if rig_mode(data) == 'stock-exact':
        verify_stock_reference(data)
        return True
    return data['rig'].get('pilotAccepted') is True
