"""Pack a stock-exact Human fixture without replacing its installed rig/equipment.

Body candidates require the complete fourteen-part native composition. Shared
posture comparisons keep the installed body and verify an explicit native actor
roster. Neither packing nor preflight accepts visuals.
"""
import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess

import target_contract as contract
from audit_pelvis_package import archive
from audit_thigh_package import compare_archive
from target_body_inventory import flat_hashes, verify_native_body
from target_part_pipeline import pin
from target_fixture import save, user_layout, module_name


def verified_animation_overlay(receipt_pin, target_path, animation_preparation=None):
    """Only an explicit executed-overlay verifier can grant model ownership."""
    contract.require(isinstance(receipt_pin,dict) and set(receipt_pin) == {'path','sha256'},
                     'Animation overlay requires an exact receipt path/hash pin')
    receipt_path = pin(receipt_pin['path'],receipt_pin['sha256'])
    kind = json.loads(receipt_path.read_text(encoding='utf-8-sig')).get('kind')
    if kind == 'executed-shared-female-source-native-idle-overlay':
        from shared_female_animation_overlay import verify_shared_female_animation_overlay
        report = verify_shared_female_animation_overlay(receipt_pin,target_path,**({'preparation':animation_preparation} if animation_preparation is not None else {}))
        required = {name for family in 'adegho' for phenotype in (0,2)
                    for name in (f'pf{family}{phenotype}.mdl',f'srn_fa_{family}{phenotype}.mdl')}
        contract.require(report.get('kind') == 'verified-shared-female-source-native-animation-overlay',
                         'Explicit verified shared-female overlay required')
        message = 'Shared-female animation overlay requires exactly the 24 roots and carriers'
    else:
        # Keep the existing single-Human verifier and its two-resource authority.
        from target_animation_overlay import verify_animation_overlay
        report = verify_animation_overlay(receipt_pin,target_path)
        required = {'pfh0.mdl','srn_fa_h0.mdl'}
        message = 'Single-Human animation overlay requires exactly the root and carrier'
    contract.require(set(report['resourceHashes']) == set(report['resourcePaths']) == required,message)
    for name,path in report['resourcePaths'].items(): pin(path,report['resourceHashes'][name])
    for path,expected in report['frozenInputs'].items(): pin(path,expected)
    return report


def verified_posture_roster(receipt_pin, target_path, prepared, module, gff_tool):
    """Bind the reviewed roster to the actually decoded archived native actors."""
    contract.require(isinstance(receipt_pin,dict) and set(receipt_pin) == {'path','sha256'},
                     'Posture roster requires an exact receipt path/hash pin')
    pin(receipt_pin['path'],receipt_pin['sha256'])
    contract.require(prepared.get('postureRoster') == receipt_pin,
                     'Prepared source must bind the exact posture roster')
    from shared_female_posture_fixture import verify_roster, validate_native_actor_rows
    from preflight_target_body_client import actor_rows
    report = verify_roster(receipt_pin,target_path)
    document = report['document']
    contract.require(report.get('roster') == receipt_pin and
                     document['moduleName'] == prepared['moduleName'] and
                     document['actorAreaResref'] == prepared['actorAreaResref'] and
                     document['bodySource'] == 'installed-stock-shared-female',
                     'Posture roster module/area/body source differs')
    contract.require(set(prepared['fixtureResourceHashes']) == {'sr_tm.set','sr_tm_edge.2da'},
                     'Shared posture fixture requires exactly the two stock fixture dependencies')
    for path,expected in report['frozenInputs'].items(): pin(path,expected)
    pin(module,prepared['moduleSha256'])
    validate_native_actor_rows(document,actor_rows(archive(module),prepared['actorAreaResref'],gff_tool))
    return report


