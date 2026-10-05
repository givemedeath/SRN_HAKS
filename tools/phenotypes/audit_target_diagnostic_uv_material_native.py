"""Separate read-only diagnostic pelvis source/ASCII/native/material audit.

No canonical lineage coercion or cap ownership. The source authored tangent
bank and UV-derived new-corner policy are compared with compiler-generated T/W;
ASCII does not carry T/W, so preservation of these native arrays is not claimed.
"""
import argparse,json,re,shutil,struct
from pathlib import Path
import numpy as np
from PIL import Image
import target_contract as contract
import target_diagnostic_lineage as diagnostic
import target_diagnostic_uv_basis as basispolicy
import target_diagnostic_uv_material_lineage as lineage
from audit_geometry import arrays
from audit_native_limb_shading import float32_ulp_distance,validate_transport
from audit_target_native_part import decode,tangent_proof,LAYOUT_COMMIT,LAYOUT_PINS
from target_body_inventory import flat_hashes
from target_part_stage import material_inputs
from target_diagnostic_uv_material_stage import cap_pixels


def ascii_meshes(text,model):
    nodes=re.findall(r'(?ms)^node (\S+) (\S+)\n(.*?)^endnode\s*$',text)
    contract.require(len(nodes)==5 and nodes[0][:2]==('dummy',model)
                     and re.search(r'(?m)^\s*parent NULL\s*$',nodes[0][2])
                     and re.search(r'(?m)^setsupermodel '+re.escape(model)+r' NULL$',text)
                     and re.search(r'(?m)^setanimationscale 1$',text)
                     and re.search(r'(?m)^classification CHARACTER$',text)
                     and 'newanim ' not in text, 'Four declared detached diagnostic ASCII meshes required')
    result={};expected={model+'p'+str(i):name for i,(name,_) in enumerate(lineage.GROUPS)}
    for kind,name,body in nodes[1:]:
        contract.require(kind=='trimesh' and name in expected and name not in result,
                         'Unsupported or duplicate diagnostic ASCII mesh')
        role=expected[name];material=model+('f' if role=='garment' else 'c' if role.startswith('cap-') else '')
        for pattern in ['parent '+re.escape(model),'position 0 0 0','orientation 0 0 0 0',
                        'bitmap '+re.escape(material),'materialname '+re.escape(material),'render 1','shadow 1']:
            contract.require(re.search(r'(?m)^\s*'+pattern+r'\s*$',body),'Diagnostic ASCII identity/material differs')
        contract.require(not re.search(r'(?m)^\s*(?:scale|positionkey|orientationkey|scalekey|tangents)\b',body),
                         'Unexpected diagnostic ASCII transform or authored tangent serialization')
        p,n,uv,f=[np.asarray(arrays(body,key)) for key in ['verts','normals','tverts','faces']]
        contract.require(p.ndim==2 and p.shape[1]==3 and n.shape==p.shape and uv.ndim==2 and uv.shape[1]==3
                         and f.ndim==2 and f.shape[1]==8 and all(np.isfinite(v).all() for v in [p,n,uv,f])
                         and np.array_equal(f,f.astype(int)), 'Malformed diagnostic ASCII corner arrays')
        f=f.astype(int);contract.require(f.size and f[:,:3].min()>=0 and f[:,:3].max()<len(p)
             and f[:,4:7].min()>=0 and f[:,4:7].max()<len(uv),'Diagnostic ASCII index exceeds attributes')
        result[name]={'role':role,'material':material,'corners':{'position':p[f[:,:3]],
                              'normal':n[f[:,:3]],'uv':uv[f[:,4:7],:2]}}
    contract.require(set(result)==set(expected),'Diagnostic ASCII mesh inventory differs')
    return result


def source_tangent_comparison(source,native):
    faces=native['faces'];t=native['tangent'][faces].astype(float);w=native['sign'][faces][...,0]
    old=source['tangents'];contract.require(old.shape==(*faces.shape,4),'Ordered source tangent provenance differs')
    lengths=np.linalg.norm(old[:,:,:3],axis=2)
    contract.require(np.isfinite(old).all() and lengths.min()>0 and np.isin(old[:,:,3],[-1,1]).all(),
                     'Finite source tangent/sign provenance required')
    cosine=np.einsum('tci,tci->tc',t,old[:,:,:3])/lengths
    return {'sourceAuthoredTangentsSerializedInAscii':False,'nativeCompilerReconstructsTangents':True,
      'corners':int(cosine.size),'sourceTangentLengthRange':[float(lengths.min()),float(lengths.max())],
      'sourceVsCompiledTangentCosines':{'minimum':float(cosine.min()),'p01':float(np.percentile(cosine,1)),
        'median':float(np.median(cosine)),'maximum':float(cosine.max()),'negativeCorners':int((cosine<0).sum())},
      'sameRawGltfSignCorners':int((w==old[:,:,3]).sum()),
      'sameVFlippedSignCorners':int((w==-old[:,:,3]).sum()),
      'maximumTangentComponentDifference':float(abs(t-old[:,:,:3]).max()),
      'sourceAuthoredTangentPreservationClaim':False,'nativeTangentVisualAccepted':False,
      'limitation':'Both sign comparisons are diagnostic. Raw GLTF V is reversed once for native UV; compiler smoothing/material/shader basis behavior still requires literal comparison.'}


