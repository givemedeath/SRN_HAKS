"""Synthetic regressions for reusable input, dispatch, mesh, palette and resume contracts."""
import copy
from contextlib import ExitStack
import os
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import tempfile
import sys
import time
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageDraw
from headkit import comfy
from headkit.common import write,read,pin,asset,manifest,source_version,digest
from headkit.gltf import mesh,write_mesh,load,encode
from headkit.images import similarity,prepare,prepare_multiview
from headkit.field import GeneratedField,load_generated_field
from headkit.mesh import topology,audit
from headkit.textures import surface,pad,tone_match,bake
from headkit.palette import quantize
from headkit.runner import Runner


class Temporary(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
    def tearDown(self):self.directory.cleanup()
    def file(self,name,text='fixture'):
        path=self.root/name;path.write_text(text);return path
    def inventory(self):
        from headkit.source_inventory import freeze_sources
        root=self.root/f'comfy-{len(list(self.root.glob("comfy-*")))}';root.mkdir()
        for relative in ['main.py','execution.py','nodes.py','server.py','folder_paths.py','comfy/model.py',
                         'comfy_extras/nodes_trellis2.py','custom_nodes/plugin/flexgemm.py','custom_nodes/plugin/kernel.pyd']:
            path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture implementation')
        rows=[pin(p) for p in sorted(root.rglob('*')) if p.is_file()]
        return freeze_sources({'comfyRoot':str(root),'comfyCustomNodes':str(root/'custom_nodes'),'comfySources':rows})
    def comfy_runtime_identity(self,source_inventory):
        if not isinstance(source_inventory,dict):
            from headkit.source_inventory import freeze_sources
            source_inventory=freeze_sources({'comfyRoot':source_inventory[0],
                'comfyCustomNodes':str(Path(source_inventory[0])/'custom_nodes'),
                'comfySources':[pin(path) for path in sorted(Path(source_inventory[0]).rglob('*')) if path.is_file()]})
        executable=pin(sys.executable);torch_file=self.root/'comfy-runtime'/'torch'/'_C.pyd'
        torch_file.parent.mkdir(parents=True,exist_ok=True);torch_file.write_bytes(b'torch fixture bytes')
        torch_pin=pin(torch_file);files=sorted([executable,torch_pin],key=lambda row:row['path'].casefold())
        configuration=self.root/'controlled-startup.json'
        if not configuration.exists():write(configuration,{'fixture':'controlled startup'})
        identity={'schemaVersion':3,
                  'python':{'path':executable['path'],'sha256':executable['sha256'],'version':'3.12 fixture',
                            'implementation':'cpython','cacheTag':'cpython-312','prefix':str(self.root),'basePrefix':str(self.root)},
                  'torch':{'path':torch_pin['path'],'sha256':torch_pin['sha256'],'version':'2.7 fixture',
                           'cuda':'12.8','hip':None,'cudnn':8900},
                  'coveredSourceRoots':[str(Path(source_inventory['core']).resolve())],
                  'roots':[str(self.root.resolve())],'files':files,
                  'comfySourceInventory':source_inventory,'session':{'id':'a'*32,'pid':123,'configuration':pin(configuration),'settingsSha256':'b'*64}}
        identity['fingerprint']=digest(identity)
        return identity
    def freeze_request(self,prepared):
        inventory=self.inventory();runtime=self.comfy_runtime_identity(inventory)
        prepared['comfySourceInventory']=inventory;prepared['comfyRuntimeIdentity']=runtime
        prepared['inputs']+=inventory['files']+runtime['files']+[runtime['session']['configuration']];return prepared
    def runtime_identity(self):
        return {'toolchain':pin(self.file('runtime-toolchain.json')),
                'migrationReceipt':pin(self.file('runtime-migration.json')),'python':pin(sys.executable),
                'toolsRoot':str(self.root.resolve())}
    def bindings_data(self, *, tools_root=None, **values):
        tools_root=Path(tools_root or self.root)
        directory=tools_root/'headkit-runtime'/'site-packages'
        files=[]
        for name in ('numpy','PIL','scipy'):
            package=directory/name;package.mkdir(parents=True,exist_ok=True)
            module=package/'__init__.py';module.write_text('# pinned test fixture: '+name)
            files.append(pin(module))
        data={'schemaVersion':1,'toolsRoot':str(tools_root),
              'pythonPackages':{'directory':str(directory),'files':files}}
        data.update(values)
        return data
    def bind_dispatch(self,prepared,endpoint='http://127.0.0.1:8188'):
        bindings=self.root/'dispatch-bindings.json'
        if not bindings.exists():bindings.write_text('{}')
        identity=self.runtime_identity();binding_pin=pin(bindings)
        prepared.update(runtimeIdentity=identity,bindings=binding_pin,comfyEndpoint=endpoint)
        if 'comfyRuntimeIdentity' not in prepared:
            prepared['comfyRuntimeIdentity']=self.comfy_runtime_identity(prepared['comfySourceInventory'])
        runtime_files=[] if prepared.get('runtimeVerification')=='server-owned' else prepared['comfyRuntimeIdentity']['files']
        for row in runtime_files+[prepared['comfyRuntimeIdentity']['session']['configuration']]:
            if row not in prepared['inputs']:prepared['inputs'].append(row)
        if binding_pin not in prepared['inputs']:prepared['inputs'].append(binding_pin)
        prepared['inputs'].extend(row for row in (identity['toolchain'],identity['migrationReceipt'],identity['python']) if row not in prepared['inputs'])
        return identity,bindings
    def submit(self,client,ledger,prepared,output,*,runtime_identity=None,bindings_path=None):
        if bindings_path is None:
            runtime_identity,bindings_path=self.bind_dispatch(prepared,client.url)
            client.server_runtime=prepared['comfyRuntimeIdentity']
        return comfy.submit(client,ledger,prepared,output,runtime_identity=runtime_identity,bindings_path=bindings_path)
    def pair(self):
        image=Image.new('RGBA',(128,128));ImageDraw.Draw(image).ellipse((20,10,108,118),fill=(180,150,120,255))
        image.save(self.root/'clay.png');image.save(self.root/'detail.png')
        return {'landmarks':[{'name':n,'clay':p,'detail':p} for n,p in [('crown',[.5,.1]),('left',[.25,.5]),('chin',[.5,.9])]]}


class ClientTransportTests(unittest.TestCase):
    def test_verification_endpoints_have_bounded_byte_read_timeout(self):
        client = comfy.Client('http://127.0.0.1:8188')
        for route, expected in [('/headkit/runtime-identity', 300),
                                ('/headkit/verify-loader-models', 300),
                                ('/queue', 30), ('/prompt', 30)]:
            with self.subTest(route=route), patch.object(comfy.urllib.request, 'urlopen') as opened, \
                    patch.object(comfy.json, 'load', return_value={'verified': True}):
                self.assertEqual(client.request(route), {'verified': True})
                self.assertEqual(opened.call_args.kwargs['timeout'], expected)

    def test_verification_timeout_propagates_without_retry_or_dispatch(self):
        client = comfy.Client('http://127.0.0.1:8188')
        with patch.object(comfy.urllib.request, 'urlopen', side_effect=TimeoutError('verification timeout')) as opened:
            with self.assertRaisesRegex(TimeoutError, 'verification timeout'):
                client.request('/headkit/verify-loader-models', {'models': []})
            self.assertEqual(opened.call_count, 1)
            self.assertEqual(opened.call_args.args[0].full_url,
                             'http://127.0.0.1:8188/headkit/verify-loader-models')


class GraphTests(Temporary):
    def test_native_single_profile_has_one_image_and_exact_controls(self):
        g=comfy.compile_graph('geometry','pixal-single-v1',{'geometry':'clay.png'},'headkit/run',fov=42)
        self.assertEqual(g['298']['inputs']['image'],['364',0]);self.assertEqual(g['298']['inputs']['camera_angle_x'],42)
        self.assertEqual(g['319']['inputs']['unet_name'],'pixal3d_int8_convrot.safetensors')
        self.assertEqual([g[k]['inputs']['seed'] for k in ['3','18','23']],[56,242,42])
        self.assertEqual(g['18']['inputs']['cfg'],12);self.assertEqual(g['94']['inputs']['target_resolution'],1536)
    def test_multiview_roles_and_checkpoint_are_distinct(self):
        g=comfy.compile_graph('geometry','pixal-multiview-v1',{'geometry'+v:v+'.png' for v in ['Front','Left','Back','Right']},'headkit/run',fov=20)
        self.assertEqual(g['324']['class_type'],'Pixal3DMultiViewConditioning')
        self.assertEqual([g['324']['inputs'][v] for v in ['front','left','back','right']],[['364',0],['377',0],['378',0],['379',0]])
        self.assertEqual([g[n]['inputs']['image'] for n in ['364','377','378','379']],['Front.png','Left.png','Back.png','Right.png'])
        self.assertEqual(g['319']['inputs']['unet_name'],'pixal3d_multiview_int8_convrot.safetensors')
        self.assertFalse(any(n['class_type']=='ImageCropToMask' for n in g.values()))
    def test_multiview_appearance_uses_four_detailed_views_on_saved_shape(self):
        shape=pin(self.file('shape.npz'))
        g=comfy.compile_graph('appearance','pixal-multiview-v1',{'detail'+v:v+'-detail.png' for v in ['Front','Left','Back','Right']},'headkit/run',fov=20,shape=shape)
        self.assertEqual([g['298']['inputs'][v] for v in ['front','left','back','right']],[['1001',0],['1002',0],['1003',0],['1004',0]])
        self.assertEqual([g[n]['inputs']['image'] for n in ['1001','1002','1003','1004']],['Front-detail.png','Left-detail.png','Back-detail.png','Right-detail.png'])
        self.assertEqual(g['319']['inputs']['unet_name'],'pixal3d_multiview_int8_convrot.safetensors')
        self.assertEqual(g['970']['inputs'],shape);self.assertEqual(g['12']['inputs']['steps'],12);self.assertEqual(g['12']['inputs']['cfg'],1)
    def test_wrong_route_fov_or_missing_view_rejected(self):
        for profile,images,fov in [('pixal-single-v1',{'geometry':'x'},20),('pixal-multiview-v1',{'geometryFront':'x'},20),('pixal-multiview-v1',{'geometry'+v:'x' for v in ['Front','Left','Back','Right']},42),
                                  ('pixal-multiview-v1',{'detail'+v:'x' for v in ['Front','Left','Back','Right']},20)]:
            with self.assertRaises(ValueError):comfy.compile_graph('geometry',profile,images,'headkit/run',fov=fov)
        shape=pin(self.file('shape.npz'))
        for images in ({'detailFront':'x'},{'geometry'+v:'x' for v in ['Front','Left','Back','Right']}):
            with self.assertRaisesRegex(ValueError,'multiview roles'):
                comfy.compile_graph('appearance','pixal-multiview-v1',images,'headkit/run',fov=20,shape=shape)
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
    def test_rgb_staging_preserves_background_routing_and_legacy_default(self):
        from headkit.generation import prepare_request
        from headkit.source_inventory import freeze_sources
        for index,decision in enumerate((None,{'route':'remove','size':[512,512]},
                                         {'route':'preserve-alpha','size':[512,512]})):
            data=self.fixture()
            with Image.open(self.root/'detail.png') as image:
                image=image.convert('RGBA');image.putpixel((10,10),(120,180,240,128));image.save(self.root/'detail.png')
            data['inputs']['detail']['sha256']=pin(self.root/'detail.png')['sha256']
            for role in ('geometry','mask'):data['inputs'][role]=dict(data['inputs']['detail'])
            path=self.root/'manifest.json';write(path,data)
            identity=self.comfy_runtime_identity(freeze_sources(read(self.root/'bindings.json')))
            with patch('headkit.comfy.compile_graph',return_value={}) as compiler:
                result=prepare_request(path,self.root/'bindings.json','calibrate',self.root/f'background-{index}.json',
                                       runtime=self.runtime_identity(),comfy_runtime=identity,background=decision)
            self.assertIs(compiler.call_args.kwargs['background'],decision)
            with Image.open(next(Path(row['path']) for row in result['inputs']
                                 if Path(row['path']).name=='geometry.png')) as staged:
                expected=(60,90,120) if decision is None else (120,180,240)
                self.assertEqual(staged.getpixel((10,10)),expected)
            if decision is None:self.assertNotIn('backgroundDecision',result)
            else:self.assertEqual(result['backgroundDecision'],decision)

    def fixture(self):
        self.pair();raw=pin(self.file('raw.glb'));shape=pin(self.file('shape.npz'))
        data={'schemaVersion':1,'id':'geometry-review','inputs':{name:{'path':Path(row['path']).name,'sha256':row['sha256']}
              for name,row in {'detail':pin(self.root/'detail.png'),'geometryRaw':raw,'shape':shape}.items()},
              'camera':{'reviewed':True,'fovDegrees':42},'approval':{'inputReviewComplete':True}}
        inventory=self.inventory();core=Path(inventory['core'])
        adapter=core/'custom_nodes'/'srn_headkit';adapter.mkdir(parents=True)
        for code in (Path(__file__).parent/'comfy_nodes').glob('*.py'):(adapter/code.name).write_bytes(code.read_bytes())
        write(self.root/'bindings.json',{'schemaVersion':1,'toolsRoot':str(self.root),'comfyInput':str(self.root/'comfy-input'),
              'comfyUrl':'http://127.0.0.1:8188','comfyRoot':str(core),'comfyCustomNodes':str(adapter.parent),'comfyStartupConfig':str(self.root/'controlled-startup.json'),
              'comfySources':[pin(p) for p in sorted(core.rglob('*')) if p.is_file()]})
        from headkit.source_inventory import freeze_sources
        write(adapter/'source-roots.json',{'schemaVersion':1,'inventory':freeze_sources(read(self.root/'bindings.json'))})
        return data
    def request(self,data,stage='appearance'):
        from headkit.__main__ import request_stage
        write(self.root/'manifest.json',data)
        runtime=self.runtime_identity()
        from headkit.source_inventory import freeze_sources
        server_runtime=self.comfy_runtime_identity(freeze_sources(read(self.root/'bindings.json')))
        if stage=='export':return request_stage(self.root/'manifest.json',self.root/'bindings.json',stage,self.root/'request.json',runtime=runtime,comfy_runtime=server_runtime)
        with patch('headkit.__main__.comfy.compile_graph',return_value={}):
            return request_stage(self.root/'manifest.json',self.root/'bindings.json',stage,self.root/'request.json',runtime=runtime,comfy_runtime=server_runtime)
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
        self.assertIn(result['bindings'],result['inputs'])
        self.assertEqual(result['comfyEndpoint'],'http://127.0.0.1:8188')
        self.assertEqual(result['runtimeIdentity'],self.runtime_identity())
        for name in ('toolchain','migrationReceipt','python'):self.assertIn(result['runtimeIdentity'][name],result['inputs'])
        source_config=Path(read(self.root/'bindings.json')['comfyCustomNodes'])/'srn_headkit'/'source-roots.json'
        self.assertIn(pin(source_config),result['inputs'])
        self.assertEqual(result['comfyRuntimeIdentity']['comfySourceInventory'],result['comfySourceInventory'])
        self.assertEqual(read(self.root/'request.json'),result)

    def test_multiview_appearance_stages_four_detailed_views(self):
        data=self.fixture();data['profile']='pixal-multiview-v1';data['camera']['fovDegrees']=20
        for view in ('Front','Left','Back','Right'):data['inputs']['detail'+view]=data['inputs']['detail']
        data['approval']['generatedGeometry']=self.approval(data);write(self.root/'manifest.json',data)
        with patch('headkit.__main__.comfy.compile_graph',return_value={}) as compile_graph:
            from headkit.__main__ import request_stage
            request_stage(self.root/'manifest.json',self.root/'bindings.json','appearance',self.root/'request.json',runtime=self.runtime_identity(),
                          comfy_runtime=self.comfy_runtime_identity(__import__('headkit.source_inventory',fromlist=['freeze_sources']).freeze_sources(read(self.root/'bindings.json'))))
        images=compile_graph.call_args.args[2]
        self.assertEqual(sorted(images),['detailBack','detailFront','detailLeft','detailRight'])
        self.assertTrue(all(path.endswith(name+'.png') for name,path in images.items()))

    def test_changed_installed_source_snapshot_blocks_request(self):
        data=self.fixture();data['approval']['generatedGeometry']=self.approval(data)
        source_config=Path(read(self.root/'bindings.json')['comfyCustomNodes'])/'srn_headkit'/'source-roots.json'
        config=read(source_config);config['inventory']['files'][0]['sha256']='0'*64;write(source_config,config)
        with self.assertRaisesRegex(ValueError,'Installed Comfy source snapshot differs'):
            self.request(data)
        self.assertFalse((self.root/'comfy-input').exists())
        self.assertFalse((self.root/'request.json').exists())

    def test_request_pins_comfy_loader_category_resolved_path_and_bytes(self):
        data=self.fixture();data['approval']['generatedGeometry']=self.approval(data)
        write(self.root/'manifest.json',data)
        name='pixal3d_int8_convrot.safetensors';model=self.root/name;model.write_bytes(b'reviewed checkpoint')
        local=read(self.root/'bindings.json');local['models']={name:pin(model)};write(self.root/'bindings.json',local)
        graph={'319':{'class_type':'UNETLoader','inputs':{'unet_name':name}}}
        original_read=__import__('headkit.__main__',fromlist=['read']).read
        def read_with_fixture_profile(path):
            if Path(path).name=='checkpoints.json':return {name:pin(model)['sha256']}
            return original_read(path)
        with patch('headkit.__main__.comfy.compile_graph',return_value=graph), patch('headkit.__main__.read',side_effect=read_with_fixture_profile):
            from headkit.__main__ import request_stage
            result=request_stage(self.root/'manifest.json',self.root/'bindings.json','appearance',self.root/'request.json',runtime=self.runtime_identity(),comfy_runtime=self.comfy_runtime_identity(__import__('headkit.source_inventory',fromlist=['freeze_sources']).freeze_sources(read(self.root/'bindings.json'))))
        self.assertEqual(result['loaderModels'],[{'category':'diffusion_models','name':name,
            'pathIdentity':__import__('headkit.comfy_nodes.model_resolution',fromlist=['path_identity']).path_identity(model),
            'sha256':pin(model)['sha256']}])
        loader=result['prompt']['319']
        self.assertEqual(loader['class_type'],'HeadkitVerifiedUNETLoaderV1')
        self.assertEqual(loader['inputs']['headkit_model_sha256'],pin(model)['sha256'])
        self.assertEqual(loader['inputs']['headkit_model_path_identity'],result['loaderModels'][0]['pathIdentity'])
        self.assertIn(pin(model),result['inputs'])


    def test_export_requires_review_bound_to_exact_source_before_staging(self):
        data=self.fixture();data['inputs']['exportSource']=data['inputs']['geometryRaw']
        valid={'decision':'approved','notes':'Reviewed exact oriented export clay','exportSourceSha256':data['inputs']['exportSource']['sha256']}
        data['approval']['generatedGeometry']=self.approval(data)
        for review in (None,dict(valid,decision='rejected'),dict(valid,exportSourceSha256='0'*64),dict(valid,notes=' ')):
            with self.subTest(review=review):
                if review is not None:data['approval']['exportGeometry']=review
                with self.assertRaisesRegex(ValueError,'Approve generated clay'):self.request(data,'export')
                self.assertFalse((self.root/'comfy-input').exists());self.assertFalse((self.root/'request.json').exists())
    def test_export_freezes_reviewed_source_and_rejects_changed_mesh(self):
        data=self.fixture();data['inputs']['exportSource']=data['inputs']['geometryRaw']
        data['approval']['exportGeometry']={'decision':'approved','notes':'Reviewed exact oriented export clay','exportSourceSha256':data['inputs']['exportSource']['sha256']}
        result=self.request(data,'export');self.assertIn(data['inputs']['exportSource']['sha256'],[p['sha256'] for p in result['inputs']])
        self.assertEqual(result['prompt']['1']['inputs']['sha256'],data['inputs']['exportSource']['sha256'])
        (self.root/'raw.glb').write_text('changed after review')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):self.request(data,'export')


