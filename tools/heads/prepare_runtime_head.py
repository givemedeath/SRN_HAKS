"""Create a separately versioned runtime candidate within the head triangle cap.

Only geometry reduction is performed. Fitting is a separate recorded similarity
and maps are requested only after standing/motion review.
"""
import argparse
from pathlib import Path
import sys,time
import bpy
import bmesh
sys.path.insert(0,str(Path(__file__).resolve().parent))
from head_workflow import MAX_TRIANGLES,pin,require,sha,write_fresh

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
require(not args.output.exists(),"Fresh runtime candidate directory required")
args.output.mkdir(parents=True); frozen=pin(args.source); begun=time.monotonic()
bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
require(bool(meshes),"No head mesh")
for obj in meshes:
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    # Meshy's GLB splits coincident positions at normal/UV boundaries. Reduce
    # connected surfaces rather than independently collapsing those splits.
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data); bm.free()
    if obj.data.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for polygon in obj.data.polygons: polygon.use_smooth=True
    obj.data.use_auto_smooth=False
    obj.data.update(); obj.data.calc_loop_triangles()
total=sum(len(o.data.loop_triangles) if o.data.loop_triangles else sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
for obj in meshes:
    bpy.context.view_layer.objects.active=obj
    modifier=obj.modifiers.new("runtime_reduction_v2","DECIMATE");modifier.ratio=min(1,7500/total)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.calc_loop_triangles()
count=sum(len(o.data.loop_triangles) for o in meshes)
print({'connectedSourceTriangles':total,'reducedTriangles':count},flush=True)
for attempt in range(3):
    if count<=7500: break
    for obj in meshes:
        bpy.context.view_layer.objects.active=obj
        modifier=obj.modifiers.new('runtime_budget_correction','DECIMATE'); modifier.ratio=7400/count
        bpy.ops.object.modifier_apply(modifier=modifier.name); obj.data.calc_loop_triangles()
    count=sum(len(o.data.loop_triangles) for o in meshes)
    print({'budgetPass':attempt+1,'triangles':count},flush=True)
require(0<count<=MAX_TRIANGLES,"Runtime reduction exceeded total head/accessory budget")
path=args.output/"runtime.glb"
bpy.ops.export_scene.gltf(filepath=str(path.resolve()),export_format="GLB",export_normals=True,
                          export_texcoords=True,export_materials="NONE",export_animations=False)
require(sha(args.source)==frozen["sha256"],"Donor changed during reduction")
write_fresh(args.output/"reduction.json",{"kind":"srn-head-runtime-reduction","source":frozen,"candidate":pin(path),
    "sourceTriangles":total,"triangles":count,"algorithm":"Coincident-position weld (1e-6 source units), preserve corner UVs, recompute normals, Blender collapse decimation to 7500",
    "seconds":time.monotonic()-begun,"bodyResourcesChanged":False,"fittingAccepted":False,"materialsAccepted":False})
