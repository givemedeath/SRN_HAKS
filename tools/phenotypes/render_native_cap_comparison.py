"""CPU-only exact native control/repaired upper-arm material views.

Whole-part and full-geometry cap context are separate from an explicitly isolated
single-triangle magnification. No client/production acceptance or mesh repair.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import target_contract as c
from target_part_pipeline import pin
from place_purposebuilt_pelvis import read_glb

KEYS=('position','normal','uv','tangent','sign','faces')


def controls(cfg):
    allowed={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','part','coordinateSpace','skinPalette','skinPaletteSha256','paletteRows','control','repaired','capPreparation','capPreparationSha256','capOriginalFaceId','width','height','renderer'}
    c.require(set(cfg)==allowed and cfg['schemaVersion']==2 and cfg['kind']=='explicit-cap-offline-native-comparison' and cfg['diagnosticOnly'] is True,'Explicit narrow offline native comparison config required')
    c.require(cfg['part']=='bicepl' and cfg['coordinateSpace']=='working' and cfg['paletteRows']==[3,8] and cfg['capOriginalFaceId']==24724 and cfg['renderer']=='cycles-cpu','Exact current upper-arm cap/working/palette3+8/CPU scope required')
    c.require(type(cfg['width']) is int and type(cfg['height']) is int and 256<=cfg['width']<=960 and 256<=cfg['height']<=960,'Bounded integer native preview dimensions required')
    for variant in ('control','repaired'):
        row=cfg[variant];c.require(isinstance(row,dict) and set(row)=={'nativeAudit','nativeAuditSha256','nativeModel'},'Exact actual native audit/model association required')


def digest_array(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def camera_plans(points,cap,width,height):
    p=np.asarray(points,float);cap=np.asarray(cap,float);c.require(p.ndim==2 and p.shape[1]==3 and cap.shape==(3,3) and np.isfinite(p).all() and np.isfinite(cap).all(),'Finite complete native camera geometry required')
    aspect=width/height;target=(p.min(0)+p.max(0))/2;result=[]
    def make(name,outward,up,target,scale,isolated=False):
        z=np.asarray(outward,float);z/=np.linalg.norm(z);u=np.cross(up,z);u/=np.linalg.norm(u);v=np.cross(z,u);rotation=np.column_stack([u,v,z]);matrix=np.eye(4);matrix[:3,:3]=rotation;matrix[:3,3]=target+z*1
        return {'id':name,'matrixWorld':matrix.tolist(),'target':target.tolist(),'orthographicHeightMetres':float(scale),'isolatedCapOnly':isolated,'actualGeometryScale':1,'cameraDistanceMetres':1}
    for name,direction in [('local-front-y+',[0,1,0]),('local-rear-y-',[0,-1,0]),('local-x+',[1,0,0]),('local-x-',[-1,0,0])]:
        z=np.asarray(direction,float);u=np.cross([0,0,1],z);up=np.cross(z,u);project=np.c_[(p-target)@u,(p-target)@up];span=np.ptp(project,axis=0);scale=max(span[1],span[0]/aspect)*1.12;result.append(make(name,z,np.asarray([0,0,1]),target,scale))
    cross=np.cross(cap[1]-cap[0],cap[2]-cap[0]);c.require(np.linalg.norm(cross)>1e-14,'Nondegenerate exact cap camera basis required');z=cross/np.linalg.norm(cross);edges=cap[[1,2,0]]-cap;u=edges[np.argmax(np.linalg.norm(edges,axis=1))];u/=np.linalg.norm(u);up=np.cross(z,u);target=cap.mean(0)
    result.append(make('cap-full-geometry-context',z,up,target,.018))
    scale=max(np.ptp(cap@up),np.ptp(cap@u)/aspect)*1.25;result.append(make('cap-isolated-triangle-magnification',z,up,target,scale,True))
    return result


def save(path,value):
    path=Path(path);c.require(not path.exists(),'Fresh immutable native preview output required');path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def prepare(config_path,output):
    from audit_target_native_part import decode
    from diagnose_native_cap_normal import validate_descendant
    from PIL import Image
    from offline_native_material_bridge import palette_rgba
    config_path=Path(config_path).resolve();cfg=json.loads(config_path.read_text());controls(cfg);tp=pin(cfg['targetContract'],cfg['targetContractSha256']);target=c.load(tp);c.require(c.rig_mode(target)=='stock-exact','Stock-exact working source required');pal=pin(cfg['skinPalette'],cfg['skinPaletteSha256']);c.require(target['frozenInputs'].get(str(pal))==c.sha(pal),'Installed female palette must be pinned by exact target')
    pp=pin(cfg['capPreparation'],cfg['capPreparationSha256']);prep=json.loads(pp.read_text());c.require(prep['kind']=='target-native-cap-normal-preparation' and prep['part']=='bicepl','Explicit cap-normal diagnostic required');c.verify_binding(prep,tp,target,'working')
    for name,h in {**prep['frozenInputs'],**prep['helperSnapshots']}.items():pin(name,h)
    original=pin(prep['source'],prep['sourceSha256']);candidate=pin(prep['diagnosticCandidate'],prep['diagnosticCandidateSha256']);od,ob=read_glb(original);nd,nb=read_glb(candidate);p,cn,uv,ct,order,exception=validate_descendant(od,ob,nd,nb,cfg['capOriginalFaceId']);model=c.model(target,'bicepl')
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable native render preparation required');output.mkdir();(output/'textures').mkdir();frozen={str(q):c.sha(q) for q in [config_path,tp,pal,pp,original,candidate,Path(__file__).resolve()]};variants={};native_rows={};material_hashes=None;palette=np.asarray(Image.open(pal).convert('RGB'))
    for variant in ('control','repaired'):
        entry=cfg[variant];ap=pin(entry['nativeAudit'],entry['nativeAuditSha256']);audit=json.loads(ap.read_text());c.verify_binding(audit,tp,target,'working');c.require(audit['kind']=='target-native-part-audit' and audit['part']=='bicepl' and audit['attributeTransportVerified'] and audit['materialTransportVerified'] and len(audit['meshes'])==1,'Exact one-skin-trimesh native audit required')
        for name,h in audit['frozenInputs'].items():pin(name,h)
        nativepath=pin(entry['nativeModel'],audit['nativeModelSha256']);meshes,_=decode(nativepath.read_bytes(),model,set(audit['meshes']));native=next(iter(meshes.values()));stagepath=pin(audit['stageReceipt'],audit['stageReceiptSha256']);stage=json.loads(stagepath.read_text());c.require(stage['aoStrength']==0 and stage['materialRoles']=={'0':'skin'} and not stage['derivedMaterialProof'],'Exact original-map AO0 skin stage required')
        c.require(stage['sourceSha256']==(c.sha(original) if variant=='control' else c.sha(candidate)),'Control/repaired native source association differs')
        if material_hashes is None:material_hashes=stage['materialResourceHashes']
        c.require(stage['materialResourceHashes']==material_hashes,'Matched control/repaired material hashes required')
        arrays_path=output/(variant+'-native.npz');np.savez_compressed(arrays_path,**{k:native[k] for k in KEYS});native_rows[variant]=native
        face_index=cfg['capOriginalFaceId'] if variant=='control' else int(np.flatnonzero(order==cfg['capOriginalFaceId'])[0]);ids=native['faces'][face_index];cap={k:native[k][ids] for k in KEYS if k!='faces'};cap['faces']=np.asarray([[0,1,2]],dtype=native['faces'].dtype);cap_path=output/(variant+'-isolated-cap.npz');np.savez_compressed(cap_path,**cap)
        textures={}
        resources=stagepath.parent/'resources'
        for name,h in stage['materialResourceHashes'].items():q=pin(resources/name,h);frozen[str(q)]=h
        for row in cfg['paletteRows']:
            rgba=palette_rgba((resources/(model+'.plt')).read_bytes(),palette,row);q=output/'textures'/(variant+'-palette'+str(row)+'.png');Image.fromarray(rgba,'RGBA').save(q);textures[str(row)]={'path':str(q),'sha256':c.sha(q)}
        variants[variant]={'nativeAudit':{'path':str(ap),'sha256':c.sha(ap)},'nativeModel':{'path':str(nativepath),'sha256':c.sha(nativepath)},'stage':{'path':str(stagepath),'sha256':c.sha(stagepath)},'arrays':{'path':str(arrays_path),'sha256':c.sha(arrays_path),'digests':{k:digest_array(native[k]) for k in KEYS}},'isolatedCap':{'path':str(cap_path),'sha256':c.sha(cap_path),'digests':{k:digest_array(cap[k]) for k in KEYS},'serializedSourceFaceId':face_index,'originalSourceFaceId':cfg['capOriginalFaceId'],'excludedTriangles':len(native['faces'])-1},'textures':textures,'normal':{'path':str(resources/(model+'n.tga')),'sha256':material_hashes[model+'n.tga']},'roughness':{'path':str(resources/(model+'r.tga')),'sha256':material_hashes[model+'r.tga']}}
        for q in [ap,nativepath,stagepath]:frozen[str(q)]=c.sha(q)
    for key in ['position','normal','uv']:
        expected=p if key=='position' else cn if key=='normal' else uv.copy()
        if key=='uv':expected[:,:,1]=1-expected[:,:,1]
        actual=native_rows['repaired'][key][native_rows['repaired']['faces']];c.require(np.array_equal(actual,expected[order].astype('f4')),'Exact repaired native corner association differs')
    cap_control=np.load(variants['control']['isolatedCap']['path'])['position'];plans=camera_plans(native_rows['control']['position'],cap_control,cfg['width'],cfg['height']);c.require(np.array_equal(cap_control,np.load(variants['repaired']['isolatedCap']['path'])['position']),'Matched cap camera positions differ')
    for name in ['render_native_cap_comparison.py','render_target_pilot_materials_v2.py','offline_native_material_bridge.py','prepare_effective_body_preview.py','audit_target_native_part.py','diagnose_native_cap_normal.py','pose_preview_render_settings.py','target_contract.py','target_part_pipeline.py']:
        q=Path(__file__).with_name(name).resolve();frozen[str(q)]=c.sha(q)
    receipt={'schemaVersion':2,'kind':'prepared-explicit-cap-offline-native-comparison',**c.binding(tp,target,'working'),'part':'bicepl','variants':variants,'paletteRows':cfg['paletteRows'],'skinPalette':{'path':str(pal),'sha256':c.sha(pal)},'width':cfg['width'],'height':cfg['height'],'renderer':'cycles-cpu','cameras':plans,'capException':exception,'materialResourceHashesMatched':material_hashes,'frozenInputs':frozen,'diagnosticOnly':True,'selected':False,'clientAccepted':False,'productionAccepted':False}
    save(output/'render-preparation.json',receipt);return output/'render-preparation.json'


def render(preparation_path,output):
    import bpy
    from mathutils import Matrix,Vector
    from render_target_pilot_materials_v2 import mesh_object,native_material
    from pose_preview_render_settings import apply_render_settings
    preparation_path=Path(preparation_path).resolve();prep=json.loads(preparation_path.read_text());c.require(prep['kind']=='prepared-explicit-cap-offline-native-comparison' and prep['renderer']=='cycles-cpu','Exact prepared CPU-only native comparison required');tp=pin(prep['targetContract'],prep['targetContractSha256']);target=c.load(tp);c.verify_binding(prep,tp,target,'working')
    for name,h in prep['frozenInputs'].items():pin(name,h)
    output=Path(output).resolve();c.require(not output.exists(),'Fresh immutable native render required');output.mkdir();(output/'helpers').mkdir();frozen={str(preparation_path):c.sha(preparation_path),**prep['frozenInputs']};bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);objects={};materials={};colors={};proofs={}
    for variant,row in prep['variants'].items():
        for owner in ['arrays','isolatedCap']:
            path=pin(row[owner]['path'],row[owner]['sha256']);frozen[str(path)]=c.sha(path)
            with np.load(path) as a:data={k:a[k] for k in KEYS}
            c.require(all(digest_array(data[k])==row[owner]['digests'][k] for k in KEYS),'Exact native shader arrays changed')
            obj,proof=mesh_object(variant+'-'+owner,data);objects[(variant,owner)]=obj;proofs[variant+'-'+owner]=proof;obj.hide_render=True
        normal=pin(row['normal']['path'],row['normal']['sha256']);rough=pin(row['roughness']['path'],row['roughness']['sha256']);q=pin(row['textures']['3']['path'],row['textures']['3']['sha256']);mat,color=native_material(variant,q,normal,rough);materials[variant]=mat;colors[variant]=color
        for owner in ['arrays','isolatedCap']:objects[(variant,owner)].data.materials.append(mat)
        for p in row['textures'].values():q=pin(p['path'],p['sha256']);frozen[str(q)]=c.sha(q)
    scene=bpy.context.scene;settings=apply_render_settings(scene,'cycles-cpu');scene.cycles.use_denoising=False;settings['denoising']=False;scene.cycles.seed=41;scene.cycles.use_animated_seed=False;scene.render.resolution_x=prep['width'];scene.render.resolution_y=prep['height'];scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='16';scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.7;scene.view_settings.gamma=1;scene.world.use_nodes=True;world=scene.world.node_tree.nodes.get('Background');world.inputs['Color'].default_value=(.15,.15,.15,1);world.inputs['Strength'].default_value=.35
    bpy.ops.object.camera_add();camera=bpy.context.object;scene.camera=camera;camera.data.type='ORTHO';camera.data.clip_start=.00001;camera.data.clip_end=3
    lights=[]
    for energy in [2.4,.8]:bpy.ops.object.light_add(type='SUN');sun=bpy.context.object;sun.data.energy=energy;sun.data.angle=.15;lights.append(sun)
    imported={}
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if filename:
            q=Path(filename).resolve()
            if q.suffix=='.py' and Path(__file__).resolve().parent in q.parents:
                frozen[str(q)]=c.sha(q);snapshot=output/'helpers'/q.name;shutil.copyfile(q,snapshot);imported[str(q)]={'path':str(snapshot),'sha256':c.sha(snapshot)}
    rows=[]
    try:
        for definition in prep['cameras']:
            matrix=np.asarray(definition['matrixWorld']);camera.matrix_world=Matrix(matrix);camera.data.ortho_scale=definition['orthographicHeightMetres'];u,v,z=matrix[:3,0],matrix[:3,1],matrix[:3,2]
            dirs=[z+.6*u+.8*v,z-.8*u+.2*v]
            for light,direction in zip(lights,dirs):light.rotation_euler=Vector(-direction).to_track_quat('-Z','Y').to_euler()
            bpy.context.view_layer.update();camera_record={**definition,'actualMatrixWorld':[list(q) for q in camera.matrix_world],'lighting':[{'energy':light.data.energy,'matrixWorld':[list(q) for q in light.matrix_world]} for light in lights]}
            owner='isolatedCap' if definition['isolatedCapOnly'] else 'arrays'
            for palette in prep['paletteRows']:
                for variant,row in prep['variants'].items():
                    for obj in objects.values():obj.hide_render=True
                    obj=objects[(variant,owner)];obj.hide_render=False;tex=pin(row['textures'][str(palette)]['path'],row['textures'][str(palette)]['sha256']);im=bpy.data.images.load(str(tex),check_existing=True);im.colorspace_settings.name='sRGB';colors[variant].image=im;name='palette'+str(palette)+'-'+definition['id']+'-'+variant+'.png';dest=output/name;scene.render.filepath=str(dest);print('RENDER '+name,flush=True);bpy.ops.render.render(write_still=True)
                    record={'path':str(dest),'sha256':c.sha(dest),'variant':variant,'paletteRow':palette,'camera':camera_record,'nativeAudit':row['nativeAudit'],'nativeModel':row['nativeModel'],'nativeArraysProof':proofs[variant+'-'+owner],'classification':'isolated exact native single triangle; all other geometry intentionally excluded' if definition['isolatedCapOnly'] else 'complete exact native upper-arm mesh; actual self occlusion retained','offlineOnly':True,'clientAccepted':False,'productionAccepted':False};rows.append(record);save(output/(name+'.receipt.json'),record)
        for name,h in frozen.items():pin(name,h)
        receipt={'schemaVersion':2,'kind':'explicit-cap-offline-native-comparison',**c.binding(tp,target,'working'),'part':'bicepl','preparation':{'path':str(preparation_path),'sha256':c.sha(preparation_path)},'renderSettings':settings,'renderSeed':41,'viewTransform':'Standard','exposure':-.7,'paletteRows':prep['paletteRows'],'materialResourcesMatched':prep['materialResourceHashesMatched'],'geometryProof':proofs,'renders':rows,'frozenInputs':frozen,'helperSnapshots':imported,'normalInterpretation':'Exact native interpolated N/T/W; normal texture RG*2-1 and reconstructed Z; B=cross(N,T)*step-sign. Native bottom-origin UV directly consumed. Normal blue not used. No Mikk/generated tangents.','paletteInterpretation':'Installed frozen female palette3/8 lookup for each original PLT texel before bilinear filtering. Offline sRGB interpretation.','brdfInterpretation':'Neutral CPU Cycles Principled, exact original normal/roughness maps, same matched SUN/world/exposure. This differs from NWN lighting/quality/shadows/BRDF/gamma.','limitations':['Four cardinal views use the attachment-local part frame, not a posed assembled character.','Cap context retains all49,998 triangles; isolated cap magnification deliberately suppresses all other49,997 triangles and cannot establish gameplay visibility.','No finite ray or magnified shader diagnostic implies hidden defect acceptance. Physical folded cap remains and10913 is unchanged.','These are CPU offline native material interpretations, not NWN client captures.'],'selected':False,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False}
        save(output/'comparison.json',receipt);return output/'comparison.json'
    except Exception as error:save(output/'failure.json',{'error':str(error),'rendersCompleted':rows,'frozenInputs':frozen,'productionAccepted':False});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','render'),required=True);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None;args=parser.parse_args(argv);result=prepare(args.input,args.output) if args.phase=='prepare' else render(args.input,args.output);print(json.dumps({'receipt':str(result),'sha256':c.sha(result)}),flush=True)
