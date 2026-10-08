"""Fresh target-bound diagnostic C1 skin lighting and explicit UV chart padding.

Uses the immutable original raw CPU bake; no new shading bake/GPU/client/stage.
Original geometry/maps and v3 evidence stay unchanged and unselected.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
import target_contract as contract
import target_skin_lighting_contract as original_helper
import skin_lighting_atlas as atlas


def sha(p):return contract.sha(p)
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def pin(p):return {'path':str(p.resolve()),'sha256':sha(p),'byteCount':p.stat().st_size}
def checked(row):
    p=Path(row['path']).resolve();contract.require(sha(p)==row['sha256'],'Frozen descendant input changed: '+str(p));return p

def stats(image,samples,weights):
    values=atlas.sample_texels(image.astype(float),samples,True);sort=np.argsort(values);v=values[sort];w=weights[sort];cdf=np.cumsum(w)/w.sum()
    mean=float(np.average(values,weights=weights));p05,p95=np.interp([.05,.95],cdf,v)
    return {'mean':mean,'p05':float(p05),'p95':float(p95),'relativeSpan':float((p95-p05)/mean),'minimum':float(values.min()),'maximum':float(values.max())}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--toolchain',type=Path,required=True);parser.add_argument('--migration-receipt',type=Path,required=True);args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8'));contract.require(set(config)=={'schemaVersion','kind','diagnosticOnly','parentLighting','sourceConfig','paddingRadiusPixels','maskGuardPixels','positionOverlapToleranceMeters','normalOverlapTolerance','requiredZeroSourceFaces'},'Explicit fresh descendant controls required')
    contract.require(config['schemaVersion']==1 and config['kind']=='target-skin-lighting-c1-padding-diagnostic' and config['diagnosticOnly'] is True,'Explicit diagnostic C1 descendant required')
    original_helper.finite(config['paddingRadiusPixels'],1,32,'padding radius');original_helper.finite(config['maskGuardPixels'],1,4,'mask guard')
    contract.require(isinstance(config['paddingRadiusPixels'],int) and isinstance(config['maskGuardPixels'],int),'Integer padding/guard required')
    original_helper.finite(config['positionOverlapToleranceMeters'],1e-7,1e-5,'position overlap tolerance');original_helper.finite(config['normalOverlapTolerance'],1e-7,1e-4,'normal overlap tolerance')
    data=original_helper.prepare(checked(config['sourceConfig']));parent_path=checked(config['parentLighting']);parent=json.loads(parent_path.read_text())
    contract.require(parent['kind']=='target-skin-lighting-diagnostic' and parent['sourceSha256']==sha(data['source']) and parent['sourceReceiptSha256']==sha(data['sourceReceipt']),'Lighting parent/geometry association differs')
    contract.verify_binding(parent,data['targetPath'],data['target'],'working');contract.require(parent['normalStrength']==1 and parent['cameraUsedForBake'] is False and parent['lighting']['device']=='CPU','Original CPU/normal contract differs')
    frozen={**parent['frozenInputs'],**data['frozenInputs'],str(parent_path):sha(parent_path),str(args.config.resolve()):sha(args.config)}
    output=args.output.resolve();contract.require(not output.exists(),'Fresh C1 descendant output required');output.mkdir();(output/'variants').mkdir();(output/'helpers').mkdir()
    for source in (Path(__file__).resolve(),Path(atlas.__file__).resolve(),Path(original_helper.__file__).resolve(),args.toolchain.resolve(),args.migration_receipt.resolve()):
        frozen[str(source)]=sha(source);shutil.copyfile(source,output/'helpers'/source.name)
    raw_path=checked(parent['lightingAtlas']);frozen[str(raw_path)]=sha(raw_path);raw=np.load(raw_path,allow_pickle=False)['rawLinearRGB']
    samples,weights=original_helper.surface_samples(data['positions'],data['uv'],data['triangleRoles']);raw_luma=raw.astype(float)@original_helper.LUMA
    mean=float(np.average(atlas.sample_texels(raw_luma,samples,True),weights=weights));contract.require(np.isfinite(mean) and mean>1e-8,'Unlit parent field');field=raw_luma/mean
    print('Rasterizing target attachment geometry at actual UV texel centers with C1 protection',flush=True)
    mask=atlas.geometry_masks(data['positions'],data['normals'],data['uv'],data['triangleRoles'],2048,data['config']['protectedRegions'],config['maskGuardPixels'],config['positionOverlapToleranceMeters'],config['normalOverlapTolerance'])
    zero=[];bary=np.asarray([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    for face in config['requiredZeroSourceFaces']:
        contract.require(isinstance(face,int) and 0<=face<len(data['positions']),'Explicit valid known-defect face required');values=atlas.sample_texels(mask['influence'],bary@data['uv'][face],True)
        contract.require(np.max(values)==0,'Known source-defect face escaped protection');zero.append({'sourceFace':face,'fourInteriorInfluenceSamples':values.tolist(),'normalRepairApplied':False,'accepted':False})
    print('Deriving explicit skin-only chart padding lineage',flush=True)
    forbidden=mask['protected']|mask['garment']|mask['ambiguous'];lineage,distance,destination=atlas.pad_lineage(mask['coverage'],forbidden,config['paddingRadiusPixels'])
    np.savez_compressed(output/'c1-mask-and-padding-lineage.npz',**mask,normalizedLuminance=field.astype('f4'),paddingSourceTexelIndex=lineage,paddingSteps=distance,paddingDestination=destination)
    Image.fromarray(np.rint(mask['influence']*255).astype('u1')).save(output/'influence.png');Image.fromarray(forbidden.astype('u1')*255).save(output/'forbidden.png');Image.fromarray(destination.astype('u1')*255).save(output/'padding-destination.png')
    original=data['originalIntensity'];palette=np.asarray(Image.open(data['config']['palette']['path']).convert('RGB'));setting=data['config']['treatment'];rows=[];preview_images=[]
    interior=atlas.sample_texels(mask['influence'],samples,True)>.95;contract.require(interior.any(),'No safely treated surface remains')
    for strength in setting['strengths']:
        treated=original_helper.compose(original,field,mask['influence'],mask['garment'],mask['protected']|mask['ambiguous'],strength,setting['maxDarkenShades'],setting['maxBrightenShades'])
        pixels=atlas.apply_padding(original,treated,lineage,destination,strength);contract.require(np.array_equal(pixels[forbidden],original[forbidden]),'Protection changed after padding')
        if strength==0:contract.require(np.array_equal(pixels,original),'Untreated reference changed')
        slug=str(strength).replace('.','p');path=output/'variants'/('intensity-'+slug+'.png');Image.fromarray(pixels).save(path)
        changed=pixels.astype(int)-original.astype(int);surface=mask['coverage'];row={'strength':strength,'intensity':pin(path),'untreatedParentSha256':sha(data['source']),
            'independentUntreatedParent':True,'protectedPixelsExact':True,'knownDefectSamplesExactZero':True,
            'changedSurfacePixels':int(np.count_nonzero(changed[surface])),'changedPaddingPixels':int(np.count_nonzero(changed[destination])),
            'maximumSurfaceDarkening':int((-changed[surface]).max()),'maximumSurfaceBrightening':int(changed[surface].max()),
            'maximumPaddingAbsoluteChange':int(abs(changed[destination]).max()),'surfaceStats':stats(pixels,samples,weights),'interiorStats':stats(pixels,samples[interior],weights[interior]),'paletteLookupDiagnostic':{}}
        for index in (3,8):
            rgb=palette[index,pixels];pp=output/'variants'/('palette'+str(index)+'-'+slug+'.png');Image.fromarray(rgb).save(pp)
            row['paletteLookupDiagnostic'][str(index)]={'image':pin(pp),'byteLuminanceStats':stats(rgb.astype(float)@original_helper.LUMA,samples,weights),'stockNeckMatched':False,'clientShaderMatched':False}
            preview_images.append({'strength':strength,'paletteRow':index,'image':pin(pp)})
        rows.append(row)
    # Reuse only the immutable original CPU worker's exact geometry job for an
    # unlit render of the fresh atlases. No new bake/normal/lighting scene change.
    worker_input=parent_path.parent/'worker-input.json';worker=Path(__file__).with_name('blender_target_skin_lighting.py');launcher=Path(__file__).with_name('launch_shared_tool.py')
    manifest=output/'preview-input.json';save(manifest,{'workerInputSha256':sha(worker_input),'images':preview_images})
    for p in (worker_input,worker,launcher):frozen[str(p.resolve())]=sha(p)
    subprocess.run([sys.executable,'-B',str(launcher),'--toolchain',str(args.toolchain.resolve()),'--migration-receipt',str(args.migration_receipt.resolve()),'--tool','blender',
        '--output',str(output/'preview-launch'),'--','--python',str(worker),'--','--operation','preview','--input',str(worker_input),'--output',str(output/'preview'),'--previews',str(manifest)],check=True)
    rendered=json.loads((output/'preview/worker.json').read_text())
    for p,h in frozen.items():contract.require(sha(p)==h,'Frozen source changed during descendant: '+p)
    contract.load(data['targetPath'])
    result={'schemaVersion':2,'kind':'target-skin-lighting-c1-padding-diagnostic',**contract.binding(data['targetPath'],data['target'],'working'),
        'part':data['config']['part'],'source':str(data['source']),'sourceSha256':sha(data['source']),'sourceReceipt':str(data['sourceReceipt']),'sourceReceiptSha256':sha(data['sourceReceipt']),
        'parentLighting':pin(parent_path),'config':pin(args.config.resolve()),'operationCount':2,'operationOrder':['Independent original-intensity bounded diffuse lighting with geometry C1 mask','Explicit nearest skin-only shade padding of empty chart texels'],
        'newCpuLightingBakePerformed':False,'normalMapStrength':1,'geometryAndOriginalMapBytesChanged':False,'uvAccessorsChanged':False,'shaderTangentBasisChanged':False,
        'normalizationMean':mean,'samplingPolicy':'Raw GLTF top-left, x=u*width-.5/y=v*height-.5 bilinear texel-center REPEAT, no image/V double flip.',
        'maskPolicy':'Per-texel barycentric attachment geometry; exactlyzero measured joint bands; C1 smoothstep outside; cloth/inequivalent geometry or authored-normal overlaps plus guard protected.',
        'paddingPolicy':'8-neighbor geodesic max16steps, deterministic lowest original seed index per shortest path; empty atlas destinations only, blocked by protected/garment/ambiguous; strength0 remains original.',
        'paddingBoundsPolicy':'Bounded shade changes apply to mapped skin. Explicit empty padding texels copy nearest treated skin value and may differ more from unused source bytes; they are not face ownership or changed original maps.',
        'maskAndPaddingLineage':pin(output/'c1-mask-and-padding-lineage.npz'),'coveragePixels':int(mask['coverage'].sum()),'ambiguousPixels':int(mask['ambiguous'].sum()),
        'strictZeroPixels':int(mask['strictZero'].sum()),'protectedPixels':int(mask['protected'].sum()),'paddingDestinationPixels':int(destination.sum()),
        'knownSourceDefectProtection':zero,'variants':rows,'previews':rendered['previews'],'previewWorkerReceipt':pin(output/'preview/worker.json'),'previewLaunch':pin(output/'preview-launch/launch.json'),
        'frozenInputs':frozen,'stageInterfaceImplemented':False,'anatomicalOrientationAccepted':False,'nativeCompiled':False,'selected':False,'clientAccepted':False,
        'limits':['Only a diagnostic technical lighting/padding descendant, not selected anatomy/materials. No stage/native/client operation.',
        'Pixel-center masks and padding address chart filtering but do not prove actual engine mips/PLT behavior or remove a source topology/normal defect.',
        'Bind-space directional paint still moves with animation and may conflict with real lights or a mirrored limb.',
        'Palette3/8 stock-neck and all neighbor/fixed-cloth brightness/boundary checks remain required. Unknown overlap texels stay original.']}
    save(output/'lighting-descendant.json',result);print(json.dumps({'receipt':str(output/'lighting-descendant.json'),'sha256':sha(output/'lighting-descendant.json'),'ambiguousPixels':result['ambiguousPixels'],'paddingPixels':result['paddingDestinationPixels'],'selected':False}),flush=True)

if __name__=='__main__':main()
