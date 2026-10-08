"""Explicit staging consumes reviewed role copies and rejects unsupported input paths."""
import copy
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

import target_contract as contract
from target_part_stage import stage,stage_controls
import test_target_garment_face_ownership as ownership_fixture


class ReviewedGarmentStageTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ownership_fixture.FaceGarmentOwnershipTests(methodName='test_shared_uv_can_propose_separate_role_copies_without_legacy_waiver')
        self.fixture.setUp()
        self.root=self.fixture.root

    def tearDown(self):
        self.fixture.tearDown()

    def config(self,pp,rp,name='stage'):
        f=self.fixture
        value={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,
               'part':'chest','coordinateSpace':'working',
               'targetContract':str(f.tp),'targetContractSha256':contract.sha(f.tp),
               'source':str(f.source),'sourceSha256':contract.sha(f.source),
               'sourceReceipt':str(f.rp),'sourceReceiptSha256':contract.sha(f.rp),
               'garmentFaceInputs':{'proposal':{'path':str(pp),'sha256':contract.sha(pp)},
                                    'review':{'path':str(rp),'sha256':contract.sha(rp)}},
               'aoStrength':0}
        path=self.root/(name+'.json');path.write_text(json.dumps(value))
        return path,value

    def test_serialized_skin_cloth_use_reviewed_copies_and_keep_original_attributes(self):
        f=self.fixture;pp,pr=f.propose();rp,_=f.review(pp,pr)
        config,_=self.config(pp,rp);old=contract.sha(f.source)
        result=stage(config,self.root/'stage');receipt=json.loads(result.read_text())
        model='pfh0_chest001';resources=self.root/'stage/resources'
        self.assertEqual(receipt['materialInputBasis'],'reviewed-per-face-derived-inputs')
        proof=receipt['derivedMaterialProof']
        self.assertEqual(proof['proposalReceipt']['sha256'],contract.sha(pp))
        self.assertTrue(proof['geometryBINExact'])
        self.assertTrue(proof['attributesUVNormalsTangentsExact'])
        self.assertTrue(proof['normalPixelsExact'])
        self.assertEqual(contract.sha(f.source),old)
        self.assertFalse(receipt['clientAccepted']);self.assertFalse(receipt['productionAccepted'])
        self.assertFalse(receipt['nativeCompiled'])
        self.assertEqual(len(receipt['materialResourceHashes']),8)
        intensity=np.frombuffer((resources/(model+'.plt')).read_bytes()[24:],dtype='u1').reshape(2048,2048,2)[::-1]
        expected=np.asarray(Image.open(pr['derivedCompilerInputs']['skin']['pltIntensityAO0']['path']))
        np.testing.assert_array_equal(intensity[:,:,0],expected)
        self.assertFalse(intensity[:,:,1].any())
        cloth=np.asarray(Image.open(resources/(model+'f.tga')).convert('RGB'))
        expected_cloth=np.asarray(Image.open(pr['derivedCompilerInputs']['garment']['baseColor']['path']))
        np.testing.assert_array_equal(cloth,expected_cloth)
        # The former shared UV edge now gets independently padded skin and cloth.
        self.assertGreater(int(intensity[1024,1024,0]),80)
        np.testing.assert_array_equal(cloth[1024,1023],[31,43,40])
        for role in ('skin','garment'):
            material=model+('f' if role=='garment' else '')
            normal=np.asarray(Image.open(resources/(material+'n.tga')).convert('RGB'))
            original=np.asarray(Image.open(pr['derivedCompilerInputs'][role]['normal']['path']).convert('RGB'))
            np.testing.assert_array_equal(normal,original)
            self.assertEqual(receipt['rawAttributeAsciiProof'][role]['actualAsciiCornerMaximumErrors'],
                             {'position':0,'normal':0,'uv':0})
        self.assertIn(str(pp),receipt['frozenInputs'])
        self.assertIn(str(rp),receipt['frozenInputs'])

    def test_unreviewed_inputs_and_known_source_defects_do_not_write_stage(self):
        f=self.fixture
        pp,pr=f.propose();rp,review=f.review(pp,pr)
        review['accepted']=False;rp.write_text(json.dumps(review));config,_=self.config(pp,rp,'unreviewed')
        with self.assertRaisesRegex(ValueError,'Independent explicit'):
            stage(config,self.root/'unreviewed-stage')
        self.assertFalse((self.root/'unreviewed-stage').exists())
        pp,pr=f.propose('source-defect',{'knownSourceGarmentDefects':['Extra rear straps.']})
        rp,_=f.review(pp,pr,'defect-review');config,_=self.config(pp,rp,'defect')
        with self.assertRaisesRegex(ValueError,'revised source'):
            stage(config,self.root/'defect-stage')
        self.assertFalse((self.root/'defect-stage').exists())

    def test_stale_review_and_sidecars_reject_before_resource_output(self):
        f=self.fixture;pp,pr=f.propose();rp,_=f.review(pp,pr);config,value=self.config(pp,rp)
        value['garmentFaceInputs']['review']['sha256']='f'*64;config.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'Frozen input'):
            stage(config,self.root/'bad-review-stage')
        self.assertFalse((self.root/'bad-review-stage').exists())
        config,_=self.config(pp,rp,'bad-sidecar')
        Path(pr['derivedCompilerInputs']['skin']['baseColor']['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input'):
            stage(config,self.root/'bad-sidecar-stage')
        self.assertFalse((self.root/'bad-sidecar-stage').exists())

    def test_unsupported_treatments_and_competing_roles_fail_closed(self):
        base={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,'materialRoles':{'0':'skin'}}
        stage_controls(base)
        for key in ('skinIntensityTreatment','garmentColourCorrection','aoStrenth'):
            bad=copy.deepcopy(base);bad[key]={}
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'Unsupported stage control'):
                stage_controls(bad)
        both=copy.deepcopy(base);both['garmentFaceInputs']={'proposal':{},'review':{}}
        with self.assertRaisesRegex(ValueError,'either original'):
            stage_controls(both)
        del base['materialRoles']
        with self.assertRaisesRegex(ValueError,'either original'):
            stage_controls(base)
        for controls in ({'proposal':{}},{'proposal':{'path':'p','sha256':'x','extra':True},'review':{'path':'r','sha256':'x'}}):
            bad=copy.deepcopy(base);bad['garmentFaceInputs']=controls
            with self.assertRaisesRegex(ValueError,'proposal/review'):
                stage_controls(bad)


if __name__=='__main__':
    unittest.main()
