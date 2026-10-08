"""Literal offline stock robe001 garment preview with diagnostic authored Cloth1 PLT."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix,Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from retarget import NODE,nodes,transforms
from audit_geometry import arrays
from shared_toolchain import sha as digest

def save_json(path,value):
    path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
from pose_preview_render_settings import apply_render_settings
from shared_toolchain import load


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--authored',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--surface-mode',choices=('lit','unlit'),default='lit')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);authored=args.authored.resolve();d=json.loads(authored.read_text());output=args.output.resolve()
    if output.exists():raise ValueError('Fresh offline robe preview required')
    if not bpy.app.background or not os.environ.get('SRN_SHARED_TOOL_MIGRATION'):raise ValueError('Canonical passed shared Blender background launcher required')
    config=Path(os.environ['SRN_SHARED_TOOLCHAIN']);migration=Path(os.environ['SRN_SHARED_TOOL_MIGRATION']);load(config,migration)
    if digest(config)!=d['sharedToolchain']['sha256'] or digest(migration)!=d['toolMigration']['sha256']:raise ValueError('Shared render toolchain provenance differs')
    for path,pin in d['frozenInputs'].items():
        if digest(Path(path))!=pin:raise ValueError('Source input changed: '+path)
    source=Path(d['sourceAscii']['path']);text=source.read_text(encoding='ascii')
    if d.get('kind')!='target-authored-robe-cloth-diagnostic' or d.get('separationProved') is not True:raise ValueError('Explicit authored cloth separation receipt required')
    visible=d['visibleCloth'];hidden=d['hiddenBindMeshes'];matches=list(NODE.finditer(text.split('endmodelgeom',1)[0]));block=next(b for b in matches if b[2]=='Robe')
    if len(hidden)!=13 or any(r['render']!='0' or r['bitmap']!='NULL' for r in hidden):raise ValueError('Hidden binding ownership is not explicit')
    for row in [visible,*hidden]:
        match=next(b for b in matches if b[2]==row['node'])
        if hashlib.sha256(match[0].encode('ascii')).hexdigest()!=row['sourceBlockSha256']:raise ValueError('Declared source mesh changed')
    frame=np.asarray(d['visibleCloth']['modelLocalFrame'],float)
    if not np.allclose(frame,transforms(nodes(text))['robe'],atol=1e-12,rtol=0):raise ValueError('Original stock garment frame differs')
    if visible['node']!='Robe' or visible['bitmap']!='pmh0_robe001':raise ValueError('Visible source ownership changed')
    texture=Path(d['offlinePalettePreview']['path']);palette=Path(d['authoredPalette']['path'])
    if digest(texture)!=d['offlinePalettePreview']['sha256'] or digest(palette)!=d['authoredPalette']['sha256']:raise ValueError('Authored material changed')
    vertices=np.asarray(arrays(block[3],'verts'));faces=np.asarray(arrays(block[3],'faces'));uvs=np.asarray(arrays(block[3],'tverts'))
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mesh=bpy.data.meshes.new('exact_stock_Robe');mesh.from_pydata(vertices.tolist(),[],faces[:,:3].astype(int).tolist());mesh.update()
    if len(mesh.vertices)!=len(vertices) or len(mesh.polygons)!=len(faces):raise ValueError('Blender source topology inventory changed')
    obj=bpy.data.objects.new('original_stock_Robe_only',mesh);bpy.context.collection.objects.link(obj);obj.matrix_world=Matrix(frame)
    layer=mesh.uv_layers.new(name='original_stock_face_UVs')
    for polygon,face in zip(mesh.polygons,faces):
        polygon.use_smooth=bool(face[3])
        if tuple(polygon.vertices)!=tuple(face[:3].astype(int)):raise ValueError('Blender ordered triangle changed')
        for loop,index in zip(polygon.loop_indices,face[4:7].astype(int)):layer.data[loop].uv=uvs[index,:2]
    uv_error=max(float(np.max(abs(np.asarray(layer.data[loop].uv)-uvs[index,:2]))) for poly,face in zip(mesh.polygons,faces) for loop,index in zip(poly.loop_indices,face[4:7].astype(int)))
    expected=vertices@frame[:3,:3].T+frame[:3,3];observed=np.array([tuple(obj.matrix_world@v.co) for v in mesh.vertices]);point_error=float(np.max(abs(expected-observed)))
    if point_error>1e-6 or uv_error>1e-6:raise ValueError('Literal source geometry/UV transfer error too large')
    material=bpy.data.materials.new('NEW_authored_Cloth1_offline_row0');material.use_nodes=True;shader=material.node_tree.nodes['Principled BSDF']
    shader.inputs['Roughness'].default_value=1.;shader.inputs['Metallic'].default_value=0.;shader.inputs['Alpha'].default_value=1.
    image=material.node_tree.nodes.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(texture),check_existing=False);image.image.colorspace_settings.name='sRGB';image.interpolation='Closest'
    material.node_tree.links.new(image.outputs['Color'],shader.inputs['Base Color'])
    if args.surface_mode=='unlit':
        emission=material.node_tree.nodes.new('ShaderNodeEmission');emission.inputs['Strength'].default_value=1
        material.node_tree.links.new(image.outputs['Color'],emission.inputs['Color']);material.node_tree.links.new(emission.outputs['Emission'],material.node_tree.nodes['Material Output'].inputs['Surface'])
    obj.data.materials.append(material)
    scene=bpy.context.scene;settings=apply_render_settings(scene,'cycles-cpu');scene.render.resolution_x=scene.render.resolution_y=512;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=False;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.035,.035,.035,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.4
    low=observed.min(0);high=observed.max(0);center=Vector((low+high)/2);span=float(np.max(high-low));scale=span*1.25
    for name,delta,energy,size in (('key',(2,3,3),280,3),('fill',(-3,1,1),160,3),('rim',(1,-3,2),200,2)):
        light=bpy.data.lights.new(name,'AREA');light.energy=energy;light.shape='DISK';light.size=size;lo=bpy.data.objects.new(name,light);bpy.context.collection.objects.link(lo);lo.location=center+Vector(delta);lo.rotation_euler=(center-lo.location).to_track_quat('-Z','Y').to_euler()
    camdata=bpy.data.cameras.new('literal_source_orthographic');camera=bpy.data.objects.new('literal_source_orthographic',camdata);bpy.context.collection.objects.link(camera);camdata.type='ORTHO';camdata.ortho_scale=scale;scene.camera=camera
    output.mkdir(parents=True);shutil.copyfile(Path(__file__),output/'executed-preview_authored_robe_cloth.py');shutil.copyfile(Path(__file__).with_name('pose_preview_render_settings.py'),output/'executed-pose_preview_render_settings.py')
    directions={'front':(0,1,0),'rear':(0,-1,0),'right':(1,0,0)};renders=[]
    for name,direction in directions.items():
        camera.location=center+Vector(direction)*8;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(output/(name+'.png'));begun=time.monotonic()
        bpy.ops.render.render(write_still=True);p=output/(name+'.png');renders.append({'name':name,'direction':direction,'path':str(p),'sha256':digest(p),'elapsedSeconds':time.monotonic()-begun})
    if scene.cycles.device!='CPU':raise ValueError('GPU render is not permitted')
    for path,pin in d['frozenInputs'].items():
        if digest(Path(path))!=pin:raise ValueError('Frozen input changed during preview')
    save_json(output/'preview.json',{'schemaVersion':1,'kind':'offline-authored-robe-cloth-preview','authoredReceipt':{'path':str(authored),'sha256':digest(authored)},
        'sourceAscii':d['sourceAscii'],'visibleSourceNode':visible,'hiddenBindMeshCount':len(hidden),'hiddenBindMeshesRendered':False,
        'sourceGeometrySpace':'Original stock model-local bind; no target fitting or stature conversion','sourceVertices':len(vertices),'sourceFaces':len(faces),'sourceTextureVertices':len(uvs),
        'maximumFloatTransferWorldPointError':point_error,'maximumFloatTransferUvError':uv_error,'orderedTrianglesPreserved':True,
        'cameraOrthoScale':scale,'views':renders,'renderSettings':settings,'offlineNormalPolicy':'Blender-derived normals; smooth iff source face smoothing group is nonzero; native renderer parity unaccepted',
        'offlineOpacity':1,'offlineSurfaceMode':args.surface_mode,'nativeLightingParityAccepted':False,'texturePreview':d['offlinePalettePreview'],'geometryExported':False,'runtimeSelectionChanged':False,'materialDonorAdopted':False,
        'clientEvidence':False,'productionAccepted':False,'clientAccepted':False,'materialBindingsAccepted':False,'originalResourcesModified':False})
    print(json.dumps({'preview':str(output/'preview.json'),'cpuOnly':True,'clientEvidence':False}),flush=True)


if __name__=='__main__':main()
