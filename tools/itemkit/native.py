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


EXTRA_RESOURCE_TYPES = {'2da': 2017, 'uti': 2025}


def archive_helpers():
    sys.path.insert(0, str(ROOT/'tools/heads'))
    import verify_head_hak
    return verify_head_hak


def write_verified_hak(target, files):
    archive = archive_helpers(); types = {**archive.TYPES, **EXTRA_RESOURCE_TYPES}
    archive.write_hak(target, [(p.stem, types[p.suffix[1:]], p.read_bytes()) for p in files])
    require(archive.payload(target) == {(p.stem, types[p.suffix[1:]]): pin(p)['sha256'] for p in files}, 'HAK payload mismatch')


def compile_with_client(converted, client, output):
    command = [sys.executable, '-B', str(ROOT/'tools/phenotypes/native_compile.py'), '--client', client['path'],
               '--user-directory', str(output/'compiler-userdir'), '--converted', str(converted), '--timeout', '120']
    result = subprocess.run(command, capture_output=True, text=True, timeout=450,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (output/'compiler.log').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    require(result.returncode == 0, 'Native compilation failed; retain log and reconcile before retry')


def blueprint_roundtrip(gff, source, binary, readback):
    """Convert JSON to UTI and back, returning the audit of what the tool wrote."""
    from .firearm_native import audit_blueprint_roundtrip
    for first, second in ((source, binary), (binary, readback)):
        done = subprocess.run([str(gff), '-i', str(first), '-o', str(second)], capture_output=True, text=True, timeout=120,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        require(done.returncode == 0, 'Blueprint conversion failed: '+done.stderr[-1000:])
    return audit_blueprint_roundtrip(binary, read(readback), read(source))


def pad_icon(image, canvas):
    """Place a logical footprint at the top left of its stock power-of-two canvas."""
    padded = Image.new('RGBA', tuple(canvas), (0, 0, 0, 0)); padded.paste(image, (0, 0))
    return padded


def offline_compiler_inputs(compiler):
    """Declared installed compiler bytes; no client or automatic fallback."""
    from tools.phenomorpher.phenomorpher.engine import neverblender_mdl
    addon=Path(compiler['neverblender']['path'])
    require(len(compiler.get('sha256',''))==64 and compiler.get('files'), 'Frozen native compiler identity required')
    for name in compiler['files']:
        require(not Path(name).is_absolute() and not Path(name).drive and '..' not in Path(name).parts,
                'Compiler file escapes its declared addon')
    return [compiler['blender']]+[{'path':str(addon/name),'sha256':value} for name,value in compiler['files'].items()]+[
        pin(neverblender_mdl.__file__),pin(neverblender_mdl.WORKER)]


def compile_offline(converted, compiler, output):
    from tools.phenomorpher.phenomorpher.engine import neverblender_mdl
    report=neverblender_mdl.compile_folder(compiler['blender']['path'],compiler['neverblender']['path'],converted,
                                         expected_identity=compiler['sha256'])
    write(Path(output)/'compiler.json',report,fresh=True)
    return report


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


def prepare(profile_path, profile, arrays, texture, icons, output):
    native, resources = native_contract(profile_path, profile)
    allocation = reserve(profile, resources)
    output = Path(output); (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    texture_name = allocation['texture']
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
            canvas=profile['native'].get('iconCanvasDimensions',{}).get(part)
            if canvas:
                require(list(image.size)==profile['native']['iconDimensions'][part]
                        and len(canvas)==2 and all(type(v)is int and v>0 and v&(v-1)==0 for v in canvas)
                        and canvas[0]>=image.width and canvas[1]>=image.height,'Invalid native icon padding contract')
                image=pad_icon(image,canvas)
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


def sanitize_proof(raw):
    """Clear string tails, proving nothing else changed; returns the bytes and changed-byte count."""
    sys.path.insert(0, str(ROOT/'tools/phenomorpher'))
    from phenomorpher.engine.stock_armor import sanitize_binary, string_fields, leaked_text
    clean = sanitize_binary(raw)
    allowed = np.zeros(len(raw), bool)
    for offset, count in string_fields(raw): allowed[offset:offset+count] = True
    changed = np.frombuffer(raw, np.uint8) != np.frombuffer(clean, np.uint8)
    require(not changed[~allowed].any() and clean == sanitize_binary(clean) and not leaked_text(clean), 'Sanitizer changed non-string data')
    return clean, int(changed.sum())


def sanitize_and_decode(binary, name, *, allow_constant_alpha=False, apply_rigid_transforms=False):
    """Shared string-tail sanitization; material-node audits remain route-specific."""
    raw = Path(binary).read_bytes(); clean, changed = sanitize_proof(raw)
    options={'require_tangents':False,'allow_constant_alpha':allow_constant_alpha,
             'apply_rigid_transforms':apply_rigid_transforms}
    before = decode(raw, name, **options); after = decode(clean, name, **options)
    require(len(before)==len(after),'Sanitizer changed the native mesh inventory')
    for old,new in zip(before,after):
        require(old['name']==new['name'] and old['textures']==new['textures']
                and old.get('alpha')==new.get('alpha'),'Sanitizer changed native material identity')
        for key in ('position','normal','uv','faces'):
            require(np.array_equal(old[key],new[key]),'Sanitizer changed decoded attributes')
    return clean,after,changed


def sanitize_and_audit(binary, name, texture, expected):
    clean,after,changed=sanitize_and_decode(binary,name)
    require(len(after) == 2, 'One visible mesh and one shadow mesh required')
    by_name = {row['name']: row for row in after}
    require(set(by_name) == {name+'v', name+'s'}, 'Unexpected native nodes')
    from .firearm_native import mesh_flags
    require(mesh_flags(clean, name) == {name+'v': {'render': 1, 'shadow': 0},
                                       name+'s': {'render': 0, 'shadow': 1}}, 'Incorrect native visibility flags')
    require(by_name[name+'v']['textures'][0] == texture, 'Wrong diffuse dependency')
    require(all(value.lower() in ('', 'null', texture) for row in after for value in row['textures']), 'Unexpected native material dependency')
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
    return clean, {'zeroedTailBytes': changed, 'attributesPreserved': True, 'nativeRoundtrip': True}


def compile_package(prepared_dir, client, output):
    tool_inputs=[client]
    verify(tool_inputs); prepared_dir = Path(prepared_dir); output = Path(output); output.mkdir()
    preparation = read(prepared_dir/'prepared.json'); verify(preparation['inputs']+preparation['outputs']+list(preparation['expected'].values()))
    converted = output/'converted'; shutil.copytree(prepared_dir, converted)
    compile_with_client(converted, client, output)
    audits = {}
    for part, name in preparation['allocation']['models'].items():
        binary = converted/'resources'/f'{name}.mdl'
        clean, audits[part] = sanitize_and_audit(binary, name, preparation['texture'], preparation['expected'][part])
        binary.write_bytes(clean)
    resources = sorted((converted/'resources').iterdir())
    require(all(p.suffix in ('.mdl', '.tga') for p in resources), 'Unexpected package resources')
    target = output/(preparation.get('identity', {}).get('hak', 'srn_cougar_test')+'.hak'); write_verified_hak(target, resources)
    verify(tool_inputs+preparation['inputs']+preparation['outputs'], fresh=True)
    result = {'hak': pin(target), 'resources': [pin(p) for p in resources], 'audits': audits,
              'allocation': preparation['allocation'], 'baseItem': preparation['baseItem'],
              'clientValidated': False, 'productionAccepted': False}
    if preparation.get('identity'): result['identity'] = preparation['identity']
    write(output/'native.json', result, fresh=True)
    return result
