"""Opt-in working pelvis diagnostic PLT/underwear/neutral-cap staging.

The distinct source/stage/composition kinds never grant canonical body ownership.
ASCII preserves ordered P/N/nativeUV. It omits source T/W; native compiler
tangent reconstruction must be independently compared, not called lossless T.
"""
import argparse,copy,json,re,shutil,struct,tempfile
from pathlib import Path
import numpy as np
from PIL import Image
import shared_toolchain
import target_contract as contract
import target_diagnostic_lineage as diagnostic
import target_diagnostic_uv_basis as basispolicy
import target_diagnostic_uv_material_lineage as lineage
from stage_stock_part import geometry,write_ascii
from target_part_stage import material_inputs

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'


def cap_pixels(descriptor):
    contract.require(descriptor.get('alphaMode')=='OPAQUE' and descriptor.get('doubleSided') is False
                     and descriptor.get('extras',{}).get('diagnosticOnly') is True
                     and descriptor.get('extras',{}).get('materialAccepted') is False
                     and set(descriptor)=={'name','pbrMetallicRoughness','alphaMode','doubleSided','extras'}
                     and descriptor['pbrMetallicRoughness']=={'baseColorFactor':[.36,.36,.36,1.],
                                                           'metallicFactor':0.,'roughnessFactor':1.},
                     'Exact literal unowned neutral gray cap descriptor required; skin/maps/recolor rejected')
    return np.full((2048,2048,3),92,dtype=np.uint8)


def write_model(path,model,groups):
    header=[f'newmodel {model}',f'setsupermodel {model} NULL','classification CHARACTER',
            'setanimationscale 1',f'beginmodelgeom {model}',f'node dummy {model}','  parent NULL','endnode']
    rows={}
    with tempfile.TemporaryDirectory() as temporary:
        for index,(name,_) in enumerate(lineage.GROUPS):
            group=groups[name];temp=Path(temporary)/'part.mdl'
            proof=write_ascii(temp,model,group['positions'],group['uvNative'],group['normals'])
            mesh=model+'p'+str(index);material=model+('f' if name=='garment' else 'c' if name.startswith('cap-') else '')
            block=re.search(r'(?ms)^node trimesh \S+\n.*?^endnode',temp.read_text(encoding='ascii'))[0]
            block=re.sub(r'^node trimesh \S+',f'node trimesh {mesh}',block)
            block=re.sub(r'(?m)^  (bitmap|materialname) \S+',lambda m:'  '+m[1]+' '+material,block)
            header.append(block);rows[mesh]={'role':name,'material':material,'primitiveIds':group['primitiveIds'],
                                          **proof,'authoredSourceTangentsSerialized':False}
    header.extend([f'endmodelgeom {model}',f'donemodel {model}'])
    path.write_text('\n'.join(header)+'\n',encoding='ascii');return rows


def write_materials(resources,model,doc,blob,ao):
    pixels,proof=material_inputs(doc,blob,{0:'skin',2:'garment'},'pelvis',ao)
    for role,item in pixels.items():
        mat=model+('f' if role=='garment' else '')
        Image.fromarray(item['normal']).save(resources/(mat+'n.tga'))
        Image.fromarray(np.repeat(item['roughness'][...,None],3,axis=2)).save(resources/(mat+'r.tga'))
        text='renderhint NormalTangents\ntexture1 '+mat+'n\ntexture3 '+mat+'r\n'
        text+='parameter float Roughness 0\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n'
        if role=='skin':
            plt=np.stack((item['intensity'],np.zeros_like(item['intensity'])),axis=2)[::-1].copy()
            (resources/(mat+'.plt')).write_bytes(b'PLT V1  '+struct.pack('<IIII',10,0,2048,2048)+plt.tobytes())
            decoded=np.frombuffer((resources/(mat+'.plt')).read_bytes()[24:],'u1').reshape(2048,2048,2)[::-1]
            contract.require(np.array_equal(decoded[:,:,0],item['intensity']) and not decoded[:,:,1].any(),'PLT pixel/layer differs')
        else:
            Image.fromarray(item['color']).save(resources/(mat+'.tga'));text+='texture0 '+mat+'\n'
        (resources/(mat+'.mtr')).write_text(text,encoding='ascii')
        for suffix,key in [('n','normal'),('r','roughness')]:
            actual=np.asarray(Image.open(resources/(mat+suffix+'.tga')).convert('RGB'))
            expected=item[key] if key=='normal' else np.repeat(item[key][...,None],3,axis=2)
            contract.require(np.array_equal(actual,expected),'Original normal/ORM-green material transport differs')
    cap=cap_pixels(doc['materials'][1]);mat=model+'c'
    Image.fromarray(cap).save(resources/(mat+'.tga'))
    (resources/(mat+'.mtr')).write_text('renderhint NormalTangents\ntexture0 '+mat+
          '\nparameter float Roughness 1\nparameter float Specularity 0.04\nparameter float Metallicness 0\n',encoding='ascii')
    proof.append({'material':1,'role':'unowned-neutral-diagnostic-cap','sourceBindings':doc['materials'][1],
                  'fixedDiffuseBytes':92,'normalTextureOmitted':True,'pltOmitted':True,
                  'capOwnershipAccepted':False,'method':'Explicit diagnostic neutral encoding: byte92 from rounded0.36*255; GLTF factor is linear while native texture0 may be sRGB. Native visual equivalence is unproven; no authored cap atlas/map exists.'})
    return proof


