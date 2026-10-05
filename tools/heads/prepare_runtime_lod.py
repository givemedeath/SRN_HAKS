"""Build a bounded skull-and-jaw LOD and bake its preserved master's normals."""
import argparse,math,sys,time
from pathlib import Path
import bpy,bmesh
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from head_workflow import MAX_TRIANGLES,pin,require,verify_pins,write_fresh
from head_export import triangles

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--voxel-size',type=float,default=.012,help='Explicit source-unit surface revision before bounded collapse')
p.add_argument('--triangles',type=int,default=19000);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
require(not a.output.exists(),'Fresh bounded LOD revision required');require(1000<=a.triangles<=MAX_TRIANGLES-500,'Leave room for cap triangles')
require(.005<=a.voxel_size<=.02,'Explicit conservative source-scale voxel size required')
frozen=pin(a.source);started=time.monotonic()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(a.source.resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];require(meshes,'No donor mesh')
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();high=bpy.context.object;high.name='preserved_master'
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
high.data.calc_loop_triangles();source_count=len(high.data.loop_triangles)
low=high.copy();low.data=high.data.copy();bpy.context.collection.objects.link(low);low.name='runtime_lod'
bpy.ops.object.select_all(action='DESELECT');low.select_set(True);bpy.context.view_layer.objects.active=low
bm=bmesh.new();bm.from_mesh(low.data)
matches=bmesh.ops.find_doubles(bm,verts=list(bm.verts),dist=1e-7)['targetmap']
exact={vertex:target for vertex,target in matches.items() if tuple(vertex.co)==tuple(target.co)}
bmesh.ops.weld_verts(bm,targetmap=exact)
print({'exactCoincidentVerticesMerged':len(exact)},flush=True)
bm.to_mesh(low.data);bm.free()
modifier=low.modifiers.new('bounded_surface_revision','REMESH');modifier.mode='VOXEL'
modifier.voxel_size=a.voxel_size;modifier.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=modifier.name)
low.data.calc_loop_triangles();surface_count=len(low.data.loop_triangles)
modifier=low.modifiers.new('bounded_runtime_lod','DECIMATE');modifier.ratio=min(1,a.triangles/source_count)
modifier.ratio=min(1,a.triangles/surface_count)
modifier.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=modifier.name)
low.data.calc_loop_triangles();count=len(low.data.loop_triangles)
print({'sourceTriangles':source_count,'firstLodTriangles':count},flush=True)
for attempt in range(2):
 if count<=a.triangles:break
 modifier=low.modifiers.new('measured_budget_correction','DECIMATE');modifier.ratio=(a.triangles-20)/count
 modifier.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=modifier.name)
 low.data.calc_loop_triangles();count=len(low.data.loop_triangles)
 print({'budgetCorrection':attempt+1,'triangles':count},flush=True)
require(0<count<=a.triangles,'LOD budget exceeded')
# Strip imported/custom corner arrays after topology changes. Rebuilding the
# same positions and face indices prevents stale glTF custom normals/UV arrays
# from surviving a voxel/modifier revision into the exporter or normal bake.
geometry=bpy.data.meshes.new('selected_lod_surface')
geometry.from_pydata([tuple(v.co) for v in low.data.vertices],[],[tuple(f.vertices) for f in low.data.polygons])
geometry.validate(verbose=True,clean_customdata=True);geometry.update();low.data=geometry
bm=bmesh.new();bm.from_mesh(low.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(low.data);bm.free()
low.data.update()
low.data.validate(verbose=True,clean_customdata=True);low.data.calc_loop_triangles()
count=len(low.data.loop_triangles)
for polygon in low.data.polygons:polygon.use_smooth=True
low.data.use_auto_smooth=False
if low.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.02);bpy.ops.object.mode_set(mode='OBJECT')
low.data.update();low.data.calc_loop_triangles();bpy.context.view_layer.update()
count=len(low.data.loop_triangles);require(0<count<=a.triangles,'Validated LOD budget exceeded')
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=4
scene.render.bake.use_selected_to_active=True;scene.render.bake.use_clear=False
scene.render.bake.cage_extrusion=.05;scene.render.bake.max_ray_distance=.10;scene.render.bake.margin=12
image=bpy.data.images.new('selected_lod_normal',width=2048,height=2048,alpha=False)
image.generated_color=(.5,.5,1,1);image.colorspace_settings.name='Non-Color'
material=bpy.data.materials.new('normal_bake_destination');material.use_nodes=True
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;material.node_tree.nodes.active=node
low.data.materials.clear();low.data.materials.append(material)
bpy.ops.object.select_all(action='DESELECT');low.select_set(True);high.select_set(True);bpy.context.view_layer.objects.active=low
bake_started=time.monotonic();bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z')
bake_seconds=time.monotonic()-bake_started
a.output.mkdir(parents=True);image.filepath_raw=str((a.output/'selected-normal.png').resolve());image.file_format='PNG';image.save()
high.hide_render=True;bpy.ops.object.select_all(action='DESELECT');low.select_set(True);bpy.context.view_layer.objects.active=low
target=a.output/'runtime.glb'
bpy.ops.export_scene.gltf(filepath=str(target.resolve()),export_format='GLB',use_selection=True,
 export_normals=True,export_texcoords=True,export_materials='NONE',export_animations=False)
returned=triangles(target,np.eye(4));require(len(returned[0])==count,'GLB export differs from the selected LOD')
verify_pins([frozen])
write_fresh(a.output/'lod.json',{'kind':'srn-head-bounded-runtime-lod','source':frozen,'output':pin(target),
 'normal':pin(a.output/'selected-normal.png'),'sourceTriangles':source_count,'triangles':count,
 'targetTriangles':a.triangles,'surfaceTriangles':surface_count,'voxelSizeSourceUnits':a.voxel_size,
 'method':'Exact coincident-position connectivity weld, explicit voxel surface revision, Blender collapse LOD, consistent smooth normals, new smart-project UV atlas; master-to-selected-LOD tangent normal bake',
 'neckTrimApplied':False,'neckTaperApplied':False,'voxelRemeshApplied':True,
 'normalBake':{'size':2048,'cageExtrusionSourceUnits':.05,'maximumRayDistanceSourceUnits':.10,'seconds':bake_seconds},
 'threads':4,'elapsedSeconds':time.monotonic()-started,'anatomyApproved':False,'fittingAccepted':False,'productionAccepted':False})
