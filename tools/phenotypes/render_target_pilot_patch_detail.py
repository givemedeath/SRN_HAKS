"""Literal matched OFFLINE closeups of a frozen measured casting terminal patch.

Loads a disposable saved offline scene; never edits source mesh/maps or accepts
NWN rendering. Only the camera framing and diffuse AO image binding change.
"""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):result.update(block)
    return result.hexdigest()

def require(condition,message):
    if not condition:raise RuntimeError(message)

def save(path,value):
    require(not path.exists(),'Fresh immutable closeup output required')
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

def digest(value):return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--comparison',type=Path,required=True)
    p.add_argument('--comparison-sha256',required=True);p.add_argument('--patch-review',type=Path,required=True)
    p.add_argument('--patch-review-sha256',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);output=args.output.resolve()
    require(not output.exists(),'Fresh output required');output.mkdir(parents=True)
    frozen={}
    def freeze(path,expected=None):
        path=Path(path).resolve();actual=sha(path);require(expected is None or actual==expected,'Changed input: '+str(path))
        require(str(path) not in frozen or frozen[str(path)]==actual,'Changed reused input');frozen[str(path)]=actual;return path
    comparison_path=freeze(args.comparison,args.comparison_sha256);source=json.loads(comparison_path.read_text())
    require(source['kind']=='target-pilot-offline-native-ao-render' and not source['clientAccepted'],'Literal offline parent required')
    for path,pin in source['frozenInputs'].items():freeze(path,pin)
    bridge_path=freeze(source['bridgeReceipt'],source['bridgeReceiptSha256']);bridge=json.loads(bridge_path.read_text())
    review_path=freeze(args.patch_review,args.patch_review_sha256);review=json.loads(review_path.read_text())
    require(review['target']['targetContractSha256']==source['targetContractSha256'],'Patch target differs')
    audit_path=freeze(review['audit'],review['auditSha256']);audit=json.loads(audit_path.read_text())
    states=[item for item in audit['poses'] if item['state']=='conjure1'];require(len(states)==1 and states[0]['time']==.25,'Actual measured casting time required')
    patches=[row for row in review['chestTerminalCapExposure'] if row['state']=='conjure1' and row['zone']=='left_chest_terminal_cap' and row['view']=='left']
    require(len(patches)==1 and patches[0]['unoccludedSamples']>0,'Measured exposed casting patch required');patch=patches[0]
    bounds=np.asarray(patch['poseSampleBoundsMetres']);target=Vector(bounds.mean(axis=0))
    scene_path=freeze(comparison_path.parent/'offline-comparison.blend')
    bpy.ops.wm.open_mainfile(filepath=str(scene_path));scene=bpy.context.scene
    require(scene.render.engine=='CYCLES' and scene.cycles.device=='CPU' and scene.cycles.samples==16 and scene.render.threads==4,'Saved CPU policy differs')
    pose=[row for row in source['poses'] if row['clip']=='conjure1' and row['time']==.25];require(len(pose)==1,'Exact casting pose required')
    joints={'chest':'torso_g','bicepl':'lbicep_g','bicepr':'rbicep_g'}
    geometry_proofs={}
    for part,ref in bridge['nativeParts'].items():
        archive=freeze(ref['file'],ref['sha256'])
        with np.load(archive) as data:original={key:data[key] for key in data.files}
        obj=bpy.data.objects[part];mesh=obj.data
        p=np.empty(len(mesh.vertices)*3,dtype='f4');mesh.vertices.foreach_get('co',p)
        actual={'position':p.reshape(-1,3)}
        vi=np.empty(len(mesh.loops),dtype='i4');mesh.loops.foreach_get('vertex_index',vi)
        require(np.array_equal(vi.reshape(-1,3),original['faces']),'Saved native face order differs')
        uv=np.empty(len(mesh.loops)*2,dtype='f4');mesh.uv_layers.active.data.foreach_get('uv',uv)
        require(np.array_equal(uv.reshape(-1,2),original['uv'][vi]),'Saved native UV differs')
        for key,name in [('normal','native_normal'),('tangent','native_tangent')]:
            values=np.empty(len(mesh.vertices)*3,dtype='f4');mesh.attributes[name].data.foreach_get('vector',values);actual[key]=values.reshape(-1,3)
        signs=np.empty(len(mesh.vertices),dtype='f4');mesh.attributes['native_handedness'].data.foreach_get('value',signs)
        require(np.array_equal(signs,original['sign'].ravel()),'Saved native sign differs')
        for key,value in actual.items():require(np.array_equal(value,original[key]),'Saved native '+key+' differs')
        matrix=np.asarray(obj.matrix_world)
        require(np.array_equal(matrix,np.asarray(pose[0]['jointWorldMatrices'][joints[part]],dtype='f4')),'Saved native posed joint differs')
        geometry_proofs[part]={'savedPositionNormalTangentSignUvFacesExact':True,'jointMatrixExactParent':True,'archiveSha256':sha(archive)}
    for item in source['lights']:
        matches=[obj for obj in bpy.data.objects if obj.type=='LIGHT' and np.array_equal(np.asarray(obj.matrix_world),np.asarray(item['matrixWorld'],dtype='f4'))]
        require(len(matches)==1 and matches[0].data.energy==item['energy'] and matches[0].data.size==item['size'],'Saved neutral lights differ')
    scene.render.resolution_x=1536;scene.render.resolution_y=1536;scene.render.resolution_percentage=100
    camera=scene.camera;camera.data.ortho_scale=.20;camera.location=target+Vector((-8,0,0));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update();rows=[]
    camera_record={'projection':'orthographic','view':'left','target':list(target),'scale':.20,
       'matrixWorld':[list(row) for row in camera.matrix_world],'width':1536,'height':1536,'workingMillimetresPerPixel':.20/1536*1000}
    freeze(__file__);shutil.copyfile(__file__,output/'executed-helper.py')
    for strength in (0,.15,.35):
        for part in joints:
            ref=bridge['textures'][part][str(strength)];png=freeze(ref['file'],ref['sha256'])
            material=bpy.data.objects[part].data.materials[0]
            image_nodes=[node for node in material.node_tree.nodes if node.type=='TEX_IMAGE' and node.image and node.image.filepath.endswith('.png')]
            require(len(image_nodes)==1,'Exactly one native palette color node required')
            image_nodes[0].image=bpy.data.images.load(str(png),check_existing=True);image_nodes[0].image.colorspace_settings.name='sRGB'
        path=output/('conjure1-quarter-left-terminal-ao'+str(strength)+'.png');scene.render.filepath=str(path)
        print('RENDER '+path.name,flush=True);bpy.ops.render.render(write_still=True)
        rows.append({'file':str(path),'sha256':sha(path),'aoStrength':strength,'camera':camera_record,
            'literalOfflineRender':True,'interpolatedOrUpscaledExistingPixels':False,'clientAccepted':False})
    for path,pin in frozen.items():require(sha(path)==pin,'Input changed during closeups')
    receipt={'schemaVersion':2,'kind':'target-pilot-offline-terminal-material-detail','parentComparison':str(comparison_path),
      'parentComparisonSha256':sha(comparison_path),'patchReview':str(review_path),'patchReviewSha256':sha(review_path),
      'patch':patch,'camera':camera_record,'geometryProofs':geometry_proofs,'renders':rows,'frozenInputs':frozen,
      'sameParentLightsMaterialsGeometryPoseAcrossAo':True,'onlyChangedAoInput':'actual stage PLT palette3 color image',
      'normalStrength':1,'device':'CPU','samples':16,'threads':4,'aoSelected':None,'clientAccepted':False,
      'limitation':'Literal higher-resolution offline Cycles interpretation of the measured patch. Denoising/BRDF/filtering and driver/client shader differ.'}
    save(output/'detail.json',receipt);print(json.dumps({'receipt':str(output/'detail.json'),'sha256':sha(output/'detail.json')}),flush=True)

if __name__=='__main__':main()
