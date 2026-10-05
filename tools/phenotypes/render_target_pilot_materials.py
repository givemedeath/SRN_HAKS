"""Matched literal OFFLINE AO views from audited native Troll pilot arrays.

Neutral Cycles BRDF/lighting; no NWN engine rendering or client acceptance.
Native P/N/UV/T/handedness are decoded directly; no glTF/Mikk tangent bridge.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Matrix,Vector
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
import target_contract as contract
from audit_target_native_part import decode,ascii_meshes
from prepare_effective_body_preview import mesh_corners
from pose_preview_bridge import pose
from pose_preview_render_settings import apply_render_settings
from offline_native_material_bridge import palette_rgba

JOINTS={'head':'head_g','neck':'neck_g','chest':'torso_g','pelvis':'pelvis_g',
 'bicepl':'lbicep_g','bicepr':'rbicep_g','forel':'lforearm_g','forer':'rforearm_g',
 'handl':'lhand_g','handr':'rhand_g'}


def save(path,value):
    path=Path(path)
    contract.require(not path.exists(),'Fresh immutable output required: '+str(path))
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def digest_array(value):return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def mesh_object(name,native):
    p,n,uv,t,sign=[native[key] for key in ('position','normal','uv','tangent','sign')]
    faces=native['faces']
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(p.tolist(),[],faces.tolist());mesh.update()
    for polygon in mesh.polygons:polygon.use_smooth=True
    mesh.normals_split_custom_set_from_vertices(n.tolist())
    layer=mesh.uv_layers.new(name='NativeUV')
    loop_vertices=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',loop_vertices)
    contract.require(np.array_equal(loop_vertices.reshape(-1,3),faces),'Blender native face/corner order changed')
    layer.data.foreach_set('uv',uv[loop_vertices].ravel())
    for key,value in [('native_normal',n),('native_tangent',t)]:
        attribute=mesh.attributes.new(key,'FLOAT_VECTOR','POINT');attribute.data.foreach_set('vector',value.ravel())
        actual=np.empty(value.size,dtype='f4');attribute.data.foreach_get('vector',actual)
        contract.require(np.array_equal(actual.reshape(value.shape),value),'Native shader vector attribute changed')
    attr=mesh.attributes.new('native_handedness','FLOAT','POINT');attr.data.foreach_set('value',sign.ravel())
    ap=np.empty(p.size,dtype='f4');mesh.vertices.foreach_get('co',ap)
    au=np.empty(len(mesh.loops)*2,dtype='f4');layer.data.foreach_get('uv',au)
    contract.require(np.array_equal(ap.reshape(p.shape),p) and np.array_equal(au.reshape(-1,2),uv[loop_vertices]),
                     'Direct native Blender position/UV arrays differ')
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return obj,{'vertices':len(p),'triangles':len(faces),'arrays':{key:digest_array(native[key]) for key in
       ('position','normal','uv','tangent','sign','faces')},'nativePositionUvFaceShaderAttributesExactFloat32':True,
       'customGeometryNormalsBlenderNormalizesMagnitude':True,'noGeometryOrUvBasisConversion':True,
       'blenderRegeneratedTangentsUsed':False}


def texture(material,path,colorspace='sRGB',extension='EXTEND'):
    node=material.node_tree.nodes.new('ShaderNodeTexImage');node.name=Path(path).name
    node.image=bpy.data.images.load(str(path),check_existing=True);node.image.colorspace_settings.name=colorspace
    node.interpolation='Linear';node.extension=extension
    return node


def native_material(name,color_path,normal_path,rough_path):
    material=bpy.data.materials.new(name);material.use_nodes=True
    tree=material.node_tree;nodes=tree.nodes;links=tree.links;nodes.clear()
    def vmath(op,*sockets):
        node=nodes.new('ShaderNodeVectorMath');node.operation=op
        for index,socket in enumerate(sockets):links.new(socket,node.inputs[index])
        return node.outputs['Vector'] if op not in ('DOT_PRODUCT','LENGTH','DISTANCE') else node.outputs['Value']
    def math(op,a=None,b=None):
        node=nodes.new('ShaderNodeMath');node.operation=op
        for index,value in enumerate((a,b)):
            if value is not None:
                if isinstance(value,(int,float)):node.inputs[index].default_value=value
                else:links.new(value,node.inputs[index])
        return node.outputs[0]
    def attr(name):
        node=nodes.new('ShaderNodeAttribute');node.attribute_name=name;return node
    color=texture(material,color_path)
    normal=texture(material,normal_path,'Non-Color');rough=texture(material,rough_path,'Non-Color')
    separate=nodes.new('ShaderNodeSeparateColor');separate.mode='RGB';links.new(normal.outputs['Color'],separate.inputs[0])
    x=math('SUBTRACT',math('MULTIPLY',separate.outputs['Red'],2),1)
    y=math('SUBTRACT',math('MULTIPLY',separate.outputs['Green'],2),1)
    z=math('SQRT',math('MAXIMUM',math('SUBTRACT',1,math('ADD',math('MULTIPLY',x,x),math('MULTIPLY',y,y))),0))
    geom=nodes.new('ShaderNodeNewGeometry');flip=math('SUBTRACT',1,math('MULTIPLY',geom.outputs['Backfacing'],2))
    n=vmath('NORMALIZE',attr('native_normal').outputs['Vector'])
    scale_n=nodes.new('ShaderNodeVectorMath');scale_n.operation='SCALE';links.new(n,scale_n.inputs[0]);links.new(flip,scale_n.inputs['Scale']);n=scale_n.outputs['Vector']
    t=vmath('NORMALIZE',attr('native_tangent').outputs['Vector'])
    # GLSL step(0,h) chooses positive handedness even when interpolation is zero.
    negative=math('LESS_THAN',attr('native_handedness').outputs['Fac'],0)
    h=math('SUBTRACT',1,math('MULTIPLY',negative,2))
    b=vmath('CROSS_PRODUCT',n,t)
    def scale(vector,value):
        node=nodes.new('ShaderNodeVectorMath');node.operation='SCALE';links.new(vector,node.inputs[0]);links.new(value,node.inputs['Scale']);return node.outputs['Vector']
    b=scale(b,h)
    combined=vmath('ADD',vmath('ADD',scale(t,x),scale(b,y)),scale(n,z))
    world=nodes.new('ShaderNodeVectorTransform');world.vector_type='VECTOR';world.convert_from='OBJECT';world.convert_to='WORLD';links.new(combined,world.inputs[0])
    shader=nodes.new('ShaderNodeBsdfPrincipled')
    links.new(color.outputs['Color'],shader.inputs['Base Color']);links.new(rough.outputs['Color'],shader.inputs['Roughness'])
    links.new(world.outputs[0],shader.inputs['Normal']);shader.inputs['Metallic'].default_value=.001
    # Cycles principled default dielectric F0=.04 is a neutral offline policy,
    # not an assertion that NWN Specularity .04 means this exact BRDF.
    shader.inputs['Specular IOR Level'].default_value=.5;shader.inputs['IOR'].default_value=1.5
    out=nodes.new('ShaderNodeOutputMaterial');links.new(shader.outputs[0],out.inputs['Surface'])
    return material,color


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    config_path=args.config.resolve();config=json.loads(config_path.read_text(encoding='utf-8'))
    output=args.output.resolve();contract.require(not output.exists(),'Fresh render output required')
    output.mkdir(parents=True);(output/'helpers').mkdir();(output/'textures').mkdir()
    frozen={str(config_path):contract.sha(config_path)}
    def freeze(path,expected=None):
        path=Path(path).resolve()
        if str(path) in frozen:
            contract.require(expected is None or frozen[str(path)]==expected,'Conflicting frozen pin')
        else:
            actual=contract.sha(path);contract.require(expected is None or actual==expected,'Changed render input: '+str(path));frozen[str(path)]=actual
        return path
    try:
        contract.require(config['kind']=='target-pilot-offline-native-ao-render' and config['schemaVersion']==2,'Explicit new offline render config required')
        for path,expected in config['expectedInputHashes'].items():freeze(path,expected)
        target_path=freeze(config['targetContract'],config['targetContractSha256']);target=contract.load(target_path)
        contract.require(config['coordinateSpace']=='working' and config['aoStrengths']==[0,.15,.35], 'Working identical AO0/.15/.35 required')
        contract.require(set(config['parts'])=={'chest','bicepl','bicepr'},'Exactly current three pilot native parts required')
        assembly=Path(config['targetAssembly']);diagnostic=json.loads(freeze(assembly/'diagnostic.json',config['diagnosticSha256']).read_text())
        contract.verify_binding(diagnostic['target'],target_path,target,'working')
        for resource,pin in diagnostic['resources'].items():freeze(assembly/'ascii'/resource,pin)
        palette=np.asarray(Image.open(freeze(config['skinPalette'],config['skinPaletteSha256'])).convert('RGB'))
        contract.require(config['paletteRow']==3,'This frozen comparison is explicitly palette3')
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        objects={};materials={};color_nodes={};images={};geometry_receipts={};stage_records={}
        for part,entry in config['parts'].items():
            audit=json.loads(freeze(entry['nativeAudit']['path'],entry['nativeAudit']['sha256']).read_text())
            contract.verify_binding(audit,target_path,target,'working')
            contract.require(audit['part']==part and audit['attributeTransportVerified'] and audit['materialTransportVerified'],'Completed exact native audit required')
            for path,pin in audit['frozenInputs'].items():freeze(path,pin)
            stage0=None;stage_records[part]={};images[part]={}
            for strength in config['aoStrengths']:
                ref=entry['stages'][str(strength)];stage_path=freeze(ref['path'],ref['sha256']);stage=json.loads(stage_path.read_text())
                contract.verify_binding(stage,target_path,target,'working')
                contract.require(stage['part']==part and stage['aoStrength']==strength and stage['statureApplications']==0 and
                    list(stage['materialRoles'].values())==['skin'] and stage['sourceSha256']==stage['untreatedParentSha256'],
                    'Exact untreated working skin stage required')
                for path,pin in stage['frozenInputs'].items():freeze(path,pin)
                if stage0 is None:stage0=stage
                contract.require(stage['sourceSha256']==stage0['sourceSha256'] and stage['sourceReceiptSha256']==stage0['sourceReceiptSha256'] and
                    stage['asciiModelSha256']==stage0['asciiModelSha256'],'AO versions differ in source/geometry')
                for suffix in ('.mtr','n.tga','r.tga'):
                    contract.require(stage['materialResourceHashes'][stage['model']+suffix]==stage0['materialResourceHashes'][stage['model']+suffix], 'AO versions differ beyond PLT')
                for name,pin in stage['materialResourceHashes'].items():freeze(stage_path.parent/'resources'/name,pin)
                plt=stage_path.parent/'resources'/(stage['model']+'.plt')
                rgba=palette_rgba(plt.read_bytes(),palette,config['paletteRow'])
                contract.require(rgba.shape==(2048,2048,4) and (rgba[:,:,3]==255).all(),'Opaque 2K palette skin required')
                png=output/'textures'/(part+'-ao'+str(strength)+'.png');Image.fromarray(rgba).save(png)
                images[part][str(strength)]=bpy.data.images.load(str(png));images[part][str(strength)].colorspace_settings.name='sRGB'
                stage_records[part][str(strength)]={'stage':str(stage_path),'sha256':contract.sha(stage_path),'plt':str(plt),
                    'pltSha256':contract.sha(plt),'paletteColorPng':str(png),'paletteColorPngSha256':contract.sha(png),
                    'untreatedParentSha256':stage['untreatedParentSha256'],'aoVariantNativeCompiled':strength==0}
            ascii_path=freeze(stage0['asciiModel'],stage0['asciiModelSha256'])
            ascii_rows=ascii_meshes(ascii_path.read_text(encoding='ascii'),stage0['model'],stage0['materialRoles'].values())
            native_path=freeze(entry['nativeModel'],audit['nativeModelSha256'])
            meshes,_=decode(native_path.read_bytes(),stage0['model'],ascii_rows)
            contract.require(len(meshes)==1,'One audited direct skin mesh required')
            obj,proof=mesh_object(part,next(iter(meshes.values())));objects[part]=obj
            geometry_receipts[part]={'nativeModel':str(native_path),'nativeSha256':contract.sha(native_path),'proof':proof,'classification':'audited-target-native-pilot'}
            folder=Path(entry['stages']['0']['path']).parent/'resources'
            material,color=native_material(part,output/'textures'/(part+'-ao0.png'),folder/(stage0['model']+'n.tga'),folder/(stage0['model']+'r.tga'))
            obj.data.materials.append(material);materials[part]=material;color_nodes[part]=color
        # Explicit stock context, with source-computed normals where ASCII omits
        # them. No assertion of compiled native shading for these fallbacks.
        for part in config['stockContextParts']:
            contract.require(part in JOINTS and part not in objects,'Unknown/overlapping stock context owner')
            path=freeze(assembly/'ascii'/(target['identity']['prefix']+'_'+part+'001.mdl'))
            rows=mesh_corners(path.read_text(encoding='cp1252'))
            for i,row in enumerate(rows):
                p=row['position'].reshape(-1,3).astype('f4');n=row['normal'].reshape(-1,3).astype('f4');uv=row['uv'].reshape(-1,2).astype('f4')
                native={'position':p,'normal':n,'uv':uv,'tangent':np.tile([1,0,0],(len(p),1)).astype('f4'),
                    'sign':np.ones(len(p),dtype='f4'),'faces':np.arange(len(p)).reshape(-1,3)}
                obj,_=mesh_object(part+'-fallback'+str(i),native);objects[part+'#'+str(i)]=obj
                material=bpy.data.materials.new(obj.name);material.use_nodes=True;shader=material.node_tree.nodes.get('Principled BSDF')
                shader.inputs['Base Color'].default_value=(.34,.34,.34,1);shader.inputs['Roughness'].default_value=.8
                policy='neutral gray fallback; not material-matched'
                if part=='neck':
                    plt=freeze(config['stockNeckPlt'],config['stockNeckPltSha256'])
                    png=output/'textures'/('stock-neck-'+str(i)+'.png');Image.fromarray(palette_rgba(plt.read_bytes(),palette,3)).save(png)
                    tex=texture(material,png);material.node_tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
                    policy='actual stock neck PLT palette3; computed ASCII normals and offline roughness .8'
                obj.data.materials.append(material)
                geometry_receipts[part+'#'+str(i)]={'ascii':str(path),'sha256':contract.sha(path),'normalPolicy':row['normalPolicy'],
                    'classification':'declared-target-stock-ascii-context','materialPolicy':policy,'noTargetBodyAcceptance':True}
        # Freeze every imported local dependency and retain its exact execution
        # snapshot. New helper provenance does not alter historical receipts.
        snapshots={}
        tools=Path(__file__).resolve().parent
        module_paths={Path(__file__).resolve()}
        for module in tuple(sys.modules.values()):
            filename=getattr(module,'__file__',None)
            if filename:
                path=Path(filename).resolve()
                if path.suffix=='.py' and tools in path.parents:module_paths.add(path)
        for path in sorted(module_paths):
            freeze(path);dest=output/'helpers'/path.name;shutil.copyfile(path,dest)
            snapshots[str(path)]={'sha256':contract.sha(path),'snapshot':str(dest),'snapshotSha256':contract.sha(dest)}
        scene=bpy.context.scene;render=apply_render_settings(scene,'cycles-cpu')
        scene.cycles.seed=31;scene.cycles.use_animated_seed=False
        scene.render.resolution_x=config['width'];scene.render.resolution_y=config['height'];scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='16'
        scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.7;scene.view_settings.gamma=1
        scene.world.use_nodes=True;world=scene.world.node_tree.nodes.get('Background');world.inputs['Color'].default_value=(.15,.15,.15,1);world.inputs['Strength'].default_value=.35
        target_vector=Vector(config['cameraTarget'])
        light_receipts=[]
        for number,(position,energy,size) in enumerate(config['lights']):
            bpy.ops.object.light_add(type='AREA',location=position);light=bpy.context.object;light.name='neutral-light-'+str(number)
            light.data.energy=energy;light.data.size=size;light.rotation_euler=(target_vector-light.location).to_track_quat('-Z','Y').to_euler()
            light_receipts.append({'position':position,'energy':energy,'size':size,'matrixWorld':[list(row) for row in light.matrix_world]})
        bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=config['cameraScale']
        render_rows=[];pose_receipts=[]
        for definition in config['poses']:
            matrices,pose_receipt=pose(assembly/'ascii',target['identity']['prefix'],definition['clip'],definition['time'])
            for row in pose_receipt['sourceInheritance']:freeze(row['file'],row['sha256'])
            pose_receipt['jointWorldMatrices']={joint:matrices[joint].tolist() for joint in JOINTS.values()}
            pose_receipts.append(pose_receipt)
            for name,obj in objects.items():
                obj.matrix_world=Matrix(matrices[JOINTS[name.split('#')[0]]])
                contract.require(abs(obj.matrix_world.to_3x3().determinant()-1)<2e-6,'Pose introduces scale/reflection')
            bpy.context.view_layer.update()
            pose_geometry_sha=hashlib.sha256(json.dumps({name:[list(row) for row in obj.matrix_world] for name,obj in objects.items()},sort_keys=True).encode()).hexdigest()
            for view,direction in [('front',(0,1,0)),('left',(-1,0,0))]:
                camera.location=target_vector+Vector(direction)*8;camera.rotation_euler=(target_vector-camera.location).to_track_quat('-Z','Y').to_euler()
                bpy.context.view_layer.update()
                camera_receipt={'view':view,'projection':'orthographic','scale':camera.data.ortho_scale,
                    'matrixWorld':[list(row) for row in camera.matrix_world], 'target':config['cameraTarget'],'width':config['width'],'height':config['height']}
                for strength in config['aoStrengths']:
                    for part,node in color_nodes.items():node.image=images[part][str(strength)]
                    name=definition['id']+'-'+view+'-ao'+str(strength)+'.png';image_path=output/name
                    scene.render.filepath=str(image_path);print('RENDER '+name,flush=True);bpy.ops.render.render(write_still=True)
                    render_rows.append({'file':str(image_path),'sha256':contract.sha(image_path),'pose':definition,
                      'aoStrength':strength,'camera':camera_receipt,'posedMatricesSha256':pose_geometry_sha,
                      'geometryArrayProofSharedAcrossAo':True,'onlyChangedMaterialInput':'palette color image from exact stage PLT',
                      'offlineOnly':True,'clientAccepted':False,'aoSelected':False})
                    save(output/(name+'.receipt.json'),render_rows[-1])
        bpy.ops.wm.save_as_mainfile(filepath=str(output/'offline-comparison.blend'))
        for path,expected in frozen.items():contract.require(contract.sha(path)==expected,'Input changed while rendering: '+path)
        receipt={'schemaVersion':2,'kind':'target-pilot-offline-native-ao-render',**contract.binding(target_path,target,'working'),
          'paletteRow':3,'renderSettings':render,'renderSeed':31,'exposure':-.7,'viewTransform':'Standard','look':'None',
          'normalInterpretation':'Original texture1 RG*2-1; z=sqrt(max(1-dot(xy,xy),0)); normalized interpolated native N/T; B=cross(N,T)*step-sign; identity texture matrix; world rigid pose. Strength1.',
          'normalBlueConsumed':False,'nativeTangentBasisUsed':True,'blenderRegeneratedTangentsUsed':False,
          'nativeUvPolicy':'Bottom-origin native UV directly into Blender; generated PNG top-origin, Blender loads bottom-origin internally.',
          'palettePolicy':'Actual installed palette3 categorical lookup per PLT texel before spatial filtering; sRGB interpretation is offline.',
          'roughnessPolicy':'Exact stage texture3 red from original ORM green; Principled roughness, no map edits or clamp added.',
          'brdfPolicy':'Neutral Cycles Principled dielectric F0 .04, metallic .001; does not reproduce NWN Specularity/lighting/quality macros.',
          'stages':stage_records,'geometry':geometry_receipts,'poses':pose_receipts,'lights':light_receipts,'renders':render_rows,
          'importedHelperSnapshots':snapshots,'frozenInputs':frozen,'nativeCoordinateDisplayScale':1,'statureApplications':0,
          'limitations':['Literal offline Blender captures, not NWN client materials or engine playback.',
            'Shader decode and native-basis arithmetic are represented; Cycles interpolation, filtering, normal normalization, BRDF, shadows, gamma and tone response differ from NWN.',
            'Stock gray context is not target material validation. Neck uses actual PLT with source-computed normals.',
            'Uncompiled AO .15/.35 use AO0 native geometry because exact ASCII/normal/roughness hashes prove these unchanged.',
            'Upper-body framing does not prove equipment or full-body anatomy; exposed terminal patch remains unaccepted.'],
          'rigPilotAccepted':False,'bodyAccepted':False,'aoSelected':None,'productionAccepted':False,'clientAccepted':False}
        save(output/'comparison.json',receipt)
        print(json.dumps({'receipt':str(output/'comparison.json'),'sha256':contract.sha(output/'comparison.json'),'renders':len(render_rows)}),flush=True)
    except Exception as error:
        save(output/'failure.json',{'error':str(error),'frozenInputs':frozen,'acceptance':False});raise

if __name__=='__main__':main()