def material_audit(folder,model,doc,blob,ao,compiled_hashes):
    pixels,transport=material_inputs(doc,blob,{0:'skin',2:'garment'},'pelvis',ao);proof={};files=[]
    for role,value in pixels.items():
        material=model+('f' if role=='garment' else '')
        mtr=folder/(material+'.mtr');normal=folder/(material+'n.tga');rough=folder/(material+'r.tga')
        lines=['renderhint NormalTangents','texture1 '+material+'n','texture3 '+material+'r',
               'parameter float Roughness 0','parameter float Specularity 0.04','parameter float Metallicness 0.001']
        if role=='garment':lines.append('texture0 '+material)
        contract.require(mtr.read_text(encoding='ascii').splitlines()==lines,'Diagnostic skin/cloth MTR policy changed')
        contract.require(np.array_equal(np.asarray(Image.open(normal).convert('RGB')),value['normal'])
              and np.array_equal(np.asarray(Image.open(rough).convert('RGB')),np.repeat(value['roughness'][...,None],3,axis=2)),
                         'Original normal-strength1 or ORM-green roughness pixels changed')
        diffuse=folder/(material+('.plt' if role=='skin' else '.tga'))
        if role=='skin':
            data=diffuse.read_bytes();contract.require(data[:8]==b'PLT V1  ' and struct.unpack_from('<II',data,16)==(2048,2048)
                          and len(data)==24+2048*2048*2,'Diagnostic skin PLT header differs')
            decoded=np.frombuffer(data[24:],'u1').reshape(2048,2048,2)[::-1]
            contract.require(np.array_equal(decoded[:,:,0],value['intensity']) and not decoded[:,:,1].any(),
                             'Diagnostic painted PLT luminance/AO/layer changed')
        else:contract.require(np.array_equal(np.asarray(Image.open(diffuse).convert('RGB')),value['color']),
                              'Fixed opaque underwear pixels changed')
        files.extend([mtr,normal,rough,diffuse]);proof[role]={'material':material,'normalPixelsExact':True,
          'roughnessPixelsExact':True,'diffusePixelsMatchDeclaredPolicy':True,'skinTexture0Omitted':role=='skin',
          'opaqueGarment':role=='garment','normalStrength':1,'aoStrength':ao,'materialAccepted':False}
    material=model+'c';mtr=folder/(material+'.mtr');diffuse=folder/(material+'.tga')
    contract.require(mtr.read_text(encoding='ascii').splitlines()==['renderhint NormalTangents','texture0 '+material,
                      'parameter float Roughness 1','parameter float Specularity 0.04','parameter float Metallicness 0'],
                     'Literal unowned cap diagnostic MTR policy differs')
    contract.require(np.array_equal(np.asarray(Image.open(diffuse).convert('RGB')),cap_pixels(doc['materials'][1])),
                     'Diagnostic neutral gray cap pixels changed')
    contract.require(not any((folder/(material+suffix)).exists() for suffix in ['.plt','n.tga','r.tga']),
                     'Unowned caps cannot inherit skin PLT or authored maps')
    files.extend([mtr,diffuse]);proof['unowned-neutral-diagnostic-cap']={'material':material,
      'fixedDiffuseBytes':92,'normalMapAbsent':True,'pltAbsent':True,'capOwnershipAccepted':False,
      'nativeVisualEquivalenceToLinearGltfFactorClaim':False,
      'limitation':'Byte92 texture0 is explicit diagnostic neutral encoding; source factor0.36 is linear and native texture may be sampled sRGB.'}
    contract.require({p.name:contract.sha(p) for p in files}==compiled_hashes,'Exact compile-time diagnostic material closure changed')
    return proof,transport,files


