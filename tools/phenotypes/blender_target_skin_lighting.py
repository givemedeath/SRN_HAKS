"""Blender-only CPU worker for pinned diagnostic light bakes and unlit previews.

Pillow and palette/protection math remain in the bundled-Python controller.
No geometry, native material or original texture is exported or changed.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix,Vector


def require(value,message):
    if not value:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def array_sha(value):return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def filepin(path):return {'path':str(path.resolve()),'sha256':sha(path),'byteCount':path.stat().st_size}
def checked(entry):
    path=Path(entry['path']).resolve();require(sha(path)==entry['sha256'],'Pinned worker input changed: '+str(path));return path


def material(name,normal_image):
    mat=bpy.data.materials.new(name);mat.use_nodes=True;tree=mat.node_tree;nodes=tree.nodes;links=tree.links;nodes.clear()
    def attr(name):
        node=nodes.new('ShaderNodeAttribute');node.attribute_name=name;return node
    def vm(operation,*sockets):
        node=nodes.new('ShaderNodeVectorMath');node.operation=operation
        for i,socket in enumerate(sockets):links.new(socket,node.inputs[i])
        return node.outputs['Vector']
    def scaled(vector,amount):
        node=nodes.new('ShaderNodeVectorMath');node.operation='SCALE';links.new(vector,node.inputs[0]);links.new(amount,node.inputs['Scale']);return node.outputs['Vector']
    normal=vm('NORMALIZE',attr('authored_normal').outputs['Vector']);tangent=vm('NORMALIZE',attr('authored_tangent').outputs['Vector'])
    bitangent=scaled(vm('CROSS_PRODUCT',normal,tangent),attr('authored_sign').outputs['Fac'])
    image=nodes.new('ShaderNodeTexImage');image.image=normal_image;image.interpolation='Linear';image.extension='REPEAT'
    split=nodes.new('ShaderNodeSeparateColor');split.mode='RGB';links.new(image.outputs['Color'],split.inputs['Color'])
    def signed(socket):
        node=nodes.new('ShaderNodeMath');node.operation='MULTIPLY_ADD';links.new(socket,node.inputs[0]);node.inputs[1].default_value=2;node.inputs[2].default_value=-1;return node.outputs[0]
    x,y,z=[signed(split.outputs[c]) for c in ('Red','Green','Blue')]
    combined=vm('NORMALIZE',vm('ADD',vm('ADD',scaled(tangent,x),scaled(bitangent,y)),scaled(normal,z)))
    world=nodes.new('ShaderNodeVectorTransform');world.vector_type='VECTOR';world.convert_from='OBJECT';world.convert_to='WORLD';links.new(combined,world.inputs[0])
    diffuse=nodes.new('ShaderNodeBsdfDiffuse');diffuse.inputs['Color'].default_value=(1,1,1,1);diffuse.inputs['Roughness'].default_value=0
    links.new(world.outputs[0],diffuse.inputs['Normal']);out=nodes.new('ShaderNodeOutputMaterial');links.new(diffuse.outputs[0],out.inputs['Surface']);return mat


def build_mesh(job,arrays,normal_images):
    p,n,uv,t=[np.asarray(arrays[k],dtype='f4').reshape(-1,width) for k,width in (('positions',3),('normals',3),('uv',2),('tangents',4))]
    faces=np.arange(len(p)).reshape(-1,3);mesh=bpy.data.meshes.new('temporary_exact_corner_skin');mesh.from_pydata(p.tolist(),[],faces.tolist());mesh.update()
    for polygon in mesh.polygons:polygon.use_smooth=True
    mesh.normals_split_custom_set_from_vertices(n.tolist())
    host_uv=uv.copy();host_uv[:,1]=1-host_uv[:,1] # GLTF top-left to Blender bottom-left once; source bytes remain exact.
    layer=mesh.uv_layers.new(name='DisposableHostUV');layer.data.foreach_set('uv',host_uv.ravel())
    for name,kind,rows in (('authored_normal','FLOAT_VECTOR',n),('authored_tangent','FLOAT_VECTOR',t[:,:3]),('authored_sign','FLOAT',t[:,3])):
        attribute=mesh.attributes.new(name,kind,'POINT');field='vector' if kind=='FLOAT_VECTOR' else 'value';attribute.data.foreach_set(field,rows.ravel())
        actual=np.empty(rows.size,dtype='f4');attribute.data.foreach_get(field,actual);require(np.array_equal(actual.reshape(rows.shape),rows),'Shader attribute changed')
    ap=np.empty(p.size,dtype='f4');mesh.vertices.foreach_get('co',ap);au=np.empty(uv.size,dtype='f4');layer.data.foreach_get('uv',au)
    require(np.array_equal(ap.reshape(p.shape),p) and np.array_equal(au.reshape(uv.shape),host_uv),'Position/host UV corner transport changed')
    obj=bpy.data.objects.new('diagnostic_untreated_fitted_'+job['part'],mesh);bpy.context.collection.objects.link(obj);obj.matrix_world=Matrix(job['attachmentWorld'])
    mids=list(job['materials']);mat_indices={mid:i for i,mid in enumerate(mids)}
    for mid in mids:mesh.materials.append(material('original_basis_'+mid,normal_images[mid]))
    ids=[mat_indices[str(row['material'])] for row in job['primitives'] for _ in range(row['triangles'])];mesh.polygons.foreach_set('material_index',np.asarray(ids,dtype='i4'))
    return obj,{'positions':array_sha(p),'authoredNormals':array_sha(n),'authoredTangentsAndSigns':array_sha(t),'rawGltfUV':array_sha(uv),
        'disposableBlenderUV':array_sha(host_uv),'disposableHostUvPolicy':'V=1-rawGLTFV exactly once; no source accessor is changed.',
        'triangleCornerOrder':array_sha(faces),'arraysExactFloat32':True,'authoredNormalLengthsRetainedInShaderAttributes':True,
        'blenderGeometryNormalsNormalizedForHostGeometry':True,'sourceAttributeBytesUnmodified':True,'mikkTangentsGenerated':False,
        'meshPolicy':'Disposable ordered corner mesh only; no geometry is exported or used to replace source.'}


def emission(mat,image):
    mat.node_tree.nodes.clear();nodes=mat.node_tree.nodes;links=mat.node_tree.links
    tex=nodes.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';tex.extension='REPEAT'
    emit=nodes.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=1;links.new(tex.outputs['Color'],emit.inputs['Color'])
    out=nodes.new('ShaderNodeOutputMaterial');links.new(emit.outputs[0],out.inputs['Surface'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--operation',choices=('bake','preview'),required=True);parser.add_argument('--previews',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);input_path=args.input.resolve();job=json.loads(input_path.read_text(encoding='utf-8'))
    require(job['kind']=='target-skin-lighting-worker-input' and job['diagnosticOnly'] is True,'Pinned diagnostic worker input required')
    settings=job['lighting'];require(settings['device']=='CPU' and settings['resolution']==2048 and settings['frame']=='target-world-bind','CPU 2K bind-space worker required')
    output=args.output.resolve();require(not output.exists(),'Fresh worker output required');output.mkdir()
    arrays_path=checked(job['arrays']);arrays=np.load(arrays_path,allow_pickle=False);frozen={str(input_path):sha(input_path),str(arrays_path):sha(arrays_path)}
    for path,expected in job['frozenInputs'].items():require(sha(path)==expected,'Frozen dependency changed');frozen[path]=expected
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);normal_images={}
    for mid,entry in job['materials'].items():
        for pin in entry['maps'].values():path=checked(pin);frozen[str(path)]=sha(path)
        image=bpy.data.images.load(str(checked(entry['maps']['normal'])),check_existing=False);image.colorspace_settings.name='Non-Color';normal_images[mid]=image
    obj,proof=build_mesh(job,arrays,normal_images);scene=bpy.context.scene;scene.camera=None;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=settings['samples'];scene.cycles.seed=settings['seed'];scene.cycles.use_adaptive_sampling=False;scene.cycles.use_denoising=False
    scene.cycles.max_bounces=2;scene.cycles.diffuse_bounces=0;scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.world.use_nodes=True;background=scene.world.node_tree.nodes.get('Background');background.inputs['Color'].default_value=(1,1,1,1);background.inputs['Strength'].default_value=settings['worldStrength']
    world=(np.c_[arrays['positions'].reshape(-1,3),np.ones(arrays['positions'].size//3)]@np.asarray(obj.matrix_world).T)[:,:3];center=(world.min(0)+world.max(0))/2
    result={'kind':'target-skin-lighting-worker-'+args.operation,'input':filepin(input_path),'geometryTransport':proof,'cpuOnly':True,'sourceChanged':False,'selected':False}
    if args.operation=='bake':
        lights=[]
        for entry in settings['lights']:
            bpy.ops.object.light_add(type='AREA',location=entry['positionWorld']);light=bpy.context.object;light.name=entry['id'];light.data.energy=entry['energy'];light.data.size=entry['sizeMeters'];light.data.color=(1,1,1)
            light.rotation_euler=(Vector(center)-light.location).to_track_quat('-Z','Y').to_euler();lights.append({'config':entry,'matrixWorld':[list(row) for row in light.matrix_world]})
        size=settings['resolution'];atlas=bpy.data.images.new('unselected_linear_diffuse_lighting',width=size,height=size,alpha=False,float_buffer=True,is_data=True)
        for mat in obj.data.materials:
            node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;node.select=True;mat.node_tree.nodes.active=node
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        scene.render.bake.use_pass_color=False;scene.render.bake.use_pass_direct=True;scene.render.bake.use_pass_indirect=False;scene.render.bake.margin=settings['marginPixels'];scene.render.bake.margin_type='EXTEND';scene.render.bake.use_clear=True
        print('CPU diffuse DIRECT bake; original authored normal/tangent basis and normal image at strength1',flush=True);bpy.ops.object.bake(type='DIFFUSE')
        pixels=np.empty(size*size*4,dtype='f4');atlas.pixels.foreach_get(pixels);raw=pixels.reshape(size,size,4)[::-1,:,:3].copy()
        np.savez_compressed(output/'linear-bake.npz',rawLinearRGB=raw);result.update(rawBake=filepin(output/'linear-bake.npz'),lightTransforms=lights,cameraUsedForBake=False)
    else:
        require(args.previews is not None,'Pinned preview manifest required');manifest_path=args.previews.resolve();manifest=json.loads(manifest_path.read_text(encoding='utf-8'));frozen[str(manifest_path)]=sha(manifest_path)
        require(manifest['workerInputSha256']==sha(input_path),'Preview input binding differs')
        background.inputs['Color'].default_value=(0,0,0,1);background.inputs['Strength'].default_value=0;scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
        scene.cycles.samples=8;scene.render.resolution_x=512;scene.render.resolution_y=768;scene.render.resolution_percentage=100
        bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=float(np.ptp(world[:,2])*1.15);rows=[]
        for entry in manifest['images']:
            path=checked(entry['image']);frozen[str(path)]=sha(path);image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='sRGB'
            for i,(mid,part) in enumerate(job['materials'].items()):
                if part['role']=='skin':emission(obj.data.materials[i],image)
                else:
                    cloth=bpy.data.images.load(str(checked(part['maps']['color'])),check_existing=False);cloth.colorspace_settings.name='sRGB';emission(obj.data.materials[i],cloth)
            for name,direction in (('front',np.array([0.,1.,0.])),('rear',np.array([0.,-1.,0.]))):
                camera.location=Vector(center+direction*2);camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler();slug=str(entry['strength']).replace('.','p')
                path=output/('palette'+str(entry['paletteRow'])+'-strength'+slug+'-'+name+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
                rows.append({'strength':entry['strength'],'paletteRow':entry['paletteRow'],'view':name,'worldOutward':direction.tolist(),'image':filepin(path),
                    'cameraMatrixWorld':[list(row) for row in camera.matrix_world],'orthoScale':camera.data.ortho_scale,'sourceAnatomicalOrientationAccepted':False,
                    'emissionOnly':True,'secondaryDirectionalLightingApplied':False,'clientEvidence':False})
        result['previews']=rows
    for path,expected in frozen.items():require(sha(path)==expected,'Worker input changed during operation')
    result['frozenInputs']=frozen;save(output/'worker.json',result);print(json.dumps({'receipt':str(output/'worker.json'),'sha256':sha(output/'worker.json'),'operation':args.operation,'cpuOnly':True}),flush=True)

if __name__=='__main__':main()
