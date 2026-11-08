"""Propose source-bound eye registration and native crops; never edit a head or approve a proposal."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from headkit.common import library, pin, read, require, verify, write
from headkit.face_masks import EYE_RING, iris_circles, landmarks
from headkit.reference_eyes import registration
from headkit.runner import Runner


def propose(source, target, circles, target_circles, source_shape, target_shape):
    """Register each eye by its own lid span, preserving different horizontal/vertical framing."""
    result = {}
    for side in ('R', 'L'):
        src, dst = source[EYE_RING[side]], target[EYE_RING[side]]
        a, b = np.ptp(src, axis=0), np.ptp(dst, axis=0)
        require(np.isfinite(a).all() and np.isfinite(b).all() and (a>2).all() and (b>2).all(),
                'Eye landmarks need nondegenerate open lid spans')
        centre, radius = circles[side]
        box = [*centre, radius, radius]
        projected = [*target_circles[side][0], *(radius*b/a)]
        registration(box, source_shape); registration(projected, target_shape)
        result[side] = {'reference':list(map(float,box)), 'target':list(map(float,projected))}
    require(result['R']['reference'][0] < result['L']['reference'][0] and
            result['R']['target'][0] < result['L']['target'][0], 'Keep eyes in front-view order')
    return result


def crop(rgb, pts):
    eyes = pts[EYE_RING['R']+EYE_RING['L']]
    margin = max(8, np.ptp(eyes[:,0])*.07)
    low = np.maximum(0, np.floor(eyes.min(0)-margin).astype(int))
    high = np.minimum(np.array(rgb.shape[:2][::-1]), np.ceil(eyes.max(0)+margin).astype(int))
    return Image.fromarray(rgb).crop((*low,*high))


def contour_proposal(rgb, labels, pts, circles, hit, registrations):
    # Propose native opening/iris/lid polygons; the result needs visual review.
    import hashlib
    from scipy.ndimage import binary_dilation, label
    from headkit.face_masks import polygon, eye_contours, render_masks

    def trace(mask):
        rows = np.flatnonzero(mask.any(axis=1))
        require(len(rows)>2, 'No visible eye contour')
        left, right = [], []
        for y in rows:
            xs = np.flatnonzero(mask[y])
            left.append([int(xs.min()),int(y)])
            right.append([int(xs.max()),int(y)])
        return left + right[::-1]

    circles = {side:(np.asarray(row[0]),row[1]) for side,row in circles.items()}
    _,hard = render_masks(rgb,labels,pts,circles,hit)
    spec = {'rgbSha256':hashlib.sha256(rgb.tobytes()).hexdigest()}
    yy,xx = np.indices(hit.shape)
    middle = (circles['R'][0][0]+circles['L'][0][0])/2
    for side in ('R','L'):
        opening = hard['eye'] & hit & ((xx<middle) if side=='R' else (xx>=middle))
        parts,_ = label(opening)
        areas = np.bincount(parts.ravel());areas[0]=0
        require(areas.max()>0, 'Missing eye opening: '+side)
        opening = parts==int(areas.argmax())
        outline = trace(opening)
        area = polygon(hit.shape,np.asarray(outline),range(len(outline)))
        cx,cy,rx,ry = registrations[side]['target']
        iris = area & (((xx-cx)/rx)**2+((yy-cy)/ry)**2<=1)
        for _ in range(4):
            iris_outline = trace(iris)
            raster = polygon(hit.shape,np.asarray(iris_outline),range(len(iris_outline)))
            spill = raster & ~area
            if not spill.any():break
            iris &= ~binary_dilation(spill)
        require(not spill.any(), 'Iris trace needs manual corner review')
        spec[side] = {'opening':outline,'iris':iris_outline,
                      'excludeBrow':trace(binary_dilation(area,iterations=3)&hit)}
    regions = eye_contours(rgb,spec,{side:row[0] for side,row in circles.items()},hit)
    overlay = rgb.copy()
    overlay[regions['excludeBrow'] & ~regions['opening']] = [0,220,255]
    overlay[regions['opening']] = [0,210,40]
    overlay[regions['iris']] = [255,0,220]
    return spec,overlay



def evidence_sheet(output, rows):
    paths = {name:output.with_name(output.stem+'-'+name+'.png') for name,_,_ in rows}
    require(len(paths)==len(rows), 'Eye crop names must be distinct')
    require(not output.exists() and all(not p.exists() for p in paths.values()), 'Eye evidence already exists')
    canvas = Image.new('RGB',(1024,192*len(rows)),(32,32,32)); pen = ImageDraw.Draw(canvas)
    for row,(name,label,native) in enumerate(rows):
        native.save(paths[name])
        thumbnail = native.copy(); thumbnail.thumbnail((1000,150))
        canvas.paste(thumbnail,((1024-thumbnail.width)//2,row*192+32))
        pen.text((12,row*192+9),label,fill='white')
    canvas.save(output)
    return {name:pin(path) for name,path in paths.items()}

def draw(head, attempt, output):
    head = head.resolve(); output = output.resolve()
    runner = Runner(head/'manifest.json',head/'bindings.json',head/'run')
    result = runner.result('masks', require_review=False)
    receipt = runner.state['stages']['masks']
    require(Path(receipt['path']).parent.name == attempt, 'Name the current masks attempt')
    role = 'detail' if runner.data.get('profile','pixal-single-v1') == 'pixal-single-v1' else 'frontDetail'
    reference = pin(runner.input(role)); files = result['files']
    entry = runner.bindings['libraries']['mediapipe']
    model = pin(Path(entry['directory'])/'models/face_landmarker.task')
    pins = [receipt,reference,model,files['frontRender'],files['frontLandmarks'],files['frontLabels'],files['frontView']]
    verify(pins,fresh=True)
    with Image.open(reference['path']) as image: rgb = np.asarray(image.convert('RGB'))
    with Image.open(files['frontRender']['path']) as image: front = np.asarray(image.convert('RGB'))
    source = landmarks(rgb,library(runner.bindings,'mediapipe'),model['path'])
    require(source is not None, 'Reference eye landmarks were not detected')
    target = np.load(files['frontLandmarks']['path'],allow_pickle=False)
    circles, refined = iris_circles(np.asarray(Image.fromarray(rgb).convert('L'),np.float32),source)
    spec = dict(frontSha256=files['frontRender']['sha256'], referenceSha256=reference['sha256'])
    with Image.open(files['frontLabels']['path']) as image: labels = np.asarray(image)
    with np.load(files['frontView']['path'],allow_pickle=False) as saved: hit = saved['hit']
    correction=contour_overlay=None;proposal_error=None
    try:
        spec.update(propose(source,target,circles,result['iris'],rgb.shape,front.shape))
        correction,contour_overlay = contour_proposal(front,labels,target,result['iris'],hit,spec)
    except ValueError as error:
        proposal_error=str(error)
    output.parent.mkdir(parents=True,exist_ok=True)
    require(not output.exists() and not output.with_suffix('.json').exists(), 'Eye evidence already exists')
    rows=[('reference', 'Approved detail / native eye crop', crop(rgb,source)),
          ('front', 'Exact masks '+attempt+' / native eye crop', crop(front,target))]
    if contour_overlay is not None:
        rows.append(('contours','Contour proposal: green opening, magenta iris, cyan skin lids',crop(contour_overlay,target)))
    crops = evidence_sheet(output,rows)
    verify(pins,fresh=True)
    write(output.with_suffix('.json'),dict(kind='headbatch-reference-eye-proposal-v1',
          head=head.name,masksAttempt=attempt,inputs=pins,spec=spec,
          **({'eyeContours':correction} if correction is not None else {'contourProposalError':proposal_error}),
          referenceIrisRefined=bool(refined),
          visualReviewRequired=True,approved=False,sheet=pin(output),crops=crops),fresh=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head',type=Path); parser.add_argument('attempt'); parser.add_argument('output',type=Path)
    args = parser.parse_args(); print(draw(args.head,args.attempt,args.output))
