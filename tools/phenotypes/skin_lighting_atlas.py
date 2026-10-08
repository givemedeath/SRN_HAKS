"""Geometry-derived C1 masks and explicit derived-skin atlas padding.

Separate from the immutable first diagnostic bake. No original map/geometry is
changed. Unknown or inequivalent UV overlaps and cloth take precedence.
"""
import numpy as np
from PIL import Image,ImageFilter
from target_contract import require


def smoothstep(value):
    t=np.clip(value,0,1);return t*t*(3-2*t)


def sample_texels(image,uv,repeat=False):
    """Top-left raw GLTF UV, texel-center bilinear filtering."""
    h,w=image.shape[:2];xy=np.asarray(uv)*[w,h]-.5;x,y=xy[:,0],xy[:,1]
    x0=np.floor(x).astype(int);y0=np.floor(y).astype(int);a=x-x0;b=y-y0
    if repeat:x1=(x0+1)%w;y1=(y0+1)%h;x0=x0%w;y0=y0%h
    else:x1=np.clip(x0+1,0,w-1);y1=np.clip(y0+1,0,h-1);x0=np.clip(x0,0,w-1);y0=np.clip(y0,0,h-1)
    if image.ndim==3:a=a[:,None];b=b[:,None]
    return image[y0,x0]*(1-a)*(1-b)+image[y0,x1]*a*(1-b)+image[y1,x0]*(1-a)*b+image[y1,x1]*a*b


def geometry_masks(p,n,uv,roles,size,regions,guard=2,position_tolerance=1e-5,normal_tolerance=1e-4):
    require(p.shape==n.shape==uv.shape[:2]+(3,) and len(p)==len(roles),'Mask geometry/normal/role association differs')
    require(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all() and uv.min()>=0 and uv.max()<=1,'Finite unwrapped atlas geometry required')
    position=np.zeros((size,size,3),dtype='f4');normal=np.zeros_like(position);owner=np.full((size,size),-1,dtype='i4')
    influence=np.zeros((size,size),dtype='f4');cloth=np.zeros((size,size),dtype=bool);ambiguous=np.zeros_like(cloth)
    for face,(points,coords,role) in enumerate(zip(p,uv,roles)):
        require(role in ('skin','garment'),'Explicit role required');coords=coords*size-.5
        low=np.maximum(np.ceil(coords.min(0)).astype(int),0);high=np.minimum(np.floor(coords.max(0)).astype(int),size-1)
        if (high<low).any():continue
        a,b,c=coords;matrix=np.stack((b-a,c-a),axis=1);det=np.linalg.det(matrix)
        require(abs(det)>1e-12,'Degenerate UV face requires separate ownership review')
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1];xy=np.stack((xx,yy),axis=-1)
        bc=(xy-a)@np.linalg.inv(matrix).T;bary=np.concatenate((1-bc.sum(-1,keepdims=True),bc),axis=-1)
        inside=(bary>=-1e-9).all(-1)
        if not inside.any():continue
        y=yy[inside];x=xx[inside];weights=bary[inside];q=weights@points;qn=weights@n[face];length=np.linalg.norm(qn,axis=1)
        require((length>1e-10).all(),'Nonzero authored normals required');qn=qn/length[:,None]
        old=owner[y,x];claimed=old>=0
        if claimed.any():
            bad=(np.linalg.norm(position[y,x]-q,axis=1)>position_tolerance)|(np.linalg.norm(normal[y,x]-qn,axis=1)>normal_tolerance)
            ambiguous[y[claimed&bad],x[claimed&bad]]=True
        if role=='garment':cloth[y,x]=True
        value=np.ones(len(q))
        for region in regions:
            distance=abs((q-np.asarray(region['originLocal']))@np.asarray(region['normalLocal']))
            value=np.minimum(value,smoothstep((distance-region['halfWidthMeters'])/region['fadeWidthMeters']))
        unclaimed=~claimed;owner[y[unclaimed],x[unclaimed]]=face;position[y[unclaimed],x[unclaimed]]=q[unclaimed];normal[y[unclaimed],x[unclaimed]]=qn[unclaimed]
        influence[y[unclaimed],x[unclaimed]]=value[unclaimed]
        # Equivalent coincident claims retain the most protective influence.
        influence[y[claimed],x[claimed]]=np.minimum(influence[y[claimed],x[claimed]],value[claimed])
    coverage=owner>=0;strict_zero=coverage&(influence==0)
    forbidden=cloth|ambiguous|strict_zero
    protected=np.asarray(Image.fromarray(forbidden.astype('u1')*255).filter(ImageFilter.MaxFilter(guard*2+1)))>0
    influence[protected|cloth|ambiguous|~coverage]=0
    return {'influence':influence,'coverage':coverage,'garment':cloth,'ambiguous':ambiguous,'strictZero':strict_zero,
        'protected':protected,'ownerFace':owner,'positionLocal':position,'authoredUnitNormal':normal}


def pad_lineage(coverage,forbidden,radius):
    """Deterministic Chebyshev dilation; ties choose the lowest source texel ID.

    Source/destination ownership is explicit. No propagation crosses forbidden
    texels. Empty atlas destinations are inferred skin padding, not body faces.
    """
    require(coverage.dtype==forbidden.dtype==np.bool_ and coverage.shape==forbidden.shape,'Boolean padding masks required')
    require(isinstance(radius,int) and not isinstance(radius,bool) and 1<=radius<=32,'Bounded integer padding radius required')
    h,w=coverage.shape;seed=np.arange(h*w,dtype='i4').reshape(h,w);lineage=np.where(coverage&~forbidden,seed,-1);distance=np.where(lineage>=0,0,-1).astype('i2')
    barrier=forbidden|coverage
    for step in range(1,radius+1):
        best=np.full((h,w),np.iinfo(np.int32).max,dtype='i4')
        for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            yt=slice(max(0,dy),min(h,h+dy));xt=slice(max(0,dx),min(w,w+dx));ys=slice(max(0,-dy),min(h,h-dy));xs=slice(max(0,-dx),min(w,w-dx))
            candidate=lineage[ys,xs];region=best[yt,xt];np.minimum(region,np.where(candidate>=0,candidate,np.iinfo(np.int32).max),out=region)
        fill=(lineage<0)&~barrier&(best<np.iinfo(np.int32).max)
        if not fill.any():break
        lineage[fill]=best[fill];distance[fill]=step
    destination=(distance>0);require(not destination[forbidden|coverage].any(),'Padding changed owned/protected atlas')
    return lineage,distance,destination


def apply_padding(original,treated,lineage,destination,strength):
    require(original.dtype==treated.dtype==np.uint8 and original.shape==treated.shape==lineage.shape==destination.shape,'Padding image/lineage shape differs')
    result=treated.copy()
    if strength==0:
        require(np.array_equal(treated,original),'Untreated reference differs');return result
    ids=lineage[destination];require((ids>=0).all() and (ids<original.size).all(),'Invalid padding lineage')
    result[destination]=treated.ravel()[ids]
    return result
