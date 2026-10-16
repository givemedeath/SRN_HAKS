"""Stock armour parts for the PhenoMorpher bodies (clothing plan, docs/phenomorpher/clothing/plan.md).

Step 1 inventories and extracts the installed stock armour parts with overrides ignored, decompiles
them, and pins every texture they reference. Later steps fit per-part affine profiles and run the
pinned NWNArmory batch. Nothing here writes a pack or approves an asset.
"""
import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from . import silhouette_model as sil
from .anim_library import digest

KIND = 'PhenoMorpher-stock-armor-inventory'
# Armour part names as the stock model resrefs spell them.
PARTS = ('belt', 'bicepl', 'bicepr', 'chest', 'footl', 'footr', 'forel', 'forer', 'handl', 'handr',
         'legl', 'legr', 'neck', 'pelvis', 'robe', 'shinl', 'shinr', 'shol', 'shor')
# Style 001 of these parts is the bare body, which srn_body overrides; belt/shoulder 001 are real armour.
BARE = ('neck', 'chest', 'pelvis', 'bicepl', 'bicepr', 'forel', 'forer', 'handl', 'handr',
        'legl', 'legr', 'shinl', 'shinr', 'footl', 'footr')
SLOTS = tuple(f'p{g}{r}{b}' for g in 'fm' for r in 'dehog' for b in '02')
MODEL = 2002
TEXTURES = {3: '.tga', 6: '.plt', 2033: '.dds', 2036: '.mtr'}
NAME = re.compile(r'^(p[fm][a-z][0-9])_([a-z]+?)(\d{3})$')
BITMAP = re.compile(r'(?mi)^\s*(?:bitmap|texture\d|materialname)\s+(\S+)\s*$')


def key_resources(game_root):
    """{resref.ext: [key files]} for the installed models and textures (resman resolves precedence)."""
    resources = {}
    for key in sorted((Path(game_root)/'data').glob('*.key')):
        data = key.read_bytes()
        if data[:8] != b'KEY V1  ':
            raise ValueError('Unsupported key file: ' + key.name)
        _, count, _, table = struct.unpack_from('<IIII', data, 8)
        for entry in range(table, table + 22*count, 22):
            kind, _ = struct.unpack_from('<HI', data, entry + 16)
            ext = '.mdl' if kind == MODEL else TEXTURES.get(kind)
            if ext:
                name = data[entry:entry+16].rstrip(b'\0').decode('ascii').lower() + ext
                resources.setdefault(name, []).append(key.name)
    return resources


def classify(resref):
    """(slot, part, style) for a stock armour part resref, or None."""
    match = NAME.match(resref)
    if not match or match[2] not in PARTS:
        return None
    return match[1], match[2], int(match[3])


def selected(resources, slots):
    """Rigid armour part models of the slots: robes and the bare style-001 parts are excluded."""
    rows = {}
    for name in resources:
        if not name.endswith('.mdl') or not (row := classify(name[:-4])):
            continue
        slot, part, style = row
        if slot in slots and part != 'robe' and not (part in BARE and style == 1):
            rows[name] = {'slot': slot, 'part': part, 'style': style}
    return dict(sorted(rows.items()))


def fit_references(resources, slots):
    """Per slot, the stock rig and bare style-001 parts the affine profiles are fitted from (never converted)."""
    names = [f'{slot}.mdl' for slot in slots] + [f'{slot}_{part}001.mdl' for slot in slots for part in BARE]
    missing = [n for n in names if n not in resources]
    if missing:
        raise ValueError('Installed fit reference missing: ' + ', '.join(missing[:10]))
    return sorted(names)


def resman_extract(tool, game_root, names, output, batch=400):
    """Extract named resources with overrides ignored and an empty user folder, in command-line-sized batches."""
    names = sorted(names)
    with tempfile.TemporaryDirectory(prefix='pheno-empty-user-') as user:
        for start in range(0, len(names), batch):
            subprocess.run([str(tool), '--root', str(game_root), '--userdirectory', user, '--no-ovr',
                            '-d', str(output), *names[start:start+batch]], check=True, capture_output=True)
    missing = [n for n in names if not (Path(output)/n).is_file()]
    if missing:
        raise ValueError('Installed resource not extracted: ' + ', '.join(missing[:10]))


def references(text):
    """Texture and material names a decompiled model references (rendered meshes and dummies alike)."""
    return sorted({m.lower() for m in BITMAP.findall(text) if m.lower() not in ('null', '****')})


