"""Small CPU-only integration checks for preflight, baking and exact recovery."""
import sys
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import pin,read,write,require,verify
from tools.headkit.uv import raster_audit
from tools.itemkit import blender_worker as worker
from tools.itemkit.recovery import recovery_inputs,successful_pixel_hash
from tools.itemkit.transfer import linear_rgb
from tools.itemkit.preflight import region_hash


def main():
    out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(parents=True,exist_ok=False)
    worker.reset();bpy.ops.mesh.primitive_cube_add(size=.1);target=bpy.context.object;target.name='item_b'
    uv=target.data.uv_layers.active
    for i,poly in enumerate(target.data.polygons):
        x=.04+(i%3)*.32;y=.06+(i//3)*.48
        for loop,xy in zip(poly.loop_indices,[(x,y),(x+.25,y),(x+.25,y+.37),(x,y+.37)]):uv.data[loop].uv=xy
    attribute=target.data.attributes.new('itemkit_uv_region','INT','FACE');attribute.data.foreach_set('value',np.arange(6,dtype=np.int32))
    p,f=worker.arrays(target);regions=np.array([tri.polygon_index for tri in target.data.loop_triangles])
    target['itemkit_uv_region_hash']=region_hash(p[f],worker.uv_corners(target),regions)
    image=bpy.data.images.new('donor-colour',width=8,height=8)
    image.generated_color=(.2,.4,.6,1);image.filepath_raw=str(out/'donor.png');image.file_format='PNG';image.save()
    material=worker.flat_material('donor-material',(.2,.4,.6));node=material.node_tree.nodes.new('ShaderNodeTexImage')
    node.image=bpy.data.images.load(str(out/'donor.png'));material.node_tree.links.new(node.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    donor=worker.duplicate(target,'donor');donor.data.materials.clear();donor.data.materials.append(material)
    donor.hide_render=True
    source=out/'source.blend';bpy.ops.wm.save_as_mainfile(filepath=str(source))
    cfg={'scene':str(source),'family':{'family':'firearm-sling','firearm':{'subtype':'pistol'},'runtimeTextureSize':64,'bakeSize':64},
         'processing':{'joinY':[],'cageExtrusion':.001,'maxRayDistance':.02,'capColour':[.05,.05,.05],
                       'missCorrection':{'method':'nearest-finished-donor','maximumDistance':.003,'minimumNormalAlignment':.5}}}
    bake_out=out/'bake';bake_out.mkdir();baked=worker.bake(cfg,bake_out)
    require(baked['visibleMisses']==0 and baked['preflight']['passed'],'Small real bake failed')
    # Deliberately retain one known failed texel without rerunning the bake.
    bpy.ops.wm.open_mainfile(filepath=str(source));donor=bpy.data.objects['donor'];low=worker.joined_target(cfg)
    pixels=np.full((64,64,4),.25,np.float32);_,owners=raster_audit(worker.uv_corners(low),64)
    caps=np.zeros_like(owners,dtype=bool);misses=caps.copy();y,x=np.argwhere(owners>=0)[0]
    pixels[y,x]=[1,0,1,1];misses[y,x]=True
    retained=out/'retained';retained.mkdir();image=bpy.data.images.new('retained-linear',width=64,height=64,float_buffer=True)
    image.colorspace_settings.name='Non-Color';image.pixels.foreach_set(pixels.ravel());image.filepath_raw=str(retained/'bake-unpadded.exr');image.file_format='OPEN_EXR';image.save()
    proof=worker.save_bake_recovery(cfg,retained,donor,low,owners,caps,misses)
    # Use decoded retained EXR as authority (rather than assuming its encoding).
    decoded=bpy.data.images.load(proof['pixels']['path'],check_existing=False);decoded.colorspace_settings.name='Non-Color'
    before=worker.image_rgba(decoded);before_hash=successful_pixel_hash(before,misses)
    recovery_cfg={**cfg,'recoveryProof':str(retained/'bake-recovery.json'),
                  'inputs':[pin(retained/'bake-recovery.json')]+recovery_inputs(proof)}
    recovered=out/'recovered';recovered.mkdir();result=worker.recover_bake(recovery_cfg,recovered)
    values=np.load(result['linear']['path']);expected=linear_rgb(np.array([[.2,.4,.6]]))[0]
    require(np.max(np.abs(values[y,x]-expected))<.01,'Recovered donor colour is not linear')
    after=before.copy();after[...,:3]=values
    require(successful_pixel_hash(after,misses)==before_hash,'Successful retained texels changed')
    verify(recovery_cfg['inputs'])
    # Distance/facing failure must be found without a bake or overwrite.
    bpy.ops.wm.open_mainfile(filepath=str(source));donor=bpy.data.objects['donor'];donor.location.x=1
    low=worker.joined_target(cfg);failed=out/'failed-preflight';failed.mkdir()
    try:worker.transfer_preflight(cfg,failed,donor,low)
    except ValueError:pass
    else:raise AssertionError('Preflight accepted displaced donor')
    require('donor-distance-or-facing' in read(failed/'preflight.json')['blockers'],'Missing donor preflight diagnostic')
    bpy.ops.wm.open_mainfile(filepath=str(source));target=bpy.data.objects['item_b']
    target.data.uv_layers.active.data[0].uv.x+=.01
    try:worker.joined_target(cfg)
    except ValueError as exc:require('UV-region lineage' in str(exc),'Unexpected lineage error')
    else:raise AssertionError('Stale UV lineage accepted')
    write(out/'result.json',{'passed':True,'realBakeSize':64,'reusedBake':True,'correctedTexels':1,
          'successfulPixelsUnchanged':True,'linearColourVerified':True,'displacedDonorBlockedBeforeBake':True,'staleUvLineageRejected':True,
          'threads':4,'gpuUsed':False},fresh=True)


if __name__=='__main__':main()
