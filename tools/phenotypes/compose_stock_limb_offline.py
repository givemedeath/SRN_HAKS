"""Pack ASCII feet with byte-exact accepted native neighbours, without nwmain.

The mixed HAK is an offline diagnostic only, never a completed native package.
No MOD, compile receipt, client directory or launch is fabricated. Native model
compile commands are recorded as blocked commands, not executed.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tool_runtime import tool as resolved_tool
import sys
from audit_thigh_package import archive, packed_index, compare_archive, TYPE_BY_EXTENSION, donor_protection, validate_inventory
from compose_stock_limb_native import file_hashes, stock_identity, thigh_attachment, stage_manifest
from stock_limb_contract import parse_preserved_parts, validate_new_parts
from stage_stock_part import require, sha, save
from audit_limb_ascii_material import audit as audit_ascii

PRESERVED_PARTS='chest,pelvis,legl,legr,shinl,shinr'
ACCEPTED_HAK='2ea5a2ffd5ee9b717e785b6aae08e88d39449395665ee18adb07c6513fcbb299'
# The exact selected payload is pinned by caller as well; do not guess a donor.
CORRECTED_PLT='990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690'


def offline_stage(root,foot_material_pin=None):
    root=Path(root).resolve()
    if (root/'foot-material-patch.json').exists():
        from foot_material_contract import validate_foot_material_stage
        converted,receipt,proof=validate_foot_material_stage(root,foot_material_pin)
        receipt=dict(receipt);receipt['footMaterialProof']=proof
        return converted,receipt
    require(not foot_material_pin,'Pinned foot material operation missing')
    receipt=json.loads((root/'stock-part-stage.json').read_text())
    config=receipt['configuration'];model=config['model']+'.mdl'
    require(config['part'] in ('footl','footr') and config.get('prefix')=='pmh0'
        and config.get('raceId')==6 and config.get('gender')=='male','Only declared Human male feet supported')
    thigh_attachment(config,model)
    require(receipt.get('stockControllersModified') is False and receipt.get('nativeCompiled') is False
        and receipt.get('equipmentMode')=='stock-identity' and receipt.get('diagnosticOnly') is True,
        'Expected uncompiled stock-rig single-foot stage')
    for path,digest in receipt['frozenInputs'].items():require(sha(path)==digest,'Frozen foot input changed: '+path)
    for relative,digest in receipt['stagedFiles'].items():
        path=(root/relative).resolve();require(path.is_relative_to(root) and sha(path)==digest,'Staged foot changed: '+relative)
    converted=root/config['slug']/'converted';conversion=json.loads((converted/'conversion.json').read_text())
    stock_identity(conversion,{model});stage_manifest(root,config['slug'])
    require(not (converted/'native-compile.json').exists(),'Offline composition requires untouched uncompiled foot stage')
    expected={config['model']+suffix for suffix in ('.plt','.mtr','n.tga')}
    require(set(file_hashes(converted/'ascii'))=={model}
        and set(file_hashes(converted/'resources'))==expected
        and file_hashes(converted/'resources')==conversion['ownedResourceHashes'],
        'Undeclared foot resources or binary model in offline stage')
    return converted,receipt


def compose(args):
    donor=args.preserve_donor.resolve();preserved=parse_preserved_parts(PRESERVED_PARTS)
    protected,native,_=donor_protection(donor,args.preserve_receipt_sha256,preserved,args.preserved_material_patch_sha256)
    geometry_path=args.preserved_geometry_selection.resolve()
    require(sha(geometry_path)==args.preserved_geometry_selection_sha256,'Preserved geometry selection changed')
    selected_geometry=json.loads(geometry_path.read_text())
    require(set(selected_geometry)==set(PRESERVED_PARTS.split(',')),'Expected explicit six accepted geometry sources')
    for part,selection in selected_geometry.items():
        require(sha(selection['path'])==selection['sha256'],'Selected accepted geometry changed: '+part)
    build=json.loads((donor/'test-module/receipt.json').read_text())
    require(build['hakSha256']==args.preserve_hak_sha256==ACCEPTED_HAK,'Wrong accepted corrected HAK pin')
    require(protected['pmh0_pelvis001.plt']==CORRECTED_PLT,'Accepted pelvis correction would revert')
    parent_rows=archive(build['hak']);require(len(parent_rows)==68,'Expected exactly68 accepted source payloads')
    pins=getattr(args,'foot_material_patch_sha256',None) or []
    require(len(pins)==len(set(pins)),'Duplicate foot material operation pins')
    used=[];stages=[]
    for path in args.stage:
        patch_path=path/'foot-material-patch.json';pin=sha(patch_path) if patch_path.exists() else None
        if pin:require(pin in pins,'Foot shade descendant requires explicit packaging opt-in');used.append(pin)
        stages.append(offline_stage(path,pin))
    require(set(used)==set(pins),'Unused or wrong foot material operation pin')
    parts=[r['configuration']['part'] for _,r in stages]
    validate_new_parts(parts,preserved)
    require(set(parts) in ({'footl'},{'footl','footr'}),'Expected left foot or complete pair')
    additions={}
    for converted,receipt in stages:
        config=receipt['configuration'];model=config['model']+'.mdl'
        for folder in ('ascii','resources'):
            for path in (converted/folder).iterdir():
                key=(path.stem,TYPE_BY_EXTENSION[path.suffix])
                require(key not in additions and key not in packed_index(parent_rows),'Foot resource ownership collision')
                additions[key]=(path,path.name)
    require(len(additions)==4*len(parts),'Expected one ASCII model plus three material resources per foot')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    resources=output/'hak-resources';resources.mkdir()
    for name,kind,data in parent_rows:
        suffix=next(ext for ext,k in TYPE_BY_EXTENSION.items() if k==kind)
        (resources/(name+suffix)).write_bytes(data)
    for path,name in additions.values():shutil.copyfile(path,resources/name)
    queue=[];audits=[]
    for index,(converted,receipt) in enumerate(stages):
        config_path=output/('foot-'+str(index)+'-config.json');save(config_path,receipt['configuration'])
        audit_converted=converted
        if receipt.get('footMaterialProof'):
            patch=json.loads((args.stage[index]/'foot-material-patch.json').read_text())
            audit_converted=Path(patch['parentStage'])/'human_male_fit/converted'
        result=audit_ascii(audit_converted,config_path);save(output/('foot-'+str(index)+'-ascii-audit.json'),result)
        audits.append({'path':str(output/('foot-'+str(index)+'-ascii-audit.json')),'sha256':sha(output/('foot-'+str(index)+'-ascii-audit.json'))})
        queue.append({'blockedByUserClientHold':True,'deferredToBulkValidationPhase':True,
            'executed':False,'requiresNwmain':True,'argv':[
            sys.executable,str(Path(__file__).with_name('native_compile.py').resolve()),'--client',native['client'],
            '--converted',str(converted),'--user-directory',str(output/('compile-userdir-'+str(index))),
            '--timeout','180','--with-material-resources']})
    hak=output/'offline-native-pending.hak'
    subprocess.run([str(resolved_tool("nwn_erf", args.tool_directory)),'-c','-f',str(hak),'-e','HAK',str(resources)],check=True,capture_output=True)
    rows=archive(hak);compare_archive(rows,resources)
    actual=packed_index(rows);before=packed_index(parent_rows)
    require(all(actual.get(k)==v for k,v in before.items()),'Offline pack changed accepted HAK payload')
    control={name for name,kind,_ in parent_rows if kind==2002 and name.startswith('pmx0')}
    validate_inventory(rows,parts,control,preserved)
    for converted,receipt in stages:
        name=receipt['configuration']['model']
        require(actual[(name,2002)]==sha(converted/'ascii'/(name+'.mdl')),'Offline foot model is not declared ASCII')
    save(output/'blocked-native-commands.json',queue)
    # Future phenotype collection is a separate clean inventory. Keep fixture
    # comparator aliases/tables in the diagnostic HAK only.
    body=output/'body-resources';body.mkdir()
    body_hashes={}
    for name,digest in protected.items():
        source=donor/'human_male_fit/converted/resources'/name
        shutil.copyfile(source,body/name);require(sha(body/name)==digest,'Clean body neighbour changed')
        body_hashes[name]=digest
    for path,name in additions.values():
        shutil.copyfile(path,body/name);body_hashes[name]=sha(body/name)
    require(len(body_hashes)==26+4*len(parts),'Clean body inventory has fixture baggage/missing payload')
    geometry=dict(selected_geometry)
    for index,(_,receipt) in enumerate(stages):
        config=receipt['configuration']
        geometry[config['part']]={'path':config['source'],'sha256':config['expectedInputHashes']['source'],
            'reviewedFitReceipt':config['reviewedFitReceipt'],'materialStage':str(args.stage[index].resolve()),
            'footMaterialProof':receipt.get('footMaterialProof'),
            'nativeCompilePending':True,'clientValidationDeferredToBulk':True}
    collection={'schemaVersion':1,'kind':'offline-selected-body-collection','fixtureResourcesIncluded':False,
        'resources':body_hashes,'resourceCount':len(body_hashes),'acceptedNativeParts':PRESERVED_PARTS.split(','),
        'newAsciiNativePendingParts':parts,'selectedGeometry':geometry,'stockRigBank':stages[0][1]['configuration']['stockBaseline'],
        'stockHeightMetres':1.9339157,'equipmentMode':'stock-identity','rootAnimationOverridesIncluded':False,
        'acceptedNativeReceipt':{'path':str(donor/'human_male_fit/converted/native-compile.json'),'sha256':args.preserve_receipt_sha256},
        'acceptedRuntimePaletteReceipt':{'path':str(donor/'human_male_fit/converted/material-patch.json'),'sha256':args.preserved_material_patch_sha256},
        'correctedPelvisPaletteSha256':CORRECTED_PLT,'geometrySelectionInputSha256':sha(geometry_path),
        'blockedNativeCommands':{'path':str(output/'blocked-native-commands.json'),'sha256':sha(output/'blocked-native-commands.json')},
        'nativeAndClientValidationSchedule':'deferred-whole-phenotype-bulk-validation','productionPromotable':False,
        'limitation':'Clean resource collection, not a new native compile assertion. Six existing native binaries remain accepted; feet are ASCII/material diagnostics pending bulk engine checks.'}
    save(output/'body-resource-manifest.json',collection)
    result={'schemaVersion':1,'diagnosticOnly':True,'fixtureOnly':True,'productionPromotable':False,
        'nativeCompilePending':True,'nativeTbnPending':True,
        'clientValidationPending':True,'compilerExecuted':False,'clientControlled':False,
        'nativeAndClientValidationSchedule':'deferred-whole-phenotype-bulk-validation',
        'modelMode':'accepted-neighbours-native/new-feet-ascii','hak':str(hak),'hakSha256':sha(hak),
        'resourceCount':len(rows),'all68AcceptedPayloadsExact':True,'correctedPelvisPalettePreserved':True,
        'preservedParts':PRESERVED_PARTS.split(','),'newParts':parts,'asciiMaterialAudits':audits,
        'footMaterialPatches':[r['footMaterialProof'] for _,r in stages if r.get('footMaterialProof')],
        'pendingCompileMaterialHashes':[{p.name:sha(p) for p in (c/'resources').iterdir()} for c,_ in stages],
        'parentHak':build['hak'],'parentHakSha256':sha(build['hak']),
        'parentNativeReceiptSha256':args.preserve_receipt_sha256,'parentMaterialPatchSha256':args.preserved_material_patch_sha256,
        'parentBuildReceiptSha256':sha(donor/'test-module/receipt.json'),
        'acceptedPayloadHashes':{name+':'+str(kind):digest for (name,kind),digest in before.items()},
        'addedPayloadHashes':{name+':'+str(kind):actual[(name,kind)] for name,kind in additions},
        'blockedCommandsSha256':sha(output/'blocked-native-commands.json'),
        'cleanBodyManifestSha256':sha(output/'body-resource-manifest.json'),
        'stages':[{'path':str(p.resolve()),'receiptSha256':sha(p/'stock-part-stage.json')} for p in args.stage],
        'helperSha256':sha(__file__),'limitations':'Offline mixed HAK only. No module or native-foot compile receipt. Do not promote or launch.'}
    save(output/'offline-composition.json',result)
    (output/'README.md').write_text(
        '# Offline fixture package only\n\n'
        'This HAK preserves all 68 accepted fixture payloads, including the private stock comparator and test tables. '
        'It adds uncompiled ASCII feet, original source maps and either original or explicitly calibrated skin0 PLTs. '
        'Normal maps and MTRs remain unchanged. It is not a production body HAK.\n\n'
        'Accepted source HAK SHA256: `'+ACCEPTED_HAK+'`. All accepted payloads and the corrected pelvis PLT are byte-exact. '
        'No MOD or complete foot native receipt exists here. `blocked-native-commands.json` records commands only; '
        'do not execute them while the user holds all NWN activity. Native compilation, actual engine TBN, motion, '
        'palette, boots and client visual acceptance remain pending.\n',encoding='utf-8')
    print(json.dumps({'hakSha256':result['hakSha256'],'resourceCount':len(rows),'nativeCompilePending':True}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=Path,action='append',required=True)
    parser.add_argument('--foot-material-patch-sha256',action='append',help='Explicit pin for each declared foot-only shade descendant.')
    for key in ('preserve-donor','tool-directory','output'):parser.add_argument('--'+key,type=Path,required=(key != 'tool-directory'))
    parser.add_argument('--preserved-geometry-selection',type=Path,required=True)
    parser.add_argument('--preserved-geometry-selection-sha256',required=True)
    for key in ('preserve-receipt-sha256','preserved-material-patch-sha256','preserve-hak-sha256'):
        parser.add_argument('--'+key,required=True)
    compose(parser.parse_args())


if __name__=='__main__':main()
