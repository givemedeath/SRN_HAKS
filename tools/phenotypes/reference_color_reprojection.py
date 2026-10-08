"""CPU literal reference-color projection math, with no mesh or source-map edits.

This additive diagnostic has no garment/skin classification or acceptance power.
It excludes background/occluded/grazing/ambiguous samples, persists exact camera
lineage, and leaves unresolved regions at their original color.
"""
import numpy as np
from PIL import Image,ImageFilter
from target_contract import require
import orthographic_reference_projection as camera
import skin_lighting_atlas as atlas

def to_linear(srgb):
    x=np.asarray(srgb,float);return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)

def to_srgb(linear):
    x=np.clip(linear,0,1);return np.where(x<=.0031308,x*12.92,1.055*x**(1/2.4)-.055)

def image_sample(rgb,xy):
    require(rgb.ndim==3 and rgb.shape[2]==3 and np.isfinite(xy).all(),'Finite RGB and source image coordinates required')
    h,w=rgb.shape[:2];require((xy[:,0]>=0).all() and (xy[:,0]<=w-1).all() and (xy[:,1]>=0).all() and (xy[:,1]<=h-1).all(),'No outside/background color extrapolation')
    return atlas.sample_texels(to_linear(rgb/255), (xy+.5)/[w,h],False)

def blend_visible_colors(colors,weights,max_difference=48/255):
    require(colors.ndim==3 and colors.shape[2]==3 and weights.shape==colors.shape[:2],'Explicit per-view RGB/weight association required')
    require(np.isfinite(colors).all() and np.isfinite(weights).all() and (weights>=0).all(),'Finite nonnegative projection inputs required')
    votes=weights>0;count=votes.sum(1);srgb=to_srgb(colors)
    minimum=np.min(np.where(votes[:,:,None],srgb,np.inf),axis=1);maximum=np.max(np.where(votes[:,:,None],srgb,-np.inf),axis=1)
    conflict=(count>1)&(np.max(maximum-minimum,axis=1)>max_difference)
    total=weights.sum(1);accepted=(total>0)&~conflict
    result=np.zeros((len(colors),3));result[accepted]=(colors*weights[:,:,None]).sum(1)[accepted]/total[accepted,None]
    winner=np.full(len(colors),-1,dtype='i1');winner[accepted]=np.argmax(weights[accepted],axis=1)
    return result,accepted,conflict,winner,count

def project_rgb(positions,uv_owner,original,views,span=1.1,depth_tolerance=.0025,min_incidence=.15,alpha_guard=2,max_difference=48/255):
    require(original.dtype==np.uint8 and original.ndim==3 and original.shape[2]==3,'Original immutable RGB atlas required')
    require(0<depth_tolerance<=.005 and 0<min_incidence<1 and isinstance(alpha_guard,int) and 1<=alpha_guard<=4,'Bounded projection controls required')
    require(list(views)==list(camera.CARDINALS),'Four frozen cardinal views in semantic order required')
    size=original.shape[0];require(original.shape[1]==size and uv_owner['coverage'].shape==(size,size),'Square atlas/UV association required')
    mask=uv_owner['coverage']&~uv_owner['protected']&~uv_owner['ambiguous'];ys,xs=np.nonzero(mask);points=uv_owner['positionLocal'][ys,xs].astype(float);owner=uv_owner['ownerFace'][ys,xs]
    geometric=np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0]);length=np.linalg.norm(geometric,axis=1);require((length>1e-12).all(),'Nonzero geometric faces required');geometric/=length[:,None]
    count=len(points);colors=np.zeros((count,4,3),dtype='f4');weights=np.zeros((count,4),dtype='f4');pixel=np.full((count,4,2),np.nan,dtype='f4');errors=np.full((count,4),np.inf,dtype='f4');incidence=np.zeros((count,4),dtype='f4');eligible=np.zeros((count,4),bool)
    for i,(name,row) in enumerate(views.items()):
        depth=row['depth'];rgb=row['rgb'];alpha=row['alpha'];require(rgb.shape[:2]==depth.shape==alpha.shape and alpha.dtype==bool,'Matched RGB/alpha/depth camera required')
        xy,z=camera.project(points,name,len(depth),span);pixel[:,i]=xy;coord=np.rint(xy).astype(int);x,y=coord[:,0],coord[:,1]
        inside=(x>=1)&(x<len(depth)-1)&(y>=1)&(y<len(depth)-1)
        eroded=np.asarray(Image.fromarray(alpha.astype('u1')*255).filter(ImageFilter.MinFilter(alpha_guard*2+1)))>0
        alpha_valid=np.zeros(count,bool);alpha_valid[inside]=eroded[y[inside],x[inside]]
        visible,error=camera.visibility(points,depth,name,span,tolerance=depth_tolerance);errors[:,i]=error
        angle=np.maximum(0,geometric[owner]@np.asarray(camera.CARDINALS[name][2]));incidence[:,i]=angle
        valid=inside&alpha_valid&visible&(angle>=min_incidence);eligible[:,i]=valid
        if valid.any():colors[valid,i]=image_sample(rgb,xy[valid])
        # A finite best view is chosen/blended only after explicit cross-view agreement.
        weights[valid,i]=angle[valid]**2*(1-.5*np.clip(error[valid]/depth_tolerance,0,1))
    linear,accepted,conflict,winner,votes=blend_visible_colors(colors,weights,max_difference)
    result=original.copy();result[ys[accepted],xs[accepted]]=np.rint(to_srgb(linear[accepted])*255).astype('u1')
    fields={}
    for name,array,fill in [('sourcePixelXY',pixel,np.nan),('depthError',errors,np.inf),('geometricIncidence',incidence,0),('viewWeight',weights,0),('visibilityAlphaFrontfaceEligible',eligible,False)]:
        out=np.full((size,size)+array.shape[1:],fill,dtype=array.dtype);out[ys,xs]=array;fields[name]=out
    for name,array,fill in [('accepted',accepted,False),('crossViewColorConflict',conflict,False),('selectedHighestWeightView',winner,-1),('eligibleViewCount',votes,0),('confidence',weights.max(1),0)]:
        out=np.full((size,size),fill,dtype=array.dtype);out[ys,xs]=array;fields[name]=out
    fields['projectionEligibleUV']=mask
    fields['originalFallback']=~fields['accepted']
    require(np.array_equal(result[~fields['accepted']],original[~fields['accepted']]),'Unresolved/protected original fallback changed')
    return result,fields
