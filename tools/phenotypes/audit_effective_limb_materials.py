"""Independent read-only proof of current four-arm native material operations.

Actual calibration/bake bytes must match exactly. Bilateral PLT equality is
reported, never assumed or repaired; each side must reproduce its own measured
connector mask, with all zero-influence/protected texels unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


OFFSETS = {'bicepl':-10,'bicepr':-10,'forel':11,'forer':11}
JOINT_PLANES = {
    'bicepl':[(0,0,1,0),(0,0,-1,.301921)],
    'bicepr':[(0,0,1,0),(0,0,-1,.301921)],
    'forel':[(0,0,1,0),(0,0,-1,.291763)],
    'forer':[(0,0,1,0),(0,0,-1,.291763)]}


def require(condition,message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    return {'path':str(Path(path).resolve()),'sha256':sha(path)}


def decode_plt(data):
    require(len(data)>=24 and data[:8]==b'PLT V1  ','Invalid PLT')
    layers,reserved,w,h=struct.unpack_from('<IIII',data,8)
    require(layers==10 and reserved==0 and w>0 and h>0 and len(data)==24+2*w*h,'Invalid PLT dimensions/length')
    result=np.frombuffer(data,np.uint8,offset=24).reshape(h,w,2)[::-1].copy()
    require(np.all(result[:,:,1]<10),'Invalid PLT layers')
    return result


def calibration_proof(before,after,offset):
    require(type(offset) is int,'Integer calibration required')
    require(before[:24]==after[:24],'Calibration changed PLT header')
    p,q=decode_plt(before),decode_plt(after)
    require(p.shape==q.shape,'Calibration changed PLT dimensions')
    skin=p[:,:,1]==0
    expected=p.copy()
    values=p[:,:,0].astype(np.int16)+offset
    expected[:,:,0][skin]=np.clip(values[skin],0,255).astype(np.uint8)
    require(np.array_equal(expected,q),'Calibration is not the exact declared layer0 integer offset')
    return {'offset':offset,'skinPixels':int(skin.sum()),'layersExact':True,'nonSkinExact':True,
            'changedShadePixels':int(np.count_nonzero(p[:,:,0]!=q[:,:,0])),
            'lowClampedPixels':int(np.count_nonzero(skin&(values<0))),
            'highClampedPixels':int(np.count_nonzero(skin&(values>255)))}


def verify_pins(pins,tool_origins,inputs):
    canonical_origins={}
    for name,origin in tool_origins.items():
        path=Path(name).resolve()
        require(path not in canonical_origins or canonical_origins[path]==origin,
                'Conflicting historical helper origins: '+name)
        canonical_origins[path]=origin
    archived=[]
    for name,pin in pins.items():
        path=Path(name).resolve()
        if path.suffix.lower()=='.py' and path in canonical_origins:
            origin=canonical_origins[path]
            require(origin['sha256']==pin,'Historical helper archive pin differs: '+name)
            path=Path(origin['archive']).resolve()
            archived.append({'origin':name,'archive':str(path),'sha256':pin})
        require(sha(path)==pin,'Changed actual input/archive: '+str(path))
        inputs[str(path)]=pin
    return archived


def connector_mask(position,uv,size,band,planes):
    """Independent published policy: whole-face outward ownership, conservative UV conflicts."""
    require(band>0 and np.isfinite(position).all() and np.isfinite(uv).all(),'Invalid measured connector data')
    value=np.ones(len(position),float)
    for normal,offset in planes:
        n=np.array(normal,float)
        require(n.shape==(3,) and abs(np.linalg.norm(n)-1)<1e-9,'Invalid connector plane')
        inward=offset-np.max(position@n,axis=1)
        value=np.minimum(value,np.clip(inward/band,0,1))
    value=value*value*(3-2*value)
    atlas=Image.new('L',size,0);draw=ImageDraw.Draw(atlas)
    protect=Image.new('L',size,0);pd=ImageDraw.Draw(protect)
    for index in np.argsort(-value,kind='stable'):
        polygon=[(float(u)*(size[0]-1),(1-float(v))*(size[1]-1)) for u,v in uv[index]]
        draw.polygon(polygon,fill=int(round(255*value[index])))
        if value[index]<.001:
            pd.polygon(polygon,fill=255)
    protected=np.array(protect.filter(ImageFilter.MaxFilter(5)))>0
    mask=np.array(atlas.filter(ImageFilter.GaussianBlur(.6)),np.uint8)
    mask[protected]=0
    return mask,protected


def sampled(image,uv):
    uv=np.clip(uv,0,1)
    x=uv[:,0]*(image.shape[1]-1);y=(1-uv[:,1])*(image.shape[0]-1)
    ix=np.floor(x).astype(int);iy=np.floor(y).astype(int)
    jx=np.minimum(ix+1,image.shape[1]-1);jy=np.minimum(iy+1,image.shape[0]-1)
    fx=x-ix;fy=y-iy
    taps=np.stack([image[iy,ix],image[iy,jx],image[jy,ix],image[jy,jx]],axis=1)
    weights=np.stack([(1-fx)*(1-fy),fx*(1-fy),(1-fx)*fy,fx*fy],axis=1)
    return np.sum(taps*weights,axis=1)


def palette_delta(shade,ao,palette,strength):
    require(0<=strength<=.6 and np.isfinite(ao).all() and ao.min()>=0 and ao.max()<=1,'Invalid AO')
    if strength==0:
        return np.zeros(shade.shape,float)
    result=np.zeros(shade.shape,float)
    factors=(1-strength)+strength*np.arange(256)/255.
    luma=np.array([.2126,.7152,.0722])
    for row in [3,8]:
        colors=palette[row].astype(float)/255.
        linear=np.where(colors<=.04045,colors/12.92,((colors+.055)/1.055)**2.4)
        luminance=colors@luma
        table=np.empty((256,256),float)
        for original in range(256):
            candidates=np.arange(original,max(-1,original-49),-1)
            target=linear[original][None,:]*factors[:,None]
            nonlinear=np.where(target<=.0031308,target*12.92,1.055*np.maximum(target,0)**(1/2.4)-.055)@luma
            choices=np.abs(nonlinear[:,None]-luminance[candidates][None,:]).argmin(axis=1)
            table[original]=candidates[choices]-original
            table[original,255]=0
        q=ao*255;lo=np.floor(q).astype(int);hi=np.minimum(lo+1,255)
        result+=(table[shade,lo]*(1-q+lo)+table[shade,hi]*(q-lo))/2
    return result


def shade_bounds(before,after,mask,protected,darken,brighten):
    require(before.shape==after.shape and mask.shape==before.shape[:2],'Shade atlas shape differs')
    delta=after[:,:,0].astype(np.int16)-before[:,:,0].astype(np.int16)
    skin=before[:,:,1]==0
    layer_errors=int(np.count_nonzero(before[:,:,1]!=after[:,:,1]))
    fixed_errors=int(np.count_nonzero(np.any(before!=after,axis=2)&~skin))
    zero_errors=int(np.count_nonzero((mask==0)&(delta!=0)))
    protected_errors=int(np.count_nonzero(protected&(delta!=0)))
    require(layer_errors==fixed_errors==zero_errors==protected_errors==0,'Layer/fixed/zero-mask/protected pixels changed')
    require(delta[skin].min()>=-darken and delta[skin].max()<=brighten,'AO shade changes exceed declared limits')
    return {'layersExact':True,'nonSkinExact':True,'publishedZeroMaskPixels':int(np.count_nonzero(mask==0)),
      'publishedZeroMaskDiscrepancyPixels':zero_errors,'protectedConnectorPixels':int(protected.sum()),
      'protectedConnectorDiscrepancyPixels':protected_errors,'changedShadePixels':int(np.count_nonzero(delta)),
      'actualShadeDeltaRange':[int(delta.min()),int(delta.max())],
      'declaredShadeDeltaLimits':[-darken,brighten]}


def compare_pair(left,right,lmask,rmask,lraw,rraw):
    delta=left[:,:,0].astype(int)-right[:,:,0].astype(int)
    indices=np.argwhere(delta!=0)
    return {'paletteBytesExact':np.array_equal(left,right),
      'shadeDifferencePixels':int(len(indices)),'maximumAbsoluteShadeDifference':int(abs(delta).max()),
      'layerDifferencePixels':int(np.count_nonzero(left[:,:,1]!=right[:,:,1])),
      'maskDifferencePixels':int(np.count_nonzero(lmask!=rmask)),
      'maximumAbsoluteMaskDifference':int(abs(lmask.astype(int)-rmask.astype(int)).max()),
      'shadeDifferencesInEitherZeroMask':int(np.count_nonzero((delta!=0)&((lmask==0)|(rmask==0)))),
      'examples':[{'y':int(y),'x':int(x),'leftShade':int(left[y,x,0]),'rightShade':int(right[y,x,0]),
        'leftMask':int(lmask[y,x]),'rightMask':int(rmask[y,x]),
        'leftBeforeRoundShade':float(lraw[y,x]),'rightBeforeRoundShade':float(rraw[y,x])}
        for y,x in indices[:16]]}


def run(args):
    output=Path(args.output).resolve()
    require(not output.exists(),'Use a fresh independent audit output')
    calibration_path=Path(args.calibration).resolve();operation_path=Path(args.operation).resolve()
    converted=Path(args.converted).resolve();accepted_path=Path(args.accepted_selection).resolve()
    preserved_path=Path(args.preserved_inventory).resolve()
    require(all(p not in output.parents and p!=output for p in [converted,calibration_path.parent,operation_path.parent]),
            'Audit output must be outside source stages')
    inputs={str(p):sha(p) for p in [calibration_path,operation_path,accepted_path,preserved_path,Path(__file__).resolve()]}
    calibration=json.loads(calibration_path.read_text());operation=json.loads(operation_path.read_text())
    require(calibration['kind']=='new-limb-skin-calibration' and set(calibration['parts'])==set(OFFSETS),
            'Exact current four-arm calibration required')
    require(operation['kind']=='runtime-body-ao-roughness' and set(operation['parts'])==set(OFFSETS),
            'Exact current four-arm operation required')
    origins=operation['executedToolOrigins']
    archived=verify_pins(calibration['frozenInputs'],origins,inputs)
    verify_pins(operation['frozenInputs'],{},inputs)
    for origin,pin in origins.items():
        require(operation['frozenInputs'].get(pin['archive'])==pin['sha256'],'Archive is not part of actual operation inputs')
    config_path=operation_path.parent/'executed-config.json'
    require(sha(config_path)==operation['configurationSha256'],'Actual executed material config changed')
    inputs[str(config_path)]=sha(config_path);config=json.loads(config_path.read_text())
    require(config['useAO'] is True and config['useRoughness'] is True,'Current complete AO/roughness treatment required')
    require(set(config['partSettings'])==set(OFFSETS),'Different bake part set')
    cal_config_path=next(Path(p) for p in calibration['frozenInputs'] if Path(p).name=='arm-skin-calibration-config-v1.json')
    cal_config=json.loads(cal_config_path.read_text())
    stages={r['part']:r for r in cal_config['stages']}
    baseline=Path(config['baselineResources']);effective=operation_path.parent/'resources'
    require({p.name:sha(p) for p in baseline.iterdir()}==operation['parentResourceHashes']==config['baselineResourceHashes'],
            'Calibrated operation baseline changed')
    require({p.name:sha(p) for p in effective.iterdir()}==operation['effectiveResourceHashes'],'Baked operation resource changed')
    material_audit_path=Path(config['audit']);material_audit=json.loads(material_audit_path.read_text())
    inputs[str(material_audit_path.resolve())]=sha(material_audit_path)
    palette_path=Path(config['palette']);palette=np.asarray(Image.open(palette_path).convert('RGB'))
    require(palette.shape[1:]==(256,3) and len(palette)>8,'Actual skin palette missing')
    inputs[str(palette_path.resolve())]=sha(palette_path)
    inv_path=converted/'effective-material-inventory.json';inv=json.loads(inv_path.read_text())
    native_path=converted/'native-compile.json';native=json.loads(native_path.read_text())
    inputs.update({str(inv_path):sha(inv_path),str(native_path):sha(native_path)})
    require(len(inv['resourceHashes'])==62,'Current native twelve requires exactly62 resources')
    actual={p.name:sha(p) for p in (converted/'resources').iterdir()}
    require(actual==inv['resourceHashes'],'Actual native resources differ from current inventory')
    require(not any(n.endswith('.2da') or n=='pmh0.mdl' or n.startswith(('a_ba','a_fa','sr_a')) for n in actual),
            'Table/root/animation contamination')
    accepted=json.loads(accepted_path.read_text())['accepted6ResourceHashes']
    require(len(accepted)==32 and all(actual.get(n)==pin for n,pin in accepted.items()),'Accepted32 resources changed')
    preserved=json.loads(preserved_path.read_text())['resourceHashes']
    require(len(preserved)==42 and all(actual.get(n)==pin for n,pin in preserved.items()),'Preserved lower-eight42 changed')
    native_models={r['name']:r for r in native['models']}
    require(len(native_models)==12 and set(native_models)==set(inv['modelParts']),'Native twelve model set differs')
    rows={};pixels={};masks={};raw_values={}
    for part,offset in OFFSETS.items():
        model='pmh0_'+part+'001';stage=stages[part]
        require(stage['shadeOffset']==offset and calibration['parts'][part]['proof']['offset']==offset,
                'Current measured integer calibration differs')
        raw_stage=Path(stage['stage']);raw_receipt=raw_stage/'stock-part-stage.json'
        require(sha(raw_receipt)==stage['stageReceiptSha256'],'Actual raw stage changed')
        raw_config=json.loads(raw_receipt.read_text())['configuration']
        raw=raw_stage/raw_config['slug']/'converted'
        p0=(raw/'resources'/(model+'.plt')).read_bytes()
        pc=(baseline/(model+'.plt')).read_bytes();pe=(effective/(model+'.plt')).read_bytes()
        require(sha(raw/'resources'/(model+'.plt'))==stage['originalPltSha256'],'Original raw palette changed')
        calproof=calibration_proof(p0,pc,offset)
        require(sha(baseline/(model+'.plt'))==calibration['parts'][part]['effectivePltSha256'],'Calibrated palette association differs')
        require(p0[:24]==pc[:24]==pe[:24],'AO changed PLT header')
        before,after=decode_plt(pc),decode_plt(pe)
        require(before.shape==(2048,2048,2) and np.all(before[:,:,1]==0),'Expected current2K layer0-only arms')
        raw_ascii=raw/'ascii'/(model+'.mdl');ascii_path=converted/'ascii'/(model+'.mdl')
        require(raw_ascii.read_bytes()==ascii_path.read_bytes()==(baseline/(model+'.mdl')).read_bytes()
                ==(effective/(model+'.mdl')).read_bytes(),'Native source ASCII geometry/UV/authored normals changed')
        require(native_models[model+'.mdl']['sourceSha256']==sha(ascii_path)
                and native_models[model+'.mdl']['binarySha256']==actual[model+'.mdl'],'Actual compiler ASCII/binary association differs')
        normal=model+'n.tga'
        require((raw/'resources'/normal).read_bytes()==(baseline/normal).read_bytes()
                ==(effective/normal).read_bytes()==(converted/'resources'/normal).read_bytes(), 'Authored normal map changed')
        settings=config['partSettings'][part];declared=settings['connectorPlanes']
        require([(tuple(p['outwardNormal']),p['offsetMetres']) for p in declared]
                ==[(tuple(p[:3]),p[3]) for p in JOINT_PLANES[part]],'Measured joint mask planes differ')
        require(settings['connectorBandMetres']==.02 and settings['aoStrength']==.35
                and settings['maxDarkenShades']==12 and settings['maxBrightenShades']==3,'Current scoped shade limits differ')
        audit_row=material_audit['parts'][part]
        sample_path=material_audit_path.parent/part/'native-uv-samples.npz'
        require(sha(sample_path)==audit_row['sampleSha256'],'Measured source UV samples changed')
        inputs[str(sample_path.resolve())]=sha(sample_path)
        samples=np.load(sample_path,allow_pickle=False)
        mask,protected=connector_mask(samples['position'],samples['uv'],(2048,2048),.02,
                      [(p['outwardNormal'],p['offsetMetres']) for p in declared])
        published_path=operation_path.parent/'masks'/(part+'-influence.png')
        published=np.asarray(Image.open(published_path).convert('L'))
        require(np.array_equal(mask,published),'Published influence mask differs from measured geometry/planes')
        inputs[str(published_path.resolve())]=sha(published_path)
        bounds=shade_bounds(before,after,published,protected,12,3)
        ao_path=Path(audit_row['images']['ao']['path'])
        require(sha(ao_path)==audit_row['images']['ao']['sha256'],'Source AO map changed')
        ao=np.asarray(Image.open(ao_path).convert('RGB'))[:,:,0]/255.
        occlusion=audit_row['material']['occlusionTexture'].get('strength',1)
        ao=1-occlusion*(1-ao)
        delta=palette_delta(before[:,:,0],ao,palette,.35)
        influence=published.astype(float)/255.
        sample_uv=samples['sampleUV'];weights=np.repeat(samples['area']/4,4)
        mean_delta=float(np.average(sampled(delta*influence,sample_uv),weights=weights))
        mean_mask=float(np.average(sampled(influence,sample_uv),weights=weights))
        compensation=-mean_delta/max(mean_mask,1e-9)
        require(abs(compensation-operation['parts'][part]['meanCompensationShades'])<1e-12,
                'Mean compensation differs from exact source calculation')
        planned=np.clip(delta+compensation,-12,3)*influence
        raw_shade=before[:,:,0].astype(float)+planned
        expected=before.copy();expected[:,:,0]=np.clip(np.rint(raw_shade),0,255).astype(np.uint8)
        require(np.array_equal(expected,after),'AO shade pixels do not reproduce actual bounded per-side bake')
        require(bounds['changedShadePixels']==operation['parts'][part]['changedPixels']
                and bounds['protectedConnectorPixels']==operation['parts'][part]['connectorProtectedPixels'],
                'Published operation counts differ from actual pixels')
        roughname=model+'r.tga';orm_path=Path(audit_row['images']['orm']['path'])
        require(sha(orm_path)==audit_row['images']['orm']['sha256'],'Source ORM map changed')
        factor=audit_row['material']['pbrMetallicRoughness'].get('roughnessFactor',1)
        orm=np.asarray(Image.open(orm_path).convert('RGB'))
        expected_rough=np.clip(np.rint(orm[:,:,1].astype(float)*factor),0,255).astype(np.uint8)
        rough=np.asarray(Image.open(effective/roughname).convert('RGB'))
        require(np.all(rough==expected_rough[:,:,None]),'Actual roughness is not exact source ORM-G times factor')
        mtr_text=(converted/'resources'/(model+'.mtr')).read_text()
        base_mtr=(baseline/(model+'.mtr')).read_text()
        expected_mtr=re.sub(r'(?mi)^\s*parameter float Roughness\s+[^\n]+',
                            'parameter float Roughness 0',base_mtr).rstrip()+'\ntexture3 '+model+'r\n'
        require(mtr_text==expected_mtr,'MTR differs beyond the declared roughness0/texture3 operation')
        require(re.search(r'(?mi)^texture1\s+'+re.escape(model+'n')+r'\s*$',mtr_text)
                and re.search(r'(?mi)^texture3\s+'+re.escape(model+'r')+r'\s*$',mtr_text)
                and re.search(r'(?mi)^parameter float Roughness\s+0(?:\.0*)?\s*$',mtr_text)
                and not re.search(r'(?mi)^texture[0245]\s',mtr_text),'Actual MTR slot/scalar ownership differs')
        for name in [model+'.plt',model+'.mtr',normal,roughname]:
            require(actual[name]==operation['effectiveResourceHashes'][name],'Actual native material differs from operation: '+name)
        rows[part]={'calibration':calproof,'shadeBounds':bounds,'meanCompensationShades':compensation,
          'actualPublishedMask':record(published_path),'exactPerSideAoReproduction':True,
          'sourceAsciiGeometryUvAuthoredNormalsExact':True,'normalMapBytesExact':True,
          'actualMtrTexture1StrengthPreserved':True,'sourceOrmGreenRoughnessPixelsExact':True,
          'actualMtrTexture3Roughness0':True,'roughnessFactor':factor,
          'effectivePalette':record(converted/'resources'/(model+'.plt'))}
        pixels[part]=after;masks[part]=published;raw_values[part]=raw_shade
    pairs={}
    for left,right in [('bicepl','bicepr'),('forel','forer')]:
        comparison=compare_pair(pixels[left],pixels[right],masks[left],masks[right],raw_values[left],raw_values[right])
        comparison['normalMapBytesExact']=(converted/'resources'/('pmh0_'+left+'001n.tga')).read_bytes()==(converted/'resources'/('pmh0_'+right+'001n.tga')).read_bytes()
        comparison['roughnessMapBytesExact']=(converted/'resources'/('pmh0_'+left+'001r.tga')).read_bytes()==(converted/'resources'/('pmh0_'+right+'001r.tga')).read_bytes()
        require(comparison['normalMapBytesExact'] and comparison['roughnessMapBytesExact'], 'Bilateral normal/roughness maps differ')
        require(comparison['layerDifferencePixels']==comparison['shadeDifferencesInEitherZeroMask']==0,
                'Bilateral material ownership/protected shade discrepancy')
        pairs[left+'/'+right]=comparison
    require(set(actual)==set(preserved)|{n for n in operation['effectiveResourceHashes'] if not n.endswith('.mdl')}
            |{'pmh0_'+p+'001.mdl' for p in OFFSETS},'Current62 namespace differs from preserved42 +four compiled arms')
    require(all(sha(p)==pin for p,pin in inputs.items()),'Actual audited inputs changed during execution')
    output.mkdir(parents=True)
    shutil.copyfile(__file__,output/'executed-auditor.py')
    report={'schemaVersion':1,'readOnly':True,'pass':True,'inputHashes':inputs,'historicalHelperArchivesUsed':archived,
      'parts':rows,'bilateralMaterialComparison':pairs,'resourceContract':{'nativeResourceCount':62,
        'nativeModelCount':12,'accepted32BytesExact':True,'preservedLowerEight42BytesExact':True,
        'actualNativeResourceHashes':actual,'tableRootAnimationResources':[]},
      'pairPolicy':'No blanket bilateral palette equality or tolerance. Each side exactly reproduces its own measured-mask operation; normal/roughness/layers and all protected or zero-mask pixels remain exact. Record every actual palette mismatch.',
      'noSourceMaterialEdits':True,'clientLaunched':False,'gpuUsed':False,
      'limits':['This independently verifies material bytes and finite mask/UV data, not native tangent rendering or client lighting.',
        'Actual native geometry corner transport is checked in separate compiler audits; this audit binds their actual ASCII/binary receipts.']}
    (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['calibration','operation','converted','accepted-selection','preserved-inventory','output']:
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();report=run(args)
    print(json.dumps({'audit':record(args.output/'audit.json'),'pass':True,
                      'bilateralComparison':report['bilateralMaterialComparison']}))


if __name__=='__main__':main()
