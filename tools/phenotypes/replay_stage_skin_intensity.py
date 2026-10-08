"""Replay pinned C1 skin intensity inputs for diagnostic native staging.

Original geometry, embedded maps and CPU bake remain immutable. Only the
explicit cap-corner exception and a measured opposite-frame mirror may bridge
lighting-source ancestry. Historical Python snapshots are data, never executed.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import target_contract as contract
import target_skin_lighting_contract as lighting
import skin_lighting_atlas as atlas
from mirror_stock_limb_part import detached_affine_bake, reflection_between_frames
from place_purposebuilt_pelvis import embedded_maps, raw_corners, read_glb
from target_part_pipeline import pin, read_target


KIND = 'replayed-c1-skin-intensity-compiler-inputs'
BASIS = 'replayed-c1-skin-intensity-inputs'


def row_pin(row):
    contract.require(isinstance(row,dict) and set(row) <= {'path','sha256','byteCount','pixelSha256','copiedEmbeddedBytesExact'}
                     and {'path','sha256'} <= set(row), 'Explicit lighting path and hash required')
    return pin(row['path'],row['sha256'])


def file_row(path):
    path=Path(path).resolve();return {'path':str(path),'sha256':contract.sha(path)}


def controls(value):
    contract.require(isinstance(value,dict) and set(value)=={'receipt','strength'},
                     'Exact skin intensity receipt and strength controls required')
    contract.require(isinstance(value['receipt'],dict) and set(value['receipt'])=={'path','sha256'},
                     'Exact skin intensity receipt path and hash required')
    lighting.finite(value['strength'],0,1,'Declared lighting strength')


def frozen_inputs(receipt, receipt_path):
    """Resolve only explicitly archived historical Python helper bytes.

    Prefer this receipt's own pinned helpers directory. Other snapshots must be
    explicitly recorded and unique; data/resource/target pins never substitute.
    """
    expected=receipt['frozenInputs'];result={};resolved=[]
    bank=Path(__file__).resolve().parent
    for name,digest in expected.items():
        original=Path(name).resolve()
        if original.is_file() and contract.sha(original)==digest:
            result[str(original)]=digest;continue
        contract.require(original.parent==bank and original.suffix=='.py',
                         'Frozen non-helper input changed: '+str(original))
        candidates=[Path(p).resolve() for p,h in expected.items()
                    if h==digest and Path(p).name==original.name and Path(p).parent.name=='helpers'
                    and Path(p).resolve()!=original]
        own=Path(receipt_path).resolve().parent/'helpers'/original.name
        if own in candidates:candidates=[own]
        contract.require(len(candidates)==1,'Missing or ambiguous explicitly archived helper: '+str(original))
        saved=pin(candidates[0],digest);result[str(saved)]=digest
        resolved.append({'originalPath':str(original),'recordedSha256':digest,'snapshot':file_row(saved)})
    return result,resolved


def source_receipt(source, receipt_path, target_path, target, part, *, execution_adoption=None):
    receipt=json.loads(Path(receipt_path).read_text(encoding='utf-8'))
    contract.require(receipt.get('schemaVersion')==2 and receipt.get('kind')=='target-part-geometry',
                     'Untreated target geometry receipt required; repeated material treatment is unsupported')
    contract.verify_binding(receipt,target_path,target,'working')
    contract.require(receipt['part']==part and receipt['joint']==contract.PART_JOINTS[part]
                     and receipt['statureApplications']==0, 'Lighting geometry part/space/stature differs')
    contract.require(Path(receipt['candidate']).resolve()==Path(source).resolve()
                     and receipt['candidateSha256']==contract.sha(source), 'Lighting geometry candidate association differs')
    contract.require(receipt['model']==contract.model(target,part) and
        np.array_equal(receipt['attachmentWorld'],contract.frame(target,contract.PART_JOINTS[part],'working')),
        'Lighting geometry stock attachment frame/model differs')
    if execution_adoption is None:
        pins,resolved=frozen_inputs(receipt,receipt_path)
    else:
        from phenotype_execution_adoption import resolve_frozen_inputs
        pins,resolved=resolve_frozen_inputs(execution_adoption, module_file=__file__,
            consumer='replay_stage_skin_intensity.source_receipt', receipt_path=receipt_path,
            receipt=receipt, target_path=target_path, target=target, space='working')
    if 'nativeCornerArchive' in receipt:
        archive_path=row_pin(receipt['nativeCornerArchive']);pins[str(archive_path)]=contract.sha(archive_path)
        doc,binary=read_glb(source);extra={};p,n,uv,_=raw_corners(doc,binary,extra=extra)
        native_uv=uv.copy();native_uv[:,:,1]=1-native_uv[:,:,1]
        with np.load(archive_path,allow_pickle=False) as saved:
            contract.require(all(key in saved.files and np.array_equal(np.asarray(saved[key],dtype='f4'),np.asarray(value,dtype='f4'))
                for key,value in [('positions',p),('normals',n),('uvGltf',uv),('uvNative',native_uv)]),
                'Declared geometry corner archive differs from serialized candidate')
            tkey='authoredTangents' if 'authoredTangents' in saved.files else 'tangents'
            contract.require(tkey in saved.files and 'TANGENT' in extra and np.array_equal(np.asarray(saved[tkey],dtype='f4'),
                np.asarray(np.concatenate(extra['TANGENT']['rows']),dtype='f4')), 'Declared authored tangent archive differs')
    return receipt,pins,resolved


def face_filter_footprint(uv, size):
    """Conservative complete level-zero bilinear support over a UV triangle.

    A texel contributes only within one texel of its center. Triangle/square
    separating axes include both coordinate axes and triangle edge normals.
    Boundary contact is conservatively included; REPEAT wraps destination IDs.
    """
    q=np.asarray(uv,float)*size-.5
    contract.require(q.shape==(3,2) and np.isfinite(q).all(),'Finite triangle UV required')
    lo=np.floor(q.min(0)-1).astype(int);hi=np.ceil(q.max(0)+1).astype(int)
    x,y=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1))
    centers=np.c_[x.ravel(),y.ravel()];valid=np.ones(len(centers),bool)
    edges=np.roll(q,-1,axis=0)-q
    for axis in [np.array([1.,0.]),np.array([0.,1.]),*np.c_[-edges[:,1],edges[:,0]]]:
        if np.linalg.norm(axis)<1e-15:continue
        tri=q@axis;s=centers@axis;radius=abs(axis).sum()
        valid&=(s+radius>=tri.min()-1e-12)&(s-radius<=tri.max()+1e-12)
    out=centers[valid];return np.unique((out[:,1]%size)*size+(out[:,0]%size))


def zero_face_proof(uv, faces, influence, original, derived):
    result=[]
    for face in faces:
        footprint=face_filter_footprint(uv[face],original.shape[0])
        zero=not np.any(influence.reshape(-1)[footprint])
        exact=np.array_equal(original.reshape(-1)[footprint],derived.reshape(-1)[footprint])
        contract.require(zero and exact, 'Changed-normal face is not wholly zero-treatment across its bilinear footprint')
        result.append({'originalSourceFaceId':int(face),'bilinearFootprintTexels':len(footprint),
                       'maximumInfluence':0,'intensityPixelsExactUntreated':True,
                       'policy':'Complete triangle/square bilinear support, conservative boundary inclusion, level-zero REPEAT.'})
    return result


def replay_atlas(data, cfg, raw, recorded, strength):
    """Recalculate C1 geometry masks, deterministic padding and intensity."""
    raw=np.asarray(raw)
    contract.require(raw.shape==data['originalIntensity'].shape+(3,) and np.isfinite(raw).all()
                     and raw.min()>=-1e-7,'Finite original linear RGB bake required')
    samples,weights=lighting.surface_samples(data['positions'],data['uv'],data['triangleRoles'])
    luma=raw.astype(float)@lighting.LUMA
    mean=float(np.average(atlas.sample_texels(luma,samples,True),weights=weights))
    contract.require(np.isfinite(mean) and mean>1e-8,'Nonempty original bake required')
    field=luma/mean
    masks=atlas.geometry_masks(data['positions'],data['normals'],data['uv'],data['triangleRoles'],
                len(field),data['config']['protectedRegions'],cfg['maskGuardPixels'],
                cfg['positionOverlapToleranceMeters'],cfg['normalOverlapTolerance'])
    forbidden=masks['protected']|masks['garment']|masks['ambiguous']
    lineage,distance,destination=atlas.pad_lineage(masks['coverage'],forbidden,cfg['paddingRadiusPixels'])
    expected={**masks,'normalizedLuminance':field.astype('f4'),'paddingSourceTexelIndex':lineage,
              'paddingSteps':distance,'paddingDestination':destination}
    contract.require(set(recorded)==set(expected),'Recorded C1 atlas inventory differs')
    for key,value in expected.items():
        contract.require(np.array_equal(recorded[key],value),'Recorded C1 atlas replay differs: '+key)
    setting=data['config']['treatment'];original=data['originalIntensity']
    treated=lighting.compose(original,field,masks['influence'],masks['garment'],
                masks['protected']|masks['ambiguous'],strength,setting['maxDarkenShades'],setting['maxBrightenShades'])
    derived=atlas.apply_padding(original,treated,lineage,destination,strength)
    contract.require(np.array_equal(derived[forbidden],original[forbidden]),'Protected original intensity pixels differ')
    bary=np.array([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    for face in cfg['requiredZeroSourceFaces']:
        contract.require(type(face) is int and 0<=face<len(data['uv']), 'Required zero face outside original geometry')
        contract.require(not np.any(atlas.sample_texels(masks['influence'],bary@data['uv'][face],True)),
                         'Original declared zero-source-face samples differ')
    return derived,masks,mean


def c1_controls(cfg):
    required={'schemaVersion','kind','diagnosticOnly','parentLighting','sourceConfig','paddingRadiusPixels',
              'maskGuardPixels','positionOverlapToleranceMeters','normalOverlapTolerance','requiredZeroSourceFaces'}
    contract.require(set(cfg)==required and cfg['schemaVersion']==1
        and cfg['kind']=='target-skin-lighting-c1-padding-diagnostic' and cfg['diagnosticOnly'] is True,
        'Exact declared C1 padding configuration required')
    contract.require(type(cfg['paddingRadiusPixels']) is int and 1<=cfg['paddingRadiusPixels']<=32
                     and type(cfg['maskGuardPixels']) is int and 1<=cfg['maskGuardPixels']<=4,'Bounded C1 padding/mask guard required')
    lighting.finite(cfg['positionOverlapToleranceMeters'],1e-7,1e-5,'C1 position overlap tolerance')
    lighting.finite(cfg['normalOverlapTolerance'],1e-7,1e-4,'C1 normal overlap tolerance')
    contract.require(isinstance(cfg['requiredZeroSourceFaces'],list)
                     and len(set(cfg['requiredZeroSourceFaces']))==len(cfg['requiredZeroSourceFaces']), 'Explicit unique zero source faces required')


def verify_bake(parent, parent_path, data, inputs, resolutions):
    """Bind retained CPU output to its exact original arrays/maps/worker input."""
    contract.verify_binding(parent,data['targetPath'],data['target'],'working')
    contract.require(parent.get('schemaVersion')==2 and parent.get('kind')=='target-skin-lighting-diagnostic'
        and parent['part']==data['config']['part'] and parent['source']==str(data['source'])
        and parent['sourceReceipt']==str(data['sourceReceipt']) and parent['sourceSha256']==contract.sha(data['source'])
        and parent['sourceReceiptSha256']==contract.sha(data['sourceReceipt'])
        and parent['untreatedParentSha256']==contract.sha(data['source']) and parent['normalStrength']==1,
        'Original untreated bake source or normal strength differs')
    contract.require(parent['lighting']==data['config']['lighting'],'Recorded CPU bake settings differ')
    fp,rs=frozen_inputs(parent,parent_path);inputs.update(fp);resolutions.extend(rs)
    worker_path=row_pin(parent['workerReceipts']['bake']);inputs[str(worker_path)]=contract.sha(worker_path)
    worker=json.loads(worker_path.read_text());contract.require(worker['kind']=='target-skin-lighting-worker-bake'
        and worker['cpuOnly'] is True and worker['cameraUsedForBake'] is False,'Retained CPU direct bake required')
    fp,rs=frozen_inputs(worker,worker_path);inputs.update(fp);resolutions.extend(rs)
    job_path=row_pin(worker['input']);inputs[str(job_path)]=contract.sha(job_path);job=json.loads(job_path.read_text())
    contract.verify_binding(job,data['targetPath'],data['target'],'working')
    contract.require(job['kind']=='target-skin-lighting-worker-input' and job['diagnosticOnly'] is True
        and job['source']=={'path':str(data['source']),'sha256':contract.sha(data['source']),
                           'byteCount':data['source'].stat().st_size}
        and job['part']==data['config']['part'] and job['lighting']==data['config']['lighting']
        and np.array_equal(job['attachmentWorld'],contract.frame(data['target'],contract.PART_JOINTS[job['part']],'working')),
        'Original CPU worker source/settings/frame association differs')
    fp,rs=frozen_inputs(job,job_path);inputs.update(fp);resolutions.extend(rs)
    arr_path=row_pin(job['arrays']);inputs[str(arr_path)]=contract.sha(arr_path)
    with np.load(arr_path,allow_pickle=False) as arrays:
        contract.require(set(arrays.files)=={'positions','normals','uv','tangents'} and all(np.array_equal(arrays[k],data[k])
            for k in ('positions','normals','uv','tangents')),'Original CPU worker arrays differ from untreated geometry')
    contract.require(job['primitives']==data['primitives'],'Original CPU primitive/material ownership differs')
    contract.require(set(job['materials'])==set(map(str,data['materials'])),'Original CPU material inventory differs')
    for mid,entry in data['materials'].items():
        contract.require(job['materials'][str(mid)]['role']==entry['role'],'Original CPU material role differs')
        for key,(blob,pixels) in entry['maps'].items():
            copy=row_pin(job['materials'][str(mid)]['maps'][key]);inputs[str(copy)]=contract.sha(copy)
            archived=row_pin(parent['originalMapCopies'][str(mid)][key]);inputs[str(archived)]=contract.sha(archived)
            contract.require(copy.read_bytes()==blob==archived.read_bytes(),'Original embedded map archive bytes differ')
    raw_path=row_pin(worker['rawBake']);inputs[str(raw_path)]=contract.sha(raw_path)
    with np.load(raw_path,allow_pickle=False) as raw_file:
        contract.require(set(raw_file.files)=={'rawLinearRGB'},'Original CPU raw bake inventory differs');raw=raw_file['rawLinearRGB']
    atlas_path=row_pin(parent['lightingAtlas']);inputs[str(atlas_path)]=contract.sha(atlas_path)
    with np.load(atlas_path,allow_pickle=False) as parent_atlas:
        contract.require(np.array_equal(raw,parent_atlas['rawLinearRGB']),'Parent atlas raw bake differs from retained CPU output')
    contract.require(parent['originalIntensityArraySha256']==hashlib.sha256(data['originalIntensity'].tobytes()).hexdigest(),
                     'Original intensity parent differs')
    launch_path=row_pin(parent['workerLaunchReceipts']['bake']);inputs[str(launch_path)]=contract.sha(launch_path)
    launch=json.loads(launch_path.read_text())
    fp,rs=frozen_inputs(launch,launch_path);inputs.update(fp);resolutions.extend(rs)
    contract.require(launch['tool']=='blender' and launch['exitCode']==0,
                     'Completed verified CPU worker launch required')
    return raw


def geometry_ancestry(source, receipt_path, data, derived, masks, inputs, resolutions, depth=0):
    contract.require(depth<=2,'Repeated or unsupported lighting geometry ancestry')
    rec=json.loads(Path(receipt_path).read_text());part=rec['part']
    rec,pins,rs=source_receipt(source,receipt_path,data['targetPath'],data['target'],part)
    inputs.update(pins);resolutions.extend(rs);inputs[str(receipt_path)]=contract.sha(receipt_path);inputs[str(source)]=contract.sha(source)
    if source==data['source'] and receipt_path==data['sourceReceipt']:
        contract.require(part==data['config']['part'],'Untreated lighting part differs')
        return rec,{'operation':'exact-untreated-source','source':file_row(source),'sourceReceipt':file_row(receipt_path),'changedNormalFaces':[]}
    op=rec.get('operation')
    if op=='explicit-cap-normal-corner-exception':
        contract.require(part==data['config']['part'] and Path(rec['source']).resolve()==data['source']
                         and rec['sourceSha256']==contract.sha(data['source'])
                         and Path(rec['sourceReceipt']).resolve()==data['sourceReceipt']
                         and rec['sourceReceiptSha256']==contract.sha(data['sourceReceipt']),
                         'Cap exception does not descend directly from original untreated lighting source')
        contract.require(np.array_equal(rec['sourceToAttachmentLocal'],np.eye(4)) and rec['reflectionWorld'] is None,
                         'Explicit cap exception requires unchanged local positions/frame')
        plan_path=row_pin(rec['repairPlan']);inputs[str(plan_path)]=contract.sha(plan_path);plan=json.loads(plan_path.read_text())
        contract.require(plan['kind']=='explicit-cap-normal-repair-plan' and plan['schemaVersion']==2
                         and plan['targetId']==data['target']['id'] and plan['part']==part
                         and plan['coordinateSpace']=='working','Explicit measured cap plan belongs to another source/target')
        plan_inputs=plan.get('inputPins',{})
        contract.require(all(name not in rec['frozenInputs'] or rec['frozenInputs'][name]==digest for name,digest in plan_inputs.items()),
                         'Repair plan frozen closure conflicts with geometry receipt')
        fp,rs=frozen_inputs({'frozenInputs':{**rec['frozenInputs'],**plan_inputs}},receipt_path)
        inputs.update(fp);resolutions.extend(row for row in rs if row not in resolutions)
        face=plan['sourceFaceId'];contract.require(type(face) is int and face in data['c1Config']['requiredZeroSourceFaces'],
                         'Cap changed face must be declared protected by original C1 recipe')
        from diagnose_native_cap_normal import validate_descendant
        child,binary=read_glb(source)
        p,n,uv,t,order,exception=validate_descendant(data['doc'],data['binary'],child,binary,face)
        contract.require(np.array_equal(p[face],plan['originalPositionsMetres'])
            and np.array_equal(data['normals'][face],plan['oldAuthoredNormals'])
            and np.allclose(exception['geometricNormalDouble'],plan['proposedGeometricNormalDouble'],atol=1e-15,rtol=0)
            and np.array_equal(t[face],np.asarray(plan['proposedProjectedTangentsDouble'],dtype='f4')),
            'Cap measured plan differs from independently replayed exception')
        protected=zero_face_proof(uv,[face],masks['influence'],data['originalIntensity'],derived)
        return rec,{'operation':op,'repairPlan':file_row(plan_path),'changedNormalFaces':protected,
                    'originalPositionsUVAndMapBytesExact':True,'allOtherAuthoredNormalTangentCornersExact':True,
                    'serializedTriangleToOriginalFaceSha256':hashlib.sha256(order.astype('<i8').tobytes()).hexdigest()}
    contract.require(op=='mirror' and depth==0,'Unexplained lighting source changes or repeated treatment ancestry')
    donor=row_pin({'path':rec['source'],'sha256':rec['sourceSha256']})
    donor_receipt=row_pin({'path':rec['sourceReceipt'],'sha256':rec['sourceReceiptSha256']})
    donor_rec,lineage=geometry_ancestry(donor,donor_receipt,data,derived,masks,inputs,resolutions,depth+1)
    contract.require(rec['sourcePart']==donor_rec['part'] and any({part,rec['sourcePart']}==set(pair) for pair in contract.PAIRS),
                     'Declared opposite-frame mirror part differs')
    # The exact frozen operation configuration supplies the measured plane;
    # recorded affine/proof booleans are independently recalculated.
    configs=[]
    for name,digest in rec['frozenInputs'].items():
        path=Path(name)
        if path.suffix=='.json':
            value=json.loads(pin(path,digest).read_text())
            if value.get('operation')=='mirror' and value.get('part')==part and value.get('source')==str(donor):configs.append((path.resolve(),value))
    contract.require(len(configs)==1,'Exactly one pinned mirror operation configuration required')
    cfgpath,cfg=configs[0];mtp,mt=read_target(cfg)
    contract.require(mtp==data['targetPath'] and mt['id']==data['target']['id'],'Mirror configuration belongs to another target')
    contract.verify_binding(rec,data['targetPath'],data['target'],'working')
    contract.require(cfg['sourceReceipt']==str(donor_receipt) and cfg['sourceReceiptSha256']==contract.sha(donor_receipt)
                     and cfg['sourceSha256']==contract.sha(donor) and cfg['sourcePart']==donor_rec['part'], 'Mirror configuration source ancestry differs')
    matrix,plane=reflection_between_frames(contract.frame(data['target'],contract.PART_JOINTS[donor_rec['part']],'working'),
        contract.frame(data['target'],contract.PART_JOINTS[part],'working'),cfg['planeOriginWorld'],cfg['planeNormalWorld'])
    contract.require(np.array_equal(matrix,rec['sourceToAttachmentLocal']) and np.array_equal(plane,rec['reflectionWorld']),
                     'Mirror recorded geometry transform differs from measured opposite frames')
    doc,binary=read_glb(donor);ed,eb,_,_=detached_affine_bake(doc,binary,matrix,True)
    cd,cb=read_glb(source);contract.require(cd==ed and cb==eb,'Serialized mirror differs from independent opposite-frame replay')
    return rec,{'operation':'mirror','mirrorConfiguration':file_row(cfgpath),'donorLineage':lineage,
                'reflectionBetweenDeclaredOppositeFramesExact':True,'positionsNormalsUVTangentsWAndMapsReplayed':True,
                'lightingPolicy':'Same original attachment-baked intensity transported with unchanged UVs; opposite-limb visual lighting remains unaccepted.'}


def with_original_ao(color, original, derived, ao_red, strength):
    contract.require(strength in (0,.15,.35) and not isinstance(strength,bool),'AO comparison must be 0, 0.15 or 0.35')
    # Preserve legacy untreated/connector bytes even where luma had fractions.
    delta=derived.astype(float)-original.astype(float)
    return ((color.astype(float)@lighting.LUMA+delta)*(1-strength*(1-ao_red.astype(float)/255))).clip(0,255).astype('u1')


def staging_inputs(value,target_path,target,part,space,source,receipt_path,roles,ao_strength):
    helpers=('replay_stage_skin_intensity.py','target_skin_lighting_contract.py','skin_lighting_atlas.py',
             'diagnose_native_cap_normal.py','mirror_stock_limb_part.py','place_purposebuilt_pelvis.py','target_part_stage.py')
    executed={str(Path(__file__).with_name(name).resolve()):contract.sha(Path(__file__).with_name(name)) for name in helpers}
    controls(value)
    contract.require(space=='working','Skin intensity currently requires explicit working geometry')
    contract.require(part in contract.BODY_PARTS and part not in contract.fixed_garment_parts(target)
                     and set(roles.values())=={'skin'},'Skin intensity requires original skin-only roles outside fixed garment parts')
    path=row_pin(value['receipt']);receipt=json.loads(path.read_text())
    contract.require(receipt.get('schemaVersion')==2 and receipt.get('kind')=='target-skin-lighting-c1-padding-diagnostic',
                     'Pinned original C1 lighting descendant required; repeated treatment is unsupported')
    contract.verify_binding(receipt,target_path,target,'working')
    inputs={str(path):contract.sha(path)};resolutions=[]
    pins,rs=frozen_inputs(receipt,path);inputs.update(pins);resolutions.extend(rs)
    cfgpath=row_pin(receipt['config']);inputs[str(cfgpath)]=contract.sha(cfgpath);cfg=json.loads(cfgpath.read_text());c1_controls(cfg)
    scpath=row_pin(cfg['sourceConfig']);inputs[str(scpath)]=contract.sha(scpath);data=lighting.prepare(scpath)
    contract.require(data['targetPath']==Path(target_path).resolve() and data['target']['id']==target['id'],
                     'Lighting source configuration belongs to another target')
    inputs.update(data['frozenInputs']);data['c1Config']=cfg
    contract.require(receipt['source']==str(data['source']) and receipt['sourceSha256']==contract.sha(data['source'])
        and receipt['sourceReceipt']==str(data['sourceReceipt']) and receipt['sourceReceiptSha256']==contract.sha(data['sourceReceipt'])
        and receipt['part']==data['config']['part'],'C1 original source/part association differs')
    contract.require({int(k):v for k,v in data['config']['materialRoles'].items()}==roles,'Lighting original material roles differ')
    for variant in receipt['variants']: lighting.finite(variant['strength'],0,1,'Recorded declared lighting strength')
    contract.require([v['strength'] for v in receipt['variants']]==data['config']['treatment']['strengths'],
                     'Complete independent declared lighting variant inventory required')
    variants=[v for v in receipt['variants'] if v['strength']==value['strength']]
    contract.require(len(variants)==1 and value['strength'] in data['config']['treatment']['strengths'],
                     'Strength is not one unique declared independent lighting variant')
    variant=variants[0];contract.require(variant['untreatedParentSha256']==contract.sha(data['source']), 'Variant untreated AO/lighting parent differs')
    parent_path=row_pin(cfg['parentLighting']);contract.require(parent_path==row_pin(receipt['parentLighting']),'C1 parent lighting receipt differs')
    inputs[str(parent_path)]=contract.sha(parent_path);parent=json.loads(parent_path.read_text())
    raw=verify_bake(parent,parent_path,data,inputs,resolutions)
    atlaspath=row_pin(receipt['maskAndPaddingLineage']);inputs[str(atlaspath)]=contract.sha(atlaspath)
    with np.load(atlaspath,allow_pickle=False) as saved:recorded={k:saved[k] for k in saved.files}
    derived,masks,mean=replay_atlas(data,cfg,raw,recorded,value['strength'])
    contract.require(mean==receipt['normalizationMean'],'C1 recorded normalization mean differs')
    intensity_path=row_pin(variant['intensity']);inputs[str(intensity_path)]=contract.sha(intensity_path)
    image=Image.open(intensity_path);contract.require(image.mode=='L' and np.array_equal(np.asarray(image),derived),
                     'Derived intensity pixels differ from independent C1 replay')
    source=Path(source).resolve();receipt_path=Path(receipt_path).resolve()
    rec,lineage=geometry_ancestry(source,receipt_path,data,derived,masks,inputs,resolutions)
    contract.require(rec['part']==part,'Staged lighting candidate part differs')
    doc,binary=read_glb(source)
    contract.require(embedded_maps(doc,binary)==data['originalEmbeddedMaps'],'Staged original embedded map bytes differ')
    from target_part_stage import image_pixels,material_inputs
    rows,transport=material_inputs(doc,binary,roles,part,ao_strength,contract.fixed_garment_parts(target))
    contract.require(set(roles)=={r['material'] for r in raw_corners(doc,binary)[3]},'Every active skin material requires original role ownership')
    ao=None
    for mid in roles:
        material=doc['materials'][mid]
        red=image_pixels(doc,binary,material['occlusionTexture'])[:,:,0] if ao_strength else np.full(derived.shape,255,dtype='u1')
        if ao is None:ao=red
        else:contract.require(np.array_equal(ao,red),'Multiple original AO atlases differ')
    rows['skin']['intensity']=with_original_ao(rows['skin']['color'],data['originalIntensity'],derived,ao,ao_strength)
    proof={'kind':KIND,'lightingReceipt':file_row(path),'strength':value['strength'],'independentUntreatedParent':file_row(data['source']),
        'sourceReceipt':file_row(data['sourceReceipt']),'cpuRawBakeReused':True,'cpuBakeRerun':False,
        'maskAndPaddingLineage':file_row(atlaspath),'derivedIntensity':file_row(intensity_path),
        'normalizationMean':mean,'protectedOriginalPixelsExact':True,'completeAtlasAndIntensityReplay':True,
        'geometryAncestry':lineage,'historicalHelperResolutions':resolutions,
        'originalEmbeddedMapsEdited':False,'normalPixelsEdited':False,'roughnessPixelsEdited':False,
        'derivedIntensityPixelsEdited':bool(np.any(derived!=data['originalIntensity'])),
        'aoStrength':ao_strength,'aoPolicy':'Original fractional color luma plus independently replayed integer lighting delta, then original AO once; truncate byte. Strength0 and protected pixels equal legacy original-map AO.',
        'selected':False,'clientAccepted':False,'limits':'Diagnostic transport only. No native/client or opposite-limb lighting/stock-neck/animation acceptance; level-zero footprint does not prove engine mip behavior.'}
    inputs.update(executed)
    for name,digest in inputs.items(): pin(name,digest)
    return {'document':doc,'binary':binary,'materialRows':rows,'originalMaterialProof':transport,'proof':proof,
            'sourceReceipt':rec,'frozenInputs':inputs,'auditFiles':[Path(p) for p in inputs]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cfg=json.loads(args.config.read_text());tp,target=read_target(cfg)
    value=staging_inputs(cfg['skinIntensityInputs'],tp,target,cfg['part'],cfg['coordinateSpace'],
        pin(cfg['source'],cfg['sourceSha256']),pin(cfg['sourceReceipt'],cfg['sourceReceiptSha256']),
        {int(k):v for k,v in cfg['materialRoles'].items()},cfg.get('aoStrength',0))
    contract.require(not args.output.exists(),'Fresh immutable lighting replay diagnostic required');args.output.mkdir(parents=True)
    out=args.output/'replay.json';out.write_text(json.dumps({'schemaVersion':2,'kind':'target-skin-intensity-replay-diagnostic',
        **contract.binding(tp,target,'working'),'part':cfg['part'],'proof':value['proof'],'frozenInputs':value['frozenInputs']},indent=2)+'\n')
    print(json.dumps({'receipt':str(out.resolve()),'sha256':contract.sha(out)}))
