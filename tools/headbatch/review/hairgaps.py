"""Source-bound scalp hair ownership evidence, including read-only correction candidates."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion, label
from headkit.common import read, write, pin, verify, require
from headkit.quality import focus_view
from headkit.face_masks import HAIR, SKIN, nearest


def measure(region, channel):
    core=binary_erosion(region['labels']==HAIR,np.ones((3,3))) & region['view']['hit']
    missing=core & (channel==0)
    groups,n=label(missing);areas=np.bincount(groups.ravel())[1:]
    return {'sourceHairCorePixels':int(core.sum()),'sourceHairOnSkinPixels':int(missing.sum()),
            'fraction':float(missing.sum()/max(1,core.sum())),
            'largestComponents':sorted(areas.tolist(),reverse=True)[:12]},missing



def restore_source_hair(layers,hair,eye,lips,mapped):
    """Restore only source-supported skin labels; preserve other material channels."""
    require(all(a.shape==layers.shape for a in (hair,eye,lips,mapped)), 'Hair repair masks must match the ownership atlas')
    selected=mapped & (hair>204) & (eye<=25) & (lips<=25) & (layers==0)
    result=layers.copy();result[selected]=1
    return result,selected


def draw(head,attempt,output,candidate=None,repair_skin_hair=False):
    head=Path(head).resolve();output=Path(output).resolve();state=read(head/'run/state.json')['stages']
    receipt=state['ownership'];require(Path(receipt['path']).parent.name==attempt,'Name the current exact ownership attempt')
    verify([receipt],fresh=True);owner=read(receipt['path']);mask_pin=owner['dependencies']['masks']
    verify([mask_pin],fresh=True);masks=read(mask_pin['path'])['result']
    inputs=[receipt,mask_pin,owner['result']['onek'],masks['source'],*masks['files'].values(),pin(__file__)]
    atlas=None
    if repair_skin_hair:
        require(candidate is None,'Choose a supplied rules candidate or a source-mask repair')
        from headkit.gltf import mesh
        from headkit.uv import raster_audit
        from headkit.runner import Runner
        runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
        require(runner.state['stages']['masks']==mask_pin,'Repair masks differ from ownership source')
        source=runner.source('uvMesh','unwrap','mesh');value=mesh(source)
        original=owner['result']['fourk'];inputs.append(original);verify(inputs,fresh=True)
        with Image.open(original['path']) as image:labels4k=np.asarray(image).copy()
        require(labels4k.shape==(4096,4096),'Source ownership must be 4K')
        hair=np.asarray(Image.open(masks['files']['hair']['path']).convert('L'))
        eye=np.asarray(Image.open(masks['files']['eye']['path']).convert('L'))
        lips=np.asarray(Image.open(masks['files']['lips']['path']).convert('L'))
        mapped=raster_audit(value['uv'],4096)[1]>=0
        labels4k,selected=restore_source_hair(labels4k,hair,eye,lips,mapped)
        require(selected.any(),'No source-supported skin-to-hair repair')
        output.parent.mkdir(parents=True,exist_ok=True)
        atlas=output.with_name(output.stem+'-candidate-4096.png');require(not atlas.exists(),'Candidate atlas exists');Image.fromarray(labels4k).save(atlas)
        candidate=output.with_name(output.stem+'-candidate.json')
        config={k:v for k,v in runner.data['ownership'].items() if k not in ('rules','regions','mode','sourceSha256','reviewed')}
        config.update(mode='atlas',sourceSha256=pin(source)['sha256'],notes='Operator candidate: source-semantic hair mask restores only skin-owned scalp hair; bald scalp, eyes, lips and non-skin materials are protected. Review exact candidate before selection.')
        write(candidate,config,fresh=True);inputs += [pin(atlas),pin(candidate)]
    elif candidate:inputs.append(pin(candidate))
    verify(inputs,fresh=True)
    if candidate:
        from headkit.runner import Runner
        from headbatch.review.roles import candidate as preview
        runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
        require(runner.state['stages']['masks']==mask_pin,'Candidate masks differ from ownership source')
        layers=preview(runner,Path(candidate),atlas=atlas)
    else:
        with Image.open(owner['result']['onek']['path']) as image:layers=np.asarray(image)
    region=focus_view(masks['source']['path'],masks,layers);channel=nearest(region['view'],layers,region['uv'])
    metrics,missing=measure(region,channel);rgb=region['render'].copy();rgb[missing]=[255,25,25]
    if candidate:
        with Image.open(owner['result']['onek']['path']) as image:old_channel=nearest(region['view'],np.asarray(image),region['uv'])
        added=binary_erosion(region['labels']==SKIN,np.ones((3,3))) & region['view']['hit'] & (channel==1) & (old_channel==0)
        metrics['addedHairOnSourceSkinPixels']=int(added.sum());rgb[added]=[25,220,255]
    require(not output.exists() and not output.with_suffix('.json').exists(),'Hair-gap evidence already exists')
    output.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(np.concatenate([region['render'],rgb],axis=1)).save(output)
    report={'kind':'headbatch-source-hair-gaps-v1','head':head.name,'attempt':attempt,'stageReceipt':receipt,
            'candidate':pin(candidate) if candidate else None,'inputs':inputs,'metrics':metrics,'sheet':pin(output),
            'requiresVisualReview':True,'approved':False,
            'limitation':'Semantic hair is evidence to inspect, not anatomical truth. Preserve intended bald scalp and skin at ears.'}
    if atlas is not None:
        report['candidateAtlas4k']=pin(atlas);report['restoredTexels']=int(selected.sum())
    if candidate:
        target=output.with_name(output.stem+'-layers.png');require(not target.exists(),'Candidate atlas already exists')
        Image.fromarray(layers).save(target);report['candidateOwnership']=pin(target)
    verify(inputs,fresh=True);write(output.with_suffix('.json'),report,fresh=True);print(metrics);print(output)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('head',type=Path);p.add_argument('attempt');p.add_argument('output',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--repair-skin-hair',action='store_true')
    a=p.parse_args();draw(a.head,a.attempt,a.output,a.candidate,a.repair_skin_hair)
