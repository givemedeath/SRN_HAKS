"""Diffuse composite item export and exact native roundtrip verification."""
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
from PIL import Image
from tools.headkit.common import ROOT, pin, read, require, verify, write
from tools.headkit.native_reader import decode
from .contracts import PARTS, resref, native_contract, reserve
from .geometry import topology, check_budgets


def archive_helpers():
    sys.path.insert(0, str(ROOT/'tools/heads'))
    import verify_head_hak
    return verify_head_hak


def ascii_model(name, texture, positions, normals, uv, shadow_vertices, shadow_faces):
    resref(name); resref(texture)
    p, n, tex = np.asarray(positions), np.asarray(normals), np.asarray(uv)
    require(p.ndim == 3 and p.shape[1:] == (3, 3) and n.shape == p.shape and tex.shape == (*p.shape[:2], 2)
            and np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(tex).all(), 'Finite per-corner native attributes required')
    require(np.all((tex >= 0) & (tex <= 1)), 'Atlas UVs outside [0,1]')
    require(np.allclose(np.linalg.norm(n, axis=2), 1, atol=1e-4), 'Unit authored normals required')
    require(topology(shadow_vertices, shadow_faces)['closedWound'], 'Closed, outward shadow proxy required')
    lines = [f'newmodel {name}', f'setsupermodel {name} NULL', 'classification ITEM', 'setanimationscale 1',
             f'beginmodelgeom {name}', f'node dummy {name}', '  parent NULL', 'endnode']
    def node(label, vertices, norms, coords, faces, render, shadow, bitmap):
        lines.extend([f'node trimesh {label}', f'  parent {name}', '  position 0 0 0', '  orientation 0 0 0 0',
            '  ambient 1 1 1', '  diffuse 1 1 1', '  specular 0 0 0', '  shininess 0',
            f'  bitmap {bitmap}', f'  render {render}', f'  shadow {shadow}'])
        for heading, rows in (('verts', vertices), ('normals', norms), ('tverts', np.c_[coords, np.zeros(len(coords))])):
            lines.append(f'  {heading} {len(rows)}')
            lines.extend('    '+' '.join(format(float(v), '.17g') for v in row) for row in rows)
        lines.append(f'  faces {len(faces)}')
        lines.extend(f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in faces)
        lines.append('endnode')
    node(name+'v', p.reshape(-1, 3), n.reshape(-1, 3), tex.reshape(-1, 2), np.arange(p.size//3).reshape(-1, 3), 1, 0, texture)
    sp = np.asarray(shadow_vertices)[shadow_faces]
    sn = np.cross(sp[:, 1]-sp[:, 0], sp[:, 2]-sp[:, 0]); sn /= np.linalg.norm(sn, axis=1)[:, None]
    node(name+'s', sp.reshape(-1, 3), np.repeat(sn, 3, axis=0), np.zeros((sp.size//3, 2)),
         np.arange(sp.size//3).reshape(-1, 3), 0, 1, 'NULL')
    lines += [f'endmodelgeom {name}', f'donemodel {name}']
    return '\n'.join(lines)+'\n'


def prepare(profile_path, profile, arrays, texture, icons, output, index=None):
    native, resources = native_contract(profile_path, profile)
    allocation = reserve(profile, resources, index)
    output = Path(output); (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    texture_name = profile.get('resources', {}).get('texturePrefix', 'sr_cfl')+'_'+str(allocation['modelIndex']).zfill(2)
    require(not any(texture_name+suffix in resources for suffix in ('.tga', '.dds', '.mtr', '.txi')), 'Texture resref collision')
    with Image.open(texture) as image:
        require(image.size == (profile['runtimeTextureSize'],)*2, 'Runtime texture size differs from family')
        image.convert('RGB').save(output/'resources'/f'{texture_name}.tga')
    counts = {'visible': {}, 'shadow': {}}; expected = {}
    for part in PARTS:
        verify([arrays[part], icons[part]])
        with np.load(arrays[part]['path'], allow_pickle=False) as values:
            require(set(values.files) == {'positions', 'normals', 'uv', 'shadowVertices', 'shadowFaces'}, 'Unexpected native corner archive')
            content = {name: values[name] for name in values.files}
            counts['visible'][part] = len(content['positions']); counts['shadow'][part] = len(content['shadowFaces'])
            name = allocation['models'][part]
            text = ascii_model(name, texture_name, content['positions'], content['normals'], content['uv'],
                               content['shadowVertices'], content['shadowFaces'])
            (output/'ascii'/f'{name}.mdl').write_text(text, encoding='ascii')
        with Image.open(icons[part]['path']) as image:
            require(image.mode == 'RGBA' and image.size[0] % 32 == image.size[1] % 32 == 0,
                    'Native inventory icons require RGBA and dimensions in 32-pixel cells')
            image.save(output/'resources'/f"{allocation['icons'][part]}.tga")
        target = output/f'expected-{part}.npz'; shutil.copyfile(arrays[part]['path'], target); expected[part] = pin(target)
    for kind in counts: check_budgets(counts[kind], profile['budgets'], kind)
    result = {'allocation': allocation, 'baseItem': native['baseItem'], 'texture': texture_name,
              'expected': expected, 'budgets': counts, 'clientValidated': False, 'productionAccepted': False}
    if profile.get('resources'): result['identity'] = profile['resources']
    result['inputs'] = [pin(profile_path), pin(texture)]+list(arrays.values())+list(icons.values())
    result['outputs'] = [pin(p) for folder in ('ascii', 'resources') for p in sorted((output/folder).iterdir())]
    write(output/'prepared.json', result, fresh=True)
    return result


def sanitize_and_audit(binary, name, texture, expected):
    sys.path.insert(0, str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine.stock_armor import sanitize_binary, string_fields, leaked_text
    raw = Path(binary).read_bytes(); clean = sanitize_binary(raw)
    allowed = np.zeros(len(raw), bool)
    for offset, count in string_fields(raw): allowed[offset:offset+count] = True
    changed = np.frombuffer(raw, np.uint8) != np.frombuffer(clean, np.uint8)
    require(not changed[~allowed].any() and clean == sanitize_binary(clean) and not leaked_text(clean), 'Sanitizer changed non-string data')
    before = decode(raw, name, require_tangents=False); after = decode(clean, name, require_tangents=False)
    require(len(before) == len(after) == 2, 'One visible mesh and one shadow mesh required')
    by_name = {row['name']: row for row in after}
    require(set(by_name) == {name+'v', name+'s'}, 'Unexpected native nodes')
    require(by_name[name+'v']['textures'][0] == texture, 'Wrong diffuse dependency')
    require(all(value.lower() in ('', 'null', texture) for row in after for value in row['textures']), 'Unexpected native material dependency')
    for old, new in zip(before, after):
        for key in ('position', 'normal', 'uv', 'faces'):
            require(np.array_equal(old[key], new[key]), 'Sanitizer changed decoded attributes')
    with np.load(expected['path'], allow_pickle=False) as target:
        visible = by_name[name+'v']; shadow = by_name[name+'s']
        for native_key, source_key in (('position', 'positions'), ('normal', 'normals'), ('uv', 'uv')):
            actual = visible[native_key][visible['faces']]
            require(actual.shape == target[source_key].shape and np.allclose(actual, target[source_key], atol=2e-6, rtol=0),
                    'Native visible roundtrip mismatch: '+source_key)
        expected_shadow = target['shadowVertices'][target['shadowFaces']]
        actual_shadow = shadow['position'][shadow['faces']]
        require(actual_shadow.shape == expected_shadow.shape and np.allclose(actual_shadow, expected_shadow, atol=2e-6, rtol=0),
                'Native shadow roundtrip mismatch')
        require(topology(shadow['position'], shadow['faces'])['closedWound'], 'Compiled shadow is not closed and outward')
    return clean, {'zeroedTailBytes': int(changed.sum()), 'attributesPreserved': True, 'nativeRoundtrip': True}


def compile_package(prepared_dir, client, output):
    verify([client]); prepared_dir = Path(prepared_dir); output = Path(output); output.mkdir()
    preparation = read(prepared_dir/'prepared.json'); verify(preparation['inputs']+preparation['outputs']+list(preparation['expected'].values()))
    converted = output/'converted'; shutil.copytree(prepared_dir, converted)
    command = [sys.executable, str(ROOT/'tools/phenotypes/native_compile.py'), '--client', client['path'],
               '--user-directory', str(output/'compiler-userdir'), '--converted', str(converted), '--timeout', '120']
    result = subprocess.run(command, capture_output=True, text=True, timeout=450,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (output/'compiler.log').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    require(result.returncode == 0, 'Native compilation failed; inspect retained compiler log')
    audits = {}
    for part, name in preparation['allocation']['models'].items():
        binary = converted/'resources'/f'{name}.mdl'
        clean, audits[part] = sanitize_and_audit(binary, name, preparation['texture'], preparation['expected'][part])
        binary.write_bytes(clean)
    archive = archive_helpers(); resources = sorted((converted/'resources').iterdir())
    require(all(p.suffix in ('.mdl', '.tga') for p in resources), 'Unexpected package resources')
    entries = [(p.stem, archive.TYPES[p.suffix[1:]], p.read_bytes()) for p in resources]
    target = output/(preparation.get('identity', {}).get('hak', 'srn_cougar_test')+'.hak'); archive.write_hak(target, entries)
    require(archive.payload(target) == {(p.stem, archive.TYPES[p.suffix[1:]]): pin(p)['sha256'] for p in resources}, 'HAK payload mismatch')
    verify([client]+preparation['inputs']+preparation['outputs'], fresh=True)
    result = {'hak': pin(target), 'resources': [pin(p) for p in resources], 'audits': audits,
              'allocation': preparation['allocation'], 'baseItem': preparation['baseItem'],
              'clientValidated': False, 'productionAccepted': False}
    if preparation.get('identity'): result['identity'] = preparation['identity']
    write(output/'native.json', result, fresh=True)
    return result
