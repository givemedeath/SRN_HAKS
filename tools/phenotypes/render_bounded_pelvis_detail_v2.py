"""A separately labeled literal right-port diagnostic closeup with camera fill."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import bpy
from mathutils import Vector
from place_purposebuilt_pelvis import read_glb
from write_bounded_pelvis_diagnostic import decoded_primitives
from render_bounded_pelvis_diagnostic import setup, world, orient, curve, legend, sha, stamp


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--diagnostic',type=Path,required=True)
    parser.add_argument('--previous-literal',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output=args.output.resolve();args.diagnostic=args.diagnostic.resolve();args.previous_literal=args.previous_literal.resolve();d=json.loads(args.diagnostic.read_text())
    if args.output.exists():raise ValueError('Fresh output required')
    fit=json.loads(Path(d['properFit']['path']).read_text());path=Path(d['exports']['working']['candidate']['path'])
    if sha(path)!=d['exports']['working']['candidate']['sha256']:raise ValueError('Diagnostic changed')
    rows=decoded_primitives(*read_glb(path));mapping=np.load(d['faceMapping']['path'])
    original=decoded_primitives(*read_glb(fit['candidate']))
    previous=json.loads(args.previous_literal.read_text())
    pv=next(r for r in previous['captures'] if r['view']=='after-right-port-detail')
    scene,camera,proofs,points=setup(rows,fit,mapping['keptOriginalFaceIds'],'after',set())
    focus=np.asarray(pv['cameraFocus']);direction=np.asarray(pv['cameraDirectionTowardCamera'])
    camera.location=Vector(focus+direction*1.35);camera.data.ortho_scale=pv['cameraOrthoScale'];orient(camera,focus)
    for side in ('left','right'):
        ring=world(original[0]['attributes']['POSITION'][mapping[side+'CapOriginalPortRows']],fit['attachmentWorld'])
        curve('exact-fixed-port-'+side,ring,(.05,.8,1.),.00022)
    # Physical camera fill is separately recorded; previous matched captures unchanged.
    light=bpy.data.lights.new('declared-camera-fill','AREA');light.energy=1.;light.shape='DISK';light.size=.08
    obj=bpy.data.objects.new('declared-camera-fill',light);bpy.context.collection.objects.link(obj)
    obj.location=Vector(focus+direction*.16);orient(obj,focus)
    caption='RELIT right-port detail | Literal bounded working diagnostic\nCamera matches earlier detail; added 1 W / 80 mm camera fill.\nCyan: exact original port. Narrow cap strips and folds unchanged.\nNeutral cap, Cycles CPU clay; no material/anatomy/client acceptance.'
    legend(camera,scene,caption);bpy.context.view_layer.update();args.output.mkdir(parents=True)
    image=args.output/'after-right-port-detail-camera-fill.png';scene.render.filepath=str(image)
    bpy.ops.render.render(write_still=True);blend=args.output/'after-right-port-detail-camera-fill.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend));snap=args.output/'helper-snapshots';snap.mkdir()
    for name in ('render_bounded_pelvis_detail_v2.py','render_bounded_pelvis_diagnostic.py','write_bounded_pelvis_diagnostic.py'):
        shutil.copyfile(Path(__file__).with_name(name),snap/name)
    r={'kind':'literal-bounded-pelvis-detail-with-declared-camera-fill','diagnostic':stamp(args.diagnostic),'previousLiteral':stamp(args.previous_literal),
       'candidate':stamp(path),'image':stamp(image),'blend':stamp(blend),'geometryProofs':proofs,'renderEngine':'Cycles CPU','samples':16,'threads':4,
       'cameraMatrixWorld':[list(row) for row in camera.matrix_world],'cameraOrthoScale':camera.data.ortho_scale,
       'additionalCameraFill':{'matrixWorld':[list(row) for row in obj.matrix_world],'energyWatts':light.energy,'diameter':light.size},
       'sourceAndDiagnosticChanged':False,'selectionMade':False,'materialAccepted':False,'anatomyAccepted':False,'clientAccepted':False}
    receipt=args.output/'literal-detail.json';receipt.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'receipt':stamp(receipt),'image':stamp(image)}),flush=True)


if __name__=='__main__':main()