class RuntimeIdentityTests(Temporary):
    def fixture(self):
        toolchain=self.file('toolchain.json');migration=self.file('migration.json')
        active={'toolsRoot':str(self.root),'tools':{'python':pin(sys.executable)}}
        local={'schemaVersion':1,'toolsRoot':str(self.root),'toolchain':str(toolchain),'migrationReceipt':str(migration),'python':pin(sys.executable)}
        return toolchain,migration,active,local
    def launch(self,local,toolchain,migration,active):
        from headkit.common import launched
        write(self.root/'bindings.json',local)
        with patch.dict('os.environ',{'SRN_SHARED_TOOLCHAIN':str(toolchain),'SRN_SHARED_TOOL_MIGRATION':str(migration)}), \
             patch.dict(sys.modules,{'shared_toolchain':SimpleNamespace(load=lambda *a,**k:active)}):
            return launched(self.root/'bindings.json')
    def test_runtime_identity_matches_and_is_returned(self):
        toolchain,migration,active,local=self.fixture();identity=self.launch(local,toolchain,migration,active)
        self.assertEqual(identity,{'toolchain':pin(toolchain),'migrationReceipt':pin(migration),'python':pin(sys.executable),'toolsRoot':str(self.root.resolve())})
    def test_rejects_different_toolchain_migration_python_or_tools_bank(self):
        toolchain,migration,active,local=self.fixture()
        for name,value in [('toolchain',str(self.file('other-toolchain'))),('migrationReceipt',str(self.file('other-migration'))),
                           ('python',pin(self.file('other-python.exe'))),('toolsRoot',str(self.root/'other-bank'))]:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError,'differs|differ'):self.launch(dict(local,**{name:value}),toolchain,migration,active)
        blender=pin(self.file('blender.exe'));other=pin(self.file('other-blender.exe'));active['runtimes']={'blender':blender}
        with self.assertRaisesRegex(ValueError,'Blender differs'):self.launch(dict(local,blender=other),toolchain,migration,active)
        wrong=copy.deepcopy(active);wrong['tools']['python']=pin(self.file('fake-python.exe'))
        with self.assertRaisesRegex(ValueError,'Executing Python'):self.launch(local,toolchain,migration,wrong)
    def test_runner_receipt_records_actual_runtime_and_rejects_other_runtime(self):
        runner=ResumeTests.fixture(self);runner.runtime={'verifiedRuntime':'A'}
        with patch('headkit.runner.python_package_pins',return_value=runner.bindings['pythonPackages']['files']):
            runner.execute('prepare')
        receipt=read(runner.state['stages']['prepare']['path']);self.assertEqual(receipt['runtimeIdentity'],runner.runtime)
        other=Runner(runner.manifest_path,runner.bindings_path,runner.run,runtime={'verifiedRuntime':'B'})
        with self.assertRaisesRegex(ValueError,'runtime differs'):other.result('prepare',require_review=False)


class PythonPackagePinTests(Temporary):
    def test_missing_or_incomplete_package_inventory_is_rejected(self):
        from headkit.common import python_package_pins
        bindings=self.bindings_data()
        with self.assertRaisesRegex(ValueError,'Missing complete Python package'):
            python_package_pins({'toolsRoot':str(self.root)})
        (Path(bindings['pythonPackages']['directory'])/'numpy'/'unlisted.py').write_text('extra executable module')
        with self.assertRaisesRegex(ValueError,'complete installation membership'):
            python_package_pins(bindings)

    def test_bound_package_origins_must_resolve_inside_inventory(self):
        from headkit.common import python_package_pins
        bindings=self.bindings_data()
        root=Path(bindings['pythonPackages']['directory'])
        modules={name:SimpleNamespace(__file__=str(root/name/'__init__.py'),
                __path__=[str(root/name)]) for name in ('numpy','PIL','scipy')}
        with patch('headkit.common.importlib.import_module',side_effect=lambda name:modules[name]):
            pins=python_package_pins(bindings,require_imports=True)
        self.assertEqual(pins,bindings['pythonPackages']['files'])
        modules['scipy']=SimpleNamespace(__file__=str(self.file('unbound-scipy.py')),
                                      __path__=[str(self.root)])
        with patch('headkit.common.importlib.import_module',side_effect=lambda name:modules[name]):
            with self.assertRaisesRegex(ValueError,'outside its byte-bound installation'):
                python_package_pins(bindings,require_imports=True)

    def test_package_inventory_is_rechecked_after_import(self):
        from headkit.common import python_package_pins
        bindings=self.bindings_data();root=Path(bindings['pythonPackages']['directory'])
        modules={name:SimpleNamespace(__file__=str(root/name/'__init__.py'),
                __path__=[str(root/name)]) for name in ('numpy','PIL','scipy')}
        def import_package(name):
            if name=='scipy':(root/'scipy'/'late.py').write_text('changed while importing')
            return modules[name]
        with patch('headkit.common.importlib.import_module',side_effect=import_package):
            with self.assertRaisesRegex(ValueError,'membership changed while importing'):
                python_package_pins(bindings,require_imports=True)

    def test_stage_receipt_pins_and_rechecks_the_complete_package_tree(self):
        runner=ResumeTests.fixture(self)
        with patch.object(runner,'_execute',return_value={'fixture':True}):
            runner.execute('prepare')
        receipt=read(runner.state['stages']['prepare']['path'])
        self.assertTrue(set((item['path'],item['sha256']) for item in runner.bindings['pythonPackages']['files'])<=
                        set((item['path'],item['sha256']) for item in receipt['inputs']))
        runner=ResumeTests.fixture(self)
        runner.run=self.root/'run-mutation';runner.run.mkdir()
        runner.state_path=runner.run/'state.json';runner.state={'schemaVersion':1,'id':runner.data['id'],'stages':{}}
        def adds_unpinned_module(stage,folder):
            (Path(runner.bindings['pythonPackages']['directory'])/'numpy'/'late.py').write_text('changed during stage')
            return {'fixture':True}
        with patch.object(runner,'_execute',side_effect=adds_unpinned_module):
            with self.assertRaisesRegex(ValueError,'complete installation membership'):
                runner.execute('prepare')
        failed=read(runner.run/'prepare'/'attempt-01'/'receipt.json')
        self.assertEqual(failed['state'],'failed')


class ComfyServerRuntimeTests(Temporary):
    def test_runtime_members_excludes_inactive_packages_and_nonexecution_assets(self):
        from headkit.comfy_nodes.runtime_identity import runtime_members
        stdlib=self.root/'Lib';active=self.root/'venv'/'site-packages'
        paths=[stdlib/'os.py',stdlib/'site-packages'/'unused.py',active/'torch'/'kernel.dll',
               active/'torch'/'template.jinja',active/'torch'/'sample.png',
               active/'torch-1.dist-info'/'METADATA',active/'torch-1.dist-info'/'RECORD']
        for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        files=runtime_members({stdlib,active})
        self.assertEqual(files,{paths[i] for i in (0,2,3,5)})
        self.assertIn(paths[1],runtime_members({stdlib,stdlib/'site-packages',active}))

    def test_runtime_members_include_sourceless_bytecode_and_zip_imports(self):
        from headkit.comfy_nodes.runtime_identity import runtime_members
        active=self.root/'venv'/'site-packages'
        paths=[active/'plain.pyc',active/'legacy.PYO',active/'bundle.pyz',active/'old.egg',active/'__pycache__'/'cached.pyc']
        for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        self.assertEqual(runtime_members({active}),set(paths[:4]))

    def test_runtime_byte_hash_catches_same_size_change_with_restored_timestamp(self):
        from headkit.comfy_nodes.runtime_identity import _pin
        path=self.file('kernel.dll','abc');before=_pin(path);stat=path.stat()
        path.write_text('xyz');os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        self.assertNotEqual(before,_pin(path))

    def test_runtime_identity_endpoint_uses_the_clients_get_method(self):
        import ast
        source=Path(__file__).parent/'comfy_nodes'/'__init__.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        handlers=[node for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
                  and node.name=='verify_headkit_runtime_identity']
        decorators=[decorator for handler in handlers for decorator in handler.decorator_list
                    if isinstance(decorator,ast.Call) and isinstance(decorator.func,ast.Attribute)
                    and decorator.func.attr in ('get','post')]
        self.assertEqual(len(decorators),1)
        self.assertEqual(decorators[0].func.attr,'get')
        self.assertEqual(ast.literal_eval(decorators[0].args[0]),'/headkit/runtime-identity')
        self.assertTrue(any(isinstance(node,ast.Name) and node.id=='loaded_source_code' for node in ast.walk(handlers[0])))

    def test_session_restart_changes_the_runtime_fingerprint(self):
        from headkit.comfy_nodes.runtime_identity import seal_runtime_identity,same_runtime_environment
        baseline=seal_runtime_identity({'session':{'id':'a'*32},'files':[]})
        restarted=seal_runtime_identity({'session':{'id':'b'*32},'files':[]})
        self.assertNotEqual(baseline['fingerprint'],restarted['fingerprint'])
        self.assertFalse(same_runtime_environment(restarted,baseline))

    def test_server_snapshot_hashes_python_torch_and_native_runtime_files(self):
        from headkit.comfy_nodes.runtime_identity import capture_runtime_identity
        app=self.root/'comfy';app.mkdir()
        stdlib=self.root/'embedded'/'Lib';site=stdlib/'site-packages'
        package=site/'torch';native=package/'lib'/'cudnn.dll'
        native.parent.mkdir(parents=True);torch_file=package/'__init__.py'
        torch_file.write_text('torch fixture');native.write_bytes(b'CUDA native fixture')
        stdlib_file=stdlib/'os.py';stdlib_file.parent.mkdir(parents=True,exist_ok=True);stdlib_file.write_text('stdlib fixture')
        executable=self.root/'embedded'/'python.exe';executable.parent.mkdir(parents=True,exist_ok=True);executable.write_bytes(b'python fixture')
        torch=SimpleNamespace(__file__=str(torch_file),__version__='2.7 fixture',
              version=SimpleNamespace(cuda='12.8',hip=None),
              backends=SimpleNamespace(cudnn=SimpleNamespace(version=lambda:8900)))
        paths={'stdlib':str(stdlib),'platstdlib':str(stdlib),'purelib':str(site),'platlib':str(site)}
        with patch('headkit.comfy_nodes.runtime_identity.sys.executable',str(executable)), \
             patch('headkit.comfy_nodes.runtime_identity.sys.prefix',str(executable.parent)), \
             patch('headkit.comfy_nodes.runtime_identity.sys.base_prefix',str(executable.parent)), \
             patch('headkit.comfy_nodes.runtime_identity.sys.path',[str(site)]), \
             patch('headkit.comfy_nodes.runtime_identity.sysconfig.get_paths',return_value=paths), \
             patch.dict(sys.modules,{'torch':torch}):
            from headkit.comfy_nodes.verification import verification_pass
            controlled={'id':'a'*32,'pid':123}
            with verification_pass('runtime-session-binding'):
                bound=capture_runtime_identity(SimpleNamespace(base_path=str(app)),session=controlled)
            self.assertEqual(bound['session'],controlled)
            result=capture_runtime_identity(SimpleNamespace(base_path=str(app)))
            self.assertEqual(result['files'],sorted([pin(path) for path in
                             (executable,native,torch_file,stdlib_file)],key=lambda row:row['path'].casefold()))
            self.assertEqual(result['fingerprint'],capture_runtime_identity(SimpleNamespace(base_path=str(app)))['fingerprint'])
            before=result['fingerprint'];native.write_bytes(b'changed CUDA native fixture')
            changed=capture_runtime_identity(SimpleNamespace(base_path=str(app)))
            runtime_module=sys.modules[capture_runtime_identity.__module__]
            with patch.object(runtime_module,'_linked',side_effect=lambda path:Path(path)==native):
                with self.assertRaisesRegex(ValueError,'Linked Comfy runtime files'):
                    capture_runtime_identity(SimpleNamespace(base_path=str(app)))
            with patch.object(runtime_module,'_linked',side_effect=lambda path:Path(path)==package):
                with self.assertRaisesRegex(ValueError,'Linked Comfy runtime directories'):
                    capture_runtime_identity(SimpleNamespace(base_path=str(app)))
            added=site/'new.py';added.write_text('new runtime member')
            enlarged=capture_runtime_identity(SimpleNamespace(base_path=str(app)))
            self.assertNotEqual(changed['fingerprint'],enlarged['fingerprint'])
            self.assertIn(pin(added),enlarged['files'])
        paths_in={row['path'] for row in result['files']}
        self.assertIn(str(executable.resolve()),paths_in)
        self.assertIn(str(native.resolve()),paths_in)
        self.assertNotEqual(before,changed['fingerprint'])

    def test_server_runtime_snapshot_is_hash_bound_and_sources_must_match(self):
        from headkit.source_inventory import validate_comfy_runtime
        inventory=self.inventory();roots=inventory['roots'];snapshot=self.comfy_runtime_identity(inventory)
        self.assertEqual(validate_comfy_runtime(snapshot,roots,inventory),snapshot)
        changed=copy.deepcopy(snapshot);changed['torch']['version']='different torch'
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            validate_comfy_runtime(changed,roots)
        with self.assertRaisesRegex(ValueError,'source coverage'):
            validate_comfy_runtime(snapshot,[str(self.root/'other-source')],inventory)

        changed=copy.deepcopy(snapshot);changed['comfySourceInventory']['files'][0]['sha256']='0'*64
        changed['fingerprint']=digest({key:value for key,value in changed.items() if key!='fingerprint'})
        with self.assertRaisesRegex(ValueError,'startup source snapshot'):
            validate_comfy_runtime(changed,roots,inventory)

    def test_unmanaged_and_legacy_runtime_identities_are_rejected(self):
        from headkit.source_inventory import validate_comfy_runtime
        inventory=self.inventory();snapshot=self.comfy_runtime_identity(inventory)
        for change in ('legacy','missing-session','bad-session'):
            altered=copy.deepcopy(snapshot)
            if change=='legacy':altered['schemaVersion']=2
            elif change=='missing-session':del altered['session']
            else:altered['session']['id']=''
            altered['fingerprint']=digest({key:value for key,value in altered.items() if key!='fingerprint'})
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_comfy_runtime(altered,inventory['roots'],inventory)



class SourceSnapshotTests(Temporary):
    def test_installed_snapshot_matches_the_prepared_inventory(self):
        from headkit.comfy_nodes.source_snapshot import capture_inventory,load_inventory,same_inventory
        inventory=self.inventory()
        captured=capture_inventory(inventory['core'],inventory['roots'])
        self.assertTrue(same_inventory(captured,inventory))
        path=self.root/'srn_headkit'/'source-roots.json';path.parent.mkdir()
        write(path,{'schemaVersion':1,'inventory':inventory})
        self.assertEqual(load_inventory(path,inventory['core']),inventory)

    def test_restored_disk_files_do_not_hide_startup_source_changes(self):
        from headkit.comfy_nodes.source_snapshot import capture_inventory,verify_inventory
        inventory=self.inventory();path=Path(inventory['core'])/'nodes.py';reviewed=path.read_bytes()
        path.write_text('modified implementation\n')
        startup=capture_inventory(inventory['core'],inventory['roots'])
        path.write_bytes(reviewed)
        with self.assertRaisesRegex(ValueError,'startup snapshot'):
            verify_inventory(startup)



class AdapterInstallTests(Temporary):
    def test_install_binds_the_source_snapshot_to_local_roots(self):
        from headkit.__main__ import install_nodes
        inventory=self.inventory();core=Path(inventory['core']);custom=core/'custom_nodes'
        local={'comfyRoot':str(core),'comfyCustomNodes':str(custom),'comfySources':inventory['files']}
        destination=custom/'srn_headkit'
        result=install_nodes(destination,local)
        from headkit.source_inventory import capture_sources
        installed_inventory=capture_sources(inventory['core'],inventory['roots'])
        self.assertTrue(result['restartRequired'])
        self.assertEqual(read(destination/'source-roots.json'),{'schemaVersion':1,'inventory':installed_inventory})
        self.assertTrue((destination/'source_snapshot.py').is_file())


