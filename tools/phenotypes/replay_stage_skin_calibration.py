"""Replay one explicit source-bound affine PLT calibration; never edit source maps.

Parent recipes are independently replayed at AO0. This additive mode applies a
bounded positive gain/offset to those integer bytes, then original AO once.
Existing C1, original-detail and original-map contracts are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import target_contract as c
from target_part_pipeline import pin, read_target
from replay_stage_skin_intensity import frozen_inputs, file_row
from place_purposebuilt_pelvis import read_glb, raw_corners, embedded_maps

MODE = 'source-bound-skin-calibration-v1'
KIND = 'replayed-source-bound-skin-calibration-compiler-inputs'
BASIS = 'replayed-source-bound-skin-calibration-inputs'
QUANTIZATION = 'ao0-byte-affine-floor-clip-then-original-ao-floor-v1'
PALETTE = 'categorical-per-texel-lut-before-filter-v1'
PARENTS = ('original-materialRoles-skin', 'reviewed-per-face-garment', 'original-source-uv-detail-v1')


def fingerprint(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def exact_pin(row):
    c.require(isinstance(row,dict) and set(row)=={'path','sha256'} and isinstance(row['path'],str)
              and isinstance(row['sha256'],str) and len(row['sha256'])==64
              and all(x in '0123456789abcdef' for x in row['sha256']), 'Exact calibration file path/hash required')
    return pin(row['path'],row['sha256'])


def controls(value):
    c.require(isinstance(value,dict) and set(value)=={'mode','recipe'} and value['mode']==MODE,
              'Exact source-bound calibration mode/recipe required')
    exact_pin(value['recipe'])


def coefficients(gain,offset):
    c.require(type(gain) in (int,float) and np.isfinite(gain) and .25<=gain<=2,
              'Positive bounded calibration gain .25..2 required')
    c.require(type(offset) in (int,float) and np.isfinite(offset) and -96<=offset<=96,
              'Bounded calibration offset -96..96 bytes required')


def calibrated_intensity(parent,ao_red,gain,offset,ao_strength):
    """Integer AO0 -> affine floor/clip -> original AO once -> floor/clip."""
    coefficients(gain,offset)
    c.require(parent.dtype==ao_red.dtype==np.uint8 and parent.shape==ao_red.shape
              and parent.ndim==2 and parent.size>0, 'Untreated AO0byte/original AOred atlas required')
    c.require(type(ao_strength) in (int,float) and ao_strength in (0,.15,.35), 'Independent AO strength0/.15/.35 required')
    affine=parent.astype(float)*gain+offset
    calibrated=np.floor(np.clip(affine,0,255)).astype('u1')
    value=np.floor(np.clip(calibrated.astype(float)*(1-ao_strength*(1-ao_red.astype(float)/255)),0,255)).astype('u1')
    return value,{'calibratedAO0':calibrated,'clampedLow':affine<0,'clampedHigh':affine>255}


def palette_texels(intensity,palette,row):
    """Categorical LUT selection BEFORE any spatial filtering."""
    c.require(intensity.dtype==palette.dtype==np.uint8 and intensity.ndim==2 and palette.ndim==3
              and palette.shape[1:]==(256,3) and type(row) is int and 0<=row<len(palette),
              'Byte intensity/palette and declared categorical row required')
    return palette[row,intensity]


def filtered_palette(intensity,palette,row,uv):
    from skin_lighting_atlas import sample_texels
    c.require(np.asarray(uv).ndim==2 and np.asarray(uv).shape[1]==2 and np.isfinite(uv).all(), 'Finite UV samples required')
    return sample_texels(palette_texels(intensity,palette,row).astype(float),np.asarray(uv),repeat=True)


def source_fingerprints(doc,binary):
    extra={};p,n,u,pr=raw_corners(doc,binary,extra=extra)
    c.require(len(p)>0 and np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(u).all()
              and (np.linalg.norm(n,axis=2)>0).all(), 'Finite nonzero authored P/N/U source required')
    t=np.concatenate(extra['TANGENT']['rows']) if 'TANGENT' in extra else None
    from place_purposebuilt_pelvis import accessor
    inventories=[];indices=[]
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            row={}
            for semantic,index in primitive['attributes'].items():
                a=doc['accessors'][index]
                row[semantic]={'componentType':a['componentType'],'type':a['type'],'count':a['count'],
                               'normalized':a.get('normalized',False),
                               'decodedAttributeSha256':fingerprint(accessor(doc,binary,index,allow_normalized=(semantic=='COLOR_0')))}
            inventories.append(row);indices.append(fingerprint(accessor(doc,binary,primitive['indices'])))
    return {'positionsFloat32':fingerprint(np.asarray(p,dtype='f4')),
            'normalsFloat32':fingerprint(np.asarray(n,dtype='f4')),
            'uvGltfFloat32':fingerprint(np.asarray(u,dtype='f4')),
            'authoredTangentsFloat32':None if t is None else fingerprint(np.asarray(t,dtype='f4')),
            'authoredTangentsStatus':'absent' if t is None else 'present',
            'primitiveTriangleMaterialInventory':[{k:r[k] for k in ('node','mesh','primitive','triangles','material')} for r in pr],
            'originalPrimitiveAttributeSignatures':inventories,'originalPrimitiveIndicesSha256':indices,
            'originalEmbeddedMaps':embedded_maps(doc,binary)}


def geometry_input(candidate_row,receipt_row,tp,target,part,space,*,material_execution=None):
    source=exact_pin(candidate_row);rp=exact_pin(receipt_row);rec=json.loads(rp.read_text(encoding='utf-8'))
    c.require(rec.get('schemaVersion')==2 and rec.get('kind')=='target-part-geometry'
              and not any(k in rec for k in ('derivedMaterialProof','materialInputBasis','calibrationApplications')),
              'Untreated geometry receipt required; calibration/stage/C1 parents cannot chain')
    c.verify_binding(rec,tp,target,space)
    c.require(rec['part']==part and rec['joint']==c.PART_JOINTS[part] and rec['model']==c.model(target,part)
              and rec['statureApplications']==(0 if space=='working' else 1), 'Calibration geometry part/space/stature differs')
    c.require(Path(rec['candidate']).resolve()==source and rec['candidateSha256']==c.sha(source)
              and np.array_equal(rec['attachmentWorld'],c.frame(target,c.PART_JOINTS[part],space)), 'Calibration geometry source/frame differs')
    if material_execution is None:
        pins,resolutions=frozen_inputs(rec,rp)
    else:
        from phenotype_material_execution_adoption import resolve
        pins,resolutions=resolve(material_execution,module_file=__file__,path=rp,value=rec,
                                 tp=tp,target=target,part=part,space=space)
    pins.update({str(source):c.sha(source),str(rp):c.sha(rp)})
    doc,binary=read_glb(source)
    c.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}] and not doc.get('skins') and not doc.get('animations'), 'Detached identity body geometry required')
    serialization_proof=None
    from target_source_face_material_lineage import OPERATION,source_face_geometry
    if material_execution is not None:
        # The explicit adapter proves the actual encoded source and its original
        # native ancestry with exact protocol equations, not a looser archive check.
        serialization_proof=material_execution.geometry_proof(receipt_path=rp,candidate=source,owner=part,space=space)
    elif rec['operation']==OPERATION:
        serialization_proof,added,rr=source_face_geometry(source,rp,rec,tp,target,part,space,doc,binary)
        pins.update(added);resolutions.extend(rr)
    elif 'nativeCornerArchive' in rec:
        row=rec['nativeCornerArchive'];ap=pin(row['path'],row['sha256']);pins[str(ap)]=c.sha(ap)
        extra={};p,n,u,_=raw_corners(doc,binary,extra=extra);un=u.copy();un[:,:,1]=1-u[:,:,1]
        with np.load(ap,allow_pickle=False) as saved:
            for key,val in [('positions',p),('normals',n),('uvGltf',u),('uvNative',un)]:
                c.require(key in saved and np.array_equal(np.asarray(saved[key],dtype='f4'),np.asarray(val,dtype='f4')), 'Geometry corner archive differs: '+key)
            if 'TANGENT' in extra:
                key='authoredTangents' if 'authoredTangents' in saved else 'tangents'
                c.require(key in saved and np.array_equal(np.asarray(saved[key],dtype='f4'),np.asarray(np.concatenate(extra['TANGENT']['rows']),dtype='f4')), 'Geometry authored tangent archive differs')
            else:
                c.require('authoredTangents' not in saved and 'tangents' not in saved, 'Absent source tangent cannot be invented by archive')
    return {'source':source,'receiptPath':rp,'receipt':rec,'document':doc,'binary':binary,'pins':pins,'resolutions':resolutions,
            'serializationProof':serialization_proof}


def material_lineage(current,material,tp,target,part,space,lineage_receipt=None,*,material_execution=None):
    if lineage_receipt is not None:
        from target_source_face_material_lineage import material_recipient
        if space=='working':
            proof,pins,resolutions=material_recipient(lineage_receipt,current,material,tp,target,part,space,material_execution=material_execution)
        else:
            lp=exact_pin(lineage_receipt);relation=json.loads(lp.read_text(encoding='utf-8'))
            row=relation.get('currentWorkingSource')
            c.require(isinstance(row,dict) and set(row)=={'candidate','geometryReceipt'}, 'Explicit intermediate working material recipient required')
            working=geometry_input(row['candidate'],row['geometryReceipt'],tp,target,part,'working')
            prior,pins,resolutions=material_recipient(lineage_receipt,working,material,tp,target,part,'working')
            identity=material_lineage(current,working,tp,target,part,'runtime')
            pins.update(working['pins']);resolutions.extend(working['resolutions'])
            proof={'kind':'one-explicit-source-face-recipient-then-one-stock-identity-runtime','workingRecipient':prior,
                   'identityRuntime':identity,'sourceFaceOperations':1,'runtimeConversions':1,'noGeometryHashRelabel':True}
        current['pins'].update(pins);current['resolutions'].extend(resolutions)
        return proof
    if current['source']==material['source'] and current['receiptPath']==material['receiptPath']:
        c.require(material['receipt']['coordinateSpace']==space,'Same-source material coordinate space differs')
        return {'kind':'same-exact-geometry','materialSource':file_row(material['source']),'materialReceipt':file_row(material['receiptPath'])}
    rec=current['receipt'];old=material['receipt']
    c.require(space=='runtime' and c.rig_mode(target)=='stock-exact' and target['rig']['runtimeScale']==1
              and old['coordinateSpace']=='working' and old['statureApplications']==0 and rec['operation']=='runtime'
              and rec['statureApplications']==1 and rec['sourcePart']==part
              and np.array_equal(rec['sourceToAttachmentLocal'],np.eye(4))
              and Path(rec['source']).resolve()==material['source'] and rec['sourceSha256']==c.sha(material['source'])
              and Path(rec['sourceReceipt']).resolve()==material['receiptPath'] and rec['sourceReceiptSha256']==c.sha(material['receiptPath']),
              'Only one explicit installed-stock identity runtime material lineage supported')
    c.require(np.array_equal(c.frame(target,c.PART_JOINTS[part],'working'),c.frame(target,c.PART_JOINTS[part],'runtime')),
              'Identity runtime attachment frames differ')
    c.require(source_fingerprints(current['document'],current['binary'])==source_fingerprints(material['document'],material['binary']),
              'Identity runtime decoded P/N/U/T/map/material inventory differs')
    for key in ('materials','textures','images','samplers'):
        c.require(current['document'].get(key)==material['document'].get(key), 'Identity runtime material definition differs: '+key)
    # Check indexed lineage as well as expanded attributes, without inferring identity from UV alone.
    from place_purposebuilt_pelvis import accessor
    a=current['document']['meshes'][0]['primitives'];b=material['document']['meshes'][0]['primitives']
    c.require(len(a)==len(b),'Identity runtime primitive count differs')
    for aa,bb in zip(a,b):
        c.require(set(aa['attributes'])==set(bb['attributes']) and aa['material']==bb['material']
                  and np.array_equal(accessor(current['document'],current['binary'],aa['indices']),accessor(material['document'],material['binary'],bb['indices'])),
                  'Identity runtime original indexed lineage differs')
        for semantic in aa['attributes']:
            c.require(np.array_equal(accessor(current['document'],current['binary'],aa['attributes'][semantic],allow_normalized=(semantic=='COLOR_0')),
                                     accessor(material['document'],material['binary'],bb['attributes'][semantic],allow_normalized=(semantic=='COLOR_0'))),
                      'Identity runtime original attribute differs: '+semantic)
    return {'kind':'single-explicit-stock-identity-working-to-runtime','workingMaterialSource':file_row(material['source']),
            'workingMaterialReceipt':file_row(material['receiptPath']),'runtimeCandidate':file_row(current['source']),
            'runtimeReceipt':file_row(current['receiptPath']),'workingApplications':0,'runtimeApplications':1,
            'decodedPNUTMapsMaterialIndicesExact':True,'noGeometryHashRelabel':True}


def parent_inputs(parent,material,tp,target,part,*,material_execution=None):
    c.require(isinstance(parent,dict) and set(parent)=={'mode','controls'} and parent['mode'] in PARENTS,
              'Explicit untreated original/garment/detail parent required; C1/calibration/chaining unsupported')
    mode=parent['mode'];value=parent['controls'];space=material['receipt']['coordinateSpace']
    from target_part_stage import material_inputs
    doc,binary=material['document'],material['binary'];pins={};files=[]
    if mode=='original-materialRoles-skin':
        c.require(isinstance(value,dict) and set(value)=={'materialRoles'} and isinstance(value['materialRoles'],dict)
                  and all(isinstance(k,str) and k==str(int(k)) for k in value['materialRoles']), 'Exact original materialRoles parent required')
        roles={int(k):v for k,v in value['materialRoles'].items()}
        _,_,_,pr=raw_corners(doc,binary)
        c.require(set(roles)=={r['material'] for r in pr} and all(type(k) is int and 0<=k<len(doc['materials']) for k in roles) and set(roles.values())=={'skin'}
                  and part not in c.fixed_garment_parts(target), 'Original parent must own complete skin-only materials outside fixed garments')
        rows,transport=material_inputs(doc,binary,roles,part,0,c.fixed_garment_parts(target));proof={'kind':'original-embedded-maps-AO0','originalMapsExact':True}
    elif mode=='reviewed-per-face-garment':
        c.require(isinstance(value,dict) and set(value)=={'proposal','review'} and part in c.fixed_garment_parts(target), 'Reviewed fixed garment owner required')
        pp=exact_pin(value['proposal']);rp=exact_pin(value['review'])
        from target_garment_face_ownership import reviewed_staging_inputs
        v=reviewed_staging_inputs(pp,rp,tp,target,part,space,material['source'],material['receiptPath'],0,material_execution=material_execution)
        doc,binary=v['document'],v['binary'];roles={int(k):r for k,r in v['materialRoles'].items()};rows=v['materialRows'];transport=v['originalMaterialProof'];proof=v['proof']
        proposal=json.loads(pp.read_text(encoding='utf-8'));pins.update(v.get('frozenInputs',{**proposal['frozenInputs'],**proposal['outputHashes']}));pins.update({str(pp):c.sha(pp),str(rp):c.sha(rp)})
        for row in proof['paletteEdgeEvidence']:ep=pin(row['path'],row['sha256']);pins[str(ep)]=c.sha(ep)
    else:
        from replay_stage_skin_detail import staging_inputs
        v=staging_inputs(value,tp,target,part,space,material['source'],material['receiptPath'],{0:'skin'},0,material_execution=material_execution)
        doc,binary=v['document'],v['binary'];roles={0:'skin'};rows=v['materialRows'];transport=v['originalMaterialProof'];proof=v['proof'];pins.update(v['frozenInputs'])
    c.require('skin' in rows and set(rows)==set(roles.values()), 'Complete parent skin/cloth rows required')
    return {'document':doc,'binary':binary,'materialRoles':roles,'materialRows':rows,'originalMaterialProof':transport,'proof':proof,'pins':pins}


def ao_inputs(doc,binary,roles):
    """Resolve only declared original occlusion; absent AO is explicit identity."""
    from target_part_stage import image_pixels
    found=[];provenance=[]
    for material,role in sorted(roles.items()):
        if role!='skin':continue
        definition=doc['materials'][material]
        if 'occlusionTexture' in definition:
            binding=definition['occlusionTexture']
            c.require(isinstance(binding,dict), 'Declared original occlusionTexture binding required')
            red=image_pixels(doc,binary,binding)[:,:,0]
            policy='declared-original-occlusionTexture-red'
        else:
            binding=None;red=np.full((2048,2048),255,dtype=np.uint8)
            policy='absent-declared-occlusionTexture-identity255'
        found.append(red);provenance.append({'material':material,'policy':policy,'originalOcclusionTextureBinding':binding,
            'effectiveAOredSha256':fingerprint(red),'ORMRedInferredAsAO':False})
    c.require(found and all(np.array_equal(found[0],item) for item in found[1:]), 'All skin materials require exact common original AOred')
    return found[0],provenance


def ao_red(doc,binary,roles):
    return ao_inputs(doc,binary,roles)[0]


def contrast(array):
    return {'minimum':int(array.min()),'maximum':int(array.max()),'mean':float(array.mean()),'std':float(array.std())}


def clipping_area(doc,binary,roles,clamped):
    from skin_lighting_atlas import sample_texels
    p,_,uv,pr=raw_corners(doc,binary);select=np.asarray([roles[r['material']]=='skin' for r in pr for _ in range(r['triangles'])])
    p,uv=p[select],uv[select];area=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)/2
    c.require((area>0).all() and len(area)>0,'Positive represented skin triangles required')
    bary=np.asarray([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]]);u=np.einsum('bc,tci->tbi',bary,uv).reshape(-1,2)
    sampled=sample_texels(clamped.astype(float),u,repeat=True);weights=np.repeat(area/4,4)
    return {'representedSkinAreaSquareMetres':float(area.sum()),'weightedClampedFilterSampleAreaFraction':float(np.average(sampled,weights=weights)),
            'samples':len(weights),'policy':'Finite four barycentric samples per skin triangle; bilinear categorical pertexel clamp mask before area weighting. Not exhaustive continuous surface or client coverage.'}


def staging_inputs(value,tp,target,part,space,source,receipt_path,roles,ao_strength,*,material_execution=None):
    controls(value);recipe_path=exact_pin(value['recipe']);recipe=json.loads(recipe_path.read_text(encoding='utf-8'))
    required={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','targetId','rigRevision','coordinateSpace','part',
              'geometryReceipt','candidate','materialSource','parent','gain','offsetBytes','parentAO0IntensitySha256','sourceFingerprints',
              'quantization','palettePolicy','calibrationApplications','parentAoStrength','frozenInputs'}
    c.require(set(recipe)==required and type(recipe['schemaVersion']) is int and recipe['schemaVersion']==1 and recipe['kind']=='target-compiler-skin-intensity-calibration'
              and recipe['diagnosticOnly'] is True and recipe['part']==part and part in c.BODY_PARTS
              and space in ('working','runtime'), 'Exact diagnostic source-bound calibration recipe required')
    c.verify_binding(recipe,tp,target,space);c.require(c.load(tp)==target,'Calibration live target differs')
    coefficients(recipe['gain'],recipe['offsetBytes'])
    c.require(type(recipe['calibrationApplications']) is int and recipe['calibrationApplications']==1
              and type(recipe['parentAoStrength']) in (int,float) and recipe['parentAoStrength']==0
              and recipe['quantization']==QUANTIZATION and recipe['palettePolicy']==PALETTE,
              'One calibration on untreated AO0 with exact quantization/palette policy required')
    if material_execution is None:
        pins,resolutions=frozen_inputs(recipe,recipe_path)
    else:
        from phenotype_material_execution_adoption import resolve
        pins,resolutions=resolve(material_execution,module_file=__file__,path=recipe_path,value=recipe,
                                 tp=tp,target=target,part=part,space=space)
    pins.update({str(recipe_path):c.sha(recipe_path),str(Path(tp).resolve()):c.sha(tp),**target['frozenInputs']})
    current=geometry_input(recipe['candidate'],recipe['geometryReceipt'],tp,target,part,space,material_execution=material_execution)
    c.require(current['source']==Path(source).resolve() and current['receiptPath']==Path(receipt_path).resolve(), 'Stale/foreign current calibration candidate/receipt')
    ms=recipe['materialSource'];c.require(isinstance(ms,dict) and set(ms) in ({'candidate','geometryReceipt','coordinateSpace'},
        {'candidate','geometryReceipt','coordinateSpace','lineageReceipt'}) and ms['coordinateSpace'] in ('working','runtime'), 'Exact material source binding required')
    if 'lineageReceipt' in ms:
        c.require(recipe['parent']['mode']=='original-source-uv-detail-v1', 'Source-face recipient lineage is restricted to exact original-detail parent')
    material=geometry_input(ms['candidate'],ms['geometryReceipt'],tp,target,part,ms['coordinateSpace'],material_execution=material_execution)
    lineage=material_lineage(current,material,tp,target,part,space,ms.get('lineageReceipt'),material_execution=material_execution)
    c.require(source_fingerprints(current['document'],current['binary'])==recipe['sourceFingerprints'], 'Source calibration P/N/U/T/map fingerprints differ')
    parent=parent_inputs(recipe['parent'],material,tp,target,part,material_execution=material_execution)
    c.require(roles is None or roles==parent['materialRoles'],'Conflicting calibration material roles')
    doc,binary=parent['document'],parent['binary'];parent_roles=parent['materialRoles']
    if lineage['kind']!='same-exact-geometry':
        if recipe['parent']['mode']=='reviewed-per-face-garment':
            from target_garment_ownership import partition
            proposal=json.loads(exact_pin(recipe['parent']['controls']['proposal']).read_text(encoding='utf-8'))
            doc,new_roles,_=partition(current['document'],current['binary'],proposal['faceRoles'],100000)
            c.require({int(k):v for k,v in new_roles.items()}==parent_roles,'Runtime reviewed partition roles differ');binary=current['binary']
        else:doc,binary=current['document'],current['binary']
    untouched=parent['materialRows']['skin']['intensity']
    c.require(untouched.dtype==np.uint8 and untouched.shape==(2048,2048)
              and fingerprint(untouched)==recipe['parentAO0IntensitySha256'], 'Untreated effective AO0 parent intensity differs')
    red,ao_provenance=ao_inputs(doc,binary,parent_roles);variants={};aux=None
    for strength in (0,.15,.35):
        arr,a=calibrated_intensity(untouched,red,recipe['gain'],recipe['offsetBytes'],strength);variants[str(strength)]=fingerprint(arr)
        if strength==ao_strength:effective=arr;aux=a
    c.require(aux is not None and type(ao_strength) in (int,float), 'Independent AO sibling selection required')
    rows={key:dict(row) for key,row in parent['materialRows'].items()};rows['skin']['intensity']=effective
    for role,row in rows.items():
        for key in ('color','normal','roughness'):c.require(np.array_equal(row[key],parent['materialRows'][role][key]),'Protected original/parent pixels changed')
        if role!='skin':c.require(all(np.array_equal(row[key],parent['materialRows'][role][key]) for key in row),'Fixed cloth row modified')
    for group in (current,material):pins.update(group['pins']);resolutions.extend(group['resolutions'])
    pins.update(parent['pins'])
    proof={'kind':KIND,'recipeMode':MODE,'recipe':file_row(recipe_path),'part':part,'coordinateSpace':space,
           'independentUntreatedParent':file_row(material['source']),'currentGeometry':file_row(current['source']),
           'materialSourceLineage':lineage,'parentMode':recipe['parent']['mode'],'parentControls':recipe['parent']['controls'],'parentProof':parent['proof'],
           'gain':recipe['gain'],'offsetBytes':recipe['offsetBytes'],'quantization':QUANTIZATION,'palettePolicy':PALETTE,
           'parentAO0IntensitySha256':fingerprint(untouched),'calibratedAO0IntensitySha256':fingerprint(aux['calibratedAO0']),
           'originalAOredSha256':fingerprint(red),'originalAOProvenance':ao_provenance,'independentAOSiblingIntensitySha256':variants,'aoStrength':ao_strength,
           'effectiveIntensitySha256':fingerprint(effective),'calibrationApplications':1,'aoApplications':1,
           'clampedLowTexels':int(aux['clampedLow'].sum()),'clampedHighTexels':int(aux['clampedHigh'].sum()),
           'atlasTexels':untouched.size,'representedSkinClipping':clipping_area(doc,binary,parent_roles,aux['clampedLow']|aux['clampedHigh']),
           'sourceGeometrySerializationProof':current['serializationProof'],
           'sourceAO0Contrast':contrast(untouched),'calibratedAO0Contrast':contrast(aux['calibratedAO0']),
           'effectiveIntensityContrast':contrast(effective),'sourceFingerprints':recipe['sourceFingerprints'],
           'fixedClothResourcesAndParentPixelsExact':True,'originalRGBNormalORMUVAndAuthoredAttributesEdited':False,
           'originalSourceTangentsStatus':recipe['sourceFingerprints']['authoredTangentsStatus'],
           'historicalHelperResolutions':resolutions,'derivedIntensityPixelsEdited':bool(np.any(effective!=untouched)),
           'derivedColorPixelsEdited':False,'selected':False,'clientAccepted':False,
           'limits':'Uniform part calibration cannot create missing muscle anatomy or painted contrast. Clipping/contrast and palette3/8 native/client views require independent review. Prefilter LUT math is baselevel byte diagnostic, not mip/gamma/HQ/client acceptance.'}
    for name in ('replay_stage_skin_calibration.py','target_part_stage.py','audit_target_native_part.py','target_contract.py',
                 'replay_stage_skin_intensity.py','skin_lighting_atlas.py','place_purposebuilt_pelvis.py','target_source_face_material_lineage.py'):
        p=Path(__file__).with_name(name).resolve();pins[str(p)]=c.sha(p)
    for p,h in pins.items():pin(p,h)
    return {'document':doc,'binary':binary,'materialRoles':parent_roles,'materialRows':rows,'originalMaterialProof':parent['originalMaterialProof'],
            'proof':proof,'sourceReceipt':current['receipt'],'frozenInputs':pins,'auditFiles':[Path(p) for p in pins]}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cfg=json.loads(args.config.read_text(encoding='utf-8'))
    c.require(cfg['kind']=='target-skin-calibration-replay-diagnostic' and cfg['diagnosticOnly'] is True,'Explicit calibration no-stage diagnostic required')
    tp,target=read_target(cfg);v=staging_inputs(cfg['skinIntensityInputs'],tp,target,cfg['part'],cfg['coordinateSpace'],
        pin(cfg['source'],cfg['sourceSha256']),pin(cfg['sourceReceipt'],cfg['sourceReceiptSha256']),None,cfg.get('aoStrength',0))
    c.require(not args.output.exists(),'Fresh immutable calibration replay output required');args.output.mkdir(parents=True)
    out=args.output/'replay.json';out.write_text(json.dumps({'schemaVersion':1,'kind':'target-source-bound-skin-calibration-replay-diagnostic',
        **c.binding(tp,target,cfg['coordinateSpace']),'part':cfg['part'],'proof':v['proof'],'frozenInputs':v['frozenInputs'],
        'assetsStagedCompiledOrConverted':False,'selected':False,'clientAccepted':False},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(out.resolve()),'sha256':c.sha(out)}),flush=True)


if __name__=='__main__':main()
