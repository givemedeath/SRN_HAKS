"""Native material audit replays reviewed face inputs; receipts cannot replace pixels."""
import copy
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

import target_contract as c
from audit_target_native_part import audit_source_inputs,audit_material_resources
from place_purposebuilt_pelvis import raw_corners,read_glb,write_glb
from target_garment_ownership import partition
from target_part_stage import material_inputs,stage
import test_target_garment_face_ownership as ownership_fixture


class ReviewedGarmentNativeAuditTests(unittest.TestCase):
    def setUp(self):
        self.f=ownership_fixture.FaceGarmentOwnershipTests(methodName='test_shared_uv_can_propose_separate_role_copies_without_legacy_waiver')
        self.f.setUp();self.root=self.f.root

    def tearDown(self):self.f.tearDown()

    def staged(self):
        f=self.f;pp,pr=f.propose();rp,_=f.review(pp,pr)
        config={'schemaVersion':2,'kind':'target-part-stage','diagnosticOnly':True,
                'part':'chest','coordinateSpace':'working','targetContract':str(f.tp),'targetContractSha256':c.sha(f.tp),
                'source':str(f.source),'sourceSha256':c.sha(f.source),'sourceReceipt':str(f.rp),'sourceReceiptSha256':c.sha(f.rp),
                'garmentFaceInputs':{'proposal':{'path':str(pp),'sha256':c.sha(pp)},'review':{'path':str(rp),'sha256':c.sha(rp)}},'aoStrength':.35}
        cp=self.root/'stage-config.json';cp.write_text(json.dumps(config));sp=stage(cp,self.root/'stage')
        return json.loads(sp.read_text()),pr

    def inputs(self,receipt):
        f=self.f
        return audit_source_inputs(receipt,f.source,f.rp,f.tp,f.target,'chest','working')

    def test_independent_replay_keeps_source_corners_and_audits_effective_cloth_plt_normal_roughness(self):
        f=self.f;receipt,proposal=self.staged();effective=self.inputs(receipt)
        doc,binary=read_glb(f.source);before=raw_corners(doc,binary)
        for key,rows in zip(('positions','normals','uv'),before[:3]):np.testing.assert_array_equal(effective[key],rows)
        self.assertTrue(effective['materialColorPixelsEdited']);self.assertEqual(effective['derivedMaterialProof'],receipt['derivedMaterialProof'])
        self.assertEqual([row['triangles'] for row in effective['primitives']],[1,1])
        self.assertEqual(effective['materialInputBasis'],'reviewed-per-face-derived-inputs')
        self.assertIn(Path(proposal['derivedCompilerInputs']['skin']['normal']['path']),effective['auditFiles'])
        resources=self.root/'stage/resources';compiled={'materialResourceHashes':{p.name:c.sha(p) for p in resources.iterdir()}}
        for role,pixels in effective['materialRows'].items():
            material='pfh0_chest001'+('f' if role=='garment' else '')
            proof,paths=audit_material_resources(resources,material,role,pixels,compiled)
            self.assertTrue(proof['compileTimeDependenciesExact']);self.assertEqual(len(paths),4)
            self.assertTrue(proof['normalPixelsExact']);self.assertTrue(proof['roughnessPixelsExact'])
        # Padding changes color at the old shared edge, while original maps remain exact.
        original,_=material_inputs(doc,binary,{0:'skin'},'chest',.35,c.fixed_garment_parts(f.target))
        self.assertFalse(np.array_equal(original['skin']['color'],effective['materialRows']['garment']['color']))
        for row in effective['materialRows'].values():
            np.testing.assert_array_equal(row['normal'],original['skin']['normal']);np.testing.assert_array_equal(row['roughness'],original['skin']['roughness'])
        self.assertEqual(c.sha(f.source),f.parent['candidateSha256'])

    def test_recorded_proof_roles_or_basis_cannot_replace_independent_replay(self):
        receipt,_=self.staged()
        for change in ('proof','roles','ao','basis','missing-proof','pin'):
            bad=copy.deepcopy(receipt)
            if change=='proof':bad['derivedMaterialProof']['normalPixelsExact']=False
            if change=='roles':bad['materialRoles']={key:('skin' if value=='garment' else 'garment') for key,value in bad['materialRoles'].items()}
            if change=='ao':bad['aoStrength']=.15
            if change=='basis':bad['materialInputBasis']='original-embedded-maps'
            if change=='missing-proof':bad['derivedMaterialProof']=None
            if change=='pin':bad['derivedMaterialProof']['reviewReceipt']['sha256']='f'*64
            with self.subTest(change=change),self.assertRaises(ValueError):self.inputs(bad)

    def test_rehashed_compiled_pixels_and_material_sidecars_cannot_hide_wrong_effective_inputs(self):
        receipt,_=self.staged();effective=self.inputs(receipt);folder=self.root/'stage/resources'
        kinds={'cloth':'pfh0_chest001f.tga','normal':'pfh0_chest001n.tga','roughness':'pfh0_chest001r.tga',
               'plt-intensity':'pfh0_chest001.plt','plt-layer':'pfh0_chest001.plt','mtr':'pfh0_chest001.mtr','dependency':'pfh0_chest001n.tga'}
        for change,name in kinds.items():
            path=folder/name;original=path.read_bytes();role='garment' if change=='cloth' else 'skin';material='pfh0_chest001'+('f' if role=='garment' else '')
            try:
                if change in ('cloth','normal','roughness'):
                    pixels=np.asarray(Image.open(path).convert('RGB')).copy();pixels[1024,1024,0]^=1;Image.fromarray(pixels).save(path)
                elif change.startswith('plt'):
                    data=bytearray(original);data[24+(2048*1024+1024)*2+(1 if change=='plt-layer' else 0)]^=1;path.write_bytes(data)
                elif change=='mtr':path.write_text(original.decode()+'texture0 pfh0_chest001\n')
                compiled={'materialResourceHashes':{p.name:c.sha(p) for p in folder.iterdir()}}
                if change=='dependency':compiled['materialResourceHashes'][name]='f'*64
                # Even rehashed native dependency receipts cannot declare these wrong pixels correct.
                with self.subTest(change=change),self.assertRaises(ValueError):
                    audit_material_resources(folder,material,role,effective['materialRows'][role],compiled)
            finally:path.write_bytes(original)

    def test_legacy_female_chest_uses_fixed_garment_owner_and_original_embedded_pixels(self):
        f=self.f;doc,binary=read_glb(f.source);partitioned,roles,_=partition(doc,binary,['skin','garment'],100000)
        source=self.root/'legacy-chest.glb';write_glb(source,partitioned,binary)
        introles={int(key):value for key,value in roles.items()}
        expected,transport=material_inputs(partitioned,binary,introles,'chest',.15,c.fixed_garment_parts(f.target))
        receipt={'materialRoles':roles,'aoStrength':.15,'materialProof':transport}
        # Historical v2 stages lack the optional basis/proof fields.
        effective=audit_source_inputs(receipt,source,f.rp,f.tp,f.target,'chest','working')
        self.assertIsNone(effective['derivedMaterialProof']);self.assertFalse(effective['materialColorPixelsEdited'])
        self.assertEqual(effective['materialInputBasis'],'original-embedded-maps')
        for role in expected:
            for name in expected[role]:np.testing.assert_array_equal(effective['materialRows'][role][name],expected[role][name])
        receipt['materialProof'][0]['normalStrength']=.5
        with self.assertRaisesRegex(ValueError,'original material transport'):
            audit_source_inputs(receipt,source,f.rp,f.tp,f.target,'chest','working')


if __name__=='__main__':unittest.main()
