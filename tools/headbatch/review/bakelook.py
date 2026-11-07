"""Render the exact baked base color on its UV mesh with complete ray coverage and no added lighting."""
import argparse
from pathlib import Path
import re

import numpy as np
from PIL import Image

from _fit_views import bounds, tile
from headkit.common import pin, read, require, verify, write
from headkit.diagnostics import sheet
from headkit.gltf import mesh
from headkit.mesh import BASIS
from headkit.rays import EmbreeScene


def draw(head, attempt):
    head = head.resolve()
    require(re.fullmatch(r'attempt-[0-9]+', attempt), 'Name the bake attempt')
    receipt = pin(head/'run/bake'/attempt/'receipt.json')
    bake = read(receipt['path'])
    require(bake['state']=='complete', 'Completed bake required')
    unwrap = bake['dependencies']['unwrap']
    repaired = read(unwrap['path'])['dependencies']['repair']
    fit = read(repaired['path'])['dependencies']['fit']
    source = read(unwrap['path'])['result']['mesh']
    atlas = next(p for p in bake['outputs'] if Path(p['path']).name=='basecolor-2048.png')
    embree = read(head/'bindings.json')['embree']
    pins = [receipt,unwrap,repaired,fit,source,atlas,embree]
    verify(pins,fresh=True)
    folder = head/'review-evidence'/('bake-ray-'+attempt)
    folder.mkdir(exist_ok=False)
    value = mesh(source['path'])
    v, f = value['positions'], value['faces']
    with Image.open(atlas['path']) as image:
        pixels = np.asarray(image.convert('RGB'))
    matrix = np.asarray(read(fit['path'])['result']['matrix']) @ BASIS
    low, high = bounds(v,matrix)
    center, span = (low+high)/2, max(high-low)*1.08
    scene = EmbreeScene(embree['path'],v,f)
    try:
        views=[]
        for label, axis in [('Front',(0,1,0)),('Side',(1,0,0)),('Rear',(0,-1,0))]:
            im=tile((scene,v,f,matrix),np.asarray(axis,float),center,span,640,False,texture=(value['uv'],pixels))
            views.append((f'{label} | baked base color | {attempt}',im))
        sheet(views,folder/'sheet.png',640,columns=3)
    finally:
        scene.close()
    verify(pins,fresh=True)
    write(folder/'evidence.json',{'inputs':pins,'sheet':pin(folder/'sheet.png'),'approved':False},fresh=True)
    return folder/'sheet.png'


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('head',type=Path)
    p.add_argument('attempt')
    args=p.parse_args()
    print(draw(args.head,args.attempt))
