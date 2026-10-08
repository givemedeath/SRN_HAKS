"""Stage a v2 target-local body candidate and its original material inputs.

Skin uses PLT painted intensity, original normal pixels at strength one and
ORM-green roughness. Fixed opaque garments use the declared chest/pelvis owners. This
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


def material_inputs(doc, binary, roles, part, ao_strength, garment_parts=('pelvis',), atlas_keys=None):
    contract.require(ao_strength in (0, .15, .35), 'AO comparison strength must be 0, 0.15 or 0.35')
    contract.require(set(roles.values()) <= {'skin', 'garment'} and 'skin' in roles.values(),
                     'Explicit skin/garment material ownership required')
    contract.require(part in garment_parts or 'garment' not in roles.values(),
                     'Garment belongs only to pelvis' if set(garment_parts) == {'pelvis'} else 'Garment belongs only to declared owners')
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
        key_role = role if atlas_keys is None else atlas_keys[material_id]
        if key_role in rows:
            contract.require(all(np.array_equal(rows[key_role][key], value[key]) for key in value),
                             'Multiple materials in one declared role require the same atlas inputs')
        else:
            rows[key_role] = value
        source.append({'material':material_id, 'role':role, 'roughnessFactor':factor,
                       'normalStrength':1, 'sourceBindings':material,
                       'roughnessPolicy':'ORM green times authored roughnessFactor, rounded to byte'})
    return rows, source


def validate_material_slots(value):
    contract.require(isinstance(value,dict) and value,'Explicit nonempty material slots required');result={}
    for key,row in value.items():
        contract.require(isinstance(key,str) and key.isdigit() and str(int(key))==key and isinstance(row,dict) and set(row)=={'role','atlasKey'},'Exact typed material slot required')
        contract.require(row['role']in ('skin','garment')and isinstance(row['atlasKey'],str)and re.fullmatch(r'skin(?:[1-9])?|garment',row['atlasKey'])is not None,'Bounded skin/garment atlas slot required')
        contract.require((row['role']=='garment')==(row['atlasKey']=='garment'),'Atlas role mismatch');result[int(key)]=row
    return result

def material_resref(model,key,role):
    name=model+('f'if role=='garment'else ''if key=='skin'else '')
    if role=='skin'and key!='skin':name=model[:-3]+'s'+key[4:]
    contract.require(len(name+'n')<=16 and len(name+'r')<=16,'Typed material resref exceeds16');return name


def write_model(path, model, positions, normals, native_uv, primitive_roles, material_names=None):
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
            material = material_names[role] if material_names is not None else model + ('f' if role == 'garment' else '')
            block = re.sub(r'^node trimesh \S+', f'node trimesh {model}p{index}', block)
            block = re.sub(r'(?m)^  (bitmap|materialname) \S+', lambda m:'  '+m[1]+' '+material, block)
            header.append(block)
    header += [f'endmodelgeom {model}', f'donemodel {model}']
    path.write_text('\n'.join(header)+'\n', encoding='ascii')
    return counts


def stage_controls(config):
    """Reject unsupported material operations before reading or writing assets."""
    contract.require(config.get('kind') == 'target-part-stage' and config.get('diagnosticOnly') is True,
                     'Explicit diagnostic stage configuration required')
    common = {'schemaVersion','kind','diagnosticOnly','part','coordinateSpace',
              'targetContract','targetContractSha256','source','sourceSha256',
              'sourceReceipt','sourceReceiptSha256','aoStrength','protectedInputs','label','notes'}
    contract.require(set(config) <= common | {'materialRoles','garmentFaceInputs','skinIntensityInputs','materialExecutionInputs','nativeGeometryInputs','materialSlots','currentMaterialInputs'},
                     'Unsupported stage control; material treatments require an explicit adapter')
    if 'nativeGeometryInputs' in config:
        from native_compiler_input_bridge import controls as native_controls
        native_controls(config['nativeGeometryInputs'])
    if 'materialSlots' in config: validate_material_slots(config['materialSlots'])
    if 'currentMaterialInputs' in config:
        contract.require('nativeGeometryInputs'in config and 'skinIntensityInputs'not in config and 'garmentFaceInputs'not in config and 'materialRoles'not in config and 'materialSlots'not in config,'Current material adapter owns its exact roles and requires native geometry')
        from current_skin_calibration_bridge import controls as current_material_controls
        current_material_controls(config['currentMaterialInputs']);return
    calibration = isinstance(config.get('skinIntensityInputs'),dict) and config['skinIntensityInputs'].get('mode') == 'source-bound-skin-calibration-v1'
    if 'materialExecutionInputs' in config:
        contract.require(calibration, 'Material execution requires source-bound calibration')
        material_execution_controls(config['materialExecutionInputs'], config['skinIntensityInputs'])
    if calibration:
        contract.require('materialRoles' not in config and 'garmentFaceInputs' not in config,
                         'Source-bound calibration owns its exact parent roles; conflicting controls unsupported')
        from replay_stage_skin_calibration import controls
        controls(config['skinIntensityInputs'])
        return
    contract.require(('materialRoles' in config) != ('garmentFaceInputs' in config),
                     'Declare either original material roles or reviewed garment face inputs')
    if 'skinIntensityInputs' in config:
        contract.require('materialRoles' in config and 'garmentFaceInputs' not in config,
                         'Skin intensity requires original materialRoles and cannot combine with garmentFaceInputs')
        if isinstance(config['skinIntensityInputs'],dict) and 'mode' in config['skinIntensityInputs']:
            from source_skin_detail_contract import controls as intensity_controls
        else:
            from replay_stage_skin_intensity import controls as intensity_controls
        intensity_controls(config['skinIntensityInputs'])
    if 'garmentFaceInputs' in config:
        controls = config['garmentFaceInputs']
        contract.require(isinstance(controls,dict) and set(controls) == {'proposal','review'},
                         'Explicit garment proposal/review pins required')
        for key in ('proposal','review'):
            row = controls[key]
            contract.require(isinstance(row,dict) and set(row) == {'path','sha256'},
                             'Exact garment proposal/review path and hash required')


def material_execution_controls(value, calibration):
    contract.require(isinstance(value,dict) and set(value) in ({'proof','recipe','representation'},{'proof','recipe','representation','parentScope'}),
                     'Exact material execution proof/recipe/representation required')
    from replay_stage_skin_calibration import exact_pin
    for row in value.values(): exact_pin(row)
    contract.require(value['recipe']==calibration.get('recipe'), 'Material execution recipe differs from calibration')


def prepare_material_execution_inputs(value, calibration, target_path, target, part, space):
    material_execution_controls(value,calibration)
    from phenotype_material_execution_adoption import prepare_material_execution
    return prepare_material_execution(value['proof'],value['recipe'],value['representation'],
                target_path=target_path,target=target,part=part,space=space,parent_scope_pin=value.get('parentScope'))


def stage(config_path, output):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    stage_controls(config)
    target_path, target = read_target(config)
    additional_pins = {}
    for name, expected in config.get('protectedInputs', {}).items():
        additional_pins[str(pin(name,expected))] = expected
    part = config['part']; space = config['coordinateSpace']
    contract.require(part in contract.BODY_PARTS, 'Generated staging owns declared body parts only')
    contract.require(space in ('working','runtime'), 'Explicit staging coordinate space required')
    source = pin(config['source'], config['sourceSha256'])
    receipt_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    # The optional lighting adapter independently verifies geometry ancestry
    # and explicitly archived historical helpers; legacy source checks stay exact.
    parent = None if 'skinIntensityInputs' in config or 'nativeGeometryInputs' in config else verify_source_receipt(
                         source, receipt_path, target_path, target, part, space)
    doc, binary = read_glb(source)
    # Canonicalize/verify without changing accepted geometry or maps.
    _, _, _, canonical = detached_affine_bake(doc, binary, np.eye(4))
    contract.require(doc['nodes'] == [{'name':'detached_geometry','mesh':0}], 'Canonical identity-node candidate required')
    if 'nativeGeometryInputs' in config:
        parent=json.loads(receipt_path.read_text(encoding='utf-8')); contract.verify_binding(parent,target_path,target,space)
        contract.require(parent['part']==part and parent['candidateSha256']==contract.sha(source),'Native source part/hash differs')
    native_geometry=None
    if 'nativeGeometryInputs'in config:
        from native_compiler_input_bridge import prepare_native_geometry
        _,_,_,source_primitives=raw_corners(doc,binary)
        document_material_ids=[row['material']for row in source_primitives for _ in range(row['triangles'])]
        native_geometry=prepare_native_geometry(config['nativeGeometryInputs'],target_path=target_path,target=target,part=part,source=source,receipt=receipt_path,document_material_ids=document_material_ids,space=space)
    compiler_material_ids=None;material_slots=config.get('materialSlots')
    derived_material_proof = None
    if 'currentMaterialInputs'in config:
        from current_skin_calibration_bridge import staging_inputs as current_material_inputs
        replay=current_material_inputs(config['currentMaterialInputs'],target_path,target,part,space,source,receipt_path,config.get('aoStrength',0),native_geometry=native_geometry)
        doc,binary=replay['document'],replay['binary'];roles={int(k):v for k,v in replay['materialRoles'].items()}
        material_rows,material_proof=replay['materialRows'],replay['originalMaterialProof'];derived_material_proof=replay['proof']
        compiler_material_ids=np.asarray(replay['compilerMaterialIds']);material_slots=replay['materialSlots']
        additional_pins.update(replay['frozenInputs'])
    elif 'garmentFaceInputs' in config:
        # Local import keeps the legacy material decoder usable by the additive
        # ownership helper without a module initialization cycle.
        from target_garment_face_ownership import reviewed_staging_inputs
        controls = config['garmentFaceInputs']
        proposal_path = pin(controls['proposal']['path'],controls['proposal']['sha256'])
        review_path = pin(controls['review']['path'],controls['review']['sha256'])
        reviewed = reviewed_staging_inputs(proposal_path,review_path,target_path,target,
                         part,space,source,receipt_path,config.get('aoStrength',0))
        doc,binary = reviewed['document'],reviewed['binary']
        roles = {int(key):value for key,value in reviewed['materialRoles'].items()}
        material_rows,material_proof = reviewed['materialRows'],reviewed['originalMaterialProof']
        derived_material_proof = reviewed['proof']
        proposed = json.loads(proposal_path.read_text(encoding='utf-8'))
        additional_pins.update({**proposed['frozenInputs'],**proposed['outputHashes']})
        additional_pins.update({str(proposal_path):contract.sha(proposal_path),
                                str(review_path):contract.sha(review_path)})
        for row in derived_material_proof['paletteEdgeEvidence']:
            additional_pins[str(Path(row['path']).resolve())] = row['sha256']
        for name in ('target_garment_face_ownership.py','target_garment_ownership.py',
                     'conservative_face_selection.py'):
            path = Path(__file__).with_name(name).resolve()
            additional_pins[str(path)] = contract.sha(path)
    elif 'skinIntensityInputs' in config:
        calibration = isinstance(config['skinIntensityInputs'],dict) and config['skinIntensityInputs'].get('mode') == 'source-bound-skin-calibration-v1'
        if calibration:
            from replay_stage_skin_calibration import staging_inputs
            roles = None  # The exact recipe, not duplicate stage fields, owns the parent roles.
        elif isinstance(config['skinIntensityInputs'],dict) and 'mode' in config['skinIntensityInputs']:
            from replay_stage_skin_detail import staging_inputs
            roles = {int(key):role for key,role in config['materialRoles'].items()}
        else:
            from replay_stage_skin_intensity import staging_inputs
            roles = {int(key):role for key,role in config['materialRoles'].items()}
        execution = None
        if 'materialExecutionInputs' in config:
            execution = prepare_material_execution_inputs(config['materialExecutionInputs'],
                      config['skinIntensityInputs'],target_path,target,part,space)
        options = {'material_execution':execution} if execution is not None else {}
        replay = staging_inputs(config['skinIntensityInputs'],target_path,target,part,space,
                                source,receipt_path,roles,config.get('aoStrength',0),**options)
        if calibration:
            roles = replay['materialRoles']
        doc,binary = replay['document'],replay['binary']
        material_rows,material_proof = replay['materialRows'],replay['originalMaterialProof']
        parent,derived_material_proof = replay['sourceReceipt'],replay['proof']
        additional_pins.update(replay['frozenInputs'])
    else:
        roles = {int(key):role for key,role in config['materialRoles'].items()}
        atlas_keys={int(k):v['atlasKey']for k,v in config['materialSlots'].items()}if 'materialSlots'in config else None
        material_rows,material_proof = material_inputs(doc,binary,roles,part,
                         config.get('aoStrength',0),contract.fixed_garment_parts(target),atlas_keys=atlas_keys)
    p,n,uv,primitives = raw_corners(doc,binary)
    active_materials = {row['material'] for row in primitives}if compiler_material_ids is None else set(map(int,compiler_material_ids))
    contract.require(set(roles) == active_materials, 'Each active material must have exactly one declared role')
    if contract.rig_mode(target) == 'stock-exact' and part in contract.fixed_garment_parts(target):
        contract.require('garment' in roles.values(), 'Fixed garment required for declared owner: ' + part)
    primitive_roles = [roles[row['material']] for row in primitives for _ in range(row['triangles'])]if compiler_material_ids is None else [roles[int(k)]for k in compiler_material_ids]
    native_uv = uv.copy(); native_uv[:,:,1] = 1-native_uv[:,:,1]
    native_geometry_proof=None
    if native_geometry is not None:
        native_geometry.verify();native_arrays={k:native_geometry.array(k)for k in ('positions','normals','uvNative')}
        try:native_arrays['tangents']=native_geometry.array('tangents')
        except KeyError:pass
        native_geometry_proof=dict(native_geometry.proof)
        p,n,native_uv=native_arrays['positions'],native_arrays['normals'],native_arrays['uvNative']
        if compiler_material_ids is not None:
            from native_compiler_input_bridge import validate_arrays
            validate_arrays(native_arrays,compiler_material_ids)
        additional_pins.update(native_geometry_proof['frozenInputs'])
    material_names=None;atlas_roles=None
    if material_slots is not None:
        slots=validate_material_slots(material_slots);contract.require(set(slots)==active_materials,'Each active material requires an exact typed slot')
        contract.require(all(slots[k]['role']==roles[k]for k in slots),'Typed slot/role disagreement')
        primitive_roles=[slots[row['material']]['atlasKey']for row in primitives for _ in range(row['triangles'])]if compiler_material_ids is None else [slots[int(k)]['atlasKey']for k in compiler_material_ids]
        atlas_roles={v['atlasKey']:v['role']for v in slots.values()};material_names={key:material_resref(contract.model(target,part),key,role)for key,role in atlas_roles.items()}
        contract.require(set(material_rows)==set(atlas_roles),'Every typed atlas must have exact compiler pixel inputs')
    geometry_proof = geometry(p)
    contract.require(not geometry_proof['degenerateTriangles'] and not geometry_proof['coincidentTriangles'],
                     'Coincident/degenerate triangles block staging')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable stage required')
    (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    model = contract.model(target,part)
    counts = write_model(output/'ascii'/(model+'.mdl'),model,p,n,native_uv,primitive_roles,material_names=material_names)
    if native_geometry_proof is not None:
        np.savez_compressed(output/'authoritative-native-compiler-corners.npz',**native_arrays)
        native_geometry_proof['compilerCornerArchive']={'path':str(output/'authoritative-native-compiler-corners.npz'),'sha256':contract.sha(output/'authoritative-native-compiler-corners.npz')}
    resources = output/'resources'
    for atlas_key, pixels in material_rows.items():
        role=atlas_key if atlas_roles is None else atlas_roles[atlas_key]
        material = model + ('f' if role == 'garment' else '')if material_names is None else material_names[atlas_key]
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
               'aoStrength':config.get('aoStrength',0), 'untreatedParentSha256':(derived_material_proof['independentUntreatedParent']['sha256']
                    if 'skinIntensityInputs' in config else contract.sha(source)),
               'nativeGeometrySource':'ascii', 'asciiModel':str(output/'ascii'/(model+'.mdl')),
               'asciiModelSha256':contract.sha(output/'ascii'/(model+'.mdl')),
               'materialResourceHashes':{path.name:contract.sha(path) for path in sorted(resources.iterdir())},
               'rawAttributeAsciiProof':counts,'materialProof':material_proof,
               'materialInputBasis':('replayed-source-bound-skin-calibration-inputs' if derived_material_proof and
                    derived_material_proof.get('kind') == 'replayed-source-bound-skin-calibration-compiler-inputs' else
                    'replayed-original-source-chart-detail-inputs' if derived_material_proof and
                    derived_material_proof.get('kind') == 'replayed-original-source-chart-detail-compiler-inputs' else
                    'replayed-c1-skin-intensity-inputs' if 'skinIntensityInputs' in config else
                    'reviewed-per-face-derived-inputs' if derived_material_proof else 'original-embedded-maps'),
               'derivedMaterialProof':derived_material_proof,
               'canonicalGeometryProof':canonical,'geometry':geometry_proof,
               'frozenInputs':{str(path):contract.sha(path) for path in [config_path,target_path,source,receipt_path,
                    Path(__file__).resolve(),Path(__file__).with_name('target_contract.py'),
                    Path(__file__).with_name('target_part_pipeline.py'),Path(__file__).with_name('stage_stock_part.py'),
                    Path(__file__).with_name('mirror_stock_limb_part.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py')]},
               'diagnosticOnly':True,'rigMode':contract.rig_mode(target),'rigValidated':contract.rig_ready(target), 'rigPilotAccepted':target['rig'].get('pilotAccepted', False),'productionAccepted':False,
               'nativeCompiled':False,'installedShaderVerified':False,'clientAccepted':False,
               'limitation':'Candidate material transport only; joint color continuity, installed shader behavior, native tangents and client appearance require review.'}
    if native_geometry_proof is not None:receipt['nativeCompilerInputProof']=native_geometry_proof;receipt['nativeGeometryInputs']=config['nativeGeometryInputs']
    if material_slots is not None:receipt['materialSlots']=material_slots
    if 'currentMaterialInputs'in config:
        receipt['currentMaterialInputs']=config['currentMaterialInputs'];receipt['materialInputBasis']='replayed-current-recipient-source-bound-skin-calibration-inputs'
        np.savez_compressed(output/'compiler-material-face-ownership.npz',materialIds=compiler_material_ids)
    if 'materialExecutionInputs' in config:
        receipt['materialExecutionInputs'] = config['materialExecutionInputs']
        for row in config['materialExecutionInputs'].values(): additional_pins[row['path']] = row['sha256']
        helper = Path(__file__).with_name('phenotype_material_execution_adoption.py').resolve()
        additional_pins[str(helper)] = contract.sha(helper)
    for name,expected in additional_pins.items(): pin(name,expected)
    receipt['frozenInputs'].update(additional_pins)
    result = output/'target-stage.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); result = stage(args.config,args.output)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
