"""Restore approved reference eye detail on the reviewed opening of an exact front bake."""
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates, distance_transform_edt
from .common import pin, require


def registration(box, shape):
    values = np.asarray(box, dtype=float)
    require(values.shape == (4,) and np.isfinite(values).all(), 'Eye registration needs cx, cy, rx, ry')
    centre, radius = values[:2], values[2:]
    limit = np.array(shape[:2][::-1])
    require(np.all(radius >= 2) and np.all(radius <= limit*.08) and
            np.all(centre-radius >= 0) and np.all(centre+radius < limit),
            'Eye registration exceeds its source frame')
    return centre, radius


def restore(colour, labels, opening, value, masks, reference, spec, *, contours=None):
    """Restore eye openings; optionally include the exact reviewed skin-lid polygons.

    Lid sampling is front-visible and skin/iris-only. Existing opening-only recipes
    retain their original behavior. Polygons and source bytes must be reviewed again
    when the front render changes.
    """
    require(spec.get('frontSha256') == masks['frontRender']['sha256']
            and spec.get('referenceSha256') == pin(reference)['sha256'],
            'Eye repair needs the reviewed front render and reference bytes')
    with Image.open(reference) as image:
        detail = np.asarray(image.convert('RGB'), dtype=np.float32)
    with np.load(masks['frontView']['path'], allow_pickle=False) as view:
        hit, faces = view['hit'], view['face']
        centre, span = view['centre'], float(view['span'])
        zbuf = view['zbuf'] if 'zbuf' in view else None
    size = len(hit)
    require(hit.shape == (size,size) and span > 0, 'Expected a square front camera')
    include_lids = spec.get('includeLids', False)
    require(type(include_lids) is bool, 'includeLids must be boolean')
    lid_alpha = None
    if include_lids:
        from .face_masks import eye_contours
        require(contours is not None and zbuf is not None, 'Lid repair needs reviewed contours and front depth')
        require(pin(masks['frontRender']['path'])['sha256'] == spec['frontSha256'], 'Changed eye front render')
        with Image.open(masks['frontRender']['path']) as image:
            front = np.asarray(image.convert('RGB'))
        centres = {side: np.asarray(spec[side]['target'][:2]) for side in ('R','L')}
        regions = eye_contours(front, contours, centres, hit)
        lid_alpha = np.clip(distance_transform_edt(regions['opening'] | regions['excludeBrow'])/2, 0, 1)
    counts = {}
    sides = [spec[key] for key in ('R','L')]
    require(sides[0]['target'][0] < sides[1]['target'][0] and sides[0]['reference'][0] < sides[1]['reference'][0],
            'Keep the subject right and left eyes in front-view order')
    for side, eye in zip(('R','L'), sides):
        dst, extent = registration(eye['target'], hit.shape)
        src, radius = registration(eye['reference'], detail.shape)
        reach = 4 if include_lids else 3
        x0,y0 = np.maximum(0,np.floor(dst-reach*extent).astype(int))
        x1,y1 = np.minimum(size,np.ceil(dst+reach*extent).astype(int)+1)
        region = np.s_[y0:y1,x0:x1]
        count = 0
        for face in np.unique(faces[region][hit[region]]):
            tri = value['uv'][face]*len(colour)
            low = np.maximum(0,np.floor(tri.min(0)).astype(int))
            high = np.minimum(len(colour)-1,np.ceil(tri.max(0)).astype(int))
            block = np.s_[low[1]:high[1]+1,low[0]:high[0]+1]
            eligible = np.isin(labels[block], (0,8))
            if not include_lids:
                eligible &= opening[block]>.02
            iy,ix = np.nonzero(eligible)
            if not len(ix):
                continue
            x,y = ix+low[0],iy+low[1]
            basis = (tri[1:]-tri[0]).T
            require(abs(np.linalg.det(basis)) > 1e-12, 'Degenerate eye UV triangle')
            uv = np.linalg.solve(basis, (np.column_stack((x+.5,y+.5))-tri[0]).T).T
            bary = np.column_stack((1-uv.sum(1),uv))
            inside = (bary>=0).all(1)
            xyz = bary @ value['positions'][value['faces'][face]]
            px = (xyz[:,:2]-centre[:2])*[size/span,-size/span] + (size-1)/2
            within = inside & (np.abs(px-dst) <= reach*extent).all(1)
            if include_lids:
                alpha = map_coordinates(lid_alpha, px[:,::-1].T, order=1, mode='constant', cval=0, prefilter=False)
                pixel = np.rint(px).astype(int).clip(0,size-1)
                visible = hit[pixel[:,1],pixel[:,0]] & (np.abs(xyz[:,2]-zbuf[pixel[:,1],pixel[:,0]]) <= span*.002)
                within &= visible & (alpha>.02)
            if not within.any():
                continue
            x,y = x[within],y[within]
            coords = src+(px[within]-dst)*radius/extent
            require(np.all(coords>=0) and np.all(coords < np.array(detail.shape[:2][::-1])-1),
                    'Registered eye exceeds the reference')
            samples = np.column_stack([map_coordinates(detail[:,:,i],coords[:,::-1].T,
                                       order=1, mode='nearest', prefilter=False) for i in range(3)])
            alpha = alpha[within,None] if include_lids else opening[y,x,None]
            colour[y,x] += alpha*(samples-colour[y,x])
            count += len(y)
        require(count > 0, 'No mapped opening in the registered '+side+' eye')
        counts[side] = count
    return counts
