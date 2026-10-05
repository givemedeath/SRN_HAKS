"""Guard a declared Troll pilot/full fixture before authorized client control.

This checks package provenance and resource isolation. It does not launch the
client or substitute for actual motion, palette, gameplay or performance review.
"""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import target_contract as contract
from audit_pelvis_package import archive
from audit_thigh_package import TYPE_BY_EXTENSION, compare_archive, packed_index
from target_body_inventory import flat_hashes, verify_native_body
from target_part_pipeline import pin


def table(text):
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('//')]
    contract.require(lines[0] == '2DA V2.0', 'Supported 2DA V2.0 table required')
    offset = 2 if lines[1].upper().startswith('DEFAULT:') else 1
    columns = re.findall(r'"[^"]*"|\S+',lines[offset]); rows = {}
    for line in lines[offset+1:]:
        values = re.findall(r'"[^"]*"|\S+',line)
        contract.require(values[0].isdigit() and len(values)-1 == len(columns), 'Invalid explicit 2DA row')
        index = int(values[0]); contract.require(index not in rows,'Duplicate 2DA row')
        rows[index] = dict(zip(columns,values[1:]))
    return columns,rows


def audit_tables(payload, target, baseline_files, fixture_appearance_rows=()):
    allowed = {
        'appearance.2da': {'LABEL','STRING_REF','NAME','RACE','MOVERATE','WALKDIST','RUNDIST',
             'PERSPACE','CREPERSPACE','HEIGHT','HITDIST','PREFATCKDIST','TARGETHEIGHT',
             'WEAPONSCALE','WING_TAIL_SCALE','HELMET_SCALE_M','SIZECATEGORY'},
        'racialtypes.2da': {'Label','Abrev','Name','ConverName','ConverNameLower','NamePlural',
             'Description','Icon','Appearance'},
        'phenotype.2da': set()}
    contract.require(set(baseline_files) == set(allowed), 'Exact installed table baseline pins required')
    report = {}
    for name, permitted in allowed.items():
        source = pin(baseline_files[name]['path'],baseline_files[name]['sha256'])
        contract.require(name in payload,'Required target table missing: '+name)
        if name == 'phenotype.2da':
            contract.require(payload[name] == source.read_bytes(), 'Phenotype table must preserve normal phenotype zero')
            report[name] = {'unchanged':True}; continue
        old_columns,old = table(source.read_text(encoding='cp1252'))
        new_columns,new = table(payload[name].decode('cp1252'))
        contract.require(old_columns == new_columns and set(old) <= set(new), 'Table columns or installed rows changed')
        additions = set(new)-set(old)
        contract.require(additions <= (set(fixture_appearance_rows) if name == 'appearance.2da' else set()),
                         'Undeclared fixture table rows')
        target_row = target['identity']['appearanceRow'] if name == 'appearance.2da' else target['identity']['raceId']
        changed = []
        for index in old:
            differences = {key for key in old_columns if old[index][key] != new[index][key]}
            contract.require(not differences or index == target_row and differences <= permitted,
                             'Gameplay, Human, female or unrelated table fields changed: '+name+' row '+str(index))
            changed.extend(sorted(differences))
        if name == 'appearance.2da':
            row = new[target_row]
            contract.require(row['MODELTYPE'] == 'P' and row['RACE'].lower() == target['identity']['prefix'][2]
                             and row['SIZECATEGORY'] == '4', 'Target appearance must resolve the declared Large model family')
        else:
            contract.require(int(new[target_row]['Appearance']) == target['identity']['appearanceRow'], 'Race appearance mapping differs')
        report[name] = {'changedColumns':changed,'fixtureAddedRows':sorted(additions),'otherInstalledRowsExact':True}
    return report


