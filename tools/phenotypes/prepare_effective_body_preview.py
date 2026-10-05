"""CPU-only disposable GLBs from effective native body ASCII and palette/MTR bytes.

Never modifies source geometry, resources or compile receipts. These previews use
actual current runtime color/normal/roughness inputs, but glTF/Blender lighting,
normal-map TBN and specular response are approximations, not NWN client evidence.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image

from audit_geometry import arrays
from run_preparation import PreparationContext
from retarget import NODE, nodes, transforms
from place_purposebuilt_pelvis import BASIS, accessor, read_glb, write_glb


PARTS = ('head', 'neck', 'chest', 'pelvis', 'bicepl', 'bicepr', 'forel', 'forer',
         'handl', 'handr', 'legl', 'legr', 'shinl', 'shinr', 'footl', 'footr')
PALETTES = ('pal_skin01.tga', 'pal_hair01.tga', 'pal_armor01.tga', 'pal_armor02.tga',
            'pal_cloth01.tga', 'pal_cloth01.tga', 'pal_leath01.tga', 'pal_leath01.tga',
            'pal_tattoo01.tga', 'pal_tattoo01.tga')
RESREF = re.compile(r'^[a-zA-Z0-9_]{1,32}$')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


class Resolver:
    """Explicit ordered banks; every consumed file must match its pinned receipt."""
    def __init__(self, banks, inputs, context=None):
        self.banks = banks
        self.inputs = inputs
        self.context = context

    def image(self, path, mode):
        decode=lambda data: np.asarray(Image.open(BytesIO(data)).convert(mode))
        return self.context.prepared(path,'palette/image-decode',decode,settings={'mode':mode}) if self.context else decode(path.read_bytes())

    def file(self, name, optional=False):
        require(Path(name).name == name and RESREF.fullmatch(Path(name).stem) is not None,
                'Invalid resource name: '+name)
        for directory, hashes in self.banks:
            path = directory/name
            if path.exists():
                require(name in hashes and sha(path) == hashes[name], 'Unpinned/changed resource: '+str(path))
                self.inputs[str(path.resolve())] = hashes[name]
                return path
        if optional:
            return None
        raise RuntimeError('Missing pinned resource: '+name)


def plt_pixels(data):
    require(data[:8] == b'PLT V1  ' and len(data) >= 24, 'Invalid PLT header')
    layers, reserved, width, height = struct.unpack_from('<IIII', data, 8)
    require(layers == 10 and reserved == 0 and width > 0 and height > 0,
            'Unsupported PLT header dimensions/layers')
    require(len(data) == 24+2*width*height, 'Invalid PLT payload length')
    image = np.frombuffer(data, np.uint8, offset=24).reshape(height, width, 2)[::-1].copy()
    require(np.all((image[:, :, 1] < 10) | (image[:, :, 1] == 255)), 'Unsupported PLT layer')
    return image


def colorize_plt(data, palette_images, selectors):
    pixels = plt_pixels(data)
    result = np.zeros((*pixels.shape[:2], 4), dtype=np.uint8)
    for layer in np.unique(pixels[:, :, 1]):
        if layer == 255:
            continue
        require(int(layer) in palette_images and int(layer) in selectors, 'Missing explicit layer palette/selector')
        palette = np.asarray(palette_images[int(layer)])
        row = selectors[int(layer)]
        require(isinstance(row, int) and 0 <= row < len(palette) and palette.shape[1:] == (256, 3),
                'Palette row outside actual 256-shade palette')
        mask = pixels[:, :, 1] == layer
        result[mask, :3] = palette[row, pixels[:, :, 0][mask]]
        result[mask, 3] = 255
    return result


def mtr_fields(text):
    textures = {}
    parameters = {}
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        texture = re.fullmatch(r'texture([0-9]+)\s+(\S+)', line, re.I)
        parameter = re.fullmatch(r'parameter\s+float\s+(\S+)\s+([-+0-9.eE]+)', line, re.I)
        if texture:
            channel = int(texture[1]); value = texture[2].lower()
            require(channel in (0, 1, 3) and RESREF.fullmatch(value) is not None,
                    'Unsupported effective MTR texture binding: '+line)
            require(channel not in textures, 'Duplicate MTR texture binding')
            textures[channel] = value
        elif parameter:
            name = parameter[1].lower()
            require(name not in parameters, 'Duplicate MTR scalar')
            value = float(parameter[2]); require(np.isfinite(value), 'Nonfinite MTR scalar')
            parameters[name] = value
        elif not re.fullmatch(r'renderhint\s+NormalTangents', line, re.I):
            raise RuntimeError('Unsupported effective MTR statement: '+line)
    return textures, parameters


def mesh_corners(text, authored_required=False):
    """Expand independent position/UV indices without welding or shape alterations."""
    local_frames = transforms(nodes(text))
    result = []
    for match in NODE.finditer(text.split('endmodelgeom', 1)[0]):
        if match[1].lower() != 'trimesh':
            require(match[1].lower() == 'dummy', 'Unsupported nonrigid ASCII node: '+match[1])
            continue
        body = match[3]
        rendering = re.search(r'(?m)^\s*render\s+(\d+)\s*$', body)
        if rendering and rendering[1] == '0':
            continue
        faces = np.asarray(arrays(body, 'faces'))
        if not faces.size:
            continue
        require(faces.ndim == 2 and faces.shape[1] >= 7 and np.equal(faces, np.floor(faces)).all(),
                'Invalid triangle/UV indices')
        faces = faces.astype(int)
        vertices = np.asarray(arrays(body, 'verts'), float)
        uv = np.asarray(arrays(body, 'tverts'), float)
        normal = np.asarray(arrays(body, 'normals'), float)
        require(vertices.ndim == 2 and vertices.shape[1] == 3 and uv.ndim == 2 and uv.shape[1] >= 2,
                'Missing valid ASCII vertices/UVs')
        require(np.isfinite(vertices).all() and np.isfinite(uv).all(), 'Nonfinite ASCII attributes')
        require(faces[:, :3].min() >= 0 and faces[:, :3].max() < len(vertices)
                and faces[:, 4:7].min() >= 0 and faces[:, 4:7].max() < len(uv), 'ASCII index outside attribute arrays')
        triangle_positions = vertices[faces[:, :3]]
        if normal.size:
            require(normal.shape == vertices.shape and np.isfinite(normal).all(), 'Invalid authored ASCII normals')
            triangle_normals = normal[faces[:, :3]]
            policy = 'authored ASCII corner normals preserved, proper rotation only'
        else:
            require(not authored_required, 'Selected native part lacks authored ASCII normals')
            # Stock ASCII frequently omits normals. Smoothing group membership is
            # explicit; compute corner averages only over adjacent intersecting groups.
            face_normal = np.cross(triangle_positions[:, 1]-triangle_positions[:, 0],
                                   triangle_positions[:, 2]-triangle_positions[:, 0])
            require(np.all(np.linalg.norm(face_normal, axis=1) > 1e-15), 'Degenerate stock comparator face')
            adjacency = [[] for _ in vertices]
            for number, face in enumerate(faces):
                for vertex in face[:3]:
                    adjacency[vertex].append(number)
            triangle_normals = np.empty_like(triangle_positions)
            for number, face in enumerate(faces):
                group = int(face[3])
                for corner, vertex in enumerate(face[:3]):
                    neighbours = [i for i in adjacency[vertex] if group and (group & int(faces[i, 3]))]
                    value = face_normal[neighbours].sum(axis=0) if neighbours else face_normal[number]
                    length = np.linalg.norm(value)
                    require(length > 1e-15, 'Undefined stock computed normal')
                    triangle_normals[number, corner] = value/length
            policy = 'computed area-weighted smoothing-group stock normals; not actual compiled native normal proof'
        matrix = local_frames[match[2].lower()]
        rotation = matrix[:3, :3]
        require(np.allclose(rotation.T@rotation, np.eye(3), atol=1e-9) and np.linalg.det(rotation) > 0,
                'Preview rejects implicit mesh scale/stretch/reflection')
        p = triangle_positions@rotation.T+matrix[:3, 3]
        n = triangle_normals@rotation.T
        require(np.isfinite(n).all() and np.all(np.linalg.norm(n, axis=2) > .1), 'Invalid effective corner normals')
        bitmap = re.search(r'(?mi)^\s*bitmap\s+(\S+)', body)
        material = re.search(r'(?mi)^\s*materialname\s+(\S+)', body)
        require(bitmap and RESREF.fullmatch(bitmap[1]) is not None, 'Missing valid ASCII bitmap')
        result.append({'name': match[2], 'position': p, 'normal': n, 'uv': uv[faces[:, 4:7], :2],
                       'bitmap': bitmap[1].lower(), 'material': material[1].lower() if material else bitmap[1].lower(),
                       'normalPolicy': policy, 'meshLocalMatrix': matrix.tolist()})
    require(result, 'No renderable rigid ASCII trimeshes')
    return result


def png_bytes(image):
    target = BytesIO()
    Image.fromarray(image).save(target, format='PNG')
    return target.getvalue()


def material_inputs(row, resolver, selectors):
    mtr = resolver.file(row['material']+'.mtr', optional=True)
    textures, parameters = mtr_fields(mtr.read_text(encoding='ascii')) if mtr else ({}, {})
    materials = {'mtr': str(mtr.resolve()) if mtr else None, 'bindings': textures, 'parameters': parameters,
                 'layerSelectors': selectors, 'paletteResources': {}}
    if 0 in textures:
        color_path = resolver.file(textures[0]+'.tga')
        color = resolver.image(color_path,'RGBA')
        materials.update(colorPolicy='fixed MTR texture0', colorResource=str(color_path.resolve()))
    else:
        plt = resolver.file(row['bitmap']+'.plt', optional=True)
        if plt:
            data = plt.read_bytes()
            used_layers = np.unique(plt_pixels(data)[:, :, 1])
            palettes = {}
            for layer in used_layers:
                if layer == 255:
                    continue
                path = resolver.file(PALETTES[int(layer)])
                palettes[int(layer)] = resolver.image(path,'RGB')
                materials['paletteResources'][int(layer)] = str(path.resolve())
            color = colorize_plt(data, palettes, selectors)
            materials.update(colorPolicy='actual PLT shade/layer lookup with explicit per-layer rows',
                             colorResource=str(plt.resolve()), usedLayers=used_layers.tolist())
        else:
            color_path = resolver.file(row['bitmap']+'.tga')
            color = resolver.image(color_path,'RGBA')
            materials.update(colorPolicy='fixed ASCII bitmap TGA', colorResource=str(color_path.resolve()))
    normal = None
    if 1 in textures:
        path = resolver.file(textures[1]+'.tga')
        normal = resolver.image(path,'RGB')
        materials['normalResource'] = str(path.resolve())
    roughness = float(parameters.get('roughness', .72))
    require(0 <= roughness <= 1, 'Unsupported effective scalar roughness')
    rough = None
    if roughness > 0:
        materials['roughnessPolicy'] = 'positive MTR scalar has precedence over texture3'
    elif 3 in textures:
        path = resolver.file(textures[3]+'.tga')
        values = resolver.image(path,'RGB')[:, :, 0]
        rough = np.zeros((*values.shape, 3), np.uint8)
        rough[:, :, 0] = 255; rough[:, :, 1] = values
        metallic = float(parameters.get('metallicness', 0))
        require(0 <= metallic <= 1, 'Unsupported metallicness')
        rough[:, :, 2] = round(metallic*255)
        materials.update(roughnessPolicy='texture3 red, explicit MTR Roughness0', roughnessResource=str(path.resolve()))
    else:
        materials['roughnessPolicy'] = 'zero scalar, no texture3'
    materials.update(previewNormalStrength=1, nativeSpecularityIsNotExactGltfBRDF=True)
    return color, normal, rough, roughness, float(parameters.get('metallicness', 0)), materials


def export_part(path, meshes, resolver, selectors):
    doc = {'asset': {'version': '2.0', 'generator': 'effective native material preview; disposable CPU export'},
           'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0, 'name': path.stem}],
           'meshes': [{'primitives': []}], 'materials': [], 'images': [], 'textures': [],
           'samplers': [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}],
           'buffers': [], 'bufferViews': [], 'accessors': []}
    binary = bytearray()
    def view(data, target=None):
        binary.extend(b'\0'*(-len(binary)%4))
        item = {'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)}
        if target:
            item['target'] = target
        doc['bufferViews'].append(item); binary.extend(data)
        return len(doc['bufferViews'])-1
    def attribute(value, kind, component=5126):
        value = np.asarray(value, dtype='<f4' if component == 5126 else '<u4')
        item = {'bufferView': view(value.tobytes(), 34963 if component == 5125 else 34962),
                'componentType': component, 'count': len(value), 'type': kind}
        if kind == 'VEC3':
            item.update(min=value.min(axis=0).tolist(), max=value.max(axis=0).tolist())
        doc['accessors'].append(item)
        return len(doc['accessors'])-1
    def texture(value):
        doc['images'].append({'bufferView': view(png_bytes(value)), 'mimeType': 'image/png'})
        doc['textures'].append({'source': len(doc['images'])-1, 'sampler': 0})
        return {'index': len(doc['textures'])-1}
    records = []
    archives = {}
    for number, row in enumerate(meshes):
        color, normal, rough, scalar, metallic, inputs = material_inputs(row, resolver, selectors)
        p = row['position'].reshape(-1, 3)@BASIS
        n = row['normal'].reshape(-1, 3)@BASIS
        uv = row['uv'].reshape(-1, 2).copy(); uv[:, 1] = 1-uv[:, 1]
        material = {'name': row['material'], 'doubleSided': False, 'pbrMetallicRoughness': {
            'baseColorTexture': texture(color), 'metallicFactor': 1 if rough is not None else metallic,
            'roughnessFactor': 1 if rough is not None else scalar}, 'extras': {'nwnEffectiveMaterial': inputs}}
        if normal is not None:
            material['normalTexture'] = {**texture(normal), 'scale': 1}
        if rough is not None:
            material['pbrMetallicRoughness']['metallicRoughnessTexture'] = texture(rough)
        if np.any(color[:, :, 3] != 255):
            material.update(alphaMode='MASK', alphaCutoff=.5)
        doc['materials'].append(material)
        attrs = {'POSITION': attribute(p, 'VEC3'), 'NORMAL': attribute(n, 'VEC3'),
                 'TEXCOORD_0': attribute(uv, 'VEC2')}
        index = attribute(np.arange(len(p), dtype=np.uint32), 'SCALAR', 5125)
        doc['meshes'][0]['primitives'].append({'attributes': attrs, 'indices': index, 'material': number, 'mode': 4})
        archives.update({f'mesh{number}PositionNwn': row['position'], f'mesh{number}NormalNwn': row['normal'],
                         f'mesh{number}UvNwn': row['uv']})
        records.append({'node': row['name'], 'triangles': len(row['position']), 'meshLocalMatrix': row['meshLocalMatrix'],
                        'normalPolicy': row['normalPolicy'], 'materialInputs': inputs})
    binary.extend(b'\0'*(-len(binary)%4))
    doc['buffers'] = [{'byteLength': len(binary)}]
    write_glb(path, doc, bytes(binary))
    actual, blob = read_glb(path)
    for number, primitive in enumerate(actual['meshes'][0]['primitives']):
        attrs = primitive['attributes']
        ap = accessor(actual, blob, attrs['POSITION'])@BASIS.T
        an = accessor(actual, blob, attrs['NORMAL'])@BASIS.T
        au = accessor(actual, blob, attrs['TEXCOORD_0']).astype(float); au[:, 1] = 1-au[:, 1]
        original = meshes[number]
        ep = original['position'].reshape(-1,3).astype(np.float32)
        en = original['normal'].reshape(-1,3).astype(np.float32)
        eu = original['uv'].reshape(-1,2).astype(np.float32)
        require(np.array_equal(ap, ep) and np.array_equal(an, en), 'GLB encoded P/N basis round trip differs')
        # V inversion can introduce one binary32 ULP at serialization. Preserve
        # the exact source in the archive and declare the measured UV bound.
        errors = np.abs(au-eu)
        require(float(errors.max()) <= 2**-24, 'GLB UV coordinate conversion exceeds declared binary32 bound')
        records[number]['serializationProof'] = {'positionsNormalsFloat32ExactAfterInverseBasis': True,
          'uvMaximumAbsoluteError': float(errors.max()), 'uvMaximumDeclaredAbsoluteError': 2**-24,
          'triangleOrderAndCornerCountExact': True, 'sourceDoubleCornerArchiveExact': True,
          'nwnToGltfUv': '[u,1-v]', 'authoredNormalLengthNotRenormalized': True,
          'nativeTangentsNotClaimed': True, 'gltfBlenderTbnApproximation': True}
    archive = path.with_suffix('.corners.npz')
    np.savez_compressed(archive, **archives)
    return {'glb': str(path.resolve()), 'glbSha256': sha(path), 'sourceCornerArchive': str(archive.resolve()),
            'sourceCornerArchiveSha256': sha(archive), 'meshes': records}


def run(config_path, output):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    require(not output.exists(), 'Use a fresh preview output directory')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    preparation=PreparationContext(target_revision=config.get('targetRevision','stock-human-male'),
        rig_revision=config.get('rigRevision','stock-exact'),animation_revision='material-export-no-pose',
        settings=config,dependencies=[config_path,Path(__file__).resolve(),
            *[Path(__file__).with_name(name) for name in ['audit_geometry.py','retarget.py','place_purposebuilt_pelvis.py']]])
    require(config.get('schemaVersion') == 1, 'Preview config schema1 required')
    converted = Path(config['converted']).resolve()
    require(output != converted and converted not in output.parents, 'Output must not alter native converted directory')
    inventory_path = Path(config['effectiveInventory']).resolve()
    stock = Path(config['stockBank']).resolve()
    stock_inventory_path = Path(config['stockInventory']).resolve()
    helpers = [Path(__file__).resolve(), *[Path(__file__).with_name(n).resolve() for n in
              ['audit_geometry.py','retarget.py','place_purposebuilt_pelvis.py']]]
    inputs = {str(config_path): sha(config_path), **{str(p): sha(p) for p in helpers}}
    expected = config['expectedInputHashes']
    require(expected and all(sha(p) == digest for p,digest in expected.items()), 'Changed preview configuration input')
    inputs.update(expected)
    require(str(inventory_path) in expected and str(stock_inventory_path) in expected,
            'Explicit body/stock inventory hash pins required')
    inventory = json.loads(inventory_path.read_text())
    require(inventory['kind'] == 'effective-native-body-inventory', 'Effective runtime inventory required')
    body_hashes = inventory['resourceHashes']
    require({p.name for p in (converted/'resources').iterdir()} == set(body_hashes), 'Native resource inventory differs')
    require(all(sha(converted/'resources'/n) == digest for n,digest in body_hashes.items()), 'Native resource bytes changed')
    require(not any(n.endswith('.2da') or n == 'pmh0.mdl' or n.startswith(('a_ba','a_fa','sr_a')) for n in body_hashes),
            'Body preview requires isolated parts without table/root/animation overrides')
    for name,digest in body_hashes.items():
        inputs[str((converted/'resources'/name).resolve())] = digest
    stock_index = json.loads(stock_inventory_path.read_text())['files']
    prefix = stock.name+'/'
    stock_hashes = {k[len(prefix+'raw/'):]: v['sha256'] for k,v in stock_index.items() if k.startswith(prefix+'raw/')}
    stock_ascii = {k[len(prefix+'ascii/'):]: v['sha256'] for k,v in stock_index.items() if k.startswith(prefix+'ascii/')}
    banks = []
    for bank in config.get('resourceBanks', []):
        receipt = Path(bank['inventory']).resolve()
        require(str(receipt) in expected, 'Unpinned supplemental inventory')
        index = json.loads(receipt.read_text())
        require(index.get('pass') is True and index.get('overridesDisabled') is True, 'Non-stock supplemental extraction')
        hashes = {r['resource']: r['rawSha256'] for r in index['resources']}
        banks.append((Path(bank['path']).resolve(), hashes))
    banks.append((stock/'raw', stock_hashes))
    protected_directories = [converted, stock, *[p for p,_ in banks]]
    require(all(output != p and p not in output.parents for p in protected_directories),
            'Preview output must be outside every source bank')
    candidate = Resolver([(converted/'resources', body_hashes), *banks], inputs, preparation)
    comparator = Resolver(banks, inputs, preparation)
    native_receipt_path = converted/'native-compile.json'
    require(str(native_receipt_path) in expected, 'Native ASCII association receipt not pinned')
    native = json.loads(native_receipt_path.read_text())
    native_rows = {row['name']: row for row in native['models']}
    model_parts = inventory['modelParts']
    require(set(model_parts) == {n for n in body_hashes if n.endswith('.mdl')}, 'Declared effective model set differs')
    require(set(model_parts.values()).issubset(PARTS), 'Unknown effective body part')
    source_rows = {}
    for model, part in model_parts.items():
        require(model == 'pmh0_'+part+'001.mdl' and model in native_rows, 'Non-stock Human style001 model mapping')
        ascii_path = converted/'ascii'/model
        require(sha(ascii_path) == native_rows[model]['sourceSha256']
                and body_hashes[model] == native_rows[model]['binarySha256'], 'ASCII/native compile association differs')
        inputs[str(ascii_path.resolve())] = sha(ascii_path)
        source_rows[part] = {'ascii': ascii_path, 'nativeBinarySha256': body_hashes[model]}
    require(len(source_rows) == len(model_parts), 'Duplicate effective part mapping')
    skin_rows = config.get('skinRows', [3,8])
    require(skin_rows and all(isinstance(r, int) and 0 <= r < 176 for r in skin_rows), 'Invalid skin rows')
    selectors = {int(k): v for k,v in config['layerSelectors'].items()}
    require(set(selectors) == set(range(10)) and all(isinstance(v,int) and 0 <= v < 176 for v in selectors.values()),
            'Ten explicit layer selector rows required')
    parsed = {}
    for part in PARTS:
        name = 'pmh0_'+part+'001.mdl'
        path = stock/'ascii'/name
        require(name in stock_ascii and sha(path) == stock_ascii[name], 'Unpinned actual stock ASCII part')
        inputs[str(path.resolve())] = stock_ascii[name]
        parsed[('stock',part)] = preparation.prepared(path,'geometry-decode',lambda data:mesh_corners(data.decode('cp1252')),settings={'authoredRequired':False})
        if part in source_rows:
            path = source_rows[part]['ascii']
            parsed[('native',part)] = preparation.prepared(path,'geometry-decode',lambda data:mesh_corners(data.decode('cp1252'),authored_required=True),settings={'authoredRequired':True})
    output.mkdir(parents=True)
    for helper in helpers:
        shutil.copyfile(helper, output/('executed-'+helper.name))
    configurations = []
    results = []
    for skin in skin_rows:
        chosen = {**selectors, 0: skin}
        for kind in ['native', 'stock']:
            directory = output/(kind+'-skin'+str(skin)); directory.mkdir()
            parts = {}
            rows = {}
            for part in PARTS:
                effective = kind == 'native' and part in source_rows
                row = export_part(directory/(part+'.glb'), parsed[('native' if effective else 'stock', part)],
                                  candidate if effective else comparator, chosen)
                row.update(sourceKind='effective selected native ASCII' if effective else 'actual stock comparator fallback',
                           sourceAscii=str((source_rows[part]['ascii'] if effective else stock/'ascii'/('pmh0_'+part+'001.mdl')).resolve()))
                parts[part] = row['glb']; rows[part] = row
            preview = directory/'stock-replacement.json'
            save(preview, {'label': ('Effective native body' if kind == 'native' else 'Stock Human effective palette')+' skin'+str(skin),
                          'modelPrefix':'pmh0', 'height':1.9339157, 'shoulderStyle':0, 'parts':parts})
            configurations.append({'path':str(preview.resolve()),'sha256':sha(preview)})
            results.append({'kind':kind,'skinRow':skin,'layerSelectors':chosen,'parts':rows})
    require(all(sha(p) == digest for p,digest in inputs.items()), 'Preview input changed during export')
    report = {'schemaVersion':1,'readOnlySourceInputs':True,'pass':True,'sourceInventory':str(inventory_path),
              'effectiveResourceCount':len(body_hashes),'effectiveNativeParts':sorted(source_rows),
              'stockFallbackParts':sorted(set(PARTS)-set(source_rows)), 'inputHashes':inputs,
              'sourceResourcesBytesUnchanged':True,'previewConfigs':configurations,'variants':results,
              'approximations':['glTF/Blender lighting and BRDF differ from NWN:EE.',
                'No native compiled TBN export; Blender reconstructs tangents from actual UVs and authored normals.',
                'Stock ASCII without normals uses recorded smoothing-group computed normals, not native exactness.',
                'PLT lookup is actual selected row/shade/layer; native runtime filtering and palette changes still require client testing.'],
              'clientLaunched':False,'nativeCompilationInvoked':False,'geometryFittingInvoked':False,'preparation':preparation.receipt()}
    save(output/'preview-export.json',report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = run(args.config,args.output)
    print(json.dumps({'pass':result['pass'],'effectiveParts':result['effectiveNativeParts'],
                      'effectiveResourceCount':result['effectiveResourceCount'],'previewConfigs':result['previewConfigs']}))


if __name__ == '__main__':
    main()
