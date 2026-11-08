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
    pins = [receipt,reference,model,files['frontRender'],files['frontLandmarks']]
    verify(pins,fresh=True)
    with Image.open(reference['path']) as image: rgb = np.asarray(image.convert('RGB'))
    with Image.open(files['frontRender']['path']) as image: front = np.asarray(image.convert('RGB'))
    source = landmarks(rgb,library(runner.bindings,'mediapipe'),model['path'])
    require(source is not None, 'Reference eye landmarks were not detected')
    target = np.load(files['frontLandmarks']['path'],allow_pickle=False)
    circles, refined = iris_circles(np.asarray(Image.fromarray(rgb).convert('L'),np.float32),source)
    spec = dict(frontSha256=files['frontRender']['sha256'], referenceSha256=reference['sha256'])
    spec.update(propose(source,target,circles,result['iris'],rgb.shape,front.shape))
    output.parent.mkdir(parents=True,exist_ok=True)
    require(not output.exists() and not output.with_suffix('.json').exists(), 'Eye evidence already exists')
    canvas = Image.new('RGB',(1024,384),(32,32,32)); pen = ImageDraw.Draw(canvas)
    for row,(label,image) in enumerate([('Approved detail / native eye crop',crop(rgb,source)),
                                       ('Exact masks '+attempt+' / native eye crop',crop(front,target))]):
        image.save(output.with_name(output.stem+('-reference.png' if row==0 else '-front.png')))
        image.thumbnail((1000,150))
        canvas.paste(image,((1024-image.width)//2,row*192+32))
        pen.text((12,row*192+9),label,fill='white')
    verify(pins,fresh=True)
    canvas.save(output)
    write(output.with_suffix('.json'),dict(kind='headbatch-reference-eye-proposal-v1',
          head=head.name,masksAttempt=attempt,inputs=pins,spec=spec,referenceIrisRefined=bool(refined),
          visualReviewRequired=True,approved=False,sheet=pin(output)),fresh=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head',type=Path); parser.add_argument('attempt'); parser.add_argument('output',type=Path)
    args = parser.parse_args(); print(draw(args.head,args.attempt,args.output))