def extract(extract_tool, decompiler, game_root, output, slots=SLOTS):
    """Fresh folder: raw/ (installed bytes), ascii/ (decompiled), textures/, reference/ (stock rigs and bare
    style-001 parts, native) and stock-armor.json pins."""
    output = Path(output); slots = tuple(slots)
    if set(slots) - set(SLOTS):
        raise ValueError('Unknown body slot: ' + ', '.join(sorted(set(slots) - set(SLOTS))))
    output.mkdir(parents=True, exist_ok=False)
    resources = key_resources(game_root); models = selected(resources, slots)
    raw, ascii_dir, textures, reference = output/'raw', output/'ascii', output/'textures', output/'reference'
    for folder in (raw, ascii_dir, textures, reference):
        folder.mkdir()
    resman_extract(extract_tool, game_root, models, raw)
    fit = fit_references(resources, slots); resman_extract(extract_tool, game_root, fit, reference)
    fit_pins = {n: {'sha256': digest((reference/n).read_bytes()), 'keys': resources[n]} for n in fit}
    referenced = {}
    for name, row in models.items():
        source, target = raw/name, ascii_dir/name; data = source.read_bytes()
        if data[:4] == b'\0\0\0\0':
            result = subprocess.run([str(decompiler), '-d', '-e', str(source), str(target)], capture_output=True)
            if result.returncode or not target.is_file():
                raise ValueError('Decompile failed: ' + name + ': ' + result.stderr.decode(errors='replace'))
        else:
            target.write_bytes(data)
        text = target.read_text(encoding='cp1252')
        if 'newmodel' not in text or 'endmodelgeom' not in text:
            raise ValueError('Invalid decompiled model: ' + name)
        names = references(text)
        row.update(rawSHA256=digest(data), rawFormat='binary' if data[:4] == b'\0\0\0\0' else 'ascii',
                   asciiSHA256=digest(target.read_bytes()), references=names,
                   meshTypes=sorted({m.lower() for m in re.findall(r'(?mi)^node\s+(trimesh|danglymesh|skin|animmesh|emitter|aabb)\s', text)}))
        for ref in names:
            found = [ref + ext for ext in ('.plt', '.tga', '.dds', '.mtr') if ref + ext in resources]
            referenced[ref] = found
            row.setdefault('unresolvedReferences', [])
            if not found:
                row['unresolvedReferences'].append(ref)
    needed = sorted({f for found in referenced.values() for f in found})
    resman_extract(extract_tool, game_root, needed, textures)
    pins = {n: {'sha256': digest((textures/n).read_bytes()), 'keys': resources[n]} for n in needed}
    manifest = {'schemaVersion': 1, 'kind': KIND, 'slots': list(slots), 'override': False,
                'tools': {'resmanExtract': {'path': str(Path(extract_tool).resolve()), 'sha256': digest(Path(extract_tool).read_bytes())},
                          'decompiler': {'path': str(Path(decompiler).resolve()), 'sha256': digest(Path(decompiler).read_bytes())}},
                'excluded': {'robe': 'skinned; separate route', 'bareStyle001': list(BARE)},
                'models': models, 'textures': pins, 'fitReferences': fit_pins,
                'counts': {'models': len(models), 'textures': len(pins), 'fitReferences': len(fit_pins),
                           'danglymesh': sum('danglymesh' in r['meshTypes'] for r in models.values()),
                           'unsupportedMeshTypes': sorted({t for r in models.values() for t in r['meshTypes']} - {'trimesh', 'danglymesh'})},
                'assetApprovalCreated': False}
    (output/'stock-armor.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    return manifest


# --- Step 3: measured affine profiles -------------------------------------------------------------

PROFILE_KIND = 'PhenoMorpher-stock-armor-profiles'
# Attachment node per armour part; belt and shoulders reuse the pelvis and bicep profiles.
ATTACH = {'chest': 'torso_g', 'pelvis': 'pelvis_g', 'neck': 'neck_g', 'bicepl': 'lbicep_g', 'bicepr': 'rbicep_g',
          'forel': 'lforearm_g', 'forer': 'rforearm_g', 'handl': 'lhand_g', 'handr': 'rhand_g', 'legl': 'lthigh_g',
          'legr': 'rthigh_g', 'shinl': 'lshin_g', 'shinr': 'rshin_g', 'footl': 'lfoot_g', 'footr': 'rfoot_g',
          'belt': 'belt_g1', 'shol': 'lshoulder_g', 'shor': 'rshoulder_g'}
DERIVED = {'belt': 'pelvis', 'shol': 'bicepl', 'shor': 'bicepr'}
LONG = ('bicepl', 'bicepr', 'forel', 'forer', 'legl', 'legr', 'shinl', 'shinr')
SAMPLES = 6000
ANISOTROPY_FLAG = 2.0


def source_slot(slot):
    """Troll replaces the Gnome slot and wears Human parts of the same style and build."""
    return slot[:2] + 'h' + slot[3] if slot[2] == 'g' else slot


def surface_samples(path, count=SAMPLES, seed=7):
    """Area-weighted samples of a part's rendered triangles in its attachment frame (fixed seed).
    Stock parts are low-poly, so vertices alone leave most height bands empty."""
    skeleton, meshes = sil.decode(path); frames = sil.frames(skeleton); triangles = []
    for m in meshes:
        if m.get('render', True):
            f = frames[m['name']]; p = m['position'] @ f[:3, :3].T + f[:3, 3]; triangles.append(p[np.asarray(m['faces'])])
    if not triangles:
        raise ValueError('Part has no rendered triangles: ' + str(path))
    t = np.vstack(triangles); area = np.linalg.norm(np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]), axis=1)/2
    rng = np.random.default_rng(seed); pick = rng.choice(len(t), count, p=area/area.sum())
    u, v = rng.random(count), rng.random(count); flip = u + v > 1; u[flip], v[flip] = 1-u[flip], 1-v[flip]
    t = t[pick]
    return t[:, 0] + u[:, None]*(t[:, 1]-t[:, 0]) + v[:, None]*(t[:, 2]-t[:, 0])


