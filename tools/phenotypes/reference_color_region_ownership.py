"""Seam-consistent object-space reference camera ownership and bounded role padding.

Literal colors are blended only across identical known source roles. Mixed-role
regions use one deterministic known camera, never a skin/cloth color blend.
Unseen/unknown/protected covered geometry is not padded or globally filled.
"""
import numpy as np
from target_contract import require
from orthographic_reference_projection import CARDINALS

def own_regions(colors,roles,eligible,normals,power=4):
 require(colors.ndim==3 and colors.shape[1:]==(4,3) and roles.shape==eligible.shape==colors.shape[:2] and normals.shape==(len(colors),3),'Explicit camera/color/role/normal association required')
 require(np.isfinite(colors).all() and np.isfinite(normals).all() and np.isin(roles,[0,1,2]).all() and eligible.dtype==np.bool_,'Finite explicit source roles required')
 require(type(power) is int and 2<=power<=8,'Bounded integer angular blend power required');require(np.allclose(np.linalg.norm(normals,axis=1),1,atol=1e-4),'Unit authored decision normals required')
 outward=np.asarray([CARDINALS[v][2] for v in CARDINALS]);angle=np.maximum(0,normals@outward.T);weight=angle**power*eligible;support=weight>1e-12;total=weight.sum(1);primary=np.argmax(weight,axis=1);owner_role=roles[np.arange(len(roles)),primary];accepted=(total>0)&(owner_role>0)
 same=((~support)|(roles==owner_role[:,None])).all(1)&accepted
 final_weights=np.zeros_like(weight);final_weights[same]=weight[same]/total[same,None]
 single=accepted&~same;final_weights[np.flatnonzero(single),primary[single]]=1
 result=(colors*final_weights[:,:,None]).sum(1);final_role=np.where(accepted,owner_role,0).astype('u1');mode=np.zeros(len(colors),dtype='u1');mode[same]=1;mode[single]=2;primary=np.where(accepted,primary,-1).astype('i1')
 require(not ((final_weights>0)&(roles!=final_role[:,None])).any(),'Forbidden skin/cloth or unknown color cross-blend')
 return result,{'accepted':accepted,'ownedRole':final_role,'cameraOwner':primary,'mode':mode,'blendWeights':final_weights.astype('f4'),'angleIncidence':angle.astype('f4'),'eligibleWeightedView':support,'sameRoleContinuousBlend':same,'singleRoleLiteralCamera':single}

def same_surface_role_padding(coverage,accepted,protected,roles,positions,normals,radius=8,max_distance=.005,max_normal_degrees=5):
 require(coverage.dtype==accepted.dtype==protected.dtype==np.bool_ and coverage.shape==accepted.shape==protected.shape==roles.shape and positions.shape==normals.shape==coverage.shape+(3,),'Explicit padding surface/role association required')
 require(type(radius) is int and 1<=radius<=16 and 0<max_distance<=.01 and 0<max_normal_degrees<=10,'Bounded padding controls required')
 require(np.isin(roles,[0,1,2]).all() and not (accepted&(~coverage|protected|(roles==0))).any(),'Only verified mapped role seeds allowed')
 h,w=coverage.shape;ids=np.arange(h*w,dtype='i4').reshape(h,w);lineage=np.where(accepted,ids,-1);steps=np.where(accepted,0,-1).astype('i2');blocked=coverage|protected;ambiguous=np.zeros_like(coverage);roleflat=roles.ravel();p=positions.reshape(-1,3);n=normals.reshape(-1,3);cosine=np.cos(np.deg2rad(max_normal_degrees));directions=((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))
 for step in range(1,radius+1):
  best=np.full((h,w),np.iinfo(np.int32).max,dtype='i4')
  for dy,dx in directions:
   yt=slice(max(0,dy),min(h,h+dy));xt=slice(max(0,dx),min(w,w+dx));ys=slice(max(0,-dy),min(h,h-dy));xs=slice(max(0,-dx),min(w,w-dx));candidate=lineage[ys,xs];np.minimum(best[yt,xt],np.where(candidate>=0,candidate,np.iinfo(np.int32).max),out=best[yt,xt])
  fill=(lineage<0)&~blocked&(best<np.iinfo(np.int32).max)
  if not fill.any():break
  fy,fx=np.nonzero(fill);seed=best[fy,fx];bad=np.zeros(len(seed),bool)
  for dy,dx in directions:
   yy,xx=fy+dy,fx+dx;valid=(yy>=0)&(yy<h)&(xx>=0)&(xx<w);indices=np.flatnonzero(valid);other=lineage[yy[valid],xx[valid]];has=other>=0;indices=indices[has];other=other[has]
   if not len(indices):continue
   original=seed[indices];disagree=(roleflat[original]!=roleflat[other])|(np.linalg.norm(p[original]-p[other],axis=1)>max_distance)|(np.einsum('ij,ij->i',n[original],n[other])<cosine);bad[indices]|=disagree
  blocked[fy[bad],fx[bad]]=True;ambiguous[fy[bad],fx[bad]]=True;good=~bad;lineage[fy[good],fx[good]]=seed[good];steps[fy[good],fx[good]]=step
 destination=steps>0;require(not destination[coverage|protected|ambiguous].any(),'Padding changed mapped/unknown/protected surface')
 return {'sourceTexel':lineage,'steps':steps,'destination':destination,'competingRoleOrSurfaceAmbiguous':ambiguous}
