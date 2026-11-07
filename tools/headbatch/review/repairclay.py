"""Compare one repair's input to reduction or neck cutting with its final GLB and stored normals."""
import argparse
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import numpy as np

from headkit.common import pin, read, require, verify
from headkit.diagnostics import sheet
from headkit.gltf import mesh
from headkit.mesh import BASIS
from headkit.rays import EmbreeScene
from _fit_views import bounds, tile


def draw(head, attempt, output):
    require(re.fullmatch(r'attempt-[0-9]+', attempt), 'Name one repair attempt')
    folder = head.resolve()/'run/repair'/attempt
    receipt = pin(folder/'receipt.json')
    data = read(receipt['path'])
    require(data.get('state') == 'complete', 'A completed repair is required')
    fit = data['dependencies']['fit']
    result = data['result']
    cut = (result.get('neck') or {}).get('cut')
    before = cut['uncut'] if cut else result['master']
    after = result['source']
    for artifact in (before, after):
        require(Path(artifact['path']).parent == folder and artifact in data['outputs'], 'Mesh must be a pinned output of the named repair')
    embree = read(head/'bindings.json')['embree']
    pins = [receipt, fit, before, after, embree]
    verify(pins, fresh=True)
    matrix = np.asarray(read(fit['path'])['result']['matrix']) @ BASIS
    size = 360
    views = [('Front',(0.,1.,0.)), ('Side',(1.,0.,0.)), ('Rear',(0.,-1.,0.)), ('Under jaw',(0.,.12,-1.))]
    tiles = []
    for label, artifact in [('Before cut' if cut else 'Before reduction',before), ('Final',after)]:
        value = mesh(artifact['path'])
        v,f = value['positions'],value['faces']
        if not tiles:
            low, high = bounds(v, matrix)
            center = (low+high)/2
            span = max(high-low)*1.10
        scene = EmbreeScene(embree['path'],v.astype(np.float32,copy=False),f.astype(np.uint32,copy=False))
        try:
            for angle, direction in views:
                toward = np.array(direction)/np.linalg.norm(direction)
                im = tile((scene,v,f,matrix),toward,center,span,size,False,normals=value['normals'])
                tiles.append((f'{attempt}   {label}   |   {angle}', im))
        finally:
            scene.close()
    with TemporaryDirectory(dir=output.parent) as scratch:
        result_path = Path(scratch)/'comparison.png'
        sheet(tiles,result_path,size,columns=len(views))
        verify(pins,fresh=True)
        result_path.replace(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head',type=Path)
    parser.add_argument('attempt')
    parser.add_argument('out',type=Path)
    args=parser.parse_args()
    print(draw(args.head,args.attempt,args.out))
