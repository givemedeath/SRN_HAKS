"""Read-only CPU cardinal projection/depth kernel for reference-color feasibility.

It neither rebakes colors nor changes a mesh. Cardinal bases match the installed
Z-up Pixal3D orbit. Anatomical registration remains an explicit reviewed input.
"""
import numpy as np
from PIL import Image,ImageFilter
from target_contract import require

CARDINALS={
 'front':([1,0,0],[0,0,1],[0,-1,0]),
 'left':([0,1,0],[0,0,1],[1,0,0]),
 'back':([-1,0,0],[0,0,1],[0,1,0]),
 'right':([0,-1,0],[0,0,1],[-1,0,0])}


def project(points,view,size,span=1.1,center=(0,0,0)):
    require(view in CARDINALS and isinstance(size,int) and size>0 and np.isfinite(span) and span>0,'Explicit cardinal camera required')
    points=np.asarray(points,float);require(points.shape[-1]==3 and np.isfinite(points).all(),'Finite positions required')
    right,up,outward=np.asarray(CARDINALS[view],float);p=points-np.asarray(center)
    image=np.stack((p@right*size/span+size/2-.5,-p@up*size/span+size/2-.5),axis=-1)
    return image,p@outward


def raster_depth(positions,view,size=1024,span=1.1,center=(0,0,0)):
    p=np.asarray(positions,float);require(p.ndim==3 and p.shape[1:]==(3,3),'Ordered triangles required')
    xy,z=project(p,view,size,span,center);depth=np.full((size,size),-np.inf,dtype='f4');face=np.full((size,size),-1,dtype='i4')
    for index,(coords,values) in enumerate(zip(xy,z)):
        low=np.maximum(np.ceil(coords.min(0)).astype(int),0);high=np.minimum(np.floor(coords.max(0)).astype(int),size-1)
        if (high<low).any():continue
        a,b,c=coords;matrix=np.stack((b-a,c-a),axis=1);det=np.linalg.det(matrix)
        if abs(det)<1e-12:continue # Side-on faces do not cover image area.
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1];bc=(np.stack((xx,yy),axis=-1)-a)@np.linalg.inv(matrix).T
        bary=np.concatenate((1-bc.sum(-1,keepdims=True),bc),axis=-1);inside=(bary>=-1e-9).all(-1)
        d=bary@values;old=depth[yy,xx];winner=inside&(d>old)
        depth[yy[winner],xx[winner]]=d[winner];face[yy[winner],xx[winner]]=index
    return {'depth':depth,'face':face,'silhouette':face>=0,'camera':{'view':view,'size':size,'span':span,'center':list(center),
        'right':CARDINALS[view][0],'up':CARDINALS[view][1],'outward':CARDINALS[view][2],
        'depthPolicy':'Maximum point dot outward is nearest; both sides considered, no background color borrowed.'}}


def visibility(points,depth,view,span=1.1,center=(0,0,0),tolerance=1e-5):
    xy,z=project(points,view,len(depth),span,center);coord=np.rint(xy).astype(int);x,y=coord[:,0],coord[:,1]
    inside=(x>=0)&(x<len(depth))&(y>=0)&(y<len(depth));visible=np.zeros(len(points),dtype=bool);error=np.full(len(points),np.inf)
    error[inside]=abs(z[inside]-depth[y[inside],x[inside]])
    visible[inside]=np.isfinite(depth[y[inside],x[inside]])&(error[inside]<=tolerance)
    return visible,error


def silhouette_metrics(candidate,reference,max_radius=32):
    require(candidate.dtype==reference.dtype==np.bool_ and candidate.shape==reference.shape,'Boolean matched silhouette masks required')
    def bounds(mask):
        y,x=np.nonzero(mask);require(len(x)>0,'Empty silhouette');return [int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]
    cb,rb=bounds(candidate),bounds(reference);intersection=int((candidate&reference).sum());union=int((candidate|reference).sum())
    def boundary(mask):return mask&~(np.asarray(Image.fromarray(mask.astype('u1')*255).filter(ImageFilter.MinFilter(3)))>0)
    a,b=boundary(candidate),boundary(reference)
    def distances(query,other):
        ys,xs=np.nonzero(query);result=np.full(len(xs),max_radius+1,dtype='i2')
        grown=other.copy()
        for radius in range(max_radius+1):
            if radius:grown=np.asarray(Image.fromarray(grown.astype('u1')*255).filter(ImageFilter.MaxFilter(3)))>0
            hit=grown[ys,xs]&(result==max_radius+1);result[hit]=radius
        return result
    error=np.r_[distances(a,b),distances(b,a)]
    return {'intersectionOverUnion':intersection/union,'candidatePixels':int(candidate.sum()),'referencePixels':int(reference.sum()),
        'candidateBoundsXYXY':cb,'referenceBoundsXYXY':rb,
        'widthAndHeightDeltaPixels':[(cb[2]-cb[0])-(rb[2]-rb[0]),(cb[3]-cb[1])-(rb[3]-rb[1])],
        'boundsCenterDeltaPixels':[(cb[0]+cb[2]-rb[0]-rb[2])/2,(cb[1]+cb[3]-rb[1]-rb[3])/2],
        'symmetricBoundaryChebyshevP50P95MaxCapped':np.percentile(error,[50,95,100]).tolist(),
        'boundarySamplesBeyond32Pixels':int((error>max_radius).sum()),'boundarySampleCount':len(error),
        'limits':'Pixel-center fixed camera silhouette only; boundary error is Chebyshev and capped at33; no local registration/warp or landmark acceptance.'}

