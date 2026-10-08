"""One original material calibration replay, separately verified current geometry.

Preserves the independently replayed original-detail ankle RGB parent. Does not
reuse an old geometry recipient claim for a new mesh or make asset approvals.
An explicit, fail-closed RGB-descendant route (shins only, AO0) carries a pinned
derived colour atlas: its luminance delta against the original material colour
is applied once, on the changed texels only, to the replayed original parent.
"""
from io import BytesIO
from pathlib import Path
import json
import numpy as np
from PIL import Image
import target_contract as c
import replay_stage_skin_calibration as cal
from place_purposebuilt_pelvis import read_glb, raw_corners

MODE='current-source-bound-skin-calibration-v1'
PELVIS_MODE='current-pelvis-routed-skin-calibration-v1'
def pelvis_mode(value):return isinstance(value,dict) and value.get('mode')==PELVIS_MODE
DESCENDANT_MODE='current-skin-intensity-descendant-v1'
def descendant_mode(value):return isinstance(value,dict) and value.get('mode')==DESCENDANT_MODE
RGB_DESCENDANT_PARTS=('shinl','shinr')
RGB_DESCENDANT_FIELDS={'derivedAtlas','bindingReceipt'}

def exact(row, pins):
    p=cal.exact_pin(row);pins[str(p)]=c.sha(p);return p

def map_bytes(doc,binary,material,channel):
    m=doc['materials'][material]
    ref=m['normalTexture'] if channel=='normal' else m['pbrMetallicRoughness']['baseColorTexture' if channel=='color' else 'metallicRoughnessTexture']
    image=doc['images'][doc['textures'][ref['index']]['source']]
    c.require('bufferView'in image and 'uri'not in image,'Embedded material source required')
    view=doc['bufferViews'][image['bufferView']];start=view.get('byteOffset',0)
    return binary[start:start+view['byteLength']]

def decode_rgb(data):
    pixels=np.asarray(Image.open(BytesIO(data)).convert('RGB'))
    c.require(pixels.shape==(2048,2048,3) and pixels.dtype==np.uint8,'Frozen 2K byte RGB atlas required');return pixels