def verified_posture_stock_basis(receipt_pin, target_path, prepared, source, module, gff_tool, game_root):
    """Verify installed binding plus actual bounded native source descendants."""
    contract.require(isinstance(receipt_pin,dict) and set(receipt_pin) == {'path','sha256'},
                     'Posture stock binding requires an exact receipt path/hash pin')
    binding_path = pin(receipt_pin['path'],receipt_pin['sha256'])
    contract.require(prepared.get('postureStockBinding') == receipt_pin and prepared.get('postureRoster') is not None,
                     'Prepared source must bind the exact posture stock binding and roster')
    from shared_female_stock_basis import verify_stock_basis
    from shared_tools import sha as streamed_sha
    from preflight_target_body_client import decode_gff
    target = contract.load(target_path)
    report = verify_stock_basis(receipt_pin,target_path,prepared['postureRoster'],
                                game_root=game_root,live_source_lookup=False)
    contract.require(report.get('kind') == 'verified-shared-female-installed-stock-basis' and
        report.get('postureStockBinding') == receipt_pin and report.get('postureRoster') == prepared['postureRoster'] and
        report.get('liveSourceLookupExecuted') is False, 'Explicit read-only stock binding verification required')
    frozen = dict(report['frozenInputs'])
    def add(entry):
        contract.require(isinstance(entry,dict) and set(entry) == {'path','sha256'}, 'Exact native source proof pin required')
        path = pin(entry['path'],entry['sha256'])
        key = str(path.resolve())
        contract.require(key not in frozen or frozen[key] == entry['sha256'], 'Conflicting native source proof input')
        frozen[key] = entry['sha256']
        return path
    def read(entry):
        return json.loads(add(entry).read_text(encoding='utf-8-sig'))
    add({'path':str(Path(__file__).resolve()),'sha256':contract.sha(__file__)})
    add({'path':str(Path(gff_tool).resolve()),'sha256':contract.sha(gff_tool)})
    basis = json.loads(binding_path.read_text(encoding='utf-8-sig'))
    recipe = read(basis['rosterRecipe'])
    proof_pin = prepared.get('sourceProof')
    proof = read(proof_pin)
    contract.verify_binding(proof,target_path,target,'runtime')
    contract.require(proof.get('schemaVersion') == 1 and type(proof.get('schemaVersion')) is int and
        proof.get('kind') == 'shared-female-stockbody-roster-native-source-proof' and
        proof.get('postureRoster') == prepared['postureRoster'] and
        proof.get('postureStockBinding') == receipt_pin and
        prepared.get('parentSourcePreparation') == proof.get('parentSourcePreparation') == recipe['sourcePreparation'] and
        prepared.get('parentSourceProof') == proof.get('parentSourceProof') == recipe['sourceProof'],
        'Prepared native source proof/binding/parent lineage differs')
    contract.require(all(proof.get(k) is False for k in
        ('HAKBuilt','clientLaunched','clientAccepted','runtimeSelected','productionAccepted')) and
        all(type(proof.get(k)) is int and proof[k] == value for k,value in
        (('scriptCompileCalls',0),('modelCompileCalls',0),('nativeGITEncodeCalls',1),('nativeMODPackCalls',1))),
        'Native source proof requires pending acceptance and exact operation counts')
    parent = read(proof['parentSourcePreparation'])
    parent_proof = read(proof['parentSourceProof'])
    contract.verify_binding(parent,target_path,target,'runtime')
    contract.require(parent.get('sourceProof') == proof['parentSourceProof'] and
        proof['parentNativeModule'] == {'path':parent['module'],'sha256':parent['moduleSha256']},
        'Original native source module/proof lineage differs')
    parent_module = add(proof['parentNativeModule'])
    parent_source = Path(proof['parentSourcePreparation']['path']).resolve().parent
    native_module = add(proof['nativeModule'])
    contract.require(native_module == Path(prepared['module']).resolve() and
        proof['nativeModule']['sha256'] == prepared['moduleSha256'] and
        contract.sha(module) == prepared['moduleSha256'], 'Native proof differs from current/copied module')
    parent_git = add(proof['parentNativeGIT'])
    native_git = add(proof['actualNativeGIT'])
    contract.require(parent_git == parent_source/'module-resources/sr_tm_floor.git' and
        native_git == Path(source).resolve()/'module-resources/sr_tm_floor.git' and
        proof['actualNativeGIT']['sha256'] == prepared['moduleResourceHashes']['sr_tm_floor.git'] and
        parent_proof.get('actualNativeGIT') == proof['parentNativeGIT'],
        'Native GIT source lineage differs')
    expected_protected = {n:h for n,h in prepared['moduleResourceHashes'].items() if n != 'sr_tm_floor.git'}
    contract.require(len(expected_protected) == 14 and proof.get('protected14ModuleResourceHashes') == expected_protected and
        expected_protected == {n:h for n,h in parent['moduleResourceHashes'].items() if n != 'sr_tm_floor.git'} and
        proof.get('fixtureResourceHashes') == prepared['fixtureResourceHashes'] == parent['fixtureResourceHashes'] and
        proof.get('stockTableBaselines') == prepared['stockTableBaselines'] == parent['stockTableBaselines'],
        'Protected fourteen resources/fixture/table basis differs')
    for ancestor,table in ((parent_source,parent['moduleResourceHashes']), (Path(source),prepared['moduleResourceHashes'])):
        contract.require(flat_hashes(ancestor/'module-resources') == table, 'Native source resource inventory changed')
        for name,digest in table.items(): add({'path':str(ancestor/'module-resources'/name),'sha256':digest})
    for ancestor in (parent_source,Path(source)):
        for name,digest in prepared['fixtureResourceHashes'].items():
            add({'path':str(ancestor/'hak-resources'/name),'sha256':digest})
    for entry in prepared['stockTableBaselines'].values(): add(entry)
    compare_archive(archive(parent_module),parent_source/'module-resources')
    decoded = read(proof['decodedNativeGIT'])
    area = prepared['actorAreaResref']
    current = decode_gff(archive(module),area,'.git',gff_tool)
    original = decode_gff(archive(parent_module),area,'.git',gff_tool)
    contract.require(current == decoded, 'Current native GIT differs from pinned decoded source proof')
    from shared_female_posture_fixture import GFF_FIELDS, PLACEMENT_FIELDS, validate_native_actor_rows
    authorized = set(GFF_FIELDS)|PLACEMENT_FIELDS|{'Equip_ItemList','VarTable'}
    contract.require(proof.get('authorizedActorFields') == sorted(authorized), 'Native source authorized actor fields differ')
    before = original['Creature List']['value']; after = current['Creature List']['value']
    contract.require(len(before) == len(after) == 8 and
        [x['Tag'] for x in before] == [x['Tag'] for x in after], 'Native source actor order/tags differ')
    validate_native_actor_rows(read(prepared['postureRoster']),after)
    import copy
    reverted = copy.deepcopy(current)
    for old,row in zip(before,reverted['Creature List']['value']):
        # Only two Value fields are authorized inside the ordered locals table.
        # Preserve all unrelated locals and the Name/Type/structure metadata.
        old_vars = old.get('VarTable')
        current_vars = copy.deepcopy(row.get('VarTable'))
        contract.require(isinstance(old_vars,dict) and isinstance(current_vars,dict) and
            old_vars.get('type') == current_vars.get('type') == 'list' and
            isinstance(old_vars.get('value'),list) and isinstance(current_vars.get('value'),list) and
            len(old_vars['value']) == len(current_vars['value']), 'Unrelated native actor locals changed')
        for old_var,new_var in zip(old_vars['value'],current_vars['value']):
            name = old_var.get('Name')
            if name in ({'type':'cexostring','value':'TM_POSE'}, {'type':'cexostring','value':'TM_PALETTE'}):
                contract.require('Value' in old_var and 'Value' in new_var, 'Authorized local Value missing')
                new_var['Value'] = copy.deepcopy(old_var['Value'])
        contract.require(current_vars == old_vars, 'Unrelated native actor locals or local metadata changed')
        for name in authorized:
            if name in old: row[name] = copy.deepcopy(old[name])
            else: row.pop(name,None)
    contract.require(reverted == original, 'Undeclared native GIT fields changed')
    # Claimed pass/byte-exact flags are descriptive; current decode and hashes above establish the proof.
    for path,expected in frozen.items():
        contract.require(streamed_sha(path) == expected, 'Native stock/source proof input changed')
    return {**report,'sourceProof':proof_pin,'coverage':basis['coverage'],'frozenInputs':frozen}

