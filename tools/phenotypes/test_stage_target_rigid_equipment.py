import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

import stage_target_rigid_equipment as stage
import target_contract as contract
from armory_rigid import correct_rigid, replace_array, profile_affine
from audit_geometry import arrays
from retarget import NODE
from pipeline import digest
from test_armory_rigid import SOURCE, RAW, PROFILE
from test_target_part_pipeline import target_fixture

IDENTITY={'scale':[1,1,1],'rotate':[0,0,0],'translate':[0,0,0]}
SOURCE=SOURCE.replace(' materialname skin\n','')
RAW=RAW.replace(' materialname skin\n','')


def normalized(root,text=SOURCE):
    a=root/'original/pmh0_chest002.mdl';b=root/'normalized/pmh0_chest002.mdl'
    a.parent.mkdir(parents=True);b.parent.mkdir(parents=True)
    a.write_text(text);b.write_text(text);correct_rigid(a,b,IDENTITY)
    return a,b


def make_inputs(root):
    stock=root/'stock';original,cs=normalized(stock);fitted=stock/'fitted'/cs.name;fitted.parent.mkdir();shutil.copyfile(cs,fitted)
    palette=stock/'pmh0_chest002.plt';palette.write_bytes(b'PLT V1  '+struct.pack('<IIII',4,0,1,1)+bytes([128,0]))
    inventory=stock/'inventory.json'
    inv={'kind':'installed-target-equipment-inputs','sourcePrefix':'pmh0','overridesDisabled':True,'missingDependencies':[],
     'models':[{'resource':original.name,'name':original.name,'part':'chest','style':2,'category':'rigid-armor','requiresSkinBindPath':False,'localAnimationCount':0,
      'rawPath':str(original),'sha256':digest(original),'asciiPath':str(original),'asciiSha256':digest(original),'renderTextureDependencies':[palette.name]}],
     'dependencies':[{'name':palette.name,'rawPath':str(palette),'sha256':digest(palette)}]}
    inventory.write_text(json.dumps(inv));target=root/'rig/target.json';target.parent.mkdir()
    data=target_fixture();data['equipment']={'sourcePrefix':'pmh0'}
    frame=np.eye(4);frame[:3,3]=[.4,-.2,1.2];frame[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]]
    data['rig']['frames']['working']['torso_g']=frame.tolist();runtime=frame.copy();runtime[:3,3]*=10/7;data['rig']['frames']['runtime']['torso_g']=runtime.tolist()
    target.write_text(json.dumps(data))
    capart=root/'capart.2da';capart.write_text('2DA V2.0\n\n NAME MDLNAME NODENAME\n0 0 CHEST torso_g\n')
    collision=root/'collision.json';collision.write_text(json.dumps({'kind':'target-rigid-equipment-collision-set',**contract.binding(target,data,'runtime'),'resourceHashes':{}}))
    armory=root/'fake-armory.exe';armory.write_bytes(b'unit-test-fake-only');binary_hash=digest(armory)
    toolchain=root/'toolchain.json';toolchain.write_text(json.dumps({'tools':{'armory':{'path':str(armory),'sha256':binary_hash}}}))
    migration=root/'migration.json';migration.write_text(json.dumps({'kind':'phenotype-shared-tool-migration','smokeChecksPassed':True,'toolchain':{'path':str(toolchain),'sha256':digest(toolchain)}}))
    ini=root/'profile.ini';ini.write_text(stage.armory_ini([(cs.stem,IDENTITY)]))
    profile=root/'profile.json';p={'schemaVersion':1,'kind':'target-rigid-equipment-profile',**contract.binding(target,data,'working'),
     'localSpace':'attachment-local','statureApplications':0,'sourceInventorySha256':digest(inventory),'armorySha256':binary_hash,
     'sharedToolchainSha256':digest(toolchain),'toolMigrationSha256':digest(migration),
     'part':'chest','attachmentJoint':'torso_g','calibrationResource':original.name,'calibrationSource':{'path':str(cs),'sha256':digest(cs)},
     'calibrationFitted':{'path':str(fitted),'sha256':digest(fitted)},'ini':{'path':str(ini),'sha256':digest(ini)},'transform':IDENTITY,
     'fitMode':'diagnostic-self','profileAccepted':False,'collisionReviewsAccepted':False,'materialBindingsAccepted':False}
    profile.write_text(json.dumps(p))
    job=root/'job.json';j={'schemaVersion':1,'kind':'target-rigid-equipment-job',**contract.binding(target,data,'working'),
     'localSpace':'attachment-local','statureApplications':0,'mode':'diagnostic','sourceInventory':{'path':str(inventory),'sha256':digest(inventory)},
     'sharedToolchain':{'path':str(toolchain),'sha256':digest(toolchain)},'toolMigration':{'path':str(migration),'sha256':digest(migration)},
     'armory':{'path':str(armory),'sha256':binary_hash},'attachmentTable':{'path':str(capart),'sha256':digest(capart)},
     'collisionManifest':{'path':str(collision),'sha256':digest(collision)},
     'entries':[{'sourceResource':original.name,'profile':{'path':str(profile),'sha256':digest(profile)},'materialBindings':[{'sourceResource':palette.name,'targetResource':'pmg0_chest002.plt','policy':'exact-native-model-plt','bindingReviewAccepted':False}],'externalDependencies':[]}]}
    job.write_text(json.dumps(j));return {'root':root,'target':target,'data':data,'inventory':inventory,'inv':inv,'profile':profile,'p':p,'job':job,'j':j,'binaryHash':binary_hash,'original':original,'cs':cs,'fitted':fitted,'ini':ini,'collision':collision,'toolchain':toolchain,'migration':migration}


