"""Verify a complete-body isolated fixture before launching the authorized client."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from audit_pelvis_package import archive
from audit_thigh_package import compare_archive,packed_index,TYPE_BY_EXTENSION
from effective_body_contract import validate_effective_body
from stage_stock_part import require,sha,save


def preflight(stage,expected_receipt,client):
    stage=Path(stage).resolve();client=Path(client).resolve()
    allowed=Path(__file__).resolve().parents[2]/'output/phenotypes/human-male-complete-goal-v1'
    require(stage.is_relative_to(allowed),'Complete Human fixture must be inside its goal directory')
    receipt=stage/'test-module/receipt.json'
    require(sha(receipt)==expected_receipt,'Explicit reviewed fixture receipt changed')
    build=json.loads(receipt.read_text())
    converted=stage/'human_male_fit/converted'
    native,_,current=validate_effective_body(converted)
    require(current['completeBodySelected'],'Client gate requires all fourteen selected parts')
    require(sha(client)==native['clientSha256'],'Client differs from actual native compiler')
    require(build.get('modelMode')=='native-binary' and build.get('textureMode')=='native'
            and not build['configuration']['cameraLock']
            and build['configuration']['effectiveNativeBodyMaterials'] is True,
            'Native current materials and unlocked cameras required')
    binding=build.get('effectiveNativeBodies',{}).get('human_male_fit',{})
    require(binding.get('completeBodySelected') is True and binding.get('acceptedSixBytesExact') is True
            and binding.get('inventorySha256')==sha(converted/'effective-material-inventory.json')
            and binding.get('resourceHashes')==current['resourceHashes'],
            'Fixture is not bound to the complete current body')
    userdir=stage/'userdir'
    require(Path(build['userDirectory']).resolve()==userdir,'Fixture userdir association differs')
    for kind,relative in [('hak','hak/srn_pheno_test.hak'),('module','modules/srn_pheno_test.mod')]:
        target=userdir/relative
        require(Path(build[kind]).resolve()==target and sha(target)==build[kind+'Sha256'],
                'Packed fixture path/hash differs: '+kind)
    rows=archive(build['hak']);compare_archive(rows,stage/'test-module/hak-resources')
    packed=packed_index(rows)
    for name,pin in current['resourceHashes'].items():
        item=Path(name)
        require(packed.get((item.stem,TYPE_BY_EXTENSION[item.suffix]))==pin,
                'Complete body payload differs: '+name)
    actual_human={n+'.mdl' for n,k,_ in rows if k==2002 and n.startswith('pmh')}
    require(actual_human==set(current['modelParts']), 'Legacy or missing Human body models packed')
    require(not any(n.startswith(('a_','pf')) for n,_,_ in rows),'Animation/female overrides packed')
    require((userdir/'override').is_dir() and not any((userdir/'override').iterdir()),'Client override must be empty')
    require({p.name for p in (userdir/'hak').iterdir()}=={'srn_pheno_test.hak'},'Undeclared client HAKs')
    require({p.name for p in (userdir/'modules').iterdir()}=={'srn_pheno_test.mod'},'Undeclared client modules')
    subprocess.run([sys.executable,str(Path(__file__).with_name('check_userdir.py')),str(userdir)],
                   check=True,capture_output=True)
    return {'schemaVersion':1,'kind':'complete-body-client-preflight','pass':True,
            'fixture':str(stage),'userDirectory':str(userdir),'fixtureReceiptSha256':sha(receipt),
            'completeBodySelected':True,'acceptedSixBytesExact':True,'actualHakPayloadVerified':True,
            'bodyParts':sorted(current['modelParts'].values()),'bodyResourceHashes':current['resourceHashes'],
            'hakSha256':build['hakSha256'],'moduleSha256':build['moduleSha256'],
            'client':str(client),'clientSha256':sha(client),'overrideEmpty':True,'cameraLocked':False,
            'clientLaunched':False,'executedCodeSha256':sha(__file__)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--receipt-sha256',required=True)
    parser.add_argument('--client',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'Fresh preflight evidence required')
    result=preflight(args.fixture,args.receipt_sha256,args.client);save(args.output,result)
    print(json.dumps({k:result[k] for k in ('pass','completeBodySelected','userDirectory','hakSha256','moduleSha256')}))
