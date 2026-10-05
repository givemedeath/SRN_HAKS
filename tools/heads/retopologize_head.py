"""Version an untextured donor's voxel surface and selected runtime UV atlas."""
import argparse
import math
from pathlib import Path
import sys,time
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from head_workflow import MAX_TRIANGLES,pin,require,sha,write_fresh

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--voxel-size',type=float,required=True)
parser.add_argument('--target-triangles',type=int,default=9700)
a=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
require(not a.output.exists(),'Fresh topology revision required')
require(.005<=a.voxel_size<=.03,'Explicit source-scale voxel size required')
require(0<a.target_triangles<MAX_TRIANGLES,'Leave room below the final triangle cap for neck corrections')
a.output.mkdir(parents=True); frozen=pin(a.source); begun=time.monotonic()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(a.source.resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];require(meshes,'No source mesh')
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:obj.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();obj=bpy.context.object
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
original=sum(len(p.vertices)-2 for p in obj.data.polygons)
modifier=obj.modifiers.new('head_surface_revision','REMESH');modifier.mode='VOXEL';modifier.voxel_size=a.voxel_size
modifier.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=modifier.name)
obj.data.calc_loop_triangles(); surface=len(obj.data.loop_triangles)
modifier=obj.modifiers.new('runtime_reduction','DECIMATE');modifier.ratio=min(1,a.target_triangles/surface)
bpy.ops.object.modifier_apply(modifier=modifier.name);obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
require(0<count<=MAX_TRIANGLES,'Topology revision exceeds head/accessory triangle cap')
for p in obj.data.polygons:p.use_smooth=True
obj.data.use_auto_smooth=False
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02)
bpy.ops.object.mode_set(mode='OBJECT')
path=a.output/'runtime.glb'
bpy.ops.export_scene.gltf(filepath=str(path.resolve()),export_format='GLB',export_normals=True,
    export_texcoords=True,export_materials='NONE',export_animations=False)
require(sha(a.source)==frozen['sha256'],'Source donor changed')
write_fresh(a.output/'topology.json',{'kind':'srn-head-topology-revision','source':frozen,'candidate':pin(path),
    'sourceTriangles':original,'surfaceTriangles':surface,'triangles':count,'voxelSizeSourceUnits':a.voxel_size,
    'targetTriangles':a.target_triangles,'finalTriangleCap':MAX_TRIANGLES,
    'algorithm':'Blender voxel surface union, collapse reduction, smooth normals, explicit new smart-project UV atlas',
    'uvPolicy':'New atlas selected before texturing; source UVs remain preserved in the immutable master',
    'uvAngleDegrees':66,'uvIslandMargin':.02,'seconds':time.monotonic()-begun,
    'bodyResourcesChanged':False,'fittingAccepted':False,'materialsAccepted':False})
