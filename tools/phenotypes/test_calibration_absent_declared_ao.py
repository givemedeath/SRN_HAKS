"""Declared Meshy-style absent AO uses identity; original maps and cloth stay exact.

Literal captured material declarations are exercised on synthetic fixtures;
current actual Meshy source proof is separately target-bound output evidence.
"""
from copy import deepcopy
from pathlib import Path
import tempfile,unittest,json
from unittest.mock import patch
import numpy as np
import target_contract as c
import replay_stage_skin_calibration as cal
import target_part_stage as stage
import test_stage_skin_calibration as fixtures
import test_target_garment_face_ownership as garments
from place_purposebuilt_pelvis import read_glb,embedded_maps
from test_target_part_stage import textured_fixture

MESHY_MATERIAL={'doubleSided':True,'name':'Material_0','normalTexture':{'index':0},
 'pbrMetallicRoughness':{'baseColorTexture':{'index':1},'metallicRoughnessTexture':{'index':2}}}


def meshy_no_ao_fixture():
    doc,binary=textured_fixture();doc['textures']=[doc['textures'][1],doc['textures'][0],doc['textures'][2]]
    doc['materials']=[deepcopy(MESHY_MATERIAL)];return doc,binary


def shared_no_ao_fixture():
    doc,binary=ORIGINAL_SHARED();material=doc['materials'][0];material.pop('occlusionTexture');material['name']='Material_0';material['doubleSided']=True
    return doc,binary

ORIGINAL_SHARED=garments.shared_uv_fixture


