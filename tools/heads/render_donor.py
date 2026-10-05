"""Four-thread Blender clay turntable of immutable donor geometry."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_workflow import pin, require, sha, write_fresh

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
require(not args.output.exists(), "Fresh render directory required")
args.output.mkdir(parents=True)
frozen=pin(args.source); started=time.monotonic()
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(args.source.resolve()))
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
require(bool(meshes), "Donor contains no mesh")
corners=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
minimum=Vector([min(c[i] for c in corners) for i in range(3)])
maximum=Vector([max(c[i] for c in corners) for i in range(3)])
center=(minimum+maximum)/2; size=max(maximum-minimum)
material=bpy.data.materials.new("inspection_clay"); material.diffuse_color=(.45,.48,.52,1)
material.use_nodes=True
shader=material.node_tree.nodes.get("Principled BSDF")
shader.inputs["Base Color"].default_value=(.28,.30,.34,1)
shader.inputs["Roughness"].default_value=.8
for obj in meshes:
    obj.data.materials.clear(); obj.data.materials.append(material)
scene=bpy.context.scene; scene.render.engine="BLENDER_EEVEE"
scene.render.threads_mode="FIXED"; scene.render.threads=4
scene.eevee.taa_render_samples=48; scene.eevee.use_gtao=True
scene.render.resolution_x=512; scene.render.resolution_y=512; scene.render.resolution_percentage=100
scene.render.image_settings.file_format="PNG"
scene.world.color=(.12,.12,.12)
scene.view_settings.view_transform="Standard"
for location, energy in [((2,-3,4),120),((-3,-1,2),60),((0,3,3),100)]:
    light=bpy.data.lights.new("studio", "AREA"); light.energy=energy*size*size; light.size=size*2
    obj=bpy.data.objects.new("studio",light); scene.collection.objects.link(obj)
    obj.location=center+Vector(location)*size
    obj.rotation_euler=(center-obj.location).to_track_quat("-Z","Y").to_euler()
camera=bpy.data.cameras.new("inspection_camera"); camera.type="ORTHO"; camera.ortho_scale=size*1.3
obj=bpy.data.objects.new("inspection_camera",camera); scene.collection.objects.link(obj); scene.camera=obj
frames=[]
for number in range(12):
    angle=number*2*math.pi/12
    obj.location=center+Vector((math.sin(angle)*size*3, -math.cos(angle)*size*3, 0))
    obj.rotation_euler=(center-obj.location).to_track_quat("-Z","Y").to_euler()
    scene.render.filepath=str((args.output/f"frame-{number:02d}.png").resolve())
    begun=time.monotonic(); bpy.ops.render.render(write_still=True)
    frames.append({"frame":number,"angleDegrees":number*30,"seconds":time.monotonic()-begun,
                   "image":pin(scene.render.filepath)})
require(sha(args.source)==frozen["sha256"], "Donor changed during render")
write_fresh(args.output/"render.json", {"kind":"srn-head-donor-turntable", "source":frozen,
    "threads":4, "elapsedSeconds":time.monotonic()-started, "frames":frames,
    "bodyAssembly":False,"clientValidation":False,"productionAcceptance":False})
