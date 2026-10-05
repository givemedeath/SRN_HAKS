"""Declare and compose target body ownership without Human-specific exceptions.

Composition copies reviewed inputs into a fresh stage; it neither compiles nor
accepts them. A separate native receipt must prove the resulting exact bytes.
"""
import argparse
import json
from pathlib import Path
import shutil

import target_contract as contract
from target_part_pipeline import pin


def expected_body_resources(target, parts, garment_parts):
    parts, garment_parts = set(parts), set(garment_parts)
    contract.require(parts <= contract.BODY_PARTS and garment_parts <= parts,
                     'Undeclared body/material owner')
    contract.require(garment_parts <= {'pelvis'}, 'Fixed garment belongs only to pelvis')
    names = set()
    for part in parts:
        name = contract.model(target,part)
        names.update(name+suffix for suffix in ('.mdl','.mtr','.plt','n.tga','r.tga'))
        if part in garment_parts:
            names.update(name+suffix for suffix in ('f.mtr','f.tga','fn.tga','fr.tga'))
    return names


def validate_body_ownership(target, model_parts, resource_names, complete, garment_parts=(), diagnostic=False):
    parts = set(model_parts.values())
    contract.require(len(parts) == len(model_parts) and parts <= contract.BODY_PARTS,
                     'Duplicate or undeclared target body part')
    contract.require(model_parts == {contract.model(target,part)+'.mdl':part for part in parts},
                     'Body namespace differs from declared target identity')
    contract.require(complete == (parts == contract.BODY_PARTS), 'Complete body differs from actual ownership')
    if complete:
        contract.require(set(garment_parts) == {'pelvis'}, 'Complete body requires its pelvis-only fixed garment')
    if not diagnostic:
        for left,right in contract.PAIRS:
            contract.require((left in parts) == (right in parts), 'Reviewed body requires complete opposite pairs')
    expected = expected_body_resources(target,parts,garment_parts)
    contract.require(set(resource_names) == expected, 'Missing or undeclared target body/material resource')
    return parts


def flat_hashes(path):
    path = Path(path)
    contract.require(path.is_dir() and all(row.is_file() for row in path.iterdir()), 'Flat resource directory required')
    return {row.name:contract.sha(row) for row in sorted(path.iterdir())}


def compose(target_path, receipt_paths, output, space='runtime', require_complete=False):
    target_path = Path(target_path).resolve(); target = contract.load(target_path)
    contract.require(space in ('working','runtime'), 'Explicit composition coordinate space required')
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh composition required')
    sources = []; model_parts = {}; resources = {}; garments = []
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
        expected = expected_body_resources(target,{part},{part} if has_garment else set())-{model}
        contract.require(set(receipt['materialResourceHashes']) == expected, 'Stage has undeclared/missing material resources')
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
    validate_body_ownership(target,model_parts,set(resources)|set(model_parts),complete,garments,diagnostic=not require_complete)
    if require_complete:
        contract.require(target['rig']['pilotAccepted'] is True, 'Rig pilot must freeze before complete-body selection')
        contract.require(set(garments) == {'pelvis'}, 'Complete body requires its pelvis-only fixed garment')
    (output/'ascii').mkdir(parents=True); (output/'resources').mkdir()
    for row in sources:
        shutil.copyfile(row['ascii'],output/'ascii'/row['ascii'].name)
        for path in row['resources'].iterdir(): shutil.copyfile(path,output/'resources'/path.name)
    source_receipts = [{'path':row['path'],'sha256':row['sha256'],'part':row['part']} for row in sources]
    record = {'schemaVersion':2,'kind':'target-body-composition',**contract.binding(target_path,target,space),
              'modelPrefix':target['identity']['prefix'],'height':target['heightMeters'] if space == 'runtime' else target['workingHeightMeters'],
              'parts':[{'part':part,'model':Path(model).stem} for model,part in sorted(model_parts.items())],
              'modelParts':model_parts,'garmentParts':garments,'completeBodyComposed':complete,
              'composition':{'sourceReceipts':source_receipts},'asciiModelHashes':flat_hashes(output/'ascii'),
              'materialResourceHashes':resources,'diagnosticOnly':True,'nativeCompiled':False,
              'rigPilotAccepted':target['rig']['pilotAccepted'],'productionAccepted':False,'clientAccepted':False,
              'frozenInputs':{str(path):contract.sha(path) for path in [target_path,Path(__file__).resolve(),
                   Path(__file__).with_name('target_contract.py')]+[Path(row['path']) for row in sources]}}
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
                            diagnostic=not require_complete)
    contract.require(native['materialResourceHashes'] == record['materialResourceHashes'], 'Native compile-time material dependencies changed')
    contract.require(flat_hashes(converted/'ascii') == record['asciiModelHashes'], 'Composed ASCII bytes changed')
    for name,expected in record['materialResourceHashes'].items():
        contract.require(actual[name] == expected, 'Current material differs from compiled tangent dependency')
    for name,row in models.items():
        binary = converted/'resources'/name
        contract.require(row['sourceSha256'] == record['asciiModelHashes'][name] and actual[name] == row['binarySha256'],
                         'Stale source or native binary: '+name)
        contract.require(binary.read_bytes()[:4] == b'\0\0\0\0' and binary.stat().st_size == row['bytes'], 'Invalid native binary')
    return native,record,actual


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--stage-receipt',type=Path,action='append',required=True)
    parser.add_argument('--coordinate-space',choices=('working','runtime'),default='runtime')
    parser.add_argument('--complete',action='store_true'); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); result = compose(args.target_contract,args.stage_receipt,args.output,args.coordinate_space,args.complete)
    print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
