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
            queue.extend((self.u32(children+4*i), name) for i in range(n))
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
                           'events': events, 'nodes': self.tree(self.u32(at+72))}
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


def inventory(root, manifest_path, stock_manifest):
    root = Path(root).resolve(); manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    stock, stock_paths = stock_files(stock_manifest)
    resources = {Path(r['path']).name.lower(): r for r in manifest['resources']}
    rigs = [r for r in manifest['resources'] if r['role'] in ('fitted-rig', 'rig-inheritance')]
    models = {}; origins = {}
    for row in rigs:
        name = Path(row['path']).stem.lower(); models[name] = load_model(root/row['path'])
        origins[name] = {'origin': 'pack', 'path': row['path'], 'sha256': row['sha256']}
    for name, path in stock_paths.items():
        if name not in models:
            models[name] = load_model(path); origins[name] = {'origin': 'installed-game', 'path': 'stock:' + stock['models'][name]['path'],
                                                              'sha256': stock['models'][name]['sha256']}
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
        clips = effective(names, models); private = [n for n in names[1:] if origins[n]['origin'] == 'pack']
        stored = sum(len(models[n]['clips']) for n in private)
        targets.append({'target': target['target'], 'root': prefix, 'rootScale': models[prefix]['scale'], 'chain': names,
            'privateCarriers': private, 'storedPrivateClips': stored, 'effectiveClips': len(clips),
            'rootNodes': sorted(models[prefix]['nodes']),
            # Clip metadata lives with its owner; rows keep the owner, payload signature and stock deltas.
            'clips': {c: {'owner': r['owner'], 'shadowed': r['shadowed'],
                          'controllerSignature': clip_row(models[r['owner']]['clips'][c], r['owner'])['controllerSignature'],
                          'stock': stock_comparison(c, r['owner'], seed)} for c, r in clips.items()}})
    carriers = {n: {**origins[n], 'parent': models[n]['parent'], 'scale': models[n]['scale'], 'clips': sorted(models[n]['clips']),
                    'nodes': sorted(models[n]['nodes'])} for n in sorted(models) if origins[n]['origin'] == 'pack' and n not in
                {t['modelPrefix'] for t in manifest['targets']}}
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
            'summary': {'privateCarriers': len(carriers), 'privateCarrierBytes': sum(resources[n+'.mdl']['bytes'] for n in carriers),
                'storedPrivateClips': sum(len(c['clips']) for c in carriers.values()),
                'texturesAbove1024': sorted(n for n, t in textures.items() if max(t['width'], t['height']) > 1024)},
            'assetApprovalCreated': False}
