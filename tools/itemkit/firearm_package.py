"""Maintained, isolated Sling packages with a whole mesh per Color.

The source profile supplies a verified effective content stack, not the firearm's
fit. Fitting/appearance reviews remain upstream gates. Compilation never launches
an interactive game session. All placeholder and Color resources are audited.
"""
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image

from tools.headkit.common import pin, read, require, verify, write, verification_pass
from .contracts import native_contract, resref, source_version, code_pins, stack_inputs
from .routes import ROUTES
from .firearms import plan, longarm_plan, longarm_row, private_override, sling_row, validate_assembly
from .firearm_native import placeholder_geometry, placeholder_ascii, audit_placeholder, variant_blueprint
from .native import (EXTRA_RESOURCE_TYPES, ascii_model, archive_helpers, blueprint_roundtrip, compile_offline, compile_with_client,
                     offline_compiler_inputs, sanitize_and_audit, write_verified_hak)


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
                             'subtype', 'identity', 'placeholderCenter', 'carrierAppearance'}, 'Unknown package specification field')
        identity = spec['identity']
        require(set(identity) == {'texturePrefix', 'blueprintPrefix', 'hak', 'module', 'displayName'},
                'Explicit firearm resource identity required')
        for key in ('texturePrefix', 'blueprintPrefix', 'hak', 'module'): resref(identity[key])
        require(isinstance(identity['displayName'], str) and identity['displayName'].strip(), 'Display name required')
        profile_path = spec['sourceProfile']['path']
        profile = read(profile_path)
        _, resources = native_contract(profile_path, profile)
        route = ROUTES[profile['family']]
        skinned = route.adapter == 'whole-skinned'
        longarm = route.longarm
        motion = None
        if skinned:
            from .contracts import crossbow_motion_inputs
            _, motion, _ = crossbow_motion_inputs(profile_path, profile)
        original = resources['baseitems.2da']
        table = Path(original['path']).read_bytes()
        _, row = (longarm_row if longarm else sling_row)(table)
        icon_size = (int(row['InvSlotWidth'])*32, int(row['InvSlotHeight'])*32)
        require(icon_size == ((64,128) if longarm else (32,64)), 'Review changed carrier inventory dimensions')
        archive = archive_helpers()
        occupied = set(resources)
        type_extensions = {value: key for key, value in {**archive.TYPES, **EXTRA_RESOURCE_TYPES}.items()}
        for hak in spec.get('comparisonHaks', []):
            for name, kind in archive.payload(hak['path']):
                require(kind in type_extensions, 'Unsupported comparison HAK resource type')
                occupied.add(name.lower()+'.'+type_extensions[kind])
        variants = spec['variants']
        require(variants and all(set(v) == {'colour', 'displayName', 'arrays', 'texture', 'icon'} for v in variants),
                'Each Color needs a name and bound arrays, texture and icon')
        if longarm:
            require(spec['subtype']==('crossbow' if skinned else 'rifle') and len(variants)==1 and 'carrierAppearance' in spec,
                    'One explicit raw-byte longarm assembly required')
            allocation = longarm_plan(spec['carrierAppearance'],occupied,identity['texturePrefix'],identity['blueprintPrefix'])
            if skinned: allocation['subtype'] = 'crossbow'
            require(variants[0]['colour']==allocation['colours'][0], 'Variant colour differs from its raw appearance byte')
            override_report = {'resource':'baseitems.2da','intentionalOverride':False,
                               'originalSha256':original['sha256'],'changes':{}}
        else:
            require('carrierAppearance' not in spec, 'Raw appearance applies only to the qualified F8 longarm route')
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
                required = {'positions', 'normals', 'uv', 'shadowVertices', 'shadowFaces'}
                if skinned: required |= {'weights', 'shadowWeights'}
                require(set(data.files) == required,
                        'Exact native corner archive required')
                counts = {p: {'visible': 4, 'shadow': 0} for p in ('b', 'm', 't')}
                counts[allocation['slot']] = {'visible': len(data['positions']), 'shadow': len(data['shadowFaces'])}
                validate_assembly(allocation, variant, counts)
                if skinned:
                    from .skinned_native import model_text
                    text = model_text(variant['models'][allocation['slot']], variant['texture'],
                                      {k:data[k] for k in data.files},
                                      Path(motion['ascii']['path']).read_text(encoding='ascii'), motion['boneNames'])
                else:
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
        if not longarm: (out/'resources/baseitems.2da').write_bytes(override)
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
                  'effectiveBaseitems': original, ('inheritedCarrierFields' if longarm else 'inheritedSlingFields'): row, 'iconSize': list(icon_size),
                  'inputs': inputs, 'outputs': outputs, 'elapsedSeconds': time.perf_counter()-started,
                  'clientValidated': False, 'productionAccepted': False}
        if skinned: result['skin'] = {'rig':motion['ascii'],'boneNames':motion['boneNames']}
    # A separate pass checks fresh bytes at completion, never a timestamp cache.
    verify(inputs, fresh=True)
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


