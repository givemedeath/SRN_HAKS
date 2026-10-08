"""Reference-specific conservative skin/charcoal-cloth diagnostic semantics.

Classification is a proposed technical mask, not approved garment ownership.
Warm skin chroma is separated from charcoal's near-neutral/cool chroma; dark
skin is never classified as cloth merely because it has low luminance. All four
bilinear source texels must agree before a projected sample receives a role.
"""
import numpy as np
from target_contract import require

def reference_roles(rgb,alpha,skin_rg_min=12,skin_gb_min=8,cloth_max=145,cloth_rg_abs=18,cloth_gb_abs=24):
 require(rgb.dtype==np.uint8 and rgb.shape[:2]==alpha.shape and rgb.shape[2]==3 and alpha.dtype==np.bool_,'Literal RGB/alpha association required')
 require(8<=skin_rg_min<=20 and 5<=skin_gb_min<=15 and 80<=cloth_max<=160 and 4<=cloth_rg_abs<=20 and 4<=cloth_gb_abs<=26,'Explicit bounded diagnostic semantic controls required')
 r,g,b=np.moveaxis(rgb.astype(int),-1,0);skin=alpha&(r-g>=skin_rg_min)&(g-b>=skin_gb_min)
 cloth=alpha&(~skin)&(np.maximum.reduce((r,g,b))<=cloth_max)&(r-g<=8)&(g-b<=8)&(abs(r-g)<=cloth_rg_abs)&(abs(g-b)<=cloth_gb_abs)
 role=np.zeros(alpha.shape,dtype='u1');role[skin]=1;role[cloth]=2;return role

def sample_role(role,xy):
 require(role.ndim==2 and role.dtype==np.uint8 and np.isin(role,[0,1,2]).all(),'Explicit unknown/skin/cloth pixel labels required')
 h,w=role.shape;coords=np.asarray(xy);x0=np.floor(coords[:,0]).astype(int);y0=np.floor(coords[:,1]).astype(int);inside=(x0>=0)&(x0<w-1)&(y0>=0)&(y0<h-1);result=np.zeros(len(coords),dtype='u1');ids=np.flatnonzero(inside)
 values=np.stack((role[y0[ids],x0[ids]],role[y0[ids],x0[ids]+1],role[y0[ids]+1,x0[ids]],role[y0[ids]+1,x0[ids]+1]),axis=1);same=(values[:,0]>0)&(values==values[:,:1]).all(1);result[ids[same]]=values[same,0];return result

def semantic_cases(roles,eligible):
 require(roles.shape==eligible.shape and roles.ndim==2 and roles.shape[1]==4 and eligible.dtype==np.bool_,'Four cardinal eligible roles required')
 known=eligible&(roles>0);unknown=eligible&(roles==0);has_skin=(known&(roles==1)).any(1);has_cloth=(known&(roles==2)).any(1);cross=has_skin&has_cloth
 consensus=np.zeros(len(roles),dtype='u1');consensus[has_skin&~has_cloth&~unknown.any(1)]=1;consensus[has_cloth&~has_skin&~unknown.any(1)]=2
 return {'knownEligible':known,'unknownEligible':unknown,'sameSkin':consensus==1,'sameCloth':consensus==2,'crossSkinCloth':cross,'hasUnknownVisibleSample':unknown.any(1),'consensusRole':consensus}