class AbsentDeclaredAOTests(unittest.TestCase):
    def test_literal_meshy_hand_declaration_all_siblings_identical_and_originals_protected(self):
        for part in ('handl','handr'):
            with self.subTest(part=part),tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve()
                with patch.object(fixtures,'textured_fixture',side_effect=meshy_no_ao_fixture):tp,t,rp,source=fixtures.fit_fixture(root,part=part,no_tangent=True)
                before=source.read_bytes();doc,binary=read_glb(source);self.assertEqual(doc['materials'],[MESHY_MATERIAL]);maps=embedded_maps(doc,binary)
                original,_=stage.material_inputs(doc,binary,{0:'skin'},part,0,c.fixed_garment_parts(t));parent={'mode':'original-materialRoles-skin','controls':{'materialRoles':{'0':'skin'}}}
                recipe=fixtures.recipe_value(tp,t,rp,source,part,parent,original['skin']['intensity']);p=fixtures.save(root/'recipe.json',recipe);controls={'mode':cal.MODE,'recipe':cal.file_row(p)};prior=None
                for ao in (0,.15,.35):
                    v=cal.staging_inputs(controls,tp,t,part,'working',source,rp,None,ao)
                    expected,_=cal.calibrated_intensity(original['skin']['intensity'],np.full((2048,2048),255,dtype='u1'),1,-17,0)
                    np.testing.assert_array_equal(v['materialRows']['skin']['intensity'],expected)
                    self.assertEqual(v['proof']['originalAOProvenance'][0]['policy'],'absent-declared-occlusionTexture-identity255')
                    self.assertIsNone(v['proof']['originalAOProvenance'][0]['originalOcclusionTextureBinding']);self.assertFalse(v['proof']['originalAOProvenance'][0]['ORMRedInferredAsAO'])
                    self.assertEqual(len(set(v['proof']['independentAOSiblingIntensitySha256'].values())),1)
                    for key in ('color','normal','roughness'):np.testing.assert_array_equal(v['materialRows']['skin'][key],original['skin'][key])
                    self.assertEqual(embedded_maps(v['document'],v['binary']),maps)
                    if prior is not None:np.testing.assert_array_equal(v['materialRows']['skin']['intensity'],prior)
                    prior=v['materialRows']['skin']['intensity']
                self.assertEqual(source.read_bytes(),before)

    def test_reviewed_torso_no_ao_calibrates_skin_and_preserves_all_fixed_cloth_rows(self):
        f=garments.FaceGarmentOwnershipTests(methodName='test_shared_uv_can_propose_separate_role_copies_without_legacy_waiver')
        with patch.object(garments,'shared_uv_fixture',side_effect=shared_no_ao_fixture):f.setUp()
        try:
            before=f.source.read_bytes();pp,pr=f.propose();rp,_=f.review(pp,pr)
            from target_garment_face_ownership import reviewed_staging_inputs
            original=reviewed_staging_inputs(pp,rp,f.tp,f.target,'chest','working',f.source,f.rp,0)
            parent={'mode':'reviewed-per-face-garment','controls':{'proposal':cal.file_row(pp),'review':cal.file_row(rp)}}
            recipe=fixtures.recipe_value(f.tp,f.target,f.rp,f.source,'chest',parent,original['materialRows']['skin']['intensity']);p=fixtures.save(f.root/'recipe.json',recipe)
            for ao in (0,.15,.35):
                v=cal.staging_inputs({'mode':cal.MODE,'recipe':cal.file_row(p)},f.tp,f.target,'chest','working',f.source,f.rp,None,ao)
                expected,_=cal.calibrated_intensity(original['materialRows']['skin']['intensity'],np.full((2048,2048),255,dtype='u1'),1,-17,0)
                np.testing.assert_array_equal(v['materialRows']['skin']['intensity'],expected)
                for key,row in original['materialRows']['garment'].items():np.testing.assert_array_equal(v['materialRows']['garment'][key],row)
                self.assertEqual(v['proof']['originalAOProvenance'][0]['policy'],'absent-declared-occlusionTexture-identity255');self.assertTrue(v['proof']['fixedClothResourcesAndParentPixelsExact'])
            self.assertEqual(f.source.read_bytes(),before)
        finally:f.tearDown()

    def test_declared_original_red_preserved_and_mixed_differing_effective_ao_rejected(self):
        doc,binary=textured_fixture();red,provenance=cal.ao_inputs(doc,binary,{0:'skin'});self.assertTrue(np.all(red==80));self.assertEqual(provenance[0]['policy'],'declared-original-occlusionTexture-red')
        self.assertEqual(provenance[0]['originalOcclusionTextureBinding'],doc['materials'][0]['occlusionTexture']);self.assertFalse(provenance[0]['ORMRedInferredAsAO'])
        doc['materials'].append(deepcopy(doc['materials'][0]));_,p=cal.ao_inputs(doc,binary,{0:'skin',1:'skin'});self.assertEqual(len(p),2)
        doc['materials'][1].pop('occlusionTexture')
        with self.assertRaisesRegex(ValueError,'exact common original AOred'):cal.ao_inputs(doc,binary,{0:'skin',1:'skin'})
        doc['materials'][0].pop('occlusionTexture');red,_=cal.ao_inputs(doc,binary,{0:'skin',1:'skin'});self.assertTrue(np.all(red==255))

    def test_absence_does_not_infer_orm_or_silently_accept_invalid_declared_binding(self):
        doc,binary=meshy_no_ao_fixture();doc['materials'][0]['pbrMetallicRoughness']['metallicRoughnessTexture']={'index':999999}
        red,p=cal.ao_inputs(doc,binary,{0:'skin'});self.assertTrue(np.all(red==255));self.assertFalse(p[0]['ORMRedInferredAsAO'])
        doc['materials'][0]['occlusionTexture']=None
        with self.assertRaisesRegex(ValueError,'Declared original occlusionTexture binding'):cal.ao_inputs(doc,binary,{0:'skin'})
        doc['materials'][0]['occlusionTexture']={'index':2,'texCoord':1}
        with self.assertRaisesRegex(ValueError,'TEXCOORD_0'):cal.ao_inputs(doc,binary,{0:'skin'})

if __name__=='__main__':unittest.main()
