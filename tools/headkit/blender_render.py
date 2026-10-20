"""Four-thread CPU inspection renderer; images never establish automatic approval."""
import argparse,json,math,sys,time,hashlib
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True,type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(args.config.read_text())
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from tools.headkit.gltf import mesh
    from tools.headkit.common import verify,pin,write,require
    verify(cfg['inputs']);value=mesh(cfg['mesh']);out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    # glTF Y-up -> Blender Z-up, the same basis used by the runtime exporter.
    transform=np.array([[1,0,0],[0,0,-1],[0,1,0]])
    vertices=value['positions']@transform.T;faces=value['faces'];data=bpy.data.meshes.new('verified-head')
    data.from_pydata(vertices.tolist(),[],faces.tolist());data.update();obj=bpy.data.objects.new('head',data);bpy.context.collection.objects.link(obj)
    for polygon in data.polygons:polygon.use_smooth=True
    if value['normals'] is not None:data.normals_split_custom_set_from_vertices((value['normals']@transform.T).tolist())
    data.use_auto_smooth=True;uv=data.uv_layers.new();corners=value['uv'].copy();corners[...,1]=1-corners[...,1];uv.data.foreach_set('uv',corners.reshape(-1))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=False
    scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=scene.render.resolution_y=cfg.get('size',768)
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.14,.14,.14)
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    center=(vertices.min(0)+vertices.max(0))/2;extent=float(np.linalg.norm(np.ptp(vertices,axis=0)))
    camera_data=bpy.data.cameras.new('camera');camera=bpy.data.objects.new('camera',camera_data);scene.collection.objects.link(camera);scene.camera=camera;camera_data.type='ORTHO'
    for name,offset,power in [('key',(-2,-3,3),70),('fill',(3,-1,1),35),('rim',(0,3,2),45)]:
        light_data=bpy.data.lights.new(name,'AREA');light_data.energy=power*extent**2;light_data.size=extent*3
        light=bpy.data.objects.new(name,light_data);scene.collection.objects.link(light);light.location=center+np.array(offset)*extent
        light.rotation_euler=(Vector(center)-light.location).to_track_quat('-Z','Y').to_euler()
    def material(mode):
        mat=bpy.data.materials.new(mode);mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;nodes.clear();output=nodes.new('ShaderNodeOutputMaterial')
        shader=nodes.new('ShaderNodeEmission' if mode=='color-only' else 'ShaderNodeBsdfPrincipled')
        if mode=='clay':shader.inputs['Base Color'].default_value=(.48,.48,.48,1);shader.inputs['Roughness'].default_value=.8
        else:
            for key,socket in [('basecolor','Color' if mode=='color-only' else 'Base Color')]+([] if mode=='color-only' else [('roughness','Roughness'),('metallic','Metallic'),('opacity','Alpha')]):
                texture=nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(cfg['maps'][key]);texture.image.colorspace_settings.name='sRGB' if key=='basecolor' else 'Non-Color'
                links.new(texture.outputs['Color'],shader.inputs[socket])
        links.new(shader.outputs[0],output.inputs['Surface']);return mat
    records=[]
    for mode in cfg.get('modes',['clay','color-only','material-lit']):
        require(mode in ('clay','color-only','material-lit'),'Unknown render material');data.materials.clear();data.materials.append(material(mode));(out/mode).mkdir()
        for view in cfg['cameras']:
            require('/' not in view['name'] and '\\' not in view['name'] and view['name'] not in ('.','..'),'Safe view name required')
            eye=np.array(view['eye'])@transform.T;target=np.array(view['target'])@transform.T;camera.location=eye
            camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler();camera_data.ortho_scale=view['orthoScale']
            scene.render.filepath=str(out/mode/(view['name']+'.png'));begun=time.monotonic();bpy.ops.render.render(write_still=True)
            records.append({'mode':mode,'view':view['name'],'seconds':time.monotonic()-begun,'image':pin(scene.render.filepath)})
    verify(cfg['inputs']);write(out/'renders.json',{'threads':4,'gpuUsed':False,'elapsedSeconds':time.monotonic()-start,
        'views':records,'triangles':len(faces),'aoAdded':False,'visualApprovalRequired':True},fresh=True)


if __name__=='__main__':main()
