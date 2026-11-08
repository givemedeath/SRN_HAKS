"""Reviewed material-local de-lighting from an intact reference region, continuous across UV seams."""
import numpy as np
from .common import require
from .face_encode import _surface_mean, luma
from .paint import colour_values
from .predicates import when
from .textures import surface, pad


def balance(colour, labels, value, spec):
    """Only darken the selected material's broad baked light; retain local texture and other materials."""
    require(isinstance(spec,dict) and set(spec)<= {'channel','reference','target','strength','minimumGain','neighbours'}
            and {'channel','reference'}<=set(spec), 'Material light needs a channel and measured reference')
    channel=spec['channel']; strength=spec.get('strength',1.); minimum=spec.get('minimumGain',.3); k=spec.get('neighbours',256)
    require(type(channel) is int and 0<=channel<=9, 'Material light channel must be 0..9')
    require(all(type(v) in (int,float) and np.isfinite(v) and 0<v<=1 for v in (strength,minimum))
            and type(k) is int and 32<=k<=512, 'Invalid material light limits')
    require(colour.shape[:2]==labels.shape and colour.shape[-1]==3, 'Material light needs matching color and labels')
    positions,owners,_=surface(value,len(colour),enforce=False); mapped=owners>=0
    chosen=mapped & (labels==channel); require(chosen.sum()>=32, 'Too few material samples')
    points=positions[chosen].astype(float); low=value['positions'].min(0); span=np.ptp(value['positions'],axis=0)
    require((span>0).all(), 'Material light needs a nondegenerate mesh')
    rel=(points-low)/span; samples=colour[chosen].astype(np.float32)
    values=colour_values(samples,{'x':lambda:rel[:,0],'y':lambda:rel[:,1],'z':lambda:rel[:,2],
                                  'mapped':lambda:np.ones(len(points),bool)})
    reference=when(spec['reference'],values,{})
    target=when(spec.get('target',{'mapped':True}),values,{})
    require(reference.sum()>=32 and target.sum()>=32, 'Material light reference/target needs 32 texels')
    anchor=float(np.median(luma(samples[reference])))
    require(anchor>1, 'Material light reference is black')
    broad=_surface_mean(points,luma(samples),k)
    gains=np.clip(1-strength*(1-np.minimum(1,anchor/np.maximum(broad,1))),minimum,1)
    gains[~target]=1
    out=colour.astype(np.float32).copy();out[chosen]=samples*gains[:,None]
    out=pad(out,mapped)
    return out, {'channel':channel,'referenceTexels':int(reference.sum()),'targetTexels':int(target.sum()),
                 'darkenedTexels':int(np.sum(gains<.999)), 'referenceLuma':anchor,
                 'gainP5P50P95':np.percentile(gains[target],[5,50,95]).tolist(),
                 'visualReviewRequired':True}