class SourceInventoryTests(Temporary):
    def test_example_declares_inventory_and_launcher_bindings(self):
        example=read(Path(__file__).parent/'examples'/'local-bindings.example.json')
        self.assertTrue({'comfyRoot','comfyDependencyRoots','comfySources','toolchain','migrationReceipt','python'}<=set(example))
    def test_incomplete_or_unrelated_source_pins_are_rejected(self):
        from headkit.source_inventory import freeze_sources,verify_sources
        inventory=self.inventory();local={'comfyRoot':inventory['core'],'comfyCustomNodes':str(Path(inventory['core'])/'custom_nodes'),'comfySources':inventory['files'][:1]}
        with self.assertRaisesRegex(ValueError,'incomplete'):freeze_sources(local)
        local['comfySources']=[pin(self.file('unrelated.py'))]
        with self.assertRaisesRegex(ValueError,'incomplete'):freeze_sources(local)
        self.assertEqual(verify_sources(inventory),inventory)
    def test_changed_deleted_and_added_source_files_invalidate_inventory(self):
        from headkit.source_inventory import verify_sources
        for change in ('changed','deleted','added'):
            inventory=self.inventory();root=Path(inventory['core'])
            if change=='changed':(root/'nodes.py').write_text('modified')
            elif change=='deleted':(root/'nodes.py').unlink()
            else:(root/'comfy'/'new_loader.py').write_text('new loader')
            with self.subTest(change=change):
                with self.assertRaises(ValueError):verify_sources(inventory)
    def test_submit_rejects_incomplete_inventory_before_server_contact(self):
        request=self.freeze_request({'token':'missing-inventory','stage':'geometry','prompt':{},'inputs':[]})
        request['comfySourceInventory']['files'].pop();client=FakeClient()
        with patch.object(client,'request') as server:
            self.bind_dispatch(request,client.url)
            with self.assertRaisesRegex(ValueError,'incomplete'):self.submit(client,self.root/'ledger.json',request,self.root/'job')
            server.assert_not_called()
    def test_added_source_is_rejected_during_collection_and_on_terminal_reuse(self):
        for terminal in (False,True):
            client,ledger,token,output,job,_=CollectionReceiptTests.fixture(self)
            if terminal:comfy.collect(client,ledger,token,output,job)
            inventory=read(job/'submission-intent.json')['prepared']['comfySourceInventory']
            (Path(inventory['core'])/'new_node.py').write_text('new implementation')
            with self.subTest(terminal=terminal):
                with self.assertRaisesRegex(ValueError,'membership'):comfy.collect(client,ledger,token,output,job)
            if not terminal:self.assertEqual(read(job/'collection.json')['state'],'failed-validation')


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
    def test_silhouette_iou_floor_rejects_lower_nonfinite_and_invalid_values(self):
        values=(.939,0,-1,float('nan'),float('inf'),-float('inf'),1.01,True,'0.94',10**400)
        for index,value in enumerate(values):
            with self.subTest(value=repr(value)):
                config=self.pair();config['minimumSilhouetteIoU']=value
                output=self.root/f'bad-threshold-{index}'
                with self.assertRaisesRegex(ValueError,'Minimum silhouette IoU'):
                    prepare(self.root/'clay.png',self.root/'detail.png',config,output)
                self.assertFalse(output.exists())
    def test_silhouette_iou_floor_allows_documented_boundary(self):
        for threshold in (.94,1.0):
            with self.subTest(threshold=threshold):
                config=self.pair();config['minimumSilhouetteIoU']=threshold
                result=prepare(self.root/'clay.png',self.root/'detail.png',config,self.root/f'valid-{threshold}')
                self.assertEqual(result['silhouetteIoU'],1)
    def test_multiview_shared_scale_and_order_gates(self):
        align=self.pair();pairs={v:(self.root/'clay.png',self.root/'detail.png') for v in ['front','left','back','right']}
        config={'rigReviewed':True,'fovDegrees':20,'views':{v:{'azimuthDegrees':a,'orientationReviewed':True,'alignment':align,
            'crown':[.5,.1],'chin':[.5,.9],'skullCenter':[.5,.5]} for v,a in [('front',0),('left',90),('back',180),('right',270)]}}
        result=prepare_multiview(pairs,config,self.root/'good');self.assertFalse(result['independentCropping'])
        config['views']['left']['skullCenter']=[.6,.5]
        with self.assertRaisesRegex(ValueError,'drift'):prepare_multiview(pairs,config,self.root/'bad')
    def test_multiview_pair_cannot_lower_silhouette_floor(self):
        align=self.pair();align['minimumSilhouetteIoU']=.5
        pairs={view:(self.root/'clay.png',self.root/'detail.png') for view in ('front','left','back','right')}
        config={'rigReviewed':True,'fovDegrees':20,'views':{view:{'azimuthDegrees':azimuth,'orientationReviewed':True,
            'alignment':align,'crown':[.5,.1],'chin':[.5,.9],'skullCenter':[.5,.5]}
            for view,azimuth in [('front',0),('left',90),('back',180),('right',270)]}}
        with self.assertRaisesRegex(ValueError,'Minimum silhouette IoU'):
            prepare_multiview(pairs,config,self.root/'low-floor')


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
    def test_duplicate_visible_mesh_instances_rejected(self):
        p,f=self.tetra();out=self.root/'mesh.glb';write_mesh(out,p,f);d,b,_=load(out.read_bytes())
        d['nodes'].append({'mesh':0});d['scenes'][0]['nodes'].append(1)
        with self.assertRaisesRegex(ValueError,'Exactly one visible mesh instance'):
            load(encode(d,b))
    def test_comfy_loader_validates_the_active_scene_mesh_instance(self):
        from headkit.comfy_nodes.gltf import load as comfy_load
        p,f=self.tetra();out=self.root/'mesh.glb';write_mesh(out,p,f);d,b,_=load(out.read_bytes())
        d['nodes'].append({'mesh':0});d['scenes'][0]['nodes'].append(1)
        with self.assertRaisesRegex(ValueError,'Exactly one visible mesh instance'):
            comfy_load(encode(d,b))
        d,b,_=load(out.read_bytes());d['scenes'][0]['nodes']=[]
        with self.assertRaisesRegex(ValueError,'Exactly one visible mesh instance'):
            comfy_load(encode(d,b))
    NECK={'taper':{'minScale':.6,'frontStart':-.06,'backStart':-.03,'axis':[0,0]},'seal':{'height':'measured','inset':.9,'rise':.003}}
    def bell(self,segments=32,rows=12):
        """Closed head-local bell (face +y, up +z) whose neck cavity opens at a rim 2 cm lower in front than behind."""
        rings=[]
        for theta in np.arange(segments)*2*np.pi/segments:
            low=-.08-.02*(1+np.cos(theta))/2
            profile=[(.03,.10),(.05,.08)]+[(.05,z) for z in np.linspace(.06,low,rows)]+[(.04,z) for z in np.linspace(low,.04,rows)]+[(.02,.06)]
            rings.append([(r*np.sin(theta),r*np.cos(theta),z) for r,z in profile])
        rings=np.transpose(np.asarray(rings),(1,0,2));count=len(rings)
        vertices=np.r_[[[0,0,.105]],rings.reshape(-1,3),[[0,0,.065]]];j=np.arange(segments);k=(j+1)%segments
        ring=lambda row,index:1+row*segments+index;last=len(vertices)-1
        faces=[np.c_[np.zeros(segments,int),ring(0,k),ring(0,j)]]
        for row in range(count-1):
            faces+=[np.c_[ring(row,j),ring(row,k),ring(row+1,k)],np.c_[ring(row,j),ring(row+1,k),ring(row+1,j)]]
        faces=np.concatenate(faces+[np.c_[np.full(segments,last),ring(count-1,j),ring(count-1,k)]])
        tri=vertices[faces]
        if np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()<0:faces=faces[:,::-1]
        return vertices,faces
    def glb(self,local):return np.c_[local[:,0],local[:,2],-local[:,1]]  # inverse of GLB->NWN (x,-z,y)
    def test_bell_fixture_is_closed_and_crossing_free(self):
        from headkit.intersections import scan
        p,f=self.bell();self.assertTrue(topology(p,f)['closed']);self.assertFalse(scan(p,f)['pairs'])
    def test_neck_taper_profile_is_monotonic_and_c1_without_a_shelf(self):
        from headkit.mesh import taper_scale
        taper=self.NECK['taper'];bottom=-.1;z=np.linspace(.0,bottom,4001);dz=z[0]-z[1]
        for phi in (0,.7,np.pi/2,2.5,np.pi):
            with self.subTest(phi=phi):
                local=np.c_[np.full_like(z,.04*np.sin(phi)),np.full_like(z,.04*np.cos(phi)),z];scale=taper_scale(local,taper,bottom)
                start=taper['backStart']+(taper['frontStart']-taper['backStart'])*((1+np.cos(phi))/2)**2
                self.assertTrue(np.all(scale[z>=start]==1));self.assertAlmostEqual(scale[-1],taper['minScale'])
                self.assertTrue(np.all(np.diff(scale)<=1e-15))  # never widens toward the rim
                slope=np.diff(scale)/dz;curvature=6*(1-taper['minScale'])/(start-bottom)**2
                # C1: the slope never jumps (a shelf or lip would), and it eases in from zero at the start.
                self.assertLessEqual(np.abs(np.diff(slope)).max(),1.01*curvature*dz)
                self.assertLess(np.abs(slope[np.argmax(z<start)]),2*curvature*dz)
    def test_section_ring_closure_is_angular_not_density(self):
        from headkit.mesh import enclosed
        angle=np.linspace(0,2*np.pi,7);ring=np.c_[np.cos(angle),np.sin(angle)];segments=np.stack([ring[:-1],ring[1:]],1)
        self.assertTrue(enclosed(segments,[0,0]));self.assertFalse(enclosed(segments[:-1],[0,0]))
        self.assertFalse(enclosed(segments,[3,0]));self.assertFalse(enclosed(segments[:0],[0,0]))
    def test_neck_seal_closes_the_open_bottom_inside_the_walls(self):
        from headkit.mesh import neck_policy,neck_seal,section,transform
        from headkit.intersections import scan
        p,f=self.bell();neck=neck_policy({'seal':dict(self.NECK['seal'],searchTop=-.03)},{'matrix':np.eye(4).tolist(),'reviewed':True})
        cap,cap_faces,record=neck_seal(self.glb(p),f,neck,None)
        self.assertEqual(record['capTriangles'],48);self.assertAlmostEqual(record['lowestClosedRing'],-.08,places=3)
        self.assertAlmostEqual(record['height'],record['lowestClosedRing']+.003)
        joined=np.r_[self.glb(p),cap];faces=np.r_[f,cap_faces+len(p)]
        self.assertTrue(topology(joined,faces)['closed']);self.assertFalse(scan(joined,faces)['pairs'])
        local=transform(neck['frame'],cap);rim=np.linalg.norm(local[:24,:2],axis=1)
        self.assertTrue(np.all((rim>.8*.04)&(rim<.04)))  # spans the inner wall's opening without touching it
        self.assertTrue(np.allclose(local[:25,2],record['height']) and np.isclose(local[25,2],record['height']+.003))
        self.assertEqual(len(section(transform(neck['frame'],joined),faces,-.09)),len(section(p,f,-.09)))  # below: unchanged
    def test_neck_repair_tapers_master_reduces_to_budget_minus_cap_and_audits(self):
        from headkit import mesh as mesh_module
        p,f=self.bell();source=self.root/'source.glb';write_mesh(source,self.glb(p),f);fit={'matrix':np.eye(4).tolist(),'reviewed':True}
        neck=mesh_module.neck_policy(self.NECK,fit);coarse,coarse_faces=self.bell(24);coarse=self.glb(coarse)
        coarse,_=mesh_module.neck_taper(coarse,coarse_faces,neck);calls=[]
        def reduce(bindings,vertices,faces,target,work):
            calls.append((len(faces),target));np.savez(work,vertices=coarse);return coarse,coarse_faces
        distances=[]
        igl=SimpleNamespace(point_mesh_squared_distance=lambda P,V,F:(distances.append(np.array(P)) or np.zeros(len(P)),))
        budget=len(f)+20;(self.root/'out').mkdir()
        with patch.object(mesh_module,'_reduce',reduce),patch.object(mesh_module,'library',lambda b,name:igl):
            result=mesh_module.repair(source,self.root/'out'/'final.glb',{},{'alphaWrap':False,'triangleBudget':budget,'neck':self.NECK},
                                      {'sourceSha256':pin(source)['sha256'],'visualReviewed':True},fit=fit)
        self.assertEqual(calls,[(len(f),budget-48)]);self.assertTrue(result['passed'])
        self.assertEqual(result['topology']['triangles'],len(coarse_faces)+48);self.assertLessEqual(result['topology']['triangles'],budget)
        self.assertEqual(result['neck']['budget'],{'total':budget,'reservedForCap':48,'reductionTarget':budget-48})
        self.assertEqual(result['neck']['seal']['shellTriangles'],len(coarse_faces))
        master=mesh(self.root/'out'/'master.glb')['positions'];untapered=mesh(self.root/'out'/'master-untapered.glb')['positions']
        self.assertEqual(result['surfaceDistance']['reference'],pin(self.root/'out'/'master.glb'))
        np.testing.assert_allclose(np.sort(distances[0],0),np.sort(np.unique(master,axis=0),0))  # tapered master, not the source
        self.assertGreater(np.abs(master-untapered).max(),.005);self.assertEqual(result['neck']['taper']['untapered'],pin(self.root/'out'/'master-untapered.glb'))
    def test_neck_policy_refuses_without_reviewed_fit_or_with_bad_parameters(self):
        from headkit import mesh as mesh_module
        p,f=self.bell();source=self.root/'source.glb';write_mesh(source,self.glb(p),f)
        inspection={'sourceSha256':pin(source)['sha256'],'visualReviewed':True};eye=np.eye(4).tolist()
        for fit,neck,message in ((None,self.NECK,'reviewed head fit'),({'matrix':eye},self.NECK,'reviewed head fit'),
                                 ({'matrix':np.diag([1,1,-1,1]).tolist(),'reviewed':True},self.NECK,'positive uniform'),
                                 ({'matrix':eye,'reviewed':True},{'taper':dict(self.NECK['taper'],minScale=.1)},'minScale'),
                                 ({'matrix':eye,'reviewed':True},{'seal':dict(self.NECK['seal'])},'searchTop'),
                                 ({'matrix':eye,'reviewed':True},{'disc':{}},'taper and/or seal')):
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):
                mesh_module.repair(source,self.root/'final.glb',{},{'neck':neck},inspection,fit=fit)
        self.assertFalse((self.root/'master.glb').exists())
        with self.assertRaisesRegex(ValueError,'no room'):
            mesh_module.repair(source,self.root/'final.glb',{},{'neck':self.NECK,'triangleBudget':40},inspection,fit={'matrix':eye,'reviewed':True})
    def test_uv_surface_uses_barycentric_positions_not_vertices(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],float);value={'positions':p,'faces':np.array([[0,1,2]]),'uv':np.array([[[0,0],[1,0],[0,1]]],float)}
        positions,ids,_=surface(value,16);self.assertEqual(ids[2,2],0);np.testing.assert_allclose(positions[2,2],[2.5/16,2.5/16,0])
    def test_uv_audit_reports_every_face_without_a_mapped_texel(self):
        from headkit.uv import raster_audit
        good=np.array([[.1,.1],[.9,.1],[.1,.9]])
        tiny=np.array([[.01,.01],[.02,.01],[.01,.02]])
        report,owners=raster_audit([good,tiny],16)
        self.assertEqual(report['degenerateUvFaces'],[])
        self.assertEqual(report['unmappedUvFaces'],[1])
        self.assertEqual(report['mappedTexelsByFace'],[int(np.count_nonzero(owners==0)),0])
        self.assertEqual(sum(report['mappedTexelsByFace']),report['mappedTexels'])
        report,_=raster_audit([tiny],512)
        self.assertEqual(report['unmappedUvFaces'],[])
        for uv in ([[[0,0],[1,0],[0,1]]],[[[0,0],[0,0],[0,0]]]):
            with self.subTest(uv=uv):
                report,_=raster_audit(np.array(uv)/16,16)
                self.assertEqual(report['unmappedUvFaces'],[0])

    def test_bake_rejects_subtexel_faces_before_padding_can_hide_them(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],float)
        value={'positions':p,'faces':np.array([[0,1,2]]),
               'uv':np.array([[[.01,.01],[.02,.01],[.01,.02]]])}
        with self.assertRaisesRegex(ValueError,'unmapped'):
            surface(value,16)

    def test_uv_audit_counts_final_owners_after_overlap(self):
        from headkit.uv import raster_audit
        uv=np.array([[[.1,.1],[.9,.1],[.1,.9]]]*2)
        report,owners=raster_audit(uv,16)
        self.assertEqual(report['overlapFaces'],[0,1])
        self.assertEqual(report['unmappedUvFaces'],[0])
        self.assertEqual(report['mappedTexelsByFace'],[0,int(np.count_nonzero(owners==1))])

    def test_unwrap_routes_unsampled_faces_into_pack_only_own_charts(self):
        from headkit.uv import unwrap
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],float)
        value={'positions':p,'faces':np.array([[0,1,2]]),
               'uv':np.array([[[.01,.01],[.02,.01],[.01,.02]]])}
        with patch('headkit.uv.library'),patch('headkit.uv.physical_fans',return_value=(p,value['faces'])), \
             patch('headkit.uv._chart',return_value=(value['uv']/1024,(2048,2048),1.0,1)) as chart, \
             patch('headkit.uv.gutter_audit',return_value={'nearbyChartPixelsByRadius':{'1':0}}), \
             patch('headkit.uv._repack',side_effect=ValueError('own chart repack reached')) as repack:
            with self.assertRaisesRegex(ValueError,'own chart repack reached'):unwrap(value,{})
            chart.assert_called_once()
            self.assertEqual(repack.call_args.args[5],[0])

    def test_entry_script_puts_bound_packages_first(self):
        source=(Path(__file__).parent/'run_headkit.py').read_text().split('root=package_root')[0];namespace={}
        exec(source,namespace);root=namespace['package_root']
        bindings_path=self.root/'b.json';bindings_path.write_text(json.dumps({'pythonPackages':{'directory':'D:/pkgs','files':[]}}))
        self.assertEqual(root(['x','status','--bindings',str(bindings_path)]),'D:/pkgs')
        self.assertIsNone(root(['x','status']));self.assertIsNone(root(['x','--bindings']))
        bindings_path.write_text('{}');self.assertIsNone(root(['x','--bindings',str(bindings_path)]))

    def test_lower_coverage_floor_needs_a_recorded_review(self):
        from headkit.uv import coverage_floor
        self.assertEqual(coverage_floor(),(.30,None));self.assertEqual(coverage_floor({'minimumCoverage':.4}),(.4,None))
        review={'reviewed':True,'notes':'Dense crest head: 1,335 charts at the 4 px 1K gutter floor reach 27%.'}
        self.assertEqual(coverage_floor({'minimumCoverage':.25,'coverageReview':review}),(.25,review))
        for policy in ({'minimumCoverage':.25},{'minimumCoverage':.25,'coverageReview':{'reviewed':True,'notes':' '}},
                       {'minimumCoverage':.25,'coverageReview':{'reviewed':False,'notes':'x'}}):
            with self.subTest(policy=policy),self.assertRaisesRegex(ValueError,'recorded review'):coverage_floor(policy)
        for floor in (.1,0.0,'0.3'):
            with self.subTest(floor=floor),self.assertRaisesRegex(ValueError,'0.20..1'):coverage_floor({'minimumCoverage':floor})

    def test_unwrap_checks_the_coverage_floor_before_charting(self):
        from headkit.uv import unwrap
        with patch('headkit.uv.library'),patch('headkit.uv._chart') as chart:
            with self.assertRaisesRegex(ValueError,'recorded review'):unwrap({'positions':np.eye(3),'faces':np.array([[0,1,2]]),'uv':np.zeros((1,3,2))},{},{'minimumCoverage':.25})
            chart.assert_not_called()

    def test_bake_and_unwrap_agree_on_corner_connected_subtexel_faces(self):
        from headkit.uv import raster_audit,subtexel_audit
        # The sub-texel face shares only a UV corner with the big face it was cut from (as after an own-chart re-pack).
        big=[[0,0],[8.3,0],[0,8.3]];corner=[[8.3,0],[8.5,0.02],[8.45,0.15]]
        uv=np.array([big,corner],float)/16;report,owners=raster_audit(uv,16)
        self.assertEqual(report['unmappedUvFaces'],[1])
        self.assertTrue(subtexel_audit(uv,16,report,owners,.02)['passed'])
        value={'positions':np.array([[0,0,0],[1,0,0],[0,1,0],[1.1,0,0],[1.05,.1,0]],float),'faces':np.array([[0,1,2],[1,3,4]]),'uv':uv}
        positions,_,low=surface(value,16,.02);self.assertTrue(low['subtexel']['passed'])

    def test_charts_touching_at_a_uv_corner_join_only_by_vertex(self):
        from headkit.uv import chart_ids
        uv=np.array([[[0,0],[.2,0],[0,.2]],[[.2,0],[.4,0],[.4,.2]],[[.6,.6],[.8,.6],[.6,.8]]],float)
        self.assertEqual(len(set(chart_ids(uv))),3)
        labels=chart_ids(uv,'vertex');self.assertEqual(labels[0],labels[1]);self.assertNotEqual(labels[0],labels[2])
        with self.assertRaisesRegex(ValueError,'edge or vertex'):chart_ids(uv,'proximity')

    def test_own_chart_is_planar_unique_and_owns_a_1k_texel(self):
        from headkit.uv import _own_chart,raster_audit
        corners=np.array([[0,0,0],[1e-4,0,0],[0,1e-4,0]],float)
        a=_own_chart(corners,(2048,2048),10.0,0);b=_own_chart(corners,(2048,2048),10.0,1)
        self.assertFalse(np.allclose(a[0],b[0]))
        twice=abs((a[1,0]-a[0,0])*(a[2,1]-a[0,1])-(a[1,1]-a[0,1])*(a[2,0]-a[0,0]))
        perimeter=sum(np.linalg.norm(a[k]-a[(k+1)%3]) for k in range(3))
        self.assertGreaterEqual(twice/perimeter*1024,1.5-1e-9)
        placed=(a-a.min(0))[None]+.25;report,_=raster_audit(placed,1024)
        self.assertEqual(report['unmappedUvFaces'],[])

    def test_imported_and_new_atlases_reject_unsampled_faces_at_each_resolution(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0]],float)
        value={'positions':p,'faces':np.array([[0,1,2]]),'normals':np.zeros((3,3)),
               'uv':np.array([[[.01,.01],[.02,.01],[.01,.02]]])}
        for reuse,size in ((True,4096),(True,2048),(True,1024),(False,4096)):
            with self.subTest(reuse=reuse,size=size):
                def audit(uv,current_size):
                    return {'overlapFaces':[],'degenerateUvFaces':[],
                            'unmappedUvFaces':[0] if size==current_size else [],'coverageFraction':.5},None
                runner=SimpleNamespace(data={'mesh':{'reuseReviewedUvs':reuse}},bindings={},source=lambda *args:'fixture')
                with patch('headkit.gltf.mesh',return_value=value),patch('headkit.gltf.write_mesh') as save, \
                     patch('headkit.uv.raster_audit',side_effect=audit), \
                     patch('headkit.uv.gutter_audit',return_value={'nearbyChartPixelsByRadius':{'1':0}}), \
                     patch('headkit.uv.unwrap',return_value=(value,{})):
                    with self.assertRaisesRegex(ValueError,'UV audit failed|failed UV audit'):
                        Runner._execute(runner,'unwrap',self.root)
                    save.assert_not_called()

    def test_padding_fills_only_unmapped_pixels_and_preserves_black(self):
        values=np.zeros((4,4,3),np.uint8);values[1,1]=[0,0,0];values[2,2]=[80,90,100];mask=np.zeros((4,4),bool);mask[1,1]=mask[2,2]=True
        result=pad(values,mask);np.testing.assert_array_equal(result[mask],values[mask]);np.testing.assert_array_equal(result[0,0],[0,0,0])


class InputInventoryTests(Temporary):
    def input_paths(self,local):
        from headkit.__main__ import main
        source=pin(self.file('geometry.glb'));manifest_path=self.root/'manifest.json'
        write(manifest_path,{'schemaVersion':1,'id':'installed-inventory',
              'inputs':{'geometry':{'path':'geometry.glb','sha256':source['sha256']}}})
        bindings_path=self.root/'bindings.json';write(bindings_path,local)
        output=self.root/'inputs.json'
        with patch('sys.argv',['headkit','inputs','--manifest',str(manifest_path),
              '--bindings',str(bindings_path),'--output',str(output)]):
            main()
        return read(output)

    def installed_adapter(self):
        adapter=self.root/'custom_nodes'/'srn_headkit';adapter.mkdir(parents=True)
        (adapter/'__init__.py').write_text('# installed adapter')
        return adapter,self.bindings_data(comfyCustomNodes=str(adapter.parent))

    def test_inputs_lists_installed_snapshot_and_detects_its_mutation(self):
        from headkit.common import verify
        adapter,local=self.installed_adapter();snapshot=adapter/'source-roots.json'
        write(snapshot,{'schemaVersion':1,'inventory':{'files':[]}})
        paths=self.input_paths(local)
        self.assertEqual(paths.count(str(snapshot.resolve())),1)
        self.assertIn(str((adapter/'__init__.py').resolve()),paths)
        frozen=[pin(path) for path in paths];verify(frozen)
        write(snapshot,{'schemaVersion':1,'inventory':{'files':['changed']}})
        with self.assertRaisesRegex(ValueError,'Stale file pin: .*source-roots.json'):
            verify(frozen)

    def test_inputs_skips_receipts_from_other_code_instead_of_failing(self):
        from headkit.__main__ import main
        from headkit.common import source_version,digest,manifest
        source=pin(self.file('geometry.glb'));manifest_path=self.root/'manifest.json'
        write(manifest_path,{'schemaVersion':1,'id':'stale-run','inputs':{'geometry':{'path':'geometry.glb','sha256':source['sha256']}}})
        bindings_path=self.root/'bindings.json';write(bindings_path,self.bindings_data())
        run=self.root/'run';run.mkdir();changed=self.file('changed.py','old helper')
        old_pin=pin(changed);changed.write_text('helper edited since that receipt')
        current=self.file('current.json','current output')
        rows={}
        for stage,code,inputs in (('repair','old-code',[old_pin]),('unwrap',source_version(),[pin(current)])):
            path=run/f'{stage}.json';write(path,{'codeVersion':code,'manifestHash':digest(manifest(manifest_path)),'inputs':inputs,'outputs':[]});rows[stage]=pin(path)
        write(run/'state.json',{'schemaVersion':1,'id':'stale-run','stages':rows})
        output=self.root/'inputs.json'
        with patch('sys.argv',['headkit','inputs','--manifest',str(manifest_path),'--bindings',str(bindings_path),
              '--output',str(output),'--run',str(run)]),patch('builtins.print') as shown:
            main()
        paths=read(output);self.assertIn(str(current.resolve()),paths);self.assertNotIn(str(changed.resolve()),paths)
        self.assertNotIn(str((run/'state.json').resolve()),paths)
        self.assertIn('"staleStagesSkipped": [\n    "repair"\n  ]',shown.call_args.args[0])

    def test_inputs_requires_the_declared_installed_snapshot(self):
        adapter,local=self.installed_adapter()
        with self.assertRaises(FileNotFoundError):self.input_paths(local)
        self.assertFalse((self.root/'inputs.json').exists())

    def test_inputs_lists_all_python_package_files(self):
        from headkit.__main__ import main
        from headkit.common import sha
        source=self.file('geometry.glb')
        manifest_path=self.root/'manifest.json'
        write(manifest_path,{'schemaVersion':1,'id':'input-inventory',
              'inputs':{'geometry':{'path':source.name,'sha256':sha(source)}}})
        local=self.bindings_data()
        bindings_path=self.root/'bindings.json';write(bindings_path,local)
        output=self.root/'inputs.json'
        with patch('sys.argv',['headkit','inputs','--manifest',str(manifest_path),
              '--bindings',str(bindings_path),'--output',str(output)]):
            main()
        paths=json.loads(output.read_text())
        for item in local['pythonPackages']['files']:
            self.assertIn(str(Path(item['path']).resolve()),paths)


