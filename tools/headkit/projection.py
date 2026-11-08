"""View-projected ownership: measured view masks carried to the 1K atlas through Embree visibility. Kept apart from the
palette so palette changes do not stale the ownership stage."""
import numpy as np
from PIL import Image
from .common import require, verify, pin
from .gltf import mesh
from .textures import surface,pad
from .rays import EmbreeScene


def project_ownership(source, views, embree, output, *, max_subtexel_fraction=.005):
    """View labels are measured annotations, not RGB-threshold skin/hair guesses. The 1K sampling gate uses the same
    reviewed sub-texel allowance as unwrap and bake."""
    verify([embree]);value=mesh(source);positions,owners,_=surface(value,1024,max_subtexel_fraction);mapped=owners>=0
    labels=np.full((1024,1024),255,np.uint8);points=positions[mapped];chosen=np.full(len(points),255,np.uint8)
    scene=EmbreeScene(embree['path'],value['positions'],value['faces']);reports=[]
    try:
        for row in views:
            require(row.get('calibrationReviewed') is True,'Review camera and withheld landmark alignment first')
            with Image.open(row['mask']) as image:
                require(image.mode=='L','Ownership masks must be eight-bit L images')
                mask=np.asarray(image).copy()
            require(np.all((mask<=9)|(mask==255)),'Invalid semantic labels')
            matrix=np.asarray(row['viewProjection'],float);origin=np.asarray(row['cameraOrigin'],float)
            require(matrix.shape==(4,4) and origin.shape==(3,) and np.isfinite(matrix).all() and np.isfinite(origin).all(),'Perspective camera matrix/origin required')
            clip=np.c_[points,np.ones(len(points))]@matrix.T;positive=clip[:,3]>0
            uv=clip[:,:2]/np.maximum(clip[:,3,None],1e-20);uv=uv*np.array([.5,-.5])+.5
            valid=positive&(uv>=0).all(1)&(uv<1).all(1)&(chosen==255)
            index=np.flatnonzero(valid);delta=points[index]-origin;distance=np.linalg.norm(delta,axis=1)
            require(np.all(distance>0),'Camera lies on sampled surface')
            directions=delta/distance[:,None];depth,face_ids,_=scene.query(np.broadcast_to(origin,delta.shape),directions)
            diagonal=float(np.linalg.norm(np.ptp(value['positions'],axis=0)))
            visible=(face_ids>=0)&(np.abs(depth-distance)<=diagonal*1e-5)
            ii=index[visible];q=uv[ii];samples=mask[(q[:,1]*len(mask)).astype(int),(q[:,0]*mask.shape[1]).astype(int)]
            accepted=samples<=9;chosen[ii[accepted]]=samples[accepted]
            reports.append({'name':row['name'],'visible':int(visible.sum()),'assigned':int(accepted.sum())})
    finally:scene.close()
    labels[mapped]=chosen;unresolved=int(np.count_nonzero(chosen==255))
    Image.fromarray(labels).save(output)
    require(unresolved==0,'Unobserved ownership remains; annotate a qualified atlas fallback instead of defaulting to hair')
    labels=pad(labels,mapped);Image.fromarray(labels).save(output)
    return {'output':pin(output),'views':reports,'unresolvedMappedSamples':unresolved}