def stage(config_path,output):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text())
    allowed={'schemaVersion','kind','diagnosticOnly','coordinateSpace','part','newCornerShadingPolicy',
             'targetContract','sourceReceipt','sourceCandidate','independentDecodedAudit','independentFootprintAudit',
             'stageReview','sharedToolchain','migrationReceipt','aoStrength','materialRoles','capMode','notes'}
    contract.require(set(config)<=allowed and config.get('schemaVersion')==2 and config.get('kind')==lineage.STAGE_KIND
                     and config.get('diagnosticOnly') is True and config.get('coordinateSpace')=='working'
                     and config.get('part')=='pelvis' and config.get('newCornerShadingPolicy')==basispolicy.POLICY_ID
                     and config.get('capMode')==lineage.CAP_MODE and config.get('materialRoles')==lineage.MATERIAL_ROLES
                     and config.get('aoStrength') in (0,.15,.35),'Explicit opt-in working diagnostic material stage required')
    diagnostic.no_acceptance(config);inputs={str(config_path):contract.sha(config_path)}
    target_path=diagnostic.pin(config['targetContract'],inputs);target=contract.load(target_path)
    shared_toolchain.load(diagnostic.pin(config['sharedToolchain'],inputs),diagnostic.pin(config['migrationReceipt'],inputs))
    source_receipt=diagnostic.pin(config['sourceReceipt'],inputs);candidate=diagnostic.pin(config['sourceCandidate'],inputs)
    review=diagnostic.load_item(config['stageReview'],inputs)
    lineage.stage_review(review,config['sourceReceipt'],config['sourceCandidate'])
    for item in review['evidence']:diagnostic.pin(item,inputs)
    parent=lineage.verify_receipt(source_receipt,target_path,target,config['independentDecodedAudit'],config['independentFootprintAudit'])
    contract.require(parent['candidate']==candidate,'Stage source differs from reviewed lineage')
    inputs.update(parent['inputs']);cap_pixels(parent['doc']['materials'][1])
    for name in ('target_diagnostic_uv_material_stage.py','target_diagnostic_uv_material_lineage.py','target_diagnostic_uv_basis.py',
                 'target_diagnostic_lineage.py','target_diagnostic_material_lineage.py','target_contract.py',
                 'target_part_stage.py','stage_stock_part.py','place_purposebuilt_pelvis.py','shared_toolchain.py'):
        path=Path(__file__).with_name(name);inputs[str(path)]=contract.sha(path)
    p=np.concatenate([group['positions'] for group in parent['groups'].values()]);g=geometry(p)
    contract.require(not g['degenerateTriangles'] and not g['coincidentTriangles'],'Degenerate/coincident diagnostic geometry cannot be staged')
    output=Path(output).resolve();contract.require(ARTIFACT_ROOT.resolve() in output.parents and not output.exists(),'Fresh diagnostic stage required')
    for path,sha in inputs.items():diagnostic.pin({'path':path,'sha256':sha},{})
    (output/'ascii').mkdir(parents=True);(output/'resources').mkdir()
    model=contract.model(target,'pelvis');ascii_path=output/'ascii'/(model+'.mdl')
    meshes=write_model(ascii_path,model,parent['groups'])
    proof=write_materials(output/'resources',model,parent['doc'],parent['binary'],config['aoStrength'])
    materials={p.name:contract.sha(p) for p in sorted((output/'resources').iterdir())}
    expected={model+'.mtr',model+'.plt',model+'n.tga',model+'r.tga',
              model+'f.mtr',model+'f.tga',model+'fn.tga',model+'fr.tga',model+'c.mtr',model+'c.tga'}
    contract.require(set(materials)==expected and all(len(Path(name).stem)<=16 for name in materials),'Exact diagnostic role resource inventory required')
    receipt={'schemaVersion':2,'kind':lineage.STAGE_KIND,**contract.binding(target_path,target,'working'),
             'part':'pelvis','joint':'pelvis_g','model':model,'newCornerShadingPolicy':basispolicy.POLICY_ID,
             'sourceReceipt':config['sourceReceipt'],'sourceCandidate':config['sourceCandidate'],'stageReview':config['stageReview'],
             'independentDecodedAudit':config['independentDecodedAudit'],'independentFootprintAudit':config['independentFootprintAudit'],
             'statureApplications':0,'aoStrength':config['aoStrength'],'untreatedParentSha256':contract.sha(candidate),
             'materialRoles':lineage.MATERIAL_ROLES,'capMode':lineage.CAP_MODE,'meshes':meshes,
             'asciiModel':str(ascii_path),'asciiModelSha256':contract.sha(ascii_path),
             'materialResourceHashes':materials,'materialProof':proof,'geometry':g,'frozenInputs':inputs,
             'diagnosticOnly':True,'closedExteriorClaim':False,'geometryAccepted':False,'materialAccepted':False,
             'capOwnershipAccepted':False,'nativeAccepted':False,'clientAccepted':False,'productionAccepted':False,
             'asciiAuthoredTangentsSerialized':False,'nativeCompilerReconstructsTangents':True,
             'limitation':'Diagnostic geometry/material transport only; unownedcaps/source topology/native tangent comparison/shader/client remain pending.'}
    diagnostic.no_acceptance(receipt)
    path=output/'diagnostic-stage.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    composition={'schemaVersion':2,'kind':lineage.COMPOSITION_KIND,**contract.binding(target_path,target,'working'),
       'modelParts':{model+'.mdl':'pelvis'},'asciiModelHashes':{model+'.mdl':contract.sha(ascii_path)},
       'materialResourceHashes':materials,'sourceStage':{'path':str(path),'sha256':contract.sha(path)},
       'frozenInputs':inputs,'diagnosticOnly':True,'closedExteriorClaim':False,
       'materialAccepted':False,'capOwnershipAccepted':False,'nativeAccepted':False,'clientAccepted':False,'productionAccepted':False}
    (output/'conversion.json').write_text(json.dumps(composition,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(__file__,output/'executed-helper.py')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();print(stage(args.config,args.output))