class LocalBindingSecurityTests(Temporary):
    def test_embree_must_resolve_inside_declared_tools_root(self):
        from headkit.common import bindings
        tools=self.root/'tools';tools.mkdir();inside=tools/'embree.dll';inside.write_bytes(b'bound Embree')
        outside=self.root/'outside'/'embree.dll';outside.parent.mkdir();outside.write_bytes(b'other Embree')
        path=self.root/'bindings.json'
        write(path,{'schemaVersion':1,'toolsRoot':str(tools),'embree':pin(inside)})
        self.assertEqual(bindings(path)['embree'],pin(inside))
        write(path,{'schemaVersion':1,'toolsRoot':str(tools),'embree':pin(outside)})
        with self.assertRaisesRegex(ValueError,'Embree DLL must be inside'):
            bindings(path)


class UvBindingTests(Temporary):
    def test_source_group_budget_keeps_head_default_and_local_fraction_limit(self):
        from headkit.uv import _local_groups
        faces=np.arange(3000).reshape(1000,3)
        with self.assertRaisesRegex(ValueError,'fragment'):_local_groups(faces,range(18))
        self.assertEqual(len(_local_groups(faces,range(18),maximum_groups=128)),19)
        with self.assertRaisesRegex(ValueError,'bounded local'):_local_groups(faces,range(40),maximum_groups=128)
    def test_invalid_source_group_policy_is_rejected_before_loading_library(self):
        from headkit.uv import unwrap
        for value in (True,1,257,128.0):
            with self.assertRaisesRegex(ValueError,'group limit'):unwrap({}, {}, {'maximumLocalGroups':value})
    def test_atlas_patches_use_only_their_vertices_and_preserve_ordered_geometry(self):
        from headkit.uv import _pack
        class Atlas:
            def __init__(self):self.meshes=[];self.atlas_count=1;self.width=self.height=2048
            def add_mesh(self,vertices,indices):self.meshes.append((vertices.copy(),indices.copy()))
            def generate(self,**kwargs):pass
            def __getitem__(self,index):
                vertices,indices=self.meshes[index]
                return np.arange(len(vertices)),indices,vertices[:,:2]
            def get_mesh_chart_count(self,index):return 1
        atlas=Atlas();module=SimpleNamespace(Atlas=lambda:atlas,ChartOptions=SimpleNamespace,PackOptions=SimpleNamespace)
        vertices=np.random.default_rng(4).random((100,3)).astype(np.float32)
        faces=np.array([[50,60,70],[1,2,3]],np.uint32)
        uv,_,_=_pack(module,vertices,faces,[np.array([0]),np.array([1])])
        self.assertEqual([len(v) for v,_ in atlas.meshes],[3,3])
        np.testing.assert_array_equal(uv,vertices[faces][:,:,:2])
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
    def test_library_rejects_unpinned_package_and_native_files(self):
        from headkit.common import library
        directory=self.root/'tools-bank'/'libraries';package=directory/'pymeshlab';package.mkdir(parents=True)
        entry=package/'__init__.py';entry.write_text('from . import helper')
        helper=package/'helper.py';helper.write_text('value = 1')
        native=package/'pymeshlab.pyd';native.write_bytes(b'native extension')
        bindings={'toolsRoot':str(self.root/'tools-bank'),'libraries':{'pymeshlab':{
            'directory':str(directory),'files':[pin(entry)]}}}
        with patch('headkit.common.importlib.import_module') as importer:
            with self.assertRaisesRegex(ValueError,'complete installation membership'):
                library(bindings,'pymeshlab')
            importer.assert_not_called()
    def test_library_accepts_exact_recursive_inventory_and_restores_import_state(self):
        from headkit.common import library
        directory=self.root/'tools-bank'/'libraries';package=directory/'xatlas';package.mkdir(parents=True)
        entry=package/'__init__.py';entry.write_text('from . import helper')
        helper=package/'helper.py';helper.write_text('value = 1')
        native=package/'xatlas.pyd';native.write_bytes(b'native extension')
        files=[pin(path) for path in sorted(directory.rglob('*')) if path.is_file()]
        bindings={'toolsRoot':str(self.root/'tools-bank'),'libraries':{'xatlas':{
            'directory':str(directory),'files':files}}}
        module=SimpleNamespace(__file__=str(entry.resolve()))
        import sys
        write_bytecode=sys.dont_write_bytecode
        with patch('headkit.common.importlib.import_module',return_value=module) as importer:
            self.assertIs(library(bindings,'xatlas'),module)
            importer.assert_called_once_with('xatlas')
        self.assertEqual(sys.dont_write_bytecode,write_bytecode)
    def test_uv_import_rejects_cached_module_from_another_installation(self):
        from headkit.uv import unwrap
        bindings=self.fixture(self.root/'tools-bank'/'libraries');unexpected=self.file('unexpected-xatlas.py')
        with patch('headkit.common.importlib.import_module',return_value=SimpleNamespace(__file__=str(unexpected))):
            with self.assertRaisesRegex(ValueError,'byte-bound module'):unwrap({},bindings)
    def test_uv_import_uses_the_pinned_tools_bank_module(self):
        from headkit.uv import unwrap
        bindings=self.fixture(self.root/'tools-bank'/'libraries');module=SimpleNamespace(__file__=bindings['libraries']['xatlas']['files'][0]['path'])
        with patch('headkit.uv.physical_fans',return_value=(np.zeros((3,3)),np.array([[0,1,2]]))), \
             patch('headkit.uv._chart',side_effect=RuntimeError('verified pack reached')) as pack, \
             patch('headkit.common.importlib.import_module',return_value=module) as importer:
            with self.assertRaisesRegex(RuntimeError,'verified pack reached'):unwrap({},bindings)
            importer.assert_called_once_with('xatlas');self.assertIs(pack.call_args.args[0],module)


class AppearanceTests(Temporary):
    def test_saved_batch_zero_field_matches_xyz_without_changing_transport(self):
        coords=np.array([[0,0,0],[1,0,0]],dtype=np.int32);attrs=np.array([[.2]*6,[.8]*6])
        batched=np.c_[np.zeros(len(coords),np.int32),coords];before=batched.copy()
        direct=GeneratedField.from_saved(coords,attrs,2)
        saved=GeneratedField.from_saved(batched,attrs,2)
        np.testing.assert_array_equal(saved.sample([[0,-.25,-.25]])[0],direct.sample([[0,-.25,-.25]])[0])
        np.testing.assert_array_equal(batched,before)
        with self.assertRaises(ValueError):GeneratedField(batched,attrs,2)
    def test_saved_batch_field_rejects_mixed_nonzero_or_float_batch_coordinates(self):
        attrs=np.ones((2,6))*.2
        for coords in (np.array([[0,0,0,0],[1,1,0,0]]),np.array([[1,0,0,0],[1,1,0,0]]),
                       np.zeros((2,4),dtype=float)):
            with self.assertRaisesRegex(ValueError,'batch-zero'):GeneratedField.from_saved(coords,attrs,2)
    def test_saved_batch_field_preserves_duplicate_and_range_checks(self):
        for coords in (np.zeros((2,4),int),np.array([[0,0,0,0],[0,2,0,0]])):
            with self.assertRaises(ValueError):GeneratedField.from_saved(coords,np.ones((2,6))*.2,2)
    def test_trilinear_interpolation_clamps_after_weighting(self):
        coords=np.array([[0,0,0],[1,0,0]]);attrs=np.array([[-.2]*6,[.8]*6])
        with self.assertRaises(ValueError):GeneratedField(coords,attrs,2)
        field=GeneratedField(coords,attrs,2,True);sample,fallback=field.sample([[0,-.25,-.25]])
        np.testing.assert_allclose(sample,.3,atol=1e-6);self.assertFalse(fallback[0])
    def test_nearest_field_fallback_is_counted(self):
        field=GeneratedField(np.array([[0,0,0]]),np.ones((1,6))*.2,4)
        values,fallback=field.sample([[.49,.49,.49]]);self.assertTrue(fallback[0]);np.testing.assert_allclose(values,.2)
    def test_nearest_fallback_matches_brute_force_on_sparse_fields(self):
        rng=np.random.default_rng(15)
        for trial in range(6):
            R=int(rng.integers(6,20));occupied=np.zeros((R,R,R),bool)
            for _ in range(3):  # solid blocks give interior voxels the fallback tree must skip
                lo=rng.integers(0,R-2,3);occupied[tuple(slice(a,a+int(rng.integers(2,5))) for a in lo)]=True
            occupied[tuple(rng.integers(0,R,(3,8)))]=True
            coords=np.argwhere(occupied);attrs=rng.random((len(coords),6))
            field=GeneratedField(coords,attrs,R)
            lattice=(rng.integers(-3,R+3,(64,3))+rng.integers(0,3,(64,3))/2+.5)/R-.5  # exact ties on half cells
            points=np.r_[rng.uniform(-.6,.6,(400,3)),rng.uniform(-4,4,(100,3)),lattice].astype(np.float32)
            values,fallback=field.sample(points,chunk=97)
            grid=(points+.5)*R-.5;base=np.floor(grid).astype(int);frac=grid-base;weight=np.zeros(len(points))
            for corner in np.ndindex(2,2,2):
                cc=base+corner;inside=((cc>=0)&(cc<R)).all(1)
                weight+=np.where(inside,occupied[tuple(cc.clip(0,R-1).T)],False)*np.prod(np.where(corner,frac,1-frac),axis=1)
            np.testing.assert_array_equal(fallback,weight<=1e-8)
            self.assertTrue(fallback.sum()>100)
            keys=(coords[:,0]*R+coords[:,1])*R+coords[:,2];centres=(coords+.5)/R-.5
            for point,value in zip(points[fallback],values[fallback]):
                squared=((centres-point.astype(np.float64))**2).sum(axis=1)
                tied=np.flatnonzero(squared==squared.min());expected=tied[np.argmin(keys[tied])]
                np.testing.assert_array_equal(value,np.clip(attrs[expected],0,1).astype(np.float32))
    def test_nearest_fallback_tie_takes_lowest_key(self):
        field=GeneratedField(np.array([[4,0,0],[0,0,0],[2,0,4]]),np.array([[.1]*6,[.2]*6,[.3]*6]),8)
        values,fallback=field.sample([[(2+.5)/8-.5,(0+.5)/8-.5,(0+.5)/8-.5]])
        self.assertTrue(fallback[0]);np.testing.assert_allclose(values,.2)
    def test_duplicate_voxel_is_rejected(self):
        with self.assertRaises(ValueError):GeneratedField(np.zeros((2,3),int),np.ones((2,6)),4)
    def test_saved_field_batch_column_is_dropped(self):
        # HeadkitSaveFieldV1 stores Trellis sparse coords as (batch,x,y,z).
        np.savez(self.root/'saved.npz',coords=np.array([[0,0,0,0],[0,1,0,0]],np.int32),
                 attrs=np.array([[.2]*6,[.6]*6],np.float16),resolution=2)
        field=load_generated_field(self.root/'saved.npz')
        np.testing.assert_array_equal(np.sort(field.keys),[0,4])
        values,fallback=field.sample([[0,-.25,-.25]]);np.testing.assert_allclose(values,.4,atol=1e-3);self.assertFalse(fallback[0])
        np.savez(self.root/'plain.npz',coords=np.array([[0,0,0]]),attrs=np.ones((1,6))*.5,resolution=2)
        self.assertEqual(load_generated_field(self.root/'plain.npz').resolution,2)
    def test_saved_field_with_second_batch_is_rejected(self):
        np.savez(self.root/'two.npz',coords=np.array([[0,0,0,0],[1,0,0,0]],np.int32),attrs=np.ones((2,6)),resolution=2)
        with self.assertRaisesRegex(ValueError,'exactly one batch'):load_generated_field(self.root/'two.npz')
    def test_subtexel_face_passes_only_inside_its_own_chart_and_bound(self):
        from headkit.uv import raster_audit,subtexel_audit
        big=[[0,0],[8.3,0],[0,8.3]]
        attached=[[8.3,0],[0,8.3],[4.22,4.22]]      # shares the hypotenuse: same chart, owns no texel centre
        loose=[[8.4,0.05],[0.05,8.4],[4.27,4.27]]   # same spot, no shared edge: another chart
        for third,own in ((attached,True),(loose,False)):
            with self.subTest(own=own):
                uv=np.array([big,third],float)/16;report,owners=raster_audit(uv,16)
                self.assertEqual(report['unmappedUvFaces'],[1])
                self.assertEqual(subtexel_audit(uv,16,report,owners,.02)['passed'],own)
        uv=np.array([big,attached],float)/16;report,owners=raster_audit(uv,16)
        result=subtexel_audit(uv,16,report,owners,0.0)
        self.assertFalse(result['passed']);self.assertEqual((result['count'],result['limit']),(1,0))
        with self.assertRaisesRegex(ValueError,'0..2%'):subtexel_audit(uv,16,report,owners,.05)
    def test_bake_rejects_unmapped_1k_faces_before_writing_output(self):
        np.savez(self.root/'field.npz',coords=np.array([[0,0,0,0]],np.int32),attrs=np.ones((1,6))*.5,resolution=2)
        value={'positions':np.eye(3),'faces':np.array([[0,1,2]]),'uv':np.array([[[0,0],[1,0],[0,1]]],float)}
        def gated(_,size,*__):
            if size==1024:raise ValueError('UV overlap/degeneracy or unmapped faces block baking')
            return np.zeros((size,size,3),np.float32),np.zeros((size,size),np.int32),{}
        with patch('headkit.textures.mesh',return_value=value),patch('headkit.textures.surface',side_effect=gated):
            with self.assertRaisesRegex(ValueError,'unmapped'):bake('mesh.glb',self.root/'field.npz',self.root/'maps')
        self.assertFalse((self.root/'maps').exists())
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
    def test_projection_uses_the_reviewed_subtexel_allowance(self):
        from headkit.palette import project_ownership
        embree=pin(self.file('embree.dll'));stop=ValueError('surface gate reached')
        with patch('headkit.palette.mesh',return_value='uv'),patch('headkit.palette.surface',side_effect=stop) as gate:
            with self.assertRaisesRegex(ValueError,'surface gate'):project_ownership('unused',[],embree,self.root/'p.png',max_subtexel_fraction=.01)
        gate.assert_called_once_with('uv',1024,.01)
        source=self.file('uv.glb','frozen UV mesh')
        runner=SimpleNamespace(data={'mesh':{'maximumSubtexelFraction':.01},'ownership':{'reviewed':True,'mode':'project',
            'sourceSha256':pin(source)['sha256'],'views':[{'maskInput':'front'}]}},bindings={'embree':embree},
            source=lambda *args:source,input=lambda role:'mask-'+role)
        with patch('headkit.palette.project_ownership',side_effect=stop) as project:
            with self.assertRaisesRegex(ValueError,'surface gate'):Runner._execute(runner,'ownership',self.root)
        self.assertEqual(project.call_args.kwargs,{'max_subtexel_fraction':.01})
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


