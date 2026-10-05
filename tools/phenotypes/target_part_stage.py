"""Stage a v2 target-local body candidate and its original material inputs.

Skin uses PLT painted intensity, original normal pixels at strength one and
ORM-green roughness. A fixed opaque garment is owned only by the pelvis. This
offline stage never implies rig, shader, native compiler or client acceptance.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

import numpy as np
from PIL import Image

import target_contract as contract
from mirror_stock_limb_part import detached_affine_bake
from place_purposebuilt_pelvis import raw_corners, read_glb
from stage_stock_part import geometry, write_ascii
from target_part_pipeline import pin, read_target, verify_source_receipt


def image_pixels(doc, binary, texture):
    contract.require(texture.get('texCoord', 0) == 0 and not texture.get('extensions'),
                     'Only unchanged TEXCOORD_0 texture bindings supported')
    item = doc['textures'][texture['index']]
    contract.require(not item.get('extensions'), 'Texture extension requires an explicit material adapter')
    image = doc['images'][item['source']]
    contract.require('bufferView' in image and not image.get('uri'), 'Embedded maps required')
    view = doc['bufferViews'][image['bufferView']]; start = view.get('byteOffset', 0)
    contract.require(view.get('buffer', 0) == 0, 'External material buffer')
    pixels = np.asarray(Image.open(BytesIO(binary[start:start+view['byteLength']])).convert('RGB'))
    contract.require(pixels.shape == (2048, 2048, 3), 'Frozen 2K material maps required')
    return pixels


def material_inputs(doc, binary, roles, part, ao_strength):
    contract.require(ao_strength in (0, .15, .35), 'AO comparison strength must be 0, 0.15 or 0.35')
    contract.require(set(roles.values()) <= {'skin', 'garment'} and 'skin' in roles.values(),
                     'Explicit skin/garment material ownership required')
    contract.require(part == 'pelvis' or 'garment' not in roles.values(), 'Garment belongs only to pelvis')
    rows = {}; source = []
    for material_id, role in sorted(roles.items()):
        material = doc['materials'][material_id]
        contract.require(material.get('alphaMode', 'OPAQUE') == 'OPAQUE', 'Opaque body/garment materials required')
        pbr = material['pbrMetallicRoughness']
        contract.require(pbr.get('baseColorFactor', [1,1,1,1]) == [1,1,1,1],
                         'Nonidentity baseColorFactor needs a separately reviewed material operation')
        contract.require(material['normalTexture'].get('scale', 1) == 1,
                         'Original normal strength one required')
        color = image_pixels(doc, binary, pbr['baseColorTexture'])
        normal = image_pixels(doc, binary, material['normalTexture'])
        orm = image_pixels(doc, binary, pbr['metallicRoughnessTexture'])
        factor = pbr.get('roughnessFactor', 1)
        contract.require(np.isfinite(factor) and 0 <= factor <= 1, 'Finite unit-interval roughness factor required')
        roughness = np.rint(orm[:,:,1].astype(float)*factor).clip(0,255).astype(np.uint8)
        if ao_strength:
            ao = image_pixels(doc, binary, material['occlusionTexture'])[:,:,0].astype(float)/255
        else:
            ao = np.ones((2048,2048), dtype=float)
        # The same untreated parent produces all AO variants; none is applied cumulatively.
        intensity = color.astype(float) @ np.asarray([.2126,.7152,.0722])
        intensity = (intensity*(1-ao_strength*(1-ao))).clip(0,255).astype(np.uint8)
        value = {'color':color, 'normal':normal, 'roughness':roughness, 'intensity':intensity}
        if role in rows:
            contract.require(all(np.array_equal(rows[role][key], value[key]) for key in value),
                             'Multiple materials in one declared role require the same atlas inputs')
        else:
            rows[role] = value
        source.append({'material':material_id, 'role':role, 'roughnessFactor':factor,
                       'normalStrength':1, 'sourceBindings':material,
                       'roughnessPolicy':'ORM green times authored roughnessFactor, rounded to byte'})
    return rows, source


def write_model(path, model, positions, normals, native_uv, primitive_roles):
    """Serialize each role independently without merging skin and garment faces."""
    header = [f'newmodel {model}', f'setsupermodel {model} NULL', 'classification CHARACTER',
              'setanimationscale 1', f'beginmodelgeom {model}', f'node dummy {model}', '  parent NULL', 'endnode']
    counts = {}
    with tempfile.TemporaryDirectory() as temporary:
        for index, role in enumerate(sorted(set(primitive_roles))):
            mask = np.asarray(primitive_roles) == role
            temp = Path(temporary)/'part.mdl'
            counts[role] = write_ascii(temp, model, positions[mask], native_uv[mask], normals[mask])
            block = re.search(r'(?ms)^node trimesh \S+\n.*?^endnode', temp.read_text(encoding='ascii'))[0]
            material = model + ('f' if role == 'garment' else '')
            block = re.sub(r'^node trimesh \S+', f'node trimesh {model}p{index}', block)
            block = re.sub(r'(?m)^  (bitmap|materialname) \S+', lambda m:'  '+m[1]+' '+material, block)
            header.append(block)
    header += [f'endmodelgeom {model}', f'donemodel {model}']
    path.write_text('\n'.join(header)+'\n', encoding='ascii')
    return counts


def stage(config_path, output):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path, target = read_target(config)
    contract.require(config.get('kind') == 'target-part-stage' and config.get('diagnosticOnly') is True,
                     'Explicit diagnostic stage configuration required')
    part = config['part']; space = config['coordinateSpace']
    contract.require(part in contract.BODY_PARTS, 'Generated staging owns declared body parts only')
    contract.require(space in ('working','runtime'), 'Explicit staging coordinate space required')
    source = pin(config['source'], config['sourceSha256'])
    receipt_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    parent = verify_source_receipt(source, receipt_path, target_path, target, part, space)
    doc, binary = read_glb(source)
    # Canonicalize/verify without changing accepted geometry or maps.
    _, _, _, canonical = detached_affine_bake(doc, binary, np.eye(4))
    contract.require(doc['nodes'] == [{'name':'detached_geometry','mesh':0}], 'Canonical identity-node candidate required')
    p, n, uv, primitives = raw_corners(doc, binary)
    active_materials = {row['material'] for row in primitives}
    roles = {int(key):role for key,role in config['materialRoles'].items()}
    contract.require(set(roles) == active_materials, 'Each active material must have exactly one declared role')
    material_rows, material_proof = material_inputs(doc, binary, roles, part, config.get('aoStrength',0))
    primitive_roles = [roles[row['material']] for row in primitives for _ in range(row['triangles'])]
    native_uv = uv.copy(); native_uv[:,:,1] = 1-native_uv[:,:,1]
    geometry_proof = geometry(p)
    contract.require(not geometry_proof['degenerateTriangles'] and not geometry_proof['coincidentTriangles'],
                     'Coincident/degenerate triangles block staging')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable stage required')
    (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    model = contract.model(target,part)
    counts = write_model(output/'ascii'/(model+'.mdl'),model,p,n,native_uv,primitive_roles)
    resources = output/'resources'
    for role, pixels in material_rows.items():
        material = model + ('f' if role == 'garment' else '')
        contract.require(len(material+'n') <= 16 and len(material+'r') <= 16, 'Material resref too long')
        normal_name, roughness_name = material+'n', material+'r'
        Image.fromarray(pixels['normal']).save(resources/(normal_name+'.tga'))
        Image.fromarray(np.repeat(pixels['roughness'][:,:,None],3,axis=2)).save(resources/(roughness_name+'.tga'))
        text = 'renderhint NormalTangents\ntexture1 '+normal_name+'\ntexture3 '+roughness_name+'\n'
        text += 'parameter float Roughness 0\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n'
        if role == 'skin':
            plt = np.stack([pixels['intensity'],np.zeros_like(pixels['intensity'])],axis=2)[::-1].copy()
            (resources/(material+'.plt')).write_bytes(b'PLT V1  '+struct.pack('<IIII',10,0,2048,2048)+plt.tobytes())
            decoded = np.frombuffer((resources/(material+'.plt')).read_bytes()[24:],dtype='u1').reshape(2048,2048,2)[::-1]
            contract.require(np.array_equal(decoded[:,:,0],pixels['intensity']) and not decoded[:,:,1].any(), 'PLT intensity/layer serialization differs')
        else:
            Image.fromarray(pixels['color']).save(resources/(material+'.tga'))
            text += 'texture0 '+material+'\n'
        (resources/(material+'.mtr')).write_text(text,encoding='ascii')
        contract.require(np.array_equal(np.asarray(Image.open(resources/(normal_name+'.tga')).convert('RGB')),pixels['normal']), 'Serialized normal pixels differ')
        contract.require(np.array_equal(np.asarray(Image.open(resources/(roughness_name+'.tga')).convert('RGB'))[:,:,0],pixels['roughness']), 'Serialized roughness pixels differ')
    shutil.copyfile(__file__, output/'executed-helper.py')
    receipt = {'schemaVersion':2,'kind':'target-part-stage',**contract.binding(target_path,target,space),
               'part':part,'model':model,'joint':contract.PART_JOINTS[part],
               'source':str(source),'sourceSha256':contract.sha(source),
               'sourceReceipt':str(receipt_path),'sourceReceiptSha256':contract.sha(receipt_path),
               'statureApplications':parent['statureApplications'], 'materialRoles':roles,
               'aoStrength':config.get('aoStrength',0), 'untreatedParentSha256':contract.sha(source),
               'nativeGeometrySource':'ascii', 'asciiModel':str(output/'ascii'/(model+'.mdl')),
               'asciiModelSha256':contract.sha(output/'ascii'/(model+'.mdl')),
               'materialResourceHashes':{path.name:contract.sha(path) for path in sorted(resources.iterdir())},
               'rawAttributeAsciiProof':counts,'materialProof':material_proof,
               'canonicalGeometryProof':canonical,'geometry':geometry_proof,
               'frozenInputs':{str(path):contract.sha(path) for path in [config_path,target_path,source,receipt_path,
                    Path(__file__).resolve(),Path(__file__).with_name('target_contract.py'),
                    Path(__file__).with_name('target_part_pipeline.py'),Path(__file__).with_name('stage_stock_part.py'),
                    Path(__file__).with_name('mirror_stock_limb_part.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py')]},
               'diagnosticOnly':True,'rigPilotAccepted':target['rig']['pilotAccepted'],'productionAccepted':False,
               'nativeCompiled':False,'installedShaderVerified':False,'clientAccepted':False,
               'limitation':'Candidate material transport only; joint color continuity, installed shader behavior, native tangents and client appearance require review.'}
    result = output/'target-stage.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); result = stage(args.config,args.output)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
