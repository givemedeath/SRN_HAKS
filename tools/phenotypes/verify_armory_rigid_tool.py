"""Exercise the pinned Armory executable with same-source rigid fixtures.

This validates tool semantics and correction, never a final Troll fit.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from armory_rigid import correct_rigid, replace_field
from audit_geometry import arrays
from pipeline import digest, save_json
from retarget import NODE

PIN='08480e535e38d712a831575ea78cc8ed952629ee4705ae8d505cdba31fc01f7f'
PARTS=('chest','pelvis','belt','neck','bicepl','bicepr','forel','forer','handl','handr',
       'legl','legr','shinl','shinr','footl','footr','shol','shor','helmet','shield')
PROFILE={'scale':[1.15,1.08,1.22],'rotate':[12,-7,19],'translate':[.011,-.027,.033]}


def verify(args):
    if digest(args.armory)!=PIN: raise RuntimeError('Pinned Armory executable changed')
    inventory=json.loads(args.inventory.read_text())
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source, raw, corrected=(out/name for name in ('source','raw','corrected'))
    for path in (source,raw,corrected):path.mkdir()
    selected=[]
    for part in PARTS:
        records=[row for row in inventory['models'] if row['part']==part and not row['requiresSkinBindPath'] and not row['localAnimationCount']]
        if not records:raise RuntimeError('No rigid fixture for '+part)
        row=records[0];path=Path(row['asciiPath'])
        if digest(path)!=row['asciiSha256']:raise RuntimeError('Fixture source changed: '+path.name)
        copied=source/path.name;shutil.copyfile(path,copied)
        selected.append({'part':part,'sourcePath':str(path),'sourceSha256':digest(path),'fixturePath':str(copied),'fixtureSha256':digest(copied)})
    dangly=next(row for row in inventory['models'] if row['meshTypes'].get('danglymesh') and row['part']=='bicepl' and not row['requiresSkinBindPath'] and not row['localAnimationCount'])
    path=Path(dangly['asciiPath']);copied=source/path.name
    if digest(path)!=dangly['asciiSha256']:raise RuntimeError('Dangly fixture source changed')
    shutil.copyfile(path,copied)
    selected.append({'part':'stock-dangly-upperarm','sourcePath':str(path),'sourceSha256':digest(path),'fixturePath':str(copied),'fixtureSha256':digest(copied)})
    # A stock mesh with unchanged vertices/UVs, explicitly nested and rotated.
    chest=source/next(row for row in inventory['models'] if row['part']=='chest')['resource']
    text=chest.read_text(encoding='ascii')
    model=re.search(r'(?mi)^newmodel\s+(\S+)',text)[1]
    text=re.sub(r'(?i)\b'+re.escape(model)+r'\b','pmh0_chest099',text)
    text=text.replace('bitmap pmh0_chest099','bitmap '+model)
    block=next(b for b in NODE.finditer(text.split('endmodelgeom')[0]) if arrays(b[3],'verts'))
    body=replace_field(block[3],'parent','fixture_pivot')
    body=replace_field(body,'orientation','0 1 0 .21')
    text=text[:block.start()]+f'node {block[1]} {block[2]}\n{body}endnode'+text[block.end():]
    pivot='node dummy fixture_pivot\n parent pmh0_chest099\n position .13 -.11 .07\n orientation 0 0 1 .37\nendnode\n'
    text=text.replace('endmodelgeom pmh0_chest099',pivot+'endmodelgeom pmh0_chest099')
    nested=source/'pmh0_chest099.mdl';nested.write_text(text,encoding='ascii')
    selected.append({'part':'nested-rotation-fixture','sourcePath':str(chest),'sourceSha256':digest(chest),
                     'fixturePath':str(nested),'fixtureSha256':digest(nested),'sameVertexUvFaceArrays':True})
    surface=source/'pmh0_chest998.mdl'
    surface.write_text('newmodel pmh0_chest998\nsetsupermodel pmh0_chest998 NULL\nbeginmodelgeom pmh0_chest998\nnode dummy pmh0_chest998\n parent NULL\nendnode\nnode trimesh support_surface\n parent pmh0_chest998\n position .1 -.2 .3\n orientation 0 1 0 .21\n bitmap support\n verts 3\n 0 0 0\n 0 0 1\n 1 -1 0\n normals 3\n .7071067811865475 .7071067811865475 0\n .7071067811865475 .7071067811865475 0\n .7071067811865475 .7071067811865475 0\n tangents 3\n 0 0 1 1\n 0 0 1 1\n 0 0 1 1\n tverts 3\n 0 0 0\n 1 0 0\n 0 1 0\n faces 1\n 0 1 2 1 0 1 2 0\nendnode\nendmodelgeom pmh0_chest998\n',encoding='ascii')
    selected.append({'part':'authored-normal-surface-fixture','sourcePath':str(surface),
                     'sourceSha256':digest(surface),'fixturePath':str(surface),'fixtureSha256':digest(surface),
                     'supportOnlySyntheticSurface':True})
    ini=out/'reviewed-tool-test.ini'
    ini.write_text('[Global]\nntransforms=1\n[s0]\nmatch=*\nsubstitute=*\nscale=(1.15,1.08,1.22)\nrotate=(12,-7,19)\ntranslate=(.011,-.027,.033)\n',encoding='ascii')
    def run(arguments,label):
        result=subprocess.run([str(args.armory.resolve()),*map(str,arguments)],capture_output=True,text=True)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        return result
    dry=run(['--dry-run',ini,source,raw],'dry-run')
    if dry.returncode or any(raw.iterdir()):raise RuntimeError('Armory dry run wrote resources or failed')
    batch=run([ini,source,raw],'batch')
    expected={Path(row['fixturePath']).name for row in selected}
    if batch.returncode or {path.name for path in raw.iterdir()}!=expected:raise RuntimeError('Armory batch failed or omitted outputs')
    proofs=[]
    for row in selected:
        src=Path(row['fixturePath']);dst=corrected/src.name;shutil.copyfile(raw/src.name,dst)
        fit=run(['--values',src,raw/src.name],'fit-'+src.stem)
        if fit.returncode:raise RuntimeError('Same-source Armory fit failed: '+src.name)
        residuals=[float(value) for value in re.findall(r'max_residual\s*[=:]\s*([\d.eE+\-]+)',fit.stdout)]
        if any(value>1e-5 for value in residuals):raise RuntimeError('Same-source Armory fit residual is too high: '+src.name)
        proofs.append({**row,'rawSha256':digest(raw/src.name),'correctedPath':str(dst),
                       'correction':correct_rigid(src,dst,PROFILE),'fitExitCode':fit.returncode,'fitResiduals':residuals})
        if digest(src)!=row['fixtureSha256']:raise RuntimeError('Armory changed a source fixture')
        if row.get('supportOnlySyntheticSurface'):
            import numpy as np
            block=next(b for b in NODE.finditer(dst.read_text()) if arrays(b[3],'verts'))
            vertices=np.asarray(arrays(block[3],'verts')); normal=np.cross(vertices[1]-vertices[0],vertices[2]-vertices[0]);normal/=np.linalg.norm(normal)
            normal_error=float(np.max(np.abs(np.asarray(arrays(block[3],'normals'))-normal)))
            if normal_error>1e-8:raise RuntimeError('Corrected authored normals do not match the transformed surface')
            proofs[-1]['transformedFaceNormalAgreementError']=normal_error
    existing={path.name:digest(path) for path in raw.iterdir()}
    collisions=run([ini,source,raw],'collisions')
    if collisions.returncode!=1 or existing!={path.name:digest(path) for path in raw.iterdir()}:
        raise RuntimeError('Armory collision behavior differs from pinned policy')
    partial_source,partial_target=out/'partial-source',out/'partial-target';partial_source.mkdir();partial_target.mkdir()
    shutil.copyfile(chest,partial_source/chest.name)
    bad=partial_source/'pmh0_bad000.mdl'
    bad.write_text('newmodel pmh0_bad000\nbeginmodelgeom pmh0_bad000\nnode trimesh bad\n verts 3\n 1 0 0\n invalid\nendnode\nendmodelgeom pmh0_bad000\n')
    partial=run([ini,partial_source,partial_target],'partial-batch')
    if partial.returncode!=1 or not (partial_target/chest.name).exists() or (partial_target/bad.name).exists():
        raise RuntimeError('Armory partial failure was not rejected while preserving successful outputs')
    shutil.copyfile(Path(__file__),out/'executed-verifier.py')
    shutil.copyfile(Path(__file__).with_name('armory_rigid.py'),out/'executed-armory-rigid.py')
    receipt={'schemaVersion':1,'kind':'armory-rigid-support-proof','armorySha256':PIN,
             'sourceInventory':{'path':str(args.inventory.resolve()),'sha256':digest(args.inventory)},
             'helperSha256':digest(Path(__file__).with_name('armory_rigid.py')),'profile':PROFILE,
             'profilePath':str(ini),'profileSha256':digest(ini),'fixtures':proofs,
             'dryRunExitCode':dry.returncode,'batchExitCode':batch.returncode,
             'collisionExitCode':collisions.returncode,'existingOutputsPreserved':True,
             'partialBatchExitCode':partial.returncode,'partialBatchAcceptanceBlocked':True,
             'rigRevision':None,'profilesAccepted':False,'clientAccepted':False}
    save_json(out/'proof.json',receipt)
    print(json.dumps({'fixtures':len(proofs),'maxWorldError':max(row['correction']['maximumWorldTransformError'] for row in proofs),
                      'collisionExitCode':collisions.returncode,'partialBatchExitCode':partial.returncode,'profilesAccepted':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','armory','output'):parser.add_argument('--'+field,type=Path,required=True)
    verify(parser.parse_args())


if __name__=='__main__':main()
