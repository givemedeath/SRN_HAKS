"""Source-bound calibration math, corruption, native serializer and lineage tests.

Synthetic static fixtures exercise the real material/geometry serialization.
They are test data, never generation, garment or client approval evidence.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image
import target_contract as c
import replay_stage_skin_calibration as cal
import target_part_stage as stage
import audit_target_native_part as audit
from place_purposebuilt_pelvis import read_glb,write_glb
from target_part_pipeline import execute
from test_target_part_stage import textured_fixture
from test_human_female_stock_exact import stock_fixture
from test_target_part_pipeline import target_fixture
import test_target_garment_face_ownership as garment_fixture


def save(path,value):
    path.write_text(json.dumps(value),encoding='utf-8');return path


def fit_fixture(root,part='bicepl',male=False,no_tangent=False):
    if male:tp=save(root/'target.json',target_fixture());target=c.load(tp)
    else:tp,target=stock_fixture(root)
    doc,binary=textured_fixture()
    if no_tangent:del doc['meshes'][0]['primitives'][0]['attributes']['TANGENT']
    raw=root/'raw.glb';write_glb(raw,doc,binary);job=save(root/'job.json',{'state':'success','promptId':'synthetic-calibration-test',
        'outputs':[{'localPath':str(raw),'sha256':c.sha(raw)}]})
    cfg={'schemaVersion':2,'operation':'fit','part':part,'coordinateSpace':'working','targetContract':str(tp),'targetContractSha256':c.sha(tp),
         'source':str(raw),'sourceSha256':c.sha(raw),'sourceReceipt':str(job),'sourceReceiptSha256':c.sha(job),
         'uniformScale':.4,'rotationDegreesXYZ':[4,9,0],'sourceAnchorNwn':[0,0,0],'targetAnchorLocal':[0,0,0]}
    rp=execute(save(root/'fit.json',cfg),root/'fit');g=json.loads(rp.read_text());return tp,target,rp,Path(g['candidate'])


def recipe_value(tp,target,rp,source,part,parent,parent_intensity,material=None,gain=1.,offset=-17.,space='working'):
    doc,b=read_glb(source);material=material or {'candidate':cal.file_row(source),'geometryReceipt':cal.file_row(rp),'coordinateSpace':space}
    return {'schemaVersion':1,'kind':'target-compiler-skin-intensity-calibration','diagnosticOnly':True,**c.binding(tp,target,space),'part':part,
        'geometryReceipt':cal.file_row(rp),'candidate':cal.file_row(source),'materialSource':material,'parent':parent,'gain':gain,'offsetBytes':offset,
        'parentAO0IntensitySha256':cal.fingerprint(parent_intensity),'sourceFingerprints':cal.source_fingerprints(doc,b),
        'quantization':cal.QUANTIZATION,'palettePolicy':cal.PALETTE,'calibrationApplications':1,'parentAoStrength':0,'frozenInputs':{}}


class CalibrationMathTests(unittest.TestCase):
    def test_exact_order_clipping_independent_ao_and_untreated_preservation(self):
        original=np.array([[0,13,100,254,255]],dtype='u1');red=np.full(original.shape,80,dtype='u1');saved=original.copy();prior=None
        for ao in (0,.15,.35):
            value,aux=cal.calibrated_intensity(original,red,1.2,-17.1,ao)
            parent=np.floor(np.clip(original.astype(float)*1.2-17.1,0,255)).astype('u1')
            expected=np.floor(parent*(1-ao*(1-80/255))).astype('u1')
            np.testing.assert_array_equal(value,expected);np.testing.assert_array_equal(aux['calibratedAO0'],parent)
            self.assertEqual(int(aux['clampedLow'].sum()),2);self.assertEqual(int(aux['clampedHigh'].sum()),2)
            if prior is not None and ao==.35:self.assertFalse(np.array_equal(value,np.floor(prior*(1-.35*(1-80/255))).astype('u1')))
            prior=value
        np.testing.assert_array_equal(original,saved)

    def test_rejects_negative_flat_boolean_nonfinite_coefficients_and_ao(self):
        a=np.array([[80]],dtype='u1')
        for g,o,ao in [(0,0,0),(-1,0,0),(.249,0,0),(2.01,0,0),(True,0,0),(1,True,0),(1,97,0),(1,float('nan'),0),(1,0,True),(1,0,.2)]:
            with self.subTest(g=g,o=o,ao=ao),self.assertRaises(ValueError):cal.calibrated_intensity(a,a,g,o,ao)

    def test_categorical_palette_before_filter_cannot_equal_lut_after_shade_filter(self):
        intensity=np.array([[0,255],[255,0]],dtype='u1');palette=np.zeros((9,256,3),dtype='u1');palette[3,0]=[20,40,60];palette[3,255]=[240,220,200]
        uv=np.array([[.5,.5]])
        np.testing.assert_allclose(cal.filtered_palette(intensity,palette,3,uv),[[130,130,130]])
        np.testing.assert_array_equal(palette[3,127],[0,0,0]);np.testing.assert_array_equal(cal.palette_texels(intensity,palette,3)[0,1],[240,220,200])
        for row in (True,-1,9):
            with self.assertRaises(ValueError):cal.palette_texels(intensity,palette,row)


class CalibrationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name).resolve();cls.tp,cls.target,cls.rp,cls.source=fit_fixture(cls.root)
        cls.doc,cls.binary=read_glb(cls.source);cls.parent={'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}}
        cls.original,cls.transport=stage.material_inputs(cls.doc,cls.binary,{0:'skin'},'bicepl',0,c.fixed_garment_parts(cls.target))
        cls.value=recipe_value(cls.tp,cls.target,cls.rp,cls.source,'bicepl',cls.parent,cls.original['skin']['intensity']);cls.counter=0
        runtime={'schemaVersion':2,'operation':'runtime','part':'bicepl','coordinateSpace':'runtime','targetContract':str(cls.tp),'targetContractSha256':c.sha(cls.tp),
            'source':str(cls.source),'sourceSha256':c.sha(cls.source),'sourceReceipt':str(cls.rp),'sourceReceiptSha256':c.sha(cls.rp)}
        cls.runtime_rp=execute(save(cls.root/'runtime.json',runtime),cls.root/'runtime');cls.runtime_source=Path(json.loads(cls.runtime_rp.read_text())['candidate'])

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def controls(self,value=None):
        type(self).counter+=1;p=save(self.root/('recipe'+str(self.counter)+'.json'),deepcopy(value or self.value));return {'mode':cal.MODE,'recipe':cal.file_row(p)}

    def inputs(self,value=None,ao=0,space='working',source=None,rp=None,target=None,tp=None):
        return cal.staging_inputs(self.controls(value),tp or self.tp,target or self.target,'bicepl',space,source or self.source,rp or self.rp,None,ao)

    def test_original_source_and_all_ao_siblings_exact_normal_roughness_and_no_source_edit(self):
        before=self.source.read_bytes();last=None
        for ao in (0,.15,.35):
            v=self.inputs(ao=ao);row=v['materialRows']['skin'];expected,_=cal.calibrated_intensity(self.original['skin']['intensity'],np.full((2048,2048),80,dtype='u1'),1,-17,ao)
            np.testing.assert_array_equal(row['intensity'],expected)
            for key in ('color','normal','roughness'):np.testing.assert_array_equal(row[key],self.original['skin'][key])
            self.assertEqual(v['proof']['recipeMode'],cal.MODE);self.assertEqual(v['proof']['calibrationApplications'],1);self.assertEqual(v['proof']['aoApplications'],1)
            self.assertEqual(v['proof']['clampedLowTexels'],0);self.assertGreater(v['proof']['representedSkinClipping']['representedSkinAreaSquareMetres'],0)
            if last is not None:self.assertEqual(v['proof']['independentAOSiblingIntensitySha256'],last)
            last=v['proof']['independentAOSiblingIntensitySha256']
        self.assertEqual(self.source.read_bytes(),before)

    def test_rehashed_parent_intensity_attribute_and_semantic_corruption_reject(self):
        changes=[('parentAO0IntensitySha256','0'*64),('calibrationApplications',2),('parentAoStrength',.15),('palettePolicy','palette-after-filter'),
                 ('quantization','fractional-luma-legacy'),('kind','target-part-stage')]
        for key,val in changes:
            bad=deepcopy(self.value);bad[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.inputs(bad)
        bad=deepcopy(self.value);bad['sourceFingerprints']['normalsFloat32']='0'*64
        with self.assertRaisesRegex(ValueError,'fingerprints'):self.inputs(bad)
        for mode in ('source-bound-skin-calibration-v1','replayed-c1-skin-intensity-inputs','arbitrary-png'):
            bad=deepcopy(self.value);bad['parent']['mode']=mode
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'chaining unsupported'):self.inputs(bad)

    def test_cross_target_part_space_stale_recipe_and_source_guards(self):
        for key,val in [('targetId','another-target'),('part','bicepr'),('coordinateSpace','runtime')]:
            bad=deepcopy(self.value);bad[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):self.inputs(bad)
        controls=self.controls();Path(controls['recipe']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'Frozen input changed'):cal.staging_inputs(controls,self.tp,self.target,'bicepl','working',self.source,self.rp,None,0)
        bad=deepcopy(self.value);bad['candidate']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen input changed'):self.inputs(bad)
        bad=deepcopy(self.value);bad['geometryReceipt']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen input changed'):self.inputs(bad)

    def test_explicit_single_identity_runtime_parent_preserves_current_geometry_and_parent(self):
        material={'candidate':cal.file_row(self.source),'geometryReceipt':cal.file_row(self.rp),'coordinateSpace':'working'}
        value=recipe_value(self.tp,self.target,self.runtime_rp,self.runtime_source,'bicepl',self.parent,self.original['skin']['intensity'],material=material,space='runtime')
        v=self.inputs(value,space='runtime',source=self.runtime_source,rp=self.runtime_rp)
        self.assertEqual(v['proof']['materialSourceLineage']['kind'],'single-explicit-stock-identity-working-to-runtime')
        self.assertEqual(v['sourceReceipt']['statureApplications'],1)
        self.assertEqual(v['document'],read_glb(self.runtime_source)[0]);self.assertEqual(v['binary'],read_glb(self.runtime_source)[1])
        bad=deepcopy(value);bad['materialSource']['coordinateSpace']='runtime'
        with self.assertRaises(ValueError):self.inputs(bad,space='runtime',source=self.runtime_source,rp=self.runtime_rp)
        orig=self.runtime_rp.read_bytes()
        try:
            for key,val in [('statureApplications',2),('operation','fit'),('sourceToAttachmentLocal',(np.eye(4)*.9).tolist())]:
                g=json.loads(orig);g[key]=val;save(self.runtime_rp,g);bad=deepcopy(value);bad['geometryReceipt']=cal.file_row(self.runtime_rp)
                with self.subTest(key=key),self.assertRaises(ValueError):self.inputs(bad,space='runtime',source=self.runtime_source,rp=self.runtime_rp)
        finally:self.runtime_rp.write_bytes(orig)

    def test_identity_runtime_guard_rejects_changed_literal_uv_and_source_normal(self):
        current=cal.geometry_input(cal.file_row(self.runtime_source),cal.file_row(self.runtime_rp),self.tp,self.target,'bicepl','runtime')
        material=cal.geometry_input(cal.file_row(self.source),cal.file_row(self.rp),self.tp,self.target,'bicepl','working')
        cal.material_lineage(current,material,self.tp,self.target,'bicepl','runtime')
        for semantic in ('TEXCOORD_0','NORMAL','COLOR_0'):
            modified=dict(current);modified['binary']=bytearray(current['binary']);doc=current['document'];index=doc['meshes'][0]['primitives'][0]['attributes'][semantic]
            a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']];at=v.get('byteOffset',0)+a.get('byteOffset',0);modified['binary'][at]^=1
            with self.subTest(semantic=semantic),self.assertRaises(ValueError):cal.material_lineage(modified,material,self.tp,self.target,'bicepl','runtime')

    def test_schema_bool_or_float_cannot_substitute_for_version_integer(self):
        for version in (True,1.0):
            bad=deepcopy(self.value);bad['schemaVersion']=version
            with self.subTest(version=version),self.assertRaisesRegex(ValueError,'Exact diagnostic'):self.inputs(bad)

    def test_skin_only_cannot_bypass_fixed_garment_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();tp,t,rp,source=fit_fixture(root,part='chest');d,b=read_glb(source);rows,_=stage.material_inputs(d,b,{0:'skin'},'chest',0,c.fixed_garment_parts(t))
            v=recipe_value(tp,t,rp,source,'chest',self.parent,rows['skin']['intensity']);p=save(root/'recipe.json',v)
            with self.assertRaisesRegex(ValueError,'outside fixed garments'):cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},tp,t,'chest','working',source,rp,None,0)

    def test_hand_absent_authored_tangent_is_truthfully_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();tp,t,rp,source=fit_fixture(root,part='handr',no_tangent=True);d,b=read_glb(source);rows,_=stage.material_inputs(d,b,{0:'skin'},'handr',0,c.fixed_garment_parts(t))
            value=recipe_value(tp,t,rp,source,'handr',self.parent,rows['skin']['intensity']);p=save(root/'recipe.json',value)
            v=cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},tp,t,'handr','working',source,rp,None,0)
            self.assertEqual(v['proof']['originalSourceTangentsStatus'],'absent');self.assertIsNone(v['proof']['sourceFingerprints']['authoredTangentsFloat32'])

    def test_new_mode_does_not_restrict_legacy_male_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();tp,t,rp,source=fit_fixture(root,male=True);d,b=read_glb(source);rows,_=stage.material_inputs(d,b,{0:'skin'},'bicepl',0,c.fixed_garment_parts(t))
            value=recipe_value(tp,t,rp,source,'bicepl',self.parent,rows['skin']['intensity']);p=save(root/'recipe.json',value)
            v=cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},tp,t,'bicepl','working',source,rp,None,0)
            self.assertEqual(v['sourceReceipt']['targetId'],'test-troll');self.assertFalse(v['proof']['selected'])

    def test_real_stage_and_native_effective_inputs_exact_and_corruption_guarded(self):
        cfg={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,'part':'bicepl','coordinateSpace':'working','targetContract':str(self.tp),'targetContractSha256':c.sha(self.tp),
             'source':str(self.source),'sourceSha256':c.sha(self.source),'sourceReceipt':str(self.rp),'sourceReceiptSha256':c.sha(self.rp),'skinIntensityInputs':self.controls(),'aoStrength':.15}
        out=self.root/'native-stage';rp=stage.stage(save(self.root/'stage.json',cfg),out);rec=json.loads(rp.read_text());self.assertEqual(rec['materialInputBasis'],cal.BASIS)
        effective=audit.audit_source_inputs(rec,self.source,self.rp,self.tp,self.target,'bicepl','working');self.assertTrue(effective['materialIntensityPixelsEdited']);self.assertFalse(effective['materialColorPixelsEdited'])
        self.assertEqual(rec['rawAttributeAsciiProof']['skin']['actualAsciiCornerMaximumErrors'],{'position':0,'normal':0,'uv':0})
        model=c.model(self.target,'bicepl');proof,_=audit.audit_material_resources(out/'resources',model,'skin',effective['materialRows']['skin'],rec);self.assertTrue(proof['normalPixelsExact'])
        for key,val in [('materialInputBasis','original-embedded-maps'),('untreatedParentSha256','0'*64),('derivedMaterialProof',None)]:
            bad=deepcopy(rec);bad[key]=val
            with self.subTest(key=key),self.assertRaises(ValueError):audit.audit_source_inputs(bad,self.source,self.rp,self.tp,self.target,'bicepl','working')
        bad=deepcopy(rec);bad['derivedMaterialProof']['aoApplications']=2
        with self.assertRaisesRegex(ValueError,'proof differs'):audit.audit_source_inputs(bad,self.source,self.rp,self.tp,self.target,'bicepl','working')
        path=out/'resources'/(model+'.plt');original=path.read_bytes();data=bytearray(original);data[24]^=1;path.write_bytes(data);forged=deepcopy(rec);forged['materialResourceHashes'][path.name]=c.sha(path)
        with self.assertRaisesRegex(ValueError,'PLT painted shade'):audit.audit_material_resources(out/'resources',model,'skin',effective['materialRows']['skin'],forged)
        path.write_bytes(original)
        for key,val in [('materialRoles',{'0':'skin'}),('garmentFaceInputs',{})]:
            bad=deepcopy(cfg);bad[key]=val
            with self.assertRaisesRegex(ValueError,'conflicting controls'):stage.stage_controls(bad)

    def test_detail_parent_is_replayed_at_ao0_not_generic_png_or_chained_intensity(self):
        # The detail module's independent real-data tests cover its source chart recipe.
        # Here spy on this new adapter boundary and supply explicitly synthetic rows.
        import replay_stage_skin_detail as detail
        import source_skin_detail_contract as contract
        material={'source':self.source,'receiptPath':self.rp,'receipt':json.loads(self.rp.read_text()),'document':self.doc,'binary':self.binary}
        pp=save(self.root/'synthetic-detail-receipt.json',{'unitFixture':True});mp=save(self.root/'synthetic-detail-manifest.json',{'unitFixture':True})
        controls={'mode':contract.MODE,'receipt':cal.file_row(pp),'sourceManifest':cal.file_row(mp)};parent={'mode':contract.MODE,'controls':controls}
        rows={'skin':dict(self.original['skin'])};rows['skin']['color']=rows['skin']['color'].copy();rows['skin']['color'][0,0]=[190,120,80]
        fake={'document':self.doc,'binary':self.binary,'materialRows':rows,'originalMaterialProof':self.transport,'proof':{'kind':contract.KIND,'unitFixture':True},'frozenInputs':{str(pp):c.sha(pp),str(mp):c.sha(mp)}}
        with patch.object(detail,'staging_inputs',return_value=fake) as worker:
            result=cal.parent_inputs(parent,material,self.tp,self.target,'shinl')
        self.assertEqual(worker.call_args.args[-1],0);self.assertEqual(worker.call_args.args[-2],{0:'skin'});self.assertEqual(worker.call_args.args[0],controls)
        self.assertEqual(result['materialRows']['skin']['color'][0,0].tolist(),[190,120,80]);self.assertIn(str(pp),result['pins'])


class CalibrationGarmentTests(unittest.TestCase):
    def setUp(self):
        self.fixture=garment_fixture.FaceGarmentOwnershipTests(methodName='test_shared_uv_can_propose_separate_role_copies_without_legacy_waiver');self.fixture.setUp();self.root=self.fixture.root
    def tearDown(self):self.fixture.tearDown()
    def preparation(self):
        f=self.fixture;pp,pr=f.propose();rp,review=f.review(pp,pr);parent={'mode':'reviewed-per-face-garment','controls':{'proposal':cal.file_row(pp),'review':cal.file_row(rp)}}
        from target_garment_face_ownership import reviewed_staging_inputs
        original=reviewed_staging_inputs(pp,rp,f.tp,f.target,'chest','working',f.source,f.rp,0)
        value=recipe_value(f.tp,f.target,f.rp,f.source,'chest',parent,original['materialRows']['skin']['intensity'])
        return value,original,rp,review
    def test_reviewed_cloth_exact_and_skin_calibrated_real_serializer(self):
        f=self.fixture;value,original,rp,review=self.preparation();p=save(self.root/'cal-recipe.json',value);controls={'mode':cal.MODE,'recipe':cal.file_row(p)}
        v=cal.staging_inputs(controls,f.tp,f.target,'chest','working',f.source,f.rp,None,.35)
        for role in ('skin','garment'):
            for key in ('color','normal','roughness'):np.testing.assert_array_equal(v['materialRows'][role][key],original['materialRows'][role][key])
        for key,row in original['materialRows']['garment'].items():np.testing.assert_array_equal(v['materialRows']['garment'][key],row)
        self.assertTrue(v['proof']['fixedClothResourcesAndParentPixelsExact']);self.assertFalse(v['proof']['originalRGBNormalORMUVAndAuthoredAttributesEdited'])
        cfg={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,'part':'chest','coordinateSpace':'working','targetContract':str(f.tp),'targetContractSha256':c.sha(f.tp),
            'source':str(f.source),'sourceSha256':c.sha(f.source),'sourceReceipt':str(f.rp),'sourceReceiptSha256':c.sha(f.rp),'skinIntensityInputs':controls,'aoStrength':.35}
        rec=json.loads(stage.stage(save(self.root/'stage.json',cfg),self.root/'stage').read_text());effective=audit.audit_source_inputs(rec,f.source,f.rp,f.tp,f.target,'chest','working')
        self.assertEqual(len(rec['materialResourceHashes']),8);cloth=np.asarray(Image.open(self.root/'stage/resources/pfh0_chest001f.tga'))
        np.testing.assert_array_equal(cloth,original['materialRows']['garment']['color']);self.assertEqual(effective['materialInputBasis'],cal.BASIS)
    def test_unapproved_garment_and_wrong_palette_evidence_cannot_be_calibrated(self):
        f=self.fixture;value,original,rp,review=self.preparation();review['accepted']=False;save(rp,review);value['parent']['controls']['review']=cal.file_row(rp);p=save(self.root/'cal.json',value)
        with self.assertRaisesRegex(ValueError,'Independent explicit'):cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},f.tp,f.target,'chest','working',f.source,f.rp,None,0)
        review['accepted']=True;review['paletteEdgeEvidence'].pop();save(rp,review);value['parent']['controls']['review']=cal.file_row(rp);save(p,value)
        with self.assertRaisesRegex(ValueError,'palette3 and8'):cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},f.tp,f.target,'chest','working',f.source,f.rp,None,0)
    def test_working_garment_review_only_bridges_explicit_identity_runtime(self):
        f=self.fixture;value,original,rp,review=self.preparation();cfg={'schemaVersion':2,'operation':'runtime','part':'chest','coordinateSpace':'runtime','targetContract':str(f.tp),'targetContractSha256':c.sha(f.tp),
            'source':str(f.source),'sourceSha256':c.sha(f.source),'sourceReceipt':str(f.rp),'sourceReceiptSha256':c.sha(f.rp)}
        rr=execute(save(self.root/'runtime.json',cfg),self.root/'runtime');source=Path(json.loads(rr.read_text())['candidate'])
        value=recipe_value(f.tp,f.target,rr,source,'chest',value['parent'],original['materialRows']['skin']['intensity'],material=value['materialSource'],space='runtime');p=save(self.root/'cal.json',value)
        v=cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},f.tp,f.target,'chest','runtime',source,rr,None,0)
        self.assertEqual(v['proof']['materialSourceLineage']['kind'],'single-explicit-stock-identity-working-to-runtime')
        self.assertEqual(v['binary'],read_glb(source)[1]);self.assertEqual(set(v['materialRoles'].values()),{'skin','garment'})


if __name__=='__main__':unittest.main()
