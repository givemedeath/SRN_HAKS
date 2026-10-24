"""Portable design contracts; native facts must come from a pinned content stack."""
from pathlib import Path
import re
from tools.headkit.common import ROOT, asset, digest, pin, read, require, verify

BASELINE = 'e607a617c273828a37d8fc56dd43d7d8a0070844'
PARTS = ('b', 'm', 't')
GENERATION = {'preset': 'pixal-single-v1', 'shapeResolution': 1536, 'shapeCFG': 12,
              'textureCFG': 1, 'textureSteps': 12}


def resref(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,15}', value),
            'NWN resref must be lowercase and at most 16 characters')
    return value


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, 'Invalid ' + label)
    return value


def family(path, *, validate_native=True):
    data = read(path)
    require(data.get('schemaVersion') == 1 and data.get('kind') == 'item-family', 'Unsupported item family')
    require(data.get('family') in ('shortsword', 'dagger', 'longsword', 'shield', 'firearm-sling'), 'Unsupported item family')
    require(data.get('materialRoute') == 'diffuse', 'Only diffuse materials are qualified for this pilot')
    require(data.get('runtimeTextureSize') in (512, 1024, 2048), 'Unsupported runtime texture size')
    require(data.get('bakeSize') == 4096, 'Source bake must be 4K')
    require(data.get('nativePackaging') in ('pending-contract', 'enabled', 'blocked'), 'Explicit native packaging state required')
    settings=data.get('resources', {})
    require(set(settings) <= {'texturePrefix','hak','module','blueprint','displayName'}, 'Unsupported resource identity')
    for key in ('texturePrefix','hak','module','blueprint'):
        if key in settings: resref(settings[key])
    if 'texturePrefix' in settings: require(len(settings['texturePrefix'])<=13,'Texture prefix leaves no appearance suffix')
    if data['family'] == 'shield' or data['family'] == 'firearm-sling' and 'firearm' not in data:
        require(data['nativePackaging'] == 'blocked', 'Shield and unqualified Sling native adapters are deferred')
    budgets = data['budgets']
    firearm_slot = None
    if 'firearm' in data:
        from .firearms import SLOTS
        require(data['family'] == 'firearm-sling' and set(data['firearm']) == {'subtype'}
                and data['firearm']['subtype'] in SLOTS, 'Explicit supported firearm slot required')
        firearm_slot = SLOTS[data['firearm']['subtype']]
        require(budgets['visible'] == 10000 and budgets['shadow'] == 500, 'Firearm trial cap is 10000/500')
    require(set(budgets) == {'visible', 'shadow', 'parts'}, 'Explicit whole-object and per-part budgets required')
    for kind in ('visible', 'shadow'):
        integer(budgets[kind], 4, 200000, kind + ' assembly budget')
        require(set(budgets['parts']) == set(PARTS), 'All native parts require budgets')
        for part, row in budgets['parts'].items():
            integer(row[kind], 0 if firearm_slot and kind == 'shadow' and part != firearm_slot else 4,
                    budgets[kind], kind + ' part budget')
            if firearm_slot and part != firearm_slot:
                require(row == {'visible': 4, 'shadow': 0}, 'Inactive firearm slots require hidden placeholders')
        require(sum(row[kind] for row in budgets['parts'].values()) <= budgets[kind], 'Part budgets exceed assembly budget')
    require(data.get('allowedAssemblies') and all(isinstance(row, dict) and set(row) == set(PARTS)
            for row in data['allowedAssemblies']), 'Declare exact allowed assemblies')
    require(len({digest(row) for row in data['allowedAssemblies']}) == len(data['allowedAssemblies']), 'Duplicate allowed assembly')
    for row in data['allowedAssemblies']:
        for design in row.values():
            require(isinstance(design, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', design), 'Invalid design ID')
    if data['nativePackaging'] == 'enabled' and validate_native:
        native_contract(path, data)
    return data


def twoda(text):
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('//')]
    require(lines and lines[0].split()[:2] == ['2DA', 'V2.0'], 'Expected 2DA V2.0')
    index = 2 if lines[1].upper().startswith('DEFAULT:') else 1
    columns = lines[index].split(); rows = {}
    for line in lines[index+1:]:
        cells = line.split()
        require(cells[0] not in rows and len(cells) == len(columns)+1, 'Malformed or duplicate 2DA row')
        rows[cells[0]] = dict(zip(columns, cells[1:]))
    return rows


def native_contract(path, data):
    import numpy as np
    native = data.get('native', {})
    require(native.get('reviewed') is True, 'Native frame, grip and donors need review')
    stack = asset(path, native['stack'])
    evidence = read(stack['path'])
    require(evidence.get('complete') is True and evidence.get('order') == 'low-to-high', 'Complete ordered effective stack required')
    layers = evidence.get('layers', [])
    require(layers and all(isinstance(row.get('resources'), list) and (row['resources'] or row.get('nameInventory'))
                           for row in layers), 'Empty content-stack inventory')
    resources = {}
    for layer in layers:
        from .native_stack import namespace
        occupied,selected,_=namespace(stack['path'],layer)
        resources.update(dict.fromkeys(occupied))
        require(len({row['resource'].lower() for row in layer['resources']}) == len(layer['resources']),
                'Duplicate resources within a content-stack layer')
        for row in layer['resources']:
            name = row['resource'].lower()
            require(name == Path(name).name, 'Resource names cannot contain directories')
            bound = asset(stack['path'], row['file'])
            if selected is not None:
                require(selected.get(name)==bound['sha256'],'Selected resource differs from its stock extraction')
            resources[name] = bound
    table = resources.get('baseitems.2da')
    require(table is not None and table['sha256'] == native.get('baseitemsSha256'), 'Effective baseitems pin mismatch')
    row = twoda(Path(table['path']).read_text(encoding='utf-8-sig'))[str(native['baseItem'])]
    require(row['ItemClass'].lower() == native['itemClass'] and int(row['ModelType']) == native['modelType'],
            'Native family differs from effective baseitems')
    firearm = data['family'] == 'firearm-sling'
    if firearm:
        from .firearms import sling_row
        from .parts import active_parts
        from PIL import Image
        sling_row(Path(table['path']).read_bytes())
        require(native['baseItem'] == 61 and native['itemClass'] == 'wbwsl'
                and native.get('packagedModelType') == 2, 'Firearm contract requires the explicit private Sling multipart override')
        require(set(native['donors']) == {'whole', 'icon'}, 'Whole Sling and inventory icon donors required')
        slot, = active_parts(data)
        dimensions = [int(row['InvSlotWidth'])*32, int(row['InvSlotHeight'])*32]
        require(dimensions == [32,64] and native.get('iconDimensions') == {slot:dimensions},
                'Review changed Sling inventory dimensions')
    else:
        require(native['modelType'] == 2, 'Pilot requires a verified composite weapon contract')
    if data['family'] == 'dagger':
        require(native['baseItem'] == 22 and native['itemClass'] == 'wswdg', 'Dagger contract must match native dagger')
    if data['family'] == 'longsword':
        require(native['baseItem'] == 1 and native['itemClass'] == 'wswls', 'Longsword contract must match native longsword')
    resref(native['itemClass'])
    if not firearm: require(set(native['donors']) == set(PARTS), 'All composite donor parts required')
    for name in native['donors'].values():
        require(resources.get(name.lower()) is not None, 'Missing native donor: ' + name)
    if firearm:
        require(native['donors']['whole'].lower().endswith('.mdl'), 'Whole Sling model donor required')
        with Image.open(resources[native['donors']['icon'].lower()]['path']) as icon:
            require(list(icon.size) == dimensions, 'Sling icon donor differs from effective inventory dimensions')
    matrix = np.asarray(native['frame'], float)
    require(matrix.shape == (3, 3) and np.isfinite(matrix).all()
            and np.allclose(matrix.T @ matrix, np.eye(3), atol=1e-7) and np.linalg.det(matrix) > 0,
            'Native frame must be a proper rotation')
    grip = np.asarray(native['gripOrigin'], float)
    require(grip.shape == (3,) and np.isfinite(grip).all(), 'Finite native grip required')
    length = native['gripLength']
    require(type(length) in (int, float) and np.isfinite(length) and length > 0, 'Measured native grip length required')
    return native, resources


def model_names(data, index, colour=1):
    integer(index, 1, 25, 'model index'); integer(colour, 1, 9, 'colour index')
    require(index*10+colour <= 255, 'Native appearance value must fit the UTI byte')
    require(data.get('nativePackaging') == 'enabled', 'Native packaging remains blocked without a verified contract')
    require(data.get('family') != 'firearm-sling', 'Use the explicit firearm assembly allocator')
    return {part: resref(f"{data['native']['itemClass']}_{part}_{index*10+colour:03d}") for part in PARTS}


def reserve(data, resources, index=None, colour=1):
    occupied = {name.lower() for name in resources}
    settings = data.get('resources', {})
    if settings.get('blueprint'):
        require(resref(settings['blueprint'])+'.uti' not in occupied, 'Blueprint resref collision')
    for candidate in ([index] if index is not None else range(1, 26)):
        names = model_names(data, candidate, colour)
        # Native composite icons share the model-part naming convention, prefixed by i.
        icons = {p: resref('i'+name) for p, name in names.items()}
        texture = resref(settings.get('texturePrefix', 'sr_cfl')+'_'+str(candidate).zfill(2))
        if all(name+'.mdl' not in occupied and icons[p]+'.tga' not in occupied
               and icons[p]+'.dds' not in occupied for p, name in names.items()) and not any(
                   texture+suffix in occupied for suffix in ('.tga', '.dds', '.mtr', '.txi')):
            return {'modelIndex': candidate, 'colourIndex': colour, 'models': names, 'icons': icons}
    raise ValueError('No collision-free native appearance slot in the supported 1..25 pilot range')


def manifest(path, *, input_roles=None, validate_native=True):
    data = read(path)
    allowed = {'schemaVersion', 'kind', 'id', 'profile', 'familyProfile', 'inputs', 'features', 'openings',
               'camera', 'approval', 'fit', 'processing', 'render', 'clientCoverage', 'notes',
               'landmarks', 'materials', 'generationSettings', 'geometrySeedOffset', 'conditioning'}
    require(set(data) <= allowed and data.get('schemaVersion') == 1 and data.get('kind') == 'item-asset', 'Unsupported item manifest')
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', data.get('id', '')), 'Safe item ID required')
    require(data.get('profile') == 'pixal-single-v1', 'Items currently qualify only the single-image workflow')
    require(data.get('generationSettings') == GENERATION, 'Item generation settings must match the frozen preset')
    integer(data.get('geometrySeedOffset', 0), 0, 2147483647, 'geometry seed offset')
    require(isinstance(data.get('landmarks'), list), 'Explicit measured landmark inventory required')
    require(data.get('materials') and all(isinstance(row.get('name'), str) and row.get('region')
            for row in data['materials']), 'Explicit material inventory required')
    require(isinstance(data.get('inputs'), dict) and 'reference' in data['inputs'], 'Pinned detailed reference required')
    for role,value in data['inputs'].items():
        require(isinstance(value,dict) and set(value)=={'path','sha256'} and
                not Path(value['path']).is_absolute() and not Path(value['path']).drive and
                '..' not in Path(value['path']).parts and re.fullmatch(r'[a-f0-9]{64}',value['sha256']),
                'Portable input path and SHA256 required')
        if input_roles is None or role in input_roles: asset(path, value)
    profile = asset(path, data['familyProfile']); profile_data = family(profile['path'],validate_native=validate_native)
    if profile_data['nativePackaging'] == 'enabled':
        expected = dict.fromkeys(PARTS, data['id'])
        if profile_data['family'] == 'firearm-sling':
            from .parts import active_parts
            expected = {part:data['id'] if part in active_parts(profile_data) else 'hidden-placeholder' for part in PARTS}
        require(profile_data['allowedAssemblies'] == [expected],
                'This pilot exports exactly one declared matching assembly')
    require(data.get('features') and all(isinstance(row.get('name'), str) for row in data['features']), 'Protected feature inventory required')
    require(isinstance(data.get('openings'), list), 'Explicit intentional-opening inventory required')
    require(data.get('clientCoverage') == ['human-male', 'human-female'], 'Pilot coverage is Human male and female')
    if data.get('approval', {}).get('inputReviewComplete') is True and (input_roles is None or 'reference' in input_roles):
        from PIL import Image
        import math
        with Image.open(asset(path, data['inputs']['reference'])['path']) as image: width, height = image.size
        landmarks = data['landmarks']
        require(len(landmarks) >= 4 and len({row['name'] for row in landmarks}) == len(landmarks),
                'Review at least four distinct measured reference landmarks')
        for row in landmarks:
            point = row.get('pixel', [])
            require(len(point) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in point)
                    and 0 <= point[0] < width and 0 <= point[1] < height, 'Landmark outside original reference')
    require(data.get('conditioning','detailed-v1') in ('detailed-v1','clay-detail-v1'), 'Unsupported conditioning mode')
    if data.get('conditioning')=='clay-detail-v1':
        from .conditioning import validate_pair
        validate_pair(data)
    for name in ('geometry', 'detail'):
        if name in data['inputs']:
            require(data.get('conditioning')=='clay-detail-v1' or data['inputs'].get('geometry') == data['inputs'].get('detail'),
                    'Item geometry and appearance must use the same normalized detailed image')
    return data


