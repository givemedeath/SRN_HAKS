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
