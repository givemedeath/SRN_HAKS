"""Replay the original-source ankle RGB/detail recipe for diagnostic compiler inputs.

The callable is additive and dispatched explicitly by stage and native audit.
Retained output PNGs are comparisons,
not trusted treatment parents. Geometry, original maps and old receipts stay exact.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import target_contract as c
import source_skin_detail_contract as detail
import skin_lighting_atlas as atlas
from replay_stage_skin_intensity import frozen_inputs, source_receipt, row_pin, file_row
from place_purposebuilt_pelvis import read_glb, raw_corners, accessor, embedded_maps, BASIS
from mirror_stock_limb_part import detached_affine_bake, reflection_between_frames
from target_part_pipeline import pin, read_target


class Inputs:
    def __init__(self,*,material_execution=None,target_path=None,target=None):
        self.pins={};self.resolutions=[];self.material_execution=material_execution;self.target_path=target_path;self.target=target
    def row(self,row):
        p=row_pin(row); self.pins[str(p)]=c.sha(p);return p
    def load(self,row):
        p=self.row(row); return p,json.loads(p.read_text(encoding='utf-8'))
    def frozen(self,receipt,path):
        if self.material_execution is None:pins,resolutions=frozen_inputs(receipt,path)
        else:
            from phenotype_material_execution_adoption import resolve
            pins,resolutions=resolve(self.material_execution,module_file=__file__,path=path,value=receipt,tp=self.target_path,target=self.target,part=None,space='working',consumer='detail.frozen')
        self.pins.update(pins);self.resolutions.extend(resolutions)
    def image(self,row,mode):
        p=self.row(row);image=Image.open(p)
        c.require(image.mode==mode and image.size==(2048,2048),'Frozen2K '+mode+' image required')
        return np.asarray(image).copy()
    def arrays(self,row):
        p=self.row(row)
        with np.load(p,allow_pickle=False) as saved:return {key:saved[key] for key in saved.files}


def exact_image(actual,expected,label):
    c.require(actual.dtype==expected.dtype and np.array_equal(actual,expected),'Derived source-detail pixels differ: '+label)


def validate_geometry(entry,part,appearance,target_path,target,inputs):
    required={'part','materialDonorPart','workingGeometryReceipt','workingCandidate','nativeCornerArchive','originalFitReceipt',
              'originalUntreatedCandidate','originalMaps','originalUvLocationAtlas','originalToCurrentCornerOrder','materialRoles',
              'exactSourceAttributeSha256','derivedColorField','derivedAO0IntensityField'}
    c.require(set(entry)==required and entry['part']==part and entry['materialDonorPart']==part[:-1]+'l'
              and entry['materialRoles']=={'0':'skin'},'Exact ankle source manifest/owner required')
    favored=(appearance['leftGeometry'] if part.endswith('l') else appearance['rightDerivedMirrorGeometry'])[part]
    c.require(entry['workingGeometryReceipt']==favored,'Foreign geometry is not the exact favored source')
    rp,rec=inputs.load(favored);source=inputs.row(entry['workingCandidate'])
    c.require(rec['candidate']==str(source) and rec['candidateSha256']==c.sha(source),'Manifest candidate association differs')
    if inputs.material_execution is None:
        rec,pins,resolutions=source_receipt(source,rp,target_path,target,part)
    else:
        from replay_stage_skin_calibration import geometry_input
        checked=geometry_input(file_row(source),file_row(rp),target_path,target,part,'working',material_execution=inputs.material_execution)
        rec,pins,resolutions=checked['receipt'],checked['pins'],checked['resolutions']
    inputs.pins.update(pins);inputs.resolutions.extend(resolutions)
    c.require(entry['nativeCornerArchive']==rec['nativeCornerArchive'],'Exact source corner archive required')
    saved=inputs.arrays(entry['nativeCornerArchive']);doc,binary=read_glb(source);extra={};p,n,uv,pr=raw_corners(doc,binary,extra=extra)
    c.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and len(pr)==1 and pr[0]['material']==0
              and 'TANGENT' in extra,'Canonical original skin-only PNUT source required')
    tangents=np.concatenate(extra['TANGENT']['rows'])
    for key,val in [('positions',p),('normals',n),('uvGltf',uv),('tangents',tangents)]:
        if inputs.material_execution is None:
            c.require(key in saved and np.array_equal(np.asarray(saved[key],dtype='f4'),np.asarray(val,dtype='f4')),'Manifest geometry archive differs: '+key)
        else:
            inputs.material_execution.geometry_proof(receipt_path=rp,candidate=source,owner=part,space='working')
    values={'positionsFloat32':p,'normalsFloat32':n,'uvFloat32':uv,'tangentsFloat32':tangents}
    c.require(set(entry['exactSourceAttributeSha256'])==set(values),'Complete source PNUT fingerprints required')
    for key,val in values.items():
        c.require(hashlib.sha256(np.asarray(val,dtype='f4').tobytes()).hexdigest()==entry['exactSourceAttributeSha256'][key],'Manifest literal source attribute differs: '+key)
    return {'receipt':rec,'receiptPath':rp,'source':source,'document':doc,'binary':binary,'positions':p,'normals':n,'uv':uv,'tangents':tangents}


def mirror_binding(part,left,right,target_path,target,inputs):
    rec=right['receipt'];lr=left['receipt']
    c.require(rec['operation']=='mirror' and rec['sourcePart']==part[:-1]+'l' and rec['source']==str(left['source'])
              and rec['sourceReceipt']==str(left['receiptPath']) and rec['sourceReceiptSha256']==c.sha(left['receiptPath'])
              and rec['sourceSha256']==c.sha(left['source']),'Exactly one declared opposite-source mirror required')
    configs=[]
    mirror_pins=rec['frozenInputs'] if inputs.material_execution is None else inputs.material_execution.physical_closure(module_file=__file__,consumer='detail.mirror',receipt_path=right['receiptPath'],receipt=rec,tp=target_path,target=target,owner=part,space='working')
    for name,digest in mirror_pins.items():
        # A scoped closure also pins its geometry receipt; it is not an operation config.
        if Path(name).resolve()==Path(right['receiptPath']).resolve():continue
        if Path(name).suffix=='.json':
            path=pin(name,digest);value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('operation')=='mirror' and value.get('part')==part and value.get('source')==str(left['source']):configs.append((path,value))
    c.require(len(configs)==1,'One pinned actual-frame mirror operation required')
    path,cfg=configs[0];tp,t=read_target(cfg)
    c.require(tp==Path(target_path).resolve() and t['id']==target['id'] and cfg['sourcePart']==lr['part']
              and cfg['sourceReceipt']==str(left['receiptPath']) and cfg['sourceReceiptSha256']==c.sha(left['receiptPath'])
              and cfg['sourceSha256']==c.sha(left['source']),'Mirror config foreign target/source')
    matrix,plane=reflection_between_frames(c.frame(target,c.PART_JOINTS[lr['part']],'working'),c.frame(target,c.PART_JOINTS[part],'working'),
                                         cfg['planeOriginWorld'],cfg['planeNormalWorld'])
    c.require(np.array_equal(matrix,rec['sourceToAttachmentLocal']) and np.array_equal(plane,rec['reflectionWorld']),'Actual installed-frame reflection differs')
    doc,binary,_,_=detached_affine_bake(left['document'],left['binary'],matrix,True)
    c.require(doc==right['document'] and binary==right['binary'],'Literal opposite mirror PNUT/winding/maps differ')
    return {'operation':'mirror','configuration':file_row(path),'sourceReceipt':file_row(left['receiptPath']),
            'reflectionBetweenActualInstalledFrames':plane.tolist(),'sourceToAttachmentLocal':matrix.tolist(),
            'literalEncodedPNUTIndicesWAndMapsReplayed':True,'textureUOrNormalMapChannelFlipped':False}


def original_data(row,part,target_path,target,basis,origin,inputs):
    rp,rec=inputs.load(row['originalFitReceipt']);c.verify_binding(rec,target_path,target,'working')
    if inputs.material_execution is not None:
        candidate=inputs.row({'path':rec['candidate'],'sha256':rec['candidateSha256']})
        inputs.material_execution.geometry_proof(receipt_path=rp,candidate=candidate,owner=part,space='working')
    c.require(rec['kind']=='target-part-geometry' and rec['part']==part and rec['statureApplications']==0
              and np.array_equal(rec['attachmentWorld'],c.frame(target,c.PART_JOINTS[part],'working')),'Original untreated fit/frame required')
    source=inputs.row({'path':rec['candidate'],'sha256':rec['candidateSha256']});doc,binary=read_glb(source)
    c.require(len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1,'One original skin primitive required')
    pr=doc['meshes'][0]['primitives'][0]
    c.require(pr['material']==0,'Original skin material0 required')
    f=accessor(doc,binary,pr['indices']).reshape(-1,3).astype(int);rawp=accessor(doc,binary,pr['attributes']['POSITION'])
    p=rawp.astype(float)@BASIS.T;n=accessor(doc,binary,pr['attributes']['NORMAL']).astype(float)@BASIS.T
    uv=accessor(doc,binary,pr['attributes']['TEXCOORD_0']).astype(float);material=doc['materials'][0]
    maps={}
    for role,binding in [('baseColor',material['pbrMetallicRoughness']['baseColorTexture']),('normal',material['normalTexture']),('orm',material['pbrMetallicRoughness']['metallicRoughnessTexture'])]:
        c.require(binding.get('texCoord',0)==0 and not binding.get('extensions'),'Original unchanged atlas binding required')
        image=doc['images'][doc['textures'][binding['index']]['source']];v=doc['bufferViews'][image['bufferView']];start=v.get('byteOffset',0)
        blob=binary[start:start+v['byteLength']];path=inputs.row(row['maps'][role]);c.require(path.read_bytes()==blob,'Original embedded map/archive differs: '+role)
        maps[role]=inputs.image(row['maps'][role],'RGB')
    masks=atlas.geometry_masks(p[f],n[f],uv[f],['skin']*len(f),2048,[],guard=2)
    h=((masks['positionLocal'].astype(float)-origin)@basis)[:,:,2] if part=='shinl' else masks['positionLocal'][:,:,2].astype(float)
    recorded=inputs.arrays(row['atlas']);detail.match_arrays(recorded,{'sourceHeight':h,'sourceOwnerFace':masks['ownerFace'],'coverage':masks['coverage'],
                               'ambiguous':masks['ambiguous'],'protected':masks['protected'],'sourcePosition':masks['positionLocal']})
    bary=np.asarray([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    sp=np.einsum('bc,tci->tbi',bary,p[f]).reshape(-1,3);su=np.einsum('bc,tci->tbi',bary,uv[f]).reshape(-1,2)
    sh=((sp-origin)@basis)[:,2] if part=='shinl' else sp[:,2];rgb=atlas.sample_texels(maps['baseColor'].astype(float),su,repeat=True)
    bounds=[(-.003,.015),(.015,.024),(.024,.040),(.040,.060)] if part=='shinl' else [(-.030,-.015),(-.015,0),(0,.015)]
    medians=[]
    for k,(lo,hi) in enumerate(bounds):
        selected=(sh>=lo)&(sh<hi);c.require(selected.any(),'Empty original calibration sample cohort')
        median=np.median(rgb[selected],axis=0);c.require(np.array_equal(median,row['sampleBins'][k]['medianRGB']),'Original source median differs')
        medians.append(median)
    return {'source':source,'receiptPath':rp,'document':doc,'binary':binary,'rawPositions':rawp,'faces':f,'uv':uv,'maps':maps,
            'masks':masks,'height':h,'medians':medians}

def replay_recipe(material_path,material,manifest,target_path,target,inputs):
    c.require(material.get('schemaVersion')==1 and material.get('kind')=='one-original-source-body-microdetail-transport-material-diagnostic',
              'Original source-detail recipe receipt required; genericPNG/chained treatment unsupported')
    c.require(material['targetContract']=={'path':str(Path(target_path).resolve()),'sha256':c.sha(target_path)},'Foreign source-detail target')
    inputs.frozen(material,material_path);parent_path,parent=inputs.load(material['parentMaterials']);inputs.frozen(parent,parent_path)
    c.require(parent['schemaVersion']==1 and parent['kind']=='two-unselected-derived-ankle-color-calibration-controls',
              'Original common-tone reconstruction phase required; chained material parent rejected')
    cp,cfg=inputs.load(parent['configuration']);_,meas=inputs.load(cfg['measurement'])
    c.require(cfg['kind']=='derived-ankle-strip-and-common-tone-diagnostic-controls' and cfg['schemaVersion']==1
              and cfg['targetContract']==material['targetContract'] and cfg['controls']==['band-only','common-tone']
              and set(cfg['parts'])=={'shinl','footl'} and meas['kind']=='exact-approved-profile-pale-strip-original-pixel-measurement'
              and meas['targetContract']==cfg['targetContract'] and cfg['parts']==meas['parts'],'Original calibration/source metadata differs')
    recipe=material['recipe'];_,field=inputs.load(recipe['sourceShaftConfiguration'])
    basis=np.asarray(field['shin']['basis']);origin=np.asarray(field['shin']['origin']);centre=np.asarray(field['shin']['centre'])
    c.require(np.array_equal(basis,recipe['sourceShaftBasis']) and np.array_equal(origin,recipe['sourceShaftOrigin'])
              and np.array_equal(centre,recipe['sourceShaftCentre']) and np.allclose(basis.T@basis,np.eye(3),atol=1e-12,rtol=0)
              and np.linalg.det(basis)>0,'Original source shaft field differs')
    c.require(recipe['sourceBodyHeightMeters']==[.024,.040] and recipe['sourceBlur']['sigmaTexels']==2
              and recipe['sourceBlur']['radiusTexels']==6 and recipe['maximumAllowedLookupMetricErrorMeters']==.001
              and recipe['AO']==0 and recipe['paddingRadiusTexels']==4
              and recipe['donorHeightGoal']=='.024 + .016*smoothstep((sourceHeight+.014)/.034)'
              and recipe['support']=='1-smoothstep((sourceHeight-.012)/.008), times smoothstep((sourceRadialDistance-.008)/.004); unowned/protected pixels zero.'
              and recipe['pixelRecipe']=='parentCommonToneRGB + support*(originalBodyHighpassAtDonor*commonShinGain-parentCommonToneHighpass); round once.',
              'Unsupported original donor/support/blur/AO recipe')
    original={}
    for part in ('shinl','footl'):
        row=cfg['parts'][part];entry=manifest['parts'][part]
        c.require(row['workingSourceReceipt']==entry['workingGeometryReceipt'] and row['originalFitReceipt']==entry['originalFitReceipt']
                  and row['maps']==entry['originalMaps'] and row['atlas']==entry['originalUvLocationAtlas'],'Recipe/source manifest original ancestry differs')
        data=original_data(row,part,target_path,target,basis,origin,inputs)
        c.require(file_row(data['source'])==entry['originalUntreatedCandidate'],'Manifest original candidate differs')
        original[part]=data
    body=original['shinl']['medians'][2];band=original['shinl']['medians'][0];target_rgb=original['footl']['medians'][1];cap=original['footl']['medians'][2]
    cr=cfg['recipe'];delta=band[1:]/band[0]-body[1:]/body[0]
    for key,val in [('shinBandRGBGain',body/band),('shinPigmentBodyGBOverR',body[1:]/body[0]),
                    ('shinPigmentExcessGBOverR',delta),('commonShinRGBGain',target_rgb/body),('commonFootCollarRGBGain',target_rgb/cap),
                    ('statisticsTargetFootBelowCollarRGB',target_rgb),('statisticsShinBodyRGB',body),('statisticsShinBandRGB',band),('statisticsFootCapRGB',cap)]:
        c.require(np.array_equal(cr[key],val),'Original regional RGB/gain measurement differs: '+key)
    c.require(cr['AO']==0 and cr['shinBandFullUntilSourceHeightMeters']==.012 and cr['shinBandFadeEndsSourceHeightMeters']==.020
              and cr['commonFootFadeStartsSourceHeightMeters']==0 and cr['commonFootFullAtSourceHeightMeters']==.010
              and cr['padding']['radiusTexels']==4,'Unsupported original common-tone/support/AO controls')
    replayed={}
    for part,data in original.items():
        parent_rgb,support=detail.common_tone(data['maps']['baseColor'],data['height'],data['masks'],part,body,band,target_rgb,cap)
        detail.match_arrays(inputs.arrays(parent['supportAtlases'][part]),support)
        exact_image(inputs.image(parent['outputs'][part]['common-tone']['color'],'RGB'),parent_rgb,part+' common-tone')
        exact_image(inputs.image(parent['outputs'][part]['common-tone']['intensityAO0'],'L'),detail.intensity(parent_rgb,data['maps']['orm'][:,:,0],0),part+' common-tone intensity')
        if part=='shinl':
            shaft=(data['masks']['positionLocal'].astype(float)-origin)@basis
            roots=detail.chart_roots(data['rawPositions'],data['uv'],data['faces'])
            rgb,lineage,charts,metrics=detail.detail_transfer(data['maps']['baseColor'],parent_rgb,data['height'],data['masks'],shaft,centre,roots,
                                                         data['masks']['ownerFace'],np.asarray(cr['commonShinRGBGain']))
            detail.match_arrays(inputs.arrays(material['lineage']),lineage)
            c.require(charts==material['chartRecords'],'Recorded original UV chart records differ')
            exact_image(inputs.image(material['color'],'RGB'),rgb,'favored shin RGB')
            exact_image(inputs.image(material['intensityAO0'],'L'),detail.intensity(rgb,data['maps']['orm'][:,:,0],0),'favored shin intensity')
            c.require(material['originalFitReceipt']==cfg['parts'][part]['originalFitReceipt']
                      and material['workingSourceReceipt']==cfg['parts'][part]['workingSourceReceipt'],'Favored material fit/profile association differs')
        else:
            rgb=parent_rgb;metrics={'detailTransferApplied':False,'commonToneReplayedFromOriginal':True}
            exact_image(inputs.image(material['footColor'],'RGB'),rgb,'favored foot RGB')
            exact_image(inputs.image(material['footIntensityAO0'],'L'),detail.intensity(rgb,data['maps']['orm'][:,:,0],0),'favored foot intensity')
        exact_image(rgb[data['masks']['protected']],data['maps']['baseColor'][data['masks']['protected']],part+' original protectedRGB')
        replayed[part]={'color':rgb,'original':data,'metrics':metrics}
    return replayed


def staging_inputs(value,target_path,target,part,space,source,receipt_path,roles,ao_strength,*,material_execution=None):
    detail.controls(value)
    c.require(space=='working' and part in detail.PARTS and part not in c.fixed_garment_parts(target)
              and roles=={0:'skin'},'Original source-detail mode requires exact working skin-only ankle role ownership')
    c.require(c.rig_mode(target)=='stock-exact' and target['identity']['gender']=='female' and target['identity']['prefix']=='pfh0'
              and target['rig']['runtimeScale']==1,'Original ankle mode requires installed female Human stock-exact target')
    c.require(not isinstance(ao_strength,bool) and ao_strength in (0,.15,.35),'Independent original AO strength required')
    loaded=c.load(target_path)
    c.require(loaded==target,'Supplied source-detail target differs from pinned live contract')
    inputs=Inputs(material_execution=material_execution,target_path=target_path,target=target);inputs.row({'path':str(Path(target_path).resolve()),'sha256':c.sha(target_path)})
    inputs.pins.update(target['frozenInputs'])
    mp,material=inputs.load(value['receipt']);sp,manifest=inputs.load(value['sourceManifest'])
    required={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','targetId','rigRevision','coordinateSpace',
              'materialReceipt','favoredAppearance','parts','scope','rightPolicy','materialAcceptedInNativeOrClient','recipeReplayImplemented'}
    c.require(set(manifest)==required and manifest['schemaVersion']==1 and manifest['kind']=='target-source-chart-detail-material-binding'
              and manifest['diagnosticOnly'] is True and set(manifest['parts'])==set(detail.PARTS)
              and manifest['materialReceipt']==value['receipt'],'Exact four-part original source manifest required')
    c.verify_binding(manifest,target_path,target,'working');ap,appearance=inputs.load(manifest['favoredAppearance'])
    c.require(appearance['schemaVersion']==1 and appearance['kind']=='user-favored-working-ankle-geometry-and-original-detail-appearance-baseline'
              and appearance['material']==value['receipt'],'Favored appearance/material association differs')
    for row in (appearance['materialIndependentReplay'],appearance['leftIndependentReadback'],appearance['mirrorIndependentReview']):inputs.row(row)
    geometry={}
    for name in detail.PARTS:geometry[name]=validate_geometry(manifest['parts'][name],name,appearance,target_path,target,inputs)
    source=Path(source).resolve();receipt_path=Path(receipt_path).resolve()
    c.require(source==geometry[part]['source'] and receipt_path==geometry[part]['receiptPath'],'Foreign source/receipt rejected; exact manifest source required')
    c.require(source!=mp and receipt_path!=mp,'Treatment receipt cannot be a geometry source')
    ancestry={name:{'operation':'exact-favored-profile','sourceReceipt':file_row(geometry[name]['receiptPath']),
                   'candidate':file_row(geometry[name]['source'])} for name in ('shinl','footl')}
    for name in ('shinr','footr'):ancestry[name]=mirror_binding(name,geometry[name[:-1]+'l'],geometry[name],target_path,target,inputs)
    replayed=replay_recipe(mp,material,manifest,target_path,target,inputs); donor=part[:-1]+'l';data=replayed[donor];orig=data['original']
    current=geometry[part];doc,binary=current['document'],current['binary'];entry=manifest['parts'][part]
    original_entry=manifest['parts'][donor]
    for key in ('originalFitReceipt','originalUntreatedCandidate','originalMaps','originalUvLocationAtlas'):
        c.require(entry[key]==original_entry[key],'Opposite source original donor binding differs: '+key)
    order=[0,1,2] if part.endswith('l') else [0,2,1]
    expected_uv=orig['uv'][orig['faces']][:,order]
    c.require(entry['originalToCurrentCornerOrder']==order and np.array_equal(current['uv'],expected_uv)
              and embedded_maps(doc,binary)==embedded_maps(orig['document'],orig['binary']) and doc['materials']==orig['document']['materials'],
              'Staged source original material/UV map identity differs')
    c.require(entry['derivedColorField']==('color' if donor=='shinl' else 'footColor')
              and entry['derivedAO0IntensityField']==('intensityAO0' if donor=='shinl' else 'footIntensityAO0'),'Manifest material field binding differs')
    from target_part_stage import material_inputs, image_pixels
    rows,transport=material_inputs(doc,binary,roles,part,ao_strength,c.fixed_garment_parts(target))
    c.require(set(rows)=={'skin'},'Original source-detail material roles differ')
    material_definition=doc['materials'][0]
    red=image_pixels(doc,binary,material_definition['occlusionTexture'])[:,:,0]
    rgb=data['color'];output_intensity=detail.intensity(rgb,red,ao_strength)
    original_rgb=orig['maps']['baseColor'];original_intensity=detail.intensity(original_rgb,red,ao_strength)
    rows['skin']['color']=rgb;rows['skin']['intensity']=output_intensity
    proof={'kind':detail.KIND,'recipeMode':detail.MODE,'materialReceipt':file_row(mp),'sourceManifest':file_row(sp),
           'favoredAppearance':file_row(ap),'part':part,'materialDonorPart':donor,
           'independentUntreatedParent':file_row(orig['source']),'stagedGeometrySource':file_row(source),'originalFitReceipt':file_row(orig['receiptPath']),
           'originalMapArchive':manifest['parts'][donor]['originalMaps'],'originalUvAtlas':manifest['parts'][donor]['originalUvLocationAtlas'],
           'replayedDonorChartLineage':material['lineage'] if donor=='shinl' else None,
           'derivedColor':material[entry['derivedColorField']],'derivedAO0Intensity':material[entry['derivedAO0IntensityField']],
           'completeOriginalAtlasCalibrationDonorAndOutputPixelReplay':True,'originalRgbQuantizationPhases':2 if donor=='shinl' else 1,
           'geometryAncestry':ancestry[part],'historicalHelperResolutions':inputs.resolutions,'replayMetrics':data['metrics'],
           'aoStrength':ao_strength,'aoPolicy':'Same independently replayed originalRGB recipe; original occlusion red once before finalPLT byte truncation. AO0/.15/.35 siblings never chain.',
           'derivedColorPixelsEdited':bool(np.any(rgb!=original_rgb)),
           'derivedIntensityPixelsEdited':bool(np.any(output_intensity!=original_intensity)),
           'originalEmbeddedMapsEdited':False,'normalPixelsEdited':False,'roughnessPixelsEdited':False,
           'currentSourcePNUTEdited':False,'selected':False,'clientAccepted':False,
           'limits':'Diagnostic original-data transport only. Actual engine palette/neck/mip/filter/lighting/motion checks and disclosed source normal/topology issues remain open.'}
    for name in ('replay_stage_skin_detail.py','source_skin_detail_contract.py','target_part_stage.py','target_contract.py','skin_lighting_atlas.py',
                 'replay_stage_skin_intensity.py','target_skin_lighting_contract.py','mirror_stock_limb_part.py','place_purposebuilt_pelvis.py','target_part_pipeline.py'):
        path=Path(__file__).with_name(name).resolve();inputs.pins[str(path)]=c.sha(path)
    for name,digest in inputs.pins.items():pin(name,digest)
    return {'document':doc,'binary':binary,'materialRows':rows,'originalMaterialProof':transport,'proof':proof,
            'sourceReceipt':current['receipt'],'frozenInputs':inputs.pins,'auditFiles':[Path(p) for p in inputs.pins]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cfg=json.loads(args.config.read_text(encoding='utf-8'))
    c.require(cfg['kind']=='target-original-source-detail-replay-diagnostic-inputs' and cfg['diagnosticOnly'] is True,'Explicit no-stage replay diagnostic input required')
    tp,target=read_target(cfg);value=staging_inputs(cfg['skinIntensityInputs'],tp,target,cfg['part'],cfg['coordinateSpace'],
            pin(cfg['source'],cfg['sourceSha256']),pin(cfg['sourceReceipt'],cfg['sourceReceiptSha256']),
            {int(k):v for k,v in cfg['materialRoles'].items()},cfg.get('aoStrength',0))
    c.require(not args.output.exists(),'Fresh immutable diagnostic replay output required');args.output.mkdir(parents=True)
    rows=value['materialRows']['skin'];fingerprints={key:hashlib.sha256(array.tobytes()).hexdigest() for key,array in rows.items()}
    receipt={'schemaVersion':1,'kind':'target-original-source-detail-replay-diagnostic',**c.binding(tp,target,'working'),'part':cfg['part'],
             'materialInputBasis':detail.BASIS,'proof':value['proof'],'effectivePixelArraySha256':fingerprints,'frozenInputs':value['frozenInputs'],
             'candidateStagedCompiledOrConverted':False,'selected':False,'clientAccepted':False}
    path=args.output/'replay.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(path.resolve()),'sha256':c.sha(path),'proof':value['proof']}),flush=True)


if __name__=='__main__':main()