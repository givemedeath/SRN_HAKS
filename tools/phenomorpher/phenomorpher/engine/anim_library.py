"""Shared animation libraries over the stock supermodel chain: stock extraction and inventory.

Bodies follow the stock structure (root > thin library > a_fa/a_ba chain). The inventory
records every root's chain, the nearest owner of each effective clip, static node sets,
real texture header sizes and the texture usage graph. It reads; it never rewrites assets.
"""
import hashlib
import json
import math
import re
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .native_motion import Reader

STOCK_KIND = 'PhenoMorpher-stock-models'
INVENTORY_KIND = 'PhenoMorpher-animation-inventory'
TRANSFORMS = {8: 'position', 20: 'orientation', 36: 'scale'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


class NativeModel(Reader):
    """native_motion.Reader plus node flags, clip metadata and controller byte ranges."""
    def tree(self, root):
        out = {}; seen = set(); queue = [(root, None)]
        while queue:
            off, parent = queue.pop()
            if off in seen:
                raise ValueError('Cyclic/shared child')
            seen.add(off); self.data(off, 112); name = self.text(off+32, 32); original = name
            if name in out:
                if name != 'impact':
                    raise ValueError('Ambiguous anatomical node ' + name)
                i = 2
                while name in out:
                    name = original + '__duplicate_' + str(i); i += 1
            ko, nk = self.array(off+84, 12); fo, nf = self.array(off+96, 4)
            floats = np.frombuffer(self.data(fo, nf*4), '<f4'); controls = {}
            if not np.isfinite(floats).all():
                raise ValueError('Nonfinite controller')
            for i in range(nk):
                kind, rows, to, vo, cols, _ = struct.unpack('<ihhhbb', self.data(ko+i*12, 12))
                if kind in controls or rows < 1 or cols < 1 or min(to, vo) < 0 or to+rows > nf or vo+rows*cols > nf:
                    raise ValueError('Invalid native controller')
                times = floats[to:to+rows].astype(float)
                if np.any(np.diff(times) < 0):
                    raise ValueError('Unordered keys')
                if kind in TRANSFORMS and cols != {8: 3, 20: 4, 36: 1}[kind]:
                    raise ValueError('Unsupported transform interpolation')
                controls[kind] = {'times': times, 'values': floats[vo:vo+rows*cols].reshape(rows, cols).astype(float),
                    'timeRange': (12+fo+4*to, 12+fo+4*(to+rows)), 'dataRange': (12+fo+4*vo, 12+fo+4*(vo+rows*cols))}
            out[name] = {'parent': parent, 'flags': self.u32(off+0x6c), 'controls': controls}
            children, n = self.array(off+72, 4)
            # Preorder in stored child order, so a rewritten model keeps the original hierarchy order.
            queue.extend(reversed([(self.u32(children+4*i), name) for i in range(n)]))
        return out

    def decode(self):
        nodes = self.tree(self.u32(72)); clips = {}; pointers, count = self.array(120, 4)
        for i in range(count):
            at = self.u32(pointers+4*i); self.data(at, 0xc4); name = self.text(at+8, 64)
            length, transition = struct.unpack('<ff', self.data(at+0x70, 8))
            events_at, events_count = self.array(at+0xb8, 36)
            events = [[float(struct.unpack('<f', self.data(events_at+36*j, 4))[0]), self.text(events_at+36*j+4, 32)]
                      for j in range(events_count)]
            if name in clips or not np.isfinite([length, transition, *(t for t, _ in events)]).all() or length < 0:
                raise ValueError('Invalid animation ' + name)
            clips[name] = {'length': float(length), 'transition': float(transition), 'animroot': self.text(at+0x78, 64),
                           'events': events, 'eventsRange': (12+events_at, 12+events_at+36*events_count),
                           'nodes': self.tree(self.u32(at+72))}
        return {'format': 'binary', 'name': self.text(8, 64), 'parent': self.text(0xa8, 64),
                'scale': float(struct.unpack('<f', self.data(0xa4, 4))[0]), 'nodes': nodes, 'clips': clips}


def axis_angle_quaternion(row):
    x, y, z, angle = row; norm = math.sqrt(x*x+y*y+z*z)
    if norm < 1e-12 or abs(angle) < 1e-12:
        return [0.0, 0.0, 0.0, 1.0]
    s = math.sin(angle/2)/norm
    return [x*s, y*s, z*s, math.cos(angle/2)]


def ascii_model(text):
    """Minimal ASCII reader: header, geometry node tree and keyed position/orientation clips."""
    model = {'format': 'ascii', 'name': '', 'parent': 'null', 'scale': 1.0, 'nodes': {}, 'clips': {}}
    target = model['nodes']; clip = None; node = None; key = None
    for raw in text.splitlines():
        row = raw.split('#', 1)[0].split()
        if not row:
            continue
        word = row[0].lower()
        if key is not None:
            if word == 'endlist' or len(key['rows']) == key['count']:
                kind = key['kind']; rows = np.array(key['rows'], float)
                values = rows[:, 1:] if kind == 8 else np.array([axis_angle_quaternion(r) for r in rows[:, 1:]])
                node['controls'][kind] = {'times': rows[:, 0], 'values': values}
                key = None
                if word == 'endlist':
                    continue
            else:
                key['rows'].append([float(v) for v in row]); continue
        if word == 'newmodel':
            model['name'] = row[1].lower()
        elif word == 'setsupermodel':
            model['parent'] = row[2].lower()
        elif word == 'setanimationscale':
            model['scale'] = float(row[1])
        elif word == 'newanim':
            clip = {'length': 0.0, 'transition': 0.0, 'animroot': '', 'events': [], 'nodes': {}}
            model['clips'][row[1].lower()] = clip; target = clip['nodes']
        elif word == 'doneanim':
            clip = None; target = model['nodes']
        elif clip is not None and word in ('length', 'transtime'):
            clip['length' if word == 'length' else 'transition'] = float(row[1])
        elif clip is not None and word == 'animroot':
            clip['animroot'] = row[1].lower()
        elif clip is not None and word == 'event':
            clip['events'].append([float(row[1]), row[2].lower()])
        elif word == 'node':
            name = original = row[2].lower(); i = 2
            while name in target:
                if original != 'impact':
                    raise ValueError('Ambiguous anatomical node ' + name)
                name = original + '__duplicate_' + str(i); i += 1
            node = target[name] = {'parent': None, 'type': row[1].lower(), 'controls': {}}
        elif word == 'endnode':
            node = None
        elif node is not None and word == 'parent':
            node['parent'] = None if row[1].lower() == 'null' else row[1].lower()
        elif node is not None and clip is not None and word in ('positionkey', 'orientationkey'):
            key = {'kind': 8 if word == 'positionkey' else 20, 'rows': [], 'count': int(row[1]) if len(row) > 1 else -1}
    if not model['name']:
        raise ValueError('ASCII model name missing')
    return model


def load_model(path):
    blob = Path(path).read_bytes()
    return NativeModel(blob).decode() if blob[:4] == b'\0\0\0\0' else ascii_model(blob.decode('cp1252'))


def controller_signature(nodes):
    """Hash of every node's controller kinds, key times and values (exact float32 payload)."""
    h = hashlib.sha256()
    for name in sorted(nodes):
        for kind in sorted(nodes[name]['controls']):
            c = nodes[name]['controls'][kind]
            h.update(f'{name}:{kind}:'.encode()); h.update(np.asarray(c['times'], '<f4').tobytes())
            h.update(np.asarray(c['values'], '<f4').tobytes())
    return h.hexdigest()


def extract_stock(resman_cat, game_root, seeds, output):
    """Extract stock models with --no-ovr, following each seed's supermodel chain to NULL."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    tool = Path(resman_cat).resolve(); models = {}; pending = [s.lower() for s in seeds]
    with tempfile.TemporaryDirectory(prefix='pheno-empty-user-') as user:
        while pending:
            name = pending.pop(0)
            if name in models or name == 'null':
                continue
            data = subprocess.run([str(tool), '--root', str(game_root), '--userdirectory', user, '--no-ovr', name+'.mdl'],
                                  check=True, capture_output=True).stdout
            if not data:
                raise ValueError('Installed stock model unavailable: ' + name)
            (output/(name+'.mdl')).write_bytes(data); model = load_model(output/(name+'.mdl'))
            models[name] = {'path': name+'.mdl', 'sha256': digest(data), 'bytes': len(data),
                            'format': model['format'], 'parent': model['parent']}
            pending.append(model['parent'])
    manifest = {'schemaVersion': 1, 'kind': STOCK_KIND, 'seeds': sorted(s.lower() for s in seeds),
                'resmanCat': {'path': str(tool), 'sha256': digest(tool.read_bytes())}, 'gameRoot': str(Path(game_root)),
                'override': False, 'models': models}
    (output/'stock-models.json').write_text(json.dumps(manifest, indent=1)+'\n', encoding='utf-8', newline='\n')
    return manifest


def stock_files(path):
    """Verified stock model paths from an extraction manifest."""
    path = Path(path); data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('kind') != STOCK_KIND or data.get('schemaVersion') != 1:
        raise ValueError('Stock model manifest required')
    files = {}
    for name, row in data['models'].items():
        file = (path.parent/row['path']).resolve()
        if digest(file.read_bytes()) != row['sha256']:
            raise ValueError('Stock model changed: ' + name)
        files[name] = file
    return data, files


def texture_header(path):
    data = Path(path).read_bytes()[:24]
    if path.suffix.lower() == '.plt':
        if data[:8] != b'PLT V1  ':
            raise ValueError('Invalid PLT header: ' + str(path))
        return {'format': 'plt', 'width': struct.unpack_from('<I', data, 16)[0], 'height': struct.unpack_from('<I', data, 20)[0]}
    if path.suffix.lower() == '.tga':
        image_type, = struct.unpack_from('<B', data, 2); width, height, bits = struct.unpack_from('<HHB', data, 12)
        return {'format': 'tga', 'imageType': image_type, 'width': width, 'height': height, 'bitsPerPixel': bits}
    return None


def material_textures(path):
    return {m[0].lower(): m[1].lower() for m in re.findall(r'(?mi)^\s*(texture\d)\s+(\S+)', Path(path).read_text(encoding='cp1252'))}


def chain(root, models):
    """Root-first supermodel chain; every link must resolve."""
    names = [root]
    while models[names[-1]]['parent'] != 'null':
        parent = models[names[-1]]['parent']
        if parent in names:
            raise ValueError('Cyclic supermodel chain at ' + parent)
        if parent not in models:
            raise ValueError('Inventory gap: unresolved supermodel ' + parent)
        names.append(parent)
    return names


def effective(names, models):
    """Nearest owner of each clip along the chain, with its stored duplicates."""
    owners = {}
    for name in names:
        for clip in models[name]['clips']:
            owners.setdefault(clip, []).append(name)
    return {clip: {'owner': rows[0], 'shadowed': rows[1:]} for clip, rows in sorted(owners.items())}


ROOT = '@root'


def keyed(clip, model):
    """Keyed nodes with the owning model's root renamed to @root (carriers rename the stock root)."""
    return {ROOT if n == model else n: row['controls'] for n, row in clip['nodes'].items() if row['controls']}


def f32(value):
    return float(np.float32(value))


STOCK_ROOTS = {'a_ba', 'a_fa'}


def clip_row(clip, model):
    """Comparable clip metadata. Carriers renamed the stock root node but kept animroot a_ba/a_fa,
    so a root alias that names no node of the clip resolves to @root; the raw value is retained."""
    controls = keyed(clip, model); root = clip['animroot']
    alias = root == model or (root in STOCK_ROOTS and root not in clip['nodes'])
    events = [[f32(t), e] for t, e in clip['events']]
    return {'length': f32(clip['length']), 'transition': f32(clip['transition']),
            'animroot': ROOT if alias else root, 'animrootRaw': root, 'events': events, 'eventSet': sorted(events),
            'keyedNodes': sorted(controls),
            'controllerSignature': controller_signature({n: {'controls': c} for n, c in controls.items()})}


def compare_clip(a, a_model, b, b_model, time_tolerance=1e-5):
    """Structure equality and worst key deltas (metres, degrees) between two clips."""
    ra, rb = clip_row(a, a_model), clip_row(b, b_model)
    # Simultaneous events fire together, so their order is recorded but not structural.
    meta = all(ra[k] == rb[k] for k in ('length', 'transition', 'animroot', 'eventSet', 'keyedNodes'))
    ca, cb = keyed(a, a_model), keyed(b, b_model); structure = meta; position = rotation = other = 0.0
    for node in set(ca) & set(cb):
        if set(ca[node]) != set(cb[node]):
            structure = False; continue
        for kind, x in ca[node].items():
            y = cb[node][kind]
            if x['values'].shape != y['values'].shape or np.abs(np.asarray(x['times'])-np.asarray(y['times'])).max() > time_tolerance:
                structure = False; continue
            if kind == 20:
                u = x['values']/np.linalg.norm(x['values'], axis=1)[:, None]; v = y['values']/np.linalg.norm(y['values'], axis=1)[:, None]
                rotation = max(rotation, float(np.degrees(2*np.arccos(np.clip(np.abs((u*v).sum(1)), 0, 1))).max()))
            elif kind == 8:
                position = max(position, float(np.linalg.norm(x['values']-y['values'], axis=1).max()))
            else:
                other = max(other, float(np.abs(x['values']-y['values']).max()))
    return {'identical': ra['controllerSignature'] == rb['controllerSignature'] and meta and ra['events'] == rb['events'],
            'eventOrderChanged': ra['eventSet'] == rb['eventSet'] and ra['events'] != rb['events'], 'structure': structure,
            'metadata': meta, 'positionMetres': position, 'rotationDegrees': rotation, 'otherMax': other}


RIG_ROLES = ('fitted-rig', 'rig-inheritance', 'animation-library')


def release_models(root, manifest, stock, stock_paths):
    """Decoded pack rigs/carriers plus the installed stock chain; pack resources shadow stock names."""
    models = {}; origins = {}
    for row in manifest['resources']:
        if row['role'] in RIG_ROLES:
            name = Path(row['path']).stem.lower(); models[name] = load_model(root/row['path'])
            origins[name] = {'origin': 'pack', 'path': row['path'], 'sha256': row['sha256'], 'role': row['role']}
    for name, path in stock_paths.items():
        if name not in models:
            models[name] = load_model(path)
            origins[name] = {'origin': 'installed-game', 'path': 'stock:' + stock['models'][name]['path'],
                             'sha256': stock['models'][name]['sha256']}
    return models, origins


def inventory(root, manifest_path, stock_manifest):
    root = Path(root).resolve(); manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    stock, stock_paths = stock_files(stock_manifest)
    resources = {Path(r['path']).name.lower(): r for r in manifest['resources']}
    models, origins = release_models(root, manifest, stock, stock_paths)
    stock_effective = {}
    for seed in stock['seeds']:
        names = chain(seed, models)
        if any(origins[n]['origin'] != 'installed-game' for n in names):
            raise ValueError('Stock chain resolves through a pack override: ' + seed)
        stock_effective[seed] = {'chain': names, 'clips': {c: {'owner': r['owner'], **clip_row(models[r['owner']]['clips'][c], r['owner'])}
                                                           for c, r in effective(names, models).items()}}
    def stock_comparison(clip, owner, seed):
        if seed not in stock_effective or clip not in stock_effective[seed]['clips']:
            return None
        stock_owner = stock_effective[seed]['clips'][clip]['owner']
        return {'seed': seed, 'owner': stock_owner, **compare_clip(models[owner]['clips'][clip], owner,
                                                                   models[stock_owner]['clips'][clip], stock_owner)}
    targets = []; used = set()
    for target in manifest['targets']:
        prefix = target['modelPrefix']; names = chain(prefix, models); used.update(names)
        # Stock donors: females inherit a_fa, males a_ba.
        seed = 'a_fa' if prefix[1] == 'f' else 'a_ba'
        clips = effective(names, models)
        private = [n for n in names[1:] if origins[n]['origin'] == 'pack' and origins[n]['role'] != 'animation-library']
        stored = sum(len(models[n]['clips']) for n in private)
        targets.append({'target': target['target'], 'root': prefix, 'rootScale': models[prefix]['scale'], 'chain': names,
            'privateCarriers': private, 'storedPrivateClips': stored, 'effectiveClips': len(clips),
            'libraries': [n for n in names[1:] if origins[n].get('role') == 'animation-library'],
            'rootNodes': sorted(models[prefix]['nodes']),
            # Clip metadata lives with its owner; rows keep the owner, payload signature and stock deltas.
            'clips': {c: {'owner': r['owner'], 'shadowed': r['shadowed'],
                          'controllerSignature': clip_row(models[r['owner']]['clips'][c], r['owner'])['controllerSignature'],
                          'stock': stock_comparison(c, r['owner'], seed)} for c, r in clips.items()}})
    carriers = {n: {**origins[n], 'parent': models[n]['parent'], 'scale': models[n]['scale'], 'clips': sorted(models[n]['clips']),
                    'nodes': sorted(models[n]['nodes'])} for n in sorted(models) if origins[n]['origin'] == 'pack'
                and origins[n]['role'] == 'rig-inheritance'}
    libraries = sorted(n for n in models if origins[n].get('role') == 'animation-library')
    unused = sorted(n for n in carriers if n not in used)
    textures = {}
    for name, row in sorted(resources.items()):
        if row['role'] in ('selected-palette', 'selected-map'):
            textures[name] = {'path': row['path'], 'sha256': row['sha256'], 'bytes': row['bytes'], **texture_header(root/row['path'])}
    materials = {name: {'path': row['path'], 'textures': material_textures(root/row['path'])}
                 for name, row in sorted(resources.items()) if row['role'] == 'selected-material'}
    def locate(texture):
        hits = [n for n in (texture+'.plt', texture+'.tga', texture+'.dds') if n in textures]
        return hits[0] if hits else 'installed-game:' + texture
    usage = []
    for row in manifest['modelDependencies']:
        if row['role'] != 'body-part':
            continue
        for bitmap, _, _, material in row['textureSlots']:
            # Player body parts take the palette named after the part model; texture0 is not consulted.
            own = row['model'].lower() + '.plt'
            entry = {'model': row['model'], 'storedTexture0': bitmap.lower(),
                     'bitmapResource': own if own in textures else locate(bitmap.lower()) if bitmap else None,
                     'material': material.lower() or None}
            if material:
                mtr = materials.get(material.lower()+'.mtr')
                entry['materialResource'] = mtr['path'] if mtr else 'installed-game:' + material.lower() + '.mtr'
                entry['materialTextures'] = {k: locate(v) for k, v in (mtr or {'textures': {}})['textures'].items()}
            usage.append(entry)
    referenced = {e['bitmapResource'] for e in usage} | {v for e in usage for v in e.get('materialTextures', {}).values()}
    return {'schemaVersion': 1, 'kind': INVENTORY_KIND, 'contractVersion': manifest['version'],
            'stockModels': {n: stock['models'][n] for n in sorted(stock['models'])}, 'stockEffective': stock_effective,
            'targets': targets, 'privateCarriers': carriers, 'unusedPrivateCarriers': unused,
            'textures': textures, 'materials': materials, 'textureUsage': usage,
            'unreferencedTextures': sorted(set(textures) - referenced),
            'summary': {'animationLibraries': libraries, 'privateCarriers': len(carriers), 'privateCarrierBytes': sum(resources[n+'.mdl']['bytes'] for n in carriers),
                'storedPrivateClips': sum(len(c['clips']) for c in carriers.values()),
                'texturesAbove1024': sorted(n for n, t in textures.items() if max(t['width'], t['height']) > 1024)},
            'assetApprovalCreated': False}


# Library build: stock-structured thin library over a_fa/a_ba, compiled by the EE client,
# then restored to the exact source controller payload bytes.

PLAN_KIND = 'PhenoMorpher-library-restoration-plan'
DEFAULT_TOLERANCES = {'positionMetres': 1e-4, 'rotationDegrees': 0.05, 'assembledDriftMetres': 1e-3}
PARENT_FIELD = (12+0xa8, 12+0xa8+64)


def original_name(name):
    return name.split('__duplicate_')[0]


def quaternion_axis_angle(q):
    x, y, z, w = np.asarray(q, float)/np.linalg.norm(q)
    if w < 0:
        x, y, z, w = -x, -y, -z, -w
    s = math.sqrt(max(0.0, 1-w*w))
    return [1.0, 0.0, 0.0, 0.0] if s < 1e-9 else [x/s, y/s, z/s, 2*math.acos(min(1.0, w))]


def fmt(values):
    # Nine significant digits round-trip every float32.
    return ' '.join('%.9g' % float(v) for v in values)


def ascii_node(lines, name, node, pad, keyed):
    parent = original_name(node['parent']) if node['parent'] else 'NULL'
    lines += [f'{pad}node dummy {original_name(name)}', f'{pad}  parent {parent}']
    for kind, word in ((8, 'position'), (20, 'orientation')):
        if kind not in node['controls']:
            continue
        c = node['controls'][kind]
        convert = (lambda r: r) if kind == 8 else quaternion_axis_angle
        if keyed:
            lines.append(f'{pad}  {word}key')
            lines += [f'{pad}    {fmt([t, *convert(r)])}' for t, r in zip(c['times'], c['values'])]
            lines.append(f'{pad}  endlist')
        else:
            lines.append(f'{pad}  {word} {fmt(convert(c["values"][0]))}')
    lines.append(f'{pad}endnode')


def library_text(name, parent, scale, geometry, clips):
    lines = [f'newmodel {name}', f'setsupermodel {name} {parent}', 'classification character',
             f'setanimationscale {fmt([scale])}', f'beginmodelgeom {name}']
    for node, row in geometry.items():
        ascii_node(lines, node, row, '', False)
    lines.append(f'endmodelgeom {name}')
    for clip_name, clip in clips.items():
        lines += [f'newanim {clip_name} {name}', f'  length {fmt([clip["length"]])}',
                  f'  transtime {fmt([clip["transition"]])}', f'  animroot {clip["animroot"]}']
        lines += [f'  event {fmt([t])} {e}' for t, e in clip['events']]
        for node, row in clip['nodes'].items():
            ascii_node(lines, node, row, '  ', True)
        lines.append(f'doneanim {clip_name} {name}')
    lines.append(f'donemodel {name}')
    return '\n'.join(lines) + '\n'


def preorder(nodes):
    """Hierarchy preorder, children in insertion order: the order the compiler writes."""
    children = {}
    for name, row in nodes.items():
        children.setdefault(row['parent'], []).append(name)
    order = []; stack = list(reversed(children.get(None, [])))
    while stack:
        name = stack.pop(); order.append(name); stack.extend(reversed(children.get(name, [])))
    if len(order) != len(nodes):
        raise ValueError('Library node tree is not a single rooted hierarchy')
    return {name: nodes[name] for name in order}


def rename(nodes, old, new):
    return {(new if n == old else n): {**row, 'parent': new if row['parent'] == old else row['parent']} for n, row in nodes.items()}


def assembled_drift(rig, rig_root, a, a_model, b, b_model):
    """Worst world-position difference of any rig node between two clips at keys, midpoints and ends."""
    from .native_motion import sample, sample_times
    first = {(rig_root if n == a_model else n): row for n, row in a['nodes'].items()}
    second = {(rig_root if n == b_model else n): row for n, row in b['nodes'].items()}
    worst = {'metres': 0.0, 'node': None, 'time': None}
    for time in sorted(set(sample_times(a)) | set(sample_times(b))):
        wa = sample(rig, first, time); wb = sample(rig, second, time)
        for node in rig:
            d = float(np.linalg.norm(wa[node][:3, 3]-wb[node][:3, 3]))
            if d > worst['metres']:
                worst = {'metres': d, 'node': node, 'time': float(time)}
    return worst


def clips_equal(a, a_model, b, b_model):
    """Exact payload, metadata and stored event order."""
    ra, rb = clip_row(a, a_model), clip_row(b, b_model)
    return all(ra[k] == rb[k] for k in ('length', 'transition', 'animrootRaw', 'events', 'keyedNodes', 'controllerSignature'))


def classify(models, rigs, owner, stock_owner, clip, tolerances):
    source = models[owner]['clips'][clip]
    if stock_owner is None:
        return {'inherit': False, 'reason': 'not in stock'}
    stock = models[stock_owner]['clips'][clip]
    result = compare_clip(source, owner, stock, stock_owner)
    within = (result['structure'] and result['positionMetres'] <= tolerances['positionMetres']
              and result['rotationDegrees'] <= tolerances['rotationDegrees'])
    result['assembledDrift'] = None
    if within:
        drifts = {r: assembled_drift(models[r]['nodes'], r, source, owner, stock, stock_owner) for r in rigs}
        result['assembledDrift'] = drifts
        within = max(d['metres'] for d in drifts.values()) <= tolerances['assembledDriftMetres']
    result['inherit'] = within
    result['reason'] = 'within tolerance' if within else 'override'
    return result


def build(root, manifest_path, stock_manifest, fit, large, name, output, allowed=(), tolerances=None):
    """Classify the Fit chain against stock and write the library ASCII plus a restoration plan."""
    tolerances = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    root = Path(root).resolve(); output = Path(output)
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    if len(name) > 15 or not re.fullmatch(r'[a-z0-9_]+', name):
        raise ValueError('Library resource name must be a lowercase resref')
    stock, stock_paths = stock_files(stock_manifest); models, origins = release_models(root, manifest, stock, stock_paths)
    if large[1] != fit[1]:
        raise ValueError('Fit and Large roots must share a gender')
    seed = 'a_fa' if fit[1] == 'f' else 'a_ba'
    fit_chain, large_chain = chain(fit, models), chain(large, models)
    fit_clips, large_clips = effective(fit_chain, models), effective(large_chain, models)
    if set(fit_clips) != set(large_clips):
        raise ValueError('Fit and Large clip sets differ')
    differences = sorted(c for c in fit_clips if not clips_equal(
        models[fit_clips[c]['owner']]['clips'][c], fit_clips[c]['owner'],
        models[large_clips[c]['owner']]['clips'][c], large_clips[c]['owner']))
    if set(differences) - set(allowed):
        raise ValueError('Unauthorized Fit/Large difference: ' + ', '.join(sorted(set(differences)-set(allowed))))
    stock_clips = effective(chain(seed, models), models)
    rows = {}
    for clip, row in fit_clips.items():
        stock_owner = stock_clips.get(clip, {}).get('owner')
        rows[clip] = {'owner': row['owner'], 'stockOwner': stock_owner,
                      **classify(models, (fit, large), row['owner'], stock_owner, clip, tolerances)}
    carrier, large_carrier = fit_chain[1], large_chain[1]
    if origins[carrier]['origin'] != 'pack' or origins[large_carrier]['origin'] != 'pack':
        raise ValueError('Fit and Large roots must use private carriers')
    geometry = rename(models[carrier]['nodes'], carrier, name)
    other = rename(models[large_carrier]['nodes'], large_carrier, name)
    if list(other) != list(geometry) or any(geometry[n]['parent'] != other[n]['parent'] for n in geometry):
        raise ValueError('Fit and Large carrier node trees differ')
    retained = [c for c in fit_clips if not rows[c]['inherit']]
    clips = {}; sources = {n: (carrier, carrier if n == name else n) for n in geometry}
    # Library nodes are dummies: carrier meshes keep only their static position/orientation.
    dropped = {n: sorted(set(row['controls']) - {8, 20}) for n, row in geometry.items()}
    geometry = {n: {**row, 'controls': {k: v for k, v in row['controls'].items() if k in (8, 20)}} for n, row in geometry.items()}
    for clip in retained:
        owner = rows[clip]['owner']; source = models[owner]['clips'][clip]
        nodes = rename(source['nodes'], owner, name)
        # Deeper carriers add nodes (e.g. belt_pelvis); take them, as dummies, from the owner's own tree.
        for node in nodes:
            if node not in geometry:
                row = models[owner]['nodes'].get(node)
                if row is None or row['parent'] not in rename(models[owner]['nodes'], owner, name):
                    raise ValueError('Clip node missing from library geometry: ' + clip)
                added = rename({node: row}, owner, name)[node]
                dropped[node] = sorted(set(added['controls']) - {8, 20})
                geometry[node] = {**added, 'controls': {k: v for k, v in added['controls'].items() if k in (8, 20)}}
                sources[node] = (owner, node)
                if geometry[node]['parent'] not in geometry:
                    raise ValueError('Added library node has no parent in the library: ' + node)
        if any(set(n['controls']) - {8, 20} for n in nodes.values()):
            raise ValueError('Unsupported clip controller: ' + clip)
        clips[clip] = {**source, 'nodes': nodes}
    geometry = preorder(geometry)
    if any(set(row['controls']) - {8, 20} or any(len(c['times']) != 1 for c in row['controls'].values())
           for row in geometry.values()):
        raise ValueError('Library geometry must be static position/orientation dummies')
    text = library_text(name, seed, models[carrier]['scale'], geometry, clips)
    ascii_dir = output/'converted/ascii'; ascii_dir.mkdir(parents=True, exist_ok=False)
    (output/'converted/resources').mkdir()
    (ascii_dir/(name+'.mdl')).write_text(text, encoding='ascii', newline='\n')
    if ascii_model(text)['clips'].keys() != clips.keys():
        raise ValueError('Library ASCII does not round-trip its clip set')
    owners = sorted({s for s, _ in sources.values()} | {rows[c]['owner'] for c in retained})
    plan = {'schemaVersion': 1, 'kind': PLAN_KIND, 'library': name, 'parent': seed, 'scale': models[carrier]['scale'],
            'ascii': {'path': 'converted/ascii/' + name + '.mdl', 'sha256': digest(text.encode('ascii'))},
            'sources': {o: {'path': origins[o]['path'], 'sha256': origins[o]['sha256']} for o in owners},
            'geometry': {'carrier': carrier, 'nodes': {n: list(sources[n]) for n in geometry},
                         'droppedStaticMeshControllers': {n: k for n, k in dropped.items() if k}},
            'clips': {c: {'source': rows[c]['owner'],
                          'nodes': {n: (rows[c]['owner'] if n == name else n) for n in clips[c]['nodes']}} for c in retained}}
    classification = {'schemaVersion': 1, 'kind': 'PhenoMorpher-library-classification', 'library': name, 'parent': seed,
                      'fit': {'root': fit, 'chain': fit_chain}, 'large': {'root': large, 'chain': large_chain},
                      'fitLargeDifferences': differences, 'authorizedFitClips': sorted(allowed), 'tolerances': tolerances,
                      'retained': len(retained), 'inherited': len(fit_clips)-len(retained), 'clips': rows,
                      'assetApprovalCreated': False}
    (output/'restoration-plan.json').write_text(json.dumps(plan, indent=1)+'\n', encoding='utf-8', newline='\n')
    (output/'classification.json').write_text(json.dumps(classification, indent=1)+'\n', encoding='utf-8', newline='\n')
    return classification


def restore(root, plan_path, compiled_path, output):
    """Copy the exact source controller bytes into the compiled library; layouts must match."""
    root = Path(root).resolve(); plan_path = Path(plan_path); plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('kind') != PLAN_KIND:
        raise ValueError('Library restoration plan required')
    if digest((plan_path.parent/plan['ascii']['path']).read_bytes()) != plan['ascii']['sha256']:
        raise ValueError('Library ASCII changed after planning')
    output = Path(output)
    if output.exists():
        raise ValueError('Fresh restored library output required')
    compiled = Path(compiled_path).read_bytes(); blob = bytearray(compiled); model = NativeModel(compiled).decode()
    if (model['name'], model['parent']) != (plan['library'], plan['parent']):
        raise ValueError('Compiled library name or supermodel differs')
    sources = {}
    for owner, pin in plan['sources'].items():
        data = (root/pin['path']).read_bytes()
        if digest(data) != pin['sha256']:
            raise ValueError('Restoration source changed: ' + owner)
        sources[owner] = (data, NativeModel(data).decode())
    ranges = []; before = [0.0]; reordered = []
    def copy(target, data, source, label):
        if set(target) != set(source):
            raise ValueError('Compiled controller kinds differ: ' + label)
        for kind in source:
            t, s = target[kind], source[kind]
            if t['values'].shape != s['values'].shape or len(t['times']) != len(s['times']):
                raise ValueError(f'Compiled controller layout differs: {label} {kind}')
            before[0] = max(before[0], float(np.abs(t['values']-s['values']).max()), float(np.abs(t['times']-s['times']).max()))
            for field in ('timeRange', 'dataRange'):
                (a, b), (c, d) = t[field], s[field]
                blob[a:b] = data[c:d]; ranges.append((a, b))
    if list(model['nodes']) != list(plan['geometry']['nodes']):
        raise ValueError('Compiled library geometry differs')
    for node, (owner, original) in plan['geometry']['nodes'].items():
        data, source = sources[owner]
        transforms = {k: v for k, v in source['nodes'][original]['controls'].items() if k in (8, 20)}
        copy(model['nodes'][node]['controls'], data, transforms, 'geometry ' + node)
    if set(model['clips']) != set(plan['clips']):
        raise ValueError('Compiled library clip set differs')
    for clip, row in plan['clips'].items():
        data, source = sources[row['source']]; target = model['clips'][clip]
        if list(target['nodes']) != list(row['nodes']):
            raise ValueError('Compiled clip node tree differs: ' + clip)
        for node, name in row['nodes'].items():
            copy(target['nodes'][node]['controls'], data, source['clips'][clip]['nodes'][name]['controls'], f'{clip} {node}')
        # The compiler sorts simultaneous events; restore the stored order of an identical event set.
        original = source['clips'][clip]
        if sorted(target['events']) != sorted(original['events']):
            raise ValueError('Compiled events differ: ' + clip)
        if target['events'] != original['events']:
            (a, b), (c, d) = target['eventsRange'], original['eventsRange']
            blob[a:b] = data[c:d]; ranges.append((a, b)); reordered.append(clip)
    restored = bytes(blob); mask = np.zeros(len(blob), bool)
    for a, b in ranges:
        mask[a:b] = True
    changed = np.frombuffer(restored, np.uint8) != np.frombuffer(compiled, np.uint8)
    if (changed & ~mask).any():
        raise ValueError('Restoration changed bytes outside controller and event ranges')
    result = NativeModel(restored).decode()
    for clip, row in plan['clips'].items():
        if not clips_equal(result['clips'][clip], plan['library'], sources[row['source']][1]['clips'][clip], row['source']):
            raise ValueError('Restored clip differs from its source: ' + clip)
    for node, (owner, original) in plan['geometry']['nodes'].items():
        ours = result['nodes'][node]['controls']; theirs = sources[owner][1]['nodes'][original]['controls']
        if any(not np.array_equal(np.float32(ours[k]['values']), np.float32(theirs[k]['values'])) for k in theirs if k in (8, 20)):
            raise ValueError('Restored geometry differs from its source: ' + node)
    output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(restored)
    receipt = {'schemaVersion': 1, 'kind': 'PhenoMorpher-library-restoration', 'library': plan['library'],
               'plan': {'sha256': digest(plan_path.read_bytes())}, 'compiled': {'sha256': digest(compiled), 'bytes': len(compiled)},
               'restored': {'sha256': digest(restored), 'bytes': len(restored)}, 'restoredRanges': len(ranges),
               'restoredBytes': int(mask.sum()), 'changedBytes': int(changed.sum()), 'maxCompileDifference': before[0], 'eventOrderRestored': reordered,
               'clips': len(plan['clips']), 'exactSourcePayload': True, 'assetApprovalCreated': False}
    output.with_suffix('.restoration.json').write_text(json.dumps(receipt, indent=1)+'\n', encoding='utf-8', newline='\n')
    return receipt


def repoint(blob, parent):
    """Change only the fixed-width supermodel field of a native root."""
    data = parent.lower().encode('ascii')
    if not 0 < len(data) < 64:
        raise ValueError('Supermodel name must fit the native field')
    before = NativeModel(blob).decode(); a, b = PARENT_FIELD
    result = blob[:a] + data.ljust(64, b'\0') + blob[b:]
    after = NativeModel(result).decode()
    if after['parent'] != parent.lower() or after['name'] != before['name'] or len(result) != len(blob):
        raise ValueError('Root repoint changed more than the supermodel field')
    return result
