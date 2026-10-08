"""Pure checks for a literal native-basis offline material interpretation.

Does not emulate NWN lighting or accept any runtime material. PLT palette lookup
happens per texel before filtering. Native UVs remain bottom-origin in Blender.
"""
import numpy as np
from prepare_effective_body_preview import colorize_plt


def palette_rgba(data, palette, row):
    return colorize_plt(data, {0:np.asarray(palette)}, {0:row})


def normal_rg(rg):
    rg=np.asarray(rg,dtype=float)
    if rg.shape[-1]!=2 or not np.isfinite(rg).all() or (rg<0).any() or (rg>1).any():
        raise ValueError('Unit-interval original normal-map RG samples required')
    xy=rg*2-1
    return np.concatenate([xy,np.sqrt(np.maximum(1-(xy*xy).sum(axis=-1),0))[...,None]],axis=-1)


def basis_fragment(normal,tangent,handedness,rg,front=True):
    n,t=np.asarray(normal,float),np.asarray(tangent,float)
    if n.shape!=t.shape or n.shape[-1]!=3 or not np.isfinite(n).all() or not np.isfinite(t).all():
        raise ValueError('Finite interpolated native N/T triples required')
    nl,tl=np.linalg.norm(n,axis=-1),np.linalg.norm(t,axis=-1)
    if (nl<=0).any() or (tl<=0).any():raise ValueError('Nonzero interpolated native N/T required')
    n=n/nl[...,None]*(1 if front else -1);t=t/tl[...,None]
    sign=np.where(np.asarray(handedness)>=0,1.,-1.)
    b=np.cross(n,t)*np.asarray(sign)[...,None]
    m=normal_rg(rg)
    return t*m[...,0,None]+b*m[...,1,None]+n*m[...,2,None]
