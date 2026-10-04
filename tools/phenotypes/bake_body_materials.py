"""Explicit AO/roughness runtime descendants of a frozen Human body material set.

Geometry, original native compiler receipts, normal maps and fixed underwear
stay byte-exact. AO is baked into existing PLT shades using real palette rows;
it is never treated as a height texture. Output is an unaccepted trial.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from audit_body_material_inputs import plt_image, sampled
from stage_stock_part import require, sha, save


def srgb_linear(rgb):
    return np.where(rgb<=.04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)


def linear_srgb(rgb):
    return np.where(rgb<=.0031308, rgb*12.92, 1.055*np.maximum(rgb,0)**(1/2.4)-.055)


def palette_delta(shade, ao, palette, strength):
    """AO transfer in linear color; map back through both actual skin palettes.

    Average resulting shade deltas so a single recolorable PLT is retained.
    The explicit source AO strength is a linear data multiplier.
    """
    require(0<=strength<=.6 and np.isfinite(ao).all() and np.min(ao)>=0 and np.max(ao)<=1,
            'Invalid AO operation')
    if strength==0:
        return np.zeros(shade.shape,float)
    result=np.zeros(shade.shape,float)
    luma=np.array([.2126,.7152,.0722])
    # Installed palette rows have local reversals. A global monotone inverse
    # is invalid. Build a bounded local inverse, favoring the closest original
    # shade on ties; full-white AO is explicitly an identity operation.
    for row in (3,8):
        colors=palette[row]/255.
        lut=colors@luma
        table=np.zeros((256,256),float)
        factors=(1-strength)+strength*np.arange(256)/255.
        for index in range(256):
            options=np.arange(index,max(-1,index-49),-1)
            target=linear_srgb(srgb_linear(colors[index])[None,:]*factors[:,None])@luma
            choice=np.argmin(np.abs(target[:,None]-lut[options][None,:]),axis=1)
            table[index]=options[choice]-index
            table[index,255]=0
        coordinate=ao*255.;lo=np.floor(coordinate).astype(int);hi=np.minimum(lo+1,255)
        result+=(table[shade,lo]*(1-coordinate+lo)+table[shade,hi]*(coordinate-lo))/2
    return result


def ownership_mask(samples, part, size, band, connector_planes=None):
    """Conservative atlas influence; protected attachment bands remain unchanged.

    UV overlap conflicts choose the smallest influence. Mask is material-only;
    no skin/cloth or animation ownership is transferred by this operation.
    """
    p=samples['position'];uv=samples['uv'];centers=p.mean(1)
    require(np.isfinite(band) and band>0,'Positive connector band required')
    z=p[:,:,2]; zlo,zhi=float(z.min()),float(z.max())
    if connector_planes is None:
        t=np.clip(np.minimum(centers[:,2]-zlo,zhi-centers[:,2])/band,0,1)
    else:
        require(isinstance(connector_planes,list) and 1<=len(connector_planes)<=4,
                'Declare one to four measured outward connector planes')
        t=np.ones(len(p))
        for plane in connector_planes:
            normal=np.asarray(plane['outwardNormal'],float);offset=float(plane['offsetMetres'])
            require(normal.shape==(3,) and np.isfinite(normal).all() and np.isfinite(offset)
                    and abs(np.linalg.norm(normal)-1)<1e-9,'Unit finite connector plane required')
            # Any outward corner protects its whole UV triangle, plus the existing
            # bilinear guard. Include the entire hidden extension beyond the joint.
            inward=-(p@normal-offset).max(axis=1)
            t=np.minimum(t,np.clip(inward/band,0,1))
    t=t*t*(3-2*t)
    # Additional stock-axis chest shoulder/neck overlap protection.
    if part=='chest':
        shoulder=np.clip((.223-np.abs(centers[:,0]))/.03,0,1)
        neck=np.clip((.43-centers[:,2])/.04,0,1)
        t*=np.minimum(shoulder,neck)
    mask=Image.new('L',size,0);draw=ImageDraw.Draw(mask)
    protect=Image.new('L',size,0);pd=ImageDraw.Draw(protect)
    for coords,value in sorted(zip(uv,t),key=lambda row:row[1],reverse=True):
        points=[(float(u)*(size[0]-1),(1-float(v))*(size[1]-1)) for u,v in coords]
        draw.polygon(points,fill=int(round(255*value)))
        if value<.001:pd.polygon(points,fill=255)
    # Extend exact-zero connector protection by two texels for bilinear/mipmap guards.
    protected=np.asarray(protect.filter(ImageFilter.MaxFilter(5)))>0
    a=np.asarray(mask.filter(ImageFilter.GaussianBlur(.6)),dtype=float)/255.
    a[protected]=0
    return a,protected


def mtr_roughness(text, resref):
    require(len(resref)<=16 and re.fullmatch('[a-z0-9_]+',resref),'Invalid roughness resref')
    require(not re.search(r'(?mi)^\s*texture[0345]\s',text), 'Unexpected existing slot ownership')
    require(re.search(r'(?mi)^\s*renderhint\s+NormalTangents\s*$',text),'NormalTangents required')
    require(re.search(r'(?mi)^\s*texture1\s+\S+',text),'Preserved normal binding required')
    # Explicitly choose zero, the checked shader's map discriminator.
    value=re.sub(r'(?mi)^\s*parameter float Roughness\s+[^\n]+',
                 'parameter float Roughness 0',text)
    require(value!=text,'Expected positive roughness override')
    return value.rstrip()+'\ntexture3 '+resref+'\n'


def archive_tool_inputs(input_hashes, output):
    frozen_inputs={};tool_origins={}
    for number,(name,pin) in enumerate(input_hashes.items()):
        source=Path(name)
        require(sha(source)==pin,'Input changed before tool archival: '+name)
        if source.suffix.lower()=='.py':
            target=output/'frozen-tools'/(str(number)+'-'+source.name)
            target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
            require(sha(target)==pin,'Executed tool archive differs')
            frozen_inputs[str(target.resolve())]=pin
            tool_origins[str(source.resolve())]={'archive':str(target.resolve()),'sha256':pin}
        else:frozen_inputs[name]=pin
    return frozen_inputs,tool_origins


def run(config_path, output):
    config=json.loads(config_path.read_text())
    require(config.get('schemaVersion')==1 and config.get('kind')=='human-male-material-trial',
            'Explicit scoped material configuration required')
    require(type(config.get('useAO')) is bool and type(config.get('useRoughness')) is bool,
            'Explicit useAO/useRoughness flags required before creating a material descendant')
    require(not output.exists(),'Fresh descendant required')
    for path,expected in config['inputHashes'].items():require(sha(path)==expected,'Stale input: '+path)
    audit=json.loads(Path(config['audit']).read_text());base=Path(config['baselineResources'])
    palette=np.asarray(Image.open(config['palette']).convert('RGB'))
    before={p.name:sha(p) for p in base.iterdir() if p.is_file()}
    require(before==config['baselineResourceHashes'],'Unexpected/stale baseline resource')
    require(set(audit['parts'])==set(config['partSettings']),'Part selection differs')
    output.mkdir(parents=True);resources=output/'resources';shutil.copytree(base,resources)
    rows={};changed=set();added=set()
    for part,record in audit['parts'].items():
        model=record['model'];settings=config['partSettings'][part]
        sample_path=Path(config['audit']).parent/part/'native-uv-samples.npz'
        require(sha(sample_path)==record['sampleSha256'],'Stale UV sample')
        samples=np.load(sample_path,allow_pickle=False)
        data=(base/(model+'.plt')).read_bytes();old=plt_image(data);new=old.copy()
        mask,protected=ownership_mask(samples,part,(old.shape[1],old.shape[0]),settings['connectorBandMetres'],
                                      settings.get('connectorPlanes'))
        ao=np.asarray(Image.open(record['images']['ao']['path']).convert('RGB'))[:,:,0]/255.
        ao=1-record['material']['occlusionTexture'].get('strength',1)*(1-ao)
        strength=settings['aoStrength'] if config['useAO'] else 0
        delta=palette_delta(old[:,:,0],ao,palette,strength)
        sampleuv=samples['sampleUV'];weights=np.repeat(samples['area']/4,4)
        # Mean compensation only within changed atlas influence, then bounded
        # to avoid invented bright areas; connector texels remain exact.
        mean_delta=float(np.average(sampled(delta*mask,sampleuv),weights=weights))
        mean_mask=float(np.average(sampled(mask,sampleuv),weights=weights))
        compensation=-mean_delta/max(mean_mask,1e-9)
        operation=np.clip(delta+compensation,-settings['maxDarkenShades'],settings['maxBrightenShades'])*mask
        require(np.isfinite(operation).all(),'Nonfinite shade correction')
        skin=old[:,:,1]==0
        raw=np.rint(old[:,:,0].astype(float)+operation)
        new[:,:,0][skin]=np.clip(raw[skin],0,255).astype(np.uint8)
        require(np.array_equal(new[:,:,1],old[:,:,1]) and np.array_equal(new[~skin],old[~skin]),
                'Layer/fixed-color ownership changed')
        require(np.array_equal(new[protected],old[protected]),'Protected connector pixels changed')
        payload=data[:24]+new[::-1].tobytes()
        (resources/(model+'.plt')).write_bytes(payload)
        if payload!=data:changed.add(model+'.plt')
        before_samples=sampled(old[:,:,0],sampleuv);after_samples=sampled(new[:,:,0],sampleuv)
        def stats(a):
            mean=float(np.average(a,weights=weights));return {'mean':mean,
                'std':float(np.sqrt(np.average((a-mean)**2,weights=weights))),'min':float(a.min()),'max':float(a.max())}
        row={'aoStrength':strength,'connectorBandMetres':settings['connectorBandMetres'],
             'connectorPlanes':settings.get('connectorPlanes'),
             'meanCompensationShades':compensation,'meanCalibrationIncludesHiddenSurfaces':True,
             'beforeUVShade':stats(before_samples),'afterUVShade':stats(after_samples),
             'changedPixels':int(np.count_nonzero(new[:,:,0]!=old[:,:,0])),
             'clampedSkinPixels':int(np.count_nonzero(skin&((raw<0)|(raw>255)))),
             'connectorProtectedPixels':int(protected.sum()),'layersExact':True}
        masks=output/'masks';masks.mkdir(exist_ok=True)
        Image.fromarray(np.rint(mask*255).astype(np.uint8)).save(masks/(part+'-influence.png'))
        if config['useRoughness']:
            rawrough=np.asarray(Image.open(record['images']['orm']['path']).convert('RGB'))[:,:,1]
            factor=record['material']['pbrMetallicRoughness'].get('roughnessFactor',1)
            rough=np.rint(rawrough.astype(float)*factor).clip(0,255).astype(np.uint8)
            name=model+'r';target=resources/(name+'.tga')
            require(not target.exists(),'Roughness resource collision')
            Image.fromarray(rough).convert('RGB').save(target)
            mtr=resources/(model+'.mtr');mtr.write_text(mtr_roughness(mtr.read_text(),name),encoding='ascii')
            changed.add(mtr.name);added.add(target.name)
            require(np.array_equal(np.asarray(Image.open(target))[:,:,0],rough),'Roughness channel altered')
            row['roughnessFactor']=factor;row['roughnessChannel']='ORM green -> texture3 red, linear data'
        rows[part]=row
    after={p.name:sha(p) for p in resources.iterdir() if p.is_file()}
    require(set(after)==set(before)|added,'Unexpected resource addition/removal')
    require({name for name in before if before[name]!=after[name]}==changed,'Undeclared resource edit')
    require(all(before[n]==after[n] for n in before if n.endswith(('.mdl','n.tga','f.tga','f.mtr'))),
            'Geometry, normal or fixed underwear changed')
    for path,expected in config['inputHashes'].items():require(sha(path)==expected,'Input changed during operation')
    shutil.copyfile(__file__,output/'executed-bake.py');shutil.copyfile(config_path,output/'executed-config.json')
    # Historical material evidence binds the implementation that actually ran,
    # not whatever a reusable helper is edited into during the next part sprint.
    # Actual selected geometry, maps and receipts remain at their pinned origins.
    frozen_inputs,tool_origins=archive_tool_inputs(config['inputHashes'],output)
    frozen_inputs[str((output/'executed-bake.py').resolve())]=sha(output/'executed-bake.py')
    save(output/'material-operation.json',{'schemaVersion':1,'kind':'runtime-body-ao-roughness',
         'configurationSha256':sha(config_path),'frozenInputs':frozen_inputs,
         'executedToolOrigins':tool_origins,
         'parentResourceHashes':before,'effectiveResourceHashes':after,'changedResources':sorted(changed),
         'addedResources':sorted(added),'parts':rows,'nativeGeometryAndNormalsExact':True,
         'pltDiffuseOverride':False,'heightMapUsed':False,'clientAccepted':False,
         'algorithm':'Linear palette-color AO -> inverse actual row3/8 luminance -> mean-compensated bounded shade delta, protected connector mask; explicit ORM-G roughness binding.',
         'limitations':'UV-area calibration includes hidden surfaces. Actual client and seam tests remain required.'})
    print(json.dumps({'output':str(output),'changed':sorted(changed),'added':sorted(added),'parts':rows},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run(args.config,args.output)
