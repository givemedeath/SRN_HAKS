"""Declare and compose target body ownership without Human-specific exceptions.

Composition copies reviewed inputs into a fresh stage; it neither compiles nor
accepts them. A separate native receipt must prove the resulting exact bytes.
"""
import argparse
import json
from pathlib import Path
import shutil

import target_contract as contract
import single_plt_part_contract as single_plt
from target_part_pipeline import pin


def skin_atlas_keys(material_slots):
    """Typed additional skin atlases declared by a stage's material slots."""
    if not material_slots: return []
    if single_plt.is_single_plt_slots(material_slots):
        single_plt.validate_slots(material_slots)
        return []  # Every node samples the one model PLT; node slots never own atlases.
    keys = sorted({row['atlasKey'] for row in material_slots.values() if row['role'] == 'skin' and row['atlasKey'] != 'skin'})
    contract.require(all(key[:4] == 'skin' and key[4:].isdigit() and 1 <= int(key[4:]) <= 9 for key in keys),
                     'Bounded typed skin atlas keys required')
    return keys


def expected_body_resources(target, parts, garment_parts, extra_skin_atlases=None):
    """Exact owner resources; extra skin atlases come only from typed stage slots."""
    parts, garment_parts = set(parts), set(garment_parts)
    extra_skin_atlases = {part:list(keys) for part,keys in (extra_skin_atlases or {}).items() if keys}
    contract.require(set(extra_skin_atlases) <= parts, 'Extra skin atlas belongs to an undeclared owner')
    contract.require(parts <= contract.BODY_PARTS and garment_parts <= parts,
                     'Undeclared body/material owner')
    contract.require(garment_parts <= contract.fixed_garment_parts(target),
                     'Fixed garment belongs only to pelvis' if contract.fixed_garment_parts(target) == {'pelvis'} else 'Undeclared fixed garment owner')
    if single_plt.applies(target):
        # Garments live in the part PLT dye layers; per-node garment/overlay resources are superseded.
        contract.require(not extra_skin_atlases, 'Per-node skin atlases are superseded by the single-PLT-per-part contract')
        return single_plt.expected_resources(target,parts)
    names = set()
    for part in parts:
        name = contract.model(target,part)
        names.update(name+suffix for suffix in ('.mdl','.mtr','.plt','n.tga','r.tga'))
        if part in garment_parts:
            names.update(name+suffix for suffix in ('f.mtr','f.tga','fn.tga','fr.tga'))
        if part in extra_skin_atlases:
            from target_part_stage import material_resref
            for key in skin_atlas_keys({str(i):{'role':'skin','atlasKey':k} for i,k in enumerate(extra_skin_atlases[part])}):
                atlas = material_resref(name,key,'skin')
                names.update(atlas+suffix for suffix in ('.mtr','.plt','n.tga','r.tga'))
    return names


def validate_body_ownership(target, model_parts, resource_names, complete, garment_parts=(), diagnostic=False, extra_skin_atlases=None):
    parts = set(model_parts.values())
    contract.require(len(parts) == len(model_parts) and parts <= contract.BODY_PARTS,
                     'Duplicate or undeclared target body part')
    contract.require(model_parts == {contract.model(target,part)+'.mdl':part for part in parts},
                     'Body namespace differs from declared target identity')
    contract.require(complete == (parts == contract.BODY_PARTS), 'Complete body differs from actual ownership')
    if complete:
        contract.require(set(garment_parts) == contract.fixed_garment_parts(target), 'Complete body requires its declared fixed garments')
    if not diagnostic:
        for left,right in contract.PAIRS:
            contract.require((left in parts) == (right in parts), 'Reviewed body requires complete opposite pairs')
    expected = expected_body_resources(target,parts,garment_parts,extra_skin_atlases)
    contract.require(set(resource_names) == expected, 'Missing or undeclared target body/material resource')
    return parts


def single_plt_stage_slots(receipt, ascii_path, resources, has_garment):
    """Check one staged part against the single-PLT contract; returns its node slots."""
    model = Path(ascii_path).stem; slots = receipt.get('materialSlots')
    if not single_plt.is_single_plt_slots(slots):
        contract.require(not has_garment, 'Garment owners require node-keyed single-PLT dye-layer slots')
        slots = None
    proof = single_plt.check_part(model,Path(ascii_path).read_text(encoding='cp1252'),
                                  (Path(resources)/(model+'.mtr')).read_text(encoding='cp1252'),
                                  (Path(resources)/(model+'.plt')).read_bytes(),slots)
    roles = {row['role'] for row in proof['nodes'].values()}
    contract.require(('garment' in roles) == has_garment, 'Single-PLT garment slots differ from declared material roles')
    return {name:{'role':row['role'],'pltLayers':row['declaredLayers']} for name,row in sorted(proof['nodes'].items())}


