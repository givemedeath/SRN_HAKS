"""Check saved or candidate ownership roles before tone/palette; never approve or alter ownership."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_erosion
from headkit.common import pin, read, verify, write, require
from headkit.face_masks import nearest, hair_locks, NOSE_BASE, HAIR
from headkit.brow_edges import upper_lids
from headkit.quality import focus_view, THRESHOLDS, lip_hair_pixels, upper_lid_hair_pixels
from headkit.runner import Runner
from headbatch.review._role_code import files as role_code_files


def measure(region,layers,settings):
    channel=nearest(region['view'],layers,region['uv'])
    brows,iris,whites=(region[k].copy() for k in ('brows','iris','whites'))
    side=settings.get('cybereyeImageSide')
    require(side in (None,'left','right'), 'Unknown cybereye side')
    if side:
        half=region['xs']<region['pts'][168,0] if side=='left' else region['xs']>=region['pts'][168,0]
        brows &= ~half; iris &= ~half; whites &= ~half
    share=lambda mask,k:float((channel[mask]==k).mean()) if mask.any() else None
    metrics={'browsOnHair':share(brows,1),'irisOnTattoo1':share(iris,8),'whitesOnSkin':share(whites,0)}
    halves={'left':region['xs']<region['pts'][168,0],'right':region['xs']>=region['pts'][168,0]}
    metrics['irisByEye']={s:share(iris & half,8) for s,half in halves.items() if s!=side}
    metrics['lipHairPx']=lip_hair_pixels(region,channel)
    metrics['upperLidHairPx']=upper_lid_hair_pixels(region,channel,side)
    game=region['small'](np.where(region['face'],channel,255).astype(np.uint8),True).astype(int)
    inside=region['mask'](region['face']);edge=inside & ~binary_erosion(inside,np.ones((3,3)))
    count=0
    for k in (0,1,8):
        groups,n=label((game==k)&inside,np.ones((3,3)))
        small=np.bincount(groups.ravel())<=2;small[0]=False;small[np.unique(groups[edge])]=False
        count+=int(small.sum())
    metrics['specks']=count
    locks=hair_locks(region['render'],region['labels'],region['view']['hit'],region['face'],region['plain'])
    upper=region['plain'] & (region['ys']<region['pts'][NOSE_BASE,1])
    plain=upper & ~locks if locks is not None else upper
    metrics['hairOnFaceSkin']=share(plain,1)
    metrics['hairLockOnSkinPx']=None
    if locks is not None:
        groups,n=label(region['small']((locks & (channel==0)).astype(np.uint8)*255)>127,np.ones((3,3)))
        metrics['hairLockOnSkinPx']=int(np.bincount(groups.ravel())[1:].max()) if n else 0
    return metrics,channel,brows,plain & (channel==1)


def candidate(runner,rules,atlas=None):
    from headkit.paint import rule_ownership
    from headkit.face_encode import apply_channels,majority,masks_at,CHANNEL_MASKS
    from headkit.gltf import mesh
    from headkit.textures import surface
    from headkit.uv import raster_audit
    config={**runner.data['ownership'],**read(rules)}
    source=runner.source('uvMesh','unwrap','mesh');color=runner._color4k()
    paint={n:p['path'] for n,p in runner.result('paint')['masks'].items()} if 'paint' in runner.data else {}
    metallic=runner.input('metallic4k') if 'metallic4k' in runner.data['inputs'] else None if 'basecolor4k' in runner.data['inputs'] else runner.result('bake')['maps']['metallic-4096.png']['path']
    if atlas is not None:
        require(config.get('mode')=='atlas' and config.get('sourceSha256')==pin(source)['sha256'],'Candidate atlas must bind the UV mesh')
        with Image.open(atlas) as image:
            require(image.mode=='L' and image.size==(4096,4096),'Candidate needs a 4K discrete ownership atlas')
            labels=np.asarray(image).copy()
        require(np.isin(labels,range(10)).all(),'Invalid candidate ownership channel')
        protected=None
    else:
        require(config.get('mode','rules')=='rules','Atlas candidates require an explicit bound atlas')
        labels,_,protected=rule_ownership(source,color,config,metallic=metallic,masks=paint,protected=True)
    value=mesh(source);positions,owners=(surface(value,4096,enforce=False)[:2] if protected is not None else (None,raster_audit(value['uv'],4096)[1]))
    with Image.open(color) as image:rgb=np.asarray(image.convert('RGB'))
    names=CHANNEL_MASKS+(('ear',) if config.get('boneEarGuard') or config.get('hairEarGuard') else ())
    features=masks_at(runner.result('masks')['files'],names)
    if config.get('hairMaskRequiresRule'):
        for name in ('brow','hairlock'):features[name]*=labels==1
    labels,_=apply_channels(labels,features,owners>=0,rgb,protected=protected,positions=positions,
                            hair_ear_guard=config.get('hairEarGuard',False),lip_skin_guard=config.get('lipSkinGuard',False))
    from headkit.brow_edges import adjust
    labels,_=adjust(labels,value,runner.result('masks'),owners>=0,config.get('browSeedGuardPixels',3),
                    recover_brows=config.get('browSeedGuard',False),
                    cybereye_image_side=runner.data.get('quality',{}).get('cybereyeImageSide'))
    return majority(labels)


def draw(head,attempt,output,rules=None):
    head=head.resolve();output=output.resolve();runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
    require('sourceHairRoles' not in runner.data.get('quality',{}), 'Use full quality for a source-hair-role audit')
    state=runner.state['stages'];receipt=state['ownership'];require(Path(receipt['path']).parent.name==attempt,'Name current ownership attempt')
    masks=runner.result('masks');settings=runner.data.get('quality',{})
    if rules:
        layers=candidate(runner,rules)
    else:
        result=runner.result('ownership',require_review=False)
        with Image.open(result['onek']['path']) as image:layers=np.asarray(image)
    inputs=[receipt,state['masks'],masks['source'],*masks['files'].values(),*[pin(path) for path in role_code_files()]]
    if rules:inputs.append(pin(rules))
    else:inputs.append(result['onek'])
    verify(inputs,fresh=True)
    region=focus_view(masks['source']['path'],masks,layers)
    metrics,channel,brows,hair_spill=measure(region,layers,settings);limits=read(THRESHOLDS)['limits']
    failed=[name for name,key in [('browsOnHair','browsOnHairMin'),('irisOnTattoo1','irisOnTattoo1Min'),('whitesOnSkin','whitesOnSkinMin')] if (metrics[name] or 0)<limits[key]]
    failed += ['irisOnTattoo1-'+s for s,v in metrics['irisByEye'].items() if (v or 0)<limits['irisOnTattoo1Min']]
    if metrics['specks']>limits['specksMax']:failed.append('specks')
    if metrics['lipHairPx']:failed.append('lipHair')
    if metrics['upperLidHairPx']:failed.append('upperLidHair')
    if metrics['hairOnFaceSkin'] is not None and metrics['hairOnFaceSkin']>limits['hairOnFaceSkinMax']:failed.append('hairOnFaceSkin')
    if (metrics['hairLockOnSkinPx'] or 0)>limits['hairLockOnSkinPxMax']:failed.append('hairLockOnSkin')
    rgb=region['render'].copy();rgb[brows & (channel==1)]=[80,100,255];rgb[brows & (channel!=1)]=[255,30,30];rgb[hair_spill]=[255,160,0]
    lid_spill=upper_lids(channel.shape,region['pts'],region['view']['hit'],settings.get('cybereyeImageSide'),source_hair=region['labels']==HAIR) & (channel==1)
    rgb[lid_spill]=[255,30,30]
    output.parent.mkdir(parents=True,exist_ok=True)
    require(not output.exists() and not output.with_suffix('.json').exists(),'Role evidence already exists')
    Image.fromarray(rgb).save(output)
    verify(inputs,fresh=True)
    report={'kind':'headbatch-ownership-roles-v1','head':head.name,'attempt':attempt,'stageReceipt':receipt,
            'candidate':pin(rules) if rules else None,'inputs':inputs,'settings':settings,'limits':limits,
            'metrics':metrics,'failed':failed,'passed':not failed,'sheet':pin(output),'approved':False}
    write(output.with_suffix('.json'),report,fresh=True)
    if rules is None:write(head/'ownership-roles.json',pin(output.with_suffix('.json')))
    print(metrics,'failed',failed)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('head',type=Path);p.add_argument('attempt');p.add_argument('output',type=Path);p.add_argument('--candidate',type=Path)
    a=p.parse_args();print(draw(a.head,a.attempt,a.output,a.candidate))
