"""Audit actual thigh/shin/foot HAK/MOD bytes against an explicit pinned donor.

This is package integrity, not geometry or client visual acceptance. The preserve
receipt hash must come from the reviewed donor; it is never inferred from a new
stage. Human root/animation/other-part overrides are not permitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from audit_pelvis_package import archive, require, sha
from build_test_module import validate_owned_normal_dependencies
from stock_limb_contract import parse_preserved_parts, validate_new_parts, validate_receipt_lineage

PROTECTED_MODELS = {'pmh0_chest001.mdl','pmh0_pelvis001.mdl'}
TYPE_BY_EXTENSION = {'.tga':3,'.dds':2033,'.plt':6,'.mdl':2002,'.mtr':2072,
    '.set':2013,'.2da':2017,'.nss':2009,'.ncs':2010,'.are':2012,'.git':2023,
    '.ifo':2014,'.fac':2038,'.uti':2025,'.utc':2027}
ACCEPTED_NATIVE = {
    'pmh0_chest001.mdl':'8afdd1e81bd7b695b18ce5b88d5f1fa265e7c34043c5bc838bd012a55fb3e1be',
    'pmh0_pelvis001.mdl':'c0d87495e6405254fa9dfb9b5ec1d144ed098ccd06a6e6290b36fced9a1a428a'}


def read(path):
    return json.loads(Path(path).read_text())


def hashes(folder):
    require(folder.is_dir() and all(p.is_file() for p in folder.iterdir()),'Missing/nested resource directory: '+str(folder))
    return {p.name:sha(p) for p in sorted(folder.iterdir())}


def packed_index(rows):
    return {(name,kind):hashlib.sha256(data).hexdigest() for name,kind,data in rows}


def compare_archive(rows,folder):
    expected = {}
    for name,digest in hashes(folder).items():
        path=Path(name)
        require(path.suffix in TYPE_BY_EXTENSION,'Unknown packed resource extension: '+name)
        key=(path.stem,TYPE_BY_EXTENSION[path.suffix])
        require(key not in expected,'Duplicate staged resref/type')
        expected[key]=digest
    require(packed_index(rows)==expected,'Actual ERF payloads/types differ from exact staging')


def validate_inventory(rows,thighs,comparator_models,protected_models=None):
    protected_models=PROTECTED_MODELS if protected_models is None else protected_models
    validate_new_parts(thighs,protected_models)
    expected_human={Path(n).stem for n in protected_models}|{'pmh0_'+part+'001' for part in thighs}
    models={name for name,kind,data in rows if kind==2002}
    require(models==expected_human|comparator_models,'Undeclared/missing Human, root, limb or comparator model')
    for name,kind,data in rows:
        require(kind in (3,6,2002,2013,2017,2033,2072),'Animation or unsupported HAK resource type')
        if name in {'appearance','sr_pt','sr_pt_edge'}:
            require(kind=={'appearance':2017,'sr_pt':2013,'sr_pt_edge':2017}[name],'Fixture resref/type changed')
            continue
        require(name.startswith(tuple(sorted(expected_human|comparator_models))),'Undeclared HAK namespace: '+name)
        require(not name.startswith(('a_','pf')),'Animation/female override')
    return sorted(expected_human)


def verify_native(converted,expected_models,allow_material_patch=False):
    native=read(converted/'native-compile.json')
    require(native.get('complete') is True and native.get('clientSha256'),'Incomplete native compilation')
    entries=native.get('models',[])
    require(len(entries)==len(expected_models) and {r['name'] for r in entries}==expected_models,
            'Missing/extra/duplicate native model entries')
    deps=native.get('materialResourceHashes',{})
    require(bool(deps),'Missing compile-time material dependencies')
    resource_hashes=hashes(converted/'resources')
    require(set(resource_hashes)==expected_models|set(deps),'Undeclared/missing native resource')
    require(set(hashes(converted/'ascii'))==expected_models,'Undeclared/missing ASCII resource')
    effective = deps
    if (converted/'material-patch.json').exists():
        require(allow_material_patch, 'Runtime palette patch requires explicit audit opt-in')
        from material_patch_contract import validate_material_patch
        effective, _ = validate_material_patch(converted)
    for name,digest in effective.items():require(resource_hashes[name]==digest,'Stale native dependency: '+name)
    validate_owned_normal_dependencies(converted/'resources',deps)
    for entry in entries:
        name=entry['name'];source=converted/'ascii'/name;binary=converted/'resources'/name
        require(sha(source)==entry['sourceSha256'] and sha(binary)==entry['binarySha256'],'Stale actual compile: '+name)
        require(binary.read_bytes()[:4]==b'\0\0\0\0' and binary.stat().st_size==entry['bytes'],'Invalid native binary: '+name)
    return native,resource_hashes


def donor_protection(donor,pinned_receipt,protected_models=None,patch_pin=None):
    protected_models=PROTECTED_MODELS if protected_models is None else protected_models
    receipt=donor/'human_male_fit/converted/native-compile.json'
    require(sha(receipt)==pinned_receipt,'Pinned accepted preserve donor receipt changed')
    composition=read(receipt).get('composition',{})
    converted=donor/'human_male_fit/converted'
    if patch_pin:require(sha(converted/'material-patch.json')==patch_pin,'Pinned accepted material patch changed')
    native,resources=verify_native(converted,protected_models,allow_material_patch=bool(patch_pin))
    require({name:resources[name] for name in PROTECTED_MODELS}==ACCEPTED_NATIVE,
            'Preserve donor is not the accepted chest/pelvis native binaries')
    validate_receipt_lineage(native)
    build=read(donor/'test-module/receipt.json')
    require(sha(build['hak'])==build['hakSha256'] and sha(build['module'])==build['moduleSha256'],
            'Accepted donor package changed')
    rows=archive(build['hak']);compare_archive(rows,donor/'test-module/hak-resources')
    actual=packed_index(rows)
    for name,digest in resources.items():
        require(actual.get((Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]))==digest,
                'Accepted donor resource missing from tested HAK: '+name)
    return resources,native,composition


def validate_actors(actors,manifest,build,donor_control):
    palette=build['configuration'].get('skinColor')
    require(isinstance(palette,int) and 0<=palette<=255,'Invalid/unrecorded skin palette')
    records=manifest['combinations']
    require(len(records)==2 and {r['slug'] for r in records}=={'human_male_fit','stock_human_male_fit'},
            'Undeclared fixture specimens')
    for record in records:
        is_control=record['slug']=='stock_human_male_fit'
        require(record['appearance']==(donor_control['appearance'] if is_control else 6) and record.get('gender')=='male'
            and record.get('phenotype')==0 and record.get('raceId')==6
            and bool(record.get('fixtureControl'))==is_control,'Manifest changes stock fixture rig selection')
        if is_control:require(record==donor_control,'Comparator manifest differs from actual donor row')
    expected={f'pt_{i}':r['appearance'] for i,r in enumerate(records)}
    require(len(actors)==build['specimenCount'] and len({a['Tag']['value'] for a in actors})==len(actors),
            'Fixture actor count/tags differ')
    require(all(tag in {a['Tag']['value'] for a in actors} for tag in expected),'Missing bare comparator/candidate')
    rows=[]
    for actor in actors:
        tag=actor['Tag']['value'];appearance=actor['Appearance_Type']['value']
        require(actor['Gender']['value']==0 and actor['Phenotype']['value']==0 and actor['Race']['value']==6,
                'Actor gender/phenotype/race alters stock rig')
        require(appearance==expected.get(tag,6) and (tag in expected or tag.startswith(('pt_full_','pt_a20_','pt_a21_'))),
                'Undeclared actor or appearance selection')
        require(actor['ScriptSpawn']['value']=='sr_pt_spawn' and actor['ScriptHeartbeat']['value']=='sr_pt_hb',
                'Unexpected actor scripts')
        require(actor['Plot']['value']==(0 if build.get('gameplayTests') else 1),'Unexpected actor plot flag')
        rows.append({'tag':tag,'appearance':appearance,'gender':0,'phenotype':0,'race':6,'plot':actor['Plot']['value']})
    return rows,palette


def validate_part_ascii(text,name):
    require(not re.search(r'(?mi)^\s*newanim\s',text),'Custom part defines animations: '+name)
    require(re.search(r'(?mi)^\s*setsupermodel\s+'+re.escape(Path(name).stem)+r'\s+NULL\s*$',text),
            'Custom part changes supermodel: '+name)


def validate_override(directory):
    require(directory.is_dir() and not list(directory.iterdir()),'Override contamination')


def validate_thigh_palette(data):
    require(data[:8]==b'PLT V1  ' and len(data)>=24,'Invalid limb palette header')
    width,height=struct.unpack_from('<II',data,16)
    require((width,height)==(2048,2048) and len(data)==24+2*width*height,'Limb palette is not exact2K')
    require(set(data[25::2])=={0},'Limb palette contains non-skin layer pixels')


def validate_unit_provenance(native):
    origins=native.get('composition',{}).get('sourceReceipts',[])
    require(len(origins) in (2,3),'Combined limb receipt lacks actual independent unit provenance')
    validate_receipt_lineage(native)


def run(args):
    stage=args.stage.resolve();donor=args.preserve_donor.resolve();thighs=args.expected_models.split(',')
    protected_models=parse_preserved_parts(getattr(args,'preserved_parts','chest,pelvis'))
    validate_new_parts(thighs,protected_models)
    patch_pin=getattr(args,'preserved_material_patch_sha256',None)
    require('footl' not in thighs or patch_pin, 'Feet require explicit accepted runtime palette donor pin')
    protected,donor_native,composition=donor_protection(donor,args.preserve_receipt_sha256,protected_models,patch_pin)
    if 'footl' in thighs:require(protected['pmh0_pelvis001.plt']==
        '990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690','Foot donor reverted accepted pelvis palette')
    donor_control_conversion=read(donor/'stock_human_male_fit/converted/conversion.json')
    aliases=donor_control_conversion.get('stockAliases',[])
    comparator_names={Path(row['source']).name.replace('pmh0','pmx0') for row in aliases}
    require(len(aliases)==len(comparator_names)==20 and all(n.startswith('pmx0') and n.endswith('.mdl') for n in comparator_names),
            'Donor comparator must expose exactly20 actual stock aliases')
    donor_controls=[r for r in read(donor/'manifest.json')['combinations'] if r['slug']=='stock_human_male_fit']
    require(len(donor_controls)==1,'Donor comparator manifest is ambiguous')
    donor_control_record=donor_controls[0]
    build=read(stage/'test-module/receipt.json')
    require(build.get('modelMode')=='native-binary' and build.get('textureMode')=='native','Native palette fixture required')
    require(sha(build['hak'])==build['hakSha256'] and sha(build['module'])==build['moduleSha256'],'Built package changed')
    packed=archive(build['hak']);compare_archive(packed,stage/'test-module/hak-resources')
    human=validate_inventory(packed,thighs,{Path(n).stem for n in comparator_names},protected_models)
    actual=packed_index(packed)
    converted=stage/'human_male_fit/converted'
    model_names={name+'.mdl' for name in human}
    native,resources=verify_native(converted,model_names,allow_material_patch=bool(patch_pin))
    if patch_pin:
        patch=read(converted/'material-patch.json')
        require(patch.get('kind')=='inherited-runtime-pelvis-skin-plt-offset'
            and Path(patch['parentConverted']).resolve()==(donor/'human_male_fit/converted').resolve()
            and patch['parentPatchSha256']==patch_pin, 'Candidate runtime patch is not pinned accepted donor')
    validate_unit_provenance(native)
    require(native['clientSha256']==donor_native['clientSha256'],'Candidate compiler differs from preserved donor')
    for name,digest in protected.items():
        require(resources.get(name)==digest and actual.get((Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]))==digest,
                'Accepted donor payload changed: '+name)
    for name in protected_models:
        require(sha(converted/'ascii'/name)==sha(donor/'human_male_fit/converted/ascii'/name),
                'Accepted donor ASCII changed: '+name)
    for name,digest in resources.items():
        require(actual.get((Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]))==digest,'Native payload differs from HAK: '+name)
    conversion=read(converted/'conversion.json')
    require(conversion.get('rigMode')=='stock-exact-game-fallback' and conversion.get('stockOtherPartsFromGame') is True,
            'Candidate alters stock rig/fallback policy')
    require(conversion.get('modelPrefix')=='pmh0' and abs(conversion.get('height',0)-1.9339157)<1e-7
        and abs(conversion.get('stockReferenceHeight',0)-1.9339157)<1e-7,'Human stock height changed')
    require(len(conversion['parts'])==len(model_names) and {p['model']+'.mdl' for p in conversion['parts']}==model_names,
            'Conversion declares unexpected/duplicate models')
    for name in model_names:
        text=(converted/'ascii'/name).read_text()
        validate_part_ascii(text,name)
    for thigh in thighs:
        validate_thigh_palette((converted/'resources'/('pmh0_'+thigh+'001.plt')).read_bytes())
    control=stage/'stock_human_male_fit/converted'
    control_native,control_resources=verify_native(control,comparator_names)
    donor_control_directory=donor/'stock_human_male_fit/converted'
    require(control_resources==hashes(donor_control_directory/'resources') and hashes(control/'ascii')==hashes(donor_control_directory/'ascii'),
            'Actual stock comparator changed')
    require(control_native['clientSha256']==native['clientSha256'],'Comparator compiler differs')
    control_conversion=read(control/'conversion.json')
    require(control_conversion.get('fixtureControl') is True and control_conversion.get('geometryStatus')=='stock-control'
        and control_conversion.get('modelPrefix')=='pmx0','Comparator is not private stock control')
    require(control_conversion==donor_control_conversion,'Comparator stock-alias provenance changed')
    for alias in aliases:
        origin=Path(alias['source']).resolve()
        require(origin.is_relative_to(args.stock_bank.resolve()/'ascii') and sha(origin)==alias['sourceSha256'],
                'Actual stock comparator source changed/outside stock bank')
        alias_name=origin.stem.replace('pmh0','pmx0')
        text=origin.read_text(encoding='cp1252').replace('pmh0','pmx0')
        if alias_name!='pmx0':text=re.sub(r'(?mi)^\s*bitmap\s+\S+','  bitmap '+alias_name,text)
        require((control/'ascii'/(alias_name+'.mdl')).read_text(encoding='cp1252')==text
            and sha(control/'ascii'/(alias_name+'.mdl'))==alias['aliasSha256'],
            'Comparator alias alters actual stock surface/controllers')
        if alias.get('paletteSha256'):
            require(sha(args.stock_bank/'raw'/(origin.stem+'.plt'))==alias['paletteSha256']
                and sha(control/'resources'/(alias_name+'.plt'))==alias['paletteSha256'],
                'Comparator stock palette changed')
    for name,digest in control_resources.items():
        require(actual.get((Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]))==digest,'Comparator payload changed/missing')
    allowed_keys={(Path(name).stem,TYPE_BY_EXTENSION[Path(name).suffix]) for name in resources.keys()|control_resources.keys()}
    allowed_keys|={('appearance',2017),('sr_pt',2013),('sr_pt_edge',2017)}
    require(set(actual)==allowed_keys,'Undeclared packed material/texture/fixture resource')
    appearance=next(data.decode('cp1252') for name,kind,data in packed if name=='appearance' and kind==2017)
    def row(text):return next(line.split()[1:] for line in text.splitlines() if re.match(r'^\s*6\s',line))
    require(row(appearance)==row((args.stock_bank/'raw/appearance.2da').read_text(encoding='cp1252')),'Stock Human appearance row changed')
    override=stage/'userdir/override';validate_override(override)
    module=archive(build['module']);module_rows=packed_index(module)
    binaries=[p for p in (stage/'test-module/configurations').glob('*/binary') if all(
        module_rows.get((p2.stem,TYPE_BY_EXTENSION.get(p2.suffix,-1)))==sha(p2) for p2 in p.iterdir() if p2.is_file())]
    require(len(binaries)==1,'Cannot associate actual module with one complete emitted-script configuration')
    compare_archive(module,binaries[0])
    require(not any(kind in (2002,2072,3,6) for name,kind,data in module),'Model/material override hidden in module')
    spawn=next(data.decode('ascii') for name,kind,data in module if name=='sr_pt_spawn' and kind==2009)
    require(re.search(r'SetColor\(OBJECT_SELF,COLOR_CHANNEL_SKIN,'+str(build['configuration'].get('skinColor'))+r'\)',spawn),
            'Packed spawn script uses wrong skin palette')
    skin_commands=re.findall(r'SetColor\(OBJECT_SELF,\s*COLOR_CHANNEL_SKIN,\s*([^)]*)\)',spawn)
    require(skin_commands and all(c.strip()==str(build['configuration'].get('skinColor')) for c in skin_commands),
            'Packed spawn script changes palette after the declared command')
    require('for(i=0;i<18;i++) SetCreatureBodyPart(i,1);' in spawn and
        all('SetCreatureBodyPart('+part+',0);' in spawn for part in
            ('CREATURE_PART_BELT','CREATURE_PART_RIGHT_SHOULDER','CREATURE_PART_LEFT_SHOULDER')),
        'Bare actor part selection differs')
    args.output.mkdir(parents=True,exist_ok=False)
    floor=next(data for name,kind,data in module if name=='sr_pt_floor' and kind==2023)
    git=args.output/'packed-floor.git';git.write_bytes(floor);json_path=args.output/'packed-floor.json'
    subprocess.run([str(args.tool_directory/'nwn_gff.exe'),'-i',str(git),'-o',str(json_path),'-p'],capture_output=True,check=True)
    actors,palette=validate_actors(read(json_path)['Creature List']['value'],read(stage/'manifest.json'),build,donor_control_record)
    report={'schemaVersion':1,'hakSha256':sha(build['hak']),'moduleSha256':sha(build['module']),
        'helperDependencyHashes':{'stock_limb_contract.py':sha(Path(__file__).with_name('stock_limb_contract.py'))},
        'preserveDonor':str(donor),'preserveReceiptSha256':args.preserve_receipt_sha256,
        'protectedAcceptedResourceHashes':protected,'exactStagedPayloadsAndTypes':True,
        'humanReplacementModels':human,'thighNativeSuffixes':[p for p in thighs if p in ('legl','legr')],
        'limbNativeSuffixes':thighs,'preservedModels':sorted(protected_models),'stockComparatorExact':True,
        'stockHumanAppearanceRowExact':True,'stockRigAndHeightExact':True,'overrideEmpty':True,
        'packedActors':actors,'skinColor':palette,'packedPaletteCommandVerified':True,
        'thighPalette2KAllLayer0Skin':all(p in ('legl','legr') for p in thighs),
        'limbPalette2KAllLayer0Skin':True,
        'nativeCompileReceiptSha256':sha(converted/'native-compile.json'),'scriptSha256':sha(__file__),
        'clientAccepted':False,'limitation':'Package integrity only; geometry, animation, palette, equipment and performance require client evidence.'}
    (args.output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('stage','preserve-donor','stock-bank','tool-directory','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--preserve-receipt-sha256',required=True,help='Pinned reviewed donor human_male_fit/converted/native-compile.json SHA256')
    parser.add_argument('--expected-models',choices=('legl','legl,legr','shinl','shinl,shinr','footl','footl,footr'),required=True)
    parser.add_argument('--preserved-material-patch-sha256',help='Explicit accepted runtime palette donor pin')
    parser.add_argument('--preserved-parts',default='chest,pelvis',
        help='Historical thigh default chest,pelvis. Feet explicitly preserve chest,pelvis,legl,legr,shinl,shinr.')
    args=parser.parse_args()
    require(re.fullmatch('[0-9a-f]{64}',args.preserve_receipt_sha256) is not None,'Invalid pinned preserve receipt hash')
    run(args)


if __name__=='__main__':main()
