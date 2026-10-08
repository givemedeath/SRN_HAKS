"""Explicit skin PLT intensity descendant on top of one replayed current (or pelvis-routed) skin calibration.

The parent material inputs are replayed in full by current_skin_calibration_bridge (which dispatches the pelvis
route). A pinned derivation receipt (derive_skin_intensity_descendant) then supplies one bounded int16 delta per
declared skin atlas of this part; each delta is bound to the exact replayed parent effective intensity and to the
resulting intensity by fingerprint, applied exactly once, and must stay within bytes. Colour, normal, roughness and
garment pixels, geometry and face ownership are unchanged. No selection, client or production acceptance.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import target_contract as c

MODE = 'current-skin-intensity-descendant-v1'
KIND = 'separately-verified-current-geometry-and-skin-intensity-descendant-material-inputs'
RECEIPT_KIND = 'skin-intensity-descendant-derivation'
FIELDS = {'mode', 'parent', 'descendant'}


def fingerprint(a):
    a = np.ascontiguousarray(a); return hashlib.sha256(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes()).hexdigest()


def exact_pin(row):
    c.require(isinstance(row, dict) and set(row) == {'path', 'sha256'} and isinstance(row['path'], str) and Path(row['path']).is_absolute(),
              'Exact absolute path/sha256 pin required')
    p = Path(row['path']).resolve(); c.require(p.is_file() and c.sha(p) == row['sha256'], 'Changed intensity descendant input: ' + str(p)); return p


def controls(value):
    import current_skin_calibration_bridge as current
    c.require(isinstance(value, dict) and set(value) == FIELDS and value['mode'] == MODE, 'Exact skin intensity descendant controls required')
    c.require(not (isinstance(value['parent'], dict) and value['parent'].get('mode') == MODE), 'Nested intensity descendants are not supported')
    current.controls(value['parent']); exact_pin(value['descendant'])


def descendant_rows(value, part):
    dp = exact_pin(value['descendant']); rec = json.loads(dp.read_text(encoding='utf-8'))
    c.require(rec.get('schemaVersion') == 1 and rec.get('kind') == RECEIPT_KIND and rec.get('selected') is False and rec.get('clientAccepted') is False
              and rec.get('productionAccepted') is False and rec.get('geometryUvNormalRoughnessGarmentEdited') is False, 'Exact unaccepted intensity derivation receipt required')
    rows = {r['atlasKey']: r for r in rec['atlases'].values() if r['part'] == part}
    c.require(rows and len(rows) == sum(1 for r in rec['atlases'].values() if r['part'] == part), 'One delta per declared atlas of this part required')
    return dp, rows


def apply_delta(parent, row):
    """Exactly one bounded application; fingerprints bind the parent and the result."""
    dp = exact_pin(row['delta'])
    with np.load(dp, allow_pickle=False) as z:
        c.require(set(z.files) == {'delta', 'parentIntensitySha256', 'intensitySha256'}, 'Exact delta schema required')
        delta = z['delta'].copy(); bound = (str(z['parentIntensitySha256'].item()), str(z['intensitySha256'].item()))
    c.require(parent.dtype == np.uint8 and parent.shape == (2048, 2048) and delta.dtype == np.int16 and delta.shape == parent.shape, 'Exact 2K byte intensity and int16 delta required')
    c.require(fingerprint(parent) == row['parentIntensitySha256'] == bound[0], 'Intensity descendant bound to a different parent calibration')
    new = parent.astype(np.int32) + delta
    c.require(new.min() >= 0 and new.max() <= 255, 'Intensity descendant leaves byte range')
    new = new.astype(np.uint8)
    c.require(fingerprint(new) == row['intensitySha256'] == bound[1], 'Intensity descendant result differs from its receipt')
    changed = int((delta != 0).sum()); c.require(changed == row['changedTexels'] and int(np.abs(delta).max()) == row['maxAbsDelta'] and changed > 0, 'Declared delta extent differs')
    return new, dp, {'delta': row['delta'], 'parentIntensitySha256': row['parentIntensitySha256'], 'intensitySha256': row['intensitySha256'], 'changedTexels': changed,
                     'maxAbsDelta': row['maxAbsDelta'], 'coveredChanged': row.get('coveredChanged'), 'uncoveredChanged': row.get('uncoveredChanged')}


def staging_inputs(value, target_path, target, part, space, source, receipt, ao_strength=0, native_geometry=None):
    import current_skin_calibration_bridge as current
    controls(value)
    parent = current.staging_inputs(value['parent'], target_path, target, part, space, source, receipt, ao_strength, native_geometry=native_geometry)
    dp, rows = descendant_rows(value, part)
    keys = {v['atlasKey'] for v in parent['materialSlots'].values() if v['role'] == 'skin'}
    c.require(set(rows) <= keys, 'Intensity descendant names an atlas this part does not own as skin')
    result = {k: dict(v) for k, v in parent['materialRows'].items()}; atlases = {}; pins = dict(parent['frozenInputs']); pins[str(dp)] = c.sha(dp)
    for key, row in sorted(rows.items()):
        new, delta_path, proof = apply_delta(parent['materialRows'][key]['intensity'], row); pins[str(delta_path)] = c.sha(delta_path)
        for other in ('color', 'normal', 'roughness'):
            c.require(np.array_equal(result[key][other], parent['materialRows'][key][other]), 'Protected parent pixels changed')
        result[key]['intensity'] = new; atlases[key] = proof
    for p in (__file__, current.__file__):
        p = str(Path(p).resolve()); pins[p] = c.sha(p)
    for p, h in pins.items():
        c.require(c.sha(p) == h, 'Intensity descendant input changed: ' + p)
    proof = {'kind': KIND, 'part': part, 'coordinateSpace': 'working', 'mode': MODE, 'parentMaterialProof': parent['proof'], 'descendant': value['descendant'],
             'atlases': atlases, 'intensityDescendantApplications': 1, 'calibrationApplications': 1, 'colorNormalRoughnessGarmentPixelsEdited': False,
             'geometryOrFaceOwnershipEdited': False, 'runtimeConversions': 0, 'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return {**parent, 'materialRows': result, 'proof': proof, 'frozenInputs': pins, 'auditFiles': [Path(p) for p in pins]}
