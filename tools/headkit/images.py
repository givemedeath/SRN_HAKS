"""Measured positive pair alignment; one shared alpha crop and placement evidence."""
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageChops, ImageDraw
from .common import positive, require, pin, write


def similarity(source, target, max_relative=1e-3):
    source, target = np.asarray(source, float), np.asarray(target, float)
    require(source.shape == target.shape and source.ndim == 2 and source.shape[0] >= source.shape[1] + 1,
            'Enough corresponding landmarks required')
    require(np.isfinite(source).all() and np.isfinite(target).all(), 'Finite landmarks required')
    a, b = source - source.mean(0), target - target.mean(0)
    require(np.linalg.matrix_rank(a) >= source.shape[1] - 1 and np.linalg.matrix_rank(b) >= source.shape[1] - 1,
            'Degenerate landmark configuration')
    u, _, vt = np.linalg.svd(a.T @ b)
    rotation = u @ vt
    require(np.linalg.det(rotation) > 0, 'Reflected correspondences rejected')
    scale = float(np.sum((a @ rotation) * b) / np.sum(a * a))
    positive(scale, 'uniform scale')
    translation = target.mean(0) - source.mean(0) @ rotation * scale
    errors = np.linalg.norm(source @ rotation * scale + translation - target, axis=1)
    extent = float(np.linalg.norm(np.ptp(target, axis=0)))
    require(extent > 0 and errors.max() <= extent * max_relative, 'Landmark fitting residual exceeds declared bound')
    return scale, rotation, translation, errors


def prepare(clay_path, detail_path, config, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    clay, detail = (Image.open(p).convert('RGBA') for p in (clay_path, detail_path))
    require(clay.size == detail.size, 'Pair must have matching canvases before alignment')
    points = config.get('landmarks', [])
    require(len(points) >= 3 and len({p['name'] for p in points}) == len(points), 'Named, distinct paired landmarks required')
    width, height = clay.size
    a = np.asarray([p['clay'] for p in points], float) * [width, height]
    b = np.asarray([p['detail'] for p in points], float) * [width, height]
    require(np.all((a >= 0) & (a <= [width, height])) and np.all((b >= 0) & (b <= [width, height])),
            'Landmarks must be normalized image coordinates')
    scale, rotation, translation, errors = similarity(a, b, config.get('maximumRelativeResidual', .01))
    require(.97 <= scale <= 1.03, 'Pair needs a larger design/alignment correction')
    require(abs(math.degrees(math.atan2(rotation[0, 1], rotation[0, 0]))) <= 3, 'Pair rotation exceeds bounded correction')
    matrix = np.linalg.inv(scale * rotation.T); offset = -matrix @ translation
    aligned = clay.transform(detail.size, Image.Transform.AFFINE,
                             (*matrix[0], offset[0], *matrix[1], offset[1]), Image.Resampling.BICUBIC)
    a_mask, b_mask = np.asarray(aligned.getchannel('A')) > 127, np.asarray(detail.getchannel('A')) > 127
    require(a_mask.any() and b_mask.any() and not a_mask.all() and not b_mask.all(), 'Nonempty transparent-background inputs required')
    for mask in (a_mask,b_mask):
        require(not (mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any()),'Input silhouette is clipped at canvas edge')
    iou = float(np.count_nonzero(a_mask & b_mask) / np.count_nonzero(a_mask | b_mask))
    require(iou >= config.get('minimumSilhouetteIoU', .94), 'Paired silhouette alignment failed')
    mask = ImageChops.lighter(aligned.getchannel('A'), detail.getchannel('A'))
    aligned.save(output / 'geometry-pair.png'); detail.save(output / 'detail-pair.png')
    Image.merge('RGBA', (mask, mask, mask, mask)).save(output / 'common-mask.png')
    overlay = Image.blend(aligned, detail, .5); draw = ImageDraw.Draw(overlay)
    for i, (point, value) in enumerate(zip(b, points), 1):
        x, y = point; draw.ellipse((x-5, y-5, x+5, y+5), outline='yellow', width=2)
        draw.text((x+7, y), f'{i}: {value["name"]}', fill='yellow')
    overlay.save(output / 'alignment-overlay.png')
    result = {'silhouetteIoU': iou, 'residualPixels': errors.tolist(), 'scale': scale,
              'rotation': rotation.tolist(), 'translation': translation.tolist(), 'manualReviewRequired': True,
              'landmarksAreOperatorMeasurements': True,
              'images': {name: pin(output / name) for name in ('geometry-pair.png', 'detail-pair.png', 'common-mask.png', 'alignment-overlay.png')}}
    write(output / 'alignment.json', result, fresh=True)
    return result


def prepare_multiview(pairs, config, output):
    """Keep a common canvas; never independently crop the four geometry views."""
    require(set(pairs)=={'front','left','back','right'}, 'Four cardinal view pairs required')
    require(config.get('rigReviewed') is True and config.get('fovDegrees')==20,
            'Review the frozen 20-degree rig and its cardinal view assignments')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    evidence={};metrics=[];canvas=None
    expected={'front':0,'left':90,'back':180,'right':270}
    for view, paths in pairs.items():
        row=config['views'][view]
        require(row.get('azimuthDegrees')==expected[view] and row.get('orientationReviewed') is True,
                'View orientation needs explicit cardinal review: '+view)
        result=prepare(paths[0],paths[1],row['alignment'],output/view)
        with Image.open(output/view/'geometry-pair.png') as image:
            require(canvas in (None,image.size),'All views must share the same canvas');canvas=image.size
            mask=np.asarray(image.getchannel('A'))>127
            y,x=np.nonzero(mask)
            require(x.min()>1 and y.min()>1 and x.max()<image.width-2 and y.max()<image.height-2,
                    'Clipped multiview silhouette: '+view)
        crown=np.asarray(row['crown'],float);jaw=np.asarray(row['chin'],float);center=np.asarray(row['skullCenter'],float)
        require(crown.shape==jaw.shape==center.shape==(2,) and np.isfinite([crown,jaw,center]).all()
                and np.all((np.array([crown,jaw,center])>=0)&(np.array([crown,jaw,center])<=1)), 'Normalized cranial measurements required')
        require(jaw[1]>crown[1],'Crown/chin orientation reversed')
        metrics.append([jaw[1]-crown[1],*center]);evidence[view]=result
    metrics=np.asarray(metrics);reference=metrics[0]
    require(np.ptp(metrics[:,0])/reference[0]<=.02,'Multiview skull heights differ by more than 2%')
    require(np.max(np.ptp(metrics[:,1:],axis=0))<=.02,'Multiview skull centers drift by more than 2% of canvas')
    result={'views':evidence,'cranialMeasurements':metrics.tolist(),'commonCanvas':list(canvas),
            'independentCropping':False,'rigFovDegrees':20,'manualReviewRequired':True}
    write(output/'alignment.json',result,fresh=True);return result