class LoaderResolutionTests(Temporary):
    def test_comfy_folder_resolver_must_select_the_bound_path_and_bytes(self):
        from headkit.comfy_nodes.model_resolution import loader_models,verify_loader_models
        name='pixal3d_int8_convrot.safetensors'
        bound=self.root/'reviewed'/name;bound.parent.mkdir();bound.write_bytes(b'reviewed model')
        shadow=self.root/'shadow'/name;shadow.parent.mkdir();shadow.write_bytes(b'different model')
        graph={'1':{'class_type':'UNETLoader','inputs':{'unet_name':name}}}
        expected=loader_models(graph,{name:pin(bound)},{name:pin(bound)['sha256']})
        class FolderPaths:
            selected=shadow
            @classmethod
            def get_full_path_or_raise(cls,category,filename):
                self.assertEqual((category,filename),('diffusion_models',name))
                return cls.selected
        with self.assertRaisesRegex(ValueError,'different model path'):
            verify_loader_models(expected,FolderPaths)
        FolderPaths.selected=bound
        bound_graph=__import__('headkit.comfy_nodes.model_resolution',fromlist=['bind_loader_models']).bind_loader_models(graph,expected)
        self.assertEqual(verify_loader_models(expected,FolderPaths,bound_graph),{'verified':True,'count':1})
        with self.assertRaisesRegex(ValueError,'hash-keyed headkit adapter'):
            verify_loader_models(expected,FolderPaths,graph)
        tampered=copy.deepcopy(bound_graph);tampered['1']['inputs']['headkit_model_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'inputs differ'):
            verify_loader_models(expected,FolderPaths,tampered)
        shadow.write_bytes(b'modified after resolution')
        FolderPaths.selected=shadow
        expected[0]['pathIdentity']=__import__('headkit.comfy_nodes.model_resolution',fromlist=['path_identity']).path_identity(shadow)
        with self.assertRaisesRegex(ValueError,'bytes differ'):
            verify_loader_models(expected,FolderPaths)

    def test_model_hash_is_bound_into_loader_type_and_cache_signature(self):
        from headkit.comfy_nodes.model_resolution import loader_models,bind_loader_models,validate_bound_loader_nodes
        from headkit.comfy_nodes.verified_loaders import verified_loader_mappings
        name='pixal3d_int8_convrot.safetensors';model=self.root/name;model.write_bytes(b'reviewed model')
        standard={'1':{'class_type':'UNETLoader','inputs':{'unet_name':name,'weight_dtype':'default'}}}
        expected=loader_models(standard,{name:pin(model)},{name:pin(model)['sha256']})
        graph=bind_loader_models(standard,expected);node=graph['1']
        self.assertEqual(node['class_type'],'HeadkitVerifiedUNETLoaderV1')
        self.assertTrue(validate_bound_loader_nodes(graph,expected))
        self.assertEqual(node['inputs']['headkit_model_sha256'],expected[0]['sha256'])
        class FolderPaths:
            @classmethod
            def get_full_path_or_raise(cls,category,filename):return model
        class CoreLoader:
            RETURN_TYPES=('MODEL',);FUNCTION='load_unet'
            @classmethod
            def INPUT_TYPES(cls):return {'required':{'unet_name':(['model.safetensors'],),'weight_dtype':(['default'],)}}
            def load_unet(self,unet_name,weight_dtype):return ('loaded',unet_name,weight_dtype)
        wrapper=verified_loader_mappings({'UNETLoader':CoreLoader},FolderPaths)['HeadkitVerifiedUNETLoaderV1']
        first=wrapper.IS_CHANGED(expected[0]['sha256'],expected[0]['pathIdentity'])
        changed=wrapper.IS_CHANGED('0'*64,expected[0]['pathIdentity'])
        self.assertNotEqual(first,changed)
        self.assertEqual(wrapper().load_verified(expected[0]['sha256'],expected[0]['pathIdentity'],
            unet_name=name,weight_dtype='default'),('loaded',name,'default'))
        model.write_bytes(b'replaced model')
        with self.assertRaisesRegex(ValueError,'bytes different'):
            wrapper().load_verified(expected[0]['sha256'],expected[0]['pathIdentity'],
                unet_name=name,weight_dtype='default')

    def test_unrecognized_model_loader_fields_fail_closed(self):
        from headkit.comfy_nodes.model_resolution import loader_models
        graph={'1':{'class_type':'CustomLoader','inputs':{'model_name':'unlisted.safetensors'}}}
        with self.assertRaisesRegex(ValueError,'Unsupported Comfy model loader field'):
            loader_models(graph,{}, {})

    def test_sampler_name_is_an_algorithm_selector_not_a_model_file(self):
        from headkit.comfy_nodes.model_resolution import loader_models
        graph={'1':{'class_type':'KSampler','inputs':{'sampler_name':'euler','steps':12}}}
        self.assertEqual(loader_models(graph,{},{}),[])


class FakeClient:
    def __init__(self,fail=False,on_idle=None,model_result=None):
        self.fail=fail;self.posts=0;self.url='http://127.0.0.1:8188';self.on_idle=on_idle;self.model_result=model_result;self.routes=[];self.server_runtime=None
    def idle(self):
        if self.on_idle:self.on_idle()
        return True
    def request(self,route,data=None):
        self.routes.append((route,data))
        if route=='/object_info':return {'Example':{},'UNETLoader':{},'HeadkitVerifiedUNETLoaderV1':{}}
        if route=='/headkit/runtime-identity':return self.server_runtime
        if route=='/headkit/verify-loader-models':
            return self.model_result if self.model_result is not None else {'verified':True,'count':len(data['models'])}
        if route=='/prompt':
            self.posts+=1
            if self.fail:raise TimeoutError('lost acknowledgement')
            return {'prompt_id':'prompt-1','node_errors':{}}
        if route.startswith('/history'):return {}
        if route=='/queue':return {'queue_running':[],'queue_pending':[]}
        return {}


class LedgerTests(Temporary):
    def prepared(self,token='token-1'):return self.freeze_request({'token':token,'stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(self.file('input'))]})
    def test_ambiguous_submission_stays_counted_and_blocks_duplicates(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,74,'Reviewed retained ledger');request=self.prepared();client=FakeClient(True)
        with self.assertRaises(TimeoutError):self.submit(client,ledger,request,self.root/'job')
        self.assertEqual(read(ledger)['jobs'][0]['state'],'intent')
        with self.assertRaisesRegex(ValueError,'Reconcile'):self.submit(client,ledger,request,self.root/'another')
        self.assertEqual(client.posts,1)
    def test_generation_ceiling_and_queue_ownership(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,100,'Existing global count');client=FakeClient()
        with self.assertRaisesRegex(ValueError,'100'):self.submit(client,ledger,self.prepared(),self.root/'job')
        self.assertEqual(client.posts,0)
    def test_request_is_frozen_before_submission(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'New environment');request=self.prepared();Path(request['inputs'][0]['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Stale'):self.submit(FakeClient(),ledger,request,self.root/'job')
    def test_existing_intent_receipt_does_not_publish_ledger_intent(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'New environment')
        request=self.prepared();client=FakeClient();output=self.root/'job';output.mkdir()
        receipt=output/'submission-intent.json';receipt.write_text('preserve historical receipt')
        with self.assertRaises(FileExistsError):self.submit(client,ledger,request,output)
        self.assertEqual(read(ledger)['jobs'],[])
        self.assertEqual(receipt.read_text(),'preserve historical receipt')
        self.assertEqual(client.posts,0)
        self.assertNotIn('/prompt',[route for route,_ in client.routes])
    def test_dispatch_requires_the_prepared_runtime_bindings_and_endpoint(self):
        for mismatch in ('runtime','bindings','endpoint'):
            with self.subTest(mismatch=mismatch):
                request=self.prepared('token-'+mismatch);client=FakeClient();runtime,bindings=self.bind_dispatch(request,client.url)
                if mismatch=='runtime':runtime=dict(runtime,toolsRoot=str(self.root/'different-runtime'))
                elif mismatch=='bindings':bindings=self.file('other-bindings.json','{}')
                else:client.url='http://localhost:8188'
                with patch.object(client,'request') as server:
                    with self.assertRaisesRegex(ValueError,'differ'):
                        comfy.submit(client,self.root/'ledger.json',request,self.root/('job-'+mismatch),
                                     runtime_identity=runtime,bindings_path=bindings)
                    server.assert_not_called()
    def test_inputs_are_reverified_under_lock_immediately_before_dispatch(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,99,'One attempt remains');request=self.prepared()
        source=request['inputs'][0]['path'];client=FakeClient(on_idle=lambda:Path(source).write_text('changed during queue check'))
        with self.assertRaisesRegex(ValueError,'Stale file pin'):
            self.submit(client,ledger,request,self.root/'preflight-failed')
        state=read(ledger);self.assertEqual(state['jobs'][0]['state'],'preflight-rejected');self.assertEqual(client.posts,0)
        self.assertTrue((self.root/'preflight-failed'/'submission-preflight-error.json').exists())
        self.assertEqual(state['priorGenerationAttempts']+sum(j['stage']=='geometry' and j['state']!='preflight-rejected' for j in state['jobs']),99)
        next_request=self.prepared('token-after-preflight');next_client=FakeClient()
        self.submit(next_client,ledger,next_request,self.root/'valid-dispatch')
        self.assertEqual(next_client.posts,1);self.assertEqual(read(ledger)['jobs'][-1]['state'],'submitted')
    def test_comfy_runtime_files_are_pinned_and_reverified_under_lock_before_dispatch(self):
        ledger=self.root/'runtime-inputs.json';comfy.initialize_ledger(ledger,0,'Reviewed generation count')
        request=self.prepared();runtime_file=request['comfyRuntimeIdentity']['torch']['path']
        client=FakeClient(on_idle=lambda:Path(runtime_file).write_bytes(b'changed after runtime snapshot'))
        with self.assertRaisesRegex(ValueError,'Stale file pin'):
            self.submit(client,ledger,request,self.root/'runtime-input-preflight')
        self.assertEqual(read(ledger)['jobs'][0]['state'],'preflight-rejected')
        self.assertEqual(client.posts,0)
        self.assertIn((runtime_file,request['comfyRuntimeIdentity']['torch']['sha256']),
                      {(row['path'],row['sha256']) for row in request['inputs']})

    def test_live_comfy_runtime_mismatch_is_preflight_rejected(self):
        from headkit.common import digest
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'Reviewed generation count')
        request=self.prepared();client=FakeClient();_,bindings=self.bind_dispatch(request,client.url)
        changed=copy.deepcopy(request['comfyRuntimeIdentity']);changed['torch']['version']='different loaded Torch'
        payload={key:value for key,value in changed.items() if key!='fingerprint'}
        changed['fingerprint']=digest(payload);client.server_runtime=changed
        with self.assertRaisesRegex(ValueError,'runtime differs'):
            comfy.submit(client,ledger,request,self.root/'runtime-mismatch',runtime_identity=request['runtimeIdentity'],bindings_path=bindings)
        self.assertEqual(read(ledger)['jobs'][0]['state'],'preflight-rejected')
        self.assertEqual(client.posts,0)
        self.assertIn('/headkit/runtime-identity',[route for route,_ in client.routes])

    def test_server_owned_runtime_is_reverified_under_lock_without_client_file_reads(self):
        ledger=self.root/'server-owned-ledger.json';comfy.initialize_ledger(ledger,0,'Reviewed generation count')
        request=self.prepared();request['runtimeVerification']='server-owned'
        runtime_file=request['comfyRuntimeIdentity']['torch']['path']
        request['inputs']=[row for row in request['inputs'] if row['path']!=runtime_file]
        client=FakeClient()
        def change_runtime():
            changed=copy.deepcopy(client.server_runtime)
            changed['torch']['sha256']='0'*64
            for row in changed['files']:
                if row['path']==runtime_file:row['sha256']='0'*64
            changed['fingerprint']=digest({k:v for k,v in changed.items() if k!='fingerprint'})
            client.server_runtime=changed
        client.on_idle=change_runtime
        with self.assertRaisesRegex(ValueError,'runtime differs'):
            self.submit(client,ledger,request,self.root/'server-owned-job')
        self.assertEqual(read(ledger)['jobs'][0]['state'],'preflight-rejected')
        self.assertEqual(client.posts,0)
    def test_restarted_session_and_changed_settings_block_dispatch_without_attempt(self):
        for field,value in (('id','b'*32),('settingsSha256','c'*64),('pid',456)):
            with self.subTest(field=field):
                ledger=self.root/(field+'-ledger.json');comfy.initialize_ledger(ledger,0,'Reviewed count')
                request=self.prepared();client=FakeClient();_,bindings=self.bind_dispatch(request,client.url)
                changed=copy.deepcopy(request['comfyRuntimeIdentity']);changed['session'][field]=value
                changed['fingerprint']=digest({key:value for key,value in changed.items() if key!='fingerprint'})
                client.server_runtime=changed
                with self.assertRaisesRegex(ValueError,'runtime differs'):
                    comfy.submit(client,ledger,request,self.root/(field+'-job'),runtime_identity=request['runtimeIdentity'],bindings_path=bindings)
                self.assertEqual(client.posts,0);self.assertEqual(read(ledger)['priorGenerationAttempts'],0)
                self.assertEqual(read(ledger)['jobs'][0]['state'],'preflight-rejected')

    def test_loader_resolved_checkpoint_mismatch_is_preflight_rejected(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,0,'Reviewed count')
        request=self.prepared();model=self.file('pixal3d_int8_convrot.safetensors','reviewed bytes')
        from headkit.comfy_nodes.model_resolution import path_identity
        row=pin(model);request['inputs'].append(row)
        from headkit.comfy_nodes.model_resolution import bind_loader_models
        standard={'1':{'class_type':'UNETLoader','inputs':{'unet_name':model.name}}}
        request['loaderModels']=[{'category':'diffusion_models','name':model.name,
            'pathIdentity':path_identity(model),'sha256':row['sha256']}]
        request['prompt']=bind_loader_models(standard,request['loaderModels'])
        client=FakeClient(model_result={'verified':False})
        original_read=comfy.read
        def read_with_test_profile(path):
            return {model.name:row['sha256']} if Path(path).name=='checkpoints.json' else original_read(path)
        with patch('headkit.comfy.read',side_effect=read_with_test_profile):
            with self.assertRaisesRegex(ValueError,'resolved checkpoint paths or bytes'):
                self.submit(client,ledger,request,self.root/'preflight')
        state=read(ledger);self.assertEqual(state['jobs'][0]['state'],'preflight-rejected')
        self.assertEqual(client.posts,0)
        self.assertEqual(state['priorGenerationAttempts']+sum(j['stage']=='geometry' and j['state']!='preflight-rejected' for j in state['jobs']),0)
        self.assertIn('/headkit/verify-loader-models',[route for route,_ in client.routes])
    def test_model_loader_cannot_be_omitted_or_given_unrelated_pins(self):
        for variant in ('omitted','unrelated'):
            with self.subTest(variant=variant):
                ledger=self.root/(variant+'.json');comfy.initialize_ledger(ledger,0,'Reviewed count')
                request=self.prepared('token-'+variant)
                request['prompt']={'1':{'class_type':'UNETLoader','inputs':{'unet_name':'expected.safetensors'}}}
                if variant=='unrelated':
                    request['loaderModels']=[{'category':'diffusion_models','name':'other.safetensors',
                        'pathIdentity':'a'*64,'sha256':'b'*64}]
                client=FakeClient()
                with self.assertRaisesRegex(ValueError,'do not exactly match graph loaders'):
                    self.submit(client,ledger,request,self.root/variant)
                self.assertEqual(client.posts,0)
                self.assertNotIn('/headkit/verify-loader-models',[route for route,_ in client.routes])
    def test_live_lock_is_exclusive_and_terminated_owner_is_recoverable(self):
        ledger=self.root/'ledger.json';marker=self.root/'locked';env=os.environ.copy()
        tools_root=str(Path(__file__).resolve().parents[1]);env['PYTHONPATH']=tools_root+os.pathsep+env.get('PYTHONPATH','')
        script=('from headkit.comfy import locked; from pathlib import Path; import sys,time; '
                'p=Path(sys.argv[1]); marker=Path(sys.argv[2]); '
                'ctx=locked(p); ctx.__enter__(); marker.write_text("ready"); time.sleep(30)')
        owner=subprocess.Popen([sys.executable,'-c',script,str(ledger),str(marker)],env=env)
        try:
            deadline=time.monotonic()+10
            while not marker.exists() and owner.poll() is None and time.monotonic()<deadline:time.sleep(.05)
            self.assertTrue(marker.exists(),'child did not acquire the ledger lock')
            with self.assertRaises(FileExistsError):
                with comfy.locked(ledger):pass
        finally:
            owner.terminate();owner.wait(timeout=10)
        if os.name!='nt':self.assertTrue(Path(str(ledger)+'.lock').exists())
        with comfy.locked(ledger):pass
    def test_remote_endpoint_not_allowed(self):
        with self.assertRaises(ValueError):comfy.Client('https://untrusted.example')

    def test_failed_job_cannot_be_resubmitted_with_same_token(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,3,'Bound count');request=self.prepared();self.submit(FakeClient(),ledger,request,self.root/'job')
        state=read(ledger);state['jobs'][0]['state']='failed';write(ledger,state)
        with self.assertRaisesRegex(ValueError,'already submitted'):self.submit(FakeClient(),ledger,request,self.root/'retry')
    def test_collect_rejects_outputs_outside_owned_prefix(self):
        ledger=self.root/'ledger.json';comfy.initialize_ledger(ledger,3,'Bound count');request=self.prepared();client=FakeClient()
        self.submit(client,ledger,request,self.root/'job')
        def reply(route,data=None):
            return {'prompt-1':{'status':{'status_str':'success'},'outputs':{'1':{'files':[{'filename':'escape.glb','subfolder':'other-run','type':'output'}]}}}}
        client.request=reply
        with self.assertRaisesRegex(ValueError,'outside'):comfy.collect(client,ledger,request['token'],self.root/'comfy-output',self.root/'job')


class ItemTrialTests(Temporary):
    def setUp(self):
        super().setUp()
        self.ledger=self.root/'trial.json'
        write(self.ledger,{'schemaVersion':1,'priorGenerationAttempts':0,'jobs':[],
                          'itemTrial':{'id':'trial','maximumGeometryAttempts':2}})
        write(self.root/'dispatch-bindings.json',{'itemTrialId':'trial','submissionLedger':str(self.ledger)})
    def request(self, token, model='cougar', reference='a', stage='geometry'):
        return self.freeze_request({'token':token,'stage':stage,'outputNamespace':'itemkit',
            'generationSubject':{'id':model,'referenceSha256':reference*64},
            'prompt':{'1':{'class_type':'Example','inputs':{'filename_prefix':'itemkit/'+token+'/mesh'}}},
            'inputs':[pin(self.file('input'))]})
    def terminal(self,state='failed'):
        data=read(self.ledger);data['jobs'][-1]['state']=state;write(self.ledger,data)
    def test_five_attempt_policy_keeps_alias_history_and_blocks_sixth(self):
        state=read(self.ledger);state['itemTrial']['maximumGeometryAttempts']=5;write(self.ledger,state)
        for n,(model,ref) in enumerate((('cougar','a'),('renamed','a'),('renamed','b'),('third-name','b'),('third-name','c'))):
            self.submit(FakeClient(),self.ledger,self.request(str(n),model,ref),self.root/str(n))
            self.terminal('not-found' if n==2 else 'complete')
        client=FakeClient()
        with self.assertRaisesRegex(ValueError,'Five generation attempts'):
            self.submit(client,self.ledger,self.request('sixth','cougar','d'),self.root/'sixth')
        self.assertEqual(client.posts,0)
        self.assertEqual(len(read(self.ledger)['jobs']),5)
        self.submit(client,self.ledger,self.request('appearance',stage='appearance'),self.root/'appearance')
        self.assertEqual(client.posts,1)
    def test_two_attempts_survive_reference_changes_and_allow_another_model(self):
        for n,ref in enumerate(('a','b')):
            self.submit(FakeClient(),self.ledger,self.request(str(n),reference=ref),self.root/str(n));self.terminal()
        client=FakeClient()
        with self.assertRaisesRegex(ValueError,'Two generation attempts'):
            self.submit(client,self.ledger,self.request('third',reference='c'),self.root/'third')
        self.assertEqual(client.posts,0)
        self.submit(client,self.ledger,self.request('other',model='another-model',reference='d'),self.root/'other')
        self.assertEqual(client.posts,1)
    def test_uncertain_post_counts_after_reconciliation(self):
        with self.assertRaises(TimeoutError):
            self.submit(FakeClient(True),self.ledger,self.request('uncertain'),self.root/'uncertain')
        with self.assertRaisesRegex(ValueError,'Reconcile'):
            self.submit(FakeClient(),self.ledger,self.request('blocked'),self.root/'blocked')
        self.terminal('not-found')
        self.submit(FakeClient(),self.ledger,self.request('second'),self.root/'second');self.terminal()
        with self.assertRaisesRegex(ValueError,'Two generation attempts'):
            self.submit(FakeClient(),self.ledger,self.request('third'),self.root/'third')
    def test_preflight_rejection_does_not_spend_attempt(self):
        request=self.request('preflight');source=request['inputs'][0]['path']
        with self.assertRaisesRegex(ValueError,'Stale'):
            self.submit(FakeClient(on_idle=lambda:Path(source).write_text('changed')),self.ledger,request,self.root/'preflight')
        for token in ('first','second'):
            self.submit(FakeClient(),self.ledger,self.request(token),self.root/token);self.terminal()
    def test_renaming_reference_does_not_reset_attempts(self):
        for token,model,ref in (('first','cougar','a'),('second','renamed','a')):
            self.submit(FakeClient(),self.ledger,self.request(token,model,ref),self.root/token);self.terminal()
        with self.assertRaisesRegex(ValueError,'Two generation attempts'):
            self.submit(FakeClient(),self.ledger,self.request('third','renamed','b'),self.root/'third')
    def test_appearance_and_export_do_not_spend_or_require_remaining_geometry_attempt(self):
        for token,stage in (('one','geometry'),('two','geometry'),('texture','appearance'),('export','export')):
            self.submit(FakeClient(),self.ledger,self.request(token,stage=stage),self.root/token);self.terminal('success')
        self.assertEqual(len(read(self.ledger)['jobs']),4)
    def test_missing_identity_or_replacement_ledger_fails_closed(self):
        request=self.request('missing');del request['generationSubject']
        with self.assertRaisesRegex(ValueError,'stable model'):
            self.submit(FakeClient(),self.ledger,request,self.root/'missing')
        other=self.root/'replacement.json';comfy.initialize_ledger(other,0,'Unrelated ledger')
        with self.assertRaisesRegex(ValueError,'two-attempt'):
            self.submit(FakeClient(),other,self.request('replacement'),self.root/'replacement')
    def test_item_collection_accepts_only_owned_item_namespace(self):
        token='collected';request=self.request(token);client=FakeClient();job=self.root/'job'
        self.submit(client,self.ledger,request,job)
        output=self.root/'output';folder=output/'itemkit'/token;folder.mkdir(parents=True)
        (folder/'mesh.glb').write_bytes(b'geometry fixture')
        client.request=lambda *args,**kwargs:{'prompt-1':{'status':{'status_str':'success'},'outputs':{'1':{'files':[
            {'filename':'mesh.glb','subfolder':'itemkit/'+token,'type':'output'}]}}}}
        result=comfy.collect(client,self.ledger,token,output,job)
        self.assertEqual(len(result['outputs']),1)


class CollectionReceiptTests(Temporary):
    def fixture(self,server_owned=False):
        base=self.root/f'case-{len(list(self.root.glob("case-*")))}';base.mkdir()
        source=base/'input';source.write_text('frozen input');ledger=base/'ledger.json';job=base/'job';output=base/'comfy-output';token='collect-test'
        prepared=self.freeze_request({'token':token,'stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(source)]})
        if server_owned:
            prepared['runtimeVerification']='server-owned'
            server_file=prepared['comfyRuntimeIdentity']['torch']['path']
            prepared['inputs']=[row for row in prepared['inputs'] if row['path']!=server_file]
        comfy.initialize_ledger(ledger,0,'Reconciled fixture');client=FakeClient();self.submit(client,ledger,prepared,job)
        artifact=output/'headkit'/token/'mesh.glb';artifact.parent.mkdir(parents=True);artifact.write_bytes(b'exported fixture')
        history={'status':{'status_str':'success'},'outputs':{'1':{'files':[{'filename':'mesh.glb','subfolder':'headkit/'+token,'type':'output'}]}}}
        client.request=lambda route,data=None: (client.server_runtime if route=='/headkit/runtime-identity' else
            {'devices':[]} if route=='/system_stats' else {'prompt-1':history})
        return client,ledger,token,output,job,artifact
    def test_server_owned_runtime_is_checked_once_at_fresh_completion_only(self):
        client,ledger,token,output,job,_=self.fixture(server_owned=True)
        with patch.object(comfy,'verify_comfy_runtime',wraps=comfy.verify_comfy_runtime) as runtime:
            result=comfy.collect(client,ledger,token,output,job)
            self.assertEqual(result['state'],'complete');runtime.assert_called_once()
            with patch.object(client,'request',side_effect=AssertionError('Terminal receipts must not repoll')):
                self.assertEqual(comfy.collect(client,ledger,token,output,job),result)
            runtime.assert_called_once()
    def test_changed_server_owned_runtime_fails_collection_and_preserves_receipt(self):
        client,ledger,token,output,job,_=self.fixture(server_owned=True)
        changed=copy.deepcopy(client.server_runtime);path=Path(changed['torch']['path']);path.write_bytes(b'changed server dependency')
        changed['torch']['sha256']=pin(path)['sha256']
        for row in changed['files']:
            if row['path']==str(path):row['sha256']=changed['torch']['sha256']
        changed['fingerprint']=digest({key:value for key,value in changed.items() if key!='fingerprint'})
        client.server_runtime=changed
        with self.assertRaisesRegex(ValueError,'runtime differs'):comfy.collect(client,ledger,token,output,job)
        result=read(job/'collection.json');self.assertEqual(result['state'],'failed-validation')
        self.assertEqual(read(ledger)['jobs'][0]['state'],'failed-validation')
        with patch.object(client,'request',side_effect=AssertionError('Failed receipt must not repoll')):
            self.assertEqual(comfy.collect(client,ledger,token,output,job),result)
    def test_repeat_collection_reuses_verified_receipt_without_server_or_writes(self):
        client,ledger,token,output,job,artifact=self.fixture();first=comfy.collect(client,ledger,token,output,job,wait=True)
        paths=[ledger,job/'history.json',job/'memory-samples.json',job/'collection.json'];before=[p.read_bytes() for p in paths]
        with patch.object(client,'request',side_effect=AssertionError('terminal collection must not poll')):
            self.assertEqual(comfy.collect(client,ledger,token,output,job),first)
        self.assertEqual([p.read_bytes() for p in paths],before);self.assertEqual(read(ledger)['jobs'][0]['collection'],pin(job/'collection.json'))
    def test_partial_history_and_memory_evidence_resume_without_overwrite(self):
        client,ledger,token,output,job,_=self.fixture()
        history=client.request('/history/prompt-1')['prompt-1']
        write(job/'history.json',history)
        write(job/'memory-samples.json',{'samples':[{'timestamp':1.0,'devices':[]}],
              'scope':'collect monitoring window only; sampled device occupancy, not exact process peak'})
        before=[(job/name).read_bytes() for name in ('history.json','memory-samples.json')]
        result=comfy.collect(client,ledger,token,output,job)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(before,[(job/name).read_bytes() for name in ('history.json','memory-samples.json')])
        self.assertEqual(read(ledger)['jobs'][0]['collection'],pin(job/'collection.json'))
    def test_changed_terminal_evidence_or_output_cannot_be_reused(self):
        for name in ('history.json','memory-samples.json','collection.json','artifact'):
            with self.subTest(name=name):
                client,ledger,token,output,job,artifact=self.fixture();comfy.collect(client,ledger,token,output,job)
                target=artifact if name=='artifact' else job/name;target.write_bytes(b'changed')
                with patch.object(client,'request',side_effect=AssertionError('must not overwrite from server')):
                    with self.assertRaisesRegex(ValueError,'Stale file pin'):comfy.collect(client,ledger,token,output,job)
                self.assertEqual(target.read_bytes(),b'changed')
    def test_unpinned_terminal_receipt_is_preserved_and_submitted_partial_receipt_recovers(self):
        client,ledger,token,output,job,_=self.fixture();comfy.collect(client,ledger,token,output,job)
        state=read(ledger);state['jobs'][0].pop('collection');write(ledger,state)
        before={p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}
        with patch.object(client,'request',side_effect=AssertionError('terminal must not poll')):
            with self.assertRaisesRegex(ValueError,'historical evidence'):comfy.collect(client,ledger,token,output,job)
        self.assertEqual(before,{p.name:p.read_bytes() for p in job.iterdir() if p.is_file()})
        state['jobs'][0]['state']='submitted';write(ledger,state)
        recovered=comfy.collect(client,ledger,token,output,job)
        self.assertEqual(recovered['state'],'complete')
        self.assertEqual(read(ledger)['jobs'][0]['collection'],pin(job/'collection.json'))
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
        request=self.freeze_request({'token':'release-race','stage':'geometry','prompt':{'1':{'class_type':'Example','inputs':{}}},'inputs':[pin(self.file('input'))]})
        return ledger,request
    def test_release_holds_submission_lock_through_idle_check_and_free(self):
        ledger,request=self.fixture();submitter=FakeClient();releaser=FakeClient();events=[]
        def blocked_submit():
            with self.assertRaises(FileExistsError):self.submit(submitter,ledger,request,self.root/'job')
            self.assertEqual(submitter.posts,0)
        def idle():events.append('idle');blocked_submit();return True
        def free(route,data=None):
            self.assertEqual(route,'/free');self.assertEqual(data,{'unload_models':True,'free_memory':True})
            events.append('free');blocked_submit();return {'freed':True}
        releaser.idle=idle;releaser.request=free
        self.assertEqual(comfy.release(releaser,ledger),{'freed':True});self.assertEqual(events,['idle','free'])
        if os.name!='nt':self.assertTrue(Path(str(ledger)+'.lock').exists())
        self.submit(submitter,ledger,request,self.root/'job');self.assertEqual(submitter.posts,1)
    def test_submission_holds_same_lock_against_release(self):
        ledger,request=self.fixture();submitter=FakeClient();releaser=FakeClient()
        with patch.object(releaser,'request') as free:
            def idle():
                with self.assertRaises(FileExistsError):comfy.release(releaser,ledger)
                return True
            submitter.idle=idle;self.submit(submitter,ledger,request,self.root/'job');free.assert_not_called()
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
    def test_failed_release_releases_os_lock_but_keeps_stable_sidecar(self):
        ledger,_=self.fixture();client=FakeClient()
        with patch.object(client,'idle',side_effect=OSError('offline')):
            with self.assertRaises(OSError):comfy.release(client,ledger)
        if os.name!='nt':self.assertTrue(Path(str(ledger)+'.lock').exists())
        self.assertEqual(comfy.release(client,ledger),{})


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


class ImportedUvTests(Temporary):
    def test_shared_import_audit_enforces_coverage_gutters_and_fragmentation(self):
        from headkit.uv import audit_imported_uvs
        value={'uv':np.zeros((1,3,2)),'faces':np.array([[0,1,2]])}
        good={'overlapFaces':[],'degenerateUvFaces':[],'unmappedUvFaces':[],'coverageFraction':.5}
        for case,message in (('coverage','coverage'),('gutters','gutters'),('charts','fragmentation')):
            with self.subTest(case=case),patch('headkit.uv.raster_audit',return_value=(dict(good,coverageFraction=.1) if case=='coverage' else good,None)),patch(
                    'headkit.uv.gutter_audit',return_value={'nearbyChartPixelsByRadius':{'1':int(case=='gutters')}}),patch(
                    'headkit.uv.chart_ids',return_value=np.arange(257) if case=='charts' else np.array([0])):
                with self.assertRaisesRegex(ValueError,message):audit_imported_uvs(value)
        with patch('headkit.uv.raster_audit',return_value=(good,None)) as raster,patch(
                'headkit.uv.gutter_audit',return_value={'nearbyChartPixelsByRadius':{'1':0}}) as gutters:
            result=audit_imported_uvs(value)
        self.assertEqual([call.args[1] for call in raster.call_args_list],[4096,2048,1024])
        self.assertEqual([call.args[1] for call in gutters.call_args_list],[4096,2048,1024])
        self.assertEqual(set(result['audits']),{'4096','2048','1024'})
        self.assertTrue(result['visualReviewRequired'])

    def test_replay_rejects_uv_overlap_before_native_preparation(self):
        from headkit.replay import replay
        p,f=MeshTests.tetra(self);source=self.root/'overlap.glb'
        write_mesh(source,p,f,np.tile([[.1,.1],[.9,.1],[.1,.9]],(4,1,1)))
        config=ReplayPinTests.fixture(self);config['source']=str(source);config['inputs'].append(pin(source))
        with patch('headkit.replay.prepare',side_effect=AssertionError('Overlapping replay reached export')) as prepare:
            with self.assertRaisesRegex(ValueError,'failed UV audit'):replay(config,self.root/'rejected')
            prepare.assert_not_called()
        self.assertFalse((self.root/'rejected'/'replay.json').exists())


class ReplayPinTests(Temporary):
    def fixture(self):
        paths={name:str(self.file(name+'.dat',name)) for name in ('source','shades','layers','binary','expectedPlt')}
        return dict(paths,id='retained',model='pfg0_head092',fit={},inputs=[pin(p) for p in paths.values()])
    def replay(self,config,output,changed=None,geometry=None):
        from headkit.replay import replay
        def prepare(source,shades,layers,fit,model,folder):
            folder.mkdir();plt=folder/'head.plt';plt.write_bytes(Path(config['expectedPlt']).read_bytes())
            expected=folder/'expected.npz';expected.write_bytes(b'fixture');return {'plt':pin(plt),'expected':pin(expected)}
        def native(*args):
            if changed:Path(config[changed]).write_text('changed during processing')
            return b'sanitized-native',{'verified':True}
        with ExitStack() as stack:
            geometry=geometry or {'topology':{'triangles':20000,'closed':True},'crossings':{'complete':True,'pairs':[]},'passed':True}
            geometry_audit=stack.enter_context(patch('headkit.replay.audit',return_value=geometry))
            stack.enter_context(patch('headkit.replay.mesh',return_value={}))
            stack.enter_context(patch('headkit.replay.audit_imported_uvs',return_value={'imported':True,'audits':{}}))
            stack.enter_context(patch('headkit.replay.prepare',side_effect=prepare))
            stack.enter_context(patch('headkit.replay.audit_native',side_effect=native))
            result=replay(config,output)
            geometry_audit.assert_called_once_with(str(Path(config['source']).resolve()))
            return result
    def test_missing_each_consumed_pin_fails_before_processing(self):
        from headkit.replay import replay
        for role in ('source','shades','layers','binary','expectedPlt'):
            config=self.fixture();config['inputs']=[p for p in config['inputs'] if Path(p['path']).resolve()!=Path(config[role]).resolve()]
            self.assertEqual(len(config['inputs']),4)
            with patch('headkit.replay.audit') as geometry_audit:
                with self.assertRaisesRegex(ValueError,'Missing replay input pin: '+role):replay(config,self.root/'missing')
                geometry_audit.assert_not_called();self.assertFalse((self.root/'missing').exists())
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


class ReplayGeometryTests(Temporary):
    def test_closed_crossing_components_fail_before_native_preparation(self):
        from headkit.replay import replay
        p,f=MeshTests.tetra(self)
        source=self.root/'crossing.glb'
        write_mesh(source,np.concatenate((p,p+[.2,.2,.2])),np.concatenate((f,f+len(p))))
        self.assertTrue(topology(mesh(source)['positions'],mesh(source)['faces'])['closed'])
        report=audit(source)
        self.assertTrue(report['crossings']['complete'])
        self.assertTrue(report['crossings']['pairs'])
        config=ReplayPinTests.fixture(self);config['source']=str(source);config['inputs'].append(pin(source))
        output=self.root/'rejected'
        with patch('headkit.replay.prepare',side_effect=AssertionError('Crossing source reached native preparation')) as prepare:
            with self.assertRaisesRegex(ValueError,'topology/collision audit'):replay(config,output)
            prepare.assert_not_called()
        self.assertFalse((output/'replay.json').exists())
        self.assertFalse((output/(config['model']+'.mdl')).exists())

    def test_incomplete_audit_and_overbudget_source_cannot_reach_export(self):
        from headkit.replay import replay
        cases=[
            ({'topology':{'triangles':8,'closed':True},'crossings':{'complete':False,'pairs':[]},'passed':False},'topology/collision audit'),
            ({'topology':{'triangles':20001,'closed':True},'crossings':{'complete':True,'pairs':[]},'passed':True},'closed 20K profile'),
        ]
        for index,(geometry,message) in enumerate(cases):
            with self.subTest(case=index):
                config=ReplayPinTests.fixture(self);output=self.root/str(index)
                with patch('headkit.replay.audit',return_value=geometry),patch('headkit.replay.prepare') as prepare:
                    with self.assertRaisesRegex(ValueError,message):replay(config,output)
                    prepare.assert_not_called()
                self.assertEqual(read(output/'geometry-audit.json'),geometry)
                self.assertFalse((output/'replay.json').exists())

    def test_valid_replay_retains_full_geometry_audit_evidence(self):
        p,f=MeshTests.tetra(self);source=self.root/'valid.glb';write_mesh(source,p,f)
        geometry=audit(source);self.assertTrue(geometry['passed'])
        config=ReplayPinTests.fixture(self);config['source']=str(source);config['inputs'].append(pin(source))
        result=ReplayPinTests.replay(self,config,self.root/'valid',geometry=geometry)
        self.assertEqual(result['topology'],geometry['topology'])
        self.assertEqual(result['geometryAudit'],pin(self.root/'valid'/'geometry-audit.json'))
        self.assertEqual(read(result['geometryAudit']['path']),geometry)
        self.assertFalse(result['generationPerformed']);self.assertFalse(result['repairPerformed'])


class ResumeTests(Temporary):
    def fixture(self):
        alignment=self.pair();inputs={name:{'path':name+'.png','sha256':pin(self.root/(name+'.png'))['sha256']} for name in ['clay','detail']}
        data={'schemaVersion':1,'id':'synthetic','inputs':inputs,'alignment':alignment,'features':[{'name':'hair','placementReviewed':True}],
              'approval':{'referenceDesignReviewed':True}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',self.bindings_data())
        return Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
    def test_resume_reuses_only_verified_outputs(self):
        runner=self.fixture();first=runner.execute('prepare');self.assertFalse(first['reused']);self.assertTrue(runner.execute('prepare')['reused'])
        image=Path(first['result']['images']['geometry-pair.png']['path']);image.write_bytes(b'changed')
        self.assertIn('staleOrFailed',runner.status()['stages']['prepare']);self.assertFalse(runner.execute('prepare')['reused'])
    def unused_field(self):
        # A large manifest input that prepare never reads.
        field=self.file('field.npz','generated field');data=read(self.root/'manifest.json')
        data['inputs']['field']={'path':'field.npz','sha256':pin(field)['sha256']};write(self.root/'manifest.json',data)
        return field
    def test_receipt_pins_only_the_inputs_a_stage_read(self):
        runner=self.fixture();field=self.unused_field()
        runner=Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run');runner.execute('prepare')
        receipt=read(runner.state['stages']['prepare']['path']);paths={p['path'] for p in receipt['inputs']}
        self.assertIn(str((self.root/'clay.png').resolve()),paths);self.assertIn(str((self.root/'detail.png').resolve()),paths)
        self.assertNotIn(str(field.resolve()),paths)
    def test_reading_undeclared_input_or_library_fails_the_stage(self):
        from headkit import common
        runner=self.fixture();self.unused_field()
        runner=Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
        data=read(self.root/'manifest.json');data['inputs']['raw']=data['inputs'].pop('field');write(self.root/'manifest.json',data)
        runner=Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
        with patch.object(runner,'_execute',side_effect=lambda stage,folder:(runner.input('raw'),{})[1]):
            with self.assertRaisesRegex(ValueError,'undeclared manifest inputs: raw'):runner.execute('prepare')
        with patch.object(runner,'_execute',side_effect=lambda stage,folder:(common.LIBRARIES_USED.add('xatlas'),{})[1]):
            with self.assertRaisesRegex(ValueError,'undeclared libraries: xatlas'):runner.execute('prepare')
        self.assertIsNone(common.LIBRARIES_USED)
    def test_upstream_check_hashes_each_file_once(self):
        from headkit import common
        runner=self.fixture();runner.execute('prepare');runner.review('prepare','approved','synthetic pair reviewed')
        receipt=read(runner.state['stages']['prepare']['path']);output=receipt['outputs'][0]
        calls=[];real=common.sha
        with patch('headkit.common.sha',side_effect=lambda path:(calls.append(str(path)),real(path))[1]):
            runner._verified=set();runner._verify([output,output]);runner._verify([output])
            self.assertEqual(calls.count(output['path']),1)
            runner.result('prepare');runner.result('prepare')
        # Each top-level check starts a fresh memo, so a file changed between checks is still caught.
        self.assertEqual(calls.count(output['path']),3)
        Path(output['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):runner.result('prepare')
    def test_launch_inputs_cover_only_the_launched_stages(self):
        from headkit.__main__ import main
        self.fixture();field=self.unused_field();listed={}
        for name,extra in (('all',[]),('prepare',['--stages','prepare'])):
            output=self.root/f'inputs-{name}.json'
            with patch('sys.argv',['headkit','inputs','--manifest',str(self.root/'manifest.json'),'--bindings',str(self.root/'bindings.json'),
                  '--output',str(output),'--run',str(self.root/'run'),*extra]),patch('builtins.print'):main()
            listed[name]=read(output)
        self.assertIn(str(field.resolve()),listed['all']);self.assertNotIn(str(field.resolve()),listed['prepare'])
        self.assertIn(str((self.root/'clay.png').resolve()),listed['prepare'])
    def test_reviewed_uv_reuse_needs_no_xatlas_binding(self):
        from headkit.__main__ import main
        from headkit.runner import stage_libraries
        self.fixture();data=read(self.root/'manifest.json');self.assertEqual(stage_libraries('unwrap',data),{'xatlas'})
        data['mesh']={'reuseReviewedUvs':True};write(self.root/'manifest.json',data);self.assertEqual(stage_libraries('unwrap',data),set())
        output=self.root/'inputs-unwrap.json'
        with patch('sys.argv',['headkit','inputs','--manifest',str(self.root/'manifest.json'),'--bindings',str(self.root/'bindings.json'),
              '--output',str(output),'--run',str(self.root/'run'),'--stages','unwrap']),patch('builtins.print'):main()
        self.assertTrue(output.exists())
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
        for role,mode,size in [('ownership1k','L',1024),('ownership4k','L',4096),('runtimeColor','RGB',1024),('basecolor4k','RGB',4096),('runtimeShades','L',1024),('detail','RGB',1024)]:
            path=base/(role+'.png');Image.new(mode,(size,size)).save(path);inputs[role]={'path':path.name,'sha256':pin(path)['sha256']}
        inputs['repairedMesh' if derived_uv else 'uvMesh']={'path':uv.name,'sha256':pin(uv)['sha256']}
        data={'schemaVersion':1,'id':'ownership-binding','inputs':inputs,'ownership':{'reviewed':True,'sourceSha256':pin(uv)['sha256']},
              'palette':{'inputs':{},'rows':{}},'tone':{},'fit':{'model':'head'}}
        data['approval']={'textureMaps':{role:{'decision':'approved','notes':'Reviewed atlas on this exact mesh',
            'sourceSha256':pin(uv)['sha256'],'textureSha256':inputs[role]['sha256']}
            for role in ('basecolor4k','runtimeColor','runtimeShades')}}
        write(base/'manifest.json',data);write(base/'bindings.json',self.bindings_data(tools_root=base))
        return Runner(base/'manifest.json',base/'bindings.json',base/'run')
    def test_imported_mesh_audit_blocks_export_and_records_passed_evidence(self):
        runner=self.fixture();source=runner.input('uvMesh')
        rejected={'source':pin(source),'passed':False,'topology':{'closed':False},
                  'crossings':{'complete':True,'pairs':[]}}
        with patch('headkit.mesh.audit',return_value=rejected) as audit, patch('headkit.native.prepare') as prepare:
            with self.assertRaisesRegex(ValueError,'Imported mesh failed topology/collision audit'):
                runner._execute('export',runner.run)
            audit.assert_called_once_with(source);prepare.assert_not_called()
        runner=self.fixture();source=runner.input('uvMesh')
        accepted={'source':pin(source),'passed':True,'topology':{'closed':True},
                  'crossings':{'complete':True,'pairs':[]}}
        uv_report={'imported':True,'audits':{'1024':{'reviewed fixture':True}}}
        with patch('headkit.mesh.audit',return_value=accepted) as audit, patch('headkit.gltf.mesh',return_value={}), patch(
                'headkit.uv.audit_imported_uvs',return_value=uv_report), patch(
                'headkit.native.prepare',return_value={'exported':True}) as prepare:
            result=runner._execute('export',runner.run)
        audit.assert_called_once_with(source);prepare.assert_called_once()
        self.assertEqual(read(result['geometryAudit']['path']),accepted)
        self.assertEqual(read(result['uvAudit']['path']),uv_report)

    def folder(self,name):
        path=self.root/name;path.mkdir();return path
    def test_fit_chosen_before_uvs_binds_to_this_runs_reviewed_unwrap(self):
        uv=self.file('uv.glb','unwrapped mesh');receipt={'path':'unwrap-receipt.json','sha256':'1'*64}
        def runner(fit,inputs):
            return SimpleNamespace(data={'inputs':inputs,'fit':fit,'mesh':{}},state={'stages':{'unwrap':receipt}},bindings={},
                                   source=lambda *args:uv,input=lambda name:uv,
                                   result=lambda stage:{'shades':{'path':'s.png'},'ownership':{'path':'o.png'}})
        fit={'matrix':np.eye(4).tolist(),'reviewed':True,'sourceStage':'unwrap','model':'pmg0_head015'}
        passed={'passed':True}
        with patch('headkit.mesh.audit',return_value=passed),patch('headkit.native.prepare',return_value={'exported':True}) as prepare:
            result=Runner._execute(runner(fit,{'repairedMesh':{}}),'export',self.folder('bound'))
        self.assertEqual(prepare.call_args.args[3]['sourceSha256'],pin(uv)['sha256'])
        self.assertNotIn('sourceSha256',fit);self.assertEqual(result['fitBinding'],{'sourceStage':'unwrap','unwrapReceipt':receipt})
        for bad_fit,inputs in ((fit,{'uvMesh':{}}),(dict(fit,sourceSha256='0'*64),{'repairedMesh':{}})):
            with self.subTest(inputs=sorted(inputs),hashed='sourceSha256' in bad_fit), \
                 patch('headkit.mesh.audit',return_value=passed),patch('headkit.uv.audit_imported_uvs',return_value={}), \
                 patch('headkit.gltf.mesh',return_value={}),patch('headkit.native.prepare') as prepare:
                with self.assertRaisesRegex(ValueError,'own unwrap'):Runner._execute(runner(bad_fit,inputs),'export',self.folder(str(len(inputs))+str(len(bad_fit))))
                prepare.assert_not_called()

    def test_direct_uv_export_rejects_overlap_degenerate_and_unmapped_faces(self):
        p,f=MeshTests.tetra(self)
        good=np.array([[[.02,.02],[.48,.02],[.02,.48]],[[.52,.02],[.98,.02],[.98,.48]],
                       [[.02,.52],[.48,.98],[.02,.98]],[[.52,.52],[.98,.52],[.98,.98]]])
        for defect in ('overlap','degenerate','unmapped'):
            with self.subTest(defect=defect):
                runner=self.fixture();source=Path(runner.input('uvMesh'));uv=good.copy()
                if defect=='overlap':uv[0]=uv[1]
                elif defect=='degenerate':uv[0]=0
                else:uv[0]=np.array([[.01,.01],[.010001,.01],[.01,.010001]])
                source=source.with_name('candidate.glb');write_mesh(source,p,f,uv)
                source_pin=pin(source);runner.data['inputs']['uvMesh']={'path':source.name,'sha256':source_pin['sha256']}
                runner.data['ownership']['sourceSha256']=source_pin['sha256']
                for review in runner.data['approval']['textureMaps'].values():review['sourceSha256']=source_pin['sha256']
                with patch('headkit.mesh.audit',return_value={'passed':True}),patch('headkit.native.prepare',
                        side_effect=AssertionError('Invalid UVs reached native preparation')) as prepare:
                    with self.assertRaisesRegex(ValueError,'failed UV audit'):runner._execute('export',runner.run)
                    prepare.assert_not_called()

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




class ImportedTextureTests(Temporary):
    fixture=ImportedOwnershipTests.fixture
    def with_render(self):
        runner=self.fixture();runner.data['inputs']['displayColor']=copy.deepcopy(runner.data['inputs']['runtimeColor'])
        runner.data['render']={'mapInputs':{'basecolor':'displayColor'},'cameras':{'front':{}}}
        runner.data['approval']['textureMaps']['displayColor']=copy.deepcopy(runner.data['approval']['textureMaps']['runtimeColor'])
        return runner
    def test_each_imported_atlas_needs_approved_exact_texture_and_mesh(self):
        runner=self.with_render();reviews=runner.data['approval']['textureMaps']
        for role in ('basecolor4k','runtimeColor','runtimeShades','displayColor'):
            valid=copy.deepcopy(reviews[role])
            for invalid in ({},dict(valid,decision='rejected'),dict(valid,notes=' '),dict(valid,sourceSha256='0'*64),dict(valid,textureSha256='0'*64)):
                with self.subTest(role=role,review=invalid):
                    reviews[role]=invalid
                    with self.assertRaisesRegex(ValueError,'Imported texture'):runner.input(role)
            reviews[role]=valid;self.assertTrue(Path(runner.input(role)).is_file())
    def test_all_consuming_stages_reject_unreviewed_atlases_before_processing(self):
        runner=self.with_render()
        for stage,role,target in [('tone','basecolor4k','headkit.textures.tone_match'),('palette','runtimeColor','headkit.palette.quantize'),
                                  ('export','runtimeShades','headkit.native.prepare'),('render','displayColor','headkit.review_images.atlas_sets')]:
            valid=runner.data['approval']['textureMaps'].pop(role)
            with self.subTest(stage=stage),patch(target) as work:
                with self.assertRaisesRegex(ValueError,'Imported texture'):runner._execute(stage,runner.run)
                work.assert_not_called()
            runner.data['approval']['textureMaps'][role]=valid
    def test_imported_atlas_rejects_another_active_uv_mesh(self):
        runner=self.fixture();other=self.file('other-uv.glb');row=pin(other)
        # Keep all paths portable beneath this fixture's manifest.
        target=runner.manifest_path.parent/'other.glb';target.write_bytes(other.read_bytes())
        runner.data['inputs']['uvMesh']={'path':target.name,'sha256':row['sha256']}
        for role in ('basecolor4k','runtimeColor','runtimeShades'):
            with self.subTest(role=role):
                with self.assertRaisesRegex(ValueError,'exact UV mesh'):runner.input(role)


class ToneResolutionTests(Temporary):
    fixture=ImportedOwnershipTests.fixture
    def one_k_only(self,runner):
        runner.data['inputs'].pop('ownership4k')
        path=Path(runner.manifest_path).parent/runner.data['inputs']['ownership1k']['path']
        labels=(np.arange(1024*1024,dtype=np.uint32).reshape(1024,1024)%10).astype(np.uint8)
        Image.fromarray(labels,'L').save(path)
        runner.data['inputs']['ownership1k']['sha256']=pin(path)['sha256']
        write(runner.manifest_path,runner.data)
        return labels
    def test_tone_rejects_lower_resolution_imports_before_matching(self):
        for color_size,mask_size in ((1024,1024),(2048,2048),(4096,1024),(1024,4096)):
            runner=self.fixture()
            for role,size in [('basecolor4k',color_size),('ownership4k',mask_size)]:
                path=Path(runner.manifest_path).parent/runner.data['inputs'][role]['path']
                mode='RGB' if role=='basecolor4k' else 'L';Image.new(mode,(size,size)).save(path)
                runner.data['inputs'][role]['sha256']=pin(path)['sha256']
                if role=='basecolor4k':runner.data['approval']['textureMaps'][role]['textureSha256']=pin(path)['sha256']
            with self.subTest(color=color_size,mask=mask_size),patch('headkit.textures.tone_match') as matcher:
                with self.assertRaisesRegex(ValueError,'Tone inputs must be actual 4096'):runner._execute('tone',runner.run)
                matcher.assert_not_called();self.assertFalse((runner.run/'tone-2048.png').exists())
    def test_tone_checks_output_before_derivatives(self):
        runner=self.fixture()
        def match(*args):Image.new('RGB',(1024,1024)).save(args[-1]);return {}
        with patch('headkit.textures.tone_match',side_effect=match):
            with self.assertRaisesRegex(ValueError,'Tone output must be actual 4096'):runner._execute('tone',runner.run)
        self.assertFalse((runner.run/'tone-2048.png').exists())
    def test_4k_tone_produces_only_downsampled_2k_and_1k_maps(self):
        runner=self.fixture()
        def match(*args):Image.new('RGB',(4096,4096),(128,96,64)).save(args[-1]);return {'output':pin(args[-1])}
        with patch('headkit.textures.tone_match',side_effect=match):result=runner._execute('tone',runner.run)
        for size in (2048,1024):
            with Image.open(result['maps'][str(size)]['path']) as image:self.assertEqual(image.size,(size,size))
    def test_reviewed_1k_only_ownership_is_nearest_expanded_for_tone(self):
        runner=self.fixture();labels=self.one_k_only(runner);observed={}
        def match(color,ownership,reference,config,output):
            with Image.open(ownership) as image:
                self.assertEqual(image.mode,'L');self.assertEqual(image.size,(4096,4096))
                expanded=np.asarray(image)
                np.testing.assert_array_equal(expanded[::4,::4],labels)
                blocks=expanded.reshape(1024,4,1024,4)
                np.testing.assert_array_equal(blocks,np.broadcast_to(labels[:,None,:,None],blocks.shape))
                observed['mask']=pin(ownership)
            Image.new('RGB',(4096,4096),(128,96,64)).save(output)
            return {'output':pin(output)}
        with patch('headkit.textures.tone_match',side_effect=match):result=runner._execute('tone',runner.run)
        self.assertEqual(result['ownershipInputRole'],'ownership1k')
        self.assertEqual(result['ownershipUpsampling'],'nearest')
        self.assertEqual(result['ownershipSource']['path'],runner.input('ownership1k'))
        self.assertEqual(result['ownershipForTone'],observed['mask'])
        self.assertTrue(Path(result['ownershipForTone']['path']).is_relative_to(runner.run))
        for size in (2048,1024):
            with Image.open(result['maps'][str(size)]['path']) as image:self.assertEqual(image.size,(size,size))
    def test_tone_rejects_invalid_1k_ownership_before_matching(self):
        for mode,size,unknown in (('RGB',1024,False),('L',512,False),('L',1024,True)):
            runner=self.fixture();self.one_k_only(runner)
            path=Path(runner.manifest_path).parent/runner.data['inputs']['ownership1k']['path']
            Image.new(mode,(size,size),10 if unknown else 0).save(path)
            runner.data['inputs']['ownership1k']['sha256']=pin(path)['sha256'];write(runner.manifest_path,runner.data)
            message='Unknown ownership' if unknown else 'actual 1024x1024 eight-bit L'
            with self.subTest(mode=mode,size=size,unknown=unknown),patch('headkit.textures.tone_match') as matcher:
                with self.assertRaisesRegex(ValueError,message):runner._execute('tone',runner.run)
                matcher.assert_not_called()
                self.assertFalse((runner.run/'tone-4096.png').exists())
    def test_1k_tone_mask_tracks_unwrap_review_and_skips_ownership_stage(self):
        runner=self.fixture(derived_uv=True);self.one_k_only(runner)
        def unwrap(stage,folder):
            target=folder/'uv.glb';target.write_text('frozen UV mesh');return {'mesh':pin(target)}
        with patch.object(runner,'_execute',side_effect=unwrap):runner.execute('unwrap')
        runner.review('unwrap','approved','Reviewed UV mesh for imported 1K mask')
        def match(*args):Image.new('RGB',(4096,4096),(128,96,64)).save(args[-1]);return {'output':pin(args[-1])}
        with patch('headkit.textures.tone_match',side_effect=match) as matcher:runner.execute('tone')
        matcher.assert_called_once()
        receipt=read(runner.state['stages']['tone']['path'])
        self.assertEqual(set(receipt['dependencies']),{'unwrap'})
        self.assertNotIn('ownership',runner.state['stages'])
        runner.review('tone','approved','Reviewed tone from the imported 1K ownership mask')
        runner.review('unwrap','rejected','UV review revoked')
        with patch('headkit.textures.tone_match') as matcher:
            with self.assertRaisesRegex(ValueError,'rejected'):runner.execute('tone')
            matcher.assert_not_called()


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


class ChainTests(Temporary):
    fixture=ResumeTests.fixture;completed=ReviewGateTests.completed
    def chain(self,runner,stages,fail=()):
        from headkit.__main__ import chain
        order=[]
        def work(stage,folder):
            order.append(stage)
            if stage in fail:raise ValueError('Synthetic failure: '+stage)
            return self.completed(stage,folder)
        with patch.object(runner,'_execute',side_effect=work):result=chain(runner,stages)
        return result,order,{row['stage']:row for row in result['stages']}
    def test_runs_in_order_and_stops_at_review_gate_without_approving(self):
        runner=self.fixture();result,order,rows=self.chain(runner,['repair','unwrap','bake'])
        self.assertEqual(order,['repair']);self.assertEqual(result['stopped'],'blocked-on-review')
        self.assertEqual(rows['repair']['status'],'ran');self.assertEqual(rows['repair']['review'],'pending')
        self.assertIsInstance(rows['repair']['elapsedSeconds'],float);self.assertNotIn('bake',rows)
        gate=rows['unwrap'];self.assertEqual((gate['status'],gate['dependency']),('blocked-on-review','repair'))
        self.assertEqual(Path(gate['evidence']),runner.run/'repair'/'attempt-01');self.assertIn('review --stage repair',gate['next'])
        self.assertNotIn('reviews',runner.state);self.assertFalse(result['autoApproved'])
        runner.review('repair','rejected','Visible accessory defect')
        result,order,rows=self.chain(runner,['repair','unwrap'])
        self.assertEqual(order,[]);self.assertEqual(rows['unwrap']['status'],'blocked-on-review');self.assertIn('rejected',rows['unwrap']['reason'])
    def test_reuses_completed_reviewed_stages(self):
        runner=self.fixture();self.chain(runner,['repair']);runner.review('repair','approved','Inspected repair')
        result,order,rows=self.chain(runner,['repair','unwrap'])
        self.assertEqual(order,['unwrap']);self.assertEqual([rows[s]['status'] for s in ('repair','unwrap')],['reused','ran'])
        self.assertEqual(rows['repair']['review'],'approved');self.assertIsNone(result['stopped'])
        runner.review('unwrap','approved','Inspected UVs')
        result,order,rows=self.chain(runner,['repair','unwrap','bake'])
        self.assertEqual(order,['bake']);self.assertEqual([row['status'] for row in result['stages']],['reused','reused','ran'])
    def test_stops_on_failure_and_resumes_there(self):
        runner=self.fixture();self.chain(runner,['repair']);runner.review('repair','approved','Inspected repair')
        result,order,rows=self.chain(runner,['repair','unwrap','bake'],fail=('unwrap',))
        self.assertEqual(order,['unwrap']);self.assertEqual(result['stopped'],'failed');self.assertNotIn('bake',rows)
        self.assertEqual(Path(rows['unwrap']['attempt']),runner.run/'unwrap'/'attempt-01');self.assertIn('Synthetic failure',rows['unwrap']['error'])
        result,order,rows=self.chain(Runner(runner.manifest_path,runner.bindings_path,runner.run),['repair','unwrap','bake'])
        self.assertEqual(order,['unwrap']);self.assertEqual(rows['repair']['status'],'reused')
        self.assertEqual((rows['unwrap']['status'],Path(rows['unwrap']['attempt'])),('ran',runner.run/'unwrap'/'attempt-02'))
        self.assertEqual((rows['bake']['status'],rows['bake']['dependency']),('blocked-on-review','unwrap'))
    def test_rejects_unknown_duplicate_or_reordered_stages(self):
        runner=self.fixture()
        for stages in ([],['unwrap','repair'],['repair','repair'],['gpu']):
            with self.subTest(stages=stages),self.assertRaisesRegex(ValueError,'pipeline order'):self.chain(runner,stages)
        self.assertEqual(runner.state['stages'],{})
    def test_cli_requires_launcher_and_exits_nonzero_only_on_failure(self):
        from headkit.__main__ import main
        runner=self.fixture();argv=['headkit','chain','--manifest',str(runner.manifest_path),'--bindings',str(runner.bindings_path),
                                    '--run',str(runner.run),'--stages','repair, unwrap']
        with patch('sys.argv',argv),patch.dict('os.environ',{'SRN_SHARED_TOOLCHAIN':'','SRN_SHARED_TOOL_MIGRATION':''}):
            with self.assertRaisesRegex(ValueError,'launch_shared_tool'):main()
        with patch('sys.argv',argv),patch('headkit.__main__.launched',return_value=None),patch('builtins.print'),\
             patch('headkit.runner.Runner._execute',autospec=True,side_effect=lambda r,s,f:self.completed(s,f)) as work:
            main();self.assertEqual([c.args[1] for c in work.call_args_list],['repair'])
        with patch('sys.argv',argv[:-1]+['prepare']),patch('headkit.__main__.launched',return_value=None),patch('builtins.print'),\
             patch('headkit.runner.Runner._execute',side_effect=ValueError('Synthetic failure')):
            with self.assertRaises(SystemExit) as stop:main()
        self.assertEqual(stop.exception.code,1)


class GeneratedFieldLineageTests(Temporary):
    def fixture(self,geometry_roles=('uvMesh',)):
        inputs={}
        for role in geometry_roles:
            path=self.file(role+'.glb',role)
            inputs[role]={'path':path.name,'sha256':pin(path)['sha256']}
        field=self.file('field.npz','generated field')
        inputs['field']={'path':field.name,'sha256':pin(field)['sha256']}
        geometry_role=next(role for role in ('uvMesh','repairedMesh','comfyExport') if role in inputs)
        data={'schemaVersion':1,'id':'field-lineage','inputs':inputs,'approval':{'appearanceField':{
            'decision':'approved','geometryInput':geometry_role,'geometrySha256':inputs[geometry_role]['sha256'],
            'fieldSha256':inputs['field']['sha256'],'notes':'Verified this field against the active geometry.'}}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',self.bindings_data())
        return Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')

    def test_field_approval_binds_to_the_active_mesh_source(self):
        for roles in (('uvMesh',),('comfyExport',),('comfyExport','repairedMesh'),('comfyExport','uvMesh')):
            with self.subTest(roles=roles):
                runner=self.fixture(roles)
                expected=runner.data['inputs']['field']['path']
                self.assertEqual(Path(runner.input('field')),runner.manifest_path.parent/expected)

    def test_field_rejects_missing_or_mismatched_approval(self):
        runner=self.fixture(('uvMesh','comfyExport'));valid=copy.deepcopy(runner.data['approval']['appearanceField'])
        invalid=({},dict(valid,decision='pending'),dict(valid,notes=' '),dict(valid,geometryInput='comfyExport'),
                 dict(valid,geometrySha256='0'*64),dict(valid,fieldSha256='0'*64))
        for review in invalid:
            with self.subTest(review=review):
                runner.data['approval']['appearanceField']=review
                with self.assertRaisesRegex(ValueError,'Generated field approval'):
                    runner.input('field')
        runner.data['approval']['appearanceField']=valid
        field=runner.manifest_path.parent/runner.data['inputs']['field']['path'];field.write_text('changed field')
        with self.assertRaisesRegex(ValueError,'Stale file pin'):
            runner.input('field')

    def test_bake_rejects_unapproved_field_before_sampling(self):
        runner=self.fixture();runner.data['approval']['appearanceField']['decision']='pending'
        with patch('headkit.textures.bake') as bake:
            with self.assertRaisesRegex(ValueError,'Generated field approval'):
                runner._execute('bake',runner.run)
            bake.assert_not_called()


class RenderPlanTests(Temporary):
    def camera(self):return {'name':'front','eye':[0,0,2],'target':[0,0,0],'orthoScale':2}
    def test_empty_camera_and_mode_plans_are_rejected(self):
        from headkit.review_images import render_plan
        for config in ({'cameras':[]},{'cameras':[self.camera()],'modes':[]}):
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError,'nonempty'):render_plan(config)
    def test_complete_plan_requires_all_unique_frames(self):
        from headkit.review_images import render_plan,validate_frames
        config={'cameras':[self.camera()]};expected=render_plan(config);self.assertEqual(len(expected),6)
        records=[{'size':s,'mode':m,'view':v} for s,m,v in expected];validate_frames(config,records)
        for bad in ([],records[:-1],records[:-1]+[records[0]]):
            with self.subTest(count=len(bad)):
                with self.assertRaisesRegex(ValueError,'frames'):validate_frames(config,bad)
    def test_production_requires_all_material_modes_and_diagnostic_subset_is_explicit(self):
        from headkit.review_images import render_plan
        with self.assertRaisesRegex(ValueError,'Production render plans'):
            render_plan({'cameras':[self.camera()],'modes':['clay']})
        self.assertEqual(len(render_plan({'cameras':[self.camera()],'modes':['clay'],'diagnostic':True})),2)

    def test_single_size_render_is_always_diagnostic(self):
        from headkit.review_images import render_plan
        with self.assertRaisesRegex(ValueError,'Single-size render plans'):
            render_plan({'cameras':[self.camera()],'size':768})
        self.assertEqual(len(render_plan({'cameras':[self.camera()],'size':768,'diagnostic':True})),3)

    def test_textured_render_requires_present_non_degenerate_uvs(self):
        from headkit.gltf import require_textured_uvs
        vertices=np.array([[0,0,0],[1,0,0],[0,1,0]],np.float32);faces=np.array([[0,1,2]])
        valid=np.array([[[0,0],[1,0],[0,1]]],np.float32)
        path=self.root/'with-uv.glb';write_mesh(path,vertices,faces,uv=valid)
        self.assertTrue(require_textured_uvs(path))
        missing=self.root/'missing-uv.glb';write_mesh(missing,vertices,faces)
        with self.assertRaisesRegex(ValueError,'TEXCOORD_0'):require_textured_uvs(missing)
        flat=self.root/'flat-uv.glb';write_mesh(flat,vertices,faces,uv=np.zeros((1,3,2),np.float32))
        with self.assertRaisesRegex(ValueError,'nondegenerate UVs'):require_textured_uvs(flat)
    def render_runner(self):
        path=self.file('uv.glb')
        data={'schemaVersion':1,'id':'render-inputs','inputs':{'uvMesh':{'path':path.name,'sha256':pin(path)['sha256']}},
              'render':{'cameras':[self.camera()],'mapInputs':{},'modes':['clay'],'size':16,'diagnostic':True}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',self.bindings_data(toolchain=str(self.file('toolchain.json')),migrationReceipt=str(self.file('migration.json'))))
        return Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')

    def launcher(self):
        from headkit.common import ROOT
        with patch.object(sys,'path',[str(ROOT/'tools/phenotypes'),*sys.path]):
            spec=importlib.util.spec_from_file_location('headkit_render_launcher',ROOT/'tools/phenotypes/launch_shared_tool.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_render_launcher_snapshots_imported_helpers_and_config(self):
        from headkit.common import ROOT,code_pins
        runner=self.render_runner();launcher=self.launcher();captured=[]
        class Launched(Exception):pass
        def launch(command,**kwargs):
            self.assertIn('--input-manifest',command)
            declared=Path(command[command.index('--input-manifest')+1])
            paths,frozen=launcher.manifest_inputs([declared])
            config=read(runner.run/'render-config.json')
            self.assertTrue({row['path'] for row in code_pins()}<={row['path'] for row in config['inputs']})
            self.assertIn((runner.run/'render-config.json').resolve(),paths)
            output=runner.run/'launcher-snapshots';output.mkdir()
            snapshots=launcher.helper_snapshots(paths,frozen,output)
            helpers=[ROOT/'tools/headkit'/name for name in ('blender_render.py','gltf.py','review_images.py','common.py')]
            helpers.append(ROOT/'tools/phenotypes/bootstrap_shared_blender_addons.py')
            for path in helpers:
                self.assertEqual(pin(snapshots[str(path)]['snapshot'])['sha256'],pin(path)['sha256'])
            captured.append(command)
            raise Launched
        with patch('subprocess.run',side_effect=launch):
            with self.assertRaises(Launched):runner._execute('render',runner.run)
        self.assertEqual(len(captured),1)

    def test_render_launcher_rejects_changed_imported_helper(self):
        from headkit.common import code_pins,verify
        helper=self.file('imported-helper.py','value=1');frozen=code_pins()+[pin(helper)]
        runner=self.render_runner();launcher=self.launcher()
        def launch(command,**kwargs):
            helper.write_text('value=2')
            # Both the shared launcher and Blender use the prepared hashes.
            with self.assertRaisesRegex(ValueError,'Stale file pin'):
                verify(read(runner.run/'render-config.json')['inputs'])
            launcher.manifest_inputs([Path(command[command.index('--input-manifest')+1])])
        with patch('headkit.runner.code_pins',return_value=frozen),patch('subprocess.run',side_effect=launch):
            with self.assertRaisesRegex(ValueError,'Manifest input changed'):
                runner._execute('render',runner.run)

    def test_runner_rejects_empty_plan_before_atlas_or_blender_work(self):
        path=self.file('uv.glb');data={'schemaVersion':1,'id':'empty-render','inputs':{'uvMesh':{'path':path.name,'sha256':pin(path)['sha256']}},
            'render':{'cameras':[],'mapInputs':{}}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',self.bindings_data())
        runner=Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
        with patch('headkit.review_images.atlas_sets') as atlases,patch('subprocess.run') as blender:
            with self.assertRaisesRegex(ValueError,'nonempty'):runner._execute('render',runner.run)
            atlases.assert_not_called();blender.assert_not_called()
        self.assertFalse((runner.run/'renders').exists())


class NativeDependencyTests(Temporary):
    def test_native_imports_and_compiler_inputs_are_pinned(self):
        from headkit.common import ROOT,code_pins
        # Isolate actual imports from modules already loaded by other tests.
        script="""import json,sys
from pathlib import Path
from headkit.common import ROOT
from headkit.native import helpers
helpers()
sys.path.insert(0,str(ROOT/'tools/phenotypes'))
import native_compile
print(json.dumps(sorted({str(Path(module.__file__).resolve()) for module in list(sys.modules.values())
    if getattr(module,'__file__',None) and Path(module.__file__).resolve().is_relative_to(ROOT)})))
"""
        result=subprocess.run([sys.executable,'-B','-c',script],capture_output=True,text=True,check=True)
        consumed=set(json.loads(result.stdout))
        consumed.add(str(ROOT/'tools/phenotypes/height_targets.json'))
        consumed.add(str(ROOT/'tools/shared-tools.lock.json'))
        self.assertFalse(consumed-{row['path'] for row in code_pins()})


class ReviewImageTests(Temporary):
    def test_default_and_example_deliver_both_native_resolutions(self):
        from headkit.review_images import resolutions
        self.assertEqual(resolutions({}),[2048,1024])
        example=read(Path(__file__).parent/'examples'/'processing.json')
        self.assertEqual(resolutions(example['render']),[2048,1024])
        self.assertTrue(set(example['render']['mapInputs'].values())<=set(example['inputs']))
        self.assertTrue(set(example['render']['mapInputs'].values())<=set(example['approval']['textureMaps']))
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
    def test_atlas_traversal_is_rejected_before_any_output_or_overwrite(self):
        from headkit.review_images import atlas_sets
        source=self.root/'source.png';Image.new('RGB',(8,8),(20,50,90)).save(source)
        victim=self.root/'outside.png';Image.new('RGB',(8,8),(90,50,20)).save(victim)
        originals=[pin(source),pin(victim)];output=self.root/'attempt'
        with self.assertRaisesRegex(ValueError,'supported map names'):
            atlas_sets({'maps':{'basecolor':str(source),'../../../outside':str(source)}},output,[8])
        self.assertFalse(output.exists())
        self.assertEqual([pin(source),pin(victim)],originals)

    def test_all_unrecognized_map_names_fail_before_image_io(self):
        from headkit.review_images import atlas_sets,render_plan
        bad_names=['../outside',r'..\outside','/absolute',r'C:\absolute',str(self.root/'absolute'),
                   'extra','basecolor.png','',1]
        for name in bad_names:
            with self.subTest(name=name):
                maps={'basecolor':'unused',name:'unused'}
                with patch('PIL.Image.open',side_effect=AssertionError('Invalid names reached image IO')) as image_open:
                    with self.assertRaisesRegex(ValueError,'supported map names'):atlas_sets({'maps':maps},self.root/'invalid',[8])
                    image_open.assert_not_called()
                for field in ('maps','mapInputs'):
                    with self.assertRaisesRegex(ValueError,'supported map names'):
                        render_plan({'cameras':[RenderPlanTests.camera(self)],field:maps})
        for bad in (None,[],['basecolor']):
            with self.subTest(mapping=bad):
                with self.assertRaisesRegex(ValueError,'supported map names'):atlas_sets({'maps':bad},self.root/'invalid',[8])
        self.assertFalse((self.root/'invalid').exists())

    def test_supported_atlas_names_preserve_color_modes_and_hashes(self):
        from headkit.review_images import atlas_sets
        source=self.root/'source.png';Image.new('RGB',(8,8),(20,50,90)).save(source)
        names={'basecolor','roughness','metallic','opacity'}
        maps={name:str(source) for name in names}
        sets,records=atlas_sets({'maps':maps},self.root/'valid',[8])
        self.assertEqual(set(sets[8]),names);self.assertEqual(len(records),4)
        for row in records:
            self.assertEqual(row['source'],pin(source));self.assertEqual(row['image'],pin(sets[8][row['map']]))
            with Image.open(row['image']['path']) as image:
                self.assertEqual(image.mode,'RGB' if row['map']=='basecolor' else 'L')
                self.assertEqual(image.size,(8,8))

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


class TextureStageTests(Temporary):
    CREST={'name':'crest','pivotHeight':.6,'angleRange':[-20,150],'angleBinDegrees':3,'slabWidth':.02,
           'midlineHalfWidth':.17,'envelopeClearance':.02,'stripeHalfWidth':.025}
    @staticmethod
    def quads(grid):
        a,b,c,d=grid[:-1,:-1],grid[1:,:-1],grid[1:,1:],grid[:-1,1:]
        return np.r_[np.stack([a,b,c],2).reshape(-1,3,3),np.stack([a,c,d],2).reshape(-1,3,3)]
    @staticmethod
    def soup(triangles, cell=4):
        """Every face owns its vertices (as after a UV split) and one square UV cell; returns value, atlas size."""
        n=len(triangles);side=int(np.ceil(np.sqrt(n)));k=np.arange(n);u0,v0=(k%side)/side,(k//side)/side;s=1/side
        uv=np.stack([np.c_[u0+.1*s,v0+.1*s],np.c_[u0+.9*s,v0+.1*s],np.c_[u0+.1*s,v0+.9*s]],1)
        return {'positions':triangles.reshape(-1,3),'faces':np.arange(3*n).reshape(n,3),'uv':uv},side*cell
    def head(self):
        """Lateral cylinder skull (x across, y up, z front), a raised midline fin and a raised side ridge at x=0.6."""
        def ring(x,radii,degrees):
            r,t=np.meshgrid(radii,np.radians(degrees),indexing='ij')
            return np.stack([np.broadcast_to(x,r.shape),r*np.sin(t),-r*np.cos(t)],-1)
        # The skull is dense enough that every 3-degree pivot-angle bin holds skull faces beneath the fin.
        x,t=np.meshgrid(np.linspace(-.8,.8,41),np.radians(np.arange(0,361,1)),indexing='ij')
        skull=self.quads(np.stack([x,np.sin(t),-np.cos(t)],-1))
        fin=self.quads(ring(0.,[1,1.1,1.2,1.3,1.4],np.arange(20,121,3)));ridge=self.quads(ring(.6,[1,1.1,1.2,1.3,1.4],np.arange(20,121,3)))
        value,size=self.soup(np.r_[skull,fin,ridge]);kind=np.repeat([0,1,2],[len(skull),len(fin),len(ridge)])
        colours=np.array([[150,110,90],[180,180,180],[180,180,180]],np.uint8)[kind];side=size//4
        cells=np.arange(side*side).reshape(side,side).repeat(4,0).repeat(4,1).clip(0,len(kind)-1)
        return value,colours[cells].copy(),kind
    def test_crest_selects_raised_midline_faces_not_skull_or_side_ridge(self):
        from headkit.paint import crest_faces
        value,rgb,kind=self.head();band,stripe,grown=crest_faces(value,rgb,self.CREST)
        radius=np.hypot(*value['positions'][value['faces']].mean(1)[:,1:].T)
        self.assertFalse(band[kind!=1].any());self.assertEqual(grown,0)
        self.assertTrue(band[(kind==1)&(radius>1.1)].all());self.assertFalse(band[(kind==1)].all())
        np.testing.assert_array_equal(stripe,band)
    def test_crest_growth_crosses_uv_seams_through_welded_positions(self):
        from headkit.paint import crest_faces,adjacency
        value,rgb,kind=self.head()
        grow={'rounds':12,'halfWidth':.2,'skullTolerance':.01,'grayMinimumLuminance':95,'grayMaximumSpread':30}
        band,_,grown=crest_faces(value,rgb,dict(self.CREST,grow=grow))
        self.assertGreater(grown,0);np.testing.assert_array_equal(band,kind==1)
        # Split vertices at equal positions are neighbours; a nearby but distinct edge is not.
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[1,0,0],[0,1,0],[1,1,0],[1,0,1e-3],[0,1,0],[1,1,1]],float)
        neighbours=adjacency(p,np.arange(9).reshape(3,3)).toarray()>0
        np.testing.assert_array_equal(neighbours,[[False,True,False],[True,False,False],[False,False,False]])
    def test_crest_paints_only_untextured_texels(self):
        from headkit.paint import crest
        value,rgb,kind=self.head();rgb[...]=(180,180,180);rgb[:,:8]=(10,10,10);report={}
        op=dict(self.CREST,color=[18,16,17],stripeColor=[120,14,22],preserve={'darkBelow':45,'redAbove':40})
        masks=crest(value,rgb,op,report);self.assertEqual(set(masks),{'crest','crest-stripe'});self.assertTrue((rgb[:,:8]==10).all())
        painted=masks['crest-stripe'].copy();painted[:,:8]=False;outside=~masks['crest'];outside[:,:8]=False
        self.assertTrue(painted.any() and (rgb[painted]==(120,14,22)).all() and (rgb[outside]==180).all())
        self.assertEqual(report['paintedTexels']['crest-stripe'],int(painted.sum()))
    def two_faces(self, size=64):
        p=np.array([[0,0,0],[1,0,0],[0,1,1],[1,0,0],[1,1,1],[0,1,1]],np.float32)
        uv=np.array([[[.02,.02],[.9,.02],[.02,.9]],[[.98,.1],[.98,.98],[.1,.98]]])
        source=self.root/'faces.glb';write_mesh(source,p,np.arange(6).reshape(2,3),uv)
        rgb=np.full((size,size,3),120,np.uint8);rgb[:,:size//2]=(200,20,20);Image.fromarray(rgb).save(self.root/'color.png')
        return source,rgb
    def test_rule_ownership_first_match_wins_and_padding_takes_nearest_label(self):
        from headkit.paint import rule_ownership
        from headkit.uv import raster_audit
        source,rgb=self.two_faces();owners=raster_audit(mesh(source)['uv'],64)[1];mapped=owners>=0;red=rgb[...,0]==200
        rules=[{'name':'red','channel':9,'when':{'of':'red','gt':50}},{'name':'rest','channel':1,'when':{'of':'lum','ge':0}}]
        labels,report=rule_ownership(source,self.root/'color.png',{'rules':rules})
        self.assertTrue((labels[mapped&red]==9).all() and (labels[mapped&~red]==1).all() and set(np.unique(labels))=={1,9})
        self.assertEqual([row['texels'] for row in report['rules']],[int((mapped&red).sum()),int((mapped&~red).sum())])
        labels,_=rule_ownership(source,self.root/'color.png',{'rules':rules[::-1]});self.assertTrue((labels==1).all())
        Image.fromarray(np.where(np.arange(64)[None,:]<8,255,0).astype(np.uint8).repeat(64,0)).save(self.root/'mask.png')
        config={'default':2,'regions':{'right':{'of':'x','center':1,'lt':.5}},
                'rules':[{'name':'masked','channel':3,'when':{'mask':'m'}},{'name':'right','channel':8,'when':{'region':'right'}}]}
        labels,_=rule_ownership(source,self.root/'color.png',config,masks={'m':self.root/'mask.png'})
        right=np.arange(64)[None,:]>=8
        self.assertTrue((labels[mapped&(owners==1)&right]==8).all() and (labels[mapped&(owners==0)&right]==2).all())
        self.assertTrue((labels[mapped&(np.arange(64)[None,:]<8)]==3).all())
        for bad in ({'of':'metallic','gt':1},{'region':'missing'},{'of':'lum'},{'channel':1}):
            with self.subTest(condition=bad),self.assertRaises(ValueError):
                rule_ownership(source,self.root/'color.png',{'rules':[{'name':'x','channel':1,'when':bad}]})
    def test_worked_texture_example_conditions_evaluate(self):
        from headkit.paint import rule_ownership,adjust
        example=read(Path(__file__).parent/'examples'/'texture-rules.json');source,rgb=self.two_faces()
        Image.new('L',(64,64),200).save(self.root/'metal.png');Image.new('L',(64,64),0).save(self.root/'mask.png')
        labels,report=rule_ownership(source,self.root/'color.png',example['ownership'],metallic=self.root/'metal.png',
                                     masks={'neck-cap':self.root/'mask.png','crest':self.root/'mask.png'})
        self.assertEqual(set(np.unique(labels)),{0,2});Image.fromarray(labels).save(self.root/'labels.png')
        Image.new('RGB',(256,89),(90,10,10)).save(self.root/'tattoo.png')
        adjust(self.root/'color.png',self.root/'labels.png',example['tone'],{'9':self.root/'tattoo.png'},self.root/'tone.png')
        self.assertEqual({op['op'] for op in example['paint']['operations']},{'fill','crest'})
    def test_fill_paints_faces_and_their_padding_with_a_median_colour(self):
        from headkit.paint import fill,texel_source
        from headkit.uv import raster_audit
        source,rgb=self.two_faces();value=mesh(source);owners=raster_audit(value['uv'],64)[1];report={}
        masks=fill(value,rgb,{'name':'cap','faces':{'of':'index','ge':1},'color':{'median':{'of':'y','ge':0}}},report,texel_source(value,rgb),{})
        self.assertEqual(report['color'],[200,20,20]);self.assertTrue(masks['cap'][owners==1].all() and not masks['cap'][owners==0].any())
        self.assertGreater(masks['cap'].sum(),(owners==1).sum());self.assertTrue((rgb[masks['cap']]==(200,20,20)).all())
    def test_adjust_passes_through_and_maps_brightness_onto_a_palette_ramp(self):
        from headkit.paint import adjust
        rgb=np.zeros((8,8,3),np.uint8);rgb[:,:,0]=np.arange(8)[None,:]*30;Image.fromarray(rgb).save(self.root/'c.png')
        labels=np.zeros((8,8),np.uint8);labels[:4]=9;Image.fromarray(labels).save(self.root/'o.png')
        adjust(self.root/'c.png',self.root/'o.png',{'mode':'adjust'},{},self.root/'same.png')
        np.testing.assert_array_equal(np.asarray(Image.open(self.root/'same.png')),rgb)
        palette=np.zeros((2,256,4),np.uint8);palette[1,:,0]=np.arange(256);palette[...,3]=255;Image.fromarray(palette).save(self.root/'p.png')
        config={'operations':[{'op':'paletteRamp','when':{'channel':9},'palette':'9','row':1,'luminanceScale':1},
                              {'op':'set','when':{'all':[{'channel':0},{'of':'r','gt':100}]},'color':[1,2,3]}]}
        result=adjust(self.root/'c.png',self.root/'o.png',config,{'9':self.root/'p.png'},self.root/'out.png')
        out=np.asarray(Image.open(self.root/'out.png'))
        np.testing.assert_array_equal(out[:4,:,0],rgb[:4,:,0]);self.assertTrue((out[4:,4:]==(1,2,3)).all())
        np.testing.assert_array_equal(out[4:,:4],rgb[4:,:4]);self.assertEqual([r['texels'] for r in result['operations']],[32,16])
    def test_auto_rows_equal_brute_force_ranking(self):
        from headkit.palette import rank_rows
        rng=np.random.default_rng(3);rgb=rng.integers(40,200,(64,64,3),dtype=np.uint8);labels=rng.choice([0,1],(64,64)).astype(np.uint8)
        rgb[:20]=rgb[:20]//8*8  # repeated colours exercise the unique-colour weights
        Image.fromarray(rgb).save(self.root/'c.png');Image.fromarray(labels).save(self.root/'o.png')
        palette=rng.integers(0,256,(12,256,4),dtype=np.uint8);palette[...,3]=np.where(rng.random((12,256))<.3,0,255)
        palette[5,:,3]=0;palette[7]=palette[2];palette[2,255,:3]=rgb[0,0];Image.fromarray(palette).save(self.root/'p.png')
        ranking=rank_rows(self.root/'c.png',self.root/'o.png',{'0':self.root/'p.png','1':self.root/'p.png'},keep=5,chunk=8)
        for key in ('0','1'):
            colours=rgb[labels==int(key)].astype(np.int64);scores=[]
            for row in range(12):
                allowed=(palette[row,:,3]>0)&(np.arange(256)<255)
                if allowed.any():
                    squared=((colours[:,None,:]-palette[row,allowed,:3].astype(np.int64)[None])**2).sum(-1).min(1)
                    scores.append((squared.sum()/len(colours),row))
            scores.sort()
            self.assertEqual([(r['meanSquaredDistance'],r['row']) for r in ranking[key]['top']],scores[:5])
            self.assertEqual(ranking[key]['row'],scores[0][1]);self.assertEqual(ranking[key]['rowsScored'],11)
    def test_palette_auto_rows_resolve_before_quantization(self):
        runner=ImportedOwnershipTests.fixture(self);base=runner.manifest_path.parent
        palette=np.zeros((3,256,4),np.uint8);palette[0,:,:3]=255;palette[0,:,3]=255;palette[2,:,3]=255
        Image.fromarray(palette).save(base/'skin.png');runner.data['inputs']['paletteSkin']={'path':'skin.png','sha256':pin(base/'skin.png')['sha256']}
        runner.data['palette']={'inputs':{'0':'paletteSkin'},'rows':'auto'}
        with patch('headkit.palette.quantize',return_value={'fixture':True}) as quantizer:result=runner._execute('palette',runner.run)
        self.assertEqual(quantizer.call_args.args[3],{'0':2});self.assertEqual(result['rowRanking']['0']['row'],2)
        self.assertTrue((runner.run/'row-ranking.json').is_file())
    def texture_runner(self):
        alignment=self.pair();inputs={name:{'path':name+'.png','sha256':pin(self.root/(name+'.png'))['sha256']} for name in ['clay','detail']}
        data={'schemaVersion':1,'id':'painted','inputs':inputs,'alignment':alignment,'features':[{'name':'hair','placementReviewed':True}],
              'approval':{'referenceDesignReviewed':True},'paint':{'operations':[{'op':'fill','name':'cap','faces':{'of':'index','ge':0},'color':[1,2,3]}]},
              'ownership':{'mode':'rules','reviewed':True,'rules':[]},'tone':{'mode':'adjust'}}
        write(self.root/'manifest.json',data);write(self.root/'bindings.json',self.bindings_data())
        return Runner(self.root/'manifest.json',self.root/'bindings.json',self.root/'run')
    def test_review_gate_blocks_consumers_of_paint(self):
        runner=self.texture_runner();completed=ReviewGateTests.completed
        with patch.object(runner,'_execute',side_effect=lambda stage,folder:completed(self,stage,folder)) as work:
            for stage in ('repair','unwrap','bake'):runner.execute(stage);runner.review(stage,'approved','Reviewed this stage')
            runner.execute('paint');calls=work.call_count
            for decision in (None,'rejected'):
                if decision:runner.review('paint',decision,'Crest recolor bled onto skin')
                for stage in ('ownership','tone'):
                    with self.subTest(decision=decision,stage=stage),self.assertRaisesRegex(ValueError,'review|rejected'):runner.execute(stage)
            self.assertEqual(work.call_count,calls)
            runner.review('paint','approved','Inspected recolored atlas and masks');runner.execute('ownership')
            runner.review('ownership','approved','Inspected rule ownership');runner.execute('tone')
        dependencies=lambda stage:set(read(runner.state['stages'][stage]['path'])['dependencies'])
        self.assertEqual(dependencies('paint'),{'bake','unwrap'});self.assertEqual(dependencies('ownership'),{'unwrap','paint','bake'})
        self.assertEqual(dependencies('tone'),{'paint','ownership'})
        runner.review('bake','rejected','Bake revoked')
        with patch.object(runner,'_execute') as work:
            with self.assertRaisesRegex(ValueError,'rejected'):runner.execute('tone')
            work.assert_not_called()


if __name__=='__main__':unittest.main()
