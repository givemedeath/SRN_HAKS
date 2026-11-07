"""Reproduce the reviewed source-pigment regions used in a facial role audit."""
import hashlib
import numpy as np
from PIL import Image
from scipy.ndimage import binary_opening, label
from .common import pin, require
from .predicates import when


def source_regions(render, face, hit, spec, output):
    # Pixel positions and pigment tests are authored against the source RGB alone.
    require(spec['rgbSha256']==hashlib.sha256(render.tobytes()).hexdigest(),
            'Source hair audit is tied to another front render')
    y,x=np.indices(face.shape)
    r,g,b=render.astype(np.int16).transpose(2,0,1)
    values={'x':x,'y':y,'r':r,'blueMinusGreen':b-g,'redMinusBlue':r-b,
            'greenOverRed':g/np.maximum(r,1),'blueOverGreen':b/np.maximum(g,1)}
    brow=hit & when(spec['brows'],values,{})
    locks=face & hit & ~brow & when(spec['locks'],values,{})
    locks=binary_opening(locks,iterations=2)
    components,_=label(locks)
    locks &= np.bincount(components.ravel())[components]>100
    overlay=render.copy()
    for name,mask,colour in [('brows',brow,(100,110,255)),('locks',locks,(0,220,150))]:
        for half in (x<face.shape[1]/2,x>=face.shape[1]/2):
            require((mask & half).sum()>=100,'Source audit must identify both brows and both hair locks')
        digest=hashlib.sha256(mask.astype(np.uint8).tobytes()).hexdigest()
        require(digest==spec['maskSha256'][name],'Source audit differs from the visually reviewed regions')
        overlay[mask]=colour
    path=output/'source-roles.png'
    Image.fromarray(overlay).save(path)
    return brow,locks,pin(path)
