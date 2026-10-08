"""Bundled Python controller for a target-bound diagnostic CPU skin-lighting bake.

Original GLB/attributes/maps remain immutable. Camera-independent raw Blender
lighting feeds conservative bounded atlas variants and unlit palette previews.
No material is staged, compiled, installed, selected or approved.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
import target_contract as contract
import target_skin_lighting_contract as treatment


def array_sha(value):return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def filepin(path):return {'path':str(path.resolve()),'sha256':contract.sha(path),'byteCount':path.stat().st_size}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--toolchain',type=Path,required=True);parser.add_argument('--migration-receipt',type=Path,required=True)
    args=parser.parse_args();data=treatment.prepare(args.config);config=data['config'];output=args.output.resolve()
    contract.require(not output.exists(),'Fresh immutable lighting output required');output.mkdir();(output/'original-map-copies').mkdir();(output/'variants').mkdir();(output/'helpers').mkdir()
    frozen=dict(data['frozenInputs']);helpers=[]
    worker=Path(__file__).with_name('blender_target_skin_lighting.py');launcher=Path(__file__).with_name('launch_shared_tool.py')
    for source in (Path(__file__).resolve(),worker,Path(treatment.__file__).resolve(),Path(contract.__file__).resolve(),
            Path(__file__).with_name('target_part_pipeline.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py'),launcher,
            args.toolchain.resolve(),args.migration_receipt.resolve()):
        frozen[str(source)]=contract.sha(source);copied=output/'helpers'/source.name;shutil.copyfile(source,copied);helpers.append(filepin(copied))
    originals={};worker_materials={}
    for mid,entry in data['materials'].items():
        originals[str(mid)]={};worker_materials[str(mid)]={'role':entry['role'],'maps':{}}
        for name,(blob,pixels) in entry['maps'].items():
            path=output/'original-map-copies'/('material'+str(mid)+'-'+name+'-original.png');path.write_bytes(blob)
            originals[str(mid)][name]={**filepin(path),'pixelSha256':array_sha(pixels),'copiedEmbeddedBytesExact':True};worker_materials[str(mid)]['maps'][name]=filepin(path)
    np.savez_compressed(output/'exact-source-arrays.npz',positions=data['positions'],normals=data['normals'],uv=data['uv'],tangents=data['tangents'])
    worker_input=output/'worker-input.json';save(worker_input,{'kind':'target-skin-lighting-worker-input','diagnosticOnly':True,
        **contract.binding(data['targetPath'],data['target'],'working'),'part':config['part'],'source':filepin(data['source']),
        'arrays':filepin(output/'exact-source-arrays.npz'),'attachmentWorld':contract.frame(data['target'],contract.PART_JOINTS[config['part']],'working').tolist(),
        'materials':worker_materials,'primitives':data['primitives'],'lighting':config['lighting'],'frozenInputs':frozen})
    def run(operation,extra=()):
        command=[sys.executable,'-B',str(launcher),'--toolchain',str(args.toolchain.resolve()),'--migration-receipt',str(args.migration_receipt.resolve()),
            '--tool','blender','--output',str(output/(operation+'-launch')),'--','--python',str(worker),'--','--operation',operation,
            '--input',str(worker_input),'--output',str(output/operation),*extra]
        print('Launching verified Blender CPU '+operation,flush=True);subprocess.run(command,check=True)
        path=output/operation/'worker.json';result=json.loads(path.read_text(encoding='utf-8'));contract.require(result['input']['sha256']==contract.sha(worker_input),'Worker binding differs')
        return result
    baked=run('bake');raw_path=Path(baked['rawBake']['path']);contract.require(contract.sha(raw_path)==baked['rawBake']['sha256'],'Raw CPU atlas changed')
    raw=np.load(raw_path,allow_pickle=False)['rawLinearRGB'];samples,weights=treatment.surface_samples(data['positions'],data['uv'],data['triangleRoles'])
    field,mean=treatment.normalized_lighting(raw,samples,weights);setting=config['treatment'];size=config['lighting']['resolution']
    influence,coverage,garment,protected=treatment.masks(data['positions'],data['uv'],data['triangleRoles'],size,config['protectedRegions'],setting['maskGuardPixels'])
    np.savez_compressed(output/'linear-lighting-and-masks.npz',rawLinearRGB=raw,normalizedLuminance=field.astype('f4'),influence=influence.astype('f4'),coverage=coverage,garment=garment,protected=protected)
    Image.fromarray(np.rint(np.clip(field/2,0,1)*255).astype('u1')).save(output/'normalized-linear-lighting-display.png')
    Image.fromarray(np.rint(influence*255).astype('u1')).save(output/'influence.png');Image.fromarray(protected.astype('u1')*255).save(output/'protected.png')
    interior=treatment.sample(influence,samples)>.95;contract.require(interior.any(),'No independently treated interior remains after connector protection')
    original=data['originalIntensity'];palette=np.asarray(Image.open(config['palette']['path']).convert('RGB'));contract.require(palette.shape[1:]==(256,3) and len(palette)>8,'Installed palette dimensions differ')
    variants=[];preview_images=[]
    for strength in setting['strengths']:
        intensity=treatment.compose(original,field,influence,garment,protected,strength,setting['maxDarkenShades'],setting['maxBrightenShades']);slug=str(strength).replace('.','p')
        path=output/'variants'/('intensity-'+slug+'.png');Image.fromarray(intensity).save(path)
        row={'strength':strength,'untreatedParentSha256':contract.sha(data['source']),'parentGeometryReceiptSha256':contract.sha(data['sourceReceipt']),
            'intensity':filepin(path),'arraySha256':array_sha(intensity),'originalIntensityArraySha256':array_sha(original),
            'changedPixels':int(np.count_nonzero(intensity!=original)),'maximumDarkeningShades':int((original.astype(int)-intensity.astype(int)).max()),
            'maximumBrighteningShades':int((intensity.astype(int)-original.astype(int)).max()),'protectedPixelsExact':bool(np.array_equal(intensity[protected|garment],original[protected|garment])),
            'surfaceStats':treatment.weighted_stats(intensity,samples,weights),'fullyTreatedInteriorSurfaceStats':treatment.weighted_stats(intensity,samples[interior],weights[interior]),
            'paletteLookupDiagnostic':{},'derivedFromOriginalIndependently':True,'selected':False}
        for index in config['palette']['rows']:
            rgb=palette[index,intensity];pp=output/'variants'/('palette'+str(index)+'-'+slug+'.png');Image.fromarray(rgb).save(pp)
            row['paletteLookupDiagnostic'][str(index)]={'image':filepin(pp),'byteLuminanceStats':treatment.weighted_stats(rgb.astype(float)@treatment.LUMA,samples,weights),
                'stockNeckMatched':False,'clientGammaShaderMatched':False};preview_images.append({'strength':strength,'paletteRow':index,'image':filepin(pp)})
        variants.append(row)
    preview_manifest=output/'preview-input.json';save(preview_manifest,{'workerInputSha256':contract.sha(worker_input),'images':preview_images})
    previews=run('preview',('--previews',str(preview_manifest)))
    for path,expected in frozen.items():contract.require(contract.sha(path)==expected,'Frozen source/dependency changed during treatment: '+path)
    contract.load(data['targetPath'])
    result={'schemaVersion':2,'kind':'target-skin-lighting-diagnostic',**contract.binding(data['targetPath'],data['target'],'working'),
        'part':config['part'],'model':contract.model(data['target'],config['part']),'source':str(data['source']),'sourceSha256':contract.sha(data['source']),
        'sourceReceipt':str(data['sourceReceipt']),'sourceReceiptSha256':contract.sha(data['sourceReceipt']),'statureApplications':0,
        'untreatedParentSha256':contract.sha(data['source']),'normalInputReview':config['normalInputReview'],'materialRoles':config['materialRoles'],
        'sourceEmbeddedMaps':data['originalEmbeddedMaps'],'originalMapCopies':originals,'originalIntensityArraySha256':array_sha(original),
        'normalStrength':1,'normalBasisPolicy':'Authored N/T/W point attributes plus original RGB normal texture at strength1; no regenerated tangent basis; proper object-to-world transform.',
        'temporaryGeometryTransport':baked['geometryTransport'],'lighting':config['lighting'],'lightTransforms':baked['lightTransforms'],
        'bakePass':'DIFFUSE DIRECT, color=false, indirect=false, CPU4threads','cameraUsedForBake':False,'linearFieldSurfaceAreaWeightedMeanBeforeNormalization':mean,
        'lightingAtlas':filepin(output/'linear-lighting-and-masks.npz'),
        'atlasRowOrientation':'Top-left arrays/PNG sample raw GLTF V directly. Disposable Blender UV V=1-rawV once; bake image bottom-left rows reverse to top-left once. Source accessors stay exact.',
        'treatment':setting,'protectedRegions':config['protectedRegions'],'protectedPixels':int(protected.sum()),'garmentPixels':int(garment.sum()),
        'variants':variants,'unlitPaletteSurfacePreviews':previews['previews'],'frozenInputs':frozen,'helperSnapshots':helpers,
        'workerReceipts':{operation:filepin(output/operation/'worker.json') for operation in ('bake','preview')},
        'workerLaunchReceipts':{operation:filepin(output/(operation+'-launch')/'launch.json') for operation in ('bake','preview')},
        'sourceGeometryUvsNormalsTangentsIndicesAndMapsChanged':False,'garmentAndNeighborFilesChanged':False,
        'stageInterfaceImplemented':False,'nativeCompiled':False,'selected':False,'clientAccepted':False,'productionAccepted':False,
        'limitations':['Diagnostic shade bytes, not an accepted native PLT or rewritten GLB. No source/albedo/normal/ORM/rig or neighboring asset is altered.',
        'Bind-space directional shading travels with the body during animation and can conflict with live light or emphasize the wrong side; review both lighting/shader paths and motion.',
        'Bake can expose shape relief present in geometry/authored normals; it cannot create anatomy missing from them.',
        'Conservative connector/garment UV masks protect whole crossing triangles and expand zero protection; UV overlaps/filtering/mip boundaries need direct review.',
        'Shade normalization preserves average linear bake before bounded clipping; output palette3/8 brightness/neck match is not automatically calibrated.',
        'Known source normal defects survive untouched. Protected cap bands are not a normal repair or blanket hidden-defect acceptance.',
        'CPU seed/settings are pinned; cross-platform/library bitwise repeatability and actual client appearance are unproven.']}
    save(output/'lighting.json',result)
    save(output/'proposed-stage-interface.json',{'schemaVersion':1,'status':'proposal-only-not-implemented','proposedConfigKey':'skinIntensityTreatment',
        'requiredBinding':{'receipt':str(output/'lighting.json'),'receiptSha256':contract.sha(output/'lighting.json'),'targetContractSha256':contract.sha(data['targetPath']),
            'part':config['part'],'coordinateSpace':'working','untreatedParentSha256':contract.sha(data['source']),'geometryReceiptSha256':contract.sha(data['sourceReceipt']),
            'variantStrength':'explicit selected value plus intensity PNG hash'},
        'requiredGuards':['A separately reviewed selected descendant must match the exact target/rig revision, part, ownership, geometry and untouched parent.',
            'Normal pixels/strength1, raw ORM-green roughness, UV/P/N/T/W and all garment/neck/neighbor hashes stay exact.',
            'Compare independent strengths from untreated parent; require aoStrength=0 by default. Any AO composition needs a new explicit reviewed operation/receipt.',
            'Stage only skin intensity; fixed garment resources retain original colors and palettes. Verify intensity/layer serialization independently.',
            'Preserve original compiler receipts; native compile/attribute audit and effective runtime material evidence must point to the chosen descendant.',
            'Palette3/8 stock-neck/cumulative skin calibration, all boundary/mip filtering and actual lighting/HQ/motion/equipment checks remain gates.'],
        'stageToolChanged':False,'selectionOrApprovalCreated':False})
    print(json.dumps({'receipt':str(output/'lighting.json'),'sha256':contract.sha(output/'lighting.json'),'strengths':setting['strengths'],
        'contrastSpans':[{'strength':v['strength'],'relativeSpan':v['surfaceStats']['relativeSpan']} for v in variants],'selected':False}),flush=True)

if __name__=='__main__':main()
