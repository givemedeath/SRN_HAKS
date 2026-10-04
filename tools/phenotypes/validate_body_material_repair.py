"""Independently check effective runtime bytes against the frozen parent.

This validates material transport and package ownership, not visual acceptance.
"""
import argparse
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image

from audit_body_material_inputs import plt_image
from audit_pelvis_package import archive
from audit_thigh_package import compare_archive, hashes
from stage_stock_part import require, sha, save


def validate(operation_path, fixture_path, output):
    op=json.loads(operation_path.read_text())
    fixture=json.loads(fixture_path.read_text())
    config_path=operation_path.parent/'executed-config.json'
    require(sha(config_path)==op['configurationSha256'],'Executed configuration differs')
    config=json.loads(config_path.read_text())
    audit=json.loads(Path(config['audit']).read_text())
    base=Path(config['baselineResources']);effective=operation_path.parent/'resources'
    require(hashes(base)==op['parentResourceHashes'],'Parent differs')
    require(hashes(effective)==op['effectiveResourceHashes'],'Effective bytes differ')
    for path,expected in op['frozenInputs'].items():require(sha(path)==expected,'Frozen input changed: '+path)
    changed={n for n in op['parentResourceHashes'] if op['parentResourceHashes'][n]!=op['effectiveResourceHashes'][n]}
    require(changed==set(op['changedResources']),'Change allowlist differs')
    require(set(op['effectiveResourceHashes'])-set(op['parentResourceHashes'])==set(op['addedResources']),
            'Addition allowlist differs')
    rows={}
    for part,record in audit['parts'].items():
        model=record['model'];settings=config['partSettings'][part]
        old=plt_image((base/(model+'.plt')).read_bytes())
        new=plt_image((effective/(model+'.plt')).read_bytes())
        skin=old[:,:,1]==0;delta=new[:,:,0].astype(int)-old[:,:,0].astype(int)
        mask=np.asarray(Image.open(operation_path.parent/'masks'/(part+'-influence.png')))
        require(np.array_equal(old[:,:,1],new[:,:,1]),'PLT layer change')
        require(np.array_equal(old[~skin],new[~skin]),'Non-skin pixel change')
        require(np.array_equal(old[mask==0],new[mask==0]),'Zero-influence connector changed')
        require(delta.min()>=-settings['maxDarkenShades'] and delta.max()<=settings['maxBrightenShades'],
                'Unbounded shade edit')
        require(sha(base/(model+'.mdl'))==sha(effective/(model+'.mdl')),'Native model changed')
        require(sha(base/(model+'n.tga'))==sha(effective/(model+'n.tga')),'Normal pixels changed')
        mtr=(effective/(model+'.mtr')).read_text()
        require(not re.search(r'(?mi)^\s*texture[045]\s',mtr),'Diffuse/height/illumination override')
        if config['useRoughness']:
            require(re.findall(r'(?mi)^\s*texture3\s+(\S+)',mtr)==[model+'r'],'Roughness binding differs')
            require(re.findall(r'(?mi)^\s*parameter float Roughness\s+(\S+)',mtr)==['0'],
                    'Positive constant masks roughness map')
            orm=np.asarray(Image.open(record['images']['orm']['path']).convert('RGB'))
            factor=record['material']['pbrMetallicRoughness'].get('roughnessFactor',1)
            expected=np.rint(orm[:,:,1].astype(float)*factor).clip(0,255).astype(np.uint8)
            actual=np.asarray(Image.open(effective/(model+'r.tga')).convert('RGB'))
            require(actual.shape==(2048,2048,3) and np.all(actual==expected[:,:,None]),'Roughness data changed')
        rows[part]={'nativeModelExact':True,'normalMapExact':True,'layersAndNonSkinExact':True,
                    'zeroInfluenceExact':True,'shadeDeltaRange':[int(delta.min()),int(delta.max())],
                    'roughnessDataExact':bool(config['useRoughness'])}
    for left,right in [('legl','legr'),('shinl','shinr'),('footl','footr')]:
        for suffix in ('.plt','r.tga'):
            if suffix=='r.tga' and not config['useRoughness']:continue
            require(sha(effective/('pmh0_'+left+'001'+suffix))==sha(effective/('pmh0_'+right+'001'+suffix)),
                    'Mirrored maps differ')
    require(fixture['bodyResourceHashes']==op['effectiveResourceHashes'],'Fixture body differs')
    require(sha(fixture['hak'])==fixture['hakSha256'] and sha(fixture['module'])==fixture['moduleSha256'],
            'Packed fixture changed')
    require(sha(fixture['bodyHak'])==fixture['bodyHakSha256'],'Body-only archive hash changed')
    compare_archive(archive(Path(fixture['hak'])),fixture_path.parent/'hak-resources')
    compare_archive(archive(Path(fixture['bodyHak'])),effective)
    require(not any((Path(fixture['userDirectory'])/'override').iterdir()),'Stale override')
    require(not fixture['configuration'].get('cameraLock'),'Locked camera')
    require(all(n.startswith('pmh0_') and not n.startswith(('pf','a_')) for n in op['effectiveResourceHashes']),
            'Non-body ownership')
    save(output,{'kind':'independent-runtime-material-audit','passed':True,
         'operationSha256':sha(operation_path),'fixtureReceiptSha256':sha(fixture_path),
         'hakSha256':fixture['hakSha256'],'bodyHakSha256':fixture['bodyHakSha256'],
         'resourceCount':len(op['effectiveResourceHashes']),'parts':rows,
         'allFrozenInputsExact':True,'mirroredMapPixelsExact':True,
         'packedInventoryExact':True,'stockRigNotOverridden':True,
         'auditorSha256':sha(__file__),
         'limitation':'No geometry acceptance or visible-only calibration claimed.'})
    print(json.dumps({'passed':True,'parts':list(rows),'resources':len(op['effectiveResourceHashes'])}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('operation','fixture','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();validate(args.operation,args.fixture,args.output)
