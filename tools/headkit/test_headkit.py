"""Synthetic regressions for reusable input, dispatch, mesh, palette and resume contracts."""
import copy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageDraw
from headkit import comfy
from headkit.common import write,read,pin,asset,manifest,source_version
from headkit.gltf import mesh,write_mesh,load,encode
from headkit.images import similarity,prepare,prepare_multiview
from headkit.field import GeneratedField
from headkit.mesh import topology,audit
from headkit.textures import surface,pad,tone_match
from headkit.palette import quantize
from headkit.runner import Runner


class Temporary(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
    def tearDown(self):self.directory.cleanup()
    def file(self,name,text='fixture'):
        path=self.root/name;path.write_text(text);return path
    def pair(self):
        image=Image.new('RGBA',(128,128));ImageDraw.Draw(image).ellipse((20,10,108,118),fill=(180,150,120,255))
        image.save(self.root/'clay.png');image.save(self.root/'detail.png')
        return {'landmarks':[{'name':n,'clay':p,'detail':p} for n,p in [('crown',[.5,.1]),('left',[.25,.5]),('chin',[.5,.9])]]}


class GraphTests(Temporary):
    def test_native_single_profile_has_one_image_and_exact_controls(self):
        g=comfy.compile_graph('geometry','pixal-single-v1',{'geometry':'clay.png'},'headkit/run',fov=42)
        self.assertEqual(g['298']['inputs']['image'],['364',0]);self.assertEqual(g['298']['inputs']['camera_angle_x'],42)
        self.assertEqual(g['319']['inputs']['unet_name'],'pixal3d_int8_convrot.safetensors')
        self.assertEqual([g[k]['inputs']['seed'] for k in ['3','18','23']],[56,242,42])
        self.assertEqual(g['18']['inputs']['cfg'],12);self.assertEqual(g['94']['inputs']['target_resolution'],1536)
    def test_multiview_roles_and_checkpoint_are_distinct(self):
        g=comfy.compile_graph('geometry','pixal-multiview-v1',{v:v+'.png' for v in ['front','left','back','right']},'headkit/run',fov=20)
        self.assertEqual(g['324']['class_type'],'Pixal3DMultiViewConditioning')
        self.assertEqual([g['324']['inputs'][v] for v in ['front','left','back','right']],[['364',0],['377',0],['378',0],['379',0]])
        self.assertEqual(g['319']['inputs']['unet_name'],'pixal3d_multiview_int8_convrot.safetensors')
        self.assertFalse(any(n['class_type']=='ImageCropToMask' for n in g.values()))
    def test_multiview_appearance_is_front_only_saved_shape(self):
        shape=pin(self.file('shape.npz'))
        g=comfy.compile_graph('appearance','pixal-multiview-v1',{'detail':'detail.png'},'headkit/run',fov=20,shape=shape)
        self.assertEqual(g['298']['inputs']['front'],['1001',0]);self.assertNotIn('left',g['298']['inputs'])
        self.assertEqual(g['970']['inputs'],shape);self.assertEqual(g['12']['inputs']['steps'],12);self.assertEqual(g['12']['inputs']['cfg'],1)
    def test_wrong_route_fov_or_missing_view_rejected(self):
        for profile,images,fov in [('pixal-single-v1',{'geometry':'x'},20),('pixal-multiview-v1',{'front':'x'},20),('pixal-multiview-v1',{v:'x' for v in ['front','left','back','right']},42)]:
            with self.assertRaises(ValueError):comfy.compile_graph('geometry',profile,images,'headkit/run',fov=fov)
    def test_hash_bound_minimal_20k_export(self):
        source=pin(self.file('mesh.glb'));g=comfy.compile_graph('export','pixal-single-v1',{},'headkit/run',source=source)
        self.assertEqual(g['1']['inputs'],source);self.assertEqual(g['241']['inputs']['sign_mode'],'udf')
        self.assertEqual(g['241']['inputs']['resolution'],768);self.assertEqual(g['186']['inputs']['target_face_count'],20000)
        self.assertNotIn('932',g);self.assertNotIn('286',g)
        Path(source['path']).write_text('changed')
        with self.assertRaises(ValueError):comfy.compile_graph('export','pixal-single-v1',{},'headkit/run',source=source)
    def test_template_manifest_has_no_operational_paths(self):
        for path in (Path(__file__).parent/'templates').glob('*.json'):
            content=path.read_text();self.assertNotIn('S:/',content);self.assertNotIn('F:/',content);self.assertNotIn('attempt74',content)

    def test_calibration_uses_shared_mask_and_linked_detector_images(self):
        g=comfy.compile_graph('calibrate','pixal-single-v1',{'geometry':'clay.png','detail':'detail.png','mask':'mask.png'},'headkit/run')
        self.assertEqual(g['8']['inputs']['image'],['6',0]);self.assertEqual(g['14']['inputs']['image'],['5',0])
        self.assertEqual(g['5']['inputs']['masks'],g['6']['inputs']['masks']);self.assertEqual(g['5']['inputs']['pad_factor'],1.1)
    def test_saved_shape_is_hash_checked_before_appearance(self):
        shape=pin(self.file('shape.npz'));Path(shape['path']).write_text('wrong')
        with self.assertRaises(ValueError):comfy.compile_graph('appearance','pixal-single-v1',{'detail':'detail.png'},'headkit/run',fov=42,shape=shape)


class GeometryApprovalTests(Temporary):
    def fixture(self):
        self.pair();raw=pin(self.file('raw.glb'));shape=pin(self.file('shape.npz'))
        data={'schemaVersion':1,'id':'geometry-review','inputs':{name:{'path':Path(row['path']).name,'sha256':row['sha256']}
              for name,row in {'detail':pin(self.root/'detail.png'),'geometryRaw':raw,'shape':shape}.items()},
              'camera':{'reviewed':True,'fovDegrees':42},'approval':{'inputReviewComplete':True}}
        source=pin(self.file('comfy.py'))
        adapter=self.root/'custom_nodes'/'srn_headkit';adapter.mkdir(parents=True)
        for code in (Path(__file__).parent/'comfy_nodes').glob('*.py'):(adapter/code.name).write_bytes(code.read_bytes())
        write(self.root/'bindings.json',{'schemaVersion':1,'toolsRoot':str(self.root),'comfyInput':str(self.root/'comfy-input'),
              'comfyCustomNodes':str(adapter.parent),'comfySources':[source]})
        return data
    def request(self,data):
        from headkit.__main__ import request_stage
        write(self.root/'manifest.json',data)
        with patch('headkit.__main__.comfy.compile_graph',return_value={}):
            return request_stage(self.root/'manifest.json',self.root/'bindings.json','appearance',self.root/'request.json')
    def approval(self,data):
        return {'decision':'approved','notes':'Inspected generated clay and accessories',
                'geometryRawSha256':data['inputs']['geometryRaw']['sha256'],'shapeSha256':data['inputs']['shape']['sha256']}
    def test_missing_rejected_and_stale_geometry_reviews_block_before_staging(self):
        data=self.fixture()
        cases=[None,dict(self.approval(data),decision='rejected'),dict(self.approval(data),geometryRawSha256='0'*64),
               dict(self.approval(data),shapeSha256='0'*64),dict(self.approval(data),notes=' ')]
        for review in cases:
            with self.subTest(review=review):
                if review is not None:data['approval']['generatedGeometry']=review
                with self.assertRaisesRegex(ValueError,'Approve generated clay'):self.request(data)
                self.assertFalse((self.root/'comfy-input').exists());self.assertFalse((self.root/'request.json').exists())
    def test_approved_geometry_and_saved_shape_are_frozen_in_request(self):
        data=self.fixture();data['approval']['generatedGeometry']=self.approval(data);result=self.request(data)
        self.assertEqual(result['expectedGeometry']['sha256'],data['inputs']['geometryRaw']['sha256'])
        self.assertIn(data['inputs']['shape']['sha256'],[row['sha256'] for row in result['inputs']])
        self.assertEqual(read(self.root/'request.json'),result)


class ImageTests(Temporary):
    def test_positive_similarity_is_scale_and_rotation_invariant(self):
        a=np.array([[0,0],[1,0],[.3,1]]);rotation=np.array([[0,-1],[1,0]]);b=a@rotation*2+[4,6]
        scale,r,t,error=similarity(a,b);self.assertAlmostEqual(scale,2);np.testing.assert_allclose(r,rotation,atol=1e-12)
        np.testing.assert_allclose(a@r*scale+t,b)
    def test_reflection_and_ambiguous_landmarks_rejected(self):
        with self.assertRaises(ValueError):similarity([[0,0],[1,0],[0,1]],[[0,0],[-1,0],[0,1]])
        with self.assertRaises(ValueError):similarity([[0,0]]*3,[[0,0]]*3)
    def test_paired_preparation_keeps_identical_silhouette(self):
        result=prepare(self.root/'clay.png',self.root/'detail.png',self.pair(),self.root/'prepared')
        self.assertEqual(result['silhouetteIoU'],1);self.assertTrue(result['manualReviewRequired'])
    def test_multiview_shared_scale_and_order_gates(self):
        align=self.pair();pairs={v:(self.root/'clay.png',self.root/'detail.png') for v in ['front','left','back','right']}
        config={'rigReviewed':True,'fovDegrees':20,'views':{v:{'azimuthDegrees':a,'orientationReviewed':True,'alignment':align,
            'crown':[.5,.1],'chin':[.5,.9],'skullCenter':[.5,.5]} for v,a in [('front',0),('left',90),('back',180),('right',270)]}}
        result=prepare_multiview(pairs,config,self.root/'good');self.assertFalse(result['independentCropping'])
        config['views']['left']['skullCenter']=[.6,.5]
        with self.assertRaisesRegex(ValueError,'drift'):prepare_multiview(pairs,config,self.root/'bad')


class MeshTests(Temporary):
    def tetra(self):
        vertices=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],np.float32)
        faces=np.array([[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
        return vertices,faces
    def test_topology_survives_uniform_scale_and_translation(self):
        p,f=self.tetra()
        for scale in (.01,10):self.assertTrue(topology(p*scale+[4,2,8],f)['closed'])
    def test_topology_is_physical_not_uv_index_topology(self):
        p,f=self.tetra();expanded=p[f].reshape(-1,3);indices=np.arange(12).reshape(-1,3)
        self.assertTrue(topology(expanded,indices)['closed']);self.assertFalse(topology(p,f[:-1])['closed'])
    def test_winding_and_duplicate_surfaces_are_not_closed(self):
        p,f=self.tetra();f[0]=f[0,::-1];self.assertFalse(topology(p,f)['closed'])
        p,f=self.tetra();self.assertFalse(topology(p,np.r_[f,f[:1]])['closed'])
    def test_glb_transport_preserves_ordered_corners_and_normals(self):
        p,f=self.tetra();uv=np.tile([[.1,.1],[.9,.1],[.1,.9]],(4,1,1));out=self.root/'mesh.glb'
        write_mesh(out,p,f,uv);loaded=mesh(out);np.testing.assert_array_equal(loaded['positions'][loaded['faces']],p[f]);np.testing.assert_array_equal(loaded['uv'],uv.astype(np.float32))
    def test_transformed_mesh_rejected(self):
        p,f=self.tetra();out=self.root/'mesh.glb';write_mesh(out,p,f);d,b,_=load(out.read_bytes());d['nodes'][0]['translation']=[1,0,0]
        with self.assertRaises(ValueError):load(encode(d,b))
    def test_uv_surface_uses_barycentric_positions_not_vertices(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],float);value={'positions':p,'faces':np.array([[0,1,2]]),'uv':np.array([[[0,0],[1,0],[0,1]]],float)}
        positions,ids,_=surface(value,16);self.assertEqual(ids[2,2],0);np.testing.assert_allclose(positions[2,2],[2.5/16,2.5/16,0])
    def test_padding_fills_only_unmapped_pixels_and_preserves_black(self):
        values=np.zeros((4,4,3),np.uint8);values[1,1]=[0,0,0];values[2,2]=[80,90,100];mask=np.zeros((4,4),bool);mask[1,1]=mask[2,2]=True
        result=pad(values,mask);np.testing.assert_array_equal(result[mask],values[mask]);np.testing.assert_array_equal(result[0,0],[0,0,0])


class UvBindingTests(Temporary):
    def fixture(self,directory):
        directory.mkdir(parents=True,exist_ok=True);module=directory/'xatlas.py';module.write_text('pinned fixture')
        return {'toolsRoot':str(self.root/'tools-bank'),'libraries':{'xatlas':{'directory':str(directory),'files':[pin(module)]}}}
    def test_uv_import_rejects_external_and_prefix_sibling_banks(self):
        from headkit.uv import unwrap
        for directory in (self.root/'other-worktree',self.root/'tools-bank-sibling'):
            with self.subTest(directory=directory):
                bindings=self.fixture(directory)
                with patch('headkit.common.importlib.import_module') as importer:
                    with self.assertRaisesRegex(ValueError,'declared durable tools bank'):unwrap({},bindings)
                    importer.assert_not_called()
    def test_uv_import_requires_current_dependency_hash(self):
        from headkit.uv import unwrap
        bindings=self.fixture(self.root/'tools-bank'/'libraries');Path(bindings['libraries']['xatlas']['files'][0]['path']).write_text('changed')
        with patch('headkit.common.importlib.import_module') as importer:
            with self.assertRaisesRegex(ValueError,'Stale file pin'):unwrap({},bindings)
            importer.assert_not_called()
    def test_uv_import_rejects_cached_module_from_another_installation(self):
        from headkit.uv import unwrap
        bindings=self.fixture(self.root/'tools-bank'/'libraries');unexpected=self.file('unexpected-xatlas.py')
        with patch('headkit.common.importlib.import_module',return_value=SimpleNamespace(__file__=str(unexpected))):
            with self.assertRaisesRegex(ValueError,'byte-bound module'):unwrap({},bindings)
    def test_uv_import_uses_the_pinned_tools_bank_module(self):
        from headkit.uv import unwrap
        bindings=self.fixture(self.root/'tools-bank'/'libraries');module=SimpleNamespace(__file__=bindings['libraries']['xatlas']['files'][0]['path'])
        with patch('headkit.uv.physical_fans',return_value=(np.zeros((3,3)),np.array([[0,1,2]]))), \
             patch('headkit.uv._pack',side_effect=RuntimeError('verified pack reached')) as pack, \
             patch('headkit.common.importlib.import_module',return_value=module) as importer:
            with self.assertRaisesRegex(RuntimeError,'verified pack reached'):unwrap({},bindings)
            importer.assert_called_once_with('xatlas');self.assertIs(pack.call_args.args[0],module)


class AppearanceTests(Temporary):
    def test_trilinear_interpolation_clamps_after_weighting(self):
        coords=np.array([[0,0,0],[1,0,0]]);attrs=np.array([[-.2]*6,[.8]*6])
        with self.assertRaises(ValueError):GeneratedField(coords,attrs,2)
        field=GeneratedField(coords,attrs,2,True);sample,fallback=field.sample([[0,-.25,-.25]])
        np.testing.assert_allclose(sample,.3,atol=1e-6);self.assertFalse(fallback[0])
    def test_nearest_field_fallback_is_counted(self):
        field=GeneratedField(np.array([[0,0,0]]),np.ones((1,6))*.2,4)
        values,fallback=field.sample([[.49,.49,.49]]);self.assertTrue(fallback[0]);np.testing.assert_allclose(values,.2)
    def test_duplicate_voxel_is_rejected(self):
        with self.assertRaises(ValueError):GeneratedField(np.zeros((2,3),int),np.ones((2,6)),4)
    def test_palette_excludes_transparent_and_255_preserving_opaque_black(self):
        rgb=np.zeros((1024,1024,3),np.uint8);labels=np.zeros((1024,1024),np.uint8);labels[:5]=8
        Image.fromarray(rgb).save(self.root/'rgb.png');Image.fromarray(labels).save(self.root/'labels.png')
        palette=np.full((1,256,4),255,np.uint8);palette[0,0]=[0,0,0,0];palette[0,1]=[0,0,0,255];palette[0,255]=[0,0,0,255]
        Image.fromarray(palette).save(self.root/'pal.png')
        result=quantize(self.root/'rgb.png',self.root/'labels.png',{'0':str(self.root/'pal.png'),'8':str(self.root/'pal.png')},{'0':0,'8':0},self.root/'quantized')
        shades=np.asarray(Image.open(result['shades']['path']));self.assertTrue(np.all(shades==1));self.assertEqual(set(result['layers']),{'0','8'})
    def test_unknown_ownership_is_not_assumed_hair(self):
        Image.new('RGB',(1024,1024)).save(self.root/'rgb.png');Image.new('L',(1024,1024),255).save(self.root/'mask.png')
        with self.assertRaisesRegex(ValueError,'ownership'):quantize(self.root/'rgb.png',self.root/'mask.png',{}, {},self.root/'bad')

    def test_tone_match_preserves_accessories_and_variation(self):
        color=np.full((8,8,3),120,np.uint8);color[:4,0]=80
        labels=np.zeros((8,8),np.uint8);labels[4:]=1;labels[:,7]=2
        Image.fromarray(color).save(self.root/'color.png');Image.fromarray(labels).save(self.root/'labels.png')
        Image.new('RGB',(8,8),(160,140,130)).save(self.root/'reference.png')
        config={k:{'reviewed':True,'referenceBoxes':[[0,0,1,1]]} for k in ('skin','hair')}
        tone_match(self.root/'color.png',self.root/'labels.png',self.root/'reference.png',config,self.root/'matched.png')
        result=np.asarray(Image.open(self.root/'matched.png'))
        np.testing.assert_array_equal(result[:,7],color[:,7]);self.assertLess(result[0,0,0],result[0,1,0])


class OwnershipModeTests(Temporary):
    def bad_masks(self):
        for mode in ('RGB','P','I;16'):
            image=Image.new(mode,(1024,1024),(1,0,0) if mode=='RGB' else 1)
            if mode=='P':image.putpalette([1,1,1]*256)
            path=self.root/(mode.replace(';','-')+'.png');image.save(path);yield path
    def test_quantization_rejects_non_label_image_modes(self):
        color=self.root/'color.png';Image.new('RGB',(1024,1024)).save(color)
        for mask in self.bad_masks():
            with self.subTest(mask=mask.name):
                with self.assertRaisesRegex(ValueError,'eight-bit L'):quantize(color,mask,{}, {},self.root/'quantized')
                self.assertFalse((self.root/'quantized').exists())
    def test_native_export_rejects_non_label_modes_before_geometry_work(self):
        from headkit.native import prepare
        shades=self.root/'shades.png';Image.new('L',(1024,1024)).save(shades)
        for mask in self.bad_masks():
            with self.subTest(mask=mask.name),patch('headkit.native.helpers') as helpers:
                with self.assertRaisesRegex(ValueError,'eight-bit L'):prepare('unused',shades,mask,{},'head',self.root/'export')
                helpers.assert_not_called();self.assertFalse((self.root/'export').exists())
    def test_tone_matching_rejects_non_label_image_modes(self):
        color=self.root/'color.png';Image.new('RGB',(1024,1024)).save(color)
        for mask in self.bad_masks():
            with self.subTest(mask=mask.name):
                with self.assertRaisesRegex(ValueError,'eight-bit L'):tone_match(color,mask,'unused',{},self.root/'tone.png')
    def test_projected_masks_reject_color_or_indexed_images(self):
        from headkit.palette import project_ownership
        embree=pin(self.file('embree.dll'))
        for mask in self.bad_masks():
            with self.subTest(mask=mask.name), \
                 patch('headkit.palette.mesh',return_value={'positions':np.zeros((3,3)), 'faces':np.array([[0,1,2]])}), \
                 patch('headkit.palette.surface',return_value=(np.zeros((1,1,3)),np.zeros((1,1),int),{})), \
                 patch('headkit.palette.EmbreeScene'):
                with self.assertRaisesRegex(ValueError,'eight-bit L'):
                    project_ownership('unused',[{'calibrationReviewed':True,'mask':str(mask)}],embree,self.root/'projected.png')
    def test_valid_labels_preserve_all_ten_channel_ids(self):
        labels=(np.arange(1024*1024).reshape(1024,1024)%10).astype(np.uint8)
        Image.fromarray(labels).save(self.root/'labels.png');Image.new('RGB',(1024,1024),(100,100,100)).save(self.root/'color.png')
        Image.new('RGBA',(256,1),(100,100,100,255)).save(self.root/'palette.png')
        palettes={str(i):str(self.root/'palette.png') for i in range(10)};rows={str(i):0 for i in range(10)}
        result=quantize(self.root/'color.png',self.root/'labels.png',palettes,rows,self.root/'quantized')
        with Image.open(result['ownership']['path']) as image:np.testing.assert_array_equal(np.asarray(image),labels)
        self.assertEqual(set(result['layers']),set(rows))


class CheckpointTests(Temporary):
    def transport(self):
        path=Path(__file__).parent/'comfy_nodes'/'transport.py';spec=importlib.util.spec_from_file_location('transport_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_lossless_checkpoint_and_bad_batch_rejection(self):
        transport=self.transport();arrays={'samples':np.ones((1,4,2,1),np.float32),'coords':np.array([[0,0,0,0],[0,1,0,0]],np.int32),'coord_counts':np.array([2],np.int32)}
        meta={'coord_resolution':32,'type':'trellis2','model_frame':'y_up'}
        path=self.root/'latent.npz';transport.write(path,arrays,meta);restored,metadata=transport.read(path)
        self.assertEqual(meta,metadata)
        for key in arrays:np.testing.assert_array_equal(arrays[key],restored[key])
        arrays['coords'][0,0]=1
        with self.assertRaises(ValueError):transport.validate(arrays,meta)
    def test_nonfinite_checkpoint_is_rejected(self):
        arrays={'samples':np.full((1,4,1,1),np.nan,np.float32),'coords':np.zeros((1,4),np.int32),'coord_counts':np.array([1],np.int32)}
        with self.assertRaises(ValueError):self.transport().validate(arrays,{'coord_resolution':32,'type':'trellis2','model_frame':'y_up'})


class FakeClient:
    def __init__(self,fail=False):self.fail=fail;self.posts=0
    def idle(self):return True
    def request(self,route,data=None):
        if route=='/object_info':return {'Example':{}}
        if route=='/prompt':
            self.posts+=1
            if self.fail:raise TimeoutError('lost acknowledgement')
            return {'prompt_id':'prompt-1','node_errors':{}}
        if route.startswith('/history'):return {}
        if route=='/queue':return {'queue_running':[],'queue_pending':[]}
        return {}


class LedgerTests(Temporary):
    def prepared(self):return {'token':'token-1','stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(self.file('input'))]}
    def test_ambiguous_submission_stays_counted_and_blocks_duplicates(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,74,'Reviewed retained ledger');request=self.prepared();client=FakeClient(True)
        with self.assertRaises(TimeoutError):comfy.submit(client,ledger,request,self.root/'job')
        self.assertEqual(read(ledger)['jobs'][0]['state'],'intent')
        with self.assertRaisesRegex(ValueError,'Reconcile'):comfy.submit(client,ledger,request,self.root/'another')
        self.assertEqual(client.posts,1)
    def test_generation_ceiling_and_queue_ownership(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,100,'Existing global count');client=FakeClient()
        with self.assertRaisesRegex(ValueError,'100'):comfy.submit(client,ledger,self.prepared(),self.root/'job')
        self.assertEqual(client.posts,0)
    def test_request_is_frozen_before_submission(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'New environment');request=self.prepared();Path(request['inputs'][0]['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Stale'):comfy.submit(FakeClient(),ledger,request,self.root/'job')
    def test_existing_lock_is_not_stolen(self):
        path=self.root/'ledger.json';Path(str(path)+'.lock').write_text('owner')
        with self.assertRaises(FileExistsError):
            with comfy.locked(path):pass
    def test_remote_endpoint_not_allowed(self):
        with self.assertRaises(ValueError):comfy.Client('https://untrusted.example')

    def test_failed_job_cannot_be_resubmitted_with_same_token(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,3,'Bound count');request=self.prepared();comfy.submit(FakeClient(),ledger,request,self.root/'job')
        state=read(ledger);state['jobs'][0]['state']='failed';write(ledger,state)
        with self.assertRaisesRegex(ValueError,'already submitted'):comfy.submit(FakeClient(),ledger,request,self.root/'retry')
    def test_collect_rejects_outputs_outside_owned_prefix(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,3,'Bound count');request=self.prepared();client=FakeClient()
        comfy.submit(client,ledger,request,self.root/'job')
        def reply(route,data=None):
            return {'prompt-1':{'status':{'status_str':'success'},'outputs':{'1':{'files':[{'filename':'escape.glb','subfolder':'other-run','type':'output'}]}}}}
        client.request=reply
        with self.assertRaisesRegex(ValueError,'outside'):comfy.collect(client,ledger,request['token'],self.root/'comfy-output',self.root/'job')


class CollectionReceiptTests(Temporary):
    def fixture(self):
        base=self.root/f'case-{len(list(self.root.glob("case-*")))}';base.mkdir()
        source=base/'input';source.write_text('frozen input');ledger=base/'ledger.json';job=base/'job';output=base/'comfy-output';token='collect-test'
        prepared={'token':token,'stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(source)]}
        comfy.initialize_ledger(ledger,0,'Reconciled fixture');client=FakeClient();comfy.submit(client,ledger,prepared,job)
        artifact=output/'headkit'/token/'mesh.glb';artifact.parent.mkdir(parents=True);artifact.write_bytes(b'exported fixture')
        history={'status':{'status_str':'success'},'outputs':{'1':{'files':[{'filename':'mesh.glb','subfolder':'headkit/'+token,'type':'output'}]}}}
        client.request=lambda route,data=None: {'devices':[]} if route=='/system_stats' else {'prompt-1':history}
        return client,ledger,token,output,job,artifact
    def test_repeat_collection_reuses_verified_receipt_without_server_or_writes(self):
        client,ledger,token,output,job,artifact=self.fixture();first=comfy.collect(client,ledger,token,output,job,wait=True)
        paths=[ledger,job/'history.json',job/'memory-samples.json',job/'collection.json'];before=[p.read_bytes() for p in paths]
        with patch.object(client,'request',side_effect=AssertionError('terminal collection must not poll')):
            self.assertEqual(comfy.collect(client,ledger,token,output,job),first)
        self.assertEqual([p.read_bytes() for p in paths],before);self.assertEqual(read(ledger)['jobs'][0]['collection'],pin(job/'collection.json'))
    def test_changed_terminal_evidence_or_output_cannot_be_reused(self):
        for name in ('history.json','memory-samples.json','collection.json','artifact'):
            with self.subTest(name=name):
                client,ledger,token,output,job,artifact=self.fixture();comfy.collect(client,ledger,token,output,job)
                target=artifact if name=='artifact' else job/name;target.write_bytes(b'changed')
                with patch.object(client,'request',side_effect=AssertionError('must not overwrite from server')):
                    with self.assertRaisesRegex(ValueError,'Stale file pin'):comfy.collect(client,ledger,token,output,job)
                self.assertEqual(target.read_bytes(),b'changed')
    def test_legacy_terminal_or_partial_evidence_is_preserved(self):
        client,ledger,token,output,job,_=self.fixture();comfy.collect(client,ledger,token,output,job)
        state=read(ledger);state['jobs'][0].pop('collection');write(ledger,state)
        before={p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}
        with patch.object(client,'request',side_effect=AssertionError('terminal must not poll')):
            with self.assertRaisesRegex(ValueError,'historical evidence'):comfy.collect(client,ledger,token,output,job)
        self.assertEqual(before,{p.name:p.read_bytes() for p in job.iterdir() if p.is_file()})
        state['jobs'][0]['state']='submitted';write(ledger,state)
        with self.assertRaises(FileExistsError):comfy.collect(client,ledger,token,output,job)
        self.assertEqual(before,{p.name:p.read_bytes() for p in job.iterdir() if p.is_file()})
    def test_terminal_collection_requires_its_original_directory(self):
        client,ledger,token,output,job,_=self.fixture();comfy.collect(client,ledger,token,output,job)
        with self.assertRaisesRegex(ValueError,'original collection directory'):comfy.collect(client,ledger,token,output,job.parent/'other')
    def test_failed_server_job_receipt_is_reused_without_repoll(self):
        client,ledger,token,output,job,_=self.fixture();client.request=lambda route,data=None: {'prompt-1':{'status':{'status_str':'error'},'outputs':{}}}
        first=comfy.collect(client,ledger,token,output,job);self.assertEqual(first['state'],'failed')
        with patch.object(client,'request',side_effect=AssertionError('failed job must not poll')):
            self.assertEqual(comfy.collect(client,ledger,token,output,job),first)
    def test_failed_validation_receipt_is_also_immutable(self):
        client,ledger,token,output,job,_=self.fixture();client.request=lambda route,data=None: {'prompt-1':{'status':{'status_str':'success'},'outputs':{}}}
        with self.assertRaisesRegex(ValueError,'No exported files'):comfy.collect(client,ledger,token,output,job)
        before=(job/'collection.json').read_bytes()
        with patch.object(client,'request',side_effect=AssertionError('failed terminal receipt must not poll')):
            result=comfy.collect(client,ledger,token,output,job)
        self.assertEqual(result['state'],'failed-validation');self.assertEqual((job/'collection.json').read_bytes(),before)


class ReleaseTests(Temporary):
    def fixture(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'Reconciled test ledger')
        request={'token':'release-race','stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(self.file('input'))]}
        return ledger,request
    def test_release_holds_submission_lock_through_idle_check_and_free(self):
        ledger,request=self.fixture();submitter=FakeClient();releaser=FakeClient();events=[]
        def blocked_submit():
            with self.assertRaises(FileExistsError):comfy.submit(submitter,ledger,request,self.root/'job')
            self.assertEqual(submitter.posts,0)
        def idle():events.append('idle');blocked_submit();return True
        def free(route,data=None):
            self.assertEqual(route,'/free');self.assertEqual(data,{'unload_models':True,'free_memory':True})
            events.append('free');blocked_submit();return {'freed':True}
        releaser.idle=idle;releaser.request=free
        self.assertEqual(comfy.release(releaser,ledger),{'freed':True});self.assertEqual(events,['idle','free'])
        self.assertFalse(Path(str(ledger)+'.lock').exists())
        comfy.submit(submitter,ledger,request,self.root/'job');self.assertEqual(submitter.posts,1)
    def test_submission_holds_same_lock_against_release(self):
        ledger,request=self.fixture();submitter=FakeClient();releaser=FakeClient()
        with patch.object(releaser,'request') as free:
            def idle():
                with self.assertRaises(FileExistsError):comfy.release(releaser,ledger)
                return True
            submitter.idle=idle;comfy.submit(submitter,ledger,request,self.root/'job');free.assert_not_called()
    def test_busy_queue_or_unreconciled_jobs_never_free_models(self):
        ledger,_=self.fixture();client=FakeClient()
        with patch.object(client,'request') as free:
            for state in ('intent','submitted','timed-out'):
                write(ledger,dict(read(ledger),jobs=[{'state':state}]))
                with self.assertRaisesRegex(ValueError,'Reconcile'):comfy.release(client,ledger)
            write(ledger,dict(read(ledger),jobs=[]))
            with patch.object(client,'idle',return_value=False):
                with self.assertRaisesRegex(ValueError,'not idle'):comfy.release(client,ledger)
            free.assert_not_called()
    def test_failed_release_drops_only_its_own_lock(self):
        ledger,_=self.fixture();client=FakeClient()
        with patch.object(client,'idle',side_effect=OSError('offline')):
            with self.assertRaises(OSError):comfy.release(client,ledger)
        self.assertFalse(Path(str(ledger)+'.lock').exists());self.assertEqual(comfy.release(client,ledger),{})


class NativeShadeTests(Temporary):
    def test_reserved_shade_255_is_rejected_before_export_work(self):
        from headkit.native import prepare
        shades=np.zeros((1024,1024),np.uint8);shades[400,500]=255;Image.fromarray(shades).save(self.root/'shades.png')
        with patch('headkit.native.helpers') as helpers:
            with self.assertRaisesRegex(ValueError,'Reserved PLT shade 255'):prepare('unused',self.root/'shades.png','unused',{},'head',self.root/'export')
            helpers.assert_not_called();self.assertFalse((self.root/'export').exists())
    def test_imported_shades_must_be_native_1k_grayscale_bytes(self):
        from headkit.native import prepare
        for index,image in enumerate((Image.new('L',(512,512)),Image.new('RGB',(1024,1024)),Image.new('I;16',(1024,1024),1000))):
            path=self.root/f'shades-{index}.png';image.save(path)
            with self.assertRaisesRegex(ValueError,'1K eight-bit grayscale'):prepare('unused',path,'unused',{},'head',self.root/'export')
    def test_valid_imported_extreme_shades_and_accessory_layers_survive_export(self):
        from headkit.native import prepare
        p,f=MeshTests.tetra(self);source=self.root/'mesh.glb';uv=np.tile([[.1,.1],[.9,.1],[.1,.9]],(4,1,1));write_mesh(source,p,f,uv)
        shades=np.zeros((1024,1024),np.uint8);shades[:512]=254;Image.fromarray(shades).save(self.root/'shades.png');Image.new('L',(1024,1024),8).save(self.root/'layers.png')
        fit={'matrix':np.eye(4).tolist(),'reviewed':True,'sourceSha256':pin(source)['sha256']}
        result=prepare(source,self.root/'shades.png',self.root/'layers.png',fit,'head',self.root/'export')
        payload=Path(result['plt']['path']).read_bytes();pixels=np.frombuffer(payload[24:],np.uint8).reshape(1024,1024,2)[::-1]
        np.testing.assert_array_equal(pixels[...,0],shades);self.assertTrue(np.all(pixels[...,1]==8))


class ReplayPinTests(Temporary):
    def fixture(self):
        paths={name:str(self.file(name+'.dat',name)) for name in ('source','shades','layers','binary','expectedPlt')}
        return dict(paths,id='retained',model='pfg0_head092',fit={},inputs=[pin(p) for p in paths.values()])
    def replay(self,config,output,changed=None):
        from headkit.replay import replay
        def prepare(source,shades,layers,fit,model,folder):
            folder.mkdir();plt=folder/'head.plt';plt.write_bytes(Path(config['expectedPlt']).read_bytes())
            expected=folder/'expected.npz';expected.write_bytes(b'fixture');return {'plt':pin(plt),'expected':pin(expected)}
        def native(*args):
            if changed:Path(config[changed]).write_text('changed during processing')
            return b'sanitized-native',{'verified':True}
        with ExitStack() as stack:
            mesh=stack.enter_context(patch('headkit.replay.mesh',return_value={'positions':[], 'faces':[]}))
            stack.enter_context(patch('headkit.replay.topology',return_value={'triangles':20000,'closed':True}))
            stack.enter_context(patch('headkit.replay.prepare',side_effect=prepare))
            stack.enter_context(patch('headkit.replay.audit_native',side_effect=native))
            result=replay(config,output)
            mesh.assert_called_once_with(str(Path(config['source']).resolve()))
            return result
    def test_missing_each_consumed_pin_fails_before_processing(self):
        from headkit.replay import replay
        for role in ('source','shades','layers','binary','expectedPlt'):
            config=self.fixture();config['inputs']=[p for p in config['inputs'] if Path(p['path']).resolve()!=Path(config[role]).resolve()]
            self.assertEqual(len(config['inputs']),4)
            with patch('headkit.replay.mesh') as mesh:
                with self.assertRaisesRegex(ValueError,'Missing replay input pin: '+role):replay(config,self.root/'missing')
                mesh.assert_not_called();self.assertFalse((self.root/'missing').exists())
    def test_unrelated_pins_do_not_qualify_consumed_artifacts(self):
        config=self.fixture();config['inputs']=[pin(self.file('unrelated'))]
        with self.assertRaisesRegex(ValueError,'Missing replay input pin'):self.replay(config,self.root/'unrelated-output')
    def test_resolved_role_pins_are_recorded_without_repinning_consumed_bytes(self):
        config=self.fixture();original=copy.deepcopy(config['inputs']);(self.root/'alias').mkdir()
        config['source']=str(self.root/'alias'/'..'/'source.dat')
        result=self.replay(config,self.root/'valid');self.assertEqual(read(self.root/'valid'/'replay.json'),result)
        self.assertEqual(set(result['consumedInputs']),{'source','shades','layers','binary','expectedPlt'})
        self.assertEqual(result['source'],original[0]);self.assertEqual(config['inputs'],original)
    def test_every_consumed_artifact_is_reverified_after_processing(self):
        for role in ('source','shades','layers','binary','expectedPlt'):
            config=self.fixture();output=self.root/('changed-'+role)
            with self.assertRaisesRegex(ValueError,'Stale file pin'):self.replay(config,output,changed=role)
            self.assertFalse((output/'replay.json').exists())
    def test_conflicting_duplicate_pins_and_stale_input_are_rejected(self):
        config=self.fixture();config['inputs'].append(dict(config['inputs'][0],sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'Conflicting replay input pins'):self.replay(config,self.root/'conflict')
        config=self.fixture();Path(config['binary']).write_text('changed before replay')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):self.replay(config,self.root/'stale')


class ResumeTests(Temporary):
    def fixture(self):
        alignment=self.pair();inputs={name:{'path':name+'.png','sha256':pin(self.root/(name+'.png'))['sha256']} for name in ['clay','detail']}
        data={'schemaVersion':1,'id':'synthetic','inputs':inputs,'alignment':alignment,'features':[{'name':'hair','placementReviewed':True}],
              'approval':{'referenceDesignReviewed':True}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',{'schemaVersion':1,'toolsRoot':str(self.root)})
        return Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
    def test_resume_reuses_only_verified_outputs(self):
        runner=self.fixture();first=runner.execute('prepare');self.assertFalse(first['reused']);self.assertTrue(runner.execute('prepare')['reused'])
        image=Path(first['result']['images']['geometry-pair.png']['path']);image.write_bytes(b'changed')
        self.assertIn('staleOrFailed',runner.status()['stages']['prepare']);self.assertFalse(runner.execute('prepare')['reused'])
    def test_two_failures_are_retained_and_block_third(self):
        runner=self.fixture()
        for _ in range(2):
            with self.assertRaises(ValueError):runner.execute('repair')
        with self.assertRaisesRegex(ValueError,'Two stage failures'):runner.execute('repair')
        self.assertEqual(len(list((self.root/'run'/'repair').glob('attempt-*/receipt.json'))),2)
    def test_serialization_failure_retains_a_failed_receipt(self):
        runner=self.fixture()
        with patch.object(runner,'_execute',return_value={'invalid':float('nan')}):
            with self.assertRaises(ValueError):runner.execute('prepare')
        self.assertEqual(read(self.root/'run'/'prepare'/'attempt-01'/'receipt.json')['state'],'failed')
    def test_portable_paths_reject_escape(self):
        with self.assertRaises(ValueError):asset(self.root/'manifest.json',{'path':'../escape','sha256':'0'*64})


class ImportedOwnershipTests(Temporary):
    def fixture(self,derived_uv=False):
        base=self.root/f'case-{len(list(self.root.glob("case-*")))}';base.mkdir()
        uv=base/'uv.glb';uv.write_text('frozen UV mesh');inputs={}
        for role,mode,size in [('ownership1k','L',1024),('ownership4k','L',4096),('runtimeColor','RGB',1024),('basecolor4k','RGB',4096),('runtimeShades','L',1024)]:
            path=base/(role+'.png');Image.new(mode,(size,size)).save(path);inputs[role]={'path':path.name,'sha256':pin(path)['sha256']}
        inputs['repairedMesh' if derived_uv else 'uvMesh']={'path':uv.name,'sha256':pin(uv)['sha256']}
        data={'schemaVersion':1,'id':'ownership-binding','inputs':inputs,'ownership':{'reviewed':True,'sourceSha256':pin(uv)['sha256']},
              'palette':{'inputs':{},'rows':{}},'tone':{},'fit':{'model':'head'}}
        write(base/'manifest.json',data);write(base/'bindings.json',{'schemaVersion':1,'toolsRoot':str(base)})
        return Runner(base/'manifest.json',base/'bindings.json',base/'run')
    def test_imported_masks_need_review_and_exact_mesh_hash(self):
        runner=self.fixture();valid=copy.deepcopy(runner.data['ownership'])
        for config in ({},dict(valid,reviewed=False),dict(valid,sourceSha256='0'*64)):
            runner.data['ownership']=config
            for role in ('ownership1k','ownership4k'):
                with self.subTest(config=config,role=role):
                    with self.assertRaisesRegex(ValueError,'ownership'):runner.input(role)
        runner.data['ownership']=valid
        for role in ('ownership1k','ownership4k'):
            self.assertEqual(Path(runner.input(role)),Path(asset(runner.manifest_path,runner.data['inputs'][role])['path']))
    def test_tone_palette_and_direct_export_do_not_consume_unreviewed_masks(self):
        runner=self.fixture();runner.data['ownership']['reviewed']=False
        for stage,target in [('tone','headkit.textures.tone_match'),('palette','headkit.palette.quantize'),('export','headkit.native.prepare')]:
            with self.subTest(stage=stage),patch(target) as operation:
                with self.assertRaisesRegex(ValueError,'Imported ownership'):runner._execute(stage,runner.run)
                operation.assert_not_called()
    def test_imported_masks_require_uv_dependency_when_not_imported(self):
        runner=self.fixture(derived_uv=True)
        with patch.object(runner,'_execute') as work:
            for stage in ('tone','palette'):
                with self.subTest(stage=stage):
                    with self.assertRaisesRegex(ValueError,'Stage not completed: unwrap'):runner.execute(stage)
            work.assert_not_called()
    def test_cached_palette_tracks_and_respects_unwrap_review(self):
        runner=self.fixture(derived_uv=True)
        def unwrap(stage,folder):
            target=folder/'uv.glb';target.write_text('frozen UV mesh');return {'mesh':pin(target)}
        with patch.object(runner,'_execute',side_effect=unwrap):runner.execute('unwrap')
        runner.review('unwrap','approved','Reviewed current UV mesh')
        with patch('headkit.palette.quantize',return_value={'fixture':True}):runner.execute('palette')
        runner.review('palette','approved','Reviewed matching ownership')
        receipt=read(runner.state['stages']['palette']['path']);self.assertIn('unwrap',receipt['dependencies'])
        runner.review('unwrap','rejected','UV review revoked')
        with patch('headkit.palette.quantize') as quantizer:
            with self.assertRaisesRegex(ValueError,'rejected'):runner.execute('palette')
            quantizer.assert_not_called()


class ReviewGateTests(Temporary):
    fixture=ResumeTests.fixture
    def completed(self,stage,folder):
        target=folder/'artifact.txt';target.write_text(stage);return {'artifact':pin(target)}
    def test_review_is_persisted_and_gates_every_processing_dependency(self):
        runner=self.fixture()
        with patch.object(runner,'_execute',side_effect=self.completed):
            for stage in ('repair','unwrap','bake','ownership','tone','palette','export','native'):
                runner.execute(stage)
                with self.assertRaisesRegex(ValueError,'pending'):runner.result(stage)
                runner.review(stage,'rejected','Visible defect')
                with self.assertRaisesRegex(ValueError,'rejected'):runner.result(stage)
                runner.review(stage,'approved','Inspected corrected output')
                self.assertIn('artifact',runner.result(stage))
        restored=Runner(runner.manifest_path,runner.bindings_path,runner.run)
        self.assertIn('artifact',restored.result('native'));self.assertEqual(restored.status()['stages']['native']['review'],'approved')
    def test_missing_or_rejected_review_blocks_work_not_just_result_reads(self):
        for decision in (None,'rejected'):
            with self.subTest(decision=decision):
                runner=self.fixture()
                with patch.object(runner,'_execute',side_effect=self.completed) as work:
                    runner.execute('repair')
                    if decision:runner.review('repair',decision,'Visible geometry defect')
                    with self.assertRaisesRegex(ValueError,'review'):runner.execute('unwrap')
                    self.assertEqual(work.call_count,1)
                # Each subcase uses its own run, retaining all its failed/complete evidence.
                self.root= self.root/('case-'+str(decision));self.root.mkdir()
    def test_rejecting_ancestor_blocks_cached_native_package_after_restart(self):
        runner=self.fixture()
        with patch.object(runner,'_execute',side_effect=self.completed):
            for stage in ('repair','unwrap','bake','ownership','tone','palette','export','native'):
                runner.execute(stage);runner.review(stage,'approved','Reviewed this stage')
        runner.review('repair','rejected','Found an accessory defect')
        restored=Runner(runner.manifest_path,runner.bindings_path,runner.run)
        with patch.object(restored,'_execute') as work:
            with self.assertRaisesRegex(ValueError,'rejected'):restored.execute('native')
            work.assert_not_called()
    def test_review_bound_to_old_receipt_or_modified_review_is_rejected(self):
        runner=self.fixture();runner.execute('prepare');review_pin=runner.review('prepare','approved','Reviewed input overlays')
        old=read(review_pin['path']);old['stageReceipt']['sha256']='0'*64
        write(review_pin['path'],old);runner.state['reviews']['prepare']=pin(review_pin['path'])
        with self.assertRaisesRegex(ValueError,'Stale visual review'):runner.result('prepare')
        runner.review('prepare','approved','Re-reviewed current receipt');current=runner.state['reviews']['prepare']
        Path(current['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):runner.result('prepare')


class ReviewImageTests(Temporary):
    def test_default_and_example_deliver_both_native_resolutions(self):
        from headkit.review_images import resolutions
        self.assertEqual(resolutions({}),[2048,1024])
        example=read(Path(__file__).parent/'examples'/'processing.json')
        self.assertEqual(resolutions(example['render']),[2048,1024])
        self.assertTrue(set(example['render']['mapInputs'].values())<=set(example['inputs']))
        with self.assertRaises(ValueError):resolutions({'sizes':[768]})
        with self.assertRaises(ValueError):resolutions({'sizes':[2048,1024],'size':768})
    def test_atlases_are_filtered_to_actual_1k_and_hashed(self):
        from headkit.review_images import atlas_sets
        # Alternating pixels average to midgray; this catches nearest-neighbor derivatives.
        values=np.tile(np.array([0,255],np.uint8),(2048,1024));Image.fromarray(values).save(self.root/'texture.png')
        sets,records=atlas_sets({'maps':{'roughness':str(self.root/'texture.png')}},self.root/'atlases',[2048,1024])
        self.assertEqual(len(records),2)
        with Image.open(sets[2048]['roughness']) as image:np.testing.assert_array_equal(np.asarray(image),values)
        with Image.open(sets[1024]['roughness']) as image:self.assertEqual(image.size,(1024,1024));self.assertTrue(np.all(np.asarray(image)==128))
        with self.assertRaisesRegex(ValueError,'no upsampling'):atlas_sets({'maps':{'roughness':sets[1024]['roughness']}},self.root/'bad',[2048])
    def test_sheets_preserve_native_view_pixels_and_reject_wrong_dimensions(self):
        from headkit.review_images import sheets
        records=[]
        for size in (2048,1024):
            image=Image.new('RGB',(size,size),(20,50,90));path=self.root/f'frame-{size}.png';image.save(path)
            records.append({'size':size,'mode':'clay','view':'front','image':pin(path)})
            (self.root/'sheets'/str(size)).mkdir(parents=True)
        result=sheets(records,self.root/'sheets',20000);self.assertEqual(len(result['sheets']),2)
        for row in result['sheets']:
            with Image.open(row['image']['path']) as image:
                self.assertEqual(image.size,(row['size'],row['size']+32));self.assertEqual(image.getpixel((0,32)),(20,50,90))
        records[0]['size']=1024
        with self.assertRaisesRegex(ValueError,'dimensions'):sheets(records,self.root/'sheets',20000)


if __name__=='__main__':unittest.main()
