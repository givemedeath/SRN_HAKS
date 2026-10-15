"""Controller audits that read published binary models (Phase 9).

rig_controller_audit and rig_pose_audit stay ASCII-only for their retarget sources. Published
binaries store unit quaternions whose sign the EE compiler may flip, and ASCII stores axis-angle,
so raw signatures never match. This module decodes both through anim_library and compares
normalised controllers: unit quaternions compared up to sign, positions in metres, float32 keys.
Bezier keys stay unsupported (NativeModel refuses them).
"""
from pathlib import Path

import numpy as np

from .anim_library import TRANSFORMS, compare_clip, f32, load_model

KIND = 'PhenoMorpher-native-controller-audit'
DEFAULT_TOLERANCES = {'positionMetres': 1e-6, 'rotationDegrees': 1e-4, 'otherControllers': 0.0, 'timeSeconds': 1e-5}


def inventory(model):
    """Per clip: keyed node -> {controller name: key count}; plus model header."""
    clips = {}
    for name, clip in model['clips'].items():
        nodes = {}
        for node, row in clip['nodes'].items():
            if row['controls']:
                nodes[node] = {TRANSFORMS.get(kind, f'controller{kind}'): len(c['times']) for kind, c in row['controls'].items()}
        clips[name] = {'length': f32(clip['length']), 'transition': f32(clip['transition']), 'events': len(clip['events']), 'nodes': nodes}
    return {'name': model['name'], 'parent': model['parent'], 'scale': f32(model['scale']), 'format': model['format'], 'clips': clips}


def restricted(clip, kinds):
    """Clip copy keeping only the controller kinds both readers can represent."""
    nodes = {n: {**row, 'controls': {k: c for k, c in row['controls'].items() if k in kinds}} for n, row in clip['nodes'].items()}
    return {**clip, 'nodes': nodes}


def compare(published, source, tolerances=None):
    """Published binary against a source model (ASCII or binary); both decoded by anim_library."""
    tol = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    a = load_model(published); b = load_model(source)
    header = {k: (a[k], b[k]) for k in ('name', 'parent') if a[k] != b[k]}
    if f32(a['scale']) != f32(b['scale']):
        header['scale'] = (a['scale'], b['scale'])
    shared_kinds = {8, 20} if 'ascii' in (a['format'], b['format']) else None
    rows = {}; failures = []
    for clip in sorted(set(a['clips']) | set(b['clips'])):
        if clip not in a['clips'] or clip not in b['clips']:
            rows[clip] = {'status': 'missing', 'in': 'source' if clip in b['clips'] else 'published'}; failures.append(clip); continue
        x, y = a['clips'][clip], b['clips'][clip]
        native_only = sorted({f'controller{k}' for row in x['nodes'].values() for k in row['controls'] if shared_kinds and k not in shared_kinds})
        if shared_kinds:
            x, y = restricted(x, shared_kinds), restricted(y, shared_kinds)
        r = compare_clip(x, a['name'], y, b['name'], tol['timeSeconds'])
        ok = (r['structure'] and r['metadata'] and r['positionMetres'] <= tol['positionMetres']
              and r['rotationDegrees'] <= tol['rotationDegrees'] and r['otherMax'] <= tol['otherControllers'])
        rows[clip] = {'status': 'equal' if ok else 'different', **{k: r[k] for k in ('structure', 'metadata', 'positionMetres', 'rotationDegrees', 'otherMax', 'eventOrderChanged')},
                      'notComparedControllers': native_only}
        if not ok:
            failures.append(clip)
    return {'schemaVersion': 1, 'kind': KIND, 'published': {'path': str(Path(published)), 'format': a['format']},
            'source': {'path': str(Path(source)), 'format': b['format']}, 'tolerances': tol, 'headerDifferences': header,
            'publishedInventory': inventory(a), 'clips': rows, 'failures': failures,
            'passed': not failures and not header, 'quaternionPolicy': 'unit quaternions compared up to sign',
            'assetApprovalCreated': False}