def verified_posture_source(receipt_pin, target_path, prepared, source, module, gff_tool, game_root,
                            transition_source_proof=None, transition_animation_authority=None, animation_preparation=None):
    """Explicit script-only descendants; original stock/GIT-only path stays strict."""
    declared = prepared.get('transitionSourceProof')
    if transition_source_proof is None:
        contract.require(declared is None and transition_animation_authority is None and
            prepared.get('transitionAnimationAuthority') is None, 'Transition source requires explicit proof and authority')
        return verified_posture_stock_basis(receipt_pin,target_path,prepared,source,module,gff_tool,game_root)
    contract.require(declared == transition_source_proof == prepared.get('sourceProof') and
        transition_animation_authority is not None and
        prepared.get('transitionAnimationAuthority') == transition_animation_authority and
        prepared.get('postureStockBinding') == receipt_pin,
        'Explicit transition proof/source/animation authority differs')
    from shared_female_transition_fixture import verify_source, strict_json
    report = verify_source(transition_source_proof,target_path,game_root,gff_tool,
        selected_overlay_pin=transition_animation_authority,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
    contract.require(report['moduleResourceHashes'] == prepared['moduleResourceHashes'] and
        report['postureRoster'] == prepared.get('postureRoster') and
        report['postureStockBinding'] == receipt_pin and
        contract.sha(module) == prepared['moduleSha256'], 'Transition child differs from packaged source')
    proof = strict_json(pin(transition_source_proof['path'],transition_source_proof['sha256']))
    contract.require(proof['nativeModule']['sha256'] == prepared['moduleSha256'] and
        proof['fixtureResourceHashes'] == prepared['fixtureResourceHashes'] and
        proof['stockTableBaselines'] == prepared['stockTableBaselines'], 'Transition source material/fixture bytes differ')
    return report


def pack(target_path, prepared_path, prepared_sha256, tools, game_root, output, body=None, animation_overlay=None, posture_roster=None, posture_stock_binding=None, transition_source_proof=None, transition_animation_authority=None, animation_preparation=None):
    target_path = Path(target_path).resolve(); target = contract.load(target_path)
    contract.require(contract.rig_mode(target) == 'stock-exact', 'Stock-exact target required')
    prepared_path = pin(prepared_path,prepared_sha256); prepared = json.loads(prepared_path.read_text())
    contract.require(prepared.get('kind') == 'target-fixture-source', 'Native prepared target fixture required')
    contract.verify_binding(prepared,target_path,target,'runtime')
    output = Path(output).resolve(); tools = Path(tools).resolve(); game_root = Path(game_root).resolve()
    contract.require(not output.exists(), 'Fresh fixture package required')
    allowed = Path(__file__).resolve().parents[2]/'output/phenotypes'/target['id']
    contract.require(output.is_relative_to(allowed), 'Fixture must be inside its declared target working area')
    contract.require(prepared.get('moduleName') == module_name(target) and re.fullmatch(r'[a-z0-9_]{1,16}',prepared['moduleName']), 'Declared target module name differs')
    source = prepared_path.parent
    contract.require(flat_hashes(source/'module-resources') == prepared['moduleResourceHashes'], 'Prepared native module resources changed')
    module_source = pin(prepared['module'],prepared['moduleSha256'])
    compare_archive(archive(module_source),source/'module-resources')
    contract.require(flat_hashes(source/'hak-resources') == prepared['fixtureResourceHashes'], 'Prepared fixture dependencies changed')
    stock = prepared['runtimeBodySource'] == 'stock-human-'+target['identity']['gender']
    contract.require(stock == (body is None), 'Matched stock/candidate fixture body selection differs')
    overlay = verified_animation_overlay(animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {})) if animation_overlay is not None else None
    shared_overlay = overlay is not None and overlay.get('kind') == 'verified-shared-female-source-native-animation-overlay'
    if shared_overlay:
        contract.require(stock and body is None and posture_roster is not None,
                         'Shared posture comparison requires stock body and an explicit roster')
    if posture_roster is not None:
        contract.require(stock and body is None and (overlay is None or shared_overlay),
                         'Posture roster requires a stock-body shared comparison')
        roster = verified_posture_roster(posture_roster,target_path,prepared,module_source,tools/'nwn_gff.exe')
    else:
        contract.require(prepared.get('postureRoster') is None,'Prepared posture roster must be explicitly supplied')
        roster = None
    if posture_roster is not None:
        contract.require(posture_stock_binding is not None, 'Posture roster requires an explicit installed stock binding')
        stock_basis = verified_posture_source(posture_stock_binding,target_path,prepared,source,
            module_source,tools/'nwn_gff.exe',game_root,transition_source_proof,transition_animation_authority,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        stock_basis['frozenInputs'][str(prepared_path.resolve())] = prepared_sha256
    else:
        contract.require(posture_stock_binding is None and prepared.get('postureStockBinding') is None,
                         'Posture stock binding requires an explicit posture roster')
        stock_basis = None
    contract.require(posture_roster is not None or (transition_source_proof is None and transition_animation_authority is None and prepared.get('transitionSourceProof') is None and prepared.get('transitionAnimationAuthority') is None), 'Transition fixture requires its exact roster and source')
    contract.require(transition_source_proof is None or animation_overlay is None or animation_overlay == transition_animation_authority, 'Transition candidate animation differs from authority')
    body_hashes = {}; body_receipt = None
    if body is not None:
        body = Path(body).resolve(); _,_,body_hashes = verify_native_body(body,target_path,require_complete=True)
        body_receipt = contract.sha(body/'native-compile.json')
    animation_hashes = overlay['resourceHashes'] if overlay else {}
    if overlay is not None:
        contract.require(not set(animation_hashes) & (set(body_hashes)|set(prepared['fixtureResourceHashes'])),
                         'Animation overlay overlaps body or fixture resource ownership')
    module_root = output/'test-module'; module_root.mkdir(parents=True)
    shutil.copytree(source/'module-resources',module_root/'module-resources')
    shutil.copytree(source/'hak-resources',module_root/'hak-resources')
    for name in body_hashes: shutil.copyfile(body/'resources'/name,module_root/'hak-resources'/name)
    for name,path in (overlay['resourcePaths'].items() if overlay else ()):
        shutil.copyfile(path,module_root/'hak-resources'/name)
        pin(module_root/'hak-resources'/name,animation_hashes[name])
    user = output/'userdir'; user_layout(user)
    name = prepared['moduleName']; module = user/'modules'/(name+'.mod'); shutil.copyfile(module_source,module)
    hak = user/'hak'/(name+'.hak')
    erf = tools/'nwn_erf.exe'; gff = tools/'nwn_gff.exe'; resman = tools/'nwn_resman_cat.exe'
    subprocess.run([str(erf),'-c','-f',str(hak),'-e','HAK',str(module_root/'hak-resources')],check=True,capture_output=True)
    compare_archive(archive(hak),module_root/'hak-resources')
    table_pins = prepared['stockTableBaselines']
    equipment = {'schemaVersion':2,'kind':'target-equipment-selection',**contract.binding(target_path,target,'runtime'),
                 'mode':'stock-identity','sourcePrefix':target['identity']['prefix'],'runtimeScale':1,
                 'resourceHashes':{},'productionTablesChanged':False,'complete':False,
                 'collisionReviewsAccepted':False,'clientAccepted':False,
                 'frozenInputs':{entry['path']:entry['sha256'] for entry in table_pins.values()},
                 'limitation':'Installed identity-sized equipment retained. Actual equipment matrix review remains pending.'}
    equipment_path = module_root/'stock-equipment-selection.json'; save(equipment_path,equipment)
    report = {'schemaVersion':2,'kind':'target-body-fixture',**contract.binding(target_path,target,'runtime'),
              'validationScope':'full','profile':prepared['profile'],'runtimeBodySource':prepared['runtimeBodySource'],
              'moduleName':name,'module':str(module),'moduleSha256':contract.sha(module),
              'hak':str(hak),'hakSha256':contract.sha(hak),'userDirectory':str(user),
              'bodyConverted':str(body) if body else None,'bodyNativeReceiptSha256':body_receipt,
              'rigConverted':None,'provisionalConverted':None,'fixtureResourceHashes':prepared['fixtureResourceHashes'],
              'moduleResourceHashes':prepared['moduleResourceHashes'],'actorAreaResref':prepared['actorAreaResref'],
              'gffTool':str(gff),'gffToolSha256':contract.sha(gff),'resmanTool':str(resman),'resmanToolSha256':contract.sha(resman),
              'gameRoot':str(game_root),'erfTool':str(erf),'erfToolSha256':contract.sha(erf),
              'equipmentSelection':{'path':str(equipment_path),'sha256':contract.sha(equipment_path)},
              'stockTableBaselines':table_pins,'fixtureAppearanceRows':[],
              'configuration':prepared['configuration'],'sourcePreparation':{'path':str(prepared_path),'sha256':prepared_sha256},
              'clientLaunched':False,'clientAccepted':False,'complete':False,
              'executedCodeSha256':contract.sha(__file__),
              'limitation':'Exact native fixture package only. Preflight and actual client observations remain pending.'}
    if overlay is not None:
        # Reverify source proof after packing; the exact tested overlay stays separate from body ownership.
        contract.require(verified_animation_overlay(animation_overlay,target_path,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))['resourceHashes'] == animation_hashes,
                         'Animation overlay changed during fixture packing')
        report.update(animationOverlay=animation_overlay,animationResourceHashes=animation_hashes)
    if roster is not None:
        # Re-decode the copied module; a matching roster claim alone grants no ownership.
        checked = verified_posture_roster(posture_roster,target_path,prepared,module,gff)
        contract.require(checked['document'] == roster['document'],
                         'Posture roster changed during fixture packing')
        report.update(postureRoster=posture_roster,postureNativeActorsValidated=True)
    if stock_basis is not None:
        pin(prepared_path,prepared_sha256)
        checked_basis = verified_posture_source(posture_stock_binding,target_path,prepared,source,
            module,gff,game_root,transition_source_proof,transition_animation_authority,**({'animation_preparation':animation_preparation} if animation_preparation is not None else {}))
        checked_basis['frozenInputs'][str(prepared_path.resolve())] = prepared_sha256
        contract.require(checked_basis['frozenInputs'] == stock_basis['frozenInputs'] and
            checked_basis['sourceProof'] == stock_basis['sourceProof'] and
            checked_basis['coverage'] == stock_basis['coverage'], 'Native stock/source basis changed during fixture packing')
        report.update(postureStockBinding=posture_stock_binding,postureSourceProof=stock_basis['sourceProof'],
                      postureCoverage=stock_basis['coverage'],postureStockFrozenInputs=stock_basis['frozenInputs'])
    if transition_source_proof is not None:
        report.update(transitionSourceProof=transition_source_proof,transitionAnimationAuthority=transition_animation_authority)
    if transition_source_proof is not None:
        report.update(transitionSourceProof=transition_source_proof,transitionAnimationAuthority=transition_animation_authority)
    receipt = module_root/'receipt.json'; save(receipt,report); return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('target-contract','prepared-fixture','tool-directory','game-root','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--prepared-sha256',required=True); parser.add_argument('--body-converted',type=Path)
    parser.add_argument('--animation-overlay',type=Path); parser.add_argument('--animation-overlay-sha256')
    parser.add_argument('--posture-roster',type=Path); parser.add_argument('--posture-roster-sha256')
    parser.add_argument('--posture-stock-binding',type=Path); parser.add_argument('--posture-stock-binding-sha256')
    args = parser.parse_args()
    contract.require((args.animation_overlay is None) == (args.animation_overlay_sha256 is None),
                     'Animation overlay path and SHA256 must be supplied together')
    overlay = {'path':str(args.animation_overlay.resolve()),'sha256':args.animation_overlay_sha256} if args.animation_overlay else None
    contract.require((args.posture_roster is None) == (args.posture_roster_sha256 is None),
                     'Posture roster path and SHA256 must be supplied together')
    roster = {'path':str(args.posture_roster.resolve()),'sha256':args.posture_roster_sha256} if args.posture_roster else None
    contract.require((args.posture_stock_binding is None) == (args.posture_stock_binding_sha256 is None),
                     'Posture stock binding path and SHA256 must be supplied together')
    stock_binding = {'path':str(args.posture_stock_binding.resolve()),'sha256':args.posture_stock_binding_sha256} if args.posture_stock_binding else None
    receipt = pack(args.target_contract,args.prepared_fixture,args.prepared_sha256,args.tool_directory,args.game_root,args.output,args.body_converted,overlay,roster,stock_binding)
    print(json.dumps({'receipt':str(receipt),'receiptSha256':contract.sha(receipt),'clientLaunched':False}))
