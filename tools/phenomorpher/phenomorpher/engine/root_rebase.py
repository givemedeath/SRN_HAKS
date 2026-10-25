"""Fold an offset model-root translation into the root's children, in place and exactly.

Stock rigs keep the model root at the origin and the compiler drops root-node transforms, so a
root offset (non-Human bodies and their libraries) moves into every direct root child: its static
geometry position and every clip key of its position. Only those float32 payloads change; the
receipt proves the byte mask and that bind and clip world frames are unchanged.
"""
import copy
import json
from pathlib import Path

import numpy as np

from .anim_library import RIG_ROLES, NativeModel, contained, digest, effective
from .native_motion import sample, sample_times

KIND = 'PhenoMorpher-root-rebase'
LIBRARY_ROLE = 'animation-library'
TOLERANCE = 1e-6


def stored(blob, span):
    a, b = span
    return np.frombuffer(blob[a:b], '<f4').copy()


def root_offset(model, blob):
    """The root's stored float32 position, or None at the origin; refuses root transforms it cannot fold."""
    name = model['name']; root = model['nodes'].get(name)
    if root is None or next(iter(model['nodes'])) != name or root['parent'] is not None:
        raise ValueError('Model root node is not named like the model: ' + name)
    controls = root['controls']; position = controls.get(8)
    if position is None or not np.any(stored(blob, position['dataRange'])):
        return None
    if len(position['times']) != 1:
        raise ValueError('Root position is keyed more than once: ' + name)
    if 36 in controls:
        raise ValueError('Root has a scale controller: ' + name)
    if 20 in controls and (len(controls[20]['times']) != 1 or np.abs(controls[20]['values'][0]-[0, 0, 0, 1]).max() > 1e-7):
        raise ValueError('Root orientation is not identity: ' + name)
    return stored(blob, position['dataRange'])


def root_children(model):
    return [n for n, row in model['nodes'].items() if row['parent'] == model['name']]


def keys_root(model):
    """Clips that key the root node or a direct root child's position (both move with a rebase)."""
    name = model['name']; children = set(root_children(model)); hits = []
    for clip_name, clip in model['clips'].items():
        tree = clip['nodes']; top = next(iter(tree))
        if tree[top]['controls'] or any(8 in row['controls'] for n, row in tree.items()
                                        if n in children or row['parent'] == top):
            hits.append(clip_name)
    return hits


def plan(model, offset):
    """Patch list [(byte range, new float32 values)]; root children come from the geometry tree."""
    name = model['name']; nodes = model['nodes']; children = root_children(model)
    patches = [(nodes[name]['controls'][8]['dataRange'], None)]
    for child in children:
        position = nodes[child]['controls'].get(8)
        if position is None or len(position['times']) != 1:
            raise ValueError(f'Root child has no static position: {name} {child}')
        patches.append((position['dataRange'], offset))
    keyed = 0
    for clip_name, clip in model['clips'].items():
        tree = clip['nodes']; top = next(iter(tree))
        if top != name:
            raise ValueError(f'Clip root is not the model root: {name} {clip_name}')
        if tree[top]['controls']:
            raise ValueError(f'Clip keys the model root: {name} {clip_name}')
        for node, row in tree.items():
            if node in children and row['parent'] != top:
                raise ValueError(f'Clip moves a root child under another parent: {clip_name} {node}')
            if 8 not in row['controls']:
                continue
            if node in children:
                patches.append((row['controls'][8]['dataRange'], offset)); keyed += 1
            elif row['parent'] == top:
                raise ValueError(f'Clip keys a root-level node outside the geometry: {clip_name} {node}')
    return patches, keyed


def apply(blob, patches):
    """Patched bytes, the patched-byte mask and the worst float32 rounding of value + offset."""
    out = bytearray(blob); mask = np.zeros(len(blob), bool); rounding = 0.0
    for (a, b), offset in patches:
        if mask[a:b].any():
            raise ValueError('Patched controller ranges overlap')
        mask[a:b] = True; old = np.frombuffer(blob[a:b], '<f4')
        if offset is None:
            new = np.zeros(len(old), '<f4')
        else:
            rows = old.reshape(-1, 3); new = (rows + offset).astype('<f4')
            rounding = max(rounding, float(np.abs(new.astype(float) - (rows.astype(float) + offset.astype(float))).max()))
        out[a:b] = new.tobytes()
    out = bytes(out)
    changed = np.frombuffer(out, np.uint8) != np.frombuffer(blob, np.uint8)
    if (changed & ~mask).any():
        raise ValueError('Rebase changed bytes outside the patched controllers')
    return out, mask, changed, rounding


