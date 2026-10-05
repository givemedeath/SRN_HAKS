"""Freeze installed shader inputs and inspect unmodified target donor material maps.

This source audit does not prove client shader selection, image quality or AO
acceptance. Historical receipts carry snapshots instead of changing Human data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import numpy as np

import target_contract as contract


EXPECTED_SHADER_PINS = {
    'fslit_nm.shd': '08c88af8a8fddf0a3bf687f324f9b57d3eb47ba9fa8586686f44c748927931b0',
    'inc_common.shd': '20ecd0437d31e26ee797c83422c83870d62c7f910ca3bffc2473553401575337',
    'inc_material.shd': 'e6b53caa87429237c32b37606b956f3b6fc20eeff69ddedd35a3128c0a3992ac',
    'inc_lighting.shd': '8548ea59d662829521e0618edb1511fc2a88a3ecf7108ead86829b8f3d200bf8',
}
ENTRYPOINTS = ('fslit_nm.shd', 'vslit_nm.shd', 'fs_pltgen.shd', 'vs_pltgen.shd')
INCLUDE = re.compile(r'^\s*#\s*include\s+"([a-zA-Z0-9_]+)"', re.M)
POLICY = {
    'skinDiffuse': 'PLT painted shade on skin layer 0; MTR omits texture0 entirely',
    'garmentDiffuse': 'Opaque fixed material with texture0, owned only by pelvis',
    'normalTexture': 'Original RGB bytes at glTF normalTexture.scale 1, texture1',
    'roughnessTexture': 'Linear ORM green times glTF roughnessFactor, rounded once to uint8; texture3 red',
    'roughnessUniform': 0,
    'roughnessUniformMeaning': 'Zero selects map/fallback; every positive value replaces the map',
    'positiveRoughnessUniformRange': [0.001, 1],
    'specularityUniform': 0.04,
    'metallicnessUniform': 0.001,
    'addedAoCandidates': [0, 0.15, 0.35],
    'addedAoSelected': None,
    'addedAoComparison': 'Each variant starts from the same untreated selected parent',
    'occlusionTextureBinding': None,
    'heightTextureBinding': None,
}


def bytes_sha(value):
    return hashlib.sha256(value).hexdigest()


def compact(source):
    source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    source = re.sub(r'//[^\n]*', '', source)
    return re.sub(r'\s+', '', source)


def evidence(source, text):
    """Locate a checked literal in original frozen source, including line number."""
    position = source.find(text)
    contract.require(position >= 0, 'Shader evidence absent: ' + text)
    return {'line': source[:position].count('\n') + 1, 'expression': text}


def prove_shader_semantics(sources):
    """Check the relevant expressions; this is not a complete GLSL preprocessor."""
    needed = {'fslit_nm.shd', 'inc_material.shd', 'inc_standard.shd',
              'inc_lighting.shd', 'inc_config.shd', 'fs_pltgen.shd'}
    contract.require(needed <= set(sources), 'Incomplete effective shader source chain')
    entry = compact(sources['fslit_nm.shd'])
    for macro in ('SHADER_TYPE2', 'NORMAL_MAP1', 'ROUGHNESS_MAP1', 'ENVIRONMENT_MAP0'):
        contract.require('#define' + macro in entry, 'Normal-map entrypoint changed: ' + macro)
    material = compact(sources['inc_material.shd'])
    checks = [
        '#defineMATERIAL_READ_ROUGHNESS_FROM_SPECULAR_MAP0',
        'if(Roughness>0.0){MATERIAL_ROUGHNESS_VALUE=Roughness;}',
        'MATERIAL_ROUGHNESS_VALUE=texture2D(texUnit3,vTexCoords.xy).r;',
        '#definefGeneratedRoughnessMax0.55',
        '#definefGeneratedRoughnessMin0.125',
    ]
    for text in checks:
        contract.require(text in material, 'Roughness source semantics changed: ' + text)
    standard = compact(sources['inc_standard.shd'])
    for text in [
        'vFragmentNormal.xy=texture2D(texUnit1,vTexCoords).rg*2.0-1.0;',
        'vFragmentNormal.z=sqrt(max(1.0-dot(vFragmentNormal.xy,vFragmentNormal.xy),0.0));',
        'vFragmentNormal=mTSB*vFragmentNormal;',
    ]:
        contract.require(text in standard, 'Normal decode semantics changed: ' + text)
    lighting = compact(sources['inc_lighting.shd'])
    for text in [
        'fRoughness_sq=MATERIAL_ROUGHNESS_VALUE*MATERIAL_ROUGHNESS_VALUE;',
        'floatfFactor=fCosNormalFacet*fCosNormalFacet*-fRoughness_sq_inv+1.0;',
        'returnfRoughness_sq/(fFactor*fFactor);',
    ]:
        contract.require(text in lighting, 'GGX source semantics changed: ' + text)
    contract.require('#defineSPECULAR_DISTRIBUTION_MODEL1' in compact(sources['inc_config.shd']),
                     'Installed specular distribution default changed')
    plt = compact(sources['fs_pltgen.shd'])
    contract.require('ColorPLT.g=PLTscheme[int(ColorPLT.g*255.0+0.5)];' in plt and
                     'ColorPLT=texture2D(texUnit1,ColorPLT.rg);' in plt,
                     'PLT palette decoding changed')
    return {
        'method': 'Static checked expressions and pinned source bytes; engine selection remains unobserved',
        'roughness': {
            'positiveUniformOverridesMap': True, 'zeroUniformSelectsMapOrFallback': True,
            'defaultMap': 'texture3 red', 'defaultAlternateSpecularGreenEnabled': False,
            'generatedFallback': 0.55, 'fragmentShaderTypeRequiredForMap': 2,
            'sourceEvidence': [evidence(sources['inc_material.shd'], value) for value in
                ['if(Roughness>0.0)', 'MATERIAL_ROUGHNESS_VALUE = Roughness;',
                 'MATERIAL_ROUGHNESS_VALUE = texture2D(texUnit3, vTexCoords.xy).r;']],
            'zeroMapSampleConcern': 'GGX denominator is zero at roughness 0 and cosine 1; actual driver/client result unobserved',
            'zeroMapSamplePolicy': 'Measure and review; do not silently clamp or alter authored roughness',
        },
        'normal': {
            'channelsRead': ['R', 'G'], 'blueRead': False, 'positiveZReconstructed': True,
            'strengthUniformObserved': False,
            'sourceEvidence': [evidence(sources['inc_standard.shd'], value) for value in
                ['vFragmentNormal.xy = texture2D(texUnit1, vTexCoords).rg * 2.0 - 1.0;',
                 'vFragmentNormal.z = sqrt(max(1.0 - dot(vFragmentNormal.xy, vFragmentNormal.xy),0.0));']],
            'preservingRgbBytesDoesNotProveGltfEquivalentRendering': True,
        },
        'plt': {'shadeChannel': 'R', 'layerChannel': 'G',
                'sourceEvidence': [evidence(sources['fs_pltgen.shd'],
                                          'ColorPLT = texture2D(texUnit1, ColorPLT.rg);')]},
        'ao': {'ormRedIsNotAnAoTextureSlot': True,
               'heightSlotUsesLocalHeightComparison': True, 'heightSlotMustNotReceiveOrmRed': True},
        'quality': {'ordinaryAndHighQualityClientChecksRequired': True,
                    'actualQualityMacroAndEntrypointSelectionObserved': False},
    }


def transport_roughness(orm, factor):
    pixels = np.asarray(orm)
    contract.require(pixels.dtype == np.uint8 and pixels.ndim >= 2 and pixels.shape[-1] >= 3,
                     'Decoded byte ORM RGB image required')
    contract.require(isinstance(factor, (int, float)) and np.isfinite(factor) and 0 <= factor <= 1,
                     'Linear glTF roughnessFactor must be finite in [0,1]')
    authored = pixels[..., 1].astype(np.float64) * factor / 255
    encoded = np.rint(pixels[..., 1].astype(np.float64) * factor).astype(np.uint8)
    reconstructed = encoded.astype(np.float64) / 255
    return encoded, {'factor': float(factor), 'gammaApplied': False, 'sourceChannel': 'G',
                     'destinationChannel': 'R', 'minimum': float(authored.min()),
                     'maximum': float(authored.max()), 'encodedMinimum': int(encoded.min()),
                     'encodedMaximum': int(encoded.max()), 'zeroTexels': int((encoded == 0).sum()),
                     'texels': int(encoded.size), 'maximumQuantizationError':
                         float(np.abs(reconstructed-authored).max()),
                     'encodedSha256': bytes_sha(encoded.tobytes())}


def normal_diagnostics(normal, strength=1):
    pixels = np.asarray(normal)
    contract.require(pixels.dtype == np.uint8 and pixels.ndim >= 2 and pixels.shape[-1] == 3,
                     'Decoded original byte RGB normal image required')
    contract.require(strength == 1, 'Original normal strength one required')
    gltf = pixels.astype(np.float64) / 255 * 2 - 1
    radius = np.sum(gltf[..., :2] ** 2, axis=-1)
    nwn = np.concatenate([gltf[..., :2], np.sqrt(np.maximum(1-radius, 0))[..., None]], axis=-1)
    gltf_length = np.linalg.norm(gltf, axis=-1)
    nwn_length = np.linalg.norm(nwn, axis=-1)
    dot = np.sum(gltf*nwn, axis=-1) / (gltf_length*nwn_length)
    angular = np.degrees(np.arccos(np.clip(dot, -1, 1)))
    return {'strength': 1, 'originalRgbSha256': bytes_sha(pixels.tobytes()),
            'texels': int(radius.size), 'xyRadiusSquaredMaximum': float(radius.max()),
            'xyOutsideUnitDiskTexels': int((radius > 1).sum()),
            'nonPositiveAuthoredZTexels': int((gltf[..., 2] <= 0).sum()),
            'nwnTangentNormalLengthRange': [float(nwn_length.min()), float(nwn_length.max())],
            'normalizedGltfToNwnAngularDegreesMaximum': float(angular.max()),
            'normalizedGltfToNwnAngularDegreesMean': float(angular.mean()),
            'edited': False, 'clientLightingAccepted': False}


def shader_roughness(uniform, map_value=None, *, specular_texture_bound=False,
                     specularity=0.04, shader_type=2):
    """Pinned fslit_nm branch model, ENVIRONMENT_MAP=0, default alternate map=0.

    MTR policy permits sentinel 0 or the documented positive range. The source
    threshold itself accepts any positive float; no claim is made about parsing.
    """
    contract.require(np.isfinite(uniform) and (uniform == 0 or 0.001 <= uniform <= 1),
                     'Roughness uniform must be sentinel 0 or documented [0.001,1]')
    contract.require(shader_type in (1, 2), 'Vertex/fragment shader type required')
    if uniform > 0:
        return float(uniform)
    if shader_type == 2 and map_value is not None:
        contract.require(np.isfinite(map_value) and 0 <= map_value <= 1, 'Unit-interval map sample required')
        return float(map_value)
    if shader_type == 2 and specular_texture_bound:
        contract.require(np.isfinite(specularity) and 0 <= specularity <= 1, 'Unit-interval specularity required')
        return float(0.125 + (0.55 - 0.125) * (1-specularity)**2)
    return 0.55


def run(command):
    completed = subprocess.run([str(item) for item in command], capture_output=True, check=True)
    return completed.stdout


def freeze(target_path, game_root, userdir, resman_directory, output):
    target_path = Path(target_path).resolve(); target = contract.load(target_path)
    game_root, userdir, resman_directory = (Path(item).resolve() for item in
                                           (game_root, userdir, resman_directory))
    output = Path(output).resolve()
    contract.require(not output.exists(), 'Fresh immutable material preparation required')
    contract.require((userdir/'override').is_dir() and not any((userdir/'override').iterdir()),
                     'Explicit isolated user directory with empty override required')
    cat = resman_directory/'nwn_resman_cat.exe'; grep = resman_directory/'nwn_resman_grep.exe'
    common = ['--root', game_root, '--userdirectory', userdir]
    inventory_raw = run([grep, *common, '--no-ovr', '--pattern', '.shd', '--details'])
    effective_inventory = run([grep, *common, '--pattern', '.shd', '--details'])
    locations = {}
    for line in inventory_raw.decode('utf-8').splitlines():
        match = re.match(r'^(\S+\.shd)\s+\S+\s+(.*)$', line)
        if match:
            locations[match[1]] = match[2]
    pending = list(ENTRYPOINTS); bank = {}; resources = {}; differences = []
    while pending:
        name = pending.pop(0)
        if name in bank:
            continue
        contract.require(name in locations, 'Installed shader missing: ' + name)
        data = run([cat, *common, '--no-ovr', name])
        with_overrides = run([cat, *common, name])
        if data != with_overrides:
            differences.append(name)
        contract.require(bool(data), 'Empty installed shader: ' + name)
        if name in EXPECTED_SHADER_PINS:
            contract.require(bytes_sha(data) == EXPECTED_SHADER_PINS[name], 'Verified shader pin differs: ' + name)
        bank[name] = data
        pending.extend(item+'.shd' for item in INCLUDE.findall(data.decode('utf-8')))
        resources[name] = {'sha256': bytes_sha(data), 'bytes': len(data),
                           'effectiveLocation': locations[name],
                           'overrideEnabledSha256': bytes_sha(with_overrides),
                           'includes': [item+'.shd' for item in INCLUDE.findall(data.decode('utf-8'))]}
    contract.require(not differences, 'Installed loose shader override differs: ' + ', '.join(differences))
    semantics = prove_shader_semantics({name: data.decode('utf-8') for name, data in bank.items()})
    palette = run([cat, *common, '--no-ovr', 'pal_skin01.tga'])
    contract.require(palette == run([cat, *common, 'pal_skin01.tga']), 'Installed skin palette override differs')
    container_paths = set()
    for value in resources.values():
        match = re.fullmatch(r'KeyTable:(.*\.key)\(id=\d+ in (.*\.bif)\)', value['effectiveLocation'])
        contract.require(match is not None, 'Unresolved effective shader container: ' + value['effectiveLocation'])
        container_paths.add(Path(match[1])); container_paths.add(game_root/match[2])
    origin_paths = [target_path, cat, grep, Path(sys.executable),
                    game_root/'bin/win32/nwmain.exe', *sorted(container_paths)]
    origin_pins = {str(path): contract.sha(path) for path in origin_paths}
    # Historical verification uses snapshot hashes; current installation pins are
    # recorded separately so replacing a live tool does not rewrite old evidence.
    (output/'shaders').mkdir(parents=True)
    for name, data in sorted(bank.items()):
        (output/'shaders'/name).write_bytes(data)
    (output/'pal_skin01.tga').write_bytes(palette)
    shutil.copyfile(target_path, output/'target-contract-snapshot.json')
    shutil.copyfile(__file__, output/'executed-helper.py')
    shutil.copyfile(Path(__file__).with_name('target_contract.py'), output/'target_contract.py')
    (output/'resolved-no-override.txt').write_bytes(inventory_raw)
    (output/'resolved-with-overrides.txt').write_bytes(effective_inventory)
    (output/'material-policy.json').write_text(json.dumps(POLICY, indent=2)+'\n', encoding='utf-8')
    receipt = {'schemaVersion': 2, 'kind': 'target-material-shader-preparation',
               **contract.binding(target_path, target, 'working'),
               'entrypoints': list(ENTRYPOINTS), 'resources': resources,
               'semantics': semantics, 'materialPolicy': POLICY,
               'sourceBank': str(output/'shaders'), 'originInputPins': origin_pins,
               'frozenInputs': {str(path): contract.sha(path) for path in sorted(output.rglob('*')) if path.is_file()},
               'shaderLooseOverrideDifferences': differences, 'userOverrideEmpty': True,
               'installedShaderSourceVerified': True, 'installedShaderConsumptionObserved': False,
               'rigPilotAccepted': target['rig']['pilotAccepted'], 'donorMaterialInputsCollected': False,
               'jointBandColorContinuityAccepted': False, 'aoVisualSelectionAccepted': False,
               'normalRenderingAccepted': False, 'nativeTangentsAccepted': False,
               'productionAccepted': False, 'clientAccepted': False,
               'pending': ['Selected donor original map/normal diagnostics', 'PLT palette color and joint-band comparison',
                           'AO 0/0.15/0.35 comparison from identical untreated parent',
                           'Native material/tangent decode', 'Observed ordinary/high-quality client shader consumption']}
    result = output/'material-shaders.json'
    result.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return result


def inspect(config_path, output):
    """Measure selected collected donor maps without staging or changing geometry."""
    from place_purposebuilt_pelvis import read_glb
    from target_part_pipeline import generation_source, pin, read_target, verify_source_receipt
    from target_part_stage import image_pixels
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path, target = read_target(config)
    contract.require(config.get('kind') == 'target-material-input-audit', 'Explicit material audit configuration required')
    part, space = config['part'], config['coordinateSpace']
    contract.require(part in contract.BODY_PARTS and space in ('working', 'runtime'), 'Declared target body material required')
    source = pin(config['source'], config['sourceSha256'])
    parent_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    parent = json.loads(parent_path.read_text(encoding='utf-8'))
    if parent.get('kind') == 'target-part-geometry':
        verify_source_receipt(source, parent_path, target_path, target, part, space)
    else:
        contract.require(space == 'working', 'Collected donor audit must use working space')
        generation_source(source, parent_path)
    shader_path = pin(config['shaderReceipt'], config['shaderReceiptSha256'])
    shader = json.loads(shader_path.read_text(encoding='utf-8'))
    contract.require(shader.get('kind') == 'target-material-shader-preparation', 'Frozen shader preparation required')
    # Shader preparation is working-bound even if inspecting a once-scaled candidate.
    contract.verify_binding(shader, target_path, target, 'working')
    for name, expected in shader['frozenInputs'].items():
        pin(name, expected)
    doc, binary = read_glb(source)
    active = {primitive.get('material') for mesh in doc['meshes'] for primitive in mesh['primitives']}
    contract.require(None not in active and set(config['materialIds']) == active,
                     'Audit every active declared material exactly once')
    rows = []
    for index in sorted(active):
        material = doc['materials'][index]; pbr = material['pbrMetallicRoughness']
        contract.require(material.get('alphaMode', 'OPAQUE') == 'OPAQUE', 'Opaque source material required')
        normal = image_pixels(doc, binary, material['normalTexture'])
        orm = image_pixels(doc, binary, pbr['metallicRoughnessTexture'])
        color = image_pixels(doc, binary, pbr['baseColorTexture'])
        _, roughness = transport_roughness(orm, pbr.get('roughnessFactor', 1))
        rows.append({'materialId': index, 'sourceBindings': material,
                     'baseColorDecodedRgbSha256': bytes_sha(color.tobytes()),
                     'ormDecodedRgbSha256': bytes_sha(orm.tobytes()),
                     'normal': normal_diagnostics(normal, material['normalTexture'].get('scale', 1)),
                     'roughness': roughness, 'anatomicalOwnershipReviewed': False})
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable material input audit required')
    output.mkdir(parents=True); shutil.copyfile(__file__, output/'executed-helper.py')
    receipt = {'schemaVersion': 2, 'kind': 'target-material-input-audit',
               **contract.binding(target_path, target, space), 'part': part,
               'source': str(source), 'sourceSha256': contract.sha(source),
               'sourceReceipt': str(parent_path), 'sourceReceiptSha256': contract.sha(parent_path),
               'shaderReceipt': str(shader_path), 'shaderReceiptSha256': contract.sha(shader_path),
               'materials': rows, 'geometryEdited': False, 'materialPixelsEdited': False,
               'sourceMaterialRolesReviewed': False, 'aoSelected': None,
               'productionAccepted': False, 'clientAccepted': False,
               'frozenInputs': {str(path): contract.sha(path) for path in
                   [config_path, target_path, source, parent_path, shader_path, output/'executed-helper.py']}}
    result = output/'material-inputs.json'; result.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return result


def compare_variants(config_path, output):
    """Verify the three existing AO stages preserve the same normal/roughness data."""
    from PIL import Image
    from place_purposebuilt_pelvis import read_glb
    from target_part_pipeline import pin, read_target, verify_source_receipt
    from target_part_stage import image_pixels
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path, target = read_target(config)
    contract.require(config.get('kind') == 'target-material-variant-audit', 'Explicit material variant audit required')
    part, space = config['part'], config['coordinateSpace']
    contract.require(part in contract.BODY_PARTS, 'Declared target part required')
    source = pin(config['source'], config['sourceSha256'])
    parent_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    verify_source_receipt(source, parent_path, target_path, target, part, space)
    shader_path = pin(config['shaderReceipt'], config['shaderReceiptSha256'])
    shader = json.loads(shader_path.read_text(encoding='utf-8'))
    contract.require(shader.get('kind') == 'target-material-shader-preparation', 'Frozen shader preparation required')
    contract.verify_binding(shader, target_path, target, 'working')
    for name, expected in shader['frozenInputs'].items(): pin(name, expected)
    doc, binary = read_glb(source)
    material_ids = {primitive.get('material') for mesh in doc['meshes'] for primitive in mesh['primitives']}
    contract.require(material_ids == {config['materialId']}, 'Single skin material required for this AO diagnostic')
    material = doc['materials'][config['materialId']]; pbr = material['pbrMetallicRoughness']
    contract.require(material['normalTexture'].get('scale', 1) == 1, 'Original normal strength one required')
    normal = image_pixels(doc, binary, material['normalTexture'])
    orm = image_pixels(doc, binary, pbr['metallicRoughnessTexture'])
    expected_roughness, roughness_proof = transport_roughness(orm, pbr.get('roughnessFactor', 1))
    expected_rgb = np.repeat(expected_roughness[..., None], 3, axis=-1)
    color = image_pixels(doc, binary, pbr['baseColorTexture'])
    ao = image_pixels(doc, binary, material['occlusionTexture'])[..., 0].astype(float)/255
    base_intensity = color.astype(float) @ np.asarray([.2126, .7152, .0722])
    rows = []; pins = [config_path, target_path, source, parent_path, shader_path]; strengths = []
    ascii_hashes = set()
    for selected in config['stages']:
        stage_path = pin(selected['receipt'], selected['sha256']); pins.append(stage_path)
        stage = json.loads(stage_path.read_text(encoding='utf-8'))
        contract.require(stage.get('schemaVersion') == 2 and stage.get('kind') == 'target-part-stage',
                         'Version 2 target stage receipt required')
        contract.verify_binding(stage, target_path, target, space)
        contract.require(stage['part'] == part and stage['sourceSha256'] == contract.sha(source) and
                         Path(stage['source']).resolve() == source and
                         stage['untreatedParentSha256'] == contract.sha(source), 'AO variant parent differs')
        contract.require(stage['materialRoles'] == {str(config['materialId']): 'skin'}, 'Skin-only variant audit required')
        for name, expected in stage['frozenInputs'].items(): pin(name, expected)
        ascii_path = pin(stage['asciiModel'], stage['asciiModelSha256']); pins.append(ascii_path)
        ascii_hashes.add(stage['asciiModelSha256'])
        folder = stage_path.parent/'resources'; model = stage['model']
        contract.require(set(stage['materialResourceHashes']) == {model+'.mtr', model+'.plt', model+'n.tga', model+'r.tga'},
                         'Unexpected material resource inventory in AO stage')
        for name, expected in stage['materialResourceHashes'].items():
            pins.append(pin(folder/name, expected))
        mtr = (folder/(model+'.mtr')).read_text(encoding='ascii')
        contract.require(re.search(r'^texture0\b', mtr, re.M) is None and
                         re.search(r'^texture1 '+re.escape(model+'n')+r'$', mtr, re.M) is not None and
                         re.search(r'^texture3 '+re.escape(model+'r')+r'$', mtr, re.M) is not None and
                         re.search(r'^parameter float Roughness 0$', mtr, re.M) is not None,
                         'PLT material binding or map-selection sentinel differs')
        staged_normal = np.asarray(Image.open(folder/(model+'n.tga')).convert('RGB'))
        staged_roughness = np.asarray(Image.open(folder/(model+'r.tga')).convert('RGB'))
        contract.require(np.array_equal(staged_normal, normal), 'AO variant rewrites original normal pixels')
        contract.require(np.array_equal(staged_roughness, expected_rgb), 'AO variant roughness transport differs')
        data = (folder/(model+'.plt')).read_bytes()
        contract.require(data[:8] == b'PLT V1  ' and len(data) == 24+2048*2048*2, 'Unexpected PLT encoding')
        decoded = np.frombuffer(data[24:], dtype='u1').reshape(2048,2048,2)[::-1]
        strength = stage['aoStrength']; strengths.append(strength)
        contract.require(strength in (0, .15, .35), 'Unexpected AO comparison strength')
        expected_intensity = (base_intensity*(1-strength*(1-ao))).clip(0,255).astype('u1')
        contract.require(np.array_equal(decoded[...,0], expected_intensity) and not decoded[...,1].any(),
                         'AO variant does not independently derive skin shades from untouched parent')
        rows.append({'stageReceipt': str(stage_path), 'stageReceiptSha256': contract.sha(stage_path),
                     'aoStrength': strength, 'normalDecodedRgbSha256': bytes_sha(staged_normal.tobytes()),
                     'roughnessDecodedRgbSha256': bytes_sha(staged_roughness.tobytes()),
                     'roughnessByteRange': [int(staged_roughness[...,0].min()), int(staged_roughness[...,0].max())],
                     'roughnessZeroTexels': int((staged_roughness[...,0] == 0).sum()),
                     'pltShadeByteRange': [int(decoded[...,0].min()), int(decoded[...,0].max())],
                     'pltShadeMean': float(decoded[...,0].mean()),
                     'sourceFormulaAndSerializedPixelsVerified': True, 'visualAccepted': False})
    contract.require(sorted(strengths) == [0, .15, .35], 'Exactly one stage at each AO comparison strength required')
    contract.require(len(ascii_hashes) == 1, 'AO stages changed serialized geometry')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable material variant audit required')
    output.mkdir(parents=True); shutil.copyfile(__file__, output/'executed-helper.py'); pins.append(output/'executed-helper.py')
    receipt = {'schemaVersion': 2, 'kind': 'target-material-variant-audit',
               **contract.binding(target_path, target, space), 'part': part,
               'untreatedParent': str(source), 'untreatedParentSha256': contract.sha(source),
               'normal': normal_diagnostics(normal), 'roughness': roughness_proof, 'variants': rows,
               'sameNormalAndRoughnessPixelsAcrossVariants': True, 'sameAsciiGeometryAcrossVariants': True,
               'geometryEdited': False, 'materialPixelsEdited': False, 'aoSelected': None,
               'rigPilotAccepted': target['rig']['pilotAccepted'], 'normalRenderingAccepted': False,
               'aoVisualSelectionAccepted': False, 'productionAccepted': False, 'clientAccepted': False,
               'frozenInputs': {str(path): contract.sha(path) for path in sorted(set(pins))}}
    result = output/'material-variants.json'; result.write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    freezer = commands.add_parser('freeze'); freezer.add_argument('--target', type=Path, required=True)
    freezer.add_argument('--root', type=Path, required=True); freezer.add_argument('--userdir', type=Path, required=True)
    freezer.add_argument('--resman', type=Path, required=True); freezer.add_argument('--output', type=Path, required=True)
    inspector = commands.add_parser('inspect'); inspector.add_argument('--config', type=Path, required=True)
    inspector.add_argument('--output', type=Path, required=True)
    comparer = commands.add_parser('compare'); comparer.add_argument('--config', type=Path, required=True)
    comparer.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'freeze': result = freeze(args.target, args.root, args.userdir, args.resman, args.output)
    elif args.command == 'inspect': result = inspect(args.config, args.output)
    else: result = compare_variants(args.config, args.output)
    print(json.dumps({'receipt': str(result), 'receiptSha256': contract.sha(result)}))
