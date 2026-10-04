"""Prepare a fresh native compile unit against an explicit effective material operation.

Leave the original stage and its compiler/material ancestry immutable. This is an
explicit inventory extension for new AO/roughness resources, not an old-guard bypass.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil

from stage_stock_part import require, sha, save
from stock_limb_contract import ATTACHMENTS


def validate_preparation(path, converted, require_native=False):
    path=Path(path).resolve(); converted=Path(converted).resolve(); record=json.loads(path.read_text())
    require(record.get('kind')=='effective-material-native-unit' and record.get('schemaVersion')==1,
            'Explicit effective native preparation required')
    require(path.parent/'human_male_fit/converted'==converted, 'Preparation/unit directory association differs')
    for relative,pin in record['files'].items():
        target=path.parent/relative
        require(target.resolve().is_relative_to(path.parent) and sha(target)==pin, 'Frozen native preparation changed: '+relative)
    stage=Path(record['parentStage'])/'stock-part-stage.json'
    require(sha(stage)==record['parentStageSha256'], 'Original stock stage changed')
    config=json.loads((path.parent/'config.json').read_text())
    require(config==json.loads(stage.read_text())['configuration'], 'Effective unit changes stock stage configuration')
    operation_path=Path(record['effectiveMaterialOperation']); manifest_path=Path(record['runtimeManifest'])
    require(sha(operation_path)==record['effectiveMaterialOperationSha256']
            and sha(manifest_path)==record['runtimeManifestSha256'], 'Effective operation/runtime manifest changed')
    operation=json.loads(operation_path.read_text()); manifest=json.loads(manifest_path.read_text())
    require(operation['effectiveResourceHashes']==manifest['resources'], 'Effective material inventory differs')
    for name,pin in operation['frozenInputs'].items():
        require(sha(Path(name))==pin, 'Effective material ancestor changed: '+name)
    model=record['model']; resources=converted/'resources'
    expected=dict(record['compileMaterialResourceHashes'])
    require(all(manifest['resources'].get(name)==pin and sha(resources/name)==pin for name,pin in expected.items()),
            'Effective compile material resource changed')
    actual={p.name for p in resources.iterdir() if p.is_file()}
    require(actual==set(expected)|({model+'.mdl'} if require_native else set()), 'Undeclared native unit resource')
    if require_native:
        native=json.loads((converted/'native-compile.json').read_text())
        require(native.get('complete') is True and native['materialResourceHashes']==expected
                and len(native['models'])==1 and native['models'][0]['name']==model+'.mdl'
                and native['models'][0]['sourceSha256']==record['sourceAsciiSha256']
                and native['models'][0]['binarySha256']==sha(resources/(model+'.mdl')),
                'Native unit does not match actual frozen source/material compilation')
    return config,record,operation


def prepare(args):
    root=args.stage.resolve(); stage=root/'stock-part-stage.json'
    receipt=json.loads(stage.read_text()); config=receipt['configuration']
    part=config['part']; model='pmh0_'+part+'001'
    require(part in ATTACHMENTS and config['model']==model and config['joint']==ATTACHMENTS[part],
            'Actual stock part/model/joint association required')
    require(config['stockHeightMeters']==1.9339157 and config['equipmentMode']=='stock-identity'
            and config['normalStrength']==1 and config['skinLayer']==0, 'Stock identity/material policy changed')
    for key in ('source','color','normal'):
        require(sha(Path(config[key]))==config['expectedInputHashes'][key], 'Selected source map changed: '+key)
    for row in config['sourceReceiptLineage']:
        require(sha(Path(row['receipt']))==row['receiptSha256'] and sha(Path(row['candidate']))==row['candidateSha256'],
                'Selected source ancestry changed')
    operation_path=args.material_operation.resolve()
    require(sha(operation_path)==args.material_operation_sha256, 'Effective material operation pin changed')
    operation=json.loads(operation_path.read_text())
    require(operation.get('schemaVersion')==1 and operation.get('kind')=='runtime-body-ao-roughness',
            'Unsupported effective material operation')
    for name,pin in operation['frozenInputs'].items():
        require(sha(Path(name))==pin,'Frozen material operation input changed: '+name)
    manifest_path=args.runtime_manifest.resolve()
    require(sha(manifest_path)==args.runtime_manifest_sha256,'Runtime collection manifest pin changed')
    manifest=json.loads(manifest_path.read_text())
    require(manifest['resources']==operation['effectiveResourceHashes'], 'Operation/runtime inventory differs')
    names={model+'.mdl',model+'.mtr',model+'.plt',model+'n.tga',model+'r.tga'}
    relevant={name for name in manifest['resources'] if name.startswith(model)}
    require(relevant==names,'Missing/undeclared isolated skin-only resources')
    paths={name:args.runtime_resources.resolve()/name for name in names}
    require(all(sha(path)==manifest['resources'][name] for name,path in paths.items()), 'Actual effective payload changed')
    origin=root/config['slug']/'converted'
    ascii_path=origin/'ascii'/(model+'.mdl')
    require(sha(ascii_path)==manifest['resources'][model+'.mdl'], 'Effective material operation changed ASCII geometry')
    text=ascii_path.read_text(encoding='ascii')
    require(not re.search(r'(?mi)^\s*newanim\s',text) and re.search(r'(?mi)^setsupermodel\s+'+model+r'\s+NULL\s*$',text),
            'Isolated part contains animation/supermodel changes')
    require(not args.output.exists(),'Fresh native preparation output required')
    converted=args.output/config['slug']/'converted'
    (converted/'ascii').mkdir(parents=True); (converted/'resources').mkdir()
    shutil.copyfile(ascii_path,converted/'ascii'/(model+'.mdl'))
    for name,path in paths.items():
        if name.endswith('.mdl'): continue
        shutil.copyfile(path,converted/'resources'/name)
    conversion=copy.deepcopy(json.loads((origin/'conversion.json').read_text()))
    conversion['ownedResourceHashes']={name:manifest['resources'][name] for name in names if not name.endswith('.mdl')}
    save(converted/'conversion.json',conversion)
    save(args.output/'config.json',config)
    shutil.copyfile(stage,args.output/'parent-stock-part-stage.json')
    shutil.copyfile(operation_path,args.output/'effective-material-operation.json')
    shutil.copyfile(__file__,args.output/'executed-preparer.py')
    result={'schemaVersion':1,'kind':'effective-material-native-unit','part':part,'model':model,
        'parentStage':str(root),'parentStageSha256':sha(stage),
        'runtimeManifest':str(manifest_path),'runtimeManifestSha256':sha(manifest_path),
        'effectiveMaterialOperation':str(operation_path),'effectiveMaterialOperationSha256':sha(operation_path),
        'sourceAsciiSha256':sha(ascii_path),'compileMaterialResourceHashes':conversion['ownedResourceHashes'],
        'stockIdentityPreserved':True,'originalStageModified':False,'nativeCompiled':False,
        'files':{str(path.relative_to(args.output)):sha(path) for path in args.output.rglob('*') if path.is_file()}}
    save(args.output/'native-unit-preparation.json',result)
    print(json.dumps({'part':part,'converted':str(converted.resolve()),'materialDependencies':len(conversion['ownedResourceHashes'])}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--runtime-resources',type=Path,required=True)
    p.add_argument('--runtime-manifest',type=Path,required=True)
    p.add_argument('--runtime-manifest-sha256',required=True)
    p.add_argument('--material-operation',type=Path,required=True)
    p.add_argument('--material-operation-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    prepare(p.parse_args())


if __name__=='__main__':main()
