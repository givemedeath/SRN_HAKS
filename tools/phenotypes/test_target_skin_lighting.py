"""Failure-oriented diagnostic light-atlas protection and provenance tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PIL import Image
import target_contract as contract
from place_purposebuilt_pelvis import read_glb, write_glb
from target_part_pipeline import execute
from test_human_female_stock_exact import stock_fixture
from test_target_part_stage import textured_fixture
import target_skin_lighting_contract as lighting


class SkinLightingContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.target_path,self.target=stock_fixture(self.root)
        self.source=self.root/'source.glb';write_glb(self.source,*textured_fixture())
        job=self.root/'generation.json';job.write_text(json.dumps({'state':'success','promptId':'diagnostic-test',
            'generationBinding':{**{k:v for k,v in contract.binding(self.target_path,self.target,'working').items() if k!='coordinateSpace'},'part':'bicepl'},
            'outputs':[{'localPath':str(self.source),'sha256':contract.sha(self.source)}]}))
        cfg={'schemaVersion':2,'operation':'fit','part':'bicepl','coordinateSpace':'working',
            'targetContract':str(self.target_path),'targetContractSha256':contract.sha(self.target_path),
            'source':str(self.source),'sourceSha256':contract.sha(self.source),'sourceReceipt':str(job),
            'sourceReceiptSha256':contract.sha(job),'uniformScale':.4,'rotationDegreesXYZ':[4,9,0],
            'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
        fit=self.root/'fit.json';fit.write_text(json.dumps(cfg));receipt=execute(fit,self.root/'fitted')
        geometry=json.loads(receipt.read_text());self.candidate=Path(geometry['candidate'])
        review=self.root/'normal-review.json';review.write_text(json.dumps({'targetId':self.target['id'],
            'source':{'path':str(self.source),'sha256':contract.sha(self.source)},'knownDefects':['Explicit synthetic test; not visual acceptance.']}))
        self.neighbor=self.root/'stock-neck.mdl';self.neighbor.write_bytes(b'untreated stock-neck proof')
        palette=self.root/'palette.png';Image.new('RGB',(256,10),(128,96,72)).save(palette)
        style=self.root/'style.png';Image.new('RGB',(8,8),(110,80,65)).save(style)
        self.config={'schemaVersion':2,'kind':'target-skin-lighting-diagnostic','diagnosticOnly':True,
            'targetContract':str(self.target_path),'targetContractSha256':contract.sha(self.target_path),
            'part':'bicepl','coordinateSpace':'working','source':str(self.candidate),'sourceSha256':contract.sha(self.candidate),
            'sourceReceipt':str(receipt),'sourceReceiptSha256':contract.sha(receipt),'materialRoles':{'0':'skin'},
            'normalInputReview':{'path':str(review),'sha256':contract.sha(review),'status':'diagnostic-with-known-defects'},
            'protectedInputs':{str(self.neighbor):contract.sha(self.neighbor)},
            'protectedRegions':[{'label':'measured shoulder','originLocal':[0,0,0],'normalLocal':[0,0,1],
                'halfWidthMeters':.02,'fadeWidthMeters':.02}],
            'lighting':{'frame':'target-world-bind','device':'CPU','resolution':2048,'samples':16,'seed':1790,
                'worldStrength':.02,'marginPixels':16,'lights':[{'id':'frozen-key','type':'AREA',
                    'positionWorld':[-3,4,5],'energy':500,'sizeMeters':3}]},
            'treatment':{'strengths':[0,.35,.65,1],'maxDarkenShades':64,'maxBrightenShades':48,
                'normalization':'surface-area-weighted-mean','maskGuardPixels':2},
            'palette':{'path':str(palette),'sha256':contract.sha(palette),'rows':[3,8]},
            'referenceStyle':{'path':str(style),'sha256':contract.sha(style)}}
        self.path=self.root/'lighting.json'

    def tearDown(self):self.tmp.cleanup()

    def prepare(self,config=None):
        self.path.write_text(json.dumps(config or self.config));return lighting.prepare(self.path)

    def test_prepare_retains_untreated_model_and_maps_without_selection(self):
        original=self.candidate.read_bytes();before={p:contract.sha(p) for p in self.root.rglob('*') if p.is_file()};data=self.prepare()
        self.assertEqual(data['target']['identity']['gender'],'female');self.assertEqual(data['parent']['statureApplications'],0)
        self.assertEqual(self.candidate.read_bytes(),original)
        self.assertTrue(all(entry['sourceMaterial']['normalTexture']['scale']==1 for entry in data['materials'].values()))
        np.testing.assert_array_equal(data['materials'][0]['maps']['normal'][1][0,0],[111,133,244])
        np.testing.assert_array_equal(data['materials'][0]['maps']['orm'][1][0,0],[80,170,23])
        np.testing.assert_allclose(np.linalg.norm(data['normals'],axis=2),1.3,atol=2e-7)
        self.assertTrue((data['tangents'][:,:,3]==-1).all())
        self.assertIn(str(self.source),data['frozenInputs']);self.assertIn(str(self.neighbor),data['frozenInputs'])
        self.assertEqual({p:contract.sha(p) for p in before},before)
        self.assertFalse(any(p.suffix in ('.plt','.mtr','.tga') for p in self.root.rglob('*'))) # Preparation cannot stage game resources.

    def test_stale_source_receipt_target_neighbor_palette_and_reference_rejected(self):
        for name in ('sourceSha256','sourceReceiptSha256','targetContractSha256'):
            bad=copy.deepcopy(self.config);bad[name]='0'*64
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Frozen input changed'):self.prepare(bad)
        for name in ('palette','referenceStyle','normalInputReview'):
            bad=copy.deepcopy(self.config);bad[name]['sha256']='0'*64
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Frozen input changed'):self.prepare(bad)
        self.neighbor.write_bytes(b'modified neighbor')
        with self.assertRaisesRegex(ValueError,'Frozen input changed'):self.prepare()

    def test_cross_target_part_and_runtime_receipts_rejected(self):
        receipt=Path(self.config['sourceReceipt']);original=receipt.read_bytes()
        for field,value in [('targetId','another-target'),('part','bicepr'),('coordinateSpace','runtime')]:
            altered=json.loads(original);altered[field]=value;receipt.write_text(json.dumps(altered))
            bad=copy.deepcopy(self.config);bad['sourceReceiptSha256']=contract.sha(receipt)
            with self.subTest(field=field),self.assertRaises(ValueError):self.prepare(bad)
        receipt.write_bytes(original)
        review=Path(self.config['normalInputReview']['path']);content=json.loads(review.read_text());content['targetId']='another-target';review.write_text(json.dumps(content))
        bad=copy.deepcopy(self.config);bad['normalInputReview']['sha256']=contract.sha(review)
        with self.assertRaisesRegex(ValueError,'Normal review belongs'):self.prepare(bad)

    def test_explicit_bounded_cpu_controls_and_head_neck_exclusion(self):
        for name,value in [('device','GPU'),('resolution',1024),('samples',24.5),('seed',True),('worldStrength',float('nan')),
                ('marginPixels',33),('frame','camera')]:
            bad=copy.deepcopy(self.config);bad['lighting'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):lighting.validate_controls(bad)
        for name,value in [('strengths',[0,.65,.35]),('strengths',[0,1.1]),('maxDarkenShades',97),('maskGuardPixels',0)]:
            bad=copy.deepcopy(self.config);bad['treatment'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):lighting.validate_controls(bad)
        for part in ('neck','head'):
            bad=copy.deepcopy(self.config);bad['part']=part
            with self.assertRaisesRegex(ValueError,'head/neck'):lighting.validate_controls(bad)
        bad=copy.deepcopy(self.config);bad['selected']=True
        with self.assertRaisesRegex(ValueError,'unknown'):lighting.validate_controls(bad)
        bad=copy.deepcopy(self.config);bad['protectedInputs']={}
        with self.assertRaisesRegex(ValueError,'neighboring'):lighting.validate_controls(bad)

    def test_normal_strength_and_garment_ownership_cannot_be_reinterpreted(self):
        bad=copy.deepcopy(self.config);bad['materialRoles']={'0':'garment'}
        with self.assertRaisesRegex(ValueError,'ownership'):self.prepare(bad)
        bad['materialRoles']={'0':'skin','1':'garment'}
        with self.assertRaisesRegex(ValueError,'ownership'):self.prepare(bad)
        doc,binary=read_glb(self.candidate);doc['materials'][0]['normalTexture']['scale']=.35;write_glb(self.candidate,doc,binary)
        # Rebinding a receipt is not allowed to silently change normal strength.
        receipt=Path(self.config['sourceReceipt']);record=json.loads(receipt.read_text());record['candidateSha256']=contract.sha(self.candidate);receipt.write_text(json.dumps(record))
        bad=copy.deepcopy(self.config);bad['sourceSha256']=contract.sha(self.candidate);bad['sourceReceiptSha256']=contract.sha(receipt)
        with self.assertRaisesRegex(ValueError,'normal strength'):self.prepare(bad)

    def test_declared_chest_and_pelvis_garments_remain_required(self):
        # Identity is checked before roles, so use a genuinely bound fit for the owner.
        for part in ('chest','pelvis'):
            source=self.root/(part+'.glb');write_glb(source,*textured_fixture())
            job=self.root/(part+'-job.json');job.write_text(json.dumps({'state':'success','promptId':'owner-test',
                'outputs':[{'localPath':str(source),'sha256':contract.sha(source)}]}))
            fit={'schemaVersion':2,'operation':'fit','part':part,'coordinateSpace':'working',
                'targetContract':str(self.target_path),'targetContractSha256':contract.sha(self.target_path),
                'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(job),'sourceReceiptSha256':contract.sha(job),
                'uniformScale':.4,'rotationDegreesXYZ':[0,0,0],'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
            path=self.root/(part+'-fit.json');path.write_text(json.dumps(fit));receipt=execute(path,self.root/(part+'-fit'))
            record=json.loads(receipt.read_text());review=self.root/(part+'-review.json');review.write_text(json.dumps({'targetId':self.target['id'],'source':{'sha256':contract.sha(source)}}))
            bad=copy.deepcopy(self.config);bad.update(part=part,source=record['candidate'],sourceSha256=record['candidateSha256'],sourceReceipt=str(receipt),sourceReceiptSha256=contract.sha(receipt))
            bad['normalInputReview'].update(path=str(review),sha256=contract.sha(review))
            with self.subTest(part=part),self.assertRaisesRegex(ValueError,'Required owner garment'):self.prepare(bad)


class SkinLightingProtectionTests(unittest.TestCase):
    def test_raw_gltf_top_left_sampling_is_asymmetric_and_not_double_flipped(self):
        atlas=np.array([[10,20],[70,90]],dtype=float)
        np.testing.assert_array_equal(lighting.sample(atlas,np.array([[0,0],[1,0],[0,1],[1,1]])),[10,20,70,90])
        self.assertEqual(lighting.sample(atlas,np.array([[.5,.5]]))[0],47.5)

    def test_crossing_triangle_protected_even_when_no_vertex_is_in_band(self):
        p=np.array([[[0,0,-.1],[1,0,.1],[0,1,.1]],[[0,0,.3],[1,0,.3],[0,1,.3]]])
        uv=np.array([[[.05,.05],[.4,.05],[.05,.4]],[[.55,.55],[.95,.55],[.55,.95]]])
        region=[{'originLocal':[0,0,0],'normalLocal':[0,0,1],'halfWidthMeters':.02,'fadeWidthMeters':.02}]
        influence,coverage,garment,protected=lighting.masks(p,uv,['skin','skin'],64,region,2)
        self.assertTrue(protected[8,8]);self.assertEqual(influence[8,8],0);self.assertFalse(protected[40,40]);self.assertGreater(influence[40,40],.9)
        self.assertFalse(influence[~coverage].any());self.assertFalse(garment.any())
        # Guard extends two texels outside the crossing triangle without affecting other islands.
        self.assertTrue(protected[1,3]);self.assertEqual(influence[1,3],0)

    def test_garment_wins_over_overlapping_skin_atlas_and_invalid_uv_rejected(self):
        p=np.array([[[0,0,.3],[1,0,.3],[0,1,.3]]]*2);uv=np.array([[[.1,.1],[.9,.1],[.1,.9]]]*2)
        region=[{'originLocal':[0,0,0],'normalLocal':[0,0,1],'halfWidthMeters':.02,'fadeWidthMeters':.02}]
        influence,coverage,garment,protected=lighting.masks(p,uv,['garment','skin'],32,region,2)
        self.assertTrue(garment[5,5]);self.assertFalse(influence[garment].any());self.assertTrue(protected[garment].all())
        bad=uv.copy();bad[0,0,0]=1.2
        with self.assertRaisesRegex(ValueError,'Wrapped'):lighting.masks(p,bad,['skin','skin'],32,region,2)

    def test_independent_strengths_are_bounded_and_protected_bytes_exact(self):
        original=np.full((4,4),105,dtype='u1');field=np.tile([0,.5,1,4],(4,1));influence=np.ones((4,4))
        garment=np.zeros((4,4),dtype=bool);garment[0]=True;protected=np.zeros((4,4),dtype=bool);protected[:,0]=True
        outputs=[lighting.compose(original,field,influence,garment,protected,s,64,48) for s in (0,.35,.65,1)]
        np.testing.assert_array_equal(outputs[0],original)
        np.testing.assert_array_equal(outputs[-1][1],[105,52,105,153]);self.assertEqual(outputs[2][1,3],136)
        for image in outputs:np.testing.assert_array_equal(image[garment|protected],original[garment|protected])
        self.assertTrue((original==105).all());self.assertFalse(np.array_equal(outputs[2],lighting.compose(outputs[1],field,influence,garment,protected,.65,64,48)))
        for change in ('nonfinite','mask','shape'):
            bad=field.astype(float).copy();gp=garment
            if change=='nonfinite':bad[1,1]=float('nan')
            if change=='mask':gp=garment.astype('u1')
            if change=='shape':bad=bad[:2]
            with self.subTest(change=change),self.assertRaises(ValueError):lighting.compose(original,bad,influence,gp,protected,.65,64,48)

    def test_surface_weighting_does_not_equate_uv_area_and_unlit_bakes_rejected(self):
        raw=np.zeros((2,2,3));raw[:,0]=1;raw[:,1]=3
        samples=np.array([[0,0],[1,0]]);weights=np.array([3.,1.])
        field,mean=lighting.normalized_lighting(raw,samples,weights)
        self.assertAlmostEqual(mean,1.5);self.assertAlmostEqual(field[0,0],2/3);self.assertAlmostEqual(field[0,1],2)
        with self.assertRaisesRegex(ValueError,'unlit'):lighting.normalized_lighting(np.zeros_like(raw),samples,weights)
        with self.assertRaisesRegex(ValueError,'nonnegative'):lighting.normalized_lighting(-raw,samples,weights)


if __name__=='__main__':unittest.main()


