"""Draw an orthographic baked material chart in head-relative coordinates."""
import argparse
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from headbatch.head_files import read
from headkit.common import pin, verify
from headkit.face_masks import front_view, sample
from headkit.gltf import mesh


def chart(head, attempt, axes, output):
    if not re.fullmatch(r'attempt-[0-9]+', attempt) or output.exists():
        raise ValueError('An exact bake attempt and fresh output path are required')
    receipt_pin = pin(head/'run'/'bake'/attempt/'receipt.json')
    receipt = read(receipt_pin['path'])
    if receipt['state'] != 'complete':
        raise ValueError('A complete bake is required')
    unwrap = receipt['dependencies']['unwrap']
    colour = receipt['result']['maps']['basecolor-4096.png']
    verify([receipt_pin, unwrap, colour], fresh=True)
    source = read(unwrap['path'])['result']['mesh']
    embree = read(head/'bindings.json')['embree']
    verify([source, embree], fresh=True)
    value = mesh(source['path'])
    pos = value['positions']
    rel = (pos-pos.min(0))/np.maximum(np.ptp(pos, axis=0), 1e-12)
    if axes == 'zy':
        rel = np.column_stack((rel[:, 2], rel[:, 1], -rel[:, 0]))
    value['positions'] = np.ascontiguousarray(rel, dtype=np.float32)
    size = 640
    view = front_view(value, embree, size)
    with Image.open(colour['path']) as texture:
        rgb = np.asarray(texture.convert('RGB'))
    image = Image.fromarray(sample(view, rgb, value['uv']).clip(0,255).astype(np.uint8))
    pen = ImageDraw.Draw(image)
    for i in range(11):
        px = round(size/2 + (i/10-.5)*size/view['span'])
        py = size-1-px
        pen.line((px,0,px,size-1), fill='#618596')
        pen.line((0,py,size-1,py), fill='#708595')
        pen.text((px+1,6),str(i/10))
        pen.text((3,py+1),str(i/10))
    verify([receipt_pin, unwrap, colour, source, embree], fresh=True)
    with output.open('xb') as target:
        image.save(target, format='PNG')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head', type=Path)
    parser.add_argument('attempt')
    parser.add_argument('axes', choices=('xy','zy'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    chart(args.head, args.attempt, args.axes, args.output)
