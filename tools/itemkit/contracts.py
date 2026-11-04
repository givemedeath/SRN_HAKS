"""Portable design contracts; native facts must come from a pinned content stack."""
from pathlib import Path
import re
from tools.headkit.common import ROOT, asset, digest, pin, read, require, verify

BASELINE = 'e607a617c273828a37d8fc56dd43d7d8a0070844'
PARTS = ('b', 'm', 't')
GENERATION = {'preset': 'pixal-single-v1', 'shapeResolution': 1536, 'shapeCFG': 12,
              'textureCFG': 1, 'textureSteps': 12}


def whole_shield(data):
    return (data.get('family') == 'shield' and data.get('nativePackaging') == 'enabled'
            and data.get('native', {}).get('kind') == 'shield-whole-v1')


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
    require(data.get('family') in ('shortsword', 'dagger', 'throwing-knife', 'longsword', 'greatsword', 'staff', 'bow', 'whip', 'shield', 'firearm-sling', 'firearm-crossbow', 'crossbow', 'catalog-object'), 'Unsupported item family')
    generation_only = data['family'] == 'catalog-object'
    shield = whole_shield(data)
    parts = ('whole',) if generation_only or shield else PARTS
    require(data.get('materialRoute') == 'diffuse', 'Only diffuse materials are qualified for this pilot')
    require(data.get('runtimeTextureSize') in (512, 1024, 2048), 'Unsupported runtime texture size')
    if data['family'] in ('firearm-sling', 'firearm-crossbow', 'crossbow'):
        require(data['runtimeTextureSize'] == 1024, 'The firearm package route is qualified for 1K diffuse only')
    require(data.get('bakeSize') == 4096, 'Source bake must be 4K')
    require(data.get('nativePackaging') in ('pending-contract', 'enabled', 'blocked'), 'Explicit native packaging state required')
    if generation_only:
        require(data['nativePackaging'] == 'blocked', 'Catalog objects require a separately qualified native adapter')
        require(data.get('sourceExport') == {'remeshResolution':768, 'targetFaceCount':200000, 'signMode':'udf'},
                'Catalog generation uses the qualified 200K UDF donor route')
    settings=data.get('resources', {})
    require(set(settings) <= {'texturePrefix','hak','module','blueprint','displayName'}, 'Unsupported resource identity')
    for key in ('texturePrefix','hak','module','blueprint'):
        if key in settings: resref(settings[key])
    if 'texturePrefix' in settings: require(len(settings['texturePrefix'])<=13,'Texture prefix leaves no appearance suffix')
    if data['family'] == 'shield' and not shield or data['family'] == 'firearm-sling' and 'firearm' not in data:
        require(data['nativePackaging'] == 'blocked', 'Shield and unqualified Sling native adapters are deferred')
    budgets = data['budgets']
    if shield:
        require('firearm' not in data and budgets['visible']==10000 and budgets['shadow']==500,
                'Whole Shield has its own 10000/500 budget and handling')
    if data['family'] == 'firearm-crossbow':
        require(data.get('firearm') == {'subtype':'rifle'}, 'Explicit longarm firearm configuration required')
    firearm_slot = None
    if data['family'] in ('bow', 'whip'):
        require('firearm' not in data and budgets['visible']==10000 and budgets['shadow']==500,
                'Rigged weapons require their own 10000/500 route')
        firearm_slot = 'm'
    if data['family'] == 'crossbow':
        require('firearm' not in data, 'Crossbows retain their own handling identity')
        require(budgets['visible'] == 10000 and budgets['shadow'] == 500, 'Crossbow cap is 10000/500')
        firearm_slot = 't'
    if 'firearm' in data:
        from .firearms import SLOTS
        require(data['family'] in ('firearm-sling', 'firearm-crossbow') and set(data['firearm']) == {'subtype'}
                and data['firearm']['subtype'] in SLOTS, 'Explicit supported firearm slot required')
        if data['family'] == 'firearm-crossbow':
            require(data['firearm']['subtype'] == 'rifle', 'Crossbow-carried firearms require the longarm slot')
        firearm_slot = SLOTS[data['firearm']['subtype']]
        require(budgets['visible'] == 10000 and budgets['shadow'] == 500, 'Firearm trial cap is 10000/500')
    require(set(budgets) == {'visible', 'shadow', 'parts'}, 'Explicit whole-object and per-part budgets required')
    for kind in ('visible', 'shadow'):
        integer(budgets[kind], 4, 200000, kind + ' assembly budget')
        require(set(budgets['parts']) == set(parts), 'Declare exactly the processing parts for this route')
        for part, row in budgets['parts'].items():
            integer(row[kind], 0 if firearm_slot and kind == 'shadow' and part != firearm_slot else 4,
                    budgets[kind], kind + ' part budget')
            if firearm_slot and part != firearm_slot:
                require(row == {'visible': 4, 'shadow': 0}, 'Inactive firearm slots require hidden placeholders')
        require(sum(row[kind] for row in budgets['parts'].values()) <= budgets[kind], 'Part budgets exceed assembly budget')
    require(data.get('allowedAssemblies') and all(isinstance(row, dict) and set(row) == set(parts)
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


def crossbow_motion_inputs(path, data):
    motion = data['native'].get('motion', {})
    require(set(motion) == {'method','proof','review','working'}
            and motion.get('method') == 'skinned-xbowshot-v1', 'Reviewed skinned crossbow motion required')
    proof_pin = asset(path, motion['proof']); review_pin = asset(path, motion['review'])
    proof, review = read(proof_pin['path']), read(review_pin['path'])
    require(asset(path, motion['working']) == proof['working'], 'Crossbow motion belongs to another working mesh')
    rows = [proof_pin, review_pin]+[proof[key] for key in
            ('working','fit','ascii','binary','decompiled','rigRoundtrip','poses')]+review['frames']
    verify(rows)
    return rows, proof, review


def rigged_motion_inputs(path, data):
    """Reuse one reviewed motion result, while freshly checking its actual bytes."""
    motion=data['native'].get('motion',{});family=data['family']
    require(set(motion)=={'method','proof','review','bodyReview'}
            and motion['method']=='skinned-'+family+'-v1', 'Reviewed rigged motion required')
    proof_pin=asset(path,motion['proof']);review_pin=asset(path,motion['review']);body_pin=asset(path,motion['bodyReview'])
    proof,review,body=read(proof_pin['path']),read(review_pin['path']),read(body_pin['path'])
    require(proof.get('rigRoundtrip',{}).get('passed') is True
            and proof.get('skinRoundtrip',{}).get('nativeWeightRoundtrip') is True
            and review.get('decision')=='approved-generated-'+family+'-motion-for-appearance'
            and review.get('nativeTarget')==proof_pin and review.get('bodyMotionReview')==body_pin
            and body.get('currentShippedBodies') is True and len(body.get('frames',()))>=6,
            'Rigged hierarchy/weight/body-motion review is incomplete')
    rows=[proof_pin,review_pin,body_pin]+[proof[k] for k in ('ascii','binary','decompiled','poses','atlas','measurement')]+body['frames']
    verify(rows)
    return rows,proof,review


def native_contract(path, data):
    import numpy as np
    require(data.get('family') != 'catalog-object', 'Catalog objects have no qualified native attachment or resource contract')
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
    row = twoda(Path(table['path']).read_text(encoding='utf-8-sig')).get(str(native['baseItem']))
    require(row is not None, 'Missing effective native BaseItem row')
    require(row['ItemClass'].lower() == native['itemClass'] and int(row['ModelType']) == native['modelType'],
            'Native family differs from effective baseitems')
    firearm = data['family'] == 'firearm-sling'
    crossbow = data['family'] == 'crossbow'
    longarm = data['family'] in ('firearm-crossbow', 'crossbow')
    shield = whole_shield(data)
    if data['family'] in ('bow', 'whip'):
        from PIL import Image
        bow = data['family'] == 'bow'
        base, item_class, size = (8, 'wbwln', [64,128]) if bow else (111, 'wwhip', [64,64])
        require(native['baseItem']==base and native['itemClass']==item_class and native['modelType']==2,
                'Rigged weapon must retain its actual native carrier')
        require([int(row['InvSlotWidth'])*32,int(row['InvSlotHeight'])*32]==size,
                'Rigged weapon native footprint changed')
        require(row['WeaponWield']==('5' if bow else '****'), 'Rigged weapon handling changed')
        if bow: require(row['AmmunitionType']=='1', 'Bow requires native Arrow ammunition')
        require(native.get('iconDimensions')==dict.fromkeys(PARTS,size)
                and set(native.get('iconDonors',{}))==set(PARTS), 'Rigged multipart icons required')
        for part in PARTS:
            require(re.fullmatch(item_class+'_'+part+r'_\d{3}\.mdl',native['donors'][part].lower()),
                    'Wrong rigged donor part')
            require(re.fullmatch('i'+item_class+'_'+part+r'_\d{3}\.tga',native['iconDonors'][part].lower()),
                    'Wrong rigged icon part')
            icon=resources.get(native['iconDonors'][part].lower());require(icon is not None,'Missing rigged icon donor')
            with Image.open(icon['path']) as image: require(list(image.size)==size, 'Rigged stock icon canvas changed')
        rigged_motion_inputs(path, data)
    if shield:
        from PIL import Image
        require(native['baseItem']==56 and native['itemClass']=='ashlw' and native['modelType']==0
                and int(row['WeaponWield'])==7, 'Shield requires the native offhand single-model carrier')
        dimensions=[int(row['InvSlotWidth'])*32,int(row['InvSlotHeight'])*32]
        require(dimensions==[64,96] and native.get('iconDimensions')=={'whole':dimensions},
                'Shield inventory dimensions differ')
        require(set(native['donors'])=={'whole','icon'}
                and re.fullmatch(r'ashlw_\d{3}\.mdl',native['donors']['whole'].lower()),
                'Installed whole Shield and icon required')
    if longarm:
        from .firearms import longarm_row
        from PIL import Image
        longarm_row(Path(table['path']).read_bytes())
        require(native['baseItem'] == 6 and native['itemClass'] == 'wbwxh' and native['modelType'] == 2,
                'Longarm contract must use native Heavy Crossbow without a table override')
        if crossbow:
            from tools.phenomorpher.phenomorpher.engine.anim_library import load_model
            from tools.phenomorpher.phenomorpher.engine.rig_native import compare
            rows, proof, review = crossbow_motion_inputs(path, data)
            require(proof.get('skinPositionAndWeightRoundtrip') is True
                    and review.get('decision') == 'approved-native-motion-prototype'
                    and review.get('nativeProof') == rows[0]
                    and len(review['frames']) >= 12
                    and 0 <= review.get('maximumReceiverCoreDisplacement', 1) <= 1e-6,
                    'Crossbow motion/skin/receiver review is incomplete')
            model = load_model(proof['binary']['path'])
            require(re.fullmatch(r'wbwxh_t_\d{3}', model['name'])
                    and model['parent'] == 'null' and set(model['clips']) == {'xbowshot'}
                    and {'body_bind','limb_l','limb_r','drawdummy'} <= set(model['nodes'])
                    and any(row['flags'] == 97 for row in model['nodes'].values())
                    and compare(proof['binary']['path'], proof['ascii']['path'])['passed'],
                    'Crossbow requires its actual skinned firing hierarchy')
        else:
            require(data.get('firearm') == {'subtype':'rifle'}, 'Explicit rigid longarm route required')
        require(set(native['donors']) == {*PARTS, 'icon'}, 'All installed crossbow parts and inventory icon required')
        require(native.get('iconDimensions') == {'t':[64,128]}, 'Review changed longarm inventory dimensions')
        for part in PARTS:
            require(re.fullmatch(r'wbwxh_'+part+r'_\d{3}\.mdl',native['donors'][part].lower()),
                    'Installed crossbow donor assignment differs from its native part')
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
    elif not shield:
        require(native['modelType'] == 2, 'Pilot requires a verified composite weapon contract')
    if data['family'] == 'shortsword':
        require(native['baseItem'] == 0 and native['itemClass'] == 'wswss', 'Shortsword contract must match native short sword')
    if data['family'] == 'dagger':
        require(native['baseItem'] == 22 and native['itemClass'] == 'wswdg', 'Dagger contract must match native dagger')
    if data['family'] == 'throwing-knife':
        from PIL import Image
        require(native['baseItem']==63 and native['itemClass']=='wthax' and native['modelType']==2
                and int(row['WeaponWield'])==11, 'Throwing Knife requires the native thrown-weapon carrier')
        require([int(row['InvSlotWidth']),int(row['InvSlotHeight'])]==[1,2], 'Thrown native footprint changed')
        require(native.get('iconDimensions')==dict.fromkeys(PARTS,[32,64])
                and set(native.get('iconDonors',{}))==set(PARTS), 'Thrown multipart inventory icons required')
        for part in PARTS:
            require(re.fullmatch(r'wthax_'+part+r'_\d{3}\.mdl',native['donors'][part].lower()), 'Wrong thrown donor part')
            require(re.fullmatch(r'iwthax_'+part+r'_\d{3}\.tga',native['iconDonors'][part].lower()), 'Wrong thrown icon part')
            icon=resources.get(native['iconDonors'][part].lower());require(icon is not None, 'Missing thrown icon donor')
            with Image.open(icon['path']) as image:require(image.size==(32,64), 'Thrown stock icon canvas changed')
    if data['family'] == 'longsword':
        require(native['baseItem'] == 1 and native['itemClass'] == 'wswls', 'Longsword contract must match native longsword')
    if data['family'] == 'greatsword':
        from PIL import Image
        require(native['baseItem']==13 and native['itemClass']=='wswgs' and native['modelType']==2,
                'Two-handed sword requires the native Greatsword carrier')
        require([int(row['InvSlotWidth']),int(row['InvSlotHeight'])]==[2,5], 'Greatsword native footprint changed')
        require(native.get('iconDimensions')==dict.fromkeys(PARTS,[64,160])
                and native.get('iconCanvasDimensions')==dict.fromkeys(PARTS,[64,256])
                and set(native.get('iconDonors',{}))==set(PARTS),'Greatsword logical icons and stock canvases required')
        for part in PARTS:
            require(re.fullmatch(r'wswgs_'+part+r'_\d{3}\.mdl',native['donors'][part].lower()),'Wrong Greatsword donor part')
            require(re.fullmatch(r'iwswgs_'+part+r'_\d{3}\.tga',native['iconDonors'][part].lower()),'Wrong Greatsword icon part')
            icon=resources.get(native['iconDonors'][part].lower());require(icon is not None,'Missing Greatsword icon donor')
            with Image.open(icon['path']) as image:require(image.size==(64,256),'Greatsword stock icon canvas changed')
    if data['family'] == 'staff':
        from PIL import Image
        require(native['baseItem']==50 and native['itemClass']=='wdbqs' and native['modelType']==2,
                'Staff requires the native Quarterstaff carrier')
        require([int(row['InvSlotWidth']),int(row['InvSlotHeight'])]==[1,4], 'Staff native footprint changed')
        require(native.get('iconDimensions')==dict.fromkeys(PARTS,[32,128])
                and set(native.get('iconDonors',{}))==set(PARTS),'Staff multipart inventory icons required')
        for part in PARTS:
            require(re.fullmatch(r'wdbqs_'+part+r'_\d{3}\.mdl',native['donors'][part].lower()),'Wrong Staff donor part')
            require(re.fullmatch(r'iwdbqs_'+part+r'_\d{3}\.tga',native['iconDonors'][part].lower()),'Wrong Staff icon part')
            icon=resources.get(native['iconDonors'][part].lower());require(icon is not None,'Missing Staff icon donor')
            with Image.open(icon['path']) as image:require(image.size==(32,128),'Staff stock icon canvas changed')
    resref(native['itemClass'])
    if not firearm and not longarm and not shield: require(set(native['donors']) == set(PARTS), 'All composite donor parts required')
    for name in native['donors'].values():
        require(resources.get(name.lower()) is not None, 'Missing native donor: ' + name)
    if longarm or shield:
        with Image.open(resources[native['donors']['icon'].lower()]['path']) as icon:
            # Shield has a2x3 logical footprint on the stock power-of-two canvas.
            require(icon.size == (64,128), 'Native icon donor differs from its qualified canvas')
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
    require(data.get('family') not in ('firearm-sling','firearm-crossbow','crossbow','shield'), 'Use the explicit whole-weapon assembly allocator')
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
        if whole_shield(profile_data): expected={'whole':data['id']}
        if profile_data['family'] in ('firearm-sling','firearm-crossbow','crossbow','bow','whip'):
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
            'calibrate':{'reference','geometry','detail','mask','calibrationReference','calibrationDetail','sourceAudit','referenceApproval'},
            'geometry':{'reference','clayReference','geometry','detail','foregroundMask','geometryForegroundMask','sourceAudit','referenceApproval'},
            'appearance':{'reference','clayReference','geometry','detail','foregroundMask','geometryForegroundMask','geometryRaw','shape','sourceAudit','referenceApproval','geometryReview','workingMesh'}}.get(stage,set())


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
        if profile['family'] == 'crossbow':
            pins += crossbow_motion_inputs(pins[1]['path'], profile)[0]
        if profile['family'] in ('bow','whip'):
            pins += rigged_motion_inputs(pins[1]['path'], profile)[0]
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
