"""Fit sheet with the actual torso and neck, in the head attachment frame."""
from contextlib import ExitStack
from pathlib import Path
import re
import tempfile
import numpy as np
from headkit.body_neck import KIND, _nodes, world, mesh_parts
from headkit.common import pin, read, verify, require, write
from headkit.gltf import positions
from headkit.mesh import BASIS, transform
from headkit.native_reader import decode
from headkit.rays import EmbreeScene
from headkit.diagnostics import sheet
try:
    from ._fit_views import attempt_result, tile
except ImportError:
    from _fit_views import attempt_result, tile


def body_surface(torso, skeleton, neck):
    geometry=re.split(r'(?im)^\s*(?:endmodelgeom|newanim)\b',skeleton,maxsplit=1)[0]
    nodes=_nodes(geometry)
    require(neck.get('kind')==KIND,'Expected bound head-local body neck')
    inverse=np.linalg.inv(world(nodes,'head_g'))
    require(np.allclose(inverse@world(nodes,'neck_g'),neck['neckToHead'],atol=1e-8),'Body neck and skeleton attachment frames disagree')
    frame=inverse@world(nodes,'torso_g')
    name=Path(torso).stem
    require(re.fullmatch(r'p[fm][hedog][0-9]_chest[0-9]{3}',name),'Body torso must preserve its native model basename')
    parts=decode(Path(torso).read_bytes(),name,require_tangents=False,apply_rigid_transforms=True)
    vertices=[];faces=[]
    for part in parts:
        start=sum(len(v) for v in vertices)
        vertices.append(transform(frame,part['position']));faces.append(part['faces']+start)
    start=sum(len(v) for v in vertices)
    vertices.append(np.asarray(neck['vertices']));faces.append(np.asarray(neck['faces'])+start)
    return np.concatenate(vertices),np.concatenate(faces),frame


def compare(head, attempt, output):
    head=Path(head).resolve();output=Path(output);evidence=output.with_suffix('.json')
    require(not output.exists() and not evidence.exists(),'Fresh upper-body fit evidence required')
    manifest=pin(head/'manifest.json');data=read(manifest['path'])
    require({'bodyTorso','bodyNeck'}<=set(data['inputs']),'Upper-body fitting needs pinned bodyTorso and bodyNeck inputs')
    torso=dict(data['inputs']['bodyTorso'],path=str(head/data['inputs']['bodyTorso']['path']))
    neck_pin=dict(data['inputs']['bodyNeck'],path=str(head/data['inputs']['bodyNeck']['path']))
    verify([manifest,torso,neck_pin],fresh=True)
    neck=read(neck_pin['path']);skeleton=neck['sources']['skeleton']
    receipt,fit=attempt_result(head,attempt)
    require(Path(torso['path']).stem[:4]==Path(fit['reference']['path']).stem.removeprefix('fit-reference-')[:4],
            'Torso and fit reference prefixes disagree')
    dll=read(head/'bindings.json')['embree']
    pins=[manifest,torso,neck_pin,skeleton,receipt,fit['source'],fit['reference'],dll]
    verify(pins,fresh=True)
    bv,bf,frame=body_surface(torso['path'],Path(skeleton['path']).read_text(encoding='utf-8'),neck)
    rv,rf=mesh_parts(re.split(r'(?im)^\s*(?:endmodelgeom|newanim)\b',Path(fit['reference']['path']).read_text(encoding='utf-8'),maxsplit=1)[0])
    v,f=positions(fit['source']['path'])
    with ExitStack() as stack:
        def model(v,f,m):
            scene=EmbreeScene(dll['path'],v.astype(np.float32),f.astype(np.uint32))
            stack.callback(scene.close);return scene,v,f,m
        body=model(bv,bf,np.eye(4))
        models=[('stock fit reference',model(rv,rf,np.eye(4))),(attempt,model(v,f,np.asarray(fit['matrix'])@BASIS))]
        # Include the shoulders and upper chest, not the internal lower neck cap alone.
        top=max(float(rv[:,2].max()),float(transform(np.asarray(fit['matrix'])@BASIS,v)[:,2].max()))
        bottom=-.35;span=max(.55,top-bottom)*1.12;center=np.array([0.,0.,(top+bottom)/2])
        tiles=[]
        for label,m in models:
            for name,direction in [('front',(0.,1.,0.)),('side',(1.,0.,0.)),('three-quarter',(.7,.714,0.))]:
                toward=np.array(direction);toward/=np.linalg.norm(toward)
                tiles.append((label+' | '+name+' | blue=torso+neck',tile(m,toward,center,span,400,False,neck=body)))
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as folder:
            tmp=Path(folder)/'sheet.png';sheet(tiles,tmp,400,columns=3)
            verify(pins,fresh=True);tmp.replace(output)
    write(evidence,{'kind':'head-upper-body-fit-review-v1','attempt':attempt,'inputs':pins,'torsoToHead':frame.tolist(),
                    'sheet':pin(output),'visualReviewRequired':True,'productionAccepted':False},fresh=True)
    return output


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('head',type=Path);parser.add_argument('attempt');parser.add_argument('output',type=Path)
    args=parser.parse_args();print(compare(args.head,args.attempt,args.output))
