"""Portable startup and native source routing regressions."""
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
from unittest.mock import patch
from . import api, cli
from .engine.silhouette_model import native_model, frames


def duplicate_fixture(name='impact', second_flags=1, first_has_child=False):
    size=0x600; data=bytearray(12+size)
    struct.pack_into('<III',data,0,0,size,0)
    struct.pack_into('<II',data,12+0x48,0xe8,3)
    for offset,label,flags in ((0xe8,'test',1),(0x158,name,1),(0x1c8,name,second_flags)):
        start=12+offset; data[start+32:start+32+len(label)]=label.encode()
        struct.pack_into('<I',data,start+0x6c,flags)
    struct.pack_into('<III',data,12+0xe8+0x48,0x500,2,2)
    struct.pack_into('<II',data,12+0x500,0x158,0x1c8)
    if first_has_child:
        struct.pack_into('<III',data,12+0x158+0x48,0x508,1,1)
        struct.pack_into('<I',data,12+0x508,0x1c8)
    return bytes(data)


class PortableCliTests(unittest.TestCase):
    def test_doctor_uses_only_shipped_measurement_utilities(self):
        out=io.StringIO()
        with patch.object(cli,'declared'),contextlib.redirect_stdout(out): cli.main(['doctor'])
        self.assertTrue(json.loads(out.getvalue())['checksPassed'])

    def test_native_duplicate_leaf_attachments_are_both_preserved(self):
        skeleton,meshes=native_model(duplicate_fixture(),'test')
        self.assertEqual(set(skeleton),{'test','impact','impact__duplicate_2'})
        self.assertEqual(set(frames(skeleton)),set(skeleton))
        self.assertEqual(meshes,[])

    def test_duplicate_mesh_joint_or_parent_still_rejected(self):
        for payload in (duplicate_fixture(second_flags=33),duplicate_fixture(name='pelvis_g'),duplicate_fixture(first_has_child=True)):
            with self.subTest(),self.assertRaisesRegex(ValueError,'Duplicate native'):native_model(payload,'test')

    def test_candidate_rejects_stale_motion_pin_before_fitting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.mdl';source.write_bytes(b'original');bundle=root/'inputs.json'
            api.save_recipe(bundle,{'schemaVersion':1,'kind':'PhenoMorpher-candidate-inputs',
                'motion':{'clips':{},'inputPins':{str(source):'0'*64}}})
            with patch.object(cli,'declared'),patch.object(cli,'snapshot',return_value={str(source.resolve()):api.digest(source)}),patch.object(api,'fit_candidate') as fit:
                with self.assertRaisesRegex(ValueError,'source pin changed'):cli.main(['candidate','--bundle',str(bundle),'--output',str(root/'out')])
                fit.assert_not_called()

    def test_complete_identity_cli_writes_reproducible_scene_and_frozen_stages(self):
        from .engine.target_contract import PART_JOINTS
        from .engine.morph_preview_pose_v13 import static_bind_frames
        skeleton={'control':{'parent':'null','position':np.zeros(3),'rotation':np.eye(3)}}
        for index,joint in enumerate(PART_JOINTS.values()):
            skeleton[joint]={'parent':'control','position':np.array([0.,0.,index*.03]),'rotation':np.eye(3)}
        frames=static_bind_frames(skeleton,{});meshes=[]
        for part,joint in PART_JOINTS.items():
            meshes.append({'part':part,'name':part,'position':frames[joint][:3,3]+np.array([[0.,0.,0.],[.03,0.,0.],[0.,.01,.04]]),'faces':np.array([[0,1,2]]),'render':True})
        for mesh in meshes:mesh['sourceAttributes']={'position':mesh['position'].copy(),'faces':mesh['faces'].copy()}
        motion={'skeleton':skeleton,'row':{'root':'control','carrier':'carrier','literalActorScaleToken':'1'},
                'clips':{name:{'name':name,'length':1.,'nodes':{}} for name in ('pause1','pause2','walk','run','nwkickl','nwkickr')},'inputPins':{}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'input.json';out=root/'out'
            api.save_recipe(bundle,{'schemaVersion':1,'kind':'PhenoMorpher-candidate-inputs','motion':motion,
                'bindMeshes':meshes,'bindFrames':frames,'reference':{'slug':'human_female_fit','targetStatureMeters':1.}})
            with patch.object(cli,'declared'),contextlib.redirect_stdout(io.StringIO()):
                cli.main(['candidate','--bundle',str(bundle),'--output',str(out)])
            self.assertGreater((out/'proposal-clay.glb').stat().st_size,100)
            first=json.loads((out/'first-pass.json').read_text(),object_hook=api.array_hook)
            second=json.loads((out/'morphed-proposal.json').read_text(),object_hook=api.array_hook)
            self.assertTrue(second['receipt']['identityPreserved'])
            self.assertTrue(second['receipt']['sourceAnimationKeysExact'])
            self.assertFalse(second['receipt']['assetApprovalCreated'])
            for original,frozen,morphed in zip(meshes,first['standingMeshes'],second['standingMeshes']):
                np.testing.assert_array_equal(original['position'],frozen['position'])
                np.testing.assert_array_equal(frozen['position'],morphed['position'])

    def test_runner_rejects_root_escape_before_reading_nested_recipe(self):
        from . import inputs as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);release=root/'release';(release/'recipes').mkdir(parents=True)
            (release/'recipes/manifest.json').write_text(json.dumps({'targets':[{'recipe':{'path':'../../outside.json'}}]}))
            with self.assertRaisesRegex(ValueError,'escaped explicit root'):
                runner.consumed(['replay','--release',str(release)])

    def test_runtime_commands_run_only_through_the_managed_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json';plan.write_text('{}');blob=root/'r.mdl';blob.write_bytes(b'x')
            calls=[['anim-library','repoint','--input',str(blob),'--parent','a_ba','--output',str(root/'o.mdl')],
                   ['downsample-textures','--root',str(root),'--manifest',str(plan),'--output',str(root/'t')]]
            with patch.dict('os.environ',{'SRN_VERIFIED_INPUTS':''}),patch.object(cli,'_PINS',None):
                for argv in calls:
                    with self.assertRaisesRegex(ValueError,'run.py'):cli.main(argv)
            self.assertFalse((root/'o.mdl').exists() or (root/'t').exists())

    def test_runner_rejects_root_escape_in_adoption_plans(self):
        from . import inputs as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pin={'path':'../outside.json','sha256':'0'*64}
            (root/'plan.json').write_text(json.dumps({'baseContract':pin,'retiredResources':pin,'stock':pin,'textures':pin,'libraries':[],'roots':[]}))
            with self.assertRaisesRegex(ValueError,'escaped explicit root'):
                runner.consumed(['adopt-runtime','--root',str(root),'--plan',str(root/'plan.json'),'--output',str(root/'x')])

    def test_runner_rejects_nested_stock_and_receipt_paths_outside_their_folders(self):
        from . import inputs as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pin=lambda p:{'path':p,'sha256':'0'*64}
            (root/'contract.json').write_text(json.dumps({'resources':[]}))
            (root/'stock').mkdir();(root/'tex').mkdir()
            for stock_row,receipt_row,label in (({'a_ba':{'path':'../../outside.mdl'}},[],'stock'),
                                                ({},[{'path':'../../outside.plt'}],'receipt')):
                (root/'stock/stock.json').write_text(json.dumps({'models':stock_row}))
                (root/'tex/receipt.json').write_text(json.dumps({'resources':receipt_row}))
                (root/'plan.json').write_text(json.dumps({'baseContract':pin('contract.json'),'retiredResources':pin('contract.json'),
                    'stock':pin('stock/stock.json'),'textures':pin('tex/receipt.json'),'libraries':[],'roots':[]}))
                with self.subTest(label),self.assertRaisesRegex(ValueError,'escaped explicit root'):
                    runner.consumed(['adopt-runtime','--root',str(root),'--plan',str(root/'plan.json'),'--output',str(root/'x')])
            (root/'stock/stock.json').write_text(json.dumps({'models':{'a_ba':{'path':'../../outside.mdl'}}}))
            with self.assertRaisesRegex(ValueError,'escaped explicit root'):
                runner.consumed(['anim-library','inventory','--root',str(root),'--manifest',str(root/'contract.json'),
                                 '--stock',str(root/'stock/stock.json'),'--output',str(root/'y')])

    def test_runner_freezes_the_installed_keys_and_model_bifs_for_stock_extraction(self):
        from . import inputs as runner
        def key(bifs,entries):
            names=b''.join(n.encode()+b'\0' for n in bifs);table=24+40;strings=table+12*len(bifs);keys=strings+len(names)
            head=b'KEY V1  '+struct.pack('<IIII',len(bifs),len(entries),table,keys)+bytes(40)
            offset=strings;rows=b''
            for n in bifs:
                rows+=struct.pack('<IIHH',0,offset,len(n)+1,0);offset+=len(n)+1
            return head+rows+names+b''.join(struct.pack('<16sHI',r.encode(),t,i<<20) for r,t,i in entries)
        with tempfile.TemporaryDirectory() as tmp:
            game=Path(tmp)/'game';(game/'data').mkdir(parents=True);tool=Path(tmp)/'resman_cat.exe';tool.write_bytes(b'x')
            for name in ('models.bif','sounds.bif'):
                (game/'data'/name).write_bytes(b'BIFFV1  ')
            (game/'data/base.key').write_bytes(key(['data\\models.bif','data\\sounds.bif'],[('a_ba',2002,0),('step',4,1)]))
            argv=['anim-library','extract-stock','--resman-cat',str(tool),'--game-root',str(game),'--seed','a_ba','--output',str(Path(tmp)/'o')]
            self.assertEqual(runner.consumed(argv),{p.resolve() for p in (tool,game/'data/base.key',game/'data/models.bif')})
            (game/'data/base.key').write_bytes(key(['..\\outside.bif'],[('a_ba',2002,0)]))
            with self.assertRaisesRegex(ValueError,'escaped explicit root'):
                runner.consumed(argv)

    def test_runner_declares_source_attribute_files_in_addition_to_motion(self):
        from . import inputs as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'attributes.mdl';source.write_bytes(b'actual');bundle=root/'inputs.json'
            bundle.write_text(json.dumps({'motion':{'inputPins':{}},'bindMeshes':[{'sourceAttributePin':{'path':str(source),'sha256':api.digest(source)}}]}))
            self.assertIn(source.resolve(),runner.consumed(['candidate','--bundle',str(bundle)]))

    def test_replay_rejects_recipe_not_frozen_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'recipes').mkdir();recipe=root/'recipe.json';recipe.write_text('{}')
            manifest=root/'recipes/manifest.json';manifest.write_text(json.dumps({'targets':[{'recipe':{'path':'recipe.json','sha256':api.digest(recipe)}}]}))
            with patch.object(cli,'declared'),patch.object(cli,'snapshot',return_value={str(manifest.resolve()):api.digest(manifest)}):
                with self.assertRaisesRegex(ValueError,'stale source binding'):
                    cli.main(['replay','--release',str(root),'--output',str(root/'out')])
            self.assertFalse((root/'out').exists())

    def test_attribute_reader_keeps_stock_duplicate_attachments_with_mesh_attributes(self):
        from .engine.test_phenomorpher_scene_v15a import fixture
        from .engine.phenomorpher_scene_v15b import attach_source_attributes
        from .engine.silhouette_model import assemble
        data=bytearray(fixture())
        struct.pack_into('<I',data,12+0x4c,5)
        struct.pack_into('<III',data,12+0xe8+0x48,0x550,3,3)
        struct.pack_into('<III',data,12+0x550,0x158,0x580,0x5f0)
        for offset,key_offset,value_offset,x in ((0x580,0x660,0x680,1.),(0x5f0,0x690,0x6b0,2.)):
            at=12+offset;data[at+32:at+39]=b'Impact\0'
            struct.pack_into('<I',data,at+0x6c,1)
            struct.pack_into('<III',data,at+0x54,key_offset,1,1)
            struct.pack_into('<III',data,at+0x60,value_offset,3,3)
            struct.pack_into('<ihhhbb',data,12+key_offset,8,1,0,0,3,0)
            struct.pack_into('<fff',data,12+value_offset,x,0,0)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'test.mdl';source.write_bytes(data)
            skeleton,attributes,_=api.read_attributes(source)
            self.assertEqual(len(skeleton),5)
            np.testing.assert_array_equal(skeleton['impact']['position'],[1,0,0])
            np.testing.assert_array_equal(skeleton['impact__duplicate_2']['position'],[2,0,0])
            np.testing.assert_array_equal(attributes['mesh']['faces'],[[0,1,2]])
            np.testing.assert_array_equal(attributes['mesh']['color'].reshape(-1),[0xffffffff,0x01234567,0x89abcdef])
            meshes,_=assemble(source,{})
            attached=attach_source_attributes(meshes,meshes,{'rig':source,'parts':{}})
            self.assertEqual(len(attached),1)
            np.testing.assert_array_equal(attached[0]['sourceAttributes']['faces'],attributes['mesh']['faces'])
            self.assertEqual(source.read_bytes(),bytes(data))

    def test_both_native_traversals_reject_ambiguous_duplicates_and_internal_collisions(self):
        from .engine.phenomorpher_scene_v15b import native_attributes
        collision=bytearray(duplicate_fixture())
        struct.pack_into('<I',collision,12+0x4c,4)
        struct.pack_into('<III',collision,12+0xe8+0x48,0x500,3,3)
        struct.pack_into('<III',collision,12+0x500,0x158,0x1c8,0x238)
        at=12+0x238;name=b'impact__duplicate_2\0';collision[at+32:at+32+len(name)]=name
        struct.pack_into('<I',collision,at+0x6c,1)
        for payload in (duplicate_fixture(second_flags=33),duplicate_fixture(name='pelvis_g'),duplicate_fixture(first_has_child=True),bytes(collision)):
            for read in (lambda:native_model(payload,'test'),lambda:native_attributes(payload,'test',set())):
                with self.subTest(),self.assertRaisesRegex(ValueError,'Duplicate'):read()