def rig_frames(path):
    skeleton, _ = sil.decode(path)
    return {k.lower(): v for k, v in sil.frames(skeleton).items()}


def rings(points, count=9):
    """Centroids of equal-height bands along local z, by fraction of the 1-99% height; None when sparse."""
    h = points[:, 2]; lo, hi = np.percentile(h, [1, 99]); rows = []
    for f in (np.arange(count) + .5)/count:
        band = points[np.abs(h - (lo + f*(hi - lo))) <= (hi - lo)/count/2]
        rows.append(band.mean(0) if len(band) >= 6 else None)
    return rows


def rotation_between(a, b):
    a = a/np.linalg.norm(a); b = b/np.linalg.norm(b); v = np.cross(a, b); c = float(a @ b)
    if np.linalg.norm(v) < 1e-12:
        return np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k/(1 + c)


def degrees(rotation):
    return float(np.degrees(np.arccos(np.clip((np.trace(rotation) - 1)/2, -1, 1))))


def armory_rotate(rotation):
    """NWNArmory 1.3.4 'rotate' degrees for a rotation: it applies X, then Y, then Z, with X/Y negated."""
    b = -np.arcsin(np.clip(rotation[2, 0], -1, 1)); a = np.arctan2(rotation[1, 0], rotation[0, 0])
    c = np.arctan2(rotation[2, 1], rotation[2, 2])
    return [float(-np.degrees(c)), float(-np.degrees(b)), float(np.degrees(a))]


def nearest(a, b, chunk=400):
    return np.concatenate([np.sqrt(((a[i:i+chunk, None, :] - b[None, :, :])**2).sum(-1)).min(1) for i in range(0, len(a), chunk)])


def fit_part(stock, new, frame_rotation, axis_correction):
    """One scale -> rotate -> translate. Rotation: the joint frame change, optionally followed by the
    ring-axis correction. Scale on the stock part's own axes from 2-98% extents measured along the
    rotated axes. Translation from matched ring centroids."""
    rotation = frame_rotation
    if axis_correction:
        rs, rn = rings(stock @ frame_rotation.T), rings(new)
        ends = [i for i in range(len(rs)) if rs[i] is not None and rn[i] is not None]
        if len(ends) >= 2:
            rotation = rotation_between(rs[ends[-1]] - rs[ends[0]], rn[ends[-1]] - rn[ends[0]]) @ frame_rotation
    scale = []
    for k in range(3):
        es = np.percentile(stock[:, k], [2, 98]); en = np.percentile(new @ rotation[:, k], [2, 98])
        scale.append(float((en[1] - en[0])/(es[1] - es[0])))
    linear = rotation @ np.diag(scale); moved = stock @ linear.T
    pairs = [(a, b) for a, b in zip(rings(moved), rings(new)) if a is not None and b is not None]
    if not pairs:
        raise ValueError('No matched rings for the translation')
    translate = np.mean([b - a for a, b in pairs], axis=0)
    there, back = nearest(moved + translate, new), nearest(new, moved + translate)
    return {'linear': linear, 'rotation': rotation, 'scale': scale, 'translate': translate,
            'residualMm': {'stockToNewMean': float(there.mean()*1000), 'stockToNewP95': float(np.percentile(there, 95)*1000),
                           'newToStockMean': float(back.mean()*1000), 'newToStockP95': float(np.percentile(back, 95)*1000)}}


