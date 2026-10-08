"""Prepare declared rigid Troll equipment in fresh isolated artifacts.

Working calibration and one runtime stature conversion remain separate.
This never writes an installed/converted pack or changes Human helper defaults.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import shutil
import subprocess
import numpy as np

import target_contract as contract
import shared_toolchain
from armory_rigid import correct_rigid, profile_affine, rigid_frames, directions
from audit_geometry import arrays
from audit_stock_equipment_palettes import read_stock_plt
from measure_held_equipment import table_rows
from pipeline import digest, save_json

ARMORY_SHA256='08480e535e38d712a831575ea78cc8ed952629ee4705ae8d505cdba31fc01f7f'
ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'
ARRAY_FIELDS=('faces','tverts','tverts1','tverts2','tverts3','colors','constraints')
MATERIAL_FIELDS=('bitmap','materialname','ambient','diffuse','specular','shininess','render','shadow','alpha','transparencyhint','inheritcolor','selfillumcolor')


def require(value,message):
    if not value:raise ValueError(message)


def output_location(output,artifact_root,protected):
    output,artifact_root=Path(output).resolve(),Path(artifact_root).resolve()
    require(output!=artifact_root and output.is_relative_to(artifact_root),'Fresh output must be inside the declared artifact root')
    require(not output.exists(),'Refusing an existing target/output directory')
    for path in protected:
        path=Path(path).resolve()
        require(not output.is_relative_to(path) and not path.is_relative_to(output),'Output overlaps frozen target/source inputs')
    return output


def mesh_data(text):
    supers=re.findall(r'(?mi)^setsupermodel\s+\S+\s+(\S+)\s*$',text)
    require(len(supers)==1 and supers[0].lower()=='null','Inherited source equipment requires an explicit private bind/controller conversion')
    _,blocks,frames=rigid_frames(text)
    require(not re.search(r'(?mi)^newanim\s',text),'Rigid staging cannot retarget local animations')
    require(all(b[1].lower() in ('dummy','trimesh','danglymesh') for b in blocks.values()),'Skins, robes and emitters require separate conversion')
    result={}
    for name,b in blocks.items():
        vertices=np.asarray(arrays(b[3],'verts'),float)
        if not vertices.size:continue
        require(not re.search(r'(?mi)^\s*(weights|bonemap|boneweights)\s',b[3]),'Skin bind arrays cannot enter rigid staging')
        require(vertices.ndim==2 and vertices.shape[1]==3 and np.isfinite(vertices).all(),'Invalid rigid vertices')
        fields={key:re.findall(r'(?mi)^\s*'+key+r'\s+([^\n]+)',b[3]) for key in MATERIAL_FIELDS}
        result[name]={'block':b,'frame':frames[name],'vertices':vertices,'world':vertices@frames[name][:3,:3].T+frames[name][:3,3],
                      'type':b[1].lower(),'arrays':{key:arrays(b[3],key) for key in ARRAY_FIELDS},'fields':fields,
                      'normals':np.asarray(arrays(b[3],'normals'),float)}
    require(result,'No rigid source mesh')
    return result


def correspondence(original,calibration_source,fitted,transform):
    """Prove normalized same-source vertex identity before Armory --values."""
    source,cal,target=[mesh_data(text) for text in (original,calibration_source,fitted)]
    require(set(source)==set(cal)==set(target),'Same-source calibration mesh inventory differs')
    linear,translation=profile_affine(transform);proof=[]
    for name,row in source.items():
        a,b=cal[name],target[name]
        require(row['type']==a['type']==b['type'],'Same-source calibration mesh type differs')
        require(row['arrays']==a['arrays']==b['arrays'],'Same-source ordered faces/UVs/constraints differ')
        require(row['fields']==a['fields']==b['fields'],'Calibration material bindings changed')
        require(row['vertices'].shape==a['vertices'].shape==b['vertices'].shape,'Calibration vertex correspondence differs')
        require(np.allclose(a['frame'],np.eye(4),atol=1e-10,rtol=0) and np.allclose(b['frame'],np.eye(4),atol=1e-10,rtol=0),
                'Calibration meshes must be normalized into attachment-local coordinates')
        normalization=float(np.max(abs(a['vertices']-row['world'])))
        fit=float(np.max(abs(b['vertices']-(a['vertices']@linear.T+translation))))
        require(normalization<1e-8,'Calibration source is not the normalized same source equipment mesh')
        require(fit<=1e-5,'Fitted same-source mesh disagrees with the frozen affine profile')
        if row['normals'].size:
            expected=directions(row['normals'],np.linalg.inv(row['frame'][:3,:3]).T)
            require(a['normals'].shape==expected.shape and np.max(abs(a['normals']-expected))<1e-8,'Calibration source authored normals changed')
            expected_fit=directions(expected,np.linalg.inv(linear).T)
            require(b['normals'].shape==expected_fit.shape and np.max(abs(b['normals']-expected_fit))<1e-8,'Calibration fitted authored normals changed')
        proof.append({'mesh':name,'vertices':len(row['vertices']),'sourceNormalizationMaxError':normalization,
                      'fitProfileMaxError':fit,'orderedFacesUvsAndBindingsExact':True})
    return proof


def validate_profile_ini(text,source_name,transform):
    cfg=configparser.ConfigParser(interpolation=None);cfg.read_string(text)
    require(set(cfg.sections())=={'Global','s0'} and set(cfg['Global'])=={'ntransforms'} and cfg['Global']['ntransforms']=='1','Single exact profile transform required')
    require(set(cfg['s0'])=={'match','substitute','scale','rotate','translate'},'Unsupported profile INI fields')
    require(cfg['s0']['match']==source_name and cfg['s0']['substitute']=='*','Calibration INI must preserve the exact source model')
    for field,default in (('scale',None),('rotate',[0,0,0]),('translate',None)):
        token=cfg['s0'][field].strip();require(token.startswith('(') and token.endswith(')'),'Invalid profile vector')
        values=[float(v.strip()) for v in token[1:-1].split(',')]
        require(values==transform.get(field,default),'Frozen INI differs from declared profile '+field)
    profile_affine(transform)


def armory_ini(entries):
    text='[Global]\nntransforms='+str(len(entries))+'\n'
    for index,(name,transform) in enumerate(entries):
        text+=f'[s{index}]\nmatch={name}\nsubstitute=*\n'
        for key,default in (('scale',None),('rotate',[0,0,0]),('translate',None)):
            text+=key+'=('+','.join(format(float(v),'.17g') for v in transform.get(key,default))+')\n'
    return text


def scale_actor_proof(working,runtime,data,joint):
    work,run=mesh_data(working),mesh_data(runtime);require(set(work)==set(run),'Runtime mesh inventory changed')
    factor=float(data['rig']['runtimeScale']);wf=contract.frame(data,joint,'working');rf=contract.frame(data,joint,'runtime');errors=[]
    for name,a in work.items():
        b=run[name];require(a['arrays']==b['arrays'] and a['fields']==b['fields'],'Runtime topology/UV/material binding changed')
        wp=a['world']@wf[:3,:3].T+wf[:3,3];rp=b['world']@rf[:3,:3].T+rf[:3,3]
        require(wp.shape==rp.shape,'Runtime ordered vertex inventory changed')
        error=float(np.max(abs(rp-factor*wp)));require(error<1e-8,'Runtime stature conversion applied incorrectly or twice')
        if a['normals'].size:
            wn=directions(a['normals'],wf[:3,:3]@np.linalg.inv(a['frame'][:3,:3]).T)
            rn=directions(b['normals'],rf[:3,:3]@np.linalg.inv(b['frame'][:3,:3]).T)
            require(wn.shape==rn.shape and np.max(abs(wn-rn))<1e-8,'Runtime authored normals changed')
        errors.append(error)
    return {'attachmentJoint':joint,'actorWorldMaximumScaleError':max(errors),'runtimeScale':factor,'statureApplications':1}


def production_gates(data,profile,mode):
    require(mode in ('diagnostic','production'),'Explicit diagnostic/production mode required')
    if mode=='production':
        require(data['rig'].get('pilotAccepted') is True and data['rig'].get('frozen') is True,'Production requires a frozen accepted rig pilot')
        require(profile.get('fitMode')=='reviewed-regional' and profile.get('profileAccepted') is True,'Production requires reviewed accepted equipment calibration')
        require(profile.get('collisionReviewsAccepted') is True,'Production requires accepted collision reviews')
        require(profile.get('materialBindingsAccepted') is True,'Production requires accepted material binding reviews')


def prepare(job_path,target_path,output,*,artifact_root=None):
    data=contract.load(target_path);job=json.loads(Path(job_path).read_text(encoding='utf-8-sig'))
    require(job.get('schemaVersion')==1 and job.get('kind')=='target-rigid-equipment-job','Explicit target rigid equipment job required')
    contract.verify_binding(job,target_path,data,'working')
    require(job.get('localSpace')=='attachment-local' and job.get('statureApplications')==0,'Working attachment-local input with no stature conversion required')
    require(data['identity']['prefix']!='pmh0','This isolated target path cannot stage Human outputs')
    frozen={}
    def pin(reference):
        path=Path(reference['path']).resolve();require(path.is_file() and digest(path)==reference['sha256'],'Frozen input hash changed: '+str(path))
        frozen[str(path)]=reference['sha256'];return path
    frozen[str(Path(target_path).resolve())]=digest(target_path);frozen[str(Path(job_path).resolve())]=digest(job_path)
    inventory_path=pin(job['sourceInventory']);inventory=json.loads(inventory_path.read_text(encoding='utf-8-sig'))
    require(inventory.get('kind')=='installed-target-equipment-inputs' and inventory.get('overridesDisabled') is True,'Frozen installed equipment ownership inventory required')
    source_prefix=data['equipment']['sourcePrefix'];require(source_prefix==inventory['sourcePrefix'] and source_prefix=='pmh0','Declared source ownership differs from installed stock')
    toolchain_path=pin(job['sharedToolchain']);migration_path=pin(job['toolMigration'])
    shared=shared_toolchain.load(toolchain_path,migration_path)
    armory=pin(job['armory']);require(armory==Path(shared['tools']['armory']['path']).resolve() and
        digest(armory)==shared['tools']['armory']['sha256']==ARMORY_SHA256,'Exact shared pinned NWNArmory v1.3.4 executable required')
    table=pin(job['attachmentTable']);attachment_rows=table_rows(table)
    connections={row['mdlname'].lower():row['nodename'].lower() for row in attachment_rows.values()}
    collision=pin(job['collisionManifest']);collision_data=json.loads(collision.read_text(encoding='utf-8-sig'))
    require(collision_data.get('kind')=='target-rigid-equipment-collision-set','Explicit target collision set required')
    contract.verify_binding(collision_data,target_path,data,'runtime')
    if job['mode']=='production':
        require(collision_data.get('complete') is True and collision_data.get('collisionReviewsAccepted') is True,
                'Production requires a complete reviewed collision inventory')
    occupied={name.lower() for name in collision_data['resourceHashes']}
    occupied.update(model+ext for model in data['models'].values() for ext in ('.mdl','.plt','.mtr'))
    models={row['resource']:row for row in inventory['models']};dependencies={row['name']:row for row in inventory['dependencies']}
    selected=[];names=set();profile_cache={};mode=job['mode'];require(job.get('entries'),'Empty equipment selection')
    protected=[inventory_path.parent,Path(target_path).resolve().parent]
    for entry in job['entries']:
        name=entry['sourceResource'];require(name in models,'Missing or undeclared installed equipment source')
        row=models[name];part=row['part']
        require(row['category']=='rigid-armor' and not row['requiresSkinBindPath'] and row['localAnimationCount']==0,'Shared held/skin/robe/animated resources cannot enter target rigid staging')
        require(re.fullmatch(re.escape(source_prefix)+'_'+re.escape(part)+r'\d{3}\.mdl',name),'Source ownership name differs')
        require(not any(f['model']==name for f in inventory['missingDependencies']),'Unresolved stock material dependency blocks staging')
        target_name=data['identity']['prefix']+name[len(source_prefix):];require(len(Path(target_name).stem)<=16,'Target resref exceeds native limit')
        require(target_name not in names and target_name not in occupied,'Target resource collision or duplicate selection');names.add(target_name)
        source=pin({'path':row['asciiPath'],'sha256':row['asciiSha256']});pin({'path':row['rawPath'],'sha256':row['sha256']});protected.extend((source.parent,Path(row['rawPath']).resolve().parent))
        profile_path=pin(entry['profile'])
        if str(profile_path) not in profile_cache:
            profile=json.loads(profile_path.read_text(encoding='utf-8-sig'))
            require(profile.get('schemaVersion')==1 and profile.get('kind')=='target-rigid-equipment-profile','Explicit target calibration profile required')
            contract.verify_binding(profile,target_path,data,'working')
            require(profile.get('localSpace')=='attachment-local' and profile.get('statureApplications')==0,'Profile is already scaled or in the wrong coordinate space')
            require(profile['sourceInventorySha256']==digest(inventory_path) and profile['armorySha256']==ARMORY_SHA256 and
                    profile['sharedToolchainSha256']==digest(toolchain_path) and profile['toolMigrationSha256']==digest(migration_path),
                    'Profile source/shared toolchain ownership differs')
            original_row=models.get(profile['calibrationResource']);require(original_row and original_row['part']==profile['part'],'Calibration must use an inventoried same-region source equipment mesh')
            original=pin({'path':original_row['asciiPath'],'sha256':original_row['asciiSha256']})
            cs,ct,ini=[pin(profile[key]) for key in ('calibrationSource','calibrationFitted','ini')]
            require(cs.stem==ct.stem==Path(profile['calibrationResource']).stem,'Calibration files must retain exact source model names')
            validation=correspondence(original.read_text(encoding='ascii'),cs.read_text(encoding='ascii'),ct.read_text(encoding='ascii'),profile['transform'])
            validate_profile_ini(ini.read_text(encoding='ascii'),cs.stem,profile['transform'])
            if profile.get('fitMode')=='diagnostic-self':
                a,t=profile_affine(profile['transform']);require(np.array_equal(a,np.eye(3)) and np.array_equal(t,np.zeros(3)) and digest(cs)==digest(ct),'Diagnostic self-calibration must be literal identity')
            production_gates(data,profile,mode)
            profile_cache[str(profile_path)]={'data':profile,'validation':validation,'source':cs,'fitted':ct,'path':profile_path}
        record=profile_cache[str(profile_path)];profile=record['data']
        require(profile['part']==part and profile['attachmentJoint']==connections.get(part),'Profile attachment does not match the frozen installed capart mapping')
        contract.frame(data,profile['attachmentJoint'],'working');contract.frame(data,profile['attachmentJoint'],'runtime')
        required=set(row['renderTextureDependencies']);bindings=entry.get('materialBindings',[]);externals=entry.get('externalDependencies',[])
        pending=list(required);visited=set()
        while pending:
            dependency=pending.pop()
            if dependency in visited:continue
            visited.add(dependency);require(dependency in dependencies,'Missing frozen material dependency: '+dependency)
            dep=dependencies[dependency];path=pin({'path':dep['rawPath'],'sha256':dep['sha256']})
            if path.suffix.lower()=='.mtr':
                for texture in re.findall(r'(?mi)^\s*texture\d+\s+(\S+)',path.read_text()):
                    if texture.lower() in ('null','****'):continue
                    matches={texture.lower()+ext for ext in ('.dds','.tga','.plt','.mtr') if texture.lower()+ext in dependencies}
                    require(matches,'Missing frozen transitive MTR texture dependency')
                    required.update(matches);pending.extend(matches-visited)
        declared={b['sourceResource'] for b in bindings}|set(externals)
        require(required and required==declared,'Missing or extra source material dependency declarations')
        material_rows=[]
        for dependency in sorted(required):
            require(dependency in dependencies,'Missing frozen material dependency: '+dependency)
            dep=dependencies[dependency];path=pin({'path':dep['rawPath'],'sha256':dep['sha256']})
            material_rows.append({'resource':dependency,'path':path,'sha256':dep['sha256']})
        for binding in bindings:
            require(binding['policy']=='exact-native-model-plt' and binding['sourceResource'].endswith('.plt'),'Only explicit native model PLT transport is supported')
            destination=Path(target_name).stem+'.plt';require(binding['targetResource']==destination and destination not in occupied and destination not in names,'Material resource collision or undeclared target ownership');names.add(destination)
            source_dep=dependencies[binding['sourceResource']];read_stock_plt(Path(source_dep['rawPath']).read_bytes())
            if mode=='production':require(binding.get('bindingReviewAccepted') is True,'Native PLT binding is still unreviewed')
        selected.append({'source':source,'sourceRow':row,'target':target_name,'profile':record,'bindings':bindings,'dependencies':material_rows,'externalDependencies':externals})
    output=output_location(output,artifact_root or ARTIFACT_ROOT,protected);output.mkdir(parents=True)
    work=output/'quarantine';work.mkdir();source_dir=work/'source';raw=work/'working-raw';corrected=work/'working-corrected';runtime_raw=work/'runtime-raw';runtime_corrected=work/'runtime-corrected'
    for path in (source_dir,raw,corrected,runtime_raw,runtime_corrected):path.mkdir()
    def run(arguments,label):
        result=subprocess.run([str(armory),*map(str,arguments)],capture_output=True,text=True)
        (work/(label+'.log')).write_text(result.stdout+result.stderr)
        require(result.returncode==0,'Armory failed; partial batch adoption blocked: '+label)
        return result
    try:
        version=run(['--version'],'version');require(version.stdout.strip()=='nwnarmory 1.3.4','Pinned Armory version differs')
        for index,record in enumerate(profile_cache.values()):
            result=run(['--values',record['source'],record['fitted']],f'calibration-{index}')
            residuals=[float(v) for v in re.findall(r'max_residual\s*[=:]\s*([\d.eE+\-]+)',result.stdout)]
            require(residuals and all(np.isfinite(v) and v<=1e-5 for v in residuals),'Actual same-source calibration residual failed')
            record['actualFitResiduals']=residuals
        for row in selected:shutil.copyfile(row['source'],source_dir/row['source'].name)
        ini=work/'working.ini';ini.write_text(armory_ini([(r['source'].stem,r['profile']['data']['transform']) for r in selected]),encoding='ascii')
        run([ini,source_dir,raw],'working-batch');expected={r['source'].name for r in selected}
        require({p.name for p in raw.iterdir()}==expected,'Armory partial or unexpected working batch outputs')
        for row in selected:
            path=corrected/row['target'];shutil.copyfile(raw/row['source'].name,path)
            row['workingProof']=correct_rigid(row['source'],path,row['profile']['data']['transform'])
            text=path.read_text(encoding='ascii');text=re.sub(r'(?i)\b'+re.escape(row['source'].stem)+r'\b',Path(row['target']).stem,text)
            for binding in row['bindings']:
                old=Path(binding['sourceResource']).stem;new=Path(binding['targetResource']).stem
                text=re.sub(r'(?mi)^(\s*bitmap\s+)'+re.escape(old)+r'\s*$',lambda m:m[1]+new,text)
            path.write_text(text,encoding='ascii');row['workingPath']=path
        factor=float(data['rig']['runtimeScale']);runtime_transform={'scale':[factor]*3,'rotate':[0,0,0],'translate':[0,0,0]}
        runtime_ini=work/'runtime.ini';runtime_ini.write_text(armory_ini([(Path(r['target']).stem,runtime_transform) for r in selected]),encoding='ascii')
        run([runtime_ini,corrected,runtime_raw],'runtime-batch');require({p.name for p in runtime_raw.iterdir()}=={r['target'] for r in selected},'Armory partial or unexpected runtime batch outputs')
        for row in selected:
            path=runtime_corrected/row['target'];shutil.copyfile(runtime_raw/row['target'],path)
            row['runtimeProof']=correct_rigid(row['workingPath'],path,runtime_transform);row['runtimePath']=path
            row['actorWorldProof']=scale_actor_proof(row['workingPath'].read_text(),path.read_text(),data,row['profile']['data']['attachmentJoint'])
        for path,value in frozen.items():require(digest(Path(path))==value,'Frozen input changed before adoption: '+path)
        for space in ('working','runtime'):
            (output/space/'ascii').mkdir(parents=True);(output/space/'resources').mkdir()
        resource_rows=[]
        for row in selected:
            for space,path in (('working',row['workingPath']),('runtime',row['runtimePath'])):
                destination=output/space/'ascii'/row['target'];shutil.copyfile(path,destination)
                require(digest(destination)==digest(path),'Prepared model copy changed')
            for binding in row['bindings']:
                dep=dependencies[binding['sourceResource']]
                for space in ('working','runtime'):
                    destination=output/space/'resources'/binding['targetResource'];shutil.copyfile(dep['rawPath'],destination)
                    require(digest(destination)==dep['sha256'],'Native material copy changed')
            resource_rows.append({'sourceResource':row['sourceRow']['resource'],'sourceAsciiSha256':row['sourceRow']['asciiSha256'],'targetResource':row['target'],
                'part':row['sourceRow']['part'],'profilePath':str(row['profile']['path']),'profileSha256':digest(row['profile']['path']),
                'workingAsciiSha256':digest(output/'working/ascii'/row['target']),'runtimeAsciiSha256':digest(output/'runtime/ascii'/row['target']),
                'materialBindings':row['bindings'],'externalDependencies':row['externalDependencies'],'workingCorrection':row['workingProof'],
                'runtimeCorrection':row['runtimeProof'],'actorWorldProof':row['actorWorldProof']})
        manifest={p.name:digest(p) for d in (output/'runtime/ascii',output/'runtime/resources') for p in d.iterdir()}
        receipt={'schemaVersion':1,'kind':'target-rigid-equipment-preparation',**contract.binding(target_path,data,'runtime'),'workingTargetBinding':contract.binding(target_path,data,'working'),
                 'mode':mode,'complete':True,'productionAccepted':mode=='production','clientAccepted':False,'nativeCompiled':False,
                 'statureApplications':1,'rigPilotAccepted':data['rig'].get('pilotAccepted',False),'frozenInputs':frozen,
                 'equipmentProfilesAccepted':mode=='production','collisionReviewsAccepted':mode=='production',
                 'nativeExportAccepted':False,'materialBindingsAccepted':mode=='production',
                 'collisionInventoryComplete':collision_data.get('complete',False),
                 'resources':resource_rows,'runtimeCandidateHashes':manifest,'profiles':[{'path':str(r['path']),'sameSourceCorrespondence':r['validation'],'actualFitResiduals':r['actualFitResiduals'],'profileAccepted':r['data'].get('profileAccepted',False)} for r in profile_cache.values()],
                 'sharedToolchain':{'path':str(toolchain_path),'sha256':digest(toolchain_path)},
                 'toolMigration':{'path':str(migration_path),'sha256':digest(migration_path)},
                 'sharedToolchainHelperSha256':digest(Path(shared_toolchain.__file__)),
                 'armorySha256':ARMORY_SHA256,'armoryPath':str(armory),'workingIniSha256':digest(ini),'runtimeIniSha256':digest(runtime_ini),
                 'helperSha256':digest(Path(__file__)),'rigidHelperSha256':digest(Path(__file__).with_name('armory_rigid.py')),
                 'originalSourceInventoryModified':False,'installedOrPublishedResourcesWritten':False,
                 'limitations':['Complete means the selected preparation batch completed; it does not approve full equipment coverage or packaging.',
                     'Diagnostic self-calibration proves staging only and never accepts a Troll body fit.',
                     'Skins, robes, cloaks and global helmets/weapons/shields use separate ownership and validation paths.']}
        save_json(output/'preparation.json',receipt)
        return output/'preparation.json'
    except Exception as exc:
        save_json(output/'terminal-failure.json',{'schemaVersion':1,'kind':'target-rigid-equipment-preparation-failure',**contract.binding(target_path,data,'working'),
            'complete':False,'productionAccepted':False,'clientAccepted':False,'partialBatchAdoptionBlocked':True,'failure':str(exc),'frozenInputs':frozen})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('job','target-contract','output'):parser.add_argument('--'+field,type=Path,required=True)
    args=parser.parse_args();path=prepare(args.job,args.target_contract,args.output)
    print(json.dumps({'receipt':str(path.resolve()),'productionAccepted':json.loads(path.read_text())['productionAccepted']}))