class TargetRigidEquipmentTests(unittest.TestCase):
    def test_same_source_normalization_retains_nested_vertex_identity_and_normals(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=normalized(Path(temp));proof=stage.correspondence(a.read_text(),b.read_text(),b.read_text(),IDENTITY)
            self.assertLess(proof[0]['sourceNormalizationMaxError'],1e-8);self.assertTrue(proof[0]['orderedFacesUvsAndBindingsExact'])
            verts=stage.mesh_data(b.read_text())['torso_g']['vertices']
            np.testing.assert_allclose(verts,[[0,.4,-.3],[-1,.4,.7],[0,1.4,.7],[0,.4,.7]],atol=1e-9)
            normals=stage.mesh_data(b.read_text())['torso_g']['normals']
            np.testing.assert_allclose(normals,np.tile([-2**-.5,0,-2**-.5],(4,1)),atol=1e-9)

    def test_wrong_mesh_vertex_reorder_or_uv_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=normalized(Path(temp));text=b.read_text();block=next(n for n in NODE.finditer(text) if arrays(n[3],'verts'))
            vertices=np.asarray(arrays(block[3],'verts'));body=replace_array(block[3],'verts',vertices[[1,0,2,3]])
            bad=text[:block.start()]+f'node {block[1]} {block[2]}\n{body}endnode'+text[block.end():]
            with self.assertRaisesRegex(ValueError,'normalized same source'):stage.correspondence(a.read_text(),bad,bad,IDENTITY)
            uv=np.asarray(arrays(block[3],'tverts'));uv[0,0]=.25;body=replace_array(block[3],'tverts',uv)
            bad=text[:block.start()]+f'node {block[1]} {block[2]}\n{body}endnode'+text[block.end():]
            with self.assertRaisesRegex(ValueError,'faces/UVs'):stage.correspondence(a.read_text(),bad,bad,IDENTITY)

    def test_fitted_calibration_profile_must_match_actual_world_points(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=normalized(Path(temp));fitted=Path(temp)/'fitted.mdl';fitted.write_text(RAW);correct_rigid(a,fitted,PROFILE)
            proof=stage.correspondence(a.read_text(),b.read_text(),fitted.read_text(),PROFILE)
            self.assertLess(proof[0]['fitProfileMaxError'],1e-8)
            with self.assertRaisesRegex(ValueError,'affine profile'):stage.correspondence(a.read_text(),b.read_text(),fitted.read_text(),IDENTITY)

    def test_runtime_actor_world_scales_local_and_bind_translation_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a,working=normalized(root);runtime=root/'runtime.mdl';text=working.read_text();block=next(n for n in NODE.finditer(text) if arrays(n[3],'verts'))
            body=replace_array(block[3],'verts',np.asarray(arrays(block[3],'verts'))*10/7)
            runtime.write_text(text[:block.start()]+f'node {block[1]} {block[2]}\n{body}endnode'+text[block.end():])
            correct_rigid(working,runtime,{'scale':[10/7]*3,'translate':[0,0,0]});data=target_fixture()
            frame=np.eye(4);frame[:3,3]=[.4,-.2,1.2];frame[:3,:3]=[[0,-1,0],[1,0,0],[0,0,1]]
            data['rig']['frames']['working']['torso_g']=frame.tolist();rf=frame.copy();rf[:3,3]*=10/7;data['rig']['frames']['runtime']['torso_g']=rf.tolist()
            proof=stage.scale_actor_proof(working.read_text(),runtime.read_text(),data,'torso_g');self.assertEqual(proof['statureApplications'],1)
            with self.assertRaisesRegex(ValueError,'twice'):stage.scale_actor_proof(working.read_text(),working.read_text(),data,'torso_g')

    def test_exact_ini_rejects_selective_uv_transforms_and_broad_match(self):
        valid=stage.armory_ini([('pmh0_chest002',IDENTITY)]);stage.validate_profile_ini(valid,'pmh0_chest002',IDENTITY)
        for bad in (valid+'tscale=(2,2)\n',valid.replace('match=pmh0_chest002','match=*'),valid.replace('scale=(1,1,1)','scale=(2,2,2)')):
            with self.assertRaises(ValueError):stage.validate_profile_ini(bad,'pmh0_chest002',IDENTITY)

    def test_output_collision_protected_source_and_escape_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);art=root/'artifacts';art.mkdir();protected=art/'stock';protected.mkdir();existing=art/'existing';existing.mkdir()
            for output in (root/'elsewhere',existing,protected/'new'):
                with self.assertRaises(ValueError):stage.output_location(output,art,[protected])

    def test_production_requires_pilot_freeze_profile_collision_and_material(self):
        data=target_fixture();profile={'fitMode':'reviewed-regional','profileAccepted':True,'collisionReviewsAccepted':True,'materialBindingsAccepted':True}
        with self.assertRaisesRegex(ValueError,'frozen accepted'):stage.production_gates(data,profile,'production')
        data['rig'].update(pilotAccepted=True,frozen=True)
        for field in ('profileAccepted','collisionReviewsAccepted','materialBindingsAccepted'):
            bad={**profile,field:False}
            with self.assertRaises(ValueError):stage.production_gates(data,bad,'production')
        stage.production_gates(data,profile,'production')

    def run_rejected(self,inputs,message,mutate=None):
        if mutate:mutate(inputs)
        inputs['job'].write_text(json.dumps(inputs['j']));out=inputs['root']/'artifacts/result'
        with patch.object(stage,'ARMORY_SHA256',inputs['binaryHash']),patch.object(stage.shared_toolchain,'load',return_value=json.loads(inputs['toolchain'].read_text())),patch.object(stage.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,message):stage.prepare(inputs['job'],inputs['target'],out,artifact_root=inputs['root']/'artifacts')
            run.assert_not_called();self.assertFalse(out.exists())

    def test_revision_coordinate_space_and_double_scale_guards_before_any_tool(self):
        for field,value in (('rigRevision','other-rig'),('coordinateSpace','runtime'),('statureApplications',1)):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                f=make_inputs(Path(temp));f['j'][field]=value;self.run_rejected(f,'another target|no stature')

    def test_missing_dependency_shared_held_and_owned_name_collision_guards(self):
        for variant in ('missing','shared','collision'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                f=make_inputs(Path(temp))
                if variant=='missing':f['inv']['missingDependencies']=[{'model':'pmh0_chest002.mdl','bitmap':'missing'}];expected='Unresolved'
                elif variant=='shared':f['inv']['models'][0]['category']='helmet';expected='Shared held'
                else:
                    c=json.loads(f['collision'].read_text());c['resourceHashes']={'pmg0_chest002.mdl':'already-present'};f['collision'].write_text(json.dumps(c));f['j']['collisionManifest']['sha256']=digest(f['collision']);expected='collision'
                f['inventory'].write_text(json.dumps(f['inv']));f['j']['sourceInventory']['sha256']=digest(f['inventory'])
                self.run_rejected(f,expected)

    def test_inherited_source_is_rejected_without_private_bind_conversion(self):
        with self.assertRaisesRegex(ValueError,'private bind/controller'):
            stage.mesh_data(SOURCE.replace('setsupermodel pmh0_chest002 NULL','setsupermodel pmh0_chest002 pmh0'))

    def test_fitted_authored_normal_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=normalized(Path(temp));text=b.read_text();block=next(n for n in NODE.finditer(text) if arrays(n[3],'verts'))
            normals=np.asarray(arrays(block[3],'normals'));normals[0]=[0,1,0]
            body=replace_array(block[3],'normals',normals)
            bad=text[:block.start()]+f'node {block[1]} {block[2]}\n{body}endnode'+text[block.end():]
            with self.assertRaisesRegex(ValueError,'fitted authored normals'):
                stage.correspondence(a.read_text(),text,bad,IDENTITY)

    def test_human_and_female_target_writes_are_rejected(self):
        for kind in ('human','female'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                f=make_inputs(Path(temp))
                if kind=='human':
                    f['data']['identity']['prefix']='pmh0'
                    f['data']['models']={key:value.replace('pmg0','pmh0') for key,value in f['data']['models'].items()}
                    expected='cannot stage Human'
                else:
                    f['data']['identity']['gender']='female';expected='male phenotype'
                f['target'].write_text(json.dumps(f['data']));f['j'].update(contract.binding(f['target'],f['data'],'working'))
                self.run_rejected(f,expected)

    def test_shared_toolchain_and_migration_bytes_are_pinned(self):
        for field in ('sharedToolchain','toolMigration'):
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                f=make_inputs(Path(temp));f['j'][field]['sha256']='0'*64
                self.run_rejected(f,'Frozen input hash changed')
        with tempfile.TemporaryDirectory() as temp:
            f=make_inputs(Path(temp));f['p']['sharedToolchainSha256']='0'*64
            f['profile'].write_text(json.dumps(f['p']));f['j']['entries'][0]['profile']['sha256']=digest(f['profile'])
            self.run_rejected(f,'shared toolchain ownership')

    def test_failed_shared_migration_stops_before_any_armory_or_output(self):
        with tempfile.TemporaryDirectory() as temp:
            f=make_inputs(Path(temp));out=Path(temp)/'artifacts/result'
            with patch.object(stage.shared_toolchain,'load',side_effect=ValueError('Passed shared tool migration receipt required')) as load,patch.object(stage.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'Passed shared tool migration'):
                    stage.prepare(f['job'],f['target'],out,artifact_root=Path(temp)/'artifacts')
                load.assert_called_once_with(f['toolchain'].resolve(),f['migration'].resolve());run.assert_not_called();self.assertFalse(out.exists())

    def test_production_requires_complete_reviewed_collision_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            f=make_inputs(Path(temp));f['j']['mode']='production'
            self.run_rejected(f,'complete reviewed collision inventory')

    def test_partial_armory_batch_retained_quarantine_but_never_adopted(self):
        with tempfile.TemporaryDirectory() as temp:
            f=make_inputs(Path(temp));before=f['original'].read_bytes();out=Path(temp)/'artifacts/result'
            def run(command,**kwargs):
                if '--version' in command:return subprocess.CompletedProcess(command,0,'nwnarmory 1.3.4\n','')
                if '--values' in command:return subprocess.CompletedProcess(command,0,'; verts fit: max_residual=0\n; tverts fit: max_residual=0\n','')
                source,destination=Path(command[-2]),Path(command[-1]);shutil.copyfile(next(source.iterdir()),destination/'pmh0_chest002.mdl')
                return subprocess.CompletedProcess(command,1,'valid file written; batch failed\n','failure\n')
            with patch.object(stage,'ARMORY_SHA256',f['binaryHash']),patch.object(stage.shared_toolchain,'load',return_value=json.loads(f['toolchain'].read_text())),patch.object(stage.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(ValueError,'partial batch adoption'):stage.prepare(f['job'],f['target'],out,artifact_root=Path(temp)/'artifacts')
            self.assertTrue((out/'quarantine/working-raw/pmh0_chest002.mdl').exists());self.assertFalse((out/'runtime').exists());self.assertFalse((out/'preparation.json').exists())
            receipt=json.loads((out/'terminal-failure.json').read_text());self.assertFalse(receipt['productionAccepted']);self.assertTrue(receipt['partialBatchAdoptionBlocked']);self.assertEqual(f['original'].read_bytes(),before)


if __name__=='__main__':unittest.main()