def audit(config_path,output):
    config_path=Path(config_path).resolve();config=json.loads(config_path.read_text())
    allowed={'schemaVersion','kind','diagnosticOnly','part','coordinateSpace','targetContract','stageReceipt',
      'composition','nativeReceipt','compiler','layoutDirectory','nativeUvMaximumUlps','notes'}
    contract.require(set(config)==allowed and config['schemaVersion']==2 and config['kind']==lineage.AUDIT_KIND
      and config['diagnosticOnly'] is True and config['part']=='pelvis' and config['coordinateSpace']=='working'
      and config['nativeUvMaximumUlps'] in (0,1), 'Explicit separate working diagnostic native audit required')
    diagnostic.no_acceptance(config);inputs={str(config_path):contract.sha(config_path)}
    target_path=diagnostic.pin(config['targetContract'],inputs);target=contract.load(target_path)
    stage_path=diagnostic.pin(config['stageReceipt'],inputs);stage=json.loads(stage_path.read_text())
    composition_path=diagnostic.pin(config['composition'],inputs);composition=json.loads(composition_path.read_text())
    contract.require(stage.get('schemaVersion')==2 and stage.get('kind')==lineage.STAGE_KIND
      and composition.get('schemaVersion')==2 and composition.get('kind')==lineage.COMPOSITION_KIND
      and stage.get('part')=='pelvis' and stage.get('capMode')==lineage.CAP_MODE
      and stage.get('materialRoles')==lineage.MATERIAL_ROLES and stage.get('statureApplications')==0
      and stage.get('newCornerShadingPolicy')==basispolicy.POLICY_ID
      and stage.get('asciiAuthoredTangentsSerialized') is False and stage.get('nativeCompilerReconstructsTangents') is True
      and stage.get('diagnosticOnly') is True and composition.get('diagnosticOnly') is True,
      'Exact diagnostic stage/composition ownership required')
    for row in [stage,composition]:
        diagnostic.no_acceptance(row);contract.verify_binding(row,target_path,target,'working')
        for path,sha in row['frozenInputs'].items():diagnostic.pin({'path':path,'sha256':sha},inputs)
    contract.require(lineage.same_pin(composition['sourceStage'],config['stageReceipt']),'Composition must select this exact diagnostic stage')
    source=diagnostic.pin(stage['sourceReceipt'],inputs);candidate=diagnostic.pin(stage['sourceCandidate'],inputs)
    parent=lineage.verify_receipt(source,target_path,target,stage['independentDecodedAudit'],stage['independentFootprintAudit'])
    contract.require(candidate==parent['candidate'],'Diagnostic native selected source differs');inputs.update(parent['inputs'])
    review=diagnostic.load_item(stage['stageReview'],inputs);lineage.stage_review(review,stage['sourceReceipt'],stage['sourceCandidate'])
    for item in review['evidence']:diagnostic.pin(item,inputs)
    model=contract.model(target,'pelvis');folder=composition_path.parent
    contract.require(stage['model']==model and composition['modelParts']=={model+'.mdl':'pelvis'}
      and stage['materialResourceHashes']==composition['materialResourceHashes'], 'Diagnostic model/material inventory changed')
    native_path=diagnostic.pin(config['nativeReceipt'],inputs);compiled=json.loads(native_path.read_text())
    compiler=diagnostic.pin(config['compiler'],inputs)
    contract.require(native_path.parent==folder and compiled.get('complete') is True and compiled.get('executionMode')=='compilemodel'
      and compiled.get('interactiveClientLaunched') is False and Path(compiled['client']).resolve()==compiler
      and compiled['clientSha256']==config['compiler']['sha256']
      and compiled['materialResourceHashes']==composition['materialResourceHashes'], 'Pinned completed noninteractive compile required')
    contract.require(flat_hashes(folder/'ascii')==composition['asciiModelHashes'],'Diagnostic compiled ASCII inventory changed')
    rows={row['name']:row for row in compiled['models']};actual=flat_hashes(folder/'resources')
    contract.require(len(rows)==len(compiled['models'])==1 and set(rows)==set(composition['modelParts'])
      and set(actual)==set(composition['materialResourceHashes'])|set(rows),'Exact diagnostic native resource closure required')
    for name,sha in composition['materialResourceHashes'].items():contract.require(actual[name]==sha,'Compiled material resource changed')
    row=rows[model+'.mdl'];native_model=folder/'resources'/(model+'.mdl')
    contract.require(row['sourceSha256']==composition['asciiModelHashes'][model+'.mdl'] and row['binarySha256']==actual[model+'.mdl']
      and native_model.stat().st_size==row['bytes'],'Native model/source association changed')
    ascii_path=diagnostic.pin({'path':stage['asciiModel'],'sha256':stage['asciiModelSha256']},inputs)
    contract.require(ascii_path==folder/'ascii'/(model+'.mdl') and contract.sha(ascii_path)==composition['asciiModelHashes'][model+'.mdl'],
                     'Diagnostic stage ASCII differs from compile')
    layout_paths=[diagnostic.pin({'path':str(Path(config['layoutDirectory'])/name),'sha256':sha},inputs) for name,sha in LAYOUT_PINS.items()]
    ascii_rows=ascii_meshes(ascii_path.read_text(encoding='ascii'),model);meshes,root=decode(native_model.read_bytes(),model,ascii_rows)
    proof={}
    for name,row in ascii_rows.items():
        group=parent['groups'][row['role']];selected={'position':group['positions'],'normal':group['normals'],'uv':group['uvNative']}
        native=meshes[name];corners={key:native[key][native['faces']] for key in selected}
        ae,be,exact=validate_transport(selected,row['corners'],corners,config['nativeUvMaximumUlps'])
        contract.require(native['layout']['textureSlots']==[row['material'],'','',row['material']] and native['layout']['shadowFlag']==1,
                         'Diagnostic native material/shadow binding changed')
        ulps=float32_ulp_distance(corners['uv'],selected['uv'])
        proof[name]={'role':row['role'],'nativeLayout':native['layout'],'sourceToAsciiOrderedCornerMaximumErrors':ae,
          'sourceToNativeOrderedCornerMaximumErrors':be,'nativeCornersExactSerializedSourceFloat32':exact,
          'nativeUvFloat32Rounding':{'maximumAllowedUlps':config['nativeUvMaximumUlps'],'maximumObservedUlps':int(ulps.max()),'nonexactValues':int((ulps>0).sum())},
          'actualNativeTangentArrays':tangent_proof(native),'sourceAuthoredAndNewUvBasisVsCompilerTangents':source_tangent_comparison(group,native)}
    materials,transport,material_files=material_audit(folder/'resources',model,parent['doc'],parent['binary'],stage['aoStrength'],compiled['materialResourceHashes'])
    for path in [native_model,*material_files]:inputs[str(path)]=contract.sha(path)
    body=parent['body'];p=np.concatenate([parent['groups'][name]['positions'] for name in ['skin','garment']])
    # Archive follows primitive0,3,4,5, whereas material groups are0,4 /3,5.
    serialized={key:[] for key in ['positions','normals','uvGltf','tangents']}
    for pi in [0,3,4,5]:
        owner=parent['groups']['skin' if pi in (0,4) else 'garment'];start=0 if pi in (0,3) else len(owner['positions'])-int((body['primitiveIds']==pi).sum())
        count=int((body['primitiveIds']==pi).sum())
        for key in serialized:serialized[key].append(owner[key][start:start+count])
    serialization={key:float(abs(np.concatenate(rows)-body[key]).max()) for key,rows in serialized.items()}
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh immutable diagnostic native audit required')
    (output/'layout').mkdir(parents=True)
    for path in layout_paths:shutil.copyfile(path,output/'layout'/path.name)
    (output/'helpers').mkdir()
    for name in ['audit_target_diagnostic_uv_material_native.py','target_diagnostic_uv_material_lineage.py','target_diagnostic_uv_material_stage.py',
       'audit_target_native_part.py','audit_native_limb_shading.py','audit_geometry.py','target_contract.py','target_part_stage.py','target_diagnostic_lineage.py']:
        path=Path(__file__).with_name(name);inputs[str(path)]=contract.sha(path);shutil.copyfile(path,output/'helpers'/name)
    receipt={'schemaVersion':2,'kind':lineage.AUDIT_KIND,**contract.binding(target_path,target,'working'),
      'part':'pelvis','model':model,'statureApplications':0,'sourceReceipt':stage['sourceReceipt'],'stageReceipt':config['stageReceipt'],
      'composition':config['composition'],'nativeReceipt':config['nativeReceipt'],'nativeModelSha256':contract.sha(native_model),
      'root':root,'meshes':proof,'materials':materials,'materialTransportPolicy':transport,
      'authoritativeBodyFloat64ToSerializedSourceMaximumErrors':serialization,
      'sourceAuthoredNormalTangentProvenancePreservedInSource':True,'asciiAuthoredTangentsSerialized':False,
      'binaryLayoutSourceCommit':LAYOUT_COMMIT,'frozenInputs':inputs,'attributeTransportVerified':True,'materialTransportVerified':True,
      'diagnosticOnly':True,'closedExteriorClaim':False,'geometryEdited':False,'materialPixelsEdited':False,'nativeCompilerExecuted':False,
      'geometryAccepted':False,'materialAccepted':False,'capOwnershipAccepted':False,'nativeAccepted':False,'nativeTangentVisualAccepted':False,
      'clientAccepted':False,'productionAccepted':False,
      'limitations':'Read-only ordered serialized-source P/N/UV and material transport. Separate unowned caps retain diagnostic encoding only. Original f64 body provenance remains separate. Native tangents are compiler-generated and compared, never called authored-T preservation; final shader/color/topology/cap/client remain pending.'}
    diagnostic.no_acceptance(receipt);result=output/'diagnostic-native-audit.json';result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.config,args.output);print(json.dumps({'receipt':str(result),'sha256':contract.sha(result)}))