def compile_package(prepared_dir, client, output, *, compiler=None):
    from tools.phenotypes import tool_runtime
    started = time.perf_counter()
    prepared_dir = Path(prepared_dir)
    with verification_pass('firearm-native-dispatch'):
        inputs = prepared_inputs(prepared_dir)+(offline_compiler_inputs(compiler) if compiler is not None else [client])
        verify(inputs)
        prepared = read(prepared_dir/'prepared.json')
        require(compiler is not None or not prepared.get('skin'), 'Skinned crossbows require the qualified offline compiler')
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    converted = out/'converted'; shutil.copytree(prepared_dir, converted)
    if compiler is not None:
        compile_offline(converted,compiler,out)
    else:
        compile_with_client(converted, client, out)
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
        if prepared.get('skin'):
            from tools.phenomorpher.phenomorpher.engine import neverblender_mdl
            from .skinned_native import audit as audit_skin
            decoded=out/(name+'-skin-readback.mdl')
            neverblender_mdl.decompile_files(compiler['blender']['path'],compiler['neverblender']['path'],[(target,decoded)],timeout=120)
            with np.load(prepared['expected'][name]['path'],allow_pickle=False) as data:
                clean,audit=audit_skin(target,name,variant['texture'],{k:data[k] for k in data.files},decoded,prepared['skin']['boneNames'])
        else:
            clean, audit = sanitize_and_audit(target, name, variant['texture'], prepared['expected'][name])
        target.write_bytes(clean); audits[name] = audit
        source = prepared['blueprints'][variant['blueprint']]; target = res/(variant['blueprint']+'.uti')
        readback = out/(variant['blueprint']+'-readback.json')
        audit = blueprint_roundtrip(gff, source['path'], target, readback)
        blueprints.append({'file': pin(target), 'colour': variant['colour'], 'utiParts': variant['utiParts'], 'audit': audit})
    expected_names = set(allocation['resources']) | ({'baseitems.2da'} if prepared['intentionalOverride']['intentionalOverride'] else set())
    require({p.name for p in res.iterdir()} == expected_names, 'Missing or unexpected firearm payload resource')
    files = sorted(res.iterdir()); hak = out/(prepared['identity']['hak']+'.hak')
    write_verified_hak(hak, files)
    verify(inputs, fresh=True)
    result = {'schemaVersion': 1, 'kind': 'firearm-native-package', 'codeVersion': prepared['codeVersion'], 'hak': pin(hak),
              'baseItem': allocation['baseItem'], 'allocation': allocation,
              'identity': {**prepared['identity'], 'blueprint': allocation['variants'][0]['blueprint']},
              'blueprints': blueprints, 'counts': prepared['counts'], 'audits': audits,
              'intentionalOverride': prepared['intentionalOverride'], 'inputs': inputs,
              'resources': [pin(p) for p in files], 'elapsedSeconds': time.perf_counter()-started,
              'clientValidated': False, 'productionAccepted': False}
    if prepared.get('skin'): result['geometryRoute'] = 'skinned-crossbow'
    if compiler is not None:result['compilationBackend']='neverblender-cleanmodels'
    write(out/'native.json', result, fresh=True)
    return result
