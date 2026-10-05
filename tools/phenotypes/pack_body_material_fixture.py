"""Pack a declared material descendant with immutable native body/test assets.

The original fixture build/compiler receipts remain untouched. This receipt is
explicitly a runtime overlay, not a claim that changed maps were compile inputs.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tool_runtime import tool as resolved_tool

from stage_stock_part import require, sha, save
from audit_pelvis_package import archive
from audit_thigh_package import compare_archive, hashes


def pack(fixture, operation_path, tool, settings_path, output, reuse_hak=None, reuse_hak_sha256=None,
         reuse_body=None, reuse_body_sha256=None):
    require(not output.exists(),'Fresh runtime fixture required')
    operation=json.loads(operation_path.read_text())
    require(operation.get('kind')=='runtime-body-ao-roughness' and
            operation.get('nativeGeometryAndNormalsExact') is True and
            operation.get('pltDiffuseOverride') is False and operation.get('heightMapUsed') is False,
            'Unsupported/unverified material operation')
    body=operation_path.parent/'resources'
    require(hashes(body)==operation['effectiveResourceHashes'],'Effective resources changed')
    for path,expected in operation['frozenInputs'].items():require(sha(path)==expected,'Stale operation input')
    build_path=fixture/'test-module/receipt.json';build=json.loads(build_path.read_text())
    require(sha(build['hak'])==build['hakSha256'] and sha(build['module'])==build['moduleSha256'],
            'Source fixture changed')
    require(build.get('modelMode')=='native-binary' and not build['configuration'].get('cameraLock'),
            'Native models and unlocked camera required')
    source=fixture/'test-module/hak-resources'
    compare_archive(archive(Path(build['hak'])),source)
    base=hashes(source);effective=operation['effectiveResourceHashes']
    require(set(effective)-set(base)==set(operation['addedResources']), 'Unexpected new resource')
    require(all(n.startswith('pmh0_') and not n.startswith(('a_','pf')) for n in effective),
            'Non-body namespace in material operation')
    allowed={('pmh0_'+p+'001'+suffix) for p in operation['parts'] for suffix in ('.plt','.mtr','r.tga')}
    require(set(operation['changedResources'])|set(operation['addedResources'])<=allowed,'Undeclared material ownership')
    output.mkdir(parents=True);staged=output/'hak-resources';shutil.copytree(source,staged)
    for name in effective:shutil.copyfile(body/name,staged/name)
    expected={**base,**effective}
    require(hashes(staged)==expected,'Overlay inventory differs')
    user=output/'userdir';(user/'modules').mkdir(parents=True);(user/'hak').mkdir();(user/'override').mkdir()
    module=user/'modules/srn_pheno_test.mod';shutil.copyfile(build['module'],module)
    shutil.copyfile(settings_path,user/'settings.tml')
    hak=user/'hak/srn_pheno_test.hak'
    if reuse_hak:
        require(sha(reuse_hak)==reuse_hak_sha256,'Stale reusable fixture HAK')
        compare_archive(archive(reuse_hak),staged)
        shutil.copyfile(reuse_hak,hak)
    else:
        require(not reuse_hak_sha256,'Unused HAK pin')
        subprocess.run([str(resolved_tool("nwn_erf", tool)),'-c','-f',str(hak),'-e','HAK',str(staged)],check=True,capture_output=True)
    compare_archive(archive(hak),staged)
    require(sha(module)==build['moduleSha256'],'Module changed during overlay')
    require(all(hashes(staged)[n]==h for n,h in base.items() if not n.startswith('pmh0_')),
            'Comparator/test fixture modified')
    if reuse_body:
        require(sha(reuse_body)==reuse_body_sha256,'Stale reusable body HAK')
        compare_archive(archive(reuse_body),body)
        bodyhak=reuse_body
    else:
        require(not reuse_body_sha256,'Unused body HAK pin')
        bodydir=output/'body-resources';shutil.copytree(body,bodydir)
        bodyhak=output/'human_male_body.hak'
        subprocess.run([str(resolved_tool("nwn_erf", tool)),'-c','-f',str(bodyhak),'-e','HAK',str(bodydir)],check=True,capture_output=True)
        compare_archive(archive(bodyhak),bodydir)
    receipt={'schemaVersion':1,'kind':'runtime-material-fixture','hak':str(hak.resolve()),'hakSha256':sha(hak),
        'module':str(module.resolve()),'moduleSha256':sha(module),'userDirectory':str(user.resolve()),
        'bodyHak':str(bodyhak.resolve()),'bodyHakSha256':sha(bodyhak),
        'bodyResourceHashes':effective,'resourceHashes':expected,'resourceCount':len(expected),
        'sourceBuildReceipt':str(build_path.resolve()),'sourceBuildReceiptSha256':sha(build_path),
        'materialOperation':str(operation_path.resolve()),'materialOperationSha256':sha(operation_path),
        'configuration':build['configuration'],'nativeMode':True,'nativeBodyHashes':{n:h for n,h in effective.items() if n.endswith('.mdl')},
        'geometryNotModified':True,'stockRigFromGame':True,'stockEquipmentIdentity':True,
        'clientAccepted':False,'feetAnatomyAccepted':False,
        'compilerReceiptPolicy':'Original compile receipts preserved; effective runtime dependencies are this explicit overlay.',
        'settingsSourceSha256':sha(settings_path),'helperSha256':sha(__file__)}
    save(output/'fixture.json',receipt);shutil.copyfile(__file__,output/'executed-pack.py')
    print(json.dumps({'output':str(output),'hakSha256':sha(hak),'moduleSha256':sha(module),'resources':len(expected)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('fixture','operation','tool-directory','settings','output'):p.add_argument('--'+key,type=Path,required=(key != 'tool-directory'))
    p.add_argument('--reuse-hak',type=Path);p.add_argument('--reuse-hak-sha256')
    p.add_argument('--reuse-body-hak',type=Path);p.add_argument('--reuse-body-hak-sha256')
    a=p.parse_args();pack(a.fixture,a.operation,a.tool_directory,a.settings,a.output,
                         a.reuse_hak,a.reuse_hak_sha256,a.reuse_body_hak,a.reuse_body_hak_sha256)