def native_group(folder, receipt_sha256, client_hash, expected_models):
    folder = Path(folder).resolve(); receipt = pin(folder/'native-compile.json',receipt_sha256)
    native = json.loads(receipt.read_text(encoding='utf-8'))
    contract.require(native.get('complete') is True and native.get('clientSha256') == client_hash,
                     'Native group compiler differs or is incomplete')
    models = {row['name']:row for row in native['models']}
    contract.require(len(models) == len(native['models']) and set(models) == set(expected_models), 'Declared native group model inventory differs')
    actual = flat_hashes(folder/'resources'); ascii_hashes = flat_hashes(folder/'ascii')
    contract.require(set(ascii_hashes) == set(models) and set(actual) == set(models)|set(native['materialResourceHashes']),
                     'Missing/undeclared native group resource')
    for name,expected in native['materialResourceHashes'].items():
        contract.require(actual[name] == expected,'Native group shading dependency changed')
    for name,row in models.items():
        binary = folder/'resources'/name
        contract.require(ascii_hashes[name] == row['sourceSha256'] and actual[name] == row['binarySha256'], 'Stale native group source/binary')
        contract.require(binary.read_bytes()[:4] == b'\0\0\0\0' and binary.stat().st_size == row['bytes'], 'Invalid native group binary')
    return actual


def validate_payload(rows, groups):
    expected = {}; names = set()
    for group,hashes in groups.items():
        for name,expected_hash in hashes.items():
            path = Path(name)
            contract.require(path.name == name and path.suffix in TYPE_BY_EXTENSION and name == name.lower(), 'Invalid declared payload resource')
            contract.require(name not in names, 'Overlapping resource ownership: '+name); names.add(name)
            contract.require(not path.stem.startswith(('pmh','pf','a_')), 'Human/female/shared animation override packed: '+name)
            expected[(path.stem,TYPE_BY_EXTENSION[path.suffix])] = expected_hash
    contract.require(packed_index(rows) == expected,'Actual target fixture payload differs from exact declared ownership')
    return names


def aliases(userdir):
    config = configparser.ConfigParser(interpolation=None); config.read(userdir/'nwn.ini')
    required = {'HD0':'','HAK':'hak','MODULES':'modules','OVERRIDE':'override','LOGS':'logs',
                'CURRENTGAME':'currentgame','MODELCOMPILER':'modelcompiler'}
    contract.require(config.has_section('Alias'),'Client resource aliases missing')
    for key,relative in required.items():
        value = config.get('Alias',key,fallback='')
        contract.require(value and Path(value).resolve() == userdir/relative, 'Client alias escapes isolated userdir: '+key)
    contract.require((userdir/'override').is_dir() and not any((userdir/'override').iterdir()),'Client override must be empty')


def actor_rows(rows, area, gff_tool):
    matches = [data for name,kind,data in rows if name == area and kind == TYPE_BY_EXTENSION['.git']]
    contract.require(len(matches) == 1,'Declared actor-area GIT missing/duplicated')
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary)/'area.git'; output = Path(temporary)/'area.json'; source.write_bytes(matches[0])
        subprocess.run([str(gff_tool),'-i',str(source),'-o',str(output),'-p'],check=True,capture_output=True)
        data = json.loads(output.read_text(encoding='utf-8'))
    return data['Creature List']['value']


