"""Render immutable body/head clay assemblies in measured offline poses."""
import argparse
import math
from pathlib import Path
import sys
import time
import bpy
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'phenotypes'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from head_export import triangles
from head_workflow import pin, read, require, verify_pins, write_fresh


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--assembly',type=Path,required=True)
parser.add_argument('--head',type=int,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--standing-only',action='store_true')
a=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
require(not a.output.exists(),'Fresh render output required'); a.output.mkdir(parents=True)
assembly=read(a.assembly); fit=read(assembly['heads'][a.head]['fit']['path'])
sources=[pin(a.assembly),assembly['heads'][a.head]['fit'],fit['source'],fit['target'],*[p.get('ascii',p.get('geometry')) for p in assembly['parts']]]
verify_pins(sources); begun=time.monotonic()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
def clay(name,color):
    mat=bpy.data.materials.new(name); mat.use_nodes=True
    shader=mat.node_tree.nodes.get('Principled BSDF'); shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=.8; return mat
bodymat=clay('preserved_body',(.24,.28,.31)); headmat=clay('candidate_head',(.42,.32,.25))
objects=[]
def mesh(name,points,normals,joint,material):
    data=bpy.data.meshes.new(name); data.from_pydata(points.reshape(-1,3).tolist(),[],np.arange(points.size//3).reshape(-1,3).tolist())
    obj=bpy.data.objects.new(name,data); bpy.context.collection.objects.link(obj); data.materials.append(material)
    for poly in data.polygons: poly.use_smooth=True
    data.use_auto_smooth=True
    data.normals_split_custom_set_from_vertices(normals.reshape(-1,3).tolist())
    objects.append((obj,joint))
for part in assembly['parts']:
    with np.load(part['geometry']['path']) as source:
        rows=[{'name':part['name'],'position':source['position'],'normal':source['normal'],'uv':source['uv']}]
    for row in rows:
        name=part['name']+row['name'];material=bodymat
        if part.get('colorMap'):
            verify_pins([part['colorMap']]);sources.append(part['colorMap']);material=clay(name,(.24,.28,.31))
            texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(part['colorMap']['path'],check_existing=False)
            material.node_tree.links.new(texture.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        mesh(name,row['position'],row['normal'],part['joint'],material)
        if part.get('colorMap'):
            layer=bpy.data.objects[name].data.uv_layers.new(name='body_uv')
            for loop,value in zip(layer.data,row['uv'].reshape(-1,2)):loop.uv=value.tolist()
p,n,uv=triangles(fit['source']['path'],fit['localMatrix']); mesh('candidate_head',p,n,'head_g',headmat)
head=bpy.data.objects['candidate_head']
layer=head.data.uv_layers.new(name='selected_uv')
for loop,texture in zip(layer.data,uv.reshape(-1,2)): loop.uv=texture.tolist()
normal_map=assembly['heads'][a.head].get('normalMap')
if normal_map:
    verify_pins([normal_map]); sources.append(normal_map)
    texture=headmat.node_tree.nodes.new('ShaderNodeTexImage'); texture.image=bpy.data.images.load(normal_map['path'],check_existing=False)
    texture.image.colorspace_settings.name='Non-Color'
    normal=headmat.node_tree.nodes.new('ShaderNodeNormalMap'); normal.inputs['Strength'].default_value=1
    headmat.node_tree.links.new(texture.outputs['Color'],normal.inputs['Color'])
    headmat.node_tree.links.new(normal.outputs['Normal'],headmat.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
for key,socket,colorspace in [('colorMap','Base Color','sRGB'),('roughnessMap','Roughness','Non-Color')]:
    reference=assembly['heads'][a.head].get(key)
    if reference:
        verify_pins([reference]);sources.append(reference)
        texture=headmat.node_tree.nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(reference['path'],check_existing=False)
        texture.image.colorspace_settings.name=colorspace
        headmat.node_tree.links.new(texture.outputs['Color'],headmat.node_tree.nodes.get('Principled BSDF').inputs[socket])
scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE'; scene.render.threads_mode='FIXED'; scene.render.threads=4
scene.eevee.taa_render_samples=48; scene.eevee.use_gtao=True
scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100
scene.view_settings.view_transform='Standard'; scene.world.color=(.10,.10,.10)
for location,energy in [((2,3,4),300),((-3,1,2),180),((0,-3,3),250)]:
    light=bpy.data.lights.new('studio','AREA'); light.energy=energy; light.size=3
    obj=bpy.data.objects.new('studio',light); scene.collection.objects.link(obj); obj.location=location
    obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
camera=bpy.data.cameras.new('review'); camera.type='ORTHO'; obj=bpy.data.objects.new('review',camera)
scene.collection.objects.link(obj); scene.camera=obj
selected=[0,assembly['worstSample']]
for label in sorted({row['label'] for row in assembly['samples']} - {'standing'}):
    selected.append(max((i for i,row in enumerate(assembly['samples']) if row['label']==label),key=lambda i:assembly['samples'][i]['neckDisplacement']))
selected=list(dict.fromkeys(selected)); renders=[]
if a.standing_only:selected=[0]
for index in selected:
    sample=assembly['samples'][index]
    for item,joint in objects: item.matrix_world=Matrix(sample['frames'][joint])
    headframe=np.asarray(sample['frames']['head_g']); center=Vector(headframe[:3,3]); center.z-=.08
    for angle in ([0,90,180] if index in (0,assembly['worstSample']) else [35]):
        camera.ortho_scale=.65
        obj.location=center+Vector((math.sin(math.radians(angle))*2,math.cos(math.radians(angle))*2,.02))
        obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
        path=a.output/f'{index:02d}-{sample["label"]}-{angle}.png'; scene.render.filepath=str(path.resolve())
        started=time.monotonic(); bpy.ops.render.render(write_still=True)
        renders.append({'sample':index,'label':sample['label'],'angle':angle,'seconds':time.monotonic()-started,'image':pin(path)})
    if index==0:
        center=Vector((0,0,1)); camera.ortho_scale=2.2; obj.location=(.8,3,1.2)
        obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
        path=a.output/'standing-full.png'; scene.render.filepath=str(path.resolve()); bpy.ops.render.render(write_still=True)
        renders.append({'sample':0,'label':'standing-full','image':pin(path)})
verify_pins(sources)
write_fresh(a.output/'render.json',{'kind':'srn-head-assembly-render','inputs':sources,'threads':4,
    'elapsedSeconds':time.monotonic()-begun,'frames':renders,'clientEvidence':False,'accepted':False})
