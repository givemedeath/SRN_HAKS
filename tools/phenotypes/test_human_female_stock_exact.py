"""Stock-exact identity, provenance, garment, fixture and runtime guards."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

import target_contract as contract
from retarget import nodes, transforms
from target_body_inventory import compose, expected_body_resources, skin_atlas_keys, validate_body_ownership
from target_fixture import actors, documents, fixture_profiles, module_name, scripts
from target_part_stage import material_inputs, stage
from target_part_pipeline import execute, generation_source
from place_purposebuilt_pelvis import read_glb, raw_corners, write_glb
from test_mirror_stock_limb_part import fixture
from test_target_part_pipeline import target_fixture
from test_target_part_stage import textured_fixture


def stock_fixture(root):
    text = 'newmodel pfh0\nsetsupermodel pfh0 a_fa\nbeginmodelgeom pfh0\nnode dummy pfh0\n parent NULL\n position 0 0 0\nendnode\n'
    for index,name in enumerate(contract.PART_JOINTS.values()):
        text += 'node dummy '+name+'\n parent pfh0\n position '+str(index*.01)+' .02 .3\n orientation 0 0 1 .1\nendnode\n'
    text += 'endmodelgeom pfh0\ndonemodel pfh0\n'
    source = root/'pfh0.mdl';source.write_text(text,encoding='cp1252')
    frames = {name:value.tolist() for name,value in transforms(nodes(text)).items()}
    proof = {'kind':'stock-target-reference','pass':True,'prefix':'pfh0','heightMeters':1.8,
             'frames':frames,'frozenInputs':{str(source):contract.sha(source)},
             'rootAscii':{'path':str(source),'sha256':contract.sha(source)}}
    receipt = root/'stock.json';receipt.write_text(json.dumps(proof))
    data = target_fixture();data.update(id='test-human-female',workingHeightMeters=1.8,heightMeters=1.8)
    data['identity']={'gender':'female','phenotype':0,'prefix':'pfh0','raceId':6,'appearanceRow':6}
    data['models']={part:'pfh0_'+part+'001' for part in contract.PART_JOINTS}
    data['rig'].update(mode='stock-exact',sourcePrefix='pfh0',runtimeScale=1,positionPolicy='stock-exact',
        frames={'working':copy.deepcopy(frames),'runtime':copy.deepcopy(frames)},privateAliases={},
        stockReferenceReceipt={'path':str(receipt),'sha256':contract.sha(receipt)})
    data['material']={'fixedGarmentParts':['chest','pelvis']}
    path = root/'target.json';path.write_text(json.dumps(data))
    return path,data


class FemaleStockExactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.path,self.target=stock_fixture(self.root)

    def tearDown(self):self.tmp.cleanup()

    def test_pinned_stock_hierarchy_accepts_without_private_pilot(self):
        result=contract.load(self.path)
        self.assertTrue(contract.rig_ready(result));self.assertFalse(result['rig']['pilotAccepted'])
        self.assertEqual(result['rig']['frames']['working'],result['rig']['frames']['runtime'])

    def test_gender_family_race_appearance_and_source_must_agree(self):
        for section,key,value in [('identity','gender','male'),('identity','prefix','pfg0'),
            ('identity','raceId',2),('identity','appearanceRow',2),('identity','phenotype',2),
            ('rig','sourcePrefix','pmh0')]:
            bad=copy.deepcopy(self.target);bad[section][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):contract.validate(bad)

    def test_runtime_scaling_and_moved_or_private_binds_are_rejected(self):
        bad=copy.deepcopy(self.target);bad['rig']['runtimeScale']=2;bad['heightMeters']=3.6
        for value in bad['rig']['frames']['runtime'].values():
            for axis in range(3):value[axis][3]*=2
        with self.assertRaisesRegex(ValueError,'identity'):contract.validate(bad)
        for key,value in [('privateAliases',{'a_fa':'private'}),('changedLocalPositions',{'torso_g':[0,0,1]})]:
            bad=copy.deepcopy(self.target);bad['rig'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'private'):contract.validate(bad)
        bad=copy.deepcopy(self.target)
        for space in ('working','runtime'):bad['rig']['frames'][space]['torso_g'][0][3]+=.01
        self.path.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,'frames differ'):contract.load(self.path)

    def test_stale_receipt_root_and_cross_target_proof_are_rejected(self):
        receipt=Path(self.target['rig']['stockReferenceReceipt']['path']);original=receipt.read_bytes()
        receipt.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError,'receipt changed'):contract.load(self.path)
        receipt.write_bytes(original);source=self.root/'pfh0.mdl';source.write_text('changed')
        with self.assertRaisesRegex(ValueError,'stock input changed'):contract.load(self.path)
        self.path,self.target=stock_fixture(self.root)
        proof=json.loads(receipt.read_text());proof['prefix']='pmh0';receipt.write_text(json.dumps(proof))
        self.target['rig']['stockReferenceReceipt']['sha256']=contract.sha(receipt);self.path.write_text(json.dumps(self.target))
        with self.assertRaisesRegex(ValueError,'identity/proof'):contract.load(self.path)

    def test_per_node_skin_atlases_are_superseded_by_the_single_plt_contract(self):
        parts=contract.BODY_PARTS;garments={'chest','pelvis'};extra={'pelvis':['skin1']}
        resources=expected_body_resources(self.target,parts,garments)
        models={contract.model(self.target,part)+'.mdl':part for part in parts}
        with self.assertRaisesRegex(ValueError,'superseded by the single-PLT'):expected_body_resources(self.target,parts,garments,extra)
        with self.assertRaisesRegex(ValueError,'superseded by the single-PLT'):
            validate_body_ownership(self.target,models,resources,True,garments,extra_skin_atlases=extra)
        legacy={'pfh0_pelviss1'+suffix for suffix in ('.mtr','.plt','n.tga','r.tga')}
        with self.assertRaisesRegex(ValueError,'undeclared'):validate_body_ownership(self.target,models,resources|legacy,True,garments)
        # Legacy typed atlas slots still parse; node-keyed single-PLT slots never own extra atlases.
        self.assertEqual(skin_atlas_keys({'0':{'role':'skin','atlasKey':'skin'},'2':{'role':'skin','atlasKey':'skin2'},
                                          '1':{'role':'skin','atlasKey':'skin1'},'4':{'role':'garment','atlasKey':'garment'}}),['skin1','skin2'])
        self.assertEqual(skin_atlas_keys({'pfh0_pelvis001p0':{'role':'garment','pltLayers':[4]},'pfh0_pelvis001p1':{'role':'skin','pltLayers':[0]},
                                          'pfh0_pelvis001p2':{'role':'skin','pltLayers':[0]}}),[])

    def test_fourteen_parts_and_two_garment_owners_have_derived_70_single_plt_resources(self):
        import single_plt_part_contract as single_plt
        parts=contract.BODY_PARTS;garments={'chest','pelvis'}
        resources=expected_body_resources(self.target,parts,garments)
        self.assertEqual(len(parts),14);self.assertEqual(len(resources),single_plt.closure_count(self.target,parts))
        self.assertEqual(len(resources),70);self.assertEqual(resources,expected_body_resources(self.target,parts,set()))
        models={contract.model(self.target,part)+'.mdl':part for part in parts}
        validate_body_ownership(self.target,models,resources,True,garments)
        for foreign in ('pmh0_chest001.mdl','pfh0.mdl','pfh0_head001.mdl','appearance.2da','pfh0_handl001f.tga',
                        'pfh0_chest001f.mtr','pfh0_chest001f.tga','pfh0_pelvis001fn.tga','pfh0_pelvis001fr.tga','pfh0_pelviss2.plt'):
            with self.subTest(foreign=foreign),self.assertRaises(ValueError):
                validate_body_ownership(self.target,models,resources|{foreign},True,garments)
        with self.assertRaises(ValueError):validate_body_ownership(self.target,models,resources,True,{'pelvis'})
        for malformed in ([['chest']],['chest','chest'],['handl']):
            bad=copy.deepcopy(self.target);bad['material']['fixedGarmentParts']=malformed
            with self.assertRaises(ValueError):contract.validate(bad)

    def test_chest_and_pelvis_cloth_preserve_original_maps_and_skin_shading(self):
        doc,binary=textured_fixture();doc['materials'].append(copy.deepcopy(doc['materials'][0]))
        for part in ('chest','pelvis'):
            rows,_=material_inputs(doc,binary,{0:'skin',1:'garment'},part,0,{'chest','pelvis'})
            np.testing.assert_array_equal(rows['skin']['normal'][0,0],[111,133,244])
            self.assertEqual(rows['skin']['intensity'][0,0],int(np.dot([128,95,72],[.2126,.7152,.0722])))
            np.testing.assert_array_equal(rows['garment']['color'][0,0],[128,95,72])
        with self.assertRaises(ValueError):material_inputs(doc,binary,{0:'skin',1:'garment'},'handl',0,{'chest','pelvis'})
        with self.assertRaisesRegex(ValueError,'only to pelvis'):material_inputs(doc,binary,{0:'skin',1:'garment'},'chest',0)

    def test_female_stock_and_candidate_fixture_identity_and_modules(self):
        profiles=fixture_profiles(self.target)
        self.assertEqual(len(profiles),6);self.assertEqual(module_name(self.target),'srn_female_test')
        for profile in profiles:
            rows=actors({},self.target,profile,3,8)
            self.assertEqual(len(rows),8)
            for index,row in enumerate(rows):
                self.assertEqual([row[key]['value'] for key in ('Race','Gender','Phenotype','Appearance_Type')],[6,1,0,6])
                self.assertEqual(row['Color_Skin']['value'],8 if profile.endswith('-palette') and index%2 else 3)
            doc=documents({},self.target,profile,3,8)
            self.assertEqual(doc['module.ifo']['Mod_HakList']['value'][0]['Mod_Hak']['value'],'srn_female_test')
            self.assertIn('HUMAN_FEMALE_FIXTURE',scripts(profile,self.target)['sr_tm_enter'])
        legacy=target_fixture();self.assertEqual(module_name(legacy),'srn_troll_test')
        self.assertTrue(all(row['Gender']['value']==0 for row in actors({},legacy,'troll-poses',3,8)))

    def _fit(self, part, document=None):
        source=self.root/(part+'-raw.glb');write_glb(source,*(document or fixture()))
        job=self.root/(part+'-job.json');job.write_text(json.dumps({'state':'success','promptId':'test',
            'outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}))
        config={'schemaVersion':2,'operation':'fit','part':part,'coordinateSpace':'working',
            'targetContract':str(self.path),'targetContractSha256':contract.sha(self.path),
            'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(job),
            'sourceReceiptSha256':contract.sha(job),'uniformScale':.6,'rotationDegreesXYZ':[0,0,0],
            'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
        path=self.root/(part+'-fit.json');path.write_text(json.dumps(config))
        receipt=execute(path,self.root/(part+'-fitted'))
        return receipt,json.loads(receipt.read_text())

    def test_stock_hierarchy_rejects_unresolved_duplicate_scaled_and_wrong_family_roots(self):
        for change,reason in [
            (lambda text:text.replace('parent pfh0','parent missing',1),'Unresolved'),
            (lambda text:text.replace('endmodelgeom','node dummy pfh0\n parent NULL\nendnode\nendmodelgeom',1),'Duplicate'),
            (lambda text:text.replace('parent NULL','parent NULL\n scale 2',1),'Nonidentity'),
            (lambda text:text.replace('newmodel pfh0','newmodel pmh0',1),'family')]:
            self.path,self.target=stock_fixture(self.root)
            source=self.root/'pfh0.mdl';source.write_text(change(source.read_text()))
            receipt=Path(self.target['rig']['stockReferenceReceipt']['path']);proof=json.loads(receipt.read_text())
            proof['rootAscii']['sha256']=contract.sha(source);proof['frozenInputs'][str(source)]=contract.sha(source)
            receipt.write_text(json.dumps(proof));self.target['rig']['stockReferenceReceipt']['sha256']=contract.sha(receipt)
            self.path.write_text(json.dumps(self.target))
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):contract.load(self.path)

    def test_invalid_numerical_stature_controls_are_rejected(self):
        for factor in (True,'1',0,float('nan')):
            bad=copy.deepcopy(self.target);bad['rig']['runtimeScale']=factor
            with self.subTest(factor=factor),self.assertRaisesRegex(ValueError,'finite runtime'):contract.validate(bad)
        for height in (True,0,-1,float('nan')):
            bad=copy.deepcopy(self.target);bad['heightMeters']=bad['workingHeightMeters']=height
            with self.subTest(height=height),self.assertRaisesRegex(ValueError,'finite stature'):contract.validate(bad)

    def test_chest_and_pelvis_stage_require_cloth_and_serialize_exact_maps(self):
        from PIL import Image
        for part in ('chest','pelvis'):
            doc,binary=textured_fixture();doc['materials'].append(copy.deepcopy(doc['materials'][0]))
            # Split the tetrahedron's four distinct triangles across skin and cloth.
            doc['accessors'][3]['count']=6
            cloth_index=copy.deepcopy(doc['accessors'][3]);cloth_index.update(byteOffset=12)
            doc['accessors'].append(cloth_index)
            cloth=copy.deepcopy(doc['meshes'][0]['primitives'][0]);cloth.update(material=1,indices=len(doc['accessors'])-1)
            doc['meshes'][0]['primitives'].append(cloth)
            parent_path,parent=self._fit(part,(doc,binary))
            config={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,
                'part':part,'coordinateSpace':'working','targetContract':str(self.path),
                'targetContractSha256':contract.sha(self.path),'source':parent['candidate'],
                'sourceSha256':parent['candidateSha256'],'sourceReceipt':str(parent_path),
                'sourceReceiptSha256':contract.sha(parent_path),'materialRoles':{'0':'skin','1':'skin'}}
            path=self.root/(part+'-stage.json');path.write_text(json.dumps(config))
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'Fixed garment required'):
                stage(path,self.root/(part+'-missing-cloth'))
            self.assertFalse((self.root/(part+'-missing-cloth')).exists())
            config['materialRoles']['1']='garment';path.write_text(json.dumps(config))
            result=stage(path,self.root/(part+'-stage'));record=json.loads(result.read_text())
            model=contract.model(self.target,part);folder=result.parent/'resources'
            # The HIGH GLB stage still serializes its historical per-node garment maps exactly ...
            self.assertEqual(set(record['materialResourceHashes']),{model+suffix for suffix in ('.mtr','.plt','n.tga','r.tga','f.mtr','f.tga','fn.tga','fr.tga')})
            self.assertTrue(record['rigValidated']);self.assertFalse(record['rigPilotAccepted'])
            np.testing.assert_array_equal(np.asarray(Image.open(folder/(model+'fn.tga')))[0,0],[111,133,244])
            np.testing.assert_array_equal(np.asarray(Image.open(folder/(model+'fr.tga')))[0,0],[102,102,102])
            np.testing.assert_array_equal(np.asarray(Image.open(folder/(model+'f.tga')))[0,0],[128,95,72])
            self.assertIn('Roughness 0',(folder/(model+'f.mtr')).read_text())
            # ... but a stock-exact body cannot compose it: garments must live in the part PLT dye layers.
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'undeclared/missing material'):
                compose(self.path,[result],self.root/(part+'-legacy-composition'),'working')
            self.assertFalse((self.root/(part+'-legacy-composition')).exists())

    def _single_plt_stages(self, garment_layer=4, bitmap_suffix='', paint_layer=None):
        from test_single_plt_part_contract import ascii_model, plt_bytes
        receipts=[]
        for part in sorted(contract.BODY_PARTS):
            folder=self.root/part;(folder/'resources').mkdir(parents=True);(folder/'ascii').mkdir()
            model=contract.model(self.target,part);source=folder/'ascii'/(model+'.mdl')
            garment={part} if part in {'chest','pelvis'} else set()
            source.write_text(ascii_model(model,garment_bitmap=(model+bitmap_suffix) if garment else None),encoding='cp1252')
            (folder/'resources'/(model+'.mtr')).write_text('renderhint NormalTangents\ntexture1 '+model+'n\ntexture3 '+model+'r\n')
            painted=garment_layer if paint_layer is None else paint_layer
            (folder/'resources'/(model+'.plt')).write_bytes(plt_bytes(garment_layer=painted if garment else 0))
            for name in (model+'n.tga',model+'r.tga'):(folder/'resources'/name).write_bytes(('authored '+name).encode())
            slots={model+'p0':{'role':'garment' if garment else 'skin','pltLayers':[garment_layer if garment else 0]},
                   model+'p1':{'role':'skin','pltLayers':[0]}}
            record={'schemaVersion':2,'kind':'target-part-stage',**contract.binding(self.path,self.target,'runtime'),
                'part':part,'statureApplications':1,'materialLayout':'single-plt-per-part-v1',
                'materialRoles':{node:row['role'] for node,row in slots.items()},'materialSlots':slots,
                'asciiModel':str(source),'asciiModelSha256':contract.sha(source),
                'materialResourceHashes':{path.name:contract.sha(path) for path in (folder/'resources').iterdir()},'frozenInputs':{}}
            path=folder/'target-stage.json';path.write_text(json.dumps(record));receipts.append(path)
        return receipts

    def test_complete_stock_body_composes_without_private_pilot(self):
        receipts=self._single_plt_stages()
        result=compose(self.path,receipts,self.root/'complete',require_complete=True);record=json.loads(result.read_text())
        self.assertTrue(record['completeBodyComposed']);self.assertTrue(record['rigValidated'])
        self.assertEqual(record['rigMode'],'stock-exact');self.assertFalse(record['rigPilotAccepted'])
        self.assertEqual(len(record['asciiModelHashes'])+len(record['materialResourceHashes']),70)
        self.assertEqual(record['resourceClosure'],70);self.assertEqual(record['materialLayout'],'single-plt-per-part-v1')
        self.assertEqual(record['partMaterialSlots']['pelvis']['pfh0_pelvis001p0'],{'role':'garment','pltLayers':[4]})
        self.assertFalse(record['nativeCompiled']);self.assertFalse(record['clientAccepted'])

    def test_native_body_verification_rechecks_single_plt_layers(self):
        from target_body_inventory import flat_hashes, verify_native_body
        result=compose(self.path,self._single_plt_stages(),self.root/'complete',require_complete=True)
        converted=result.parent;record=json.loads(result.read_text());models=[]
        for name,digest in record['asciiModelHashes'].items():
            binary=converted/'resources'/name;binary.write_bytes(b'\0\0\0\0native '+name.encode())
            models.append({'name':name,'sourceSha256':digest,'binarySha256':contract.sha(binary),'bytes':binary.stat().st_size})
        (converted/'native-compile.json').write_text(json.dumps({'complete':True,'clientSha256':'c'*64,'models':models,
            'materialResourceHashes':record['materialResourceHashes']}))
        native,checked,actual=verify_native_body(converted,self.path)
        self.assertEqual(len(actual),70);self.assertEqual(checked['partMaterialSlots'],record['partMaterialSlots'])
        from test_single_plt_part_contract import plt_bytes
        plt=converted/'resources'/'pfh0_chest001.plt';plt.write_bytes(plt_bytes(garment_layer=6))
        with self.assertRaises(ValueError):verify_native_body(converted,self.path)

    def test_complete_body_rejects_per_node_material_bindings(self):
        with self.assertRaisesRegex(ValueError,'must equal the model name'):
            compose(self.path,self._single_plt_stages(bitmap_suffix='f'),self.root/'per-node',require_complete=True)
        self.assertFalse((self.root/'per-node').exists())

    def test_complete_body_rejects_garment_texels_outside_declared_dye_layers(self):
        with self.assertRaisesRegex(ValueError,'declared garment layers'):
            compose(self.path,self._single_plt_stages(paint_layer=5),self.root/'wrong-layer',require_complete=True)
        self.assertFalse((self.root/'wrong-layer').exists())

    def test_generation_binding_accepts_only_declared_target_rig_and_part(self):
        source=self.root/'bound-source.glb';write_glb(source,*fixture())
        binding=contract.binding(self.path,self.target,'working');binding.pop('coordinateSpace');binding['part']='chest'
        record={'state':'success','promptId':'test','generationBinding':binding,
            'outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}
        path=self.root/'bound-job.json';path.write_text(json.dumps(record))
        self.assertEqual(generation_source(source,path,self.path,self.target,'chest'),record)
        with self.assertRaisesRegex(ValueError,'explicit target'):generation_source(source,path)
        for key,value in [('part','pelvis'),('targetId','another-human-female'),
            ('rigRevision','stale'),('targetContractSha256','0'*64)]:
            bad=copy.deepcopy(record);bad['generationBinding'][key]=value;path.write_text(json.dumps(bad))
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'another target'):
                generation_source(source,path,self.path,self.target,'chest')
        record.pop('generationBinding');path.write_text(json.dumps(record))
        self.assertEqual(generation_source(source,path),record)

    def test_same_family_cross_target_runtime_receipt_is_rejected(self):
        path,fitted=self._fit('bicepl')
        other=copy.deepcopy(self.target);other['id']='another-human-female'
        other_path=self.root/'other-target.json';other_path.write_text(json.dumps(other))
        config={'schemaVersion':2,'operation':'runtime','part':'bicepl','coordinateSpace':'runtime',
            'targetContract':str(other_path),'targetContractSha256':contract.sha(other_path),
            'source':fitted['candidate'],'sourceSha256':fitted['candidateSha256'],
            'sourceReceipt':str(path),'sourceReceiptSha256':contract.sha(path)}
        path=self.root/'other-runtime.json';path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError,'another target'):execute(path,self.root/'cross-target')
        self.assertFalse((self.root/'cross-target').exists())

    def test_identity_conversion_is_recorded_once_and_retains_serialized_positions(self):
        source=self.root/'raw.glb';write_glb(source,*fixture())
        job=self.root/'job.json';job.write_text(json.dumps({'state':'success','promptId':'test',
            'outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}))
        base={'schemaVersion':2,'operation':'fit','part':'bicepl','coordinateSpace':'working',
            'targetContract':str(self.path),'targetContractSha256':contract.sha(self.path),
            'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(job),
            'sourceReceiptSha256':contract.sha(job),'uniformScale':.6,'rotationDegreesXYZ':[0,0,0],
            'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
        config=self.root/'fit.json';config.write_text(json.dumps(base));fitted_path=execute(config,self.root/'fitted')
        fitted=json.loads(fitted_path.read_text());base.update(operation='runtime',coordinateSpace='runtime',
            source=fitted['candidate'],sourceSha256=fitted['candidateSha256'],sourceReceipt=str(fitted_path),sourceReceiptSha256=contract.sha(fitted_path))
        for control in ('uniformScale','rotationDegreesXYZ','sourceAnchorNwn','targetAnchorLocal'):
            base.pop(control)
        config=self.root/'runtime.json';config.write_text(json.dumps(base));runtime_path=execute(config,self.root/'runtime')
        runtime=json.loads(runtime_path.read_text());self.assertEqual(runtime['statureApplications'],1)
        before=raw_corners(*read_glb(fitted['candidate']));after=raw_corners(*read_glb(runtime['candidate']))
        for original,converted in zip(before[:3],after[:3]):np.testing.assert_array_equal(original,converted)
        base.update(source=runtime['candidate'],sourceSha256=runtime['candidateSha256'],sourceReceipt=str(runtime_path),sourceReceiptSha256=contract.sha(runtime_path))
        config.write_text(json.dumps(base))
        with self.assertRaises(ValueError):execute(config,self.root/'repeated')


if __name__=='__main__':unittest.main()
