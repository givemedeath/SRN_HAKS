"""Reduce an oversized preserved master for Meshy's upload limit; no neck edits."""
import argparse
from pathlib import Path
import sys,time
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from head_workflow import pin,require,verify_pins,write_fresh

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--triangles',type=int,default=450000)
a=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);frozen=pin(a.source);started=time.monotonic()
require(not a.output.exists(),'Fresh Meshy input revision required')
require(100000<=a.triangles<=500000,'Explicit intermediate master budget required')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(a.source.resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];require(meshes,'No donor geometry')
for o in meshes:o.data.calc_loop_triangles()
count=sum(len(o.data.loop_triangles) for o in meshes)
bounds={o.name:[list(o.matrix_world@__import__('mathutils').Vector(v)) for v in o.bound_box] for o in meshes}
for o in meshes:
 bpy.context.view_layer.objects.active=o
 modifier=o.modifiers.new('upload_budget','DECIMATE');modifier.ratio=min(1,a.triangles/count)
 bpy.ops.object.modifier_apply(modifier=modifier.name);o.data.calc_loop_triangles()
total=sum(len(o.data.loop_triangles) for o in meshes)
require(total<=a.triangles+100,'Intermediate triangle budget exceeded')
a.output.mkdir(parents=True);target=a.output/'upload.glb'
bpy.ops.export_scene.gltf(filepath=str(target.resolve()),export_format='GLB',export_normals=True,
 export_texcoords=True,export_materials='NONE',export_animations=False)
require(target.stat().st_size<=50*1024*1024,'Intermediate still exceeds Meshy upload limit')
verify_pins([frozen])
write_fresh(a.output/'preparation.json',{'kind':'srn-head-meshy-upload-preparation','source':frozen,
 'output':pin(target),'sourceTriangles':count,'triangles':total,'sourceBounds':bounds,
 'method':'Uniform Blender collapse decimation for the service file-size limit; final reduction stays in Meshy',
 'neckTrimApplied':False,'neckTaperApplied':False,'elapsedSeconds':time.monotonic()-started,
 'threads':4,'runtimeSelected':False,'anatomyApproved':False})
