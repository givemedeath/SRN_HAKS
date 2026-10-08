"""Guard a declared stock Human or retargeted pilot/full client fixture.

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
    if contract.rig_mode(target) == 'stock-exact':
        contract.require(not fixture_appearance_rows, 'Stock-exact fixtures cannot add appearance rows')
        report = {}
        for name in allowed:
            source = pin(baseline_files[name]['path'],baseline_files[name]['sha256'])
            contract.require(name not in payload, 'Stock-exact fixture cannot override installed table: '+name)
            columns,rows = table(source.read_text(encoding='cp1252'))
            if name == 'appearance.2da':
                row = rows[target['identity']['appearanceRow']]
                contract.require(row['MODELTYPE'] == 'P' and row['RACE'].lower() == 'h', 'Installed Human appearance mapping differs')
            elif name == 'racialtypes.2da':
                contract.require(int(rows[target['identity']['raceId']]['Appearance']) == target['identity']['appearanceRow'], 'Installed Human race appearance mapping differs')
            else:
                contract.require(0 in rows, 'Installed normal phenotype missing')
            report[name] = {'unchanged':True,'packed':False,'installedSha256':contract.sha(source)}
        return report
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


def verified_animation_overlay(receipt_pin, target_path, animation_preparation=None):
    contract.require(target_path is not None and isinstance(receipt_pin,dict) and set(receipt_pin) == {'path','sha256'},
                     'Animation overlay requires an exact receipt pin and target contract')
    receipt = json.loads(pin(receipt_pin['path'],receipt_pin['sha256']).read_text(encoding='utf-8-sig'))
    if receipt.get('kind') == 'executed-shared-female-source-native-idle-overlay':
        from shared_female_animation_overlay import verify_shared_female_animation_overlay
        report = verify_shared_female_animation_overlay(receipt_pin,target_path,**({'preparation':animation_preparation} if animation_preparation is not None else {}))
        roots = ('pfa0','pfa2','pfd0','pfd2','pfe0','pfe2','pfg0','pfg2','pfh0','pfh2','pfo0','pfo2')
        expected = {name for root in roots for name in (root+'.mdl','srn_fa_'+root[2:]+'.mdl')}
        contract.require(report.get('kind') == 'verified-shared-female-source-native-animation-overlay',
                         'Explicit verified shared female overlay required')
        contract.require(set(report['resourceHashes']) == set(report['resourcePaths']) == expected,
                         'Shared female animation overlay requires exactly twelve roots and carriers')
    else:
        from target_animation_overlay import verify_animation_overlay
        report = verify_animation_overlay(receipt_pin,target_path)
        contract.require(set(report['resourceHashes']) == set(report['resourcePaths']) == {'pfh0.mdl','srn_fa_h0.mdl'},
                         'Single-Human animation overlay requires exactly the root and carrier')
    for name,path in report['resourcePaths'].items(): pin(path,report['resourceHashes'][name])
    for path,expected in report['frozenInputs'].items(): pin(path,expected)
    return report


def validate_payload(rows, groups, target=None, animation_overlay=None, target_path=None, animation_preparation=None, extra_skin_atlases=None):
    animation_hashes = {}
    if 'animation' in groups or animation_overlay is not None:
        contract.require(target is not None and contract.rig_mode(target) == 'stock-exact' and 'animation' in groups,
                         'Animation overlay is restricted to a declared stock-exact fixture')
        overlay = verified_animation_overlay(animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        animation_hashes = overlay['resourceHashes']
        contract.require(groups['animation'] == animation_hashes, 'Animation payload differs from verified overlay')
    expected = {}; names = set()
    for group,hashes in groups.items():
        for name,expected_hash in hashes.items():
            path = Path(name)
            contract.require(path.name == name and path.suffix in TYPE_BY_EXTENSION and name == name.lower(), 'Invalid declared payload resource')
            contract.require(name not in names, 'Overlapping resource ownership: '+name); names.add(name)
            if target is not None and contract.rig_mode(target) == 'stock-exact':
                from target_body_inventory import expected_body_resources
                allowed_body = expected_body_resources(target,contract.BODY_PARTS,contract.fixed_garment_parts(target),extra_skin_atlases)
                allowed_fixture = {'sr_tm.set','sr_tm_edge.2da'}
                allowed_animation = set(animation_hashes)
                contract.require(group in ('body','fixture','equipment','animation') and name in (allowed_body if group == 'body' else allowed_fixture if group == 'fixture' else allowed_animation if group == 'animation' else set()),
                                 'Stock-exact payload overrides installed rig/head/neck/tables/equipment or another body: '+name)
            else:
                contract.require(not path.stem.startswith(('pmh','pf','a_')), 'Human/female/shared animation override packed: '+name)
            expected[(path.stem,TYPE_BY_EXTENSION[path.suffix])] = expected_hash
    contract.require(len(rows) == len(expected) and packed_index(rows) == expected,'Actual target fixture payload differs from exact declared ownership')
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


def decode_gff(rows, name, extension, gff_tool):
    matches = [data for resref,kind,data in rows if resref == name and kind == TYPE_BY_EXTENSION[extension]]
    contract.require(len(matches) == 1,'Declared native GFF missing/duplicated: '+name+extension)
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary)/('source'+extension); output = Path(temporary)/'area.json'; source.write_bytes(matches[0])
        subprocess.run([str(gff_tool),'-i',str(source),'-o',str(output),'-p'],check=True,capture_output=True)
        data = json.loads(output.read_text(encoding='utf-8'))
    return data


def actor_rows(rows, area, gff_tool):
    return decode_gff(rows,area,'.git',gff_tool)['Creature List']['value']


def validate_actors(actors, target):
    identity = target['identity']; gender = 1 if identity['gender'] == 'female' else 0
    expected = {'Appearance_Type':identity['appearanceRow'],'Race':identity['raceId'],
                'Gender':gender,'Phenotype':identity['phenotype']}
    contract.require(bool(actors) and all(all(row.get(key,{}).get('value') == value for key,value in expected.items())
                     for row in actors), 'Target actors differ from declared race/appearance/gender/phenotype')
    return len(actors)


def module_binding(rows, build, gff_tool):
    name = build.get('moduleName','')
    contract.require(re.fullmatch(r'[a-z0-9_]{1,16}',name), 'Declared safe module name required')
    contract.require(Path(build['module']).stem == name and Path(build['hak']).stem == name, 'Declared module name differs from packages')
    ifo = decode_gff(rows,'module','.ifo',gff_tool)
    hak_names = [entry['Mod_Hak']['value'] for entry in ifo['Mod_HakList']['value']]
    contract.require(hak_names == [name] and ifo['Mod_Entry_Area']['value'] == build['actorAreaResref'], 'Native module HAK/entry-area binding differs')
    return name



def verified_posture_roster(build, target_path, animation=None):
    shared = animation is not None and animation.get('kind') == 'verified-shared-female-source-native-animation-overlay'
    declared = 'postureRoster' in build
    contract.require(not shared or declared, 'Shared female overlay requires its exact typed posture roster')
    if not declared:
        contract.require('postureStockBinding' not in build, 'Stock posture binding requires its declared roster')
        return None
    contract.require('postureStockBinding' in build, 'Shared posture roster requires its installed stock binding')
    from shared_female_posture_fixture import verify_roster
    target = contract.load(target_path)
    contract.require(contract.rig_mode(target) == 'stock-exact' and
        build.get('runtimeBodySource') == 'stock-human-female' and
        build.get('bodyConverted') is None and build.get('bodyNativeReceiptSha256') is None and
        build.get('rigConverted') is None and build.get('provisionalConverted') is None and
        (animation is None or shared), 'Shared posture comparison requires installed female body/rig only')
    contract.require(set(build.get('fixtureResourceHashes',{})) == {'sr_tm.set','sr_tm_edge.2da'},
                     'Shared posture fixture requires exactly its two fixture dependencies')
    roster = verify_roster(build['postureRoster'],target_path)
    contract.require(build.get('moduleName') == roster['document']['moduleName'] and
        build.get('actorAreaResref') == roster['document']['actorAreaResref'], 'Fixture differs from typed posture roster')
    return roster



def verified_posture_stock_basis(build, target_path, roster, client, animation_preparation=None):
    if roster is None:
        contract.require('postureStockBinding' not in build, 'Stock posture binding requires its declared roster')
        return None
    from shared_female_stock_basis import verify_stock_basis
    entry = build.get('postureStockBinding')
    contract.require(isinstance(entry,dict) and set(entry) == {'path','sha256'},
                     'Exact installed stock posture binding required')
    report = verify_stock_basis(entry,target_path,build['postureRoster'],
        game_root=build['gameRoot'],client_path=client,live_source_lookup=True)
    contract.require(report.get('kind') == 'verified-shared-female-installed-stock-basis' and
        report.get('postureStockBinding') == entry and report.get('postureRoster') == build['postureRoster'] and
        report.get('liveSourceLookupExecuted') is True and report.get('clientAccepted') is False and
        report.get('runtimeSelected') is False and report.get('productionAccepted') is False,
        'Executed live stock posture verification required')
    basis = json.loads(pin(entry['path'],entry['sha256']).read_text(encoding='utf-8-sig'))
    contract.require(Path(build['resmanTool']).resolve() == Path(basis['resmanTool']['path']).resolve() and
        build['resmanToolSha256'] == basis['resmanTool']['sha256'],
        'Fixture installed lookup tool differs from verified stock basis')
    declared = 'transitionSourceProof' in build or 'transitionAnimationAuthority' in build
    if declared:
        contract.require('transitionSourceProof' in build and 'transitionAnimationAuthority' in build and
            ('animationOverlay' not in build or build['animationOverlay'] == build['transitionAnimationAuthority']),
            'Complete transition proof/animation authority required')
        from pack_stock_target_fixture import verified_posture_source
        preparation_pin = build['sourcePreparation']
        preparation_path = pin(preparation_pin['path'],preparation_pin['sha256'])
        prepared = json.loads(preparation_path.read_text(encoding='utf-8-sig'))
        contract.verify_binding(prepared,target_path,contract.load(target_path),'runtime')
        child = verified_posture_source(entry,target_path,prepared,preparation_path.parent,
            Path(build['module']),Path(build['gffTool']),Path(build['gameRoot']),
            build['transitionSourceProof'],build['transitionAnimationAuthority'],**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        contract.require(child['moduleResourceHashes'] == build['moduleResourceHashes'] and
            child['sourceProof'] == build.get('postureSourceProof'), 'Packaged transition source differs')
        report['frozenInputs'].update(child['frozenInputs'])
        report['frozenInputs'][str(preparation_path.resolve())] = preparation_pin['sha256']
        report['transitionSourceProof'] = build['transitionSourceProof']
    return report


def audit_posture_identity_tables(roster, table_pins):
    tables = {}
    for name in ('appearance.2da','racialtypes.2da','phenotype.2da'):
        entry = table_pins[name]
        _,tables[name] = table(pin(entry['path'],entry['sha256']).read_text(encoding='cp1252'))
    rows = []
    for actor in roster['document']['actors']:
        appearance = tables['appearance.2da'].get(actor['appearanceId'],{})
        race = tables['racialtypes.2da'].get(actor['raceId'],{})
        phenotype = tables['phenotype.2da'].get(actor['phenotypeId'],{})
        contract.require(appearance.get('MODELTYPE') == 'P' and
            appearance.get('RACE','').lower() == actor['femaleRoot'][2] and
            race.get('Appearance') == str(actor['appearanceId']) and race.get('PlayerRace') == '1' and
            phenotype.get('Label') == ('Normal' if actor['phenotypeId'] == 0 else 'Large'),
            'Posture actor identity differs from installed appearance/race/phenotype tables')
        rows.append({'tag':actor['tag'],'raceId':actor['raceId'],'appearanceId':actor['appearanceId'],
                     'phenotypeId':actor['phenotypeId'],'femaleRoot':actor['femaleRoot']})
    return rows


def stock_dependencies(target, table_pins, build=None, animation_overlay=None, target_path=None, animation_preparation=None):
    overlay = verified_animation_overlay(animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {})) if animation_overlay is not None else None
    if overlay is not None:
        contract.require(build is not None and build.get('animationResourceHashes') == overlay['resourceHashes'],
                         'Stock dependency exception requires the exact verified animation group')
    proof = contract.verify_stock_reference(target)
    frozen = {Path(name).resolve():expected for name,expected in proof['frozenInputs'].items()}
    root = Path(proof['rootAscii']['path']).resolve().parent.parent
    required = {root/'raw'/(name+'.mdl') for name in proof['chain']}
    required |= {root/folder/(target['models'][part]+'.mdl') for part in ('head','neck') for folder in ('raw','ascii')}
    required |= {root/'raw'/name for name in ('appearance.2da','racialtypes.2da','phenotype.2da','pal_skin01.tga','pal_hair01.tga','pal_cloth01.tga',
              'pal_armor01.tga','pal_armor02.tga','pal_leath01.tga','pal_tattoo01.tga')}
    for part in ('head','neck'):
        text = (root/'ascii'/(target['models'][part]+'.mdl')).read_text(encoding='cp1252')
        required |= {root/'raw'/(bitmap.lower()+'.plt') for bitmap in re.findall(r'(?mi)^\s*bitmap\s+(\S+)',text) if bitmap.lower() != 'null'}
    contract.require(required <= set(frozen), 'Installed stock rig/head/neck/palette dependency pins missing')
    for name,entry in table_pins.items():
        installed = root/'raw'/name
        contract.require(installed in frozen and entry['sha256'] == frozen[installed], 'Fixture table basis differs from installed stock reference')
        pin(entry['path'],entry['sha256'])
    if build is not None:
        tool = pin(build['resmanTool'],build['resmanToolSha256'])
        game = Path(build['gameRoot']).resolve(); user = Path(build['userDirectory']).resolve()
        for path in sorted(required):
            if path.parent.name != 'raw': continue
            actual = subprocess.run([str(tool),'--root',str(game),'--userdirectory',str(user),'--no-ovr',path.name],
                                    check=True,capture_output=True).stdout
            contract.require(hashlib.sha256(actual).hexdigest() == frozen[path], 'Installed stock dependency changed since extraction: '+path.name)
    report = {'stockReferenceReceipt':target['rig']['stockReferenceReceipt'],
              'installedDependencyHashes':{str(path):frozen[path] for path in sorted(required)},
              'rigHeadNeckOverridden':False,'stockFramesExact':True}
    if overlay is not None:
        report.update(animationOverlay=animation_overlay,animationResourceHashes=overlay['resourceHashes'],
                      animationParentRootOverridden=True,rootParentOverlayVerified=True,
                      headNeckOverridden=False,stockStaticFramesPreserved=True,
                      installedRootBaselineSha256=frozen[root/'raw'/'pfh0.mdl'])
    return report


def stock_equipment(build, target, target_path):
    entry = build['equipmentSelection']; source = pin(entry['path'],entry['sha256'])
    equipment = json.loads(source.read_text(encoding='utf-8'))
    contract.require(equipment.get('schemaVersion') == 2 and equipment.get('kind') == 'target-equipment-selection', 'Explicit target equipment selection required')
    contract.verify_binding(equipment,target_path,target,'runtime')
    contract.require(equipment.get('mode') == 'stock-identity' and equipment.get('sourcePrefix') == target['identity']['prefix']
                     and equipment.get('runtimeScale') == 1 and equipment.get('resourceHashes') == {}
                     and equipment.get('productionTablesChanged') is False, 'Stock-exact equipment must retain installed identity sizing and tables')
    for name,expected in equipment.get('frozenInputs',{}).items(): pin(name,expected)
    return equipment


def preflight(stage, receipt_sha256, client, target_path, animation_preparation=None):
    stage = Path(stage).resolve(); target_path = Path(target_path).resolve(); target = contract.load(target_path)
    allowed = Path(__file__).resolve().parents[2]/'output/phenotypes'/target['id']
    contract.require(stage.is_relative_to(allowed),'Fixture must be inside its declared target working area')
    receipt = pin(stage/'test-module/receipt.json',receipt_sha256)
    build = json.loads(receipt.read_text(encoding='utf-8'))
    contract.require(build.get('schemaVersion') == 2 and build.get('kind') == 'target-body-fixture','Version 2 declared target fixture required')
    contract.verify_binding(build,target_path,target,'runtime')
    scope = build['validationScope']; contract.require(scope in ('pilot','full'),'Explicit pilot/full client scope required')
    full = scope == 'full'
    stock_exact = contract.rig_mode(target) == 'stock-exact'
    has_overlay = 'animationOverlay' in build or 'animationResourceHashes' in build
    contract.require(not has_overlay or stock_exact and 'animationOverlay' in build and 'animationResourceHashes' in build,
                     'Complete animation overlay declaration requires a stock-exact fixture')
    animation_overlay = build['animationOverlay'] if has_overlay else None
    animation = verified_animation_overlay(animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {})) if has_overlay else None
    if animation is not None:
        contract.require(build['animationResourceHashes'] == animation['resourceHashes'], 'Fixture animation hashes differ from verified receipt')
    posture_roster = verified_posture_roster(build,target_path,animation)
    contract.require(not full or contract.rig_ready(target), 'Full client fixture requires a frozen rig pilot or verified stock reference')
    client = Path(client).resolve(); client_hash = contract.sha(client)
    if animation is not None:
        contract.require(animation['compilerClientSha256'] == client_hash,
                         'Client differs from verified animation carrier compiler')
    if stock_exact:
        contract.require(Path(build['gameRoot']).resolve() == client.parents[2], 'Stock fixture game installation differs from client')
        contract.require(full, 'Stock-exact client fixtures require full scope')
        rig_proof = stock_dependencies(target,build['stockTableBaselines'],build,animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        posture_basis = verified_posture_stock_basis(build,target_path,posture_roster,client,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        contract.require(build.get('rigConverted') is None and build.get('provisionalConverted') is None,
                         'Stock-exact fixture cannot replace installed rig/head/neck')
        source = build.get('runtimeBodySource')
        contract.require(source in ('stock-human-'+target['identity']['gender'], 'target-human-'+target['identity']['gender']), 'Stock-exact fixture body source differs')
        if source.startswith('stock-'):
            contract.require(build.get('bodyConverted') is None and build.get('bodyNativeReceiptSha256') is None,
                             'Matched stock fixture cannot pack candidate body')
            body = {}; parts = set(contract.BODY_PARTS); body_extra = {}
        else:
            body_folder = Path(build['bodyConverted']).resolve()
            pin(body_folder/'native-compile.json',build['bodyNativeReceiptSha256'])
            native,composition,body = verify_native_body(body_folder,target_path,require_complete=True)
            contract.require(native['clientSha256'] == client_hash,'Client differs from native body compiler')
            parts = set(composition['modelParts'].values())
            contract.require(parts == contract.BODY_PARTS, 'Stock-exact candidate requires all fourteen body parts')
            body_extra = composition.get('extraSkinAtlases',{})
        equipment = stock_equipment(build,target,target_path)
        groups = {'body':body}
    else:
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
        groups = {'body':body,'rig':rig,'provisional':provisional}; body_extra = composition.get('extraSkinAtlases',{})
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
    if animation is not None: groups['animation'] = animation['resourceHashes']
    contract.require(not build['configuration']['cameraLock'] and build['configuration']['effectiveNativeBodyMaterials'] is True,
                     'Native material fixture and unlocked camera required')
    userdir = stage/'userdir'; contract.require(Path(build['userDirectory']).resolve() == userdir,'Fixture userdir differs')
    aliases(userdir)
    for kind,folder,suffix in [('hak','hak','.hak'),('module','modules','.mod')]:
        path = pin(build[kind],build[kind+'Sha256'])
        contract.require(path.parent == userdir/folder and path.suffix == suffix,'Fixture package escapes its userdir')
        contract.require({p.name for p in (userdir/folder).iterdir()} == {path.name},'Undeclared client '+folder)
    hak_rows = archive(build['hak']); validate_payload(hak_rows,groups,target,animation_overlay,target_path,extra_skin_atlases=body_extra,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
    compare_archive(hak_rows,stage/'test-module/hak-resources')
    module_rows = archive(build['module']); compare_archive(module_rows,stage/'test-module/module-resources')
    if stock_exact:
        contract.require(flat_hashes(stage/'test-module/module-resources') == build['moduleResourceHashes'], 'Native fixture module resource inventory differs')
    payload = {name+extension:data for name,kind,data in hak_rows
               for extension,resource_type in TYPE_BY_EXTENSION.items() if kind == resource_type}
    table_proof = audit_tables(payload,target,build['stockTableBaselines'],build.get('fixtureAppearanceRows',[]))
    posture_table_rows = audit_posture_identity_tables(posture_roster,build['stockTableBaselines']) if posture_roster is not None else None
    tool = pin(build['gffTool'],build['gffToolSha256'])
    if stock_exact:
        allowed_module = {'module.ifo','sr_tm_floor.are','sr_tm_floor.git','repute.fac','sr_tm_target.utc'}
        allowed_module |= {name+suffix for name in ('sr_tm_spawn','sr_tm_next','sr_tm_enter','sr_tm_damage','sr_tm_death') for suffix in ('.nss','.ncs')}
        actual_module = {(name,kind) for name,kind,_ in module_rows}
        expected_module = {(Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]) for name in allowed_module}
        contract.require(len(module_rows) == len(expected_module) and actual_module == expected_module, 'Stock-exact module cannot hide resource overrides or undeclared scripts')
        declared_name = module_binding(module_rows,build,tool)
    else:
        declared_name = build.get('moduleName',Path(build['module']).stem)
    actors = actor_rows(module_rows,build['actorAreaResref'],tool)
    target_actors = [row for row in actors if row['Appearance_Type']['value'] == target['identity']['appearanceRow']]
    if posture_roster is None:
        validate_actors(target_actors,target)
        if stock_exact:
            contract.require(len(target_actors) == len(actors) == 8, 'Stock-exact matched scene requires eight declared Human actors')
    else:
        from shared_female_posture_fixture import validate_native_actor_rows
        validate_native_actor_rows(posture_roster['document'],actors)
    dressed_actors = None
    if stock_exact:
        contract.require({row['Tag']['value'] for row in actors} == {'tm_'+str(index) for index in range(8)}, 'Stock-exact fixture actor tags must be unique and controllable')
        contract.require(set(build['configuration']['skinIndices']) == {3,8} and all(row['Color_Skin']['value'] in (3,8) for row in actors), 'Stock-exact female skin palettes 3 and 8 required')
        # Dressed dye actors must carry their own head/body-part fields or the client draws nothing.
        if posture_roster is None:
            from target_fixture_dye import validate_dressed_actors
            dressed_actors = validate_dressed_actors(actors)
    report = {'schemaVersion':2,'kind':'target-client-preflight',**contract.binding(target_path,target,'runtime'),
            'pass':True,'validationScope':scope,'fixtureReceiptSha256':contract.sha(receipt),
            'userDirectory':str(userdir),'client':str(client),'clientSha256':client_hash,
            'hakSha256':build['hakSha256'],'moduleSha256':build['moduleSha256'],'moduleName':declared_name,
            'resourceGroups':groups,'tableProof':table_proof,'targetActorCount':len(target_actors),
            'rigPilotAccepted':target['rig'].get('pilotAccepted',False),'rigMode':contract.rig_mode(target),
            'stockProof':rig_proof if stock_exact else None,'overrideEmpty':True,
            'clientLaunched':False,'clientAccepted':False,'executedCodeSha256':contract.sha(__file__),
            'limitation':'Pre-launch identity/provenance/isolation only; all actual client observation gates remain required.'}
    if dressed_actors:
        report['dressedDyeActors'] = dressed_actors
    if animation is not None:
        report.update(animationOverlay=animation_overlay,animationResourceHashes=animation['resourceHashes'])
    if posture_roster is not None:
        report.update(postureRoster=build['postureRoster'],typedPostureActorCount=len(actors),
                      postureRequiredCells=posture_roster['requiredCells'],
                      postureRosterFrozenInputs=posture_roster['frozenInputs'],
                      postureStockBinding=build['postureStockBinding'],postureStockBasis=posture_basis,
                      postureInstalledIdentityRows=posture_table_rows)
    if animation_preparation is not None:
        report['animationPreparation'] = animation_preparation.receipt()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True); parser.add_argument('--receipt-sha256',required=True)
    parser.add_argument('--client',type=Path,required=True); parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); contract.require(not args.output.exists(),'Fresh preflight receipt required')
    build = json.loads(pin(args.fixture/'test-module/receipt.json',args.receipt_sha256).read_text(encoding='utf-8-sig'))
    authority = build.get('transitionAnimationAuthority',build.get('animationOverlay'))
    preparation = None
    if authority is not None:
        selected = json.loads(pin(authority['path'],authority['sha256']).read_text(encoding='utf-8-sig'))
        if selected.get('kind') == 'executed-shared-female-source-native-idle-overlay':
            from animation_verification_preparation import AnimationVerificationPreparation
            preparation = AnimationVerificationPreparation(authority,args.target_contract)
    report = preflight(args.fixture,args.receipt_sha256,args.client,args.target_contract,**({'animation_preparation':preparation} if preparation is not None else {}))
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'validationScope':report['validationScope'],'clientLaunched':False}))
