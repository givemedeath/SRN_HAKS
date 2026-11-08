"""Select foreground preparation from the actual input; never infer isolation from padding."""
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from .common import asset, pin, require


BACKGROUND_MODEL='birefnet.safetensors'


def mask_report(mask):
    mask=np.asarray(mask,dtype=np.float32)
    require(mask.ndim==2 and np.isfinite(mask).all(),'Finite foreground mask required')
    foreground=mask>=.5
    require(foreground.any(),'Empty foreground mask')
    fraction=float(foreground.mean())
    require(fraction<.95,'Foreground mask includes the canvas/background')
    require(not (foreground[0].any() or foreground[-1].any() or foreground[:,0].any() or foreground[:,-1].any()),
            'Foreground silhouette is clipped at the canvas edge')
    y,x=np.nonzero(foreground)
    return {'foregroundFraction':fraction,'bounds':[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]}


def analyze_reference(path):
    with Image.open(path) as image:
        alpha=np.asarray(image.convert('RGBA').getchannel('A'),dtype=np.float32)/255
        size=list(image.size)
    require(alpha.max()>=.5,'Reference has no usable opaque foreground')
    meaningful=bool((alpha<=.02).any() and (alpha>=.5).any() and float((alpha>=.5).mean())<.95)
    result={'schemaVersion':1,'source':pin(path),'size':size,
            'route':'preserve-alpha' if meaningful else 'remove',
            'reason':'Existing nonempty isolated alpha' if meaningful else 'Opaque or effectively full-canvas input requires foreground extraction'}
    if meaningful:result['mask']=mask_report(alpha)
    return result


def require_conditioning_review(manifest_path,data):
    """A reviewed RGB render on black is valid only with its bound foreground mask."""
    review=data.get('approval',{}).get('background',{})
    require(review.get('decision')=='approved' and bool(review.get('notes','').strip()),
            'Review background isolation and the foreground mask before geometry or appearance')
    require('foregroundMask' in data['inputs'],'Pinned reviewed foregroundMask required')
    reference=asset(manifest_path,data['inputs']['reference'])
    geometry=asset(manifest_path,data['inputs']['geometry'])
    detail=asset(manifest_path,data['inputs']['detail'])
    mask=asset(manifest_path,data['inputs']['foregroundMask'])
    require(geometry==detail and review.get('imageSha256')==geometry['sha256']
            and review.get('maskSha256')==mask['sha256']
            and review.get('referenceSha256')==reference['sha256'],
            'Stale background-isolation review')
    require(review.get('route')==analyze_reference(reference['path'])['route'],
            'Background route differs from the actual original input')
    with Image.open(geometry['path']) as image:rgb=np.asarray(image.convert('RGB'),dtype=np.float32)/255
    with Image.open(mask['path']) as image:alpha=np.asarray(image.convert('L'),dtype=np.float32)/255
    require(rgb.shape[:2]==alpha.shape,'Conditioning image/mask dimensions differ')
    report=mask_report(alpha)
    # Lanczos resizing can create a one-pixel colour fringe where the resized
    # white mask cancels to zero. Keep this fixed, measured footprint separate
    # from empty background; do not erode thin features to make it disappear.
    adjacent=np.asarray(Image.fromarray(((alpha>=.5)*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)))>0
    fringe=(alpha<=2/255)&adjacent&(rgb.max(2)>4/255)
    report['resamplingFringePixels']=int(fringe.sum())
    outside=(alpha<=2/255)&~adjacent
    require(outside.any() and np.max(rgb[outside])<=4/255,
            'Conditioning image still contains background outside its reviewed foreground mask')
    return report
