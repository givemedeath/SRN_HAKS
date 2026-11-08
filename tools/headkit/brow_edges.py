"""Keep upper eyelids on skin and recover only nearby, source-supported brow hairs."""
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation
from .common import require
from .face_masks import EYE_RING, BROW_RING, IRIS, polygon, brow_seed, eye_contours, sample, project, HAIR
from .textures import pad


def upper_lids(shape,pts,hit,cybereye_image_side=None,*,source_hair=None):
    """Lower half of the brow-to-upper-eye gap, anchored to each eye's own landmarks.

    With a source-hair mask, protect the full gap and the eight-pixel end margin,
    preserving genuine hair locks in the added upper band. The legacy lower band
    remains mandatory. The parser can join a dark lid crease to a brow. Its label is therefore not
    evidence that the crease is hair. Keep the landmark brow and eye opening out.
    """
    require(cybereye_image_side in (None,'left','right'),'Unknown cybereye side')
    if source_hair is not None:
        require(isinstance(source_hair,np.ndarray) and source_hair.shape==shape and source_hair.dtype==bool,
                'Source hair needs a matching boolean front mask')
    ys,xs=np.indices(shape);out=np.zeros(shape,bool)
    for side,ring in EYE_RING.items():
        eye=pts[ring[8:]+[ring[0]]];brow=pts[BROW_RING[side][5:]]
        eye=eye[np.argsort(eye[:,0])];brow=brow[np.argsort(brow[:,0])]
        width=eye[-1,0]-eye[0,0]
        require(np.isfinite(eye).all() and np.isfinite(brow).all() and width>0,'Invalid eyelid landmarks')
        ey=np.interp(np.arange(shape[1]),eye[:,0],eye[:,1])
        by=np.interp(np.arange(shape[1]),brow[:,0],brow[:,1])
        top=(ey+by)/2
        local=(xs>=max(eye[0,0]-.18*width,brow[0,0])) & (xs<=min(eye[-1,0]+.18*width,brow[-1,0]))
        local &= (ys>=top[None,:]) & (ys<=ey[None,:]+1) & (ey>by+2)[None,:]
        if source_hair is not None:
            gap=(xs>=min(eye[0,0]-.18*width,brow[0,0])-8) & (xs<=max(eye[-1,0]+.18*width,brow[-1,0])+8)
            gap &= (ys>=by[None,:]+1) & (ys<=ey[None,:]+1) & (ey>by+2)[None,:]
            local |= gap & ~source_hair
        local &= ~polygon(shape,pts,EYE_RING[side]) & ~polygon(shape,pts,BROW_RING[side])
        out |= local
    if cybereye_image_side is not None:
        cyber=xs<pts[168,0] if cybereye_image_side=='left' else xs>=pts[168,0]
        out &= ~cyber
    return out & hit


def fringe(seed,core,eyes,excluded,maximum_front_pixels=3):
    """Recover source-brow edges within a bounded distance, excluding lids and remote marks."""
    require(type(maximum_front_pixels) is int and 1 <= maximum_front_pixels <= 8,
            "Brow edge reach must be an integer from 1 to 8 source pixels")
    return seed & binary_dilation(core,iterations=maximum_front_pixels) & ~eyes & ~excluded


def apply_regions(labels,mapped,brows,lids):
    """Lid skin takes precedence over brow recovery; leave other material channels intact."""
    recovered=mapped & brows & ~lids & (labels==0)
    removed=mapped & lids & (labels==1)
    result=labels.copy();result[recovered]=1;result[removed]=0
    return result,{'changedTexels':int(recovered.sum()),'upperLidHairToSkinTexels':int(removed.sum())}


def adjust(labels,value,masks,mapped,maximum_front_pixels=3,*,recover_brows=False,cybereye_image_side=None):
    require(type(recover_brows) is bool,'browSeedGuard must be boolean')
    files=masks['files']
    with Image.open(files['frontRender']['path']) as image:rgb=np.asarray(image.convert('RGB'))
    with Image.open(files['frontLabels']['path']) as image:parsed=np.asarray(image)
    pts=np.load(files['frontLandmarks']['path'],allow_pickle=False)
    with np.load(files['frontView']['path'],allow_pickle=False) as saved:view={k:saved[k] for k in saved.files}
    lids=upper_lids(parsed.shape,pts,view['hit'],cybereye_image_side,source_hair=parsed==HAIR)
    eyes=binary_dilation(polygon(parsed.shape,pts,EYE_RING['R']) | polygon(parsed.shape,pts,EYE_RING['L']),iterations=1)
    excluded=lids.copy()
    if 'eyeContours' in masks:
        contours=eye_contours(rgb,masks['eyeContours'],{s:pts[c] for s,(c,_) in IRIS.items()},view['hit'])
        eyes=contours['opening'];excluded |= contours['excludeBrow']
    repair=np.zeros_like(eyes);seed=np.zeros_like(eyes)
    if recover_brows:
        with Image.open(files['brow']['path']) as image:atlas=np.asarray(image.convert('L'),np.float32)/255
        seed=brow_seed(parsed,pts,eyes | excluded,view['hit']) & ~excluded & ~eyes
        core=sample(view,atlas[...,None],value['uv'])[...,0]>.5
        repair=fringe(seed,core,eyes,excluded,maximum_front_pixels)
        require(repair.any(),'No source-bound brow edge evidence')
    maps,_=project(value,view,{'browEdge':repair.astype(np.float32),'upperLid':lids.astype(np.float32)},size=len(labels),visible_only=('upperLid',))
    result,report=apply_regions(labels,mapped,maps['browEdge']>127,maps['upperLid']>127)
    result=pad(result[...,None],mapped)[...,0]
    report.update(maximumFrontPixels=maximum_front_pixels if recover_brows else None,
                  sourceBrowPixels=int(seed.sum()),boundedBrowPixels=int(repair.sum()),upperLidPixels=int(lids.sum()))
    return result,report


def restore(labels,value,masks,mapped,maximum_front_pixels=3):
    """Compatibility entry point for bounded brow recovery, with mandatory lid protection."""
    return adjust(labels,value,masks,mapped,maximum_front_pixels,recover_brows=True)
