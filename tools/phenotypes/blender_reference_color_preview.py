"""CPU emission-only previews of immutable original and derived RGB sidecars."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def checked(row):p=Path(row['path']);require(sha(p)==row['sha256'],'Pinned preview input changed');return p

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
 job=json.loads(args.input.read_text());require(job['kind']=='reference-color-diagnostic-preview' and job['diagnosticOnly'] is True,'Diagnostic input required');out=args.output.resolve();require(not out.exists(),'Fresh preview directory required');out.mkdir()
 arrays=np.load(checked(job['arrays']),allow_pickle=False);p=arrays['positions'].astype('f4').reshape(-1,3);n=arrays['normals'].astype('f4').reshape(-1,3);uv=arrays['uv'].astype('f4').reshape(-1,2);hostuv=uv.copy();hostuv[:,1]=1-hostuv[:,1]
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);mesh=bpy.data.meshes.new('temporary_source_corner_mesh');mesh.from_pydata(p.tolist(),[],np.arange(len(p)).reshape(-1,3).tolist());mesh.update();mesh.normals_split_custom_set_from_vertices(n.tolist())
 layer=mesh.uv_layers.new(name='DisposableGLTFHostUV');layer.data.foreach_set('uv',hostuv.ravel());obj=bpy.data.objects.new('unaccepted_source_chest',mesh);bpy.context.collection.objects.link(obj)
 actual=np.empty(p.size,dtype='f4');mesh.vertices.foreach_get('co',actual);require(np.array_equal(actual.reshape(p.shape),p),'Position transport changed');actual=np.empty(uv.size,dtype='f4');layer.data.foreach_get('uv',actual);require(np.array_equal(actual.reshape(uv.shape),hostuv),'UV transport changed')
 mat=bpy.data.materials.new('literal_color_emission');mat.use_nodes=True;mat.node_tree.nodes.clear();tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.interpolation='Linear';tex.extension='REPEAT';emit=mat.node_tree.nodes.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=1;output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(tex.outputs['Color'],emit.inputs['Color']);mat.node_tree.links.new(emit.outputs[0],output.inputs['Surface']);mesh.materials.append(mat)
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.use_denoising=False;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=scene.render.resolution_y=1024;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.film_transparent=True;scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=0;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
 bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=job['span'];center=Vector((0,0,0));directions={'front':(0,-1,0),'left':(1,0,0),'back':(0,1,0),'right':(-1,0,0),'front-left':(1,-1,0),'front-right':(-1,-1,0),'back-left':(1,1,0),'back-right':(-1,1,0)};rows=[]
 for name,imagepin in job['images'].items():
  image=bpy.data.images.load(str(checked(imagepin)),check_existing=False);image.colorspace_settings.name='sRGB';tex.image=image
  for view,direction in directions.items():
   outward=Vector(direction).normalized();cam.location=center+outward*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();path=out/(name+'-'+view+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);rows.append({'atlas':name,'view':view,'outward':list(outward),'orthoSpan':job['span'],'cameraMatrixWorld':[list(x) for x in cam.matrix_world],'image':{'path':str(path),'sha256':sha(path)},'emissionOnly':True,'anatomyOrGarmentApproved':False,'clientEvidence':False})
 for p,h in job['frozenInputs'].items():require(sha(p)==h,'Frozen preview source changed')
 result={'kind':'reference-color-diagnostic-preview-receipt','input':{'path':str(args.input.resolve()),'sha256':sha(args.input)},'cpuOnly':True,'resolution':[1024,1024],'samples':8,'sourceFrame':'generator Zup center0','disposableUVConversion':'V=1-rawGLTFV exactlyonce','sourceMapOrMeshChanged':False,'sourceAttributesTransportedToHost':True,'previews':rows,'selected':False,'nativeCompiled':False,'clientAccepted':False};(out/'preview.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'receipt':str(out/'preview.json'),'sha256':sha(out/'preview.json')}),flush=True)
if __name__=='__main__':main()
