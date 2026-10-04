"""Compose exact accepted-six runtime bytes and verified new native units.

Compile unions retain their real historical inputs. The explicit effective
inventory carries current AO/roughness materials; comparator/test assets stay out.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess

from stage_stock_part import require, sha, save
from stock_limb_contract import validate_receipt_lineage, PAIRS
from prepare_effective_native_unit import validate_preparation
from effective_body_contract import hashes, validate_effective_body, PRESERVED_PARTS, BODY_PARTS
from audit_pelvis_package import archive
from audit_thigh_package import compare_archive


def compose(config_path,output,tool=None):
    config=json.loads(config_path.read_text()); require(config.get('schemaVersion')==1,'Explicit native body configuration required')
    require(not output.exists(),'Fresh native body composition required')
    frozen={str(config_path.resolve()):sha(config_path)}
    selection_path=Path(config['preservedSelection']); require(sha(selection_path)==config['preservedSelectionSha256'],'Accepted material selection changed')
    selection=json.loads(selection_path.read_text()); preserved_resources=selection_path.parent/'accepted-six-resources'
    prior_hashes=selection['accepted6ResourceHashes']
    require(hashes(preserved_resources)==prior_hashes and len(prior_hashes)==32,'Exact selected-six inventory required')
    frozen[str(selection_path.resolve())]=sha(selection_path)
    for filename,pin in config['preservedGeometry'].items():
        require(sha(Path(filename))==pin,'Accepted source geometry changed')
        frozen[str(Path(filename).resolve())]=pin
    require(len(config['preservedGeometry'])==6,'Six accepted geometry authorities required')
    parent=Path(config['preservedNativeConverted']).resolve(); prior_path=parent/'native-compile.json'
    require(sha(prior_path)==config['preservedNativeReceiptSha256'],'Accepted original native union changed')
    prior=json.loads(prior_path.read_text()); validate_receipt_lineage(prior)
    models=copy.deepcopy(prior['models']); deps=dict(prior['materialResourceHashes'])
    old_models={'pmh0_'+part+'001.mdl' for part in PRESERVED_PARTS}
    require({row['name'] for row in models}==old_models,'Accepted six native model set differs')
    for row in models:
        require(sha(parent/'ascii'/row['name'])==row['sourceSha256'] and prior_hashes[row['name']]==row['binarySha256'],
                'Accepted native/source model association differs')
    origins=[{'path':str(prior_path),'sha256':sha(prior_path),'models':sorted(old_models),
              'materialResourceHashes':prior['materialResourceHashes']}]
    frozen[str(prior_path)]=sha(prior_path);units=[];parts=set(PRESERVED_PARTS)
    for entry in config['units']:
        prep_path=Path(entry['preparation']).resolve(); require(sha(prep_path)==entry['preparationSha256'],'Prepared native unit pin changed')
        converted=prep_path.parent/'human_male_fit/converted'
        unit_config,prep,_=validate_preparation(prep_path,converted,require_native=True)
        part=prep['part']; require(part not in parts,'Duplicate/overlapping body ownership');parts.add(part)
        audit_path=Path(entry['audit']).resolve(); require(sha(audit_path)==entry['auditSha256'],'Actual native attribute audit changed')
        audit=json.loads(audit_path.read_text()); require(audit.get('pass') is True and audit['part']==part
            and audit['nativeCornersExactSourceFloat32']['position'] and audit['nativeCornersExactSourceFloat32']['normal']
            and audit['material']['compileTimeDependenciesExact'] is True,'New part lacks native attribute/material evidence')
        native_path=converted/'native-compile.json'; native=json.loads(native_path.read_text())
        require(native['clientSha256']==prior['clientSha256'] and not set(deps)&set(native['materialResourceHashes']),
                'Compiler differs or material ownership overlaps')
        require(audit['sourceHashes'][str((converted/'resources'/(prep['model']+'.mdl')).resolve())]==native['models'][0]['binarySha256'],
                'Native audit addresses another binary')
        models+=copy.deepcopy(native['models']); deps.update(native['materialResourceHashes'])
        origins.append({'path':str(native_path),'sha256':sha(native_path),'models':[row['name'] for row in native['models']],
            'materialResourceHashes':native['materialResourceHashes']})
        frozen.update({str(prep_path):sha(prep_path),str(audit_path):sha(audit_path),str(native_path):sha(native_path)})
        units.append((converted,unit_config))
    require(parts==set(config['requiredParts']) and parts<=BODY_PARTS,'Required body ownership incomplete/differs')
    for left,right in PAIRS:require((left in parts)==(right in parts),'Native body requires complete selected pairs')
    require(not config.get('requireComplete') or parts==BODY_PARTS,'Complete fourteen-part body required')
    target=output/'human_male_fit/converted';(target/'resources').mkdir(parents=True);(target/'ascii').mkdir()
    for name in prior_hashes:shutil.copyfile(preserved_resources/name,target/'resources'/name)
    for name in old_models:shutil.copyfile(parent/'ascii'/name,target/'ascii'/name)
    conversion=copy.deepcopy(json.loads((parent/'conversion.json').read_text()))
    for converted,_ in units:
        for folder in ('ascii','resources'):
            for path in (converted/folder).iterdir():
                require(not (target/folder/path.name).exists(),'Native body resource collision')
                shutil.copyfile(path,target/folder/path.name)
        conversion['parts']+=copy.deepcopy(json.loads((converted/'conversion.json').read_text())['parts'])
    actual=hashes(target/'resources');conversion['ownedResourceHashes']=actual;conversion['equipmentMode']='stock-identity'
    conversion['geometryStatus']='effective-native-purpose-built-body'; save(target/'conversion.json',conversion)
    combined={'client':prior['client'],'clientSha256':prior['clientSha256'],'complete':True,'models':models,
        'materialResourceHashes':deps,'composition':{'kind':'verified-independent-native-units',
        'sourceReceipts':origins,'acceptedNeighboursRecompiled':False}}
    save(target/'native-compile.json',combined)
    inventory={'schemaVersion':1,'kind':'effective-native-body-inventory','resourceHashes':actual,
        'runtimeMaterialResourceHashes':{n:p for n,p in actual.items() if not n.endswith('.mdl')},
        'nativeReceiptSha256':sha(target/'native-compile.json'),'frozenInputs':frozen,
        'modelParts':{'pmh0_'+part+'001.mdl':part for part in sorted(parts)},
        'acceptedSixBytesExact':all(actual[name]==pin for name,pin in prior_hashes.items()),
        'completeBodySelected':parts==BODY_PARTS,'clientReady':False,
        'compilerDependencyPolicy':'Actual original compile union immutable; current selected runtime bytes declared separately.',
        'clientLaunched':False,'noFixtureOrRigResources':True}
    save(target/'effective-material-inventory.json',inventory);validate_effective_body(target)
    shutil.copyfile(__file__,output/'executed-composer.py')
    if tool:
        hak=output/'human_male_body.hak'
        subprocess.run([str(tool/'nwn_erf.exe'),'-c','-f',str(hak.resolve()),'-e','HAK',str((target/'resources').resolve())],capture_output=True,check=True)
        compare_archive(archive(hak),target/'resources')
        save(output/'body-hak.json',{'hak':str(hak.resolve()),'hakSha256':sha(hak),'resourceHashes':actual,
            'inventorySha256':sha(target/'effective-material-inventory.json'),'actualPayloadVerified':True,'clientReady':False})
    print(json.dumps({'parts':sorted(parts),'resources':len(actual),'completeBodySelected':parts==BODY_PARTS,'acceptedSixBytesExact':inventory['acceptedSixBytesExact']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tool-directory',type=Path)
    a=p.parse_args();compose(a.config,a.output,a.tool_directory)