def same_controls(before, after, patched, label):
    """Every unpatched controller is unchanged and every time row is untouched."""
    for node, row in before.items():
        if node not in after or set(after[node]['controls']) != set(row['controls']):
            raise ValueError('Rebase changed the controller layout: ' + label)
        for kind, c in row['controls'].items():
            d = after[node]['controls'][kind]
            if not np.array_equal(c['times'], d['times']):
                raise ValueError(f'Rebase changed key times: {label} {node}')
            if c['dataRange'] not in patched and not np.array_equal(c['values'], d['values']):
                raise ValueError(f'Rebase changed an unpatched controller: {label} {node} {kind}')


def top(rig, root):
    """The root and its direct children. same_controls proves every other controller byte-identical, so
    equal world frames here mean equal world frames for the whole tree below them."""
    return {n: row for n, row in rig.items() if n == root or row['parent'] == root}


def bind_difference(a, b, root):
    """Worst world-matrix element change below the root (the root itself moves to the origin)."""
    a, b = top(a, root), top(b, root)
    wa, wb = sample(a, {}, 0.), sample(b, {}, 0.)
    return max(float(np.abs(wa[n]-wb[n]).max()) for n in a if n != root)


def clip_difference(rig_before, rig_after, rig_root, before, after, owner):
    """Worst rig world-position change for one clip, applied with its owner root renamed to the rig root."""
    rig_before, rig_after = top(rig_before, rig_root), top(rig_after, rig_root)
    first = {(rig_root if n == owner else n): row for n, row in before['nodes'].items()}
    second = {(rig_root if n == owner else n): row for n, row in after['nodes'].items()}
    worst = {'metres': 0.0, 'node': None, 'time': None}
    for time in sample_times(before):
        wa = sample(rig_before, first, time); wb = sample(rig_after, second, time)
        for node in (n for n in rig_before if n != rig_root):
            d = float(np.linalg.norm(wa[node][:3, 3]-wb[node][:3, 3]))
            if d > worst['metres']:
                worst = {'metres': d, 'node': node, 'time': float(time)}
    return worst