def preflight(stage, receipt_sha256, client, target_path):
    stage = Path(stage).resolve(); target_path = Path(target_path).resolve(); target = contract.load(target_path)
    allowed = Path(__file__).resolve().parents[2]/'output/phenotypes'/target['id']
    contract.require(stage.is_relative_to(allowed),'Fixture must be inside its declared target working area')
    receipt = pin(stage/'test-module/receipt.json',receipt_sha256)
    build = json.loads(receipt.read_text(encoding='utf-8'))
    contract.require(build.get('schemaVersion') == 2 and build.get('kind') == 'target-body-fixture','Version 2 declared target fixture required')
    contract.verify_binding(build,target_path,target,'runtime')
    scope = build['validationScope']; contract.require(scope in ('pilot','full'),'Explicit pilot/full client scope required')
    full = scope == 'full'
    contract.require(not full or target['rig']['pilotAccepted'], 'Full client fixture requires the frozen rig pilot')
    client = Path(client).resolve(); client_hash = contract.sha(client)
    body_folder = Path(build['bodyConverted']).resolve()
    pin(body_folder/'native-compile.json',build['bodyNativeReceiptSha256'])
    native,composition,body = verify_native_body(body_folder,target_path,require_complete=full)
    contract.require(native['clientSha256'] == client_hash,'Client differs from native body compiler')
    parts = set(composition['modelParts'].values())
    contract.require(full or {'chest','bicepl','bicepr'} <= parts,'Pilot fixture needs torso and both upper arms')
    rig_models = {name+'.mdl' for name in target['rig']['privateAliases'].values()}
    rig = native_group(build['rigConverted'],build['rigNativeReceiptSha256'],client_hash,rig_models)
    provisional_models = {target['models'][part]+'.mdl' for part in ('head','neck')}
    provisional = native_group(build['provisionalConverted'],build['provisionalNativeReceiptSha256'],client_hash,provisional_models)
    contract.require(all(Path(name).stem.startswith(tuple(target['models'][part] for part in ('head','neck'))) for name in provisional),
                     'Provisional head/neck group owns unrelated material resources')
    groups = {'body':body,'rig':rig,'provisional':provisional}
    if not full:
        remaining = {target['models'][part]+'.mdl' for part in contract.BODY_PARTS-parts}
        groups['diagnostic-stock'] = native_group(build['stockConverted'],build['stockNativeReceiptSha256'],client_hash,remaining)
    equipment_path = pin(build['equipmentSelection']['path'],build['equipmentSelection']['sha256'])
    equipment = json.loads(equipment_path.read_text(encoding='utf-8'))
    contract.require(equipment.get('schemaVersion') == 2 and equipment.get('kind') == 'target-equipment-selection','Explicit target equipment selection required')
    contract.verify_binding(equipment,target_path,target,'runtime')
    contract.require(not full or equipment.get('complete') is True and equipment.get('profilesAccepted') is True
                     and equipment.get('collisionReviewsAccepted') is True and not equipment.get('failures'),
                     'Missing, collided or partially converted equipment blocks full fixture acceptance')
    groups['equipment'] = equipment['resourceHashes']; groups['fixture'] = build['fixtureResourceHashes']
    contract.require(not build['configuration']['cameraLock'] and build['configuration']['effectiveNativeBodyMaterials'] is True,
                     'Native material fixture and unlocked camera required')
    userdir = stage/'userdir'; contract.require(Path(build['userDirectory']).resolve() == userdir,'Fixture userdir differs')
    aliases(userdir)
    for kind,folder,suffix in [('hak','hak','.hak'),('module','modules','.mod')]:
        path = pin(build[kind],build[kind+'Sha256'])
        contract.require(path.parent == userdir/folder and path.suffix == suffix,'Fixture package escapes its userdir')
        contract.require({p.name for p in (userdir/folder).iterdir()} == {path.name},'Undeclared client '+folder)
    hak_rows = archive(build['hak']); validate_payload(hak_rows,groups)
    compare_archive(hak_rows,stage/'test-module/hak-resources')
    module_rows = archive(build['module']); compare_archive(module_rows,stage/'test-module/module-resources')
    payload = {name+extension:data for name,kind,data in hak_rows
               for extension,resource_type in TYPE_BY_EXTENSION.items() if kind == resource_type}
    table_proof = audit_tables(payload,target,build['stockTableBaselines'],build.get('fixtureAppearanceRows',[]))
    tool = pin(build['gffTool'],build['gffToolSha256']); actors = actor_rows(module_rows,build['actorAreaResref'],tool)
    target_actors = [row for row in actors if row['Appearance_Type']['value'] == target['identity']['appearanceRow']]
    contract.require(bool(target_actors) and all(row['Gender']['value'] == 0 and row['Phenotype']['value'] == 0
                     for row in target_actors),'Target actors must use supported male normal phenotype')
    return {'schemaVersion':2,'kind':'target-client-preflight',**contract.binding(target_path,target,'runtime'),
            'pass':True,'validationScope':scope,'fixtureReceiptSha256':contract.sha(receipt),
            'userDirectory':str(userdir),'client':str(client),'clientSha256':client_hash,
            'hakSha256':build['hakSha256'],'moduleSha256':build['moduleSha256'],
            'resourceGroups':groups,'tableProof':table_proof,'targetActorCount':len(target_actors),
            'rigPilotAccepted':target['rig']['pilotAccepted'],'overrideEmpty':True,
            'clientLaunched':False,'clientAccepted':False,'executedCodeSha256':contract.sha(__file__),
            'limitation':'Pre-launch identity/provenance/isolation only; all actual client observation gates remain required.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True); parser.add_argument('--receipt-sha256',required=True)
    parser.add_argument('--client',type=Path,required=True); parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); contract.require(not args.output.exists(),'Fresh preflight receipt required')
    report = preflight(args.fixture,args.receipt_sha256,args.client,args.target_contract)
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'validationScope':report['validationScope'],'clientLaunched':False}))