def controls(value):
    if pelvis_mode(value):
        from pelvis_routed_material_bridge import controls as pelvis_controls
        return pelvis_controls(value)
    if descendant_mode(value):
        from skin_intensity_descendant_bridge import controls as descendant_controls
        return descendant_controls(value)
    base={'mode','recipe','materialExecution','faceRoleLineage'}
    c.require(isinstance(value,dict) and set(value) in (base,base|{'rgbDescendant'}) and value['mode']==MODE,'Exact current calibration controls required')
    if 'rgbDescendant' in value:
        d=value['rgbDescendant'];c.require(isinstance(d,dict) and set(d)==RGB_DESCENDANT_FIELDS,'Exact RGB-descendant derived atlas and binding receipt required')
        for row in d.values():cal.exact_pin(row)
        recipe=json.loads(cal.exact_pin(value['recipe']).read_text(encoding='utf-8'))
        c.require(recipe.get('part') in RGB_DESCENDANT_PARTS and value['faceRoleLineage'] is None,'RGB-descendant calibration is restricted to shinl/shinr')
    e=value['materialExecution']
    c.require(isinstance(e,dict) and set(e)=={'proof','representation','parentScope'},'Explicit original material execution bindings required')
    for row in [value['recipe'],e['proof'],e['representation']]:cal.exact_pin(row)
    if e['parentScope'] is None:
        recipe=json.loads(cal.exact_pin(value['recipe']).read_text(encoding='utf-8'))
        c.require(recipe.get('part') in ('bicepl','bicepr','forel','forer','handl','handr','legl','legr') and recipe.get('parent')=={'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}},'Null parent scope is restricted to eight exact simple original skin recipes')
    else:cal.exact_pin(e['parentScope'])
    role=value['faceRoleLineage']
    c.require(role is None or isinstance(role,dict) and set(role)=={'nativeCornerArchive','originalOwnershipProposal'},'Explicit original chest face-role ancestry required')
    if role is not None:
        for row in role.values():cal.exact_pin(row)

def match_current_maps(rgbd,part,ao_strength,receipt,rec,doc,binary,original_doc,original_binary,pins):
    """Exact original map identity per current material, or the explicit shin RGB-descendant binding (normal/ORM byte-exact)."""
    original_active={r['material'] for r in raw_corners(original_doc,original_binary)[3]}
    current_active={r['material'] for r in raw_corners(doc,binary)[3]};matches={};descendant={};derived=None
    if rgbd is not None:
        c.require(part in RGB_DESCENDANT_PARTS and ao_strength==0,'RGB-descendant calibration is restricted to AO0 shinl/shinr')
        bp=exact(rgbd['bindingReceipt'],pins);c.require(Path(bp).resolve()==Path(receipt).resolve() and rgbd['bindingReceipt']['sha256']==c.sha(receipt),'RGB binding receipt must be the current geometry receipt')
        c.require(rec.get('materialRGBBindingHistoricalDerivedAtlas')==rgbd['derivedAtlas'],'RGB binding receipt names a different derived atlas')
        derived=decode_rgb(exact(rgbd['derivedAtlas'],pins).read_bytes())
    for mid in sorted(current_active):
        match=[j for j in original_active if all(map_bytes(doc,binary,mid,k)==map_bytes(original_doc,original_binary,j,k) for k in('color','normal','orm'))]
        if not match and rgbd is not None:
            match=[j for j in original_active if all(map_bytes(doc,binary,mid,k)==map_bytes(original_doc,original_binary,j,k) for k in('normal','orm'))]
            c.require(match and np.array_equal(decode_rgb(map_bytes(doc,binary,mid,'color')),derived),'RGB-descendant colour must decode exactly to the pinned derived atlas with byte-exact original normal/ORM')
            descendant[str(mid)]=sorted(match)
        c.require(match,'Current original RGB/normal/ORM maps differ; a fresh RGB-descendant calibration is required')
        matches[str(mid)]=sorted(match)
    c.require(rgbd is None or (descendant and len({tuple(v) for v in descendant.values()})==1),'Unneeded or ambiguous RGB-descendant calibration rejected')
    return matches,descendant,derived

def staging_inputs(value,target_path,target,part,space,source,receipt,ao_strength=0,native_geometry=None):
    if pelvis_mode(value):
        from pelvis_routed_material_bridge import staging_inputs as pelvis_inputs
        return pelvis_inputs(value,target_path,target,part,space,source,receipt,ao_strength,native_geometry=native_geometry)
    if descendant_mode(value):
        from skin_intensity_descendant_bridge import staging_inputs as descendant_inputs
        return descendant_inputs(value,target_path,target,part,space,source,receipt,ao_strength,native_geometry=native_geometry)
    controls(value)
    from native_compiler_input_bridge import VerifiedNativeCompilerInputs
    c.require(type(native_geometry)is VerifiedNativeCompilerInputs,'Sealed current native geometry context required')
    native_geometry.verify();gp=dict(native_geometry.proof)
    c.require(space=='working' and part in c.BODY_PARTS and part!='pelvis' and ao_strength in(0,.15,.35),'Current original material bridge supports working non-pelvis owners')
    pins=dict(gp['frozenInputs']);source=Path(source).resolve();receipt=Path(receipt).resolve();rec=json.loads(receipt.read_text(encoding='utf-8'))
    c.verify_binding(rec,target_path,target,space)
    c.require(gp['part']==part and gp['candidate']=={'path':str(source),'sha256':c.sha(source)} and gp['geometryReceipt']=={'path':str(receipt),'sha256':c.sha(receipt)},'Cross-owner/current native geometry context')
    pins[str(Path(__file__).resolve())]=c.sha(__file__)
    c.require(rec['part']==part and Path(rec['candidate']).resolve()==source and rec['candidateSha256']==c.sha(source),'Current material source/owner differs')
    c.require(np.array_equal(native_geometry.material_ids,np.asarray([x['material'] for x in raw_corners(*read_glb(source))[3] for _ in range(x['triangles'])])),'Current source primitive ownership differs')
    rp=exact(value['recipe'],pins);recipe=json.loads(rp.read_text(encoding='utf-8'));c.verify_binding(recipe,target_path,target,'working');c.require(recipe['part']==part,'Cross-owner original material recipe')
    # Map identity (or the explicit RGB-descendant binding) is checked before the expensive parent replay: fail fast, fail closed.
    rgbd=value.get('rgbDescendant');doc,binary=read_glb(source);original_doc,original_binary=read_glb(cal.exact_pin(recipe['materialSource']['candidate']))
    matches,descendant,derived=match_current_maps(rgbd,part,ao_strength,receipt,rec,doc,binary,original_doc,original_binary,pins)
    from phenotype_material_execution_adoption import prepare_material_execution
    e=value['materialExecution'];ctx=prepare_material_execution(e['proof'],value['recipe'],e['representation'],target_path=target_path,target=target,part=part,space='working',parent_scope_pin=e['parentScope'])

    # A run scope needs a saved immutable descriptor; ordinary staging uses the
    # exact scoped material execution directly and its full opening/closing checks.
    old=cal.staging_inputs({'mode':cal.MODE,'recipe':value['recipe']},target_path,target,part,'working',cal.exact_pin(recipe['candidate']),cal.exact_pin(recipe['geometryReceipt']),None,ao_strength,material_execution=ctx)
    ctx.verify();pins.update(old['frozenInputs'])
    roles=['skin']*len(native_geometry.material_ids)
    if part=='chest':
        row=value['faceRoleLineage'];c.require(row is not None,'Chest needs explicit face-role ancestor')
        c.require(row['nativeCornerArchive']==rec['nativeCornerArchive'],'Chest role archive differs sealed source archive');ap=exact(row['nativeCornerArchive'],pins);pp=exact(row['originalOwnershipProposal'],pins);prop=json.loads(pp.read_text(encoding='utf-8'));c.verify_binding(prop,target_path,target,'working');c.require(prop['part']=='chest' and row['originalOwnershipProposal']==recipe['parent']['controls']['proposal'],'Chest ownership proposal differs original calibrated parent')
        with np.load(ap,allow_pickle=False) as a:ids=a['directParentFaceIds'].copy();p=a['positions']
        c.require(len(ids)==len(roles) and np.array_equal(p,native_geometry.array('positions')),'Chest face-role archive differs sealed geometry')
        oldroles=prop['faceRoles'];c.require(np.all(ids[ids>=0]<len(oldroles)),'Chest ancestor face IDs out of range')
        roles=[oldroles[int(i)] if i>=0 else 'skin' for i in ids]
    else:c.require(value['faceRoleLineage']is None,'Non-chest cannot borrow garment roles')
    from target_garment_ownership import partition
    mapped,material_roles,_=partition(doc,binary,roles,100000)
    mapped_ids=np.asarray([x['material'] for x in raw_corners(mapped,binary)[3] for _ in range(x['triangles'])],dtype='i8')
    c.require(np.array_equal(native_geometry.material_ids.shape,mapped_ids.shape),'Mapped face ownership count differs')
    for p,h in pins.items():c.require(c.sha(p)==h,'Current material bridge input changed: '+p)
    native_geometry.verify();ctx.verify()
    rows=old['materialRows'];descendant_proof=None
    if rgbd is not None:
        j=next(iter(descendant.values()))[0];original_rgb=decode_rgb(map_bytes(original_doc,original_binary,j,'color'))
        red,_=cal.ao_inputs(original_doc,original_binary,{j:'skin'});c.require(cal.fingerprint(red)==old['proof']['originalAOredSha256'],'RGB-descendant AO red differs from the replayed calibration')
        rows,descendant_proof=rgb_descendant_rows(rows,old['proof'],recipe,original_rgb,derived,red)
        descendant_proof.update({'derivedAtlas':rgbd['derivedAtlas'],'bindingReceipt':rgbd['bindingReceipt'],'descendantMaterials':descendant,'originalMaterial':j})
    proof={'kind':'separately-verified-current-geometry-and-original-calibration-material-inputs','part':part,'coordinateSpace':'working','originalMaterialRecipe':value['recipe'],'originalMaterialExecution':e,'originalCalibrationProof':old['proof'],'currentNativeGeometryProof':gp,'currentMapMatchesOriginalMaterialSource':matches,'originalDetailRGBParentRetained':recipe['parent']['mode']=='original-source-uv-detail-v1','calibrationApplications':1,'aoApplications':1,'oldGeometryRecipientProofAppliedToCurrent':False,'currentFaceRoleLineage':value['faceRoleLineage'],'currentRGBDescendantCalibration':descendant_proof,'currentMaterialIdsSha256':cal.fingerprint(mapped_ids),'runtimeConversions':0,'selected':False,'clientAccepted':False,'productionAccepted':False}
    return {'document':mapped,'binary':binary,'materialRoles':{int(k):v for k,v in material_roles.items()},'materialRows':rows,'originalMaterialProof':old['originalMaterialProof'],'sourceReceipt':rec,'proof':proof,'frozenInputs':pins,'auditFiles':[Path(p) for p in pins],'compilerMaterialIds':mapped_ids,'materialSlots':{str(k):{'role':v,'atlasKey':v}for k,v in material_roles.items()}}

def rgb_descendant_rows(rows,proof,recipe,original_rgb,derived,red):
    """Apply one derived-colour luminance delta to the replayed parent on changed texels; unchanged texels stay exact."""
    from source_skin_detail_contract import intensity
    c.require(set(rows)=={'skin'} and recipe['gain']==1 and proof['aoStrength']==0 and proof['calibrationApplications']==1 and 'rgbDescendantApplications' not in proof,
              'Single AO0 unit-gain skin calibration required before one RGB-descendant application')
    effective=rows['skin']['intensity'];c.require(effective.dtype==np.uint8 and effective.shape==(2048,2048) and cal.fingerprint(effective)==proof['effectiveIntensitySha256'],'Replayed effective calibration differs')
    changed=np.any(derived!=original_rgb,axis=2);count=int(changed.sum());c.require(0<count<changed.size,'RGB-descendant atlas must change a bounded nonempty texel set')
    delta=intensity(derived,red,0).astype(np.int64)-intensity(original_rgb,red,0).astype(np.int64)
    c.require(np.all(effective[changed]>=1),'RGB-descendant texels must be unclamped in the original calibration')
    parent=effective[changed].astype(np.int64)-int(np.floor(recipe['offsetBytes']));c.require(parent.min()>=0 and parent.max()<=255,'Reconstructed parent intensity outside bytes')
    replay,_=cal.calibrated_intensity(parent.astype(np.uint8)[None,:],red[changed][None,:],recipe['gain'],recipe['offsetBytes'],0)
    c.require(np.array_equal(replay[0],effective[changed]),'Reconstructed parent does not replay the original calibration')
    new_parent=np.clip(parent+delta[changed],0,255).astype(np.uint8)
    value,aux=cal.calibrated_intensity(new_parent[None,:],red[changed][None,:],recipe['gain'],recipe['offsetBytes'],0)
    out=effective.copy();out[changed]=value[0]
    c.require(np.array_equal(out[~changed],effective[~changed]),'Unchanged texels must equal the original calibrated AO0')
    result={key:dict(row) for key,row in rows.items()};result['skin']['intensity']=out
    for key in ('color','normal','roughness'):c.require(np.array_equal(result['skin'][key],rows['skin'][key]),'Protected parent pixels changed')
    return result,{'operation':'derived-RGB-luminance-delta-on-replayed-parent-then-recipe-calibration-once','rgbDescendantApplications':1,'calibrationApplications':1,
                   'changedRGBTexels':count,'changedIntensityTexels':int((out!=effective).sum()),'unchangedTexelsEqualOriginalCalibratedAO0':True,
                   'reconstructedParentReplaysOriginalCalibration':True,'luminanceDeltaRange':[int(delta[changed].min()),int(delta[changed].max())],
                   'newParentClampedTexels':int(((parent+delta[changed])<0).sum()+((parent+delta[changed])>255).sum()),
                   'calibratedClampedLowTexels':int(aux['clampedLow'].sum()),'calibratedClampedHighTexels':int(aux['clampedHigh'].sum()),
                   'originalEffectiveIntensitySha256':proof['effectiveIntensitySha256'],'effectiveIntensitySha256':cal.fingerprint(out),
                   'changedTexelMaskSha256':cal.fingerprint(changed),'originalAOredSha256':cal.fingerprint(red)}