def rebase(root, manifest_path, output, version):
    """Stage root-rebased rigs/libraries, the next contract and a receipt in a fresh folder."""
    from .runtime_rules import check
    root = Path(root).resolve(); output = Path(output)
    if output.exists():
        raise ValueError('Fresh output required')
    raw = Path(manifest_path).read_bytes(); manifest = json.loads(raw.decode('utf-8-sig'))
    blobs, models, rows = {}, {}, {}
    for row in manifest['resources']:
        if row['role'] not in RIG_ROLES:
            continue
        blob = contained(root, row['path']).read_bytes(); name = Path(row['path']).stem.lower()
        if digest(blob) != row['sha256']:
            raise ValueError('Published model differs from the contract: ' + row['path'])
        if name in models:
            raise ValueError('Duplicate published model: ' + name)
        model = NativeModel(blob).decode()
        if model['name'] != name:
            raise ValueError('Model name differs from its resource: ' + row['path'])
        blobs[name], models[name], rows[name] = blob, model, row
    offsets = {n: root_offset(m, blobs[n]) for n, m in models.items()}
    rebased = sorted(n for n, o in offsets.items() if o is not None)
    if not rebased:
        raise ValueError('No published model root carries an offset')
    # Each target's pack links up to the first installed link; the rig's own geometry drives world frames.
    targets, reached = {}, set()
    for target in manifest['targets']:
        prefix = target['modelPrefix'].lower()
        if prefix not in models:
            raise ValueError('Target root is not a published rig: ' + prefix)
        links = [prefix]
        while models[links[-1]]['parent'] in models:
            if models[links[-1]]['parent'] in links:
                raise ValueError('Cyclic supermodel chain at ' + prefix)
            links.append(models[links[-1]]['parent'])
        if not any(offsets[n] is not None for n in links):
            continue
        own = offsets[prefix]
        for n in links:
            if (n in rebased or rows[n]['role'] == LIBRARY_ROLE) and (own is None or offsets[n] is None
                                                                      or not np.array_equal(offsets[n], own)):
                raise ValueError(f'Root offsets disagree: {prefix} and {n}')
        if not any(rows[n]['role'] == LIBRARY_ROLE for n in links):
            raise ValueError('Rebased target reaches the installed chain without a library: ' + prefix)
        # Installed and carrier clips stay relative to the old root, so none may key what moves.
        for n in links[1:]:
            if rows[n]['role'] != LIBRARY_ROLE and keys_root(models[n]):
                raise ValueError(f'Carrier {n} in the chain of {prefix} keys the root or a root child: '
                                 + ', '.join(keys_root(models[n])[:5]))
        targets[prefix] = links; reached.update(n for n in links if n in rebased)
    if set(rebased) - reached:
        raise ValueError('Offset roots reached by no rebased target: ' + ', '.join(sorted(set(rebased) - reached)))
    after_blobs, after_models, records = {}, {}, {}
    for name in rebased:
        patches, keyed = plan(models[name], offsets[name])
        blob, mask, changed, rounding = apply(blobs[name], patches)
        model = NativeModel(blob).decode(); patched = {span for span, _ in patches}
        if root_offset(model, blob) is not None:
            raise ValueError('Rebased root is not at the origin: ' + name)
        same_controls(models[name]['nodes'], model['nodes'], patched, name + ' geometry')
        if set(model['clips']) != set(models[name]['clips']):
            raise ValueError('Rebase changed the clip set: ' + name)
        for clip_name, clip in models[name]['clips'].items():
            same_controls(clip['nodes'], model['clips'][clip_name]['nodes'], patched, f'{name} {clip_name}')
        bind = bind_difference(models[name]['nodes'], model['nodes'], name)
        if bind > TOLERANCE:
            raise ValueError(f'Rebase moved the bind frames of {name}: {bind}')
        after_blobs[name], after_models[name] = blob, model
        records[name] = {'path': rows[name]['path'], 'role': rows[name]['role'], 'offset': offsets[name].astype(float).tolist(),
                         'fromSHA256': rows[name]['sha256'], 'toSHA256': digest(blob), 'bytes': len(blob),
                         'patchedControllers': len(patches), 'patchedClipKeyControllers': keyed,
                         'patchedBytes': int(mask.sum()), 'changedBytes': int(changed.sum()),
                         'maxFloat32Rounding': rounding, 'bindWorstElement': bind}
    # Equivalence: each target's bind and every clip a rebased link owns, before vs after, for every node below the root.
    equivalence = {}
    for prefix, links in sorted(targets.items()):
        new = {n: after_models.get(n, models[n]) for n in links}
        bind = bind_difference(models[prefix]['nodes'], new[prefix]['nodes'], prefix)
        worst = {'metres': 0.0, 'clip': None, 'node': None, 'time': None}; count = 0
        for clip_name, row in effective(links, models).items():
            owner = row['owner']
            if owner not in after_models:
                continue
            drift = clip_difference(models[prefix]['nodes'], new[prefix]['nodes'], prefix,
                                    models[owner]['clips'][clip_name], new[owner]['clips'][clip_name], owner)
            count += 1
            if drift['metres'] > worst['metres']:
                worst = {'metres': drift['metres'], 'clip': clip_name, 'node': drift['node'], 'time': drift['time']}
        if bind > TOLERANCE or worst['metres'] > TOLERANCE:
            raise ValueError(f'Rebase moved world frames of {prefix}: bind {bind}, clip {worst}')
        equivalence[prefix] = {'chain': links, 'bindWorstElement': bind, 'clips': count, 'worstClipDrift': worst}
    staged = copy.deepcopy(manifest); staged['version'] = version
    for row in staged['resources']:
        name = Path(row['path']).stem.lower()
        if row['role'] in RIG_ROLES and name in records:
            row['sha256'] = records[name]['toSHA256']; row['bytes'] = records[name]['bytes']
            row['rootRebase'] = {'offset': records[name]['offset'], 'fromSHA256': records[name]['fromSHA256']}
    rules = check(root, staged, overlay={rows[n]['path']: after_blobs[n] for n in rebased})
    if not rules['passed']:
        raise ValueError('Rebased release breaks the runtime rules: ' + json.dumps(rules['violations'][:5]))
    receipt = {'schemaVersion': 1, 'kind': KIND, 'version': version,
               'contract': {'sha256': digest(raw), 'version': manifest.get('version')}, 'tolerance': TOLERANCE,
               'models': records, 'equivalence': equivalence,
               'runtimeRules': {k: rules[k] for k in ('mode', 'violationCounts', 'passed')},
               # Installed stock clips are not read here; only pack-owned clips are proven.
               'installedClipsChecked': False,
               'summary': {'version': version, 'models': len(records), 'targets': len(equivalence),
                           'worstBindElement': max(e['bindWorstElement'] for e in equivalence.values()),
                           'worstClipMetres': max(e['worstClipDrift']['metres'] for e in equivalence.values()),
                           'maxFloat32Rounding': max(r['maxFloat32Rounding'] for r in records.values()),
                           'runtimeRulesPassed': True},
               'assetApprovalCreated': False}
    output.mkdir(parents=True, exist_ok=False)
    for name in rebased:
        path = output/'files'/rows[name]['path']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after_blobs[name])
    for file, data in (('game-ready-assets.json', staged), ('root-rebase-receipt.json', receipt)):
        (output/file).write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8', newline='\n')
    return receipt
