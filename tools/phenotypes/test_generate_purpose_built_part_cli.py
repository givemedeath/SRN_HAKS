"""Prevent accidental preparation of the wrong part without network activity."""
import contextlib
import copy
import json
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import generate_purpose_built_part as generator


class ExplicitPartConfiguration(unittest.TestCase):
    def test_prepare_without_configuration_fails_before_service_access(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views']), \
                patch.object(generator, 'prepare') as prepare, \
                contextlib.redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit) as exit_status:
                generator.main()
        self.assertEqual(exit_status.exception.code, 2)
        self.assertIn('explicit --config', error.getvalue())
        prepare.assert_not_called()

    def test_explicit_configuration_reaches_prepare_unchanged(self):
        with patch.object(sys, 'argv', ['generator', 'prepare', '--output', 'fresh',
                                      '--views-dir', 'views', '--config', 'shin.json']), \
                patch.object(generator, 'prepare') as prepare:
            generator.main()
        self.assertEqual(prepare.call_args.args[0].config, Path('shin.json'))

    def test_collection_uses_receipts_without_a_new_configuration(self):
        with patch.object(sys, 'argv', ['generator', 'status', '--output', 'existing']), \
                patch.object(generator, 'status') as status:
            generator.main()
        self.assertIsNone(status.call_args.args[0].config)


    def test_uncertain_submission_recovers_only_exact_persisted_attempt(self):
        api={'1':{'class_type':'LoadImage','inputs':{'image':'approved.png'}}}
        receipt={'clientId':'female-attempt'};entry=[4,'prompt-a',api,{'client_id':'female-attempt'},['1']]
        self.assertEqual(generator.recover_prompt_id(receipt,api,{'queue_running':[entry]},{}),'prompt-a')
        self.assertEqual(generator.recover_prompt_id(receipt,api,{}, {'prompt-a':{'prompt':entry}}),'prompt-a')
        other=[5,'prompt-b',api,{'client_id':'female-attempt'},['1']]
        with self.assertRaisesRegex(RuntimeError,'exactly one'):
            generator.recover_prompt_id(receipt,api,{'queue_pending':[entry,other]}, {})
        with self.assertRaisesRegex(RuntimeError,'Do not resubmit'):
            generator.recover_prompt_id({'clientId':'another'},api,{'queue_pending':[entry]}, {})
        with self.assertRaises(RuntimeError):generator.recover_prompt_id(receipt,{'changed':{}},{'queue_running':[entry]}, {})


class IndependentTextureConditioning(unittest.TestCase):
    def config(self):
        return {'schemaVersion':1,'projection':'orthographic-six-view',
                'viewOrder':list(generator.ORTHO_VIEW_ORDER),'orthoSpan':1.1,
                'textureViewOrder':list(generator.VIEW_ORDER)}

    def schemas(self):
        return {
            'SRNOrthographicMultiViewConditioning':{'input':{
                'required':{'clip_vision_model':['CLIP_VISION',{}],'ortho_span':['FLOAT',{}],'front':['IMAGE',{}]},
                'optional':{name:['IMAGE',{}] for name in generator.ORTHO_VIEW_ORDER[1:]}},
                'output':['CONDITIONING','CONDITIONING'],'output_is_list':[False,False]},
            'Trellis2TextureStage':{'input':{'required':{name:[kind,{}] for name,kind in
                [('positive','CONDITIONING'),('negative','CONDITIONING'),('shape_latent','LATENT')]}},
                'output':['CONDITIONING','CONDITIONING','LATENT'],'output_is_list':[False,False,False]},
            'RemeshMesh':{'input':{'required':{'mesh':['MESH',{}], 'resolution':['INT',{}],
                'sign_mode':['COMFY_DYNAMICCOMBO',{'options':[{'key':'udf','inputs':{'required':{}}}]}]}}}}

    def graph(self):
        graph={'15':{'class_type':'CLIPVisionLoader','inputs':{'clip_name':'dino_fixture.safetensors'}},
            '324':{'class_type':'SRNOrthographicMultiViewConditioning','inputs':{
                'clip_vision_model':['15',0],'ortho_span':1.1,**{name:[str(1000+i),0] for i,name in enumerate(generator.ORTHO_VIEW_ORDER)}}}}
        for i,name in enumerate(generator.ORTHO_VIEW_ORDER):
            graph[str(1000+i)]={'class_type':'LoadImage','inputs':{'image':'__UPLOAD_'+name.upper()+'__'}}
        nodes={
            '87':('EmptyTrellis2LatentStructure',{'batch_size':1}),
            '3':('KSampler',{'positive':['324',0],'negative':['324',1],'latent_image':['87',0],'seed':61}),
            '119':('VaeDecodeStructureTrellis2',{'samples':['3',0]}),
            '91':('Trellis2ShapeStage',{'positive':['324',0],'negative':['324',1],'voxel':['119',0]}),
            '18':('KSampler',{'positive':['91',0],'negative':['91',1],'latent_image':['91',2],'seed':47}),
            '94':('Trellis2UpsampleStage',{'positive':['91',0],'negative':['91',1],'shape_latent':['18',0],'target_resolution':1024}),
            '23':('KSampler',{'positive':['94',0],'negative':['94',1],'latent_image':['94',2],'seed':47}),
            '98':('Trellis2TextureStage',{'positive':['94',0],'negative':['94',1],'shape_latent':['23',0]}),
            '12':('KSampler',{'positive':['98',0],'negative':['98',1],'latent_image':['98',2],'seed':48}),
            '92':('VaeDecodeShapeTrellis',{'samples':['23',0]}),
            '93':('VaeDecodeTextureTrellis',{'samples':['12',0],'shape_subdivides':['92',1]}),
            '202':('MeshPass',{'mesh':['92',0]}),
            '241':('RemeshMesh',{'mesh':['202',0],'resolution':384,'sign_mode':'udf'}),
            '186':('DecimateMesh',{'mesh':['241',0],'target_face_count':50000}),
            '196':('UnwrapMesh',{'mesh':['186',0]}),
            '288':('PrimitiveInt',{'value':2048}),
            '147':('BakeTextureFromVoxel',{'mesh':['196',0],'voxel_colors':['93',0],'reference_mesh':['241',0],'texture_size':['288',0]}),
            '224':('BakeNormalMapFromMesh',{'low_poly':['196',0],'high_poly':['241',0],'resolution':2048}),
            '210':('ApplyTextureToMesh',{'mesh':['196',0],'base_color':['147',0],'normal_map':['224',0]}),
            '282':('MeshToFile3D',{'mesh':['186',0]}),
            '285':('MeshToFile3D',{'mesh':['210',0]}),
            '372':('Save3DAdvanced',{'model_3d':['285',0],'filename_prefix':'fixture'})}
        graph.update({key:{'class_type':kind,'inputs':inputs} for key,(kind,inputs) in nodes.items()})
        return graph

    def test_omitted_option_is_byte_exact_noop(self):
        graph=self.graph();config=self.config();del config['textureViewOrder']
        before=json.dumps(graph,indent=2).encode()
        self.assertIsNone(generator.configure_texture_conditioning(graph,config,{}))
        self.assertEqual(json.dumps(graph,indent=2).encode(),before)
        self.assertEqual(generator.texture_record_fields(None),{})

    def test_split_preserves_every_shape_and_geometry_node_exactly(self):
        graph=self.graph();before=copy.deepcopy(graph)
        metadata=generator.configure_texture_conditioning(graph,self.config(),self.schemas())
        self.assertEqual(graph['98']['inputs']['shape_latent'],['23',0])
        self.assertEqual(graph['98']['inputs']['positive'],['1016',0])
        self.assertEqual(graph['98']['inputs']['negative'],['1016',1])
        texture=graph['1016']['inputs']
        self.assertEqual(list(texture),['clip_vision_model','ortho_span',*generator.VIEW_ORDER])
        self.assertNotIn('top',texture);self.assertNotIn('bottom',texture)
        self.assertEqual(metadata['viewOrbit']['back'],{'azimuth':180,'elevation':0})
        restored=copy.deepcopy(graph);restored.pop('1016');restored['98']=before['98']
        self.assertEqual(json.dumps(restored,indent=2).encode(),json.dumps(before,indent=2).encode())
        self.assertEqual(graph['324'],before['324'])
        for name in generator.VIEW_ORDER:
            self.assertEqual(texture[name],before['324']['inputs'][name])

    def test_option_rejects_noncanonical_sets_and_types_without_mutation(self):
        for value in (None,True,'front,left,back,right',tuple(generator.VIEW_ORDER),[],
                      ['left','front','back','right'],['front','left','back','back'],list(generator.ORTHO_VIEW_ORDER)):
            with self.subTest(value=value):
                graph=self.graph();before=copy.deepcopy(graph);config=self.config();config['textureViewOrder']=value
                with self.assertRaisesRegex(RuntimeError,'textureViewOrder'):
                    generator.configure_texture_conditioning(graph,config,self.schemas())
                self.assertEqual(graph,before)
        for key,value in [('schemaVersion',True),('schemaVersion',2),('projection','perspective-four-view'),
                          ('viewOrder',list(generator.VIEW_ORDER)),('orthoSpan',True),('orthoSpan','1.1'),
                          ('orthoSpan',float('nan')),('orthoSpan',float('inf'))]:
            with self.subTest(key=key,value=value):
                config=self.config();config[key]=value
                with self.assertRaises(RuntimeError):generator.configure_texture_conditioning(self.graph(),config,self.schemas())

    def test_stale_schema_types_and_outputs_fail_before_graph_mutation(self):
        for change in ('missing-camera','camera-type','texture-type','output','required-top','output-type'):
            with self.subTest(change=change):
                schemas=self.schemas();graph=self.graph();before=copy.deepcopy(graph)
                camera=schemas['SRNOrthographicMultiViewConditioning']
                if change=='missing-camera':del camera['input']['optional']['bottom']
                if change=='camera-type':camera['input']['required']['front'][0]='LATENT'
                if change=='texture-type':schemas['Trellis2TextureStage']['input']['required']['shape_latent'][0]='IMAGE'
                if change=='output':camera['output']=['CONDITIONING']
                if change=='output-type':camera['output_is_list']=[0,0]
                if change=='required-top':camera['input']['required']['top']=camera['input']['optional'].pop('top')
                with self.assertRaisesRegex(RuntimeError,'schema'):
                    generator.configure_texture_conditioning(graph,self.config(),schemas)
                self.assertEqual(graph,before)

    def test_wrong_shape_or_texture_edges_and_reserved_id_fail_closed(self):
        for key,name,value in [('91','positive',['98',0]),('23','latent_image',['91',2]),
                               ('98','shape_latent',['18',0]),('98','positive',['23',0]),
                               ('324','left',['1001',False]),('324','ortho_span',True)]:
            with self.subTest(key=key,name=name):
                graph=self.graph();graph[key]['inputs'][name]=value;before=copy.deepcopy(graph)
                with self.assertRaisesRegex(RuntimeError,'mismatch'):
                    generator.configure_texture_conditioning(graph,self.config(),self.schemas())
                self.assertEqual(graph,before)
        graph=self.graph();graph['1016']={'class_type':'LoadImage','inputs':{'image':'existing.png'}}
        with self.assertRaisesRegex(RuntimeError,'collides'):
            generator.configure_texture_conditioning(graph,self.config(),self.schemas())

    def test_independent_conditioner_cannot_leak_into_shape(self):
        graph=self.graph();generator.configure_texture_conditioning(graph,self.config(),self.schemas())
        graph['87']['inputs']['unexpected_conditioning']=['1016',0]
        with self.assertRaisesRegex(RuntimeError,'another graph branch'):
            generator.texture_graph_metadata(graph,self.config(),self.schemas(),split=True)

    def prepare_fixture(self, folder, split=True):
        root=Path(folder);config=self.config()
        if not split:del config['textureViewOrder']
        deps={}
        for name in ('adapter','model','nodes'):
            path=root/(name+'.py');path.write_text('# source fixture '+name);deps[str(path)]=generator.digest(path)
        config.update({'name':'fixture','part':'chest','service':'http://fixture.invalid','workflow':'fixture.json',
            'conditioningDependencies':deps,'imageSize':1024,'shapeResolution':1024,'textureSize':2048,
            'normalBakeSize':2048,'masterTriangleBudget':50000,'remesh':{'sign_mode':'udf','resolution':384},
            'compactBakeReference':True,'seeds':{'structure':61,'shape':47,'texture':48},
            'postFitNormalStrength':1,'retainRawMaster':True})
        config_path=root/'source-config.json';config_path.write_text(json.dumps(config));views=root/'views';views.mkdir()
        for name in generator.ORTHO_VIEW_ORDER:Image.new('RGB',(1024,1024),'black').save(views/(name+'.png'))
        schemas=self.schemas();graph=self.graph();graph['324']={'class_type':'Pixal3DMultiViewConditioning','inputs':{'clip_vision_model':['15',0],'fov':20}}
        service=Mock();service.base='http://fixture.invalid'
        def request(path,value=None):
            if path.startswith('/userdata/'):return {'fixtureWorkflow':True}
            if path=='/object_info':return schemas
            if path=='/queue':return {'queue_running':[],'queue_pending':[]}
            raise AssertionError('Unexpected service request '+path)
        service.request.side_effect=request
        args=SimpleNamespace(output=root/'prepared',config=config_path,views_dir=views,service=None)
        with patch.object(generator,'Comfy',return_value=service),patch.object(generator,'compile_prompt',return_value=graph),contextlib.redirect_stdout(io.StringIO()):
            generator.prepare(args)
        return args.output,generator.read_json(args.output/'preparation.json'),service

    def test_prepare_freezes_independent_cameras_and_stale_provenance_rejects(self):
        with tempfile.TemporaryDirectory() as folder:
            root,record,service=self.prepare_fixture(folder)
            self.assertEqual(record['viewOrder'],list(generator.ORTHO_VIEW_ORDER))
            self.assertEqual(record['textureViewOrder'],list(generator.VIEW_ORDER))
            self.assertEqual(record['textureViewOrbit']['right'],{'azimuth':270,'elevation':0})
            self.assertEqual(generator.verify_record(root),record)
            service.upload.assert_not_called()
            bad=copy.deepcopy(record);bad['textureViewOrbit']['front']['elevation']=90
            generator.save_json(root/'preparation.json',bad)
            with self.assertRaisesRegex(RuntimeError,'provenance differs'):
                generator.verify_record(root)
            bad=copy.deepcopy(record);bad.pop('textureConditioning');generator.save_json(root/'preparation.json',bad)
            with self.assertRaisesRegex(RuntimeError,'Missing/malformed'):
                generator.verify_record(root)

    def test_prepare_without_option_keeps_legacy_graph_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root,record,_=self.prepare_fixture(folder,split=False)
            api=generator.read_json(root/'workflow-api-template.json')
            self.assertNotIn('1016',api)
            self.assertEqual(api['98']['inputs']['positive'],['94',0])
            self.assertFalse(any(key in record for key in generator.TEXTURE_RECORD_FIELDS))
            self.assertEqual(generator.verify_record(root),record)

    def test_uploaded_api_and_submission_camera_binding_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root,record,_=self.prepare_fixture(folder)
            api=generator.read_json(root/'workflow-api-template.json')
            for index,name in enumerate(generator.ORTHO_VIEW_ORDER):api[str(1000+index)]['inputs']['image']='uploads/'+name+'.png'
            generator.verify_texture_api(root,record,api)
            generator.save_json(root/'workflow-api.json',api)
            receipt={'preparationSha256':generator.digest(root/'preparation.json'),
                     'apiSha256':generator.digest(root/'workflow-api.json'),**generator.texture_record_fields(record['textureConditioning'])}
            generator.verify_texture_submission(record,receipt)
            receipt['textureViewOrder']=['front','left']
            generator.save_json(root/'generation.json',receipt)
            with patch.object(generator,'Comfy') as service:
                with self.assertRaisesRegex(RuntimeError,'Submission separate texture'):
                    generator.status(SimpleNamespace(output=root,service=None))
                service.assert_not_called()
            api['1016']['inputs']['right']=['1004',0]
            with self.assertRaisesRegex(RuntimeError,'conditioner graph differs'):
                generator.verify_texture_api(root,record,api)

    def test_legacy_receipts_reject_unrequested_texture_provenance(self):
        generator.verify_texture_submission({}, {'schemaVersion':1})
        with self.assertRaisesRegex(RuntimeError,'Submission separate texture'):
            generator.verify_texture_submission({}, {'textureViewOrder':list(generator.VIEW_ORDER)})


if __name__ == '__main__':
    unittest.main()
