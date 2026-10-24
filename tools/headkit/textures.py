"""UV surface rasterization and bounded CPU sampling of the generated appearance."""
from pathlib import Path
import time
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from .common import require, pin, write
from .gltf import mesh
from .field import load_generated_field
from .uv import raster_audit, subtexel_audit


def surface(value, size, max_subtexel_fraction=0.0, *, enforce=True):
    report, owners=raster_audit(value['uv'],size)
    subtexel=subtexel_audit(value['uv'],size,report,owners,max_subtexel_fraction)
    require(not enforce or (not report['overlapFaces'] and not report['degenerateUvFaces'] and subtexel['passed']),
            'UV overlap/degeneracy or unmapped faces block baking')
    report['subtexel']={k:v for k,v in subtexel.items() if k!='failingFaces'}
    positions=np.zeros((size,size,3),np.float32)
    for fi in np.unique(owners[owners>=0]):
        t=value['uv'][fi]*size
        lo=np.maximum(0,np.floor(t.min(0)-.5).astype(int));hi=np.minimum(size-1,np.ceil(t.max(0)-.5).astype(int))
        yy,xx=np.nonzero(owners[lo[1]:hi[1]+1,lo[0]:hi[0]+1]==fi);y=yy+lo[1];x=xx+lo[0]
        ab,ac=t[1]-t[0],t[2]-t[0];q=np.c_[x+.5,y+.5]-t[0]
        det=ab[0]*ac[1]-ab[1]*ac[0]
        u=(q[:,0]*ac[1]-q[:,1]*ac[0])/det;v=(ab[0]*q[:,1]-ab[1]*q[:,0])/det
        bary=np.c_[1-u-v,u,v];positions[y,x]=bary@value['positions'][value['faces'][fi]]
    return positions,owners,report


def pad(values, mapped):
    require(mapped.any(),'No mapped texture samples')
    nearest=distance_transform_edt(~mapped,return_distances=False,return_indices=True)
    result=values.copy();result[~mapped]=values[tuple(nearest[:,~mapped])]
    return result


def bake(source, field_path, output, *, allow_decoder_overshoot=False, size=4096, max_subtexel_fraction=.005,
         derived_surface='gated'):
    require(size==4096,'Production source bake is 4K; derive 2K/1K afterward')
    begun=time.perf_counter();value=mesh(source)
    field=load_generated_field(field_path,allow_decoder_overshoot)
    # Every raster gate runs before anything is written, so a rejected bake leaves no partial output.
    # The 4K source stays zero-tolerance; the derived 1K surface takes the measured sub-texel allowance.
    # A 4K-qualified donor atlas only consumes the 4K map; its 1K surface is then diagnostic.
    require(derived_surface in ('gated','diagnostic'),'Unknown derived surface policy')
    positions,owners,report=surface(value,size);mapped=owners>=0
    low,ids,low_report=surface(value,1024,max_subtexel_fraction,enforce=derived_surface=='gated')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sampled,fallback=field.sample(positions[mapped],chunk=65536)
    values=np.zeros((size,size,6),np.float32);values[mapped]=sampled;values=pad(values,mapped)
    files={}
    channels={'basecolor':values[...,:3],'metallic':values[...,3],'roughness':values[...,4],'opacity':values[...,5]}
    for name,array in channels.items():
        image=Image.fromarray(np.rint(np.clip(array,0,1)*255).astype(np.uint8))
        for resolution in (4096,2048,1024):
            path=output/f'{name}-{resolution}.png'
            (image if resolution==size else image.resize((resolution,resolution),Image.Resampling.BOX)).save(path)
            files[path.name]=pin(path)
    # Full-resolution coverage remains explicit; padded samples never become ownership evidence.
    Image.fromarray(mapped.astype(np.uint8)*255).save(output/'mapped-4096.png')
    np.savez(output/'surface-1024.npz',positions=low,faceIds=ids)
    result={'source':pin(source),'field':pin(field_path),'maps':files,'surface':pin(output/'surface-1024.npz'),
            'coverage':report,'subtexel1024':low_report['subtexel'],'mappedSamples':int(mapped.sum()),'nearestFallbackSamples':int(fallback.sum()),
            'clippedSamplesByChannel':field.clipped_samples_per_channel.tolist(),'rawRanges':field.raw_ranges,
            'paddingOnlyOutsideMappedSurface':True,'aoAdded':False,'threads':4,'elapsedSeconds':time.perf_counter()-begun,
            'visualReviewRequired':True}
    if derived_surface=='diagnostic':
        result['derivedSurface']={'policy':'diagnostic','passed':bool(not low_report['overlapFaces']
            and not low_report['degenerateUvFaces'] and low_report['subtexel']['passed'])}
    write(output/'bake.json',result,fresh=True);return result


def tone_match(color, ownership, reference, config, output):
    """Match skin/hair separately in logit color while retaining local source variation."""
    rgb=np.asarray(Image.open(color).convert('RGB'),float)/255
    with Image.open(ownership) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images')
        labels=np.asarray(image).copy()
    ref=np.asarray(Image.open(reference).convert('RGB'),float)/255
    require(labels.shape==rgb.shape[:2] and np.all(labels<=9),'Discrete 0..9 ownership required')
    require(set(config)=={'skin','hair'},'Skin and hair tone samples must both be reviewed')
    def logit(x):
        x=np.clip(x,1/255,254/255);return np.log(x/(1-x))
    result=rgb.copy();report={}
    for name,layer in [('skin',0),('hair',1)]:
        row=config[name];require(row.get('reviewed') is True,'Review clean tone samples')
        samples=[]
        for box in row['referenceBoxes']:
            x0,y0,x1,y1=np.asarray(box,float)
            require(0<=x0<x1<=1 and 0<=y0<y1<=1,'Normalized reference rectangle required')
            pixels=ref[int(y0*len(ref)):int(y1*len(ref)),int(x0*ref.shape[1]):int(x1*ref.shape[1])]
            require(pixels.size>0,'Empty reference tone sample');samples.extend(pixels.reshape(-1,3))
        selected=labels==layer;require(selected.any(),'Missing '+name+' ownership')
        source=np.median(rgb[selected],axis=0);target=np.median(samples,axis=0)
        shift=logit(target)-logit(source);require(np.max(abs(shift))<=2,'Tone shift exceeds supported range; review masks/samples')
        result[selected]=1/(1+np.exp(-(logit(rgb[selected])+shift)))
        report[name]={'sourceMedian':source.tolist(),'referenceMedian':target.tolist(),'logitShift':shift.tolist()}
    Image.fromarray(np.rint(result*255).astype(np.uint8)).save(output)
    return {'source':pin(color),'ownership':pin(ownership),'reference':pin(reference),'output':pin(output),'regions':report}