def code_pins():
    from tools.headkit.common import code_pins as head_pins
    files = [p for p in sorted(Path(__file__).parent.rglob('*')) if p.is_file()
             and p.suffix in ('.py', '.json') and '__pycache__' not in p.parts]
    return head_pins() + [pin(p) for p in files]


def source_version():
    return digest({Path(p['path']).relative_to(ROOT).as_posix(): p['sha256'] for p in code_pins()})


def stage_roles(stage):
    return {'prepare':{'reference'},'inspect':{'geometryRaw'},'donor':{'geometryDonor','field'},
            'fit':{'texturedDonor','workingMesh','gripStandard'},'finish':{'reference'},'bake':{'reference'},
            'fixture':{'fixtureTemplate','maleCreature','femaleCreature','nwscript','comparisonBlueprint'},
            'calibrate':{'reference','geometry','detail','mask'},
            'geometry':{'reference','clayReference','geometry','detail','foregroundMask','geometryForegroundMask'},
            'appearance':{'reference','clayReference','geometry','detail','foregroundMask','geometryForegroundMask','geometryRaw','shape'}}.get(stage,set())


def all_pins(manifest_path, *, roles=None, native=True):
    if roles is not None and 'comparisonBlueprint' in roles:
        roles = set(roles) | {key for key in read(manifest_path)['inputs']
                            if re.fullmatch(r'comparisonBlueprint[0-9]*', key)}
    data = manifest(manifest_path,input_roles=roles,validate_native=native)
    pins = [pin(manifest_path), asset(manifest_path, data['familyProfile'])]
    pins += [asset(manifest_path, row) for role,row in data['inputs'].items() if roles is None or role in roles]
    # manifest() already validated this exact hash-bound family. Read its data
    # here rather than repeating the complete installed donor-stack audit.
    # The consumed namespace pins and final byte verification remain below.
    profile = read(pins[1]['path'])
    if profile['nativePackaging'] == 'enabled' and native:
        stack = asset(pins[1]['path'], profile['native']['stack']); pins.append(stack)
        for layer in read(stack['path'])['layers']:
            from .native_stack import namespace
            pins += namespace(stack['path'],layer)[2]
            pins += [asset(stack['path'], row['file']) for row in layer['resources']]
    verify(pins)
    return pins


def evidence_pins(path):
    data = read(path); pins = [pin(path)]
    for row in data.get('observations', []):
        pins += [asset(path, source) for source in row.get('screenshots', [])+row.get('logs', [])]
    return pins
