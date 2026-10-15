"""Controller audits that read published binary models (Phase 9).

rig_controller_audit and rig_pose_audit stay ASCII-only for their retarget sources. Published
binaries store unit quaternions whose sign the EE compiler may flip, and ASCII stores axis-angle,
so raw signatures never match. This module decodes both through anim_library and compares
normalised controllers: unit quaternions compared up to sign, positions in metres, float32 keys.
Bezier keys stay unsupported (NativeModel refuses them).
"""
from pathlib import Path

import numpy as np

from .anim_library import TRANSFORMS, axis_angle_quaternion, compare_clip, f32, load_model

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


def malformed(clip):
    """Controllers whose keys cannot be compared: non-finite values or quaternions of near-zero length."""
    bad = []
    for node, row in clip['nodes'].items():
        for kind, c in row['controls'].items():
            values = np.asarray(c['values'], float); times = np.asarray(c['times'], float)
            if not (np.isfinite(values).all() and np.isfinite(times).all()):
                bad.append(f'{node}:{TRANSFORMS.get(kind, kind)}:non-finite')
            elif kind == 20 and values.size and (np.linalg.norm(values.reshape(len(times), -1), axis=1) < 1e-6).any():
                bad.append(f'{node}:{TRANSFORMS.get(kind, kind)}:zero-quaternion')
    return bad


def restricted(clip, kinds):
    """Clip copy keeping only the controller kinds both readers can represent."""
    nodes = {n: {**row, 'controls': {k: c for k, c in row['controls'].items() if k in kinds}} for n, row in clip['nodes'].items()}
    return {**clip, 'nodes': nodes}


NODE_TYPES = {1: 'dummy', 3: 'light', 5: 'emitter', 17: 'reference', 33: 'trimesh', 97: 'skin', 289: 'danglymesh', 545: 'aabb'}
IDENTITY = np.array([0., 0., 0., 1.])


def static_rig(model, blob):
    """Geometry nodes: {name: parent, type, bind position, bind orientation quaternion}.

    anim_library keeps only keyed clip controllers for ASCII, so static transforms are read here."""
    if model['format'] == 'binary':
        rig = {}
        for name, row in model['nodes'].items():
            c = row['controls']
            q = np.asarray(c[20]['values'][0], float) if 20 in c else IDENTITY
            rig[name.lower()] = {'parent': row['parent'].lower() if row['parent'] else None, 'type': NODE_TYPES.get(row['flags'], f'flags{row["flags"]}'),
                                 'position': np.asarray(c[8]['values'][0], float) if 8 in c else np.zeros(3), 'orientation': q,
                                 'scale': float(c[36]['values'][0][0]) if 36 in c else 1.0}
        return rig
    rig = {}; node = None; inside = False
    for raw in blob.decode('cp1252').splitlines():
        row = raw.split('#', 1)[0].split()
        if not row:
            continue
        word = row[0].lower()
        if word == 'beginmodelgeom':
            inside = True
        elif word == 'endmodelgeom':
            break
        elif inside and word == 'node':
            # Duplicate attachment nodes get the same suffixes as anim_library's readers.
            name = original = row[2].lower(); i = 2
            while name in rig:
                if original != 'impact':
                    raise ValueError('Ambiguous anatomical node ' + name)
                name = original + '__duplicate_' + str(i); i += 1
            node = rig[name] = {'parent': None, 'type': row[1].lower(), 'position': np.zeros(3), 'orientation': IDENTITY, 'scale': 1.0}
        elif inside and word == 'endnode':
            node = None
        elif node is not None and word == 'parent':
            node['parent'] = None if row[1].lower() == 'null' else row[1].lower()
        elif node is not None and word == 'position':
            node['position'] = np.array([float(v) for v in row[1:4]])
        elif node is not None and word == 'orientation':
            node['orientation'] = np.array(axis_angle_quaternion([float(v) for v in row[1:5]]))
        elif node is not None and word == 'scale':
            node['scale'] = float(row[1])
    return rig


def compare_static(a, b, tol):
    """Hierarchy, node types and bind transforms; quaternions up to sign."""
    differences = []; position = rotation = 0.0
    for name in sorted(set(a) ^ set(b)):
        differences.append(f'{name}: only in {"published" if name in a else "source"}')
    for name in sorted(set(a) & set(b)):
        x, y = a[name], b[name]
        for field in ('parent', 'type'):
            if x[field] != y[field]:
                differences.append(f'{name}: {field} {x[field]} != {y[field]}')
        u, v = (q/np.linalg.norm(q) if np.linalg.norm(q) > 1e-6 else None for q in (x['orientation'], y['orientation']))
        if u is None or v is None:
            differences.append(f'{name}: zero-length bind orientation'); continue
        d = float(np.linalg.norm(x['position']-y['position'])); r = float(np.degrees(2*np.arccos(min(1., abs(float(u@v))))))
        position, rotation = max(position, d), max(rotation, r)
        if not np.isfinite([d, r]).all() or d > tol['positionMetres'] or r > tol['rotationDegrees']:
            differences.append(f'{name}: bind transform differs ({d:.3g} m, {r:.3g} deg)')
        # Static scale feeds the bind hierarchy that every pose is sampled from.
        if not (np.isfinite([x['scale'], y['scale']]).all() and f32(x['scale']) == f32(y['scale'])):
            differences.append(f'{name}: bind scale {x["scale"]:.6g} != {y["scale"]:.6g}')
    return {'nodes': len(a), 'positionMetres': position, 'rotationDegrees': rotation, 'differences': differences}


def compare(published, source, tolerances=None):
    """Published binary against a source model (ASCII or binary); both decoded by anim_library."""
    tol = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    blob_a = Path(published).read_bytes(); blob_b = Path(source).read_bytes()
    a = load_model(published, blob_a); b = load_model(source, blob_b)
    header = {k: (a[k], b[k]) for k in ('name', 'parent') if a[k] != b[k]}
    geometry = compare_static(static_rig(a, blob_a), static_rig(b, blob_b), tol)
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
        # NaN deltas would vanish in compare_clip's max() reductions, so malformed keys fail first.
        invalid = {'published': malformed(x), 'source': malformed(y)}
        r = compare_clip(x, a['name'], y, b['name'], tol['timeSeconds'])
        # The ASCII reader keeps only position/orientation keys; any other published controller (e.g. scale)
        # would go unchecked, so it fails rather than passing unseen.
        ok = (not native_only and not invalid['published'] and not invalid['source'] and r['structure'] and r['metadata']
              and r['positionMetres'] <= tol['positionMetres'] and r['rotationDegrees'] <= tol['rotationDegrees']
              and r['otherMax'] <= tol['otherControllers'])
        rows[clip] = {'status': 'equal' if ok else 'different', **{k: r[k] for k in ('structure', 'metadata', 'positionMetres', 'rotationDegrees', 'otherMax', 'eventOrderChanged')},
                      'invalidControllers': invalid, 'notComparedControllers': native_only}
        if not ok:
            failures.append(clip)
    return {'schemaVersion': 1, 'kind': KIND, 'published': {'path': str(Path(published)), 'format': a['format']},
            'source': {'path': str(Path(source)), 'format': b['format']}, 'tolerances': tol, 'headerDifferences': header,
            'staticRig': geometry, 'publishedInventory': inventory(a), 'clips': rows, 'failures': failures,
            'passed': not failures and not header and not geometry['differences'],
            'quaternionPolicy': 'unit quaternions compared up to sign',
            'assetApprovalCreated': False}