def verify_single_plt_body(converted, target, record):
    """Every compiled part keeps one model-named PLT/MTR and its declared dye layers."""
    contract.require(record.get('materialLayout') == single_plt.LAYOUT, 'Single-PLT-per-part composition required')
    parts = set(record['modelParts'].values())
    contract.require(record.get('resourceClosure') == single_plt.closure_count(target,parts), 'Derived resource closure differs')
    contract.require(set(record.get('partMaterialSlots',{})) == parts, 'Every owner requires recorded single-PLT node slots')
    proofs = {}
    for name,part in sorted(record['modelParts'].items()):
        model = Path(name).stem
        proofs[part] = single_plt.check_part(model,(converted/'ascii'/name).read_text(encoding='cp1252'),
                                            (converted/'resources'/(model+'.mtr')).read_text(encoding='cp1252'),
                                            (converted/'resources'/(model+'.plt')).read_bytes(),record['partMaterialSlots'][part])
    return proofs


def flat_hashes(path):
    path = Path(path)
    contract.require(path.is_dir() and all(row.is_file() for row in path.iterdir()), 'Flat resource directory required')
    return {row.name:contract.sha(row) for row in sorted(path.iterdir())}


def compose(target_path, receipt_paths, output, space='runtime', require_complete=False):
    target_path = Path(target_path).resolve(); target = contract.load(target_path)
    contract.require(space in ('working','runtime'), 'Explicit composition coordinate space required')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh composition required')
    sources = []; model_parts = {}; resources = {}; garments = []; extra_atlases = {}; part_slots = {}
    for receipt_path in receipt_paths:
        receipt_path = Path(receipt_path).resolve()
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        contract.require(receipt.get('schemaVersion') == 2 and receipt.get('kind') == 'target-part-stage',
                         'Target composition does not reinterpret legacy staging receipts')
        contract.verify_binding(receipt,target_path,target,space)
        part = receipt['part']; model = contract.model(target,part)+'.mdl'
        contract.require(part in contract.BODY_PARTS and model not in model_parts, 'Duplicate or undeclared composition part')
        contract.require(receipt['statureApplications'] == (1 if space == 'runtime' else 0), 'Stature applied incorrectly')
        for name,expected in receipt['frozenInputs'].items(): pin(name,expected)
        ascii_path = pin(receipt['asciiModel'],receipt['asciiModelSha256'])
        contract.require(ascii_path.name == model, 'Staged ASCII filename differs from declared model owner')
        origin = receipt_path.parent/'resources'
        contract.require(flat_hashes(origin) == receipt['materialResourceHashes'], 'Staged material inventory differs')
        has_garment = 'garment' in receipt['materialRoles'].values()
        extra = skin_atlas_keys(receipt.get('materialSlots'))
        if extra: extra_atlases[part] = extra
        expected = expected_body_resources(target,{part},{part} if has_garment else set(),{part:extra})-{model}
        contract.require(set(receipt['materialResourceHashes']) == expected, 'Stage has undeclared/missing material resources')
        if single_plt.applies(target):
            part_slots[part] = single_plt_stage_slots(receipt,ascii_path,origin,has_garment)
        model_parts[model] = part
        if has_garment: garments.append(part)
        for name,expected in receipt['materialResourceHashes'].items():
            contract.require(name not in resources, 'Duplicate material ownership')
            resources[name] = expected
        sources.append({'path':str(receipt_path),'sha256':contract.sha(receipt_path),
                        'part':part,'ascii':ascii_path,'resources':origin})
    complete = set(model_parts.values()) == contract.BODY_PARTS
    contract.require(bool(model_parts), 'At least one declared source part required')
    contract.require(not require_complete or complete, 'Fourteen parts required for complete body composition')
    validate_body_ownership(target,model_parts,set(resources)|set(model_parts),complete,garments,diagnostic=not require_complete,
                            extra_skin_atlases=extra_atlases)
    if require_complete:
        contract.require(contract.rig_ready(target), 'Rig pilot must freeze or stock reference must verify before complete-body selection')
        contract.require(set(garments) == contract.fixed_garment_parts(target), 'Complete body requires its declared fixed garments')
    (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    for row in sources:
        shutil.copyfile(row['ascii'],output/'ascii'/row['ascii'].name)
        for path in row['resources'].iterdir(): shutil.copyfile(path,output/'resources'/path.name)
    source_receipts = [{'path':row['path'],'sha256':row['sha256'],'part':row['part']} for row in sources]
    record = {'schemaVersion':2,'kind':'target-body-composition',**contract.binding(target_path,target,space),
              'modelPrefix':target['identity']['prefix'],'height':target['heightMeters'] if space == 'runtime' else target['workingHeightMeters'],
              'parts':[{'part':part,'model':Path(model).stem} for model,part in sorted(model_parts.items())],
              'modelParts':model_parts,'garmentParts':garments,'extraSkinAtlases':extra_atlases,'completeBodyComposed':complete,
              'composition':{'sourceReceipts':source_receipts},'asciiModelHashes':flat_hashes(output/'ascii'),
              'materialResourceHashes':resources,'diagnosticOnly':True,'nativeCompiled':False,
              **({'materialLayout':single_plt.LAYOUT,'partMaterialSlots':part_slots,
                  'resourceClosure':single_plt.closure_count(target,set(model_parts.values()))} if single_plt.applies(target) else {}),
              'rigMode':contract.rig_mode(target),'rigValidated':contract.rig_ready(target), 'rigPilotAccepted':target['rig'].get('pilotAccepted', False),'productionAccepted':False,'clientAccepted':False,
              'frozenInputs':{str(path):contract.sha(path) for path in [target_path,Path(__file__).resolve(),
                   Path(__file__).with_name('target_contract.py')]+[Path(row['path']) for row in sources]+
                   ([Path(__file__).with_name(name) for name in ('single_plt_part_contract.py','uv_atlas_raster.py','nwn_ascii_trimesh.py')]
                    if single_plt.applies(target) else [])}}
    receipt = output/'conversion.json'; receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    return receipt


def verify_native_body(converted, target_path, require_complete=True):
    """Check exact composition, original dependencies and native compiler bytes."""
    converted = Path(converted).resolve(); target_path = Path(target_path).resolve()
    target = contract.load(target_path)
    record = json.loads((converted/'conversion.json').read_text(encoding='utf-8'))
    contract.require(record.get('schemaVersion') == 2 and record.get('kind') == 'target-body-composition',
                     'Explicit target composition required')
    contract.verify_binding(record,target_path,target,'runtime')
    for name,expected in record['frozenInputs'].items(): pin(name,expected)
    contract.require(not require_complete or record['completeBodyComposed'], 'Complete target body required')
    native = json.loads((converted/'native-compile.json').read_text(encoding='utf-8'))
    contract.require(native.get('complete') is True and native.get('clientSha256'), 'Complete pinned native compilation required')
    models = {row['name']:row for row in native['models']}
    contract.require(len(models) == len(native['models']) and set(models) == set(record['modelParts']),
                     'Native model ownership differs from target composition')
    actual = flat_hashes(converted/'resources')
    validate_body_ownership(target,record['modelParts'],actual,record['completeBodyComposed'],record['garmentParts'],
                            diagnostic=not require_complete,extra_skin_atlases=record.get('extraSkinAtlases',{}))
    contract.require(native['materialResourceHashes'] == record['materialResourceHashes'], 'Native compile-time material dependencies changed')
    contract.require(flat_hashes(converted/'ascii') == record['asciiModelHashes'], 'Composed ASCII bytes changed')
    for name,expected in record['materialResourceHashes'].items():
        contract.require(actual[name] == expected, 'Current material differs from compiled tangent dependency')
    for name,row in models.items():
        binary = converted/'resources'/name
        contract.require(row['sourceSha256'] == record['asciiModelHashes'][name] and actual[name] == row['binarySha256'],
                         'Stale source or native binary: '+name)
        contract.require(binary.read_bytes()[:4] == b'\0\0\0\0' and binary.stat().st_size == row['bytes'], 'Invalid native binary')
    if single_plt.applies(target):
        verify_single_plt_body(converted,target,record)
    return native,record,actual


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--stage-receipt',type=Path,action='append',required=True)
    parser.add_argument('--coordinate-space',choices=('working','runtime'),default='runtime')
    parser.add_argument('--complete',action='store_true'); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); result = compose(args.target_contract,args.stage_receipt,args.output,args.coordinate_space,args.complete)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