def profile_row(fit, frame_rotation, axis_choice, candidates):
    scale = fit['scale']; ratio = max(scale)/min(scale)
    return {'transform': {'scale': scale, 'rotate': armory_rotate(fit['rotation']), 'translate': [float(v) for v in fit['translate']]},
            'frameRotationDegrees': degrees(frame_rotation), 'axisCorrectionDegrees': degrees(fit['rotation'] @ frame_rotation.T),
            'axisCorrection': axis_choice, 'candidates': candidates, 'residualMm': fit['residualMm'],
            'anisotropy': float(ratio), 'flags': ['anisotropy'] if ratio > ANISOTROPY_FLAG else []}


def fit_profiles(root, manifest, stock_manifest, output, slots=SLOTS):
    """Measured affine per target slot x armour part, from the source slot's stock bare part to the
    published body part. Long limbs keep the ring-axis correction only when it lowers the mean residual."""
    root = Path(root).resolve(); output = Path(output)
    if output.exists():
        raise FileExistsError('Fresh output required: ' + str(output))
    contract = json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    pins = {r['path']: r['sha256'] for r in contract['resources']}
    stock_manifest = Path(stock_manifest); stock = json.loads(stock_manifest.read_text(encoding='utf-8'))
    if stock.get('kind') != KIND:
        raise ValueError('Stock armour inventory required')
    def reference(name):
        path = stock_manifest.parent/'reference'/name
        if digest(path.read_bytes()) != stock['fitReferences'][name]['sha256']:
            raise ValueError('Fit reference changed: ' + name)
        return path
    def published(name):
        path = root/'srn_body'/name
        if digest(path.read_bytes()) != pins.get('srn_body/' + name):
            raise ValueError('Published part differs from the contract: ' + name)
        return path
    rows = {}
    for slot in slots:
        src = source_slot(slot); fs = rig_frames(reference(src + '.mdl')); fn = rig_frames(published(slot + '.mdl'))
        parts = {}; fits = {}; options = {}; frame = {}
        for part in BARE:
            joint = ATTACH[part]; frame[part] = fn[joint][:3, :3].T @ fs[joint][:3, :3]
            stock_points = surface_samples(reference(f'{src}_{part}001.mdl')); new_points = surface_samples(published(f'{slot}_{part}001.mdl'))
            options[part] = {False: fit_part(stock_points, new_points, frame[part], False)}
            if part in LONG:
                options[part][True] = fit_part(stock_points, new_points, frame[part], True)
        cost = lambda part, k: options[part][k]['residualMm']['stockToNewMean'] + options[part][k]['residualMm']['newToStockMean']
        for part in BARE:
            # Left and right share one rotation mode, chosen on their summed residual, so the armour stays symmetric.
            pair = [p for p in (part[:-1] + 'l', part[:-1] + 'r') if p in options] if part in LONG else [part]
            choice = min(options[part], key=lambda k: sum(cost(p, k) for p in pair))
            candidates = {('ring-axis' if k else 'frame-only'): v['residualMm'] for k, v in options[part].items()}
            parts[part] = profile_row(options[part][choice], frame[part], 'ring-axis' if choice else 'frame-only', candidates)
            fits[part] = options[part][choice]
        for part, base in DERIVED.items():
            # Same linear map; the translation moves through the fixed offset between the two attachment nodes.
            os_ = np.linalg.inv(fs[ATTACH[base]]) @ fs[ATTACH[part]]; on = np.linalg.inv(fn[ATTACH[base]]) @ fn[ATTACH[part]]
            if degrees(os_[:3, :3]) > 1e-4 or degrees(on[:3, :3]) > 1e-4:
                raise ValueError(f'{part} attachment is rotated against {ATTACH[base]}')
            fit = fits[base]; derived = {**fit, 'translate': fit['linear'] @ os_[:3, 3] + fit['translate'] - on[:3, 3]}
            row = profile_row(derived, np.eye(3), parts[base]['axisCorrection'], parts[base]['candidates'])
            row.update(derivedFrom=base, frameRotationDegrees=parts[base]['frameRotationDegrees'],
                       attachmentOffsets={'stock': os_[:3, 3].tolist(), 'new': on[:3, 3].tolist()})
            row.pop('residualMm'); parts[part] = row
        rows[slot] = {'source': src, 'parts': parts}
    result = {'schemaVersion': 1, 'kind': PROFILE_KIND, 'contractVersion': contract['version'],
              'stockInventorySHA256': digest(stock_manifest.read_bytes()), 'samplesPerPart': SAMPLES,
              'armoryConvention': 'scale on the part axes, then rotate X, Y, Z with X/Y negated (1.3.4), then translate',
              'slots': rows, 'flagged': sorted(f'{s}:{p}' for s, r in rows.items() for p, v in r['parts'].items() if v['flags']),
              'assetApprovalCreated': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8', newline='\n')
    return result
