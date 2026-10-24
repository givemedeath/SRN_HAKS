"""Maintained, isolated Sling packages with a whole mesh per Color.

The source profile supplies a verified effective content stack, not the firearm's
fit. Fitting/appearance reviews remain upstream gates. Compilation never launches
an interactive game session. All placeholder and Color resources are audited.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
from PIL import Image

from tools.headkit.common import ROOT, asset, pin, read, require, verify, write, verification_pass
from .contracts import native_contract, resref, source_version, code_pins
from .firearms import plan, private_override, sling_row, validate_assembly
from .firearm_native import placeholder_geometry, placeholder_ascii, audit_placeholder, variant_blueprint, mesh_flags, audit_blueprint_roundtrip
from .native import ascii_model, sanitize_and_audit, archive_helpers


def stack_inputs(profile_path):
    """Enumerate only the effective namespace and selected resource evidence."""
    from .native_stack import namespace
    profile = read(profile_path)
    stack = asset(profile_path, profile['native']['stack'])
    result = [pin(profile_path), stack]
    for layer in read(stack['path'])['layers']:
        result += namespace(stack['path'], layer)[2]
        result += [asset(stack['path'], row['file']) for row in layer['resources']]
    return result


def specification_inputs(spec_path):
    spec = read(spec_path)
    result = [pin(spec_path), spec['sourceProfile'], *spec.get('comparisonHaks', [])]
    verify(result)
    result += stack_inputs(spec['sourceProfile']['path'])
    for row in spec['variants']:
        result += [row[key] for key in ('arrays', 'texture', 'icon')]
    verify(result)
    return result


def prepare(spec_path, output):
    """Prepare all Color resources from final, individually bound corner arrays."""
    started = time.perf_counter()
    with verification_pass('firearm-prepare'):
        inputs = specification_inputs(spec_path)+code_pins()
        spec = read(spec_path)
        require(spec.get('schemaVersion') == 1, 'Unsupported firearm package specification')
        require(set(spec) <= {'schemaVersion', 'sourceProfile', 'comparisonHaks', 'variants',
                             'subtype', 'identity', 'placeholderCenter'}, 'Unknown package specification field')
        identity = spec['identity']
        require(set(identity) == {'texturePrefix', 'blueprintPrefix', 'hak', 'module', 'displayName'},
                'Explicit firearm resource identity required')
        for key in ('texturePrefix', 'blueprintPrefix', 'hak', 'module'): resref(identity[key])
        require(isinstance(identity['displayName'], str) and identity['displayName'].strip(), 'Display name required')
        profile_path = spec['sourceProfile']['path']
        _, resources = native_contract(profile_path, read(profile_path))
        original = resources['baseitems.2da']
        table = Path(original['path']).read_bytes()
        _, row = sling_row(table)
        icon_size = (int(row['InvSlotWidth'])*32, int(row['InvSlotHeight'])*32)
        require(icon_size == (32, 64), 'Review changed Sling inventory dimensions')
        archive = archive_helpers()
        occupied = set(resources)
        type_extensions = {value: key for key, value in {**archive.TYPES, '2da': 2017, 'uti': 2025}.items()}
        for hak in spec.get('comparisonHaks', []):
            for name, kind in archive.payload(hak['path']):
                require(kind in type_extensions, 'Unsupported comparison HAK resource type')
                occupied.add(name.lower()+'.'+type_extensions[kind])
        variants = spec['variants']
        require(variants and all(set(v) == {'colour', 'displayName', 'arrays', 'texture', 'icon'} for v in variants),
                'Each Color needs a name and bound arrays, texture and icon')
        allocation = plan(spec['subtype'], [v['colour'] for v in variants], occupied,
                          identity['texturePrefix'], identity['blueprintPrefix'])
        override, override_report = private_override(table, allocation)
        placeholder = placeholder_geometry(spec.get('placeholderCenter', (0, 0, 0)))
        # Validate every variant before producing a partial prepared directory.
        selected = {v['colour']: v for v in variants}
        checked = []
        for variant in allocation['variants']:
            source = selected[variant['colour']]
            with np.load(source['arrays']['path'], allow_pickle=False) as data:
                require(set(data.files) == {'positions', 'normals', 'uv', 'shadowVertices', 'shadowFaces'},
                        'Exact native corner archive required')
                counts = {p: {'visible': 4, 'shadow': 0} for p in ('b', 'm', 't')}
                counts[allocation['slot']] = {'visible': len(data['positions']), 'shadow': len(data['shadowFaces'])}
                validate_assembly(allocation, variant, counts)
                text = ascii_model(variant['models'][allocation['slot']], variant['texture'],
                                   **{k: data[k] for k in ('positions', 'normals', 'uv')},
                                   shadow_vertices=data['shadowVertices'], shadow_faces=data['shadowFaces'])
            for key, size, mode in (('texture', (1024, 1024), None), ('icon', icon_size, 'RGBA')):
                with Image.open(source[key]['path']) as image:
                    require(image.size == size and (mode is None or image.mode == mode),
                            'Incorrect runtime texture or multipart icon dimensions/mode')
            item = variant_blueprint(allocation, variant, counts, source['displayName'])
            checked.append((variant, source, counts, text, item))
        out = Path(output); out.mkdir(parents=True, exist_ok=False)
        (out/'ascii').mkdir(); (out/'resources').mkdir()
        (out/'resources/baseitems.2da').write_bytes(override)
        np.savez(out/'placeholder.npz', **placeholder)
        for name in allocation['placeholders']:
            (out/'ascii'/f'{name}.mdl').write_text(placeholder_ascii(name, placeholder), encoding='ascii')
            Image.new('RGBA', icon_size, (0, 0, 0, 0)).save(out/'resources'/f'i{name}.tga')
        expected = {}; counts = {}; blueprints = {}
        for variant, source, count, text, item in checked:
            name = variant['models'][allocation['slot']]
            (out/'ascii'/f'{name}.mdl').write_text(text, encoding='ascii')
            target = out/f'expected-{variant["colour"]}.npz'
            shutil.copyfile(source['arrays']['path'], target); expected[name] = pin(target)
            with Image.open(source['texture']['path']) as image:
                image.convert('RGB').save(out/'resources'/f'{variant["texture"]}.tga')
            with Image.open(source['icon']['path']) as image:
                image.save(out/'resources'/f'{variant["icons"][allocation["slot"]]}.tga')
            target = out/f'{variant["blueprint"]}.json'; write(target, item, fresh=True)
            blueprints[variant['blueprint']] = pin(target); counts[str(variant['colour'])] = count
        outputs = [pin(p) for directory in ('ascii', 'resources') for p in sorted((out/directory).iterdir())]
        result = {'schemaVersion': 1, 'kind': 'firearm-native-prepared', 'codeVersion': source_version(), 'allocation': allocation,
                  'identity': identity, 'expected': expected, 'counts': counts, 'blueprints': blueprints,
                  'placeholder': pin(out/'placeholder.npz'), 'intentionalOverride': override_report,
                  'effectiveBaseitems': original, 'inheritedSlingFields': row, 'iconSize': list(icon_size),
                  'inputs': inputs, 'outputs': outputs, 'elapsedSeconds': time.perf_counter()-started,
                  'clientValidated': False, 'productionAccepted': False}
    # A separate pass checks fresh bytes at completion, never a timestamp cache.
    verify(inputs)
    write(out/'prepared.json', result, fresh=True)
    return result


def prepared_inputs(prepared_dir):
    prepared_dir = Path(prepared_dir); prepared = read(prepared_dir/'prepared.json')
    require(prepared.get('kind') == 'firearm-native-prepared', 'Expected firearm preparation')
    require(prepared.get('codeVersion') == source_version(), 'Stale firearm preparation code')
    result = [pin(prepared_dir/'prepared.json'), prepared['placeholder'], *prepared['inputs'],
              *prepared['outputs'], *prepared['expected'].values(), *prepared['blueprints'].values()]
    verify(result)
    return result


def native_inputs(native_path):
    data = read(native_path)
    require(data.get('kind') == 'firearm-native-package', 'Expected firearm native package')
    require(data.get('codeVersion') == source_version(), 'Stale firearm native package code')
    result = [pin(native_path), data['hak'], *data['inputs'], *data['resources']]
    verify(result)
    return result


def compile_package(prepared_dir, client, output):
    from tools.phenotypes import tool_runtime
    started = time.perf_counter()
    prepared_dir = Path(prepared_dir)
    with verification_pass('firearm-native-dispatch'):
        inputs = prepared_inputs(prepared_dir)+[client]
        verify(inputs)
        prepared = read(prepared_dir/'prepared.json')
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    converted = out/'converted'; shutil.copytree(prepared_dir, converted)
    command = [sys.executable, '-B', str(ROOT/'tools/phenotypes/native_compile.py'), '--client', client['path'],
               '--user-directory', str(out/'compiler-userdir'), '--converted', str(converted), '--timeout', '120']
    result = subprocess.run(command, capture_output=True, text=True, timeout=450,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (out/'compiler.log').write_text(result.stdout+'\n'+result.stderr, encoding='utf-8')
    require(result.returncode == 0, 'Native compilation failed; retain log and reconcile before retry')
    res = converted/'resources'; allocation = prepared['allocation']; audits = {}
    with np.load(prepared['placeholder']['path'], allow_pickle=False) as data:
        expected_placeholder = {k: data[k] for k in data.files}
    for name in allocation['placeholders']:
        target = res/(name+'.mdl'); clean, audit = audit_placeholder(target, name, expected_placeholder)
        target.write_bytes(clean); audits[name] = audit
    blueprints = []
    gff = tool_runtime.tool('nwn_gff', inputs=[p['path'] for p in inputs])
    for variant in allocation['variants']:
        name = variant['models'][allocation['slot']]; target = res/(name+'.mdl')
        clean, audit = sanitize_and_audit(target, name, variant['texture'], prepared['expected'][name])
        require(mesh_flags(clean, name) == {name+'v': {'render': 1, 'shadow': 0},
                                           name+'s': {'render': 0, 'shadow': 1}}, 'Incorrect native visibility flags')
        target.write_bytes(clean); audits[name] = audit
        source = prepared['blueprints'][variant['blueprint']]; target = res/(variant['blueprint']+'.uti')
        readback = out/(variant['blueprint']+'-readback.json')
        for args in (['-i', source['path'], '-o', str(target)], ['-i', str(target), '-o', str(readback)]):
            done = subprocess.run([str(gff), *args], capture_output=True, text=True, timeout=120,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            require(done.returncode == 0, 'Blueprint conversion failed: '+done.stderr[-1000:])
        audit = audit_blueprint_roundtrip(target, read(readback), read(source['path']))
        blueprints.append({'file': pin(target), 'colour': variant['colour'], 'utiParts': variant['utiParts'], 'audit': audit})
    expected_names = set(allocation['resources']) | {'baseitems.2da'}
    require({p.name for p in res.iterdir()} == expected_names, 'Missing or unexpected firearm payload resource')
    archive = archive_helpers(); types = {**archive.TYPES, '2da': 2017, 'uti': 2025}
    files = sorted(res.iterdir()); hak = out/(prepared['identity']['hak']+'.hak')
    archive.write_hak(hak, [(p.stem, types[p.suffix[1:]], p.read_bytes()) for p in files])
    require(archive.payload(hak) == {(p.stem, types[p.suffix[1:]]): pin(p)['sha256'] for p in files},
            'Exact firearm HAK payload differs')
    verify(inputs)
    result = {'schemaVersion': 1, 'kind': 'firearm-native-package', 'codeVersion': prepared['codeVersion'], 'hak': pin(hak),
              'baseItem': 61, 'allocation': allocation,
              'identity': {**prepared['identity'], 'blueprint': allocation['variants'][0]['blueprint']},
              'blueprints': blueprints, 'counts': prepared['counts'], 'audits': audits,
              'intentionalOverride': prepared['intentionalOverride'], 'inputs': inputs,
              'resources': [pin(p) for p in files], 'elapsedSeconds': time.perf_counter()-started,
              'clientValidated': False, 'productionAccepted': False}
    write(out/'native.json', result, fresh=True)
    return result
